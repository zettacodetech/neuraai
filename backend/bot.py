"""Telegram bot — Faza 2.

Ishga tushirish:
    TELEGRAM_BOT_TOKEN=... ./venv/bin/python bot.py

@BotFather dan token oling. Bot sayt bilan BIR xil DB va miyadan foydalanadi.
"""

import asyncio
import json
import logging
import os
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
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⭐ 1 oy — 150 ⭐", callback_data="premium:1m")],
                [InlineKeyboardButton("⭐ 3 oy — 400 ⭐", callback_data="premium:3m")],
                [
                    InlineKeyboardButton(
                        "⭐ 12 oy — 1400 ⭐", callback_data="premium:12m"
                    )
                ],
            ]
        )
        await update.message.reply_text(
            "👑 <b>Inomjon AI Premium</b>\n\n"
            "⭐ 1 oy — 150 ⭐\n⭐ 3 oy — 400 ⭐\n⭐ 12 oy — 1400 ⭐\n\n"
            f"Holat: <b>{_premium_text(until)}</b>\n\n"
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
        "/help — ushbu yordam\n\n"
        "Javoblar 👍/👎 orqali meni o'rgatasiz!",
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
# Rejalar (Telegram Stars):
#   1 oy  — 150 ⭐
#   3 oy  — 400 ⭐ (oyiga ~133)
#   12 oy — 1400 ⭐ (oyiga ~117)
PLANS = {
    "1m": {"title": "1 oy Premium", "stars": 150, "days": 30},
    "3m": {"title": "3 oy Premium", "stars": 400, "days": 90},
    "12m": {"title": "12 oy Premium", "stars": 1400, "days": 365},
}

STAR_CURRENCY = "XTR"


def _premium_text(until: str | None) -> str:
    if not until:
        return "Premium yoqilmagan."
    return f"Premium faol — {until[:10]} gacha."


async def premium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = get_db()
    user_id = db.get_or_create_user(telegram_id=update.effective_user.id)
    until = db.get_premium_until(user_id)
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"⭐ 1 oy — {PLANS['1m']['stars']} ⭐",
                    callback_data="premium:1m",
                )
            ],
            [
                InlineKeyboardButton(
                    f"⭐ 3 oy — {PLANS['3m']['stars']} ⭐ (o'yiga arzon)",
                    callback_data="premium:3m",
                )
            ],
            [
                InlineKeyboardButton(
                    f"⭐ 12 oy — {PLANS['12m']['stars']} ⭐ (eng qulay)",
                    callback_data="premium:12m",
                )
            ],
        ]
    )
    await update.message.reply_text(
        "👑 <b>Inomjon AI Premium</b>\n\n"
        "⭐ 1 oy — 150 ⭐\n"
        "⭐ 3 oy — 400 ⭐\n"
        "⭐ 12 oy — 1400 ⭐\n\n"
        f"Holat: <b>{_premium_text(until)}</b>\n\n"
        "Premium imkoniyatlari:\n"
        "• 🚀 Tez va kuchli model (LLM)\n"
        "• 🎨 Cheksiz rasm yaratish\n"
        "• 🎬 Video / musiqa yaratish\n"
        "• 🌐 Kengaytirilgan internet qidiruv\n\n"
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
    until = db.add_premium_days(user_id, plan["days"])
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


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id
    text = update.message.text.strip()
    if not text:
        return

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

    db = get_db()
    user_id = db.get_or_create_user(telegram_id=tg_id)

    # joriy suhbat: xotiradan yoki oxirgisidan
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

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👍", callback_data=f"rate:{msg_id}:1"),
                InlineKeyboardButton("👎", callback_data=f"rate:{msg_id}:-1"),
            ]
        ]
    )
    await update.message.reply_text(reply, reply_markup=kb)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
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


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Faza 4: rasm tahlili — format, ranglar, yorug'lik va boshqa ma'lumotlar."""
    file = await update.message.photo[-1].get_file()
    raw = await file.download_as_bytearray()
    path = tempfile.mktemp(suffix=".jpg")
    with open(path, "wb") as f:
        f.write(raw)
    try:
        data = analyze_image(path)
    except Exception as e:
        await update.message.reply_text(f"Rasmni tahlil qila olmadim: {e}")
    else:
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
        db.add_message(
            user_id, "assistant", text, source="vision", conversation_id=conv_id
        )

        await update.message.reply_text(text, parse_mode="HTML")
    finally:
        os.unlink(path)


def _build_app() -> Application:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("webapp", webapp_cmd))
    app.add_handler(CommandHandler("new", new_chat))
    app.add_handler(CommandHandler("premium", premium_cmd))
    app.add_handler(CommandHandler("pay", premium_cmd))
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(CallbackQueryHandler(premium_callback, pattern=r"^premium:"))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    return app


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
