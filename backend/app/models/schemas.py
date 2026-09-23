from pydantic import BaseModel
from typing import List, Optional

# Re-export structured persona and world model components for convenient access
from app.models.persona import (
    PersonaProfile,
    ValueOrientation,
    StakeholderGoal,
    Incentive,
    KnowledgeBoundary,
    CompanyContext,
    EnterprisePersona,
)

# Re-export dynamic runtime state components
from app.models.state import (
    ClientState,
    StateDelta,
    StateEvent,
    InteractionSignal,
)

# Re-export behavioral policy components (Phase 6)
from app.models.behavior import (
    ActionType,
    BehavioralAction,
    PolicyTrace,
    BehavioralDecision,
)

# Re-export information & memory components (Phase 7)
from app.models.memory import (
    KnowledgeStatus,
    InformationSource,
    DisclosureLevel,
    StakeholderKnowledgeItem,
    KnowledgeAccessDecision,
    WorldFact,
    MemoryType,
    MemoryItem,
    StakeholderCommitment,
    CommitmentStatus,
    UnresolvedQuestion,
    UnresolvedObjection,
    ItemStatus,
    ConsistencyValidationResult,
)

# Re-export evaluation components (Phase 8)
from app.evaluation.evaluation_models import (
    SimulatorArchitectureMode,
    SimulatorFailureCategory,
    ExpectedBehavior,
    ControlledScenario,
    TurnEvaluation,
    SimulatorEvaluation,
    HumanEvaluationRecord,
)

# Re-export persona configuration components (Phase 9)
from app.models.configuration import (
    PersonaTraitDefinition,
    PersonaPreset,
    PersonaConfiguration,
    RoleConfigurationSchema,
)

class RoleModel(BaseModel):
    id: str
    name: str
    description: str
    traits: List[str]

class TopicModel(BaseModel):
    id: str
    title: str
    description: str
    icon: str

class SessionRequest(BaseModel):
    topic: str
    role: str
    scenario: str
    experience: str
    style: str
    policy_mode: Optional[str] = "rule_based"
    memory_mode: Optional[str] = "full"
    architecture_mode: Optional[str] = "FULL_SIMULATOR"
    persona_configuration: Optional[PersonaConfiguration] = None

class SessionResponse(BaseModel):
    session_id: str
    initial_message: Optional[str] = None

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    reply: str

class EvaluationRunRequest(BaseModel):
    scenario_id: str
    architecture_mode: Optional[str] = "FULL_SIMULATOR"
    role_id: Optional[str] = "CTO"
    topic: Optional[str] = "Enterprise Cloud Modernization"
    random_seed: Optional[int] = 42

class HumanRatingRequest(BaseModel):
    session_id: str
    evaluator_id: Optional[str] = "expert_evaluator"
    role_authenticity: int
    behavior_realism: int
    question_realism: int
    objection_realism: int
    state_evolution: int
    information_realism: int
    stakeholder_goal_consistency: int
    overall_realism: int
    free_text_feedback: Optional[str] = ""
    behavioral_agreement_ratings: Optional[dict] = {}


# Re-export coaching, lifecycle & history components (Priority P0 & P1)
from app.models.coaching import (
    FeedbackSubscore,
    FeedbackStrength,
    FeedbackWeakness,
    StructuredCoachingReport,
    CoachingHintResponse,
    RewindResponse,
    SessionSummaryItem,
    SessionTranscriptResponse,
)


