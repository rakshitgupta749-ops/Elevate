"""Simulator Evaluator Service for Elevate.

Orchestrates multi-tier evaluation of simulated stakeholder fidelity:
1. Deterministic state trajectory coherence and oscillation analysis
2. Persona and role boundary consistency
3. Goal persistence and alignment
4. Behavioral trajectory adherence against declarative expectations
5. Information integrity, memory consistency, and confidentiality verification
6. Action-response alignment
7. Aggregation of standardized failure categories
"""

from typing import List, Dict, Optional, Any
import uuid
from datetime import datetime

from app.models.persona import EnterprisePersona
from app.evaluation.evaluation_models import (
    SimulatorArchitectureMode,
    SimulatorFailureCategory,
    ControlledScenario,
    TurnEvaluation,
    SimulatorEvaluation,
)
from app.evaluation.metrics import (
    calculate_state_trajectory_coherence,
    evaluate_persona_consistency,
    evaluate_goal_consistency,
    evaluate_behavior_consistency,
    evaluate_information_and_memory,
    evaluate_action_response_alignment,
    calculate_overall_fidelity,
)


class SimulatorEvaluator:
    """Formal evaluator assessing simulated enterprise stakeholder fidelity."""

    def __init__(self, evaluation_method: str = "deterministic_rules+llm_judge"):
        self.evaluation_method = evaluation_method

    def evaluate_session(
        self,
        session_id: str,
        scenario: ControlledScenario,
        persona: EnterprisePersona,
        architecture_mode: SimulatorArchitectureMode,
        transcript_turns: List[Dict[str, Any]],
        state_trajectory: List[Dict[str, Any]],
        memory_items: Optional[List[Any]] = None,
        world_facts: Optional[List[Any]] = None,
        decisions: Optional[List[Any]] = None,
        performance_metrics: Optional[Dict[str, Any]] = None,
        reproducibility_metadata: Optional[Dict[str, Any]] = None,
    ) -> SimulatorEvaluation:
        """Run formal fidelity evaluation across an executed simulation session."""
        all_failures: List[SimulatorFailureCategory] = []

        # 1. State Coherence
        state_coherence_score, state_failures = calculate_state_trajectory_coherence(
            trajectory=state_trajectory,
            expected_pattern=scenario.expected_state_pattern,
        )
        all_failures.extend(state_failures)

        # 2. Persona Consistency
        persona_score, persona_failures = evaluate_persona_consistency(
            turns=transcript_turns,
            persona_role=persona.profile.role,
            technical_depth=persona.profile.technical_depth,
        )
        all_failures.extend(persona_failures)

        # 3. Goal Consistency
        goal_score, goal_failures = evaluate_goal_consistency(
            turns=transcript_turns,
            persona_goals=persona.goals,
            decisions=decisions,
        )
        all_failures.extend(goal_failures)

        # 4. Behavioral Trajectory Consistency
        behavior_score, behavior_failures = evaluate_behavior_consistency(
            turns=transcript_turns,
            expected_behaviors=scenario.expected_trajectories,
        )
        all_failures.extend(behavior_failures)

        # 5. Information, Confidentiality & Memory Consistency
        confidential_topics = persona.knowledge_boundary.confidential_topics if persona.knowledge_boundary else []
        info_score, boundary_score, mem_score, info_failures = evaluate_information_and_memory(
            turns=transcript_turns,
            world_facts=world_facts,
            confidential_topics=confidential_topics,
            memory_events=memory_items,
        )
        all_failures.extend(info_failures)

        # 6. Turn-by-Turn Action-Response Alignment
        turn_evaluations: List[TurnEvaluation] = []
        alignment_scores: List[float] = []

        for turn_data in transcript_turns:
            turn_num = turn_data.get("turn_number", 1)
            cand_msg = turn_data.get("candidate_input", "")
            stake_resp = turn_data.get("stakeholder_response", "")
            sel_act = turn_data.get("selected_action")
            turn_state = turn_data.get("state_snapshot")
            latency = turn_data.get("latency_ms", 0.0)

            alignment = evaluate_action_response_alignment(
                selected_action=sel_act,
                response_text=stake_resp,
            )
            alignment_scores.append(alignment)

            turn_violations = []
            turn_failures = []
            if alignment < 0.5 and sel_act:
                turn_violations.append(f"Response did not execute action {sel_act}")
                turn_failures.append(SimulatorFailureCategory.POLICY_RESPONSE_MISMATCH)

            turn_eval = TurnEvaluation(
                turn_number=turn_num,
                candidate_input=cand_msg,
                stakeholder_response=stake_resp,
                selected_action=sel_act,
                action_alignment=alignment,
                state_snapshot=turn_state,
                state_coherence_turn=1.0,
                violations=turn_violations,
                failure_categories=turn_failures,
                latency_ms=latency,
            )
            turn_evaluations.append(turn_eval)

        avg_alignment = sum(alignment_scores) / max(1, len(alignment_scores)) if alignment_scores else 1.0

        # 7. Composite Overall Fidelity
        overall_fidelity = calculate_overall_fidelity(
            persona_consistency=persona_score,
            goal_consistency=goal_score,
            behavior_consistency=behavior_score,
            state_coherence=state_coherence_score,
            information_consistency=info_score,
            knowledge_boundary_compliance=boundary_score,
            action_response_alignment=avg_alignment,
            memory_consistency=mem_score,
        )

        # Deduplicate failure categories preserving order
        unique_failures = []
        for f in all_failures:
            if f not in unique_failures:
                unique_failures.append(f)

        return SimulatorEvaluation(
            session_id=session_id,
            scenario_id=scenario.scenario_id,
            persona_id=persona.profile.role,
            architecture_mode=architecture_mode,
            persona_consistency=persona_score,
            goal_consistency=goal_score,
            behavior_consistency=behavior_score,
            state_coherence=state_coherence_score,
            information_consistency=info_score,
            knowledge_boundary_compliance=boundary_score,
            action_response_alignment=round(avg_alignment, 3),
            memory_consistency=mem_score,
            overall_fidelity=overall_fidelity,
            persona_collapse_score=0.0,
            evaluation_method=self.evaluation_method,
            failure_categories=unique_failures,
            turn_evaluations=turn_evaluations,
            state_trajectory=state_trajectory,
            performance_metrics=performance_metrics or {},
            reproducibility_metadata=reproducibility_metadata or {},
            created_at=datetime.utcnow().isoformat(),
        )
