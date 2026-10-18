// Main UI: status, source setup, field controls and LCD drawing.
const $=id=>document.getElementById(id);
const controls=['source','page','scenario'];
const pageLabels={dsp_startup:'Start',dsp_main:'Hauptanzeige',dsp_debug:'Debug',dsp_SDCI:'SDC-Status',dsp_reduced:'Reduziert',dsp_modes:'Moduswahl',dsp_FRO0:'Sicherungen A',dsp_FRO1:'Sicherungen B'};
function sourceLabel(label){return String(label||'').replace(/^Arbeitsordner · /,'Lokale Dateien · ').replace(/ · gespeicherte Dateien$/,'').replace(/ · [0-9a-f]{7,40} · lokal gespeicherter Git-Stand$/,' · gespeicherter Git-Stand');}
const tabKeys=['values','tests','source','help'];
const fieldGroups={vehicle:['front','rear','apps1','apps2','steering','speed'],battery:['ts','accu','precharge','ts_ready','soc','current','inv0','inv1','motor0','motor1','lv','cooling'],errors:['ams_error','imd_error','diag'],can:['gps_mode','diag_mode','ams_mode','can_ok'],fuse:['fan','fuse','sdc15','sdc14','sdc13','sdc12','sdc11','sdc8','sdc7','sdc6'],controls:['ts_button','r2d_button','mode','buttons','duration']};
let busy=false,revision='',selected=localStorage.getItem('dic.live.page')||'',fieldSchema=[],configured=false,configTicks=0;
let configData=null,configOnline=false,simulationState='pending',lastSimulation=0,lastBuild=0,lastError='',requestVersion=0,needsRefresh=false,activeTab='values',firstConfig=true,hasPreview=false,lastSessionId='',lastSessionTime=-1;
function setTab(name,focus=false){if(!tabKeys.includes(name))name='values';activeTab=name;for(const key of tabKeys){const tab=$('tab-'+key);tab.setAttribute('aria-selected',String(key===name));tab.tabIndex=key===name?0:-1;$('panel-'+key).hidden=key!==name;}$('settings-scroll').scrollTop=0;localStorage.setItem('dic.ui.tab',name);if(focus)$('tab-'+name).focus();}
for(const key of tabKeys){$('tab-'+key).addEventListener('click',()=>setTab(key));$('tab-'+key).addEventListener('keydown',e=>{const keys=tabKeys,i=keys.indexOf(key);let next;if(e.key==='ArrowRight')next=keys[(i+1)%keys.length];if(e.key==='ArrowLeft')next=keys[(i+keys.length-1)%keys.length];if(e.key==='Home')next=keys[0];if(e.key==='End')next=keys[keys.length-1];if(next){e.preventDefault();setTab(next,true);}});}
setTab(localStorage.getItem('dic.ui.tab')||'values');
for(const section of document.querySelectorAll('[data-accordion]')){const key='dic.ui.accordion.'+section.dataset.accordion,saved=localStorage.getItem(key);if(saved!==null)section.open=saved==='true';section.addEventListener('toggle',()=>localStorage.setItem(key,String(section.open)));}
for(const id of ['open-source-empty','open-source-error'])$(id).addEventListener('click',()=>{setTab('source',true);if(lastError){$('error-details').open=true;$('error-notice').scrollIntoView({block:'nearest'});}});
function chosenStand(){if($('source').value==='test')return 'origin/TY26_Test';if($('source').value==='ref')return $('git-ref').value||'—';return configData?.branch||'Arbeitsdateien';}
function updateStatus(){
 let tone='pending',title='Simulation wird vorbereitet',short='Vorschau wird aktualisiert';
 if(!configOnline){tone='bad';title='Nicht verbunden – lokaler Server nicht erreichbar';short='Keine aktuelle Verbindung';}
 else if(!configured){tone='bad';title='Nicht verbunden – Firmware-Verzeichnis auswählen';short='Firmware-Verzeichnis fehlt';}
 else if(simulationState==='success'){tone='good';title='Verbunden – Firmware erkannt';short='✓ Aktuell';}
 else if(simulationState==='compile-error'){tone='warn';title='Kompilierung fehlgeschlagen';short='⚠ Kompilierung fehlgeschlagen';}
 else if(simulationState==='input-error'){tone='warn';title='Eingaben prüfen';short='Keine aktuelle Simulation – Eingaben prüfen';}
 else if(simulationState==='error'){tone='warn';title='Simulation nicht verfügbar';short='⚠ Simulation fehlgeschlagen';}
 $('status').dataset.tone=tone;$('status-text').textContent=title;
 $('preview-status').dataset.tone=tone;$('preview-status').textContent=short;
 $('summary-branch').textContent=chosenStand();
 $('open-source-error').hidden=!lastError;
 $('summary-time').textContent=lastSimulation?(Date.now()-lastSimulation<1000?'Gerade eben':`vor ${Math.floor((Date.now()-lastSimulation)/1000)} Sekunden`):'—';
 const show=configOnline&&configured&&hasPreview&&(simulationState==='success'||simulationState==='pending');$('screen').hidden=!show;$('empty-preview').hidden=show;
 $('empty-title').textContent=!configured?'Firmware auswählen':simulationState==='pending'?'Vorschau wird aktualisiert':'Keine aktuelle Vorschau';
 $('empty-description').textContent=!configured?'Wähle unter „Quelle“ den Ordner deines Firmware-Repositories.':simulationState==='pending'?'Die aktuelle Codequelle und deine Eingaben werden geprüft.':'Die letzte Anzeige wird nicht als aktueller Stand gezeigt. Details findest du unter „Quelle“.';
}
function invalidate({resetPreview=false}={}){if(resetPreview)hasPreview=false;requestVersion++;needsRefresh=true;simulationState='pending';lastError='';$('error-notice').hidden=true;updateStatus();}
async function api(path,body){const response=await fetch(path,{method:body===undefined?'GET':'POST',headers:{'X-DIC-Token':sessionToken,...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body),cache:'no-store'});const data=await response.json();if(!response.ok||data.ok===false){const error=Error(data.error||'Lokale Anfrage fehlgeschlagen');error.status=response.status;throw error;}return data;}
function applyConfig(data){
 const previous=configData;configData=data;configOnline=true;configured=data.configured;
 if(previous&&(previous.path!==data.path||previous.branch!==data.branch||previous.configured!==data.configured))invalidate({resetPreview:true});
 if(document.activeElement!==$('firmware-path'))$('firmware-path').value=data.path;
 $('config-status').textContent=configured?'Verzeichnis erkannt. Gespeicherte Dateien werden ausschließlich gelesen.':'Wähle den Repository-Ordner mit dem Unterordner DIC_23.';
 $('config-error').hidden=!data.error;$('config-error').textContent=data.error||'';
 $('git-branch').textContent=data.branch||'Nicht verfügbar';
 $('git-files').textContent=data.working_files===null||data.working_files===undefined?'Git-Dateistatus nicht verfügbar':data.working_files.length?`${data.working_files.length} geänderte versionierte Datei(en)`:'Keine Änderungen an versionierten Dateien';
 $('compiler-name').textContent=data.compiler||'Nicht verfügbar';
 const options=data.refs.join('|');if($('git-ref').dataset.options!==options){const selectedRef=$('git-ref').value||localStorage.getItem('dic.live.ref');$('git-ref').replaceChildren(...data.refs.map(ref=>{const o=document.createElement('option');o.value=ref;o.textContent=ref;return o;}));if(data.refs.includes(selectedRef))$('git-ref').value=selectedRef;$('git-ref').dataset.options=options;}
 $('ref-label').hidden=$('source').value!=='ref';
 if(firstConfig){firstConfig=false;if(!configured||data.error)setTab('source');}
 updateSourceNotice();updateStatus();
}
function updateSourceNotice(){$('notice').textContent=['auto','local'].includes($('source').value)?'Verwendet gespeicherte Arbeitsdateien einschließlich uncommitteter Änderungen. Branchwechsel werden automatisch übernommen.':'Verwendet committete Dateien des ausgewählten, lokal gespeicherten Git-Stands. Keine uncommitteten Änderungen und kein automatischer Fetch.';}
async function loadConfig(){try{applyConfig(await api('/api/config'));}catch(e){configOnline=false;$('config-error').hidden=false;$('config-error').textContent=e.message;updateStatus();}}
async function saveFolder(path){try{applyConfig(await api('/api/config',{path}));invalidate();await refresh();}catch(e){$('config-error').hidden=false;$('config-error').textContent=e.message;}}
$('save-folder').addEventListener('click',()=>saveFolder($('firmware-path').value));
$('choose-folder').addEventListener('click',async()=>{const button=$('choose-folder');button.disabled=true;$('config-status').textContent='Ordnerdialog geöffnet. Wähle dein Firmware-Repository.';try{const data=await api('/api/choose-folder',{});if(data.path)await saveFolder(data.path);else await loadConfig();}catch(e){$('config-error').hidden=false;$('config-error').textContent=e.message;}finally{button.disabled=false;}});
$('git-ref').addEventListener('change',()=>{localStorage.setItem('dic.live.ref',$('git-ref').value);invalidate({resetPreview:true});refresh();});
for(const id of controls){const saved=localStorage.getItem('dic.live.'+id);if(saved!==null&&id!=='page')$(id).value=saved;$(id).addEventListener('change',()=>{if(id==='page')selected=$('page').value;$('ref-label').hidden=$('source').value!=='ref';localStorage.setItem('dic.live.'+id,$(id).value);updateSourceNotice();invalidate({resetPreview:id==='source'});refresh();});}
$('raw').value=localStorage.getItem('dic.live.raw')||'';$('raw').addEventListener('change',()=>{localStorage.setItem('dic.live.raw',$('raw').value);invalidate();refresh();});
function buildFields(fields){
 if(fieldSchema.length)return false;fieldSchema=fields;
 for(const f of fields){let group=Object.keys(fieldGroups).find(key=>fieldGroups[key].includes(f.id));if(!group)group='controls';const label=document.createElement('label');label.append(document.createTextNode(f.label));const input=document.createElement(f.options?'select':'input');input.id=f.id;if(f.id==='duration')label.hidden=true;
 if(f.options){for(const [value,title] of f.options){const o=document.createElement('option');o.value=String(value);o.textContent=title;input.append(o);}}else{input.type='number';input.min=f.min/f.divisor;input.max=f.max/f.divisor;input.step=1/f.divisor;}
 const saved=localStorage.getItem('dic.live.'+f.id),value=saved===null?f.default/f.divisor:Number(saved);input.value=Number.isFinite(value)&&value*f.divisor>=f.min&&value*f.divisor<=f.max?value:f.default/f.divisor;
 input.addEventListener('change',()=>{localStorage.setItem('dic.live.'+f.id,input.value);if($('scenario').value==='zero'){$('scenario').value='example';localStorage.setItem('dic.live.scenario','example');}invalidate();refresh();});label.append(input);$('fields-'+group).append(label);}
 $('field-loading').hidden=true;return true;
}
$('reset').addEventListener('click',()=>{for(const f of fieldSchema){$(f.id).value=f.default/f.divisor;localStorage.removeItem('dic.live.'+f.id);}$('raw').value='';localStorage.removeItem('dic.live.raw');$('scenario').value='example';localStorage.setItem('dic.live.scenario','example');invalidate();refresh();});
function amsDiagnosisWarning(out){return out.ams_diagnostic_valid!==undefined&&(!out.ams_diagnostic_valid||out.ams_diagnostic_code!==0);}
function showOutputs(out){showLeds(out);const warning=!!out.ams_led;const diagnosis=amsDiagnosisWarning(out);$('diagnostic-warning').hidden=!diagnosis;$('diagnostic-warning').textContent=diagnosis?'Zusätzliche Diagnosewarnung: '+(out.ams_diagnostic_valid?'AMS-Code '+out.ams_diagnostic_code:'Keine gültige AMS-Diagnose')+'. Die LEDs zeigen weiterhin die tatsächlichen Firmware-Ausgänge.':'';const items=[['AMS-Warnlampe',warning?'AN':'Aus',warning],['IMD-Warnlampe',out.imd_led?'AN':'Aus',!!out.imd_led],['DIC → 0x500',out.tx.map(b=>b.toString(16).padStart(2,'0').toUpperCase()).join(' '),false]];$('outputs').replaceChildren(...items.map(([label,value,on])=>{const e=document.createElement('span');e.className='output';e.dataset.on=String(on);e.textContent=label+': '+value;return e;}));}
function showLeds(out){function lamp(el,on,label,rgb){el.dataset.on=String(!!on);el.setAttribute('aria-label',label+': '+(on?'An':'Aus'));if(rgb)el.style.setProperty('--lamp',`rgb(${rgb.map(v=>v?255:0).join(',')})`);}function row(id,values,label,rgb=false){const box=$(id);if(box.children.length!==values.length)box.replaceChildren(...values.map(()=>{const el=document.createElement('span');el.className='led';el.setAttribute('role','img');return el;}));values.forEach((v,i)=>lamp(box.children[i],rgb?v.some(Boolean):v,label+' '+(i+1),rgb?v:null));}row('top-leds',out.top,'Oben');row('ams-leds',out.bottom,'AMS unten');row('left-leds',out.left_rgb,'RGB links',true);row('right-leds',out.right_rgb,'RGB rechts',true);lamp($('imd-lamp'),out.imd_led,'IMD');}
function draw(data){drawLcd($('display'),data,getComputedStyle($('lcd')).color);}
function paramsForFrame(){const params=new URLSearchParams({source:$('source').value,ref:$('git-ref').value,page:selected,scenario:$('scenario').value,raw:$('raw').value});for(const f of fieldSchema){if(!$(f.id).checkValidity()){const error=Error('Bitte gültigen Wert eingeben: '+f.label);error.input=true;throw error;}params.set(f.id,String(Math.round(Number($(f.id).value)*f.divisor)));}return params;}
async function refresh(){
 if(busy){needsRefresh=true;return;}busy=true;needsRefresh=false;const generation=requestVersion;
 try{
  if(!configured){updateStatus();return;}
  const data=await sessionFrame(paramsForFrame());if(generation!==requestVersion){needsRefresh=true;return;}
  configOnline=true;if(buildFields(data.fields)){needsRefresh=true;return;}
  const options=data.pages.join('|');if($('page').dataset.options!==options){$('page').replaceChildren(...data.pages.map(p=>{const o=document.createElement('option');o.value=p;o.textContent=pageLabels[p]||p;return o;}));$('page').dataset.options=options;}
  selected=data.page;$('page').value=selected;$('page').disabled=!!data.replay&&!data.replay.manual_swc;localStorage.setItem('dic.live.page',selected);$('source-files').textContent=(data.source_files||[]).join(' · ');window.dispatchEvent(new CustomEvent('dic-frame',{detail:{revision:data.revision}}));
  draw(displayFrame(data));$('outputs').hidden=false;showOutputs(data.outputs);showSession(data);$('origin').textContent=sourceLabel(data.source);
  lastBuild=data.compiled_at?data.compiled_at*1000:(data.revision!==revision?Date.now():lastBuild);if(!data.session||data.session.id!==lastSessionId||data.session.time_ms!==lastSessionTime){lastSimulation=Date.now();lastSessionId=data.session?.id;lastSessionTime=data.session?.time_ms;}revision=data.revision;lastError='';simulationState='success';hasPreview=true;
  $('build-status').textContent='Kompilierung und Simulation erfolgreich';$('build-time').textContent=lastBuild?new Date(lastBuild).toLocaleString('de-DE'):'Erfolgreich bestätigt';$('error-notice').hidden=true;updateStatus();
 }catch(e){
  if(generation!==requestVersion){needsRefresh=true;return;}
  window.dispatchEvent(new CustomEvent('dic-frame-error'));showSessionError(e.message);
  hasPreview=false;lastError=e.message;simulationState=e.input?'input-error':/nicht kompiliert|C-Compiler|DIC_CC/i.test(e.message)?'compile-error':'error';
  if(e instanceof TypeError||e.status===403){configOnline=false;}
  $('build-status').textContent=simulationState==='compile-error'?'Kompilierung fehlgeschlagen':simulationState==='input-error'?'Eingaben ungültig':'Simulation nicht verfügbar';
  $('error').textContent=e.message;$('error-summary').textContent=simulationState==='compile-error'?'Der aktuelle Code konnte nicht kompiliert werden. Die Vorschau ist nicht aktuell.':simulationState==='input-error'?e.message:'Keine aktuelle Simulation. Prüfe die vollständige Fehlermeldung.';$('error-notice').hidden=false;$('outputs').hidden=true;updateStatus();
 }finally{busy=false;if(needsRefresh){needsRefresh=false;queueMicrotask(refresh);}}
}
// More frequent observations never advance firmware time or skip virtual steps.
window.addEventListener('DOMContentLoaded',()=>{
 const preview=$('preview-column'),workspace=$('workspace');
 if(typeof ResizeObserver!=='undefined'&&preview&&workspace){
  const resize=new ResizeObserver(()=>{workspace.style.setProperty('--preview-height',Math.ceil(preview.getBoundingClientRect().height)+'px');});
  resize.observe(preview);
 }
 loadConfig().then(refresh);
 setInterval(()=>{refresh();if(++configTicks%100===0)loadConfig();updateStatus();},50);
});
