"""Tests de cambios-recoger y de los cambios en los avisos de alert-dm. Uso: python3 -m unittest discover -s tests"""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

FILES = os.path.join(os.path.dirname(__file__), "..", "files")


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_") + "_c", os.path.join(FILES, name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


cambios = load("cambios-recoger")
alert_dm = load("alert-dm")

BLOQUE_AUTO = """Start-Date: 2026-11-17  06:12:01
Upgrade: libssl3t64:amd64 (3.0.13-0ubuntu3.5, 3.0.13-0ubuntu3.6), openssl:amd64 (3.0.13-0ubuntu3.5, 3.0.13-0ubuntu3.6)
End-Date: 2026-11-17  06:12:44
"""
BLOQUE_MANO = """Start-Date: 2026-11-17  10:00:00
Commandline: apt install htop
Requested-By: derkyu (1000)
Install: htop:amd64 (3.3.0-4build1)
End-Date: 2026-11-17  10:00:05
"""
BLOQUE_A_MEDIAS = """Start-Date: 2026-11-17  11:00:00
Commandline: apt-get -y upgrade
Upgrade: curl:amd64 (8.5.0-2ubuntu10.6, 8.5.0-2ubuntu10.7)
"""


class CambiosTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        cambios.DIR = self.d
        cambios.EVENTOS = os.path.join(self.d, "eventos.jsonl")
        cambios.ESTADO = os.path.join(self.d, "estado.json")
        cambios.APT = os.path.join(self.d, "history.log")
        cambios.CONFIG_GIT = os.path.join(self.d, "no-hay")
        cambios.GRAFANA = ""
        with open(cambios.APT, "w") as f:
            f.write("Start-Date: 2026-11-01  00:00:00\nUpgrade: viejo:amd64 (1, 2)\nEnd-Date: 2026-11-01  00:00:01\n\n")
        os.environ.update({"CAMBIOS_BOOT_ID": "boot-1", "CAMBIOS_BTIME": "1794900000"})
        self.journal = os.path.join(self.d, "journal.json")
        open(self.journal, "w").close()
        os.environ["CAMBIOS_JOURNAL"] = self.journal

    def tearDown(self):
        for k in ("CAMBIOS_BOOT_ID", "CAMBIOS_BTIME", "CAMBIOS_JOURNAL"):
            os.environ.pop(k, None)

    def test_paquetes(self):
        estado = {}
        self.assertEqual(cambios.paquetes(estado), [], "la primera vez no se cuenta lo de antes")
        with open(cambios.APT, "a") as f:
            f.write(BLOQUE_AUTO + "\n" + BLOQUE_MANO + "\n" + BLOQUE_A_MEDIAS)
        ev = cambios.paquetes(estado)
        self.assertEqual([e["texto"] for e in ev], [
            "Paquetes (automáticas): 2 actualizados: libssl3t64, openssl",
            "Paquetes (a mano): 1 instalados: htop",
        ])
        self.assertEqual(ev[0]["t"], int(datetime(2026, 11, 17, 6, 12, 44).timestamp()))
        # el bloque a medias sale cuando termina
        with open(cambios.APT, "a") as f:
            f.write("End-Date: 2026-11-17  11:00:09\n")
        ev = cambios.paquetes(estado)
        self.assertEqual([e["texto"] for e in ev], ["Paquetes (root/Ansible): 1 actualizados: curl"])
        self.assertEqual(cambios.paquetes(estado), [])

    def test_reinicio(self):
        estado = {}
        self.assertEqual(cambios.reinicio(estado), [])
        self.assertEqual(cambios.reinicio(estado), [])
        os.environ["CAMBIOS_BOOT_ID"] = "boot-2"
        self.assertEqual(cambios.reinicio(estado), [{"t": 1794900000, "tipo": "reinicio", "texto": "Reinicio de la máquina"}])

    def test_journal_ansible_y_despliegue(self):
        viejo = (int(time.time()) - 3600) * 1_000_000
        # como lo deja de verdad Ansible: identificador python3.12 y el módulo al principio del mensaje
        py = "python3.12"
        lineas = [
            {"__CURSOR": "c0", "__REALTIME_TIMESTAMP": str(viejo - 5_000_000), "SYSLOG_IDENTIFIER": py, "MESSAGE": "ansible-ansible.legacy.setup Invoked with gather_subset=['all']"},
            {"__CURSOR": "c1", "__REALTIME_TIMESTAMP": str(viejo), "SYSLOG_IDENTIFIER": py, "MESSAGE": "ansible-ansible.builtin.copy Invoked with dest=/x mode=0644"},
            {"__CURSOR": "c2", "__REALTIME_TIMESTAMP": str(viejo + 30_000_000), "SYSLOG_IDENTIFIER": py, "MESSAGE": "ansible-ansible.legacy.copy Invoked with dest=/y"},
            {"__CURSOR": "c3", "__REALTIME_TIMESTAMP": str(viejo + 90_000_000), "SYSLOG_IDENTIFIER": py, "MESSAGE": "ansible-ansible.builtin.systemd_service Invoked with name=x"},
            {"__CURSOR": "c4", "__REALTIME_TIMESTAMP": str(viejo + 600_000_000), "SYSLOG_IDENTIFIER": "deploy-repo", "MESSAGE": "Desplegado oficina abc1234"},
            {"__CURSOR": "c5", "__REALTIME_TIMESTAMP": str(viejo + 700_000_000), "SYSLOG_IDENTIFIER": "sshd", "MESSAGE": "nada de ansible-x Invoked with"},
            # la deriva de cada noche (--check desde deriva.service): no cuenta
            {"__CURSOR": "c5b", "__REALTIME_TIMESTAMP": str(viejo + 800_000_000), "SYSLOG_IDENTIFIER": py, "_SYSTEMD_UNIT": "deriva.service", "MESSAGE": "ansible-ansible.builtin.copy Invoked with dest=/z"},
            # una pasada que sigue en marcha (reciente): no sale todavía
            {"__CURSOR": "c6", "__REALTIME_TIMESTAMP": str(int(time.time()) * 1_000_000), "SYSLOG_IDENTIFIER": py, "MESSAGE": "ansible-ansible.builtin.apt Invoked with name=['x']"},
        ]
        with open(self.journal, "w") as f:
            f.write("\n".join(json.dumps(l) for l in lineas))
        estado = {}
        ev = cambios.journal(estado)
        self.assertEqual([e["tipo"] for e in ev], ["ansible", "despliegue"])
        self.assertEqual(ev[0]["texto"], "Ansible: 3 tareas en ~2 min (copy ×2, systemd_service ×1)")
        self.assertEqual(ev[1]["texto"], "Desplegado oficina abc1234")
        self.assertEqual(estado["cursor"], "c6")
        self.assertEqual(estado["ansible"]["n"], 1, "la pasada en marcha queda pendiente")

    def test_config_git(self):
        repo = os.path.join(self.d, "config")
        g = lambda *a: subprocess.run(["git", "-C", repo, *a], capture_output=True, check=True, text=True)
        os.makedirs(os.path.join(repo, "ctrlpanel"))
        subprocess.run(["git", "init", "-q", repo], check=True)
        g("config", "user.email", "t@t"); g("config", "user.name", "t")
        open(os.path.join(repo, "ctrlpanel", "productos.json"), "w").write("[]")
        g("add", "-A"); g("commit", "-qm", "uno")
        cambios.CONFIG_GIT = repo
        estado = {}
        self.assertEqual(cambios.config(estado), [], "la primera vez solo apunta dónde está")
        open(os.path.join(repo, "ctrlpanel", "productos.json"), "w").write("[1]")
        open(os.path.join(repo, "ctrlpanel", "ajustes.json"), "w").write("{}")
        g("add", "-A"); g("commit", "-qm", "dos")
        ev = cambios.config(estado)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["tipo"], "config")
        self.assertIn("2 ficheros", ev[0]["texto"])
        self.assertIn("productos", ev[0]["texto"])

    def test_main_con_grafana(self):
        recibidas = []

        class G(BaseHTTPRequestHandler):
            def do_POST(self):
                recibidas.append((self.path, self.headers.get("Authorization"), json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
                self.send_response(200); self.end_headers(); self.wfile.write(b"{}")

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), G)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            cambios.main()   # primera pasada: solo apunta posiciones
            os.environ["CAMBIOS_BOOT_ID"] = "boot-2"
            # Grafana caído: queda pendiente
            cambios.GRAFANA = "http://127.0.0.1:1"
            cambios.main()
            self.assertEqual(len(json.load(open(cambios.ESTADO))["pendientes"]), 1)
            # vuelve: se manda el pendiente con usuario y contraseña
            cambios.GRAFANA = f"http://127.0.0.1:{srv.server_port}"
            os.environ["GRAFANA_PASS"] = "x"
            cambios.main()
            self.assertEqual(len(recibidas), 1)
            path, auth, cuerpo = recibidas[0]
            self.assertEqual(path, "/api/annotations")
            self.assertTrue(auth.startswith("Basic "))
            self.assertEqual(cuerpo["tags"], ["cambio", "reinicio"])
            self.assertEqual(cuerpo["time"], 1794900000 * 1000)
            self.assertEqual(json.load(open(cambios.ESTADO))["pendientes"], [])
            eventos = [json.loads(l) for l in open(cambios.EVENTOS)]
            self.assertEqual([e["tipo"] for e in eventos], ["reinicio"])
            self.assertEqual(oct(os.stat(cambios.EVENTOS).st_mode & 0o777), "0o644")
        finally:
            os.environ.pop("GRAFANA_PASS", None)
            srv.shutdown()


class AlertDmCambiosTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.old = alert_dm.CAMBIOS
        alert_dm.CAMBIOS = os.path.join(self.d, "eventos.jsonl")
        base = int(datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc).timestamp())
        with open(alert_dm.CAMBIOS, "w") as f:
            for dt, texto in ((-3 * 3600, "muy viejo"), (-3000, "Paquetes (automáticas): 1 actualizados: curl"),
                              (-600, "Desplegado oficina abc1234"), (+3600, "después")):
                f.write(json.dumps({"t": base + dt, "tipo": "x", "texto": texto}) + "\n")

    def tearDown(self):
        alert_dm.CAMBIOS = self.old

    def test_cambios_en_el_aviso(self):
        args = alert_dm.message({"labels": {"alertname": "Disco"}, "startsAt": "2026-11-17T10:00:00.123456789Z",
                                 "annotations": {"summary": "s"}}, "firing")
        campo = next(a for a in args if a.startswith("Cambios (2 h)="))
        lineas = campo.split("=", 1)[1].split("\n")
        self.assertEqual(len(lineas), 2, "solo los de las 2 h antes")
        self.assertTrue(lineas[0].endswith("Desplegado oficina abc1234"), "el más reciente primero")
        self.assertEqual(args[-1], "s")

    def test_sin_fraccion_de_segundo(self):
        args = alert_dm.message({"labels": {"alertname": "Disco"}, "startsAt": "2026-11-17T10:00:00Z"}, "firing")
        self.assertTrue(any(a.startswith("Cambios (2 h)=") for a in args))

    def test_resuelta_sin_cambios(self):
        args = alert_dm.message({"labels": {"alertname": "Disco"}, "startsAt": "2026-11-17T10:00:00Z"}, "resolved")
        self.assertFalse(any(a.startswith("Cambios") for a in args))

    def test_sin_fichero(self):
        alert_dm.CAMBIOS = os.path.join(self.d, "no-existe")
        args = alert_dm.message({"labels": {"alertname": "Disco"}, "startsAt": "2026-11-17T10:00:00Z"}, "firing")
        self.assertFalse(any(a.startswith("Cambios") for a in args))
