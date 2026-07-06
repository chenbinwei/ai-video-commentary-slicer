from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path
from typing import Any


class FFmpegError(RuntimeError):
    pass


def run_command(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        pretty = " ".join(shlex.quote(a) for a in args)
        raise FFmpegError(f"Command failed: {pretty}\n{result.stderr.strip()}")
    return result


def ffprobe_json(video_path: Path) -> dict[str, Any]:
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]
    )
    return json.loads(result.stdout)


def media_duration(info: dict[str, Any]) -> float:
    duration = info.get("format", {}).get("duration")
    if duration is not None:
        return float(duration)
    for stream in info.get("streams", []):
        if "duration" in stream:
            return float(stream["duration"])
    return 0.0


def extract_wav(video_path: Path, output_path: Path, sample_rate: int = 16000) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ]
    )


def trim_media(
    source_video: Path,
    output_path: Path,
    start: float,
    duration: float,
    output_profile: str,
    *,
    include_audio: bool = False,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    vf = video_filter(output_profile)
    args = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(source_video),
        "-vf",
        vf,
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
    ]
    if include_audio:
        args.extend(["-c:a", "aac", "-b:a", "128k"])
    else:
        args.extend(["-an"])
    args.append(str(output_path))
    run_command(args)


def video_filter(output_profile: str) -> str:
    if output_profile == "vertical_9_16_blur_bg":
        return (
            "split=2[base][fg];"
            "[base]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,boxblur=20:1[bg];"
            "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fg2];"
            "[bg][fg2]overlay=(W-w)/2:(H-h)/2,setsar=1"
        )
    return "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1"


def concat_files(list_path: Path, output_path: Path, *, reencode: bool = False) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
    ]
    if reencode:
        args.extend(["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"])
    else:
        args.extend(["-c", "copy"])
    args.append(str(output_path))
    run_command(args)


def mux_video_audio(video_path: Path, audio_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ]
    )
