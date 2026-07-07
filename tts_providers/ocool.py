"""OCool/OpenAI-compatible TTS provider."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def synthesize_batch(
    items: list[dict[str, Any]],
    *,
    model: str,
    voice: str,
    base_url: str,
    speed: float,
    api_key: str | None = None,
) -> None:
    api_key = api_key or os.environ.get("OCOOL_API_KEY")
    if not api_key:
        raise SystemExit("OCOOL_API_KEY is required for OCool TTS.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SystemExit(
            "OpenAI SDK is required for OCool calls. Run: .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt"
        ) from exc

    client = OpenAI(api_key=api_key, base_url=base_url)
    for item in items:
        output_path = Path(item["audio_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=str(item["text"]),
            speed=speed,
        )
        response.write_to_file(output_path)
