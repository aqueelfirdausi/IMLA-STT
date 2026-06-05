# IMLA-STT — Project Plan & Vision

> Companion to `IMLA-STT_HANDOFF.md`. The handoff captures the *current technical state*.
> This file captures the *mission, vision, and roadmap* — why this app exists and where it's going.
> Keep both in the repo. Hand both to any new AI session.

---

## 0. The Core Mission (the "why")

**The real problem this app solves: existing speech-to-text tools do not transcribe the user's accent accurately.**

Everything else in this plan — the two modes, the phone version, the memory, the hosting — is in service of this one goal. If a decision doesn't move toward *accurate transcription of the user's voice*, it is secondary.

This is not a throwaway learning project. The user builds small tools to learn AI **and** to have genuinely powerful tools in their workspace. IMLA-STT is meant to be one of the **real, relied-upon tools** in that library.

---

## 1. The Accuracy Problem (priority #1) — ✅ SOLVED

**Status: RESOLVED.** Swapping the local faster-whisper `small` model for Groq's hosted `whisper-large-v3`, plus the prompt/vocabulary hint, fixed the accent accuracy problem. Tested successfully against accented speech in noisy conditions (full-speed fan + background noise) and transcription was accurate. Fine-tuning (the longer-term lever below) is NOT needed for now.

**Levers, in order of effort:**

1. ✅ **Upgrade the model — DONE.** Moved from `small` to Groq's `whisper-large-v3`. Runs on Groq's hardware, far better at accents. This was the biggest win.
2. ✅ **Prompt/context parameter — DONE.** `STT_PROMPT` in config.py feeds Groq's Whisper a vocabulary hint (~224 tokens max) to bias toward names, technical terms, and domain vocabulary.
3. ⏸️ **Fine-tune on the user's own voice — NOT NEEDED for now.** Parked unless real-world use later reveals gaps that large-v3 + prompting can't close.

---

## 2. The Product Vision — Two Modes

IMLA-STT is **one app with two modes**:

### Mode 1 — Simple Dictation (laptop)
- Speak → cleaned-up text inserted into **any app** in the workspace (browser, editor, terminal, etc.).
- Current working tool (PySide6 + Groq large-v3 transcription + Groq cleanup + text insertion).
- **The system-wide "type into any app" feature is laptop-only** — see platform notes.

### Mode 2 — "Chatterbox" / Journal Assistant (later phase)
- A voice-driven journal/assistant that **records daily activities**.
- Has **intelligence**: logs and organizes entries **by topic**, like a smart voice recorder.
- Has a **brain** (LLM) — can **chat back**.
- Has **memory** — remembers past entries and context.
- **Note:** "Chatterbox" here means *better dictation / the journal mode* — **not** text-to-speech / the app talking back.

---

## 3. Platform Reality (verified)

| Target | Verdict | Notes |
|---|---|---|
| **Laptop (PySide6)** | Keep as-is | Only place the system-wide "type into any app" dictation can work. |
| **Phone (Android PWA)** | Realistic for Mode 2 | Browser recording works on Chrome for Android. Foreground recording only — no silent background listening. Transcription via Groq's hosted Whisper. The laptop "type into any app" feature does NOT survive the move. |
| **GitHub** | No roadblock | Pure version control. Do this. |
| **Hosting (Vercel etc.)** | For the PWA only | Hosts the future PWA front-end, not the desktop app. |

**Key mental model:** the laptop app and the phone PWA are **two front-ends sharing the same idea/backend**, not one codebase ported across platforms.

### Verified technical facts (as of June 2026)
- Groq runs a hosted, OpenAI-compatible Whisper endpoint (`whisper-large-v3` and a faster `turbo` variant). Send a complete audio file, get text back.
- No true streaming via REST — record in short chunks (~5s) and transcribe each.
- File size cap is 25 MB per request (or pass a URL).
- Android Chrome fully supports browser mic recording (MediaRecorder). User is on Android.

---

## 4. Powerful-Tool Idea (parked for the right phase)

**Searchable memory across journal mode** — ask *"what did I say about the X project last week?"* and pull from past entries. The difference between a voice recorder and an actual second brain. Enabled by storing transcripts with dates/topics so they're queryable.

---

## 5. How We Work (process rules)

- **Phased / sprint-based.** No abrupt, sweeping work. Build in stages.
- **Consultation before building.** Agree on direction *before* writing code.
- **UI mockup exists.** The user has a UI mockup/skeleton and will hand it over when a phase needs it.
- **Honesty over guessing.** If a detail is unconfirmed, say "Needs verification" rather than inventing it.

---

## 6. Phase Order

1. ✅ **Phase 1 — Fix accuracy (the mission). DONE.** large-v3 swapped in, prompt hint wired in, tested successfully against accented speech in noisy conditions. Accent accuracy mission solved.
2. ⬜ **Phase 2 — Solidify the laptop tool.** GitHub repo, `requirements.txt`, persistent env config, virtual environment.
3. ⬜ **Phase 3 — Mode 2 (journal/chatterbox) on laptop.** Recording, topic organization, LLM chat, memory store.
4. ⬜ **Phase 4 — Searchable memory.** Make past entries queryable (the "second brain").
5. ⬜ **Phase 5 — Android PWA.** Web front-end + Groq transcription + Vercel hosting for journal mode on the phone.

---

## 7. Carried-Over Constraints

- Don't refactor/rewrite working source code unless explicitly asked.
- Don't change Python version, package versions, Whisper model, or device without discussion.
- Never put API keys in screenshots, chat, or source control. (The previously exposed Groq key has been rotated.)

---

*Living plan. Update as phases complete or decisions change, so the mission doesn't drift.*
