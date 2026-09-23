"""Comprehensive Unit and Integration Test Suite for Phase 9: Configurable Persona & Scenario Builder.

Validates:
1. PersonaConfiguration schema validation, bounds clamping, and error handling
2. Role-specific trait schemas (CTO vs CFO vs HR vs CEO)
3. Role simulation defaults and presets
4. Configuration precedence: Role Defaults -> Preset -> Scenario Overrides -> User Configuration
5. Trait vs Value independence (kindness != security value)
6. Policy engine integration: skepticism divergence on identical candidate input
7. Policy engine strictness and kindness modulation
8. Trait interactions (strictness + skepticism; strictness + kindness)
9. ClientState initialization calibrated by traits
10. SQLite persistence of resolved persona configuration
11. Persona schema versioning
12. API endpoints (/api/personas/configuration-schema/{role} and debug endpoint)
13. Backward compatibility with unconfigured sessions
14. Inspectable trait influences in PolicyTrace
15. Formal research experiments (RQ7, RQ8, RQ9)
16. Deterministic performance (<1ms, 0 extra LLM calls)
"""

import pytest
import time
from fastapi.testclient import TestClient

from app.main import app
from app.models.configuration import (
    PersonaTraitDefinition,
    PersonaPreset,
    PersonaConfiguration,
    RoleConfigurationSchema,
)
from app.roles.traits import (
    get_role_configuration_schema,
    resolve_persona_configuration,
    generate_persona_summary,
    ROLE_TRAIT_DEFINITIONS,
    ROLE_SIMULATION_DEFAULTS,
    ROLE_PRESETS,
)
from app.roles.registry import get_persona
from app.models.state import ClientState, InteractionSignal
from app.models.stages import InterviewState, InterviewStage
from app.models.analysis import (
    CandidateTurnAnalysis,
    CandidateClaim,
    ResponseQualityAnalysis,
    SalesBehaviorAnalysis,
    TechnicalBehaviorAnalysis,
    BusinessUnderstandingAnalysis,
)
from app.models.behavior import ActionType
from app.services.state_manager import ClientStateManager
from app.services.policy_engine import BehavioralPolicyEngine
from app.agents.role_agent import RoleAgent
from app.services.storage_service import storage
from app.evaluation.evaluation_runner import EvaluationRunner


client = TestClient(app)


class TestPersonaConfiguration:
    """Test suite for Phase 9 Configurable Persona & Scenario Builder."""

    def test_01_persona_configuration_validation_and_bounds(self):
        """Test strict validation, bounds checking [0.0, 1.0], and canonical role normalization."""
        # Valid configuration
        valid_cfg = PersonaConfiguration(
            role="CTO",
            preset="STRICT",
            traits={"strictness": 0.90, "skepticism": 0.85, "kindness": 0.30},
            persona_schema_version="1.0",
        )
        assert valid_cfg.role == "CTO"
        assert valid_cfg.preset == "STRICT"
        assert valid_cfg.get_trait("strictness") == 0.90
        assert valid_cfg.get_trait("skepticism") == 0.85
        assert valid_cfg.get_trait("non_existent", 0.50) == 0.50

        # Out-of-bounds trait (> 1.0) must raise ValueError
        with pytest.raises(ValueError, match="out of bounds"):
            PersonaConfiguration(
                role="CTO",
                traits={"strictness": 1.50},
            )

        # Out-of-bounds trait (< 0.0) must raise ValueError
        with pytest.raises(ValueError, match="out of bounds"):
            PersonaConfiguration(
                role="CTO",
                traits={"kindness": -0.20},
            )

        # Empty role must raise ValueError
        with pytest.raises(ValueError, match="Role cannot be empty"):
            PersonaConfiguration(role="")

    def test_02_role_specific_trait_schemas(self):
        """Verify role-specific trait definitions strictly expose relevant controls."""
        cto_schema = get_role_configuration_schema("CTO")
        cfo_schema = get_role_configuration_schema("CFO")
        hr_schema = get_role_configuration_schema("HR")

        cto_trait_ids = [t.id for t in cto_schema.traits]
        cfo_trait_ids = [t.id for t in cfo_schema.traits]
        hr_trait_ids = [t.id for t in hr_schema.traits]

        # CTO must expose technical architecture and security sensitivity
        assert "technical_depth" in cto_trait_ids
        assert "architecture_focus" in cto_trait_ids
        assert "security_sensitivity" in cto_trait_ids

        # CFO must expose financial scrutiny, cost sensitivity, and ROI focus
        assert "financial_scrutiny" in cfo_trait_ids
        assert "cost_sensitivity" in cfo_trait_ids
        assert "roi_focus" in cfo_trait_ids
        # CFO should NOT expose low-level technical architecture depth
        assert "technical_depth" not in cfo_trait_ids

        # HR must expose empathy, patience, and conflict sensitivity
        assert "empathy" in hr_trait_ids
        assert "conflict_sensitivity" in hr_trait_ids
        assert "financial_scrutiny" not in hr_trait_ids

    def test_03_role_defaults_sensible_definitions(self):
        """Verify sensible simulation defaults exist and are properly bounded."""
        for role_id, defaults in ROLE_SIMULATION_DEFAULTS.items():
            assert len(defaults) >= 5, f"Role {role_id} should define at least 5 default traits"
            for trait_id, val in defaults.items():
                assert 0.0 <= val <= 1.0, f"Default {trait_id}={val} for {role_id} out of bounds"

        # Check documented conceptual defaults
        assert ROLE_SIMULATION_DEFAULTS["CTO"]["technical_depth"] >= 0.85
        assert ROLE_SIMULATION_DEFAULTS["CTO"]["skepticism"] >= 0.70
        assert ROLE_SIMULATION_DEFAULTS["CFO"]["financial_scrutiny"] >= 0.90
        assert ROLE_SIMULATION_DEFAULTS["CFO"]["cost_sensitivity"] >= 0.85

    def test_04_preset_definitions_and_overrides(self):
        """Verify presets load correctly and user sliders override preset values."""
        # Balanced preset returns default values
        balanced_cfg = resolve_persona_configuration("CTO", preset="BALANCED")
        assert balanced_cfg.get_trait("strictness") == ROLE_SIMULATION_DEFAULTS["CTO"]["strictness"]

        # Strict preset applies strictness and skepticism modifiers
        strict_cfg = resolve_persona_configuration("CTO", preset="STRICT")
        assert strict_cfg.get_trait("strictness") == 0.90
        assert strict_cfg.get_trait("skepticism") == 0.85
        assert strict_cfg.get_trait("kindness") == 0.25

        # Custom overrides on top of Strict preset
        custom_cfg = resolve_persona_configuration(
            "CTO",
            preset="STRICT",
            custom_traits={"kindness": 0.40, "technical_depth": 0.95, "patience": 0.50},
        )
        assert custom_cfg.get_trait("strictness") == 0.90  # from preset
        assert custom_cfg.get_trait("kindness") == 0.40    # overridden by user
        assert custom_cfg.get_trait("technical_depth") == 0.95  # overridden by user
        assert custom_cfg.get_trait("patience") == 0.50   # overridden by user

    def test_05_configuration_precedence_order(self):
        """Verify precedence: Role Defaults -> Preset -> Scenario Overrides -> User Configuration."""
        # Baseline CTO skepticism default is 0.75
        base_skep = ROLE_SIMULATION_DEFAULTS["CTO"]["skepticism"]

        # 1. Preset modifies skepticism
        cfg_preset = resolve_persona_configuration("CTO", preset="FRIENDLY")
        assert cfg_preset.get_trait("skepticism") == 0.40

        # 2. Scenario overrides preset
        cfg_scenario = resolve_persona_configuration(
            "CTO",
            preset="FRIENDLY",
            scenario_overrides={"skepticism": 0.65},
        )
        assert cfg_scenario.get_trait("skepticism") == 0.65

        # 3. User configuration overrides scenario
        cfg_user = resolve_persona_configuration(
            "CTO",
            preset="FRIENDLY",
            scenario_overrides={"skepticism": 0.65},
            custom_traits={"skepticism": 0.92},
        )
        assert cfg_user.get_trait("skepticism") == 0.92

    def test_06_trait_vs_value_independence(self):
        """Verify changing persona traits does not alter or replace Phase 2 values, goals, or incentives."""
        persona = get_persona("CTO", scenario="Enterprise Cloud Platform")
        security_val = next((v for v in persona.values if v.name == "security"), None)
        assert security_val is not None
        initial_security_weight = security_val.weight

        # Apply high kindness configuration
        kind_cfg = resolve_persona_configuration("CTO", custom_traits={"kindness": 0.95, "strictness": 0.20})
        agent = RoleAgent(
            role_id="CTO",
            topic="Tech Interview",
            scenario="Enterprise Cloud Platform",
            experience="Senior",
            style="Professional",
            session_id="test_independence_session",
            persona_configuration=kind_cfg,
        )

        # The underlying persona values must remain identical
        agent_security_val = next((v for v in agent.persona.values if v.name == "security"), None)
        assert agent_security_val is not None
        assert agent_security_val.weight == initial_security_weight
        assert agent.persona_configuration.get_trait("kindness") == 0.95

    def test_07_policy_engine_skepticism_divergence(self):
        """Verify low vs high skepticism on identical candidate input produces different policy actions."""
        policy_engine = BehavioralPolicyEngine(policy_mode="rule_based")
        persona = get_persona("CTO")
        client_state = ClientState(trust=0.50, skepticism=0.60, patience=0.60, frustration=0.10)
        interview_state = InterviewState(current_stage=InterviewStage.STAGE_2_PROBLEM_DISCOVERY)

        # Candidate makes an unsupported general claim
        analysis = CandidateTurnAnalysis(
            response_quality=ResponseQualityAnalysis(unsupported_claim=True, vague=False),
            sales_behavior=SalesBehaviorAnalysis(),
            technical_behavior=TechnicalBehaviorAnalysis(),
            business_understanding=BusinessUnderstandingAnalysis(),
            extracted_claims=[CandidateClaim(id="c1", claim="We guarantee seamless integration with no effort", topic="integration", is_quantitative=False, source_turn=1)],
        )
        msg = "We guarantee seamless integration with zero effort on your part."

        # Configuration A: Low Skepticism CTO (skepticism = 0.20)
        low_skep_cfg = PersonaConfiguration(role="CTO", traits={"skepticism": 0.20, "strictness": 0.40, "kindness": 0.80})
        decision_low = policy_engine.evaluate(
            persona=persona,
            client_state=client_state,
            interview_state=interview_state,
            candidate_analysis=analysis,
            turn=1,
            candidate_message=msg,
            persona_config=low_skep_cfg,
        )

        # Configuration B: High Skepticism CTO (skepticism = 0.90)
        high_skep_cfg = PersonaConfiguration(role="CTO", traits={"skepticism": 0.90, "strictness": 0.85, "kindness": 0.25})
        decision_high = policy_engine.evaluate(
            persona=persona,
            client_state=client_state,
            interview_state=interview_state,
            candidate_analysis=analysis,
            turn=1,
            candidate_message=msg,
            persona_config=high_skep_cfg,
        )

        # Low skepticism should NOT aggressively challenge the general claim (falls through to discovery/rapport)
        assert decision_low.primary_action.action_type != ActionType.CHALLENGE_CLAIM

        # High skepticism MUST challenge the claim or demand proof
        assert decision_high.primary_action.action_type in (ActionType.CHALLENGE_CLAIM, ActionType.REQUEST_EVIDENCE)
        assert decision_high.intensity > decision_low.intensity

    def test_08_policy_engine_strictness_and_kindness(self):
        """Verify strictness boosts challenge scores while kindness moderates confrontational intensity."""
        policy_engine = BehavioralPolicyEngine(policy_mode="rule_based")
        persona = get_persona("CTO")
        client_state = ClientState(trust=0.50, skepticism=0.70, patience=0.50, frustration=0.10)
        interview_state = InterviewState(current_stage=InterviewStage.STAGE_2_PROBLEM_DISCOVERY)

        analysis = CandidateTurnAnalysis(
            response_quality=ResponseQualityAnalysis(unsupported_claim=True, vague=False),
            sales_behavior=SalesBehaviorAnalysis(),
            technical_behavior=TechnicalBehaviorAnalysis(),
            business_understanding=BusinessUnderstandingAnalysis(),
            extracted_claims=[CandidateClaim(id="c2", claim="We have 99.999% reliability in all clouds", topic="reliability", is_quantitative=True, source_turn=1)],
        )
        msg = "We have 99.999% reliability in all cloud environments."

        # Case 1: Strict & Blunt CTO (high strictness, low kindness)
        strict_blunt_cfg = PersonaConfiguration(role="CTO", traits={"strictness": 0.95, "kindness": 0.20, "skepticism": 0.85})
        dec_strict = policy_engine.evaluate(
            persona=persona,
            client_state=client_state,
            interview_state=interview_state,
            candidate_analysis=analysis,
            turn=1,
            candidate_message=msg,
            persona_config=strict_blunt_cfg,
        )

        # Case 2: Supportive & Kind CTO (high strictness, high kindness)
        strict_kind_cfg = PersonaConfiguration(role="CTO", traits={"strictness": 0.85, "kindness": 0.85, "skepticism": 0.85})
        dec_kind = policy_engine.evaluate(
            persona=persona,
            client_state=client_state,
            interview_state=interview_state,
            candidate_analysis=analysis,
            turn=1,
            candidate_message=msg,
            persona_config=strict_kind_cfg,
        )

        # Both challenge the quantitative claim (values/evidence maintained)
        assert dec_strict.primary_action.action_type in (ActionType.REQUEST_EVIDENCE, ActionType.CHALLENGE_CLAIM)
        assert dec_kind.primary_action.action_type in (ActionType.REQUEST_EVIDENCE, ActionType.CHALLENGE_CLAIM)

        # But Kindness moderates the confrontation intensity!
        assert dec_kind.intensity < dec_strict.intensity
        # And strictness + kindness triggers respectful inquiry objective
        assert dec_kind.primary_action.objective == "firm_but_respectful_inquiry"

    def test_09_trait_interactions(self):
        """Verify explicit trait interactions (strictness + skepticism evidence boost)."""
        policy_engine = BehavioralPolicyEngine(policy_mode="rule_based")
        persona = get_persona("CTO")
        client_state = ClientState(trust=0.50, skepticism=0.60, patience=0.60)
        interview_state = InterviewState(current_stage=InterviewStage.STAGE_2_PROBLEM_DISCOVERY)

        analysis = CandidateTurnAnalysis(
            response_quality=ResponseQualityAnalysis(unsupported_claim=True),
            sales_behavior=SalesBehaviorAnalysis(),
            technical_behavior=TechnicalBehaviorAnalysis(),
            business_understanding=BusinessUnderstandingAnalysis(),
            extracted_claims=[CandidateClaim(id="c3", claim="Our speed is 100x faster than legacy", topic="speed", is_quantitative=True, source_turn=2)],
        )

        # High strictness (>0.75) + High skepticism (>0.75)
        interactive_cfg = PersonaConfiguration(
            role="CTO",
            traits={"strictness": 0.90, "skepticism": 0.90, "kindness": 0.30},
        )

        dec = policy_engine.evaluate(
            persona=persona,
            client_state=client_state,
            interview_state=interview_state,
            candidate_analysis=analysis,
            turn=2,
            candidate_message="Our speed is 100x faster than legacy.",
            persona_config=interactive_cfg,
        )

        assert dec.policy_id == "unsupported_quantitative_claim"
        assert dec.primary_action.action_type in (ActionType.CHALLENGE_CLAIM, ActionType.REQUEST_EVIDENCE)
        assert "skepticism" in dec.trace.trait_influences
        assert dec.trace.trait_influences["skepticism"] > 0

    def test_10_client_state_initialization_with_traits(self):
        """Verify traits calibrate initial ClientState, and runtime state evolves independently."""
        # Low skepticism, high patience configuration
        calibrated_cfg = PersonaConfiguration(
            role="CTO",
            traits={"skepticism": 0.30, "patience": 0.90, "risk_aversion": 0.40, "kindness": 0.85},
        )

        persona = get_persona("CTO")
        initial_state = ClientStateManager.initialize_state(
            persona=persona,
            style="Professional",
            persona_config=calibrated_cfg,
        )

        # Skepticism must be lower than baseline CTO (0.75)
        assert initial_state.skepticism < 0.70
        # Patience must be higher than baseline CTO (0.70)
        assert initial_state.patience > 0.75
        # Perceived risk must be lower than baseline CTO (0.65)
        assert initial_state.perceived_risk < 0.65

        # Dynamic evolution does not alter configured traits
        delta = ClientStateManager.calculate_delta(
            current_state=initial_state,
            signal=InteractionSignal(type="positive_evidence", confidence=0.9, reason="Strong benchmarks provided"),
            persona=persona,
        )
        updated_state = initial_state.apply_delta(delta)
        assert updated_state.trust > initial_state.trust
        # Configured trait remains static
        assert calibrated_cfg.get_trait("skepticism") == 0.30

    def test_11_sqlite_configuration_persistence(self):
        """Verify resolved persona configuration is persisted in elevate.db and retrievable."""
        test_session_id = f"test_persist_{int(time.time())}"
        cfg = resolve_persona_configuration(
            role="CFO",
            preset="STRICT",
            custom_traits={"financial_scrutiny": 0.99, "cost_sensitivity": 0.95},
        )

        storage.save_persona_configuration(
            session_id=test_session_id,
            role=cfg.role,
            preset=cfg.preset,
            traits=cfg.traits,
            scenario_overrides=cfg.scenario_overrides,
            schema_version=cfg.persona_schema_version,
        )

        retrieved = storage.get_persona_configuration(test_session_id)
        assert retrieved is not None
        assert retrieved["session_id"] == test_session_id
        assert retrieved["role"] == "CFO"
        assert retrieved["preset"] == "STRICT"
        assert retrieved["traits"]["financial_scrutiny"] == 0.99
        assert retrieved["persona_schema_version"] == "1.0"

    def test_12_persona_schema_versioning(self):
        """Verify persona_schema_version is explicitly tracked."""
        cfg = PersonaConfiguration(role="CEO", persona_schema_version="1.0")
        assert cfg.persona_schema_version == "1.0"

    def test_13_api_configuration_schema_endpoint(self):
        """Verify GET /api/personas/configuration-schema/{role} returns valid schemas."""
        for role in ["CTO", "CFO", "SALES_MANAGER", "CEO", "HR"]:
            response = client.get(f"/api/personas/configuration-schema/{role}")
            assert response.status_code == 200
            data = response.json()
            assert data["role"] == role
            assert "traits" in data
            assert "presets" in data
            assert len(data["traits"]) > 0
            assert len(data["presets"]) > 0

    def test_14_api_session_creation_backward_compatibility(self):
        """Verify existing session requests without persona_configuration succeed with role defaults."""
        payload = {
            "topic": "Technical Interview",
            "role": "CTO",
            "scenario": "System Architecture Review",
            "experience": "Intermediate",
            "style": "Professional",
        }
        response = client.post("/api/session", json=payload)
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        # Stored configuration must use role defaults
        stored_config = storage.get_persona_configuration(session_id)
        assert stored_config is not None
        assert stored_config["role"] == "CTO"
        assert stored_config["traits"]["technical_depth"] == ROLE_SIMULATION_DEFAULTS["CTO"]["technical_depth"]

    def test_15_api_session_creation_with_persona_config(self):
        """Verify POST /api/session with explicit persona_configuration saves custom traits."""
        payload = {
            "topic": "Sales Conversation",
            "role": "CFO",
            "scenario": "Enterprise SaaS Pricing",
            "experience": "Advanced",
            "style": "Professional",
            "persona_configuration": {
                "role": "CFO",
                "preset": "STRICT",
                "traits": {
                    "financial_scrutiny": 0.98,
                    "cost_sensitivity": 0.92,
                    "kindness": 0.40,
                },
                "persona_schema_version": "1.0",
            },
        }
        response = client.post("/api/session", json=payload)
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        # Check debug endpoint
        debug_resp = client.get(f"/api/personas/debug/{session_id}")
        assert debug_resp.status_code == 200
        debug_data = debug_resp.json()
        assert debug_data["role"] == "CFO"
        assert debug_data["preset"] == "STRICT"
        assert debug_data["traits"]["financial_scrutiny"] == 0.98

    def test_16_policy_trace_inspectable_trait_influences(self):
        """Verify PolicyTrace records explicit numeric trait influences."""
        policy_engine = BehavioralPolicyEngine(policy_mode="rule_based")
        persona = get_persona("CTO")
        client_state = ClientState(skepticism=0.75, frustration=0.10)
        interview_state = InterviewState(current_stage=InterviewStage.STAGE_2_PROBLEM_DISCOVERY)

        analysis = CandidateTurnAnalysis(
            response_quality=ResponseQualityAnalysis(unsupported_claim=True),
            sales_behavior=SalesBehaviorAnalysis(),
            technical_behavior=TechnicalBehaviorAnalysis(),
            business_understanding=BusinessUnderstandingAnalysis(),
            extracted_claims=[CandidateClaim(id="c4", claim="Our throughput is 10M QPS", topic="throughput", is_quantitative=True, source_turn=1)],
        )

        cfg = PersonaConfiguration(
            role="CTO",
            traits={"skepticism": 0.85, "strictness": 0.90, "kindness": 0.30, "patience": 0.40},
        )

        decision = policy_engine.evaluate(
            persona=persona,
            client_state=client_state,
            interview_state=interview_state,
            candidate_analysis=analysis,
            turn=1,
            candidate_message="Our throughput is 10M QPS.",
            persona_config=cfg,
        )

        trace = decision.trace
        assert "skepticism" in trace.trait_influences
        assert "strictness" in trace.trait_influences
        assert trace.trait_influences["skepticism"] > 0
        assert trace.trait_influences["strictness"] > 0

    def test_17_research_experiment_rq7_controllability(self):
        """Verify RQ7 experiment evaluates trait controllability and behavioral monotonicity."""
        runner = EvaluationRunner()
        result = runner.run_experiment("RQ7")
        assert result["experiment_id"] == "RQ7"
        assert result["trait_tested"] == "skepticism"
        assert len(result["levels_tested"]) == 3
        assert result["role_identity_preserved"] is True
        assert "monotonicity_verified" in result

    def test_18_research_experiment_rq8_independence(self):
        """Verify RQ8 experiment validates trait independence and no persona collapse."""
        runner = EvaluationRunner()
        result = runner.run_experiment("RQ8")
        assert result["experiment_id"] == "RQ8"
        assert result["trait_tested"] == "kindness"
        assert result["dealbreakers_protected"] is True
        assert result["persona_collapse_avoided"] is True

    def test_19_research_experiment_rq9_coverage(self):
        """Verify RQ9 experiment evaluates multi-preset training coverage expansion."""
        runner = EvaluationRunner()
        result = runner.run_experiment("RQ9")
        assert result["experiment_id"] == "RQ9"
        assert len(result["presets_tested"]) >= 4
        assert "action_space_coverage_multiplier" in result

    def test_20_deterministic_performance_no_extra_llm_call(self):
        """Verify persona configuration resolution and summary execute in <1ms without LLM."""
        start = time.time()
        for _ in range(100):
            cfg = resolve_persona_configuration(
                "CTO",
                preset="STRICT",
                custom_traits={"technical_depth": 0.95, "skepticism": 0.88},
            )
            summary = generate_persona_summary(cfg)
        elapsed_ms = (time.time() - start) * 1000.0 / 100.0
        assert elapsed_ms < 1.0, f"Average execution took {elapsed_ms:.3f}ms (must be <1ms)"
        assert "CTO" in summary
