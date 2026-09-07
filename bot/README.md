# PixelPilot voice bot

A local Pipecat voice agent built with a cascade pipeline (STT -> LLM -> TTS).
It uses Whisper for speech recognition, Ollama for the language model, and
Piper for speech synthesis. No cloud API keys are required.

## Configuration

- **Bot Type**: Local audio
- **Transport**: Local microphone and speakers
- **Pipeline**: Cascade
   - **STT**: Whisper
   - **LLM**: Ollama
   - **TTS**: Piper

## Setup

1. **Navigate to the bot directory**:

   ```bash
   cd bot
   ```

2. **Install dependencies**:

   ```bash
   uv sync
   ```

3. **Configure environment variables**:

   ```bash
   cp .env.example .env
   ```

   Edit `config.yaml` for non-secret settings such as the Whisper model,
   CPU/CUDA mode, Ollama model, and audio input device. Keep `.env` for
   optional secrets or environment-specific overrides.

   The default values use a tiny Whisper model, the Amy Piper voice, and the
   `llama3` Ollama model. Start Ollama separately and pull the model:

   ```bash
   ollama pull llama3
   ```

4. **Run the bot**:

   ```bash
   uv run bot.py
   ```

   The bot listens to the local microphone and plays responses through the
   default audio output device.

## Project Structure

```
PixelPilot/
├── bot/                 # Local voice bot
│   ├── bot.py           # Main bot implementation
│   ├── pyproject.toml   # Python dependencies
│   ├── .env.example     # Local configuration template
│   ├── .env             # Local configuration (git-ignored)
│   └── whisperLiveTest.py # Standalone Whisper microphone test
├── main.py              # Root placeholder entry point
├── .gitignore           # Git ignore patterns
└── README.md            # Project overview
```

## Building with an AI coding agent

Extending this bot with Claude Code, Codex, or another AI coding assistant? Give it live, accurate Pipecat context instead of stale training data with the **Pipecat Context Hub** — a local index of Pipecat docs, examples, and API source your agent queries over MCP:

```bash
# The Context Hub ships with the CLI
uv tool install "pipecat-ai[cli]"
pipecat context-hub install
```

`install` registers the MCP server with each coding agent it finds and builds the index — a few minutes and about 900 MB the first time. MCP servers load at session start, so do this before opening your coding session, and note the server won't start against an empty index. See the [Pipecat Context Hub docs](https://docs.pipecat.ai/api-reference/context-hub) for the full setup.

## Learn More

- [Pipecat Documentation](https://docs.pipecat.ai/)
- [Pipecat GitHub](https://github.com/pipecat-ai/pipecat)
- [Pipecat Examples](https://github.com/pipecat-ai/pipecat-examples)
- [Discord Community](https://discord.gg/pipecat)