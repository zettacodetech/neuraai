"""deAPI (api.deapi.ai) — arzon AI rasm/video generatsiyasi.

Env:
- DEAPI_API_KEY — majburiy (format: "user_id|token")
- GEN_OUT_DIR   — yuklab olinadigan fayllar papkasi (gen.py bilan birga)

Oqim: generatsiya job'ini yaratamiz → /api/v2/jobs/{id} ni poll qilamiz →
tayyor bo'lgach result_url (S3) ni yuklab local papkaga saqlaymiz.
Cloudflare himoyasi bor, shuning uchun hamma so'rovga browser User-Agent.
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.request

API_BASE = "https://api.deapi.ai"
API_KEY = os.environ.get("DEAPI_API_KEY", "").strip()
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

IMAGE_MODEL = os.environ.get("DEAPI_IMAGE_MODEL", "Flux1schnell")
VIDEO_MODEL = os.environ.get("DEAPI_VIDEO_MODEL", "Ltxv_13B_0_9_8_Distilled_FP8")

_POLL_SECONDS = 5
_POLL_MAX_TRIES = 60  # video uchun ~5 daqiqa

_OUT_DIR = os.environ.get(
    "GEN_OUT_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "gen"),
)


def available() -> bool:
    return bool(API_KEY)


def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


def _req(method: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        API_BASE + path,
        data=data,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _create(path: str, payload: dict) -> str | None:
    data = _req("POST", path, payload)
    return (data.get("data") or data).get("request_id")


def _poll(request_id: str) -> dict:
    for _ in range(_POLL_MAX_TRIES):
        try:
            data = _req("GET", f"/api/v2/jobs/{request_id}")
        except Exception:
            time.sleep(_POLL_SECONDS)
            continue
        info = data.get("data") or {}
        status = (info.get("status") or "").lower()
        if status == "done":
            return info
        if status in ("failed", "error"):
            raise RuntimeError(
                f"deAPI generatsiyasi muvaffaqiyatsiz: "
                f"{info.get('error_message') or status}"
            )
        time.sleep(_POLL_SECONDS)
    raise TimeoutError("deAPI generatsiyasi vaqtida tugamadi")


def _download(url: str, dest: str) -> str | None:
    """S3 signed URL ba'zida Authorization header'ni rad etadi (403/422),
    shuning uchun avval oddiy so'rov, keyin header bilan qayta urinamiz."""
    for hdrs in (
        {"User-Agent": _USER_AGENT},
        {"Authorization": f"Bearer {API_KEY}", "User-Agent": _USER_AGENT},
    ):
        req = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                with open(dest, "wb") as f:
                    f.write(resp.read())
            return dest
        except Exception as exc:
            import sys

            print(f"[deapi] download urinish muvaffaqiyatsiz: {exc}", flush=True)
            continue
    return None


def generate_image(prompt: str) -> str | None:
    """Haqiqiy AI rasm (FLUX.1 Schnell), local path qaytaradi."""
    if not available():
        return None
    try:
        request_id = _create(
            "/api/v2/images/generations",
            {
                "model": IMAGE_MODEL,
                "prompt": prompt,
                "width": 768,
                "height": 768,
                "steps": 4,
                "seed": _seed(prompt),
            },
        )
        if not request_id:
            return None
        info = _poll(request_id)
        url = info.get("result_url")
        if not url:
            return None
        dest = os.path.join(
            _OUT_DIR,
            f"img_de_{request_id[:8]}_{int(time.time() * 1000) % 100000}.png",
        )
        return _download(url, dest)
    except Exception as exc:
        import sys

        print(f"[deapi] download fail: {exc}", flush=True)
        return None


def generate_video(prompt: str) -> str | None:
    """Haqiqiy AI video (LTX-Video), local path qaytaradi."""
    if not available():
        return None
    try:
        request_id = _create(
            "/api/v2/videos/generations",
            {
                "model": VIDEO_MODEL,
                "prompt": prompt,
                "width": 720,
                "height": 720,
                "frames": 48,
                "fps": 30,
                "steps": 1,
                "seed": _seed(prompt),
            },
        )
        if not request_id:
            return None
        info = _poll(request_id)
        url = info.get("result_url")
        if not url:
            return None
        dest = os.path.join(
            _OUT_DIR,
            f"vid_de_{request_id[:8]}_{int(time.time() * 1000) % 100000}.mp4",
        )
        return _download(url, dest)
    except Exception as exc:
        import sys

        print(f"[deapi] download fail: {exc}", flush=True)
        return None


__all__ = ["available", "generate_image", "generate_video"]
