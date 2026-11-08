import re

from sqlmodel import Session, select

from models import Account, Book, Loan

ISBN_RE = re.compile(r"^(\d{13}|\d{9}[\dX])$")


def clean_isbn(isbn: str) -> str:
    """Removes spaces and hyphens and uppercases the final X."""
    return re.sub(r"[\s-]", "", isbn).upper()


class Library:
    def __init__(self, session: Session):
        self.session = session

    def get_books(self) -> list[Book]:
        loaned_book_ids = select(Loan.book_id)
        return list(
            self.session.exec(
                select(Book).where(Book.id.not_in(loaned_book_ids)).order_by(Book.title)
            )
        )

    def get_book(self, isbn: str) -> Book | None:
        return self.session.exec(
            select(Book).where(Book.isbn == isbn)
        ).first()

    def is_available(self, isbn: str) -> bool:
        book = self.get_book(isbn)
        if not book:
            return False

        return self.session.exec(
            select(Loan).where(Loan.book_id == book.id)
        ).first() is None

    def has_book(self, isbn: str) -> bool:
        return self.session.exec(select(Book).where(Book.isbn == isbn)).first() is not None


class Manage:
    def __init__(self, session: Session):
        self.session = session
        self.library = Library(session)

    def _account(self, username: str) -> Account | None:
        return self.session.exec(
            select(Account).where(Account.username == username)
        ).first()

    def books_of(self, username: str) -> list[Book]:
        account = self._account(username)
        if not account:
            return []
        return list(
            self.session.exec(
                select(Book)
                .join(Loan, Loan.book_id == Book.id)
                .where(Loan.account_id == account.id)
                .order_by(Book.title)
            )
        )

    def add_book(self, isbn: str, title: str, author: str) -> tuple[bool, str]:
        isbn, title, author = clean_isbn(isbn), title.strip(), author.strip()
        if not ISBN_RE.match(isbn):
            return False, "ISBN must be 10 or 13 digits (the last digit of a 10-digit ISBN can be X)."
        if not title:
            return False, "Title cannot be empty."
        if not author:
            return False, "Author cannot be empty."
        if self.library.get_book(isbn):
            return False, f"A book with ISBN {isbn} already exists."

        self.session.add(Book(isbn=isbn, title=title, author=author))
        self.session.commit()
        return True, f"'{title}' by {author} was added to the library."

    def issue_book(self, username: str, isbn: str) -> tuple[bool, str]:
        book = self.library.get_book(isbn)
        if not book:
            return False, "That book does not exist in the library."

        loan = self.session.exec(
            select(Loan).where(Loan.book_id == book.id)
        ).first()
        if loan:
            account = self.session.get(Account, loan.account_id)
            return False, f"'{book.title}' is already taken by {account.username}."

        account = self._account(username)
        if not account:
            return False, "That account does not exist."

        self.session.add(Loan(book_id=book.id, account_id=account.id))
        self.session.commit()
        return True, f"You borrowed '{book.title}'."

    def receive_book(self, username: str, isbn: str) -> tuple[bool, str]:
        account = self._account(username)
        loan = None
        if account:
            loan = self.session.exec(
                select(Loan)
                .join(Book, Loan.book_id == Book.id)
                .where(Loan.account_id == account.id, Book.isbn == isbn)
            ).first()
        if not loan:
            return False, "You did not borrow that book."
        book = self.session.get(Book, loan.book_id)
        self.session.delete(loan)
        self.session.commit()
        return True, f"You returned '{book.title}'."

    def issued_books(self) -> list[tuple[Book, Account]]:
        return list(
            self.session.exec(
                select(Book, Account)
                .join(Loan, Loan.book_id == Book.id)
                .join(Account, Loan.account_id == Account.id)
                .order_by(Book.title)
            )
        )


class User:
    def __init__(self, name: str, role: str, manage: Manage):
        self.name = name
        self.role = role
        self.manage = manage

    def is_admin(self) -> bool:
        return self.role == "admin"

    def take_book(self, isbn: str) -> tuple[bool, str]:
        return self.manage.issue_book(self.name, isbn)

    def return_book(self, isbn: str) -> tuple[bool, str]:
        return self.manage.receive_book(self.name, isbn)

    def borrowed_books(self) -> list[Book]:
        return self.manage.books_of(self.name)
