import asyncio
import base64
import gc
import io
import os
import re
import threading
from typing import AsyncGenerator, Dict, Any, Optional, Tuple, List, cast
import httpx
import numpy as np
import soundfile as sf
import torch
from openai import AsyncOpenAI
from kokoro import KPipeline

from app.utils.logger import logger

# Cap PyTorch CPU threads to prevent multi-threaded thread-local memory spikes in OpenMP
try:
    torch.set_num_threads(min(2, os.cpu_count() or 2))
except Exception:
    pass

VALID_VOICE_IDS = {"am_onyx", "am_michael", "af_bella", "bf_emma"}
DEFAULT_VOICE_ID = "am_onyx"
DEFAULT_TTS_SPEED = 1.15

# Global mutex to serialize CPU PyTorch forward passes and prevent allocator memory corruption / crashes
_KOKORO_LOCK = threading.Lock()

# In-memory LRU cache to eliminate duplicate synthesis overhead
_TTS_CACHE: Dict[Tuple[str, str, float], Tuple[bytes, float]] = {}
_TTS_CACHE_MAX_SIZE = 128


def sanitize_text_for_tts(text: str) -> str:
    """
    Sanitize text before TTS synthesis so Kokoro never speaks markdown characters.
    - Strips markdown headers ('### Header' -> 'Header')
    - Strips bold/italics ('**text**' -> 'text', '*text*' -> 'text')
    - Strips bullet markers ('- item', '* item' -> 'item')
    - Strips stray '#', '*', '`', '~' symbols so TTS never speaks 'hash' or 'asterisk'
    """
    if not text:
        return ""
    cleaned = text.replace("[END_INTERVIEW]", "")
    cleaned = re.sub(r'#+\s*', '', cleaned)
    cleaned = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', cleaned)
    cleaned = re.sub(r'_{1,3}(.*?)_{1,3}', r'\1', cleaned)
    cleaned = re.sub(r'^\s*[-*•]\s+', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'^\s*>\s+', '', cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace('#', '').replace('*', '').replace('`', '').replace('~', '')
    cleaned = re.sub(r'[ \t]+', ' ', cleaned).strip()
    return cleaned


def _synthesize_sentence_sync(pipeline: KPipeline, text: str, voice: str, speed: float = DEFAULT_TTS_SPEED) -> Tuple[np.ndarray, int]:
    """
    Synchronous CPU-bound synthesis function for Kokoro-82M.
    Protected by _KOKORO_LOCK to prevent concurrent PyTorch thread collisions and C++ allocator crashes.
    """
    cleaned = sanitize_text_for_tts(text)
    if not cleaned:
        return np.array([], dtype=np.float32), 24000

    with _KOKORO_LOCK:
        try:
            # Disable gradient computation to reduce CPU memory consumption
            with torch.inference_mode():
                generator = pipeline(cleaned, voice=voice, speed=cast(Any, speed))
                chunks: List[Any] = []
                for _, _, audio in generator:
                    if audio is not None:
                        if isinstance(audio, torch.Tensor):
                            arr = audio.detach().cpu().numpy()
                        elif hasattr(audio, "numpy"):
                            arr = getattr(audio, "numpy")()
                        else:
                            arr = np.asarray(audio, dtype=np.float32)

                        if arr.size > 0:
                            chunks.append(arr)

                if chunks:
                    full_audio = np.concatenate(chunks)
                    return full_audio, 24000
                return np.array([], dtype=np.float32), 24000
        except Exception as exc:
            logger.warning(f"[Kokoro TTS] First attempt failed for '{cleaned[:40]}...': {exc}. Running gc.collect() and retrying...")
            gc.collect()
            try:
                with torch.inference_mode():
                    generator = pipeline(cleaned, voice=voice, speed=cast(Any, speed))
                    chunks = []
                    for _, _, audio in generator:
                        if audio is not None:
                            if isinstance(audio, torch.Tensor):
                                arr = audio.detach().cpu().numpy()
                            elif hasattr(audio, "numpy"):
                                arr = getattr(audio, "numpy")()
                            else:
                                arr = np.asarray(audio, dtype=np.float32)

                            if arr.size > 0:
                                chunks.append(arr)

                    if chunks:
                        return np.concatenate(chunks), 24000
            except Exception as retry_exc:
                logger.error(f"[Kokoro TTS] Retry synthesis failed for '{cleaned[:40]}...': {retry_exc}")
            return np.array([], dtype=np.float32), 24000


HALLUCINATION_PHRASES = {
    "thank you",
    "thank you.",
    "thanks for watching",
    "thanks for watching.",
    "thanks for watching!",
    "bye",
    "bye.",
    "bye!",
    "okay",
    "okay.",
    "yeah",
    "yeah.",
    "you",
    "thank you very much",
    "thank you very much.",
    "thank you so much",
    "thank you so much.",
    "bye bye",
    "bye-bye",
    "goodbye",
    "goodbye.",
}


def is_hallucination(transcript: str, audio_duration: float) -> bool:
    """
    Filters out Whisper noise hallucinations (e.g. 'Thank you', 'Thanks for watching', 'Bye')
    typically generated when receiving sub-1.5s non-speech acoustic energy (laptop fan, sigh, chair squeak).
    """
    if not transcript:
        return False

    cleaned = transcript.strip().lower()
    stripped = cleaned.rstrip(".!?, ")

    if audio_duration < 1.5:
        if cleaned in HALLUCINATION_PHRASES or stripped in HALLUCINATION_PHRASES:
            return True

    return False


COMMON_ABBREVIATIONS = {
    "mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.",
    "e.g.", "i.e.", "etc.", "vs.", "fig.", "inc.", "ltd.", "co.",
    "approx.", "dept.", "est.", "min.", "max.", "no.", "vol."
}


def find_sentence_split(buffer: str, is_first: bool) -> Optional[int]:
    """
    Finds the optimal character boundary to split streamed LLM tokens into TTS chunks.
    - For opening turns (is_first=True): requires >= 10 words or >= 55 chars to guarantee
      Chunk 1 provides 4-6 seconds of continuous playback buffer. Prevents rushed greetings
      and downstream queue underruns.
    - Preserves common abbreviations ('Dr.', 'e.g.', etc.) without premature splits.
    - Subsequent chunks (is_first=False) split at natural sentence boundaries (>= 3 words or >= 18 chars).
    """
    pattern = re.compile(r"([.!?]+(?:\s+|\n+|$))")
    for match in pattern.finditer(buffer):
        candidate = buffer[:match.end()].strip()
        last_word = candidate.split()[-1].lower() if candidate.split() else ""
        if last_word in COMMON_ABBREVIATIONS:
            continue

        words = candidate.split()
        if is_first:
            if len(words) < 10 and len(candidate) < 55:
                continue
            if "\n\n" in match.group(0) and len(words) < 8 and len(candidate) < 45:
                continue
        else:
            if len(words) < 4 and len(candidate) < 22:
                continue

        return match.end()

    # Safety fallback for long sentences without punctuation (> 130 chars)
    if len(buffer) > 130:
        comma_pattern = re.compile(r"([,;:]\s+)")
        for match in comma_pattern.finditer(buffer):
            if match.end() >= 60:
                return match.end()

    return None


def detect_audio_filename(audio_bytes: bytes, default: str = "audio.wav") -> str:
    """Detects audio container format from header magic bytes for Whisper API compatibility."""
    if len(audio_bytes) >= 4:
        if audio_bytes[:4] == b"RIFF":
            return "audio.wav"
        if audio_bytes[:4] == b"\x1a\x45\xdf\xa3":
            return "audio.webm"
        if audio_bytes[:4] == b"OggS":
            return "audio.ogg"
    if len(audio_bytes) >= 12 and b"ftyp" in audio_bytes[:12]:
        return "audio.mp4"
    if len(audio_bytes) >= 3 and (audio_bytes[:3] == b"ID3" or audio_bytes[:2] == b"\xff\xfb"):
        return "audio.mp3"
    return default


def calculate_audio_duration_sec(audio_bytes: bytes) -> float:
    """Calculates duration in seconds of audio bytes (WAV or 16-bit PCM @ 16kHz)."""
    if not audio_bytes:
        return 0.0

    # 1. WAV with RIFF header
    if len(audio_bytes) >= 44 and audio_bytes[:4] == b"RIFF":
        try:
            import wave
            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0:
                    return round(frames / float(rate), 3)
        except Exception:
            pass

    # 2. Soundfile fallback if available
    try:
        info = sf.info(io.BytesIO(audio_bytes))
        return round(float(info.duration), 3)
    except Exception:
        pass

    # 3. Raw 16-bit mono PCM @ 16kHz (2 bytes per sample = 32000 bytes/sec)
    return round(len(audio_bytes) / 32000.0, 3)


class AntigravityInterviewPipeline:
    """
    Real-time AI Sales Interview Simulator Pipeline:
    - STT: Azure MaaS Whisper ('azure/genailab-maas-whisper') via enterprise gateway
    - LLM: Streaming response with sentence boundary chunking (genailab-maas-gpt-4o)
    - TTS: Kokoro-82M KPipeline with asyncio.to_thread CPU offloading (<500ms TTFA)
    """

    def __init__(
        self,
        gateway_base_url: str = "https://genailab.tcs.in",
        api_key: Optional[str] = None,
        whisper_model: str = "azure/genailab-maas-whisper",
        llm_model: Optional[str] = None,
        voice: str = "af_heart",
        lang_code: str = "a",
    ):
        self.gateway_base_url = gateway_base_url
        self.api_key = api_key or os.getenv("TCS_API_KEY", "sk-FHCqt-_flSjGm2TRjj1wXw")
        self.whisper_model = whisper_model
        self.llm_model = llm_model or os.getenv("LLM_MODEL", "genailab-maas-gpt-4o")
        self.voice = voice
        self.lang_code = lang_code

        logger.info(f"Initializing AntigravityInterviewPipeline with gateway: {self.gateway_base_url}")

        # Shared Async HTTP client with verify=False for enterprise gateway SSL
        self.http_client = httpx.AsyncClient(verify=False, timeout=60.0)

        # Global AsyncOpenAI client instance (initialized ONCE at startup)
        self.openai_client = AsyncOpenAI(
            base_url=self.gateway_base_url,
            api_key=self.api_key,
            http_client=cast(Any, self.http_client),
        )

        # Global Kokoro KPipeline instance (initialized ONCE at startup)
        logger.info(f"Loading Kokoro KPipeline (lang_code='{self.lang_code}') into memory...")
        self.kokoro_pipeline = KPipeline(lang_code=self.lang_code)
        try:
            # Shared-model British English pipeline for authentic British voices (bf_emma)
            self.kokoro_pipeline_british = KPipeline(lang_code="b", model=cast(Any, self.kokoro_pipeline.model))
            logger.info("Kokoro British KPipeline loaded successfully with shared neural weights.")
        except Exception as exc:
            logger.warning(f"Could not initialize British Kokoro pipeline: {exc}")
            self.kokoro_pipeline_british = self.kokoro_pipeline
        logger.info("Kokoro KPipeline and AsyncOpenAI successfully loaded globally.")

    async def transcribe_audio(self, audio_bytes: bytes, filename: Optional[str] = None) -> str:
        """
        Transcribe user speech audio using enterprise Azure MaaS Whisper.
        Auto-detects container format (webm, mp4, wav, ogg) to ensure Whisper API compatibility.
        """
        if not audio_bytes or len(audio_bytes) < 400:
            return ""

        effective_filename = filename or detect_audio_filename(audio_bytes)

        # Resolve explicit MIME content-type for enterprise gateway
        content_type = "audio/wav"
        if effective_filename.endswith(".webm"):
            content_type = "audio/webm"
        elif effective_filename.endswith(".mp4") or effective_filename.endswith(".m4a"):
            content_type = "audio/mp4"
        elif effective_filename.endswith(".ogg") or effective_filename.endswith(".oga"):
            content_type = "audio/ogg"
        elif effective_filename.endswith(".mp3"):
            content_type = "audio/mpeg"

        try:
            transcript_response = await self.openai_client.audio.transcriptions.create(
                model=self.whisper_model,
                file=(effective_filename, audio_bytes, content_type),
            )
            if isinstance(transcript_response, str):
                text = transcript_response.strip()
            elif hasattr(transcript_response, "text"):
                text = str(transcript_response.text).strip()
            else:
                text = str(transcript_response).strip()
            logger.info(f"[Whisper STT] Transcribed text: {text}")
            return text
        except Exception as exc:
            logger.error(f"[Whisper STT Error]: {exc}")
            raise

    async def synthesize_sentence_with_metadata(
        self,
        sentence: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> Tuple[bytes, float]:
        """
        Synthesize text into WAV audio bytes using Kokoro TTS in a worker thread.
        Returns tuple of (wav_bytes, duration_sec).
        If voice is provided and is a valid curated voice ID, it overrides self.voice for this call.
        """
        cleaned = sanitize_text_for_tts(sentence)
        if not cleaned:
            return b"", 0.0

        effective_voice = voice if (voice and voice in VALID_VOICE_IDS) else self.voice
        effective_speed = speed if speed is not None else DEFAULT_TTS_SPEED

        # Check in-memory cache to return repeated sentences immediately (0ms latency, zero CPU allocation)
        cache_key = (cleaned, effective_voice, round(effective_speed, 2))
        if cache_key in _TTS_CACHE:
            return _TTS_CACHE[cache_key]

        pipeline_to_use = (
            self.kokoro_pipeline_british
            if (effective_voice.startswith("b") and hasattr(self, "kokoro_pipeline_british"))
            else self.kokoro_pipeline
        )

        # CPU offloading via asyncio.to_thread
        audio_np, sample_rate = await asyncio.to_thread(
            _synthesize_sentence_sync,
            pipeline_to_use,
            cleaned,
            effective_voice,
            effective_speed,
        )

        if len(audio_np) == 0:
            return b"", 0.0

        duration_sec = round(len(audio_np) / float(sample_rate), 3)
        wav_buffer = io.BytesIO()
        sf.write(wav_buffer, audio_np, sample_rate, format="WAV", subtype="PCM_16")
        result = (wav_buffer.getvalue(), duration_sec)

        # LRU eviction
        if len(_TTS_CACHE) >= _TTS_CACHE_MAX_SIZE:
            try:
                _TTS_CACHE.pop(next(iter(_TTS_CACHE)))
            except Exception:
                pass
        _TTS_CACHE[cache_key] = result

        return result

    async def synthesize_sentence_to_wav_bytes(self, sentence: str, voice: Optional[str] = None) -> bytes:
        """
        Synthesize text into WAV audio bytes using Kokoro TTS in a worker thread.
        Thread safety: Kokoro is CPU-bound; running in asyncio.to_thread() prevents event loop blocking.
        """
        wav_bytes, _ = await self.synthesize_sentence_with_metadata(sentence, voice=voice)
        return wav_bytes

    async def stream_agent_audio_pipeline(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        voice: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streams LLM tokens, chunks at sentence boundaries (., ?, !), and yields TTS audio
        chunks immediately as each sentence completes for sub-500ms TTFA.
        """
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if chat_history:
            messages.extend(chat_history)
        messages.append({"role": "user", "content": prompt})

        SENTINEL = object()
        OUTPUT_DONE = object()

        sentence_queue: asyncio.Queue[Any] = asyncio.Queue()
        output_queue: asyncio.Queue[Any] = asyncio.Queue()

        token_buffer = ""
        full_response = ""
        is_first_chunk = True

        async def _stream_llm_producer():
            nonlocal token_buffer, full_response, is_first_chunk
            try:
                stream: Any = await self.openai_client.chat.completions.create(
                    model=self.llm_model,
                    messages=cast(Any, messages),
                    stream=True,
                    temperature=0.7,
                )

                async for chunk in stream:
                    content = chunk.choices[0].delta.content if chunk.choices else ""
                    if not content:
                        continue

                    token_buffer += content
                    full_response += content

                    # Yield text delta immediately so transcript updates in real time
                    await output_queue.put({
                        "type": "text_delta",
                        "delta": content,
                    })

                    # Check if buffer contains a robust, complete sentence
                    split_idx = find_sentence_split(token_buffer, is_first_chunk)
                    while split_idx is not None:
                        sentence = token_buffer[:split_idx].strip()
                        token_buffer = token_buffer[split_idx:]
                        is_first_chunk = False

                        if sentence:
                            await sentence_queue.put((sentence, False))

                        split_idx = find_sentence_split(token_buffer, is_first_chunk)

                # Flush any remaining tokens in buffer
                remaining = token_buffer.strip()
                if remaining:
                    await sentence_queue.put((remaining, True))
            except Exception as exc:
                logger.error(f"[Pipeline Streaming Producer Error]: {exc}")
                await output_queue.put({
                    "type": "error",
                    "error": str(exc),
                })
            finally:
                await sentence_queue.put(SENTINEL)

        async def _tts_consumer():
            try:
                while True:
                    item = await sentence_queue.get()
                    if item is SENTINEL:
                        break

                    sentence, is_final = item
                    if not sentence:
                        continue

                    # Offload CPU-heavy Kokoro synthesis to thread
                    wav_bytes, duration_sec = await self.synthesize_sentence_with_metadata(sentence, voice=voice)
                    audio_b64 = base64.b64encode(wav_bytes).decode("ascii") if wav_bytes else ""

                    await output_queue.put({
                        "type": "audio_chunk",
                        "text": sentence,
                        "audio": audio_b64,
                        "sample_rate": 24000,
                        "format": "wav",
                        "is_final": is_final,
                        "duration_sec": duration_sec,
                    })

                # Once all audio chunks are synthesized and enqueued, send turn_complete
                await output_queue.put({
                    "type": "turn_complete",
                    "full_text": full_response,
                    "is_final": True,
                })
            except Exception as exc:
                logger.error(f"[Pipeline TTS Consumer Error]: {exc}")
                await output_queue.put({
                    "type": "error",
                    "error": str(exc),
                })
            finally:
                await output_queue.put(OUTPUT_DONE)

        producer_task = asyncio.create_task(_stream_llm_producer())
        tts_task = asyncio.create_task(_tts_consumer())

        try:
            while True:
                packet = await output_queue.get()
                if packet is OUTPUT_DONE:
                    break
                yield packet
        finally:
            producer_task.cancel()
            tts_task.cancel()
            await asyncio.gather(producer_task, tts_task, return_exceptions=True)


async def tts_pipeline(text: str, voice: str = DEFAULT_VOICE_ID) -> bytes:
    """
    Top-level convenience: synthesize text to WAV bytes with a specific Kokoro voice.
    Falls back to DEFAULT_VOICE_ID if the requested voice is not in VALID_VOICE_IDS.
    """
    pipeline = get_interview_pipeline()
    safe_voice = voice if voice in VALID_VOICE_IDS else DEFAULT_VOICE_ID
    return await pipeline.synthesize_sentence_to_wav_bytes(text, voice=safe_voice)


# Global pipeline singleton instance (Memory Management constraint: initialized once)
_GLOBAL_PIPELINE: Optional[AntigravityInterviewPipeline] = None


def get_interview_pipeline() -> AntigravityInterviewPipeline:
    """
    Returns the globally initialized pipeline instance.
    """
    global _GLOBAL_PIPELINE
    if _GLOBAL_PIPELINE is None:
        _GLOBAL_PIPELINE = AntigravityInterviewPipeline()
    return _GLOBAL_PIPELINE


def init_interview_pipeline() -> AntigravityInterviewPipeline:
    """
    Explicit startup initializer for FastAPI lifespan.
    """
    global _GLOBAL_PIPELINE
    if _GLOBAL_PIPELINE is None:
        _GLOBAL_PIPELINE = AntigravityInterviewPipeline()
    return _GLOBAL_PIPELINE
