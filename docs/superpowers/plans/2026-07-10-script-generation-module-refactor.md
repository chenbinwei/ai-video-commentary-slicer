# Script Generation Module Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract voiceover script generation, semantic review, humanized polish, JSON parsing, and script validation from `video_slicer/pipeline.py` into `video_slicer/script_generation.py` without changing current CLI behavior.

**Architecture:** Keep `video_slicer.pipeline` as the orchestration layer. Move script-specific prompt construction, LLM response parsing, forbidden-term validation, humanized polish checks, fallback script creation, and script text/diff output helpers into `video_slicer.script_generation`. Provider API details stay in `llm_providers/`; alignment and rendering stay in their existing modules.

**Tech Stack:** Python 3, standard library `json`, `os`, `re`, `pathlib.Path`, `unittest`, `unittest.mock`, existing DashScope provider.

**Execution Status:** Implemented and verified locally.

## Global Constraints

- Keep common code reusable across videos; do not add current-demo people, plot terms, or forbidden words to shared code.
- Do not commit `.env`, `outputs/`, `videos/*.mp4`, `assets/voice_refs/*`, `assets/bgm/*`, or generated media.
- Preserve current CLI behavior for `scripts.run_pipeline`, `1.py`, and `scripts.run_batch`.
- Use TDD for behavior changes: write the failing test, run it and confirm the expected failure, implement the smallest change, then run the test again.
- Unit tests must not call network APIs or FFmpeg.
- Do not move provider request details into `video_slicer/script_generation.py`; import `llm_providers.dashscope.text_completion` only at call sites as current `pipeline.py` does.
- Keep `pipeline.py` as orchestration only; do not move transcription, TTS synthesis, audio fitting, alignment, rendering, or project records in this plan.
- Update `docs/code-map.zh-CN.md`, `docs/development-rules.zh-CN.md`, and `docs/README.zh-CN.md` after the module split.

---

## File Structure

Create:

- `video_slicer/script_generation.py`
  - Owns voiceover prompt helpers, JSON response parsing, script validation, LLM script generation/review/humanization, fallback voiceover script creation, and script output writing.
  - Exports:
    - `voiceover_length_requirements(target_duration: float) -> dict[str, int]`
    - `parse_json_response(text: str) -> dict[str, Any]`
    - `parse_llm_json_response(text: str, *, model: str, base_url: str, api_key: str) -> dict[str, Any]`
    - `find_terms_in_text(text: str, terms: list[str]) -> list[str]`
    - `terms_from_context(context_packet: dict[str, Any] | None, keys: tuple[str, ...]) -> list[str]`
    - `humanize_unsafe_terms_from_context(context_packet: dict[str, Any] | None) -> list[str]`
    - `tts_unfriendly_terms_from_context(context_packet: dict[str, Any] | None) -> list[str]`
    - `blocked_humanize_terms(text: str, context_packet: dict[str, Any] | None) -> list[str]`
    - `narration_style_violations(voiceover_doc: dict[str, Any], context_packet: dict[str, Any] | None) -> list[str]`
    - `forbidden_terms_from_context(context_packet: dict[str, Any] | None) -> list[str]`
    - `validate_voiceover_doc(voiceover_doc: dict[str, Any], context_packet: dict[str, Any] | None) -> None`
    - `generate_voiceover_with_llm(...) -> dict[str, Any] | None`
    - `review_voiceover_with_llm(...) -> dict[str, Any] | None`
    - `humanize_voiceover_with_llm(...) -> dict[str, Any] | None`
    - `write_humanize_diff(before_doc: dict[str, Any], after_doc: dict[str, Any], path: Path) -> None`
    - `fallback_voiceover_script(segments: list[dict[str, Any]], target_duration: float) -> dict[str, Any]`
    - `write_voiceover_outputs(...) -> None`
- `tests/test_script_generation.py`
  - Tests pure validation, JSON parsing, prompt-call behavior with mocked providers, fallback script output, humanize rejection, and script output files.

Modify:

- `video_slicer/pipeline.py`
  - Import script-generation functions from `video_slicer.script_generation`.
  - Delete moved function definitions after tests pass.
  - Keep `transcript_for_prompt()` in `pipeline.py` only if still needed by legacy clip selection functions; otherwise move it with script generation when no pipeline-local callers remain.
- `tests/test_pipeline.py`
  - Stop importing script validation/fallback helpers from `video_slicer.pipeline`.
  - Keep pipeline-only tests for target duration and timeline validation.
- `README.md`
  - Add `video_slicer/script_generation.py` to project structure.
- `docs/README.zh-CN.md`
  - Add script-generation ownership to core code table.
- `docs/code-map.zh-CN.md`
  - Move 文案生成/审稿/润色/文案校验 rows to `video_slicer.script_generation::*`.
  - Mark “第四阶段：拆 Script Generation” as completed after implementation.
- `docs/development-rules.zh-CN.md`
  - Change 文案生成、审稿、润色 location from “现在在 pipeline.py” to `video_slicer/script_generation.py`.

Do not modify:

- `llm_providers/`
- `tts_providers/`
- `video_slicer/alignment.py`
- `video_slicer/rendering.py`
- `video_slicer/quality_report.py`
- `video_slicer/project_models.py`
- `video_slicer/project_store.py`
- `.env`
- `context.example.json`

---

### Task 1: Create Script Generation Module for Pure Helpers

**Files:**
- Create: `video_slicer/script_generation.py`
- Create: `tests/test_script_generation.py`
- Modify: `video_slicer/pipeline.py`
- Modify: `tests/test_pipeline.py`

**Interfaces:**
- Consumes:
  - `video_slicer.context_packet.narration_rules_for_prompt`
  - `video_slicer.context_packet.compact_context_for_prompt`
  - `video_slicer.pipeline.write_srt` only until Task 4 moves script output helpers.
- Produces:
  - `voiceover_length_requirements(target_duration: float) -> dict[str, int]`
  - `parse_json_response(text: str) -> dict[str, Any]`
  - `parse_llm_json_response(text: str, *, model: str, base_url: str, api_key: str) -> dict[str, Any]`
  - `validate_voiceover_doc(voiceover_doc: dict[str, Any], context_packet: dict[str, Any] | None) -> None`
  - `fallback_voiceover_script(segments: list[dict[str, Any]], target_duration: float) -> dict[str, Any]`

- [ ] **Step 1: Write failing tests for new module imports**

Create `tests/test_script_generation.py`:

```python
import json
import unittest
from unittest.mock import patch

from video_slicer.script_generation import (
    fallback_voiceover_script,
    forbidden_terms_from_context,
    parse_json_response,
    parse_llm_json_response,
    validate_voiceover_doc,
    voiceover_length_requirements,
)


class ScriptGenerationPureHelperTest(unittest.TestCase):
    def test_voiceover_length_requirements_scale_with_target_duration(self):
        result = voiceover_length_requirements(120.0)

        self.assertEqual(result["target_duration_seconds"], 120)
        self.assertGreaterEqual(result["min_voiceover_items"], 8)
        self.assertGreater(result["max_voiceover_items"], result["min_voiceover_items"])
        self.assertGreater(result["ideal_total_cjk_chars"], result["min_total_cjk_chars"])
        self.assertLess(result["ideal_total_cjk_chars"], result["max_total_cjk_chars"])

    def test_parse_json_response_accepts_markdown_wrapped_json(self):
        result = parse_json_response('```json\\n{"voiceover": [{"text": "你好"}]}\\n```')

        self.assertEqual(result["voiceover"][0]["text"], "你好")

    def test_parse_llm_json_response_repairs_invalid_json_once(self):
        broken = '{"voiceover": [{"text": "你好"}'
        fixed = '{"voiceover": [{"text": "你好"}]}'

        with patch("llm_providers.dashscope.text_completion", return_value=fixed) as mocked_completion:
            result = parse_llm_json_response(
                broken,
                model="qwen-plus-latest",
                base_url="https://example.test",
                api_key="sk-test",
            )

        self.assertEqual(result["voiceover"][0]["text"], "你好")
        mocked_completion.assert_called_once()

    def test_fallback_voiceover_script_passes_text_validation(self):
        voiceover_doc = fallback_voiceover_script(
            [{"id": 1, "start": 0.0, "end": 2.0, "text": "主角走进房间。"}],
            target_duration=10.0,
        )

        validate_voiceover_doc(voiceover_doc, context_packet={})

    def test_default_forbidden_terms_do_not_include_project_specific_terms(self):
        terms = forbidden_terms_from_context(context_packet={})

        self.assertIn("VOICEOVER", terms)
        self.assertNotIn("bird", terms)
        self.assertNotIn("birds", terms)

    def test_validate_voiceover_doc_rejects_tts_unfriendly_terms(self):
        voiceover_doc = {
            "title": "测试",
            "summary": "测试",
            "voiceover": [{"text": "他说得平，但意思很清楚。"}],
        }

        with self.assertRaises(SystemExit) as ctx:
            validate_voiceover_doc(voiceover_doc, context_packet={})

        self.assertIn("TTS-unfriendly", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new test and confirm the expected failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_script_generation
```

Expected:

```text
ModuleNotFoundError: No module named 'video_slicer.script_generation'
```

- [ ] **Step 3: Create `video_slicer/script_generation.py` by moving pure helpers unchanged**

Create `video_slicer/script_generation.py` with this import block:

```python
"""Voiceover script generation, review, validation, and output helpers."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from video_slicer.context_packet import (
    compact_context_for_prompt,
    narration_rules_for_prompt,
)
```

Move these exact existing definitions from `video_slicer/pipeline.py` into `video_slicer/script_generation.py` without changing their bodies:

```text
compact_voiceover_generation_instructions
compact_voiceover_review_instructions
voiceover_length_requirements
extract_response_text
parse_json_response
parse_llm_json_response
DEFAULT_FORBIDDEN_TERMS
DEFAULT_TTS_UNFRIENDLY_TERMS
find_terms_in_text
terms_from_context
humanize_unsafe_terms_from_context
tts_unfriendly_terms_from_context
blocked_humanize_terms
narration_style_violations
forbidden_terms_from_context
validate_voiceover_doc
fallback_voiceover_script
```

Do not move these in Task 1:

```text
generate_voiceover_with_llm
review_voiceover_with_llm
humanize_voiceover_with_llm
write_humanize_diff
write_voiceover_outputs
```

- [ ] **Step 4: Import moved helpers back into `pipeline.py`**

Add this import block to `video_slicer/pipeline.py`:

```python
from video_slicer.script_generation import (
    fallback_voiceover_script,
    forbidden_terms_from_context,
    validate_voiceover_doc,
)
```

Only import the helpers that `pipeline.py` or existing tests still consume after Task 1. Do not import unused prompt helper functions.

- [ ] **Step 5: Update `tests/test_pipeline.py` imports**

Replace:

```python
from video_slicer.pipeline import (
    fallback_voiceover_script,
    forbidden_terms_from_context,
    validate_requested_target_duration,
    validate_timeline_duration,
    validate_voiceover_doc,
)
```

With:

```python
from video_slicer.pipeline import (
    validate_requested_target_duration,
    validate_timeline_duration,
)
from video_slicer.script_generation import (
    fallback_voiceover_script,
    forbidden_terms_from_context,
    validate_voiceover_doc,
)
```

- [ ] **Step 6: Run Task 1 tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_script_generation tests.test_pipeline
```

Expected:

```text
OK
```

- [ ] **Step 7: Commit Task 1 after confirming the changed-file scope**

Run:

```powershell
git add video_slicer/script_generation.py video_slicer/pipeline.py tests/test_script_generation.py tests/test_pipeline.py
git commit -m "refactor: extract script generation helpers"
```

If the worktree contains unrelated local changes, skip the commit and report the exact files that should be included.

---

### Task 2: Move LLM Script Generation, Review, and Humanization

**Files:**
- Modify: `video_slicer/script_generation.py`
- Modify: `video_slicer/pipeline.py`
- Modify: `tests/test_script_generation.py`

**Interfaces:**
- Consumes:
  - `transcript_for_prompt(segments: list[dict[str, Any]]) -> str`
  - `compact_context_for_prompt(context_packet: dict[str, Any] | None) -> dict[str, Any]`
  - `narration_rules_for_prompt(context_packet: dict[str, Any]) -> str`
  - `parse_llm_json_response(...) -> dict[str, Any]`
  - `voiceover_length_requirements(...) -> dict[str, int]`
- Produces:
  - `generate_voiceover_with_llm(...) -> dict[str, Any] | None`
  - `review_voiceover_with_llm(...) -> dict[str, Any] | None`
  - `humanize_voiceover_with_llm(...) -> dict[str, Any] | None`

- [ ] **Step 1: Write failing mocked-provider tests**

Append these tests to `tests/test_script_generation.py`:

```python
    def test_generate_voiceover_with_llm_returns_none_without_api_key(self):
        from video_slicer.script_generation import generate_voiceover_with_llm

        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": ""}, clear=False):
            result = generate_voiceover_with_llm(
                segments=[{"id": 1, "start": 0.0, "end": 1.0, "text": "一句字幕"}],
                target_duration=30.0,
                model="qwen-plus-latest",
                base_url="https://example.test",
                context_packet={},
            )

        self.assertIsNone(result)

    def test_generate_voiceover_with_llm_calls_dashscope_provider(self):
        from video_slicer.script_generation import generate_voiceover_with_llm

        response_json = json.dumps({
            "title": "标题",
            "summary": "概括",
            "story_plan": [],
            "voiceover": [
                {
                    "text": "主角走进房间，冲突已经开始。",
                    "source_segment_ids": [1],
                    "context_refs": [],
                    "story_role": "hook",
                    "confidence": 0.8,
                    "visual_note": "进门画面",
                }
            ],
            "evidence_notes": [],
        }, ensure_ascii=False)
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}, clear=False):
            with patch("llm_providers.dashscope.text_completion", return_value=response_json) as mocked_completion:
                result = generate_voiceover_with_llm(
                    segments=[{"id": 1, "start": 0.0, "end": 1.0, "speaker": "UNKNOWN", "text": "一句字幕"}],
                    target_duration=30.0,
                    model="qwen-plus-latest",
                    base_url="https://example.test",
                    context_packet={"correct_synopsis": "只允许使用已知剧情。"},
                )

        self.assertEqual(result["voiceover"][0]["source_segment_ids"], [1])
        mocked_completion.assert_called_once()
        kwargs = mocked_completion.call_args.kwargs
        self.assertEqual(kwargs["model"], "qwen-plus-latest")
        self.assertEqual(kwargs["base_url"], "https://example.test")
        self.assertEqual(kwargs["api_key"], "sk-test")

    def test_review_voiceover_with_llm_marks_reviewed(self):
        from video_slicer.script_generation import review_voiceover_with_llm

        response_json = json.dumps({
            "title": "标题",
            "summary": "概括",
            "voiceover": [{"text": "主角语气平静。", "source_segment_ids": [1]}],
            "review_notes": ["修正口播"],
            "read_aloud_checks": ["无英文"],
        }, ensure_ascii=False)
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}, clear=False):
            with patch("llm_providers.dashscope.text_completion", return_value=response_json):
                result = review_voiceover_with_llm(
                    voiceover_doc={"voiceover": [{"text": "主角说得平。", "source_segment_ids": [1]}]},
                    segments=[{"id": 1, "start": 0.0, "end": 1.0, "speaker": "UNKNOWN", "text": "字幕"}],
                    target_duration=30.0,
                    model="qwen-plus-latest",
                    base_url="https://example.test",
                    context_packet={},
                )

        self.assertTrue(result["reviewed"])
        self.assertEqual(result["review_model"], "qwen-plus-latest")

    def test_humanize_voiceover_rejects_unsafe_rows_and_keeps_original(self):
        from video_slicer.script_generation import humanize_voiceover_with_llm

        response_json = json.dumps({
            "humanize_notes": ["尝试润色"],
            "humanized_voiceover": [{"index": 1, "text": "他说得平，但意思很清楚。"}],
        }, ensure_ascii=False)
        original = {
            "title": "标题",
            "summary": "概括",
            "voiceover": [{"text": "他语气平静，意思很清楚。", "source_segment_ids": [1]}],
        }
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}, clear=False):
            with patch("llm_providers.dashscope.text_completion", return_value=response_json):
                result = humanize_voiceover_with_llm(
                    voiceover_doc=original,
                    target_duration=30.0,
                    model="qwen-plus-latest",
                    base_url="https://example.test",
                    context_packet={},
                )

        self.assertEqual(result["voiceover"][0]["text"], "他语气平静，意思很清楚。")
        self.assertTrue(result["humanized"])
        self.assertIn("自动丢弃不可靠润色句", result["humanize_notes"][-1])
```

- [ ] **Step 2: Run tests and confirm the expected failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_script_generation
```

Expected: import errors for `generate_voiceover_with_llm`, `review_voiceover_with_llm`, and `humanize_voiceover_with_llm`.

- [ ] **Step 3: Move `transcript_for_prompt()` if required**

If `transcript_for_prompt()` is only used by script-generation functions after Task 2, move its exact existing definition from `pipeline.py` to `script_generation.py`.

If legacy clip-selection helpers still use it in `pipeline.py`, duplicate no logic. Instead move `transcript_for_prompt()` now and import it into `pipeline.py`:

```python
from video_slicer.script_generation import transcript_for_prompt
```

- [ ] **Step 4: Move LLM script functions unchanged**

Move these exact existing definitions from `video_slicer/pipeline.py` into `video_slicer/script_generation.py` without changing their bodies:

```text
generate_voiceover_with_llm
review_voiceover_with_llm
humanize_voiceover_with_llm
```

Ensure `video_slicer/script_generation.py` imports:

```python
from video_slicer.context_packet import (
    compact_context_for_prompt,
    narration_rules_for_prompt,
)
```

- [ ] **Step 5: Import moved LLM functions in `pipeline.py`**

Extend the `video_slicer.script_generation` import in `video_slicer/pipeline.py`:

```python
from video_slicer.script_generation import (
    fallback_voiceover_script,
    forbidden_terms_from_context,
    generate_voiceover_with_llm,
    humanize_voiceover_with_llm,
    review_voiceover_with_llm,
    validate_voiceover_doc,
)
```

If `transcript_for_prompt()` was moved, include it only if legacy clip selection functions still need it.

- [ ] **Step 6: Run Task 2 tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_script_generation tests.test_pipeline
```

Expected:

```text
OK
```

- [ ] **Step 7: Commit Task 2 after confirming the changed-file scope**

Run:

```powershell
git add video_slicer/script_generation.py video_slicer/pipeline.py tests/test_script_generation.py
git commit -m "refactor: extract llm script generation"
```

If the worktree contains unrelated local changes, skip the commit and report the exact files that should be included.

---

### Task 3: Move Script Output Writers

**Files:**
- Modify: `video_slicer/script_generation.py`
- Modify: `video_slicer/pipeline.py`
- Modify: `tests/test_script_generation.py`

**Interfaces:**
- Consumes:
  - `write_srt(segments: list[dict[str, Any]], path: Path) -> None`
- Produces:
  - `write_humanize_diff(before_doc: dict[str, Any], after_doc: dict[str, Any], path: Path) -> None`
  - `write_voiceover_outputs(voiceover_doc: dict[str, Any], alignment: list[dict[str, Any]], script_json_path: Path, script_txt_path: Path, voiceover_srt_path: Path) -> None`

- [ ] **Step 1: Write failing output-writer tests**

Append these tests to `tests/test_script_generation.py`:

```python
    def test_write_humanize_diff_writes_changed_lines(self):
        from tempfile import TemporaryDirectory

        from video_slicer.script_generation import write_humanize_diff

        before = {"voiceover": [{"text": "原句。"}]}
        after = {"voiceover": [{"text": "润色句。"}]}
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "voiceover_humanize_diff.txt"
            write_humanize_diff(before, after, path)
            text = path.read_text(encoding="utf-8")

        self.assertIn("原文：原句。", text)
        self.assertIn("润色：润色句。", text)

    def test_write_voiceover_outputs_writes_json_text_and_srt(self):
        from tempfile import TemporaryDirectory

        from video_slicer.script_generation import write_voiceover_outputs

        voiceover_doc = {"title": "标题", "summary": "概括", "voiceover": []}
        alignment = [
            {
                "text": "第一句。",
                "estimated_voiceover_start": 0.0,
                "estimated_voiceover_end": 1.2,
            },
            {
                "text": "第二句。",
                "voiceover_start": 1.2,
                "voiceover_end": 2.5,
                "estimated_voiceover_start": 1.2,
                "estimated_voiceover_end": 2.5,
            },
        ]
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            script_json_path = root / "voiceover_script.json"
            script_txt_path = root / "voiceover_script.txt"
            voiceover_srt_path = root / "voiceover.srt"
            write_voiceover_outputs(
                voiceover_doc,
                alignment,
                script_json_path,
                script_txt_path,
                voiceover_srt_path,
            )

            script_json = json.loads(script_json_path.read_text(encoding="utf-8"))
            script_txt = script_txt_path.read_text(encoding="utf-8")
            srt_text = voiceover_srt_path.read_text(encoding="utf-8")

        self.assertEqual(script_json["voiceover"][1]["text"], "第二句。")
        self.assertIn("# 标题", script_txt)
        self.assertIn("第一句。", script_txt)
        self.assertIn("00:00:01,200 --> 00:00:02,500", srt_text)
```

Also add these imports at the top of `tests/test_script_generation.py`:

```python
from pathlib import Path
```

- [ ] **Step 2: Run tests and confirm the expected failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_script_generation
```

Expected: import errors for `write_humanize_diff` and `write_voiceover_outputs`.

- [ ] **Step 3: Move output writer helpers**

Move these exact existing definitions from `video_slicer/pipeline.py` into `video_slicer/script_generation.py`:

```text
write_humanize_diff
write_voiceover_outputs
```

Because `write_voiceover_outputs()` uses SRT formatting, also move these exact existing definitions into `script_generation.py` if they no longer need to remain in `pipeline.py`:

```text
seconds_to_srt_time
write_srt
```

If `transcribe_audio()` still calls `write_srt()` in `pipeline.py`, import it back:

```python
from video_slicer.script_generation import write_srt
```

- [ ] **Step 4: Import moved output writers in `pipeline.py`**

Extend the import block:

```python
from video_slicer.script_generation import (
    fallback_voiceover_script,
    forbidden_terms_from_context,
    generate_voiceover_with_llm,
    humanize_voiceover_with_llm,
    review_voiceover_with_llm,
    validate_voiceover_doc,
    write_humanize_diff,
    write_srt,
    write_voiceover_outputs,
)
```

Only include `write_srt` if `transcribe_audio()` or legacy subtitle helpers still need it.

- [ ] **Step 5: Run Task 3 tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_script_generation tests.test_pipeline
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit Task 3 after confirming the changed-file scope**

Run:

```powershell
git add video_slicer/script_generation.py video_slicer/pipeline.py tests/test_script_generation.py
git commit -m "refactor: extract voiceover output writers"
```

If the worktree contains unrelated local changes, skip the commit and report the exact files that should be included.

---

### Task 4: Update Documentation and Run Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/README.zh-CN.md`
- Modify: `docs/code-map.zh-CN.md`
- Modify: `docs/development-rules.zh-CN.md`
- Modify: `docs/superpowers/plans/2026-07-10-script-generation-module-refactor.md`

**Interfaces:**
- Consumes:
  - `video_slicer.script_generation` public helpers from Tasks 1-3.
- Produces:
  - Documentation that identifies `script_generation.py` as the owner of script generation, review, humanization, validation, and script output helpers.

- [ ] **Step 1: Update README project structure**

In `README.md`, under `## 项目结构`, add:

```markdown
- `video_slicer/script_generation.py`：配音文案生成、语义审稿、真人口播润色、文案校验和脚本文本输出
```

- [ ] **Step 2: Update directory overview**

In `docs/README.zh-CN.md`, update the core ownership table with:

```markdown
| 配音文案生成、语义审稿、真人口播润色、文案校验 | `video_slicer/script_generation.py` |
```

- [ ] **Step 3: Update code map pipeline table**

In `docs/code-map.zh-CN.md`, change the script-related rows:

```markdown
| 文案生成 | `video_slicer.script_generation::generate_voiceover_with_llm()` | 调用 LLM 生成解说脚本 |
| 语义审稿 | `video_slicer.script_generation::review_voiceover_with_llm()` | 调用 LLM 做语义和口播审查 |
| 真人口播润色 | `video_slicer.script_generation::humanize_voiceover_with_llm()` | 调用 LLM 做口播润色 |
| 文案校验 | `video_slicer.script_generation::validate_voiceover_doc()` | 检查禁用词、英文残留、结构等 |
| 输出记录 | `video_slicer.script_generation::write_voiceover_outputs()`、`video_slicer.rendering::write_visual_time_mapping()` | 写脚本、字幕、映射 |
```

Add a section after the Rendering module section:

```markdown
### 已拆出的 Script Generation 模块

`video_slicer/script_generation.py` 负责配音文案相关逻辑。

核心函数：

- `voiceover_length_requirements()`
- `parse_json_response()`
- `parse_llm_json_response()`
- `forbidden_terms_from_context()`
- `validate_voiceover_doc()`
- `generate_voiceover_with_llm()`
- `review_voiceover_with_llm()`
- `humanize_voiceover_with_llm()`
- `write_humanize_diff()`
- `fallback_voiceover_script()`
- `write_voiceover_outputs()`

对应测试：

- `tests/test_script_generation.py`

后续规则：

- 新增文案策略、审稿规则、口播润色限制、禁用词校验，优先放到 `video_slicer/script_generation.py`。
- `pipeline.py` 只负责决定何时生成、审稿、润色和写出脚本，不直接拼大段 prompt。
- 第三方模型请求细节仍然放在 `llm_providers/`。
```

Mark “第四阶段：拆 Script Generation” as completed:

```markdown
### 第四阶段：拆 Script Generation

状态：已完成。
```

- [ ] **Step 4: Update development rules**

In `docs/development-rules.zh-CN.md`, change:

```markdown
| 文案生成、审稿、润色 | 现在在 `pipeline.py`，后续迁到 `video_slicer/script_generation.py` |
```

To:

```markdown
| 文案生成、审稿、润色 | `video_slicer/script_generation.py` |
```

Add `tests.test_script_generation` to the recommended unit-test command:

```powershell
python -m unittest tests.test_script_generation tests.test_rendering tests.test_alignment tests.test_pipeline tests.test_project_models tests.test_project_store tests.test_pipeline_records tests.test_quality_report
```

- [ ] **Step 5: Mark this plan execution status**

At the top of this file, after the `**Tech Stack:**` line, add:

```markdown
**Execution Status:** Implemented and verified locally.
```

- [ ] **Step 6: Run full unit tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_script_generation tests.test_rendering tests.test_alignment tests.test_pipeline tests.test_project_models tests.test_project_store tests.test_pipeline_records tests.test_quality_report
```

Expected:

```text
OK
```

- [ ] **Step 7: Run compile check**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall video_slicer tests scripts
```

Expected: command exits with code 0.

- [ ] **Step 8: Run whitespace check**

Run:

```powershell
git diff --check
```

Expected: command exits with code 0. LF/CRLF warnings are acceptable on Windows if there are no whitespace error lines.

- [ ] **Step 9: Run video-specific term scan for common code**

Run:

```powershell
rg "刘华强|封彪|征服|孙红雷|买瓜|瓜摊|西瓜|birds|bird" video_slicer llm_providers tts_providers scripts
```

Expected: exit code 1 with no matches.

- [ ] **Step 10: Confirm Git scope**

Run:

```powershell
git status --short
git ls-files outputs videos .env assets\voice_refs assets\bgm
```

Expected tracked local asset dirs only:

```text
assets/bgm/.gitkeep
assets/voice_refs/.gitkeep
videos/.gitkeep
```

- [ ] **Step 11: Commit Task 4 after confirming the changed-file scope**

Run:

```powershell
git add README.md docs/README.zh-CN.md docs/code-map.zh-CN.md docs/development-rules.zh-CN.md docs/superpowers/plans/2026-07-10-script-generation-module-refactor.md
git commit -m "docs: document script generation module split"
```

If the worktree contains unrelated local changes, skip the commit and report the exact files that should be included.

---

## Post-Plan Roadmap

After this plan is implemented and verified, continue in this order:

1. **Commit scope cleanup**
   - Group current finished refactors into clear commits before large API work.
   - Do not mix generated outputs, local videos, or `.env`.

2. **Local API design plan**
   - Create a FastAPI plan for project creation, version settings, context editing, script generation, script editing, render jobs, and job status.
   - API should call stable modules, not shell out to CLI scripts.

3. **Frontend MVP plan**
   - Build only after local API shape is stable.
   - First screen should be a creator workspace: upload/select video, edit context, set target duration, choose voice/BGM, preview script, render.

4. **Quality gate plan**
   - Decide which `quality_report.json` issues remain warnings and which become blocking errors.
   - Add batch-level reporting so matrix-style production can compare many outputs.

## Self-Review

**Spec coverage:** This plan covers the next concrete refactor in the documented sequence: split script generation from `pipeline.py`. It does not implement FastAPI or frontend work because those depend on this module boundary.

**Placeholder scan:** The plan names exact files, exact functions to move, exact tests to add, exact commands to run, and expected outputs. It avoids unspecified future work inside implementation tasks.

**Type consistency:** Public function names and signatures match the existing functions found in `video_slicer/pipeline.py`. Later tasks consume functions produced by earlier tasks through `video_slicer.script_generation`.

**Execution handoff:** Implement with `superpowers:subagent-driven-development` if available. If working inline, use `superpowers:executing-plans` and follow tasks in order.
