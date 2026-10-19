// Profile storage is machine-local in the backend, independent of browser port.
// This file adds controls only; display and CAN logic remain in the C simulation.
let savedProfiles=[], profileBusy=false;
function profileMessage(message,error=false){$('profile-message').hidden=!message;$('profile-message').textContent=message;$('profile-message').dataset.tone=error?'bad':'pending';}
function profileButtons(){const active=!!$('profile-select').value;for(const id of ['profile-save','profile-rename','profile-delete'])$(id).disabled=profileBusy||!active;for(const id of ['profile-new','profile-export','profile-import','profile-select'])$(id).disabled=profileBusy;}
function profileState(){const params=paramsForFrame();return {values:Object.fromEntries(fieldSchema.map(f=>[f.id,Number(params.get(f.id))])),raw:$('raw').value,scenario:$('scenario').value,page:selected};}
function profileList(items,id=$('profile-select').value){savedProfiles=items;const empty=document.createElement('option');empty.value='';empty.textContent='Ungespeicherte Werte';$('profile-select').replaceChildren(empty,...items.map(item=>{const option=document.createElement('option');option.value=item.id;option.textContent=item.name;return option;}));$('profile-select').value=items.some(p=>p.id===id)?id:'';profileButtons();}
function applyProfile(item){
 for(const field of fieldSchema){const value=item.state.values[field.id]/field.divisor;$(field.id).value=String(value);localStorage.setItem('dic.live.'+field.id,String(value));}
 $('raw').value=item.state.raw;$('scenario').value=item.state.scenario;selected=item.state.page;
 localStorage.setItem('dic.live.raw',item.state.raw);localStorage.setItem('dic.live.scenario',item.state.scenario);localStorage.setItem('dic.live.page',selected);localStorage.setItem('dic.profile.id',item.id);
 $('profile-name').value=item.name;profileMessage('Profil als Eingaben geladen. Firmware-Zustand und Verriegelungen bleiben erhalten.');invalidate();refresh();
}
async function loadProfiles(){try{const data=await api('/api/profiles');buildFields(data.fields);profileList(data.profiles,localStorage.getItem('dic.profile.id')||'');const item=savedProfiles.find(p=>p.id===$('profile-select').value);if(item)$('profile-name').value=item.name;profileMessage('');}catch(e){profileMessage(e.message,true);}}
async function profileAction(action,extra={}){
 if(profileBusy)return;profileBusy=true;profileButtons();
 try{const body={action,id:$('profile-select').value,...extra};if(action==='create'||action==='save')body.state=profileState();if(action==='create'||action==='rename')body.name=$('profile-name').value;
  const data=await api('/api/profiles',body);profileList(data.profiles,data.selected||'');localStorage.setItem('dic.profile.id',data.selected||'');
  const item=savedProfiles.find(p=>p.id===data.selected);if(item)$('profile-name').value=item.name;
  if(action==='import'&&item)applyProfile(item);else profileMessage(action==='delete'?'Profil gelöscht. Die eingestellten Fahrzeugwerte bleiben erhalten.':action==='rename'?'Profil umbenannt.':'Profil gespeichert.');
 }catch(e){profileMessage(e.message,true);}finally{profileBusy=false;profileButtons();}
}
$('profile-select').addEventListener('change',()=>{const item=savedProfiles.find(p=>p.id===$('profile-select').value);profileButtons();if(item)applyProfile(item);else{localStorage.removeItem('dic.profile.id');profileMessage('Aktuelle Werte sind keinem Profil zugeordnet.');}});
$('profile-new').addEventListener('click',()=>{
 const name=$('profile-name').value.trim();
 if(!name||savedProfiles.some(p=>p.name===name)){
  $('profile-tools').open=true;if(name)$('profile-name').value='';$('profile-name').focus();
  profileMessage('Namen eingeben, dann erneut „Neues Profil“ wählen.');return;
 }
 return profileAction('create');
});
$('profile-save').addEventListener('click',()=>profileAction('save'));
$('profile-rename').addEventListener('click',()=>profileAction('rename'));
$('profile-delete').addEventListener('click',()=>profileAction('delete'));
function markProfileDirty(){if($('profile-select').value)profileMessage('Werte geändert. „Speichern“ übernimmt sie in das ausgewählte Profil.');}
for(const id of ['fields','raw','scenario','page'])$(id).addEventListener('change',markProfileDirty);
$('reset').addEventListener('click',markProfileDirty);
$('profile-export').addEventListener('click',()=>{try{const name=$('profile-name').value.trim()||'Simulationsprofil';if(name.length>80)throw Error('Profilname darf maximal 80 Zeichen enthalten.');const data={format:'dic-simulation-profile',version:1,name,state:profileState()};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)+'\n'],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download=(name.replace(/[^a-zA-Z0-9_-]+/g,'_')||'profil')+'.dic-profile.json';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);profileMessage('Aktuelle Werte als JSON exportiert. Das lokale Profil wurde dadurch nicht überschrieben.');}catch(e){profileMessage(e.message,true);}});
$('profile-import').addEventListener('click',()=>$('profile-file').click());
$('profile-file').addEventListener('change',async()=>{const file=$('profile-file').files[0];try{if(!file)return;if(file.size>60000)throw Error('Profil-Datei zu groß (maximal 60 KB).');const profile=JSON.parse(await file.text());await profileAction('import',{profile});}catch(e){profileMessage('Import fehlgeschlagen: '+e.message,true);}finally{$('profile-file').value='';}});

loadProfiles();
