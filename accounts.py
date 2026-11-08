import hashlib
import hmac
import re
import secrets

from sqlmodel import Session, select

from config import SECRET
from models import Account

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")
MIN_PASSWORD_LENGTH = 6


def _hash(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt_hex), 200_000
    ).hex()


def _make_record(password: str, role: str) -> Account:
    salt = secrets.token_hex(16)
    return Account(
        username="",
        salt=salt,
        password_hash=_hash(password, salt),
        role=role,
    )


def make_seed_account(username: str, password: str, role: str) -> Account:
    """Create a deterministic seed account from the application secret."""
    salt = hmac.new(
        SECRET.encode(), username.encode(), hashlib.sha256
    ).hexdigest()[:32]
    return Account(
        username=username,
        salt=salt,
        password_hash=_hash(password, salt),
        role=role,
    )


def verify_login(session: Session, username: str, password: str) -> str | None:
    account = session.exec(
        select(Account).where(Account.username == username.strip().lower())
    ).first()
    if not account or not hmac.compare_digest(
        _hash(password, account.salt), account.password_hash
    ):
        return None
    return account.role


def create_account(
    session: Session, username: str, password: str, confirm: str
) -> tuple[bool, str]:
    username = username.strip().lower()

    if not USERNAME_RE.match(username):
        return False, "Username must be 3-20 characters: letters, numbers or underscore."
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if password != confirm:
        return False, "Passwords do not match."
    if session.exec(select(Account).where(Account.username == username)).first():
        return False, "That username is already taken."

    account = _make_record(password, "user")
    account.username = username
    session.add(account)
    session.commit()
    return True, "Account created."
