"""One-off: fix duplicated BY 43 credit on trailer_poster.png."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
POSTER = ROOT / "trailer_poster.png"


def main():
    im = Image.open(POSTER).convert("RGBA")
    w, h = im.size
    draw = ImageDraw.Draw(im)

    # Cover bottom-right credit zone (duplicate "BY 43 BY 43 INDUSTRIES")
    cover_w, cover_h = min(560, int(w * 0.45)), min(120, int(h * 0.16))
    x0, y0 = w - cover_w - 12, h - cover_h - 10
    # Blend with scene: sample a row above the bar
    sample_y = max(0, y0 - 6)
    strip = im.crop((x0, sample_y, x0 + cover_w, sample_y + 1))
    px = [strip.getpixel((x, 0)) for x in range(strip.width)]
    rs = sum(p[0] for p in px) / len(px)
    gs = sum(p[1] for p in px) / len(px)
    bs = sum(p[2] for p in px) / len(px)
    fill = (int(rs * 0.25 + 12), int(gs * 0.25 + 10), int(bs * 0.25 + 14), 255)
    draw.rounded_rectangle((x0 - 4, y0 - 4, x0 + cover_w + 4, y0 + cover_h + 4), radius=8, fill=fill)

    # Font
    font = None
    windir = __import__("os").environ.get("WINDIR", "C:\\Windows")
    for fname in ("segoeui.ttf", "arial.ttf", "calibri.ttf"):
        p = Path(windir) / "Fonts" / fname
        if p.is_file():
            try:
                font = ImageFont.truetype(str(p), size=28)
                break
            except OSError:
                pass
    if font is None:
        font = ImageFont.load_default()

    text = "BY 43 Industries"
    gold = (212, 175, 95, 255)
    shadow = (0, 0, 0, 200)
    tw, th = draw.textbbox((0, 0), text, font=font)[2:]
    tx = w - tw - 24
    ty = h - th - 28
    for ox, oy in ((2, 2), (1, 1)):
        draw.text((tx + ox, ty + oy), text, font=font, fill=shadow)
    draw.text((tx, ty), text, font=font, fill=gold)

    im.save(POSTER, "PNG")
    print("Updated", POSTER)


if __name__ == "__main__":
    main()
