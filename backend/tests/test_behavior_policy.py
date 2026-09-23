"""Comprehensive Test Suite for Behavioral Policy Engine (Phase 6).

Tests:
1. Action and decision model validation (enum members, serialization, bounds checking).
2. Invalid intensity rejection.
3. Policy matching for unsupported quantitative claims.
4. Policy matching for strong verifiable evidence.
5. Policy matching for evasive / dodged responses.
6. Policy matching for high-impact discovery questions (information disclosure).
7. Persona value orientation influences policy action selection.
8. Dynamic ClientState metrics influence action selection and intensity.
9. Active InterviewStage influences behavioral constraints and default actions.
10. Unresolved stakeholder evaluation goals drive targeted probing behavior.
11. Confidentiality and knowledge boundaries prevent unauthorized disclosure.
12. Deterministic priority resolution and tie-breaking.
13. Auditable PolicyTrace completeness and low-latency performance.
14. SQLite persistence in behavior_decisions table.
15. Developer debug endpoint GET /api/session/{session_id}/behavior-history.
16. Policy mode switching (rule_based vs disabled) for research ablation.
17. Full LangGraph pipeline integration with prompt instruction injection.
"""

import unittest
import uuid
import json
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage

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
from app.models.analysis import (
    CandidateTurnAnalysis,
    ResponseQualityAnalysis,
    SalesBehaviorAnalysis,
    TechnicalBehaviorAnalysis,
    BusinessUnderstandingAnalysis,
    CommercialBehaviorAnalysis,
    CandidateClaim,
    CandidateFact,
)
from app.models.behavior import (
    ActionType,
    BehavioralAction,
    PolicyTrace,
    BehavioralDecision,
)
from app.services.policy_engine import (
    BehavioralPolicyEngine,
    BehaviorPolicy,
    POLICY_CATALOG,
)
from app.services.interview_state_manager import InterviewStateManager
from app.services.storage_service import storage


class TestBehaviorPolicy(unittest.TestCase):
    def setUp(self):
        self.engine = BehavioralPolicyEngine(policy_mode="rule_based")
        self.stage_manager = InterviewStateManager()

        # Standard Test Persona (CTO: High Security & Reliability)
        self.cto_persona = EnterprisePersona(
            profile=PersonaProfile(
                role="CTO",
                title="Chief Technology Officer",
                department="Engineering",
                seniority="Executive",
                years_of_experience=20,
                technical_depth="Deep Architectural",
                communication_style="Direct, skeptical, concise",
                personality_characteristics=["Analytical", "Pragmatic"],
                risk_profile="Risk-Averse",
            ),
            values=[
                ValueOrientation(name="security", weight=0.95, description="Zero tolerance for security vulnerabilities", priority=1),
                ValueOrientation(name="reliability", weight=0.90, description="Mission-critical uptime and SLA compliance", priority=2),
                ValueOrientation(name="cost", weight=0.40, description="Commercials secondary to architectural stability", priority=3),
            ],
            goals=[
                StakeholderGoal(
                    id="verify_security_compliance",
                    description="Confirm SOC2 and HIPAA regulatory compliance",
                    priority=0.95,
                    type="technical",
                    success_condition="Detailed third-party audit reports provided",
                    dealbreaker=True,
                ),
                StakeholderGoal(
                    id="verify_integration_safety",
                    description="Ensure zero-downtime database integration",
                    priority=0.90,
                    type="technical",
                    success_condition="Documented blue/green deployment strategy",
                    dealbreaker=False,
                ),
            ],
            incentives=[
                Incentive(id="avoid_production_incident", description="Prevent downtime during peak trading hours", importance=0.95, category="organizational"),
            ],
            knowledge_boundary=KnowledgeBoundary(
                expert_topics=["Distributed Systems", "Cloud Security", "PostgreSQL"],
                known_topics=["DevOps", "Kubernetes"],
                limited_topics=["Marketing Automation"],
                unknown_topics=["Sales Commission Structures"],
                confidential_topics=["exact budget", "operating margins", "unannounced roadmap"],
                disclosure_rules=["Withhold exact budget until vendor demonstrates technical compliance"],
            ),
            world_model=CompanyContext(
                company_name="Apex Global Financial",
                industry="FinTech",
                company_size="10,000+ employees",
                current_technology_stack=["AWS", "PostgreSQL", "Kafka", "Redis"],
                incumbent_vendors=["Oracle Cloud"],
                pain_points=["Read latency spikes during market open", "High maintenance licensing costs"],
                constraints=["Zero downtime requirement", "Strict SOC2 compliance"],
                budget_constraints="$500,000 annual max",
                timeline="Q4 deployment",
            ),
        )

        # Baseline Client State
        self.baseline_state = ClientState(
            trust=0.50,
            skepticism=0.50,
            patience=0.80,
            engagement=0.60,
            interest=0.50,
            perceived_risk=0.50,
            frustration=0.10,
            confidence_in_candidate=0.50,
        )

        # Baseline Interview State
        self.interview_state = self.stage_manager.initialize_state()

    def test_01_action_and_decision_model_validation(self):
        """Verify ActionType enum coverage, BehavioralAction fields, and BehavioralDecision formatting."""
        # Ensure all 26 canonical actions exist
        expected_actions = [
            "ASK_QUESTION", "FOLLOW_UP", "REQUEST_CLARIFICATION", "SUMMARIZE",
            "CHALLENGE_CLAIM", "REQUEST_EVIDENCE", "PROBE_RISK", "PROBE_TECHNICAL_DETAIL",
            "PROBE_BUSINESS_VALUE", "PROBE_IMPLEMENTATION", "PROBE_SECURITY", "PROBE_SCALABILITY",
            "CHALLENGE_PRICING", "EXPRESS_INTEREST", "EXPRESS_CONCERN", "EXPRESS_SKEPTICISM",
            "ACKNOWLEDGE_POINT", "CONCEDE_POINT", "PUSH_BACK", "REDIRECT", "INTERRUPT",
            "WITHHOLD_INFORMATION", "REVEAL_INFORMATION", "MOVE_FORWARD", "CLOSE", "TERMINATE",
        ]
        for act in expected_actions:
            self.assertIn(act, ActionType.__members__)

        action = BehavioralAction(
            action_type=ActionType.CHALLENGE_CLAIM,
            target="ROI",
            intensity=0.82,
            objective="test_business_claim",
            trigger="unsupported_quantitative_claim",
            reason="Candidate claimed 40% reduction without supporting evidence.",
            required_information=["calculation_method"],
            expected_effect="increase_evidence_requirement",
        )
        self.assertEqual(action.action_type, ActionType.CHALLENGE_CLAIM)
        self.assertEqual(action.intensity, 0.82)
        d_dict = action.to_dict()
        self.assertEqual(d_dict["action_type"], "CHALLENGE_CLAIM")
        self.assertEqual(d_dict["target"], "ROI")

        trace = PolicyTrace(
            turn=1,
            selected_action="CHALLENGE_CLAIM",
            intensity=0.82,
            reason=action.reason,
        )
        decision = BehavioralDecision(
            primary_action=action,
            intensity=0.82,
            policy_id="unsupported_quantitative_claim",
            trace=trace,
        )
        prompt_instructions = decision.format_prompt_instructions()
        self.assertIn("PRIMARY ACTION: CHALLENGE_CLAIM", prompt_instructions)
        self.assertIn("TARGET: ROI", prompt_instructions)
        self.assertIn("INTENSITY: 0.82", prompt_instructions)
        self.assertIn("MANDATORY EXECUTION CONSTRAINTS", prompt_instructions)

    def test_02_invalid_intensity_rejected(self):
        """Verify values < 0.0 or > 1.0 are rejected by validators."""
        # Valid intensities
        a1 = BehavioralAction(
            action_type=ActionType.ASK_QUESTION,
            intensity=0.0,
            objective="ask",
            trigger="init",
            reason="valid zero",
        )
        self.assertEqual(a1.intensity, 0.0)

        a2 = BehavioralAction(
            action_type=ActionType.ASK_QUESTION,
            intensity=1.0,
            objective="ask",
            trigger="init",
            reason="valid one",
        )
        self.assertEqual(a2.intensity, 1.0)

        # Invalid: < 0.0
        with self.assertRaises(ValueError):
            BehavioralAction(
                action_type=ActionType.ASK_QUESTION,
                intensity=-0.1,
                objective="ask",
                trigger="init",
                reason="invalid negative",
            )

        # Invalid: > 1.0
        with self.assertRaises(ValueError):
            BehavioralAction(
                action_type=ActionType.ASK_QUESTION,
                intensity=1.1,
                objective="ask",
                trigger="init",
                reason="invalid excessive",
            )

    def test_03_policy_matching_unsupported_claim(self):
        """Unsupported quantitative claim triggers CHALLENGE_CLAIM with REQUEST_EVIDENCE."""
        analysis = CandidateTurnAnalysis(
            turn=2,
            response_quality=ResponseQualityAnalysis(
                unsupported_claim=True,
                evidence_backed=False,
            ),
            extracted_claims=[
                CandidateClaim(
                    id="c1",
                    topic="latency",
                    claim="We reduce latency by 90% in every deployment.",
                    is_quantitative=True,
                    evidence_provided=False,
                    confidence=0.90,
                    source_turn=2,
                )
            ],
        )

        decision = self.engine.evaluate(
            persona=self.cto_persona,
            client_state=self.baseline_state,
            interview_state=self.interview_state,
            candidate_analysis=analysis,
            turn=2,
            candidate_message="We reduce latency by 90% in every deployment.",
        )

        self.assertEqual(decision.primary_action.action_type, ActionType.CHALLENGE_CLAIM)
        self.assertEqual(decision.primary_action.target, "latency")
        self.assertIsNotNone(decision.secondary_action)
        self.assertEqual(decision.secondary_action.action_type, ActionType.REQUEST_EVIDENCE)
        self.assertEqual(decision.policy_id, "unsupported_quantitative_claim")

    def test_04_policy_matching_strong_evidence(self):
        """Candidate provides strong quantitative evidence -> ACKNOWLEDGE_POINT + PROBE_TECHNICAL_DETAIL."""
        analysis = CandidateTurnAnalysis(
            turn=3,
            response_quality=ResponseQualityAnalysis(
                evidence_backed=True,
                answered_question=True,
            ),
            technical_behavior=TechnicalBehaviorAnalysis(
                technical_evidence=True,
                architecture_explanation=True,
            ),
            extracted_claims=[
                CandidateClaim(
                    id="c2",
                    topic="throughput",
                    claim="Benchmarked at 50,000 ops/sec over 30 days in banking deployment",
                    is_quantitative=True,
                    evidence_provided=True,
                    confidence=0.95,
                    source_turn=3,
                )
            ],
        )

        decision = self.engine.evaluate(
            persona=self.cto_persona,
            client_state=self.baseline_state,
            interview_state=self.interview_state,
            candidate_analysis=analysis,
            turn=3,
            candidate_message="We benchmarked at 50,000 ops/sec over 30 days in banking deployment.",
        )

        self.assertEqual(decision.primary_action.action_type, ActionType.ACKNOWLEDGE_POINT)
        self.assertEqual(decision.secondary_action.action_type, ActionType.PROBE_TECHNICAL_DETAIL)
        self.assertEqual(decision.policy_id, "high_evidence_technical")

    def test_05_policy_matching_evasive_response(self):
        """Candidate dodges question -> PUSH_BACK + FOLLOW_UP."""
        analysis = CandidateTurnAnalysis(
            turn=4,
            response_quality=ResponseQualityAnalysis(
                evasive=True,
                answered_question=False,
                defensive=True,
            ),
        )

        decision = self.engine.evaluate(
            persona=self.cto_persona,
            client_state=self.baseline_state,
            interview_state=self.interview_state,
            candidate_analysis=analysis,
            turn=4,
            candidate_message="I'd rather not discuss architecture right now. Let's talk about pricing discounts.",
        )

        self.assertEqual(decision.primary_action.action_type, ActionType.PUSH_BACK)
        self.assertEqual(decision.secondary_action.action_type, ActionType.FOLLOW_UP)
        self.assertEqual(decision.policy_id, "candidate_dodges_evasive")

    def test_06_policy_matching_strong_discovery(self):
        """Candidate asks high-impact discovery question -> REVEAL_INFORMATION + EXPRESS_INTEREST."""
        analysis = CandidateTurnAnalysis(
            turn=2,
            sales_behavior=SalesBehaviorAnalysis(
                discovery_question=True,
                needs_exploration=True,
            ),
            business_understanding=BusinessUnderstandingAnalysis(
                pain_identified=True,
            ),
        )

        decision = self.engine.evaluate(
            persona=self.cto_persona,
            client_state=self.baseline_state,
            interview_state=self.interview_state,
            candidate_analysis=analysis,
            turn=2,
            candidate_message="What happens to your transaction processing and downstream revenue when latency spikes occur during market open?",
        )

        self.assertEqual(decision.primary_action.action_type, ActionType.REVEAL_INFORMATION)
        self.assertEqual(decision.secondary_action.action_type, ActionType.EXPRESS_INTEREST)
        self.assertEqual(decision.policy_id, "strong_discovery_pain_uncovered")
        # Authorized pain point from World Model is populated
        self.assertGreater(len(decision.primary_action.information_to_reveal), 0)
        self.assertIn("latency spikes", decision.primary_action.information_to_reveal[0].lower())

    def test_07_persona_value_influences_action(self):
        """Different value configurations produce different policy responses to the same input."""
        # Persona 1: High Security CTO (security=0.95)
        # Candidate says: "Our security controls are simple and standard."
        analysis_sec = CandidateTurnAnalysis(
            turn=3,
            technical_behavior=TechnicalBehaviorAnalysis(security_discussion=True),
        )
        decision_cto = self.engine.evaluate(
            persona=self.cto_persona,
            client_state=self.baseline_state,
            interview_state=self.interview_state,
            candidate_analysis=analysis_sec,
            turn=3,
            candidate_message="Our security controls are simple and standard.",
        )
        self.assertEqual(decision_cto.primary_action.action_type, ActionType.PROBE_SECURITY)

        # Persona 2: Commercial Sales VP (security=0.10, cost=0.95, revenue=0.95)
        vp_sales_persona = EnterprisePersona(
            profile=PersonaProfile(
                role="SALES_MANAGER",
                title="VP Commercial Sales",
                department="Sales",
                seniority="Executive",
                years_of_experience=15,
                technical_depth="Strategic High-Level",
                communication_style="Energetic, persuasive",
                personality_characteristics=["Commercial", "Goal-Oriented"],
                risk_profile="Calculated Risk-Taker",
            ),
            values=[
                ValueOrientation(name="cost", weight=0.95, description="Maximize margin and TCO", priority=1),
                ValueOrientation(name="security", weight=0.10, description="Handled by IT team", priority=3),
            ],
            goals=[],
            incentives=[],
            knowledge_boundary=KnowledgeBoundary(),
            world_model=None,
        )

        decision_vp = self.engine.evaluate(
            persona=vp_sales_persona,
            client_state=self.baseline_state,
            interview_state=self.interview_state,
            candidate_analysis=analysis_sec,
            turn=3,
            candidate_message="Our security controls are simple and standard.",
        )
        # VP does not prioritize PROBE_SECURITY
        self.assertNotEqual(decision_vp.primary_action.action_type, ActionType.PROBE_SECURITY)

    def test_08_client_state_influences_action_and_intensity(self):
        """Same input under high skepticism yields higher intensity challenge than under high trust."""
        claim_analysis = CandidateTurnAnalysis(
            turn=3,
            response_quality=ResponseQualityAnalysis(unsupported_claim=True),
            extracted_claims=[
                CandidateClaim(id="c1", topic="ROI", claim="40% cost reduction", is_quantitative=True, confidence=0.88, source_turn=3)
            ],
        )

        # High Skepticism State
        skeptical_state = ClientState(
            trust=0.20,
            skepticism=0.90,
            frustration=0.40,
            perceived_risk=0.80,
            patience=0.30,
        )
        dec_skeptical = self.engine.evaluate(
            persona=self.cto_persona,
            client_state=skeptical_state,
            interview_state=self.interview_state,
            candidate_analysis=claim_analysis,
            turn=3,
            candidate_message="We achieve a 40% cost reduction across the board.",
        )

        # High Trust State
        trusting_state = ClientState(
            trust=0.85,
            skepticism=0.15,
            frustration=0.05,
            perceived_risk=0.10,
            patience=0.90,
        )
        dec_trusting = self.engine.evaluate(
            persona=self.cto_persona,
            client_state=trusting_state,
            interview_state=self.interview_state,
            candidate_analysis=claim_analysis,
            turn=3,
            candidate_message="We achieve a 40% cost reduction across the board.",
        )

        self.assertGreater(dec_skeptical.intensity, dec_trusting.intensity)
        self.assertGreater(dec_skeptical.intensity, 0.75)
        self.assertLess(dec_trusting.intensity, 0.65)

    def test_09_interview_stage_influences_behavior(self):
        """Interview stage constrains action selection and applies stage defaults."""
        # Stage 2 (Discovery): Pitch attempt triggers REDIRECT
        self.interview_state.current_stage = InterviewStage.STAGE_2_PROBLEM_DISCOVERY
        pitch_analysis = CandidateTurnAnalysis(
            turn=2,
            sales_behavior=SalesBehaviorAnalysis(value_proposition=True),
        )
        dec_stage2 = self.engine.evaluate(
            persona=self.cto_persona,
            client_state=self.baseline_state,
            interview_state=self.interview_state,
            candidate_analysis=pitch_analysis,
            turn=2,
            candidate_message="Our platform has 50 enterprise features including real-time replication.",
        )
        self.assertEqual(dec_stage2.primary_action.action_type, ActionType.REDIRECT)

        # Stage 4 (Objections): Stage default triggers PROBE_RISK
        self.interview_state.current_stage = InterviewStage.STAGE_4_OBJECTIONS_AND_DEEP_DIVE
        dec_stage4 = self.engine.evaluate(
            persona=self.cto_persona,
            client_state=self.baseline_state,
            interview_state=self.interview_state,
            candidate_analysis=None,
            turn=7,
            candidate_message="How do you view our solution so far?",
        )
        self.assertEqual(dec_stage4.primary_action.action_type, ActionType.PROBE_RISK)

        # Stage 5 (Commercials): Stage default triggers MOVE_FORWARD / CLOSE
        self.interview_state.current_stage = InterviewStage.STAGE_5_COMMERCIALS_AND_CLOSING
        dec_stage5 = self.engine.evaluate(
            persona=self.cto_persona,
            client_state=self.baseline_state,
            interview_state=self.interview_state,
            candidate_analysis=None,
            turn=11,
            candidate_message="What are the next steps to move to a POC?",
        )
        self.assertEqual(dec_stage5.primary_action.action_type, ActionType.MOVE_FORWARD)

    def test_10_unresolved_goal_drives_probing(self):
        """Active unresolved architecture goal drives PROBE_TECHNICAL_DETAIL when architecture is mentioned."""
        analysis = CandidateTurnAnalysis(
            turn=3,
            technical_behavior=TechnicalBehaviorAnalysis(architecture_explanation=True),
        )
        decision = self.engine.evaluate(
            persona=self.cto_persona,
            client_state=self.baseline_state,
            interview_state=self.interview_state,
            candidate_analysis=analysis,
            turn=3,
            candidate_message="Integration with your existing stack is seamless via our REST and Kafka connectors.",
        )
        self.assertEqual(decision.primary_action.action_type, ActionType.PROBE_TECHNICAL_DETAIL)
        self.assertEqual(decision.policy_id, "unresolved_integration_goal")

    def test_11_confidentiality_boundary_enforced(self):
        """Confidential topic inquiry triggers WITHHOLD_INFORMATION with topic withheld."""
        decision = self.engine.evaluate(
            persona=self.cto_persona,
            client_state=self.baseline_state,
            interview_state=self.interview_state,
            candidate_analysis=None,
            turn=3,
            candidate_message="Could you share your exact approved budget for this infrastructure project?",
        )
        self.assertEqual(decision.primary_action.action_type, ActionType.WITHHOLD_INFORMATION)
        self.assertIn("budget", decision.primary_action.target.lower())
        self.assertGreater(len(decision.primary_action.information_to_withhold), 0)
        self.assertEqual(len(decision.primary_action.information_to_reveal), 0)

    def test_12_deterministic_priority_resolution(self):
        """Higher-priority policies deterministically override lower-priority policies."""
        # Multi-signal: candidate asks for confidential data (Priority 90) AND makes an unsupported claim (Priority 50)
        analysis_multi = CandidateTurnAnalysis(
            turn=4,
            response_quality=ResponseQualityAnalysis(unsupported_claim=True),
        )
        dec_confidential = self.engine.evaluate(
            persona=self.cto_persona,
            client_state=self.baseline_state,
            interview_state=self.interview_state,
            candidate_analysis=analysis_multi,
            turn=4,
            candidate_message="We guarantee 99.999% uptime. By the way, what is your exact allocated budget?",
        )
        # Priority 90 (Confidentiality) must win over Priority 50 (Unsupported Claim)
        self.assertEqual(dec_confidential.primary_action.action_type, ActionType.WITHHOLD_INFORMATION)

        # Frustration >= 0.95 (Priority 100) must win over everything else -> TERMINATE
        frustrated_state = ClientState(frustration=0.98, skepticism=0.95, trust=0.10)
        dec_terminate = self.engine.evaluate(
            persona=self.cto_persona,
            client_state=frustrated_state,
            interview_state=self.interview_state,
            candidate_analysis=analysis_multi,
            turn=5,
            candidate_message="What is your budget?",
        )
        self.assertEqual(dec_terminate.primary_action.action_type, ActionType.TERMINATE)

    def test_13_policy_trace_completeness(self):
        """Verify PolicyTrace records complete auditable context and latency < 10ms."""
        analysis = CandidateTurnAnalysis(
            turn=2,
            response_quality=ResponseQualityAnalysis(unsupported_claim=True),
        )
        decision = self.engine.evaluate(
            persona=self.cto_persona,
            client_state=self.baseline_state,
            interview_state=self.interview_state,
            candidate_analysis=analysis,
            turn=2,
            candidate_message="Our latency is the lowest in the market.",
        )
        trace = decision.trace
        self.assertEqual(trace.turn, 2)
        self.assertIn("unsupported_claim", trace.candidate_signals)
        self.assertEqual(trace.selected_action, decision.primary_action.action_type.value)
        self.assertIn("trust", trace.state)
        self.assertIn("skepticism", trace.state)
        self.assertGreaterEqual(len(trace.matched_policies), 1)
        self.assertLess(trace.execution_latency_ms, 10.0)  # Pure python evaluation is fast

    def test_14_sqlite_persistence_and_retrieval(self):
        """Verify behavioral decision persistence in SQLite and retrieval."""
        session_id = f"test-behavior-persist-{uuid.uuid4()}"
        storage.save_session(
            session_id=session_id,
            topic="Infrastructure",
            role="CTO",
            scenario="Database scale",
            experience="Senior",
            style="Direct",
        )

        action = BehavioralAction(
            action_type=ActionType.CHALLENGE_CLAIM,
            target="latency",
            intensity=0.78,
            objective="test_latency_claim",
            trigger="unsupported_claim",
            reason="Candidate claimed sub-millisecond latency without benchmark.",
        )
        trace = PolicyTrace(
            turn=1,
            candidate_signals=["unsupported_claim"],
            selected_action="CHALLENGE_CLAIM",
            intensity=0.78,
            reason=action.reason,
            execution_latency_ms=0.45,
        )
        decision = BehavioralDecision(
            primary_action=action,
            secondary_action=None,
            intensity=0.78,
            policy_id="unsupported_general_claim",
            trace=trace,
            mode="rule_based",
        )

        storage.save_behavior_decision(session_id=session_id, turn_number=1, decision=decision)

        history = storage.get_behavior_history(session_id)
        self.assertEqual(len(history), 1)
        rec = history[0]
        self.assertEqual(rec["turn"], 1)
        self.assertEqual(rec["action"], "CHALLENGE_CLAIM")
        self.assertEqual(rec["target"], "latency")
        self.assertAlmostEqual(rec["intensity"], 0.78, places=2)
        self.assertEqual(rec["policy_id"], "unsupported_general_claim")
        self.assertIn("unsupported_claim", rec["trace"]["candidate_signals"])

    def test_15_debug_api_behavior_history(self):
        """Verify GET /api/session/{session_id}/behavior-history endpoint."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.api.endpoints import sessions
        from app.agents.role_agent import RoleAgent

        client = TestClient(app)
        session_id = f"test-api-behavior-{uuid.uuid4()}"

        with patch("app.agents.role_agent.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm
            agent = RoleAgent(
                role_id="CTO",
                topic="Cloud Infrastructure",
                scenario="Architecture Review",
                experience="Senior",
                style="Direct",
                session_id=session_id,
            )
            sessions[session_id] = agent

        # Save a test decision
        action = BehavioralAction(
            action_type=ActionType.PROBE_SECURITY,
            target="SOC2",
            intensity=0.85,
            objective="verify_compliance",
            trigger="security_discussion",
            reason="Verify SOC2 reports",
        )
        trace = PolicyTrace(turn=1, selected_action="PROBE_SECURITY", intensity=0.85, reason=action.reason)
        dec = BehavioralDecision(primary_action=action, intensity=0.85, policy_id="unresolved_security_goal", trace=trace)
        storage.save_behavior_decision(session_id, turn_number=1, decision=dec)
        agent.current_decision = dec

        response = client.get(f"/api/session/{session_id}/behavior-history")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["session_id"], session_id)
        self.assertEqual(data["policy_mode"], "rule_based")
        self.assertEqual(data["total_decisions"], 1)
        self.assertEqual(data["history"][0]["action"], "PROBE_SECURITY")
        self.assertEqual(data["current_decision"]["primary_action"]["action_type"], "PROBE_SECURITY")

    def test_16_policy_mode_ablation_support(self):
        """Verify policy engine supports disabled pass-through mode for research ablation."""
        engine_disabled = BehavioralPolicyEngine(policy_mode="disabled")
        decision = engine_disabled.evaluate(
            persona=self.cto_persona,
            client_state=self.baseline_state,
            interview_state=self.interview_state,
            candidate_analysis=None,
            turn=1,
            candidate_message="Hello, nice to meet you.",
        )
        self.assertEqual(decision.mode, "disabled")
        self.assertEqual(decision.policy_id, "disabled_passthrough")
        self.assertEqual(decision.trace.mode, "disabled")

    @patch("app.agents.role_agent.get_llm")
    def test_17_full_langgraph_pipeline_integration(self, mock_get_llm):
        """Verify RoleAgent multi-turn graph execution analyzes speech, updates states, evaluates policy, and injects directives."""
        captured_messages = []

        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        def mock_invoke(messages):
            captured_messages.append(messages)
            return AIMessage(content="What benchmarks substantiate that 40% reduction claim?")

        mock_llm.bind_tools.return_value.invoke.side_effect = mock_invoke

        from app.agents.role_agent import RoleAgent

        session_id = f"test-langgraph-phase6-{uuid.uuid4()}"
        agent = RoleAgent(
            role_id="CTO",
            topic="Database Architecture",
            scenario="Migration scaling",
            experience="Senior",
            style="Direct",
            session_id=session_id,
        )

        # Mock candidate analyzer to return an unsupported quantitative claim
        mock_analysis = CandidateTurnAnalysis(
            turn=1,
            response_quality=ResponseQualityAnalysis(
                unsupported_claim=True,
                evidence_backed=False,
                answered_question=True,
            ),
            extracted_claims=[
                CandidateClaim(
                    id="c1",
                    topic="ROI",
                    claim="We reduce overall infrastructure cost by 40% immediately.",
                    is_quantitative=True,
                    evidence_provided=False,
                    confidence=0.92,
                    source_turn=1,
                )
            ],
            overall_confidence=0.90,
        )
        agent.analyzer.analyze = MagicMock(return_value=mock_analysis)

        reply = agent.chat("We reduce overall infrastructure cost by 40% immediately.")
        self.assertIn("benchmarks substantiate", reply)
        self.assertEqual(agent.turn_count, 1)

        # Verify behavioral decision was produced and stored on agent
        self.assertIsNotNone(agent.current_decision)
        self.assertEqual(agent.current_decision.primary_action.action_type, ActionType.CHALLENGE_CLAIM)
        self.assertEqual(agent.current_decision.primary_action.target, "ROI")

        # Verify SQLite persistence
        history = storage.get_behavior_history(session_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["action"], "CHALLENGE_CLAIM")

        # Verify the prompt passed to LLM contained mandatory behavioral directives
        self.assertGreater(len(captured_messages), 0)
        sys_msg = captured_messages[0][0].content
        self.assertIn("SELECTED BEHAVIORAL ACTION", sys_msg)
        self.assertIn("PRIMARY ACTION: CHALLENGE_CLAIM", sys_msg)
        self.assertIn("TARGET: ROI", sys_msg)
        self.assertIn("MANDATORY EXECUTION CONSTRAINTS", sys_msg)


if __name__ == "__main__":
    unittest.main()
