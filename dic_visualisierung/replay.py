"""Run one isolated JSON scenario or classical candump log against local firmware."""
import argparse
import json
from pathlib import Path
import tempfile
from . import server
from . import scenarios
from . import simulation
def run(backend,definition):
    definition=scenarios.validate(definition,backend.FIELDS)
    snapshot=backend.sources('local')
    with simulation.Session(backend,snapshot,backend.input_packet({},snapshot),replay=definition) as session:
        while session.now<definition['duration_ms']:
            session.advance_to(min(definition['duration_ms'],session.now+60000))
        frame=session.frame()
        return dict(name=definition['name'],time_ms=frame['time_ms'],checks=session.check_results,
                    tx_comparison=session.tx_comparison(),tx=list(session.worker.tx_history),
                    traffic=frame['traffic'],state=frame['state'],outputs=frame['outputs'],
                    rows=frame['rows'],logical_rows=frame['logical_rows'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('input',type=Path)
    parser.add_argument('--format',choices=('scenario','candump'))
    parser.add_argument('--offset-ms',type=int,default=0);parser.add_argument('--json',action='store_true')
    args=parser.parse_args()
    if args.input.stat().st_size>scenarios.MAX_BYTES:raise SystemExit('Importdatei überschreitet 5 MiB.')
    kind=args.format or ('scenario' if args.input.suffix=='.json' else 'candump')
    definition=scenarios.import_text(args.input.read_text(encoding='utf-8'),kind,server.FIELDS,args.input.stem[:80],args.offset_ms)
    server.REPO=server.settings.validate_firmware(str(args.firmware),server.FILES)
    with tempfile.TemporaryDirectory(prefix='DIC-replay-') as directory:
        server.BUILD_ROOT=Path(directory);result=run(server,definition)
    failed=sum(not c['passed'] for c in result['checks'])+result['tx_comparison'].get('failed',0)
    if args.json:print(json.dumps(result,ensure_ascii=False,indent=2))
    else:
        print(result['name'],str(result['time_ms'])+' ms')
        print(len(result['checks'])-sum(not c['passed'] for c in result['checks']),'Ablaufprüfungen bestanden ·',failed,'fehlgeschlagen')
        print('0x500:',len(result['tx']),'Sendeaufträge; Vergleich', 'konfiguriert' if result['tx_comparison']['configured'] else 'nicht konfiguriert')
    return 1 if failed or result['tx_comparison'].get('incomplete_history') else 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError) as error:raise SystemExit('Replay-Fehler: '+str(error))
