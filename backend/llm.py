"""Kuchaytirilgan javoblar — OpenAI-compatible LLM (Groq, OpenRouter, KIE va h.k.).

Yangi modullarga bog'liq emas (faqat stdlib urllib). Kalitlar env orqali:
- NEURA_LLM_API_KEY (yoki GROQ_API_KEY) — majburiy emas
- NEURA_LLM_BASE_URL  (standart: Groq)
- NEURA_LLM_MODEL     (standart: llama-3.3-70b-versatile)
- OPENROUTER_API_KEY  — OpenRouter qo'shimcha provider (kuchli modellar, kam kredit)
- OPENROUTER_MODEL    (standart: ~openai/gpt-latest)
- KIE_API_KEY         — kie.ai agregatori (arzon, OpenAI-compatible, deepseek-chat)
- KIE_API_KEY_2       — kie.ai ikkinchi kalit (zaxira)

Provider tartibi: NEURA_LLM_PROVIDER env orqali tanlanadi (groq | openrouter | kie | auto).
'auto' da: OpenRouter → KIE → Groq (kuchlidan arzonga zanjir).
"""

import json
import os
import urllib.request

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
KIE_BASE_URL = "https://api.kie.ai/api/v1"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_OPENROUTER_MODEL = "~openai/gpt-latest"
DEFAULT_KIE_MODEL = "deepseek-chat"

LLM_TIMEOUT = float(os.environ.get("NEURA_LLM_TIMEOUT", "25"))

# OpenRouter kreditlari kam bo'lgani uchun chiqish tokenlarini cheklaymiz.
OPENROUTER_MAX_TOKENS = int(os.environ.get("OPENROUTER_MAX_TOKENS", "450"))


class _Provider:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    @property
    def available(self) -> bool:
        return bool(self.api_key.strip())


def _build_providers() -> list[_Provider]:
    providers: list[_Provider] = []

    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        providers.append(
            _Provider(
                OPENROUTER_BASE_URL,
                openrouter_key,
                os.environ.get("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL),
            )
        )

    for env_name in ("KIE_API_KEY", "KIE_API_KEY_2"):
        kie_key = os.environ.get(env_name, "").strip()
        if kie_key:
            providers.append(_Provider(KIE_BASE_URL, kie_key, DEFAULT_KIE_MODEL))

    groq_key = (
        os.environ.get("NEURA_LLM_API_KEY", "").strip()
        or os.environ.get("GROQ_API_KEY", "").strip()
    )
    if groq_key:
        providers.append(
            _Provider(
                os.environ.get("NEURA_LLM_BASE_URL", GROQ_BASE_URL),
                groq_key,
                os.environ.get("NEURA_LLM_MODEL", DEFAULT_GROQ_MODEL),
            )
        )

    mode = os.environ.get("NEURA_LLM_PROVIDER", "auto").strip().lower()
    if mode == "groq":
        providers.sort(key=lambda p: p.base_url != GROQ_BASE_URL)
    elif mode == "openrouter":
        providers.sort(key=lambda p: p.base_url == GROQ_BASE_URL)
    elif mode == "kie":
        providers.sort(
            key=lambda p: (p.base_url == GROQ_BASE_URL, p.base_url != KIE_BASE_URL)
        )
    # auto: OpenRouter → KIE → Groq (kuchlisi birinchi)
    return providers


LLM_PROVIDERS = _build_providers()


def llm_available() -> bool:
    return any(p.available for p in LLM_PROVIDERS)


def llm_chat(
    messages: list[dict],
    *,
    temperature: float = 0.4,
    max_tokens: int = 600,
) -> str | None:
    """OpenAI-compatible /chat/completions — providerlar bo'ylab zanjir. Xatoda None."""
    if not LLM_PROVIDERS:
        return None
    last_error: Exception | None = None
    for provider in LLM_PROVIDERS:
        if not provider.available:
            continue
        limit = (
            min(max_tokens, OPENROUTER_MAX_TOKENS)
            if OPENROUTER_BASE_URL in provider.base_url
            else max_tokens
        )
        body = json.dumps(
            {
                "model": provider.model,
                "messages": messages,
                "temperature": temperature,
                "max_completion_tokens": limit,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            provider.base_url.rstrip("/") + "/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {provider.api_key}",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, str) and content.strip():
                return content.strip()
            return None
        except Exception as exc:  # keyingi providerga o'tamiz
            last_error = exc
            continue
    return None


def llm_answer(
    message: str,
    history: list[dict] | None = None,
    context: str | None = None,
) -> str | None:
    """Foydalanuvchi savoliga LLM javobi — tarix va internet konteksti bilan."""
    if not llm_available():
        return None
    system = (
        "Siz Neura AI yordamchisiz. O'zbek tilida (lotin yozuvida) sodda, ishonchli "
        "va hurmatli javob bering. Javob 3-5 qisqa jumla bo'lsin. Faktni bilmasangiz, "
        "o'ylab topmang — shunchaki bilmasligingizni ayting."
    )
    if context:
        system += (
            "\n\nInternetdan topilgan ma'lumotlar (javobda aynan shulardan foydalaning, "
            "manbani keltirmasdan):\n" + context
        )
    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history[-6:])
    messages.append({"role": "user", "content": message})
    return llm_chat(messages)


__all__ = ["llm_available", "llm_chat", "llm_answer"]
