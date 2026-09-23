"""Typed Structured Persona & World Model schemas for Elevate.

This module establishes the machine-readable data foundation for simulated
enterprise stakeholders (CTO, VP Eng, CIO, CFO, Procurement, etc.) and their
operating environment (CompanyContext / World Model).

NOTE ON VALUE ORIENTATION & INCENTIVE WEIGHTS:
The numerical weights in ValueOrientation and Incentive models are simulation
tuning parameters that configure topic emphasis and conversational focus.
They are NOT scientifically validated psychological or psychometric scores.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class PersonaProfile(BaseModel):
    """Core biographical, organizational, and stylistic profile of a simulated stakeholder."""
    role: str = Field(..., description="Canonical role identifier, e.g., 'CTO', 'CFO', 'SALES_MANAGER'")
    title: str = Field(..., description="Formal corporate job title, e.g., 'Chief Technology Officer'")
    department: str = Field(..., description="Department or business unit, e.g., 'Engineering', 'Finance'")
    seniority: str = Field(..., description="Organizational seniority level, e.g., 'Executive', 'Senior Management'")
    years_of_experience: int = Field(..., ge=0, description="Total professional career experience in years")
    industry_expertise: List[str] = Field(default_factory=list, description="Domains/sectors of deep familiarity")
    technical_depth: str = Field(..., description="Level of technical fluency, e.g., 'Deep Architectural', 'Strategic High-Level', 'Non-Technical'")
    communication_style: str = Field(..., description="Verbal demeanor, e.g., 'Direct, terse, skeptical'")
    personality_characteristics: List[str] = Field(default_factory=list, description="Key behavioral traits, e.g., ['Analytical', 'Pragmatic']")
    risk_profile: str = Field(..., description="Stance toward risk, e.g., 'Risk-Averse', 'Calculated Risk-Taker', 'Innovation-First'")

    @field_validator("role", "title", "department", "seniority")
    @classmethod
    def validate_non_empty_string(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace only.")
        return v.strip()


class ValueOrientation(BaseModel):
    """Structured organizational/professional value guiding simulated stakeholder decisions.

    CRITICAL NOTE:
    'weight' is an internal simulation parameter (0.0 to 1.0) defining how strongly
    this persona prioritizes this dimension during conversation. It is NOT a
    psychometric diagnostic score.
    """
    name: str = Field(..., description="Name of the value, e.g., 'security', 'cost', 'reliability'")
    weight: float = Field(..., ge=0.0, le=1.0, description="Simulation weight between 0.0 and 1.0")
    description: str = Field(..., description="Explanation of how the persona prioritizes this value")
    priority: int = Field(..., ge=1, description="Relative rank order (1 = highest priority)")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Value name cannot be empty.")
        return v.strip().lower()


class StakeholderGoal(BaseModel):
    """Discrete objective or evaluation criterion held by the stakeholder."""
    id: str = Field(..., description="Unique programmatic goal identifier, e.g., 'verify_integration_safety'")
    description: str = Field(..., description="What the stakeholder wants to accomplish or evaluate")
    priority: float = Field(..., ge=0.0, le=1.0, description="Relative priority weight of this goal")
    type: Literal["business", "technical", "financial", "risk", "political", "personal", "procurement"] = Field(
        ..., description="Category of the goal"
    )
    success_condition: str = Field(..., description="Condition required for this stakeholder to consider the goal satisfied")
    dealbreaker: bool = Field(default=False, description="Whether failure to satisfy this goal halts the deal/interview")
    required_information: List[str] = Field(default_factory=list, description="Specific metrics, proof points, or artifacts required")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Goal id cannot be empty.")
        return clean


class Incentive(BaseModel):
    """Personal, organizational, or political incentive influencing stakeholder behavior."""
    id: str = Field(..., description="Unique incentive identifier, e.g., 'avoid_deployment_downtime'")
    description: str = Field(..., description="Description of the incentive and why it matters to the persona")
    importance: float = Field(..., ge=0.0, le=1.0, description="Weight/importance of this incentive in simulation")
    category: Literal["organizational", "personal", "political"] = Field(
        ..., description="Category of stakeholder incentive"
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Incentive id cannot be empty.")
        return clean


class KnowledgeBoundary(BaseModel):
    """Explicit epistemic boundaries defining what the simulated persona knows, does not know, or will not disclose.

    Prevents unrealistic omniscient LLM hallucinations or off-role expertise.
    """
    expert_topics: List[str] = Field(default_factory=list, description="Topics where persona possesses deep, authoritative expertise")
    known_topics: List[str] = Field(default_factory=list, description="Topics persona understands at a competent operational level")
    limited_topics: List[str] = Field(default_factory=list, description="Topics persona has only high-level or secondhand awareness of")
    unknown_topics: List[str] = Field(default_factory=list, description="Topics explicitly out-of-scope or unknown to this persona")
    confidential_topics: List[str] = Field(default_factory=list, description="Topics persona knows but will not disclose without high trust or authorization")
    disclosure_rules: List[str] = Field(default_factory=list, description="Rules governing when confidential information can be shared")


class CompanyContext(BaseModel):
    """World Model representing the external operating environment of the enterprise."""
    company_name: Optional[str] = Field("Enterprise Global", description="Company or organization name")
    industry: str = Field(..., description="Industry sector, e.g., 'Enterprise FinTech'")
    company_size: str = Field(..., description="Company size scale, e.g., '5,000+ employees (Enterprise)'")
    company_stage: Optional[str] = Field(None, description="Stage, e.g., 'Public Enterprise', 'Series C', 'Mature'")
    approximate_revenue_band: Optional[str] = Field(None, description="Revenue range, e.g., '$500M - $1B ARR'")
    current_technology_stack: List[str] = Field(default_factory=list, description="Current primary tools, clouds, architectures")
    incumbent_vendors: List[str] = Field(default_factory=list, description="Existing software/vendors in place")
    business_priorities: List[str] = Field(default_factory=list, description="Top strategic corporate goals for the current fiscal year")
    pain_points: List[str] = Field(default_factory=list, description="Existing operational, technical, or cost problems")
    constraints: List[str] = Field(default_factory=list, description="Hard constraints, e.g., SOC2, On-premises requirement")
    budget_constraints: Optional[str] = Field(None, description="Budget posture, e.g., 'Capped at $150k OpEx'")
    timeline: Optional[str] = Field(None, description="Project or decision timeline, e.g., 'Q3 procurement cycle'")
    regulatory_environment: Optional[str] = Field(None, description="Governing compliance frameworks, e.g., 'HIPAA, GDPR, PCI-DSS'")
    organizational_structure: Optional[str] = Field(None, description="Structure, e.g., 'Decentralized engineering with centralized security'")
    relevant_stakeholders: List[str] = Field(default_factory=list, description="Other stakeholders involved in evaluation, e.g., ['CFO', 'VP Eng']")
    internal_politics: Optional[str] = Field(None, description="Political tensions or dynamics, e.g., 'Friction between Product and Security'")
    current_initiative: Optional[str] = Field(None, description="Active corporate project name, e.g., 'Cloud Migration 2026'")


class EnterprisePersona(BaseModel):
    """Top-level simulation model composing a stakeholder persona and their environment."""
    profile: PersonaProfile = Field(..., description="Biographical and stylistic profile")
    values: List[ValueOrientation] = Field(default_factory=list, description="Ranked simulation values")
    goals: List[StakeholderGoal] = Field(default_factory=list, description="Evaluation goals and dealbreakers")
    incentives: List[Incentive] = Field(default_factory=list, description="Organizational, personal, and political incentives")
    knowledge_boundary: KnowledgeBoundary = Field(default_factory=KnowledgeBoundary, description="Epistemic limits")
    world_model: Optional[CompanyContext] = Field(None, description="Company and scenario environment")

    @field_validator("values")
    @classmethod
    def validate_unique_value_names(cls, values: List[ValueOrientation]) -> List[ValueOrientation]:
        seen = set()
        for v in values:
            lowered = v.name.strip().lower()
            if lowered in seen:
                raise ValueError(f"Duplicate ValueOrientation name '{v.name}' is not permitted.")
            seen.add(lowered)
        return values

    @field_validator("goals")
    @classmethod
    def validate_unique_goal_ids(cls, goals: List[StakeholderGoal]) -> List[StakeholderGoal]:
        seen = set()
        for g in goals:
            clean_id = g.id.strip()
            if clean_id in seen:
                raise ValueError(f"Duplicate StakeholderGoal id '{g.id}' is not permitted.")
            seen.add(clean_id)
        return goals

    @field_validator("incentives")
    @classmethod
    def validate_unique_incentive_ids(cls, incentives: List[Incentive]) -> List[Incentive]:
        seen = set()
        for inc in incentives:
            clean_id = inc.id.strip()
            if clean_id in seen:
                raise ValueError(f"Duplicate Incentive id '{inc.id}' is not permitted.")
            seen.add(clean_id)
        return incentives
