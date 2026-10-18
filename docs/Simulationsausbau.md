# Simulationsausbau – Etappe 2, Version 1.4.0

## Stand, Quellen und Arbeitsgrenzen

Etappe 2 erweitert dieselbe fortlaufende Firmware-Sitzung aus Etappe 1. Es gibt keine zweite Display- oder CAN-Auswertungslogik. Verwendet werden die tatsächlich vorhandenen DIC_23-Quellen, einschließlich **canlib.c**. Projektordner und ihre Anweisungen wurden geprüft; es wurden keine zusätzlichen AGENTS.md gefunden und keine fehlenden Firmware-Dateien durch erfundene Quellen ersetzt.

Vor Beginn bestanden die 16 Abnahmetests aus Etappe 1 erneut. Der Ausgangszustand wurde außerhalb des Projekts gesichert. Die Originalfirmware und vorhandene Nutzerprofile/-einstellungen bleiben unverändert. Alle Firmware-Mutationen, Git-Fixtures, Builds und Testkonfigurationen liegen in isolierten temporären Ordnern. Kein Push, Merge, Cloud-Deployment oder Installieren von Systemkomponenten gehört zu dieser Arbeit.

**Eine bestätigte Übereinstimmung mit dem echten DIC liegt noch nicht vor.** Diese Etappe liefert reproduzierbare Abläufe gegen den begrenzten Host-Adapter und die gelieferte C-Logik.

## Start und Bedienung

Die bisherigen Voraussetzungen und Starter bleiben erhalten: Python 3 und ein vorhandener clang/GCC. Keine neuen zwingenden Pakete.

- macOS: `Einrichtungs- und Startscripts/Start_macOS.command`.
- Windows: bei bereits eingerichteter Umgebung `Einrichtungs- und Startscripts/Start_Windows.bat`.
- Alternativ aus dem Projektordner: `python3 start.py` (Windows: `py -3 start.py`). Nach einem Backend-Update den alten Server beenden und neu starten, anschließend die Browserseite neu laden.

Unter **Beispielwerte → Zeitliches Szenario**:

1. Manuelle Generatoren oder ein mitgeliefertes Beispiel auswählen.
2. Alternativ eine Szenario-JSON-Datei oder ein klassisches candump-Log importieren. Der Import allein verändert keine laufende Sitzung.
3. **Laden / Kaltstart** erstellt ausdrücklich eine neue, pausierte Sitzung bei 0 ms.
4. Start/Fortsetzen, Pause, Zielzeit, Geschwindigkeit und Reset benutzen. Der 1-ms-Einzelschritt bleibt in der API und den automatischen Tests verfügbar; die Schaltfläche entfällt in der Oberfläche.
5. Unter CAN-Kommunikation letzte RX-, TX-, verworfene und LCD-Ereignisse ansehen.
6. Im Tab Tests die festen Szenarioerwartungen einschließlich erwarteter/tatsächlicher TX-Ergebnisse lesen. Die bisherigen Fahrzeugtests laufen weiterhin in eigenen Sitzungen.

Importierte Szenarien liegen bewusst nur im Speicher des lokalen Servers (maximal 30 Einträge einschließlich Beispielen). Für spätere Nutzung die Originaldatei behalten oder **JSON exportieren**. Es gibt keine automatische Profilspeicherung oder Migration. Der Start lädt keine externen Dienste nach.

**LCD · übertragene Zeichen** ist die Standardansicht. **Diagnose · vollständiger Puffer** zeigt einen klar bezeichneten logischen Puffer. Die zusätzliche Auswahl „Nur beobachten“ ändert weder SWC-CAN-Daten noch Zeit. Die bisherige Seitenauswahl ist dagegen ausdrücklich ein **SWC-Eingang über 0x750**, wenn ein dynamischer SWC-Generator vorhanden ist. Bei einem reinen Log oder statischem SWC-Generator ist diese Steuerauswahl deaktiviert; dort bestimmen die aufgezeichneten Frames die reale Seite.

## Architektur: Erhaltene Sitzung, echter Treiber, Ereignissender

| Datei | Aufgabe |
|---|---|
| `dic_visualisierung/server.py` | Lokale APIs, Authentisierung, Quellsnapshots, Host-Kompilierung |
| `dic_visualisierung/simulation.py` | Virtuelle Uhr, Timeline, Eingabeänderungen und Sitzungssteuerung |
| `dic_visualisierung/worker.py` | Begrenzte C-Prozesskommunikation, Watchdog, Verlauf und CAN-Beobachtungsindex |
| `dic_visualisierung/fields.py` | Gemeinsamer Katalog der bestehenden Eingabefelder |
| `dic_visualisierung/host_session.py` | Fortsetzbare Grenze in derselben laufenden C-Hauptschleife, begrenztes Protokoll |
| `dic_visualisierung/host_can.py` | Benötigte Registerzugriffe des echten `canlib.c`, begrenzte Empfangspuffer und LCD-Schreibmodell |
| `dic_visualisierung/generators.py` | Bisherige Wertefelder als CAN-Sender; keine Empfangs- oder Displayauswertung |
| `dic_visualisierung/scenarios.py` | Versioniertes Szenarioformat, Validierung, candump-Import, Beispiel-/Importauswahl |
| `replay.py` → `dic_visualisierung/replay.py` | Isolierter Replay-Lauf ohne Browser |
| `web/session.js`, `web/replay.js` | Zeitsteuerung, Import, Ereignisanzeige und getrennte Beobachtung |
| `verify.py` → `dic_visualisierung/verify.py` | Fahrzeugfälle mit expliziten Sollwerten, jeweils eigene Sitzung |

Ordner, Einstiegspunkte und Aufteilung der Oberfläche: [Projektstruktur](Projektstruktur.md).

Die Firmware wird einmal initialisiert. Globale und statische Variablen sowie lokale Displayseiten, Zeiger und der Aufrufstack bleiben im C-Prozess erhalten. Kein `longjmp`, kein Neustart pro Browserabruf. Auch ein neu geöffnetes Browserfenster hängt sich lesend an die vorhandene Sitzung an; alte lokale Formularwerte werden dabei nicht unaufgefordert als Steuerereignisse gesendet. Die äußere Hauptschleife kooperiert an einer definierten Grenze; ein hängender Durchlauf wird beendet statt aus einem ungültigen Zustand fortgesetzt.

Der synthetische `can_rx()`-Übergangsadapter aus Etappe 1 ist entfernt. Die gelieferte `canlib.c` wird mitkompiliert. Nur Registerzugriffe mit Seiteneffekt (`CANCDMOB`, `CANMSG`) werden in der erzeugten Host-Kopie auf Adapterfunktionen gelenkt. Die echten Abfragen, Initialisierungszweige und Acht-Byte-Lese-/Schreibschleifen bleiben ausgeführt. Änderungen am Treiber gehören zum Quellsnapshot und lösen einen sichtbaren Neustart aus.

## Verifizierte MOb-Regeln und Modellumfang

Die Registerregeln wurden mit dem offiziellen [Microchip AT90CAN32/64/128-Datenblatt, doc7679H](https://ww1.microchip.com/downloads/en/DeviceDoc/doc7679.pdf) abgeglichen, insbesondere 19.5.2, 19.10.17 und 19.11.1–2 (gedruckte Seiten 244–245 und 261–263):

- 15 MObs; bei mehreren passenden Objekten hat die niedrigere Nummer Vorrang.
- RXOK ist Bit 5, TXOK Bit 6, DLCW Bit 7. Empfangsabschluss setzt RXOK und löscht das entsprechende CANEN-Bit.
- Die CONMOB-Bits bleiben erhalten; ihr erneutes Schreiben aktiviert das Objekt wieder. `11` bezeichnet Frame-Buffer-Empfang.
- CANPAGE wählt MOb und Datenindex. AINC ist aktiv-low.
- Abweichendes DLC wird zurückgemeldet; Status und Nutzdaten sind getrennt.

Dies ist der überprüfte Registerausschnitt, keine vollständige CAN-Controller-Emulation. Implementiert sind Standard-Datenframes, ID-Maskierung, per-MOb-Datenpuffer, CANEN, RXOK/DLCW, Seiten-/Indexzugriffe und der vom Treiber benutzte Sendeweg. BXOK-Interruptbehandlung, Busfehler, ACK, Bit-Arbitrierung, Bus-Off, automatische Wiederholung, Remote-Reply und Extended/CAN-FD sind nicht emuliert. CAN-Frame-Zeiten bedeuten idealisierten **Empfangsabschluss**, keine simulierte Busbelegung.

Die Software konfiguriert MObs in `init_mobs()`, aber schaltet sie erst beim ersten `can_rx()`-Aufruf scharf: im gegebenen Ablauf bei 10 ms. Früher eingehende Frames werden mit Grund verworfen. Pro passend konfiguriertem MOb existiert genau ein acht Byte großer Puffer, keine Hardware-Empfangswarteschlange. Nach einer Ankunft bleibt er belegt, bis der echte Treiber das Objekt wieder aktiviert. Eine weitere passende Nachricht kann deshalb verworfen werden. Bei zwei passenden freien MObs gilt die niedrigere Nummer.

Der Treiber liest auch ohne neue Nachricht alle acht Pufferbytes. Die alten Daten bleiben dann erhalten, RXOK wird dabei nicht erfunden. Identische neue Frames setzen dagegen erneut RXOK. Bei einem kürzeren DLC schreibt das Modell nur die gelieferten Bytes; der Rest bleibt im Modell alt. **Die reale Bedeutung ungenutzter Bytes wird damit nicht zugesichert** – der Firmwaretreiber ignoriert DLC beim Kopieren, weshalb Kurzframes separat geprüft werden müssen.

Verwerfungsgründe: CAN-Controller deaktiviert, noch kein passender MOb scharfgeschaltet, kein passender ID-Filter, oder passender MOb belegt/nicht wieder aktiviert. Gesamtzähler und letzte Ereignisse je Art sind sichtbar. Dies ist kein Ersatz für reale CAN-Fehlerzähler.

## Zeitmodell und stabile Ereignisreihenfolge

Die Grundlage aus Etappe 1 bleibt:

- Reproduzierbarer Kaltstart bei 0 ms. Auflösung 1 ms; angenommener Takt 16 MHz, Timer-0-Prescaler 64/OCR0A 249. Der reale Oszillator wurde nicht gemessen.
- Ein vollständiger Firmware-Hauptschleifendurchlauf pro virtuellem Millisekundenschritt. Keine Zyklusgenauigkeit.
- Firmware-Uhr, `sys_time_old` und AMS-Zeitstempel sind im erzeugten Host-Code `uint32_t`; die Gesamtzeit ist getrennt monoton. 32-Bit-Überlauf und verpasste Timerstände bleiben getestet.
- Wandzeit dient ausschließlich der Wiedergabegeschwindigkeit. Last erzeugt sichtbaren Rückstand, keine übersprungenen virtuellen Schritte.

Verbindliche Reihenfolge pro Zeit t:

1. Timerfortschritt auf t.
2. Steueränderungen aus der Szenariodatei in stabiler Dateireihenfolge (GPIO, Eingabewerte, Generatorzustand); danach manuell geplante Änderungen in Auftragsreihenfolge. Der letzte Wert je Eingabefeld gewinnt.
3. Explizite CAN-Ankünfte aus der Datei in Dateireihenfolge, dann manuell geplante CAN-Ankünfte.
4. Fällige periodische Frames in Reihenfolge ihrer Generatordeklaration. Sie verwenden die gerade gültigen Eingaben und Rohbyte-Vorlagen.
5. Tatsächliche Firmware-Verarbeitung einschließlich MOb-Abfragen, Layout, GPIO und Sendefunktion.
6. Schnappschuss und für t definierte Ablaufprüfungen.

Explizite Frames liegen damit vor Generatoren gleicher Zeit: Ein Generator überschreibt kein bereits durch ein explizites Ereignis belegtes MOb. Unterschiedliche Nutzdaten derselben ID zu derselben Zeit sind mehrere Ankünfte, kein „letzter Wert gewinnt“-Empfang. Der zuerst angenommene Frame bleibt im Puffer.

Ereignisse bei t=0 werden nach Firmware-Initialisierung, aber ohne Timer-/Hauptschleifenschritt auf den Peripherieadapter angewandt. Da die MObs noch nicht scharf sind, werden CAN-Frames dann verworfen. GPIO-Werte werden vor dem ersten Verarbeitungsschritt übernommen. Ein Replay endet an seiner definierten Gesamtlaufzeit und bleibt dort stehen. Reset verwirft RAM und manuelle Zusatzereignisse und wiederholt dasselbe Szenario ab seinen Anfangseinstellungen.

Start, Pause, Fortsetzen, Einzelschritt und Zielzeit erhalten Zustände. Ein manueller Ziel-/Einzelschritt pausiert und ersetzt einen eventuellen Wiedergaberückstand durch diesen ausdrücklichen Auftrag. Zielzeiten sind absolut, maximal 60 s voraus pro Aufruf und dürfen das Replay-Ende nicht überschreiten. Ein Schnellstart simuliert tatsächlich jeden Schritt.

## Felder, Rohbytes und Profile

Die bisherigen Felder sind **Sender-Einstellungen**, keine Befüllung beim Empfangsaufruf. In Live-Nutzung senden die bekannten zwölf IDs standardmäßig alle 10 ms, erstmals bei 11 ms. Dadurch findet die erste Ankunft nach dem Scharfschalten statt. Das sind nachvollziehbare Testintervalle, keine bestätigten Fahrzeug-Sendeperioden.

Der AMS-Zähler läuft weiter, friert bei entsprechender Einstellung auf seinem zuletzt gesendeten Wert ein und läuft nach Rücknahme weiter. Bei Ausfall fehlen Frames vollständig. Neue identische Frames, eingefrorener Zähler und fehlende Frames sind damit getrennte Fälle. Die bisherigen „nach 0,5 s“-Ausfalloptionen behalten ihre Grenze ab Kaltstart; für beliebige Ausfall-/Wiederkehrzeiten Generatorereignisse verwenden. Ein deaktivierter Generator behält seine zeitliche Phase; Wiederkehr sendet ab dem nächsten fälligen Termin.

Rohbyte-Zeilen bleiben konstante Vorlagen für die periodischen Sender; letzte Zeile je ID gewinnt. Sie ersetzen Generatornutzdaten nach dem Werte-Encoding und können auch den Zähler überschreiben. Sie erzeugen weder eine zusätzliche Nachricht noch einen zeitlichen Verlauf. Explizite Szenario-/Logframes bleiben unverändert. Reine Logs haben **keine zusätzlichen Generatoren**, damit fehlende Nachrichten nicht verdeckt werden.

Profile bleiben unverändert im bestehenden Format Version 1: Werte, Rohvorlagen, Beispiel-/Nullwertmodus und SWC-Seitenauswahl. Laden eines Profils ändert Eingaben, niemals Firmware-RAM oder Verriegelungen. Während eines Replays ohne passende Generatoren erzeugen solche Werte keine zusätzlichen CAN-Frames; lokale GPIO-Eingaben bleiben möglich. Der alte Fahrmodus ist weiterhin nur eine Kaltstart-Einstellung, `duration` nur ein altes Einzeltestfeld. Es findet keine unbemerkte Datenmigration oder Überschreibung vorhandener Profile statt.

### Widerspruch bei 0x44A und Einheiten

Der Kommentar bei `inv00_mob` beschreibt ERPM, Duty und Spannung. Die tatsächliche C-Auswertung liest aus **0x44A Bytes 0/1 und 2/3 big-endian Temperaturwerte**; 0x453 wird dort ebenfalls so ausgewertet. Auch die Variablensuffixe `_0`/`_1` sind nicht durchgehend intuitiv. Der Adapter folgt den gelesenen Bytes und IDs, nicht dem widersprüchlichen Kommentar. Das wurde mit festen Rohbytes geprüft: `01 C8 02 D3` ergibt in den ausgewerteten Variablen 456 und 723.

Die vorhandenen Anzeigeskalierungen bleiben als Bedienhilfe erhalten; eine passende DBC oder bestätigte physikalische Einheit wird daraus nicht erfunden.

## Szenarioformat Version 1

Eigenständiges JSON-Format `dic-scenario`, Version 1. Es ist kein Eingabeprofil und kein gespeicherter Firmware-RAM. Unbekannte Versionen/Felder werden abgelehnt; Export/erneuter Import ist idempotent. Bestehende Profile benötigen keine Migration.

Vollständiges kleines Beispiel:

```json
{
  "format": "dic-scenario",
  "version": 1,
  "name": "IMD-Verzögerung und Verriegelung",
  "duration_ms": 5000,
  "initial": {"values": {}, "page": "dsp_main"},
  "generators": [
    {"can_id": 512, "period_ms": 10, "start_ms": 11},
    {"can_id": 1872, "period_ms": 10, "start_ms": 11}
  ],
  "events": [
    {"at_ms": 2001, "kind": "inputs", "values": {"imd_error": 1}},
    {"at_ms": 4001, "kind": "inputs", "values": {"imd_error": 0}}
  ],
  "assertions": [
    {"at_ms": 3999, "path": "outputs.imd_led", "expected": 0},
    {"at_ms": 4000, "path": "outputs.imd_led", "expected": 1},
    {"at_ms": 5000, "path": "outputs.imd_led", "expected": 1}
  ]
}
```

CAN-IDs sind hier JSON-Ganzzahlen, z. B. 512 = 0x200. Fehlende bekannte Anfangswerte erhalten dieselben Standards wie Profile. `initial.raw`, `initial.scenario` (example/zero) und `initial.page` sind optional.

Ereignisarten:

```json
{"at_ms": 11, "kind": "can", "can_id": 516, "dlc": 1, "data": [6]}
{"at_ms": 15000, "kind": "gpio", "pin": "TS_ON", "pressed": true}
{"at_ms": 15100, "kind": "gpio", "pin": "TS_ON", "pressed": false}
{"at_ms": 2001, "kind": "inputs", "values": {"front": 15}, "raw": "", "page": "dsp_debug"}
{"at_ms": 2201, "kind": "generator", "can_id": 512, "enabled": false}
{"at_ms": 3201, "kind": "generator", "can_id": 512, "enabled": true}
{"at_ms": 4201, "kind": "generator", "can_id": 512, "freeze_counter": true}
```

GPIO-Pins sind `TS_ON` und `R2D`, pressed ist boolesch. Ein CAN-Ereignis enthält exakt DLC viele Bytes, DLC 0–8. Unbekannte Standard-IDs dürfen als echte Ankunft erscheinen und werden gegebenenfalls vom Empfangsfilter verworfen. 0x500 ist als Empfang unzulässig und gehört in `expected_tx`.

Generatoren benötigen `can_id` und `period_ms`. Optional: start_ms (Standard 11), end_ms (Szenarioende), enabled, statische data/dlc und counter mit byte/start/step. Ohne data codieren bekannte IDs die vorhandenen Wertefelder. Unbekannte Generator-IDs benötigen explizite Daten. Pro ID ist höchstens ein Generator zulässig. Generatorzustandsereignisse müssen auf einen deklarierten Generator verweisen.

`assertions` haben at_ms, path, expected und optional op (`eq` oder `contains`). Zulässige Beobachtungen sind outputs, state, rows, logical_rows, active_page, time_ms und sys_time; Listenindizes stehen im Pfad, z. B. outputs.tx.7. Es gibt weder eval noch gelernte Sollwerte. Prüfungen werden genau am Zeitpunkt ausgeführt, unabhängig von Browserabrufen.

`expected_tx` enthält zeitlich sortierte 0x500-Frames mit at_ms, can_id, dlc, data und optional tolerance_ms (Standard 0). Die tatsächliche Sendereihenfolge wird positionsweise verglichen; Inhalt, DLC und Zeit müssen passen. Fehlende, zusätzliche, falsche oder verspätete Frames werden angezeigt. Zukünftige Erwartungen sind offen. Bei abgeschnittenem TX-Verlauf gilt der Vergleich nicht als vollständig. Dieser Vergleich setzt eine für den jeweiligen Kaltstart sinnvoll ausgerichtete Aufnahme voraus.

## Klassischer candump-Import

Unterstützt wird die klassische kompakte Form, z. B. aus `candump -L`:

```text
(1000.000000) can0 200#0000000000200001
(1000.011000) can0 200#0000000000200002
(1000.100000) can0 500#0000000000000003
```

- Standard-Datenframes mit 11-Bit-ID und 0–8 Bytes, ein Interface pro Log.
- Zeitbezug: kleinster Zeitstempel wird Null; optionaler nicht negativer Startversatz in ms wird addiert.
- Dezimalzeiten werden exakt gelesen, nicht über float. Sub-ms-Zeiten werden auf die nächste Millisekunde **aufgerundet**, niemals vorgezogen. Innerhalb derselben Ziel-Millisekunde bleibt die Reihenfolge nach Originalzeit erhalten; bei identischer Originalzeit die Dateireihenfolge.
- 0x500 wird ausschließlich erwartete Ausgabe, niemals RX-Eingabe.
- CAN FD (`##`), Extended-, Error- und RTR-Frames, mehrere Interfaces, unvollständige Bytes und anderes Textformat werden mit Fehler abgelehnt. Ungültige Zeilen werden nicht still übersprungen; Leerzeilen sind erlaubt.

Ein Logbeginn mitten im laufenden Fahrzeug ist nicht automatisch ein Firmware-Kaltstart. Frühe Frames können deshalb vor dem Scharfschalten verworfen werden. Ein Startversatz simuliert die Zeit davor tatsächlich; er stellt die Firmwareuhr nicht bloß vor. Eine reale Aufnahme muss für belastbare Vergleiche entsprechend eingeordnet werden.

Mitgeliefert: `examples/logs/minimal.candump`, `examples/scenarios/normal.scenario.json`, `examples/scenarios/imd-latch.scenario.json`, `examples/scenarios/bispingen.scenario.json`. Diese Beispiele sind synthetisch und keine Fahrzeugmessungen.

## LCD und getrennte Ausgänge

`display_write_data()` wird am Hardwareübergang beobachtet. Das Modell hält DDRAM, CGRAM, Cursor, Schreibrichtung und Display-An/Aus. Implementiert sind die im Ablauf benötigten Adressbefehle 0x80…/0x40…, Home, Clear, Entry-Inkrement/-Dekrement und Display-An/Aus. Zeilenadressen: 0x00, 0x40, 0x14, 0x54. Benutzerdefinierte Zeichen werden aus den tatsächlich geschriebenen fünf Bit pro CGRAM-Zeile übernommen.

`rows` enthält übertragenen LCD-Inhalt; `logical_rows` den ausgewählten vollständigen Diagnosepuffer. `active_page` ist die tatsächliche Firmwareseite, `logical_page` der beobachtete Puffer. Das Modell initialisiert DDRAM deterministisch mit Leerzeichen; reale Einschalt-Zufallswerte werden nicht behauptet. Nicht implementierte LCD-Kommandos werden im Schreibverlauf sichtbar, aber nicht als vollständig unterstützt ausgegeben. Controllerinterne Busy-Zeiten, alle Shift-/Function-Set-Varianten und die komplette physische ROM-Schrift werden nicht emuliert. Die Browser-Schriftdarstellung bleibt schematisch.

Eine Seitenumschaltung verändert zunächst den Zeiger. Die erste Layoutaktualisierung für die neue Seite kann erst im nächsten 10-ms-Zweig stattfinden, während bereits Zeichen geschrieben werden. Deshalb kann selbst nach dem ersten Scan noch alter Inhalt stehen. Das ist keine zweite Layoutberechnung im Simulator.

LEDs und GPIO stammen ausschließlich aus tatsächlichen Firmwareausgängen. Zusätzliche AMS-Diagnoseinterpretationen bleiben eine getrennte Warnung. Eine Rückkehr von Empfang oder ein verschwundener Eingang setzt keine Verriegelung künstlich zurück. Die vorhandenen aufrufbasierten AMS-/IMD-Fristen, GPS-/Diagnosealterung, niedrige Bremssumme und `wait` nach Modusbestätigung bleiben unverändert.

## Schnittstellen, Grenzen und Fehlerbehandlung

Weiterhin nur 127.0.0.1, Sitzungstoken, Host-/Origin-Prüfung und no-store. Die input_state-Metadaten bezeichnen manuelle Sender-Einstellungen, nicht Firmware-RAM; ein zeitliches Szenario kann diese während seines Ablaufs überlagern. Kein CORS, keine Shellbefehle aus Eingaben, keine neuen Netzwerkverbindungen der Anwendung. Die Firmware wird nur gelesen. Quellwechsel/Änderungen frieren einen neuen konsistenten Quellenbund ein und starten ausdrücklich pausiert neu. Compilerfehler führen keinen alten Worker weiter.

Ergänzte APIs:

- GET `/api/scenarios`: Beispiele und Importe dieses Serverlaufs.
- POST `/api/scenarios`: action import mit kind scenario/candump, text, optional name/offset_ms; oder action export mit id.
- POST `/api/session`: zusätzlich scenario (id), inspect (page oder null) und can (event mit can_id/dlc/data, optional at_ms). Bestehende Zeit-/GPIO-Befehle bleiben.
- GET `/api/frame`: reiner Schnappschuss. traffic enthält Gesamtzähler, letzte RX/TX/Drop/LCD-Ereignisse und gekennzeichnete Verlaufskürzungen. replay enthält Dauer, Prüfergebnisse und TX-Vergleich.

Das private C-Protokoll bleibt zeilenbasiert mit einer DIC1-JSON-Antwort. Ergänzungen: F für Ankünfte vor dem nächsten Schritt, B für Ankünfte am aktuellen Initialisierungszeitpunkt, V für reine Pufferbeobachtung. Kein Befehl enthält auszuführenden Code. Standardzugriffe gehen weiterhin über S, I und A. F ist ein begrenzter Transportbatch, **kein Hardware-FIFO**.

Begrenzungen:

| Ressource | Grenze |
|---|---|
| Importtext | 5 MiB; HTTP-Importkörper maximal 8 MiB wegen JSON-Hülle |
| Szenariodauer | 10 Minuten |
| Explizite Ereignisse einschließlich Erwartungen | 100.000 |
| Generatoren | 32, höchstens eine Million potentielle Ereignisse insgesamt |
| Explizite CAN-Ankünfte pro ms | 96; mit Generatoren maximal 128 |
| Manuell geplante Änderungen | 1.024 |
| Python/C-Befehl | 8.191 Bytes |
| C-Antwort | 65.536 Bytes |
| C-Ereignistransport | 256 Einträge, Kürzungen werden gezählt |
| Python-Gesamtverlauf | 4.096 Einträge; zusätzlich letzte 20 je Ereignisart |
| TX-Vergleichsverlauf | 10.000 Telegramme, Kürzung ausdrücklich gemeldet |

Die Sitzung leert den C-Transport spätestens nach zehn virtuellen Millisekunden beziehungsweise an Ereignisgrenzen. Normale validierte Batches passen in den Transport. Ein extrem schreibender veränderter Firmware-Durchlauf kann dennoch Diagnostik abschneiden; das wird angezeigt. Dies ändert nicht rückwirkend die tatsächlich verarbeiteten CAN-Frames. Erfasste TX-Zeit bedeutet den Aufruf/Sendeauftrag der Firmware; erfolgreicher Busabschluss und ACK werden ideal sofort angenommen, nicht an Hardware gemessen.

Compiler-/Git-/Worker-Timeouts, Absturzprüfung, getrennte stdout-Protokoll-/stderr-Diagnosekanäle und Aufräumen bei regulärem Ende, Strg+C/SIGTERM bleiben erhalten. Ein Hänger oder Absturz erzeugt keinen heimlichen neuen Firmware-RAM. Die Windows-Dateideskriptorpfade bleiben vorhanden; keine POSIX-only-Pipe-Abfrage wurde eingeführt.

## Getrennte Firmwarekorrekturen und Arithmetik

Es wurde keine fachliche Originalfirmware geändert. Die definierte Initialisierung von `sys_time_old` erfolgt weiterhin nur in der erzeugten Host-Kopie. Der separate, nicht auf das Original angewandte `Firmware-Zeitkorrektur.patch` aus Etappe 1 bleibt vorhanden: definierte Initialisierung und atomarer 32-Bit-Zeitleser auf AVR. Der Patch ist in einer temporären Kopie auf Anwendbarkeit/Host-Verhalten geprüft; keine AVR-Kompilierung wird behauptet.

Gezielt feste 32-Bit-Zeitwerte und uintptr_t-Seitenadressen sind weiterhin notwendig. Allgemeine AVR-Integer-Promotions und Pointer-/Float-/Bibliotheksunterschiede werden nicht vollständig emuliert. Geprüft sind unter anderem unsigned-32-Bit-Zeitüberlauf, signed Lenkwinkel -128 sowie CAN-Bremswerte 0xFFFF → 6553 und Balance 66/33. Bei kleiner Bremssumme bleiben die vorherigen Balancewerte stehen – diese vorhandene Logik wurde nicht „korrigiert“.

## Tests und Abnahme der ursprünglichen Etappe 2

Aus dem Projektordner (Windows: `py -3` statt `python3`):

```sh
python3 -B -m unittest discover -s tests -v
python3 -B tests/regression/session_checks.py "../DIC_Firmware"
python3 -B tests/regression/replay_checks.py "../DIC_Firmware"
python3 -B tests/regression/integration.py "../DIC_Firmware"
python3 -B tests/regression/firmware_changes.py "../DIC_Firmware"
python3 -B verify.py "../DIC_Firmware"
python3 -B replay.py "../DIC_Firmware" examples/scenarios/imd-latch.scenario.json
python3 -B replay.py "../DIC_Firmware" examples/logs/minimal.candump --json
```

Optional mit bereits vorhandenem Node.js: `python3 -B tests/ui/ui_check.py`. Node ist keine Laufzeitabhängigkeit.

Die Prüfungen sind getrennt: `tests/unit/test_scenarios.py` prüft Simulatorformate/Import/Profilkompatibilität; `SimulatorContracts` in replay_checks prüft Register-/Puffer-/LCD-/Reihenfolgeverträge. `FirmwareTimelineOracles` prüft unabhängig festgelegtes Verhalten des gelieferten C-Codes. Sollwerte werden niemals aus aktuellen Resultaten gelernt.

**Historischer Stand bei Abschluss von Etappe 2**, vor den späteren UI-/Beispielergänzungen. Auf macOS mit vorhandenem clang tatsächlich erfolgreich ausgeführt:

- 33 lokale Tests: bisherige 24 plus neun Szenario-/Importverträge.
- 16 Abnahmeprüfungen aus Etappe 1, vor und nach Umbau.
- 22 neue Replay-/Firmware-Ablaufprüfungen: AMS-Zählerlauf/Freeze/Wiederkehr, vollständiger Ausfall, AMS 49/50 und IMD 199/200 Aufrufe, Verriegelungen, 99/100 leere Empfangszyklen und Wiederkehr, identische neue Frames, MOb-Puffer/Filter/Reaktivierung/Priorität/Kurz-DLC, GPIO/Modus/wait, Bremsarithmetik, 0x44A, LCD/CGRAM/Beobachtung, TX-Zeit/Inhalt, Geschwindigkeiten, Pause/Step/Reset, feste fehlerhafte Erwartungen und geschützte Import-API.
- 20 Quelländerungsprüfungen mit temporären Firmwarekopien; zusätzliche Dateien, Seiten, Git-Quellen und Compilerfehler bleiben unterstützt.
- Breite bestehende CAN-/Displayintegration mit allen Feldgrenzen.
- UI-Interaktionen einschließlich Profilen, Szenarioimport/-export, Auswahl und Beobachtung ohne CAN-Eingriff. Dies ist ein DOM-Test, kein Screenshot-Test.
- Regulärer Programmstart in einem separaten Prozess mit isolierter Konfiguration, Laden aller drei JavaScript-Dateien, Import/Replay/TX-Vergleich und SIGTERM-Worker-Aufräumen.
- Isolierte CLI-Läufe mit den mitgelieferten Beispielen. Das candump-Beispiel enthält einen festen 0x500-Sollvergleich.

Die Testprogramme verwenden die gelieferten lokalen Quellen und benötigen keinen externen Branch origin/TY26_Test. Originaldateien werden per Hashvergleich auf unveränderten Inhalt geprüft. Windows, Linux, ein AVR-Compiler und echte Hardware wurden in dieser Etappe nicht ausgeführt.

## Vorbereitung für Etappe 3

Der zeitlich geordnete Empfang, die expliziten GPIO-Ereignisse, tatsächliche LCD-Schreibbytes und erfasste TX-Aufträge bieten nun Vergleichspunkte. Für Etappe 3 bleiben offen:

- Reale Messaufnahme mit nachvollziehbarem Startzustand und gemeinsamem Zeitbezug.
- Bestätigte DBC-/Protokolleinheiten und Klärung des 0x44A-Widerspruchs.
- Reale Sendeperioden, Busbelegung, CAN-Fehler, ACK-/Arbitrierungs- und Latenzmodell.
- Vergleich realer GPIO-/LCD-/CAN-Reaktionen mit passenden Toleranzen.
- Native Windows-Prüfung und gegebenenfalls gezielte weitere LCD-Controllerdetails.

Ein erfolgreicher Replay-Test ist ein Nachweis für die festgelegten Erwartungen in diesem Modell, noch kein bestätigter Hardwarevergleich.

## Aktuelle Bedienung und Beobachtung

- Die Browseransicht liest alle 50 ms einen Schnappschuss (höchstens 20 Abrufe/s ohne überlappende Anfragen); die Konfigurationsprüfung erfolgt etwa alle fünf Sekunden. Das verändert weder Firmwaretakt noch virtuelle Zeit. Es gibt keine interpolierte Firmwareuhr.
- Nur die virtuelle Gesamtzeit wird angezeigt. „Ansicht“ unterscheidet tatsächliche LCD-Zeichen und Diagnosepuffer. „Simulieren bis“ verarbeitet bis zur absoluten Zielzeit seit Kaltstart und pausiert dann.
- Die rechte Einstellungsleiste richtet ihre Höhe an der linken Vorschau aus und scrollt innen. Kleine Fenster ordnen beide Bereiche untereinander an.
- Das Normalbetrieb-Beispiel sendet eine Minute lang periodisch; die manuelle Live-Simulation läuft ohne festes Ende.
- Fahrzeugtests halten die gemeinsame Backend-Sperre nur für Quellaufnahme/Kompilierung, nicht während ihrer unabhängigen Zeitabläufe.
- Die seitlichen RGB-LEDs starten laut main.c rot und werden im unveränderten can_put_data() regulär erst bei 15.000 ms und wait=0 gelöscht. Die Moduswahl setzt Gelb/Grün/Aus. Ein AMS-Diagnosecode aus 0x204 schaltet die untere Warnleiste nicht: Diese folgt dem AMS-Fehlerbit (50 Prüfanrufe) oder der Zählerüberwachung.

Laut sys_timer.c ist der Timer für einen 1-ms-Interrupt bei angenommenen 16 MHz eingestellt; main.c schreibt bei gesetztem draw_data ein Zeichen. 80 Zeichen benötigen nominal 80 ms bei rechtzeitigem Hauptschleifenlauf. Ein Timerflag zählt keine garantiert nachholbare LCD-Warteschlange; unter echter Last können Schreibzeitpunkte abweichen. CAN/Layout-Aufrufe im time_10ms-Zweig sind ebenfalls aufrufabhängig. Realer Takt und zyklusgenaue Laufzeit wurden nicht gemessen.

## Synthetische Bispingen-Runde und kompakte Beispielwerte

`examples/scenarios/bispingen.scenario.json` ist ein versioniertes Szenario mit bestehenden 10-ms-CAN-Generatoren und 100-ms-Eingabestützstellen. `python3 -B examples/generators/create_bispingen.py` erzeugt dieselbe Datei reproduzierbar. Es gibt keine neue Physik- oder Firmwareauswertung.

Das [Kartcenter nennt 1.000 m für die Außenstrecke](https://rs-kartcenter.de/infos/ueber-uns/). Angenommen wird hier eine ungefähr 1 km lange Runde mit generischen Geraden und fünf wechselnden Kurven. **Kurvengeometrie, Rundenzeit, Geschwindigkeiten, Bremswerte und Temperaturen sind synthetisch, keine reale Ralf-Schumacher-Kartcenter-Telemetrie.** Die Betriebsannahmen sind zudem für die Anzeige der DIC-Fahrzeugsignale gedacht, nicht als Fahrzeugmodell eines dortigen Leihkarts. Die Homepage enthält abweichende Zählerangaben; es wird die ausdrücklich benannte Außenstrecke der Informationsseite verwendet.

- 0–16 s: Kaltstart und Stillstand; TS_ON-Puls bei 15,001 s, Ready-to-Drive-Puls bei 15,201 s, jeweils 100 ms. Das bildet nur die lokalen Eingänge ab, keinen realen Hochvolt-Freigabeablauf.
- 16–96,8 s: synthetische stehende Runde, knapp 1.000 m bei Integration des Geschwindigkeitssignals, 0–70 km/h, maximale angenommene Beschleunigung/Verzögerung unter 4,5 m/s².
- 96,8–102 s: Abbremsen; bis 104 s Stillstand. Die Strecke dieses Ausrollens gehört nicht zur 1-km-Rundenangabe.
- Geschwindigkeit, APPS, vordere/hintere Bremswerte, Lenkwert, Spannung und Temperaturen ändern sich. AMS-Zähler und Empfang laufen weiter; keine Fehler werden absichtlich gesetzt. Bremswerte sind vorhandene Anzeigewerte ohne behauptete Bar-Kalibrierung, Lenkwert ist kein vermessener Lenkradwinkel.
- Geschwindigkeit wird unverändert big-endian in 0x797 Bytes 6/7 mit der vorhandenen Zehntel-km/h-Skalierung gesendet. Die originale Firmware rundet auf ganze km/h. Das Beispiel wählt dsp_debug, weil der gelieferte Code dort Geschwindigkeit darstellt.

Die rechte Leiste zeigt den Fahrablauf und sechs kompakte **aus der C-Firmware gelesene** Werte. Manuelle Eingaben, Profile und Dateiwerkzeuge sind separat aufklappbar. Ein neuer APPS1-Beobachter liest nur eine vorhandene C-Variable; er beeinflusst die Firmware nicht. Live-Anzeigen verändern weder Formularentwürfe noch CAN-Ereignisse. Temperaturanzeigen verwenden dieselbe Dezimaldarstellung wie die vorhandene Firmware, ohne eine neue DBC-Bestätigung.

## Formula-Student-Disziplinen als Eingabeszenarien

Die vorhandenen DIC-Modi 0/1/2/3 heißen im gelieferten main.c Acceleration, Skidpad, Autocross und Endurance. Fünf neue Version-1-JSON-Dateien werden von der bestehenden Szenarioauswahl automatisch gefunden. Sie erfordern keine Backend- oder Firmwareänderung. Efficiency verwendet denselben vorhandenen Endurance-Modus 3, keinen erfundenen Modus.

| Datei | Gesamtdauer mit Startphase | Ablauf |
|---|---:|---|
| examples/scenarios/fs-acceleration.scenario.json | 28 s | Stehender Start, angenommene 75 m in 5 s bis 108 km/h, Ausbremsen, Stillstand |
| examples/scenarios/fs-skidpad.scenario.json | 48 s | Einfahrt, etwa zwei Rechts- und zwei Linkskreise bei 40 km/h, Ausfahrt |
| examples/scenarios/fs-autocross.scenario.json | 89 s | Generische Handlingrunde mit Geraden, Slalom und wechselnden Kurven; 0–90 km/h |
| examples/scenarios/fs-endurance.scenario.json | 307 s | Ausschnitt mit fünf verkürzten synthetischen Runden, 20-s-Stillstand zwischen drei und zwei Runden, steigenden Temperaturen und Wiederanfahrt |
| examples/scenarios/fs-efficiency.scenario.json | 357 s | Langsamerer, sanfterer Verlauf auf demselben angenommenen Kurs, ebenfalls mit Halt; keine Verbrauchs- oder Punktewertung |

Alle Szenarien enthalten die bisherige 16-s-Vorbereitungsphase, lokale TS_ON-/Ready-to-Drive-Pulse und einen laufenden AMS-Zähler. Die Startseite ist Debug, um Geschwindigkeit und Bremsdaten aus der echten C-Auswertung zu sehen. Anfangs-Fahrmodus wird einmal über die bestehende Kaltstart-Einstellung gesetzt. Während der Fahrt ändern 100-ms-Stützstellen die bestehenden CAN-Senderwerte; die periodischen Frames laufen alle 10 ms weiter. Profile und Verriegelungen werden dadurch nicht unbemerkt zurückgesetzt. Fehlerfälle bleiben als gesonderte Beispiele erhalten, statt normale Fahrten automatisch mit Fehlern zu vermischen.

Die Disziplincharakteristik orientiert sich an [FS Rules 2026 v1.1, D4–D7](https://www.formulastudent.de/fileadmin/user_upload/all/2026/rules/FS-Rules_2026_v1.1.pdf): Acceleration über 75 m, Skidpad mit Rechts-/Linkskreisen, eine Autocross-Runde und Endurance/ Efficiency. Das vollständige Endurance umfasst laut Regelwerk ungefähr 22 km. Hier werden ausdrücklich kürzere Ausschnitte verwendet; es werden keine 22 km in wenige Minuten komprimiert und keine regulären Rundenlängen behauptet. Die angenommene Acceleration-Geschwindigkeit wird unabhängig zu 75 m integriert; Rundenzeiten und Fahrzeugreaktionen sind synthetische Testannahmen.

Brems- und Lenkeingaben verwenden die vorhandenen Anzeigewerte ohne neue physikalische Kalibrierung. Spannung/Temperatur sind illustrative Eingabeverläufe, keine berechnete Batterie-/Energiebilanz. Efficiency ist kein Effizienznachweis und kein offiziell bewertbarer Wettbewerbslauf. Das Haltfenster zeigt nur Stillstand und Wiederanfahrt: kein realer HV-Ablauf, kein Fahrerwechselprotokoll und keine Aussage zur zulässigen Wechselzeit.

Statische Disziplinen (Design, Cost, Business Plan) haben keinen eigenen DIC-Fahrverlauf. Driverless-Varianten und Trackdrive benötigen im aktuellen Projekt fehlende autonome Status-/Steuerschnittstellen und werden nicht als getestet ausgegeben. Vorhandene manuelle Fahrmodi werden weder dafür umgedeutet noch erweitert.

Reproduzierbar neu erzeugen und isoliert vollständig prüfen:

```sh
python3 -B examples/generators/create_disciplines.py
python3 -B tests/regression/discipline_checks.py "../DIC_Firmware"
```

Der Erzeuger schreibt ausschließlich die fünf Projektbeispiele. Die Prüfungen verwenden temporäre Build-Verzeichnisse, eigene Firmware-Prozesse und die lokal vorhandenen Quellen. Explizite Erwartungen prüfen unter anderem Fahrmodus, GPIO, ausgewählte Geschwindigkeiten, Stillstand im Halt, Zustand am Ende und alle zeitlich geordneten 0x500-Sendeaufträge einschließlich Modusbyte. Sollwerte werden nicht aus einem aktuellen Simulationsergebnis erzeugt. Die unveränderten Originaldateien werden per Hashvergleich kontrolliert.

Frühere Abnahme dieser Szenarioergänzung auf macOS (bei der Strukturänderung nicht vollständig wiederholt): 37 lokale Tests und der bestehende UI-DOM-Test erfolgreich. `tests/regression/discipline_checks.py` hat alle fünf neuen Szenarien vollständig ausgeführt: Acceleration 28.000 ms/10 Erwartungen/280 TX, Skidpad 48.000 ms/10/480, Autocross 89.000 ms/10/890, Endurance 307.000 ms/11/3.070 und Efficiency 357.000 ms/11/3.570. Insgesamt 52 feste Ablaufprüfungen und die Reihenfolge/Zeit/ID/Modusbytes von 8.290 Sendeaufträgen bestanden. Die Originalfirmware ist nach Hashvergleich unverändert. Die komplette 23er-Replay-Regression wurde für diese reine Ergänzung von Eingabedateien nicht erneut ausgeführt; Firmware, CAN-/LCD-Adapter und Backend wurden nicht verändert. Keine native Windows-/Linux-Prüfung oder Hardwareprüfung.

## Lesender CAN-Monitor unter der C-Auswertung

Unter den sechs C-Live-Werten befindet sich die aufklappbare CAN-Tabelle. Sie liest `traffic.can` aus demselben Schnappschuss; ID-Filter und Richtungswahl senden keine Steuerbefehle. Richtungen sind angenommenes RX, DIC-Sendeauftrag TX und verworfene Ankunft.

Eine Zeile pro ID zeigt ID, DLC, acht Hex-Bytepositionen und Ereignisanzahl. Positionen oberhalb des tatsächlichen DLC erscheinen als „—“, nicht als alter MOb-Pufferinhalt. Tooltips enthalten Byteposition und Dezimal-/Binärwerte. Es gibt keine Bytekarten, zweite Payload-Zeile oder zusätzliche Scrollfläche. Für die zwölf normalen Empfangs-IDs entstehen zwölf Zeilen; kleine Fenster können die äußere Seitenleiste scrollen.

Zeit, Alter, letzter Abstand und gegebenenfalls Verwerfungsgrund stehen in der gemeinsamen Detailzeile nach Klick oder Tastaturfokus. Datenänderungen aktualisieren bestehende Zeilen; bei unveränderter ID-Liste bleiben Fokus und Auswahl erhalten.

`Worker.can_latest` hält höchstens 2048 Standard-IDs je Richtung. Diese Zusammenfassung ist ein Beobachtungsindex, **keine zusätzliche Empfangswarteschlange**. Sie beeinflusst RXOK, Pufferbelegung, Freigabe und Firmwareaufrufe nicht. Sie bleibt erhalten, wenn ein altes Ereignis aus dem auf 20 Einträge begrenzten Detailverlauf fällt. Identische neue Nachrichten erhöhen den Zähler; bloße Browserabrufe und C-Abfragen erhöhen ihn nicht. Ohne neue Nachricht bleibt der letzte Datensatz erhalten, sein Alter wächst mit der virtuellen Zeit. Kaltstart/Reset beginnen mit leerem Index. Pro Filter werden maximal 100 passende IDs gerendert, mit sichtbarer Trefferzahl; der vollständige begrenzte Index bleibt in der API verfügbar.

Einträge repräsentieren angenommene MOb-Ankünfte, nicht zwingend schon erfolgte `can_rx()`-/`can_put_data()`-Auswertung. Die darüberliegenden Werte stammen separat direkt aus C. Es gibt bewusst keinen unabhängig nachgebauten Signaldecoder, keinen DBC-Import/-Editor und keine erfundenen Einheiten. Bei verlorenen C-Transportereignissen wird die Erfassung ausdrücklich als unvollständig bezeichnet; Zähler sind dann beobachtete, keine garantierten Gesamtanzahlen. Bei einer fehlgeschlagenen Vorschau wird der letzte bestätigte Tabellenstand als solcher markiert. TX ist weiterhin der Firmware-Sendeauftrag mit idealisierter Fertigstellung, kein gemessenes Bus-ACK.

### Größeres 20×4-Layout im Firmware-Code

Layout und fachliche Funktionen werden weiterhin im originalen Firmwareprojekt bearbeitet, zum Beispiel in VS Code. Speichern löst für lokale Quellen einen neuen Host-Build und einen ausdrücklich angezeigten, pausierten Kaltstart aus. Ein geöffnetes Editorfenster allein bestimmt nicht die verwendete Codequelle.

Die vorhandene `display_large_number()` in display.c arbeitet bereits mit zusammengesetzten Zeichen, schreibt aber hart auf alle vier Zeilen. Ihr offset ist eine Spalte, kein Zeilenversatz; number ist eine einzelne Ziffer beziehungsweise ein vordefiniertes Symbol. Für einen oberen Schriftzug über Zeilen 1/2 und Ziffern über Zeilen 3/4 ist deshalb ein eigener zweizeiliger Zeichen-/Ziffernzeichner mit Startzeile notwendig. Die C-Pufferzeilen sind 0/1 beziehungsweise 2/3, die Spalten 0–19. Einfaches Schreiben desselben normalen Textes in zwei Zeilen vergrößert die Zeichen nicht.

`display_definechars()` belegt bereits benutzerdefinierte Muster 1–7. Beide großen Schriftzüge und andere Seiten teilen sich denselben Zeichenspeicher; eine neue Glyphenzuordnung muss mit den vorhandenen Symbolen abgestimmt werden. Slot 0 wäre über direkte Pufferzuweisung nutzbar, aber nicht mitten in den nullterminierten Strings von display_write_str(). Der genaue physische LCD-Controller wurde anhand der vorhandenen Dateien nicht identifiziert; integrierte alternative Font-/Doppelhöhenmodi werden deshalb nicht zugesichert. Die aktuelle, nachweisbare Technik ist die vorhandene Zusammensetzung aus Zeichenzellen.

Der Monitor macht die Simulation besser beobachtbar, nicht automatisch hardwaregetreu. Empfangsbytes, MOb-Ausschnitt und C-Auswertung werden ausgeführt; reale Sendeperioden, Busarbitrierung, Fehler/ACK, exakte CPU-Laufzeiten, vollständige AVR-Zahlenbreiten und das echte LCD-Modul sind weiterhin nicht umfassend validiert. Für den nächsten Genauigkeitsschritt sind echte Aufzeichnungen und ein Hardwarevergleich erforderlich.

## Mögliche Moduslayouts

Vier Fahrmodi mit jeweils fünf Layoutvarianten plus einer gemeinsamen Moduswahl ergeben beispielsweise 21 Ansichten. Die aktuelle Firmware wählt aber alle Modi aus derselben globalen page_order[6] und benutzt active_mode noch nicht zur Auswahl eigener Seitengruppen. Eine einfache spätere Erweiterung könnte die fünf vorhandenen Seitenslots behalten und deren Inhalt abhängig von active_mode zeichnen. Dann entstehen 20 modusspezifische Layouts bei fünf Navigationspositionen plus der gemeinsamen Moduswahl. Die vorhandene Simulation führt solche Änderungen am normalen C-Layoutpfad aus; sie benötigt dafür keine erfundenen Browserlayouts. 21 unabhängige Seiteneinträge in einer flachen page_order unterstützt die bestehende Seitenextraktion grundsätzlich ebenfalls (1–256 Einträge). Die tatsächlichen Drehreglerpositionen des SWC und deren Zuordnung müssen separat geprüft werden.

Es wurden hierfür keine Firmwareänderungen umgesetzt. 21 dauerhaft abgelegte DISPLAY_PAGE-Puffer bräuchten bereits 21×80=1.680 Byte Zeichendaten zuzüglich anderer Daten, Tabellen und Stack. Der [AT90CAN128 besitzt 4 KiB internes SRAM](https://ww1.microchip.com/downloads/en/DeviceDoc/doc7679.pdf), siehe Speicherübersicht auf Seite 2. Deshalb ist das Wiederverwenden weniger Zeichenpuffer und gegebenenfalls das Ablegen konstanter Vorlagen im AVR-Flash sinnvoll. Eine vollständig andere Seitenarchitektur ohne page_order würde weiterhin eine gezielte Anpassung der Anbindung erfordern; sie wird nicht automatisch zugesichert.

## Prüfung der Projektaufteilung

Bei der anschließenden Aufräumetappe wurden ausschließlich Simulatororganisation, Import-/Ressourcenpfade und Dokumentation angepasst. Die C-Firmware und Szenario-Nutzdaten blieben unverändert. HTML, CSS und zentrale Browserlogik wurden getrennt; Profile und Testbedienung haben eigene Skripte. Veraltete Entwicklungshinweise liegen ausdrücklich im [Archiv](archive/Entwicklung-bis-1.2.md).

Auf macOS ausgeführt: 37 lokale Tests, 16 Sitzungsprüfungen, 25 Replay-/Firmwareprüfungen und 20 Quelländerungsprüfungen erfolgreich. Außerdem UI-DOM-Prüfung, sechs Fahrzeugfälle und ein isolierter vollständiger Programmstart außerhalb des Projektordners mit Szenario-/Logimport, festem 0x500-Vergleich, allen fünf JavaScript-Dateien und dem Stylesheet sowie SIGTERM-/Worker-Aufräumen. Die vollständigen fünf Disziplinläufe und die breite Feldgrenzenintegration wurden für die Strukturänderung nicht erneut ausgeführt. Windows/PowerShell, Linux und AVR/Hardware wurden dabei nicht nativ geprüft.

Dateibewertung, Aufteilungen und konkrete Testbefehle: [Projektstruktur](Projektstruktur.md), [Tests](../tests/README.md).

## Punktmatrix-Darstellung des LCD

Die Browserdarstellung verwendet in `web/lcd.js` für alle 20×4 Zeichen eine einheitliche 5×8-Punktmatrix statt der bisherigen Computerschrift. Ein separater matter Rahmen, grüne Hintergrundbeleuchtung und schwach sichtbare inaktive Elektroden verbessern die optische Annäherung. Die normalen ASCII-Muster sind lokale Darstellungsmuster, kein bestätigter ROM-Abzug des tatsächlichen LCD-Moduls. Nicht unterstützte ROM-Zeichen bleiben leer wie bisher; 0xFF wird als volle Punktmatrix dargestellt. Benutzerdefinierte Zeichen verwenden unverändert die tatsächlichen acht CGRAM-Zeilen aus dem C-Schreibmodell. Zeilen, Seiten, Zeitverhalten und C-Auswertung bleiben unverändert; es wurden keine künstlichen Übergangszeiten eingeführt.

Alle LED-Gruppen verwenden dieselbe responsive Durchmesserdefinition wie die obere Leiste. Seitliche Balken und abweichende Größen von AMS/IMD entfallen. Reflexe und Leuchten sind rein optisch; Farben und Schaltzustände werden weiterhin ausschließlich aus den vorhandenen Firmwareausgängen übernommen. Physische Millimetermaße, Leuchtstärke und das reale LCD-ROM sind ohne identifiziertes Modul oder Referenzfoto nicht kalibriert.

Prüfung dieser Darstellungsänderung auf macOS: 37 lokale Tests, bestehender UI-DOM-Test und gezielte Rasterprüfung erfolgreich. Geprüft sind alle 95 ASCII-Muster, feste A-/0-Muster, 80 Zellen, Bitreihenfolge der acht CGRAM-Zeilen, Leer-/Vollzellen, Zellgrenzen, zugänglicher Text und unverändernde Darstellung. Die LED-Prüfung kontrolliert die gemeinsame Durchmesserdefinition ohne abweichende Gruppen-/Mobilgrößen. Befehle: `python3 -B tests/ui/ui_check.py` und `python3 -B tests/ui/lcd_check.py` mit vorhandenem Node.js (gegebenenfalls DIC_NODE setzen). Keine physische Kalibrierung oder visuelle Browser-/Hardwarevergleichsprüfung wird behauptet. Die langen Firmwareläufe wurden für die reine Raster-/CSS-Änderung nicht wiederholt.
