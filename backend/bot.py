"""Telegram bot — Faza 2.

Ishga tushirish:
    TELEGRAM_BOT_TOKEN=... ./venv/bin/python bot.py

@BotFather dan token oling. Bot sayt bilan BIR xil DB va miyadan foydalanadi.
"""

import asyncio
import json
import logging
import os
import re
import tempfile
import threading

# .env faylini yuklash (tokenni repo'ga yozmaslik uchun)
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_ENV_PATH):
    with open(_ENV_PATH, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from auth import hash_password, new_token, verify_password

from brain import brain
from db import get_db
from gen import generate_image, generate_video
from vision import analyze as analyze_image

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Telegram foydalanuvchisi -> joriy suhbat id (xotira)
current_conv: dict[int, int] = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Deep link: t.me/InomjonAI_Bot?start=premium — to'lov oynasini ochadi
    payload = ""
    if context.args:
        payload = context.args[0]
    if payload.startswith("premium"):
        # Sayt/ilova/CLI'dan to'lovga kelganda — to'g'ridan rejalar
        db = get_db()
        user_id = db.get_or_create_user(telegram_id=update.effective_user.id)
        until = db.get_premium_until(user_id)
        tier = db.get_premium_plan(user_id)
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🚀 Go — 150 ⭐/oy", callback_data="premium:go_m"
                    ),
                    InlineKeyboardButton(
                        "🚀 Go — 1500 ⭐/yil", callback_data="premium:go_y"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "⚡ Pro — 400 ⭐/oy", callback_data="premium:pro_m"
                    ),
                    InlineKeyboardButton(
                        "⚡ Pro — 4000 ⭐/yil", callback_data="premium:pro_y"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "👑 Ultra — 1400 ⭐/oy", callback_data="premium:ultra_m"
                    ),
                    InlineKeyboardButton(
                        "👑 Ultra — 14000 ⭐/yil", callback_data="premium:ultra_y"
                    ),
                ],
            ]
        )
        await update.message.reply_text(
            TIERS_INFO + "\n\n" + f"Holat: <b>{_premium_text(until, tier)}</b>\n\n"
            "Rejani tanlang — to'lov Telegram Stars orqali:",
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💬 Suhbat", callback_data="menu:chat"),
                InlineKeyboardButton("🎨 Rasm yarat", callback_data="menu:gen"),
                InlineKeyboardButton("📷 Tahlil", callback_data="menu:photo"),
            ],
            [
                InlineKeyboardButton("🌐 Sayt", url="https://neuraai.up.railway.app"),
                InlineKeyboardButton(
                    "📲 APK",
                    url="https://github.com/zettacodetech/neuraai/releases/latest/download/neuraai.apk",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🌐 Web ilova",
                    web_app={"url": "https://neuraai.up.railway.app/webapp"},
                )
            ],
            [InlineKeyboardButton("🆕 Suhbatni yangilash", callback_data="menu:new")],
        ]
    )
    await update.message.reply_text(
        "👋 <b>Inomjon AI</b> — o'zbek tilidagi sun'iy intellekt yordamchingiz!\n\n"
        "🟣 Savol yozing — tabiiy javob beraman\n"
        "💻 <code>kod yoz</code> — dastur kodlayman\n"
        "📷 Rasm yuboring — tahlil qilaman\n"
        "🎨 <code>rasm yarat ...</code> — rasm chizaman\n"
        "🌐 Bilmaganimni internetdan qidiraman\n\n"
        "Yuqoridagi tugmalardan foydalanishing ham mumkin 👇",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 <b>Imkoniyatlar:</b>\n"
        "• Savol-javob, suhbat\n"
        "• 💻 Kod yozish (python, js, sql, html)\n"
        "• 📷 Rasm tahlili — rasm yuboring\n"
        "• 🌐 Internetdan javob izlash (ixcham xulosa)\n"
        "• 📈 Suhbatlardan o'rganish\n\n"
        "Buyruqlar:\n"
        "/new — yangi suhbat boshlash\n"
        "/webapp — 🌐 Web ilova (premium, profil, API kalit)\n"
        "/ibrat — 💫 Bugungi ibratli so'z\n"
        "/yangilik — 📰 Bugungi yangiliklar (Internetdan)\n"
        "/til — 🌐 Til tanlash (UZ/RU/EN)\n"
        "/help — ushbu yordam\n\n"
        "Javoblar 👍/👎 orqali meni o'rgatasiz!",
        parse_mode="HTML",
    )


async def ibrat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bugungi ibratli so'zni yuboradi."""
    await update.message.reply_text("💫 Ibrat izlanmoqda...")
    try:
        from llm import llm_chat

        soz = llm_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Sen motivatsion notiqsan. Bugungi ibratli so'zni o'zbek "
                        "tilida yoz: qisqa hikoya yoki hayotiy o'git + oxirida "
                        "bitta aniq maslahat. 4-6 qatordan oshmasin."
                    ),
                },
                {"role": "user", "content": "Bugungi ibratli so'zni yubor"},
            ],
            fast=True,
        )
    except Exception:
        soz = ""
    if not soz:
        soz = (
            "💫 <b>Bugungi ibrat:</b>\n\n"
            "Kichik qadamlar ham buyuk yo'lni boshlaydi. Bugun bitta "
            "ishni oxiriga yetkaz — ertaga ikkita bo'ladi."
        )
    await update.message.reply_text(soz, parse_mode="HTML")


async def yangilik_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bugungi yangiliklar — internetdan qidirib, ixcham xulosa beradi."""
    await update.message.reply_text("📰 Yangiliklar izlanmoqda...")
    try:
        from websearch import search_answer

        summary = search_answer(
            "bugungi eng muhim jahon va O'zbekiston yangiliklari", 4
        )
    except Exception:
        summary = ""
    if not summary:
        await update.message.reply_text(
            "📰 Yangiliklarni topa olmadim, keyinroq urinib ko'ring."
        )
        return
    await update.message.reply_text(
        f"📰 <b>Bugungi yangiliklar:</b>\n\n{summary[:2500]}",
        parse_mode="HTML",
    )


async def webapp_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🌐 Web ilovani ochish",
                    web_app={"url": "https://neuraai.up.railway.app/webapp"},
                )
            ]
        ]
    )
    await update.message.reply_text(
        "🌐 <b>Inomjon AI Web ilova</b>\n\n"
        "• 👑 Premium sotib olish (Stars)\n"
        "• 👤 Profil va statistika\n"
        "• 🔑 API kalitlar\n\n"
        "Quyidagi tugmani bosing — ilova ichida ochiladi 👇",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    current_conv.pop(uid, None)
    await update.message.reply_text(
        "✨ Yangi suhbat boshlanmoqda. Savolingizni yozing!"
    )


# ================= Ro'yxatdan o'tish / Login (sayt hisobi bilan bog'lash) =================
# Foydalanuvchi Telegram'da hisob yaratadi yoki mavjud sayt hisobiga kiradi.
# Shu bilan bir xil premium/to'lov, suhbatlar va API key ishlatiladi.
REG_USERNAME, REG_PASSWORD, LOGIN_USERNAME, LOGIN_PASSWORD = range(4)

_ME_URL = "https://neuraai.up.railway.app"


async def register_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db = get_db()
    user_id = db.get_or_create_user(telegram_id=update.effective_user.id)
    existing = db.get_user(user_id)
    if existing and existing.get("username") and existing.get("password_hash"):
        await update.message.reply_text(
            "📋 <b>Siz allaqachon ro'yxatdan o'tgansiz!</b>\n\n"
            f"Login: <code>{existing['username']}</code>\n\n"
            "Agar boshqa hisobga ulashmoqchi bo'lsangiz — <code>/login</code> yozing.\n"
            "Premium sotib olish — <code>/premium</code>.",
            parse_mode="HTML",
        )
        return ConversationHandler.END
    await update.message.reply_text(
        "📝 <b>Ro'yxatdan o'tish</b>\n\n"
        "Sayt (neuraai.up.railway.app) va barcha qurilmalarda ishlatiladigan "
        "bir xil hisob yaratiladi.\n\n"
        "Login (foydalanuvchi nomi) kiriting:\n"
        "• Harflar, raqamlar, <code>_</code> yoki <code>-</code>\n"
        "• 3-20 belgi\n\n"
        "Bekor qilish — <code>/cancel</code>",
        parse_mode="HTML",
    )
    return REG_USERNAME


async def reg_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    username = (update.message.text or "").strip().lower()
    if (
        not (3 <= len(username) <= 20)
        or not username.replace("_", "").replace("-", "").isalnum()
    ):
        await update.message.reply_text(
            "❌ Login noto'g'ri. Faqat harflar, raqamlar, _ yoki - ishlating (3-20 belgi)."
        )
        return REG_USERNAME
    db = get_db()
    exists = db.get_user_by_username(username)
    if exists:
        await update.message.reply_text(
            "❌ Bu login band. Boshqa login tanlang yoki mavjud hisobga kirmoqchi bo'lsangiz — <code>/login</code>."
        )
        return REG_USERNAME
    context.user_data["reg_username"] = username
    await update.message.reply_text(
        f"✅ Login: <code>{username}</code>\n\nEndi parol kiriting (kamida 4 belgi):",
        parse_mode="HTML",
    )
    return REG_PASSWORD


async def reg_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    password = (update.message.text or "").strip()
    if len(password) < 4:
        await update.message.reply_text(
            "❌ Parol kamida 4 belgi bo'lishi kerak. Qayta kiriting:"
        )
        return REG_PASSWORD
    username = context.user_data.get("reg_username")
    db = get_db()
    user_id = db.get_or_create_user(telegram_id=update.effective_user.id)
    user = db.get_user(user_id)
    if user and user.get("username"):
        await update.message.reply_text(
            "❌ Hisob allaqachon mavjud. <code>/login</code> dan foydalaning."
        )
        return ConversationHandler.END
    db._execute(
        "UPDATE users SET username = ?, password_hash = ?, name = ? WHERE id = ?",
        (
            username,
            hash_password(password),
            update.effective_user.username or username,
            user_id,
        ),
    )
    token = new_token()
    db.set_token(user_id, token)
    await update.message.reply_text(
        "🎉 <b>Ro'yxatdan o'tish muvaffaqiyatli!</b>\n\n"
        f"👤 Login: <code>{username}</code>\n"
        "✅ Endi saytga ham shu login/parol bilan kira olasiz: "
        "https://neuraai.up.railway.app/login\n\n"
        "Premium sotib olish — <code>/premium</code>",
        parse_mode="HTML",
    )
    context.user_data.pop("reg_username", None)
    return ConversationHandler.END


async def login_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🔑 <b>Sayt hisobiga kirish</b>\n\n"
        "Saytda ro'yxatdan o'tgan login (foydalanuvchi nomi) kiriting:\n\n"
        "Bekor qilish — <code>/cancel</code>",
        parse_mode="HTML",
    )
    return LOGIN_USERNAME


async def login_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    username = (update.message.text or "").strip().lower()
    db = get_db()
    user = db.get_user_by_username(username)
    if not user or not user.get("password_hash"):
        await update.message.reply_text(
            "❌ Bunday hisob topilmadi. Ro'yxatdan o'tish — <code>/register</code>, qayta urinish — <code>/login</code>."
        )
        return ConversationHandler.END
    context.user_data["login_username"] = username
    await update.message.reply_text(
        f"✅ Hisob topildi: <code>{username}</code>\n\nParolni kiriting:"
    )
    return LOGIN_PASSWORD


async def login_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    password = (update.message.text or "").strip()
    username = context.user_data.get("login_username")
    db = get_db()
    user = db.get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        await update.message.reply_text(
            "❌ Parol noto'g'ri. Qayta urinish — <code>/login</code>."
        )
        return ConversationHandler.END
    # Telegram ID'ni sayt hisobiga bog'lash (bitta to'lov/hisob hammasida)
    db.bind_telegram(user["id"], update.effective_user.id)
    token = new_token()
    db.set_token(user["id"], token)
    until = db.get_premium_until(user["id"])
    await update.message.reply_text(
        "✅ <b>Kirish muvaffaqiyatli!</b>\n\n"
        f"👤 <code>{username}</code>\n"
        f"👑 Premium: {_premium_text(until)}\n\n"
        "Endi sayt, ilova, CLI va bot'da bir xil hisob ishlatiladi.\n"
        "Premium sotib olish — <code>/premium</code>",
        parse_mode="HTML",
    )
    context.user_data.pop("login_username", None)
    return ConversationHandler.END


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("reg_username", None)
    context.user_data.pop("login_username", None)
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END


# ================= Premium / Telegram Stars to'lov =================
# 4 tarif: Free (bepul), Go, Pro, Ultra
# Har tarif OYLIK yoki YILLIK variantda.
# BONUS: 1 oy bepul — faqat Pro OYLIK tarifi uchun (400 ⭐ => 60 kun)
PLANS = {
    "go_m": {"title": "Go — 1 oy", "stars": 150, "days": 30, "tier": "go"},
    "go_y": {"title": "Go — 1 yil", "stars": 1500, "days": 365, "tier": "go"},
    "pro_m": {
        "title": "Pro — 1 oy (+1 oy bepul)",
        "stars": 400,
        "days": 60,
        "tier": "pro",
    },
    "pro_y": {"title": "Pro — 1 yil", "stars": 4000, "days": 365, "tier": "pro"},
    "ultra_m": {"title": "Ultra — 1 oy", "stars": 1400, "days": 30, "tier": "ultra"},
    "ultra_y": {
        "title": "Ultra — 1 yil",
        "stars": 14000,
        "days": 365,
        "tier": "ultra",
    },
}
TIER_STARS = {"go": 150, "pro": 400, "ultra": 1400}
TIER_DAYS = {"go": 30, "pro": 30, "ultra": 30}

STAR_CURRENCY = "XTR"

TIERS_INFO = (
    "👑 <b>Inomjon AI — Premium tariflar</b>\n\n"
    "🆓 <b>Free</b> — 0 ⭐\n"
    "• Asosiy suhbat va kod yozish\n"
    "• 10 ta rasm oyiga\n\n"
    "🚀 <b>Go</b> — 150 ⭐/oy | 1500 ⭐/yil\n"
    "• Tez model (fast)\n"
    "• 100 ta rasm oyiga\n\n"
    "⚡ <b>Pro</b> — 400 ⭐/oy | 4000 ⭐/yil\n"
    "• Cheksiz rasm, video, musiqa\n"
    "• Kengaytirilgan internet qidiruv\n"
    "🎁 <i>Oylik: 1 oy bepul!</i>\n\n"
    "👑 <b>Ultra</b> — 1400 ⭐/oy | 14000 ⭐/yil\n"
    "• Eng kuchli model + hammasi"
)


def _premium_text(until: str | None, tier: str = "free") -> str:
    if not until:
        return "Tarif: Free (bepul)."
    label = {"go": "Go", "pro": "Pro", "ultra": "Ultra"}.get(tier, "Premium")
    return f"Tarif: <b>{label}</b> — {until[:10]} gacha."


async def premium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = get_db()
    user_id = db.get_or_create_user(telegram_id=update.effective_user.id)
    until = db.get_premium_until(user_id)
    tier = db.get_premium_plan(user_id)
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"🚀 Go — 150 ⭐/oy", callback_data="premium:go_m"
                ),
                InlineKeyboardButton(
                    f"🚀 Go — 1500 ⭐/yil", callback_data="premium:go_y"
                ),
            ],
            [
                InlineKeyboardButton(
                    "⚡ Pro — 400 ⭐/oy", callback_data="premium:pro_m"
                ),
                InlineKeyboardButton(
                    "⚡ Pro — 4000 ⭐/yil", callback_data="premium:pro_y"
                ),
            ],
            [
                InlineKeyboardButton(
                    "👑 Ultra — 1400 ⭐/oy", callback_data="premium:ultra_m"
                ),
                InlineKeyboardButton(
                    "👑 Ultra — 14000 ⭐/yil", callback_data="premium:ultra_y"
                ),
            ],
        ]
    )
    await update.message.reply_text(
        TIERS_INFO + "\n\n" + f"Holat: <b>{_premium_text(until, tier)}</b>\n\n"
        "Rejani tanlang — to'lov Telegram Stars orqali:",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def premium_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not query.data.startswith("premium:"):
        return
    plan_key = query.data.split(":", 1)[1]
    plan = PLANS.get(plan_key)
    if not plan:
        await query.message.reply_text("Noma'lum reja. /premium qayta bosing.")
        return

    chat_id = query.message.chat_id
    prices = [LabeledPrice("Premium", plan["stars"])]
    try:
        await context.bot.send_invoice(
            chat_id=chat_id,
            title=plan["title"],
            description=f"Inomjon AI Premium — {plan['title']}. "
            "To'lov Telegram Stars orqali amalga oshiriladi.",
            payload=f"premium:{plan_key}",
            provider_token="",
            currency=STAR_CURRENCY,
            prices=prices,
        )
    except Exception as e:
        logging.error("Stars invoice yuborilmadi: %s", e)
        await query.message.reply_text(
            f"❌ Invoice yuborilmadi. Bot @BotFather → Payments da "
            f"Stars yoqilganini tekshiring.\nXato: {e}"
        )


async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.pre_checkout_query
    payload = query.invoice_payload or ""
    plan_key = payload.split(":", 1)[1] if payload.startswith("premium:") else ""
    if plan_key not in PLANS:
        await query.answer(ok=False, error_message="Noma'lum reja")
        return
    await query.answer(ok=True)


async def successful_payment(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    payment = update.message.successful_payment
    payload = payment.invoice_payload or ""
    plan_key = ""
    paid_tg_id = update.effective_user.id if update.effective_user else None
    if payload.startswith("premium:"):
        plan_key = payload.split(":", 1)[1]
    else:
        # WebApp (createInvoiceLink) dan kelgan JSON payload
        try:
            data = json.loads(payload)
            plan_key = str(data.get("premium") or "")
            if data.get("tg_id"):
                paid_tg_id = int(data["tg_id"])
        except Exception:
            pass
    plan = PLANS.get(plan_key)
    if not plan:
        await update.message.reply_text("To'lov qabul qilindi, lekin reja tanlanmadi.")
        return
    db = get_db()
    user_id = db.get_or_create_user(telegram_id=paid_tg_id)
    until = db.add_premium_days(user_id, plan["days"], plan=plan["tier"])
    db.add_payment(
        user_id,
        amount=payment.total_amount,
        plan=plan["title"],
        payload=payload,
        provider="stars",
    )
    await update.message.reply_text(
        f"🎉 <b>To'lov muvaffaqiyatli!</b>\n\n"
        f"👑 {plan['title']} faollashtirildi!\n"
        f"📅 Premium <b>{until[:10]}</b> gacha amal qiladi.\n\n"
        "Endi barcha imkoniyatlar ochiq — foydalaning! 🚀",
        parse_mode="HTML",
    )
    logging.info(
        "Stars to'lov: user=%s plan=%s stars=%s",
        user_id,
        plan["title"],
        payment.total_amount,
    )


async def on_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ovozli xabarni matnga aylantirib (Whisper) AI javob beradi."""
    tg_id = update.effective_user.id
    db0 = get_db()
    uid0 = db0.get_or_create_user(telegram_id=tg_id)
    await update.message.reply_text(_t(uid0, "voice_working"))
    try:
        file = await update.message.voice.get_file()
        raw = await file.download_as_bytearray()
        path = tempfile.mktemp(suffix=".ogg")
        with open(path, "wb") as f:
            f.write(raw)
        try:
            text = _transcribe(path)
        finally:
            os.unlink(path)
    except Exception as e:
        await update.message.reply_text(f"Ovozni yuklab ololmadim: {e}")
        return

    if not text:
        await update.message.reply_text(_t(uid0, "voice_fail"))
        return

    await update.message.reply_text(
        _t(uid0, "voice_said", text=text), parse_mode="HTML"
    )
    await _answer_message(update, context, text, source_note="🎤")


def _transcribe(path: str, timeout: float = 60.0) -> str:
    """Ovozli faylni matnga aylantiradi (Groq Whisper, fallback: lokal)."""
    import urllib.error
    import urllib.request

    api_key = (
        os.environ.get("GROQ_API_KEY", "").strip()
        or os.environ.get("NEURA_LLM_API_KEY", "").strip()
    )
    if api_key:
        boundary = "----neuraboundary"
        import uuid

        bnd = uuid.uuid4().hex
        with open(path, "rb") as f:
            audio = f.read()
        body = (
            f"--{bnd}\r\n"
            'Content-Disposition: form-data; name="file"; filename="voice.ogg"\r\n'
            "Content-Type: audio/ogg\r\n\r\n"
        ).encode()
        body += audio
        body += (
            f"\r\n--{bnd}\r\n"
            'Content-Disposition: form-data; name="model"\r\n\r\n'
            "whisper-large-v3\r\n"
            f"--{bnd}--\r\n"
        ).encode()
        try:
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                data=body,
                method="POST",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": f"multipart/form-data; boundary={bnd}",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
            return str(data.get("text", "")).strip()
        except Exception as exc:
            logging.warning("Groq STT xato: %s", exc)
    try:
        import whisper_local  # noqa

        return whisper_local.transcribe(path)
    except Exception:
        return ""


async def _answer_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    source_note: str = "",
    voice_mode: bool = False,
) -> None:
    """Umumiy javob berish (matn / ovoz / guruh uchun)."""
    tg_id = update.effective_user.id
    db = get_db()
    user_id = db.get_or_create_user(telegram_id=tg_id)

    plan = db.get_premium_plan(user_id)
    if not db.is_premium(user_id):
        plan = "free"
    limit = {"free": 20, "go": 100, "pro": 500}.get(plan, 0)
    if limit > 0:
        used = db.daily_usage(user_id)
        if used >= limit:
            await update.message.reply_text(
                _t(user_id, "limit", used=used, limit=limit, plan=plan),
                parse_mode="HTML",
            )
            return

    conv_id = current_conv.get(tg_id)
    if conv_id is not None:
        conv = db.get_conversation(conv_id)
        if not conv or conv["user_id"] != user_id:
            conv_id = None
    if conv_id is None:
        convs = db.list_conversations(user_id)
        conv_id = convs[0]["id"] if convs else db.create_conversation(user_id, text)

    db.add_message(user_id, "user", text, conversation_id=conv_id)
    reply, source = brain.answer(text, db.get_knowledge())
    msg_id = db.add_message(
        user_id, "assistant", reply, source=source, conversation_id=conv_id
    )
    if source == "fallback":
        db.add_unanswered(text, user_id)
    try:
        db.bump_daily_usage(user_id)
    except Exception:
        pass

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👍", callback_data=f"rate:{msg_id}:1"),
                InlineKeyboardButton("👎", callback_data=f"rate:{msg_id}:-1"),
            ]
        ]
    )
    if voice_mode:
        try:
            await update.message.reply_text("🗣 Ovoz tayyorlanmoqda...")
            import pollinations

            data, err = None, "no-voice"
            try:
                import elevenlabs

                if elevenlabs.available():
                    data, err = elevenlabs.generate_voice(reply)
            except Exception:
                pass
            if not data and pollinations.available():
                data, err = pollinations.generate_audio(reply)
            if data:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    f.write(data)
                    tmp = f.name
                try:
                    with open(tmp, "rb") as f:
                        await update.message.reply_voice(f)
                finally:
                    os.unlink(tmp)
                await update.message.reply_text(reply)
            else:
                await update.message.reply_text(reply)
        except Exception as e:
            logging.warning("Ovoz yuborilolmadi (%s); matn yuborildi", e)
            await update.message.reply_text(reply, reply_markup=kb)
        return
    await update.message.reply_text(reply, reply_markup=kb)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Matnli xabarga javob berish (rasm/video/ovoz buyruqlari ham shu yerda)."""
    tg_id = update.effective_user.id
    text = update.message.text.strip()
    if not text:
        return

    low = text.lower()
    voice_mode = text.startswith(("voice:", "ovoz:", "🗣", "🎤"))
    if voice_mode:
        text = (
            text.split(":", 1)[1].strip() if ":" in text else text.lstrip("🗣🎤").strip()
        )
        low = text.lower()
    if any(
        k in low for k in ("rasm yarat", "rasm chiz", "logotip yarat", "suret yarat")
    ):
        await update.message.reply_text("🎨 Rasm tayyorlanmoqda...")
        try:
            path = generate_image(text)
            with open(path, "rb") as f:
                await update.message.reply_photo(f, caption=f"🎨 {text[:80]}")
        except Exception as e:
            await update.message.reply_text(f"Rasm yarata olmadim: {e}")
        return
    if any(k in low for k in ("video yarat", "video tayorla", "animatsiya yarat")):
        await update.message.reply_text("🎬 Video tayyorlanmoqda...")
        try:
            path = generate_video(text)
            with open(path, "rb") as f:
                await update.message.reply_video(f, caption=f"🎬 {text[:80]}")
        except Exception as e:
            await update.message.reply_text(f"Video yarata olmadim: {e}")
        return

    await _answer_message(update, context, text, voice_mode=voice_mode)


async def on_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guruh rejimi: @Inomjonai_bot mention qilinsa javob beradi."""
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    low = text.lower()
    me = (update.effective_user.username or "").lower()
    if me and me in low:
        text = low.replace(me, "").strip()
    if not text or not any(
        k in low for k in ("inomjonai_bot", "@inomjon", "ai assistant", "neuraai")
    ):
        return
    text = re.sub(r"@inomjonai_bot", "", text, flags=re.IGNORECASE).strip()
    if not text:
        text = "salom"
    await update.message.reply_text(
        "🤖 <b>NeuraAI:</b> javob tayyorlanmoqda...", parse_mode="HTML"
    )
    try:
        db = get_db()
        user_id = db.get_or_create_user(telegram_id=update.effective_user.id)
        conv_id = db.create_conversation(user_id, "👥 Guruh")
        db.add_message(user_id, "user", text, conversation_id=conv_id)
        reply, source = brain.answer(text, db.get_knowledge())
        db.add_message(
            user_id, "assistant", reply, source=source, conversation_id=conv_id
        )
        if len(reply) > 4000:
            reply = reply[:4000] + "..."
        await update.message.reply_text(reply, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Xatolik: {e}")


_STRINGS = {
    "limit": {
        "uz": "⛔ Kunlik limit tugadi ({used}/{limit} so'rov).\n\nTarifingiz: <b>{plan}</b>\nLimitni oshirish — <code>/premium</code> (Go/Pro/Ultra).",
        "ru": "⛔ Дневной лимит исчерпан ({used}/{limit} запросов).\n\nТариф: <b>{plan}</b>\nУвеличить лимит — <code>/premium</code> (Go/Pro/Ultra).",
        "en": "⛔ Daily limit reached ({used}/{limit} requests).\n\nPlan: <b>{plan}</b>\nUpgrade — <code>/premium</code> (Go/Pro/Ultra).",
    },
    "voice_working": {
        "uz": "🎤 Eshitayapman... (matnga aylantirilmoqda)",
        "ru": "🎤 Слушаю... (преобразование в текст)",
        "en": "🎤 Listening... (converting to text)",
    },
    "voice_fail": {
        "uz": "Ovozli xabarni tushunolmadim. Yana bir bor, aniqroq gapiring yoki matn yozing.",
        "ru": "Не удалось распознать голос. Повторите чётче или напишите текстом.",
        "en": "Couldn't understand the voice. Try again more clearly or type.",
    },
    "voice_said": {
        "uz": "📝 <b>Siz aytdingiz:</b> {text}",
        "ru": "📝 <b>Вы сказали:</b> {text}",
        "en": "📝 <b>You said:</b> {text}",
    },
    "lang_changed": {
        "uz": "✅ Til o'zgartirildi: O'zbekcha",
        "ru": "✅ Язык изменён: Русский",
        "en": "✅ Language changed: English",
    },
}


def _t(user_id: int, key: str, **kw) -> str:
    """Foydalanuvchi tiliga qarab matn qaytaradi (uz/ru/en)."""
    try:
        lang = get_db().get_settings(user_id).get("lang", "uz")
    except Exception:
        lang = "uz"
    s = _STRINGS.get(key, {}).get(lang) or _STRINGS.get(key, {}).get("uz", key)
    if kw:
        try:
            s = s.format(**kw)
        except Exception:
            pass
    return s


async def lang_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Til tanlash tugmalari."""
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang:uz"),
                InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
            ],
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang:en")],
        ]
    )
    await update.message.reply_text(
        "🌐 <b>Tilni tanlang / Выберите язык / Choose language:</b>",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("lang:"):
        lang = data.split(":", 1)[1]
        if lang in ("uz", "ru", "en"):
            uid = update.effective_user.id
            db = get_db()
            user_id = db.get_or_create_user(telegram_id=uid)
            cur = db.get_settings(user_id)
            db.set_settings(user_id, lang, cur.get("theme", "dark"))
            names = {"uz": "O'zbekcha", "ru": "Русский", "en": "English"}
            await query.edit_message_text(
                f"✅ <b>{names.get(lang, lang)}</b> tanlandi!",
                parse_mode="HTML",
            )
        return
    if data.startswith("menu:"):
        action = data.split(":", 1)[1]
        uid = update.effective_user.id
        if action == "new":
            current_conv.pop(uid, None)
            await query.edit_message_text(
                "✨ <b>Yangi suhbat</b> boshlanmoqda.\nSavolingizni yozing!",
                parse_mode="HTML",
            )
        elif action == "gen":
            await query.edit_message_text(
                "🎨 <b>Rasm yaratish</b>\n\n"
                "Yozing, masalan:\n"
                "<code>rasm yarat: o'rmonda quyosh botishi</code>\n\n"
                "Endi oddiygina istakni yozing — avtomatik aniqlayman.",
                parse_mode="HTML",
            )
        elif action == "photo":
            await query.edit_message_text(
                "📷 <b>Rasm tahlili</b>\n\n"
                "Rasm yuboring — format, ranglar, yorug'lik va boshqa ma'lumotlarni tahlil qilaman.",
                parse_mode="HTML",
            )
        return

    parts = data.split(":")
    if len(parts) == 3 and parts[0] == "rate":
        db = get_db()
        db.rate_message(int(parts[1]), int(parts[2]))
        await query.edit_message_reply_markup(reply_markup=None)
        await query.edit_message_text(
            query.message.text
            + ("\n\n✅ Rahmat! Bu javob meni o'rgatadi." if parts[2] == "1" else "")
        )
        return

    # --- Rasm: internetdan topish / tarjima / tahrirlash ---
    if (
        len(parts) == 3
        and parts[0] == "img"
        and parts[1]
        in (
            "search",
            "translate",
            "retro",
            "upscale",
        )
    ):
        action, file_id = parts[1], parts[2]
        await query.edit_message_text("⏳ Iltimos kuting...")
        try:
            file = await context.bot.get_file(file_id)
            raw = await file.download_as_bytearray()
            path = tempfile.mktemp(suffix=".jpg")
            with open(path, "wb") as f:
                f.write(raw)
            try:
                if action == "search":
                    await _img_web_search(query, path)
                elif action == "translate":
                    await _img_translate(query, path)
                else:
                    await _img_edit(query, path, action)
            finally:
                os.unlink(path)
        except Exception as e:
            await query.edit_message_text(f"Xatolik yuz berdi: {e}")
        return


async def _img_web_search(query, path: str) -> None:
    """Rasmdagi narsani internetdan topib beradi (AI tasvirlash + Google qidiruv)."""
    from vision import describe as vision_describe

    desc = vision_describe(path)
    if not desc:
        await query.edit_message_text(
            "Rasmni tahlil qila olmadim, qidiruv bajarilmadi."
        )
        return
    from websearch import search_answer

    await query.edit_message_text(
        f"🔍 <b>Internetdan qidirilmoqda...</b>\n\n📝 <b>Rasmda:</b> {desc[:300]}...",
        parse_mode="HTML",
    )
    summary = search_answer(desc[:300])
    if not summary:
        await query.edit_message_text(
            f"🤖 <b>Rasmda nima bor:</b>\n\n{desc[:2000]}\n\n"
            "❌ Internetdan ma'lumot topilmadi.",
            parse_mode="HTML",
        )
        return
    await query.edit_message_text(
        f"🌐 <b>Internetdan topilgan ma'lumot:</b>\n\n{summary[:2500]}",
        parse_mode="HTML",
    )


async def _img_translate(query, path: str) -> None:
    """Rasmdagi matnni o'zbek tiliga tarjima qiladi."""
    from vision import ocr as vision_ocr

    ocr_text = vision_ocr(path)
    if not ocr_text:
        await query.edit_message_text("Rasmda matn topilmadi.")
        return
    try:
        from llm import llm_chat

        result = llm_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Sen professional tarjimonsan. Quyidagi matnni o'zbek "
                        "tiliga tarjima qil. Asl ma'noni saqlab, tabiiy tarjima "
                        "qil. Faqat tarjima matnini qaytar."
                    ),
                },
                {"role": "user", "content": ocr_text[:2000]},
            ],
            fast=True,
        )
    except Exception:
        result = ""
    if not result or result == ocr_text.strip():
        result = ocr_text
    await query.edit_message_text(
        f"📝 <b>Asl matn:</b>\n{ocr_text[:1000]}\n\n"
        f"🇺🇿 <b>O'zbekcha tarjima:</b>\n{result[:2000]}",
        parse_mode="HTML",
    )


async def _img_edit(query, path: str, action: str) -> None:
    """Rasmni tahrirlaydi: retro | upscale va natijani yuboradi."""
    from vision import edit_image

    dest = tempfile.mktemp(suffix=".png")
    try:
        ok = edit_image(path, dest, action)
        if not ok:
            await query.edit_message_text("Rasmni tahrirlay olmadim.")
            return
        with open(dest, "rb") as f:
            await query.message.reply_photo(
                f,
                caption="🖼 Retro uslubda!"
                if action == "retro"
                else "🔍 Kattalashtirildi!",
            )
        await query.edit_message_text("✅ Tayyor! Tahrirlangan rasm yuqorida.")
    except Exception as e:
        await query.edit_message_text(f"Xatolik: {e}")
    finally:
        try:
            os.unlink(dest)
        except OSError:
            pass


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rasm tahlili: format/ranglar + OCR (matn o'qish) + AI tasvirlash + tarjima + qidiruv."""
    file = await update.message.photo[-1].get_file()
    file_id = file.file_id
    raw = await file.download_as_bytearray()
    path = tempfile.mktemp(suffix=".jpg")
    with open(path, "wb") as f:
        f.write(raw)

    text = ""
    ocr_text = ""
    try:
        data = analyze_image(path)
        lines = [
            "📷 <b>Rasm tahlili:</b>",
            f"• Format: {data['format']}, {data['width']}×{data['height']}",
            f"• Yorug'lik: {data['brightness']}",
            "• Asosiy ranglar: "
            + ", ".join(f"{c['name']} ({c['percent']}%)" for c in data["colors"]),
            f"• {data['unique_colors']} xil rang",
            "• Bu fotografiya" if data["photo_like"] else "• Bu kompyuter grafikasi",
        ]
        exif = data["exif"]
        if exif.get("DateTimeOriginal"):
            lines.append(f"• Sana: {exif['DateTimeOriginal']}")
        text = "\n".join(lines)

        # OCR: suratdagi matnni o'qish
        try:
            from vision import ocr as vision_ocr

            ocr_text = vision_ocr(path)
            if ocr_text:
                text += "\n\n📝 <b>Suratdagi matn:</b>\n" + ocr_text[:1500]
        except Exception:
            pass

        # AI to'liq tasvirlash: rasmda nima bor
        try:
            from vision import describe as vision_describe

            desc = vision_describe(path)
            if desc:
                text += "\n\n🤖 <b>AI tasvirlashi:</b>\n" + desc[:2000]
        except Exception:
            pass
    except Exception as e:
        await update.message.reply_text(f"Rasmni tahlil qila olmadim: {e}")
        return
    finally:
        os.unlink(path)

    db = get_db()
    user_id = db.get_or_create_user(telegram_id=update.effective_user.id)
    conv_id = current_conv.get(update.effective_user.id)
    if conv_id is not None:
        conv = db.get_conversation(conv_id)
        if not conv or conv["user_id"] != user_id:
            conv_id = None
    if conv_id is None:
        conv_id = db.create_conversation(user_id, "📷 Rasm tahlili")
    db.add_message(user_id, "user", "📷 Rasm yubordi", conversation_id=conv_id)
    db.add_message(user_id, "assistant", text, source="vision", conversation_id=conv_id)

    buttons = [
        InlineKeyboardButton(
            "🌐 Internetdan topish", callback_data=f"img:search:{file_id}"
        )
    ]
    if ocr_text:
        buttons.append(
            InlineKeyboardButton("🔄 Tarjima", callback_data=f"img:translate:{file_id}")
        )
    buttons2 = [
        InlineKeyboardButton("🖼 Retro", callback_data=f"img:retro:{file_id}"),
        InlineKeyboardButton(
            "🔍 Kattalashtirish", callback_data=f"img:upscale:{file_id}"
        ),
    ]
    kb = InlineKeyboardMarkup([buttons, buttons2])
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fayl tahlili: PDF/DOCX/TXT — matn ajratib, AI'ga savol berish mumkin."""
    doc = update.message.document
    name = (doc.file_name or "hujjat").lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext not in ("pdf", "docx", "doc", "txt", "md"):
        await update.message.reply_text(
            "Faqat PDF, DOCX, TXT, MD fayllarni qabul qilaman!"
        )
        return
    await update.message.reply_text(
        f"📄 <b>{doc.file_name}</b> o'qilmoqda...", parse_mode="HTML"
    )
    try:
        file = await doc.get_file()
        raw = await file.download_as_bytearray()
        import io

        text = ""
        if ext in ("pdf",):
            import pypdf

            reader = pypdf.PdfReader(io.BytesIO(bytes(raw)))
            text = "\n\n".join(p.extract_text() or "" for p in reader.pages)
        elif ext in ("docx", "doc"):
            import docx as docxlib

            docxobj = docxlib.Document(io.BytesIO(bytes(raw)))
            text = "\n".join(p.text for p in docxobj.paragraphs)
        else:
            for enc in ("utf-8", "windows-1251", "utf-16"):
                try:
                    text = bytes(raw).decode(enc)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
        text = (text or "").strip()
        if not text:
            await update.message.reply_text(
                "Faylda matn topilmadi (skanerlangan PDF bo'lishi mumkin)."
            )
            return

        db = get_db()
        user_id = db.get_or_create_user(telegram_id=update.effective_user.id)
        conv_id = current_conv.get(update.effective_user.id)
        if conv_id is not None:
            conv = db.get_conversation(conv_id)
            if not conv or conv["user_id"] != user_id:
                conv_id = None
        if conv_id is None:
            conv_id = db.create_conversation(user_id, f"📄 {doc.file_name}")

        summary = text[:3000]
        if len(text) > 3000:
            summary += "\n...[fayl uzun, to'liq matn saqlandi]"
        db.add_message(
            user_id, "user", f"📄 Fayl: {doc.file_name}", conversation_id=conv_id
        )
        db.add_message(
            user_id,
            "assistant",
            f"📄 <b>{doc.file_name}</b> yuklandi ({len(text)} ta belgi).\n\n"
            f"<b>Xulosa:</b>\n{summary}",
            source="document",
            conversation_id=conv_id,
        )
        reply = (
            f"📄 <b>{doc.file_name}</b> yuklandi — {len(text)} ta belgi.\n\n"
            f"<b>Matn boshi:</b>\n{summary}"
        )
        if len(reply) > 4000:
            reply = reply[:4000] + "..."
        await update.message.reply_text(reply, parse_mode="HTML")
    except Exception as e:
        logging.warning("Fayl tahlili xato: %s", e)
        await update.message.reply_text(f"Faylni o'qiy olmadim: {e}")


def _build_app() -> Application:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("webapp", webapp_cmd))
    app.add_handler(CommandHandler("new", new_chat))
    app.add_handler(CommandHandler("premium", premium_cmd))
    app.add_handler(CommandHandler("pay", premium_cmd))
    app.add_handler(CommandHandler("ibrat", ibrat_cmd))
    app.add_handler(CommandHandler("yangilik", yangilik_cmd))
    app.add_handler(CommandHandler("til", lang_cmd))
    app.add_handler(CommandHandler("lang", lang_cmd))
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("register", register_cmd)],
            states={
                REG_USERNAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, reg_username)
                ],
                REG_PASSWORD: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, reg_password)
                ],
            },
            fallbacks=[CommandHandler("cancel", cancel_cmd)],
        )
    )
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("login", login_cmd)],
            states={
                LOGIN_USERNAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, login_username)
                ],
                LOGIN_PASSWORD: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, login_password)
                ],
            },
            fallbacks=[CommandHandler("cancel", cancel_cmd)],
        )
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
            on_group_message,
        )
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_handler(MessageHandler(filters.VOICE, on_voice))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.Document, on_document))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(CallbackQueryHandler(premium_callback, pattern=r"^premium:"))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    _schedule_reminders(app)
    return app


async def _remind_premium(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Premium muddati yaqinlashgan userlarga eslatma yuboradi (har 6 soat)."""
    try:
        from db import get_db

        db = get_db()
        for days in (3, 1):
            for entry in db.users_expiring_soon(days):
                uid = entry["id"]
                kind = f"expiry:{days}"
                if db.notification_sent(uid, kind):
                    continue
                tid = entry.get("telegram_id")
                if not tid:
                    continue
                text = (
                    f"⏳ <b>Premium muddati tugashiga {days} kun qoldi!</b>\n\n"
                    f"Hisobingiz {days} kundan keyin Free rejimiga o'tadi.\n"
                    "Tarifni yangilash uchun: @Inomjonai_bot ichida /premium yoki "
                    "saytdagi 'Premium' tugmasi orqali to'lash mumkin."
                )
                try:
                    await context.bot.send_message(
                        chat_id=tid, text=text, parse_mode="HTML"
                    )
                    db.mark_notification(uid, kind)
                except Exception as exc:
                    logging.warning("Eslatma yuborilmadi (%s): %s", tid, exc)
    except Exception as exc:
        logging.warning("Eslatma job xato: %s", exc)


async def _send_scheduled(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rejalashtirilgan xabarlarni (saytda yaratilgan) vaqti kelganda yuboradi."""
    try:
        from db import get_db

        db = get_db()
        from datetime import datetime

        now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M")
        for entry in db.due_scheduled(now_iso):
            sched_id = entry["id"]
            user = db.get_user(entry["user_id"])
            tid = (user or {}).get("telegram_id")
            text = entry.get("text", "")
            at = entry.get("send_at", "")
            try:
                if tid:
                    await context.bot.send_message(
                        chat_id=tid,
                        text=(f"⏰ <b>Rejalashtirilgan xabar ({at})</b>\n\n{text}"),
                        parse_mode="HTML",
                    )
                db.mark_scheduled_sent(sched_id)
            except Exception as exc:
                logging.warning(
                    "Rejalashtirilgan xabar yuborilmadi (%s): %s", sched_id, exc
                )
    except Exception as exc:
        logging.warning("Rejalashtirilgan xabar job xato: %s", exc)


def _schedule_reminders(app: Application) -> None:
    """Har 6 soatda premium eslatma + har daqiqada rejalashtirilgan xabar job'lari."""
    try:
        app.job_queue.run_repeating(_remind_premium, interval=6 * 3600, first=3600)
        app.job_queue.run_repeating(_send_scheduled, interval=60, first=30)
        logging.info("Premium eslatma va rejalashtirilgan xabar job'lari ishga tushdi")
    except Exception as exc:
        logging.warning("Eslatma job yaratilmadi: %s", exc)


def start_bot_in_thread() -> None:
    """FastAPI (Railway) ichida botni alohida thread'da ishga tushiradi."""
    if not TOKEN:
        logging.warning("TELEGRAM_BOT_TOKEN o'rnatilmagan — bot ishga tushmaydi")
        return

    def _run() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            logging.info("Inomjon AI bot ishga tushdi (thread)")
            _build_app().run_polling(stop_signals=None)
        except Exception as exc:
            logging.error("Bot to'xtadi: %s", exc)
        finally:
            try:
                loop.close()
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True, name="telegram-bot").start()


def main() -> None:
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN muhit o'zgaruvchisi kerak!")
    logging.info("Inomjon AI bot ishga tushdi")
    _build_app().run_polling()


if __name__ == "__main__":
    main()
