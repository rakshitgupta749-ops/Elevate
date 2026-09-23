import asyncio
import base64
import io
import os
import re
from typing import AsyncGenerator, Dict, Any, Optional, Tuple, List
import httpx
import numpy as np
import soundfile as sf
import torch
from openai import AsyncOpenAI
from kokoro import KPipeline

from app.utils.logger import logger


def _synthesize_sentence_sync(pipeline: KPipeline, text: str, voice: str, speed: float = 1.0) -> Tuple[np.ndarray, int]:
    """
    Synchronous CPU-bound synthesis function for Kokoro-82M.
    MUST be executed inside asyncio.to_thread() to avoid blocking the FastAPI async event loop.
    """
    cleaned = text.strip()
    if not cleaned:
        return np.array([], dtype=np.float32), 24000

    try:
        # Kokoro pipeline yields (graphemes, phonemes, audio) where audio is torch.Tensor
        generator = pipeline(cleaned, voice=voice, speed=speed)
        chunks: List[np.ndarray] = []
        for _, _, audio in generator:
            if audio is not None:
                if isinstance(audio, torch.Tensor):
                    arr = audio.detach().cpu().numpy()
                elif hasattr(audio, "numpy"):
                    arr = audio.numpy()
                else:
                    arr = np.asarray(audio, dtype=np.float32)

                if arr.size > 0:
                    chunks.append(arr)

        if chunks:
            full_audio = np.concatenate(chunks)
            return full_audio, 24000
        return np.array([], dtype=np.float32), 24000
    except Exception as exc:
        logger.error(f"[Kokoro TTS] Synthesis failed for text '{cleaned[:40]}...': {exc}")
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
    - LLM: Streaming response with sentence boundary chunking (azure/genailab-maas-gpt-4o)
    - TTS: Kokoro-82M KPipeline with asyncio.to_thread CPU offloading (<500ms TTFA)
    """

    def __init__(
        self,
        gateway_base_url: str = "https://genailab.tcs.in",
        api_key: Optional[str] = None,
        whisper_model: str = "azure/genailab-maas-whisper",
        llm_model: str = "azure/genailab-maas-gpt-4o",
        voice: str = "af_heart",
        lang_code: str = "a",
    ):
        self.gateway_base_url = gateway_base_url
        self.api_key = api_key or os.getenv("TCS_API_KEY", "sk-FHCqt-_flSjGm2TRjj1wXw")
        self.whisper_model = whisper_model
        self.llm_model = llm_model
        self.voice = voice
        self.lang_code = lang_code

        logger.info(f"Initializing AntigravityInterviewPipeline with gateway: {self.gateway_base_url}")

        # Shared Async HTTP client with verify=False for enterprise gateway SSL
        self.http_client = httpx.AsyncClient(verify=False, timeout=60.0)

        # Global AsyncOpenAI client instance (initialized ONCE at startup)
        self.openai_client = AsyncOpenAI(
            base_url=self.gateway_base_url,
            api_key=self.api_key,
            http_client=self.http_client,
        )

        # Global Kokoro KPipeline instance (initialized ONCE at startup)
        logger.info(f"Loading Kokoro KPipeline (lang_code='{self.lang_code}') into memory...")
        self.kokoro_pipeline = KPipeline(lang_code=self.lang_code)
        logger.info("Kokoro KPipeline and AsyncOpenAI successfully loaded globally.")

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.wav") -> str:
        """
        Transcribe user speech audio using enterprise Azure MaaS Whisper.
        """
        if not audio_bytes:
            return ""

        try:
            audio_buffer = io.BytesIO(audio_bytes)
            audio_buffer.name = filename

            transcript_response = await self.openai_client.audio.transcriptions.create(
                model=self.whisper_model,
                file=audio_buffer,
            )
            text = transcript_response.text.strip()
            logger.info(f"[Whisper STT] Transcribed text: {text}")
            return text
        except Exception as exc:
            logger.error(f"[Whisper STT Error]: {exc}")
            raise

    async def synthesize_sentence_with_metadata(self, sentence: str) -> Tuple[bytes, float]:
        """
        Synthesize text into WAV audio bytes using Kokoro TTS in a worker thread.
        Returns tuple of (wav_bytes, duration_sec).
        """
        cleaned = sentence.strip()
        if not cleaned:
            return b"", 0.0

        # CPU offloading via asyncio.to_thread
        audio_np, sample_rate = await asyncio.to_thread(
            _synthesize_sentence_sync,
            self.kokoro_pipeline,
            cleaned,
            self.voice,
        )

        if len(audio_np) == 0:
            return b"", 0.0

        duration_sec = round(len(audio_np) / float(sample_rate), 3)
        wav_buffer = io.BytesIO()
        sf.write(wav_buffer, audio_np, sample_rate, format="WAV", subtype="PCM_16")
        return wav_buffer.getvalue(), duration_sec

    async def synthesize_sentence_to_wav_bytes(self, sentence: str) -> bytes:
        """
        Synthesize text into WAV audio bytes using Kokoro TTS in a worker thread.
        Thread safety: Kokoro is CPU-bound; running in asyncio.to_thread() prevents event loop blocking.
        """
        wav_bytes, _ = await self.synthesize_sentence_with_metadata(sentence)
        return wav_bytes

    async def stream_agent_audio_pipeline(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
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

        # Regex sentence delimiter pattern: punctuation followed by space or newline
        sentence_end_pattern = re.compile(r"([.!?]+(?:\s+|\n+))")

        token_buffer = ""
        full_response = ""

        try:
            stream = await self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                stream=True,
                temperature=0.7,
            )

            async for chunk in stream:
                content = chunk.choices[0].delta.content if chunk.choices else ""
                if not content:
                    continue

                token_buffer += content
                full_response += content

                # Also stream text delta so client UI can render text immediately
                yield {
                    "type": "text_delta",
                    "delta": content,
                }

                # Check if buffer contains completed sentence
                match = sentence_end_pattern.search(token_buffer)
                while match:
                    end_idx = match.end()
                    sentence = token_buffer[:end_idx].strip()
                    token_buffer = token_buffer[end_idx:]

                    if sentence:
                        # Offload CPU-heavy Kokoro synthesis to thread
                        wav_bytes, duration_sec = await self.synthesize_sentence_with_metadata(sentence)
                        audio_b64 = base64.b64encode(wav_bytes).decode("ascii") if wav_bytes else ""

                        yield {
                            "type": "audio_chunk",
                            "text": sentence,
                            "audio": audio_b64,
                            "sample_rate": 24000,
                            "format": "wav",
                            "is_final": False,
                            "duration_sec": duration_sec,
                        }

                    match = sentence_end_pattern.search(token_buffer)

            # Flush any remaining tokens in buffer
            remaining = token_buffer.strip()
            if remaining:
                wav_bytes, duration_sec = await self.synthesize_sentence_with_metadata(remaining)
                audio_b64 = base64.b64encode(wav_bytes).decode("ascii") if wav_bytes else ""
                yield {
                    "type": "audio_chunk",
                    "text": remaining,
                    "audio": audio_b64,
                    "sample_rate": 24000,
                    "format": "wav",
                    "is_final": True,
                    "duration_sec": duration_sec,
                }

            # Final completion signal with complete text
            yield {
                "type": "turn_complete",
                "full_text": full_response,
                "is_final": True,
            }

        except Exception as exc:
            logger.error(f"[Pipeline Streaming Error]: {exc}")
            yield {
                "type": "error",
                "error": str(exc),
            }


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
