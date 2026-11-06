"""`lemmata hub config --overleaf on|off` (S06): sets overleaf_enabled in the hub config."""
import contextlib
import io
import json
import tempfile
import unittest
from argparse import Namespace

from lemmata.hub import cli
from lemmata.hub.config import Config, DataDir


class OverleafFlag(unittest.TestCase):
    def run_cfg(self, root, overleaf):
        a = Namespace(data=root, github_client_id=None, sync_interval=None, allow_host=None, overleaf=overleaf)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(cli.cmd_config(a), 0)
        return json.loads(buf.getvalue())

    def test_on_off(self):
        with tempfile.TemporaryDirectory() as root:
            d = DataDir(root).ensure()
            self.assertFalse(Config(d).load()["overleaf_enabled"])
            self.assertTrue(self.run_cfg(root, "on")["overleaf_enabled"])
            self.assertTrue(Config(d).load()["overleaf_enabled"])
            self.assertTrue(self.run_cfg(root, None)["overleaf_enabled"])   # no flag: unchanged
            self.assertFalse(self.run_cfg(root, "off")["overleaf_enabled"])

    def test_argparse(self):
        import argparse
        ap = argparse.ArgumentParser()
        cli.add_parser(ap.add_subparsers())
        self.assertEqual(ap.parse_args(["hub", "config", "--overleaf", "on"]).overleaf, "on")
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            ap.parse_args(["hub", "config", "--overleaf", "maybe"])


if __name__ == "__main__":
    unittest.main()
