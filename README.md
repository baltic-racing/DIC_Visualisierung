# DIC_Visualisierung

Lokales Entwicklungswerkzeug für das aktuelle Formula-Student-DIC. Es erweitert die bestehende DIC-Live-Vorschau: dieselbe Browseroberfläche, dieselbe 20×4-Anzeige und dieselbe Host-Simulation. Es wird kein Cloud-Dienst und kein zentrales Team-System verwendet.

Die originale C-Displaylogik und CAN-Auswertung werden aus einem **separaten, lokal vorhandenen Firmware-Repository** gelesen und für den Computer kompiliert. Es gibt keine zweite HTML-Implementierung der Firmware-Layouts. Alle Entwickler verwenden ihre eigenen lokalen Einstellungen und Arbeitsdateien.

## Voraussetzungen

- Python **3.10 oder neuer**, vorzugsweise vom [offiziellen Python-Anbieter](https://www.python.org/downloads/).
- Ein moderner Browser, z. B. Safari, Firefox, Chrome oder Edge.
- Das originale Firmware-Repository mit dem Unterordner `DIC_23`.
- Ein C-Host-Compiler, siehe die plattformspezifischen Schritte unten.
- Git für die Auswahl gespeicherter Git-Stände. Die Simulation gespeicherter Arbeitsdateien funktioniert auch ohne verfügbares Git-Kommando.

Es sind keine zusätzlichen Python-Pakete und kein `pip install` nötig. Internet wird nur zum einmaligen Installieren der Voraussetzungen benötigt.

## macOS: Installation und Start

1. Python von [python.org](https://www.python.org/downloads/macos/) installieren. Der Ordnerdialog verwendet unter macOS den nativen Systemdialog über das vorinstallierte `osascript`; Tk wird dort nicht gestartet.
2. Falls noch kein Compiler installiert ist: einmal im Terminal `xcode-select --install` ausführen und die Apple Command Line Tools installieren. Danach verwendet das Werkzeug `clang`.
3. Den Projektordner an einen beliebigen Ort legen, außerhalb des Firmware-Repositories.
4. **`Start_macOS.command` doppelklicken.** Die Browseroberfläche öffnet sich automatisch.

Bei einem ZIP-Download kann das Ausführungsrecht verloren gehen. In diesem Fall einmal im Projektordner `chmod +x Start_macOS.command` ausführen. Bei einem Git-Klon bleibt das gesetzte Ausführungsrecht erhalten. Startet eine macOS-Sicherheitsprüfung die Datei nicht, deren Herkunft prüfen und die üblichen macOS-Freigabemöglichkeiten verwenden; Schutzmechanismen müssen nicht abgeschaltet werden.

Alternativ im Terminal: `python3 start.py`.

## Windows: Installation und Start

1. Reguläres Python von [python.org](https://www.python.org/downloads/windows/) installieren, einschließlich `tkinter` und Python-Launcher. Bei einem klassischen Installer die Option zur Aufnahme von Python in `PATH` aktivieren.
2. [MSYS2](https://www.msys2.org/) für x64 installieren; der Standardpfad `C:\msys64` wird automatisch erkannt.
3. **MSYS2 UCRT64** aus dem Startmenü öffnen und einmal aktualisieren:

   ```sh
   pacman -Syu
   ```

   Falls das Fenster dabei geschlossen werden muss, UCRT64 erneut öffnen und die Aktualisierung wiederholen.
4. In UCRT64 den Compiler installieren:

   ```sh
   pacman -S --needed mingw-w64-ucrt-x86_64-gcc
   ```

5. **`Start_Windows.bat` doppelklicken.** Die Anwendung findet den Compiler automatisch unter `C:\msys64\ucrt64\bin\gcc.exe`. Eine systemweite PATH-Änderung für MSYS2 ist bei diesem Standardpfad nicht notwendig.

Die Compilerempfehlung folgt den [MSYS2-/MinGW-w64-Installationshinweisen](https://www.mingw-w64.org/getting-started/msys2/). Bei einer anderen MSYS2-Installation kann `MSYS2_ROOT` auf deren Hauptordner zeigen. Alternativ kann `DIC_CC` den vollständigen Pfad zu `gcc.exe` beziehungsweise einem kompatiblen `clang` enthalten, **ohne zusätzliche Argumente**. Die jeweilige Compiler-Bin-Verzeichnis wird auch für die benötigten Windows-DLLs an die Kindprozesse weitergegeben.

Ein einzelnes LLVM-`clang.exe` ohne Windows-CRT/Linker reicht nicht zwangsläufig. Deshalb ist MSYS2 UCRT64 GCC der empfohlene Windows-Weg. MSVC/`cl.exe` wird nicht unterstützt.

**Windows ist vorbereitet, aber noch nicht auf einem Windows-Rechner getestet.** Insbesondere müssen Compilerlauf, nativer Ordnerdialog und Doppelklick-Start dort vor einer Teamfreigabe geprüft werden. macOS wurde mit tatsächlicher Firmware und clang getestet. Es gibt keine gepackte `.exe` oder `.app` in Version 1.0.

## Erster Start und tägliche Arbeit

1. In der Browserseite **Firmware-Ordner auswählen / ändern** öffnen.
2. **Ordner auswählen …** drücken und den lokalen Firmware-Klon auswählen. Alternativ den vollständigen Pfad eingeben und **Pfad übernehmen** drücken. Auch die Auswahl des Unterordners `DIC_23` wird akzeptiert.
3. Fehlende Dateien werden verständlich gemeldet; ein ungültiger Ordner ersetzt die bisherige Auswahl nicht.
4. Die Codequelle **Automatisch: aktueller Branch** verwenden.
5. C-Dateien im originalen Repository in VS Code bearbeiten und speichern. Die Seite prüft etwa jede Sekunde auf Änderungen und kompiliert bei geänderten Quellen neu. Eine Seite muss nicht neu geladen werden.
6. Unter **Beispielwerte ändern** die simulierten Fahrzeugzustände einstellen.

Der aktuell ausgecheckte Branch und uncommittete **gespeicherte** Änderungen werden übernommen. Noch ungespeicherte Editorinhalte sind nicht zugänglich. Der geöffnete Editor-Tab bestimmt die Codequelle nicht. Neue Seiten werden aus `page_order` ermittelt.

**Anderer lokaler Git-Stand** erlaubt die Auswahl vorhandener lokaler und Remote-Tracking-Branches, ohne einen Checkout auszuführen oder Arbeitsdateien zu ändern. **TY26_Test aus lokalem Git-Stand** bleibt als bisherige Direktwahl erhalten. Diese Modi zeigen committed Dateien aus dem ausgewählten Stand; uncommittete Bearbeitungen gehören nur zum Arbeitsordnermodus. Es gibt keinen automatischen Fetch, Pull, Commit oder Push.

Die Seite öffnet sich standardmäßig unter `http://127.0.0.1:8766/`. Ist der Port bereits belegt, wird automatisch ein anderer freier lokaler Port gewählt und im Startfenster ausgegeben. Der Browser wird mit genau diesem Port geöffnet. Das Startfenster muss offen bleiben; **Strg+C** beendet den Server. Nach einem Neustart die neu geöffnete Seite verwenden, da sich der Sitzungsschlüssel ändert.

## Was erhalten bleibt

Die Desktop-Oberfläche ordnet die große Displayvorschau links und die unabhängig scrollbaren Einstellungen rechts an. Unter dem Display bleibt die Seitenauswahl immer erreichbar. Rechts gibt es drei Tabs: **Beispielwerte**, **Quelle** und **Hilfe**. Die Beispielwerte sind in Fahrzeugdaten, Batterie/Spannungen, Fehlerzustände, CAN, Fusebox/SDC und Bedienelemente gegliedert. Eingaben gehen beim Tabwechsel nicht verloren; Werte, Tab und aufgeklappte Bereiche werden lokal im Browser gespeichert.

Der Kopfbereich unterscheidet ein erkanntes Firmware-Verzeichnis von einer erfolgreichen Simulation. Bei einem Compilerfehler verschwindet die alte Vorschau; der Link zu den Fehlerdetails öffnet den Tab Quelle. Die Build-Zeit stammt aus dem Server, die Zeit der letzten erfolgreichen Simulation aus der Browser-Anfrage. Der Git-Dateistatus wird nur lesend und ohne optionale Index-Sperren abgefragt. Auf kleineren Fenstern stehen Vorschau und Einstellungen untereinander.

- Bisheriges Displaydesign mit 20×4 Zeichen und benutzerdefinierten Zeichensätzen.
- Alle bestehenden Displayseiten sowie Live-Übernahme ihrer Texte, Positionen und Berechnungen aus C.
- RGB-LEDs links/rechts, obere Leiste, untere AMS-Leiste und separate IMD-LED.
- Alle bisherigen Beispielwerte: Drücke, Pedalsignale, Lenkwinkel, GPS, Spannungen, Temperaturen, Fusebox/SDC, Taster und Fahrmodus.
- AMS-/IMD-Fehlerbits, Diagnosecodes, stehender AMS-Zähler und simulierte Empfangsausfälle.
- CAN-Rohbyte-Überschreibungen und Anzeige des ausgehenden DIC-Telegramms.
- Fehleranzeigen bei ungültigen Eingaben, fehlenden Dateien und Compiler-/Laufzeitfehlern. Ein fehlgeschlagener Build zeigt keinen alten Bildschirm als aktuellen Stand.

Bei **AMS-E** bestimmt der Diagnosecode den Text. Auf Wunsch wird die AMS-Leiste in der Vorschau zusätzlich immer rot dargestellt, wenn die ausgeführte Firmware keinen gültigen Diagnosezustand OK meldet: Fehlercodes, unbekannte Kürzel sowie ungültige/veraltete Diagnosen. Diese reine Vorschau-Kopplung liest den tatsächlichen Diagnosezustand nach Ausführung des C-Codes; sie funktioniert daher auch bei im C-Code erzwungenen Diagnosecodes und auf anderen Displayseiten. Das ursprüngliche AMS-Fehlerbit kann die Leiste weiterhin unabhängig einschalten. Ohne Diagnosevariablen (z. B. im Car-Stand) gilt nur die vorhandene Firmware-Ansteuerung. Die Firmware-Dateien und GPIO-Ergebnisse werden dadurch nicht geändert. Die Firmware-Zuordnung 0–9 wird weiterverwendet. Die Rohbyte-Überschreibungen haben Vorrang vor den normalen Eingaben; Empfangsausfälle bleiben wirksam.

Jede Anfrage simuliert einen frischen Durchlauf. Fehler-Latches gelten nur innerhalb dieses Durchlaufs. Die Zeit beginnt wie bisher bei 20 s, damit Startverzögerungen übersprungen werden, und läuft für die gewählte Dauer weiter. Die Startseite ist auswählbar; es gibt keine zeitgetreue Startanimation. Die Vorschau ist kein fortlaufender Echtzeit-CAN-Emulator.

## Lokale Dateien und Datenschutz

Die Pfadauswahl wird außerhalb des Projekts gespeichert:

| System | Einstellungsdatei |
|---|---|
| macOS | `~/Library/Application Support/DIC_Visualisierung/settings.json` |
| Windows | `%LOCALAPPDATA%\DIC_Visualisierung\settings.json` |
| Linux, nicht als Zielplattform getestet | `$XDG_CONFIG_HOME/DIC_Visualisierung/settings.json` oder `~/.config/DIC_Visualisierung/settings.json` |

Nur diese lokale Datei enthält den persönlichen Firmware-Pfad. Sie gehört nicht ins Git-Repository. Änderungen sind jederzeit über die Oberfläche möglich. Eingabewerte und gewählte Ansichten werden wie bisher im lokalen Browserspeicher gespeichert.

Generierte Host-C-Dateien und Binärdateien liegen in einem eigenen temporären Verzeichnis des laufenden Prozesses, **außerhalb der Firmware und dieses Projekts**. Bei normalem Beenden wird es entfernt. Nach einem Prozessabsturz können temporäre Reste verbleiben, die das Betriebssystem beziehungsweise der Nutzer später bereinigen kann. Die Firmware-Quellen werden ausschließlich gelesen.

Für Tests oder alternative Konfigurationen unterstützt der Start `--config-dir ORDNER` oder die Umgebungsvariable `DIC_VIS_CONFIG_DIR`. Dieser Ordner darf nicht innerhalb der Firmware liegen. Weitere Optionen: `--port NUMMER` und `--no-browser`.

## Architektur und Grenzen

```text
Externes Firmware-Repository (nur lesen)
   -> Quellen lesen + Änderung anhand Inhalt erkennen
   -> externe Host-Kopie und Hardwareadapter erzeugen
   -> clang / GCC auf dem lokalen Computer
   -> originalen C-Code mit simuliertem CAN / GPIO / SPI ausführen
   -> 4×20 Zeichen, Sonderzeichen, LEDs und CAN-Ausgabe
   -> bestehende lokale Browseroberfläche
```

`main.c`, `candata.c`, `display.c`, `portextender.c`, `port_definitions.c` und die zugehörigen bekannten Header bleiben die Quelle der Logik. Die Hardwareadapter ersetzen nur die nötigen AVR-Zugriffe. Die bisherigen Anpassungen bleiben erhalten: `main` und die mit macOS kollidierende Variable `wait` werden in der erzeugten Host-Kopie umbenannt; der Seitenzeigertyp wird auf `uintptr_t` angepasst; `sys_time_old` wird deterministisch initialisiert. Die verschachtelte GCC-Lüfterfunktion aus `_Car` wird für clang auf Dateiebene verschoben. Die originalen Dateien werden dafür nicht bearbeitet.

Layoutänderungen und neue Funktionen in den bereits einbezogenen C-Dateien werden mitkompiliert. Neue Quelldateien, neue Bibliotheken oder zusätzliche Hardwarezugriffe können eine Anpassung des kleinen Adapters erfordern. Ziel ist das aktuelle Fahrzeug, keine beliebige Firmware.

Host-Integerbreite, MCU-Timing, echte CAN-Treiber und elektrische Eigenschaften entsprechen nicht vollständig dem AT90CAN128. LED-Anordnung und Warnfarben sind schematisch; RGB-Kanäle und Schaltzustände folgen dem Code. Die widersprüchlichen Polaritätskommentare der AMS-Leiste werden nach der Funktionsabsicht `bms_error(1)` = Warnung an dargestellt. Physikalische Einheiten und die Bremsbalance-Faktoren müssen vom Fahrzeugteam bestätigt werden.

**Die Simulation ersetzt keine Hardwaretests.**

## Angemessene lokale Absicherung

- Bindung ausschließlich an `127.0.0.1`, keine LAN-Freigabe.
- Keine Cloud-Verbindung, Telemetrie, externen Skripte oder automatischen Updates/Downloads.
- Lokale API verlangt einen zufälligen Sitzungsschlüssel; der Browser erhält ihn mit der Seite.
- Host-, Origin- und Fetch-Site-Prüfung; keine CORS-Freigabe. Einbettung durch fremde Webseiten ist untersagt.
- Konfigurationsänderungen nur als authentifizierte JSON-POST-Anfragen.
- Compiler und Git erhalten Argumentlisten, keine zusammengesetzten Shell-Kommandos. Git-Stände werden gegen die lokal vorhandenen Referenzen geprüft.
- Zeitlimits: Git-Lesezugriffe 8 s, Kompilierung 20 s, Simulation 3 s, Ordnerdialog 120 s.

Das ist keine Sandbox gegen bösartigen C-Code und kein Zugriffsschutz vor anderen Prozessen desselben Betriebssystembenutzers. Nur vertraute Team-Firmware auswählen und prüfen. Die Live-Ausführung von heruntergeladenen, unbekannten Repositories wird nicht empfohlen.

## Tests

Ohne Firmware-Daten im Projekt:

```sh
python3 -m unittest discover -s tests -v
```

Unter Windows `py -3` statt `python3` verwenden. Diese Tests prüfen Konfiguration, Pfadvalidierung, Plattformpfade, Compilerwahl und lokale HTTP-Zugriffskontrolle. Der Ordnerdialog wird dabei simuliert und nicht geöffnet.

Die übernommenen Simulationstests verwenden einen externen, vertrauten Firmware-Klon:

```sh
python3 tests/integration.py "/Pfad/zur/DIC_Firmware"
```

Sie prüfen unter anderem Displayseiten, CAN-Auswertung, AMS/IMD, GPS-/Diagnoseausfall, Rohbytes, Compilerfehler und Wiederherstellung sowie die automatische Aktualisierung nach einer gespeicherten Änderung. Veränderungstests laufen auf temporären Kopien außerhalb des originalen Klons. Die bekannten lokalen Referenzen `origin/TY26_Test` und `origin/TY26_Car` müssen für diesen Regressionstest vorhanden sein. Die Tests sind auf den bekannten Fahrzeugstand ausgerichtet; absichtliche Protokoll-/Layoutänderungen können entsprechende Testanpassungen verlangen.

## Projektstruktur

```text
DIC_Visualisierung/
  server.py                 # bestehende Simulation + lokale HTTP-Schnittstelle
  settings.py               # lokale Pfadauswahl, Validierung und Speicherung
  choose_folder.py          # macOS-Systemdialog / Windows-Tk, eigener Prozess
  start.py                  # gemeinsamer Starter
  Start_macOS.command       # Doppelklick unter macOS
  Start_Windows.bat         # Doppelklick unter Windows
  web/index.html            # bestehende Oberfläche + Ordnerauswahl
  tests/test_local.py        # Konfiguration und HTTP-Absicherung
  tests/integration.py       # übernommene Simulationstests gegen externe Firmware
  .gitignore
  VERSION
  README.md
```

## GitHub vorbereiten

Der Ordner ist für ein **separates privates** Repository `DIC_Visualisierung` vorbereitet. Es wurden kein GitHub-Repository und kein Push automatisch ausgeführt. Der originale Firmware-Klon gehört nicht in dieses Repository. Auch lokale Einstellungen, temporäre Host-Kopien und Build-Artefakte gehören nicht hinein; die `.gitignore` schützt vor den üblichen versehentlichen Ergänzungen.

Nach Freigabe: diesen Projektordner als eigenständiges Repository initialisieren, die vorgemerkten Dateien prüfen, ein **privates** GitHub-Repository anlegen und erst dann den ersten Push durchführen. Vor einer späteren öffentlichen Veröffentlichung müssen Teamfreigabe, Rechte und eine passende Lizenz geklärt werden; es ist derzeit keine Lizenzfreigabe vorweggenommen.
