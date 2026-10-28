"""Teste de banda sob demanda, contra os endpoints publicos da Cloudflare.

So' roda quando o usuario clica: baixa ~10 MB e sobe ~4 MB. Nada disso
acontece em background.
"""

import threading
import time
import urllib.request

DOWN_URL = "https://speed.cloudflare.com/__down?bytes={n}"
UP_URL = "https://speed.cloudflare.com/__up"
DOWN_BYTES = 10 * 1024 * 1024
UP_BYTES = 4 * 1024 * 1024
TIMEOUT = 20


def _download():
    req = urllib.request.Request(DOWN_URL.format(n=DOWN_BYTES),
                                 headers={"User-Agent": "MyPCStatus/1.0"})
    got = 0
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            got += len(chunk)
    dt = max(time.monotonic() - t0, 1e-3)
    return got * 8 / dt / 1e6          # Mbit/s


def _upload():
    payload = b"0" * UP_BYTES
    req = urllib.request.Request(UP_URL, data=payload, method="POST",
                                 headers={"Content-Type": "application/octet-stream",
                                          "User-Agent": "MyPCStatus/1.0"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        resp.read()
    dt = max(time.monotonic() - t0, 1e-3)
    return UP_BYTES * 8 / dt / 1e6


def run_async(on_progress, on_done):
    """on_progress(texto) e on_done(down_mbps, up_mbps, erro) vem de outra thread.

    Quem chama e' responsavel por voltar para a main loop (GLib.idle_add).
    """
    def worker():
        try:
            on_progress("baixando...")
            down = _download()
            on_progress("enviando...")
            try:
                up = _upload()
            except Exception:
                up = None              # upload falha mais; download ja' vale
            on_done(down, up, None)
        except Exception as exc:
            on_done(None, None, str(exc))

    threading.Thread(target=worker, daemon=True).start()
