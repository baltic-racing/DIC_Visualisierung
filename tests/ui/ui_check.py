"""DOM/interaction regression tests using Node's built-in VM, no UI framework.

These use synthetic API responses; real C output is tested by the Python suites.
Node is a development/test tool only, never needed to start the simulator.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dic_visualisierung import server
from dic_visualisierung import verify
html = (ROOT/'web/index.html').read_text(encoding='utf-8')
scripts = re.search(r'<script>(.*?)</script>', html, re.S)[1].replace('__DIC_TOKEN__','test-token')
scripts += '\n' + (ROOT/'web/lcd.js').read_text(encoding='utf-8')
scripts += '\n' + (ROOT/'web/app.js').read_text(encoding='utf-8')
scripts += '\n' + (ROOT/'web/session.js').read_text(encoding='utf-8')
scripts += '\n' + (ROOT/'web/replay.js').read_text(encoding='utf-8')
scripts += '\n' + (ROOT/'web/profiles.js').read_text(encoding='utf-8')
scripts += '\n' + (ROOT/'web/tests.js').read_text(encoding='utf-8')
tags = re.findall(r'<([a-z][a-z0-9]*)\b([^>]*)>', html)
frame = dict(ok=True, fields=server.FIELDS, pages=['custom_home','custom_debug'],page='custom_home',
             source='fixture',branch='Fixture',revision='revision-1',compiled_at=100,active_page='custom_home',
             session=dict(time_ms=0,sys_time=0,status='paused',speed=1,next_input_ms=None,pending_events=0),
             rows=[[32]*20 for _ in range(4)],glyphs=[[0]*8 for _ in range(8)],notes='fixture',source_files=['main.c','extra.c'],
             state=dict(speed_valid=1,speed_kmh=34,APPS1=75,BPSF=42,BPSR=30,bms_max_temp=324,motor_temp=550),
             outputs=dict(ams_led=0,imd_led=0,bottom=[0]*6,top=[0]*15,left_rgb=[[0]*3]*2,right_rgb=[[0]*3]*2,tx=[0]*8))
javascript = r'''
const vm=require('vm'),assert=require('assert');
const intervals=[];const nodes=new Map(),accordions=[],storage=new Map([['dic.live.front','380']]),requests=[],blobs=new Map();let doc;
class Element{
 constructor(tag='div'){this.tag=tag;this.children=[];this.dataset={};this.events={};this.hidden=false;this.value='';this.style={setProperty(k,v){this[k]=v;}};this.invalid=false;this.width=640;this.height=160;this.files=[];}
 set id(v){this._id=v;nodes.set(v,this);}get id(){return this._id;}
 append(...items){for(const item of items){item.parentElement=this;this.children.push(item);}}
 replaceChildren(...items){this.children=[];this.append(...items);}
 addEventListener(type,fn){(this.events[type]||=[]).push(fn);}
 async fire(type,event={}){for(const fn of this.events[type]||[])await fn(event);}
 click(){return this.fire('click');}remove(){if(this.parentElement)this.parentElement.children=this.parentElement.children.filter(x=>x!==this);}
 setAttribute(name,value){this[name]=value;}checkValidity(){return !this.invalid;}
 getBoundingClientRect(){return {height:this.height};}
 getContext(){return {clearRect(){},fillRect(){},fillText(){}};}
 focus(){doc.activeElement=this;}scrollIntoView(){}
}
for(const [tag,attrs] of TAGS){const id=/\bid="([^"]+)"/.exec(attrs),acc=/data-accordion="([^"]+)"/.exec(attrs);if(id||acc){const el=new Element(tag);if(id)el.id=id[1];el.hidden=/\bhidden\b/.test(attrs);el.open=/\bopen\b/.test(attrs);if(acc){el.dataset.accordion=acc[1];accordions.push(el);}}}
nodes.get('source').value='auto';nodes.get('scenario').value='example';
let scenarioData=[{id:'fixture',name:'Fixture scenario',duration_ms:5000}];
let configured=false,compileError=false,profileData=[],profileId=0,failedTest=false,hold=false,release;
doc={body:new Element('body'),getElementById(id){assert(nodes.has(id),'Missing DOM ID '+id);return nodes.get(id);},createElement(tag){return new Element(tag);},createTextNode(text){return {text};},querySelectorAll(query){assert.equal(query,'[data-accordion]');return accordions;},activeElement:null};
const windowEvents={};
const context={document:doc,localStorage:{getItem(k){return storage.has(k)?storage.get(k):null;},setItem(k,v){storage.set(k,String(v));},removeItem(k){storage.delete(k);}},URLSearchParams,Map,Number,String,Boolean,Error,TypeError,Date,JSON,Blob,console,ResizeObserver:class {constructor(fn){this.callback=fn;}observe(el){el.height=1200;this.callback();}},setInterval(fn,ms){intervals.push(ms);},setTimeout(){},queueMicrotask,getComputedStyle(){return {color:'#c0d8b6'};},CustomEvent:class {constructor(type,options={}){this.type=type;this.detail=options.detail;}},URL:{createObjectURL(blob){blobs.set('test-blob',blob);return 'test-blob';},revokeObjectURL(){}},window:{addEventListener(type,fn){(windowEvents[type]||=[]).push(fn);},dispatchEvent(event){for(const fn of windowEvents[event.type]||[])fn(event);}},fetch:async(path,options)=>{
 requests.push({path,options});assert.equal(options.headers['X-DIC-Token'],'test-token');let data;const body=options.body?JSON.parse(options.body):{};
 if(path==='/api/config'){if(options.method==='POST')configured=true;data={configured,path:configured?'/fixture':'',refs:['Fixture','Other'],branch:'Fixture',commit:'abc',compiler:'clang',error:'',working_files:[]};}
 else if(path==='/api/scenarios'){if(body.action==='import')scenarioData.push({id:'imported',name:'Imported',duration_ms:100});data={ok:true,scenarios:scenarioData,selected:'imported',scenario:{format:'dic-scenario',version:1,name:'Fixture',duration_ms:100}};}
 else if(path==='/api/choose-folder')data={ok:true,path:'/fixture'};
 else if(path==='/api/profiles'){
  if(body.action==='create'||body.action==='import'){const value=body.action==='import'?body.profile:body;const item={id:String(++profileId),name:value.name,state:structuredClone(value.state)};profileData.push(item);data={selected:item.id};}
  if(body.action==='save')profileData.find(p=>p.id===body.id).state=structuredClone(body.state);
  if(body.action==='rename')profileData.find(p=>p.id===body.id).name=body.name;
  if(body.action==='delete')profileData=profileData.filter(p=>p.id!==body.id);
  data={ok:true,profiles:structuredClone(profileData),fields:FRAME.fields,selected:body.id,...data};
  if(body.action==='delete')data.selected=null;
 }
 else if(path==='/api/tests'){
  if(options.method==='POST'){const chosen=body.test==='all'?TESTS:TESTS.filter(t=>t.id===body.test);data={ok:true,revision:FRAME.revision,source:'fixture',results:chosen.map(t=>({id:t.id,name:t.name,status:failedTest?'failed':'passed',checks:[{label:'outputs.ams_led',expected:1,actual:failedTest?0:1,passed:!failedTest}]}))};}
  else data={ok:true,tests:TESTS};
 }
 else if(path.startsWith('/api/frame')||path==='/api/session'){
  if(body.action==='resume')FRAME.session.status='running';
  if(body.action==='pause')FRAME.session.status='paused';
  if(body.action==='step')FRAME.session.time_ms++;
  if(body.action==='advance')FRAME.session.time_ms=body.target_ms;
  if(body.action==='reset')FRAME.session.time_ms=0;
  if(hold){hold=false;await new Promise(r=>release=r);}
  if(compileError)return {ok:false,status:422,json:async()=>({ok:false,error:'Vorschau konnte nicht kompiliert werden. #error EXPECTED'})};
  const query=new URLSearchParams(body.query||path.split('?')[1]),wanted=query.get('page');data={...FRAME,page:FRAME.pages.includes(wanted)?wanted:FRAME.pages[0]};
 }else throw Error(path);
 return {ok:true,status:200,json:async()=>data};
}};
vm.createContext(context);vm.runInContext(SCRIPTS,context);context.window.dispatchEvent(new context.CustomEvent('DOMContentLoaded'));
const node=id=>nodes.get(id),tick=()=>new Promise(r=>setImmediate(r));async function settle(){for(let n=0;n<15;n++)await tick();}
const evaluate=code=>vm.runInContext(code,context);
(async()=>{
 await settle();assert.equal(node('workspace').style['--preview-height'],'1200px');assert(node('screen').hidden);assert.equal(node('front').value,380);assert.equal(node('tests-list').children.length,TESTS.length);
 await node('choose-folder').fire('click');await settle();assert(!node('screen').hidden);assert.equal(node('top-leds').children.length,15);assert.equal(node('ams-leds').children.length,6);assert.equal(node('left-leds').children.length,2);
 for(const field of FRAME.fields)assert(node(field.id),'Missing field '+field.id);
 assert.equal(node('signal-speed').textContent,'34 km/h');assert.equal(node('signal-throttle').textContent,'75 %');assert.equal(node('signal-battery').textContent,'32,4 °C');
 const manual=accordions.find(x=>x.dataset.accordion==='manual'),profiles=accordions.find(x=>x.dataset.accordion==='profiles');assert(!manual.open);assert(!profiles.open);
 const beforeSignals=requests.length;const oldFront=node('front').value;context.showVehicleSignals({...FRAME,state:{...FRAME.state,speed_kmh:65,BPSF:64}});assert.equal(node('signal-speed').textContent,'65 km/h');assert.equal(node('signal-front').textContent,64);assert.equal(node('front').value,oldFront);assert.equal(requests.length,beforeSignals,'Live readouts must not steer CAN or overwrite manual fields');
 const beforeMonitor=requests.length;
 const canFrame={...FRAME,traffic:{transport_dropped:0,can:{rx:[{can_id:0x204,dlc:1,data:[6],count:2,at_ms:21,age_ms:9,interval_ms:10,reason_text:''},{can_id:0x797,dlc:8,data:[0,0,0,0,0,0,2,138],count:3,at_ms:31,age_ms:0,interval_ms:10,reason_text:''}],tx:[{can_id:0x500,dlc:8,data:[0,0,0,0,0,0,0,3],count:1,at_ms:100,age_ms:0,interval_ms:null,reason_text:''}],drop:[]}}};
 context.displayFrame(canFrame);context.showCanMonitor(canFrame);
 assert.equal(node('can-table-body').children.length,2);assert.equal(node('can-table-body').children[0].children[0].textContent,'0x204');
 const shownBytes=node('can-table-body').children[0].children[2].children;
 assert.equal(shownBytes[0].textContent,'06');assert.equal(shownBytes[1].textContent,'—');assert.equal(shownBytes[1].dataset.missing,'true');
 const stableCanRow=node('can-table-body').children[0];canFrame.traffic.can.rx[0].age_ms=10;context.showCanMonitor(canFrame);assert.equal(node('can-table-body').children[0],stableCanRow,'Live updates must preserve row focus');await stableCanRow.fire('focus');assert(node('can-selected').textContent.includes('Alter 10 ms'));assert(node('can-selected').textContent.includes('Δ 10 ms'));
 node('can-filter').value='0x797';await node('can-filter').fire('input');assert.equal(node('can-table-body').children.length,1);assert.equal(node('can-table-body').children[0].children[0].textContent,'0x797');
 node('can-filter').value='';node('can-kind').value='tx';await node('can-kind').fire('change');assert.equal(node('can-table-body').children[0].children[0].textContent,'0x500');
 node('can-kind').value='drop';await node('can-kind').fire('change');assert.equal(node('can-table-body').children.length,0);
 context.showCanMonitor({...canFrame,traffic:{...canFrame.traffic,transport_dropped:3}});assert(node('can-monitor-status').textContent.includes('unvollständig'));
 assert.equal(requests.length,beforeMonitor,'CAN table observation and filters must not send control requests');
 node('can-kind').value='rx';context.displayFrame(FRAME);context.showCanMonitor(FRAME);
 for(const key of ['values','tests','source','help']){await node('tab-'+key).fire('click');assert(!node('panel-'+key).hidden);assert.equal(node('front').value,380);}
 await node('tab-help').fire('keydown',{key:'ArrowRight',preventDefault(){}});assert.equal(node('tab-values')['aria-selected'],'true');
 await node('tab-values').fire('keydown',{key:'ArrowLeft',preventDefault(){}});assert.equal(node('tab-help')['aria-selected'],'true');
 const acc=accordions.find(x=>x.dataset.accordion==='vehicle');acc.open=false;await acc.fire('toggle');assert.equal(storage.get('dic.ui.accordion.vehicle'),'false');
 assert(node('source-files').textContent.includes('extra.c'));assert.equal(node('page').children[0].textContent,'custom_home');
 node('raw').value='204: 06 00 00 00 00 00 00 00';node('ams_mode').value='2';node('gps_mode').value='1';node('profile-name').value='Training';
 await node('profile-new').fire('click');assert.equal(profileData.length,1);assert.equal(profileData[0].state.values.front,380);assert.equal(profileData[0].state.values.ams_mode,2);assert.equal(profileData[0].state.values.gps_mode,1);assert.equal(profileData[0].state.raw,node('raw').value);
 node('front').value='12';node('raw').value='';await node('profile-select').fire('change');await settle();assert.equal(node('front').value,'380');assert.equal(node('raw').value,'204: 06 00 00 00 00 00 00 00');
 node('front').value='99';await node('profile-save').fire('click');assert.equal(profileData[0].state.values.front,99);
 node('profile-name').value='Renamed';await node('profile-rename').fire('click');assert.equal(profileData[0].name,'Renamed');
 await node('profile-export').fire('click');const exported=JSON.parse(await blobs.get('test-blob').text());assert.equal(exported.format,'dic-simulation-profile');assert.equal(exported.state.values.front,99);
 await node('profile-delete').fire('click');assert.equal(profileData.length,0);assert.equal(node('front').value,'99');
 node('profile-file').files=[{size:100,text:async()=>JSON.stringify(exported)}];await node('profile-file').fire('change');await settle();assert.equal(profileData.length,1);assert.equal(node('front').value,'99');
 node('front').value='7';await context.loadProfiles();assert.equal(profileData.length,1);assert.equal(node('front').value,'7','Refreshing profile list must not discard unsaved inputs');
 const before=JSON.stringify(evaluate('profileState()'));await node('tests-all').fire('click');await settle();assert.equal(JSON.stringify(evaluate('profileState()')),before,'Tests changed example values');assert(node('tests-summary').textContent.includes('0 fehlgeschlagen'));assert(!node('tests-summary').textContent.includes('Quelle:'));assert(!node('tests-list').children.flatMap(card=>card.children).flatMap(child=>child.children||[]).some(x=>x.textContent?.includes('Quellstand:')));
 failedTest=true;await context.runTests('ams');assert(node('tests-list').children.some(card=>card.children.some(child=>child.textContent==='FEHLGESCHLAGEN')));assert(node('tests-list').children.flatMap(card=>card.children).flatMap(child=>child.children||[]).some(x=>x.textContent?.includes('Tatsächlich: 0')));
 FRAME.revision='revision-2';await context.refresh();assert(node('tests-context').textContent.includes('seit dem Testlauf geändert'));assert(node('tests-summary').textContent.includes('fehlgeschlagen'));assert(!node('tests-context').textContent.includes('revision-'));
 FRAME.pages=['dsp_main','dsp_debug','dsp_reduced','new_page'];await context.refresh();assert.deepEqual(node('page').children.map(p=>p.textContent),['Hauptanzeige','Debug','Reduziert','new_page']);assert.deepEqual(node('page').children.map(p=>p.value),FRAME.pages);
 assert.equal(evaluate("sourceLabel('Arbeitsordner · TY26_Test · gespeicherte Dateien')"),'Lokale Dateien · TY26_Test');assert.equal(evaluate("sourceLabel('origin/TY26_Test · abc1234 · lokal gespeicherter Git-Stand')"),'origin/TY26_Test · gespeicherter Git-Stand');
 FRAME.pages=['renamed_only'];await context.refresh();assert.equal(node('page').value,'renamed_only');assert.equal(storage.get('dic.live.page'),'renamed_only');
 compileError=true;await context.refresh();assert(node('screen').hidden);assert(!node('error-notice').hidden);compileError=false;await context.refresh();assert(!node('screen').hidden);
 hold=true;const pending=context.refresh();await tick();node('front').value='23';await node('front').fire('change');assert(!node('screen').hidden);release();await pending;await settle();assert.equal(JSON.parse(requests.filter(r=>r.path==='/api/session'&&JSON.parse(r.options.body).action==='inputs').at(-1).options.body).query.front,'23');
 for(const code of [1,6,9,22]){context.showOutputs({...FRAME.outputs,ams_diagnostic_code:code,ams_diagnostic_valid:1});assert(node('ams-leds').children.every(x=>x.dataset.on==='false'));assert(!node('diagnostic-warning').hidden);}context.showOutputs({...FRAME.outputs,bottom:[1,1,1,1,1,1],ams_led:1});assert(node('ams-leds').children.every(x=>x.dataset.on==='true'));context.showOutputs({...FRAME.outputs,ams_diagnostic_code:0,ams_diagnostic_valid:1});assert(node('ams-leds').children.every(x=>x.dataset.on==='false'));
 await node('session-start').fire('click');assert.equal(node('session-status').textContent,'Läuft');await node('session-pause').fire('click');assert.equal(node('session-status').textContent,'Pausiert');assert(!node('session-step'));assert(!node('session-clock'));assert(intervals.includes(50));node('session-target').value='15000';await node('session-advance').fire('click');assert(node('virtual-time').textContent.includes('15,000'));await node('session-reset').fire('click');assert(node('virtual-time').textContent.includes('0,000'));
 assert(!node('session-speed'),'Playback speed selector was removed');
 for(const [ms,text] of [[0,'0,000 s'],[59999,'59,999 s'],[60000,'1 min 00,000 s'],[61234,'1 min 01,234 s'],[119999,'1 min 59,999 s'],[120000,'2 min 00,000 s'],[600000,'10 min 00,000 s']]){
  assert.equal(context.formatSimulationTime(ms),text);
  context.showSession({...FRAME,session:{...FRAME.session,time_ms:ms}});
  assert.equal(node('virtual-time').textContent,text);
 }
 const requestCount=requests.length;node('view-mode').value='buffer';await node('view-mode').fire('change');assert.equal(requests.length,requestCount,'Local buffer view must not send a CAN input');assert(!node('inspect-controls').hidden);
 const inputCount=()=>requests.filter(r=>r.path==='/api/session'&&JSON.parse(r.options.body).action==='inputs').length;const beforeInspect=inputCount();node('inspect-page').value='renamed_only';await node('inspect-page').fire('change');assert.equal(inputCount(),beforeInspect,'Inspecting a page must not change SWC');
 await node('replay-json').fire('click');node('replay-file').files=[{name:'test.json',size:100,text:async()=>JSON.stringify({format:'dic-scenario',version:1})}];await node('replay-file').fire('change');assert.equal(node('replay-select').value,'imported');await node('replay-export').fire('click');assert.equal(JSON.parse(await blobs.get('test-blob').text()).format,'dic-scenario');await node('replay-apply').fire('click');assert(requests.some(r=>r.path==='/api/session'&&JSON.parse(r.options.body).action==='scenario'));
 FRAME.input_state={values:Object.fromEntries(FRAME.fields.map(f=>[f.id,f.default])),raw:'',page:'renamed_only',scenario:'example'};FRAME.input_state.values.front=88;FRAME.session.id='existing-session';FRAME.session.selection={source:node('source').value,ref:node('git-ref').value,scenario:'example'};evaluate("sessionAttached=false;sentInputs=''");const beforeAttach=inputCount();await context.refresh();await settle();assert.equal(node('front').value,'88');assert.equal(inputCount(),beforeAttach,'Reopening browser must attach without posting input changes');
 console.log('PASS UI: minute timer boundaries and removed playback selector, compact one-row CAN matrix, stable keyboard focus and timing details, ID/filter/direction/DLC/bytes/loss, compact scenario/manual/profile sections, independent live C readouts, 50 ms read-only observation, simplified session controls, read-only attach to existing session, scenario import/export/select, observation without CAN steering, persistent-session controls, GPIO/diagnostic separation, friendly/dynamic page labels, readable source labels, large result summary and stale warnings, four tabs/keyboard, all controls/LEDs, profiles create/load/save/rename/delete/reload/export/import, tests preserve inputs and show actual/expected failures, stale test status, dynamic pages, compiler recovery and input races.');
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
node = os.environ.get('DIC_NODE') or shutil.which('node')
if not node:
    raise SystemExit('Für diese optionalen UI-Tests wird Node.js benötigt (oder DIC_NODE setzen).')
prefix = 'const SCRIPTS='+json.dumps(scripts)+';const FRAME='+json.dumps(frame)+';const TAGS='+json.dumps(tags)+';const TESTS='+json.dumps(verify.catalog())+';\n'
subprocess.run([node], input=prefix+javascript, text=True, check=True)
