# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the project

```bash
# Install dependencies (system Python, no venv)
pip3 install fastapi uvicorn python-multipart --break-system-packages

# Start the server
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &

# Or with hot reload during development
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The server binds to `0.0.0.0` so it's reachable from Windows when running inside WSL2. Background processes must use `nohup` — plain `&` in this shell environment exits with code 144.

## Architecture

All files live in the root directory. No template engine, no static files folder.

### Files

- **`main.py`** — FastAPI app. Contains all routes, admin auth logic, and every HTML page as inline Python strings (`PAGE_HTML`, `_admin_login_html()`, `_admin_dashboard_html()`). Shared CSS is extracted into `_BASE_STYLE` and `_FONTS` constants to avoid repetition across the three pages.
- **`shortener.py`** — Business logic only: short code generation, deduplication, redirect, and info lookup.
- **`database.py`** — All SQLite access. Uses a `get_conn()` context manager that auto-commits and closes. `urls.db` is created in the working directory on first run.

### HTML templating pattern

There is no Jinja2 or similar. HTML is built as Python strings concatenated at import time (static pages) or at request time (admin dashboard, which embeds live data). JavaScript inside these strings must use **backtick template literals** — never single-quote string concatenation — to avoid quote escaping bugs that silently break `e.preventDefault()`.

### Route declaration order matters

FastAPI matches routes in declaration order. The `GET /{short_code}` catch-all must always be the **last** route registered, after all `/admin/*` and `/info/{short_code}` routes.

## API endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | — | Public frontend |
| `POST` | `/shorten` | — | `{"url": "https://..."}` → `{"short_url": "...", "short_code": "..."}` |
| `GET` | `/info/{short_code}` | — | Returns `short_code`, `original_url`, `created_at`, `clicks` |
| `GET` | `/{short_code}` | — | 307 redirect to original URL, increments click counter |
| `GET` | `/admin/login` | — | Login page |
| `POST` | `/admin/login` | — | Form submit: validates credentials, sets `admin_session` cookie |
| `GET` | `/admin/logout` | cookie | Discards session token, clears cookie |
| `GET` | `/admin` | cookie | Dashboard: stats + full URL table |

## Admin area

- Credentials are hardcoded constants in `main.py`: `ADMIN_USER = "admin"`, `ADMIN_PASS = "admin123"`.
- Sessions are stored in `_sessions: set[str]` (in-memory). Sessions are lost on server restart.
- Tokens are `secrets.token_hex(32)`, stored in an `HttpOnly` cookie named `admin_session`.
- `require_admin` is a FastAPI `Depends()` that raises a 307 redirect to `/admin/login` if the cookie is missing or invalid.
- Credential comparison uses `secrets.compare_digest` to prevent timing attacks.

## Database

Single table `urls`:

| Column | Type | Notes |
|--------|------|-------|
| `id` | `INTEGER` | Auto PK |
| `short_code` | `TEXT UNIQUE` | 6-char URL-safe base64 |
| `original_url` | `TEXT` | Full original URL |
| `created_at` | `TIMESTAMP` | SQLite `CURRENT_TIMESTAMP` (UTC) |
| `clicks` | `INTEGER` | Incremented on every redirect |

`database.py` exports: `init_db`, `get_conn`, `get_all_urls`, `get_stats`.

## Key behaviours

- **Deduplication**: `create_short_url` checks if the original URL already exists before inserting. The same long URL always returns the same short code.
- **`short_url` base**: derived from `request.base_url` at request time (not at startup), so it always reflects the URL the client actually used — critical for WSL2 where the machine IP differs from `localhost`.
- **Collision retry**: the generator retries up to 10 times on short code collision before raising `RuntimeError`.
- **Fonts**: `Syne` (headings) and `JetBrains Mono` (URLs/code) loaded from Google Fonts CDN. Pages degrade gracefully without internet but lose the custom typography.
