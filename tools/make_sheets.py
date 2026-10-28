#!/usr/bin/env python3
"""Gera assets/expressoes.png e assets/poses.png a partir do sprite.

Precisa de Pillow, que NAO e' dependencia do app -- so' deste utilitario.
Rode depois de mexer em art.py: python3 tools/make_sheets.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from mypcstatus import art, sprite

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = 5
BG = (11, 14, 20, 255)


def frame(grid):
    im = Image.new("RGBA", (art.WIDTH * S, art.HEIGHT * S), (0, 0, 0, 0))
    px = im.load()
    for x, y, (r, g, b) in sprite.to_rgba(grid):
        for dy in range(S):
            for dx in range(S):
                px[x * S + dx, y * S + dy] = (r, g, b, 255)
    return im


def sheet(frames, cols):
    rows = (len(frames) + cols - 1) // cols
    w, h = art.WIDTH * S, art.HEIGHT * S
    out = Image.new("RGBA", (w * cols, h * rows), BG)
    for i, im in enumerate(frames):
        pos = ((i % cols) * w, (i // cols) * h)
        # com a mascara: o transparente do sprite compoe sobre o fundo escuro.
        # sem ela, o alfa do sprite SOBRESCREVE o fundo e a folha sai furada --
        # o corpo escuro do gato sumia no tema escuro do GitHub.
        out.paste(im, pos, im)
    return out


def main():
    eyes = [frame(sprite.compose("idle", eyes=e)) for e in art.EYES]
    sheet(eyes, 5).save(os.path.join(ROOT, "assets", "expressoes.png"))

    poses = [frame(sprite.compose(p)) for p in art.POSES]
    sheet(poses, 4).save(os.path.join(ROOT, "assets", "poses.png"))

    print("expressoes:", list(art.EYES))
    print("poses     :", list(art.POSES))


if __name__ == "__main__":
    main()
