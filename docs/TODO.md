# Work Items

## Now



## Next

- [ ] Handle unavailable audio devices with a clear startup error.
- [ ] Add a focused test for loading and validating the YAML configuration.

## Later

- [ ] Document the WSLg audio prerequisites and recovery steps.

## Completed

- [X] Verify WSLg audio playback end to end with `pactl info` and a short test tone.
- [X] Confirm the microphone and speaker device indexes in `bot/config.yaml` on the target machine.
- [X] Run the bot from `bot/` with `uv run bot.py` and confirm a spoken response.
- [x] Enable local audio output in the Pipecat transport.
- [x] Make the local output device index configurable.
- [x] Add a command that prints available input and output audio devices.
