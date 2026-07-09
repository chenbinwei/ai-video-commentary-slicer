import tempfile
import unittest
import warnings
from pathlib import Path

from fastapi import BackgroundTasks

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)
from fastapi.testclient import TestClient

from video_slicer.api.app import create_app
from video_slicer.api.job_runner import PipelineJobRunner
from video_slicer.api.schemas import CreateRenderJobRequest
from video_slicer.project_models import JobStatus, VersionSettings
from video_slicer.project_store import LocalProjectStore


class RecordingRunner:
    def __init__(self):
        self.calls = []

    def run_job(self, *, project_id, version_id, job_id, request):
        self.calls.append((project_id, version_id, job_id, request.tts_mode))


class ApiJobTest(unittest.TestCase):
    def test_create_render_job_schedules_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalProjectStore(Path(tmp))
            project = store.create_project("videos/input.mp4", source_duration_seconds=300.0)
            version = store.create_version(project.project_id, VersionSettings(target_duration_seconds=90.0))
            runner = RecordingRunner()
            client = TestClient(create_app(store=store, job_runner=runner))

            response = client.post(
                f"/api/projects/{project.project_id}/versions/{version.version_id}/render",
                json={"tts_mode": "none", "require_llm": False},
            )

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertTrue(body["job_id"].startswith("job_"))
            self.assertEqual(body["status"], "pending")
            self.assertEqual(runner.calls, [(project.project_id, version.version_id, body["job_id"], "none")])

    def test_list_and_get_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalProjectStore(Path(tmp))
            project = store.create_project("videos/input.mp4", source_duration_seconds=300.0)
            version = store.create_version(project.project_id, VersionSettings(target_duration_seconds=90.0))
            job = store.create_job(project.project_id, version.version_id)
            client = TestClient(create_app(store=store, job_runner=RecordingRunner()))

            listed = client.get(f"/api/projects/{project.project_id}/jobs")
            fetched = client.get(f"/api/projects/{project.project_id}/jobs/{job.job_id}")

            self.assertEqual(listed.status_code, 200)
            self.assertEqual(listed.json()[0]["job_id"], job.job_id)
            self.assertEqual(fetched.status_code, 200)
            self.assertEqual(fetched.json()["job_id"], job.job_id)

    def test_build_pipeline_args_maps_version_settings_and_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalProjectStore(Path(tmp))
            project = store.create_project("videos/input.mp4", source_duration_seconds=300.0, project_id="project_demo")
            project.context_packet = {"title": "测试", "correct_synopsis": "主角进入房间。"}
            store.save_project(project)
            version = store.create_version(
                project.project_id,
                VersionSettings(
                    target_duration_seconds=90.0,
                    voice_clone_id="fish_voice_demo",
                    bgm_path="assets/bgm/demo.mp3",
                    bgm_volume=0.18,
                    voiceover_volume=1.2,
                    voiceover_speed=0.92,
                ),
                version_id="version_demo",
            )
            job = store.create_job(project.project_id, version.version_id, job_id="job_demo")
            runner = PipelineJobRunner(store=store, pipeline_fn=lambda args: None)

            args = runner.build_pipeline_args(
                project_id=project.project_id,
                version_id=version.version_id,
                job_id=job.job_id,
                request=CreateRenderJobRequest(tts_mode="fish", require_llm=True, force_tts=True),
            )

            self.assertEqual(args.input, "videos/input.mp4")
            self.assertEqual(args.project_id, "project_demo")
            self.assertEqual(args.version_id, "version_demo")
            self.assertEqual(args.job_id, "job_demo")
            self.assertEqual(args.target_duration, 90.0)
            self.assertEqual(args.tts_mode, "fish")
            self.assertEqual(args.fish_reference_id, "fish_voice_demo")
            self.assertEqual(args.bgm_audio, "assets/bgm/demo.mp3")
            self.assertEqual(args.bgm_volume, 0.18)
            self.assertEqual(args.voiceover_volume, 1.2)
            self.assertTrue(args.require_llm)
            self.assertTrue(args.force_tts)
            self.assertTrue(Path(args.context).exists())

    def test_runner_marks_failed_when_pipeline_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalProjectStore(Path(tmp))
            project = store.create_project("videos/input.mp4", source_duration_seconds=300.0)
            version = store.create_version(project.project_id, VersionSettings(target_duration_seconds=90.0))
            job = store.create_job(project.project_id, version.version_id)

            def boom(args):
                raise RuntimeError("render failed")

            runner = PipelineJobRunner(store=store, pipeline_fn=boom)
            runner.run_job(
                project_id=project.project_id,
                version_id=version.version_id,
                job_id=job.job_id,
                request=CreateRenderJobRequest(tts_mode="none", require_llm=False),
            )

            saved = store.get_job(project.project_id, job.job_id)
            self.assertEqual(saved.status, JobStatus.FAILED)
            self.assertIn("render failed", saved.error_message)


if __name__ == "__main__":
    unittest.main()
