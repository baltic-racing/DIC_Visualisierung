# Beispiele

- `scenarios/`: direkt ladbare JSON-Szenarien, Format `dic-scenario` Version 1.
- `logs/`: synthetisches klassisches candump-Log mit einem festen 0x500-Sollvergleich.
- `generators/`: Python-Erzeuger der Fahrkurven. Sie schreiben ausschließlich die zugehörigen JSON-Dateien unter `scenarios/`.

Mitgeliefert sind Normalbetrieb, Akkuübertemperatur, verzögerter AMS-Fehler, IMD-Verriegelung, die generische Bispingen-Außenrunde und fünf Formula-Student-Fahrabläufe. Alle Daten sind synthetisch und enthalten weder Originalfirmware noch persönliche Fahrzeugaufzeichnungen. Die bisherigen 10-ms-Sendeperioden sind Testannahmen. Das neue Temperaturbeispiel verwendet für AMS0 20 ms und AMS1 100 ms gemäß dem gelesenen AMS-TY26-Sender.

Die JSON-Dateien sind bewusst zusätzlich zu den Erzeugern enthalten: Teammitglieder können sie ohne Erzeugerschritt laden, importieren oder teilen. Die Tests prüfen, dass Erzeuger und gespeicherte Dateien übereinstimmen. Deshalb handelt es sich nicht um versehentlich doppelte Implementierungen der Firmware.

Bei gewollten Änderungen an den Fahrkurven, aus dem Projektordner:

```sh
python3 -B examples/generators/create_bispingen.py
python3 -B examples/generators/create_disciplines.py
python3 -B examples/generators/create_ams_temperature.py
```

Das ist eine ausdrückliche Neugenerierung der gebündelten Beispiele, keine automatische Migration von Nutzerprofilen. Eigene Aufzeichnungen/Exporte bleiben durch `.gitignore` ausgeschlossen; nur diese bewusst gebündelten Beispiele sind freigegeben.

## AMS-Fehler nach 20 Sekunden

`scenarios/ams-delayed.scenario.json` läuft 30 Sekunden im Standbetrieb. Nach dem zweisekündigen Lampentest sind AMS und IMD aus. Ab 20,001 s setzen die periodischen Sender das AMS-Fehlerbit in 0x200 (Byte 6, Bit 7) und separat Diagnosecode 6 (PEC) in 0x204 (Byte 0). Nach 50 Prüfaufrufen, bei 20,500 s in diesem Zeitmodell, schaltet die originale Firmware alle sechs unteren AMS-LEDs ein. Auf „Reduziert“ erscheint der Diagnosetext PEC. Der AMS-Zähler läuft weiter; ein Empfangsausfall ist nicht der Auslöser.

Ab 25,001 s werden Fehlerbit und Diagnose zurückgenommen. Der Diagnosetext wird wieder OK, die roten LEDs bleiben gemäß Firmware verriegelt. Am Ende bei 30 s hält der Ablauf an. Erneutes Laden oder Reset beginnt mit einem Kaltstart. Die 14 festen Erwartungen prüfen Lampentest, Verzögerung, echte LED-Ausgänge, Diagnose und Verriegelung; zusätzliche Regressionen kontrollieren die tatsächlich empfangenen CAN-Bytes.

In der Oberfläche den Ablauf auswählen, „Laden / Kaltstart“ und anschließend „Start / Fortsetzen“ drücken. Der Fehler wird als CAN-Eingang erzeugt, nicht als Browser-LED-Übersteuerung. Es wird keine reale Ursache für den beispielhaften PEC-Code simuliert.


## Akku wird heiß · AMS-Übertemperatur

`scenarios/ams-temperature.scenario.json` läuft 45 Sekunden. In der Oberfläche unter **Fahrablauf** auswählen, **Laden / Kaltstart**, danach links **Start / Fortsetzen**. Die größte Akkutemperatur steigt von 32,4 auf 61 °C. Ab 28,001 s liegt sie über 58,611 °C; nach 1,2 s setzt das ausdrücklich nachgebildete AMS-Sendermodell das Fehlerbit in 0x200. Die originale DIC-Logik schaltet bei 29,710 s die sechs roten AMS-LEDs ein. Abkühlung ab 35 s löscht die Verriegelung nicht. 15 feste Ablaufprüfungen sind enthalten.

Die Temperaturkurve ist für die Demonstration beschleunigt, kein physikalisches Akkumodell. Es wird keine AMS-STM32-Firmware ausgeführt. Keine 0x204-Diagnose: Der gelesene AMS-Stand sendet diese nicht, weshalb `AMS-E` weiterhin `---` anzeigen kann. Der oben beschriebene PEC-Ablauf bleibt ein zusätzlicher synthetischer DIC-Test, kein nachgewiesener AMS-Sendeablauf.

CLI aus dem Projektordner (Windows: `py -3` statt `python3`):

```sh
python3 -B replay.py ../DIC_Firmware examples/scenarios/ams-temperature.scenario.json
```


## CAN-Ausfall · AMS und Wiederkehr

`scenarios/can-loss.scenario.json` läuft acht Sekunden. Nach dem Lampentest ist die AMS-Warnung aus. Ab 3,001 s pausieren die AMS-Nachrichten 0x200/0x201; die übrigen Sender bleiben aktiv. Bei 4 s aktiviert die DIC-Lebenszeichenüberwachung die roten AMS-LEDs. Ab 5,001 s kehrt der Empfang zurück, die Warnung bleibt gemäß DIC-Verriegelung an. Acht feste Erwartungen prüfen Ausfall und Wiederkehr.

Die gruppierte Auswahlliste zeigt alle bisherigen Beispiele: Tests & Fehler, Simulationen und eigene Abläufe. Der synthetische PEC-Diagnosetest bleibt unter Tests & Fehler erreichbar. Szenario-API, Import/Export und vorhandene Dateien bleiben vollständig erhalten.
