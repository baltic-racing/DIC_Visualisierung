"""Machine-local configuration. Never writes into the firmware checkout."""
import json
import os
from pathlib import Path
import sys
import tempfile


def settings_directory():
    if os.environ.get('DIC_VIS_CONFIG_DIR'):
        return Path(os.environ['DIC_VIS_CONFIG_DIR']).expanduser()
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'DIC_Visualisierung'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/DIC_Visualisierung'
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'DIC_Visualisierung'


def load(directory=None):
    path = (directory or settings_directory()) / 'settings.json'
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def validate_firmware(path, filenames):
    if not isinstance(path, str) or not path.strip():
        raise ValueError('Bitte den lokalen Ordner des Firmware-Repositories auswählen.')
    root = Path(path).expanduser().resolve()
    if root.name == 'DIC_23':
        root = root.parent
    if not root.is_dir():
        raise ValueError('Dieser Ordner existiert nicht oder ist nicht zugänglich.')
    missing = [f'DIC_23/{name}' for name in filenames if not (root / 'DIC_23' / name).is_file()]
    if missing:
        raise ValueError('Kein passender Firmware-Ordner. Es fehlen: ' + ', '.join(missing))
    return root


def save_firmware(root, directory=None):
    directory = directory or settings_directory()
    # A deliberately chosen config override must not put files into the firmware.
    resolved = directory.resolve()
    if resolved == root or root in resolved.parents:
        raise ValueError('Der Einstellungsordner darf nicht im Firmware-Repository liegen.')
    directory.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='settings-', suffix='.tmp', dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump({'version': 1, 'firmware_path': str(root)}, out, ensure_ascii=False, indent=2)
            out.write('\n')
        os.replace(temporary, directory / 'settings.json')
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
