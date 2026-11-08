from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Account(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, max_length=20)
    salt: str
    password_hash: str
    role: str = Field(default="user", max_length=20)


class Book(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    isbn: str = Field(index=True, unique=True, max_length=13)
    title: str
    author: str


class Loan(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id", index=True)
    account_id: int = Field(foreign_key="account.id", index=True)
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
