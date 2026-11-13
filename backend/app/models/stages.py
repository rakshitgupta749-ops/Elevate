"""Enterprise Sales Interview Stage Models.

Defines the discrete, deterministic conversation stages, stage criteria,
transition events, and overall interview lifecycle state for the simulated stakeholder.

Strict architectural separation:
- ClientState (Phase 3): Internal perception/reaction of stakeholder toward the candidate.
- InterviewState (Phase 4): Explicit meeting stage, progress, turn counters, criteria, and lifecycle.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


class InterviewStage(str, Enum):
    """The 5 primary enterprise sales conversation stages."""
    STAGE_1_OPENING_RAPPORT = "STAGE_1_OPENING_RAPPORT"
    STAGE_2_PROBLEM_DISCOVERY = "STAGE_2_PROBLEM_DISCOVERY"
    STAGE_3_SOLUTION_ALIGNMENT = "STAGE_3_SOLUTION_ALIGNMENT"
    STAGE_4_OBJECTIONS_AND_DEEP_DIVE = "STAGE_4_OBJECTIONS_AND_DEEP_DIVE"
    STAGE_5_COMMERCIALS_AND_CLOSING = "STAGE_5_COMMERCIALS_AND_CLOSING"


class InterviewStatus(str, Enum):
    """Overall lifecycle status of the interview session."""
    ACTIVE = "ACTIVE"
    READY_TO_ADVANCE = "READY_TO_ADVANCE"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"


class StageCriterion(BaseModel):
    """Specific measurable criterion or information milestone within an interview stage."""
    id: str = Field(..., description="Unique criterion identifier")
    name: str = Field(..., description="Human-readable criterion name")
    description: str = Field(..., description="Concrete description of what candidate must demonstrate or uncover")
    stage: InterviewStage = Field(..., description="Stage where this criterion belongs")
    required: bool = Field(default=False, description="Whether this criterion is mandatory for stage completion")
    satisfied: bool = Field(default=False, description="Whether this criterion has been met")
    satisfied_at_turn: Optional[int] = Field(default=None, description="Turn number when criterion was satisfied")
    evidence: Optional[str] = Field(default=None, description="Candidate excerpt or signal evidence satisfying the criterion")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "stage": self.stage.value if isinstance(self.stage, InterviewStage) else self.stage,
            "required": self.required,
            "satisfied": self.satisfied,
            "satisfied_at_turn": self.satisfied_at_turn,
            "evidence": self.evidence,
        }


class StageConfig(BaseModel):
    """Configuration and guardrails for a specific interview stage."""
    stage: InterviewStage = Field(..., description="Stage identifier")
    name: str = Field(..., description="Human-readable stage title")
    objective: str = Field(..., description="Core business objective of the stage")
    min_turns: int = Field(..., ge=1, description="Minimum turns required before stage can advance")
    max_turns: int = Field(..., ge=1, description="Maximum turns permitted before fail-safe advancement")
    allowed_next_stages: List[InterviewStage] = Field(default_factory=list, description="Permitted stage destinations")
    criteria: List[StageCriterion] = Field(default_factory=list, description="Criteria registered for this stage")


class StageTransitionEvent(BaseModel):
    """Auditable log entry recorded whenever the conversation transitions between stages."""
    turn: int = Field(..., ge=0, description="Turn number at which the transition occurred")
    from_stage: InterviewStage = Field(..., description="Preceding interview stage")
    to_stage: InterviewStage = Field(..., description="Succeeding interview stage")
    reason: str = Field(..., description="Inspectable deterministic rationale for the transition")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="ISO timestamp")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn": self.turn,
            "from_stage": self.from_stage.value if isinstance(self.from_stage, InterviewStage) else self.from_stage,
            "to_stage": self.to_stage.value if isinstance(self.to_stage, InterviewStage) else self.to_stage,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


class InterviewState(BaseModel):
    """Explicit, inspectable state of the sales interview meeting."""
    current_stage: InterviewStage = Field(
        default=InterviewStage.STAGE_1_OPENING_RAPPORT,
        description="Active interview stage"
    )
    stage_turn_count: int = Field(default=0, ge=0, description="Turns elapsed in current stage")
    total_turn_count: int = Field(default=0, ge=0, description="Total turns elapsed in interview session")
    max_total_turns: int = Field(default=15, ge=1, description="Global maximum turns allowed before forced completion")
    status: InterviewStatus = Field(default=InterviewStatus.ACTIVE, description="Lifecycle status")
    criteria: Dict[str, StageCriterion] = Field(default_factory=dict, description="Registry of all stage criteria")
    history: List[StageTransitionEvent] = Field(default_factory=list, description="Audit log of stage transitions")
    termination_reason: Optional[str] = Field(default=None, description="Reason if early termination occurred")

    @property
    def stage_history(self) -> List[Dict[str, Any]]:
        """Convenience property for stage history list."""
        return [event.to_dict() for event in self.history]

    @property
    def discovery_criteria(self) -> Dict[str, bool]:
        """Status of all Problem Discovery criteria."""
        return {
            c.id: c.satisfied
            for c in self.criteria.values()
            if c.stage == InterviewStage.STAGE_2_PROBLEM_DISCOVERY
        }

    @property
    def solution_alignment_criteria(self) -> Dict[str, bool]:
        """Status of all Solution Alignment criteria."""
        return {
            c.id: c.satisfied
            for c in self.criteria.values()
            if c.stage == InterviewStage.STAGE_3_SOLUTION_ALIGNMENT
        }

    @property
    def objections_covered(self) -> Dict[str, bool]:
        """Status of all Objections & Deep Dive criteria."""
        return {
            c.id: c.satisfied
            for c in self.criteria.values()
            if c.stage == InterviewStage.STAGE_4_OBJECTIONS_AND_DEEP_DIVE
        }

    @property
    def commercials_discussed(self) -> Dict[str, bool]:
        """Status of all Commercials criteria."""
        return {
            c.id: c.satisfied
            for c in self.criteria.values()
            if c.stage == InterviewStage.STAGE_5_COMMERCIALS_AND_CLOSING
        }

    @property
    def closing_criteria(self) -> Dict[str, bool]:
        """Status of closing criteria."""
        return self.commercials_discussed

    def get_stage_criteria(self, stage: InterviewStage) -> List[StageCriterion]:
        """Return list of criteria defined for a specific stage."""
        return [c for c in self.criteria.values() if c.stage == stage]

    def all_required_criteria_satisfied(self, stage: InterviewStage) -> bool:
        """Check if all required criteria for the given stage are satisfied."""
        stage_reqs = [c for c in self.criteria.values() if c.stage == stage and c.required]
        return all(c.satisfied for c in stage_reqs)

    def to_dict(self) -> Dict[str, Any]:
        """Produce a clean, JSON-serializable dictionary safe for LangGraph MemorySaver msgpack."""
        return {
            "current_stage": self.current_stage.value if isinstance(self.current_stage, InterviewStage) else self.current_stage,
            "stage_turn_count": self.stage_turn_count,
            "total_turn_count": self.total_turn_count,
            "max_total_turns": self.max_total_turns,
            "status": self.status.value if isinstance(self.status, InterviewStatus) else self.status,
            "criteria": {cid: c.to_dict() for cid, c in self.criteria.items()},
            "history": [event.to_dict() for event in self.history],
            "termination_reason": self.termination_reason,
            "discovery_criteria": self.discovery_criteria,
            "solution_alignment_criteria": self.solution_alignment_criteria,
            "objections_covered": self.objections_covered,
            "commercials_discussed": self.commercials_discussed,
        }
