"""O mascote desenhado e animado num Gtk.DrawingArea."""

import random
import time

import cairo
from . import gtkcompat                      # noqa: F401  (fixa as versoes)
from gi.repository import GLib, Gtk

from . import art, sprite
from .pomodoro import FOCUS, LONG, PAUSED, SHORT

FPS_MS = 130
BOB = (0, 0, 0, 1, 1, 1, 0, 0)       # respiracao: 8 frames
BLINK_S = 0.26
CACHE_MAX = 64


class MascotArea(Gtk.DrawingArea):
    def __init__(self, scale=4):
        super().__init__()
        self.scale = scale
        self.pose = "idle"
        self.eyes = None                 # None = usa a expressao da pose
        self.set_size_request(art.WIDTH * scale, art.HEIGHT * scale)

        self._frame = 0
        self._cache = {}
        self._blink_until = 0.0
        self._next_blink = time.monotonic() + random.uniform(3, 7)

        self.connect("draw", self._on_draw)
        self._timer = GLib.timeout_add(FPS_MS, self._on_tick)

    def stop(self):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = None

    def set_scale(self, scale):
        if scale != self.scale:
            self.scale = scale
            self._cache.clear()
            self.set_size_request(art.WIDTH * scale, art.HEIGHT * scale)
            self.queue_draw()

    # ------------------------------------------------------------- animacao
    def _on_tick(self):
        self._frame = (self._frame + 1) % len(BOB)
        now = time.monotonic()
        if now >= self._next_blink:
            self._blink_until = now + BLINK_S
            self._next_blink = now + random.uniform(3.5, 9.0)
        self.queue_draw()
        return True

    def _state(self):
        eyes = self.eyes
        if time.monotonic() < self._blink_until and self.pose != "sleep":
            eyes = "sleepy"              # piscada rapida
        return (self.pose, eyes, BOB[self._frame], self._frame % 4)

    def _surface(self, key):
        surf = self._cache.get(key)
        if surf is None:
            if len(self._cache) > CACHE_MAX:
                self._cache.clear()
            pose, eyes, bob, phase = key
            grid = sprite.compose(pose, eyes, bob, phase)
            w, h = art.WIDTH * self.scale, art.HEIGHT * self.scale
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
            cr = cairo.Context(surf)
            for x, y, (r, g, b) in sprite.to_rgba(grid):
                cr.set_source_rgb(r / 255, g / 255, b / 255)
                cr.rectangle(x * self.scale, y * self.scale, self.scale, self.scale)
                cr.fill()
            self._cache[key] = surf
        return surf

    def _on_draw(self, widget, cr):
        surf = self._surface(self._state())
        alloc = widget.get_allocation()
        w, h = art.WIDTH * self.scale, art.HEIGHT * self.scale
        cr.set_source_surface(surf, (alloc.width - w) // 2, (alloc.height - h) // 2)
        cr.paint()
        return False


class Mood:
    """Escolhe pose e fala do gato a partir das metricas e do pomodoro.

    Sem sinal forte, o gato vai rodando entre as atividades (notebook, musica,
    livro, cafe) para a janela nao ficar parada.
    """

    IDLE_ROTATION = ("idle", "music", "work", "read", "coffee", "idle")
    ROTATE_EVERY = 24.0

    def __init__(self, cfg):
        self.cfg = cfg
        self._i = 0
        self._next_rotate = time.monotonic() + self.ROTATE_EVERY

    def pick(self, m, pomo):
        """Devolve (pose, eyes_override, frase)."""
        warn, crit = self.cfg["temp_warn"], self.cfg["temp_crit"]
        temp = m.temp

        if temp is not None and temp >= crit:
            return "hot", None, f"{temp:.0f}°C! tá fervendo aqui"
        if pomo.phase == FOCUS:
            return "work", ("strain" if m.cpu > 85 else None), "foco — tô junto"
        if pomo.phase == SHORT:
            return "coffee", None, "pausa curta, respira"
        if pomo.phase == LONG:
            return "read", None, "pausa longa, sai da cadeira"
        if pomo.phase == PAUSED:
            return "idle", "neutral", "pausado — volta quando quiser"
        if m.cpu >= 88:
            return "alert", None, f"CPU em {m.cpu:.0f}%, segura aí"
        if m.ram_pct >= 90:
            return "alert", "surprise", f"RAM em {m.ram_pct:.0f}%"
        if temp is not None and temp >= warn:
            return "hot", None, f"{temp:.0f}°C, tá esquentando"
        if m.disk_pct >= 90:
            return "idle", "curious", f"disco em {m.disk_pct:.0f}%, dá uma limpada"

        now = time.monotonic()
        if now >= self._next_rotate:
            self._i = (self._i + 1) % len(self.IDLE_ROTATION)
            self._next_rotate = now + self.ROTATE_EVERY
        pose = self.IDLE_ROTATION[self._i]
        if m.cpu < 6 and pose == "idle":
            return "sleep", None, "tudo quieto por aqui"
        return pose, None, None
