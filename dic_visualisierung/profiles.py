"""Versioned simulation profiles, stored only in the machine-local config directory."""
import copy
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import uuid

LOCK = threading.RLock()
CAN_IDS = {0x200, 0x201, 0x204, 0x300, 0x400, 0x401, 0x420, 0x44a, 0x453, 0x600, 0x750, 0x797}


def raw_bytes(value):
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError('CAN-Rohbytes müssen Text sein (maximal 4096 Zeichen).')
    parsed = []
    for line in value.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'\s*(?:0x)?([0-9a-fA-F]{1,3})\s*:\s*((?:[0-9a-fA-F]{2}\s*){8})', line)
        if not match:
            raise ValueError('CAN-Zeile erwartet z. B. 204: 01 00 00 00 00 00 00 00')
        canid = int(match[1], 16)
        if canid not in CAN_IDS:
            raise ValueError('Unbekannte CAN-ID für Testdaten')
        parsed.append((canid, bytes.fromhex(match[2])))
    if len(parsed) > 16:
        raise ValueError('Maximal 16 CAN-Zeilen')
    return parsed


def validate_state(state, fields):
    if not isinstance(state, dict) or set(state) - {'values', 'raw', 'scenario', 'page'}:
        raise ValueError('Ungültiger Profilinhalt. Erwartet werden values, raw, scenario und page.')
    values = state.get('values')
    known = {f['id']: f for f in fields}
    if not isinstance(values, dict) or set(values) - known.keys():
        raise ValueError('Das Profil enthält unbekannte Fahrzeugwerte.')
    complete = {}
    for key, field in known.items():
        value = values.get(key, field['default'])
        if type(value) is not int or not field['min'] <= value <= field['max']:
            raise ValueError('Ungültiger Profilwert: ' + field['label'])
        complete[key] = value
    raw = state.get('raw', '')
    raw_bytes(raw)
    scenario = state.get('scenario', 'example')
    if scenario not in ('example', 'zero'):
        raise ValueError('Unbekanntes Simulationsszenario.')
    page = state.get('page', '')
    if not isinstance(page, str) or len(page) > 160 or any(ord(c) < 32 for c in page):
        raise ValueError('Ungültige Displayseite im Profil.')
    return dict(values=complete, raw=raw, scenario=scenario, page=page)


def valid_name(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 80 or any(ord(c) < 32 for c in value):
        raise ValueError('Bitte einen Profilnamen mit 1 bis 80 Zeichen eingeben.')
    return value.strip()


class Store:
    def __init__(self, directory, fields, firmware=None):
        self.directory = Path(directory)
        self.fields = fields
        resolved = self.directory.resolve()
        if firmware is not None and (resolved == firmware.resolve() or firmware.resolve() in resolved.parents):
            raise ValueError('Profile dürfen nicht im Firmware-Repository gespeichert werden.')
        # Also protect an explicit --config-dir before the user selects a repo.
        if any((parent / 'DIC_23/main.c').is_file() for parent in (resolved, *resolved.parents)):
            raise ValueError('Profile dürfen nicht im Firmware-Repository gespeichert werden.')
        self.path = self.directory / 'profiles.json'

    def _read(self):
        if not self.path.exists():
            return []
        try:
            if self.path.stat().st_size > 2_000_000:
                raise ValueError('Profildatei zu groß.')
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or type(data.get('version')) is not int or data.get('version') != 1 or not isinstance(data.get('profiles'), list) or len(data['profiles']) > 100:
                raise ValueError('Unbekanntes Format.')
            items = []
            for item in data['profiles']:
                if not isinstance(item, dict) or not re.fullmatch(r'[a-f0-9]{32}', item.get('id', '')):
                    raise ValueError('Ungültige Profil-ID.')
                items.append(dict(id=item['id'], name=valid_name(item['name']),
                                  state=validate_state(item['state'], self.fields)))
            if len({p['id'] for p in items}) != len(items):
                raise ValueError('Doppelte Profil-ID.')
            return items
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError('Lokale Profile sind beschädigt oder inkompatibel. Die Datei wurde nicht überschrieben: ' + str(exc)) from None

    def _write(self, items):
        self.directory.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix='profiles-', suffix='.tmp', dir=self.directory)
        try:
            with os.fdopen(handle, 'w', encoding='utf-8') as stream:
                json.dump(dict(version=1, profiles=items), stream, ensure_ascii=False, indent=2)
                stream.write('\n')
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def list(self):
        with LOCK:
            return copy.deepcopy(self._read())

    def change(self, request):
        with LOCK:
            items = self._read()
            action = request.get('action')
            if action in ('create', 'import'):
                if len(items) >= 100:
                    raise ValueError('Maximal 100 Profile. Bitte zuerst ein Profil löschen.')
                value = request
                if action == 'import':
                    value = request.get('profile')
                    if not isinstance(value, dict) or value.get('format') != 'dic-simulation-profile' or type(value.get('version')) is not int or value.get('version') != 1:
                        raise ValueError('Keine unterstützte DIC-Profil-Datei (Version 1).')
                item = dict(id=uuid.uuid4().hex, name=valid_name(value.get('name')), state=validate_state(value.get('state'), self.fields))
                items.append(item)
            elif action in ('save', 'rename', 'delete'):
                item = next((p for p in items if p['id'] == request.get('id')), None)
                if item is None:
                    raise ValueError('Dieses Profil existiert nicht mehr. Bitte die Liste neu laden.')
                if action == 'save':
                    item['state'] = validate_state(request.get('state'), self.fields)
                elif action == 'rename':
                    item['name'] = valid_name(request.get('name'))
                else:
                    items.remove(item)
            else:
                raise ValueError('Unbekannte Profilaktion.')
            names = [p['name'].casefold() for p in items]
            if len(names) != len(set(names)):
                raise ValueError('Dieser Profilname wird bereits verwendet. Bitte einen anderen Namen wählen.')
            self._write(items)
            return dict(ok=True, profiles=items, selected=None if action == 'delete' else item['id'])
