"""
stt/transcriber.py — Converts audio (NumPy array) to text using Groq whisper-large-v3.
"""

import io
import wave
import numpy as np

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # allow `import config`
import config
from groq import Groq

_client = Groq(api_key=config.GROQ_API_KEY)


def transcribe(audio: np.ndarray) -> str:
    """
    Transcribe a NumPy float32 audio array to a string.

    Parameters
    ----------
    audio : np.ndarray
        1-D float32 array at SAMPLE_RATE Hz (from recorder.py).

    Returns
    -------
    str
        The transcribed text, stripped of whitespace. Empty string on failure.
    """
    # Convert float32 → int16 PCM, then wrap in an in-memory WAV container.
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(config.CHANNELS)
        wf.setsampwidth(2)          # 16-bit = 2 bytes
        wf.setframerate(config.SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())
    buf.seek(0)
    buf.name = "audio.wav"          # Groq SDK reads .name for the MIME type

    try:
        result = _client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=buf,
            language=config.STT_LANGUAGE,
            prompt=config.STT_PROMPT,
            response_format="text",
        )
        text = result.strip() if isinstance(result, str) else result.text.strip()
    except Exception as exc:
        print(f"[STT] Groq error ({exc}) — returning empty string.")
        return ""

    if text:
        print(f"[STT] Heard: {text}")
    else:
        print("[STT] (nothing transcribed)")

    return text
