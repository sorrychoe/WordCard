from dataclasses import asdict, dataclass, field, fields
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def data_dir() -> Path:
    """운영체제별 사용자 데이터 폴더를 생성하고 경로를 반환한다."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    path = base / "WordCard"
    path.mkdir(parents=True, exist_ok=True)
    return path


def atomic_json(path: Path, data):
    """같은 폴더의 임시 파일을 원자적으로 교체하여 UTF-8 JSON을 저장한다."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
            name = file.name
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
    finally:
        if name and Path(name).exists():
            Path(name).unlink()


@dataclass
class Settings:
    """사용자 기본값과 공개 계정 정보만 보관하며 비밀 값은 제외한다."""
    church: str = "우리교회"
    account: str = ""
    logo: str = ""
    template: str = "light"
    output: str = ""
    ending: bool = True
    ending_phrase: str = "저장하고 묵상하세요"
    page_numbers: bool = True
    indent: bool = False
    caption: str = ""
    hashtags: str = "#주일설교 #말씀"
    ig_id: str = ""
    ig_username: str = ""
    expires_at: str = ""
    overrides: dict = field(default_factory=dict)


def load_settings() -> Settings:
    """설정 JSON의 알려진 필드만 읽고 파일이 없으면 기본값을 반환한다."""
    path = data_dir() / "settings.json"
    if not path.exists():
        return Settings()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("설정 파일 형식이 올바르지 않습니다.")
    defaults = Settings()
    for item in fields(Settings):
        if item.name in data and type(data[item.name]) is not type(getattr(defaults, item.name)):
            raise ValueError("설정 값의 형식이 올바르지 않습니다.")
    return Settings(**{f.name: data[f.name] for f in fields(Settings) if f.name in data})


def save_settings(settings: Settings):
    """비밀 값을 포함하지 않는 설정 데이터를 사용자 폴더에 저장한다."""
    atomic_json(data_dir() / "settings.json", asdict(settings))


def secret(name: str, value: str | None = None) -> str:
    """OS 비밀 저장소에서 값을 읽거나 교체하며 평문 저장소와 임의 백엔드는 거부한다."""
    import keyring
    backend = keyring.get_keyring()
    module = type(backend).__module__
    if not module.startswith(("keyring.backends.Windows", "keyring.backends.macOS", "keyring.backends.SecretService")):
        raise ValueError("OS 자격 증명 저장소를 사용할 수 없습니다. Windows 자격 증명 관리자 또는 키체인을 확인해 주세요.")
    try:
        if value is None:
            return keyring.get_password("WordCard", name) or ""
        if value:
            keyring.set_password("WordCard", name, value)
        elif keyring.get_password("WordCard", name):
            keyring.delete_password("WordCard", name)
        return value
    except Exception:
        raise ValueError("자격 증명 저장소에 접근할 수 없습니다. OS 로그인과 저장소 잠금을 확인해 주세요.") from None
