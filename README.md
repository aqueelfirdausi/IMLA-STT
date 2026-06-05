# IMLA Voice Agent — Phase 1

A fully local voice assistant loop:
**Microphone → Whisper (STT) → Groq LLM → Piper (TTS) → Speakers**

---

## What you need before starting

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10 or 3.11 | 3.12 may have minor issues with faster-whisper |
| A Groq API key | free tier is fine | https://console.groq.com |
| A microphone | any | built-in laptop mic works |
| Speakers or headphones | any | |

---

## Step 1 — Get your Groq API key

1. Go to https://console.groq.com and create a free account.
2. Click **API Keys → Create API Key**.
3. Copy the key — you'll use it in Step 3.

---

## Step 2 — Install Python packages

Open a terminal (PowerShell or Command Prompt) in this folder and run:

```
pip install -r requirements.txt
```

This installs:
- `faster-whisper` — runs Whisper locally (no OpenAI API needed)
- `groq` — talks to the Groq LLM API
- `sounddevice` — records your mic and plays audio (no PyAudio drama)
- `numpy` — math for audio arrays

If you get an error about `sounddevice`, you may also need to install the
VC++ runtime from Microsoft. Search "Microsoft Visual C++ Redistributable".

---

## Step 3 — Set your Groq API key

**PowerShell (Windows):**
```powershell
$env:GROQ_API_KEY = "gsk_your_actual_key_here"
```

**Command Prompt (Windows):**
```
set GROQ_API_KEY=gsk_your_actual_key_here
```

> Tip: Add this to your PowerShell profile so you don't have to type it
> every time. Run `notepad $PROFILE` and add the line above.

---

## Step 4 — Install Piper TTS

Piper is the text-to-speech engine. It runs completely offline on your PC.

### 4a — Download Piper

1. Go to: https://github.com/rhasspy/piper/releases/latest
2. Download `piper_windows_amd64.zip` (for 64-bit Windows).
3. Extract it. You'll get a folder with `piper.exe` inside.
4. Copy the **entire extracted folder** into:
   ```
   IMLA-STT\tts\piper\
   ```
   So the path becomes: `IMLA-STT\tts\piper\piper.exe`

### 4b — Download the voice model

1. Go to: https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/lessac/medium
2. Download both files:
   - `en_US-lessac-medium.onnx`
   - `en_US-lessac-medium.onnx.json`
3. Put both files in: `IMLA-STT\tts\voices\`

Your `tts/` folder should look like this:
```
tts/
  piper/
    piper.exe
    (other piper files)
  voices/
    en_US-lessac-medium.onnx
    en_US-lessac-medium.onnx.json
  speaker.py
  __init__.py
```

---

## Step 5 — Run the agent

```
python main.py
```

The first run will download the Whisper "base" model (~145 MB) automatically.
After that, it starts instantly.

---

## How to use it

1. Wait for the `🎤 Listening…` prompt.
2. Speak naturally. Pause when you're done — silence ends your turn.
3. IMLA will think (Groq is fast, ~0.5 s) then speak back to you.
4. To quit, either say **"goodbye"** or press **Ctrl+C**.

---

## Folder layout

```
IMLA-STT/
  main.py          ← the main loop (run this)
  recorder.py      ← mic recording + silence detection
  config.py        ← ALL settings (edit this to tune behaviour)
  requirements.txt ← pip packages

  stt/
    transcriber.py ← faster-whisper speech-to-text
  llm/
    brain.py       ← Groq API calls
  tts/
    speaker.py     ← Piper TTS + playback
    piper/         ← Piper executable goes here
    voices/        ← .onnx voice files go here

  recordings/      ← temp WAV files (auto-created and deleted)
  docs/            ← notes and future docs
```

---

## Tuning (all settings are in config.py)

| Setting | What it does |
|---|---|
| `SILENCE_THRESHOLD` | Raise if background noise triggers false stop |
| `SILENCE_DURATION` | Seconds of quiet before your turn ends (default 1.5 s) |
| `CONVERSATION_MEMORY_TURNS` | How many exchanges the agent remembers (default 8) |
| `STT_MODEL` | Swap `"base"` to your fine-tuned model path later |
| `SYSTEM_PROMPT` | Change the agent's personality |

---

## Switching to your fine-tuned model (later)

When you have a fine-tuned Whisper model in this folder:

1. Open `config.py`
2. Change `STT_MODEL` from `"base"` to the path of your model folder, e.g.:
   ```python
   STT_MODEL = "./imla-whisper-finetuned"
   ```
3. That's it — no other changes needed.

---

## Troubleshooting

**"No module named sounddevice"**
→ Run `pip install sounddevice` and check the VC++ redistributable note in Step 2.

**Silence detection cuts off too early**
→ Increase `SILENCE_DURATION` in `config.py` (try `2.5`).

**Agent mishears words**
→ Try `STT_MODEL = "small"` in `config.py` for better accuracy (slower).

**Piper not found error**
→ Check that `piper.exe` is at `tts\piper\piper.exe` exactly.

**GROQ_API_KEY not set error**
→ Make sure you ran the `$env:GROQ_API_KEY = "..."` command in the *same*
  terminal window where you run `python main.py`.
