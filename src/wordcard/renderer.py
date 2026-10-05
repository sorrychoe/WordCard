from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
from .layout import fit, font_name, text_spec
from .parser import Card
from .settings import Settings


def draw_text(draw, text, filename, spec, color):
    """텍스트를 지정 영역에 맞춰 정렬하여 그리며 넘치는 내용은 거부한다."""
    if not text:
        return
    fitted = fit(text, filename, spec)
    if fitted is None:
        raise ValueError("문구가 카드 영역을 넘습니다. 제목·출처·교회명 또는 설정의 문구를 줄여 주세요.")
    face, lines, spacing = fitted
    x, y, width, height = spec["box"]
    y += (height - len(lines) * spacing) / 2
    for line in lines:
        length = draw.textlength(line, font=face)
        align = spec.get("align", "center")
        offset = (width - length) / 2 if align == "center" else width - length if align == "right" else 0
        draw.text((x + offset, y), line, font=face, fill=color, anchor="lt")
        y += spacing


def render(card: Card, template: dict, settings: Settings, index=1, total=1) -> Image.Image:
    """배경·텍스트·교회 정보로 실제 저장과 미리보기에 공통으로 쓸 RGB 이미지를 만든다."""
    width, height = template["size"]
    colors = template["colors"]
    image = Image.new("RGB", (width, height), colors["background"])
    layout = template["cards"][card.type]
    background = template.get("background") or layout.get("background")
    if background:
        path = Path(background)
        if not path.is_absolute():
            path = Path(template["directory"]) / path
        with Image.open(path) as source:
            image = ImageOps.fit(source.convert("RGB"), (width, height), method=Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image)
    draw.line((100, 130, 200, 130), fill=colors["accent"], width=6)
    if card.type == "verse":
        draw_text(draw, "“", template["fonts"]["verse"], {"box": [100, 140, 880, 100], "size": 64}, colors["accent"])
    draw_text(draw, card.text, font_name(template, card.type), text_spec(template, card.type), colors["text"])
    if card.type == "cover":
        draw_text(draw, card.subtitle, template["fonts"]["body"], layout["subtitle"], colors["accent"])
    if card.ref:
        draw_text(draw, card.ref, template["fonts"]["body"], layout.get("ref", template["cards"]["verse"]["ref"]), colors["accent"])
    if card.type == "ending":
        draw_text(draw, "\n".join(filter(None, [settings.account, settings.ending_phrase])), template["fonts"]["body"], layout["message"], colors["accent"])
    if settings.logo and card.type in ("cover", "ending"):
        with Image.open(settings.logo) as source:
            logo = source.convert("RGBA")
            logo.thumbnail((140, 120), Image.Resampling.LANCZOS)
            image.paste(logo, ((width - logo.width) // 2, 170), logo)
    footer = settings.church
    if settings.page_numbers:
        footer += f"  ·  {index}/{total}"
    draw_text(draw, footer, template["fonts"]["body"], template["footer"], colors["text"])
    return image
