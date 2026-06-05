"""
dictation/cleanup.py -- AI grammar/punctuation cleanup via Groq.

Sends raw Whisper output to the LLM with a strict "clean only, add nothing"
prompt. Falls back to the raw text if the API call fails or times out.
"""

import concurrent.futures
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

_CLEANUP_SYSTEM_PROMPT = """\
You are a transcription editor.
The user will give you raw speech-to-text output.
Your ONLY job is to correct grammar, punctuation, capitalisation, and remove
obvious filler words ("um", "uh", "like", "you know") and false starts.
Return ONLY the corrected text -- no explanation, no quotes, nothing else.
If the input is already clean, return it unchanged."""


def _call_groq(raw: str) -> str:
    from groq import Groq
    client = Groq(api_key=config.GROQ_API_KEY)
    response = client.chat.completions.create(
        model=config.GROQ_MODEL,
        messages=[
            {"role": "system", "content": _CLEANUP_SYSTEM_PROMPT},
            {"role": "user",   "content": raw},
        ],
        max_tokens=400,
        temperature=0.1,   # low temperature = deterministic cleanup, no creativity
    )
    return response.choices[0].message.content.strip()


def cleanup(raw: str) -> str:
    """
    Return cleaned text. Falls back to `raw` on any error or timeout.

    Uses a ThreadPoolExecutor so we can enforce DICTATION_CLEANUP_TIMEOUT
    without blocking the calling thread indefinitely.
    """
    if not config.GROQ_API_KEY:
        return raw   # no key -- skip silently

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_call_groq, raw)
        try:
            return future.result(timeout=config.DICTATION_CLEANUP_TIMEOUT)
        except concurrent.futures.TimeoutError:
            print("[Cleanup] Groq timed out -- using raw text.")
            return raw
        except Exception as exc:
            print(f"[Cleanup] Groq error ({exc}) -- using raw text.")
            return raw
