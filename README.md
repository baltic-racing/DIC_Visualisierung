# DIC-Visualisierung

Lokales Entwicklungswerkzeug für die DIC-Firmware: echte C-Displaylogik, 20×4-LCD, LEDs, CAN-Ereignisse, Profile und reproduzierbare Fahrabläufe. Die Firmware bleibt in ihrem eigenen Repository und wird ausschließlich gelesen.

## Start

- **macOS:** `Einrichtungs- und Startscripts/Start_macOS.command` doppelklicken.
- **Windows:** einmalig `Einrichtungs- und Startscripts/Einrichtung_Windows.bat`, danach `Start_Windows.bat` im selben Ordner. Die Einrichtung fragt vor Downloads/Installationen nach.
- **Terminal, auch Linux:** aus diesem Projektordner `python3 -B start.py` (Windows: `py -3 -B start.py`). Unter Linux Python und clang/GCC zuvor über die übliche Paketverwaltung bereitstellen.

Der Server bindet ausschließlich an `127.0.0.1`. Nach Änderungen an der Anwendung den Server neu starten und die Browserseite neu laden.

## Bedienung

1. Unter **Quelle** den eigenen Firmware-Ordner mit `DIC_23` auswählen; der Pfad wird lokal gespeichert.
2. Für VS-Code-Änderungen **Automatisch: aktueller Branch** oder **Dateien im Arbeitsordner** verwenden.
3. Firmware in VS Code bearbeiten und speichern. Änderungen führen sichtbar zu einem neuen Build und pausierten Kaltstart.
4. **Start / Fortsetzen** drücken. **Pause**, **Simulieren bis** und **Reset / Kaltstart** steuern die virtuelle Zeit.
5. Unter **Beispielwerte → Fahrablauf** ein Beispiel laden oder eigene Werte, Profile und CAN-Rohbytes verwenden.