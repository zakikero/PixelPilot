# Development setup

## Prerequisites

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

## Install the project

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

## Set up Ollama

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

## Whisper hardware configuration

The last runtime review found a CUDA initialization failure and an invalid
Whisper language setting. See [FAILSAFE.md](FAILSAFE.md) for the observed errors
and recommended fixes. The installation guidance below should be checked
against the target machine's driver and CUDA requirements.

### CUDA GPU support

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

The command must print at least `1`. If `nvidia-smi` fails, follow the GPU
diagnostics in [FAILSAFE.md](FAILSAFE.md) to check driver exposure before
changing the Windows driver. If the CUDA count is zero or the bot reports a
missing `libcublas.so` or `libcudnn.so`, use the CPU configuration below.

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

## Run the voice bot

Start Ollama in a separate terminal if it is not already running:

```bash
ollama serve
```

From the `bot` directory, select a transport:

| Command | Audio devices |
| --- | --- |
| `uv run bot.py` | Browser over SmallWebRTC (default) |
| `uv run bot.py -t webrtc` | Browser over SmallWebRTC (explicit) |
| `uv run bot.py -t local` | Host microphone and speakers |

Both transports use the same Whisper → Ollama → Kokoro pipeline. Stop the
running bot before starting it in the other mode.

For WebRTC, open **http://localhost:7860/client/**, connect, and allow microphone
access. Select audio devices in the browser; the `audio` indexes in
`config.yaml` are used only in local mode. A Windows browser can provide the
audio while the bot runs in WSL.

Each WebRTC connection creates a fresh conversation and loads its own models.
Use one browser session at a time on a laptop. Disconnecting stops that session
while leaving the HTTP server available for a new connection.

For local audio, inspect the host's devices first:

```bash
uv run audio_devices.py
```

Set `audio.input_device_index` and `audio.output_device_index` in
[config.yaml](../bot/config.yaml) before running `uv run bot.py -t local`.

With the default wake configuration, say **"hey pixel"** followed by your
question. Set `wake.enabled: false` to converse without the wake phrase.

To change the WebRTC HTTP port:

```bash
uv run bot.py --port 7861
```

## Connecting a launcher or another client

The Pipecat runner provides signaling and the test UI. A custom Pipecat client
should use `@pipecat-ai/small-webrtc-transport`, paired with this server's
SmallWebRTC transport. The endpoints are:

| Endpoint | Purpose |
| --- | --- |
| `GET /client/` | Prebuilt browser voice client |
| `GET /status` | HTTP availability and selected transport; model readiness is not checked |
| `POST /start` | Start a WebRTC session (`{"transport": "webrtc"}`) |
| `POST /api/offer` | Exchange the SDP offer and answer |
| `PATCH /api/offer` | Send additional ICE candidates |

For local development, serve your client and bot from localhost. For a client
on another machine, the browser page needs HTTPS for microphone access, and
both peers need a reachable media path. An HTTP tunnel alone does not carry
the WebRTC media. In WSL, localhost HTTP forwarding also does not guarantee
UDP/ICE reachability from another machine.

The runner accepts STUN/TURN configuration through `--ice-servers` or the
`PIPECAT_ICE_SERVERS` environment variable; see
[`.env.example`](../bot/.env.example). STUN helps discover a public address;
TURN relays media when direct connections fail.
Bind with `--host 0.0.0.0` only when you intend to allow remote access. The
development runner is not an authenticated public deployment.

## Verify a conversation

1. Start Ollama, then run `uv run bot.py` (WebRTC is the default).
2. Open `/client/`, connect, and grant microphone access.
3. Say "hey pixel, introduce yourself". Check the transcript and listen for a
   Kokoro reply through the browser.
4. Disconnect. The terminal should report that the conversation is stopping.
5. Reconnect and ask another question to check that a fresh session works.

For the transport-selection and startup-failure regression tests:

```bash
uv run python -m unittest discover -s tests -v
```

## Pipecat Context Hub (optional)

Context Hub gives coding agents searchable Pipecat documentation and examples.
It is a developer tool and is not installed by `uv sync`:

```bash
uv tool install "pipecat-ai[cli]"
pipecat context-hub install
pipecat context-hub refresh --framework-version latest
```

Restart VS Code after installation so the MCP server is loaded.

## References

- [Pipecat documentation](https://docs.pipecat.ai/)
- [Pipecat examples](https://github.com/pipecat-ai/pipecat-examples)
