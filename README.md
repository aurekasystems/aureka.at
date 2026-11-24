# Aureka Systems

Kleine deutschsprachige Startseite mit HTML und CSS.
Vorerst kein Framework, Build, JavaScript, externen Fonts oder Laufzeit-Abhängigkeiten.

## Struktur
- public/: ausschließlich veröffentlichte Website-Dateien
- compose.yaml, compose.override.yaml, deploy/: Betrieb auf Blossom
  (siehe [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md))

## Lokal ansehen
public/index.html im Browser öffnen. Alternativ mit installiertem Python:
`python -m http.server 8000 --directory public`
Dann http://localhost:8000 öffnen.

## Betrieb
Die Website läuft auf Blossom (`/srv/sites/aureka.at`) hinter dem gemeinsamen
Caddy-Proxy. Einrichtung, Aktualisierung und Rollback stehen in
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Ein Push auf `main` ist nach etwa
einer Minute online: Ein systemd-Timer auf Blossom holt den Stand selbst.

## Hinweise
Die AS-Buchstaben sind ein vorläufiges Textzeichen. Das Impressum liegt in
public/impressum.html; die E-Mail-Adresse ist dort als HTML-Entities kodiert.
Eine Datenschutzerklärung fehlt noch.
