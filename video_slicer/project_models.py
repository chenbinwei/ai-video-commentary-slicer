"""Project, version, and render-job records for the local product workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def default_privacy_flags() -> dict[str, bool]:
    return {
        "contains_voice_clone": False,
        "contains_person_audio": True,
        "contains_sensitive_content": False,
    }


class AudioMode(str, Enum):
    PURE_COMMENTARY = "pure_commentary"
    KEY_ORIGINAL_AUDIO = "key_original_audio"


class SubtitleLanguage(str, Enum):
    ZH = "zh"
    EN = "en"
    ZH_EN = "zh_en"


class AspectRatio(str, Enum):
    ORIGINAL = "original"
    VERTICAL_9_16_BLUR = "vertical_9_16_blur"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    FAILED = "failed"
    DONE = "done"
    CANCELLED = "cancelled"


class JobStage(str, Enum):
    EXTRACT_AUDIO = "extract_audio"
    TRANSCRIBE = "transcribe"
    GENERATE_SCRIPT = "generate_script"
    SEGMENT_SCRIPT = "segment_script"
    MATCH_VISUALS = "match_visuals"
    GENERATE_TTS = "generate_tts"
    FIT_DURATION = "fit_duration"
    CUT_VIDEO = "cut_video"
    MIX_AUDIO = "mix_audio"
    BURN_SUBTITLES = "burn_subtitles"
    EXPORT = "export"


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _coerce_enum(enum_type: type[Enum], value: Any) -> Enum:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(str(item.value) for item in enum_type)
        raise ValueError(f"{enum_type.__name__} must be one of: {allowed}") from exc


@dataclass
class UserContext:
    work_title: str = ""
    main_characters: list[str] = field(default_factory=list)
    synopsis: str = ""
    must_mentions: list[str] = field(default_factory=list)
    forbidden_content: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_title": self.work_title,
            "main_characters": list(self.main_characters),
            "synopsis": self.synopsis,
            "must_mentions": list(self.must_mentions),
            "forbidden_content": list(self.forbidden_content),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "UserContext":
        data = data or {}
        return cls(
            work_title=str(data.get("work_title", "")),
            main_characters=_string_list(data.get("main_characters")),
            synopsis=str(data.get("synopsis", "")),
            must_mentions=_string_list(data.get("must_mentions")),
            forbidden_content=_string_list(data.get("forbidden_content")),
        )


@dataclass
class VersionSettings:
    target_duration_seconds: float
    audio_mode: AudioMode = AudioMode.PURE_COMMENTARY
    voice_clone_id: str = ""
    bgm_path: str = ""
    voiceover_speed: float = 1.0
    voiceover_volume: float = 1.0
    bgm_volume: float = 0.16
    subtitle_language: SubtitleLanguage = SubtitleLanguage.ZH
    aspect_ratio: AspectRatio = AspectRatio.ORIGINAL

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_duration_seconds": self.target_duration_seconds,
            "audio_mode": self.audio_mode.value,
            "voice_clone_id": self.voice_clone_id,
            "bgm_path": self.bgm_path,
            "voiceover_speed": self.voiceover_speed,
            "voiceover_volume": self.voiceover_volume,
            "bgm_volume": self.bgm_volume,
            "subtitle_language": self.subtitle_language.value,
            "aspect_ratio": self.aspect_ratio.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VersionSettings":
        return cls(
            target_duration_seconds=float(data["target_duration_seconds"]),
            audio_mode=_coerce_enum(AudioMode, data.get("audio_mode", AudioMode.PURE_COMMENTARY.value)),
            voice_clone_id=str(data.get("voice_clone_id", "")),
            bgm_path=str(data.get("bgm_path", "")),
            voiceover_speed=float(data.get("voiceover_speed", 1.0)),
            voiceover_volume=float(data.get("voiceover_volume", 1.0)),
            bgm_volume=float(data.get("bgm_volume", 0.16)),
            subtitle_language=_coerce_enum(SubtitleLanguage, data.get("subtitle_language", SubtitleLanguage.ZH.value)),
            aspect_ratio=_coerce_enum(AspectRatio, data.get("aspect_ratio", AspectRatio.ORIGINAL.value)),
        )


def validate_version_settings(
    settings: VersionSettings,
    *,
    source_duration_seconds: float | None = None,
) -> None:
    errors: list[str] = []
    if settings.target_duration_seconds <= 0:
        errors.append("target_duration_seconds must be greater than 0")
    if source_duration_seconds is not None and settings.target_duration_seconds >= source_duration_seconds:
        errors.append("target_duration_seconds must be shorter than source video duration")
    if not 0.5 <= settings.voiceover_speed <= 1.5:
        errors.append("voiceover_speed must be between 0.5 and 1.5")
    if settings.voiceover_volume < 0:
        errors.append("voiceover_volume must be greater than or equal to 0")
    if settings.bgm_volume < 0:
        errors.append("bgm_volume must be greater than or equal to 0")
    if errors:
        raise ValueError("; ".join(errors))


@dataclass
class ProjectRecord:
    user_id: str = "local_user"
    project_id: str = field(default_factory=lambda: new_id("project"))
    source_video_path: str = ""
    source_audio_path: str = ""
    transcript_path: str = ""
    source_duration_seconds: float | None = None
    user_context: UserContext = field(default_factory=UserContext)
    analysis: dict[str, Any] = field(default_factory=dict)
    data_region: str = "local"
    privacy_flags: dict[str, bool] = field(default_factory=default_privacy_flags)
    retention_until: str = ""
    deleted_at: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "project_id": self.project_id,
            "source_video_path": self.source_video_path,
            "source_audio_path": self.source_audio_path,
            "transcript_path": self.transcript_path,
            "source_duration_seconds": self.source_duration_seconds,
            "user_context": self.user_context.to_dict(),
            "analysis": self.analysis,
            "data_region": self.data_region,
            "privacy_flags": dict(self.privacy_flags),
            "retention_until": self.retention_until,
            "deleted_at": self.deleted_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectRecord":
        duration = data.get("source_duration_seconds")
        return cls(
            user_id=str(data.get("user_id", "local_user")),
            project_id=str(data["project_id"]),
            source_video_path=str(data.get("source_video_path", "")),
            source_audio_path=str(data.get("source_audio_path", "")),
            transcript_path=str(data.get("transcript_path", "")),
            source_duration_seconds=float(duration) if duration is not None else None,
            user_context=UserContext.from_dict(data.get("user_context")),
            analysis=dict(data.get("analysis", {})),
            data_region=str(data.get("data_region", "local")),
            privacy_flags={**default_privacy_flags(), **dict(data.get("privacy_flags", {}))},
            retention_until=str(data.get("retention_until", "")),
            deleted_at=str(data.get("deleted_at", "")),
            created_at=str(data.get("created_at", utc_now_iso())),
            updated_at=str(data.get("updated_at", utc_now_iso())),
        )


@dataclass
class VersionRecord:
    project_id: str
    version_id: str = field(default_factory=lambda: new_id("version"))
    parent_version_id: str = ""
    generation_group_id: str = ""
    variant_goal: str = "manual"
    settings: VersionSettings = field(default_factory=lambda: VersionSettings(target_duration_seconds=120.0))
    generated_script: str = ""
    final_script: str = ""
    segmented_script: list[dict[str, Any]] = field(default_factory=list)
    visual_matches: list[dict[str, Any]] = field(default_factory=list)
    tts_audio_path: str = ""
    subtitle_paths: dict[str, str] = field(default_factory=dict)
    export_paths: dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "version_id": self.version_id,
            "parent_version_id": self.parent_version_id,
            "generation_group_id": self.generation_group_id,
            "variant_goal": self.variant_goal,
            "settings": self.settings.to_dict(),
            "generated_script": self.generated_script,
            "final_script": self.final_script,
            "segmented_script": self.segmented_script,
            "visual_matches": self.visual_matches,
            "tts_audio_path": self.tts_audio_path,
            "subtitle_paths": self.subtitle_paths,
            "export_paths": self.export_paths,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VersionRecord":
        return cls(
            project_id=str(data["project_id"]),
            version_id=str(data["version_id"]),
            parent_version_id=str(data.get("parent_version_id", "")),
            generation_group_id=str(data.get("generation_group_id", "")),
            variant_goal=str(data.get("variant_goal", "manual")),
            settings=VersionSettings.from_dict(data["settings"]),
            generated_script=str(data.get("generated_script", "")),
            final_script=str(data.get("final_script", "")),
            segmented_script=list(data.get("segmented_script", [])),
            visual_matches=list(data.get("visual_matches", [])),
            tts_audio_path=str(data.get("tts_audio_path", "")),
            subtitle_paths=dict(data.get("subtitle_paths", {})),
            export_paths=dict(data.get("export_paths", {})),
            created_at=str(data.get("created_at", utc_now_iso())),
            updated_at=str(data.get("updated_at", utc_now_iso())),
        )


@dataclass
class JobRecord:
    project_id: str
    version_id: str
    job_id: str = field(default_factory=lambda: new_id("job"))
    status: JobStatus = JobStatus.PENDING
    current_stage: JobStage = JobStage.EXTRACT_AUDIO
    error_message: str = ""
    duration_seconds: float | None = None
    export_paths: dict[str, str] = field(default_factory=dict)
    stage_history: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def add_history(self, *, status: JobStatus, stage: JobStage, error_message: str = "") -> None:
        self.stage_history.append({
            "status": status.value,
            "stage": stage.value,
            "error_message": error_message,
            "at": utc_now_iso(),
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "version_id": self.version_id,
            "job_id": self.job_id,
            "status": self.status.value,
            "current_stage": self.current_stage.value,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds,
            "export_paths": self.export_paths,
            "stage_history": self.stage_history,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobRecord":
        duration = data.get("duration_seconds")
        return cls(
            project_id=str(data["project_id"]),
            version_id=str(data["version_id"]),
            job_id=str(data["job_id"]),
            status=_coerce_enum(JobStatus, data.get("status", JobStatus.PENDING.value)),
            current_stage=_coerce_enum(JobStage, data.get("current_stage", JobStage.EXTRACT_AUDIO.value)),
            error_message=str(data.get("error_message", "")),
            duration_seconds=float(duration) if duration is not None else None,
            export_paths=dict(data.get("export_paths", {})),
            stage_history=list(data.get("stage_history", [])),
            created_at=str(data.get("created_at", utc_now_iso())),
            updated_at=str(data.get("updated_at", utc_now_iso())),
        )
