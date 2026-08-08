"""Telegram bot — Faza 2.

Ishga tushirish:
    TELEGRAM_BOT_TOKEN=... ./venv/bin/python bot.py

@BotFather dan token oling. Bot sayt bilan BIR xil DB va miyadan foydalanadi.
"""

import asyncio
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

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from brain import brain
from db import get_db
from gen import generate_image, generate_video
from vision import analyze as analyze_image

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Telegram foydalanuvchisi -> joriy suhbat id (xotira)
current_conv: dict[int, int] = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        "/help — ushbu yordam\n\n"
        "Javoblar 👍/👎 orqali meni o'rgatasiz!",
        parse_mode="HTML",
    )


async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    current_conv.pop(uid, None)
    await update.message.reply_text(
        "✨ Yangi suhbat boshlanmoqda. Savolingizni yozing!"
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
    app.add_handler(CommandHandler("new", new_chat))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(CallbackQueryHandler(on_callback))
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
