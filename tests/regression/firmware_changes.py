"""Mutate only temporary firmware fixtures to verify the adapter's supported edits."""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dic_visualisierung import server
from dic_visualisierung import verify
def rows(frame):
    return [''.join(map(chr, row)) for row in frame['rows']]


def order(source, names):
    return re.sub(r'\bpage_order\s*\[[^]]*\]\s*=\s*\{.*?\}',
                  'page_order[] = {' + ','.join('&'+name for name in names) + '}', source, count=1, flags=re.S)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware', type=Path)
    args = parser.parse_args()
    original = args.firmware.resolve()
    hashes = {str(p.relative_to(original)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in original.rglob('*') if p.is_file() and '.git' not in p.relative_to(original).parts}
    server.REPO = original
    baseline = server.sources('local')[0]
    count = 0
    with tempfile.TemporaryDirectory(prefix='DIC-firmware-edits-') as tmp, tempfile.TemporaryDirectory(prefix='DIC-edits-build-') as build:
        root = Path(tmp)
        source_dir = root/'DIC_23'
        source_dir.mkdir()
        server.REPO = root
        server.BUILD_ROOT = Path(build)
        def reset():
            for path in list(source_dir.iterdir()):
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
            for name, content in baseline.items():
                path = source_dir/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding='utf-8')
        def write(name, content):
            path = source_dir/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        def frame(page='dsp_main'):
            return server.frame({'page':[page]})
        def check(name, condition):
            nonlocal count
            assert condition, name
            count += 1
            print('PASS', name)
        reset()
        initial = frame()
        names = initial['pages']
        text = baseline['main.c']
        declaration = 'struct DISPLAY_PAGE preview_added = get_empty_display();\ndisplay_write_str(&preview_added,"NEW PAGE",0,0);\n'
        updated = order(text, names+['preview_added'])
        updated = re.sub(r'\b(uint32_t|uintptr_t)\s+page_order', lambda m: declaration+m[0], updated, count=1)
        write('main.c', updated)
        added = frame('preview_added')
        check('new page is discovered and actually rendered', added['pages'][-1]=='preview_added' and rows(added)[0].startswith('NEW PAGE'))

        write('main.c', order(text, [p for p in names if p!='dsp_reduced']))
        removed = frame('dsp_reduced')
        check('removed page disappears and stale selection falls back', 'dsp_reduced' not in removed['pages'] and removed['page']==removed['pages'][0])

        write('main.c', order(text, list(reversed(names))))
        reordered = frame('dsp_main')
        check('page order changes while the selected page stays correct', reordered['pages']==list(reversed(names)) and rows(reordered)[0].startswith('INV :'))

        cast_order = order(text, names)
        table = 'page_order[] = {' + ','.join('(uint32_t)&'+name for name in names) + '}'
        write('main.c', re.sub(r'page_order\[\]\s*=\s*\{.*?\}', lambda m: table, cast_order, count=1, flags=re.S))
        check('AVR pointer casts remain safe on a 64-bit host', rows(frame())[0].startswith('INV :'))

        reset()
        renamed = text
        for name in names:
            renamed = re.sub(r'\b'+name+r'\b', 'new_'+name, renamed)
        write('main.c', renamed)
        check('all page identifiers may be renamed', frame('new_dsp_main')['pages']==['new_'+name for name in names])

        reset()
        for name, content in baseline.items():
            write(name, re.sub(r'\bdraw_char\b','render_current_display',content))
        check('low-level renderer function may be renamed', rows(frame())[0].startswith('INV :'))

        reset()
        display = baseline['display.c']
        match = re.search(r'void\s+display_meme\s*\([^)]*\)\s*\{', display)
        _, end = server.firmware.function_end(display, match.end())
        write('display.c', display[:match.start()]+display[end:])
        write('display.h', re.sub(r'void\s+display_meme\s*\([^)]*\)\s*;', '', baseline['display.h']))
        check('unused display function may be removed', rows(frame())[0].startswith('INV :'))

        reset()
        helper = 'void new_layout_helper(struct DISPLAY_PAGE *p) { display_write_str(p,"HELP:",0,0); }\n'
        write('main.c', text.replace('int main(void)', helper+'int main(void)').replace('struct DISPLAY_PAGE dsp_reduced =','new_layout_helper(&dsp_main);\nstruct DISPLAY_PAGE dsp_reduced ='))
        check('new C function is executed', rows(frame())[0].startswith('HELP:'))

        reset()
        header = '#ifndef NEW_DISPLAY_H\n#define NEW_DISPLAY_H\n#include "display.h"\nvoid new_layout(struct DISPLAY_PAGE *p);\n#endif\n'
        helper = '#include "new_display.h"\nvoid new_layout(struct DISPLAY_PAGE *p) { display_write_str(p,"FILE:",0,0); }\n'
        main_with_helper = '#include "new_display.h"\n'+text.replace('struct DISPLAY_PAGE dsp_reduced =','new_layout(&dsp_main);\nstruct DISPLAY_PAGE dsp_reduced =')
        write('new_display.h', header)
        write('new_display.c', helper)
        write('unrelated_hardware.c', '#error DO_NOT_COMPILE_UNRELATED_HARDWARE\n')
        write('main.c', main_with_helper)
        external = frame()
        check('reachable .c/.h included, unrelated C excluded', rows(external)[0].startswith('FILE:') and 'new_display.c' in external['source_files'] and 'unrelated_hardware.c' not in external['source_files'])
        write('new_display.c', helper.replace('FILE:', 'EDIT:'))
        edited = frame()
        check('saved extra-file changes trigger a new build', edited['revision']!=external['revision'] and rows(edited)[0].startswith('EDIT:'))
        write('new_display.c', helper+'\n#error EXPECTED_BAD_EXTRA_FILE\n')
        try:
            frame()
        except ValueError as exc:
            check('extra-file compiler error is shown', 'EXPECTED_BAD_EXTRA_FILE' in str(exc))
        else:
            raise AssertionError('Bad extra file accepted')
        write('new_display.c', helper)
        check('compiler error recovers after restoring the same source', rows(frame())[0].startswith('FILE:'))

        # Relative includes inside subdirectories must not duplicate core files.
        (source_dir/'new_display.c').unlink()
        (source_dir/'new_display.h').unlink()
        write('ui/new_display.h', header.replace('"display.h"', '"../display.h"'))
        write('ui/new_display.c', helper)
        write('main.c', main_with_helper.replace('"new_display.h"', '"ui/new_display.h"'))
        nested = frame()
        check('nested C files and parent-relative local headers work', rows(nested)[0].startswith('FILE:') and 'ui/new_display.c' in nested['source_files'])

        # Commit the fixture to exercise discovery from a Git source too.
        subprocess.run(['git','init','-q',str(root)], check=True)
        subprocess.run(['git','-C',str(root),'-c','core.autocrlf=false','add','.'], check=True)
        subprocess.run(['git','-C',str(root),'-c','user.name=Fixture','-c','user.email=fixture@localhost','commit','-qm','Fixture'], check=True)
        branch = server.git('branch','--show-current')
        committed = server.frame({'source':['ref'],'ref':[branch],'page':['dsp_main']})
        check('extra-file discovery works from committed Git sources', rows(committed)[0].startswith('FILE:') and not committed['local'])
        write('ui/new_display.c', helper.replace('FILE:', 'LOCAL'))
        check('Git source ignores uncommitted file changes', rows(server.frame({'source':['ref'],'ref':[branch],'page':['dsp_main']}))[0].startswith('FILE:'))

        reset()
        conditional = order(text, names).replace('page_order[] = {', 'page_order[] = {\n#if 0\n&not_existing,\n#endif\n', 1)
        write('main.c', conditional)
        check('preprocessor conditions determine actual pages', frame()['pages']==names)

        reset()
        wrong_size = order(text, names+['dsp_FRO0']).replace('page_order[]','page_order[6]')
        write('main.c', wrong_size)
        try:
            frame()
        except ValueError as exc:
            check('inconsistent array capacity is rejected', 'Arraygroesse' in str(exc))
        else:
            raise AssertionError('Wrong page_order capacity silently accepted')

        reset()
        write('main.c', text+'\nvoid new_hardware_access(void) { unsupported_adc_read(); }\n')
        try:
            frame()
        except ValueError as exc:
            check('unsupported hardware produces an actionable error', 'unsupported_adc_read' in str(exc) and 'Host-Adapter' in str(exc))
        else:
            raise AssertionError('Unsupported hardware call accepted')

        reset()
        good = verify.run_suite(server)
        check('fixed vehicle expectations pass against baseline C', all(r['status']=='passed' for r in good['results']))
        # Break the actual IMD output; the test must fail without learning it.
        broken, replacements = re.subn(r'PORTA\s*\|=\s*\(1\s*<<\s*PA2\)', 'PORTA &= ~(1 << PA2)', baseline['candata.c'])
        assert replacements, 'IMD fixture mutation did not match'
        write('candata.c', broken)
        bad = verify.run_suite(server, test='imd')['results'][0]
        check('real wrong IMD output fails explicit expectation', bad['status']=='failed' and bad['checks'][0]['expected']==1)

    after = {str(p.relative_to(original)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in original.rglob('*') if p.is_file() and '.git' not in p.relative_to(original).parts}
    assert after==hashes, 'Original firmware changed'
    print(f'{count} source-edit and vehicle checks passed; original firmware unchanged.')


if __name__ == '__main__':
    main()
