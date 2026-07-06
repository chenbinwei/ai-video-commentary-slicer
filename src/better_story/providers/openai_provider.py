from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from better_story.providers.base import AIProvider
from better_story.utils.audio import estimate_tts_duration, wav_duration


class OpenAIProvider(AIProvider):
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str | None = None,
        asr_model: str,
        llm_model: str,
        tts_model: str,
        tts_voice: str,
    ) -> None:
        super().__init__(
            asr_model=asr_model,
            llm_model=llm_model,
            tts_model=tts_model,
            tts_voice=tts_voice,
        )
        if not api_key:
            raise RuntimeError(
                "OpenAI provider requires an API key. Set OPENAI_API_KEY, pass --api-key, "
                "or use --prompt-api-key."
            )
        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:
            raise RuntimeError("Missing dependency: run `pip install -e .` first.") from exc
        client_kwargs: dict[str, str] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)

    def transcribe_audio(
        self,
        audio_path: Path,
        *,
        language: str,
        offset_sec: float = 0.0,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "model": self.asr_model,
            "file": audio_path.open("rb"),
            "response_format": "verbose_json",
        }
        if language != "auto":
            kwargs["language"] = language
        try:
            kwargs["timestamp_granularities"] = ["segment"]
            result = self.client.audio.transcriptions.create(**kwargs)
        except Exception:
            kwargs.pop("timestamp_granularities", None)
            kwargs["file"].close()
            kwargs["file"] = audio_path.open("rb")
            result = self.client.audio.transcriptions.create(**kwargs)
        finally:
            try:
                kwargs["file"].close()
            except Exception:
                pass

        data = _model_to_dict(result)
        segments = data.get("segments") or []
        utterances: list[dict[str, Any]] = []
        if segments:
            for segment in segments:
                text = str(segment.get("text", "")).strip()
                if not text:
                    continue
                utterances.append(
                    {
                        "start": round(offset_sec + float(segment.get("start", 0.0)), 3),
                        "end": round(offset_sec + float(segment.get("end", 0.0)), 3),
                        "text": text,
                        "language": data.get("language") or language,
                        "confidence": segment.get("avg_logprob"),
                        "source": "openai",
                    }
                )
        else:
            text = str(data.get("text", "")).strip()
            if text:
                utterances.append(
                    {
                        "start": round(offset_sec, 3),
                        "end": round(offset_sec + wav_duration(audio_path), 3),
                        "text": text,
                        "language": data.get("language") or language,
                        "confidence": None,
                        "source": "openai",
                    }
                )
        return utterances

    def suggest_characters(self, utterances: list[dict[str, Any]]) -> dict[str, Any]:
        compact = [
            {
                "utterance_id": u["utterance_id"],
                "start": u["start"],
                "end": u["end"],
                "speaker_id": u.get("speaker_id", "spk_00"),
                "text": u["text"],
            }
            for u in utterances[:500]
        ]
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["speakers", "utterances"],
            "properties": {
                "speakers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "speaker_id",
                            "suggested_character_name",
                            "confidence",
                            "evidence",
                        ],
                        "properties": {
                            "speaker_id": {"type": "string"},
                            "suggested_character_name": {"type": "string"},
                            "confidence": {"type": "number"},
                            "evidence": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
                "utterances": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "utterance_id",
                            "suggested_character",
                            "confidence",
                            "evidence",
                        ],
                        "properties": {
                            "utterance_id": {"type": "string"},
                            "suggested_character": {"type": "string"},
                            "confidence": {"type": "number"},
                            "evidence": {"type": "string"},
                        },
                    },
                },
            },
        }
        return self._json_response(
            name="character_suggestions",
            schema=schema,
            system=(
                "You infer likely character names from transcript context. Be conservative. "
                "If evidence is weak, use generic names like 男主, 女主, 旁白, 路人, 未知."
            ),
            user=json.dumps({"utterances": compact}, ensure_ascii=False),
        )

    def extract_story_beats(
        self,
        utterances: list[dict[str, Any]],
        *,
        target_language: str,
    ) -> dict[str, Any]:
        compact = [
            {
                "utterance_id": u["utterance_id"],
                "start": u["start"],
                "end": u["end"],
                "character_name": u.get("character_name", "未知"),
                "text": u["text"],
            }
            for u in utterances
        ]
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["beats"],
            "properties": {
                "beats": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "beat_id",
                            "start",
                            "end",
                            "title",
                            "summary",
                            "characters",
                            "source_utterance_ids",
                            "importance",
                            "main_plot",
                        ],
                        "properties": {
                            "beat_id": {"type": "string"},
                            "start": {"type": "number"},
                            "end": {"type": "number"},
                            "title": {"type": "string"},
                            "summary": {"type": "string"},
                            "characters": {"type": "array", "items": {"type": "string"}},
                            "source_utterance_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "importance": {"type": "number"},
                            "main_plot": {"type": "boolean"},
                        },
                    },
                }
            },
        }
        return self._json_response(
            name="story_beats",
            schema=schema,
            system=(
                "You extract chronological story beats from a transcript. "
                "Every claim must be supported by source_utterance_ids. "
                f"Write titles and summaries in {target_language}."
            ),
            user=json.dumps({"utterances": compact}, ensure_ascii=False),
        )

    def write_narration_script(
        self,
        story_beats: list[dict[str, Any]],
        *,
        target_duration_sec: int,
        narration_language: str,
    ) -> dict[str, Any]:
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["script_id", "target_duration_sec", "language", "lines"],
            "properties": {
                "script_id": {"type": "string"},
                "target_duration_sec": {"type": "integer"},
                "language": {"type": "string"},
                "lines": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "line_id",
                            "text",
                            "source_beat_ids",
                            "expected_duration_sec",
                            "importance",
                        ],
                        "properties": {
                            "line_id": {"type": "string"},
                            "text": {"type": "string"},
                            "source_beat_ids": {"type": "array", "items": {"type": "string"}},
                            "expected_duration_sec": {"type": "number"},
                            "importance": {"type": "number"},
                        },
                    },
                },
            },
        }
        return self._json_response(
            name="narration_script",
            schema=schema,
            system=(
                "You write concise recap narration for a short video edit. "
                "Preserve story causality. Do not invent facts. Each line must cite source_beat_ids. "
                f"Write in {narration_language}."
            ),
            user=json.dumps(
                {
                    "target_duration_sec": target_duration_sec,
                    "beats": story_beats,
                    "duration_guidance": "Keep total narration close to target duration.",
                },
                ensure_ascii=False,
            ),
        )

    def synthesize_speech(
        self,
        text: str,
        output_path: Path,
        *,
        language: str,
    ) -> float:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.client.audio.speech.with_streaming_response.create(
                model=self.tts_model,
                voice=self.tts_voice,
                input=text,
                response_format="wav",
            ) as response:
                response.stream_to_file(output_path)
        except Exception:
            # Some TTS models or accounts may not accept response_format. Retry with defaults.
            with self.client.audio.speech.with_streaming_response.create(
                model=self.tts_model,
                voice=self.tts_voice,
                input=text,
            ) as response:
                response.stream_to_file(output_path)
        try:
            return wav_duration(output_path)
        except Exception:
            return estimate_tts_duration(text, language)

    def _json_response(self, *, name: str, schema: dict[str, Any], system: str, user: str) -> dict[str, Any]:
        try:
            response = self.client.responses.create(
                model=self.llm_model,
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": name,
                        "schema": schema,
                        "strict": True,
                    }
                },
            )
            return json.loads(response.output_text)
        except Exception:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": system
                        + "\nReturn only valid JSON matching this schema: "
                        + json.dumps(schema, ensure_ascii=False),
                    },
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(content)


def _model_to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return json.loads(value.json())
