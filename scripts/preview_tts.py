"""Generate one standalone TTS preview audio file."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from video_slicer.pipeline import load_dotenv
from video_slicer.voice_registry import DEFAULT_REGISTRY_PATH, find_voice


def main() -> None:
    load_dotenv(Path(".env"))
    parser = argparse.ArgumentParser(description="Generate a standalone TTS preview without running the full video pipeline.")
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", default="outputs/tts_preview.mp3")
    parser.add_argument("--provider", choices=["fish", "ocool"], default=os.environ.get("TTS_MODE", "fish"))
    parser.add_argument("--voice-name", default=None, help="Local voice registry name or Fish reference id.")
    parser.add_argument("--fish-reference-id", default=os.environ.get("FISH_REFERENCE_ID", ""))
    parser.add_argument("--fish-model", default=os.environ.get("FISH_TTS_MODEL", "s2.1-pro-free"))
    parser.add_argument("--fish-base-url", default=os.environ.get("FISH_BASE_URL", "https://api.fish.audio"))
    parser.add_argument("--fish-speed", type=float, default=float(os.environ.get("FISH_TTS_SPEED", "1.0")))
    parser.add_argument("--fish-volume", type=float, default=float(os.environ.get("FISH_TTS_VOLUME", "0")))
    parser.add_argument("--fish-latency", default=os.environ.get("FISH_TTS_LATENCY", "normal"), choices=["normal", "balanced", "low"])
    parser.add_argument("--ocool-base-url", default=os.environ.get("OCOOL_BASE_URL", "https://one.ocoolai.com/v1"))
    parser.add_argument("--ocool-model", default=os.environ.get("OCOOL_TTS_MODEL", "tts-1-hd"))
    parser.add_argument("--ocool-voice", default=os.environ.get("OCOOL_TTS_VOICE", "echo"))
    parser.add_argument("--ocool-speed", type=float, default=float(os.environ.get("OCOOL_TTS_SPEED", "1.0")))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    args = parser.parse_args()

    output_path = Path(args.output)
    item: dict[str, Any] = {
        "sentence_id": 1,
        "text": args.text,
        "audio_path": str(output_path),
    }

    if args.provider == "fish":
        from tts_providers.fish import synthesize_batch

        reference_id = args.fish_reference_id
        if args.voice_name:
            voice = find_voice(args.voice_name, Path(args.registry))
            reference_id = str(voice.get("reference_id", "")) if voice else args.voice_name
        synthesize_batch(
            [item],
            reference_id=reference_id,
            model=args.fish_model,
            base_url=args.fish_base_url,
            speed=args.fish_speed,
            volume=args.fish_volume,
            latency=args.fish_latency,
        )
    else:
        from tts_providers.ocool import synthesize_batch

        synthesize_batch(
            [item],
            model=args.ocool_model,
            voice=args.ocool_voice,
            base_url=args.ocool_base_url,
            speed=args.ocool_speed,
        )

    print(f"Wrote TTS preview: {output_path}")


if __name__ == "__main__":
    main()
