"""Tests de ram-servidores con un Prometheus falso. Uso: python3 -m unittest discover -s tests"""

import http.server
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import threading
import unittest
import urllib.parse

FILES = os.path.join(os.path.dirname(__file__), "..", "files")


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_"), os.path.join(FILES, name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


ram = load("ram-servidores")

# valor por consulta (según la función de PromQL) para dos servidores, uno local y otro de un nodo
VALORES = {"quantile_over_time(0.5": 500, "quantile_over_time(0.95": 900, "max_over_time(contenedor_memoria_bytes": 1000,
           "count_over_time": 1440, "max_over_time(contenedor_memoria_limite_bytes": 2048}
CONSULTAS = []


class Falso(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)["query"][0]
        CONSULTAS.append(q)
        v = next(v for k, v in VALORES.items() if q.startswith(k))
        res = [{"metric": {"servidor": "abcd1234"}, "value": [0, str(v)]},
               {"metric": {"servidor": "ffff0000", "nodo": "n1"}, "value": [0, str(v * 2)]}]
        if q.startswith("quantile_over_time(0.5"):
            res.append({"metric": {}, "value": [0, "1"]})  # sin etiqueta servidor: se ignora
        cuerpo = json.dumps({"status": "success", "data": {"resultType": "vector", "result": res}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *a):
        pass


class RamTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.HTTPServer(("127.0.0.1", 0), Falso)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        ram.PROM = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        ram.HISTORICO = os.path.join(self.dir.name, "sub", "historico.jsonl")
        CONSULTAS.clear()

    def tearDown(self):
        self.dir.cleanup()

    def lineas(self):
        with open(ram.HISTORICO) as f:
            return [json.loads(l) for l in f]

    def test_escribe_un_dia(self):
        ram.sys.argv = ["ram-servidores", "2026-11-16"]
        ram.main()
        filas = self.lineas()
        self.assertEqual(len(filas), 2)
        a = next(f for f in filas if f["servidor"] == "abcd1234")
        self.assertEqual(a, {"fecha": "2026-11-16", "servidor": "abcd1234", "nodo": "local",
                             "p50": 500, "p95": 900, "max": 1000, "muestras": 1440, "limite": 2048})
        b = next(f for f in filas if f["servidor"] == "ffff0000")
        self.assertEqual((b["nodo"], b["max"]), ("n1", 2000))
        self.assertTrue(all("[1d]" in q for q in CONSULTAS))

    def test_no_repite_fecha(self):
        ram.sys.argv = ["ram-servidores", "2026-11-16"]
        ram.main()
        ram.main()
        self.assertEqual(len(self.lineas()), 2)
        ram.sys.argv = ["ram-servidores", "2026-11-17"]
        ram.main()
        self.assertEqual(len(self.lineas()), 4)


if __name__ == "__main__":
    unittest.main()
