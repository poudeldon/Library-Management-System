import base64
import hashlib
import hmac
import html
import json
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from accounts import create_account, verify_login
from classes import Manage, User
from models import Book
from config import SECRET, COOKIE_NAME, COOKIE_MAX_AGE
from database import get_session, initialize_database


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Library Management", lifespan=lifespan)


# ---------- Cookie login ----------

def _sign(payload: str) -> str:
    return hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def make_cookie_value(username: str, role: str) -> str:
    data = json.dumps({"username": username, "role": role}).encode()
    payload = base64.urlsafe_b64encode(data).decode()
    return f"{payload}.{_sign(payload)}"


def read_cookie_value(value: str | None):
    """Returns {'username':..., 'role':...} or None if missing or tampered with."""
    if not value or "." not in value:
        return None
    payload, signature = value.split(".", 1)
    if not hmac.compare_digest(_sign(payload), signature):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
    except ValueError:
        return None
    if isinstance(data, dict) and "username" in data and "role" in data:
        return data
    return None


class NotLoggedIn(Exception):
    pass


@app.exception_handler(NotLoggedIn)
async def not_logged_in_handler(_request: Request, _exc: NotLoggedIn):
    return RedirectResponse("/login", status_code=303)


def optional_user(request: Request):
    return read_cookie_value(request.cookies.get(COOKIE_NAME))


def require_login(request: Request) -> dict:
    info = optional_user(request)
    if not info:
        raise NotLoggedIn()
    return info


def require_admin(info: dict = Depends(require_login)) -> dict:
    if info["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admins only.")
    return info


def load_user(info: dict, session: Session):
    manage = Manage(session)
    return User(info["username"], info["role"], manage), manage


# ---------- HTML helpers ----------

def e(text) -> str:
    return html.escape(str(text), quote=True)


CSS = """
body { font-family: Arial, sans-serif; background: #f4f6f8; margin: 0; color: #222; }
header { background: #2c3e50; color: #fff; padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; }
header a { color: #fff; margin-left: 16px; text-decoration: none; }
main { max-width: 640px; margin: 32px auto; background: #fff; padding: 24px; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }
h1 { margin-top: 0; }
input[type=text], input[type=password] { width: 100%; padding: 10px; margin: 6px 0 14px; box-sizing: border-box; }
button, .btn { background: #2980b9; color: #fff; border: 0; padding: 10px 16px; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; }
.btn.admin { background: #8e44ad; }
.menu { display: flex; flex-direction: column; gap: 12px; margin-top: 16px; }
.menu .btn { text-align: center; padding: 16px; font-size: 18px; }
.msg { padding: 10px; border-radius: 4px; margin-bottom: 16px; }
.msg.ok { background: #d4edda; } .msg.err { background: #f8d7da; }
ul { list-style: none; padding: 0; }
li { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid #eee; }
li form { margin: 0; }
.muted { color: #777; }
"""


def page(title: str, body: str, info: dict | None = None) -> HTMLResponse:
    nav = ""
    if info:
        nav = (f'{e(info["username"])} ({e(info["role"])}) '
               '<a href="/home">Home</a><a href="/logout">Logout</a>')
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} - Library</title><style>{CSS}</style></head>
<body><header><strong>Library Management</strong><span>{nav}</span></header>
<main>{body}</main></body></html>""")


def message(msg: str, ok: bool) -> str:
    if not msg:
        return ""
    return f'<div class="msg {"ok" if ok else "err"}">{e(msg)}</div>'


def book_info(book: Book) -> str:
    """Title, author and ISBN of one book."""
    return (f'<span><strong>{e(book.title)}</strong><br>'
            f'<small class="muted">by {e(book.author)} &middot; ISBN {e(book.isbn)}</small></span>')


def book_list(books: list[Book], button_label: str) -> str:
    items = "".join(
        f'<li>{book_info(b)}<form method="post">'
        f'<input type="hidden" name="isbn" value="{e(b.isbn)}">'
        f'<button type="submit">{button_label}</button></form></li>'
        for b in books
    )
    return f"<ul>{items}</ul>"


def plain_list(items, empty_text="(none)") -> str:
    if not items:
        return f'<ul><li class="muted">{empty_text}</li></ul>'
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


# ---------- Routes: entry, login, signup, logout ----------

@app.get("/")
def index():
    return RedirectResponse("/home", status_code=303)


def login_redirect(username: str, role: str):
    """Sends the user home and sets the signed login cookie."""
    response = RedirectResponse("/home", status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        make_cookie_value(username, role),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


def login_page(error: str = ""):
    body = f"""<h1>Login</h1>{message(error, False)}
<form method="post" action="/login">
  <label>Username</label>
  <input type="text" name="username" required autofocus>
  <label>Password</label>
  <input type="password" name="password" required>
  <button type="submit">Log in</button>
</form>
<p>First time here? <a href="/signup">Create an account</a></p>
<p class="muted">Demo: admin / admin123, alice / alice123, bob / bob123</p>"""
    return page("Login", body)


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if optional_user(request):
        return RedirectResponse("/home", status_code=303)
    return login_page()


@app.post("/login")
def login(
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    username = username.strip().lower()
    role = verify_login(session, username, password)
    if role:
        return login_redirect(username, role)
    return login_page("Invalid username or password.")


def signup_page(error: str = ""):
    body = f"""<h1>Create an account</h1>{message(error, False)}
<form method="post" action="/signup">
  <label>Username</label>
  <input type="text" name="username" required autofocus minlength="3" maxlength="20">
  <label>Password</label>
  <input type="password" name="password" required minlength="6">
  <label>Confirm password</label>
  <input type="password" name="confirm" required>
  <button type="submit">Sign up</button>
</form>
<p class="muted">Already have an account? <a href="/login">Log in</a></p>"""
    return page("Sign up", body)


@app.get("/signup", response_class=HTMLResponse)
def signup_form(request: Request):
    if optional_user(request):
        return RedirectResponse("/home", status_code=303)
    return signup_page()


@app.post("/signup")
def signup(
    username: str = Form(...),
    password: str = Form(...),
    confirm: str = Form(...),
    session: Session = Depends(get_session),
):
    ok, msg = create_account(session, username, password, confirm)
    if not ok:
        return signup_page(msg)
    # Log the new user in straight away
    return login_redirect(username.strip().lower(), "user")


@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


# ---------- Routes: home ----------

@app.get("/home", response_class=HTMLResponse)
def home(info: dict = Depends(require_login)):
    admin_link = (
        '<a class="btn admin" href="/add-book">Add a book (admin)</a>'
        if info["role"] == "admin" else ""
    )
    body = f"""<h1>Welcome, {e(info["username"])}!</h1>
<p>What would you like to do?</p>
<div class="menu">
  <a class="btn" href="/borrow">Borrow a book</a>
  <a class="btn" href="/return">Return a book</a>
  <a class="btn" href="/display">Display books</a>
  {admin_link}
</div>"""
    return page("Home", body, info)


# ---------- Routes: borrow ----------

def borrow_page(info, manage, msg="", ok=False):
    books = manage.library.get_books()
    content = (book_list(books, "Borrow") if books
               else '<p class="muted">No books are available right now.</p>')
    return page("Borrow", f"<h1>Borrow a book</h1>{message(msg, ok)}{content}", info)


@app.get("/borrow", response_class=HTMLResponse)
def borrow_form(
    info: dict = Depends(require_login), session: Session = Depends(get_session)
):
    _, manage = load_user(info, session)
    return borrow_page(info, manage)


@app.post("/borrow", response_class=HTMLResponse)
def borrow(
    isbn: str = Form(""),
    info: dict = Depends(require_login),
    session: Session = Depends(get_session),
):
    user, manage = load_user(info, session)
    ok, msg = user.take_book(isbn)
    return borrow_page(info, manage, msg, ok)


# ---------- Routes: return ----------

def return_page(info, user, msg="", ok=False):
    mine = user.borrowed_books()
    content = (book_list(mine, "Return") if mine
               else '<p class="muted">You have no borrowed books.</p>')
    return page("Return", f"<h1>Return a book</h1>{message(msg, ok)}{content}", info)


@app.get("/return", response_class=HTMLResponse)
def return_form(
    info: dict = Depends(require_login), session: Session = Depends(get_session)
):
    user, _ = load_user(info, session)
    return return_page(info, user)


@app.post("/return", response_class=HTMLResponse)
def return_book(
    isbn: str = Form(""),
    info: dict = Depends(require_login),
    session: Session = Depends(get_session),
):
    user, _ = load_user(info, session)
    ok, msg = user.return_book(isbn)
    return return_page(info, user, msg, ok)


# ---------- Routes: display ----------

@app.get("/display", response_class=HTMLResponse)
def display(
    info: dict = Depends(require_login), session: Session = Depends(get_session)
):
    user, manage = load_user(info, session)
    body = "<h1>Available books</h1>"
    body += plain_list([book_info(b) for b in manage.library.get_books()])
    body += "<h1>Books you hold</h1>"
    body += plain_list([book_info(b) for b in user.borrowed_books()])

    if user.is_admin():
        body += "<h1>All issued books</h1>"
        body += plain_list(
            [f'{book_info(book)}<span class="muted">taken by {e(account.username)}</span>'
             for book, account in manage.issued_books()],
            "(no books issued)",
        )
    return page("Display", body, info)


# ---------- Routes: add book (admin only) ----------

def add_book_page(info, msg="", ok=False):
    body = f"""<h1>Add a book</h1>{message(msg, ok)}
<form method="post" action="/add-book">
  <label>ISBN (10 or 13 digits)</label>
  <input type="text" name="isbn" required autofocus>
  <label>Title</label>
  <input type="text" name="title" required>
  <label>Author</label>
  <input type="text" name="author" required>
  <button type="submit">Add book</button>
</form>"""
    return page("Add Book", body, info)


@app.get("/add-book", response_class=HTMLResponse)
def add_book_form(info: dict = Depends(require_admin)):
    return add_book_page(info)


@app.post("/add-book", response_class=HTMLResponse)
def add_book(
    isbn: str = Form(""),
    title: str = Form(""),
    author: str = Form(""),
    info: dict = Depends(require_admin),
    session: Session = Depends(get_session),
):
    _, manage = load_user(info, session)
    ok, msg = manage.add_book(isbn, title, author)
    return add_book_page(info, msg, ok)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000, log_level="info")