import sqlite3
import datetime
import re
import time

from config import DB_PATH
from logger_setup import logger


def _connect():
    con = sqlite3.connect(DB_PATH, timeout=5.0)
    con.row_factory = sqlite3.Row
    con.create_function(
        "jarvis_casefold",
        1,
        lambda value: str(value or "").casefold().replace("i\u0307", "i"),
        deterministic=True,
    )
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=5000")
    con.execute("PRAGMA journal_mode=WAL")
    return con


def _db_execute(query: str, params: tuple = (), fetch: bool = False):
    last_error = None
    for attempt in range(3):
        con = _connect()
        try:
            cur = con.cursor()
            cur.execute(query, params)
            if fetch:
                rows = cur.fetchall()
                return [dict(row) for row in rows]
            con.commit()
            return cur.lastrowid
        except sqlite3.OperationalError as exc:
            con.rollback()
            last_error = exc
            if "locked" not in str(exc).lower() or attempt == 2:
                raise
            time.sleep(0.1 * (attempt + 1))
        finally:
            con.close()
    raise last_error


def db_init():
    _db_execute("""CREATE TABLE IF NOT EXISTS sessions
        (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, created_at TEXT)""")
    _db_execute("""CREATE TABLE IF NOT EXISTS messages
        (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL,
         role TEXT, content TEXT, ts TEXT)""")
    _db_execute("""CREATE TABLE IF NOT EXISTS reminders
        (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, remind_date TEXT, done INTEGER DEFAULT 0)""")
    _db_execute("""CREATE TABLE IF NOT EXISTS watchlist
        (id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT UNIQUE,
         added_at TEXT, notes TEXT)""")
    _db_execute("""CREATE TABLE IF NOT EXISTS finance_history
        (id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT,
         price REAL, currency TEXT, ts TEXT)""")
    _db_execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id)")
    _db_execute("CREATE INDEX IF NOT EXISTS idx_reminders_pending ON reminders(done, remind_date)")
    _db_execute("CREATE INDEX IF NOT EXISTS idx_finance_ticker_ts ON finance_history(ticker, ts)")
    db_cleanup_old_data()


def db_cleanup_old_data(retention_days: int = 90) -> None:
    if retention_days < 1:
        raise ValueError("Retention süresi en az bir gün olmalı")
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=retention_days)).isoformat()
    _db_execute(
        "DELETE FROM messages WHERE session_id IN "
        "(SELECT id FROM sessions WHERE created_at < ?)",
        (cutoff,),
    )
    _db_execute("DELETE FROM sessions WHERE created_at < ?", (cutoff,))
    _db_execute("DELETE FROM finance_history WHERE ts < ?", (cutoff,))


def db_new_session(title: str = "Yeni Oturum") -> int:
    title = str(title or "Yeni Oturum").strip()[:200] or "Yeni Oturum"
    return _db_execute(
        "INSERT INTO sessions (title,created_at) VALUES (?,?)",
        (title, datetime.datetime.now().isoformat()),
        fetch=False,
    )


def db_save_msg(sid, role, content):
    if role not in {"user", "assistant", "system"}:
        raise ValueError("Geçersiz mesaj rolü")
    content = str(content or "")[:20_000]
    _db_execute(
        "INSERT INTO messages (session_id,role,content,ts) VALUES (?,?,?,?)",
        (sid, role, content, datetime.datetime.now().isoformat()),
        fetch=False,
    )


def db_get_sessions(limit: int = 30):
    rows = _db_execute(
        "SELECT id,title,created_at FROM sessions ORDER BY id DESC LIMIT ?",
        (limit,),
        fetch=True,
    )
    return [(row["id"], row["title"], row["created_at"]) for row in rows]


def db_get_messages(sid, limit: int | None = None):
    if limit is not None:
        if not isinstance(limit, int) or not 1 <= limit <= 10_000:
            raise ValueError("Mesaj sınırı 1 ile 10000 arasında olmalı")
        rows = _db_execute(
            """
            SELECT role, content FROM (
                SELECT id, role, content
                FROM messages
                WHERE session_id=?
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id
            """,
            (sid, limit),
            fetch=True,
        )
    else:
        rows = _db_execute(
            "SELECT role,content FROM messages WHERE session_id=? ORDER BY id",
            (sid,),
            fetch=True,
        )
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def db_search_messages(
    query: str,
    limit: int = 5,
    exclude_content: str | None = None,
) -> list[dict[str, str]]:
    query = str(query or "").strip()[:200]
    if not query:
        raise ValueError("Arama ifadesi boş olamaz")
    if not isinstance(limit, int) or not 1 <= limit <= 20:
        raise ValueError("Arama sonucu sınırı 1 ile 20 arasında olmalı")
    ignored_terms = {
        "acaba", "ama", "bana", "bir", "bunu", "da", "de", "ile",
        "icin", "için", "mi", "mu", "mı", "mü", "ne", "olan", "olarak",
        "onceki", "önceki", "sohbet", "gecmis", "geçmiş", "baglamiyla",
        "bağlamıyla", "yararlan", "kullan", "ve",
    }
    terms = []
    for term in re.findall(r"[^\W_]+", query.casefold().replace("\u0307", "")):
        if len(term) > 1 and term not in ignored_terms and term not in terms:
            terms.append(term)
        if len(terms) == 8:
            break
    if not terms:
        raise ValueError("Arama ifadesi anlamlı bir sözcük içermeli")
    matches_any_term = " OR ".join(
        "instr(jarvis_casefold(m.content), jarvis_casefold(?)) > 0"
        for _ in terms
    )
    relevance = " + ".join(
        "(instr(jarvis_casefold(m.content), jarvis_casefold(?)) > 0)"
        for _ in terms
    )
    rows = _db_execute(
        f"""
        SELECT s.title, m.role, m.content, m.ts
        FROM messages AS m
        JOIN sessions AS s ON s.id = m.session_id
        WHERE ({matches_any_term})
          AND (? IS NULL OR m.content != ?)
        ORDER BY ({relevance}) DESC, m.id DESC
        LIMIT ?
        """,
        (*terms, exclude_content, exclude_content, *terms, limit),
        fetch=True,
    )
    return [
        {
            "title": row["title"] or "İsimsiz sohbet",
            "role": row["role"],
            "content": row["content"],
            "ts": row["ts"],
        }
        for row in rows
    ]


def db_clear_session(sid: int) -> int:
    if not isinstance(sid, int) or sid < 1:
        raise ValueError("Geçersiz oturum kimliği")
    con = _connect()
    try:
        with con:
            cursor = con.execute(
                "DELETE FROM messages WHERE session_id=?", (sid,)
            )
            return cursor.rowcount
    finally:
        con.close()


def db_clear_all_history(keep_session_id: int) -> int:
    if not isinstance(keep_session_id, int) or keep_session_id < 1:
        raise ValueError("Geçersiz oturum kimliği")
    con = _connect()
    try:
        with con:
            con.execute("DELETE FROM messages")
            cursor = con.execute(
                "DELETE FROM sessions WHERE id != ?", (keep_session_id,)
            )
            return cursor.rowcount
    finally:
        con.close()


def db_add_reminder(title, date_str):
    title = str(title or "").strip()[:500]
    datetime.date.fromisoformat(str(date_str))
    if not title:
        raise ValueError("Hatırlatıcı başlığı boş olamaz")
    _db_execute(
        "INSERT INTO reminders (title,remind_date) VALUES (?,?)",
        (title, date_str),
        fetch=False,
    )


def db_get_reminders():
    rows = _db_execute(
        "SELECT id,title,remind_date FROM reminders WHERE done=0 ORDER BY remind_date",
        (),
        fetch=True,
    )
    return [(row["id"], row["title"], row["remind_date"]) for row in rows]


def db_claim_due_reminders(today: str | None = None):
    """Atomically mark and return due reminders so polling cannot repeat them."""
    due_date = today or datetime.date.today().isoformat()
    con = _connect()
    try:
        with con:
            con.execute("BEGIN IMMEDIATE")
            rows = con.execute(
                "SELECT id,title,remind_date FROM reminders "
                "WHERE done=0 AND remind_date<=? ORDER BY remind_date,id",
                (due_date,),
            ).fetchall()
            if rows:
                con.executemany(
                    "UPDATE reminders SET done=1 WHERE id=? AND done=0",
                    [(row["id"],) for row in rows],
                )
        return [(row["id"], row["title"], row["remind_date"]) for row in rows]
    finally:
        con.close()


def db_log_finance(ticker: str, price: float, currency: str):
    try:
        _db_execute(
            "INSERT INTO finance_history (ticker,price,currency,ts) VALUES (?,?,?,?)",
            (ticker, price, currency, datetime.datetime.now().isoformat()),
            fetch=False,
        )
    except Exception:
        logger.exception("Finance log insert failed")
