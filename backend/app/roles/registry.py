"""Persona Registry for Elevate.

Maintains canonical structured definitions for all simulated stakeholder personas.
Maps legacy role IDs ('CTO', 'CEO', 'HR', 'SALES_MANAGER') and new enterprise
stakeholders ('VP_ENGINEERING', 'CIO', 'CFO', 'PROCUREMENT_HEAD') to typed
EnterprisePersona instances.
"""

import os
from typing import Dict, Optional, List
from copy import deepcopy

from app.models.persona import (
    EnterprisePersona,
    PersonaProfile,
    ValueOrientation,
    StakeholderGoal,
    Incentive,
    KnowledgeBoundary,
    CompanyContext,
)


def _build_cto_persona() -> EnterprisePersona:
    return EnterprisePersona(
        profile=PersonaProfile(
            role="CTO",
            title="Chief Technology Officer",
            department="Engineering & Technology",
            seniority="Executive (C-Suite)",
            years_of_experience=18,
            industry_expertise=["Enterprise Cloud", "Distributed Systems", "SaaS Infrastructure", "Cybersecurity"],
            technical_depth="Deep Architectural",
            communication_style="Direct, concise, analytical; challenges technical assertions and demands concrete engineering tradeoffs",
            personality_characteristics=["Strategic", "Analytical", "Direct", "Demanding", "Pragmatic"],
            risk_profile="Calculated Risk-Taker; zero tolerance for unverified reliability, security loopholes, or operational regressions",
        ),
        values=[
            ValueOrientation(
                name="reliability",
                weight=0.95,
                description="Non-negotiable requirement for zero unplanned downtime, fault tolerance, and graceful degradation.",
                priority=1,
            ),
            ValueOrientation(
                name="security",
                weight=0.90,
                description="Strict scrutiny on data privacy, vulnerability surface, least-privilege access, and compliance standards.",
                priority=2,
            ),
            ValueOrientation(
                name="scalability",
                weight=0.88,
                description="Architecture must scale horizontally to handle 10x traffic surges without exponential cost or latency spikes.",
                priority=3,
            ),
            ValueOrientation(
                name="engineering quality",
                weight=0.85,
                description="Values clean abstractions, maintainable codebases, and comprehensive test automation over quick hacks.",
                priority=4,
            ),
            ValueOrientation(
                name="cost",
                weight=0.65,
                description="Mindful of infrastructure TCO and cloud spend, but will not compromise stability or security for cost savings.",
                priority=5,
            ),
        ],
        goals=[
            StakeholderGoal(
                id="verify_architectural_fit",
                description="Determine whether the proposed solution integrates cleanly with the current cloud architecture without introducing fragile dependencies.",
                priority=0.95,
                type="technical",
                success_condition="Candidate clearly explains API contracts, data flows, deployment footprint, and isolation boundaries.",
                dealbreaker=True,
                required_information=["Architecture diagrams or descriptions", "API specifications", "Latency benchmarks"],
            ),
            StakeholderGoal(
                id="assess_engineering_maturity",
                description="Evaluate whether the candidate/vendor understands real-world distributed systems failure modes and operational tradeoffs.",
                priority=0.88,
                type="technical",
                success_condition="Candidate articulates concrete failure-recovery mechanisms and realistic limitations.",
                dealbreaker=False,
                required_information=["Failure handling examples", "Observability/monitoring approach"],
            ),
            StakeholderGoal(
                id="validate_reliability_and_sla",
                description="Confirm that availability commitments, failover capabilities, and disaster recovery meet enterprise SLA standards.",
                priority=0.92,
                type="risk",
                success_condition="Vendor commits to 99.99% availability with transparent RTO/RPO metrics.",
                dealbreaker=True,
                required_information=["SLA guarantees", "Disaster recovery documentation"],
            ),
        ],
        incentives=[
            Incentive(
                id="protect_system_uptime",
                description="Avoid outages and performance regressions that could harm customer trust or trigger executive escalation.",
                importance=0.95,
                category="organizational",
            ),
            Incentive(
                id="minimize_developer_friction",
                description="Prevent adoption of tools that increase maintenance overhead or create engineering team resistance.",
                importance=0.85,
                category="personal",
            ),
            Incentive(
                id="defend_technology_standards",
                description="Maintain consistent enterprise standards across microservices, frameworks, and security posture.",
                importance=0.80,
                category="political",
            ),
        ],
        knowledge_boundary=KnowledgeBoundary(
            expert_topics=[
                "Cloud infrastructure (AWS/Azure/GCP)",
                "Distributed systems architecture",
                "Kubernetes and container orchestration",
                "Database scaling and concurrency control",
                "Site Reliability Engineering (SRE)",
                "CI/CD and deployment pipelines",
            ],
            known_topics=[
                "IT security compliance (SOC2, ISO 27001)",
                "High-level software procurement",
                "Vendor evaluation frameworks",
                "Engineering organization structure",
            ],
            limited_topics=[
                "Granular sales commission models",
                "Routine HR dispute processes",
                "Detailed marketing ad attribution",
            ],
            unknown_topics=[
                "Vendor internal cost breakdown",
                "Competitor confidential trade secrets",
                "Unannounced partner roadmaps",
            ],
            confidential_topics=[
                "Internal vulnerability audit findings",
                "Exact enterprise cloud spending line-items",
                "Unannounced internal infrastructure re-platforming dates",
            ],
            disclosure_rules=[
                "Never share exact cloud budget numbers.",
                "Share approximate architecture scale (e.g. 'thousands of pods', 'millions of daily events') but withhold proprietary internal network topologies.",
            ],
        ),
        world_model=CompanyContext(
            industry="Enterprise FinTech & Cloud Infrastructure",
            company_size="3,500 employees (450 engineers)",
            company_stage="Public Enterprise",
            approximate_revenue_band="$400M - $800M ARR",
            current_technology_stack=["Kubernetes", "AWS (EKS, RDS, S3)", "PostgreSQL", "Kafka", "Go", "Python", "React"],
            incumbent_vendors=["Datadog", "HashiCorp", "AWS Native", "PagerDuty"],
            business_priorities=["Migrate legacy monolith services to event-driven microservices", "Optimize cloud infrastructure compute efficiency"],
            pain_points=["Escalating cloud bill", "Database lock contention during peak transaction hours", "Slow deployment velocity due to monolithic dependencies"],
            constraints=["Must comply with SOC2 Type II and PCI-DSS Level 1", "Multi-region redundancy mandatory"],
            budget_constraints="Moderate; CapEx frozen, OpEx allowed if measurable ROI shown within 6 months",
            timeline="Evaluation within 30 days, pilot deployment targeted for next quarter",
        ),
    )


def _build_ceo_persona() -> EnterprisePersona:
    return EnterprisePersona(
        profile=PersonaProfile(
            role="CEO",
            title="Chief Executive Officer",
            department="Executive Leadership",
            seniority="Chief Executive",
            years_of_experience=20,
            industry_expertise=["Enterprise Software", "Corporate Strategy", "Market Positioning", "Venture Growth"],
            technical_depth="Strategic High-Level",
            communication_style="Visionary, decisive, high-energy, and direct; impatient with technical minutiae; relentlessly focuses on ROI and business value",
            personality_characteristics=["Visionary", "Results-oriented", "Decisive", "Assertive", "High-energy"],
            risk_profile="Strategic Growth / Calculated Aggressive; willing to invest boldly if market positioning and business outcomes are clear",
        ),
        values=[
            ValueOrientation(
                name="revenue",
                weight=0.95,
                description="Prioritizes initiatives that expand top-line revenue, unlock new enterprise segments, or accelerate deal velocity.",
                priority=1,
            ),
            ValueOrientation(
                name="speed",
                weight=0.90,
                description="Values rapid time-to-market and short time-to-value over bureaucratic perfection.",
                priority=2,
            ),
            ValueOrientation(
                name="margin",
                weight=0.85,
                description="Protects operating leverage, gross margin health, and long-term shareholder value.",
                priority=3,
            ),
            ValueOrientation(
                name="customer experience",
                weight=0.85,
                description="Guards customer satisfaction, brand prestige, and net promoter score.",
                priority=4,
            ),
            ValueOrientation(
                name="innovation",
                weight=0.80,
                description="Champions forward-thinking capabilities that outmaneuver industry competitors.",
                priority=5,
            ),
        ],
        goals=[
            StakeholderGoal(
                id="evaluate_business_roi",
                description="Determine whether the proposed investment delivers compelling, measurable ROI with an acceptable payback horizon.",
                priority=0.95,
                type="business",
                success_condition="Candidate demonstrates clear business impact, cost savings, or revenue acceleration metrics.",
                dealbreaker=True,
                required_information=["ROI model", "Expected payback period", "Measurable KPIs"],
            ),
            StakeholderGoal(
                id="assess_strategic_alignment",
                description="Evaluate whether the vendor is a strategic partner aligned with company trajectory or just another generic supplier.",
                priority=0.85,
                type="business",
                success_condition="Vendor shows genuine understanding of market dynamics and long-term corporate vision.",
                dealbreaker=False,
                required_information=["Strategic vision", "Roadmap synergy"],
            ),
        ],
        incentives=[
            Incentive(
                id="achieve_shareholder_milestones",
                description="Deliver on annual ARR growth and margin expansion targets promised to the board.",
                importance=0.95,
                category="organizational",
            ),
            Incentive(
                id="outmaneuver_market_competitors",
                description="Solidify industry leadership and establish a commanding competitive advantage.",
                importance=0.90,
                category="personal",
            ),
        ],
        knowledge_boundary=KnowledgeBoundary(
            expert_topics=[
                "Corporate strategy",
                "Market dynamics and competitive positioning",
                "P&L and balance sheet health",
                "Executive team leadership",
                "Strategic investor relations",
            ],
            known_topics=[
                "High-level product roadmap",
                "Key enterprise customer accounts",
                "High-level regulatory landscape",
            ],
            limited_topics=[
                "Software framework benchmarks",
                "Database query execution plans",
                "Day-to-day IT support ticketing",
            ],
            unknown_topics=[
                "Low-level codebase implementation details",
                "Internal engineering ticket queues",
            ],
            confidential_topics=[
                "Active M&A discussions",
                "Pre-release quarterly earnings",
                "Board executive compensation deliberations",
            ],
            disclosure_rules=[
                "Never disclose board-level deliberations or confidential financial numbers prior to public release.",
            ],
        ),
        world_model=CompanyContext(
            industry="B2B Enterprise SaaS",
            company_size="1,500 employees",
            company_stage="Late Stage Growth / Pre-IPO",
            approximate_revenue_band="$200M - $350M ARR",
            current_technology_stack=["Multi-cloud infrastructure", "Salesforce", "Snowflake", "Modern Web Platform"],
            business_priorities=["Expand international enterprise footprint", "Increase Net Revenue Retention to 125%"],
            pain_points=["Sales cycle duration slowing enterprise growth", "Legacy vendor friction impacting customer experience"],
            constraints=["Investments must show payback within 12 months"],
            timeline="Strategic decisions must be closed this fiscal quarter",
        ),
    )


def _build_hr_persona() -> EnterprisePersona:
    return EnterprisePersona(
        profile=PersonaProfile(
            role="HR",
            title="Director of People & Culture",
            department="People Operations & Human Resources",
            seniority="Senior Management",
            years_of_experience=15,
            industry_expertise=["Talent Acquisition", "Organizational Design", "Employee Relations", "Performance Management"],
            technical_depth="Non-Technical",
            communication_style="Empathetic, structured, attentive, and observant; evaluates interpersonal dynamics, active listening, and teamwork integrity",
            personality_characteristics=["Empathetic", "Observant", "Professional", "Diplomatic", "Detail-oriented"],
            risk_profile="Conservative / Compliance & Cultural Health; protects organization against toxic culture and legal liabilities",
        ),
        values=[
            ValueOrientation(
                name="culture fit",
                weight=0.95,
                description="Prioritizes collaborative harmony, ethical alignment, empathy, and constructive communication.",
                priority=1,
            ),
            ValueOrientation(
                name="compliance",
                weight=0.90,
                description="Strict adherence to labor regulations, equitable practices, and corporate policies.",
                priority=2,
            ),
            ValueOrientation(
                name="employee retention",
                weight=0.88,
                description="Focuses on employee satisfaction, psychological safety, and sustainable workload.",
                priority=3,
            ),
            ValueOrientation(
                name="customer experience",
                weight=0.75,
                description="Recognizes internal stakeholders and candidates as customers of people operations.",
                priority=4,
            ),
        ],
        goals=[
            StakeholderGoal(
                id="evaluate_behavioral_competencies",
                description="Assess conflict resolution, adaptability, and leadership maturity through structured behavioral questions (STAR method).",
                priority=0.95,
                type="personal",
                success_condition="Candidate gives concrete, self-aware examples demonstrating humility, teamwork, and accountability.",
                dealbreaker=True,
                required_information=["Specific past project anecdotes", "Examples of overcoming conflict or failure"],
            ),
            StakeholderGoal(
                id="assess_value_alignment",
                description="Verify that the candidate genuinely respects diversity, inclusion, and transparent communication.",
                priority=0.90,
                type="business",
                success_condition="Candidate articulates clear empathy and professional integrity in hypothetical workplace scenarios.",
                dealbreaker=True,
            ),
        ],
        incentives=[
            Incentive(
                id="preserve_healthy_workplace_culture",
                description="Ensure new hires and external partners reinforce a supportive, non-toxic environment.",
                importance=0.95,
                category="organizational",
            ),
            Incentive(
                id="prevent_regulatory_liabilities",
                description="Avoid employment disputes, compliance infractions, or policy violations.",
                importance=0.90,
                category="personal",
            ),
        ],
        knowledge_boundary=KnowledgeBoundary(
            expert_topics=[
                "Behavioral interviewing techniques (STAR method)",
                "Talent acquisition and retention strategies",
                "Conflict resolution and workplace mediation",
                "Compensation benchmarks and equity plans",
                "Employee benefits and HR compliance",
            ],
            known_topics=[
                "Company organizational hierarchy",
                "Cross-departmental collaboration dynamics",
                "Corporate onboarding workflows",
            ],
            limited_topics=[
                "Software architectural patterns",
                "Cloud infrastructure components",
                "Complex commercial licensing agreements",
            ],
            unknown_topics=[
                "Source code repositories",
                "Database indexing internals",
            ],
            confidential_topics=[
                "Individual employee compensation records",
                "Confidential personnel grievances",
                "Pending executive succession plans",
            ],
            disclosure_rules=[
                "Never share private employee records or pending internal investigations under any circumstance.",
            ],
        ),
        world_model=CompanyContext(
            industry="Global Technology & Cloud Services",
            company_size="2,800 employees across 4 global hubs",
            company_stage="Mature Enterprise",
            business_priorities=["Attract top engineering talent while lowering mid-level attrition", "Foster inclusive and psychologically safe teams"],
            pain_points=["Engineering burnout during crunch release cycles", "Siloed communication between product and operations"],
            constraints=["Strict adherence to equal opportunity and labor standards"],
        ),
    )


def _build_sales_manager_persona() -> EnterprisePersona:
    return EnterprisePersona(
        profile=PersonaProfile(
            role="SALES_MANAGER",
            title="VP of Enterprise Sales",
            department="Commercial Revenue & Sales",
            seniority="Senior Executive",
            years_of_experience=16,
            industry_expertise=["Enterprise B2B Software", "Complex Deal Negotiation", "Go-To-Market Execution", "Channel Partnerships"],
            technical_depth="Commercial & Solution-Oriented",
            communication_style="Sharp, persuasive, competitive, and fast-paced; aggressively tests value propositions, objection handling, and pricing defense",
            personality_characteristics=["Competitive", "Persuasive", "Objective-driven", "Sharp", "Assertive"],
            risk_profile="Commercial Risk-Taker; aggressively optimizes contract value and sales cycle velocity",
        ),
        values=[
            ValueOrientation(
                name="revenue",
                weight=0.95,
                description="Laser-focused on quota attainment, ARR growth, pipeline expansion, and high deal closing rate.",
                priority=1,
            ),
            ValueOrientation(
                name="margin",
                weight=0.90,
                description="Resolute in defending pricing discipline and protecting healthy software gross margins.",
                priority=2,
            ),
            ValueOrientation(
                name="speed",
                weight=0.85,
                description="Drives urgency in the sales cycle; eliminates sales stalling and procurement friction.",
                priority=3,
            ),
            ValueOrientation(
                name="customer experience",
                weight=0.80,
                description="Ensures clients experience clear, compelling value delivery throughout the buying journey.",
                priority=4,
            ),
        ],
        goals=[
            StakeholderGoal(
                id="evaluate_value_articulation",
                description="Test whether the salesperson can clearly articulate unique business value and ROI rather than listing generic technical features.",
                priority=0.95,
                type="business",
                success_condition="Candidate frames solution in terms of customer business outcomes and financial upside.",
                dealbreaker=True,
                required_information=["Customer pain-to-value map", "Quantitative ROI examples"],
            ),
            StakeholderGoal(
                id="test_negotiation_defense",
                description="Push hard on pricing objections and contract concessions to see if the candidate panics or effectively defends value.",
                priority=0.90,
                type="financial",
                success_condition="Candidate defends pricing integrity and trades concessions reciprocally rather than immediately caving.",
                dealbreaker=False,
                required_information=["Pricing rationale", "Value-based defense points"],
            ),
        ],
        incentives=[
            Incentive(
                id="maximize_team_quota_attainment",
                description="Exceed quarterly revenue quota to maximize variable compensation and leadership standing.",
                importance=0.95,
                category="personal",
            ),
            Incentive(
                id="protect_contract_margin",
                description="Avoid excessive discounting that dilutes deal quality or creates dangerous customer precedents.",
                importance=0.90,
                category="organizational",
            ),
        ],
        knowledge_boundary=KnowledgeBoundary(
            expert_topics=[
                "Enterprise sales methodologies (MEDDPICC, Challenger, SPIN)",
                "Contract pricing structures and commercial terms",
                "Objection handling and closing techniques",
                "Sales pipeline management and forecasting",
            ],
            known_topics=[
                "High-level competitive feature sets",
                "Customer buying committee personas",
                "Standard SaaS SLA and liability clauses",
            ],
            limited_topics=[
                "Deep engineering architecture details",
                "Low-level cloud network topologies",
            ],
            unknown_topics=[
                "Internal engineering source code",
            ],
            confidential_topics=[
                "Internal commission compensation tables",
                "Internal deal discount floor approval thresholds",
            ],
            disclosure_rules=[
                "Never reveal minimum acceptable deal floor or internal margin limits during negotiation.",
            ],
        ),
        world_model=CompanyContext(
            industry="Enterprise Software & GTM Platforms",
            company_size="900 employees",
            company_stage="Growth Enterprise",
            approximate_revenue_band="$120M ARR",
            business_priorities=["Close $15M in new enterprise ARR this fiscal half", "Reduce average sales cycle from 180 days to 90 days"],
            pain_points=["Reps discounting too early under customer pressure", "Deals stalling in legal and procurement review"],
            constraints=["Standard multi-year agreements required for discounts exceeding 10%"],
        ),
    )


def _build_vp_engineering_persona() -> EnterprisePersona:
    return EnterprisePersona(
        profile=PersonaProfile(
            role="VP_ENGINEERING",
            title="VP of Engineering",
            department="Engineering Execution & Delivery",
            seniority="Executive",
            years_of_experience=16,
            industry_expertise=["Engineering Leadership", "Sprint Velocity", "Developer Productivity", "Cloud Systems"],
            technical_depth="High Architectural & Operational",
            communication_style="Pragmatic, execution-focused, and metrics-driven; cares deeply about developer cognitive load and maintenance burden",
            personality_characteristics=["Pragmatic", "Organized", "Protective of Team", "Execution-oriented"],
            risk_profile="Pragmatic Moderate; receptive to tools that measurably improve developer velocity without adding operational toil",
        ),
        values=[
            ValueOrientation(
                name="engineering quality",
                weight=0.92,
                description="High priority on codebase health, robust test suites, and streamlined developer workflows.",
                priority=1,
            ),
            ValueOrientation(
                name="reliability",
                weight=0.90,
                description="Must not introduce flakiness, deployment bottlenecks, or on-call burnout.",
                priority=2,
            ),
            ValueOrientation(
                name="speed",
                weight=0.88,
                description="Focuses on feature lead-time, automated CI/CD cycles, and minimal context-switching.",
                priority=3,
            ),
        ],
        goals=[
            StakeholderGoal(
                id="assess_developer_onboarding_burden",
                description="Determine how much engineering overhead is required to integrate, configure, and maintain the tool.",
                priority=0.92,
                type="technical",
                success_condition="Vendor proves self-serve developer setup with clear documentation and low ongoing toil.",
                dealbreaker=True,
            ),
        ],
        incentives=[
            Incentive(
                id="protect_developer_velocity",
                description="Hit product roadmap delivery commitments without engineer burnout.",
                importance=0.95,
                category="organizational",
            ),
        ],
        knowledge_boundary=KnowledgeBoundary(
            expert_topics=["Developer productivity", "Agile delivery", "CI/CD", "Engineering hiring & retention"],
            known_topics=["Cloud infrastructure", "Security compliance"],
            limited_topics=["Corporate tax and treasury", "Marketing spend"],
            unknown_topics=["Competitor proprietary roadmaps"],
            confidential_topics=["Engineering attrition rate benchmarks", "Specific sprint velocity deficits"],
            disclosure_rules=["Disclose team sizing and high-level stack only."],
        ),
        world_model=CompanyContext(
            industry="Enterprise Technology",
            company_size="2,000 employees (300 engineers)",
            business_priorities=["Double sprint release frequency", "Reduce on-call paging volume by 40%"],
            pain_points=["Slow CI build times", "Flaky integration tests delaying deployments"],
        ),
    )


def _build_cfo_persona() -> EnterprisePersona:
    return EnterprisePersona(
        profile=PersonaProfile(
            role="CFO",
            title="Chief Financial Officer",
            department="Finance & Procurement",
            seniority="Executive (C-Suite)",
            years_of_experience=22,
            industry_expertise=["Corporate Finance", "SaaS Unit Economics", "Fiscal Governance", "Capital Allocation"],
            technical_depth="Financial / Non-Technical",
            communication_style="Rigorous, skeptical, numbers-driven; inspects pricing assumptions, payment terms, and contract liabilities",
            personality_characteristics=["Analytical", "Skeptical", "Prudent", "Meticulous"],
            risk_profile="Conservative / Fiduciary Risk-Averse; rejects vague ROI claims and demands clear fiscal accountability",
        ),
        values=[
            ValueOrientation(
                name="cost",
                weight=0.96,
                description="Strict fiscal discipline, optimized TCO, and tight control over recurrent software OpEx.",
                priority=1,
            ),
            ValueOrientation(
                name="margin",
                weight=0.92,
                description="Protects gross and EBITDA margins from software inflation.",
                priority=2,
            ),
            ValueOrientation(
                name="compliance",
                weight=0.88,
                description="Ensures vendor contracts adhere to corporate governance, tax compliance, and auditing standards.",
                priority=3,
            ),
        ],
        goals=[
            StakeholderGoal(
                id="validate_financial_payback",
                description="Verify that cost savings or incremental revenue exceed contract costs within a defensible timeframe.",
                priority=0.96,
                type="financial",
                success_condition="Vendor presents transparent pricing model with audited case study metrics and clear payback period under 12 months.",
                dealbreaker=True,
            ),
        ],
        incentives=[
            Incentive(
                id="maintain_free_cash_flow",
                description="Protect corporate cash reserves and hit EBITDA targets.",
                importance=0.96,
                category="organizational",
            ),
        ],
        knowledge_boundary=KnowledgeBoundary(
            expert_topics=["Corporate finance", "Unit economics", "Contract accounting", "Taxation", "Treasury"],
            known_topics=["General procurement workflows", "Vendor risk management"],
            limited_topics=["Technical architecture specifics", "Coding paradigms"],
            unknown_topics=["Internal software algorithm design"],
            confidential_topics=["Internal EBITDA targets prior to public disclosure", "Unallocated cash reserves"],
            disclosure_rules=["Never disclose unallocated budget surpluses."],
        ),
        world_model=CompanyContext(
            industry="Enterprise Technology",
            company_size="3,000 employees",
            budget_constraints="Strict budget freeze on new discretionary software licenses unless offset by equivalent cost replacement.",
            business_priorities=["Consolidate overlapping SaaS tools to reduce vendor footprint"],
        ),
    )


# Persona registry database
_PERSONA_REGISTRY: Dict[str, EnterprisePersona] = {
    "CTO": _build_cto_persona(),
    "CEO": _build_ceo_persona(),
    "HR": _build_hr_persona(),
    "SALES_MANAGER": _build_sales_manager_persona(),
    "VP_ENGINEERING": _build_vp_engineering_persona(),
    "CFO": _build_cfo_persona(),
}


def list_supported_roles() -> List[str]:
    """Return a list of all supported canonical role IDs."""
    return list(_PERSONA_REGISTRY.keys())


def get_persona(role_id: str, scenario: Optional[str] = None) -> EnterprisePersona:
    """Retrieve a structured EnterprisePersona by role ID.

    Maintains 100% backward compatibility:
    - Normalizes case and underscores (e.g. 'cto' -> 'CTO', 'sales-manager' -> 'SALES_MANAGER').
    - If an unknown role is requested, attempts to load legacy markdown or creates
      a safe baseline structured persona rather than crashing.
    - If scenario text is provided, seamlessly merges it into the persona's world_model.
    """
    clean_role_id = role_id.strip().upper().replace("-", "_")

    if clean_role_id in _PERSONA_REGISTRY:
        persona = deepcopy(_PERSONA_REGISTRY[clean_role_id])
    else:
        # Fallback: attempt to read legacy markdown file if it exists, or build a resilient generic persona
        role_file = os.path.join(os.path.dirname(__file__), f"{role_id}.md")
        legacy_text = ""
        if os.path.exists(role_file):
            try:
                with open(role_file, "r") as f:
                    legacy_text = f.read()
            except Exception:
                pass

        persona = EnterprisePersona(
            profile=PersonaProfile(
                role=role_id,
                title=f"{role_id} Professional",
                department="Corporate Operations",
                seniority="Executive",
                years_of_experience=10,
                industry_expertise=["Enterprise Business"],
                technical_depth="Strategic / Professional",
                communication_style="Professional, objective, and realistic",
                personality_characteristics=["Professional", "Objective"],
                risk_profile="Calculated Moderate",
            ),
            values=[
                ValueOrientation(name="reliability", weight=0.85, description="Values consistent delivery and competence.", priority=1),
                ValueOrientation(name="cost", weight=0.70, description="Mindful of organizational resources.", priority=2),
            ],
            goals=[
                StakeholderGoal(
                    id="evaluate_proposal",
                    description=f"Evaluate candidate performance and proposal from the perspective of {role_id}.",
                    priority=0.90,
                    type="business",
                    success_condition="Candidate provides clear, professional answers.",
                    dealbreaker=False,
                )
            ],
            incentives=[
                Incentive(id="protect_business_outcomes", description="Ensure decisions benefit the organization.", importance=0.85, category="organizational")
            ],
            knowledge_boundary=KnowledgeBoundary(
                known_topics=[f"Domain operations of {role_id}"],
            ),
            world_model=CompanyContext(
                industry="Enterprise Business",
                company_size="Enterprise",
                pain_points=[legacy_text] if legacy_text else [],
            ),
        )

    # If scenario is provided, enrich the persona's world_model
    if scenario and scenario.strip():
        if persona.world_model is None:
            persona.world_model = CompanyContext(
                industry="Enterprise Business",
                company_size="Enterprise",
                current_initiative=scenario.strip(),
            )
        else:
            persona.world_model.current_initiative = scenario.strip()

    return persona
