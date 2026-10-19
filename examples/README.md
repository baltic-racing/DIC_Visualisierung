# Beispiele

- `scenarios/`: direkt ladbare JSON-Szenarien, Format `dic-scenario` Version 1.
- `logs/`: synthetisches klassisches candump-Log mit einem festen 0x500-Sollvergleich.
- `generators/`: Python-Erzeuger der Fahrkurven. Sie schreiben ausschließlich die zugehörigen JSON-Dateien unter `scenarios/`.

Mitgeliefert sind Normalbetrieb, verzögerter AMS-Fehler, IMD-Verriegelung, die generische Bispingen-Außenrunde und fünf Formula-Student-Fahrabläufe. Alle Daten sind synthetisch und enthalten weder Originalfirmware noch persönliche Fahrzeugaufzeichnungen. Die mitgelieferten 10-ms-Sendeperioden sind Testannahmen.

Die JSON-Dateien sind bewusst zusätzlich zu den Erzeugern enthalten: Teammitglieder können sie ohne Erzeugerschritt laden, importieren oder teilen. Die Tests prüfen, dass Erzeuger und gespeicherte Dateien übereinstimmen. Deshalb handelt es sich nicht um versehentlich doppelte Implementierungen der Firmware.

Bei gewollten Änderungen an den Fahrkurven, aus dem Projektordner:

```sh
python3 -B examples/generators/create_bispingen.py
python3 -B examples/generators/create_disciplines.py
```

Das ist eine ausdrückliche Neugenerierung der gebündelten Beispiele, keine automatische Migration von Nutzerprofilen. Eigene Aufzeichnungen/Exporte bleiben durch `.gitignore` ausgeschlossen; nur diese bewusst gebündelten Beispiele sind freigegeben.

## AMS-Fehler nach 20 Sekunden

`scenarios/ams-delayed.scenario.json` läuft 30 Sekunden im Standbetrieb. Nach dem zweisekündigen Lampentest sind AMS und IMD aus. Ab 20,001 s setzen die periodischen Sender das AMS-Fehlerbit in 0x200 (Byte 6, Bit 7) und separat Diagnosecode 6 (PEC) in 0x204 (Byte 0). Nach 50 Prüfaufrufen, bei 20,500 s in diesem Zeitmodell, schaltet die originale Firmware alle sechs unteren AMS-LEDs ein. Auf „Reduziert“ erscheint der Diagnosetext PEC. Der AMS-Zähler läuft weiter; ein Empfangsausfall ist nicht der Auslöser.

Ab 25,001 s werden Fehlerbit und Diagnose zurückgenommen. Der Diagnosetext wird wieder OK, die roten LEDs bleiben gemäß Firmware verriegelt. Am Ende bei 30 s hält der Ablauf an. Erneutes Laden oder Reset beginnt mit einem Kaltstart. Die 14 festen Erwartungen prüfen Lampentest, Verzögerung, echte LED-Ausgänge, Diagnose und Verriegelung; zusätzliche Regressionen kontrollieren die tatsächlich empfangenen CAN-Bytes.

In der Oberfläche den Ablauf auswählen, „Laden / Kaltstart“ und anschließend „Start / Fortsetzen“ drücken. Der Fehler wird als CAN-Eingang erzeugt, nicht als Browser-LED-Übersteuerung. Es wird keine reale Ursache für den beispielhaften PEC-Code simuliert.
