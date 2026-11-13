# Implementation Plan: Kokoro-82M Voice Configuration & Live Preview

Implement an executive voice configuration system for Kokoro-82M TTS in Elevate. This allows candidates to choose an AI executive voice profile (`am_onyx`, `am_michael`, `af_bella`, `af_nicole`), preview it live in the `ScenarioBuilder` before the interview begins, store it in the Zustand session store, and pass it dynamically through the WebSocket to Kokoro's synthesis engine.

## Proposed Architecture & Design

### a) FastAPI `GET /api/voice/preview` Endpoint
- **Location**: `backend/app/api/endpoints.py` (mounted at `/api` in `main.py`).
- **Endpoint**: `GET /api/voice/preview?voice_id={id}` (also accepting `voice={id}`).
- **Curated Profiles**:
  - `am_onyx` (Authoritative Male) [Default]
  - `am_michael` (Direct Male)
  - `af_bella` (Confident Female)
  - `af_nicole` (Calm Female)
- **Validation & Fallback**: If an unknown or invalid `voice_id` is supplied, it falls back safely to `am_onyx`.
- **Generation Logic**: Calls `tts_pipeline("Hello, I am ready to begin the interview.", voice=voice_id)` which runs Kokoro in a background thread via `asyncio.to_thread(_generate_tts_sync, ...)` to ensure the async loop is never blocked.
- **Response**: Returns a `StreamingResponse` with `media_type="audio/wav"` and `io.BytesIO(wav_bytes)`.

### b) WebSocket Connection & Dynamic TTS Wiring
- **WS URL Query Param**: Update `InterviewWebSocketClient` in `frontend/src/utils/interviewWebSocket.ts`:
  ```ts
  this.url = `${protocol}//${host}:${port}/api/ws/interview/${encodeURIComponent(sessionId)}?voice=${encodeURIComponent(voiceId)}`;
  ```
- **Backend Parameter Extraction**:
  In `backend/app/api/endpoints.py`, `_handle_interview_websocket`:
  - Extract `voice` or `voice_id` from `websocket.query_params`.
  - Validate against curated voices; fallback to `am_onyx` if invalid or missing.
  - Store `selected_voice` on the active `RoleAgent` instance (`agent.voice_profile = selected_voice; agent.voice_id = selected_voice`).
  - Pass `voice=selected_voice` into `pipeline.stream_agent_audio_pipeline(..., voice=selected_voice)` and `pipeline.synthesize_sentence_with_metadata(..., voice=selected_voice)` for exit-intent responses.
- **Synthesis Engine**: In `backend/app/services/interview_pipeline.py`:
  - Define `_generate_tts_sync` (and alias `_synthesize_sentence_sync = _generate_tts_sync`) taking `(pipeline, text, voice, speed)`.
  - Update `synthesize_sentence_with_metadata(sentence, voice=None)` and `stream_agent_audio_pipeline(..., voice=None)` to accept and forward the requested voice profile.

### c) Frontend React `VoiceConfiguration` Component
- **Component**: `frontend/src/components/VoiceConfiguration.tsx`
  - Sleek modern card design consistent with Tailwind design system and existing `PersonaConfigurator`.
  - Displays curated dropdown:
    - `am_onyx` — Authoritative Male
    - `am_michael` — Direct Male
    - `af_bella` — Confident Female
    - `af_nicole` — Calm Female
  - **Live Audio Preview**:
    - "Play Preview" button with `Play` / `Square` (Stop) and `Loader2` (spinner) icons.
    - When clicked, fetches the audio blob from `GET /api/voice/preview?voice_id=${id}`.
    - Converts blob to Object URL: `new Audio(url).play()`.
    - Manages audio lifecycle: handles loading state, playing state, audio end events, error handling, and URL revocation.
- **Zustand Store**: `frontend/src/store/useStore.ts`
  - Add state field `voiceProfile: string` (default: `'am_onyx'`).
  - Add action `setVoiceProfile: (voice: string) => void`.
  - Reset to `'am_onyx'` in `resetSession()`.
- **Integration**:
  - Injected into `frontend/src/pages/ScenarioBuilder.tsx` right alongside the persona and conversation style controls.
  - Wired into `frontend/src/pages/ConversationScreen.tsx` where `InterviewWebSocketClient` is initialized with the selected `voiceProfile`.

---

## User Review Required

> [!NOTE]
> Kokoro-82M CPU synthesis takes ~0.5s for the short 8-word preview text ("Hello, I am ready to begin the interview."). The frontend includes a responsive loading spinner on the preview button during synthesis so the user has immediate feedback.

---

## Proposed Changes

### Backend

#### [MODIFY] [interview_pipeline.py](file:///home/labuser/Desktop/Project/Elevate/backend/app/services/interview_pipeline.py)
- Expose `_generate_tts_sync` with signature `(pipeline, text, voice, speed)`.
- Define `VALID_VOICE_IDS = {"am_onyx", "am_michael", "af_bella", "af_nicole"}` and `DEFAULT_VOICE_ID = "am_onyx"`.
- Update `synthesize_sentence_with_metadata` and `synthesize_sentence_to_wav_bytes` to accept optional `voice: Optional[str] = None`.
- Update `stream_agent_audio_pipeline` to accept `voice: Optional[str] = None` and pass it to sentence synthesis.
- Add async top-level function `tts_pipeline(text: str, voice: str = "am_onyx") -> bytes`.

#### [MODIFY] [endpoints.py](file:///home/labuser/Desktop/Project/Elevate/backend/app/api/endpoints.py)
- Add `GET /voice/preview` route taking `voice_id: Optional[str] = None`, invoking `tts_pipeline`, and returning `StreamingResponse(..., media_type="audio/wav")`.
- In `_handle_interview_websocket`:
  - Extract `voice` / `voice_id` from `websocket.query_params`.
  - Validate and fallback to `am_onyx`.
  - Pass the dynamic voice profile to `pipeline.stream_agent_audio_pipeline(..., voice=selected_voice)`.
  - Update `websocket_interview_session` and `websocket_interview_default` route handlers.

#### [NEW] [test_voice_configuration.py](file:///home/labuser/Desktop/Project/Elevate/backend/tests/test_voice_configuration.py)
- Unit tests verifying:
  - `GET /api/voice/preview?voice_id=am_onyx` returns 200 with `audio/wav`.
  - Fallback logic for invalid voice IDs.
  - `_generate_tts_sync` and `tts_pipeline` behavior.
  - Query param extraction on WebSocket endpoint.

---

### Frontend

#### [MODIFY] [useStore.ts](file:///home/labuser/Desktop/Project/Elevate/frontend/src/store/useStore.ts)
- Add `voiceProfile: string` (default: `'am_onyx'`).
- Add `setVoiceProfile: (voice: string) => void`.
- Update `resetSession` to reset `voiceProfile`.

#### [NEW] [VoiceConfiguration.tsx](file:///home/labuser/Desktop/Project/Elevate/frontend/src/components/VoiceConfiguration.tsx)
- Modern styled voice selector with dropdown for the 4 curated executive voices.
- Play Preview button with loading state (`Loader2`), playing state (`Square`), and native HTML `Audio` API playback.
- Displays voice tone and gender badges.

#### [MODIFY] [ScenarioBuilder.tsx](file:///home/labuser/Desktop/Project/Elevate/frontend/src/pages/ScenarioBuilder.tsx)
- Embed `<VoiceConfiguration />` into the scenario customization section.

#### [MODIFY] [interviewWebSocket.ts](file:///home/labuser/Desktop/Project/Elevate/frontend/src/utils/interviewWebSocket.ts)
- Accept `voiceId: string = 'am_onyx'` in constructor and append `?voice=${encodeURIComponent(voiceId)}` to the connection URL.

#### [MODIFY] [ConversationScreen.tsx](file:///home/labuser/Desktop/Project/Elevate/frontend/src/pages/ConversationScreen.tsx)
- Destructure `voiceProfile` from `useStore()` and pass it to `new InterviewWebSocketClient(sessionId, handlers, voiceProfile)`.

---

## Verification Plan

### Automated Tests
1. Run backend unit tests:
   ```bash
   PYTHONPATH=backend /home/labuser/Desktop/Project/Elevate/venv/bin/python -m pytest backend/tests/test_voice_configuration.py backend/tests/test_coaching_and_lifecycle.py
   ```
2. Run frontend TypeScript & bundle check:
   ```bash
   npm --prefix frontend run build
   ```

### Manual Verification
1. Test `GET /api/voice/preview?voice_id=am_onyx` via curl or test client, verifying WAV header bytes (`RIFF...WAVE`).
2. Test invalid voice `GET /api/voice/preview?voice_id=invalid_voice` verifying it safely falls back to `am_onyx`.
3. Verify live frontend interaction in ScenarioBuilder:
   - Selecting each voice from the dropdown updates the store.
   - Clicking "Play Preview" shows the loading spinner, plays audio via native HTML `Audio`, and restores icon when playback finishes.
