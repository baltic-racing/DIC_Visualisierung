# Beispiele

- `scenarios/`: direkt ladbare JSON-Szenarien, Format `dic-scenario` Version 1.
- `logs/`: synthetisches klassisches candump-Log mit einem festen 0x500-Sollvergleich.
- `generators/`: Python-Erzeuger der Fahrkurven. Sie schreiben ausschließlich die zugehörigen JSON-Dateien unter `scenarios/`.

Mitgeliefert sind Normalbetrieb, IMD-Verriegelung, die generische Bispingen-Außenrunde und fünf Formula-Student-Fahrabläufe. Alle Daten sind synthetisch und enthalten weder Originalfirmware noch persönliche Fahrzeugaufzeichnungen. Die mitgelieferten 10-ms-Sendeperioden sind Testannahmen.

Die JSON-Dateien sind bewusst zusätzlich zu den Erzeugern enthalten: Teammitglieder können sie ohne Erzeugerschritt laden, importieren oder teilen. Die Tests prüfen, dass Erzeuger und gespeicherte Dateien übereinstimmen. Deshalb handelt es sich nicht um versehentlich doppelte Implementierungen der Firmware.

Bei gewollten Änderungen an den Fahrkurven, aus dem Projektordner:

```sh
python3 -B examples/generators/create_bispingen.py
python3 -B examples/generators/create_disciplines.py
```

Das ist eine ausdrückliche Neugenerierung der gebündelten Beispiele, keine automatische Migration von Nutzerprofilen. Eigene Aufzeichnungen/Exporte bleiben durch `.gitignore` ausgeschlossen; nur diese bewusst gebündelten Beispiele sind freigegeben.
