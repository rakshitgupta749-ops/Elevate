import sqlite3
import os
import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, List, Dict, Optional

class StorageService:
    def __init__(self):
        self.storage_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage")
        os.makedirs(self.storage_dir, exist_ok=True)
        self.db_file = os.path.join(self.storage_dir, "elevate.db")
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_file, timeout=30.0)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA busy_timeout=30000;")
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    topic TEXT,
                    role TEXT,
                    scenario TEXT,
                    experience TEXT,
                    style TEXT,
                    created_at TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    sender TEXT,
                    message TEXT,
                    timestamp TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    report TEXT,
                    created_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scorecards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE,
                    scorecard_json TEXT,
                    created_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS state_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    turn_number INTEGER,
                    state_json TEXT,
                    event_type TEXT,
                    event_reason TEXT,
                    created_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interview_stage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    turn_number INTEGER,
                    from_stage TEXT,
                    to_stage TEXT,
                    reason TEXT,
                    created_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            ''')
            cursor.execute('''
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
                )
            ''')
            cursor.execute('''
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
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS knowledge_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    topic TEXT,
                    value_text TEXT,
                    status TEXT,
                    source TEXT,
                    confidence REAL,
                    disclosure_level TEXT,
                    turn_number INTEGER,
                    provenance TEXT,
                    created_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS memory_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    memory_id TEXT,
                    memory_type TEXT,
                    topic TEXT,
                    content TEXT,
                    source_turn INTEGER,
                    importance REAL,
                    confidence REAL,
                    tags_json TEXT,
                    metadata_json TEXT,
                    created_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stakeholder_commitments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    commitment_id TEXT,
                    commitment_type TEXT,
                    description TEXT,
                    status TEXT,
                    source_turn INTEGER,
                    fulfilled_at_turn INTEGER,
                    created_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS unresolved_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    item_id TEXT,
                    item_type TEXT,
                    topic TEXT,
                    content TEXT,
                    status TEXT,
                    severity REAL,
                    source_turn INTEGER,
                    resolved_at_turn INTEGER,
                    created_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS consistency_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    turn_number INTEGER,
                    violation_type TEXT,
                    violation_details TEXT,
                    repaired INTEGER,
                    created_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS simulator_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    scenario_id TEXT NOT NULL,
                    persona_id TEXT NOT NULL,
                    architecture_mode TEXT NOT NULL,
                    persona_consistency REAL NOT NULL,
                    goal_consistency REAL NOT NULL,
                    behavior_consistency REAL NOT NULL,
                    state_coherence REAL NOT NULL,
                    information_consistency REAL NOT NULL,
                    knowledge_boundary_compliance REAL NOT NULL,
                    action_response_alignment REAL NOT NULL,
                    memory_consistency REAL NOT NULL,
                    overall_fidelity REAL NOT NULL,
                    persona_collapse_score REAL DEFAULT 0.0,
                    evaluation_method TEXT,
                    failure_categories_json TEXT,
                    evaluation_json TEXT,
                    created_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS human_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    evaluator_id TEXT NOT NULL,
                    role_authenticity INTEGER NOT NULL,
                    behavior_realism INTEGER NOT NULL,
                    question_realism INTEGER NOT NULL,
                    objection_realism INTEGER NOT NULL,
                    state_evolution INTEGER NOT NULL,
                    information_realism INTEGER NOT NULL,
                    stakeholder_goal_consistency INTEGER NOT NULL,
                    overall_realism INTEGER NOT NULL,
                    free_text_feedback TEXT,
                    behavioral_agreement_json TEXT,
                    created_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS persona_configurations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE,
                    role TEXT NOT NULL,
                    preset TEXT,
                    traits_json TEXT NOT NULL,
                    scenario_overrides_json TEXT,
                    persona_schema_version TEXT DEFAULT '1.0',
                    created_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            ''')
            conn.commit()

    def save_session(self, session_id: str, topic: str, role: str, scenario: str, experience: str, style: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sessions (id, topic, role, scenario, experience, style, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (session_id, topic, role, scenario, experience, style, datetime.now().isoformat()))
            conn.commit()

    def get_session(self, session_id: str) -> Optional[dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, topic, role, scenario, experience, style, created_at
                FROM sessions WHERE id = ?
            ''', (session_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "topic": row[1],
                    "role": row[2],
                    "scenario": row[3],
                    "experience": row[4],
                    "style": row[5],
                    "created_at": row[6],
                }
            return None

    def list_sessions(self, limit: int = 50) -> List[dict]:
        """List all previous sessions with interaction counts and evaluation outcomes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.id, s.topic, s.role, s.scenario, s.experience, s.style, s.created_at,
                       COUNT(i.id) as interaction_count,
                       e.report
                FROM sessions s
                LEFT JOIN interactions i ON s.id = i.session_id
                LEFT JOIN (
                    SELECT session_id, report
                    FROM evaluations
                    WHERE id IN (SELECT MAX(id) FROM evaluations GROUP BY session_id)
                ) e ON s.id = e.session_id
                GROUP BY s.id
                ORDER BY s.created_at DESC
                LIMIT ?
            ''', (limit,))
            results = []
            for r in cursor.fetchall():
                overall_score = None
                verdict = None
                has_eval = False
                if r[8]:
                    has_eval = True
                    try:
                        eval_data = json.loads(r[8])
                        if isinstance(eval_data, dict):
                            overall_score = eval_data.get("overall_score")
                            verdict = eval_data.get("outcome_verdict")
                    except Exception:
                        pass
                results.append({
                    "id": r[0],
                    "topic": r[1],
                    "role": r[2],
                    "scenario": r[3],
                    "experience": r[4],
                    "style": r[5],
                    "created_at": r[6],
                    "turn_count": max(0, (r[7] or 0) // 2),
                    "has_evaluation": has_eval,
                    "overall_score": overall_score,
                    "outcome_verdict": verdict,
                })
            return results

    def get_interactions(self, session_id: str) -> List[dict]:
        """Retrieve all interactions for a session in chronological order."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, sender, message, timestamp
                FROM interactions
                WHERE session_id = ?
                ORDER BY id ASC
            ''', (session_id,))
            return [
                {"id": r[0], "sender": r[1], "message": r[2], "timestamp": r[3]}
                for r in cursor.fetchall()
            ]

    def get_evaluation(self, session_id: str) -> Optional[dict]:
        """Retrieve stored evaluation report for a session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT report, created_at FROM evaluations
                WHERE session_id = ?
                ORDER BY id DESC LIMIT 1
            ''', (session_id,))
            row = cursor.fetchone()
            if row:
                try:
                    data = json.loads(row[0])
                    if isinstance(data, dict):
                        return data
                    return {"markdown_report": str(data), "created_at": row[1]}
                except Exception:
                    return {"markdown_report": row[0], "created_at": row[1]}
            return None

    def rewind_last_turn(self, session_id: str) -> bool:
        """Roll back the last turn's interactions, snapshot, and analysis in SQLite."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Fetch last interaction sender and id (delete up to 2: latest ai message + user message)
            cursor.execute('''
                SELECT id, sender FROM interactions
                WHERE session_id = ?
                ORDER BY id DESC LIMIT 2
            ''', (session_id,))
            rows = cursor.fetchall()
            if not rows:
                return False
            ids_to_del = [r[0] for r in rows]
            cursor.execute(f'''
                DELETE FROM interactions WHERE id IN ({','.join(['?']*len(ids_to_del))})
            ''', ids_to_del)

            # Delete the latest state snapshot
            cursor.execute('''
                SELECT id FROM state_snapshots
                WHERE session_id = ?
                ORDER BY id DESC LIMIT 1
            ''', (session_id,))
            snap_row = cursor.fetchone()
            if snap_row:
                cursor.execute('DELETE FROM state_snapshots WHERE id = ?', (snap_row[0],))

            # Delete the latest candidate analysis
            cursor.execute('''
                SELECT id FROM candidate_turn_analyses
                WHERE session_id = ?
                ORDER BY id DESC LIMIT 1
            ''', (session_id,))
            ana_row = cursor.fetchone()
            if ana_row:
                cursor.execute('DELETE FROM candidate_turn_analyses WHERE id = ?', (ana_row[0],))

            conn.commit()
            return True

    def save_interaction(self, session_id: str, sender: str, message: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO interactions (session_id, sender, message, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (session_id, sender, message, datetime.now().isoformat()))
            conn.commit()

    def save_evaluation(self, session_id: str, report: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO evaluations (session_id, report, created_at)
                VALUES (?, ?, ?)
            ''', (session_id, report, datetime.now().isoformat()))
            conn.commit()

    def save_scorecard(self, session_id: str, scorecard: dict):
        """Save or update consolidated SalesInterviewScorecard JSON."""
        scorecard_json = json.dumps(scorecard) if isinstance(scorecard, dict) else str(scorecard)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO scorecards (session_id, scorecard_json, created_at)
                VALUES (?, ?, ?)
            ''', (session_id, scorecard_json, datetime.now().isoformat()))
            conn.commit()

    def get_scorecard(self, session_id: str) -> Optional[dict]:
        """Retrieve stored consolidated SalesInterviewScorecard JSON for a session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT scorecard_json FROM scorecards
                WHERE session_id = ?
                ORDER BY id DESC LIMIT 1
            ''', (session_id,))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except Exception:
                    pass

        # Fallback to evaluations table if stored there
        raw_eval = self.get_evaluation(session_id)
        if raw_eval and isinstance(raw_eval, dict) and "delivery_scorecard" in raw_eval:
            return raw_eval

        return None

    def save_state_snapshot(self, session_id: str, turn_number: int, state: any, event_type: str, event_reason: str):
        import json
        state_dict = state.to_dict() if hasattr(state, "to_dict") else dict(state)
        state_json = json.dumps(state_dict)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO state_snapshots (session_id, turn_number, state_json, event_type, event_reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (session_id, turn_number, state_json, event_type, event_reason, datetime.now().isoformat()))
            conn.commit()

    def get_state_history(self, session_id: str) -> list:
        import json
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT turn_number, state_json, event_type, event_reason, created_at
                FROM state_snapshots
                WHERE session_id = ?
                ORDER BY turn_number ASC, id ASC
            ''', (session_id,))
            rows = cursor.fetchall()
            
            history = []
            for row in rows:
                turn_number, state_json, event_type, event_reason, created_at = row
                try:
                    state_data = json.loads(state_json)
                except Exception:
                    state_data = state_json
                history.append({
                    "turn": turn_number,
                    "state": state_data,
                    "event_type": event_type,
                    "reason": event_reason,
                    "created_at": created_at,
                })
            return history

    def save_interview_stage_event(self, session_id: str, turn_number: int, from_stage: str, to_stage: str, reason: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO interview_stage_events (session_id, turn_number, from_stage, to_stage, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (session_id, turn_number, from_stage, to_stage, reason, datetime.now().isoformat()))
            conn.commit()

    def get_interview_stage_events(self, session_id: str) -> list:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT turn_number, from_stage, to_stage, reason, created_at
                FROM interview_stage_events
                WHERE session_id = ?
                ORDER BY turn_number ASC, id ASC
            ''', (session_id,))
            rows = cursor.fetchall()

            events = []
            for row in rows:
                turn_number, from_stage, to_stage, reason, created_at = row
                events.append({
                    "turn": turn_number,
                    "from_stage": from_stage,
                    "to_stage": to_stage,
                    "reason": reason,
                    "created_at": created_at,
                })
            return events

    def save_candidate_analysis(
        self,
        session_id: str,
        turn_number: int,
        candidate_message: str,
        current_stage: str,
        analysis: any,
        extracted_facts: list,
        extracted_claims: list,
        interaction_signals: list,
        latency_ms: float = 0.0,
        model_name: str = "azure/genailab-maas-gpt-4o-mini",
    ):
        import json
        analysis_dict = analysis.to_dict() if hasattr(analysis, "to_dict") else dict(analysis)
        facts_list = [f.to_dict() if hasattr(f, "to_dict") else dict(f) for f in extracted_facts]
        claims_list = [c.to_dict() if hasattr(c, "to_dict") else dict(c) for c in extracted_claims]
        signals_list = [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in interaction_signals]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO candidate_turn_analyses (
                    session_id, turn_number, candidate_message, current_stage,
                    analysis_json, extracted_facts_json, extracted_claims_json,
                    interaction_signals_json, latency_ms, model_name, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                turn_number,
                candidate_message,
                current_stage,
                json.dumps(analysis_dict),
                json.dumps(facts_list),
                json.dumps(claims_list),
                json.dumps(signals_list),
                latency_ms,
                model_name,
                datetime.now().isoformat(),
            ))
            conn.commit()

    def get_candidate_analyses(self, session_id: str) -> list:
        import json
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT turn_number, candidate_message, current_stage, analysis_json,
                       extracted_facts_json, extracted_claims_json, interaction_signals_json,
                       latency_ms, model_name, created_at
                FROM candidate_turn_analyses
                WHERE session_id = ?
                ORDER BY turn_number ASC, id ASC
            ''', (session_id,))
            rows = cursor.fetchall()

            records = []
            for row in rows:
                (turn_number, candidate_message, current_stage, analysis_json,
                 facts_json, claims_json, signals_json, latency_ms, model_name, created_at) = row
                try:
                    analysis_data = json.loads(analysis_json)
                except Exception:
                    analysis_data = analysis_json
                try:
                    facts_data = json.loads(facts_json)
                except Exception:
                    facts_data = []
                try:
                    claims_data = json.loads(claims_json)
                except Exception:
                    claims_data = []
                try:
                    signals_data = json.loads(signals_json)
                except Exception:
                    signals_data = []

                records.append({
                    "turn": turn_number,
                    "candidate_message": candidate_message,
                    "current_stage": current_stage,
                    "analysis": analysis_data,
                    "extracted_facts": facts_data,
                    "extracted_claims": claims_data,
                    "interaction_signals": signals_data,
                    "latency_ms": latency_ms,
                    "model_name": model_name,
                    "created_at": created_at,
                })
            return records

    def save_behavior_decision(
        self,
        session_id: str,
        turn_number: int,
        decision: Any,
    ):
        """Save stakeholder behavioral decision and policy trace to SQLite."""
        if hasattr(decision, "to_dict"):
            d_dict = decision.to_dict()
        elif isinstance(decision, dict):
            d_dict = decision
        else:
            d_dict = {}

        primary = d_dict.get("primary_action", {})
        action = primary.get("action_type", "") if isinstance(primary, dict) else str(primary)
        target = primary.get("target", "") if isinstance(primary, dict) else ""
        intensity = d_dict.get("intensity", 0.50)
        objective = primary.get("objective", "") if isinstance(primary, dict) else ""
        trigger = primary.get("trigger", "") if isinstance(primary, dict) else ""
        reason = primary.get("reason", "") if isinstance(primary, dict) else ""

        secondary = d_dict.get("secondary_action")
        secondary_action = ""
        if secondary and isinstance(secondary, dict):
            secondary_action = secondary.get("action_type", "")

        policy_id = d_dict.get("policy_id", "")
        trace = d_dict.get("trace", {})
        trace_json = json.dumps(trace if isinstance(trace, dict) else (trace.to_dict() if hasattr(trace, "to_dict") else {}))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO behavior_decisions (
                    session_id, turn_number, action, secondary_action, target,
                    intensity, objective, trigger, reason, policy_id, trace_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id, turn_number, action, secondary_action, target,
                float(intensity), objective, trigger, reason, policy_id, trace_json,
                datetime.now().isoformat()
            ))
            conn.commit()

    def get_behavior_history(self, session_id: str):
        """Retrieve complete chronological behavioral decision history for a session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT turn_number, action, secondary_action, target,
                       intensity, objective, trigger, reason, policy_id, trace_json, created_at
                FROM behavior_decisions
                WHERE session_id = ?
                ORDER BY turn_number ASC, id ASC
            ''', (session_id,))
            rows = cursor.fetchall()

            history = []
            for row in rows:
                (turn_number, action, secondary_action, target,
                 intensity, objective, trigger, reason, policy_id, trace_json, created_at) = row
                try:
                    trace_data = json.loads(trace_json)
                except Exception:
                    trace_data = {}

                history.append({
                    "turn": turn_number,
                    "action": action,
                    "secondary_action": secondary_action if secondary_action else None,
                    "target": target,
                    "intensity": intensity,
                    "objective": objective,
                    "trigger": trigger,
                    "reason": reason,
                    "policy_id": policy_id,
                    "trace": trace_data,
                    "created_at": created_at,
                })
            return history

    get_behavior_decisions = get_behavior_history

    def save_knowledge_item(self, session_id: str, item: Any = None, **kwargs):
        """Save a stakeholder knowledge item to SQLite."""
        if item is not None and hasattr(item, "to_dict"):
            i_dict = item.to_dict()
        elif isinstance(item, dict):
            i_dict = item
        else:
            i_dict = kwargs
        topic = i_dict.get("topic", kwargs.get("topic", ""))
        value_text = str(i_dict.get("value", i_dict.get("fact_summary", kwargs.get("fact_summary", ""))))
        status = str(i_dict.get("status", kwargs.get("status", "KNOWN")))
        source = str(i_dict.get("source", kwargs.get("source", "WORLD_MODEL")))
        confidence = float(i_dict.get("confidence", kwargs.get("confidence", 1.0)))
        disclosure_level = str(i_dict.get("disclosure_level", kwargs.get("disclosure_level", "INTERNAL")))
        turn_number = int(kwargs.get("turn_number", i_dict.get("turn_number", 0)))
        provenance = str(i_dict.get("provenance", kwargs.get("provenance", "")))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO knowledge_items (
                    session_id, topic, value_text, status, source, confidence,
                    disclosure_level, turn_number, provenance, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id, topic, value_text, status, source, confidence,
                disclosure_level, turn_number, provenance, datetime.now().isoformat()
            ))
            conn.commit()

    def get_knowledge_history(self, session_id: str):
        """Retrieve all knowledge items for a session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT topic, value_text, status, source, confidence,
                       disclosure_level, turn_number, provenance, created_at
                FROM knowledge_items
                WHERE session_id = ?
                ORDER BY turn_number ASC, id ASC
            ''', (session_id,))
            rows = cursor.fetchall()
            return [
                {
                    "topic": r[0],
                    "value": r[1],
                    "status": r[2],
                    "source": r[3],
                    "confidence": r[4],
                    "disclosure_level": r[5],
                    "turn_number": r[6],
                    "provenance": r[7],
                    "created_at": r[8],
                }
                for r in rows
            ]

    def save_memory_item(self, session_id: str, item: Any = None, **kwargs):
        """Save a structured conversational memory item to SQLite."""
        import uuid
        if item is not None and hasattr(item, "to_dict"):
            m_dict = item.to_dict()
        elif isinstance(item, dict):
            m_dict = item
        else:
            m_dict = kwargs
        mem_id = m_dict.get("memory_id", kwargs.get("memory_id", str(uuid.uuid4())))
        m_type = m_dict.get("type", m_dict.get("memory_type", kwargs.get("memory_type", "CANDIDATE_STATEMENT")))
        topic = m_dict.get("topic", kwargs.get("topic", ""))
        content = m_dict.get("content", kwargs.get("content", ""))
        source_turn = int(m_dict.get("source_turn", kwargs.get("turn_number", 0)))
        importance = float(m_dict.get("importance", kwargs.get("importance", 0.50)))
        confidence = float(m_dict.get("confidence", kwargs.get("confidence", 1.0)))
        raw_tags = m_dict.get("retrieval_tags", m_dict.get("tags", kwargs.get("tags", [])))
        tags_json = json.dumps(raw_tags if isinstance(raw_tags, list) else [])
        raw_meta = m_dict.get("metadata", kwargs.get("metadata", {}))
        if not isinstance(raw_meta, dict):
            raw_meta = {}
        speaker_val = m_dict.get("speaker") or kwargs.get("speaker") or ("candidate" if "candidate" in str(m_type).lower() else "stakeholder")
        raw_meta["speaker"] = speaker_val
        metadata_json = json.dumps(raw_meta)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO memory_items (
                    session_id, memory_id, memory_type, topic, content,
                    source_turn, importance, confidence, tags_json, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id, mem_id, m_type, topic, content, source_turn,
                importance, confidence, tags_json, metadata_json, datetime.now().isoformat()
            ))
            conn.commit()

    def get_memory_history(self, session_id: str):
        """Retrieve all structured conversational memories for a session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT memory_id, memory_type, topic, content, source_turn,
                       importance, confidence, tags_json, metadata_json, created_at
                FROM memory_items
                WHERE session_id = ?
                ORDER BY source_turn ASC, id ASC
            ''', (session_id,))
            rows = cursor.fetchall()
            records = []
            for r in rows:
                try:
                    tags = json.loads(r[7])
                except Exception:
                    tags = []
                try:
                    meta = json.loads(r[8])
                except Exception:
                    meta = {}
                records.append({
                    "memory_id": r[0],
                    "type": r[1],
                    "topic": r[2],
                    "content": r[3],
                    "source_turn": r[4],
                    "importance": r[5],
                    "confidence": r[6],
                    "retrieval_tags": tags,
                    "metadata": meta,
                    "speaker": meta.get("speaker", "candidate" if "candidate" in str(r[1]).lower() else "stakeholder"),
                    "created_at": r[9],
                })
            return records

    def save_commitment(self, session_id: str, commitment: Any = None, **kwargs):
        """Save a stakeholder commitment to SQLite."""
        if commitment is not None and hasattr(commitment, "to_dict"):
            c_dict = commitment.to_dict()
        elif isinstance(commitment, dict):
            c_dict = commitment
        else:
            c_dict = kwargs
        cid = c_dict.get("id", c_dict.get("commitment_id", kwargs.get("commitment_id", "")))
        ctype = c_dict.get("commitment_type", kwargs.get("commitment_type", "DOCUMENT"))
        desc = c_dict.get("description", kwargs.get("description", ""))
        status = str(c_dict.get("status", kwargs.get("status", "ACTIVE")))
        source_turn = int(c_dict.get("source_turn", kwargs.get("turn_promised", 0)))
        fulfilled_at = c_dict.get("fulfilled_at_turn", kwargs.get("fulfilled_at_turn"))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO stakeholder_commitments (
                    session_id, commitment_id, commitment_type, description,
                    status, source_turn, fulfilled_at_turn, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id, cid, ctype, desc, status, source_turn, fulfilled_at, datetime.now().isoformat()
            ))
            conn.commit()

    def save_stakeholder_commitment(self, session_id: str, commitment: Any = None, **kwargs):
        return self.save_commitment(session_id, commitment=commitment, **kwargs)

    def get_commitments(self, session_id: str):
        """Retrieve all commitments for a session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT commitment_id, commitment_type, description, status, source_turn, fulfilled_at_turn, created_at
                FROM stakeholder_commitments
                WHERE session_id = ?
                ORDER BY source_turn ASC, id ASC
            ''', (session_id,))
            rows = cursor.fetchall()
            return [
                {
                    "id": r[0],
                    "commitment_id": r[0],
                    "commitment_type": r[1],
                    "description": r[2],
                    "status": r[3],
                    "source_turn": r[4],
                    "fulfilled_at_turn": r[5],
                    "created_at": r[6],
                }
                for r in rows
            ]

    def save_unresolved_item(self, session_id: str, item: Any = None, item_type: str = "question", **kwargs):
        """Save an unresolved question or objection to SQLite."""
        if item is not None and hasattr(item, "to_dict"):
            i_dict = item.to_dict()
        elif isinstance(item, dict):
            i_dict = item
        else:
            i_dict = kwargs
        item_id = i_dict.get("id", i_dict.get("item_id", kwargs.get("item_id", "")))
        i_type = i_dict.get("item_type", kwargs.get("item_type", item_type))
        topic = i_dict.get("topic", kwargs.get("topic", ""))
        content = i_dict.get("question") or i_dict.get("description") or i_dict.get("content", kwargs.get("content", ""))
        status = str(i_dict.get("status", kwargs.get("status", "UNRESOLVED")))
        severity = float(i_dict.get("severity", kwargs.get("severity", 0.50)))
        source_turn = int(i_dict.get("source_turn", kwargs.get("turn_created", 0)))
        resolved_at = i_dict.get("addressed_at_turn") or i_dict.get("resolved_at_turn", kwargs.get("resolved_at_turn"))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO unresolved_items (
                    session_id, item_id, item_type, topic, content,
                    status, severity, source_turn, resolved_at_turn, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id, item_id, i_type, topic, content, status,
                severity, source_turn, resolved_at, datetime.now().isoformat()
            ))
            conn.commit()

    def get_unresolved_items(self, session_id: str):
        """Retrieve unresolved items for a session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT item_id, item_type, topic, content, status, severity, source_turn, resolved_at_turn, created_at
                FROM unresolved_items
                WHERE session_id = ?
                ORDER BY source_turn ASC, id ASC
            ''', (session_id,))
            rows = cursor.fetchall()
            return [
                {
                    "item_id": r[0],
                    "item_type": r[1],
                    "topic": r[2],
                    "content": r[3],
                    "status": r[4],
                    "severity": r[5],
                    "source_turn": r[6],
                    "resolved_at_turn": r[7],
                    "created_at": r[8],
                }
                for r in rows
            ]

    def save_consistency_event(self, session_id: str, turn_number: int = 0, violation_type: str = "", details: str = "", repaired: bool = True, **kwargs):
        """Save a response consistency validation event."""
        violations = kwargs.get("violations")
        v_type = violation_type or (violations[0] if violations else "VIOLATION")
        v_details = details or (", ".join(violations) if violations else "")
        repaired_val = 1 if (repaired or kwargs.get("repaired", False)) else 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO consistency_events (
                    session_id, turn_number, violation_type, violation_details, repaired, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session_id, turn_number, v_type, v_details, repaired_val, datetime.now().isoformat()
            ))
            conn.commit()

    def get_consistency_events(self, session_id: str):
        """Retrieve consistency validation events for a session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT turn_number, violation_type, violation_details, repaired, created_at
                FROM consistency_events
                WHERE session_id = ?
                ORDER BY turn_number ASC, id ASC
            ''', (session_id,))
            rows = cursor.fetchall()
            return [
                {
                    "turn_number": r[0],
                    "violation_type": r[1],
                    "violation_details": r[2],
                    "repaired": r[3],
                    "is_valid": 1 if (not r[1] and not r[2]) or r[1] == "VALID" else 0,
                    "created_at": r[4],
                }
                for r in rows
            ]

    def save_simulator_evaluation(self, evaluation: Any) -> int:
        """Save a SimulatorEvaluation model or dict to SQLite."""
        if hasattr(evaluation, "model_dump"):
            data = evaluation.model_dump()
        elif isinstance(evaluation, dict):
            data = evaluation
        else:
            data = evaluation.__dict__

        session_id = data.get("session_id", "")
        scenario_id = data.get("scenario_id", "")
        persona_id = data.get("persona_id", "")
        arch_mode = data.get("architecture_mode", "")
        if hasattr(arch_mode, "value"):
            arch_mode = arch_mode.value

        fail_cats = data.get("failure_categories", [])
        fail_cats_str = json.dumps([f.value if hasattr(f, "value") else str(f) for f in fail_cats])

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO simulator_evaluations (
                    session_id, scenario_id, persona_id, architecture_mode,
                    persona_consistency, goal_consistency, behavior_consistency,
                    state_coherence, information_consistency, knowledge_boundary_compliance,
                    action_response_alignment, memory_consistency, overall_fidelity,
                    persona_collapse_score, evaluation_method, failure_categories_json,
                    evaluation_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                scenario_id,
                persona_id,
                arch_mode,
                float(data.get("persona_consistency", 0.0)),
                float(data.get("goal_consistency", 0.0)),
                float(data.get("behavior_consistency", 0.0)),
                float(data.get("state_coherence", 0.0)),
                float(data.get("information_consistency", 0.0)),
                float(data.get("knowledge_boundary_compliance", 0.0)),
                float(data.get("action_response_alignment", 0.0)),
                float(data.get("memory_consistency", 0.0)),
                float(data.get("overall_fidelity", 0.0)),
                float(data.get("persona_collapse_score", 0.0)),
                data.get("evaluation_method", "deterministic_rules+llm_judge"),
                fail_cats_str,
                json.dumps(data, default=str),
                data.get("created_at", datetime.now().isoformat()),
            ))
            conn.commit()
            return cursor.lastrowid

    def get_simulator_evaluation(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve latest simulator evaluation for a session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT evaluation_json FROM simulator_evaluations
                WHERE session_id = ?
                ORDER BY id DESC LIMIT 1
            ''', (session_id,))
            row = cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
            return None

    def get_all_simulator_evaluations(self) -> List[Dict[str, Any]]:
        """Retrieve all simulator evaluations."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT evaluation_json FROM simulator_evaluations
                ORDER BY id DESC
            ''')
            rows = cursor.fetchall()
            return [json.loads(r[0]) for r in rows if r[0]]

    def save_human_evaluation(self, record: Any) -> int:
        """Save human expert evaluation record."""
        if hasattr(record, "model_dump"):
            data = record.model_dump()
        elif isinstance(record, dict):
            data = record
        else:
            data = record.__dict__

        session_id = data.get("session_id", "")
        evaluator_id = data.get("evaluator_id", "expert_evaluator")
        agreement_json = json.dumps(data.get("behavioral_agreement_ratings", {}))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO human_evaluations (
                    session_id, evaluator_id, role_authenticity, behavior_realism,
                    question_realism, objection_realism, state_evolution,
                    information_realism, stakeholder_goal_consistency, overall_realism,
                    free_text_feedback, behavioral_agreement_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                evaluator_id,
                int(data.get("role_authenticity", 3)),
                int(data.get("behavior_realism", 3)),
                int(data.get("question_realism", 3)),
                int(data.get("objection_realism", 3)),
                int(data.get("state_evolution", 3)),
                int(data.get("information_realism", 3)),
                int(data.get("stakeholder_goal_consistency", 3)),
                int(data.get("overall_realism", 3)),
                data.get("free_text_feedback", ""),
                agreement_json,
                data.get("created_at", datetime.now().isoformat()),
            ))
            conn.commit()
            return cursor.lastrowid

    def get_human_evaluations(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve all human expert evaluations for a session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, session_id, evaluator_id, role_authenticity, behavior_realism,
                       question_realism, objection_realism, state_evolution,
                       information_realism, stakeholder_goal_consistency, overall_realism,
                       free_text_feedback, behavioral_agreement_json, created_at
                FROM human_evaluations
                WHERE session_id = ?
                ORDER BY id ASC
            ''', (session_id,))
            rows = cursor.fetchall()
            return [
                {
                    "id": r[0],
                    "session_id": r[1],
                    "evaluator_id": r[2],
                    "role_authenticity": r[3],
                    "behavior_realism": r[4],
                    "question_realism": r[5],
                    "objection_realism": r[6],
                    "state_evolution": r[7],
                    "information_realism": r[8],
                    "stakeholder_goal_consistency": r[9],
                    "overall_realism": r[10],
                    "free_text_feedback": r[11],
                    "behavioral_agreement_ratings": json.loads(r[12]) if r[12] else {},
                    "created_at": r[13],
                }
                for r in rows
            ]

    def save_persona_configuration(
        self,
        session_id: str,
        role: str,
        preset: Optional[str],
        traits: Dict[str, float],
        scenario_overrides: Optional[Dict[str, float]] = None,
        schema_version: str = "1.0",
    ) -> int:
        """Persist resolved concrete persona configuration for a simulation session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO persona_configurations (
                    session_id, role, preset, traits_json, scenario_overrides_json,
                    persona_schema_version, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                role,
                preset or "BALANCED",
                json.dumps(traits),
                json.dumps(scenario_overrides or {}),
                schema_version,
                datetime.now().isoformat(),
            ))
            conn.commit()
            return cursor.lastrowid

    def get_persona_configuration(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve persisted persona configuration for a session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT session_id, role, preset, traits_json, scenario_overrides_json,
                       persona_schema_version, created_at
                FROM persona_configurations
                WHERE session_id = ?
            ''', (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "session_id": row[0],
                "role": row[1],
                "preset": row[2],
                "traits": json.loads(row[3]) if row[3] else {},
                "scenario_overrides": json.loads(row[4]) if row[4] else {},
                "persona_schema_version": row[5],
                "created_at": row[6],
            }

    # Aliases for unified API & test access
    get_memory_items = get_memory_history
    get_stakeholder_commitments = get_commitments
    get_knowledge_items = get_knowledge_history


# Singleton storage service instance
storage = StorageService()
