"""
recorder.py — Listens to the microphone and stops automatically when
you stop talking (silence detection). Returns raw audio as a NumPy array.
"""

import numpy as np
import sounddevice as sd
import time

import config


def record_until_silence() -> np.ndarray | None:
    """
    Record audio from the microphone.

    Starts capturing as soon as you speak.
    Stops automatically after SILENCE_DURATION seconds of quiet.
    Returns a 1-D float32 NumPy array, or None if nothing was recorded.
    """

    print("🎤  Listening… (speak now, silence ends your turn)")

    # We'll collect chunks of audio in this list, then join them at the end.
    audio_chunks: list[np.ndarray] = []

    # Track silence timing.
    silence_start: float | None = None   # when the current silence began
    speech_started = False               # have we heard any speech yet?
    recording_start = time.time()        # overall start time (for the safety cap)

    # ── callback ──────────────────────────────────────────────────────────
    # sounddevice calls this function every time it has a new chunk ready.
    # `indata` shape: (CHUNK_SIZE, CHANNELS)  dtype: float32
    def _callback(indata, frames, time_info, status):
        nonlocal silence_start, speech_started

        # Flatten to 1-D mono and measure loudness (RMS amplitude).
        chunk = indata[:, 0].copy()
        rms = float(np.sqrt(np.mean(chunk ** 2)))

        is_speech = rms > config.SILENCE_THRESHOLD

        if is_speech:
            speech_started = True
            silence_start = None          # reset silence timer
            audio_chunks.append(chunk)
        else:
            if speech_started:
                # We've already heard speech — start/continue silence timer.
                if silence_start is None:
                    silence_start = time.time()
                audio_chunks.append(chunk)   # keep trailing silence for context

    # ── open the mic stream ───────────────────────────────────────────────
    with sd.InputStream(
        samplerate=config.SAMPLE_RATE,
        channels=config.CHANNELS,
        dtype="float32",
        blocksize=config.CHUNK_SIZE,
        callback=_callback,
    ):
        # Poll until one of the stop conditions is met.
        while True:
            time.sleep(0.05)  # check every 50 ms

            elapsed = time.time() - recording_start

            # Safety cap: never record more than MAX_RECORD_SECONDS.
            if elapsed > config.MAX_RECORD_SECONDS:
                print("⚠️  Max recording length reached.")
                break

            # Silence-based stop: speech detected AND silence long enough.
            if speech_started and silence_start is not None:
                silence_elapsed = time.time() - silence_start
                if silence_elapsed >= config.SILENCE_DURATION:
                    break

    if not audio_chunks:
        return None

    # Join all chunks into one array.
    audio = np.concatenate(audio_chunks)

    # Reject clips that are too short (probably just noise).
    duration = len(audio) / config.SAMPLE_RATE
    if duration < config.MIN_SPEECH_SECONDS:
        return None

    return audio
