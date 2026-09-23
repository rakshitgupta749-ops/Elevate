"""Candidate Behavior & Content Analyzer Service (Phase 5).

Converts natural-language salesperson speech into structured, inspectable semantic classifications,
verifiable candidate facts, and subjective candidate claims.

Architectural Separation:
- Answers strictly: "What did the salesperson actually do in this turn?"
- Does NOT decide stakeholder behavior (reserved for Phase 6 Behavioral Policy Engine).
- Does NOT alter ClientState directly (feeds deterministic signals into ClientStateManager).
- Does NOT receive hidden stakeholder profile or private ClientState (strictly prevents data leakage).
"""

import os
import json
import time
import logging
from typing import List, Optional, Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from app.models.analysis import (
    CandidateTurnAnalysis,
    CandidateFact,
    CandidateClaim,
    SemanticClassificationEvidence,
    CommunicationStyleAnalysis,
    SalesBehaviorAnalysis,
    ResponseQualityAnalysis,
    BusinessUnderstandingAnalysis,
    TechnicalBehaviorAnalysis,
    CommercialBehaviorAnalysis,
    FactStatus,
)
from app.models.state import InteractionSignal

logger = logging.getLogger("elevate.candidate_analyzer")


def get_analyzer_llm() -> ChatOpenAI:
    """Instantiate a dedicated, deterministic LLM instance for semantic analysis."""
    import httpx
    client = httpx.Client(verify=False)
    return ChatOpenAI(
        base_url="https://genailab.tcs.in",
        model="azure/genailab-maas-gpt-4o-mini",
        api_key=os.getenv("TCS_API_KEY"),
        http_client=client,
        temperature=0.0,
    )


ANALYZER_SYSTEM_PROMPT = """You are an expert Enterprise Sales Conversation Analyst.
Your role is to strictly analyze what the salesperson communicated in their latest message.

TASK:
Classify the candidate's communication style, sales technique, response quality, business/technical/commercial indicators, and extract any concrete facts or subjective claims.

CRITICAL GUIDELINES:
1. Objectivity: Classify what was ACTUALLY said. Do not assume or hallucinate unstated intentions.
2. Facts vs Claims:
   - Verifiable, objective disclosures (e.g. current vendor, timeline, observed problem) -> Extracted Facts.
   - Assertions, guarantees, or performance claims (e.g. 'we guarantee 99.99%', 'reduced costs by 40%') -> Extracted Claims.
3. Evidence & Confidence: For key classifications, extract concise supporting evidence quotes and assign confidence [0.0 to 1.0].
4. Multiple Signals: The salesperson may perform multiple actions in one turn (e.g. answer a question AND ask a discovery question AND make a claim). Flag all that apply.

Return ONLY a valid, raw JSON object strictly adhering to the specified schema. Do not enclose in markdown codeblocks or prepend any text."""


class CandidateBehaviorAnalyzer:
    """Performs semantic candidate behavior classification and information extraction."""

    def __init__(self, llm: Optional[Any] = None):
        self.llm = llm

    def _get_llm(self):
        if self.llm is None:
            self.llm = get_analyzer_llm()
        return self.llm

    def analyze(
        self,
        candidate_message: str,
        current_stage: str,
        turn: int,
        recent_context: Optional[str] = None,
        known_facts: Optional[List[Dict[str, Any]]] = None,
    ) -> CandidateTurnAnalysis:
        """Analyze a single candidate turn and return structured CandidateTurnAnalysis.

        Includes latency measurement and resilient fallback on failure.
        """
        start_time = time.time()

        if not candidate_message or not candidate_message.strip():
            return self._create_neutral_analysis(turn=turn, reason="Empty candidate message")

        prompt_payload = self._build_analysis_prompt(
            candidate_message=candidate_message,
            current_stage=current_stage,
            turn=turn,
            recent_context=recent_context,
            known_facts=known_facts,
        )

        # Attempt 1: Invocation with JSON parsing
        try:
            analysis = self._call_llm_and_parse(prompt_payload, turn=turn)
            latency_ms = (time.time() - start_time) * 1000.0
            logger.info(f"CandidateTurnAnalysis turn {turn} succeeded in {latency_ms:.1f}ms")
            return analysis
        except Exception as first_err:
            logger.warning(f"Candidate analysis attempt 1 failed (turn {turn}): {first_err}. Retrying once...")

            # Attempt 2: Strict retry
            try:
                retry_payload = prompt_payload + "\n\nCRITICAL: Return ONLY valid, parseable JSON matching the schema."
                analysis = self._call_llm_and_parse(retry_payload, turn=turn)
                latency_ms = (time.time() - start_time) * 1000.0
                logger.info(f"CandidateTurnAnalysis turn {turn} succeeded on retry in {latency_ms:.1f}ms")
                return analysis
            except Exception as second_err:
                latency_ms = (time.time() - start_time) * 1000.0
                logger.error(f"Candidate analysis failed after retry (turn {turn}) in {latency_ms:.1f}ms: {second_err}. Returning neutral fallback.")
                return self._create_neutral_analysis(turn=turn, reason=f"Analyzer error: {second_err}")

    def _build_analysis_prompt(
        self,
        candidate_message: str,
        current_stage: str,
        turn: int,
        recent_context: Optional[str],
        known_facts: Optional[List[Dict[str, Any]]],
    ) -> str:
        facts_summary = "None"
        if known_facts:
            facts_summary = "; ".join(f"[{f.get('category')}]: {f.get('value')}" for f in known_facts[:5])

        context_str = f"\nRecent Context: {recent_context}" if recent_context else ""

        schema_format = """{
  "turn": """ + str(turn) + """,
  "communication": {
    "clarity": 0.85,
    "conciseness": 0.80,
    "confidence": 0.80,
    "professionalism": 0.90,
    "directness": 0.85
  },
  "sales_behavior": {
    "discovery_question": false,
    "needs_exploration": false,
    "value_proposition": false,
    "feature_dumping": false,
    "objection_handling": false,
    "negotiation": false,
    "closing_attempt": false,
    "next_step_proposal": false
  },
  "response_quality": {
    "answered_question": true,
    "evasive": false,
    "vague": false,
    "contradictory": false,
    "defensive": false,
    "proactive": false,
    "evidence_backed": false,
    "unsupported_claim": false,
    "unprofessional_behavior": false
  },
  "business_understanding": {
    "pain_identified": false,
    "impact_identified": false,
    "decision_criteria_explored": false,
    "business_value_explained": false,
    "roi_discussed": false
  },
  "technical_behavior": {
    "technical_claim": false,
    "technical_evidence": false,
    "architecture_explanation": false,
    "security_discussion": false,
    "scalability_discussion": false,
    "implementation_discussion": false
  },
  "commercial_behavior": {
    "pricing_discussed": false,
    "budget_discussed": false,
    "procurement_discussed": false,
    "timeline_discussed": false,
    "commercial_expectation_defined": false
  },
  "evidence_items": [
    {"criterion": "string", "detected": true, "evidence": "quote", "confidence": 0.9}
  ],
  "extracted_facts": [
    {"id": "fact_1", "category": "pain_point", "value": "description", "confidence": 0.85, "source_turn": """ + str(turn) + """, "evidence": "quote", "status": "OBSERVED"}
  ],
  "extracted_claims": [
    {"id": "claim_1", "topic": "uptime", "claim": "assertion", "evidence_provided": false, "is_quantitative": true, "confidence": 0.9, "source_turn": """ + str(turn) + """, "evidence": "quote"}
  ],
  "summary_observations": "Brief summary",
  "overall_confidence": 0.85,
  "uncertain": false
}"""

        return f"""Current Interview Stage: {current_stage}
Turn Number: {turn}
Known Session Facts: {facts_summary}{context_str}

CANDIDATE MESSAGE TO ANALYZE:
"{candidate_message}"

JSON SCHEMA TEMPLATE TO POPULATE:
{schema_format}"""

    def _call_llm_and_parse(self, prompt_text: str, turn: int) -> CandidateTurnAnalysis:
        llm = self._get_llm()
        messages = [
            SystemMessage(content=ANALYZER_SYSTEM_PROMPT),
            HumanMessage(content=prompt_text),
        ]

        response = llm.invoke(messages)
        content = response.content.strip()

        # Clean potential markdown wrapping ```json ... ```
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        data = json.loads(content)
        data["turn"] = turn

        # Validate with Pydantic model
        return CandidateTurnAnalysis(**data)

    def _create_neutral_analysis(self, turn: int, reason: str = "") -> CandidateTurnAnalysis:
        """Create a safe, neutral analysis that avoids corrupting state machine or client trust."""
        return CandidateTurnAnalysis(
            turn=turn,
            communication=CommunicationStyleAnalysis(
                clarity=0.70,
                conciseness=0.70,
                confidence=0.70,
                professionalism=0.80,
                directness=0.70,
            ),
            sales_behavior=SalesBehaviorAnalysis(),
            response_quality=ResponseQualityAnalysis(
                answered_question=False,
                evasive=False,
                vague=False,
                unsupported_claim=False,
                evidence_backed=False,
                unprofessional_behavior=False,
            ),
            business_understanding=BusinessUnderstandingAnalysis(),
            technical_behavior=TechnicalBehaviorAnalysis(),
            commercial_behavior=CommercialBehaviorAnalysis(),
            evidence_items=[],
            extracted_facts=[],
            extracted_claims=[],
            summary_observations=f"Neutral fallback analysis applied. Reason: {reason}",
            overall_confidence=0.0,
            uncertain=True,
        )


# ==============================================================================
# DETERMINISTIC MAPPING LAYER TO PHASE 3 (ClientState InteractionSignals)
# ==============================================================================

def map_analysis_to_signals(analysis: CandidateTurnAnalysis) -> List[InteractionSignal]:
    """Map semantic CandidateTurnAnalysis deterministically into Phase 3 InteractionSignals.

    Supports multiple simultaneous signals per turn (Section 14).
    The LLM classifies what the candidate did; this deterministic application logic
    decides which signals are emitted to ClientStateManager.
    """
    if analysis.uncertain or analysis.overall_confidence == 0.0:
        return [
            InteractionSignal(
                type="neutral_turn",
                details="Neutral turn due to analyzer uncertainty or failure fallback.",
                reason="No decisive candidate signal extracted from turn.",
            )
        ]

    signals: List[InteractionSignal] = []
    rq = analysis.response_quality
    tb = analysis.technical_behavior
    cb = analysis.commercial_behavior

    # 1. Unsupported Claim
    if rq.unsupported_claim:
        claim_detail = analysis.summary_observations or "Candidate asserted significant claims without empirical evidence."
        signals.append(
            InteractionSignal(
                type="unsupported_claim",
                details=claim_detail,
                reason="Semantic analysis detected unbacked superlative or absolute claims.",
            )
        )

    # 2. Positive Evidence
    if rq.evidence_backed or tb.technical_evidence:
        evidence_detail = "Candidate provided concrete empirical benchmarks, metrics, or architectural validation."
        signals.append(
            InteractionSignal(
                type="positive_evidence",
                details=evidence_detail,
                reason="Semantic analysis verified evidence-backed responses and technical validation.",
            )
        )

    # 3. Question Dodging / Evasiveness / Defensiveness
    if rq.evasive or rq.defensive:
        dodge_detail = "Candidate evaded direct question or exhibited defensive posture under inquiry."
        signals.append(
            InteractionSignal(
                type="candidate_dodges_question",
                details=dodge_detail,
                reason="Semantic analysis detected evasive or defensive posture.",
            )
        )

    # 3b. Unprofessional / Hostile Behavior
    if rq.unprofessional_behavior:
        signals.append(
            InteractionSignal(
                type="unprofessional_behavior",
                details="Candidate acted unprofessionally, inappropriately, or with hostility.",
                reason="Semantic analysis detected highly unprofessional or disrespectful communication.",
            )
        )

    # 4. Vague Response
    if rq.vague and not rq.evasive:
        signals.append(
            InteractionSignal(
                type="vague_response",
                details="Candidate used generic buzzwords without substantive detail.",
                reason="Semantic analysis identified overly vague or surface-level framing.",
            )
        )

    # 5. Price Concession / Commercial Discussion
    if cb.pricing_discussed and analysis.sales_behavior.negotiation:
        signals.append(
            InteractionSignal(
                type="price_concession",
                details="Candidate proposed commercial concessions or flexible pricing structure.",
                reason="Candidate engaged in commercial negotiation and pricing flexibility.",
            )
        )

    # 6. Clear Substantive Answer
    if rq.answered_question and not (rq.vague or rq.evasive or rq.defensive or rq.unsupported_claim or rq.unprofessional_behavior):
        signals.append(
            InteractionSignal(
                type="clear_answer",
                details="Candidate articulated a direct, structured response addressing the prompt.",
                reason="Candidate directly and clearly addressed stakeholder inquiry.",
            )
        )

    # 7. Fallback Neutral Turn if no specific signals were triggered
    if not signals:
        signals.append(
            InteractionSignal(
                type="neutral_turn",
                details="Standard conversational response.",
                reason="Standard conversational exchange without strong negative or positive valence.",
            )
        )

    return signals
