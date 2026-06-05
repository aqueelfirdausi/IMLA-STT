"""
dictation/dict_recorder.py -- Record microphone until a threading.Event is set.

Unlike recorder.py (which uses silence detection), this module records until
the caller signals it to stop -- suitable for hold-to-record or toggle mode.
"""

import threading
import time

import numpy as np
import sounddevice as sd

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


def record_until_stopped(
    stop_event: threading.Event,
    amplitude_callback=None,   # optional: called each chunk with RMS float (0..1)
) -> np.ndarray | None:
    """
    Record from the default microphone until `stop_event` is set.

    Parameters
    ----------
    stop_event         : set this to stop recording early
    amplitude_callback : if provided, called ~30x/sec with the chunk's RMS
                         amplitude (0.0–1.0). Safe to call from any thread.

    Returns a 1-D float32 NumPy array, or None if the clip was too short.
    """
    chunks: list[np.ndarray] = []
    start_time = time.time()

    def _callback(indata, frames, time_info, status):
        mono = indata[:, 0].copy()
        chunks.append(mono)
        if amplitude_callback is not None:
            rms = float(np.sqrt(np.mean(mono ** 2)))
            amplitude_callback(rms)

    with sd.InputStream(
        samplerate=config.SAMPLE_RATE,
        channels=config.CHANNELS,
        dtype="float32",
        blocksize=config.CHUNK_SIZE,
        callback=_callback,
    ):
        while not stop_event.is_set():
            time.sleep(0.02)

            # Safety cap -- never record forever.
            if time.time() - start_time > config.DICTATION_MAX_SECONDS:
                break

    if not chunks:
        return None

    audio = np.concatenate(chunks)
    duration = len(audio) / config.SAMPLE_RATE

    if duration < config.MIN_SPEECH_SECONDS:
        return None

    return audio
