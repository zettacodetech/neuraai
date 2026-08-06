"""JSON2Video (api.json2video.com) — matndan to'liq haqiqiy MP4 video.

Env:
- JSON2VIDEO_API_KEY — majburiy
- GEN_OUT_DIR      — yuklab olinadigan fayllar papkasi (gen.py bilan birga)

Oqim: POST /v2/movies (scenes: sarlavha + matn) → project id → 3 soniyalik
poll (status: queued→running→done) → done bo'lgach movie.url (CDN MP4) yuklab
olamiz.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request

API_BASE = "https://api.json2video.com/v2"
API_KEY = os.environ.get("JSON2VIDEO_API_KEY", "").strip()
_USER_AGENT = "NeuraAI/1.0"

_RENDER_SECONDS = 3
_POLL_MAX_TRIES = 100  # ~5 daqiqa

_OUT_DIR = os.environ.get(
    "GEN_OUT_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "gen"),
)


def available() -> bool:
    return bool(API_KEY)


def _headers() -> dict[str, str]:
    return {
        "x-api-key": API_KEY,
        "Content-Type": "application/json",
        "User-Agent": _USER_AGENT,
    }


def _request(method: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        API_BASE + path,
        data=data,
        headers=_headers(),
        method=method,
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _clean_lines(prompt: str) -> list[str]:
    lines = [
        re.sub(r"[\r\n]+", " ", ln).strip()
        for ln in (prompt.splitlines() or [prompt])
        if ln.strip()
    ]
    return [ln[:90] for ln in lines][:6]


def generate_video(prompt: str) -> str | None:
    """Prompt'dan sarlavhali real MP4 video yaratadi, local path qaytaradi."""
    if not available():
        return None
    try:
        lines = _clean_lines(prompt)
        title = lines[0] if lines else "Neura AI"
        body = lines[1:] if len(lines) > 1 else []
        title_el = {
            "type": "text",
            "text": title,
            "style": "001",
            "size": {"x": 0.5, "y": 0.42, "width": 0.84, "height": 0.25},
            "properties": {"align": "center", "valign": "middle"},
        }
        scene: dict = {"duration": 4, "elements": [title_el]}
        if body:
            body_text = "\n".join(body)
            body_el = {
                "type": "text",
                "text": body_text,
                "style": "002",
                "size": {"x": 0.5, "y": 0.68, "width": 0.84, "height": 0.35},
                "properties": {"align": "center", "valign": "middle"},
            }
            scene["elements"].append(body_el)
        resp = _request(
            "POST",
            "/movies",
            {"resolution": "horizontal", "scenes": [scene]},
        )
        project = resp.get("project")
        if not project:
            return None
        for _ in range(_POLL_MAX_TRIES):
            time.sleep(_RENDER_SECONDS)
            try:
                info = _request("GET", f"/movies?project={project}")
            except Exception:
                continue
            movie = info.get("movie") or {}
            status = (movie.get("status") or "").lower()
            if status == "done":
                url = movie.get("url")
                if not url:
                    return None
                dest = os.path.join(
                    _OUT_DIR,
                    f"vid_j2v_{project}_{int(time.time() * 1000) % 100000}.mp4",
                )
                return _download(url, dest)
            if status in ("failed", "error"):
                raise RuntimeError(
                    f"JSON2Video generatsiyasi muvaffaqiyatsiz: {status}"
                )
        raise TimeoutError("JSON2Video generatsiyasi vaqtida tugamadi")
    except Exception:
        return None


def _download(url: str, dest: str) -> str | None:
    req = urllib.request.Request(
        url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json, */*"}
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            with open(dest, "wb") as f:
                f.write(resp.read())
        return dest
    except Exception:
        return None


__all__ = ["available", "generate_video"]
