"""Kuchaytirilgan javoblar — OpenAI-compatible LLM (Groq, Z.AI va h.k.).

Yangi modullarga bog'liq emas (faqat stdlib urllib). Kalitlar env orqali:
- NEURA_LLM_API_KEY (yoki GROQ_API_KEY) — majburiy emas
- NEURA_LLM_BASE_URL  (standart: Groq)
- NEURA_LLM_MODEL     (standart: llama-3.3-70b-versatile)
"""

import json
import os
import urllib.request

LLM_BASE_URL = os.environ.get("NEURA_LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_API_KEY = (
    os.environ.get("NEURA_LLM_API_KEY", "").strip()
    or os.environ.get("GROQ_API_KEY", "").strip()
)
LLM_MODEL = os.environ.get("NEURA_LLM_MODEL", "llama-3.3-70b-versatile")
LLM_TIMEOUT = float(os.environ.get("NEURA_LLM_TIMEOUT", "25"))


def llm_available() -> bool:
    return bool(LLM_API_KEY)


def llm_chat(
    messages: list[dict],
    *,
    temperature: float = 0.4,
    max_tokens: int = 600,
) -> str | None:
    """OpenAI-compatible /chat/completions. Xatoda None (javob yozib bo'lmaydi)."""
    if not LLM_API_KEY:
        return None
    body = json.dumps(
        {
            "model": LLM_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        LLM_BASE_URL.rstrip("/") + "/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
    except Exception:
        return None
    if isinstance(content, str) and content.strip():
        return content.strip()
    return None


def llm_answer(
    message: str,
    history: list[dict] | None = None,
    context: str | None = None,
) -> str | None:
    """Foydalanuvchi savoliga LLM javobi — tarix va internet konteksti bilan."""
    if not LLM_API_KEY:
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
