"""Unit tests for Phase 2: Typed Structured Persona & World Model.

Verifies:
1. PersonaProfile creation & non-empty validation
2. ValueOrientation simulation weight validation (0.0 - 1.0)
3. StakeholderGoal validation & dealbreaker logic
4. Incentive model validation & category checks
5. KnowledgeBoundary validation
6. CompanyContext creation & defaults
7. EnterprisePersona composition & duplicate detection
8. Loading CTO structured persona
9. Loading CEO structured persona
10. Loading HR structured persona
11. Loading SALES_MANAGER structured persona
12. Backward compatibility with existing role IDs
13. End-to-end session creation with structured persona & existing API contracts
14. PromptBuilder generation formatting
"""

import unittest
import os
from unittest.mock import patch, MagicMock
from pydantic import ValidationError

from app.models.persona import (
    PersonaProfile,
    ValueOrientation,
    StakeholderGoal,
    Incentive,
    KnowledgeBoundary,
    CompanyContext,
    EnterprisePersona,
)
from app.models.schemas import SessionRequest, SessionResponse
from app.roles.registry import get_persona, list_supported_roles
from app.services.prompt_builder import build_persona_system_prompt
from app.agents.prompts import get_interviewer_system_prompt


class TestPersonaModels(unittest.TestCase):

    def test_1_persona_profile_creation(self):
        """Test valid creation of PersonaProfile across diverse roles."""
        profile = PersonaProfile(
            role="CTO",
            title="Chief Technology Officer",
            department="Engineering",
            seniority="C-Suite",
            years_of_experience=18,
            industry_expertise=["Cloud", "Distributed Systems"],
            technical_depth="Deep Architectural",
            communication_style="Direct, concise",
            personality_characteristics=["Analytical", "Skeptical"],
            risk_profile="Calculated Risk-Taker",
        )
        self.assertEqual(profile.role, "CTO")
        self.assertEqual(profile.years_of_experience, 18)

        # Test validation: empty string should fail
        with self.assertRaises(ValidationError):
            PersonaProfile(
                role="",
                title="Title",
                department="Dept",
                seniority="Exec",
                years_of_experience=5,
                technical_depth="High",
                communication_style="Direct",
                risk_profile="Low",
            )

        # Test validation: negative experience years should fail
        with self.assertRaises(ValidationError):
            PersonaProfile(
                role="CFO",
                title="Chief Financial Officer",
                department="Finance",
                seniority="Executive",
                years_of_experience=-1,
                technical_depth="Low",
                communication_style="Direct",
                risk_profile="Conservative",
            )

    def test_2_value_orientation_validation(self):
        """Test ValueOrientation simulation weight boundaries and description."""
        val = ValueOrientation(
            name="security",
            weight=0.95,
            description="Strong preference for reducing security vulnerabilities",
            priority=1,
        )
        self.assertEqual(val.name, "security")
        self.assertAlmostEqual(val.weight, 0.95)

        # Weight > 1.0 must fail
        with self.assertRaises(ValidationError):
            ValueOrientation(name="cost", weight=1.5, description="High cost focus", priority=1)

        # Weight < 0.0 must fail
        with self.assertRaises(ValidationError):
            ValueOrientation(name="cost", weight=-0.2, description="Negative weight", priority=1)

        # Empty name must fail
        with self.assertRaises(ValidationError):
            ValueOrientation(name="", weight=0.5, description="No name", priority=1)

    def test_3_stakeholder_goal_validation(self):
        """Test StakeholderGoal model validation and type checking."""
        goal = StakeholderGoal(
            id="technical_feasibility",
            description="Determine whether the proposed solution can integrate safely",
            priority=0.9,
            type="technical",
            success_condition="Technical integration risks are sufficiently addressed",
            dealbreaker=True,
            required_information=["Architecture diagrams"],
        )
        self.assertEqual(goal.id, "technical_feasibility")
        self.assertTrue(goal.dealbreaker)
        self.assertEqual(goal.type, "technical")

        # Invalid type must fail
        with self.assertRaises(ValidationError):
            StakeholderGoal(
                id="goal_1",
                description="Invalid type goal",
                priority=0.5,
                type="invalid_type",  # type: ignore[arg-type]
                success_condition="Should fail",
            )

        # Priority > 1.0 must fail
        with self.assertRaises(ValidationError):
            StakeholderGoal(
                id="goal_2",
                description="Invalid priority goal",
                priority=1.2,
                type="business",
                success_condition="Should fail",
            )

    def test_4_incentive_validation(self):
        """Test Incentive model validation and categories."""
        inc = Incentive(
            id="protect_uptime",
            description="Prevent outages that harm customer trust",
            importance=0.95,
            category="organizational",
        )
        self.assertEqual(inc.id, "protect_uptime")
        self.assertEqual(inc.category, "organizational")

        # Invalid category must fail
        with self.assertRaises(ValidationError):
            Incentive(
                id="inc_bad",
                description="Bad category",
                importance=0.5,
                category="random_category",  # type: ignore[arg-type]
            )

        # Importance < 0.0 must fail
        with self.assertRaises(ValidationError):
            Incentive(
                id="inc_bad2",
                description="Negative importance",
                importance=-0.1,
                category="personal",
            )

    def test_5_knowledge_boundary_validation(self):
        """Test KnowledgeBoundary model."""
        kb = KnowledgeBoundary(
            expert_topics=["Kubernetes", "Distributed Systems"],
            known_topics=["SOC2 Compliance"],
            limited_topics=["Marketing Funnels"],
            unknown_topics=["Competitor Internal Margins"],
            confidential_topics=["Internal Unpatched CVEs"],
            disclosure_rules=["Do not share exact vulnerability findings."],
        )
        self.assertIn("Kubernetes", kb.expert_topics)
        self.assertIn("SOC2 Compliance", kb.known_topics)
        self.assertIn("Internal Unpatched CVEs", kb.confidential_topics)

    def test_6_company_context_creation(self):
        """Test CompanyContext / WorldModel creation and optional fields."""
        ctx = CompanyContext(
            industry="FinTech",
            company_size="5,000 employees",
            company_stage="Public Enterprise",
            current_technology_stack=["Azure", "PostgreSQL", "Kubernetes"],
            incumbent_vendors=["VendorA"],
            pain_points=["High infrastructure cost", "Slow deployment"],
            constraints=["Must comply with PCI-DSS"],
            budget_constraints="Moderate",
            timeline="90 days",
        )
        self.assertEqual(ctx.industry, "FinTech")
        self.assertEqual(len(ctx.current_technology_stack), 3)
        self.assertEqual(ctx.budget_constraints, "Moderate")

    def test_7_enterprise_persona_composition(self):
        """Test EnterprisePersona composition and duplicate detection."""
        profile = PersonaProfile(
            role="VP_ENG",
            title="VP of Engineering",
            department="Engineering",
            seniority="Executive",
            years_of_experience=15,
            technical_depth="Deep",
            communication_style="Pragmatic",
            risk_profile="Moderate",
        )
        val1 = ValueOrientation(name="reliability", weight=0.9, description="Reliability", priority=1)
        val2 = ValueOrientation(name="cost", weight=0.7, description="Cost", priority=2)
        goal1 = StakeholderGoal(id="g1", description="G1", priority=0.8, type="business", success_condition="OK")
        inc1 = Incentive(id="inc1", description="Inc1", importance=0.8, category="organizational")

        persona = EnterprisePersona(
            profile=profile,
            values=[val1, val2],
            goals=[goal1],
            incentives=[inc1],
            knowledge_boundary=KnowledgeBoundary(),
            world_model=None,
        )
        self.assertEqual(persona.profile.role, "VP_ENG")
        self.assertEqual(len(persona.values), 2)

        # Duplicate value name rejection
        val_dup = ValueOrientation(name="reliability", weight=0.8, description="Duplicate name", priority=3)
        with self.assertRaises(ValidationError):
            EnterprisePersona(
                profile=profile,
                values=[val1, val_dup],
                goals=[goal1],
                incentives=[inc1],
            )

        # Duplicate goal ID rejection
        goal_dup = StakeholderGoal(id="g1", description="Duplicate ID", priority=0.5, type="technical", success_condition="OK")
        with self.assertRaises(ValidationError):
            EnterprisePersona(
                profile=profile,
                values=[val1],
                goals=[goal1, goal_dup],
                incentives=[inc1],
            )

        # Duplicate incentive ID rejection
        inc_dup = Incentive(id="inc1", description="Duplicate Inc", importance=0.5, category="personal")
        with self.assertRaises(ValidationError):
            EnterprisePersona(
                profile=profile,
                values=[val1],
                goals=[goal1],
                incentives=[inc1, inc_dup],
            )

    def test_8_load_cto_persona(self):
        """Test loading structured CTO persona from registry."""
        persona = get_persona("CTO")
        self.assertEqual(persona.profile.role, "CTO")
        self.assertEqual(persona.profile.title, "Chief Technology Officer")
        self.assertEqual(persona.profile.technical_depth, "Deep Architectural")
        self.assertTrue(any(v.name == "reliability" for v in persona.values))
        self.assertTrue(any(g.id == "verify_architectural_fit" for g in persona.goals))
        assert persona.world_model is not None
        self.assertIn("Kubernetes", persona.world_model.current_technology_stack)

    def test_9_load_ceo_persona(self):
        """Test loading structured CEO persona from registry."""
        persona = get_persona("CEO")
        self.assertEqual(persona.profile.role, "CEO")
        self.assertEqual(persona.profile.title, "Chief Executive Officer")
        self.assertTrue(any(v.name == "revenue" for v in persona.values))
        self.assertTrue(any(g.id == "evaluate_business_roi" for g in persona.goals))

    def test_10_load_hr_persona(self):
        """Test loading structured HR persona from registry."""
        persona = get_persona("HR")
        self.assertEqual(persona.profile.role, "HR")
        self.assertEqual(persona.profile.technical_depth, "Non-Technical")
        self.assertTrue(any(v.name == "culture fit" for v in persona.values))
        self.assertTrue(any(g.id == "evaluate_behavioral_competencies" for g in persona.goals))

    def test_11_load_sales_manager_persona(self):
        """Test loading structured SALES_MANAGER persona from registry."""
        persona = get_persona("SALES_MANAGER")
        self.assertEqual(persona.profile.role, "SALES_MANAGER")
        self.assertTrue(any(v.name == "revenue" for v in persona.values))
        self.assertTrue(any(g.id == "evaluate_value_articulation" for g in persona.goals))

    def test_12_backward_compatibility_role_ids(self):
        """Test that role IDs in lowercase or with hyphens resolve gracefully."""
        persona_cto_lower = get_persona("cto")
        self.assertEqual(persona_cto_lower.profile.role, "CTO")

        persona_sales_hyphen = get_persona("sales-manager")
        self.assertEqual(persona_sales_hyphen.profile.role, "SALES_MANAGER")

        # Unknown role should fall back to resilient generic persona rather than raising error
        persona_custom = get_persona("UnknownCustomRole")
        self.assertEqual(persona_custom.profile.role, "UnknownCustomRole")
        self.assertIsNotNone(persona_custom.world_model)

    def test_13_prompt_builder_integration(self):
        """Test prompt builder renders structured sections cleanly."""
        cto = get_persona("CTO")
        prompt = build_persona_system_prompt(
            persona=cto,
            topic="Technical Interview",
            scenario="Evaluating candidate on distributed microservices architecture",
            experience="Senior",
            style="Challenging",
        )
        self.assertIn("PERSONA PROFILE", prompt)
        self.assertIn("Chief Technology Officer", prompt)
        self.assertIn("CORE VALUES & PRIORITIES", prompt)
        self.assertIn("STAKEHOLDER EVALUATION GOALS", prompt)
        self.assertIn("KNOWLEDGE BOUNDARIES", prompt)
        self.assertIn("INDUSTRY & OPERATING ENVIRONMENT", prompt)
        self.assertIn("Technical Interview", prompt)
        self.assertIn("[END_INTERVIEW]", prompt)

        # Verify get_interviewer_system_prompt delegates cleanly
        prompt_delegated = get_interviewer_system_prompt(
            persona_or_context=cto,
            topic="Technical Interview",
            scenario="Evaluating candidate on distributed microservices architecture",
            experience="Senior",
            style="Challenging",
        )
        self.assertEqual(prompt, prompt_delegated)

    def test_14_legacy_prompt_fallback(self):
        """Test that get_interviewer_system_prompt still supports legacy string input."""
        legacy_context = "Role: You are a legacy CTO acting professionally."
        prompt = get_interviewer_system_prompt(
            persona_or_context=legacy_context,
            topic="Tech",
            scenario="Scenario",
            experience="Intermediate",
            style="Professional",
        )
        self.assertIn("Role: You are a legacy CTO acting professionally.", prompt)
        self.assertIn("[END_INTERVIEW]", prompt)

    @patch("app.agents.role_agent.get_llm")
    def test_15_session_creation_with_role_agent(self, mock_get_llm):
        """Verify RoleAgent initializes with structured persona using standard SessionRequest contract."""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        from app.agents.role_agent import RoleAgent

        agent = RoleAgent(
            role_id="CTO",
            topic="Technical Interview",
            scenario="Architecture evaluation",
            experience="Expert",
            style="Executive",
            session_id="test-session-123",
        )

        self.assertIsNotNone(agent.persona)
        self.assertEqual(agent.persona.profile.role, "CTO")
        self.assertIsNotNone(agent.graph)
        self.assertEqual(agent.role_id, "CTO")

    @patch("app.agents.role_agent.get_llm")
    def test_16_api_endpoints_backward_compatibility(self, mock_get_llm):
        """Test that FastAPI endpoints work seamlessly with structured persona."""
        mock_get_llm.return_value = MagicMock()
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)

        # GET /api/topics
        res_topics = client.get("/api/topics")
        self.assertEqual(res_topics.status_code, 200)
        self.assertEqual(len(res_topics.json()), 8)

        # GET /api/roles
        res_roles = client.get("/api/roles")
        self.assertEqual(res_roles.status_code, 200)
        self.assertEqual(len(res_roles.json()), 4)

        # POST /api/session
        res_session = client.post(
            "/api/session",
            json={
                "topic": "Technical Interview",
                "role": "CTO",
                "scenario": "Cloud migration and database scaling evaluation",
                "experience": "Intermediate",
                "style": "Professional",
            },
        )
        self.assertEqual(res_session.status_code, 200)
        session_data = res_session.json()
        self.assertIn("session_id", session_data)


if __name__ == "__main__":
    unittest.main()

