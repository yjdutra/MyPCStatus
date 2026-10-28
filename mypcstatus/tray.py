"""Icone de bandeja. Opcional: se o AppIndicator nao existir, o app segue sem."""

from . import gtkcompat                      # noqa: F401
from gi.repository import Gtk

AppIndicator3 = None
if gtkcompat.HAVE_INDICATOR:
    try:
        from gi.repository import AppIndicator3
    except ImportError:                      # pragma: no cover
        try:
            from gi.repository import AyatanaAppIndicator3 as AppIndicator3
        except ImportError:
            AppIndicator3 = None


class Tray:
    def __init__(self, on_toggle_window, on_toggle_timer, on_reset, on_quit):
        self.ind = None
        if AppIndicator3 is None:
            return
        menu = Gtk.Menu()

        def item(label, cb):
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", lambda *_: cb())
            mi.show()
            menu.append(mi)
            return mi

        item("Mostrar / esconder", on_toggle_window)
        self.timer_item = item("Iniciar pomodoro", on_toggle_timer)
        item("Zerar pomodoro", on_reset)
        sep = Gtk.SeparatorMenuItem()
        sep.show()
        menu.append(sep)
        item("Sair", on_quit)

        self.ind = AppIndicator3.Indicator.new(
            "mypcstatus", "utilities-system-monitor",
            AppIndicator3.IndicatorCategory.SYSTEM_SERVICES)
        self.ind.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.ind.set_menu(menu)
        self.ind.set_title("MyPCStatus")

    def set_label(self, text):
        if self.ind:
            self.ind.set_label(text, "00:00")

    def set_timer_label(self, text):
        if self.ind:
            self.timer_item.set_label(text)
