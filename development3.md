# Walkthrough: Track 1 Acoustic & Delivery Telemetry and Unified Sales Scorecard

We implemented **Track 1: Deterministic acoustic & delivery telemetry from raw audio frames and timestamps**, integrated it into the live WebSocket interview loop with **zero latency and complete decoupling**, and built a post-call orchestrator combining Track 1 with **Track 2 strategic transcript evaluation** into a consolidated **`SalesInterviewScorecard`**.

---

## What Changed

### 1. Track 1 Acoustic & Delivery Engine
- **[telemetry.py](file:///home/labuser/Desktop/Project/Elevate/backend/app/services/telemetry.py)** & **[telemetry.py](file:///home/labuser/Desktop/Project/Elevate/backend/app/telemetry.py)**:
  - `SessionTelemetry`: In-memory state tracker monitoring live audio frames and timestamps during the call.
  - `FrameVAD`: Zero-latency RMS/energy-based Voice Activity Detector with 2-frame onset debouncing and 250ms hangover smoothing to exclude dead silence and bridge natural inter-word micro-pauses.
  - **Talk-to-Listen Ratio**: Strictly calculates active speech: `user_active_seconds / (user_active_seconds + ai_active_seconds)`.
    - Verdicts: `"Balanced"` (45%–55% benchmark), `"Pitch Slapping"` (>65%), `"Under-engaging"` (<35%).
  - **Response Latency (Hesitation)**: Tracks delta `user_speech_start - last_ai_playback_end`.
    - Verdicts: `"Crisp"` (0.8s–1.8s benchmark), `"Hesitant"` (>3.0s), `"Abrupt"` (<0.8s).
  - **Pace / Speaking Rate (WPM)**: `(total_user_words / total_user_active_seconds) * 60`.
    - Verdicts: `"Optimal"` (130–160 WPM benchmark), `"Rushing"` (>175 WPM), `"Slow"` (<115 WPM).
  - **Interruptions & Barge-ins**: Triggered when candidate speaks while `ai_state == "PLAYING"`. Natural listening backchannels (e.g., "yeah", "ok", "got it", <=3 words and <=700ms) are filtered out; only aggressive barge-ins (>700ms or >3 words) increment `interruption_count`.

### 2. Audio Pipeline Synthesis Duration Metadata
- **[interview_pipeline.py](file:///home/labuser/Desktop/Project/Elevate/backend/app/services/interview_pipeline.py)**:
  - Added `synthesize_sentence_with_metadata` which computes exact audio duration `duration_sec = len(audio_np) / sample_rate`.
  - Kokoro audio streaming yields `duration_sec` in `audio_chunk` packets so that the WebSocket loop accurately projects AI playback duration in real time.

### 3. Unified Post-Call Evaluation Orchestrator
- **[evaluator.py](file:///home/labuser/Desktop/Project/Elevate/backend/app/evaluation/evaluator.py)** & **[evaluator.py](file:///home/labuser/Desktop/Project/Elevate/backend/app/services/evaluator.py)**:
  - `SalesInterviewEvaluator`:
    - Collects Track 1 `DeliveryScorecard` from `SessionTelemetry`.
    - Computes Track 2 `StrategicScorecard` (discovery score, objection handling score, value proposition score, strengths, critical misses, key coaching quote) via LLM rubric with deterministic fallback.
    - Computes `overall_readiness_score` (scaled 1-100) combining delivery telemetry (40%) and strategic content (60%).
    - Formats output strictly according to the specified schema:
      ```json
      {
        "session_id": "...",
        "timestamp": "...",
        "delivery_scorecard": {
          "talk_listen_ratio": float,
          "talk_ratio_verdict": "Balanced" | "Pitch Slapping" | "Under-engaging",
          "avg_response_latency_sec": float,
          "latency_verdict": "Crisp" | "Hesitant" | "Abrupt",
          "average_wpm": float,
          "pace_verdict": "Optimal" | "Rushing" | "Slow",
          "interruption_count": int
        },
        "strategic_scorecard": {
          "discovery_score": int,
          "objection_handling_score": int,
          "value_proposition_score": int,
          "strengths": [string],
          "critical_misses": [string],
          "key_coaching_quote": string
        },
        "overall_readiness_score": int
      }
      ```

### 4. Storage Persistence
- **[storage_service.py](file:///home/labuser/Desktop/Project/Elevate/backend/app/services/storage_service.py)**:
  - Added `scorecards` SQLite table (`id`, `session_id`, `scorecard_json`, `created_at`).
  - Added `save_scorecard(session_id, scorecard)` and `get_scorecard(session_id)`.

### 5. WebSocket Integration & Scorecard REST Endpoint
- **[endpoints.py](file:///home/labuser/Desktop/Project/Elevate/backend/app/api/endpoints.py)**:
  - `_handle_interview_websocket`:
    - Attaches `SessionTelemetry` collector with zero-latency in-memory tracking.
    - Processes raw audio bytes and base64 audio frames via VAD.
    - Captures `playback_start` and `playback_end` signals from client.
    - Emits AI audio chunks with `duration_sec` and signals `telemetry.on_ai_audio_chunk`.
    - Triggers `_run_post_call_evaluation_background` in a decoupled `asyncio.create_task` upon WebSocket disconnect or session end.
  - Added `GET /api/session/{session_id}/scorecard` endpoint returning `SalesInterviewScorecard`.

---

## Verification & Test Results

### Automated Unit & Integration Tests
Ran test suite in [test_session_telemetry.py](file:///home/labuser/Desktop/Project/Elevate/backend/tests/test_session_telemetry.py):
```bash
/home/labuser/Desktop/Project/Elevate/venv/bin/python -m unittest tests/test_session_telemetry.py
```
**Results**:
- `test_1_talk_to_listen_ratio_benchmarks`: Verified "Balanced" (50%), "Pitch Slapping" (75%), and "Under-engaging" (20%) verdicts.
- `test_2_response_latency_benchmarks`: Verified "Crisp" (1.2s), "Hesitant" (3.8s), and "Abrupt" (0.3s) verdicts.
- `test_3_speaking_rate_wpm_benchmarks`: Verified "Optimal" (145 WPM), "Rushing" (200 WPM), and "Slow" (90 WPM) verdicts.
- `test_4_interruption_vs_backchannel_filtering`: Confirmed short backchannels ("yeah", 300ms) are ignored, while barge-ins (>700ms or >3 words) increment `interruption_count`.
- `test_5_frame_vad_processing`: Confirmed acoustic RMS energy debouncer detects speech and ignores silence.
- `test_6_combined_post_call_evaluator_schema`: Verified full serialization of `SalesInterviewScorecard` matching all required fields and types.
- `test_7_get_scorecard_api_endpoint`: Verified REST endpoint retrieval and persistence in SQLite.
- `test_8_websocket_telemetry_live_lifecycle`: Verified WebSocket connect, telemetry initialization, playback signaling, and disconnect background trigger.

Ran regression suite in [test_coaching_and_lifecycle.py](file:///home/labuser/Desktop/Project/Elevate/backend/tests/test_coaching_and_lifecycle.py):
- 7/7 tests passed with zero regressions.
