"""Coaching, Lifecycle, Hint, and History Models for Elevate (Priority P0 & P1)."""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class FeedbackSubscore(BaseModel):
    name: str
    score: int  # 0 - 100
    description: str


class FeedbackStrength(BaseModel):
    title: str
    description: str
    quote: Optional[str] = None


class FeedbackWeakness(BaseModel):
    title: str
    description: str
    quote: Optional[str] = None
    recommended_alternative: Optional[str] = None  # "What you should have said instead"


class StructuredCoachingReport(BaseModel):
    session_id: str
    role: str
    topic: str
    scenario: str
    overall_score: int  # 0 - 100
    letter_grade: str  # A+, A, B, C, D, F
    outcome_verdict: str  # e.g., "Follow-up Secured", "Stakeholder Walkout"
    outcome_summary: str
    subscores: List[FeedbackSubscore] = []
    strengths: List[FeedbackStrength] = []
    weaknesses: List[FeedbackWeakness] = []
    tactical_takeaways: List[str] = []
    markdown_report: str = ""


class CoachingHintResponse(BaseModel):
    session_id: str
    hint: str
    focus_area: str
    current_stakeholder_perception: str


class RewindResponse(BaseModel):
    session_id: str
    status: str
    restored_turn: int
    restored_state: Dict[str, Any]
    messages: List[Dict[str, Any]]
    system_notice: str


class SessionSummaryItem(BaseModel):
    id: str
    topic: str
    role: str
    scenario: str
    experience: str
    style: str
    created_at: str
    turn_count: int
    has_evaluation: bool
    overall_score: Optional[int] = None
    outcome_verdict: Optional[str] = None


class SessionTranscriptResponse(BaseModel):
    session_id: str
    topic: str
    role: str
    scenario: str
    created_at: str
    interactions: List[Dict[str, Any]]
    evaluation: Optional[StructuredCoachingReport] = None
