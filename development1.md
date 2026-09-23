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
