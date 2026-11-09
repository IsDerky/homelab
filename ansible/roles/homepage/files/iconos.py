#!/usr/bin/env python3
"""Iconos pixel-art de la página de inicio (16x16, SVG).

Cada icono es un dibujo de 16 filas de 16 caracteres; cada carácter es un
color de la paleta (la de la oficina) y "." es transparente. Genera
icons/<nombre>.svg junto a este script:  python3 iconos.py
"""

import os

PALETA = {
    "k": "#121214",  # contorno
    "w": "#f0efec",
    "g": "#c3c2b7",
    "m": "#8f8e86",
    "d": "#34332f",
    "b": "#3987e5",
    "B": "#1f5fae",
    "c": "#22d3ee",
    "o": "#d95926",
    "y": "#c98500",
    "Y": "#f2b632",
    "G": "#199e70",
    "l": "#22c55e",
    "r": "#d55181",
    "p": "#8b5cf6",
}

ICONOS = {
    "inicio": [
        "................",
        ".......kk.......",
        "......kook......",
        ".....kooook.....",
        "....kooooook....",
        "...kooooooook...",
        "..kooooooooook..",
        ".kkkkkkkkkkkkkk.",
        "..kggggggggggk..",
        "..kgbbgggkkkgk..",
        "..kgbbgggkyykk..",
        "..kggggggkyykk..",
        "..kggggggkyykk..",
        "..kkkkkkkkkkkk..",
        "................",
        "................",
    ],
    "oficina": [
        "................",
        "....kkkkkkkk....",
        "....kggggggk....",
        "....kgbgbgbk....",
        "....kggggggk....",
        "....kgYgbgYk....",
        "....kggggggk....",
        "....kgbgYgbk....",
        "....kggggggk....",
        "....kgYgbgbk....",
        "....kggggggk....",
        "....kggooggk....",
        "....kggooggk....",
        "..kkkkkkkkkkkk..",
        "..kmmmmmmmmmmk..",
        "..kkkkkkkkkkkk..",
    ],
    "honeypot": [
        "................",
        "................",
        "....kkkkkkkk....",
        "....kooooook....",
        "...kkkkYkkkkk...",
        "..kYYYYYYYYYYk..",
        "..kYwYYYYYYYYk..",
        ".kYYwYYYYYYYYYk.",
        ".kYwYYYYYYYYYYk.",
        ".kYYYYYYYYYYYYk.",
        ".kyYYYYYYYYYYyk.",
        "..kyYYYYYYYYyk..",
        "..kyyyyyyyyyyk..",
        "...kkkkkkkkkk...",
        "................",
        "................",
    ],
    "grafana": [
        "................",
        "................",
        ".kkkkkkkkkkkkkk.",
        ".kddddddddddddk.",
        ".kdddddddddddok.",
        ".kddddddddddodk.",
        ".kdddddddoddddk.",
        ".kddoddddodddbk.",
        ".kdododdodddbbk.",
        ".kodddoodddbbbk.",
        ".kddddddddbdbbk.",
        ".kddbddbddbdbbk.",
        ".kddbddbddbdbbk.",
        ".kkkkkkkkkkkkkk.",
        "................",
        "................",
    ],
    "adguard": [
        "................",
        ".....kkkkkk.....",
        "...kkGGGGGGkk...",
        "..kGGGGGGGGGGk..",
        "..kGGGGGGGGGGk..",
        "..kGGGGGGGGwGk..",
        "..kGGGGGGGwwGk..",
        "..kGwGGGGwwGGk..",
        "..kGwwGGwwGGGk..",
        "...kGwwwwGGGk...",
        "...kGGwwGGGGk...",
        "....kGGGGGGk....",
        ".....kGGGGk.....",
        "......kkkk......",
        "................",
        "................",
    ],
    "codigo": [
        "................",
        "................",
        ".kkkkkkkkkkkkkk.",
        ".kBBBBBBBBBBBBk.",
        ".kBBBBBBBBwBBBk.",
        ".kBBBcBBBwBcBBk.",
        ".kBBcBBBwBBBcBk.",
        ".kBcBBBBwBBBBck.",
        ".kBBcBBwBBBBcBk.",
        ".kBBBcBwBBBcBBk.",
        ".kBBBBwBBBBBBBk.",
        ".kBBBBBBBBBBBBk.",
        ".kkkkkkkkkkkkkk.",
        "......kmmk......",
        "....kkkkkkkk....",
        "................",
    ],
    "juegos": [
        "................",
        "................",
        "................",
        "................",
        "...kkkkkkkkkk...",
        "..kmmmmmmmmmmk..",
        ".kmmwmmmmmmrmmk.",
        ".kmwwwmmmmrmrmk.",
        ".kmmwmmmmmmrmmk.",
        ".kmmmmmkkmmmmmk.",
        ".kmmmmk..kmmmmk.",
        "..kkkk....kkkk..",
        "................",
        "................",
        "................",
        "................",
    ],
    "bentonime": [
        "................",
        "....k.....k.....",
        ".....k...k......",
        "......k.k.......",
        ".kkkkkkkkkkkkkk.",
        ".kppppppppppppk.",
        ".kpddddddddddpk.",
        ".kpddcdddddddpk.",
        ".kpddccddddddpk.",
        ".kpddcccdddddpk.",
        ".kpddccddddddpk.",
        ".kpddcdddddddpk.",
        ".kpddddddddddpk.",
        ".kppppppppppppk.",
        ".kkkkkkkkkkkkkk.",
        "................",
    ],
    "futbol": [
        "................",
        ".....kkkkkk.....",
        "...kkwwwwwwkk...",
        "..kwwwwmmwwwwk..",
        "..kwwwmmmmwwwk..",
        ".kwwwwmmmmwwwwk.",
        ".kmwwwwmmwwwwmk.",
        ".kmmwwwwwwwwmmk.",
        ".kmwwwwwwwwwwmk.",
        ".kwwwwmmmmwwwwk.",
        "..kwwmmmmmmwwk..",
        "..kwwwmmmmwwwk..",
        "...kkwwwwwwkk...",
        ".....kkkkkk.....",
        "................",
        "................",
    ],
    "hosting": [
        "................",
        ".....kkkkkk.....",
        "...kkbbGGbbkk...",
        "..kbbbGGGbbbbk..",
        "..kbbGGGGGbbbk..",
        ".kbbbbGGGbbGGbk.",
        ".kbbbbbGbbGGGbk.",
        ".kbbbbbbbbGGbbk.",
        ".kbGGbbbbbbbbbk.",
        ".kbGGGbbbbbbbbk.",
        "..kbGGGbbbGbbk..",
        "..kbbGbbbGGGbk..",
        "...kkbbbbbbkk...",
        ".....kkkkkk.....",
        "................",
        "................",
    ],
    "nas": [
        "................",
        ".kkkkkkkkkkkkkk.",
        ".kggggggggggggk.",
        ".kgmmmmmmmmlggk.",
        ".kggggggggggggk.",
        ".kkkkkkkkkkkkkk.",
        ".kggggggggggggk.",
        ".kgmmmmmmmmlggk.",
        ".kggggggggggggk.",
        ".kkkkkkkkkkkkkk.",
        ".kggggggggggggk.",
        ".kgmmmmmmmmlggk.",
        ".kggggggggggggk.",
        ".kkkkkkkkkkkkkk.",
        "................",
        "................",
    ],
    "vault": [
        "................",
        ".kkkkkkkkkkkkkk.",
        ".kmmmmmmmmmmmmk.",
        ".kmddddddddddmk.",
        ".kmdggggggggdmk.",
        ".kmdggkkkkggdmk.",
        ".kmdgkYYYYkgdmk.",
        ".kmmgkYkkYkgdmk.",
        ".kmmgkYkkYkgdmk.",
        ".kmdgkYYYYkgdmk.",
        ".kmdggkkkkggdmk.",
        ".kmddddddddddmk.",
        ".kmmmmmmmmmmmmk.",
        ".kkkkkkkkkkkkkk.",
        "..kk........kk..",
        "................",
    ],
    "pagos": [
        "................",
        "................",
        "................",
        "..kkkkkkkkkkkk..",
        ".kggggggggggggk.",
        ".kddddddddddddk.",
        ".kddddddddddddk.",
        ".kmmmmmmmmmmmmk.",
        ".kmYYYmmmmmmmmk.",
        ".kmYkYmmmmmmmmk.",
        ".kmmmmmmmmmmmmk.",
        ".kmwwmwwmwwmggk.",
        ".kmmmmmmmmmmmmk.",
        "..kkkkkkkkkkkk..",
        "................",
        "................",
    ],
}


def svg(filas):
    # Un rect por tramo horizontal del mismo color
    rects = []
    for y, fila in enumerate(filas):
        x = 0
        while x < 16:
            c = fila[x]
            fin = x
            while fin + 1 < 16 and fila[fin + 1] == c:
                fin += 1
            if c != ".":
                rects.append(f'<rect x="{x}" y="{y}" width="{fin - x + 1}" height="1" fill="{PALETA[c]}"/>')
            x = fin + 1
    cuerpo = "".join(rects)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" shape-rendering="crispEdges">{cuerpo}</svg>\n'


def main():
    salida = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
    os.makedirs(salida, exist_ok=True)
    for nombre, filas in ICONOS.items():
        assert len(filas) == 16 and all(len(f) == 16 for f in filas), nombre
        assert all(c in PALETA or c == "." for f in filas for c in f), nombre
        with open(os.path.join(salida, f"{nombre}.svg"), "w") as f:
            f.write(svg(filas))


if __name__ == "__main__":
    main()
