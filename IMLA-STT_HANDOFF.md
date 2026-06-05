# IMLA-STT — Technical Handoff

Companion to IMLA-STT_PLAN.md. The plan captures the mission, vision, and roadmap. This file captures the current technical state — what's built, how it runs, and the gotchas. Hand both files to any new AI session.

## Current State (as of June 2026)

Working tool. Phases 1 and 2 of the plan are complete and tested.

Phase 1 (accent accuracy — the mission): SOLVED. Transcription uses Groq's hosted whisper-large-v3 (not the old local faster-whisper small). A vocabulary hint (STT_PROMPT in config.py) biases toward project-specific terms. Tested successfully in both noisy (fan + background voices) and quiet conditions.

Phase 2 (solidify the laptop tool): DONE. GitHub repo live, .gitignore in place, reproducible requirements.txt, isolated virtual environment — all verified.

## How It Runs

Activate the venv first (Windows): run ".venv\Scripts\activate" — the prompt should show (.venv) — then run "python dictate.py".

Entry point: dictate.py. Hotkey: hold caps lock to dictate (hold mode). Mic button on the floating bar also starts dictation. Right-click tray icon for options/quit. Pipeline: record (sounddevice) then transcribe (Groq large-v3) then clean up (Groq LLM) then insert text into the active app (pyperclip + paste).

## Architecture / Key Files

dictate.py — main entry point, GUI event loop, hotkey + tray wiring.

stt/transcriber.py — transcribe(audio) returns a string. Converts the NumPy audio array to an in-memory WAV and sends it to Groq whisper-large-v3 with the STT_PROMPT hint. Module-level singleton Groq client.

config.py — all settings. GROQ_API_KEY is read from the environment (os.environ.get), NOT hardcoded. STT_PROMPT holds the vocabulary hint.

imla_ui/ — the active PySide6 UI.

Cleanup step — Groq LLM call that polishes the raw transcription.

## Environment

Python 3.14, global install on the machine, BUT the project now runs in a virtual environment (.venv/ in repo root, gitignored). Dependencies declared in requirements.txt (minimum-version pins). Verified: a fresh venv installs cleanly from it and all imports resolve. Always activate .venv before running, or you fall back to global Python.

## Dead Code / Gotchas

gui.py is a dead prototype (customtkinter-based, predates imla_ui/). Nothing imports it. It is NOT in requirements.txt. Safe to delete eventually; left in place for now.

docs/ contains local debug logs — gitignored, not committed.

No true streaming from Groq; transcription is per-recording (send full audio file, get text).

## Constraints (carried, still active)

Don't refactor/rewrite working source code unless explicitly asked. Don't change Python version, package versions, Whisper model, or device without discussion. Never put the API key in screenshots, chat, or source control (previously exposed key already rotated; current key is environment-only).

## Next Up (from the plan)

Phase 3 — Mode 2 (journal/chatterbox) on laptop: recording, topic organization, LLM chat, memory store. Then Phase 4 (searchable memory) and Phase 5 (Android PWA).

Update this file as the technical state changes, so a fresh session always has accurate ground truth.
