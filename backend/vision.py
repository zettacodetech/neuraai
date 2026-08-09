"""Faza 4: rasm tahlili — Pillow bilan, model/API siz.

Formati, o'lchami, yorug'ligi, asosiy ranglari, EXIF (kamera, sana)
va rasm/fotografiya ekanligi aniqlanadi. Qo'shimcha: OCR (matn o'qish)
Ollama vision model (llama3.2-vision) orqali.
"""

import base64
import os
import urllib.request
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


def ocr(path: str, timeout: float = 60.0) -> str:
    """Suratdagi matnni o'qiydi (Ollama vision model orqali).

    OLLAMA_BASE_URL (yoki _2.._8) serverlaridan birini sinaydi.
    Topilmasa yoki xato bo'lsa — bo'sh qator qaytaradi.
    """
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    except Exception:
        return ""

    model = os.environ.get("OLLAMA_VISION_MODEL", "llama3.2-vision")
    base_urls = [os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")]
    for i in range(2, 9):
        u = os.environ.get(f"OLLAMA_BASE_URL_{i}", "").strip()
        if u:
            base_urls.append(u)

    prompt = (
        "Bu suratdagi BARCHA matnni aniq o'qib chiq. "
        "Faqat matnning o'zini qaytar, hech qanday izohsiz. "
        "Agar matn bo'lmasa, 'matn topilmadi' deb yoz."
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [b64],
        "stream": False,
        "options": {"temperature": 0},
    }
    body = bytes(
        __import__("json").dumps(payload),
        "utf-8",
    )

    for base_url in base_urls:
        try:
            req = urllib.request.Request(
                base_url.rstrip("/") + "/api/generate",
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = __import__("json").loads(r.read().decode())
            out = str(data.get("response", "")).strip()
            if out and out.lower() != "matn topilmadi":
                return out
        except Exception:
            continue
    return ""


def describe(path: str, timeout: float = 90.0) -> str:
    """Rasmdagi barcha narsalarni AI (vision model) bilan batafsil tasvirlaydi.

    Obyektlar, odamlar, hayvonlar, transport, joy, hislatlar va boshqalar.
    O'zbek tilida javob qaytaradi. Xato bo'lsa — bo'sh qator.
    """
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    except Exception:
        return ""

    model = os.environ.get("OLLAMA_VISION_MODEL", "llama3.2-vision")
    base_urls = [os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")]
    for i in range(2, 9):
        u = os.environ.get(f"OLLAMA_BASE_URL_{i}", "").strip()
        if u:
            base_urls.append(u)

    prompt = (
        "Bu rasmni diqqat bilan ko'rib chiq va undagi BARCHA narsalarni "
        "o'zbek tilida batafsil tasvirlab ber: qanday obyektlar, odamlar, "
        "hayvonlar, transport vositalari, joy, ranglar, harakat va xolatlar. "
        "Agar rasmda matn bo'lsa, uni ham ayt. Aniq, tartibli ro'yxat qilib yoz."
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [b64],
        "stream": False,
        "options": {"temperature": 0.4},
    }
    body = bytes(__import__("json").dumps(payload), "utf-8")

    for base_url in base_urls:
        try:
            req = urllib.request.Request(
                base_url.rstrip("/") + "/api/generate",
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = __import__("json").loads(r.read().decode())
            out = str(data.get("response", "")).strip()
            if out:
                return out
        except Exception:
            continue
    return ""
