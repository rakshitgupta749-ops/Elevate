"""Unit tests for Phase 3: Dynamic Client State for Elevate.

Verifies:
1. ClientState initialization and [0.0, 1.0] range enforcement
2. Role-specific deterministic initialization (CTO, CEO, HR, SALES_MANAGER, etc.)
3. Conversation style modifiers (Stress, Friendly, Executive)
4. State boundary clamping and NaN/Inf protection
5. State transitions for positive evidence, unsupported claims, dodging, vague answers
6. Persona risk-sensitivity amplification
7. State event auditing (before, delta, after, reason, turn)
8. SQLite state_snapshots persistence & query functionality
9. LangGraph multi-turn state survival and evolution in RoleAgent
10. System prompt injection of dynamic perception state
11. Developer state-history inspection API endpoint
"""

import unittest
import os
import sqlite3
from unittest.mock import patch, MagicMock
from pydantic import ValidationError

from app.models.state import ClientState, StateDelta, StateEvent, InteractionSignal, clamp
from app.models.persona import EnterprisePersona
from app.roles.registry import get_persona
from app.services.state_manager import ClientStateManager, detect_interaction_signal
from app.services.storage_service import storage
from app.services.prompt_builder import build_persona_system_prompt
from app.agents.prompts import get_interviewer_system_prompt


class TestClientState(unittest.TestCase):

    def setUp(self):
        self.state_manager = ClientStateManager()

    def test_1_default_state_initialization(self):
        """Test default ClientState values and range validity."""
        state = ClientState()
        self.assertAlmostEqual(state.trust, 0.50)
        self.assertAlmostEqual(state.skepticism, 0.60)
        self.assertAlmostEqual(state.patience, 0.70)
        self.assertAlmostEqual(state.engagement, 0.65)
        self.assertAlmostEqual(state.interest, 0.50)
        self.assertAlmostEqual(state.perceived_risk, 0.50)
        self.assertAlmostEqual(state.frustration, 0.10)
        self.assertAlmostEqual(state.confidence_in_candidate, 0.45)

        # All fields must be within [0.0, 1.0]
        state_dict = state.to_dict()
        for k, v in state_dict.items():
            self.assertTrue(0.0 <= v <= 1.0, f"Field {k} value {v} outside [0, 1]")

    def test_2_role_specific_initialization(self):
        """Test deterministic role-specific baselines for CTO, CEO, and HR."""
        cto_persona = get_persona("CTO")
        cto_state = self.state_manager.initialize_state(cto_persona, style="Professional")
        # CTO starts with high skepticism and high perceived risk
        self.assertGreaterEqual(cto_state.skepticism, 0.70)
        self.assertGreaterEqual(cto_state.perceived_risk, 0.60)
        self.assertLessEqual(cto_state.trust, 0.50)

        hr_persona = get_persona("HR")
        hr_state = self.state_manager.initialize_state(hr_persona, style="Professional")
        # HR starts with higher patience and lower perceived risk
        self.assertGreaterEqual(hr_state.patience, 0.80)
        self.assertLessEqual(hr_state.perceived_risk, 0.45)
        self.assertGreaterEqual(hr_state.trust, 0.55)

        ceo_persona = get_persona("CEO")
        ceo_state = self.state_manager.initialize_state(ceo_persona, style="Professional")
        # CEO starts with high engagement and moderate patience
        self.assertGreaterEqual(ceo_state.engagement, 0.65)
        self.assertLessEqual(ceo_state.patience, 0.65)

    def test_3_style_modifiers(self):
        """Test conversation style influences initial baseline deterministically."""
        cto = get_persona("CTO")
        challenging_state = self.state_manager.initialize_state(cto, style="Stress Interview")
        friendly_state = self.state_manager.initialize_state(cto, style="Friendly")

        self.assertGreater(challenging_state.skepticism, friendly_state.skepticism)
        self.assertLess(challenging_state.patience, friendly_state.patience)
        self.assertGreater(friendly_state.trust, challenging_state.trust)

    def test_4_state_bounds_clamping(self):
        """Test that values are strictly clamped between 0.0 and 1.0."""
        # Manual extreme delta application
        state = ClientState(trust=0.95, skepticism=0.05)
        delta_huge_positive = StateDelta(trust=+0.50, skepticism=-0.50, reason="Massive change")
        new_state, event = self.state_manager.apply_delta(state, delta_huge_positive, turn=1)

        self.assertEqual(new_state.trust, 1.0)
        self.assertEqual(new_state.skepticism, 0.0)

        # Extreme negative delta
        delta_huge_negative = StateDelta(trust=-2.0, skepticism=+2.0, reason="Negative change")
        newer_state, _ = self.state_manager.apply_delta(new_state, delta_huge_negative, turn=2)

        self.assertEqual(newer_state.trust, 0.0)
        self.assertEqual(newer_state.skepticism, 1.0)

        # Check clamp helper with NaN and Inf
        self.assertEqual(clamp(float("nan")), 0.0)
        self.assertEqual(clamp(float("inf")), 1.0)
        self.assertEqual(clamp(float("-inf")), 0.0)

    def test_5_positive_evidence_transition(self):
        """Test positive evidence increases trust and confidence while decreasing skepticism and risk."""
        initial = ClientState(trust=0.45, skepticism=0.70, perceived_risk=0.60, confidence_in_candidate=0.40)
        signal = InteractionSignal(type="positive_evidence", details="Provided benchmarks and SLA proof")
        new_state, event = self.state_manager.apply_signal(initial, signal, turn=1)

        self.assertGreater(new_state.trust, initial.trust)
        self.assertGreater(new_state.confidence_in_candidate, initial.confidence_in_candidate)
        self.assertLess(new_state.skepticism, initial.skepticism)
        self.assertLess(new_state.perceived_risk, initial.perceived_risk)
        self.assertEqual(event.event_type, "positive_evidence")
        self.assertIn("Candidate provided verifiable metrics", event.reason)

    def test_6_unsupported_claim_transition(self):
        """Test unsupported claim increases skepticism and perceived risk while decreasing trust."""
        initial = ClientState(trust=0.55, skepticism=0.55, perceived_risk=0.50, confidence_in_candidate=0.50)
        signal = InteractionSignal(type="unsupported_claim", details="Claimed 100% uptime with zero risk")
        new_state, event = self.state_manager.apply_signal(initial, signal, turn=1)

        self.assertLess(new_state.trust, initial.trust)
        self.assertGreater(new_state.skepticism, initial.skepticism)
        self.assertGreater(new_state.perceived_risk, initial.perceived_risk)
        self.assertLess(new_state.confidence_in_candidate, initial.confidence_in_candidate)
        self.assertEqual(event.event_type, "unsupported_claim")

    def test_7_dodging_question_transition(self):
        """Test candidate dodging decreases trust and patience, while increasing frustration."""
        initial = ClientState(trust=0.50, patience=0.70, frustration=0.10)
        signal = InteractionSignal(type="candidate_dodges_question", details="Candidate said 'let's skip that'")
        new_state, event = self.state_manager.apply_signal(initial, signal, turn=1)

        self.assertLess(new_state.trust, initial.trust)
        self.assertLess(new_state.patience, initial.patience)
        self.assertGreater(new_state.frustration, initial.frustration)

    def test_8_persona_risk_amplification(self):
        """Test Section 18 rule: high risk-sensitivity persona has amplified perceived_risk delta."""
        cto = get_persona("CTO")  # High security priority (0.90) and calculated risk-taker with zero tolerance
        signal = InteractionSignal(type="unsupported_claim")

        state = ClientState(perceived_risk=0.50)
        delta_cto = self.state_manager.calculate_delta(state, signal, persona=cto)
        delta_generic = self.state_manager.calculate_delta(state, signal, persona=None)

        self.assertGreater(delta_cto.perceived_risk, delta_generic.perceived_risk)
        self.assertIn("risk factor", delta_cto.reason)

    def test_9_state_event_auditing(self):
        """Test StateEvent records full audit trail (turn, before, delta, after, reason)."""
        initial = ClientState(trust=0.50, skepticism=0.60)
        signal = InteractionSignal(type="positive_evidence", reason="Custom audited reason")
        new_state, event = self.state_manager.apply_signal(initial, signal, turn=3)

        self.assertEqual(event.turn, 3)
        self.assertEqual(event.event_type, "positive_evidence")
        self.assertEqual(event.reason, "Custom audited reason")
        self.assertAlmostEqual(event.before["trust"], 0.50)
        self.assertAlmostEqual(event.delta["trust"], 0.08)
        self.assertAlmostEqual(event.after["trust"], 0.58)

    def test_10_sqlite_snapshot_persistence(self):
        """Test saving and retrieving state snapshots from SQLite."""
        import uuid
        test_session_id = f"test-session-audit-{uuid.uuid4()}"
        
        # Save session first to satisfy foreign key constraint
        storage.save_session(
            session_id=test_session_id,
            topic="Tech Interview",
            role="CTO",
            scenario="Testing snapshot table",
            experience="Senior",
            style="Professional",
        )

        # Save turn 0 snapshot
        state_0 = ClientState(trust=0.45, skepticism=0.75)
        storage.save_state_snapshot(
            session_id=test_session_id,
            turn_number=0,
            state=state_0,
            event_type="session_initialized",
            event_reason="Initial state",
        )

        # Save turn 1 snapshot
        state_1 = ClientState(trust=0.53, skepticism=0.70)
        storage.save_state_snapshot(
            session_id=test_session_id,
            turn_number=1,
            state=state_1,
            event_type="positive_evidence",
            event_reason="Candidate provided microservice metrics",
        )

        history = storage.get_state_history(test_session_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["turn"], 0)
        self.assertEqual(history[0]["event_type"], "session_initialized")
        self.assertAlmostEqual(history[0]["state"]["trust"], 0.45)

        self.assertEqual(history[1]["turn"], 1)
        self.assertEqual(history[1]["event_type"], "positive_evidence")
        self.assertAlmostEqual(history[1]["state"]["trust"], 0.53)

    def test_11_prompt_builder_reflects_client_state(self):
        """Test that build_persona_system_prompt injects the current client state when provided."""
        cto = get_persona("CTO")
        state = ClientState(trust=0.42, skepticism=0.81, patience=0.55)
        prompt = build_persona_system_prompt(
            persona=cto,
            topic="Tech Interview",
            scenario="Scenario test",
            experience="Intermediate",
            style="Professional",
            client_state=state,
        )

        self.assertIn("CURRENT STAKEHOLDER PERCEPTION (INTERNAL SIMULATION CONTEXT)", prompt)
        self.assertIn("Trust: 0.42", prompt)
        self.assertIn("Skepticism: 0.81", prompt)
        self.assertIn("Patience: 0.55", prompt)
        self.assertIn("DO NOT mention these numeric metrics", prompt)

    @patch("app.agents.role_agent.get_llm")
    def test_12_langgraph_multi_turn_state_evolution(self, mock_get_llm):
        """Test that ClientState evolves across turns in RoleAgent without resetting."""
        import uuid
        from langchain_core.messages import AIMessage
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        # Mock LLM return message
        ai_msg = AIMessage(content="Can you provide specific throughput metrics for your message queue?")
        mock_llm.invoke.return_value = ai_msg
        mock_get_llm.return_value = mock_llm

        from app.agents.role_agent import RoleAgent

        session_id = f"test-agent-state-evolution-{uuid.uuid4()}"
        # Save session to satisfy FK
        storage.save_session(
            session_id=session_id,
            topic="Tech Interview",
            role="CTO",
            scenario="Testing state evolution",
            experience="Expert",
            style="Challenging",
        )

        agent = RoleAgent(
            role_id="CTO",
            topic="Technical Interview",
            scenario="Architecture evaluation",
            experience="Expert",
            style="Challenging",
            session_id=session_id,
        )

        # Turn 0 initial state was saved
        initial_trust = agent.current_state.trust
        self.assertEqual(agent.turn_count, 0)

        # Turn 1: Candidate gives positive evidence response with metrics
        candidate_turn_1 = "We scaled PostgreSQL to 50,000 throughput operations per second with 15 ms latency using Redis caching."
        reply_1 = agent.chat(candidate_turn_1)

        self.assertEqual(agent.turn_count, 1)
        self.assertGreater(agent.current_state.trust, initial_trust)

        # Turn 2: Candidate makes an unverified superlative claim
        turn_1_skepticism = agent.current_state.skepticism
        candidate_turn_2 = "Our solution is 100% flawless and has zero risk."
        reply_2 = agent.chat(candidate_turn_2)

        self.assertEqual(agent.turn_count, 2)
        self.assertGreater(agent.current_state.skepticism, turn_1_skepticism)

        # Check SQLite history
        history = storage.get_state_history(session_id)
        self.assertEqual(len(history), 3)  # Turn 0, Turn 1, Turn 2
        self.assertEqual(history[0]["turn"], 0)
        self.assertEqual(history[1]["turn"], 1)
        self.assertEqual(history[2]["turn"], 2)

    @patch("app.agents.role_agent.get_llm")
    def test_13_api_state_history_endpoint(self, mock_get_llm):
        """Test GET /api/session/{session_id}/state-history endpoint."""
        mock_get_llm.return_value = MagicMock()
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)

        # Create session
        res_create = client.post(
            "/api/session",
            json={
                "topic": "Technical Interview",
                "role": "CTO",
                "scenario": "Architecture testing",
                "experience": "Intermediate",
                "style": "Professional",
            },
        )
        self.assertEqual(res_create.status_code, 200)
        sid = res_create.json()["session_id"]

        # Inspect state history endpoint
        res_hist = client.get(f"/api/session/{sid}/state-history")
        self.assertEqual(res_hist.status_code, 200)
        data = res_hist.json()
        self.assertEqual(data["session_id"], sid)
        self.assertGreaterEqual(data["total_snapshots"], 1)  # Turn 0 present
        self.assertEqual(data["history"][0]["turn"], 0)
        self.assertEqual(data["history"][0]["event_type"], "session_initialized")

    def test_unprofessional_behavior_transition(self):
        """Test unprofessional_behavior signal decreases patience/trust and increases frustration."""
        initial = ClientState(trust=0.60, patience=0.80, frustration=0.10)
        signal = InteractionSignal(
            type="unprofessional_behavior",
            details="Candidate made inappropriate remark",
            reason="Unprofessional behavior detected",
        )
        new_state, event = self.state_manager.apply_signal(initial, signal, turn=2)

        self.assertLess(new_state.trust, initial.trust)
        self.assertLess(new_state.patience, initial.patience)
        self.assertGreater(new_state.frustration, initial.frustration)
        self.assertEqual(event.event_type, "unprofessional_behavior")


if __name__ == "__main__":

    unittest.main()
