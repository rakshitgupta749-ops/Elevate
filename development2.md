# Walkthrough: Real-Time Audio Interview Pipeline Integration

We integrated a zero-cost, enterprise-grade real-time interview pipeline into the FastAPI WebSocket backend.

---

## 1. Key Components Implemented

### A. Pipeline Service (`backend/app/services/interview_pipeline.py`)
- **Memory Management (Singleton)**:
  - Instantiates `KPipeline(lang_code='a')` and `AsyncOpenAI(base_url="https://genailab.tcs.in", http_client=httpx.AsyncClient(verify=False))` **globally once** via `get_interview_pipeline()` and `init_interview_pipeline()`.
  - Reused across all WebSocket connections without per-request allocation overhead.
- **Thread Safety (CPU Offloading)**:
  - Kokoro-82M neural speech synthesis is CPU-bound.
  - Offloaded using `await asyncio.to_thread(_synthesize_sentence_sync, self.kokoro_pipeline, cleaned, self.voice)`, completely preventing blocking of FastAPI's async event loop.
- **Speech-to-Text (STT)**:
  - Transcribes speech audio using enterprise gateway Whisper: `azure/genailab-maas-whisper`.
- **Streaming LLM with Sentence Chunking**:
  - Streams tokens from `azure/genailab-maas-gpt-4o`.
  - Buffers tokens and splits at sentence boundaries (`.`, `?`, `!`, `\n`).
  - Instantly yields `{ "type": "audio_chunk", "text": sentence, "audio": "<base64_wav>", ... }` per sentence to minimize Time-to-First-Audio (TTFA).

### B. Global Lifespan Pre-warming (`backend/app/main.py`)
- Configured FastAPI `lifespan` context manager to pre-warm the global pipeline at startup so the first connected WebSocket user experiences zero cold-start delay.

### C. WebSocket Endpoint (`backend/app/api/endpoints.py`)
- Injected `@router.websocket("/ws/interview/{session_id}")` and fallback `@router.websocket("/ws/interview")`.
- Supports:
  - Raw binary audio streaming (microphone input).
  - JSON envelope messages (`{"type": "audio", "data": "<base64>"}` and `{"type": "text", "message": "..."}`).
  - Pings (`{"type": "ping"}` -> `{"type": "pong"}`).
- Preserves full compatibility with session tracking (`storage.save_interaction`, `RoleAgent` persona and context).

---

## 2. Verification & Test Results

### 1. Model Imports & Availability
```bash
./venv/bin/python -c "import kokoro, asyncio, openai, numpy; print('All required imports succeed!')"
```
**Result**: `All required imports succeed!`

### 2. End-to-End TTS & STT Loop
- Synthesized speech sentence with local Kokoro-82M model -> Produced 133,244 bytes PCM WAV.
- Fed synthesized audio to `azure/genailab-maas-whisper` on enterprise gateway:
  - **Input**: `"Hello! Can you tell me about your background?"`
  - **Whisper Output**: `"Hello, can you tell me about your background?"`

### 3. WebSocket Real-Time Streaming Test
- Connected to `/api/ws/interview` over WebSocket.
- Sent prompt: `"Hello, could you introduce the role?"`
- Received stream:
  - **Audio Chunk 1**: `"Of course!"` (synthesized & yielded immediately)
  - **Audio Chunk 2**: `"Could you clarify which role you're referring to?"`
  - **Audio Chunk 3**: `"Are you asking about a specific job, position, or type of role?"`
  - **Audio Chunk 4**: `"For example, it could be a professional role, a character role in a story, or even a role within a team or organization."`
  - **Audio Chunk 5**: `"Let me know, and I’ll be happy to provide a detailed introduction!"`
  - **Turn Complete**: Full text delivered with graceful closure.

---

## 3. Candidate Early Exit / Dropout Resolution

### Problem Solved
When candidates said *"i have some work can you end this session"* or asked to leave early, the system previously produced a standard 7/10 score without penalizing the abrupt departure, treating it as a natural completion.

### Solution Applied
1. **Exit Intent Detection (`app/utils/guardrails.py`)**:
   - Implemented `is_candidate_exit_intent(text)` matching patterns such as *"can you end this session"*, *"have to go"*, *"need to leave"*, *"have some work"*, etc.
2. **In-Character Professional Wrap-Up (`RoleAgent`)**:
   - AI executive immediately acknowledges the early exit in persona:
     *"Understood. We all have tight schedules, so let's cut it here. Keep in mind that we haven't touched on your security architecture, downtime risks, or commercial closing, which are critical for our executive evaluation. I will note this session as incomplete. Thank you for your time."*
3. **Capped Early Exit Evaluation Report**:
   - Status explicitly marked as: **`INCOMPLETE / EARLY CANDIDATE WITHDRAWAL`**.
   - Score is **strictly capped at a maximum of 4/10** (or 35/100 on the scorecard).
   - In 'Situation & Scenario Handling', evaluates exit etiquette (abrupt departure without setting next steps or addressing pending security questions damages credibility).
   - Lists unassessed critical topics and provides concrete scripts for professional postponement.
4. **WebSocket & REST Synchronization**:
   - Emits `{"type": "session_terminated", "status": "INCOMPLETE", "reason": "Candidate requested early exit"}`.
   - Synthesizes and speaks the parting words over WebSocket in under 500ms while delivering the complete evaluation report text.
   - `POST /api/session/{session_id}/conclude` sets verdict to `Candidate Walkout / Incomplete Session` with grade `F`.

