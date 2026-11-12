import { VillageScene, drawPerson } from './scene.js';
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const pretty = (s) => String(s ?? '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
const clamp = (n, a, b) => Math.max(a, Math.min(b, Number(n) || 0));
const clock = (minute) => `${String(Math.floor((Number(minute)||0)/60)%24).padStart(2,'0')}:${String(Math.floor((Number(minute)||0)%60)).padStart(2,'0')}`;
const initial = (name) => String(name||'?').split(' ').map(n=>n[0]).slice(0,2).join('');
let state = null, selectedId = null, selectedTab = 'story', latestSnapshot = 0, lastError = '', pending = 0, pollActive = false;
let detailKey = '', rosterKey = '', chronicleKey = '', headerKey = '', providerKey = '', following = false;
let editingScenarioId = null, draftBeforeEdit = null, oracleSubmitting = false, scenarioKey = '';
const dismissingScenarios = new Set();
const scene = new VillageScene($('#village-canvas'), selectPerson);
scene.onFollowChange = active => { following=active;updateFollow(); };

async function request(path, body) {
  const abort = new AbortController(); const timer=setTimeout(()=>abort.abort(),path.startsWith('/api/oracle')?125000:30000);
  try { const response=await fetch(path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:abort.signal});let data;try{data=await response.json();}catch{throw new Error('The village server returned an unreadable response.');}if(!response.ok)throw new Error(data.error||`Village server error (${response.status}).`);return data; }
  catch(error){if(error.name==='AbortError')throw new Error('The village server took too long to respond. Check its terminal, then try again.');throw error;}
  finally{clearTimeout(timer);}
}
async function mutate(path, body, message) {
  pending++; updateBusy();
  try { const result=await request(path,body);acceptState(result);if(message)toast(message);return result; }
  catch(error){toast(error.message,true);return null;}
  finally{pending--;updateBusy();}
}
function updateBusy(){const disabled=!state||pending>0;for(const id of ['play-button','step-button','speed-select','mode-select','reset-button','save-button'])$('#'+id).disabled=disabled;updateOracleControls();}
function toast(message,error=false){const el=document.createElement('div');el.className=`toast${error?' error':''}`;el.innerHTML=`<button aria-label="Dismiss message">×</button>${esc(message)}`;el.querySelector('button').addEventListener('click',()=>el.remove());$('#toast-stack').append(el);if(!error)setTimeout(()=>el.remove(),5000);else setTimeout(()=>el.remove(),20000);}
async function poll(){if(pollActive)return;pollActive=true;try{const data=await request('/api/state');acceptState(data);$('#connection').className='connection connected';$('#connection').innerHTML='<span class="status-dot"></span><span>World connected</span>';}catch(error){$('#connection').className='connection error';$('#connection').innerHTML='<span class="status-dot"></span><span>Connection lost</span>';if(!state){$('#map-hint').textContent='Waiting for the village server. Reconnecting…';$('#person-details').innerHTML='<p class="empty-copy">Start the local server with <code>python -m village.server</code>. This page reconnects automatically.</p>';}}finally{pollActive=false;}}
function acceptState(data){
  if(!data||!Array.isArray(data.villagers))return;
  // Oracle edits can finish between polls without advancing the clock.
  if(state&&data.server_instance&&data.server_instance===state.server_instance&&Number.isFinite(Number(data.revision))&&Number(data.revision)<Number(state.revision))return;
  if(state&&!data.server_instance&&data.seed===state.seed&&Number(data.tick)<Number(state.tick)&&Date.now()-latestSnapshot<2000)return;
  state=data;latestSnapshot=Date.now();if(!selectedId||!state.villagers.some(v=>v.id===selectedId))selectedId=state.villagers[0]?.id;
  scene.setState(state);scene.select(selectedId);render();updateBusy();
}
function selectPerson(id){if(!state?.villagers.some(v=>v.id===id))return;selectedId=id;scene.select(id);detailKey='';headerKey='';chronicleKey='';rosterKey='';renderPerson();renderChronicle();renderPeople();$('#people-popover').hidden=true;if(following)scene.centerOn(id);if(matchMedia('(max-width:700px)').matches&&document.activeElement!==$('#village-canvas'))$('.inspector').scrollIntoView({behavior:'smooth',block:'nearest'});}
function render(){
  $('#clock-label').textContent=`Day ${state.day} · ${clock(state.minute)}`;
  const pop=state.villagers.length,prosperity=Math.round(state.world?.prosperity??0),tension=Math.round(state.world?.tension??0);
  $('#world-stats').innerHTML=`<div class="world-stat"><span>POPULATION</span><strong>${pop} <small>souls</small></strong></div><div class="world-stat"><span>PROSPERITY</span><strong>${prosperity}<small>/100</small> <span class="stat-state">${prosperity>70?'Thriving':prosperity>40?'Steady':'Struggling'}</span></strong></div><div class="world-stat"><span>SOCIAL TENSION</span><strong>${tension}<small>/100</small> <span class="stat-state ${tension>60?'tension-high':''}">${tension>70?'Volatile':tension>40?'Uneasy':'Peaceful'}</span></strong></div>`;
  const weather=String(state.weather||'clear');$('#weather-label').textContent=`${/rain|storm/i.test(weather)?'☂':/snow/i.test(weather)?'❄':/cloud|fog/i.test(weather)?'☁':'☀'} ${pretty(weather).toUpperCase()} · ${pretty(state.season||'Spring').toUpperCase()}`;
  $('#play-button .play-icon').textContent=state.running?'Ⅱ':'▶';$('#play-button .play-label').textContent=state.running?'Pause':state.tick?'Resume':'Begin life';$('#play-button').setAttribute('aria-label',state.running?'Pause simulation':'Start simulation');
  $('#speed-select').value=String(state.speed||1);$('#mode-select').value=state.mode||'demo';$('#mode-badge').textContent=state.mode==='live'?'JEV + LUNA · LIVE':'LOCAL SIMULATION';$('#mode-badge').className=`model-badge${state.mode==='live'?' live':''}`;
  const calls=state.metrics?.inflight||0;$('#simulation-state').textContent=`${state.running?'Life is unfolding':'World paused'}${calls?` · ${calls} model ${calls===1?'request':'requests'}`:''}`;
  $('#map-hint').hidden=Boolean(state.running||state.tick>1);$('#map-hint').textContent=state.mode==='live'?'A whole world is waiting. Press play to begin.':'Local simulation · press play to bring the clearing to life.';
  $('#people-count').textContent=pop;
  const contexts=state.contexts||[];$('#map-context').hidden=!contexts.length;if(contexts.length)$('#map-context').textContent=`✳ ${contexts[0].text}`;
  const modelStatus=$('#oracle-model-status');modelStatus.textContent=state.mode==='live'?'Live intelligence · Luna interprets your scenarios':'Local simulation · procedural scenario interpretation';modelStatus.classList.toggle('live',state.mode==='live');
  renderScenarios();updateOracleControls();
  const err=state.last_error;if(err&&err!==lastError){toast(typeof err==='string'?err:JSON.stringify(err),true);lastError=err;}if(!err)lastError='';
  renderPerson();renderPeople();renderChronicle();renderProviders();
}
function renderPerson(){
  const v=state?.villagers.find(v=>v.id===selectedId);if(!v)return;
  const newHeader=JSON.stringify([v.id,v.name,v.age,v.occupation,v.pronouns,v.action_label,v.decision?.source]);
  if(newHeader!==headerKey){headerKey=newHeader;$('#person-header').innerHTML=`<div class="portrait"><canvas id="portrait-canvas" width="96" height="96" aria-label="Pixel portrait of ${esc(v.name)}"></canvas></div><h2>${esc(v.name)}</h2><p class="person-meta">${esc(v.occupation)} · ${v.age} years · ${esc(v.pronouns||v.gender)}</p><span class="person-action"><span class="dot"></span>${esc(v.action_label||pretty(v.action)||'Taking in the day')}${v.decision?.source?`<span class="source-tag">${esc(v.decision.source.toUpperCase())}</span>`:''}</span>`;const pc=$('#portrait-canvas').getContext('2d');pc.imageSmoothingEnabled=false;drawPerson(pc,v,48,82,3,0,false,1);}
  const key=JSON.stringify([v,selectedTab]);if(key===detailKey)return;detailKey=key;
  const details=$('#person-details'),scroll=details.scrollTop;
  if(selectedTab==='story')details.innerHTML=storyContent(v);
  else if(selectedTab==='mind')details.innerHTML=mindContent(v);
  else details.innerHTML=tiesContent(v);
  details.scrollTop=scroll;
  details.querySelectorAll('[data-nudge]').forEach(btn=>btn.addEventListener('click',async()=>{btn.disabled=true;await mutate(`/api/villagers/${encodeURIComponent(v.id)}/nudge`,{action:btn.dataset.nudge});btn.disabled=false;}));
  details.querySelectorAll('[data-person]').forEach(btn=>btn.addEventListener('click',()=>selectPerson(btn.dataset.person)));
}
function storyContent(v){
  const traits=Object.entries(v.traits||{}).sort((a,b)=>(Number(b[1])||0)-(Number(a[1])||0)).slice(0,5);
  const n=Object.entries(v.needs||{}).map(([key,value])=>`<div class="need-row"><span class="need-name">${key==='hunger'?'Nourished':esc(pretty(key))}</span><div class="need-track" role="meter" aria-label="${esc(key==='hunger'?'Nourishment':pretty(key))}" aria-valuenow="${Math.round(value)}" aria-valuemin="0" aria-valuemax="100"><div class="need-fill" style="width:${clamp(value,0,100)}%;background:${value<25?'#c78b66':value<50?'#bbad74':'#8ca477'}"></div></div><span class="need-value">${Math.round(value)}</span></div>`).join('');
  const d=v.demographics||{};const demoEntries=Object.entries(d).filter(([k,val])=>val!==null&&val!==undefined&&(typeof val!=='object'||Array.isArray(val))&&!['age','name','occupation','gender','pronouns'].includes(k));
  const home=state.locations.find(l=>l.id===v.home);const goal=v.goal||'Finding their place in the village.';
  const pregnancy=v.pregnancy;const otherParent=pregnancy&&state.villagers.find(p=>p.id===pregnancy.other_parent_id);
  const family=pregnancy?`<section class="detail-section"><div class="detail-heading">A new chapter <span>EXPECTING</span></div><p class="detail-copy">${esc(v.name.split(' ')[0])}${otherParent?` and ${esc(otherParent.name.split(' ')[0])}`:''} ${otherParent?'are':'is'} expecting a child.</p><div class="need-row"><span class="need-name">Progress</span><div class="need-track" role="meter" aria-label="Pregnancy progress" aria-valuenow="${Math.round(pregnancy.progress||0)}" aria-valuemin="0" aria-valuemax="100"><div class="need-fill" style="width:${clamp(pregnancy.progress,0,100)}%;background:#bf9b91"></div></div><span class="need-value">${Math.round(pregnancy.progress||0)}%</span></div><p class="empty-copy">Pregnancy lasts ${esc(pregnancy.gestation_days||state.rules?.gestation_days||7)} village days in this simulation.</p></section>`:'';
  return `<section class="detail-section"><div class="detail-heading">A life before this</div><p class="detail-copy">${esc(v.backstory||'Their story is still being written.')}</p></section><section class="detail-section"><div class="detail-heading">What they hope for</div><div class="life-goal"><span>✧</span><p>${esc(goal)}</p></div></section><section class="detail-section"><div class="detail-heading">Their nature</div><div class="trait-list">${traits.map(([key,value])=>`<span class="trait-tag" title="${esc(pretty(key))}: ${esc(value)}">${esc(pretty(key))}</span>`).join('')}${(v.values||[]).slice(0,3).map(t=>`<span class="trait-tag">${esc(pretty(t))}</span>`).join('')}</div></section><section class="detail-section"><div class="detail-heading">The everyday things <span>FULFILMENT</span></div>${n}<div class="mood-line"><span>How they feel</span><strong>${esc(v.mood||'Content')}</strong></div></section><section class="detail-section"><div class="detail-heading">More than a name</div><div class="demographics"><div><span>HOME</span><strong>${esc(home?.name||'Hearth')}</strong></div><div><span>GENDER</span><strong>${esc(v.gender||'—')}</strong></div>${demoEntries.map(([key,val])=>`<div><span>${esc(pretty(key).toUpperCase())}</span><strong>${esc(Array.isArray(val)?val.map(pretty).join(', '):pretty(val))}</strong></div>`).join('')}</div></section>${family}`;
}
function mindContent(v){
  const source=v.thought_source||v.narrative_source||'authored';
  const thoughts=v.thought?`<div class="thought-card">“${esc(v.thought)}”</div>`:'<p class="empty-copy">A quiet mind, for now. Thoughts appear when their decision calls for reflection.</p>';
  const speech=v.speech?`<div class="speech-card">“${esc(v.speech)}”</div>`:'<p class="empty-copy">Nothing said at the moment.</p>';
  const decision=v.decision;let probs=decision?.probabilities||{};if(Array.isArray(probs))probs=Object.fromEntries(probs.map(p=>[p.action||p.label,p.probability||p.score||0]));const sorted=Object.entries(probs).sort((a,b)=>Number(b[1])-Number(a[1])).slice(0,7);
  const memories=(v.memories||[]).slice(0,12);
  return `<section class="detail-section"><div class="detail-heading">Behind their eyes <span>${source?esc(source==='demo'?'PROCEDURAL':source.toUpperCase()):'WAITING'}</span></div>${thoughts}<div class="nudge-controls"><button data-nudge="think">✧ Invite a thought</button><button data-nudge="talk">“ Start a conversation</button></div></section><section class="detail-section"><div class="detail-heading">Out loud <span>${v.speech_source?esc(v.speech_source==='demo'?'PROCEDURAL':v.speech_source.toUpperCase()):''}</span></div>${speech}</section><section class="detail-section"><div class="detail-heading">The next small decision <span>${esc(decision?.source?.toUpperCase()||'PENDING')}</span></div>${decision?`<p class="detail-copy">${esc(pretty(decision.action))}${decision.target_id?` → ${esc(state.villagers.find(p=>p.id===decision.target_id)?.name||decision.target_id)}`:''}</p><p class="empty-copy">${Math.round(clamp(decision.confidence,0,1)*100)}% confidence · ${decision.think?'Reflection invited':'No reflection'} · ${decision.speak?'Speech invited':'Staying quiet'}</p>${sorted.map(([action,probability])=>`<div class="probability"><span title="${esc(pretty(action))}">${esc(pretty(action))}</span><div class="probability-track"><i style="width:${clamp(Number(probability)*100,0,100)}%"></i></div><span>${Math.round(Number(probability)*100)}%</span></div>`).join('')}`:'<p class="empty-copy">Their first decision is still ahead. Start the village or advance a turn.</p>'}</section><section class="detail-section"><div class="detail-heading">What stays with them <span>${(v.memories||[]).length} MEMORIES</span></div>${memories.length?memories.map(m=>`<div class="memory"><span class="memory-dot"></span><div><p>${esc(m.text)}</p><small>Day ${m.day} · ${clock(m.minute)}${m.emotion?` · ${esc(pretty(m.emotion))}`:''}${m.context_status&&m.context_status!=='active'?` · ${esc(pretty(m.context_status))}`:''}</small></div></div>`).join(''):'<p class="empty-copy">The clearing has not left its mark yet. Significant moments become memories.</p>'}</section>`;
}
function tiesContent(v){
  const ties=Object.entries(v.relationships||{}).map(([id,tie])=>({person:state.villagers.find(p=>p.id===id),tie})).filter(x=>x.person).sort((a,b)=>Number(b.tie.affinity||0)-Number(a.tie.affinity||0));
  return `<section class="detail-section"><div class="detail-heading">The people in their orbit <span>${ties.length} CONNECTIONS</span></div><p class="empty-copy" style="margin-bottom:9px">Affinity, trust, and romance change with every shared moment.</p>${ties.length?ties.map(({person:p,tie})=>`<button class="relationship" data-person="${esc(p.id)}" aria-label="Inspect ${esc(p.name)}, ${esc(tie.status||'acquaintance')}"><span class="mini-avatar" style="color:${safeColor(p.color)}">${esc(initial(p.name))}</span><span class="relationship-info"><span class="relationship-name">${esc(p.name)}</span><span class="relationship-status">${esc(tie.status||'Acquaintance')} · trust ${Math.round(tie.trust||0)}${tie.romance>10?` · ♥ ${Math.round(tie.romance)}`:''}</span></span><span class="relationship-score">${Math.round(tie.affinity||0)} affinity<span class="bond-track"><span style="width:${clamp(tie.affinity,0,100)}%"></span></span></span></button>`).join(''):'<p class="empty-copy">There is a whole village of people to know.</p>'}</section><section class="detail-section"><div class="detail-heading">A gentle intervention</div><p class="empty-copy">A nudge sets their next immediate action. They continue choosing for themselves afterward.</p><div class="nudge-controls"><button data-nudge="talk">Start a conversation</button><button data-nudge="go_home">Send home</button></div></section>`;
}
function safeColor(color){return /^#[\da-f]{3,8}$/i.test(color||'')?color:'#597e4a';}
function renderPeople(){if(!state)return;const search=$('#people-search').value.toLowerCase();const key=JSON.stringify([state.villagers.map(v=>[v.id,v.name,v.action_label,v.occupation]),selectedId,search]);if(key===rosterKey)return;rosterKey=key;$('#people-list').innerHTML=state.villagers.filter(v=>`${v.name} ${v.occupation}`.toLowerCase().includes(search)).map(v=>`<button data-id="${esc(v.id)}" class="${v.id===selectedId?'selected':''}"><span class="mini-avatar" style="color:${safeColor(v.color)}">${esc(initial(v.name))}</span><span>${esc(v.name)}<small>${esc(v.occupation)} · ${esc(v.action_label||pretty(v.action))}</small></span></button>`).join('')||'<p class="empty-copy">Nobody by that name lives here.</p>';$('#people-list').querySelectorAll('button').forEach(btn=>btn.addEventListener('click',()=>{selectPerson(btn.dataset.id);scene.centerOn(btn.dataset.id,true);}));}
function renderChronicle(){if(!state)return;let events=state.events||[];const filter=$('#event-filter').value;const key=JSON.stringify([events,filter,selectedId]);if(key===chronicleKey)return;chronicleKey=key;
  if(filter==='selected')events=events.filter(e=>e.actor_id===selectedId||e.target_id===selectedId);
  if(filter==='social')events=events.filter(e=>/social|romance|relationship|conversation|gossip|marriage|fight|conflict|birth|family|friend|flirt/.test(e.type||''));
  if(filter==='world')events=events.filter(e=>/oracle|context|world|weather|politics|revolt|festival|harvest|scarcity|threat/.test(e.type||''));
  const list=$('#chronicle-list'),scroll=list.scrollTop;list.innerHTML=events.slice(0,70).map(e=>{const actor=state.villagers.find(v=>v.id===e.actor_id);let copy=esc(e.text);if(actor){const name=esc(actor.name);copy=copy.replace(name,`<strong>${name}</strong>`);}return `<button class="chronicle-event" data-person="${esc(e.actor_id||'')}" data-event="${esc(e.id)}" title="Day ${e.day}${e.source?` · ${esc(e.source)}`:''}"><span class="event-time">${clock(e.minute)}</span><span class="event-dot ${/romance|marriage|flirt/.test(e.type)?'romance':/fight|conflict|revolt/.test(e.type)?'conflict':/oracle|context|world/.test(e.type)?'oracle-event':''}"></span><span class="event-text">${copy}</span></button>`;}).join('')||'<div class="empty-state">A quiet moment in the clearing.<br><span>Life will find a way to surprise you.</span></div>';list.scrollTop=scroll;list.querySelectorAll('button[data-person]').forEach(btn=>btn.addEventListener('click',()=>{if(btn.dataset.person){selectPerson(btn.dataset.person);scene.centerOn(btn.dataset.person,true);}else{const e=events.find(e=>String(e.id)===btn.dataset.event);if(e)toast(e.text);}}));$('#event-count').textContent=`${(state.events||[]).length} moments recorded${filter!=='all'?` · ${events.length} shown`:''}`;
}
function renderProviders(){const key=JSON.stringify([state.mode,state.providers,state.metrics,state.notice,state.last_save]);if(key===providerKey)return;providerKey=key;
  const p=state.providers||{},m=state.metrics||{},diagnosticsOpen=Boolean($('#provider-panel details')?.open);let body='';for(const [name,info] of Object.entries(p)){if(info&&typeof info==='object'){body+=`<p><strong>${esc(pretty(name))}</strong> · ${esc(info.model||'Model not specified')}${info.provider?` via ${esc(info.provider)}`:''} · ${info.configured?'Configured (credentials found)':'Not configured'}${Number(info.cost_usd)>0?` · $${Number(info.cost_usd).toFixed(4)} spent this session`:''}${info.last_error?` · ${esc(info.last_error)}`:''}</p>`;}else body+=`<p>${esc(pretty(name))}: ${esc(info)}</p>`;}
  $('#provider-panel').innerHTML=`<h3>Where decisions and words come from</h3><p>${state.mode==='live'?'Live mode uses Jev for action selection and Luna for thoughts and dialogue. Configuration status confirms credentials are present; completed request counts show actual use.':'Local simulation uses deterministic procedural decisions, thoughts, and dialogue. No model requests are made in this mode.'}</p>${body}${state.notice?`<p>${esc(state.notice)}</p>`:''}<p>Session calls: <strong>${esc(m.session_calls??0)}</strong>${m.session_call_limit?` / ${esc(m.session_call_limit)}`:''} · Requests in flight: <strong>${esc(m.inflight??0)}</strong>${state.last_save?` · Last saved: ${esc(new Date(Number(state.last_save)*1000).toLocaleString())}`:''}</p><details${diagnosticsOpen?' open':''}><summary>Usage and provider diagnostics</summary><pre>${esc(JSON.stringify({providers:p,metrics:m},null,2))}</pre></details>`;
}
function readOracleDraft(){return {text:$('#oracle-input').value,intensity:Number($('#oracle-intensity').value),duration_hours:Number($('#oracle-duration').value)};}
function writeOracleDraft(draft){
  $('#oracle-input').value=draft.text||'';
  const intensity=clamp(draft.intensity??60,0,100);$('#oracle-intensity').value=String(intensity);$('#intensity-value').textContent=`${intensity}%`;
  const select=$('#oracle-duration'),hours=Number(draft.duration_hours)||24;
  if(![...select.options].some(option=>Number(option.value)===hours)){const option=document.createElement('option');option.value=String(hours);option.textContent=`${hours} hours`;option.dataset.custom='true';select.append(option);}
  select.value=String(hours);
}
function updateOracleControls(){
  const submit=$('#oracle-form button[type=submit]'),busy=oracleSubmitting||Boolean(state?.oracle_busy);
  submit.disabled=!state||busy||pending>0;
  submit.innerHTML=busy?(editingScenarioId?'Updating scenario…':'Shaping the world…'):editingScenarioId?'Save changes <span>↗</span>':'Let it be <span>↗</span>';
  $('#oracle-edit-banner').hidden=!editingScenarioId;
  $('#oracle-input-label').textContent=editingScenarioId?'Revise this scenario':'Your scenario';
  $('#oracle-cancel-edit').disabled=oracleSubmitting;
  for(const input of $$('#oracle-form textarea, #oracle-form input, #oracle-form select, #oracle-form [data-preset]'))input.disabled=oracleSubmitting;
  for(const button of $$('#scenario-list button'))button.disabled=!state||pending>0||oracleSubmitting;
}
function editScenario(id){
  const context=state?.contexts?.find(item=>String(item.id)===String(id));if(!context)return;
  if(!editingScenarioId)draftBeforeEdit=readOracleDraft();
  editingScenarioId=String(context.id);writeOracleDraft(context);scenarioKey='';renderScenarios();updateOracleControls();
  $('#oracle-form').scrollIntoView({behavior:'smooth',block:'nearest'});$('#oracle-input').focus();
}
function cancelOracleEdit(restoreDraft=true){
  editingScenarioId=null;if(restoreDraft&&draftBeforeEdit)writeOracleDraft(draftBeforeEdit);draftBeforeEdit=null;scenarioKey='';renderScenarios();updateOracleControls();
}
function scenarioTime(context){
  const now=Number(state.total_minutes??((state.day-1)*1440+state.minute)),remaining=Number(context.expires_at)-now;
  if(!Number.isFinite(remaining))return context.duration_hours?`${Number(context.duration_hours)}h duration`:'Active';
  if(remaining<=0)return 'Ending soon';
  if(remaining<60)return `${Math.ceil(remaining)}m left`;
  if(remaining<1440)return `${Math.ceil(remaining/60)}h left`;
  const days=Math.floor(remaining/1440),hours=Math.ceil((remaining%1440)/60);return `${days}d${hours?` ${hours}h`:''} left`;
}
function renderScenarios(){
  if(!state)return;const contexts=state.contexts||[];
  if(editingScenarioId&&!contexts.some(context=>String(context.id)===editingScenarioId)&&!oracleSubmitting&&!dismissingScenarios.has(editingScenarioId)){
    editingScenarioId=null;draftBeforeEdit=null;scenarioKey='';toast('That scenario has ended. Your edits are kept in the form as a new scenario.');
  }
  const key=JSON.stringify([contexts,contexts.map(scenarioTime),editingScenarioId]);if(key===scenarioKey)return;scenarioKey=key;
  $('#scenario-count').textContent=String(contexts.length);
  $('#scenario-list').innerHTML=contexts.length?contexts.map(context=>`<article class="scenario-card${String(context.id)===editingScenarioId?' is-editing':''}" data-kind="${esc(context.kind)}"><div class="scenario-card-top"><span class="scenario-kind">${esc(pretty(context.kind||'atmosphere'))}</span><span>${esc(scenarioTime(context))}</span></div><p class="scenario-card-text">${esc(context.text)}</p><div class="scenario-card-bottom"><span class="scenario-strength">Intensity ${Math.round(context.intensity||0)}%</span><div class="scenario-card-actions"><button type="button" data-edit-scenario="${esc(context.id)}" aria-label="Edit scenario: ${esc(String(context.text).slice(0,80))}">${String(context.id)===editingScenarioId?'Editing':'Edit'}</button><button type="button" class="scenario-end" data-end-scenario="${esc(context.id)}" aria-label="End scenario: ${esc(String(context.text).slice(0,80))}">End scenario</button></div></div></article>`).join(''):'<p class="scenario-empty">No active scenarios. Write one above to shape the world.</p>';
  $$('#scenario-list [data-edit-scenario]').forEach(button=>button.addEventListener('click',()=>editScenario(button.dataset.editScenario)));
  $$('#scenario-list [data-end-scenario]').forEach(button=>button.addEventListener('click',()=>dismissScenario(button.dataset.endScenario)));
  updateOracleControls();
}
async function dismissScenario(id){
  if(dismissingScenarios.has(id))return;dismissingScenarios.add(id);
  try{const result=await mutate(`/api/oracle/${encodeURIComponent(id)}/dismiss`,{},'Scenario ended. Its influence is gone; the village remembers what happened.');if(result&&editingScenarioId===id)cancelOracleEdit(true);}
  finally{dismissingScenarios.delete(id);renderScenarios();updateOracleControls();}
}

function updateFollow(){scene.follow=following;$('#follow-button').classList.toggle('active',following);$('#follow-button').textContent=following?'◎ Following their day':'◎ Follow their day';$('#follow-button').setAttribute('aria-pressed',String(following));}

$('#play-button').addEventListener('click',()=>state&&mutate('/api/control',{running:!state.running}));
$('#step-button').addEventListener('click',()=>mutate('/api/control',{step:true}));
$('#speed-select').addEventListener('change',e=>mutate('/api/control',{speed:Number(e.target.value)}));
$('#mode-select').addEventListener('change',async e=>{const result=await mutate('/api/control',{mode:e.target.value,running:false},e.target.value==='live'?'Live intelligence selected. Press play when ready.':'Local simulation selected.');if(!result&&state)e.target.value=state.mode;});
$('#save-button').addEventListener('click',()=>mutate('/api/save',{},'Your village has been saved.'));
$('#reset-button').addEventListener('click',async()=>{if(!confirm('Start a new village? This replaces the current world and its memories. Export first if you want to keep a copy.'))return;state=null;detailKey='';headerKey='';selectedId=null;const result=await mutate('/api/reset',{seed:Math.floor(Math.random()*1000000)},'A new chapter begins.');if(result)scene.fit();else await poll();});
$('#help-button').addEventListener('click',()=>$('#help-dialog').showModal());$('#help-dialog').addEventListener('click',e=>{if(e.target===$('#help-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
$('#provider-button').addEventListener('click',()=>{const p=$('#provider-panel');p.hidden=!p.hidden;if(!p.hidden)p.scrollIntoView({behavior:'smooth',block:'nearest'});});
$('#people-button').addEventListener('click',()=>{const p=$('#people-popover');p.hidden=!p.hidden;if(!p.hidden)$('#people-search').focus();});$('#close-people').addEventListener('click',()=>$('#people-popover').hidden=true);$('#people-search').addEventListener('input',renderPeople);
$('#labels-button').addEventListener('click',()=>{scene.labels=!scene.labels;$('#labels-button').setAttribute('aria-pressed',String(scene.labels));});
$('#zoom-in').addEventListener('click',()=>scene.changeZoom(1.25));$('#zoom-out').addEventListener('click',()=>scene.changeZoom(.8));$('#zoom-fit').addEventListener('click',()=>scene.fit());
$('#follow-button').addEventListener('click',()=>{following=!following;updateFollow();if(following)scene.centerOn(selectedId,true);});$('#focus-button').addEventListener('click',()=>scene.centerOn(selectedId,true));
$('#random-person').addEventListener('click',()=>{if(!state)return;const candidates=state.villagers.filter(v=>v.id!==selectedId);const v=candidates[Math.floor(Math.random()*candidates.length)];if(v){selectPerson(v.id);scene.centerOn(v.id,true);}});
$$('[data-tab]').forEach((btn,index)=>{btn.addEventListener('click',()=>{selectedTab=btn.dataset.tab;$$('[data-tab]').forEach(b=>{b.setAttribute('aria-selected',String(b===btn));b.tabIndex=b===btn?0:-1;});$('#person-details').scrollTop=0;renderPerson();});btn.addEventListener('keydown',e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();const tabs=$$('[data-tab]'),next=tabs[(index+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length];next.click();next.focus();}});btn.tabIndex=index===0?0:-1;});
$('#event-filter').addEventListener('change',()=>{chronicleKey='';$('#chronicle-list').scrollTop=0;renderChronicle();});
const presets={doom:'An impending feeling of doom spreads through the village: artificial intelligence is taking over, and nobody is sure what place people will have in the future.',monster:'A colossal Godzilla-like creature is approaching the village from beyond the eastern river. The ground trembles with each distant step.',harvest:'A wonderfully bountiful harvest fills the village storehouses. Food is plentiful, debts feel lighter, and a generous mood is in the air.',festival:'Tonight the village is holding a lantern festival. There will be music, shared food, dancing, and a chance to mend old disagreements.'};
$$('[data-preset]').forEach(btn=>btn.addEventListener('click',()=>{$('#oracle-input').value=presets[btn.dataset.preset];$('#oracle-input').focus();}));
$('#oracle-intensity').addEventListener('input',e=>$('#intensity-value').textContent=`${e.target.value}%`);
$('#oracle-cancel-edit').addEventListener('click',()=>cancelOracleEdit(true));
$('#oracle-form').addEventListener('submit',async e=>{
  e.preventDefault();const draft=readOracleDraft(),text=draft.text.trim();if(!text||oracleSubmitting)return;
  const editingId=editingScenarioId;oracleSubmitting=true;updateOracleControls();
  try{const result=await mutate(editingId?`/api/oracle/${encodeURIComponent(editingId)}/update`:'/api/oracle',{...draft,text},editingId?'Scenario updated. The village is feeling the change.':'Your scenario is now part of the village.');
    if(result){if(editingId)cancelOracleEdit(true);else $('#oracle-input').value='';}
  }finally{oracleSubmitting=false;renderScenarios();updateOracleControls();}
});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){$('#people-popover').hidden=true;following=false;updateFollow();}if(/INPUT|TEXTAREA|SELECT|BUTTON/.test(e.target.tagName)||e.target.isContentEditable||$('#help-dialog').open||e.ctrlKey||e.metaKey||e.altKey)return;if(e.code==='Space'){e.preventDefault();if(!pending&&state)mutate('/api/control',{running:!state.running});}else if(e.key==='.'&&!pending)mutate('/api/control',{step:true});else if(e.key==='+'||e.key==='=')scene.changeZoom(1.2);else if(e.key==='-')scene.changeZoom(1/1.2);else if(e.key==='0')scene.fit();else if(e.key.toLowerCase()==='n')$('#labels-button').click();});
window.addEventListener('beforeunload',()=>{if(state?.running)navigator.sendBeacon?.('/api/save',new Blob(['{}'],{type:'application/json'}));});
updateBusy();poll();setInterval(poll,1100);
