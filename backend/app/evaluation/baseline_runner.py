"""Baseline and Ablation Session Runner for Elevate.

Executes simulation runs under controlled architecture ablation modes:
1. STATIC_PROMPT: Original Phase 1 static markdown persona + unguided LLM.
2. PERSONA_ONLY: Phase 2 typed EnterprisePersona prompt.
3. PERSONA_PLUS_STATE: Adds Phase 3 dynamic client state.
4. PERSONA_PLUS_STATE_PLUS_INTERVIEW: Adds Phase 4 interview state machine.
5. PERSONA_PLUS_STATE_PLUS_INTERVIEW_PLUS_BEHAVIOR: Adds Phase 5 & 6 behavioral policy.
6. FULL_SIMULATOR: Complete Phase 1-7 pipeline (knowledge, memory, consistency).
"""

import time
import uuid
from typing import Dict, List, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.services.llm_service import get_llm
from app.agents.prompts import get_interviewer_system_prompt
from app.roles.registry import get_persona
from app.evaluation.evaluation_models import (
    SimulatorArchitectureMode,
    ControlledScenario,
)
from app.agents.role_agent import RoleAgent


class BaselineRunner:
    """Executes controlled scenario runs across different simulation architectures."""

    def __init__(self):
        self.llm = get_llm()

    def run_session(
        self,
        scenario: ControlledScenario,
        architecture_mode: SimulatorArchitectureMode,
        role_id: str = "CTO",
        topic: str = "Enterprise Cloud Modernization",
        session_id: Optional[str] = None,
        experience: str = "Senior Enterprise Account Executive",
        style: str = "Professional",
        persona_configuration: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Execute all candidate turns for a scenario under the specified architecture mode."""
        session_id = session_id or str(uuid.uuid4())
        persona = get_persona(role_id, scenario=scenario.title)

        transcript_turns: List[Dict[str, Any]] = []
        state_trajectory: List[Dict[str, Any]] = []
        decisions: List[Any] = []
        memory_items: List[Any] = []
        world_facts: List[Any] = []

        total_start_time = time.time()

        if architecture_mode == SimulatorArchitectureMode.STATIC_PROMPT:
            # Baseline: execute via raw static markdown persona prompt
            import os
            role_file = os.path.join(os.path.dirname(__file__), "..", "roles", f"{role_id}.md")
            try:
                with open(role_file, "r") as f:
                    legacy_prompt = f.read()
            except Exception:
                legacy_prompt = f"You are a simulated {role_id} in an enterprise sales interview."

            messages = [SystemMessage(content=legacy_prompt)]
            state_trajectory.append({"turn": 0, "trust": 0.5, "skepticism": 0.5})

            for idx, candidate_text in enumerate(scenario.candidate_turns):
                turn_num = idx + 1
                messages.append(HumanMessage(content=candidate_text))
                turn_start = time.time()
                try:
                    resp = self.llm.invoke(messages)
                    messages.append(resp)
                except Exception as e:
                    resp = AIMessage(content=f"Mock baseline response to: {candidate_text[:30]}")

                turn_latency = (time.time() - turn_start) * 1000.0
                transcript_turns.append({
                    "turn": turn_num,
                    "candidate_message": candidate_text,
                    "stakeholder_response": resp.content,
                    "selected_action": None,
                    "state_snapshot": {"trust": 0.5, "skepticism": 0.5},
                    "latency_ms": turn_latency,
                })
                state_trajectory.append({"turn": turn_num, "trust": 0.5, "skepticism": 0.5})

        else:
            # Execute through RoleAgent configured with ablation mode and persona configuration
            agent = RoleAgent(
                role_id=role_id,
                topic=topic,
                scenario=scenario.title,
                experience=experience,
                style=style,
                session_id=session_id,
                architecture_mode=architecture_mode.value,
                memory_mode="disabled" if architecture_mode != SimulatorArchitectureMode.FULL_SIMULATOR else "full",
                persona_configuration=persona_configuration,
            )

            state_trajectory.append({
                "turn": 0,
                "trust": agent.current_state.trust,
                "skepticism": agent.current_state.skepticism,
                "patience": agent.current_state.patience,
                "interest": agent.current_state.interest,
                "frustration": agent.current_state.frustration,
                "perceived_risk": agent.current_state.perceived_risk,
            })

            for idx, candidate_text in enumerate(scenario.candidate_turns):
                turn_num = idx + 1
                turn_start = time.time()
                reply = agent.chat(candidate_text)
                turn_latency = (time.time() - turn_start) * 1000.0

                action_name = None
                if agent.current_decision and hasattr(agent.current_decision, "primary_action"):
                    action_name = agent.current_decision.primary_action.action_type.value if hasattr(agent.current_decision.primary_action.action_type, "value") else str(agent.current_decision.primary_action.action_type)
                    decisions.append(agent.current_decision)

                state_snapshot = {
                    "trust": agent.current_state.trust,
                    "skepticism": agent.current_state.skepticism,
                    "patience": agent.current_state.patience,
                    "interest": agent.current_state.interest,
                    "frustration": agent.current_state.frustration,
                    "perceived_risk": agent.current_state.perceived_risk,
                }
                state_trajectory.append({"turn": turn_num, **state_snapshot})

                transcript_turns.append({
                    "turn_number": turn_num,
                    "candidate_input": candidate_text,
                    "stakeholder_response": reply,
                    "selected_action": action_name,
                    "state_snapshot": state_snapshot,
                    "latency_ms": turn_latency,
                })

            if hasattr(agent, "memory_store") and agent.memory_store:
                memory_items = agent.memory_store.memories
            if hasattr(agent, "world_registry") and agent.world_registry:
                world_facts = agent.world_registry.get_all_facts()

        total_latency_ms = (time.time() - total_start_time) * 1000.0

        return {
            "session_id": session_id,
            "persona": persona,
            "transcript_turns": transcript_turns,
            "state_trajectory": state_trajectory,
            "decisions": decisions,
            "memory_items": memory_items,
            "world_facts": world_facts,
            "performance_metrics": {
                "total_session_latency_ms": round(total_latency_ms, 2),
                "turns_count": len(scenario.candidate_turns),
                "avg_turn_latency_ms": round(total_latency_ms / max(1, len(scenario.candidate_turns)), 2),
            },
        }
