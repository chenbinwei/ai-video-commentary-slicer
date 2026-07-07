"""Create a Fish Audio voice model and save it to the local voice registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tts_providers.fish import create_voice_model
from video_slicer.pipeline import load_dotenv
from video_slicer.voice_registry import DEFAULT_REGISTRY_PATH, upsert_voice


def main() -> None:
    load_dotenv(Path(".env"))
    parser = argparse.ArgumentParser(description="Create a Fish Audio voice model from local reference audio.")
    parser.add_argument("--audio", action="append", required=True, help="Reference audio path. Can be passed more than once.")
    parser.add_argument("--name", required=True, help="Local registry name, for example narrator_a.")
    parser.add_argument("--title", default=None, help="Fish Audio model title. Defaults to --name.")
    parser.add_argument("--description", default="Voice model for video slicing narration.")
    parser.add_argument("--visibility", default="private", choices=["private", "unlist", "public"])
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    audio_paths = [Path(item) for item in args.audio]
    result = create_voice_model(
        audio_paths=audio_paths,
        title=args.title or args.name,
        description=args.description,
        visibility=args.visibility,
        base_url=args.base_url,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    response_path = output_dir / f"fish_voice_model_{args.name}.json"
    response_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    reference_id = result.get("_id") or result.get("id") or result.get("model_id") or ""
    if not reference_id:
        raise SystemExit(f"Fish response did not include a model id. See {response_path}")

    upsert_voice(
        name=args.name,
        reference_id=reference_id,
        source_audio=[str(path) for path in audio_paths],
        note=args.note,
        metadata={"response_path": str(response_path)},
        path=Path(args.registry),
    )
    print(f"Wrote Fish Audio voice model response: {response_path}")
    print(f"Registered voice '{args.name}' in {args.registry}")
    print(f"FISH_REFERENCE_ID={reference_id}")


if __name__ == "__main__":
    main()
