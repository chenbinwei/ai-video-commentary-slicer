from __future__ import annotations

from pathlib import Path
from typing import Any

from better_story.providers.base import AIProvider
from better_story.utils.audio import estimate_tts_duration, wav_duration, write_silence_wav


class MockProvider(AIProvider):
    def transcribe_audio(
        self,
        audio_path: Path,
        *,
        language: str,
        offset_sec: float = 0.0,
    ) -> list[dict[str, Any]]:
        duration = wav_duration(audio_path)
        utterances: list[dict[str, Any]] = []
        step = 12.0
        cursor = 0.0
        index = 0
        while cursor < duration:
            end = min(duration, cursor + 6.0)
            utterances.append(
                {
                    "start": round(offset_sec + cursor, 3),
                    "end": round(offset_sec + end, 3),
                    "text": f"Mock transcript line {index + 1}. Replace this with real ASR.",
                    "language": "mock" if language == "auto" else language,
                    "confidence": 1.0,
                    "source": "mock",
                }
            )
            cursor += step
            index += 1
        return utterances

    def suggest_characters(self, utterances: list[dict[str, Any]]) -> dict[str, Any]:
        suggestions = []
        for item in utterances:
            speaker_id = item.get("speaker_id", "spk_00")
            suggestions.append(
                {
                    "utterance_id": item["utterance_id"],
                    "suggested_character": "旁白/未知" if speaker_id == "spk_00" else speaker_id,
                    "confidence": 0.2,
                    "evidence": "mock provider",
                }
            )
        speakers = sorted({item.get("speaker_id", "spk_00") for item in utterances})
        return {
            "speakers": [
                {
                    "speaker_id": speaker_id,
                    "suggested_character_name": "旁白/未知",
                    "confidence": 0.2,
                    "evidence": ["mock provider"],
                }
                for speaker_id in speakers
            ],
            "utterances": suggestions,
        }

    def extract_story_beats(
        self,
        utterances: list[dict[str, Any]],
        *,
        target_language: str,
    ) -> dict[str, Any]:
        beats = []
        group_size = 5
        for index in range(0, len(utterances), group_size):
            group = utterances[index : index + group_size]
            if not group:
                continue
            beat_no = len(beats) + 1
            beats.append(
                {
                    "beat_id": f"beat_{beat_no:04}",
                    "start": group[0]["start"],
                    "end": group[-1]["end"],
                    "title": f"Mock story beat {beat_no}",
                    "summary": "This placeholder beat groups nearby transcript lines for pipeline testing.",
                    "characters": sorted({u.get("character_name", "未知") for u in group}),
                    "source_utterance_ids": [u["utterance_id"] for u in group],
                    "importance": 0.6,
                    "main_plot": True,
                }
            )
        return {"beats": beats}

    def write_narration_script(
        self,
        story_beats: list[dict[str, Any]],
        *,
        target_duration_sec: int,
        narration_language: str,
    ) -> dict[str, Any]:
        lines = []
        max_lines = max(1, min(len(story_beats), target_duration_sec // 12))
        for beat in story_beats[:max_lines]:
            line_no = len(lines) + 1
            text = f"第 {line_no} 段剧情：{beat['summary']}"
            lines.append(
                {
                    "line_id": f"line_{line_no:04}",
                    "text": text,
                    "source_beat_ids": [beat["beat_id"]],
                    "expected_duration_sec": estimate_tts_duration(text, narration_language),
                    "importance": beat.get("importance", 0.5),
                }
            )
        return {
            "script_id": "script_mock",
            "target_duration_sec": target_duration_sec,
            "language": narration_language,
            "lines": lines,
        }

    def synthesize_speech(
        self,
        text: str,
        output_path: Path,
        *,
        language: str,
    ) -> float:
        duration = estimate_tts_duration(text, language)
        write_silence_wav(output_path, duration)
        return duration
