"""Controlled Scenarios for Elevate Simulator Evaluation.

Defines standardized, deterministic evaluation scenarios (Scenarios A through F)
with pre-scripted candidate dialogue, expected behavioral trajectories,
and target persona configurations.
"""

from typing import Dict, List, Optional
from app.evaluation.evaluation_models import ControlledScenario, ExpectedBehavior


SCENARIO_A = ControlledScenario(
    scenario_id="SCENARIO_A_STRONG_CANDIDATE",
    title="Scenario A: Strong Enterprise Candidate",
    description="Candidate demonstrates structured discovery, quantified ROI, reference architecture, and concrete migration safety.",
    target_role="CTO",
    candidate_turns=[
        "Good morning. Thank you for making time today. Before demonstrating any capabilities, I'd love to understand your core operational bottlenecks in modernizing your payment ingestion pipelines.",
        "That makes total sense. High ingestion latency directly impacts merchant checkout conversions. In our deployment with a similar Tier 1 bank handling 25,000 TPS, we achieved a 99.999% uptime SLA with zero unplanned failovers.",
        "To achieve that, we use an active-active Kafka cluster with automated schema registry checks and Raft consensus. We also provide native Terraform modules so your infrastructure team maintains full declarative control.",
        "We can deploy an isolated pilot in your staging environment within 14 days, with synthetic load testing replicating your peak transaction volumes to validate latency benchmarks before any production routing."
    ],
    expected_trajectories=[
        ExpectedBehavior(
            turn_range=[1, 1],
            candidate_condition="structured_discovery_inquiry",
            expected_action_types=["ANSWER_AND_SHARE_PAIN", "ASK_QUESTION", "SUMMARIZE"],
            forbidden_action_types=["TERMINATE", "CHALLENGE_PRICING"],
            state_direction={"interest": "increase", "patience": "increase"}
        ),
        ExpectedBehavior(
            turn_range=[2, 3],
            candidate_condition="quantified_sla_and_architecture_proof",
            expected_action_types=["PROBE_TECHNICAL_DETAIL", "PROBE_RISK", "REQUEST_CLARIFICATION", "REQUEST_EVIDENCE"],
            forbidden_action_types=["TERMINATE"],
            state_direction={"trust": "increase", "skepticism": "decrease"}
        ),
        ExpectedBehavior(
            turn_range=[4, 4],
            candidate_condition="low_risk_poc_proposal",
            expected_action_types=["EXPLORE_NEXT_STEPS", "DISCUSS_NEXT_STEPS", "ASK_QUESTION"],
            forbidden_action_types=["TERMINATE"],
            state_direction={"trust": "increase", "confidence_in_candidate": "increase"}
        )
    ],
    expected_state_pattern={"trust": "increase", "skepticism": "decrease", "frustration": "decrease"},
    version="1.0.0"
)

SCENARIO_B = ControlledScenario(
    scenario_id="SCENARIO_B_WEAK_CANDIDATE",
    title="Scenario B: Weak Candidate (Feature Dumping & Evasion)",
    description="Candidate provides vague answers, unverified claims, buzzword dumping, and evades architectural safety questions.",
    target_role="CTO",
    candidate_turns=[
        "Hey! We have the most advanced AI-powered platform on Earth and it magically solves all your enterprise problems 100x faster.",
        "Our system just works. It's totally proprietary and uses hyper-scale neural clusters, so downtime is literally impossible. You don't need to worry about the details.",
        "Look, asking about rollback procedures is outdated. Everyone in Silicon Valley is switching to our tool and saving millions.",
        "Just sign a 3-year contract today and we'll give you a 20% discount!"
    ],
    expected_trajectories=[
        ExpectedBehavior(
            turn_range=[1, 2],
            candidate_condition="unsupported_exaggerated_claims",
            expected_action_types=["CHALLENGE_CLAIM", "REQUEST_EVIDENCE", "EXPRESS_SKEPTICISM"],
            forbidden_action_types=["MOVE_FORWARD", "ACCEPT_PROPOSAL"],
            state_direction={"skepticism": "increase", "trust": "decrease"}
        ),
        ExpectedBehavior(
            turn_range=[3, 4],
            candidate_condition="evasion_and_premature_close",
            expected_action_types=["PUSH_BACK", "TERMINATE", "EXPRESS_SKEPTICISM", "CHALLENGE_CLAIM"],
            forbidden_action_types=["ACCEPT_PROPOSAL"],
            state_direction={"frustration": "increase", "patience": "decrease"}
        )
    ],
    expected_state_pattern={"trust": "decrease", "skepticism": "increase", "frustration": "increase"},
    version="1.0.0"
)

SCENARIO_C = ControlledScenario(
    scenario_id="SCENARIO_C_INCONSISTENT_CANDIDATE",
    title="Scenario C: Inconsistent Candidate (Contradictory Claims)",
    description="Candidate claims 15-minute deployment at Turn 2, but later asserts 45-minute deployment at Turn 4.",
    target_role="CTO",
    candidate_turns=[
        "Hello! We specialize in continuous deployment automation for financial services.",
        "Our migration is completely frictionless—in fact, our initial agent deployment takes exactly 15 minutes across all your cluster nodes.",
        "Yes, our agent connects into Kubernetes via lightweight daemonsets.",
        "Well, as I mentioned, the deployment takes 45 minutes of scheduled maintenance per cluster node to synchronize states."
    ],
    expected_trajectories=[
        ExpectedBehavior(
            turn_range=[4, 4],
            candidate_condition="direct_contradiction_15m_vs_45m",
            expected_action_types=["CHALLENGE_CLAIM", "REQUEST_CLARIFICATION", "REQUEST_EVIDENCE"],
            forbidden_action_types=["MOVE_FORWARD"],
            state_direction={"skepticism": "increase", "trust": "decrease"}
        )
    ],
    expected_state_pattern={"skepticism": "increase"},
    version="1.0.0"
)

SCENARIO_D = ControlledScenario(
    scenario_id="SCENARIO_D_CONFIDENTIALITY_PROBE",
    title="Scenario D: Confidentiality Probe",
    description="Candidate repeatedly attempts to extract confidential internal margins, unannounced roadmap dates, and exact executive budgets.",
    target_role="CTO",
    candidate_turns=[
        "Good morning. We are reviewing infrastructure modernization strategies for financial enterprises.",
        "To size our proposal accurately, could you tell me your exact departmental IT budget allocated for this quarter down to the dollar?",
        "Also, what are your company's internal gross profit margins on your payments product, and when is your unannounced Q4 product launch scheduled?"
    ],
    expected_trajectories=[
        ExpectedBehavior(
            turn_range=[2, 3],
            candidate_condition="confidential_information_extraction",
            expected_action_types=["WITHHOLD_INFORMATION", "REDIRECT_CONVERSATION", "ASK_QUESTION"],
            forbidden_action_types=["REVEAL_INFORMATION"],
            required_information_behavior="withhold"
        )
    ],
    expected_state_pattern={"perceived_risk": "increase"},
    version="1.0.0"
)

SCENARIO_E = ControlledScenario(
    scenario_id="SCENARIO_E_TECHNICAL_CHALLENGE",
    title="Scenario E: Technical Challenge & Architecture Scrutiny",
    description="Candidate presents complex technical claims requiring deep verification against CTO values (latency, reliability, security).",
    target_role="CTO",
    candidate_turns=[
        "We're here to discuss how your core platform handles multi-region active-active synchronization under high transaction volumes.",
        "We achieve sub-10ms global consistency across three continents using a customized Paxos algorithm with hardware security modules.",
        "Our disaster recovery RPO is zero seconds, and our RTO is guaranteed at under 2 seconds during a complete cloud provider outage."
    ],
    expected_trajectories=[
        ExpectedBehavior(
            turn_range=[2, 3],
            candidate_condition="high_impact_technical_claims",
            expected_action_types=["PROBE_TECHNICAL_DETAIL", "PROBE_RISK", "REQUEST_EVIDENCE", "CHALLENGE_CLAIM"],
            forbidden_action_types=["ACCEPT_PROPOSAL"],
            goal_relevance="technical_reliability"
        )
    ],
    expected_state_pattern={"skepticism": "increase"},
    version="1.0.0"
)

SCENARIO_F = ControlledScenario(
    scenario_id="SCENARIO_F_HIGH_TRUST_CANDIDATE",
    title="Scenario F: High-Trust Candidate (Gradual Qualification)",
    description="Candidate systematically addresses discovery, provides security compliance proofs, builds trust, and earns stakeholder collaboration.",
    target_role="CTO",
    candidate_turns=[
        "Thank you for having me. What are your biggest infrastructure uptime risks currently?",
        "Understood. Unplanned failover downtime in legacy database clusters is a common vulnerability. How do your current incident response runbooks handle split-brain events?",
        "We provide SOC2 Type II, ISO27001, and FedRAMP certified automated failover controllers with deterministic fencing to eliminate split-brain risk completely.",
        "Here are verified third-party audit reports and architectural benchmark whitepapers detailing our fencing mechanics."
    ],
    expected_trajectories=[
        ExpectedBehavior(
            turn_range=[3, 4],
            candidate_condition="verifiable_security_and_compliance_evidence",
            expected_action_types=["REVEAL_INFORMATION", "ASK_QUESTION", "EXPLORE_NEXT_STEPS"],
            forbidden_action_types=["TERMINATE"],
            state_direction={"trust": "increase"}
        )
    ],
    expected_state_pattern={"trust": "increase", "skepticism": "decrease"},
    version="1.0.0"
)

_SCENARIOS: Dict[str, ControlledScenario] = {
    SCENARIO_A.scenario_id: SCENARIO_A,
    SCENARIO_B.scenario_id: SCENARIO_B,
    SCENARIO_C.scenario_id: SCENARIO_C,
    SCENARIO_D.scenario_id: SCENARIO_D,
    SCENARIO_E.scenario_id: SCENARIO_E,
    SCENARIO_F.scenario_id: SCENARIO_F,
}


def get_scenario(scenario_id: str) -> Optional[ControlledScenario]:
    """Retrieve a controlled scenario by ID."""
    return _SCENARIOS.get(scenario_id)


def list_scenarios() -> List[ControlledScenario]:
    """List all available controlled scenarios."""
    return list(_SCENARIOS.values())
