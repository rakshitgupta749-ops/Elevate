from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import List, Optional, Any, Dict
import io
import uuid
import json
import base64
import asyncio
import numpy as np
import openai
from app.services.interview_pipeline import (
    get_interview_pipeline,
    calculate_audio_duration_sec,
    detect_audio_filename,
    tts_pipeline,
    VALID_VOICE_IDS,
    DEFAULT_VOICE_ID,
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
    VoiceSpeakRequest,
    VoiceTranscribeRequest,
    AdminRoleConfigurationRequest,
)
from app.models.configuration import PersonaConfiguration
from app.models.coaching import (
    StructuredCoachingReport,
    CoachingHintResponse,
    RewindResponse,
    SessionSummaryItem,
    SessionTranscriptResponse,
)
from app.agents.role_agent import RoleAgent
from app.utils.logger import logger
from app.utils.guardrails import is_safe_input, validate_input, is_candidate_exit_intent
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
async def create_session(request: SessionRequest):
    session_id = str(uuid.uuid4())
    
    try:
        # Check if learner selected a specific admin persona scenario, or canonical role configuration
        admin_cfg = None
        if getattr(request, "admin_configuration_id", None):
            admin_cfg = storage.get_admin_persona_scenario(request.admin_configuration_id)
        if not admin_cfg:
            admin_cfg = storage.get_admin_role_configuration(request.role)

        effective_persona_cfg = getattr(request, "persona_configuration", None)
        effective_voice = getattr(request, "voice", None) or getattr(request, "voice_id", None)
        effective_experience = request.experience or "expert"
        effective_style = request.style or "direct"
        effective_scenario = request.scenario or "Standard Interview"
        effective_topic = (request.topic or "").strip()

        if admin_cfg:
            if not effective_persona_cfg and admin_cfg.get("traits"):
                effective_persona_cfg = PersonaConfiguration(
                    role=admin_cfg.get("role", request.role),
                    preset=admin_cfg.get("preset") or "BALANCED",
                    traits=admin_cfg.get("traits", {}),
                    persona_schema_version="1.0"
                )
            if (not effective_voice or effective_voice == DEFAULT_VOICE_ID) and admin_cfg.get("voice"):
                effective_voice = admin_cfg.get("voice")
            if admin_cfg.get("experience"):
                effective_experience = admin_cfg.get("experience")
            if admin_cfg.get("style"):
                effective_style = admin_cfg.get("style")
            if admin_cfg.get("custom_scenario"):
                effective_scenario = admin_cfg.get("custom_scenario")
            if not effective_topic:
                effective_topic = (admin_cfg.get("scenario_title") or admin_cfg.get("title") or "").strip()

        if not effective_topic:
            effective_topic = f"{request.role} Executive Session"

        session_voice = effective_voice if effective_voice in VALID_VOICE_IDS else DEFAULT_VOICE_ID

        storage.save_session(
            session_id=session_id,
            topic=effective_topic,
            role=request.role,
            scenario=effective_scenario,
            experience=effective_experience,
            style=effective_style
        )
        
        agent = RoleAgent(
            role_id=request.role,
            topic=effective_topic,
            scenario=effective_scenario,
            experience=effective_experience,
            style=effective_style,
            session_id=session_id,
            policy_mode=getattr(request, "policy_mode", "rule_based") or "rule_based",
            memory_mode=getattr(request, "memory_mode", "full") or "full",
            architecture_mode=getattr(request, "architecture_mode", "FULL_SIMULATOR") or "FULL_SIMULATOR",
            persona_configuration=effective_persona_cfg,
            voice_profile=session_voice,
        )
        
        sessions[session_id] = agent

        # Explicitly persist persona configuration to SQLite so inspector tabs always load traits
        if hasattr(agent, "persona_configuration") and agent.persona_configuration:
            try:
                cfg = agent.persona_configuration
                traits_dict = cfg.traits if isinstance(cfg.traits, dict) else (cfg.traits.model_dump() if hasattr(cfg.traits, "model_dump") else dict(cfg.traits))
                storage.save_persona_configuration(
                    session_id=session_id,
                    role=getattr(cfg, "role", request.role),
                    preset=getattr(cfg, "preset", "BALANCED"),
                    traits=traits_dict,
                    scenario_overrides=getattr(cfg, "scenario_overrides", {}),
                    schema_version=getattr(cfg, "persona_schema_version", "1.0"),
                )
            except Exception as save_cfg_err:
                logger.warning(f"Failed to persist persona configuration in create_session: {save_cfg_err}")

        initial_message = agent.generate_opening()

        initial_audio_b64 = None
        try:
            # Fast bounded pre-synthesis (up to 3.0s).
            # With concise opening greetings (<35 words asking for candidate intro),
            # synthesis completes in ~300-500ms, returning initial_audio immediately for 0ms room startup!
            wav_bytes = await asyncio.wait_for(
                tts_pipeline(initial_message, voice=session_voice),
                timeout=3.0
            )
            if wav_bytes:
                initial_audio_b64 = base64.b64encode(wav_bytes).decode("ascii")
        except (asyncio.TimeoutError, Exception) as tts_err:
            logger.info(f"Opening audio will stream asynchronously inside the conversation room ({tts_err})")

        return SessionResponse(
            session_id=session_id,
            initial_message=initial_message,
            initial_audio=initial_audio_b64,
            voice=session_voice,
        )
    except Exception as e:
        import traceback
        logger.error(f"Failed to create session: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=traceback.format_exc())

@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if request.session_id not in sessions:
        logger.warning(f"Session not found: {request.session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
        
    is_safe, safety_err = validate_input(request.message)
    if not is_safe:
        logger.warning(f"Unsafe input detected in session {request.session_id}: {safety_err}")
        raise HTTPException(status_code=400, detail=safety_err or "Input violates safety guidelines")

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
from pydantic import BaseModel

class ChatStreamPayload(BaseModel):
    session_id: str
    message: str

@router.api_route("/chat/stream", methods=["GET", "POST"])
async def stream_chat(
    session_id: Optional[str] = None,
    message: Optional[str] = None,
    payload: Optional[ChatStreamPayload] = None,
):
    effective_session_id = (payload.session_id if payload else None) or session_id
    effective_message = (payload.message if payload else None) or message

    if not effective_session_id or not effective_message:
        raise HTTPException(status_code=400, detail="session_id and message are required")

    if effective_session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    is_safe, safety_err = validate_input(effective_message)
    if not is_safe:
        raise HTTPException(status_code=400, detail=safety_err or "Input violates safety guidelines")

    agent = sessions[effective_session_id]

    storage.save_interaction(effective_session_id, "user", effective_message)

    async def event_generator():
        try:
            full_reply = ""
            async for chunk in agent.stream_chat(effective_message):
                full_reply += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            storage.save_interaction(effective_session_id, "ai", full_reply)
            if "### 📊 Interview Complete" in full_reply:
                storage.save_evaluation(effective_session_id, full_reply)

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


@router.get("/voice/preview")
async def get_voice_preview(
    voice_id: Optional[str] = None, 
    voice: Optional[str] = None,
    text: Optional[str] = None,
):
    """
    Live audio synthesis and preview endpoint for Kokoro-82M TTS executive voices.
    Returns 24kHz WAV audio for the specified text or default preview.
    Falls back to 'am_onyx' if the requested voice is invalid.
    """
    raw_voice = voice_id or voice or DEFAULT_VOICE_ID
    safe_voice = raw_voice if raw_voice in VALID_VOICE_IDS else DEFAULT_VOICE_ID

    preview_text = text.strip() if (text and text.strip()) else "Hello, I am ready to begin the interview."
    try:
        wav_bytes = await tts_pipeline(preview_text, voice=safe_voice)
        return StreamingResponse(
            io.BytesIO(wav_bytes),
            media_type="audio/wav",
            headers={
                "Content-Disposition": f'inline; filename="speak_{safe_voice}.wav"',
                "Cache-Control": "no-cache",
            },
        )
    except Exception as exc:
        logger.error(f"[Voice Preview Error] Failed for voice '{safe_voice}': {exc}")
        raise HTTPException(status_code=500, detail=f"Voice synthesis failed: {str(exc)}")


@router.post("/voice/speak")
async def speak_text(req: VoiceSpeakRequest):
    """
    Synthesize arbitrary text with the configured Kokoro-82M voice profile.
    Returns JSON containing the base64 audio and metadata for seamless UI playback.
    """
    agent = sessions.get(req.session_id) if req.session_id else None
    agent_voice = getattr(agent, "voice_profile", None) if agent else None
    raw_voice = req.voice or req.voice_id or agent_voice or DEFAULT_VOICE_ID
    safe_voice = raw_voice if raw_voice in VALID_VOICE_IDS else DEFAULT_VOICE_ID

    clean_text = req.text.replace("#", "").replace("*", "").replace("[END_INTERVIEW]", "").strip()
    if not clean_text:
        return {"text": "", "voice": safe_voice, "audio": "", "duration_sec": 0.0}

    try:
        wav_bytes = await tts_pipeline(clean_text, voice=safe_voice)
        audio_b64 = base64.b64encode(wav_bytes).decode("ascii") if wav_bytes else ""
        duration = calculate_audio_duration_sec(wav_bytes)
        return {
            "text": clean_text,
            "voice": safe_voice,
            "audio": audio_b64,
            "duration_sec": duration,
        }
    except Exception as exc:
        logger.error(f"[Voice Speak Error] Failed for voice '{safe_voice}': {exc}")
        raise HTTPException(status_code=500, detail=f"Voice synthesis failed: {str(exc)}")


@router.get("/voice/speak")
async def speak_text_get(text: str, voice: Optional[str] = None, voice_id: Optional[str] = None):
    """
    Stream Kokoro-82M synthesized WAV audio directly for any text input.
    """
    raw_voice = voice or voice_id or DEFAULT_VOICE_ID
    safe_voice = raw_voice if raw_voice in VALID_VOICE_IDS else DEFAULT_VOICE_ID
    clean_text = text.replace("#", "").replace("*", "").replace("[END_INTERVIEW]", "").strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Empty text parameter")

    try:
        wav_bytes = await tts_pipeline(clean_text, voice=safe_voice)
        return StreamingResponse(
            io.BytesIO(wav_bytes),
            media_type="audio/wav",
            headers={
                "Content-Disposition": f'inline; filename="speak_{safe_voice}.wav"',
                "Cache-Control": "no-cache",
            },
        )
    except Exception as exc:
        logger.error(f"[Voice Speak GET Error]: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/voice/transcribe")
async def transcribe_voice_only(req: VoiceTranscribeRequest):
    """
    Transcribe speech audio using Whisper WITHOUT submitting it as an interview reply.
    Used when the candidate manually closes the microphone so they can edit/send via the Send button.
    """
    b64_audio = req.audio_base64 or ""
    if "," in b64_audio:
        b64_audio = b64_audio.split(",", 1)[1]
    if not b64_audio:
        return {"text": "", "empty": True}

    try:
        audio_bytes = base64.b64decode(b64_audio)
    except Exception:
        return {"text": "", "empty": True}

    if len(audio_bytes) < 400:
        return {"text": "", "empty": True}

    audio_duration = calculate_audio_duration_sec(audio_bytes)

    fallback_filename = "audio.webm"
    if req.mime_type:
        mt = req.mime_type.lower()
        if "mp4" in mt or "m4a" in mt:
            fallback_filename = "audio.mp4"
        elif "ogg" in mt:
            fallback_filename = "audio.ogg"
        elif "wav" in mt:
            fallback_filename = "audio.wav"
        elif "mpeg" in mt or "mp3" in mt:
            fallback_filename = "audio.mp3"

    effective_filename = detect_audio_filename(audio_bytes, default=fallback_filename)
    pipeline = get_interview_pipeline()
    try:
        user_text = await pipeline.transcribe_audio(audio_bytes, filename=effective_filename)
    except Exception as exc:
        err_str = str(exc)
        logger.warning(f"[HTTP Transcribe-Only Error]: {err_str}")
        if "could not be decoded" in err_str or "Invalid file format" in err_str or "400" in err_str:
            return {"text": "", "empty": True}
        raise HTTPException(status_code=500, detail=f"Transcription failed: {err_str}")

    if not user_text or is_hallucination(user_text, audio_duration):
        return {"text": "", "empty": True}

    return {"text": user_text.strip(), "empty": False}


@router.websocket("/ws/interview/{session_id}")
async def websocket_interview_session(websocket: WebSocket, session_id: str):
    voice = websocket.query_params.get("voice") or websocket.query_params.get("voice_id")
    await _handle_interview_websocket(websocket, session_id, voice=voice)


@router.websocket("/ws/interview")
async def websocket_interview_default(websocket: WebSocket):
    voice = websocket.query_params.get("voice") or websocket.query_params.get("voice_id")
    await _handle_interview_websocket(websocket, session_id=None, voice=voice)


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


async def _handle_interview_websocket(websocket: WebSocket, session_id: Optional[str] = None, voice: Optional[str] = None):
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

    # Resolve voice profile: query param > agent stored > default fallback
    agent_voice = getattr(agent, "voice_profile", None) if agent else None
    candidate_voice = voice or agent_voice or DEFAULT_VOICE_ID
    session_voice = candidate_voice if candidate_voice in VALID_VOICE_IDS else DEFAULT_VOICE_ID
    if agent:
        agent.voice_profile = session_voice
        agent.voice_id = session_voice
    logger.info(f"WebSocket client connected: session_id={session_id}, voice={session_voice}")

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
                if hasattr(agent, "process_turn_state_for_streaming"):
                    try:
                        system_prompt = await asyncio.to_thread(agent.process_turn_state_for_streaming, prompt_text)
                    except Exception as turn_err:
                        logger.error(f"[RoleAgent Streaming State Error]: {turn_err}")
                        system_prompt = None

                if not system_prompt:
                    system_prompt = (
                        f"You are roleplaying as {agent.role_id} in an interview setting about '{agent.topic}'. "
                        f"Scenario: {agent.scenario}. Experience level: {agent.experience}. Communication style: {agent.style}. "
                        "Engage in a professional, realistic interview dialogue. Speak naturally without any markdown headers, bullet points, or bold text. Keep responses focused and conversational."
                    )

            # Build multi-turn chat_history from persisted session interactions
            chat_history: List[Dict[str, str]] = []
            if session_id:
                try:
                    stored_interactions = storage.get_interactions(session_id)
                    if (
                        stored_interactions
                        and stored_interactions[-1].get("sender") == "user"
                        and stored_interactions[-1].get("message") == prompt_text
                    ):
                        stored_interactions = stored_interactions[:-1]
                    for item in stored_interactions:
                        msg_content = item.get("message", "")
                        if not msg_content:
                            continue
                        role_label = "assistant" if item.get("sender") == "ai" else "user"
                        chat_history.append({"role": role_label, "content": msg_content})
                except Exception as hist_err:
                    logger.debug(f"[WebSocket] Failed to load chat_history for {session_id}: {hist_err}")

            if not chat_history and agent and getattr(agent, "_opening_message", None):
                chat_history.append({"role": "assistant", "content": agent._opening_message})

            full_reply = ""
            async for packet in pipeline.stream_agent_audio_pipeline(
                prompt=prompt_text,
                system_prompt=system_prompt,
                chat_history=chat_history,
                voice=session_voice,
            ):
                if packet.get("type") == "audio_chunk":
                    duration = packet.get("duration_sec", 0.0)
                    telemetry.on_ai_audio_chunk(duration_sec=duration, timestamp=time.time())
                elif packet.get("type") == "turn_complete":
                    full_reply = packet.get("full_text", "")
                await safe_send_json(packet)

            if agent and hasattr(agent, "interview_state"):
                status_val = getattr(agent.interview_state.status, "value", str(agent.interview_state.status))
                if status_val == "TERMINATED":
                    await safe_send_json({
                        "type": "session_terminated",
                        "status": "TERMINATED",
                        "reason": getattr(agent.interview_state, "termination_reason", None)
                        or "Stakeholder terminated the session early.",
                    })

            if session_id and full_reply:
                storage.save_interaction(session_id, "ai", full_reply)
                if agent is not None and hasattr(agent, "record_ai_turn"):
                    try:
                        agent.record_ai_turn(full_reply)
                    except Exception:
                        pass
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
                    err_str = str(exc)
                    logger.warning(f"[WebSocket STT Error]: {err_str}")
                    if "could not be decoded" in err_str or "Invalid file format" in err_str or "400" in err_str:
                        await safe_send_json({
                            "type": "transcript_empty",
                            "reason": "Audio was too short or could not be decoded. Please speak into your microphone."
                        })
                    else:
                        await safe_send_json({"type": "error", "error": f"STT failed: {exc}"})
                    continue

                if not user_text:
                    await safe_send_json({
                        "type": "transcript_empty",
                        "reason": "No speech detected in audio frame."
                    })
                    continue

                # Whisper Hallucination Filter: Drop phantom phrases on sub-1.5s acoustic bursts
                if is_hallucination(user_text, audio_duration):
                    logger.info(
                        f"[Whisper Hallucination Filter] Dropped phantom transcript '{user_text}' "
                        f"from {audio_duration:.2f}s acoustic frame in session {session_id}."
                    )
                    if telemetry.active_barge_in or telemetry.barge_in_triggered:
                        telemetry.reset_barge_in_trigger()
                    await safe_send_json({
                        "type": "transcript_empty",
                        "reason": "Filtered non-speech acoustic noise."
                    })
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
                    continue

                elif msg_type in ("set_voice", "voice_change", "update_voice"):
                    new_voice = data.get("voice") or data.get("voice_id")
                    if new_voice and new_voice in VALID_VOICE_IDS:
                        session_voice = new_voice
                        if agent:
                            agent.voice_profile = new_voice
                            agent.voice_id = new_voice
                        logger.info(f"[WebSocket] Voice dynamically updated to '{session_voice}' for session {session_id}")
                        await safe_send_json({"type": "voice_updated", "voice": session_voice})
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
                        err_str = str(exc)
                        logger.warning(f"[WebSocket Base64 STT Error]: {err_str}")
                        if "could not be decoded" in err_str or "Invalid file format" in err_str or "400" in err_str:
                            await safe_send_json({
                                "type": "transcript_empty",
                                "reason": "Audio was too short or could not be decoded. Please speak into your microphone."
                            })
                        else:
                            await safe_send_json({"type": "error", "error": f"STT failed: {exc}"})
                        continue

                    if not user_text:
                        await safe_send_json({
                            "type": "transcript_empty",
                            "reason": "No speech detected in audio frame."
                        })
                        continue

                    # Whisper Hallucination Filter: Drop phantom phrases on sub-1.5s acoustic bursts
                    if is_hallucination(user_text, audio_duration):
                        logger.info(
                            f"[Whisper Hallucination Filter] Dropped phantom base64 transcript '{user_text}' "
                            f"from {audio_duration:.2f}s acoustic frame in session {session_id}."
                        )
                        if telemetry.active_barge_in or telemetry.barge_in_triggered:
                            telemetry.reset_barge_in_trigger()
                        await safe_send_json({
                            "type": "transcript_empty",
                            "reason": "Filtered non-speech acoustic noise."
                        })
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
                    speech_dur = data.get("speech_duration_sec")
                    if isinstance(speech_dur, (int, float)) and speech_dur > 0:
                        telemetry.user_active_seconds += float(speech_dur)
                    telemetry.on_user_speech_transcribed(user_text, timestamp=time.time())
                    await check_and_handle_barge_in()

            if not user_text:
                continue

            # Backchannel filtering check:
            # If AI is currently speaking and user did not trigger an aggressive barge-in,
            # allow AI playback to continue smoothly without interrupting.
            telemetry._sync_ai_state(time.time())
            is_ai_speaking = (active_ai_task and not active_ai_task.done()) or telemetry.ai_state == "PLAYING"
            if is_ai_speaking and not telemetry.barge_in_triggered:
                logger.info(
                    f"[WebSocket Backchannel] Candidate backchannel '{user_text}' during AI speech - continuing AI playback."
                )
                continue

            # Safety check
            is_safe, safety_err = validate_input(user_text)
            if not is_safe:
                logger.warning(f"Unsafe input detected in WebSocket session {session_id}: {safety_err}")
                notice_msg = f"⚠️ [Input Notice]: {safety_err}"
                await safe_send_json({"type": "error", "error": notice_msg})
                await safe_send_json({"type": "turn_complete", "full_text": notice_msg})
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

                wav_bytes, duration_sec = await pipeline.synthesize_sentence_with_metadata(spoken_text, voice=session_voice)
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
            if hasattr(agent.persona_configuration, "model_dump"):
                persona_cfg = agent.persona_configuration.model_dump()
            elif hasattr(agent.persona_configuration, "to_dict"):
                persona_cfg = agent.persona_configuration.to_dict()
            elif isinstance(agent.persona_configuration, dict):
                persona_cfg = agent.persona_configuration
            else:
                persona_cfg = {
                    "role": getattr(agent.persona_configuration, "role", agent.role_id),
                    "preset": getattr(agent.persona_configuration, "preset", "BALANCED"),
                    "traits": getattr(agent.persona_configuration, "traits", {}),
                }

        if not persona_cfg or not persona_cfg.get("traits"):
            stored_cfg = storage.get_persona_configuration(session_id)
            if stored_cfg and stored_cfg.get("traits"):
                persona_cfg = stored_cfg
            else:
                try:
                    from app.roles.traits import resolve_persona_configuration
                    resolved = resolve_persona_configuration(role=agent.role_id)
                    persona_cfg = resolved.model_dump()
                except Exception:
                    pass

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
            architecture_mode=request.architecture_mode or "FULL_SIMULATOR",
            role_id=request.role_id or "CTO",
            topic=request.topic or "Enterprise Cloud Modernization",
            random_seed=request.random_seed if request.random_seed is not None else 42,
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
# ADMIN PERSONA & ROLE CONFIGURATION ENDPOINTS (MULTIPLE PERSONAS PER ROLE)
# ==============================================================================

@router.get("/admin/personas")
def get_all_admin_personas():
    """Retrieve all published admin persona scenarios across all roles."""
    try:
        return storage.get_all_admin_persona_scenarios()
    except Exception as e:
        logger.error(f"Failed to fetch admin personas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/personas/by-role/{role}")
def get_admin_personas_by_role(role: str):
    """Retrieve all published admin persona scenarios for a specific role."""
    try:
        clean_role = role.upper()
        return storage.get_admin_scenarios_by_role(clean_role)
    except Exception as e:
        logger.error(f"Failed to fetch admin personas for role {role}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/personas/{id}")
def get_admin_persona_by_id(id: str):
    """Retrieve a specific admin persona scenario by ID."""
    try:
        scenario = storage.get_admin_persona_scenario(id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Persona scenario not found")
        return scenario
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch admin persona {id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/personas")
def save_admin_persona(request: AdminRoleConfigurationRequest):
    """Create or update a specific admin persona scenario."""
    try:
        clean_role = request.role.upper()
        scenario_id = request.id or f"{clean_role.lower()}-{uuid.uuid4().hex[:8]}"
        title = request.title or request.scenario_title or f"{clean_role} Persona"
        saved = storage.save_admin_persona_scenario(
            scenario_id=scenario_id,
            role=clean_role,
            title=title,
            preset=request.preset or "BALANCED",
            traits=request.traits or {},
            experience=request.experience or "expert",
            style=request.style or "direct",
            voice=request.voice or "am_onyx",
            conversation_overview=request.conversation_overview or "",
            custom_scenario=request.custom_scenario or "",
            scenario_title=request.scenario_title or title,
            challenge_tags=request.challenge_tags or [],
        )
        return saved
    except Exception as e:
        logger.error(f"Failed to save admin persona: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/personas/{id}")
def delete_admin_persona(id: str):
    """Delete an admin persona scenario by ID."""
    try:
        success = storage.delete_admin_persona_scenario(id)
        return {
            "success": success,
            "id": id,
            "message": f"Persona scenario {id} deleted successfully."
        }
    except Exception as e:
        logger.error(f"Failed to delete admin persona {id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/configurations")
def get_all_admin_configurations():
    """Retrieve all published admin role configurations."""
    try:
        return storage.get_all_admin_role_configurations()
    except Exception as e:
        logger.error(f"Failed to fetch admin configurations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/configurations/{id_or_role}")
def get_admin_configuration_for_role(id_or_role: str):
    """Retrieve published admin configuration by ID or role, or schema defaults."""
    try:
        # First check if ID matches a specific persona scenario
        specific_scenario = storage.get_admin_persona_scenario(id_or_role)
        if specific_scenario:
            return specific_scenario

        clean_role = id_or_role.upper()
        config = storage.get_admin_role_configuration(clean_role)
        if config:
            return config
        # Return sensible defaults if not yet published by admin
        schema = get_role_configuration_schema(clean_role)
        default_traits = {t.id: t.default for t in schema.traits}
        default_voice = "am_onyx" if clean_role in ["CTO", "CEO"] else "af_heart"
        return {
            "id": f"{clean_role.lower()}-default",
            "role": clean_role,
            "title": f"Default {clean_role} Persona",
            "preset": "BALANCED",
            "traits": default_traits,
            "experience": "expert",
            "style": "direct",
            "voice": default_voice,
            "conversation_overview": "",
            "custom_scenario": "",
            "scenario_title": "",
            "challenge_tags": [],
            "updated_at": None,
        }
    except Exception as e:
        logger.error(f"Failed to fetch admin configuration for {id_or_role}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/configurations")
def save_admin_configuration(request: AdminRoleConfigurationRequest):
    """Save and publish admin role configuration and persona scenario."""
    try:
        clean_role = request.role.upper()
        scenario_id = request.id or f"{clean_role.lower()}-canonical"
        title = request.title or request.scenario_title or f"{clean_role} Persona"

        saved = storage.save_admin_persona_scenario(
            scenario_id=scenario_id,
            role=clean_role,
            title=title,
            preset=request.preset or "BALANCED",
            traits=request.traits or {},
            experience=request.experience or "expert",
            style=request.style or "direct",
            voice=request.voice or "am_onyx",
            conversation_overview=request.conversation_overview or "",
            custom_scenario=request.custom_scenario or "",
            scenario_title=request.scenario_title or title,
            challenge_tags=request.challenge_tags or [],
        )
        return saved
    except Exception as e:
        logger.error(f"Failed to save admin configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/configurations/{id_or_role}")
def delete_admin_configuration(id_or_role: str):
    """Delete a published admin persona scenario or role configuration."""
    try:
        persona_deleted = storage.delete_admin_persona_scenario(id_or_role)
        storage.delete_admin_persona_scenario(f"{id_or_role.lower()}-canonical")
        role_deleted = storage.delete_admin_role_configuration(id_or_role.upper())
        success = persona_deleted or role_deleted
        return {
            "success": success,
            "role": id_or_role.upper(),
            "target": id_or_role,
            "message": f"Configuration for {id_or_role} deleted successfully."
        }
    except Exception as e:
        logger.error(f"Failed to delete admin configuration for {id_or_role}: {e}")
        raise HTTPException(status_code=500, detail=str(e))




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







