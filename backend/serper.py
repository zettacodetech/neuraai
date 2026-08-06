"""Serper.dev — Google real-time qidiruv (API kaliti bilan).

Kalit: SERPER_API_KEY env. Kalit bo'lmasa yoki xato bo'lsa — bo'sh natija,
DDG fallback ishlatiladi (websearch.py).
"""

import json
import os
import urllib.request

SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "").strip()
SERPER_URL = "https://google.serper.dev/search"


def serper_available() -> bool:
    return bool(SERPER_API_KEY)


def serper_search(query: str, max_results: int = 5) -> list[dict]:
    """Google natijalari: [{title, link, snippet}]."""
    if not SERPER_API_KEY:
        return []
    body = json.dumps({"q": query, "num": max_results}).encode("utf-8")
    req = urllib.request.Request(
        SERPER_URL,
        data=body,
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []
    out = []
    for item in data.get("organic", [])[:max_results]:
        out.append(
            {
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            }
        )
    return out


def serper_context(query: str) -> str:
    """Natijalarni LLM kontekstga tayyor matnga aylantiradi (bo'sh bo'lishi mumkin)."""
    results = serper_search(query)
    lines = []
    for r in results:
        parts = [p for p in (r["title"], r["snippet"], r["link"]) if p]
        if parts:
            lines.append("- " + " — ".join(parts))
    return "\n".join(lines)


__all__ = ["serper_available", "serper_search", "serper_context"]
