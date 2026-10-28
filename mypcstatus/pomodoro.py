"""Maquina de estados do pomodoro.

O tempo sai de time.monotonic(), nao da contagem de ticks: se a UI travar ou
o timer da GLib atrasar, o relogio continua certo.
"""

import time

IDLE, FOCUS, SHORT, LONG, PAUSED = "idle", "focus", "short", "long", "paused"

LABELS = {
    IDLE:  "pronto",
    FOCUS: "foco",
    SHORT: "pausa",
    LONG:  "pausa longa",
}


class Pomodoro:
    def __init__(self, cfg, on_phase_end=None):
        self.cfg = cfg
        self.on_phase_end = on_phase_end
        self.phase = IDLE
        self.prev_phase = IDLE          # o que estava rodando antes de pausar
        self.done_focus = 0             # focos concluidos no ciclo atual
        self._ends_at = None            # time.monotonic() do fim
        self._left_when_paused = None

    # ------------------------------------------------------------- duracoes
    def duration(self, phase):
        return {
            FOCUS: self.cfg["focus_min"],
            SHORT: self.cfg["short_min"],
            LONG:  self.cfg["long_min"],
        }.get(phase, 0) * 60

    @property
    def running(self):
        return self.phase in (FOCUS, SHORT, LONG)

    @property
    def remaining(self):
        if self.phase == PAUSED:
            return self._left_when_paused or 0
        if self._ends_at is None:
            return self.duration(FOCUS)
        return max(self._ends_at - time.monotonic(), 0)

    @property
    def progress(self):
        """0.0 -> 1.0 do quanto ja' passou da fase atual."""
        base = self.duration(self.prev_phase if self.phase == PAUSED else self.phase)
        if not base:
            return 0.0
        return 1.0 - (self.remaining / base)

    @property
    def label(self):
        if self.phase == PAUSED:
            return f"{LABELS.get(self.prev_phase, '')} (pausado)"
        return LABELS.get(self.phase, "")

    # ------------------------------------------------------------- controles
    def start(self, phase=FOCUS):
        self.phase = phase
        self._ends_at = time.monotonic() + self.duration(phase)
        self._left_when_paused = None

    def toggle(self):
        if self.phase == IDLE:
            self.start(FOCUS)
        elif self.phase == PAUSED:
            self.phase = self.prev_phase
            self._ends_at = time.monotonic() + (self._left_when_paused or 0)
            self._left_when_paused = None
        else:
            self._left_when_paused = self.remaining
            self.prev_phase = self.phase
            self.phase = PAUSED

    def reset(self):
        self.phase = IDLE
        self.prev_phase = IDLE
        self.done_focus = 0
        self._ends_at = None
        self._left_when_paused = None

    def skip(self):
        """Encerra a fase atual na marra e vai para a proxima."""
        if self.phase in (IDLE, PAUSED):
            self.phase = self.prev_phase if self.phase == PAUSED else FOCUS
        self._advance(skipped=True)

    # ------------------------------------------------------------- tick
    def tick(self):
        """Chamado 1x/s. Devolve True se a fase virou agora."""
        if not self.running:
            return False
        if self.remaining > 0:
            return False
        self._advance(skipped=False)
        return True

    def _advance(self, skipped):
        finished = self.phase
        if finished == FOCUS:
            self.done_focus += 1
            if self.done_focus % max(self.cfg["cycles"], 1) == 0:
                nxt = LONG
            else:
                nxt = SHORT
        else:
            nxt = FOCUS
        self.start(nxt)
        if self.on_phase_end and not skipped:
            self.on_phase_end(finished, nxt)

    @staticmethod
    def clock(seconds):
        seconds = int(seconds + 0.5)
        return f"{seconds // 60:02d}:{seconds % 60:02d}"
