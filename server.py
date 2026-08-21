#!/usr/bin/env python3
"""avxt.ca server: static files from docs/ plus POST /api/contact.

Stdlib only, one process. Replaces the nginx-only container (2026-08-21,
owner ruling: contact form instead of mailto CTAs).

Contact submissions ALWAYS persist to DATA_DIR/submissions.jsonl (a Fly
volume in production), and are ALSO emailed via Spacemail SMTP when
SMTP_PASSWORD is set. The password is a Fly secret the owner sets himself:

    flyctl secrets set SMTP_PASSWORD=... -a avxt-site

It never lives in this repo (vault INV-3). With no password set, the
server logs MAIL-DISABLED loudly on boot and on every submission, and
the disk log is the only delivery until the secret exists.
"""

import gzip
import json
import os
import re
import smtplib
import sys
import threading
import time
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
DATA_DIR = Path(os.environ.get("DATA_DIR", str(ROOT / "data")))
PORT = int(os.environ.get("PORT", "8080"))

SMTP_HOST = os.environ.get("SMTP_HOST", "mail.spacemail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "karan@avxt.ca")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
MAIL_TO = os.environ.get("MAIL_TO", "karan@avxt.ca")

MAX_BODY = 10_000          # bytes; a real submission is well under 4KB
RATE_LIMIT = 5             # submissions per window per IP
RATE_WINDOW = 3600         # seconds

MIME = {
    ".html": "text/html; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".webmanifest": "application/manifest+json",
    ".json": "application/json",
}
IMMUTABLE = {".woff2", ".png", ".svg", ".ico"}
COMPRESSIBLE = {".html", ".txt", ".svg", ".json"}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_rate_lock = threading.Lock()
_rate: dict[str, list[float]] = {}

_gzip_lock = threading.Lock()
_gzip_cache: dict[tuple[str, float], bytes] = {}


def rate_allowed(ip: str, now: float | None = None) -> bool:
    """True if this IP may submit; records the attempt when allowed."""
    now = time.time() if now is None else now
    with _rate_lock:
        hits = [t for t in _rate.get(ip, []) if now - t < RATE_WINDOW]
        if len(hits) >= RATE_LIMIT:
            _rate[ip] = hits
            return False
        hits.append(now)
        _rate[ip] = hits
        return True


def validate(fields: dict) -> tuple[dict | None, str]:
    """Returns (submission, "") or (None, reason).

    reason "honeypot" means: pretend success, never process.
    """
    def one(name: str, cap: int) -> str:
        vals = fields.get(name, [])
        raw = vals[0] if isinstance(vals, list) else str(vals)
        return " ".join(str(raw).split())[:cap]

    if one("website", 200):
        return None, "honeypot"
    business = one("business", 120)
    phone = one("phone", 40)
    email = one("email", 120)
    notes = one("notes", 2000)
    if not business:
        return None, "business name required"
    if not phone and not email:
        return None, "phone or email required"
    if email and not EMAIL_RE.match(email):
        return None, "email looks malformed"
    return {
        "business": business,
        "phone": phone,
        "email": email,
        "notes": notes,
    }, ""


def persist(sub: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(sub, ensure_ascii=False)
    with open(DATA_DIR / "submissions.jsonl", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def send_mail(sub: dict) -> bool:
    if not SMTP_PASSWORD:
        print("MAIL-DISABLED: submission persisted to disk only "
              "(set SMTP_PASSWORD to enable email)", flush=True)
        return False
    msg = EmailMessage()
    msg["Subject"] = f"avxt.ca form: {sub['business']}"
    msg["From"] = SMTP_USER
    msg["To"] = MAIL_TO
    msg.set_content(
        "New form submission on avxt.ca\n\n"
        f"Business: {sub['business']}\n"
        f"Phone:    {sub['phone'] or '(not given)'}\n"
        f"Email:    {sub['email'] or '(not given)'}\n"
        f"Notes:    {sub['notes'] or '(none)'}\n\n"
        f"Received: {sub['received']} (UTC)\n"
    )
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20) as s:
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
        return True
    except Exception as e:  # persisted either way; never 500 the visitor
        print(f"MAIL-FAILED: {type(e).__name__}: {e}", flush=True)
        return False


def safe_path(url_path: str) -> Path | None:
    """Map a URL path to a file under DOCS, or None if outside/absent."""
    path = urlsplit(url_path).path
    if path.endswith("/"):
        path += "index.html"
    candidate = (DOCS / path.lstrip("/")).resolve()
    if not str(candidate).startswith(str(DOCS.resolve())):
        return None
    if candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate if candidate.is_file() else None


class Handler(BaseHTTPRequestHandler):
    server_version = "avxt"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # concise access log
        print(f"{self.client_ip()} {fmt % args}", flush=True)

    def client_ip(self) -> str:
        fwd = self.headers.get("Fly-Client-IP") or self.headers.get(
            "X-Forwarded-For", "")
        return fwd.split(",")[0].strip() if fwd else self.client_address[0]

    # ---------- static ----------

    def _send_file(self, head_only: bool = False) -> None:
        if self.path == "/healthz":
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not head_only:
                self.wfile.write(body)
            return
        target = safe_path(self.path)
        status = 200
        if target is None:
            target = DOCS / "404.html"
            status = 404
        suffix = target.suffix.lower()
        data = target.read_bytes()
        headers = {
            "Content-Type": MIME.get(suffix, "application/octet-stream"),
            "X-Content-Type-Options": "nosniff",
        }
        if suffix in IMMUTABLE:
            headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            headers["Cache-Control"] = "no-cache"
        accepts_gzip = "gzip" in self.headers.get("Accept-Encoding", "")
        if suffix in COMPRESSIBLE and accepts_gzip and len(data) > 1400:
            key = (str(target), target.stat().st_mtime)
            with _gzip_lock:
                if key not in _gzip_cache:
                    _gzip_cache.clear()  # tiny site: one generation at a time
                    _gzip_cache[key] = gzip.compress(data, 6)
                data = _gzip_cache[key]
            headers["Content-Encoding"] = "gzip"
            headers["Vary"] = "Accept-Encoding"
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def do_GET(self):
        self._send_file()

    def do_HEAD(self):
        self._send_file(head_only=True)

    # ---------- form ----------

    def _reply(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect_thanks(self) -> None:
        self.send_response(303)
        self.send_header("Location", "/thanks.html")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        if urlsplit(self.path).path != "/api/contact":
            self._reply(404, {"ok": False})
            return
        wants_json = "application/json" in self.headers.get("Accept", "")
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            self._reply(400, {"ok": False, "error": "bad request"})
            return
        raw = self.rfile.read(length).decode("utf-8", "replace")
        fields = parse_qs(raw, keep_blank_values=True)
        sub, reason = validate(fields)
        if reason == "honeypot":
            # pretend success; never persist, never mail
            self._reply(200, {"ok": True}) if wants_json \
                else self._redirect_thanks()
            return
        if sub is None:
            self._reply(400, {"ok": False, "error": reason})
            return
        if not rate_allowed(self.client_ip()):
            self._reply(429, {"ok": False, "error": "slow down"})
            return
        sub["received"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        sub["ip"] = self.client_ip()
        try:
            persist(sub)
        except OSError as e:
            print(f"PERSIST-FAILED: {e}", flush=True)
            self._reply(500, {"ok": False, "error": "server trouble"})
            return
        sub["emailed"] = send_mail(sub)
        print(f"SUBMISSION: {sub['business']} "
              f"(emailed={sub['emailed']})", flush=True)
        if wants_json:
            self._reply(200, {"ok": True})
        else:
            self._redirect_thanks()


def main() -> None:
    if not SMTP_PASSWORD:
        print("MAIL-DISABLED at boot: SMTP_PASSWORD not set; submissions "
              "persist to disk only", flush=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"serving docs/ + /api/contact on :{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
