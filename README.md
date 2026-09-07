# PixelPilot

A conversational AI designed as an integrated arcade assistant transforms the solitary nostalgia of retro gaming into a dynamic, two-player experience. Positioned either within the physical cabinet, the AI functions as a real-time copilot, strategy advisor, and interactive character tailored to the coin-op atmosphere.

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

The default environment uses Whisper on the CPU, Piper's `en_US-amy-medium`
voice, and the local Ollama `llama3` model. Download the model before starting:

```bash
ollama pull llama3
```

#### Optional CUDA GPU support

Whisper runs on the CPU by default. To use an NVIDIA GPU, install a compatible
NVIDIA driver on the host and the CUDA runtime libraries inside the environment,
including the cuBLAS library required by `faster-whisper`. The cuBLAS version
must match the CUDA runtime expected by your installed `ctranslate2` package.
For example, an error mentioning `libcublas.so.12` requires the CUDA 12 cuBLAS
runtime; installing a CUDA 13 library will not satisfy it.

After installing the matching libraries, configure `bot/.env`:

```env
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```

If the required CUDA libraries are unavailable, leave these values set to
`WHISPER_DEVICE=cpu` and `WHISPER_COMPUTE_TYPE=int8`.

### Run the voice bot

Make sure Ollama is running, then start the local audio transport:

```bash
ollama serve
```

In a second terminal:

```bash
cd bot
uv run bot.py
```

Speak into the configured microphone. The bot plays its responses through the
default audio output device.

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
