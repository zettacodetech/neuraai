# Neura AI — noldan qurilgan sun'iy intellekt

Noldan qurilgan sun'iy intellekt: sayt chat + Telegram bot + CLI + PWA ilova.
Hech qanday tashqi AI, API yoki tayyor model yo'q — hammasi o'z kodimiz.
AI foydalanuvchilar bilan suhbatlashib o'rganadi (ma'lumotlar flywheli).

## Imkoniyatlar

- 💬 Suhbat (sayt, Telegram, terminal)
- 📚 Bilim bazasidan javob (IDF + so'z o'xshashligi)
- 🌐 Internetdan ixcham javob — snippetni **to'liq nusxa ko'chirmaydi**, faqat muhim jumlalarni yig'adi (`websearch.py`)
- 💻 Kod yozish (python, js, sql, html qoliplari — `coder.py`)
- 📷 Rasm tahlili (format, o'lcham, ranglar, yorug'lik, EXIF — `vision.py`)
- 📈 Avto-o'rganish: 👍 olgan javoblar + suhbatlar bilim bazasiga aylanadi
- 📱 PWA: sayt telefonga ilova sifatida o'rnatiladi

## Ishga tushirish (lokal)

```bash
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python daemon.py 8000        # server ishga tushadi
```

Brauzer: http://localhost:8000
To'xtatish: `pkill -9 -f "[u]vicorn"`

## Telegram bot

```bash
cd backend
./venv/bin/python bot.py            # token backend/.env dan o'qiladi
```

Yoki token paydo qilib:

```bash
TELEGRAM_BOT_TOKEN=123:abc ./venv/bin/python bot.py
```

Bot @BotFather dan olinadi. Token `backend/.env` fayliga yoziladi (repo'ga
qo'shilmaydi). Bot sayt bilan bitta DB va miyadan foydalanadi:
suhbat, 👍/👎 o'rganish, rasm tahlili. Hozirgi bot: @NeuraAI_UzBot.

## CLI

```bash
cd backend
./venv/bin/python cli.py "Savolingiz"          # bir martalik savol
./venv/bin/python cli.py --chat                # interaktiv suhbat
./venv/bin/python cli.py --image rasm.jpg      # rasm tahlili
./venv/bin/python cli.py --stats               # statistika
```

## Internet (DuckDuckGo, API kalitsiz)

AI bilim bazasidan javob topa olmasa, o'zi internetdan qidiradi va **ixcham xulosa** tuzadi.
O'chirish: `ENABLE_WEB_SEARCH=0`.

Internetdan o'qitish:

```bash
./venv/bin/python learn_from_web.py            # QUESTS ro'yxatidan
./venv/bin/python learn_from_web.py savollar.txt
```

## API

| Yo'l | Vazifa |
|---|---|
| `POST /api/chat` | Xabar yuborish → javob + message_id |
| `POST /api/feedback` | Javobni baholash (1/-1) → 👍 da darhol o'rganadi |
| `POST /api/analyze-image` | Rasm tahlili (multipart `file`) |
| `POST /api/learn` | Qo'lda o'rganish |
| `GET /api/conversations` | Suhbatlar tarixi (token) |
| `GET /api/admin/unanswered` | Javobsiz savollar (admin) |
| `POST /api/admin/answer` | Javob yozish (admin) |

Admin: `ADMIN_KEY` muhit o'zgaruvchisi (default: admin123 — almashtiring!).

## Avto-o'rganish qanday ishlaydi

1. Har suhbat DB'ga yoziladi (`data/ai.db`)
2. Foydalanuvchi javobni 👍 baholasa → **darhol** bilim bazasiga aylanadi
3. Har 120 soniyada fonda: 👍 olgan javoblar + yangi savollar qayta ishlanadi
4. AI javob bilmasa → savol `unanswered` ro'yxatiga tushadi
5. Admin javob yozsa → bilim bazasiga qo'shiladi

## Railway'ga deploy

1. `railway up`
2. Muhit o'zgaruvchilari: `ADMIN_KEY` (xavfsiz parol), ixtiyoriy `TELEGRAM_BOT_TOKEN`
3. Dockerfile avtomatik tanlanadi, `PORT` env ishlatiladi

Keyinchalik (GPU talab qiladi): rasm/video generatsiya — L40S 48GB plan.
