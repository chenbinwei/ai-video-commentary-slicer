from __future__ import annotations

from pathlib import Path

from better_story.utils.ffmpeg import media_duration
from better_story.utils.json_io import read_json, write_json
from better_story.utils.timecode import overlap_seconds


def build_scenes(task_dir: Path, *, scene_length_sec: float = 20.0) -> None:
    media_info = read_json(task_dir / "analysis" / "media_info.json")
    duration = float(media_info.get("better_story", {}).get("duration_sec") or media_duration(media_info))
    utterances_path = task_dir / "analysis" / "utterances_with_characters.json"
    utterances = read_json(utterances_path) if utterances_path.exists() else read_json(task_dir / "analysis" / "utterances.json")
    scenes = []
    cursor = 0.0
    index = 1
    while cursor < duration:
        end = min(duration, cursor + scene_length_sec)
        scene_utterances = [
            item for item in utterances if overlap_seconds(cursor, end, item["start"], item["end"]) > 0
        ]
        scenes.append(
            {
                "scene_id": f"scene_{index:04}",
                "start": round(cursor, 3),
                "end": round(end, 3),
                "utterance_ids": [item["utterance_id"] for item in scene_utterances],
                "characters": sorted({item.get("character_name", "未知") for item in scene_utterances}),
            }
        )
        cursor = end
        index += 1
    write_json(task_dir / "analysis" / "scenes.json", {"scenes": scenes})
