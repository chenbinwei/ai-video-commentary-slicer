# Rendering Module Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract FFmpeg rendering, muxing, BGM mixing, subtitle burning, and media duration helpers from `video_slicer/pipeline.py` into a reusable `video_slicer/rendering.py` module without changing current CLI behavior.

**Architecture:** Keep `video_slicer.pipeline` as the orchestration layer and move media command execution into `video_slicer.rendering`. The new rendering module owns FFmpeg command construction, subprocess execution, media duration probing, clip rendering, audio muxing, BGM mixing, and final duration validation. `pipeline.py` and `scripts/mix_bgm.py` import these functions from the new module, while tests use mocked command runners so unit tests do not require real FFmpeg.

**Tech Stack:** Python 3, standard library `subprocess`, `pathlib.Path`, `json`, `unittest`, `unittest.mock`, FFmpeg/ffprobe for real integration runs.

**Execution Status:** Implemented and verified locally.

## Global Constraints

- Keep common code reusable across videos; do not add video-specific names, plot facts, forbidden terms, or demo-only assumptions to `video_slicer/`, `scripts/`, `llm_providers/`, or `tts_providers/`.
- Do not commit `.env`, `outputs/`, `videos/*.mp4`, `assets/voice_refs/*`, or generated media outputs.
- Preserve current CLI behavior for `scripts.run_pipeline`, `1.py`, and `scripts.mix_bgm`.
- Use TDD for behavior changes: write the failing test, run it and confirm failure, implement the smallest change, then run the test again.
- Do not require real FFmpeg in unit tests; mock `video_slicer.rendering.run`, `video_slicer.rendering.run_capture`, or `subprocess.run`.
- Keep `pipeline.py` as orchestration only; do not move 文案生成, TTS provider calls, context packet logic, project records, or alignment logic in this plan.
- Maintain target duration hard checks already added in `pipeline.py`; rendering refactor must not weaken `validate_requested_target_duration()` or `validate_timeline_duration()`.
- Keep Windows path behavior working in PowerShell; concat list entries must use absolute POSIX-style paths as current code does.

---

## File Structure

Create:

- `video_slicer/rendering.py`
  - Owns FFmpeg/ffprobe command execution and media output helpers.
  - Exports:
    - `run(cmd: list[str], cwd: Path | None = None) -> None`
    - `run_capture(cmd: list[str]) -> str`
    - `ensure_ffmpeg() -> None`
    - `ffprobe_duration_media(media_path: Path) -> float`
    - `ffprobe_duration(video_path: Path) -> float`
    - `burn_subtitles(video_path: Path, subtitle_path: Path, output_path: Path) -> None`
    - `clip_video_silent(video_path: Path, output_dir: Path, clips: list[dict[str, Any]]) -> Path`
    - `render_clips_with_voiceover(video_path: Path, output_dir: Path, clips: list[dict[str, Any]]) -> Path`
    - `write_visual_time_mapping(clips: list[dict[str, Any]], mapping_path: Path) -> None`
    - `mux_voiceover_audio(video_path: Path, voiceover_audio: Path, output_path: Path) -> None`
    - `validate_final_duration(media_path: Path, target_duration: float, tolerance: float, label: str) -> float`
    - `add_background_music(video_path: Path, bgm_audio: Path, output_path: Path, *, bgm_volume: float, voiceover_volume: float, bgm_start: float, bgm_fade_in: float, bgm_fade_out: float) -> None`
- `tests/test_rendering.py`
  - Tests rendering command construction, validation behavior, concat list writing, BGM filter construction, and duration checking with mocks.

Modify:

- `video_slicer/pipeline.py`
  - Remove `subprocess` import if it is no longer used directly.
  - Import rendering functions from `video_slicer.rendering`.
  - Delete moved function definitions after tests pass.
- `scripts/mix_bgm.py`
  - Import `add_background_music` from `video_slicer.rendering`.
  - Keep `load_dotenv` imported from `video_slicer.pipeline` until env loading is extracted in a later plan.
- `tests/test_pipeline.py`
  - Keep pipeline-only tests for target duration and voiceover validation.
  - Do not add rendering tests here.
- `README.md`
  - Update the project structure section to mention `video_slicer/rendering.py`.
- `docs/code-map.zh-CN.md`
  - Move rendering responsibilities from `pipeline.py` to `rendering.py`.
  - Mark rendering split as completed after implementation.

Do not modify:

- `video_slicer/alignment.py`
- `video_slicer/quality_report.py`
- `llm_providers/`
- `tts_providers/`
- `context.example.json`
- `.env`

---

### Task 1: Create Rendering Command and Duration Helpers

**Files:**
- Create: `video_slicer/rendering.py`
- Create: `tests/test_rendering.py`
- Modify: `video_slicer/pipeline.py`

**Interfaces:**
- Consumes: standard library `subprocess`, `Path`, `Any`.
- Produces:
  - `video_slicer.rendering.run(cmd: list[str], cwd: Path | None = None) -> None`
  - `video_slicer.rendering.run_capture(cmd: list[str]) -> str`
  - `video_slicer.rendering.ensure_ffmpeg() -> None`
  - `video_slicer.rendering.ffprobe_duration_media(media_path: Path) -> float`
  - `video_slicer.rendering.ffprobe_duration(video_path: Path) -> float`

- [ ] **Step 1: Write failing tests for command helpers**

Create `tests/test_rendering.py` with this content:

```python
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from video_slicer.rendering import (
    ensure_ffmpeg,
    ffprobe_duration,
    ffprobe_duration_media,
    run,
    run_capture,
)


class RenderingCommandTest(unittest.TestCase):
    def test_run_calls_subprocess_with_optional_cwd(self):
        with patch("video_slicer.rendering.subprocess.run") as mocked_run:
            run(["ffmpeg", "-version"], cwd=Path("outputs"))

        mocked_run.assert_called_once_with(["ffmpeg", "-version"], cwd=Path("outputs"), check=True)

    def test_run_capture_returns_stripped_stdout(self):
        completed = subprocess.CompletedProcess(args=["ffprobe"], returncode=0, stdout="12.345\n", stderr="")
        with patch("video_slicer.rendering.subprocess.run", return_value=completed) as mocked_run:
            result = run_capture(["ffprobe"])

        self.assertEqual(result, "12.345")
        mocked_run.assert_called_once_with(["ffprobe"], check=True, capture_output=True, text=True)

    def test_run_capture_includes_process_detail_on_failure(self):
        error = subprocess.CalledProcessError(
            returncode=2,
            cmd=["ffprobe", "missing.mp4"],
            stderr="missing file",
        )
        with patch("video_slicer.rendering.subprocess.run", side_effect=error):
            with self.assertRaises(SystemExit) as ctx:
                run_capture(["ffprobe", "missing.mp4"])

        self.assertIn("missing file", str(ctx.exception))
        self.assertIn("ffprobe missing.mp4", str(ctx.exception))

    def test_ensure_ffmpeg_checks_ffmpeg_and_ffprobe(self):
        with patch("video_slicer.rendering.subprocess.run") as mocked_run:
            ensure_ffmpeg()

        self.assertEqual(mocked_run.call_count, 2)
        self.assertEqual(mocked_run.call_args_list[0].args[0], ["ffmpeg", "-version"])
        self.assertEqual(mocked_run.call_args_list[1].args[0], ["ffprobe", "-version"])

    def test_ffprobe_duration_media_parses_duration(self):
        with patch("video_slicer.rendering.run_capture", return_value="90.004") as mocked_capture:
            duration = ffprobe_duration_media(Path("outputs/output.mp4"))

        self.assertEqual(duration, 90.004)
        mocked_capture.assert_called_once_with([
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            "outputs\\output.mp4" if "\\" in str(Path("outputs/output.mp4")) else "outputs/output.mp4",
        ])

    def test_ffprobe_duration_delegates_to_media_duration(self):
        with patch("video_slicer.rendering.ffprobe_duration_media", return_value=12.5) as mocked_duration:
            duration = ffprobe_duration(Path("videos/input.mp4"))

        self.assertEqual(duration, 12.5)
        mocked_duration.assert_called_once_with(Path("videos/input.mp4"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail because module is missing**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_rendering
```

Expected: FAIL or ERROR with `ModuleNotFoundError: No module named 'video_slicer.rendering'`.

- [ ] **Step 3: Create `video_slicer/rendering.py` with command helpers**

Create `video_slicer/rendering.py`:

```python
"""FFmpeg rendering, muxing, and media probing helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("$ " + " ".join(cmd))
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
    except FileNotFoundError as exc:
        raise SystemExit(f"Command not found: {cmd[0]}. Install it and try again.") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Command failed with exit code {exc.returncode}: {' '.join(cmd)}") from exc


def run_capture(cmd: list[str]) -> str:
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise SystemExit(f"Command not found: {cmd[0]}. Install it and try again.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise SystemExit(f"Command failed with exit code {exc.returncode}: {' '.join(cmd)}\n{detail}") from exc
    return result.stdout.strip()


def ensure_ffmpeg() -> None:
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        subprocess.run(["ffprobe", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except Exception as exc:
        raise SystemExit("FFmpeg/ffprobe is required. Install FFmpeg and make sure it is in PATH.") from exc


def ffprobe_duration_media(media_path: Path) -> float:
    value = run_capture([
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(media_path),
    ])
    if not value or value == "N/A":
        raise SystemExit(f"Could not read media duration: {media_path}")
    return float(value)


def ffprobe_duration(video_path: Path) -> float:
    return ffprobe_duration_media(video_path)
```

- [ ] **Step 4: Update `pipeline.py` imports for helper functions**

In `video_slicer/pipeline.py`, add this import block after the existing quality report import:

```python
from video_slicer.rendering import (
    ensure_ffmpeg,
    ffprobe_duration,
    ffprobe_duration_media,
    run,
    run_capture,
)
```

Then remove these function definitions from `video_slicer/pipeline.py`:

```python
def run(cmd: list[str], cwd: Path | None = None) -> None:
def run_capture(cmd: list[str]) -> str:
def ensure_ffmpeg() -> None:
def ffprobe_duration_media(media_path: Path) -> float:
def ffprobe_duration(video_path: Path) -> float:
```

If `subprocess` is no longer used in `pipeline.py`, remove:

```python
import subprocess
```

- [ ] **Step 5: Run tests for Task 1**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_rendering tests.test_pipeline
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 1**

Run:

```powershell
git add video_slicer/rendering.py video_slicer/pipeline.py tests/test_rendering.py
git commit -m "refactor: extract rendering command helpers"
```

---

### Task 2: Move Silent Clip Rendering and Time Mapping

**Files:**
- Modify: `video_slicer/rendering.py`
- Modify: `video_slicer/pipeline.py`
- Modify: `tests/test_rendering.py`

**Interfaces:**
- Consumes:
  - `run(cmd: list[str], cwd: Path | None = None) -> None`
- Produces:
  - `clip_video_silent(video_path: Path, output_dir: Path, clips: list[dict[str, Any]]) -> Path`
  - `write_visual_time_mapping(clips: list[dict[str, Any]], mapping_path: Path) -> None`

- [ ] **Step 1: Write failing tests for silent rendering**

Append these tests inside `RenderingCommandTest` in `tests/test_rendering.py`:

```python
    def test_clip_video_silent_writes_concat_list_and_runs_expected_commands(self):
        from tempfile import TemporaryDirectory

        from video_slicer.rendering import clip_video_silent

        clips = [
            {"id": 1, "source_start": 10.0, "duration": 3.5},
            {"id": 2, "source_start": 20.25, "duration": 4.0},
        ]
        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            with patch("video_slicer.rendering.run") as mocked_run:
                output_path = clip_video_silent(Path("videos/input.mp4"), output_dir, clips)

            self.assertEqual(output_path, output_dir / "output.mp4")
            self.assertEqual(mocked_run.call_count, 3)
            first_cmd = mocked_run.call_args_list[0].args[0]
            self.assertEqual(first_cmd[:8], ["ffmpeg", "-y", "-ss", "10.000", "-i", "videos\\input.mp4" if "\\" in str(Path("videos/input.mp4")) else "videos/input.mp4", "-t", "3.500"])
            self.assertIn("-an", first_cmd)
            concat_list = output_dir / "concat_list.txt"
            concat_text = concat_list.read_text(encoding="utf-8")
            self.assertIn("clip_001.mp4", concat_text)
            self.assertIn("clip_002.mp4", concat_text)

    def test_write_visual_time_mapping_writes_new_timeline(self):
        from tempfile import TemporaryDirectory

        from video_slicer.rendering import write_visual_time_mapping

        clips = [
            {
                "id": 1,
                "sentence_ids": [1],
                "source_segment_ids": [10],
                "source_start": 5.0,
                "source_end": 8.0,
                "duration": 3.0,
            },
            {
                "id": 2,
                "sentence_ids": [2],
                "source_segment_ids": [11],
                "source_start": 12.0,
                "source_end": 16.0,
                "duration": 4.0,
            },
        ]
        with TemporaryDirectory() as tmp:
            mapping_path = Path(tmp) / "time_mapping.json"
            write_visual_time_mapping(clips, mapping_path)

            mapping = json.loads(mapping_path.read_text(encoding="utf-8"))

        self.assertEqual(mapping[0]["new_start"], 0.0)
        self.assertEqual(mapping[0]["new_end"], 3.0)
        self.assertEqual(mapping[1]["new_start"], 3.0)
        self.assertEqual(mapping[1]["new_end"], 7.0)
        self.assertEqual(mapping[1]["source_segment_ids"], [11])
```

Add `import json` to the top of `tests/test_rendering.py`:

```python
import json
```

- [ ] **Step 2: Run tests to verify they fail because functions are not in rendering**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_rendering
```

Expected: FAIL or ERROR with import errors for `clip_video_silent` and `write_visual_time_mapping`.

- [ ] **Step 3: Move silent rendering functions into `rendering.py`**

Append these functions to `video_slicer/rendering.py`:

```python
def clip_video_silent(video_path: Path, output_dir: Path, clips: list[dict[str, Any]]) -> Path:
    clips_dir = output_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    clip_files: list[Path] = []

    for clip in clips:
        clip_path = clips_dir / f"clip_{clip['id']:03}.mp4"
        run([
            "ffmpeg",
            "-y",
            "-ss",
            f"{clip['source_start']:.3f}",
            "-i",
            str(video_path),
            "-t",
            f"{clip['duration']:.3f}",
            "-map",
            "0:v:0",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-movflags",
            "+faststart",
            str(clip_path),
        ])
        clip_files.append(clip_path)

    concat_list = output_dir / "concat_list.txt"
    concat_list.write_text("\n".join(f"file '{path.resolve().as_posix()}'" for path in clip_files), encoding="utf-8")

    output_path = output_dir / "output.mp4"
    run([
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
        "-c",
        "copy",
        str(output_path),
    ])
    return output_path


def write_visual_time_mapping(clips: list[dict[str, Any]], mapping_path: Path) -> None:
    mapping: list[dict[str, Any]] = []
    cursor = 0.0
    for clip in clips:
        new_start = cursor
        new_end = cursor + float(clip["duration"])
        mapping.append({
            "clip_id": clip["id"],
            "sentence_ids": clip.get("sentence_ids", []),
            "source_segment_ids": clip.get("source_segment_ids", []),
            "source_start": round(float(clip["source_start"]), 3),
            "source_end": round(float(clip["source_end"]), 3),
            "new_start": round(new_start, 3),
            "new_end": round(new_end, 3),
        })
        cursor = new_end
    mapping_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Update `pipeline.py` imports and delete moved functions**

Extend the `video_slicer.rendering` import in `video_slicer/pipeline.py`:

```python
from video_slicer.rendering import (
    clip_video_silent,
    ensure_ffmpeg,
    ffprobe_duration,
    ffprobe_duration_media,
    run,
    run_capture,
    write_visual_time_mapping,
)
```

Delete these function definitions from `video_slicer/pipeline.py`:

```python
def clip_video_silent(video_path: Path, output_dir: Path, clips: list[dict[str, Any]]) -> Path:
def write_visual_time_mapping(clips: list[dict[str, Any]], mapping_path: Path) -> None:
```

- [ ] **Step 5: Run tests for Task 2**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_rendering tests.test_pipeline
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 2**

Run:

```powershell
git add video_slicer/rendering.py video_slicer/pipeline.py tests/test_rendering.py
git commit -m "refactor: extract silent clip rendering"
```

---

### Task 3: Move Voiceover Rendering and Audio Muxing

**Files:**
- Modify: `video_slicer/rendering.py`
- Modify: `video_slicer/pipeline.py`
- Modify: `tests/test_rendering.py`

**Interfaces:**
- Consumes:
  - `run(cmd: list[str], cwd: Path | None = None) -> None`
- Produces:
  - `render_clips_with_voiceover(video_path: Path, output_dir: Path, clips: list[dict[str, Any]]) -> Path`
  - `mux_voiceover_audio(video_path: Path, voiceover_audio: Path, output_path: Path) -> None`

- [ ] **Step 1: Write failing tests for voiceover rendering and muxing**

Append these tests inside `RenderingCommandTest`:

```python
    def test_render_clips_with_voiceover_requires_audio_path(self):
        from tempfile import TemporaryDirectory

        from video_slicer.rendering import render_clips_with_voiceover

        with TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as ctx:
                render_clips_with_voiceover(
                    Path("videos/input.mp4"),
                    Path(tmp),
                    [{"id": 1, "source_start": 0.0, "duration": 2.0}],
                )

        self.assertIn("missing voiceover_audio_path", str(ctx.exception))

    def test_render_clips_with_voiceover_writes_final_concat(self):
        from tempfile import TemporaryDirectory

        from video_slicer.rendering import render_clips_with_voiceover

        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            audio_path = output_dir / "voice_001.mp3"
            audio_path.write_bytes(b"fake audio")
            clips = [{"id": 1, "source_start": 2.0, "duration": 3.0, "voiceover_audio_path": str(audio_path)}]
            with patch("video_slicer.rendering.run") as mocked_run:
                output_path = render_clips_with_voiceover(Path("videos/input.mp4"), output_dir, clips)

            self.assertEqual(output_path, output_dir / "final_with_voiceover.mp4")
            self.assertEqual(mocked_run.call_count, 2)
            first_cmd = mocked_run.call_args_list[0].args[0]
            self.assertIn(str(audio_path), first_cmd)
            self.assertIn("-shortest", first_cmd)
            concat_text = (output_dir / "final_concat_list.txt").read_text(encoding="utf-8")
            self.assertIn("part_001.mp4", concat_text)

    def test_mux_voiceover_audio_checks_audio_exists_and_runs_mux(self):
        from tempfile import TemporaryDirectory

        from video_slicer.rendering import mux_voiceover_audio

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio_path = root / "voiceover.mp3"
            audio_path.write_bytes(b"fake audio")
            output_path = root / "final.mp4"
            with patch("video_slicer.rendering.run") as mocked_run:
                mux_voiceover_audio(Path("output.mp4"), audio_path, output_path)

        cmd = mocked_run.call_args.args[0]
        self.assertEqual(cmd[:4], ["ffmpeg", "-y", "-i", "output.mp4"])
        self.assertIn(str(audio_path), cmd)
        self.assertIn(str(output_path), cmd)
```

- [ ] **Step 2: Run tests to verify they fail because functions are not in rendering**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_rendering
```

Expected: FAIL or ERROR with import errors for `render_clips_with_voiceover` and `mux_voiceover_audio`.

- [ ] **Step 3: Move voiceover rendering functions into `rendering.py`**

Append these functions to `video_slicer/rendering.py`:

```python
def render_clips_with_voiceover(video_path: Path, output_dir: Path, clips: list[dict[str, Any]]) -> Path:
    clips_dir = output_dir / "final_clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    clip_files: list[Path] = []

    for clip in clips:
        audio_value = clip.get("voiceover_audio_path")
        if not audio_value:
            raise SystemExit("Cannot render final voiceover video: a clip is missing voiceover_audio_path.")
        audio_path = Path(str(audio_value))
        if not audio_path.exists():
            raise SystemExit(f"Voiceover audio not found: {audio_path}")

        clip_path = clips_dir / f"part_{clip['id']:03}.mp4"
        run([
            "ffmpeg",
            "-y",
            "-ss",
            f"{clip['source_start']:.3f}",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-t",
            f"{clip['duration']:.3f}",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(clip_path),
        ])
        clip_files.append(clip_path)

    concat_list = output_dir / "final_concat_list.txt"
    concat_list.write_text("\n".join(f"file '{path.resolve().as_posix()}'" for path in clip_files), encoding="utf-8")

    output_path = output_dir / "final_with_voiceover.mp4"
    run([
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output_path),
    ])
    return output_path


def mux_voiceover_audio(video_path: Path, voiceover_audio: Path, output_path: Path) -> None:
    if not voiceover_audio.exists():
        raise SystemExit(f"Voiceover audio not found: {voiceover_audio}")
    run([
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(voiceover_audio),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        str(output_path),
    ])
```

- [ ] **Step 4: Update `pipeline.py` imports and delete moved functions**

Extend the `video_slicer.rendering` import:

```python
from video_slicer.rendering import (
    clip_video_silent,
    ensure_ffmpeg,
    ffprobe_duration,
    ffprobe_duration_media,
    mux_voiceover_audio,
    render_clips_with_voiceover,
    run,
    run_capture,
    write_visual_time_mapping,
)
```

Delete these function definitions from `video_slicer/pipeline.py`:

```python
def render_clips_with_voiceover(video_path: Path, output_dir: Path, clips: list[dict[str, Any]]) -> Path:
def mux_voiceover_audio(video_path: Path, voiceover_audio: Path, output_path: Path) -> None:
```

- [ ] **Step 5: Run tests for Task 3**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_rendering tests.test_pipeline
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 3**

Run:

```powershell
git add video_slicer/rendering.py video_slicer/pipeline.py tests/test_rendering.py
git commit -m "refactor: extract voiceover rendering"
```

---

### Task 4: Move BGM Mixing, Subtitle Burning, and Final Duration Validation

**Files:**
- Modify: `video_slicer/rendering.py`
- Modify: `video_slicer/pipeline.py`
- Modify: `scripts/mix_bgm.py`
- Modify: `tests/test_rendering.py`

**Interfaces:**
- Consumes:
  - `run(cmd: list[str], cwd: Path | None = None) -> None`
  - `ffprobe_duration_media(media_path: Path) -> float`
- Produces:
  - `burn_subtitles(video_path: Path, subtitle_path: Path, output_path: Path) -> None`
  - `validate_final_duration(media_path: Path, target_duration: float, tolerance: float, label: str) -> float`
  - `add_background_music(video_path: Path, bgm_audio: Path, output_path: Path, *, bgm_volume: float, voiceover_volume: float, bgm_start: float, bgm_fade_in: float, bgm_fade_out: float) -> None`

- [ ] **Step 1: Write failing tests for BGM, subtitles, and duration validation**

Append these tests inside `RenderingCommandTest`:

```python
    def test_validate_final_duration_rejects_target_drift(self):
        from video_slicer.rendering import validate_final_duration

        with patch("video_slicer.rendering.ffprobe_duration_media", return_value=104.0):
            with self.assertRaises(SystemExit) as ctx:
                validate_final_duration(Path("final.mp4"), target_duration=120.0, tolerance=3.0, label="Final")

        self.assertIn("outside tolerance", str(ctx.exception))

    def test_validate_final_duration_returns_duration_when_inside_tolerance(self):
        from video_slicer.rendering import validate_final_duration

        with patch("video_slicer.rendering.ffprobe_duration_media", return_value=119.5):
            duration = validate_final_duration(Path("final.mp4"), target_duration=120.0, tolerance=3.0, label="Final")

        self.assertEqual(duration, 119.5)

    def test_burn_subtitles_escapes_subtitle_path_for_filter(self):
        from video_slicer.rendering import burn_subtitles

        with patch("video_slicer.rendering.run") as mocked_run:
            burn_subtitles(Path("input.mp4"), Path("outputs/subtitle's.srt"), Path("burned.mp4"))

        cmd = mocked_run.call_args.args[0]
        self.assertEqual(cmd[:4], ["ffmpeg", "-y", "-i", "input.mp4"])
        self.assertIn("subtitles='outputs/subtitle\\'s.srt'", cmd)

    def test_add_background_music_validates_non_negative_values(self):
        from tempfile import TemporaryDirectory

        from video_slicer.rendering import add_background_music

        with TemporaryDirectory() as tmp:
            bgm_path = Path(tmp) / "bgm.mp3"
            bgm_path.write_bytes(b"fake bgm")
            with self.assertRaises(SystemExit) as ctx:
                add_background_music(
                    video_path=Path("final.mp4"),
                    bgm_audio=bgm_path,
                    output_path=Path("mixed.mp4"),
                    bgm_volume=-0.1,
                    voiceover_volume=1.0,
                    bgm_start=0.0,
                    bgm_fade_in=0.0,
                    bgm_fade_out=2.5,
                )

        self.assertIn("--bgm-volume", str(ctx.exception))

    def test_add_background_music_builds_filter_with_loop_and_fades(self):
        from tempfile import TemporaryDirectory

        from video_slicer.rendering import add_background_music

        with TemporaryDirectory() as tmp:
            bgm_path = Path(tmp) / "bgm.mp3"
            bgm_path.write_bytes(b"fake bgm")
            with patch("video_slicer.rendering.ffprobe_duration_media", return_value=90.0):
                with patch("video_slicer.rendering.run") as mocked_run:
                    add_background_music(
                        video_path=Path("final_with_voiceover.mp4"),
                        bgm_audio=bgm_path,
                        output_path=Path("final_with_bgm.mp4"),
                        bgm_volume=0.25,
                        voiceover_volume=1.0,
                        bgm_start=1.5,
                        bgm_fade_in=0.8,
                        bgm_fade_out=2.5,
                    )

        cmd = mocked_run.call_args.args[0]
        self.assertIn("-stream_loop", cmd)
        self.assertIn("-1", cmd)
        self.assertIn("1.500", cmd)
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("volume=1.000[voice]", filter_complex)
        self.assertIn("atrim=0:90.000", filter_complex)
        self.assertIn("afade=t=in:st=0:d=0.800", filter_complex)
        self.assertIn("afade=t=out:st=87.500:d=2.500", filter_complex)
        self.assertIn("volume=0.250", filter_complex)
```

- [ ] **Step 2: Run tests to verify they fail because functions are not in rendering**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_rendering
```

Expected: FAIL or ERROR with import errors for `validate_final_duration`, `burn_subtitles`, and `add_background_music`.

- [ ] **Step 3: Move BGM, subtitle, and duration functions into `rendering.py`**

Append these functions to `video_slicer/rendering.py`:

```python
def burn_subtitles(video_path: Path, subtitle_path: Path, output_path: Path) -> None:
    subtitle_arg = subtitle_path.as_posix().replace("'", "\\'")
    run([
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"subtitles='{subtitle_arg}'",
        "-c:a",
        "copy",
        str(output_path),
    ])


def validate_final_duration(media_path: Path, target_duration: float, tolerance: float, label: str) -> float:
    if target_duration <= 0:
        return ffprobe_duration_media(media_path)
    duration = ffprobe_duration_media(media_path)
    delta = abs(duration - target_duration)
    print(f"{label} duration check: {duration:.2f}s target={target_duration:.2f}s delta={delta:.2f}s")
    if delta > tolerance:
        raise SystemExit(
            f"{label} duration is outside tolerance: {duration:.2f}s vs "
            f"{target_duration:.2f}s target (tolerance {tolerance:.2f}s)."
        )
    return duration


def add_background_music(
    video_path: Path,
    bgm_audio: Path,
    output_path: Path,
    *,
    bgm_volume: float,
    voiceover_volume: float,
    bgm_start: float,
    bgm_fade_in: float,
    bgm_fade_out: float,
) -> None:
    if not bgm_audio.exists():
        raise SystemExit(f"BGM audio not found: {bgm_audio}")
    if bgm_volume < 0:
        raise SystemExit("--bgm-volume must be greater than or equal to 0.")
    if voiceover_volume < 0:
        raise SystemExit("--voiceover-volume must be greater than or equal to 0.")
    if bgm_start < 0:
        raise SystemExit("--bgm-start must be greater than or equal to 0.")
    if bgm_fade_in < 0:
        raise SystemExit("--bgm-fade-in must be greater than or equal to 0.")
    if bgm_fade_out < 0:
        raise SystemExit("--bgm-fade-out must be greater than or equal to 0.")

    video_duration = ffprobe_duration_media(video_path)
    fade_in = min(bgm_fade_in, max(0.0, video_duration / 2))
    fade_out = min(bgm_fade_out, max(0.0, video_duration / 2))
    fade_out_start = max(0.0, video_duration - fade_out)
    bgm_filters = [
        f"atrim=0:{video_duration:.3f}",
        "asetpts=PTS-STARTPTS",
    ]
    if fade_in > 0:
        bgm_filters.append(f"afade=t=in:st=0:d={fade_in:.3f}")
    if fade_out > 0:
        bgm_filters.append(f"afade=t=out:st={fade_out_start:.3f}:d={fade_out:.3f}")
    bgm_filters.append(f"volume={bgm_volume:.3f}")
    filter_complex = (
        f"[0:a]volume={voiceover_volume:.3f}[voice];"
        f"[1:a]{','.join(bgm_filters)}[bgm];"
        "[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )
    run([
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-stream_loop",
        "-1",
        "-ss",
        f"{bgm_start:.3f}",
        "-i",
        str(bgm_audio),
        "-filter_complex",
        filter_complex,
        "-map",
        "0:v:0",
        "-map",
        "[aout]",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_path),
    ])
```

- [ ] **Step 4: Update `pipeline.py` imports and delete moved functions**

Extend the `video_slicer.rendering` import:

```python
from video_slicer.rendering import (
    add_background_music,
    burn_subtitles,
    clip_video_silent,
    ensure_ffmpeg,
    ffprobe_duration,
    ffprobe_duration_media,
    mux_voiceover_audio,
    render_clips_with_voiceover,
    run,
    run_capture,
    validate_final_duration,
    write_visual_time_mapping,
)
```

Delete these function definitions from `video_slicer/pipeline.py`:

```python
def burn_subtitles(video_path: Path, subtitle_path: Path, output_path: Path) -> None:
def validate_final_duration(media_path: Path, target_duration: float, tolerance: float, label: str) -> float:
def add_background_music(
```

- [ ] **Step 5: Update `scripts/mix_bgm.py` import**

Replace:

```python
from video_slicer.pipeline import add_background_music, load_dotenv
```

With:

```python
from video_slicer.pipeline import load_dotenv
from video_slicer.rendering import add_background_music
```

- [ ] **Step 6: Run tests for Task 4**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_rendering tests.test_pipeline
```

Expected: all tests pass.

- [ ] **Step 7: Commit Task 4**

Run:

```powershell
git add video_slicer/rendering.py video_slicer/pipeline.py scripts/mix_bgm.py tests/test_rendering.py
git commit -m "refactor: extract media rendering utilities"
```

---

### Task 5: Update Documentation and Run End-to-End Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/code-map.zh-CN.md`
- Modify: `docs/superpowers/plans/2026-07-10-rendering-module-refactor.md`

**Interfaces:**
- Consumes:
  - `video_slicer.rendering` public functions from Tasks 1-4.
  - Existing CLI command `.\.venv\Scripts\python.exe -m scripts.run_pipeline`.
- Produces:
  - Updated docs explaining that rendering is no longer owned by `pipeline.py`.
  - Verified 90s and 120s low-cost pipeline runs with `--no-llm --tts-mode none`.

- [ ] **Step 1: Update README project structure**

In `README.md`, under `## 项目结构`, add this bullet after `video_slicer/alignment.py`:

```markdown
- `video_slicer/rendering.py`：FFmpeg 剪辑、配音合成、BGM 混音、字幕烧录和媒体时长探测
```

- [ ] **Step 2: Update code map current pipeline stages**

In `docs/code-map.zh-CN.md`, update the pipeline stage table rows so rendering responsibilities point to `video_slicer.rendering`:

```markdown
| 环境和命令执行 | `video_slicer.rendering::ensure_ffmpeg()`、`run()`、`run_capture()` | 检查 FFmpeg，执行外部命令 |
| 媒体时长 | `video_slicer.rendering::ffprobe_duration_media()`、`ffprobe_duration()` | 读取视频/音频真实时长 |
| 静音剪辑 | `video_slicer.rendering::clip_video_silent()` | 生成无原声预览 |
| 配音成片 | `video_slicer.rendering::render_clips_with_voiceover()` | 用新配音合成视频 |
| BGM 混音 | `video_slicer.rendering::add_background_music()` | 混入背景音乐 |
| 输出记录 | `write_voiceover_outputs()`、`video_slicer.rendering::write_visual_time_mapping()` | 写脚本、字幕、映射 |
| 时长校验 | `video_slicer.rendering::validate_final_duration()` | 校验最终视频时长 |
```

Add a new section after the Alignment module section:

```markdown
### 已拆出的 Rendering 模块

`video_slicer/rendering.py` 负责 FFmpeg/ffprobe 相关媒体处理。

核心函数：

- `run()`
- `run_capture()`
- `ensure_ffmpeg()`
- `ffprobe_duration_media()`
- `ffprobe_duration()`
- `burn_subtitles()`
- `clip_video_silent()`
- `render_clips_with_voiceover()`
- `write_visual_time_mapping()`
- `mux_voiceover_audio()`
- `validate_final_duration()`
- `add_background_music()`

对应测试：

- `tests/test_rendering.py`

后续规则：

- 新增剪辑、混音、字幕烧录、封装容器、编码参数相关能力，优先放到 `video_slicer/rendering.py`。
- `pipeline.py` 只负责决定何时调用渲染函数，不直接拼 FFmpeg 命令。
- 单元测试通过 mock 验证命令构造，真实 FFmpeg 行为放到低成本集成验证中检查。
```

- [ ] **Step 3: Mark this plan execution status**

At the top of `docs/superpowers/plans/2026-07-10-rendering-module-refactor.md`, change no header text. Add this line after the line that begins with `**Tech Stack:** Python 3`:

```markdown
**Execution Status:** Implemented and verified locally.
```

- [ ] **Step 4: Run full unit tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_rendering tests.test_alignment tests.test_pipeline tests.test_project_models tests.test_project_store tests.test_pipeline_records tests.test_quality_report
```

Expected:

```text
OK
```

- [ ] **Step 5: Run compile check**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall video_slicer tests scripts
```

Expected: command exits with code 0.

- [ ] **Step 6: Run whitespace check**

Run:

```powershell
git diff --check
```

Expected: command exits with code 0. LF/CRLF warnings are acceptable on Windows if there are no whitespace error lines.

- [ ] **Step 7: Run video-specific term scan for common code**

Run:

```powershell
rg "刘华强|封彪|征服|孙红雷|买瓜|瓜摊|西瓜|birds|bird" video_slicer llm_providers tts_providers scripts
```

Expected: exit code 1 with no matches.

- [ ] **Step 8: Run 90s low-cost pipeline verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_pipeline --input videos/demo_lhq.mp4 --context context.json --target-duration 90 --output-dir outputs/order_test_90 --no-llm --tts-mode none
```

Expected:

```text
Visual duration: 90.00s
Real voiceover duration: 90.00s
```

Then inspect:

```powershell
$report = Get-Content -LiteralPath 'outputs\order_test_90\quality_report.json' -Encoding UTF8 | ConvertFrom-Json
$report.status
$report.metrics.duration_delta
$report.metrics.source_backtrack_count
$report.metrics.source_major_overlap_count
```

Expected:

```text
pass
0.004
0
0
```

Accept `duration_delta` less than or equal to `0.05` if encoding changes produce a slightly different value.

- [ ] **Step 9: Run 120s low-cost pipeline verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_pipeline --input videos/demo_lhq.mp4 --context context.json --target-duration 120 --output-dir outputs/order_test --no-llm --tts-mode none
```

Expected:

```text
Visual duration: 120.00s
Real voiceover duration: 120.00s
```

Then inspect:

```powershell
$report = Get-Content -LiteralPath 'outputs\order_test\quality_report.json' -Encoding UTF8 | ConvertFrom-Json
$report.status
$report.metrics.duration_delta
$report.metrics.source_backtrack_count
$report.metrics.source_major_overlap_count
```

Expected:

```text
pass
0.002
0
0
```

Accept `duration_delta` less than or equal to `0.05` if encoding changes produce a slightly different value.

- [ ] **Step 10: Confirm Git scope**

Run:

```powershell
git status --short
git ls-files outputs videos .env assets\voice_refs assets\bgm
```

Expected:

```text
assets/bgm/.gitkeep
assets/voice_refs/.gitkeep
videos/.gitkeep
```

`outputs/`, real videos, `.env`, and local voice references must not appear as tracked files.

- [ ] **Step 11: Commit Task 5**

Run:

```powershell
git add README.md docs/code-map.zh-CN.md docs/superpowers/plans/2026-07-10-rendering-module-refactor.md
git commit -m "docs: document rendering module split"
```

---

## Self-Review

**Spec coverage:** This plan covers the next development step discussed with the user: split rendering/FFmpeg logic before building frontend or API layers. It does not touch script generation, API, frontend, OCR, vertical video, or key-original-audio mode because those are separate subsystems and should have their own plans.

**Placeholder scan:** The plan contains exact file paths, exported function signatures, concrete test code, concrete implementation code for new module functions, exact verification commands, and expected outputs. It does not rely on unstated task behavior.

**Type consistency:** All public functions use the same signatures currently used by `pipeline.py`. Later tasks consume functions produced by earlier tasks through `video_slicer.rendering`. `scripts/mix_bgm.py` keeps `load_dotenv` from `pipeline.py` and only moves `add_background_music` to `rendering.py`.

**Execution handoff:** Implement this plan with `superpowers:subagent-driven-development` when available. If working inline, use `superpowers:executing-plans`, follow the task order exactly, and stop if any red test does not fail for the expected reason.
