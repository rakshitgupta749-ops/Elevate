import unittest
from unittest.mock import MagicMock, patch
from app.agents.role_agent import RoleAgent
from app.models.schemas import SessionResponse
from app.models.persona import EnterprisePersona
from app.roles.registry import get_persona


class TestOpeningTurn(unittest.TestCase):
    def setUp(self):
        self.session_id = "test_opening_session_123"
        self.agent = RoleAgent(
            role_id="CEO",
            topic="Tech Interview",
            scenario="Enterprise Cloud Platform Pitch",
            experience="Senior",
            style="Professional",
            session_id=self.session_id,
        )

    def test_fallback_opening_ceo(self):
        fallback = self.agent._get_fallback_opening()
        self.assertIn("strategic impact", fallback)
        self.assertNotIn("Visionary and results-oriented executive", fallback)
        self.assertNotIn("What would you like to start with?", fallback)

    def test_fallback_opening_all_roles(self):
        for role_id in ["CEO", "CTO", "HR", "SALES_MANAGER"]:
            agent = RoleAgent(
                role_id=role_id,
                topic="Strategy",
                scenario="Expansion",
                experience="Intermediate",
                style="Professional",
                session_id=f"test_{role_id}",
            )
            fallback = agent._get_fallback_opening()
            self.assertTrue(len(fallback) > 20)
            self.assertNotIn("Visionary and results-oriented executive", fallback)

    def test_generate_opening_with_mock_llm(self):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Thanks for meeting today. Give me the high-level roadmap for this platform."
        mock_llm.invoke.return_value = mock_response
        self.agent.llm = mock_llm

        opening = self.agent.generate_opening()
        self.assertEqual(opening, "Thanks for meeting today. Give me the high-level roadmap for this platform.")
        self.assertEqual(self.agent._opening_message, opening)

    def test_session_response_schema(self):
        resp = SessionResponse(session_id="abc", initial_message="Welcome.")
        self.assertEqual(resp.session_id, "abc")
        self.assertEqual(resp.initial_message, "Welcome.")

        resp_no_msg = SessionResponse(session_id="abc")
        self.assertIsNone(resp_no_msg.initial_message)

    def test_api_session_and_opening_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)

        with patch("app.agents.role_agent.RoleAgent.generate_opening", return_value="Welcome to the executive briefing."):
            res = client.post("/api/session", json={
                "topic": "Leadership",
                "role": "CEO",
                "scenario": "Strategic turnaround",
                "experience": "Senior",
                "style": "Professional"
            })
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIn("session_id", data)
            self.assertEqual(data.get("initial_message"), "Welcome to the executive briefing.")

            session_id = data["session_id"]
            opening_res = client.get(f"/api/session/{session_id}/opening")
            self.assertEqual(opening_res.status_code, 200)
            self.assertEqual(opening_res.json().get("opening_message"), "Welcome to the executive briefing.")


if __name__ == "__main__":
    unittest.main()
