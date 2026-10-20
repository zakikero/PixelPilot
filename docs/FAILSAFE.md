# PixelPilot failsafe and recovery review

Reviewed **2026-10-20**, at revision `f9804c7`, against the project and its
installed **Pipecat 1.12.0 / Python 3.14.4** dependencies.

This is a reliability review and implementation plan. Only this document was
updated; the recommendations below have not been implemented.

## Current state and verification

The shared pipeline still uses Whisper `large-v3-turbo` on CPU INT8, Ollama
`llama3.2:3b`, and Kokoro. WebRTC is the default; local audio remains supported.
Whisper's saved language is now `en`, and Kokoro speed is correctly supplied
through its settings object.

The existing WebRTC `finally` block releases the peer after configuration or
model-construction failure. The wake strategy is correctly placed before
the default turn-start strategies. Keep the VAD processor before segmented
Whisper: it supplies the speech boundaries needed for transcription.

| Check performed in this review | Result |
| --- | --- |
| Existing automated tests | 12 passed |
| Ruff lint and format check | Passed |
| Pyright | 0 errors, 0 warnings |
| Temporary localhost WebRTC server, using cached models | Started |
| Browser client page and signaling offer | HTTP 200 |
| Silent aiortc peer and RTVI readiness | Connected; received `bot-ready` about 6.79 seconds after applying the answer |
| Ollama availability | HTTP 200; configured `llama3.2:3b` present |
| Peer disconnect | Pipeline stopped; HTTP server remained available |
| Server shutdown | Clean exit, code 0 |
| Injected permanent pipeline error | Error logged, but `run_bot()` returned normally; probe process exited 0 |
| Whisper with a controlled lazy model | Segment iteration ran on the event-loop thread |
| Local output with a controlled blocking stream | Cleanup closed the stream while a cancelled write was still running |
| Invalid configuration field | Loader accepted integer log level; logging then raised `AttributeError` |

The connection probe sent silence and did not use physical microphones or
speakers. It verified connection readiness and cleanup, not an actual spoken
turn, Ollama generation, or model inference quality. The Whisper and local
cleanup probes used fake components to establish execution order safely.

Temporary diagnostics are in `/tmp/pixelpilot-reliability-review.py` and
`/tmp/pixelpilot-reliability-review-server.log`; this document preserves the
results because those files are not durable project artifacts. The temporary
server and probes were stopped.

## Findings in priority order

### 1. High: Whisper can block the event loop during transcription

The project selects `WhisperSTTService` in
[voice_pipeline.py](../bot/voice_pipeline.py#L42). Its installed `run_stt()`
sends `model.transcribe()` through `asyncio.to_thread()`, then iterates
`segments` directly in the async function. Faster Whisper returns a lazy
generator: transcription work also happens during iteration.

The controlled probe confirmed that the initial call ran in a worker thread
but segment iteration ran on the event loop. A deliberate 150 ms delay in
the generator produced a 156.2 ms gap in a 5 ms async ticker. This is an
execution-order demonstration, not a benchmark of the real model.

During actual recognition this can delay HTTP requests, WebRTC handling,
wake timers, cancellation, and heartbeat monitoring. CPU inference with the
current large model makes this particularly relevant.

**Recommended fix:** use a narrowly scoped, tested STT adapter or an upstream
fix that performs both the transcription call and generator consumption in
the worker thread. Preserve transcription frames, filtering, tracing, metrics,
and error propagation. Keep inference concurrency bounded. A thread timeout
does not stop native inference already running; process isolation is needed
if hard termination is required.

Sources: [pinned Whisper implementation](https://github.com/pipecat-ai/pipecat/blob/v1.12.0/src/pipecat/services/whisper/stt.py),
[Faster Whisper's generator semantics](https://github.com/SYSTRAN/faster-whisper#usage).

### 2. High: a permanent pipeline failure can look like successful process completion

[run_bot()](../bot/voice_pipeline.py#L111) uses
`ProcessorUnusablePolicy.END`; its error handler only logs. The injected
permanent error marked a processor unusable and ended the pipeline, but
`run_bot()` returned normally and the probe process exited with code `0`.

That policy provides graceful session termination. It does not communicate
a failed outcome to the local command or restart a conversation. A supervisor
configured with `Restart=on-failure` can therefore miss this failure. In WebRTC
mode the HTTP process can also remain alive after an individual session fails.

**Recommended fix:** record the session's terminal outcome. After cleanup,
propagate an unexpected permanent failure to the local command as a nonzero
exit; keep deliberate disconnects and user shutdown successful. Report WebRTC
session failure through an explicit lifecycle outcome while preserving the
HTTP server for subsequent connections.

Handle recoverable failures separately. Retry transient connectivity/server
errors within a budget; reject invalid configuration or unknown model/voice
without retrying unchanged inputs. Include session ID, processor, category,
exception, and usability in error logs.

Source: [Pipecat error handling](https://docs.pipecat.ai/pipecat/fundamentals/error-handling).

### 3. High for an unattended cabinet: local listening ends after five idle minutes

[run_local_bot()](../bot/bot.py#L104) creates default `RunnerArguments`, whose
installed idle timeout is `300` seconds.
[run_bot()](../bot/voice_pipeline.py#L115) passes that value to the worker.
The idle handler logs but leaves automatic cancellation enabled.

After five minutes without activity, local mode can stop listening and return
normally. This is intentional framework idle behavior, distinct from the
five-second wake-phrase window, but it conflicts with an always-listening
cabinet. This review checked the configuration and framework path; it did
not wait five real minutes.

**Recommended fix:** choose the policy explicitly for each transport. For an
always-listening local bot, set the pipeline idle timeout to `None`. Retain
a finite WebRTC timeout if abandoned browser sessions should be released.
A disconnected or expired browser session should start a new conversation
when reconnecting.

Source: [pipeline idle detection](https://docs.pipecat.ai/api-reference/server/pipeline/pipeline-idle-detection).

### 4. High: Ollama has no overall turn deadline or bounded recovery policy

[Ollama construction](../bot/voice_pipeline.py#L50) does not configure a turn
deadline or application retry policy. The installed SDK defaults remain
two retries, a five-second connect timeout, and 600-second read/write
timeouts. A read timeout is not a deadline for the entire streamed reply.

Pipecat's optional `retry_on_timeout` also does not solve this: in this
version it bounds initial completion creation and reissues the request
without that outer bound. Passing arbitrary `timeout` or `max_retries`
keywords to this version's service is insufficient: its client factory
constructs the SDK client without forwarding those options.

**Recommended fix:** configure the actual HTTP/SDK client through a tested
client-factory override, and enforce first-output and overall turn budgets
around streamed generation. Choose limits from cold and warm measurements.
Use one coordinated retry budget, for example at most two attempts total
for transient failures, with backoff inside the deadline. Account for SDK
retries rather than adding another independent retry loop.

Cancel retries on interruption or disconnect. Once speech has started,
avoid replaying the entire answer automatically. Give local users a brief
failure indication and ensure WebRTC clients handle the error/lifecycle
event; Pipecat already has RTVI error reporting.

Source: [pinned OpenAI-compatible client implementation](https://github.com/pipecat-ai/pipecat/blob/v1.12.0/src/pipecat/services/openai/base_llm.py).
The SDK timeout/retry defaults were checked in the installed package.

### 5. Medium: readiness and admission control do not cover models

[create_pipeline()](../bot/voice_pipeline.py#L36) constructs Whisper, Kokoro,
and both Silero analyzers synchronously for every connection. It runs inside
the async session before `PipelineWorker` exists. Model loading and first-use
downloads can block the ASGI event loop; worker setup/start timeouts cannot
bound constructor work that precedes the worker.

The runner's `/status` and startup banner indicate HTTP availability.
They do not check Ollama inference or successful pipeline construction.
Multiple WebRTC clients can each allocate another set of models; the
README's one-session recommendation is not enforced.

**Recommended fix:** pre-download required assets, validate model readiness
before admitting a conversation, and enforce one active/starting session on
cabinet hardware. Return a clear busy outcome for a second session instead
of allowing duplicate model loading. Use a tested loading path that keeps
blocking initialization off the HTTP event loop.

Expose model readiness separately from liveness, such as `/readyz`, and
track startup failures outside `on_pipeline_error`. Keep fresh conversation
context and stateful processors per session; cached model files do not make
live processors safe to share.

### 6. Medium: configuration is parsed but only the YAML root is validated

[load_config()](../bot/bot.py#L29) uses `safe_load()` and checks for a mapping.
It does not validate sections, required fields, types, or ranges. For example,
`logging.level: 17` passed the loader and later failed at `.upper()`.
A null section, a quoted boolean, or an empty wake phrase can likewise fail
late or select unintended behavior.

**Recommended fix:** validate once, before transport/model allocation, and
report field-specific errors such as `logging.level must be a supported
log level`. Check required mappings, model/voice names, language syntax,
CPU/compute compatibility, numeric ranges, and a nonempty list of nonblank
wake phrases when enabled. Let semantic preflight handle actual asset and
hardware availability. Validate environment overrides as well.

Extend the existing config tests with missing sections, wrong types,
invalid ranges/log levels, empty phrases, and valid `language: null`.
The existing null-language test confirms YAML parsing; it does not establish
complete schema validation.

### 7. Medium, local only: cancellation can race a native output write

Pipecat's installed local transport writes audio in a thread pool.
Cancelling the awaiting coroutine does not stop that native thread.
Cleanup closes the output stream before shutting down the executor with
`wait=False`.

The controlled probe cancelled an active write and confirmed that
`stream.close()` ran while the write remained in flight. A native crash was
not reproduced in this review; the unsafe ordering was demonstrated with a
fake stream.

**Recommended fix:** prefer an upstream transport fix, verified and pinned,
that drains/joins in-flight output work before closing its stream. If a
targeted project fix is later needed, keep it limited to cleanup ordering
and test cancellation during playback and device loss. Do not reintroduce
the custom PortAudio build or broad transport changes that were rolled back.

Source: [pinned local audio transport](https://github.com/pipecat-ai/pipecat/blob/v1.12.0/src/pipecat/transports/local/audio.py).

### 8. Medium for long sessions: context and response length have no explicit budget

The shared pipeline creates a fresh `LLMContext()`, which is correct for
session isolation, but does not enable automatic summarization or impose
a history budget. Ollama generation also has no configured output-token
limit. The system prompt's request for short replies is not an enforced limit.

**Recommended fix:** cap output length and preserve a bounded recent history,
or enable Pipecat's optional context summarization after measuring its local
inference cost. Preserve the system instruction and complete tool exchanges.
Reset conversation state deliberately between cabinet users.

Source: [context summarization](https://docs.pipecat.ai/pipecat/fundamentals/context-summarization).

## Monitoring and restart policy

After the event-loop blocking issue is addressed, enable metrics and
heartbeats through `PipelineParams`. Handle `on_heartbeat_timeout` explicitly;
a logged warning does not restart anything. Measure healthy CPU stalls
before choosing a threshold. Async heartbeats cannot detect a blocked
event loop until that loop runs again.

Use external process supervision for native crashes, killed processes, and
hard hangs. Combine a restart delay with a restart-rate limit; permanent
configuration errors should not create an endless restart loop. First fix
the exit-status gap in finding 2 so `Restart=on-failure` has a useful signal.
A healthy HTTP process also needs session/readiness monitoring.

A fallback is useful only if it has an independent working dependency.
A second model on the same unavailable Ollama server is not an availability
fallback. A `ServiceSwitcher` also cannot rescue a model constructor that
fails before the pipeline is built.

Sources: [heartbeats](https://docs.pipecat.ai/api-reference/server/pipeline/heartbeats),
[service switching](https://docs.pipecat.ai/api-reference/server/utilities/service-switchers/service-switcher),
[systemd restart behavior](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html#Restart=).

## Deployment checks

[Dockerfile](../bot/Dockerfile) pins Python dependencies through the lockfile
but uses a moving `dailyco/pipecat-base:latest` image. Pin a tested base digest
for reproducible deployments. Also configure an Ollama URL reachable from
inside the container: `localhost:11434` normally refers to that container,
rather than the host's Ollama process. Preload or persist the model cache
so a restart does not depend on downloading large assets. No container build
was performed in this review.

## Startup warnings and previous findings

- **WSLg ALSA/JACK discovery noise:** the previously observed probe messages
  are benign when the selected microphone and speaker work. The minimal
  suppression still applies only to successful local transport construction;
  initialization failures replay diagnostics. Stream-open and runtime errors
  remain visible. Keep this behavior.
- **Whisper latency estimate:** the current connection probe logged
  `ttfs_p99_latency not set, using default 1.0s`. Measure and configure an
  appropriate estimate for turn timing; this warning does not mean startup
  failed.
- **No video/screen transceiver:** observed with the audio-only test peer.
  This is expected for that probe and did not prevent readiness.
- **Client version unknown:** the minimal probe omitted an RTVI client
  version. This is a probe limitation, not evidence that the bundled browser
  client is incompatible.
- **Media stream ended:** occurred when the probe deliberately closed its
  peer; distinguish that teardown warning from unexpected media loss.
- **Earlier CUDA failure and YAML `None` string:** historical findings from
  2026-10-19. The saved configuration now uses CPU INT8 and `language: en`;
  neither failure occurred in this review. CUDA still needs target-machine
  validation if it is selected again. See [NVIDIA's WSL guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html).
- **Earlier ICE-closed exception and leaked semaphore:** not reproduced in
  the successful current connection/shutdown probe. One clean session does
  not establish that repeated-session leaks or races are absent.

## Suggested implementation order and acceptance checks

Start with the Whisper threading correction, explicit local idle policy,
and propagation of failed session outcomes. Then add configuration/preflight
validation and session admission control, followed by bounded Ollama recovery.
Add monitoring, external supervision, and long-session limits after those
failure paths have deterministic outcomes.

| Scenario to cover when implementing | Acceptance condition |
| --- | --- |
| Slow or failed Whisper inference | HTTP/cancellation remain responsive; inference concurrency stays bounded |
| Permanent processor error | Local cleanup finishes and exit status is nonzero; WebRTC session ends clearly |
| No activity for more than five minutes | Local bot still accepts the wake phrase under the always-on policy |
| Ollama offline, missing model, or stalled stream | Correct classification, bounded attempts, explicit completion/failure outcome |
| Bad YAML field or unavailable device | Clear startup error naming the field/device before accepting a usable session |
| Second WebRTC connection | Clear busy outcome without allocating another pipeline |
| Disconnect during model startup or audio playback | Bounded cleanup without dangling work or stream-close/write overlap |
| Long conversation | Bounded context/output; acceptable latency and memory use |
| Process killed and restarted | Supervisor restores readiness within a measured budget |
| Repeated connections and failures | File descriptors, tasks, threads, and memory stabilize |

These are proposed regression/acceptance checks, except for the explicitly
listed probes already performed above.
