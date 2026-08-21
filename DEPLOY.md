# Deploying avxt.ca

Hosting: **Fly.io** (owner ruling 2026-08-20 in-session: "host the website on
that server" after signing into Fly; implemented as its own tiny app in the
same personal org as nova-ai-receptionist, NOT inside the Nova machine — a
Nova redeploy from this PC would have shipped undeployed code to the line
that answers calls).

The earlier GitHub Pages deploy (same evening) is retired: custom domain
unbound, records replaced, repo made private. History in git.

## The Fly app

- App: `avxt-site`, org `personal`, region `yyz` (Toronto), single
  shared-cpu-1x/256MB machine, always on (~$2 USD/mo). Since 2026-08-21:
  `python:3.12-alpine` running `server.py` (static docs/ with gzip +
  immutable caching, `POST /api/contact`, `/healthz`), replacing the
  nginx-only container so the contact form has a backend.
- Volume: `avxt_data` (1GB, yyz) mounted at `/data` — every form
  submission appends to `/data/submissions.jsonl`, whether or not email
  is configured. Read it:
  `flyctl ssh console -a avxt-site -C "cat /data/submissions.jsonl"`.
- Email: submissions are mailed to karan@avxt.ca via Spacemail SMTP only
  once the secret exists — the owner sets it himself, so the password
  never reaches the repo or a session:
  `flyctl secrets set SMTP_PASSWORD=<spacemail password> -a avxt-site`
  Until then the server logs MAIL-DISABLED and disk is the only delivery.
- IPs: shared IPv4 `66.241.124.191`, dedicated IPv6 `2a09:8280:1::179:2e23:0`.
- Certs: `fly certs add avxt.ca` + `fly certs add www.avxt.ca` (Let's
  Encrypt, auto-renewing).

## DNS at Spaceship (zone avxt.ca) — live state since 2026-08-20 ~10:15 PM

Spacemail group (MX ×2, SPF, DKIM, autodiscover SRV) and the `_dmarc` TXT:
untouched. Custom records:

| Type  | Host | Value                     |
|-------|------|---------------------------|
| A     | @    | 66.241.124.191            |
| AAAA  | @    | 2a09:8280:1::179:2e23:0   |
| CNAME | www  | avxt-site.fly.dev         |

## Update flow (copy or design changes)

1. Edit `copy/landing-copy.md`, mirror into `docs/index.html`.
2. `python -m pytest tests/ -q` → all green (voice gate included).
3. `flyctl deploy --remote-only --ha=false` from the repo root.
4. Commit and push (repo is the source of record; deploys come from the
   working tree, so never deploy with uncommitted changes you don't intend).

## Verify (no green by assumption)

1. `https://avxt-site.fly.dev/` renders (bypasses DNS).
2. `nslookup avxt.ca 8.8.8.8` → 66.241.124.191.
3. `fly certs check avxt.ca -a avxt-site` → verified.
4. `https://avxt.ca` renders in a real browser; http:// redirects (force_https).
5. `nslookup -type=MX avxt.ca` still returns mx1/mx2.spacemail.com.
6. Submit the form with a test marker, then confirm the row landed:
   `flyctl ssh console -a avxt-site -C "cat /data/submissions.jsonl"` —
   and delete the test row after. If SMTP is configured, also confirm
   the email arrived.

## Rollback

`fly apps destroy avxt-site` kills hosting; delete the three custom DNS
records above to return the domain to no-website state. Email unaffected
either way.
