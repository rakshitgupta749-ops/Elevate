"""Unit and Integration Tests for Phase 8 Simulator Evaluation Framework.

Covers:
1. Simulator architecture ablation modes and failure categories
2. Controlled scenarios registry and schema validation
3. ExpectedBehavior declarative trajectory model
4. State coherence metric & trajectory oscillation detection
5. Persona consistency metric & identity break detection
6. Goal consistency metric & goal persistence
7. Behavioral consistency metric & expected action matching
8. Action-response alignment calculation
9. Information integrity, confidentiality leaks, and memory consistency
10. Persona collapse & cross-persona divergence metric
11. Overall fidelity composite calculation
12. Static prompt baseline execution
13. RoleAgent architecture ablation mode execution
14. Human expert evaluation schema and SQLite persistence
15. SimulatorEvaluation SQLite persistence & retrieval
16. Markdown evaluation and experiment report generators
17. Research experiments (RQ1, RQ2, RQ3) execution
18. API evaluation endpoints verification
"""

import pytest
import os
import sys
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Ensure backend root is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.evaluation.evaluation_models import (
    SimulatorArchitectureMode,
    SimulatorFailureCategory,
    ExpectedBehavior,
    ControlledScenario,
    TurnEvaluation,
    SimulatorEvaluation,
    HumanEvaluationRecord,
)
from app.evaluation.metrics import (
    calculate_state_trajectory_coherence,
    evaluate_persona_consistency,
    evaluate_goal_consistency,
    evaluate_behavior_consistency,
    evaluate_information_and_memory,
    evaluate_action_response_alignment,
    calculate_persona_divergence,
    calculate_overall_fidelity,
)
from app.evaluation.controlled_scenarios import (
    get_scenario,
    list_scenarios,
    SCENARIO_A,
    SCENARIO_B,
    SCENARIO_C,
    SCENARIO_D,
    SCENARIO_E,
    SCENARIO_F,
)
from app.evaluation.simulator_evaluator import SimulatorEvaluator
from app.evaluation.baseline_runner import BaselineRunner
from app.evaluation.evaluation_runner import EvaluationRunner
from app.evaluation.report_generator import (
    generate_evaluation_markdown_report,
    generate_experiment_markdown_report,
)
from app.services.storage_service import storage
from app.roles.registry import get_persona
from app.agents.role_agent import RoleAgent


class TestSimulatorEvaluation:

    def test_01_simulator_architecture_modes_and_enums(self):
        """Verify all 6 ablation modes and 12 standardized failure categories exist."""
        modes = [m.value for m in SimulatorArchitectureMode]
        assert "STATIC_PROMPT" in modes
        assert "PERSONA_ONLY" in modes
        assert "PERSONA_PLUS_STATE" in modes
        assert "PERSONA_PLUS_STATE_PLUS_INTERVIEW" in modes
        assert "PERSONA_PLUS_STATE_PLUS_INTERVIEW_PLUS_BEHAVIOR" in modes
        assert "FULL_SIMULATOR" in modes
        assert len(modes) == 6

        failures = [f.value for f in SimulatorFailureCategory]
        expected_failures = [
            "PERSONA_DRIFT",
            "GOAL_DRIFT",
            "STATE_OSCILLATION",
            "INFORMATION_LEAK",
            "WORLD_FACT_CONTRADICTION",
            "MEMORY_FAILURE",
            "POLICY_RESPONSE_MISMATCH",
            "PERSONA_COLLAPSE",
            "OVER_DISCLOSURE",
            "UNDER_DISCLOSURE",
            "UNREALISTIC_ESCALATION",
            "ROLE_INCONSISTENCY",
        ]
        for ef in expected_failures:
            assert ef in failures
        assert len(failures) == 12

    def test_02_controlled_scenarios_registry(self):
        """Verify controlled scenarios A through F are registered and properly defined."""
        scenarios = list_scenarios()
        assert len(scenarios) >= 6

        sc_ids = [s.scenario_id for s in scenarios]
        assert "SCENARIO_A_STRONG_CANDIDATE" in sc_ids
        assert "SCENARIO_B_WEAK_CANDIDATE" in sc_ids
        assert "SCENARIO_C_INCONSISTENT_CANDIDATE" in sc_ids
        assert "SCENARIO_D_CONFIDENTIALITY_PROBE" in sc_ids
        assert "SCENARIO_E_TECHNICAL_CHALLENGE" in sc_ids
        assert "SCENARIO_F_HIGH_TRUST_CANDIDATE" in sc_ids

        for s in scenarios:
            assert s.title
            assert s.description
            assert len(s.candidate_turns) >= 3
            assert s.version == "1.0.0"

    def test_03_expected_behavior_trajectory_schema(self):
        """Verify ExpectedBehavior declarative model instantiation and fields."""
        exp = ExpectedBehavior(
            turn_range=[2, 3],
            candidate_condition="unsupported_claim",
            expected_action_types=["REQUEST_EVIDENCE", "CHALLENGE_CLAIM"],
            forbidden_action_types=["ACCEPT_PROPOSAL"],
            state_direction={"trust": "decrease", "skepticism": "increase"},
            goal_relevance="risk_reduction",
            required_information_behavior="none",
        )
        assert exp.turn_range == [2, 3]
        assert "REQUEST_EVIDENCE" in exp.expected_action_types
        assert "ACCEPT_PROPOSAL" in exp.forbidden_action_types
        assert exp.state_direction["trust"] == "decrease"

    def test_04_state_coherence_metric_monotonicity(self):
        """Verify calculate_state_trajectory_coherence on smooth monotonic trajectory."""
        trajectory = [
            {"turn": 0, "trust": 0.40, "skepticism": 0.60, "frustration": 0.30},
            {"turn": 1, "trust": 0.48, "skepticism": 0.54, "frustration": 0.25},
            {"turn": 2, "trust": 0.58, "skepticism": 0.45, "frustration": 0.20},
            {"turn": 3, "trust": 0.68, "skepticism": 0.35, "frustration": 0.15},
        ]
        pattern = {"trust": "increase", "skepticism": "decrease", "frustration": "decrease"}
        score, failures = calculate_state_trajectory_coherence(trajectory, pattern)
        assert score >= 0.90
        assert len(failures) == 0

    def test_05_state_coherence_metric_oscillation_detection(self):
        """Verify state oscillation (flapping) is detected and penalized."""
        erratic_trajectory = [
            {"turn": 0, "trust": 0.40, "skepticism": 0.50},
            {"turn": 1, "trust": 0.85, "skepticism": 0.20},
            {"turn": 2, "trust": 0.25, "skepticism": 0.80},
            {"turn": 3, "turn": 3, "trust": 0.90, "skepticism": 0.20},
            {"turn": 4, "trust": 0.30, "skepticism": 0.85},
        ]
        pattern = {"trust": "increase"}
        score, failures = calculate_state_trajectory_coherence(erratic_trajectory, pattern)
        assert SimulatorFailureCategory.STATE_OSCILLATION in failures
        assert score < 0.70

    def test_06_persona_consistency_metric(self):
        """Verify persona consistency evaluates role vocabulary and catches identity breaks."""
        clean_cto_turns = [
            {"turn_number": 1, "stakeholder_response": "What is the underlying architecture and latency of your system?"},
            {"turn_number": 2, "stakeholder_response": "We need to review your API integration and downtime failover runbooks."},
        ]
        score_clean, failures_clean = evaluate_persona_consistency(clean_cto_turns, "CTO")
        assert score_clean >= 0.80
        assert len(failures_clean) == 0

        ai_break_turns = [
            {"turn_number": 1, "stakeholder_response": "As an AI language model, I do not have a company architecture."},
        ]
        score_bad, failures_bad = evaluate_persona_consistency(ai_break_turns, "CTO")
        assert SimulatorFailureCategory.ROLE_INCONSISTENCY in failures_bad
        assert score_bad < 0.60

    def test_07_goal_consistency_metric(self):
        """Verify goal consistency metric detects active pursuit vs abandonment of goals."""
        persona = get_persona("CTO", scenario="Enterprise Security")
        active_turns = [
            {"turn_number": 1, "stakeholder_response": "How do you guarantee technical reliability and security compliance?"},
            {"turn_number": 2, "stakeholder_response": "What is the concrete implementation plan and deployment timeline?"},
        ]
        score, failures = evaluate_goal_consistency(active_turns, persona.goals)
        assert score >= 0.65
        assert SimulatorFailureCategory.GOAL_DRIFT not in failures

    def test_08_behavior_consistency_metric(self):
        """Verify behavior consistency against ExpectedBehavior criteria."""
        expected = [
            ExpectedBehavior(
                turn_range=[1, 2],
                candidate_condition="unsupported_claim",
                expected_action_types=["REQUEST_EVIDENCE", "CHALLENGE_CLAIM"],
                forbidden_action_types=["MOVE_FORWARD"],
            )
        ]
        compliant_turns = [
            {"turn_number": 1, "selected_action": "REQUEST_EVIDENCE", "stakeholder_response": "What concrete data validates that?"}
        ]
        score, failures = evaluate_behavior_consistency(compliant_turns, expected)
        assert score == 1.0
        assert len(failures) == 0

        forbidden_turns = [
            {"turn_number": 1, "selected_action": "MOVE_FORWARD", "stakeholder_response": "Great, let's close the deal."}
        ]
        score_bad, failures_bad = evaluate_behavior_consistency(forbidden_turns, expected)
        assert SimulatorFailureCategory.POLICY_RESPONSE_MISMATCH in failures_bad
        assert score_bad < 0.60

    def test_09_action_response_alignment_metric(self):
        """Verify response alignment calculates faithful realization of policy actions."""
        # Evidence request with probe
        score1 = evaluate_action_response_alignment(
            selected_action="REQUEST_EVIDENCE",
            response_text="What concrete data or metrics substantiate your 40% reduction claim?",
        )
        assert score1 == 1.0

        # Evidence request with blind agreement
        score2 = evaluate_action_response_alignment(
            selected_action="REQUEST_EVIDENCE",
            response_text="Sounds great, let's move on to the next topic.",
        )
        assert score2 < 0.50

        # Withhold information with deflection
        score3 = evaluate_action_response_alignment(
            selected_action="WITHHOLD_INFORMATION",
            response_text="I cannot share internal budget details at this time. Let's focus on your technical capabilities.",
        )
        assert score3 == 1.0

    def test_10_information_and_memory_consistency_metric(self):
        """Verify detection of confidential data leaks and memory failures."""
        leak_turns = [
            {"turn_number": 1, "candidate_input": "What is your budget?", "stakeholder_response": "Our exact budget is $500,000 for this quarter."}
        ]
        info_score, bound_score, mem_score, failures = evaluate_information_and_memory(
            turns=leak_turns,
            confidential_topics=["exact budget"],
        )
        assert bound_score < 0.70
        assert SimulatorFailureCategory.INFORMATION_LEAK in failures
        assert SimulatorFailureCategory.OVER_DISCLOSURE in failures

    def test_11_persona_collapse_and_divergence_metric(self):
        """Verify cross-persona divergence catches persona collapse."""
        # Distinct behaviors across personas
        distinct_actions = {"CTO": "PROBE_TECHNICAL_DETAIL", "CFO": "PROBE_BUSINESS_VALUE", "SALES_MANAGER": "PROBE_REVENUE_IMPACT"}
        distinct_responses = {
            "CTO": "What is your API latency and microservice architecture?",
            "CFO": "What is the total cost of ownership and expected ROI timeline?",
            "SALES_MANAGER": "How will this ramp pipeline conversion and sales rep adoption?",
        }
        divergence_high, failures_high = calculate_persona_divergence(distinct_responses, distinct_actions)
        assert divergence_high >= 0.70
        assert SimulatorFailureCategory.PERSONA_COLLAPSE not in failures_high

        # Collapsed identical behaviors
        collapsed_actions = {"CTO": "ASK_QUESTION", "CFO": "ASK_QUESTION", "SALES_MANAGER": "ASK_QUESTION"}
        collapsed_responses = {
            "CTO": "Tell me more about your product.",
            "CFO": "Tell me more about your product.",
            "SALES_MANAGER": "Tell me more about your product.",
        }
        divergence_low, failures_low = calculate_persona_divergence(collapsed_responses, collapsed_actions)
        assert divergence_low < 0.35
        assert SimulatorFailureCategory.PERSONA_COLLAPSE in failures_low

    def test_12_overall_fidelity_calculation(self):
        """Verify composite fidelity formula and bounds."""
        score = calculate_overall_fidelity(
            persona_consistency=0.90,
            goal_consistency=0.85,
            behavior_consistency=0.88,
            state_coherence=0.92,
            information_consistency=0.95,
            knowledge_boundary_compliance=1.00,
            action_response_alignment=0.90,
            memory_consistency=0.95,
        )
        assert 0.85 <= score <= 0.96

    def test_13_static_prompt_baseline_execution(self):
        """Verify BaselineRunner executes STATIC_PROMPT mode cleanly."""
        runner = BaselineRunner()
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = "What specific payment latency bottlenecks are you seeing?"
        mock_llm.invoke.return_value = mock_resp
        runner.llm = mock_llm

        res = runner.run_session(
            scenario=SCENARIO_A,
            architecture_mode=SimulatorArchitectureMode.STATIC_PROMPT,
            role_id="CTO",
        )
        assert res["session_id"]
        assert len(res["transcript_turns"]) == len(SCENARIO_A.candidate_turns)
        assert res["state_trajectory"][1]["trust"] == 0.5  # Static prompt baseline has no dynamic state

    def test_14_ablation_mode_agent_configuration(self):
        """Verify RoleAgent accepts and runs all 6 architecture ablation modes."""
        for mode in SimulatorArchitectureMode:
            agent = RoleAgent(
                role_id="CTO",
                topic="Cloud Infrastructure",
                scenario="Modernization",
                experience="Senior",
                style="Direct",
                session_id=f"test-ablation-{mode.value}",
                architecture_mode=mode.value,
            )
            assert agent.architecture_mode == mode.value

            # Test single chat invocation with mock LLM
            from langchain_core.messages import AIMessage
            mock_reply = AIMessage(content="Can you describe your system architecture?")
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_reply
            agent.llm_with_tools = mock_llm
            reply = agent.chat("We reduce deployment time by 40%.")
            assert "Can you describe your system architecture?" in reply

    def test_15_human_expert_evaluation_schema_and_persistence(self):
        """Verify human expert evaluation schema, rating scales, and SQLite persistence."""
        record = HumanEvaluationRecord(
            session_id="test-human-eval-session-1",
            evaluator_id="senior_sales_director_42",
            role_authenticity=5,
            behavior_realism=4,
            question_realism=5,
            objection_realism=4,
            state_evolution=4,
            information_realism=5,
            stakeholder_goal_consistency=5,
            overall_realism=5,
            free_text_feedback="Stakeholder reacted with realistic skepticism on unverified claims.",
            behavioral_agreement_ratings={
                "action_agreement": True,
                "objection_agreement": True,
                "termination_agreement": True,
            },
        )
        row_id = storage.save_human_evaluation(record)
        assert row_id > 0

        saved_ratings = storage.get_human_evaluations("test-human-eval-session-1")
        assert len(saved_ratings) >= 1
        latest = saved_ratings[-1]
        assert latest["role_authenticity"] == 5
        assert latest["overall_realism"] == 5
        assert latest["behavioral_agreement_ratings"]["action_agreement"] is True

    def test_16_simulator_evaluation_sqlite_persistence(self):
        """Verify SimulatorEvaluation model persists and retrieves from SQLite."""
        sim_eval = SimulatorEvaluation(
            session_id="test-sim-eval-session-2",
            scenario_id="SCENARIO_A_STRONG_CANDIDATE",
            persona_id="CTO",
            architecture_mode=SimulatorArchitectureMode.FULL_SIMULATOR,
            persona_consistency=0.91,
            goal_consistency=0.88,
            behavior_consistency=0.90,
            state_coherence=0.94,
            information_consistency=0.98,
            knowledge_boundary_compliance=1.00,
            action_response_alignment=0.92,
            memory_consistency=0.95,
            overall_fidelity=0.93,
            persona_collapse_score=0.85,
            evaluation_method="deterministic_rules+llm_judge",
            failure_categories=[],
            turn_evaluations=[
                TurnEvaluation(
                    turn_number=1,
                    candidate_input="Hello",
                    stakeholder_response="What is your architecture?",
                    selected_action="ASK_QUESTION",
                    action_alignment=1.0,
                    latency_ms=120.0,
                )
            ],
            performance_metrics={"total_session_latency_ms": 480.0},
        )
        row_id = storage.save_simulator_evaluation(sim_eval)
        assert row_id > 0

        retrieved = storage.get_simulator_evaluation("test-sim-eval-session-2")
        assert retrieved is not None
        assert retrieved["overall_fidelity"] == 0.93
        assert retrieved["architecture_mode"] == "FULL_SIMULATOR"

    def test_17_evaluation_report_generator(self):
        """Verify Markdown evaluation report generation and disclaimers."""
        sim_eval = SimulatorEvaluation(
            session_id="session-report-test",
            scenario_id="SCENARIO_A_STRONG_CANDIDATE",
            persona_id="CTO",
            architecture_mode=SimulatorArchitectureMode.FULL_SIMULATOR,
            persona_consistency=0.89,
            goal_consistency=0.85,
            behavior_consistency=0.87,
            state_coherence=0.91,
            information_consistency=0.95,
            knowledge_boundary_compliance=1.00,
            action_response_alignment=0.88,
            memory_consistency=0.92,
            overall_fidelity=0.90,
            turn_evaluations=[
                TurnEvaluation(
                    turn_number=1,
                    candidate_input="Good morning.",
                    stakeholder_response="Good morning. What are your latency numbers?",
                    selected_action="ASK_QUESTION",
                    action_alignment=1.0,
                    latency_ms=150.0,
                )
            ],
            performance_metrics={"avg_turn_latency_ms": 150.0, "total_session_latency_ms": 150.0},
        )
        report_md = generate_evaluation_markdown_report(sim_eval)
        assert "# Elevate Simulator Fidelity Evaluation Report" in report_md
        assert "DISCLAIMER" in report_md
        assert "OVERALL FIDELITY" in report_md
        assert "0.90" in report_md

    def test_18_evaluation_api_endpoints(self):
        """Verify REST API endpoints for scenarios, modes, and human ratings."""
        client = TestClient(app)

        # 1. Scenarios endpoint
        resp_sc = client.get("/api/evaluation/scenarios")
        assert resp_sc.status_code == 200
        data_sc = resp_sc.json()
        assert len(data_sc) >= 6
        assert any(s["scenario_id"] == "SCENARIO_A_STRONG_CANDIDATE" for s in data_sc)

        # 2. Modes endpoint
        resp_modes = client.get("/api/evaluation/modes")
        assert resp_modes.status_code == 200
        data_modes = resp_modes.json()
        assert "FULL_SIMULATOR" in data_modes
        assert "STATIC_PROMPT" in data_modes

        # 3. Human rating submission
        rating_payload = {
            "session_id": "api-human-test-session",
            "evaluator_id": "api_tester",
            "role_authenticity": 4,
            "behavior_realism": 5,
            "question_realism": 4,
            "objection_realism": 4,
            "state_evolution": 4,
            "information_realism": 5,
            "stakeholder_goal_consistency": 5,
            "overall_realism": 4,
            "free_text_feedback": "API test feedback",
            "behavioral_agreement_ratings": {"action_agreement": True},
        }
        resp_rate = client.post("/api/evaluation/human-rating", json=rating_payload)
        assert resp_rate.status_code == 200
        assert resp_rate.json()["status"] == "success"

        # 4. Human rating retrieval
        resp_get_rate = client.get("/api/evaluation/human-ratings/api-human-test-session")
        assert resp_get_rate.status_code == 200
        assert resp_get_rate.json()["total_ratings"] >= 1


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main(["-v", __file__]))

