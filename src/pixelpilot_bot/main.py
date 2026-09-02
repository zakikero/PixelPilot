from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class OfflineServiceConfig:
    stt_command: str
    llm_command: str
    tts_command: str


@dataclass(frozen=True)
class BotPipelineConfig:
    offline: bool
    transport: str
    services: OfflineServiceConfig


@dataclass(frozen=True)
class PipelineStage:
    name: str
    detail: str


@dataclass(frozen=True)
class PipelineBlueprint:
    stages: Tuple[PipelineStage, ...]


def _as_bool(raw: str, *, default: bool) -> bool:
    if raw is None:
        return default
    value = raw.strip().lower()
    return value in {"1", "true", "yes", "on"}


def load_config_from_env() -> BotPipelineConfig:
    offline = _as_bool(os.getenv("PIXELPILOT_OFFLINE"), default=True)
    transport = os.getenv("PIXELPILOT_TRANSPORT", "stdio").strip() or "stdio"
    services = OfflineServiceConfig(
        stt_command=os.getenv("PIXELPILOT_STT_CMD", "whisper.cpp --stdin").strip(),
        llm_command=os.getenv("PIXELPILOT_LLM_CMD", "llama.cpp --prompt-file -").strip(),
        tts_command=os.getenv("PIXELPILOT_TTS_CMD", "piper --output-raw").strip(),
    )
    return BotPipelineConfig(offline=offline, transport=transport, services=services)


def build_offline_pipeline(config: BotPipelineConfig) -> PipelineBlueprint:
    if not config.offline:
        raise ValueError("PixelPilot currently supports only fully offline local setup.")

    if config.transport != "stdio":
        raise ValueError("Only 'stdio' transport is supported in this initial offline setup.")

    return PipelineBlueprint(
        stages=(
            PipelineStage("transport", config.transport),
            PipelineStage("stt", config.services.stt_command),
            PipelineStage("llm", config.services.llm_command),
            PipelineStage("tts", config.services.tts_command),
            PipelineStage("output", "local-speaker-or-stream"),
        )
    )


def run() -> PipelineBlueprint:
    config = load_config_from_env()
    blueprint = build_offline_pipeline(config)
    print("PixelPilot offline pipeline configured:")
    for stage in blueprint.stages:
        print(f"- {stage.name}: {stage.detail}")
    return blueprint


if __name__ == "__main__":
    run()
