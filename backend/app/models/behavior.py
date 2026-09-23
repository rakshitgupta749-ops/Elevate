"""Behavioral Action and Decision Models (Phase 6).

Defines strongly typed representations for stakeholder behavioral actions:
- Action vocabulary (26 canonical actions)
- BehavioralAction with target, intensity, objective, trigger, reason, disclosure bounds
- PolicyTrace for auditable decision logging
- BehavioralDecision with primary action, optional secondary action, and prompt formatting
"""

from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, field_validator


class ActionType(str, Enum):
    """Canonical behavioral actions available to the simulated stakeholder."""
    # Inquiries & Follow-ups
    ASK_QUESTION = "ASK_QUESTION"
    FOLLOW_UP = "FOLLOW_UP"
    REQUEST_CLARIFICATION = "REQUEST_CLARIFICATION"
    SUMMARIZE = "SUMMARIZE"

    # Challenges & Probes
    CHALLENGE_CLAIM = "CHALLENGE_CLAIM"
    REQUEST_EVIDENCE = "REQUEST_EVIDENCE"
    PROBE_RISK = "PROBE_RISK"
    PROBE_TECHNICAL_DETAIL = "PROBE_TECHNICAL_DETAIL"
    PROBE_TECHNICAL_FEASIBILITY = "PROBE_TECHNICAL_FEASIBILITY"
    PROBE_BUSINESS_VALUE = "PROBE_BUSINESS_VALUE"
    PROBE_IMPLEMENTATION = "PROBE_IMPLEMENTATION"
    PROBE_SECURITY = "PROBE_SECURITY"
    PROBE_SCALABILITY = "PROBE_SCALABILITY"
    CHALLENGE_PRICING = "CHALLENGE_PRICING"

    # Reactions & Dispositions
    EXPRESS_INTEREST = "EXPRESS_INTEREST"
    EXPRESS_CONCERN = "EXPRESS_CONCERN"
    EXPRESS_SKEPTICISM = "EXPRESS_SKEPTICISM"
    ACKNOWLEDGE_POINT = "ACKNOWLEDGE_POINT"
    CONCEDE_POINT = "CONCEDE_POINT"
    PUSH_BACK = "PUSH_BACK"
    REDIRECT = "REDIRECT"
    INTERRUPT = "INTERRUPT"

    # Information Disclosure
    WITHHOLD_INFORMATION = "WITHHOLD_INFORMATION"
    REVEAL_INFORMATION = "REVEAL_INFORMATION"

    # Conversation Flow & Stage Progression
    MOVE_FORWARD = "MOVE_FORWARD"
    CLOSE = "CLOSE"
    TERMINATE = "TERMINATE"


class BehavioralAction(BaseModel):
    """Structured stakeholder behavioral action decided by the Policy Engine."""
    action_type: ActionType = Field(..., description="Canonical action type")
    target: str = Field(default="", description="Specific target topic, claim, metric, or boundary")
    intensity: float = Field(default=0.50, description="Reaction intensity [0.0, 1.0]")
    objective: str = Field(default="", description="High-level conversational objective")
    trigger: str = Field(default="", description="Direct trigger signal or condition")
    reason: str = Field(default="", description="Human-readable explanation of why this action was selected")
    required_information: List[str] = Field(default_factory=list, description="Information demanded from candidate")
    information_to_reveal: List[str] = Field(default_factory=list, description="Information explicitly cleared to reveal")
    information_to_withhold: List[str] = Field(default_factory=list, description="Confidential or guarded information to withhold")
    expected_effect: str = Field(default="", description="Intended conversational outcome")

    def __init__(self, **data):
        if "target_topic" in data and "target" not in data:
            data["target"] = data["target_topic"]
        if "rationale" in data and "reason" not in data:
            data["reason"] = data["rationale"]
        if "objective" not in data or not data["objective"]:
            data["objective"] = f"Execute {data.get('action_type', 'action')}"
        if "trigger" not in data or not data["trigger"]:
            data["trigger"] = "Policy rule condition satisfied"
        if "reason" not in data or not data["reason"]:
            data["reason"] = "Behavioral directive"
        super().__init__(**data)

    @property
    def target_topic(self) -> str:
        return self.target

    @property
    def rationale(self) -> str:
        return self.reason

    @field_validator("intensity")
    @classmethod
    def validate_intensity(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError(f"Intensity must be between 0.0 and 1.0, got {v}")
        return round(v, 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type.value if isinstance(self.action_type, ActionType) else str(self.action_type),
            "target": self.target,
            "intensity": self.intensity,
            "objective": self.objective,
            "trigger": self.trigger,
            "reason": self.reason,
            "required_information": self.required_information,
            "information_to_reveal": self.information_to_reveal,
            "information_to_withhold": self.information_to_withhold,
            "expected_effect": self.expected_effect,
        }


class PolicyTrace(BaseModel):
    """Auditable trace of the policy evaluation process."""
    turn: int = Field(..., ge=0, description="Interview turn number")
    candidate_signals: List[str] = Field(default_factory=list, description="Observed candidate signals from Phase 5")
    activated_values: List[str] = Field(default_factory=list, description="Persona values that influenced decision")
    active_goals: List[str] = Field(default_factory=list, description="Persona goals actively being pursued")
    state: Dict[str, float] = Field(default_factory=dict, description="Snapshot of dynamic ClientState metrics")
    stage: str = Field(default="", description="Active interview stage name")
    matched_policies: List[str] = Field(default_factory=list, description="IDs of all matching policy rules")
    selected_action: str = Field(..., description="Primary action selected")
    secondary_action: Optional[str] = Field(default=None, description="Optional secondary action selected")
    intensity: float = Field(..., ge=0.0, le=1.0, description="Computed decision intensity")
    reason: str = Field(..., description="Primary reasoning rationale")
    trait_influences: Dict[str, float] = Field(default_factory=dict, description="Numerical influence of traits on selected policy and intensity")
    execution_latency_ms: float = Field(default=0.0, ge=0.0, description="Policy evaluation latency in milliseconds")
    mode: str = Field(default="rule_based", description="Policy engine mode: rule_based or disabled")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn": self.turn,
            "candidate_signals": self.candidate_signals,
            "activated_values": self.activated_values,
            "active_goals": self.active_goals,
            "state": self.state,
            "stage": self.stage,
            "matched_policies": self.matched_policies,
            "selected_action": self.selected_action,
            "secondary_action": self.secondary_action,
            "intensity": round(self.intensity, 4),
            "reason": self.reason,
            "trait_influences": self.trait_influences,
            "execution_latency_ms": round(self.execution_latency_ms, 3),
            "mode": self.mode,
        }


class BehavioralDecision(BaseModel):
    """Aggregate decision produced by the Behavioral Policy Engine."""
    primary_action: BehavioralAction = Field(..., description="Primary behavioral directive")
    secondary_action: Optional[BehavioralAction] = Field(default=None, description="Optional complementary action")
    intensity: float = Field(..., ge=0.0, le=1.0, description="Overall decision intensity [0.0, 1.0]")
    policy_id: str = Field(..., description="ID of winning policy rule")
    trace: PolicyTrace = Field(..., description="Auditable policy trace")
    mode: str = Field(default="rule_based", description="Mode under which decision was evaluated")

    @field_validator("intensity")
    @classmethod
    def validate_intensity(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError(f"Intensity must be between 0.0 and 1.0, got {v}")
        return round(v, 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_action": self.primary_action.to_dict(),
            "secondary_action": self.secondary_action.to_dict() if self.secondary_action else None,
            "intensity": self.intensity,
            "policy_id": self.policy_id,
            "trace": self.trace.to_dict() if hasattr(self.trace, "to_dict") else self.trace,
            "mode": self.mode,
        }

    def format_prompt_instructions(self) -> str:
        """Render mandatory instructions for the response generator LLM."""
        lines = [
            "### SELECTED BEHAVIORAL ACTION (MANDATORY EXECUTION DIRECTIVE)",
            f"PRIMARY ACTION: {self.primary_action.action_type.value}",
        ]
        if self.primary_action.target:
            lines.append(f"TARGET: {self.primary_action.target}")
        lines.append(f"INTENSITY: {self.primary_action.intensity:.2f} (0.0 = gentle/subtle, 1.0 = forceful/uncompromising)")
        lines.append(f"OBJECTIVE: {self.primary_action.objective}")
        lines.append(f"TRIGGER: {self.primary_action.trigger}")
        lines.append(f"REASON: {self.primary_action.reason}")

        if self.secondary_action:
            lines.append(f"SECONDARY INTENT: {self.secondary_action.action_type.value} (Target: {self.secondary_action.target or 'General'}, Objective: {self.secondary_action.objective})")

        if self.primary_action.information_to_reveal:
            reveal_str = "; ".join(self.primary_action.information_to_reveal)
            lines.append(f"AUTHORIZED INFORMATION TO REVEAL: {reveal_str}")

        if self.primary_action.information_to_withhold:
            withhold_str = "; ".join(self.primary_action.information_to_withhold)
            lines.append(f"STRICTLY CONFIDENTIAL - DO NOT REVEAL: {withhold_str}")

        lines.extend([
            "",
            "MANDATORY EXECUTION CONSTRAINTS:",
            "1. You MUST realize the PRIMARY ACTION in your speech. DO NOT invent, substitute, or execute a different behavioral action.",
            "2. If PRIMARY ACTION is WITHHOLD_INFORMATION, state professionally that the requested information cannot be disclosed. Under NO circumstances reveal it.",
            "3. If PRIMARY ACTION is CHALLENGE_CLAIM or REQUEST_EVIDENCE, challenge the specified TARGET with the designated INTENSITY.",
            "4. If PRIMARY ACTION is REDIRECT or PUSH_BACK, firmly push back, assert control, and steer the candidate back to the current interview focus. If intensity is high, be sharp and reprimand inappropriate or irrelevant behavior.",
            "5. If PRIMARY ACTION is ACKNOWLEDGE_POINT, concede or validate the candidate's point before addressing any secondary intent.",
            "6. DO NOT mention behavioral action names (e.g. 'CHALLENGE_CLAIM'), internal scores, policy rules, or numerical state values (trust, skepticism) in your response.",
        ])

        return "\n".join(lines)
