# -*- coding: utf-8 -*-
"""D1 AI 台账（SQLite 事实源）。表结构见 docs/design-phase3-contract.md。
向后兼容：migrate() 幂等；禁止 DROP；新增列用 ADD COLUMN。"""
import json
import os
import sqlite3

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_code TEXT UNIQUE NOT NULL,
        product TEXT NOT NULL, qty INTEGER NOT NULL,
        due TEXT, priority INTEGER DEFAULT 2,
        source_system TEXT DEFAULT 'chat', source_ref TEXT,
        status TEXT DEFAULT 'open', frozen INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS execution (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_code TEXT NOT NULL, plan_date TEXT,
        actual_start TEXT, actual_end TEXT, qty_done INTEGER,
        wait_reason TEXT, exception_reason TEXT,
        reported_by TEXT, created_at TEXT DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS adjust_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_code TEXT, field TEXT, old_value TEXT, new_value TEXT,
        reason TEXT, decided_by TEXT,
        created_at TEXT DEFAULT (datetime('now')))""",
]
_MIGRATIONS = []  # 未来：["ALTER TABLE orders ADD COLUMN x TEXT"]


def init_db(path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = sqlite3.connect(path)
    for ddl in _SCHEMA:
        con.execute(ddl)
    con.commit(); con.close()
    return path


def migrate(path):
    con = sqlite3.connect(path)
    for ddl in _MIGRATIONS:
        con.execute(ddl)
    con.commit(); con.close()


def _conn(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def record_order(path, order):
    con = _conn(path)
    con.execute("INSERT OR REPLACE INTO orders(order_code, product, qty, due, priority, "
                "source_system, source_ref, status) VALUES(?,?,?,?,?,?,?,?)",
                (order["order_code"], order["product"], order["qty"], order.get("due"),
                 order.get("priority", 2), order.get("source_system", "chat"),
                 order.get("source_ref"), order.get("status", "open")))
    con.commit(); con.close()


def get_order(path, order_code):
    con = _conn(path)
    row = con.execute("SELECT * FROM orders WHERE order_code=?", (order_code,)).fetchone()
    con.close()
    return dict(row) if row else None


def record_execution(path, ex):
    con = _conn(path)
    con.execute("INSERT INTO execution(order_code, plan_date, actual_start, actual_end, "
                "qty_done, wait_reason, exception_reason, reported_by) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (ex["order_code"], ex.get("plan_date"), ex.get("actual_start"),
                 ex.get("actual_end"), ex.get("qty_done"), ex.get("wait_reason"),
                 ex.get("exception_reason"), ex.get("reported_by")))
    con.commit(); con.close()


def emit_event(path, event_type, payload):
    con = _conn(path)
    con.execute("INSERT INTO events(event_type, payload_json) VALUES(?,?)",
                (event_type, json.dumps(payload, ensure_ascii=False)))
    con.commit(); con.close()


def count_events(path, event_type=None):
    con = _conn(path)
    if event_type:
        n = con.execute("SELECT COUNT(*) FROM events WHERE event_type=?", (event_type,)).fetchone()[0]
    else:
        n = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    con.close()
    return n


def recent_events(path, limit=50):
    con = _conn(path)
    rows = con.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]
