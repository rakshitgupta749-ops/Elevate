# Elevate Information & Memory Layer Architecture (Phase 7)

## Executive Summary

Phase 7 introduces the **Information & Memory Layer**, answering the fundamental conversational integrity question:
> **"What does this stakeholder know, remember, believe, have been told, and have permission to disclose at this point in the conversation?"**

In long enterprise sales simulations, LLMs without deterministic memory and knowledge governance suffer from:
1. **Fact drift**: Inconsistent company headcount, budget figures, tech stack details, or timelines emerging mid-conversation.
2. **Confidentiality leaks**: Stakeholders prematurely disclosing confidential margins, internal roadmaps, or unapproved pricing.
3. **Amnesia**: Forgetting prior commitments, unanswered objections, or earlier claims made by the candidate.
4. **Silent overwrite of candidate contradictions**: When a candidate changes their story (e.g., claiming 99.9% SLA and later stating 99.999%), naive systems overwrite the state rather than preserving the contradiction for strategic behavioral exploitation.

Phase 7 implements deterministic, inspectable, and auditable memory governance while maintaining zero breaking changes to existing endpoints and test suites.

---

## 1. Architectural Separation & Causal Chain

The Elevate simulator implements an explicit, multi-stage causal pipeline:

```text
Candidate Speech
      │
      ▼
┌────────────────────────────────────────────────────────┐
│ Phase 5: Candidate Behavior & Content Analyzer        │
│ "What did the salesperson do and claim in this turn?"  │
│ (Signals, extracted facts, extracted claims)           │
└───────────────────────────┬────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
┌───────────────────┐ ┌───────────┐ ┌───────────────────────────┐
│ Phase 3:          │ │ Phase 4:  │ │ Phase 7:                  │
│ ClientStateManager│ │ Interview │ │ ConversationalMemoryStore │
│ "Perception       │ │ State     │ │ • Ingest candidate turn   │
│  evolution"       │ │ Machine   │ │ • Contradiction detection │
│ (trust, risk, etc)│ │ (stages)  │ │ • Track commitments/inq   │
└─────────┬─────────┘ └─────┬─────┘ └─────────────┬─────────────┘
          │                 │                     │
          └────────┬────────┴─────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 6: Behavioral Policy Engine                               │
│ "What should the simulated stakeholder DO next?"                │
│ (Selects action, target topic, intensity, disclosure intent)    │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 7: Knowledge Governance & Access Decision                 │
│ • Check StakeholderKnowledgeState against topic & trust level   │
│ • Policy Override: If policy proposes REVEAL_INFORMATION but   │
│   stakeholder lacks permission or trust is insufficient,        │
│   override action to WITHHOLD_INFORMATION                       │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 7: Deterministic Memory Retrieval                         │
│ • Query ConversationalMemoryStore for relevant items            │
│ • Retrieve unresolved inquiries & active commitments            │
│ • Format KNOWLEDGE & MEMORY prompt directives                   │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ Response Generation (LLM)                                       │
│ Generates draft response conforming strictly to policy & bounds │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 7: Response Consistency Validator                         │
│ • Check draft for confidential leaks, fact contradictions,      │
│   and policy action alignment                                   │
│ • If valid: Accept and emit response                            │
│ • If invalid: Trigger 1 corrective repair retry with feedback   │
│ • If retry fails: Deterministic safe fallback generation        │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
Final Validated Stakeholder Response + SQLite Persistence
```

---

## 2. Core Data Models

Defined in `backend/app/models/memory.py`:

### Knowledge Governance Models
- **`KnowledgeStatus`**: `CONFIRMED`, `UNCONFIRMED`, `PROPOSED`, `REFUTED`.
- **`InformationSource`**: `WORLD_MODEL`, `PERSONA_KNOWLEDGE`, `STAKEHOLDER_DISCLOSURE`, `CANDIDATE_CLAIM`, `INTERVIEW_OBSERVATION`.
- **`DisclosureLevel`**:
  - `PUBLIC`: Freely disclosable at any time.
  - `SHARED_UPON_REQUEST`: Shared if candidate asks appropriately.
  - `QUALIFIED_ONLY`: Requires candidate to build minimum trust (default threshold: 0.60).
  - `CONFIDENTIAL`: Strictly restricted; requires high trust (default threshold: 0.85).
  - `FORBIDDEN`: Never disclosed in this interview under any circumstances.
- **`StakeholderKnowledgeItem`**:
  - `knowledge_id`, `topic`, `content`, `category`, `status`, `source`, `disclosure_level`, `disclosed_to_candidate`, `first_disclosed_turn`, `disclosure_count`, `provenance`.
- **`KnowledgeAccessDecision`**:
  - `topic`, `permitted` / `allowed`, `disclosure_level`, `reason`, `authorized_content`.
- **`WorldFact`**:
  - `fact_id`, `domain`, `key`, `value`, `data_type`, `immutable`, `source`.

### Conversational Memory Models
- **`MemoryType`**:
  - `CANDIDATE_STATEMENT`: Factual claims or statements made by candidate.
  - `CANDIDATE_COMMITMENT`: Promises or commitments made by candidate.
  - `STAKEHOLDER_STATEMENT`: Statements made by the simulated client.
  - `STAKEHOLDER_COMMITMENT`: Commitments made by stakeholder.
  - `CONTRADICTION`: Conflicting statements identified across turns.
  - `UNRESOLVED_QUESTION`: Inquiries requiring answers.
  - `UNRESOLVED_OBJECTION`: Concerns raised that have not been adequately mitigated.
- **`MemoryItem`**:
  - `memory_id`, `turn_number`, `speaker`, `memory_type`, `content`, `entities`, `retrieval_tags`, `importance_score`, `verified`.
- **`StakeholderCommitment`**:
  - `commitment_id`, `created_turn`, `description`, `condition`, `status` (`ACTIVE`, `FULFILLED`, `BROKEN`).
- **`UnresolvedQuestion`** & **`UnresolvedObjection`**:
  - Track open stakeholder questions and objections, target topics, and resolution turn numbers.
- **`ConsistencyValidationResult`**:
  - `is_valid`, `violations`, `violation_type`, `corrective_instructions`, `fallback_response`.

---

## 3. Knowledge Governance & Immutability

### `WorldFactRegistry`
1. **Scenario Ground Truth**: Built from `EnterprisePersona.company_context` (e.g. `company_name`, `company_size`, `industry`, `target_market`).
2. **Strict Immutability**:
   - Updates to existing keys with conflicting values raise `ValueError("Cannot modify immutable world fact ...")`.
   - Idempotent updates (identical key/value) are permitted.
3. **Contradiction Detection**:
   - `check_contradiction(key, candidate_value)` and `check_statement_contradiction(candidate_text)` evaluate candidate assertions against immutable facts.

### `StakeholderKnowledgeState`
1. **Role-Bounded Knowledge**:
   - Distinguishes topics known vs. unknown to the specific stakeholder role (e.g., CTO knows tech stack & security architecture; CFO knows procurement budgets and financial hurdle rates).
2. **Deterministic Access Evaluation (`evaluate_access`)**:
   - Inspects topic against role knowledge items.
   - If topic is not in role knowledge: Access DENIED (`"Topic is outside stakeholder's knowledge boundaries"`).
   - If topic is `FORBIDDEN`: Access DENIED (`"Topic is forbidden from disclosure"`).
   - If topic is `CONFIDENTIAL`: Requires candidate trust >= 0.85.
   - If topic is `QUALIFIED_ONLY`: Requires candidate trust >= 0.60.
   - If topic is `SHARED_UPON_REQUEST` or `PUBLIC`: Access GRANTED.
3. **Policy Engine Override**:
   - If Phase 6 policy generates `REVEAL_INFORMATION` for an unauthorized or unearned topic, the pipeline intercepts and overrides the action to `WITHHOLD_INFORMATION`.

---

## 4. Conversational Memory Store & Contradiction Handling

### Ingestion Lifecycle
- **Candidate Turn Ingestion**:
  - Candidate text is ingested as a `CANDIDATE_STATEMENT` memory item.
  - Extracted claims/facts from Phase 5 analyzer are added to memory.
  - Regex-based numerical contradiction detection extracts metrics (e.g., SLA percentages, pricing dollars, implementation weeks, team sizes).
- **Contradiction Preservation**:
  - When candidate claims differ from prior claims (e.g., "15 minutes" vs. "45 minutes"), **neither turn is overwritten**.
  - Both original memory items remain intact in the ledger.
  - A new `CONTRADICTION` memory item is generated referencing both turns and the conflicting values.
  - The Behavioral Policy Engine can leverage this contradiction item to fire `CHALLENGE_CLAIM` or `EXPRESS_SKEPTICISM`.
- **Stakeholder Turn Ingestion**:
  - Stakeholder responses are stored as `STAKEHOLDER_STATEMENT` memory items.
  - Commitments (e.g., "I will follow up with security team") are registered with `ACTIVE` status.

---

## 5. Selective Memory Retrieval

The `MemoryRetriever` deterministically selects memories to inject into the response prompt without polluting token context:
1. **Recency + Importance Scoring**:
   - Base importance score (1 to 5) assigned by memory type (`CONTRADICTION` = 5, `COMMITMENT` = 4, `STATEMENT` = 2).
   - Linear recency decay: Items from recent turns receive a recency boost.
2. **Topic Relevance Matching**:
   - Matches candidate keywords and policy target topics against `retrieval_tags` and entities.
3. **Budget & Limit Clamping**:
   - Retrieves top $K$ items (default 5) sorted by score.
   - Filters out redundant or outdated non-contradiction items.

---

## 6. Response Consistency Validator & Repair Loop

Before any LLM-generated stakeholder response is emitted, it passes through `ResponseConsistencyValidator`:

1. **Validation Checks**:
   - **Confidentiality Check**: Detects if prohibited confidential topics or metrics were leaked.
   - **Immutable World Fact Check**: Ensures the stakeholder does not state false facts about their own company (e.g., wrong size or industry).
   - **Policy Action Alignment**: Confirms the response style matches the directive (e.g., if action is `WITHHOLD_INFORMATION`, ensures response does not say "Here is our full budget").
2. **Retry Repair Loop**:
   - If a violation is detected on attempt 1, the pipeline issues a second generation call with explicit `CORRECTIVE REPAIR INSTRUCTIONS`.
3. **Deterministic Fallback Generator**:
   - If the second attempt fails or an unrecoverable exception occurs, a safe, persona-aligned fallback is generated:
     - E.g., for `WITHHOLD_INFORMATION`: *"I cannot share internal details on that right now. Let's keep our focus on your technical capabilities."*
     - E.g., for `CHALLENGE_CLAIM`: *"That doesn't align with what we typically see or what you noted earlier. What concrete data backs that up?"*

---

## 7. Storage Schema & SQLite Persistence

Implemented in `backend/app/services/storage_service.py` with 5 dedicated tables:

```sql
CREATE TABLE IF NOT EXISTS knowledge_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    knowledge_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    disclosure_level TEXT NOT NULL,
    disclosed_to_candidate INTEGER NOT NULL DEFAULT 0,
    first_disclosed_turn INTEGER,
    disclosure_count INTEGER NOT NULL DEFAULT 0,
    provenance TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, knowledge_id)
);

CREATE TABLE IF NOT EXISTS memory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    memory_id TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    speaker TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    entities_json TEXT,
    tags_json TEXT,
    importance_score REAL NOT NULL DEFAULT 1.0,
    verified INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, memory_id)
);

CREATE TABLE IF NOT EXISTS stakeholder_commitments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    commitment_id TEXT NOT NULL,
    created_turn INTEGER NOT NULL,
    description TEXT NOT NULL,
    condition TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    fulfilled_turn INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, commitment_id)
);

CREATE TABLE IF NOT EXISTS unresolved_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    item_type TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    text TEXT NOT NULL,
    target_topic TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN',
    resolution_turn INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, item_id)
);

CREATE TABLE IF NOT EXISTS consistency_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    is_valid INTEGER NOT NULL,
    violation_type TEXT,
    violations_json TEXT,
    repair_attempted INTEGER NOT NULL DEFAULT 0,
    fallback_used INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 8. Inspection Endpoints

Three developer and test audit endpoints are exposed under `/api/session`:

| Endpoint | Method | Description |
|---|---|---|
| `/api/session/{session_id}/memory` | `GET` | Returns full memory store: `memories`, `commitments`, `unresolved_questions`, `unresolved_objections`, `contradictions`. |
| `/api/session/{session_id}/knowledge` | `GET` | Returns stakeholder knowledge state: `disclosed_items`, `undisclosed_items`, `all_items`. |
| `/api/session/{session_id}/consistency-history` | `GET` | Returns history of validation events: `events`, `total_events`, `violations_count`. |

---

## 9. Verification & Regression Results

All 93 tests across the entire test suite pass with 100% success rate:

- `test_memory_knowledge.py`: 17 passed (100% Phase 7 tests)
- `test_behavior_policy.py`: 16 passed (Phase 6)
- `test_candidate_analyzer.py`: 15 passed (Phase 5)
- `test_interview_state_machine.py`: 15 passed (Phase 4)
- `test_client_state.py`: 14 passed (Phase 3)
- `test_persona_models.py`: 16 passed (Phase 2)
- **Total**: 93 passed, 0 failures.
