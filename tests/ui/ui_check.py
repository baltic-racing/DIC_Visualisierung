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
# Screen order is part of this UI change, independent of simulated API responses.
positions=[html.index(marker) for marker in ['class="run-picker"','class="accordion live-signals-panel"','class="accordion can-monitor"','id="manual-values"','data-accordion="diagnostics"','class="profile-panel"']]
assert positions==sorted(positions),'Panels must be scenarios, received values, CAN, values, diagnostics, profiles'
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
 constructor(tag='div'){this.tag=tag;this.children=[];this.dataset={};this.events={};this.hidden=false;this.checked=false;this.value='';this.style={setProperty(k,v){this[k]=v;}};this.invalid=false;this.width=640;this.height=160;this.files=[];}
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
const descendants=el=>el.children.flatMap(child=>[child,...descendants(child)]);
const node=id=>nodes.get(id),tick=()=>new Promise(r=>setImmediate(r));async function settle(){for(let n=0;n<15;n++)await tick();}
const evaluate=code=>vm.runInContext(code,context);
(async()=>{
 await settle();assert.equal(node('workspace').style['--preview-height'],'1200px');assert(node('screen').hidden);assert.equal(node('front').value,380);assert.equal(node('tests-list').children.length,TESTS.length);
 await node('choose-folder').fire('click');await settle();assert(!node('screen').hidden);assert.equal(node('top-leds').children.length,15);assert.equal(node('ams-leds').children.length,6);assert.equal(node('left-leds').children.length,2);
 for(const field of FRAME.fields)assert(node(field.id),'Missing field '+field.id);
 assert.equal(node('signal-speed').textContent,'34 km/h');assert.equal(node('signal-throttle').textContent,'75 %');assert.equal(node('signal-battery').textContent,'32,4 °C');
 const advanced=accordions.find(x=>x.dataset.accordion==='advanced-inputs');assert(!advanced.open);assert(!node('profile-tools').open);
 assert.equal(node('front').parentElement.parentElement.id,'fields-vehicle');assert.equal(node('accu').parentElement.parentElement.id,'fields-battery');assert.equal(node('ams_error').parentElement.parentElement.id,'fields-errors');
 assert.equal(node('ams_sender').parentElement.parentElement.id,'fields-model');assert.equal(node('ams_thermal').parentElement.parentElement.id,'fields-model');assert.equal(node('diag').parentElement.parentElement.id,'fields-can');assert.equal(node('apps2').parentElement.parentElement.id,'fields-extra');
 assert(node('session-notice').hidden);assert(node('profile-message').hidden);assert(node('replay-message').hidden);
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
 const acc=accordions.find(x=>x.dataset.accordion==='advanced-inputs');acc.open=true;await acc.fire('toggle');assert.equal(storage.get('dic.ui.accordion.advanced-inputs'),'true');
 assert(node('source-files').textContent.includes('extra.c'));assert.equal(node('page').children[0].textContent,'custom_home');
 const primaryItems=[{id:'normal.scenario',name:'Normalbetrieb'},{id:'ams-temperature.scenario',name:'Akku wird heiß'},{id:'can-loss.scenario',name:'CAN-Ausfall'},{id:'ams-delayed.scenario',name:'PEC demo'},{id:'fs-endurance.scenario',name:'Endurance'},{id:'bispingen.scenario',name:'Bispingen'},{id:'custom',name:'Mein Ablauf'}];
 const beforeChoices=requests.length;context.scenarioOptions(primaryItems,'');
 assert.deepEqual(node('replay-select').children.filter(x=>x.tag==='optgroup').map(x=>x.label),['Tests & Fehler','Simulationen','Eigene Abläufe']);
 assert.deepEqual(descendants(node('replay-select')).filter(x=>x.tag==='option').map(x=>x.value),['','normal.scenario','ams-temperature.scenario','can-loss.scenario','ams-delayed.scenario','fs-endurance.scenario','bispingen.scenario','custom']);
 assert(!node('replay-more'),'Scenario toggle must be removed');
 context.scenarioOptions(primaryItems,'ams-delayed.scenario');assert.equal(node('replay-select').value,'ams-delayed.scenario','Rebuilding groups preserves historical scenario selection');
 context.scenarioOptions(primaryItems,'custom');assert.equal(node('replay-select').value,'custom');
 assert.equal(requests.length,beforeChoices,'Grouping scenarios must not reset or steer firmware');
 const manual=node('manual-values'),received=accordions.find(x=>x.dataset.accordion==='received-values');assert(manual.open);assert(received.open);
 const beforeFold=requests.length,originalValues=JSON.stringify(evaluate('profileState()'));
 manual.open=false;await manual.fire('toggle');assert.equal(storage.get('dic.ui.accordion.manual-values'),'false');assert.equal(JSON.stringify(evaluate('profileState()')),originalValues);assert.equal(requests.length,beforeFold,'Folding values must not change or send inputs');manual.open=true;await manual.fire('toggle');
 context.scenarioOptions(scenarioData,'');
 node('profile-name').value='';await node('profile-new').fire('click');assert(node('profile-tools').open);assert.equal(doc.activeElement,node('profile-name'));assert.equal(profileData.length,0,'Opening profile name must not overwrite profiles');
 node('raw').value='204: 06 00 00 00 00 00 00 00';node('ams_mode').value='2';node('gps_mode').value='1';node('profile-name').value='Training';
 await node('profile-new').fire('click');assert.equal(profileData.length,1);assert.equal(profileData[0].state.values.front,380);assert.equal(profileData[0].state.values.ams_mode,2);assert.equal(profileData[0].state.values.gps_mode,1);assert.equal(profileData[0].state.raw,node('raw').value);
 assert.deepEqual(Object.keys(profileData[0].state.values).sort(),FRAME.fields.map(f=>f.id).sort(),'Profiles retain every advanced value');
 node('front').value='12';node('raw').value='';await node('profile-select').fire('change');await settle();assert.equal(node('front').value,'380');assert.equal(node('raw').value,'204: 06 00 00 00 00 00 00 00');
 node('front').value='99';await node('profile-save').fire('click');assert.equal(profileData[0].state.values.front,99);
 node('profile-name').value='Renamed';await node('profile-rename').fire('click');assert.equal(profileData[0].name,'Renamed');
 await node('profile-export').fire('click');const exported=JSON.parse(await blobs.get('test-blob').text());assert.equal(exported.format,'dic-simulation-profile');assert.equal(exported.state.values.front,99);
 await node('profile-delete').fire('click');assert.equal(profileData.length,0);assert.equal(node('front').value,'99');
 node('profile-file').files=[{size:100,text:async()=>JSON.stringify(exported)}];await node('profile-file').fire('change');await settle();assert.equal(profileData.length,1);assert.equal(node('front').value,'99');
 node('front').value='7';await context.loadProfiles();assert.equal(profileData.length,1);assert.equal(node('front').value,'7','Refreshing profile list must not discard unsaved inputs');
 const before=JSON.stringify(evaluate('profileState()'));await node('tests-all').fire('click');await settle();assert.equal(JSON.stringify(evaluate('profileState()')),before,'Tests changed example values');assert(node('tests-summary').textContent.includes('0 fehlgeschlagen'));assert(!node('tests-summary').textContent.includes('Quelle:'));assert(!descendants(node('tests-list')).some(x=>x.textContent?.includes('Quellstand:')));
 assert(evaluate('[...testCards.values()].every(card=>card.details.open===false)'),'Successful test details stay closed');
 failedTest=true;await context.runTests('ams');assert(node('tests-list').children.some(card=>card.children.some(child=>child.textContent==='FEHLGESCHLAGEN')));assert(evaluate("testCards.get('ams').details.open"),'Failed test opens actual/expected details');assert(descendants(node('tests-list')).some(x=>x.textContent?.includes('Tatsächlich: 0')));
 FRAME.revision='revision-2';await context.refresh();assert(node('tests-context').textContent.includes('seit dem Testlauf geändert'));assert(node('tests-summary').textContent.includes('fehlgeschlagen'));assert(!node('tests-context').textContent.includes('revision-'));
 FRAME.pages=['dsp_main','dsp_debug','dsp_reduced','new_page'];await context.refresh();assert.deepEqual(node('page').children.map(p=>p.textContent),['Hauptanzeige','Debug','Reduziert','new_page']);assert.deepEqual(node('page').children.map(p=>p.value),FRAME.pages);
 assert.equal(evaluate("sourceLabel('Arbeitsordner · TY26_Test · gespeicherte Dateien')"),'Lokale Dateien · TY26_Test');assert.equal(evaluate("sourceLabel('origin/TY26_Test · abc1234 · lokal gespeicherter Git-Stand')"),'origin/TY26_Test · gespeicherter Git-Stand');
 FRAME.pages=['renamed_only'];await context.refresh();assert.equal(node('page').value,'renamed_only');assert.equal(storage.get('dic.live.page'),'renamed_only');
 compileError=true;await context.refresh();assert(node('screen').hidden);assert(!node('error-notice').hidden);compileError=false;await context.refresh();assert(!node('screen').hidden);
 hold=true;const pending=context.refresh();await tick();node('front').value='23';await node('front').fire('change');assert(!node('screen').hidden);release();await pending;await settle();assert.equal(JSON.parse(requests.filter(r=>r.path==='/api/session'&&JSON.parse(r.options.body).action==='inputs').at(-1).options.body).query.front,'23');
 for(const code of [1,6,9,22]){context.showOutputs({...FRAME.outputs,ams_diagnostic_code:code,ams_diagnostic_valid:1});assert(node('ams-leds').children.every(x=>x.dataset.on==='false'));assert(!node('diagnostic-warning').hidden);}context.showOutputs({...FRAME.outputs,bottom:[1,1,1,1,1,1],ams_led:1});assert(node('ams-leds').children.every(x=>x.dataset.on==='true'));context.showOutputs({...FRAME.outputs,ams_diagnostic_code:0,ams_diagnostic_valid:1});assert(node('ams-leds').children.every(x=>x.dataset.on==='false'));
 context.displayFrame({...FRAME,ams_sender:{kind:'ams-ty26-subset-v1'}});
 context.showOutputs({...FRAME.outputs,ams_diagnostic_code:0,ams_diagnostic_valid:0});assert(node('diagnostic-warning').hidden,'Missing 0x204 is expected for AMS TY26');assert(node('ams-leds').children.every(x=>x.dataset.on==='false'));
 context.showVehicleSignals({...FRAME,ams_sender:{kind:'ams-ty26-subset-v1',thermal_enabled:true,overtemperature_latched:true}});assert(node('ams-model-status').textContent.includes('Übertemperatur gespeichert'));
 context.displayFrame({...FRAME,ams_sender:{kind:'ams-ty26-subset-v1'},traffic:{can:{rx:[{can_id:0x204}]}}});context.showOutputs({...FRAME.outputs,ams_diagnostic_code:255,ams_diagnostic_valid:0});assert(!node('diagnostic-warning').hidden,'Received invalid diagnosis stays visible');
 context.displayFrame(FRAME);

 await node('session-start').fire('click');assert.equal(node('session-status').textContent,'Läuft');await node('session-pause').fire('click');assert.equal(node('session-status').textContent,'Pausiert');assert(!node('session-step'));assert(!node('session-clock'));assert(intervals.includes(50));node('session-target').value='15000';await node('session-advance').fire('click');assert(node('virtual-time').textContent.includes('15,000'));await node('session-reset').fire('click');assert(node('virtual-time').textContent.includes('0,000'));
 assert(!node('session-speed'),'Playback speed selector was removed');
 for(const [ms,text] of [[0,'0,000 s'],[59999,'59,999 s'],[60000,'1 min 00,000 s'],[61234,'1 min 01,234 s'],[119999,'1 min 59,999 s'],[120000,'2 min 00,000 s'],[600000,'10 min 00,000 s']]){
  assert.equal(context.formatSimulationTime(ms),text);
  context.showSession({...FRAME,session:{...FRAME.session,time_ms:ms}});
  assert.equal(node('virtual-time').textContent,text);
 }
 const oracleFrame={...FRAME,session:{...FRAME.session,id:'oracle'},replay:{name:'Oracle',checks:[{passed:true,at_ms:10,path:'outputs.ams_led',expected:0,actual:0}],tx:{},duration_ms:100}};
 context.showReplay(oracleFrame);assert(node('replay-check-summary').textContent.includes('1 bestanden'));assert(!node('replay-check-details').open);
 oracleFrame.replay.checks[0]={passed:false,at_ms:10,path:'outputs.ams_led',expected:1,actual:0};context.showReplay(oracleFrame);assert(node('replay-check-details').open);assert(node('replay-checks').textContent.includes('Tatsächlich: 0'));
 node('replay-check-details').open=false;context.showReplay(oracleFrame);assert(!node('replay-check-details').open,'Polling must not reopen dismissed details');
 const historyFrame={...FRAME,session:{...FRAME.session,id:'long-history'},replay:{name:'History',duration_ms:501,finished:true,
  checks:Array.from({length:50},(_,i)=>({passed:true,at_ms:452+i,path:'time_ms',expected:452+i,actual:452+i})),
  check_summary:{total:501,passed:500,failed:1,pending:0},
  earlier_failure:{passed:false,at_ms:1,path:'time_ms',expected:999,actual:1},tx:{}}};
 context.showReplay(historyFrame);
 assert(node('replay-check-summary').textContent.includes('500 bestanden · 1 fehlgeschlagen'));
 assert.equal(node('replay-check-summary').dataset.tone,'bad');
 assert(node('replay-check-details').open);assert(!node('replay-check-details').hidden);
 assert(node('replay-checks').textContent.includes('Früherer Fehlschlag'));
 assert(node('replay-checks').textContent.includes('Erwartet: 999\nTatsächlich: 1'));
 node('replay-check-details').open=false;context.showReplay(historyFrame);
 assert.equal(node('replay-check-summary').dataset.tone,'bad');
 assert(!node('replay-check-details').open,'Polling keeps earlier errors without reopening dismissed details');
 historyFrame.replay.check_summary={total:502,passed:500,failed:1,pending:1};historyFrame.replay.finished=false;
 context.showReplay(historyFrame);assert(node('replay-check-summary').textContent.includes('1 offen'));
 historyFrame.session.id='reset-history';historyFrame.replay.checks=[];historyFrame.replay.earlier_failure=null;
 historyFrame.replay.check_summary={total:501,passed:0,failed:0,pending:501};
 context.showReplay(historyFrame);assert.equal(node('replay-check-summary').dataset.tone,'pending');
 assert(node('replay-check-summary').textContent.includes('501 offen'));
 assert(!node('replay-checks').textContent.includes('Erwartet: 999'));
 historyFrame.replay.check_summary={total:501,passed:501,failed:0,pending:0};historyFrame.replay.finished=true;
 context.showReplay(historyFrame);assert.equal(node('replay-check-summary').dataset.tone,'good');
 assert(node('replay-check-summary').textContent.includes('501 bestanden'));
 historyFrame.replay.check_summary={total:502,passed:501,failed:0,pending:1};
 context.showReplay(historyFrame);assert.equal(node('replay-check-summary').dataset.tone,'pending','Incomplete checks cannot turn green');
 historyFrame.replay.check_summary={total:0,passed:0,failed:0,pending:0};historyFrame.replay.tx={configured:true,passed:1,failed:0,pending:1};
 context.showReplay(historyFrame);assert.equal(node('replay-check-summary').dataset.tone,'pending','Pending TX cannot turn green');
 historyFrame.replay.tx={configured:true,passed:1,failed:1,pending:0};
 context.showReplay(historyFrame);assert.equal(node('replay-check-summary').dataset.tone,'bad','TX failures stay red');
 historyFrame.replay.tx={configured:true,passed:2,failed:0,pending:0};
 context.showReplay(historyFrame);assert.equal(node('replay-check-summary').dataset.tone,'good');
 historyFrame.replay.tx.incomplete_history=true;
 context.showReplay(historyFrame);assert.equal(node('replay-check-summary').dataset.tone,'bad','Lost TX history cannot turn green');
 context.showSession({...FRAME,session:{...FRAME.session,generation:2,notice:'Firmware-Quelldateien oder Branch geändert; bisherige Sitzung beendet.'}});assert(!node('session-notice').hidden,'Source resets must remain explicit');
 const requestCount=requests.length;node('view-mode').value='buffer';await node('view-mode').fire('change');assert.equal(requests.length,requestCount,'Local buffer view must not send a CAN input');assert(!node('inspect-controls').hidden);assert(!node('buffer-view-warning').hidden);
 const inputCount=()=>requests.filter(r=>r.path==='/api/session'&&JSON.parse(r.options.body).action==='inputs').length;const beforeInspect=inputCount();node('inspect-page').value='renamed_only';await node('inspect-page').fire('change');assert.equal(inputCount(),beforeInspect,'Inspecting a page must not change SWC');
 await node('replay-json').fire('click');node('replay-file').files=[{name:'test.json',size:100,text:async()=>JSON.stringify({format:'dic-scenario',version:1})}];await node('replay-file').fire('change');assert.equal(node('replay-select').value,'imported');await node('replay-export').fire('click');assert.equal(JSON.parse(await blobs.get('test-blob').text()).format,'dic-scenario');await node('replay-apply').fire('click');assert(requests.some(r=>r.path==='/api/session'&&JSON.parse(r.options.body).action==='scenario'));
 FRAME.input_state={values:Object.fromEntries(FRAME.fields.map(f=>[f.id,f.default])),raw:'',page:'renamed_only',scenario:'example'};FRAME.input_state.values.front=88;FRAME.session.id='existing-session';FRAME.session.selection={source:node('source').value,ref:node('git-ref').value,scenario:'example'};evaluate("sessionAttached=false;sentInputs=''");const beforeAttach=inputCount();await context.refresh();await settle();assert.equal(node('front').value,'88');assert.equal(inputCount(),beforeAttach,'Reopening browser must attach without posting input changes');
 console.log('PASS UI: simplified everyday/advanced placement, grouped scenarios including imports/legacy without resets, collapsible values preserve all inputs, profile options preserve all inputs, collapsed success and expanded failure details, source-reset notices, buffer-view warning, minute timer boundaries and removed playback selector, compact one-row CAN matrix, stable keyboard focus and timing details, ID/filter/direction/DLC/bytes/loss, compact scenario/manual/profile sections, independent live C readouts, 50 ms read-only observation, simplified session controls, read-only attach to existing session, scenario import/export/select, observation without CAN steering, persistent-session controls, GPIO/diagnostic separation, friendly/dynamic page labels, readable source labels, large result summary and stale warnings, four tabs/keyboard, all controls/LEDs, profiles create/load/save/rename/delete/reload/export/import, tests preserve inputs and show actual/expected failures, stale test status, dynamic pages, compiler recovery and input races.');
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
node = os.environ.get('DIC_NODE') or shutil.which('node')
if not node:
    raise SystemExit('Für diese optionalen UI-Tests wird Node.js benötigt (oder DIC_NODE setzen).')
prefix = 'const SCRIPTS='+json.dumps(scripts)+';const FRAME='+json.dumps(frame)+';const TAGS='+json.dumps(tags)+';const TESTS='+json.dumps(verify.catalog())+';\n'
subprocess.run([node], input=prefix+javascript, text=True, check=True)
