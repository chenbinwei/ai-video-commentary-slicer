# 模块化实现路线图

## 1. 当前结论

这个项目不能一开始就按“输入一部电影，自动生成完美短视频”来做。正确路线是先做一个最小可跑通 Demo，把整条链路拆成多个可独立验证的模块。每个模块只做一件事，输出可检查的中间文件，再由后续模块消费这些文件。

第一版 Demo 的核心目标：

- 输入一个 20 分钟左右的单集视频。
- 自动提取音频、转写台词、粗略识别说话人。
- 提供一个简单 GUI，让你检查每句台词对应的角色并手动微调。
- 使用云端 AI 抽取剧情、生成剧情解说旁白脚本。
- 用普通 AI TTS 生成旁白。
- 根据脚本回链原视频时间戳，自动剪出一个短版视频。
- 输出成片、字幕、剪辑表和所有中间 JSON。

最终目标仍然是“保留大量原剧台词的精剪版”，但第一版先做“剧情解说旁白版”。这是为了验证流程可行性，先把数据链路和剪辑回链做稳。

## 2. 已确认需求

根据你的第 16 节回答，项目约束如下：

- 第一版形式：先做最简单 Demo，不追求完整产品形态。
- 语言：希望支持多语言，不限制中文普通话。
- 当前内容形态：先做剧情解说旁白版。
- 最终内容形态：保留大量原剧台词的精剪版。
- 当前视频长度：先处理 20 分钟左右番剧。
- 最终视频长度：支持两小时以上电影。
- 分发平台：多平台分发。
- AI 方式：接受云端 AI 服务，不要求本地离线。
- 成本要求：需要通过 API 使用策略降低成本。
- 批量处理：最终可支持多集，当前先做单集。
- 人工校正：需要 GUI 显示每句台词、说话人、角色，并允许人工微调。

## 3. 工程原则

### 3.1 不做黑盒流水线

每个模块必须落盘自己的输入、输出和日志。

错误必须能定位到具体阶段，例如：

- ASR 转写错误。
- speaker 分离错误。
- speaker 到角色绑定错误。
- 剧情事件抽取错误。
- 脚本生成幻觉。
- 脚本行无法回链原片段。
- 剪辑点不自然。

### 3.2 AI 只处理结构化任务

不要让 AI 直接“看完整电影然后给出剪辑时间戳”。正确做法是：

1. 程序负责媒体处理和时间戳。
2. ASR 负责语音转文字。
3. 程序把台词、speaker、场景边界整理成结构化数据。
4. AI 只在结构化数据上做剧情理解、归纳、改写和打分。
5. 程序根据 AI 输出的 `source_beat_ids` 回到原视频时间戳。

这样可以最大限度降低幻觉和错位。

### 3.3 每一步都可人工介入

第一版最重要的人工介入点是“台词到角色”的校正。

后续还要加入：

- 剧情事件校正。
- 解说脚本编辑。
- 剪辑片段替换。
- 输出平台参数调整。

### 3.4 先旁白，后原声精剪

旁白版只需要把“剧情事实”讲清楚，画面片段做辅助。

原声精剪版要求更高：

- 必须知道每句原台词的角色、时间戳和剧情作用。
- 必须保留上下文，否则原台词会断裂。
- 必须处理台词之间的音频衔接。
- 必须判断哪些台词能删、哪些台词必须保留。

因此后者应建立在前者的数据层之上。

## 4. Demo 版本定义

### 4.1 Demo 输入

```text
input_video: 本地 mp4/mkv/mov 文件
target_duration: 例如 180 秒
source_language: auto
narration_language: zh-CN 或 same_as_source
output_profile: 16:9 或 9:16
style: 剧情解说
```

### 4.2 Demo 输出

```text
output/
  recap.mp4
  recap.srt
  narration.wav
  edl.json
analysis/
  media_info.json
  transcript.json
  utterances.json
  speakers.json
  character_map.json
  story_beats.json
rewrite/
  outline.json
  narration_script.json
  qc_report.json
logs/
  run.log
  api_usage.json
```

### 4.3 Demo 验收标准

Demo 成功不等于质量完美。第一版验收标准应是：

- 能完整跑通一次从视频到成片。
- 每句旁白能追溯到原视频的一个或多个时间段。
- GUI 中能看到每句台词、时间戳、speaker、角色，并能改角色。
- 生成的视频故事大体连贯。
- 生成的视频时长接近目标时长，误差控制在 +/- 10% 以内。
- 所有 AI 输出都有 JSON 文件可检查。

## 5. 推荐技术形态

第一版建议使用：

- Python 后端 pipeline。
- ffmpeg / ffprobe 做媒体处理。
- OpenAI 或其他云端服务做 ASR、LLM、TTS。
- Streamlit 或 Gradio 做最小 GUI。
- 本地文件系统存储任务数据。
- SQLite 可选，第一版可以先不用数据库。

推荐第一版不是正式 Web 系统，也不是桌面应用，而是：

```text
Python CLI pipeline + Streamlit/Gradio 校正界面
```

原因：

- CLI 最适合快速验证流水线。
- Streamlit/Gradio 能最快做出表格校正 GUI。
- 不需要一开始设计复杂前后端。
- 后续可以把 pipeline 平滑迁移到 FastAPI + React。

## 6. 总体模块图

```text
M00 项目骨架和任务管理
  -> M01 媒体探测和音频提取
  -> M02 ASR 转写
  -> M03 说话人分离和 utterance 对齐
  -> M04 角色映射 GUI
  -> M05 场景切分
  -> M06 剧情事件抽取
  -> M07 剧情压缩和旁白脚本生成
  -> M08 脚本到原片时间戳回链
  -> M09 TTS 旁白生成
  -> M10 剪辑决策表 EDL 生成
  -> M11 ffmpeg 合成
  -> M12 质检和成本统计
```

每个模块都必须可以单独运行。例如：

```bash
python -m better_story.pipeline ingest --video input.mp4
python -m better_story.pipeline transcribe --task runs/task_001
python -m better_story.pipeline review-characters --task runs/task_001
python -m better_story.pipeline rewrite --task runs/task_001 --target-duration 180
python -m better_story.pipeline render --task runs/task_001
```

## 7. 目录结构规划

```text
better-story/
  docs/
    VIDEO_RECAP_PIPELINE_PLAN.md
    MODULAR_IMPLEMENTATION_ROADMAP.md
  src/
    better_story/
      __init__.py
      cli.py
      config.py
      models/
        media.py
        transcript.py
        story.py
        edit.py
      modules/
        m00_task.py
        m01_media.py
        m02_asr.py
        m03_diarize.py
        m04_character_review.py
        m05_scene.py
        m06_story.py
        m07_rewrite.py
        m08_align.py
        m09_tts.py
        m10_edl.py
        m11_render.py
        m12_qc.py
      providers/
        openai_client.py
        asr_provider.py
        llm_provider.py
        tts_provider.py
      utils/
        ffmpeg.py
        json_io.py
        timecode.py
        cost.py
  app/
    review_gui.py
  runs/
    task_xxx/
  tests/
```

第一版可以先不把 `docs/` 迁移出去，当前两个 Markdown 文件也可以继续放在根目录。

## 8. 数据流总览

```text
source_video
  -> media_info.json
  -> source.wav
  -> transcript_raw.json
  -> utterances.json
  -> character_map.json
  -> scenes.json
  -> story_beats.json
  -> narration_script.json
  -> aligned_script.json
  -> narration.wav
  -> edl.json
  -> recap.mp4
```

关键点：

- `utterances.json` 是所有后续模块的基础。
- `character_map.json` 是人工校正后的角色真相来源。
- `story_beats.json` 必须绑定原视频时间范围。
- `narration_script.json` 的每一句都必须引用 `source_beat_ids`。
- `edl.json` 是最终剪辑合成的唯一输入，不允许 render 阶段临时做剧情判断。

## 9. M00 项目骨架和任务管理

### 9.1 目标

建立一个任务目录，把每次处理的视频和中间产物隔离开。

### 9.2 输入

```json
{
  "video_path": "/path/to/source.mp4",
  "target_duration_sec": 180,
  "source_language": "auto",
  "narration_language": "zh-CN",
  "output_profile": "vertical_9_16"
}
```

### 9.3 输出

```text
runs/task_20260629_001/
  input/source.mp4
  config.json
  status.json
```

### 9.4 实现逻辑

1. 校验输入文件是否存在。
2. 生成 task id。
3. 创建任务目录。
4. 复制或软链接原视频。
5. 写入 `config.json`。
6. 初始化 `status.json`。

### 9.5 验证方式

- 输入不存在时明确报错。
- 同一个视频多次运行不会覆盖旧任务。
- 任务目录结构稳定。

## 10. M01 媒体探测和音频提取

### 10.1 目标

用 ffprobe 获取视频信息，用 ffmpeg 提取音频。

### 10.2 输入

```text
input/source.mp4
```

### 10.3 输出

```text
analysis/media_info.json
audio/source.wav
```

### 10.4 实现逻辑

1. 调用 `ffprobe` 获取：
   - 视频时长。
   - 分辨率。
   - 帧率。
   - 音轨数量。
   - 编码格式。
2. 调用 `ffmpeg` 提取单声道或双声道 wav。
3. 统一采样率，例如 16 kHz 或 24 kHz，取决于 ASR 服务要求。
4. 长音频要预留切片能力，因为云端 ASR 可能有文件大小限制。

### 10.5 注意事项

多语言不是这里的问题。这里不要做字幕解析、翻译或剧情判断。

### 10.6 验证方式

- `media_info.json` 能正确显示时长。
- `source.wav` 可播放。
- 音频时长与视频时长基本一致。

## 11. M02 ASR 转写

### 11.1 目标

把音频转成带时间戳的文本。

### 11.2 输入

```text
audio/source.wav
config.source_language
```

### 11.3 输出

```text
analysis/transcript_raw.json
analysis/utterances.json
```

### 11.4 实现逻辑

1. 如果音频文件超过云端接口限制，先按时间切片。
2. 对每个切片调用 ASR。
3. 合并切片结果，并把切片内时间戳转换成全局时间戳。
4. 统一输出为 `utterances.json`。

### 11.5 多语言策略

MVP 不要自己写复杂语言识别，优先依赖 ASR 服务的自动语言能力。

配置上保留：

```json
{
  "source_language": "auto",
  "detected_language": "ja",
  "transcript_language": "ja",
  "narration_language": "zh-CN"
}
```

这样未来可以支持：

- 原视频日语，中文解说。
- 原视频英语，中文解说。
- 原视频中文，中文解说。
- 原视频任意语言，同语言解说。

### 11.6 数据结构

```json
{
  "utterance_id": "utt_000123",
  "start": 125.42,
  "end": 130.18,
  "text": "你为什么要骗我？",
  "language": "zh-CN",
  "confidence": 0.91,
  "asr_chunk_id": "chunk_003"
}
```

### 11.7 验证方式

- 每条台词有 `start` 和 `end`。
- 时间戳递增。
- 没有明显重复切片内容。
- 20 分钟视频能在可接受时间内完成。

## 12. M03 说话人分离和 utterance 对齐

### 12.1 目标

给每句台词绑定 speaker，例如 `spk_00`、`spk_01`。

### 12.2 输入

```text
audio/source.wav
analysis/utterances.json
```

### 12.3 输出

```text
analysis/speakers.json
analysis/utterances_with_speakers.json
```

### 12.4 实现逻辑

1. 调用支持 diarization 的 ASR 服务，或单独调用说话人分离模型。
2. 得到 speaker 时间段。
3. 对每条 utterance 计算与 speaker 时间段的重叠比例。
4. 选择重叠比例最高的 speaker。
5. 如果重叠低于阈值，标记为 `unknown`。

### 12.5 对齐算法

```text
utterance [start, end]
speaker_segment [start, end]
overlap = max(0, min(u.end, s.end) - max(u.start, s.start))
ratio = overlap / (u.end - u.start)
```

选择 `ratio` 最大的 speaker。

### 12.6 数据结构

```json
{
  "utterance_id": "utt_000123",
  "start": 125.42,
  "end": 130.18,
  "text": "你为什么要骗我？",
  "speaker_id": "spk_02",
  "speaker_confidence": 0.82
}
```

### 12.7 验证方式

- 大多数台词有 speaker。
- speaker 数量大致合理。
- GUI 中能按 speaker 筛选台词。

## 13. M04 角色映射 GUI

### 13.1 目标

这是第一版必须优先做的人工校正模块。它解决“AI 未必百分百准确”的问题。

### 13.2 输入

```text
analysis/utterances_with_speakers.json
analysis/speakers.json
```

### 13.3 输出

```text
analysis/character_map.json
analysis/utterances_with_characters.json
```

### 13.4 GUI 最小功能

表格列：

- 序号。
- 开始时间。
- 结束时间。
- 台词文本。
- speaker id。
- AI 推测角色名。
- 人工确认角色名。
- 置信度。
- 是否锁定。

操作：

- 按 speaker 筛选。
- 批量把某个 speaker 设为某个角色。
- 单句改角色。
- 合并两个 speaker。
- 标记旁白、路人、群声、未知。
- 保存为 `character_map.json`。

### 13.5 AI 辅助角色推断

AI 可以先根据台词上下文推断：

```json
{
  "speaker_id": "spk_02",
  "suggested_character_name": "女主",
  "evidence": [
    "多次被称呼为姐姐",
    "在第 04:12 处提到自己的名字"
  ],
  "confidence": 0.68
}
```

但 GUI 保存后的人工结果优先级最高。

### 13.6 实现逻辑

1. 从 `utterances_with_speakers.json` 读取所有台词。
2. 生成 speaker 分组统计：
   - speaker 出现次数。
   - 总说话时长。
   - 前 10 条代表台词。
3. 调用 LLM 给每个 speaker 推测角色名。
4. 在 GUI 中展示。
5. 用户修改后保存。
6. 后续所有模块只读取 `utterances_with_characters.json`，不再直接相信原始 speaker。

### 13.7 验证方式

- 修改角色后文件正确保存。
- 再次打开 GUI 能恢复已修改结果。
- 后续剧情抽取使用人工确认角色。

## 14. M05 场景切分

### 14.1 目标

识别视频中的镜头或场景边界，为后续剪辑提供自然切点。

### 14.2 输入

```text
input/source.mp4
analysis/utterances_with_characters.json
```

### 14.3 输出

```text
analysis/scenes.json
```

### 14.4 实现逻辑

MVP 可以先用简单策略：

1. 使用 ffmpeg 或 PySceneDetect 检测画面变化。
2. 生成 scene start/end。
3. 把 utterance 归属到相邻 scene。

第一版不需要做复杂视觉理解。只要避免剪在突兀位置即可。

### 14.5 数据结构

```json
{
  "scene_id": "scene_0012",
  "start": 320.4,
  "end": 348.9,
  "utterance_ids": ["utt_00120", "utt_00121"],
  "characters": ["女主", "男主"]
}
```

### 14.6 验证方式

- scenes 覆盖整段视频。
- scene 时间不重叠。
- 能根据 scene 找到相关台词。

## 15. M06 剧情事件抽取

### 15.1 目标

把台词和场景整理成“剧情事件”，即 story beats。

### 15.2 输入

```text
analysis/utterances_with_characters.json
analysis/scenes.json
analysis/character_map.json
```

### 15.3 输出

```text
analysis/story_beats.json
rewrite/outline.json
```

### 15.4 实现逻辑

1. 按时间把 utterances 分块，例如每 2 到 4 分钟一块，或按场景聚合。
2. 对每块调用 LLM，抽取：
   - 发生了什么。
   - 哪些角色参与。
   - 冲突是什么。
   - 有没有关键台词。
   - 重要度。
   - 是否主线相关。
3. 再调用一次 LLM，把所有块合并成全片 story beats。
4. 每个 beat 必须保留源 utterance id 和时间范围。

### 15.5 数据结构

```json
{
  "beat_id": "beat_0012",
  "start": 620.5,
  "end": 742.3,
  "title": "女主发现男主隐瞒真相",
  "summary": "女主通过一通电话发现男主一直隐瞒事故真相。",
  "characters": ["女主", "男主"],
  "source_utterance_ids": ["utt_00480", "utt_00481"],
  "source_scene_ids": ["scene_0033", "scene_0034"],
  "importance": 0.86,
  "main_plot": true
}
```

### 15.6 重要约束

AI 不允许编造没有来源的事件。每个 beat 都必须引用原台词或原场景。

### 15.7 验证方式

- 每个 beat 有 start/end。
- 每个 beat 有 source_utterance_ids 或 source_scene_ids。
- beat 按时间顺序排列。
- 20 分钟视频通常生成 10 到 30 个 beat。

## 16. M07 剧情压缩和旁白脚本生成

### 16.1 目标

根据目标时长生成解说旁白脚本。

### 16.2 输入

```text
analysis/story_beats.json
analysis/character_map.json
config.target_duration_sec
config.narration_language
```

### 16.3 输出

```text
rewrite/narration_script.json
rewrite/script.txt
```

### 16.4 实现逻辑

1. 根据目标时长估算字数。
2. 将 story beats 按重要度分级。
3. 强制保留主线必要 beat。
4. 根据剩余时长选择可选 beat。
5. 调用 LLM 生成旁白脚本。
6. 每句脚本必须绑定 `source_beat_ids`。
7. 生成后做一次结构化校验。

### 16.5 字数估算

中文旁白可先按以下粗略规则：

```text
目标 60 秒：220 到 300 字
目标 180 秒：650 到 900 字
目标 300 秒：1100 到 1500 字
```

多语言时不要硬编码中文语速。需要配置：

```json
{
  "narration_language": "zh-CN",
  "chars_or_words_per_minute": 260
}
```

英文可按 words per minute 估算，中文按 chars per minute 估算。

### 16.6 数据结构

```json
{
  "script_id": "script_001",
  "target_duration_sec": 180,
  "language": "zh-CN",
  "lines": [
    {
      "line_id": "line_0018",
      "text": "女主终于发现，男主隐瞒的并不是感情，而是一场事故的真相。",
      "source_beat_ids": ["beat_0012"],
      "expected_duration_sec": 5.2,
      "importance": 0.9
    }
  ]
}
```

### 16.7 验证方式

- 每句 line 都有 `source_beat_ids`。
- 角色名只来自 `character_map.json`。
- 没有无法回链的剧情信息。
- 字数符合目标时长。

## 17. M08 脚本到原片时间戳回链

### 17.1 目标

把每句旁白对应到原视频片段。

### 17.2 输入

```text
rewrite/narration_script.json
analysis/story_beats.json
analysis/scenes.json
```

### 17.3 输出

```text
rewrite/aligned_script.json
```

### 17.4 实现逻辑

1. 对每句 script line 读取 `source_beat_ids`。
2. 根据 beat 找到候选 scenes。
3. 按以下规则选画面：
   - 优先使用 beat 中间有台词或冲突的片段。
   - 优先使用和当前 line 角色一致的 scene。
   - 避免太短的片段。
   - 避免连续复用同一个画面。
4. 给每个片段加缓冲，例如前后各 0.3 秒。
5. 输出 aligned line。

### 17.5 数据结构

```json
{
  "line_id": "line_0018",
  "text": "女主终于发现，男主隐瞒的并不是感情，而是一场事故的真相。",
  "source_beat_ids": ["beat_0012"],
  "candidate_ranges": [
    {
      "start": 620.5,
      "end": 646.0,
      "score": 0.88,
      "reason": "女主发现真相的关键反应"
    }
  ],
  "selected_range": {
    "start": 620.5,
    "end": 646.0
  }
}
```

### 17.6 验证方式

- 每句脚本都有 selected_range。
- selected_range 在原视频时长范围内。
- 片段总时长能覆盖旁白总时长。

## 18. M09 TTS 旁白生成

### 18.1 目标

用普通 AI TTS 生成解说旁白音频。

### 18.2 输入

```text
rewrite/narration_script.json
config.narration_language
```

### 18.3 输出

```text
audio/narration.wav
audio/narration_segments.json
```

### 18.4 实现逻辑

第一版建议整段旁白一次生成，或者按 line 分段生成后拼接。

推荐先按 line 分段生成：

- 好处是每句有独立音频时长。
- 便于对齐字幕。
- 便于替换单句。
- 便于后续做多角色配音。

### 18.5 数据结构

```json
{
  "line_id": "line_0018",
  "text": "女主终于发现，男主隐瞒的并不是感情，而是一场事故的真相。",
  "audio_path": "audio/tts/line_0018.wav",
  "duration_sec": 5.48
}
```

### 18.6 验证方式

- 每句 line 都有音频文件。
- 拼接后的旁白可播放。
- 旁白总时长接近目标时长。

## 19. M10 剪辑决策表 EDL 生成

### 19.1 目标

生成最终渲染所需的剪辑表。

### 19.2 输入

```text
rewrite/aligned_script.json
audio/narration_segments.json
analysis/scenes.json
```

### 19.3 输出

```text
edit/edl.json
edit/subtitles.srt
```

### 19.4 实现逻辑

1. 按旁白句子顺序安排 output 时间轴。
2. 为每句旁白匹配原片 selected_range。
3. 如果原片片段比旁白短：
   - 放慢一点画面。
   - 扩展到同一 scene 的上下文。
   - 或补充相邻 reaction shot。
4. 如果原片片段比旁白长：
   - 裁剪到关键信息段。
5. 生成字幕时间轴。
6. 生成原片音量 ducking 策略。

### 19.5 数据结构

```json
{
  "clips": [
    {
      "clip_id": "clip_0007",
      "source_start": 620.5,
      "source_end": 646.0,
      "output_start": 48.0,
      "output_end": 73.5,
      "script_line_ids": ["line_0018"],
      "narration_audio": "audio/tts/line_0018.wav",
      "source_audio_gain": 0.18,
      "narration_gain": 1.0
    }
  ]
}
```

### 19.6 验证方式

- clips 按 output_start 递增。
- clips 不引用不存在的音频或时间范围。
- 字幕时间和旁白音频一致。

## 20. M11 ffmpeg 合成

### 20.1 目标

根据 EDL 生成最终视频。

### 20.2 输入

```text
input/source.mp4
edit/edl.json
edit/subtitles.srt
audio/narration.wav 或 audio/tts/*.wav
```

### 20.3 输出

```text
output/recap.mp4
```

### 20.4 实现逻辑

1. 按 EDL 截取视频片段。
2. 拼接片段。
3. 混入旁白音频。
4. 降低原视频音量。
5. 生成字幕。
6. 根据输出平台做画幅处理。

### 20.5 输出画幅

第一版支持两个 profile：

```json
{
  "landscape_16_9": {
    "width": 1920,
    "height": 1080
  },
  "vertical_9_16_blur_bg": {
    "width": 1080,
    "height": 1920,
    "background": "blurred_source",
    "foreground": "fit_width"
  }
}
```

多平台分发先不要做复杂平台 API 上传，只做多种导出规格。

### 20.6 验证方式

- 成片可播放。
- 音画基本同步。
- 字幕不越界。
- 时长接近目标时长。

## 21. M12 质检和成本统计

### 21.1 目标

在每次任务完成后输出质量检查和 API 成本统计。

### 21.2 输入

```text
所有中间 JSON
API 调用日志
output/recap.mp4
```

### 21.3 输出

```text
rewrite/qc_report.json
logs/api_usage.json
```

### 21.4 质检项

- 是否所有 script line 都有 source beat。
- 是否所有 source beat 都能回到原视频时间。
- 是否有角色名不在角色表中。
- 是否有空文本或超长字幕。
- 是否成片时长超出目标范围。
- 是否有 API 调用失败后未重试。

### 21.5 成本统计项

```json
{
  "asr": {
    "provider": "openai",
    "model": "gpt-4o-mini-transcribe",
    "audio_minutes": 20.4,
    "estimated_cost_usd": null
  },
  "llm": {
    "requests": 8,
    "input_tokens": 62000,
    "output_tokens": 9000,
    "cached_input_tokens": 30000
  },
  "tts": {
    "characters": 820,
    "segments": 42
  }
}
```

第一版可以先记录用量，不强行计算精确费用。价格会变化，精确金额应在运行时根据当前定价配置表计算。

## 22. API 使用和成本控制

### 22.1 API 分层

建议把云端 AI 封装成 provider，不要在业务模块里直接写具体 SDK 调用。

```text
ASRProvider
  transcribe(audio_path, language) -> transcript

LLMProvider
  extract_story_beats(utterances, characters) -> story_beats
  write_narration(beats, target_duration) -> script
  quality_check(inputs, outputs) -> qc_report

TTSProvider
  synthesize(text, voice, language) -> audio_path
```

这样未来可以替换不同供应商，或者针对不同任务换模型。

### 22.2 推荐 API 策略

基于 OpenAI 官方文档，文本和结构化生成建议优先围绕 Responses API 设计。Responses API 支持文本输入输出、结构化 JSON 输出、工具调用、会话状态等能力，适合作为剧情抽取和脚本生成的统一接口。

ASR 阶段可以用 Speech-to-text。官方文档显示文件转写支持多种音频格式，并且有支持 diarized JSON 的模型路径。需要注意文件大小限制，长视频必须做音频切片。

TTS 阶段可以用 Text-to-speech。第一版使用内置声音，不做声音克隆。声音克隆涉及授权和资格限制，后续再考虑。

### 22.3 成本控制原则

成本主要来自：

- 音频转写。
- LLM 剧情抽取和改写。
- TTS 生成。
- 重复调试时的无效调用。

第一版就要加入成本控制，否则调试视频会很快浪费预算。

### 22.4 具体省钱做法

1. 缓存所有 AI 输出。

同一个输入文件、同一个 prompt 版本、同一个模型参数，不要重复调用 API。

```text
cache_key = hash(model + prompt_version + input_json + parameters)
```

2. 分层使用模型。

低风险任务用便宜模型：

- 文本清洗。
- 台词分块摘要。
- speaker 角色初步猜测。
- 字幕格式转换。

高风险任务用更强模型：

- 全片剧情主线抽取。
- 压缩脚本生成。
- 幻觉和因果检查。

3. 控制输入 token。

不要把全量 transcript 每次都塞给模型。应先做分块摘要，再把摘要和必要证据传给后续阶段。

4. 使用结构化输出。

让模型直接输出 JSON schema，减少返工、解析失败和二次调用。

5. 稳定 prompt 前缀。

把固定系统指令、schema 和例子放在 prompt 开头，把每集变化的数据放在后面。官方 prompt caching 对重复前缀有优化价值，因此 prompt 结构要从一开始就保持稳定。

6. 使用 Batch 或异步低优先级处理。

如果后续做批量多集，剧情抽取、字幕清洗、质检这类不需要实时结果的任务，可以考虑 Batch。官方文档说明 Batch 适合不需要立即响应的批处理任务，并有更低成本。Flex processing 也适合低优先级异步任务，但要接受更慢和偶发不可用。

7. 给每个模块设置预算。

例如：

```json
{
  "max_llm_requests": 20,
  "max_input_tokens": 150000,
  "max_output_tokens": 30000,
  "max_tts_characters": 3000
}
```

超过预算时停止并提示，而不是继续烧钱。

8. 调试时使用短片段。

开发阶段先用 2 到 5 分钟片段，不要每次跑完整 20 分钟。

## 23. 结构化输出策略

AI 输出都必须走 schema。

例如 story beats：

```json
{
  "type": "object",
  "required": ["beats"],
  "properties": {
    "beats": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "beat_id",
          "title",
          "summary",
          "characters",
          "source_utterance_ids",
          "importance"
        ],
        "properties": {
          "beat_id": {"type": "string"},
          "title": {"type": "string"},
          "summary": {"type": "string"},
          "characters": {
            "type": "array",
            "items": {"type": "string"}
          },
          "source_utterance_ids": {
            "type": "array",
            "items": {"type": "string"}
          },
          "importance": {
            "type": "number",
            "minimum": 0,
            "maximum": 1
          }
        }
      }
    }
  }
}
```

实现时建议用 Pydantic 定义数据模型，然后从同一个模型生成 JSON schema。这样 Python 类型、AI 输出 schema 和本地文件结构不会分裂。

## 24. GUI 规划

### 24.1 第一版 GUI

第一版只做一个 review GUI，不做完整产品后台。

页面：

- 任务选择。
- 视频基本信息。
- 台词表。
- speaker 汇总。
- 角色映射编辑。
- 保存按钮。

### 24.2 第二版 GUI

增加：

- story beats 列表。
- 每个 beat 的原视频时间段预览。
- 旁白脚本编辑。
- 每句脚本对应片段预览。
- 重新生成按钮。

### 24.3 第三版 GUI

增加：

- 时间线剪辑视图。
- 多平台导出设置。
- 多集项目管理。
- 人物关系跨集记忆。

## 25. 从旁白版走向原声精剪版

你的最终追求是保留大量原剧台词的精剪版。要达到这个目标，需要在旁白版基础上增加以下模块。

### 25.1 台词重要度评分

给每句原台词打分：

- 是否推动剧情。
- 是否体现角色动机。
- 是否是名场面。
- 是否解释关键设定。
- 是否能独立理解。
- 是否需要前后文支撑。

### 25.2 原声片段组合

从 script line 变成 dialogue segment：

```json
{
  "dialogue_segment_id": "dlg_0012",
  "utterance_ids": ["utt_0101", "utt_0102", "utt_0103"],
  "reason": "保留女主质问男主的关键冲突",
  "required_context": ["beat_0012"],
  "can_trim_silence": true
}
```

### 25.3 音频衔接

原声精剪要处理：

- BGM 突然断裂。
- 台词尾音被切断。
- 环境音不连续。
- 角色情绪跳跃。

因此要加入：

- 静音检测。
- 音频淡入淡出。
- room tone 或背景音铺底。
- 原声和旁白混合策略。

### 25.4 旁白和原声混合

最终形态不一定是纯原声，也可以是：

```text
旁白交代背景 -> 保留关键原台词 -> 旁白过渡 -> 保留冲突台词 -> 旁白总结
```

这比纯保留原台词更适合短视频平台，也更容易保证观众理解。

## 26. 分平台输出规划

第一版只做导出 profile，不做自动发布。

建议预设：

```json
{
  "douyin_tiktok": {
    "aspect": "9:16",
    "resolution": "1080x1920",
    "subtitle_safe_area": "center_lower"
  },
  "bilibili": {
    "aspect": "16:9",
    "resolution": "1920x1080",
    "subtitle_safe_area": "bottom"
  },
  "youtube_shorts": {
    "aspect": "9:16",
    "resolution": "1080x1920",
    "subtitle_safe_area": "center_lower"
  },
  "xiaohongshu": {
    "aspect": "9:16",
    "resolution": "1080x1920",
    "subtitle_safe_area": "center_lower"
  }
}
```

后续可增加：

- 标题生成。
- 简介生成。
- 标签生成。
- 封面图生成。
- 多版本 A/B 脚本。

## 27. 多语言规划

### 27.1 第一版

支持 source language auto，旁白语言可配置。

流程：

1. ASR 识别原语言。
2. 剧情抽取用原文台词。
3. 如果旁白语言不同，LLM 在生成脚本时翻译和改写。
4. TTS 使用目标旁白语言。

### 27.2 注意事项

不要把中文特有规则写死在核心逻辑里。

需要避免：

- 只按中文句号切句。
- 只按中文字数估算时长。
- 只支持中文角色称呼。
- 只支持中文 TTS voice。

### 27.3 未来增强

- 多语字幕。
- 原语言字幕 + 目标语言旁白。
- 保留原声台词时自动生成翻译字幕。

## 28. 开发顺序

### 28.1 第一个可运行版本

先完成：

1. M00 任务目录。
2. M01 音频提取。
3. M02 ASR 转写。
4. M03 speaker 标注。
5. M04 角色校正 GUI。

这一步还不需要生成视频。目标是确认“台词、时间戳、角色校正”这条基础数据链成立。

### 28.2 第二个可运行版本

继续完成：

6. M05 场景切分。
7. M06 story beats。
8. M07 旁白脚本。
9. M08 回链。

这一步目标是确认“剧情脚本能回到原视频时间戳”。

### 28.3 第三个可运行版本

继续完成：

10. M09 TTS。
11. M10 EDL。
12. M11 ffmpeg render。
13. M12 质检和成本统计。

这一步目标是生成第一条可播放 recap。

### 28.4 第四个版本

提升可用性：

- GUI 增加脚本编辑。
- GUI 增加片段预览。
- 支持竖屏输出。
- 支持重跑单个模块。
- 支持缓存和 API 预算。

## 29. 测试策略

### 29.1 单元测试

优先测试纯逻辑：

- 时间戳 overlap。
- 字幕生成。
- EDL 排序。
- JSON schema 校验。
- token/成本统计。

### 29.2 集成测试

准备一个 1 到 2 分钟的测试视频，固定期望输出：

- transcript 不为空。
- utterance 时间递增。
- story beat 至少一个。
- narration script 每句有 source beat。
- edl 可被 render 消费。

### 29.3 人工验收

每次跑完整 20 分钟样片时检查：

- 角色是否错乱。
- 剧情是否断裂。
- 旁白是否编造。
- 画面是否和旁白相关。
- 成片节奏是否能看完。

## 30. 风险优先级

### 30.1 最高风险

- ASR 时间戳不准。
- speaker 到角色绑定错误。
- AI 改写时添加原片没有的事实。
- 脚本无法准确回链原片。

### 30.2 中等风险

- 画面切换突兀。
- 旁白语速和视频时长不匹配。
- 多语言翻译导致人物关系错乱。
- 竖屏裁剪挡住关键信息。

### 30.3 后期风险

- 两小时电影上下文过长。
- 多集角色记忆冲突。
- 原声精剪的音频衔接复杂。
- 声音克隆合规和授权问题。

## 31. 不建议第一版做的事

第一版不要做：

- 声音克隆。
- 自动上传平台。
- 全自动多集处理。
- 两小时电影。
- 复杂前端工程。
- 复杂视觉理解。
- 逐字级口型匹配。
- 原声精剪。

这些都不是不重要，而是会拖垮 Demo 验证。

## 32. 官方资料参考

以下资料用于 API 规划和成本控制，后续真正实现前应再次确认最新接口和价格：

- OpenAI Responses API: https://platform.openai.com/docs/api-reference/responses
- OpenAI Structured Outputs: https://platform.openai.com/docs/guides/structured-outputs
- OpenAI Speech-to-text: https://platform.openai.com/docs/guides/speech-to-text
- OpenAI Text-to-speech: https://platform.openai.com/docs/guides/text-to-speech
- OpenAI Cost optimization: https://developers.openai.com/api/docs/guides/cost-optimization
- OpenAI Batch API: https://developers.openai.com/api/docs/guides/batch
- OpenAI Flex processing: https://developers.openai.com/api/docs/guides/flex-processing
- OpenAI Prompt caching: https://developers.openai.com/api/docs/guides/prompt-caching

## 33. 下一步建议

下一步不要立刻写完整软件，而是先实现第一组基础模块：

```text
M00 任务目录
M01 音频提取
M02 ASR 转写
M03 speaker 标注
M04 角色校正 GUI
```

这五个模块完成后，项目就有了最关键的数据底座。只要台词、时间戳、speaker、角色映射这部分跑稳，后面的剧情抽取、脚本改写、时间戳回链和剪辑合成才有可靠基础。
