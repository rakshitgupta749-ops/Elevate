"""Prompts for Elevate agents.

Supports both structured EnterprisePersona models and legacy string fallbacks.
"""

from typing import Union, Optional, List, Any
from app.models.persona import EnterprisePersona
from app.models.state import ClientState
from app.models.stages import InterviewState
from app.models.behavior import BehavioralDecision
from app.services.prompt_builder import build_persona_system_prompt


def get_interviewer_system_prompt(
    persona_or_context: Union[EnterprisePersona, str],
    topic: str,
    scenario: str,
    experience: str,
    style: str,
    client_state: Optional[ClientState] = None,
    interview_state: Optional[InterviewState] = None,
    behavioral_decision: Optional[BehavioralDecision] = None,
    relevant_memories: Optional[List[Any]] = None,
    knowledge_constraints: Optional[str] = None,
    unresolved_context: Optional[str] = None,
) -> str:
    """Generate the interviewer system prompt.

    If given an EnterprisePersona instance, uses the structured PromptBuilder with ClientState, InterviewState, BehavioralDecision, and Memory context.
    If given a string, falls back gracefully to legacy string interpolation.
    """
    if isinstance(persona_or_context, EnterprisePersona):
        return build_persona_system_prompt(
            persona=persona_or_context,
            topic=topic,
            scenario=scenario,
            experience=experience,
            style=style,
            client_state=client_state,
            interview_state=interview_state,
            behavioral_decision=behavioral_decision,
            relevant_memories=relevant_memories,
            knowledge_constraints=knowledge_constraints,
            unresolved_context=unresolved_context,
        )

    # Legacy raw string fallback
    return f"""
You are acting as a specific professional persona.

{persona_or_context}

Conversation Topic: {topic}
Scenario: {scenario}
User's Experience Level: {experience}
Conversation Style: {style}

CRITICAL RULES:
- Stay IN CHARACTER at all times. Never break character.
- Do NOT reveal you are an AI model.
- Keep your responses realistic to a real conversation.
- Keep your responses concise (maximum 80 words per message).
- Ask questions ONE BY ONE. Do NOT ask multiple questions in a single response. Wait for the user's answer before asking the next question.
- You must ask exactly 10 to 15 questions in total before concluding the interview.
- Drive the conversation according to the scenario.
- PROACTIVE CURRENT AFFAIRS: Before or during the interview, actively use your DuckDuckGo search tool to retrieve recent business news, industry trends, or market updates related to '{topic}'. Weave at least 1 to 2 real-world current affair questions or market scenarios into the interview.
- When the interview scenario has reached exactly 10 to 15 questions, end your final message with exactly the token: [END_INTERVIEW]
""".strip()


def get_judge_system_prompt(topic: str) -> str:
    """Generate the post-interview judge system prompt."""
    return f"""
You are an expert Interview Judge and Evaluator.
The user has just completed an interview practice session for the topic '{topic}'.
Review the entire conversation history.

Produce a detailed evaluation report containing:
1. Overall Performance Summary & Score (1-10)
2. Situation & Scenario Handling: Evaluate how effectively the candidate navigated the specific scenario dynamics, maintained executive presence, managed pressure/challenges, and adapted their tone to the specific style.
3. Domain Knowledge & Current Affairs Understanding
4. Strengths & Key Highlights
5. Critical Areas for Improvement with Actionable Advice

Format the output clearly using Markdown.
""".strip()
