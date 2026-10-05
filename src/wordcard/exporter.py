from datetime import datetime
from pathlib import Path
import re
from PIL import ImageCms

SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def export_png(images, folder: Path, title: str) -> Path:
    """sRGB PNG를 순서대로 새 작업 폴더에 저장하고 해당 폴더를 반환한다."""
    if not images:
        raise ValueError("먼저 카드를 만들어 주세요.")
    title = re.sub(r'[\s<>:"/\\|?*\x00-\x1f]', '', title)[:50].rstrip(". ") or "말씀카드"
    stem = f"{datetime.now():%Y%m%d}_{title}"
    destination = Path(folder) / stem
    number = 1
    while True:
        try:
            destination.mkdir(parents=True, exist_ok=False)
            break
        except FileExistsError:
            number += 1
            destination = Path(folder) / f"{stem}_{number}"
    for i, image in enumerate(images, 1):
        path = destination / f"{stem}_{i:02}.png"
        temp = path.with_suffix(".tmp")
        image.save(temp, format="PNG", icc_profile=SRGB)
        temp.replace(path)
    return destination
