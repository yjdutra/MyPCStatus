"""Preferencias gravadas em ~/.config/mypcstatus/config.json."""

import json
import os

DIR = os.path.join(os.path.expanduser("~"), ".config", "mypcstatus")
PATH = os.path.join(DIR, "config.json")

DEFAULTS = {
    "x": -1,              # -1 = posiciona no canto superior direito na 1a vez
    "y": -1,
    "scale": 4,           # pixels de tela por pixel logico do mascote
    "cpu_smooth": 3,      # amostras na media movel da CPU (1 = sem suavizar)
    "cpu_expanded": False,  # dropdown dos nucleos aberto
    "opacity": 1.0,          # 0.85-0.95 deixa o fundo transparecer
    "keep_above": True,
    "focus_min": 25,
    "short_min": 5,
    "long_min": 15,
    "cycles": 4,          # focos ate' a pausa longa
    "autostart_timer": False,
    "sound": True,
    "temp_warn": 75,      # °C: mascote comeca a reclamar
    "temp_crit": 85,      # °C: mascote entra em panico
}


def load():
    cfg = dict(DEFAULTS)
    try:
        with open(PATH) as fh:
            cfg.update(json.load(fh))
    except (OSError, ValueError):
        pass
    return cfg


def save(cfg):
    try:
        os.makedirs(DIR, exist_ok=True)
        tmp = PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(cfg, fh, indent=2)
        os.replace(tmp, PATH)
    except OSError:
        pass          # preferencia nao e' critica: falhou, segue a vida
