"""List audio devices available to the local bot environment."""

import sounddevice as sd


def main() -> None:
    """Print input and output devices with their PortAudio indexes."""
    devices = sd.query_devices()
    print("Input devices:")
    for index, device in enumerate(devices):
        if device["max_input_channels"] > 0:
            print(f"  {index}: {device['name']}")

    print("Output devices:")
    for index, device in enumerate(devices):
        if device["max_output_channels"] > 0:
            print(f"  {index}: {device['name']}")


if __name__ == "__main__":
    main()
