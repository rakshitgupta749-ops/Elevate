# Elevate Candidate Behavior & Content Analyzer Architecture (Phase 5)

## Executive Summary

Phase 5 introduces the dedicated **Candidate Behavior & Content Analyzer**, transforming the Elevate client simulation engine from heuristic lexical matching into an explicit, auditable semantic analysis system.

The analyzer answers the fundamental question:
> **"What did the salesperson actually do in this turn?"**

It does **NOT** decide stakeholder behavior (Phase 6), nor does it generate stakeholder dialogue. Instead, it provides structured, typed behavioral classifications, verifiable candidate facts, and subjective candidate claims that feed deterministically into `ClientStateManager` (Phase 3) and `InterviewStateManager` (Phase 4).

---

## 1. Architectural Separation & Causal Chain

Elevate enforces strict decoupling across simulator components:

```
┌────────────────────────────────────────────────────────┐
│                   Candidate Speech                     │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ Candidate Behavior & Content Analyzer (Phase 5)        │
│ "What did the salesperson do in this turn?"            │
│ • Communication (clarity, confidence, directness)      │
│ • Sales behavior (discovery, needs, value, closing)    │
│ • Response quality (evidence-backed, evasive, claims)  │
│ • Business, technical, and commercial classifications  │
│ • Fact extraction (status: OBSERVED, CONFIRMED, etc.)  │
│ • Claim extraction (quantitative vs qualitative)       │
└───────────────────────────┬────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌───────────────────────────────┐ ┌───────────────────────────────┐
│  ClientStateManager (Phase 3) │ │ InterviewStateManager(Phase 4)│
├───────────────────────────────┤ ├───────────────────────────────┤
│ "How did that affect client   │ │ "Does this satisfy stage      │
│  internal perception?"        │ │  criteria?"                   │
│ • trust, skepticism, patience │ │ • min/max stage progression   │
│ • perceived_risk, frustration │ │ • required criteria checking  │
└───────────────────────────────┘ └───────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ Response Generator (Existing)                          │
│ "How should the stakeholder realize this in speech?"   │
└────────────────────────────────────────────────────────┘
```

### Critical Boundaries
1. **No Data Leakage**: The analyzer receives only the candidate's message, current stage, and known facts. It does **NOT** receive the stakeholder's hidden profile, private values, or internal `ClientState` (trust, patience, frustration).
2. **No Direct State Mutation**: The analyzer never directly alters numerical metrics or advances interview stages. State updates are mediated through explicit, inspectable mapping layers.
3. **Resilient Failure Fallback**: On LLM timeouts, network errors, or malformed outputs, the analyzer falls back safely to a neutral analysis (`overall_confidence=0.0`, `uncertain=True`), preventing simulation corruption.

---

## 2. Structured Analysis Schema (`CandidateTurnAnalysis`)

Defined in [`backend/app/models/analysis.py`](file:///home/labuser/Desktop/Project/Elevate/backend/app/models/analysis.py):

- **CommunicationStyleAnalysis**: `clarity`, `conciseness`, `confidence`, `professionalism`, `directness` (normalized scores `[0.0, 1.0]`).
- **SalesBehaviorAnalysis**: `discovery_question`, `needs_exploration`, `value_proposition`, `feature_dumping`, `objection_handling`, `negotiation`, `closing_attempt`, `next_step_proposal` (booleans).
- **ResponseQualityAnalysis**: `answered_question`, `evasive`, `vague`, `contradictory`, `defensive`, `proactive`, `evidence_backed`, `unsupported_claim` (booleans).
- **BusinessUnderstandingAnalysis**: `pain_identified`, `impact_identified`, `decision_criteria_explored`, `business_value_explained`, `roi_discussed` (booleans).
- **TechnicalBehaviorAnalysis**: `technical_claim`, `technical_evidence`, `architecture_explanation`, `security_discussion`, `scalability_discussion`, `implementation_discussion` (booleans).
- **CommercialBehaviorAnalysis**: `pricing_discussed`, `budget_discussed`, `procurement_discussed`, `timeline_discussed`, `commercial_expectation_defined` (booleans).
- **SemanticClassificationEvidence**: Target criterion, detected boolean, evidence quote, confidence.

---

## 3. Working Memory: Fact & Claim Ledgers

Elevate differentiates objective facts from unverified candidate claims:

### Candidate Facts (`CandidateFactLedger`)
- Verifiable information regarding customer constraints, current vendors, timelines, or discovered pain.
- Lifecycle statuses: `OBSERVED`, `CLAIMED`, `CONFIRMED`, `CONTRADICTED`, `UNKNOWN`.
- **Contradiction Preservation**: Conflicting statements (e.g. stating a 3-month rollout in Turn 2, then a 9-month rollout in Turn 6) are preserved in working memory with both entries flagged as `CONTRADICTED`.

### Candidate Claims (`CandidateClaimLedger`)
- Commercial or technical assertions made by the candidate (e.g. "We guarantee 99.99% uptime", "Platform saves 40% on costs").
- Flags whether the claim is quantitative and whether empirical evidence was provided.

---

## 4. Deterministic Mapping Layers

### Mapping to Phase 3 ClientState (`map_analysis_to_signals`)
- Supports multiple simultaneous signals per turn:
  - `unsupported_claim` -> `InteractionSignal(type="unsupported_claim")`
  - `evidence_backed` / `technical_evidence` -> `InteractionSignal(type="positive_evidence")`
  - `evasive` / `defensive` -> `InteractionSignal(type="candidate_dodges_question")`
  - `vague` -> `InteractionSignal(type="vague_response")`
  - `answered_question` (clean) -> `InteractionSignal(type="clear_answer")`
  - `pricing_discussed` with negotiation -> `InteractionSignal(type="price_concession")`
  - Uncertainty / Fallback -> `InteractionSignal(type="neutral_turn")`

### Mapping to Phase 4 Interview Criteria (`update_criteria_from_analysis`)
- **Confidence Thresholds**:
  - `High (>= 0.80)`: Satisfies required and optional stage criteria.
  - `Medium (0.60–0.79)`: Records evidence in criterion, but does **NOT** advance required criteria.
  - `Low (< 0.60)`: Ignored for progression.

---

## 5. Research Persistence & Developer API

### SQLite Table: `candidate_turn_analyses`
```sql
CREATE TABLE IF NOT EXISTS candidate_turn_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    turn_number INTEGER,
    candidate_message TEXT,
    current_stage TEXT,
    analysis_json TEXT,
    extracted_facts_json TEXT,
    extracted_claims_json TEXT,
    interaction_signals_json TEXT,
    latency_ms REAL,
    model_name TEXT,
    created_at TEXT,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);
```

### Developer Endpoint:
`GET /api/session/{session_id}/analysis-history`
Returns complete turn-by-turn candidate analyses, active fact ledgers, and claim ledgers.
