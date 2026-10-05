from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QSize, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QSplitter, QVBoxLayout, QWidget,
)
from .. import __version__
from ..exporter import export_png
from ..layout import paginate, prepare_template, templates
from ..parser import Card, TYPES, parse
from ..project import Project, load_project, save_project
from ..renderer import render
from ..settings import ROOT, Settings, data_dir, load_settings, save_settings, secret
from ..uploader import days_remaining, expiry_date, refresh
from .common import Worker, ask, button, error, pixmap
from .settings_dialog import SettingsDialog
from .upload_dialog import UploadDialog


class MainWindow(QMainWindow):
    """원문 입력, 카드 편집·미리보기, 파일 저장과 계정 작업을 연결하는 기본 창."""
    def __init__(self):
        """기본 설정을 읽고 입력·편집·미리보기 위젯과 저장 타이머를 구성한다."""
        super().__init__()
        self.setWindowTitle("말씀카드")
        self.resize(1180, 860)
        self.templates = templates()
        self.start_error = None
        try:
            self.settings = load_settings()
        except Exception:
            self.settings = Settings()
            self.start_error = "설정 파일을 읽지 못했습니다. 기본 설정으로 열었습니다. 설정에서 교회 정보를 다시 확인해 주세요."
        self.project = Project(template=self.settings.template)
        self.project_path = None
        self.images = []
        self.index = 0
        self.dirty = False
        self.loading = False
        self.refresh_worker = None
        self.edit_timer = QTimer(self)
        self.edit_timer.setSingleShot(True)
        self.edit_timer.setInterval(350)
        self.edit_timer.timeout.connect(self.edit_card)
        self.generate_timer = QTimer(self)
        self.generate_timer.setSingleShot(True)
        self.generate_timer.setInterval(1000)
        self.generate_timer.timeout.connect(lambda: self.generate(silent=True))
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        toolbar = QHBoxLayout()
        for text, handler, shortcut in [("새 작업", self.new_project, "Ctrl+N"), ("열기", self.open_project, "Ctrl+O"), ("작업 저장", self.save, "Ctrl+S"), ("설정", self.configure, None), ("정보", self.about, None)]:
            button(text, handler, toolbar)
            if shortcut:
                action = QAction(text, self)
                action.setShortcut(QKeySequence(shortcut))
                action.triggered.connect(handler)
                self.addAction(action)
        outer.addLayout(toolbar)
        splitter = QSplitter()
        outer.addWidget(splitter, 1)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("① 설교 요약 또는 성경 구절 입력"))
        self.source = QPlainTextEdit()
        self.source.setPlaceholderText("첫 줄에 제목을 입력하세요.\n둘째 줄에는 날짜와 설교자를 적으세요.\n\n빈 줄로 문단을 나누면 카드가 나뉩니다.")
        self.source.setAccessibleName("전체 입력 글")
        self.source.textChanged.connect(self.source_changed)
        left_layout.addWidget(self.source, 1)
        self.auto = QCheckBox("입력 후 1초 멈추면 자동 만들기")
        left_layout.addWidget(self.auto)
        left_layout.addWidget(QLabel("② 카드 모양"))
        self.template_box = QComboBox()
        for key, template in self.templates.items():
            self.template_box.addItem(template["name"], key)
        self.template_box.setCurrentIndex(max(0, self.template_box.findData(self.settings.template)))
        self.project.template = self.template_box.currentData()
        left_layout.addWidget(self.template_box)
        self.ratio = QComboBox()
        self.ratio.addItems(["4:5", "1:1"])
        left_layout.addWidget(self.ratio)
        self.template_box.currentIndexChanged.connect(self.change_design)
        self.ratio.currentTextChanged.connect(self.change_design)
        button("카드 만들기 (Ctrl+Enter)", self.generate, left_layout)
        action = QAction(self)
        action.setShortcut(QKeySequence("Ctrl+Return"))
        action.triggered.connect(self.generate)
        self.addAction(action)
        splitter.addWidget(left)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("③ 미리보기와 카드 수정"))
        self.preview = QLabel("왼쪽에 글을 입력하고 [카드 만들기]를 눌러 주세요.")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(300, 280)
        self.preview.setStyleSheet("background: #deded8; border-radius: 6px;")
        right_layout.addWidget(self.preview, 1)
        nav = QHBoxLayout()
        button("◀ 이전", lambda: self.select(self.index - 1), nav)
        self.page = QLabel("0 / 0")
        self.page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(self.page)
        button("다음 ▶", lambda: self.select(self.index + 1), nav)
        right_layout.addLayout(nav)
        editor_row = QHBoxLayout()
        editor_row.addWidget(QLabel("카드 유형"))
        self.kind = QComboBox()
        for key, label in TYPES.items():
            self.kind.addItem(label, key)
        self.kind.currentIndexChanged.connect(self.schedule_edit)
        editor_row.addWidget(self.kind)
        right_layout.addLayout(editor_row)
        self.card_text = QPlainTextEdit()
        self.card_text.setMaximumHeight(100)
        self.card_text.setAccessibleName("이 카드의 글")
        self.card_text.textChanged.connect(self.schedule_edit)
        right_layout.addWidget(self.card_text)
        self.subtitle = QLineEdit()
        self.subtitle.setPlaceholderText("표지 부제 (날짜·설교자)")
        self.subtitle.textChanged.connect(self.schedule_edit)
        right_layout.addWidget(self.subtitle)
        self.ref = QLineEdit()
        self.ref.setPlaceholderText("성경 장절 출처")
        self.ref.textChanged.connect(self.schedule_edit)
        right_layout.addWidget(self.ref)
        self.thumbnails = QListWidget()
        self.thumbnails.setFlow(QListWidget.Flow.LeftToRight)
        self.thumbnails.setMaximumHeight(105)
        self.thumbnails.setIconSize(QSize(52, 65))
        self.thumbnails.currentRowChanged.connect(self.select)
        right_layout.addWidget(self.thumbnails)
        actions = QHBoxLayout()
        self.export_button = button("PNG로 모두 저장", self.export, actions)
        self.upload_button = button("계정 연결하기", self.upload, actions)
        right_layout.addLayout(actions)
        splitter.addWidget(right)
        splitter.setSizes([440, 680])
        self.status = QLabel()
        outer.addWidget(self.status)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(60000)
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start()
        self.update_status()
        QTimer.singleShot(0, self.startup)

    def startup(self):
        """이전 임시 작업과 불확실한 게시를 안내하고 필요한 토큰 갱신을 시작한다."""
        if self.start_error:
            QMessageBox.warning(self, "설정 확인", self.start_error)
        recovery = data_dir() / "recovery.wordcard"
        if recovery.exists() and ask(self, "이전 작업의 임시 저장 파일이 있습니다. 복구할까요?"):
            try:
                self.apply_project(load_project(recovery))
                self.dirty = True
            except Exception as exc:
                error(self, exc)
        journal = data_dir() / "publication.json"
        if journal.exists():
            try:
                data = json.loads(journal.read_text(encoding="utf-8"))
                if data.get("record", {}).get("status") == "pending":
                    QMessageBox.warning(self, "이전 게시 확인", "결과를 확인하지 못한 게시 요청이 있습니다. 다시 올리기 전에 인스타 계정을 확인해 주세요.\n자동 저장 작업: " + data.get("backup", ""))
            except (OSError, ValueError):
                pass
        self.refresh_token()

    def current_template(self):
        """현재 선택한 비율과 교회 설정을 반영한 템플릿 사본을 반환한다."""
        key = self.template_box.currentData()
        return prepare_template(self.templates[key], self.ratio.currentText(), self.settings.overrides.get(key))

    def source_changed(self):
        """원문 변경을 작업에 반영하고 선택적으로 지연 카드 생성을 예약한다."""
        if self.loading:
            return
        self.project.source = self.source.toPlainText()
        self.dirty = True
        if self.auto.isChecked():
            self.generate_timer.start()

    def generate(self, checked=False, silent=False):
        """입력 원문을 카드로 나누고 모두 그린 후 성공한 결과만 화면에 반영한다."""
        self.generate_timer.stop()
        self.edit_timer.stop()
        try:
            if len(self.source.toPlainText()) > 100000:
                raise ValueError("입력 글이 너무 깁니다. 10만 자 이하로 나눠 주세요.")
            cards = paginate(parse(self.source.toPlainText(), self.settings.ending), self.current_template())
            if not cards:
                raise ValueError("먼저 제목과 글을 입력해 주세요.")
            images = self.render_cards(cards)
            self.project.cards = cards
            self.project.source = self.source.toPlainText()
            self.images = images
            self.index = 0
            self.dirty = True
            self.rebuild_thumbnails()
            self.select(0)
            self.warn_count(silent)
        except Exception as exc:
            if silent:
                self.status.setText(str(exc) if isinstance(exc, ValueError) else "카드를 만들지 못했습니다. 설정의 이미지 파일을 확인해 주세요.")
            else:
                error(self, exc)

    def render_cards(self, cards):
        """현재 템플릿과 교회 설정으로 순번이 포함된 카드 이미지를 생성한다."""
        template = self.current_template()
        return [render(card, template, self.settings, i, len(cards)) for i, card in enumerate(cards, 1)]

    def rebuild_thumbnails(self):
        """선택 변경 신호를 잠시 막고 현재 이미지로 썸네일 목록을 다시 채운다."""
        self.thumbnails.blockSignals(True)
        self.thumbnails.clear()
        for i, image in enumerate(self.images, 1):
            self.thumbnails.addItem(QListWidgetItem(QIcon(pixmap(image)), str(i)))
        self.thumbnails.blockSignals(False)

    def select(self, index):
        """이전 카드 수정을 먼저 반영한 뒤 선택한 카드의 편집 값과 이미지를 표시한다."""
        if not self.images or index < 0 or index >= len(self.images):
            return
        if self.edit_timer.isActive() and not self.loading:
            self.edit_timer.stop()
            if not self.edit_card():
                return
        self.index = min(index, len(self.images) - 1)
        card = self.project.cards[self.index]
        self.loading = True
        self.card_text.setPlainText(card.text)
        self.subtitle.setText(card.subtitle)
        self.ref.setText(card.ref)
        self.kind.setCurrentIndex(self.kind.findData(card.type))
        self.subtitle.setEnabled(card.type == "cover")
        self.ref.setEnabled(card.type == "verse" or bool(card.ref))
        self.thumbnails.blockSignals(True)
        self.thumbnails.setCurrentRow(self.index)
        self.thumbnails.blockSignals(False)
        self.loading = False
        self.show_preview()

    def show_preview(self):
        """저장용 원본 이미지를 화면 크기로 축소하고 현재 페이지를 표시한다."""
        if self.images:
            self.preview.setPixmap(pixmap(self.images[self.index]).scaled(self.preview.size() - QSize(12, 12), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.page.setText(f"{self.index + 1} / {len(self.images)}")

    def resizeEvent(self, event):
        """창 크기가 바뀌면 원본 이미지의 비율을 유지하며 미리보기를 갱신한다."""
        super().resizeEvent(event)
        if hasattr(self, "preview"):
            self.show_preview()

    def schedule_edit(self, *args):
        """프로그램이 필드를 채우는 경우를 제외하고 카드 수정 적용을 지연 예약한다."""
        if not self.loading and self.project.cards:
            self.edit_timer.start()
            self.dirty = True

    def edit_card(self):
        """수정 카드를 검증하고 필요하면 분할하며 실패할 때 기존 이미지를 보존한다."""
        if self.loading or not self.project.cards:
            return True
        try:
            card = Card(self.kind.currentData(), self.card_text.toPlainText(), self.ref.text(), self.subtitle.text())
            pieces = paginate([card], self.current_template())
            if not pieces:
                pieces = [card]
            cards = self.project.cards[:self.index] + pieces + self.project.cards[self.index + 1:]
            if len(pieces) == 1:
                image = render(card, self.current_template(), self.settings, self.index + 1, len(cards))
                self.project.cards = cards
                self.images[self.index] = image
                self.thumbnails.item(self.index).setIcon(QIcon(pixmap(image)))
                self.subtitle.setEnabled(card.type == "cover")
                self.ref.setEnabled(card.type == "verse" or bool(card.ref))
                self.show_preview()
            else:
                images = self.render_cards(cards)
                self.project.cards = cards
                self.images = images
                self.rebuild_thumbnails()
                self.select(self.index)
            self.warn_count(True)
            return True
        except Exception as exc:
            self.status.setText(str(exc) if isinstance(exc, ValueError) else "카드를 수정하지 못했습니다. 이미지 파일을 확인해 주세요.")
            return False

    def flush_edit(self):
        """예약된 편집을 즉시 적용하고 안전하게 저장할 수 있는지 반환한다."""
        if self.edit_timer.isActive():
            self.edit_timer.stop()
        return self.edit_card()

    def change_design(self, *args):
        """수동 수정 내용을 유지하며 모양을 바꾸고 실패하면 이전 선택으로 되돌린다."""
        if self.loading:
            return
        old_template, old_ratio = self.project.template, self.project.ratio
        try:
            cards = paginate(self.project.cards, self.current_template())
            images = self.render_cards(cards)
            self.project.cards = cards
            self.images = images
            self.project.template = self.template_box.currentData()
            self.project.ratio = self.ratio.currentText()
            self.dirty = True
            self.rebuild_thumbnails()
            self.select(min(self.index, len(images) - 1))
            self.warn_count(True)
        except Exception as exc:
            self.loading = True
            self.template_box.setCurrentIndex(self.template_box.findData(old_template))
            self.ratio.setCurrentText(old_ratio)
            self.loading = False
            error(self, exc)

    def warn_count(self, silent=False):
        """계정 상태를 갱신하고 10장 초과 시 문단을 줄이도록 안내한다."""
        self.update_status()
        if len(self.images) > 10:
            message = "글이 너무 길어 10장을 넘습니다. 문단을 줄이거나 나눠서 올려 주세요."
            self.status.setText(message)
            if not silent:
                QMessageBox.warning(self, "카드 장수 확인", message)

    def update_status(self):
        """계정 연결과 만료까지 남은 날짜를 표시하고 게시 버튼 문구를 맞춘다."""
        self.upload_button.setText("인스타에 올리기" if self.settings.ig_id else "계정 연결하기")
        if self.settings.ig_id:
            days = days_remaining(self.settings.expires_at)
            self.status.setText(f"인스타: @{self.settings.ig_username} 연결됨" + (f" · 토큰 만료 D-{max(0, int(days))}" if days is not None else " · 만료일 확인 필요"))
        else:
            self.status.setText("인스타 계정이 연결되지 않았습니다. 카드 만들기와 PNG 저장은 오프라인으로 사용할 수 있습니다.")

    def apply_project(self, project):
        """불러온 작업을 먼저 검증·이미지화한 뒤 현재 작업과 화면을 교체한다."""
        if project.template not in self.templates:
            raise ValueError("이 작업의 템플릿이 없습니다. 해당 템플릿 폴더를 추가해 주세요.")
        # Validate all images before replacing the current work.
        template = prepare_template(self.templates[project.template], project.ratio, self.settings.overrides.get(project.template))
        images = [render(c, template, self.settings, i, len(project.cards)) for i, c in enumerate(project.cards, 1)]
        self.loading = True
        self.edit_timer.stop()
        self.generate_timer.stop()
        self.project = project
        self.source.setPlainText(project.source)
        self.template_box.setCurrentIndex(self.template_box.findData(project.template))
        self.ratio.setCurrentText(project.ratio)
        self.images = images
        self.index = 0
        self.card_text.clear()
        self.subtitle.clear()
        self.ref.clear()
        self.preview.clear()
        self.page.setText("0 / 0")
        self.loading = False
        self.rebuild_thumbnails()
        self.select(0)
        self.dirty = False
        self.warn_count(True)

    def maybe_save(self):
        """변경된 작업의 저장·버리기·취소를 묻고 진행 가능 여부를 반환한다."""
        if not self.dirty:
            return True
        choice = QMessageBox.question(self, "작업 저장", "변경한 작업을 저장할까요?", QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if choice == QMessageBox.StandardButton.Cancel:
            return False
        return self.save() if choice == QMessageBox.StandardButton.Save else True

    def new_project(self):
        """이전 변경 처리 후 새 작업을 열고 오래된 임시 저장 파일을 제거한다."""
        if self.maybe_save():
            self.apply_project(Project(template=self.template_box.currentData()))
            self.project_path = None
            (data_dir() / "recovery.wordcard").unlink(missing_ok=True)

    def open_project(self):
        """파일 선택 창에서 고른 작업을 검증해 열고 현재 저장 경로를 갱신한다."""
        if not self.maybe_save():
            return
        filename = QFileDialog.getOpenFileName(self, "작업 열기", "", "말씀카드 작업 (*.wordcard)")[0]
        if filename:
            try:
                self.apply_project(load_project(Path(filename)))
                self.project_path = Path(filename)
            except Exception as exc:
                error(self, exc)

    def save(self):
        """카드 수정을 확정하고 작업을 선택한 경로에 저장하며 성공 여부를 반환한다."""
        if not self.flush_edit():
            error(self, ValueError("수정 중인 카드가 너무 깁니다. 글을 줄인 후 저장해 주세요."))
            return False
        path = self.project_path
        if path is None:
            filename = QFileDialog.getSaveFileName(self, "작업 저장", "말씀카드.wordcard", "말씀카드 작업 (*.wordcard)")[0]
            if not filename:
                return False
            path = Path(filename).with_suffix(".wordcard")
        try:
            save_project(path, self.project)
            self.project_path = path
            self.dirty = False
            self.status.setText(f"작업을 저장했습니다: {path}")
            return True
        except Exception as exc:
            error(self, exc)
            return False

    def autosave(self):
        """현재 작업을 복구용 파일에 저장하고 저장 실패를 상태 표시줄로 알린다."""
        if not self.project.source and not self.project.cards:
            return
        try:
            if not self.flush_edit():
                return
            save_project(data_dir() / "recovery.wordcard", self.project)
        except Exception:
            self.status.setText("임시 저장에 실패했습니다. 저장 공간과 폴더 권한을 확인해 주세요.")

    def export(self):
        """수정 내용을 확정한 후 PNG를 저장하고 결과 폴더 열기 버튼을 제공한다."""
        if not self.flush_edit() or not self.images:
            error(self, ValueError("카드를 먼저 만들고, 수정 중인 글이 카드 안에 들어가는지 확인해 주세요."))
            return
        folder = QFileDialog.getExistingDirectory(self, "카드 저장 폴더", self.settings.output)
        if folder:
            try:
                destination = export_png(self.images, Path(folder), self.project.cards[0].text)
                box = QMessageBox(self)
                box.setWindowTitle("저장 완료")
                box.setText(f"PNG {len(self.images)}장을 저장했습니다.\n{destination}")
                open_button = box.addButton("폴더 열기", QMessageBox.ButtonRole.ActionRole)
                box.addButton("닫기", QMessageBox.ButtonRole.RejectRole)
                box.exec()
                if box.clickedButton() == open_button:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(destination)))
            except Exception as exc:
                error(self, exc)

    def configure(self):
        """계정 갱신과 충돌하지 않도록 설정 창을 열고 변경된 디자인을 적용한다."""
        if self.refresh_worker and self.refresh_worker.isRunning():
            error(self, ValueError("계정 연결을 갱신하고 있습니다. 잠시 후 설정을 열어 주세요."))
            return
        self.generate_timer.stop()
        if not self.flush_edit():
            return
        dialog = SettingsDialog(self.settings, self.templates, self)
        if dialog.exec():
            self.settings = dialog.settings
        self.change_design()
        self.update_status()

    def upload(self):
        """계정과 카드 장수를 확인한 뒤 별도의 게시 창을 연다."""
        self.generate_timer.stop()
        if not self.settings.ig_id:
            self.configure()
            return
        if self.refresh_worker and self.refresh_worker.isRunning():
            error(self, ValueError("계정 연결을 갱신하고 있습니다. 잠시 후 다시 눌러 주세요."))
            return
        if not self.flush_edit() or not 1 <= len(self.images) <= 10:
            error(self, ValueError("카드를 1~10장으로 만들고 수정 중인 글을 확인해 주세요."))
            return
        UploadDialog(self).exec()
        self.dirty = True

    def refresh_token(self):
        """만료 7일 이내의 유효 토큰을 백그라운드에서 갱신한다."""
        if not self.settings.ig_id:
            return
        days = days_remaining(self.settings.expires_at)
        if days is None or days <= 0:
            self.status.setText("계정 만료일을 확인할 수 없거나 만료되었습니다. 설정에서 다시 연결해 주세요.")
            return
        if days > 7:
            return
        def task(progress):
            """저장된 토큰을 갱신해 비밀 저장소에 교체하고 새 수명만 UI에 반환한다."""
            result = refresh(secret("instagram_token"))
            secret("instagram_token", result["access_token"])
            return result["expires_in"]
        self.refresh_worker = Worker(task, self)
        self.refresh_worker.succeeded.connect(self.refreshed)
        self.refresh_worker.failed.connect(self.status.setText)
        self.refresh_worker.start()

    def refreshed(self, seconds):
        """갱신 결과의 실제 수명으로 새 만료일을 저장하고 계정 상태를 표시한다."""
        self.settings.expires_at = expiry_date(seconds)
        try:
            save_settings(self.settings)
            self.update_status()
        except Exception as exc:
            error(self, exc)

    def about(self):
        """프로그램 버전과 번들 글꼴·GUI 라이선스를 한국어로 알린다."""
        QMessageBox.about(self, "말씀카드 정보", f"말씀카드 {__version__}\n교회를 위한 카드뉴스 만들기\n\n나눔고딕·나눔명조: NAVER, SIL Open Font License 1.1\n배포 폴더 fonts/OFL-Nanum.txt 참조\nPySide6 / Qt: LGPLv3 (동적 라이브러리)\n성경 본문 데이터는 포함하지 않습니다.")

    def closeEvent(self, event):
        """진행 중인 계정 갱신과 미저장 변경을 처리한 뒤 정상 종료한다."""
        if self.refresh_worker and self.refresh_worker.isRunning():
            self.status.setText("계정 갱신이 끝난 후 닫아 주세요.")
            event.ignore()
            return
        if not self.maybe_save():
            event.ignore()
            return
        try:
            (data_dir() / "recovery.wordcard").unlink(missing_ok=True)
        except OSError:
            pass
        event.accept()
