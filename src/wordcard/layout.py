from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
import json
from pathlib import Path
import re
from PIL import ImageFont
from .parser import Card
from .settings import ROOT

PUNCTUATION = '.,!?)」』，。！？、:;”’'


def templates() -> dict:
    """설치된 템플릿 폴더의 JSON과 이미지 기준 경로를 읽어 반환한다."""
    result = {}
    for path in sorted((ROOT / "templates").glob("*/template.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["directory"] = str(path.parent)
        result[path.parent.name] = data
    if not result:
        raise ValueError("템플릿이 없습니다. 프로그램을 다시 설치해 주세요.")
    return result


def prepare_template(template: dict, ratio: str, overrides: dict | None = None) -> dict:
    """원본을 복사해 비율별 안전 여백과 사용자 색상·배경을 적용한다."""
    result = deepcopy(template)
    if ratio not in ("4:5", "1:1"):
        raise ValueError("지원하지 않는 카드 비율입니다.")
    height = 1350 if ratio == "4:5" else 1080
    scale = height / result["size"][1]
    result["size"] = [1080, height]
    for group in [*result["cards"].values(), {"footer": result["footer"]}]:
        for spec in group.values():
            if isinstance(spec, dict) and "box" in spec:
                x, y, w, h = spec["box"]
                y = max(80, round(y * scale))
                spec["box"] = [max(80, x), y, min(w, 1000 - max(80, x)), min(round(h * scale), height - 80 - y)]
    if overrides:
        result["colors"].update(overrides.get("colors", {}))
        result["background"] = overrides.get("background", "")
    return result


@lru_cache(maxsize=160)
def font(filename: str, size: int):
    """번들 폴더의 글꼴을 지정 크기로 읽고 반복 사용을 위해 캐시한다."""
    path = ROOT / "fonts" / filename
    if not path.is_file() or path.parent.resolve() != (ROOT / "fonts").resolve():
        raise ValueError("번들 한글 글꼴을 찾을 수 없습니다. 프로그램을 다시 설치해 주세요.")
    return ImageFont.truetype(str(path), size)


def font_name(template: dict, kind: str) -> str:
    """카드 유형에 해당하는 표지·본문·성경 구절 글꼴 이름을 반환한다."""
    return template["fonts"]["title" if kind == "cover" else "verse" if kind == "verse" else "body"]


def wrap(text: str, face, width: int) -> list[str]:
    """어절 우선으로 줄을 나누며 긴 어절만 쪼개고 줄 첫 문장부호를 피한다."""
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            candidate = f"{line} {word}" if line else word
            if face.getlength(candidate) <= width:
                line = candidate
                continue
            if line:
                # Move the last character with leading punctuation; never exceed the box.
                if word[0] in PUNCTUATION:
                    carry = line[-1]
                    line = line[:-1].rstrip()
                    if line:
                        lines.append(line)
                    word = carry + word
                else:
                    lines.append(line)
                line = ""
            for char in word:
                if line and face.getlength(line + char) > width:
                    if char in PUNCTUATION and len(line) > 1:
                        lines.append(line[:-1])
                        line = line[-1] + char
                    else:
                        lines.append(line)
                        line = char
                else:
                    line += char
        lines.append(line)
    return lines


def fit(text: str, filename: str, spec: dict):
    """허용 범위에서 가장 큰 글꼴과 줄 간격을 찾고 넘치면 None을 반환한다."""
    sizes = spec["size"]
    maximum, minimum = sizes if isinstance(sizes, list) else (sizes, sizes)
    width, height = spec["box"][2:]
    for size in range(maximum, minimum - 1, -2):
        face = font(filename, size)
        lines = wrap(text, face, width)
        spacing = sum(face.getmetrics()) + round(size * .18)
        if len(lines) * spacing <= height and all(face.getlength(line) <= width for line in lines):
            return face, lines, spacing
    face = font(filename, minimum)
    lines = wrap(text, face, width)
    spacing = sum(face.getmetrics()) + round(minimum * .18)
    if len(lines) * spacing <= height and all(face.getlength(line) <= width for line in lines):
        return face, lines, spacing
    return None


def text_spec(template: dict, kind: str):
    """카드 유형의 주 텍스트 영역과 글자 크기 규칙을 반환한다."""
    return template["cards"][kind]["title" if kind == "cover" else "text"]


def paginate(cards: list[Card], template: dict) -> list[Card]:
    """문장 경계를 보존해 넘치는 카드를 나누고 한 문장도 못 담으면 안내한다."""
    result = []
    for card in cards:
        spec = text_spec(template, card.type)
        filename = font_name(template, card.type)
        if fit(card.text, filename, spec):
            result.append(replace(card))
            continue
        # Preserve sentences; an individual unfit sentence needs explicit user editing.
        sentences = re.split(r'(?<=[.!?。！？])\s+|\n+', card.text)
        chunk = ""
        for sentence in sentences:
            if not sentence:
                continue
            if not fit(sentence, filename, spec):
                raise ValueError("한 문장이 카드에 들어가지 않습니다. 문장 사이에 줄바꿈을 넣거나 글을 줄여 주세요.")
            candidate = f"{chunk}\n{sentence}" if chunk else sentence
            if fit(candidate, filename, spec):
                chunk = candidate
            else:
                result.append(replace(card, text=chunk))
                chunk = sentence
        if chunk:
            result.append(replace(card, text=chunk))
    return result
