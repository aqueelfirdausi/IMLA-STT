"""
main.py — The main conversation loop for the IMLA voice agent.

Flow each turn:
  1. recorder.py  → listens to mic, stops on silence → raw audio
  2. stt/          → faster-whisper transcribes audio → text
  3. llm/          → Groq API generates reply → text
  4. tts/          → Piper speaks reply aloud
  5. Repeat until user says goodbye or presses Ctrl+C.
"""

import sys

import config
from recorder import record_until_silence
from stt.transcriber import transcribe
from llm.brain import get_reply
from tts.speaker import speak


def is_goodbye(text: str) -> bool:
    """Return True if the user's text contains a goodbye phrase."""
    lower = text.lower()
    return any(phrase in lower for phrase in config.GOODBYE_PHRASES)


def trim_history(history: list[dict]) -> list[dict]:
    """
    Keep only the last N turns of conversation to stay within token limits.
    Each turn = 1 user message + 1 assistant message = 2 entries.
    """
    max_entries = config.CONVERSATION_MEMORY_TURNS * 2
    return history[-max_entries:]


def main() -> None:
    print("=" * 50)
    print("  IMLA Voice Agent  —  Phase 1")
    print("  Say 'goodbye' or press Ctrl+C to quit.")
    print("=" * 50)

    # Greeting on startup.
    greeting = "Hello! I'm IMLA, your voice assistant. How can I help you today?"
    print(f"\n[IMLA] {greeting}")
    speak(greeting)

    # conversation_history stores dicts like:
    #   {"role": "user",      "content": "What is the capital of France?"}
    #   {"role": "assistant", "content": "Paris."}
    conversation_history: list[dict] = []

    try:
        while True:
            print()  # blank line for readability

            # ── Step 1: Record ─────────────────────────────────────────────
            audio = record_until_silence()

            if audio is None:
                print("[Main] No speech detected, listening again…")
                continue

            # ── Step 2: Transcribe ─────────────────────────────────────────
            user_text = transcribe(audio)

            if not user_text.strip():
                print("[Main] Empty transcription, listening again…")
                continue

            # ── Step 3: Check for goodbye ──────────────────────────────────
            if is_goodbye(user_text):
                farewell = "Goodbye! It was great talking with you."
                print(f"[IMLA] {farewell}")
                speak(farewell)
                break

            # ── Step 4: Add user message to history ────────────────────────
            conversation_history.append({"role": "user", "content": user_text})
            conversation_history = trim_history(conversation_history)

            # ── Step 5: Get LLM reply ──────────────────────────────────────
            reply = get_reply(conversation_history)

            # ── Step 6: Add assistant reply to history ─────────────────────
            conversation_history.append({"role": "assistant", "content": reply})

            # ── Step 7: Speak the reply ────────────────────────────────────
            print(f"[IMLA] {reply}")
            speak(reply)

    except KeyboardInterrupt:
        print("\n\n[Main] Ctrl+C detected. Goodbye!")
        speak("Goodbye!")


if __name__ == "__main__":
    main()
