import os
import re
import sys
import tempfile
import threading
import time
import json
import urllib.request
import hashlib
import hmac
import secrets

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

from collections.abc import Iterable
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from auth import hash_password, new_token, verify_password
from brain import brain
from db import get_db
from gen import generate_image, generate_video, status as gen_status
from coder import generate_code
from learning import collect_unanswered, learn_from_messages, learn_pair
from seeds import SEED_KNOWLEDGE
from vision import analyze as vision_analyze

from llm import OPENROUTER_BASE_URL, llm_chat

_MODELS_CACHE: dict = {"ts": 0.0, "items": []}

app = FastAPI(title="Inomjon AI")

ADMIN_KEY = os.environ.get("ADMIN_KEY", "admin123")

ROOT = os.path.join(os.path.dirname(__file__), "..")
FRONTEND = os.path.join(ROOT, "frontend")

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

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
    telegram_id: int | str | None = None
    token: str | None = None
    conversation_id: int | None = None
    api_key: str | None = None
    model: str | None = None  # "fast" | "think" | aniq model nomi


class FeedbackRequest(BaseModel):
    message_id: int
    rating: int


class AnswerRequest(BaseModel):
    item_id: int
    answer: str
    key: str = ""


class RegisterRequest(BaseModel):
    email: str = ""
    username: str = ""  # eski ilovalar uchun zaxira
    password: str
    name: str = ""
    surname: str = ""
    phone: str = ""
    client_id: str | None = None


class LoginRequest(BaseModel):
    email: str = ""
    username: str = ""  # eski ilovalar uchun zaxira
    password: str
    client_id: str | None = None


class RenameRequest(BaseModel):
    token: str
    name: str


class ProfileUpdateRequest(BaseModel):
    token: str = ""
    name: str = ""
    surname: str = ""
    phone: str = ""


class ChangePasswordRequest(BaseModel):
    token: str = ""
    old_password: str = ""
    new_password: str = ""


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


@app.get("/login")
def login_page() -> FileResponse:
    return FileResponse(os.path.join(FRONTEND, "login.html"))


@app.get("/register")
def register_page() -> FileResponse:
    return FileResponse(os.path.join(FRONTEND, "register.html"))


@app.get("/profile")
def profile_page() -> FileResponse:
    return FileResponse(os.path.join(FRONTEND, "profile.html"))


@app.get("/api-key")
def api_key_page() -> FileResponse:
    return FileResponse(os.path.join(FRONTEND, "api-key.html"))


@app.get("/about")
def about_page() -> FileResponse:
    return FileResponse(os.path.join(FRONTEND, "about.html"))


@app.get("/admin")
def admin_page() -> FileResponse:
    return FileResponse(os.path.join(FRONTEND, "admin.html"))


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


@app.middleware("http")
async def no_cache_static(request, call_next):
    """Statik fayllar va sahifa — har yuklashda yangilansin (eski dizayn muammosi)."""
    response = await call_next(request)
    path = request.url.path
    if not path.startswith("/api/") and not path.startswith("/generated"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


# ================= generatsiya (Faza 5) =================


class GenRequest(BaseModel):
    prompt: str
    token: str | None = None


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
    _record_gen(req, "image", _gen_url(path))
    return JSONResponse({"url": _gen_url(path), "prompt": req.prompt.strip()})


def _record_gen(req, kind: str, url: str) -> None:
    token = getattr(req, "token", None)
    if not token:
        return
    try:
        user = get_db().get_user_by_token(token)
        if user:
            get_db().add_gen(user["id"], kind, url, req.prompt.strip())
    except Exception:
        pass


# ================= Rasm generatsiya (O'zbekcha prompt + auto tarjima) =================


class GenerateImageRequest(BaseModel):
    prompt: str  # O'zbekcha: "toglar boglar gullar"
    translate: bool = True  # Avtomatik inglizchaga o'tkazish
    token: str | None = None


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
    _record_gen(req, "image", _gen_url(path))
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
    _record_gen(req, "video", _gen_url(path))
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

_ANALYSIS_RE = re.compile(
    r"(tahlil|analiz|izohla|tarifla|tushuntir|bilasan?mi|oladimi|"
    r"mumkinmi|nima degan|qanday qilin|\bwhat\b|\bwhy\b|\bhow\b)"
)
_QUESTION_RE = re.compile(r"\b(nima|nega|qachon|qanday|qayer|kim|nechta)\b|\?")
_TALK_RE = re.compile(
    r"(gapirib?|ayt(bing)?|haqida|tavsifla|ma'lu[mt]ot|izohl?ab?|qanday ko'rinish)"
)
_IMG_RE = re.compile(r"(rasim|rasm|surot|surat|tasvir|image|\bphoto\b)")
_VID_RE = re.compile(r"(video|vidio)")
_PAINT_RE = re.compile(r"(chiz|draw|paint)")
_MAKE_RE = re.compile(r"(yarat|yasa|create|make|generate)")
_SCENE_RE = re.compile(
    r"(tog'|daryo|o'rmon|dengiz|osmon|quyosh|botish|chiqish|"
    r"shahar|qishloq|manzara|panorama|tabiat|portret)"
)
_GEN_STRIP_RE = re.compile(
    r"\w*(chiz|yarat|yasa|qil|draw|paint|create|make|generate)\w*"
)
_GEN_WORDS_RE = re.compile(r"\b(ber|berib|tashla|uchun)\b", re.IGNORECASE)
_TEXT_CLEAN_RE = re.compile(r"[\s:;,.\-]+")


def _gen_request(text: str) -> tuple[str, str] | None:
    """Rasm/video generatsiya so'rovini aniqlaydi.

    Qaytaradi: ('image'|'video', prompt) yoki None. "rasm/video" so'zisiz
    ham aniqlay oladi — masalan "dengiz bo'yda quyosh botishini chiz".
    """
    t = text.strip()
    low = t.lower()
    # Tahlil / savol — generatsiya EMAS
    if _ANALYSIS_RE.search(low) or _QUESTION_RE.search(low):
        return None
    # "rasm haqida gapirib ber" kabi suhbat so'rovlari — generatsiya EMAS,
    # faqat aniq yaratish fe'li bo'lsa generatsiya
    if _TALK_RE.search(low) and not _PAINT_RE.search(low) and not _MAKE_RE.search(low):
        return None

    has_video = bool(_VID_RE.search(low))
    has_img = bool(_IMG_RE.search(low))
    # Video birinchi (aniq kalit so'z)
    if has_video:
        return ("video", _gen_prompt(t, "video"))
    if has_img:
        return ("image", _gen_prompt(t, "image"))
    # "chizib ber" — rasim so'zisiz ham rasm
    if _PAINT_RE.search(low):
        return ("image", _gen_prompt(t, "image"))
    # Sahna ta'rifi + yaratish fe'li
    if _SCENE_RE.search(low) and _MAKE_RE.search(low):
        return ("image", _gen_prompt(t, "image"))
    return None


def _gen_prompt(text: str, kind: str) -> str:
    """Rasm/video markerlari va fe'llarini olib, aniq prompt qoldiradi."""
    prompt = text
    if kind == "video":
        prompt = re.sub(r"^\s*(?:video|vidio)\b\s*:?", "", prompt, flags=re.IGNORECASE)
    else:
        prompt = _IMG_RE.sub(" ", prompt)
    prompt = _GEN_STRIP_RE.sub(" ", prompt)
    prompt = _GEN_WORDS_RE.sub(" ", prompt)
    return _TEXT_CLEAN_RE.sub(" ", prompt).strip()


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
        tg = req.telegram_id
        uid_str = str(req.user_id) if req.user_id else None
        if isinstance(tg, int):
            user_id = db.get_or_create_user(tg, uid_str)
        elif tg:
            # Eski ilovalar telegram_id'ga "mobile_..." satrini yuboradi
            user_id = db.get_or_create_user(None, str(tg))
        else:
            user_id = db.get_or_create_user(None, uid_str)

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

    # Model tanlash: "fast" → NEURA_FAST_MODEL (tez), "think" → NEURA_THINK_MODEL (mulohazali)
    model_name = None
    if req.model in ("fast", "think"):
        key = "NEURA_FAST_MODEL" if req.model == "fast" else "NEURA_THINK_MODEL"
        model_name = os.environ.get(key, "").strip() or None
    elif req.model:
        model_name = req.model.strip() or None

    # Rasm/video so'rovi — LLM'ga bermay, to'g'ridan generatsiya qilamiz
    gen = _gen_request(req.message)
    if gen:
        kind, prompt = gen
        if not prompt:
            prompt = (
                "chiroyli tabiat manzarasi"
                if kind == "image"
                else "go'zal tabiat panoramasi"
            )
        try:
            path = generate_image(prompt) if kind == "image" else generate_video(prompt)
            url = _gen_url(path)
            label = "🎨 Rasm tayyor!" if kind == "image" else "🎬 Video tayyor!"
            reply = f"{label}\nPrompt: {prompt}\n\n{url}"
            msg_id = db.add_message(
                user_id,
                "assistant",
                reply,
                source="generation",
                conversation_id=conv_id,
            )
            return JSONResponse(
                {
                    "reply": reply,
                    "source": "generation",
                    "message_id": msg_id,
                    "conversation_id": conv_id,
                    "model": model_name,
                    "media_type": kind,
                    "media_url": url,
                }
            )
        except Exception as exc:
            reply = f"⚠️ Rasm yaratishda xatolik: {exc}"
            msg_id = db.add_message(
                user_id, "assistant", reply, source="error", conversation_id=conv_id
            )
            return JSONResponse(
                {
                    "reply": reply,
                    "source": "error",
                    "message_id": msg_id,
                    "conversation_id": conv_id,
                    "model": model_name,
                }
            )

    reply, source = brain.answer(
        req.message, db.get_knowledge(), history=history, model=model_name
    )
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
        "model": model_name,
    }
    if user and user.get("name"):
        resp["user_name"] = user["name"]
    return JSONResponse(resp)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _resolve_chat(req: "ChatRequest") -> dict:
    """Chat so'z boshi: foydalanuvchi + suhbat + tarix + model. Xatoda {'error': ...}."""
    db = get_db()

    user = db.get_user_by_token(req.token) if req.token else None
    if not user and req.api_key:
        key_user = db.get_user_by_api_key(req.api_key)
        if not key_user:
            return {
                "error": JSONResponse(
                    {"error": "api kaliti noto'g'ri"}, status_code=401
                )
            }
        if not _api_key_allowed(req.api_key):
            return {
                "error": JSONResponse(
                    {
                        "error": "So'rovlar limiti (20/daqiqa) tugadi. Keyinroq urinib ko'ring."
                    },
                    status_code=429,
                )
            }
        user = key_user
    if user:
        user_id = user["id"]
    else:
        tg = req.telegram_id
        uid_str = str(req.user_id) if req.user_id else None
        if isinstance(tg, int):
            user_id = db.get_or_create_user(tg, uid_str)
        elif tg:
            # Eski ilovalar telegram_id'ga "mobile_..." satrini yuboradi
            user_id = db.get_or_create_user(None, str(tg))
        else:
            user_id = db.get_or_create_user(None, uid_str)

    conv_id = req.conversation_id
    if conv_id is not None:
        conv = db.get_conversation(conv_id)
        if not conv or conv["user_id"] != user_id:
            return {
                "error": JSONResponse({"error": "suhbat topilmadi"}, status_code=404)
            }
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

    # Model tanlash: "fast" → NEURA_FAST_MODEL (tez), "think" → NEURA_THINK_MODEL (o'ylab)
    model_name = None
    if req.model in ("fast", "think"):
        key = "NEURA_FAST_MODEL" if req.model == "fast" else "NEURA_THINK_MODEL"
        model_name = os.environ.get(key, "").strip() or None
    elif req.model:
        model_name = req.model.strip() or None

    return {
        "db": db,
        "user_id": user_id,
        "conv_id": conv_id,
        "history": history,
        "model_name": model_name,
        "user": user,
    }


def _chat_stream_events(req: "ChatRequest", ctx: dict) -> Iterable[str]:
    """SSE hodisalari: start → (media | text…) → done. `text` bo'laklari hash-hash keladi."""
    db = ctx["db"]
    user_id = ctx["user_id"]
    conv_id = ctx["conv_id"]
    history = ctx["history"]
    model_name = ctx["model_name"]

    yield _sse({"type": "start", "conversation_id": conv_id})

    # Rasm/video so'rovi — bevosita generatsiya
    gen = _gen_request(req.message)
    if gen:
        kind, prompt = gen
        if not prompt:
            prompt = (
                "chiroyli tabiat manzarasi"
                if kind == "image"
                else "go'zal tabiat panoramasi"
            )
        try:
            path = generate_image(prompt) if kind == "image" else generate_video(prompt)
            url = _gen_url(path)
            label = "🎨 Rasm tayyor!" if kind == "image" else "🎬 Video tayyor!"
            reply = f"{label}\nPrompt: {prompt}\n\n{url}"
            msg_id = db.add_message(
                user_id,
                "assistant",
                reply,
                source="generation",
                conversation_id=conv_id,
            )
            yield _sse(
                {
                    "type": "media",
                    "media_type": kind,
                    "media_url": url,
                    "reply": reply,
                    "message_id": msg_id,
                }
            )
        except Exception as exc:
            reply = f"⚠️ Rasm yaratishda xatolik: {exc}"
            msg_id = db.add_message(
                user_id, "assistant", reply, source="error", conversation_id=conv_id
            )
            yield _sse({"type": "error", "reply": reply, "message_id": msg_id})
        yield _sse({"type": "done", "conversation_id": conv_id})
        return

    # Tezkor yo'llar: intent / kod / bilim → bir martada to'liq matn
    reply: str | None = None
    source = "llm"
    context: str | None = None

    intent = brain._detect_intent(req.message)
    if intent:
        if intent["name"] == "code":
            code = generate_code(req.message)
            if code:
                reply = (
                    f"Kod tayyor:\n\n```\n{code}\n```\n\n"
                    "So'rovda noma 'l3m joylar bo'lsa, ularni o'zingizga moslab o'zgartiring. "
                    "Yana boshqa narsa kerak bo'lsa — yozing!"
                )
            else:
                reply = (
                    "Kod yozish uchun aniqroq yozing, masalan:\n"
                    "• 'telegram bot yoz'\n"
                    "• 'http so'rov yoz'\n"
                    "• 'jadval yarat' (SQL)\n"
                    "• 'saralash algoritmi yoz'\n"
                    "• 'parolni hash qilish'\n\n"
                    "Yoki kerakli kodni boshqa savol shaklida yozing!"
                )
            source = "code"
        else:
            reply = intent["reply"]
            source = "intent"
    elif not brain._tokens(req.message):
        reply = "Savolingizni aniqroq yozing, iltimos. Yordam kerak bo'lsa 'yordam' deb yozing."
        source = "fallback"
    else:
        best = brain._retrieve(brain._tokens(req.message), db.get_knowledge())
        if best and best[1] >= 2.0 and best[2] >= 0.4:
            reply = best[0]["answer"]
            source = "knowledge"

    if reply is None and source == "llm":
        # Kuchaytirilgan yo'l: internet + LLM streaming
        if os.environ.get("ENABLE_WEB_SEARCH", "1") == "1" and len(req.message) >= 10:
            try:
                _, web_ctx = brain._web_search(req.message)
                if web_ctx:
                    context = web_ctx
            except Exception:
                context = None
        from llm import _clean, llm_answer_stream

        got_any = False
        parts: list[str] = []
        try:
            for chunk in llm_answer_stream(
                req.message, history=history, context=context, model=model_name
            ):
                got_any = True
                parts.append(chunk)
                yield _sse({"type": "text", "text": chunk})
        except Exception:
            got_any = False
        if got_any:
            reply = _clean("".join(parts).strip()) or None
            source = "websearch" if context else "llm"

    reply = reply or (
        "Kechirasiz, javob tayyorlay olmadim. Savolingizni boshqacha yozib ko'ring."
    )
    msg_id = db.add_message(
        user_id, "assistant", reply, source=source, conversation_id=conv_id
    )
    if source == "fallback":
        db.add_unanswered(req.message, user_id)

    yield _sse(
        {
            "type": "done",
            "reply": reply,
            "message_id": msg_id,
            "source": source,
            "model": model_name,
        }
    )


@app.post("/api/chat/stream", response_model=None)
def chat_stream(req: ChatRequest) -> StreamingResponse | JSONResponse:
    ctx = _resolve_chat(req)
    if "error" in ctx:
        return ctx["error"]
    return StreamingResponse(
        _chat_stream_events(req, ctx),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


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


# ================= Hujjat yuklash (PDF/DOCX/TXT) =================


@app.post("/api/upload-doc")
async def upload_doc(file: UploadFile = File(...)) -> JSONResponse:
    """Hujjatdan matn ajratib oladi, keyin foydalanuvchi chatga yuboradi."""
    try:
        raw = await file.read()
        name = file.filename or "hujjat"
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else "txt"
        text = ""

        if ext == "pdf":
            import io

            import pypdf

            reader = pypdf.PdfReader(io.BytesIO(raw))
            pages = [p.extract_text() or "" for p in reader.pages]
            text = "\n\n".join(pages)
        elif ext == "docx":
            import io

            import docx as docxlib

            doc = docxlib.Document(io.BytesIO(raw))
            text = "\n".join(p.text for p in doc.paragraphs)
        else:
            for enc in ("utf-8", "windows-1251", "utf-16"):
                try:
                    text = raw.decode(enc)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue

        text = text.strip()
        if not text:
            return JSONResponse(
                {
                    "error": "Hujjatdan matn ajratib bo'lmadi (skanerlangan PDF bo'lishi mumkin)"
                },
                status_code=400,
            )
        if len(text) > 4000:
            text = text[:4000] + "\n\n... (hujjat uzun, davomi kesildi)"

        return JSONResponse(
            {
                "success": True,
                "filename": name,
                "chars": len(text),
                "text": text,
                "preview": text[:200],
            }
        )
    except Exception as e:
        return JSONResponse({"error": f"Hujjatni o'qishda xato: {e}"}, status_code=400)


# ================= Ovozli xabar (Speech-to-Text, Groq Whisper) =================


def groq_stt(audio_bytes: bytes, filename: str) -> str:
    import json
    import urllib.request

    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY topilmadi")
    boundary = "----aiuz" + secrets.token_hex(8)
    parts = []
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
    )
    parts.append(b"Content-Type: audio/mpeg\r\n\r\n")
    parts.append(audio_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(b'Content-Disposition: form-data; name="model"\r\n\r\n')
    parts.append(b"whisper-large-v3-turbo\r\n")
    parts.append(b"--" + boundary.encode() + b"--\r\n")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        data=b"".join(parts),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
    return (data.get("text") or "").strip()


@app.post("/api/stt")
async def stt(file: UploadFile = File(...)) -> JSONResponse:
    tmp_path = tempfile.mktemp(suffix=".audio")
    try:
        audio = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(audio)
        text = groq_stt(audio, file.filename or "voice.mp3")
    except Exception as e:
        return JSONResponse({"error": f"Ovozni tanib bo'lmadi: {e}"}, status_code=400)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    if not text:
        return JSONResponse({"error": "Nutq tanilmadi"}, status_code=400)
    return JSONResponse({"success": True, "text": text})


# ================= Lokal AI (Ollama) =================


def _ollama_provider():
    try:
        import llm as llm_mod

        for p in llm_mod.LLM_PROVIDERS:
            if isinstance(p, llm_mod._OllamaProvider):
                return p
    except Exception:
        pass
    return None


@app.get("/api/local-ai")
def local_ai_status() -> JSONResponse:
    """Lokal AI holati: Ollama ishlayaptimi, qaysi modellar bor."""
    prov = _ollama_provider()
    if not prov:
        return JSONResponse({"success": False, "error": "Ollama sozlanmagan"})
    models = prov.installed_models()
    configured = prov.model
    return JSONResponse(
        {
            "success": True,
            "available": prov.available,
            "base_url": prov.base_url,
            "configured_model": configured,
            "configured_installed": prov.model_installed(configured),
            "models": models,
            "provider_order": [
                os.environ.get("NEURA_LLM_PROVIDER", "auto"),
            ],
            "hint": "Yangi model: POST /api/local-ai/pull (admin)",
        }
    )


class LocalAiPullRequest(BaseModel):
    admin_key: str = ""
    model: str = ""


@app.post("/api/local-ai/pull")
def local_ai_pull(req: LocalAiPullRequest) -> JSONResponse:
    """Model yuklab olish (admin). Yangi model fon'da yuklanadi."""
    if req.admin_key != ADMIN_KEY:
        return JSONResponse({"error": "admin kaliti kerak"}, status_code=401)
    prov = _ollama_provider()
    if not prov:
        return JSONResponse({"error": "Ollama sozlanmagan"}, status_code=503)
    name = (req.model or "").strip()
    if not name:
        name = prov.model
    if prov.model_installed(name):
        return JSONResponse({"success": True, "model": name, "already": True})
    threading.Thread(target=prov.pull_model, args=(name,), daemon=True).start()
    return JSONResponse(
        {
            "success": True,
            "model": name,
            "status": "downloading",
            "hint": "Holatni tekshirish: GET /api/local-ai",
        }
    )


# ================= Ulashish (share) =================


@app.post("/api/share/create")
async def share_create(req: Request) -> JSONResponse:
    db = get_db()
    body = await req.json()
    token = (body.get("token") or "").strip()
    conversation_id = int(body.get("conversation_id") or 0)
    user = db.get_user_by_token(token) if token else None
    if not user:
        return JSONResponse({"error": "Avval tizimga kiring"}, status_code=401)
    if not conversation_id:
        return JSONResponse({"error": "Suhbat topilmadi"}, status_code=400)
    existing = db.list_shares(user["id"])
    if any(s["conversation_id"] == conversation_id for s in existing):
        code = next(
            s["code"] for s in existing if s["conversation_id"] == conversation_id
        )
        return JSONResponse(
            {
                "success": True,
                "code": code,
                "url": f"/share/{code}",
                "public_url": f"{PUBLIC_BASE_URL}/share/{code}",
                "created": True,
            }
        )
    code = secrets.token_urlsafe(8)
    ok = db.create_share(conversation_id, user["id"], code)
    if not ok:
        return JSONResponse({"error": "Suhbat topilmadi"}, status_code=404)
    return JSONResponse(
        {
            "success": True,
            "code": code,
            "url": f"/share/{code}",
            "public_url": f"{PUBLIC_BASE_URL}/share/{code}",
            "created": True,
        }
    )


@app.post("/api/share/delete")
async def share_delete(req: Request) -> JSONResponse:
    db = get_db()
    body = await req.json()
    token = (body.get("token") or "").strip()
    conversation_id = int(body.get("conversation_id") or 0)
    user = db.get_user_by_token(token) if token else None
    if not user:
        return JSONResponse({"error": "Avval tizimga kiring"}, status_code=401)
    db.delete_share(conversation_id, user["id"])
    return JSONResponse({"success": True})


@app.get("/api/share/{code}")
async def share_get(code: str) -> JSONResponse:
    """Ommaviy — login talab qilinmaydi."""
    db = get_db()
    share = db.get_share(code)
    if not share:
        return JSONResponse({"error": "Havola topilmadi"}, status_code=404)
    msgs = db.get_messages(share["conversation_id"])
    conv = db.get_conversation(share["conversation_id"])
    return JSONResponse(
        {
            "code": code,
            "title": (conv or {}).get("title", "Suhbat"),
            "messages": [m for m in msgs if m["role"] in ("user", "assistant")],
            "created_at": share["created_at"],
        }
    )


@app.get("/share/{code}")
async def share_page(code: str) -> FileResponse:
    db = get_db()
    share = db.get_share(code)
    if not share:
        return JSONResponse({"error": "Havola topilmadi"}, status_code=404)
    return FileResponse(os.path.join(FRONTEND, "index.html"))


@app.get("/share")
async def share_redirect() -> FileResponse:
    return FileResponse(os.path.join(FRONTEND, "index.html"))


# ================= Qidiruv =================


@app.get("/api/search")
async def search(q: str = "", token: str = "") -> JSONResponse:
    db = get_db()
    user = db.get_user_by_token(token) if token else None
    if not user:
        return JSONResponse({"error": "Avval tizimga kiring"}, status_code=401)
    q = q.strip()
    if len(q) < 2:
        return JSONResponse({"error": "Qidiruv so'zi juda qisqa"}, status_code=400)
    results = db.search_messages(user["id"], q)
    return JSONResponse({"success": True, "results": results})


# ================= Galereya (generatsiya tarixi) =================


@app.get("/api/gallery")
async def gallery(kind: str = "", token: str = "") -> JSONResponse:
    db = get_db()
    user = db.get_user_by_token(token) if token else None
    if not user:
        return JSONResponse({"error": "Avval tizimga kiring"}, status_code=401)
    items = db.list_gen(user["id"], kind or None)
    return JSONResponse({"success": True, "items": items})


@app.get("/gallery")
async def gallery_page() -> FileResponse:
    return FileResponse(os.path.join(FRONTEND, "index.html"))


# ================= Telegram WebApp login =================


def validate_tg_init_data(init_data: str) -> dict | None:
    try:
        from urllib.parse import parse_qsl

        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            return None
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        hash_ = pairs.pop("hash", "")
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret_key = hashlib.sha256(bot_token.encode()).digest()
        calc = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, hash_):
            return None
        import json

        return json.loads(pairs["user"])
    except Exception:
        return None


@app.post("/api/tg-login")
async def tg_login(req: Request) -> JSONResponse:
    body = await req.json()
    init_data = (body.get("initData") or "").strip()
    if not init_data:
        return JSONResponse({"error": "initData kerak"}, status_code=400)
    tg_user = validate_tg_init_data(init_data)
    if not tg_user:
        return JSONResponse(
            {"error": "Telegram ma'lumotlari tasdiqlanmadi"}, status_code=401
        )
    tg_id = str(tg_user.get("id"))
    db = get_db()
    existing = db.get_user_by_telegram(tg_id)
    if existing:
        user = existing
    else:
        username = tg_user.get("username") or tg_user.get("first_name") or "tg_user"
        user = db.create_telegram_user(
            tg_id,
            username,
            tg_user.get("first_name") or "",
            tg_user.get("photo_url") or "",
        )
    token = new_token()
    db.set_user_token(user["id"], token)
    return JSONResponse(
        {
            "success": True,
            "token": token,
            "user": {"name": user["name"], "tg_id": user["tg_id"]},
        }
    )


@app.post("/api/tg-bind")
async def tg_bind(req: Request) -> JSONResponse:
    """Joriy hisobga Telegramni bog'lash (mavjud foydalanuvchi uchun)."""
    body = await req.json()
    token = (body.get("token") or "").strip()
    init_data = (body.get("initData") or "").strip()
    if not token:
        return JSONResponse({"error": "Avval tizimga kiring"}, status_code=401)
    if not init_data:
        return JSONResponse({"error": "initData kerak"}, status_code=400)
    db = get_db()
    user = db.get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Avval tizimga kiring"}, status_code=401)
    tg_user = validate_tg_init_data(init_data)
    if not tg_user:
        return JSONResponse(
            {"error": "Telegram ma'lumotlari tasdiqlanmadi"}, status_code=401
        )
    tg_id = str(tg_user.get("id"))
    taken = db.get_user_by_telegram(tg_id)
    if taken and taken["id"] != user["id"]:
        return JSONResponse(
            {"error": "Bu Telegram hisob boshqa akkauntga bog'langan"}, status_code=409
        )
    db.bind_telegram(user["id"], tg_id)
    return JSONResponse({"success": True, "tg_id": int(tg_id)})


@app.post("/api/tg-unbind")
async def tg_unbind(req: Request) -> JSONResponse:
    body = await req.json()
    token = (body.get("token") or "").strip()
    if not token:
        return JSONResponse({"error": "Avval tizimga kiring"}, status_code=401)
    db = get_db()
    user = db.get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Avval tizimga kiring"}, status_code=401)
    db.unbind_telegram(user["id"])
    return JSONResponse({"success": True})


# ================= Musiqa generatsiya (Suno API) =================


class MusicRequest(BaseModel):
    prompt: str  # Qo'shiq mavzusi/matni
    tags: str = "pop, uzbek, energetic"
    title: str = "InomjonAI Track"
    instrumental: bool = False
    token: str | None = None


@app.post("/api/generate-music")
async def generate_music(req: MusicRequest) -> JSONResponse:
    """Qo'shiq/musiqa generatsiya: Pollinations (elevenmusic) → Suno API."""
    hint = (
        "Kalit holati: gen.pollinations.ai dan `Bearer` so'rov talab qilinadi. "
        "Yangi kalit: https://enter.pollinations.ai (bepul kreditlar bor). "
        "Yoki Suno lokal: `git clone https://github.com/suno-ai/suno-api && npm install && npm start` (port 3000, SUNO_API_URL env)"
    )
    try:
        import pollinations

        if not pollinations.available():
            return JSONResponse(
                {"error": "POLLINATIONS_API_KEY o'rnatilmagan serverda", "hint": hint},
                status_code=503,
            )
        data, err = pollinations.generate_music(req.prompt)
        if not data:
            if err == "HTTP 401":
                return JSONResponse(
                    {
                        "error": "Pollinations API kaliti eskirgan yoki bekor qilingan (401)",
                        "hint": hint,
                    },
                    status_code=502,
                )
            if err and err.startswith("HTTP 402"):
                return JSONResponse(
                    {"error": "Pollinations balansi yetarli emas (402)", "hint": hint},
                    status_code=402,
                )
            raise RuntimeError(err or "javob yo'q")
        name = f"poll_music_{int(time.time() * 1000) % 1000000}.mp3"
        path = os.path.join(GEN_DIR, name)
        with open(path, "wb") as f:
            f.write(data)
        _record_gen(req, "music", _gen_url(path))
        return JSONResponse(
            {
                "success": True,
                "audio_url": _gen_url(path),
                "provider": "pollinations",
            }
        )
    except Exception as e:
        return JSONResponse(
            {"error": f"Musiqa generatsiya xato: {e}", "hint": hint},
            status_code=503,
        )


class VoiceRequest(BaseModel):
    text: str
    voice: str = ""  # af_heart, af_bella, am_onyx, ... (ixtiyoriy)
    token: str | None = None


@app.post("/api/generate-voice")
async def generate_voice(req: VoiceRequest) -> JSONResponse:
    """Matndi ovozga aylantirish (TTS): ElevenLabs → Pollinations (fallback)."""
    if len(req.text.strip()) < 1:
        return JSONResponse({"error": "matn kiritilmadi"}, status_code=400)
    text = req.text.strip()
    voice_id = req.voice if len(req.voice or "") == 20 else None

    try:
        import elevenlabs

        if elevenlabs.available():
            data, err = elevenlabs.generate_voice(text, voice=voice_id)
            if data:
                name = f"el_voice_{int(time.time() * 1000) % 1000000}.mp3"
                path = os.path.join(GEN_DIR, name)
                with open(path, "wb") as f:
                    f.write(data)
                _record_gen(req, "voice", _gen_url(path))
                return JSONResponse(
                    {
                        "success": True,
                        "audio_url": _gen_url(path),
                        "provider": "elevenlabs",
                    }
                )
    except Exception:
        pass

    try:
        import pollinations

        if not pollinations.available():
            raise RuntimeError("POLLINATIONS_API_KEY o'rnatilmagan")
        data, err = pollinations.generate_audio(text, voice=req.voice or None)
        if not data:
            if err == "HTTP 401":
                raise RuntimeError("Pollinations API kaliti eskirgan (401)")
            if err and err.startswith("HTTP 402"):
                raise RuntimeError(
                    "Pollinations balansi 0 — enter.pollinations.ai dan to'ldiring (402)"
                )
            raise RuntimeError(err or "javob yo'q")
        name = f"poll_voice_{int(time.time() * 1000) % 1000000}.mp3"
        path = os.path.join(GEN_DIR, name)
        with open(path, "wb") as f:
            f.write(data)
        _record_gen(req, "voice", _gen_url(path))
        return JSONResponse(
            {"success": True, "audio_url": _gen_url(path), "provider": "pollinations"}
        )
    except Exception as e:
        return JSONResponse({"error": f"Ovoz generatsiya xato: {e}"}, status_code=503)


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
    email = req.email.strip().lower()
    login = email or req.username.strip().lower()
    if len(login) < 3:
        return JSONResponse(
            {"error": "email kamida 3 belgi bo'lishi kerak"}, status_code=400
        )
    if not email or "@" not in email or "." not in email:
        return JSONResponse(
            {"error": "to'g'ri email kiriting (masalan: ism@mail.com)"}, status_code=400
        )
    if len(req.password) < 4:
        return JSONResponse(
            {"error": "parol kamida 4 belgi bo'lishi kerak"}, status_code=400
        )
    if not req.name.strip():
        return JSONResponse({"error": "ismingizni kiriting"}, status_code=400)
    user_id = db.register_user(
        login,
        req.password and hash_password(req.password),
        req.name,
        req.surname or "",
        email,
        req.phone or "",
        req.client_id,
    )
    if user_id is None:
        return JSONResponse(
            {"error": "bu email band — boshqasini tanlang"}, status_code=409
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
            "surname": user.get("surname") or "",
            "email": user.get("email") or "",
            "phone": user.get("phone") or "",
        }
    )


@app.post("/api/login")
def login(req: LoginRequest) -> JSONResponse:
    db = get_db()
    email = req.email.strip().lower()
    login = email or req.username.strip().lower()
    user = db.get_user_by_email(login) if login else None
    if not user:
        user = db.get_user_by_username(login) if login else None
    if (
        not user
        or not user.get("password_hash")
        or not verify_password(req.password, user["password_hash"])
    ):
        return JSONResponse({"error": "email yoki parol noto'g'ri"}, status_code=401)
    if req.client_id:
        db.transfer_guest(req.client_id, user["id"])
    token = new_token()
    db.set_token(user["id"], token)
    return JSONResponse(
        {
            "token": token,
            "username": user["username"],
            "name": user["name"] or user["username"],
            "surname": user.get("surname") or "",
            "email": user.get("email") or "",
            "phone": user.get("phone") or "",
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
            "surname": user.get("surname") or "",
            "email": user.get("email") or "",
            "phone": user.get("phone") or "",
            "telegram_id": user.get("telegram_id") or None,
        }
    )


@app.post("/api/profile")
def update_profile(req: ProfileUpdateRequest) -> JSONResponse:
    db = get_db()
    user = db.get_user_by_token(req.token)
    if not user:
        return JSONResponse({"error": "kirish talab qilinadi"}, status_code=401)
    db.update_profile(
        user["id"],
        name=(req.name.strip()[:40] or None),
        surname=(req.surname.strip()[:40] or None),
        phone=(req.phone.strip()[:30] or None),
    )
    user = db.get_user(user["id"])
    return JSONResponse(
        {
            "ok": True,
            "username": user["username"],
            "name": user["name"] or user["username"],
            "surname": user.get("surname") or "",
            "email": user.get("email") or "",
            "phone": user.get("phone") or "",
        }
    )


@app.post("/api/change-password")
def change_password(req: ChangePasswordRequest) -> JSONResponse:
    db = get_db()
    user = db.get_user_by_token(req.token)
    if not user:
        return JSONResponse({"error": "kirish talab qilinadi"}, status_code=401)
    if len(req.new_password) < 4:
        return JSONResponse(
            {"error": "yangi parol kamida 4 belgidan iborat bo'lishi kerak"},
            status_code=400,
        )
    old_hash = db.get_password_hash(user["id"]) or ""
    if not verify_password(req.old_password, old_hash):
        return JSONResponse({"error": "eski parol noto'g'ri"}, status_code=400)
    db.set_password_hash(user["id"], hash_password(req.new_password))
    return JSONResponse({"ok": True})


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


class KeyCreateRequest(BaseModel):
    token: str = ""
    name: str = ""
    models: list[str] = []


@app.post("/api/key/create")
def api_key_create(req: KeyCreateRequest) -> JSONResponse:
    db = get_db()
    user = db.get_user_by_token(req.token)
    if not user:
        return JSONResponse({"error": "kirish talab qilinadi"}, status_code=401)
    name = (req.name or "").strip()[:60] or "Bosh kalit"
    models = req.models[:20]
    key = new_token()
    db.set_api_key(user["id"], key, name=name, models=",".join(models))
    return JSONResponse(
        {
            "key": key,
            "name": name,
            "models": models,
            "limit_per_minute": _API_RATE_LIMIT,
        }
    )


@app.get("/api/key")
def api_key_get(token: str = "") -> JSONResponse:
    db = get_db()
    user = db.get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "kirish talab qilinadi"}, status_code=401)
    row = db.get_api_key(user["id"])
    if not row:
        return JSONResponse({"key": None})
    models = [m for m in (row.get("models") or "").split(",") if m]
    return JSONResponse(
        {
            "key": row["key"],
            "name": row.get("name") or "Bosh kalit",
            "models": models,
            "limit_per_minute": _API_RATE_LIMIT,
        }
    )


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


@app.delete("/api/conversations/{conv_id}")
def conversation_delete(conv_id: int, token: str = "") -> JSONResponse:
    db = get_db()
    user = db.get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "kirish talab qilinadi"}, status_code=401)
    if not db.delete_conversation(conv_id, user["id"]):
        return JSONResponse({"error": "suhbat topilmadi"}, status_code=404)
    return JSONResponse({"ok": True})


@app.get("/api/stats")
def user_stats(token: str = "") -> JSONResponse:
    db = get_db()
    user = db.get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "kirish talab qilinadi"}, status_code=401)
    return JSONResponse(db.user_stats(user["id"]))


@app.get("/api/models")
def list_models() -> JSONResponse:
    """Barcha provider modellari ro'yxati (OpenRouter + Cohere + Pollinations, 5 daqiqa cache)."""
    import time as _time

    now = _time.time()
    if _MODELS_CACHE["ts"] and now - _MODELS_CACHE["ts"] < 300:
        return JSONResponse({"items": _MODELS_CACHE["items"]})

    items: list = []

    # 1) OpenRouter
    url = OPENROUTER_BASE_URL + "/models"
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + api_key,
            "User-Agent": "InomjonAI/1.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        items.extend(
            {
                "id": m["id"],
                "name": m.get("name", m["id"]),
                "ctx": m.get("context_length", 0),
                "pricing": m.get("pricing", {}),
                "provider": "openrouter",
            }
            for m in data.get("data", [])
        )
    except Exception:
        pass

    # 2) Cohere
    cohere_key = os.environ.get("COHERE_API_KEY", "").strip()
    if cohere_key:
        try:
            req2 = urllib.request.Request(
                "https://api.cohere.com/v2/models",
                headers={
                    "Authorization": "Bearer " + cohere_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req2, timeout=15) as r:
                data2 = json.loads(r.read().decode("utf-8"))
            items.extend(
                {
                    "id": m["name"],
                    "name": m["name"],
                    "ctx": m.get("context_length", 0),
                    "pricing": {},
                    "provider": "cohere",
                    "endpoints": m.get("endpoints", []),
                }
                for m in data2.get("models", [])
            )
        except Exception:
            pass

    # 3) Pollinations
    poll_key = os.environ.get("POLLINATIONS_API_KEY", "").strip()
    if poll_key:
        try:
            req3 = urllib.request.Request(
                "https://gen.pollinations.ai/models",
                headers={"Authorization": "Bearer " + poll_key},
            )
            with urllib.request.urlopen(req3, timeout=20) as r:
                data3 = json.loads(r.read().decode("utf-8"))
            items.extend(
                {
                    "id": m.get("name", m.get("id", "")),
                    "name": m.get("title", m.get("name", "")),
                    "ctx": m.get("max_referenced_tokens") or m.get("context_length", 0),
                    "pricing": m.get("pricing", {}),
                    "provider": "pollinations",
                    "category": m.get("category", ""),
                }
                for m in data3
            )
        except Exception:
            pass

    _MODELS_CACHE["items"] = items
    _MODELS_CACHE["ts"] = now
    return JSONResponse({"items": items})


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
