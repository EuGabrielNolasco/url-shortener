import secrets
from database import get_conn


def generate_short_code() -> str:
    return secrets.token_urlsafe(4)[:6]


def create_short_url(original_url: str) -> str:
    with get_conn() as conn:
        # Avoid duplicating already shortened URLs
        row = conn.execute(
            "SELECT short_code FROM urls WHERE original_url = ?", (original_url,)
        ).fetchone()
        if row:
            return row["short_code"]

        for _ in range(10):
            code = generate_short_code()
            exists = conn.execute(
                "SELECT 1 FROM urls WHERE short_code = ?", (code,)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO urls (short_code, original_url) VALUES (?, ?)",
                    (code, original_url),
                )
                return code

        raise RuntimeError("Failed to generate a unique short code")


def get_original_url(short_code: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT original_url FROM urls WHERE short_code = ?", (short_code,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE urls SET clicks = clicks + 1 WHERE short_code = ?", (short_code,)
            )
            return row["original_url"]
        return None


def get_url_info(short_code: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT short_code, original_url, created_at, clicks FROM urls WHERE short_code = ?",
            (short_code,),
        ).fetchone()
        if row:
            return dict(row)
        return None
