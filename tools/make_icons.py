"""Generuje ikony PWA dla FASARO Zlecenia (Pillow)."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "docs" / "icons"
OUT.mkdir(parents=True, exist_ok=True)

BG = (20, 23, 27, 255)
CARD = (27, 32, 39, 255)
GOLD = (195, 154, 92, 255)
GOLD_LIGHT = (220, 179, 119, 255)

FONT_BOLD = r"C:\Windows\Fonts\arialbd.ttf"


def draw_icon(size: int, maskable: bool = False) -> Image.Image:
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), BG)
    draw = ImageDraw.Draw(img)

    if maskable:
        # Pełne tło, treść w bezpiecznej strefie (~80%).
        pad = int(s * 0.16)
    else:
        pad = int(s * 0.045)
        radius = int(s * 0.22)
        draw.rounded_rectangle(
            [pad, pad, s - pad, s - pad],
            radius=radius,
            fill=CARD,
            outline=(195, 154, 92, 90),
            width=max(2, int(s * 0.006)),
        )
        pad = int(s * 0.12)

    inner = s - pad * 2
    font = ImageFont.truetype(FONT_BOLD, int(inner * 0.56))

    text = "F"
    cx = s / 2
    cy = s / 2 - inner * 0.035
    draw.text((cx, cy), text, font=font, fill=GOLD_LIGHT, anchor="mm")

    box = draw.textbbox((cx, cy), text, font=font, anchor="mm")
    th = box[3] - box[1]

    # Złota kreska pod literą — sygnatura marki.
    line_w = int(inner * 0.30)
    line_h = max(3, int(s * 0.011))
    ly = cy + th / 2 + inner * 0.055
    draw.rounded_rectangle(
        [cx - line_w / 2, ly, cx + line_w / 2, ly + line_h],
        radius=line_h / 2,
        fill=GOLD,
    )

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    draw_icon(512).save(OUT / "icon-512.png")
    draw_icon(192).save(OUT / "icon-192.png")
    draw_icon(512, maskable=True).save(OUT / "icon-maskable-512.png")
    draw_icon(180).save(OUT / "apple-touch-icon.png")
    icon32 = draw_icon(64)
    icon32 = icon32.resize((32, 32), Image.LANCZOS)
    icon32.save(OUT / "favicon-32.png")
    print("Ikony zapisane w", OUT)
    for path in sorted(OUT.glob("*.png")):
        print(" -", path.name, path.stat().st_size, "B")


if __name__ == "__main__":
    main()
