#!/usr/bin/env python3
"""Pone los SHA-256 (y los asset id de restic) de las versiones de los defaults.

restic, rclone, Wings y Lynis.

Renovate sube la versión pero no sabe de sumas. Esto las saca del digest que da
la API de GitHub para cada asset (si no lo hay, descarga y calcula) y del
SHA256SUMS de rclone. Sin cambios de versión no toca nada.
"""
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROLES = Path(__file__).resolve().parents[2] / "ansible" / "roles"
ARCHS = ("amd64", "arm64")


def get(url, api=False):
    headers = {"User-Agent": "homelab-sumas"}
    token = os.environ.get("GH_TOKEN")
    if api and token:
        headers["Authorization"] = f"Bearer {token}"
        headers["Accept"] = "application/vnd.github+json"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as r:
        return r.read()


def asset(repo, tag, nombre):
    rel = json.loads(get(f"https://api.github.com/repos/{repo}/releases/tags/{tag}", api=True))
    for a in rel["assets"]:
        if a["name"] == nombre:
            digest = a.get("digest") or ""
            if digest.startswith("sha256:"):
                return a["id"], digest.removeprefix("sha256:")
            return a["id"], hashlib.sha256(get(a["browser_download_url"])).hexdigest()
    sys.exit(f"{repo} {tag}: no hay {nombre}")


def version(texto, var):
    m = re.search(rf"^{var}: (\S+)$", texto, re.M)
    if not m:
        sys.exit(f"no encuentro {var}")
    return m.group(1)


def poner(texto, var, arch, valor):
    # La clave de la arquitectura dentro del bloque "var:\n  amd64: ..."
    patron = rf"(^{var}:\n(?:  .*\n)*?  {arch}: )\S+"
    nuevo, n = re.subn(patron, lambda m: m.group(1) + str(valor), texto, count=1, flags=re.M)
    if n != 1:
        sys.exit(f"no encuentro {var}.{arch}")
    return nuevo


def restic(texto):
    v = version(texto, "backup_restic_version")
    for arch in ARCHS:
        id_, suma = asset("restic/restic", f"v{v}", f"restic_{v}_linux_{arch}.bz2")
        texto = poner(texto, "backup_restic_sha256", arch, suma)
        texto = poner(texto, "backup_restic_asset_id", arch, id_)
    return texto


def rclone(texto):
    v = version(texto, "backup_rclone_version")
    sumas = get(f"https://downloads.rclone.org/v{v}/SHA256SUMS").decode()
    for arch in ARCHS:
        m = re.search(rf"^([0-9a-f]{{64}})  rclone-v{re.escape(v)}-linux-{arch}\.zip$", sumas, re.M)
        if not m:
            sys.exit(f"rclone {v}: no hay suma para {arch}")
        texto = poner(texto, "backup_rclone_sha256", arch, m.group(1))
    return texto


def wings(texto):
    v = version(texto, "pterodactyl_wings_version")
    for arch in ARCHS:
        _, suma = asset("pterodactyl/wings", f"v{v}", f"wings_linux_{arch}")
        texto = poner(texto, "pterodactyl_wings_sha256", arch, suma)
    return texto


def lynis(texto):
    # Sin assets: el tarball del tag (GitHub mantiene estable su suma)
    v = version(texto, "lynis_version")
    suma = hashlib.sha256(get(f"https://github.com/CISOfy/lynis/archive/refs/tags/{v}.tar.gz")).hexdigest()
    return re.sub(r"(?m)^lynis_sha256: \S+$", f"lynis_sha256: {suma}", texto)


def main():
    for fichero, pasos in (
        (ROLES / "backup" / "defaults" / "main.yml", (restic, rclone)),
        (ROLES / "pterodactyl" / "defaults" / "main.yml", (wings,)),
        (ROLES / "lynis" / "defaults" / "main.yml", (lynis,)),
    ):
        antes = fichero.read_text()
        despues = antes
        for paso in pasos:
            despues = paso(despues)
        if despues != antes:
            fichero.write_text(despues)
            print(f"actualizado {fichero.relative_to(ROLES.parent.parent)}")


if __name__ == "__main__":
    main()
