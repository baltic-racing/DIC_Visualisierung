> **Historisches Dokument:** Beschreibt den damaligen Stand. Aktuelle Pfade/Bedienung: [README](../../README.md), Architektur: [Simulationsausbau](../Simulationsausbau.md).

# Profile, Tests und Firmware-Anbindung

> Seit Version 1.3 läuft die Firmware in einer fortlaufenden Sitzung; Version 1.4 ergänzt ereignisgesteuerten Empfang und Replay. Für das aktuelle Zeitmodell, die getrennte Diagnoseanzeige und die Sitzungs-API gilt [Simulationsausbau.md](../Simulationsausbau.md). Frühere Angaben zu Einzel-Durchläufen beschreiben Version 1.2.

## Start und Architektur

Die Startdateien liegen unter `Einrichtungsscripts/`. Der normale Start bleibt lokal und benötigt keine zusätzlichen Python-Pakete. Python-Backend, Browseroberfläche und C-Host-Simulation bleiben erhalten. Windows-Einrichtung und Compilerwahl sind unverändert. Windows und Linux wurden hier nicht ausgeführt; macOS ist mit tatsächlichem externem Firmware-Code geprüft.

Die Firmware bleibt ein separates Repository. Der Simulator liest daraus Quellen und erzeugt ausschließlich temporäre Host-Dateien. CAN-Treiber, Timer, Display-Übertragung und SPI werden gezielt ersetzt. Die Berechnungen und Displayinhalte stammen weiterhin aus dem C-Code. Ein Neustart des Python-Servers ist nach Änderungen am Simulator selbst erforderlich; gespeicherte Firmware-Änderungen erkennt die Vorschau automatisch.

## Simulationsprofile

Oben unter **Beispielwerte**:

1. Fahrzeugwerte einstellen und einen Namen eingeben.
2. **Neues Profil** erstellt einen vollständigen Schnappschuss.
3. Auswahl eines Profils lädt seine Werte und aktualisiert die Vorschau.
4. Werte ändern und mit **Speichern** das ausgewählte Profil bearbeiten.
5. Namen ändern und **Umbenennen** wählen.
6. **Löschen** entfernt das Profil; die aktuell eingestellten Werte bleiben erhalten.

Gespeichert werden alle vorhandenen Eingabefelder in den ganzzahligen internen CAN-Einheiten, außerdem Rohbyte-Overrides, Empfangsausfälle, Beispiel-/Nullwertszenario und Seitenauswahl. Nicht gespeichert werden persönliche Firmware-Pfade, Codequelle, Branch und Compiler. Ein Profil schaltet also nicht versehentlich auf einen anderen Quellstand um. Gibt es seine Displayseite nicht mehr, wählt die Firmware-Vorschau die erste gültige Seite.

`profiles.json` liegt neben der lokalen `settings.json`, standardmäßig:

| System | Ordner |
|---|---|
| macOS | `~/Library/Application Support/DIC_Visualisierung/` |
| Windows | `%LOCALAPPDATA%\DIC_Visualisierung\` |
| Linux | `$XDG_CONFIG_HOME/DIC_Visualisierung/` oder `~/.config/DIC_Visualisierung/` |

`--config-dir` und `DIC_VIS_CONFIG_DIR` gelten wie bisher auch für Profile. Ein Speicherort innerhalb der Firmware wird abgelehnt. Dateien werden atomar ersetzt. Beschädigte oder inkompatible Profildateien werden gemeldet und nicht überschrieben. Maximal 100 Profile; Namen müssen eindeutig sein. Die `.gitignore` schließt lokale Profildateien und exportierte `*.dic-profile.json` aus.

**JSON exportieren** exportiert die aktuell eingestellten Werte, einschließlich noch nicht gespeicherter Änderungen. **JSON importieren** validiert das Format, legt ein neues Profil an und lädt es. Bei einem bereits vorhandenen Namen wird der Import abgelehnt. Im exportierten JSON kann der Name vor dem Import geändert werden.

Formatversion 1 verwendet diese Struktur:

```json
{
  "format": "dic-simulation-profile",
  "version": 1,
  "name": "Training",
  "state": {
    "values": { "front": 42, "rear": 30, "ams_error": 1 },
    "scenario": "example",
    "raw": "204: 06 00 00 00 00 00 00 00",
    "page": "dsp_main"
  }
}
```

Das Beispiel zeigt nur einige Werte; der Export enthält alle. Beim Einlesen fehlende bekannte Felder erhalten den aktuellen Standardwert. Unbekannte Felder, ungültige Zahlen, boolesche Werte statt Zahlen, unbekannte Szenarien, falsche CAN-IDs oder unvollständige Rohbytes werden abgelehnt. Rohbytes haben weiter Vorrang vor normalen Fahrzeugwerten; simulierte Empfangsausfälle bleiben wirksam. Die Laufzeitprüfung der Firmware verhindert weiterhin bekannte unsichere Fusebox-Indizes im Car-Stand.

## Fahrzeugtests

Der Tab **Tests** und `verify.py` verwenden dieselben Erwartungen und dieselbe C-Host-Simulation. Jeder Fall verwendet frische, feste Standardeingaben plus seine angegebenen Änderungen. Ein Testlauf friert einen Quellstand ein; Änderungen während des Laufs werden erst bei einem neuen Lauf berücksichtigt. Es werden weder Beispielwerte noch Profile, Codequelle oder Firmware-Dateien geändert.

| Fall | Explizite Erwartung |
|---|---|
| Normalbetrieb | AMS-Ausgang 0, IMD-Ausgang 0, TX-Byte 7 gleich Fahrmodus 3 |
| AMS-Fehler | Bei `ams_error=1` AMS-Ausgang 1 und sechs untere LEDs an |
| IMD-Fehler | Bei `imd_error=1` IMD-Ausgang 1 nach 5 simulierten Sekunden ab Kaltstart |
| CAN-Empfangsausfall | Bei `ams_mode=2` AMS-Ausgang 1 nach 5 simulierten Sekunden ab Kaltstart |
| Displayseiten · Format | Jede tatsächlich vorhandene Seite liefert 4 Zeilen mit jeweils 20 Zeichen |
| AMS-Diagnosetext | Auf `dsp_reduced` steht bei Diagnosecode 6 in Zeile 2 das Kürzel `PEC` |

Diese Sollwerte sind Konstanten in `verify.py`; sie werden niemals aus dem gerade geprüften Ergebnis gelernt. Stimmen sie nach einer absichtlichen Protokolländerung nicht mehr, müssen sie bewusst geprüft und angepasst werden. Ein fehlendes `dsp_reduced` oder fehlende AMS-Diagnosemetadaten werden beim Texttest als **nicht konfiguriert** markiert. Der Format-Test bestätigt ausdrücklich nicht den Inhalt oder das Design jeder beliebig veränderten Seite. Dafür wären zusätzliche fachlich festgelegte Erwartungen nötig.

Maßgeblich sind der aktuelle `_Test`-Arbeitsstand und die dafür definierten Erwartungen. Ein alter `_Car`-Stand ist keine Voraussetzung für diese Erweiterung oder ihre Tests.

Die LED-Tests prüfen die tatsächlichen C-/GPIO-Ausgänge. Diagnosewarnungen werden separat angezeigt und überschreiben keine Firmware-LEDs. Testergebnisse zeigen eine verständliche Quellenangabe; interne Revisionskennungen bleiben für die Änderungserkennung erhalten. Nach Quelländerungen werden alte Ergebnisse als nicht zum aktuellen Stand gehörig gekennzeichnet.

Unabhängig vom Browser, aus dem Projektordner:

```sh
python3 verify.py "/Pfad/zur/DIC_Firmware"
python3 verify.py "/Pfad/zur/DIC_Firmware" --test imd
python3 verify.py "/Pfad/zur/DIC_Firmware" --source ref --ref TY26_Test --json
```

Unter Windows `py -3` anstelle von `python3` verwenden. Nur lokal vorhandene Git-Referenzen sind zulässig. Exitcode: 0 = alle ausgewählten Fälle bestanden; 1 = mindestens ein Fehler; 2 = mindestens ein nicht konfigurierter Fall, sonst kein Fehler.

## Automatische Übernahme von Firmware-Änderungen

Die Seitentabelle `page_order` bleibt der Vertrag für dieses Fahrzeug. Die Namen und Reihenfolge werden nach der tatsächlichen C-Vorverarbeitung aus deren Adress-Einträgen übernommen. Kommentare und deaktivierte Tabellen-Einträge erzeugen keine Phantomseiten. Es gibt keine feste Seitenanzahl. Bekannte Seitennamen werden freundlich beschriftet; neue Namen erscheinen unverändert. Für das CAN-Seitenbyte sind 1 bis 256 Einträge unterstützt. Eine feste Arraygröße muss mit der Zahl der Einträge übereinstimmen; andernfalls wird der Build mit einer verständlichen Meldung abgelehnt.

Automatisch unterstützt:

- Seiten hinzufügen, aus der Tabelle entfernen, umbenennen und umsortieren.
- Texte, Zeichenpositionen, Berechnungen und benutzerdefinierte Zeichen im C-Code ändern.
- Normale Funktionen ergänzen, umbenennen, aufteilen oder unbenutzte Funktionen entfernen, solange die gültige Firmware sie entsprechend deklariert und aufruft.
- Den Namen der Display-Ausgabefunktion ändern. Erkannt wird ihre Schnittstelle `void name(struct DISPLAY_PAGE *, struct DISPLAY_STATE *)` mit genau einer direkt aus `main` aufgerufenen Funktion dieser Form.
- Zusätzliche lokale Header und passende gleichnamige `.c`-Dateien einbinden, auch in Unterordnern mit relativen Includes innerhalb von `DIC_23`.
- CAN-Auswertung in den eingebundenen Quellen ändern. Die derzeit simulierten IDs und Datenformate bleiben die bekannten des Fahrzeugs.

### Neue C-Datei einbinden

Einfacher Weg: `new_display.h` aus einer bereits eingebundenen Datei inkludieren und die Implementierung `new_display.c` daneben ablegen. Die Anwendung muss auf Windows weiterhin Python und GCC benutzen können; an deren Einrichtung ändert sich nichts.

```c
/* new_display.h */
#ifndef NEW_DISPLAY_H
#define NEW_DISPLAY_H
#include "display.h"
void update_new_layout(struct DISPLAY_PAGE *page);
#endif
```

```c
/* new_display.c */
#include "new_display.h"
void update_new_layout(struct DISPLAY_PAGE *page) {
    display_write_str(page, "Neue Anzeige", 0, 0);
}
```

Die Firmware muss den Header inkludieren und die Funktion selbst aufrufen. Die Vorschau ruft keine erfundenen Layoutfunktionen auf. Unter **Quelle → Eingebundene Firmware-Dateien** wird die tatsächlich verwendete Auswahl angezeigt. Namen und Inhalte aller ausgewählten Dateien gehören zum Änderungsfingerabdruck. Lokale Git-Quellen verwenden dieselbe Auswahlregel aus einem exakt aufgelösten Commit; uncommittete Dateien bleiben dort ausgeschlossen.

Nicht erreichbare `.c`-Dateien werden nicht kompiliert. `canlib.c` und `sys_timer.c` bleiben bewusst ausgeschlossen, da deren Hardwarefunktionen ersetzt sind. Compilerfehlermeldungen nennen nach Möglichkeit die ursprüngliche Datei unter `DIC_23`, obwohl ausschließlich temporäre Kopien kompiliert werden.

### Konkrete Grenzen

- Die bekannten Basisdateien `main.c`, `candata.c`, `display.c`, `portextender.c`, `port_definitions.c` und ihre bisherigen notwendigen Header bleiben vorausgesetzt. Deren vollständige Umbenennung/Entfernung erfordert eine Adapteränderung.
- Die Hardwaregrenzen für Display-Übertragung, CAN, Timer, SPI und die oben beschriebene Display-Ausgabeschnittstelle müssen erhalten bleiben. Neue Hardwarefunktionen, AVR-Header oder grundlegend andere Datenstrukturen benötigen einen gezielten Adapter. Fehler werden angezeigt, nicht durch scheinbar passende Ersatzlogik verdeckt.
- `page_order` wird als initialisierte Tabelle mit `&Seitenvariable`-Einträgen erwartet, optional mit Cast. Dynamisch zur Laufzeit erzeugte Seitentabellen oder Funktionsaufrufe als Einträge sind nicht unterstützt.
- Die Header-Erkennung ist bewusst einfach und konservativ: lokale Includes werden als Abhängigkeiten verfolgt. Auch ein nur bedingt eingebundener lokaler Header kann deshalb vorhanden sein müssen. Makros als Include-Dateinamen werden nicht aufgelöst.
- Dateien ohne erreichbaren passenden Header oder zusätzliche externe Bibliotheken brauchen eine gezielte Erweiterung der Dateiauswahl beziehungsweise Linkeroptionen. Die Fehlermeldung weist darauf hin.
- Neue CAN-IDs, geänderte Nachrichtenformate und zusätzliche simulierte Eingangssignale benötigen eine Anpassung der bekannten CAN-Stubs und Eingaben. Änderungen der C-Auswertung der bisher unterstützten Nachrichten werden dagegen direkt ausgeführt.
- Die bestehende Simulation kompiliert die ausgewählten C-Quellen gemeinsam in einer Host-Übersetzungseinheit. Gleichnamige `static`-Funktionen in verschiedenen neuen C-Dateien können deshalb kollidieren. Präfixe oder eine spätere gezielte Adapteränderung sind dann nötig.
- Host-Zahlenbreiten, Speicherverhalten, elektrische Eigenschaften, echtes CAN-Timing und Interrupts entsprechen nicht vollständig dem Mikrocontroller. Nur isolierte Tests beginnen jeweils neu. Die interaktive Sitzung erhält ihre Zustände bis Reset oder Quellwechsel.

## Regressionstests der Anwendung

```sh
python3 -m unittest discover -s tests -v
python3 tests/integration.py "/Pfad/zur/DIC_Firmware"
python3 tests/firmware_changes.py "/Pfad/zur/DIC_Firmware"
python3 tests/ui_check.py
```

Die ersten Tests benötigen keine Firmware. Die beiden C-Suiten verwenden ausschließlich temporäre Kopien des externen vertrauenswürdigen Firmware-Klons; Die Prüfungen verwenden die gelieferten lokalen Quellen; ein externer Branch ist nicht erforderlich. Die alten Car-Prüfungen sind nur noch optional mit `tests/integration.py ... --legacy-car` ausführbar und keine Voraussetzung. Veränderungstests prüfen neue/entfernte/umbenannte/umsortierte Seiten, neue Funktionen, entfernte Funktionen, zusätzliche und verschachtelte Dateien, Kompilierfehler, Wiederherstellung und einen absichtlich falschen IMD-Ausgang.

Die optionalen UI-Interaktionstests benötigen Node.js oder `DIC_NODE` mit dessen Pfad. Sie prüfen mit synthetischen API-Antworten Profile, vier Tabs, Tastaturbedienung, Felder/LEDs, Testergebnisse, veraltete Testergebnisse und dynamische Seitenauswahl. Sie sind kein visueller Screenshot-Test. Die eigentliche Simulation benötigt weiterhin kein Node.js.

Windows-Start-/Einrichtungstests, ohne Downloads und Installationen:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tests\test_windows.ps1
```

Windows-Installation, Windows PowerShell 5.1, native Windows-Dialoge und Linux-Läufe müssen weiter auf den jeweiligen Systemen geprüft werden.

## Dateien dieser Erweiterung

| Datei | Änderung |
|---|---|
| `server.py` | Profil-/Test-APIs, Quellsnapshots, Dateierkennung und Host-Build |
| `firmware.py` | Neu: gezielte Abhängigkeiten, Seiten-/Renderer-Erkennung, Host-Anpassungen |
| `profiles.py` | Neu: validierte, lokale und atomare Profilspeicherung |
| `verify.py` | Neu: gemeinsame Sollwerttests für Browser und Kommandozeile |
| `web/index.html` | Profilverwaltung, vierter Tab und dynamische Seitennamen |
| `web/development.js` | Neu: Profil- und Testbedienung, Import/Export und Ergebnisdarstellung |
| `tests/test_extension.py` | Neu: Profil-, API- und Erwartungsprüfungen |
| `tests/firmware_changes.py` | Neu: Änderungen ausschließlich an temporären Firmware-Kopien |
| `tests/ui_check.py` | Neu: UI-Interaktionen ohne zusätzliche Frameworks |
| `tests/integration.py` | Bestehende Tests behalten; Car-Prüfungen optional statt Voraussetzung |
| `tests/test_windows.ps1` | Verweis auf bereits verschobenen Starter in Einrichtungsscripts korrigiert |
| `.gitignore` | Lokale Profile und exportierte Profil-JSONs ausschließen |
| `README.md` | Bestehende kurze Fassung ergänzt, Startpfad-Tippfehler korrigiert |
| `VERSION` | 1.2.0 |
| `docs/Entwicklung.md` | Diese Anleitung und konkrete Unterstützungsgrenzen |

Die übrigen Start-/Einrichtungsskripte, `settings.py`, `choose_folder.py` und `start.py` wurden nicht geändert. Die originale Firmware wurde durch diese Erweiterung nicht bearbeitet. Es wurden kein GitHub-Repository erstellt und kein Push ausgeführt.
