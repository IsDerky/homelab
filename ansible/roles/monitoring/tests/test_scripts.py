"""Tests de ops-exporter, alert-dm y systemd-textfile. Uso: python3 -m unittest discover -s tests"""

import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest

FILES = os.path.join(os.path.dirname(__file__), "..", "files")


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_"), os.path.join(FILES, name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


exporter = load("ops-exporter")
alert_dm = load("alert-dm")
textfile = load("systemd-textfile")

SNAPSHOT = {
    "collected_at": "2026-11-06T19:22:03+00:00",
    "backups": {
        "sistema": {"Result": "success", "ExecMainStartTimestamp": 1000, "ExecMainExitTimestamp": 1028},
        "clientes": {"Result": "exit-code", "ExecMainStartTimestamp": 2000, "ExecMainExitTimestamp": 0},
    },
    "simulacro": {"at": "2026-11-01T09:00:53+00:00", "ok": True, "duration_s": 46},
    "certificates": {'web "rara"': {"expires_at": "2026-12-17T13:44:34+00:00"}},
    "smart": {"device": "/dev/sda", "passed": True, "temperature_c": 26, "wear_remaining_pct": 96},
    "services": {
        "nginx": {"ActiveState": "active"},
        "wings": {"ActiveState": "failed"},
        "backup.timer": {"ActiveState": "active"},
    },
    "fail2ban": {"sshd": {"banned": ["192.0.2.1", "192.0.2.2"], "total_banned": 7}},
    "deploys": {
        "bentonime_deployed_at": "2026-10-30T05:28:36+00:00",
        "last_deploy": {"phase": "health", "rollback": "ok"},
    },
    "wings": [
        {
            "uuid": "30c38de2-83c0-4953-9f91-d7aa7e8bcf98",
            "state": "running",
            "suspended": False,
            "mem_bytes": 1000,
            "mem_limit_bytes": 4000,
            "cpu_pct": 250.0,
            "disk_bytes": 9000,
            "uptime_ms": 61500,
        },
        {"uuid": "d4d90d68-0840-498e-9982-d45738e5e57a", "state": "offline", "mem_bytes": 0, "uptime_ms": 0},
    ],
    "wings_remote": {
        "n1.invalid": {"servers": [{"uuid": "6709f5ae-5df9", "state": "starting", "suspended": True}]},
        "n2.invalid": {"error": "no responde"},
    },
}


def samples(text):
    """{'nombre{labels}': valor} sin las líneas de HELP/TYPE."""
    out = {}
    for line in text.splitlines():
        if line and not line.startswith("#"):
            key, value = line.rsplit(" ", 1)
            out[key] = float(value)
    return out


class ExporterTest(unittest.TestCase):
    def setUp(self):
        self.text = exporter.collect(SNAPSHOT).render()
        self.s = samples(self.text)

    def test_backups(self):
        self.assertEqual(self.s['ops_backup_success{modo="sistema"}'], 1)
        self.assertEqual(self.s['ops_backup_success{modo="clientes"}'], 0)
        self.assertEqual(self.s['ops_backup_last_end_timestamp_seconds{modo="sistema"}'], 1028)
        # Sin fin (0) no se inventa una fecha
        self.assertNotIn('ops_backup_last_end_timestamp_seconds{modo="clientes"}', self.s)

    def test_simulacro_y_smart(self):
        self.assertEqual(self.s["ops_restore_test_success"], 1)
        self.assertEqual(self.s["ops_restore_test_duration_seconds"], 46)
        self.assertEqual(self.s['ops_smart_wear_remaining_ratio{device="/dev/sda"}'], 0.96)

    def test_servicios_sin_timers(self):
        self.assertEqual(self.s['ops_service_active{service="nginx"}'], 1)
        self.assertEqual(self.s['ops_service_active{service="wings"}'], 0)
        self.assertFalse(any("backup.timer" in k for k in self.s))

    def test_fail2ban_y_deploy(self):
        self.assertEqual(self.s['ops_fail2ban_banned{jail="sshd"}'], 2)
        self.assertEqual(self.s['ops_fail2ban_bans_since_start{jail="sshd"}'], 7)
        self.assertEqual(self.s["ops_deploy_last_ok"], 0)

    def test_servidores_de_juego(self):
        local = 'nodo="local",servidor="30c38de2"'
        self.assertEqual(self.s[f"ops_game_server_running{{{local}}}"], 1)
        self.assertEqual(self.s[f"ops_game_server_cpu_cores{{{local}}}"], 2.5)
        self.assertEqual(self.s[f"ops_game_server_uptime_seconds{{{local}}}"], 61.5)
        self.assertEqual(self.s[f"ops_game_server_memory_limit_bytes{{{local}}}"], 4000)
        self.assertEqual(self.s['ops_game_server_running{nodo="local",servidor="d4d90d68"}'], 0)
        self.assertEqual(self.s['ops_wings_node_servers{nodo="local"}'], 2)
        # Arrancando no es encendido
        self.assertEqual(self.s['ops_game_server_running{nodo="n1.invalid",servidor="6709f5ae"}'], 0)
        self.assertEqual(self.s['ops_game_server_suspended{nodo="n1.invalid",servidor="6709f5ae"}'], 1)
        self.assertNotIn('ops_game_server_memory_bytes{nodo="n1.invalid",servidor="6709f5ae"}', self.s)

    def test_nodos_de_wings(self):
        self.assertEqual(self.s['ops_wings_node_up{nodo="local"}'], 1)
        self.assertEqual(self.s['ops_wings_node_up{nodo="n1.invalid"}'], 1)
        self.assertEqual(self.s['ops_wings_node_up{nodo="n2.invalid"}'], 0)
        self.assertFalse(any('nodo="n2.invalid",servidor' in k for k in self.s))
        # Wings local caído o el recolector sin el fichero de nodos
        s = samples(exporter.collect({"wings": {"error": "no responde"}, "wings_remote": {"error": "x"}}).render())
        self.assertEqual(s['ops_wings_node_up{nodo="local"}'], 0)
        self.assertNotIn('ops_wings_node_up{nodo="error"}', s)

    def test_timestamps_sin_redondear(self):
        self.assertIn("ops_snapshot_timestamp_seconds 1793992923\n", self.text)
        self.assertIn('ops_backup_last_end_timestamp_seconds{modo="sistema"} 1028\n', self.text)

    def test_escapa_las_etiquetas(self):
        self.assertIn('ops_cert_expiry_timestamp_seconds{cert="web \\"rara\\""}', self.text)

    def test_help_y_type_una_vez_por_metrica(self):
        self.assertEqual(self.text.count("# TYPE ops_backup_success gauge"), 1)

    def test_snapshot_ilegible(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{roto")
        try:
            self.assertEqual(samples(exporter.render(f.name, "/no/existe")), {"ops_snapshot_up": 0})
        finally:
            os.unlink(f.name)
        self.assertEqual(samples(exporter.render("/no/existe.json", "/no/existe")), {"ops_snapshot_up": 0})

    def test_estado_de_los_backups(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "sistema-local.json"), "w") as f:
                json.dump({"ok": False, "at": 2000, "last_ok_at": 1000, "max_age_s": 46800, "duration_s": 3}, f)
            with open(os.path.join(d, "nas-drive.json"), "w") as f:
                json.dump({"ok": True, "at": 3000, "last_ok_at": 3000, "max_age_s": 108000}, f)
            with open(os.path.join(d, "roto-local.json"), "w") as f:
                f.write("{roto")
            s = samples(exporter.render("/no/existe.json", d))
        # El snapshot no se lee, pero el estado de los backups sale igual
        self.assertEqual(s["ops_snapshot_up"], 0)
        self.assertEqual(s['ops_backup_run_success{destino="local",modo="sistema"}'], 0)
        self.assertEqual(s['ops_backup_run_last_success_timestamp_seconds{destino="local",modo="sistema"}'], 1000)
        self.assertEqual(s['ops_backup_run_success{destino="drive",modo="nas"}'], 1)
        self.assertFalse(any("roto" in k for k in s))

    def test_snapshot_vacio(self):
        self.assertEqual(samples(exporter.collect({}).render()), {"ops_snapshot_up": 1})


class AlertDmTest(unittest.TestCase):
    def test_critica(self):
        args = alert_dm.message(
            {"labels": {"alertname": "SLO", "severity": "critical", "servicio": "app"},
             "annotations": {"summary": "Se está comiendo el presupuesto"}},
            "firing",
        )
        self.assertEqual(args[1:5], ["-t", "🚨 SLO", "-c", "red"])
        self.assertIn("Servicio=app", args)
        self.assertEqual(args[-1], "Se está comiendo el presupuesto")

    def test_resuelta(self):
        args = alert_dm.message({"labels": {"alertname": "Disco"}}, "resolved")
        self.assertEqual(args[2], "✅ Resuelto: Disco")
        self.assertEqual(args[4], "green")
        self.assertEqual(args[-1], "Disco")

    def test_notify_cuenta_los_enviados(self):
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(f.name, 0o755)
        old = alert_dm.DISCORD_DM
        alert_dm.DISCORD_DM = f.name
        try:
            payload = json.loads('{"status":"firing","alerts":[{"labels":{"alertname":"A"}},{"labels":{"alertname":"B"}}]}')
            self.assertEqual(alert_dm.notify(payload), 2)
        finally:
            alert_dm.DISCORD_DM = old
            os.unlink(f.name)


LIST_UNITS = """\
nginx.service                 loaded    active   running   A high performance web server
wings.service                 loaded    failed   failed    Pterodactyl Wings Daemon
certbot.timer                 loaded    active   waiting   Run certbot twice daily
code-server@derkyu.service    loaded    active   running   code-server
actions.runner.a.b.service    loaded    inactive dead      GitHub Actions Runner
"""


class SystemdTextfileTest(unittest.TestCase):
    def setUp(self):
        self.units = textfile.parse(LIST_UNITS)
        self.text = textfile.render(self.units, ["nginx.service", "wings.service", "code-server@derkyu.service",
                                                 "actions.runner.*", "certbot.timer"])
        self.s = samples(self.text)

    def test_un_valor_por_estado(self):
        self.assertEqual(self.s['node_systemd_unit_state{name="nginx.service",state="active"}'], 1)
        self.assertEqual(self.s['node_systemd_unit_state{name="nginx.service",state="failed"}'], 0)
        self.assertEqual(self.s['node_systemd_unit_state{name="wings.service",state="failed"}'], 1)
        self.assertEqual(self.s['node_systemd_unit_state{name="actions.runner.a.b.service",state="inactive"}'], 1)
        self.assertEqual(len(self.s), 5 * len(textfile.STATES))

    def test_solo_las_de_la_lista(self):
        s = samples(textfile.render(self.units, ["nginx.service"]))
        self.assertEqual({k.split('"')[1] for k in s}, {"nginx.service"})

    def test_regex_completa(self):
        # "nginx" no coge nginx.service
        self.assertNotIn("node_systemd_unit_state{", textfile.render(self.units, ["nginx"]))

    def test_ultima_ejecucion_de_los_timers(self):
        show = ("LastTriggerUSec=Tue 2026-11-10 10:48:00 UTC\nId=certbot.timer\n\n"
                "LastTriggerUSec=\nId=nunca.timer\n")
        triggers = textfile.parse_triggers(show)
        # Sin disparar desde el arranque: sin serie, mejor que un 0 que parezca muy viejo
        self.assertEqual(triggers, {"certbot.timer": 1794307680})
        s = samples(textfile.render(self.units, ["certbot.timer"], triggers))
        self.assertEqual(s['node_systemd_timer_last_trigger_seconds{name="certbot.timer"}'], 1794307680)

    def test_escritura_atomica(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "systemd.prom")
            textfile.write(path, self.text)
            self.assertEqual(os.listdir(d), ["systemd.prom"])
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o644)


if __name__ == "__main__":
    unittest.main()
