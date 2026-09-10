from pathlib import Path
import re

app_js = Path(r"C:\TEST\MikuChat-Lab\projects\SpriteRepair\app\app.js")
code = app_js.read_text(encoding="utf-8")

# Add notifyUser helper after status()
helper = '''
  function notifyUser(msg, isError = false) {
    console.warn("[SpriteRepair]", msg);
    status(msg);
    const hud = $("stageHud");
    if (hud && isError) {
      hud.style.borderColor = "var(--danger)";
      setTimeout(() => { if (hud) hud.style.borderColor = "var(--border)"; }, 3500);
    }
  }
'''

if "function notifyUser(" not in code:
    code = code.replace(
        '  const status = (msg) => { $("status").textContent = msg; };\n',
        '  const status = (msg) => { $("status").textContent = msg; };\n' + helper
    )

# Replace alerts
code = re.sub(r'\balert\(', 'notifyUser(', code)

app_js.write_text(code, encoding="utf-8")
print("Replaced all alert() calls with notifyUser()!")
