"""Client State Manager Service for Elevate.

Manages dynamic runtime perception state (ClientState) for the simulated stakeholder.
Provides:
- Deterministic initial-state generation based on persona and conversation style
- Rule-based state transition calculations (StateDelta)
- Epistemic bounds enforcement and clamping [0.0, 1.0]
- Auditable transition event generation (StateEvent)
- Integration with persona risk sensitivities
"""

import re
import logging
from typing import Optional, Tuple, Dict, List
from copy import deepcopy

logger = logging.getLogger("elevate.state_manager")

from app.models.state import ClientState, StateDelta, StateEvent, InteractionSignal, clamp
from app.models.persona import EnterprisePersona
from app.models.configuration import PersonaConfiguration


class ClientStateManager:
    """Calculates and governs state transitions for simulated stakeholder perception."""

    @staticmethod
    def initialize_state(
        persona: Optional[EnterprisePersona] = None,
        style: str = "Professional",
        persona_config: Optional[PersonaConfiguration] = None,
    ) -> ClientState:
        """Deterministic baseline initialization of ClientState.

        Calibrated from persona role, risk profile, conversation style,
        and Phase 9 configured behavioral traits.
        Does NOT rely on stochastic LLM generation.
        """
        # 1. Base default metrics
        trust = 0.50
        skepticism = 0.60
        patience = 0.70
        engagement = 0.65
        interest = 0.50
        perceived_risk = 0.50
        frustration = 0.10
        confidence_in_candidate = 0.45

        # 2. Role-specific calibration
        if persona and persona.profile:
            role = persona.profile.role.upper().replace("-", "_")

            if role == "CTO":
                trust = 0.45
                skepticism = 0.75
                patience = 0.70
                engagement = 0.60
                interest = 0.45
                perceived_risk = 0.65
                confidence_in_candidate = 0.40
            elif role == "CEO":
                trust = 0.50
                skepticism = 0.65
                patience = 0.60
                engagement = 0.70
                interest = 0.55
                perceived_risk = 0.50
                confidence_in_candidate = 0.45
            elif role == "HR":
                trust = 0.60
                skepticism = 0.45
                patience = 0.85
                engagement = 0.75
                interest = 0.60
                perceived_risk = 0.35
                frustration = 0.05
                confidence_in_candidate = 0.50
            elif role == "SALES_MANAGER":
                trust = 0.45
                skepticism = 0.70
                patience = 0.60
                engagement = 0.80
                interest = 0.50
                perceived_risk = 0.55
                frustration = 0.15
                confidence_in_candidate = 0.40
            elif role == "CFO":
                trust = 0.40
                skepticism = 0.80
                patience = 0.60
                engagement = 0.60
                interest = 0.40
                perceived_risk = 0.70
                confidence_in_candidate = 0.35
            elif role == "VP_ENGINEERING":
                trust = 0.50
                skepticism = 0.70
                patience = 0.70
                engagement = 0.65
                interest = 0.50
                perceived_risk = 0.60
                confidence_in_candidate = 0.45

            # Risk-profile adjustment
            risk_profile = persona.profile.risk_profile.lower()
            if "risk-averse" in risk_profile or "conservative" in risk_profile:
                perceived_risk += 0.06
                skepticism += 0.04
            elif "growth" in risk_profile or "aggressive" in risk_profile:
                interest += 0.05
                skepticism -= 0.03

        # 3. Conversation style modifiers
        clean_style = style.lower()
        if "stress" in clean_style or "challenging" in clean_style:
            skepticism += 0.08
            patience -= 0.10
            frustration += 0.05
        elif "friendly" in clean_style:
            trust += 0.08
            skepticism -= 0.08
            patience += 0.08
        elif "executive" in clean_style:
            patience -= 0.05
            engagement += 0.05

        # 4. Phase 9 Configured Trait Calibration (Explicit deterministic influence on initial state)
        if persona_config and persona_config.traits:
            cfg_skepticism = persona_config.get_trait("skepticism", 0.50)
            cfg_patience = persona_config.get_trait("patience", 0.50)
            cfg_risk_aversion = persona_config.get_trait("risk_aversion", 0.50)
            cfg_kindness = persona_config.get_trait("kindness", 0.50)
            cfg_strictness = persona_config.get_trait("strictness", 0.50)

            # Skepticism trait directly calibrates initial skepticism (centered at baseline 0.50)
            skepticism += 0.35 * (cfg_skepticism - 0.50)

            # Patience trait directly calibrates initial patience
            patience += 0.35 * (cfg_patience - 0.50)

            # Risk aversion trait calibrates initial perceived risk
            perceived_risk += 0.30 * (cfg_risk_aversion - 0.50)

            # Kindness and strictness calibrate baseline warmth and initial frustration sensitivity
            trust += 0.15 * (cfg_kindness - 0.50)
            frustration += 0.05 * (cfg_strictness - 0.50) - 0.05 * (cfg_kindness - 0.50)

        return ClientState(
            trust=clamp(trust),
            skepticism=clamp(skepticism),
            patience=clamp(patience),
            engagement=clamp(engagement),
            interest=clamp(interest),
            perceived_risk=clamp(perceived_risk),
            frustration=clamp(frustration),
            confidence_in_candidate=clamp(confidence_in_candidate),
        )

    @staticmethod
    def calculate_delta(
        current_state: ClientState,
        signal: InteractionSignal,
        persona: Optional[EnterprisePersona] = None,
        persona_config: Optional[PersonaConfiguration] = None,
    ) -> StateDelta:
        """Calculate state delta based on explicit interaction signals, persona, and traits."""
        sig_type = signal.type
        reason = signal.reason

        if sig_type == "positive_evidence":
            delta = StateDelta(
                trust=+0.08,
                skepticism=-0.05,
                patience=+0.02,
                engagement=+0.04,
                interest=+0.05,
                perceived_risk=-0.04,
                frustration=-0.03,
                confidence_in_candidate=+0.07,
                reason=reason or "Candidate provided verifiable metrics, architectural rationale, or concrete business evidence.",
            )

        elif sig_type == "unsupported_claim":
            # Risk amplification check: if persona has high risk sensitivity, amplify risk impact
            risk_mult = 1.0
            if persona:
                security_val = next((v.weight for v in persona.values if v.name in ("security", "compliance")), 0.0)
                if security_val >= 0.85 or "risk-averse" in persona.profile.risk_profile.lower():
                    risk_mult = 1.35

            delta = StateDelta(
                trust=-0.08,
                skepticism=+0.10,
                patience=-0.03,
                interest=-0.04,
                perceived_risk=+round(0.08 * risk_mult, 4),
                frustration=+0.04,
                confidence_in_candidate=-0.06,
                reason=reason or f"Candidate made unsubstantiated assertions without supporting evidence (risk factor: {risk_mult:.2f}x).",
            )

        elif sig_type == "candidate_dodges_question":
            delta = StateDelta(
                trust=-0.06,
                skepticism=+0.08,
                patience=-0.07,
                engagement=-0.03,
                interest=-0.05,
                perceived_risk=+0.05,
                frustration=+0.08,
                confidence_in_candidate=-0.05,
                reason=reason or "Candidate evaded or refused to address a direct question.",
            )

        elif sig_type == "clear_answer":
            delta = StateDelta(
                trust=+0.03,
                skepticism=-0.02,
                patience=+0.03,
                engagement=+0.04,
                interest=+0.02,
                perceived_risk=-0.02,
                frustration=-0.02,
                confidence_in_candidate=+0.03,
                reason=reason or "Candidate provided a clear, relevant, structured response.",
            )

        elif sig_type == "vague_response":
            delta = StateDelta(
                trust=-0.04,
                skepticism=+0.06,
                patience=-0.05,
                engagement=-0.02,
                interest=-0.03,
                perceived_risk=+0.03,
                frustration=+0.05,
                confidence_in_candidate=-0.04,
                reason=reason or "Candidate provided superficial or generic response lacking depth.",
            )

        elif sig_type == "price_concession":
            delta = StateDelta(
                trust=-0.02,
                skepticism=+0.04,
                interest=+0.04,
                perceived_risk=+0.02,
                confidence_in_candidate=-0.03,
                reason=reason or "Candidate conceded on commercial pricing prematurely.",
            )

        elif sig_type == "unprofessional_behavior":
            delta = StateDelta(
                trust=-0.25,
                skepticism=+0.20,
                patience=-0.40,
                engagement=-0.20,
                interest=-0.15,
                perceived_risk=+0.25,
                frustration=+0.40,
                confidence_in_candidate=-0.30,
                reason=reason or "Candidate acted unprofessionally or inappropriately.",
            )

        else:  # neutral_turn
            delta = StateDelta(
                patience=-0.01,
                reason=reason or "Routine turn progression with neutral interaction signal.",
            )

        return delta

    @classmethod
    def apply_delta(
        cls,
        current_state: ClientState,
        delta: StateDelta,
        turn: int,
        event_type: str = "interaction_update",
    ) -> Tuple[ClientState, StateEvent]:
        """Apply a StateDelta to ClientState, enforce [0.0, 1.0] bounds, and record a StateEvent."""
        before_dict = current_state.to_dict()

        new_state = ClientState(
            trust=clamp(current_state.trust + delta.trust),
            skepticism=clamp(current_state.skepticism + delta.skepticism),
            patience=clamp(current_state.patience + delta.patience),
            engagement=clamp(current_state.engagement + delta.engagement),
            interest=clamp(current_state.interest + delta.interest),
            perceived_risk=clamp(current_state.perceived_risk + delta.perceived_risk),
            frustration=clamp(current_state.frustration + delta.frustration),
            confidence_in_candidate=clamp(current_state.confidence_in_candidate + delta.confidence_in_candidate),
        )

        event = StateEvent(
            turn=turn,
            event_type=event_type,
            reason=delta.reason,
            before=before_dict,
            delta=delta.to_dict(),
            after=new_state.to_dict(),
        )

        return new_state, event

    @classmethod
    def apply_signal(
        cls,
        current_state: ClientState,
        signal: InteractionSignal,
        turn: int,
        persona: Optional[EnterprisePersona] = None,
    ) -> Tuple[ClientState, StateEvent]:
        """Compute delta from an InteractionSignal and apply it to produce updated state and event."""
        delta = cls.calculate_delta(current_state, signal, persona=persona)
        return cls.apply_delta(current_state, delta, turn=turn, event_type=signal.type)

    @classmethod
    def apply_signals(
        cls,
        current_state: ClientState,
        signals: List[InteractionSignal],
        turn: int,
        persona: Optional[EnterprisePersona] = None,
    ) -> Tuple[ClientState, StateEvent]:
        """Apply multiple simultaneous InteractionSignals cumulatively (Phase 5)."""
        if not signals:
            return current_state, StateEvent(
                turn=turn,
                event_type="neutral_turn",
                reason="No signals applied",
                before=current_state.to_dict(),
                delta={},
                after=current_state.to_dict(),
            )

        working_state = deepcopy(current_state)
        before_snapshot = current_state.to_dict()
        applied_reasons = []
        event_types = []

        for sig in signals:
            delta = cls.calculate_delta(working_state, sig, persona=persona)
            working_state, _ = cls.apply_delta(working_state, delta, turn=turn, event_type=sig.type)
            applied_reasons.append(f"[{sig.type}]: {delta.reason}")
            event_types.append(sig.type)

        composite_reason = " | ".join(applied_reasons)
        composite_type = "+".join(event_types)

        # Calculate composite delta between final and original
        composite_delta = {
            k: round(working_state.to_dict()[k] - before_snapshot[k], 4)
            for k in before_snapshot
        }

        event = StateEvent(
            turn=turn,
            event_type=composite_type,
            reason=composite_reason,
            before=before_snapshot,
            delta=composite_delta,
            after=working_state.to_dict(),
        )
        logger.info(f"[State Manager] Turn {turn} | Signals: {composite_type} | Delta: {composite_delta} | Frustration: {working_state.frustration:.2f}, Patience: {working_state.patience:.2f}")
        return working_state, event


# ==============================================================================
# DEPRECATED INTERACTION SIGNAL PLACEHOLDER
# DEPRECATION NOTICE: This heuristic detector is superseded by CandidateBehaviorAnalyzer
# and map_analysis_to_signals (Phase 5 migration). Preserved solely for backward
# compatibility with legacy Phase 3 unit tests.
# ==============================================================================
def detect_interaction_signal(message: str) -> InteractionSignal:
    """DEPRECATED: Heuristic rule detector from Phase 3.

    Use CandidateBehaviorAnalyzer and map_analysis_to_signals instead.
    """
    clean_msg = message.strip().lower()

    # Evasion / Dodge detection
    evasion_patterns = [
        r"\b(can('?t| not) say|don'?t know|no idea|skip this|next question|can we move on)\b",
        r"\b(not really sure|pass on that|prefer not to answer)\b",
    ]
    for pattern in evasion_patterns:
        if re.search(pattern, clean_msg):
            return InteractionSignal(
                type="candidate_dodges_question",
                details="Detected evasion phrase",
                reason="Candidate expressed inability or refusal to answer directly.",
            )

    # Very brief or non-committal vague responses
    if len(clean_msg) < 15 and clean_msg in ("maybe", "not sure", "depends", "dunno", "it depends", "yes and no", "possibly"):
        return InteractionSignal(
            type="vague_response",
            details=f"Terse response: '{clean_msg}'",
            reason="Candidate gave a non-committal or overly terse response.",
        )

    # Positive evidence detection: presence of quantifiable metrics, architecture components, or concrete facts
    evidence_patterns = [
        r"\b(\d+%\s*|\$\d+|\d+\s*ms|\d+\s*seconds|\d+\s*x|roi|sla|benchmarks?|tested|measured|latency|throughput|reduced by|increased by)\b",
        r"\b(postgresql|kubernetes|kafka|redis|microservices?|caching|failover|redundancy|star method)\b",
    ]
    has_metrics = bool(re.search(evidence_patterns[0], clean_msg))
    has_concrete_tech = bool(re.search(evidence_patterns[1], clean_msg))

    if has_metrics and has_concrete_tech:
        return InteractionSignal(
            type="positive_evidence",
            details="Found metrics and concrete technical details",
            reason="Candidate cited quantifiable results and specific technical architectural choices.",
        )

    # Unsupported claim: broad superlatives without architectural backing
    unsupported_patterns = [
        r"\b(100%|guarantee|zero risk|best in the world|flawless|unlimited|infinitely scalable|no problems ever)\b"
    ]
    if re.search(unsupported_patterns[0], clean_msg) and not has_concrete_tech:
        return InteractionSignal(
            type="unsupported_claim",
            details="Found superlative claims without architectural backing",
            reason="Candidate made absolute or unverified claims without supporting technical data.",
        )

    # Substantial answer without extreme superlatives
    if len(clean_msg) > 50:
        return InteractionSignal(
            type="clear_answer",
            details=f"Structured response of {len(clean_msg)} characters",
            reason="Candidate articulated a structured, thoughtful explanation.",
        )

    return InteractionSignal(
        type="neutral_turn",
        details="Standard conversational response",
        reason="Standard conversational exchange.",
    )
