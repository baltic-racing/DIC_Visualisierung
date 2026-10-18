"""Explicit vehicle assertions using the existing host simulation; also usable as CLI.

Expectations are reviewed constants, never recorded from the run being tested.
The raw GPIO output is checked, not the browser's extra AMS warning colour.
"""
import argparse
import json
from pathlib import Path
import tempfile

CASES = [
    dict(id='normal', name='Normalbetrieb', description='AMS- und IMD-Ausgänge aus; Fahrmodus 3 im TX-Telegramm.',
         inputs={}, checks=[('outputs.ams_led', 0), ('outputs.imd_led', 0), ('outputs.tx.7', 3)]),
    dict(id='ams', name='AMS-Fehler', description='AMS-Fehlerbit aktiviert den echten AMS-Ausgang und alle sechs unteren LEDs.',
         inputs={'ams_error': 1}, checks=[('outputs.ams_led', 1), ('outputs.bottom', [1]*6)]),
    dict(id='imd', name='IMD-Fehler', description='IMD-Fehlerbit aktiviert den IMD-Ausgang nach 5 simulierten Sekunden ab Kaltstart.',
         inputs={'imd_error': 1}, checks=[('outputs.imd_led', 1)]),
    dict(id='can-loss', name='CAN-Empfangsausfall', description='Keine neuen AMS-Daten nach 0,5 s: AMS-Warnung muss nach 5 s ab Kaltstart aktiv sein.',
         inputs={'ams_mode': 2}, checks=[('outputs.ams_led', 1)]),
    dict(id='pages', name='Displayseiten · Format', description='Jede Seite aus page_order liefert genau 4 Zeilen mit je 20 Zeichen. Kein Test des Layoutinhalts.',
         inputs={}, checks=[]),
    dict(id='diagnosis', name='AMS-Diagnosetext', description='Diagnosecode 6 muss auf dsp_reduced in Zeile 2 „PEC“ anzeigen. Ohne diese Seite nicht konfiguriert.',
         inputs={'diag': 6}, page='dsp_reduced', checks=[('text.1.contains', 'PEC')]),
]


def catalog():
    return [{key: case[key] for key in ('id', 'name', 'description')} for case in CASES]


def lookup(frame, path):
    value = frame
    for key in path.split('.'):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def run_suite(backend, source='auto', ref=None, test='all'):
    if source not in ('auto', 'local', 'test', 'ref'):
        raise ValueError('Unbekannte Codequelle für Tests.')
    chosen = CASES if test == 'all' else [case for case in CASES if case['id'] == test]
    if not chosen:
        raise ValueError('Unbekannter Testfall.')
    results = []
    # One immutable source snapshot for the whole run. No test changes input UI,
    # source selection, config files, or firmware files.
    with backend.LOCK:
        try:
            snapshot = backend.sources(source, ref)
            _, pages = backend.compile_preview(snapshot[0], snapshot[4])
        except Exception as exc:
            return dict(ok=True, source=source, revision=None, results=[dict(id=c['id'], name=c['name'], status='failed',
                        checks=[dict(label='Kompilierung', expected='Firmware für Host-Simulation kompilierbar', actual=str(exc), passed=False)]) for c in chosen])
    for case in chosen:
        result = dict(id=case['id'], name=case['name'], status='passed', checks=[])
        if case.get('page') and case['page'] not in pages:
            result.update(status='not-configured', reason='Die explizite Erwartung ist für ' + case['page'] + ' definiert. Diese Seite existiert in dieser Quelle nicht.')
            results.append(result)
            continue
        selected = pages if case['id'] == 'pages' else [case.get('page', pages[0])]
        try:
            for page in selected:
                values = {f['id']: f['default'] for f in backend.FIELDS}
                values.update(duration=5000)
                values.update(case['inputs'])
                query = {key: [str(value)] for key, value in values.items()}
                query.update(source=[source], ref=[ref], page=[page], scenario=['example'], raw=[''])
                frame = backend.frame(query, snapshot=snapshot)
                if case['id'] == 'diagnosis' and not {'ams_diagnostic_code', 'ams_diagnostic_valid'} <= frame['outputs'].keys():
                    result.update(status='not-configured', reason='Diese Quelle stellt keine AMS-Diagnosemetadaten für die festgelegte PEC-Textprüfung bereit.')
                    break
                if case['id'] == 'pages':
                    rows = frame.get('rows', [])
                    actual = [len(rows), [len(row) for row in rows]]
                    expected = [4, [20, 20, 20, 20]]
                    result['checks'].append(dict(label=page + ' · Zeichengeometrie', expected=expected, actual=actual, passed=actual == expected))
                else:
                    for path, expected in case['checks']:
                        if path.startswith('text.'):
                            actual = ''.join(chr(c) for c in frame['rows'][int(path.split('.')[1])])
                            passed = expected in actual
                        else:
                            actual = lookup(frame, path)
                            passed = actual == expected
                        result['checks'].append(dict(label=path, expected=expected, actual=actual, passed=passed))
            if not all(c['passed'] for c in result['checks']):
                result['status'] = 'failed'
        except Exception as exc:
            result['status'] = 'failed'
            result['checks'].append(dict(label='Ausführung', expected='Simulationslauf mit den festgelegten Eingaben', actual=str(exc), passed=False))
        results.append(result)
    return dict(ok=True, source=snapshot[1], revision=snapshot[4][:12], results=results)


def main():
    parser = argparse.ArgumentParser(description='DIC-Fahrzeugtests gegen externen Firmware-Klon (nur lesend)')
    parser.add_argument('firmware', type=Path)
    parser.add_argument('--source', choices=('auto', 'local', 'test', 'ref'), default='auto')
    parser.add_argument('--ref')
    parser.add_argument('--test', default='all', choices=['all']+[c['id'] for c in CASES])
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    from . import server
    server.REPO = server.settings.validate_firmware(str(args.firmware), server.FILES)
    with tempfile.TemporaryDirectory(prefix='DIC-verify-') as temporary:
        server.BUILD_ROOT = Path(temporary)
        result = run_suite(server, args.source, args.ref, args.test)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result['source'], '·', result['revision'])
        for case in result['results']:
            print(case['name'], {'passed': 'BESTANDEN', 'failed': 'FEHLGESCHLAGEN', 'not-configured': 'NICHT KONFIGURIERT'}[case['status']])
            if case.get('reason'):
                print(' ', case['reason'])
            for check in case['checks']:
                if not check['passed']:
                    print(' ', check['label'], 'Erwartet:', check['expected'], 'Tatsächlich:', check['actual'])
    return 1 if any(r['status'] == 'failed' for r in result['results']) else 2 if any(r['status'] == 'not-configured' for r in result['results']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
