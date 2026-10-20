# PixelPilot

PixelPilot is a local voice assistant for an arcade cabinet. It uses Pipecat
with Whisper for speech recognition, Ollama for the language model, and Kokoro
for spoken responses. SmallWebRTC provides browser audio by default; local
microphone and speaker audio is also supported.

## Quick start

Install Python 3.11 or newer, [uv](https://docs.astral.sh/uv/), and
[Ollama](https://ollama.com/download). See [setup instructions](docs/SETUP.md)
for system dependencies and GPU configuration.

Start Ollama in a separate terminal with `ollama serve` if it is not already
running. From the repository root:

```bash
cd bot
uv sync
cp .env.example .env
ollama pull llama3.2:3b
```

Edit [bot/config.yaml](bot/config.yaml) for your models, Whisper CPU/CUDA mode,
language, and wake phrase. See [FAILSAFE.md](docs/FAILSAFE.md) for known startup
issues and proposed fixes. Keep optional secrets and environment overrides in
`bot/.env`.

## Run

From `bot/`:

```bash
uv run bot.py             # WebRTC (default)
uv run bot.py -t local    # Host microphone and speakers
```

For WebRTC, open **http://localhost:7860/client/**, connect, and allow microphone
access. Use a wake phrase from `bot/config.yaml` followed by your question.
Use one browser session at a time on a laptop.

For local audio, run `uv run audio_devices.py` and set the matching device
indexes in `bot/config.yaml`. Stop the bot before switching transports.

[bot/bot.py](bot/bot.py) handles configuration, startup, and the two audio
transports. [bot/voice_pipeline.py](bot/voice_pipeline.py) builds and runs the
shared conversation pipeline.

## Documentation

- [Setup](docs/SETUP.md) — installation, hardware, transport integration, and verification.
- [Performance](docs/PERFORMANCE.md) — latency measurements and optimization ideas.
- [Failsafe](docs/FAILSAFE.md) — observed errors and proposed recovery behavior.
- [TODO](docs/TODO.md) — planned and completed work.

## Tests

From `bot/`:

```bash
uv run python -m unittest discover -s tests -v
```
