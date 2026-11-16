"""Accounts: first-time registration and login for student, teacher and admin."""
import hashlib
import hmac
import os

MIN_PASSWORD_LENGTH = 4
ADMIN_ID = "admin"

CREATE_ACCOUNTS = """
CREATE TABLE IF NOT EXISTS accounts (
  role ENUM('student','teacher','admin') NOT NULL,
  user_id VARCHAR(20) NOT NULL,
  salt VARCHAR(64) NOT NULL,
  pw_hash VARCHAR(128) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (role, user_id)
)
"""


def ensure_tables(conn):
    cur = conn.cursor()
    cur.execute(CREATE_ACCOUNTS)
    conn.commit()


def hash_password(password, salt_hex):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 150_000).hex()


def _person(conn, role, user_id):
    """Return the display name if this ID exists in the CSV data, else None."""
    cur = conn.cursor()
    if role == "student":
        cur.execute("SELECT name FROM students WHERE student_id = %s", (user_id,))
    elif role == "teacher":
        if not user_id.isdigit():
            return None
        cur.execute("SELECT name FROM teachers WHERE teacher_id = %s", (int(user_id),))
    else:
        return "Administrator" if user_id == ADMIN_ID else None
    row = cur.fetchone()
    return row[0] if row else None


def _registered(conn, role, user_id):
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM accounts WHERE role=%s AND user_id=%s", (role, user_id))
    return cur.fetchone() is not None


def register(conn, role, user_id, password, confirm):
    """First-time registration. Returns (ok, message)."""
    user_id = user_id.strip()
    if role == "admin":
        user_id = ADMIN_ID
    if not user_id:
        return False, "Please enter your ID."
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if password != confirm:
        return False, "Passwords do not match."
    if role == "admin":
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM accounts WHERE role='admin'")
        if cur.fetchone():
            return False, "Admin is already registered. Please login."
    else:
        if _person(conn, role, user_id) is None:
            return False, f"This {role} ID was not found. Check the ID or ask the admin."
        if _registered(conn, role, user_id):
            return False, "This ID is already registered. Please login."
    salt = os.urandom(16).hex()
    cur = conn.cursor()
    cur.execute("INSERT INTO accounts (role, user_id, salt, pw_hash) VALUES (%s,%s,%s,%s)",
                (role, user_id, salt, hash_password(password, salt)))
    conn.commit()
    return True, "Registration successful. You can login now."


def login(conn, role, user_id, password):
    """Returns (ok, message, display_name, user_id)."""
    user_id = user_id.strip()
    if role == "admin":
        user_id = ADMIN_ID
    if not user_id or not password:
        return False, "Please enter your ID and password.", None, None
    cur = conn.cursor()
    cur.execute("SELECT salt, pw_hash FROM accounts WHERE role=%s AND user_id=%s",
                (role, user_id))
    row = cur.fetchone()
    if row is None:
        if role != "admin" and _person(conn, role, user_id) is None:
            return False, "This ID was not found.", None, None
        return False, "Not registered yet. Please use Register first.", None, None
    if not hmac.compare_digest(hash_password(password, row[0]), row[1]):
        return False, "Wrong password.", None, None
    return True, "Welcome!", _person(conn, role, user_id), user_id
