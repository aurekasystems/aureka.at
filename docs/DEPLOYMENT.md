# Deployment on Blossom

The website runs on Blossom as its own Compose project below `/srv/sites/`
(own sites; client sites live below `/srv/clients/`), following the same
pattern as the other sites behind the shared proxy. A slim Caddy container serves only
`public/` over internal HTTP. The shared proxy (`aureka-proxy-caddy`)
terminates HTTPS and forwards over the Docker network `edge`.

> According to `aurekasystems/infrastructure`, Blossom is a preview/staging
> platform without production guarantees. `aureka.at` has been running there
> since 2026-11-25 as a temporary home; see [Moving off Blossom](#moving-off-blossom).

## Stable names

| Component | Value |
| --- | --- |
| Repository | `aurekasystems/aureka.at` |
| Server checkout | `/srv/sites/aureka.at/` |
| Compose project | `aureka-website` |
| Service | `website` |
| Alias on network `edge` | `aureka-website` |
| Domains | `aureka.at` (primary), `www.aureka.at` → redirect |

## Files

- `compose.yaml`: website stack with `caddy:2.11.4-alpine`, read-only mounts
  for `public/` and `deploy/Caddyfile`, healthcheck. No host port.
- `compose.override.yaml`: Blossom additions, external network `edge` and alias.
- `deploy/Caddyfile`: internal file server on port 80 with security headers;
  `/impressum` also serves `impressum.html`.
- `deploy/blossom/aureka-website.caddy`: route for the shared proxy. Because
  the site is on Blossom only temporarily, it is deliberately not tracked in
  `aurekasystems/infrastructure`.
- `deploy/blossom/systemd/site-pull@.service`, `site-pull@.timer`: pull the
  branch `release` on Blossom every minute (section 6).
- `.github/workflows/release.yml`: publishes each GitHub release to the branch
  `release` (section 6).

Always pass the base and override files together.

## 1. Before the first deployment

- Replace all `[…]` placeholders in `public/impressum.html`. Check:
  `grep -n '\[' public/impressum.html` must print nothing.
- Commit the changes and push them to `main`.

## 2. Checkout on Blossom (as `mjs`)

The repository is public; Blossom clones it over HTTPS, with no key on the
server:

```bash
git ls-remote https://github.com/aurekasystems/aureka.at.git HEAD
sudo install -d -o root -g root -m 755 /srv/sites
sudo install -d -o mjs -g mjs /srv/sites/aureka.at
git clone https://github.com/aurekasystems/aureka.at.git /srv/sites/aureka.at
cd /srv/sites/aureka.at
```

## 3. Check and start the website stack

```bash
cd /srv/sites/aureka.at
sudo docker network inspect edge --format '{{.Name}}'
sudo docker compose -f compose.yaml -f compose.override.yaml config --quiet
sudo docker compose -f compose.yaml -f compose.override.yaml pull
sudo docker compose -f compose.yaml -f compose.override.yaml run --rm --no-deps website caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo docker compose -f compose.yaml -f compose.override.yaml up -d
sudo docker compose -f compose.yaml -f compose.override.yaml ps
```

## 4. Route in the shared proxy

The main Caddyfile (`/srv/proxy/caddy/app/Caddyfile`) imports
`/config/sites-enabled/*.caddy`. Validate the route in a check copy first;
the running proxy is not touched.

```bash
C=/srv/proxy/caddy/data/config
sudo docker exec aureka-proxy-caddy-caddy-1 wget -q -O /dev/null http://aureka-website:80/
sudo install -d -m 755 $C/aureka-website-check
sudo cp deploy/blossom/aureka-website.caddy $C/aureka-website-check/
{ cat /srv/proxy/caddy/app/Caddyfile; echo 'import /config/aureka-website-check/*.caddy'; } | sudo tee $C/Caddyfile.aureka-website-check >/dev/null
sudo docker exec aureka-proxy-caddy-caddy-1 caddy validate --config /config/Caddyfile.aureka-website-check --adapter caddyfile
```

Activate it, with a backup of `sites-enabled`. Reload only after a successful
validation:

```bash
sudo cp -a $C/sites-enabled $C/backups/sites-enabled-$(date +%Y%m%d-%H%M%S)
sudo cp deploy/blossom/aureka-website.caddy $C/sites-enabled/aureka-website.caddy
sudo docker exec aureka-proxy-caddy-caddy-1 caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo docker exec aureka-proxy-caddy-caddy-1 caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
```

Then check that every other site behind the proxy still answers with its
usual status code (list the hosts from the main Caddyfile and
`sites-enabled/`), and remove the check copy:

```bash
for h in <other hosts>; do echo "$h: $(curl -s -o /dev/null -w '%{http_code}' https://$h/)"; done
sudo rm -r $C/aureka-website-check $C/Caddyfile.aureka-website-check
```

## 5. DNS and verification

Set at Infomaniak (lower the TTL to 300 beforehand); leave MX and mail
records unchanged:

| Name | Type | Value |
| --- | --- | --- |
| `aureka.at` | A | `179.237.76.73` |
| `aureka.at` | AAAA | `2001:1600:16:10::acf` |
| `www.aureka.at` | A | `179.237.76.73` |
| `www.aureka.at` | AAAA | `2001:1600:16:10::acf` |

Blossom's addresses: `ip -br addr show enp3s0`. `dig` is not installed on
Blossom; check resolution with `getent ahosts aureka.at`.

Follow the certificate issuance until `certificate obtained successfully`
appears for both names:

```bash
sudo docker logs -f --since 2m aureka-proxy-caddy-caddy-1 2>&1 | grep -iE 'aureka\.at|obtain|error'
```

If issuance stalls after the DNS change, retrigger it with
`caddy reload … --force`. Then:

```bash
curl -I http://aureka.at/
curl -I https://aureka.at/
curl -I https://www.aureka.at/
curl -I https://aureka.at/impressum
curl -I https://aureka.at/assets/style.css
```

Expected: HTTP → HTTPS (308), `www` → `https://aureka.at/` (301), otherwise
HTTP 200.

Rolling back the move: remove `sites-enabled/aureka-website.caddy`, validate
and reload the proxy, and restore the previous Infomaniak DNS values.

## 6. Releases and the pull timer

Only published GitHub releases go live; merging to `main` does not deploy.

1. Merge the changes to `main`.
2. Publish a release on GitHub with a new tag on `main`, e.g. `v1.4.0`
   (letters, digits, `.`, `_`, `-`). Pre-releases are not deployed.
3. The workflow `Release` (`.github/workflows/release.yml`) commits the tagged
   files to the branch `release`, with the tag filled in where the footer of
   each page has `<!-- version -->`. Each release commit has the previous one
   as a parent, so the branch only ever fast-forwards.
4. Blossom pulls `release`: the timer `site-pull@aureka.at.timer` runs
   `git pull --ff-only` in `/srv/sites/aureka.at` as `mjs` every minute. Since
   the container serves `public/` straight from the checkout, the release is
   live after about a minute. GitHub needs neither access to the server nor
   secrets.

The server checkout follows `release` once (after the first release exists):

```bash
cd /srv/sites/aureka.at
git status --short   # must be empty
git fetch origin && git switch release
git status -sb       # ## release...origin/release
```

The units in `deploy/blossom/systemd/` are templates; the instance is the
directory name below `/srv/sites/`. Further sites (e.g. the blog) use the same
installed units with their own instance. The files are **copied**, not linked,
so that a push can never change what runs on the server.

Install once:

```bash
cd /srv/sites/aureka.at
git status --short   # must be empty
sudo install -m 644 deploy/blossom/systemd/site-pull@.service deploy/blossom/systemd/site-pull@.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemd-analyze verify site-pull@aureka.at.service site-pull@aureka.at.timer
sudo systemctl start site-pull@aureka.at.service
systemctl show site-pull@aureka.at.service -p Result -p ExecMainStatus
sudo systemctl enable --now site-pull@aureka.at.timer
systemctl list-timers 'site-pull@*' --no-pager
```

Expected: `Result=success` and `ExecMainStatus=0`; the timer is listed with
its next run.

Monitor (`mjs` can read the system journal only with `sudo`):

```bash
sudo journalctl -u site-pull@aureka.at.service --since today | grep -E 'deployed|manual step|fatal|error'
```

- `deployed <old>..<new>`: the new revision is live.
- `manual step needed: <file>`: Compose files or `deploy/` changed. A pull
  does not apply these; see below.
- `fatal: Not possible to fast-forward`: the checkout on Blossom has local
  commits or changes. Nothing is overwritten; find the cause
  (`git status`, `git log origin/release..`) and clean up the checkout.

After changing the units in `deploy/blossom/systemd/`, repeat the
installation (`install`, `daemon-reload`).

## Manual steps and rollback

After `manual step needed` for `compose*.yaml` or `deploy/Caddyfile`:

```bash
cd /srv/sites/aureka.at
sudo docker compose -f compose.yaml -f compose.override.yaml up -d --force-recreate website
```

(The website Caddy's admin API is disabled, hence recreate instead of
reload.) For `deploy/blossom/aureka-website.caddy`, repeat section 4.

Prefer rolling back through a release: run the workflow `Release` manually
(Actions → Release → Run workflow) with the tag of the last good release. It
puts that release's files on top of `release`, and the timer picks them up. If it has to be faster on the server, stop the timer first,
otherwise every run fails:

```bash
sudo systemctl stop site-pull@aureka.at.timer
cd /srv/sites/aureka.at && git switch --detach <COMMIT>
# back to normal:
git switch release && git pull --ff-only && sudo systemctl start site-pull@aureka.at.timer
```

## Moving off Blossom

Once `aureka.at` runs elsewhere and DNS points there:

```bash
C=/srv/proxy/caddy/data/config
sudo rm $C/sites-enabled/aureka-website.caddy
sudo docker exec aureka-proxy-caddy-caddy-1 caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo docker exec aureka-proxy-caddy-caddy-1 caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl disable --now site-pull@aureka.at.timer
cd /srv/sites/aureka.at && sudo docker compose -f compose.yaml -f compose.override.yaml down
```

Then remove `/srv/sites/aureka.at`. Keep the `site-pull@` template units
while other sites below `/srv/sites/` use them.

## Former FTP deployment

Until the move on 2026-11-25, a GitHub workflow uploaded `public/` via FTP to
the Infomaniak webspace. The workflow and script have been removed; the
`FTP_*` repository secrets and the old webspace are no longer needed.
