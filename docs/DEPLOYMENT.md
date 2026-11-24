# Bereitstellung auf Blossom

Die Website läuft auf Blossom als eigenes Compose-Projekt unter `/srv/sites/`
(eigene Seiten; Kundenseiten liegen unter `/srv/clients/`), nach demselben Muster
wie `client-holzerweiss-website`. Ein schlanker Caddy-Container liefert
ausschließlich `public/` über internes HTTP aus. Der gemeinsame Proxy
(`aureka-proxy-caddy`) übernimmt HTTPS und leitet über das Docker-Netzwerk
`edge` weiter.

> Blossom ist laut `aurekasystems/infrastructure` eine Preview-/Staging-Plattform
> ohne Produktivgarantie. `aureka.at` läuft seit dem 25.11.2026 trotzdem dort.

## Stabile Bezeichnungen

| Bestandteil | Wert |
| --- | --- |
| Repository | `aurekasystems/aureka.at` |
| Server-Checkout | `/srv/sites/aureka.at/` |
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

Das Repository ist öffentlich; Blossom klont es über HTTPS, ohne Schlüssel auf
dem Server:

```bash
git ls-remote https://github.com/aurekasystems/aureka.at.git HEAD
sudo install -d -o root -g root -m 755 /srv/sites
sudo install -d -o mjs -g mjs /srv/sites/aureka.at
git clone https://github.com/aurekasystems/aureka.at.git /srv/sites/aureka.at
cd /srv/sites/aureka.at
```

## 3. Website-Stack prüfen und starten

```bash
cd /srv/sites/aureka.at
sudo docker network inspect edge --format '{{.Name}}'
sudo docker compose -f compose.yaml -f compose.override.yaml config --quiet
sudo docker compose -f compose.yaml -f compose.override.yaml pull
sudo docker compose -f compose.yaml -f compose.override.yaml run --rm --no-deps website caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo docker compose -f compose.yaml -f compose.override.yaml up -d
sudo docker compose -f compose.yaml -f compose.override.yaml ps
```

## 4. Route im gemeinsamen Proxy

Die Haupt-Caddyfile (`/srv/proxy/caddy/app/Caddyfile`) importiert
`/config/sites-enabled/*.caddy`. Die Route zuerst in einer Prüfkopie
validieren; der laufende Proxy bleibt dabei unberührt.

```bash
C=/srv/proxy/caddy/data/config
sudo docker exec aureka-proxy-caddy-caddy-1 wget -q -O /dev/null http://aureka-website:80/
sudo install -d -m 755 $C/aureka-website-check
sudo cp deploy/blossom/aureka-website.caddy $C/aureka-website-check/
{ cat /srv/proxy/caddy/app/Caddyfile; echo 'import /config/aureka-website-check/*.caddy'; } | sudo tee $C/Caddyfile.aureka-website-check >/dev/null
sudo docker exec aureka-proxy-caddy-caddy-1 caddy validate --config /config/Caddyfile.aureka-website-check --adapter caddyfile
```

Aktivieren, mit Sicherung von `sites-enabled`. Erst nach erfolgreicher
Validierung neu laden:

```bash
sudo cp -a $C/sites-enabled $C/backups/sites-enabled-$(date +%Y%m%d-%H%M%S)
sudo cp deploy/blossom/aureka-website.caddy $C/sites-enabled/aureka-website.caddy
sudo docker exec aureka-proxy-caddy-caddy-1 caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo docker exec aureka-proxy-caddy-caddy-1 caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
```

Danach prüfen, dass die übrigen Seiten weiter antworten (Photos: 200,
`ahw.preview`: 401):

```bash
for h in alpha.test.aureka.photos beta.test.aureka.photos ahw.preview.aureka.systems; do echo "$h: $(curl -s -o /dev/null -w '%{http_code}' https://$h/)"; done
```

## 5. DNS und Prüfung

Bei Infomaniak (TTL vorher auf 300 senken) setzen; MX und Mail-Einträge
unverändert lassen:

| Name | Typ | Wert |
| --- | --- | --- |
| `aureka.at` | A | `179.237.76.73` |
| `aureka.at` | AAAA | `2001:1600:16:10::acf` |
| `www.aureka.at` | A | `179.237.76.73` |
| `www.aureka.at` | AAAA | `2001:1600:16:10::acf` |

Adressen von Blossom: `ip -br addr show enp3s0`. Auf Blossom ist `dig` nicht
installiert; Auflösung mit `getent ahosts aureka.at` prüfen.

Zertifikate verfolgen, bis für beide Namen `certificate obtained successfully`
erscheint:

```bash
sudo docker logs -f --since 2m aureka-proxy-caddy-caddy-1 2>&1 | grep -iE 'aureka\.at|obtain|error'
```

Hängt die Ausstellung nach dem DNS-Wechsel, mit `caddy reload … --force`
neu anstoßen. Danach:

```bash
curl -I http://aureka.at/
curl -I https://aureka.at/
curl -I https://www.aureka.at/
curl -I https://aureka.at/impressum
curl -I https://aureka.at/assets/style.css
```

Erwartet: HTTP → HTTPS (308), `www` → `https://aureka.at/` (301), sonst HTTP 200.

Rollback des Umzugs: `sites-enabled/aureka-website.caddy` entfernen, Proxy
validieren und neu laden, DNS auf die alten Infomaniak-Werte zurücksetzen.

## Aktualisieren und zurückrollen

```bash
cd /srv/sites/aureka.at
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

Seit dem DNS-Umzug ist das FTP-Deployment überflüssig. Der Workflow
`.github/workflows/deploy.yml` lädt aber weiterhin bei jedem Push auf `main`
auf den alten Webspace hoch, bis er zusammen mit `scripts/deploy_ftp.py`
entfernt wird.
