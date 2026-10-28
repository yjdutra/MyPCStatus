"""Painel de metricas desenhado a mao com cairo + pango.

Um DrawingArea so' para o painel inteiro: o visual fica consistente e nao
precisa de uma arvore de widgets GTK so' para mostrar numero.
"""

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

PAD = 14
ROW_H = 26
BAR_H = 7
LABEL_W = 42
VALUE_W = 74
GRID_H = 20
CORE_ROW_H = 16
CORE_LABEL_W = 32
CORE_VALUE_W = 30
GPU_NAME_H = 15


def rgb(cr, name, a=1.0):
    r, g, b = THEME[name]
    cr.set_source_rgba(r / 255, g / 255, b / 255, a)


def rounded(cr, x, y, w, h, r):
    import math
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
    """Barras principais (CPU/RAM/TEMP/GPU) + uma grade compacta embaixo.

    As linhas de CPU e GPU abrem um dropdown com os detalhes. Clicar em
    qualquer ponto da linha alterna.
    """

    def __init__(self, cfg, on_resize=None):
        super().__init__()
        self.cfg = cfg
        self.m = None
        self.speed_text = None
        self.on_resize = on_resize
        self.cpu_expanded = bool(cfg.get("cpu_expanded", False))
        self.gpu_expanded = bool(cfg.get("gpu_expanded", False))
        self._hit = {}            # faixa clicavel de cada linha, medida ao desenhar
        self._h = 0
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self._on_click)
        self.connect("draw", self._on_draw)
        self._sync_height()

    def update(self, m):
        self.m = m
        self._sync_height()
        self.queue_draw()

    # ------------------------------------------------------------- dados
    def _gpu(self):
        if self.m is None or not self.m.gpus.available:
            return None
        return self.m.gpus.primary

    def _gpu_cells(self):
        """Celulas do dropdown da GPU: (rotulo, valor, cor)."""
        g = self._gpu()
        if g is None:
            return []
        warn = self.cfg.get("gpu_temp_warn", 80)
        crit = self.cfg.get("gpu_temp_crit", 90)
        cells = []
        if g.temp is not None:
            cells.append(("temp", "%.0f°C" % g.temp,
                          level_color(g.temp, warn, crit)))
        if g.mem_total:
            cells.append(("vram", "%s/%s" % (fmt_bytes(g.mem_used),
                                             fmt_bytes(g.mem_total)),
                          level_color(g.mem_pct)))
        if g.clock:
            cells.append(("clock", "%.0fMHz" % g.clock, "text"))
        for other in self.m.gpus.secondary:
            if other.clock:
                lab = other.short if len(other.short) <= 11 else "iGPU"
                cells.append((lab.lower(), "%.0fMHz" % other.clock, "text"))
        return cells

    # ------------------------------------------------------------- tamanho
    def _core_rows(self):
        if not self.cpu_expanded:
            return 0
        n = len(self.m.cpu_cores) if self.m else 0
        return (n + 1) // 2

    def _gpu_rows(self):
        if not self.gpu_expanded:
            return 0
        n = len(self._gpu_cells())
        return (n + 1) // 2

    def _wanted_height(self):
        bars = 4 if self._gpu() is not None else 3
        h = ROW_H * bars + GRID_H * 3 + 14
        if self._core_rows():
            h += self._core_rows() * CORE_ROW_H + 6
        if self._gpu_rows():
            h += self._gpu_rows() * GRID_H + GPU_NAME_H + 4
        return h

    def _sync_height(self):
        h = self._wanted_height()
        if h != self._h:
            self._h = h
            self.set_size_request(-1, h)
            if self.on_resize:
                self.on_resize()

    def _on_click(self, widget, event):
        if event.button != 1:
            return False
        for key, (y0, y1) in self._hit.items():
            if y0 <= event.y <= y1:
                attr = key + "_expanded"
                setattr(self, attr, not getattr(self, attr))
                self.cfg[attr] = getattr(self, attr)
                self._sync_height()
                self.queue_draw()
                return True
        return False

    # ------------------------------------------------------------- desenho
    def _text(self, cr, x, y, txt, color="text", size=10, bold=False,
              align="left", width=None):
        layout = PangoCairo.create_layout(cr)
        desc = Pango.FontDescription("Sans %s%d" % ("Bold " if bold else "", size))
        layout.set_font_description(desc)
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

    def _measure(self, cr, txt, size=10, bold=False):
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(
            Pango.FontDescription("Sans %s%d" % ("Bold " if bold else "", size)))
        layout.set_text(txt, -1)
        return layout.get_pixel_size()[0]

    def _value(self, cr, x, y, w, value):
        """Valor alinhado a' direita; quebra em duas linhas se nao couber.

        "11.2GB/31.1GB" mede 91 px numa coluna de 68 e invadia a barra. Quando
        o texto cabe -- "84°C", "17%" -- segue numa linha so'.
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

    def _row(self, cr, y, w, label, pct, value, color):
        self._text(cr, PAD, y, label, "dim", 9, bold=True)
        bx = PAD + LABEL_W
        bw = w - PAD * 2 - LABEL_W - VALUE_W
        self._bar(cr, bx, y, bw, pct, color)
        self._value(cr, bx + bw + 6, y, VALUE_W - 6, value)

    def _chevron(self, cr, x, y, is_open):
        """Triangulinho desenhado a mao: nao depende de glifo da fonte."""
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

    def _core(self, cr, x, y, w, idx, pct):
        self._text(cr, x, y, "CPU%d" % (idx + 1), "dim", 8)
        bx = x + CORE_LABEL_W
        bw = w - CORE_LABEL_W - CORE_VALUE_W - 4
        self._bar(cr, bx, y, bw, pct, level_color(pct), h=5)
        self._text(cr, bx + bw + 4, y, "%.0f%%" % pct, "text", 8,
                   align="right", width=CORE_VALUE_W)

    def _cell(self, cr, x, y, w, label, value, color="text"):
        self._text(cr, x, y, label, "dim", 9)
        self._text(cr, x, y, value, color, 10, align="right", width=w)

    def _on_draw(self, widget, cr):
        alloc = widget.get_allocation()
        w = alloc.width
        m = self.m
        if m is None:
            return False

        self._hit = {}
        warn, crit = self.cfg["temp_warn"], self.cfg["temp_crit"]
        col_w = (w - PAD * 2 - 10) / 2
        cx2 = PAD + col_w + 10
        y = ROW_H / 2 + 2

        # ---- CPU, com os nucleos
        self._row(cr, y, w, "CPU", m.cpu, "%.0f%%" % m.cpu, level_color(m.cpu))
        self._chevron(cr, PAD + 27, y, self.cpu_expanded)
        self._hit["cpu"] = (y - ROW_H / 2, y + ROW_H / 2)
        y += ROW_H / 2

        if self._core_rows():
            y += 2
            for i, pct in enumerate(m.cpu_cores):
                cx = PAD + (i % 2) * (col_w + 10)
                cy = y + CORE_ROW_H / 2 + (i // 2) * CORE_ROW_H
                self._core(cr, cx, cy, col_w, i, pct)
            y += self._core_rows() * CORE_ROW_H + 4

        # ---- RAM
        y += ROW_H / 2
        self._row(cr, y, w, "RAM", m.ram_pct,
                  "%s/%s" % (fmt_bytes(m.ram_used), fmt_bytes(m.ram_total)),
                  level_color(m.ram_pct))
        y += ROW_H

        # ---- temperatura da CPU
        if m.temp is None:
            self._row(cr, y, w, "TEMP", 0, "--", "dim")
        else:
            pct = max(0.0, min((m.temp - 30) / (crit + 10 - 30) * 100, 100))
            self._row(cr, y, w, "TEMP", pct, "%.0f°C" % m.temp,
                      level_color(m.temp, warn, crit))
        y += ROW_H / 2

        # ---- GPU, com os detalhes
        g = self._gpu()
        if g is not None:
            y += ROW_H / 2
            if g.util is not None:
                self._row(cr, y, w, "GPU", g.util, "%.0f%%" % g.util,
                          level_color(g.util))
            elif g.clock_pct is not None:
                # sem uso real (caso do i915 sem root): mostra o clock, e diz
                # que e' clock, em vez de fingir que e' porcentagem de uso
                self._row(cr, y, w, "GPU", g.clock_pct, "%.0fMHz" % g.clock,
                          level_color(g.clock_pct))
            else:
                self._row(cr, y, w, "GPU", 0, "--", "dim")
            self._chevron(cr, PAD + 27, y, self.gpu_expanded)
            self._hit["gpu"] = (y - ROW_H / 2, y + ROW_H / 2)
            y += ROW_H / 2

            if self._gpu_rows():
                y += 2
                self._text(cr, PAD, y + GPU_NAME_H / 2, g.short, "dim", 8)
                y += GPU_NAME_H
                for i, (lab, val, color) in enumerate(self._gpu_cells()):
                    cx = PAD + (i % 2) * (col_w + 10)
                    cy = y + GRID_H / 2 + (i // 2) * GRID_H
                    self._cell(cr, cx, cy, col_w, lab, val, color)
                y += self._gpu_rows() * GRID_H + 2

        # ---- grade compacta
        y += ROW_H / 2 - 2
        self._cell(cr, PAD, y, col_w, "baixada", fmt_rate(m.net_down), "cyan")
        self._cell(cr, cx2, y, col_w, "subida", fmt_rate(m.net_up), "cyan")
        y += GRID_H

        ping = "--" if m.ping is None else "%.0fms" % m.ping
        ping_col = "dim" if m.ping is None else (
            "green" if m.ping < 50 else "amber" if m.ping < 120 else "red")
        self._cell(cr, PAD, y, col_w, "ping", ping, ping_col)
        disk_extra = " · %.0f°C" % m.nvme_temp if m.nvme_temp else ""
        self._cell(cr, cx2, y, col_w, "disco",
                   "%.0f%%%s" % (m.disk_pct, disk_extra),
                   level_color(m.disk_pct, 80, 92))
        y += GRID_H

        if m.battery_pct is None:
            self._cell(cr, PAD, y, col_w, "bateria", "--", "dim")
        else:
            icon = "⚡" if m.battery_plugged else ""
            self._cell(cr, PAD, y, col_w, "bateria",
                       "%.0f%%%s" % (m.battery_pct, icon),
                       "green" if m.battery_pct > 40 or m.battery_plugged else "red")
        if self.speed_text:
            self._cell(cr, cx2, y, col_w, "banda", self.speed_text, "accent")
        else:
            self._cell(cr, cx2, y, col_w, "ligado há", fmt_secs(m.uptime), "text")
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
