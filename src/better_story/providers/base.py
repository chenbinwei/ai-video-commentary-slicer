from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class AIProvider(ABC):
    def __init__(self, *, asr_model: str, llm_model: str, tts_model: str, tts_voice: str) -> None:
        self.asr_model = asr_model
        self.llm_model = llm_model
        self.tts_model = tts_model
        self.tts_voice = tts_voice

    @abstractmethod
    def transcribe_audio(
        self,
        audio_path: Path,
        *,
        language: str,
        offset_sec: float = 0.0,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def suggest_characters(self, utterances: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def extract_story_beats(
        self,
        utterances: list[dict[str, Any]],
        *,
        target_language: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def write_narration_script(
        self,
        story_beats: list[dict[str, Any]],
        *,
        target_duration_sec: int,
        narration_language: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def synthesize_speech(
        self,
        text: str,
        output_path: Path,
        *,
        language: str,
    ) -> float:
        raise NotImplementedError
