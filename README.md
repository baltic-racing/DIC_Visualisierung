# DIC-Visualisierung

Lokale Entwicklungs- und Testumgebung für die DIC-Firmware.

Die Anwendung stellt das 20×4-LCD, die LEDs und verschiedene Fahrzustände dar. CAN-Nachrichten, Displayprofile und Fahrabläufe können simuliert werden, um Änderungen an der Firmware zu testen.

Die originale C-Displaylogik wird verwendet. Das Firmware-Repository bleibt unverändert und wird nur lesend eingebunden.

## Voraussetzungen

- Python 3
- C-Compiler (clang oder GCC)
- Aktuelles Firmware-Repository mit `DIC_23`

## Installation und Start

### macOS

`Einrichtungs- und Startscripts/Start_macOS.command` doppelklicken.

### Windows

1. `Einrichtungs- und Startscripts/Einrichtung_Windows.bat` ausführen.
2. Anschließend `Start_Windows.bat` im selben Ordner starten.

Vor notwendigen Downloads oder Installationen wird eine Bestätigung angefordert.

### Linux / Terminal

Im Projektverzeichnis folgenden Befehl ausführen:

```bash
python3 -B start.py
```

Unter Windows alternativ:

```bash
py -3 -B start.py
```

Unter Linux müssen Python und ein C-Compiler gegebenenfalls vorher installiert werden.

Der lokale Server läuft ausschließlich über `127.0.0.1`.

## Verwendung

1. **Firmware auswählen:** Unter `Quelle` den Firmware-Ordner mit `DIC_23` auswählen. Der Pfad wird lokal gespeichert.
2. **Arbeitsstand festlegen:** `Automatisch: aktueller Branch` oder `Dateien im Arbeitsordner` auswählen, um lokale Änderungen zu verwenden.
3. **Firmware bearbeiten:** Änderungen in VS Code vornehmen und speichern. Die Anwendung erkennt Änderungen und erstellt einen neuen Build.
4. **Simulation starten:** Über `Start / Fortsetzen` die Simulation ausführen. Mit `Pause`, `Simulieren bis` und `Reset / Kaltstart` lässt sich die virtuelle Zeit steuern.
5. **Testdaten verwenden:** Unter `Beispielwerte → Fahrablauf` vordefinierte Abläufe laden oder eigene Werte, Displayprofile und CAN-Rohdaten eingeben.
