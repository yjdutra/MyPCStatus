"""Descobre o IP publico da maquina, sob demanda.

Duas decisoes de privacidade deliberadas:

* Nada e' buscado sozinho. A consulta so' sai quando voce clica, porque cada
  consulta entrega seu IP a um terceiro -- inevitavel para descobri-lo, mas
  nao ha' razao para fazer isso a cada vez que o app abre.
* O valor fica OCULTO ate' voce mandar mostrar, para nao vazar em captura de
  tela, em compartilhamento de tela ou para quem passar atras de voce.

A resposta e' validada como endereco IP de verdade: portal cativo de wi-fi
publico devolve HTML com status 200, e sem a checagem isso viraria "IP".
"""

import ipaddress
import threading
import urllib.request

# varios servicos porque um pode estar fora do ar ou bloqueado na rede
SERVICES = (
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
    "https://icanhazip.com",
)
TIMEOUT = 6


def _looks_like_ip(text):
    try:
        ipaddress.ip_address(text.strip())
        return True
    except ValueError:
        return False


def fetch():
    """Devolve (ip, erro). Bloqueia: chame de uma thread."""
    last = "sem resposta"
    for url in SERVICES:
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "MyPCStatus/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                body = resp.read(64).decode("utf-8", "replace").strip()
            if _looks_like_ip(body):
                return body, None
            last = "resposta inesperada"      # provavelmente portal cativo
        except Exception as exc:
            last = type(exc).__name__
    return None, last


def fetch_async(on_done):
    """on_done(ip, erro) vem de outra thread: volte para a main loop."""
    threading.Thread(target=lambda: on_done(*fetch()), daemon=True).start()
