"""Role-specific behavioral trait schemas, simulation defaults, and presets (Phase 9).

NOTE ON SIMULATION DEFAULTS:
The baseline trait values and presets defined herein are SIMULATION DEFAULTS
designed to calibrate realistic enterprise conversational practice. They are
NOT scientific claims or psychological profiles of real-world individuals in
these corporate positions.
"""

from typing import Dict, List, Optional, Any
from app.models.configuration import (
    PersonaTraitDefinition,
    PersonaPreset,
    PersonaConfiguration,
    RoleConfigurationSchema,
)

# ==============================================================================
# 1. CORE TRAIT DEFINITION CATALOG
# ==============================================================================

CORE_COMMUNICATION_TRAITS: List[PersonaTraitDefinition] = [
    PersonaTraitDefinition(
        id="directness",
        display_name="Directness",
        description="Preference for concise, explicit statements over diplomatic framing",
        category="communication",
        default=0.70,
        affects=["brevity", "direct_questions", "less_padding"],
    ),
    PersonaTraitDefinition(
        id="formality",
        display_name="Formality",
        description="Preference for structured, formal corporate protocol and terminology",
        category="communication",
        default=0.75,
        affects=["professional_tone", "structured_agenda"],
    ),
    PersonaTraitDefinition(
        id="verbosity_preference",
        display_name="Verbosity Preference",
        description="Tendency to elaborate details versus giving terse, focused answers",
        category="communication",
        default=0.45,
        affects=["response_length", "detail_orientation"],
    ),
    PersonaTraitDefinition(
        id="interruption_tendency",
        display_name="Interruption Tendency",
        description="Willingness to cut off unhelpful or evasive answers early",
        category="communication",
        default=0.40,
        affects=["turn_cutoff", "interruption_probability"],
    ),
]

CORE_INTERPERSONAL_TRAITS: List[PersonaTraitDefinition] = [
    PersonaTraitDefinition(
        id="kindness",
        display_name="Kindness & Warmth",
        description="Warmth, encouragement, and supportive phrasing when communicating",
        category="interpersonal",
        default=0.55,
        affects=["objection_cushioning", "confrontation_moderation", "collaborative_tone"],
    ),
    PersonaTraitDefinition(
        id="patience",
        display_name="Patience",
        description="Tolerance for incomplete answers before escalating or cutting off discussion",
        category="interpersonal",
        default=0.65,
        affects=["followup_allowance", "frustration_threshold", "escalation_speed"],
    ),
    PersonaTraitDefinition(
        id="empathy",
        display_name="Empathy",
        description="Attunement to team dynamics, user friction, and emotional factors",
        category="interpersonal",
        default=0.50,
        affects=["human_factors_focus", "change_management_concern"],
    ),
    PersonaTraitDefinition(
        id="aggressiveness",
        display_name="Confrontational Stance",
        description="Tendency to challenge or press vigorously during disagreements",
        category="interpersonal",
        default=0.35,
        affects=["pushback_intensity", "negotiation_pressure"],
    ),
    PersonaTraitDefinition(
        id="openness",
        display_name="Openness to New Ideas",
        description="Receptivity to unfamiliar methodologies and outside solutions",
        category="interpersonal",
        default=0.60,
        affects=["early_dismissal_resistance", "interest_gain_rate"],
    ),
]

CORE_EVALUATION_TRAITS: List[PersonaTraitDefinition] = [
    PersonaTraitDefinition(
        id="strictness",
        display_name="Strictness",
        description="Rigorousness in enforcing standards and rejecting vague responses",
        category="evaluation",
        default=0.70,
        affects=["challenge_frequency", "requirement_threshold", "vague_answer_rejection"],
    ),
    PersonaTraitDefinition(
        id="skepticism",
        display_name="Skepticism",
        description="How readily the stakeholder challenges unsupported or extraordinary claims",
        category="evaluation",
        default=0.75,
        affects=["evidence_demand", "claim_verification", "challenge_intensity"],
    ),
    PersonaTraitDefinition(
        id="evidence_demand",
        display_name="Evidence Demand",
        description="Requirement for quantitative data, reference architectures, or benchmarks",
        category="evaluation",
        default=0.80,
        affects=["proof_requirement", "quantitative_scrutiny"],
    ),
    PersonaTraitDefinition(
        id="challenge_intensity",
        display_name="Challenge Intensity",
        description="Sharpness and directness of counter-arguments and objections",
        category="evaluation",
        default=0.65,
        affects=["objection_sharpness", "counter_question_depth"],
    ),
]

CORE_DECISION_TRAITS: List[PersonaTraitDefinition] = [
    PersonaTraitDefinition(
        id="risk_aversion",
        display_name="Risk Aversion",
        description="Focus on downside protection, failure modes, and operational hazards",
        category="decision",
        default=0.75,
        affects=["perceived_risk", "security_scrutiny", "governance_demand"],
    ),
    PersonaTraitDefinition(
        id="cost_sensitivity",
        display_name="Cost Sensitivity",
        description="Scrutiny of licensing costs, TCO, and budget allocation",
        category="decision",
        default=0.60,
        affects=["pricing_scrutiny", "roi_requirement", "commercial_pushback"],
    ),
    PersonaTraitDefinition(
        id="innovation_bias",
        display_name="Innovation Bias",
        description="Appetite for modern, cutting-edge technology versus proven legacy systems",
        category="decision",
        default=0.65,
        affects=["modernization_interest", "architectural_curiosity"],
    ),
    PersonaTraitDefinition(
        id="urgency",
        display_name="Decision Urgency",
        description="Pressure to make rapid evaluation decisions and move deal stages forward",
        category="decision",
        default=0.55,
        affects=["stage_transition_pacing", "brevity_demand"],
    ),
]


# ==============================================================================
# 2. ROLE-SPECIFIC TRAIT DEFINITIONS
# ==============================================================================

ROLE_TRAIT_DEFINITIONS: Dict[str, List[PersonaTraitDefinition]] = {
    "CTO": [
        PersonaTraitDefinition(
            id="technical_depth",
            display_name="Technical Architecture Depth",
            description="Focus on low-level systems, data pipelines, scalability, and stack design",
            category="role_specific",
            default=0.90,
            affects=["architectural_probing", "deep_technical_questions"],
        ),
        PersonaTraitDefinition(
            id="architecture_focus",
            display_name="System Architecture Focus",
            description="Emphasis on latency, coupling, distributed state, and clean modularity",
            category="role_specific",
            default=0.85,
            affects=["integration_scrutiny", "api_probing"],
        ),
        PersonaTraitDefinition(
            id="security_sensitivity",
            display_name="Security Sensitivity",
            description="Focus on zero-trust, identity, data residency, and SOC2/ISO boundaries",
            category="role_specific",
            default=0.90,
            affects=["compliance_checks", "threat_model_scrutiny"],
        ),
        PersonaTraitDefinition(
            id="risk_aversion",
            display_name="Production Risk Aversion",
            description="Protection against outages, deployment rollbacks, and operational chaos",
            category="decision",
            default=0.80,
            affects=["sla_probing", "failover_inquiries"],
        ),
        PersonaTraitDefinition(
            id="strictness",
            display_name="Technical Strictness",
            description="Zero tolerance for hand-waving or marketing buzzwords in lieu of mechanics",
            category="evaluation",
            default=0.75,
            affects=["buzzword_rejection", "claim_scrutiny"],
        ),
        PersonaTraitDefinition(
            id="skepticism",
            display_name="Skepticism",
            description="Doubt toward unverified benchmarks and high vendor performance claims",
            category="evaluation",
            default=0.75,
            affects=["evidence_demand", "benchmark_inquiry"],
        ),
        PersonaTraitDefinition(
            id="kindness",
            display_name="Kindness & Warmth",
            description="Constructive, collaborative tone even during rigorous technical challenges",
            category="interpersonal",
            default=0.45,
            affects=["challenge_tone", "patience_cushion"],
        ),
        PersonaTraitDefinition(
            id="patience",
            display_name="Technical Patience",
            description="Tolerance for salesperson explaining complex technical nuance",
            category="interpersonal",
            default=0.65,
            affects=["followup_depth", "interruption_rate"],
        ),
        PersonaTraitDefinition(
            id="directness",
            display_name="Directness",
            description="Direct, to-the-point technical questions without corporate fluff",
            category="communication",
            default=0.85,
            affects=["question_directness", "response_conciseness"],
        ),
        PersonaTraitDefinition(
            id="innovation_bias",
            display_name="Innovation Appetite",
            description="Openness to adopt emerging tech (AI, modern clouds) vs battle-tested stacks",
            category="decision",
            default=0.70,
            affects=["emerging_tech_interest", "modernization_openness"],
        ),
    ],

    "CFO": [
        PersonaTraitDefinition(
            id="financial_scrutiny",
            display_name="Financial Scrutiny",
            description="Detailed inspection of cost models, variable charges, and billing traps",
            category="role_specific",
            default=0.95,
            affects=["pricing_inquiry", "fee_audit"],
        ),
        PersonaTraitDefinition(
            id="cost_sensitivity",
            display_name="Cost Sensitivity",
            description="Aggressive push to minimize operational expenditure and license fees",
            category="decision",
            default=0.90,
            affects=["discount_demands", "budget_cap_enforcement"],
        ),
        PersonaTraitDefinition(
            id="roi_focus",
            display_name="ROI & Payback Rigor",
            description="Requirement for quantified return on investment and clear payback timeline",
            category="role_specific",
            default=0.90,
            affects=["payback_horizon_scrutiny", "economic_value_proof"],
        ),
        PersonaTraitDefinition(
            id="risk_aversion",
            display_name="Fiscal Risk Aversion",
            description="Aversion to long-term lock-ins, runaway variable usage, and hidden fees",
            category="decision",
            default=0.85,
            affects=["contract_safeguards", "tco_probing"],
        ),
        PersonaTraitDefinition(
            id="negotiation_pressure",
            display_name="Negotiation Pressure",
            description="Forcefulness in demanding vendor concessions and price cuts",
            category="role_specific",
            default=0.80,
            affects=["discount_leverage", "payment_terms_pressure"],
        ),
        PersonaTraitDefinition(
            id="strictness",
            display_name="Budgetary Strictness",
            description="Refusal to proceed without auditable financial justification",
            category="evaluation",
            default=0.75,
            affects=["commercial_hold", "evidence_requirement"],
        ),
        PersonaTraitDefinition(
            id="kindness",
            display_name="Interpersonal Warmth",
            description="Cordial and respectful manner in commercial negotiations",
            category="interpersonal",
            default=0.50,
            affects=["tone_softening", "diplomatic_pushback"],
        ),
        PersonaTraitDefinition(
            id="directness",
            display_name="Directness",
            description="Blunt transparency regarding budget ceilings and financial dealbreakers",
            category="communication",
            default=0.85,
            affects=["commercial_clarity", "terse_questions"],
        ),
        PersonaTraitDefinition(
            id="patience",
            display_name="Commercial Patience",
            description="Willingness to review multi-phase financial models",
            category="interpersonal",
            default=0.55,
            affects=["followup_allowance"],
        ),
    ],

    "SALES_MANAGER": [
        PersonaTraitDefinition(
            id="revenue_focus",
            display_name="Revenue Acceleration Focus",
            description="Focus on deal closing speed, pipeline conversion, and quota attainment",
            category="role_specific",
            default=0.90,
            affects=["time_to_value_inquiry", "sales_efficiency"],
        ),
        PersonaTraitDefinition(
            id="commercial_pressure",
            display_name="Deal Velocity Pressure",
            description="Impatience with long evaluation cycles; push for immediate execution",
            category="role_specific",
            default=0.80,
            affects=["timeline_scrutiny", "close_plan_inquiries"],
        ),
        PersonaTraitDefinition(
            id="competitive_sensitivity",
            display_name="Competitive Differentiation",
            description="Scrutiny of why candidate is genuinely better than incumbent competitors",
            category="role_specific",
            default=0.85,
            affects=["competitor_comparison", "moat_probing"],
        ),
        PersonaTraitDefinition(
            id="customer_focus",
            display_name="Customer Value Orientation",
            description="Emphasis on real customer adoption, usability, and rep productivity",
            category="role_specific",
            default=0.75,
            affects=["adoption_probing", "enablement_scrutiny"],
        ),
        PersonaTraitDefinition(
            id="strictness",
            display_name="Discovery Strictness",
            description="Rejection of generic pitch decks; demand for tailored value propositions",
            category="evaluation",
            default=0.70,
            affects=["premature_pitch_pushback", "value_prop_scrutiny"],
        ),
        PersonaTraitDefinition(
            id="directness",
            display_name="Directness",
            description="Fast-paced, high-energy, direct conversational cadence",
            category="communication",
            default=0.80,
            affects=["brisk_cadence", "sharp_followups"],
        ),
        PersonaTraitDefinition(
            id="kindness",
            display_name="Rapport & Warmth",
            description="Colleague-to-colleague warmth and sales peer camaraderie",
            category="interpersonal",
            default=0.60,
            affects=["rapport_building", "encouraging_cues"],
        ),
        PersonaTraitDefinition(
            id="patience",
            display_name="Patience",
            description="Tolerance for discovery questions before cutting to the chase",
            category="interpersonal",
            default=0.55,
            affects=["discovery_tolerance"],
        ),
    ],

    "CEO": [
        PersonaTraitDefinition(
            id="strategic_focus",
            display_name="Strategic Enterprise Vision",
            description="Focus on 3-year market position, enterprise valuation, and strategic fit",
            category="role_specific",
            default=0.95,
            affects=["strategic_probing", "macro_vision"],
        ),
        PersonaTraitDefinition(
            id="urgency",
            display_name="Executive Urgency",
            description="Intolerance for slow conversation or tactical micro-details",
            category="decision",
            default=0.85,
            affects=["brevity_demand", "high_level_orientation"],
        ),
        PersonaTraitDefinition(
            id="innovation_bias",
            display_name="Disruptive Innovation Bias",
            description="Appetite to leapfrog competition with bold technological bets",
            category="decision",
            default=0.80,
            affects=["visionary_openness", "transformation_interest"],
        ),
        PersonaTraitDefinition(
            id="business_skepticism",
            display_name="Business Skepticism",
            description="Scrutiny of long-term viability, execution capability, and partner stability",
            category="evaluation",
            default=0.75,
            affects=["viability_checks", "track_record_inquiry"],
        ),
        PersonaTraitDefinition(
            id="risk_tolerance",
            display_name="Calculated Risk Tolerance",
            description="Willingness to take calculated strategic risks for outsized market reward",
            category="decision",
            default=0.70,
            affects=["strategic_risk_appetite"],
        ),
        PersonaTraitDefinition(
            id="directness",
            display_name="Executive Directness",
            description="Concise, bottom-line-first communication without preamble",
            category="communication",
            default=0.90,
            affects=["bottom_line_focus", "concise_turns"],
        ),
        PersonaTraitDefinition(
            id="kindness",
            display_name="Executive Grace",
            description="Professional charisma and executive courtesy",
            category="interpersonal",
            default=0.55,
            affects=["executive_diplomacy"],
        ),
        PersonaTraitDefinition(
            id="strictness",
            display_name="Executive Standards",
            description="High standard for clarity, presentation competence, and executive presence",
            category="evaluation",
            default=0.75,
            affects=["presence_evaluation"],
        ),
        PersonaTraitDefinition(
            id="patience",
            display_name="Executive Patience",
            description="Patience for rambling or unprepared presentations",
            category="interpersonal",
            default=0.45,
            affects=["cutoff_speed", "redirection_frequency"],
        ),
    ],

    "HR": [
        PersonaTraitDefinition(
            id="empathy",
            display_name="Empathy & Cultural Resonance",
            description="Attunement to human factors, team sentiment, and workplace well-being",
            category="interpersonal",
            default=0.90,
            affects=["human_impact_inquiry", "cultural_harmony"],
        ),
        PersonaTraitDefinition(
            id="patience",
            display_name="Active Listening Patience",
            description="High patience to let candidate explain their perspective thoroughly",
            category="interpersonal",
            default=0.85,
            affects=["interruption_resistance", "deep_listening"],
        ),
        PersonaTraitDefinition(
            id="kindness",
            display_name="Warmth & Encouragement",
            description="Supportive, affirming demeanor creating a constructive dialogue atmosphere",
            category="interpersonal",
            default=0.85,
            affects=["positive_reinforcement", "cushioned_feedback"],
        ),
        PersonaTraitDefinition(
            id="people_focus",
            display_name="People & Talent Focus",
            description="Prioritizing team retention, training burden, and change fatigue",
            category="role_specific",
            default=0.90,
            affects=["change_management_scrutiny", "user_burnout_inquiry"],
        ),
        PersonaTraitDefinition(
            id="policy_strictness",
            display_name="Policy & Compliance Strictness",
            description="Rigorous enforcement of organizational policies, DE&I, and ethical conduct",
            category="evaluation",
            default=0.75,
            affects=["compliance_checks", "conduct_scrutiny"],
        ),
        PersonaTraitDefinition(
            id="conflict_sensitivity",
            display_name="Conflict Sensitivity",
            description="Discomfort with aggressive, hyper-adversarial sales tactics",
            category="role_specific",
            default=0.80,
            affects=["adversarial_pushback", "tone_deescalation"],
        ),
        PersonaTraitDefinition(
            id="strictness",
            display_name="Evaluation Strictness",
            description="Fair but structured evaluation against behavioral criteria",
            category="evaluation",
            default=0.60,
            affects=["structured_rubric_adherence"],
        ),
        PersonaTraitDefinition(
            id="directness",
            display_name="Directness",
            description="Diplomatic, constructive feedback rather than blunt confrontation",
            category="communication",
            default=0.55,
            affects=["diplomatic_framing"],
        ),
    ],

    "PROCUREMENT": [
        PersonaTraitDefinition(
            id="price_sensitivity",
            display_name="Price Sensitivity",
            description="Aggressive drive to drive down unit costs and extract volume discounts",
            category="role_specific",
            default=0.95,
            affects=["discount_demands", "margin_compression"],
        ),
        PersonaTraitDefinition(
            id="negotiation_aggressiveness",
            display_name="Negotiation Aggressiveness",
            description="Relentless probing for seller concessions and contractual flexibility",
            category="role_specific",
            default=0.85,
            affects=["hardball_tactics", "concession_requests"],
        ),
        PersonaTraitDefinition(
            id="vendor_skepticism",
            display_name="Vendor Skepticism",
            description="Inherent distrust of initial quote sheets and unvetted vendor promises",
            category="evaluation",
            default=0.85,
            affects=["audit_demands", "quote_dissection"],
        ),
        PersonaTraitDefinition(
            id="contract_strictness",
            display_name="Contract & SLA Strictness",
            description="Strict adherence to enterprise standard terms, indemnities, and penalties",
            category="evaluation",
            default=0.90,
            affects=["legal_clause_scrutiny", "sla_guarantees"],
        ),
        PersonaTraitDefinition(
            id="cost_focus",
            display_name="TCO Scrutiny",
            description="Focus on hidden implementation, training, and support escalators",
            category="role_specific",
            default=0.90,
            affects=["total_cost_breakdown"],
        ),
        PersonaTraitDefinition(
            id="strictness",
            display_name="RFP Strictness",
            description="Strict enforcement of procedural guidelines and RFP submission rules",
            category="evaluation",
            default=0.80,
            affects=["process_adherence"],
        ),
        PersonaTraitDefinition(
            id="directness",
            display_name="Directness",
            description="Blunt, formal negotiation communication without small talk",
            category="communication",
            default=0.85,
            affects=["terse_negotiation"],
        ),
        PersonaTraitDefinition(
            id="kindness",
            display_name="Warmth",
            description="Level of relational warmth during procurement negotiation",
            category="interpersonal",
            default=0.35,
            affects=["businesslike_demeanor"],
        ),
        PersonaTraitDefinition(
            id="patience",
            display_name="Negotiation Patience",
            description="Willingness to engage in extended multi-round commercial discussions",
            category="interpersonal",
            default=0.70,
            affects=["extended_negotiation"],
        ),
    ],
}


# ==============================================================================
# 3. SENSIBLE SIMULATION DEFAULTS PER ROLE
# ==============================================================================

ROLE_SIMULATION_DEFAULTS: Dict[str, Dict[str, float]] = {
    "CTO": {
        "technical_depth": 0.90,
        "architecture_focus": 0.85,
        "security_sensitivity": 0.90,
        "risk_aversion": 0.80,
        "strictness": 0.75,
        "skepticism": 0.75,
        "kindness": 0.45,
        "patience": 0.65,
        "directness": 0.85,
        "innovation_bias": 0.70,
    },
    "CFO": {
        "financial_scrutiny": 0.95,
        "cost_sensitivity": 0.90,
        "roi_focus": 0.90,
        "risk_aversion": 0.85,
        "negotiation_pressure": 0.80,
        "strictness": 0.75,
        "kindness": 0.50,
        "directness": 0.85,
        "patience": 0.55,
    },
    "SALES_MANAGER": {
        "revenue_focus": 0.90,
        "commercial_pressure": 0.80,
        "competitive_sensitivity": 0.85,
        "customer_focus": 0.75,
        "strictness": 0.70,
        "directness": 0.80,
        "kindness": 0.60,
        "patience": 0.55,
    },
    "CEO": {
        "strategic_focus": 0.95,
        "urgency": 0.85,
        "innovation_bias": 0.80,
        "business_skepticism": 0.75,
        "risk_tolerance": 0.70,
        "directness": 0.90,
        "kindness": 0.55,
        "strictness": 0.75,
        "patience": 0.45,
    },
    "HR": {
        "empathy": 0.90,
        "patience": 0.85,
        "kindness": 0.85,
        "people_focus": 0.90,
        "policy_strictness": 0.75,
        "conflict_sensitivity": 0.80,
        "strictness": 0.60,
        "directness": 0.55,
    },
    "PROCUREMENT": {
        "price_sensitivity": 0.95,
        "negotiation_aggressiveness": 0.85,
        "vendor_skepticism": 0.85,
        "contract_strictness": 0.90,
        "cost_focus": 0.90,
        "strictness": 0.80,
        "directness": 0.85,
        "kindness": 0.35,
        "patience": 0.70,
    },
}


# ==============================================================================
# 4. PRESET DEFINITIONS PER ROLE
# ==============================================================================

ROLE_PRESETS: Dict[str, List[PersonaPreset]] = {
    "CTO": [
        PersonaPreset(
            id="BALANCED",
            display_name="Balanced CTO",
            description="Default enterprise engineering executive posture: analytical, pragmatic, and thorough.",
            trait_modifiers={},
        ),
        PersonaPreset(
            id="STRICT",
            display_name="Strict / Demanding",
            description="High skepticism and strictness, low patience for vague answers, demands deep technical evidence.",
            trait_modifiers={
                "strictness": 0.90,
                "skepticism": 0.85,
                "kindness": 0.25,
                "patience": 0.35,
                "directness": 0.90,
                "technical_depth": 0.95,
                "risk_aversion": 0.85,
            },
        ),
        PersonaPreset(
            id="FRIENDLY",
            display_name="Friendly / Mentoring",
            description="Supportive and patient demeanor, but remains technically rigorous on architecture.",
            trait_modifiers={
                "strictness": 0.40,
                "skepticism": 0.40,
                "kindness": 0.85,
                "patience": 0.85,
                "directness": 0.55,
                "technical_depth": 0.85,
                "risk_aversion": 0.60,
            },
        ),
        PersonaPreset(
            id="SKEPTICAL",
            display_name="Highly Skeptical",
            description="Intensely probes every quantitative claim and architecture guarantee; demands proof points.",
            trait_modifiers={
                "skepticism": 0.95,
                "strictness": 0.85,
                "kindness": 0.35,
                "patience": 0.50,
                "risk_aversion": 0.90,
                "technical_depth": 0.90,
            },
        ),
        PersonaPreset(
            id="AGGRESSIVE",
            display_name="Fast-Paced & Aggressive",
            description="Short patience, high directness, cuts to bottom-line tradeoffs immediately.",
            trait_modifiers={
                "directness": 0.95,
                "patience": 0.25,
                "kindness": 0.20,
                "strictness": 0.85,
                "skepticism": 0.80,
            },
        ),
        PersonaPreset(
            id="TECHNICAL",
            display_name="Deep Architecture Specialist",
            description="Maximum technical depth, focuses exclusively on system internals and latency mechanics.",
            trait_modifiers={
                "technical_depth": 1.0,
                "architecture_focus": 0.95,
                "security_sensitivity": 0.90,
                "strictness": 0.80,
                "directness": 0.85,
            },
        ),
    ],

    "CFO": [
        PersonaPreset(
            id="BALANCED",
            display_name="Balanced CFO",
            description="Standard fiscal leadership posture: value-driven, risk-aware, and financially disciplined.",
            trait_modifiers={},
        ),
        PersonaPreset(
            id="STRICT",
            display_name="Strict Auditor",
            description="Demands uncompromising payback justification; questions every line-item expense.",
            trait_modifiers={
                "financial_scrutiny": 0.98,
                "cost_sensitivity": 0.95,
                "strictness": 0.90,
                "kindness": 0.30,
                "patience": 0.40,
                "directness": 0.90,
            },
        ),
        PersonaPreset(
            id="FRIENDLY",
            display_name="Collaborative CFO",
            description="Approachable and constructive; open to mutually beneficial financial partnerships.",
            trait_modifiers={
                "kindness": 0.80,
                "patience": 0.80,
                "strictness": 0.45,
                "cost_sensitivity": 0.70,
                "directness": 0.60,
            },
        ),
        PersonaPreset(
            id="AGGRESSIVE",
            display_name="Hardball Negotiator",
            description="Relentless commercial pressure; insists on steep discounts and concession terms.",
            trait_modifiers={
                "negotiation_pressure": 0.95,
                "cost_sensitivity": 0.98,
                "kindness": 0.25,
                "directness": 0.95,
                "patience": 0.30,
            },
        ),
    ],

    "SALES_MANAGER": [
        PersonaPreset(
            id="BALANCED",
            display_name="Balanced Sales Director",
            description="Pragmatic sales leader balancing revenue goals with rep adoption.",
            trait_modifiers={},
        ),
        PersonaPreset(
            id="STRICT",
            display_name="Strict Pipeline Enforcer",
            description="High expectations for discovery rigor, no patience for boilerplate pitches.",
            trait_modifiers={
                "strictness": 0.90,
                "commercial_pressure": 0.90,
                "kindness": 0.35,
                "patience": 0.35,
                "directness": 0.90,
            },
        ),
        PersonaPreset(
            id="FRIENDLY",
            display_name="Supportive Sales Coach",
            description="Encouraging peer; helps guide salesperson through objection navigation.",
            trait_modifiers={
                "kindness": 0.85,
                "patience": 0.80,
                "strictness": 0.45,
                "directness": 0.60,
            },
        ),
    ],

    "CEO": [
        PersonaPreset(
            id="BALANCED",
            display_name="Balanced Executive",
            description="Standard corporate chief executive: focused on valuation, strategic vision, and growth.",
            trait_modifiers={},
        ),
        PersonaPreset(
            id="EXECUTIVE",
            display_name="Impatient & High Urgency",
            description="Maximum urgency, very low patience for tactical weeds, demands bottom-line impact.",
            trait_modifiers={
                "urgency": 0.95,
                "patience": 0.20,
                "directness": 0.98,
                "strategic_focus": 0.98,
                "kindness": 0.35,
            },
        ),
        PersonaPreset(
            id="FRIENDLY",
            display_name="Visionary Partner",
            description="Inspirational and receptive to forward-thinking transformative enterprise ideas.",
            trait_modifiers={
                "kindness": 0.80,
                "patience": 0.70,
                "innovation_bias": 0.95,
                "directness": 0.70,
            },
        ),
    ],

    "HR": [
        PersonaPreset(
            id="BALANCED",
            display_name="Balanced HR Leader",
            description="People-first, empathetic, and culturally conscious.",
            trait_modifiers={},
        ),
        PersonaPreset(
            id="STRICT",
            display_name="Strict Policy Guardian",
            description="Very high compliance and policy rigor; scrutinizes conduct and DEI alignment.",
            trait_modifiers={
                "policy_strictness": 0.95,
                "strictness": 0.85,
                "patience": 0.60,
                "kindness": 0.50,
            },
        ),
        PersonaPreset(
            id="FRIENDLY",
            display_name="Empathetic Counselor",
            description="Maximum warmth and patience; highly supportive conversational style.",
            trait_modifiers={
                "empathy": 0.98,
                "kindness": 0.95,
                "patience": 0.95,
                "strictness": 0.35,
            },
        ),
    ],

    "PROCUREMENT": [
        PersonaPreset(
            id="BALANCED",
            display_name="Balanced Sourcing Lead",
            description="Standard enterprise procurement: rigorous on terms and pricing.",
            trait_modifiers={},
        ),
        PersonaPreset(
            id="AGGRESSIVE",
            display_name="Aggressive Cost Cutter",
            description="Extreme pricing scrutiny and aggressive demand for contractual concessions.",
            trait_modifiers={
                "price_sensitivity": 1.0,
                "negotiation_aggressiveness": 0.95,
                "kindness": 0.15,
                "directness": 0.95,
                "patience": 0.40,
            },
        ),
    ],
}


# ==============================================================================
# 5. DETERMINISTIC RESOLUTION ENGINE & PRECEDENCE
# ==============================================================================

def get_role_configuration_schema(role_id: str) -> RoleConfigurationSchema:
    """Retrieve the read-only configuration schema for a specific role."""
    canonical_role = role_id.strip().upper().replace("-", "_")
    traits = ROLE_TRAIT_DEFINITIONS.get(canonical_role, ROLE_TRAIT_DEFINITIONS["CTO"])
    presets = ROLE_PRESETS.get(canonical_role, ROLE_PRESETS["CTO"])
    defaults = ROLE_SIMULATION_DEFAULTS.get(canonical_role, ROLE_SIMULATION_DEFAULTS["CTO"])

    display_names = {
        "CTO": "Chief Technology Officer",
        "CFO": "Chief Financial Officer",
        "SALES_MANAGER": "Sales Director",
        "CEO": "Chief Executive Officer",
        "HR": "Human Resources Director",
        "PROCUREMENT": "Head of Procurement",
    }

    descriptions = {
        "CTO": "Evaluates architectural feasibility, production reliability, security, and technical depth.",
        "CFO": "Evaluates financial ROI, Total Cost of Ownership (TCO), budget allocation, and contractual exposure.",
        "SALES_MANAGER": "Evaluates sales cycle velocity, pipeline conversion, competitive edge, and rep adoption.",
        "CEO": "Evaluates strategic enterprise alignment, corporate valuation, transformation impact, and urgency.",
        "HR": "Evaluates team cultural impact, employee enablement, change friction, and compliance.",
        "PROCUREMENT": "Evaluates commercial pricing concessions, RFP terms, SLAs, and contract risk.",
    }

    return RoleConfigurationSchema(
        role=canonical_role,
        display_name=display_names.get(canonical_role, canonical_role),
        description=descriptions.get(canonical_role, "Enterprise simulated stakeholder."),
        traits=traits,
        presets=presets,
        default_traits=defaults,
        schema_version="1.0",
    )


def resolve_persona_configuration(
    role: str,
    preset: Optional[str] = "BALANCED",
    custom_traits: Optional[Dict[str, float]] = None,
    scenario_overrides: Optional[Dict[str, float]] = None,
    schema_version: str = "1.0",
) -> PersonaConfiguration:
    """Deterministic configuration resolution implementing strict precedence:

    Role Defaults
          ↓
    Preset Modifiers (if selected)
          ↓
    Scenario Overrides (if present)
          ↓
    User Custom Configuration (sliders)
          ↓
    Final Clamped [0.0, 1.0] Concrete PersonaConfiguration
    """
    canonical_role = role.strip().upper().replace("-", "_")
    defaults = ROLE_SIMULATION_DEFAULTS.get(canonical_role, ROLE_SIMULATION_DEFAULTS["CTO"]).copy()

    # 1. Start with Role Defaults
    resolved: Dict[str, float] = defaults.copy()

    # 2. Apply Preset Modifiers if a valid preset is specified
    selected_preset = (preset or "BALANCED").strip().upper()
    presets_for_role = ROLE_PRESETS.get(canonical_role, ROLE_PRESETS["CTO"])
    matched_preset = next((p for p in presets_for_role if p.id == selected_preset), None)

    if matched_preset and matched_preset.trait_modifiers:
        for trait_id, mod_val in matched_preset.trait_modifiers.items():
            t_key = trait_id.lower().strip()
            # If modifier is within [0.0, 1.0], treat as explicit replacement
            resolved[t_key] = float(mod_val)

    # 3. Apply Scenario Overrides
    if scenario_overrides:
        for trait_id, override_val in scenario_overrides.items():
            t_key = trait_id.lower().strip()
            if t_key in resolved:
                # Add scenario delta or set value
                resolved[t_key] = float(override_val)

    # 4. Apply User Persona Configuration (highest priority user sliders)
    if custom_traits:
        for trait_id, user_val in custom_traits.items():
            t_key = trait_id.lower().strip()
            if isinstance(user_val, (int, float)):
                resolved[t_key] = float(user_val)

    # 5. Strict bounds check and clamp to [0.0, 1.0]
    final_traits: Dict[str, float] = {}
    for k, v in resolved.items():
        clamped_val = max(0.0, min(1.0, float(v)))
        final_traits[k] = round(clamped_val, 4)

    return PersonaConfiguration(
        role=canonical_role,
        preset=selected_preset,
        traits=final_traits,
        scenario_overrides=scenario_overrides or {},
        persona_schema_version=schema_version,
    )


# ==============================================================================
# 6. DETERMINISTIC PERSONA SUMMARY PREVIEW (FOR UI & DEBUGGING)
# ==============================================================================

def generate_persona_summary(config: PersonaConfiguration) -> str:
    """Generate a clean, deterministic natural-language summary from traits.

    Used exclusively for frontend UI live preview and developer inspection.
    This summary is NOT used as prompt injection.
    """
    role = config.role
    traits = config.traits

    # Extract key normalized dimensions
    strictness = traits.get("strictness", 0.50)
    skepticism = traits.get("skepticism", 0.50)
    kindness = traits.get("kindness", 0.50)
    patience = traits.get("patience", 0.50)
    directness = traits.get("directness", 0.50)
    tech_depth = traits.get("technical_depth", 0.50)
    risk_aversion = traits.get("risk_aversion", 0.50)
    fin_scrutiny = traits.get("financial_scrutiny", 0.50)
    urgency = traits.get("urgency", 0.50)
    empathy = traits.get("empathy", 0.50)

    # Tone descriptor
    if kindness >= 0.75:
        tone_str = "supportive and collegial"
    elif kindness <= 0.30:
        tone_str = "blunt and demanding"
    else:
        tone_str = "pragmatic and professional"

    # Skepticism / Strictness descriptor
    if skepticism >= 0.80 and strictness >= 0.80:
        evaluation_str = "highly skeptical, demanding verifiable proof and zero hand-waving"
    elif skepticism >= 0.80:
        evaluation_str = "vigilantly skeptical toward vendor claims and benchmarks"
    elif strictness >= 0.80:
        evaluation_str = "exacting and thorough, rejecting vague or incomplete answers"
    elif skepticism <= 0.35 and strictness <= 0.40:
        evaluation_str = "open-minded, receptive, and exploratory"
    else:
        evaluation_str = "balanced in scrutiny, requiring standard business justification"

    # Communication style descriptor
    if directness >= 0.80 and patience <= 0.40:
        comm_str = "fast-paced and terse with little patience for conversational padding"
    elif directness >= 0.80:
        comm_str = "direct and explicit in questioning"
    elif patience >= 0.75:
        comm_str = "patient and willing to let you elaborate your points"
    else:
        comm_str = "structured and businesslike in demeanor"

    # Role-specific focus descriptor
    if role == "CTO":
        if tech_depth >= 0.85:
            focus_str = "with deep scrutiny on technical architecture, scalability, and system failure modes."
        else:
            focus_str = "with a focus on engineering governance, delivery risk, and stack compatibility."
    elif role == "CFO":
        if fin_scrutiny >= 0.85:
            focus_str = "with intense scrutiny on total cost of ownership, ROI horizons, and contract liabilities."
        else:
            focus_str = "with a focus on budget compliance and financial predictability."
    elif role == "SALES_MANAGER":
        focus_str = "with an aggressive focus on deal velocity, quota impact, and clear competitive differentiation."
    elif role == "CEO":
        focus_str = "with an executive lens on enterprise strategy, time-to-market urgency, and strategic ROI."
    elif role == "HR":
        focus_str = "with a strong emphasis on team dynamics, cultural impact, empathy, and change management."
    elif role == "PROCUREMENT":
        focus_str = "with relentless focus on pricing discounts, contract strictness, and vendor compliance."
    else:
        focus_str = "with focused enterprise evaluation criteria."

    return f"A {tone_str} {role} who is {evaluation_str}, {comm_str}, {focus_str}"
