"""Generate Sotto's app icon (.ico): dark rounded square, violet waveform bars."""

import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))


def draw(size):
    s = size / 64.0
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2 * s, 2 * s, 62 * s, 62 * s], radius=16 * s, fill=(16, 16, 20, 255))
    heights = [18, 30, 42, 30, 18]
    for i, h in enumerate(heights):
        x = (12 + i * 9) * s
        d.rounded_rectangle([x, (32 - h / 2) * s, x + 5 * s, (32 + h / 2) * s],
                            radius=2.5 * s, fill=(157, 140, 255, 255))
    return img


imgs = [draw(n) for n in (16, 24, 32, 48, 64, 128, 256)]
out = os.path.join(HERE, "sotto.ico")
imgs[-1].save(out, format="ICO", sizes=[(i.width, i.height) for i in imgs],
              append_images=imgs[:-1])
print("wrote", out)

# 256x256 PNG for the Linux .desktop / hicolor icon theme
png = os.path.join(HERE, "sotto.png")
draw(256).save(png, format="PNG")
print("wrote", png)
