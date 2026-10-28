#!/usr/bin/env python3
"""Renderiza a janela direto para PNG, sem capturar a tela.

Desenha o widget num ImageSurface do cairo, entao o resultado sai com fundo
transparente e NADA do desktop atras -- que e' o que a gente quer para o
README. Precisa de uma sessao grafica para realizar a janela.

    python3 tools/screenshot.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cairo

from mypcstatus import config, gtkcompat          # noqa: F401
from gi.repository import GLib, Gtk               # noqa: E402

from mypcstatus.pomodoro import FOCUS             # noqa: E402
from mypcstatus.window import StatusWindow        # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")

# o app grava preferencias ao posicionar/redimensionar: nao deixa a captura
# encostar no config.json de quem estiver rodando
config.save = lambda cfg: None


def shot(name, overrides=None, focus=False, settle_ms=2600):
    cfg = dict(config.DEFAULTS)
    cfg.update(x=40, y=40)
    cfg.update(overrides or {})

    win = StatusWindow(None, cfg)
    win.show_all()
    if focus:
        win.pomo.start(FOCUS)

    GLib.timeout_add(settle_ms, Gtk.main_quit)
    Gtk.main()                      # deixa as metricas pegarem leitura real

    # o painel pode ter pedido outra altura no ultimo instante; sem escoar a
    # fila o gtk_widget_draw reclama de alocacao pendente e pode sair torto
    while Gtk.events_pending():
        Gtk.main_iteration()

    alloc = win.get_allocation()
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, alloc.width, alloc.height)
    cr = cairo.Context(surf)
    win.draw(cr)
    path = os.path.join(OUT, name + ".png")
    surf.write_to_png(path)

    win.m.stop()
    win.mascot.stop()
    win.destroy()
    print("  %-14s %dx%d  ->  %s" % (name, alloc.width, alloc.height, path))
    return path


def hero(names, out="hero.png", pad=36, gap=28):
    """Monta a imagem de capa com as janelas lado a lado."""
    from PIL import Image, ImageDraw

    ims = [Image.open(os.path.join(OUT, n + ".png")).convert("RGBA")
           for n in names]
    w = sum(i.width for i in ims) + gap * (len(ims) - 1) + pad * 2
    h = max(i.height for i in ims) + pad * 2
    sheet = Image.new("RGB", (w, h), (13, 16, 23))
    draw = ImageDraw.Draw(sheet)
    for y in range(h):                       # gradiente sutil de fundo
        t = y / h
        draw.line([(0, y), (w, y)],
                  fill=(int(13 + 9 * t), int(16 + 10 * t), int(23 + 14 * t)))
    x = pad
    for im in ims:
        sheet.paste(im, (x, pad + (h - pad * 2 - im.height) // 2), im)
        x += im.width + gap
    path = os.path.join(OUT, out)
    sheet.save(path)
    print("  %-14s %dx%d  ->  %s" % ("hero", w, h, path))


def main():
    os.makedirs(OUT, exist_ok=True)
    shot("janela")
    shot("janela-nucleos", {"cpu_expanded": True})
    shot("janela-gpu", {"gpu_expanded": True})
    shot("janela-detalhes", {"cpu_expanded": True, "gpu_expanded": True})
    shot("janela-foco", focus=True)
    hero(["janela", "janela-detalhes", "janela-foco"])


if __name__ == "__main__":
    main()
