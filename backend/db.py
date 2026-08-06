import os
import sqlite3
from threading import RLock

DB_PATH = os.environ.get(
    "DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "ai.db")
)


class Database:
    def __init__(self, path: str = DB_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self._lock = RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._migrate()

    def _create_tables(self):
        with self._lock:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id   INTEGER UNIQUE,
                    client_id     TEXT UNIQUE,
                    username      TEXT UNIQUE,
                    password_hash TEXT,
                    name          TEXT,
                    token         TEXT,
                    created_at    TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER NOT NULL,
                    title      TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id         INTEGER NOT NULL,
                    conversation_id INTEGER,
                    role            TEXT NOT NULL,
                    text            TEXT NOT NULL,
                    rating          INTEGER,
                    source          TEXT,
                    created_at      TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS knowledge (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    question   TEXT UNIQUE,
                    answer     TEXT NOT NULL,
                    source     TEXT DEFAULT 'seed',
                    weight     INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS unanswered (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    question   TEXT NOT NULL,
                    user_id    INTEGER,
                    answer     TEXT,
                    status     TEXT DEFAULT 'new',
                    created_at TEXT DEFAULT (datetime('now'))
                );
                """
            )

    def _migrate(self):
        """Eski DB'lardan yangi ustunlarni qo'shish."""
        with self._lock:
            user_cols = [r[1] for r in self.conn.execute("PRAGMA table_info(users)")]
            for col in ("username", "password_hash", "name", "token"):
                if col not in user_cols:
                    self.conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
            msg_cols = [r[1] for r in self.conn.execute("PRAGMA table_info(messages)")]
            if "conversation_id" not in msg_cols:
                self.conn.execute(
                    "ALTER TABLE messages ADD COLUMN conversation_id INTEGER"
                )

    # ================= users =================
    def get_or_create_user(
        self, telegram_id: int | None = None, client_id: str | None = None
    ) -> int:
        with self._lock:
            if client_id is not None:
                cur = self.conn.execute(
                    "SELECT id FROM users WHERE client_id = ?", (client_id,)
                )
                row = cur.fetchone()
                if row:
                    return row["id"]
                cur = self.conn.execute(
                    "INSERT INTO users (client_id) VALUES (?)", (client_id,)
                )
                assert cur.lastrowid is not None
                return cur.lastrowid
            if telegram_id is not None:
                cur = self.conn.execute(
                    "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
                )
                row = cur.fetchone()
                if row:
                    return row["id"]
                cur = self.conn.execute(
                    "INSERT INTO users (telegram_id) VALUES (?)", (telegram_id,)
                )
                assert cur.lastrowid is not None
                return cur.lastrowid
            cur = self.conn.execute("INSERT INTO users DEFAULT VALUES")
            assert cur.lastrowid is not None
            return cur.lastrowid

    def get_user(self, user_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT id, username, name, token, client_id FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_user_by_token(self, token: str) -> dict | None:
        row = self.conn.execute(
            "SELECT id, username, name, token, client_id FROM users WHERE token = ?",
            (token,),
        ).fetchone()
        return dict(row) if row else None

    def get_user_by_username(self, username: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.lower(),)
        ).fetchone()
        return dict(row) if row else None

    def register_user(
        self,
        username: str,
        password_hash: str,
        name: str = "",
        client_id: str | None = None,
    ) -> int | None:
        username = username.strip().lower()
        if not username or not password_hash:
            return None
        with self._lock:
            exists = self.conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if exists:
                return None
            cur = self.conn.execute(
                "INSERT INTO users (username, password_hash, name) VALUES (?, ?, ?)",
                (username, password_hash, name or username),
            )
            assert cur.lastrowid is not None
            new_id = cur.lastrowid
            if client_id:
                guest = self.conn.execute(
                    "SELECT id FROM users WHERE client_id = ?", (client_id,)
                ).fetchone()
                if guest and guest["id"] != new_id:
                    gid = guest["id"]
                    self.conn.execute(
                        "UPDATE conversations SET user_id = ? WHERE user_id = ?",
                        (new_id, gid),
                    )
                    self.conn.execute(
                        "UPDATE messages SET user_id = ? WHERE user_id = ?",
                        (new_id, gid),
                    )
                    self.conn.execute("DELETE FROM users WHERE id = ?", (gid,))
            return new_id

    def set_token(self, user_id: int, token: str) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE users SET token = ? WHERE id = ?", (token, user_id)
            )

    def update_name(self, user_id: int, name: str) -> None:
        with self._lock:
            self.conn.execute("UPDATE users SET name = ? WHERE id = ?", (name, user_id))

    # ================= conversations =================
    def create_conversation(self, user_id: int, title: str) -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
                (user_id, title[:60] or "Yangi suhbat"),
            )
            assert cur.lastrowid is not None
            return cur.lastrowid

    def get_conversation(self, conv_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_conversations(self, user_id: int) -> list:
        rows = self.conn.execute(
            """
            SELECT c.id, c.title, c.created_at,
                   (SELECT count(*) FROM messages m WHERE m.conversation_id = c.id) AS msg_count
            FROM conversations c
            WHERE c.user_id = ?
            ORDER BY c.id DESC LIMIT 100
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def conversation_messages(self, conv_id: int, user_id: int) -> list:
        rows = self.conn.execute(
            """
            SELECT id, role, text, rating, source, created_at
            FROM messages
            WHERE conversation_id = ? AND user_id = ?
            ORDER BY id
            """,
            (conv_id, user_id),
        ).fetchall()
        return [dict(r) for r in rows]

    # ================= messages =================
    def add_message(
        self,
        user_id: int,
        role: str,
        text: str,
        source: str | None = None,
        conversation_id: int | None = None,
    ) -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO messages (user_id, role, text, source, conversation_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, role, text, source, conversation_id),
            )
            assert cur.lastrowid is not None
            return cur.lastrowid

    def rate_message(self, message_id: int, rating: int) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE messages SET rating = ? WHERE id = ?", (rating, message_id)
            )

    def get_rating(self, message_id: int) -> int | None:
        row = self.conn.execute(
            "SELECT rating FROM messages WHERE id = ?", (message_id,)
        ).fetchone()
        return row["rating"] if row else None

    def recent_pairs(self, limit: int = 500):
        rows = self.conn.execute(
            """
            SELECT m1.user_id, m1.id AS q_id, m1.text AS q, m2.id AS a_id, m2.text AS a, m2.source
            FROM messages m1
            JOIN messages m2 ON m2.id = m1.id + 1 AND m2.user_id = m1.user_id
            WHERE m1.role = 'user' AND m2.role = 'assistant'
            ORDER BY m1.id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ================= knowledge =================
    def get_knowledge(self) -> list:
        rows = self.conn.execute(
            "SELECT id, question, answer, weight, source FROM knowledge"
        ).fetchall()
        return [dict(r) for r in rows]

    def add_knowledge(self, question: str, answer: str, source: str = "admin") -> bool:
        question = question.strip()
        if not question or not answer.strip():
            return False
        with self._lock:
            try:
                self.conn.execute(
                    "INSERT INTO knowledge (question, answer, source) VALUES (?, ?, ?)",
                    (question, answer, source),
                )
            except sqlite3.IntegrityError:
                self.conn.execute(
                    "UPDATE knowledge SET answer = ?, source = ? WHERE question = ?",
                    (answer, source, question),
                )
            return True

    def add_seed_knowledge(self, pairs: list) -> None:
        for q, a in pairs:
            self.add_knowledge(q, a, source="seed")

    # ================= unanswered =================
    def add_unanswered(self, question: str, user_id: int) -> None:
        existing = self.conn.execute(
            "SELECT id FROM unanswered WHERE question = ? AND status = 'new' LIMIT 1",
            (question.strip(),),
        ).fetchone()
        if existing:
            return
        with self._lock:
            self.conn.execute(
                "INSERT INTO unanswered (question, user_id) VALUES (?, ?)",
                (question.strip(), user_id),
            )

    def get_unanswered(self, status: str = "new") -> list:
        rows = self.conn.execute(
            "SELECT * FROM unanswered WHERE status = ? ORDER BY created_at DESC LIMIT 200",
            (status,),
        ).fetchall()
        return [dict(r) for r in rows]

    def answer_unanswered(self, unanswered_id: int, answer: str) -> None:
        q = self.conn.execute(
            "SELECT question FROM unanswered WHERE id = ?", (unanswered_id,)
        ).fetchone()
        if q is None:
            return
        with self._lock:
            self.conn.execute(
                "UPDATE unanswered SET answer = ?, status = 'answered' WHERE id = ?",
                (answer, unanswered_id),
            )
            self.add_knowledge(q["question"], answer, source="learning")


_db_instance: Database | None = None


def get_db() -> Database:
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
