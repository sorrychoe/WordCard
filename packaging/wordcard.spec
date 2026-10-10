# PyInstaller: run from the repository root on the target OS.
from pathlib import Path

root = Path(SPECPATH).parent
analysis = Analysis(
    [str(root / 'packaging/launcher.py')],
    pathex=[str(root / 'src')],
    datas=[(str(root / folder), folder) for folder in ('templates', 'fonts', 'docs')]
    + [(str(root / 'packaging/wordcard.ico'), 'packaging')],
    hiddenimports=['keyring.backends.Windows', 'keyring.backends.macOS', 'keyring.backends.SecretService'],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtQml', 'PySide6.QtQuick', 'tkinter'],
)
pyz = PYZ(analysis.pure)
# 단일 실행 파일: 설치 프로그램 없이 배포. UPX 압축은 백신 오탐을 늘려 끈다.
exe = EXE(pyz, analysis.scripts, analysis.binaries, analysis.datas, [], name='WordCard', console=False, upx=False,
          icon=str(root / 'packaging/wordcard.ico'))
