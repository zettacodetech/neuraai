"""Pollinations.ai integratsiyasi — rasm, video, audio (TTS/musiqa).

Base: https://gen.pollinations.ai  (turi Open, kalit enter.pollinations.ai dan olinadi)
Kalit: POLLINATIONS_API_KEY env.
Bepul rejimda (kalitsiz) logolangan kichik output; kalit bilan 402 qaytsa
protsur/см. fallback ishlatiladi.
"""

import os
import time
import urllib.parse
import urllib.request

BASE = "https://gen.pollinations.ai"
_TIMEOUT = float(os.environ.get("POLLINATIONS_TIMEOUT", "90"))
_IMG_MODEL = os.environ.get("POLLINATIONS_IMAGE_MODEL", "flux")
_VID_MODEL = os.environ.get("POLLINATIONS_VIDEO_MODEL", "wan")
_AUD_MODEL = os.environ.get("POLLINATIONS_AUDIO_MODEL", "elevenlabs")
_MUS_MODEL = os.environ.get("POLLINATIONS_MUSIC_MODEL", "elevenmusic")
_VOICE = os.environ.get("POLLINATIONS_VOICE", "af_heart")


def available() -> bool:
    """Kalit mavjud bo'lsa — urinib ko'ramiz. HTTP 402 (balance yo'q) bo'lsa None."""
    return bool(os.environ.get("POLLINATIONS_API_KEY", "").strip())


def _headers() -> dict:
    key = os.environ.get("POLLINATIONS_API_KEY", "").strip()
    return {
        "Authorization": "Bearer " + key,
        "User-Agent": "NeuraAI/1.1 (referrer=neuraai)",
    }


def _get(url: str) -> tuple[bytes | None, str | None]:
    """GET so'rov — muvaffaqiyat: (bytes, None). Xato: (None, 'masalan: 402 balans')."""
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            data = r.read()
            ctype = r.headers.get("Content-Type", "")
            if "json" in ctype:
                return None, "JSON javob"
            return data, None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as exc:
        return None, str(exc)


def generate_image(
    prompt: str, *, width: int = 1024, height: int = 1024, model: str | None = None
) -> bytes | None:
    """Rasm yaratish (WebP/PNG bytes qaytaradi)."""
    url = (
        f"{BASE}/image/{urllib.parse.quote(prompt, safe='')}"
        f"?model={model or _IMG_MODEL}&width={width}&height={height}"
        f"&seed={int(time.time() * 1000) % 1000000}&nologo=true&referrer=neuraai"
    )
    data, err = _get(url)
    if data is None:
        return None
    return data


def generate_video(prompt: str, *, model: str | None = None) -> bytes | None:
    """Video generatsiya (MP4). Pollinations video bir necha soniya davom etadi."""
    url = (
        f"{BASE}/video/{urllib.parse.quote(prompt, safe='')}"
        f"?model={model or _VID_MODEL}&nologo=true&referrer=neuraai"
    )
    data, err = _get(url)
    if data is None:
        return None
    return data


def generate_audio(
    text: str,
    *,
    voice: str | None = None,
    model: str | None = None,
) -> bytes | None:
    """Matndi ovozga aylantiradi (TTS). WAV/MP3 bytes qaytaradi."""
    url = (
        f"{BASE}/audio/{urllib.parse.quote(text, safe='')}"
        f"?model={model or _AUD_MODEL}&voice={voice or _VOICE}&referrer=neuraai"
    )
    data, err = _get(url)
    if data is None:
        return None
    return data


def generate_music(prompt: str, *, model: str | None = None) -> bytes | None:
    """Qo'shiq/musiqa generatsiya (elevenmusic). WAV/MP3 qaytaradi."""
    return generate_audio(prompt, voice=None, model=model or _MUS_MODEL)
