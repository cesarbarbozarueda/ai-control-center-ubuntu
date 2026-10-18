const icons = {'ollama':'◉','open-webui':'▦','immich':'▧','comfyui':'✧'};
const descriptions = {
  'ollama':'Motor de modelos locales · puerto 11434',
  'open-webui':'Interfaz de chat · puerto 3000 · Docker',
  'immich':'Servidor de fotos · puerto 2283 · Docker',
  'comfyui':'Generación de imágenes · puerto 8188'
};
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
let toastTimer;
function toast(msg,bad=false){const t=document.getElementById('toast');t.textContent=msg;t.className='toast show'+(bad?' bad':'');clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.className='toast',4000);}
function serviceCard(s){
  const stateText = s.state==='active'||s.state==='running'?'Activo':s.state==='inactive'||s.state==='exited'?'Detenido':s.state==='missing'?'No encontrado':s.state;
  const stateClass = s.running?'running':(['missing','unavailable','failed','unknown'].includes(s.state)?'error':'');
  const busy = s.state==='missing'||s.state==='unavailable';
  return `<article class="service-card"><div class="service-top"><div class="service-icon">${icons[s.id]||'◈'}</div><div><div class="service-name">${esc(s.name)}</div><div class="service-type">${esc(descriptions[s.id]||s.kind)}</div></div><span class="state ${stateClass}">${esc(stateText)}</span></div><div class="service-bottom"><a class="service-link" href="${esc(s.url)}" target="_blank" rel="noopener">Abrir interfaz ↗</a><div class="service-actions"><button class="action primary" ${s.running||busy?'disabled':''} onclick="serviceAction('${esc(s.id)}','start',this)">Iniciar</button><button class="action danger" ${!s.running?'disabled':''} onclick="serviceAction('${esc(s.id)}','stop',this)">Detener</button><button class="action" ${!s.running?'disabled':''} onclick="serviceAction('${esc(s.id)}','restart',this)">Reiniciar</button></div></div></article>`;
}
async function refreshAll(){
  try{
    const res=await fetch('/api/status',{cache:'no-store'});if(!res.ok)throw new Error('HTTP '+res.status);
    const data=await res.json();
    document.getElementById('serviceGrid').innerHTML=data.services.map(serviceCard).join('');
    const active=data.services.filter(s=>s.running).length;
    document.getElementById('activeCount').textContent=active;
    document.getElementById('serviceCount').textContent=data.services.length;
    const m=data.metrics;
    document.getElementById('cpu').textContent=m.cpu_percent==null?'N/D':Math.round(m.cpu_percent)+'%';
    document.getElementById('cpu2').textContent=m.cpu_percent==null?'N/D':Math.round(m.cpu_percent)+'%';
    setBar('cpuBar',m.cpu_percent);setBar('cpuBar2',m.cpu_percent);
    document.getElementById('ram').textContent=m.ram_percent==null?'N/D':Math.round(m.ram_percent)+'%';
    document.getElementById('ram2').textContent=m.ram_percent==null?'N/D':Math.round(m.ram_percent)+'%';
    document.getElementById('ramDetail').textContent=m.ram_used_mb==null?'Métricas no disponibles':`${fmt(m.ram_used_mb)} / ${fmt(m.ram_total_mb)} MB`;
    setBar('ramBar',m.ram_percent);setBar('ramBar2',m.ram_percent);
    const g=m.gpu;
    document.getElementById('gpu').textContent=g?g.util_percent+'%':'N/D';
    document.getElementById('gpu2').textContent=g?g.util_percent+'%':'N/D';
    document.getElementById('gpuDetail').textContent=g?`${fmt(g.vram_used_mb)} / ${fmt(g.vram_total_mb)} MB VRAM · ${g.temperature_c}°C`:'GPU no disponible';
    setBar('gpuBar',g?g.util_percent:null);setBar('gpuBar2',g?g.util_percent:null);
    document.getElementById('gpuError').textContent=m.gpu_error|| (g?`${g.name} · ${fmt(g.vram_used_mb)} MB de VRAM ocupados.`:'');
    renderModels(data.models);
    document.getElementById('lastUpdated').textContent='Actualizado '+new Date(data.timestamp*1000).toLocaleTimeString();
  }catch(e){toast('No se pudo consultar el panel: '+e.message,true);}
}
function fmt(n){return Number(n).toLocaleString('es-AR');}
function setBar(id,v){document.getElementById(id).style.width=(v==null?0:Math.max(0,Math.min(100,v)))+'%';}
function renderModels(models){
  const box=document.getElementById('modelsBox');
  if(models===null){box.innerHTML='<div class="empty">Ollama no responde. Comprobá que el servicio esté iniciado.</div>';return;}
  if(!models.length){box.innerHTML='<div class="empty">No hay modelos cargados en memoria en este momento.</div>';return;}
  box.innerHTML=models.map(m=>{
    const name=m.name||m.model||'Modelo';
    const size=m.size?`${(m.size/1073741824).toFixed(2)} GB`:'Tamaño no informado';
    const vram=m.size_vram?` · VRAM ${ (m.size_vram/1048576).toFixed(0)} MB`:'';
    return `<div class="model-row"><div class="model-symbol">◉</div><div class="model-info"><b>${esc(name)}</b><small>${esc(size)}${esc(vram)}${m.expires_at?' · sesión activa':''}</small></div><button class="action danger" onclick="unloadModel('${esc(name)}',this)">Descargar de memoria</button></div>`;
  }).join('');
}
async function serviceAction(id,action,btn){
  if(action==='stop'&&!confirm(`¿Detener ${id}? Las sesiones activas de ese servicio pueden interrumpirse.`))return;
  btn.disabled=true;
  try{const r=await fetch(`/api/service/${encodeURIComponent(id)}/${action}`,{method:'POST'});const d=await r.json();if(!r.ok||!d.ok)throw new Error(d.message||'Operación fallida');toast(d.message);setTimeout(refreshAll,700);}
  catch(e){toast(e.message,true);refreshAll();}
}
async function unloadModel(name,btn){
  if(!confirm(`¿Descargar "${name}" de la memoria? No se borrará del disco.`))return;
  btn.disabled=true;
  try{const r=await fetch('/api/model/unload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});const d=await r.json();if(!r.ok||!d.ok)throw new Error(d.message||'Operación fallida');toast(d.message);setTimeout(refreshAll,1500);}
  catch(e){toast(e.message,true);btn.disabled=false;}
}
refreshAll();setInterval(refreshAll,5000);
