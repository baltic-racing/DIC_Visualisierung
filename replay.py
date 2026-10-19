"""Command entry point; implementation lives in dic_visualisierung.replay."""
from dic_visualisierung.replay import main

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        raise SystemExit("Replay-Fehler: " + str(error))
