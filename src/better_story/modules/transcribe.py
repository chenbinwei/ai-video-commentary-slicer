from __future__ import annotations

from pathlib import Path
from typing import Any

from better_story.config import load_config
from better_story.providers.base import AIProvider
from better_story.utils.audio import wav_duration
from better_story.utils.ffmpeg import run_command
from better_story.utils.json_io import read_json, write_json


def transcribe(task_dir: Path, provider: AIProvider) -> None:
    config = load_config(task_dir)
    audio_path = task_dir / "audio" / "source.wav"
    if not audio_path.exists():
        raise FileNotFoundError(f"Missing audio file: {audio_path}. Run prepare first.")

    chunks = split_audio_if_needed(audio_path, task_dir / "audio" / "chunks", config.asr_chunk_sec)
    utterances: list[dict[str, Any]] = []
    for chunk_index, (chunk_path, offset) in enumerate(chunks):
        chunk_utterances = provider.transcribe_audio(
            chunk_path,
            language=config.source_language,
            offset_sec=offset,
        )
        for item in chunk_utterances:
            item["asr_chunk_id"] = f"chunk_{chunk_index:03}"
            utterances.append(item)

    utterances.sort(key=lambda item: (item["start"], item["end"]))
    normalized = []
    for index, item in enumerate(utterances):
        normalized.append(
            {
                "utterance_id": f"utt_{index + 1:06}",
                "start": round(float(item["start"]), 3),
                "end": round(float(item["end"]), 3),
                "text": str(item.get("text", "")).strip(),
                "language": item.get("language") or config.source_language,
                "confidence": item.get("confidence"),
                "speaker_id": item.get("speaker_id") or "spk_00",
                "speaker_confidence": item.get("speaker_confidence"),
                "source": item.get("source", "asr"),
                "asr_chunk_id": item.get("asr_chunk_id"),
            }
        )

    write_json(task_dir / "analysis" / "transcript_raw.json", utterances)
    write_json(task_dir / "analysis" / "utterances.json", normalized)
    write_json(task_dir / "analysis" / "speakers.json", summarize_speakers(normalized))
    initialize_character_files(task_dir, normalized)


def split_audio_if_needed(audio_path: Path, chunks_dir: Path, chunk_sec: int) -> list[tuple[Path, float]]:
    duration = wav_duration(audio_path)
    if duration <= chunk_sec:
        return [(audio_path, 0.0)]
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunks: list[tuple[Path, float]] = []
    offset = 0.0
    index = 0
    while offset < duration:
        out = chunks_dir / f"chunk_{index:03}.wav"
        run_command(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{offset:.3f}",
                "-t",
                f"{chunk_sec:.3f}",
                "-i",
                str(audio_path),
                "-c",
                "copy",
                str(out),
            ]
        )
        chunks.append((out, offset))
        offset += chunk_sec
        index += 1
    return chunks


def summarize_speakers(utterances: list[dict[str, Any]]) -> dict[str, Any]:
    speakers: dict[str, dict[str, Any]] = {}
    for item in utterances:
        speaker_id = item.get("speaker_id") or "spk_00"
        entry = speakers.setdefault(
            speaker_id,
            {
                "speaker_id": speaker_id,
                "utterance_count": 0,
                "total_duration_sec": 0.0,
                "sample_utterance_ids": [],
            },
        )
        entry["utterance_count"] += 1
        entry["total_duration_sec"] += max(0.0, item["end"] - item["start"])
        if len(entry["sample_utterance_ids"]) < 8:
            entry["sample_utterance_ids"].append(item["utterance_id"])
    return {"speakers": list(speakers.values())}


def initialize_character_files(task_dir: Path, utterances: list[dict[str, Any]]) -> None:
    speaker_ids = sorted({item.get("speaker_id") or "spk_00" for item in utterances})
    character_map = {
        "speakers": [
            {
                "speaker_id": speaker_id,
                "character_name": "未知",
                "locked": False,
                "notes": "",
            }
            for speaker_id in speaker_ids
        ],
        "utterance_overrides": [],
    }
    write_json(task_dir / "analysis" / "character_map.json", character_map)
    write_json(task_dir / "analysis" / "utterances_with_characters.json", apply_character_map_data(utterances, character_map))


def apply_character_map_data(utterances: list[dict[str, Any]], character_map: dict[str, Any]) -> list[dict[str, Any]]:
    speaker_map = {item["speaker_id"]: item["character_name"] for item in character_map.get("speakers", [])}
    overrides = {
        item["utterance_id"]: item["character_name"]
        for item in character_map.get("utterance_overrides", [])
    }
    out = []
    for item in utterances:
        copied = dict(item)
        copied["character_name"] = overrides.get(
            item["utterance_id"],
            speaker_map.get(item.get("speaker_id") or "spk_00", "未知"),
        )
        copied.setdefault("suggested_character", copied["character_name"])
        out.append(copied)
    return out


def suggest_characters(task_dir: Path, provider: AIProvider) -> None:
    utterances = read_json(task_dir / "analysis" / "utterances.json")
    suggestions = provider.suggest_characters(utterances)
    write_json(task_dir / "analysis" / "character_suggestions.json", suggestions)

    suggested_by_utterance = {
        item["utterance_id"]: item
        for item in suggestions.get("utterances", [])
    }
    speaker_suggestions = {
        item["speaker_id"]: item
        for item in suggestions.get("speakers", [])
    }
    for item in utterances:
        utterance_suggestion = suggested_by_utterance.get(item["utterance_id"])
        if utterance_suggestion:
            item["suggested_character"] = utterance_suggestion.get("suggested_character", "未知")
            item["character_suggestion_confidence"] = utterance_suggestion.get("confidence")
            item["character_suggestion_evidence"] = utterance_suggestion.get("evidence")
        else:
            speaker_id = item.get("speaker_id") or "spk_00"
            item["suggested_character"] = speaker_suggestions.get(speaker_id, {}).get(
                "suggested_character_name",
                "未知",
            )
    character_map = {
        "speakers": [
            {
                "speaker_id": speaker_id,
                "character_name": speaker_suggestions.get(speaker_id, {}).get("suggested_character_name", "未知"),
                "locked": False,
                "notes": "; ".join(speaker_suggestions.get(speaker_id, {}).get("evidence", [])),
            }
            for speaker_id in sorted({u.get("speaker_id") or "spk_00" for u in utterances})
        ],
        "utterance_overrides": [],
    }
    write_json(task_dir / "analysis" / "utterances.json", utterances)
    write_json(task_dir / "analysis" / "character_map.json", character_map)
    write_json(task_dir / "analysis" / "utterances_with_characters.json", apply_character_map_data(utterances, character_map))
