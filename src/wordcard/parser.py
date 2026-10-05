from dataclasses import dataclass
import re
from .bible_books import REFERENCE

TYPES = {"cover": "표지", "body": "말씀 본문", "verse": "성경 구절", "ending": "마무리"}

@dataclass
class Card:
    """카드 유형과 본문, 성경 출처, 표지 부제를 보관하는 값 객체."""
    type: str
    text: str
    ref: str = ""
    subtitle: str = ""


def parse(text: str, ending: bool = True) -> list[Card]:
    """빈 줄로 문단을 나누고 표지·본문·구절·마무리 카드와 출처를 추출한다."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.replace("\r\n", "\n")) if p.strip()]
    cards = []
    for i, paragraph in enumerate(paragraphs):
        if i == 0:
            title, _, subtitle = paragraph.partition("\n")
            cards.append(Card("cover", title, subtitle=subtitle.strip()))
            continue
        matches = list(REFERENCE.finditer(paragraph))
        if matches:
            refs = " · ".join(m.group().strip().strip("()").strip() for m in matches)
            cards.append(Card("verse", REFERENCE.sub("", paragraph).strip(), refs))
        else:
            kind = "ending" if ending and i == len(paragraphs) - 1 else "body"
            cards.append(Card(kind, paragraph))
    return cards
