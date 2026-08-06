import os
import tempfile
import threading
import time

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from auth import hash_password, new_token, verify_password
from brain import brain
from db import get_db
from learning import collect_unanswered, learn_from_messages, learn_pair
from seeds import SEED_KNOWLEDGE
from vision import analyze as vision_analyze

app = FastAPI(title="Neura AI")

ADMIN_KEY = os.environ.get("ADMIN_KEY", "admin123")

ROOT = os.path.join(os.path.dirname(__file__), "..")
FRONTEND = os.path.join(ROOT, "frontend")


class ChatRequest(BaseModel):
    message: str
    user_id: str | int | None = None
    telegram_id: int | None = None
    token: str | None = None
    conversation_id: int | None = None


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
    db.add_seed_knowledge(SEED_KNOWLEDGE)


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


@app.get("/sw.js")
def sw() -> FileResponse:
    return FileResponse(os.path.join(FRONTEND, "sw.js"), media_type="text/javascript")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


# ================= suhbat =================


@app.post("/api/chat")
def chat(req: ChatRequest) -> JSONResponse:
    db = get_db()

    user = db.get_user_by_token(req.token) if req.token else None
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
    reply, source = brain.answer(req.message, db.get_knowledge())
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
        guest = db.get_user_by_token(req.client_id)
        guest_row = db.conn.execute(
            "SELECT id FROM users WHERE client_id = ?", (req.client_id,)
        ).fetchone()
        if guest_row and guest_row["id"] != user["id"]:
            gid = guest_row["id"]
            db.conn.execute(
                "UPDATE conversations SET user_id = ? WHERE user_id = ?",
                (user["id"], gid),
            )
            db.conn.execute(
                "UPDATE messages SET user_id = ? WHERE user_id = ?", (user["id"], gid)
            )
            db.conn.execute("DELETE FROM users WHERE id = ?", (gid,))
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
