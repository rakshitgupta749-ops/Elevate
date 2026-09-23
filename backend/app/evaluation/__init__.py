"""Elevate Simulator Evaluation Framework (Phase 8)."""

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

__all__ = [
    "SimulatorArchitectureMode",
    "SimulatorFailureCategory",
    "ExpectedBehavior",
    "ControlledScenario",
    "TurnEvaluation",
    "SimulatorEvaluation",
    "HumanEvaluationRecord",
    "calculate_state_trajectory_coherence",
    "evaluate_persona_consistency",
    "evaluate_goal_consistency",
    "evaluate_behavior_consistency",
    "evaluate_information_and_memory",
    "evaluate_action_response_alignment",
    "calculate_persona_divergence",
    "calculate_overall_fidelity",
    "get_scenario",
    "list_scenarios",
    "SCENARIO_A",
    "SCENARIO_B",
    "SCENARIO_C",
    "SCENARIO_D",
    "SCENARIO_E",
    "SCENARIO_F",
    "SimulatorEvaluator",
    "BaselineRunner",
    "EvaluationRunner",
    "generate_evaluation_markdown_report",
    "generate_experiment_markdown_report",
]
