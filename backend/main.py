import os
import sys
import tempfile
import threading
import time
import json
import urllib.request

# Railway/uvicorn da backend modullari (auth, brain...) shu papkadan topilsin
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# .env faylini yuklash (lokalda token/flaglar shu yerda turadi, repo'ga kirmaydi)
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_ENV_PATH):
    with open(_ENV_PATH, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from auth import hash_password, new_token, verify_password
from brain import brain
from db import get_db
from gen import generate_image, generate_video, status as gen_status
from learning import collect_unanswered, learn_from_messages, learn_pair
from seeds import SEED_KNOWLEDGE
from vision import analyze as vision_analyze

app = FastAPI(title="Neura AI")

ADMIN_KEY = os.environ.get("ADMIN_KEY", "admin123")

ROOT = os.path.join(os.path.dirname(__file__), "..")
FRONTEND = os.path.join(ROOT, "frontend")

# ================= API kalitlari rate-limit (bepul, amortizatsiya) =================
_API_RATE_LIMIT = int(os.environ.get("API_KEY_LIMIT_PER_MINUTE", "20"))
_api_hits: dict[str, list[float]] = {}
_api_lock = threading.Lock()


def _api_key_allowed(key: str) -> bool:
    import time as _time

    now = _time.time()
    with _api_lock:
        window = [t for t in _api_hits.get(key, []) if now - t < 60]
        if len(window) >= _API_RATE_LIMIT:
            return False
        window.append(now)
        _api_hits[key] = window[-_API_RATE_LIMIT:]
        return True


class ChatRequest(BaseModel):
    message: str
    user_id: str | int | None = None
    telegram_id: int | None = None
    token: str | None = None
    conversation_id: int | None = None
    api_key: str | None = None


class FeedbackRequest(BaseModel):
    message_id: int
    rating: int


class AnswerRequest(BaseModel):
    item_id: int
    answer: str
    key: str = ""


class RegisterRequest(BaseModel):
    username: str
    password: str
    name: str = ""
    client_id: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str
    client_id: str | None = None


class RenameRequest(BaseModel):
    token: str
    name: str


@app.on_event("startup")
def startup() -> None:
    db = get_db()
    if os.environ.get("NEURA_USE_SEED_KNOWLEDGE", "0") == "1":
        db.add_seed_knowledge(SEED_KNOWLEDGE)
    if os.environ.get("NEURA_BOT_EMBEDDED", "1") == "1":
        try:
            import bot

            bot.start_bot_in_thread()
        except Exception as exc:
            print(f"[startup] bot ishga tushmadi: {exc}")


def _auto_learn_loop() -> None:
    """Fonda har 120 soniyada: 👍 olgan javoblarni va yangi savollarni o'rganadi."""
    while True:
        time.sleep(120)
        try:
            db = get_db()
            learn_from_messages(db)
            collect_unanswered(db)
        except Exception:
            pass


threading.Thread(target=_auto_learn_loop, daemon=True).start()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(FRONTEND, "index.html"))


@app.get("/apk/neuraai.apk")
def apk_download() -> FileResponse:
    """Android APK — yuklab olish (fayl frontend/apk/ dan xizmat qilinadi)."""
    apk = os.path.join(FRONTEND, "apk", "neuraai.apk")
    if not os.path.exists(apk):
        return JSONResponse({"error": "APK hozircha tayyor emas"}, status_code=404)
    return FileResponse(apk, media_type="application/vnd.android.package-archive")


@app.get("/static-apk/neuraai.apk")
def apk_download_static() -> FileResponse:
    return apk_download()


@app.get("/sw.js")
def sw() -> FileResponse:
    return FileResponse(os.path.join(FRONTEND, "sw.js"), media_type="text/javascript")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


# ================= generatsiya (Faza 5) =================


class GenRequest(BaseModel):
    prompt: str


GEN_DIR = os.environ.get("GEN_OUT_DIR", os.path.join(ROOT, "data", "gen"))
os.makedirs(GEN_DIR, exist_ok=True)
app.mount("/generated", StaticFiles(directory=GEN_DIR), name="generated")


def _gen_url(path: str) -> str:
    return "/generated/" + os.path.basename(path)


@app.post("/api/gen/image")
def gen_image(req: GenRequest) -> JSONResponse:
    if len(req.prompt.strip()) < 2:
        return JSONResponse({"error": "prompt kamida 2 belgi"}, status_code=400)
    path = generate_image(req.prompt.strip())
    return JSONResponse({"url": _gen_url(path), "prompt": req.prompt.strip()})


# ================= Rasm generatsiya (O'zbekcha prompt + auto tarjima) =================


class GenerateImageRequest(BaseModel):
    prompt: str  # O'zbekcha: "toglar boglar gullar"
    translate: bool = True  # Avtomatik inglizchaga o'tkazish


@app.post("/api/generate-image")
def generate_image_endpoint(req: GenerateImageRequest) -> JSONResponse:
    """O'zbekcha promptdan rasm yaratish (auto inglizchaga o'tkazib)."""
    prompt = req.prompt.strip()
    if len(prompt) < 2:
        return JSONResponse({"error": "prompt kamida 2 belgi"}, status_code=400)

    final_prompt = prompt
    if req.translate:
        # LLM orqali inglizchaga o'tkazish
        try:
            translation = llm_chat(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a prompt translator for Stable Diffusion/Flux. "
                        "Translate the user's prompt into a detailed, high-quality English prompt. "
                        "Only return the English prompt, no extra text.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=200,
            )
            if translation and translation.strip():
                final_prompt = translation.strip()
        except Exception:
            pass  # Tarjima muvaffaqiyatsiz bo'lsa, asl prompt ishlatiladi

    path = generate_image(final_prompt)
    return JSONResponse(
        {
            "url": _gen_url(path),
            "prompt": prompt,
            "translated_prompt": final_prompt if req.translate else None,
        }
    )


@app.post("/api/gen/video")
def gen_video(req: GenRequest) -> JSONResponse:
    if len(req.prompt.strip()) < 2:
        return JSONResponse({"error": "prompt kamida 2 belgi"}, status_code=400)
    path = generate_video(req.prompt.strip())
    return JSONResponse({"url": _gen_url(path), "prompt": req.prompt.strip()})


@app.get("/api/gen/status")
def gen_api_status() -> JSONResponse:
    return JSONResponse(gen_status())


_version_cache: dict = {}


@app.get("/api/version")
def version() -> JSONResponse:
    now = time.time()
    if _version_cache and now - _version_cache["ts"] < 300:
        return JSONResponse(_version_cache["data"])
    data = {"version": "0", "apk_url": None, "size": None}
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github+json"}
        tok = os.environ.get("GITHUB_TOKEN", "").strip()
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
        req = urllib.request.Request(
            "https://api.github.com/repos/zettacodetech/neuraai/releases/latest",
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            rel = json.loads(r.read().decode())
        asset = next(
            (a for a in rel.get("assets", []) if a.get("name", "").endswith(".apk")),
            None,
        )
        data = {
            "version": rel.get("tag_name", "").lstrip("v"),
            "apk_url": asset["browser_download_url"] if asset else None,
            "size": asset["size"] if asset else None,
            "published": rel.get("published_at", ""),
        }
    except Exception:
        data = {
            "version": "1.0.0",
            "apk_url": "https://github.com/zettacodetech/neuraai/releases/latest/download/neuraai.apk",
            "size": 26887547,
            "published": "",
        }
    _version_cache["ts"] = now
    _version_cache["data"] = data
    return JSONResponse(data)


# ================= suhbat =================


@app.post("/api/chat")
def chat(req: ChatRequest) -> JSONResponse:
    db = get_db()

    user = db.get_user_by_token(req.token) if req.token else None
    if not user and req.api_key:
        key_user = db.get_user_by_api_key(req.api_key)
        if not key_user:
            return JSONResponse({"error": "api kaliti noto'g'ri"}, status_code=401)
        if not _api_key_allowed(req.api_key):
            return JSONResponse(
                {
                    "error": "So'rovlar limiti (20/daqiqa) tugadi. Keyinroq urinib ko'ring."
                },
                status_code=429,
            )
        user = key_user
    if user:
        user_id = user["id"]
    else:
        user_id = db.get_or_create_user(
            req.telegram_id, str(req.user_id) if req.user_id else None
        )

    conv_id = req.conversation_id
    if conv_id is not None:
        conv = db.get_conversation(conv_id)
        if not conv or conv["user_id"] != user_id:
            return JSONResponse({"error": "suhbat topilmadi"}, status_code=404)
    else:
        conv_id = db.create_conversation(user_id, req.message)

    db.add_message(user_id, "user", req.message, conversation_id=conv_id)

    history: list[dict] | None = None
    try:
        prev = db.conversation_messages(conv_id, user_id)
        if len(prev) > 1:
            history = [
                {
                    "role": "assistant" if m["role"] == "assistant" else "user",
                    "content": m["text"],
                }
                for m in prev[:-1]
            ][-8:]
    except Exception:
        history = None

    reply, source = brain.answer(req.message, db.get_knowledge(), history=history)
    reply = (
        reply
        or "Kechirasiz, javob tayyorlay olmadim. Savolingizni boshqacha yozib ko'ring."
    )
    msg_id = db.add_message(
        user_id, "assistant", reply, source=source, conversation_id=conv_id
    )

    if source == "fallback":
        db.add_unanswered(req.message, user_id)

    resp = {
        "reply": reply,
        "source": source,
        "message_id": msg_id,
        "conversation_id": conv_id,
    }
    if user and user.get("name"):
        resp["user_name"] = user["name"]
    return JSONResponse(resp)


@app.post("/api/feedback")
def feedback(req: FeedbackRequest) -> JSONResponse:
    db = get_db()
    db.rate_message(req.message_id, req.rating)
    if req.rating == 1:
        row = db.conn.execute(
            "SELECT user_id, conversation_id FROM messages WHERE id = ?",
            (req.message_id,),
        ).fetchone()
        if row and row["conversation_id"]:
            prev = db.conn.execute(
                "SELECT id, text FROM messages "
                "WHERE conversation_id = ? AND user_id = ? AND id < ? AND role = 'user' "
                "ORDER BY id DESC LIMIT 1",
                (row["conversation_id"], row["user_id"], req.message_id),
            ).fetchone()
            if prev:
                learn_pair(db, prev["id"], req.message_id)
    return JSONResponse({"ok": True})


@app.post("/api/learn")
def learn() -> JSONResponse:
    db = get_db()
    learned = learn_from_messages(db)
    collect_unanswered(db)
    return JSONResponse({"learned": learned})


# ================= rasm tahlili (Faza 4) =================


@app.post("/api/analyze-image")
async def analyze_image(file: UploadFile = File(...)) -> JSONResponse:
    tmp_path = tempfile.mktemp(suffix=".img")
    try:
        with open(tmp_path, "wb") as f:
            f.write(await file.read())
        data = vision_analyze(tmp_path)
    except Exception as e:
        return JSONResponse(
            {"error": f"rasmni tahlil qilib bo'lmadi: {e}"}, status_code=400
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return JSONResponse(data)


# ================= Vision (Ollama) =================


class VisionRequest(BaseModel):
    image: str  # base64
    prompt: str = (
        "Ushbu rasmni tahlil qilib, undagi narsalarni o'zbekcha batafsil tushuntir."
    )


@app.post("/api/vision")
async def vision_analyze_ollama(req: VisionRequest) -> JSONResponse:
    """Ollama vision model (llama3.2-vision) orqali rasm tahlili."""
    try:
        import llm

        # Ollama provider ni topish
        ollama_provider = None
        for p in llm.LLM_PROVIDERS:
            if isinstance(p, llm._OllamaProvider):
                ollama_provider = p
                break

        if not ollama_provider or not ollama_provider.available:
            # Ollama yo'q — local yuklash uchun ko'rsatma
            return JSONResponse(
                {
                    "error": "Ollama server topilmadi. Lokalda: `ollama pull llama3.2-vision && ollama serve`",
                    "hint": "Railwayda: Ollama service deploy qiling (GPU bilan).",
                },
                status_code=503,
            )

        # Vision model uchun alohida model nomi
        vision_model = os.environ.get("OLLAMA_VISION_MODEL", "llama3.2-vision")
        orig_model = ollama_provider.model
        ollama_provider.model = vision_model

        try:
            result = ollama_provider.chat(
                messages=[{"role": "user", "content": req.prompt}],
                images=[req.image],
                temperature=0.3,
                max_tokens=800,
            )
        finally:
            ollama_provider.model = orig_model

        if not result:
            return JSONResponse(
                {"error": "Vision model javob bermadi"}, status_code=500
            )

        return JSONResponse(
            {"success": True, "analysis": result, "model": vision_model}
        )
    except Exception as e:
        return JSONResponse({"error": f"Vision xato: {e}"}, status_code=500)


# ================= Musiqa generatsiya (Suno API) =================


class MusicRequest(BaseModel):
    prompt: str  # Qo'shiq mavzusi/matni
    tags: str = "pop, uzbek, energetic"
    title: str = "NeuraAI Track"
    instrumental: bool = False


@app.post("/api/generate-music")
async def generate_music(req: MusicRequest) -> JSONResponse:
    """Suno API (lokal yoki bulut) orqali musiqa generatsiya."""
    suno_url = os.environ.get("SUNO_API_URL", "http://localhost:3000/api/generate")
    try:
        import urllib.request
        import json

        payload = json.dumps(
            {
                "prompt": req.prompt,
                "tags": req.tags,
                "title": req.title,
                "make_instrumental": req.instrumental,
                "wait_audio": True,
            }
        ).encode()

        req_obj = urllib.request.Request(
            suno_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_obj, timeout=120) as r:
            data = json.loads(r.read().decode())

        # Suno response: [{"audio_url": "..."}]
        audio_url = data[0].get("audio_url") if data else None
        return JSONResponse({"success": True, "audio_url": audio_url})
    except Exception as e:
        return JSONResponse(
            {
                "error": f"Musiqa generatsiya xato: {e}",
                "hint": "Lokal Suno API: `git clone https://github.com/suno-ai/suno-api && cd suno-api && npm install && npm start` (port 3000)",
            },
            status_code=503,
        )


# ================= Canvas / Dizayn shablonlari =================


class CanvasTemplate(BaseModel):
    id: int
    name: str
    width: int
    height: int
    category: str = "general"


@app.get("/api/canvas/templates")
async def canvas_templates() -> JSONResponse:
    """Canva/Excalidraw kabi dizayn platformasi uchun shablonlar."""
    templates = [
        {
            "id": 1,
            "name": "Instagram Post",
            "width": 1080,
            "height": 1080,
            "category": "social",
        },
        {
            "id": 2,
            "name": "Instagram Story",
            "width": 1080,
            "height": 1920,
            "category": "social",
        },
        {
            "id": 3,
            "name": "YouTube Thumbnail",
            "width": 1280,
            "height": 720,
            "category": "social",
        },
        {
            "id": 4,
            "name": "A4 Hujjat",
            "width": 2480,
            "height": 3508,
            "category": "document",
        },
        {
            "id": 5,
            "name": "Prezentatsiya (16:9)",
            "width": 1920,
            "height": 1080,
            "category": "document",
        },
        {
            "id": 6,
            "name": "Logo (Kvadrat)",
            "width": 512,
            "height": 512,
            "category": "branding",
        },
        {
            "id": 7,
            "name": "Vizitka",
            "width": 1050,
            "height": 600,
            "category": "branding",
        },
        {
            "id": 8,
            "name": "Twitter Header",
            "width": 1500,
            "height": 500,
            "category": "social",
        },
        {
            "id": 9,
            "name": "LinkedIn Post",
            "width": 1200,
            "height": 628,
            "category": "social",
        },
    ]
    return JSONResponse({"templates": templates})


# ================= hisob (registratsiya / kirish) =================


@app.post("/api/register")
def register(req: RegisterRequest) -> JSONResponse:
    db = get_db()
    if len(req.username.strip()) < 3:
        return JSONResponse(
            {"error": "login kamida 3 belgi bo'lishi kerak"}, status_code=400
        )
    if len(req.password) < 4:
        return JSONResponse(
            {"error": "parol kamida 4 belgi bo'lishi kerak"}, status_code=400
        )
    user_id = db.register_user(
        req.username,
        req.password and hash_password(req.password),
        req.name,
        req.client_id,
    )
    if user_id is None:
        return JSONResponse(
            {"error": "bu login band, boshqasini tanlang"}, status_code=409
        )
    token = new_token()
    db.set_token(user_id, token)
    user = db.get_user(user_id)
    assert user is not None
    return JSONResponse(
        {
            "token": token,
            "username": user["username"],
            "name": user["name"] or user["username"],
        }
    )


@app.post("/api/login")
def login(req: LoginRequest) -> JSONResponse:
    db = get_db()
    user = db.get_user_by_username(req.username)
    if (
        not user
        or not user.get("password_hash")
        or not verify_password(req.password, user["password_hash"])
    ):
        return JSONResponse({"error": "login yoki parol noto'g'ri"}, status_code=401)
    if req.client_id:
        db.transfer_guest(req.client_id, user["id"])
    token = new_token()
    db.set_token(user["id"], token)
    return JSONResponse(
        {
            "token": token,
            "username": user["username"],
            "name": user["name"] or user["username"],
        }
    )


@app.get("/api/me")
def me(token: str = "") -> JSONResponse:
    db = get_db()
    user = db.get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "kirish talab qilinadi"}, status_code=401)
    return JSONResponse(
        {
            "id": user["id"],
            "username": user["username"],
            "name": user["name"] or user["username"],
        }
    )


@app.post("/api/rename")
def rename(req: RenameRequest) -> JSONResponse:
    db = get_db()
    user = db.get_user_by_token(req.token)
    if not user:
        return JSONResponse({"error": "kirish talab qilinadi"}, status_code=401)
    db.update_name(user["id"], req.name.strip()[:40] or user["username"])
    return JSONResponse({"ok": True})


@app.get("/api/session")
def session(client_id: str = "") -> JSONResponse:
    """Mehmon seansi: brauzer/ilova uchun doimiy token (tarix saqlanadi)."""
    if not client_id:
        client_id = "anon_" + new_token()[:12]
    db = get_db()
    user_id = db.get_or_create_user(client_id=client_id[:60])
    user = db.get_user(user_id)
    if user and user.get("token"):
        return JSONResponse({"token": user["token"], "guest": not user.get("username")})
    token = new_token()
    db.set_token(user_id, token)
    return JSONResponse({"token": token, "guest": True})


# ================= API kalitlari (bepul, limitle) =================


@app.post("/api/key/create")
def api_key_create(token: str = "") -> JSONResponse:
    db = get_db()
    user = db.get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "kirish talab qilinadi"}, status_code=401)
    key = new_token()
    db.set_api_key(user["id"], key)
    return JSONResponse({"key": key, "limit_per_minute": _API_RATE_LIMIT})


@app.get("/api/key")
def api_key_get(token: str = "") -> JSONResponse:
    db = get_db()
    user = db.get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "kirish talab qilinadi"}, status_code=401)
    row = db.get_api_key(user["id"])
    if not row:
        return JSONResponse({"key": None})
    return JSONResponse({"key": row["key"], "limit_per_minute": _API_RATE_LIMIT})


@app.delete("/api/key")
def api_key_delete(token: str = "") -> JSONResponse:
    db = get_db()
    user = db.get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "kirish talab qilinadi"}, status_code=401)
    db.delete_api_key(user["id"])
    return JSONResponse({"ok": True})


@app.post("/api/logout")
def logout(token: str = "") -> JSONResponse:
    db = get_db()
    if token:
        db.conn.execute("UPDATE users SET token = NULL WHERE token = ?", (token,))
    return JSONResponse({"ok": True})


# ================= suhbat tarixi =================


@app.get("/api/conversations")
def conversations(token: str = "") -> JSONResponse:
    db = get_db()
    user = db.get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "kirish talab qilinadi"}, status_code=401)
    return JSONResponse({"items": db.list_conversations(user["id"])})


@app.get("/api/conversations/{conv_id}")
def conversation_messages(conv_id: int, token: str = "") -> JSONResponse:
    db = get_db()
    user = db.get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "kirish talab qilinadi"}, status_code=401)
    conv = db.get_conversation(conv_id)
    if not conv or conv["user_id"] != user["id"]:
        return JSONResponse({"error": "suhbat topilmadi"}, status_code=404)
    return JSONResponse(
        {"title": conv["title"], "items": db.conversation_messages(conv_id, user["id"])}
    )


# ================= admin =================


@app.get("/api/admin/unanswered")
def admin_unanswered(key: str = "") -> JSONResponse:
    if key != ADMIN_KEY:
        return JSONResponse({"error": "ruxsat yo'q"}, status_code=403)
    db = get_db()
    return JSONResponse({"items": db.get_unanswered()})


@app.post("/api/admin/answer")
def admin_answer(req: AnswerRequest) -> JSONResponse:
    if req.key != ADMIN_KEY:
        return JSONResponse({"error": "ruxsat yo'q"}, status_code=403)
    db = get_db()
    db.answer_unanswered(req.item_id, req.answer)
    return JSONResponse({"ok": True})
