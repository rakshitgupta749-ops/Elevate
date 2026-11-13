"""Prompt Builder Service for Elevate.

Translates typed EnterprisePersona, CompanyContext models, runtime ClientState,
and deterministic InterviewState into structured LLM system prompts without embedding hardcoded
behavioral branching logic.
"""

from typing import Optional, List, Any
from app.models.persona import EnterprisePersona
from app.models.state import ClientState
from app.models.stages import InterviewState, InterviewStage, InterviewStatus
from app.models.behavior import BehavioralDecision
from app.services.interview_state_manager import DEFAULT_STAGE_CONFIGS


def build_persona_system_prompt(
    persona: EnterprisePersona,
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
    """Build a structured system prompt from EnterprisePersona, scenario, ClientState, and InterviewState.

    Formats the persona profile, simulation values, evaluation goals, incentives,
    epistemic boundaries, company world model, current perception state, and active interview stage.
    """
    profile = persona.profile
    kb = persona.knowledge_boundary
    wm = persona.world_model

    # Format values section (sorted by priority)
    sorted_values = sorted(persona.values, key=lambda v: v.priority)
    values_text = "\n".join(
        f"- {v.name.capitalize()} (Simulation weight: {v.weight:.2f}): {v.description}"
        for v in sorted_values
    ) or "None specified."

    # Format goals section
    goals_text = "\n".join(
        f"- [{g.id}] (Priority: {g.priority:.2f}, Type: {g.type}{', DEALBREAKER' if g.dealbreaker else ''}): {g.description} -> Target: {g.success_condition}"
        for g in persona.goals
    ) or "None specified."

    # Format incentives section
    incentives_text = "\n".join(
        f"- [{inc.category.capitalize()}] {inc.description}"
        for inc in persona.incentives
    ) or "None specified."

    # Format knowledge boundaries
    expert_topics = ", ".join(kb.expert_topics) if kb.expert_topics else "None"
    known_topics = ", ".join(kb.known_topics) if kb.known_topics else "None"
    limited_topics = ", ".join(kb.limited_topics) if kb.limited_topics else "None"
    unknown_topics = ", ".join(kb.unknown_topics) if kb.unknown_topics else "None"
    confidential_topics = ", ".join(kb.confidential_topics) if kb.confidential_topics else "None"
    disclosure_rules = "\n".join(f"  * {rule}" for rule in kb.disclosure_rules) if kb.disclosure_rules else "  * Standard enterprise confidentiality applies."

    # Format World Model / Company Context
    if wm:
        stack_str = ", ".join(wm.current_technology_stack) if wm.current_technology_stack else "Standard enterprise tools"
        vendors_str = ", ".join(wm.incumbent_vendors) if wm.incumbent_vendors else "Incumbent enterprise providers"
        pains_str = "; ".join(wm.pain_points) if wm.pain_points else "General operational efficiency challenges"
        constraints_str = "; ".join(wm.constraints) if wm.constraints else "Standard budget and security controls"

        world_model_text = f"""INDUSTRY & OPERATING ENVIRONMENT:
- Industry: {wm.industry}
- Scale: {wm.company_size}{f' ({wm.company_stage})' if wm.company_stage else ''}
- Current Tech Stack: {stack_str}
- Incumbent Vendors: {vendors_str}
- Core Pain Points: {pains_str}
- Constraints: {constraints_str}{f', Budget: {wm.budget_constraints}' if wm.budget_constraints else ''}{f', Timeline: {wm.timeline}' if wm.timeline else ''}"""
    else:
        world_model_text = "INDUSTRY & OPERATING ENVIRONMENT: Enterprise commercial environment."

    traits_str = ", ".join(profile.personality_characteristics) if profile.personality_characteristics else "Professional"

    prompt = f"""You are roleplaying as an enterprise simulated stakeholder: {profile.title} ({profile.role}).

### PERSONA PROFILE
- Title & Department: {profile.title}, {profile.department} ({profile.seniority}, {profile.years_of_experience} yrs exp)
- Technical Depth: {profile.technical_depth}
- Communication Style: {profile.communication_style}
- Personality Traits: {traits_str}
- Risk Stance: {profile.risk_profile}

### CORE VALUES & PRIORITIES
{values_text}

### STAKEHOLDER EVALUATION GOALS
{goals_text}

### INCENTIVES
{incentives_text}

### KNOWLEDGE BOUNDARIES & CONFIDENTIALITY
- Expert Domains: {expert_topics}
- Competent Domains: {known_topics}
- Limited Understanding: {limited_topics}
- Out-of-Bounds / Unknown: {unknown_topics}
- Confidential (Withhold): {confidential_topics}
- Disclosure Rules:
{disclosure_rules}

### {world_model_text}

### PRACTICE CONVERSATION PARAMETERS
- Topic: {topic}
- Scenario: {scenario}
- Candidate Experience Level: {experience}
- Conversation Tone/Style: {style}"""

    # Stage Context Injection (InterviewState)
    if interview_state:
        stage_cfg = DEFAULT_STAGE_CONFIGS.get(interview_state.current_stage)
        stage_name = stage_cfg.name if stage_cfg else interview_state.current_stage.value
        stage_obj = stage_cfg.objective if stage_cfg else "Progress through the enterprise sales conversation."
        min_turns = stage_cfg.min_turns if stage_cfg else 1
        max_turns = stage_cfg.max_turns if stage_cfg else 5

        # Format criteria progress
        stage_criteria = [c for c in interview_state.criteria.values() if c.stage == interview_state.current_stage]
        criteria_lines = []
        for c in stage_criteria:
            status_str = "MET" if c.satisfied else f"PENDING ({'MANDATORY' if c.required else 'OPTIONAL'})"
            criteria_lines.append(f"- [{status_str}] {c.name}: {c.description}")
        criteria_text = "\n".join(criteria_lines) if criteria_lines else "- No specific criteria."

        # Stage specific behavioral guard
        guard_text = ""
        if interview_state.current_stage == InterviewStage.STAGE_2_PROBLEM_DISCOVERY:
            if not interview_state.all_required_criteria_satisfied(InterviewStage.STAGE_2_PROBLEM_DISCOVERY):
                guard_text = "\nPREMATURE PITCH GUARD: You are in PROBLEM DISCOVERY and key business pain is not yet uncovered. If the candidate attempts to pitch solutions prematurely, do NOT accept or validate their pitch; guide them back by asking about specific challenges, current-state processes, and pain points."
        elif interview_state.current_stage == InterviewStage.STAGE_3_SOLUTION_ALIGNMENT:
            guard_text = "\nSTAGE GUIDANCE: Focus on evaluating how well the candidate maps their solution directly to the problems uncovered during discovery. Probe whether it truly fits your architecture."
        elif interview_state.current_stage == InterviewStage.STAGE_4_OBJECTIONS_AND_DEEP_DIVE:
            guard_text = "\nSTAGE GUIDANCE: Actively challenge assumptions, raise technical risks (reliability, downtime, migration, security), and scrutinize candidate claims under pressure."
        elif interview_state.current_stage == InterviewStage.STAGE_5_COMMERCIALS_AND_CLOSING:
            guard_text = "\nSTAGE GUIDANCE: Discuss commercial model, pricing expectations, procurement approvals, and determine concrete next steps or proof of concept."

        prompt += f"""

### CURRENT INTERVIEW STAGE: {interview_state.current_stage.value} ({stage_name})
- Stage Objective: {stage_obj}
- Stage Progress: Turn {interview_state.stage_turn_count} of min {min_turns} / max {max_turns} (Total interview turn: {interview_state.total_turn_count}/{interview_state.max_total_turns})
- Lifecycle Status: {interview_state.status.value}
- Stage Criteria Progress:
{criteria_text}{guard_text}"""

    # Dynamic Client State Injection
    if client_state:
        extreme_behavior_guidance = ""
        if client_state.patience < 0.3 or client_state.frustration > 0.6:
            extreme_behavior_guidance = "\nCRITICAL TONE DIRECTIVE: Your patience is extremely low and frustration is high. You MUST reflect this by being terse, blunt, visibly annoyed, and explicitly calling out unprofessional or irrelevant behavior. Do not be polite if the candidate is wasting your time."
        elif client_state.trust > 0.8:
            extreme_behavior_guidance = "\nTONE DIRECTIVE: You have high trust in the candidate. You can be more open, collaborative, and conversational."

        prompt += f"""

### CURRENT STAKEHOLDER PERCEPTION (INTERNAL SIMULATION CONTEXT)
- Trust: {client_state.trust:.2f} | Skepticism: {client_state.skepticism:.2f} | Patience: {client_state.patience:.2f}
- Engagement: {client_state.engagement:.2f} | Interest: {client_state.interest:.2f} | Perceived Risk: {client_state.perceived_risk:.2f}
- Frustration: {client_state.frustration:.2f} | Confidence in Candidate: {client_state.confidence_in_candidate:.2f}

GUIDANCE: Calibrate conversational tone and questioning depth to your current perception. If skepticism is high, probe deeper on unverified assertions. If patience is low or frustration is elevated, be more terse and demand brevity. DO NOT mention these numeric metrics or reveal your internal state directly to the salesperson.{extreme_behavior_guidance}"""

    prompt += f"""

### OPERATIONAL RULES
1. Stay strictly IN CHARACTER at all times. Never break character.
2. Do NOT reveal you are an AI model or language assistant.
3. SPOKEN AUDIO CONVERSATION ONLY: Every response is spoken aloud via voice synthesis. You MUST NEVER output Markdown headings (NO '#', '##', '###'), bold/italic formatting (NO '**', '*'), or bullet points/lists (NO '-', '•', '1.'). Speak in natural conversational prose.
4. Maintain realistic executive posture consistent with your Communication Style, Values, and the CURRENT INTERVIEW STAGE.
5. Keep your responses concise (maximum 80 words per message).
6. Ask questions ONE BY ONE. Do NOT ask multiple questions in a single response. Wait for the user's answer before asking the next question.
7. The conversation stage is governed by the state machine. Focus your response exclusively on the active stage objectives.
8. CURRENT AFFAIRS: Before or during the interview, you may use your DuckDuckGo search tool to retrieve recent business news, industry trends, or market updates related to '{topic}'. Weave at least 1 to 2 real-world market questions into the discussion.
9. When the interview scenario has concluded or reached completion, conclude your final message with exactly the token: [END_INTERVIEW]
"""

    if relevant_memories:
        mem_lines = []
        for m in relevant_memories:
            m_type = m.type.value if hasattr(m.type, "value") else str(getattr(m, "type", "MEMORY"))
            m_content = getattr(m, "content", str(m))
            m_turn = getattr(m, "source_turn", "?")
            mem_lines.append(f"- [{m_type} (Turn {m_turn})]: {m_content}")
        mem_text = "\n".join(mem_lines)
        prompt += f"""

### CONVERSATIONAL MEMORY (RELEVANT HISTORICAL CONTEXT)
The following verified historical memories are relevant to the current turn:
{mem_text}
RULE: Maintain strict consistency with your prior statements. If the candidate contradicts their own prior statements, hold them accountable."""

    if unresolved_context:
        prompt += f"""

### ACTIVE STAKEHOLDER CONTEXT (UNRESOLVED QUESTIONS & OBJECTIONS)
{unresolved_context}"""

    if knowledge_constraints:
        prompt += f"""

### KNOWLEDGE & DISCLOSURE BOUNDARIES
{knowledge_constraints}"""

    if behavioral_decision and behavioral_decision.mode != "disabled":
        prompt += f"\n\n{behavioral_decision.format_prompt_instructions()}"

    return prompt.strip()
