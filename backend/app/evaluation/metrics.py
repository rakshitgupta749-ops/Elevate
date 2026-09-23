"""Fidelity Metrics and Algorithmic Scoring for Simulator Evaluation.

Provides deterministic mathematical calculations for:
1. State Coherence & Oscillation Analysis
2. Persona Consistency
3. Goal Consistency
4. Behavioral Consistency & Trajectory Verification
5. Information Integrity & Memory Fidelity
6. Response-Action Alignment
7. Cross-Persona Divergence & Persona Collapse Detection
8. Overall Composite Simulator Fidelity

NOTE: These metrics are internal engineering and research benchmarks designed to measure
system fidelity, causal coherence, and architectural improvement. They are not
psychometric standards.
"""

from typing import List, Dict, Optional, Tuple, Any
import re
from app.evaluation.evaluation_models import (
    SimulatorFailureCategory,
    ExpectedBehavior,
    TurnEvaluation,
)


def calculate_state_trajectory_coherence(
    trajectory: List[Dict[str, float]],
    expected_pattern: Optional[Dict[str, str]] = None,
) -> Tuple[float, List[SimulatorFailureCategory]]:
    """Calculate the coherence and stability of the client perception state trajectory.
    
    Evaluates:
    - Monotonicity / directional adherence to scenario expectations
    - Frequency of rapid oscillation (flapping)
    - Unexplained abrupt reversals
    - Out-of-bounds metrics (0.0 to 1.0 clamping integrity)
    
    Formula:
      coherence = 1.0 - (0.4 * oscillation_penalty + 0.4 * directional_penalty + 0.2 * bound_violations)
    """
    if not trajectory or len(trajectory) < 2:
        return 1.0, []

    failures = []
    total_metrics_evaluated = 0
    oscillation_count = 0
    directional_errors = 0
    bound_violations = 0

    metric_keys = ["trust", "skepticism", "patience", "interest", "frustration", "perceived_risk"]
    expected_pattern = expected_pattern or {}

    for key in metric_keys:
        values = [t.get(key, 0.5) for t in trajectory if key in t]
        if len(values) < 2:
            continue

        total_metrics_evaluated += 1

        # Check bounds
        for v in values:
            if v < 0.0 or v > 1.0:
                bound_violations += 1

        # Check oscillation: sign changes in deltas
        deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
        sign_changes = 0
        for i in range(1, len(deltas)):
            # If sign flips with non-trivial delta magnitude (> 0.05)
            if (deltas[i] * deltas[i - 1] < -0.001) and (abs(deltas[i]) >= 0.05 or abs(deltas[i - 1]) >= 0.05):
                sign_changes += 1

        if sign_changes >= 2:
            oscillation_count += 1
            if SimulatorFailureCategory.STATE_OSCILLATION not in failures:
                failures.append(SimulatorFailureCategory.STATE_OSCILLATION)

        # Check expected overall direction
        if key in expected_pattern:
            target_dir = expected_pattern[key].lower()
            overall_delta = values[-1] - values[0]
            if "increase" in target_dir and overall_delta < -0.05:
                directional_errors += 1
            elif "decrease" in target_dir and overall_delta > 0.05:
                directional_errors += 1

    if total_metrics_evaluated == 0:
        return 1.0, failures

    osc_ratio = oscillation_count / max(1, total_metrics_evaluated)
    dir_ratio = directional_errors / max(1, total_metrics_evaluated)
    bnd_ratio = min(1.0, bound_violations / max(1, len(trajectory) * 6))

    raw_score = 1.0 - (0.45 * osc_ratio + 0.45 * dir_ratio + 0.10 * bnd_ratio)
    coherence_score = max(0.0, min(1.0, raw_score))

    return round(coherence_score, 3), failures


def evaluate_persona_consistency(
    turns: List[Dict[str, Any]],
    persona_role: str,
    technical_depth: str = "deep",
) -> Tuple[float, List[SimulatorFailureCategory]]:
    """Evaluate whether the simulated stakeholder maintains role-consistent posture."""
    if not turns:
        return 1.0, []

    failures = []
    penalties = 0.0

    role_upper = persona_role.upper()
    role_keywords = {
        "CTO": ["architecture", "scale", "latency", "tech", "security", "infrastructure", "api", "integration", "reliability", "downtime", "stack"],
        "CFO": ["cost", "budget", "roi", "margin", "commercial", "pricing", "financial", "expenditure", "terms", "contract"],
        "SALES_MANAGER": ["quota", "revenue", "pipeline", "conversion", "sales", "crm", "adoption", "churn", "enablement"],
    }

    keywords = role_keywords.get(role_upper, ["process", "strategy", "impact", "outcomes"])

    keyword_hits = 0
    total_evaluated_turns = 0

    for t in turns:
        resp = t.get("stakeholder_response", "").lower()
        if not resp:
            continue
        total_evaluated_turns += 1

        # Check if response reflects role vocabulary
        if any(k in resp for k in keywords):
            keyword_hits += 1

        # Check for AI identity breaks
        if any(ai_phrase in resp for ai_phrase in ["as an ai", "as a language model", "i am an artificial"]):
            penalties += 0.5
            if SimulatorFailureCategory.ROLE_INCONSISTENCY not in failures:
                failures.append(SimulatorFailureCategory.ROLE_INCONSISTENCY)

    if total_evaluated_turns == 0:
        return 1.0, failures

    hit_ratio = keyword_hits / total_evaluated_turns
    score = max(0.0, min(1.0, 0.4 + 0.6 * hit_ratio - penalties))

    if score < 0.6:
        failures.append(SimulatorFailureCategory.PERSONA_DRIFT)

    return round(score, 3), failures


def evaluate_goal_consistency(
    turns: List[Dict[str, Any]],
    persona_goals: List[Any],
    decisions: Optional[List[Any]] = None,
) -> Tuple[float, List[SimulatorFailureCategory]]:
    """Evaluate whether stakeholder pursues configured evaluation goals across the session."""
    if not turns or not persona_goals:
        return 1.0, []

    failures = []
    # Collect all stakeholder responses and target topics
    all_responses = " ".join([t.get("stakeholder_response", "").lower() for t in turns])
    action_targets = []
    if decisions:
        for d in decisions:
            if hasattr(d, "primary_action"):
                action_targets.append((d.primary_action.target or "").lower())
            elif isinstance(d, dict):
                act = d.get("primary_action", {})
                action_targets.append((act.get("target") or "").lower())

    goals_addressed = 0
    total_goals = len(persona_goals)

    for g in persona_goals:
        desc = getattr(g, "description", "").lower()
        success_cond = getattr(g, "success_condition", "").lower()
        words = [w for w in (desc + " " + success_cond).split() if len(w) > 4]

        # Check if key goal concepts appeared in questions or action targets
        hit = False
        if any(w in all_responses for w in words):
            hit = True
        elif any(w in t for t in action_targets for w in words):
            hit = True

        if hit:
            goals_addressed += 1

    ratio = goals_addressed / max(1, total_goals)
    score = max(0.0, min(1.0, 0.3 + 0.7 * ratio))

    if score < 0.6:
        failures.append(SimulatorFailureCategory.GOAL_DRIFT)

    return round(score, 3), failures


def evaluate_behavior_consistency(
    turns: List[Dict[str, Any]],
    expected_behaviors: List[ExpectedBehavior],
) -> Tuple[float, List[SimulatorFailureCategory]]:
    """Evaluate whether stakeholder reactions conform to declarative behavioral expectations."""
    if not turns or not expected_behaviors:
        return 1.0, []

    failures = []
    total_checks = 0
    passed_checks = 0

    for exp in expected_behaviors:
        start_turn, end_turn = exp.turn_range[0], exp.turn_range[1]
        relevant_turns = [t for t in turns if start_turn <= t.get("turn_number", 0) <= end_turn]

        for t in relevant_turns:
            total_checks += 1
            act = t.get("selected_action", "")
            resp = t.get("stakeholder_response", "").lower()

            # Check forbidden action types
            if act and act in exp.forbidden_action_types:
                if SimulatorFailureCategory.POLICY_RESPONSE_MISMATCH not in failures:
                    failures.append(SimulatorFailureCategory.POLICY_RESPONSE_MISMATCH)
                continue

            # Check expected action types
            action_match = False
            if exp.expected_action_types:
                if act and act in exp.expected_action_types:
                    action_match = True
                else:
                    # Semantic heuristic in response text
                    for expected_act in exp.expected_action_types:
                        if "evidence" in expected_act.lower() or "challenge" in expected_act.lower():
                            if any(w in resp for w in ["what data", "basis", "prove", "concrete", "how do you", "guarantee"]):
                                action_match = True
                                break
                        elif "withhold" in expected_act.lower():
                            if any(w in resp for w in ["cannot share", "internal only", "focus on", "not able to disclose"]):
                                action_match = True
                                break
                        elif "question" in expected_act.lower() or "probe" in expected_act.lower():
                            if "?" in resp:
                                action_match = True
                                break
            else:
                action_match = True

            if action_match:
                passed_checks += 1

    if total_checks == 0:
        return 1.0, failures

    score = passed_checks / total_checks
    if score < 0.6:
        failures.append(SimulatorFailureCategory.POLICY_RESPONSE_MISMATCH)

    return round(score, 3), failures


def evaluate_information_and_memory(
    turns: List[Dict[str, Any]],
    world_facts: Optional[List[Any]] = None,
    confidential_topics: Optional[List[str]] = None,
    memory_events: Optional[List[Any]] = None,
) -> Tuple[float, float, float, List[SimulatorFailureCategory]]:
    """Evaluate information integrity, confidentiality compliance, and conversational memory fidelity.
    
    Returns:
      (information_consistency, knowledge_boundary_compliance, memory_consistency, failures)
    """
    failures = []
    info_penalties = 0.0
    leak_penalties = 0.0
    mem_penalties = 0.0

    all_responses = " ".join([t.get("stakeholder_response", "") for t in turns]).lower()

    # 1. Confidentiality leaks
    confidential_topics = confidential_topics or ["exact budget", "profit margin", "unannounced roadmap", "internal margin"]
    for topic in confidential_topics:
        # Check if numbers or leaks occurred following confidential terms
        if topic.lower() in all_responses:
            # E.g. "our budget is $500k" or "our margin is 25%"
            if re.search(rf"{re.escape(topic.lower())}.*?(\$\d+|\d+%)", all_responses):
                leak_penalties += 0.4
                if SimulatorFailureCategory.INFORMATION_LEAK not in failures:
                    failures.append(SimulatorFailureCategory.INFORMATION_LEAK)
                if SimulatorFailureCategory.OVER_DISCLOSURE not in failures:
                    failures.append(SimulatorFailureCategory.OVER_DISCLOSURE)

    # 2. Immutable world fact contradictions
    if world_facts:
        for f in world_facts:
            key = getattr(f, "key", "")
            val = str(getattr(f, "value", "")).lower()
            # If world fact says company size is 5000 and response says 50 employees
            if key == "company_size" and "50 employees" in all_responses and "5000" in val:
                info_penalties += 0.5
                failures.append(SimulatorFailureCategory.WORLD_FACT_CONTRADICTION)

    # 3. Memory consistency (contradiction catching)
    contradiction_turn_seen = any("contradiction" in str(m).lower() for m in (memory_events or []))
    # If candidate contradicted themselves in turn 4 vs 2, check if response addressed it
    has_candidate_contradiction_in_turns = any("40-minute" in t.get("candidate_input", "") or "45-minute" in t.get("candidate_input", "") for t in turns)
    if has_candidate_contradiction_in_turns:
        # Check if stakeholder challenged the contradiction
        addressed = any(w in all_responses for w in ["earlier you said", "previously mentioned", "15 minute", "inconsistency", "differ"])
        if not addressed and not contradiction_turn_seen:
            mem_penalties += 0.3
            failures.append(SimulatorFailureCategory.MEMORY_FAILURE)

    info_score = max(0.0, min(1.0, 1.0 - info_penalties))
    boundary_score = max(0.0, min(1.0, 1.0 - leak_penalties))
    mem_score = max(0.0, min(1.0, 1.0 - mem_penalties))

    return round(info_score, 3), round(boundary_score, 3), round(mem_score, 3), failures


def evaluate_action_response_alignment(
    selected_action: Optional[str],
    response_text: str,
) -> float:
    """Calculate whether the generated verbal response faithfully realizes the policy action.
    
    Formula:
      action_alignment = compatible_behaviors / total_evaluated_behaviors
    """
    if not selected_action or not response_text:
        return 1.0

    act = selected_action.upper()
    resp = response_text.lower()

    if act in ["REQUEST_EVIDENCE", "CHALLENGE_CLAIM"]:
        # Should ask for concrete validation or challenge figures
        indicators = ["what data", "basis", "how do you", "concrete", "proof", "metric", "evidence", "demonstrate", "?"]
        has_probe = any(ind in resp for ind in indicators)
        has_blind_acceptance = any(acc in resp for acc in ["sounds great", "let's move on", "no problem", "i agree completely"])
        if has_probe and not has_blind_acceptance:
            return 1.0
        elif has_probe:
            return 0.7
        else:
            return 0.2

    elif act == "WITHHOLD_INFORMATION":
        # Should refuse or deflect disclosure
        indicators = ["cannot share", "internal only", "focus on", "not able to disclose", "confidential", "keep our discussion"]
        return 1.0 if any(ind in resp for ind in indicators) else 0.2

    elif act in ["ASK_QUESTION", "PROBE_TECHNICAL_DETAIL", "PROBE_BUSINESS_VALUE", "PROBE_RISK", "PROBE_SECURITY"]:
        return 1.0 if "?" in resp else 0.4

    elif act == "TERMINATE":
        indicators = ["[end_interview]", "terminate", "not a fit", "conclude", "pass on this opportunity"]
        return 1.0 if any(ind in resp for ind in indicators) else 0.3

    elif act == "EXPRESS_SKEPTICISM":
        indicators = ["skeptical", "hard to believe", "ambitious", "dubious", "unrealistic", "how exactly", "?"]
        return 1.0 if any(ind in resp for ind in indicators) else 0.4

    return 0.9


def calculate_persona_divergence(
    responses_by_persona: Dict[str, str],
    actions_by_persona: Dict[str, str],
) -> Tuple[float, List[SimulatorFailureCategory]]:
    """Measure divergence between different personas given identical candidate input.
    
    Prevents 'persona collapse' where CTO, CFO, and Sales Director produce identical behavior.
    """
    failures = []
    if len(actions_by_persona) < 2:
        return 1.0, failures

    actions = list(actions_by_persona.values())
    unique_actions = set(actions)

    # Ratio of unique actions to total personas tested
    action_diversity = len(unique_actions) / len(actions)

    # Word-level vocabulary difference
    responses = list(responses_by_persona.values())
    vocab_sets = [set(r.lower().split()) for r in responses if r]
    jaccard_similarities = []
    for i in range(len(vocab_sets)):
        for j in range(i + 1, len(vocab_sets)):
            s1, s2 = vocab_sets[i], vocab_sets[j]
            if s1 and s2:
                sim = len(s1.intersection(s2)) / len(s1.union(s2))
                jaccard_similarities.append(sim)

    avg_similarity = sum(jaccard_similarities) / max(1, len(jaccard_similarities)) if jaccard_similarities else 0.5
    divergence = (action_diversity * 0.6) + ((1.0 - avg_similarity) * 0.4)
    divergence_score = max(0.0, min(1.0, divergence))

    if divergence_score < 0.35:
        failures.append(SimulatorFailureCategory.PERSONA_COLLAPSE)

    return round(divergence_score, 3), failures


def calculate_overall_fidelity(
    persona_consistency: float,
    goal_consistency: float,
    behavior_consistency: float,
    state_coherence: float,
    information_consistency: float,
    knowledge_boundary_compliance: float,
    action_response_alignment: float,
    memory_consistency: float,
) -> float:
    """Calculate composite engineering fidelity score.
    
    Weights:
    - 0.15 Persona Consistency
    - 0.15 Goal Consistency
    - 0.15 Behavior Consistency
    - 0.15 State Coherence
    - 0.15 Information Consistency
    - 0.10 Knowledge Boundary Compliance
    - 0.10 Action-Response Alignment
    - 0.05 Memory Consistency
    """
    raw_composite = (
        0.15 * persona_consistency
        + 0.15 * goal_consistency
        + 0.15 * behavior_consistency
        + 0.15 * state_coherence
        + 0.15 * information_consistency
        + 0.10 * knowledge_boundary_compliance
        + 0.10 * action_response_alignment
        + 0.05 * memory_consistency
    )
    return round(max(0.0, min(1.0, raw_composite)), 3)
