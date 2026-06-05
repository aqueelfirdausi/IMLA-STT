"""
test_groq.py — Quick sanity-check for your Groq API key.

Run this BEFORE the full voice agent to confirm:
  - The GROQ_API_KEY environment variable is set correctly
  - The key is valid and accepted by Groq
  - The model responds as expected

Usage:
    python test_groq.py
"""

import os
import sys


# ── Step 1: Check the key exists ─────────────────────────────────────────────

api_key = os.environ.get("GROQ_API_KEY", "")

if not api_key:
    print()
    print("ERROR: GROQ_API_KEY is not set in this terminal session.")
    print()
    print("Fix it by running ONE of these, then open a NEW terminal and retry:")
    print()
    print("  Permanent (recommended) — PowerShell:")
    print('    setx GROQ_API_KEY "gsk_your_key_here"')
    print()
    print("  Temporary (this session only) — PowerShell:")
    print('    $env:GROQ_API_KEY = "gsk_your_key_here"')
    print()
    sys.exit(1)

# Show a masked version so you can confirm it loaded without exposing the key.
masked = api_key[:8] + "..." + api_key[-4:]
print(f"✓ GROQ_API_KEY found: {masked}")


# ── Step 2: Import groq (tells you early if it's not installed) ───────────────

try:
    from groq import Groq
except ImportError:
    print()
    print("ERROR: The 'groq' package is not installed.")
    print("  Fix: pip install groq")
    sys.exit(1)


# ── Step 3: Make a test API call ──────────────────────────────────────────────

print("Sending test message to Groq API…")
print()

client = Groq(api_key=api_key)

try:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": "Say exactly this and nothing else: Hello from IMLA!",
            }
        ],
        max_tokens=30,
        temperature=0.0,   # deterministic — makes the reply predictable for testing
    )
except Exception as e:
    print(f"ERROR: Groq API call failed.")
    print(f"  Detail: {e}")
    print()
    print("Common causes:")
    print("  - The API key is invalid or has been revoked")
    print("  - No internet connection")
    print("  - Groq service is temporarily down (check status.groq.com)")
    sys.exit(1)


# ── Step 4: Print the result ──────────────────────────────────────────────────

reply = response.choices[0].message.content.strip()
model_used = response.model
tokens_used = response.usage.total_tokens

print("=" * 40)
print(f"  Model  : {model_used}")
print(f"  Tokens : {tokens_used}")
print(f"  Reply  : {reply}")
print("=" * 40)
print()
print("✓ Groq API is working. You're ready to run the voice agent.")
print()
