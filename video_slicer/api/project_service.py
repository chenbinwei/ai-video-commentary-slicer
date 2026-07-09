"""Service helpers for project, context, and version API routes."""

from __future__ import annotations

import json
from pathlib import Path

from video_slicer.api.schemas import CreateProjectRequest, CreateVersionRequest
from video_slicer.context_packet import normalize_context_packet
from video_slicer.project_models import (
    AspectRatio,
    AudioMode,
    ProjectRecord,
    SubtitleLanguage,
    VersionRecord,
    VersionSettings,
)
from video_slicer.project_store import LocalProjectStore


def create_project(store: LocalProjectStore, request: CreateProjectRequest) -> ProjectRecord:
    return store.create_project(
        source_video_path=request.source_video_path,
        source_duration_seconds=request.source_duration_seconds,
        user_id=request.user_id,
    )


def update_project_context(
    store: LocalProjectStore,
    *,
    project_id: str,
    context_packet: dict,
) -> ProjectRecord:
    project = store.get_project(project_id)
    project.context_packet = normalize_context_packet(context_packet)
    return store.save_project(project)


def version_settings_from_request(request: CreateVersionRequest) -> VersionSettings:
    return VersionSettings(
        target_duration_seconds=request.target_duration_seconds,
        audio_mode=AudioMode(request.audio_mode),
        voice_clone_id=request.voice_clone_id,
        bgm_path=request.bgm_path,
        voiceover_speed=request.voiceover_speed,
        voiceover_volume=request.voiceover_volume,
        bgm_volume=request.bgm_volume,
        subtitle_language=SubtitleLanguage(request.subtitle_language),
        aspect_ratio=AspectRatio(request.aspect_ratio),
    )


def create_version(store: LocalProjectStore, *, project_id: str, request: CreateVersionRequest) -> VersionRecord:
    settings = version_settings_from_request(request)
    return store.create_version(
        project_id=project_id,
        settings=settings,
        parent_version_id=request.parent_version_id,
        generation_group_id=request.generation_group_id,
        variant_goal=request.variant_goal,
    )


def write_project_context_file(store: LocalProjectStore, *, project_id: str, output_dir: Path) -> Path:
    project = store.get_project(project_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "context.json"
    path.write_text(json.dumps(project.context_packet, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
