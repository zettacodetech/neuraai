"""LLM dvigatel adapteri — backend logikasini yagona nuqtadan ulaydi.

Birinchi versiyada `backend.brain` va `backend.llm` to'g'ridan ishlatiladi;
kelajakda HTTP API'ga o'tish kerak bo'lsa, faqat shu modul o'zgaradi:

    def chat_reply(message, model=None):
        resp = requests.post(f"{BASE_URL}/api/chat", json={...})
        return resp.json()["reply"], resp.json().get("source")

Yangi buyruq backend xizmatidan foydalanmoqchi bo'lsa, funksiyani
shu joyga qo'shing (masalan: `translate()`, `summarize()` va h.k.).
"""

from __future__ import annotations

from brain import brain
from db import get_db
from llm import llm_chat

_CHAT_HISTORY: list[dict] = []


def chat_reply(message: str, model: str | None = None) -> tuple[str, str]:
    """Suhbat javobi: (reply, source). source — 'intent|code|knowledge|llm|fallback'."""
    reply, source = brain.answer(
        message,
        get_db().get_knowledge(),
        history=_CHAT_HISTORY or None,
        model=model,
    )
    _CHAT_HISTORY.append({"role": "user", "content": message})
    _CHAT_HISTORY.append({"role": "assistant", "content": reply})
    return reply, source


def clear_history() -> None:
    """Suhbat tarixini tozalaydi (yangi suhbat boshlash uchun)."""
    _CHAT_HISTORY.clear()


def fix_code(code: str, filename: str, model: str | None = None) -> str | None:
    """Fayl tarkibini LLM'ga yuborib, tuzatilgan kodni qaytaradi.

    Bu yerda LLM bevosita chaqiriladi — `brain` ni ishlatmaymiz,
    chunki tuzatish "so'z" javob emas, kod kutiladi.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "Sen kuchli dasturchi yordamchisisan. "
                "Berilgan fayl kodini tahlil qil va unchalik yaxshi "
                "bo'lmagan joylarini tuzat. Javobda FAQAT to'liq "
                "tuzatilgan kodni ``` bloki ichida yoz, izohlar va "
                "boshqa matnsiz."
            ),
        },
        {
            "role": "user",
            "content": f"# Fayl: {filename}\n\n```\n{code}\n```",
        },
    ]
    return llm_chat(messages, max_tokens=2500, model=model)
