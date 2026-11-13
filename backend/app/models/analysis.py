"""Candidate Behavior & Content Analysis Models (Phase 5).

Provides typed representations for semantic candidate turn analysis:
- Communication style, sales behavior, response quality, business/technical/commercial indicators
- Evidence extraction with confidence tracking
- Structured Candidate Facts (with lifecycle status: OBSERVED, CLAIMED, CONFIRMED, CONTRADICTED)
- Structured Candidate Claims (subjective/unverified vs objective facts)
- Fact & Claim Ledgers with contradiction preservation
"""

from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class FactStatus(str, Enum):
    """Lifecycle status of an extracted candidate fact."""
    OBSERVED = "OBSERVED"
    CLAIMED = "CLAIMED"
    CONFIRMED = "CONFIRMED"
    CONTRADICTED = "CONTRADICTED"
    UNKNOWN = "UNKNOWN"


class CandidateFact(BaseModel):
    """Structured verifiable fact uncovered or confirmed in the conversation."""
    id: str = Field(..., description="Unique fact identifier, e.g., 'fact_current_vendor'")
    category: str = Field(..., description="Category: pain_point, business_impact, budget, timeline, current_vendor, technical_requirement, general")
    value: str = Field(..., description="Concrete fact value or description")
    confidence: float = Field(default=0.80, ge=0.0, le=1.0, description="Confidence score [0.0, 1.0]")
    source_turn: int = Field(..., ge=0, description="Turn number where this fact was identified")
    evidence: str = Field(..., description="Verbatim or summarized phrase serving as evidence")
    status: FactStatus = Field(default=FactStatus.OBSERVED, description="Status in working memory")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "value": self.value,
            "confidence": round(self.confidence, 4),
            "source_turn": self.source_turn,
            "evidence": self.evidence,
            "status": self.status.value if isinstance(self.status, FactStatus) else self.status,
        }


class CandidateClaim(BaseModel):
    """Subjective, commercial, or technical assertion made by candidate, not yet established as ground truth."""
    id: str = Field(..., description="Unique claim identifier, e.g., 'claim_uptime_9999'")
    topic: str = Field(..., description="Topic of the claim, e.g., 'uptime', 'cost_reduction', 'security'")
    claim: str = Field(..., description="The specific assertion or proposition stated by candidate")
    evidence_provided: bool = Field(default=False, description="Whether candidate provided supporting empirical data")
    is_quantitative: bool = Field(default=False, description="Whether the claim includes specific numbers, percentages, or metrics")
    confidence: float = Field(default=0.80, ge=0.0, le=1.0, description="Confidence in claim extraction [0.0, 1.0]")
    source_turn: int = Field(..., ge=0, description="Turn number where the claim was made")
    evidence: Optional[str] = Field(default=None, description="Supporting excerpt if provided")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "claim": self.claim,
            "evidence_provided": self.evidence_provided,
            "is_quantitative": self.is_quantitative,
            "confidence": round(self.confidence, 4),
            "source_turn": self.source_turn,
            "evidence": self.evidence,
        }


class CommunicationStyleAnalysis(BaseModel):
    """Semantic evaluation of candidate conversational delivery."""
    clarity: float = Field(default=0.80, ge=0.0, le=1.0, description="How clear and articulate the answer was")
    conciseness: float = Field(default=0.80, ge=0.0, le=1.0, description="Brevity vs verbosity")
    confidence: float = Field(default=0.80, ge=0.0, le=1.0, description="Confidence in tone and framing")
    professionalism: float = Field(default=0.90, ge=0.0, le=1.0, description="Executive presence and posture")
    directness: float = Field(default=0.80, ge=0.0, le=1.0, description="Direct answer vs beating around the bush")


class SalesBehaviorAnalysis(BaseModel):
    """Structured classification of sales techniques displayed in this turn."""
    discovery_question: bool = Field(default=False, description="Candidate asked an inquiry to understand client context")
    needs_exploration: bool = Field(default=False, description="Candidate probed deeper into expressed bottlenecks")
    value_proposition: bool = Field(default=False, description="Candidate explained concrete business benefits")
    feature_dumping: bool = Field(default=False, description="Candidate listed product features without mapping to pain")
    objection_handling: bool = Field(default=False, description="Candidate actively addressed a client concern")
    negotiation: bool = Field(default=False, description="Candidate discussed concessions, trade-offs, or commercial terms")
    closing_attempt: bool = Field(default=False, description="Candidate attempted to gain commitment or agreement")
    next_step_proposal: bool = Field(default=False, description="Candidate proposed a concrete follow-up meeting or demo")


class ResponseQualityAnalysis(BaseModel):
    """Assessment of the informational quality and trustworthiness of candidate answer."""
    answered_question: bool = Field(default=True, description="Directly addressed the stakeholder's prior prompt")
    evasive: bool = Field(default=False, description="Dodged or sidestepped the question")
    vague: bool = Field(default=False, description="High-level buzzwords without substance")
    contradictory: bool = Field(default=False, description="Contradicted earlier statements in the session")
    defensive: bool = Field(default=False, description="Reacted defensively or combatively to skepticism")
    proactive: bool = Field(default=False, description="Anticipated client needs and offered valuable perspective")
    evidence_backed: bool = Field(default=False, description="Supported statements with data, benchmarks, or case studies")
    unsupported_claim: bool = Field(default=False, description="Made significant assertions without backing")
    unprofessional_behavior: bool = Field(default=False, description="Acted inappropriately, unprofessionally, or with hostility")


class BusinessUnderstandingAnalysis(BaseModel):
    """Evaluation of candidate's commercial and business acumen in this turn."""
    pain_identified: bool = Field(default=False, description="Uncovered or articulated specific business pain")
    impact_identified: bool = Field(default=False, description="Explored financial, operational, or strategic impact")
    decision_criteria_explored: bool = Field(default=False, description="Investigated stakeholder priorities and constraints")
    business_value_explained: bool = Field(default=False, description="Connected solution to business outcomes")
    roi_discussed: bool = Field(default=False, description="Discussed financial payback or efficiency gains")


class TechnicalBehaviorAnalysis(BaseModel):
    """Evaluation of technical depth, architectural fit, and feasibility."""
    technical_claim: bool = Field(default=False, description="Asserted a technical capability or integration")
    technical_evidence: bool = Field(default=False, description="Provided concrete technical architecture or benchmarks")
    architecture_explanation: bool = Field(default=False, description="Explained how systems integrate or scale")
    security_discussion: bool = Field(default=False, description="Discussed compliance, encryption, or security safeguards")
    scalability_discussion: bool = Field(default=False, description="Discussed load handling, throughput, or high availability")
    implementation_discussion: bool = Field(default=False, description="Discussed migration timeline, rollout, or staffing")


class CommercialBehaviorAnalysis(BaseModel):
    """Evaluation of commercial, contracting, and procurement readiness."""
    pricing_discussed: bool = Field(default=False, description="Discussed licensing, pricing structure, or cost model")
    budget_discussed: bool = Field(default=False, description="Asked about or acknowledged client budget limits")
    procurement_discussed: bool = Field(default=False, description="Discussed approval hurdles or purchasing process")
    timeline_discussed: bool = Field(default=False, description="Discussed target dates for pilot or production rollout")
    commercial_expectation_defined: bool = Field(default=False, description="Framed engagement terms or pilot scope")


class SemanticClassificationEvidence(BaseModel):
    """Inspectable evidence supporting a key semantic determination."""
    criterion: str = Field(..., description="Target criterion or behavior name")
    detected: bool = Field(..., description="Whether this criterion was detected")
    evidence: Optional[str] = Field(default=None, description="Verbatim quote or excerpt demonstrating detection")
    confidence: float = Field(default=0.80, ge=0.0, le=1.0, description="Confidence in this extraction [0.0, 1.0]")


class CandidateTurnAnalysis(BaseModel):
    """Comprehensive, typed semantic analysis of a single salesperson turn."""
    turn: int = Field(default=1, ge=0, description="Turn index of the conversation")
    communication: CommunicationStyleAnalysis = Field(default_factory=CommunicationStyleAnalysis)
    sales_behavior: SalesBehaviorAnalysis = Field(default_factory=SalesBehaviorAnalysis)
    response_quality: ResponseQualityAnalysis = Field(default_factory=ResponseQualityAnalysis)
    business_understanding: BusinessUnderstandingAnalysis = Field(default_factory=BusinessUnderstandingAnalysis)
    technical_behavior: TechnicalBehaviorAnalysis = Field(default_factory=TechnicalBehaviorAnalysis)
    commercial_behavior: CommercialBehaviorAnalysis = Field(default_factory=CommercialBehaviorAnalysis)
    evidence_items: List[SemanticClassificationEvidence] = Field(default_factory=list)
    extracted_facts: List[CandidateFact] = Field(default_factory=list)
    extracted_claims: List[CandidateClaim] = Field(default_factory=list)
    summary_observations: str = Field(default="", description="Concise notes on salesperson execution")
    overall_confidence: float = Field(default=0.85, ge=0.0, le=1.0, description="Aggregate confidence score")
    uncertain: bool = Field(default=False, description="Whether the response was too ambiguous for definitive classification")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn": self.turn,
            "communication": self.communication.model_dump(),
            "sales_behavior": self.sales_behavior.model_dump(),
            "response_quality": self.response_quality.model_dump(),
            "business_understanding": self.business_understanding.model_dump(),
            "technical_behavior": self.technical_behavior.model_dump(),
            "commercial_behavior": self.commercial_behavior.model_dump(),
            "evidence_items": [e.model_dump() for e in self.evidence_items],
            "extracted_facts": [f.to_dict() for f in self.extracted_facts],
            "extracted_claims": [c.to_dict() for c in self.extracted_claims],
            "summary_observations": self.summary_observations,
            "overall_confidence": round(self.overall_confidence, 4),
            "uncertain": self.uncertain,
        }


class CandidateFactLedger(BaseModel):
    """Per-session working memory of extracted facts with contradiction detection."""
    facts: Dict[str, CandidateFact] = Field(default_factory=dict)

    def add_or_update_fact(self, fact: CandidateFact) -> Optional[CandidateFact]:
        """Add new fact or flag contradiction if conflicting with previously observed fact."""
        for existing in self.facts.values():
            if existing.category == fact.category and existing.category in ["timeline", "budget", "current_vendor"]:
                # Check for direct conflicting value
                if existing.value.strip().lower() != fact.value.strip().lower():
                    existing.status = FactStatus.CONTRADICTED
                    fact.status = FactStatus.CONTRADICTED
        self.facts[fact.id] = fact
        return fact

    def to_list(self) -> List[Dict[str, Any]]:
        return [f.to_dict() for f in self.facts.values()]


class CandidateClaimLedger(BaseModel):
    """Per-session ledger of candidate claims made throughout the interview."""
    claims: List[CandidateClaim] = Field(default_factory=list)

    def add_claim(self, claim: CandidateClaim) -> None:
        self.claims.append(claim)

    def to_list(self) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self.claims]
