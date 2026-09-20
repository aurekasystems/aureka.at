# Aureka Systems

Kleine deutschsprachige Startseite mit HTML und CSS.
Vorerst kein Framework, Build, JavaScript, externen Fonts oder Laufzeit-Abhängigkeiten.

## Struktur
- public/: ausschließlich veröffentlichte Website-Dateien
- .github/workflows/deploy.yml: Upload bei Push auf main
- scripts/deploy_ftp.py: FTP-Upload mit der Python-Standardbibliothek

## Lokal ansehen
public/index.html im Browser öffnen. Alternativ mit installiertem Python:
`python -m http.server 8000 --directory public`
Dann http://localhost:8000 öffnen.

## Git und GitHub
Git ist bereits auf main initialisiert. Die vorhandene Git-Identität wird verwendet.
Ein Remote muss noch mit der tatsächlichen GitHub-Repository-URL verbunden werden.
Kein Repository-Name oder Eigentümer wird angenommen.

```sh
git remote add origin <GITHUB-REPOSITORY-URL>
git add .
git commit -m "Add minimal Aureka landing page and FTP deployment"
git push -u origin main
```

Vor dem ersten Push die Secrets und das Zielverzeichnis konfigurieren.

## GitHub Actions: normales FTP
Unter **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Inhalt |
| --- | --- |
| FTP_HOST | FTP-Hostname aus Infomaniak, ohne Protokoll, Port oder Pfad |
| FTP_USERNAME | FTP-Benutzername |
| FTP_PASSWORD | FTP-Passwort |
| FTP_REMOTE_DIR | Existierendes Webroot aus Sicht des FTP-Benutzers |

Den tatsächlichen Webroot-Pfad in Infomaniak bzw. mit einem FTP-Client prüfen.
Keinen Beispielpfad ungeprüft übernehmen. / oder . nur verwenden, wenn das
FTP-Start-/Rootverzeichnis tatsächlich das dedizierte Webroot dieser Website ist.
Absolute Pfade beginnen mit /, relative Pfade gelten ab dem FTP-Loginverzeichnis.
Das konfigurierte Zielverzeichnis muss bereits existieren.

Der Workflow verwendet ausdrücklich **normales, unverschlüsseltes FTP auf Port
21 im passiven Modus**, kein FTPS und kein SFTP. Zugangsdaten werden ausschließlich
über GitHub Secrets als Umgebungsvariablen übergeben; keine lokalen Secret-Dateien
sind erforderlich.

Bei jedem Push auf main wird der **Inhalt** von public/ hochgeladen, ohne einen
zusätzlichen public-Ordner auf dem Server. Der Workflow kann auf main auch
manuell unter **Actions → Deploy via FTP → Run workflow** gestartet werden.
Gleichzeitige Uploads werden serialisiert.

### Verhalten und Grenzen
- Gleichnamige Dateien werden überschrieben, fehlende Unterordner angelegt.
- Keine entfernten Dateien oder Verzeichnisse werden gelöscht.
- Lokal entfernte oder umbenannte Dateien bleiben auf dem Server stehen und
  können nach Prüfung manuell entfernt werden.
- Assets werden vor index.html übertragen; FTP-Uploads sind nicht atomar.
  Nach einem Teilfehler den Workflow erneut starten.
- Bei fehlenden Secrets oder nicht vorhandenem Zielverzeichnis bricht der Upload ab.
- Nur öffentliche Inhalte in public/ ablegen. Git, README und Workflow werden
  nicht veröffentlicht.
- Die Verbindung zum echten Webspace ist erst nach Einrichtung der Secrets
  überprüfbar. Nach dem ersten erfolgreichen Lauf die Website im Browser prüfen.

Die AS-Buchstaben sind ein vorläufiges Textzeichen. Produktangebot, finale
Markengestaltung und rechtliche Seiten sind noch nicht Bestandteil dieses Starts.

Technische Referenz: https://docs.python.org/3/library/ftplib.html