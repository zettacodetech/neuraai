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
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_OPENROUTER_MODEL = "~openai/gpt-latest"
DEFAULT_KIE_MODEL = "deepseek-chat"
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"

# Mavjud Gemini modellar (Google API da) — eng kuchlisi birinchi:
# https://ai.google.dev/gemini-api/docs/models/gemini
GEMINI_MODELS = [
    "gemini-1.5-pro",  # Eng kuchli, murakkab vazifalar uchun
    "gemini-1.5-pro-002",  # Yangilangan Pro (sentyabr 2024)
    "gemini-1.5-flash",  # Tez va arzon, ko'pgina vazifalar uchun
    "gemini-1.5-flash-002",  # Yangilangan Flash
    "gemini-1.0-pro",  # Eski avlod Pro
    "gemini-1.0-pro-vision",  # Multimodal (rasm+matn) — eski
]


def _resolve_gemini_model(name: str) -> str:
    """Foydalanuvchi kiritgan nomi ro'yxatda bo'lmasa, default qaytaradi."""
    if not name:
        return DEFAULT_GEMINI_MODEL
    if name in GEMINI_MODELS:
        return name
    for m in GEMINI_MODELS:
        if name.lower() in m.lower() or m.lower() in name.lower():
            return m
    return DEFAULT_GEMINI_MODEL


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


class _GeminiProvider:
    """Google Generative Language API — format OpenAI-compatible emas."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    @property
    def available(self) -> bool:
        return bool(self.api_key.strip())

    def chat(
        self, messages: list[dict], temperature: float = 0.4, max_tokens: int = 600
    ) -> str | None:
        # Gemini format: contents[{role, parts[{text}]}]
        contents = []
        for m in messages:
            role = "user" if m["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        url = (
            f"{GEMINI_BASE_URL}/models/{self.model}:generateContent?key={self.api_key}"
        )
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as r:
                data = json.loads(r.read().decode())
            cand = data.get("candidates", [{}])[0]
            return cand.get("content", {}).get("parts", [{}])[0].get("text")
        except Exception:
            return None


class _OllamaProvider:
    """Lokal Ollama server (API key kerak emas). Vision ham qo'llab-quvvatlanadi."""

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = base_url or os.environ.get(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.3:8b")

    @property
    def available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as r:
                return r.status == 200
        except Exception:
            return False

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.4,
        max_tokens: int = 600,
        images: list[str] | None = None,
    ) -> str | None:
        # Ollama format: messages + images (base64)
        ollama_messages = []
        for m in messages:
            content = m["content"]
            role = m["role"]
            if role == "system":
                ollama_messages.append({"role": "system", "content": content})
            elif role == "user":
                msg = {"role": "user", "content": content}
                if images:
                    msg["images"] = images
                ollama_messages.append(msg)
            else:
                ollama_messages.append({"role": "assistant", "content": content})

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        url = f"{self.base_url}/api/chat"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as r:
                data = json.loads(r.read().decode())
            return data.get("message", {}).get("content")
        except Exception:
            return None


class _DuckDuckGoProvider:
    """DuckDuckGo AI Chat — API key kerak emas, GPT-4o-mini / Claude-3-haiku."""

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model  # gpt-4o-mini, claude-3-haiku, llama-3.1-70b, mixtral-8x7b

    @property
    def available(self) -> bool:
        return True  # Hechqachon o'chmaydi

    def chat(
        self, messages: list[dict], temperature: float = 0.4, max_tokens: int = 600
    ) -> str | None:
        # DuckDuckGo AI Chat HTML scraping / hidden API
        # Bu soddalashtirilgan — real implementatsiya uchun DDG tokenlari kerak
        # Hozircha placeholder — oddiyroq: hech narsa qilmaymiz, None qaytarib keyingi providerga o'tamiz
        return None


def _build_providers() -> list:
    providers: list = []

    # 1. DuckDuckGo (bepul, API key kerak emas) — birinchi urinish
    ddg_model = os.environ.get("DDG_MODEL", "gpt-4o-mini")
    providers.append(_DuckDuckGoProvider(ddg_model))

    # 2. OpenRouter
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        providers.append(
            _Provider(
                OPENROUTER_BASE_URL,
                openrouter_key,
                os.environ.get("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL),
            )
        )

    # 3. KIE
    for env_name in ("KIE_API_KEY", "KIE_API_KEY_2"):
        kie_key = os.environ.get(env_name, "").strip()
        if kie_key:
            providers.append(_Provider(KIE_BASE_URL, kie_key, DEFAULT_KIE_MODEL))

    # 4. Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
        providers.append(
            _GeminiProvider(
                gemini_key,
                _resolve_gemini_model(os.environ.get("GEMINI_MODEL", "")),
            )
        )

    # 5. Ollama (lokal, API key kerak emas, vision qo'llab-quvvatlanadi)
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.3:8b")
    providers.append(_OllamaProvider(ollama_url, ollama_model))

    # 6. Groq
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
        providers.sort(key=lambda p: getattr(p, "base_url", "") != OPENROUTER_BASE_URL)
    elif mode == "kie":
        providers.sort(
            key=lambda p: (p.base_url == GROQ_BASE_URL, p.base_url != KIE_BASE_URL)
        )
    elif mode == "gemini":
        providers.sort(key=lambda p: not isinstance(p, _GeminiProvider))
    elif mode == "ollama":
        providers.sort(key=lambda p: not isinstance(p, _OllamaProvider))
    elif mode == "duckduckgo":
        providers.sort(key=lambda p: not isinstance(p, _DuckDuckGoProvider))
    # auto: DuckDuckGo → OpenRouter → KIE → Gemini → Ollama → Groq
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
    """Providerlar bo'ylab zanjir — xatoda keyingi prov qiladi, bari yiqilsa None."""
    if not LLM_PROVIDERS:
        return None
    last_error: Exception | None = None
    for provider in LLM_PROVIDERS:
        if not provider.available:
            continue
        try:
            if hasattr(provider, "chat") and callable(provider.chat):
                # Ollama / Gemini / DDG — o'z API formatiga ega
                content = provider.chat(
                    messages, temperature=temperature, max_tokens=max_tokens
                )
            else:
                # OpenAI-compatible /chat/completions
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
