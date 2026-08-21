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
  shared-cpu-1x/256MB machine, always on (~$2 USD/mo). nginx:1.27-alpine
  serving `docs/` per `nginx.conf` (gzip, immutable font/image caching,
  no-cache HTML, 404 page wired).
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

## Rollback

`fly apps destroy avxt-site` kills hosting; delete the three custom DNS
records above to return the domain to no-website state. Email unaffected
either way.
