"""Faza 4: kod yozish — qolip (template) asosidagi generator.

Tayyor model/API yo'q — shuning uchun keng tarqalgan topshiriqlar uchun
sifatli kod qoliplaridan javob beradi. Mos qolip topilmasa — None qaytadi
va AI internetdan izlaydi.
"""

import re

LANG_HINTS = {
    "python": ["python", "piton"],
    "javascript": ["javascript", "js", "node"],
    "sql": ["sql", "jadval", "database", "baza"],
    "bash": ["bash", "shell", "terminal", "komanda"],
    "html": ["html", "sahifa", "sayt", "css"],
}

TEMPLATES = [
    {
        "keys": [
            "http so'rov",
            "http request",
            "so'rov yuborish",
            "request",
            "yuklab olish",
            "fetch",
            "qidiruv so'rovi",
        ],
        "name": "HTTP so'rov (GET)",
        "code": """import urllib.request

url = "https://api.example.com/data"

req = urllib.request.Request(url, headers={"User-Agent": "NeuraAI/1.0"})
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = resp.read().decode("utf-8")
        print(data)
except urllib.error.URLError as e:
    print(f"Xatolik: {e}")
""",
    },
    {
        "keys": [
            "fayl o'qish",
            "fayl oqish",
            "fayl yozish",
            "fayldan",
            "faylga",
            "file",
        ],
        "name": "Fayl o'qish / yozish",
        "code": """# Fayl o'qish
with open("input.txt", "r", encoding="utf-8") as f:
    matn = f.read()
    print(matn)

# Faylga yozish
with open("output.txt", "w", encoding="utf-8") as f:
    f.write("Salom, dunyo!")
""",
    },
    {
        "keys": [
            "saralash",
            "sort",
            "tartiblash",
            "eng katta",
            "eng kichik",
            "algoritm",
            "binary",
            "izlash",
        ],
        "name": "Saralash algoritmi",
        "code": """def quicksort(ro'yxat):
    if len(ro'yxat) <= 1:
        return ro'yxat
    tayanch = ro'yxat[len(ro'yxat) // 2]
    chap = [x for x in ro'yxat if x < tayanch]
    o'rta = [x for x in ro'yxat if x == tayanch]
    o'ng = [x for x in ro'yxat if x > tayanch]
    return quicksort(chap) + o'rta + quicksort(o'ng)

sonlar = [5, 2, 9, 1, 7]
print(quicksort(sonlar))  # [1, 2, 5, 7, 9]
""",
    },
    {
        "keys": ["telegram bot", "bot yoz", "tg bot", "bot"],
        "name": "Telegram bot",
        "code": """from telegram.ext import Application, CommandHandler

TOKEN = "BOT_TOKEN"  # @BotFather dan oling

async def start(update, context):
    await update.message.reply_text("Salom! Men oddiy botman.")

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.run_polling()
""",
    },
    {
        "keys": ["web sayt", "sayt yoz", "html", "sahifa", "css", "sayt"],
        "name": "HTML sahifa",
        "code": """<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Mening sahifam</title>
  <style>
    body { font-family: sans-serif; margin: 40px; }
    h1 { color: #7c6cff; }
  </style>
</head>
<body>
  <h1>Salom, dunyo!</h1>
  <p>Bu mening birinchi sahifam.</p>
</body>
</html>
""",
    },
    {
        "keys": ["jadval yarat", "jadval", "table", "create table", "database", "sql"],
        "name": "SQL jadval yaratish",
        "code": """CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name          TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);

INSERT INTO users (username, password_hash, name)
VALUES ('alisher', 'hashbu_yerda', 'Alisher');
""",
    },
    {
        "keys": ["parol", "hash", "shifrlash", "kodlash", "password"],
        "name": "Parolni xavfsiz saqlash (PBKDF2)",
        "code": """import hashlib
import secrets

def hash_password(parol: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", parol.encode(), bytes.fromhex(salt), 100_000)
    return f"{salt}${digest.hex()}"

def verify_password(parol: str, stored: str) -> bool:
    salt, digest = stored.split("$")
    calc = hashlib.pbkdf2_hmac("sha256", parol.encode(), bytes.fromhex(salt), 100_000)
    return calc.hex() == digest

stored = hash_password("1234")
print(verify_password("1234", stored))  # True
""",
    },
    {
        "keys": ["api server", "fastapi", "rest api", "backend", "server yoz"],
        "name": "FastAPI server",
        "code": """from fastapi import FastAPI

app = FastAPI(title="Mening API'm")

@app.get("/")
def index():
    return {"message": "Salom, dunyo!"}

@app.get("/api/users/{user_id}")
def get_user(user_id: int):
    return {"id": user_id, "name": "Alisher"}

# Ishga tushirish: uvicorn main:app --reload
""",
    },
    {
        "keys": ["zip", "arxiv", "siqish", "ko'chirish", "fayllarni", "backup"],
        "name": "Fayllarni ziplash",
        "code": """import shutil

# Papkani zip qilish
shutil.make_archive("arxiv", "zip", "papka_nomi")
print("Papka zip qilindi: arxiv.zip")
""",
    },
]


def generate_code(message: str) -> str | None:
    """Savolga mos kod qolipini qaytaradi. Topilmasa None."""
    norm = message.lower().replace("'", "")
    norm = re.sub(r"[^\w\s]", " ", norm)
    norm = re.sub(r"\s+", " ", norm).strip()
    for t in TEMPLATES:
        if any(k.replace("'", "") in norm for k in t["keys"]):
            lang = "python"
            for name, hints in LANG_HINTS.items():
                if any(h.replace("'", "") in norm for h in hints):
                    lang = name
                    break
            return t["code"].strip()
    return None
