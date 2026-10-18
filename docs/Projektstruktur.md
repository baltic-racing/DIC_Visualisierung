# Projektstruktur und Aufräumprüfung

## Ergebnis

Das Projekt bleibt eine lokale Python-/C-/Browseranwendung ohne zusätzliche Pakete, Buildsysteme oder Frameworks. Die Originalfirmware wird weiterhin ausschließlich gelesen. Die Aufräumarbeiten ändern weder Firmwarelogik noch Profileinstellungen oder Szenario-Nutzdaten.

```text
DIC_Visualisierung/
├── start.py                      # Anwendung starten
├── replay.py                     # Replay ohne Browser
├── verify.py                     # Sechs Fahrzeugfälle
├── README.md
├── VERSION
├── Einrichtungs- und Startscripts/
├── dic_visualisierung/           # Python-Implementierung und C-Host-Adapter
│   ├── server.py                 # Lokale HTTP-API, Quellsnapshots, Kompilierung
│   ├── paths.py                  # Projektpfad unabhängig vom Arbeitsverzeichnis
│   ├── fields.py                 # Gemeinsamer Eingabefeld-Katalog
│   ├── firmware.py               # C-Quellen/Seiten analysieren und einbinden
│   ├── host_session.py           # C-Hauptschleife, Timer und Worker-Protokoll
│   ├── host_can.py               # CAN-Register-/MOb- und LCD-Adapter
│   ├── simulation.py             # Zeitachse und interaktive Sitzung
│   ├── worker.py                 # C-Prozesskommunikation, Watchdog, Ereignisse
│   ├── generators.py             # Werte als periodische CAN-Sender codieren
│   ├── scenarios.py              # Szenarioformat, Import, Validierung, Bibliothek
│   ├── profiles.py               # Eingabeprofile und Import/Export
│   ├── settings.py               # Rechnerlokale Einstellungen und Pfadprüfung
│   ├── choose_folder.py          # Separater Prozess für Betriebssystemdialog
│   ├── replay.py                 # Implementierung des Replay-CLI
│   └── verify.py                 # Fahrzeugfälle und feste Erwartungen
├── web/
│   ├── index.html                # Struktur und Sitzungstoken
│   ├── styles.css                # Gestaltung, inklusive schmaler Fenster
│   ├── app.js                    # Felder, Quellen, Status, Displayanbindung
│   ├── lcd.js                    # 5×8-Punktmatrix und tatsächliche CGRAM-Muster
│   ├── session.js                # Uhr und Sitzungssteuerung
│   ├── replay.js                 # Replay, Ereignisse, CAN-Monitor, Beobachtung
│   ├── profiles.js               # Profilbedienung
│   └── tests.js                  # Fahrzeugtests und Ergebnisanzeige
├── examples/
│   ├── scenarios/                # Acht direkt verwendbare synthetische Abläufe
│   ├── logs/                     # Synthetisches candump-Beispiel
│   └── generators/               # Reproduzierbare Erzeugung der Fahrkurven
├── tests/
│   ├── unit/                    # Schnelle Python-Tests
│   ├── regression/              # Firmware-/Sitzungs-/Replay-Prüfungen
│   ├── ui/                      # DOM-Prüfung mit optionalem Node.js
│   └── windows/                 # PowerShell-Starterprüfung
└── docs/
    ├── Simulationsausbau.md       # Aktuelles Modell, Protokolle und Grenzen
    ├── Projektstruktur.md        # Diese Dateibewertung
    ├── Firmware-Zeitkorrektur.patch
    └── archive/Entwicklung-bis-1.2.md
```

## Was redundant oder vermischt war

| Vorher | Bewertung und Änderung |
|---|---|
| Lose Python-Module im Hauptordner | Keine inhaltlichen Duplikate, aber schlecht abgegrenzt. Implementierung in einem eigenen Python-Paket gebündelt; relative Imports verhindern Verwechslungen mit allgemeinen Modulnamen. |
| HTML mit eingebettetem Stylesheet und zentralem JavaScript | Drei verschiedene Aufgaben in einer Datei. CSS und Browserlogik ausgelagert, Darstellung und Funktionen beibehalten. |
| `web/development.js` | Vermischte Profilverwaltung und Fahrzeugtests. Durch `profiles.js` und `tests.js` ersetzt. Keine zweite parallele Implementierung behalten. |
| `simulation.py` mit Prozessprotokoll und Zeitsteuerung | Worker-Transport in `worker.py` abgetrennt. `simulation.py` steuert weiterhin die Sitzung; importierte Worker-Namen bleiben kompatibel. |
| Eingabefeldkatalog mitten in `server.py` | Nach `fields.py` ausgelagert, damit UI und Tests denselben Katalog verwenden. |
| Leere Konstante `STUBS` | Historischer Platzhalter ohne Inhalt; entfernt. Die tatsächlich verwendeten Hardwareadapter bleiben erhalten. |
| `docs/Entwicklung.md` | Beschrieb Version 1.2 und teils längst abgelöste Abläufe. Als historische Referenz archiviert statt gelöscht. |
| Wiederholte Bedienungs-/Abnahmeabschnitte im Simulationsausbau | Aktuelle Bedienung und kompakte CAN-Tabelle zusammengefasst, veraltete 200-ms-Angabe und überholte Tabellenbeschreibung entfernt. Ursprüngliche Etappenabnahme bleibt ausdrücklich historisch. |
| Verweise auf `Einrichtungsscripts/` | Zeigten nicht mehr auf den vom Nutzer umbenannten Ordner. Aktuelle Dokumentation und Windows-Test verwenden `Einrichtungs- und Startscripts/`. |
| Gemischte Test-/Beispielordner | Nach Zweck gruppiert, Pfade und Testsuche angepasst. Keine Tests oder Beispieldaten entfernt. |

## Was bewusst getrennt bleibt

- **Drei Einstiegspunkte:** `start.py`, `replay.py` und `verify.py` starten unterschiedliche Arbeitsabläufe. Die beiden CLI-Dateien sind kleine Weiterleitungen; doppelte Dateinamen im Paket bedeuten keine kopierte Logik. Bestehende Startbefehle bleiben gültig.
- **Fahrzeugtests gegenüber Regressionen:** `verify.py` stellt sechs einfache Fahrzeugfälle auch für die Oberfläche bereit. `tests/regression/` überprüft die Simulatorverträge und umfangreichere Firmwareabläufe. Beides erfüllt unterschiedliche Aufgaben.
- **Szenarien gegenüber Profilen:** Profile speichern Eingabewerte; Szenarien Zeitverläufe und feste Erwartungen; RAM lebt nur in der Sitzung. Zusammenlegen würde diese fachliche Trennung verwischen.
- **JSON-Beispiele und ihre Erzeuger:** JSON-Dateien sind sofort importierbar und teilbar. Die kleinen Erzeuger machen synthetische Kurven reproduzierbar. Tests vergleichen erzeugte und mitgelieferte Daten. Das ist beabsichtigte, geprüfte Ableitung, keine zweite Firmwareimplementierung.
- **C-Host-Adapter gegenüber Python-Worker:** Der Adapter modelliert die Hardwaregrenze im kompilierten C-Prozess; der Worker transportiert Befehle und Schnappschüsse. Eine Zusammenführung würde zwei Laufzeitumgebungen vermischen.
- **Ordnerdialog:** Der separate Prozess verhindert, dass ein problematischer nativer Dialog den laufenden Server mitreißt. Keine Zusammenführung in den Serverprozess.
- **Firmware-Patch:** Bleibt als eigene, nicht auf das Original angewandte Datei erhalten. Die Prüfungen verwenden ausschließlich temporäre Kopien.

## Was vorerst nicht weiter aufgeteilt wird

`server.py` bleibt das größte Python-Modul: HTTP-API, Quellaufnahme und Buildverwaltung teilen vorhandene Zustände und Sperren. Eine weitere Aufteilung würde deren Lebenszyklus ändern und war für diese Aufräumetappe nicht nötig. Auch die bestehenden C-Adapter bleiben als erkennbare Einheiten erhalten. Größere Umbauten sollten erst bei einer konkreten neuen Anforderung erfolgen.

`app.js` und `replay.js` enthalten noch kompakte Funktionen im bisherigen Stil. Die Dateigrenzen sind jetzt klarer; eine flächendeckende Umformatierung oder neue JavaScript-Modularchitektur wurde bewusst nicht mit der Strukturänderung vermischt.

## Lokale und erzeugte Dateien

Einstellungen, Profile und Buildverzeichnisse behalten ihre bisherigen Speicherorte außerhalb der versionierten Quellen. `.gitignore` schließt Cache, persönliche Pfade, Exporte, Aufzeichnungen und Buildartefakte aus; nur die synthetischen Beispiele sind ausgenommen. Keine Firmwarekopie wurde hinzugefügt.

Vor der Umstellung wurde der bisherige Quellstand außerhalb des Projekts gesichert. Bei der Übernahme werden ursprüngliche Dateiinhalte gegen diese Aufnahme geprüft, damit zwischenzeitliche Änderungen nicht überschrieben werden. Vorhandene Nutzerdaten und Git-Metadaten werden nicht gelöscht oder verschoben. Python-Bytecode und Finder-Metadaten sind entbehrliche, ignorierte Laufzeitdateien.

## Prüfung der Änderungen

Auf macOS mit vorhandenem C-Compiler ausgeführt:

- 37 lokale Tests erfolgreich.
- 16 Sitzungsprüfungen erfolgreich.
- 25 Replay-/Firmwareprüfungen erfolgreich.
- 20 Quelländerungsprüfungen erfolgreich.
- Sechs Fahrzeugfälle erfolgreich.
- UI-DOM-Prüfung einschließlich Profile, Tabs, Felder und CAN-Tabelle erfolgreich.
- Isolierter Programmstart außerhalb des Projektordners: alle fünf JavaScript-Dateien und das Stylesheet erreichbar; Szenarien-/Logimport, Replay mit festem 0x500-Vergleich, reine Beobachtung und reguläres Worker-Aufräumen erfolgreich.
- CLI-Hilfe für Replay und Fahrzeugtests außerhalb des Projektordners erreichbar.

Befehle: [tests/README.md](../tests/README.md). Die vollständigen fünf langen Disziplinabläufe und die breite Feldgrenzenintegration wurden bei dieser Strukturänderung nicht erneut ausgeführt. Deren Testdateien bleiben verfügbar. Keine native Windows-/Linux-/AVR-Prüfung; PowerShell ist auf dem verwendeten Mac nicht vorhanden. Die Windows-Import-/Starterpfade wurden angepasst, Betriebssystempfade zusätzlich mit den vorhandenen Mocks geprüft. Keine Hardwareübereinstimmung wird daraus abgeleitet.
