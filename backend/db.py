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
    referal_code  TEXT UNIQUE,
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

CREATE TABLE IF NOT EXISTS shares (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    code       TEXT NOT NULL UNIQUE,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gen_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    kind       TEXT NOT NULL,
    url        TEXT NOT NULL,
    prompt     TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    title      TEXT,
    content    TEXT,
    category   TEXT DEFAULT 'umumiy',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS referrals (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_id INTEGER NOT NULL,
    referred_id INTEGER NOT NULL UNIQUE,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE,
    lang    TEXT DEFAULT 'uz',
    theme   TEXT DEFAULT 'dark',
    updated_at TEXT DEFAULT (datetime('now'))
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
        referal_code  TEXT UNIQUE,
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
    """
    CREATE TABLE IF NOT EXISTS shares (
        id         BIGSERIAL PRIMARY KEY,
        conversation_id BIGINT NOT NULL,
        user_id    BIGINT NOT NULL,
        code       TEXT NOT NULL UNIQUE,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gen_history (
        id         BIGSERIAL PRIMARY KEY,
        user_id    BIGINT NOT NULL,
        kind       TEXT NOT NULL,
        url        TEXT NOT NULL,
        prompt     TEXT,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS notes (
        id         BIGSERIAL PRIMARY KEY,
        user_id    BIGINT NOT NULL,
        title      TEXT,
        content    TEXT,
        category   TEXT DEFAULT 'umumiy',
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS referrals (
        id         BIGSERIAL PRIMARY KEY,
        referrer_id BIGINT NOT NULL,
        referred_id BIGINT NOT NULL UNIQUE,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        id      BIGSERIAL PRIMARY KEY,
        user_id BIGINT UNIQUE,
        lang    TEXT DEFAULT 'uz',
        theme   TEXT DEFAULT 'dark',
        updated_at TIMESTAMPTZ DEFAULT now()
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
                        "referal_code",
                        "avatar",
                    ):
                        cur.execute(
                            f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} TEXT"
                        )
                    for col in ("name", "models"):
                        cur.execute(
                            f"ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS {col} TEXT"
                        )
                    for col in ("folder", "archived"):
                        cur.execute(
                            f"ALTER TABLE conversations ADD COLUMN IF NOT EXISTS {col} TEXT"
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
                "referal_code",
                "avatar",
            ):
                if col not in user_cols:
                    self.conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
            conv_cols = [
                r[1] for r in self.conn.execute("PRAGMA table_info(conversations)")
            ]
            if "folder" not in conv_cols:
                self.conn.execute("ALTER TABLE conversations ADD COLUMN folder TEXT")
            if "archived" not in conv_cols:
                self.conn.execute(
                    "ALTER TABLE conversations ADD COLUMN archived INTEGER DEFAULT 0"
                )
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
            "SELECT id, username, name, surname, email, phone, token, client_id, referal_code "
            "FROM users WHERE id = ?",
            (user_id,),
        )
        return dict(row) if row else None

    def get_user_by_token(self, token: str) -> dict | None:
        row = self._row(
            "SELECT id, username, name, surname, email, phone, token, client_id, telegram_id, referal_code "
            "FROM users WHERE token = ?",
            (token,),
        )
        return dict(row) if row else None

    def get_user_by_username(self, username: str) -> dict | None:
        row = self._row("SELECT * FROM users WHERE username = ?", (username.lower(),))
        return dict(row) if row else None

    def get_user_by_email(self, email: str) -> dict | None:
        row = self._row("SELECT * FROM users WHERE email = ?", (email.lower(),))
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

    def set_user_token(self, user_id: int, token: str) -> None:
        self.set_token(user_id, token)

    # ================= Telegram WebApp =================
    def get_user_by_telegram(self, telegram_id: str) -> dict | None:
        row = self._row(
            "SELECT id, username, name, token, telegram_id FROM users "
            "WHERE telegram_id = ?",
            (int(telegram_id) if str(telegram_id).isdigit() else telegram_id,),
        )
        return dict(row) if row else None

    def create_telegram_user(
        self, telegram_id: str, username: str, name: str = "", photo_url: str = ""
    ) -> dict:
        tid = int(telegram_id) if str(telegram_id).isdigit() else telegram_id
        with self._lock:
            new_id = self._insert(
                "INSERT INTO users (telegram_id, username, name) VALUES (?, ?, ?)",
                (tid, username, name or username),
            )
        return dict(self._row("SELECT * FROM users WHERE id = ?", (new_id,)))

    def bind_telegram(self, user_id: int, telegram_id: str) -> None:
        tid = int(telegram_id) if str(telegram_id).isdigit() else telegram_id
        with self._lock:
            self._execute(
                "UPDATE users SET telegram_id = ? WHERE id = ?", (tid, user_id)
            )

    def unbind_telegram(self, user_id: int) -> None:
        with self._lock:
            self._execute(
                "UPDATE users SET telegram_id = NULL WHERE id = ?", (user_id,)
            )

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

    def update_profile(
        self,
        user_id: int,
        name: str | None = None,
        surname: str | None = None,
        phone: str | None = None,
    ) -> None:
        with self._lock:
            self._execute(
                "UPDATE users SET name = COALESCE(?, name), "
                "surname = COALESCE(?, surname), phone = COALESCE(?, phone) "
                "WHERE id = ?",
                (name, surname, phone, user_id),
            )

    def set_avatar(self, user_id: int, avatar_url: str) -> None:
        self._execute("UPDATE users SET avatar = ? WHERE id = ?", (avatar_url, user_id))

    def get_password_hash(self, user_id: int) -> str | None:
        row = self._row("SELECT password_hash FROM users WHERE id = ?", (user_id,))
        return row["password_hash"] if row else None

    def set_password_hash(self, user_id: int, password_hash: str) -> None:
        with self._lock:
            self._execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (password_hash, user_id),
            )

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

    def list_conversations(
        self, user_id: int, folder: str = "", archived: int = 0
    ) -> list:
        rows = self._rows(
            """
            SELECT c.id, c.title, c.created_at, c.folder, c.archived,
                   (SELECT count(*) FROM messages m WHERE m.conversation_id = c.id) AS msg_count
            FROM conversations c
            WHERE c.user_id = ? AND CAST(COALESCE(c.archived, '0') AS INTEGER) = ?
            AND (? = '' OR COALESCE(c.folder, '') = ?)
            ORDER BY c.id DESC LIMIT 200
            """,
            (user_id, archived, folder, folder),
        )
        return [dict(r) for r in rows]

    def list_folders(self, user_id: int) -> list:
        rows = self._rows(
            "SELECT DISTINCT COALESCE(folder, '') AS folder FROM conversations "
            "WHERE user_id = ? AND COALESCE(folder, '') != '' ORDER BY folder",
            (user_id,),
        )
        return [r["folder"] for r in rows]

    def set_conversation_folder(self, conv_id: int, user_id: int, folder: str) -> bool:
        conv = self.get_conversation(conv_id)
        if not conv or conv["user_id"] != user_id:
            return False
        self._execute(
            "UPDATE conversations SET folder = ? WHERE id = ? AND user_id = ?",
            (folder.strip()[:40] or None, conv_id, user_id),
        )
        return True

    def set_conversation_archived(
        self, conv_id: int, user_id: int, archived: int
    ) -> bool:
        conv = self.get_conversation(conv_id)
        if not conv or conv["user_id"] != user_id:
            return False
        self._execute(
            "UPDATE conversations SET archived = ? WHERE id = ? AND user_id = ?",
            (1 if archived else 0, conv_id, user_id),
        )
        return True

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

    def delete_conversation(self, conv_id: int, user_id: int) -> bool:
        """Suhbatni va uning barcha xabarlarini o'chiradi (faqat egasi)."""
        conv = self.get_conversation(conv_id)
        if not conv or conv["user_id"] != user_id:
            return False
        with self._lock:
            self._execute(
                "DELETE FROM messages WHERE conversation_id = ? AND user_id = ?",
                (conv_id, user_id),
            )
            self._execute(
                "DELETE FROM conversations WHERE id = ? AND user_id = ?",
                (conv_id, user_id),
            )
        return True

    def user_stats(self, user_id: int) -> dict:
        """Foydalanuvchi statistikasi: xabarlar soni, manbalar, kunlik taqsimot."""
        total = self._row(
            "SELECT count(*) AS n FROM messages WHERE user_id = ?", (user_id,)
        )
        convs = self._row(
            "SELECT count(*) AS n FROM conversations WHERE user_id = ?", (user_id,)
        )
        by_source = self._rows(
            "SELECT source, count(*) AS n FROM messages "
            "WHERE user_id = ? AND role = 'assistant' GROUP BY source ORDER BY n DESC",
            (user_id,),
        )
        by_day = self._rows(
            "SELECT SUBSTR(CAST(created_at AS TEXT), 1, 10) AS day, count(*) AS n "
            "FROM messages WHERE user_id = ? GROUP BY day ORDER BY day DESC LIMIT 14",
            (user_id,),
        )
        rated = self._row(
            "SELECT COUNT(*) AS n FROM messages "
            "WHERE user_id = ? AND rating IS NOT NULL AND role = 'assistant'",
            (user_id,),
        )
        return {
            "messages": total["n"] if total else 0,
            "conversations": convs["n"] if convs else 0,
            "by_source": [dict(r) for r in by_source],
            "by_day": [dict(r) for r in by_day],
            "rated": rated["n"] if rated else 0,
        }

    def admin_stats(self) -> dict:
        """Admin panel uchun umumiy statistika."""

        def cnt(sql: str) -> int:
            row = self._row(sql)
            return row["n"] if row else 0

        users = cnt("SELECT count(*) AS n FROM users")
        convs = cnt("SELECT count(*) AS n FROM conversations")
        msgs = cnt("SELECT count(*) AS n FROM messages")
        notes = cnt("SELECT count(*) AS n FROM notes")
        refs = cnt("SELECT count(*) AS n FROM referrals")
        for_sources = self._rows(
            "SELECT source, count(*) AS n FROM messages WHERE role = 'assistant' "
            "GROUP BY source ORDER BY n DESC LIMIT 8"
        )
        for_days = self._rows(
            "SELECT SUBSTR(CAST(created_at AS TEXT), 1, 10) AS day, count(*) AS n "
            "FROM messages GROUP BY day ORDER BY day DESC LIMIT 7"
        )
        top_users = self._rows(
            "SELECT u.username, u.name, count(m.id) AS n FROM messages m "
            "JOIN users u ON u.id = m.user_id GROUP BY u.id "
            "ORDER BY n DESC LIMIT 10"
        )
        return {
            "users": users,
            "conversations": convs,
            "messages": msgs,
            "notes": notes,
            "referrals": refs,
            "by_source": [dict(r) for r in for_sources],
            "by_day": [dict(r) for r in for_days],
            "top_users": [dict(r) for r in top_users],
        }

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

    def get_messages(self, conversation_id: int) -> list:
        rows = self._rows(
            "SELECT id, role, text, source, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        )
        return [dict(r) for r in rows]

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

    # ================= ulashish (shares) =================
    def create_share(self, conversation_id: int, user_id: int, code: str) -> bool:
        existing = self._row(
            "SELECT id FROM shares WHERE conversation_id = ?", (conversation_id,)
        )
        if existing:
            return False
        with self._lock:
            self._execute(
                "INSERT INTO shares (conversation_id, user_id, code) VALUES (?, ?, ?)",
                (conversation_id, user_id, code),
            )
        return True

    def get_share(self, code: str) -> dict | None:
        row = self._row("SELECT * FROM shares WHERE code = ?", (code.strip(),))
        return dict(row) if row else None

    def list_shares(self, user_id: int) -> list:
        rows = self._rows(
            "SELECT * FROM shares WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
            (user_id,),
        )
        return [dict(r) for r in rows]

    def delete_share(self, conversation_id: int, user_id: int) -> None:
        with self._lock:
            self._execute(
                "DELETE FROM shares WHERE conversation_id = ? AND user_id = ?",
                (conversation_id, user_id),
            )

    # ================= qidiruv =================
    def search_messages(self, user_id: int, q: str, limit: int = 30) -> list:
        like = f"%{q.strip()}%"
        rows = self._rows(
            "SELECT m.id, m.role, m.text, m.created_at, c.id AS conversation_id, c.title "
            "FROM messages m LEFT JOIN conversations c ON c.id = m.conversation_id "
            "WHERE m.user_id = ? AND m.text LIKE ? "
            "ORDER BY m.id DESC LIMIT ?",
            (user_id, like, limit),
        )
        return [dict(r) for r in rows]

    # ================= generatsiya tarixi (galereya) =================
    def add_gen(
        self, user_id: int, kind: str, url: str, prompt: str | None = None
    ) -> None:
        with self._lock:
            self._execute(
                "INSERT INTO gen_history (user_id, kind, url, prompt) VALUES (?, ?, ?, ?)",
                (user_id, kind, url, prompt),
            )

    def list_gen(self, user_id: int, kind: str | None = None, limit: int = 60) -> list:
        if kind:
            rows = self._rows(
                "SELECT * FROM gen_history WHERE user_id = ? AND kind = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (user_id, kind, limit),
            )
        else:
            rows = self._rows(
                "SELECT * FROM gen_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            )
        return [dict(r) for r in rows]

    # ================= suhbat eksporti =================
    def export_conversation(self, conversation_id: int, user_id: int) -> list | None:
        conv = self._row(
            "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        if not conv:
            return None
        rows = self._rows(
            "SELECT role, text, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        )
        return {"title": conv["title"], "messages": [dict(r) for r in rows]}

    # ================= notalar =================
    def create_note(
        self, user_id: int, title: str, content: str, category: str = "umumiy"
    ) -> int:
        return self._insert(
            "INSERT INTO notes (user_id, title, content, category) VALUES (?, ?, ?, ?)",
            (user_id, title, content, category),
        )

    def list_notes(self, user_id: int) -> list:
        rows = self._rows(
            "SELECT * FROM notes WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        )
        return [dict(r) for r in rows]

    def get_note(self, note_id: int, user_id: int) -> dict | None:
        row = self._row(
            "SELECT * FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id)
        )
        return dict(row) if row else None

    def update_note(
        self, note_id: int, user_id: int, title: str, content: str, category: str
    ) -> bool:
        self._execute(
            "UPDATE notes SET title = ?, content = ?, category = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND user_id = ?",
            (title, content, category, note_id, user_id),
        )
        return self.get_note(note_id, user_id) is not None

    def delete_note(self, note_id: int, user_id: int) -> None:
        self._execute(
            "DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id)
        )

    # ================= sozlamalar (til/theme) =================
    def get_settings(self, user_id: int) -> dict:
        row = self._row(
            "SELECT lang, theme FROM settings WHERE user_id = ?", (user_id,)
        )
        if row:
            return dict(row)
        return {"lang": "uz", "theme": "dark"}

    def set_settings(self, user_id: int, lang: str, theme: str) -> None:
        with self._lock:
            row = self._row("SELECT id FROM settings WHERE user_id = ?", (user_id,))
            if row:
                self._execute(
                    "UPDATE settings SET lang = ?, theme = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (lang, theme, user_id),
                )
            else:
                self._insert(
                    "INSERT INTO settings (user_id, lang, theme) VALUES (?, ?, ?)",
                    (user_id, lang, theme),
                )

    # ================= referral =================
    def gen_referal_code(self, user_id: int) -> str | None:
        import random
        import string

        with self._lock:
            row = self._row("SELECT referal_code FROM users WHERE id = ?", (user_id,))
            if row and row["referal_code"]:
                return row["referal_code"]
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
            self._execute(
                "UPDATE users SET referal_code = ? WHERE id = ?", (code, user_id)
            )
        return code

    def get_user_by_referal_code(self, code: str) -> dict | None:
        row = self._row(
            "SELECT id FROM users WHERE referal_code = ?", (code.strip().upper(),)
        )
        return dict(row) if row else None

    def apply_referral(self, referrer_id: int, referred_id: int) -> bool:
        if referrer_id == referred_id:
            return False
        with self._lock:
            exists = self._row(
                "SELECT id FROM referrals WHERE referred_id = ?", (referred_id,)
            )
            if exists:
                return False
            # referrer ham mavjud bo'lishi kerak
            if not self._row("SELECT id FROM users WHERE id = ?", (referrer_id,)):
                return False
            self._insert(
                "INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
                (referrer_id, referred_id),
            )
        return True

    def list_referrals(self, user_id: int) -> list:
        rows = self._rows(
            "SELECT r.id, r.created_at, u.username, u.name FROM referrals r "
            "LEFT JOIN users u ON u.id = r.referred_id WHERE r.referrer_id = ? "
            "ORDER BY r.created_at DESC",
            (user_id,),
        )
        return [dict(r) for r in rows]


_db_instance: Database | None = None


def get_db() -> Database:
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
