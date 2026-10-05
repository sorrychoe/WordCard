from copy import deepcopy
from threading import Event
from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QVBoxLayout
from ..exporter import export_png
from ..project import save_project
from ..settings import atomic_json, data_dir, secret
from ..uploader import caption_counts, publish, days_remaining
from .common import Worker, ask, button, error, pixmap


class UploadDialog(QDialog):
    """게시 확인, 캡션 검증, 로컬 백업과 비동기 업로드 진행을 관리하는 창."""
    def __init__(self, parent):
        """현재 카드와 캡션을 표시하고 취소 이벤트와 게시 결과 상태를 준비한다."""
        super().__init__(parent)
        self.setWindowTitle("인스타그램에 올리기")
        self.resize(700, 620)
        self.worker = None
        self.cancel = Event()
        self.record = None
        self.project = parent.project
        self.settings = parent.settings
        self.images = parent.images
        self.journal = data_dir() / "publication.json"
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"계정: @{self.settings.ig_username} · {len(self.images)}장"))
        thumbs = QHBoxLayout()
        for image in self.images:
            label = QLabel()
            label.setPixmap(pixmap(image).scaled(56, 70, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            thumbs.addWidget(label)
        layout.addLayout(thumbs)
        layout.addWidget(QLabel("캡션과 해시태그"))
        self.caption = QPlainTextEdit()
        if self.project.caption:
            self.caption.setPlainText(self.project.caption)
        else:
            first = self.project.cards[0]
            self.caption.setPlainText("\n\n".join(filter(None, [self.settings.caption, first.text, first.subtitle, self.settings.hashtags])))
        layout.addWidget(self.caption)
        self.count = QLabel()
        layout.addWidget(self.count)
        self.status = QLabel("올리기 전에 카드 PNG와 작업 파일을 자동 저장합니다.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        layout.addWidget(self.progress)
        row = QHBoxLayout()
        self.close_button = button("취소", self.reject, row)
        self.submit = button("올리기", self.start, row)
        self.link = button("인스타에서 보기", self.open_link, row)
        self.link.setVisible(False)
        layout.addLayout(row)
        self.caption.textChanged.connect(self.update_counts)
        self.update_counts()

    def update_counts(self):
        """입력 중인 캡션의 글자·해시태그 수를 표시하고 게시 가능 여부를 반영한다."""
        length, tags = caption_counts(self.caption.toPlainText())
        self.count.setText(f"{length} / 2200자 · 해시태그 {tags} / 30")
        self.submit.setEnabled(length <= 2200 and tags <= 30 and 1 <= len(self.images) <= 10)

    def start(self):
        """재게시와 최종 동의를 확인한 후 PNG·작업을 백업하고 게시 작업을 시작한다."""
        if self.project.publications:
            record = self.project.publications[-1]
            message = f"이 작업에 {record.get('timestamp', '')[:10]} 게시 기록이 있습니다."
            if record.get("status") == "pending":
                message += " 이전 게시 결과가 불확실합니다. 인스타에서 중복 여부를 확인하세요."
            if not ask(self, message + " 다시 올릴까요?"):
                return
        if not ask(self, f"@{self.settings.ig_username} 계정에 {len(self.images)}장을 게시합니다. 진행할까요?"):
            return
        try:
            remaining = days_remaining(self.settings.expires_at)
            if remaining is not None and remaining <= 0:
                raise ValueError("계정 연결이 만료되었습니다. 설정에서 다시 연결해 주세요.")
            token, key = secret("instagram_token"), secret("imgbb_key")
            if not token or not key:
                raise ValueError("설정에서 인스타 계정과 ImgBB 키를 연결해 주세요.")
            folder = self.settings.output or QFileDialog.getExistingDirectory(self, "카드 자동 저장 폴더")
            if not folder:
                return
            destination = export_png(self.images, Path(folder), self.project.cards[0].text)
            self.project.caption = self.caption.toPlainText()
            self.backup = destination / "작업.wordcard"
            save_project(self.backup, self.project)
            self.parent().autosave()
            snapshot = deepcopy(self.project)
            project_path = self.parent().project_path
            def checkpoint(record):
                """게시 전후 기록을 저널과 작업 사본에 저장해 종료·통신 실패에도 흔적을 남긴다."""
                self.record = record
                if snapshot.publications and snapshot.publications[-1].get("container_id") == record["container_id"]:
                    snapshot.publications[-1] = record
                else:
                    snapshot.publications.append(record)
                # A crash after the server commits still leaves a pending marker.
                atomic_json(self.journal, {"project_path": str(project_path or ""), "backup": str(self.backup), "record": record})
                save_project(self.backup, snapshot)
                save_project(data_dir() / "recovery.wordcard", snapshot)
                if project_path:
                    save_project(project_path, snapshot)
            self.worker = Worker(lambda progress: publish(self.images, self.project.caption, self.settings.ig_id, token, key, progress, self.cancel, checkpoint), self)
            self.worker.progress.connect(self.status.setText)
            self.worker.succeeded.connect(self.success)
            self.worker.failed.connect(self.failure)
            self.worker.finished.connect(self.finished_upload)
            self.caption.setEnabled(False)
            self.submit.setEnabled(False)
            self.progress.setRange(0, 0)
            self.parent().autosave_timer.stop()
            self.worker.start()
        except Exception as exc:
            error(self, exc)

    def remember(self):
        """마지막 게시 상태를 현재 작업 이력에 중복 없이 반영한다."""
        if self.record:
            if self.project.publications and self.project.publications[-1].get("container_id") == self.record["container_id"]:
                self.project.publications[-1] = self.record
            else:
                self.project.publications.append(self.record)
            self.parent().dirty = True

    def success(self, record):
        """게시 완료 상태와 링크 열기 버튼을 표시하고 재전송 버튼을 숨긴다."""
        self.record = record
        self.status.setText("게시 완료!" if record.get("permalink") else "게시 완료! 게시물 링크를 받지 못했습니다. 인스타 계정에서 확인해 주세요.")
        self.link.setVisible(bool(record.get("permalink")))
        self.submit.setVisible(False)

    def failure(self, message):
        """실패 안내를 표시하고 불확실한 결과를 확인 없이 재시도하지 못하게 한다."""
        self.status.setText(message)
        self.submit.setVisible(False)  # Reopen to get duplicate confirmation after uncertain commit.

    def finished_upload(self):
        """게시 이력을 UI에 반영하고 임시 저장과 닫기 동작을 복원한다."""
        self.remember()
        self.parent().autosave()
        self.parent().autosave_timer.start()
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.close_button.setText("닫기")

    def open_link(self):
        """공식 응답에서 검증된 게시물 링크를 기본 브라우저로 연다."""
        if self.record and self.record.get("permalink"):
            QDesktopServices.openUrl(QUrl(self.record["permalink"]))

    def reject(self):
        """게시 전 단계의 취소를 요청하거나 현재 캡션을 보존하고 창을 닫는다."""
        if self.worker and self.worker.isRunning():
            if ask(self, "업로드 중입니다. 취소할까요? 최종 게시 요청이 이미 전송되었다면 취소할 수 없습니다."):
                self.cancel.set()
                self.status.setText("취소 요청을 보냈습니다. 진행 중인 요청의 결과를 기다려 주세요.")
            return
        self.project.caption = self.caption.toPlainText()
        super().reject()

    def closeEvent(self, event):
        """게시 중에는 취소를 요청하고 스레드가 끝날 때까지 창을 유지한다."""
        if self.worker and self.worker.isRunning():
            self.reject()
            event.ignore()
        else:
            super().closeEvent(event)
