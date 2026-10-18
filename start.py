"""Double-click launchers enter here; no third-party Python packages required."""
import sys

if sys.version_info < (3, 10):
    print('Bitte Python 3.10 oder neuer von python.org installieren.')
    input('Enter zum Schließen …')
    raise SystemExit(1)

from server import main

if __name__ == '__main__':
    try:
        main(open_browser=True)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f'Die DIC-Visualisierung konnte nicht gestartet werden: {exc}')
        input('Enter zum Schließen …')
        raise SystemExit(1)
