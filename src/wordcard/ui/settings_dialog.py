from copy import deepcopy
from datetime import datetime, time, timezone
from pathlib import Path
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDateEdit, QDialog, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QScrollArea, QVBoxLayout, QWidget,
)
from ..settings import ROOT, save_settings, secret
from ..uploader import connect
from .common import Worker, button, error


class SettingsDialog(QDialog):
    """교회 정보, 템플릿 기본값, 비밀 저장소의 계정 연결을 편집하는 창."""
    def __init__(self, settings, templates, parent=None):
        """설정 사본으로 편집 폼과 비밀번호 입력칸, 연결 확인 버튼을 구성한다."""
        super().__init__(parent)
        self.setWindowTitle("교회와 계정 설정")
        self.resize(680, 780)
        self.settings = deepcopy(settings)
        self.worker = None
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.fields = {}
        for key, label in [("church", "교회명"), ("account", "인스타 표시 이름 (@계정)"), ("ending_phrase", "마무리 고정 문구"), ("caption", "기본 캡션"), ("hashtags", "기본 해시태그")]:
            entry = QLineEdit(getattr(settings, key))
            self.fields[key] = entry
            form.addRow(label, entry)
        for key, label in [("logo", "교회 로고"), ("output", "기본 저장 폴더")]:
            row = QHBoxLayout()
            entry = QLineEdit(getattr(settings, key))
            self.fields[key] = entry
            row.addWidget(entry)
            button("찾기", lambda checked=False, k=key: self.choose_file(k), row)
            form.addRow(label, row)
        self.logo_preview = QLabel()
        self.logo_preview.setFixedHeight(80)
        form.addRow("로고 미리보기", self.logo_preview)
        self.fields["logo"].textChanged.connect(self.show_logo)
        self.show_logo()
        self.default_template = QComboBox()
        for key, template in templates.items():
            self.default_template.addItem(template["name"], key)
        self.default_template.setCurrentIndex(max(0, self.default_template.findData(settings.template)))
        form.addRow("기본 템플릿 / 색상 편집 대상", self.default_template)
        self.colors = {}
        self.color_row = QHBoxLayout()
        for key, label in [("background", "배경색"), ("text", "글자색"), ("accent", "강조색")]:
            self.colors[key] = button(label, lambda checked=False, k=key: self.choose_color(k), self.color_row)
        form.addRow("템플릿 색상", self.color_row)
        self.background = QLineEdit()
        self.background.setPlaceholderText("비우면 기본 배경을 사용합니다")
        background_row = QHBoxLayout()
        background_row.addWidget(self.background)
        button("찾기", self.choose_background, background_row)
        form.addRow("배경 이미지", background_row)
        self.current_template = self.default_template.currentData()
        self.background.setText(self.settings.overrides.get(self.current_template, {}).get("background", ""))
        self.default_template.currentIndexChanged.connect(self.switch_template)
        for key, label in [("ending", "마지막 문단을 마무리 카드로"), ("page_numbers", "페이지 번호 표시")]:
            entry = QCheckBox(label)
            entry.setChecked(getattr(settings, key))
            self.fields[key] = entry
            form.addRow(entry)
        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.token.setPlaceholderText("새 토큰 입력 (비우면 기존 연결 유지)")
        form.addRow("인스타 액세스 토큰", self.token)
        self.expires = QDateEdit(QDate.currentDate().addDays(60))
        self.expires.setCalendarPopup(True)
        self.expires.setDisplayFormat("yyyy-MM-dd")
        form.addRow("토큰 실제 만료일", self.expires)
        note = QLabel("장기 토큰을 입력하고 발급 화면의 만료일을 선택하세요.\n이전에 발급한 토큰은 발급일로부터 60일을 기준으로 입력하세요.")
        note.setWordWrap(True)
        form.addRow(note)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("새 키 입력 (비우면 기존 키 유지)")
        form.addRow("ImgBB 이미지 호스팅 키", self.key)
        self.status = QLabel(f"@{settings.ig_username} 연결됨" if settings.ig_id else "연결된 계정이 없습니다")
        self.status.setWordWrap(True)
        form.addRow(self.status)
        row = QHBoxLayout()
        self.test_button = button("연결 테스트 및 저장", self.test_connection, row)
        button("연결 해제", self.disconnect, row)
        button("연결 안내", self.show_help, row)
        form.addRow(row)
        actions = QHBoxLayout()
        button("닫기", self.reject, actions)
        self.save_button = button("설정 저장", self.save, actions)
        outer.addLayout(actions)

    def show_logo(self):
        """설정에 입력된 로고 파일을 비율에 맞춰 작게 표시한다."""
        self.logo_preview.setPixmap(QPixmap(self.fields["logo"].text()).scaled(100, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def choose_file(self, key):
        """로고 또는 기본 저장 폴더를 선택해 해당 입력칸에 반영한다."""
        value = QFileDialog.getExistingDirectory(self, "저장 폴더 선택") if key == "output" else QFileDialog.getOpenFileName(self, "로고 선택", "", "그림 (*.png *.jpg *.jpeg)")[0]
        if value:
            self.fields[key].setText(value)

    def choose_background(self):
        """템플릿 배경으로 사용할 로컬 이미지 파일을 선택한다."""
        value = QFileDialog.getOpenFileName(self, "배경 선택", "", "그림 (*.png *.jpg *.jpeg)")[0]
        if value:
            self.background.setText(value)

    def switch_template(self):
        """이전 템플릿의 배경 변경을 보관하고 새 템플릿의 설정을 표시한다."""
        self.settings.overrides.setdefault(self.current_template, {})["background"] = self.background.text().strip()
        self.current_template = self.default_template.currentData()
        self.background.setText(self.settings.overrides.get(self.current_template, {}).get("background", ""))

    def choose_color(self, key):
        """사용자가 선택한 색상을 해당 템플릿의 배경·본문·강조 색상에 반영한다."""
        color = QColorDialog.getColor(parent=self, title="카드 색상 선택")
        if color.isValid():
            self.settings.overrides.setdefault(self.current_template, {}).setdefault("colors", {})[key] = color.name()

    def show_help(self):
        """설치본에 포함된 인스타 계정 연결 안내를 읽기 전용 창으로 연다."""
        dialog = QDialog(self)
        dialog.setWindowTitle("인스타 연결 안내")
        dialog.resize(650, 600)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText((ROOT / "docs/인스타_연결_안내.md").read_text(encoding="utf-8"))
        layout.addWidget(text)
        button("닫기", dialog.accept, layout)
        dialog.exec()

    def test_connection(self):
        """새 토큰 또는 저장 토큰으로 계정을 조회하는 백그라운드 작업을 시작한다."""
        try:
            token = self.token.text().strip() or secret("instagram_token")
            if self.token.text().strip() and self.expires.date() <= QDate.currentDate():
                raise ValueError("만료일이 지났습니다. 새 장기 토큰을 발급받아 주세요.")
        except Exception as exc:
            error(self, exc)
            return
        self.test_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.token.setEnabled(False)
        self.expires.setEnabled(False)
        self.status.setText("계정 확인 중…")
        self.worker = Worker(lambda progress: connect(token), self)
        self.worker.succeeded.connect(lambda result: self.connected(result, token))
        self.worker.failed.connect(self.status.setText)
        self.worker.finished.connect(lambda: self.test_button.setEnabled(True))
        self.worker.finished.connect(lambda: self.save_button.setEnabled(True))
        self.worker.finished.connect(lambda: self.token.setEnabled(True))
        self.worker.finished.connect(lambda: self.expires.setEnabled(True))
        self.worker.start()

    def connected(self, result, token):
        """확인된 토큰은 OS 저장소에, 계정 정보와 만료일은 설정 파일에 저장한다."""
        try:
            secret("instagram_token", token)
            self.settings.ig_id = result["id"]
            self.settings.ig_username = result["username"]
            if self.token.text().strip():
                self.settings.expires_at = datetime.combine(self.expires.date().toPython(), time.max, timezone.utc).isoformat()
            self.token.clear()
            save_settings(self.settings)
            # Connection is committed immediately; keep the main window in sync on Cancel.
            self.parent().settings = deepcopy(self.settings)
            self.status.setText(f"@{result['username']} 연결됨")
        except Exception as exc:
            error(self, exc)

    def disconnect(self):
        """진행 중인 연결 확인이 없으면 저장 토큰과 공개 계정 정보를 제거한다."""
        if self.worker and self.worker.isRunning():
            return
        try:
            secret("instagram_token", "")
            self.settings.ig_id = self.settings.ig_username = self.settings.expires_at = ""
            save_settings(self.settings)
            self.parent().settings = deepcopy(self.settings)
            self.token.clear()
            self.status.setText("계정 연결을 해제했습니다")
        except Exception as exc:
            error(self, exc)

    def save(self):
        """일반 설정을 검증하고 새 호스팅 키는 비밀 저장소에 따로 저장한다."""
        try:
            if self.token.text().strip():
                raise ValueError("입력한 토큰의 [연결 테스트 및 저장]을 먼저 눌러 주세요.")
            for key, widget in self.fields.items():
                value = widget.isChecked() if isinstance(widget, QCheckBox) else widget.text().strip()
                if key == "logo" and value and not Path(value).is_file():
                    raise ValueError("로고 파일을 찾을 수 없습니다. 다시 선택해 주세요.")
                setattr(self.settings, key, value)
            self.switch_template()
            self.settings.template = self.default_template.currentData()
            if self.key.text().strip():
                secret("imgbb_key", self.key.text().strip())
            save_settings(self.settings)
            self.accept()
        except Exception as exc:
            error(self, exc)

    def reject(self):
        """계정 확인 중에는 닫기를 보류하여 실행 중인 스레드를 보호한다."""
        if self.worker and self.worker.isRunning():
            self.status.setText("계정 확인이 끝난 후 닫아 주세요.")
            return
        super().reject()

    def closeEvent(self, event):
        """연결 확인 스레드가 실행 중이면 창 파괴를 막는다."""
        if self.worker and self.worker.isRunning():
            event.ignore()
        else:
            super().closeEvent(event)
