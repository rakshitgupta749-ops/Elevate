"""Unit and Integration Tests for Phase 5: Candidate Behavior & Content Analyzer.

Validates:
- CandidateTurnAnalysis, CandidateFact, and CandidateClaim models
- Confidence bounds and validation
- Multiple simultaneous signal generation per turn
- Deterministic semantic mapping to Phase 3 InteractionSignals
- Deterministic criteria mapping to Phase 4 InterviewState
- Confidence threshold gates (high vs medium vs low confidence)
- Candidate fact extraction and lifecycle status
- Separation of subjective claims from objective facts
- Contradiction preservation in CandidateFactLedger
- Resilient failure fallback on LLM error/timeout
- SQLite research persistence in candidate_turn_analyses
- LangGraph multi-turn execution with CandidateBehaviorAnalyzer
- Developer debug inspection API endpoint
"""

import unittest
from unittest.mock import patch, MagicMock
import uuid
import json
from langchain_core.messages import AIMessage, HumanMessage

from app.models.analysis import (
    CandidateTurnAnalysis,
    CandidateFact,
    CandidateClaim,
    CandidateFactLedger,
    CandidateClaimLedger,
    FactStatus,
    CommunicationStyleAnalysis,
    SalesBehaviorAnalysis,
    ResponseQualityAnalysis,
    BusinessUnderstandingAnalysis,
    TechnicalBehaviorAnalysis,
    CommercialBehaviorAnalysis,
    SemanticClassificationEvidence,
)
from app.models.state import ClientState, InteractionSignal
from app.models.stages import InterviewStage, InterviewState, InterviewStatus
from app.services.candidate_analyzer import (
    CandidateBehaviorAnalyzer,
    map_analysis_to_signals,
)
from app.services.state_manager import ClientStateManager
from app.services.interview_state_manager import InterviewStateManager
from app.services.storage_service import storage


class TestCandidateAnalyzer(unittest.TestCase):

    def setUp(self):
        self.state_manager = ClientStateManager()
        self.interview_manager = InterviewStateManager()

    def test_01_analysis_model_validation(self):
        """Verify CandidateTurnAnalysis and submodels validate and serialize properly."""
        analysis = CandidateTurnAnalysis(
            turn=1,
            communication=CommunicationStyleAnalysis(
                clarity=0.85,
                conciseness=0.90,
                confidence=0.80,
                professionalism=0.95,
                directness=0.85,
            ),
            sales_behavior=SalesBehaviorAnalysis(
                discovery_question=True,
                needs_exploration=True,
                value_proposition=False,
            ),
            response_quality=ResponseQualityAnalysis(
                answered_question=True,
                evasive=False,
                vague=False,
                evidence_backed=True,
                unsupported_claim=False,
            ),
            business_understanding=BusinessUnderstandingAnalysis(
                pain_identified=True,
                impact_identified=True,
            ),
            technical_behavior=TechnicalBehaviorAnalysis(
                technical_evidence=True,
                architecture_explanation=True,
            ),
            commercial_behavior=CommercialBehaviorAnalysis(),
            extracted_facts=[
                CandidateFact(
                    id="fact_1",
                    category="pain_point",
                    value="Database replication lag during peak hours",
                    confidence=0.92,
                    source_turn=1,
                    evidence="Our cross-region replication takes up to 45 seconds during sales events",
                    status=FactStatus.OBSERVED,
                )
            ],
            extracted_claims=[
                CandidateClaim(
                    id="claim_1",
                    topic="uptime",
                    claim="Platform guarantees 99.99% uptime",
                    evidence_provided=False,
                    is_quantitative=True,
                    confidence=0.95,
                    source_turn=1,
                    evidence="We provide four nines uptime guarantee",
                )
            ],
            summary_observations="Clear technical discovery response with concrete latency metrics.",
            overall_confidence=0.90,
        )

        d = analysis.to_dict()
        self.assertEqual(d["turn"], 1)
        self.assertTrue(d["sales_behavior"]["discovery_question"])
        self.assertTrue(d["response_quality"]["evidence_backed"])
        self.assertEqual(len(d["extracted_facts"]), 1)
        self.assertEqual(d["extracted_facts"][0]["category"], "pain_point")
        self.assertEqual(len(d["extracted_claims"]), 1)
        self.assertTrue(d["extracted_claims"][0]["is_quantitative"])

    def test_02_confidence_bounds(self):
        """Verify confidence scores outside [0.0, 1.0] are rejected by Pydantic validation."""
        with self.assertRaises(Exception):
            CandidateFact(
                id="f_invalid",
                category="timeline",
                value="Q4",
                confidence=1.5,  # Invalid: > 1.0
                source_turn=1,
                evidence="Q4 rollout",
            )

        with self.assertRaises(Exception):
            CandidateTurnAnalysis(turn=1, overall_confidence=-0.1)  # Invalid: < 0.0

    def test_03_multiple_simultaneous_signals(self):
        """Verify one candidate turn can trigger multiple simultaneous interaction signals."""
        analysis = CandidateTurnAnalysis(
            turn=2,
            sales_behavior=SalesBehaviorAnalysis(
                discovery_question=True,
                needs_exploration=True,
                value_proposition=True,
            ),
            response_quality=ResponseQualityAnalysis(
                answered_question=True,
                evidence_backed=True,
                unsupported_claim=True,  # Made an unsupported claim while also presenting evidence
            ),
            technical_behavior=TechnicalBehaviorAnalysis(technical_evidence=True),
        )

        signals = map_analysis_to_signals(analysis)
        signal_types = [s.type for s in signals]
        self.assertIn("unsupported_claim", signal_types)
        self.assertIn("positive_evidence", signal_types)
        self.assertGreaterEqual(len(signals), 2)

    def test_04_signal_mapping_unsupported_claim(self):
        """Verify unsupported claim maps deterministically to UNSUPPORTED_CLAIM signal."""
        analysis = CandidateTurnAnalysis(
            turn=1,
            response_quality=ResponseQualityAnalysis(
                unsupported_claim=True,
                answered_question=True,
            ),
        )
        signals = map_analysis_to_signals(analysis)
        self.assertTrue(any(s.type == "unsupported_claim" for s in signals))

    def test_05_signal_mapping_positive_evidence(self):
        """Verify evidence backed answer maps deterministically to POSITIVE_EVIDENCE signal."""
        analysis = CandidateTurnAnalysis(
            turn=1,
            response_quality=ResponseQualityAnalysis(
                evidence_backed=True,
                answered_question=True,
            ),
            technical_behavior=TechnicalBehaviorAnalysis(technical_evidence=True),
        )
        signals = map_analysis_to_signals(analysis)
        self.assertTrue(any(s.type == "positive_evidence" for s in signals))

    def test_06_signal_mapping_evasive_and_defensive(self):
        """Verify evasive or defensive responses map to CANDIDATE_DODGES_QUESTION signal."""
        analysis_evasive = CandidateTurnAnalysis(
            turn=1,
            response_quality=ResponseQualityAnalysis(
                evasive=True,
                answered_question=False,
            ),
        )
        signals_evasive = map_analysis_to_signals(analysis_evasive)
        self.assertTrue(any(s.type == "candidate_dodges_question" for s in signals_evasive))

        analysis_defensive = CandidateTurnAnalysis(
            turn=1,
            response_quality=ResponseQualityAnalysis(
                defensive=True,
                answered_question=False,
            ),
        )
        signals_defensive = map_analysis_to_signals(analysis_defensive)
        self.assertTrue(any(s.type == "candidate_dodges_question" for s in signals_defensive))

    def test_07_interview_criteria_mapping_high_confidence(self):
        """Verify high-confidence (>=0.80) signals satisfy required stage criteria."""
        state = self.interview_manager.initialize_state()
        state.current_stage = InterviewStage.STAGE_2_PROBLEM_DISCOVERY

        analysis = CandidateTurnAnalysis(
            turn=2,
            business_understanding=BusinessUnderstandingAnalysis(
                pain_identified=True,
                impact_identified=True,
            ),
            overall_confidence=0.88,  # High confidence
        )

        satisfied = self.interview_manager.update_criteria_from_analysis(state, analysis)
        self.assertIn("business_pain_identified", satisfied)
        self.assertTrue(state.criteria["business_pain_identified"].satisfied)
        self.assertTrue(state.criteria["business_impact_identified"].satisfied)

    def test_08_interview_criteria_mapping_medium_and_low_confidence(self):
        """Verify medium confidence records evidence without satisfying required criteria, and low confidence is ignored."""
        state = self.interview_manager.initialize_state()
        state.current_stage = InterviewStage.STAGE_2_PROBLEM_DISCOVERY

        # Medium confidence (0.60 - 0.79)
        analysis_med = CandidateTurnAnalysis(
            turn=2,
            business_understanding=BusinessUnderstandingAnalysis(pain_identified=True),
            overall_confidence=0.68,
        )
        satisfied_med = self.interview_manager.update_criteria_from_analysis(state, analysis_med)
        # Required criterion must NOT be marked satisfied
        self.assertNotIn("business_pain_identified", satisfied_med)
        self.assertFalse(state.criteria["business_pain_identified"].satisfied)
        # Evidence was captured
        self.assertIn("Medium Confidence", state.criteria["business_pain_identified"].evidence or "")

        # Low confidence (< 0.60)
        analysis_low = CandidateTurnAnalysis(
            turn=3,
            business_understanding=BusinessUnderstandingAnalysis(pain_identified=True),
            overall_confidence=0.45,
        )
        satisfied_low = self.interview_manager.update_criteria_from_analysis(state, analysis_low)
        self.assertEqual(len(satisfied_low), 0)
        self.assertFalse(state.criteria["business_pain_identified"].satisfied)

    def test_09_fact_extraction_and_status(self):
        """Verify facts are extracted and tracked in CandidateFactLedger with lifecycle status."""
        ledger = CandidateFactLedger()
        fact = CandidateFact(
            id="f_vendor",
            category="current_vendor",
            value="LegacyOracle11g",
            confidence=0.91,
            source_turn=2,
            evidence="We are currently on Oracle 11g and struggling with licensing costs",
            status=FactStatus.OBSERVED,
        )
        ledger.add_or_update_fact(fact)

        fact_list = ledger.to_list()
        self.assertEqual(len(fact_list), 1)
        self.assertEqual(fact_list[0]["category"], "current_vendor")
        self.assertEqual(fact_list[0]["status"], "OBSERVED")
        self.assertEqual(fact_list[0]["source_turn"], 2)

    def test_10_claim_vs_fact_separation(self):
        """Verify unverified candidate assertions are categorized as claims, not ground truth facts."""
        claim_ledger = CandidateClaimLedger()
        fact_ledger = CandidateFactLedger()

        claim = CandidateClaim(
            id="c_cost",
            topic="cost_reduction",
            claim="Our platform saves 40% on cloud infrastructure costs",
            evidence_provided=False,
            is_quantitative=True,
            confidence=0.85,
            source_turn=3,
        )
        claim_ledger.add_claim(claim)

        # Ensure claim is in claim ledger and not fact ledger
        self.assertEqual(len(claim_ledger.to_list()), 1)
        self.assertEqual(len(fact_ledger.to_list()), 0)
        self.assertEqual(claim_ledger.to_list()[0]["topic"], "cost_reduction")
        self.assertFalse(claim_ledger.to_list()[0]["evidence_provided"])

    def test_11_contradiction_preservation(self):
        """Verify contradictory statements are preserved and marked with CONTRADICTED status."""
        ledger = CandidateFactLedger()

        fact1 = CandidateFact(
            id="f_timeline_1",
            category="timeline",
            value="3 months",
            confidence=0.85,
            source_turn=2,
            evidence="Our cutover will be completed in 3 months",
            status=FactStatus.OBSERVED,
        )
        ledger.add_or_update_fact(fact1)

        # Later in the interview, conflicting timeline is stated
        fact2 = CandidateFact(
            id="f_timeline_2",
            category="timeline",
            value="9 months",
            confidence=0.90,
            source_turn=6,
            evidence="Realistically, enterprise migration takes about 9 months",
            status=FactStatus.OBSERVED,
        )
        ledger.add_or_update_fact(fact2)

        facts = ledger.to_list()
        self.assertEqual(len(facts), 2)
        statuses = [f["status"] for f in facts]
        # Both facts are retained, and flagged as CONTRADICTED
        self.assertIn("CONTRADICTED", statuses)

    def test_12_analyzer_failure_resilience(self):
        """Verify analyzer handles LLM exceptions or invalid JSON by returning safe neutral analysis."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("MaaS API Timeout / Network Failure")

        analyzer = CandidateBehaviorAnalyzer(llm=mock_llm)
        analysis = analyzer.analyze(
            candidate_message="We can handle your workloads easily.",
            current_stage="STAGE_2_PROBLEM_DISCOVERY",
            turn=3,
        )

        self.assertIsInstance(analysis, CandidateTurnAnalysis)
        self.assertEqual(analysis.overall_confidence, 0.0)
        self.assertTrue(analysis.uncertain)
        self.assertIn("Neutral fallback", analysis.summary_observations)
        # Verify neutral analysis does not falsely trigger claims or errors
        signals = map_analysis_to_signals(analysis)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].type, "neutral_turn")

    def test_13_sqlite_persistence(self):
        """Verify candidate analysis records persist in candidate_turn_analyses SQLite table."""
        test_session_id = f"test-analysis-persist-{uuid.uuid4()}"
        storage.save_session(
            session_id=test_session_id,
            topic="Enterprise Sales",
            role="CTO",
            scenario="Database scale",
            experience="Mid",
            style="Direct",
        )

        analysis = CandidateTurnAnalysis(
            turn=1,
            summary_observations="Introduction and discovery question",
            overall_confidence=0.89,
        )
        facts = [
            CandidateFact(
                id="f_1",
                category="pain_point",
                value="High read latency",
                confidence=0.88,
                source_turn=1,
                evidence="Read latency is 200ms",
            )
        ]
        claims = [
            CandidateClaim(
                id="c_1",
                topic="latency",
                claim="Reduces latency to 5ms",
                confidence=0.90,
                source_turn=1,
            )
        ]
        signals = [InteractionSignal(type="clear_answer", details="Good answer", reason="Direct")]

        storage.save_candidate_analysis(
            session_id=test_session_id,
            turn_number=1,
            candidate_message="Our customers see latency drop from 200ms to 5ms.",
            current_stage="STAGE_2_PROBLEM_DISCOVERY",
            analysis=analysis,
            extracted_facts=facts,
            extracted_claims=claims,
            interaction_signals=signals,
            latency_ms=120.5,
        )

        records = storage.get_candidate_analyses(test_session_id)
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec["turn"], 1)
        self.assertEqual(rec["candidate_message"], "Our customers see latency drop from 200ms to 5ms.")
        self.assertEqual(rec["current_stage"], "STAGE_2_PROBLEM_DISCOVERY")
        self.assertEqual(len(rec["extracted_facts"]), 1)
        self.assertEqual(rec["extracted_facts"][0]["category"], "pain_point")
        self.assertEqual(len(rec["extracted_claims"]), 1)
        self.assertEqual(rec["latency_ms"], 120.5)

    @patch("app.agents.role_agent.get_llm")
    def test_14_langgraph_integration(self, mock_get_llm):
        """Verify RoleAgent multi-turn graph execution analyzes speech and updates ledgers and states."""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        def mock_invoke(messages):
            return AIMessage(content="Understood. What is the current migration timeline?")

        mock_llm.bind_tools.return_value.invoke.side_effect = mock_invoke

        from app.agents.role_agent import RoleAgent

        session_id = f"test-langgraph-phase5-{uuid.uuid4()}"
        agent = RoleAgent(
            role_id="CTO",
            topic="Infrastructure",
            scenario="Database scaling",
            experience="Senior",
            style="Direct",
            session_id=session_id,
        )

        # Mock analyzer to return deterministic CandidateTurnAnalysis
        mock_analysis = CandidateTurnAnalysis(
            turn=1,
            sales_behavior=SalesBehaviorAnalysis(discovery_question=True),
            response_quality=ResponseQualityAnalysis(answered_question=True, evidence_backed=True),
            business_understanding=BusinessUnderstandingAnalysis(pain_identified=True),
            extracted_facts=[
                CandidateFact(
                    id="f_turn1",
                    category="pain_point",
                    value="Latency spikes on read traffic",
                    confidence=0.91,
                    source_turn=1,
                    evidence="We suffer latency spikes on read traffic",
                )
            ],
            overall_confidence=0.90,
        )
        agent.analyzer.analyze = MagicMock(return_value=mock_analysis)

        reply = agent.chat("Hi, we are experiencing significant latency spikes on read traffic. How is your team addressing that?")
        self.assertIn("migration timeline", reply)
        self.assertEqual(agent.turn_count, 1)

        # Check fact ledger in agent
        facts = agent.fact_ledger.to_list()
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["value"], "Latency spikes on read traffic")

        # Check SQLite persistence for candidate analysis
        history = storage.get_candidate_analyses(session_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["turn"], 1)

    def test_15_api_analysis_history_endpoint(self):
        """Test GET /api/session/{session_id}/analysis-history debug inspection endpoint."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.api.endpoints import sessions
        from app.agents.role_agent import RoleAgent

        client = TestClient(app)
        session_id = f"test-api-phase5-{uuid.uuid4()}"

        with patch("app.agents.role_agent.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm
            agent = RoleAgent(
                role_id="CTO",
                topic="Cloud",
                scenario="Migration",
                experience="Mid",
                style="Professional",
                session_id=session_id,
            )
            # Populate a mock fact and claim in ledger
            agent.fact_ledger.add_or_update_fact(
                CandidateFact(
                    id="fact_test",
                    category="budget",
                    value="$250k annual limit",
                    confidence=0.88,
                    source_turn=1,
                    evidence="Our budget is capped at $250k",
                )
            )
            sessions[session_id] = agent

            res = client.get(f"/api/session/{session_id}/analysis-history")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["session_id"], session_id)
            self.assertIn("fact_ledger", data)
            self.assertIn("claim_ledger", data)
            self.assertEqual(len(data["fact_ledger"]), 1)
            self.assertEqual(data["fact_ledger"][0]["category"], "budget")


if __name__ == "__main__":
    unittest.main()
