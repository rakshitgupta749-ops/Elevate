# Elevate Behavioral Policy Engine Architecture (Phase 6)

## Executive Summary

Phase 6 introduces the dedicated **Behavioral Policy Engine**, answering the central behavioral simulation question:
> **"Given who this stakeholder is, what they value, what they want, the current interview stage, what the salesperson just did, and how the stakeholder currently perceives the salesperson — what should the stakeholder do next?"**

The Behavioral Policy Engine decides the simulated stakeholder's **next behavioral action** (e.g. `CHALLENGE_CLAIM`, `target="ROI"`, `intensity=0.82`, `information_to_withhold=["budget"]`).

It does **NOT** generate natural-language dialogue. Natural language realization remains the exclusive responsibility of the downstream LLM response generator, which operates under strict mandatory instructions derived from the policy decision.

---

## 1. Architectural Separation & Causal Chain

The Elevate simulator maintains an explicit, inspectable, turn-by-turn causal chain:

```text
Candidate Speech
      │
      ▼
┌────────────────────────────────────────────────────────┐
│ Phase 5: Candidate Behavior & Content Analyzer        │
│ "What did the salesperson do in this turn?"            │
│ (Semantic signals, extracted facts, extracted claims)  │
└───────────────────────────┬────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌───────────────────────────────┐ ┌───────────────────────────────┐
│ Phase 3: ClientStateManager   │ │ Phase 4: InterviewStateManager│
│ "How did client perception    │ │ "What stage are we in and     │
│  shift?"                      │ │  have criteria been met?"     │
│ (trust, skepticism, patience, │ │ (STAGE_1 through STAGE_5,     │
│  frustration, perceived_risk) │ │  lifecycle status, criteria)  │
└───────────────────────┬───────┘ └───────┬───────────────────────┘
                        │                 │
                        └────────┬────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 6: Behavioral Policy Engine (Deterministic & Inspectable) │
│ "What should the simulated stakeholder DO next?"                │
│ • Persona values, goals, incentives, knowledge boundaries       │
│ • Dynamic ClientState metrics                                   │
│ • Active InterviewStage & stage criteria                        │
│ • Candidate signals from Turn Analysis                          │
│ • Deterministic priority hierarchy (Dealbreaker > Safety >      │
│   Goal > Signal > Stage Default)                                │
│ • Explicit action intensity calculation [0.0, 1.0]              │
│ • Primary action + optional secondary action                    │
│ • Auditable PolicyTrace & SQLite persistence                    │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 6 Response Directives Injection                           │
│ • SELECTED BEHAVIOR: action, target, intensity, objective       │
│ • DISCLOSURE RULES: information_to_reveal / withhold            │
│ • MANDATORY CONSTRAINTS: LLM cannot alter action or leak state  │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ Existing Response Generator (LLM)                               │
│ "How does that behavioral action sound in executive speech?"    │
└─────────────────────────────────────────────────────────────────┘
```

### Critical Boundaries
1. **Zero Policy Hallucination**: The response generator LLM cannot decide or alter the stakeholder's behavioral action. It receives explicit execution directives.
2. **Sub-Millisecond Evaluation**: No expensive LLM calls are used for policy selection. Policies are evaluated deterministically in pure Python (<1ms).
3. **Information Asymmetry Guarantee**: Knowledge boundaries established in Phase 2 are strictly audited. Confidential topics (budget, internal margins, unannounced features) automatically enforce `WITHHOLD_INFORMATION`.
4. **Inspectable Policy Trace**: Every turn generates an auditable `PolicyTrace` capturing candidate signals, activated persona values, active goals, state snapshots, matched rules, selected action, intensity, and latency.

---

## 2. Behavioral Action Schema

Stakeholder actions are drawn from a 26-action canonical vocabulary:

```python
class ActionType(str, Enum):
    # Inquiries & Follow-ups
    ASK_QUESTION = "ASK_QUESTION"
    FOLLOW_UP = "FOLLOW_UP"
    REQUEST_CLARIFICATION = "REQUEST_CLARIFICATION"
    SUMMARIZE = "SUMMARIZE"

    # Challenges & Probes
    CHALLENGE_CLAIM = "CHALLENGE_CLAIM"
    REQUEST_EVIDENCE = "REQUEST_EVIDENCE"
    PROBE_RISK = "PROBE_RISK"
    PROBE_TECHNICAL_DETAIL = "PROBE_TECHNICAL_DETAIL"
    PROBE_BUSINESS_VALUE = "PROBE_BUSINESS_VALUE"
    PROBE_IMPLEMENTATION = "PROBE_IMPLEMENTATION"
    PROBE_SECURITY = "PROBE_SECURITY"
    PROBE_SCALABILITY = "PROBE_SCALABILITY"
    CHALLENGE_PRICING = "CHALLENGE_PRICING"

    # Reactions & Dispositions
    EXPRESS_INTEREST = "EXPRESS_INTEREST"
    EXPRESS_CONCERN = "EXPRESS_CONCERN"
    EXPRESS_SKEPTICISM = "EXPRESS_SKEPTICISM"
    ACKNOWLEDGE_POINT = "ACKNOWLEDGE_POINT"
    CONCEDE_POINT = "CONCEDE_POINT"
    PUSH_BACK = "PUSH_BACK"
    REDIRECT = "REDIRECT"
    INTERRUPT = "INTERRUPT"

    # Information Disclosure
    WITHHOLD_INFORMATION = "WITHHOLD_INFORMATION"
    REVEAL_INFORMATION = "REVEAL_INFORMATION"

    # Conversation Flow & Stage Progression
    MOVE_FORWARD = "MOVE_FORWARD"
    CLOSE = "CLOSE"
    TERMINATE = "TERMINATE"
```

### `BehavioralAction` Data Model

```json
{
  "action_type": "CHALLENGE_CLAIM",
  "target": "ROI",
  "intensity": 0.82,
  "objective": "test_business_claim",
  "trigger": "unsupported_quantitative_claim",
  "reason": "Candidate made an unverified quantitative claim regarding ROI while stakeholder skepticism is active (0.85).",
  "required_information": ["proof_for_ROI"],
  "information_to_reveal": [],
  "information_to_withhold": [],
  "expected_effect": "compel_candidate_to_provide_verifiable_metrics"
}
```

---

## 3. Deterministic Priority Resolution

The engine resolves competing policies across five strict priority tiers:

| Priority Tier | Tier Name | Conditions / Triggers | Canonical Action |
|:---|:---|:---|:---|
| **Tier 100** | Termination & Dealbreakers | Critical frustration $\ge 0.95$ | `TERMINATE` |
| **Tier 95** | Dealbreaker Goal Violation | Unresolved dealbreaker goal under high scrutiny | `PUSH_BACK` + `TERMINATE` |
| **Tier 90** | Safety & Confidentiality | Candidate probes confidential topics (budget, margins) | `WITHHOLD_INFORMATION` |
| **Tier 70** | Critical Unresolved Goals | Active evaluation goal (security compliance, integration) | `PROBE_SECURITY`, `PROBE_TECHNICAL_DETAIL` |
| **Tier 50** | Candidate Behavior Reactions | Phase 5 semantic signals (unsupported claim, positive evidence, dodged question) | `CHALLENGE_CLAIM`, `ACKNOWLEDGE_POINT`, `PUSH_BACK`, `REVEAL_INFORMATION` |
| **Tier 10** | Stage Defaults | Stage governance fallback for active conversation stage | `ASK_QUESTION`, `PROBE_RISK`, `MOVE_FORWARD` |

### Deterministic Tie-Breaking
When multiple policies match within the same tier:
1. Calculate match score: $\text{tier} \times 100 + \sum (\text{persona value weight} \times \text{policy affinity}) \times 5.0$.
2. For example, a candidate making an unverified security claim scores higher under a CTO persona (security value = 0.95) than a general technical claim.
3. If match scores tie exactly, resolve deterministically using alphabetical sort on `policy.id`. No random selection occurs.

---

## 4. State-Aware Action Intensity Formulation

Action intensity ($0.0 \le \text{intensity} \le 1.0$) governs the strength, firmness, and pressure of the stakeholder's reaction:

* **Challenging / Adversarial Actions** (`CHALLENGE_CLAIM`, `REQUEST_EVIDENCE`, `PUSH_BACK`, `PROBE_RISK`, `WITHHOLD_INFORMATION`, `TERMINATE`):
  $$\text{intensity} = 0.50 + 0.35 \times \text{skepticism} + 0.30 \times \text{frustration} + 0.15 \times \text{perceived\_risk} - 0.25 \times \text{trust} + \text{risk\_modifier}$$
  *(Risk-averse personas add $+0.08$)*

* **Cooperative / Receptive Actions** (`REVEAL_INFORMATION`, `EXPRESS_INTEREST`, `ACKNOWLEDGE_POINT`, `CONCEDE_POINT`, `MOVE_FORWARD`, `CLOSE`):
  $$\text{intensity} = 0.50 + 0.30 \times \text{trust} + 0.20 \times \text{interest} - 0.25 \times \text{skepticism} - 0.25 \times \text{frustration}$$

* **Probing / Inquiries** (`PROBE_TECHNICAL_DETAIL`, `PROBE_SECURITY`, `PROBE_BUSINESS_VALUE`, `ASK_QUESTION`, `FOLLOW_UP`):
  $$\text{intensity} = 0.50 + 0.20 \times \text{engagement} + 0.15 \times \text{skepticism} - 0.10 \times \text{trust}$$

Intensity is clamped strictly to $[0.05, 0.98]$.

---

## 5. Persistence & Developer Inspection API

### SQLite Persistence
Decisions are persisted into `behavior_decisions`:
```sql
CREATE TABLE IF NOT EXISTS behavior_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    turn_number INTEGER,
    action TEXT,
    secondary_action TEXT,
    target TEXT,
    intensity REAL,
    objective TEXT,
    trigger TEXT,
    reason TEXT,
    policy_id TEXT,
    trace_json TEXT,
    created_at TEXT,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);
```

### Developer Inspection API
* `GET /api/session/{session_id}/behavior-history`:
  Returns chronological turn-by-turn behavioral actions, secondary actions, targets, intensities, policy IDs, and complete audit traces for research verification.

---

## 6. Research Experiment & Ablation Support

The engine supports the `POLICY_MODE` parameter:
* `POLICY_MODE = "rule_based"`: Active policy engine injecting mandatory behavioral directives.
* `POLICY_MODE = "disabled"`: Pass-through baseline mode where the policy engine logs neutral metadata without constraining the response generator prompt.
