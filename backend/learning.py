"""Auto-o'rganish: suhbatlar asosida bilim bazasini kengaytirish."""

from db import Database

MIN_SOURCE = 3
MIN_LEN = 2
# Faqat "knowledge" manbali (bilim bazasidagi) javoblar o'rganiladi.
# Web-qidiruv javoblari xom bo'lishi mumkin — ularni bilim bazasiga ko'chirmaymiz.
LEARNABLE = ("knowledge",)


def learn_pair(db: Database, q_id: int, a_id: int) -> bool:
    """Bitta savol-javob juftligini darhol bilim bazasiga o'tkazadi."""
    q = db.conn.execute("SELECT text FROM messages WHERE id = ?", (q_id,)).fetchone()
    a = db.conn.execute("SELECT text FROM messages WHERE id = ?", (a_id,)).fetchone()
    if not q or not a:
        return False
    if len(q["text"].strip()) < 4 or len(a["text"].strip()) < 10:
        return False
    if "Internetdan qidirib topdim" in a["text"] or "Internetdan topildi" in a["text"]:
        return False
    return db.add_knowledge(q["text"], a["text"], source="learning")


def learn_from_messages(db: Database, min_source: int = MIN_SOURCE) -> int:
    """Foydalanuvchilar ma'qullagan (👍) savol-javob juftlarini bilim bazasiga qo'shadi.

    Qoida: AI javobi knowledge manbasidan bo'lib, foydalanuvchi 👍 bosgan
    bo'lsa, shu juftlik 'learning' manbali bilimga aylanadi.
    """
    pairs = db.recent_pairs()
    learned = 0
    for p in pairs:
        if p.get("source") not in LEARNABLE:
            continue
        rating = db.get_rating(p["a_id"])
        if rating == 1:
            if learn_pair(db, p["q_id"], p["a_id"]):
                learned += 1
    return learned


def collect_unanswered(db: Database, min_len: int = MIN_LEN) -> int:
    """Fallback javob olgan savollarni o'rganish navbatiga qo'yadi."""
    pairs = db.recent_pairs()
    added = 0
    for p in pairs:
        if p.get("source") != "fallback":
            continue
        if len(p["q"].split()) < min_len:
            continue
        try:
            db.add_unanswered(p["q"], p["user_id"])
            added += 1
        except Exception:
            pass
    return added
