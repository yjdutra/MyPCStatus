"""Ponto de entrada: python3 -m mypcstatus"""

import signal
import sys

from . import gtkcompat                  # noqa: F401  (fixa as versoes)
from gi.repository import GLib, Gtk

from . import config
from .window import StatusWindow


def main():
    cfg = config.load()
    win = StatusWindow(None, cfg)
    win.show_all()
    win.place()

    # Ctrl+C no terminal fecha a janela em vez de deixar o GTK engolir o sinal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    GLib.timeout_add(200, lambda: True)   # dá chance ao Python de ver sinais

    if cfg["autostart_timer"]:
        win._on_toggle_timer()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
