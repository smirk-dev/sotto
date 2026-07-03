"""Render docs/social-preview.png (1280x640 GitHub social card) and docs/logo.png."""

import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "docs")
os.makedirs(OUT, exist_ok=True)

BG = (11, 11, 15)
BG2 = (22, 20, 34)
TEXT = (236, 236, 242)
MUTED = (150, 150, 162)
ACCENT = (157, 140, 255)
CHIPBG = (26, 24, 36)
CHIPBORDER = (60, 54, 96)
PILL_BG = (16, 16, 20)
BORDER = (40, 38, 52)

FB = "C:/Windows/Fonts/segoeuib.ttf"
FSB = "C:/Windows/Fonts/seguisb.ttf"
F = "C:/Windows/Fonts/segoeui.ttf"
FDEV = "C:/Windows/Fonts/Nirmala.ttc"


def logo_mark(size, bar_color=ACCENT, bg=(16, 16, 20)):
    """The app mark: rounded dark square with a violet waveform."""
    S = 4
    img = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2 * S, 2 * S, (size - 2) * S, (size - 2) * S],
                        radius=int(size * 0.26) * S, fill=bg)
    heights = [0.28, 0.5, 0.72, 0.92, 0.72, 0.5, 0.28]
    n = len(heights)
    bw = size * 0.66 / n
    x0 = size * 0.17
    cy = size / 2
    for i, hf in enumerate(heights):
        h = hf * size * 0.6
        x = x0 + i * bw
        d.rounded_rectangle([(x + bw * 0.25) * S, (cy - h / 2) * S,
                             (x + bw * 0.72) * S, (cy + h / 2) * S],
                            radius=bw * 0.2 * S, fill=bar_color)
    return img.resize((size, size), Image.LANCZOS)


def vgradient(w, h, top, bot):
    base = Image.new("RGB", (w, h), top)
    top_img = Image.new("RGB", (w, h), bot)
    mask = Image.new("L", (w, h))
    md = ImageDraw.Draw(mask)
    for y in range(h):
        md.line([(0, y), (w, y)], fill=int(255 * (y / h) ** 1.3))
    base.paste(top_img, (0, 0), mask)
    return base


def make_social():
    W, H, S = 1280, 640, 2
    img = vgradient(W * S, H * S, BG, BG2)
    d = ImageDraw.Draw(img)

    def fnt(p, s, idx=None):
        return ImageFont.truetype(p, s * S, index=idx) if idx is not None else ImageFont.truetype(p, s * S)

    # soft accent glow blob top-right
    glow = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([(W - 260) * S, (-160) * S, (W + 180) * S, (240) * S], fill=(157, 140, 255, 40))
    from PIL import ImageFilter
    glow = glow.filter(ImageFilter.GaussianBlur(80 * S))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    d = ImageDraw.Draw(img)

    # logo + wordmark
    mark = logo_mark(132).resize((132 * S, 132 * S), Image.LANCZOS)
    img.paste(mark, (96 * S, 92 * S), mark)
    d.text((250 * S, 104 * S), "Sotto", font=fnt(FB, 96), fill=TEXT)
    d.text((256 * S, 214 * S), "local dictation for Windows", font=fnt(FSB, 34), fill=ACCENT)

    # tagline
    d.text((100 * S, 300 * S), "Hold a hotkey, speak, and accurate text is typed",
           font=fnt(F, 38), fill=TEXT)
    d.text((100 * S, 352 * S), "wherever your cursor is — 100% on your device.",
           font=fnt(F, 38), fill=TEXT)

    # chips
    chips = [("Free & open-source", F), ("No cloud · no account", F),
             ("English + हिन्दी", FDEV), ("Whisper on your CPU", F)]
    x = 100
    y = 452
    for label, fp in chips:
        f = fnt(fp, 26, idx=0 if fp == FDEV else None)
        tw = d.textlength(label, font=f) / S
        cw = tw + 44
        d.rounded_rectangle([x * S, y * S, (x + cw) * S, (y + 52) * S], radius=26 * S,
                            fill=CHIPBG, outline=CHIPBORDER, width=1 * S)
        d.text(((x + 22) * S, (y + 10) * S), label, font=f, fill=(210, 205, 230))
        x += cw + 18

    # url
    d.text((100 * S, 560 * S), "github.com/smirk-dev/sotto", font=fnt(FSB, 28), fill=MUTED)

    # decorative waveform pill top-right (clear of the tagline)
    pw, pph = 300, 62
    px, py = W - pw - 80, 120
    d.rounded_rectangle([px * S, py * S, (px + pw) * S, (py + pph) * S], radius=(pph // 2) * S,
                        fill=PILL_BG, outline=BORDER, width=1 * S)
    nb = 26
    span = pw - 60
    bw = span / nb
    cy = py + pph / 2
    for i in range(nb):
        a = 0.5 + 0.5 * math.sin(i * 0.7)
        bh = 5 + a * (pph - 26)
        bx = px + 30 + i * bw
        d.rounded_rectangle([(bx + bw * 0.2) * S, (cy - bh / 2) * S,
                             (bx + bw * 0.68) * S, (cy + bh / 2) * S], radius=2 * S, fill=ACCENT)

    out = img.resize((W, H), Image.LANCZOS)
    p = os.path.join(OUT, "social-preview.png")
    out.save(p)
    print("wrote", p)


make_social()
logo_mark(256).save(os.path.join(OUT, "logo.png"))
print("wrote", os.path.join(OUT, "logo.png"))
