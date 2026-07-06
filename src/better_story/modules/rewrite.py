from __future__ import annotations

from pathlib import Path
from typing import Any

from better_story.config import load_config
from better_story.providers.base import AIProvider
from better_story.utils.audio import estimate_tts_duration
from better_story.utils.json_io import read_json, write_json


def write_script(task_dir: Path, provider: AIProvider) -> None:
    config = load_config(task_dir)
    story = read_json(task_dir / "analysis" / "story_beats.json")
    beats = story.get("beats", [])
    result = provider.write_narration_script(
        beats,
        target_duration_sec=config.target_duration_sec,
        narration_language=config.narration_language,
    )
    script = normalize_script(result, beats, config.target_duration_sec, config.narration_language)
    write_json(task_dir / "rewrite" / "narration_script.json", script)
    script_text = "\n".join(item["text"] for item in script["lines"])
    (task_dir / "rewrite" / "script.txt").write_text(script_text, encoding="utf-8")


def normalize_script(
    script: dict[str, Any],
    beats: list[dict[str, Any]],
    target_duration_sec: int,
    language: str,
) -> dict[str, Any]:
    beat_ids = {beat["beat_id"] for beat in beats}
    lines = []
    for index, line in enumerate(script.get("lines", [])):
        source_ids = [beat_id for beat_id in line.get("source_beat_ids", []) if beat_id in beat_ids]
        if not source_ids and beats:
            source_ids = [beats[min(index, len(beats) - 1)]["beat_id"]]
        text = str(line.get("text", "")).strip()
        if not text:
            continue
        lines.append(
            {
                "line_id": line.get("line_id") or f"line_{len(lines) + 1:04}",
                "text": text,
                "source_beat_ids": source_ids,
                "expected_duration_sec": float(
                    line.get("expected_duration_sec") or estimate_tts_duration(text, language)
                ),
                "importance": float(line.get("importance", 0.5)),
            }
        )
    return {
        "script_id": script.get("script_id", "script_001"),
        "target_duration_sec": int(script.get("target_duration_sec") or target_duration_sec),
        "language": script.get("language") or language,
        "lines": lines,
    }
