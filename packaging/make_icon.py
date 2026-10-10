"""말씀카드 실행 아이콘(펼친 성경 위 십자가)을 Pillow로 그려 packaging/wordcard.ico를 만든다.

사용: python packaging/make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

S = 1024  # 원본 크기. 작은 크기는 여기서 축소한다.
NAVY_TOP, NAVY_BOTTOM = (38, 52, 86), (20, 28, 50)
GOLD, GOLD_DARK = (222, 182, 104), (168, 128, 60)
PAGE, PAGE_SHADE = (250, 245, 234), (226, 216, 196)


def background() -> Image.Image:
    """세로 그라데이션을 채운 둥근 사각형 배경을 만든다."""
    gradient = Image.new("RGB", (1, S))
    for y in range(S):
        t = y / (S - 1)
        gradient.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(NAVY_TOP, NAVY_BOTTOM)))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((24, 24, S - 24, S - 24), radius=200, fill=255)
    image = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    image.paste(gradient.resize((S, S)), mask=mask)
    return image


def page(left: bool) -> list[tuple[float, float]]:
    """펼친 책 한쪽 면의 외곽선 좌표를 반환한다. 위아래 가장자리를 살짝 휘게 그린다."""
    cx, top, bottom, width, sag = S / 2, 600, 860, 340, 60
    sign = -1 if left else 1
    points = []
    for i in range(41):  # 윗변: 가운데(제본선)가 낮고 바깥으로 갈수록 올라간다
        t = i / 40
        points.append((cx + sign * width * t, top + sag * (1 - t) ** 2 - sag * 0.4 * t))
    for i in range(41):  # 아랫변
        t = 1 - i / 40
        points.append((cx + sign * width * t, bottom + sag * (1 - t) ** 2 - sag * 0.4 * t))
    return points


def draw_icon() -> Image.Image:
    """배경, 십자가 후광, 십자가, 펼친 책을 합성한 원본 아이콘을 반환한다."""
    image = background()
    # 십자가 뒤 은은한 후광
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((262, 120, 762, 620), fill=(255, 196, 96, 70))
    image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(70)))

    draw = ImageDraw.Draw(image)
    # 십자가: 세로 기둥이 책 제본선으로 이어진다
    beam = 76
    draw.rounded_rectangle((S / 2 - beam / 2, 150, S / 2 + beam / 2, 640), radius=14, fill=GOLD)
    draw.rounded_rectangle((S / 2 - 170, 270, S / 2 + 170, 270 + beam), radius=14, fill=GOLD)
    draw.rectangle((S / 2 + beam / 2 - 16, 150 + 14, S / 2 + beam / 2, 640), fill=GOLD_DARK)  # 입체감용 그림자 면

    # 책 표지(금색 테두리) → 양쪽 면 → 제본선
    for left in (True, False):
        cover = [(x, y + 26) for x, y in page(left)]
        draw.polygon(cover, fill=GOLD_DARK)
        draw.polygon(page(left), fill=PAGE)
    draw.line((S / 2, 640, S / 2, 916), fill=GOLD_DARK, width=8)
    # 글줄 표현
    for row in range(4):
        y = 700 + row * 40
        for left in (True, False):
            sign = -1 if left else 1
            x1, x2 = S / 2 + sign * 70, S / 2 + sign * (280 - (row == 3) * 90)
            draw.line((min(x1, x2), y, max(x1, x2), y), fill=PAGE_SHADE, width=14)
    return image


def main() -> None:
    """아이콘을 그려 Windows용 다중 크기 .ico로 저장한다."""
    out = Path(__file__).with_name("wordcard.ico")
    draw_icon().save(out, sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    print(out)


if __name__ == "__main__":
    main()
