import os
import operator
from typing import Annotated, Sequence, TypedDict, Optional, List, Any, Union, Dict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_community.tools import DuckDuckGoSearchRun
from app.services.llm_service import get_llm
from langgraph.checkpoint.memory import MemorySaver
from app.agents.prompts import get_interviewer_system_prompt, get_judge_system_prompt
from app.roles.registry import get_persona
from app.models.state import ClientState, StateEvent
from app.models.stages import (
    InterviewStage,
    InterviewStatus,
    StageCriterion,
    StageTransitionEvent,
    InterviewState,
)
import time
from app.services.state_manager import ClientStateManager, detect_interaction_signal
from app.services.interview_state_manager import InterviewStateManager
from app.models.analysis import (
    CandidateTurnAnalysis,
    CandidateFactLedger,
    CandidateClaimLedger,
)
from app.services.candidate_analyzer import (
    CandidateBehaviorAnalyzer,
    map_analysis_to_signals,
)
from app.models.behavior import BehavioralDecision, ActionType
from app.services.policy_engine import BehavioralPolicyEngine
from app.models.memory import (
    WorldFact,
    StakeholderKnowledgeItem,
    MemoryItem,
    StakeholderCommitment,
    UnresolvedQuestion,
    UnresolvedObjection,
    ConsistencyValidationResult,
    DisclosureLevel,
    ItemStatus,
    CommitmentStatus,
)
from app.services.memory_service import (
    WorldFactRegistry,
    StakeholderKnowledgeState,
    ConversationalMemoryStore,
    MemoryRetriever,
    ResponseConsistencyValidator,
)
from app.models.configuration import PersonaConfiguration
from app.roles.traits import resolve_persona_configuration
from app.services.storage_service import storage
from app.models.coaching import (
    StructuredCoachingReport,
    FeedbackSubscore,
    FeedbackStrength,
    FeedbackWeakness,
    CoachingHintResponse,
    RewindResponse,
)
from app.utils.guardrails import is_candidate_exit_intent


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    is_finished: bool
    client_state: dict
    state_events: Annotated[List[dict], operator.add]
    turn_count: int
    interview_state: dict
    interview_events: Annotated[List[dict], operator.add]
    candidate_analysis: dict
    fact_ledger: list[dict]
    claim_ledger: list[dict]
    behavioral_decision: dict
    policy_mode: str
    memory_items: list[dict]
    knowledge_items: list[dict]
    commitments: list[dict]
    unresolved_items: list[dict]
    memory_mode: str
    architecture_mode: Optional[str]


class RoleAgent:
    def __init__(
        self,
        role_id: str,
        topic: str,
        scenario: str,
        experience: str,
        style: str,
        session_id: str,
        policy_mode: str = "rule_based",
        memory_mode: str = "full",
        architecture_mode: str = "FULL_SIMULATOR",
        persona_configuration: Optional[Any] = None,
    ):
        self.role_id = role_id
        self.topic = topic
        self.scenario = scenario
        self.experience = experience
        self.style = style
        self.session_id = session_id
        self.policy_mode = policy_mode
        self.memory_mode = memory_mode
        self.architecture_mode = architecture_mode

        # Phase 9: Resolve concrete PersonaConfiguration
        if isinstance(persona_configuration, PersonaConfiguration):
            self.persona_configuration = persona_configuration
        elif isinstance(persona_configuration, dict):
            self.persona_configuration = resolve_persona_configuration(
                role=self.role_id,
                preset=persona_configuration.get("preset", "BALANCED"),
                custom_traits=persona_configuration.get("traits"),
                scenario_overrides=persona_configuration.get("scenario_overrides"),
                schema_version=persona_configuration.get("persona_schema_version", "1.0"),
            )
        else:
            self.persona_configuration = resolve_persona_configuration(role=self.role_id)

        self.llm = get_llm()
        self.persona = get_persona(self.role_id, scenario=self.scenario)
        self.role_context = self._load_role_context()

        # Dynamic Perception State Initialization (Turn 0, calibrated by Phase 9 traits)
        self.state_manager = ClientStateManager()
        self.current_state = self.state_manager.initialize_state(
            persona=self.persona,
            style=self.style,
            persona_config=self.persona_configuration,
        )
        self.turn_count = 0
        self._opening_message: Optional[str] = None
        self.candidate_early_exit: bool = False

        # Persist resolved persona configuration to SQLite
        try:
            storage.save_persona_configuration(
                session_id=self.session_id,
                role=self.persona_configuration.role,
                preset=self.persona_configuration.preset,
                traits=self.persona_configuration.traits,
                scenario_overrides=self.persona_configuration.scenario_overrides,
                schema_version=self.persona_configuration.persona_schema_version,
            )
        except Exception:
            pass

        # Interview State Machine Initialization (Turn 0)
        self.interview_state_manager = InterviewStateManager()
        self.interview_state = self.interview_state_manager.initialize_state(max_total_turns=15)

        # Candidate Behavior & Content Analyzer Initialization (Phase 5)
        self.analyzer = CandidateBehaviorAnalyzer()
        self.fact_ledger = CandidateFactLedger()
        self.claim_ledger = CandidateClaimLedger()

        # Behavioral Policy Engine Initialization (Phase 6)
        self.policy_engine = BehavioralPolicyEngine(policy_mode=self.policy_mode)
        self.current_decision: Optional[BehavioralDecision] = None

        # Information & Memory Layer Initialization (Phase 7)
        self.world_registry = WorldFactRegistry(persona=self.persona, scenario=self.scenario)
        self.knowledge_state = StakeholderKnowledgeState(persona=self.persona)
        self.memory_store = ConversationalMemoryStore()
        self.memory_retriever = MemoryRetriever()
        self.consistency_validator = ResponseConsistencyValidator()

        # Persist Turn 0 knowledge items to SQLite
        for k_item in self.knowledge_state.get_all_items():
            try:
                storage.save_knowledge_item(self.session_id, k_item, turn_number=0)
            except Exception as e:
                pass

        # Persist Turn 0 initial state snapshot to SQLite
        try:
            storage.save_state_snapshot(
                session_id=self.session_id,
                turn_number=0,
                state=self.current_state,
                event_type="session_initialized",
                event_reason="Initial baseline state established for persona and style",
            )
            storage.save_interview_stage_event(
                session_id=self.session_id,
                turn_number=0,
                from_stage=self.interview_state.current_stage.value,
                to_stage=self.interview_state.current_stage.value,
                reason="Initial interview state established: Opening & Rapport",
            )
        except Exception as e:
            # Non-blocking log if SQLite error occurs in isolated test environments
            print(f"Warning: Failed to save initial state snapshot or stage event: {e}")

        self.memory = MemorySaver()
        try:
            self.search_tool = DuckDuckGoSearchRun()
            self.tools = [self.search_tool]
        except Exception:
            self.search_tool = None
            self.tools = []

        if self.tools and hasattr(self.llm, "bind_tools"):
            try:
                self.llm_with_tools = self.llm.bind_tools(self.tools)
            except Exception:
                self.llm_with_tools = self.llm
        else:
            self.llm_with_tools = self.llm
        self.graph = self._build_graph()

    def _load_role_context(self) -> str:
        role_file = os.path.join(os.path.dirname(__file__), "..", "roles", f"{self.role_id}.md")
        try:
            with open(role_file, "r") as f:
                return f.read()
        except FileNotFoundError:
            return f"Role {self.role_id} acting professionally."

    def _interviewer_node(self, state: AgentState):
        messages = state["messages"]
        turn_count = state.get("turn_count", self.turn_count)
        raw_state = state.get("client_state")
        if isinstance(raw_state, dict):
            current_state = ClientState(**raw_state)
        elif isinstance(raw_state, ClientState):
            current_state = raw_state
        else:
            current_state = self.current_state

        # Hydrate InterviewState from LangGraph state dict
        raw_interview = state.get("interview_state")
        if isinstance(raw_interview, dict):
            criteria_dict = {}
            for cid, cdata in raw_interview.get("criteria", {}).items():
                if isinstance(cdata, dict):
                    criteria_dict[cid] = StageCriterion(**cdata)
                elif isinstance(cdata, StageCriterion):
                    criteria_dict[cid] = cdata
            history_list = []
            for hevent in raw_interview.get("history", []):
                if isinstance(hevent, dict):
                    history_list.append(StageTransitionEvent(**hevent))
                elif isinstance(hevent, StageTransitionEvent):
                    history_list.append(hevent)
            interview_state = InterviewState(
                current_stage=raw_interview.get("current_stage", InterviewStage.STAGE_1_OPENING_RAPPORT),
                stage_turn_count=raw_interview.get("stage_turn_count", 0),
                total_turn_count=raw_interview.get("total_turn_count", 0),
                max_total_turns=raw_interview.get("max_total_turns", 15),
                status=raw_interview.get("status", InterviewStatus.ACTIVE),
                criteria=criteria_dict,
                history=history_list,
                termination_reason=raw_interview.get("termination_reason"),
            )
        elif isinstance(raw_interview, InterviewState):
            interview_state = raw_interview
        else:
            interview_state = self.interview_state

        # Determine candidate message
        candidate_message = ""
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                candidate_message = m.content
                break

        new_turn = turn_count + 1

        # Architecture Ablation Mode Handling
        arch_mode = state.get("architecture_mode") or self.architecture_mode

        # Check for candidate early exit intent (e.g., "i have some work can you end this session")
        if is_candidate_exit_intent(candidate_message):
            self.candidate_early_exit = True
            interview_state.status = InterviewStatus.TERMINATED
            interview_state.termination_reason = "Candidate requested early exit / withdrawal from the interview."

            # Determine unaddressed topics based on current stage
            stage_val = interview_state.current_stage.value if hasattr(interview_state.current_stage, "value") else str(interview_state.current_stage)
            unaddressed = []
            if stage_val != "STAGE_5_COMMERCIALS_AND_CLOSING":
                unaddressed.append("security compliance & risk mitigation")
                unaddressed.append("integration architecture & downtime")
                unaddressed.append("commercial terms & contract review")
            unaddressed_str = ", ".join(unaddressed) if unaddressed else "final commercial terms"

            exit_response_text = (
                f"Understood. We all have tight schedules, so let's cut it here. "
                f"Keep in mind that we haven't touched on your {unaddressed_str}, "
                f"which are critical for our executive evaluation. I will note this session as incomplete. "
                f"Thank you for your time. [END_INTERVIEW]"
            )
            response = AIMessage(content=exit_response_text)
            self.turn_count = new_turn
            return {
                "messages": [response],
                "is_finished": True,
                "client_state": self.current_state.to_dict(),
                "state_events": [],
                "turn_count": new_turn,
                "interview_state": interview_state.to_dict(),
                "interview_events": [],
                "candidate_analysis": {},
                "fact_ledger": self.fact_ledger.to_list(),
                "claim_ledger": self.claim_ledger.to_list(),
                "behavioral_decision": {},
                "policy_mode": self.policy_mode,
                "memory_items": [],
                "knowledge_items": [],
                "commitments": [],
                "unresolved_items": [],
                "memory_mode": self.memory_mode,
                "architecture_mode": arch_mode,
            }

        if arch_mode == "STATIC_PROMPT":
            system_template = get_interviewer_system_prompt(
                self.role_context,
                self.topic,
                self.scenario,
                self.experience,
                self.style,
            )
            non_system_messages = [m for m in messages if not isinstance(m, SystemMessage)]
            full_messages = [SystemMessage(content=system_template)] + non_system_messages
            response = self.llm_with_tools.invoke(full_messages)
            is_finished = "[END_INTERVIEW]" in response.content
            if "[END_INTERVIEW]" in response.content:
                response.content = response.content.replace("[END_INTERVIEW]", "").strip()
            self.turn_count = new_turn
            return {
                "messages": [response],
                "is_finished": is_finished,
                "client_state": self.current_state.to_dict(),
                "state_events": [],
                "turn_count": new_turn,
                "interview_state": self.interview_state.to_dict(),
                "interview_events": [],
                "candidate_analysis": {},
                "fact_ledger": self.fact_ledger.to_list(),
                "claim_ledger": self.claim_ledger.to_list(),
                "behavioral_decision": {},
                "policy_mode": self.policy_mode,
                "memory_items": [],
                "knowledge_items": [],
                "commitments": [],
                "unresolved_items": [],
                "memory_mode": self.memory_mode,
                "architecture_mode": arch_mode,
            }

        elif arch_mode == "PERSONA_ONLY":
            system_template = get_interviewer_system_prompt(
                self.persona,
                self.topic,
                self.scenario,
                self.experience,
                self.style,
                client_state=None,
                interview_state=None,
                behavioral_decision=None,
                relevant_memories=None,
                knowledge_constraints=None,
                unresolved_context=None,
            )
            non_system_messages = [m for m in messages if not isinstance(m, SystemMessage)]
            full_messages = [SystemMessage(content=system_template)] + non_system_messages
            response = self.llm_with_tools.invoke(full_messages)
            is_finished = "[END_INTERVIEW]" in response.content
            if "[END_INTERVIEW]" in response.content:
                response.content = response.content.replace("[END_INTERVIEW]", "").strip()
            self.turn_count = new_turn
            return {
                "messages": [response],
                "is_finished": is_finished,
                "client_state": self.current_state.to_dict(),
                "state_events": [],
                "turn_count": new_turn,
                "interview_state": self.interview_state.to_dict(),
                "interview_events": [],
                "candidate_analysis": {},
                "fact_ledger": self.fact_ledger.to_list(),
                "claim_ledger": self.claim_ledger.to_list(),
                "behavioral_decision": {},
                "policy_mode": self.policy_mode,
                "memory_items": [],
                "knowledge_items": [],
                "commitments": [],
                "unresolved_items": [],
                "memory_mode": self.memory_mode,
                "architecture_mode": arch_mode,
            }

        elif arch_mode == "PERSONA_PLUS_STATE":
            stage_str = interview_state.current_stage.value if isinstance(interview_state.current_stage, InterviewStage) else str(interview_state.current_stage)
            analysis = self.analyzer.analyze(
                candidate_message=candidate_message,
                current_stage=stage_str,
                turn=new_turn,
                known_facts=self.fact_ledger.to_list(),
            )
            signals = map_analysis_to_signals(analysis)
            updated_state, event = self.state_manager.apply_signals(
                current_state=current_state,
                signals=signals,
                turn=new_turn,
                persona=self.persona,
            )
            self.current_state = updated_state
            self.turn_count = new_turn

            system_template = get_interviewer_system_prompt(
                self.persona,
                self.topic,
                self.scenario,
                self.experience,
                self.style,
                client_state=updated_state,
                interview_state=None,
                behavioral_decision=None,
                relevant_memories=None,
                knowledge_constraints=None,
                unresolved_context=None,
            )
            non_system_messages = [m for m in messages if not isinstance(m, SystemMessage)]
            full_messages = [SystemMessage(content=system_template)] + non_system_messages
            response = self.llm_with_tools.invoke(full_messages)
            is_finished = "[END_INTERVIEW]" in response.content
            if "[END_INTERVIEW]" in response.content:
                response.content = response.content.replace("[END_INTERVIEW]", "").strip()
            return {
                "messages": [response],
                "is_finished": is_finished,
                "client_state": updated_state.to_dict(),
                "state_events": [event.model_dump()],
                "turn_count": new_turn,
                "interview_state": self.interview_state.to_dict(),
                "interview_events": [],
                "candidate_analysis": analysis.to_dict(),
                "fact_ledger": self.fact_ledger.to_list(),
                "claim_ledger": self.claim_ledger.to_list(),
                "behavioral_decision": {},
                "policy_mode": self.policy_mode,
                "memory_items": [],
                "knowledge_items": [],
                "commitments": [],
                "unresolved_items": [],
                "memory_mode": self.memory_mode,
                "architecture_mode": arch_mode,
            }

        elif arch_mode == "PERSONA_PLUS_STATE_PLUS_INTERVIEW":
            stage_str = interview_state.current_stage.value if isinstance(interview_state.current_stage, InterviewStage) else str(interview_state.current_stage)
            analysis = self.analyzer.analyze(
                candidate_message=candidate_message,
                current_stage=stage_str,
                turn=new_turn,
                known_facts=self.fact_ledger.to_list(),
            )
            signals = map_analysis_to_signals(analysis)
            updated_state, event = self.state_manager.apply_signals(
                current_state=current_state,
                signals=signals,
                turn=new_turn,
                persona=self.persona,
            )
            self.current_state = updated_state
            self.turn_count = new_turn

            self.interview_state_manager.record_turn(interview_state)
            self.interview_state_manager.update_criteria_from_analysis(interview_state, analysis)
            transition_event = self.interview_state_manager.evaluate_stage_transition(interview_state, updated_state, self.persona_configuration)
            interview_events_out = [transition_event.to_dict()] if transition_event else []
            self.interview_state = interview_state

            system_template = get_interviewer_system_prompt(
                self.persona,
                self.topic,
                self.scenario,
                self.experience,
                self.style,
                client_state=updated_state,
                interview_state=interview_state,
                behavioral_decision=None,
                relevant_memories=None,
                knowledge_constraints=None,
                unresolved_context=None,
            )
            non_system_messages = [m for m in messages if not isinstance(m, SystemMessage)]
            full_messages = [SystemMessage(content=system_template)] + non_system_messages
            response = self.llm_with_tools.invoke(full_messages)
            is_finished = "[END_INTERVIEW]" in response.content or interview_state.status in [InterviewStatus.COMPLETED, InterviewStatus.TERMINATED]
            if "[END_INTERVIEW]" in response.content:
                response.content = response.content.replace("[END_INTERVIEW]", "").strip()
            return {
                "messages": [response],
                "is_finished": is_finished,
                "client_state": updated_state.to_dict(),
                "state_events": [event.model_dump()],
                "turn_count": new_turn,
                "interview_state": interview_state.to_dict(),
                "interview_events": interview_events_out,
                "candidate_analysis": analysis.to_dict(),
                "fact_ledger": self.fact_ledger.to_list(),
                "claim_ledger": self.claim_ledger.to_list(),
                "behavioral_decision": {},
                "policy_mode": self.policy_mode,
                "memory_items": [],
                "knowledge_items": [],
                "commitments": [],
                "unresolved_items": [],
                "memory_mode": self.memory_mode,
                "architecture_mode": arch_mode,
            }

        elif arch_mode == "PERSONA_PLUS_STATE_PLUS_INTERVIEW_PLUS_BEHAVIOR":
            stage_str = interview_state.current_stage.value if isinstance(interview_state.current_stage, InterviewStage) else str(interview_state.current_stage)
            analysis = self.analyzer.analyze(
                candidate_message=candidate_message,
                current_stage=stage_str,
                turn=new_turn,
                known_facts=self.fact_ledger.to_list(),
            )
            signals = map_analysis_to_signals(analysis)
            updated_state, event = self.state_manager.apply_signals(
                current_state=current_state,
                signals=signals,
                turn=new_turn,
                persona=self.persona,
            )
            self.current_state = updated_state
            self.turn_count = new_turn

            self.interview_state_manager.record_turn(interview_state)
            self.interview_state_manager.update_criteria_from_analysis(interview_state, analysis)
            transition_event = self.interview_state_manager.evaluate_stage_transition(interview_state, updated_state, self.persona_configuration)
            interview_events_out = [transition_event.to_dict()] if transition_event else []
            self.interview_state = interview_state

            active_mode = state.get("policy_mode") or self.policy_mode
            decision = self.policy_engine.evaluate(
                persona=self.persona,
                client_state=updated_state,
                interview_state=interview_state,
                candidate_analysis=analysis,
                turn=new_turn,
                candidate_message=candidate_message,
                policy_mode=active_mode,
                persona_config=self.persona_configuration,
            )
            self.current_decision = decision
            is_terminated_by_policy = decision.primary_action.action_type == ActionType.TERMINATE
            if is_terminated_by_policy:
                interview_state.status = InterviewStatus.TERMINATED
                interview_state.termination_reason = decision.primary_action.reason

            system_template = get_interviewer_system_prompt(
                self.persona,
                self.topic,
                self.scenario,
                self.experience,
                self.style,
                client_state=updated_state,
                interview_state=interview_state,
                behavioral_decision=decision,
                relevant_memories=None,
                knowledge_constraints=None,
                unresolved_context=None,
            )
            non_system_messages = [m for m in messages if not isinstance(m, SystemMessage)]
            full_messages = [SystemMessage(content=system_template)] + non_system_messages
            response = self.llm_with_tools.invoke(full_messages)
            is_finished = "[END_INTERVIEW]" in response.content or is_terminated_by_policy or interview_state.status in [InterviewStatus.COMPLETED, InterviewStatus.TERMINATED]
            if "[END_INTERVIEW]" in response.content:
                response.content = response.content.replace("[END_INTERVIEW]", "").strip()
            return {
                "messages": [response],
                "is_finished": is_finished,
                "client_state": updated_state.to_dict(),
                "state_events": [event.model_dump()],
                "turn_count": new_turn,
                "interview_state": interview_state.to_dict(),
                "interview_events": interview_events_out,
                "candidate_analysis": analysis.to_dict(),
                "fact_ledger": self.fact_ledger.to_list(),
                "claim_ledger": self.claim_ledger.to_list(),
                "behavioral_decision": decision.to_dict(),
                "policy_mode": active_mode,
                "memory_items": [],
                "knowledge_items": [],
                "commitments": [],
                "unresolved_items": [],
                "memory_mode": self.memory_mode,
                "architecture_mode": arch_mode,
            }

        # Phase 5: Semantic Candidate Behavior & Content Analysis
        analysis_start = time.time()
        stage_str = interview_state.current_stage.value if isinstance(interview_state.current_stage, InterviewStage) else str(interview_state.current_stage)
        analysis = self.analyzer.analyze(
            candidate_message=candidate_message,
            current_stage=stage_str,
            turn=new_turn,
            known_facts=self.fact_ledger.to_list(),
        )
        latency_ms = (time.time() - analysis_start) * 1000.0

        # Update Working Memory Ledgers
        for fact in analysis.extracted_facts:
            self.fact_ledger.add_or_update_fact(fact)
        for claim in analysis.extracted_claims:
            self.claim_ledger.add_claim(claim)

        # Ingest candidate turn into Conversational Memory Store (reconciles claims & detects contradictions)
        self.memory_store.record_candidate_turn(
            turn=new_turn,
            candidate_message=candidate_message,
            analysis=analysis,
            fact_ledger=self.fact_ledger,
            claim_ledger=self.claim_ledger,
        )

        # 1. Update Dynamic ClientState (Perception) via mapped InteractionSignals
        signals = map_analysis_to_signals(analysis)
        updated_state, event = self.state_manager.apply_signals(
            current_state=current_state,
            signals=signals,
            turn=new_turn,
            persona=self.persona,
        )

        self.current_state = updated_state
        self.turn_count = new_turn

        # 2. Update Interview State Machine (Lifecycle & Stages) via Semantic Analysis
        self.interview_state_manager.record_turn(interview_state)
        self.interview_state_manager.update_criteria_from_analysis(
            state=interview_state,
            analysis=analysis,
        )

        transition_event = self.interview_state_manager.evaluate_stage_transition(
            state=interview_state,
            client_state=updated_state,
            persona_config=self.persona_configuration,
        )

        interview_events_out = []
        if transition_event:
            interview_events_out.append(transition_event.to_dict())

        self.interview_state = interview_state

        # 3. Phase 6: Deterministic Behavioral Policy Engine Evaluation
        active_mode = state.get("policy_mode") or self.policy_mode
        active_memory_mode = state.get("memory_mode") or self.memory_mode
        decision = self.policy_engine.evaluate(
            persona=self.persona,
            client_state=updated_state,
            interview_state=interview_state,
            candidate_analysis=analysis,
            turn=new_turn,
            candidate_message=candidate_message,
            policy_mode=active_mode,
            persona_config=self.persona_configuration,
        )

        # Phase 7: Knowledge Boundary & Disclosure Permission Verification
        if decision.primary_action.action_type == ActionType.REVEAL_INFORMATION:
            target_topic = decision.primary_action.target or ""
            access_dec = self.knowledge_state.evaluate_access(
                topic=target_topic,
                candidate_trust=updated_state.trust,
                stage=interview_state.current_stage,
            )
            if not access_dec.allowed:
                decision.primary_action.action_type = ActionType.WITHHOLD_INFORMATION
                decision.primary_action.information_to_withhold = [target_topic]
                decision.primary_action.information_to_reveal = []
                decision.primary_action.reason = f"Knowledge access policy denied disclosure: {access_dec.reason}"
                decision.primary_action.objective = "protect_confidential_information"

        self.current_decision = decision

        # Check for policy-driven termination
        is_terminated_by_policy = decision.primary_action.action_type == ActionType.TERMINATE
        if is_terminated_by_policy:
            interview_state.status = InterviewStatus.TERMINATED
            interview_state.termination_reason = decision.primary_action.reason

        # Phase 7: Selective Memory Retrieval & Knowledge Context
        relevant_memories = None
        if active_memory_mode in ("structured", "full"):
            relevant_memories = self.memory_retriever.retrieve_relevant_memories(
                stage=interview_state.current_stage,
                selected_action=decision.primary_action,
                memory_store=self.memory_store,
                candidate_analysis=analysis,
                max_results=5,
            )

        unresolved_context = None
        knowledge_constraints = None
        if active_memory_mode == "full":
            # Knowledge constraints
            knowledge_constraints = (
                "1. Do NOT disclose confidential topics (exact budget, internal margins, unannounced roadmap).\n"
                "2. Maintain strict factual consistency with the company's verified technology stack and operational reality.\n"
                "3. Do NOT invent new company facts not provided in the World Model."
            )
            # Unresolved items context
            unresolved_lines = []
            open_questions = [q for q in self.memory_store.unresolved_questions if q.status == "UNRESOLVED"]
            for q in open_questions[-2:]:
                unresolved_lines.append(f"- [UNANSWERED QUESTION (Turn {q.source_turn})]: '{q.question}' remains unanswered by candidate.")
            open_objections = [o for o in self.memory_store.unresolved_objections if o.status in (ItemStatus.OPEN, ItemStatus.PARTIALLY_ADDRESSED)]
            for o in open_objections[-2:]:
                unresolved_lines.append(f"- [ACTIVE OBJECTION ({o.topic})]: {o.description}")
            active_commits = [c for c in self.memory_store.commitments if c.status == CommitmentStatus.PROMISED]
            for c in active_commits[-2:]:
                unresolved_lines.append(f"- [PENDING COMMITMENT (Turn {c.source_turn})]: {c.description}")
            if unresolved_lines:
                unresolved_context = "\n".join(unresolved_lines)

        # 4. Synthesize Response Generation Context with Selected Behavior & Memory
        system_template = get_interviewer_system_prompt(
            self.persona,
            self.topic,
            self.scenario,
            self.experience,
            self.style,
            client_state=updated_state,
            interview_state=interview_state,
            behavioral_decision=decision,
            relevant_memories=relevant_memories,
            knowledge_constraints=knowledge_constraints,
            unresolved_context=unresolved_context,
        )

        # Make sure current perception, stage context, and behavior instructions are reflected
        non_system_messages = [m for m in messages if not isinstance(m, SystemMessage)]
        full_messages = [SystemMessage(content=system_template)] + non_system_messages

        response = self.llm_with_tools.invoke(full_messages)

        # Phase 7: Post-Generation Response Consistency Validation
        if active_memory_mode == "full":
            val_result = self.consistency_validator.validate_response(
                response_text=response.content,
                world_registry=self.world_registry,
                knowledge_state=self.knowledge_state,
                memory_store=self.memory_store,
                selected_action=decision.primary_action,
                candidate_trust=updated_state.trust,
                stage=interview_state.current_stage,
            )
            if not val_result.is_valid:
                try:
                    storage.save_consistency_event(
                        session_id=self.session_id,
                        turn_number=new_turn,
                        violation_type=val_result.violation_type or "consistency_violation",
                        details=val_result.violation_details or "",
                        repaired=True,
                    )
                except Exception as e:
                    pass

                # Single retry with corrective prompt instruction
                corrective_msg = SystemMessage(
                    content=f"CONSISTENCY VIOLATION: {val_result.corrective_instructions}\nRegenerate your response immediately adhering to these constraints."
                )
                retry_messages = full_messages + [response, corrective_msg]
                try:
                    retry_resp = self.llm_with_tools.invoke(retry_messages)
                    second_val = self.consistency_validator.validate_response(
                        response_text=retry_resp.content,
                        world_registry=self.world_registry,
                        knowledge_state=self.knowledge_state,
                        memory_store=self.memory_store,
                        selected_action=decision.primary_action,
                        candidate_trust=updated_state.trust,
                        stage=interview_state.current_stage,
                    )
                    if second_val.is_valid:
                        response = retry_resp
                    else:
                        response.content = val_result.fallback_response or response.content
                except Exception:
                    response.content = val_result.fallback_response or response.content

        # Record stakeholder utterance and track commitments/unresolved questions
        self.memory_store.record_stakeholder_turn(
            turn=new_turn,
            stakeholder_message=response.content,
            selected_action=decision.primary_action,
        )

        # Check if the LLM output the END token or interview is completed/terminated
        is_finished = "[END_INTERVIEW]" in response.content or is_terminated_by_policy

        if "[END_INTERVIEW]" in response.content:
            cleaned_content = response.content.replace("[END_INTERVIEW]", "").strip()
            response.content = cleaned_content

        if interview_state.status in [InterviewStatus.COMPLETED, InterviewStatus.TERMINATED]:
            is_finished = True

        # 5. Persist Research Traces to SQLite
        try:
            storage.save_state_snapshot(
                session_id=self.session_id,
                turn_number=new_turn,
                state=updated_state,
                event_type=event.event_type,
                event_reason=event.reason,
            )
        except Exception as e:
            print(f"Warning: Failed to save post-turn state snapshot: {e}")

        if transition_event:
            try:
                storage.save_interview_stage_event(
                    session_id=self.session_id,
                    turn_number=new_turn,
                    from_stage=transition_event.from_stage.value if isinstance(transition_event.from_stage, InterviewStage) else transition_event.from_stage,
                    to_stage=transition_event.to_stage.value if isinstance(transition_event.to_stage, InterviewStage) else transition_event.to_stage,
                    reason=transition_event.reason,
                )
            except Exception as e:
                print(f"Warning: Failed to save interview stage event: {e}")

        try:
            storage.save_candidate_analysis(
                session_id=self.session_id,
                turn_number=new_turn,
                candidate_message=candidate_message,
                current_stage=stage_str,
                analysis=analysis,
                extracted_facts=analysis.extracted_facts,
                extracted_claims=analysis.extracted_claims,
                interaction_signals=signals,
                latency_ms=latency_ms,
            )
        except Exception as e:
            print(f"Warning: Failed to save candidate analysis research record: {e}")

        try:
            storage.save_behavior_decision(
                session_id=self.session_id,
                turn_number=new_turn,
                decision=decision,
            )
        except Exception as e:
            print(f"Warning: Failed to save behavior decision: {e}")

        # Persist memory items, commitments, and unresolved items
        for m_item in self.memory_store.memories[-3:]:
            try:
                storage.save_memory_item(self.session_id, m_item)
            except Exception:
                pass
        for c_item in self.memory_store.commitments[-1:]:
            try:
                storage.save_commitment(self.session_id, c_item)
            except Exception:
                pass
        for u_item in self.memory_store.unresolved_questions[-1:]:
            try:
                storage.save_unresolved_item(self.session_id, u_item, item_type="question")
            except Exception:
                pass
        for o_item in self.memory_store.unresolved_objections[-1:]:
            try:
                storage.save_unresolved_item(self.session_id, o_item, item_type="objection")
            except Exception:
                pass

        return {
            "messages": [response],
            "is_finished": is_finished,
            "client_state": updated_state.to_dict(),
            "state_events": [event.model_dump()],
            "turn_count": new_turn,
            "interview_state": interview_state.to_dict(),
            "interview_events": interview_events_out,
            "candidate_analysis": analysis.to_dict(),
            "fact_ledger": self.fact_ledger.to_list(),
            "claim_ledger": self.claim_ledger.to_list(),
            "behavioral_decision": decision.to_dict(),
            "policy_mode": active_mode,
            "memory_items": [m.to_dict() for m in self.memory_store.memories],
            "knowledge_items": [k.to_dict() for k in self.knowledge_state.get_all_items()],
            "commitments": [c.to_dict() for c in self.memory_store.commitments],
            "unresolved_items": [q.to_dict() for q in self.memory_store.unresolved_questions],
            "memory_mode": active_memory_mode,
        }

    def _judge_node(self, state: AgentState):
        messages = state["messages"]
        is_early_exit = getattr(self, "candidate_early_exit", False)

        if is_early_exit:
            stage_name = getattr(self.interview_state.current_stage, "value", str(self.interview_state.current_stage))
            early_exit_directive = f"""
CRITICAL EVALUATION DIRECTIVE - CANDIDATE WITHDREW EARLY:
The candidate requested to end the interview prematurely / withdrew early from the session at Stage: {stage_name}.
You MUST adhere to the following strict evaluation rules:
1. Overall Performance Summary & Score:
   - Mark the session status as **INCOMPLETE / EARLY CANDIDATE WITHDRAWAL**.
   - The candidate abandoned the interview before addressing essential stakeholder criteria (such as reliability, security, downtime, or commercial terms).
   - Their Overall Score MUST BE CAPPED AT A MAXIMUM OF 4/10 (e.g., 3/10 or 4/10). Under NO circumstances should an abandoned interview receive a passing score (5 or above).
2. Situation & Scenario Handling:
   - Explicitly evaluate their exit etiquette. In an enterprise meeting, an executive who abruptly terminates with "I have work, end this" without professional framing, acknowledging pending questions, or proposing concrete next steps forfeits credibility and deal momentum.
3. Domain Knowledge & Critical Gaps:
   - Clearly enumerate the critical topics and stages that were left completely unaddressed (e.g., security, integration downtime, SLAs, pricing).
4. Critical Areas for Improvement with Actionable Advice:
   - Provide concrete scripts and techniques on how an executive should professionally handle unexpected emergencies or scheduling conflicts (e.g., formally postponing with a confirmed callback window rather than abruptly walking away).
"""
            judge_system = f"{get_judge_system_prompt(self.topic)}\n\n{early_exit_directive}"
            report_header = "### 📊 Interview Complete (Candidate Withdrew Early)\n\n**Session Status: INCOMPLETE (Candidate Terminated Early)**\n\n**Here is your early exit evaluation report:**\n\n"
        else:
            judge_system = get_judge_system_prompt(self.topic)
            report_header = "### 📊 Interview Complete\n\n**Here is your evaluation report:**\n\n"

        # Extract only user and assistant messages for evaluation
        non_system_messages = [m for m in messages if not isinstance(m, SystemMessage)]
        full_messages = [SystemMessage(content=judge_system)] + non_system_messages
        response = self.llm.invoke(full_messages)

        # Prepend a header to make it clear this is the judge
        report_content = f"{report_header}{response.content}"
        return {"messages": [AIMessage(content=report_content)]}

    def _should_continue(self, state: AgentState):
        messages = state["messages"]
        last_message = messages[-1]

        # If the LLM made a tool call, route to tools
        if getattr(last_message, "tool_calls", []):
            return "tools"

        if state.get("is_finished"):
            return "judge"

        return END

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        tool_node = ToolNode(self.tools)

        workflow.add_node("interviewer", self._interviewer_node)
        workflow.add_node("tools", tool_node)
        workflow.add_node("judge", self._judge_node)

        workflow.set_entry_point("interviewer")
        workflow.add_conditional_edges(
            "interviewer",
            self._should_continue,
            {
                "tools": "tools",
                "judge": "judge",
                END: END,
            },
        )
        workflow.add_edge("tools", "interviewer")
        workflow.add_edge("judge", END)

        return workflow.compile(checkpointer=self.memory)

    def chat(self, message: str) -> str:
        try:
            config = {"configurable": {"thread_id": self.session_id}}

            incoming_messages = []
            if self.turn_count == 0 and hasattr(self, "_opening_message") and self._opening_message:
                incoming_messages.append(AIMessage(content=self._opening_message))
            incoming_messages.append(HumanMessage(content=message))

            inputs = {
                "messages": incoming_messages,
                "client_state": self.current_state.to_dict(),
                "state_events": [],
                "turn_count": self.turn_count,
                "interview_state": self.interview_state.to_dict(),
                "interview_events": [],
                "candidate_analysis": {},
                "fact_ledger": self.fact_ledger.to_list(),
                "claim_ledger": self.claim_ledger.to_list(),
                "is_finished": False,
                "architecture_mode": self.architecture_mode,
            }

            output = None
            for event in self.graph.stream(inputs, config=config, stream_mode="values"):
                output = event

            if output and "messages" in output:
                # Update current perception state from graph output if present
                if "client_state" in output:
                    raw_cs = output["client_state"]
                    self.current_state = ClientState(**raw_cs) if isinstance(raw_cs, dict) else raw_cs
                if "turn_count" in output:
                    self.turn_count = output["turn_count"]

                # Update current interview state from graph output if present
                if "interview_state" in output:
                    raw_is = output["interview_state"]
                    if isinstance(raw_is, dict):
                        criteria_dict = {}
                        for cid, cdata in raw_is.get("criteria", {}).items():
                            criteria_dict[cid] = StageCriterion(**cdata) if isinstance(cdata, dict) else cdata
                        history_list = [
                            StageTransitionEvent(**hevent) if isinstance(hevent, dict) else hevent
                            for hevent in raw_is.get("history", [])
                        ]
                        self.interview_state = InterviewState(
                            current_stage=raw_is.get("current_stage", InterviewStage.STAGE_1_OPENING_RAPPORT),
                            stage_turn_count=raw_is.get("stage_turn_count", 0),
                            total_turn_count=raw_is.get("total_turn_count", 0),
                            max_total_turns=raw_is.get("max_total_turns", 15),
                            status=raw_is.get("status", InterviewStatus.ACTIVE),
                            criteria=criteria_dict,
                            history=history_list,
                            termination_reason=raw_is.get("termination_reason"),
                        )
                    elif isinstance(raw_is, InterviewState):
                        self.interview_state = raw_is

                # Get the last AI message
                for msg in reversed(output["messages"]):
                    if isinstance(msg, AIMessage):
                        if not msg.tool_calls:
                            return msg.content

            return "Sorry, I encountered an error generating a response."
        except Exception as e:
            print(f"LLM Error: {e}")
            return f"[Mock AI] I'm a placeholder response because the real AI connection failed. Error: {e}"

    async def stream_chat(self, message: str):
        import asyncio
        # Run the synchronous chat method in a background thread to avoid blocking the event loop
        output = await asyncio.to_thread(self.chat, message)

        # Simulate streaming chunk by chunk
        chunk_size = 4
        i = 0
        while i < len(output):
            chunk = output[i:i+chunk_size]
            yield chunk
            await asyncio.sleep(0.01)
            i += chunk_size

    def _get_fallback_opening(self) -> str:
        role = self.role_id.upper()
        if "CEO" in role:
            return (
                "Thanks for taking the time to meet today. We have high expectations for this initiative, "
                "and my focus is strictly on strategic impact and enterprise valuation. Let's get straight to it—"
                f"give me the high-level picture of how your approach for '{self.topic}' moves the needle for our growth."
            )
        elif "CTO" in role:
            return (
                f"Thanks for jumping on. I've reviewed the outline for our {self.topic} session. "
                "From an architectural standpoint, I care about scalability, reliability, and technical tradeoffs. "
                "To kick us off, walk me through the high-level architecture and the core decisions behind it."
            )
        elif "HR" in role:
            return (
                "Hello, thanks for joining me today. I'm looking forward to learning more about your background "
                f"and experience. To get started with our {self.topic} conversation, could you tell me briefly about "
                "a recent project you led and how you handled key team and stakeholder dynamics?"
            )
        elif "SALES" in role:
            return (
                "Good to connect today. We're evaluating solutions in this space, but our pipeline and ROI requirements "
                "are aggressive. Let's dive right in—what is the core differentiator of your offering, and why should we prioritize this now?"
            )
        else:
            return (
                f"Thanks for joining today's session on {self.topic}. Let's jump right in—"
                "could you provide an overview of your strategy and how you plan to tackle this scenario?"
            )

    def generate_opening(self) -> str:
        """Generate an authentic, in-character opening turn for the interview."""
        if hasattr(self, "_opening_message") and self._opening_message:
            return self._opening_message

        try:
            system_prompt = get_interviewer_system_prompt(
                self.persona,
                self.topic,
                self.scenario,
                self.experience,
                self.style,
                client_state=self.current_state,
                interview_state=self.interview_state,
                behavioral_decision=None,
                relevant_memories=None,
                knowledge_constraints=None,
                unresolved_context=None,
            )

            opening_directive = (
                f"You are initiating the meeting/interview as {self.persona.profile.title} ({self.role_id}).\n"
                f"Topic: {self.topic}\n"
                f"Scenario Context: {self.scenario}\n\n"
                "Instructions for your opening turn:\n"
                "1. Greet the candidate in-character with the appropriate tone for your role.\n"
                "2. State the context/purpose of today's meeting based on the topic and scenario.\n"
                "3. Take charge and ask your first strategic opening question or challenge to start the conversation.\n"
                "CRITICAL CONSTRAINTS:\n"
                "- Never dump internal metadata or recite traits (e.g., do NOT say 'Hello, I am the CEO. Visionary and results-oriented executive').\n"
                "- Do NOT passively ask 'What would you like to start with?'. YOU take the lead.\n"
                "- Do NOT reveal you are an AI model.\n"
                "- Keep your opening punchy, authoritative, and concise (under 60 words)."
            )

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"[SYSTEM DIRECTIVE: Initiate the conversation. {opening_directive}]"),
            ]

            response = self.llm.invoke(messages)
            opening_text = response.content.strip()

            if "[END_INTERVIEW]" in opening_text:
                opening_text = opening_text.replace("[END_INTERVIEW]", "").strip()

            if not opening_text:
                opening_text = self._get_fallback_opening()

            self._opening_message = opening_text
            storage.save_interaction(self.session_id, "ai", opening_text)
            return opening_text
        except Exception as e:
            print(f"Error generating dynamic opening: {e}")
            opening_text = self._get_fallback_opening()
            self._opening_message = opening_text
            storage.save_interaction(self.session_id, "ai", opening_text)
            return opening_text

    async def stream_opening(self):
        """Stream the dynamic opening message chunk-by-chunk."""
        import asyncio
        output = await asyncio.to_thread(self.generate_opening)

        chunk_size = 4
        i = 0
        while i < len(output):
            chunk = output[i:i+chunk_size]
            yield chunk
            await asyncio.sleep(0.01)
            i += chunk_size

    def get_persona_configuration(self) -> PersonaConfiguration:
        """Return the resolved persona configuration for this simulated stakeholder."""
        return self.persona_configuration

    def generate_coaching_report(self) -> StructuredCoachingReport:
        """Generate a structured, rubric-based post-interview coaching report (Priority P0)."""
        interactions = storage.get_interactions(self.session_id)
        candidate_analyses = storage.get_candidate_analyses(self.session_id)
        cs = self.current_state

        # 1. Calculate overall score (0 - 100) based on dynamic perception state
        trust_pts = cs.trust * 30.0
        skep_pts = (1.0 - cs.skepticism) * 20.0
        pat_pts = cs.patience * 15.0
        risk_pts = (1.0 - cs.perceived_risk) * 15.0
        frust_pts = (1.0 - cs.frustration) * 20.0
        raw_score = int(round(trust_pts + skep_pts + pat_pts + risk_pts + frust_pts))
        overall_score = max(10, min(100, raw_score))

        # 2. Letter grade
        if overall_score >= 90:
            letter_grade = "A+"
        elif overall_score >= 82:
            letter_grade = "A"
        elif overall_score >= 74:
            letter_grade = "B"
        elif overall_score >= 65:
            letter_grade = "C"
        elif overall_score >= 50:
            letter_grade = "D"
        else:
            letter_grade = "F"

        # 3. Outcome verdict
        is_candidate_exit = getattr(self, "candidate_early_exit", False) or (
            self.interview_state.status == InterviewStatus.TERMINATED
            and "Candidate requested early exit" in (self.interview_state.termination_reason or "")
        )

        if is_candidate_exit:
            overall_score = min(35, overall_score)
            letter_grade = "F"
            outcome_verdict = "Candidate Walkout / Incomplete Session"
            outcome_summary = (
                f"The candidate abruptly withdrew from the session at {self.interview_state.current_stage.value}. "
                f"Crucial stakeholder criteria (including security, risk mitigation, and closing) remained completely unaddressed."
            )
        else:
            is_terminated = (
                self.interview_state.status == InterviewStatus.TERMINATED
                or (cs.frustration >= 0.85 and cs.patience <= 0.20)
            )
            if is_terminated:
                outcome_verdict = "Stakeholder Walkout / Premature Termination"
                outcome_summary = (
                    f"The {self.role_id} terminated the conversation early. Critical friction arose around "
                    f"frustration ({cs.frustration:.2f}) and depleted patience ({cs.patience:.2f})."
                )
            elif overall_score >= 80:
                outcome_verdict = "Follow-up Secured / Strong Executive Buy-in"
                outcome_summary = (
                    f"The {self.role_id} gained high confidence ({cs.confidence_in_candidate:.2f}) and trust ({cs.trust:.2f}). "
                    f"Next steps for a technical demo or contract review were successfully unlocked."
                )
            elif overall_score >= 65:
                outcome_verdict = "Conditional Follow-up / Pending Due Diligence"
                outcome_summary = (
                    f"The {self.role_id} remains moderately interested, but skepticism ({cs.skepticism:.2f}) or "
                    f"perceived risk ({cs.perceived_risk:.2f}) requires concrete evidence before final commitment."
                )
            else:
                outcome_verdict = "Deal Declined / Opportunity Lost"
                outcome_summary = (
                    f"The {self.role_id} was unconvinced by value claims and perceived excessive organizational risk ({cs.perceived_risk:.2f})."
                )

        # 4. Dimension Subscores
        clarity_score = int(round(min(100, max(15, (cs.engagement * 50 + (1.0 - cs.frustration) * 50)))))
        objection_score = int(round(min(100, max(15, (1.0 - cs.skepticism) * 60 + cs.patience * 40))))
        value_score = int(round(min(100, max(15, cs.interest * 60 + cs.trust * 40))))
        domain_score = int(round(min(100, max(15, cs.confidence_in_candidate * 70 + cs.trust * 30))))
        composure_score = int(round(min(100, max(15, cs.patience * 50 + (1.0 - cs.frustration) * 50))))

        subscores = [
            FeedbackSubscore(name="Communication Clarity", score=clarity_score, description="Directness, brevity, and structure of answers"),
            FeedbackSubscore(name="Objection Handling", score=objection_score, description="Defusing skepticism and validating stakeholder concerns"),
            FeedbackSubscore(name="Value & ROI Articulation", score=value_score, description="Quantifying business impact and strategic alignment"),
            FeedbackSubscore(name="Domain Knowledge Depth", score=domain_score, description="Technical depth, architectural tradeoffs, and authority"),
            FeedbackSubscore(name="Composure Under Pressure", score=composure_score, description="Maintaining executive presence when challenged"),
        ]

        # 5. Extract Strengths & Weaknesses with "What you should have said instead"
        strengths = []
        weaknesses = []

        for ana in candidate_analyses:
            an_data = ana.get("analysis", {})
            user_msg = ana.get("candidate_message", "")
            rq = an_data.get("response_quality", {})
            sb = an_data.get("sales_behavior", {})

            if rq.get("unprofessional_behavior"):
                weaknesses.append(FeedbackWeakness(
                    title="Inappropriate / Defensive Tone",
                    description="Response contained unprofessional, abrasive, or overly defensive phrasing that immediately broke executive trust.",
                    quote=user_msg[:120] + ("..." if len(user_msg) > 120 else ""),
                    recommended_alternative="I understand your concern completely. Let me address the core risk directly and explain the safeguards we have in place.",
                ))
            elif rq.get("evasive") or rq.get("vague"):
                weaknesses.append(FeedbackWeakness(
                    title="Vague or Evasive Explanation",
                    description="Answer lacked concrete numbers or direct answers, triggering stakeholder skepticism.",
                    quote=user_msg[:120] + ("..." if len(user_msg) > 120 else ""),
                    recommended_alternative="To give you the exact specifics: our typical timeline is 6 to 8 weeks, with zero downtime during cutover and a dedicated migration engineer.",
                ))
            elif rq.get("unsupported_claim"):
                weaknesses.append(FeedbackWeakness(
                    title="Unsupported Assertion",
                    description="Bold performance or ROI claims were made without providing proof points or architectural rationale.",
                    quote=user_msg[:120] + ("..." if len(user_msg) > 120 else ""),
                    recommended_alternative="We achieved a 42% cost reduction with our enterprise clients by rightsizing compute clusters and automating cold storage tiering.",
                ))

            if rq.get("evidence_backed") or sb.get("value_articulated") or sb.get("discovery_question"):
                strengths.append(FeedbackStrength(
                    title="Strong Evidence & Value Alignment",
                    description="Directly tied capabilities to business pain points with clear operational context.",
                    quote=user_msg[:120] + ("..." if len(user_msg) > 120 else ""),
                ))

        # Default fallbacks if none detected
        if not strengths:
            strengths.append(FeedbackStrength(
                title="Professional Engagement",
                description="Maintained conversational momentum and engaged the stakeholder across the primary topic agenda.",
                quote=interactions[1]["message"][:100] if len(interactions) > 1 else None,
            ))
        if not weaknesses:
            weaknesses.append(FeedbackWeakness(
                title="Sharpen Strategic Concision",
                description="Executive stakeholders appreciate concise answers front-loading the business impact before diving into implementation details.",
                quote=None,
                recommended_alternative="Lead with the metric impact: 'We reduce operational overhead by 30%,' followed by the specific mechanism.",
            ))

        tactical_takeaways = [
            f"Tailor answers to the {self.role_id}'s primary driver: prioritize high-level ROI and enterprise valuation over granular operational details.",
            "Acknowledge objections before answering: say 'That is a valid concern' to disarm skepticism before explaining your solution.",
            "Quantify claims with verifiable metrics, timeframes, or reference case studies to prevent perceived risk from escalating.",
        ]

        # 6. Generate Markdown Report
        md_lines = [
            f"# 📊 Elevate Coaching & Performance Report",
            f"**Session**: {self.session_id} | **Role**: {self.role_id} | **Topic**: {self.topic}",
            f"\n## Overall Score: {overall_score}/100 ({letter_grade})",
            f"**Verdict**: {outcome_verdict}",
            f"\n{outcome_summary}",
            f"\n### Core Performance Dimensions",
        ]
        for sub in subscores:
            md_lines.append(f"- **{sub.name}**: {sub.score}/100 — *{sub.description}*")

        md_lines.append(f"\n### Key Strengths")
        for st in strengths:
            quote_txt = f"\n  > *\"{st.quote}\"*" if st.quote else ""
            md_lines.append(f"- **{st.title}**: {st.description}{quote_txt}")

        md_lines.append(f"\n### Critical Improvement Areas & Suggested Alternatives")
        for wk in weaknesses:
            quote_txt = f"\n  > Original: *\"{wk.quote}\"*" if wk.quote else ""
            alt_txt = f"\n  > 💡 **Recommended Alternative**: *\"{wk.recommended_alternative}\"*" if wk.recommended_alternative else ""
            md_lines.append(f"- **{wk.title}**: {wk.description}{quote_txt}{alt_txt}")

        md_lines.append(f"\n### Actionable Next Steps")
        for t in tactical_takeaways:
            md_lines.append(f"1. {t}")

        markdown_report = "\n".join(md_lines)

        report = StructuredCoachingReport(
            session_id=self.session_id,
            role=self.role_id,
            topic=self.topic,
            scenario=self.scenario,
            overall_score=overall_score,
            letter_grade=letter_grade,
            outcome_verdict=outcome_verdict,
            outcome_summary=outcome_summary,
            subscores=subscores,
            strengths=strengths,
            weaknesses=weaknesses,
            tactical_takeaways=tactical_takeaways,
            markdown_report=markdown_report,
        )

        # Save to SQLite
        try:
            storage.save_evaluation(self.session_id, report.model_dump_json())
        except Exception as e:
            print(f"Warning: Failed to save structured report to SQLite: {e}")

        return report

    def rewind_turn(self) -> RewindResponse:
        """Roll back the last turn: removes the last user & assistant messages, restores prior state (Priority P1)."""
        # 1. Update SQLite
        storage.rewind_last_turn(self.session_id)

        # 2. Roll back in-memory counters
        if self.turn_count > 0:
            self.turn_count -= 1
        if self.interview_state.total_turn_count > 0:
            self.interview_state.total_turn_count -= 1
        if self.interview_state.stage_turn_count > 0:
            self.interview_state.stage_turn_count -= 1

        # 3. Restore perception state from latest snapshot in storage
        snapshots = storage.get_state_history(self.session_id)
        if snapshots:
            last_snap = snapshots[-1].get("state", {})
            self.current_state = ClientState(**last_snap)
        else:
            self.current_state = ClientStateManager().initialize_state(self.persona, style=self.style)

        # 4. Fetch updated interactions
        interactions = storage.get_interactions(self.session_id)

        return RewindResponse(
            session_id=self.session_id,
            status="success",
            restored_turn=self.turn_count,
            restored_state=self.current_state.to_dict(),
            messages=interactions,
            system_notice=f"Turn rewound successfully. Restored to Turn {self.turn_count}.",
        )

    def generate_coaching_hint(self) -> CoachingHintResponse:
        """Generate a concise real-time tactical hint for the current turn (Priority P1)."""
        cs = self.current_state
        stage = self.interview_state.current_stage
        role = self.role_id

        if cs.frustration >= 0.60:
            focus_area = "De-escalating Stakeholder Frustration"
            hint = (
                f"The {role} is becoming impatient or frustrated ({cs.frustration:.2f}). "
                "Keep your next answer concise, directly address their question without preamble, and validate their concern."
            )
            perception = f"Frustration is elevated ({cs.frustration:.2f}). Patience is low ({cs.patience:.2f})."
        elif cs.skepticism >= 0.65:
            focus_area = "Addressing Skepticism & Providing Evidence"
            hint = (
                f"The {role} doubts your claims (skepticism: {cs.skepticism:.2f}). "
                "Provide a specific metric, case study, or technical mechanism rather than broad assertions."
            )
            perception = f"Skepticism is high ({cs.skepticism:.2f}). Needs concrete validation."
        elif cs.perceived_risk >= 0.60:
            focus_area = "Mitigating Perceived Risk"
            hint = (
                f"The {role} sees significant risk in this proposal ({cs.perceived_risk:.2f}). "
                "Highlight fallback plans, security controls, or phased implementation to lower risk."
            )
            perception = f"Perceived risk is concerning ({cs.perceived_risk:.2f})."
        elif "STAGE_1" in stage:
            focus_area = "Building Rapport & Setting Agenda"
            hint = f"Establish credibility with the {role} and clearly outline the strategic purpose of today's discussion."
            perception = "Initial rapport formation."
        elif "STAGE_2" in stage:
            focus_area = "Uncovering Core Business Pain"
            hint = f"Ask discovery questions to uncover the {role}'s top operational headaches and priorities before pitching."
            perception = f"Engaged ({cs.engagement:.2f}), awaiting discovery."
        elif "STAGE_5" in stage:
            focus_area = "Securing Next Steps & Commercial Alignment"
            hint = f"Summarize key value points and propose a clear, low-friction next step (such as a 30-minute technical deep-dive or pilot)."
            perception = f"Receptive (interest: {cs.interest:.2f}). Ready for close."
        else:
            focus_area = "Aligning Solution to Pain Points"
            hint = f"Directly map your capabilities to the specific challenges the {role} mentioned earlier."
            perception = f"Trust: {cs.trust:.2f}, Interest: {cs.interest:.2f}."

        return CoachingHintResponse(
            session_id=self.session_id,
            hint=hint,
            focus_area=focus_area,
            current_stakeholder_perception=perception,
        )

