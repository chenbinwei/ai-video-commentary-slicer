from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from better_story.utils.json_io import read_json, write_json


SETTINGS_PATH = Path(".better_story") / "settings.json"


@dataclass
class ProviderSettings:
    provider: str = "openai_compatible"
    api_key: str = ""
    base_url: str = ""
    asr_model: str = "whisper-1"
    llm_model: str = "gpt-4o-mini"
    tts_provider: str = "same"
    tts_api_key: str = ""
    tts_base_url: str = ""
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "alloy"


def load_settings(path: Path = SETTINGS_PATH) -> ProviderSettings:
    if not path.exists():
        return ProviderSettings()
    data = read_json(path)
    return ProviderSettings(**{**asdict(ProviderSettings()), **data})


def save_settings(settings: ProviderSettings, path: Path = SETTINGS_PATH) -> None:
    write_json(path, asdict(settings))


def update_settings(updates: dict[str, Any], path: Path = SETTINGS_PATH) -> ProviderSettings:
    settings = load_settings(path)
    data = asdict(settings)
    data.update({key: value for key, value in updates.items() if value is not None})
    settings = ProviderSettings(**data)
    save_settings(settings, path)
    return settings
