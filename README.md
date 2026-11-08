# Library Management System

A small FastAPI-based library management application for managing books,
accounts, borrowing, and returns. Data is stored in a local SQLite database.

## Run locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/#installing-uv)

Install the project dependencies:

```bash
uv sync
```

Start the application with hot reload:

```bash
uv run main.py
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

The database is initialized automatically with the seed data on first run.
