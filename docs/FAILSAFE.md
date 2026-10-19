# PixelPilot failsafe and recovery plan

Reviewed 2026-10-19 against the installed Pipecat **1.12.0**, Python 3.14.4,
faster-whisper 1.2.1, CTranslate2 4.8.3, and the actual project sources.
This document records observed failures and proposed reliability changes.
The recovery policies below are recommendations; they have not been implemented
as part of this review.

## What the single launch established

I launched the saved bot configuration once, using its default WebRTC mode on
localhost port 7862, and connected one real aiortc audio/data-channel peer.
No model settings were overridden. The temporary server was stopped afterward.

| Boundary | Result |
| --- | --- |
| HTTP server and prebuilt browser client | Started; `/client/` returned 200 |
| SDP offer/answer endpoint | `/api/offer` returned 200 |
| Whisper initialization | Failed with a CUDA runtime/driver error |
| Voice-session readiness | No RTVI `bot-ready` message |
| HTTP server after session failure | Still running; `/status` still returned `ready` |

This was a voice-session initialization failure, not an observed process crash.
The final process termination was requested by the probe, not spontaneous.
Ollama inference, Kokoro synthesis, microphone quality, and runtime retry
behavior could not be exercised in this launch because Whisper failed first.

The run produced `pixelpilot-reliability-run.log` and
`pixelpilot-reliability-run.json` under `/tmp`. Those are temporary diagnostic
artifacts outside the repository; the relevant results and errors are preserved
in this document.

## Messages observed and recommended fixes

### 1. CUDA model initialization is the blocking error

The log ends the startup traceback with:

```text
RuntimeError: CUDA failed with error CUDA driver version is insufficient for CUDA runtime version
```

This occurs in `WhisperSTTService` construction, before `PipelineWorker` and
its `on_pipeline_error` handler exist. Retrying the same initialization will
not repair the environment.

The probe can see `/dev/dxg`, but cannot load `libcuda.so.1` through the loader
or `/usr/lib/wsl/lib/libcuda.so.1`. No `nvidia-smi` executable was found in the
standard locations checked. Therefore an outdated Windows driver has **not**
been established: GPU driver exposure to this execution environment is also
in question.

In your normal WSL terminal, check:

```bash
nvidia-smi
ls -l /usr/lib/wsl/lib/libcuda.so*
```

If GPU access works there, compare that terminal's environment with the bot's
launch environment. If access is absent there as well, check the Windows NVIDIA
driver and WSL integration. NVIDIA documents that WSL receives `libcuda.so`
from the Windows driver; installing a Linux GPU driver inside WSL is not the
appropriate repair. See [NVIDIA's WSL CUDA guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html).

A practical CPU alternative is the following proposed configuration, using a
smaller Whisper model already cached here:

```yaml
whisper:
  model: base
  device: cpu
  compute_type: int8
  language: null
```

This is a recommendation, not a change made during this review. CPU INT8 is a
supported inference configuration; it changes performance and may warrant a
smaller model. See [Faster Whisper's usage guide](https://github.com/SYSTRAN/faster-whisper#usage).

### 2. `language: None` is an invalid configuration value

The log reports at DEBUG level that the string `None` is not a recognized
language code. YAML loads `None` as a string, not Python's `None`.

Change [config.yaml](../bot/config.yaml)
to `language: null` for automatic detection, or `language: en` for English.
The installed Whisper service checks supported languages after loading its
model, so this is another startup problem currently hidden behind the CUDA
failure. Automatic detection accepts actual `None`; see the
[Whisper service documentation](https://docs.pipecat.ai/api-reference/server/services/stt/whisper).

### 3. The ICE exception is a secondary cleanup race

Both the server and probe logged an unhandled aiortc task exception containing
`RTCIceTransport is closed`. Based on the timing and cleanup path, a failed
model initialization closes the peer while ICE connection work is still in
flight. This does not establish that STUN, TURN, or the network is misconfigured.

Validate model startup before accepting offers. Also report initialization
failure to the session owner and test cancellation during negotiation. Keep
the peer cleanup; do not simply hide the exception or leave failed peers open.
After the primary error is fixed, check whether the ICE race still occurs
before deciding that an aiortc/Pipecat dependency change is needed.

### 4. One leaked semaphore was reported at shutdown

Python's resource tracker reported one `loky` semaphore while the failed run
was shutting down. This is a resource-cleanup warning, not the CUDA failure's
cause. One aborted run does not establish an accumulating leak during normal
operation. After startup works, test repeated connect/disconnect and failed
initialization cycles while tracking resource counts. Avoid suppressing the
warning before establishing whether cleanup is complete.

## Recovery changes worth adding, in priority order

### A. Validate readiness before advertising a working voice bot

The development runner's `/status` implementation reports HTTP availability
and selected transports; it does not check models. Its `Bot ready!` banner
also precedes model initialization in this project.

Add a startup preflight that validates YAML, verifies cached model/voice assets,
checks the configured Ollama endpoint and model, and initializes the selected
Whisper device. Give failures a clear component name and corrective message.
Report application readiness separately from HTTP liveness, for example
`/readyz` returning 503 when the bot cannot start a conversation.

For the cabinet's current hardware, limit active sessions to one, or apply
explicit admission control. The runner currently permits multiple peers, and
every connection constructs another Whisper/Kokoro pipeline. Concurrent model
loads can exhaust RAM/VRAM. Cache assets and preflight results, but create fresh
stateful processors and conversation context for each session; sharing live
processors between sessions is not a safe shortcut.

### B. Distinguish failures by layer

| Failure | Recommended behavior |
| --- | --- |
| Invalid YAML, language, voice/model name, or CUDA configuration | Fail clearly; do not retry unchanged inputs |
| Temporary Ollama connection failure or server error | Bounded request retries with backoff and one overall deadline |
| Service becomes unusable during a pipeline | End cleanly, or use a prepared fallback |
| Temporary WebRTC outage | Use transport reconnection; create a fresh session after a server restart |
| Python process exits or is killed | External process supervisor with restart rate limits |

Keep `ProcessorUnusablePolicy.END` unless a fallback is added. It ends a
pipeline when a processor becomes unusable; it does not restart the process.
Enhance `on_pipeline_error` logging with session ID, service, category,
exception, and `processor.is_usable`. Handle constructor failures outside this
event handler. Only restore usability after the cause is fixed. These semantics
are described in [Pipecat error handling](https://docs.pipecat.ai/pipecat/fundamentals/error-handling).

### C. Bound Ollama response times

The installed local Ollama client uses the OpenAI-compatible SDK, whose
observed defaults are **2 retries**, a **5-second connect timeout**, and
**600-second read/write timeouts**. A read timeout is not a total turn deadline.
The project currently adds no application-level completion deadline.

Pipecat 1.12.0's `retry_on_timeout=True` bounds the initial completion-creation
await and then retries once without that outer timeout. It does not put a
deadline around the whole streamed response. See the
[pinned implementation](https://github.com/pipecat-ai/pipecat/blob/v1.12.0/src/pipecat/services/openai/base_llm.py).

Define an explicit connect limit, first-response limit, and overall turn budget.
Coordinate retries with the SDK so layers do not multiply attempts. A proposed
starting policy is at most two retries, with jittered delays around one and
two seconds, all inside the total budget. Choose deadlines using cold and warm
model measurements. Stop retries on user cancellation, and avoid replaying a
reply after partial speech has already been delivered. Tell the client when
the turn fails instead of remaining silently connected.

### D. Add monitoring and correct idle behavior

Enable `PipelineParams(enable_metrics=True, enable_heartbeats=True)`. The
installed version emits `on_heartbeat_timeout` when frames stop traversing the
pipeline. Heartbeats alone do not restart anything: add an explicit handler
that records the stall and applies a bounded cancellation/recovery policy.
An external watchdog is needed for a completely blocked event loop or native
process failure. See [pipeline heartbeats](https://docs.pipecat.ai/api-reference/server/pipeline/heartbeats)
and the [heartbeat example](https://github.com/pipecat-ai/pipecat/blob/main/examples/observability/observability-heartbeats.py).

Both modes currently inherit a **300-second pipeline idle timeout**. Local
audio therefore stops after inactivity; that is expected cancellation, not a
crash. For an always-listening cabinet, set local mode's pipeline idle timeout
to `None`, or implement an explicit idle lifecycle. Keep this separate from
the wake phrase's five-second inactivity window. See
[pipeline idle detection](https://docs.pipecat.ai/api-reference/server/pipeline/pipeline-idle-detection).

### E. Restart crashed processes

For a WSL/Linux deployment with systemd enabled, a user service can run the
bot and restart it after abnormal exits. The following is an illustrative
configuration; replace `/absolute/path/to/PixelPilot` with the deployment path.
No service was installed or enabled:

```ini
[Unit]
Description=PixelPilot voice bot
StartLimitIntervalSec=60
StartLimitBurst=3

[Service]
WorkingDirectory=/absolute/path/to/PixelPilot/bot
ExecStart=/absolute/path/to/PixelPilot/bot/.venv/bin/python -u bot.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

`on-failure` handles process failure, not an ASGI background task failing while
the server stays alive. It also does not restart a local pipeline that ends
normally on idle. The startup rate limit prevents a permanently broken setup
from looping continuously. See [systemd restart behavior](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html#Restart=).

### F. Configure reconnection and failover

The current documented SmallWebRTC client already retries transient connection
failures up to three times. The installed prebuilt client bundle also contains
a three-attempt reconnection limit. A successful signaling response followed
by failed model initialization is not automatically an HTTP 5xx retry case.
After process restart, the application should start a new session rather than
assume the old peer and conversation still exist. See
[SmallWebRTC reconnection](https://docs.pipecat.ai/api-reference/client/js/transports/small-webrtc#reconnection-handling).

`ServiceSwitcher` can move from an unusable provider to a prepared healthy
alternative. It cannot catch a GPU service constructor that raises before the
switcher can be built. An explicit GPU-to-CPU construction fallback would be
needed here. A smaller Ollama model can help with model-specific resource
failures, but cannot fix the same Ollama server being offline. Piper is not
currently an active, validated TTS fallback. See
[ServiceSwitcher](https://docs.pipecat.ai/api-reference/server/utilities/service-switchers/service-switcher).

## Smaller code corrections

- Put Kokoro `speed` inside `KokoroTTSService.Settings(...)`; the installed
  service reads speed from settings. Passing it as an unrelated constructor
  keyword does not apply a non-default speech speed.
- Validate configuration types and log levels at startup, with field-specific
  errors. Currently YAML loading and most indexing happen without validation.
- Review the two Silero analyzers only with speech-boundary tests. The one
  before segmented Whisper supplies the speech boundaries it needs; simply
  deleting it is not a complete reliability fix.

## Suggested implementation order and acceptance checks

1. Correct `language`, resolve GPU exposure or select CPU, then make readiness
   depend on a successful model preflight.
2. Add bounded Ollama deadlines/retries and clear session-level error reporting.
3. Enable metrics/heartbeat handling and choose an always-on local idle policy.
4. Add process supervision and a validated fallback only where it is useful.
5. Fault-test unavailable Ollama, invalid model/voice, failed CUDA startup,
   network loss, cancellation during negotiation, a second simultaneous client,
   five minutes of local inactivity, and process termination/restart.

Those fault tests are recommendations, not tests performed in this review.
The runtime evidence above comes from exactly one unchanged-config launch.
