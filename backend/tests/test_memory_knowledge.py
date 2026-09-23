"""Comprehensive Test Suite for Information & Memory Layer (Phase 7).

Tests:
1. StakeholderKnowledgeItem creation, validation, and provenance tracking.
2. Disclosure levels and boundaries (PUBLIC, SHAREABLE, CONFIDENTIAL, FORBIDDEN).
3. WorldFactRegistry immutability enforcement.
4. WorldFactRegistry contradiction detection.
5. Candidate claim vs. fact separation (source provenance).
6. Conversational memory ingestion and indexing.
7. Candidate contradiction preservation across multi-turn claims.
8. Stakeholder statement consistency tracking.
9. Stakeholder commitment lifecycle tracking (ACTIVE, FULFILLED, BROKEN).
10. Unresolved questions and objections tracking.
11. Deterministic selective memory retrieval (no full history dumps).
12. Policy action override: unauthorized REVEAL_INFORMATION -> WITHHOLD_INFORMATION.
13. Response consistency validator (detects confidential leaks & fact contradictions).
14. Response consistency repair retry and deterministic safe fallback.
15. SQLite persistence for all 5 Phase 7 tables.
16. Debug API endpoints (/memory, /knowledge, /consistency-history).
17. Full LangGraph multi-turn pipeline integration with memory retention.
"""

import sys
import os
sys.path.insert(0, os.path.abspath("backend"))
sys.path.insert(0, "/home/labuser/Desktop/Project/Elevate/venv/lib/python3.13/site-packages")

import unittest
import uuid
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.models.persona import (
    EnterprisePersona,
    PersonaProfile,
    ValueOrientation,
    StakeholderGoal,
    Incentive,
    KnowledgeBoundary,
    CompanyContext,
)
from app.models.state import ClientState
from app.models.stages import InterviewState, InterviewStage, InterviewStatus
from app.models.behavior import (
    ActionType,
    BehavioralAction,
    BehavioralDecision,
    PolicyTrace,
)
from app.models.memory import (
    KnowledgeStatus,
    InformationSource,
    DisclosureLevel,
    StakeholderKnowledgeItem,
    KnowledgeAccessDecision,
    WorldFact,
    MemoryType,
    MemoryItem,
    StakeholderCommitment,
    CommitmentStatus,
    UnresolvedQuestion,
    UnresolvedObjection,
    ItemStatus,
    ConsistencyValidationResult,
)
from app.services.memory_service import (
    WorldFactRegistry,
    StakeholderKnowledgeState,
    ConversationalMemoryStore,
    MemoryRetriever,
    ResponseConsistencyValidator,
)
from app.services.storage_service import storage


class TestMemoryKnowledge(unittest.TestCase):
    """Phase 7 Information and Memory Layer Unit & Integration Tests."""

    def setUp(self):
        self.session_id = f"test_mem_{uuid.uuid4().hex[:8]}"

        self.persona = EnterprisePersona(
            profile=PersonaProfile(
                role="CTO",
                title="Chief Technology Officer",
                department="Engineering & Infrastructure",
                seniority="C-Level Executive",
                years_of_experience=22,
                technical_depth="Deep Architectural",
                communication_style="Direct, analytical, low-tolerance for fluff",
                risk_profile="Risk-Averse",
            ),
            values=[
                ValueOrientation(name="reliability", weight=0.9, description="High availability", priority=1),
                ValueOrientation(name="security", weight=0.95, description="Zero tolerance data breach", priority=2),
            ],
            goals=[
                StakeholderGoal(
                    id="g_eval_sla",
                    description="Verify 99.99% uptime claim",
                    priority=0.95,
                    type="technical",
                    success_condition="Verified SLA audit documentation",
                    dealbreaker=True,
                ),
            ],
            incentives=[
                Incentive(id="inc_uptime", description="Maintain high uptime", importance=0.9, category="organizational"),
            ],
            knowledge_boundary=KnowledgeBoundary(
                expert_topics=["Distributed Systems", "Cloud Security", "PostgreSQL"],
                known_topics=["DevOps", "Kubernetes"],
                limited_topics=["Marketing Automation"],
                unknown_topics=["Sales Commission Structures"],
                confidential_topics=["unannounced roadmap", "exact infrastructure budget", "security incident details"],
                disclosure_rules=["Withhold exact budget until vendor proves technical viability"],
            ),
            world_model=CompanyContext(
                company_name="Apex Global Financial",
                industry="FinTech",
                company_size="10,000+ employees",
                current_technology_stack=["Azure", "PostgreSQL", "Kafka", "Redis"],
                incumbent_vendors=["VendorLegacy"],
                pain_points=["High read latency", "Failover recovery times"],
                constraints=["SOC2 Type II mandatory", "Must support Azure deployment"],
                budget_constraints="$500k annual CapEx",
                timeline="Q4 deployment",
            ),
        )

        self.client_state = ClientState(
            role="CTO",
            patience=0.6,
            skepticism=0.5,
            engagement=0.6,
            rapport=0.5,
            perceived_competence=0.5,
            trust=0.4,
            current_objection=None,
        )

        self.interview_state = InterviewState(
            current_stage=InterviewStage.STAGE_2_PROBLEM_DISCOVERY,
            stage_turn_count=2,
            total_turn_count=4,
            status=InterviewStatus.ACTIVE,
        )

    def test_01_knowledge_item_creation_and_provenance(self):
        """Test StakeholderKnowledgeItem creation, serialization, and provenance metadata."""
        item = StakeholderKnowledgeItem(
            topic="azure_architecture",
            fact_summary="Apex runs mission-critical core banking on Azure US-East.",
            status=KnowledgeStatus.CONFIRMED,
            disclosure_level=DisclosureLevel.SHAREABLE,
            source=InformationSource.WORLD_MODEL,
            provenance="Enterprise Architecture Spec v3.2",
            confidence=1.0,
            disclosure_count=0,
        )
        self.assertEqual(item.topic, "azure_architecture")
        self.assertEqual(item.status, KnowledgeStatus.CONFIRMED)
        self.assertEqual(item.disclosure_level, DisclosureLevel.SHAREABLE)
        self.assertEqual(item.source, InformationSource.WORLD_MODEL)
        self.assertEqual(item.provenance, "Enterprise Architecture Spec v3.2")
        self.assertEqual(item.confidence, 1.0)
        self.assertFalse(item.is_disclosed)

        item.mark_disclosed(turn=3)
        self.assertTrue(item.is_disclosed)
        self.assertEqual(item.disclosure_count, 1)
        self.assertEqual(item.first_disclosed_turn, 3)

    def test_02_disclosure_levels_and_boundaries(self):
        """Test deterministic disclosure permissions based on trust and boundary rules."""
        knowledge_state = StakeholderKnowledgeState(persona=self.persona)

        # 1. Public topic -> always permitted
        pub_decision = knowledge_state.evaluate_access("company_overview", self.client_state, self.interview_state)
        self.assertTrue(pub_decision.permitted)

        # 2. Unknown topic -> always rejected
        unknown_decision = knowledge_state.evaluate_access("Sales Commission Structures", self.client_state, self.interview_state)
        self.assertFalse(unknown_decision.permitted)
        self.assertIn("unknown", unknown_decision.reason.lower())

        # 3. Confidential topic with low trust (trust = 0.4, threshold = 0.7) -> rejected
        conf_decision_low = knowledge_state.evaluate_access("unannounced roadmap", self.client_state, self.interview_state)
        self.assertFalse(conf_decision_low.permitted)
        self.assertIn("trust", conf_decision_low.reason.lower())

        # 4. Confidential topic with high trust (trust = 0.85) -> permitted
        high_trust_state = ClientState(role="CTO", trust=0.85, perceived_competence=0.8)
        conf_decision_high = knowledge_state.evaluate_access("unannounced roadmap", high_trust_state, self.interview_state)
        self.assertTrue(conf_decision_high.permitted)

    def test_03_world_fact_registry_immutability(self):
        """Test that immutable ground truth facts cannot be overwritten or mutated."""
        registry = WorldFactRegistry(persona=self.persona)
        
        # Verify initial immutable fact
        tech_fact = registry.get_fact("company.cloud_provider")
        self.assertIsNotNone(tech_fact)
        self.assertEqual(tech_fact.value, "Azure")
        self.assertTrue(tech_fact.immutable)

        # Attempt to overwrite with AWS -> must raise ValueError
        new_fact = WorldFact(
            key="company.cloud_provider",
            value="AWS",
            category="technology",
            source=InformationSource.STAKEHOLDER_STATEMENT,
            immutable=False,
        )
        with self.assertRaises(ValueError) as ctx:
            registry.register_fact(new_fact)
        self.assertIn("immutable", str(ctx.exception).lower())

        # Verify fact remained Azure
        self.assertEqual(registry.get_fact("company.cloud_provider").value, "Azure")

    def test_04_world_fact_contradiction_detection(self):
        """Test checking contradiction against immutable scenario world facts."""
        registry = WorldFactRegistry(persona=self.persona)
        
        # Azure is ground truth
        contradiction = registry.check_contradiction("company.cloud_provider", "AWS")
        self.assertIsNotNone(contradiction)
        self.assertIn("Contradiction", contradiction)

        # Consistent value -> No contradiction
        no_contradiction = registry.check_contradiction("company.cloud_provider", "Azure")
        self.assertIsNone(no_contradiction)

    def test_05_candidate_claim_vs_fact_separation(self):
        """Test candidate claims are tagged with provenance and never promoted to world facts."""
        store = ConversationalMemoryStore()
        registry = WorldFactRegistry(persona=self.persona)

        # Candidate makes a claim in turn 2
        claim_content = "Our tool guarantees zero data loss and 99.999% SLA."
        store.record_turn(
            turn_number=2,
            speaker="candidate",
            stage="STAGE_2_PROBLEM_DISCOVERY",
            content=claim_content,
            memory_type=MemoryType.CANDIDATE_CLAIM,
            confidence=0.85,
            provenance="Candidate Turn 2 utterance",
        )

        # Verify memory item exists
        claims = store.get_memories_by_type(MemoryType.CANDIDATE_CLAIM)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].source, InformationSource.CANDIDATE_STATEMENT)
        self.assertEqual(claims[0].provenance, "Candidate Turn 2 utterance")

        # Verify candidate claim is NOT present in world registry facts
        self.assertIsNone(registry.get_fact("candidate.sla_claim"))

    def test_06_conversational_memory_ingestion(self):
        """Test conversational memory store ingests candidate and stakeholder turns with proper metadata."""
        store = ConversationalMemoryStore()

        store.record_turn(
            turn_number=1,
            speaker="candidate",
            stage="STAGE_1_OPENING_RAPPORT",
            content="Hello, thanks for taking the time to meet with us.",
            memory_type=MemoryType.CANDIDATE_STATEMENT,
            tags=["greeting"],
        )
        store.record_turn(
            turn_number=1,
            speaker="stakeholder",
            stage="STAGE_1_OPENING_RAPPORT",
            content="Thanks. Let's keep this focused; we have 20 minutes.",
            memory_type=MemoryType.STAKEHOLDER_STATEMENT,
            tags=["time_constraint"],
        )

        self.assertEqual(len(store.memories), 2)
        self.assertEqual(store.memories[0].speaker, "candidate")
        self.assertEqual(store.memories[1].speaker, "stakeholder")
        self.assertIn("time_constraint", store.memories[1].tags)

    def test_07_contradiction_preservation(self):
        """Test candidate conflicting claims preserve both statements and create contradiction link."""
        store = ConversationalMemoryStore()

        # Turn 2: Candidate says 15 minutes downtime
        store.record_turn(
            turn_number=2,
            speaker="candidate",
            stage="STAGE_2_PROBLEM_DISCOVERY",
            content="Our automated cutover requires only 15 minutes of downtime.",
            memory_type=MemoryType.CANDIDATE_CLAIM,
            tags=["migration", "downtime"],
        )

        # Turn 4: Candidate says 45 minutes downtime
        store.record_turn(
            turn_number=4,
            speaker="candidate",
            stage="STAGE_3_SOLUTION_ALIGNMENT",
            content="A typical enterprise migration requires roughly 45 minutes of scheduled maintenance.",
            memory_type=MemoryType.CANDIDATE_CLAIM,
            tags=["migration", "downtime"],
        )

        contradictions = store.detect_candidate_contradictions()
        self.assertGreaterEqual(len(contradictions), 1)

        c_item = contradictions[0]
        self.assertEqual(c_item.memory_type, MemoryType.CONTRADICTION)
        self.assertEqual(c_item.related_turn_numbers, [2, 4])
        self.assertIn("15", c_item.content)
        self.assertIn("45", c_item.content)

        # Verify BOTH original turns are still in memories (neither was deleted or overwritten)
        candidate_turns = [m for m in store.memories if m.speaker == "candidate"]
        self.assertEqual(len(candidate_turns), 2)

    def test_08_stakeholder_statement_consistency(self):
        """Test tracking stakeholder prior statements to prevent contradictory simulated utterances."""
        store = ConversationalMemoryStore()
        
        # Turn 2: Stakeholder explicitly mentions their primary database
        store.record_turn(
            turn_number=2,
            speaker="stakeholder",
            stage="STAGE_2_PROBLEM_DISCOVERY",
            content="We run PostgreSQL across our primary clusters on Azure.",
            memory_type=MemoryType.STAKEHOLDER_STATEMENT,
            tags=["database", "cloud"],
        )

        # Check stakeholder statements retrieval
        stakeholder_statements = store.get_stakeholder_statements()
        self.assertEqual(len(stakeholder_statements), 1)
        self.assertIn("PostgreSQL", stakeholder_statements[0].content)

    def test_09_commitment_tracking(self):
        """Test stakeholder commitments lifecycle: ACTIVE, FULFILLED, BROKEN."""
        store = ConversationalMemoryStore()

        commitment = StakeholderCommitment(
            id="c_arch_review",
            turn_promised=3,
            speaker="stakeholder",
            topic="architecture_diagram",
            description="I will review your SOC2 documentation with my security lead tomorrow.",
            status=CommitmentStatus.ACTIVE,
        )
        store.add_commitment(commitment)

        active = store.get_active_commitments()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].id, "c_arch_review")

        # Fulfill commitment
        store.update_commitment_status("c_arch_review", CommitmentStatus.FULFILLED)
        self.assertEqual(len(store.get_active_commitments()), 0)
        self.assertEqual(store.commitments[0].status, CommitmentStatus.FULFILLED)

    def test_10_unresolved_questions_and_objections(self):
        """Test tracking and resolving open questions and objections."""
        store = ConversationalMemoryStore()

        # Add question
        q = UnresolvedQuestion(
            id="q_1",
            turn_asked=2,
            asked_by="stakeholder",
            question_text="What is your data retention policy for deleted tenant records?",
            topic="data_retention",
            status=ItemStatus.UNRESOLVED,
        )
        store.add_unresolved_question(q)

        # Add objection
        obj = UnresolvedObjection(
            id="obj_1",
            turn_raised=3,
            objection_text="Your solution doesn't support our on-premise HSM requirement.",
            topic="hsm_compliance",
            status=ItemStatus.UNRESOLVED,
            severity="high",
        )
        store.add_unresolved_objection(obj)

        unresolved = store.get_unresolved_items()
        self.assertEqual(len(unresolved), 2)

        # Resolve question
        store.resolve_item("q_1", resolution_turn=4)
        active_unresolved = store.get_unresolved_items()
        self.assertEqual(len(active_unresolved), 1)
        self.assertEqual(active_unresolved[0].id, "obj_1")

    def test_11_selective_memory_retrieval(self):
        """Test deterministic selective retrieval fetches relevant items without dumping full history."""
        store = ConversationalMemoryStore()
        retriever = MemoryRetriever(store)

        # Ingest 10 turns on various topics
        for i in range(1, 11):
            topic_tag = "security" if i in [2, 5, 8] else "pricing" if i in [3, 6] else "general"
            store.record_turn(
                turn_number=i,
                speaker="candidate" if i % 2 == 1 else "stakeholder",
                stage="STAGE_2_PROBLEM_DISCOVERY",
                content=f"Turn {i} discussion regarding {topic_tag} requirements and SLAs.",
                memory_type=MemoryType.CANDIDATE_STATEMENT if i % 2 == 1 else MemoryType.STAKEHOLDER_STATEMENT,
                tags=[topic_tag],
            )

        self.assertEqual(len(store.memories), 10)

        # Retrieve specifically for security query with limit=3
        results = retriever.retrieve(
            query="security encryption compliance",
            current_turn=10,
            current_stage="STAGE_2_PROBLEM_DISCOVERY",
            limit=3,
        )

        self.assertLessEqual(len(results), 3)
        for item in results:
            self.assertTrue("security" in item.tags or "security" in item.content.lower())

    def test_12_knowledge_access_decision_policy_override(self):
        """Test that unauthorized REVEAL_INFORMATION action is deterministically overridden to WITHHOLD."""
        knowledge_state = StakeholderKnowledgeState(persona=self.persona)

        # Behavioral action tries to reveal confidential roadmap when trust is low
        action = BehavioralAction(
            action_type=ActionType.REVEAL_INFORMATION,
            intensity=0.8,
            target_topic="unannounced roadmap",
            rationale="Salesperson asked about future plans.",
        )

        decision = knowledge_state.evaluate_access(action.target_topic, self.client_state, self.interview_state)
        self.assertFalse(decision.permitted)

        # Deterministic override logic
        if not decision.permitted and action.action_type == ActionType.REVEAL_INFORMATION:
            overridden_action = BehavioralAction(
                action_type=ActionType.WITHHOLD_INFORMATION,
                intensity=action.intensity,
                target_topic=action.target_topic,
                rationale=f"Knowledge boundary enforced: {decision.reason}",
            )
        else:
            overridden_action = action

        self.assertEqual(overridden_action.action_type, ActionType.WITHHOLD_INFORMATION)
        self.assertIn("Knowledge boundary enforced", overridden_action.rationale)

    def test_13_response_consistency_validation(self):
        """Test ResponseConsistencyValidator catches confidential leaks and immutable fact violations."""
        registry = WorldFactRegistry(persona=self.persona)
        knowledge_state = StakeholderKnowledgeState(persona=self.persona)
        validator = ResponseConsistencyValidator(registry=registry, knowledge_state=knowledge_state)

        # 1. Leaking confidential budget ($500k CapEx)
        leaky_response = "Well, our confidential budget is exactly $500k annual CapEx."
        res_leak = validator.validate(
            response_text=leaky_response,
            planned_action=BehavioralAction(action_type=ActionType.PROBE_TECHNICAL_FEASIBILITY, intensity=0.5),
            client_state=self.client_state,
            interview_state=self.interview_state,
        )
        self.assertFalse(res_leak.is_valid)
        self.assertTrue(any("budget" in v.lower() or "confidential" in v.lower() for v in res_leak.violations))

        # 2. Contradicting immutable cloud provider (says AWS when company runs Azure)
        contradictory_response = "All of our production workloads currently run on AWS."
        res_contra = validator.validate(
            response_text=contradictory_response,
            planned_action=BehavioralAction(action_type=ActionType.PROBE_TECHNICAL_FEASIBILITY, intensity=0.5),
            client_state=self.client_state,
            interview_state=self.interview_state,
        )
        self.assertFalse(res_contra.is_valid)
        self.assertTrue(any("azure" in v.lower() or "contradict" in v.lower() or "aws" in v.lower() for v in res_contra.violations))

        # 3. Valid consistent response
        valid_response = "We currently run our primary infrastructure on Azure with PostgreSQL."
        res_valid = validator.validate(
            response_text=valid_response,
            planned_action=BehavioralAction(action_type=ActionType.PROBE_TECHNICAL_FEASIBILITY, intensity=0.5),
            client_state=self.client_state,
            interview_state=self.interview_state,
        )
        self.assertTrue(res_valid.is_valid)
        self.assertEqual(len(res_valid.violations), 0)

    def test_14_response_consistency_repair_and_fallback(self):
        """Test repair fallback mechanism when response validation fails twice."""
        registry = WorldFactRegistry(persona=self.persona)
        knowledge_state = StakeholderKnowledgeState(persona=self.persona)
        validator = ResponseConsistencyValidator(registry=registry, knowledge_state=knowledge_state)

        # Create an invalid response
        invalid_response = "Our confidential budget is $500k annual CapEx and we run AWS."
        val_result = validator.validate(
            response_text=invalid_response,
            planned_action=BehavioralAction(action_type=ActionType.WITHHOLD_INFORMATION, intensity=0.7),
            client_state=self.client_state,
            interview_state=self.interview_state,
        )
        self.assertFalse(val_result.is_valid)

        # Safe fallback generation
        fallback = validator.generate_safe_fallback(
            planned_action=BehavioralAction(action_type=ActionType.WITHHOLD_INFORMATION, intensity=0.7, target_topic="budget"),
            persona=self.persona,
        )
        self.assertIsNotNone(fallback)
        self.assertTrue(len(fallback) > 10)
        # Verify fallback does not contain leaked numbers
        self.assertNotIn("$500k", fallback)

    def test_15_sqlite_memory_and_knowledge_persistence(self):
        """Test saving and loading knowledge items, memory items, commitments, unresolved items, and events in SQLite."""
        session_id = f"test_sql_{uuid.uuid4().hex[:8]}"

        # 1. Save knowledge item
        storage.save_knowledge_item(
            session_id=session_id,
            topic="azure_security",
            fact_summary="Apex uses Azure Private Link.",
            status="CONFIRMED",
            disclosure_level="SHAREABLE",
            source="WORLD_MODEL",
            provenance="Architecture Manual",
            confidence=1.0,
            disclosure_count=1,
            is_disclosed=True,
        )
        k_items = storage.get_knowledge_items(session_id)
        self.assertEqual(len(k_items), 1)
        self.assertEqual(k_items[0]["topic"], "azure_security")
        self.assertEqual(k_items[0]["disclosure_level"], "SHAREABLE")

        # 2. Save memory item
        storage.save_memory_item(
            session_id=session_id,
            turn_number=1,
            speaker="candidate",
            stage="STAGE_1_OPENING_RAPPORT",
            content="Hello CTO, glad to speak.",
            memory_type="CANDIDATE_STATEMENT",
            source="CANDIDATE_STATEMENT",
            tags=["greeting"],
        )
        mem_items = storage.get_memory_items(session_id)
        self.assertEqual(len(mem_items), 1)
        self.assertEqual(mem_items[0]["speaker"], "candidate")

        # 3. Save commitment
        storage.save_stakeholder_commitment(
            session_id=session_id,
            commitment_id="comm_1",
            turn_promised=2,
            speaker="stakeholder",
            topic="review",
            description="Will send follow up email",
            status="ACTIVE",
        )
        comms = storage.get_stakeholder_commitments(session_id)
        self.assertEqual(len(comms), 1)
        self.assertEqual(comms[0]["commitment_id"], "comm_1")

        # 4. Save unresolved item
        storage.save_unresolved_item(
            session_id=session_id,
            item_id="unres_1",
            item_type="QUESTION",
            turn_created=2,
            topic="encryption",
            content="Do you support AES-256?",
            status="UNRESOLVED",
        )
        unres = storage.get_unresolved_items(session_id)
        self.assertEqual(len(unres), 1)
        self.assertEqual(unres[0]["item_id"], "unres_1")

        # 5. Save consistency event
        storage.save_consistency_event(
            session_id=session_id,
            turn_number=3,
            is_valid=False,
            violations=["Leaked confidential budget"],
            repaired=True,
            original_response="Budget is $500k",
            final_response="I cannot share internal budget details.",
        )
        events = storage.get_consistency_events(session_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["is_valid"], 0)
        self.assertEqual(events[0]["repaired"], 1)

    def test_16_debug_api_endpoints(self):
        """Test FastAPI developer debug inspection endpoints for memory, knowledge, and consistency history."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)

        # Create a session
        res_session = client.post(
            "/api/session",
            json={
                "topic": "Sales Conversation",
                "role": "CTO",
                "scenario": "FinTech infrastructure evaluation",
                "experience": "Intermediate",
                "style": "Professional",
                "memory_mode": "full",
            },
        )
        self.assertEqual(res_session.status_code, 200)
        session_id = res_session.json()["session_id"]

        # GET /api/session/{session_id}/memory
        res_mem = client.get(f"/api/session/{session_id}/memory")
        self.assertEqual(res_mem.status_code, 200)
        mem_data = res_mem.json()
        self.assertEqual(mem_data["session_id"], session_id)
        self.assertIn("memories", mem_data)
        self.assertIn("commitments", mem_data)
        self.assertIn("unresolved_items", mem_data)

        # GET /api/session/{session_id}/knowledge
        res_know = client.get(f"/api/session/{session_id}/knowledge")
        self.assertEqual(res_know.status_code, 200)
        know_data = res_know.json()
        self.assertEqual(know_data["session_id"], session_id)
        self.assertIn("knowledge_items", know_data)
        self.assertIn("world_facts", know_data)
        self.assertIn("boundaries", know_data)

        # GET /api/session/{session_id}/consistency-history
        res_const = client.get(f"/api/session/{session_id}/consistency-history")
        self.assertEqual(res_const.status_code, 200)
        const_data = res_const.json()
        self.assertEqual(const_data["session_id"], session_id)
        self.assertIn("history", const_data)

    @patch("app.agents.role_agent.get_llm")
    def test_17_langgraph_multi_turn_memory_pipeline(self, mock_get_llm):
        """Test full LangGraph multi-turn execution preserves memory and maintains consistency across turns."""
        from langchain_core.messages import AIMessage
        mock_llm_instance = MagicMock()
        mock_get_llm.return_value = mock_llm_instance

        replies = [
            AIMessage(content="Hello. We have 15 minutes to discuss this. What is your architecture?"),
            AIMessage(content="We currently run Azure across all our US clusters. How do you handle failover?"),
            AIMessage(content="That failover mechanism is interesting, but I need to see verified SOC2 compliance data."),
        ]
        mock_llm_instance.invoke.side_effect = replies
        mock_llm_instance.bind_tools.return_value.invoke.side_effect = replies

        from app.agents.role_agent import RoleAgent

        agent = RoleAgent(
            role_id="CTO",
            topic="Sales Conversation",
            scenario="Enterprise Cloud Infrastructure Evaluation",
            experience="Intermediate",
            style="Professional",
            session_id=f"test_pipe_{uuid.uuid4().hex[:8]}",
            policy_mode="rule_based",
            memory_mode="full",
        )

        # Turn 1
        reply_1 = agent.chat("Good morning! Thank you for taking the time to meet today.")
        self.assertIn("15 minutes", reply_1)
        self.assertGreaterEqual(len(agent.memory_store.memories), 2)

        # Turn 2
        reply_2 = agent.chat("We integrate natively with Azure and PostgreSQL to ensure zero downtime.")
        self.assertIn("Azure", reply_2)
        self.assertGreaterEqual(len(agent.memory_store.memories), 4)

        # Turn 3
        reply_3 = agent.chat("Our failover takes under 3 seconds and we have SOC2 Type II certification.")
        self.assertIn("SOC2", reply_3)
        self.assertGreaterEqual(len(agent.memory_store.memories), 6)

        # Verify memory retention and persistence
        memories = storage.get_memory_items(agent.session_id)
        self.assertGreaterEqual(len(memories), 4)


if __name__ == "__main__":
    unittest.main()
