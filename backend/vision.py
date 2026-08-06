"""Faza 4: rasm tahlili — Pillow bilan, model/API siz.

Formati, o'lchami, yorug'ligi, asosiy ranglari, EXIF (kamera, sana)
va rasm/fotografiya ekanligi aniqlanadi.
"""

from collections import Counter

from PIL import ExifTags, Image, ImageStat

COLOR_NAMES = {
    "qora": (0, 0, 0),
    "oq": (255, 255, 255),
    "kulrang": (128, 128, 128),
    "qizil": (230, 25, 30),
    "to'q qizil": (128, 0, 0),
    "pushti": (255, 105, 180),
    "binafsha": (150, 50, 200),
    "ko'k": (30, 90, 230),
    "och ko'k": (130, 200, 255),
    "yashil": (60, 180, 75),
    "to'q yashil": (0, 100, 0),
    "sariq": (255, 210, 0),
    "to'q sariq": (255, 140, 0),
    "jigarrang": (139, 90, 43),
    "neft ko'k": (0, 120, 120),
    "mayin jigarrang": (205, 155, 120),
}


def _nearest_color(rgb: tuple[int, int, int]) -> str:
    best, best_d = "noma'lum", float("inf")
    for name, (r, g, b) in COLOR_NAMES.items():
        d = (r - rgb[0]) ** 2 + (g - rgb[1]) ** 2 + (b - rgb[2]) ** 2
        if d < best_d:
            best, best_d = name, d
    return best


def _exif_info(img: Image.Image) -> dict:
    info: dict[str, str] = {}
    try:
        exif = img.getexif()
        for tag, val in exif.items():
            name = ExifTags.TAGS.get(tag, "")
            if name in ("DateTimeOriginal", "Make", "Model"):
                info[name] = str(val)
    except Exception:
        pass
    return info


def analyze(path: str) -> dict:
    """Rasm faylini tahlil qiladi va ma'lumotlar lug'atini qaytaradi."""
    with Image.open(path) as im:
        fmt = im.format or "noma'lum"
        w, h = im.size
        exif = _exif_info(im)

        rgb = im.convert("RGB")
        small = rgb.resize((48, 48))
        pixels = list(small.getdata())

        stat = ImageStat.Stat(rgb.resize((64, 64)))
        brightness = round(sum(stat.mean[:3]) / 3, 1)
        if brightness > 170:
            bright = "yorug'"
        elif brightness > 85:
            bright = "o'rtacha"
        else:
            bright = "qorong'i"

        counter = Counter(pixels)
        total = len(pixels)
        colors = [
            {
                "name": _nearest_color((r, g, b)),
                "percent": round(cnt / total * 100),
            }
            for (r, g, b), cnt in counter.most_common(3)
        ]
        unique = len(counter)
        photo_like = unique > 150

    return {
        "format": fmt,
        "width": w,
        "height": h,
        "brightness": bright,
        "colors": colors,
        "unique_colors": unique,
        "photo_like": photo_like,
        "exif": exif,
    }
