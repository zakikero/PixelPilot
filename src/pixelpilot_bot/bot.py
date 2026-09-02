from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

DEFAULT_TRANSPORT = "stdio"
DEFAULT_STT_COMMAND = "whisper.cpp --stdin"
DEFAULT_LLM_COMMAND = "llama.cpp --prompt-file -"
DEFAULT_TTS_COMMAND = "piper --output-raw"


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


def create_default_config() -> BotPipelineConfig:
    services = OfflineServiceConfig(
        stt_command=DEFAULT_STT_COMMAND,
        llm_command=DEFAULT_LLM_COMMAND,
        tts_command=DEFAULT_TTS_COMMAND,
    )
    return BotPipelineConfig(offline=True, transport=DEFAULT_TRANSPORT, services=services)


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
    config = create_default_config()
    blueprint = build_offline_pipeline(config)
    print("PixelPilot offline pipeline configured:")
    for stage in blueprint.stages:
        print(f"- {stage.name}: {stage.detail}")
    return blueprint

