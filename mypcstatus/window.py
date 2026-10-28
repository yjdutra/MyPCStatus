"""A janelinha flutuante: mascote em cima, metricas no meio, pomodoro embaixo."""

import os
import subprocess

import cairo

from . import gtkcompat                        # noqa: F401  (fixa as versoes)
from gi.repository import Gdk, GLib, Gtk, Pango

if gtkcompat.HAVE_NOTIFY:
    from gi.repository import Notify
    Notify.init("MyPCStatus")
else:                                          # pragma: no cover
    Notify = None

from . import config, speedtest
from .mascot import MascotArea, Mood
from .metrics import Metrics
from .pomodoro import FOCUS, LONG, PAUSED, SHORT, Pomodoro
from .tray import Tray
from .widgets import PomodoroBar, StatsPanel, THEME, rounded

WIDTH = 300
MARGIN = 24
PHASE_COLOR = {FOCUS: "accent", SHORT: "green", LONG: "cyan", PAUSED: "amber"}


class StatusWindow(Gtk.Window):
    def __init__(self, app, cfg):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.app = app
        self.cfg = cfg
        self.m = Metrics(smooth=cfg["cpu_smooth"])
        self.mood = Mood(cfg)
        self.pomo = Pomodoro(cfg, on_phase_end=self._on_phase_end)
        self._speed_running = False
        self._save_pos_id = None

        self._setup_window()
        self._build_ui()
        self._load_css()

        self.m.start_ping()
        self._tick()
        GLib.timeout_add_seconds(1, self._tick)

        self.tray = Tray(self.toggle_visible, self._on_toggle_timer,
                         self._on_reset, self.quit)

    # ------------------------------------------------------------- janela
    def _setup_window(self):
        self.set_title("MyPCStatus")
        self.set_decorated(False)
        self.set_app_paintable(True)
        self.set_resizable(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(self.cfg["keep_above"])
        self.stick()                       # aparece em todas as areas de trabalho
        self.set_default_size(WIDTH, -1)

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None and screen.is_composited():
            self.set_visual(visual)

        self.connect("draw", self._draw_bg)
        self.connect("configure-event", self._on_configure)
        self.connect("delete-event", self._on_delete)

    def _on_delete(self, *_):
        self.quit()
        return True            # ja' tratamos: o GTK nao destroi por conta propria

    def place(self):
        x, y = self.cfg["x"], self.cfg["y"]
        if x < 0 or y < 0:                 # primeira vez: canto superior direito
            display = Gdk.Display.get_default()
            mon = display.get_primary_monitor() or display.get_monitor(0)
            geo = mon.get_workarea()
            _, nat = self.get_preferred_height()
            x = geo.x + geo.width - WIDTH - MARGIN
            y = geo.y + MARGIN
            self.cfg["x"], self.cfg["y"] = x, y
            config.save(self.cfg)
        self.move(x, y)

    def _draw_bg(self, widget, cr):
        alloc = widget.get_allocation()
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        r, g, b = THEME["bg"]
        rounded(cr, 0.5, 0.5, alloc.width - 1, alloc.height - 1, 14)
        cr.set_source_rgba(r / 255, g / 255, b / 255, self.cfg["opacity"])
        cr.fill_preserve()
        cr.set_source_rgba(0.38, 0.42, 0.53, 0.28)
        cr.set_line_width(1)
        cr.stroke()
        return False

    def _on_configure(self, widget, event):
        # debounce: so' grava a posicao quando a janela para de se mexer
        if self._save_pos_id:
            GLib.source_remove(self._save_pos_id)
        self._save_pos_id = GLib.timeout_add(600, self._save_pos)
        return False

    def _save_pos(self):
        self._save_pos_id = None
        x, y = self.get_position()
        if (x, y) != (self.cfg["x"], self.cfg["y"]):
            self.cfg["x"], self.cfg["y"] = x, y
            config.save(self.cfg)
        return False

    def _load_css(self):
        path = os.path.join(os.path.dirname(__file__), "style.css")
        provider = Gtk.CssProvider()
        try:
            provider.load_from_path(path)
        except GLib.Error:
            return
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    # ------------------------------------------------------------- interface
    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.set_name("root")
        self.add(root)

        # --- cabecalho (arrastavel)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        head.set_margin_top(8)
        head.set_margin_start(14)
        head.set_margin_end(10)
        title = Gtk.Label(label="MyPCStatus")
        title.set_name("title")
        title.set_xalign(0.0)
        head.pack_start(title, True, True, 0)

        self.pin_btn = Gtk.ToggleButton(label="📌")
        self.pin_btn.set_active(self.cfg["keep_above"])
        self.pin_btn.set_tooltip_text("Manter sempre no topo")
        self.pin_btn.connect("toggled", self._on_pin)
        for cls in ("flat", "chip"):
            self.pin_btn.get_style_context().add_class(cls)
        head.pack_start(self.pin_btn, False, False, 0)

        for label, cb, tip in (("–", self.toggle_visible, "Esconder na bandeja"),
                               ("✕", self.quit, "Sair")):
            btn = Gtk.Button(label=label)
            btn.get_style_context().add_class("flat")
            btn.get_style_context().add_class("chip")
            btn.set_tooltip_text(tip)
            btn.connect("clicked", lambda *_, f=cb: f())
            head.pack_start(btn, False, False, 0)

        # --- mascote (tambem serve de alca para arrastar)
        self.mascot = MascotArea(scale=self.cfg["scale"])
        drag = Gtk.EventBox()
        drag.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        drag.connect("button-press-event", self._on_drag)
        drag_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        drag_box.pack_start(head, False, False, 0)
        drag_box.pack_start(self.mascot, False, False, 2)
        drag.add(drag_box)
        root.pack_start(drag, False, False, 0)

        self.speech = Gtk.Label(label="")
        self.speech.set_name("speech")
        self.speech.set_ellipsize(Pango.EllipsizeMode.END)
        root.pack_start(self.speech, False, False, 2)

        # --- metricas
        self.stats = StatsPanel(self.cfg, on_resize=self._on_panel_resize)
        self.stats.set_margin_top(6)
        root.pack_start(self.stats, False, False, 0)

        root.pack_start(self._separator(), False, False, 6)

        # --- pomodoro
        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        line.set_margin_start(14)
        line.set_margin_end(14)
        self.phase_lbl = Gtk.Label(label="pronto")
        self.phase_lbl.set_name("phase")
        self.phase_lbl.set_xalign(0.0)
        line.pack_start(self.phase_lbl, True, True, 0)
        self.cycles_lbl = Gtk.Label(label="")
        self.cycles_lbl.set_name("cycles")
        line.pack_start(self.cycles_lbl, False, False, 0)
        root.pack_start(line, False, False, 0)

        self.clock_lbl = Gtk.Label(label="25:00")
        self.clock_lbl.set_name("clock")
        root.pack_start(self.clock_lbl, False, False, 0)

        self.pbar = PomodoroBar()
        self.pbar.set_margin_top(2)
        root.pack_start(self.pbar, False, False, 0)

        ctl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        ctl.set_margin_start(14)
        ctl.set_margin_end(14)
        ctl.set_margin_top(10)
        ctl.set_margin_bottom(12)

        self.play_btn = Gtk.Button(label="▶  iniciar")
        self.play_btn.connect("clicked", lambda *_: self._on_toggle_timer())
        self.play_btn.get_style_context().add_class("flat")
        self.play_btn.get_style_context().add_class("go")
        ctl.pack_start(self.play_btn, True, True, 0)

        for label, cb, tip in (("⏭", self._on_skip, "Pular fase"),
                               ("↺", self._on_reset, "Zerar")):
            btn = Gtk.Button(label=label)
            btn.get_style_context().add_class("flat")
            btn.get_style_context().add_class("chip")
            btn.set_tooltip_text(tip)
            btn.connect("clicked", lambda *_, f=cb: f())
            ctl.pack_start(btn, False, False, 0)

        self.speed_btn = Gtk.Button(label="⚡")
        self.speed_btn.get_style_context().add_class("flat")
        self.speed_btn.get_style_context().add_class("chip")
        self.speed_btn.set_tooltip_text("Testar velocidade da internet "
                                        "(baixa ~10 MB)")
        self.speed_btn.connect("clicked", lambda *_: self._on_speedtest())
        ctl.pack_start(self.speed_btn, False, False, 0)

        root.pack_start(ctl, False, False, 0)
        self._build_menu()

    def _on_panel_resize(self):
        """O dropdown dos nucleos mudou a altura do painel.

        A janela nao e' redimensionavel, entao pedir um tamanho qualquer faz o
        GTK recalcular a altura natural -- e' assim que ela encolhe de volta.
        """
        def apply():
            self.resize(WIDTH, 1)
            # o WM reposiciona a janela ao redimensiona-la; sem isto ela
            # anda um pouco a cada vez que o dropdown abre ou fecha
            x, y = self.cfg["x"], self.cfg["y"]
            if x >= 0 and y >= 0:
                self.move(x, y)
            config.save(self.cfg)
            return False
        GLib.idle_add(apply)

    @staticmethod
    def _separator():
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_start(14)
        sep.set_margin_end(14)
        return sep

    def _build_menu(self):
        self.menu = Gtk.Menu()
        for label, cb in (("Mostrar / esconder", self.toggle_visible),
                          ("Zerar pomodoro", self._on_reset),
                          ("Testar velocidade", self._on_speedtest),
                          ("Sair", self.quit)):
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", lambda *_, f=cb: f())
            mi.show()
            self.menu.append(mi)

    # ------------------------------------------------------------- eventos
    def _on_drag(self, widget, event):
        if event.button == 1:
            self.begin_move_drag(event.button, int(event.x_root),
                                 int(event.y_root), event.time)
            return True
        if event.button == 3:
            self.menu.popup_at_pointer(event)
            return True
        return False

    def _on_pin(self, btn):
        self.cfg["keep_above"] = btn.get_active()
        self.set_keep_above(self.cfg["keep_above"])
        config.save(self.cfg)

    def toggle_visible(self):
        if self.get_visible():
            self.hide()
        else:
            self.show_all()
            self.place()
            self.present()

    def _on_toggle_timer(self):
        self.pomo.toggle()
        self._refresh_pomo()

    def _on_skip(self):
        self.pomo.skip()
        self._refresh_pomo()

    def _on_reset(self):
        self.pomo.reset()
        self._refresh_pomo()

    def _on_phase_end(self, finished, nxt):
        titles = {FOCUS: "Foco concluído", SHORT: "Pausa terminada",
                  LONG: "Pausa longa terminada"}
        bodies = {FOCUS: "Levanta, bebe água, olha pra longe.",
                  SHORT: "Bora, mais um foco.",
                  LONG: "Recarregado? Próximo foco começando."}
        self._notify(titles.get(finished, "Pomodoro"),
                     bodies.get(finished, ""))

    def _notify(self, title, body):
        if Notify is not None:
            try:
                note = Notify.Notification.new(title, body,
                                               "utilities-system-monitor")
                note.set_urgency(Notify.Urgency.NORMAL)
                note.show()
            except Exception:
                pass
        if self.cfg["sound"]:
            try:
                subprocess.Popen(["canberra-gtk-play", "-i", "complete"],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            except OSError:
                pass

    # ------------------------------------------------------------- speedtest
    def _on_speedtest(self):
        if self._speed_running:
            return
        self._speed_running = True
        self.speed_btn.set_sensitive(False)
        self.stats.speed_text = "..."
        self.stats.queue_draw()

        def progress(txt):
            GLib.idle_add(self._speed_progress, txt)

        def done(down, up, err):
            GLib.idle_add(self._speed_done, down, up, err)

        speedtest.run_async(progress, done)

    def _speed_progress(self, txt):
        self.stats.speed_text = txt
        self.stats.queue_draw()
        return False

    def _speed_done(self, down, up, err):
        self._speed_running = False
        self.speed_btn.set_sensitive(True)
        if err or down is None:
            self.stats.speed_text = "falhou"
        elif up is None:
            self.stats.speed_text = f"{down:.0f}↓ Mbps"
        else:
            self.stats.speed_text = f"{down:.0f}↓ {up:.0f}↑"
        self.stats.queue_draw()
        return False

    # ------------------------------------------------------------- loop
    def _tick(self):
        self.m.sample()
        self.pomo.tick()
        self.stats.update(self.m)
        pose, eyes, phrase = self.mood.pick(self.m, self.pomo)
        self.mascot.pose, self.mascot.eyes = pose, eyes
        self.speech.set_text(phrase or "")
        self._refresh_pomo()
        return True

    def _refresh_pomo(self):
        p = self.pomo
        self.clock_lbl.set_text(p.clock(p.remaining))
        self.phase_lbl.set_text(p.label)
        phase = p.prev_phase if p.phase == PAUSED else p.phase
        self.pbar.update(p.progress, PHASE_COLOR.get(phase, "accent"))
        self.play_btn.set_label("⏸  pausar" if p.running else "▶  iniciar")
        total = self.cfg["cycles"]
        done = p.done_focus % total if total else 0
        self.cycles_lbl.set_text("●" * done + "○" * (total - done) if total else "")
        if hasattr(self, "tray"):
            self.tray.set_label(p.clock(p.remaining) if p.running else "")
            self.tray.set_timer_label("Pausar pomodoro" if p.running
                                      else "Iniciar pomodoro")

    def quit(self):
        self._save_pos()
        self.m.stop_ping()
        self.mascot.stop()
        config.save(self.cfg)
        if self.app is not None:
            self.app.quit()
        else:
            # as ferramentas de tools/ sobem a janela sem Gtk.Application
            Gtk.main_quit()
