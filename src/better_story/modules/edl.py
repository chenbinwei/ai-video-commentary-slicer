from __future__ import annotations

from pathlib import Path

from better_story.config import load_config
from better_story.utils.ffmpeg import media_duration
from better_story.utils.json_io import read_json, write_json
from better_story.utils.timecode import clamp, srt_timestamp


def build_edl(task_dir: Path) -> None:
    config = load_config(task_dir)
    media_info = read_json(task_dir / "analysis" / "media_info.json")
    video_duration = float(media_info.get("better_story", {}).get("duration_sec") or media_duration(media_info))
    aligned = read_json(task_dir / "rewrite" / "aligned_script.json")
    tts_segments = read_json(task_dir / "audio" / "narration_segments.json").get("segments", [])
    by_line = {item["line_id"]: item for item in tts_segments}

    clips = []
    subtitles = []
    output_cursor = 0.0
    for index, line in enumerate(aligned.get("lines", [])):
        audio = by_line.get(line["line_id"])
        duration = float(audio.get("duration_sec") if audio else line.get("expected_duration_sec", 3.0))
        selected = line.get("selected_range") or {"start": 0.0, "end": duration}
        source_start = float(selected["start"])
        source_end = float(selected["end"])
        if source_end - source_start < duration:
            source_end = source_start + duration
        if source_end > video_duration:
            source_end = video_duration
            source_start = clamp(video_duration - duration, 0.0, video_duration)
        source_start = clamp(source_start, 0.0, max(0.0, video_duration - 0.1))
        source_end = clamp(source_start + duration, source_start + 0.1, video_duration)
        output_start = output_cursor
        output_end = output_start + (source_end - source_start)
        clips.append(
            {
                "clip_id": f"clip_{index + 1:04}",
                "source_start": round(source_start, 3),
                "source_end": round(source_end, 3),
                "output_start": round(output_start, 3),
                "output_end": round(output_end, 3),
                "script_line_ids": [line["line_id"]],
                "narration_audio": audio.get("audio_path") if audio else None,
                "source_audio_gain": 0.0,
                "narration_gain": 1.0,
            }
        )
        subtitles.append(
            {
                "index": index + 1,
                "start": output_start,
                "end": output_end,
                "text": line["text"],
            }
        )
        output_cursor = output_end

    edl = {
        "target_duration_sec": config.target_duration_sec,
        "actual_duration_sec": round(output_cursor, 3),
        "output_profile": config.output_profile,
        "clips": clips,
    }
    write_json(task_dir / "edit" / "edl.json", edl)
    write_srt(task_dir / "edit" / "subtitles.srt", subtitles)


def write_srt(path: Path, subtitles: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    chunks = []
    for item in subtitles:
        text = str(item["text"]).replace("\n", " ").strip()
        chunks.append(
            f"{item['index']}\n{srt_timestamp(item['start'])} --> {srt_timestamp(item['end'])}\n{text}\n"
        )
    path.write_text("\n".join(chunks), encoding="utf-8")
