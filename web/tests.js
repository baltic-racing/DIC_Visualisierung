// Test execution is unchanged; successful details stay folded, failures open.
let testBusy=false, lastTestRevision='', currentFrameRevision='', lastTestSource='';
const testCards=new Map();
function testStatus(card,status,text){card.status.textContent=text;card.status.dataset.tone=status==='passed'?'good':status==='failed'?'bad':status==='not-configured'?'warn':'pending';}
const resultTitles={passed:'BESTANDEN',failed:'FEHLGESCHLAGEN','not-configured':'NICHT KONFIGURIERT'};
const testNames={normal:'Normalbetrieb',ams:'AMS-Warnung',imd:'IMD-Warnung','can-loss':'CAN-Ausfall',pages:'Displayseiten',diagnosis:'Diagnoseanzeige'};
function testContext(text,tone='pending'){$('tests-context').textContent=text;$('tests-context').hidden=!text;$('tests-context').dataset.tone=tone;}
function staleTests(){
 if(lastTestRevision&&currentFrameRevision)testContext(lastTestRevision!==currentFrameRevision?'Der Code wurde seit dem Testlauf geändert. Bitte Tests erneut ausführen.':lastTestSource,lastTestRevision!==currentFrameRevision?'warn':'pending');
 for(const card of testCards.values())if(card.result){const different=!!currentFrameRevision&&card.revision&&card.revision!==currentFrameRevision;testStatus(card,card.result.status,(resultTitles[card.result.status]||card.result.status)+(different?' · Code geändert':''));if(different&&card.result.status==='passed')card.status.dataset.tone='warn';}
}
window.addEventListener('dic-frame',event=>{currentFrameRevision=event.detail.revision;staleTests();});
window.addEventListener('dic-frame-error',()=>{currentFrameRevision='';if(lastTestRevision)testContext('Die Vorschau ist nicht aktuell bestätigt. Testergebnisse gehören zum letzten Testlauf.','warn');});
for(const id of ['source','git-ref','firmware-path'])$(id).addEventListener('change',()=>{if(lastTestRevision)testContext('Codequelle geändert. Angezeigte Ergebnisse gehören zum vorherigen Testlauf.','warn');});
function showTestResult(result,revision){
 const card=testCards.get(result.id);if(!card)return;
 card.result=result;card.revision=revision;testStatus(card,result.status,resultTitles[result.status]||result.status);
 card.body.replaceChildren();
 const description=document.createElement('p');description.className='info';description.textContent=card.description;card.body.append(description);
 if(result.reason){const p=document.createElement('p');p.className='info';p.textContent=result.reason;card.body.append(p);}
 for(const check of result.checks||[]){const pre=document.createElement('pre');pre.className='test-check';pre.dataset.tone=check.passed?'good':'bad';pre.textContent=(check.passed?'✓ ':'✕ ')+check.label+'\nErwartet: '+JSON.stringify(check.expected)+'\nTatsächlich: '+JSON.stringify(check.actual);card.body.append(pre);}
 card.details.open=result.status!=='passed';
}
async function runTests(id){
 if(testBusy)return;testBusy=true;$('tests-all').disabled=true;
 for(const [key,card] of testCards){card.button.disabled=true;if(id==='all'||key===id)testStatus(card,'pending','Läuft …');}
 const source=$('source').value,ref=$('git-ref').value;$('tests-summary').textContent='Tests laufen …';testContext('');
 try{
  const data=await api('/api/tests',{test:id,source,ref});lastTestRevision=data.revision||'';
  for(const result of data.results)showTestResult(result,data.revision);
  const passed=data.results.filter(r=>r.status==='passed').length,failed=data.results.filter(r=>r.status==='failed').length,skipped=data.results.filter(r=>r.status==='not-configured').length;
  $('tests-summary').textContent=`${passed} bestanden · ${failed} fehlgeschlagen · ${skipped} nicht konfiguriert`;
  lastTestSource='Getestet: '+sourceLabel(data.source);testContext(lastTestSource);
  if($('source').value!==source||$('git-ref').value!==ref)testContext('Die Codequelle wurde während des Tests geändert. Ergebnisse gehören zu den zuvor gewählten Dateien.','warn');else staleTests();
 }catch(e){
  $('tests-summary').textContent='Tests konnten nicht ausgeführt werden';testContext(e.message,'bad');
  for(const [key] of testCards)if(id==='all'||key===id)showTestResult({id:key,status:'failed',reason:e.message},'');
 }finally{testBusy=false;$('tests-all').disabled=false;for(const card of testCards.values())card.button.disabled=false;}
}
async function loadTests(){
 try{
  const data=await api('/api/tests');
  for(const test of data.tests){
   const card=document.createElement('article');card.className='test-card';
   const name=document.createElement('h3');name.textContent=testNames[test.id]||test.name;
   const status=document.createElement('p');status.className='test-result';status.textContent='Noch nicht ausgeführt';status.setAttribute('role','status');
   const button=document.createElement('button');button.type='button';button.textContent='Ausführen';button.addEventListener('click',()=>runTests(test.id));
   const details=document.createElement('details');details.className='test-details';
   const summary=document.createElement('summary');summary.textContent='Details';
   const body=document.createElement('div');const description=document.createElement('p');description.className='info';description.textContent=test.description;body.append(description);
   details.append(summary,body);card.append(name,status,button,details);$('tests-list').append(card);
   testCards.set(test.id,{status,button,details,body,description:test.description});
  }
 }catch(e){$('tests-summary').textContent=e.message;}
}
$('tests-all').addEventListener('click',()=>runTests('all'));
loadTests();
