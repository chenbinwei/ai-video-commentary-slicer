# better-story Demo

This is a first-pass demo pipeline for converting a short episode-length video into a narrated recap edit. It is intentionally modular: every step writes JSON or media files under `runs/<task_id>/` so failures are easy to inspect and rerun.

## What Works In This Demo

- Create an isolated task directory for a source video.
- Probe video metadata with `ffprobe`.
- Extract ASR-ready audio with `ffmpeg`.
- Transcribe audio through an API provider or a no-cost mock provider.
- Review and edit per-line character labels in a local GUI.
- Generate story beats, narration script, TTS audio, EDL, SRT subtitles, and a recap MP4.
- Choose API key input from environment, CLI flag, or interactive prompt.

## Requirements

- Python 3.10+
- `ffmpeg` and `ffprobe` on `PATH`
- API key if you use `--provider openai` or `--provider openai_compatible`

Install:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

For a no-cost dry run of the file pipeline:

```bash
better-story run-auto --video /path/to/video.mp4 --provider mock --target-duration 120
```

For the API-backed flow:

```bash
better-story settings-gui
better-story create --video /path/to/video.mp4 --target-duration 180 --provider openai_compatible
better-story prepare --task runs/<task_id>
better-story transcribe --task runs/<task_id> --provider openai_compatible
better-story review --task runs/<task_id>
```

Open the printed local URL, adjust character names, then continue:

```bash
better-story continue-demo --task runs/<task_id> --provider openai_compatible
```

You can also pass the API key directly or enter it interactively:

```bash
better-story transcribe --task runs/<task_id> --provider openai --api-key "sk-..."
better-story transcribe --task runs/<task_id> --provider openai --prompt-api-key
```

## Provider Choices

- `openai_compatible`: uses OpenAI SDK-compatible APIs, including third-party base URLs.
- `openai`: uses the official OpenAI API unless you explicitly pass a base URL.
- `mock`: generates placeholder transcript/story/TTS so you can test task files, GUI, EDL, subtitles, and rendering without API cost.

Saved API settings:

```bash
better-story settings-gui
better-story settings \
  --provider openai_compatible \
  --base-url "https://api.example.com/v1" \
  --api-key "your-key" \
  --llm-model "your-llm-model" \
  --asr-model "your-asr-model"
```

Settings are stored locally in `.better_story/settings.json`. This file is ignored by git and should not be shared.

If TTS uses a different API:

```bash
better-story settings \
  --tts-provider openai_compatible \
  --tts-base-url "https://tts-api.example.com/v1" \
  --tts-api-key "your-tts-key" \
  --tts-model "your-tts-model" \
  --tts-voice "your-voice"
```

Use `--tts-provider same` to reuse the main provider.

Default models are configurable:

```bash
better-story continue-demo \
  --task runs/<task_id> \
  --provider openai_compatible \
  --llm-model gpt-4o-mini \
  --tts-model gpt-4o-mini-tts \
  --tts-voice alloy
```

If your account does not have access to a default model, pass another model with the relevant flag.

## Cost Controls

The demo records API usage metadata in `logs/api_usage.json`. It also writes all intermediate outputs to disk, so rerunning later stages does not require repeating transcription unless you explicitly run it again.

For cheaper development:

- Use `--provider mock` until the media and GUI flow works.
- Test with a 1-2 minute clip before a 10-20 minute episode.
- Reuse the same task directory and rerun only failed downstream steps.
- Prefer lower-cost models for character suggestions and drafts.

## Main Commands

```bash
better-story create --video input.mp4
better-story prepare --task runs/task_xxx
better-story transcribe --task runs/task_xxx --provider openai
better-story review --task runs/task_xxx
better-story continue-demo --task runs/task_xxx --provider openai_compatible
better-story render --task runs/task_xxx
better-story run-auto --video input.mp4 --provider mock
```

## External TTS Workflow

If you want to use a separate TTS service manually:

```bash
better-story continue-demo --task runs/<task_id> --provider openai_compatible --skip-tts
```

Copy the exported text from:

```text
runs/<task_id>/rewrite/tts_text_for_external.txt
```

Generate narration audio externally, then import it:

```bash
better-story import-narration --task runs/<task_id> --audio /path/to/narration.mp3
better-story edl --task runs/<task_id>
better-story render --task runs/<task_id>
```

## Output

Typical task output:

```text
runs/task_YYYYMMDD_HHMMSS/
  input/source.mp4
  config.json
  analysis/media_info.json
  analysis/utterances.json
  analysis/utterances_with_characters.json
  analysis/story_beats.json
  rewrite/narration_script.json
  rewrite/aligned_script.json
  audio/source.wav
  audio/tts/*.wav
  edit/edl.json
  edit/subtitles.srt
  output/recap.mp4
```

这是一次测试