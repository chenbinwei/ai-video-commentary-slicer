"""Local registry for cloned voice ids.

The registry is intentionally local-only because it may reveal private voice
model ids and reference-audio filenames.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_REGISTRY_PATH = Path("assets/voice_refs/fish_voice_models.local.json")


def load_registry(path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"voices": []}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_registry(registry: dict[str, Any], path: Path = DEFAULT_REGISTRY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")


def list_voices(path: Path = DEFAULT_REGISTRY_PATH) -> list[dict[str, Any]]:
    registry = load_registry(path)
    voices = registry.get("voices", [])
    if not isinstance(voices, list):
        return []
    return [voice for voice in voices if isinstance(voice, dict)]


def find_voice(name_or_id: str, path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, Any] | None:
    for voice in list_voices(path):
        if voice.get("name") == name_or_id or voice.get("reference_id") == name_or_id:
            return voice
    return None


def upsert_voice(
    *,
    name: str,
    reference_id: str,
    provider: str = "fish_audio",
    source_audio: str | list[str] | None = None,
    note: str = "",
    metadata: dict[str, Any] | None = None,
    path: Path = DEFAULT_REGISTRY_PATH,
) -> dict[str, Any]:
    registry = load_registry(path)
    voices = registry.setdefault("voices", [])
    if not isinstance(voices, list):
        voices = []
        registry["voices"] = voices

    record: dict[str, Any] = {
        "name": name,
        "provider": provider,
        "reference_id": reference_id,
        "source_audio": source_audio or "",
        "note": note,
    }
    if metadata:
        record["metadata"] = metadata

    for index, voice in enumerate(voices):
        if voice.get("name") == name or voice.get("reference_id") == reference_id:
            voices[index] = record
            break
    else:
        voices.append(record)

    save_registry(registry, path)
    return record
