"""
test_tts.py -- Verifies Piper TTS works without needing the mic or Groq.

Synthesizes one sentence to a WAV file and confirms it was created.
Run: python test_tts.py
"""

import os
import sys
import subprocess
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

TEST_TEXT = "Piper voice is working."
OUTPUT_WAV = os.path.join("recordings", "test_tts_output.wav")

print("=" * 45)
print("  Piper TTS test")
print("=" * 45)

# Check 1: piper.exe exists
piper_path = os.path.abspath(config.PIPER_EXECUTABLE)
if not os.path.exists(piper_path):
    print(f"\n[FAIL] piper.exe not found at:\n  {piper_path}")
    print("\nFix: make sure tts\\piper\\piper.exe exists.")
    sys.exit(1)
print("[OK] piper.exe found")

# Check 2: voice model exists
model_path = os.path.abspath(config.PIPER_VOICE_MODEL)
config_path = os.path.abspath(config.PIPER_VOICE_CONFIG)

for label, path in [("voice .onnx", model_path), ("voice .json", config_path)]:
    if not os.path.exists(path):
        print(f"\n[FAIL] {label} not found at:\n  {path}")
        sys.exit(1)
    print(f"[OK] {label} found")

# Check 3: recordings/ folder
os.makedirs("recordings", exist_ok=True)
output_abs = os.path.abspath(OUTPUT_WAV)

# Run Piper
print(f"\nSynthesizing: \"{TEST_TEXT}\"")

cmd = [
    piper_path,
    "--model", model_path,
    "--config", config_path,
    "--output_file", output_abs,
]

try:
    result = subprocess.run(
        cmd,
        input=TEST_TEXT.encode("utf-8"),
        capture_output=True,
        timeout=30,
    )
except subprocess.TimeoutExpired:
    print("[FAIL] Piper timed out after 30 seconds.")
    sys.exit(1)
except Exception as e:
    print(f"[FAIL] Failed to launch Piper: {e}")
    sys.exit(1)

if result.returncode != 0:
    print(f"[FAIL] Piper exited with error:\n{result.stderr.decode()}")
    sys.exit(1)

# Verify the WAV
if not os.path.exists(output_abs):
    print("[FAIL] WAV file was not created.")
    sys.exit(1)

size = os.path.getsize(output_abs)
if size < 1000:
    print(f"[FAIL] WAV file is suspiciously small ({size} bytes).")
    sys.exit(1)

with wave.open(output_abs, "rb") as wf:
    duration_s = wf.getnframes() / wf.getframerate()

print(f"[OK] WAV file created: {os.path.basename(output_abs)}")
print(f"     Size    : {size:,} bytes")
print(f"     Duration: {duration_s:.1f} seconds")

os.remove(output_abs)
print(f"     (temp file deleted)")

print()
print("[OK] Piper TTS is working. Run  python main.py  to start the voice agent.")
print()
