"""Server route and guard tests (web-eng). Runs on the fixture engine, no network, stdlib unittest.

    PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p "test_server.py"
"""
import http.client
import json
import re
import threading
import unittest

from lemmata.fixture_engine import FixtureEngine
from lemmata.server import bind

BANNED = re.compile(r"\b(wrong|fake|fabricated|mistake|error by|cheat)\b", re.I)


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = bind(FixtureEngine(""), port=18765)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def req(self, method, path, body=None, headers=None, raw=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Host": "127.0.0.1:%d" % self.port}
        h.update(headers or {})
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        if data is not None:
            h.setdefault("Content-Type", "application/json")
        c.request(method, path, body=data, headers=h)
        r = c.getresponse()
        out = r.read()
        c.close()
        return r.status, r.getheader("Content-Type"), out

    def j(self, method, path, body=None, **kw):
        s, _, out = self.req(method, path, body, **kw)
        return s, json.loads(out)

    def test_health_and_static(self):
        self.assertEqual(self.j("GET", "/api/health"), (200, {"ok": True, "version": "0.1.0"}))
        s, ct, out = self.req("GET", "/")
        self.assertEqual(s, 200)
        self.assertIn("text/html", ct)
        self.assertEqual(self.req("GET", "/app.js")[0], 200)
        self.assertEqual(self.req("GET", "/vendor/cytoscape.min.js")[0], 200)

    def test_static_is_confined_to_web(self):
        for p in ("/../server.py", "/%2e%2e/server.py", "/..%2fserver.py", "/vendor/../../server.py"):
            self.assertEqual(self.req("GET", p)[0], 404, p)

    def test_host_and_origin_guards(self):
        self.assertEqual(self.j("GET", "/api/health", headers={"Host": "evil.example"})[0], 403)
        s, body = self.j("POST", "/api/triage", {"target_type": "node", "target_id": "thesis", "state": "reviewed"}, headers={"Origin": "http://evil.example"})
        self.assertEqual(s, 403)
        self.assertEqual(body["error"]["code"], "forbidden")

    def test_post_rules(self):
        self.assertEqual(self.req("POST", "/api/triage", raw=b"{}", headers={"Content-Type": "text/plain"})[0], 400)
        self.assertEqual(self.req("POST", "/api/triage", raw=b"not json")[0], 400)
        self.assertEqual(self.req("POST", "/api/triage", raw=b"[]")[0], 400)
        s, body = self.j("POST", "/api/triage", raw=b"{" + b" " * 70000 + b"}")
        self.assertEqual((s, body["error"]["code"]), (413, "too_large"))

    def test_get_routes_and_shapes(self):
        for path, key in (("/api/project", "counts"), ("/api/graph", "nodes"), ("/api/events", "events"), ("/api/findings", "findings"),
                          ("/api/alarms", "groups"), ("/api/checkpoints", "checkpoints"), ("/api/triage", "entries")):
            s, b = self.j("GET", path)
            self.assertEqual(s, 200, path)
            self.assertIn(key, b)
        self.assertEqual(self.j("GET", "/api/nope")[0], 404)
        self.assertEqual(self.j("GET", "/api/analyze?group=x")[0], 400)

    def test_triage_and_links_and_ask(self):
        s, b = self.j("POST", "/api/triage", {"target_type": "node", "target_id": "tex:tab:main", "state": "needs_fixing", "note": "rerun"})
        self.assertEqual(s, 200)
        self.assertEqual(b["entry"]["effective_state"], "needs_fixing")
        self.assertEqual(self.j("POST", "/api/triage", {"target_type": "node", "target_id": "nope", "state": "reviewed"})[0], 404)
        self.assertEqual(self.j("POST", "/api/triage", {"target_type": "node", "target_id": "thesis", "state": "bogus"})[0], 400)
        s, b = self.j("POST", "/api/links/decide", {"edge_id": "tex:app:hparams|value_match|file:code/configs/default.yaml", "decision": "approved"})
        self.assertEqual(s, 200)
        self.assertEqual(b["edge"]["status"], "approved")
        s, b = self.j("POST", "/api/ask", {})
        self.assertEqual((s, b["error"]["code"]), (501, "not_implemented"))
        self.assertEqual(self.j("GET", "/api/ask")[0], 405)

    def test_checkpoint_clears_alarms(self):
        s, b = self.j("POST", "/api/checkpoints", {"note": "t"})
        self.assertEqual(s, 201)
        self.assertEqual(b["alarms"]["groups"], [])

    def test_export_is_one_offline_file(self):
        s, ct, out = self.req("GET", "/api/export")
        self.assertEqual(s, 200)
        html = out.decode()
        self.assertIn('id="lemmata-snapshot"', html)
        self.assertNotRegex(html, r'<script[^>]+src=|<link[^>]+href="(?!data:)')
        m = re.search(r'<script type="application/json" id="lemmata-snapshot">(.*?)</script>', html, re.S)
        snap = json.loads(m.group(1).replace("<\\/", "</"))
        for k in ("project", "graph", "events", "findings", "alarms", "checkpoints", "triage", "exported_at"):
            self.assertIn(k, snap)

    def test_file_route_stays_inside_repo(self):
        self.assertEqual(self.j("GET", "/api/file?repo=paper&path=main.tex&start=1&end=3")[0], 200)
        self.assertEqual(self.j("GET", "/api/file?repo=paper&path=../code/train.py")[0], 404)
        self.assertEqual(self.j("GET", "/api/file?repo=paper&path=/etc/passwd")[0], 400)

    def test_ui_wording(self):
        from pathlib import Path
        web = Path(__file__).resolve().parents[1] / "src" / "lemmata" / "web"
        for f in ("app.js", "index.html", "app.css"):
            self.assertIsNone(BANNED.search((web / f).read_text(encoding="utf-8")), f)


if __name__ == "__main__":
    unittest.main()
