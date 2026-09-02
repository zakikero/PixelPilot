import unittest

from pixelpilot_bot.main import BotPipelineConfig, OfflineServiceConfig, build_offline_pipeline, create_default_config


class OfflinePipelineTests(unittest.TestCase):
    def test_default_config_builds_expected_stage_order(self) -> None:
        config = create_default_config()
        blueprint = build_offline_pipeline(config)
        stage_names = [stage.name for stage in blueprint.stages]
        self.assertEqual(stage_names, ["transport", "stt", "llm", "tts", "output"])

    def test_rejects_non_offline_mode(self) -> None:
        config = BotPipelineConfig(
            offline=False,
            transport="stdio",
            services=OfflineServiceConfig(
                stt_command="whisper.cpp --stdin",
                llm_command="llama.cpp --prompt-file -",
                tts_command="piper --output-raw",
            ),
        )
        with self.assertRaises(ValueError):
            build_offline_pipeline(config)

    def test_accepts_code_defined_local_commands(self) -> None:
        config = BotPipelineConfig(
            offline=True,
            transport="stdio",
            services=OfflineServiceConfig(
                stt_command="/opt/stt --offline",
                llm_command="/opt/llm --local",
                tts_command="/opt/tts --offline",
            ),
        )
        blueprint = build_offline_pipeline(config)
        details = [stage.detail for stage in blueprint.stages]
        self.assertIn("/opt/stt --offline", details)
        self.assertIn("/opt/llm --local", details)
        self.assertIn("/opt/tts --offline", details)


if __name__ == "__main__":
    unittest.main()
