"""Isolated folder chooser: macOS native panel, Tk on Windows/other systems."""
import json
import subprocess
import sys


def choose_macos():
    # Do not initialize Tk on macOS: its native file panel can abort Python.
    # Constant AppleScript, no shell or interpolated user input.
    script = 'POSIX path of (choose folder with prompt "DIC-Firmware-Repository auswählen")'
    try:
        result = subprocess.run(['/usr/bin/osascript', '-e', script], capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=110)
    except subprocess.TimeoutExpired:
        return {'error': 'Ordnerdialog nach 110 Sekunden beendet. Bitte erneut öffnen oder den Pfad manuell eingeben.'}
    except OSError:
        return {'error': 'Der native macOS-Ordnerdialog ist nicht verfügbar. Bitte den Pfad manuell eingeben.'}
    if result.returncode:
        if '-128' in result.stderr:  # Standard Additions: user canceled.
            return {'path': ''}
        return {'error': 'macOS konnte den Ordnerdialog nicht öffnen. Bitte den Firmware-Pfad manuell eingeben.'}
    return {'path': result.stdout.rstrip('\r\n')}


def choose_tk():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes('-topmost', True)
    except tk.TclError:
        pass
    try:
        chosen = filedialog.askdirectory(parent=root, title='DIC-Firmware-Repository auswählen', mustexist=True)
        return {'path': chosen}
    finally:
        root.destroy()


def main():
    try:
        value = choose_macos() if sys.platform == 'darwin' else choose_tk()
    except Exception:
        value = {'error': 'Der Ordnerdialog ist nicht verfügbar. Bitte den Pfad im Browser eingeben. Unter Windows enthält Python von python.org normalerweise tkinter.'}
    print(json.dumps(value, ensure_ascii=True))


if __name__ == '__main__':
    main()
