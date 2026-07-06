from __future__ import annotations

import math
import wave
from pathlib import Path


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        if rate == 0:
            return 0.0
        return frames / float(rate)


def write_silence_wav(path: Path, duration_sec: float, sample_rate: int = 24000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = max(1, int(duration_sec * sample_rate))
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * frames)


def estimate_tts_duration(text: str, language: str = "zh-CN") -> float:
    text = text.strip()
    if not text:
        return 0.8
    if language.lower().startswith(("zh", "ja", "ko")):
        units_per_min = 260.0
        units = len(text)
    else:
        units_per_min = 150.0
        units = max(1, len(text.split()))
    return max(1.2, math.ceil((units / units_per_min) * 60.0 * 10.0) / 10.0)
