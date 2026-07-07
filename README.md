# 自动影视解说切片 Demo

这个仓库是一个“配音文案优先”的视频自动切片 demo。流程会先从原视频提取语音字幕，再用大模型结合人工上下文包生成影视解说文案，经过语义审查后生成 TTS 配音，最后按配音文案对应的原视频字幕时间戳剪辑画面，并移除原视频声音。

当前 demo 使用同一套已验证参数：

- 默认输入视频：`videos/input.mp4`
- 上下文模板：`context.example.json`
- 文本模型：`gpt-4.1`
- 真人口播润色模型：`qwen-plus-latest`
- TTS provider：`fish`
- Fish TTS 模型：`s2.1-pro-free`
- Fish 声音模型：通过 `.env` 里的 `FISH_REFERENCE_ID` 指定
- 目标时长：约 `120` 秒

## 项目结构

现在项目已经按“以后能接前端/后端”的方向整理：

- `1.py`：兼容旧命令的薄入口，内部转到 `video_slicer.pipeline`
- `video_slicer/pipeline.py`：完整视频切片主流程
- `video_slicer/voice_registry.py`：本地 Fish 声音 ID 注册表工具
- `tts_providers/`：TTS provider，当前有 Fish Audio 和 OCool fallback
- `scripts/run_pipeline.py`：完整流程入口
- `scripts/preview_tts.py`：单独试听 TTS，不跑完整视频
- `scripts/create_fish_voice.py`：创建 Fish 声音模型并登记到本地注册表
- `scripts/run_batch.py`：按 JSON 清单批量跑多个视频
- `batch.example.json`：批量任务模板

## 应该上传到 GitHub 的文件

建议提交这些文件，方便同学直接复用：

- `1.py`：兼容旧命令的入口
- `video_slicer/`：后端核心流程模块
- `tts_providers/`：TTS provider
- `scripts/`：可复用命令行入口
- `requirements.txt`：Python 依赖
- `README.md`：使用说明
- `.gitignore`：忽略本地密钥、输出和缓存
- `.env.example`：环境变量模板，不包含真实 key
- `context.example.json`：通用上下文包模板
- `batch.example.json`：批量任务模板
- `videos/.gitkeep`：保留空的视频目录
- `assets/voice_refs/.gitkeep`：保留声音参考目录

不要提交这些文件：

- `.env`：里面有你的 API key
- `.venv/`：本地虚拟环境
- `outputs/`：运行输出，别人可以自己生成
- `outputs_archive/`：历史输出归档
- `context.json`：本地实际上下文包，可以由模板复制出来
- `videos/*.mp4`：本地输入视频，别人可以换成自己的视频
- `assets/voice_refs/*`：本地参考音频和声音 ID 注册表
- `__pycache__/`：Python 缓存

## 环境准备

先安装 FFmpeg，并确保命令行能识别：

```powershell
ffmpeg -version
ffprobe -version
```

然后创建 Python 虚拟环境并安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 配置 API Key

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

打开 `.env`，先填 OCool key。这个 key 仍然用于文案生成、审稿和真人口播润色：

```env
OCOOL_API_KEY=put_your_ocool_api_key_here
```

如果要使用 Fish Audio 配音和声音克隆，再填：

```env
FISH_API_KEY=put_your_fish_audio_key_here
FISH_TTS_MODEL=s2.1-pro-free
FISH_REFERENCE_ID=
```

`s2.1-pro-free` 是 Fish Audio 的免费开发/测试模型。它适合 demo 和原型验证，但没有延迟和可用性保证。`FISH_REFERENCE_ID` 先留空。创建声音模型后，把 Fish 返回的 `_id` 填进去。

`.env` 已经被 `.gitignore` 忽略，不要手动把它加进 Git。

## 配置上下文包

复制 demo 上下文模板：

```powershell
Copy-Item context.example.json context.json
```

`context.json` 是本地运行时读取的上下文包。你可以在里面改视频标题、人物关系、剧情梗概、禁用词和解说风格。

其中这几个字段和复用关系最大：

- `forbidden_terms`：不允许出现在文案里的词。
- `forbidden_story_facts`：不允许模型写错的剧情方向。
- `humanize_unsafe_detail_terms`：某个视频里容易被模型脑补、但没有证据的画面细节。
- `tts_unfriendly_terms`：TTS 容易读错或听起来别扭的表达。

## 放入视频

把要处理的视频放到 `videos/` 目录。最简单的方式是命名成默认输入：

```powershell
Copy-Item 你的视频.mp4 videos/input.mp4
```

## 运行 demo

使用 Fish Audio 配音运行：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_pipeline `
  --input videos/input.mp4 `
  --context context.json `
  --target-duration 120 `
  --ocool-model gpt-4.1 `
  --ocool-humanize-model qwen-plus-latest `
  --require-llm `
  --tts-mode fish
```

旧入口仍然可用：

```powershell
.\.venv\Scripts\python.exe 1.py --input videos/input.mp4 --context context.json --target-duration 120 --tts-mode fish
```

如果想强制重新生成脚本、审稿和配音，可以加：

```powershell
--force-script --force-review --force-humanize --force-tts
```

如果只想测试“真人口播润色”后的文案，不想重新生成配音，可以用：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_pipeline `
  --input videos/input.mp4 `
  --context context.json `
  --target-duration 120 `
  --require-llm `
  --force-humanize `
  --tts-mode none
```

## 输出文件

运行后主要看这些文件：

- `outputs/final_with_voiceover.mp4`：最终带新配音的视频
- `outputs/output.mp4`：无原声的剪辑预览
- `outputs/voiceover_script.txt`：大模型生成并审查后的配音文案
- `outputs/voiceover_script.json`：配音文案、来源字幕和上下文引用
- `outputs/voiceover_humanize_diff.txt`：真人口播润色前后对比
- `outputs/voiceover.srt`：新配音字幕
- `outputs/alignment.json`：配音句子和原字幕时间戳映射
- `outputs/time_mapping.json`：最终视频时间和原视频时间映射
- `outputs/final_voiceover_transcript.json`：最终配音文案时间轴

## 复用到别的视频

换新视频时，把视频放到 `videos/` 下面，然后改命令里的 `--input`。同时复制一份新的上下文包，写清楚人物、剧情背景、禁止出现的错误剧情和解说风格。

这个 demo 暂时没有做 OCR，所以如果视频里关键信息只出现在画面文字里、字幕没有说出来，需要手动补到 `context.json` 里。

## 注意

请确认你有权处理和分享输入视频。公开视频、课程内部仓库或私有仓库的使用边界不一样，正式公开前最好再检查版权风险。


## Fish Audio 配音和声音克隆

Fish Audio 作为 TTS provider 使用。你只需要在 `.env` 填：

```env
FISH_API_KEY=put_your_fish_audio_key_here
FISH_TTS_MODEL=s2.1-pro-free
FISH_REFERENCE_ID=
```

先准备一段本地参考音频：

```text
assets/voice_refs/my_voice.mp3
```

建议参考音频 10 到 30 秒，单人说话，背景干净，没有音乐或多人重叠。

创建私有声音模型，并把声音 ID 记录到本地注册表：

```powershell
.\.venv\Scripts\python.exe -m scripts.create_fish_voice `
  --audio assets/voice_refs/my_voice.mp3 `
  --name narrator_a
```

命令会把 Fish 返回结果写到：

```text
outputs/fish_voice_model_narrator_a.json
```

同时会把声音记录到本地注册表：

```text
assets/voice_refs/fish_voice_models.local.json
```

如果你想让这个声音成为默认声音，把终端打印的 `_id` 填到 `.env`：

```env
FISH_REFERENCE_ID=返回的_id
```

如果只想试听声音，不跑完整切片流程，可以生成一段单独的 mp3：

```powershell
.\.venv\Scripts\python.exe -m scripts.preview_tts `
  --provider fish `
  --text "刘华强语气平静，但意思很清楚：机会给了，是你没接住。" `
  --output outputs/fish_preview.mp3
```

之后正式运行：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_pipeline `
  --input videos/input.mp4 `
  --context context.json `
  --target-duration 120 `
  --tts-mode fish
```

## 批量生产

复制 `batch.example.json`，为每个视频写一个 job：

```powershell
Copy-Item batch.example.json batch.local.json
```

然后运行：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_batch --manifest batch.local.json
```

每个 job 建议使用独立 `output_dir`，例如 `outputs/job_001`、`outputs/job_002`，这样批量生产时不会互相覆盖。
