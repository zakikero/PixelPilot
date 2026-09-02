import os
import unittest
from unittest.mock import patch

from pixelpilot_bot.main import build_offline_pipeline, load_config_from_env


class OfflinePipelineTests(unittest.TestCase):
    def test_default_env_builds_expected_stage_order(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = load_config_from_env()
        blueprint = build_offline_pipeline(config)
        stage_names = [stage.name for stage in blueprint.stages]
        self.assertEqual(stage_names, ["transport", "stt", "llm", "tts", "output"])

    def test_rejects_non_offline_mode(self) -> None:
        with patch.dict(os.environ, {"PIXELPILOT_OFFLINE": "false"}, clear=True):
            config = load_config_from_env()
        with self.assertRaises(ValueError):
            build_offline_pipeline(config)

    def test_accepts_custom_local_commands(self) -> None:
        custom_env = {
            "PIXELPILOT_OFFLINE": "true",
            "PIXELPILOT_TRANSPORT": "stdio",
            "PIXELPILOT_STT_CMD": "/opt/stt --offline",
            "PIXELPILOT_LLM_CMD": "/opt/llm --local",
            "PIXELPILOT_TTS_CMD": "/opt/tts --offline",
        }
        with patch.dict(os.environ, custom_env, clear=True):
            config = load_config_from_env()
        blueprint = build_offline_pipeline(config)
        details = [stage.detail for stage in blueprint.stages]
        self.assertIn("/opt/stt --offline", details)
        self.assertIn("/opt/llm --local", details)
        self.assertIn("/opt/tts --offline", details)


if __name__ == "__main__":
    unittest.main()
