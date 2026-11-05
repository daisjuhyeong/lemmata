# PyInstaller spec: one-file console sidecar. Build with packaging/build_sidecar.sh
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

HERE = Path(SPECPATH).resolve()
SRC = HERE.parent / "src"

hidden = collect_submodules("lemmata")  # engine, samples and watch are imported lazily
# the web UI is read from disk (server.WEB = <package>/web); the sample generator is a module, collected above
datas = [(str(SRC / "lemmata" / "web"), "lemmata/web")]

a = Analysis([str(HERE / "lemmata_server.py")], pathex=[str(SRC)], datas=datas, hiddenimports=hidden,
             excludes=["tkinter", "unittest", "pydoc", "test"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="lemmata-server", console=True, debug=False,
          strip=False, upx=False, runtime_tmpdir=None)
