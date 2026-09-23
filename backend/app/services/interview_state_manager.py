"""Enterprise Sales Interview State Machine & Transition Engine.

Governs the deterministic conversation stage transitions, criteria tracking,
min/max turn enforcement, and interview lifecycle management for Elevate.

Strict architectural principles:
- The LLM does NOT decide interview stage transitions.
- Application logic deterministically controls progression.
- ClientState (perception) and InterviewState (meeting lifecycle) remain decoupled.
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from app.models.stages import (
    InterviewStage,
    InterviewStatus,
    StageCriterion,
    StageConfig,
    StageTransitionEvent,
    InterviewState,
)
from app.models.state import ClientState
from app.models.analysis import CandidateTurnAnalysis
from app.models.configuration import PersonaConfiguration


DEFAULT_STAGE_CONFIGS: Dict[InterviewStage, StageConfig] = {
    InterviewStage.STAGE_1_OPENING_RAPPORT: StageConfig(
        stage=InterviewStage.STAGE_1_OPENING_RAPPORT,
        name="Opening & Rapport",
        objective="Establish conversational context, understand meeting purpose, and allow candidate introduction.",
        min_turns=1,
        max_turns=3,
        allowed_next_stages=[InterviewStage.STAGE_2_PROBLEM_DISCOVERY],
        criteria=[
            StageCriterion(
                id="rapport_established",
                name="Candidate Introduction & Rapport",
                description="Candidate introduced themselves and established conversational context.",
                stage=InterviewStage.STAGE_1_OPENING_RAPPORT,
                required=True,
            ),
            StageCriterion(
                id="meeting_agenda_acknowledged",
                name="Meeting Agenda Acknowledged",
                description="Candidate stated or acknowledged the purpose and objective of the meeting.",
                stage=InterviewStage.STAGE_1_OPENING_RAPPORT,
                required=False,
            ),
        ],
    ),
    InterviewStage.STAGE_2_PROBLEM_DISCOVERY: StageConfig(
        stage=InterviewStage.STAGE_2_PROBLEM_DISCOVERY,
        name="Problem Discovery",
        objective="Identify core business pain, understand current-state workflows, quantify business impact, and uncover decision criteria.",
        min_turns=3,
        max_turns=8,
        allowed_next_stages=[InterviewStage.STAGE_3_SOLUTION_ALIGNMENT],
        criteria=[
            StageCriterion(
                id="business_pain_identified",
                name="Core Business Pain Identified",
                description="Candidate identified a concrete operational, architectural, or commercial pain point.",
                stage=InterviewStage.STAGE_2_PROBLEM_DISCOVERY,
                required=True,
            ),
            StageCriterion(
                id="current_process_understood",
                name="Current Workflow & Process Understood",
                description="Candidate explored how the stakeholder's organization currently operates.",
                stage=InterviewStage.STAGE_2_PROBLEM_DISCOVERY,
                required=False,
            ),
            StageCriterion(
                id="business_impact_identified",
                name="Business Impact Quantified",
                description="Candidate investigated the cost, latency, or revenue impact of current challenges.",
                stage=InterviewStage.STAGE_2_PROBLEM_DISCOVERY,
                required=False,
            ),
            StageCriterion(
                id="decision_criteria_uncovered",
                name="Decision Criteria Uncovered",
                description="Candidate inquired into key stakeholder decision criteria and constraints.",
                stage=InterviewStage.STAGE_2_PROBLEM_DISCOVERY,
                required=False,
            ),
        ],
    ),
    InterviewStage.STAGE_3_SOLUTION_ALIGNMENT: StageConfig(
        stage=InterviewStage.STAGE_3_SOLUTION_ALIGNMENT,
        name="Solution Alignment",
        objective="Map proposed solution capabilities directly to discovered business pain, establishing technical and business value fit.",
        min_turns=2,
        max_turns=6,
        allowed_next_stages=[InterviewStage.STAGE_4_OBJECTIONS_AND_DEEP_DIVE],
        criteria=[
            StageCriterion(
                id="solution_linked_to_pain",
                name="Solution Linked to Discovered Pain",
                description="Candidate explicitly mapped solution capabilities to the stakeholder's expressed problems.",
                stage=InterviewStage.STAGE_3_SOLUTION_ALIGNMENT,
                required=True,
            ),
            StageCriterion(
                id="technical_fit_established",
                name="Technical & Architectural Fit",
                description="Candidate addressed integration, scalability, or architecture compatibility.",
                stage=InterviewStage.STAGE_3_SOLUTION_ALIGNMENT,
                required=False,
            ),
            StageCriterion(
                id="value_proposition_articulated",
                name="Business Value Proposition",
                description="Candidate clearly articulated tangible business ROI or productivity gains.",
                stage=InterviewStage.STAGE_3_SOLUTION_ALIGNMENT,
                required=False,
            ),
        ],
    ),
    InterviewStage.STAGE_4_OBJECTIONS_AND_DEEP_DIVE: StageConfig(
        stage=InterviewStage.STAGE_4_OBJECTIONS_AND_DEEP_DIVE,
        name="Objections & Deep Dive",
        objective="Probe implementation risks, challenge technical/commercial assumptions, and test candidate credibility under pressure.",
        min_turns=2,
        max_turns=8,
        allowed_next_stages=[InterviewStage.STAGE_5_COMMERCIALS_AND_CLOSING],
        criteria=[
            StageCriterion(
                id="technical_risk_probed",
                name="Technical & Security Risks Probed",
                description="Candidate addressed concerns regarding reliability, downtime, or security.",
                stage=InterviewStage.STAGE_4_OBJECTIONS_AND_DEEP_DIVE,
                required=True,
            ),
            StageCriterion(
                id="implementation_feasibility_addressed",
                name="Implementation Feasibility",
                description="Candidate addressed migration effort, timeline, or staffing requirements.",
                stage=InterviewStage.STAGE_4_OBJECTIONS_AND_DEEP_DIVE,
                required=False,
            ),
            StageCriterion(
                id="objection_defused",
                name="Objection Effectively Defused",
                description="Candidate satisfied stakeholder skepticism or pushback with concrete evidence.",
                stage=InterviewStage.STAGE_4_OBJECTIONS_AND_DEEP_DIVE,
                required=False,
            ),
        ],
    ),
    InterviewStage.STAGE_5_COMMERCIALS_AND_CLOSING: StageConfig(
        stage=InterviewStage.STAGE_5_COMMERCIALS_AND_CLOSING,
        name="Commercials & Closing",
        objective="Discuss commercial models, procurement timeline, decision process, and secure actionable next steps.",
        min_turns=2,
        max_turns=5,
        allowed_next_stages=[],
        criteria=[
            StageCriterion(
                id="commercial_expectations_clarified",
                name="Commercial Model & Pricing",
                description="Candidate outlined licensing model, pricing structure, or pilot scope.",
                stage=InterviewStage.STAGE_5_COMMERCIALS_AND_CLOSING,
                required=True,
            ),
            StageCriterion(
                id="decision_process_clarified",
                name="Procurement & Decision Timeline",
                description="Candidate inquired about purchasing approval steps or target go-live date.",
                stage=InterviewStage.STAGE_5_COMMERCIALS_AND_CLOSING,
                required=False,
            ),
            StageCriterion(
                id="next_steps_agreed",
                name="Actionable Next Steps Agreed",
                description="Candidate proposed concrete follow-up meeting, demo, or technical proof of concept.",
                stage=InterviewStage.STAGE_5_COMMERCIALS_AND_CLOSING,
                required=True,
            ),
        ],
    ),
}


class InterviewStateManager:
    """Manages the interview state machine, turn recording, criteria updates, and deterministic transitions."""

    def __init__(self, stage_configs: Optional[Dict[InterviewStage, StageConfig]] = None):
        self.configs = stage_configs or DEFAULT_STAGE_CONFIGS

    def initialize_state(self, max_total_turns: int = 15) -> InterviewState:
        """Create a fresh initial InterviewState at STAGE_1_OPENING_RAPPORT."""
        all_criteria: Dict[str, StageCriterion] = {}
        for config in self.configs.values():
            for criterion in config.criteria:
                all_criteria[criterion.id] = criterion.model_copy()

        return InterviewState(
            current_stage=InterviewStage.STAGE_1_OPENING_RAPPORT,
            stage_turn_count=0,
            total_turn_count=0,
            max_total_turns=max_total_turns,
            status=InterviewStatus.ACTIVE,
            criteria=all_criteria,
            history=[],
            termination_reason=None,
        )

    def record_turn(self, state: InterviewState) -> None:
        """Increment turn counters for the active stage and total session."""
        state.stage_turn_count += 1
        state.total_turn_count += 1

    def update_criteria_from_analysis(
        self,
        state: InterviewState,
        analysis: CandidateTurnAnalysis,
        high_confidence_threshold: float = 0.80,
        medium_confidence_threshold: float = 0.60,
    ) -> List[str]:
        """Update interview criteria based on semantic CandidateTurnAnalysis (Phase 5).

        Evaluates confidence thresholds:
        - High confidence (>= 0.80): satisfies required and optional criteria.
        - Medium confidence (0.60 to 0.79): records evidence, but does NOT advance required criteria.
        - Low confidence (< 0.60): ignored for criteria progression.
        """
        satisfied_ids: List[str] = []
        turn = analysis.turn
        conf = analysis.overall_confidence

        if analysis.uncertain or conf < medium_confidence_threshold:
            return satisfied_ids

        def try_satisfy(cid: str, detected: bool, evidence_text: str, custom_conf: Optional[float] = None):
            effective_conf = custom_conf if custom_conf is not None else conf
            if not detected or effective_conf < medium_confidence_threshold:
                return

            if cid in state.criteria:
                crit = state.criteria[cid]
                # High confidence required to satisfy mandatory criteria
                if crit.required and effective_conf < high_confidence_threshold:
                    crit.evidence = f"[Medium Confidence: {effective_conf:.2f}] {evidence_text}"
                    return

                if not crit.satisfied:
                    crit.satisfied = True
                    crit.satisfied_at_turn = turn
                    crit.evidence = evidence_text
                    satisfied_ids.append(cid)

        # 1. Process explicit evidence items from analysis
        for ev in analysis.evidence_items:
            try_satisfy(
                cid=ev.criterion,
                detected=ev.detected,
                evidence_text=ev.evidence or f"Semantic evidence detected for {ev.criterion}",
                custom_conf=ev.confidence,
            )

        # 2. Stage-specific semantic indicator mapping
        sb = analysis.sales_behavior
        rq = analysis.response_quality
        bu = analysis.business_understanding
        tb = analysis.technical_behavior
        cb = analysis.commercial_behavior
        comm = analysis.communication

        if state.current_stage == InterviewStage.STAGE_1_OPENING_RAPPORT:
            is_rapport = (comm.professionalism >= 0.70) and (
                sb.discovery_question or sb.needs_exploration or sb.value_proposition or rq.answered_question
            )
            try_satisfy("rapport_established", is_rapport, "Candidate demonstrated professional opening communication")

            is_agenda = bu.decision_criteria_explored or any("agenda" in (e.evidence or "").lower() for e in analysis.evidence_items)
            try_satisfy("meeting_agenda_acknowledged", is_agenda, "Candidate stated or acknowledged meeting agenda")

        elif state.current_stage == InterviewStage.STAGE_2_PROBLEM_DISCOVERY:
            try_satisfy("business_pain_identified", bu.pain_identified, "Candidate identified concrete business pain/bottleneck")

            is_workflow = bu.decision_criteria_explored or tb.architecture_explanation or sb.needs_exploration
            try_satisfy("current_process_understood", is_workflow, "Candidate explored existing organizational workflow")

            is_impact = bu.impact_identified or bu.roi_discussed
            try_satisfy("business_impact_identified", is_impact, "Candidate explored quantified business impact")

            try_satisfy("decision_criteria_uncovered", bu.decision_criteria_explored, "Candidate uncovered decision criteria and constraints")

        elif state.current_stage == InterviewStage.STAGE_3_SOLUTION_ALIGNMENT:
            is_solution_linked = sb.value_proposition and (bu.business_value_explained or bu.pain_identified)
            try_satisfy("solution_linked_to_pain", is_solution_linked, "Candidate mapped solution capabilities to business problems")

            is_tech_fit = tb.technical_claim and (tb.technical_evidence or tb.architecture_explanation or tb.scalability_discussion)
            try_satisfy("technical_fit_established", is_tech_fit, "Candidate demonstrated technical and architectural fit")

            is_val_prop = bu.business_value_explained or bu.roi_discussed or sb.value_proposition
            try_satisfy("value_proposition_articulated", is_val_prop, "Candidate articulated clear business value and ROI")

        elif state.current_stage == InterviewStage.STAGE_4_OBJECTIONS_AND_DEEP_DIVE:
            is_tech_risk = tb.security_discussion or tb.implementation_discussion or sb.objection_handling
            try_satisfy("technical_risk_probed", is_tech_risk, "Candidate probed technical/security risks")

            try_satisfy("implementation_feasibility_addressed", tb.implementation_discussion, "Candidate addressed rollout/migration feasibility")

            is_defused = sb.objection_handling and (rq.evidence_backed or tb.technical_evidence)
            try_satisfy("objection_defused", is_defused, "Candidate defused skepticism with evidence-backed answers")

        elif state.current_stage == InterviewStage.STAGE_5_COMMERCIALS_AND_CLOSING:
            is_commercial = cb.pricing_discussed or cb.commercial_expectation_defined
            try_satisfy("commercial_expectations_clarified", is_commercial, "Candidate clarified pricing structure and commercial model")

            is_procurement = cb.procurement_discussed or cb.timeline_discussed
            try_satisfy("decision_process_clarified", is_procurement, "Candidate clarified procurement and timeline")

            is_closing = sb.next_step_proposal or sb.closing_attempt
            try_satisfy("next_steps_agreed", is_closing, "Candidate proposed concrete next steps or proof of concept")

        return satisfied_ids

    def update_criteria_from_message(
        self,
        state: InterviewState,
        candidate_message: str,
        turn: int,
        explicit_criteria: Optional[List[str]] = None,
    ) -> List[str]:
        """DEPRECATED: Heuristic signal extractor from Phase 4.

        Use update_criteria_from_analysis instead (Phase 5 migration).
        Preserved for backward compatibility with Phase 4 unit tests.
        """
        satisfied_ids: List[str] = []
        msg_lower = candidate_message.lower().strip()

        # Handle explicit programmatic overrides first
        if explicit_criteria:
            for cid in explicit_criteria:
                if cid in state.criteria and not state.criteria[cid].satisfied:
                    state.criteria[cid].satisfied = True
                    state.criteria[cid].satisfied_at_turn = turn
                    state.criteria[cid].evidence = f"Explicit signal at turn {turn}"
                    satisfied_ids.append(cid)

        # Stage 1 Heuristics
        if state.current_stage == InterviewStage.STAGE_1_OPENING_RAPPORT:
            if any(k in msg_lower for k in ["hi", "hello", "thank", "meet", "introduce", "morning", "afternoon", "pleasure", "role", "name is"]):
                cid = "rapport_established"
                if cid in state.criteria and not state.criteria[cid].satisfied:
                    state.criteria[cid].satisfied = True
                    state.criteria[cid].satisfied_at_turn = turn
                    state.criteria[cid].evidence = "Candidate established opening rapport"
                    satisfied_ids.append(cid)
            if any(k in msg_lower for k in ["agenda", "purpose", "goal", "today", "discuss", "explore", "walk through", "talk about"]):
                cid = "meeting_agenda_acknowledged"
                if cid in state.criteria and not state.criteria[cid].satisfied:
                    state.criteria[cid].satisfied = True
                    state.criteria[cid].satisfied_at_turn = turn
                    state.criteria[cid].evidence = "Candidate framed meeting agenda"
                    satisfied_ids.append(cid)

        # Stage 2 Heuristics
        elif state.current_stage == InterviewStage.STAGE_2_PROBLEM_DISCOVERY:
            # Check for business pain exploration
            if any(k in msg_lower for k in ["pain", "challenge", "problem", "bottleneck", "issue", "struggle", "frustrat", "slow", "delay", "failure", "broken"]):
                cid = "business_pain_identified"
                if cid in state.criteria and not state.criteria[cid].satisfied:
                    state.criteria[cid].satisfied = True
                    state.criteria[cid].satisfied_at_turn = turn
                    state.criteria[cid].evidence = "Candidate probed business pain/bottleneck"
                    satisfied_ids.append(cid)
            # Check for current workflow / stack inquiry
            if any(k in msg_lower for k in ["how do you currently", "current stack", "current process", "workflow", "architecture", "existing", "tools", "in place"]):
                cid = "current_process_understood"
                if cid in state.criteria and not state.criteria[cid].satisfied:
                    state.criteria[cid].satisfied = True
                    state.criteria[cid].satisfied_at_turn = turn
                    state.criteria[cid].evidence = "Candidate inquired about current workflow"
                    satisfied_ids.append(cid)
            # Check for business impact
            if any(k in msg_lower for k in ["impact", "cost", "revenue", "loss", "metric", "kpi", "hours", "downtime", "expensive", "spend"]):
                cid = "business_impact_identified"
                if cid in state.criteria and not state.criteria[cid].satisfied:
                    state.criteria[cid].satisfied = True
                    state.criteria[cid].satisfied_at_turn = turn
                    state.criteria[cid].evidence = "Candidate quantified business impact"
                    satisfied_ids.append(cid)
            # Check for decision criteria
            if any(k in msg_lower for k in ["criteria", "decision", "priority", "evaluate", "requirement", "stakeholder", "must have"]):
                cid = "decision_criteria_uncovered"
                if cid in state.criteria and not state.criteria[cid].satisfied:
                    state.criteria[cid].satisfied = True
                    state.criteria[cid].satisfied_at_turn = turn
                    state.criteria[cid].evidence = "Candidate uncovered decision criteria"
                    satisfied_ids.append(cid)

        # Stage 3 Heuristics
        elif state.current_stage == InterviewStage.STAGE_3_SOLUTION_ALIGNMENT:
            # Check for solution linkage
            if any(k in msg_lower for k in ["our solution", "we provide", "platform", "addresses this", "solves", "features", "capabilities", "we help", "automate", "handles"]):
                cid = "solution_linked_to_pain"
                if cid in state.criteria and not state.criteria[cid].satisfied:
                    state.criteria[cid].satisfied = True
                    state.criteria[cid].satisfied_at_turn = turn
                    state.criteria[cid].evidence = "Candidate mapped solution to customer challenge"
                    satisfied_ids.append(cid)
            # Check for technical fit
            if any(k in msg_lower for k in ["integrate", "api", "cloud", "architecture", "scale", "latency", "pipeline", "database", "compatibility"]):
                cid = "technical_fit_established"
                if cid in state.criteria and not state.criteria[cid].satisfied:
                    state.criteria[cid].satisfied = True
                    state.criteria[cid].satisfied_at_turn = turn
                    state.criteria[cid].evidence = "Candidate established technical fit"
                    satisfied_ids.append(cid)
            # Check for value proposition
            if any(k in msg_lower for k in ["roi", "value", "reduce cost", "increase revenue", "save time", "efficiency", "productivity"]):
                cid = "value_proposition_articulated"
                if cid in state.criteria and not state.criteria[cid].satisfied:
                    state.criteria[cid].satisfied = True
                    state.criteria[cid].satisfied_at_turn = turn
                    state.criteria[cid].evidence = "Candidate articulated value proposition"
                    satisfied_ids.append(cid)

        # Stage 4 Heuristics
        elif state.current_stage == InterviewStage.STAGE_4_OBJECTIONS_AND_DEEP_DIVE:
            # Check technical risk
            if any(k in msg_lower for k in ["risk", "security", "encryption", "compliance", "sla", "downtime", "audit", "governance", "privacy", "soc2"]):
                cid = "technical_risk_probed"
                if cid in state.criteria and not state.criteria[cid].satisfied:
                    state.criteria[cid].satisfied = True
                    state.criteria[cid].satisfied_at_turn = turn
                    state.criteria[cid].evidence = "Candidate addressed technical/security risks"
                    satisfied_ids.append(cid)
            # Check implementation feasibility
            if any(k in msg_lower for k in ["migration", "rollout", "training", "timeline", "weeks", "months", "support", "onboarding", "effort"]):
                cid = "implementation_feasibility_addressed"
                if cid in state.criteria and not state.criteria[cid].satisfied:
                    state.criteria[cid].satisfied = True
                    state.criteria[cid].satisfied_at_turn = turn
                    state.criteria[cid].evidence = "Candidate addressed implementation feasibility"
                    satisfied_ids.append(cid)
            # Check objection defusal
            if any(k in msg_lower for k in ["we understand your concern", "to address that", "specifically", "mitigate", "guarantee", "in our experience"]):
                cid = "objection_defused"
                if cid in state.criteria and not state.criteria[cid].satisfied:
                    state.criteria[cid].satisfied = True
                    state.criteria[cid].satisfied_at_turn = turn
                    state.criteria[cid].evidence = "Candidate effectively defused stakeholder objection"
                    satisfied_ids.append(cid)

        # Stage 5 Heuristics
        elif state.current_stage == InterviewStage.STAGE_5_COMMERCIALS_AND_CLOSING:
            # Check commercials
            if any(k in msg_lower for k in ["pricing", "cost", "license", "commercial", "budget", "tier", "subscription", "annual", "pilot"]):
                cid = "commercial_expectations_clarified"
                if cid in state.criteria and not state.criteria[cid].satisfied:
                    state.criteria[cid].satisfied = True
                    state.criteria[cid].satisfied_at_turn = turn
                    state.criteria[cid].evidence = "Candidate clarified commercial structure"
                    satisfied_ids.append(cid)
            # Check decision process
            if any(k in msg_lower for k in ["procurement", "decision", "approval", "timeline", "sign off", "legal", "evaluation process"]):
                cid = "decision_process_clarified"
                if cid in state.criteria and not state.criteria[cid].satisfied:
                    state.criteria[cid].satisfied = True
                    state.criteria[cid].satisfied_at_turn = turn
                    state.criteria[cid].evidence = "Candidate clarified procurement/decision process"
                    satisfied_ids.append(cid)
            # Check next steps
            if any(k in msg_lower for k in ["next step", "schedule", "demo", "follow up", "calendar", "call next week", "poc", "proof of concept", "proposal"]):
                cid = "next_steps_agreed"
                if cid in state.criteria and not state.criteria[cid].satisfied:
                    state.criteria[cid].satisfied = True
                    state.criteria[cid].satisfied_at_turn = turn
                    state.criteria[cid].evidence = "Candidate secured actionable next steps"
                    satisfied_ids.append(cid)

        return satisfied_ids

    def evaluate_stage_transition(
        self,
        state: InterviewState,
        client_state: Optional[ClientState] = None,
        persona_config: Optional[PersonaConfiguration] = None,
    ) -> Optional[StageTransitionEvent]:
        """Evaluate deterministic transition rules and advance stage if criteria are met.

        Rules:
        1. Max Total Turns Cap: If total_turn_count >= max_total_turns -> status = COMPLETED.
        2. Early Termination: If client_state frustration >= 0.95 and patience <= 0.10 -> status = TERMINATED.
        3. Standard Criteria Progression:
           - If stage_turn_count >= min_turns AND all required stage criteria satisfied -> advance to next stage.
        4. Max Stage Timeout Failsafe:
           - If stage_turn_count >= max_turns -> advance to next stage to prevent deadlock.
        """
        if state.status in [InterviewStatus.COMPLETED, InterviewStatus.TERMINATED]:
            return None

        # Rule 1: Max Total Turns Check
        if state.total_turn_count >= state.max_total_turns:
            prev_stage = state.current_stage
            state.status = InterviewStatus.COMPLETED
            event = StageTransitionEvent(
                turn=state.total_turn_count,
                from_stage=prev_stage,
                to_stage=prev_stage,
                reason=f"Interview reached maximum total turn limit ({state.max_total_turns}); session completed.",
            )
            state.history.append(event)
            return event

        # Rule 2: Early Termination Check (ClientState Dealbreaker / Extreme Frustration)
        if client_state:
            # Default thresholds
            frustration_threshold = 0.95
            patience_threshold = 0.10
            
            # Dynamic scaling based on persona configuration
            if persona_config:
                strictness = persona_config.get_trait("strictness", 0.50)
                trait_patience = persona_config.get_trait("patience", 0.50)
                
                # A highly strict persona terminates at a lower frustration (e.g., 0.75 instead of 0.95)
                frustration_threshold = max(0.60, 0.95 - (strictness - 0.50) * 0.40)
                # An impatient persona terminates at a higher patience remaining (e.g., 0.30 instead of 0.10)
                patience_threshold = min(0.40, 0.10 + (0.50 - trait_patience) * 0.40)
                
            if client_state.frustration >= frustration_threshold and client_state.patience <= patience_threshold:
                prev_stage = state.current_stage
                state.status = InterviewStatus.TERMINATED
                state.termination_reason = f"Irrecoverable conversational breakdown: stakeholder patience ({client_state.patience:.2f}) exhausted and frustration ({client_state.frustration:.2f}) reached critical ceiling."
                event = StageTransitionEvent(
                    turn=state.total_turn_count,
                    from_stage=prev_stage,
                    to_stage=prev_stage,
                    reason=state.termination_reason,
                )
                state.history.append(event)
                return event

        current_config = self.configs.get(state.current_stage)
        if not current_config:
            return None

        req_satisfied = state.all_required_criteria_satisfied(state.current_stage)
        min_turns_reached = state.stage_turn_count >= current_config.min_turns
        max_turns_reached = state.stage_turn_count >= current_config.max_turns

        # Rule 3: Deterministic Progression (Min Turns + Required Criteria)
        if min_turns_reached and req_satisfied:
            return self._advance_to_next_stage(
                state=state,
                current_config=current_config,
                reason=f"Required criteria satisfied for {current_config.name} and minimum stage turns ({current_config.min_turns}) reached.",
            )

        # Rule 4: Max Stage Turns Failsafe (Stage Timeout)
        if max_turns_reached:
            return self._advance_to_next_stage(
                state=state,
                current_config=current_config,
                reason=f"Maximum stage turn limit ({current_config.max_turns}) reached for {current_config.name}; advancing to next stage.",
            )

        # No transition: remain in current stage
        return None

    def _advance_to_next_stage(
        self,
        state: InterviewState,
        current_config: StageConfig,
        reason: str,
    ) -> StageTransitionEvent:
        """Execute stage transition or session completion."""
        from_stage = state.current_stage

        if not current_config.allowed_next_stages:
            # Final stage completed
            state.status = InterviewStatus.COMPLETED
            event = StageTransitionEvent(
                turn=state.total_turn_count,
                from_stage=from_stage,
                to_stage=from_stage,
                reason=f"{reason} All stages finished; interview completed.",
            )
            state.history.append(event)
            return event

        to_stage = current_config.allowed_next_stages[0]
        state.current_stage = to_stage
        state.stage_turn_count = 0

        event = StageTransitionEvent(
            turn=state.total_turn_count,
            from_stage=from_stage,
            to_stage=to_stage,
            reason=reason,
        )
        state.history.append(event)
        return event
