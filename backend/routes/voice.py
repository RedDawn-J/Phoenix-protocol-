"""Voice routes — Whisper STT + OpenAI TTS via the BYOK.

Both endpoints use the user's OpenAI API key through the public OpenAI SDK
so the user gets voice-in / voice-out with zero extra credentials.

- POST /api/voice/transcribe — multipart file upload, returns {text}.
- POST /api/voice/speak — {text, voice?}, returns audio/mpeg bytes.

The J persona uses `nova` by default (confident, warm, authoritative female — J's canonical voice).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from capabilities import require_capability
from deps import get_current_user
from llm_chain import resolve_byok

log = logging.getLogger("gauntlet.voice")
router = APIRouter()

# Voice choices we expose. `nova` = J's canonical voice (confident female).
J_VOICES = {"onyx", "sage", "echo", "ash", "fable", "alloy", "coral", "nova", "shimmer"}
MAX_TTS_CHARS = 4096
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # Whisper's own cap


@router.post("/voice/transcribe")
async def voice_transcribe(
    file: UploadFile = File(...),
    language: str = Form("en"),
    _user: dict = Depends(get_current_user),
):
    """Whisper STT — audio in, text out."""
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="Empty audio upload")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail=f"Audio exceeds {MAX_AUDIO_BYTES // (1024*1024)}MB cap")

    # Whisper cares about the filename extension. Browser MediaRecorder
    # produces `audio/webm;codecs=opus` — save it as .webm so Whisper handles it.
    fname = file.filename or "clip.webm"
    if "." not in fname:
        fname += ".webm"
    require_capability("voice")
    api_key = await resolve_byok(_user["user_id"], "openai")
    if not api_key or isinstance(api_key, dict):
        raise HTTPException(status_code=503, detail="Configure an OpenAI key in Settings to use speech transcription")
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key, timeout=60)
    try:
        resp = await client.audio.transcriptions.create(
            file=(fname, audio, file.content_type or "application/octet-stream"),
            model="whisper-1",
            response_format="json",
            language=language or None,
        )
    except Exception as e:  # noqa: BLE001
        log.warning(f"speech transcription failed: {e}")
        raise HTTPException(status_code=502, detail="Speech transcription provider failed") from e
    return {"text": (getattr(resp, "text", "") or "").strip()}


@router.post("/voice/speak")
async def voice_speak(
    payload: dict,
    _user: dict = Depends(get_current_user),
):
    """OpenAI TTS — text in, mp3 bytes out."""
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    if len(text) > MAX_TTS_CHARS:
        # Silently truncate rather than fail — voice is a "nice-to-have" surface.
        text = text[:MAX_TTS_CHARS]

    voice = payload.get("voice") or "nova"
    if voice not in J_VOICES:
        voice = "nova"
    speed = float(payload.get("speed") or 1.0)
    speed = max(0.5, min(speed, 2.0))

    require_capability("voice")
    api_key = await resolve_byok(_user["user_id"], "openai")
    if not api_key or isinstance(api_key, dict):
        raise HTTPException(status_code=503, detail="Configure an OpenAI key in Settings to use speech synthesis")
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key, timeout=60)
    try:
        audio = await client.audio.speech.create(
            input=text,
            model="tts-1",
            voice=voice,
            response_format="mp3",
            speed=speed,
        )
        audio_bytes = audio.content
    except Exception as e:  # noqa: BLE001
        log.warning(f"speech synthesis failed: {e}")
        raise HTTPException(status_code=502, detail="Speech synthesis provider failed") from e

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store", "X-Gauntlet-Voice": voice},
    )
