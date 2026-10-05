from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from .parser import Card, TYPES
from .settings import atomic_json

@dataclass
class Project:
    """입력 원문, 수동 수정 카드, 캡션과 게시 이력을 담는 작업 데이터."""
    source: str = ""
    template: str = "light"
    ratio: str = "4:5"
    cards: list[Card] = field(default_factory=list)
    caption: str = ""
    publications: list[dict] = field(default_factory=list)


def save_project(path: Path, project: Project):
    """작업을 버전이 포함된 JSON으로 원자적으로 저장한다."""
    atomic_json(path, {"version": 1, **asdict(project)})


def load_project(path: Path) -> Project:
    """크기와 카드 스키마를 검증한 작업을 읽으며 잘못된 형식은 거부한다."""
    try:
        if Path(path).stat().st_size > 5_000_000:
            raise ValueError
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("version") != 1 or data.get("ratio") not in ("4:5", "1:1"):
            raise ValueError
        for name in ("source", "template", "caption"):
            if not isinstance(data[name], str):
                raise ValueError
        if not isinstance(data["cards"], list) or len(data["cards"]) > 500:
            raise ValueError
        cards = []
        for item in data["cards"]:
            card = Card(**item)
            if card.type not in TYPES or not all(isinstance(v, str) for v in asdict(card).values()):
                raise ValueError
            cards.append(card)
        records = data.get("publications", [])
        if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
            raise ValueError
        return Project(data["source"], data["template"], data["ratio"], cards, data["caption"], records)
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError("작업 파일 형식이 올바르지 않습니다. 다른 .wordcard 파일을 선택해 주세요.") from None
