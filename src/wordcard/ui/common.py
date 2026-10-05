from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QMessageBox, QPushButton


def button(text, action, layout):
    """표준 높이의 버튼을 배치하고 클릭 시 실행할 함수를 연결한다."""
    widget = QPushButton(text)
    widget.setMinimumHeight(36)
    widget.clicked.connect(action)
    layout.addWidget(widget)
    return widget


def pixmap(image):
    """Pillow 이미지의 픽셀을 복사해 원본 수명에 독립적인 Qt 이미지를 반환한다."""
    rgba = image.convert("RGBA")
    return QPixmap.fromImage(QImage(rgba.tobytes(), rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888).copy())


def error(parent, exc):
    """알려진 오류는 해결 안내와 함께 표시하고 내부 예외의 민감한 내용은 숨긴다."""
    message = str(exc) if isinstance(exc, ValueError) else "처리하지 못했습니다. 파일 경로·사용 권한·이미지 형식을 확인해 주세요."
    QMessageBox.warning(parent, "확인이 필요합니다", message)


def ask(parent, text):
    """사용자에게 기본값이 아니오인 확인 창을 표시하고 동의 여부를 반환한다."""
    return QMessageBox.question(parent, "확인", text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes


class Worker(QThread):
    """GUI를 멈추지 않고 작업을 실행하며 진행·성공·실패를 신호로 전달한다."""
    succeeded = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, task, parent=None):
        """실행할 작업을 보관하고 Qt 부모 객체에 스레드 수명을 연결한다."""
        super().__init__(parent)
        self.task = task

    def run(self):
        """백그라운드 작업을 실행하고 내부 예외를 노출하지 않는 결과 신호를 보낸다."""
        try:
            self.succeeded.emit(self.task(self.progress.emit))
        except ValueError as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit("처리하지 못했습니다. 파일 접근 권한, 인터넷 연결 및 계정 설정을 확인해 주세요.")
