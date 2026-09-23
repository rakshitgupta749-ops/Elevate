"""Dynamic Runtime State Models for Elevate.

This module defines the runtime conversational state of the simulated stakeholder.
Maintains strict architectural separation between:
- WHO the stakeholder is (EnterprisePersona - static/immutable)
- HOW the stakeholder currently perceives and reacts to the candidate (ClientState - dynamic runtime)

NOTE ON SIMULATION VARIABLES:
The numerical attributes in ClientState (trust, skepticism, patience, etc.) are internal
normalized simulation control parameters (clamped strictly between 0.0 and 1.0).
They are NOT psychometric or psychological diagnostic measurements.
"""

from typing import Dict, Optional, Literal
from datetime import datetime
import math
from pydantic import BaseModel, Field, field_validator, model_validator


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp a floating point number within bounded range, guarding against NaN and Inf."""
    if math.isnan(value):
        return min_val
    if math.isinf(value):
        return max_val if value > 0 else min_val
    return max(min_val, min(max_val, round(value, 4)))


class ClientState(BaseModel):
    """Dynamic runtime perception state of the simulated stakeholder during conversation."""
    trust: float = Field(default=0.50, ge=0.0, le=1.0, description="Confidence in candidate's credibility and honesty")
    skepticism: float = Field(default=0.60, ge=0.0, le=1.0, description="Doubt regarding unverified claims or vague assertions")
    patience: float = Field(default=0.70, ge=0.0, le=1.0, description="Tolerance for verbose, evasive, or repetitive answers")
    engagement: float = Field(default=0.65, ge=0.0, le=1.0, description="Level of active conversational investment and attention")
    interest: float = Field(default=0.50, ge=0.0, le=1.0, description="Interest in the proposed commercial or technical solution")
    perceived_risk: float = Field(default=0.50, ge=0.0, le=1.0, description="Assessment of architectural, financial, or organizational danger")
    frustration: float = Field(default=0.10, ge=0.0, le=1.0, description="Annoyance or irritation caused by poor communication or dodging")
    confidence_in_candidate: float = Field(default=0.45, ge=0.0, le=1.0, description="Overall evaluation of candidate competence")

    @model_validator(mode="after")
    def clamp_all_fields(self) -> "ClientState":
        self.trust = clamp(self.trust)
        self.skepticism = clamp(self.skepticism)
        self.patience = clamp(self.patience)
        self.engagement = clamp(self.engagement)
        self.interest = clamp(self.interest)
        self.perceived_risk = clamp(self.perceived_risk)
        self.frustration = clamp(self.frustration)
        self.confidence_in_candidate = clamp(self.confidence_in_candidate)
        return self

    def apply_delta(self, delta: "StateDelta") -> "ClientState":
        """Apply a StateDelta and return a new clamped ClientState."""
        return ClientState(
            trust=clamp(self.trust + delta.trust),
            skepticism=clamp(self.skepticism + delta.skepticism),
            patience=clamp(self.patience + delta.patience),
            engagement=clamp(self.engagement + delta.engagement),
            interest=clamp(self.interest + delta.interest),
            perceived_risk=clamp(self.perceived_risk + delta.perceived_risk),
            frustration=clamp(self.frustration + delta.frustration),
            confidence_in_candidate=clamp(self.confidence_in_candidate + delta.confidence_in_candidate),
        )

    def to_dict(self) -> Dict[str, float]:
        """Return a clean dictionary of all normalized state variables."""
        return {
            "trust": round(self.trust, 4),
            "skepticism": round(self.skepticism, 4),
            "patience": round(self.patience, 4),
            "engagement": round(self.engagement, 4),
            "interest": round(self.interest, 4),
            "perceived_risk": round(self.perceived_risk, 4),
            "frustration": round(self.frustration, 4),
            "confidence_in_candidate": round(self.confidence_in_candidate, 4),
        }


class StateDelta(BaseModel):
    """Explicit incremental adjustment to client state."""
    trust: float = Field(default=0.0, description="Delta for trust")
    skepticism: float = Field(default=0.0, description="Delta for skepticism")
    patience: float = Field(default=0.0, description="Delta for patience")
    engagement: float = Field(default=0.0, description="Delta for engagement")
    interest: float = Field(default=0.0, description="Delta for interest")
    perceived_risk: float = Field(default=0.0, description="Delta for perceived_risk")
    frustration: float = Field(default=0.0, description="Delta for frustration")
    confidence_in_candidate: float = Field(default=0.0, description="Delta for confidence_in_candidate")
    reason: str = Field(..., description="Inspectable explanation for this state adjustment")

    def to_dict(self) -> Dict[str, float]:
        return {
            "trust": round(self.trust, 4),
            "skepticism": round(self.skepticism, 4),
            "patience": round(self.patience, 4),
            "engagement": round(self.engagement, 4),
            "interest": round(self.interest, 4),
            "perceived_risk": round(self.perceived_risk, 4),
            "frustration": round(self.frustration, 4),
            "confidence_in_candidate": round(self.confidence_in_candidate, 4),
        }


class StateEvent(BaseModel):
    """Auditable log entry recording exact state transition and rationale."""
    turn: int = Field(..., ge=0, description="Turn index (0 = initialization, 1, 2, ...)")
    event_type: str = Field(..., description="Identifier of the event triggering the transition")
    reason: str = Field(..., description="Human-readable explanation of why the state changed")
    before: Dict[str, float] = Field(..., description="Snapshot of state variables prior to delta")
    delta: Dict[str, float] = Field(..., description="Deltas applied to state variables")
    after: Dict[str, float] = Field(..., description="Snapshot of state variables following transition")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="ISO timestamp")


class InteractionSignal(BaseModel):
    """Internal interaction classification triggering state delta calculation."""
    type: Literal[
        "positive_evidence",
        "unsupported_claim",
        "candidate_dodges_question",
        "clear_answer",
        "vague_response",
        "neutral_turn",
        "price_concession",
        "unprofessional_behavior",
    ] = Field(..., description="Category of candidate behavior detected in interaction")
    details: Optional[str] = Field(None, description="Supporting context or extracted phrase")
    reason: Optional[str] = Field(None, description="Optional custom rationale")

