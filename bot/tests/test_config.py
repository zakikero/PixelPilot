"""Load settings without starting models, audio devices, or a web server."""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bot


class ConfigTests(unittest.TestCase):
    def test_whisper_automatic_language_is_none(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text("whisper:\n  language: null\n", encoding="utf-8")
            config = bot.load_config(path)
        self.assertIsNone(config["whisper"]["language"])

    def test_invalid_root_is_rejected_with_the_file_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text("- invalid\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "config.yaml must contain a YAML mapping"):
                bot.load_config(path)

    def test_help_does_not_load_the_configuration(self):
        with (
            patch.object(sys, "argv", ["bot.py", "--help"]),
            patch.object(bot, "load_config", side_effect=AssertionError("unexpected config read")),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as result,
        ):
            bot.main()
        self.assertEqual(result.exception.code, 0)
