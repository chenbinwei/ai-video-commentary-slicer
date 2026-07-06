from __future__ import annotations

from pathlib import Path
import shutil

from better_story.providers.base import AIProvider
from better_story.utils.audio import wav_duration
from better_story.utils.ffmpeg import concat_files, run_command
from better_story.utils.json_io import read_json, write_json


def synthesize_narration(task_dir: Path, provider: AIProvider) -> None:
    script = read_json(task_dir / "rewrite" / "narration_script.json")
    language = script.get("language", "zh-CN")
    tts_dir = task_dir / "audio" / "tts"
    segments = []
    for index, line in enumerate(script.get("lines", [])):
        output_path = tts_dir / f"{line['line_id']}.wav"
        duration = provider.synthesize_speech(line["text"], output_path, language=language)
        segments.append(
            {
                "line_id": line["line_id"],
                "text": line["text"],
                "audio_path": str(output_path.relative_to(task_dir)),
                "duration_sec": round(duration, 3),
            }
        )
    write_json(task_dir / "audio" / "narration_segments.json", {"segments": segments})
    concat_list = task_dir / "tmp" / "tts_concat.txt"
    concat_list.parent.mkdir(parents=True, exist_ok=True)
    concat_list.write_text(
        "".join(f"file '{(task_dir / item['audio_path']).resolve()}'\n" for item in segments),
        encoding="utf-8",
    )
    if segments:
        concat_files(concat_list, task_dir / "audio" / "narration.wav")


def export_tts_text(task_dir: Path) -> Path:
    script = read_json(task_dir / "rewrite" / "narration_script.json")
    lines = script.get("lines", [])
    plain_text = "\n".join(line["text"] for line in lines)
    numbered = "\n".join(f"{line['line_id']}\t{line['text']}" for line in lines)
    output = task_dir / "rewrite" / "tts_text_for_external.txt"
    numbered_output = task_dir / "rewrite" / "tts_lines_for_external.tsv"
    output.write_text(plain_text + "\n", encoding="utf-8")
    numbered_output.write_text(numbered + "\n", encoding="utf-8")
    return output


def import_external_narration(task_dir: Path, audio_path: Path) -> None:
    if not audio_path.exists():
        raise FileNotFoundError(f"External narration audio not found: {audio_path}")
    script = read_json(task_dir / "rewrite" / "narration_script.json")
    output = task_dir / "audio" / "narration.wav"
    output.parent.mkdir(parents=True, exist_ok=True)

    if audio_path.suffix.lower() == ".wav":
        shutil.copy2(audio_path, output)
    else:
        run_command(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(audio_path),
                "-ac",
                "1",
                "-ar",
                "24000",
                "-c:a",
                "pcm_s16le",
                str(output),
            ]
        )

    total_duration = wav_duration(output)
    lines = script.get("lines", [])
    expected_total = sum(max(0.1, float(line.get("expected_duration_sec", 1.0))) for line in lines) or 1.0
    segments = []
    cursor = 0.0
    for index, line in enumerate(lines):
        if index == len(lines) - 1:
            duration = max(0.1, total_duration - cursor)
        else:
            weight = max(0.1, float(line.get("expected_duration_sec", 1.0))) / expected_total
            duration = max(0.1, total_duration * weight)
        segments.append(
            {
                "line_id": line["line_id"],
                "text": line["text"],
                "audio_path": str(output.relative_to(task_dir)),
                "duration_sec": round(duration, 3),
                "external_audio_start": round(cursor, 3),
                "external_audio_end": round(min(total_duration, cursor + duration), 3),
            }
        )
        cursor += duration
    write_json(
        task_dir / "audio" / "narration_segments.json",
        {
            "source": "external_single_audio",
            "audio_path": str(output.relative_to(task_dir)),
            "total_duration_sec": round(total_duration, 3),
            "segments": segments,
        },
    )
