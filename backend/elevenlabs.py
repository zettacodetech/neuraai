"""ElevenLabs integratsiyasi — matndi ovozga aylantirish (TTS, MP3).

Kalit: ELEVENLABS_API_KEY env.
Model: eleven_multilingual_v2 (o'zbek tilini qo'llab-quvvatlaydi).
"""

import os
import urllib.request
import urllib.error

API = "https://api.elevenlabs.io/v1"
_TIMEOUT = float(os.environ.get("ELEVENLABS_TIMEOUT", "60"))
_DEFAULT_VOICE = os.environ.get("ELEVENLABS_VOICE", "EXAVITQu4vr4xnSDxMaL")  # Rachel


def available() -> bool:
    return bool(os.environ.get("ELEVENLABS_API_KEY", "").strip())


def _headers() -> dict:
    return {
        "xi-api-key": os.environ.get("ELEVENLABS_API_KEY", "").strip(),
        "Content-Type": "application/json",
    }


def generate_voice(
    text: str, *, voice: str | None = None
) -> tuple[bytes | None, str | None]:
    """Matndi ovozga aylantiradi. (mp3 bytes, err) qaytaradi."""
    if not available():
        return None, "ELEVENLABS_API_KEY o'rnatilmagan"
    url = f"{API}/text-to-speech/{voice or _DEFAULT_VOICE}"
    payload = (
        '{"text":"'
        + text.replace("\\", "\\\\").replace('"', '\\"')
        + '","model_id":"eleven_multilingual_v2"}'
    ).encode()
    req = urllib.request.Request(url, data=payload, headers=_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            return r.read(), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as exc:
        return None, str(exc)
