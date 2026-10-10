import argparse
from pathlib import Path
import sys


def main():
    """명령줄 PNG 생성 또는 한국어 네이티브 GUI를 시작한다."""
    parser = argparse.ArgumentParser(description="말씀카드 — 교회용 카드뉴스 만들기")
    parser.add_argument("--text", type=Path, help="GUI 없이 UTF-8 글 파일로 카드 만들기")
    parser.add_argument("--output", type=Path, default=Path("output"), help="PNG 저장 폴더")
    parser.add_argument("--template", default="light", help="템플릿 폴더 이름")
    parser.add_argument("--ratio", choices=["4:5", "1:1"], default="4:5")
    args = parser.parse_args()
    if args.text:
        from .exporter import export_png
        from .layout import paginate, prepare_template, templates
        from .parser import parse
        from .renderer import render
        from .settings import Settings
        try:
            available = templates()
            if args.template not in available:
                raise ValueError("템플릿을 찾을 수 없습니다.")
            template = prepare_template(available[args.template], args.ratio)
            cards = paginate(parse(args.text.read_text(encoding="utf-8")), template)
            images = [render(card, template, Settings(), i, len(cards)) for i, card in enumerate(cards, 1)]
            if len(cards) > 10:
                print("주의: 10장을 넘습니다. 인스타에 올릴 때 작업을 나눠 주세요.", file=sys.stderr)
            destination = export_png(images, args.output, cards[0].text if cards else "말씀카드")
            print(f"{len(images)}장 저장 완료: {destination}")
            return
        except (OSError, ValueError) as exc:
            parser.exit(1, f"카드를 만들지 못했습니다: {exc}\n")
    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox
    from .ui.main_window import MainWindow
    application = QApplication(sys.argv[:1])
    application.setApplicationName("말씀카드")
    from .settings import ROOT
    application.setWindowIcon(QIcon(str(ROOT / "packaging/wordcard.ico")))
    application.setFont(QFont("맑은 고딕" if sys.platform == "win32" else "Sans Serif", 11))
    translator = QTranslator(application)
    translator.load(QLocale("ko_KR"), "qtbase", "_", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    application.installTranslator(translator)
    application.setStyleSheet("QPushButton { padding: 6px 12px; } QLineEdit, QComboBox { min-height: 30px; }")
    try:
        window = MainWindow()
    except Exception:
        QMessageBox.critical(None, "시작할 수 없습니다", "필수 글꼴·템플릿 또는 사용자 저장 폴더를 확인해 주세요. 프로그램을 다시 설치하면 해결될 수 있습니다.")
        return
    window.show()
    sys.exit(application.exec())


if __name__ == "__main__":
    main()
