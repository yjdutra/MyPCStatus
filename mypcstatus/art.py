"""Pixel art do mascote.

Tudo e' desenhado em grids de caracteres: cada caractere e' um pixel logico
cuja cor vem de PALETTE. O ponto '.' significa transparente; o espaco ' '
significa "nao mexe" e so' aparece em stamps sobrepostos ao corpo.

O gato base ocupa um canvas de WIDTH x HEIGHT pixels logicos. As expressoes
sao carimbadas por cima nas cavidades dos olhos, e as poses carimbam
acessorios (notebook, livro, notas musicais).
"""

WIDTH = 40
HEIGHT = 34

PALETTE = {
    ".": None,          # transparente
    "D": "#1B1E27",     # corpo escuro
    "S": "#13161D",     # sombra do corpo
    "L": "#98A3B8",     # pelo claro (contorno, listras, patas)
    "M": "#6B7389",     # pelo medio
    "B": "#5E64E8",     # fone de ouvido
    "b": "#8A8FF5",     # fone de ouvido, brilho
    "E": "#F4BD57",     # olho ambar
    "e": "#8A6C33",     # olho, sombra
    "N": "#E38BA6",     # rosa (orelha, nariz)
    "W": "#FFFFFF",     # brilho
    "G": "#2B3040",     # acessorio escuro (notebook)
    "g": "#4A5168",     # acessorio claro
    "C": "#7BE0E8",     # tela ciano
    "R": "#E8705E",     # vermelho (capa do livro)
    "Y": "#F4BD57",     # amarelo (notas, cafe)
}

# ---------------------------------------------------------------- corpo base
# Gato sentado de frente, fone de ouvido, rabo listrado a' direita.
BASE = [
    "........................................",  # 0
    "........................................",  # 1
    "..........L................L............",  # 2
    "..........L.....bbbbbb.....L............",  # 3
    "..........LL..bbBBBBBBbb..LL............",  # 4
    ".........LNDLbbbbbbbbbbbbLDNL...........",  # 5
    ".........LNNDLLLLLLLLLLLLDNNL...........",  # 6
    ".........LDDDDDDDDDDDDDDDDDDL...........",  # 7
    "........LNDDDDDDDDDDDDDDDDDDNL..........",  # 8
    "........LDDDDDDDDDDDDDDDDDDDDL..........",  # 9
    ".......LLDDDDDDDDDDDDDDDDDDDDLL.........",  # 10
    ".......bbLDDDDDDDDDDDDDDDDDDLbb.........",  # 11
    "......bBBbDDDDDDDDDDDDDDDDDDbBBb........",  # 12
    "......bBBbDDDDDDDDDDDDDDDDDDbBBb........",  # 13
    "......bBBbDDDDDDDDDDDDDDDDDDbBBb........",  # 14
    "......bBBbDDDDDDLLLLLLDDDDDDbBBb........",  # 15
    ".......bb.LDDDDLLLLLLLLDDDDL.bb.........",  # 16
    "..........LLDDDLLLLLLLLDDDLLLL..........",  # 17
    "............LDDDLLLLLLDDDL.LLL..........",  # 18
    ".............LDDDDDDDDDDL..LLLL.........",  # 19
    "............LDDDDDDDDDDDDL..LMML........",  # 20
    "............LDDDDDDDDDDDDL...LLL........",  # 21
    "............LDDDDDDDDDDDDL...LLL........",  # 22
    "............LDDDDDDDDDDDDL...LLL........",  # 23
    "............LDDDDDDDDDDDDL...LML........",  # 24
    "............LDDDDDDDDDDDDL...LLL........",  # 25
    "............LDDDDDDDDDDDDL...LLL........",  # 26
    "............LDDDDDDDDDDDDL..LLLL........",  # 27
    ".............LDDDDDDDDDMMMLLMML.........",  # 28
    ".............LLLLDDDDLLLLLLLLL..........",  # 29
    ".............LLLLLLLLLLLLLLLLL..........",  # 30
    ".............LLLLL..LLLLL...............",  # 31
    "..............LLL....LLL................",  # 32
    "........................................",  # 33
]

# ------------------------------------------------------------------- carimbos
# Cada stamp e' (coluna, linha, grid). ' ' preserva o que ja' estava embaixo.

NOSE = (18, 16, [
    "NN",
])

# ------------------------------------------------------------------- expressoes
# Cavidade de 5x4. Desenhadas para o olho ESQUERDO; o direito e' espelhado
# quando a expressao e' assimetrica (ver MIRROR_EYES).
EYES = {
    # 1. padrao: olho redondo
    "normal": [
        ".EEE.",
        "EEEEE",
        "EEEEE",
        ".EEE.",
    ],
    # 2. gota / fofo
    "soft": [
        "..EE.",
        ".EEEE",
        "EEEEE",
        ".EEE.",
    ],
    # 3. feliz ^ ^
    "happy": [
        ".....",
        "..E..",
        ".E.E.",
        "E...E",
    ],
    # 4. curioso (arco)
    "curious": [
        "..E..",
        ".E.E.",
        "EE.EE",
        "EEEEE",
    ],
    # 5. focado / determinado (fenda inclinada)
    "focus": [
        "EE...",
        "EEEE.",
        ".EEEE",
        "...EE",
    ],
    # 6. cansado (apagado, meia palpebra)
    "tired": [
        ".....",
        ".eee.",
        "EEEEE",
        ".EEE.",
    ],
    # 7. neutro (tracinho)
    "neutral": [
        ".....",
        ".EEE.",
        ".EEE.",
        ".....",
    ],
    # 8. surpreso (anel)
    "surprise": [
        ".EEE.",
        "EE.EE",
        "EE.EE",
        ".EEE.",
    ],
    # 9. escaneando (alvo)
    "scan": [
        ".EEE.",
        "EeEeE",
        "EEEEE",
        ".EEE.",
    ],
    # 10. dormindo (curva pra baixo)
    "sleepy": [
        ".....",
        "E...E",
        ".EEE.",
        ".....",
    ],
    # 11. contente (curva fechada)
    "content": [
        ".....",
        ".....",
        "EEEEE",
        ".EEE.",
    ],
    # 12. esforco > <
    "strain": [
        "E...E",
        ".E.E.",
        ".E.E.",
        "E...E",
    ],
    # 13. alerta (brilhante, bem aberto)
    "alert": [
        "EEEEE",
        "EEEEE",
        "EEEEE",
        "EEEEE",
    ],
    # 14. carregando (espiral)
    "load": [
        ".EEE.",
        "EE..E",
        "E.EEE",
        ".EEE.",
    ],
    # 15. alegria (arco largo pra cima)
    "joy": [
        ".....",
        ".EEE.",
        "E...E",
        ".....",
    ],
}

# Expressoes assimetricas que precisam espelhar no olho direito
MIRROR_EYES = {"focus", "strain", "soft", "load"}

EYE_L = (12, 10)   # canto superior esquerdo da cavidade esquerda
EYE_R = (21, 10)   # idem direita


# ------------------------------------------------------------------- acessorios
# Stamps de pose: (coluna, linha, grid). '.' preserva o que esta' embaixo.

LAPTOP = (9, 24, [
    "...GGGGGGGGGGGGGGG...",
    "...GCCCCCCCCCCCCCG...",
    "...GCGGGGGGGCCCCCG...",
    "...GCGGGGGCCCCCCCG...",
    "...GCGGGGGGGGGCCCG...",
    "...GGGGGGGGGGGGGGG...",
    "ggggggggggggggggggggg",
    ".gggLLgggggggggLLggg.",
    "..GGGGGGGGGGGGGGGGG..",
])

BOOK = (11, 25, [
    "RRRRRRRRRRRRRRRRR",
    "RLLLLLLLRLLLLLLLR",
    "RLMMMMMLRLMMMMMLR",
    "RLLLLLLLRLLLLLLLR",
    "RLMMMMMLRLMMMMMLR",
    "RRRRRRRRRRRRRRRRR",
])

MUG = (2, 24, [
    "..M.M..",
    ".M.M...",
    "LLLLLL.",
    "LRRRRLL",
    "LRRRRL.",
    "LRRRRLL",
    "LLLLLL.",
])

NOTE = [
    "..b",
    "..b",
    "bbb",
    "bb.",
]

ZED = [
    "LLL",
    "..L",
    ".L.",
    "L..",
    "LLL",
]

DROP = [
    "..W.",
    ".WWW",
    "WWWW",
    ".WW.",
]

# Poses: lista de stamps fixos + expressao padrao dos olhos.
# 'float' sao stamps que balancam de frame em frame (notas, zzz, suor).
POSES = {
    "idle":   {"stamps": [],       "eyes": "normal",  "float": []},
    "work":   {"stamps": [LAPTOP], "eyes": "focus",   "float": []},
    "read":   {"stamps": [BOOK],   "eyes": "content", "float": []},
    "coffee": {"stamps": [MUG],    "eyes": "soft",    "float": []},
    "music":  {"stamps": [],       "eyes": "happy",
               "float": [(32, 5, NOTE), (4, 9, NOTE)]},
    "sleep":  {"stamps": [],       "eyes": "sleepy",
               "float": [(31, 3, ZED), (35, 8, ZED)]},
    "hot":    {"stamps": [],       "eyes": "strain",
               "float": [(32, 6, DROP), (3, 8, DROP)]},
    "alert":  {"stamps": [],       "eyes": "alert",   "float": []},
}


def validate():
    """Erra alto se algum grid estiver com largura errada."""
    for i, row in enumerate(BASE):
        if len(row) != WIDTH:
            raise ValueError(f"BASE linha {i}: {len(row)} chars, esperado {WIDTH}")
    if len(BASE) != HEIGHT:
        raise ValueError(f"BASE tem {len(BASE)} linhas, esperado {HEIGHT}")
    for name, grid in EYES.items():
        if len(grid) != 4 or any(len(r) != 5 for r in grid):
            raise ValueError(f"expressao {name!r} precisa ser 5x4")
    for ch in {c for row in BASE for c in row}:
        if ch not in PALETTE:
            raise ValueError(f"BASE usa cor desconhecida {ch!r}")


validate()
