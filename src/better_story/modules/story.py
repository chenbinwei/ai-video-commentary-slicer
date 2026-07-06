from __future__ import annotations

from pathlib import Path
from typing import Any

from better_story.config import load_config
from better_story.providers.base import AIProvider
from better_story.utils.json_io import read_json, write_json


def extract_story(task_dir: Path, provider: AIProvider) -> None:
    config = load_config(task_dir)
    utterances_path = task_dir / "analysis" / "utterances_with_characters.json"
    utterances = read_json(utterances_path) if utterances_path.exists() else read_json(task_dir / "analysis" / "utterances.json")
    result = provider.extract_story_beats(utterances, target_language=config.narration_language)
    beats = normalize_beats(result.get("beats", []), utterances)
    write_json(task_dir / "analysis" / "story_beats.json", {"beats": beats})
    write_json(
        task_dir / "rewrite" / "outline.json",
        {
            "title": "Auto-generated outline",
            "beat_count": len(beats),
            "beats": [
                {
                    "beat_id": beat["beat_id"],
                    "title": beat["title"],
                    "summary": beat["summary"],
                    "importance": beat["importance"],
                }
                for beat in beats
            ],
        },
    )


def normalize_beats(beats: list[dict[str, Any]], utterances: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["utterance_id"]: item for item in utterances}
    normalized = []
    for index, beat in enumerate(beats):
        source_ids = [u for u in beat.get("source_utterance_ids", []) if u in by_id]
        if source_ids:
            start = min(by_id[u]["start"] for u in source_ids)
            end = max(by_id[u]["end"] for u in source_ids)
        else:
            start = float(beat.get("start", 0.0))
            end = float(beat.get("end", start + 5.0))
        normalized.append(
            {
                "beat_id": beat.get("beat_id") or f"beat_{index + 1:04}",
                "start": round(start, 3),
                "end": round(max(end, start + 1.0), 3),
                "title": str(beat.get("title") or f"Beat {index + 1}"),
                "summary": str(beat.get("summary") or ""),
                "characters": beat.get("characters") or [],
                "source_utterance_ids": source_ids,
                "importance": float(beat.get("importance", 0.5)),
                "main_plot": bool(beat.get("main_plot", True)),
            }
        )
    normalized.sort(key=lambda item: (item["start"], item["end"]))
    return normalized
