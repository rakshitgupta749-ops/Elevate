"""Consolidated Post-Call Evaluation Orchestrator for Elevate.

Unifies:
- Track 1: Deterministic acoustic & delivery telemetry (Talk-to-Listen, Response Latency, Speaking Pace, Interruptions)
- Track 2: Strategic LLM transcript evaluation (Discovery, Objection Handling, Value Proposition, Strengths, Critical Misses, Coaching Quote)
into a unified SalesInterviewScorecard with overall_readiness_score (1-100).
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Literal
from pydantic import BaseModel, Field

from app.services.telemetry import DeliveryScorecard, SessionTelemetry
from app.services.storage_service import storage
from app.models.coaching import StructuredCoachingReport

logger = logging.getLogger("elevate.evaluator")


class StrategicScorecard(BaseModel):
    """Track 2: Strategic LLM Rubric Evaluation on Transcript Text."""
    discovery_score: int = Field(..., ge=0, le=100, description="Needs discovery, active listening, qualification [0-100]")
    objection_handling_score: int = Field(..., ge=0, le=100, description="Defusing skepticism and validating concerns [0-100]")
    value_proposition_score: int = Field(..., ge=0, le=100, description="ROI, business impact, and strategic alignment [0-100]")
    strengths: List[str] = Field(default_factory=list, description="Candidate key strategic strengths")
    critical_misses: List[str] = Field(default_factory=list, description="Critical sales omissions or missteps")
    key_coaching_quote: str = Field("", description="Pivotal candidate quote needing coaching / improvement")


class SalesInterviewScorecard(BaseModel):
    """Consolidated post-call evaluation scorecard merging Track 1 & Track 2."""
    session_id: str
    timestamp: str
    delivery_scorecard: DeliveryScorecard
    strategic_scorecard: StrategicScorecard
    overall_readiness_score: int = Field(..., ge=1, le=100, description="Scaled 1-100 combining delivery + content")


def calculate_delivery_numerical_score(delivery: DeliveryScorecard) -> float:
    """Calculates a normalized 0-100 delivery performance score from deterministic telemetry."""
    score = 100.0

    # Talk-to-listen penalty
    if delivery.talk_ratio_verdict == "Pitch Slapping":
        score -= 25.0
    elif delivery.talk_ratio_verdict == "Under-engaging":
        score -= 25.0

    # Latency penalty
    if delivery.latency_verdict == "Hesitant":
        score -= 20.0
    elif delivery.latency_verdict == "Abrupt":
        score -= 10.0

    # Speaking pace penalty
    if delivery.pace_verdict == "Rushing":
        score -= 15.0
    elif delivery.pace_verdict == "Slow":
        score -= 15.0

    # Interruption penalty (aggressive barge-ins)
    interruption_penalty = min(30.0, delivery.interruption_count * 10.0)
    score -= interruption_penalty

    return max(20.0, min(100.0, score))


def compute_stakeholder_momentum(session_id: str) -> int:
    """
    Computes Stakeholder Perception Momentum (Track 3) by measuring net delta in trust,
    skepticism reduction, and risk mitigation from initial baseline.
    Avoids penalizing candidates for an executive's naturally cautious starting baseline.
    """
    try:
        snapshots = storage.get_state_history(session_id)
        if len(snapshots) >= 2:
            first_state = snapshots[0].get("state", {})
            last_state = snapshots[-1].get("state", {})

            delta_trust = float(last_state.get("trust", 0.50)) - float(first_state.get("trust", 0.50))
            delta_skep = float(first_state.get("skepticism", 0.60)) - float(last_state.get("skepticism", 0.60))
            delta_risk = float(first_state.get("perceived_risk", 0.50)) - float(last_state.get("perceived_risk", 0.50))

            net_shift = (delta_trust + delta_skep + delta_risk) / 3.0
            return int(max(20, min(100, round(70.0 + (net_shift * 100.0)))))
    except Exception as exc:
        logger.debug(f"Could not compute momentum delta for session {session_id}: {exc}")
    return 75


def calculate_overall_readiness_score(
    delivery: DeliveryScorecard,
    strategic: StrategicScorecard,
    momentum_score: Optional[int] = None,
) -> int:
    """
    Calculates unified 1-100 readiness score combining:
    - Track 1: Deterministic Delivery Telemetry (30%)
    - Track 2: Strategic Content Rubric (50%)
    - Track 3: Stakeholder Perception Momentum Delta (20%)
    """
    deliv_score = calculate_delivery_numerical_score(delivery)
    strat_score = (
        strategic.discovery_score + strategic.objection_handling_score + strategic.value_proposition_score
    ) / 3.0

    if momentum_score is not None:
        combined = round(0.30 * deliv_score + 0.50 * strat_score + 0.20 * momentum_score)
    else:
        combined = round(0.35 * deliv_score + 0.65 * strat_score)

    return int(max(1, min(100, combined)))


def get_letter_grade(score: int) -> str:
    """Harmonized letter grade mapping used across all scorecard and coaching views."""
    if score >= 90:
        return "A+"
    elif score >= 82:
        return "A"
    elif score >= 74:
        return "B"
    elif score >= 65:
        return "C"
    elif score >= 50:
        return "D"
    else:
        return "F"


def get_outcome_verdict(score: int, role: str = "Executive") -> tuple[str, str]:
    """Harmonized business outcome verdict mapping aligned with the readiness score."""
    if score >= 80:
        verdict = "Follow-up Secured / Strong Executive Buy-in"
        summary = (
            f"The {role} gained high confidence and trust in your solution. "
            f"Next steps for a technical demo, formal proposal review, or pilot scoping were successfully unlocked."
        )
    elif score >= 65:
        verdict = "Positive Alignment / Pending Due Diligence"
        summary = (
            f"The {role} showed solid interest and strategic alignment, but requires additional validation on "
            f"integration, proof points, or risk mitigation before formal commitment."
        )
    elif score >= 50:
        verdict = "Conditional Interest / Substantial Proof Required"
        summary = (
            f"The {role} remains cautious. Key skepticism or perceived organizational risk "
            f"requires deeper justification and executive-level clarity before advancing."
        )
    else:
        verdict = "Deal Declined / Opportunity Lost"
        summary = (
            f"The {role} was unconvinced by value claims and perceived excessive risk. "
            f"The pitch did not adequately address executive priorities."
        )
    return verdict, summary


class SalesInterviewEvaluator:
    """Orchestrates combined Track 1 delivery telemetry and Track 2 strategic LLM evaluation."""

    def __init__(self, llm: Optional[Any] = None):
        self.llm = llm

    def _get_llm(self):
        if self.llm is None:
            try:
                import httpx
                from langchain_openai import ChatOpenAI
                client = httpx.Client(verify=False)
                self.llm = ChatOpenAI(
                    base_url="https://genailab.tcs.in",
                    model="azure/genailab-maas-gpt-4o-mini",
                    api_key=os.getenv("TCS_API_KEY", "sk-FHCqt-_flSjGm2TRjj1wXw"),  # type: ignore[arg-type]
                    http_client=client,
                    temperature=0.0,
                )
            except Exception as e:
                logger.warning(f"Could not initialize LLM for evaluator: {e}")
                self.llm = None
        return self.llm

    def evaluate_strategic_transcript(
        self,
        session_id: str,
        transcript: List[Dict[str, Any]],
        role: str = "Executive Buyer",
        topic: str = "Enterprise Sales",
    ) -> StrategicScorecard:
        """Evaluates conversation transcript strategically via LLM rubric with deterministic fallback."""
        analyses = storage.get_candidate_analyses(session_id)
        existing_report_dict = storage.get_evaluation(session_id)

        # 1. Attempt LLM-based rubric evaluation if candidate speech turns exist
        candidate_messages = [t["message"] for t in transcript if t.get("sender") == "user"]
        llm = self._get_llm()

        if llm and candidate_messages:
            try:
                transcript_text = "\n".join(
                    f"{t.get('sender', 'user').upper()}: {t.get('message', '')}"
                    for t in transcript
                )
                prompt = (
                    f"You are an expert Executive Sales Pitch Judge evaluating a sales interview candidate.\n"
                    f"Role: {role}\nTopic: {topic}\n\n"
                    f"Transcript:\n{transcript_text}\n\n"
                    "Evaluate the candidate across these strategic criteria:\n"
                    "1. discovery_score: (0-100) How well did candidate diagnose pain, ask qualifying questions, and uncover buyer needs?\n"
                    "2. objection_handling_score: (0-100) How well did candidate acknowledge, validate, and defuse buyer skepticism and risk?\n"
                    "3. value_proposition_score: (0-100) How persuasively did candidate tie solution to ROI and business impact?\n"
                    "4. strengths: 2-3 concise bullet points of strategic strengths.\n"
                    "5. critical_misses: 2-3 concise bullet points of critical omissions, evasions, or lost opportunities.\n"
                    "6. key_coaching_quote: The most important quote from the candidate that needs coaching.\n\n"
                    "Return ONLY valid JSON matching this schema:\n"
                    "{\n"
                    '  "discovery_score": int,\n'
                    '  "objection_handling_score": int,\n'
                    '  "value_proposition_score": int,\n'
                    '  "strengths": [str],\n'
                    '  "critical_misses": [str],\n'
                    '  "key_coaching_quote": str\n'
                    "}"
                )
                response = llm.invoke([{"role": "system", "content": prompt}])
                raw_content = str(response.content).strip()
                if "```json" in raw_content:
                    raw_content = raw_content.split("```json", 1)[1].split("```", 1)[0].strip()
                elif "```" in raw_content:
                    raw_content = raw_content.split("```", 1)[1].split("```", 1)[0].strip()

                parsed = json.loads(raw_content)
                return StrategicScorecard(
                    discovery_score=max(0, min(100, int(parsed.get("discovery_score", 70)))),
                    objection_handling_score=max(0, min(100, int(parsed.get("objection_handling_score", 70)))),
                    value_proposition_score=max(0, min(100, int(parsed.get("value_proposition_score", 70)))),
                    strengths=parsed.get("strengths", ["Maintained conversational momentum."]),
                    critical_misses=parsed.get("critical_misses", ["Could sharpen quantified ROI claims."]),
                    key_coaching_quote=parsed.get("key_coaching_quote", candidate_messages[0] if candidate_messages else ""),
                )
            except Exception as exc:
                logger.warning(f"LLM strategic evaluation failed or timed out: {exc}. Using deterministic synthesis.")

        # 2. Resilient Deterministic Fallback: Derive from candidate analyses and structured report
        return self._deterministic_strategic_fallback(candidate_messages, analyses, existing_report_dict)

    def _deterministic_strategic_fallback(
        self,
        candidate_messages: List[str],
        analyses: List[Dict[str, Any]],
        existing_report: Optional[Dict[str, Any]],
    ) -> StrategicScorecard:
        """Deterministic synthesis of strategic scorecard when LLM is unavailable or in unit tests."""
        discovery_count = 0
        value_count = 0
        objection_defused = 0
        weakness_quotes: List[str] = []
        strengths: List[str] = []

        for ana in analyses:
            analysis_dict = ana.get("analysis", {})
            sb = analysis_dict.get("sales_behavior", {})
            rq = analysis_dict.get("response_quality", {})

            if sb.get("discovery_question") or "?" in ana.get("candidate_message", ""):
                discovery_count += 1
            if sb.get("value_articulated") or rq.get("evidence_backed"):
                value_count += 1
            if sb.get("objection_handled") or not rq.get("evasive"):
                objection_defused += 1

            if rq.get("vague") or rq.get("evasive") or rq.get("unprofessional_behavior"):
                weakness_quotes.append(ana.get("candidate_message", "")[:120])

        total_turns = max(1, len(analyses))
        discovery_score = min(95, max(30, int(45 + (discovery_count / total_turns) * 50)))
        value_score = min(95, max(30, int(45 + (value_count / total_turns) * 50)))
        objection_score = min(95, max(30, int(50 + (objection_defused / total_turns) * 45)))

        if existing_report and isinstance(existing_report, dict) and "subscores" in existing_report:
            for sub in existing_report.get("subscores", []):
                name = sub.get("name", "").lower()
                if "objection" in name:
                    objection_score = int(sub.get("score", objection_score))
                elif "value" in name:
                    value_score = int(sub.get("score", value_score))

            if existing_report.get("strengths"):
                strengths = [s.get("title", "") + ": " + s.get("description", "") for s in existing_report["strengths"][:3]]

        if not strengths:
            strengths = [
                "Maintained clear executive focus and professional tone.",
                "Engaged buyer directly on primary problem agenda.",
            ]

        critical_misses = [
            "Front-load quantitative metrics earlier in the conversation.",
            "Confirm buyer agreement before transitioning between topics.",
        ]

        key_quote = weakness_quotes[0] if weakness_quotes else (candidate_messages[0] if candidate_messages else "N/A")

        return StrategicScorecard(
            discovery_score=discovery_score,
            objection_handling_score=objection_score,
            value_proposition_score=value_score,
            strengths=strengths,
            critical_misses=critical_misses,
            key_coaching_quote=key_quote,
        )

    def evaluate_post_call(
        self,
        session_id: str,
        telemetry: Optional[SessionTelemetry] = None,
        transcript: Optional[List[Dict[str, Any]]] = None,
    ) -> SalesInterviewScorecard:
        """Executes the combined evaluation pipeline and returns the consolidated SalesInterviewScorecard."""
        # 1. Track 1: Delivery Scorecard
        if telemetry:
            delivery_scorecard = telemetry.compute_delivery_scorecard()
        else:
            delivery_scorecard = DeliveryScorecard(
                talk_listen_ratio=0.50,
                talk_ratio_verdict="Balanced",
                avg_response_latency_sec=1.20,
                latency_verdict="Crisp",
                average_wpm=140.0,
                pace_verdict="Optimal",
                interruption_count=0,
            )

        # 2. Track 2: Strategic Scorecard
        raw_transcript = transcript if transcript is not None else storage.get_interactions(session_id)
        stored_session = storage.get_session(session_id) or {}
        role = stored_session.get("role", "Executive Buyer")
        topic = stored_session.get("topic", "Sales Conversation")

        strategic_scorecard = self.evaluate_strategic_transcript(
            session_id=session_id,
            transcript=raw_transcript,
            role=role,
            topic=topic,
        )

        # 3. Overall Readiness Score (Tri-Track: Delivery 30% + Strategic 50% + Momentum 20%)
        momentum_score = compute_stakeholder_momentum(session_id)
        readiness_score = calculate_overall_readiness_score(
            delivery_scorecard, strategic_scorecard, momentum_score=momentum_score
        )

        scorecard = SalesInterviewScorecard(
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            delivery_scorecard=delivery_scorecard,
            strategic_scorecard=strategic_scorecard,
            overall_readiness_score=readiness_score,
        )

        # 4. Persist to storage
        try:
            storage.save_scorecard(session_id, scorecard.model_dump())
        except Exception as exc:
            logger.error(f"Failed to persist scorecard for session {session_id}: {exc}")

        return scorecard


# Global evaluator singleton
_GLOBAL_EVALUATOR = SalesInterviewEvaluator()


def get_sales_evaluator() -> SalesInterviewEvaluator:
    return _GLOBAL_EVALUATOR
