"""PySide6가 설치된 빌드 환경에서 네이티브 화면 흐름을 확인합니다."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'PySide6가 설치되지 않았습니다')
class GuiTests(unittest.TestCase):
    """사용 가능한 Qt 환경에서 입력부터 편집·작업 저장까지의 흐름을 검증한다."""
    def test_create_edit_save_and_load(self):
        """네이티브 화면에서 생성·수정·저장·비율 변경을 실제로 수행한다."""
        from PySide6.QtWidgets import QApplication
        from wordcard.ui.main_window import MainWindow
        from wordcard.project import load_project
        application = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with patch('wordcard.settings.data_dir', return_value=base), patch('wordcard.ui.main_window.data_dir', return_value=base):
                window = MainWindow()
                window.show()
                application.processEvents()
                window.source.setPlainText('화면 검증 제목\n날짜와 설교자\n\n첫 번째 본문입니다.\n\n마무리 문장입니다.')
                window.generate()
                self.assertEqual(len(window.images), 3)
                original = window.images[0].tobytes()
                window.select(1)
                window.card_text.setPlainText('수정한 본문입니다.')
                self.assertTrue(window.flush_edit())
                self.assertEqual(window.project.cards[1].text, '수정한 본문입니다.')
                self.assertEqual(window.images[0].tobytes(), original)
                window.project_path = base / 'gui.wordcard'
                self.assertTrue(window.save())
                self.assertEqual(load_project(window.project_path).cards[1].text, '수정한 본문입니다.')
                window.ratio.setCurrentText('1:1')
                self.assertTrue(all(image.size == (1080, 1080) for image in window.images))
                window.dirty = False
                window.close()
                application.processEvents()


if __name__ == '__main__':
    unittest.main()
