"""Render docs/demo.gif — a polished animated demo of Sotto live-typing into an
editor, showcasing English + Hindi. Rendered at 2x and downscaled for crisp text.
No app/audio needed; a faithful mock of the real overlay + live-typing behavior."""

import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "docs")
os.makedirs(OUT, exist_ok=True)

W, H = 960, 560
S = 2  # supersample
BG = (11, 11, 15)
CARD = (23, 23, 29)
BAR = (30, 30, 38)
TEXT = (234, 234, 240)
MUTED = (138, 138, 150)
ACCENT = (157, 140, 255)
ACCENT2 = (124, 110, 210)
BORDER = (38, 38, 46)
OK = (123, 201, 138)
PILL_BG = (16, 16, 20)

F = "C:/Windows/Fonts/segoeui.ttf"
FB = "C:/Windows/Fonts/segoeuib.ttf"
FSB = "C:/Windows/Fonts/seguisb.ttf"
FDEV = "C:/Windows/Fonts/Nirmala.ttc"


def font(path, size, index=None):
    if index is not None:
        return ImageFont.truetype(path, size * S, index=index)
    return ImageFont.truetype(path, size * S)


f_title = font(FSB, 15)
f_body = font(F, 23)
f_body_b = font(FB, 23)
f_dev = font(FDEV, 24, index=0)
f_pill = font(FSB, 15)
f_cap = font(FSB, 15)
f_small = font(F, 13)


def rrect(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle([c * S for c in box], radius=r * S, fill=fill, outline=outline,
                        width=width * S)


def draw_frame(typed_en, typed_dev, caret_on, state, wave_phase, show_pill, cap):
    img = Image.new("RGB", (W * S, H * S), BG)
    d = ImageDraw.Draw(img)

    # ---- editor card ----
    ex, ey, ew, eh = 70, 60, W - 140, 330
    rrect(d, (ex, ey, ex + ew, ey + eh), 16, fill=CARD, outline=BORDER, width=1)
    # title bar
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([(ex + 20 + i * 20) * S, (ey + 18) * S,
                   (ex + 20 + i * 20 + 11) * S, (ey + 18 + 11) * S], fill=c)
    d.text(((ex + ew / 2 - 44) * S, (ey + 14) * S), "Notes — meeting.txt", font=f_title, fill=MUTED)
    d.line([(ex + 1) * S, (ey + 46) * S, (ex + ew - 1) * S, (ey + 46) * S], fill=BORDER, width=S)

    # ---- typed text ----
    tx, ty = ex + 26, ey + 70
    lh = 40
    d.text((tx * S, ty * S), typed_en, font=f_body, fill=TEXT)
    line2_y = ty + lh
    caret_x = tx + d.textlength(typed_en, font=f_body) / S
    caret_y = ty
    if typed_dev:
        d.text((tx * S, line2_y * S), typed_dev, font=f_dev, fill=TEXT)
        caret_x = tx + d.textlength(typed_dev, font=f_dev) / S
        caret_y = line2_y
    if caret_on:
        d.rectangle([caret_x * S, caret_y * S, (caret_x + 1.5) * S, (caret_y + 27) * S], fill=ACCENT)

    # hint under editor
    d.text((ex * S, (ey + eh + 22) * S),
           "Hold  Ctrl + Win  and speak — text appears at your cursor, in any app.",
           font=f_small, fill=MUTED)

    # ---- recording pill ----
    if show_pill:
        pw, ph = 250, 54
        px, py = (W - pw) // 2, H - ph - 40
        rrect(d, (px, py, px + pw, py + ph), ph // 2, fill=PILL_BG, outline=BORDER, width=1)
        if state == "listening":
            nbars = 22
            span = pw - 60
            bw = span / nbars
            cy = py + ph / 2
            for i in range(nbars):
                a = 0.5 + 0.5 * math.sin(wave_phase * 0.5 + i * 0.6)
                bh = 4 + a * (ph - 24)
                bx = px + 30 + i * bw
                d.rounded_rectangle([(bx + bw * 0.2) * S, (cy - bh / 2) * S,
                                     (bx + bw * 0.7) * S, (cy + bh / 2) * S],
                                    radius=2 * S, fill=ACCENT)
        elif state == "transcribing":
            cy = py + ph / 2
            for i in range(3):
                a = 0.35 + 0.65 * max(0.0, math.sin(wave_phase * 0.4 - i * 0.6)) ** 2
                col = tuple(int(PILL_BG[j] + (ACCENT[j] - PILL_BG[j]) * a) for j in range(3))
                d.ellipse([(px + pw / 2 - 22 + i * 18) * S, (cy - 5) * S,
                           (px + pw / 2 - 22 + i * 18 + 10) * S, (cy + 5) * S], fill=col)
        elif state == "inserted":
            txt = "inserted"
            tw = d.textlength(txt, font=f_pill) / S
            gap = 14
            total = 16 + gap + tw
            gx = px + pw / 2 - total / 2
            cy = py + ph / 2
            # vector checkmark (glyph fonts render tofu)
            d.line([(gx) * S, (cy + 1) * S, (gx + 5) * S, (cy + 6) * S], fill=OK, width=3 * S)
            d.line([(gx + 5) * S, (cy + 6) * S, (gx + 14) * S, (cy - 6) * S], fill=OK, width=3 * S)
            d.text(((gx + 16 + gap) * S, (cy - 11) * S), txt, font=f_pill, fill=OK)

    # ---- caption ----
    if cap:
        cw = d.textlength(cap, font=f_cap) / S
        d.text(((W / 2 - cw / 2) * S, (H - 26) * S), cap, font=f_cap, fill=MUTED)

    return img.resize((W, H), Image.LANCZOS)


EN = "Meeting notes: ship the beta on Friday and email the whole team."
DEV = "कल डेमो तैयार करना है और सबको भेजना है।"

frames, durations = [], []


def add(img, ms):
    frames.append(img)
    durations.append(ms)


ph = 0
# intro: empty editor, pill appears listening
for i in range(6):
    ph += 1
    add(draw_frame("", "", i % 2 == 0, "listening", ph, True,
                   "English · Hindi · Hinglish — 100% on your device"), 90)
# type English word by word
words = EN.split(" ")
acc = ""
for w in words:
    acc = (acc + " " + w).strip()
    ph += 1
    add(draw_frame(acc, "", True, "listening", ph, True,
                   "English · Hindi · Hinglish — 100% on your device"), 110)
    ph += 1
    add(draw_frame(acc, "", True, "listening", ph, True,
                   "English · Hindi · Hinglish — 100% on your device"), 60)
# transcribing beat
for i in range(4):
    ph += 1
    add(draw_frame(EN, "", i % 2 == 0, "transcribing", ph, True,
                   "Switch to Hindi in one click — it just works"), 110)
# type Hindi (Devanagari) word by word
dwords = DEV.split(" ")
dacc = ""
for w in dwords:
    dacc = (dacc + " " + w).strip()
    ph += 1
    add(draw_frame(EN, dacc, True, "listening", ph, True,
                   "Switch to Hindi in one click — it just works"), 150)
    ph += 1
    add(draw_frame(EN, dacc, True, "listening", ph, True,
                   "Switch to Hindi in one click — it just works"), 70)
# inserted + hold
for i in range(3):
    ph += 1
    add(draw_frame(EN, DEV, False, "inserted", ph, True,
                   "Sotto — free & open-source local dictation"), 120)
for i in range(14):
    add(draw_frame(EN, DEV, i % 2 == 0, "inserted", ph, True,
                   "Sotto — free & open-source local dictation"), 130)

# save gif
out = os.path.join(OUT, "demo.gif")
pal = [f.convert("P", palette=Image.ADAPTIVE, colors=128) for f in frames]
pal[0].save(out, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=True,
            disposal=2)
print("wrote", out, f"{os.path.getsize(out)/1e6:.2f} MB, {len(frames)} frames")
# dump a couple of frames for inspection
frames[10].save(os.path.join(OUT, "_demo_frame_a.png"))
frames[len(frames) // 2].save(os.path.join(OUT, "_demo_frame_b.png"))
frames[-1].save(os.path.join(OUT, "_demo_frame_c.png"))
