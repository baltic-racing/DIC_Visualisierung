"""Raster/bit-order contract for the browser renderer; Node is optional tooling."""
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
node = os.environ.get('DIC_NODE') or shutil.which('node')
if not node:
    raise SystemExit('Bitte vorhandenes Node.js bereitstellen oder DIC_NODE setzen.')
js = r'''
const assert = require('assert'), vm = require('vm');
const context = {};
vm.createContext(context);
vm.runInContext(SOURCE, context);
const read = expr => JSON.parse(vm.runInContext('JSON.stringify('+expr+')', context));
assert.equal(read('lcdFont.size'), 95);
for (let code = 32; code < 127; code++) {
  const rows = read(`lcdGlyph(${code},[])`);
  assert.equal(rows.length, 8);
  assert(rows.every(row => Number.isInteger(row) && row >= 0 && row <= 31));
}
assert.deepStrictEqual(read('lcdGlyph(65,[])'), [14,17,17,31,17,17,17,0]);
assert.deepStrictEqual(read('lcdGlyph(48,[])'), [14,17,19,21,25,17,14,0]);
assert.deepStrictEqual(read('lcdGlyph(32,[])'), Array(8).fill(0));
assert.deepStrictEqual(read('lcdGlyph(255,[])'), Array(8).fill(31));
assert.deepStrictEqual(read('lcdGlyph(200,[])'), Array(8).fill(0));
const dots = [], labels = {}, ctx = {
  globalAlpha: 1, clearRect(){dots.length = 0;},
  fillRect(x,y,w,h){dots.push({x,y,w,h,alpha:this.globalAlpha});},
  fillText(){throw Error('A browser font must never replace the LCD raster');}
};
const canvas = {width:640, height:160, getContext(){return ctx;}, setAttribute(k,v){labels[k]=v;}};
const data = {rows:Array.from({length:4},()=>Array(20).fill(32)),glyphs:Array.from({length:8},()=>Array(8).fill(0))};
context.drawLcd(canvas,data,'#25351b');
assert.equal(dots.length,3200);assert(dots.every(d=>d.alpha===0.075));
assert.deepStrictEqual(labels['aria-label'].split('\n').map(r=>r.length),[20,20,20,20]);
data.rows[0][0] = 65;
context.drawLcd(canvas,data,'#25351b');
assert.deepStrictEqual(dots.filter(d=>d.alpha===1&&d.y===4).map(d=>d.x),[10,14,18]);
data.rows[0][0] = 0;data.glyphs[0] = [16,0,0,0,0,0,0,1];
const before = JSON.stringify(data);
context.drawLcd(canvas,data,'#25351b');
assert.equal(JSON.stringify(data),before,'Rendering must not mutate firmware bytes');
assert.deepStrictEqual(dots.filter(d=>d.alpha===1).map(({x,y})=>[x,y]),[[6,4],[22,32]]);
assert.equal(labels['aria-label'][0],'▧');
data.rows = Array.from({length:4},()=>Array(20).fill(255));
context.drawLcd(canvas,data,'#25351b');
assert.equal(dots.filter(d=>d.alpha===1).length,3200);
assert(dots.every(d=>d.x>=0&&d.y>=0&&d.x+d.w<=640&&d.y+d.h<=160));
assert.equal(ctx.globalAlpha,1);assert.equal(ctx.imageSmoothingEnabled,false);
console.log('PASS LCD: 95 ASCII rasters, fixed A/0 patterns, all 80 cells, 5×8 bit order, custom CGRAM, blank/full cells, boundaries, accessibility and read-only drawing.');
'''
result = subprocess.run([node, '-e', 'const SOURCE='+json.dumps((ROOT/'web/lcd.js').read_text())+';\n'+js], capture_output=True, text=True, timeout=20)
print(result.stdout, end='')
if result.returncode:
    raise SystemExit(result.stderr)
# All positions derive their dimensions from one declaration, including small screens.
css = (ROOT/'web/styles.css').read_text()
assert 'width:var(--led-size)' in css and 'height:var(--led-size)' in css
for selector in ('.side-leds .led', '.ams-bar .led', '.imd-lamp'):
    import re
    for rules in re.findall(re.escape(selector)+r'\s*\{([^}]+)\}',css):
        assert not re.search(r'(?<![-\w])(width|height|aspect-ratio|max-width|max-height)\s*:',rules),selector
print('PASS LED: one shared diameter for top, sides, AMS and IMD; no size overrides at small widths.')
