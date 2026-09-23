"""Typed configuration models for Persona & Scenario Builder (Phase 9).

Provides:
- PersonaTraitDefinition: Definition of role-specific configurable traits
- PersonaPreset: Preset configuration templates (Balanced, Strict, Friendly, etc.)
- PersonaConfiguration: Concrete, resolved runtime configuration with schema versioning
- RoleConfigurationSchema: API schema defining available traits and presets for a role
"""

from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class PersonaTraitDefinition(BaseModel):
    """Schema defining a single configurable behavioral trait."""
    id: str = Field(..., description="Unique programmatic trait identifier, e.g. 'skepticism'")
    display_name: str = Field(..., description="Human-readable trait label, e.g. 'Skepticism'")
    description: str = Field(..., description="Short explanation of behavioral consequence")
    category: Literal[
        "communication",
        "interpersonal",
        "evaluation",
        "decision",
        "role_specific"
    ] = Field(..., description="Category of behavioral trait")
    default: float = Field(..., ge=0.0, le=1.0, description="Sensible simulation baseline default (0.0 to 1.0)")
    min_value: float = Field(default=0.0, ge=0.0, description="Minimum allowed normalized value")
    max_value: float = Field(default=1.0, le=1.0, description="Maximum allowed normalized value")
    configurable: bool = Field(default=True, description="Whether this trait is exposed to trainee in UI")
    affects: List[str] = Field(default_factory=list, description="Behavioral dimensions or policy actions affected")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        clean = v.strip().lower()
        if not clean:
            raise ValueError("Trait ID cannot be empty.")
        return clean

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.min_value >= self.max_value:
            raise ValueError(f"min_value ({self.min_value}) must be strictly less than max_value ({self.max_value}).")
        if not (self.min_value <= self.default <= self.max_value):
            raise ValueError(f"default ({self.default}) must be within [{self.min_value}, {self.max_value}].")
        return self


class PersonaPreset(BaseModel):
    """Configuration template modifying role defaults (Balanced, Strict, Friendly, etc.)."""
    id: str = Field(..., description="Unique preset identifier, e.g. 'STRICT', 'FRIENDLY'")
    display_name: str = Field(..., description="Human-readable preset name, e.g. 'Strict / Demanding'")
    description: str = Field(..., description="Narrative description of this behavioral persona preset")
    trait_modifiers: Dict[str, float] = Field(
        default_factory=dict,
        description="Explicit trait values or modifiers applied on top of role defaults",
    )

    @field_validator("id")
    @classmethod
    def validate_preset_id(cls, v: str) -> str:
        clean = v.strip().upper()
        if not clean:
            raise ValueError("Preset ID cannot be empty.")
        return clean


class PersonaConfiguration(BaseModel):
    """Concrete, validated persona configuration applied to a simulation session."""
    role: str = Field(..., description="Target stakeholder role, e.g. 'CTO', 'CFO'")
    preset: Optional[str] = Field(default="BALANCED", description="Preset identifier if derived from preset")
    traits: Dict[str, float] = Field(
        default_factory=dict,
        description="Resolved map of trait IDs to normalized values in [0.0, 1.0]",
    )
    scenario_overrides: Optional[Dict[str, float]] = Field(
        default_factory=dict,
        description="Optional scenario-level trait adjustments",
    )
    persona_schema_version: str = Field(default="1.0", description="Persona schema version for backward compatibility")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        clean = v.strip().upper().replace("-", "_")
        if not clean:
            raise ValueError("Role cannot be empty.")
        return clean

    @field_validator("traits")
    @classmethod
    def validate_traits_range(cls, traits: Dict[str, float]) -> Dict[str, float]:
        """Strictly validate normalized trait values in [0.0, 1.0]. Reject out-of-bounds."""
        validated: Dict[str, float] = {}
        for k, v in traits.items():
            key = k.strip().lower()
            if not isinstance(v, (int, float)):
                raise ValueError(f"Trait '{key}' value must be a float or int, got {type(v).__name__}")
            val = float(v)
            if val < 0.0 or val > 1.0:
                raise ValueError(
                    f"Trait '{key}' value {val} is out of bounds. Must be strictly between 0.0 and 1.0."
                )
            validated[key] = round(val, 4)
        return validated

    def get_trait(self, trait_id: str, default: float = 0.50) -> float:
        """Helper to get a trait value safely with fallback."""
        return self.traits.get(trait_id.strip().lower(), default)


class RoleConfigurationSchema(BaseModel):
    """Read-only schema defining configurable controls and presets for a specific role."""
    role: str = Field(..., description="Role identifier, e.g. 'CTO'")
    display_name: str = Field(..., description="Role title, e.g. 'Chief Technology Officer'")
    description: str = Field(..., description="Summary of role evaluation perspective")
    traits: List[PersonaTraitDefinition] = Field(default_factory=list, description="Role-relevant configurable traits")
    presets: List[PersonaPreset] = Field(default_factory=list, description="Available persona presets for this role")
    default_traits: Dict[str, float] = Field(default_factory=dict, description="Default trait values for this role")
    schema_version: str = Field(default="1.0", description="Schema version")
