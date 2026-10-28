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

    alloc = win.get_allocation()
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, alloc.width, alloc.height)
    cr = cairo.Context(surf)
    win.draw(cr)
    path = os.path.join(OUT, name + ".png")
    surf.write_to_png(path)

    win.m.stop_ping()
    win.mascot.stop()
    win.destroy()
    print("  %-14s %dx%d  ->  %s" % (name, alloc.width, alloc.height, path))
    return path


def main():
    os.makedirs(OUT, exist_ok=True)
    shot("janela")
    shot("janela-nucleos", {"cpu_expanded": True})
    shot("janela-foco", focus=True)


if __name__ == "__main__":
    main()
