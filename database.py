import json
from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from accounts import make_seed_account
from models import Account, Book

DATABASE_URL = "sqlite:///library.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def initialize_database() -> None:
    create_db_and_tables()
    seed_path = Path(__file__).parent / "seed_data.json"

    with Session(engine) as session:
        if session.exec(select(Account)).first() or session.exec(select(Book)).first():
            return

        with seed_path.open(encoding="utf-8") as file:
            seed_data = json.load(file)

        session.add_all(
            make_seed_account(
                username=account["username"],
                password=account["password"],
                role=account["role"],
            )
            for account in seed_data["accounts"]
        )
        session.add_all(
            Book(
                isbn=book["isbn"],
                title=book["title"],
                author=book["author"],
            )
            for book in seed_data["books"]
        )
        session.commit()
