"""PyInstaller entry point: the sidecar binary is the `lemmata` CLI."""
import multiprocessing
import sys

from lemmata.cli import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
