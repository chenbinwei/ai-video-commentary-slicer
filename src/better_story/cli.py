from __future__ import annotations

import argparse
import sys
from pathlib import Path

from better_story.config import TaskConfig, load_config
from better_story.modules.align import align_script
from better_story.modules.edl import build_edl
from better_story.modules.media import prepare_media
from better_story.modules.qc import write_qc_report
from better_story.modules.render import render_video
from better_story.modules.scenes import build_scenes
from better_story.modules.story import extract_story
from better_story.modules.task import create_task
from better_story.modules.transcribe import suggest_characters, transcribe
from better_story.modules.tts import export_tts_text, import_external_narration, synthesize_narration
from better_story.modules.rewrite import write_script
from better_story.providers import make_provider
from better_story.review_gui import run_review_gui
from better_story.settings import load_settings, update_settings
from better_story.settings_gui import run_settings_gui
from better_story.utils.api_key import resolve_api_key
from better_story.utils.json_io import write_json


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    try:
        args.func(args)
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="better-story")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("providers", help="List supported API providers.")
    p.set_defaults(func=cmd_providers)

    p = sub.add_parser("settings", help="Show or update saved local API settings.")
    p.add_argument("--provider", choices=["openai", "openai_compatible", "mock"])
    p.add_argument("--api-key")
    p.add_argument("--base-url")
    p.add_argument("--asr-model")
    p.add_argument("--llm-model")
    p.add_argument("--tts-model")
    p.add_argument("--tts-voice")
    p.add_argument("--tts-provider", choices=["same", "openai", "openai_compatible", "mock"])
    p.add_argument("--tts-api-key")
    p.add_argument("--tts-base-url")
    p.set_defaults(func=cmd_settings)

    p = sub.add_parser("settings-gui", help="Start local GUI for saving API settings.")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8764)
    p.set_defaults(func=cmd_settings_gui)

    p = sub.add_parser("create", help="Create a task directory for a source video.")
    p.add_argument("--video", required=True)
    add_config_args(p)
    p.add_argument("--copy-input", action="store_true")
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("prepare", help="Probe media and extract audio.")
    p.add_argument("--task", required=True)
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("transcribe", help="Transcribe task audio.")
    p.add_argument("--task", required=True)
    add_provider_args(p)
    p.add_argument("--suggest-characters", action="store_true")
    p.set_defaults(func=cmd_transcribe)

    p = sub.add_parser("suggest-characters", help="Ask provider to suggest character labels.")
    p.add_argument("--task", required=True)
    add_provider_args(p)
    p.set_defaults(func=cmd_suggest_characters)

    p = sub.add_parser("review", help="Start local GUI for per-line character correction.")
    p.add_argument("--task", required=True)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("scenes", help="Build simple fixed-window scenes.")
    p.add_argument("--task", required=True)
    p.add_argument("--scene-length-sec", type=float, default=20.0)
    p.set_defaults(func=cmd_scenes)

    p = sub.add_parser("story", help="Extract story beats.")
    p.add_argument("--task", required=True)
    add_provider_args(p)
    p.set_defaults(func=cmd_story)

    p = sub.add_parser("script", help="Generate narration script.")
    p.add_argument("--task", required=True)
    add_provider_args(p)
    p.set_defaults(func=cmd_script)

    p = sub.add_parser("align", help="Align script lines to source video ranges.")
    p.add_argument("--task", required=True)
    p.set_defaults(func=cmd_align)

    p = sub.add_parser("tts", help="Generate narration TTS.")
    p.add_argument("--task", required=True)
    add_provider_args(p)
    p.set_defaults(func=cmd_tts)

    p = sub.add_parser("export-tts-text", help="Export narration text for external TTS tools.")
    p.add_argument("--task", required=True)
    p.set_defaults(func=cmd_export_tts_text)

    p = sub.add_parser("import-narration", help="Import externally generated narration audio.")
    p.add_argument("--task", required=True)
    p.add_argument("--audio", required=True)
    p.set_defaults(func=cmd_import_narration)

    p = sub.add_parser("edl", help="Build edit decision list and subtitles.")
    p.add_argument("--task", required=True)
    p.set_defaults(func=cmd_edl)

    p = sub.add_parser("render", help="Render final recap video.")
    p.add_argument("--task", required=True)
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("qc", help="Write a simple QC report.")
    p.add_argument("--task", required=True)
    p.set_defaults(func=cmd_qc)

    p = sub.add_parser("continue-demo", help="Run stages after character review.")
    p.add_argument("--task", required=True)
    add_provider_args(p)
    p.add_argument("--skip-tts", action="store_true", help="Stop after exporting text for external TTS.")
    p.add_argument("--external-narration", help="Use an externally generated narration audio file.")
    p.set_defaults(func=cmd_continue_demo)

    p = sub.add_parser("run-auto", help="Run the whole demo without manual review.")
    p.add_argument("--video", required=True)
    add_config_args(p)
    add_api_key_args(p)
    p.add_argument("--copy-input", action="store_true")
    p.add_argument("--skip-character-suggestions", action="store_true")
    p.set_defaults(func=cmd_run_auto)
    return parser


def add_config_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target-duration", type=int, default=180)
    parser.add_argument("--source-language", default="auto")
    parser.add_argument("--narration-language", default="zh-CN")
    parser.add_argument(
        "--output-profile",
        choices=["landscape_16_9", "vertical_9_16_blur_bg"],
        default="landscape_16_9",
    )
    parser.add_argument("--provider", choices=["openai", "openai_compatible", "mock"], default="openai_compatible")
    parser.add_argument("--base-url")
    parser.add_argument("--asr-model")
    parser.add_argument("--llm-model")
    parser.add_argument("--tts-provider", choices=["same", "openai", "openai_compatible", "mock"])
    parser.add_argument("--tts-base-url")
    parser.add_argument("--tts-model")
    parser.add_argument("--tts-voice")


def add_provider_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", choices=["openai", "openai_compatible", "mock"])
    add_api_key_args(parser)
    parser.add_argument("--base-url")
    parser.add_argument("--asr-model")
    parser.add_argument("--llm-model")
    parser.add_argument("--tts-provider", choices=["same", "openai", "openai_compatible", "mock"])
    parser.add_argument("--tts-api-key")
    parser.add_argument("--tts-base-url")
    parser.add_argument("--tts-model")
    parser.add_argument("--tts-voice")


def add_api_key_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--api-key")
    parser.add_argument("--prompt-api-key", action="store_true")


def task_dir_arg(args: argparse.Namespace) -> Path:
    return Path(args.task).expanduser().resolve()


def provider_from_args(args: argparse.Namespace, task_dir: Path):
    config = load_config(task_dir)
    settings = load_settings()
    provider_name = args.provider or settings.provider or config.provider
    base_url = args.base_url or settings.base_url or config.base_url
    asr_model = args.asr_model or settings.asr_model or config.asr_model
    llm_model = args.llm_model or settings.llm_model or config.llm_model
    tts_model = args.tts_model or settings.tts_model or config.tts_model
    tts_voice = args.tts_voice or settings.tts_voice or config.tts_voice
    api_key = resolve_api_key(
        provider_name,
        cli_api_key=args.api_key or settings.api_key,
        prompt_api_key=args.prompt_api_key,
    )
    return make_provider(
        provider_name,
        api_key=api_key,
        base_url=base_url,
        asr_model=asr_model,
        llm_model=llm_model,
        tts_model=tts_model,
        tts_voice=tts_voice,
    )


def tts_provider_from_args(args: argparse.Namespace, task_dir: Path, fallback_provider=None):
    config = load_config(task_dir)
    settings = load_settings()
    tts_provider_name = (
        getattr(args, "tts_provider", None)
        or settings.tts_provider
        or config.tts_provider
        or "same"
    )
    if tts_provider_name == "same":
        return fallback_provider or provider_from_args(args, task_dir)
    tts_base_url = (
        getattr(args, "tts_base_url", None)
        or settings.tts_base_url
        or config.tts_base_url
        or ""
    )
    tts_api_key = (
        getattr(args, "tts_api_key", None)
        or settings.tts_api_key
        or getattr(args, "api_key", None)
        or settings.api_key
    )
    return make_provider(
        tts_provider_name,
        api_key=resolve_api_key(tts_provider_name, cli_api_key=tts_api_key, prompt_api_key=getattr(args, "prompt_api_key", False)),
        base_url=tts_base_url,
        asr_model=getattr(args, "asr_model", None) or settings.asr_model or config.asr_model,
        llm_model=getattr(args, "llm_model", None) or settings.llm_model or config.llm_model,
        tts_model=getattr(args, "tts_model", None) or settings.tts_model or config.tts_model,
        tts_voice=getattr(args, "tts_voice", None) or settings.tts_voice or config.tts_voice,
    )


def cmd_providers(args: argparse.Namespace) -> None:
    print("openai_compatible - OpenAI SDK-compatible third-party or official API with optional base_url")
    print("openai            - Official OpenAI API shortcut")
    print("mock              - No-cost placeholder provider for pipeline testing")


def cmd_settings(args: argparse.Namespace) -> None:
    updates = {
        "provider": args.provider,
        "api_key": args.api_key,
        "base_url": args.base_url,
        "asr_model": args.asr_model,
        "llm_model": args.llm_model,
        "tts_provider": args.tts_provider,
        "tts_api_key": args.tts_api_key,
        "tts_base_url": args.tts_base_url,
        "tts_model": args.tts_model,
        "tts_voice": args.tts_voice,
    }
    if any(value is not None for value in updates.values()):
        settings = update_settings(updates)
        print("Saved settings to .better_story/settings.json")
    else:
        settings = load_settings()
    masked_key = f"{settings.api_key[:6]}...{settings.api_key[-4:]}" if len(settings.api_key) > 12 else "(not set)"
    print(f"provider: {settings.provider}")
    print(f"base_url: {settings.base_url or '(default official endpoint)'}")
    print(f"api_key: {masked_key}")
    print(f"asr_model: {settings.asr_model}")
    print(f"llm_model: {settings.llm_model}")
    tts_masked_key = f"{settings.tts_api_key[:6]}...{settings.tts_api_key[-4:]}" if len(settings.tts_api_key) > 12 else "(not set)"
    print(f"tts_provider: {settings.tts_provider}")
    print(f"tts_base_url: {settings.tts_base_url or '(same/default endpoint)'}")
    print(f"tts_api_key: {tts_masked_key}")
    print(f"tts_model: {settings.tts_model}")
    print(f"tts_voice: {settings.tts_voice}")


def cmd_settings_gui(args: argparse.Namespace) -> None:
    run_settings_gui(host=args.host, port=args.port)


def cmd_create(args: argparse.Namespace) -> None:
    config = TaskConfig.from_env_and_args(
        video_path=args.video,
        target_duration_sec=args.target_duration,
        source_language=args.source_language,
        narration_language=args.narration_language,
        output_profile=args.output_profile,
        provider=args.provider,
        base_url=args.base_url,
        asr_model=args.asr_model,
        llm_model=args.llm_model,
        tts_provider=args.tts_provider,
        tts_base_url=args.tts_base_url,
        tts_model=args.tts_model,
        tts_voice=args.tts_voice,
        copy_input=args.copy_input,
    )
    task_dir = create_task(config)
    print(task_dir)


def cmd_prepare(args: argparse.Namespace) -> None:
    task_dir = task_dir_arg(args)
    prepare_media(task_dir)
    print(f"Prepared media under {task_dir}")


def cmd_transcribe(args: argparse.Namespace) -> None:
    task_dir = task_dir_arg(args)
    provider = provider_from_args(args, task_dir)
    transcribe(task_dir, provider)
    if args.suggest_characters:
        suggest_characters(task_dir, provider)
    print(f"Transcription written under {task_dir / 'analysis'}")


def cmd_suggest_characters(args: argparse.Namespace) -> None:
    task_dir = task_dir_arg(args)
    provider = provider_from_args(args, task_dir)
    suggest_characters(task_dir, provider)
    print(f"Character suggestions written under {task_dir / 'analysis'}")


def cmd_review(args: argparse.Namespace) -> None:
    run_review_gui(task_dir_arg(args), host=args.host, port=args.port)


def cmd_scenes(args: argparse.Namespace) -> None:
    task_dir = task_dir_arg(args)
    build_scenes(task_dir, scene_length_sec=args.scene_length_sec)
    print(f"Scenes written to {task_dir / 'analysis' / 'scenes.json'}")


def cmd_story(args: argparse.Namespace) -> None:
    task_dir = task_dir_arg(args)
    provider = provider_from_args(args, task_dir)
    extract_story(task_dir, provider)
    print(f"Story beats written to {task_dir / 'analysis' / 'story_beats.json'}")


def cmd_script(args: argparse.Namespace) -> None:
    task_dir = task_dir_arg(args)
    provider = provider_from_args(args, task_dir)
    write_script(task_dir, provider)
    print(f"Script written to {task_dir / 'rewrite' / 'narration_script.json'}")


def cmd_align(args: argparse.Namespace) -> None:
    task_dir = task_dir_arg(args)
    align_script(task_dir)
    print(f"Aligned script written to {task_dir / 'rewrite' / 'aligned_script.json'}")


def cmd_tts(args: argparse.Namespace) -> None:
    task_dir = task_dir_arg(args)
    provider = tts_provider_from_args(args, task_dir)
    synthesize_narration(task_dir, provider)
    print(f"Narration written under {task_dir / 'audio'}")


def cmd_export_tts_text(args: argparse.Namespace) -> None:
    task_dir = task_dir_arg(args)
    output = export_tts_text(task_dir)
    print(output)


def cmd_import_narration(args: argparse.Namespace) -> None:
    task_dir = task_dir_arg(args)
    import_external_narration(task_dir, Path(args.audio).expanduser().resolve())
    print(f"Imported narration to {task_dir / 'audio' / 'narration.wav'}")


def cmd_edl(args: argparse.Namespace) -> None:
    task_dir = task_dir_arg(args)
    build_edl(task_dir)
    print(f"EDL written to {task_dir / 'edit' / 'edl.json'}")


def cmd_render(args: argparse.Namespace) -> None:
    task_dir = task_dir_arg(args)
    output = render_video(task_dir)
    print(output)


def cmd_qc(args: argparse.Namespace) -> None:
    task_dir = task_dir_arg(args)
    write_qc_report(task_dir)
    print(f"QC report written to {task_dir / 'rewrite' / 'qc_report.json'}")


def cmd_continue_demo(args: argparse.Namespace) -> None:
    task_dir = task_dir_arg(args)
    provider = provider_from_args(args, task_dir)
    tts_provider = tts_provider_from_args(args, task_dir, fallback_provider=provider)
    run_downstream(
        task_dir,
        provider,
        tts_provider=tts_provider,
        skip_tts=args.skip_tts,
        external_narration=Path(args.external_narration).expanduser().resolve() if args.external_narration else None,
    )
    if not args.skip_tts:
        print(f"Demo output: {task_dir / 'output' / 'recap.mp4'}")


def cmd_run_auto(args: argparse.Namespace) -> None:
    config = TaskConfig.from_env_and_args(
        video_path=args.video,
        target_duration_sec=args.target_duration,
        source_language=args.source_language,
        narration_language=args.narration_language,
        output_profile=args.output_profile,
        provider=args.provider,
        base_url=args.base_url,
        asr_model=args.asr_model,
        llm_model=args.llm_model,
        tts_provider=args.tts_provider,
        tts_base_url=args.tts_base_url,
        tts_model=args.tts_model,
        tts_voice=args.tts_voice,
        copy_input=args.copy_input,
    )
    task_dir = create_task(config)
    print(f"Created task: {task_dir}")
    prepare_media(task_dir)
    provider = provider_from_args(args, task_dir)
    tts_provider = tts_provider_from_args(args, task_dir, fallback_provider=provider)
    transcribe(task_dir, provider)
    if not args.skip_character_suggestions:
        suggest_characters(task_dir, provider)
    run_downstream(task_dir, provider, tts_provider=tts_provider)
    write_json(
        task_dir / "logs" / "run_summary.json",
        {
            "task_dir": str(task_dir),
            "provider": args.provider,
            "output": str(task_dir / "output" / "recap.mp4"),
        },
    )
    print(f"Demo output: {task_dir / 'output' / 'recap.mp4'}")


def run_downstream(
    task_dir: Path,
    provider,
    *,
    tts_provider=None,
    skip_tts: bool = False,
    external_narration: Path | None = None,
) -> None:
    build_scenes(task_dir)
    extract_story(task_dir, provider)
    write_script(task_dir, provider)
    align_script(task_dir)
    if external_narration:
        export_tts_text(task_dir)
        import_external_narration(task_dir, external_narration)
    elif skip_tts:
        output = export_tts_text(task_dir)
        print(f"Exported TTS text to {output}")
        print("Generate narration externally, then run import-narration, edl, and render.")
        return
    else:
        synthesize_narration(task_dir, tts_provider or provider)
    build_edl(task_dir)
    render_video(task_dir)
    write_qc_report(task_dir)


if __name__ == "__main__":
    raise SystemExit(main())
