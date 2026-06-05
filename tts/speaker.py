"""
tts/speaker.py — Converts text to speech using Piper, then plays it.

Piper is a local TTS engine. It reads text from stdin and writes a WAV file.
We then play that WAV file with sounddevice (no PyAudio needed).
"""

import subprocess
import os
import sys
import wave

import numpy as np
import sounddevice as sd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


def speak(text: str) -> None:
    """
    Convert `text` to speech and play it through the speakers.

    Steps:
      1. Run Piper as a subprocess, piping `text` in via stdin.
      2. Piper writes a WAV file to TTS_OUTPUT_WAV.
      3. We read that WAV with the standard `wave` module.
      4. We play it with sounddevice.
      5. Delete the temp WAV.
    """
    if not text.strip():
        return

    # ── safety check: make sure Piper is installed ───────────────────────
    piper_path = os.path.abspath(config.PIPER_EXECUTABLE)
    if not os.path.exists(piper_path):
        print(
            f"[TTS] ERROR: Piper not found at {piper_path}\n"
            "      Follow README step 4 to install Piper."
        )
        return

    voice_model = os.path.abspath(config.PIPER_VOICE_MODEL)
    voice_config = os.path.abspath(config.PIPER_VOICE_CONFIG)
    output_wav = os.path.abspath(config.TTS_OUTPUT_WAV)

    # ── run Piper ─────────────────────────────────────────────────────────
    # We pass the text via stdin so we don't have to worry about shell escaping.
    cmd = [
        piper_path,
        "--model", voice_model,
        "--config", voice_config,
        "--output_file", output_wav,
    ]

    try:
        result = subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(f"[TTS] Piper error:\n{result.stderr.decode()}")
            return
    except subprocess.TimeoutExpired:
        print("[TTS] Piper timed out.")
        return
    except Exception as e:
        print(f"[TTS] Failed to run Piper: {e}")
        return

    # ── read and play the WAV ─────────────────────────────────────────────
    if not os.path.exists(output_wav):
        print("[TTS] WAV file was not created by Piper.")
        return

    try:
        with wave.open(output_wav, "rb") as wf:
            sample_rate = wf.getframerate()
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()   # bytes per sample
            raw = wf.readframes(wf.getnframes())

        # Convert raw bytes to a NumPy array.
        # sample_width=2 means 16-bit (int16); normalise to float32 [-1, 1].
        dtype_map = {1: np.int8, 2: np.int16, 4: np.int32}
        np_dtype = dtype_map.get(sample_width, np.int16)
        audio = np.frombuffer(raw, dtype=np_dtype).astype(np.float32)
        audio /= np.iinfo(np_dtype).max

        # Reshape to (frames, channels) if stereo.
        if n_channels > 1:
            audio = audio.reshape(-1, n_channels)

        print("[TTS] Speaking…")
        sd.play(audio, samplerate=sample_rate)
        sd.wait()   # block until playback is done

    except Exception as e:
        print(f"[TTS] Playback error: {e}")
    finally:
        # Clean up the temp file.
        try:
            os.remove(output_wav)
        except OSError:
            pass
