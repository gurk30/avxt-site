# Deploying avxt.ca

Source of truth for records and steps. All doc citations verified 2026-08-20
against docs.github.com.

## 1. GitHub Pages

- Repo: `gurk30/avxt-site`, **public** (GitHub Free only serves Pages from
  public repos — docs.github.com plan comparison), default branch `master`.
- Settings → Pages → Build and deployment → Source: *Deploy from a branch*,
  Branch `master`, folder `/docs`.
- Custom domain: `avxt.ca` (also written in `docs/CNAME`, so a redeploy can
  never drop it). With the apex as the custom domain, GitHub redirects
  `www.avxt.ca` → `avxt.ca` once both records exist.
- After the certificate issues (Let's Encrypt, usually minutes after DNS
  checks pass): tick **Enforce HTTPS** on the same settings page.
- Recommended hardening: Settings (account) → Pages → *Verified domains* →
  add avxt.ca; GitHub supplies a `_github-pages-challenge-gurk30` TXT record.

## 2. Spaceship DNS (Advanced DNS panel, zone avxt.ca)

Leave every existing Spacemail record (MX ×2, SPF TXT, DKIM, DMARC,
autodiscover SRV) untouched. Add exactly these nine:

| Type  | Host | Value                     | TTL  |
|-------|------|---------------------------|------|
| A     | @    | 185.199.108.153           | auto |
| A     | @    | 185.199.109.153           | auto |
| A     | @    | 185.199.110.153           | auto |
| A     | @    | 185.199.111.153           | auto |
| AAAA  | @    | 2606:50c0:8000::153       | auto |
| AAAA  | @    | 2606:50c0:8001::153       | auto |
| AAAA  | @    | 2606:50c0:8002::153       | auto |
| AAAA  | @    | 2606:50c0:8003::153       | auto |
| CNAME | www  | gurk30.github.io          | auto |

(IPs from docs.github.com "Managing a custom domain for your GitHub Pages
site", read 2026-08-20. AAAA optional per docs but recommended alongside A.)

## 3. Verify (no green by assumption)

1. `https://gurk30.github.io/avxt-site/` serves the page (pre-DNS proof the
   Pages build works — note absolute asset paths 404 here; the real check
   is the custom domain).
2. `nslookup -type=A avxt.ca 8.8.8.8` returns the four 185.199.x IPs.
3. `curl -sI https://avxt.ca/` → `HTTP/2 200` after cert issuance.
4. `curl -sI http://avxt.ca/` → 301 to https once Enforce HTTPS is on.
5. Page renders in a real browser at https://avxt.ca with fonts + art.
6. Email must stay alive: `nslookup -type=MX avxt.ca` still returns
   mx1/mx2.spacemail.com (we only added records, never touched mail).

## Rollback

Delete the nine DNS records → the domain goes back to no-website state;
email unaffected. The repo/Pages site can stay up harmlessly.

## Update flow (copy or design changes)

1. Edit `copy/landing-copy.md`, mirror into `docs/index.html`.
2. `python -m pytest tests/ -q` → 23 green, voice gate included.
3. Commit and push to master. Pages redeploys automatically in ~1 min.
