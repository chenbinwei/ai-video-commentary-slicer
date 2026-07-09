"""Background pipeline job runner for the local API."""

from __future__ import annotations

import threading
from typing import Callable

from video_slicer.api.project_service import write_project_context_file
from video_slicer.api.schemas import CreateRenderJobRequest
from video_slicer.pipeline import build_parser, run_cli
from video_slicer.project_models import JobStage, JobStatus
from video_slicer.project_store import LocalProjectStore


class PipelineJobRunner:
    def __init__(
        self,
        *,
        store: LocalProjectStore,
        pipeline_fn: Callable | None = None,
    ) -> None:
        self.store = store
        self.pipeline_fn = pipeline_fn or run_cli
        self._lock = threading.Lock()

    def build_pipeline_args(
        self,
        *,
        project_id: str,
        version_id: str,
        job_id: str,
        request: CreateRenderJobRequest,
    ):
        project = self.store.get_project(project_id)
        version = self.store.get_version(project_id, version_id)
        output_dir = self.store.project_dir(project_id) / "outputs" / job_id
        context_path = write_project_context_file(self.store, project_id=project_id, output_dir=output_dir)
        settings = version.settings

        argv = [
            "--input", project.source_video_path,
            "--output-dir", str(output_dir),
            "--context", str(context_path),
            "--target-duration", str(settings.target_duration_seconds),
            "--tts-mode", request.tts_mode,
            "--duration-tolerance", "3.0",
            "--record-project",
            "--project-root", str(self.store.root),
            "--project-id", project_id,
            "--version-id", version_id,
            "--job-id", job_id,
            "--bgm-volume", str(settings.bgm_volume),
            "--voiceover-volume", str(settings.voiceover_volume),
        ]

        if request.require_llm:
            argv.append("--require-llm")
        else:
            argv.append("--no-llm")
        if request.force_script:
            argv.append("--force-script")
        if request.force_review:
            argv.append("--force-review")
        if request.force_humanize:
            argv.append("--force-humanize")
        if request.force_tts:
            argv.append("--force-tts")
        if request.no_fit_duration:
            argv.append("--no-fit-duration")
        if settings.voice_clone_id and request.tts_mode == "fish":
            argv.extend(["--fish-reference-id", settings.voice_clone_id])
        if settings.voiceover_speed and request.tts_mode == "fish":
            argv.extend(["--fish-tts-speed", str(settings.voiceover_speed)])
        if settings.voice_clone_id and request.tts_mode == "ocool":
            argv.extend(["--ocool-tts-voice", settings.voice_clone_id])
        if settings.voiceover_speed and request.tts_mode == "ocool":
            argv.extend(["--ocool-tts-speed", str(settings.voiceover_speed)])
        if settings.bgm_path:
            argv.extend(["--bgm-audio", settings.bgm_path])

        return build_parser().parse_args(argv)

    def run_job(
        self,
        *,
        project_id: str,
        version_id: str,
        job_id: str,
        request: CreateRenderJobRequest,
    ) -> None:
        if not self._lock.acquire(blocking=False):
            self.store.update_job_status(
                project_id=project_id,
                job_id=job_id,
                status=JobStatus.FAILED,
                stage=JobStage.EXPORT,
                error_message="Another render job is already running",
            )
            return
        try:
            self.store.update_job_status(
                project_id=project_id,
                job_id=job_id,
                status=JobStatus.RUNNING,
                stage=JobStage.EXTRACT_AUDIO,
            )
            args = self.build_pipeline_args(
                project_id=project_id,
                version_id=version_id,
                job_id=job_id,
                request=request,
            )
            self.pipeline_fn(args)
        except BaseException as exc:
            self.store.update_job_status(
                project_id=project_id,
                job_id=job_id,
                status=JobStatus.FAILED,
                stage=JobStage.EXPORT,
                error_message=str(exc),
            )
        finally:
            self._lock.release()
