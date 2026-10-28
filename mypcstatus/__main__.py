"""Ponto de entrada: python3 -m mypcstatus"""

import signal
import sys

from . import gtkcompat                  # noqa: F401  (fixa as versoes)
from gi.repository import Gio, GLib, Gtk

from . import config
from .window import StatusWindow

APP_ID = "io.github.yjdutra.MyPCStatus"


class MyPCStatus(Gtk.Application):
    """Instancia unica.

    O GtkApplication registra APP_ID no barramento de sessao. Se o app ja'
    estiver rodando, esta execucao nao abre uma segunda janela: ela manda um
    'activate' para a instancia que existe e sai. Sem isso, o autostart mais
    um clique no menu dariam dois gatos disputando o config.json.
    """

    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.win = None

    def do_activate(self):
        if self.win is None:
            cfg = config.load()
            self.win = StatusWindow(self, cfg)
            self.add_window(self.win)
            self.win.show_all()
            self.win.place()
            if cfg["autostart_timer"]:
                self.win._on_toggle_timer()
        else:
            # ja' estava rodando: pode estar escondida na bandeja
            self.win.show_all()
            self.win.place()
            self.win.present()


def main():
    # Ctrl+C no terminal fecha o app em vez de o GTK engolir o sinal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    GLib.timeout_add(200, lambda: True)   # dá chance ao Python de ver sinais
    return MyPCStatus().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
