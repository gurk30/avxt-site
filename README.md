# avxt-site — the avxt.ca landing page

The public page for AVXT (AI receptionist for Ontario home service shops).
One static page, zero JavaScript, zero third-party requests, self-hosted
subset fonts. Built 2026-08-20; style A ("dark card") picked by the owner
from four candidates the same evening (comps in `comps/`).

## Layout

```
docs/            what actually deploys (GitHub Pages serves this folder)
  index.html     the page (style A), contour art inlined between markers
  404.html       not-found page, same copy governance
  fonts/         Space Grotesk latin subsets (woff2, built locally)
  og.png         link-preview card, favicon.* / apple-touch-icon.png
  CNAME          custom-domain binding for GitHub Pages (avxt.ca)
  _gen/          generator output + local check pages (gitignored, never deploys)
copy/landing-copy.md   EVERY visible string on the page, in order — see below
tools/           fetch_font / build_fonts / gen_contours / inject_art / gen_images
tests/           pytest suite (voice gate, copy sync, a11y, perf, integrity)
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

**Standing copy caveat:** "The first month is free" is the founding offer
(one client, sales-kit-founding-offer.md). When the founding page is
countersigned, that paragraph must be rewritten (shop B gets band price,
no free month) — update copy + page + re-gate the same day.

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

## Hosting decision (2026-08-20, simplest-first per the standing rule)

Options enumerated: GitHub Pages (free, public repo required on Free plan —
docs.github.com plan table), Cloudflare Pages (rejected: apex custom domain
needs the zone on Cloudflare nameservers; moving NS off Spaceship mid
email-warm-up risks the Spacemail records), Fly.io static ($2.02/mo/machine,
fly.io/docs/about/pricing — viable fallback, and flyctl auth on this PC is
currently expired anyway), Spaceship hosting (paid, adds nothing over Pages).
Picked: **GitHub Pages from `docs/` on master**, public repo `gurk30/avxt-site`.

## Deploy

See DEPLOY.md for the exact GitHub Pages + Spaceship DNS records and the
verification checklist.
