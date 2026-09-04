import queue
import sys
import threading
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

# --- CONFIGURATION ---
MODEL_SIZE = "tiny"     
COMPUTE_TYPE = "int8"   
SAMPLE_RATE = 16000      
CHUNK_DURATION = 2.0     

audio_queue = queue.Queue()

def callback(indata, frames, time, status):
    """Callback function for the sounddevice input stream."""
    if status:
        print(status, file=sys.stderr)
    audio_queue.put(indata.copy())

def transcribe_stream():
    print("Loading model...")
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type=COMPUTE_TYPE, cpu_threads=4)
    print("Speak into your microphone (Press Ctrl+C to stop)...")

    audio_buffer = np.zeros(0, dtype=np.float32)
    chunk_samples = int(SAMPLE_RATE * CHUNK_DURATION)

    while True:
        try:
            data = audio_queue.get(timeout=1.0)
            audio_buffer = np.append(audio_buffer, data.ravel())

            if len(audio_buffer) >= chunk_samples:
                current_chunk = audio_buffer[:chunk_samples]
                audio_buffer = audio_buffer[chunk_samples:]

                segments, info = model.transcribe(
                    current_chunk, 
                    beam_size=1, 
                    language="en", # Hardcoding language skips detection step (faster)
                    vad_filter=True # Skips processing pure background silence
                )

                for segment in segments:
                    if segment.text.strip():
                        print(f"\r💬 {segment.text.strip()}", end="", flush=True)

        except queue.Empty:
            continue

if __name__ == "__main__":
    transcribe_thread = threading.Thread(target=transcribe_stream, daemon=True)
    transcribe_thread.start()

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=callback, dtype='float32'):
            while True:
                sd.sleep(100)
    except KeyboardInterrupt:
        print("\n👋 Exiting real-time transcriber.")
        sys.exit(0)
