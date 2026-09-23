# Elevate Interview State Machine Architecture (Phase 4)

## Executive Summary

Phase 4 of the Elevate migration replaces the legacy flat conversation loop—which relied on static LLM system prompt instructions to ask 10 to 15 questions—with an explicit, typed, deterministic enterprise sales **Interview State Machine**.

The application runtime owns and controls the meeting lifecycle, stage progression, criteria validation, turn bounds, and completion events. The LLM is confined strictly to natural-language realization within the active stage.

---

## 1. Architectural Separation: ClientState vs. InterviewState

Elevate enforces strict decoupling between perception and meeting structure:

```
┌────────────────────────────────────────────────────────┐
│                      Candidate Turn                    │
└───────────────────────────┬────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌───────────────────────────────┐ ┌───────────────────────────────┐
│     ClientState (Phase 3)     │ │    InterviewState (Phase 4)   │
├───────────────────────────────┤ ├───────────────────────────────┤
│ "How the stakeholder perceives│ │ "Where the meeting is         │
│  and reacts to the candidate" │ │  structurally in its life"    │
│                               │ │                               │
│ • trust                       │ │ • current_stage               │
│ • skepticism                  │ │ • stage_turn_count            │
│ • patience                    │ │ • total_turn_count            │
│ • engagement                  │ │ • max_total_turns             │
│ • interest                    │ │ • criteria satisfaction       │
│ • perceived_risk              │ │ • status (ACTIVE/COMPLETED...)│
│ • frustration                 │ │ • auditable transition events │
│ • confidence_in_candidate     │ │ • termination_reason          │
└───────────────────────────────┘ └───────────────────────────────┘
```

Neither state model pollutes or inherits from the other. Both evolve independently on each interaction turn.

---

## 2. The 5 Enterprise Sales Stages

```
STAGE_1_OPENING_RAPPORT
        │ (min 1, max 3 turns; required: rapport_established)
        ▼
STAGE_2_PROBLEM_DISCOVERY
        │ (min 3, max 8 turns; required: business_pain_identified)
        ▼
STAGE_3_SOLUTION_ALIGNMENT
        │ (min 2, max 6 turns; required: solution_linked_to_pain)
        ▼
STAGE_4_OBJECTIONS_AND_DEEP_DIVE
        │ (min 2, max 8 turns; required: technical_risk_probed)
        ▼
STAGE_5_COMMERCIALS_AND_CLOSING
        │ (min 2, max 5 turns; required: commercial_expectations_clarified, next_steps_agreed)
        ▼
    COMPLETED
```

### Stage Summary Table

| Stage ID | Name | Objective | Min Turns | Max Turns | Required Criteria |
|---|---|---|---|---|---|
| `STAGE_1_OPENING_RAPPORT` | Opening & Rapport | Establish context, understand purpose, allow candidate intro | 1 | 3 | `rapport_established` |
| `STAGE_2_PROBLEM_DISCOVERY` | Problem Discovery | Identify business pain, workflow challenges, impact, criteria | 3 | 8 | `business_pain_identified` |
| `STAGE_3_SOLUTION_ALIGNMENT` | Solution Alignment | Map solution to discovered pain; establish technical & value fit | 2 | 6 | `solution_linked_to_pain` |
| `STAGE_4_OBJECTIONS_AND_DEEP_DIVE` | Objections & Deep Dive | Probe implementation risks, challenge assumptions, test credibility | 2 | 8 | `technical_risk_probed` |
| `STAGE_5_COMMERCIALS_AND_CLOSING` | Commercials & Closing | Discuss commercial model, pricing, decision timeline, next steps | 2 | 5 | `commercial_expectations_clarified`, `next_steps_agreed` |

---

## 3. Transition Rules Engine (`InterviewStateManager`)

Stage transitions are evaluated deterministically in `InterviewStateManager.evaluate_stage_transition()`:

1. **Max Total Turns Limit**: If `total_turn_count >= max_total_turns` (default: 15), status becomes `COMPLETED`.
2. **Early Termination (Dealbreaker / Risk)**: If `client_state.frustration >= 0.95` and `client_state.patience <= 0.10`, status becomes `TERMINATED`.
3. **Criteria Progression**: If `stage_turn_count >= min_turns` AND all required criteria for the stage are satisfied, advance to the next stage.
4. **Max Stage Turns Failsafe**: If `stage_turn_count >= max_turns`, the system advances to the next stage automatically to prevent deadlocks.
5. **Premature Pitch Guard**: In `STAGE_2_PROBLEM_DISCOVERY`, solution pitches cannot trigger progression if `business_pain_identified` is unsatisfied. The prompt instructs the stakeholder to demand business context first.

---

## 4. LangGraph Flow Integration

`AgentState` is typed with primitives for checkpointer serialization safety:

```python
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    is_finished: bool
    client_state: dict
    state_events: Annotated[List[dict], operator.add]
    turn_count: int
    interview_state: dict
    interview_events: Annotated[List[dict], operator.add]
```

On each turn inside `_interviewer_node`:
1. `InterviewState` is hydrated from `state["interview_state"]`.
2. `InterviewState` context is formatted into system prompt via `PromptBuilder`.
3. LLM invokes within stage boundaries.
4. Candidate turn updates criteria heuristically.
5. `InterviewStateManager.evaluate_stage_transition()` determines progression.
6. Stage transition events are persisted to SQLite table `interview_stage_events`.

---

## 5. Persistence & Developer Inspection API

### SQLite Table: `interview_stage_events`

```sql
CREATE TABLE IF NOT EXISTS interview_stage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    turn_number INTEGER,
    from_stage TEXT,
    to_stage TEXT,
    reason TEXT,
    created_at TEXT,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);
```

### Inspection Endpoint:
`GET /api/session/{session_id}/interview-history`

```json
{
  "session_id": "test-session-uuid",
  "current_stage": "STAGE_2_PROBLEM_DISCOVERY",
  "stage_turn_count": 2,
  "total_turn_count": 3,
  "status": "ACTIVE",
  "criteria": {
    "rapport_established": {
      "id": "rapport_established",
      "name": "Candidate Introduction & Rapport",
      "required": true,
      "satisfied": true,
      "satisfied_at_turn": 1,
      "evidence": "Candidate established opening rapport"
    },
    "business_pain_identified": {
      "id": "business_pain_identified",
      "name": "Core Business Pain Identified",
      "required": true,
      "satisfied": false,
      "satisfied_at_turn": null,
      "evidence": null
    }
  },
  "history": [
    {
      "turn": 1,
      "from_stage": "STAGE_1_OPENING_RAPPORT",
      "to_stage": "STAGE_2_PROBLEM_DISCOVERY",
      "reason": "Required criteria satisfied for Opening & Rapport and minimum stage turns (1) reached.",
      "created_at": "2026-09-14T04:36:00.000000"
    }
  ]
}
```
