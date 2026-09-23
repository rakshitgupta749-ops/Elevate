# Elevate Simulator Fidelity Evaluation Framework (Phase 8)

## Executive Summary

Phase 8 establishes a formal **Simulator Evaluation Framework** for the Elevate simulation engine, answering the central research question:
> **"Does a goal-, value-, state-, behavior-, and memory-driven stakeholder simulator produce more behaviorally faithful enterprise-client interactions than static persona prompting?"**

The framework allows researchers and engineers to measure, compare, and validate whether each successive layer of the Elevate simulation engine improves client realism, consistency, and conversational integrity.

---

## 1. Separation of Evaluation Targets

The Elevate platform maintains two strictly independent evaluation systems:

```text
┌────────────────────────────────────────────────────────┐
│ 1. Salesperson / Candidate Evaluator (Existing)       │
│ "How well did the candidate perform?"                  │
│ • Scoring 1-10 on objection handling                   │
│ • Discovery depth, domain expertise, closing skills    │
│ • Generates post-interview coaching feedback           │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ 2. Simulator Fidelity Evaluator (Phase 8 - NEW)        │
│ "How realistic and consistent was the stakeholder?"   │
│ • Persona consistency & goal persistence               │
│ • Perception state trajectory coherence & stability    │
│ • Behavioral action & policy alignment                 │
│ • Confidentiality compliance & memory integrity        │
│ • Cross-persona divergence (Persona Collapse detection)│
└────────────────────────────────────────────────────────┘
```

> **RESEARCH DISCLAIMER**: All simulator evaluation metrics (`overall_fidelity`, `state_coherence`, `persona_consistency`, etc.) are internal engineering benchmarks designed to assess simulation architecture improvements. They are not psychometric standards.

---

## 2. Architecture Ablation Modes

The framework supports 6 reproducible simulation modes:

| Mode | Architecture Stack | Description |
|---|---|---|
| **`STATIC_PROMPT`** | Phase 1 Raw Markdown | Original baseline: static markdown persona + unguided LLM. No client state, stage machine, policy, or memory. |
| **`PERSONA_ONLY`** | Phase 2 Structured Persona | Typed `EnterprisePersona` with profile, values, goals, incentives, and knowledge boundaries in system prompt. |
| **`PERSONA_PLUS_STATE`** | Phase 2 + Phase 3 ClientState | Adds dynamic perception state (`trust`, `skepticism`, `patience`, etc.) calibrated to candidate signals. |
| **`PERSONA_PLUS_STATE_PLUS_INTERVIEW`** | Phases 2, 3, + 4 State Machine | Adds deterministic enterprise sales conversation stages (Stage 1 to Stage 5) and stage criteria guards. |
| **`PERSONA_PLUS_STATE_PLUS_INTERVIEW_PLUS_BEHAVIOR`** | Phases 2 to 6 Policy Engine | Adds deterministic behavioral policy engine selecting canonical actions (`CHALLENGE_CLAIM`, `REQUEST_EVIDENCE`). |
| **`FULL_SIMULATOR`** | Phases 1 through 7 Complete Pipeline | Complete system with World Model immutability, role knowledge boundaries, conversational memory, and response consistency validation. |

---

## 3. Simulator Fidelity Metrics

### 1. State Coherence Metric
Evaluates the stability and directional validity of internal perception state:
- **Monotonicity**: Compares delta trajectories against scenario expectations (e.g. strong candidate $\to$ `trust` increase).
- **Oscillation Penalty**: Detects rapid sign changes (flapping) between consecutive turns without stimulus shifts.
- **Bound Clamping**: Verifies $[0.0, 1.0]$ boundary clamping integrity.

$$\text{state\_coherence} = 1.0 - (0.45 \cdot \text{osc\_ratio} + 0.45 \cdot \text{dir\_ratio} + 0.10 \cdot \text{bound\_violations})$$

### 2. Persona Consistency Metric
Measures whether the simulated executive adheres to their configured role, technical depth, and executive communication posture:
- Vocabulary frequency matching (e.g. CTO $\to$ `architecture`, `latency`, `failover`, `scale`).
- Identity preservation: penalizes AI identity leaks (`"As an AI..."`).

### 3. Goal Consistency Metric
Evaluates whether configured persona goals (e.g. security verification, cost control, migration risk) remain actively pursued across the conversation rather than being abandoned.

### 4. Behavioral Consistency Metric
Compares turn actions against declarative `ExpectedBehavior` rules:
- Checks if expected canonical action types are chosen under given candidate conditions.
- Flags and penalizes prohibited actions (e.g. `ACCEPT_PROPOSAL` during premature discovery).

### 5. Information Integrity & Memory Fidelity
- **Confidentiality Compliance**: Detects and penalizes leakage of confidential numbers (exact budget, profit margins, unannounced roadmap).
- **World Fact Consistency**: Detects contradictions with ground truth company data.
- **Memory Consistency**: Evaluates whether prior statements are maintained and candidate contradictions are detected and challenged.

### 6. Action-Response Alignment Metric
Measures whether the natural language response realization matches the policy action intent:

$$\text{action\_alignment} = \frac{\text{compatible\_behaviors}}{\text{total\_evaluated\_behaviors}}$$

### 7. Cross-Persona Divergence (Persona Collapse Detection)
Tests different personas (CTO vs CFO vs Sales Director) against identical candidate inputs. If all personas produce identical actions or responses, flags `PERSONA_COLLAPSE`.

### 8. Overall Composite Fidelity Score
Explicit engineering composite score:

$$\text{overall\_fidelity} = 0.15 \cdot \text{persona} + 0.15 \cdot \text{goal} + 0.15 \cdot \text{behavior} + 0.15 \cdot \text{state} + 0.15 \cdot \text{info} + 0.10 \cdot \text{boundary} + 0.10 \cdot \text{alignment} + 0.05 \cdot \text{memory}$$

---

## 4. Standardized Failure Categories

| Category | Description |
|---|---|
| `PERSONA_DRIFT` | Stakeholder drifts from role-specific posture, technical depth, or tone. |
| `GOAL_DRIFT` | Stakeholder abandons configured goals mid-interview. |
| `STATE_OSCILLATION` | Perception metrics oscillate erratically between turns without cause. |
| `INFORMATION_LEAK` | Confidential or forbidden internal data is disclosed to candidate. |
| `WORLD_FACT_CONTRADICTION` | Stakeholder states facts contradicting verified scenario ground truth. |
| `MEMORY_FAILURE` | Stakeholder forgets prior turns or overlooks candidate contradictions. |
| `POLICY_RESPONSE_MISMATCH` | Verbal response fails to realize the selected behavioral action directive. |
| `PERSONA_COLLAPSE` | Distinct stakeholder roles produce indistinguishable responses to identical stimuli. |
| `OVER_DISCLOSURE` | Stakeholder reveals qualified information before candidate builds required trust. |
| `UNDER_DISCLOSURE` | Stakeholder withholds public or earned information inappropriately. |
| `UNREALISTIC_ESCALATION` | Confrontation or termination intensity spikes inappropriately. |
| `ROLE_INCONSISTENCY` | Stakeholder breaks character (e.g. acknowledges being an AI model). |

---

## 5. Controlled Scenarios (Scenarios A through F)

- **Scenario A (Strong Candidate)**: Candidate demonstrates structured discovery, quantified ROI, reference architecture, and concrete migration safety $\to$ `trust` $\uparrow$, `skepticism` $\downarrow$.
- **Scenario B (Weak Candidate)**: Candidate provides vague answers, buzzword dumping, and premature pitch $\to$ `CHALLENGE_CLAIM`, `PUSH_BACK`, `frustration` $\uparrow$.
- **Scenario C (Inconsistent Candidate)**: Candidate asserts 15-minute setup at Turn 2, then asserts 45-minute setup at Turn 4 $\to$ `CHALLENGE_CLAIM`, contradiction flagged.
- **Scenario D (Confidentiality Probe)**: Candidate probes exact quarterly IT budget and internal margins $\to$ `WITHHOLD_INFORMATION`.
- **Scenario E (Technical Challenge)**: Complex multi-region claims evaluated against CTO reliability values $\to$ `PROBE_TECHNICAL_DETAIL`, `PROBE_RISK`.
- **Scenario F (High-Trust Candidate)**: Candidate provides verified SOC2 and ISO compliance reports, building trust $\to$ `trust` $\uparrow$, qualified disclosure unlocked.

---

## 6. Research Experiments (RQ1, RQ2, RQ3)

The evaluation runner provides automated execution of formal ablation experiments:

1. **RQ1 (Dynamic State Benefit)**:
   - *Question*: Does adding dynamic client state improve stakeholder behavioral consistency over structured persona prompting?
   - *Comparison*: `PERSONA_ONLY` vs `PERSONA_PLUS_STATE`.
2. **RQ2 (Behavioral Policy Benefit)**:
   - *Question*: Does explicit behavioral policy improve action-level realism?
   - *Comparison*: `PERSONA_PLUS_STATE_PLUS_INTERVIEW` vs `PERSONA_PLUS_STATE_PLUS_INTERVIEW_PLUS_BEHAVIOR`.
3. **RQ3 (Memory Governance Benefit)**:
   - *Question*: Does information/memory governance improve long-horizon consistency?
   - *Comparison*: `WITHOUT_MEMORY` vs `FULL_SIMULATOR`.

---

## 7. CLI & REST API Endpoints

### CLI Tool
```bash
# Run single scenario evaluation
python backend/scripts/run_simulation_eval.py --mode FULL_SIMULATOR --scenario SCENARIO_A_STRONG_CANDIDATE --output report.md

# Run research experiment
python backend/scripts/run_simulation_eval.py --experiment RQ1
```

### REST API
- `GET /api/evaluation/scenarios`: Lists all controlled evaluation scenarios.
- `GET /api/evaluation/modes`: Lists available architecture ablation modes.
- `POST /api/evaluation/run`: Runs evaluation on demand.
- `GET /api/evaluation/{session_id}`: Retrieves persisted simulator evaluation.
- `POST /api/evaluation/human-rating`: Submits expert human evaluation (1-5 scales + agreement).
- `GET /api/evaluation/human-ratings/{session_id}`: Retrieves human ratings for session.
- `POST /api/evaluation/experiment/{experiment_id}`: Executes RQ1, RQ2, or RQ3.
