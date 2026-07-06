# Demo 使用说明

## 1. 安装

```bash
cd /Users/acaja/Desktop/better-story
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

如果暂时不想安装，也可以用：

```bash
PYTHONPATH=src python3 -m better_story.cli --help
```

## 2. API 选择方式

当前 Demo 支持三个 provider：

- `openai_compatible`：调用兼容 OpenAI SDK 的 API，适合 PinAI 或其他第三方 API。
- `openai`：官方 OpenAI API 快捷方式。
- `mock`：不调用 API，用占位转写、占位剧情和静音 TTS 测试完整文件流。

### 2.1 页面保存 API 信息

```bash
better-story settings-gui
```

打开终端里显示的本地地址，例如：

```text
http://127.0.0.1:8764
```

填写：

- Provider：第三方兼容 API 选 `openai_compatible`。
- API Key：你的第三方 API key。
- Base URL：第三方 API 地址，例如 `https://api.example.com/v1`。
- ASR/LLM/TTS Model：按第三方平台提供的模型名填写。

保存后会写入：

```text
.better_story/settings.json
```

这个文件是本地明文保存，已经加入 `.gitignore`，不要分享。

### 2.2 命令行保存 API 信息

```bash
better-story settings \
  --provider openai_compatible \
  --base-url "https://api.example.com/v1" \
  --api-key "your-key" \
  --llm-model "your-llm-model" \
  --asr-model "your-asr-model" \
  --tts-model "your-tts-model"
```

如果文字转语音走另一个 API，可以继续保存：

```bash
better-story settings \
  --tts-provider openai_compatible \
  --tts-base-url "https://tts-api.example.com/v1" \
  --tts-api-key "your-tts-key" \
  --tts-model "your-tts-model" \
  --tts-voice "your-voice"
```

如果配音 API 和主 API 是同一个，保持 `--tts-provider same` 即可。

### 2.3 临时输入 API key

API key 也仍然可以临时输入：

```bash
export OPENAI_API_KEY="sk-..."
```

或：

```bash
better-story transcribe --task runs/<task_id> --provider openai --api-key "sk-..."
```

或：

```bash
better-story transcribe --task runs/<task_id> --provider openai --prompt-api-key
```

模型也可以手动选择：

```bash
better-story continue-demo \
  --task runs/<task_id> \
  --provider openai \
  --llm-model gpt-4o-mini \
  --asr-model whisper-1 \
  --tts-model gpt-4o-mini-tts \
  --tts-voice alloy
```

如果某个模型你的账号不可用，就换成你账号可用的模型。

## 3. 不花钱先测试流程

```bash
better-story run-auto \
  --video /path/to/your-video.mp4 \
  --provider mock \
  --target-duration 120
```

这个命令会生成占位成片，用来确认：

- ffmpeg 可用。
- 任务目录能创建。
- JSON 中间文件能生成。
- EDL 和字幕能生成。
- 最终 mp4 能渲染。

## 4. 真实 API 测试推荐流程

先创建任务：

```bash
better-story create \
  --video /path/to/your-video.mp4 \
  --provider openai_compatible \
  --target-duration 180 \
  --source-language auto \
  --narration-language zh-CN \
  --output-profile landscape_16_9
```

命令会输出类似：

```text
runs/task_20260629_170505
```

然后提取音频：

```bash
better-story prepare --task runs/<task_id>
```

转写并生成角色建议：

```bash
better-story transcribe \
  --task runs/<task_id> \
  --provider openai_compatible \
  --suggest-characters
```

打开角色校正 GUI：

```bash
better-story review --task runs/<task_id>
```

打开终端打印的地址，例如：

```text
http://127.0.0.1:8765
```

在页面中校正每句台词对应的角色，点击保存。保存后回到终端按 `Ctrl+C` 结束 GUI 服务。

继续生成剧情、旁白、TTS、EDL 和成片：

```bash
better-story continue-demo \
  --task runs/<task_id> \
  --provider openai_compatible
```

最终视频在：

```text
runs/<task_id>/output/recap.mp4
```

字幕在：

```text
runs/<task_id>/edit/subtitles.srt
```

## 5. 竖屏输出

创建任务时选择：

```bash
--output-profile vertical_9_16_blur_bg
```

第一版竖屏策略是模糊背景加中间原画，不做智能人脸追踪。

## 6. 当前 Demo 的限制

- 还没有真正稳定的说话人分离。当前 ASR 后默认是 `spk_00`，角色主要依赖 AI 文本推测和你的人工校正。
- 旁白版已经接通，原声精剪版还没做。
- OpenAI 模型可用性取决于你的账号权限。
- 真实 API 成本取决于视频长度、转写模型、LLM 模型和 TTS 字数。
- 第一版建议先用 1 到 2 分钟片段测试，再跑 10 分钟视频。

## 7. 外部 TTS 手动流程

如果你不想让系统直接调用 TTS API，可以先生成脚本文本，然后复制到外部 TTS 工具。

运行到脚本阶段并停止在 TTS 前：

```bash
better-story continue-demo \
  --task runs/<task_id> \
  --provider openai_compatible \
  --skip-tts
```

系统会导出：

```text
runs/<task_id>/rewrite/tts_text_for_external.txt
runs/<task_id>/rewrite/tts_lines_for_external.tsv
```

你可以把 `tts_text_for_external.txt` 的内容复制到外部 TTS 工具，生成一条完整旁白音频，例如 `narration.mp3`。

然后导入音频并继续：

```bash
better-story import-narration \
  --task runs/<task_id> \
  --audio /path/to/narration.mp3

better-story edl --task runs/<task_id>
better-story render --task runs/<task_id>
better-story qc --task runs/<task_id>
```

如果你已经有外部音频，也可以在继续流程时直接传入：

```bash
better-story continue-demo \
  --task runs/<task_id> \
  --provider openai_compatible \
  --external-narration /path/to/narration.mp3
```

## 8. 本次自测结果

我已用 `mock` provider 跑通过一次端到端流程：

```text
runs/task_20260629_170505/output/recap.mp4
```

同时验证了角色校正 GUI 能返回 HTML 页面。
