# DIC-Visualisierung

Lokales Entwicklungswerkzeug für die DIC-Firmware: echte C-Displaylogik, 20×4-LCD, LEDs, CAN-Ereignisse, Profile und reproduzierbare Fahrabläufe. Die Firmware bleibt in ihrem eigenen Repository und wird ausschließlich gelesen.

## Start

- **macOS:** `Einrichtungs- und Startscripts/Start_macOS.command` doppelklicken.
- **Windows:** einmalig `Einrichtungs- und Startscripts/Einrichtung_Windows.bat`, danach `Start_Windows.bat` im selben Ordner. Die Einrichtung fragt vor Downloads/Installationen nach.
- **Terminal, auch Linux:** aus diesem Projektordner `python3 -B start.py` (Windows: `py -3 -B start.py`). Unter Linux Python und clang/GCC zuvor über die übliche Paketverwaltung bereitstellen.

Der Server bindet ausschließlich an `127.0.0.1`. Nach Änderungen an der Anwendung den Server neu starten und die Browserseite neu laden.

## Tägliche Arbeit

1. Unter **Quelle** den eigenen Firmware-Ordner mit `DIC_23` auswählen; der Pfad wird lokal gespeichert.
2. Für VS-Code-Änderungen **Automatisch: aktueller Branch** oder **Dateien im Arbeitsordner** verwenden.
3. Firmware in VS Code bearbeiten und speichern. Änderungen führen sichtbar zu einem neuen Build und pausierten Kaltstart.
4. **Start / Fortsetzen** drücken. **Pause**, **Simulieren bis** und **Reset / Kaltstart** steuern die virtuelle Zeit. **Bis 15 s vorsimulieren** verarbeitet alle Zwischenschritte.
5. Unter **Beispielwerte → Fahrablauf** ein Beispiel laden oder eigene Werte, Profile und CAN-Rohbytes verwenden.


### AMS-TY26 und Akkuübertemperatur

Unter **Beispielwerte → Erweitert → AMS-Sendermodell** steht der neue Sender **AMS TY26** bereit. Er verwendet AMS0/AMS1-Intervalle und Datenbelegung aus der gelesenen AMS-Firmware. „Übertemperatur automatisch auslösen“ aktiviert ein begrenztes Sendermodell; die DIC-Reaktion läuft weiterhin im originalen C-Code. Alte Profile/Abläufe behalten ihren bisherigen Testsender. Details und Grenzen: [Simulationsausbau](docs/Simulationsausbau.md#ams-ty26-sender-und-temperaturablauf-erweiterung).

Zum Ansehen unter **Fahrablauf** „Akku wird heiß · AMS-Übertemperatur“ wählen, **Laden / Kaltstart**, danach **Start / Fortsetzen**. Bei etwa 29,71 s werden die roten AMS-LEDs durch die DIC-Firmware eingeschaltet. Das Beispiel läuft 45 s und prüft auch die Verriegelung nach Abkühlung. Beide Firmware-Repositories bleiben unabhängig und unverändert.


### Vereinfachte Bedienung

- **Beispielwerte:** Unter dem aufklappbaren Bereich **Werte** stehen Fahrzeugwerte, Temperaturen, Spannungen und Fehlerbits bereit. Empfangene Werte und CAN-Nachrichten stehen darüber; Profile ganz unten. Weitere Senderwerte, AMS-Modellwahl, Empfangsausfälle und geplante Taster liegen unter **Erweitert**. Alle Eingaben und Profilwerte bleiben erhalten.
- **Fahrablauf:** Eine Auswahlliste zeigt alle Abläufe in den Gruppen **Tests & Fehler**, **Simulationen** und **Eigene Abläufe**. Zusätzliche Einblendschalter entfallen. Umgruppieren oder Auswählen startet keine Simulation; erst **Laden / Kaltstart** übernimmt einen Ablauf.
- **Profile:** Auswahl, Neu, Speichern und Löschen bleiben direkt erreichbar. **Profiloptionen** enthält Namen, Umbenennen und JSON-Import/-Export. Bei einem neuen Profil öffnet die Anwendung bei Bedarf die Namenseingabe. Vorhandene Profile werden nicht migriert.
- **Diagnose:** CAN-Rohbytes, Firmware-Ausgänge, Ereignislisten und LCD-Pufferansicht sind eingeklappt. Die kompakte CAN-Tabelle bleibt erhalten. Eine aktivierte Pufferansicht wird weiterhin direkt unter dem Display gekennzeichnet.
- **Tests:** Bestandene Ergebnisse bleiben kompakt; Fehler öffnen ihre Soll-/Ist-Details. Alle Prüferwartungen bleiben erhalten. Zeitliche Ablaufprüfungen haben ebenfalls aufklappbare Details.
- **Status:** Verbindung/Build oben, Laufzustand und Uhr unter dem Display. Zusätzliche Zeitsteuerung und Sitzungsdetails sind aufklappbar. Fehler und automatische Quell-Neustarts werden weiterhin ausdrücklich angezeigt.
- **Quelle:** Die vorhandene Quellenauswahl und alle Einstellungen bleiben unverändert.
