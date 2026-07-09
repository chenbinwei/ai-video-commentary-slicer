# 本地前端 MVP 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 在 `http://127.0.0.1:8000/` 做出一个本地浏览器工作台，让用户不用手动调用 API，就能创建视频项目、编辑上下文包、创建渲染版本、启动渲染任务并查看任务状态。

**架构：** 前端使用普通 HTML/CSS/JavaScript，作为静态文件由现有 FastAPI 后端托管。前端只负责表单、状态、校验、API 调用和任务轮询；项目存储、上下文规范化、版本校验、渲染调度和 pipeline 执行继续留在 `video_slicer/api/` 以及后端底层模块。

**技术栈：** Python 3、FastAPI、Starlette `StaticFiles`、标准 HTML/CSS/JavaScript、`unittest`、FastAPI `TestClient`。

**执行状态：** 已在本地实现并验证。

---

## 范围

这份计划只做第一版本地网页工作台。它不做登录、付费、云存储、视频上传、浏览器内视频预览、文案预览编辑，也不做公开 SaaS API。第一版继续使用本地视频路径，因为当前后端接口接收的是 `source_video_path`。

页面定位是创作者工具，不是宣传页。打开后的第一屏就是可用工作台：项目创建、上下文编辑、版本设置、渲染按钮和任务状态。

## 文件结构

新增：

- `frontend/index.html`
  - 本地工作台页面结构。
  - 包含项目、上下文、版本、渲染和任务状态区域。
- `frontend/styles.css`
  - 安静、密集、工具型的产品界面样式。
  - 使用 pane/list/form 结构，不做营销 hero，不做嵌套卡片。
- `frontend/app.js`
  - 调用现有本地 API。
  - 维护当前项目、当前版本、当前任务状态。
  - 创建版本前校验目标时长必须小于原视频时长。
  - 启动渲染后轮询任务状态。
- `tests/test_frontend_static.py`
  - 验证 FastAPI 能访问 `/`、`/assets/styles.css`、`/assets/app.js`。
  - 验证前端包含后端契约需要的关键控件和请求字段。

修改：

- `video_slicer/api/app.py`
  - 增加静态前端挂载和根路由。
  - 保持所有 `/api/...` 路由不变。
- `README.md`
  - 增加本地前端启动地址。
- `docs/README.zh-CN.md`
  - 增加 `frontend/` 的目录职责。
- `docs/code-map.zh-CN.md`
  - 增加前端到 API 的边界说明。
- `docs/development-rules.zh-CN.md`
  - 增加前端文件的放置规则和验证规则。

不要修改：

- `.env`
- `context.example.json`
- `videos/`
- `outputs/`
- `projects.local/`
- `llm_providers/`
- `tts_providers/`
- `video_slicer/pipeline.py`
- `video_slicer/script_generation.py`
- `video_slicer/alignment.py`
- `video_slicer/rendering.py`

---

### 任务 1：让 FastAPI 托管静态前端

**文件：**
- 新增：`frontend/index.html`
- 新增：`frontend/styles.css`
- 新增：`frontend/app.js`
- 修改：`video_slicer/api/app.py`
- 新增：`tests/test_frontend_static.py`

**接口：**
- 使用：
  - `create_app(project_root=None, store=None, job_runner=None)`
- 产出：
  - `GET /`
  - `GET /assets/styles.css`
  - `GET /assets/app.js`

- [ ] **步骤 1：先写失败的静态前端测试**

创建 `tests/test_frontend_static.py`：

```python
import unittest
import warnings

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)
from fastapi.testclient import TestClient

from video_slicer.api.app import create_app


class FrontendStaticTest(unittest.TestCase):
    def test_root_serves_workspace_html(self):
        client = TestClient(create_app())

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("视频切片工作台", response.text)
        self.assertIn('/assets/styles.css', response.text)
        self.assertIn('/assets/app.js', response.text)

    def test_static_assets_are_served(self):
        client = TestClient(create_app())

        css = client.get("/assets/styles.css")
        js = client.get("/assets/app.js")

        self.assertEqual(css.status_code, 200)
        self.assertIn(".workspace", css.text)
        self.assertEqual(js.status_code, 200)
        self.assertIn("requestJson", js.text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **步骤 2：运行测试，确认它会失败**

运行：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_frontend_static
```

预期：

```text
FAILED
```

失败原因应该是 `GET /` 返回 404。

- [ ] **步骤 3：创建前端 HTML 页面骨架**

创建 `frontend/index.html`：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>视频切片工作台</title>
    <link rel="stylesheet" href="/assets/styles.css">
  </head>
  <body>
    <header class="topbar">
      <div>
        <h1>视频切片工作台</h1>
        <p id="apiStatus" class="muted">连接中</p>
      </div>
      <div class="status-pill">Local</div>
    </header>

    <main class="workspace">
      <section class="pane pane-projects" aria-labelledby="projectHeading">
        <div class="pane-header">
          <h2 id="projectHeading">项目</h2>
        </div>

        <form id="projectForm" class="stack">
          <label>
            <span>视频路径</span>
            <input id="sourceVideoPath" name="source_video_path" type="text" autocomplete="off" required>
          </label>
          <label>
            <span>原视频时长（秒）</span>
            <input id="sourceDurationSeconds" name="source_duration_seconds" type="number" min="1" step="0.1">
          </label>
          <button id="createProjectButton" type="submit">创建项目</button>
        </form>

        <div id="projectList" class="item-list" aria-live="polite"></div>
      </section>

      <section class="pane pane-context" aria-labelledby="contextHeading">
        <div class="pane-header">
          <h2 id="contextHeading">上下文</h2>
          <button id="saveContextButton" type="button" disabled>保存上下文</button>
        </div>

        <form id="contextForm" class="context-grid">
          <label>
            <span>标题</span>
            <input id="contextTitle" type="text" autocomplete="off">
          </label>
          <label>
            <span>素材类型</span>
            <input id="sourceType" type="text" autocomplete="off">
          </label>
          <label class="span-2">
            <span>人物</span>
            <textarea id="contextCharacters" rows="4"></textarea>
          </label>
          <label class="span-2">
            <span>正确梗概</span>
            <textarea id="correctSynopsis" rows="5"></textarea>
          </label>
          <label>
            <span>切片重点</span>
            <textarea id="storyFocus" rows="4"></textarea>
          </label>
          <label>
            <span>允许背景</span>
            <textarea id="externalKnowledge" rows="4"></textarea>
          </label>
          <label>
            <span>禁用词</span>
            <textarea id="forbiddenTerms" rows="4"></textarea>
          </label>
          <label>
            <span>禁止剧情</span>
            <textarea id="forbiddenStoryFacts" rows="4"></textarea>
          </label>
          <label>
            <span>其他禁止内容</span>
            <textarea id="mustNotInclude" rows="4"></textarea>
          </label>
          <label>
            <span>TTS 易错词</span>
            <textarea id="ttsTerms" rows="4"></textarea>
          </label>
        </form>
      </section>

      <section class="pane pane-render" aria-labelledby="renderHeading">
        <div class="pane-header">
          <h2 id="renderHeading">版本与渲染</h2>
        </div>

        <form id="versionForm" class="stack">
          <label>
            <span>目标时长（秒）</span>
            <input id="targetDurationSeconds" type="number" min="1" step="0.1" required>
          </label>
          <label>
            <span>声音模式</span>
            <select id="audioMode">
              <option value="pure_commentary">纯解说</option>
              <option value="key_original_audio">关键原声</option>
            </select>
          </label>
          <label>
            <span>声音克隆 ID</span>
            <input id="voiceCloneId" type="text" autocomplete="off">
          </label>
          <label>
            <span>BGM 路径</span>
            <input id="bgmPath" type="text" autocomplete="off">
          </label>
          <label>
            <span>配音速度</span>
            <input id="voiceoverSpeed" type="number" min="0.5" max="1.5" step="0.01" value="0.92">
          </label>
          <label>
            <span>配音音量</span>
            <input id="voiceoverVolume" type="number" min="0" step="0.01" value="1.0">
          </label>
          <label>
            <span>BGM 音量</span>
            <input id="bgmVolume" type="number" min="0" step="0.01" value="0.22">
          </label>
          <label>
            <span>字幕语言</span>
            <select id="subtitleLanguage">
              <option value="zh">中文</option>
              <option value="en">英文</option>
              <option value="zh_en">中英双语</option>
            </select>
          </label>
          <label>
            <span>画幅</span>
            <select id="aspectRatio">
              <option value="original">原画幅</option>
              <option value="vertical_9_16_blur">竖屏 9:16</option>
            </select>
          </label>
          <label>
            <span>版本目标</span>
            <input id="variantGoal" type="text" value="manual" autocomplete="off">
          </label>
          <button id="createVersionButton" type="submit" disabled>创建版本</button>
        </form>

        <div id="versionList" class="item-list" aria-live="polite"></div>

        <form id="renderForm" class="stack render-form">
          <label>
            <span>TTS</span>
            <select id="ttsMode">
              <option value="fish">Fish Audio</option>
              <option value="ocool">Ocool</option>
              <option value="none">不生成配音</option>
            </select>
          </label>
          <label class="check-row">
            <input id="requireLlm" type="checkbox" checked>
            <span>使用大模型</span>
          </label>
          <label class="check-row">
            <input id="forceScript" type="checkbox">
            <span>重写文案</span>
          </label>
          <label class="check-row">
            <input id="forceReview" type="checkbox">
            <span>重新审查</span>
          </label>
          <label class="check-row">
            <input id="forceHumanize" type="checkbox">
            <span>重新口语化</span>
          </label>
          <label class="check-row">
            <input id="forceTts" type="checkbox">
            <span>重新配音</span>
          </label>
          <button id="startRenderButton" type="submit" disabled>开始渲染</button>
        </form>

        <div id="jobList" class="item-list" aria-live="polite"></div>
      </section>
    </main>

    <div id="statusMessage" class="toast" role="status" aria-live="polite"></div>
    <script src="/assets/app.js"></script>
  </body>
</html>
```

- [ ] **步骤 4：创建前端样式文件**

创建 `frontend/styles.css`：

```css
:root {
  color-scheme: light;
  --bg: #f7f8fa;
  --surface: #ffffff;
  --line: #d9dee7;
  --text: #172033;
  --muted: #677084;
  --accent: #0f766e;
  --accent-strong: #0b5f58;
  --danger: #b42318;
  --ok: #16794c;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 360px;
  background: var(--bg);
  color: var(--text);
  font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
  letter-spacing: 0;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 72px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--line);
  background: var(--surface);
}

h1,
h2 {
  margin: 0;
  font-weight: 650;
  line-height: 1.2;
}

h1 {
  font-size: 22px;
}

h2 {
  font-size: 16px;
}

.muted {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 13px;
}

.status-pill {
  min-width: 64px;
  padding: 6px 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--muted);
  text-align: center;
  font-size: 13px;
}

.workspace {
  display: grid;
  grid-template-columns: minmax(250px, 0.75fr) minmax(420px, 1.4fr) minmax(300px, 0.95fr);
  min-height: calc(100vh - 72px);
}

.pane {
  min-width: 0;
  padding: 18px;
  border-right: 1px solid var(--line);
  background: var(--surface);
}

.pane:last-child {
  border-right: 0;
}

.pane-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.stack,
.context-grid {
  display: grid;
  gap: 12px;
}

.context-grid {
  grid-template-columns: 1fr 1fr;
}

.span-2 {
  grid-column: 1 / -1;
}

label {
  display: grid;
  gap: 6px;
  min-width: 0;
  color: var(--muted);
  font-size: 13px;
}

input,
select,
textarea,
button {
  width: 100%;
  min-height: 36px;
  border: 1px solid var(--line);
  border-radius: 6px;
  font: inherit;
  letter-spacing: 0;
}

input,
select,
textarea {
  padding: 8px 10px;
  background: #ffffff;
  color: var(--text);
}

textarea {
  resize: vertical;
  line-height: 1.5;
}

button {
  padding: 8px 12px;
  border-color: var(--accent);
  background: var(--accent);
  color: #ffffff;
  cursor: pointer;
  font-weight: 600;
}

button:hover:not(:disabled) {
  background: var(--accent-strong);
}

button:disabled {
  border-color: #c6cbd6;
  background: #c6cbd6;
  cursor: default;
}

.check-row {
  grid-template-columns: 18px 1fr;
  align-items: center;
}

.check-row input {
  width: 18px;
  min-height: 18px;
}

.item-list {
  display: grid;
  gap: 8px;
  margin-top: 16px;
}

.item-button,
.job-row {
  display: grid;
  gap: 4px;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #ffffff;
  color: var(--text);
  text-align: left;
}

.item-button {
  cursor: pointer;
}

.item-button.is-active {
  border-color: var(--accent);
  outline: 2px solid rgba(15, 118, 110, 0.16);
}

.item-title {
  overflow-wrap: anywhere;
  font-size: 14px;
  font-weight: 650;
}

.item-meta {
  overflow-wrap: anywhere;
  color: var(--muted);
  font-size: 12px;
}

.job-row[data-status="done"] .item-title {
  color: var(--ok);
}

.job-row[data-status="failed"] .item-title {
  color: var(--danger);
}

.render-form {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}

.toast {
  position: fixed;
  right: 16px;
  bottom: 16px;
  max-width: min(420px, calc(100vw - 32px));
  min-height: 0;
  padding: 0;
  border-radius: 6px;
  background: #172033;
  color: #ffffff;
  font-size: 13px;
  opacity: 0;
  transform: translateY(8px);
  transition: opacity 160ms ease, transform 160ms ease, padding 160ms ease;
  pointer-events: none;
}

.toast.is-visible {
  padding: 10px 12px;
  opacity: 1;
  transform: translateY(0);
}

@media (max-width: 1080px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .pane {
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }
}

@media (max-width: 680px) {
  .topbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .context-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **步骤 5：创建第一版 JavaScript**

创建 `frontend/app.js`：

```javascript
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);

  async function requestJson(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });
    const text = await response.text();
    const payload = text ? JSON.parse(text) : null;
    if (!response.ok) {
      const detail = payload && payload.detail ? payload.detail : response.statusText;
      throw new Error(detail);
    }
    return payload;
  }

  async function init() {
    const health = await requestJson("/api/health");
    $("apiStatus").textContent = `${health.service}: ${health.status}`;
  }

  document.addEventListener("DOMContentLoaded", () => {
    init().catch((error) => {
      $("apiStatus").textContent = error.message;
    });
  });
})();
```

- [ ] **步骤 6：修改 FastAPI，让它托管前端**

修改 `video_slicer/api/app.py`。

增加 import：

```python
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
```

在 `create_app()` 上方增加：

```python
def default_frontend_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "frontend"
```

把 `create_app` 函数签名从：

```python
def create_app(
    *,
    project_root: Path | str | None = None,
    store: LocalProjectStore | None = None,
    job_runner: Any | None = None,
) -> FastAPI:
```

改成：

```python
def create_app(
    *,
    project_root: Path | str | None = None,
    store: LocalProjectStore | None = None,
    job_runner: Any | None = None,
    frontend_dir: Path | str | None = None,
) -> FastAPI:
```

在 `create_app()` 内部，`app.state.job_runner = ...` 后面加入：

```python
    static_dir = Path(frontend_dir) if frontend_dir is not None else default_frontend_dir()
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=static_dir), name="assets")

        @app.get("/", response_class=HTMLResponse, include_in_schema=False)
        def frontend_index() -> str:
            return (static_dir / "index.html").read_text(encoding="utf-8")
```

- [ ] **步骤 7：运行任务 1 测试**

运行：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_frontend_static
```

预期：

```text
Ran 2 tests
OK
```

- [ ] **步骤 8：提交任务 1**

运行：

```powershell
git add frontend/index.html frontend/styles.css frontend/app.js video_slicer/api/app.py tests/test_frontend_static.py
git commit -m "feat: serve local frontend workspace"
```

---

### 任务 2：实现项目、上下文、版本、渲染和任务状态 UI

**文件：**
- 修改：`frontend/app.js`
- 修改：`tests/test_frontend_static.py`

**接口：**
- 使用：
  - `GET /api/health`
  - `GET /api/projects`
  - `POST /api/projects`
  - `GET /api/projects/{project_id}`
  - `PUT /api/projects/{project_id}/context`
  - `GET /api/projects/{project_id}/versions`
  - `POST /api/projects/{project_id}/versions`
  - `POST /api/projects/{project_id}/versions/{version_id}/render`
  - `GET /api/projects/{project_id}/jobs`
  - `GET /api/projects/{project_id}/jobs/{job_id}`
- 产出：
  - 浏览器状态：当前项目、当前版本、当前渲染任务。
  - 前端校验：如果知道原视频时长，目标时长必须小于原视频时长。
  - 任务轮询：任务进入 `done`、`failed` 或 `cancelled` 后停止轮询。

- [ ] **步骤 1：补充失败的前端契约测试**

在 `tests/test_frontend_static.py` 顶部增加：

```python
from pathlib import Path
```

在 `FrontendStaticTest` 类中追加：

```python
    def test_frontend_contains_required_workspace_controls(self):
        html = Path("frontend/index.html").read_text(encoding="utf-8")

        required_ids = [
            "projectForm",
            "sourceVideoPath",
            "sourceDurationSeconds",
            "contextForm",
            "contextTitle",
            "correctSynopsis",
            "storyFocus",
            "versionForm",
            "targetDurationSeconds",
            "voiceCloneId",
            "bgmPath",
            "renderForm",
            "ttsMode",
            "jobList",
        ]
        for element_id in required_ids:
            self.assertIn(f'id="{element_id}"', html)

    def test_frontend_javascript_uses_backend_contract(self):
        script = Path("frontend/app.js").read_text(encoding="utf-8")

        required_snippets = [
            'requestJson("/api/projects"',
            "source_duration_seconds",
            "context_packet",
            "target_duration_seconds",
            "voice_clone_id",
            "bgm_path",
            "voiceover_speed",
            "targetDuration >= state.selectedProject.source_duration_seconds",
            "setInterval",
            "clearInterval",
        ]
        for snippet in required_snippets:
            self.assertIn(snippet, script)
```

- [ ] **步骤 2：运行测试，确认它会失败**

运行：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_frontend_static
```

预期：

```text
FAILED
```

失败原因应该是 `frontend/app.js` 还没有包含 `target_duration_seconds`、`setInterval` 等逻辑。

- [ ] **步骤 3：替换 `frontend/app.js` 为完整工作台逻辑**

把 `frontend/app.js` 替换为：

```javascript
(() => {
  "use strict";

  const state = {
    projects: [],
    versions: [],
    jobs: [],
    selectedProject: null,
    selectedVersion: null,
    activeJob: null,
    pollTimer: null,
  };

  const $ = (id) => document.getElementById(id);

  async function requestJson(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });
    const text = await response.text();
    const payload = text ? JSON.parse(text) : null;
    if (!response.ok) {
      const detail = payload && payload.detail ? payload.detail : response.statusText;
      throw new Error(detail);
    }
    return payload;
  }

  function showMessage(message) {
    const toast = $("statusMessage");
    toast.textContent = message;
    toast.classList.add("is-visible");
    window.setTimeout(() => toast.classList.remove("is-visible"), 2600);
  }

  function numberValue(id) {
    const value = $(id).value.trim();
    return value ? Number(value) : null;
  }

  function splitLines(value) {
    return value
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
  }

  function listToText(value) {
    return Array.isArray(value) ? value.join("\n") : "";
  }

  function parseCharacters(value) {
    return splitLines(value).map((line) => {
      const parts = line.split(/[:：]/);
      if (parts.length >= 2) {
        return {
          name: parts.shift().trim(),
          role: parts.join("：").trim(),
        };
      }
      return { name: line };
    });
  }

  function charactersToText(value) {
    if (!Array.isArray(value)) {
      return "";
    }
    return value
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }
        const name = item.name || "";
        const role = item.role || item.description || "";
        return role ? `${name}：${role}` : name;
      })
      .filter(Boolean)
      .join("\n");
  }

  function setActionState() {
    const hasProject = Boolean(state.selectedProject);
    const hasVersion = Boolean(state.selectedVersion);
    $("saveContextButton").disabled = !hasProject;
    $("createVersionButton").disabled = !hasProject;
    $("startRenderButton").disabled = !hasProject || !hasVersion;
  }

  function projectTitle(project) {
    const title = project.context_packet && project.context_packet.title;
    return title || project.source_video_path || project.project_id;
  }

  function renderProjects() {
    const list = $("projectList");
    list.innerHTML = "";
    state.projects.forEach((project) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "item-button";
      if (state.selectedProject && state.selectedProject.project_id === project.project_id) {
        button.classList.add("is-active");
      }
      button.innerHTML = `
        <span class="item-title">${projectTitle(project)}</span>
        <span class="item-meta">${project.project_id}</span>
      `;
      button.addEventListener("click", () => selectProject(project.project_id));
      list.appendChild(button);
    });
  }

  function renderVersions() {
    const list = $("versionList");
    list.innerHTML = "";
    state.versions.forEach((version) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "item-button";
      if (state.selectedVersion && state.selectedVersion.version_id === version.version_id) {
        button.classList.add("is-active");
      }
      const settings = version.settings;
      button.innerHTML = `
        <span class="item-title">${settings.target_duration_seconds}s · ${settings.audio_mode}</span>
        <span class="item-meta">${version.version_id}</span>
      `;
      button.addEventListener("click", () => {
        state.selectedVersion = version;
        renderVersions();
        setActionState();
      });
      list.appendChild(button);
    });
  }

  function renderJobs() {
    const list = $("jobList");
    list.innerHTML = "";
    state.jobs.forEach((job) => {
      const row = document.createElement("div");
      row.className = "job-row";
      row.dataset.status = job.status;
      row.innerHTML = `
        <span class="item-title">${job.status} · ${job.current_stage}</span>
        <span class="item-meta">${job.job_id}</span>
        <span class="item-meta">${job.error_message || JSON.stringify(job.export_paths || {})}</span>
      `;
      list.appendChild(row);
    });
  }

  function fillContextForm(project) {
    const packet = project.context_packet || {};
    $("contextTitle").value = packet.title || "";
    $("sourceType").value = packet.source_type || "";
    $("contextCharacters").value = charactersToText(packet.characters);
    $("correctSynopsis").value = packet.correct_synopsis || "";
    $("storyFocus").value = listToText(packet.story_focus);
    $("externalKnowledge").value = listToText(packet.allowed_external_knowledge);
    $("forbiddenTerms").value = listToText(packet.forbidden_terms);
    $("forbiddenStoryFacts").value = listToText(packet.forbidden_story_facts);
    $("mustNotInclude").value = listToText(packet.must_not_include);
    $("ttsTerms").value = listToText(packet.tts_unfriendly_terms);
  }

  function buildContextPacket() {
    const existing = state.selectedProject && state.selectedProject.context_packet ? state.selectedProject.context_packet : {};
    return {
      ...existing,
      title: $("contextTitle").value.trim(),
      source_type: $("sourceType").value.trim(),
      characters: parseCharacters($("contextCharacters").value),
      correct_synopsis: $("correctSynopsis").value.trim(),
      story_focus: splitLines($("storyFocus").value),
      allowed_external_knowledge: splitLines($("externalKnowledge").value),
      forbidden_terms: splitLines($("forbiddenTerms").value),
      forbidden_story_facts: splitLines($("forbiddenStoryFacts").value),
      must_not_include: splitLines($("mustNotInclude").value),
      tts_unfriendly_terms: splitLines($("ttsTerms").value),
    };
  }

  async function loadProjects() {
    state.projects = await requestJson("/api/projects");
    renderProjects();
  }

  async function loadVersions(projectId) {
    state.versions = await requestJson(`/api/projects/${projectId}/versions`);
    state.selectedVersion = state.versions[0] || null;
    renderVersions();
  }

  async function loadJobs(projectId) {
    state.jobs = await requestJson(`/api/projects/${projectId}/jobs`);
    renderJobs();
  }

  async function selectProject(projectId) {
    state.selectedProject = await requestJson(`/api/projects/${projectId}`);
    fillContextForm(state.selectedProject);
    await loadVersions(projectId);
    await loadJobs(projectId);
    renderProjects();
    setActionState();
  }

  async function createProject(event) {
    event.preventDefault();
    const sourceVideoPath = $("sourceVideoPath").value.trim();
    const sourceDuration = numberValue("sourceDurationSeconds");
    if (!sourceVideoPath) {
      showMessage("视频路径不能为空");
      return;
    }
    const project = await requestJson("/api/projects", {
      method: "POST",
      body: JSON.stringify({
        source_video_path: sourceVideoPath,
        source_duration_seconds: sourceDuration,
      }),
    });
    await loadProjects();
    await selectProject(project.project_id);
    showMessage("项目已创建");
  }

  async function saveContext() {
    if (!state.selectedProject) {
      showMessage("先选择项目");
      return;
    }
    const projectId = state.selectedProject.project_id;
    state.selectedProject = await requestJson(`/api/projects/${projectId}/context`, {
      method: "PUT",
      body: JSON.stringify({
        context_packet: buildContextPacket(),
      }),
    });
    await loadProjects();
    renderProjects();
    showMessage("上下文已保存");
  }

  async function createVersion(event) {
    event.preventDefault();
    if (!state.selectedProject) {
      showMessage("先选择项目");
      return;
    }
    const targetDuration = numberValue("targetDurationSeconds");
    if (!targetDuration || targetDuration <= 0) {
      showMessage("目标时长必须大于 0");
      return;
    }
    if (
      state.selectedProject.source_duration_seconds &&
      targetDuration >= state.selectedProject.source_duration_seconds
    ) {
      showMessage("目标时长必须小于原视频时长");
      return;
    }
    const projectId = state.selectedProject.project_id;
    const version = await requestJson(`/api/projects/${projectId}/versions`, {
      method: "POST",
      body: JSON.stringify({
        target_duration_seconds: targetDuration,
        audio_mode: $("audioMode").value,
        voice_clone_id: $("voiceCloneId").value.trim(),
        bgm_path: $("bgmPath").value.trim(),
        voiceover_speed: numberValue("voiceoverSpeed") || 1.0,
        voiceover_volume: numberValue("voiceoverVolume") || 1.0,
        bgm_volume: numberValue("bgmVolume") || 0,
        subtitle_language: $("subtitleLanguage").value,
        aspect_ratio: $("aspectRatio").value,
        variant_goal: $("variantGoal").value.trim() || "manual",
      }),
    });
    await loadVersions(projectId);
    state.selectedVersion = version;
    renderVersions();
    setActionState();
    showMessage("版本已创建");
  }

  async function refreshActiveJob(projectId, jobId) {
    state.activeJob = await requestJson(`/api/projects/${projectId}/jobs/${jobId}`);
    await loadJobs(projectId);
    if (["done", "failed", "cancelled"].includes(state.activeJob.status)) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
      showMessage(`渲染结束：${state.activeJob.status}`);
    }
  }

  function startPolling(projectId, jobId) {
    if (state.pollTimer) {
      clearInterval(state.pollTimer);
    }
    state.pollTimer = setInterval(() => {
      refreshActiveJob(projectId, jobId).catch((error) => showMessage(error.message));
    }, 3000);
  }

  async function startRender(event) {
    event.preventDefault();
    if (!state.selectedProject || !state.selectedVersion) {
      showMessage("先选择项目和版本");
      return;
    }
    const projectId = state.selectedProject.project_id;
    const versionId = state.selectedVersion.version_id;
    const job = await requestJson(`/api/projects/${projectId}/versions/${versionId}/render`, {
      method: "POST",
      body: JSON.stringify({
        tts_mode: $("ttsMode").value,
        require_llm: $("requireLlm").checked,
        force_script: $("forceScript").checked,
        force_review: $("forceReview").checked,
        force_humanize: $("forceHumanize").checked,
        force_tts: $("forceTts").checked,
        no_fit_duration: false,
      }),
    });
    state.activeJob = job;
    await loadJobs(projectId);
    startPolling(projectId, job.job_id);
    showMessage("渲染任务已开始");
  }

  function bindEvents() {
    $("projectForm").addEventListener("submit", (event) => {
      createProject(event).catch((error) => showMessage(error.message));
    });
    $("saveContextButton").addEventListener("click", () => {
      saveContext().catch((error) => showMessage(error.message));
    });
    $("versionForm").addEventListener("submit", (event) => {
      createVersion(event).catch((error) => showMessage(error.message));
    });
    $("renderForm").addEventListener("submit", (event) => {
      startRender(event).catch((error) => showMessage(error.message));
    });
  }

  async function init() {
    bindEvents();
    const health = await requestJson("/api/health");
    $("apiStatus").textContent = `${health.service}: ${health.status}`;
    await loadProjects();
    setActionState();
  }

  document.addEventListener("DOMContentLoaded", () => {
    init().catch((error) => {
      $("apiStatus").textContent = error.message;
      showMessage(error.message);
    });
  });
})();
```

- [ ] **步骤 4：运行前端静态和契约测试**

运行：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_frontend_static
```

预期：

```text
Ran 4 tests
OK
```

- [ ] **步骤 5：运行 API 回归测试**

运行：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_api_app tests.test_api_projects tests.test_api_jobs
```

预期：

```text
OK
```

- [ ] **步骤 6：提交任务 2**

运行：

```powershell
git add frontend/app.js tests/test_frontend_static.py
git commit -m "feat: add local frontend workflow"
```

---

### 任务 3：补充前端职责和启动文档

**文件：**
- 修改：`README.md`
- 修改：`docs/README.zh-CN.md`
- 修改：`docs/code-map.zh-CN.md`
- 修改：`docs/development-rules.zh-CN.md`
- 修改：`docs/superpowers/plans/2026-07-10-local-frontend-mvp.zh-CN.md`

- [ ] **步骤 1：更新 `README.md` 的前端启动说明**

在本地 API 启动说明后加入：

````markdown
## 启动本地前端

前端由 FastAPI 直接托管。启动本地后端后，浏览器打开：

```text
http://127.0.0.1:8000/
```

这个页面可以创建项目、编辑上下文包、创建版本、启动渲染并查看任务状态。第一版使用本地视频路径；视频文件仍然放在不受 Git 管理的 `videos/` 或本机其他目录。
````

- [ ] **步骤 2：更新 `docs/README.zh-CN.md` 的目录职责**

在顶层目录表里加入：

```markdown
| `frontend/` | 本地浏览器工作台：项目、上下文、版本、渲染和任务状态页面 | 提交 |
```

加入放置规则：

```markdown
- 新的浏览器工作台页面、静态 CSS、静态 JS：放到 `frontend/`。前端只能调用 `video_slicer/api/` 暴露的 HTTP 接口，不能直接读写 `projects.local/`。
```

- [ ] **步骤 3：更新 `docs/code-map.zh-CN.md`**

在架构概览附近加入：

```text
本地浏览器工作台
  -> frontend/index.html / frontend/styles.css / frontend/app.js
  -> video_slicer.api
  -> LocalProjectStore / pipeline
```

在本地 API 模块前加入：

```markdown
## 本地前端工作台

### `frontend/index.html`

职责：

- 提供项目创建、上下文编辑、版本配置、渲染启动和任务状态区域。
- 只包含静态结构，不写业务决策。
- 控件 ID 要和 `frontend/app.js` 保持一致。

### `frontend/styles.css`

职责：

- 提供本地工具型界面样式。
- 使用稳定的 grid 和 pane 布局，避免动态内容挤压表单。
- 不放营销页 hero、装饰性背景、嵌套卡片。

### `frontend/app.js`

职责：

- 调用 `/api/...` 接口。
- 维护 selected project、selected version、active job 三类浏览器状态。
- 在创建版本前校验目标时长小于原视频时长。
- 启动渲染后轮询 job 状态，并在 `done`、`failed`、`cancelled` 时停止轮询。

边界：

- 前端不直接调用 FFmpeg、LLM、TTS 或本地 JSON 存储。
- 前端不包含任何具体影视片段的人名、剧情或梗概。
- 如果需要新增可配置项，先更新 `CreateVersionRequest` 或 context packet，再更新前端字段。
```

- [ ] **步骤 4：更新 `docs/development-rules.zh-CN.md`**

在放置规则表里加入：

```markdown
| 本地前端页面、样式、浏览器交互 | `frontend/` |
```

在测试映射表里加入：

```markdown
| `frontend/index.html` / `frontend/styles.css` / `frontend/app.js` | `tests/test_frontend_static.py` |
```

加入前端规则：

```markdown
- 前端只能通过 `/api/...` 和后端交互；不能在浏览器代码里拼接或修改 `projects.local/` 文件路径。
- 前端表单字段必须使用通用命名，不能写入某个具体视频的人名、剧情或专用规则。
- 如果新增目标时长、声音、BGM、字幕、画幅相关设置，必须同时更新 `CreateVersionRequest`、前端控件和对应测试。
```

- [ ] **步骤 5：实现完成后标记计划状态**

全部实现并验证通过后，在本计划 `**技术栈：**` 下方加入：

```markdown
**执行状态：** 已在本地实现并验证。
```

- [ ] **步骤 6：提交任务 3**

运行：

```powershell
git add README.md docs/README.zh-CN.md docs/code-map.zh-CN.md docs/development-rules.zh-CN.md docs/superpowers/plans/2026-07-10-local-frontend-mvp.zh-CN.md
git commit -m "docs: document local frontend workspace"
```

---

### 任务 4：完整验证

**文件：**
- 验证任务 1 到任务 3 修改过的所有文件。

- [ ] **步骤 1：运行前端测试**

运行：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_frontend_static
```

预期：

```text
OK
```

- [ ] **步骤 2：运行 API 测试**

运行：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_api_app tests.test_api_projects tests.test_api_jobs
```

预期：

```text
OK
```

- [ ] **步骤 3：运行核心 pipeline 回归测试**

运行：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_script_generation tests.test_rendering tests.test_alignment tests.test_pipeline tests.test_project_models tests.test_project_store tests.test_pipeline_records tests.test_quality_report
```

预期：

```text
OK
```

- [ ] **步骤 4：运行编译检查**

运行：

```powershell
.\.venv\Scripts\python.exe -m compileall video_slicer tests scripts
```

预期：退出码为 0。

- [ ] **步骤 5：运行空白字符检查**

运行：

```powershell
git diff --check
```

预期：退出码为 0。

- [ ] **步骤 6：扫描公共代码里是否误写具体视频特征**

运行：

```powershell
rg "刘华强|封彪|征服|孙红雷|买瓜|瓜摊|西瓜|birds|bird" video_slicer llm_providers tts_providers scripts frontend tests
```

预期：退出码为 1，没有匹配。

- [ ] **步骤 7：确认 Git 范围**

运行：

```powershell
git status --short
git ls-files outputs videos .env assets\voice_refs assets\bgm projects.local
```

预期只有这些本地资源占位文件被 Git 跟踪：

```text
assets/bgm/.gitkeep
assets/voice_refs/.gitkeep
videos/.gitkeep
```

`projects.local`、`.env`、`outputs`、生成的视频、生成的音频、BGM 文件、声音参考文件都不应该出现。

- [ ] **步骤 8：浏览器手动冒烟测试**

运行：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_api
```

打开：

```text
http://127.0.0.1:8000/
```

预期：

- 页面标题是 `视频切片工作台`。
- `apiStatus` 显示 `video-slicer-local-api: ok`。
- 用 `videos/demo.mp4` 和原视频时长 `300` 创建项目后，项目列表出现新项目。
- 用目标时长 `90` 创建版本可以成功。
- 用目标时长 `300` 创建版本时，页面提示 `目标时长必须小于原视频时长`，并且不会调用后端创建版本。

- [ ] **步骤 9：如果验证过程改了文档，则提交验证说明**

如果任务 4 导致文档发生修改，运行：

```powershell
git add README.md docs/README.zh-CN.md docs/code-map.zh-CN.md docs/development-rules.zh-CN.md docs/superpowers/plans/2026-07-10-local-frontend-mvp.zh-CN.md
git commit -m "docs: record frontend verification"
```

如果任务 4 没有造成任何文件修改，不要创建空提交。

---

## 本计划完成后的 UI 契约

浏览器工作台支持这些用户动作：

```text
创建项目
选择项目
编辑上下文包
保存上下文包
创建版本
选择版本
启动渲染
轮询任务状态
```

前端会调用这些后端路由：

```text
GET  /api/health
POST /api/projects
GET  /api/projects
GET  /api/projects/{project_id}
PUT  /api/projects/{project_id}/context
POST /api/projects/{project_id}/versions
GET  /api/projects/{project_id}/versions
POST /api/projects/{project_id}/versions/{version_id}/render
GET  /api/projects/{project_id}/jobs
GET  /api/projects/{project_id}/jobs/{job_id}
```

前端不会直接调用：

```text
ffmpeg
Fish Audio
DashScope
Ocool
OpenAI-compatible model providers
LocalProjectStore JSON files directly
```

## 下一步产品边界

本计划之后，下一份独立计划应该做 **文案预览与编辑 API**：

- 可以只生成文案，不直接渲染。
- 把生成文案和用户最终确认文案存入 `VersionRecord`。
- 前端可以预览完整解说文案。
- 最终渲染使用用户确认后的文案。

这件事应该单独做，因为它会同时改变后端 pipeline 阶段、项目记录结构和前端工作流。

## 自查

**需求覆盖：** 这份计划解决了当前打开后端只有 API JSON 的问题。它会加一个真实的浏览器工作台，同时保留现有后端 API、目标时长校验、Fish/Ocool TTS 选择、BGM 字段、配音速度和音量字段、上下文包编辑、渲染任务创建和任务轮询。

**占位符扫描：** 计划写明了精确文件、精确路由契约、精确测试、精确代码片段、精确命令、预期失败、预期通过条件和提交信息，没有使用未说明的占位步骤。

**类型一致性：** 前端请求字段和 `CreateProjectRequest`、`UpdateProjectContextRequest`、`CreateVersionRequest`、`CreateRenderJobRequest` 保持一致：`source_video_path`、`source_duration_seconds`、`context_packet`、`target_duration_seconds`、`audio_mode`、`voice_clone_id`、`bgm_path`、`voiceover_speed`、`voiceover_volume`、`bgm_volume`、`subtitle_language`、`aspect_ratio`、`variant_goal`、`tts_mode`、`require_llm`、`force_script`、`force_review`、`force_humanize`、`force_tts`、`no_fit_duration`。
