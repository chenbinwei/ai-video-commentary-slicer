"""Fish Audio TTS provider and voice model creation."""

from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from typing import Any

import requests


DEFAULT_BASE_URL = "https://api.fish.audio"


def _api_key(api_key: str | None = None) -> str:
    value = api_key or os.environ.get("FISH_API_KEY")
    if not value:
        raise SystemExit("FISH_API_KEY is required for Fish Audio.")
    return value


def _base_url(base_url: str | None = None) -> str:
    return (base_url or os.environ.get("FISH_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def synthesize_batch(
    items: list[dict[str, Any]],
    *,
    reference_id: str,
    model: str = "s2.1-pro-free",
    base_url: str | None = None,
    api_key: str | None = None,
    speed: float = 1.0,
    volume: float = 0.0,
    temperature: float = 0.7,
    top_p: float = 0.7,
    latency: str = "normal",
    mp3_bitrate: int = 128,
) -> None:
    if not reference_id:
        raise SystemExit("FISH_REFERENCE_ID is required for --tts-mode fish.")

    headers = {
        "Authorization": f"Bearer {_api_key(api_key)}",
        "Content-Type": "application/json",
        "model": model,
    }
    url = f"{_base_url(base_url)}/v1/tts"
    for item in items:
        output_path = Path(item["audio_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "text": str(item["text"]),
            "reference_id": reference_id,
            "temperature": temperature,
            "top_p": top_p,
            "prosody": {
                "speed": speed,
                "volume": volume,
                "normalize_loudness": True,
            },
            "chunk_length": 300,
            "normalize": True,
            "format": "mp3",
            "sample_rate": 44100,
            "mp3_bitrate": mp3_bitrate,
            "latency": latency,
            "max_new_tokens": 1024,
            "repetition_penalty": 1.2,
            "min_chunk_length": 50,
            "condition_on_previous_chunks": True,
            "early_stop_threshold": 1,
        }
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=120)
        if response.status_code >= 400:
            raise SystemExit(f"Fish Audio TTS failed ({response.status_code}): {response.text}")
        output_path.write_bytes(response.content)


def create_voice_model(
    *,
    audio_paths: list[Path],
    title: str,
    base_url: str | None = None,
    api_key: str | None = None,
    description: str = "",
    visibility: str = "private",
    texts: list[str] | None = None,
    enhance_audio_quality: bool = True,
) -> dict[str, Any]:
    if not audio_paths:
        raise SystemExit("At least one Fish reference audio file is required.")

    files: list[tuple[str, tuple[str, Any, str]]] = []
    handles = []
    try:
        for audio_path in audio_paths:
            if not audio_path.exists():
                raise SystemExit(f"Fish reference audio not found: {audio_path}")
            mime = mimetypes.guess_type(str(audio_path))[0] or "application/octet-stream"
            handle = audio_path.open("rb")
            handles.append(handle)
            files.append(("voices", (audio_path.name, handle, mime)))

        data: dict[str, Any] = {
            "type": "tts",
            "title": title,
            "train_mode": "fast",
            "visibility": visibility,
            "description": description,
            "enhance_audio_quality": str(enhance_audio_quality).lower(),
            "generate_sample": "false",
        }
        if texts:
            for text in texts:
                data.setdefault("texts", [])
                data["texts"].append(text)

        response = requests.post(
            f"{_base_url(base_url)}/model",
            headers={"Authorization": f"Bearer {_api_key(api_key)}"},
            data=data,
            files=files,
            timeout=180,
        )
        if response.status_code >= 400:
            raise SystemExit(f"Fish Audio model creation failed ({response.status_code}): {response.text}")
        return response.json()
    finally:
        for handle in handles:
            handle.close()
