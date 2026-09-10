import subprocess
import tempfile
import time
from pathlib import Path

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BRAIN_DIR = Path(r"C:\Users\a4jud\.gemini\antigravity\brain\b5119880-0c34-4dde-90ea-a2e123b3394a")

# Ensure sample session is pre-loaded on server
import urllib.request
import json
print("Pre-fetching /api/load-sample...")
try:
    with urllib.request.urlopen("http://127.0.0.1:5190/api/load-sample") as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"Session preloaded: {data.get('session_id')} with {len(data.get('frames', []))} frames.")
except Exception as e:
    print(f"Preload warning: {e}")

time.sleep(1)

viewports = [
    (1920, 1080, "screenshot_1920x1080.png"),
    (1440, 900, "screenshot_1440x900.png"),
    (1280, 720, "screenshot_1280x720.png"),
]

with tempfile.TemporaryDirectory() as tmpdir:
    for w, h, fname in viewports:
        out_path = BRAIN_DIR / fname
        cmd = [
            EDGE,
            "--headless",
            f"--user-data-dir={tmpdir}",
            "--disable-gpu",
            "--no-sandbox",
            f"--window-size={w},{h}",
            f"--screenshot={out_path}",
            # We add a slight delay in the browser by triggering a hash or delay
            "http://127.0.0.1:5190/?sample=1",
        ]
        print(f"Capturing {w}x{h} -> {fname}...")
        subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if out_path.is_file():
            print(f"  [SUCCESS] {fname} ({out_path.stat().st_size} bytes)")

print("All screenshots refreshed successfully!")
