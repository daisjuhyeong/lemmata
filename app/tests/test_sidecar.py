"""Sidecar contract tests (S03): ready-json, port 0, error JSON, parent-pid, watch, PyInstaller binary.

    PYTHONPATH=app/src python3 -m unittest discover -s app/tests -p "test_sidecar.py"
The binary test is skipped when app/packaging/dist/lemmata-server has not been built (app/packaging/build_sidecar.sh).
"""
import http.client
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ENV = dict(os.environ, PYTHONPATH=str(APP / "src"))
BINARY = APP / "packaging" / "dist" / "lemmata-server"


def spawn(cmd, **kw):
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=ENV, **kw)


def cli(*args):
    return [sys.executable, "-m", "lemmata"] + list(args)


def ready_line(p, timeout=60):
    """First stdout line, parsed; fails the test if nothing arrives."""
    import threading
    box = []
    t = threading.Thread(target=lambda: box.append(p.stdout.readline()), daemon=True)
    t.start()
    t.join(timeout)
    if not box or not box[0]:
        p.kill()
        raise AssertionError("no output line; stderr: %s" % p.stderr.read())
    return box[0], json.loads(box[0])


def get(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("GET", path, headers={"Host": "127.0.0.1:%d" % port})
    r = c.getresponse()
    body = r.read()
    c.close()
    return r.status, json.loads(body)


def stop(p):
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(5)
        except subprocess.TimeoutExpired:
            p.kill()
    for f in (p.stdout, p.stderr):
        f.close()


class SidecarTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.procs = []
        self.addCleanup(lambda: [stop(p) for p in self.procs])

    def start(self, *args, **kw):
        p = spawn(cli(*args), **kw)
        self.procs.append(p)
        return p

    def test_ready_json_and_port_zero(self):
        p = self.start("demo", "--dir", self.tmp.name + "/s", "--port", "0", "--no-open", "--ready-json")
        raw, ev = ready_line(p)
        self.assertTrue(raw.endswith("\n"))
        self.assertEqual(list(ev), ["event", "url", "port", "project", "root"])
        self.assertEqual(ev["event"], "ready")
        self.assertGreater(ev["port"], 0)
        self.assertNotEqual(ev["port"], 8765)
        self.assertEqual(ev["url"], "http://127.0.0.1:%d/" % ev["port"])
        self.assertEqual(Path(ev["root"]), Path(self.tmp.name, "s").resolve())
        self.assertTrue(ev["project"])
        # Host check uses the real bound port
        self.assertEqual(get(ev["port"], "/api/health")[0], 200)
        c = http.client.HTTPConnection("127.0.0.1", ev["port"], timeout=10)
        c.request("GET", "/api/health", headers={"Host": "127.0.0.1:8765"})
        self.assertEqual(c.getresponse().status, 403)
        # SIGTERM -> clean exit
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(10), 0)

    def test_error_missing_folder(self):
        p = self.start("open", self.tmp.name + "/nope", "--port", "0", "--no-open", "--ready-json")
        out = p.stdout.read()
        self.assertNotEqual(p.wait(10), 0)
        lines = out.splitlines()
        self.assertEqual(len(lines), 1)
        ev = json.loads(lines[0])
        self.assertEqual((ev["event"], ev["code"]), ("error", "not_found"))
        self.assertTrue(ev["message"])

    def test_error_no_project(self):
        p = self.start("open", self.tmp.name, "--port", "0", "--no-open", "--ready-json")
        ev = json.loads(p.stdout.read().splitlines()[0])
        self.assertEqual(ev["code"], "no_project")
        self.assertNotEqual(p.wait(10), 0)

    def test_parent_pid_exit(self):
        parent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.addCleanup(lambda: parent.poll() is None and parent.kill())
        p = self.start("demo", "--dir", self.tmp.name + "/s", "--port", "0", "--no-open", "--ready-json", "--parent-pid", str(parent.pid))
        ready_line(p)
        self.assertIsNone(p.poll())
        parent.kill()
        parent.wait()
        t0 = time.time()
        p.wait(timeout=5)
        self.assertLess(time.time() - t0, 2.5)

    def test_watch_rescans_after_edit(self):
        root = self.tmp.name + "/s"
        p = self.start("demo", "--dir", root, "--port", "0", "--no-open", "--ready-json", "--watch")
        _, ev = ready_line(p)
        first = get(ev["port"], "/api/project")[1]["scanned_at"]
        time.sleep(1.1)  # scanned_at has one-second resolution
        f = Path(root, "code", "train.py")
        f.write_text(f.read_text() + "\n# edited by test\n")
        deadline = time.time() + 12
        second = first
        while time.time() < deadline and second == first:
            time.sleep(0.5)
            second = get(ev["port"], "/api/project")[1]["scanned_at"]
        self.assertNotEqual(first, second)
        self.assertEqual(get(ev["port"], "/api/health")[0], 200)

    def test_watch_survives_failing_rescan(self):
        sys.path.insert(0, str(APP / "src"))
        from lemmata.samples.make_sample import build
        from lemmata.engine.api import Engine
        from lemmata.server import App
        from lemmata.watch import Watcher
        root = Path(self.tmp.name, "w")
        build(root)
        eng = Engine(root)
        eng.scan()
        w = Watcher(App(eng), min_gap=0)
        good = eng.project()["scanned_at"]
        eng.scan = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        f = root / "code" / "train.py"
        f.write_text(f.read_text() + "\n# x\n")
        self.assertTrue(w.tick())  # attempted, swallowed
        self.assertEqual(w.rescans, 0)
        self.assertEqual(eng.project()["scanned_at"], good)
        self.assertFalse(w.tick())  # unchanged since: no retry storm

    @unittest.skipUnless(BINARY.exists(), "build the sidecar first: app/packaging/build_sidecar.sh")
    def test_pyinstaller_binary(self):
        t0 = time.time()
        p = subprocess.Popen([str(BINARY), "demo", "--dir", self.tmp.name + "/x", "--port", "0", "--no-open", "--ready-json"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.procs.append(p)
        _, ev = ready_line(p, timeout=90)
        self.assertEqual(ev["event"], "ready")
        self.assertEqual(get(ev["port"], "/api/health")[1]["ok"], True)
        self.assertGreater(len(get(ev["port"], "/api/graph")[1]["nodes"]), 5)
        c = http.client.HTTPConnection("127.0.0.1", ev["port"], timeout=10)
        c.request("GET", "/", headers={"Host": "127.0.0.1:%d" % ev["port"]})
        self.assertEqual(c.getresponse().status, 200)
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(10), 0)


if __name__ == "__main__":
    unittest.main()
