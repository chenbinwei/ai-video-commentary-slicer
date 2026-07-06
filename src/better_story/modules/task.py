from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from better_story.config import TaskConfig, save_config
from better_story.utils.json_io import write_json


def create_task(config: TaskConfig, *, runs_dir: Path = Path("runs")) -> Path:
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    task_dir = runs_dir / task_id
    input_dir = task_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=False)

    source = Path(config.video_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Video not found: {source}")
    dest = input_dir / f"source{source.suffix.lower()}"
    if config.copy_input:
        shutil.copy2(source, dest)
    else:
        try:
            dest.symlink_to(source)
        except OSError:
            shutil.copy2(source, dest)
    config.video_path = str(dest)
    save_config(task_dir, config)

    for child in ["analysis", "audio", "rewrite", "edit", "output", "logs", "tmp"]:
        (task_dir / child).mkdir(parents=True, exist_ok=True)
    write_json(
        task_dir / "status.json",
        {
            "task_id": task_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "status": "created",
        },
    )
    return task_dir


def source_video_path(task_dir: Path) -> Path:
    input_dir = task_dir / "input"
    matches = sorted(input_dir.glob("source.*"))
    if not matches:
        raise FileNotFoundError(f"No source video found under {input_dir}")
    return matches[0]
