"""Magic Hour (magichour.ai) — haqiqiy AI rasm/video generatsiyasi.

Env:
- MAGIC_HOUR_API_KEY — majburiy (live token)
- GEN_OUT_DIR       — yuklab olinadigan fayllar papkasi (gen.py bilan birga)

Oqim: loyiha yaratamiz → holatini poll qilamiz → chiqish URL'ini yuklab
olamiz va local papkaga saqlaymiz (fastapi /generated orqali xizmat qiladi).
"""

import json
import os
import time
import urllib.error
import urllib.request

API_BASE = "https://api.magichour.ai/v1"
API_KEY = os.environ.get("MAGIC_HOUR_API_KEY", "").strip()
_POLL_SECONDS = 4
_POLL_MAX_TRIES = 40  # ~160s gacha

_OUT_DIR = os.environ.get(
    "GEN_OUT_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "gen"),
)


def available() -> bool:
    return bool(API_KEY)


def _headers() -> dict[str, str]:
    return {
        "accept": "application/json",
        "authorization": f"Bearer {API_KEY}",
        "content-type": "application/json",
    }


def _post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        API_BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(path: str) -> dict:
    req = urllib.request.Request(API_BASE + path, headers=_headers(), method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download(url: str, dest: str) -> str | None:
    req = urllib.request.Request(
        url,
        headers={
            "accept": "application/json",
            "authorization": f"Bearer {API_KEY}",
            "User-Agent": "NeuraAI/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
    except urllib.error.HTTPError:
        # ba'zi output URL'lar bepul (signed S3)
        req = urllib.request.Request(url, headers={"User-Agent": "NeuraAI/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
        except Exception:
            return None
    with open(dest, "wb") as f:
        f.write(data)
    return dest


def _poll(kind: str, project_id: str) -> dict:
    """kind: image | video — loyiha tugashini kutadi, holatni qaytaradi."""
    detail_path = f"/v1/{kind}-projects/{project_id}"
    for _ in range(_POLL_MAX_TRIES):
        try:
            data = _get(detail_path)
        except Exception:
            time.sleep(_POLL_SECONDS)
            continue
        status = (data.get("status") or "").lower()
        if status == "completed":
            return data
        if status in ("failed", "cancelled", "error"):
            raise RuntimeError(
                f"Magic Hour {kind} generatsiyasi muvaffaqiyatsiz: {status}"
            )
        time.sleep(_POLL_SECONDS)
    raise TimeoutError("Magic Hour generatsiyasi vaqtida tugamadi")


def _first_output(data: dict) -> str | None:
    outputs = data.get("outputs") or []
    if not outputs:
        return None
    first = outputs[0]
    if isinstance(first, str):
        return first
    return first.get("url") or first.get("link")


def generate_image(prompt: str) -> str | None:
    """Haqiqiy AI rasm yaratadi (ai-image-generator), local path qaytaradi."""
    project = _post(
        "/v1/ai-image-generator",
        {
            "name": "Neura AI image",
            "image_count": 1,
            "model": "default",
            "aspect_ratio": "1:1",
            "resolution": "auto",
            "style": {"prompt": prompt, "tool": "ai-anime-generator"},
        },
    )
    project_id = project.get("id")
    if not project_id:
        return None
    data = _poll("image", project_id)
    url = _first_output(data)
    if not url:
        return None
    ts = int(time.time() * 1000)
    dest = os.path.join(_OUT_DIR, f"img_mh_{project_id}_{ts % 100000}.png")
    return _download(url, dest)


def generate_video(prompt: str, end_seconds: int = 5) -> str | None:
    """Haqiqiy AI video yaratadi (text-to-video), local path qaytaradi."""
    project = _post(
        "/v1/text-to-video",
        {
            "name": "Neura AI video",
            "end_seconds": end_seconds,
            "model": "kling-3.0",
            "resolution": "720p",
            "style": {"prompt": prompt},
        },
    )
    project_id = project.get("id")
    if not project_id:
        return None
    data = _poll("video", project_id)
    url = _first_output(data)
    if not url:
        return None
    ts = int(time.time() * 1000)
    dest = os.path.join(_OUT_DIR, f"vid_mh_{project_id}_{ts % 100000}.mp4")
    return _download(url, dest)
