"""Verify source-driven rendering without writing to the firmware checkout."""
import hashlib
import tempfile
from pathlib import Path
import sys
import argparse
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dic_visualisierung import server
parser=argparse.ArgumentParser(description="Integrationstests gegen vertraute externe Firmware (nur lesend)")
parser.add_argument("firmware", type=Path)
parser.add_argument("--legacy-car", action="store_true", help="Optionale alte Car-Regressionen; für _Test nicht nötig")
args=parser.parse_args()
server.REPO=server.settings.validate_firmware(str(args.firmware),server.FILES)
_build=tempfile.TemporaryDirectory(prefix="DIC_Visualisierung-test-")
server.BUILD_ROOT=Path(_build.name)


def rows(frame):
    return [''.join(chr(c) for c in row) for row in frame['rows']]


original_status = server.git('status','--porcelain')
initial = server.frame({'source':['local']})
assert len(initial['pages']) == 6
for page in initial['pages']:
    result = server.frame({'source':['local'],'page':[page]})
    assert len(result['rows']) == 4 and all(len(r)==20 for r in result['rows'])
    print(page, rows(result))

debug = rows(server.frame({'source':['local'],'page':['dsp_debug'],'front':['42'],'rear':['30']}))
assert debug[0][17:19]=='42'
assert debug[1][17:19]=='30'
assert debug[2][16:19]=='073' and debug[3][16:19]=='026'
assert debug[3][:9]=='V:052km/h'
zero = rows(server.frame({'source':['local'],'page':['dsp_debug'],'scenario':['zero']}))
assert zero[0][17:19]=='00'

# Error bits drive actual firmware outputs; diagnosis is a separate text signal.
def test_frame(**values):
    return server.frame({'source':['local'],'duration':['5000'],'ams_sender':['0'],**{k:[str(v)] for k,v in values.items()}})

assert test_frame()['outputs']['ams_led']==0
assert test_frame()['outputs']['imd_led']==0
assert test_frame()['outputs']['top']==[0]*15
assert test_frame()['outputs']['left_rgb']==[[1,0,0],[1,0,0]]  # BSPD startup lasts 15 s
assert test_frame(ams_error=1)['outputs']['bottom']==[1]*6
amber=test_frame(page='dsp_modes',buttons=2)['outputs']
assert amber['left_rgb']==[[1,1,0],[1,1,0]] and amber['right_rgb']==[[1,1,0],[1,1,0]]
if args.legacy_car:
    assert test_frame(source='ref',ref='origin/TY26_Car')['local']==False
assert test_frame(ams_error=1)['outputs']['ams_led']==1
assert test_frame(imd_error=1)['outputs']['imd_led']==1
assert test_frame(imd_error=1,duration=500)['outputs']['imd_led']==1  # boot lamp test
assert test_frame(ams_mode=1)['outputs']['ams_led']==1
assert test_frame(ams_mode=2)['outputs']['ams_led']==1
assert 'OV ' in rows(test_frame(page='dsp_reduced',diag=1))[1]
assert '???' in rows(test_frame(page='dsp_reduced',diag=22))[1]
assert '---' in rows(test_frame(page='dsp_reduced',diag=255))[1]
assert '---' in rows(test_frame(page='dsp_reduced',diag=1,diag_mode=1))[1]
for code in (0,1,6,9,22):
    diagnostic=test_frame(diag=code)['outputs']
    assert diagnostic['ams_diagnostic_code']==code
    assert diagnostic['ams_diagnostic_valid']==1
assert test_frame(diag=255)['outputs']['ams_diagnostic_valid']==0
assert test_frame(diag=6,diag_mode=1)['outputs']['ams_diagnostic_valid']==0
assert rows(test_frame(page='dsp_debug',gps_mode=1))[3][:9]=='V:---km/h'
assert test_frame(page='dsp_debug',gps_mode=1,duration=800)['active_page']=='dsp_startup'
assert rows(test_frame(page='dsp_main',steering=-42))[2][17:20]=='-42'
assert rows(test_frame(page='dsp_main',apps1=123))[0][17:20]=='012'
assert rows(test_frame(page='dsp_main',ts=32100))[3][16:19]=='321'
assert rows(test_frame(page='dsp_main',inv0=123,inv1=456))[0][5:9]=='45.6'
assert rows(test_frame(page='dsp_main',motor0=123,motor1=456))[1][5:9]=='45.6'
assert rows(test_frame(page='dsp_SDCI',sdc15=0))[0][6]==' '
assert test_frame(ts_button=1,r2d_button=1)['outputs']['tx'][:2]==[0,1]  # TS_ON blocked until 15 s
assert test_frame(mode=2)['outputs']['tx'][7]==2
assert 'UV ' in rows(test_frame(page='dsp_reduced',raw='204: 02 00 00 00 00 00 00 00'))[1]
assert rows(test_frame(page='dsp_debug',raw='401: 64 00 C8 00 00 00 00 00'))[0][17:19]=='10'
for invalid in ['204: 01','123: 00 00 00 00 00 00 00 00']:
    try: test_frame(raw=invalid)
    except ValueError: pass
    else: raise AssertionError('Invalid CAN override accepted')

# Every generated control is parsed and accepted at both limits in the Test source.
for field in server.FIELDS:
    for value in (field['min'],field['max']):
        test_frame(**{field['id']:value})

if args.legacy_car:
    # Exercise real Car sources too, without switching or changing the user's checkout.
    original_sources=server.sources
    car_src={name:server.subprocess.check_output(['git','-C',str(server.REPO),'show',f'origin/TY26_Car:DIC_23/{name}']).decode('utf-8',errors='replace') for name in server.FILES}
    server.sources=lambda mode,ref=None:(car_src,'Car fixture','TY26_Car','fixture',hashlib.sha256(''.join(car_src.values()).encode()).hexdigest(),False)
    assert len(test_frame()['pages'])==7
    assert test_frame(ams_error=1)['outputs']['ams_led']==1
    assert test_frame(imd_error=1)['outputs']['imd_led']==1
    try: test_frame(fuse=255)
    except ValueError as exc: assert 'Sicherungsarrays' in str(exc)
    else: raise AssertionError('Unsafe Car index was not rejected')
    server.sources=original_sources


# Real saved-file update path, using a temporary checkout copy outside the repository.
src, *_ = server.sources('local')
original_repo = server.REPO
with tempfile.TemporaryDirectory(prefix='dic-preview-check-') as tmp:
    root=Path(tmp)
    server.subprocess.run(['git','init','-q',str(root)],check=True)
    server.subprocess.run(['git','-C',str(root),'checkout','-q','-b','TY26_Test'],check=True)
    server.subprocess.run(['git','-C',str(root),'-c','user.name=Preview','-c','user.email=preview@localhost','commit','-q','--allow-empty','-m','Preview fixture'],check=True)
    (root/'DIC_23').mkdir()
    for name,content in src.items():
        (root/'DIC_23'/name).write_text(content,encoding='utf-8')
    server.REPO=root
    before=server.frame({'page':['dsp_main']})
    assert before['local']
    server.subprocess.run(['git','-C',str(root),'checkout','-q','-b','preview-other-source'],check=True)
    assert server.frame({'page':['dsp_main']})['branch']=='preview-other-source'
    assert server.frame({'page':['dsp_main']})['local']
    main=root/'DIC_23/main.c'
    text=main.read_text(encoding='utf-8')
    helper='void preview_layout_helper(struct DISPLAY_PAGE *p) { display_write_str(p,"LIVE:",0,0); }\n'
    text=text.replace('int main(void)',helper+'int main(void)')
    text=text.replace('struct DISPLAY_PAGE dsp_reduced =', 'preview_layout_helper(&dsp_main);\n\tstruct DISPLAY_PAGE dsp_reduced =')
    main.write_text(text,encoding='utf-8')
    after=server.frame({'page':['dsp_main']})
    assert rows(after)[0].startswith('LIVE:')
    assert after['revision']!=before['revision']
    # Compile errors are reported rather than serving the previous successful frame.
    main.write_text(text+'\n#error PREVIEW_EXPECTED_ERROR\n',encoding='utf-8')
    try:
        server.frame({'page':['dsp_main']})
    except ValueError as exc:
        assert 'PREVIEW_EXPECTED_ERROR' in str(exc)
    else:
        raise AssertionError('Compile error was not surfaced')
    main.write_text(text,encoding='utf-8')
    assert rows(server.frame({'page':['dsp_main']}))[0].startswith('LIVE:')
server.REPO=original_repo
assert server.git('status','--porcelain')==original_status
current=server.frame({'page':['dsp_main']})
assert current['local'] and current['branch']==server.git('branch','--show-current')
for page in current['pages']:
    assert len(server.frame({'page':[page]})['rows'])==4
print('PASS: Test and current branch pages, data decoding, saved layout helper, automatic branch switch, error/recovery, unchanged checkout')
_build.cleanup()
print('PASS: all control limits, AMS/IMD outputs and delay, freeze/loss, diagnosis codes/timeout, GPS age, signed steering, temperatures, SDC, TX, raw overrides')
