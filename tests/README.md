# Tests

Alle Firmwaretests lesen einen separat vorhandenen Klon. Mutationen, Git-Fixtures, Builds und Einstellungen liegen in temporären Verzeichnissen. Keine Prüfung benötigt `origin/TY26_Test`; einzelne optionale Legacy-Car-Prüfungen sind separat gekennzeichnet.

| Gruppe | Zweck | Voraussetzung |
|---|---|---|
| `unit/` | Formate, Profile, Pfade, Adapterregeln, lokale HTTP-Sicherheit | Python 3.10+ |
| `regression/session_checks.py` | Zustandserhalt, Uhr, Fehler, Quellwechsel, Prozessbereinigung | Python, C-Compiler, Firmware |
| `regression/replay_checks.py` | MObs, CAN-Ankünfte, LCD, Verriegelungen und zeitliche Erwartungen | wie oben |
| `regression/firmware_changes.py` | Zusätzliche/entfernte Seiten und C-Dateien, Git-Quellen und Compilerfehler | zusätzlich Git |
| `regression/integration.py` | Breite Prüfung bisheriger Feldgrenzen und CAN-Auswertung; relativ langsam | wie oben |
| `regression/discipline_checks.py` | Alle fünf langen Disziplinabläufe vollständig; 52 feste Erwartungen | wie oben, mehrere Minuten möglich |
| `ui/lcd_check.py` | 5×8-Zeichenraster, CGRAM-Bitreihenfolge, Zeichengrenzen und gemeinsame LED-Größe | optional vorhandenes Node.js |
| `ui/ui_check.py` | DOM-Bedienung, Profile, Tabs, kompakte CAN-Tabelle, kein Screenshot-Test | optional vorhandenes Node.js |
| `windows/test_windows.ps1` | Starter-/Einrichtungslogik mit Mocks ohne Downloads/Installationen | PowerShell |

Aus dem Projektordner, Windows mit `py -3` statt `python3`:

```sh
python3 -B -m unittest discover -s tests -v
python3 -B tests/regression/session_checks.py "../DIC_Firmware"
python3 -B tests/regression/replay_checks.py "../DIC_Firmware"
python3 -B tests/regression/firmware_changes.py "../DIC_Firmware"
python3 -B tests/regression/integration.py "../DIC_Firmware"
python3 -B tests/regression/discipline_checks.py "../DIC_Firmware"
python3 -B tests/ui/ui_check.py
python3 -B tests/ui/lcd_check.py
```

Falls Node nicht im PATH liegt, kann `DIC_NODE` auf eine vorhandene ausführbare Node-Datei zeigen. Node ist keine Laufzeitabhängigkeit der Anwendung. Die PowerShell-Prüfung wird mit `pwsh -NoProfile -File tests/windows/test_windows.ps1` gestartet; unter Windows PowerShell entsprechend `powershell.exe`.

`verify.py` im Hauptordner startet die sechs Fahrzeugfälle, die auch die Oberfläche anbietet. Diese sechs Fälle ersetzen weder die detaillierten Simulatorregressionen noch die vollständigen Disziplinszenarien. Sollwerte sind ausdrücklich festgelegt und werden nicht aus aktuellen Ausgaben gelernt.
