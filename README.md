# PixelPilot

A conversational AI designed as an integrated arcade assistant transforms the solitary nostalgia of retro gaming into a dynamic, two-player experience. Positioned either within the physical cabinet, the AI functions as a real-time copilot, strategy advisor, and interactive character tailored to the coin-op atmosphere.

Current development work is tracked in [TODO.md](TODO.md).

## Development Setup

### Prerequisites

- Python 3.11 or newer
- A microphone and audio output device
- [Ollama](https://ollama.com/download) installed locally
- `uv` installed:

For the local audio setup on Ubuntu or Debian:

```bash
sudo apt update
sudo apt install -y build-essential python3-dev portaudio19-dev
```

Linux and macOS:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart the terminal after installation and verify the tools:

```bash
uv --version
python --version
ollama --version
```

### Install the project

From the repository root:

```bash
cd bot
uv sync
cp .env.example .env
```

Non-secret settings such as model names, audio device selection, and CUDA/CPU
mode are stored in `bot/config.yaml`. Edit that file when changing the local
setup. The `.env` file is reserved for optional environment-specific overrides
and secrets.

The default environment uses Whisper, Piper's `en_US-amy-medium` voice, and
the local Ollama `llama3.1:8b` model.

### Set up Ollama

Install Ollama on the machine that will host the language model. On Linux or
WSL, install it with:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Start the Ollama server in its own terminal:

```bash
ollama serve
```

In another terminal, download the model configured in `bot/config.yaml`:

```bash
ollama pull llama3.1:8b
```

Verify that the server is responding and the model is available:

```bash
curl http://localhost:11434/api/tags
ollama list
```

The bot connects to Ollama at `http://localhost:11434/v1`, as configured in
`bot/config.yaml`. If Ollama runs on another machine, change the `ollama.host`
value to that machine's reachable Ollama URL. The Ollama server must be
configured to listen on an address reachable by the bot.

The Pipecat pipeline already uses `OLLamaLLMService` after the user aggregator,
so no CLI flag is needed. Start the bot from a third terminal:

```bash
cd bot
uv run bot.py
```

Speak into the microphone and watch the terminal for transcription and LLM log
output. Piper is currently disabled in `bot.py`; enable the `PiperTTSService`
and add `tts` to the pipeline if you also want the response spoken aloud.

#### Optional CUDA GPU support

Whisper runs on the CPU by default. To use an NVIDIA GPU, install a compatible
NVIDIA driver on the host and the CUDA runtime libraries inside the environment,
including the cuBLAS library required by `faster-whisper`. The cuBLAS version
must match the CUDA runtime expected by your installed `ctranslate2` package.
For example, an error mentioning `libcublas.so.12` requires the CUDA 12 cuBLAS
runtime; installing a CUDA 13 library will not satisfy it.

After installing the matching libraries, configure `bot/config.yaml`:

```yaml
whisper:
	device: cuda
	compute_type: float16
```

If the required CUDA libraries are unavailable, set these values to
`device: cpu` and `compute_type: int8` in `config.yaml`.

### Run the voice bot

Speak into the configured microphone. The bot logs transcriptions and Ollama
responses in the terminal. Piper must be enabled in `bot.py` before responses
are played through the default audio output device.

### Pipecat Context Hub (optional)

Context Hub gives coding agents searchable Pipecat documentation and examples.
It is a developer tool and is not installed by `uv sync`:

```bash
uv tool install "pipecat-ai[cli]"
pipecat context-hub install
pipecat context-hub refresh --framework-version latest
```

Restart VS Code after installation so the MCP server is loaded.

## Project Structure

```text
PixelPilot/
├── bot/                 # Local Pipecat voice bot
│   ├── bot.py           # Main bot implementation
│   ├── pyproject.toml   # Python dependencies and tooling
│   ├── .env.example     # Local configuration template
│   └── whisperLiveTest.py # Standalone Whisper microphone test
├── main.py              # Root placeholder entry point
└── README.md
```
