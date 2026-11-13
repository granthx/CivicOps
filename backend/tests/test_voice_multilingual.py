from __future__ import annotations

import json

from app.config import settings

from .conftest import login_headers


def _minimal_wav_bytes() -> bytes:
    # Minimal valid RIFF/WAVE header (44 bytes)
    return (
        b"RIFF"
        + (36).to_bytes(4, "little")
        + b"WAVE"
        + b"fmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + (8000).to_bytes(4, "little")
        + (8000).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (8).to_bytes(2, "little")
        + b"data"
        + (0).to_bytes(4, "little")
    )


def test_multilingual_hinglish_and_hindi_fallback_triage(client):
    wards = client.get("/api/wards").json()
    ward_id = wards[0]["id"]

    hinglish_res = client.post(
        "/api/reports",
        data={
            "description": "Gali ke bahar kudedan bhar gaya hai aur kachra road par fail raha hai.",
            "latitude": "12.9718",
            "longitude": "77.5948",
            "ward_id": str(ward_id),
            "preferred_language": "hinglish",
        },
    )
    assert hinglish_res.status_code == 201
    report = hinglish_res.json()["report"]
    assert report["detected_language"] == "hinglish"
    assert report["preferred_language"] == "hinglish"
    assert report["ai_category"] == "overflowing_bin"

    hindi_res = client.post(
        "/api/reports",
        data={
            "description": "मोहल्ले में तीन दिन से कचरा गाड़ी नहीं आई है और गंदगी बढ़ रही है।",
            "latitude": "12.9719",
            "longitude": "77.5949",
            "ward_id": str(ward_id),
            "preferred_language": "hi",
        },
    )
    assert hindi_res.status_code == 201
    hi_report = hindi_res.json()["report"]
    assert hi_report["detected_language"] == "hi"
    assert hi_report["ai_category"] == "missed_collection"


def test_voice_audio_upload_validation_and_persistence(client):
    wards = client.get("/api/wards").json()
    ward_id = wards[0]["id"]

    bad_audio = client.post(
        "/api/reports",
        data={
            "description": "",
            "latitude": "12.9720",
            "longitude": "77.5950",
            "ward_id": str(ward_id),
        },
        files={"audio": ("bad.wav", b"not-a-valid-wav-file", "audio/wav")},
    )
    assert bad_audio.status_code == 422

    wav_res = client.post(
        "/api/reports",
        data={
            "description": "",
            "latitude": "12.9720",
            "longitude": "77.5950",
            "ward_id": str(ward_id),
            "preferred_language": "hi",
        },
        files={"audio": ("complaint.wav", _minimal_wav_bytes(), "audio/wav")},
    )
    assert wav_res.status_code == 201
    payload = wav_res.json()
    report = payload["report"]
    assert report["voice_transcript"] is not None
    assert "Voice note attached" in report["voice_transcript"]
    audio_assets = [m for m in report["media"] if m["kind"] == "report_audio"]
    assert len(audio_assets) == 1

    operator = login_headers(client, "demo.operator@civicops.local")
    media_id = audio_assets[0]["id"]
    assert client.get(f"/api/media/{media_id}").status_code == 401
    media_fetch = client.get(f"/api/media/{media_id}", headers=operator)
    assert media_fetch.status_code == 200
    assert media_fetch.headers["content-type"].startswith("audio/wav")


def test_gemini_voice_transcription_persists(client, monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "category": "garbage_accumulation",
                                            "severity": "high",
                                            "summary": "Resident reported 3-day garbage buildup near school gate in Hindi.",
                                            "visible_indicators": ["garbage buildup", "voice report"],
                                            "confidence": 0.91,
                                            "rationale": "Voice recording describes persistent waste pile near school.",
                                            "voice_transcript": "स्कूल गेट के पास तीन दिन से कचरा पड़ा है।",
                                            "detected_language": "hi",
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            }

    monkeypatch.setattr(settings, "gemini_api_key", "fake-test-key")
    monkeypatch.setattr("app.services.triage.httpx.post", lambda *a, **kw: FakeResponse())

    wards = client.get("/api/wards").json()
    res = client.post(
        "/api/reports",
        data={
            "description": "",
            "latitude": "12.9722",
            "longitude": "77.5952",
            "ward_id": str(wards[0]["id"]),
            "preferred_language": "hi",
        },
        files={"audio": ("voice.wav", _minimal_wav_bytes(), "audio/wav")},
    )
    assert res.status_code == 201
    report = res.json()["report"]
    assert report["ai_provider"] == "google-gemini"
    assert report["detected_language"] == "hi"
    assert report["voice_transcript"] == "स्कूल गेट के पास तीन दिन से कचरा पड़ा है।"
    assert report["ai_category"] == "garbage_accumulation"


def test_local_stt_fallback_transcribes_and_handles_missing_package(client, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.setattr(settings, "local_stt_enabled", True)

    # 1. Mock local STT returning a Hinglish transcript
    monkeypatch.setattr(
        "app.services.triage.transcribe_audio_local",
        lambda audio, content_type=None: (
            "Main road ke paas kudedan bhar gaya hai.",
            "hi",
        ),
    )
    wards = client.get("/api/wards").json()
    res = client.post(
        "/api/reports",
        data={
            "description": "",
            "latitude": "12.9724",
            "longitude": "77.5954",
            "ward_id": str(wards[0]["id"]),
            "preferred_language": "hi",
        },
        files={"audio": ("local.wav", _minimal_wav_bytes(), "audio/wav")},
    )
    assert res.status_code == 201
    report = res.json()["report"]
    assert report["voice_transcript"] == "Main road ke paas kudedan bhar gaya hai."
    assert report["detected_language"] == "hi"
    assert report["ai_category"] == "overflowing_bin"

    # 2. When local STT is unavailable (returns None, None), report still succeeds safely
    monkeypatch.setattr(
        "app.services.triage.transcribe_audio_local",
        lambda audio, content_type=None: (None, None),
    )
    res_unavail = client.post(
        "/api/reports",
        data={
            "description": "",
            "latitude": "12.9725",
            "longitude": "77.5955",
            "ward_id": str(wards[0]["id"]),
        },
        files={"audio": ("offline.wav", _minimal_wav_bytes(), "audio/wav")},
    )
    assert res_unavail.status_code == 201
    assert "Voice note attached" in res_unavail.json()["report"]["voice_transcript"]


