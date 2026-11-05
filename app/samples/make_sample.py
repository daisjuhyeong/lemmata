#!/usr/bin/env python3
"""Thin wrapper: the sample generator lives in the package (src/lemmata/samples/make_sample.py) so the
PyInstaller bundle can build the sample. Usage: python3 make_sample.py <target_dir>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lemmata.samples.make_sample import MARKER, build, main  # noqa: E402,F401

if __name__ == "__main__":
    sys.exit(main(sys.argv))
