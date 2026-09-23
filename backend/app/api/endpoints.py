from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import List, Optional, Any, Dict
import uuid
import json
import base64
import asyncio
import numpy as np
import openai
import kokoro
from app.services.interview_pipeline import (
    get_interview_pipeline,
    calculate_audio_duration_sec,
)
from app.models.schemas import (
    RoleModel,
    TopicModel,
    SessionRequest,
    SessionResponse,
    ChatRequest,
    ChatResponse,
    EvaluationRunRequest,
    HumanRatingRequest,
)
from app.models.coaching import (
    StructuredCoachingReport,
    CoachingHintResponse,
    RewindResponse,
    SessionSummaryItem,
    SessionTranscriptResponse,
)
from app.agents.role_agent import RoleAgent
from app.utils.logger import logger
from app.utils.guardrails import is_safe_input, is_candidate_exit_intent
from app.services.storage_service import storage
from app.roles.traits import get_role_configuration_schema
import time
from app.services.telemetry import (
    get_or_create_telemetry,
    get_telemetry,
    remove_telemetry,
    SessionTelemetry,
)
from app.evaluation.evaluator import (
    SalesInterviewScorecard,
    get_sales_evaluator,
)

router = APIRouter()

# In-memory storage for prototype
sessions = {}

# Mock Data for Topics and Roles
TOPICS = [
    {"id": "tech-interview", "title": "Technical Interview", "description": "System design and coding interview practice", "icon": "Code"},
    {"id": "sales", "title": "Sales Conversation", "description": "Objection handling and closing techniques", "icon": "Briefcase"},
    {"id": "marketing", "title": "Marketing Discussion", "description": "Campaign strategy and branding", "icon": "Megaphone"},
    {"id": "leadership", "title": "Leadership Discussion", "description": "Managing teams and culture", "icon": "Users"},
    {"id": "client", "title": "Client Meeting", "description": "Managing expectations and deliverables", "icon": "UserCheck"},
    {"id": "hr", "title": "HR Interview", "description": "Behavioral and culture fit interview", "icon": "HeartHandshake"},
    {"id": "negotiation", "title": "Negotiation", "description": "Salary or contract negotiation practice", "icon": "Handshake"},
    {"id": "startup-pitch", "title": "Startup Pitch", "description": "Pitching to investors", "icon": "Rocket"}
]

ROLES = [
    {"id": "CEO", "name": "CEO", "description": "Visionary and results-oriented executive", "traits": ["Strategic", "Direct", "High-energy"]},
    {"id": "CTO", "name": "CTO", "description": "Technology Executive", "traits": ["Strategic", "Technical", "Direct"]},
    {"id": "HR", "name": "HR Manager", "description": "Focuses on culture fit and behavior", "traits": ["Empathetic", "Observant", "Professional"]},
    {"id": "SALES_MANAGER", "name": "Sales Director", "description": "Enterprise software sales leader", "traits": ["Persuasive", "Competitive", "Sharp"]}
]

@router.get("/topics", response_model=List[TopicModel])
def get_topics():
    return TOPICS

@router.get("/roles", response_model=List[RoleModel])
def get_roles():
    return ROLES

@router.post("/session", response_model=SessionResponse)
def create_session(request: SessionRequest):
    session_id = str(uuid.uuid4())
    
    try:
        storage.save_session(
            session_id=session_id,
            topic=request.topic,
            role=request.role,
            scenario=request.scenario,
            experience=request.experience,
            style=request.style
        )
        
        agent = RoleAgent(
            role_id=request.role,
            topic=request.topic,
            scenario=request.scenario,
            experience=request.experience,
            style=request.style,
            session_id=session_id,
            policy_mode=getattr(request, "policy_mode", "rule_based") or "rule_based",
            memory_mode=getattr(request, "memory_mode", "full") or "full",
            architecture_mode=getattr(request, "architecture_mode", "FULL_SIMULATOR") or "FULL_SIMULATOR",
            persona_configuration=getattr(request, "persona_configuration", None),
        )
        
        sessions[session_id] = agent
        initial_message = agent.generate_opening()
        return SessionResponse(session_id=session_id, initial_message=initial_message)
    except Exception as e:
        import traceback
        logger.error(f"Failed to create session: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=traceback.format_exc())

@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if request.session_id not in sessions:
        logger.warning(f"Session not found: {request.session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
        
    if not is_safe_input(request.message):
        logger.warning(f"Unsafe input detected in session {request.session_id}")
        raise HTTPException(status_code=400, detail="Input violates safety guidelines")

    agent = sessions[request.session_id]
    
    try:
        logger.info(f"User ({request.session_id}): {request.message}")
        storage.save_interaction(request.session_id, "user", request.message)

        reply = agent.chat(request.message)

        logger.info(f"Agent ({request.session_id}): {reply}")
        storage.save_interaction(request.session_id, "ai", reply)
        
        if "### 📊 Interview Complete" in reply:
            storage.save_evaluation(request.session_id, reply)

        return ChatResponse(reply=reply)
    except Exception as e:
        logger.error(f"Error during chat in session {request.session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

from fastapi.responses import StreamingResponse
import asyncio
import json

@router.get("/chat/stream")
async def stream_chat(session_id: str, message: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if not is_safe_input(message):
        raise HTTPException(status_code=400, detail="Input violates safety guidelines")

    agent = sessions[session_id]
    
    storage.save_interaction(session_id, "user", message)

    async def event_generator():
        try:
            full_reply = ""
            async for chunk in agent.stream_chat(message):
                full_reply += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            
            storage.save_interaction(session_id, "ai", full_reply)
            if "### 📊 Interview Complete" in full_reply:
                storage.save_evaluation(session_id, full_reply)
                
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Error during streaming chat: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/chat/stream/opening")
async def stream_opening(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    agent = sessions[session_id]

    async def event_generator():
        try:
            full_reply = ""
            async for chunk in agent.stream_opening():
                full_reply += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Error during streaming opening: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.websocket("/ws/interview/{session_id}")
async def websocket_interview_session(websocket: WebSocket, session_id: str):
    await _handle_interview_websocket(websocket, session_id)


@router.websocket("/ws/interview")
async def websocket_interview_default(websocket: WebSocket):
    await _handle_interview_websocket(websocket, session_id=None)


async def _run_post_call_evaluation_background(session_id: Optional[str], telemetry: Optional[Any]):
    """Background worker executing post-call evaluation pipeline upon candidate disconnect or session end."""
    if not session_id:
        return
    try:
        logger.info(f"[Post-Call Orchestrator] Triggered background evaluation for session {session_id}")
        evaluator = get_sales_evaluator()
        scorecard = await asyncio.to_thread(evaluator.evaluate_post_call, session_id, telemetry)
        logger.info(
            f"[Post-Call Orchestrator] Completed scorecard for session {session_id}: "
            f"readiness={scorecard.overall_readiness_score}"
        )
    except Exception as exc:
        logger.error(f"[Post-Call Orchestrator Error] Failed evaluation for session {session_id}: {exc}")


HALLUCINATION_PHRASES = {"thank you", "thank you.", "thanks for watching", "bye", "okay", "yeah"}


def is_hallucination(transcript: str, audio_duration: float) -> bool:
    cleaned = transcript.strip().lower()
    # If the audio was under 1.5 seconds and matches a known hallucination string, drop it.
    if audio_duration < 1.5 and (cleaned in HALLUCINATION_PHRASES or cleaned.rstrip(".!?,") in HALLUCINATION_PHRASES):
        return True
    return False


async def _handle_interview_websocket(websocket: WebSocket, session_id: Optional[str] = None):
    """
    Real-time WebSocket audio interview handler.
    - STT: Azure MaaS Whisper via enterprise gateway
    - LLM: Streaming response chunked at sentence boundaries
    - TTS: Local Kokoro-82M KPipeline with asyncio.to_thread CPU offloading (<500ms TTFA)
    - Telemetry (Track 1): Isolated in-memory acoustic VAD and delivery metrics
    - Orchestrator: Post-call background evaluation trigger
    """
    await websocket.accept()
    pipeline = get_interview_pipeline()
    agent = sessions.get(session_id) if session_id else None

    # Track 1: Initialize in-memory telemetry collector
    effective_session_id = session_id or f"ws-{uuid.uuid4()}"
    telemetry = get_or_create_telemetry(effective_session_id)

    logger.info(f"WebSocket client connected: session_id={session_id}")

    ws_lock = asyncio.Lock()

    async def safe_send_json(data: dict):
        async with ws_lock:
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.debug(f"Failed to send JSON to websocket: {e}")

    active_ai_task: Optional[asyncio.Task] = None

    async def cancel_active_ai_stream():
        nonlocal active_ai_task
        if active_ai_task and not active_ai_task.done():
            logger.info(f"[WebSocket] Cancelling active AI streaming task for session {session_id}")
            active_ai_task.cancel()
            try:
                await asyncio.shield(active_ai_task)
            except (asyncio.CancelledError, Exception):
                pass
            active_ai_task = None

    async def check_and_handle_barge_in() -> bool:
        if telemetry.should_flush_barge_in():
            logger.info(
                f"[WebSocket Barge-in Flush] session={session_id}: "
                f"Interruption #{telemetry.interruption_count} detected! Cancelling AI playback and sending flush frame."
            )
            await cancel_active_ai_stream()
            await safe_send_json({
                "type": "barge_in_flush",
                "timestamp": time.time(),
                "interruption_count": telemetry.interruption_count,
            })
            return True
        return False

    async def _stream_ai_response(prompt_text: str):
        try:
            telemetry.reset_barge_in_trigger()
            telemetry.on_ai_playback_start(timestamp=time.time())

            system_prompt = None
            if agent:
                system_prompt = (
                    f"You are roleplaying as {agent.role_id} in an interview setting about '{agent.topic}'. "
                    f"Scenario: {agent.scenario}. Experience level: {agent.experience}. Communication style: {agent.style}. "
                    "Engage in a professional, realistic interview dialogue. Keep responses focused and conversational."
                )

            full_reply = ""
            async for packet in pipeline.stream_agent_audio_pipeline(
                prompt=prompt_text,
                system_prompt=system_prompt,
            ):
                if packet.get("type") == "audio_chunk":
                    duration = packet.get("duration_sec", 0.0)
                    telemetry.on_ai_audio_chunk(duration_sec=duration, timestamp=time.time())
                elif packet.get("type") == "turn_complete":
                    full_reply = packet.get("full_text", "")
                await safe_send_json(packet)

            if session_id and full_reply:
                storage.save_interaction(session_id, "ai", full_reply)
                if hasattr(agent, "turn_count"):
                    agent.turn_count += 1
                if "### 📊 Interview Complete" in full_reply:
                    storage.save_evaluation(session_id, full_reply)
        except asyncio.CancelledError:
            logger.info(f"[WebSocket AI Stream Cancelled] Barge-in interrupted AI turn for session {session_id}")
            telemetry.on_ai_playback_end(timestamp=time.time())
            raise
        except Exception as exc:
            logger.error(f"[WebSocket AI Stream Error] session={session_id}: {exc}")

    try:
        while True:
            raw_msg = await websocket.receive()
            user_text = ""

            # 1. Binary payload (e.g. raw audio stream from microphone)
            if "bytes" in raw_msg and raw_msg["bytes"]:
                raw_bytes = raw_msg["bytes"]
                audio_duration = calculate_audio_duration_sec(raw_bytes)
                # Track 1 acoustic telemetry: zero-latency VAD frame processing
                telemetry.process_audio_chunk(raw_bytes, timestamp=time.time())
                await check_and_handle_barge_in()

                try:
                    user_text = await pipeline.transcribe_audio(raw_bytes)
                except Exception as exc:
                    logger.error(f"[WebSocket STT Error]: {exc}")
                    await safe_send_json({"type": "error", "error": f"STT failed: {exc}"})
                    continue

                if not user_text:
                    continue

                # Whisper Hallucination Filter: Drop phantom phrases on sub-1.5s acoustic bursts
                if is_hallucination(user_text, audio_duration):
                    logger.info(
                        f"[Whisper Hallucination Filter] Dropped phantom transcript '{user_text}' "
                        f"from {audio_duration:.2f}s acoustic frame in session {session_id}."
                    )
                    if telemetry.active_barge_in or telemetry.barge_in_triggered:
                        telemetry.reset_barge_in_trigger()
                    continue

                # Track 1 word & turn correlation
                telemetry.on_user_speech_transcribed(user_text, timestamp=time.time())
                await check_and_handle_barge_in()

                await safe_send_json({
                    "type": "transcript",
                    "text": user_text,
                    "role": "user"
                })

            # 2. Text / JSON envelope payload
            elif "text" in raw_msg and raw_msg["text"]:
                text_content = raw_msg["text"]
                try:
                    data = json.loads(text_content)
                except Exception:
                    data = {"type": "text", "message": text_content}

                msg_type = data.get("type", "text")

                if msg_type == "ping":
                    await safe_send_json({"type": "pong"})
                    continue

                elif msg_type == "playback_start":
                    telemetry.on_ai_playback_start(timestamp=time.time())
                    continue

                elif msg_type in ("playback_end", "playback_stop", "playback_done"):
                    telemetry.on_ai_playback_end(timestamp=time.time())
                    continue

                elif msg_type in ("barge_in", "barge_in_request"):
                    telemetry.barge_in_triggered = True
                    telemetry.interruption_count += 1
                    await check_and_handle_barge_in()
                    continue

                elif msg_type == "user_speech_start":
                    telemetry.on_user_speech_start(timestamp=time.time())
                    await check_and_handle_barge_in()
                    continue

                elif msg_type == "audio":
                    b64_audio = data.get("data") or data.get("audio", "")
                    if "," in b64_audio:
                        b64_audio = b64_audio.split(",", 1)[1]
                    try:
                        audio_bytes = base64.b64decode(b64_audio)
                        audio_duration = calculate_audio_duration_sec(audio_bytes)
                        telemetry.process_audio_chunk(audio_bytes, timestamp=time.time())
                        await check_and_handle_barge_in()
                        user_text = await pipeline.transcribe_audio(audio_bytes)
                    except Exception as exc:
                        logger.error(f"[WebSocket Base64 STT Error]: {exc}")
                        await safe_send_json({"type": "error", "error": f"STT failed: {exc}"})
                        continue

                    if not user_text:
                        continue

                    # Whisper Hallucination Filter: Drop phantom phrases on sub-1.5s acoustic bursts
                    if is_hallucination(user_text, audio_duration):
                        logger.info(
                            f"[Whisper Hallucination Filter] Dropped phantom base64 transcript '{user_text}' "
                            f"from {audio_duration:.2f}s acoustic frame in session {session_id}."
                        )
                        if telemetry.active_barge_in or telemetry.barge_in_triggered:
                            telemetry.reset_barge_in_trigger()
                        continue

                    telemetry.on_user_speech_transcribed(user_text, timestamp=time.time())
                    await check_and_handle_barge_in()

                    await safe_send_json({
                        "type": "transcript",
                        "text": user_text,
                        "role": "user"
                    })

                elif msg_type == "text":
                    user_text = data.get("message") or data.get("text", "")
                    if not user_text:
                        continue
                    telemetry.on_user_speech_transcribed(user_text, timestamp=time.time())
                    await check_and_handle_barge_in()

            if not user_text:
                continue

            # Backchannel filtering check:
            # If AI is currently speaking and user did not trigger an aggressive barge-in,
            # allow AI playback to continue smoothly without interrupting.
            is_ai_speaking = (active_ai_task and not active_ai_task.done()) or telemetry.ai_state == "PLAYING"
            if is_ai_speaking and not telemetry.barge_in_triggered:
                logger.info(
                    f"[WebSocket Backchannel] Candidate backchannel '{user_text}' during AI speech - continuing AI playback."
                )
                continue

            # Safety check
            if not is_safe_input(user_text):
                logger.warning(f"Unsafe input detected in WebSocket session {session_id}")
                await safe_send_json({"type": "error", "error": "Input violates safety guidelines"})
                continue

            # Record user interaction in session storage
            if session_id:
                storage.save_interaction(session_id, "user", user_text)

            # Cancel previous AI stream if active
            await cancel_active_ai_stream()

            # Check if candidate requested early exit/withdrawal
            if agent and is_candidate_exit_intent(user_text):
                agent.candidate_early_exit = True
                full_reply = await asyncio.to_thread(agent.chat, user_text)
                if session_id:
                    storage.save_interaction(session_id, "ai", full_reply)
                    storage.save_evaluation(session_id, full_reply)

                # Send early termination status packet
                await safe_send_json({
                    "type": "session_terminated",
                    "status": "INCOMPLETE",
                    "reason": "Candidate requested early exit",
                })

                spoken_text = "Understood. We all have tight schedules, so let's cut it here. I will note this session as incomplete. Thank you for your time."
                if "### 📊 Interview Complete" in full_reply:
                    prefix = full_reply.split("### 📊 Interview Complete", 1)[0].strip()
                    if prefix:
                        spoken_text = prefix

                wav_bytes, duration_sec = await pipeline.synthesize_sentence_with_metadata(spoken_text)
                telemetry.on_ai_audio_chunk(duration_sec=duration_sec, timestamp=time.time())

                audio_b64 = base64.b64encode(wav_bytes).decode("ascii") if wav_bytes else ""
                await safe_send_json({
                    "type": "audio_chunk",
                    "text": spoken_text,
                    "audio": audio_b64,
                    "sample_rate": 24000,
                    "format": "wav",
                    "duration_sec": duration_sec,
                    "is_final": True,
                })

                await safe_send_json({
                    "type": "turn_complete",
                    "full_text": full_reply,
                    "is_final": True,
                })
                continue

            # Launch streaming AI response in background task
            active_ai_task = asyncio.create_task(_stream_ai_response(user_text))

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected cleanly: session_id={session_id}")
    except RuntimeError as exc:
        if "disconnect" in str(exc).lower():
            logger.info(f"WebSocket client disconnected: session_id={session_id}")
        else:
            logger.error(f"WebSocket RuntimeError in session {session_id}: {exc}")
    except Exception as exc:
        logger.error(f"WebSocket error in session {session_id}: {exc}")
    finally:
        await cancel_active_ai_stream()
        # Combined Evaluation Pipeline Trigger:
        # When candidate disconnects or session concludes, trigger background orchestrator task
        if session_id:
            asyncio.create_task(_run_post_call_evaluation_background(session_id, telemetry))


@router.get("/session/{session_id}/opening")
def get_session_opening(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    agent = sessions[session_id]
    return {"session_id": session_id, "opening_message": agent.generate_opening()}


@router.get("/session/{session_id}/state-history")
def get_session_state_history(session_id: str):
    """Developer inspection endpoint: returns the state trajectory and transition event logs."""
    history = storage.get_state_history(session_id)
    return {
        "session_id": session_id,
        "total_snapshots": len(history),
        "history": history,
    }


@router.get("/session/{session_id}/interview-history")
def get_session_interview_history(session_id: str):
    """Developer inspection endpoint: returns the interview state machine status, criteria, and stage events."""
    stage_events = storage.get_interview_stage_events(session_id)

    if session_id in sessions:
        agent = sessions[session_id]
        interview_dict = agent.interview_state.to_dict()
        return {
            "session_id": session_id,
            "current_stage": interview_dict["current_stage"],
            "stage_turn_count": interview_dict["stage_turn_count"],
            "total_turn_count": interview_dict["total_turn_count"],
            "status": interview_dict["status"],
            "criteria": interview_dict["criteria"],
            "history": stage_events if stage_events else interview_dict["history"],
        }

    last_event = stage_events[-1] if stage_events else None
    current_stage = last_event["to_stage"] if last_event else "STAGE_1_OPENING_RAPPORT"
    return {
        "session_id": session_id,
        "current_stage": current_stage,
        "stage_turn_count": 0,
        "total_turn_count": last_event["turn"] if last_event else 0,
        "status": "COMPLETED" if last_event and last_event.get("to_stage") == "COMPLETED" else "ACTIVE",
        "criteria": {},
        "history": stage_events,
    }


@router.get("/session/{session_id}/live-state")
def get_session_live_state(session_id: str):
    """Real-time developer inspection endpoint: returns configured persona traits,
    current perception metrics, stage progress, and recent trajectory delta."""
    state_history = storage.get_state_history(session_id)
    stage_history = storage.get_interview_stage_events(session_id)
    analyses = storage.get_candidate_analyses(session_id)

    if session_id in sessions:
        agent = sessions[session_id]
        current_state_dict = agent.current_state.to_dict()
        interview_dict = agent.interview_state.to_dict()

        persona_cfg = None
        if hasattr(agent, "persona_configuration") and agent.persona_configuration:
            persona_cfg = agent.persona_configuration.to_dict() if hasattr(agent.persona_configuration, "to_dict") else {
                "role": agent.persona_configuration.role,
                "preset": agent.persona_configuration.preset,
                "traits": agent.persona_configuration.traits,
            }

        decision_dict = None
        if hasattr(agent, "current_decision") and agent.current_decision:
            decision_dict = agent.current_decision.to_dict()

        latest_analysis = analyses[-1] if analyses else None

        # Calculate delta between last two snapshots
        deltas = {}
        if len(state_history) >= 2:
            prev = state_history[-2].get("state", {})
            curr = state_history[-1].get("state", {})
            for k in curr:
                if k in prev and isinstance(curr[k], (int, float)) and isinstance(prev[k], (int, float)):
                    diff = curr[k] - prev[k]
                    if abs(diff) > 0.001:
                        deltas[k] = round(diff, 3)

        return {
            "session_id": session_id,
            "role": agent.role_id,
            "topic": agent.topic,
            "scenario": agent.scenario,
            "style": agent.style,
            "experience": agent.experience,
            "turn_count": agent.turn_count,
            "persona_configuration": persona_cfg,
            "current_state": current_state_dict,
            "deltas": deltas,
            "interview_state": interview_dict,
            "latest_decision": decision_dict,
            "latest_analysis": latest_analysis,
            "state_history": state_history,
            "stage_history": stage_history,
            "total_turns": len(state_history),
        }

    stored_session = storage.get_session(session_id)
    persona_cfg = storage.get_persona_configuration(session_id)
    latest_snapshot = state_history[-1] if state_history else None
    latest_state = latest_snapshot["state"] if latest_snapshot else {}

    return {
        "session_id": session_id,
        "role": stored_session.get("role") if stored_session else "Unknown",
        "topic": stored_session.get("topic") if stored_session else "",
        "scenario": stored_session.get("scenario") if stored_session else "",
        "style": stored_session.get("style") if stored_session else "",
        "experience": stored_session.get("experience") if stored_session else "",
        "turn_count": len(state_history) - 1 if state_history else 0,
        "persona_configuration": persona_cfg,
        "current_state": latest_state,
        "deltas": {},
        "interview_state": {
            "current_stage": stage_history[-1]["to_stage"] if stage_history else "STAGE_1_OPENING_RAPPORT",
            "stage_turn_count": 0,
            "total_turn_count": len(stage_history) if stage_history else 0,
            "status": "ACTIVE",
            "criteria": {},
        },
        "latest_decision": None,
        "latest_analysis": None,
        "state_history": state_history,
        "stage_history": stage_history,
        "total_turns": len(state_history),
    }


@router.get("/session/{session_id}/analysis-history")
def get_session_analysis_history(session_id: str):
    """Developer inspection endpoint: returns the turn-by-turn semantic candidate analyses, facts, and claims."""
    analyses = storage.get_candidate_analyses(session_id)
    fact_ledger = []
    claim_ledger = []
    if session_id in sessions:
        agent = sessions[session_id]
        fact_ledger = agent.fact_ledger.to_list()
        claim_ledger = agent.claim_ledger.to_list()

    return {
        "session_id": session_id,
        "total_analyzed_turns": len(analyses),
        "fact_ledger": fact_ledger,
        "claim_ledger": claim_ledger,
        "history": analyses,
    }


@router.get("/session/{session_id}/behavior-history")
def get_session_behavior_history(session_id: str):
    """Developer inspection endpoint: returns turn-by-turn behavioral policy decisions and trace."""
    history = storage.get_behavior_history(session_id)
    current_decision = None
    policy_mode = "rule_based"
    if session_id in sessions:
        agent = sessions[session_id]
        if hasattr(agent, "current_decision") and agent.current_decision:
            current_decision = agent.current_decision.to_dict()
        if hasattr(agent, "policy_mode"):
            policy_mode = agent.policy_mode

    return {
        "session_id": session_id,
        "policy_mode": policy_mode,
        "total_decisions": len(history),
        "current_decision": current_decision,
        "history": history,
    }


@router.get("/session/{session_id}/memory")
def get_session_memory(session_id: str):
    """Developer inspection endpoint: returns memory items, active commitments, and unresolved items."""
    db_memories = storage.get_memory_items(session_id)
    db_commitments = storage.get_stakeholder_commitments(session_id)
    db_unresolved = storage.get_unresolved_items(session_id)
    
    memory_mode = "full"
    memories_list = db_memories
    commitments_list = db_commitments
    unresolved_list = db_unresolved

    if session_id in sessions:
        agent = sessions[session_id]
        if hasattr(agent, "memory_mode"):
            memory_mode = agent.memory_mode
        if hasattr(agent, "memory_store") and agent.memory_store:
            memories_list = [m.model_dump() if hasattr(m, "model_dump") else m for m in agent.memory_store.memories]
            commitments_list = [c.model_dump() if hasattr(c, "model_dump") else c for c in agent.memory_store.commitments]
            unresolved_list = [u.model_dump() if hasattr(u, "model_dump") else u for u in agent.memory_store.unresolved_items]

    return {
        "session_id": session_id,
        "memory_mode": memory_mode,
        "total_memories": len(memories_list),
        "memories": memories_list,
        "commitments": commitments_list,
        "unresolved_items": unresolved_list,
    }


@router.get("/session/{session_id}/knowledge")
def get_session_knowledge(session_id: str):
    """Developer inspection endpoint: returns stakeholder knowledge items, world facts, and boundaries."""
    db_knowledge = storage.get_knowledge_items(session_id)
    knowledge_list = db_knowledge
    world_facts_list = []
    boundaries = {}

    if session_id in sessions:
        agent = sessions[session_id]
        if hasattr(agent, "knowledge_state") and agent.knowledge_state:
            knowledge_list = [k.model_dump() if hasattr(k, "model_dump") else k for k in agent.knowledge_state.get_all_items()]
        if hasattr(agent, "world_facts") and agent.world_facts:
            world_facts_list = [f.model_dump() if hasattr(f, "model_dump") else f for f in agent.world_facts.get_all_facts()]
        if hasattr(agent, "persona") and hasattr(agent.persona, "knowledge_boundaries"):
            boundaries = agent.persona.knowledge_boundaries.model_dump() if hasattr(agent.persona.knowledge_boundaries, "model_dump") else {}

    return {
        "session_id": session_id,
        "total_knowledge_items": len(knowledge_list),
        "knowledge_items": knowledge_list,
        "world_facts": world_facts_list,
        "boundaries": boundaries,
    }


@router.get("/session/{session_id}/consistency-history")
def get_session_consistency_history(session_id: str):
    """Developer inspection endpoint: returns consistency validation events and repair history."""
    events = storage.get_consistency_events(session_id)
    return {
        "session_id": session_id,
        "total_events": len(events),
        "history": events,
    }


@router.get("/evaluation/scenarios")
def get_evaluation_scenarios():
    """List all available controlled scenarios for simulator evaluation."""
    from app.evaluation.controlled_scenarios import list_scenarios
    return [
        {
            "scenario_id": s.scenario_id,
            "title": s.title,
            "description": s.description,
            "target_role": s.target_role,
            "turns_count": len(s.candidate_turns),
            "expected_state_pattern": s.expected_state_pattern,
            "version": s.version,
        }
        for s in list_scenarios()
    ]


@router.get("/evaluation/modes")
def get_evaluation_modes():
    """List available architecture ablation modes."""
    from app.evaluation.evaluation_models import SimulatorArchitectureMode
    return [mode.value for mode in SimulatorArchitectureMode]


@router.post("/evaluation/run")
def run_evaluation(request: EvaluationRunRequest):
    """Execute scenario evaluation under specified architecture mode."""
    from app.evaluation.evaluation_runner import EvaluationRunner
    runner = EvaluationRunner()
    try:
        result = runner.run_scenario_evaluation(
            scenario_id=request.scenario_id,
            architecture_mode=request.architecture_mode,
            role_id=request.role_id,
            topic=request.topic,
            random_seed=request.random_seed,
        )
        return result.model_dump()
    except Exception as e:
        import traceback
        logger.error(f"Evaluation run failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evaluation/{session_id}")
def get_evaluation_result(session_id: str):
    """Retrieve persisted simulator evaluation result for a session."""
    eval_json = storage.get_simulator_evaluation(session_id)
    if not eval_json:
        raise HTTPException(status_code=404, detail="Simulator evaluation not found for session")
    return eval_json


@router.post("/evaluation/human-rating")
def submit_human_rating(request: HumanRatingRequest):
    """Submit expert human evaluation for simulated stakeholder session."""
    try:
        row_id = storage.save_human_evaluation(request)
        return {"status": "success", "id": row_id, "session_id": request.session_id}
    except Exception as e:
        logger.error(f"Failed to submit human evaluation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evaluation/human-ratings/{session_id}")
def get_session_human_ratings(session_id: str):
    """Retrieve all human expert evaluations for a session."""
    ratings = storage.get_human_evaluations(session_id)
    return {
        "session_id": session_id,
        "total_ratings": len(ratings),
        "ratings": ratings,
    }


@router.post("/evaluation/experiment/{experiment_id}")
def run_research_experiment(experiment_id: str):
    """Run one of the formal research experiments (RQ1, RQ2, RQ3, RQ7, RQ8, RQ9)."""
    from app.evaluation.evaluation_runner import EvaluationRunner
    runner = EvaluationRunner()
    try:
        result = runner.run_experiment(experiment_id)
        return result
    except Exception as e:
        import traceback
        logger.error(f"Experiment execution failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/personas/configuration-schema/{role}")
def get_persona_configuration_schema_endpoint(role: str):
    """Retrieve configurable behavioral trait definitions and presets for a role."""
    try:
        schema = get_role_configuration_schema(role)
        return schema.model_dump()
    except Exception as e:
        logger.error(f"Failed to get persona schema for {role}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/personas/debug/{session_id}")
def get_persona_debug_endpoint(session_id: str):
    """Retrieve persisted resolved persona configuration and recent decisions with trait influences."""
    config = storage.get_persona_configuration(session_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Persona configuration not found for session {session_id}")

    decisions = storage.get_behavior_decisions(session_id)
    return {
        "session_id": session_id,
        "role": config.get("role"),
        "preset": config.get("preset"),
        "persona_schema_version": config.get("persona_schema_version"),
        "traits": config.get("traits", {}),
        "scenario_overrides": config.get("scenario_overrides", {}),
        "total_decisions": len(decisions),
        "recent_decisions": decisions[-5:] if decisions else [],
    }


# ==============================================================================
# P0 & P1 ENDPOINTS: COACHING DASHBOARD, LIFECYCLE, HINTS, REWIND & HISTORY
# ==============================================================================

@router.post("/session/{session_id}/conclude", response_model=StructuredCoachingReport)
def conclude_session(session_id: str):
    """Explicitly conclude an interview and generate a structured coaching report (Priority P0)."""
    if session_id in sessions:
        agent = sessions[session_id]
        report = agent.generate_coaching_report()
        return report

    # Check SQLite if session was persisted
    stored = storage.get_session(session_id)
    if not stored:
        raise HTTPException(status_code=404, detail="Session not found")

    existing_eval = storage.get_evaluation(session_id)
    if existing_eval and "overall_score" in existing_eval:
        return StructuredCoachingReport(**existing_eval)

    # If no active agent instance, reconstruct a minimal agent to generate report
    try:
        agent = RoleAgent(
            role_id=stored.get("role", "CTO"),
            topic=stored.get("topic", "General"),
            scenario=stored.get("scenario", ""),
            experience=stored.get("experience", "Senior"),
            style=stored.get("style", "Professional"),
            session_id=session_id,
        )
        sessions[session_id] = agent
        return agent.generate_coaching_report()
    except Exception as e:
        logger.error(f"Failed to conclude session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/{session_id}/rewind", response_model=RewindResponse)
def rewind_session(session_id: str):
    """Rewind the last turn ('Take 2'), restoring the previous state and message history (Priority P1)."""
    if session_id not in sessions:
        # Try to revive from stored session
        stored = storage.get_session(session_id)
        if not stored:
            raise HTTPException(status_code=404, detail="Session not found")
        agent = RoleAgent(
            role_id=stored.get("role", "CTO"),
            topic=stored.get("topic", "General"),
            scenario=stored.get("scenario", ""),
            experience=stored.get("experience", "Senior"),
            style=stored.get("style", "Professional"),
            session_id=session_id,
        )
        sessions[session_id] = agent

    agent = sessions[session_id]
    try:
        return agent.rewind_turn()
    except Exception as e:
        logger.error(f"Failed to rewind session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/{session_id}/hint", response_model=CoachingHintResponse)
def get_session_hint(session_id: str):
    """Generate a real-time tactical coaching hint for the current turn (Priority P1)."""
    if session_id not in sessions:
        stored = storage.get_session(session_id)
        if not stored:
            raise HTTPException(status_code=404, detail="Session not found")
        agent = RoleAgent(
            role_id=stored.get("role", "CTO"),
            topic=stored.get("topic", "General"),
            scenario=stored.get("scenario", ""),
            experience=stored.get("experience", "Senior"),
            style=stored.get("style", "Professional"),
            session_id=session_id,
        )
        sessions[session_id] = agent

    agent = sessions[session_id]
    try:
        return agent.generate_coaching_hint()
    except Exception as e:
        logger.error(f"Failed to generate coaching hint for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=List[SessionSummaryItem])
def list_previous_sessions(limit: int = 50):
    """Retrieve list of previous practice sessions and scores for the History dashboard (Priority P1)."""
    try:
        items = storage.list_sessions(limit=limit)
        return [SessionSummaryItem(**it) for it in items]
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/transcript", response_model=SessionTranscriptResponse)
def get_session_transcript(session_id: str):
    """Retrieve full conversation transcript and evaluation report for replay/review (Priority P1)."""
    stored = storage.get_session(session_id)
    if not stored:
        raise HTTPException(status_code=404, detail="Session not found")

    interactions = storage.get_interactions(session_id)
    raw_eval = storage.get_evaluation(session_id)
    eval_model = None
    if raw_eval and isinstance(raw_eval, dict) and "overall_score" in raw_eval:
        try:
            eval_model = StructuredCoachingReport(**raw_eval)
        except Exception:
            pass

    return SessionTranscriptResponse(
        session_id=session_id,
        topic=stored.get("topic", ""),
        role=stored.get("role", ""),
        scenario=stored.get("scenario", ""),
        created_at=stored.get("created_at", ""),
        interactions=interactions,
        evaluation=eval_model,
    )


@router.get("/session/{session_id}/coaching-report", response_model=StructuredCoachingReport)
def get_session_coaching_report(session_id: str):
    """Retrieve the stored structured coaching report for a session (Priority P0)."""
    raw_eval = storage.get_evaluation(session_id)
    if not raw_eval or not isinstance(raw_eval, dict) or "overall_score" not in raw_eval:
        raise HTTPException(status_code=404, detail="Coaching report not found for this session")
    return StructuredCoachingReport(**raw_eval)


@router.get("/session/{session_id}/scorecard", response_model=SalesInterviewScorecard)
def get_session_sales_scorecard(session_id: str):
    """Retrieve consolidated post-call SalesInterviewScorecard (Delivery + Strategic)."""
    scorecard = storage.get_scorecard(session_id)
    if scorecard:
        return scorecard

    stored = storage.get_session(session_id)
    if not stored and session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    telemetry = get_telemetry(session_id)
    evaluator = get_sales_evaluator()
    return evaluator.evaluate_post_call(session_id=session_id, telemetry=telemetry)







