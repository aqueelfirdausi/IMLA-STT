"""
gui.py -- Desktop GUI for the IMLA voice agent.

Entry point: python gui.py

Architecture:
  - UI runs on the main thread (customtkinter requirement).
  - Audio pipeline (record -> STT -> LLM -> TTS) runs on a daemon thread.
  - The background thread never touches tkinter widgets directly; it puts
    messages into a queue.Queue. The UI thread drains that queue every 50 ms
    via root.after(), keeping the window fully responsive at all times.
"""

import customtkinter as ctk
import threading
import queue
import os
import sys

import config

# ── Appearance (must be set before any widget is created) ────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ─────────────────────────────────────────────────────────────────────────────
#  Main application window
# ─────────────────────────────────────────────────────────────────────────────

class IMLAApp(ctk.CTk):

    # Colour coding for the status indicator dot.
    _STATUS_COLORS = {
        "loading":   "#888888",   # grey
        "idle":      "#4CAF50",   # green
        "listening": "#F44336",   # red
        "thinking":  "#FF9800",   # orange
        "speaking":  "#2196F3",   # blue
        "error":     "#E91E63",   # pink-red
    }

    def __init__(self):
        super().__init__()

        self.title("IMLA Voice Agent")
        self.geometry("740x620")
        self.minsize(520, 440)

        # Thread -> UI message queue.
        # Messages are tuples whose first element is a string "verb".
        self._q: queue.Queue = queue.Queue()

        # Conversation history shared between UI and audio thread.
        # Accessed only on the audio thread after init, so no lock needed.
        self._history: list[dict] = []

        # Whether the continuous listen loop is running.
        self._running = False
        self._audio_thread: threading.Thread | None = None

        # Build layout, then load models in background.
        self._build_ui()
        self._poll_queue()           # start the 50ms polling loop
        self._post_startup_greeting()
        threading.Thread(target=self._load_models, daemon=True).start()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)   # transcript row expands

        # -- Header bar -------------------------------------------------------
        hdr = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 0))
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr, text="IMLA",
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, sticky="w")

        # Status: coloured dot + text
        self._status_dot = ctk.CTkLabel(hdr, text="  --",
                                        font=ctk.CTkFont(size=13),
                                        text_color="#888888")
        self._status_dot.grid(row=0, column=1, sticky="w", padx=(10, 0))

        self._settings_btn = ctk.CTkButton(
            hdr, text="Settings", width=80, height=28,
            font=ctk.CTkFont(size=12),
            fg_color="transparent", border_width=1,
            command=self._toggle_settings)
        self._settings_btn.grid(row=0, column=2, sticky="e")

        # -- Transcript (scrollable) ------------------------------------------
        self._transcript = ctk.CTkScrollableFrame(self, corner_radius=8)
        self._transcript.grid(row=1, column=0, sticky="nsew", padx=16, pady=12)
        self._transcript.grid_columnconfigure(0, weight=1)
        self._t_row = 0   # next available row inside the scrollable frame

        # -- Settings panel (hidden until toggled) ----------------------------
        self._settings_frame = ctk.CTkFrame(self, corner_radius=8)
        self._settings_visible = False
        self._build_settings_panel()

        # -- Bottom: Talk button ----------------------------------------------
        btm = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        btm.grid(row=3, column=0, pady=(0, 18))

        self._talk_btn = ctk.CTkButton(
            btm, text="TALK",
            width=150, height=60, corner_radius=30,
            font=ctk.CTkFont(size=20, weight="bold"),
            state="disabled",
            command=self._toggle_talk)
        self._talk_btn.pack()

    def _build_settings_panel(self):
        f = self._settings_frame
        f.grid_columnconfigure(1, weight=1)

        # Voice picker
        ctk.CTkLabel(f, text="Voice:", anchor="w").grid(
            row=0, column=0, padx=(14, 8), pady=(10, 4), sticky="w")

        voices = self._scan_voices()
        current = os.path.basename(config.PIPER_VOICE_MODEL)
        self._voice_var = ctk.StringVar(
            value=current if current in voices else (voices[0] if voices else ""))
        self._voice_menu = ctk.CTkOptionMenu(
            f,
            values=voices if voices else ["(no voices found)"],
            variable=self._voice_var,
            command=self._on_voice_change,
            width=280)
        self._voice_menu.grid(row=0, column=1, padx=(0, 14), pady=(10, 4), sticky="w")

        # Personality prompt
        ctk.CTkLabel(f, text="Personality:", anchor="nw").grid(
            row=1, column=0, padx=(14, 8), pady=(6, 4), sticky="nw")

        self._prompt_box = ctk.CTkTextbox(
            f, height=110, wrap="word", font=ctk.CTkFont(size=12))
        self._prompt_box.grid(
            row=1, column=1, padx=(0, 14), pady=(6, 4), sticky="ew")
        self._prompt_box.insert("0.0", config.SYSTEM_PROMPT.strip())

        ctk.CTkButton(f, text="Save", width=72, height=28,
                      command=self._save_settings).grid(
            row=2, column=1, padx=(0, 14), pady=(4, 12), sticky="e")

    # ── Settings helpers ──────────────────────────────────────────────────────

    def _scan_voices(self) -> list[str]:
        voices_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "tts", "voices")
        if not os.path.isdir(voices_dir):
            return []
        return sorted(f for f in os.listdir(voices_dir) if f.endswith(".onnx"))

    def _toggle_settings(self):
        if self._settings_visible:
            self._settings_frame.grid_forget()
            self._settings_visible = False
        else:
            self._settings_frame.grid(
                row=2, column=0, sticky="ew", padx=16, pady=(0, 4))
            self._settings_visible = True

    def _on_voice_change(self, selection: str):
        voices_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "tts", "voices")
        config.PIPER_VOICE_MODEL  = os.path.join(voices_dir, selection)
        config.PIPER_VOICE_CONFIG = config.PIPER_VOICE_MODEL + ".json"
        self._sys_note(f"Voice changed to {selection}")

    def _save_settings(self):
        config.SYSTEM_PROMPT = self._prompt_box.get("0.0", "end").strip()
        self._sys_note("Personality saved for this session.")

    # ── Model loading (background thread) ─────────────────────────────────────

    def _load_models(self):
        """Import STT transcriber (triggers Whisper model download/load)."""
        self._q.put(("status", "loading", "Loading Whisper model..."))
        try:
            from stt.transcriber import transcribe  # noqa: F401 -- side effect load
            self._q.put(("status", "idle", "Ready"))
            self._q.put(("enable_talk",))
        except Exception as exc:
            self._q.put(("status", "error", f"Load error: {exc}"))
            self._q.put(("sys_note", f"Model load failed: {exc}"))

    # ── Talk button ───────────────────────────────────────────────────────────

    def _toggle_talk(self):
        if not self._running:
            self._running = True
            self._talk_btn.configure(
                text="STOP",
                fg_color="#C0392B",
                hover_color="#A93226")
            self._audio_thread = threading.Thread(
                target=self._pipeline_loop, daemon=True)
            self._audio_thread.start()
        else:
            self._running = False
            # Button text/colour will reset once the audio thread notices
            # _running is False and exits.

    # ── Audio pipeline loop (background thread) ───────────────────────────────

    def _pipeline_loop(self):
        """
        Continuous listen -> transcribe -> LLM -> speak loop.
        Runs entirely on a daemon thread. Communicates with the UI via self._q.
        Exits when self._running is set to False (STOP pressed or goodbye said).
        """
        from recorder import record_until_silence
        from stt.transcriber import transcribe
        from llm.brain import get_reply
        from tts.speaker import speak

        while self._running:

            # ── Record ───────────────────────────────────────────────────────
            self._q.put(("status", "listening", "Listening..."))
            audio = record_until_silence()

            if not self._running:
                break

            if audio is None:
                # Nothing detected; loop back and listen again.
                continue

            # ── Transcribe ───────────────────────────────────────────────────
            self._q.put(("status", "thinking", "Transcribing..."))
            user_text = transcribe(audio)

            if not user_text.strip():
                continue

            self._q.put(("user_msg", user_text))

            # ── Goodbye check ─────────────────────────────────────────────────
            if any(p in user_text.lower() for p in config.GOODBYE_PHRASES):
                self._running = False
                farewell = "Goodbye! It was a pleasure."
                self._q.put(("imla_msg", farewell))
                self._q.put(("status", "speaking", "Speaking..."))
                speak(farewell)
                break

            # ── LLM ───────────────────────────────────────────────────────────
            self._q.put(("status", "thinking", "Thinking..."))
            self._history.append({"role": "user", "content": user_text})
            max_entries = config.CONVERSATION_MEMORY_TURNS * 2
            self._history = self._history[-max_entries:]

            try:
                reply = get_reply(self._history)
            except Exception as exc:
                self._q.put(("sys_note", f"LLM error: {exc}"))
                self._q.put(("status", "idle", "Ready"))
                continue

            self._history.append({"role": "assistant", "content": reply})

            # ── Speak ─────────────────────────────────────────────────────────
            self._q.put(("imla_msg", reply))
            self._q.put(("status", "speaking", "Speaking..."))
            speak(reply)

        # Loop exited -- reset button and status from the UI thread.
        self._q.put(("status", "idle", "Ready"))
        self._q.put(("reset_talk_btn",))

    # ── Queue polling (UI thread, every 50 ms) ────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                msg = self._q.get_nowait()
                self._dispatch(msg)
        except queue.Empty:
            pass
        finally:
            self.after(50, self._poll_queue)

    def _dispatch(self, msg: tuple):
        verb = msg[0]
        if verb == "status":
            _, state, text = msg
            color = self._STATUS_COLORS.get(state, "#888888")
            self._status_dot.configure(text=f"  {text}", text_color=color)
        elif verb == "user_msg":
            self._bubble_user(msg[1])
        elif verb == "imla_msg":
            self._bubble_imla(msg[1])
        elif verb == "sys_note":
            self._sys_note(msg[1])
        elif verb == "enable_talk":
            self._talk_btn.configure(state="normal")
        elif verb == "reset_talk_btn":
            self._talk_btn.configure(
                text="TALK",
                fg_color=("#3B8ED0", "#1F6AA5"),
                hover_color=("#36719F", "#144870"))

    # ── Transcript helpers ────────────────────────────────────────────────────

    def _bubble_user(self, text: str):
        """Right-aligned blue bubble for the user's words."""
        outer = ctk.CTkFrame(self._transcript, fg_color="transparent")
        outer.grid(row=self._t_row, column=0, sticky="e", padx=(60, 10), pady=(4, 0))

        ctk.CTkLabel(outer, text="You",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#7EB8F7").pack(anchor="e")

        bubble = ctk.CTkFrame(outer, fg_color="#1A5276", corner_radius=14)
        bubble.pack(anchor="e")
        ctk.CTkLabel(bubble, text=text, wraplength=400,
                     justify="right", font=ctk.CTkFont(size=13),
                     padx=14, pady=9).pack()

        self._t_row += 1
        self._scroll_bottom()

    def _bubble_imla(self, text: str):
        """Left-aligned green-tinted bubble for IMLA's replies."""
        outer = ctk.CTkFrame(self._transcript, fg_color="transparent")
        outer.grid(row=self._t_row, column=0, sticky="w", padx=(10, 60), pady=(4, 0))

        ctk.CTkLabel(outer, text="IMLA",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#82E0AA").pack(anchor="w")

        bubble = ctk.CTkFrame(outer, fg_color="#1E4D2B", corner_radius=14)
        bubble.pack(anchor="w")
        ctk.CTkLabel(bubble, text=text, wraplength=400,
                     justify="left", font=ctk.CTkFont(size=13),
                     padx=14, pady=9).pack()

        self._t_row += 1
        self._scroll_bottom()

    def _sys_note(self, text: str):
        """Centred italic grey note — system events, not conversation."""
        lbl = ctk.CTkLabel(self._transcript, text=text,
                           font=ctk.CTkFont(size=11, slant="italic"),
                           text_color="#555555")
        lbl.grid(row=self._t_row, column=0, pady=(6, 2))
        self._t_row += 1
        self._scroll_bottom()

    def _scroll_bottom(self):
        self.after(60, lambda: self._transcript._parent_canvas.yview_moveto(1.0))

    def _post_startup_greeting(self):
        self._sys_note("Starting up -- loading Whisper model, please wait...")


# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = IMLAApp()
    app.mainloop()


if __name__ == "__main__":
    main()
