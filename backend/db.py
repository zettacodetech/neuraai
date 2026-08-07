"""Ma'lumotlar bazasi — SQLite (lokal) yoki PostgreSQL (Railway).

`DATABASE_URL` muhit o'zgaruvchisi o'rnatilgan bo'lsa PostgreSQL ishlatiladi,
aks holda SQLite (data/ai.db). Ikkala rejim ham bir xil API beradi.
"""

import os
import sqlite3
from threading import RLock

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DB_PATH = os.environ.get(
    "DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "ai.db")
)

_SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER UNIQUE,
    client_id     TEXT UNIQUE,
    username      TEXT UNIQUE,
    password_hash TEXT,
    name          TEXT,
    surname       TEXT,
    email         TEXT,
    phone         TEXT,
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

CREATE TABLE IF NOT EXISTS api_keys (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL UNIQUE,
    key        TEXT NOT NULL UNIQUE,
    name       TEXT,
    models     TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

_PG_DDL = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id            BIGSERIAL PRIMARY KEY,
        telegram_id   BIGINT UNIQUE,
        client_id     TEXT UNIQUE,
        username      TEXT UNIQUE,
        password_hash TEXT,
        name          TEXT,
        surname       TEXT,
        email         TEXT,
        phone         TEXT,
        token         TEXT,
        created_at    TIMESTAMPTZ DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id         BIGSERIAL PRIMARY KEY,
        user_id    BIGINT NOT NULL,
        title      TEXT,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id              BIGSERIAL PRIMARY KEY,
        user_id         BIGINT NOT NULL,
        conversation_id BIGINT,
        role            TEXT NOT NULL,
        text            TEXT NOT NULL,
        rating          INTEGER,
        source          TEXT,
        created_at      TIMESTAMPTZ DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge (
        id         BIGSERIAL PRIMARY KEY,
        question   TEXT UNIQUE,
        answer     TEXT NOT NULL,
        source     TEXT DEFAULT 'seed',
        weight     INTEGER DEFAULT 1,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS unanswered (
        id         BIGSERIAL PRIMARY KEY,
        question   TEXT NOT NULL,
        user_id    BIGINT,
        answer     TEXT,
        status     TEXT DEFAULT 'new',
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS api_keys (
        id         BIGSERIAL PRIMARY KEY,
        user_id    BIGINT NOT NULL UNIQUE,
        key        TEXT NOT NULL UNIQUE,
        name       TEXT,
        models     TEXT,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
]


def _pg_sql(sql: str) -> str:
    """SQLite '?' placeholderlarini PostgreSQL '%s' ga o'tkazadi."""
    return sql.replace("?", "%s")


class Database:
    def __init__(self, path: str = DB_PATH, url: str = DATABASE_URL):
        self._lock = RLock()
        self.pg = bool(url)
        if self.pg:
            import psycopg2
            import psycopg2.extras

            self._psycopg2 = psycopg2
            self.conn = psycopg2.connect(url, connect_timeout=10)
            self.conn.autocommit = True
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self.path = path
            self.conn = sqlite3.connect(
                path, check_same_thread=False, isolation_level=None
            )
            self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._migrate()

    # ================= ichki yordamchilar =================
    def _rows(self, sql: str, params: tuple = ()) -> list:
        if self.pg:
            import datetime

            with self.conn.cursor(
                cursor_factory=self._psycopg2.extras.RealDictCursor
            ) as cur:
                cur.execute(_pg_sql(sql), params)
                return [
                    {
                        k: (
                            v.strftime("%Y-%m-%d %H:%M:%S")
                            if isinstance(v, datetime.datetime)
                            else v
                        )
                        for k, v in dict(r).items()
                    }
                    for r in cur.fetchall()
                ]
        return self.conn.execute(sql, params).fetchall()

    def _row(self, sql: str, params: tuple = ()) -> dict | None:
        rows = self._rows(sql, params)
        return rows[0] if rows else None

    def _execute(self, sql: str, params: tuple = ()) -> None:
        if self.pg:
            with self.conn.cursor() as cur:
                cur.execute(_pg_sql(sql), params)
        else:
            self.conn.execute(sql, params)

    def _insert(self, sql: str, params: tuple = ()) -> int:
        if self.pg:
            with self.conn.cursor() as cur:
                cur.execute(_pg_sql(sql) + " RETURNING id", params)
                row = cur.fetchone()
                assert row is not None
                return int(row[0])
        cur = self.conn.execute(sql, params)
        assert cur.lastrowid is not None
        return cur.lastrowid

    def _create_tables(self):
        with self._lock:
            if self.pg:
                for ddl in _PG_DDL:
                    with self.conn.cursor() as cur:
                        cur.execute(ddl)
            else:
                self.conn.executescript(_SQLITE_DDL)

    def _migrate(self):
        """Eski sxemadan yangi ustunlarni qo'shish (SQLite ham, Postgres ham)."""
        if self.pg:
            with self._lock:
                with self.conn.cursor() as cur:
                    for col in (
                        "username",
                        "password_hash",
                        "name",
                        "surname",
                        "email",
                        "phone",
                        "token",
                        "client_id",
                    ):
                        cur.execute(
                            f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} TEXT"
                        )
                    for col in ("name", "models"):
                        cur.execute(
                            f"ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS {col} TEXT"
                        )
                self.conn.commit()
            return
        with self._lock:
            user_cols = [r[1] for r in self.conn.execute("PRAGMA table_info(users)")]
            for col in (
                "username",
                "password_hash",
                "name",
                "surname",
                "email",
                "phone",
                "token",
            ):
                if col not in user_cols:
                    self.conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
            msg_cols = [r[1] for r in self.conn.execute("PRAGMA table_info(messages)")]
            if "conversation_id" not in msg_cols:
                self.conn.execute(
                    "ALTER TABLE messages ADD COLUMN conversation_id INTEGER"
                )
            key_cols = [r[1] for r in self.conn.execute("PRAGMA table_info(api_keys)")]
            for col in ("name", "models"):
                if col not in key_cols:
                    self.conn.execute(f"ALTER TABLE api_keys ADD COLUMN {col} TEXT")

    # ================= users =================
    def get_or_create_user(
        self, telegram_id: int | None = None, client_id: str | None = None
    ) -> int:
        with self._lock:
            if client_id is not None:
                row = self._row(
                    "SELECT id FROM users WHERE client_id = ?", (client_id,)
                )
                if row:
                    return row["id"]
                return self._insert(
                    "INSERT INTO users (client_id) VALUES (?)", (client_id,)
                )
            if telegram_id is not None:
                row = self._row(
                    "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
                )
                if row:
                    return row["id"]
                return self._insert(
                    "INSERT INTO users (telegram_id) VALUES (?)", (telegram_id,)
                )
            return self._insert("INSERT INTO users DEFAULT VALUES")

    def transfer_guest(self, client_id: str, user_id: int) -> None:
        row = self._row("SELECT id FROM users WHERE client_id = ?", (client_id,))
        if row and row["id"] != user_id:
            gid = row["id"]
            self._execute(
                "UPDATE conversations SET user_id = ? WHERE user_id = ?",
                (user_id, gid),
            )
            self._execute(
                "UPDATE messages SET user_id = ? WHERE user_id = ?",
                (user_id, gid),
            )
            self._execute("DELETE FROM users WHERE id = ?", (gid,))

    def get_user(self, user_id: int) -> dict | None:
        row = self._row(
            "SELECT id, username, name, surname, email, phone, token, client_id "
            "FROM users WHERE id = ?",
            (user_id,),
        )
        return dict(row) if row else None

    def get_user_by_token(self, token: str) -> dict | None:
        row = self._row(
            "SELECT id, username, name, surname, email, phone, token, client_id "
            "FROM users WHERE token = ?",
            (token,),
        )
        return dict(row) if row else None

    def get_user_by_username(self, username: str) -> dict | None:
        row = self._row("SELECT * FROM users WHERE username = ?", (username.lower(),))
        return dict(row) if row else None

    def register_user(
        self,
        username: str,
        password_hash: str,
        name: str = "",
        surname: str = "",
        email: str = "",
        phone: str = "",
        client_id: str | None = None,
    ) -> int | None:
        username = username.strip().lower()
        if not username or not password_hash:
            return None
        with self._lock:
            exists = self._row("SELECT id FROM users WHERE username = ?", (username,))
            if exists:
                return None
            if email:
                dup_email = self._row(
                    "SELECT id FROM users WHERE email = ?", (email.strip().lower(),)
                )
                if dup_email:
                    return None
            new_id = self._insert(
                "INSERT INTO users (username, password_hash, name, surname, email, phone) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    username,
                    password_hash,
                    name or username,
                    surname,
                    email.strip().lower(),
                    phone,
                ),
            )
            if client_id:
                guest = self._row(
                    "SELECT id FROM users WHERE client_id = ?", (client_id,)
                )
                if guest and guest["id"] != new_id:
                    gid = guest["id"]
                    self._execute(
                        "UPDATE conversations SET user_id = ? WHERE user_id = ?",
                        (new_id, gid),
                    )
                    self._execute(
                        "UPDATE messages SET user_id = ? WHERE user_id = ?",
                        (new_id, gid),
                    )
                    self._execute("DELETE FROM users WHERE id = ?", (gid,))
            return new_id

    def set_token(self, user_id: int, token: str) -> None:
        with self._lock:
            self._execute("UPDATE users SET token = ? WHERE id = ?", (token, user_id))

    # ================= api keys (bepul, limitle) =================
    def set_api_key(
        self,
        user_id: int,
        key: str,
        name: str = "",
        models: str = "",
    ) -> None:
        with self._lock:
            self._execute(
                "INSERT INTO api_keys (user_id, key, name, models) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET "
                "key = excluded.key, name = COALESCE(excluded.name, api_keys.name), "
                "models = COALESCE(excluded.models, api_keys.models)",
                (user_id, key, name, models),
            )

    def get_api_key(self, user_id: int) -> dict | None:
        row = self._row(
            "SELECT id, user_id, key, name, models, created_at "
            "FROM api_keys WHERE user_id = ?",
            (user_id,),
        )
        return dict(row) if row else None

    def delete_api_key(self, user_id: int) -> None:
        with self._lock:
            self._execute("DELETE FROM api_keys WHERE user_id = ?", (user_id,))

    def get_user_by_api_key(self, key: str) -> dict | None:
        row = self._row(
            "SELECT u.id, u.username, u.name, u.client_id, u.token "
            "FROM api_keys k JOIN users u ON u.id = k.user_id WHERE k.key = ?",
            (key,),
        )
        return dict(row) if row else None

    def update_name(self, user_id: int, name: str) -> None:
        with self._lock:
            self._execute("UPDATE users SET name = ? WHERE id = ?", (name, user_id))

    # ================= conversations =================
    def create_conversation(self, user_id: int, title: str) -> int:
        with self._lock:
            return self._insert(
                "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
                (user_id, title[:60] or "Yangi suhbat"),
            )

    def get_conversation(self, conv_id: int) -> dict | None:
        row = self._row("SELECT * FROM conversations WHERE id = ?", (conv_id,))
        return dict(row) if row else None

    def list_conversations(self, user_id: int) -> list:
        rows = self._rows(
            """
            SELECT c.id, c.title, c.created_at,
                   (SELECT count(*) FROM messages m WHERE m.conversation_id = c.id) AS msg_count
            FROM conversations c
            WHERE c.user_id = ?
            ORDER BY c.id DESC LIMIT 100
            """,
            (user_id,),
        )
        return [dict(r) for r in rows]

    def conversation_messages(self, conv_id: int, user_id: int) -> list:
        rows = self._rows(
            """
            SELECT id, role, text, rating, source, created_at
            FROM messages
            WHERE conversation_id = ? AND user_id = ?
            ORDER BY id
            """,
            (conv_id, user_id),
        )
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
            return self._insert(
                "INSERT INTO messages (user_id, role, text, source, conversation_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, role, text, source, conversation_id),
            )

    def rate_message(self, message_id: int, rating: int) -> None:
        with self._lock:
            self._execute(
                "UPDATE messages SET rating = ? WHERE id = ?", (rating, message_id)
            )

    def get_rating(self, message_id: int) -> int | None:
        row = self._row("SELECT rating FROM messages WHERE id = ?", (message_id,))
        return row["rating"] if row else None

    def recent_pairs(self, limit: int = 500):
        rows = self._rows(
            """
            SELECT m1.user_id, m1.id AS q_id, m1.text AS q, m2.id AS a_id, m2.text AS a, m2.source
            FROM messages m1
            JOIN messages m2 ON m2.id = m1.id + 1 AND m2.user_id = m1.user_id
            WHERE m1.role = 'user' AND m2.role = 'assistant'
            ORDER BY m1.id DESC LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in rows]

    # ================= knowledge =================
    def get_knowledge(self) -> list:
        rows = self._rows("SELECT id, question, answer, weight, source FROM knowledge")
        return [dict(r) for r in rows]

    def add_knowledge(self, question: str, answer: str, source: str = "admin") -> bool:
        question = question.strip()
        if not question or not answer.strip():
            return False
        with self._lock:
            try:
                self._insert(
                    "INSERT INTO knowledge (question, answer, source) VALUES (?, ?, ?)",
                    (question, answer, source),
                )
            except Exception:
                self._execute(
                    "UPDATE knowledge SET answer = ?, source = ? WHERE question = ?",
                    (answer, source, question),
                )
            return True

    def add_seed_knowledge(self, pairs: list) -> None:
        for q, a in pairs:
            self.add_knowledge(q, a, source="seed")

    # ================= unanswered =================
    def add_unanswered(self, question: str, user_id: int) -> None:
        existing = self._row(
            "SELECT id FROM unanswered WHERE question = ? AND status = 'new' LIMIT 1",
            (question.strip(),),
        )
        if existing:
            return
        with self._lock:
            self._execute(
                "INSERT INTO unanswered (question, user_id) VALUES (?, ?)",
                (question.strip(), user_id),
            )

    def get_unanswered(self, status: str = "new") -> list:
        rows = self._rows(
            "SELECT * FROM unanswered WHERE status = ? ORDER BY created_at DESC LIMIT 200",
            (status,),
        )
        return [dict(r) for r in rows]

    def answer_unanswered(self, unanswered_id: int, answer: str) -> None:
        q = self._row("SELECT question FROM unanswered WHERE id = ?", (unanswered_id,))
        if q is None:
            return
        with self._lock:
            self._execute(
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
