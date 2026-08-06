"""Internet qidiruv — API kaliti shart emas (DuckDuckGo HTML).

Qidiruv natijasini AI o'zi qayta ishlaydi: snippetlardan eng muhim
jumlalarni ajratib, ixcham javob tuzadi — to'liq nusxa ko'chirmaydi.
"""

import html as html_lib
import re
import time
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"[a-zа-яёўғҳқхжцчшщъыьэө0-9]{3,}")
_SENT_RE = re.compile(r"(?<=[.!?])\s+")
_BOILERPLATE = re.compile(
    r"^(wikipedia|cookie|biz |yandex|google|reklama|advertisement|this (website|site))",
    re.I,
)


class DDGResult:
    def __init__(self, title: str = "", url: str = "", snippet: str = ""):
        self.title = title
        self.url = url
        self.snippet = snippet

    def __repr__(self) -> str:
        return f"<DDGResult {self.title!r}>"


def _clean(raw: str) -> str:
    raw = _TAG_RE.sub(" ", raw)
    raw = html_lib.unescape(raw)
    return _SPACE_RE.sub(" ", raw).strip()


def _unwrap(url: str) -> str:
    """DDG redirect URL dan haqiqiy manbani ajratadi."""
    q = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(q.query)
    if "uddg" in params:
        return params["uddg"][0]
    if url.startswith("//"):
        return "https:" + url
    return url


def web_search(query: str, max_results: int = 5) -> list[DDGResult]:
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=12) as resp:
        raw = resp.read().decode("utf-8", "ignore")

    results: list[DDGResult] = []
    titles = re.findall(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', raw, re.S)
    hrefs = re.findall(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"', raw, re.S)
    snippets = re.findall(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', raw, re.S)

    for i in range(min(len(titles), len(snippets), max_results)):
        href = hrefs[i] if i < len(hrefs) else ""
        results.append(
            DDGResult(
                title=_clean(titles[i]),
                url=_unwrap(href),
                snippet=_clean(snippets[i]),
            )
        )
    return results


def _sentences(text: str) -> list[str]:
    return [p.strip() for p in _SENT_RE.split(text) if len(p.strip()) >= 15]


def _summarize(
    query: str, results: list[DDGResult], max_sentences: int = 3, max_chars: int = 420
) -> str:
    """Snippetlardan eng mos, takrorlanmagan jumlalarni yig'adi — ixcham xulosa."""
    q_words = set(_WORD_RE.findall(query.lower()))
    seen: set[str] = set()
    scored: list[tuple[int, int, str]] = []

    for r in results:
        if not r.snippet:
            continue
        for s in _sentences(r.snippet):
            key = re.sub(r"\W", "", s.lower())[:40]
            if key in seen:
                continue
            seen.add(key)
            words = set(_WORD_RE.findall(s.lower()))
            hits = len(words & q_words)
            if s.endswith("?"):
                hits -= 1
            if _BOILERPLATE.match(s) and hits == 0:
                continue
            scored.append((hits, -len(s), s))

    scored.sort(reverse=True)
    chosen: list[str] = []
    total = 0
    for _, _, s in scored:
        if total + len(s) > max_chars:
            continue
        chosen.append(s)
        total += len(s)
        if len(chosen) >= max_sentences:
            break
    return " ".join(chosen)


_cache: dict[str, tuple[float, str | None]] = {}
CACHE_TTL = 3600  # 1 soat


def search_answer(query: str, max_results: int = 3) -> str | None:
    """Savol bo'yicha internetdan IXCHAM javob tuzadi. Topilmasa None.

    Manba snippetini to'liq ko'chirmaydi — faqat eng muhim jumlalarni
    qayta ishlangan, ixcham shaklda beradi. Natija 1 soat keshlanadi
    (DuckDuckGo limitlaridan himoya).
    """
    now = time.time()
    hit = _cache.get(query)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]

    answer = None
    for attempt in (0, 1):  # bitta qayta urinish (limit tushib qolsa)
        try:
            results = web_search(query, max_results)
            if results:
                break
        except Exception:
            results = []
            time.sleep(2)
    if results:
        summary = _summarize(query, results)
        if not summary:
            top = results[0]
            if top.snippet:
                summary = _clean(top.snippet)[:420]
        if summary:
            if summary[-1] not in ".!?":
                summary += "."
            top = results[0]
            answer = f"Internetdan qidirib topdim:\n\n{summary}\n\nManba: {top.url}"

    _cache[query] = (now, answer)
    return answer
