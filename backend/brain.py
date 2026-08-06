"""AI miya — hech qanday tayyor model/API siz, 100% o'z kodingiz.

Faza 1 uchun:
- intent tanib olish (qoidalar asosida)
- bilim bazasidan javob topish (so'z o'xshashligi + IDF og'irligi)
- topilmasa — o'rganish navbatiga qo'yish
"""

import math
import os
import re

from coder import generate_code
from websearch import search_answer

STOP_WORDS = {
    "bu",
    "va",
    "da",
    "de",
    "ham",
    "bir",
    "bilan",
    "uchun",
    "kim",
    "nima",
    "qanday",
    "qanaqa",
    "nega",
    "nima",
    "uchun",
    "ha",
    "yoq",
    "yo'q",
    "men",
    "siz",
    "u",
    "ular",
    "biz",
    "bor",
    "kerak",
    "mumkin",
    "endi",
    "hammasi",
    "yana",
    "keyin",
    "avval",
    "aniq",
    "xuddi",
    "shu",
    "bu",
}

INTENTS = {
    "greeting": {
        "keywords": [
            "salom",
            "assalomu",
            "assalom",
            "alaykum",
            "vaalaykum",
            "hayrli",
            "xayrli",
            "good",
            "morning",
            "hello",
            "hi",
        ],
        "reply": "Assalomu alaykum! Men sizning sun'iy intellekt yordamchingizman. Qanday savol yoki topshiriq bor?",
    },
    "farewell": {
        "keywords": [
            "xayr",
            "hayr",
            "sog' bo'ling",
            "sog boling",
            "bye",
            "goodbye",
            "salamat",
            "keyinroq ko'rishamiz",
        ],
        "reply": "Xayr! Yana savol bo'lsa, kutilgan mehmonsiz. Har bir suhbat meni o'rganadi — keyingi safar yanada aqlliroq bo'laman.",
    },
    "thanks": {
        "keywords": [
            "rahmat",
            "tashakkur",
            "thanks",
            "thank",
            "o'xshaydi",
            "yordam berdingiz",
        ],
        "reply": "Arzimaydi! Sizning fikringiz meni rivojlantiradi. Yana boshqa savol bormi?",
    },
    "whoami": {
        "keywords": [
            "kim san",
            "kimsiz",
            "sen kimsan",
            "kim ekan",
            "who are you",
            "isming",
            "nom",
            "o'zingni tanishtir",
        ],
        "reply": "Men noldan qurilgan sun'iy intellektman — hech qanday tashqi xizmatdan foydalanmayman. Meni bilim bazasi va foydalanuvchilar bilan suhbatlarim o'rgatadi. Siz qancha ko'p gaplashsangiz, shuncha aqlli bo'laman!",
    },
    "help": {
        "keywords": [
            "yordam",
            "help",
            "qanday ishlayman",
            "nima qila olasan",
            "imkoniyat",
            "qobiliyat",
        ],
        "reply": "Men quyidagilarni qila olaman: suhbatlashish, savollarga javob berish, bilim bazasidan ma'lumot topish, internetdan izlash, kod yozish (python, js, sql, html), rasmni tahlil qilish, va har suhbatda sizdan o'rganish. Savolingizni yozing — javob berishga harakat qilaman!",
    },
    "age": {
        "keywords": [
            "necha yosh",
            "yoshingiz necha",
            "yoshing necha",
            "necha yoshda",
            "tug'ilgan",
            "tugilgan",
            "qachon yaratilgan",
            "qachon tug'ilgansan",
            "qachon tugilgansan",
        ],
        "reply": "Men 2026-yilda yaratilganman va har kuni foydalanuvchilar bilan suhbatlashib o'rganyapman — yoshim emas, bilimim oshmoqda.",
    },
    "joke": {
        "keywords": ["hazil", "kuldir", "latifa", "joke"],
        "reply": "Kompyuter nima uchun muzlab qoladi? Chunki u 'windoz'ga ochiq! 😄 Yana bir hazil aytishimni xohlaysizmi?",
    },
    "code": {
        "keywords": [
            "kod yoz",
            "kod yozib",
            "dastur yoz",
            "skript yoz",
            "code",
            "function yoz",
            "algoritm yoz",
            "bot yoz",
            "sayt yoz",
            "jadval yarat",
            "api yoz",
            "parol hash",
            "saralash",
        ],
        "reply": None,  # kod maxsus ishlov beriladi (coder.generate_code)
    },
}


SUFFIXES = (
    "ning",
    "lardan",
    "larga",
    "larda",
    "larni",
    "larning",
    "larim",
    "dan",
    "lar",
    "da",
    "ga",
    "ni",
)


class Brain:
    def __init__(self):
        self.doc_freq: dict[str, int] = {}

    # ---------- matnni tayyorlash ----------
    def _normalize(self, text: str) -> str:
        text = text.lower().strip().replace("'", "")
        text = re.sub(r"[^a-zа-яёўғҳқхжцчшщъыьэө0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def _stem(word: str) -> str:
        """O'zbekcha qo'shimchalarni olib tashlaydi: Toshkentda → Toshkent."""
        if len(word) <= 4:
            return word
        for s in SUFFIXES:
            if word.endswith(s) and len(word) - len(s) >= 3:
                return word[: -len(s)]
        return word

    def _tokens(self, text: str) -> list[str]:
        return [
            self._stem(t) for t in self._normalize(text).split() if t not in STOP_WORDS
        ]

    # ---------- intent ----------
    def _detect_intent(self, text: str) -> dict | None:
        norm = self._normalize(text)
        best, best_len = None, 0
        for name, cfg in INTENTS.items():
            hit = sum(1 for kw in cfg["keywords"] if kw in norm)
            if hit > best_len:
                best, best_len = name, hit
        if best and best_len >= 1:
            return {**INTENTS[best], "name": best}
        return None

    # ---------- IDF hisoblash (0 dan) ----------
    def _build_index(self, knowledge: list[dict]):
        self.doc_freq = {}
        for row in knowledge:
            for tok in set(self._tokens(row["question"])):
                self.doc_freq[tok] = self.doc_freq.get(tok, 0) + 1
        n = max(len(knowledge), 1)
        self.idf = {
            tok: math.log(n / (1 + freq)) + 1 for tok, freq in self.doc_freq.items()
        }

    def _score(self, q_tokens: list[str], doc_tokens: set[str]) -> float:
        score = 0.0
        for tok in q_tokens:
            if tok in doc_tokens:
                score += self.idf.get(tok, 1.0)
        overlap = len(set(q_tokens) & doc_tokens)
        coverage = overlap / max(len(q_tokens), 1)
        return score * (1.0 + coverage)

    # ---------- javob ----------
    def answer(
        self,
        message: str,
        knowledge: list[dict],
        history: list[dict] | None = None,
    ) -> tuple[str, str]:
        """(javob, source) — source: intent | code | knowledge | websearch | llm | fallback"""
        intent = self._detect_intent(message)
        if intent:
            if intent["name"] == "code":
                code = generate_code(message)
                if code:
                    return (
                        f"Kod tayyor:\n\n```\n{code}\n```\n\nSo'rovda noma'lum joylar bo'lsa, ularni o'zingizga moslab o'zgartiring. Yana boshqa narsa kerak bo'lsa — yozing!",
                        "code",
                    )
                return (
                    "Kod yozish uchun aniqroq yozing, masalan:\n"
                    "• 'telegram bot yoz'\n"
                    "• 'http so'rov yoz'\n"
                    "• 'jadval yarat' (SQL)\n"
                    "• 'saralash algoritmi yoz'\n"
                    "• 'parolni hash qilish'\n\n"
                    "Yoki kerakli kodni boshqa savol shaklida yozing!",
                    "code",
                )
            return intent["reply"], "intent"

        q_tokens = self._tokens(message)
        if not q_tokens:
            return (
                "Savolingizni aniqroq yozing, iltimos. Yordam kerak bo'lsa 'yordam' deb yozing.",
                "fallback",
            )

        best = self._retrieve(q_tokens, knowledge)
        if best and best[1] >= 2.0 and best[2] >= 0.4:
            return best[0]["answer"], "knowledge"

        # Kuchaytirilgan yo'l: internet (Serper/DDG) + LLM (OpenRouter/KIE/Groq)
        if os.environ.get("ENABLE_WEB_SEARCH", "1") == "1" and len(message) >= 10:
            web_answer, context = self._web_search(message)
            if context:
                llm_reply = self._llm(message, context=context, history=history)
                if llm_reply:
                    return llm_reply, "llm"
            if web_answer:
                return web_answer, "websearch"

        llm_reply = self._llm(message, history=history)
        if llm_reply:
            return llm_reply, "llm"
        return self._fallback(message), "fallback"

    def _web_search(self, message: str) -> tuple[str, str]:
        """(javob matni, LLM konteksti) — Serper bo'lmasa DDG."""
        has_serper = False
        serper_context_fn = None
        try:
            from serper import serper_available, serper_context

            if serper_available():
                has_serper = True
                serper_context_fn = serper_context
        except ImportError:
            pass

        if has_serper and serper_context_fn is not None:
            context = serper_context_fn(message)
            if context:
                return "", context
        answer = search_answer(message)
        return answer or "", answer or ""

    @staticmethod
    def _llm(
        message: str,
        context: str | None = None,
        history: list[dict] | None = None,
    ) -> str | None:
        try:
            from llm import llm_answer
        except ImportError:
            return None
        return llm_answer(message, history=history, context=context)

    def _retrieve(
        self, q_tokens: list[str], knowledge: list[dict]
    ) -> tuple[dict, float, float] | None:
        self._build_index(knowledge)
        best_row, best_score, best_cov = None, 0.0, 0.0
        for row in knowledge:
            doc_tokens = set(self._tokens(row["question"]))
            if not doc_tokens:
                continue
            score = self._score(q_tokens, doc_tokens) * row.get("weight", 1)
            coverage = len(set(q_tokens) & doc_tokens) / len(q_tokens)
            if score > best_score:
                best_row, best_score, best_cov = row, score, coverage
        if best_row:
            return best_row, best_score, best_cov
        return None

    @staticmethod
    def _fallback(message: str) -> str:
        return (
            "Bu savol bo'yicha ishonchli ma'lumotim yo'q. "
            "Savolingizni aniqroq yozing (masalan, qaysi davlat, yil yoki mavzu bo'yicha) "
            "yoki menga javobni o'rgatib yuboring — keyingi safar bilaman!"
        )


brain = Brain()
