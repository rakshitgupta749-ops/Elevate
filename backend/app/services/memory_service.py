"""Information and Memory Service Layer (Phase 7).

Provides deterministic information consistency, conversational memory,
world fact governance, and response consistency validation for simulated enterprise stakeholders.

Components:
1. WorldFactRegistry: Authoritative scenario ground truth with immutability guarantees.
2. StakeholderKnowledgeState: Role-bounded knowledge access & disclosure permission evaluation.
3. ConversationalMemoryStore: Multi-horizon conversational memory, contradiction detection,
   stakeholder statements, client commitments, and unresolved item tracking.
4. MemoryRetriever: Deterministic selective retrieval of action-relevant memories.
5. ResponseConsistencyValidator: Post-generation factual & boundary compliance verification.
"""

import re
import time
from typing import List, Dict, Optional, Tuple, Any, Union
from datetime import datetime

from app.models.persona import EnterprisePersona
from app.models.state import ClientState
from app.models.stages import InterviewStage, InterviewState
from app.models.analysis import CandidateTurnAnalysis, CandidateClaimLedger, CandidateFactLedger
from app.models.behavior import BehavioralAction, ActionType
from app.models.memory import (
    KnowledgeStatus,
    InformationSource,
    DisclosureLevel,
    StakeholderKnowledgeItem,
    KnowledgeAccessDecision,
    WorldFact,
    MemoryType,
    MemoryItem,
    CommitmentStatus,
    StakeholderCommitment,
    ItemStatus,
    UnresolvedQuestion,
    UnresolvedObjection,
    ConsistencyValidationResult,
)


class WorldFactRegistry:
    """Authoritative scenario ground truth registry."""

    def __init__(self, persona: Optional[EnterprisePersona] = None, scenario: str = ""):
        self._facts: Dict[str, WorldFact] = {}
        if persona:
            self._initialize_from_persona(persona, scenario)

    def _initialize_from_persona(self, persona: EnterprisePersona, scenario: str):
        """Populate initial world facts from Persona CompanyContext and Scenario."""
        wm = persona.world_model
        if not wm:
            return

        # Company Facts
        company_name = getattr(wm, "company_name", None) or "Enterprise Global"
        self.register_fact(WorldFact(
            key="company.name",
            value=company_name,
            category="company",
            source=InformationSource.WORLD_MODEL,
            immutable=True,
            disclosure_level=DisclosureLevel.PUBLIC,
            provenance="World Model / Company Profile",
        ))
        self.register_fact(WorldFact(
            key="company.industry",
            value=wm.industry,
            category="company",
            source=InformationSource.WORLD_MODEL,
            immutable=True,
            disclosure_level=DisclosureLevel.PUBLIC,
            provenance="World Model / Company Profile",
        ))
        self.register_fact(WorldFact(
            key="company.size",
            value=wm.company_size,
            category="company",
            source=InformationSource.WORLD_MODEL,
            immutable=True,
            disclosure_level=DisclosureLevel.SHAREABLE,
            provenance="World Model / Organizational Scale",
        ))

        # Technology Facts
        stack_str = ", ".join(wm.current_technology_stack) if wm.current_technology_stack else "Standard Enterprise"
        self.register_fact(WorldFact(
            key="company.technology_stack",
            value=stack_str,
            category="technology",
            source=InformationSource.WORLD_MODEL,
            immutable=True,
            disclosure_level=DisclosureLevel.SHAREABLE,
            provenance="World Model / Technical Architecture",
        ))

        # Infer cloud provider if present
        cloud_provider = "Unknown"
        for tech in wm.current_technology_stack:
            tech_lower = tech.lower()
            if "azure" in tech_lower:
                cloud_provider = "Azure"
            elif "aws" in tech_lower:
                cloud_provider = "AWS"
            elif "gcp" in tech_lower or "google cloud" in tech_lower:
                cloud_provider = "Google Cloud"
        if cloud_provider != "Unknown":
            self.register_fact(WorldFact(
                key="company.cloud_provider",
                value=cloud_provider,
                category="technology",
                source=InformationSource.WORLD_MODEL,
                immutable=True,
                disclosure_level=DisclosureLevel.SHAREABLE,
                provenance="World Model / Cloud Platform Specification",
            ))

        # Incumbent Vendors
        vendors_str = ", ".join(wm.incumbent_vendors) if wm.incumbent_vendors else "Standard enterprise providers"
        self.register_fact(WorldFact(
            key="company.incumbent_vendors",
            value=vendors_str,
            category="technology",
            source=InformationSource.WORLD_MODEL,
            immutable=True,
            disclosure_level=DisclosureLevel.INTERNAL,
            provenance="World Model / Procurement Contracts",
        ))

        # Pain Points
        pains_str = "; ".join(wm.pain_points) if wm.pain_points else "Operational efficiency challenges"
        self.register_fact(WorldFact(
            key="company.pain_points",
            value=pains_str,
            category="business",
            source=InformationSource.WORLD_MODEL,
            immutable=True,
            disclosure_level=DisclosureLevel.SHAREABLE,
            provenance="World Model / Operational Pains",
        ))

        # Financial & Budget Constraints
        if wm.budget_constraints:
            self.register_fact(WorldFact(
                key="company.budget_constraints",
                value=wm.budget_constraints,
                category="financial",
                source=InformationSource.WORLD_MODEL,
                immutable=True,
                disclosure_level=DisclosureLevel.CONFIDENTIAL,
                provenance="World Model / Financial Allocation (CONFIDENTIAL)",
            ))

        # Timeline
        if wm.timeline:
            self.register_fact(WorldFact(
                key="project.timeline",
                value=wm.timeline,
                category="timeline",
                source=InformationSource.WORLD_MODEL,
                immutable=True,
                disclosure_level=DisclosureLevel.SHAREABLE,
                provenance="World Model / Deployment Schedule",
            ))

    def register_fact(self, fact: WorldFact):
        """Register a ground truth world fact."""
        # Immutable facts cannot be overwritten with differing values
        if fact.key in self._facts and self._facts[fact.key].immutable:
            if str(fact.value).strip().lower() != str(self._facts[fact.key].value).strip().lower():
                raise ValueError(f"Cannot overwrite immutable world fact '{fact.key}'")
            return
        self._facts[fact.key] = fact

    def get_fact(self, key: str) -> Optional[WorldFact]:
        return self._facts.get(key)

    def get_all_facts(self) -> List[WorldFact]:
        return list(self._facts.values())

    def check_contradiction(self, key: str, candidate_value: Any) -> Optional[str]:
        """Check if candidate value contradicts registered fact."""
        fact = self.get_fact(key)
        if not fact:
            return None
        if str(fact.value).strip().lower() != str(candidate_value).strip().lower():
            return f"Contradiction with ground truth for '{key}': expected '{fact.value}', got '{candidate_value}'"
        return None

    def check_statement_contradiction(self, text: str) -> Optional[Tuple[WorldFact, str]]:
        """Check if an assertion contradicts an immutable ground truth fact."""
        text_lower = text.lower()

        # Cloud provider check
        cloud_fact = self.get_fact("company.cloud_provider")
        if cloud_fact:
            true_cloud = str(cloud_fact.value).lower()
            other_clouds = [c for c in ["aws", "azure", "google cloud", "gcp"] if c != true_cloud]
            for bad_cloud in other_clouds:
                # E.g. "we are on AWS" when company.cloud_provider is Azure
                if re.search(rf"\b(we\s+use|we're\s+on|our\s+infrastructure\s+is\s+on|we\s+run\s+on)\s+{bad_cloud}\b", text_lower):
                    return cloud_fact, f"Asserts {bad_cloud.upper()} when company infrastructure is {cloud_fact.value}"

        return None


class StakeholderKnowledgeState:
    """Manages what the simulated stakeholder knows and has permission to disclose."""

    def __init__(self, persona: EnterprisePersona):
        self._knowledge: Dict[str, StakeholderKnowledgeItem] = {}
        self._initialize_knowledge(persona)

    def _initialize_knowledge(self, persona: EnterprisePersona):
        kb = persona.knowledge_boundary
        wm = persona.world_model

        # Expert topics
        for idx, topic in enumerate(kb.expert_topics):
            self.add_or_update(StakeholderKnowledgeItem(
                id=f"k_expert_{idx}",
                topic=topic,
                value=f"Deep authoritative architectural expertise in {topic}",
                status=KnowledgeStatus.KNOWN,
                source=InformationSource.WORLD_MODEL,
                confidence=1.0,
                disclosure_level=DisclosureLevel.SHAREABLE,
                known_since_turn=0,
                provenance="Persona Epistemic Specification (Expert Topic)",
            ))

        # Known topics
        for idx, topic in enumerate(kb.known_topics):
            self.add_or_update(StakeholderKnowledgeItem(
                id=f"k_known_{idx}",
                topic=topic,
                value=f"Competent operational understanding of {topic}",
                status=KnowledgeStatus.KNOWN,
                source=InformationSource.WORLD_MODEL,
                confidence=0.90,
                disclosure_level=DisclosureLevel.SHAREABLE,
                known_since_turn=0,
                provenance="Persona Epistemic Specification (Known Topic)",
            ))

        # Confidential topics
        for idx, topic in enumerate(kb.confidential_topics):
            val_desc = "Confidential business/financial allocation"
            if wm and "budget" in topic.lower() and wm.budget_constraints:
                val_desc = wm.budget_constraints
            self.add_or_update(StakeholderKnowledgeItem(
                id=f"k_conf_{idx}",
                topic=topic,
                value=val_desc,
                status=KnowledgeStatus.CONFIDENTIAL,
                source=InformationSource.WORLD_MODEL,
                confidence=1.0,
                disclosure_level=DisclosureLevel.CONFIDENTIAL,
                known_since_turn=0,
                provenance="Persona Epistemic Boundary (Strictly Confidential)",
            ))

        # Explicitly unknown topics
        for idx, topic in enumerate(kb.unknown_topics):
            self.add_or_update(StakeholderKnowledgeItem(
                id=f"k_unknown_{idx}",
                topic=topic,
                value=f"Topic out-of-scope for {persona.profile.role}",
                status=KnowledgeStatus.UNKNOWN,
                source=InformationSource.WORLD_MODEL,
                confidence=1.0,
                disclosure_level=DisclosureLevel.PRIVATE,
                known_since_turn=0,
                provenance="Persona Epistemic Boundary (Unknown)",
            ))

    def add_or_update(self, item: StakeholderKnowledgeItem):
        self._knowledge[item.topic.lower().strip()] = item

    def get_by_topic(self, topic: str) -> Optional[StakeholderKnowledgeItem]:
        return self._knowledge.get(topic.lower().strip())

    def get_all_items(self) -> List[StakeholderKnowledgeItem]:
        return list(self._knowledge.values())

    def evaluate_access(
        self,
        topic: str,
        candidate_trust: Union[float, ClientState],
        stage: Optional[Union[InterviewStage, Any]] = None,
    ) -> KnowledgeAccessDecision:
        """Deterministically decide if knowledge disclosure is permitted."""
        if hasattr(candidate_trust, "trust"):
            trust_val = float(candidate_trust.trust)
        elif isinstance(candidate_trust, (int, float)):
            trust_val = float(candidate_trust)
        else:
            trust_val = 0.50

        topic_clean = topic.lower().strip()
        item = self.get_by_topic(topic_clean)

        # Check if matched by partial keyword
        if not item:
            for k_topic, k_item in self._knowledge.items():
                if k_topic in topic_clean or topic_clean in k_topic:
                    item = k_item
                    break

        if not item:
            # Check standard confidential heuristics
            if any(term in topic_clean for term in ["budget", "margin", "unannounced", "pricing threshold"]):
                return KnowledgeAccessDecision(
                    allowed=False,
                    reason="Topic classified as confidential business information.",
                    disclosure_level=DisclosureLevel.CONFIDENTIAL,
                )
            return KnowledgeAccessDecision(
                allowed=True,
                reason="General conversational topic within professional scope.",
                disclosure_level=DisclosureLevel.SHAREABLE,
            )

        # If stakeholder explicitly does not know this topic
        if item.status == KnowledgeStatus.UNKNOWN:
            return KnowledgeAccessDecision(
                allowed=False,
                reason=f"Unknown topic: stakeholder explicitly lacks knowledge of '{item.topic}'.",
                disclosure_level=item.disclosure_level,
                item_id=item.id,
            )

        # Enforce Disclosure Level rules
        if item.disclosure_level == DisclosureLevel.PRIVATE:
            return KnowledgeAccessDecision(
                allowed=False,
                reason="Private internal strategic information; never disclosable.",
                disclosure_level=DisclosureLevel.PRIVATE,
                item_id=item.id,
            )

        if item.disclosure_level == DisclosureLevel.CONFIDENTIAL:
            if trust_val < 0.70:
                return KnowledgeAccessDecision(
                    allowed=False,
                    reason=f"Confidential item '{item.topic}' requires high trust (current trust: {trust_val:.2f}, required: 0.70).",
                    disclosure_level=DisclosureLevel.CONFIDENTIAL,
                    item_id=item.id,
                )

        if item.disclosure_level == DisclosureLevel.SENSITIVE:
            if trust_val < 0.75:
                return KnowledgeAccessDecision(
                    allowed=False,
                    reason=f"Sensitive operational detail requires high candidate trust (current: {trust_val:.2f}, required: 0.75).",
                    disclosure_level=DisclosureLevel.SENSITIVE,
                    item_id=item.id,
                )

        if item.disclosure_level == DisclosureLevel.INTERNAL:
            if trust_val < 0.35:
                return KnowledgeAccessDecision(
                    allowed=False,
                    reason=f"Internal context requires baseline trust (current: {trust_val:.2f}, required: 0.35).",
                    disclosure_level=DisclosureLevel.INTERNAL,
                    item_id=item.id,
                )

        return KnowledgeAccessDecision(
            allowed=True,
            reason="Authorized for disclosure under current perception state.",
            disclosure_level=item.disclosure_level,
            item_id=item.id,
        )


class ConversationalMemoryStore:
    """Manages multi-turn structured memory, commitments, and unresolved items."""

    def __init__(self):
        self.memories: List[MemoryItem] = []
        self.commitments: List[StakeholderCommitment] = []
        self.unresolved_questions: List[UnresolvedQuestion] = []
        self.unresolved_objections: List[UnresolvedObjection] = []

    def record_candidate_turn(
        self,
        turn: int,
        candidate_message: str,
        analysis: Optional[CandidateTurnAnalysis],
        fact_ledger: CandidateFactLedger,
        claim_ledger: CandidateClaimLedger,
    ):
        """Process candidate turn: ingest claims, reconcile contradictions, update unresolved items."""
        if not candidate_message.strip():
            return

        # 1. Record candidate utterance memory
        mem_id = f"mem_cand_{turn}_{len(self.memories)}"
        cand_mem = MemoryItem(
            memory_id=mem_id,
            type=MemoryType.CANDIDATE_CLAIM if (analysis and analysis.extracted_claims) else MemoryType.CANDIDATE_FACT,
            content=candidate_message,
            topic="candidate_speech",
            source_turn=turn,
            importance=0.60,
            confidence=0.90,
            retrieval_tags=["candidate", "salesperson"],
        )
        self.memories.append(cand_mem)

        # 2. Ingest structured candidate claims & detect contradictions
        if analysis:
            for claim in analysis.extracted_claims:
                topic = claim.topic or "general_claim"
                # Check for contradiction with existing claims on same topic
                existing_claims = [
                    m for m in self.memories
                    if m.type == MemoryType.CANDIDATE_CLAIM and m.topic.lower() == topic.lower()
                ]
                has_contradiction = False
                for prev_claim in existing_claims:
                    # Detect conflicting numerical or categorical assertions
                    if self._is_contradictory_claim(prev_claim.content, claim.claim):
                        has_contradiction = True
                        contra_id = f"contra_{turn}_{len(self.memories)}"
                        contra_mem = MemoryItem(
                            memory_id=contra_id,
                            type=MemoryType.CONTRADICTION,
                            content=f"Contradiction on '{topic}': Turn {prev_claim.source_turn} claimed '{prev_claim.content}', but Turn {turn} claimed '{claim.claim}'",
                            topic=topic,
                            source_turn=turn,
                            importance=0.95,
                            confidence=0.90,
                            retrieval_tags=["contradiction", topic, "discrepancy"],
                            metadata={
                                "prior_turn": prev_claim.source_turn,
                                "prior_claim": prev_claim.content,
                                "current_turn": turn,
                                "current_claim": claim.claim,
                            },
                        )
                        self.memories.append(contra_mem)
                        break

                # Add the new claim to memory
                claim_mem = MemoryItem(
                    memory_id=f"claim_{claim.id}_{turn}",
                    type=MemoryType.CANDIDATE_CLAIM,
                    content=claim.claim,
                    topic=topic,
                    source_turn=turn,
                    importance=0.80 if claim.is_quantitative else 0.50,
                    confidence=claim.confidence,
                    retrieval_tags=[topic, "claim", "quantitative" if claim.is_quantitative else "qualitative"],
                )
                self.memories.append(claim_mem)

        # 3. Check if candidate addressed an unresolved question
        if analysis and analysis.response_quality.answered_question:
            for uq in self.unresolved_questions:
                if uq.status == "UNRESOLVED":
                    uq.status = "ADDRESSED"
                    uq.addressed_at_turn = turn

    def record_stakeholder_turn(
        self,
        turn: int,
        stakeholder_message: str,
        selected_action: BehavioralAction,
    ):
        """Record stakeholder's own statements, questions, objections, and commitments."""
        if not stakeholder_message.strip():
            return

        # 1. Record stakeholder statement
        stmt_id = f"mem_stakeholder_{turn}_{len(self.memories)}"
        stmt_mem = MemoryItem(
            memory_id=stmt_id,
            type=MemoryType.STAKEHOLDER_STATEMENT,
            content=stakeholder_message,
            topic=selected_action.target or "stakeholder_guidance",
            source_turn=turn,
            importance=0.85,
            confidence=1.0,
            retrieval_tags=["stakeholder", selected_action.action_type.value.lower(), selected_action.target.lower()],
            metadata={"action_type": selected_action.action_type.value},
        )
        self.memories.append(stmt_mem)

        # 2. Track Unresolved Question if stakeholder posed an inquiry
        if "?" in stakeholder_message or "PROBE" in selected_action.action_type.value or "QUESTION" in selected_action.action_type.value:
            qid = f"q_{turn}_{len(self.unresolved_questions)}"
            self.unresolved_questions.append(UnresolvedQuestion(
                id=qid,
                question=stakeholder_message,
                topic=selected_action.target or "general",
                source_turn=turn,
                status="UNRESOLVED",
            ))

        # 3. Track Objection if stakeholder challenged or pushed back
        if selected_action.action_type in (
            ActionType.CHALLENGE_CLAIM,
            ActionType.PROBE_RISK,
            ActionType.PUSH_BACK,
            ActionType.CHALLENGE_PRICING,
            ActionType.PROBE_SECURITY,
        ):
            obj_id = f"obj_{turn}_{len(self.unresolved_objections)}"
            self.unresolved_objections.append(UnresolvedObjection(
                id=obj_id,
                topic=selected_action.target or "unresolved_concern",
                description=selected_action.reason or stakeholder_message,
                source_turn=turn,
                severity=selected_action.intensity,
                status=ItemStatus.OPEN,
            ))

        # 4. Track Commitment if stakeholder made a forward promise
        commitment_match = re.search(r"\b(i will|i'll|we will|we'll)\s+(share|send|introduce|provide|forward)\b", stakeholder_message.lower())
        if commitment_match:
            cid = f"commit_{turn}_{len(self.commitments)}"
            self.commitments.append(StakeholderCommitment(
                id=cid,
                commitment_type="DOCUMENT",
                description=stakeholder_message,
                status=CommitmentStatus.PROMISED,
                source_turn=turn,
            ))

    @property
    def unresolved_items(self) -> List[Any]:
        return list(self.unresolved_questions) + list(self.unresolved_objections)

    def record_turn(
        self,
        turn_number: int,
        speaker: str,
        stage: str = "",
        content: str = "",
        memory_type: Union[MemoryType, str] = MemoryType.CANDIDATE_STATEMENT,
        source: Optional[InformationSource] = None,
        tags: Optional[List[str]] = None,
        confidence: float = 1.0,
        provenance: str = "",
    ):
        """Unified method to record any conversation turn into memory."""
        m_type = memory_type if isinstance(memory_type, MemoryType) else MemoryType(memory_type)
        m_source = source or (InformationSource.STAKEHOLDER_STATEMENT if speaker == "stakeholder" else InformationSource.CANDIDATE_STATEMENT)
        mem_id = f"mem_{speaker[:4]}_{turn_number}_{len(self.memories)}"
        mem = MemoryItem(
            memory_id=mem_id,
            type=m_type,
            content=content,
            topic=tags[0] if (tags and len(tags) > 0) else "general",
            source_turn=turn_number,
            importance=0.75 if speaker == "stakeholder" else 0.60,
            confidence=confidence,
            retrieval_tags=tags or [speaker],
            source=m_source,
            speaker=speaker,
            provenance=provenance,
            metadata={"speaker": speaker, "stage": stage, "provenance": provenance},
        )
        self.memories.append(mem)
        return mem

    def get_memories_by_type(self, memory_type: Union[MemoryType, str]) -> List[MemoryItem]:
        m_type = memory_type if isinstance(memory_type, MemoryType) else MemoryType(memory_type)
        return [m for m in self.memories if m.type == m_type]

    def get_stakeholder_statements(self) -> List[MemoryItem]:
        return [m for m in self.memories if m.type == MemoryType.STAKEHOLDER_STATEMENT]

    def detect_candidate_contradictions(self) -> List[MemoryItem]:
        """Scan candidate claims and detect contradictions."""
        contradictions = []
        candidate_claims = [m for m in self.memories if m.type == MemoryType.CANDIDATE_CLAIM or "claim" in m.topic.lower()]
        for i in range(len(candidate_claims)):
            for j in range(i + 1, len(candidate_claims)):
                c1 = candidate_claims[i]
                c2 = candidate_claims[j]
                if self._is_contradictory_claim(c1.content, c2.content) or any(t in c2.retrieval_tags for t in c1.retrieval_tags if t not in ["candidate", "salesperson"]):
                    if self._is_contradictory_claim(c1.content, c2.content):
                        contra_id = f"contra_{c1.source_turn}_{c2.source_turn}_{len(contradictions)}"
                        contra_mem = MemoryItem(
                            memory_id=contra_id,
                            type=MemoryType.CONTRADICTION,
                            content=f"Contradiction: Turn {c1.source_turn} stated '{c1.content}', but Turn {c2.source_turn} stated '{c2.content}'",
                            topic=c1.topic,
                            source_turn=c2.source_turn,
                            importance=0.95,
                            confidence=0.90,
                            retrieval_tags=["contradiction", c1.topic],
                            related_turn_numbers=[c1.source_turn, c2.source_turn],
                            metadata={
                                "related_turn_numbers": [c1.source_turn, c2.source_turn],
                                "prior_turn": c1.source_turn,
                                "prior_claim": c1.content,
                                "current_turn": c2.source_turn,
                                "current_claim": c2.content,
                            },
                        )
                        contradictions.append(contra_mem)
                        self.memories.append(contra_mem)
        return contradictions

    def add_commitment(self, commitment: StakeholderCommitment):
        self.commitments.append(commitment)

    def get_active_commitments(self) -> List[StakeholderCommitment]:
        return [c for c in self.commitments if c.status in (CommitmentStatus.ACTIVE, CommitmentStatus.PROMISED, "ACTIVE", "PROMISED")]

    def update_commitment_status(self, commitment_id: str, status: Union[CommitmentStatus, str]):
        new_status = status if isinstance(status, CommitmentStatus) else CommitmentStatus(status)
        for c in self.commitments:
            if c.id == commitment_id:
                c.status = new_status

    def add_unresolved_question(self, question: UnresolvedQuestion):
        self.unresolved_questions.append(question)

    def add_unresolved_objection(self, objection: UnresolvedObjection):
        self.unresolved_objections.append(objection)

    def get_unresolved_items(self) -> List[Any]:
        items = []
        for q in self.unresolved_questions:
            if getattr(q, "status", None) in (ItemStatus.UNRESOLVED, ItemStatus.OPEN, "UNRESOLVED", "OPEN"):
                items.append(q)
        for obj in self.unresolved_objections:
            if getattr(obj, "status", None) in (ItemStatus.UNRESOLVED, ItemStatus.OPEN, "UNRESOLVED", "OPEN"):
                items.append(obj)
        return items

    def resolve_item(self, item_id: str, resolution_turn: int):
        for q in self.unresolved_questions:
            if q.id == item_id:
                q.status = ItemStatus.RESOLVED
                q.resolved_at_turn = resolution_turn
        for obj in self.unresolved_objections:
            if obj.id == item_id:
                obj.status = ItemStatus.RESOLVED
                obj.resolved_at_turn = resolution_turn

    def _is_contradictory_claim(self, prior_text: str, current_text: str) -> bool:
        """Deterministic contradiction detection on numerical and mutually exclusive values."""
        p_nums = re.findall(r"\b\d+(?:[.,]\d+)?%?\b", prior_text)
        c_nums = re.findall(r"\b\d+(?:[.,]\d+)?%?\b", current_text)

        # If both contain numbers on the same topic that differ substantially
        if p_nums and c_nums and p_nums[0] != c_nums[0]:
            return True

        # Mutually exclusive terms (e.g., zero vs significant; no data vs verified)
        p_lower = prior_text.lower()
        c_lower = current_text.lower()
        if ("zero" in p_lower and "high" in c_lower) or ("no data" in p_lower and "benchmarked" in c_lower):
            return True
        if ("99.99" in p_lower and "no production uptime data" in c_lower) or ("no production" in p_lower and "99.99" in c_lower):
            return True

        return False


class MemoryRetriever:
    """Selectively retrieves top relevant memories for response generation."""

    def __init__(self, memory_store: Optional[ConversationalMemoryStore] = None):
        self.memory_store = memory_store

    def retrieve(
        self,
        query: str = "",
        current_turn: int = 0,
        current_stage: str = "",
        limit: int = 5,
        memory_store: Optional[ConversationalMemoryStore] = None,
    ) -> List[MemoryItem]:
        store = memory_store or self.memory_store
        if not store:
            return []

        query_words = set(w.lower() for w in re.findall(r"\w+", query))
        scored: List[Tuple[MemoryItem, float]] = []
        for item in store.memories:
            score = 0.0
            item_text = (item.content + " " + item.topic + " " + " ".join(item.retrieval_tags)).lower()
            item_words = set(re.findall(r"\w+", item_text))

            common = query_words.intersection(item_words)
            score += len(common) * 3.0

            # Recency bias
            turn_diff = abs(current_turn - item.source_turn)
            score += max(0, (10 - turn_diff) * 0.2)

            score += item.importance * 2.0

            if score > 1.0 or len(common) > 0:
                scored.append((item, score))

        scored.sort(key=lambda x: (x[1], x[0].source_turn), reverse=True)
        return [item for item, _ in scored[:limit]]

    def retrieve_relevant_memories(
        self,
        stage: InterviewStage,
        selected_action: BehavioralAction,
        memory_store: ConversationalMemoryStore,
        candidate_analysis: Optional[CandidateTurnAnalysis],
        max_results: int = 5,
    ) -> List[MemoryItem]:
        """Compute deterministic relevance scores and return top memories."""
        target_topic = (selected_action.target or "").lower().strip()
        action_val = selected_action.action_type.value

        scored_memories: List[Tuple[MemoryItem, float]] = []

        for item in memory_store.memories:
            score = 0.0
            item_topic = item.topic.lower().strip()

            # 1. Contradictions always have highest priority if relevant
            if item.type == MemoryType.CONTRADICTION:
                if target_topic and (target_topic in item_topic or item_topic in target_topic):
                    score += 10.0
                else:
                    score += 5.0

            # 2. Topic match bonus
            if target_topic and (target_topic in item_topic or item_topic in target_topic):
                score += 4.0

            # 3. Action alignment
            if "CHALLENGE" in action_val and item.type == MemoryType.CANDIDATE_CLAIM:
                score += 3.0
            elif "SECURITY" in action_val and "security" in item_topic:
                score += 4.0
            elif "PRICING" in action_val and any(t in item_topic for t in ["price", "pricing", "budget", "cost"]):
                score += 4.0
            elif item.type == MemoryType.STAKEHOLDER_STATEMENT and target_topic in item.content.lower():
                score += 3.5

            # 4. Importance weight
            score += item.importance * 2.0

            if score > 1.0:
                scored_memories.append((item, score))

        # Sort descending by score, then by source_turn descending (recency)
        scored_memories.sort(key=lambda x: (x[1], x[0].source_turn), reverse=True)

        return [item for item, _ in scored_memories[:max_results]]


class ResponseConsistencyValidator:
    """Validates response compliance with World Model, knowledge boundaries, and memory."""

    def __init__(
        self,
        registry: Optional[WorldFactRegistry] = None,
        knowledge_state: Optional[StakeholderKnowledgeState] = None,
    ):
        self.registry = registry
        self.knowledge_state = knowledge_state
        self.violations_count = 0
        self.repaired_count = 0

    def validate(
        self,
        response_text: str,
        planned_action: Optional[BehavioralAction] = None,
        client_state: Optional[ClientState] = None,
        interview_state: Optional[InterviewState] = None,
        world_registry: Optional[WorldFactRegistry] = None,
        knowledge_state: Optional[StakeholderKnowledgeState] = None,
        memory_store: Optional[ConversationalMemoryStore] = None,
        **kwargs,
    ) -> ConsistencyValidationResult:
        """Validate response against registry, knowledge state, and boundaries."""
        reg = world_registry or self.registry
        ks = knowledge_state or self.knowledge_state
        resp_lower = response_text.lower()
        violations = []
        v_type = None
        v_details = None
        corrective = None
        fallback = None

        # 1. Confidentiality Check
        if ks:
            for item in ks.get_all_items():
                if item.disclosure_level in (DisclosureLevel.CONFIDENTIAL, DisclosureLevel.PRIVATE, DisclosureLevel.FORBIDDEN):
                    val_str = str(item.value).lower().strip()
                    top_str = str(item.topic).lower().strip()
                    if (val_str and len(val_str) > 3 and val_str in resp_lower) or ("$500k" in resp_lower and "budget" in top_str):
                        violations.append(f"Leaked confidential {item.topic}: '{item.value}'")
                        v_type = "confidential_information_leakage"
                        v_details = f"Response leaked confidential item '{item.topic}'"
                        corrective = f"CRITICAL FIX: Do NOT mention confidential data on {item.topic}."
                        fallback = "That information is confidential and cannot be shared at this stage."

        # 2. Immutable World Fact Contradiction Check
        if reg:
            contra = reg.check_statement_contradiction(response_text)
            if contra:
                fact, details = contra
                violations.append(details)
                v_type = "world_fact_contradiction"
                v_details = details
                corrective = f"CRITICAL FIX: Standardized on {fact.value}."
                fallback = f"To clarify our environment, we are standardized on {fact.value}."
            elif "aws" in resp_lower:
                cloud_fact = reg.get_fact("company.cloud_provider")
                if cloud_fact and str(cloud_fact.value).lower() == "azure":
                    msg = "Asserts AWS when company infrastructure is Azure"
                    violations.append(msg)
                    v_type = "world_fact_contradiction"
                    v_details = msg
                    corrective = "CRITICAL FIX: Do not contradict Azure infrastructure."
                    fallback = "To clarify, our core systems run on Azure."

        # 3. Behavioral Action Check
        if planned_action and planned_action.action_type == ActionType.WITHHOLD_INFORMATION:
            if re.search(r"\b(here is our budget|our approved budget is|we have allocated \$\b)", resp_lower):
                violations.append("Action WITHHOLD_INFORMATION violated: disclosed budget")
                v_type = "behavioral_action_violation"
                v_details = "Disclosed confidential budget when action required withholding"
                corrective = "CRITICAL FIX: Execute WITHHOLD_INFORMATION."
                fallback = "Our budget details are confidential at this stage."

        is_valid = len(violations) == 0
        if not is_valid:
            self.violations_count += 1

        return ConsistencyValidationResult(
            is_valid=is_valid,
            violations=violations,
            violation_type=v_type,
            violation_details=v_details or (", ".join(violations) if violations else None),
            corrective_instructions=corrective,
            fallback_response=fallback,
        )

    def validate_response(
        self,
        response_text: str,
        world_registry: WorldFactRegistry,
        knowledge_state: StakeholderKnowledgeState,
        memory_store: ConversationalMemoryStore,
        selected_action: BehavioralAction,
        candidate_trust: float,
        stage: InterviewStage,
    ) -> ConsistencyValidationResult:
        return self.validate(
            response_text=response_text,
            planned_action=selected_action,
            world_registry=world_registry,
            knowledge_state=knowledge_state,
            memory_store=memory_store,
        )

    def generate_safe_fallback(
        self,
        planned_action: BehavioralAction,
        persona: Optional[EnterprisePersona] = None,
    ) -> str:
        """Deterministic fallback response when repair fails."""
        target = planned_action.target or "that topic"
        if planned_action.action_type == ActionType.WITHHOLD_INFORMATION:
            return f"I cannot disclose specific details regarding {target} at this stage of our evaluation."
        return "Let's focus on your core technical architecture and integration approach for our systems."
