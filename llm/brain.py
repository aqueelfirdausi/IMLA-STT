"""
llm/brain.py — Sends conversation history to Groq and returns the reply.
"""

from groq import Groq
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

# ── initialise the Groq client once ──────────────────────────────────────────
if not config.GROQ_API_KEY:
    raise EnvironmentError(
        "GROQ_API_KEY is not set. "
        "Run:  $env:GROQ_API_KEY = 'your-key-here'  (PowerShell)\n"
        "   or set GROQ_API_KEY=your-key-here       (Command Prompt)"
    )

_client = Groq(api_key=config.GROQ_API_KEY)

print("[LLM] Groq client ready.")


def get_reply(conversation_history: list[dict]) -> str:
    """
    Send the full conversation history to the LLM and return its reply.

    Parameters
    ----------
    conversation_history : list[dict]
        List of {"role": "user"/"assistant", "content": "..."} dicts.
        The system prompt is prepended automatically inside this function.

    Returns
    -------
    str
        The assistant's reply text.
    """
    # Always put the system prompt at the front.
    messages = [{"role": "system", "content": config.SYSTEM_PROMPT}] + conversation_history

    response = _client.chat.completions.create(
        model=config.GROQ_MODEL,
        messages=messages,
        temperature=config.LLM_TEMPERATURE,
        max_tokens=config.LLM_MAX_TOKENS,
    )

    reply = response.choices[0].message.content.strip()
    print(f"[LLM] Reply: {reply}")
    return reply
