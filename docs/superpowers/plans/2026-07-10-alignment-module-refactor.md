# Alignment 模块拆分实施计划

日期：2026-07-10

状态：第一阶段已执行，质量修复基础版进行中

## 目标

把文案到原视频字幕/画面的匹配逻辑从 `video_slicer/pipeline.py` 中拆出来，形成独立的 `video_slicer/alignment.py` 模块，并用测试保护当前行为。

拆分完成后，再逐步修复当前输出质量问题：

- 画面时间线倒跳。
- 相邻画面大量重叠。
- `source_segment_ids` 过度信任大模型。
- source evidence 跨度过长导致画面取错。
- 评论/收束句硬绑定到原字幕证据。

## 原则

第一阶段只拆分，不改变行为。

第二阶段再修质量。

这样可以避免同时做“移动代码”和“改算法”，否则出了问题很难定位。

## 当前相关函数

当前都在 `video_slicer/pipeline.py`：

- `simple_text_score()`
- `align_voiceover_to_transcript()`
- `build_clips_from_alignment()`
- `limit_alignment_to_target_duration()`

这些函数直接影响：

- `outputs/alignment.json`
- `outputs/selected_clips.json`
- `outputs/time_mapping.json`
- 最终剪辑画面顺序
- `outputs/quality_report.json`

## 第一阶段：无行为变化拆分

执行状态：已完成。

### 新增文件

- `video_slicer/alignment.py`
- `tests/test_alignment.py`

### 移动函数

从 `pipeline.py` 移动到 `alignment.py`：

- `simple_text_score()`
- `align_voiceover_to_transcript()`
- `build_clips_from_alignment()`
- `limit_alignment_to_target_duration()`

### `pipeline.py` 修改

在 `pipeline.py` 顶部改为导入：

```python
from video_slicer.alignment import (
    align_voiceover_to_transcript,
    build_clips_from_alignment,
    limit_alignment_to_target_duration,
)
```

如果 `simple_text_score()` 只在 `alignment.py` 内部使用，就不要再从 `pipeline.py` 暴露。

### 测试要求

`tests/test_alignment.py` 至少覆盖：

1. 有 `source_segment_ids` 时能按指定字幕段对齐。
2. 没有 `source_segment_ids` 时能走文本相似度 fallback。
3. `limit_alignment_to_target_duration()` 能截断超过目标时长的句子。
4. `build_clips_from_alignment()` 能生成合法 clip。
5. 生成 clip 时不会越过视频边界。
6. 行为迁移前后字段名保持兼容：
   - `sentence_id`
   - `text`
   - `source_segment_ids`
   - `source_start`
   - `source_end`
   - `source_text`
   - `match_score`
   - `voiceover_start`
   - `voiceover_end`
   - `voiceover_duration`

### 验证命令

```powershell
python -m unittest tests.test_alignment tests.test_quality_report tests.test_pipeline_records
python -m compileall video_slicer tests
```

### 验收标准

- 旧 pipeline 命令仍然可跑。
- `pipeline.py` 行数减少。
- `alignment.py` 有清晰单元测试。
- `quality_report.py` 不需要改调用方式。
- 现有测试全部通过。

执行结果：

- 新增 `video_slicer/alignment.py`。
- 新增 `tests/test_alignment.py`。
- `pipeline.py` 改为导入 alignment 相关函数。
- 已运行 `python -m unittest tests.test_alignment tests.test_quality_report tests.test_pipeline_records tests.test_project_models tests.test_project_store`。
- 已运行 `python -m compileall video_slicer tests`。

## 第二阶段：增加对齐质量评分

执行状态：已完成第一项，后续继续使用分数修复画面选择。

### 问题

当前如果 LLM 返回 `source_segment_ids`，程序直接把 `match_score` 设为 `1.0`。这会让报告和后续逻辑误以为匹配一定可靠。

### 修改方向

新增内部函数：

```python
score_source_evidence(text, source_text) -> float
```

即使有 `source_segment_ids`，也要计算文本/语义证据分数。

第一版可以先用轻量字符重合度，不调用大模型。

已执行：

- 新增 `score_source_evidence()`。
- 新增 `evidence_warning_for_score()`。
- `source_segment_ids` 来自大模型时，仍然计算真实 `match_score`。
- alignment row 新增 `source_id_trust`。
- alignment row 新增 `evidence_warning`。
- `quality_report.json` 新增 `llm_source_ids_low_evidence_score` warning。

### 输出字段建议

alignment row 增加：

- `match_score`：实际计算分数。
- `source_id_trust`：`llm_provided` 或 `fallback_matched`。
- `evidence_warning`：可选说明。

### 测试要求

- LLM 指定字幕但文本完全无关时，`match_score` 不能是 `1.0`。
- fallback 匹配时保留当前行为。

执行结果：

- 新增/更新 `tests/test_alignment.py`。
- 更新 `tests/test_quality_report.py`。

## 第三阶段：顺序截取，减少画面倒跳和大重叠

### 问题

旧输出中出现：

- `source_timeline_backtrack`
- `source_timeline_major_overlap`

这会导致观众看到画面来回跳。

### 修改方向

MVP 不做 hook/高能片段前置，也不做结尾高光复用。第一版策略只保证稳定：

1. alignment row 和最终 clip 固定写入 `source_order_policy=monotonic`。
2. 如果 LLM 返回的 `source_segment_ids` 指向当前 cursor 之前的字幕，替换成从当前 cursor 往后的 ordered fallback。
3. 如果 LLM 返回的 `source_segment_ids` 文本证据分过低，先从当前 cursor 往后寻找 ordered fallback。
4. 只有当 ordered fallback 的证据分达到阈值时，才替换成 `source_id_trust=llm_replaced_by_ordered_fallback`，并保留 `original_source_segment_ids`。
5. 如果低证据行找不到更强 fallback，则保留原始位置，但降级为 `source_id_trust=continuity_visual_support`，表示这里只作为顺序画面支撑，不再视为可信字幕语义证据。
6. `build_clips_from_alignment()` 对最终 clip 的 `source_start` 做单调保护，避免居中取画面时重新倒跳。
7. `build_clips_from_alignment()` 对相邻 clip 做基础重叠约束：在有足够视频空间时，后续 clip 向后平移，目标是相邻重叠不超过 2 秒。
8. `quality_report.json` 记录 `llm_source_ids_replaced_by_ordered_fallback` warning、`continuity_visual_support_low_evidence` info、`source_order_repair_count`、`continuity_visual_support_count`、`source_major_overlap_count` 和 `source_major_overlap_max` 指标。
9. `build_clips_from_alignment()` 从后往前计算每个 clip 的最晚开始时间，避免多个证据点集中在原视频结尾时，最后几段被压成极短片段。

### 测试要求

- 常规剧情段不会倒跳。
- LLM 指向更早字幕时会被顺序 fallback 替换。
- LLM 指向低证据字幕时，只有找到更强 ordered fallback 才替换；否则降级为连续画面支撑。
- 最终 clip 的 `source_start` 不会因为配音时长居中而倒退。
- 如果后续视频空间足够，相邻 clip 的重叠不超过 2 秒。
- 如果视频空间不够，仍保留 `source_timeline_major_overlap` warning，供后续人工或更高级策略处理。

执行结果：

- 新增 `find_best_ordered_match()`。
- 新增 `minimum_timeline_span_for_durations()`。
- 新增 `latest_start_bounds_for_durations()`。
- `align_voiceover_to_transcript()` 已按单调顺序策略校验 LLM ids。
- `alignment.json` 新增 `source_order_policy`，必要时新增 `original_source_segment_ids`。
- `selected_clips.json` 的 clip 新增 `source_order_policy`，并保持 `source_start` 单调不倒退。
- `selected_clips.json` 的 clip 新增 `visual_selection_reason`，说明画面窗口是否被平移以减少重叠。
- `quality_report.json` 新增 `llm_source_ids_replaced_by_ordered_fallback`、`continuity_visual_support_low_evidence`、`source_order_repair_count`、`continuity_visual_support_count`、`source_major_overlap_count` 和 `source_major_overlap_max`。
- 低成本真实视频验证结果：目标 120 秒时，`actual_visual_duration=120.002`，`actual_voiceover_duration=120.002`，`source_backtrack_count=0`，`source_major_overlap_count=0`。

## 第四阶段：处理 source evidence 跨度过长

执行状态：基础版已完成。

### 问题

如果一个 source span 很长，例如几十秒，但配音只有四秒，当前逻辑会按中心取画面，可能错过真正关键瞬间。

### 修改方向

新增函数：

```python
choose_visual_window_for_row(row, desired_duration, video_duration, padding)
```

策略：

1. 如果 source span 小于等于目标画面时长，按当前逻辑。
2. 如果 source span 太长，基础版按 `story_role` 选择锚点：
   - `hook`、`setup` 靠近 source span 开头。
   - `escalation`、`turning_point`、`payoff` 靠近 source span 结尾。
   - 其他角色暂时继续居中。
3. 将选择原因写入 clip：
   - `visual_selection_reason`
   - `source_span`

### 测试要求

- 超长 source span 不再简单取正中间。
- `setup` 更靠近 source span 开头。
- `turning_point`/`payoff` 更靠近 source span 结尾。

执行结果：

- 新增 `choose_visual_window_for_row()`。
- `build_clips_from_alignment()` 先选择单句画面窗口，再执行全局顺序排程。
- 新增 `anchored_to_source_span_start` 和 `anchored_to_source_span_end` 选择原因。
- 新增对应单元测试。

## 第五阶段：区分剧情句和评论句

执行状态：基础版已开始。当前不新增复杂 schema，先通过 `continuity_visual_support` 把低文本重合但仍需要画面支撑的句子，从“可信字幕语义证据”里区分出来。

### 问题

类似“孙红雷的表演把狠稳霸展现得淋漓尽致”这种评论句，不一定能和原字幕文本重合，但仍需要画面支撑。

### 修改方向

根据 `story_role` 或新增字段区分：

- `narrative_evidence`：剧情推进句，需要强证据。
- `commentary_wrap`：评论/收束句，可使用邻近高光画面。

第一版可以不让 LLM 新增复杂 schema，只在 alignment 中根据 `story_role` 做保守判断。

### 测试要求

- payoff/commentary 句低文本重合时不一定判为严重问题。
- 但仍要有可用画面来源。

## 不在本计划内

- 关键原声模式。
- 多语言字幕。
- 竖屏 9:16 渲染。
- FastAPI。
- 前端。
- 云端任务队列。

这些都等 alignment 基础稳定后再做。

## 执行建议

优先执行第一阶段。

第一阶段完成后，不要马上提交复杂算法修复。先跑一次现有 demo，观察新的 `quality_report.json`，确认拆分没有改变输出，再进入第二阶段。

推荐提交拆分时的 commit 信息：

```text
refactor: extract alignment helpers from pipeline
```

推荐提交质量修复时的 commit 信息：

```text
fix: validate source evidence scores in alignment
fix: reduce visual timeline backtracking
```

## 自检

这份计划符合当前开发规则：

- 先拆模块，再改算法。
- 新核心模块有对应测试。
- 代码地图需要在拆分执行时更新。
- 不继续把匹配逻辑堆进 `pipeline.py`。
- 修复质量问题前先通过 `quality_report.json` 定位风险。
