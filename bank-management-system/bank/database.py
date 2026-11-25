"""SQLite database setup."""
import sqlite3
from pathlib import Path

from .security import hash_secret

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "bank.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    account_no      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    phone           TEXT NOT NULL,
    pin_hash        TEXT NOT NULL,
    acc_type        TEXT NOT NULL CHECK (acc_type IN ('SAVINGS', 'CURRENT')),
    balance         INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),  -- stored in paise
    status          TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'CLOSED')),
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked          INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    account_no    TEXT NOT NULL REFERENCES accounts(account_no),
    txn_type      TEXT NOT NULL,
    amount        INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admins (
    username      TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL
);
"""


def get_connection(db_path=DEFAULT_DB) -> sqlite3.Connection:
    if str(db_path) != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    # Seed a default admin (change this password after first run!)
    if conn.execute("SELECT COUNT(*) FROM admins").fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            ("admin", hash_secret("admin123")),
        )
    conn.commit()
