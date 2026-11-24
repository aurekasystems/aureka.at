# Bereitstellung auf Blossom

Die Website läuft auf Blossom als eigenes Compose-Projekt unter `/srv/sites/`
(eigene Seiten; Kundenseiten liegen unter `/srv/clients/`), nach demselben Muster
wie die anderen Seiten hinter dem gemeinsamen Proxy. Ein schlanker Caddy-Container liefert
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
- `deploy/blossom/systemd/site-pull@.service`, `site-pull@.timer`: holen `main`
  jede Minute auf Blossom (Abschnitt 6).

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
andere Hosts: wie gewohnt):

```bash
for h in <other hosts>; do echo "$h: $(curl -s -o /dev/null -w '%{http_code}' https://$h/)"; done
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

## 6. Automatisches Aktualisieren (Pull-Timer)

Blossom holt `main` selbst: Der Timer `site-pull@aureka.at.timer` führt jede
Minute als `mjs` ein `git pull --ff-only` in `/srv/sites/aureka.at` aus. Da der
Container `public/` direkt aus dem Checkout liest, ist ein Push auf `main`
spätestens nach etwa einer Minute online. GitHub braucht dafür weder Zugang
zum Server noch Secrets.

Die Units in `deploy/blossom/systemd/` sind Templates; die Instanz ist der
Ordnername unter `/srv/sites/`. Weitere Seiten (z. B. der Blog) nutzen dieselben
installierten Units mit eigener Instanz. Die Dateien werden **kopiert**, nicht
verlinkt, damit ein Push nie ändert, was auf dem Server ausgeführt wird.

Einmalig installieren:

```bash
cd /srv/sites/aureka.at
git status --short   # muss leer sein
sudo install -m 644 deploy/blossom/systemd/site-pull@.service deploy/blossom/systemd/site-pull@.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemd-analyze verify site-pull@aureka.at.service site-pull@aureka.at.timer
sudo systemctl start site-pull@aureka.at.service
systemctl status site-pull@aureka.at.service --no-pager
sudo systemctl enable --now site-pull@aureka.at.timer
systemctl list-timers 'site-pull@*' --no-pager
```

Erwartet: Der Service endet mit `status=0/SUCCESS`, der Timer erscheint mit
dem nächsten Lauf in `list-timers`.

Beobachten:

```bash
sudo journalctl -u site-pull@aureka.at.service --since today | grep -E 'deployed|manual step|fatal|error'
```

- `deployed <alt>..<neu>`: neuer Stand ist online.
- `manual step needed: <Datei>`: Compose-Dateien oder `deploy/` haben sich
  geändert. Ein Pull wendet das nicht an; siehe unten.
- `fatal: Not possible to fast-forward`: Im Checkout auf Blossom gibt es lokale
  Commits oder Änderungen. Nichts wird überschrieben; Ursache klären
  (`git status`, `git log origin/main..`) und den Checkout bereinigen.

Nach Änderungen an den Units in `deploy/blossom/systemd/` die Installation
wiederholen (`install`, `daemon-reload`).

## Manuelle Schritte und Rollback

Nach `manual step needed` für `compose*.yaml` oder `deploy/Caddyfile`:

```bash
cd /srv/sites/aureka.at
sudo docker compose -f compose.yaml -f compose.override.yaml up -d --force-recreate website
```

(Die Admin-API des Website-Caddy ist deaktiviert, daher Neuerstellen statt
Reload.) Für `deploy/blossom/aureka-website.caddy` Abschnitt 4 wiederholen.

Rollback bevorzugt über Git: auf `main` mit `git revert` zurücknehmen und
pushen; der Timer übernimmt den Stand. Muss es auf dem Server schneller gehen,
zuerst den Timer anhalten, sonst schlägt jeder Lauf fehl:

```bash
sudo systemctl stop site-pull@aureka.at.timer
cd /srv/sites/aureka.at && git switch --detach <COMMIT>
# zurück:
git switch main && git pull --ff-only && sudo systemctl start site-pull@aureka.at.timer
```

## Früheres FTP-Deployment

Bis zum Umzug am 25.11.2026 lud ein GitHub-Workflow `public/` per FTP auf den
Infomaniak-Webspace. Workflow und Skript sind entfernt; die Secrets `FTP_*` im
Repository und der alte Webspace werden nicht mehr gebraucht.
