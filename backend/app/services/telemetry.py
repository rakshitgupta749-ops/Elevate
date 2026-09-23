"""Track 1: Deterministic Acoustic & Delivery Telemetry Engine for Elevate.

Monitors audio frames, VAD events, and timestamps during live WebSocket sessions:
1. Talk-to-Listen Ratio: user_active_seconds / (user_active_seconds + ai_active_seconds)
   - Benchmark: 45%-55% (Balanced). Flags: >65% 'Pitch Slapping', <35% 'Under-engaging'.
2. Response Latency (Hesitation): user_speech_start - last_ai_playback_end
   - Benchmark: 0.8s-1.8s (Crisp). Flags: >3.0s 'Hesitant', <0.8s 'Abrupt'.
3. Pace / Speaking Rate (WPM): (total_user_words / total_user_active_seconds) * 60
   - Benchmark: 130-160 WPM (Optimal). Flags: >175 WPM 'Rushing', <115 WPM 'Slow'.
4. Interruptions & Barge-ins: Candidate speech triggering during ai_state == 'PLAYING'.
   - Backchannel filtering: Only counts if speech persists >700ms or exceeds 3 words.
"""

import io
import time
import math
import logging
from typing import List, Optional, Dict, Any, Literal, Tuple
import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger("elevate.telemetry")

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False


class DeliveryScorecard(BaseModel):
    """Deterministic Delivery Telemetry Metrics and Rubric Verdicts."""
    talk_listen_ratio: float = Field(..., description="Active speech talk-to-listen ratio [0.0 - 1.0]")
    talk_ratio_verdict: Literal["Balanced", "Pitch Slapping", "Under-engaging"] = Field(
        ..., description="Verdict based on 45%-55% rep talk benchmark"
    )
    avg_response_latency_sec: float = Field(..., description="Average response latency in seconds")
    latency_verdict: Literal["Crisp", "Hesitant", "Abrupt"] = Field(
        ..., description="Verdict based on 0.8s-1.8s confidence benchmark"
    )
    average_wpm: float = Field(..., description="Average words per minute based on active speech")
    pace_verdict: Literal["Optimal", "Rushing", "Slow"] = Field(
        ..., description="Verdict based on 130-160 WPM benchmark"
    )
    interruption_count: int = Field(0, description="Count of aggressive interruptions (>700ms or >3 words)")


class FrameVAD:
    """Lightweight zero-latency acoustic energy Voice Activity Detector with hangover debouncing."""

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_ms: int = 20,
        energy_threshold: float = 0.015,
        hangover_ms: int = 250,
        onset_frames: int = 2,
    ):
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.frame_samples = int(sample_rate * (frame_ms / 1000.0))
        self.energy_threshold = energy_threshold
        self.hangover_frames = int(hangover_ms / frame_ms)
        self.onset_frames = onset_frames

        # State tracking
        self.consecutive_speech_frames = 0
        self.silence_frames_after_speech = 0
        self.is_speech_active = False

    def process_samples(self, samples: np.ndarray, sample_rate: Optional[int] = None) -> float:
        """Processes audio samples and returns active speech seconds detected in this chunk."""
        if samples.size == 0:
            return 0.0

        sr = sample_rate or self.sample_rate
        frame_size = int(sr * (self.frame_ms / 1000.0))
        if frame_size <= 0:
            frame_size = 320

        total_speech_seconds = 0.0
        frame_duration = frame_size / sr

        num_frames = len(samples) // frame_size
        for i in range(num_frames):
            frame = samples[i * frame_size : (i + 1) * frame_size]
            rms = float(np.sqrt(np.mean(frame ** 2)))

            if rms > self.energy_threshold:
                self.consecutive_speech_frames += 1
                self.silence_frames_after_speech = 0
                if self.consecutive_speech_frames >= self.onset_frames:
                    self.is_speech_active = True
            else:
                self.consecutive_speech_frames = 0
                if self.is_speech_active:
                    self.silence_frames_after_speech += 1
                    if self.silence_frames_after_speech > self.hangover_frames:
                        self.is_speech_active = False

            if self.is_speech_active:
                total_speech_seconds += frame_duration

        return total_speech_seconds


class SessionTelemetry:
    """Isolated, zero-latency state tracker for Acoustic & Delivery Telemetry during a live call."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.start_timestamp = time.time()
        self.end_timestamp: Optional[float] = None

        # Cumulative acoustic durations
        self.user_active_seconds: float = 0.0
        self.ai_active_seconds: float = 0.0
        self.total_user_words: int = 0

        # State tracking
        self.ai_state: str = "IDLE"  # "IDLE" | "PLAYING"
        self.ai_playback_projected_end: float = 0.0
        self.last_ai_playback_end_timestamp: Optional[float] = None

        # Latency tracking
        self.response_latencies: List[float] = []
        self.current_user_speech_start: Optional[float] = None
        self.current_speech_burst_duration: float = 0.0

        # Interruption tracking
        self.interruption_count: int = 0
        self.active_barge_in: bool = False
        self.barge_in_duration: float = 0.0
        self.barge_in_word_count: int = 0
        self.barge_in_triggered: bool = False
        self.barge_in_flushed: bool = False

        # VAD processor
        self.vad = FrameVAD()

    def _sync_ai_state(self, current_time: Optional[float] = None):
        """Re-evaluates whether AI is still actively playing based on projected audio end time."""
        now = current_time or time.time()
        if self.ai_state == "PLAYING" and now >= self.ai_playback_projected_end:
            self.ai_state = "IDLE"
            self.last_ai_playback_end_timestamp = self.ai_playback_projected_end

    def on_ai_playback_start(self, timestamp: Optional[float] = None):
        """Called when AI begins speech generation/playback."""
        now = timestamp or time.time()
        self.ai_state = "PLAYING"
        self.reset_barge_in_trigger()

    def on_ai_audio_chunk(self, duration_sec: float, timestamp: Optional[float] = None):
        """Signals an AI audio chunk emitted by Kokoro TTS to the WebSocket."""
        now = timestamp or time.time()
        self.ai_active_seconds += max(0.0, duration_sec)

        if self.ai_state == "PLAYING":
            self.ai_playback_projected_end = max(self.ai_playback_projected_end, now) + duration_sec
        else:
            self.ai_state = "PLAYING"
            self.ai_playback_projected_end = now + duration_sec
            self.reset_barge_in_trigger()

        self.last_ai_playback_end_timestamp = self.ai_playback_projected_end

    def on_ai_playback_end(self, timestamp: Optional[float] = None):
        """Explicitly signals that AI playback has ended."""
        now = timestamp or time.time()
        self.ai_state = "IDLE"
        self.last_ai_playback_end_timestamp = now
        self.ai_playback_projected_end = now

    def on_user_speech_start(self, timestamp: Optional[float] = None):
        """Signals candidate speech onset detected by VAD."""
        now = timestamp or time.time()
        self._sync_ai_state(now)

        self.current_user_speech_start = now
        self.current_speech_burst_duration = 0.0

        # Measure response latency if AI recently finished speaking
        if self.last_ai_playback_end_timestamp is not None and self.ai_state == "IDLE":
            delta = now - self.last_ai_playback_end_timestamp
            if delta >= 0.0:
                self.response_latencies.append(round(delta, 3))

        # Check for barge-in / interruption
        if self.ai_state == "PLAYING":
            self.active_barge_in = True
            self.barge_in_duration = 0.0
            self.barge_in_word_count = 0
        else:
            self.active_barge_in = False

    def process_audio_chunk(self, raw_audio: bytes, timestamp: Optional[float] = None) -> float:
        """Processes incoming audio frame bytes via energy/VAD and accumulates active user speech."""
        now = timestamp or time.time()
        self._sync_ai_state(now)

        if not raw_audio:
            return 0.0

        samples, sr = self._decode_audio(raw_audio)
        if samples.size == 0:
            return 0.0

        speech_sec = self.vad.process_samples(samples, sample_rate=sr)
        if speech_sec > 0.0:
            # If candidate was not already marked speaking, trigger onset
            if self.current_user_speech_start is None:
                self.on_user_speech_start(timestamp=now)

            self.user_active_seconds += speech_sec
            self.current_speech_burst_duration += speech_sec

            if self.active_barge_in:
                self.barge_in_duration += speech_sec
                if self.barge_in_duration >= 0.7 and not self.barge_in_triggered:
                    self.barge_in_triggered = True
                    self.interruption_count += 1
                    logger.info(
                        f"[Telemetry Barge-in Detected] session={self.session_id}: "
                        f"duration={self.barge_in_duration:.2f}s >= 0.7s"
                    )

        return speech_sec

    def on_user_speech_transcribed(self, text: str, timestamp: Optional[float] = None, words_in_turn: Optional[int] = None):
        """Called when candidate speech chunk/turn has been transcribed."""
        now = timestamp or time.time()
        self._sync_ai_state(now)

        cleaned = text.strip()
        num_words = words_in_turn if words_in_turn is not None else (len(cleaned.split()) if cleaned else 0)
        self.total_user_words += num_words

        # If user active seconds wasn't captured acoustically (e.g. text mode or empty VAD),
        # estimate speech duration using typical speech pace (140 WPM)
        if self.user_active_seconds == 0.0 and num_words > 0:
            estimated_duration = (num_words / 140.0) * 60.0
            self.user_active_seconds += estimated_duration
            self.current_speech_burst_duration += estimated_duration

        # Interruption verification:
        # Only count if candidate speech exceeds 3 words or persists for >700ms (0.7s)
        if self.active_barge_in:
            self.barge_in_word_count += num_words
            if (self.barge_in_duration >= 0.7 or self.barge_in_word_count > 3) and not self.barge_in_triggered:
                self.barge_in_triggered = True
                self.interruption_count += 1
                logger.info(
                    f"[Telemetry Barge-in Detected] session={self.session_id}: "
                    f"duration={self.barge_in_duration:.2f}s, words={self.barge_in_word_count}"
                )
            elif not self.barge_in_triggered:
                logger.info(
                    f"[Telemetry Backchannel] Ignored natural backchannel: "
                    f"duration={self.barge_in_duration:.2f}s, words={self.barge_in_word_count}"
                )
            self.active_barge_in = False
            self.barge_in_duration = 0.0
            self.barge_in_word_count = 0

        self.current_user_speech_start = None
        self.current_speech_burst_duration = 0.0

    def should_flush_barge_in(self) -> bool:
        """Returns True if an aggressive barge-in just triggered and requires flushing client audio buffer."""
        if self.barge_in_triggered and not self.barge_in_flushed:
            self.barge_in_flushed = True
            self.ai_state = "IDLE"
            now = time.time()
            self.ai_playback_projected_end = now
            self.last_ai_playback_end_timestamp = now
            return True
        return False

    def reset_barge_in_trigger(self):
        """Resets barge-in flags for a new AI speech turn."""
        self.barge_in_triggered = False
        self.barge_in_flushed = False
        self.active_barge_in = False
        self.barge_in_duration = 0.0
        self.barge_in_word_count = 0

    def compute_delivery_scorecard(self) -> DeliveryScorecard:
        """Computes deterministic delivery telemetry scorecard and verdicts against sales benchmarks."""
        # 1. Talk-to-Listen Ratio
        # Calculated strictly on active speech: user / (user + ai)
        total_active = self.user_active_seconds + self.ai_active_seconds
        if total_active > 0.0:
            raw_ratio = self.user_active_seconds / total_active
            ratio = round(max(0.0, min(1.0, raw_ratio)), 4)
        else:
            ratio = 0.50

        # Benchmark: 45%-55% rep talk time
        # Flag >65% as "Pitch Slapping / Over-talking" and <35% as "Under-engaging"
        if ratio > 0.65:
            talk_verdict = "Pitch Slapping"
        elif ratio < 0.35:
            talk_verdict = "Under-engaging"
        else:
            talk_verdict = "Balanced"

        # 2. Response Latency (Hesitation)
        # Measure delta: user_speech_start - last_ai_playback_end
        if self.response_latencies:
            avg_latency = round(float(np.mean(self.response_latencies)), 2)
        else:
            avg_latency = 1.20  # Confident fallback if single-turn / test

        # Benchmark: 0.8s-1.8s (Confident). Flag >3.0s as "High Hesitation / Stalling", <0.8s as "Abrupt"
        if avg_latency > 3.0:
            latency_verdict = "Hesitant"
        elif avg_latency < 0.8:
            latency_verdict = "Abrupt"
        else:
            latency_verdict = "Crisp"

        # 3. Pace / Speaking Rate (WPM)
        # (total_user_words / total_user_active_seconds) * 60
        if self.user_active_seconds > 0.0 and self.total_user_words > 0:
            raw_wpm = (self.total_user_words / self.user_active_seconds) * 60.0
            wpm = round(float(raw_wpm), 1)
        else:
            wpm = 140.0 if self.total_user_words > 0 else 0.0

        # Benchmark: 130-160 WPM. Flag >175 WPM as "Rushing under pressure" and <115 WPM as "Slow/Lethargic"
        if wpm > 175.0:
            pace_verdict = "Rushing"
        elif wpm < 115.0 and self.total_user_words > 0:
            pace_verdict = "Slow"
        else:
            pace_verdict = "Optimal"

        # 4. Interruptions count
        interruptions = int(self.interruption_count)

        return DeliveryScorecard(
            talk_listen_ratio=ratio,
            talk_ratio_verdict=talk_verdict,
            avg_response_latency_sec=avg_latency,
            latency_verdict=latency_verdict,
            average_wpm=wpm,
            pace_verdict=pace_verdict,
            interruption_count=interruptions,
        )

    def _decode_audio(self, raw_bytes: bytes) -> Tuple[np.ndarray, int]:
        """Decodes raw audio bytes (WAV or 16-bit PCM) into float32 array."""
        if HAS_SOUNDFILE and raw_bytes[:4] == b"RIFF":
            try:
                data, sr = sf.read(io.BytesIO(raw_bytes), dtype="float32")
                if data.ndim > 1:
                    data = np.mean(data, axis=1)
                return data, sr
            except Exception as e:
                logger.debug(f"Soundfile WAV decode failed: {e}")

        # Fallback: assume raw 16-bit PCM mono @ 16kHz
        try:
            int16_arr = np.frombuffer(raw_bytes, dtype=np.int16)
            float_arr = int16_arr.astype(np.float32) / 32768.0
            return float_arr, 16000
        except Exception:
            return np.array([], dtype=np.float32), 16000


# In-memory registry for active WebSocket sessions
_ACTIVE_TELEMETRY: Dict[str, SessionTelemetry] = {}


def get_or_create_telemetry(session_id: str) -> SessionTelemetry:
    """Retrieves or creates a SessionTelemetry tracker for an active WebSocket call."""
    if session_id not in _ACTIVE_TELEMETRY:
        _ACTIVE_TELEMETRY[session_id] = SessionTelemetry(session_id=session_id)
    return _ACTIVE_TELEMETRY[session_id]


def get_telemetry(session_id: str) -> Optional[SessionTelemetry]:
    """Retrieves an existing SessionTelemetry instance, or None if not active."""
    return _ACTIVE_TELEMETRY.get(session_id)


def remove_telemetry(session_id: str) -> Optional[SessionTelemetry]:
    """Removes and returns a SessionTelemetry instance upon session completion."""
    return _ACTIVE_TELEMETRY.pop(session_id, None)
