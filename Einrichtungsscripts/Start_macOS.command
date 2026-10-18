#!/bin/zsh
cd -- "${0:A:h}/.." || exit 1
if command -v python3 >/dev/null 2>&1; then
    python3 start.py
else
    echo "Bitte Python 3.10 oder neuer von https://www.python.org/downloads/macos/ installieren."
    read "?Enter zum Schließen …"
fi
