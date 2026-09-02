# PixelPilot
A conversational AI designed as an integrated arcade assistant transforms the solitary nostalgia of retro gaming into a dynamic, two-player experience. Positioned either within the physical cabinet, the AI functions as a real-time copilot, strategy advisor, and interactive character tailored to the coin-op atmosphere.

## Offline Python bot scaffold

This repository now includes a minimal Python scaffold for a fully offline, local-first Pipecat-style bot pipeline.

### Quick start

1. (Optional) Update local service command constants in:
   - `src/pixelpilot_bot/main.py`
2. Run:
   - `PYTHONPATH=src python -m pixelpilot_bot`

### What is included

- `src/pixelpilot_bot/main.py`:
  - Uses code-defined offline local config (no environment variables required)
  - Validates offline-only mode
  - Builds a pipeline blueprint (`transport -> stt -> llm -> tts -> output`)
- `tests/test_offline_pipeline.py`:
  - Focused tests for config and pipeline blueprint behavior
