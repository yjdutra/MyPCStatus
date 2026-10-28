"""Coleta de metricas do sistema.

As leituras baratas (psutil sobre /proc e /sys) rodam direto no loop principal,
a cada segundo. So' o ping vai para uma thread, porque bloqueia.
"""

import collections
import os
import shutil
import subprocess
import threading
import time

import psutil

from .gpu import GpuMonitor

# ordem de preferencia para "a" temperatura do sistema
_TEMP_PREF = [
    ("coretemp", "Package id 0"),
    ("k10temp", "Tctl"),
    ("zenpower", "Tdie"),
    ("acpitz", ""),
]

HIST = 60          # segundos de historico para os graficos


class Metrics:
    def __init__(self, smooth=3):
        # a leitura de 1 s pula muito; a media movel curta deixa o numero
        # legivel sem esconder picos reais (smooth=1 desliga)
        self._cpu_window = collections.deque(maxlen=max(1, int(smooth)))
        self.cpu = 0.0
        self.cpu_cores = []        # suavizado, um por nucleo
        self.cpu_cores_raw = []    # leitura crua do ultimo segundo
        self.ram_pct = 0.0
        self.ram_used = 0
        self.ram_total = psutil.virtual_memory().total
        self.swap_pct = 0.0
        self.temp = None
        self.temp_label = "--"
        self.net_down = 0.0        # bytes/s
        self.net_up = 0.0
        self.ping = None           # ms
        self.ping_host = "1.1.1.1"
        self.disk_pct = 0.0
        self.disk_used = 0
        self.disk_total = 0
        self.nvme_temp = None
        self.battery_pct = None
        self.battery_plugged = False
        self.battery_left = None   # segundos
        self.uptime = 0

        self.cpu_hist = collections.deque([0.0] * HIST, maxlen=HIST)
        self.ram_hist = collections.deque([0.0] * HIST, maxlen=HIST)
        self.temp_hist = collections.deque([0.0] * HIST, maxlen=HIST)

        self._last_net = psutil.net_io_counters()
        self._last_t = time.monotonic()
        self._ping_stop = threading.Event()
        self._ping_thread = None
        self.gpus = GpuMonitor()

        psutil.cpu_percent(interval=None, percpu=True)   # descarta a 1a leitura

    # ------------------------------------------------------------- ciclo
    def start(self):
        self._start_ping()
        self.gpus.start()

    def stop(self):
        self._ping_stop.set()
        self.gpus.stop()

    # ------------------------------------------------------------- ping
    def _start_ping(self):
        if self._ping_thread:
            return
        self._ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
        self._ping_thread.start()

    def _ping_loop(self):
        ping = shutil.which("ping")
        while not self._ping_stop.is_set():
            if not ping:
                self.ping = None
            else:
                try:
                    out = subprocess.run(
                        [ping, "-c", "1", "-W", "2", self.ping_host],
                        capture_output=True, text=True, timeout=5,
                    ).stdout
                    self.ping = None
                    for part in out.split():
                        if part.startswith("time="):
                            self.ping = float(part[5:])
                            break
                except (subprocess.SubprocessError, ValueError, OSError):
                    self.ping = None
            self._ping_stop.wait(10)

    # ------------------------------------------------------------- leitura
    def sample(self):
        now = time.monotonic()
        dt = max(now - self._last_t, 1e-3)
        self._last_t = now

        raw = psutil.cpu_percent(interval=None, percpu=True)
        self.cpu_cores_raw = raw
        n = len(raw)
        if n:
            self._cpu_window.append(raw)
            # ignora amostras de tamanho diferente (nucleo entrando/saindo)
            window = [w for w in self._cpu_window if len(w) == n] or [raw]
            self.cpu_cores = [sum(w[i] for w in window) / len(window)
                              for i in range(n)]
            self.cpu = sum(self.cpu_cores) / n
        else:
            self.cpu_cores = []
            self.cpu = 0.0

        vm = psutil.virtual_memory()
        self.ram_pct = vm.percent
        self.ram_used = vm.total - vm.available
        self.ram_total = vm.total
        try:
            self.swap_pct = psutil.swap_memory().percent
        except OSError:
            self.swap_pct = 0.0

        self.temp, self.temp_label = self._read_temp()

        net = psutil.net_io_counters()
        self.net_down = max(net.bytes_recv - self._last_net.bytes_recv, 0) / dt
        self.net_up = max(net.bytes_sent - self._last_net.bytes_sent, 0) / dt
        self._last_net = net

        try:
            du = psutil.disk_usage("/")
            self.disk_pct, self.disk_used, self.disk_total = du.percent, du.used, du.total
        except OSError:
            pass

        bat = psutil.sensors_battery()
        if bat:
            self.battery_pct = bat.percent
            self.battery_plugged = bat.power_plugged
            self.battery_left = (bat.secsleft if bat.secsleft and bat.secsleft > 0
                                 else None)

        self.gpus.sample()
        self.uptime = time.time() - psutil.boot_time()

        self.cpu_hist.append(self.cpu)
        self.ram_hist.append(self.ram_pct)
        self.temp_hist.append(self.temp or 0.0)
        return self

    def _read_temp(self):
        try:
            temps = psutil.sensors_temperatures()
        except (AttributeError, OSError):
            return None, "--"
        if not temps:
            return None, "--"

        for chip, label in _TEMP_PREF:
            for entry in temps.get(chip, []):
                if not label or entry.label == label:
                    self.nvme_temp = self._nvme(temps)
                    return entry.current, chip
        # sem sensor conhecido: pega o mais quente que parecer plausivel
        best = None
        for chip, entries in temps.items():
            for e in entries:
                if e.current and 20 < e.current < 120:
                    if best is None or e.current > best[0]:
                        best = (e.current, chip)
        self.nvme_temp = self._nvme(temps)
        return best if best else (None, "--")

    @staticmethod
    def _nvme(temps):
        vals = [e.current for e in temps.get("nvme", []) if e.current and e.current > 10]
        return max(vals) if vals else None


def fmt_bytes(n, suffix="B"):
    for unit in ("", "K", "M", "G", "T"):
        if abs(n) < 1024:
            return f"{n:.0f}{unit}{suffix}" if unit == "" else f"{n:.1f}{unit}{suffix}"
        n /= 1024
    return f"{n:.1f}P{suffix}"


def fmt_rate(bps):
    return fmt_bytes(bps) + "/s"


def fmt_secs(s):
    if s is None:
        return "--"
    s = int(s)
    h, m = s // 3600, (s % 3600) // 60
    if h >= 24:
        return f"{h // 24}d {h % 24}h"
    return f"{h}h {m:02d}m" if h else f"{m}m"
