"""Small adapter for this vehicle: selected source discovery and C boundary hooks."""
from pathlib import PurePosixPath
import posixpath
import re

HARDWARE_HEADERS = {'sys_timer.h'}
NO_HOST_SIBLING = {'sys_timer.h', 'canlib.h'}


def relative_include(parent, include):
    name = posixpath.normpath(str(PurePosixPath(parent).parent / include))
    if name == '..' or name.startswith(('../', '/')) or '\\' in name:
        raise ValueError('Lokale Includes müssen innerhalb von DIC_23 liegen: ' + include)
    return name


def unit(name, source):
    """Keep compiler messages attributable to the original read-only sources."""
    import json
    return '#line 1 ' + json.dumps('DIC_23/' + name) + '\n' + source + '\n#line 1 "host-adapter"\n'


def host_page_table(source):
    source = re.sub(r'\b(?:uint16_t|uint32_t|unsigned\s+long)(?=\s+page_order\b)', 'uintptr_t', source)
    def adapt(match):
        return re.sub(r'\(\s*(?:uint16_t|uint32_t|unsigned\s+long)\s*\)(?=\s*&)', '(uintptr_t)', match[0])
    return re.sub(r'\bpage_order\s*\[[^]]*\]\s*=\s*\{.*?\}', adapt, source, flags=re.S)


def uncomment(source):
    return re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*',
                  lambda m: m[0] if not m[0].startswith('/') else re.sub(r'[^\n]', ' ', m[0]), source, flags=re.S)


def strip_includes(source):
    # Keep host standard headers, remove only local headers and known AVR stubs.
    def replace(match):
        name = match[2]
        if match[1] == '"' or name in ('avr/io.h', 'avr/interrupt.h'):
            return ''
        if name.startswith(('avr/', 'util/')):
            raise ValueError('Hardwareadapter fehlt für Header <' + name + '>. Dieser Hardwarezugriff muss gezielt simuliert werden.')
        return match[0]
    return re.sub(r'^\s*#\s*include\s*(["<])([^">]+)[">][^\n]*', replace, source, flags=re.M)


def function_end(source, start):
    depth = 1
    token = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*|[{}]', re.S)
    for part in token.finditer(source, start):
        if part[0] == '{':
            depth += 1
        elif part[0] == '}':
            depth -= 1
        if depth == 0:
            return part.start(), part.end()
    raise ValueError('Unvollständige C-Funktion im Hardwareadapter.')


def replace_body(source, name, body, required=True):
    match = re.search(r'\bvoid\s+' + re.escape(name) + r'\s*\([^)]*\)\s*\{', uncomment(source))
    if not match:
        if not required:
            return source
        raise ValueError(f'Hardwareadapter: Funktion {name} nicht gefunden. Die Hardware-Schnittstelle muss angepasst werden.')
    close, _ = function_end(source, match.end())
    return source[:match.end()] + '\n' + body + '\n' + source[close:]


def rename_definition(source, name):
    match = re.search(r'\bvoid\s+(' + re.escape(name) + r')\s*\([^)]*\)\s*\{', uncomment(source))
    if not match:
        raise ValueError('Ausgabefunktion nicht gefunden: ' + name)
    return source[:match.start(1)] + 'preview_real_' + name + source[match.end(1):]


def discover(read, exists, base_files):
    """Read only entry files, reachable quoted headers and their matching .c files.

    Timer and CAN drivers stay stubbed. No scanning/compiling unrelated .c files.
    The callbacks read either worktree files or files from one exact Git commit.
    """
    found = {}

    def visit(name, optional=False):
        if name in found or name in HARDWARE_HEADERS:
            return
        if not exists(name):
            if optional:
                return
            raise ValueError('Benötigte Firmware-Datei fehlt: DIC_23/' + name)
        source = read(name).decode('utf-8', errors='replace')
        found[name] = source
        for include in re.findall(r'^\s*#\s*include\s*"([^"\n]+)"', uncomment(source), re.M):
            local = relative_include(name, include)
            if local in HARDWARE_HEADERS:
                continue
            if not exists(local) and exists(include):
                local = include
            if PurePosixPath(local).suffix not in ('.h', '.c'):
                raise ValueError('Nicht unterstützte lokale Include-Datei: ' + local)
            visit(local, optional=local == 'helpers.h')  # older regression fixtures omit this unused header
        if name.endswith('.h') and PurePosixPath(name).name not in NO_HOST_SIBLING:
            sibling = str(PurePosixPath(name).with_suffix('.c'))
            if exists(sibling):
                visit(sibling)

    for name in base_files:
        visit(name)
    return found


def render_hook(sources):
    """Find the driver's typed rendering boundary rather than its function name."""
    pattern = re.compile(r'\bvoid\s+(\w+)\s*\(\s*struct\s+DISPLAY_PAGE\s*\*\s*\w+\s*,\s*struct\s+DISPLAY_STATE\s*\*\s*\w+\s*\)\s*\{')
    candidates = [(name, match[1]) for name, source in sources.items() if name.endswith('.c')
                  for match in pattern.finditer(uncomment(source))]
    main = uncomment(sources['main.c'])
    entry = re.search(r'\bint\s+main\s*\([^)]*\)\s*\{', main)
    if not entry:
        raise ValueError('Firmware-Einstieg int main(...) in main.c nicht gefunden.')
    close, _ = function_end(main, entry.end())
    body = main[entry.end():close]
    called = [(file, name) for file, name in candidates if re.search(r'\b' + re.escape(name) + r'\s*\(', body)]
    if len(called) != 1:
        raise ValueError('Displayadapter: Genau eine aus main.c aufgerufene Funktion mit (struct DISPLAY_PAGE *, struct DISPLAY_STATE *) wird benötigt. Die Hardware-Ausgabeschnittstelle wurde geändert; Adapter bitte gezielt anpassen.')
    return called[0]


def headers(sources):
    ordered, seen = [], set()
    def visit(name):
        if name in seen:
            return
        seen.add(name)
        for include in re.findall(r'^\s*#\s*include\s*"([^"\n]+)"', uncomment(sources[name]), re.M):
            local = relative_include(name, include)
            if local not in sources:
                local = include
            if local in sources and local.endswith('.h'):
                visit(local)
        ordered.append(unit(name, strip_includes(sources[name])))
    for name in sources:
        if name.endswith('.h'):
            visit(name)
    return '\n'.join(ordered)


def page_names(preprocessed):
    match = re.search(r'\bpage_order\s*\[[^]]*\]\s*=\s*\{(.*?)\}', preprocessed, re.S)
    if not match:
        raise ValueError('Seitenreihenfolge page_order nicht gefunden. Unterstützt wird die Seitentabelle des aktuellen Fahrzeugs mit &Seitenvariable-Einträgen.')
    entries = [entry.strip() for entry in match[1].split(',') if entry.strip()]
    names = []
    for entry in entries:
        pointers = re.findall(r'&\s*([A-Za-z_]\w*)', entry)
        if len(pointers) != 1:
            raise ValueError('Nicht unterstützter page_order-Eintrag: ' + entry[:120] + '. Erwartet wird eine Seitenadresse (&Seitenvariable), optional mit Cast.')
        name = pointers[0]
        names.append(name if name not in names else name + '@' + str(len(names)))
    if not 1 <= len(names) <= 256:
        raise ValueError('page_order benötigt 1 bis 256 Einträge (Seitenauswahl über ein CAN-Byte).')
    return names
