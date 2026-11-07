import json
import os
import re

ISBN_RE = re.compile(r"^(\d{13}|\d{9}[\dX])$")


def clean_isbn(isbn: str) -> str:
    """Removes spaces and hyphens and uppercases the final X."""
    return re.sub(r"[\s-]", "", isbn).upper()


class Library:
    """Stores the books that are on the shelf. Each book is a dict:
    {"isbn": ..., "title": ..., "author": ...}"""

    def __init__(self, books=None):
        self._books = list(books or [])

    def get_books(self):
        return list(self._books)

    def has_book(self, isbn):
        return any(b["isbn"] == isbn for b in self._books)

    def add_book(self, book):
        self._books.append(book)

    def remove_book(self, isbn):
        """Removes the book from the shelf and returns it."""
        for book in self._books:
            if book["isbn"] == isbn:
                self._books.remove(book)
                return book
        return None

class Manage:
    """Tracks which user has which book and saves everything to a JSON file."""

    DEFAULT_BOOKS = [
        {"isbn": "9780132350884", "title": "Clean Code", "author": "Robert C. Martin"},
        {"isbn": "9781593279288", "title": "Python Crash Course", "author": "Eric Matthes"},
        {"isbn": "9781492056355", "title": "Fluent Python", "author": "Luciano Ramalho"},
        {"isbn": "9780262046305", "title": "Introduction to Algorithms", "author": "Thomas H. Cormen"},
    ]

    def __init__(self, library, records, file):
        self.library = library
        self.records = records  # {isbn: {"user": username, "book": {...}}}
        self.file = file

    @classmethod
    def load(cls, file):
        data = {"books": [dict(b) for b in cls.DEFAULT_BOOKS], "records": {}}
        if os.path.isfile(file):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
            except (json.JSONDecodeError, OSError):
                saved = {}

            books = saved.get("books", [])
            records = saved.get("records", {})

            # Old format stored plain strings; the new format uses dicts.
            old_books = any(not isinstance(b, dict) for b in books)
            old_records = any(not isinstance(r, dict) for r in records.values())

            if not old_books and not old_records and "books" in saved:
                data = {"books": books, "records": records}
        return cls(Library(data["books"]), data["records"], file)

    def _save(self):
        data = {"books": self.library.get_books(), "records": self.records}
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def books_of(self, username):
        return [r["book"] for r in self.records.values() if r["user"] == username]

    # Each action returns (success, message)

    def add_book(self, isbn, title, author):
        isbn = clean_isbn(isbn)
        title = title.strip()
        author = author.strip()

        if not ISBN_RE.match(isbn):
            return False, "ISBN must be 10 or 13 digits (the last digit of a 10-digit ISBN can be X)."
        if not title:
            return False, "Title cannot be empty."
        if not author:
            return False, "Author cannot be empty."
        if self.library.has_book(isbn) or isbn in self.records:
            return False, f"A book with ISBN {isbn} already exists."

        self.library.add_book({"isbn": isbn, "title": title, "author": author})
        self._save()
        return True, f"'{title}' by {author} was added to the library."

    def issue_book(self, username, isbn):
        if not self.library.has_book(isbn):
            if isbn in self.records:
                title = self.records[isbn]["book"]["title"]
                return False, f"'{title}' is already taken by {self.records[isbn]['user']}."
            return False, "That book does not exist in the library."
        book = self.library.remove_book(isbn)
        self.records[isbn] = {"user": username, "book": book}
        self._save()
        return True, f"You borrowed '{book['title']}'."

    def receive_book(self, username, isbn):
        record = self.records.get(isbn)
        if not record or record["user"] != username:
            return False, "You did not borrow that book."
        del self.records[isbn]
        self.library.add_book(record["book"])
        self._save()
        return True, f"You returned '{record['book']['title']}'."

class User:
    """A person who takes and returns books."""

    def __init__(self, name, role, manage):
        self.name = name
        self.role = role
        self.manage = manage

    def is_admin(self):
        return self.role == "admin"

    def take_book(self, isbn):
        return self.manage.issue_book(self.name, isbn)

    def return_book(self, isbn):
        return self.manage.receive_book(self.name, isbn)

    def borrowed_books(self):
        return self.manage.books_of(self.name)