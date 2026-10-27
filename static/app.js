const TOKEN = document.querySelector('meta[name="aicc-token"]').content;
const ACCENTS = ['#5de4ef','#8a8bff','#5fe0a0','#ffb454','#ff7da8','#4d9fff','#e8eef9'];
const DEFAULT_UI = {theme:'auto',accent:'#5de4ef',font_size:14,radius:15,density:'normal',columns:'auto',gradient:true,animations:true,refresh_seconds:5,auto_update_check:true};
let ui = Object.assign({}, DEFAULT_UI, loadLocalUi());
let services = [];
let refreshTimer;

function loadLocalUi(){try{return JSON.parse(localStorage.getItem('aicc-ui')||'{}');}catch(e){return {};}}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function fmt(n){return Number(n).toLocaleString('es-AR');}
function $(id){return document.getElementById(id);}
let toastTimer;
function toast(msg,bad=false){const t=$('toast');t.textContent=msg;t.className='toast show'+(bad?' bad':'');clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.className='toast',4500);}

async function api(path, opts={}){
  const init={method:opts.method||'GET',headers:{'X-AICC-Token':TOKEN}};
  if(opts.body!==undefined){init.method=opts.method||'POST';init.headers['Content-Type']='application/json';init.body=JSON.stringify(opts.body);}
  else if(opts.method){init.method=opts.method;}
  const r=await fetch(path,init);let d={};try{d=await r.json();}catch(e){}
  if(!r.ok||d.ok===false)throw new Error(d.message||('HTTP '+r.status));
  return d;
}
const post=(path,body={})=>api(path,{method:'POST',body});

/* ---------- look & feel ---------- */
function resolvedTheme(){return ui.theme==='auto'?(matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'):ui.theme;}
function applyUi(){
  const root=document.documentElement;
  root.dataset.theme=resolvedTheme();
  root.style.setProperty('--accent',ui.accent);
  root.style.setProperty('--fs',ui.font_size+'px');
  root.style.setProperty('--r',ui.radius+'px');
  root.style.setProperty('--d',{compact:.72,normal:1,comfortable:1.3}[ui.density]||1);
  if(ui.columns==='auto')root.style.removeProperty('--cols');else root.style.setProperty('--cols',ui.columns);
  document.body.classList.toggle('gradient',!!ui.gradient);
  document.body.classList.toggle('no-anim',!ui.animations);
  document.querySelectorAll('[data-set-theme]').forEach(b=>b.classList.toggle('on',b.dataset.setTheme===resolvedTheme()));
  $('footerRefresh').textContent=`Actualización automática cada ${ui.refresh_seconds} segundos`;
  try{localStorage.setItem('aicc-ui',JSON.stringify(ui));}catch(e){}
}
let saveTimer;
function setUi(patch){
  const oldRefresh=ui.refresh_seconds;
  Object.assign(ui,patch);applyUi();syncSettingsForm();
  if(ui.refresh_seconds!==oldRefresh)schedule();
  clearTimeout(saveTimer);saveTimer=setTimeout(()=>post('/api/settings',{ui}).catch(e=>toast(e.message,true)),400);
}
matchMedia('(prefers-color-scheme: light)').addEventListener('change',()=>{if(ui.theme==='auto')applyUi();});
document.querySelectorAll('[data-set-theme]').forEach(b=>b.addEventListener('click',()=>setUi({theme:b.dataset.setTheme})));

function syncSettingsForm(){
  $('setTheme').value=ui.theme;$('setFontSize').value=ui.font_size;$('fontSizeVal').textContent=ui.font_size+' px';
  $('setRadius').value=ui.radius;$('radiusVal').textContent=ui.radius+' px';$('setDensity').value=ui.density;
  $('setColumns').value=ui.columns;$('setGradient').checked=ui.gradient;$('setAnimations').checked=ui.animations;
  $('setRefresh').value=String(ui.refresh_seconds);
  const sw=$('swatches');
  sw.innerHTML=ACCENTS.map(c=>`<button class="swatch${c===ui.accent?' on':''}" style="background:${c}" data-accent="${c}" title="${c}" aria-label="Acento ${c}"></button>`).join('')+
    `<input type="color" id="setAccentCustom" value="${esc(ui.accent)}" title="Elegir otro color">`;
  sw.querySelectorAll('[data-accent]').forEach(b=>b.onclick=()=>setUi({accent:b.dataset.accent}));
  $('setAccentCustom').oninput=e=>setUi({accent:e.target.value});
}
function bindSettings(){
  $('setTheme').onchange=e=>setUi({theme:e.target.value});
  $('setFontSize').oninput=e=>setUi({font_size:+e.target.value});
  $('setRadius').oninput=e=>setUi({radius:+e.target.value});
  $('setDensity').onchange=e=>setUi({density:e.target.value});
  $('setColumns').onchange=e=>setUi({columns:e.target.value});
  $('setGradient').onchange=e=>setUi({gradient:e.target.checked});
  $('setAnimations').onchange=e=>setUi({animations:e.target.checked});
  $('setRefresh').onchange=e=>setUi({refresh_seconds:+e.target.value});
  $('setAutoUpdate').onchange=e=>setUi({auto_update_check:e.target.checked});
  $('setPanelAutostart').onchange=async e=>{
    try{await post('/api/settings',{panel_autostart:e.target.checked});toast(e.target.checked?'El panel se abrirá al iniciar sesión.':'El panel ya no se abrirá al iniciar sesión.');}
    catch(err){toast(err.message,true);e.target.checked=!e.target.checked;}
  };
}
function openSettings(){syncSettingsForm();$('settingsOverlay').hidden=false;}
function closeSettings(){$('settingsOverlay').hidden=true;}
function resetSettings(){if(confirm('¿Volver a la apariencia original?'))setUi(Object.assign({},DEFAULT_UI));}
function closeModal(id){$(id).hidden=true;}
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeSettings();closeModal('locationOverlay');closeModal('uninstallOverlay');closeModal('updateOverlay');closeModal('customOverlay');if($('donateOverlay'))closeModal('donateOverlay');}});
function openDonate(){$('donateOverlay').hidden=false;}
function copyText(t){navigator.clipboard.writeText(t).then(()=>toast('Copiado'),()=>toast(t));}

/* ---------- services ---------- */
function stateInfo(s){
  const map={active:'Activo',running:'Activo',external:'Activo (fuera del panel)',inactive:'Detenido',exited:'Detenido',created:'Detenido',
    failed:'Con error',missing:'No encontrado',activating:'Iniciando…',deactivating:'Deteniendo…',restarting:'Reiniciando…'};
  const cls=s.running?'running':(['missing','failed','unknown'].includes(s.state)?'error':'');
  return [map[s.state]||s.state,cls];
}
function metricsBlock(s){
  const m=s.metrics||{};
  if(!s.running)return `<div class="service-metrics unavailable"><span>CPU</span><b>—</b><span>RAM</span><b>—</b><small>Servicio detenido</small></div>`;
  const val=v=>v==null?'N/D':`${Math.round(v)}%`;const bar=v=>v==null?0:Math.max(0,Math.min(100,v));
  const ramDetail=m.ram_mb==null?'No disponible':`${fmt(m.ram_mb)} MB${m.ram_total_mb?` / ${fmt(m.ram_total_mb)} MB`:''}`;
  return `<div class="service-metrics">
    <div class="service-metric"><div class="service-metric-heading"><span>CPU</span><b>${val(m.cpu_percent)}</b></div><div class="service-meter"><i style="width:${bar(m.cpu_percent)}%"></i></div></div>
    <div class="service-metric"><div class="service-metric-heading"><span>RAM</span><b>${val(m.ram_percent)}</b></div><div class="service-meter ram"><i style="width:${bar(m.ram_percent)}%"></i></div><small>${esc(ramDetail)}</small></div></div>`;
}
function serviceCard(s){
  const [stateText,stateClass]=stateInfo(s);
  const missing=s.state==='missing';const id=esc(s.id);
  const own=s.running&&s.state!=='external';  // started outside the panel: we can't stop it
  const autostartTitle=s.type==='docker'?'Docker reinicia el contenedor al arrancar el equipo':s.type==='systemd'?'Servicio del sistema: arranca con el equipo':s.type==='app'?'La app se abre al iniciar tu sesión':'Se inicia al iniciar tu sesión';
  const upd=s.update&&s.update.available;
  const link=s.web!==false&&s.port?`<a class="service-link" href="${esc(s.url)}" target="_blank" rel="noopener">Abrir interfaz ↗</a>`:(s.homepage?`<a class="service-link" href="${esc(s.homepage)}" target="_blank" rel="noopener">Sitio oficial ↗</a>`:'<span></span>');
  return `<article class="service-card">
    <div class="service-top"><div class="service-icon">${esc(s.icon)}</div><div style="min-width:0"><div class="service-name">${esc(s.name)}${upd?' <span class="badge-new">Actualización disponible</span>':''}</div>
      <div class="service-type">${esc(s.description)}${s.port?` · puerto ${s.port}`:''}</div><div class="service-type" title="${esc(s.location)}">${esc(s.location)}${s.source==='manual'?' · manual':''}</div></div>
      <span class="state ${stateClass}">${esc(stateText)}</span></div>
    ${metricsBlock(s)}
    <div class="service-options">
      <label class="toggle" title="${esc(autostartTitle)}"><input type="checkbox" ${s.autostart?'checked':''} ${missing||s.autostart===null?'disabled':''} onchange="toggleAutostart('${id}',this)"> Iniciar al iniciar sesión</label>
      <div class="mini-actions">${s.custom?'':`<button class="action ghost" onclick="openLocation('${id}')">Cambiar ubicación</button>`}<button class="action ghost danger" onclick="openUninstall('${id}')">Desinstalar…</button></div>
    </div>
    <div class="service-bottom">${link}
      <div class="service-actions"><button class="action primary" ${s.running||missing?'disabled':''} onclick="serviceAction('${id}','start',this)">Iniciar</button><button class="action danger" ${!own?'disabled':''} onclick="serviceAction('${id}','stop',this)">Detener</button><button class="action" ${!own?'disabled':''} onclick="serviceAction('${id}','restart',this)">Reiniciar</button><button class="action${upd?' primary':''}" ${missing?'disabled':''} onclick="openUpdate('${id}')">${s.updating?'Actualizando…':'Actualizar'}</button></div></div>
  </article>`;
}
function missingCard(s){
  return `<div class="missing-card"><div class="service-icon">${esc(s.icon)}</div><div class="info"><b>${esc(s.name)}</b><small>${esc(s.description)} · no se encontró instalada</small></div>
    <button class="action" onclick="openLocation('${esc(s.id)}')">Indicar ruta</button></div>`;
}
async function refreshAll(){
  try{
    const data=await api('/api/status');
    services=data.services;
    const installed=services.filter(s=>s.installed),missing=services.filter(s=>!s.installed);
    $('serviceGrid').innerHTML=installed.length?installed.map(serviceCard).join(''):'<div class="empty">No se detectó ninguna IA. Usá "Indicar ruta" abajo o "Detectar de nuevo".</div>';
    $('missingWrap').hidden=!missing.length;$('missingGrid').innerHTML=missing.map(missingCard).join('');
    $('missingToggle').textContent=`${missingOpen?'▾':'▸'} No detectadas (${missing.length})`;$('missingBody').hidden=!missingOpen;
    $('notes').innerHTML=(data.notes||[]).map(n=>`<div class="note">${esc(n)}</div>`).join('');
    $('activeCount').textContent=installed.filter(s=>s.running).length;$('serviceCount').textContent=installed.length;
    const m=data.metrics;const pct=v=>v==null?'N/D':Math.round(v)+'%';
    ['cpu','cpu2'].forEach(i=>$(i).textContent=pct(m.cpu_percent));setBar('cpuBar',m.cpu_percent);setBar('cpuBar2',m.cpu_percent);
    ['ram','ram2'].forEach(i=>$(i).textContent=pct(m.ram_percent));setBar('ramBar',m.ram_percent);setBar('ramBar2',m.ram_percent);
    $('ramDetail').textContent=m.ram_used_mb==null?'Métricas no disponibles':`${fmt(m.ram_used_mb)} / ${fmt(m.ram_total_mb)} MB`;
    const g=m.gpu;
    ['gpu','gpu2'].forEach(i=>$(i).textContent=g?g.util_percent+'%':'N/D');setBar('gpuBar',g?g.util_percent:null);setBar('gpuBar2',g?g.util_percent:null);
    $('gpuDetail').textContent=g?`${fmt(g.vram_used_mb)} / ${fmt(g.vram_total_mb)} MB VRAM · ${g.temperature_c}°C`:'GPU no disponible';
    $('gpuError').textContent=m.gpu_error||(g?`${g.name} · ${fmt(g.vram_used_mb)} MB de VRAM ocupados.`:'');
    renderModels(data.models);
    $('lastUpdated').textContent='Actualizado '+new Date(data.timestamp*1000).toLocaleTimeString();
  }catch(e){toast('No se pudo consultar el panel: '+e.message,true);}
}
function setBar(id,v){$(id).style.width=(v==null?0:Math.max(0,Math.min(100,v)))+'%';}
function schedule(){clearInterval(refreshTimer);refreshTimer=setInterval(()=>{if(!document.hidden)refreshAll();},ui.refresh_seconds*1000);}
function renderModels(models){
  const box=$('modelsBox');
  if(models===null){box.innerHTML='<div class="empty">Ollama no responde. Comprobá que el servicio esté iniciado.</div>';return;}
  if(!models.length){box.innerHTML='<div class="empty">No hay modelos cargados en memoria en este momento.</div>';return;}
  box.innerHTML=models.map(m=>{
    const name=m.name||m.model||'Modelo';
    const size=m.size?`${(m.size/1073741824).toFixed(2)} GB`:'Tamaño no informado';
    const vram=m.size_vram?` · VRAM ${(m.size_vram/1048576).toFixed(0)} MB`:'';
    return `<div class="model-row"><div class="model-symbol">◉</div><div class="model-info"><b>${esc(name)}</b><small>${esc(size)}${esc(vram)}${m.expires_at?' · sesión activa':''}</small></div><button class="action danger" data-model="${esc(name)}" onclick="unloadModel(this.dataset.model,this)">Descargar de memoria</button></div>`;
  }).join('');
}
const byId=id=>services.find(s=>s.id===id)||{id,name:id};
async function serviceAction(id,action,btn){
  if(action==='stop'&&!confirm(`¿Detener ${byId(id).name}? Las sesiones activas de ese servicio pueden interrumpirse.`))return;
  btn.disabled=true;
  try{const d=await post(`/api/service/${encodeURIComponent(id)}/${action}`);toast(d.message);setTimeout(refreshAll,900);}
  catch(e){toast(e.message,true);refreshAll();}
}
async function toggleAutostart(id,input){
  const enabled=input.checked;input.disabled=true;
  try{const d=await post(`/api/service/${encodeURIComponent(id)}/autostart`,{enabled});toast(d.message);}
  catch(e){toast(e.message,true);input.checked=!enabled;}
  finally{input.disabled=false;}
}
async function redetect(btn){
  btn.disabled=true;btn.textContent='Buscando…';
  try{const d=await post('/api/detect');toast(d.message);await refreshAll();}
  catch(e){toast(e.message,true);}
  finally{btn.disabled=false;btn.textContent='⟳ Detectar de nuevo';}
}
async function unloadModel(name,btn){
  if(!confirm(`¿Descargar "${name}" de la memoria? No se borrará del disco.`))return;
  btn.disabled=true;
  try{const d=await post('/api/model/unload',{name});toast(d.message);setTimeout(refreshAll,1500);}
  catch(e){toast(e.message,true);btn.disabled=false;}
}

/* ---------- location dialog ---------- */
let locService=null,locType='path';
function setLocType(t){
  locType=t;document.querySelectorAll('[data-loc-type]').forEach(b=>b.classList.toggle('on',b.dataset.locType===t));
  $('locPath').hidden=t!=='path';$('locDocker').hidden=t!=='docker';
}
document.querySelectorAll('[data-loc-type]').forEach(b=>b.onclick=()=>{setLocType(b.dataset.locType);if(b.dataset.locType==='docker')loadContainers();});
async function loadContainers(){
  const sel=$('locContainer');sel.innerHTML='<option>Cargando…</option>';
  try{const d=await api('/api/docker/containers');
    if(d.error){sel.innerHTML=`<option value="">${esc(d.error)}</option>`;return;}
    sel.innerHTML=d.containers.length?d.containers.map(c=>`<option value="${esc(c.name)}">${esc(c.name)} · ${esc(c.image)} · ${esc(c.state)}</option>`).join(''):'<option value="">No hay contenedores</option>';
  }catch(e){sel.innerHTML=`<option value="">${esc(e.message)}</option>`;}
}
function openLocation(id){
  const s=byId(id);locService=s;
  $('locTitle').textContent=`Ubicación de ${s.name}`;$('locHint').textContent=s.manual_hint||'';
  $('locTabs').hidden=!(s.accepts_docker&&s.accepts_path);
  $('locPathInput').value=s.type==='process'?s.location:'';$('locPythonInput').value='';$('locPortInput').value='';
  $('locPythonField').hidden=!['comfyui','fooocus','text-generation-webui'].includes(s.id);
  $('locPathInput').placeholder={comfyui:'/home/usuario/ComfyUI',ollama:'/usr/local/bin/ollama','open-webui':'/home/usuario/.local/bin/open-webui','lm-studio':'/home/usuario/Applications/LM-Studio.AppImage'}[s.id]||'/home/usuario/...';
  $('locCandidates').innerHTML=(s.candidates||[]).map(c=>`<option value="${esc(c)}">`).join('');
  setLocType(s.type==='docker'||!s.accepts_path?'docker':'path');
  if(locType==='docker')loadContainers();
  $('locationOverlay').hidden=false;
  if(locType==='path')$('locPathInput').focus();
}
$('locSave').onclick=async()=>{
  const body=locType==='docker'?{type:'docker',container:$('locContainer').value}:{type:'path',path:$('locPathInput').value,python:$('locPythonInput').value,port:$('locPortInput').value||null};
  if(locType==='docker'&&!body.container){toast('Elegí un contenedor.',true);return;}
  try{const d=await post(`/api/service/${encodeURIComponent(locService.id)}/location`,body);toast(d.message);closeModal('locationOverlay');refreshAll();}
  catch(e){toast(e.message,true);}
};

/* ---------- uninstall dialog ---------- */
let unService=null;
async function openUninstall(id){
  const s=byId(id);unService=s;
  $('unTitle').textContent=`Desinstalar ${s.name}`;$('unName').textContent=s.name;$('unConfirm').value='';
  $('unItems').innerHTML='<div class="empty">Revisando qué hay instalado…</div>';$('unNotes').textContent='';$('unResults').innerHTML='';
  $('unGo').disabled=true;$('uninstallOverlay').hidden=false;
  try{
    const d=await api(`/api/service/${encodeURIComponent(id)}/uninstall-plan`);
    const size=mb=>mb==null?'':` · ${mb>=1024?(mb/1024).toFixed(1)+' GB':mb+' MB'}`;
    const group=(g,title)=>{const items=d.items.filter(i=>i.group===g);if(!items.length)return '';
      return `<p class="un-group">${title}</p>`+items.map(i=>`<label class="un-item"><input type="checkbox" value="${esc(i.key)}" ${i.default?'checked':''} onchange="checkUninstall()"><span><b>${esc(i.label)}${i.root?' 🔒':''}</b><small>${esc(i.detail)}${size(i.size_mb)}</small></span></label>`).join('');};
    $('unItems').innerHTML=group('program','Programa')+group('data','Datos (modelos, archivos generados, configuraciones)')||'<div class="empty">No hay nada para quitar.</div>';
    $('unNotes').innerHTML=(d.notes||[]).map(esc).join('<br>');
  }catch(e){$('unItems').innerHTML=`<div class="empty">${esc(e.message)}</div>`;}
}
function checkUninstall(){
  const any=[...document.querySelectorAll('#unItems input:checked')].length>0;
  $('unGo').disabled=!(any&&unService&&$('unConfirm').value.trim().toLowerCase()===unService.name.toLowerCase());
}
$('unConfirm').oninput=checkUninstall;
$('unGo').onclick=async()=>{
  const keys=[...document.querySelectorAll('#unItems input:checked')].map(i=>i.value);
  $('unGo').disabled=true;$('unResults').innerHTML='<div>Desinstalando… puede pedir la contraseña de administrador.</div>';
  try{
    const r=await fetch(`/api/service/${encodeURIComponent(unService.id)}/uninstall`,{method:'POST',headers:{'X-AICC-Token':TOKEN,'Content-Type':'application/json'},body:JSON.stringify({keys,confirm:$('unConfirm').value})});
    const d=await r.json();
    $('unResults').innerHTML=(d.results||[]).map(x=>`<div class="${x.ok?'ok':'bad'}">${x.ok?'✓':'✕'} ${esc(x.label)}: ${esc(x.message)}</div>`).join('')+`<div><b>${esc(d.message)}</b></div>`;
    toast(d.message,!d.ok);refreshAll();
  }catch(e){$('unResults').innerHTML=`<div class="bad">${esc(e.message)}</div>`;}
};

/* ---------- not detected list ---------- */
let missingOpen=false;
try{missingOpen=localStorage.getItem('aicc-missing-open')==='1';}catch(e){}
function toggleMissing(){
  missingOpen=!missingOpen;$('missingBody').hidden=!missingOpen;$('missingToggle').setAttribute('aria-expanded',missingOpen);
  $('missingToggle').textContent=$('missingToggle').textContent.replace(/^[▸▾]/,missingOpen?'▾':'▸');
  try{localStorage.setItem('aicc-missing-open',missingOpen?'1':'0');}catch(e){}
}
async function checkUpdates(btn){
  btn.disabled=true;
  try{const d=await post('/api/check-updates');toast(d.message);setTimeout(refreshAll,15000);}catch(e){toast(e.message,true);}
  finally{setTimeout(()=>btn.disabled=false,5000);}
}

/* ---------- custom AI dialog ---------- */
let cuType='path';
function setCuType(t){cuType=t;document.querySelectorAll('[data-cu-type]').forEach(b=>b.classList.toggle('on',b.dataset.cuType===t));$('cuPath').hidden=t!=='path';$('cuDocker').hidden=t!=='docker';
  if(t==='docker'){const sel=$('cuContainer');sel.innerHTML='<option>Cargando…</option>';api('/api/docker/containers').then(d=>{sel.innerHTML=d.error?`<option value="">${esc(d.error)}</option>`:(d.containers.map(c=>`<option value="${esc(c.name)}">${esc(c.name)} · ${esc(c.image)}</option>`).join('')||'<option value="">No hay contenedores</option>');}).catch(e=>sel.innerHTML=`<option value="">${esc(e.message)}</option>`);}}
document.querySelectorAll('[data-cu-type]').forEach(b=>b.onclick=()=>setCuType(b.dataset.cuType));
function openCustom(){['cuLabel','cuDesc','cuFolder','cuCommand','cuPort'].forEach(i=>$(i).value='');setCuType('path');$('customOverlay').hidden=false;$('cuLabel').focus();}
$('cuSave').onclick=async()=>{
  const body={label:$('cuLabel').value,description:$('cuDesc').value,type:cuType,port:$('cuPort').value||null,
    path:$('cuFolder').value,command:$('cuCommand').value,container:$('cuContainer').value};
  try{const d=await post('/api/custom',body);toast(d.message);closeModal('customOverlay');refreshAll();}catch(e){toast(e.message,true);}
};

/* ---------- update dialog ---------- */
let upService=null,upTimer=null;
async function openUpdate(id){
  const s=byId(id);upService=s;clearInterval(upTimer);
  $('upTitle').textContent=`Actualizar ${s.name}`;$('upResult').innerHTML='';$('upLog').hidden=true;$('upLog').textContent='';
  $('upGo').disabled=true;$('upGo').hidden=false;$('upInfo').innerHTML='<div class="empty">Buscando la última versión…</div>';
  $('updateOverlay').hidden=false;
  if(s.updating){$('upInfo').innerHTML='';$('upGo').hidden=true;followJob(`/api/service/${encodeURIComponent(id)}/job`);return;}
  try{
    const d=await api(`/api/service/${encodeURIComponent(id)}/update-info`);
    const row=(k,v,cls='')=>v?`<div class="row"><span>${k}</span><b class="${cls}">${esc(v)}</b></div>`:'';
    let html=row('Versión instalada',d.current)+row('Última versión',d.latest,d.up_to_date?'ok':'new');
    if(d.up_to_date===true)html+='<div class="row"><span>Estado</span><b class="ok">Ya tenés la última versión</b></div>';
    html+=`<p class="hint">${esc(d.method)}</p>`+(d.warning?`<p class="warn">${esc(d.warning)}</p>`:'');
    $('upInfo').innerHTML=html;
    $('upGo').disabled=!d.supported;$('upGo').textContent=d.up_to_date===true?'Reinstalar igual':'Actualizar ahora';
  }catch(e){$('upInfo').innerHTML=`<div class="empty">${esc(e.message)}</div>`;}
}
$('upGo').onclick=async()=>{
  if(['active','running','external'].includes(upService.state)&&!confirm(`${upService.name} se va a reiniciar durante la actualización. ¿Seguimos?`))return;
  $('upGo').disabled=true;
  try{const d=await post(`/api/service/${encodeURIComponent(upService.id)}/update`);followJob(`/api/jobs/${d.job}`);refreshAll();}
  catch(e){toast(e.message,true);$('upGo').disabled=false;}
};
function followJob(url){
  $('upLog').hidden=false;$('upGo').hidden=true;$('upResult').innerHTML='<p class="hint">Actualizando… podés cerrar esta ventana, sigue en segundo plano.</p>';
  const tick=async()=>{
    try{const j=await api(url);const log=$('upLog');const atEnd=log.scrollTop+log.clientHeight>=log.scrollHeight-20;
      log.textContent=j.log.join('\n');if(atEnd)log.scrollTop=log.scrollHeight;
      if(j.state!=='running'){clearInterval(upTimer);$('upResult').innerHTML=`<p class="${j.state==='done'?'up-result-ok':'up-result-bad'}">${esc(j.message)}</p>`;toast(j.message,j.state!=='done');refreshAll();}
    }catch(e){clearInterval(upTimer);}
  };
  clearInterval(upTimer);tick();upTimer=setInterval(tick,1000);
}

/* ---------- start ---------- */
applyUi();bindSettings();
api('/api/settings').then(d=>{ui=Object.assign({},DEFAULT_UI,d.ui);applyUi();$('setPanelAutostart').checked=d.panel_autostart;$('setAutoUpdate').checked=d.ui.auto_update_check!==false;schedule();}).catch(()=>schedule());
refreshAll();
