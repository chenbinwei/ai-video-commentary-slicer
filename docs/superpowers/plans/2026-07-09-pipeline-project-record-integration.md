# Pipeline 项目记录接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让现有命令行 pipeline 可以选择性写入项目、版本、任务记录，为后续前端进度展示和多版本管理打地基。

**Architecture:** 不重写 `video_slicer.pipeline` 的剪辑逻辑，只新增一个轻量适配模块，把 CLI 参数映射成 `VersionSettings`，并在 pipeline 开始、失败、成功时更新 `LocalProjectStore`。默认旧命令行为不变，只有传入 `--record-project` 时才写入 `projects.local/`。

**Tech Stack:** Python 3.11 标准库、`argparse.Namespace`、`unittest`、现有 `video_slicer.project_models` 和 `video_slicer.project_store`。

---

## 范围

本计划只做 pipeline 和项目记录的最小连接。

包括：

- 新增 `video_slicer/pipeline_records.py`。
- 新增 `tests/test_pipeline_records.py`。
- 给 `pipeline.py` 增加可选 CLI 参数。
- 在 `run_cli()` 里创建 project/version/job。
- 成功时记录导出视频路径和最终时长。
- 失败时记录 job 状态和错误信息。
- 保持旧命令不变：不传 `--record-project` 就不写项目记录。

不包括：

- FastAPI。
- 前端。
- 真正多版本 UI。
- 关键原声模式实现。
- 字幕语言和画幅的真实导出逻辑。
- 订阅额度扣减。

## 文件结构

新增：

- `video_slicer/pipeline_records.py`
  - 把 pipeline CLI 参数映射为 `VersionSettings`。
  - 创建 project/version/job。
  - 更新 job 状态。
  - 记录导出结果。

- `tests/test_pipeline_records.py`
  - 测试参数映射。
  - 测试不启用记录时不会写项目数据。
  - 测试启用记录时会创建 project/version/job。
  - 测试成功导出会写入 version/job。
  - 测试失败会写入 job failed。

修改：

- `video_slicer/pipeline.py`
  - 增加 `--record-project`、`--project-root`、`--project-id`、`--version-id`。
  - 在 `run_cli()` 开始时调用记录适配器。
  - 在最终导出后记录成功结果。
  - 用 `try/except` 包裹主流程，失败时记录 job failed 后继续抛出原错误。

- `README.md`
  - 增加如何开启项目记录的命令。

---

## Task 1: 新增 pipeline_records 适配模块

**Files:**

- Create: `video_slicer/pipeline_records.py`
- Create: `tests/test_pipeline_records.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_pipeline_records.py`：

```python
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from video_slicer.pipeline_records import (
    PipelineRecordSession,
    begin_pipeline_record_session,
    settings_from_pipeline_args,
)
from video_slicer.project_models import AudioMode, JobStatus
from video_slicer.project_store import LocalProjectStore


def make_args(**overrides):
    values = {
        "record_project": False,
        "project_root": "",
        "project_id": "",
        "version_id": "",
        "input": "videos/input.mp4",
        "target_duration": 120.0,
        "tts_mode": "fish",
        "fish_reference_id": "fish_voice_demo",
        "fish_tts_speed": 0.92,
        "ocool_tts_voice": "echo",
        "ocool_tts_speed": 1.0,
        "bgm_audio": "assets/bgm/demo.mp3",
        "bgm_volume": 0.18,
        "voiceover_volume": 1.1,
    }
    values.update(overrides)
    return Namespace(**values)


class PipelineRecordsTest(unittest.TestCase):
    def test_settings_from_fish_args(self):
        settings = settings_from_pipeline_args(make_args())

        self.assertEqual(settings.target_duration_seconds, 120.0)
        self.assertEqual(settings.audio_mode, AudioMode.PURE_COMMENTARY)
        self.assertEqual(settings.voice_clone_id, "fish_voice_demo")
        self.assertEqual(settings.voiceover_speed, 0.92)
        self.assertEqual(settings.voiceover_volume, 1.1)
        self.assertEqual(settings.bgm_path, "assets/bgm/demo.mp3")
        self.assertEqual(settings.bgm_volume, 0.18)

    def test_settings_from_ocool_args_uses_voice_name(self):
        settings = settings_from_pipeline_args(make_args(tts_mode="ocool", fish_reference_id="", ocool_tts_voice="nova"))

        self.assertEqual(settings.voice_clone_id, "nova")
        self.assertEqual(settings.voiceover_speed, 1.0)

    def test_begin_session_disabled(self):
        session = begin_pipeline_record_session(make_args(record_project=False), video_duration=300.0)

        self.assertFalse(session.enabled)
        self.assertIsNone(session.store)
        self.assertEqual(session.project_id, "")

    def test_begin_session_enabled_creates_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = make_args(record_project=True, project_root=tmp, project_id="project_demo")

            session = begin_pipeline_record_session(args, video_duration=300.0)

            self.assertTrue(session.enabled)
            self.assertEqual(session.project_id, "project_demo")
            self.assertTrue(session.version_id.startswith("version_"))
            self.assertTrue(session.job_id.startswith("job_"))

            store = LocalProjectStore(Path(tmp))
            project = store.get_project(session.project_id)
            version = store.get_version(session.project_id, session.version_id)
            job = store.get_job(session.project_id, session.job_id)

            self.assertEqual(project.source_video_path, "videos/input.mp4")
            self.assertEqual(project.source_duration_seconds, 300.0)
            self.assertEqual(version.settings.target_duration_seconds, 120.0)
            self.assertEqual(job.status, JobStatus.RUNNING)

    def test_record_success_and_failure_are_noops_when_disabled(self):
        session = PipelineRecordSession.disabled()

        session.mark_success(final_video_path="outputs/final.mp4", duration_seconds=119.8)
        session.mark_failed(RuntimeError("boom"))

        self.assertFalse(session.enabled)

    def test_record_success_updates_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = begin_pipeline_record_session(
                make_args(record_project=True, project_root=tmp, project_id="project_demo"),
                video_duration=300.0,
            )

            session.mark_success(final_video_path="outputs/final_with_bgm.mp4", duration_seconds=119.8)

            store = LocalProjectStore(Path(tmp))
            version = store.get_version(session.project_id, session.version_id)
            job = store.get_job(session.project_id, session.job_id)

            self.assertEqual(version.export_paths["final_video"], "outputs/final_with_bgm.mp4")
            self.assertEqual(job.export_paths["final_video"], "outputs/final_with_bgm.mp4")
            self.assertEqual(job.duration_seconds, 119.8)
            self.assertEqual(job.status, JobStatus.DONE)

    def test_record_failure_updates_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = begin_pipeline_record_session(
                make_args(record_project=True, project_root=tmp, project_id="project_demo"),
                video_duration=300.0,
            )

            session.mark_failed(ValueError("bad duration"))

            store = LocalProjectStore(Path(tmp))
            job = store.get_job(session.project_id, session.job_id)

            self.assertEqual(job.status, JobStatus.FAILED)
            self.assertIn("bad duration", job.error_message)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_pipeline_records -v
```

Expected:

```text
ModuleNotFoundError: No module named 'video_slicer.pipeline_records'
```

- [ ] **Step 3: 写适配模块**

创建 `video_slicer/pipeline_records.py`：

```python
"""Optional project/version/job recording for the CLI pipeline."""

from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path

from video_slicer.project_models import (
    AspectRatio,
    AudioMode,
    JobStage,
    JobStatus,
    SubtitleLanguage,
    VersionSettings,
)
from video_slicer.project_store import LocalProjectStore


def settings_from_pipeline_args(args: Namespace) -> VersionSettings:
    if getattr(args, "tts_mode", "") == "fish":
        voice_clone_id = str(getattr(args, "fish_reference_id", "") or "")
        voiceover_speed = float(getattr(args, "fish_tts_speed", 1.0))
    elif getattr(args, "tts_mode", "") == "ocool":
        voice_clone_id = str(getattr(args, "ocool_tts_voice", "") or "")
        voiceover_speed = float(getattr(args, "ocool_tts_speed", 1.0))
    else:
        voice_clone_id = ""
        voiceover_speed = 1.0

    return VersionSettings(
        target_duration_seconds=float(getattr(args, "target_duration", 120.0)),
        audio_mode=AudioMode.PURE_COMMENTARY,
        voice_clone_id=voice_clone_id,
        bgm_path=str(getattr(args, "bgm_audio", "") or ""),
        voiceover_speed=voiceover_speed,
        voiceover_volume=float(getattr(args, "voiceover_volume", 1.0)),
        bgm_volume=float(getattr(args, "bgm_volume", 0.16)),
        subtitle_language=SubtitleLanguage.ZH,
        aspect_ratio=AspectRatio.ORIGINAL,
    )


@dataclass
class PipelineRecordSession:
    enabled: bool
    store: LocalProjectStore | None = None
    project_id: str = ""
    version_id: str = ""
    job_id: str = ""

    @classmethod
    def disabled(cls) -> "PipelineRecordSession":
        return cls(enabled=False)

    def mark_success(self, *, final_video_path: str, duration_seconds: float | None) -> None:
        if not self.enabled or self.store is None:
            return
        self.store.record_export(
            project_id=self.project_id,
            version_id=self.version_id,
            job_id=self.job_id,
            export_kind="final_video",
            export_path=final_video_path,
            duration_seconds=duration_seconds,
        )
        self.store.update_job_status(
            project_id=self.project_id,
            job_id=self.job_id,
            status=JobStatus.DONE,
            stage=JobStage.EXPORT,
        )

    def mark_failed(self, exc: BaseException) -> None:
        if not self.enabled or self.store is None:
            return
        self.store.update_job_status(
            project_id=self.project_id,
            job_id=self.job_id,
            status=JobStatus.FAILED,
            stage=JobStage.EXPORT,
            error_message=str(exc),
        )


def begin_pipeline_record_session(args: Namespace, *, video_duration: float) -> PipelineRecordSession:
    if not getattr(args, "record_project", False):
        return PipelineRecordSession.disabled()

    store = LocalProjectStore(Path(getattr(args, "project_root", "") or "projects.local"))
    project_id = str(getattr(args, "project_id", "") or "")
    version_id = str(getattr(args, "version_id", "") or "")

    if project_id:
        try:
            project = store.get_project(project_id)
        except FileNotFoundError:
            project = store.create_project(
                source_video_path=str(getattr(args, "input", "")),
                source_duration_seconds=video_duration,
                project_id=project_id,
            )
    else:
        project = store.create_project(
            source_video_path=str(getattr(args, "input", "")),
            source_duration_seconds=video_duration,
        )

    settings = settings_from_pipeline_args(args)
    if version_id:
        try:
            version = store.get_version(project.project_id, version_id)
        except FileNotFoundError:
            version = store.create_version(
                project_id=project.project_id,
                version_id=version_id,
                settings=settings,
            )
    else:
        version = store.create_version(project_id=project.project_id, settings=settings)

    job = store.create_job(
        project_id=project.project_id,
        version_id=version.version_id,
        initial_stage=JobStage.EXTRACT_AUDIO,
    )
    store.update_job_status(
        project_id=project.project_id,
        job_id=job.job_id,
        status=JobStatus.RUNNING,
        stage=JobStage.EXTRACT_AUDIO,
    )

    return PipelineRecordSession(
        enabled=True,
        store=store,
        project_id=project.project_id,
        version_id=version.version_id,
        job_id=job.job_id,
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_pipeline_records -v
```

Expected:

```text
Ran 7 tests

OK
```

- [ ] **Step 5: 提交**

Run:

```powershell
git add video_slicer/pipeline_records.py tests/test_pipeline_records.py
git commit -m "feat: add optional pipeline record session"
```

Expected:

```text
[feat/fish-audio-tts <hash>] feat: add optional pipeline record session
```

---

## Task 2: 在 pipeline CLI 中接入记录模式

**Files:**

- Modify: `video_slicer/pipeline.py`
- Test: `tests/test_pipeline_records.py`

- [ ] **Step 1: 增加 parser 测试**

在 `tests/test_pipeline_records.py` 追加：

```python
from video_slicer.pipeline import build_parser


class PipelineParserRecordArgsTest(unittest.TestCase):
    def test_parser_accepts_project_record_args(self):
        parser = build_parser()
        args = parser.parse_args([
            "--record-project",
            "--project-root",
            "projects.local",
            "--project-id",
            "project_demo",
            "--version-id",
            "version_demo",
        ])

        self.assertTrue(args.record_project)
        self.assertEqual(args.project_root, "projects.local")
        self.assertEqual(args.project_id, "project_demo")
        self.assertEqual(args.version_id, "version_demo")
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_pipeline_records.PipelineParserRecordArgsTest -v
```

Expected:

```text
unrecognized arguments: --record-project --project-root projects.local --project-id project_demo --version-id version_demo
```

- [ ] **Step 3: 修改 `build_parser()`**

在 `video_slicer/pipeline.py` 的 `build_parser()` 中，紧跟 `--output-dir` 后加入：

```python
    parser.add_argument("--record-project", action="store_true", help="Write local project/version/job records under --project-root.")
    parser.add_argument("--project-root", default=os.environ.get("PROJECT_ROOT", "projects.local"), help="Local project data root used with --record-project.")
    parser.add_argument("--project-id", default="", help="Existing or desired project id used with --record-project.")
    parser.add_argument("--version-id", default="", help="Existing or desired version id used with --record-project.")
```

- [ ] **Step 4: 运行 parser 测试确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_pipeline_records.PipelineParserRecordArgsTest -v
```

Expected:

```text
Ran 1 test

OK
```

- [ ] **Step 5: 提交**

Run:

```powershell
git add video_slicer/pipeline.py tests/test_pipeline_records.py
git commit -m "feat: add project record cli flags"
```

Expected:

```text
[feat/fish-audio-tts <hash>] feat: add project record cli flags
```

---

## Task 3: 在 run_cli 中写入任务状态和导出结果

**Files:**

- Modify: `video_slicer/pipeline.py`
- Modify: `README.md`

- [ ] **Step 1: 修改 run_cli 导入和记录会话**

在 `video_slicer/pipeline.py` 顶部 imports 后加入：

```python
from video_slicer.pipeline_records import begin_pipeline_record_session
```

在 `run_cli()` 中读取 `video_duration` 后加入：

```python
    record_session = begin_pipeline_record_session(args, video_duration=video_duration)
```

把 `run_cli()` 从 `extract_audio(...)` 开始到最终打印输出的主体包进：

```python
    try:
        ...
    except BaseException as exc:
        record_session.mark_failed(exc)
        raise
```

在确定最终输出后加入：

```python
    if final_with_bgm_path:
        record_output_path = final_with_bgm_path
    elif final_path:
        record_output_path = final_path
    else:
        record_output_path = output_video

    record_duration = ffprobe_duration_media(record_output_path) if record_output_path.exists() else None
    record_session.mark_success(
        final_video_path=str(record_output_path),
        duration_seconds=record_duration,
    )
```

注意：不要改变现有输出文件名和旧命令行为。

- [ ] **Step 2: 运行无记录模式的轻量解析测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_project_models tests.test_project_store tests.test_pipeline_records -v
```

Expected:

```text
OK
```

- [ ] **Step 3: 更新 README**

在 README 的“本地项目数据结构”章节增加：

```markdown
如果想让命令行 pipeline 写入项目、版本和任务记录，可以在原命令后增加：

```powershell
--record-project --project-root projects.local
```

也可以指定项目和版本：

```powershell
--record-project --project-id project_demo --version-id version_120s
```

不加 `--record-project` 时，旧流程完全不写项目记录。
```

- [ ] **Step 4: 运行编译检查**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall video_slicer tests
```

Expected:

```text
Listing 'video_slicer'...
Listing 'tests'...
```

- [ ] **Step 5: 提交**

Run:

```powershell
git add video_slicer/pipeline.py README.md
git commit -m "feat: record pipeline jobs locally"
```

Expected:

```text
[feat/fish-audio-tts <hash>] feat: record pipeline jobs locally
```

---

## 验收

完成本计划后：

- 旧命令不受影响。
- 传 `--record-project` 时会写入 `projects.local/projects/<project_id>/project.json`。
- 每次运行会创建一个 `job.json`。
- 成功导出会记录 `final_video` 路径和成片时长。
- 失败会记录 job 为 `failed`，并保留错误信息。
- 版本记录会保存目标时长、声音、BGM、音量等生成参数。

## 自检

Spec 覆盖：

- 覆盖项目、版本、任务记录接入 pipeline。
- 覆盖本地单人模式。
- 覆盖未来前端生成进度所需的 job 状态。
- 保持旧 CLI 行为不变。

未覆盖内容：

- 前端进度轮询。
- FastAPI API。
- 关键原声真正实现。
- 多语言字幕真正导出。
- 竖屏 9:16 真正导出。
- 商业额度扣减。
