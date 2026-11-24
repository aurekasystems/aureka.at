# Bereitstellung auf Blossom

Die Website läuft auf Blossom als eigenes Compose-Projekt, nach demselben Muster
wie `client-holzerweiss-website`. Ein schlanker Caddy-Container liefert
ausschließlich `public/` über internes HTTP aus. Der gemeinsame Proxy
(`aureka-proxy-caddy`) übernimmt HTTPS und leitet über das Docker-Netzwerk
`edge` weiter.

> Blossom ist laut `aurekasystems/infrastructure` eine Preview-/Staging-Plattform
> ohne Produktivgarantie. Vor dem DNS-Umzug von `aureka.at` bewusst entscheiden,
> ob das für die Unternehmensseite ausreicht.

## Stabile Bezeichnungen

| Bestandteil | Wert |
| --- | --- |
| Repository | `aurekasystems/aureka.at` |
| Server-Checkout | `/srv/aureka/website/` |
| Compose-Projekt | `aureka-website` |
| Service | `website` |
| Alias im Netzwerk `edge` | `aureka-website` |
| Domains | `aureka.at` (Hauptdomain), `www.aureka.at` → Weiterleitung |

## Dateien

- `compose.yaml`: Website-Stack mit `caddy:2.11.4-alpine`, schreibgeschützten
  Mounts für `public/` und `deploy/Caddyfile`, Healthcheck. Kein Host-Port.
- `compose.override.yaml`: Blossom-Ergänzung, externes Netzwerk `edge` und Alias.
- `deploy/Caddyfile`: interner Dateiserver auf Port 80 mit Sicherheits-Headern;
  `/impressum` liefert auch `impressum.html`.
- `deploy/blossom/aureka-website.caddy`: Route für den gemeinsamen Proxy. Die
  installierte Proxy-Konfiguration gehört nachvollziehbar in
  `aurekasystems/infrastructure`.

Basis- und Override-Datei werden bei allen Befehlen gemeinsam angegeben.

## 1. Vor dem ersten Deployment

- Alle Platzhalter `[…]` in `public/impressum.html` ersetzen. Prüfen:
  `grep -n '\[' public/impressum.html` darf nichts mehr liefern.
- Änderungen committen und nach `main` pushen.

## 2. Checkout auf Blossom (als `mjs`)

Für das private Repository einen lesenden Deploy-Key bei GitHub hinterlegen und
den Zugriff prüfen:

```bash
git ls-remote git@github.com:aurekasystems/aureka.at.git HEAD
sudo install -d -o mjs -g mjs /srv/aureka
git clone git@github.com:aurekasystems/aureka.at.git /srv/aureka/website
cd /srv/aureka/website
```

## 3. Website-Stack prüfen und starten

```bash
cd /srv/aureka/website
sudo docker network inspect edge --format '{{.Name}}'
sudo docker compose -f compose.yaml -f compose.override.yaml config --quiet
sudo docker compose -f compose.yaml -f compose.override.yaml pull
sudo docker compose -f compose.yaml -f compose.override.yaml run --rm --no-deps website caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo docker compose -f compose.yaml -f compose.override.yaml up -d
sudo docker compose -f compose.yaml -f compose.override.yaml ps
```

## 4. Route im gemeinsamen Proxy

Die Haupt-Caddyfile importiert bereits `/config/sites-enabled/*.caddy`.

```bash
sudo docker exec aureka-proxy-caddy-caddy-1 wget -q -O /dev/null http://aureka-website:80/
sudo cp deploy/blossom/aureka-website.caddy /srv/proxy/caddy/data/config/sites-enabled/aureka-website.caddy
sudo docker exec aureka-proxy-caddy-caddy-1 caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo docker exec aureka-proxy-caddy-caddy-1 caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
```

Erst nach erfolgreicher Validierung neu laden. Caddy holt die Zertifikate,
sobald DNS auf Blossom zeigt; vorher schlägt die Ausstellung für `aureka.at`
fehl und wird automatisch wiederholt.

## 5. DNS und Prüfung

A-/AAAA-Einträge von `aureka.at` und `www.aureka.at` auf die Adressen von
Blossom setzen (Infomaniak-DNS). Danach:

```bash
curl -I http://aureka.at/
curl -I https://aureka.at/
curl -I https://www.aureka.at/
curl -I https://aureka.at/impressum
curl -I https://aureka.at/assets/style.css
```

Erwartet: HTTP → HTTPS, `www` → `https://aureka.at/` (308), sonst HTTP 200.

## Aktualisieren und zurückrollen

```bash
cd /srv/aureka/website
git status --short
git rev-parse HEAD   # für Rollback notieren
git pull --ff-only
sudo docker compose -f compose.yaml -f compose.override.yaml up -d
```

Änderungen in `public/` sind sofort sichtbar. Nach Änderungen an
`deploy/Caddyfile` den Service neu erstellen (Admin-API ist deaktiviert):

```bash
sudo docker compose -f compose.yaml -f compose.override.yaml up -d --force-recreate website
```

Rollback: `git switch --detach <COMMIT>` und denselben Befehl ausführen;
zurück mit `git switch main && git pull --ff-only`.

## FTP-Deployment (Infomaniak)

Der bestehende Workflow `.github/workflows/deploy.yml` lädt weiterhin bei jedem
Push auf `main` per FTP hoch. Nach dem DNS-Umzug auf Blossom ist er überflüssig
und kann zusammen mit `scripts/deploy_ftp.py` entfernt werden.
