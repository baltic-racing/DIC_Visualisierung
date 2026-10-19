"""Full isolated replays of all five synthetic Formula Student input scenarios."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dic_visualisierung import replay
from dic_visualisierung import server
def main():
    if len(sys.argv)!=2:raise SystemExit('Aufruf: python3 -B tests/regression/discipline_checks.py /Pfad/zur/DIC_Firmware')
    server.REPO=server.settings.validate_firmware(sys.argv[1],server.FILES)
    source=server.REPO/'DIC_23'
    def hashes():return {str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in source.rglob('*') if p.is_file() and p.name!='.DS_Store'}
    before=hashes()
    with tempfile.TemporaryDirectory(prefix='DIC-disciplines-') as tmp:
        server.BUILD_ROOT=Path(tmp);server.CACHE.clear();server.BUILDS.clear()
        try:
            for kind,mode in [('acceleration',0),('skidpad',1),('autocross',2),('endurance',3),('efficiency',3)]:
                definition=json.loads((ROOT/f'examples/scenarios/fs-{kind}.scenario.json').read_text())
                print('Prüfe',kind,'·',definition['duration_ms']//1000,'simulierte Sekunden …',flush=True)
                result=replay.run(server,definition)
                failed=[c for c in result['checks'] if not c['passed']]
                assert not failed,json.dumps(failed,ensure_ascii=False)
                assert result['time_ms']==definition['duration_ms']
                # Independent invariants, with no learned or recorded golden output.
                assert result['state']['active_mode']==mode
                assert result['outputs']['ams_led']==result['outputs']['imd_led']==0
                assert result['state']['speed_kmh']==0
                tx=result['tx']
                assert len(tx)==definition['duration_ms']//100
                assert all(e['at_ms']==(i+1)*100 and e['can_id']==0x500 and e['data'][7]==mode for i,e in enumerate(tx))
                assert not result['traffic']['tx_history_dropped']
                print('PASS',kind,'·',len(result['checks']),'feste Ablaufprüfungen ·',len(tx),'zeitlich geordnete 0x500-Sendeaufträge',flush=True)
        finally:
            assert hashes()==before,'Originalfirmware verändert'
            server.CACHE.clear();server.BUILDS.clear()
    print('PASS: alle fünf vollständigen Replay-Läufe; Originalfirmware unverändert. Kein Hardwarevergleich.')


if __name__=='__main__':main()
