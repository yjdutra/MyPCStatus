"""Leitura de GPU, com um backend por fabricante.

O que da' para medir muda bastante conforme o driver:

* NVIDIA  -- `nvidia-smi` entrega uso, VRAM, temperatura e clock. Custa ~16 ms
             por chamada porque sobe um processo, entao vai para uma thread.
* AMD     -- o amdgpu publica `gpu_busy_percent` em sysfs: uso real, de graca.
* Intel   -- o i915 NAO publica uso sem root (precisa do PMU via perf). So' da'
             para ler a frequencia. Isso e' um indicio de carga, nao uso, e a
             interface rotula como clock justamente para nao mentir.
"""

import glob
import os
import re
import shutil
import subprocess
import threading


class Reading:
    """Uma GPU num instante. Campos que o driver nao expoe ficam None."""

    __slots__ = ("name", "vendor", "util", "temp", "mem_used", "mem_total",
                 "clock", "clock_max")

    def __init__(self, name, vendor):
        self.name = name
        self.vendor = vendor
        self.util = None          # % de uso real
        self.temp = None          # °C
        self.mem_used = None      # bytes
        self.mem_total = None
        self.clock = None         # MHz
        self.clock_max = None

    @property
    def mem_pct(self):
        if not self.mem_total:
            return None
        return self.mem_used / self.mem_total * 100

    @property
    def short(self):
        """Nome curto para caber no painel."""
        n = self.name
        m = re.search(r"\[([^\]]+)\]", n)      # lspci poe o modelo entre colchetes
        if m:
            n = m.group(1)
        for junk in ("NVIDIA ", "Corporation ", "Advanced Micro Devices, Inc. ",
                     "Intel ", "GeForce ", "Radeon ", "AMD/ATI "):
            n = n.replace(junk, "")
        return n.strip() or self.vendor

    @property
    def clock_pct(self):
        if not self.clock_max:
            return None
        return self.clock / self.clock_max * 100

    def __repr__(self):
        return ("<%s util=%s temp=%s clock=%s/%s>"
                % (self.name, self.util, self.temp, self.clock, self.clock_max))


def _read(path, cast=int):
    try:
        with open(path) as fh:
            return cast(fh.read().strip())
    except (OSError, ValueError):
        return None


def _pci_names():
    """Mapa 'slot pci' -> nome legivel, via lspci. Roda uma vez so'."""
    out = {}
    lspci = shutil.which("lspci")
    if not lspci:
        return out
    try:
        txt = subprocess.run([lspci, "-mm"], capture_output=True, text=True,
                             timeout=4).stdout
    except (OSError, subprocess.SubprocessError):
        return out
    for line in txt.splitlines():
        parts = re.findall(r'"([^"]*)"|(\S+)', line)
        flat = [a or b for a, b in parts]
        if len(flat) >= 4 and flat[1] in ("VGA compatible controller",
                                          "3D controller", "Display controller"):
            out["0000:" + flat[0]] = "%s %s" % (flat[2], flat[3])
    return out


# ------------------------------------------------------------------ backends
class _SysfsBackend:
    """Base dos backends que so' leem arquivo: custo desprezivel."""

    slow = False

    def __init__(self, card, name, vendor):
        self.card = card
        self.reading = Reading(name, vendor)

    def poll(self):
        raise NotImplementedError


class AmdBackend(_SysfsBackend):
    def poll(self):
        r = self.reading
        dev = os.path.join(self.card, "device")
        r.util = _read(os.path.join(dev, "gpu_busy_percent"), float)
        used = _read(os.path.join(dev, "mem_info_vram_used"))
        total = _read(os.path.join(dev, "mem_info_vram_total"))
        r.mem_used, r.mem_total = used, total
        for h in glob.glob(os.path.join(dev, "hwmon", "hwmon*")):
            milli = _read(os.path.join(h, "temp1_input"))
            if milli:
                r.temp = milli / 1000.0
                break
        khz = _read(os.path.join(dev, "pp_dpm_sclk"), str)
        if khz:
            m = re.search(r"(\d+)Mhz\s*\*", khz)
            if m:
                r.clock = int(m.group(1))


class IntelBackend(_SysfsBackend):
    """So' frequencia: o uso real do i915 exige PMU e, portanto, privilegio."""

    def poll(self):
        r = self.reading
        cur = (_read(os.path.join(self.card, "gt_act_freq_mhz"))
               or _read(os.path.join(self.card, "gt_cur_freq_mhz")))
        r.clock = cur
        r.clock_max = _read(os.path.join(self.card, "gt_max_freq_mhz"))


class NvidiaBackend:
    """Sobe um processo por leitura, entao e' marcado como lento."""

    slow = True
    QUERY = ("name,utilization.gpu,memory.used,memory.total,"
             "temperature.gpu,clocks.sm,clocks.max.sm")

    def __init__(self, index):
        self.index = index
        self.reading = Reading("NVIDIA", "nvidia")

    def poll(self):
        smi = shutil.which("nvidia-smi")
        if not smi:
            return
        try:
            out = subprocess.run(
                [smi, "-i", str(self.index), "--query-gpu=" + self.QUERY,
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=8).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return
        if not out:
            return
        vals = [v.strip() for v in out.split(",")]
        if len(vals) < 7:
            return

        def num(s, scale=1.0):
            try:
                return float(s) * scale
            except ValueError:
                return None            # nvidia-smi devolve "N/A" quando nao sabe

        r = self.reading
        r.name = vals[0] or "NVIDIA"
        r.util = num(vals[1])
        r.mem_used = num(vals[2], 1024 * 1024)
        r.mem_total = num(vals[3], 1024 * 1024)
        r.temp = num(vals[4])
        r.clock = num(vals[5])
        r.clock_max = num(vals[6])


def _detect():
    backends = []
    names = _pci_names()

    for card in sorted(glob.glob("/sys/class/drm/card[0-9]")):
        try:
            driver = os.path.basename(os.readlink(
                os.path.join(card, "device", "driver")))
        except OSError:
            continue
        slot = os.path.basename(os.path.realpath(os.path.join(card, "device")))
        nice = names.get(slot)
        if driver == "amdgpu":
            backends.append(AmdBackend(card, nice or "AMD", "amd"))
        elif driver == "i915" or driver == "xe":
            backends.append(IntelBackend(card, nice or "Intel", "intel"))

    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            out = subprocess.run([smi, "--query-gpu=index",
                                  "--format=csv,noheader"],
                                 capture_output=True, text=True,
                                 timeout=8).stdout
            for line in out.split():
                backends.append(NvidiaBackend(int(line)))
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    return backends


class GpuMonitor:
    """Junta os backends e separa o que e' barato do que e' caro de ler."""

    SLOW_PERIOD = 2.0        # segundos entre leituras dos backends lentos

    def __init__(self):
        self.backends = _detect()
        self._slow = [b for b in self.backends if b.slow]
        self._fast = [b for b in self.backends if not b.slow]
        self._stop = threading.Event()
        self._thread = None

    @property
    def available(self):
        return bool(self.backends)

    @property
    def readings(self):
        return [b.reading for b in self.backends]

    @property
    def primary(self):
        """A GPU que vale mostrar: quem reporta uso real vem primeiro."""
        rs = self.readings
        for r in rs:
            if r.util is not None:
                return r
        return rs[0] if rs else None

    @property
    def secondary(self):
        p = self.primary
        return [r for r in self.readings if r is not p]

    def start(self):
        if self._slow and self._thread is None:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            for b in self._slow:
                b.poll()
            self._stop.wait(self.SLOW_PERIOD)

    def sample(self):
        """Chamado 1x/s na main loop: so' os backends de sysfs."""
        for b in self._fast:
            b.poll()
