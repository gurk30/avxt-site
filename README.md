# avxt-site — the avxt.ca landing page

The public page for AVXT (AI receptionist for Ontario businesses — sector-
agnostic since 2026-08-20, owner ruling: land the first client, then build
in that sector).
One page plus a contact-form endpoint, zero third-party requests,
self-hosted subset fonts. Built 2026-08-20 (v1 killed same night, v2 is
the company-site rebuild); v2.3 (2026-08-21) added the full-background
contour hero, Jobber-style two-tier pricing (Answered $30 / Booked from
$200), and the contact form that replaced every mailto CTA — the owner's
name and email are deliberately absent from the page. `server.py` (python
stdlib) serves `docs/` and handles `POST /api/contact`: every submission
persists to the Fly volume and is emailed via Spacemail SMTP when the
`SMTP_PASSWORD` secret is set (owner-set only, never in this repo).

## Layout

```
server.py        static file server + POST /api/contact (python stdlib, no deps)
docs/            the site the server serves
  index.html     the page, contour art inlined between markers
  404.html       not-found page, same copy governance
  thanks.html    no-JS form fallback target
  fonts/         Space Grotesk latin subsets (woff2, built locally)
  og.png         link-preview card, favicon.* / apple-touch-icon.png
  _gen/          generator output + local check pages (gitignored, never deploys)
copy/landing-copy.md   EVERY visible string on the page, in order — see below
tools/           fetch_font / build_fonts / gen_contours / inject_art / gen_images
tests/           pytest suite (voice gate, copy sync, a11y, perf, server round-trip)
comps/           the three unpicked style candidates (B paper, C amber, D Swiss)
```

## Copy governance (do not skip)

The page is storefront copy in Karan's name, governed by the vault voice
module (`Brain Vault/.claude/rules/anti-ai-voice.md`). The rules this repo
enforces mechanically:

- `copy/landing-copy.md` holds every human-visible string. Change copy
  there first, then mirror it into the HTML.
- `python "C:\Users\gurka\Brain Vault\scripts\voice_check.py" copy/landing-copy.md`
  must exit 0. The test suite runs this.
- `tests/` assert the HTML's visible text is a subset of the gated file,
  so un-gated copy cannot ship while tests are green.

**Free month DEPRECATED 2026-08-20** (owner ruling, same night as launch:
charge for the product, don't give it away). The page now says billing
starts the day the test call passes. The old standing caveat about
rewriting the free-month paragraph at countersign is moot — there is no
free-month paragraph anymore.

**Two-tier pricing 2026-08-21** (owner ruling, Jobber-style): Answered at
$30/month flat, Booked from $200/month with the measured band-floor
mechanic. The $200 floor is the owner's ruled §6.3 band bottom. The
Answered tier is a NEW SKU that exists nowhere in the vault sales kit yet.

## Build (only needed when changing fonts/art)

```
python tools/fetch_font.py      # owner-approved download, google/fonts repo
python tools/build_fonts.py     # variable TTF -> 3 static latin woff2 subsets
python tools/gen_contours.py    # deterministic contour art -> docs/_gen/
python tools/inject_art.py      # splice art into index.html between markers
python tools/gen_images.py      # favicon.svg/pngs + og.png (same design math)
```

All generators are deterministic; `tests/` verify the inlined art matches a
fresh generation, so art and generator can never drift apart.

## Test

```
python -m pytest tests/ -q
```

23 checks: voice gate, copy sync, banned typography, zero external
requests, asset existence, meta/OG completeness, preload crossorigin,
art integrity + determinism, WCAG AA contrast on every used token pair,
single-h1/landmarks/skip-link, mailto CTAs, tag balance, CNAME/robots/404,
woff2 magic bytes, page-weight budget (critical path < 200 KB; actual ~62 KB).

## Hosting decision

2026-08-20, two rounds. Round 1 (simplest-first): GitHub Pages from /docs,
public repo (Free-plan requirement). Round 2, same evening: the owner signed
into Fly and ruled "host the website on that server" — moved to a dedicated
tiny Fly app (`avxt-site`, yyz) in the same org as Nova; the repo went
private since Pages no longer constrains visibility. Not deployed inside the
Nova machine itself: redeploying Nova from this PC would push undeployed
code (v1.2.1) to the production phone line. Cloudflare Pages stayed rejected
(nameserver move would risk Spacemail mid warm-up).

## Deploy

See DEPLOY.md for the exact GitHub Pages + Spaceship DNS records and the
verification checklist.
