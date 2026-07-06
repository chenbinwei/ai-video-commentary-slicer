from __future__ import annotations

from pathlib import Path
from typing import Any

from better_story.modules.transcribe import apply_character_map_data
from better_story.utils.json_io import read_json, write_json


def apply_character_map(task_dir: Path, character_map: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    utterances = read_json(task_dir / "analysis" / "utterances.json")
    if character_map is None:
        character_map = read_json(task_dir / "analysis" / "character_map.json")
    updated = apply_character_map_data(utterances, character_map)
    write_json(task_dir / "analysis" / "character_map.json", character_map)
    write_json(task_dir / "analysis" / "utterances_with_characters.json", updated)
    return updated
