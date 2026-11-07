import hashlib
import hmac
import json
import os
import re
import secrets

USERS_FILE = "users.json"
USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")
MIN_PASSWORD_LENGTH = 6

SEED_ACCOUNTS = [
    ("admin", "admin123", "admin"),
    ("alice", "alice123", "user"),
    ("bob", "bob123", "user"),
]


def _hash(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt_hex), 200_000
    ).hex()


def _save(users: dict) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def _make_record(password: str, role: str) -> dict:
    salt = secrets.token_hex(16)
    return {"salt": salt, "hash": _hash(password, salt), "role": role}


def _load() -> dict:
    """Loads accounts. On the very first run, creates the demo accounts."""
    if not os.path.isfile(USERS_FILE):
        users = {name: _make_record(pw, role) for name, pw, role in SEED_ACCOUNTS}
        _save(users)
        return users
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def verify_login(username: str, password: str):
    """Returns the user's role if the credentials are correct, otherwise None."""
    account = _load().get(username.strip().lower())
    if not account:
        return None
    if hmac.compare_digest(_hash(password, account["salt"]), account["hash"]):
        return account["role"]
    return None


def create_account(username: str, password: str, confirm: str):
    """Returns (success, message). New accounts are always regular users."""
    username = username.strip().lower()

    if not USERNAME_RE.match(username):
        return False, "Username must be 3-20 characters: letters, numbers or underscore."
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if password != confirm:
        return False, "Passwords do not match."

    users = _load()
    if username in users:
        return False, "That username is already taken."

    users[username] = _make_record(password, "user")
    _save(users)
    return True, "Account created."