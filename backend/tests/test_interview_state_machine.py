"""Unit and Integration Tests for Phase 4: Interview State Machine.

Validates:
- 5 enterprise sales stages and configuration
- InterviewState initialization and serialization
- Deterministic stage progression and guardrails
- Minimum stage turn enforcement
- Required criteria satisfaction checks
- Premature pitch prevention in Problem Discovery
- Maximum stage turn timeout fail-safe
- Complete 5-stage lifecycle progression
- Auditable transition event generation
- SQLite persistence in interview_stage_events table
- PromptBuilder stage context injection
- Independence of ClientState and InterviewState
- LangGraph multi-turn execution and state updates
- Debug inspection API endpoint
- Early termination on dealbreaker / frustration
"""

import unittest
from unittest.mock import patch, MagicMock
import uuid
from langchain_core.messages import AIMessage, HumanMessage

from app.models.stages import (
    InterviewStage,
    InterviewStatus,
    StageCriterion,
    StageConfig,
    StageTransitionEvent,
    InterviewState,
)
from app.models.state import ClientState
from app.models.persona import EnterprisePersona, PersonaProfile, ValueOrientation, StakeholderGoal, Incentive, KnowledgeBoundary
from app.services.interview_state_manager import (
    InterviewStateManager,
    DEFAULT_STAGE_CONFIGS,
)
from app.services.prompt_builder import build_persona_system_prompt
from app.services.storage_service import storage


class TestInterviewStateMachine(unittest.TestCase):

    def setUp(self):
        self.manager = InterviewStateManager()
        self.dummy_persona = EnterprisePersona(
            profile=PersonaProfile(
                role="CTO",
                title="Chief Technology Officer",
                department="Engineering",
                seniority="Executive",
                years_of_experience=20,
                technical_depth="Deep",
                communication_style="Direct",
                personality_characteristics=["Analytical"],
                risk_profile="Conservative",
            ),
            values=[
                ValueOrientation(name="reliability", priority=1, weight=0.9, description="High uptime"),
            ],
            goals=[
                StakeholderGoal(id="g1", description="Maintain reliability", priority=1.0, type="technical", success_condition="99.99%"),
            ],
            incentives=[
                Incentive(id="inc1", category="organizational", description="Zero unplanned outages", importance=0.9),
            ],
            knowledge_boundary=KnowledgeBoundary(
                expert_topics=["Distributed Systems"],
                known_topics=["Cloud Infrastructure"],
                limited_topics=["Sales Ops"],
                unknown_topics=["Fashion"],
                confidential_topics=["Unreleased Q4 roadmap"],
            ),
        )

    def test_01_stage_enum_and_configs(self):
        """Verify all 5 primary enterprise sales stages exist and have valid configs."""
        expected_stages = [
            InterviewStage.STAGE_1_OPENING_RAPPORT,
            InterviewStage.STAGE_2_PROBLEM_DISCOVERY,
            InterviewStage.STAGE_3_SOLUTION_ALIGNMENT,
            InterviewStage.STAGE_4_OBJECTIONS_AND_DEEP_DIVE,
            InterviewStage.STAGE_5_COMMERCIALS_AND_CLOSING,
        ]
        for stage in expected_stages:
            self.assertIn(stage, DEFAULT_STAGE_CONFIGS)
            cfg = DEFAULT_STAGE_CONFIGS[stage]
            self.assertIsInstance(cfg, StageConfig)
            self.assertTrue(len(cfg.name) > 0)
            self.assertTrue(len(cfg.objective) > 0)
            self.assertGreaterEqual(cfg.min_turns, 1)
            self.assertGreater(cfg.max_turns, cfg.min_turns)
            self.assertIsInstance(cfg.criteria, list)

    def test_02_initial_state(self):
        """Verify fresh interview state initializes at STAGE_1 with turn counters at 0."""
        state = self.manager.initialize_state(max_total_turns=15)
        self.assertEqual(state.current_stage, InterviewStage.STAGE_1_OPENING_RAPPORT)
        self.assertEqual(state.stage_turn_count, 0)
        self.assertEqual(state.total_turn_count, 0)
        self.assertEqual(state.status, InterviewStatus.ACTIVE)
        self.assertEqual(len(state.history), 0)
        self.assertGreater(len(state.criteria), 5)
        self.assertFalse(state.criteria["rapport_established"].satisfied)

        # Test to_dict serialization
        d = state.to_dict()
        self.assertEqual(d["current_stage"], "STAGE_1_OPENING_RAPPORT")
        self.assertEqual(d["status"], "ACTIVE")
        self.assertIn("discovery_criteria", d)

    def test_03_stage_minimum_turn_guard(self):
        """Verify stage does NOT advance before minimum turns, even if required criteria are satisfied."""
        state = self.manager.initialize_state()
        # Stage 1 has min_turns = 1. Turn count is 0.
        # Mark required criteria satisfied
        state.criteria["rapport_established"].satisfied = True

        # Turn count is 0 (< min_turns 1)
        event = self.manager.evaluate_stage_transition(state)
        self.assertIsNone(event)
        self.assertEqual(state.current_stage, InterviewStage.STAGE_1_OPENING_RAPPORT)

    def test_04_required_criteria_guard(self):
        """Verify stage does NOT advance when min turns are reached if required criteria are NOT satisfied."""
        state = self.manager.initialize_state()
        # Stage 1: min_turns = 1
        self.manager.record_turn(state)  # stage_turn_count = 1
        self.assertEqual(state.stage_turn_count, 1)

        # Required criterion 'rapport_established' is False
        state.criteria["rapport_established"].satisfied = False
        event = self.manager.evaluate_stage_transition(state)
        self.assertIsNone(event)
        self.assertEqual(state.current_stage, InterviewStage.STAGE_1_OPENING_RAPPORT)

    def test_05_premature_pitch_prevention(self):
        """Verify Stage 2 (Discovery) blocks transition to Solution Alignment if business pain is not identified."""
        state = self.manager.initialize_state()
        state.current_stage = InterviewStage.STAGE_2_PROBLEM_DISCOVERY
        state.stage_turn_count = 4  # Reached min_turns (3) for Stage 2

        # Required criterion 'business_pain_identified' is NOT satisfied
        state.criteria["business_pain_identified"].satisfied = False
        event = self.manager.evaluate_stage_transition(state)
        self.assertIsNone(event)
        self.assertEqual(state.current_stage, InterviewStage.STAGE_2_PROBLEM_DISCOVERY)

        # Now satisfy business pain
        state.criteria["business_pain_identified"].satisfied = True
        event = self.manager.evaluate_stage_transition(state)
        self.assertIsNotNone(event)
        self.assertEqual(event.to_stage, InterviewStage.STAGE_3_SOLUTION_ALIGNMENT)
        self.assertEqual(state.current_stage, InterviewStage.STAGE_3_SOLUTION_ALIGNMENT)
        self.assertEqual(state.stage_turn_count, 0)

    def test_06_stage_maximum_turn_failsafe(self):
        """Verify stage advances automatically when max turn limit is reached as a timeout failsafe."""
        state = self.manager.initialize_state()
        # Stage 1 max_turns = 3
        state.stage_turn_count = 3
        state.total_turn_count = 3
        # Criteria are still unsatisfied
        state.criteria["rapport_established"].satisfied = False

        event = self.manager.evaluate_stage_transition(state)
        self.assertIsNotNone(event)
        self.assertEqual(event.from_stage, InterviewStage.STAGE_1_OPENING_RAPPORT)
        self.assertEqual(event.to_stage, InterviewStage.STAGE_2_PROBLEM_DISCOVERY)
        self.assertIn("Maximum stage turn limit", event.reason)
        self.assertEqual(state.current_stage, InterviewStage.STAGE_2_PROBLEM_DISCOVERY)

    def test_07_full_lifecycle_progression(self):
        """Simulate a complete 5-stage progression from STAGE_1 to COMPLETED."""
        state = self.manager.initialize_state()

        # 1. Opening -> Discovery
        self.manager.record_turn(state)
        self.manager.update_criteria_from_message(state, "Hello, nice to meet you, I'd like to discuss our agenda.", 1)
        self.assertTrue(state.criteria["rapport_established"].satisfied)
        ev1 = self.manager.evaluate_stage_transition(state)
        self.assertIsNotNone(ev1)
        self.assertEqual(state.current_stage, InterviewStage.STAGE_2_PROBLEM_DISCOVERY)

        # 2. Discovery -> Solution Alignment (min 3 turns)
        for t in range(2, 5):
            self.manager.record_turn(state)
        self.manager.update_criteria_from_message(state, "What is your core business pain, bottleneck, and how do you currently operate?", 4)
        self.assertTrue(state.criteria["business_pain_identified"].satisfied)
        ev2 = self.manager.evaluate_stage_transition(state)
        self.assertIsNotNone(ev2)
        self.assertEqual(state.current_stage, InterviewStage.STAGE_3_SOLUTION_ALIGNMENT)

        # 3. Solution Alignment -> Objections (min 2 turns)
        for t in range(5, 7):
            self.manager.record_turn(state)
        self.manager.update_criteria_from_message(state, "Our platform solves this challenge and provides significant ROI.", 6)
        self.assertTrue(state.criteria["solution_linked_to_pain"].satisfied)
        ev3 = self.manager.evaluate_stage_transition(state)
        self.assertIsNotNone(ev3)
        self.assertEqual(state.current_stage, InterviewStage.STAGE_4_OBJECTIONS_AND_DEEP_DIVE)

        # 4. Objections -> Commercials (min 2 turns)
        for t in range(7, 9):
            self.manager.record_turn(state)
        self.manager.update_criteria_from_message(state, "Regarding security risk and downtime, we guarantee 99.99% SLA and SOC2 compliance.", 8)
        self.assertTrue(state.criteria["technical_risk_probed"].satisfied)
        ev4 = self.manager.evaluate_stage_transition(state)
        self.assertIsNotNone(ev4)
        self.assertEqual(state.current_stage, InterviewStage.STAGE_5_COMMERCIALS_AND_CLOSING)

        # 5. Commercials -> COMPLETED (min 2 turns)
        for t in range(9, 11):
            self.manager.record_turn(state)
        self.manager.update_criteria_from_message(state, "Our annual pricing tier is flexible, let's schedule a demo and follow up meeting next week.", 10)
        self.assertTrue(state.criteria["commercial_expectations_clarified"].satisfied)
        self.assertTrue(state.criteria["next_steps_agreed"].satisfied)
        ev5 = self.manager.evaluate_stage_transition(state)
        self.assertIsNotNone(ev5)
        self.assertEqual(state.status, InterviewStatus.COMPLETED)
        self.assertEqual(len(state.history), 5)

    def test_08_stage_transition_events_auditing(self):
        """Verify each transition records an auditable event with from, to, turn, and reason."""
        state = self.manager.initialize_state()
        state.stage_turn_count = 1
        state.total_turn_count = 1
        state.criteria["rapport_established"].satisfied = True

        event = self.manager.evaluate_stage_transition(state)
        self.assertIsInstance(event, StageTransitionEvent)
        self.assertEqual(event.turn, 1)
        self.assertEqual(event.from_stage, InterviewStage.STAGE_1_OPENING_RAPPORT)
        self.assertEqual(event.to_stage, InterviewStage.STAGE_2_PROBLEM_DISCOVERY)
        self.assertIn("Required criteria satisfied", event.reason)
        self.assertTrue(hasattr(event, "timestamp"))

    def test_09_sqlite_persistence(self):
        """Verify stage transitions persist to SQLite interview_stage_events table and can be queried."""
        test_session_id = f"test-stage-persist-{uuid.uuid4()}"
        storage.save_session(
            session_id=test_session_id,
            topic="Sales Interview",
            role="CTO",
            scenario="Testing",
            experience="Senior",
            style="Direct",
        )

        storage.save_interview_stage_event(
            session_id=test_session_id,
            turn_number=0,
            from_stage="STAGE_1_OPENING_RAPPORT",
            to_stage="STAGE_1_OPENING_RAPPORT",
            reason="Session initialized",
        )
        storage.save_interview_stage_event(
            session_id=test_session_id,
            turn_number=2,
            from_stage="STAGE_1_OPENING_RAPPORT",
            to_stage="STAGE_2_PROBLEM_DISCOVERY",
            reason="Rapport established",
        )

        events = storage.get_interview_stage_events(test_session_id)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["turn"], 0)
        self.assertEqual(events[1]["turn"], 2)
        self.assertEqual(events[1]["from_stage"], "STAGE_1_OPENING_RAPPORT")
        self.assertEqual(events[1]["to_stage"], "STAGE_2_PROBLEM_DISCOVERY")

    def test_10_prompt_builder_contains_stage_context(self):
        """Verify prompt builder formats current stage, objective, progress, and behavioral guards."""
        state = self.manager.initialize_state()
        state.current_stage = InterviewStage.STAGE_2_PROBLEM_DISCOVERY
        state.stage_turn_count = 2
        state.total_turn_count = 3

        prompt = build_persona_system_prompt(
            persona=self.dummy_persona,
            topic="Enterprise Sales",
            scenario="Database evaluation",
            experience="Mid",
            style="Professional",
            interview_state=state,
        )

        self.assertIn("CURRENT INTERVIEW STAGE: STAGE_2_PROBLEM_DISCOVERY", prompt)
        self.assertIn("Problem Discovery", prompt)
        self.assertIn("PREMATURE PITCH GUARD", prompt)
        self.assertIn("Turn 2 of min 3 / max 8", prompt)

    def test_11_independent_client_and_interview_states(self):
        """Verify ClientState and InterviewState update independently without data coupling."""
        c_state = ClientState(trust=0.5, skepticism=0.6, frustration=0.1)
        i_state = self.manager.initialize_state()

        # Change ClientState
        c_state.trust = 0.7
        c_state.frustration = 0.05

        # Change InterviewState
        i_state.stage_turn_count = 2
        i_state.current_stage = InterviewStage.STAGE_3_SOLUTION_ALIGNMENT

        self.assertEqual(c_state.trust, 0.7)
        self.assertNotIn("current_stage", c_state.to_dict())
        self.assertEqual(i_state.current_stage, InterviewStage.STAGE_3_SOLUTION_ALIGNMENT)
        self.assertNotIn("trust", i_state.to_dict())

    @patch("app.agents.role_agent.get_llm")
    def test_12_langgraph_multi_turn_interview_state(self, mock_get_llm):
        """Verify RoleAgent updates InterviewState through multi-turn LangGraph execution."""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        def mock_invoke(messages):
            return AIMessage(content="Thank you for the introduction. What specific challenges are you looking to solve?")

        mock_llm.bind_tools.return_value.invoke.side_effect = mock_invoke

        from app.agents.role_agent import RoleAgent

        session_id = f"test-langgraph-stage-{uuid.uuid4()}"
        agent = RoleAgent(
            role_id="CTO",
            topic="Cloud Scaling",
            scenario="Migration",
            experience="Senior",
            style="Direct",
            session_id=session_id,
        )

        # Initial turn
        self.assertEqual(agent.interview_state.current_stage, InterviewStage.STAGE_1_OPENING_RAPPORT)
        self.assertEqual(agent.interview_state.stage_turn_count, 0)

        # Turn 1: Candidate introduces self (satisfies rapport)
        reply = agent.chat("Hi, nice to meet you. I'm here to discuss the migration agenda today.")
        self.assertIn("Thank you for the introduction", reply)
        self.assertEqual(agent.turn_count, 1)
        self.assertEqual(agent.interview_state.total_turn_count, 1)
        # Should have transitioned to STAGE_2_PROBLEM_DISCOVERY
        self.assertEqual(agent.interview_state.current_stage, InterviewStage.STAGE_2_PROBLEM_DISCOVERY)
        self.assertEqual(agent.interview_state.stage_turn_count, 0)

    def test_13_interview_history_api_endpoint(self):
        """Test GET /api/session/{session_id}/interview-history debug endpoint."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.api.endpoints import sessions
        from app.agents.role_agent import RoleAgent

        client = TestClient(app)
        session_id = f"test-api-stage-{uuid.uuid4()}"

        with patch("app.agents.role_agent.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm
            agent = RoleAgent(
                role_id="CTO",
                topic="Cloud Infrastructure",
                scenario="Architecture Review",
                experience="Senior",
                style="Direct",
                session_id=session_id,
            )
            sessions[session_id] = agent

            res = client.get(f"/api/session/{session_id}/interview-history")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["session_id"], session_id)
            self.assertEqual(data["current_stage"], "STAGE_1_OPENING_RAPPORT")
            self.assertEqual(data["status"], "ACTIVE")
            self.assertIn("criteria", data)
            self.assertIn("history", data)

    def test_14_early_termination_dealbreaker(self):
        """Verify client dealbreaker / extreme frustration triggers TERMINATED status."""
        state = self.manager.initialize_state()
        client_state = ClientState(
            trust=0.1,
            skepticism=0.9,
            patience=0.05,
            frustration=0.98,
        )

        event = self.manager.evaluate_stage_transition(state, client_state=client_state)
        self.assertIsNotNone(event)
        self.assertEqual(state.status, InterviewStatus.TERMINATED)
        self.assertIn("reached critical ceiling", state.termination_reason)

    def test_15_max_total_turns_completion(self):
        """Verify reaching max_total_turns forces interview completion."""
        state = self.manager.initialize_state(max_total_turns=10)
        state.total_turn_count = 10
        state.stage_turn_count = 1

        event = self.manager.evaluate_stage_transition(state)
        self.assertIsNotNone(event)
        self.assertEqual(state.status, InterviewStatus.COMPLETED)
        self.assertIn("maximum total turn limit", event.reason)


if __name__ == "__main__":
    unittest.main()
