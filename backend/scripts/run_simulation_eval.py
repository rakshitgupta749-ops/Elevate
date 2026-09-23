#!/usr/bin/env python3
"""Elevate Simulator Fidelity Evaluation CLI.

Command-line tool to run controlled scenario evaluations across architecture ablation modes
and execute formal research experiments (RQ1, RQ2, RQ3).

Examples:
  python backend/scripts/run_simulation_eval.py --mode FULL_SIMULATOR --scenario SCENARIO_A_STRONG_CANDIDATE
  python backend/scripts/run_simulation_eval.py --mode STATIC_PROMPT --scenario SCENARIO_B_WEAK_CANDIDATE
  python backend/scripts/run_simulation_eval.py --experiment RQ1
"""

import sys
import os
import argparse

# Ensure backend root is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.evaluation.evaluation_models import SimulatorArchitectureMode
from app.evaluation.controlled_scenarios import list_scenarios
from app.evaluation.evaluation_runner import EvaluationRunner
from app.evaluation.report_generator import (
    generate_evaluation_markdown_report,
    generate_experiment_markdown_report,
)


def main():
    parser = argparse.ArgumentParser(description="Elevate Simulator Fidelity Evaluation Runner")
    parser.add_argument(
        "--mode",
        type=str,
        default="FULL_SIMULATOR",
        choices=[m.value for m in SimulatorArchitectureMode],
        help="Architecture ablation mode",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default="SCENARIO_A_STRONG_CANDIDATE",
        help="Scenario ID (e.g. SCENARIO_A_STRONG_CANDIDATE, SCENARIO_B_WEAK_CANDIDATE)",
    )
    parser.add_argument(
        "--persona",
        type=str,
        default="CTO",
        help="Target persona role ID (e.g. CTO, CFO, SALES_MANAGER)",
    )
    parser.add_argument(
        "--experiment",
        type=str,
        default=None,
        choices=["RQ1", "RQ2", "RQ3"],
        help="Run formal research experiment (RQ1, RQ2, or RQ3)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional file path to save Markdown report",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for evaluation run reproducibility",
    )

    args = parser.parse_args()
    runner = EvaluationRunner()

    if args.experiment:
        print(f"\n[*] Executing Research Experiment: {args.experiment}...")
        res = runner.run_experiment(args.experiment)
        report_md = generate_experiment_markdown_report(res)
        print("\n" + report_md + "\n")
        if args.output:
            with open(args.output, "w") as f:
                f.write(report_md)
            print(f"[+] Experiment report written to: {args.output}")
    else:
        print(f"\n[*] Running Evaluation: Scenario='{args.scenario}' | Mode='{args.mode}' | Persona='{args.persona}'...")
        eval_result = runner.run_scenario_evaluation(
            scenario_id=args.scenario,
            architecture_mode=SimulatorArchitectureMode(args.mode),
            role_id=args.persona,
            random_seed=args.seed,
        )
        report_md = generate_evaluation_markdown_report(eval_result)
        print("\n" + report_md + "\n")
        if args.output:
            with open(args.output, "w") as f:
                f.write(report_md)
            print(f"[+] Evaluation report written to: {args.output}")


if __name__ == "__main__":
    main()
