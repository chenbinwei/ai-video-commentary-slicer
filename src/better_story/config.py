from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from better_story.utils.json_io import read_json, write_json


@dataclass
class TaskConfig:
    video_path: str
    target_duration_sec: int = 180
    source_language: str = "auto"
    narration_language: str = "zh-CN"
    output_profile: str = "landscape_16_9"
    provider: str = "openai"
    base_url: str = ""
    asr_model: str = "whisper-1"
    llm_model: str = "gpt-4o-mini"
    tts_provider: str = "same"
    tts_base_url: str = ""
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "alloy"
    asr_chunk_sec: int = 300
    copy_input: bool = False

    @classmethod
    def from_env_and_args(cls, **kwargs: Any) -> "TaskConfig":
        defaults = {
            "base_url": os.getenv("BETTER_STORY_BASE_URL", cls.base_url),
            "asr_model": os.getenv("BETTER_STORY_ASR_MODEL", cls.asr_model),
            "llm_model": os.getenv("BETTER_STORY_LLM_MODEL", cls.llm_model),
            "tts_provider": os.getenv("BETTER_STORY_TTS_PROVIDER", cls.tts_provider),
            "tts_base_url": os.getenv("BETTER_STORY_TTS_BASE_URL", cls.tts_base_url),
            "tts_model": os.getenv("BETTER_STORY_TTS_MODEL", cls.tts_model),
            "tts_voice": os.getenv("BETTER_STORY_TTS_VOICE", cls.tts_voice),
        }
        defaults.update({k: v for k, v in kwargs.items() if v is not None})
        return cls(**defaults)


def task_config_path(task_dir: Path) -> Path:
    return task_dir / "config.json"


def load_config(task_dir: Path) -> TaskConfig:
    data = read_json(task_config_path(task_dir))
    return TaskConfig(**data)


def save_config(task_dir: Path, config: TaskConfig) -> None:
    write_json(task_config_path(task_dir), asdict(config))
