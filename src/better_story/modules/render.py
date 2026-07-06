from __future__ import annotations

from pathlib import Path

from better_story.config import load_config
from better_story.modules.task import source_video_path
from better_story.utils.ffmpeg import concat_files, mux_video_audio, trim_media
from better_story.utils.json_io import read_json


def render_video(task_dir: Path) -> Path:
    config = load_config(task_dir)
    source = source_video_path(task_dir)
    edl = read_json(task_dir / "edit" / "edl.json")
    clips_dir = task_dir / "tmp" / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    clip_paths = []
    for clip in edl.get("clips", []):
        clip_path = clips_dir / f"{clip['clip_id']}.mp4"
        duration = float(clip["source_end"]) - float(clip["source_start"])
        trim_media(
            source,
            clip_path,
            float(clip["source_start"]),
            duration,
            config.output_profile,
            include_audio=False,
        )
        clip_paths.append(clip_path)

    video_list = task_dir / "tmp" / "video_concat.txt"
    video_list.write_text(
        "".join(f"file '{path.resolve()}'\n" for path in clip_paths),
        encoding="utf-8",
    )
    silent_video = task_dir / "tmp" / "recap_video.mp4"
    concat_files(video_list, silent_video)

    narration = task_dir / "audio" / "narration.wav"
    output = task_dir / "output" / "recap.mp4"
    if narration.exists():
        mux_video_audio(silent_video, narration, output)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        silent_video.replace(output)
    return output
