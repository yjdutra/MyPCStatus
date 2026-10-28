"""Painel de metricas desenhado a mao com cairo + pango.

As informacoes ficam agrupadas em cards: CPU, GPU, memoria, rede e bateria.
Tudo e' um DrawingArea so' -- o visual fica consistente e nao precisa de uma
arvore de widgets GTK apenas para mostrar numero.

Medir e desenhar sao o mesmo codigo: `_layout` roda contra um contexto cairo
descartavel quando so' queremos a altura, e contra o contexto de verdade na
hora de pintar. Assim nao da' para a medida e o desenho divergirem.
"""

import math
import time

import cairo

from . import gtkcompat                                 # noqa: F401
from gi.repository import Gdk, Gtk, Pango, PangoCairo

from .metrics import fmt_bytes, fmt_rate, fmt_secs

THEME = {
    "bg":      (0x0B, 0x0E, 0x14),
    "panel":   (0x15, 0x19, 0x23),
    "track":   (0x21, 0x26, 0x33),
    "dim":     (0x6B, 0x73, 0x89),
    "text":    (0x98, 0xA3, 0xB8),
    "bright":  (0xE6, 0xEB, 0xF5),
    "accent":  (0x5E, 0x64, 0xE8),
    "amber":   (0xF4, 0xBD, 0x57),
    "pink":    (0xE3, 0x8B, 0xA6),
    "green":   (0x6B, 0xD4, 0x9A),
    "red":     (0xE8, 0x70, 0x5E),
    "cyan":    (0x7B, 0xE0, 0xE8),
}

PAD = 12            # margem da janela ate' o card
CARD_PAD = 9        # margem interna do card
CARD_GAP = 6
CARD_R = 9
ROW_H = 24          # linha com barra
CELL_H = 19         # linha de rotulo + valor
IP_ROW_H = 23
BAR_H = 7
LABEL_W = 40
VALUE_W = 72
CORE_ROW_H = 16
CORE_LABEL_W = 32
CORE_VALUE_W = 30
GAP_COL = 10
PANEL_W = 300       # usado so' para medir antes da primeira alocacao
COPIED_S = 1.8


def rgb(cr, name, a=1.0):
    r, g, b = THEME[name]
    cr.set_source_rgba(r / 255, g / 255, b / 255, a)


def rounded(cr, x, y, w, h, r):
    r = min(r, h / 2, w / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def level_color(pct, warn=60, crit=85):
    if pct >= crit:
        return "red"
    if pct >= warn:
        return "amber"
    return "green"


class StatsPanel(Gtk.DrawingArea):
    def __init__(self, cfg, on_resize=None, on_ip_request=None, on_ip_copy=None):
        super().__init__()
        self.cfg = cfg
        self.m = None
        self.speed_text = None
        self.on_resize = on_resize
        self.on_ip_request = on_ip_request
        self.on_ip_copy = on_ip_copy

        self.cpu_expanded = bool(cfg.get("cpu_expanded", False))
        self.gpu_expanded = bool(cfg.get("gpu_expanded", False))
        self.ip_value = None
        self.ip_visible = False
        self.ip_error = None
        self.ip_loading = False
        self._ip_copied_until = 0.0

        self._hit = {}      # nome -> (x0, y0, x1, y1), medido ao desenhar
        self._h = 0
        self._scratch = cairo.Context(
            cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self._on_click)
        self.connect("draw", self._on_draw)
        self._sync_height()

    # ------------------------------------------------------------- estado
    def update(self, m):
        self.m = m
        self._sync_height()
        self.queue_draw()

    def set_ip(self, ip, error, reveal=True):
        self.ip_loading = False
        self.ip_value = ip
        self.ip_error = error
        if ip and reveal:
            self.ip_visible = True
        self._sync_height()
        self.queue_draw()

    def _gpu(self):
        if self.m is None or not self.m.gpus.available:
            return None
        return self.m.gpus.primary

    # ------------------------------------------------------------- tamanho
    def _width(self):
        w = self.get_allocated_width()
        return w if w > 1 else PANEL_W

    def _wanted_height(self):
        return self._layout(self._scratch, self._width())

    def _sync_height(self):
        h = self._wanted_height()
        if h != self._h:
            self._h = h
            self.set_size_request(-1, h)
            if self.on_resize:
                self.on_resize()

    # ------------------------------------------------------------- cliques
    def _on_click(self, widget, event):
        if event.button != 1:
            return False
        for key, (x0, y0, x1, y1) in self._hit.items():
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                return self._activate(key)
        return False

    def _activate(self, key):
        if key in ("cpu", "gpu"):
            attr = key + "_expanded"
            setattr(self, attr, not getattr(self, attr))
            self.cfg[attr] = getattr(self, attr)
            self._sync_height()
            self.queue_draw()
            return True
        if key == "ip_eye":
            if self.ip_value is None and not self.ip_loading:
                self.ip_error = None
                self.ip_loading = True
                if self.on_ip_request:
                    self.on_ip_request()
            else:
                self.ip_visible = not self.ip_visible
            self.queue_draw()
            return True
        if key == "ip_copy" and self.ip_value:
            if self.on_ip_copy:
                self.on_ip_copy(self.ip_value)
            self._ip_copied_until = time.monotonic() + COPIED_S
            self.queue_draw()
            return True
        return False

    # ------------------------------------------------------------- primitivas
    def _measure(self, cr, txt, size=10, bold=False):
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(
            Pango.FontDescription("Sans %s%d" % ("Bold " if bold else "", size)))
        layout.set_text(txt, -1)
        return layout.get_pixel_size()[0]

    def _text(self, cr, x, y, txt, color="text", size=10, bold=False,
              align="left", width=None):
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(
            Pango.FontDescription("Sans %s%d" % ("Bold " if bold else "", size)))
        layout.set_text(txt, -1)
        w, h = layout.get_pixel_size()
        if align == "right" and width is not None:
            x = x + width - w
        elif align == "center" and width is not None:
            x = x + (width - w) / 2
        rgb(cr, color)
        cr.move_to(x, y - h / 2)
        PangoCairo.show_layout(cr, layout)
        return w

    def _value(self, cr, x, y, w, value):
        """Valor a' direita; quebra em duas linhas quando nao cabe.

        "11.2GB/31.1GB" mede 91 px numa coluna de 72 e invadia a barra.
        "86°C" e "41%" seguem numa linha so'.
        """
        if "/" not in value or self._measure(cr, value, 10) <= w:
            self._text(cr, x, y, value, "bright", 10, align="right", width=w)
            return
        used, _, total = value.partition("/")
        self._text(cr, x, y - 6, used, "bright", 9, align="right", width=w)
        self._text(cr, x, y + 6, "/" + total, "dim", 9, align="right", width=w)

    def _bar(self, cr, x, y, w, pct, color, h=BAR_H):
        rgb(cr, "track")
        rounded(cr, x, y - h / 2, w, h, h / 2)
        cr.fill()
        fill = max(0.0, min(pct, 100.0)) / 100.0 * w
        if fill > 1:
            rgb(cr, color)
            rounded(cr, x, y - h / 2, fill, h, h / 2)
            cr.fill()

    def _row(self, cr, x, y, w, label, pct, value, color, bold=True):
        self._text(cr, x, y, label, "dim", 9, bold=bold)
        bx = x + LABEL_W
        bw = w - LABEL_W - VALUE_W
        self._bar(cr, bx, y, bw, pct, color)
        self._value(cr, bx + bw + 6, y, VALUE_W - 6, value)

    def _cell(self, cr, x, y, w, label, value, color="text"):
        self._text(cr, x, y, label, "dim", 9)
        self._text(cr, x, y, value, color, 10, align="right", width=w)

    def _core(self, cr, x, y, w, idx, pct):
        self._text(cr, x, y, "CPU%d" % (idx + 1), "dim", 8)
        bx = x + CORE_LABEL_W
        bw = w - CORE_LABEL_W - CORE_VALUE_W - 4
        self._bar(cr, bx, y, bw, pct, level_color(pct), h=5)
        self._text(cr, bx + bw + 4, y, "%.0f%%" % pct, "text", 8,
                   align="right", width=CORE_VALUE_W)

    def _card(self, cr, x, y, w, h):
        rgb(cr, "panel")
        rounded(cr, x, y, w, h, CARD_R)
        cr.fill_preserve()
        cr.set_source_rgba(1, 1, 1, 0.04)
        cr.set_line_width(1)
        cr.stroke()

    def _chevron(self, cr, x, y, is_open):
        cr.new_path()
        rgb(cr, "dim")
        if is_open:
            cr.move_to(x, y - 2)
            cr.line_to(x + 7, y - 2)
            cr.line_to(x + 3.5, y + 3)
        else:
            cr.move_to(x, y - 3.5)
            cr.line_to(x + 5, y)
            cr.line_to(x, y + 3.5)
        cr.close_path()
        cr.fill()

    def _icon_eye(self, cr, x, y, is_open):
        """Olho desenhado a mao: glifo de fonte nao e' garantido.

        O new_path() importa: PangoCairo deixa um ponto corrente para tras, e
        um arc() sem limpar o caminho liga uma reta daquele ponto ate' o inicio
        do arco -- o olho saia com um risco atravessando o card.
        """
        cr.new_path()
        rgb(cr, "text" if is_open else "dim")
        cr.set_line_width(1.3)
        cr.save()
        cr.translate(x + 8, y)
        cr.scale(1.0, 0.58)
        cr.arc(0, 0, 7.2, 0, 2 * math.pi)
        cr.restore()
        cr.stroke()
        cr.arc(x + 8, y, 2.3, 0, 2 * math.pi)
        cr.fill()
        if not is_open:
            cr.move_to(x + 1.5, y + 5.5)
            cr.line_to(x + 14.5, y - 5.5)
            cr.stroke()

    def _icon_copy(self, cr, x, y):
        cr.new_path()
        rgb(cr, "panel")
        rounded(cr, x + 4, y - 3, 9, 10, 2)
        cr.fill()
        rgb(cr, "dim")
        cr.set_line_width(1.2)
        rounded(cr, x + 0.5, y - 6.5, 9, 10, 2)
        cr.stroke()
        rounded(cr, x + 4.5, y - 2.5, 9, 10, 2)
        cr.stroke()

    # ------------------------------------------------------------- cards
    def _card_cpu(self, cr, x, y, w):
        m = self.m
        rows = 0
        if self.cpu_expanded:
            rows = (len(m.cpu_cores) + 1) // 2
        h = CARD_PAD * 2 + ROW_H * 2 + (rows * CORE_ROW_H + 4 if rows else 0)
        self._card(cr, x, y, w, h)

        ix, iw = x + CARD_PAD, w - CARD_PAD * 2
        cy = y + CARD_PAD + ROW_H / 2
        self._row(cr, ix, cy, iw, "CPU", m.cpu, "%.0f%%" % m.cpu,
                  level_color(m.cpu))
        self._chevron(cr, ix + 26, cy, self.cpu_expanded)
        self._hit["cpu"] = (x, cy - ROW_H / 2, x + w, cy + ROW_H / 2)
        cy += ROW_H / 2

        if rows:
            col_w = (iw - GAP_COL) / 2
            for i, pct in enumerate(m.cpu_cores):
                self._core(cr, ix + (i % 2) * (col_w + GAP_COL),
                           cy + CORE_ROW_H / 2 + (i // 2) * CORE_ROW_H,
                           col_w, i, pct)
            cy += rows * CORE_ROW_H + 4

        cy += ROW_H / 2
        warn, crit = self.cfg["temp_warn"], self.cfg["temp_crit"]
        if m.temp is None:
            self._row(cr, ix, cy, iw, "temp", 0, "--", "dim", bold=False)
        else:
            pct = max(0.0, min((m.temp - 30) / (crit + 10 - 30) * 100, 100))
            self._row(cr, ix, cy, iw, "temp", pct, "%.0f°C" % m.temp,
                      level_color(m.temp, warn, crit), bold=False)
        return h

    def _card_gpu(self, cr, x, y, w):
        g = self._gpu()
        if g is None:
            return 0
        m = self.m
        extras = []
        if self.gpu_expanded:
            if g.mem_total:
                extras.append(("vram", "%s/%s" % (fmt_bytes(g.mem_used),
                                                  fmt_bytes(g.mem_total)),
                               level_color(g.mem_pct)))
            if g.clock:
                extras.append(("clock", "%.0fMHz" % g.clock, "text"))
            for other in m.gpus.secondary:
                if other.clock:
                    lab = other.short if len(other.short) <= 11 else "iGPU"
                    extras.append((lab.lower(), "%.0fMHz" % other.clock, "text"))
        rows = (len(extras) + 1) // 2
        has_temp = g.temp is not None
        h = (CARD_PAD * 2 + ROW_H + (ROW_H if has_temp else 0)
             + (rows * CELL_H + 4 if rows else 0))
        self._card(cr, x, y, w, h)

        ix, iw = x + CARD_PAD, w - CARD_PAD * 2
        cy = y + CARD_PAD + ROW_H / 2
        if g.util is not None:
            self._row(cr, ix, cy, iw, "GPU", g.util, "%.0f%%" % g.util,
                      level_color(g.util))
        elif g.clock_pct is not None:
            # sem uso real (i915 sem root): mostra clock e diz que e' clock
            self._row(cr, ix, cy, iw, "GPU", g.clock_pct, "%.0fMHz" % g.clock,
                      level_color(g.clock_pct))
        else:
            self._row(cr, ix, cy, iw, "GPU", 0, "--", "dim")
        self._chevron(cr, ix + 26, cy, self.gpu_expanded)
        self._hit["gpu"] = (x, cy - ROW_H / 2, x + w, cy + ROW_H / 2)
        cy += ROW_H / 2

        if has_temp:
            cy += ROW_H / 2
            gwarn = self.cfg.get("gpu_temp_warn", 80)
            gcrit = self.cfg.get("gpu_temp_crit", 90)
            pct = max(0.0, min((g.temp - 30) / (gcrit + 10 - 30) * 100, 100))
            self._row(cr, ix, cy, iw, "temp", pct, "%.0f°C" % g.temp,
                      level_color(g.temp, gwarn, gcrit), bold=False)
            cy += ROW_H / 2

        if rows:
            cy += 2
            self._text(cr, ix, cy + CELL_H / 2 - 4, g.short, "dim", 8)
            col_w = (iw - GAP_COL) / 2
            for i, (lab, val, color) in enumerate(extras):
                self._cell(cr, ix + (i % 2) * (col_w + GAP_COL),
                           cy + CELL_H / 2 + (i // 2) * CELL_H + 8,
                           col_w, lab, val, color)
        return h

    def _card_memoria(self, cr, x, y, w):
        m = self.m
        h = CARD_PAD * 2 + ROW_H * 2
        self._card(cr, x, y, w, h)
        ix, iw = x + CARD_PAD, w - CARD_PAD * 2
        cy = y + CARD_PAD + ROW_H / 2
        self._row(cr, ix, cy, iw, "RAM", m.ram_pct,
                  "%s/%s" % (fmt_bytes(m.ram_used), fmt_bytes(m.ram_total)),
                  level_color(m.ram_pct))
        cy += ROW_H
        extra = " · %.0f°C" % m.nvme_temp if m.nvme_temp else ""
        self._row(cr, ix, cy, iw, "disco", m.disk_pct,
                  "%.0f%%%s" % (m.disk_pct, extra),
                  level_color(m.disk_pct, 80, 92), bold=False)
        return h

    def _card_rede(self, cr, x, y, w):
        m = self.m
        h = CARD_PAD * 2 + CELL_H * 2 + IP_ROW_H
        self._card(cr, x, y, w, h)
        ix, iw = x + CARD_PAD, w - CARD_PAD * 2
        col_w = (iw - GAP_COL) / 2
        cy = y + CARD_PAD + CELL_H / 2

        self._cell(cr, ix, cy, col_w, "baixada", fmt_rate(m.net_down), "cyan")
        self._cell(cr, ix + col_w + GAP_COL, cy, col_w, "subida",
                   fmt_rate(m.net_up), "cyan")
        cy += CELL_H

        ping = "--" if m.ping is None else "%.0fms" % m.ping
        ping_col = "dim" if m.ping is None else (
            "green" if m.ping < 50 else "amber" if m.ping < 120 else "red")
        self._cell(cr, ix, cy, col_w, "ping", ping, ping_col)
        self._cell(cr, ix + col_w + GAP_COL, cy, col_w, "banda",
                   self.speed_text or "--",
                   "accent" if self.speed_text else "dim")
        cy += CELL_H / 2 + IP_ROW_H / 2

        self._ip_row(cr, ix, cy, iw)
        return h

    def _ip_row(self, cr, x, y, w):
        self._text(cr, x, y, "IP", "dim", 9, bold=True)
        bx_copy = x + w - 16
        bx_eye = bx_copy - 24

        if time.monotonic() < self._ip_copied_until:
            txt, col = "copiado!", "green"
        elif self.ip_loading:
            txt, col = "buscando…", "dim"
        elif self.ip_error:
            txt, col = self.ip_error, "red"
        elif self.ip_value is None:
            txt, col = "mostrar", "dim"
        elif not self.ip_visible:
            txt, col = "•" * 11, "dim"
        else:
            txt, col = self.ip_value, "bright"
        vx = x + 22
        self._text(cr, vx, y, txt, col, 10, align="right",
                   width=bx_eye - 8 - vx)

        self._icon_eye(cr, bx_eye, y, self.ip_visible)
        self._hit["ip_eye"] = (bx_eye - 3, y - 10, bx_eye + 19, y + 10)
        if self.ip_value:
            self._icon_copy(cr, bx_copy, y)
            self._hit["ip_copy"] = (bx_copy - 3, y - 10, bx_copy + 17, y + 10)

    def _card_bateria(self, cr, x, y, w):
        m = self.m
        h = CARD_PAD * 2 + CELL_H
        self._card(cr, x, y, w, h)
        ix, iw = x + CARD_PAD, w - CARD_PAD * 2
        col_w = (iw - GAP_COL) / 2
        cy = y + CARD_PAD + CELL_H / 2
        if m.battery_pct is None:
            self._cell(cr, ix, cy, col_w, "bateria", "--", "dim")
        else:
            icon = "⚡" if m.battery_plugged else ""
            self._cell(cr, ix, cy, col_w, "bateria",
                       "%.0f%%%s" % (m.battery_pct, icon),
                       "green" if m.battery_pct > 40 or m.battery_plugged
                       else "red")
        self._cell(cr, ix + col_w + GAP_COL, cy, col_w, "ligado há",
                   fmt_secs(m.uptime), "text")
        return h

    # ------------------------------------------------------------- layout
    def _layout(self, cr, w):
        """Mede e desenha com o mesmo codigo. Devolve a altura total."""
        if self.m is None:
            return CARD_PAD * 2 + ROW_H
        self._hit = {}
        x, cw, y = PAD, w - PAD * 2, 2
        for fn in (self._card_cpu, self._card_gpu, self._card_memoria,
                   self._card_rede, self._card_bateria):
            h = fn(cr, x, y, cw)
            if h:
                y += h + CARD_GAP
        return y - CARD_GAP + 2

    def _on_draw(self, widget, cr):
        self._layout(cr, widget.get_allocation().width)
        return False


class PomodoroBar(Gtk.DrawingArea):
    """Barra fina de progresso da fase atual do pomodoro."""

    def __init__(self):
        super().__init__()
        self.progress = 0.0
        self.color = "accent"
        self.set_size_request(-1, 6)
        self.connect("draw", self._on_draw)

    def update(self, progress, color):
        self.progress, self.color = progress, color
        self.queue_draw()

    def _on_draw(self, widget, cr):
        alloc = widget.get_allocation()
        w, h = alloc.width - PAD * 2, 6
        rgb(cr, "track")
        rounded(cr, PAD, 0, w, h, h / 2)
        cr.fill()
        fill = max(0.0, min(self.progress, 1.0)) * w
        if fill > 1:
            rgb(cr, self.color)
            rounded(cr, PAD, 0, fill, h, h / 2)
            cr.fill()
        return False
