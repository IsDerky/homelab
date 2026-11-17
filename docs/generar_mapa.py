#!/usr/bin/env python3
"""Genera docs/mapa.md a partir del código de Ansible: qué rol va a qué máquinas
(playbooks), qué hace cada uno (meta/main.yml) y qué corre solo y cuándo (las
unidades .timer de cada rol, con las variables resueltas con sus defaults).

Lo lanza el CI antes de construir la web, así el mapa no se queda viejo.
Uso: python3 docs/generar_mapa.py   (desde la raíz del repo)
"""
import glob
import os
import re
from collections import defaultdict

import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANSIBLE = os.path.join(RAIZ, "ansible")
SALIDA = os.path.join(RAIZ, "docs", "mapa.md")
GRUPOS = {"homelab": "Servidor de casa", "wings_remotos": "Nodos externos"}


def carga(ruta):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def roles_de_play(play):
    r = []
    for x in play.get("roles") or []:
        r.append(x if isinstance(x, str) else x.get("role") or x.get("name"))
    for t in (play.get("tasks") or []) + (play.get("pre_tasks") or []) + (play.get("post_tasks") or []):
        for clave in ("ansible.builtin.include_role", "ansible.builtin.import_role", "include_role", "import_role"):
            if isinstance(t, dict) and clave in t:
                r.append(t[clave].get("name"))
    return [x for x in r if x]


def donde():
    """{rol: {grupo}} y {rol: {playbook}} recorriendo todos los playbooks."""
    grupos, playbooks = defaultdict(set), defaultdict(set)
    for pb in sorted(glob.glob(os.path.join(ANSIBLE, "playbooks", "*.yml"))):
        for play in carga(pb) if isinstance(carga(pb), list) else []:
            if not isinstance(play, dict) or "import_playbook" in play or "ansible.builtin.import_playbook" in play:
                continue
            hosts = re.split(r"[:,]", str(play.get("hosts", "")))
            for rol in roles_de_play(play):
                playbooks[rol].add(os.path.basename(pb))
                for h in hosts:
                    h = h.strip()
                    if h:
                        grupos[rol].add(h)
    return grupos, playbooks


def defaults(rol):
    ruta = os.path.join(ANSIBLE, "roles", rol, "defaults", "main.yml")
    return carga(ruta) if os.path.exists(ruta) else {}


def resuelve(valor, vars_):
    """Sustituye {{ var }} simples por su default; lo que no se pueda, se deja como variable."""
    def cambia(m):
        v = vars_.get(m.group(1))
        return str(v) if isinstance(v, (str, int, float)) else m.group(0)
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", cambia, valor)


def timers(rol):
    """[(unidad, cuándo)] de las unidades .timer del rol."""
    r = []
    vars_ = defaults(rol)
    base = os.path.join(ANSIBLE, "roles", rol)
    for f in sorted(glob.glob(os.path.join(base, "templates", "*.timer*")) + glob.glob(os.path.join(base, "files", "*.timer"))):
        texto = open(f, encoding="utf-8").read()
        nombre = os.path.basename(f).removesuffix(".j2")
        # plantillas con un bucle de timers (p. ej. server-backup-<modo>.timer) se ven tal cual
        cuando = []
        for clave in ("OnCalendar", "OnUnitActiveSec", "OnBootSec"):
            for m in re.finditer(rf"^{clave}=(.+)$", texto, re.M):
                v = resuelve(m.group(1).strip(), vars_)
                cuando.append({"OnCalendar": v, "OnUnitActiveSec": f"cada {v}", "OnBootSec": f"{v} tras arrancar"}[clave])
        if cuando:
            r.append((nombre, "; ".join(cuando)))
    return r


def descripcion(rol):
    ruta = os.path.join(ANSIBLE, "roles", rol, "meta", "main.yml")
    if not os.path.exists(ruta):
        return ""
    return ((carga(ruta).get("galaxy_info") or {}).get("description") or "").strip()


def main():
    grupos, playbooks = donde()
    roles = sorted(d for d in os.listdir(os.path.join(ANSIBLE, "roles")) if os.path.isdir(os.path.join(ANSIBLE, "roles", d)))
    por_sitio = defaultdict(list)
    for rol in roles:
        g = frozenset(x for x in grupos.get(rol, set()) if x in GRUPOS)
        por_sitio[g].append(rol)

    lineas = [
        "# Mapa (generado)",
        "",
        "!!! note \"Generado\"",
        "    Esta página la genera el CI desde el código de Ansible (`docs/generar_mapa.py`): qué rol va a qué",
        "    máquinas según los playbooks, qué hace según su `meta/main.yml` y qué corre solo según sus unidades",
        "    `.timer`. Si algo no cuadra, está mal en el código, no aquí.",
        "",
        "## Qué corre dónde",
        "",
        "```mermaid",
        "flowchart TB",
    ]
    orden = [frozenset({"homelab"}), frozenset({"homelab", "wings_remotos"}), frozenset({"wings_remotos"})]
    titulos = {frozenset({"homelab"}): "Solo en el servidor de casa", frozenset({"wings_remotos"}): "Solo en los nodos externos",
               frozenset({"homelab", "wings_remotos"}): "En el servidor y en los nodos"}
    for i, sitio in enumerate(orden):
        if not por_sitio.get(sitio):
            continue
        lineas.append(f'    subgraph s{i}["{titulos[sitio]}"]')
        lineas.append("        direction LR")
        for rol in por_sitio[sitio]:
            reloj = " ⏱" if timers(rol) else ""
            lineas.append(f'        {rol}["{rol}{reloj}"]')
        lineas.append("    end")
    for a, b in zip(orden, orden[1:]):
        if por_sitio.get(a) and por_sitio.get(b):
            lineas.append(f"    s{orden.index(a)} ~~~ s{orden.index(b)}")
    lineas += ["```", "", "⏱ = tiene tareas programadas (abajo).", ""]
    sueltos = por_sitio.get(frozenset(), [])
    if sueltos:
        lineas += [f"Roles que no aplica ningún playbook de este repo (se usan desde otros o por partes): {', '.join(f'`{r}`' for r in sueltos)}.", ""]

    lineas += ["## Roles", "", "| Rol | Dónde | Playbooks | Qué hace |", "|---|---|---|---|"]
    for rol in roles:
        sitio = ", ".join(GRUPOS.get(g, g) for g in sorted(grupos.get(rol, set()))) or "—"
        pbs = ", ".join(f"`{p}`" for p in sorted(playbooks.get(rol, set()))) or "—"
        lineas.append(f"| `{rol}` | {sitio} | {pbs} | {descripcion(rol).replace('|', '/')} |")

    lineas += ["", "## Tareas programadas", "", "| Rol | Unidad | Cuándo |", "|---|---|---|"]
    for rol in roles:
        for unidad, cuando in timers(rol):
            lineas.append(f"| `{rol}` | `{unidad}` | `{cuando}` |")
    lineas.append("")

    with open(SALIDA, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))
    print(f"{SALIDA}: {len(roles)} roles, {sum(len(timers(r)) for r in roles)} timers")


if __name__ == "__main__":
    main()
