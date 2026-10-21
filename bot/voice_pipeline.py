#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Shared Whisper → Ollama → Kokoro conversation pipeline."""

from typing import Any

from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.observers.loggers.llm_log_observer import LLMLogObserver
from pipecat.observers.loggers.transcription_log_observer import TranscriptionLogObserver
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.runner.types import RunnerArguments, SmallWebRTCRunnerArguments
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.services.ollama.llm import OLLamaLLMService
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.transports.base_transport import BaseTransport
from pipecat.turns.user_start import WakePhraseUserTurnStartStrategy
from pipecat.turns.user_turn_strategies import (
    UserTurnStrategies,
    default_user_turn_start_strategies,
)
from pipecat.workers.runner import WorkerRunner


def create_pipeline(transport: BaseTransport, config: dict[str, Any]) -> Pipeline:
    """Create independent services, turn handling, and conversation context."""
    whisper = config["whisper"]
    ollama = config["ollama"]
    kokoro = config["kokoro"]

    stt = WhisperSTTService(
        settings=WhisperSTTService.Settings(
            model=whisper["model"],
            language=whisper["language"],
        ),
        device=whisper["device"],
        compute_type=whisper["compute_type"],
    )
    llm = OLLamaLLMService(
        base_url=ollama["host"],
        settings=OLLamaLLMService.Settings(
            model=ollama["model"],
            system_instruction=ollama["system_instruction"],
            temperature=ollama["temperature"],
        ),
    )
    tts = KokoroTTSService(
        settings=KokoroTTSService.Settings(
            voice=kokoro["voice"],
            language=kokoro["language"],
            speed=kokoro["speed"],
        ),
    )

    start_strategies = default_user_turn_start_strategies()
    wake = config.get("wake", {})
    if wake.get("enabled", False):
        wake_strategy = WakePhraseUserTurnStartStrategy(
            phrases=wake["phrases"],
            timeout=wake["timeout"],
        )
        start_strategies.insert(0, wake_strategy)

        @wake_strategy.event_handler("on_wake_phrase_detected")
        async def on_wake_phrase_detected(strategy, phrase):
            logger.info("Wake phrase detected: {}", phrase)

        @wake_strategy.event_handler("on_wake_phrase_timeout")
        async def on_wake_phrase_timeout(strategy):
            logger.info("Wake phrase timed out — returning to idle")

    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        LLMContext(),
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(),
            user_turn_strategies=UserTurnStrategies(start=start_strategies),
        ),
    )

    return Pipeline(
        [
            transport.input(),
            # Segmented Whisper needs speech boundaries before transcription.
            VADProcessor(vad_analyzer=SileroVADAnalyzer()),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )


async def run_bot(
    transport: BaseTransport, runner_args: RunnerArguments, config: dict[str, Any]
) -> None:
    """Run one conversation until it ends, fails, or the client disconnects."""
    logger.info("Starting conversation")
    worker = PipelineWorker(
        create_pipeline(transport, config),
        params=PipelineParams(),
        observers=[TranscriptionLogObserver(), LLMLogObserver()],
        idle_timeout_secs=None,
        processor_unusable_policy=ProcessorUnusablePolicy.END,
    )
    runner = WorkerRunner(
        handle_sigint=runner_args.handle_sigint,
        handle_sigterm=runner_args.handle_sigterm,
    )

    @worker.event_handler("on_pipeline_started")
    async def on_pipeline_started(worker, frame):
        logger.info("Pipeline is ready")

    @worker.event_handler("on_pipeline_finished")
    async def on_pipeline_finished(worker, frame):
        logger.info("Pipeline stopped")

    @worker.event_handler("on_pipeline_error")
    async def on_pipeline_error(worker, frame):
        logger.error("Pipeline error: {}", frame)

    @worker.event_handler("on_idle_timeout")
    async def on_idle_timeout(worker):
        logger.info("Pipeline reached its inactivity timeout")

    if isinstance(runner_args, SmallWebRTCRunnerArguments):

        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            logger.info("WebRTC client connected")

        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            logger.info("WebRTC client disconnected")
            await runner.cancel()

    await runner.add_workers(worker)
    await runner.run()
