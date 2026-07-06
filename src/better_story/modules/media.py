from __future__ import annotations

from pathlib import Path

from better_story.modules.task import source_video_path
from better_story.utils.ffmpeg import extract_wav, ffprobe_json, media_duration
from better_story.utils.json_io import write_json


def prepare_media(task_dir: Path) -> None:
    source = source_video_path(task_dir)
    info = ffprobe_json(source)
    info["better_story"] = {"duration_sec": media_duration(info)}
    write_json(task_dir / "analysis" / "media_info.json", info)
    extract_wav(source, task_dir / "audio" / "source.wav")
