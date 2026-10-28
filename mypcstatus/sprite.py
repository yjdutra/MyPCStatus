"""Compoe o mascote: corpo + pose + expressao, em grid de caracteres.

Nao depende de GTK nem de cairo de proposito: da' pra testar e renderizar
com PIL fora do app.
"""

from . import art


def _blank():
    return [["." for _ in range(art.WIDTH)] for _ in range(art.HEIGHT)]


def _stamp(grid, col, row, cells, mirror=False):
    for dy, line in enumerate(cells):
        if mirror:
            line = line[::-1]
        for dx, ch in enumerate(line):
            if ch in (".", " "):
                continue            # preserva o que esta' embaixo
            y, x = row + dy, col + dx
            if 0 <= y < art.HEIGHT and 0 <= x < art.WIDTH:
                grid[y][x] = ch


def compose(pose="idle", eyes=None, bob=0, phase=0):
    """Monta um frame.

    pose  -- chave de art.POSES
    eyes  -- sobrescreve a expressao padrao da pose
    bob   -- deslocamento vertical do corpo (respiracao), em pixels logicos
    phase -- 0..3, anima os elementos flutuantes (notas, zzz)
    """
    spec = art.POSES.get(pose, art.POSES["idle"])
    eyes = eyes or spec["eyes"]
    eye_grid = art.EYES.get(eyes, art.EYES["normal"])

    # corpo + olhos + nariz, montados juntos para balancarem como um so'
    body = _blank()
    _stamp(body, 0, 0, art.BASE)
    _stamp(body, art.EYE_L[0], art.EYE_L[1], eye_grid)
    _stamp(body, art.EYE_R[0], art.EYE_R[1], eye_grid,
           mirror=eyes in art.MIRROR_EYES)
    _stamp(body, *art.NOSE)

    out = _blank()
    for y, row in enumerate(body):
        ty = y + bob
        if 0 <= ty < art.HEIGHT:
            for x, ch in enumerate(row):
                if ch != ".":
                    out[ty][x] = ch

    # acessorios ficam parados (o gato que balanca em cima deles)
    for col, row, cells in spec["stamps"]:
        _stamp(out, col, row, cells)

    # flutuantes sobem e descem fora de fase com o corpo
    drift = (0, -1, -2, -1)[phase % 4]
    for i, (col, row, cells) in enumerate(spec["float"]):
        _stamp(out, col, row + drift + (i % 2), cells)

    return out


def to_rgba(grid):
    """Grid -> lista de (x, y, (r, g, b)) para quem for pintar."""
    out = []
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            hexc = art.PALETTE.get(ch)
            if hexc is None:
                continue
            out.append((x, y, (int(hexc[1:3], 16),
                               int(hexc[3:5], 16),
                               int(hexc[5:7], 16))))
    return out
