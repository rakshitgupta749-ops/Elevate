"""Unit and Integration Tests for Track 1 Telemetry and Unified Scorecard Pipeline.

Verifies:
1. Talk-to-Listen Ratio calculation and benchmark verdicts (Balanced, Pitch Slapping, Under-engaging).
2. Response Latency calculation and hesitation verdicts (Crisp, Hesitant, Abrupt).
3. Speaking Pace (WPM) calculation and pace verdicts (Optimal, Rushing, Slow).
4. Interruption vs Backchannel filtering (>700ms or >3 words).
5. Consolidated SalesInterviewScorecard schema and overall_readiness_score calculation.
6. REST endpoint GET /api/session/{session_id}/scorecard and background execution.
"""

import unittest
import uuid
import time
import io
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.services.telemetry import (
    SessionTelemetry,
    FrameVAD,
    DeliveryScorecard,
    get_or_create_telemetry,
    remove_telemetry,
)
from app.evaluation.evaluator import (
    SalesInterviewEvaluator,
    SalesInterviewScorecard,
    StrategicScorecard,
    calculate_delivery_numerical_score,
    calculate_overall_readiness_score,
)
from app.services.storage_service import storage
from app.services.interview_pipeline import (
    is_hallucination,
    calculate_audio_duration_sec,
    HALLUCINATION_PHRASES,
)


class TestSessionTelemetry(unittest.TestCase):

    def setUp(self):
        self.session_id = f"test-telemetry-{uuid.uuid4()}"
        self.client = TestClient(app)
        storage.save_session(
            session_id=self.session_id,
            topic="Enterprise SaaS Pitch",
            role="CEO",
            scenario="Cold Executive Pitch",
            experience="Senior",
            style="Direct",
        )

    def tearDown(self):
        remove_telemetry(self.session_id)

    def test_1_talk_to_listen_ratio_benchmarks(self):
        """Verify talk-to-listen ratio on active speech and benchmark verdicts."""
        # Case A: Balanced (45% - 55%, e.g., 50%)
        t_balanced = SessionTelemetry(session_id="test-balanced")
        t_balanced.user_active_seconds = 50.0
        t_balanced.ai_active_seconds = 50.0
        card_a = t_balanced.compute_delivery_scorecard()
        self.assertAlmostEqual(card_a.talk_listen_ratio, 0.50, places=2)
        self.assertEqual(card_a.talk_ratio_verdict, "Balanced")

        # Case B: Pitch Slapping / Over-talking (>65%)
        t_over = SessionTelemetry(session_id="test-over")
        t_over.user_active_seconds = 75.0
        t_over.ai_active_seconds = 25.0
        card_b = t_over.compute_delivery_scorecard()
        self.assertGreater(card_b.talk_listen_ratio, 0.65)
        self.assertEqual(card_b.talk_ratio_verdict, "Pitch Slapping")

        # Case C: Under-engaging (<35%)
        t_under = SessionTelemetry(session_id="test-under")
        t_under.user_active_seconds = 20.0
        t_under.ai_active_seconds = 80.0
        card_c = t_under.compute_delivery_scorecard()
        self.assertLess(card_c.talk_listen_ratio, 0.35)
        self.assertEqual(card_c.talk_ratio_verdict, "Under-engaging")

    def test_2_response_latency_benchmarks(self):
        """Verify response latency calculation and hesitation verdicts."""
        # Case A: Crisp (0.8s - 1.8s)
        t_crisp = SessionTelemetry(session_id="test-crisp")
        t_crisp.last_ai_playback_end_timestamp = 100.0
        t_crisp.ai_state = "IDLE"
        t_crisp.on_user_speech_start(timestamp=101.2)  # delta = 1.2s
        card_a = t_crisp.compute_delivery_scorecard()
        self.assertAlmostEqual(card_a.avg_response_latency_sec, 1.2, places=1)
        self.assertEqual(card_a.latency_verdict, "Crisp")

        # Case B: High Hesitation / Stalling (>3.0s)
        t_hesitant = SessionTelemetry(session_id="test-hesitant")
        t_hesitant.last_ai_playback_end_timestamp = 100.0
        t_hesitant.ai_state = "IDLE"
        t_hesitant.on_user_speech_start(timestamp=103.8)  # delta = 3.8s
        card_b = t_hesitant.compute_delivery_scorecard()
        self.assertGreater(card_b.avg_response_latency_sec, 3.0)
        self.assertEqual(card_b.latency_verdict, "Hesitant")

        # Case C: Abrupt (<0.8s)
        t_abrupt = SessionTelemetry(session_id="test-abrupt")
        t_abrupt.last_ai_playback_end_timestamp = 100.0
        t_abrupt.ai_state = "IDLE"
        t_abrupt.on_user_speech_start(timestamp=100.3)  # delta = 0.3s
        card_c = t_abrupt.compute_delivery_scorecard()
        self.assertLess(card_c.avg_response_latency_sec, 0.8)
        self.assertEqual(card_c.latency_verdict, "Abrupt")

    def test_3_speaking_rate_wpm_benchmarks(self):
        """Verify pace / WPM calculation and pace verdicts."""
        # Case A: Optimal (130-160 WPM, e.g. 145 WPM)
        t_opt = SessionTelemetry(session_id="test-opt")
        t_opt.user_active_seconds = 60.0
        t_opt.total_user_words = 145
        card_a = t_opt.compute_delivery_scorecard()
        self.assertAlmostEqual(card_a.average_wpm, 145.0, places=1)
        self.assertEqual(card_a.pace_verdict, "Optimal")

        # Case B: Rushing under pressure (>175 WPM)
        t_rush = SessionTelemetry(session_id="test-rush")
        t_rush.user_active_seconds = 30.0
        t_rush.total_user_words = 100  # 200 WPM
        card_b = t_rush.compute_delivery_scorecard()
        self.assertGreater(card_b.average_wpm, 175.0)
        self.assertEqual(card_b.pace_verdict, "Rushing")

        # Case C: Lethargic / Slow (<115 WPM)
        t_slow = SessionTelemetry(session_id="test-slow")
        t_slow.user_active_seconds = 60.0
        t_slow.total_user_words = 90  # 90 WPM
        card_c = t_slow.compute_delivery_scorecard()
        self.assertLess(card_c.average_wpm, 115.0)
        self.assertEqual(card_c.pace_verdict, "Slow")

    def test_4_interruption_vs_backchannel_filtering(self):
        """Verify natural backchannels ('yeah', 'ok', <700ms) are ignored, while aggressive barge-ins are counted."""
        telemetry = SessionTelemetry(session_id="test-interruption")

        # AI starts speaking for 5 seconds
        telemetry.on_ai_audio_chunk(duration_sec=5.0, timestamp=10.0)
        self.assertEqual(telemetry.ai_state, "PLAYING")

        # Event 1: Candidate says short backchannel: "yeah" (1 word, 300ms)
        telemetry.on_user_speech_start(timestamp=11.0)
        telemetry.barge_in_duration = 0.30
        telemetry.on_user_speech_transcribed(text="yeah", timestamp=11.3)

        # Backchannel should NOT be counted as an aggressive interruption
        self.assertEqual(telemetry.interruption_count, 0)

        # Event 2: Candidate aggressive barge-in: persists for 1.2s (>700ms) with 6 words (>3 words)
        telemetry.on_user_speech_start(timestamp=12.0)
        telemetry.barge_in_duration = 1.20
        telemetry.on_user_speech_transcribed(
            text="Wait let me stop you right there",
            timestamp=13.2,
        )

        # Aggressive barge-in MUST increment interruption_count
        self.assertEqual(telemetry.interruption_count, 1)

        # Event 3: Candidate speaks after AI finished playing
        telemetry._sync_ai_state(current_time=16.0)
        self.assertEqual(telemetry.ai_state, "IDLE")

        telemetry.on_user_speech_start(timestamp=16.5)
        telemetry.on_user_speech_transcribed(text="Here is our technical pricing breakdown.", timestamp=18.0)
        # Should NOT count as interruption since AI was IDLE
        self.assertEqual(telemetry.interruption_count, 1)

    def test_5_frame_vad_processing(self):
        """Verify acoustic FrameVAD processes audio samples and debounces silence."""
        vad = FrameVAD(sample_rate=16000, frame_ms=20, energy_threshold=0.01)

        # Generate 100ms of silence (zeros)
        silence = np.zeros(1600, dtype=np.float32)
        speech_sec = vad.process_samples(silence)
        self.assertEqual(speech_sec, 0.0)

        # Generate 200ms of sine tone (speech-like energy)
        t = np.linspace(0, 0.2, 3200, endpoint=False, dtype=np.float32)
        tone = 0.2 * np.sin(2 * np.pi * 440 * t)
        speech_sec = vad.process_samples(tone)
        self.assertGreater(speech_sec, 0.1)

    def test_6_combined_post_call_evaluator_schema(self):
        """Verify post-call evaluator combines delivery & strategic rubrics into the exact required schema."""
        evaluator = SalesInterviewEvaluator()

        telemetry = SessionTelemetry(session_id=self.session_id)
        telemetry.user_active_seconds = 48.0
        telemetry.ai_active_seconds = 52.0
        telemetry.total_user_words = 120
        telemetry.response_latencies = [1.1, 1.3, 0.9]
        telemetry.interruption_count = 0

        storage.save_interaction(self.session_id, "user", "How does your data governance meet SOC2 standards?")
        storage.save_interaction(self.session_id, "ai", "We enforce strict encryption and annual SOC2 audits.")

        scorecard = evaluator.evaluate_post_call(session_id=self.session_id, telemetry=telemetry)

        # Schema verification
        self.assertIsInstance(scorecard, SalesInterviewScorecard)
        self.assertEqual(scorecard.session_id, self.session_id)
        self.assertIsNotNone(scorecard.timestamp)

        # Delivery Scorecard
        deliv = scorecard.delivery_scorecard
        self.assertAlmostEqual(deliv.talk_listen_ratio, 0.48, places=2)
        self.assertEqual(deliv.talk_ratio_verdict, "Balanced")
        self.assertAlmostEqual(deliv.avg_response_latency_sec, 1.1, places=1)
        self.assertEqual(deliv.latency_verdict, "Crisp")
        self.assertAlmostEqual(deliv.average_wpm, 150.0, places=1)
        self.assertEqual(deliv.pace_verdict, "Optimal")
        self.assertEqual(deliv.interruption_count, 0)

        # Strategic Scorecard
        strat = scorecard.strategic_scorecard
        self.assertTrue(0 <= strat.discovery_score <= 100)
        self.assertTrue(0 <= strat.objection_handling_score <= 100)
        self.assertTrue(0 <= strat.value_proposition_score <= 100)
        self.assertTrue(len(strat.strengths) >= 1)
        self.assertTrue(len(strat.critical_misses) >= 1)
        self.assertTrue(len(strat.key_coaching_quote) > 0)

        # Overall Readiness Score
        self.assertTrue(1 <= scorecard.overall_readiness_score <= 100)

        # Verify exact JSON dictionary serialization
        data = scorecard.model_dump()
        self.assertIn("session_id", data)
        self.assertIn("timestamp", data)
        self.assertIn("delivery_scorecard", data)
        self.assertIn("strategic_scorecard", data)
        self.assertIn("overall_readiness_score", data)

    def test_7_get_scorecard_api_endpoint(self):
        """Test GET /api/session/{session_id}/scorecard REST endpoint."""
        # Create active telemetry for the session
        telemetry = get_or_create_telemetry(self.session_id)
        telemetry.user_active_seconds = 50.0
        telemetry.ai_active_seconds = 50.0
        telemetry.total_user_words = 130
        telemetry.response_latencies = [1.2]

        storage.save_interaction(self.session_id, "user", "We accelerate cloud deployments by 40%.")
        storage.save_interaction(self.session_id, "ai", "Tell me more about your migration methodology.")

        res = self.client.get(f"/api/session/{self.session_id}/scorecard")
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertEqual(data["session_id"], self.session_id)
        self.assertIn("delivery_scorecard", data)
        self.assertIn("strategic_scorecard", data)
        self.assertIn("overall_readiness_score", data)

        self.assertEqual(data["delivery_scorecard"]["talk_ratio_verdict"], "Balanced")
        self.assertEqual(data["delivery_scorecard"]["latency_verdict"], "Crisp")
        self.assertEqual(data["delivery_scorecard"]["pace_verdict"], "Optimal")
        self.assertTrue(1 <= data["overall_readiness_score"] <= 100)

        # Verify subsequent retrieval returns from storage
        res2 = self.client.get(f"/api/session/{self.session_id}/scorecard")
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["session_id"], self.session_id)

    def test_8_websocket_telemetry_live_lifecycle(self):
        """Test WebSocket session telemetry tracking and disconnect lifecycle."""
        ws_session_id = f"test-ws-{uuid.uuid4()}"
        storage.save_session(
            session_id=ws_session_id,
            topic="Enterprise Sales",
            role="CEO",
            scenario="Introductory Pitch",
            experience="Senior",
            style="Direct",
        )

        with self.client.websocket_connect(f"/api/ws/interview/{ws_session_id}") as ws:
            ws.send_json({"type": "ping"})
            resp = ws.receive_json()
            self.assertEqual(resp.get("type"), "pong")

            # Send a playback start signal
            ws.send_json({"type": "playback_start"})

            # Send playback end signal
            ws.send_json({"type": "playback_end"})

        # Check telemetry was created and registered
        telemetry = get_or_create_telemetry(ws_session_id)
        self.assertEqual(telemetry.session_id, ws_session_id)

    def test_9_websocket_barge_in_flush_control_frame(self):
        """Test WebSocket barge-in detection triggers 'barge_in_flush' control frame and cancels AI playback."""
        ws_session_id = f"test-barge-ws-{uuid.uuid4()}"
        storage.save_session(
            session_id=ws_session_id,
            topic="Enterprise Sales",
            role="CEO",
            scenario="Introductory Pitch",
            experience="Senior",
            style="Direct",
        )

        with self.client.websocket_connect(f"/api/ws/interview/{ws_session_id}") as ws:
            # 1. Simulate AI starting audio playback
            ws.send_json({"type": "playback_start"})
            time.sleep(0.05)

            telemetry = get_or_create_telemetry(ws_session_id)
            self.assertEqual(telemetry.ai_state, "PLAYING")
            self.assertEqual(telemetry.interruption_count, 0)

            # 2. Send barge-in trigger control message
            ws.send_json({"type": "barge_in"})

            # 3. Assert server returns barge_in_flush frame
            flush_frame = ws.receive_json()
            self.assertEqual(flush_frame.get("type"), "barge_in_flush")
            self.assertEqual(flush_frame.get("interruption_count"), 1)
            self.assertIn("timestamp", flush_frame)

            # 4. Telemetry should now have reset AI state to IDLE
            self.assertEqual(telemetry.ai_state, "IDLE")
            self.assertEqual(telemetry.interruption_count, 1)

    def test_10_whisper_hallucination_filter(self):
        """Test Whisper hallucination filter drops phantom phrases on sub-1.5s non-speech acoustic energy."""
        # 1. Hallucination phrases under 1.5s must be filtered out
        self.assertTrue(is_hallucination("Thank you.", audio_duration=1.2))
        self.assertTrue(is_hallucination("thank you", audio_duration=0.5))
        self.assertTrue(is_hallucination("Thanks for watching.", audio_duration=1.4))
        self.assertTrue(is_hallucination("thanks for watching!", audio_duration=0.8))
        self.assertTrue(is_hallucination("Bye.", audio_duration=0.6))
        self.assertTrue(is_hallucination("bye", audio_duration=0.3))
        self.assertTrue(is_hallucination("okay", audio_duration=0.9))
        self.assertTrue(is_hallucination("yeah.", audio_duration=0.4))
        self.assertTrue(is_hallucination("Thank you so much", audio_duration=1.1))

        # 2. Legitimate pitch content or duration >= 1.5s must NOT be filtered
        self.assertFalse(is_hallucination("Thank you.", audio_duration=2.0))
        self.assertFalse(is_hallucination("Thank you for your time today.", audio_duration=2.8))
        self.assertFalse(is_hallucination("Yes, exactly.", audio_duration=0.8))
        self.assertFalse(is_hallucination("We deliver 40% cost reduction.", audio_duration=1.2))
        self.assertFalse(is_hallucination("", audio_duration=0.5))

        # 3. Audio duration calculation
        # 32,000 bytes @ 16kHz 16-bit mono = 1.0s
        pcm_1s = b"\x00" * 32000
        self.assertAlmostEqual(calculate_audio_duration_sec(pcm_1s), 1.0, places=2)

        # 16,000 bytes = 0.5s
        pcm_half_s = b"\x00" * 16000
        self.assertAlmostEqual(calculate_audio_duration_sec(pcm_half_s), 0.5, places=2)

        # 4. Empty bytes
        self.assertEqual(calculate_audio_duration_sec(b""), 0.0)

    def test_11_websocket_whisper_hallucination_dropped(self):
        """Test WebSocket handler drops Whisper hallucination and does not emit transcript or reply."""
        from unittest.mock import AsyncMock, patch
        from app.services.interview_pipeline import get_interview_pipeline

        ws_session_id = f"test-halluc-ws-{uuid.uuid4()}"
        storage.save_session(
            session_id=ws_session_id,
            topic="Enterprise Sales",
            role="CEO",
            scenario="Introductory Pitch",
            experience="Senior",
            style="Direct",
        )

        pipeline = get_interview_pipeline()
        with patch.object(pipeline, "transcribe_audio", new_callable=AsyncMock) as mock_stt:
            # Whisper returns a hallucinated phantom phrase
            mock_stt.return_value = "Thank you."

            with self.client.websocket_connect(f"/api/ws/interview/{ws_session_id}") as ws:
                # Send 0.5s of audio bytes (16,000 bytes = 0.5s @ 16kHz 16-bit mono)
                dummy_audio = b"\x00" * 16000
                ws.send_bytes(dummy_audio)

                # Send a ping immediately afterwards
                ws.send_json({"type": "ping"})

                # The first response MUST be "pong" because the hallucinated transcript was dropped!
                resp = ws.receive_json()
                self.assertEqual(resp.get("type"), "pong")

    def test_12_sqlite_wal_mode_and_concurrency(self):
        """Verify SQLite database enables Write-Ahead Logging (WAL) and handles concurrent writes."""
        import concurrent.futures

        # 1. Verify PRAGMAs on live storage connection
        with storage._get_connection() as conn:
            cursor = conn.cursor()
            journal_mode = cursor.execute("PRAGMA journal_mode;").fetchone()[0]
            self.assertEqual(journal_mode.lower(), "wal")

            sync_mode = cursor.execute("PRAGMA synchronous;").fetchone()[0]
            # synchronous=NORMAL is represented as 1 in sqlite pragma output
            self.assertIn(str(sync_mode).lower(), ("1", "normal"))

        # 2. Verify concurrent background writes don't collide or throw database locked error
        def worker_write(idx: int):
            sid = f"test-concurrent-{uuid.uuid4()}"
            storage.save_session(sid, "Concurrent Pitch", "CTO", "Load Test", "Senior", "Direct")
            storage.save_interaction(sid, "user", f"Concurrent statement {idx}")
            storage.save_scorecard(sid, {"session_id": sid, "readiness": 85})
            return True

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker_write, i) for i in range(10)]
            results = [f.result() for f in futures]
            self.assertTrue(all(results))


if __name__ == "__main__":
    unittest.main()




