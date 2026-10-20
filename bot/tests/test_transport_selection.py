"""Transport CLI contracts without loading models or opening audio devices."""

import contextlib
import io
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pipecat.runner.types import SmallWebRTCRunnerArguments

import bot


class TransportSelectionTests(unittest.TestCase):
    def test_default_is_webrtc_and_runner_options_are_forwarded(self):
        argv = ["bot.py", "--host", "127.0.0.1", "--port", "7861"]
        seen = []
        with (
            patch.object(sys, "argv", argv),
            patch("pipecat.runner.run.main", side_effect=lambda: seen.append(sys.argv.copy())),
            patch.object(bot, "run_local_bot", new_callable=AsyncMock) as local,
        ):
            bot.main()
            self.assertIs(sys.argv, argv)

        self.assertEqual(
            seen,
            [["bot.py", "-t", "webrtc", "--host", "127.0.0.1", "--port", "7861"]],
        )
        local.assert_not_awaited()

    def test_explicit_webrtc_accepts_both_flag_spellings(self):
        for option in [["-t", "webrtc"], ["--transport=webrtc"]]:
            with (
                self.subTest(option=option),
                patch.object(sys, "argv", ["bot.py", *option]),
                patch("pipecat.runner.run.main") as runner,
            ):
                bot.main()
                runner.assert_called_once_with()

    def test_local_uses_shared_pipeline_without_starting_web_server(self):
        transport = object()
        config = bot.load_config()
        with (
            patch.object(sys, "argv", ["bot.py", "-t", "local"]),
            patch.object(bot, "load_config", return_value=config),
            patch.object(bot, "configure_logging"),
            patch(
                "pipecat.transports.local.audio.LocalAudioTransport", return_value=transport
            ) as local_transport,
            patch.object(bot, "run_bot", new_callable=AsyncMock) as run_bot,
            patch("pipecat.runner.run.main") as runner,
        ):
            bot.main()

        runner.assert_not_called()
        run_bot.assert_awaited_once()
        await_args = run_bot.await_args
        assert await_args is not None
        actual_transport, runner_args, actual_config = await_args.args
        self.assertIs(actual_transport, transport)
        self.assertIs(actual_config, config)
        self.assertTrue(runner_args.handle_sigint)
        self.assertTrue(runner_args.handle_sigterm)
        params = local_transport.call_args.args[0]
        self.assertEqual(params.input_device_index, config["audio"]["input_device_index"])
        self.assertEqual(params.output_device_index, config["audio"]["output_device_index"])
        self.assertIsNotNone(params.audio_in_filter)

    def test_local_rejects_server_options(self):
        with (
            patch.object(sys, "argv", ["bot.py", "-t", "local", "--port", "7861"]),
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as error,
        ):
            bot.main()
        self.assertEqual(error.exception.code, 2)

    def test_unsupported_transport_fails_before_starting_services(self):
        with (
            patch.object(sys, "argv", ["bot.py", "-t", "daily"]),
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as error,
        ):
            bot.main()
        self.assertEqual(error.exception.code, 2)


class WebRTCLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_startup_failure_closes_the_peer(self):
        connection = SimpleNamespace(disconnect=AsyncMock())
        args = SmallWebRTCRunnerArguments(webrtc_connection=connection)
        with (
            patch("pipecat.transports.smallwebrtc.transport.SmallWebRTCTransport"),
            patch.object(bot, "configure_logging"),
            patch.object(bot, "run_bot", new_callable=AsyncMock, side_effect=RuntimeError("model")),
            self.assertRaisesRegex(RuntimeError, "model"),
        ):
            await bot.bot(args)
        connection.disconnect.assert_awaited_once()

    async def test_configuration_failure_also_closes_the_peer(self):
        connection = SimpleNamespace(disconnect=AsyncMock())
        args = SmallWebRTCRunnerArguments(webrtc_connection=connection)
        with (
            patch.object(bot, "load_config", side_effect=ValueError("configuration")),
            self.assertRaisesRegex(ValueError, "configuration"),
        ):
            await bot.bot(args)
        connection.disconnect.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
