import subprocess
import sys
import time
from pathlib import Path

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BRAIN_DIR = Path(r"C:\Users\a4jud\.gemini\antigravity\brain\b5119880-0c34-4dde-90ea-a2e123b3394a")
BRAIN_DIR.mkdir(parents=True, exist_ok=True)

viewports = [
    (1920, 1080, "screenshot_1920x1080.png"),
    (1440, 900, "screenshot_1440x900.png"),
    (1280, 720, "screenshot_1280x720.png"),
]

for w, h, fname in viewports:
    out_path = BRAIN_DIR / fname
    cmd = [
        CHROME,
        "--headless=new",
        "--hide-scrollbars",
        f"--window-size={w},{h}",
        f"--screenshot={out_path}",
        "--virtual-time-budget=3000",
        "http://127.0.0.1:5190/?sample=1",
    ]
    print(f"Capturing {w}x{h} -> {out_path.name}...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if out_path.is_file():
        print(f"  [OK] Saved: {out_path} ({out_path.stat().st_size} bytes)")
    else:
        print(f"  [FAIL] Did not create {out_path}. Stderr: {res.stderr}")

print("Visual QA capture complete!")
