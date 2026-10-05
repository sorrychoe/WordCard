# PyInstaller: run from the repository root on the target OS.
from pathlib import Path

root = Path(SPECPATH).parent
analysis = Analysis(
    [str(root / 'packaging/launcher.py')],
    pathex=[str(root / 'src')],
    datas=[(str(root / folder), folder) for folder in ('templates', 'fonts', 'docs')],
    hiddenimports=['keyring.backends.Windows', 'keyring.backends.macOS', 'keyring.backends.SecretService'],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtQml', 'PySide6.QtQuick', 'tkinter'],
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name='WordCard', console=False)
collection = COLLECT(exe, analysis.binaries, analysis.datas, name='WordCard')
