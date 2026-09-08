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
sudo apt install -y build-essential python3-dev portaudio19-dev libsndfile1 ffmpeg
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

`uv sync` installs every Python requirement declared in `bot/pyproject.toml`,
including Pipecat, faster-whisper, PyAudio, sounddevice, Kokoro, Ollama
support, and the local audio transport. Run the remaining commands from the
`bot` directory.

Non-secret settings such as model names, audio device selection, and CUDA/CPU
mode are stored in `bot/config.yaml`. Edit that file when changing the local
setup. The `.env` file is reserved for optional environment-specific overrides
and secrets.

The default environment uses Whisper, Kokoro's `af_heart` voice, and the local
Ollama `llama3.1:8b` model.

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

#### CUDA GPU support for Whisper

The current `config.yaml` selects CUDA. CUDA on WSL requires an NVIDIA driver
installed on Windows with WSL support; the driver is not installed by `uv`.
First check that the GPU is visible inside WSL:

```bash
nvidia-smi
```

Install the CUDA libraries used by `faster-whisper` into the project
environment. These packages are for CUDA 12, which is the runtime expected by
the current `ctranslate2` dependency:

```bash
uv pip install "nvidia-cublas-cu12" "nvidia-cudnn-cu12==9.*"
```

Expose those libraries to the current shell and verify CUDA through
`ctranslate2`:

```bash
CUDA_LIB_DIRS="$(find "$PWD/.venv/lib" -type d \( -path '*/nvidia/cublas/lib' -o -path '*/nvidia/cudnn/lib' \) -print | paste -sd:)"
export LD_LIBRARY_PATH="${CUDA_LIB_DIRS}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
uv run python -c "import ctranslate2; print(ctranslate2.get_cuda_device_count())"
```

The command must print at least `1`. If `nvidia-smi` fails, install or update
the Windows NVIDIA driver first. If the CUDA count is zero or the bot reports
a missing `libcublas.so` or `libcudnn.so`, use the CPU configuration below.

After installing the matching libraries, configure `bot/config.yaml`:

```yaml
whisper:
  device: cuda
  compute_type: float16
```

If the required CUDA libraries are unavailable, set these values to
`device: cpu` and `compute_type: int8` in `config.yaml`.

Download the configured Whisper model before the first conversation:

```bash
uv run python -c "from faster_whisper import WhisperModel; WhisperModel('large-v3-turbo', device='cuda', compute_type='float16')"
```

For CPU mode, change `device='cuda'` to `device='cpu'` and
`compute_type='float16'` to `compute_type='int8'` in that command.

The model is cached after this command. Kokoro downloads its voice model on
first use.

### Run the voice bot

Before starting, check the local audio devices:

```bash
uv run audio_devices.py
```

Set the matching input and output indexes in `config.yaml`, then start the
Ollama server and bot:

```bash
ollama serve
```

In another terminal, still inside `bot`:

```bash
ollama pull llama3.1:8b
uv run bot.py
```

Speak into the configured microphone. Kokoro produces the spoken response
through the configured local output device.

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
