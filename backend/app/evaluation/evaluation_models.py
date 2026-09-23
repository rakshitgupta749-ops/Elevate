"""Typed Models and Schemas for Phase 8 Simulator Evaluation Framework.

Defines architecture ablation modes, standardized simulator failure categories,
expected behavioral trajectory schemas, controlled scenario definitions,
turn-by-turn evaluations, comprehensive evaluation results, and human expert rating formats.
"""

from enum import Enum
from typing import List, Dict, Optional, Any, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class SimulatorArchitectureMode(str, Enum):
    """Architecture ablation modes for evaluating stakeholder simulation fidelity."""
    STATIC_PROMPT = "STATIC_PROMPT"
    PERSONA_ONLY = "PERSONA_ONLY"
    PERSONA_PLUS_STATE = "PERSONA_PLUS_STATE"
    PERSONA_PLUS_STATE_PLUS_INTERVIEW = "PERSONA_PLUS_STATE_PLUS_INTERVIEW"
    PERSONA_PLUS_STATE_PLUS_INTERVIEW_PLUS_BEHAVIOR = "PERSONA_PLUS_STATE_PLUS_INTERVIEW_PLUS_BEHAVIOR"
    FULL_SIMULATOR = "FULL_SIMULATOR"


class SimulatorFailureCategory(str, Enum):
    """Standardized failure categories for enterprise stakeholder simulation failures."""
    PERSONA_DRIFT = "PERSONA_DRIFT"
    GOAL_DRIFT = "GOAL_DRIFT"
    STATE_OSCILLATION = "STATE_OSCILLATION"
    INFORMATION_LEAK = "INFORMATION_LEAK"
    WORLD_FACT_CONTRADICTION = "WORLD_FACT_CONTRADICTION"
    MEMORY_FAILURE = "MEMORY_FAILURE"
    POLICY_RESPONSE_MISMATCH = "POLICY_RESPONSE_MISMATCH"
    PERSONA_COLLAPSE = "PERSONA_COLLAPSE"
    OVER_DISCLOSURE = "OVER_DISCLOSURE"
    UNDER_DISCLOSURE = "UNDER_DISCLOSURE"
    UNREALISTIC_ESCALATION = "UNREALISTIC_ESCALATION"
    ROLE_INCONSISTENCY = "ROLE_INCONSISTENCY"


class ExpectedBehavior(BaseModel):
    """Declarative specification of expected behavioral trajectory for a turn range."""
    turn_range: List[int] = Field(..., description="[start_turn, end_turn] 1-indexed inclusive")
    candidate_condition: str = Field(..., description="Condition or stimulus provided by candidate")
    expected_action_types: List[str] = Field(default_factory=list, description="Allowable canonical action types")
    forbidden_action_types: List[str] = Field(default_factory=list, description="Strictly prohibited action types")
    state_direction: Dict[str, str] = Field(
        default_factory=dict,
        description="Expected directional shifts, e.g. {'trust': 'increase', 'skepticism': 'decrease'}"
    )
    goal_relevance: Optional[str] = Field(None, description="Persona goal ID or theme being evaluated")
    required_information_behavior: Optional[str] = Field(
        "none", description="'withhold', 'reveal', or 'none'"
    )


class ControlledScenario(BaseModel):
    """Deterministic, versioned enterprise sales simulation test scenario."""
    scenario_id: str = Field(..., description="Unique scenario identifier, e.g. SCENARIO_A_STRONG_CANDIDATE")
    title: str = Field(..., description="Human-readable title")
    description: str = Field(..., description="Detailed test scenario description")
    target_role: str = Field("CTO", description="Target simulated persona role (CTO, CFO, etc.)")
    candidate_turns: List[str] = Field(..., description="Pre-scripted candidate speech turns")
    expected_trajectories: List[ExpectedBehavior] = Field(
        default_factory=list, description="Behavioral expectations per turn range"
    )
    expected_state_pattern: Dict[str, str] = Field(
        default_factory=dict, description="High-level state pattern, e.g. {'trust': 'overall_increase'}"
    )
    version: str = Field("1.0.0", description="Scenario specification version")


class TurnEvaluation(BaseModel):
    """Evaluation result for a single conversation turn."""
    turn_number: int
    candidate_input: str
    stakeholder_response: str
    selected_action: Optional[str] = None
    action_alignment: float = Field(1.0, ge=0.0, le=1.0)
    state_snapshot: Optional[Dict[str, float]] = None
    state_coherence_turn: float = Field(1.0, ge=0.0, le=1.0)
    violations: List[str] = Field(default_factory=list)
    failure_categories: List[SimulatorFailureCategory] = Field(default_factory=list)
    latency_ms: float = 0.0


class SimulatorEvaluation(BaseModel):
    """Formal research evaluation result measuring stakeholder simulation fidelity.
    
    NOTE: These metrics are internal engineering and research benchmarks designed to measure
    system fidelity, causal coherence, and architectural improvement. They are not
    psychometric standards.
    """
    session_id: str
    scenario_id: str
    persona_id: str
    architecture_mode: SimulatorArchitectureMode
    persona_consistency: float = Field(..., ge=0.0, le=1.0, description="Adherence to persona profile, style, and boundaries")
    goal_consistency: float = Field(..., ge=0.0, le=1.0, description="Persistence in pursuing configured stakeholder goals")
    behavior_consistency: float = Field(..., ge=0.0, le=1.0, description="Plausibility and repeatability of behavioral reactions")
    state_coherence: float = Field(..., ge=0.0, le=1.0, description="Directional consistency and low oscillation in client state")
    information_consistency: float = Field(..., ge=0.0, le=1.0, description="World fact integrity and non-contradiction")
    knowledge_boundary_compliance: float = Field(..., ge=0.0, le=1.0, description="Strict withholding of confidential/forbidden info")
    action_response_alignment: float = Field(..., ge=0.0, le=1.0, description="Execution match between policy action and verbal response")
    memory_consistency: float = Field(..., ge=0.0, le=1.0, description="Recall of past turns and contradiction handling")
    overall_fidelity: float = Field(..., ge=0.0, le=1.0, description="Weighted composite engineering fidelity score")
    persona_collapse_score: float = Field(0.0, ge=0.0, le=1.0, description="Divergence from other personas (1.0 = highly distinct, 0.0 = collapsed)")
    evaluation_method: str = Field("deterministic_rules+llm_judge")
    failure_categories: List[SimulatorFailureCategory] = Field(default_factory=list)
    turn_evaluations: List[TurnEvaluation] = Field(default_factory=list)
    state_trajectory: List[Dict[str, Any]] = Field(default_factory=list)
    performance_metrics: Dict[str, Any] = Field(
        default_factory=dict, description="Latencies, token usage, cost estimates"
    )
    reproducibility_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Model, temperature, random seed, versions"
    )
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HumanEvaluationRecord(BaseModel):
    """Human expert rating record for manual validation by enterprise sales professionals."""
    session_id: str
    evaluator_id: str
    role_authenticity: int = Field(..., ge=1, le=5, description="1-5 rating")
    behavior_realism: int = Field(..., ge=1, le=5, description="1-5 rating")
    question_realism: int = Field(..., ge=1, le=5, description="1-5 rating")
    objection_realism: int = Field(..., ge=1, le=5, description="1-5 rating")
    state_evolution: int = Field(..., ge=1, le=5, description="1-5 rating")
    information_realism: int = Field(..., ge=1, le=5, description="1-5 rating")
    stakeholder_goal_consistency: int = Field(..., ge=1, le=5, description="1-5 rating")
    overall_realism: int = Field(..., ge=1, le=5, description="1-5 rating")
    free_text_feedback: str = ""
    behavioral_agreement_ratings: Dict[str, bool] = Field(
        default_factory=dict,
        description="Agreed with action, question, objection, disclosure, escalation, termination"
    )
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
