import tempfile
import unittest
import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)
from fastapi.testclient import TestClient

from video_slicer.api.app import create_app
from video_slicer.project_store import LocalProjectStore


class ApiProjectTest(unittest.TestCase):
    def test_create_list_and_get_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalProjectStore(Path(tmp))
            client = TestClient(create_app(store=store))

            created = client.post(
                "/api/projects",
                json={
                    "source_video_path": "videos/input.mp4",
                    "source_duration_seconds": 300.0,
                    "user_id": "local_user",
                },
            )

            self.assertEqual(created.status_code, 200)
            project = created.json()
            self.assertTrue(project["project_id"].startswith("project_"))
            self.assertEqual(project["source_video_path"], "videos/input.mp4")

            listed = client.get("/api/projects")
            self.assertEqual(listed.status_code, 200)
            self.assertEqual(len(listed.json()), 1)

            fetched = client.get(f"/api/projects/{project['project_id']}")
            self.assertEqual(fetched.status_code, 200)
            self.assertEqual(fetched.json()["project_id"], project["project_id"])

    def test_update_context_normalizes_narration_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalProjectStore(Path(tmp))
            project = store.create_project("videos/input.mp4", source_duration_seconds=300.0)
            client = TestClient(create_app(store=store))

            response = client.put(
                f"/api/projects/{project.project_id}/context",
                json={
                    "context_packet": {
                        "title": "测试项目",
                        "correct_synopsis": "主角走进房间。",
                    }
                },
            )

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["context_packet"]["title"], "测试项目")
            self.assertIn("narration_rules", body["context_packet"])
            self.assertEqual(
                store.get_project(project.project_id).context_packet["correct_synopsis"],
                "主角走进房间。",
            )

    def test_missing_project_returns_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(store=LocalProjectStore(Path(tmp))))

            response = client.get("/api/projects/project_missing")

            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()["detail"], "Project not found")


if __name__ == "__main__":
    unittest.main()
