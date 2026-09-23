"""Report Generator for Elevate Simulator Evaluations.

Formats formal evaluation results and comparative ablation experiment outcomes
into human-readable Markdown and CLI summary reports.
"""

from typing import Dict, Any, List
from app.evaluation.evaluation_models import SimulatorEvaluation


def generate_evaluation_markdown_report(eval_res: SimulatorEvaluation) -> str:
    """Format a SimulatorEvaluation into a structured Markdown report."""
    failure_bullets = "\n".join([f"- **{f.value}**" for f in eval_res.failure_categories]) if eval_res.failure_categories else "- None (Clean behavioral execution)"

    turn_rows = []
    for t in eval_res.turn_evaluations:
        cand_snip = (t.candidate_input[:45] + "...") if len(t.candidate_input) > 45 else t.candidate_input
        cand_snip = cand_snip.replace("\n", " ")
        resp_snip = (t.stakeholder_response[:55] + "...") if len(t.stakeholder_response) > 55 else t.stakeholder_response
        resp_snip = resp_snip.replace("\n", " ")
        act_str = t.selected_action or "None (Static)"
        turn_rows.append(f"| {t.turn_number} | {cand_snip} | {resp_snip} | {act_str} | {t.action_alignment:.2f} | {t.latency_ms:.0f}ms |")

    turn_table = "\n".join(turn_rows) if turn_rows else "| - | - | - | - | - | - |"

    md = f"""# Elevate Simulator Fidelity Evaluation Report

> **DISCLAIMER**: These metrics are internal engineering and research benchmarks designed to measure system fidelity, causal coherence, and architectural improvement across simulation layers. They are not psychometric standards.

---

## Executive Summary
- **Session ID**: `{eval_res.session_id}`
- **Scenario**: `{eval_res.scenario_id}`
- **Target Persona**: `{eval_res.persona_id}`
- **Architecture Mode**: `{eval_res.architecture_mode.value}`
- **Evaluation Method**: `{eval_res.evaluation_method}`
- **Timestamp**: `{eval_res.created_at}`

---

## Fidelity Metrics Overview

| Metric Dimension | Score | Description |
|---|---|---|
| **Persona Consistency** | **{eval_res.persona_consistency:.3f}** | Adherence to role, technical depth, and communication style |
| **Goal Consistency** | **{eval_res.goal_consistency:.3f}** | Persistence in pursuing configured stakeholder objectives |
| **Behavioral Consistency** | **{eval_res.behavior_consistency:.3f}** | Reactive plausibility against declarative expectations |
| **State Coherence** | **{eval_res.state_coherence:.3f}** | Monotonicity, stability, and lack of erratic oscillation |
| **Information Consistency** | **{eval_res.information_consistency:.3f}** | World fact immutability and non-contradiction |
| **Knowledge Compliance** | **{eval_res.knowledge_boundary_compliance:.3f}** | Strict withholding of confidential and forbidden data |
| **Action-Response Alignment** | **{eval_res.action_response_alignment:.3f}** | Execution match between policy action and verbal output |
| **Memory Consistency** | **{eval_res.memory_consistency:.3f}** | Historical claim recall and contradiction detection |
| **OVERALL FIDELITY** | **{eval_res.overall_fidelity:.3f}** | **Weighted Composite Engineering Fidelity Score** |

---

## Standardized Failure Categories Detected
{failure_bullets}

---

## Turn-by-Turn Execution Trace

| Turn | Candidate Input | Stakeholder Response | Selected Action | Alignment | Latency |
|---|---|---|---|---|---|
{turn_table}

---

## Performance & Reproducibility Metadata
- **Avg Turn Latency**: {eval_res.performance_metrics.get('avg_turn_latency_ms', 0.0)}ms
- **Total Session Latency**: {eval_res.performance_metrics.get('total_session_latency_ms', 0.0)}ms
- **Model**: `{eval_res.reproducibility_metadata.get('model_name', 'default')}`
- **Random Seed**: `{eval_res.reproducibility_metadata.get('random_seed', 42)}`
- **Evaluation Version**: `{eval_res.reproducibility_metadata.get('evaluation_version', '8.0.0')}`
"""
    return md.strip()


def generate_experiment_markdown_report(exp_result: Dict[str, Any]) -> str:
    """Format an ablation research experiment result into Markdown."""
    exp_id = exp_result.get("experiment_id")
    rq = exp_result.get("research_question")
    base_eval = exp_result.get("baseline_evaluation", {})
    treat_eval = exp_result.get("treatment_evaluation", {})
    findings = exp_result.get("findings", "")

    md = f"""# Elevate Research Experiment: {exp_id}

### Research Question
> **"{rq}"**

---

## Comparative Architecture Results

| Dimension | Baseline ({exp_result.get('baseline_mode')}) | Treatment ({exp_result.get('treatment_mode')}) | Delta |
|---|---|---|---|
| **Overall Fidelity** | {base_eval.get('overall_fidelity', 0.0):.3f} | {treat_eval.get('overall_fidelity', 0.0):.3f} | **{exp_result.get('overall_fidelity_delta', 0.0):+.3f}** |
| **Persona Consistency** | {base_eval.get('persona_consistency', 0.0):.3f} | {treat_eval.get('persona_consistency', 0.0):.3f} | {treat_eval.get('persona_consistency', 0.0) - base_eval.get('persona_consistency', 0.0):+.3f} |
| **State Coherence** | {base_eval.get('state_coherence', 0.0):.3f} | {treat_eval.get('state_coherence', 0.0):.3f} | {treat_eval.get('state_coherence', 0.0) - base_eval.get('state_coherence', 0.0):+.3f} |
| **Behavior Consistency** | {base_eval.get('behavior_consistency', 0.0):.3f} | {treat_eval.get('behavior_consistency', 0.0):.3f} | {treat_eval.get('behavior_consistency', 0.0) - base_eval.get('behavior_consistency', 0.0):+.3f} |
| **Action-Response Alignment** | {base_eval.get('action_response_alignment', 0.0):.3f} | {treat_eval.get('action_response_alignment', 0.0):.3f} | {treat_eval.get('action_response_alignment', 0.0) - base_eval.get('action_response_alignment', 0.0):+.3f} |
| **Information Consistency** | {base_eval.get('information_consistency', 0.0):.3f} | {treat_eval.get('information_consistency', 0.0):.3f} | {treat_eval.get('information_consistency', 0.0) - base_eval.get('information_consistency', 0.0):+.3f} |

---

## Empirical Findings & Interpretation
{findings}

> **NOTE**: Evaluation conducted under controlled seed with standardized candidate stimulus script.
"""
    return md.strip()
