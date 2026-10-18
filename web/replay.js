// Observation is deliberately separate from the SWC input and profile page field.
let latestFrame=null, renderedReplaySession=null, importKind='scenario', observedSessionId=null, availableScenarios=[];
function displayFrame(data){latestFrame=data;return $('view-mode').value==='buffer'&&data.logical_rows?{...data,rows:data.logical_rows}:data;}
function replayMessage(text,error=false){$('replay-message').textContent=text;$('replay-message').dataset.tone=error?'bad':'pending';}
function scenarioOptions(items,selected=$('replay-select').value){availableScenarios=items;if(!selected&&latestFrame?.replay)selected=items.find(item=>item.name===latestFrame.replay.name)?.id||'';const empty=document.createElement('option');empty.value='';empty.textContent='Manuelle Generatoren · Live';$('replay-select').replaceChildren(empty,...items.map(item=>{const option=document.createElement('option');option.value=item.id;option.textContent=item.name;return option;}));$('replay-select').value=selected;}
async function loadScenarios(){try{const data=await api('/api/scenarios');scenarioOptions(data.scenarios);replayMessage('Ablauf laden, dann links starten. Lädt einen neuen Kaltstart.');}catch(error){replayMessage(error.message,true);}}
function syncReplayInputs(data){
 if(!data.input_state)return;
 for(const field of fieldSchema)$(field.id).value=String(data.input_state.values[field.id]/field.divisor);
 $('scenario').value=data.input_state.scenario||'example';$('raw').value=data.input_state.raw;selected=data.input_state.page;$('page').value=selected;
 // The replay already owns these initial settings; do not send a second change.
 sentInputs=paramsForFrame().toString();
 if($('profile-select').value)profileMessage('Szenario-Eingaben geladen. Das ausgewählte gespeicherte Profil wurde nicht verändert.');
}
function showVehicleSignals(data){
 const state=data.state||{};
 const value=(name,unit='')=>typeof state[name]==='number'?state[name]+unit:'—';
 $('signal-speed').textContent=state.speed_valid?value('speed_kmh',' km/h'):'—';
 $('signal-throttle').textContent=value('APPS1',' %');
 $('signal-front').textContent=value('BPSF');$('signal-rear').textContent=value('BPSR');
 $('signal-battery').textContent=typeof state.bms_max_temp==='number'?(state.bms_max_temp/10).toLocaleString('de-DE',{maximumFractionDigits:1})+' °C':'—';
 $('signal-motor').textContent=typeof state.motor_temp==='number'?(state.motor_temp/10).toLocaleString('de-DE',{maximumFractionDigits:1})+' °C':'—';
 $('signals-status').textContent=data.session.time_ms===0?'Kaltstart · noch keine CAN-Daten verarbeitet.':data.replay?'Werte folgen dem Szenario. Manuelle Eingaben werden unterhalb geändert.':'Werte folgen den manuellen CAN-Sendern.';
}
let selectedCanMessage=null;
function showCanMonitor(data){
 const kind=$('can-kind').value||'rx',filter=$('can-filter').value.trim().replace(/^0x/i,'').toUpperCase();
 const traffic=data.traffic||{},messages=traffic.can?.[kind]||[];
 const matches=messages.filter(item=>item.can_id.toString(16).toUpperCase().padStart(3,'0').includes(filter));
 const items=matches.slice(0,100),body=$('can-table-body');
 $('can-monitor-status').textContent=(matches.length?`${items.length} von ${matches.length} CAN-IDs`:'Noch keine passenden Nachrichten.')+(traffic.transport_dropped?' · Erfassung unvollständig: Transportereignisse verloren.':'');
 function element(tag,text){const item=document.createElement(tag);if(text!==undefined)item.textContent=text;return item;}
 const order=JSON.stringify([data.session.id,kind,items.map(item=>item.can_id)]);
 // Keep rows and focus stable while bytes/counters change in the live view.
 if(body.dataset.order!==order){
  body.dataset.order=order;
  body.replaceChildren(...items.map(item=>{
   const row=element('tr');row.tabIndex=0;
   row.append(element('td'),element('td'),element('td'),element('td'));row.children[2].className='can-data';
   for(let i=0;i<8;i++){const byte=element('span');byte.className='can-byte';row.children[2].append(byte);}
   const select=()=>{selectedCanMessage={session:data.session.id,kind,id:item.can_id};if(latestFrame)showCanMonitor(latestFrame);};
   row.addEventListener('click',select);row.addEventListener('focus',select);
   return row;
  }));
 }
 items.forEach((item,index)=>{
  const row=body.children[index],id='0x'+item.can_id.toString(16).toUpperCase().padStart(3,'0');
  row.children[0].textContent=id;row.children[1].textContent=item.dlc;row.children[3].textContent=item.count.toLocaleString('de-DE');
  row.dataset.selected=String(selectedCanMessage&&selectedCanMessage.session===data.session.id&&selectedCanMessage.kind===kind&&selectedCanMessage.id===item.can_id);
  row.setAttribute('aria-label',`${id}, DLC ${item.dlc}, ${item.count} Telegramme. Details durch Auswahl.`);
  for(let i=0;i<8;i++){
   const byte=row.children[2].children[i],present=i<item.dlc;
   byte.dataset.missing=String(!present);byte.textContent=present?item.data[i].toString(16).toUpperCase().padStart(2,'0'):'—';
   byte.setAttribute('title',present?`Byte ${i}: ${item.data[i]} dezimal · ${item.data[i].toString(2).padStart(8,'0')} binär`:`Byte ${i}: nicht im Telegramm übertragen`);
  }
 });
 const chosen=selectedCanMessage&&selectedCanMessage.session===data.session.id&&selectedCanMessage.kind===kind?items.find(item=>item.can_id===selectedCanMessage.id):null;
 $('can-selected').textContent=chosen?`0x${chosen.can_id.toString(16).toUpperCase()} · t=${chosen.at_ms.toLocaleString('de-DE')} ms · Alter ${chosen.age_ms.toLocaleString('de-DE')} ms · Δ ${chosen.interval_ms===null?'—':chosen.interval_ms.toLocaleString('de-DE')+' ms'}`+(chosen.reason_text?' · '+chosen.reason_text:''):'Zeile wählen: Zeit, Alter und Abstand anzeigen.';
}
$('can-kind').addEventListener('change',()=>{if(latestFrame)showCanMonitor(latestFrame);});
$('can-filter').addEventListener('input',()=>{if(latestFrame)showCanMonitor(latestFrame);});
window.addEventListener('dic-frame-error',()=>{$('can-monitor-status').textContent='Keine aktuelle Bestätigung · angezeigt wird der letzte bestätigte Schnappschuss.';});
function showReplay(data){
 showVehicleSignals(data);
 showCanMonitor(data);
 if(data.session.id!==observedSessionId){observedSessionId=data.session.id;$('inspect-page').value='';}
 if(data.replay&&data.session.id!==renderedReplaySession){renderedReplaySession=data.session.id;syncReplayInputs(data);const item=availableScenarios.find(item=>item.name===data.replay.name);if(item)$('replay-select').value=item.id;}
 const pageOptions=data.pages.join('|');
 if($('inspect-page').dataset.options!==pageOptions){
  const chosen=$('inspect-page').value;const active=document.createElement('option');active.value='';active.textContent='Aktive Firmwareseite';
  $('inspect-page').replaceChildren(active,...data.pages.map(page=>{const option=document.createElement('option');option.value=page;option.textContent=pageLabels[page]||page;return option;}));
  $('inspect-page').value=data.pages.includes(chosen)?chosen:'';$('inspect-page').dataset.options=pageOptions;
 }
 $('inspect-controls').hidden=$('view-mode').value!=='buffer';
 $('display-view-note').textContent=$('view-mode').value==='buffer'?'Diagnosepuffer · '+(pageLabels[data.logical_page]||data.logical_page||data.active_page)+' · kein übertragener LCD-Inhalt':'LCD · tatsächlich übertragene Zeichen';
 const traffic=data.traffic;
 if(traffic){
  const c=traffic.counts;$('traffic-counts').textContent=`${c.rx} empfangen · ${c.tx} gesendet · ${c.drop} verworfen · ${c.lcd} LCD-Zugriffe`+(traffic.history_dropped?' · Ältere Anzeigeereignisse aus begrenztem Verlauf entfernt: '+traffic.history_dropped:'')+(traffic.transport_dropped?' · Achtung: Transportereignisse verloren: '+traffic.transport_dropped:'');
  for(const kind of ['rx','tx','drop','lcd'])$('traffic-'+kind).textContent=(traffic[kind]||[]).map(e=>`${e.at_ms} ms · ${kind==='lcd'?'RS/Byte':'0x'+e.can_id.toString(16).toUpperCase()} · ${e.data.map(b=>b.toString(16).padStart(2,'0').toUpperCase()).join(' ')}${e.reason_text?' · '+e.reason_text:''}`).join('\n')||'Noch keine Ereignisse.';
 }
 if(!data.replay){$('replay-check-summary').textContent='Kein zeitliches Szenario geladen.';$('replay-checks').textContent='';return;}
 const r=data.replay,checks=r.checks||[],failed=checks.filter(c=>!c.passed).length,tx=r.tx||{};
 $('replay-check-summary').textContent=`${r.name} · ${data.session.time_ms} / ${r.duration_ms} ms · ${checks.length-failed} Ablaufprüfungen bestanden · ${failed} fehlgeschlagen`+(tx.configured?` · TX: ${tx.passed} bestanden, ${tx.failed} fehlgeschlagen, ${tx.pending} offen`:' · Kein TX-Sollvergleich definiert.');
 $('replay-check-summary').dataset.tone=failed||tx.failed||tx.incomplete_history?'bad':r.finished&&(checks.length||tx.configured)?'good':'pending';
 const lines=checks.map(c=>`${c.passed?'✓':'✕'} ${c.at_ms} ms · ${c.path}\nErwartet: ${JSON.stringify(c.expected)}\nTatsächlich: ${JSON.stringify(c.actual)}`);
 for(const c of tx.results||[])if(c.status!=='passed')lines.push(`${c.status==='pending'?'…':'✕'} TX-Vergleich\nErwartet: ${JSON.stringify(c.expected)}\nTatsächlich: ${JSON.stringify(c.actual)}`);
 if(tx.incomplete_history)lines.push('TX-Verlauf unvollständig; kein vollständiger Vergleich möglich.');
 $('replay-checks').textContent=lines.join('\n\n');
}
$('view-mode').addEventListener('change',()=>{if(latestFrame){showReplay(latestFrame);draw(displayFrame(latestFrame));}});
$('inspect-page').addEventListener('change',()=>sessionCommand('inspect',{page:$('inspect-page').value||null}));
$('replay-apply').addEventListener('click',()=>sessionCommand('scenario',{id:$('replay-select').value}));
for(const [id,kind] of [['replay-json','scenario'],['replay-log','candump']])$(id).addEventListener('click',()=>{importKind=kind;$('replay-file').accept=kind==='scenario'?'.json':'.log,.txt,.candump';$('replay-file').click();});
$('replay-file').addEventListener('change',async()=>{
 const file=$('replay-file').files[0];
 try{if(!file)return;if(file.size>5*1024*1024)throw Error('Importdatei zu groß: maximal 5 MiB.');
  const data=await api('/api/scenarios',{action:'import',kind:importKind,text:await file.text(),name:file.name.replace(/\.[^.]+$/,'').slice(0,80),offset_ms:Number($('log-offset').value||0)});
  scenarioOptions(data.scenarios,data.selected);replayMessage('Importiert. „Laden / Kaltstart“ startet den Ablauf. Import bleibt bis zum Serverende verfügbar.');
 }catch(error){replayMessage(error.message,true);}finally{$('replay-file').value='';}
});
$('replay-export').addEventListener('click',async()=>{
 try{if(!$('replay-select').value)throw Error('Zuerst ein zeitliches Szenario auswählen.');
  const data=await api('/api/scenarios',{action:'export',id:$('replay-select').value});
  const url=URL.createObjectURL(new Blob([JSON.stringify(data.scenario,null,2)+'\n'],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download='dic.scenario.json';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }catch(error){replayMessage(error.message,true);}
});
loadScenarios();
