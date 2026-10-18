// Session commands change state; GET /api/frame is strictly a snapshot read.
let sentInputs='', sessionBusy=false, sessionAttached=false;
async function sessionFrame(params){
 let signature=params.toString();
 if(!sessionAttached){
  const generation=requestVersion;
  try{
   const existing=await api('/api/frame');sessionAttached=true;
   if(generation===requestVersion&&existing.input_state){
    buildFields(existing.fields);const selection=existing.session.selection;
    if(selection){$('source').value=selection.source;$('git-ref').value=selection.ref;$('scenario').value=selection.scenario;}
    syncReplayInputs(existing);
   }else sentInputs=signature;
   return existing;
  }catch(error){if(error.status!==422||!error.message.includes('Noch keine Firmware-Sitzung'))throw error;sessionAttached=true;}
 }

 if(signature!==sentInputs){
  const at=$('input-at').value;
  const data=await api('/api/session',{action:'inputs',query:Object.fromEntries(params),...(at===''?{}:{at_ms:Number(at)})});
  sentInputs=signature;
  return data;
 }
 return api('/api/frame');
}
function showSession(data){
 const s=data.session;if(!s)return;showReplay(data);
 $('session-status').textContent=s.status==='running'?'Läuft':s.status==='finished'?'Replay beendet':'Pausiert';
 $('virtual-time').textContent=(s.time_ms/1000).toLocaleString('de-DE',{minimumFractionDigits:3,maximumFractionDigits:3})+' s';
 $('session-speed').value=String(s.speed||1);
 $('session-notice').textContent=s.notice||'Firmware-Zustand bleibt zwischen Abrufen erhalten.';
 $('session-events').textContent=(s.next_input_ms===null?'Keine geplanten Eingabeänderungen.':'Nächste Eingabe: '+s.next_input_ms+' ms · '+s.pending_events+' Ereignis(se).')+(s.backlog_ms?' · Noch nachzuholen: '+s.backlog_ms+' ms':'');
}
function showSessionError(message){$('session-status').textContent='Fehler – Sitzung angehalten';$('session-notice').textContent=message.split('\n')[0];}
async function sessionCommand(action,extra={}){
 if(sessionBusy)return;sessionBusy=true;
 const ids=['session-start','session-pause','session-reset','session-advance','session-fast','pulse-ts','pulse-r2d'];
 ids.forEach(id=>$(id).disabled=true);
 try{
  const data=await api('/api/session',{action,...extra});
  showSession(data);$('session-feedback').textContent='';
  await refresh();
 }catch(error){$('session-feedback').textContent=error.message;$('session-feedback').dataset.tone='bad';await refresh();}
 finally{sessionBusy=false;ids.forEach(id=>$(id).disabled=false);}
}
$('session-start').addEventListener('click',()=>sessionCommand('resume'));
$('session-pause').addEventListener('click',()=>sessionCommand('pause'));
$('session-reset').addEventListener('click',()=>sessionCommand('reset'));
$('session-speed').addEventListener('change',()=>sessionCommand('speed',{speed:Number($('session-speed').value)}));
$('session-advance').addEventListener('click',()=>sessionCommand('advance',{target_ms:Number($('session-target').value)}));
$('session-fast').addEventListener('click',()=>sessionCommand('advance',{target_ms:15000}));
function pulse(button){const at=$('pulse-at').value;return sessionCommand('pulse',{button,duration_ms:Number($('pulse-duration').value),...(at===''?{}:{at_ms:Number(at)})});}
$('pulse-ts').addEventListener('click',()=>pulse('ts_button'));
$('pulse-r2d').addEventListener('click',()=>pulse('r2d_button'));
