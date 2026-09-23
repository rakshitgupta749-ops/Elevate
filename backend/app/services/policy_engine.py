"""Behavioral Policy Engine (Phase 6).

Determines the simulated enterprise stakeholder's next behavioral action:
"Given who this stakeholder is, what they value, what they want, the current interview stage,
what the salesperson just did, and how the stakeholder currently perceives the salesperson —
what should the stakeholder do next?"

Key Design Principles:
1. Deterministic evaluation: Pure Python rule-based priority resolution (<1ms execution).
2. Persona-driven: Operationalizes values, goals, incentives, and knowledge boundaries.
3. State-aware: Modulates action selection and computes action intensity explicitly.
4. Stage-constrained: Enforces stage progression constraints and defaults.
5. Auditable: Produces complete PolicyTrace stored in SQLite for research and debugging.
6. A/B Support: Supports POLICY_MODE = 'rule_based' | 'disabled' for comparative ablation.
"""

import time
import re
from typing import List, Dict, Optional, Tuple, Any
from pydantic import BaseModel, Field

from app.models.persona import EnterprisePersona
from app.models.state import ClientState
from app.models.stages import InterviewState, InterviewStage, InterviewStatus
from app.models.analysis import CandidateTurnAnalysis
from app.models.configuration import PersonaConfiguration
from app.models.behavior import (
    ActionType,
    BehavioralAction,
    PolicyTrace,
    BehavioralDecision,
)


class BehaviorPolicy(BaseModel):
    """Declarative behavioral policy rule definition."""
    id: str = Field(..., description="Unique policy identifier")
    name: str = Field(..., description="Human-readable policy name")
    priority_tier: int = Field(
        ...,
        description="Priority tier: 100=Dealbreaker/Termination, 90=Confidentiality/Safety, 70=Active Goals/Incentives, 50=Candidate Signal Reactions, 10=Stage Default",
    )
    stage_filter: Optional[List[InterviewStage]] = Field(default=None, description="Stages where this policy is active")
    signal_filter: Optional[List[str]] = Field(default=None, description="Signals that trigger this policy")
    state_conditions: Dict[str, Tuple[str, float]] = Field(
        default_factory=dict,
        description="State conditions, e.g. {'skepticism': ('>=', 0.60)}",
    )
    value_affinities: Dict[str, float] = Field(
        default_factory=dict,
        description="Affinities for persona values, e.g. {'security': 0.8, 'cost': 0.5}",
    )
    primary_action_type: ActionType = Field(..., description="Primary action to execute")
    secondary_action_type: Optional[ActionType] = Field(default=None, description="Optional secondary intent")
    default_objective: str = Field(..., description="Conversational objective")
    default_expected_effect: str = Field(..., description="Expected conversational outcome")
    reason_template: str = Field(..., description="Reasoning template for audit trail")


# Standard declarative policy catalog
POLICY_CATALOG: List[BehaviorPolicy] = [
    # Tier 1: Termination & Dealbreakers (Priority 100)
    BehaviorPolicy(
        id="dealbreaker_frustration_termination",
        name="Frustration Termination",
        priority_tier=100,
        state_conditions={"frustration": (">=", 0.95)},
        primary_action_type=ActionType.TERMINATE,
        default_objective="halt_interview_due_to_unproductive_dialogue",
        default_expected_effect="end_interview",
        reason_template="Stakeholder frustration reached critical threshold (>=0.95); terminating interview.",
    ),
    BehaviorPolicy(
        id="dealbreaker_goal_violation",
        name="Dealbreaker Goal Violation",
        priority_tier=95,
        primary_action_type=ActionType.PUSH_BACK,
        secondary_action_type=ActionType.TERMINATE,
        default_objective="enforce_non_negotiable_dealbreaker_requirement",
        default_expected_effect="halt_or_escalate_dealbreaker",
        reason_template="Mandatory dealbreaker requirement violated or evaded under high scrutiny.",
    ),

    # Tier 2: Safety & Confidentiality (Priority 90)
    BehaviorPolicy(
        id="confidential_inquiry_withhold",
        name="Confidential Information Protection",
        priority_tier=90,
        primary_action_type=ActionType.WITHHOLD_INFORMATION,
        secondary_action_type=ActionType.REDIRECT,
        default_objective="protect_confidential_information",
        default_expected_effect="prevent_unauthorized_information_disclosure",
        reason_template="Candidate requested confidential organizational or financial details.",
    ),

    # Tier 3: Critical Unresolved Goals & Incentives (Priority 70)
    BehaviorPolicy(
        id="unresolved_security_goal",
        name="Probe Security and Compliance",
        priority_tier=70,
        value_affinities={"security": 0.90, "risk": 0.80},
        primary_action_type=ActionType.PROBE_SECURITY,
        secondary_action_type=ActionType.REQUEST_EVIDENCE,
        default_objective="verify_enterprise_security_and_compliance",
        default_expected_effect="demand_concrete_security_controls",
        reason_template="Stakeholder prioritizes security compliance and requires verification of candidate technical assertions.",
    ),
    BehaviorPolicy(
        id="unresolved_integration_goal",
        name="Probe Architecture and Integration Feasibility",
        priority_tier=70,
        value_affinities={"reliability": 0.85, "scalability": 0.80},
        primary_action_type=ActionType.PROBE_TECHNICAL_DETAIL,
        secondary_action_type=ActionType.PROBE_IMPLEMENTATION,
        default_objective="evaluate_integration_feasibility_with_existing_stack",
        default_expected_effect="uncover_architectural_friction_and_dependencies",
        reason_template="Stakeholder pursues active architecture goal to confirm safe integration with existing stack.",
    ),
    BehaviorPolicy(
        id="incentive_avoid_incident_probe_risk",
        name="Probe Operational and Implementation Risk",
        priority_tier=70,
        value_affinities={"reliability": 0.90, "risk": 0.85},
        primary_action_type=ActionType.PROBE_RISK,
        secondary_action_type=ActionType.PROBE_IMPLEMENTATION,
        default_objective="minimize_operational_downtime_and_production_risk",
        default_expected_effect="demand_risk_mitigation_and_rollback_plans",
        reason_template="Stakeholder incentive to prevent production incidents prompts deep probing of deployment risk.",
    ),

    # Tier 4: Candidate Behavior Reactions (Priority 50)
    BehaviorPolicy(
        id="unsupported_quantitative_claim",
        name="Challenge Unsupported Quantitative Claim",
        priority_tier=50,
        signal_filter=["unsupported_claim"],
        primary_action_type=ActionType.CHALLENGE_CLAIM,
        secondary_action_type=ActionType.REQUEST_EVIDENCE,
        default_objective="test_quantitative_business_claim",
        default_expected_effect="compel_candidate_to_provide_verifiable_metrics",
        reason_template="Candidate made a quantitative claim without supporting evidence while skepticism is active.",
    ),
    BehaviorPolicy(
        id="unsupported_general_claim",
        name="Request Evidence for Unverified Claim",
        priority_tier=50,
        signal_filter=["unsupported_claim"],
        primary_action_type=ActionType.REQUEST_EVIDENCE,
        secondary_action_type=ActionType.EXPRESS_SKEPTICISM,
        default_objective="request_substantiating_evidence",
        default_expected_effect="increase_evidence_requirement",
        reason_template="Candidate made an unverified assertion; demanding empirical evidence.",
    ),
    BehaviorPolicy(
        id="candidate_dodges_evasive",
        name="Push Back on Evasive Response",
        priority_tier=50,
        signal_filter=["candidate_dodges_question"],
        primary_action_type=ActionType.PUSH_BACK,
        secondary_action_type=ActionType.FOLLOW_UP,
        default_objective="hold_candidate_accountable_to_original_question",
        default_expected_effect="force_direct_response_to_unanswered_inquiry",
        reason_template="Candidate dodged or gave an evasive response to the stakeholder inquiry.",
    ),
    BehaviorPolicy(
        id="premature_pitch_discovery",
        name="Redirect Premature Pitch in Discovery",
        priority_tier=50,
        stage_filter=[InterviewStage.STAGE_2_PROBLEM_DISCOVERY],
        primary_action_type=ActionType.REDIRECT,
        secondary_action_type=ActionType.ASK_QUESTION,
        default_objective="recenter_on_business_pain_and_current_state",
        default_expected_effect="block_premature_pitch_and_redirect_to_problem_scope",
        reason_template="Candidate pitched solutions before uncovering core business pains in Discovery stage.",
    ),
    BehaviorPolicy(
        id="high_evidence_technical",
        name="Acknowledge Evidence and Probe Technical Depth",
        priority_tier=50,
        signal_filter=["positive_evidence"],
        primary_action_type=ActionType.ACKNOWLEDGE_POINT,
        secondary_action_type=ActionType.PROBE_TECHNICAL_DETAIL,
        default_objective="validate_metrics_and_deepen_technical_inquiry",
        default_expected_effect="increase_candidate_credibility_and_advance_discussion",
        reason_template="Candidate provided verifiable quantitative evidence; acknowledging and probing technical implementation.",
    ),
    BehaviorPolicy(
        id="strong_discovery_pain_uncovered",
        name="Reveal Information on Strong Discovery",
        priority_tier=50,
        primary_action_type=ActionType.REVEAL_INFORMATION,
        secondary_action_type=ActionType.EXPRESS_INTEREST,
        default_objective="share_operational_pain_and_collaborate",
        default_expected_effect="advance_mutual_understanding_of_business_impact",
        reason_template="Candidate asked a high-impact discovery question; reciprocating with relevant operational context.",
    ),
    BehaviorPolicy(
        id="vague_response_clarify",
        name="Request Clarification on Vague Response",
        priority_tier=50,
        signal_filter=["vague_response"],
        primary_action_type=ActionType.REQUEST_CLARIFICATION,
        secondary_action_type=ActionType.FOLLOW_UP,
        default_objective="resolve_ambiguity",
        default_expected_effect="obtain_specific_unambiguous_details",
        reason_template="Candidate's explanation was vague or lacked architectural specifics.",
    ),
    BehaviorPolicy(
        id="pricing_objection_commercial",
        name="Challenge Pricing and Commercial Structure",
        priority_tier=50,
        stage_filter=[InterviewStage.STAGE_5_COMMERCIALS_AND_CLOSING],
        value_affinities={"cost": 0.85, "budget": 0.80},
        primary_action_type=ActionType.CHALLENGE_PRICING,
        secondary_action_type=ActionType.PROBE_BUSINESS_VALUE,
        default_objective="scrutinize_total_cost_of_ownership_and_licensing",
        default_expected_effect="negotiate_favorable_terms_and_verify_roi",
        reason_template="Stakeholder actively scrutinizes commercial terms, pricing models, and TCO alignment.",
    ),

    # Tier 5: Stage Default Behaviors (Priority 10)
    BehaviorPolicy(
        id="stage1_default_rapport",
        name="Stage 1 Default: Opening Question",
        priority_tier=10,
        stage_filter=[InterviewStage.STAGE_1_OPENING_RAPPORT],
        primary_action_type=ActionType.ASK_QUESTION,
        secondary_action_type=ActionType.EXPRESS_INTEREST,
        default_objective="establish_meeting_agenda_and_context",
        default_expected_effect="set_collaborative_professional_tone",
        reason_template="Stage 1 Opening: Engaging candidate on meeting purpose and opening context.",
    ),
    BehaviorPolicy(
        id="stage2_default_discovery",
        name="Stage 2 Default: Probe Business Pain",
        priority_tier=10,
        stage_filter=[InterviewStage.STAGE_2_PROBLEM_DISCOVERY],
        primary_action_type=ActionType.ASK_QUESTION,
        secondary_action_type=ActionType.PROBE_BUSINESS_VALUE,
        default_objective="explore_current_pain_points_and_business_impact",
        default_expected_effect="uncover_latent_operational_challenges",
        reason_template="Stage 2 Discovery: Probing candidate on understanding of current operational challenges.",
    ),
    BehaviorPolicy(
        id="stage3_default_alignment",
        name="Stage 3 Default: Probe Technical Alignment",
        priority_tier=10,
        stage_filter=[InterviewStage.STAGE_3_SOLUTION_ALIGNMENT],
        primary_action_type=ActionType.PROBE_TECHNICAL_DETAIL,
        secondary_action_type=ActionType.PROBE_BUSINESS_VALUE,
        default_objective="evaluate_solution_fit_against_specific_needs",
        default_expected_effect="confirm_architectural_and_business_alignment",
        reason_template="Stage 3 Alignment: Testing how candidate's proposed solution maps to identified requirements.",
    ),
    BehaviorPolicy(
        id="stage4_default_objections",
        name="Stage 4 Default: Probe Risk and Objections",
        priority_tier=10,
        stage_filter=[InterviewStage.STAGE_4_OBJECTIONS_AND_DEEP_DIVE],
        primary_action_type=ActionType.PROBE_RISK,
        secondary_action_type=ActionType.REQUEST_EVIDENCE,
        default_objective="stress_test_solution_under_enterprise_constraints",
        default_expected_effect="surface_hidden_risks_and_implementation_hurdles",
        reason_template="Stage 4 Deep Dive: Stress-testing claims and evaluating operational risks under pressure.",
    ),
    BehaviorPolicy(
        id="stage5_default_closing",
        name="Stage 5 Default: Commercials and Next Steps",
        priority_tier=10,
        stage_filter=[InterviewStage.STAGE_5_COMMERCIALS_AND_CLOSING],
        primary_action_type=ActionType.MOVE_FORWARD,
        secondary_action_type=ActionType.CLOSE,
        default_objective="define_clear_next_steps_or_evaluation_milestones",
        default_expected_effect="establish_concrete_actionable_next_steps",
        reason_template="Stage 5 Closing: Defining pilot criteria, evaluation milestones, and next steps.",
    ),
]


class BehavioralPolicyEngine:
    """Deterministic, persona-aware, state-driven policy evaluation engine."""

    def __init__(
        self,
        policies: Optional[List[BehaviorPolicy]] = None,
        policy_mode: str = "rule_based",
    ):
        self.policies = policies or list(POLICY_CATALOG)
        self.policy_mode = policy_mode.lower().strip()

    def evaluate(
        self,
        persona: EnterprisePersona,
        client_state: ClientState,
        interview_state: InterviewState,
        candidate_analysis: Optional[CandidateTurnAnalysis],
        turn: int,
        candidate_message: str = "",
        policy_mode: Optional[str] = None,
        persona_config: Optional[PersonaConfiguration] = None,
    ) -> BehavioralDecision:
        """Evaluate stakeholder next action deterministically based on context and configurable persona traits."""
        start_time = time.time()
        mode = (policy_mode or self.policy_mode).lower().strip()

        # Handle disabled ablation mode
        if mode == "disabled":
            action = BehavioralAction(
                action_type=ActionType.ASK_QUESTION,
                target="General",
                intensity=0.50,
                objective="conversation_continuation",
                trigger="policy_mode_disabled",
                reason="Behavioral policy engine is disabled for baseline comparison.",
                expected_effect="continue_dialogue_without_explicit_policy",
            )
            trace = PolicyTrace(
                turn=turn,
                candidate_signals=[],
                activated_values=[],
                active_goals=[],
                state=client_state.to_dict(),
                stage=interview_state.current_stage.value if isinstance(interview_state.current_stage, InterviewStage) else str(interview_state.current_stage),
                matched_policies=["disabled_passthrough"],
                selected_action=action.action_type.value,
                intensity=0.50,
                reason=action.reason,
                trait_influences={},
                execution_latency_ms=(time.time() - start_time) * 1000.0,
                mode="disabled",
            )
            return BehavioralDecision(
                primary_action=action,
                secondary_action=None,
                intensity=0.50,
                policy_id="disabled_passthrough",
                trace=trace,
                mode="disabled",
            )

        # 1. Inspect Candidate Signals and Attributes
        observed_signals = self._extract_turn_signals(candidate_analysis)
        current_stage = interview_state.current_stage

        # Extract normalized traits if available
        cfg_strictness = persona_config.get_trait("strictness", 0.50) if persona_config else 0.50
        cfg_skepticism = persona_config.get_trait("skepticism", 0.50) if persona_config else 0.50
        cfg_kindness = persona_config.get_trait("kindness", 0.50) if persona_config else 0.50
        cfg_patience = persona_config.get_trait("patience", 0.50) if persona_config else 0.50
        cfg_directness = persona_config.get_trait("directness", 0.50) if persona_config else 0.50

        # 2. Check Confidentiality Boundaries (Tier 2 Safety)
        confidential_probe = self._detect_confidential_inquiry(
            candidate_message=candidate_message,
            analysis=candidate_analysis,
            persona=persona,
        )

        # 3. Collect Candidate Matching Policies
        matched_policies: List[Tuple[BehaviorPolicy, float]] = []

        for policy in self.policies:
            if not self._check_stage_filter(policy, current_stage):
                continue
            if not self._check_state_conditions(policy, client_state):
                continue

            matches = False
            # Check specific policy conditions
            if policy.id == "dealbreaker_frustration_termination":
                if client_state.frustration >= 0.95:
                    matches = True

            elif policy.id == "dealbreaker_goal_violation":
                # If a dealbreaker goal exists and candidate has high evasion or excessive stage turns
                dealbreakers = [g for g in persona.goals if g.dealbreaker]
                if dealbreakers and (client_state.frustration >= 0.85 or (client_state.skepticism >= 0.85 and "candidate_dodges_question" in observed_signals)):
                    matches = True

            elif policy.id == "confidential_inquiry_withhold":
                if confidential_probe is not None:
                    matches = True

            elif policy.id == "unresolved_security_goal":
                security_weight = self._get_persona_value_weight(persona, "security")
                has_security_goal = any("security" in g.id.lower() or "compliance" in g.id.lower() for g in persona.goals)
                is_security_topic = (
                    (candidate_analysis and candidate_analysis.technical_behavior.security_discussion)
                    or "security" in candidate_message.lower()
                    or "compliance" in candidate_message.lower()
                )
                if (has_security_goal or security_weight >= 0.70) and is_security_topic:
                    matches = True

            elif policy.id == "unresolved_integration_goal":
                reliability_weight = self._get_persona_value_weight(persona, "reliability")
                has_integ_goal = any("integration" in g.id.lower() or "architecture" in g.id.lower() for g in persona.goals)
                is_integ_topic = (
                    (candidate_analysis and candidate_analysis.technical_behavior.architecture_explanation)
                    or "integrate" in candidate_message.lower()
                    or "stack" in candidate_message.lower()
                    or "api" in candidate_message.lower()
                )
                has_positive_evidence = "positive_evidence" in observed_signals or (candidate_analysis and candidate_analysis.response_quality.evidence_backed)
                if (has_integ_goal or reliability_weight >= 0.70) and is_integ_topic and not has_positive_evidence:
                    matches = True

            elif policy.id == "incentive_avoid_incident_probe_risk":
                risk_incentive = any("incident" in inc.id.lower() or "downtime" in inc.id.lower() for inc in persona.incentives)
                is_risk_topic = (
                    "downtime" in candidate_message.lower()
                    or "sla" in candidate_message.lower()
                    or "failover" in candidate_message.lower()
                    or (candidate_analysis and candidate_analysis.technical_behavior.implementation_discussion)
                )
                if risk_incentive and is_risk_topic:
                    matches = True

            elif policy.id == "unsupported_quantitative_claim":
                has_unsupported = "unsupported_claim" in observed_signals
                is_quant = False
                if candidate_analysis:
                    is_quant = any(c.is_quantitative for c in candidate_analysis.extracted_claims) or bool(re.search(r"\b\d+([.,]\d+)?%?", candidate_message))
                # High/Standard skepticism triggers evidence request; low skepticism (<0.35) accepts claims without challenge
                if has_unsupported and is_quant and (cfg_skepticism >= 0.35 or not persona_config):
                    matches = True

            elif policy.id == "unsupported_general_claim":
                # High/Standard skepticism triggers challenge; low skepticism (<0.40) is open-minded and lets candidate proceed
                if "unsupported_claim" in observed_signals and (cfg_skepticism >= 0.40 or not persona_config):
                    matches = True

            elif policy.id == "candidate_dodges_evasive":
                if "candidate_dodges_question" in observed_signals or (candidate_analysis and candidate_analysis.response_quality.evasive):
                    matches = True

            elif policy.id == "premature_pitch_discovery":
                if current_stage == InterviewStage.STAGE_2_PROBLEM_DISCOVERY:
                    if candidate_analysis and (candidate_analysis.sales_behavior.value_proposition or candidate_analysis.sales_behavior.closing_attempt):
                        matches = True

            elif policy.id == "high_evidence_technical":
                if "positive_evidence" in observed_signals or (candidate_analysis and candidate_analysis.response_quality.evidence_backed):
                    matches = True

            elif policy.id == "strong_discovery_pain_uncovered":
                if candidate_analysis and (candidate_analysis.sales_behavior.discovery_question or candidate_analysis.business_understanding.pain_identified):
                    # Cooperative response requires baseline trust or non-critical frustration
                    if client_state.frustration < 0.70:
                        matches = True

            elif policy.id == "vague_response_clarify":
                if "vague_response" in observed_signals or (candidate_analysis and candidate_analysis.response_quality.vague):
                    matches = True
                elif cfg_strictness >= 0.80 and candidate_analysis and not candidate_analysis.response_quality.answered_question:
                    matches = True

            elif policy.id == "pricing_objection_commercial":
                is_commercial = (
                    (candidate_analysis and candidate_analysis.commercial_behavior.pricing_discussed)
                    or any(w in candidate_message.lower() for w in ["price", "pricing", "cost", "budget", "license", "discount", "margin", "fee", "tco"])
                )
                if is_commercial:
                    matches = True

            elif policy.priority_tier == 10:
                # Stage default
                if policy.stage_filter and current_stage in policy.stage_filter:
                    matches = True

            if matches:
                # Compute deterministic score: base tier + persona value affinity bonus
                affinity_bonus = 0.0
                for val_name, aff_weight in policy.value_affinities.items():
                    val_weight = self._get_persona_value_weight(persona, val_name)
                    affinity_bonus += val_weight * aff_weight * 5.0

                # Phase 9 Trait scoring modifiers
                trait_bonus = 0.0
                if persona_config:
                    # Challenging / claim verification policies
                    if policy.id in (
                        "unsupported_quantitative_claim",
                        "unsupported_general_claim",
                        "candidate_dodges_evasive",
                        "vague_response_clarify",
                        "premature_pitch_discovery",
                    ):
                        trait_bonus += 25.0 * (cfg_skepticism - 0.50)
                        trait_bonus += 20.0 * (cfg_strictness - 0.50)
                        trait_bonus -= 15.0 * (cfg_kindness - 0.50)
                        trait_bonus -= 15.0 * (cfg_patience - 0.50)

                        # Trait Interaction 1: strictness high (>0.75) + skepticism high (>0.75) -> strong evidence requirement boost
                        if cfg_strictness >= 0.75 and cfg_skepticism >= 0.75 and policy.id in ("unsupported_quantitative_claim", "unsupported_general_claim"):
                            trait_bonus += 15.0

                    # Cooperative / receptive policies
                    elif policy.id in ("high_evidence_technical", "strong_discovery_pain_uncovered"):
                        trait_bonus -= 25.0 * (cfg_skepticism - 0.50)
                        trait_bonus += 25.0 * (cfg_kindness - 0.50)
                        trait_bonus -= 15.0 * (cfg_strictness - 0.50)
                        trait_bonus += 15.0 * (cfg_patience - 0.50)

                    # Commercial policies
                    elif policy.id == "pricing_objection_commercial":
                        cost_sens = persona_config.get_trait("cost_sensitivity", 0.50)
                        trait_bonus += 20.0 * (cost_sens - 0.50)
                        trait_bonus += 15.0 * (cfg_strictness - 0.50)

                score = float(policy.priority_tier * 100) + affinity_bonus + trait_bonus
                matched_policies.append((policy, score))

        if not matched_policies:
            # Fallback to stage default
            fallback_policy = self.policies[-1]
            matched_policies = [(fallback_policy, 1000.0)]

        # 4. Deterministic Conflict Resolution
        matched_policies.sort(key=lambda x: (x[0].priority_tier, x[1], -ord(x[0].id[0])), reverse=True)
        highest_tier = matched_policies[0][0].priority_tier
        tier_candidates = [item for item in matched_policies if item[0].priority_tier == highest_tier]

        tier_candidates.sort(key=lambda x: (x[1], x[0].id), reverse=True)
        winning_policy, winning_score = tier_candidates[0]

        # 5. Determine Target, Reveal, Withhold, and Reason
        target, info_reveal, info_withhold, trigger_str = self._resolve_action_parameters(
            policy=winning_policy,
            candidate_analysis=candidate_analysis,
            candidate_message=candidate_message,
            persona=persona,
            confidential_probe=confidential_probe,
        )

        # 6. Compute State-Aware Action Intensity modulated by Persona Traits
        intensity = self._compute_intensity(
            action_type=winning_policy.primary_action_type,
            client_state=client_state,
            persona=persona,
            persona_config=persona_config,
        )

        reason = winning_policy.reason_template
        if winning_policy.id == "unsupported_quantitative_claim" and target:
            reason = f"Candidate made an unverified quantitative claim regarding {target} while stakeholder skepticism is active ({client_state.skepticism:.2f})."
        elif winning_policy.id == "confidential_inquiry_withhold":
            reason = f"Candidate inquired about confidential topic '{target}'. Stakeholder enforces confidentiality boundaries."
        elif winning_policy.id == "high_evidence_technical" and target:
            reason = f"Candidate supported claim with concrete metrics on {target}; acknowledging point and probing technical feasibility."

        # Trait Interaction 2: High strictness + High kindness -> firm but respectful inquiry
        objective = winning_policy.default_objective
        if persona_config:
            if cfg_strictness >= 0.75 and cfg_kindness >= 0.70 and "CHALLENGE" in winning_policy.primary_action_type.value:
                objective = "firm_but_respectful_inquiry"
                reason = f"{reason} (Expressed with professional courtesy and supportive phrasing)."

        # 7. Construct Primary and Secondary Actions
        primary_action = BehavioralAction(
            action_type=winning_policy.primary_action_type,
            target=target,
            intensity=intensity,
            objective=objective,
            trigger=trigger_str,
            reason=reason,
            required_information=[f"proof_for_{target}"] if "CHALLENGE" in winning_policy.primary_action_type.value or "REQUEST" in winning_policy.primary_action_type.value else [],
            information_to_reveal=info_reveal,
            information_to_withhold=info_withhold,
            expected_effect=winning_policy.default_expected_effect,
        )

        secondary_action = None
        if winning_policy.secondary_action_type:
            sec_intensity = max(0.1, min(0.95, intensity * 0.85))
            secondary_action = BehavioralAction(
                action_type=winning_policy.secondary_action_type,
                target=target,
                intensity=round(sec_intensity, 4),
                objective=f"secondary_{winning_policy.secondary_action_type.value.lower()}",
                trigger="complementary_intent",
                reason=f"Follow-up complementary action to {winning_policy.primary_action_type.value}",
                expected_effect="complementary_inquiry",
            )

        # 8. Compile Auditable Policy Trace with Explicit Inspectable Trait Influences
        activated_values = [
            v.name for v in persona.values
            if v.name.lower() in winning_policy.value_affinities and v.weight >= 0.50
        ]
        active_goals = [g.id for g in persona.goals if g.priority >= 0.70][:3]

        trait_influences: Dict[str, float] = {}
        if persona_config:
            if primary_action.action_type.value in ("CHALLENGE_CLAIM", "REQUEST_EVIDENCE", "PUSH_BACK", "TERMINATE"):
                trait_influences["skepticism"] = round(0.25 * (cfg_skepticism - 0.50), 4)
                trait_influences["strictness"] = round(0.20 * (cfg_strictness - 0.50), 4)
                trait_influences["kindness"] = round(-0.25 * (cfg_kindness - 0.50), 4)
                trait_influences["patience"] = round(-0.15 * (cfg_patience - 0.50), 4)
            elif primary_action.action_type.value in ("ACKNOWLEDGE_POINT", "EXPRESS_INTEREST", "MOVE_FORWARD"):
                trait_influences["kindness"] = round(0.25 * (cfg_kindness - 0.50), 4)
                trait_influences["skepticism"] = round(-0.25 * (cfg_skepticism - 0.50), 4)
                trait_influences["strictness"] = round(-0.20 * (cfg_strictness - 0.50), 4)
            else:
                trait_influences["directness"] = round(0.15 * (cfg_directness - 0.50), 4)
                trait_influences["patience"] = round(0.15 * (cfg_patience - 0.50), 4)

        latency_ms = (time.time() - start_time) * 1000.0

        trace = PolicyTrace(
            turn=turn,
            candidate_signals=observed_signals,
            activated_values=activated_values,
            active_goals=active_goals,
            state={k: round(v, 4) for k, v in client_state.to_dict().items() if isinstance(v, (int, float))},
            stage=current_stage.value if isinstance(current_stage, InterviewStage) else str(current_stage),
            matched_policies=[p[0].id for p in matched_policies],
            selected_action=primary_action.action_type.value,
            secondary_action=secondary_action.action_type.value if secondary_action else None,
            intensity=primary_action.intensity,
            reason=primary_action.reason,
            trait_influences=trait_influences,
            execution_latency_ms=latency_ms,
            mode=mode,
        )

        return BehavioralDecision(
            primary_action=primary_action,
            secondary_action=secondary_action,
            intensity=primary_action.intensity,
            policy_id=winning_policy.id,
            trace=trace,
            mode=mode,
        )

    # Alias for explicit naming
    evaluate_action = evaluate

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _extract_turn_signals(self, analysis: Optional[CandidateTurnAnalysis]) -> List[str]:
        """Extract flat list of semantic signal identifiers from turn analysis."""
        signals: List[str] = []
        if not analysis:
            return signals

        rq = analysis.response_quality
        sb = analysis.sales_behavior
        tb = analysis.technical_behavior
        bu = analysis.business_understanding

        if rq.unsupported_claim:
            signals.append("unsupported_claim")
        if rq.evidence_backed or tb.technical_evidence:
            signals.append("positive_evidence")
        if rq.evasive or rq.defensive or not rq.answered_question:
            signals.append("candidate_dodges_question")
        if rq.vague:
            signals.append("vague_response")
        if sb.discovery_question or sb.needs_exploration:
            signals.append("discovery_question")
        if bu.pain_identified:
            signals.append("pain_identified")
        if sb.value_proposition:
            signals.append("value_proposition")
        return signals

    def _detect_confidential_inquiry(
        self,
        candidate_message: str,
        analysis: Optional[CandidateTurnAnalysis],
        persona: EnterprisePersona,
    ) -> Optional[str]:
        """Check if candidate probed confidential topics defined in KnowledgeBoundary."""
        kb = persona.knowledge_boundary
        msg_lower = candidate_message.lower()

        # Check explicit confidential topics
        for topic in kb.confidential_topics:
            topic_clean = topic.lower().strip()
            if not topic_clean:
                continue
            words = topic_clean.split()
            if topic_clean in msg_lower or (len(words) > 1 and all(w in msg_lower for w in words)):
                return topic_clean

        # Standard confidential heuristics
        confidential_patterns = [
            (r"\b(exact|allocated|approved|total|internal)?\s*(?:approved\s+|allocated\s+)?budget\b", "budget"),
            (r"\b(internal|operating)\s+margin[s]?\b", "operating_margins"),
            (r"\b(unannounced|confidential|internal)\s+(roadmap|feature[s]?)\b", "unannounced_roadmap"),
            (r"\b(competitor|incumbent)\s+contract\s*(?:terms|pricing)?\b", "vendor_contract_terms"),
        ]
        for pattern, topic_label in confidential_patterns:
            if re.search(pattern, msg_lower):
                return topic_label

        return None

    def _check_stage_filter(self, policy: BehaviorPolicy, current_stage: InterviewStage) -> bool:
        if not policy.stage_filter:
            return True
        return current_stage in policy.stage_filter

    def _check_state_conditions(self, policy: BehaviorPolicy, state: ClientState) -> bool:
        for metric, (op, threshold) in policy.state_conditions.items():
            val = getattr(state, metric, None)
            if val is None:
                continue
            if op == ">=" and not (val >= threshold):
                return False
            elif op == "<=" and not (val <= threshold):
                return False
            elif op == ">" and not (val > threshold):
                return False
            elif op == "<" and not (val < threshold):
                return False
        return True

    def _get_persona_value_weight(self, persona: EnterprisePersona, value_name: str) -> float:
        """Lookup simulation weight of a named value in persona."""
        val_name_lower = value_name.lower().strip()
        for v in persona.values:
            if v.name.lower().strip() == val_name_lower:
                return v.weight
        return 0.50

    def _resolve_action_parameters(
        self,
        policy: BehaviorPolicy,
        candidate_analysis: Optional[CandidateTurnAnalysis],
        candidate_message: str,
        persona: EnterprisePersona,
        confidential_probe: Optional[str],
    ) -> Tuple[str, List[str], List[str], str]:
        """Determine target, authorized disclosure, and withheld details."""
        target = ""
        info_reveal: List[str] = []
        info_withhold: List[str] = []
        trigger_str = policy.id

        if policy.id == "confidential_inquiry_withhold":
            target = confidential_probe or "confidential_business_data"
            info_withhold = [target]
            trigger_str = f"confidential_topic_inquiry: {target}"

        elif policy.id in ("unsupported_quantitative_claim", "unsupported_general_claim", "high_evidence_technical"):
            if candidate_analysis and candidate_analysis.extracted_claims:
                claim = candidate_analysis.extracted_claims[0]
                target = claim.topic or "claimed_performance_metric"
            elif "latency" in candidate_message.lower():
                target = "latency"
            elif "roi" in candidate_message.lower() or "cost" in candidate_message.lower():
                target = "ROI"
            elif "security" in candidate_message.lower():
                target = "security"
            else:
                target = "performance_claim"
            trigger_str = f"candidate_claim_evaluation: {target}"

        elif policy.id == "strong_discovery_pain_uncovered":
            target = "operational_pain_points"
            trigger_str = "effective_discovery_question"
            if persona.world_model and persona.world_model.pain_points:
                info_reveal = [persona.world_model.pain_points[0]]

        elif policy.id == "pricing_objection_commercial":
            target = "TCO_and_licensing"
            trigger_str = "commercial_terms_review"

        elif policy.id == "unresolved_security_goal":
            target = "security_compliance"
            trigger_str = "unresolved_security_evaluation_goal"

        elif policy.id == "unresolved_integration_goal":
            target = "architecture_integration"
            trigger_str = "unresolved_integration_evaluation_goal"

        elif policy.id == "premature_pitch_discovery":
            target = "problem_discovery_focus"
            trigger_str = "premature_solution_pitch"

        else:
            target = "interview_progression"
            trigger_str = "stage_governance"

        return target, info_reveal, info_withhold, trigger_str

    def _compute_intensity(
        self,
        action_type: ActionType,
        client_state: ClientState,
        persona: EnterprisePersona,
        persona_config: Optional[PersonaConfiguration] = None,
    ) -> float:
        """Compute explicit action intensity from ClientState, Persona risk, and Persona traits."""
        base_intensity = 0.50

        # Persona risk profile modifier
        risk_mod = 0.0
        if "risk-averse" in persona.profile.risk_profile.lower():
            risk_mod = 0.08
        elif "risk-taker" in persona.profile.risk_profile.lower():
            risk_mod = -0.05

        action_val = action_type.value

        # Phase 9 Trait modifiers on intensity
        trait_mod = 0.0
        if persona_config:
            cfg_strictness = persona_config.get_trait("strictness", 0.50)
            cfg_skepticism = persona_config.get_trait("skepticism", 0.50)
            cfg_kindness = persona_config.get_trait("kindness", 0.50)
            cfg_patience = persona_config.get_trait("patience", 0.50)
            cfg_directness = persona_config.get_trait("directness", 0.50)

            if action_val in (
                "CHALLENGE_CLAIM",
                "REQUEST_EVIDENCE",
                "PUSH_BACK",
                "PROBE_RISK",
                "WITHHOLD_INFORMATION",
                "TERMINATE",
                "INTERRUPT",
                "CHALLENGE_PRICING",
            ):
                trait_mod = (
                    (0.20 * (cfg_strictness - 0.50))
                    + (0.20 * (cfg_skepticism - 0.50))
                    - (0.20 * (cfg_kindness - 0.50))
                )
            elif action_val in (
                "REVEAL_INFORMATION",
                "EXPRESS_INTEREST",
                "ACKNOWLEDGE_POINT",
                "CONCEDE_POINT",
                "MOVE_FORWARD",
                "CLOSE",
            ):
                trait_mod = (
                    (0.20 * (cfg_kindness - 0.50))
                    - (0.15 * (cfg_strictness - 0.50))
                )
            else:
                trait_mod = (
                    (0.15 * (cfg_directness - 0.50))
                    - (0.10 * (cfg_patience - 0.50))
                )

        # Category 1: Challenging / Adversarial / Protective Actions
        if action_val in (
            "CHALLENGE_CLAIM",
            "REQUEST_EVIDENCE",
            "PUSH_BACK",
            "PROBE_RISK",
            "WITHHOLD_INFORMATION",
            "TERMINATE",
            "INTERRUPT",
            "CHALLENGE_PRICING",
        ):
            # Intensity increases with skepticism, frustration, and risk; decreases with trust
            computed = (
                base_intensity
                + (0.35 * client_state.skepticism)
                + (0.30 * client_state.frustration)
                + (0.15 * client_state.perceived_risk)
                - (0.25 * client_state.trust)
                + risk_mod
                + trait_mod
            )

        # Category 2: Cooperative / Receptive Actions
        elif action_val in (
            "REVEAL_INFORMATION",
            "EXPRESS_INTEREST",
            "ACKNOWLEDGE_POINT",
            "CONCEDE_POINT",
            "MOVE_FORWARD",
            "CLOSE",
        ):
            # Intensity increases with trust and interest; decreases with skepticism and frustration
            computed = (
                base_intensity
                + (0.30 * client_state.trust)
                + (0.20 * client_state.interest)
                - (0.25 * client_state.skepticism)
                - (0.25 * client_state.frustration)
                + trait_mod
            )

        # Category 3: Inquiries / Probing Actions
        else:
            # Moderate depth modulated by engagement and skepticism
            computed = (
                base_intensity
                + (0.20 * client_state.engagement)
                + (0.15 * client_state.skepticism)
                - (0.10 * client_state.trust)
                + trait_mod
            )

        # Clamp strictly to [0.05, 0.98]
        return round(max(0.05, min(0.98, computed)), 4)
