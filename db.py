# -*- coding: utf-8 -*-
import sqlite3, time, threading, os
from pathlib import Path

DB_PATH = os.environ.get("DB_PATH", "./data/fartbot.sqlite3")
Path(os.path.dirname(DB_PATH)).mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()

def _connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            created_at INTEGER NOT NULL,
            UNIQUE(chat_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS stats(
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            farts_count INTEGER NOT NULL DEFAULT 0,
            whips_count INTEGER NOT NULL DEFAULT 0,
            updated_at INTEGER NOT NULL,
            PRIMARY KEY (chat_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            amount INTEGER NOT NULL DEFAULT 1,
            ts INTEGER NOT NULL,
            file_id TEXT
        );
        CREATE TABLE IF NOT EXISTS achievements_awarded(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            achievement_key TEXT NOT NULL,
            threshold INTEGER NOT NULL,
            ts INTEGER NOT NULL,
            UNIQUE(chat_id, user_id, achievement_key)
        );
        CREATE TABLE IF NOT EXISTS audit_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            target_user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            delta INTEGER NOT NULL,
            admin_user_id INTEGER,
            ts INTEGER NOT NULL,
            note TEXT
        );
        """)
        conn.commit()
        conn.close()

def ensure_user(chat_id: int, user):
    now = int(time.time())
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("""INSERT OR IGNORE INTO users(chat_id, user_id, username, first_name, last_name, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)
                   """, (chat_id, user.id, user.username, user.first_name, user.last_name, now))
        cur.execute("""INSERT OR IGNORE INTO stats(chat_id, user_id, farts_count, whips_count, updated_at)
                       VALUES (?, ?, 0, 0, ?)
                   """, (chat_id, user.id, now))
        conn.commit()
        conn.close()

def add_event(chat_id: int, user_id: int, kind: str, amount: int = 1, file_id: str = None):
    now = int(time.time())
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO events(chat_id,user_id,kind,amount,ts,file_id) VALUES(?,?,?,?,?,?)",
                    (chat_id, user_id, kind, amount, now, file_id))
        if kind == 'fart':
            cur.execute("UPDATE stats SET farts_count = farts_count + ?, updated_at=? WHERE chat_id=? AND user_id=?",
                        (amount, now, chat_id, user_id))
        elif kind == 'whip':
            cur.execute("UPDATE stats SET whips_count = whips_count + ?, updated_at=? WHERE chat_id=? AND user_id=?",
                        (amount, now, chat_id, user_id))
        conn.commit()
        conn.close()

def inc_dec_stat(chat_id: int, user_id: int, field: str, delta: int):
    assert field in ('farts_count','whips_count')
    now = int(time.time())
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(f"UPDATE stats SET {field} = MAX(0, {field} + ?), updated_at=? WHERE chat_id=? AND user_id=?",
                    (delta, now, chat_id, user_id))
        conn.commit()
        conn.close()

def get_stats(chat_id: int, user_id: int):
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("SELECT farts_count, whips_count FROM stats WHERE chat_id=? AND user_id=?",
                    (chat_id, user_id))
        row = cur.fetchone()
        conn.close()
    if row is None:
        return {"farts": 0, "whips": 0}
    return {"farts": row[0], "whips": row[1]}

def get_top(chat_id: int, days: int = 7, limit: int = 10):
    now = int(time.time())
    after = now - days*86400 if days else 0
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        if days:
            cur.execute("""SELECT user_id, SUM(amount) as total
                           FROM events
                           WHERE chat_id=? AND kind='fart' AND ts>=?
                           GROUP BY user_id
                           ORDER BY total DESC
                           LIMIT ?
                        """, (chat_id, after, limit))
        else:
            cur.execute("""SELECT user_id, farts_count as total
                           FROM stats
                           WHERE chat_id=?
                           ORDER BY total DESC
                           LIMIT ?
                        """, (chat_id, limit))
        rows = cur.fetchall()
        conn.close()
    return [(r[0], int(r[1])) for r in rows]

def get_usernames(chat_id: int, user_ids):
    if not user_ids:
        return {}
    qmarks = ','.join('?' for _ in user_ids)
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(f"SELECT user_id, username, first_name, last_name FROM users WHERE chat_id=? AND user_id IN ({qmarks})",
                    (chat_id, *user_ids))
        rows = cur.fetchall()
        conn.close()
    res = {}
    for r in rows:
        uname = r['username']
        if uname:
            res[r['user_id']] = '@' + uname
        else:
            full = (r['first_name'] or '') + ' ' + (r['last_name'] or '')
            res[r['user_id']] = full.strip() or str(r['user_id'])
    return res

def save_achievement(chat_id: int, user_id: int, key: str, threshold: int):
    now = int(time.time())
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("""INSERT OR IGNORE INTO achievements_awarded(chat_id,user_id,achievement_key,threshold,ts)
                       VALUES(?,?,?,?,?)""", (chat_id, user_id, key, threshold, now))
        conn.commit()
        conn.close()

def has_achievement(chat_id: int, user_id: int, key: str) -> bool:
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM achievements_awarded WHERE chat_id=? AND user_id=? AND achievement_key=?",
                    (chat_id, user_id, key))
        ok = cur.fetchone() is not None
        conn.close()
    return ok

def log_admin_action(chat_id: int, target_user_id: int, action: str, delta: int, admin_user_id: int, note: str = None):
    now = int(time.time())
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO audit_log(chat_id,target_user_id,action,delta,admin_user_id,ts,note) VALUES(?,?,?,?,?,?,?)",
                    (chat_id, target_user_id, action, delta, admin_user_id, now, note))
        conn.commit()
        conn.close()
