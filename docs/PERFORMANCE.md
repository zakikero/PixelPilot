# Bot response time and readable metrics

Review date: 2026-10-18.

The deployment machine is expected to be similar to a laptop. Its CPU, GPU,
memory, and operating system are not yet specified. Measurements from the
development machine should not be treated as deployment results.

These are code review findings and a measurement plan. No latency benchmark has
been collected, and no runtime behavior was changed for this document.

## Current setup

The shared pipeline is now in [voice_pipeline.py](../bot/voice_pipeline.py).
The configuration table below records the original review snapshot; current
model and device choices are in [config.yaml](../bot/config.yaml).

The pipeline is microphone → voice detection → Whisper → user
turn aggregation → Ollama → Kokoro → speakers.

| Component | Current configuration | What to investigate |
| --- | --- | --- |
| Speech recognition | Whisper `large-v3-turbo`, CUDA, FP16, English | Recognition time and memory use on the target laptop. CUDA requires a compatible NVIDIA setup. |
| Language model | Ollama `llama3.1:8b`, local server | Time to first usable text, memory pressure, and model loading after idle periods. |
| Speech synthesis | Kokoro, `af_heart`, speed `1.0` | Delay before the first generated audio. Piper is configured but inactive. |
| Voice detection | Two separate Silero analyzers | One is before Whisper; the other is in the user aggregator. Review repeated processing and boundary events. |
| Turn completion | Default stop strategies | The locked Pipecat version, 1.12.0, defaults to Smart Turn V3. Completion decisions can affect when the LLM starts. |
| Wake phrase | Enabled, `hey pixel`, timeout `5.0` seconds | The timeout is an inactivity window, not a five-second delay before each response. |
| Observability | Transcription and LLM logs; metrics and Whisker commented out | Existing logs do not provide a clear breakdown of response time. |

Configuration is in [config.yaml](../bot/config.yaml); dependency versions are in
[uv.lock](../bot/uv.lock).

## The main metric: time until the bot starts speaking

Measure from the end of the user's speech to the first bot audio sent for
playback. This is the most useful software approximation of the pause the user
experiences. Label it **response start delay**, and display it in milliseconds.

Audio sent to the output device is not proof that sound has reached the speaker.
Measuring actual audible latency requires an audio recording or loopback test.
Label the software result as an estimate until that is verified.

Use these milestones for each turn:

| Milestone | Meaning |
| --- | --- |
| A | User finishes speaking, estimated from the input audio or VAD speech boundary. |
| B | The complete user turn is submitted to the LLM. |
| C | The LLM produces its first usable text token. |
| D | TTS produces the first audio for that reply. |
| E | The output transport begins submitting that audio for playback. |

| Readable metric | Calculation | What a large value suggests |
| --- | --- | --- |
| Wait before model | B − A | Speech recognition, silence detection, turn completion, or queueing. |
| Model first text | C − B | Model loading, prompt processing, inference, or resource contention. |
| Prepare first audio | D − C | Waiting for a sentence boundary, speech synthesis, or queueing. |
| Output buffering | E − D | Transport scheduling and software audio buffers. Device latency may remain unmeasured. |
| **Response start delay** | **E − A** | The overall pause before the reply starts playing. |

For the current pipeline, the four consecutive intervals above add up to the
response start delay. Track them for the same turn and use a monotonic clock.
If a milestone is unavailable, report `unavailable` rather than zero.

Also record the time from speech end to the final transcript. This helps explain
the wait before the model, but it overlaps that interval: do not add it again.
With segmented Whisper, it includes waiting for the speech boundary as well as
transcription. Keep the VAD silence delay visible; starting the timer only when
the stop event arrives can hide part of the user's wait.

## A readable summary after each turn

The following is an illustrative format, not measured output:

```text
Turn 12 | warm model | 4 messages in context
Response start delay: 960 ms (software playback estimate)
  Wait before model:  420 ms
    Final transcript: 350 ms after speech ended (included above)
  Model first text:   260 ms
  Prepare first audio:240 ms
  Output buffering:    40 ms
Result: completed
```

Pipecat's service metrics are useful supporting evidence. A service's
time-to-first-byte (TTFB) is tied to that service's measurement boundaries; it is
not automatically the user's total waiting time. For TTS, time after the synthesis
request also excludes earlier sentence buffering. Convert seconds to milliseconds
and name the interval explicitly instead of displaying an unexplained `TTFB`.

Keep token counts, tokens per second, and total reply duration as secondary
details. Faster token generation does not necessarily mean earlier speech.
Increasing Kokoro's speaking speed changes delivery speed, not necessarily the
delay before the first sound.

## Optimization candidates

1. **Benchmark smaller speech recognition models.** Compare `base.en` or
   `small.en` with the current model. For a CPU deployment, use an appropriate
   CPU configuration such as INT8. Test game names, accents, and arcade noise;
   speed gains are useful only if recognition stays reliable. Faster Whisper is
   already the backend, so adopting it again would not be a new optimization.
2. **Benchmark a smaller, quantized LLM.** Compare a model around 3B parameters,
   such as `llama3.2:3b`, against the current 8B model. Check answer quality and
   instruction following alongside model first-text time and memory use.
3. **Keep the first sentence short.** Pipecat's default sentence aggregation
   waits for a sentence boundary before synthesis. A brief, useful first sentence
   can start playback earlier. Kokoro already uses an audio streaming API in the
   locked version; do not assume streaming is entirely absent.
4. **Review the duplicated VAD setup.** Consolidating detection may reduce work
   and make timing easier to understand. Preserve the boundary events needed by
   segmented Whisper; simply deleting the processor before STT is not a complete
   plan. Do not assume the duplication doubles latency.
5. **Preload and retain the Ollama model when memory permits.** This primarily
   addresses the first response after startup or idle periods. Compare cold and
   warm requests separately before changing `OLLAMA_KEEP_ALIVE`.
6. **Watch performance as conversations grow.** The bot maintains conversation
   context without an explicit application history limit. Record context size and
   first-text time; consider trimming or summarization if long sessions slow down.

If the largest interval is before the model, investigate STT and turn completion
first. If it is model first text, investigate the LLM. If text arrives quickly but
audio is late, investigate sentence buffering and TTS. Change one thing at a time.

## Comparing results on the target laptop

- Use the same recorded phrases, microphone conditions, model versions, and
  reply-length instructions for each configuration. Include real game names and
  background noise, not only easy greetings.
- Separate startup/model-loading requests, warm requests, and requests after an
  idle period. Include a longer conversation to reveal context growth.
- Record hardware, available RAM/VRAM, model quantization, inference device,
  context size, and power mode. Check sustained use as well as the first few turns.
- Collect roughly 50–100 completed turns for an initial comparison. Report the
  sample size; percentile estimates from a small sample are unstable.
- Report **p50** (the typical delay) and **p95** (the delay at or below which about
  95% of responses fall). Report failed, interrupted, and unanswered turns
  separately so a fast successful subset does not hide reliability problems.
- Track recognition errors, missed wake phrases, incorrect answers, and the bot
  speaking before the user has finished. Set latency targets after establishing
  the laptop baseline; no target or speedup is established yet.

| Configuration | Test condition | Completed / attempted turns | Response p50 | Response p95 | Recognition / answer issues |
| --- | --- | --- | --- | --- | --- |
| Current models | Warm | Not measured | — | — | — |
| Smaller Whisper | Warm | Not measured | — | — | — |
| Smaller LLM | Warm | Not measured | — | — | — |
| Selected combination | Startup / after idle | Not measured | — | — | — |

## Suggested next implementation

Enable the existing service metrics and add one readable summary per turn using
the definitions above. Associate measurements with a turn ID, keep raw timings
available for diagnosis, and export comparable records if needed. End-to-end
milestones require observation beyond simply enabling service metrics. This is
a proposed implementation; this document does not enable instrumentation.

## Supporting references

- Smaller models and CPU/GPU quantization: [Faster Whisper](https://github.com/SYSTRAN/faster-whisper#usage).
- Candidate smaller LLM: [Ollama Llama 3.2 3B](https://ollama.com/library/llama3.2:3b).
- Preloading and model retention: [Ollama FAQ](https://docs.ollama.com/faq).
- Sentence aggregation: [Pipecat 1.12.0 TTS service](https://github.com/pipecat-ai/pipecat/blob/v1.12.0/src/pipecat/services/tts_service.py).
- Kokoro audio streaming: [Pipecat 1.12.0 Kokoro service](https://github.com/pipecat-ai/pipecat/blob/v1.12.0/src/pipecat/services/kokoro/tts.py).
- Aggregator VAD: [Pipecat 1.12.0 user aggregator](https://github.com/pipecat-ai/pipecat/blob/v1.12.0/src/pipecat/processors/aggregators/llm_response_universal.py).
- Default turn completion: [Pipecat 1.12.0 turn strategies](https://github.com/pipecat-ai/pipecat/blob/v1.12.0/src/pipecat/turns/user_turn_strategies.py).
- Wake phrase timeout: [Pipecat wake phrase strategy](https://reference-server.pipecat.ai/en/latest/_modules/pipecat/turns/user_start/wake_phrase_user_turn_start_strategy.html).
