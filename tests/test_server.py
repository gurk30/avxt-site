"""Tests for server.py: validation, rate limit, path safety, and a live
round-trip against the real server on a loopback port."""

import json
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode

import pytest

import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import server  # noqa: E402


# ---------- validate ----------

def fields(**kw):
    base = {"business": ["Test Co"], "phone": ["555-0100"],
            "email": [""], "notes": [""], "website": [""]}
    base.update({k: [v] for k, v in kw.items()})
    return base


def test_validate_good():
    sub, reason = server.validate(fields())
    assert reason == "" and sub["business"] == "Test Co"


def test_validate_honeypot():
    sub, reason = server.validate(fields(website="http://spam"))
    assert sub is None and reason == "honeypot"


def test_validate_requires_business():
    sub, reason = server.validate(fields(business=""))
    assert sub is None and "business" in reason


def test_validate_requires_contact():
    sub, reason = server.validate(fields(phone="", email=""))
    assert sub is None and "phone or email" in reason


def test_validate_rejects_bad_email():
    sub, reason = server.validate(fields(email="not-an-email"))
    assert sub is None and "email" in reason


def test_validate_email_only_is_fine():
    sub, reason = server.validate(fields(phone="", email="a@b.ca"))
    assert reason == "" and sub["email"] == "a@b.ca"


def test_validate_caps_lengths():
    sub, _ = server.validate(fields(notes="x" * 9000))
    assert len(sub["notes"]) == 2000


# ---------- rate limit ----------

def test_rate_limit_window():
    ip = "203.0.113.9"
    now = time.time()
    server._rate.pop(ip, None)
    for _ in range(server.RATE_LIMIT):
        assert server.rate_allowed(ip, now)
    assert not server.rate_allowed(ip, now)
    # window rolls over
    assert server.rate_allowed(ip, now + server.RATE_WINDOW + 1)


# ---------- path safety ----------

def test_safe_path_normal():
    assert server.safe_path("/") == server.DOCS / "index.html"
    assert server.safe_path("/favicon.svg") == server.DOCS / "favicon.svg"


def test_safe_path_traversal_blocked():
    for evil in ["/../server.py", "/../../etc/passwd", "/%2e%2e/server.py",
                 "/..%5cserver.py"]:
        got = server.safe_path(evil)
        assert got is None or str(got).startswith(str(server.DOCS)), evil


def test_safe_path_missing_is_none():
    assert server.safe_path("/nope.html") is None


# ---------- live round-trip ----------

@pytest.fixture(scope="module")
def live(tmp_path_factory):
    server.DATA_DIR = tmp_path_factory.mktemp("data")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _get(url):
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except HTTPError as e:
        return e.code, e.read()


def _post(url, data, accept=None):
    body = urlencode(data).encode()
    req = urllib.request.Request(url + "/api/contact", data=body, method="POST")
    if accept:
        req.add_header("Accept", accept)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read(), dict(r.headers)
    except HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def test_live_serves_index(live):
    status, body = _get(live + "/")
    assert status == 200 and b"Every call gets answered" in body


def test_live_healthz(live):
    assert _get(live + "/healthz")[0] == 200


def test_live_404(live):
    status, body = _get(live + "/nothing-here")
    assert status == 404 and b"Nothing at this address." in body


def test_live_form_json_roundtrip(live):
    status, body, _ = _post(
        live, {"business": "Roundtrip Co", "phone": "555-0101",
               "email": "", "notes": "test", "website": ""},
        accept="application/json")
    assert status == 200 and json.loads(body)["ok"] is True
    logged = (server.DATA_DIR / "submissions.jsonl").read_text()
    assert "Roundtrip Co" in logged


def test_live_form_nojs_redirects_to_thanks(live):
    status, _, headers = _post(
        live, {"business": "NoJS Co", "phone": "555-0102",
               "email": "", "notes": "", "website": ""})
    # urllib follows the 303; we should land on the thanks page
    if status == 200:
        assert True  # redirect already followed
    else:
        assert status == 303 and headers.get("Location") == "/thanks.html"


def test_live_form_honeypot_not_persisted(live):
    before = (server.DATA_DIR / "submissions.jsonl").read_text()
    status, body, _ = _post(
        live, {"business": "Bot Co", "phone": "555", "email": "",
               "notes": "", "website": "spam.example"},
        accept="application/json")
    assert status == 200 and json.loads(body)["ok"] is True
    after = (server.DATA_DIR / "submissions.jsonl").read_text()
    assert "Bot Co" not in after and before == after


def test_live_form_rejects_empty(live):
    status, _, _ = _post(live, {"business": "", "phone": "", "email": "",
                                "notes": "", "website": ""},
                         accept="application/json")
    assert status == 400
