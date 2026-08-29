"""Test suite for the avxt.ca landing page.

Run from the repo root:  python -m pytest tests/ -q

What is enforced and why:
- voice gate: every visible word is storefront copy in the owner's name; the
  vault's voice_check.py must pass (exit 0) on copy/landing-copy.md.
- copy sync: the deployed HTML's visible text must be a subset of the gated
  copy file, so un-gated copy can never ship.
- self-containment: the live page makes zero third-party requests.
- art integrity: the inline contour SVG must match a fresh deterministic
  generation from tools/gen_contours.py.
- accessibility floors: WCAG AA contrast on every token pair actually used,
  single h1, labelled nav, hidden decorative SVG, working skip link.
- performance floor: page weight budget (research: instant-feel budget for a
  contractor's phone, well under the ~500KB guideline).
"""

import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
INDEX = DOCS / "index.html"
NOTFOUND = DOCS / "404.html"
THANKS = DOCS / "thanks.html"
COPY = ROOT / "copy" / "landing-copy.md"
# The vault moved off the Windows box with the rest of the stack, and this path
# never followed it -- so the voice gate has been skipping, not passing, on
# every run since. First existing path wins; the skipif still covers a machine
# that has no vault at all.
VAULT_CHECKER = next(
    (p for p in (
        Path.home() / "brain-vault" / "scripts" / "voice_check.py",
        Path(r"C:\Users\gurka\Brain Vault\scripts\voice_check.py"),
    ) if p.exists()),
    Path.home() / "brain-vault" / "scripts" / "voice_check.py",
)

sys.path.insert(0, str(ROOT / "tools"))
import gen_contours  # noqa: E402


# ---------- helpers ----------

class TextExtractor(HTMLParser):
    """Visible text nodes, skipping non-content elements.

    Also skips subtrees marked data-dynamic (JS-filled, e.g. the live clock
    chip) and aria-hidden="true" (decorative arrows, the footer watermark) —
    those are not reader copy in the voice-gate sense.
    """

    SKIP = {"style", "script", "svg", "title"}
    VOID = {"meta", "link", "br", "img", "input", "hr", "source"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth_skip = 0
        self.hidden_stack = []
        self.texts = []

    @staticmethod
    def _non_content(attrs) -> bool:
        d = dict(attrs)
        return "data-dynamic" in d or d.get("aria-hidden") == "true"

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth_skip += 1
        elif tag not in self.VOID:
            self.hidden_stack.append(self._non_content(attrs))

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            if self.depth_skip:
                self.depth_skip -= 1
        elif tag not in self.VOID and self.hidden_stack:
            self.hidden_stack.pop()

    def handle_data(self, data):
        if not self.depth_skip and not any(self.hidden_stack) and data.strip():
            self.texts.append(data.strip())


class TagBalancer(HTMLParser):
    VOID = {"meta", "link", "br", "img", "input", "hr", "source", "path",
            "stop", "circle", "rect"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack:
            self.errors.append(f"closing </{tag}> with empty stack")
        elif self.stack[-1] != tag:
            self.errors.append(f"expected </{self.stack[-1]}>, got </{tag}>")
        else:
            self.stack.pop()


def visible_text(path: Path) -> list[str]:
    p = TextExtractor()
    p.feed(path.read_text(encoding="utf-8"))
    return p.texts


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\u00a0", " ")).strip()


def rel_lum(hexcolor: str) -> float:
    h = hexcolor.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(fg: str, bg: str) -> float:
    l1, l2 = sorted((rel_lum(fg), rel_lum(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


HTML = INDEX.read_text(encoding="utf-8")
COPY_TEXT = norm(COPY.read_text(encoding="utf-8"))


# ---------- voice gate ----------

@pytest.mark.skipif(not VAULT_CHECKER.exists(), reason="vault checker not on this machine")
def test_voice_gate_passes():
    r = subprocess.run(
        [sys.executable, str(VAULT_CHECKER), str(COPY)],
        capture_output=True, text=True, cwd=str(VAULT_CHECKER.parent.parent),
    )
    assert r.returncode == 0, f"voice_check FAILED:\n{r.stdout}\n{r.stderr}"


# ---------- copy sync ----------

@pytest.mark.parametrize("page", [INDEX, NOTFOUND, THANKS])
def test_every_visible_string_is_gated(page):
    missing = [t for t in visible_text(page) if norm(t) not in COPY_TEXT]
    assert not missing, f"visible text not in gated copy file: {missing}"


def test_key_strings_present():
    text = norm(" ".join(visible_text(INDEX)))
    for needle in [
        "Every call gets answered, even when no one can get to the phone.",
        "Two plans, on paper before you sign.",
        "$30 a month",
        "from $200 a month",
        "Billing starts the day your test call passes",
        "Get a free missed call audit",
        "Send it",
        "This site runs no trackers and sets no cookies.",
    ]:
        assert needle in text, f"missing from page: {needle}"


# ---------- banned typography ----------

@pytest.mark.parametrize("page", [INDEX, NOTFOUND, THANKS])
def test_no_banned_typography(page):
    joined = " ".join(visible_text(page))
    for ch, name in [("\u2014", "em dash"), ("\u2013", "en dash"),
                     ("\u2026", "ellipsis char")]:
        assert ch not in joined, f"banned character on page: {name}"


# ---------- self-containment ----------

def test_no_external_requests():
    urls = re.findall(r'(?:href|src)="([^"]+)"', HTML)
    urls += re.findall(r"url\(['\"]?([^)'\"]+)", HTML)
    bad = [u for u in urls
           if not (u.startswith(("/", "#", "mailto:", "tel:", "https://avxt.ca")))]
    assert not bad, f"external or non-root-relative references: {bad}"


def test_referenced_local_assets_exist():
    urls = re.findall(r'(?:href|src)="(/[^"]+)"', HTML)
    urls += re.findall(r"url\('(/[^']+)'\)", HTML)
    missing = [u for u in set(urls) if not (DOCS / u.lstrip("/")).exists()]
    assert not missing, f"referenced assets missing on disk: {missing}"


# ---------- meta ----------

def test_meta_completeness():
    head = HTML.split("</head>")[0]
    assert "<title>AVXT" in head
    desc = re.search(r'name="description" content="([^"]+)"', head).group(1)
    assert 50 <= len(desc) <= 250
    for needle in [
        'rel="canonical" href="https://avxt.ca/"',
        'property="og:title"', 'property="og:description"',
        'property="og:image" content="https://avxt.ca/og.png"',
        'property="og:url"', 'name="twitter:card"',
        'name="viewport"', 'charset="utf-8"', 'name="theme-color"',
        'rel="icon" href="/favicon.svg"', 'rel="apple-touch-icon"',
    ]:
        assert needle in head, f"missing in <head>: {needle}"
    assert '<html lang="en-CA">' in HTML


def test_font_preloads_have_crossorigin():
    # per web.dev: same-origin font preloads still need crossorigin or the
    # browser double-fetches
    for m in re.finditer(r'<link rel="preload"[^>]+as="font"[^>]*>', HTML):
        assert "crossorigin" in m.group(0), m.group(0)


# ---------- art integrity ----------

def test_inline_art_matches_generator():
    m = re.search(r"<!-- contours:start -->(.*?)<!-- contours:end -->", HTML, re.S)
    assert m, "contour markers missing from index.html"
    assert m.group(1) == gen_contours.build(), (
        "inline art out of sync: run tools/gen_contours.py + tools/inject_art.py"
    )


def test_generator_is_deterministic():
    assert gen_contours.build() == gen_contours.build()


# ---------- accessibility ----------

def test_contrast_aa():
    pairs = [
        ("#c3c7d9", "#0c0d12", 4.5, "body text on card"),
        ("#f4f5f9", "#0c0d12", 4.5, "headline on card"),
        ("#8f93a8", "#0c0d12", 4.5, "dim text on card"),
        ("#ffffff", "#4353ff", 4.5, "button label on indigo"),
    ]
    for fg, bg, floor, what in pairs:
        c = contrast(fg, bg)
        assert c >= floor, f"{what}: {c:.2f} < {floor}"


def test_single_h1_and_heading_order():
    assert len(re.findall(r"<h1[ >]", HTML)) == 1
    assert not re.search(r"<h[3-6][ >]", HTML), "only h1/h2 belong on this page"


def test_a11y_landmarks():
    assert '<nav aria-label=' in HTML
    assert 'aria-hidden="true"' in HTML  # decorative contour svg
    assert re.search(r'<a class="skip" href="#main">', HTML)
    assert '<main id="main"' in HTML
    assert ":focus-visible" in HTML
    assert "prefers-reduced-motion" in HTML


def test_no_identity_on_page():
    # owner ruling 2026-08-21: name and email off the page, form instead
    assert "mailto:" not in HTML
    assert "karan@avxt.ca" not in HTML
    assert "Gurkaran" not in HTML


def test_callback_number_is_reachable():
    # The line is armed and answers 24/7, and until 2026-08-29 this page was the
    # one surface a buyer lands on that carried no way to dial it. Three shops
    # have called it unprompted with zero promotion behind it, so a silent
    # regression here costs the only channel that has ever produced inbound.
    # E.164 in the href (a contractor's phone dials it from any area code),
    # human formatting in the text.
    assert HTML.count('href="tel:+15313213883"') == 2, "contact section + footer"
    text = norm(" ".join(visible_text(INDEX)))
    assert "531-321-3883" in text, "the number must be readable, not just dialable"
    # The form stays the primary route (owner ruling 2026-08-21); the number is
    # an addition to the contact section, never a replacement for it.
    assert 'action="/api/contact"' in HTML


def test_contact_form():
    assert '<form class="cform" id="cform" method="post" action="/api/contact">' in HTML
    for field in ['name="business"', 'name="phone"', 'name="email"',
                  'name="notes"', 'name="website"']:
        assert field in HTML, f"form field missing: {field}"
    # honeypot must be hidden from readers and screen readers alike
    assert '<div class="hp" aria-hidden="true">' in HTML
    assert 'type="submit"' in HTML
    # required floors mirror the server's validation
    assert re.search(r'name="business"[^>]*required', HTML)
    assert re.search(r'name="phone"[^>]*required', HTML)
    # the hidden attribute must beat display classes, or the form never
    # disappears on success (caught live 2026-08-21)
    assert "[hidden]{display:none!important}" in HTML


def test_thanks_page():
    html = THANKS.read_text(encoding="utf-8")
    assert 'name="robots" content="noindex"' in html
    assert 'href="https://avxt.ca/"' in html


# ---------- structure ----------

@pytest.mark.parametrize("page", [INDEX, NOTFOUND, THANKS])
def test_tags_balanced(page):
    b = TagBalancer()
    b.feed(page.read_text(encoding="utf-8"))
    assert not b.errors, b.errors
    assert not b.stack, f"unclosed tags: {b.stack}"


# ---------- deploy files ----------

def test_fly_config():
    # hosting moved to Fly (owner ruling 2026-08-20); the GitHub Pages CNAME
    # artifact must stay gone or a re-enabled Pages build would fight Fly
    assert not (DOCS / "CNAME").exists()
    fly = (ROOT / "fly.toml").read_text()
    assert 'app = "avxt-site"' in fly and 'primary_region = "yyz"' in fly
    # the form (2026-08-21) needs the python server, its volume, and no
    # SMTP secret in the repo
    assert 'source = "avxt_data"' in fly and 'destination = "/data"' in fly
    # the password is a Fly secret; an assignment line here would be INV-3
    assert not re.search(r"(?m)^\s*SMTP_PASSWORD\s*=", fly)
    docker = (ROOT / "Dockerfile").read_text()
    assert "server.py" in docker and "python" in docker


def test_robots():
    r = (DOCS / "robots.txt").read_text()
    assert "User-agent: *" in r and "Allow: /" in r


def test_404_page():
    html404 = NOTFOUND.read_text(encoding="utf-8")
    assert 'href="https://avxt.ca/"' in html404
    assert 'name="robots" content="noindex"' in html404


# ---------- performance ----------

def test_fonts_are_woff2_and_small():
    fonts = sorted((DOCS / "fonts").glob("space-grotesk-*.woff2"))
    assert len(fonts) == 3
    for f in fonts:
        assert f.read_bytes()[:4] == b"wOF2", f"{f.name} is not woff2"
        assert f.stat().st_size < 20_000, f"{f.name} over 20KB"


def test_page_weight_budget():
    total = INDEX.stat().st_size
    total += sum(f.stat().st_size for f in (DOCS / "fonts").glob("*.woff2"))
    total += (DOCS / "favicon.svg").stat().st_size
    assert INDEX.stat().st_size < 80_000, "index.html over 80KB"
    assert total < 200_000, f"critical-path weight {total:,} over 200KB budget"
