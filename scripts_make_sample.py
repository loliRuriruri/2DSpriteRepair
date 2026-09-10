"""Generate a tiny synthetic 4x4 spritesheet for smoke tests."""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "samples" / "synthetic_4x4.png"
cols, rows = 4, 4
cell = 64
sheet = Image.new("RGBA", (cols * cell, rows * cell), (0, 0, 0, 0))
draw = ImageDraw.Draw(sheet)
colors = [
    (80, 180, 255, 255),
    (255, 140, 180, 255),
    (120, 220, 140, 255),
    (255, 210, 90, 255),
]
for r in range(rows):
    for c in range(cols):
        i = r * cols + c
        x0, y0 = c * cell, r * cell
        # character body shifted per frame (overflows cell a bit on purpose)
        ox = 8 + (i % 3) * 3 - 3
        oy = 6 + (i % 4) * 2
        body = [x0 + ox + 18, y0 + oy + 10, x0 + ox + 42, y0 + oy + 48]
        draw.ellipse(body, fill=colors[i % 4])
        # head
        draw.ellipse([body[0] + 4, body[1] - 12, body[2] - 4, body[1] + 8], fill=colors[i % 4])
        # hanging VFX speck below (should be ignorable-ish)
        if i % 3 == 0:
            draw.ellipse([body[0] + 10, body[3] + 2, body[0] + 16, body[3] + 10], fill=(255, 255, 100, 180))
        # feet mark near bottom-center of body
        fx = (body[0] + body[2]) // 2
        fy = body[3]
        draw.rectangle([fx - 3, fy - 2, fx + 3, fy], fill=(40, 40, 80, 255))

OUT.parent.mkdir(parents=True, exist_ok=True)
sheet.save(OUT)
print("wrote", OUT, sheet.size)
