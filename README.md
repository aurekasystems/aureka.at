# Aureka Systems

Small German-language landing page built with plain HTML and CSS.
For now: no framework, build step, JavaScript, external fonts or runtime
dependencies.

## Structure
- `public/`: published website files only
- `compose.yaml`, `compose.override.yaml`, `deploy/`: operation on Blossom
  (see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md))

## Local preview
Open `public/index.html` in a browser, or with Python installed:
`python -m http.server 8000 --directory public`
and open http://localhost:8000.

## Operation
The website runs on Blossom (`/srv/sites/aureka.at`) behind the shared Caddy
proxy. Setup, updates and rollback are described in
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). A push to `main` is live after about
a minute: a systemd timer on Blossom pulls it.

## Notes
- The site content is German. An English version (EN/DE) is planned.
- The "AS" letters are a provisional text mark.
- The legal notice lives in `public/impressum.html`; its email address is
  encoded as HTML entities.
- A privacy policy is still missing.

## Development
This repository was built with the help of AI assistants. All changes are reviewed and
committed by a human, who remains responsible for them. Commits carry no
per-commit AI attribution.
