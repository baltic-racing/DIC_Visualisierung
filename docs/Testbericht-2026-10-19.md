# Vollständige lokale Prüfung · 19. Oktober 2026

## Ergebnis

Die vorhandenen Testgruppen und alle mitgelieferten Fahrabläufe wurden ausgeführt. Zwei Fehler wurden reproduziert, korrigiert und durch zusätzliche Regressionstests abgesichert. In den abschließenden Prüfungen bestehen keine bekannten offenen Fehler innerhalb des geprüften Umfangs. Das ist kein Nachweis vollständiger Fehlerfreiheit oder bestätigter Hardwareübereinstimmung.

Umgebung: macOS 27.0.1, Python 3.13.5, vorhandener Apple clang; Browserprüfung im In-App-Browser. Keine Systemkomponenten installiert, kein Push oder Merge. Originalfirmware und vorhandene Nutzereinstellungen/-profile wurden vor und nach der Prüfung per Dateihash verglichen. Alle Testzustände, Firmwareänderungen, Builds und Profile lagen in eigenen temporären Verzeichnissen.

## Gefundene und behobene Fehler

### 1. Ungültige erste Eingabe blockierte die Sitzung

Bei einer ungültigen CAN-Rohbyte-Zeile im ersten Eingabepaket wurde die fehlerhafte Auswahl bereits als Sitzungszustand übernommen. Eine anschließende Korrektur wurde abgewiesen; Reset verwendete erneut das ungültige Paket. Derselbe Fehler war mit einem ungültigen ersten Eingabezeitpunkt möglich.

`dic_visualisierung/simulation.py` validiert Eingabepaket und Kaltstart-Zeitpunkt jetzt vor der Übernahme der Auswahl und dem Schließen einer vorhandenen Sitzung. Korrigierte Eingaben können unmittelbar starten. Abgewiesene Eingaben bei einer Quellenauswahl beschädigen keine vorhandene Sitzung oder Fehlerverriegelung. Ein gültiger Quellwechsel bleibt ein ausdrücklich angezeigter Kaltstart. Worker-Abstürze werden weiterhin nicht durch automatische Neustarts verdeckt.

Drei neue Tests in `tests/regression/session_checks.py` prüfen die Wiederherstellung nach ungültigen Rohbytes, ungültige Anfangszeiten und den Zustandserhalt bei einem abgewiesenen Quellwechsel.

### 2. Szenarioereignisse fehlten in der Statusanzeige

Während eines Replays konnte unter der Zeitsteuerung „Keine geplanten Eingabeänderungen“ stehen, obwohl zukünftige Ereignisse aus der Szenariodatei vorhanden waren. Die Simulation führte sie korrekt aus; die Anzeige zählte nur manuelle Zusatzereignisse.

Der Schnappschuss zählt jetzt beide Wartelisten und meldet ihren frühesten Termin. Periodische Generatoren sind weiterhin keine Liste einmalig geplanter Eingabeänderungen. Ein neuer Test in `tests/regression/replay_checks.py` prüft Dateiereignisse, manuelle Änderungen, Reihenfolge, Verbrauch und unverändernde Beobachtung.

## Ausgeführte Prüfungen

| Gruppe | Ergebnis |
|---|---|
| Lokale Unit-/API-Tests | 37 bestanden; nach den Korrekturen erneut ausgeführt |
| Fortlaufende Sitzung und virtuelle Zeit | 19 bestanden auf endgültigem Stand, einschließlich drei neuer Regressionen |
| CAN-/Replay-/LCD-Verträge und Firmwareabläufe | 26 bestanden, einschließlich der neuen Ereignisanzeige-Prüfung |
| Quelländerungen, zusätzliche/entfernte Seiten und Funktionen | 20 bestanden |
| Fahrzeugfälle der Oberfläche | Alle sechs bestanden; zusätzlich im echten Browser ausgeführt |
| Breite CAN-/Displayintegration | Bestanden; alle vorhandenen Eingabefelder an beiden Bereichsgrenzen, Rohbytes, Fehler, Seiten und Quellaktualisierung |
| UI-DOM-Prüfung | Bestanden; Tabs, Profile, Steuerung, CAN-Tabelle, Fehler-/Statusdarstellung |
| LCD-Rasterprüfung | Bestanden; 95 ASCII-Zeichen, 80 Zellen, CGRAM-Bitreihenfolge, Leer-/Vollzellen und gemeinsame LED-Größe |
| C-Speicher-/Arithmetikprüfung | Alle sechs Fahrzeugfälle mit AddressSanitizer und UndefinedBehaviorSanitizer ohne Befund; Fehler führen dabei zum Abbruch |
| Start und Beenden als eigenständiger Prozess | Bestanden; Start außerhalb des Projektordners, sechs JS-Dateien/CSS, Szenario-/Logimport, fester TX-Vergleich, Pause/Reset, SIGTERM-/Worker-Aufräumen |
| Echte HTTP-Fehlerwiederherstellung | Ungültige erste Eingaben abgewiesen, Korrektur akzeptiert; Szenarioereignisse korrekt im Schnappschuss |
| Quelltext-/Diff-Prüfung | Keine Leerraumfehler; Originalfirmware und persönliche Einstellungen unverändert |

Die fünf Formula-Student-Szenarien liefen vollständig: Acceleration 28 s, Skidpad 48 s, Autocross 89 s, Endurance 307 s und Efficiency 357 s virtuelle Zeit. Bestanden: 52 feste Ablaufprüfungen und Zeit/Reihenfolge/ID/Modusbyte von 8.290 Sendeaufträgen auf 0x500.

Zusätzlich vollständig: Normalbetrieb 60 s mit fünf Erwartungen, IMD-Verriegelung 5,2 s mit drei Erwartungen, Bispingen 104 s mit acht Erwartungen und das candump-Beispiel mit einem festen 0x500-Sollvergleich. Für die normalen Fahrbeispiele ist kein vollständiger Vergleich sämtlicher Nutzdaten jedes TX-Telegramms definiert.

Nach den beiden Korrekturen wurden die betroffenen Sitzungs-/Replay-Prüfungen, die lokalen Tests und die echte HTTP-Prozessprüfung erneut ausgeführt. Die langen Fahrkurven und die breite Feldgrenzenprüfung wurden nicht nochmals wiederholt: Firmwareverarbeitung, Ereignisausführung und Fahrzeugdaten-Encoding wurden durch die Korrekturen nicht verändert.

## Prüfung im echten Browser

Eine getrennte Instanz auf einem eigenen lokalen Port verwendete ausschließlich Testeinstellungen. Geprüft wurden:

- Verbindung, Kompilierung, 15-s-Vorsimulation, gezielter Zeitfortschritt und ein tatsächlicher SWC-Seitenwechsel zur Debug-Anzeige.
- LCD-Zeichen, Live-C-Werte, gleich große obere/seitliche/untere LEDs und die CAN-Tabelle.
- Alle vier Tabs und aufklappbare Bereiche; sechs echte Fahrzeugtests ohne Änderung der pausierten Zeit bei 15.300 ms.
- Profil erstellen, umbenennen, nach Neuladen wiederfinden und das ausschließlich für den Test erzeugte Profil löschen.
- IMD-Szenario bis 5.200 ms: Replay beendet, IMD-Ausgang weiterhin aktiv nach Rücknahme des Fehlereingangs, AMS-Leiste aus und keine angezeigte Sitzungsfehlermeldung.
- Keine Warnungen/Fehler in der abgefragten Browserkonsole; bei der geprüften Layoutbreite von 1.280 CSS-Pixeln kein horizontaler Überlauf.

Eine lückenlose Pixelprüfung aller Fenstergrößen und Browservarianten wurde nicht durchgeführt. Der native Betriebssystem-Ordnerdialog wurde im Test nicht manuell geöffnet; dessen Erfolgs-, Abbruch- und Fehlerpfade sind mit Mocks geprüft.

## Wiederholen und offene Plattformprüfungen

Befehle stehen in [tests/README.md](../tests/README.md). Alle Regressionen verwenden die lokalen Firmwarequellen; ein externer Branch `origin/TY26_Test` ist nicht erforderlich.

Windows, Linux und die PowerShell-Starterprüfung wurden nicht nativ ausgeführt; PowerShell ist auf diesem Mac nicht verfügbar. Es wurden keine Downloads oder Installationen angestoßen. Native Windows-/Linux-Tests sowie ein Vergleich mit dem echten DIC bleiben ausstehend. Compilerinstrumentierung auf dem Host prüft keine vollständige AVR-Arithmetik und ersetzt keine Hardwaretests.
