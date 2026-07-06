from __future__ import annotations

from better_story.providers.base import AIProvider
from better_story.providers.mock_provider import MockProvider
from better_story.providers.openai_provider import OpenAIProvider


def make_provider(
    name: str,
    *,
    api_key: str | None,
    base_url: str | None = None,
    asr_model: str,
    llm_model: str,
    tts_model: str,
    tts_voice: str,
) -> AIProvider:
    if name == "mock":
        return MockProvider(
            asr_model=asr_model,
            llm_model=llm_model,
            tts_model=tts_model,
            tts_voice=tts_voice,
        )
    if name in {"openai", "openai_compatible"}:
        return OpenAIProvider(
            api_key=api_key,
            base_url=base_url,
            asr_model=asr_model,
            llm_model=llm_model,
            tts_model=tts_model,
            tts_voice=tts_voice,
        )
    raise ValueError(f"Unsupported provider: {name}")
