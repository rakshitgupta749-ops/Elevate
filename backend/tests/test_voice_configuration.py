import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.interview_pipeline import (
    get_interview_pipeline,
    tts_pipeline,
    _synthesize_sentence_sync,
    find_sentence_split,
    VALID_VOICE_IDS,
    DEFAULT_VOICE_ID,
)


@pytest.fixture
def client():
    return TestClient(app)


# ─── Constants ───────────────────────────────────────────────────────────────

def test_voice_constants():
    assert VALID_VOICE_IDS == {"am_onyx", "am_michael", "af_bella", "bf_emma"}
    assert DEFAULT_VOICE_ID == "am_onyx"


# ─── Sync synthesis ─────────────────────────────────────────────────────────

def test_synthesize_sentence_sync_produces_audio():
    pipeline = get_interview_pipeline()
    audio_np, sample_rate = _synthesize_sentence_sync(
        pipeline.kokoro_pipeline, "Hello test", voice="am_onyx"
    )
    assert sample_rate == 24000
    assert audio_np is not None
    assert len(audio_np) > 0


# ─── Async tts_pipeline helper ───────────────────────────────────────────────

@pytest.mark.anyio
async def test_tts_pipeline_valid_voice():
    wav_bytes = await tts_pipeline("Hello", voice="am_michael")
    assert len(wav_bytes) > 44
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"


@pytest.mark.anyio
async def test_tts_pipeline_invalid_voice_falls_back():
    wav_bytes = await tts_pipeline("Hello", voice="totally_invalid")
    assert len(wav_bytes) > 44
    assert wav_bytes[:4] == b"RIFF"


# ─── GET /api/voice/preview ─────────────────────────────────────────────────

def test_voice_preview_valid(client):
    response = client.get("/api/voice/preview?voice_id=am_onyx")
    assert response.status_code == 200
    assert "audio/wav" in response.headers.get("content-type", "")
    assert response.content[:4] == b"RIFF"
    assert response.content[8:12] == b"WAVE"


def test_voice_preview_all_curated(client):
    for vid in VALID_VOICE_IDS:
        resp = client.get(f"/api/voice/preview?voice_id={vid}")
        assert resp.status_code == 200, f"Failed for {vid}"
        assert resp.content[:4] == b"RIFF", f"Not WAV for {vid}"


def test_voice_preview_fallback_on_invalid(client):
    response = client.get("/api/voice/preview?voice_id=nonexistent_robot_voice")
    assert response.status_code == 200
    assert response.content[:4] == b"RIFF"


# ─── WebSocket voice query param ────────────────────────────────────────────

def test_websocket_accepts_voice_param(client):
    with client.websocket_connect("/api/ws/interview/test-ws-voice?voice=bf_emma") as ws:
        ws.send_json({"type": "ping"})
        msg = ws.receive_json()
        assert msg["type"] == "pong"


def test_websocket_accepts_invalid_voice_gracefully(client):
    with client.websocket_connect("/api/ws/interview/test-ws-bad?voice=fake_voice") as ws:
        ws.send_json({"type": "ping"})
        msg = ws.receive_json()
        assert msg["type"] == "pong"


def test_voice_speak_post_endpoint(client):
    response = client.post("/api/voice/speak", json={
        "text": "Hello there, testing speak endpoint.",
        "voice": "af_bella"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["voice"] == "af_bella"
    assert "audio" in data
    assert len(data["audio"]) > 0
    assert data["duration_sec"] > 0


def test_voice_speak_get_endpoint(client):
    response = client.get("/api/voice/speak?text=Hello+Kokoro&voice=am_michael")
    assert response.status_code == 200
    assert "audio/wav" in response.headers.get("content-type", "")
    assert response.content[:4] == b"RIFF"


def test_websocket_dynamic_set_voice(client):
    with client.websocket_connect("/api/ws/interview/test-ws-dynamic?voice=am_onyx") as ws:
        ws.send_json({"type": "set_voice", "voice": "af_bella"})
        msg = ws.receive_json()
        assert msg["type"] == "voice_updated"
        assert msg["voice"] == "af_bella"


# ─── Sentence Boundary & Chunking Tests ─────────────────────────────────────

def test_first_chunk_does_not_split_on_brief_greeting():
    """Short greetings alone must NOT trigger a premature first split (<12 words, <65 chars)."""
    assert find_sentence_split("Good morning!", is_first=True) is None
    assert find_sentence_split("Hello, thanks for meeting.", is_first=True) is None
    assert find_sentence_split("Good morning.\n\n", is_first=True) is None
    assert find_sentence_split("Hi there! Nice to meet you.", is_first=True) is None


def test_first_chunk_splits_when_threshold_reached():
    """First chunk splits cleanly once substantive context or question is complete (>=12 words or >=65 chars)."""
    text = "Good morning, thanks for meeting today. Could you walk me through your recent system architecture decisions?"
    split_idx = find_sentence_split(text, is_first=True)
    assert split_idx is not None
    # Verifies it split at the sentence boundary
    assert split_idx == len(text)


def test_abbreviation_not_treated_as_sentence_end():
    """Ensure common abbreviations like Dr., e.g., i.e. do not prematurely cut sentences."""
    buffer = "We worked with Dr. Smith on the distributed consensus algorithm for enterprise scaling."
    split_idx = find_sentence_split(buffer, is_first=True)
    assert split_idx is not None
    # Ensure it did not split at "Dr." (which would be around index 20)
    assert split_idx > 30


def test_subsequent_chunks_split_at_lower_threshold():
    """Subsequent chunks (is_first=False) split at standard sentence boundaries (>=6 words or >=35 chars)."""
    text = "That makes complete sense. Now let's explore your database indexing strategy."
    split_idx = find_sentence_split(text, is_first=False)
    assert split_idx is not None
    first_sentence = text[:split_idx].strip()
    assert first_sentence == "That makes complete sense."


# ─── POST /api/voice/transcribe (Transcribe-Only for manual mic close) ───────

def test_voice_transcribe_empty_or_tiny_audio(client):
    """Empty or tiny (<400 bytes) audio returns empty=True cleanly without failing."""
    res_empty = client.post("/api/voice/transcribe", json={"audio_base64": ""})
    assert res_empty.status_code == 200
    assert res_empty.json() == {"text": "", "empty": True}

    import base64
    tiny_b64 = base64.b64encode(b"tiny").decode("ascii")
    res_tiny = client.post("/api/voice/transcribe", json={"audio_base64": tiny_b64})
    assert res_tiny.status_code == 200
    assert res_tiny.json() == {"text": "", "empty": True}


def test_voice_transcribe_valid_audio_returns_text_only(client, monkeypatch):
    """Transcribe-only returns transcript text without triggering any AI session turn."""
    import base64
    from unittest.mock import AsyncMock

    pipeline = get_interview_pipeline()
    mock_transcribe = AsyncMock(return_value="I recommend partitioning by tenant ID.")
    monkeypatch.setattr(pipeline, "transcribe_audio", mock_transcribe)

    fake_webm = b"\x1a\x45\xdf\xa3" + b"\x00" * 2500
    b64 = base64.b64encode(fake_webm).decode("ascii")

    res = client.post("/api/voice/transcribe", json={"audio_base64": b64, "mime_type": "audio/webm"})
    assert res.status_code == 200
    assert res.json() == {"text": "I recommend partitioning by tenant ID.", "empty": False}
    mock_transcribe.assert_awaited_once()


def test_voice_transcribe_filters_short_hallucinations(client, monkeypatch):
    """Short sub-1.5s hallucinations (e.g., 'thank you.') are filtered to empty=True."""
    import base64
    from unittest.mock import AsyncMock

    pipeline = get_interview_pipeline()
    monkeypatch.setattr(pipeline, "transcribe_audio", AsyncMock(return_value="Thank you."))

    fake_short_audio = b"\x1a\x45\xdf\xa3" + b"\x00" * 600
    b64 = base64.b64encode(fake_short_audio).decode("ascii")

    res = client.post("/api/voice/transcribe", json={"audio_base64": b64, "mime_type": "audio/webm"})
    assert res.status_code == 200
    assert res.json() == {"text": "", "empty": True}



