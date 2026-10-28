#!/usr/bin/env python3
"""Gera assets/icon.png a partir do sprite do mascote.

Precisa de Pillow, que NAO e' dependencia do app -- so' deste utilitario.
Rode de novo se mexer no desenho: python3 tools/make_icon.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from mypcstatus import art, sprite

SIZE = 256


def main():
    grid = sprite.compose("idle")
    cells = sprite.to_rgba(grid)
    xs = [x for x, _, _ in cells]
    ys = [y for _, y, _ in cells]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w, h = x1 - x0 + 1, y1 - y0 + 1
    side = max(w, h)
    scale = SIZE // (side + 2)

    im = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    px = im.load()
    ox = (SIZE - w * scale) // 2
    oy = (SIZE - h * scale) // 2
    for x, y, (r, g, b) in cells:
        for dy in range(scale):
            for dx in range(scale):
                X, Y = ox + (x - x0) * scale + dx, oy + (y - y0) * scale + dy
                if 0 <= X < SIZE and 0 <= Y < SIZE:
                    px[X, Y] = (r, g, b, 255)

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets", "icon.png")
    im.save(out)
    print("gravado", out, im.size)


if __name__ == "__main__":
    main()
