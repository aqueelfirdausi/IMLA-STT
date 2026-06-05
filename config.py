"""
config.py — All settings for the IMLA voice agent live here.
Change values here instead of hunting through multiple files.
"""

import os

# ─────────────────────────────────────────────
# STT (Speech-to-Text) — faster-whisper
# ─────────────────────────────────────────────

# Which Whisper model to load.
# Options: "tiny", "base", "small", "medium", "large-v2"
# Use "base" to start; swap to your fine-tuned model path later.
STT_MODEL = "small"

# If you have a fine-tuned model folder inside this project, set the path here
# and change STT_MODEL to STT_CUSTOM_MODEL_PATH to use it.
STT_CUSTOM_MODEL_PATH = "./imla-whisper-finetuned"  # change when ready

# Device for Whisper: "cpu" or "cuda" (GPU). Use "cpu" if unsure.
STT_DEVICE = "cpu"

# Number format for Whisper on CPU. Keep "int8" — it's fast and accurate enough.
STT_COMPUTE_TYPE = "int8"

# Language to transcribe. "en" = English. None = auto-detect.
STT_LANGUAGE = "en"

# Optional prompt to bias Whisper toward your vocabulary/style.
# Leave empty to let Whisper decide on its own.
STT_PROMPT = "Groq, faster-whisper, PySide6, IMLA-STT, Vercel, PWA"

# ─────────────────────────────────────────────
# Audio recording & silence detection
# ─────────────────────────────────────────────

# Microphone sample rate (Hz). 16000 is standard for Whisper.
SAMPLE_RATE = 16000

# How many audio samples per chunk (≈ 30 ms at 16 kHz).
CHUNK_SIZE = 512

# How many channels. 1 = mono (recommended for Whisper).
CHANNELS = 1

# Volume level (0.0–1.0) below which we consider it "silence".
# Raise this if the mic picks up background noise.
SILENCE_THRESHOLD = 0.02

# How many seconds of silence ends the recording.
SILENCE_DURATION = 1.5

# Maximum recording length in seconds (safety cap).
MAX_RECORD_SECONDS = 30

# Minimum speech duration to bother transcribing (seconds).
# Avoids sending tiny blips to Whisper.
MIN_SPEECH_SECONDS = 0.5

# ─────────────────────────────────────────────
# LLM — Groq API
# ─────────────────────────────────────────────

# Read the API key from the environment — never hardcode secrets.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Groq model to use. llama-3.3-70b-versatile is fast and capable.
GROQ_MODEL = "llama-3.3-70b-versatile"

# How many recent conversation turns to remember (1 turn = 1 user + 1 assistant).
CONVERSATION_MEMORY_TURNS = 8

# Controls randomness in replies. 0.0 = robotic/deterministic, 1.0 = creative.
LLM_TEMPERATURE = 0.7

# Maximum tokens the LLM may output per reply. Keep low for spoken responses.
LLM_MAX_TOKENS = 150

# Words/phrases that end the session when the user says them.
GOODBYE_PHRASES = ["goodbye", "good bye", "bye", "exit", "quit", "stop", "see you"]

# ─────────────────────────────────────────────
# TTS (Text-to-Speech) — Piper
# ─────────────────────────────────────────────

# Path to the Piper executable.
PIPER_EXECUTABLE = r".\tts\piper\piper.exe"

# Path to the voice model file (.onnx).
PIPER_VOICE_MODEL = r".\tts\voices\en_US-lessac-medium.onnx"

# Path to the voice config file (.onnx.json).
PIPER_VOICE_CONFIG = r".\tts\voices\en_US-lessac-medium.onnx.json"

# Temporary WAV file Piper writes; the agent plays this then deletes it.
TTS_OUTPUT_WAV = r".\recordings\tts_output.wav"

# ─────────────────────────────────────────────
# Dictation (dictate.py) — global voice input
# ─────────────────────────────────────────────

# The key that triggers dictation.
# Any key name recognised by the `keyboard` library works (e.g. "caps lock", "f9").
DICTATION_HOTKEY = "caps lock"

# "hold"   -- hold the key while speaking, release to insert
# "toggle" -- first press starts recording, second press stops
DICTATION_MODE = "hold"

# Suppress Caps Lock's normal toggle behaviour while the app runs.
# Set False only if you choose a non-Caps-Lock hotkey above.
DICTATION_SUPPRESS_CAPSLOCK = True

# Send the raw transcript through Groq for grammar / punctuation cleanup.
# If the Groq call fails or times out, raw text is inserted as a fallback.
DICTATION_AI_CLEANUP = True

# Seconds to wait for Groq cleanup before giving up and using raw text.
DICTATION_CLEANUP_TIMEOUT = 6

# Max recording length in seconds for dictation (safety cap).
DICTATION_MAX_SECONDS = 60

# ─────────────────────────────────────────────
# System prompt — the agent's personality
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are IMLA, a razor-sharp voice assistant with the energy of
a brilliant friend who has read everything and is mildly amused by most of it.
You are witty, direct, and occasionally sarcastic — but never mean. You have
genuine expertise in language learning, Arabic, English, and linguistics, and
you're not shy about having opinions. You find corporate-speak physically painful.

STRICT VOICE RULES — violating these is not an option:
- Reply in 1 to 2 sentences maximum. Every time. No exceptions.
- No bullet points, numbered lists, markdown, or emojis. You are speaking, not typing.
- Never open with "Certainly!", "Great question!", "Of course!", or any sycophantic filler. Just talk.
- If you don't know something, admit it briefly and move on — don't spiral.
- Dry humour and light sarcasm are welcome. Lectures are not.
- If the user says goodbye, sign off with something memorable, not "Have a nice day!"
"""
