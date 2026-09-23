"""Information and Memory Models (Phase 7).

Defines strongly typed representations for:
- StakeholderKnowledgeItem & KnowledgeAccessDecision
- WorldFact (Scenario ground truth with immutability)
- MemoryItem (Typed conversational memory with provenance)
- StakeholderCommitment & Unresolved items (Questions & Objections)
- ConsistencyValidationResult
"""

import uuid
from enum import Enum
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class KnowledgeStatus(str, Enum):
    """Status of knowledge held by the stakeholder."""
    KNOWN = "KNOWN"
    CONFIRMED = "CONFIRMED"
    PARTIALLY_KNOWN = "PARTIALLY_KNOWN"
    UNKNOWN = "UNKNOWN"
    UNCERTAIN = "UNCERTAIN"
    CONFIDENTIAL = "CONFIDENTIAL"


class InformationSource(str, Enum):
    """Provenance origin of an information item."""
    WORLD_MODEL = "WORLD_MODEL"
    CANDIDATE_STATEMENT = "CANDIDATE_STATEMENT"
    STAKEHOLDER_STATEMENT = "STAKEHOLDER_STATEMENT"
    SCENARIO = "SCENARIO"
    SYSTEM_PROVIDED = "SYSTEM_PROVIDED"


class DisclosureLevel(str, Enum):
    """Information security and disclosure boundary level."""
    PUBLIC = "PUBLIC"              # Freely shareable with external parties
    SHAREABLE = "SHAREABLE"        # Operational context shareable under normal discovery
    INTERNAL = "INTERNAL"          # Internal team awareness; requires moderate trust
    SENSITIVE = "SENSITIVE"        # Sensitive technical/operational details; high trust
    CONFIDENTIAL = "CONFIDENTIAL"  # Explicitly confidential (e.g. exact budget, roadmap)
    PRIVATE = "PRIVATE"            # Internal board / personal political motivations (never disclosed)
    FORBIDDEN = "FORBIDDEN"        # Out-of-bounds or strictly disallowed


class StakeholderKnowledgeItem(BaseModel):
    """Granular piece of knowledge known or unknown to the simulated stakeholder."""
    id: str = Field(default_factory=lambda: f"k_{uuid.uuid4().hex[:8]}", description="Unique knowledge item identifier")
    topic: str = Field(..., description="Topic domain, e.g., 'cloud_infrastructure', 'budget'")
    value: Any = Field(default="", description="Value or descriptive fact")
    fact_summary: Optional[str] = Field(default=None)
    status: Union[KnowledgeStatus, str] = Field(default=KnowledgeStatus.KNOWN, description="Knowledge state")
    source: Union[InformationSource, str] = Field(default=InformationSource.WORLD_MODEL, description="Provenance origin")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in accuracy [0.0, 1.0]")
    disclosure_level: Union[DisclosureLevel, str] = Field(default=DisclosureLevel.INTERNAL, description="Disclosure classification")
    known_since_turn: int = Field(default=0, ge=0, description="Turn number when learned/established")
    provenance: str = Field(default="", description="Human-readable provenance trail")
    is_disclosed: bool = Field(default=False)
    disclosure_count: int = Field(default=0)
    first_disclosed_turn: Optional[int] = Field(default=None)

    def __init__(self, **data):
        import uuid
        if "fact_summary" in data and "value" not in data:
            data["value"] = data["fact_summary"]
        super().__init__(**data)

    def mark_disclosed(self, turn: int):
        self.is_disclosed = True
        self.disclosure_count += 1
        if self.first_disclosed_turn is None:
            self.first_disclosed_turn = turn

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "value": self.value,
            "status": self.status.value if isinstance(self.status, KnowledgeStatus) else self.status,
            "source": self.source.value if isinstance(self.source, InformationSource) else self.source,
            "confidence": round(self.confidence, 4),
            "disclosure_level": self.disclosure_level.value if isinstance(self.disclosure_level, DisclosureLevel) else self.disclosure_level,
            "known_since_turn": self.known_since_turn,
            "provenance": self.provenance,
            "is_disclosed": self.is_disclosed,
            "disclosure_count": self.disclosure_count,
            "first_disclosed_turn": self.first_disclosed_turn,
        }


class KnowledgeAccessDecision(BaseModel):
    """Deterministic access determination for a requested knowledge item or topic."""
    allowed: bool = Field(..., description="Whether disclosure is permitted in the current turn")
    reason: str = Field(..., description="Reason for permission grant or denial")
    disclosure_level: DisclosureLevel = Field(..., description="Classification level")
    item_id: Optional[str] = Field(default=None, description="Matched knowledge item id if any")

    def __init__(self, **data):
        if "permitted" in data and "allowed" not in data:
            data["allowed"] = data["permitted"]
        super().__init__(**data)

    @property
    def permitted(self) -> bool:
        return self.allowed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "permitted": self.allowed,
            "reason": self.reason,
            "disclosure_level": self.disclosure_level.value if isinstance(self.disclosure_level, DisclosureLevel) else self.disclosure_level,
            "item_id": self.item_id,
        }


class WorldFact(BaseModel):
    """Ground truth factual entry in the World Model registry."""
    key: str = Field(..., description="Canonical key, e.g., 'company.cloud_provider'")
    value: Any = Field(..., description="Ground truth value")
    category: str = Field(..., description="Category: company, technology, business, financial, organizational, timeline, constraints")
    source: InformationSource = Field(default=InformationSource.WORLD_MODEL, description="Source of truth")
    immutable: bool = Field(default=True, description="Whether this fact cannot be modified mid-session")
    disclosure_level: DisclosureLevel = Field(default=DisclosureLevel.INTERNAL, description="Disclosure boundary")
    provenance: str = Field(default="World Model Specification", description="Authoritative source description")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "source": self.source.value if isinstance(self.source, InformationSource) else self.source,
            "immutable": self.immutable,
            "disclosure_level": self.disclosure_level.value if isinstance(self.disclosure_level, DisclosureLevel) else self.disclosure_level,
            "provenance": self.provenance,
        }


class MemoryType(str, Enum):
    """Categorical classification of conversational memories."""
    CANDIDATE_STATEMENT = "CANDIDATE_STATEMENT"
    CANDIDATE_CLAIM = "CANDIDATE_CLAIM"
    CANDIDATE_FACT = "CANDIDATE_FACT"
    STAKEHOLDER_COMMITMENT = "STAKEHOLDER_COMMITMENT"
    STAKEHOLDER_STATEMENT = "STAKEHOLDER_STATEMENT"
    UNRESOLVED_QUESTION = "UNRESOLVED_QUESTION"
    UNRESOLVED_OBJECTION = "UNRESOLVED_OBJECTION"
    DECISION_SIGNAL = "DECISION_SIGNAL"
    CONTRADICTION = "CONTRADICTION"
    RELEVANT_EVENT = "RELEVANT_EVENT"


class MemoryItem(BaseModel):
    """Structured, provenance-tracked conversational memory record."""
    memory_id: str = Field(..., description="Unique memory identifier")
    type: MemoryType = Field(..., description="Category of memory")
    content: str = Field(..., description="Concise text representation of the memory")
    topic: str = Field(default="general", description="Topic tag, e.g., 'latency', 'pricing', 'cloud'")
    source_turn: int = Field(default=0, ge=0, description="Turn number when memory was formed")
    importance: float = Field(default=0.50, ge=0.0, le=1.0, description="Relevance weight [0.0, 1.0]")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Certainty score")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    retrieval_tags: List[str] = Field(default_factory=list, description="Keywords for selective retrieval")
    source: Optional[InformationSource] = Field(default=None)
    provenance: Optional[str] = Field(default=None)
    speaker: Optional[str] = Field(default=None)
    related_turn_numbers: Optional[List[int]] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary typed metadata")

    def __init__(self, **data):
        if "tags" in data and "retrieval_tags" not in data:
            data["retrieval_tags"] = data["tags"]
        if "turn_number" in data and "source_turn" not in data:
            data["source_turn"] = data["turn_number"]
        super().__init__(**data)

    @property
    def tags(self) -> List[str]:
        return self.retrieval_tags

    @property
    def memory_type(self) -> MemoryType:
        return self.type

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "type": self.type.value if isinstance(self.type, MemoryType) else self.type,
            "content": self.content,
            "topic": self.topic,
            "source_turn": self.source_turn,
            "importance": round(self.importance, 4),
            "confidence": round(self.confidence, 4),
            "timestamp": self.timestamp,
            "retrieval_tags": self.retrieval_tags,
            "source": self.source.value if isinstance(self.source, InformationSource) else self.source,
            "provenance": self.provenance,
            "speaker": self.speaker,
            "related_turn_numbers": self.related_turn_numbers,
            "metadata": self.metadata,
        }


class CommitmentStatus(str, Enum):
    PROMISED = "PROMISED"
    ACTIVE = "ACTIVE"
    FULFILLED = "FULFILLED"
    BROKEN = "BROKEN"
    SUPERSEDED = "SUPERSEDED"


class StakeholderCommitment(BaseModel):
    """Action or artifact promised by the stakeholder during conversation."""
    id: str = Field(..., description="Unique commitment ID")
    commitment_type: str = Field(default="DOCUMENT", description="Type: DOCUMENT, FOLLOW_UP, MEETING, INTRO")
    description: str = Field(..., description="Description of the commitment")
    status: Union[CommitmentStatus, str] = Field(default=CommitmentStatus.PROMISED)
    source_turn: int = Field(default=0, ge=0)
    topic: Optional[str] = Field(default=None)
    speaker: Optional[str] = Field(default="stakeholder")
    fulfilled_at_turn: Optional[int] = Field(default=None)

    def __init__(self, **data):
        if "turn_promised" in data and "source_turn" not in data:
            data["source_turn"] = data["turn_promised"]
        super().__init__(**data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "commitment_type": self.commitment_type,
            "description": self.description,
            "status": self.status.value if isinstance(self.status, CommitmentStatus) else self.status,
            "source_turn": self.source_turn,
            "topic": self.topic,
            "speaker": self.speaker,
            "fulfilled_at_turn": self.fulfilled_at_turn,
        }


class ItemStatus(str, Enum):
    OPEN = "OPEN"
    UNRESOLVED = "UNRESOLVED"
    PARTIALLY_ADDRESSED = "PARTIALLY_ADDRESSED"
    RESOLVED = "RESOLVED"
    REOPENED = "REOPENED"


class UnresolvedQuestion(BaseModel):
    """Question posed by stakeholder that candidate has not yet adequately answered."""
    id: str = Field(..., description="Question ID")
    question: str = Field(default="", description="Verbatim or summarized question")
    topic: str = Field(default="general", description="Topic tag")
    source_turn: int = Field(default=0, ge=0)
    status: Union[ItemStatus, str] = Field(default=ItemStatus.UNRESOLVED)
    asked_by: Optional[str] = Field(default="stakeholder")
    addressed_at_turn: Optional[int] = Field(default=None)
    resolved_at_turn: Optional[int] = Field(default=None)

    def __init__(self, **data):
        if "question_text" in data and "question" not in data:
            data["question"] = data["question_text"]
        if "turn_asked" in data and "source_turn" not in data:
            data["source_turn"] = data["turn_asked"]
        super().__init__(**data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "topic": self.topic,
            "source_turn": self.source_turn,
            "status": self.status.value if isinstance(self.status, ItemStatus) else self.status,
            "asked_by": self.asked_by,
            "addressed_at_turn": self.addressed_at_turn,
            "resolved_at_turn": self.resolved_at_turn,
        }


class UnresolvedObjection(BaseModel):
    """Active concern, risk, or objection raised by stakeholder."""
    id: str = Field(..., description="Objection ID")
    topic: str = Field(default="general", description="Topic, e.g., 'security', 'pricing', 'downtime'")
    description: str = Field(default="", description="Substance of the objection")
    source_turn: int = Field(default=0, ge=0)
    severity: Union[float, str] = Field(default=0.50)
    status: Union[ItemStatus, str] = Field(default=ItemStatus.OPEN)
    evidence_provided: Optional[str] = Field(default=None)
    resolved_at_turn: Optional[int] = Field(default=None)

    def __init__(self, **data):
        if "objection_text" in data and "description" not in data:
            data["description"] = data["objection_text"]
        if "turn_raised" in data and "source_turn" not in data:
            data["source_turn"] = data["turn_raised"]
        super().__init__(**data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "description": self.description,
            "source_turn": self.source_turn,
            "severity": self.severity,
            "status": self.status.value if isinstance(self.status, ItemStatus) else self.status,
            "evidence_provided": self.evidence_provided,
            "resolved_at_turn": self.resolved_at_turn,
        }


class ConsistencyValidationResult(BaseModel):
    """Evaluation result from the post-generation response consistency validator."""
    is_valid: bool = Field(default=True, description="True if response complies with memory & world facts")
    violations: List[str] = Field(default_factory=list, description="List of violation messages")
    violation_type: Optional[str] = Field(default=None, description="Category of violation if any")
    violation_details: Optional[str] = Field(default=None, description="Specific factual or boundary mismatch")
    corrective_instructions: Optional[str] = Field(default=None, description="Constraint guidance for single retry")
    fallback_response: Optional[str] = Field(default=None, description="Deterministic fallback response if repair fails")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "violations": self.violations,
            "violation_type": self.violation_type,
            "violation_details": self.violation_details,
            "corrective_instructions": self.corrective_instructions,
            "fallback_response": self.fallback_response,
        }
