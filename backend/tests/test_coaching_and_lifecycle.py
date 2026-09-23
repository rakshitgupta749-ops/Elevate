"""Unit and Integration Tests for Priority P0 and P1:
- Structured Coaching & Feedback Dashboard
- Explicit End & Evaluate
- "Take 2" Turn Rewind
- In-Session Coaching Hints
- Session History and Transcript Retrieval
"""

import unittest
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.api.endpoints import sessions
from app.agents.role_agent import RoleAgent
from app.services.storage_service import storage
from app.models.coaching import (
    StructuredCoachingReport,
    CoachingHintResponse,
    RewindResponse,
    SessionSummaryItem,
    SessionTranscriptResponse,
)
from app.models.state import ClientState
from app.models.stages import InterviewStage, InterviewStatus


class TestCoachingAndLifecycle(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.session_id = f"test-p0p1-{uuid.uuid4()}"

        # Save session to storage
        storage.save_session(
            session_id=self.session_id,
            topic="Cloud Infrastructure",
            role="CTO",
            scenario="Architecture Review",
            experience="Senior",
            style="Professional",
        )

        # Initialize agent
        with patch("app.agents.role_agent.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm
            self.agent = RoleAgent(
                role_id="CTO",
                topic="Cloud Infrastructure",
                scenario="Architecture Review",
                experience="Senior",
                style="Professional",
                session_id=self.session_id,
            )
            sessions[self.session_id] = self.agent

    def test_1_generate_coaching_report_structure(self):
        """Verify generate_coaching_report returns valid structured metrics and markdown."""
        storage.save_interaction(self.session_id, "user", "We are migrating to a multi-cloud architecture.")
        storage.save_interaction(self.session_id, "ai", "How are you handling data synchronization?")

        report = self.agent.generate_coaching_report()
        self.assertIsInstance(report, StructuredCoachingReport)
        self.assertEqual(report.session_id, self.session_id)
        self.assertEqual(report.role, "CTO")
        self.assertTrue(10 <= report.overall_score <= 100)
        self.assertIn(report.letter_grade, ["A+", "A", "B", "C", "D", "F"])
        self.assertTrue(len(report.subscores) >= 5)
        self.assertTrue(len(report.strengths) >= 1)
        self.assertTrue(len(report.weaknesses) >= 1)
        self.assertTrue(len(report.tactical_takeaways) >= 1)
        self.assertIn("# 📊 Elevate Coaching & Performance Report", report.markdown_report)

        # Verify weakness has recommended_alternative ("What you should have said instead")
        first_weakness = report.weaknesses[0]
        self.assertIsNotNone(first_weakness.recommended_alternative)

    def test_2_conclude_session_api_endpoint(self):
        """Test POST /api/session/{session_id}/conclude endpoint."""
        storage.save_interaction(self.session_id, "user", "Our SLA guarantees 99.99% uptime.")
        storage.save_interaction(self.session_id, "ai", "What is your failover strategy?")

        res = self.client.post(f"/api/session/{self.session_id}/conclude")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["session_id"], self.session_id)
        self.assertIn("overall_score", data)
        self.assertIn("outcome_verdict", data)
        self.assertIn("subscores", data)
        self.assertIn("weaknesses", data)

    def test_3_coaching_hint_api_endpoint(self):
        """Test POST /api/session/{session_id}/hint endpoint."""
        res = self.client.post(f"/api/session/{self.session_id}/hint")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["session_id"], self.session_id)
        self.assertIn("hint", data)
        self.assertIn("focus_area", data)
        self.assertIn("current_stakeholder_perception", data)
        self.assertTrue(len(data["hint"]) > 10)

    def test_4_rewind_turn_api_endpoint(self):
        """Test POST /api/session/{session_id}/rewind endpoint ('Take 2')."""
        # Simulate turn 1
        storage.save_interaction(self.session_id, "user", "I will cut corners to save money.")
        storage.save_interaction(self.session_id, "ai", "That sounds like a terrible idea.")
        self.agent.turn_count = 1
        self.agent.interview_state.total_turn_count = 1
        self.agent.current_state.frustration = 0.85
        storage.save_state_snapshot(self.session_id, 1, self.agent.current_state, "unprofessional", "Frustration spiked")

        # Rewind
        res = self.client.post(f"/api/session/{self.session_id}/rewind")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["restored_turn"], 0)
        self.assertEqual(self.agent.turn_count, 0)
        self.assertIn("Turn rewound successfully", data["system_notice"])

    def test_5_list_sessions_api_endpoint(self):
        """Test GET /api/sessions endpoint for history dashboard."""
        res = self.client.get("/api/sessions")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        session_ids = [s["id"] for s in data]
        self.assertIn(self.session_id, session_ids)

    def test_6_get_session_transcript_api_endpoint(self):
        """Test GET /api/session/{session_id}/transcript endpoint."""
        storage.save_interaction(self.session_id, "user", "Hello CTO.")
        storage.save_interaction(self.session_id, "ai", "Hello, let's talk.")

        res = self.client.get(f"/api/session/{self.session_id}/transcript")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["session_id"], self.session_id)
        self.assertEqual(data["role"], "CTO")
        self.assertTrue(len(data["interactions"]) >= 2)

    def test_7_get_session_coaching_report_api_endpoint(self):
        """Test GET /api/session/{session_id}/coaching-report endpoint."""
        # Conclude first
        self.client.post(f"/api/session/{self.session_id}/conclude")

        res = self.client.get(f"/api/session/{self.session_id}/coaching-report")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["session_id"], self.session_id)
        self.assertIn("overall_score", data)
        self.assertIn("markdown_report", data)


if __name__ == "__main__":
    unittest.main()
