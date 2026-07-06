from __future__ import annotations

from pathlib import Path

from better_story.utils.json_io import read_json, write_json


def write_qc_report(task_dir: Path) -> None:
    issues = []
    script_path = task_dir / "rewrite" / "narration_script.json"
    aligned_path = task_dir / "rewrite" / "aligned_script.json"
    edl_path = task_dir / "edit" / "edl.json"

    if script_path.exists():
        script = read_json(script_path)
        for line in script.get("lines", []):
            if not line.get("source_beat_ids"):
                issues.append({"level": "error", "message": f"{line['line_id']} has no source_beat_ids"})
    if aligned_path.exists():
        aligned = read_json(aligned_path)
        for line in aligned.get("lines", []):
            if not line.get("selected_range"):
                issues.append({"level": "error", "message": f"{line['line_id']} has no selected_range"})
    if edl_path.exists():
        edl = read_json(edl_path)
        if not edl.get("clips"):
            issues.append({"level": "error", "message": "EDL has no clips"})

    write_json(
        task_dir / "rewrite" / "qc_report.json",
        {
            "ok": not any(item["level"] == "error" for item in issues),
            "issues": issues,
        },
    )
