from __future__ import annotations

from pathlib import Path

from better_story.utils.json_io import read_json, write_json


def align_script(task_dir: Path) -> None:
    script = read_json(task_dir / "rewrite" / "narration_script.json")
    story = read_json(task_dir / "analysis" / "story_beats.json")
    beats = {beat["beat_id"]: beat for beat in story.get("beats", [])}
    aligned_lines = []
    for line in script.get("lines", []):
        candidate_ranges = []
        for beat_id in line.get("source_beat_ids", []):
            beat = beats.get(beat_id)
            if not beat:
                continue
            candidate_ranges.append(
                {
                    "start": beat["start"],
                    "end": beat["end"],
                    "score": beat.get("importance", 0.5),
                    "reason": beat.get("title", "linked story beat"),
                }
            )
        if not candidate_ranges:
            candidate_ranges.append(
                {
                    "start": 0.0,
                    "end": max(2.0, line.get("expected_duration_sec", 2.0)),
                    "score": 0.1,
                    "reason": "fallback range",
                }
            )
        selected = sorted(candidate_ranges, key=lambda item: item["score"], reverse=True)[0]
        aligned = dict(line)
        aligned["candidate_ranges"] = candidate_ranges
        aligned["selected_range"] = {"start": selected["start"], "end": selected["end"]}
        aligned_lines.append(aligned)
    output = dict(script)
    output["lines"] = aligned_lines
    write_json(task_dir / "rewrite" / "aligned_script.json", output)
