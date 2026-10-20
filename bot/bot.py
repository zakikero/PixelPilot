#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Start PixelPilot with browser WebRTC (default) or local microphone audio."""

import argparse
import asyncio
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from loguru import logger
from pipecat.runner.types import RunnerArguments, SmallWebRTCRunnerArguments

from voice_pipeline import run_bot

BOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BOT_DIR / "config.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    """Read model, voice, wake phrase, and device settings for a session."""
    with path.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    if not isinstance(config, dict):
        raise ValueError(f"{path} must contain a YAML mapping.")
    return config


def configure_logging(config: dict[str, Any]) -> None:
    """Use the configured level, with LOG_LEVEL as an environment override."""
    level = os.getenv("LOG_LEVEL", config["logging"]["level"]).upper()
    logger.remove()
    logger.add(sys.stderr, level=level)


@contextmanager
def _quiet_audio_probe():
    """Quiet successful Linux device discovery; replay diagnostics on failure."""
    if sys.platform != "linux":
        yield
        return
    with tempfile.TemporaryFile() as messages:
        original_stderr = os.dup(2)
        try:
            os.dup2(messages.fileno(), 2)
            yield
        except BaseException:
            os.dup2(original_stderr, 2)
            messages.seek(0)
            sys.stderr.write(messages.read().decode(errors="replace"))
            raise
        finally:
            os.dup2(original_stderr, 2)
            os.close(original_stderr)


async def bot(runner_args: RunnerArguments) -> None:
    """Handle one WebRTC session started by Pipecat's development runner."""
    from pipecat.transports.base_transport import TransportParams
    from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

    if not isinstance(runner_args, SmallWebRTCRunnerArguments):
        raise ValueError("PixelPilot supports WebRTC and local audio only.")

    try:
        config = load_config()
        configure_logging(config)
        transport = SmallWebRTCTransport(
            webrtc_connection=runner_args.webrtc_connection,
            params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
        )
        await run_bot(transport, runner_args, config)
    finally:
        # A failed model startup must also release the negotiated peer.
        await runner_args.webrtc_connection.disconnect()


async def run_local_bot() -> None:
    """Use the host devices and RNNoise with the same conversation pipeline."""
    from pipecat.audio.filters.rnnoise_filter import RNNoiseFilter
    from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams

    config = load_config()
    configure_logging(config)
    with _quiet_audio_probe():
        transport = LocalAudioTransport(
            LocalAudioTransportParams(
                audio_in_enabled=True,
                audio_in_filter=RNNoiseFilter(),
                audio_out_enabled=True,
                input_device_index=config["audio"]["input_device_index"],
                output_device_index=config["audio"]["output_device_index"],
            )
        )
    runner_args = RunnerArguments()
    runner_args.handle_sigint = True
    runner_args.handle_sigterm = True
    await run_bot(transport, runner_args, config)


def main() -> None:
    """Select the audio transport and forward WebRTC server options."""
    parser = argparse.ArgumentParser(
        description="PixelPilot voice bot",
        epilog="WebRTC accepts --host, --port, --ice-servers and --allowed-origins.",
    )
    parser.add_argument(
        "-t",
        "--transport",
        choices=["webrtc", "local"],
        default="webrtc",
        help="Audio transport (default: webrtc)",
    )
    args, runner_options = parser.parse_known_args()
    load_dotenv(BOT_DIR / ".env", override=True)

    if args.transport == "local":
        if runner_options:
            parser.error(f"Local audio does not accept server options: {' '.join(runner_options)}")
        asyncio.run(run_local_bot())
        return

    from pipecat.runner.run import main as runner_main

    original_argv = sys.argv
    try:
        sys.argv = [sys.argv[0], "-t", "webrtc", *runner_options]
        runner_main()
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    main()
