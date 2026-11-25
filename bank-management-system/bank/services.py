"""Core banking logic: accounts, transactions, admin operations."""
import random
import re
from decimal import Decimal, InvalidOperation

from .database import DEFAULT_DB, get_connection, init_db
from .security import hash_secret, verify_secret

MAX_FAILED_ATTEMPTS = 3
MIN_BALANCE_SAVINGS = 50_000  # Rs. 500 in paise
MIN_OPENING_DEPOSIT = 50_000  # Rs. 500 in paise

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class BankError(Exception):
    """Raised for any business-rule violation (shown to the user)."""


def to_paise(value) -> int:
    """Convert user input like '1500.50' to integer paise. Must be > 0."""
    try:
        d = Decimal(str(value).strip())
    except InvalidOperation:
        raise BankError("Invalid amount.")
    if not d.is_finite() or d <= 0:
        raise BankError("Amount must be greater than zero.")
    if d.as_tuple().exponent < -2:
        raise BankError("Amount can have at most two decimal places.")
    return int(d * 100)


def money(paise: int) -> str:
    return f"Rs. {Decimal(paise) / 100:,.2f}"


class BankService:
    def __init__(self, db_path=DEFAULT_DB):
        self.conn = get_connection(db_path)
        init_db(self.conn)

    def close(self):
        self.conn.close()

    # ---------------- helpers ----------------
    def _log(self, acc_no, txn_type, amount, balance_after, description=""):
        self.conn.execute(
            "INSERT INTO transactions (account_no, txn_type, amount, balance_after, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (acc_no, txn_type, amount, balance_after, description),
        )

    def _get_active(self, acc_no):
        row = self.conn.execute(
            "SELECT * FROM accounts WHERE account_no = ?", (str(acc_no).strip(),)
        ).fetchone()
        if row is None or row["status"] != "ACTIVE":
            raise BankError("Account not found or closed.")
        return row

    def _new_account_no(self) -> str:
        while True:
            no = "10" + "".join(str(random.randint(0, 9)) for _ in range(8))
            if not self.conn.execute(
                "SELECT 1 FROM accounts WHERE account_no = ?", (no,)
            ).fetchone():
                return no

    # ---------------- customer ----------------
    def create_account(self, name, email, phone, pin, acc_type="SAVINGS", initial_deposit="500"):
        name, email, phone = name.strip(), email.strip().lower(), phone.strip()
        acc_type = acc_type.upper()
        if len(name) < 2:
            raise BankError("Please enter a valid name.")
        if not EMAIL_RE.match(email):
            raise BankError("Please enter a valid email address.")
        if not re.fullmatch(r"\d{10}", phone):
            raise BankError("Phone number must be exactly 10 digits.")
        if not re.fullmatch(r"\d{4,6}", pin):
            raise BankError("PIN must be 4 to 6 digits.")
        if acc_type not in ("SAVINGS", "CURRENT"):
            raise BankError("Account type must be SAVINGS or CURRENT.")
        deposit = to_paise(initial_deposit)
        if deposit < MIN_OPENING_DEPOSIT:
            raise BankError(f"Minimum opening deposit is {money(MIN_OPENING_DEPOSIT)}.")

        acc_no = self._new_account_no()
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO accounts (account_no, name, email, phone, pin_hash, acc_type, balance) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (acc_no, name, email, phone, hash_secret(pin), acc_type, deposit),
                )
                self._log(acc_no, "OPENING", deposit, deposit, "Account opened")
        except Exception as exc:  # sqlite3.IntegrityError for duplicate email
            if "UNIQUE" in str(exc):
                raise BankError("An account with this email already exists.")
            raise
        return acc_no

    def login(self, acc_no, pin):
        row = self.conn.execute(
            "SELECT * FROM accounts WHERE account_no = ?", (str(acc_no).strip(),)
        ).fetchone()
        if row is None or row["status"] != "ACTIVE":
            raise BankError("Invalid account number or PIN.")
        if row["locked"]:
            raise BankError("Account is locked after too many failed attempts. Contact admin.")
        if verify_secret(pin, row["pin_hash"]):
            with self.conn:
                self.conn.execute(
                    "UPDATE accounts SET failed_attempts = 0 WHERE account_no = ?", (row["account_no"],)
                )
            return dict(row)
        attempts = row["failed_attempts"] + 1
        locked = 1 if attempts >= MAX_FAILED_ATTEMPTS else 0
        with self.conn:
            self.conn.execute(
                "UPDATE accounts SET failed_attempts = ?, locked = ? WHERE account_no = ?",
                (attempts, locked, row["account_no"]),
            )
        if locked:
            raise BankError("Too many failed attempts. Account locked. Contact admin.")
        raise BankError(f"Invalid account number or PIN. {MAX_FAILED_ATTEMPTS - attempts} attempt(s) left.")

    def get_balance(self, acc_no) -> int:
        return self._get_active(acc_no)["balance"]

    def deposit(self, acc_no, amount) -> int:
        paise = to_paise(amount)
        with self.conn:
            acc = self._get_active(acc_no)
            new_bal = acc["balance"] + paise
            self.conn.execute("UPDATE accounts SET balance = ? WHERE account_no = ?", (new_bal, acc_no))
            self._log(acc_no, "DEPOSIT", paise, new_bal, "Cash deposit")
        return new_bal

    def withdraw(self, acc_no, amount) -> int:
        paise = to_paise(amount)
        with self.conn:
            acc = self._get_active(acc_no)
            new_bal = acc["balance"] - paise
            minimum = MIN_BALANCE_SAVINGS if acc["acc_type"] == "SAVINGS" else 0
            if new_bal < 0:
                raise BankError("Insufficient funds.")
            if new_bal < minimum:
                raise BankError(f"Savings accounts must keep a minimum balance of {money(minimum)}.")
            self.conn.execute("UPDATE accounts SET balance = ? WHERE account_no = ?", (new_bal, acc_no))
            self._log(acc_no, "WITHDRAW", paise, new_bal, "Cash withdrawal")
        return new_bal

    def transfer(self, from_acc, to_acc, amount) -> int:
        paise = to_paise(amount)
        to_acc = str(to_acc).strip()
        if from_acc == to_acc:
            raise BankError("Cannot transfer to the same account.")
        with self.conn:
            src = self._get_active(from_acc)
            dst = self._get_active(to_acc)
            src_new = src["balance"] - paise
            minimum = MIN_BALANCE_SAVINGS if src["acc_type"] == "SAVINGS" else 0
            if src_new < 0:
                raise BankError("Insufficient funds.")
            if src_new < minimum:
                raise BankError(f"Savings accounts must keep a minimum balance of {money(minimum)}.")
            dst_new = dst["balance"] + paise
            self.conn.execute("UPDATE accounts SET balance = ? WHERE account_no = ?", (src_new, from_acc))
            self.conn.execute("UPDATE accounts SET balance = ? WHERE account_no = ?", (dst_new, to_acc))
            self._log(from_acc, "TRANSFER_OUT", paise, src_new, f"Transfer to {to_acc}")
            self._log(to_acc, "TRANSFER_IN", paise, dst_new, f"Transfer from {from_acc}")
        return src_new

    def history(self, acc_no, limit=10):
        self._get_active(acc_no)
        rows = self.conn.execute(
            "SELECT * FROM transactions WHERE account_no = ? ORDER BY id DESC LIMIT ?",
            (acc_no, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def change_pin(self, acc_no, old_pin, new_pin):
        acc = self._get_active(acc_no)
        if not verify_secret(old_pin, acc["pin_hash"]):
            raise BankError("Current PIN is incorrect.")
        if not re.fullmatch(r"\d{4,6}", new_pin):
            raise BankError("PIN must be 4 to 6 digits.")
        with self.conn:
            self.conn.execute(
                "UPDATE accounts SET pin_hash = ? WHERE account_no = ?", (hash_secret(new_pin), acc_no)
            )

    def close_account(self, acc_no, pin):
        acc = self._get_active(acc_no)
        if not verify_secret(pin, acc["pin_hash"]):
            raise BankError("PIN is incorrect.")
        if acc["balance"] != 0:
            raise BankError(
                f"Balance is {money(acc['balance'])}. Withdraw the full amount before closing."
            )
        with self.conn:
            self.conn.execute("UPDATE accounts SET status = 'CLOSED' WHERE account_no = ?", (acc_no,))

    # ---------------- admin ----------------
    def admin_login(self, username, password) -> bool:
        row = self.conn.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
        if row is None or not verify_secret(password, row["password_hash"]):
            raise BankError("Invalid admin credentials.")
        return True

    def list_accounts(self):
        rows = self.conn.execute(
            "SELECT account_no, name, email, acc_type, balance, status, locked FROM accounts ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]

    def unlock_account(self, acc_no):
        with self.conn:
            cur = self.conn.execute(
                "UPDATE accounts SET locked = 0, failed_attempts = 0 WHERE account_no = ?", (acc_no,)
            )
        if cur.rowcount == 0:
            raise BankError("Account not found.")

    def bank_summary(self):
        row = self.conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(balance), 0) AS total FROM accounts WHERE status = 'ACTIVE'"
        ).fetchone()
        return {"active_accounts": row["n"], "total_deposits": row["total"]}
