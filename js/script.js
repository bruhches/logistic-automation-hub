const API='http://127.0.0.1:5000';let token=null;let currentProcess=null;let currentFindings=[];

// V1.0 - autenticação local e experiência operacional consolidada
let authMode='login';
async function authStatus(){
  try{const r=await fetch(`${API}/api/auth/status`);const d=await r.json();
    if(d.authenticated){authGate.classList.add('hidden');currentUser.textContent=d.user.nome;logoutBtn.classList.remove('hidden');return true;}
    authGate.classList.remove('hidden');logoutBtn.classList.add('hidden');authMode=d.configured?'login':'setup';setupNameWrap.classList.toggle('hidden',authMode!=='setup');authTitle.textContent=authMode==='setup'?'Configuração inicial':'Entrar no Hub';authText.textContent=authMode==='setup'?'Crie o primeiro operador local. A senha é armazenada como hash no SQLite.':'Informe suas credenciais para acessar a operação.';authSubmit.textContent=authMode==='setup'?'Criar operador e entrar':'Entrar';return false;
  }catch{authMessage.textContent='Não foi possível conectar ao servidor local.';return false;}
}
authSubmit.onclick=async()=>{authMessage.textContent='';const payload={username:authUser.value,password:authPassword.value,nome:setupName.value};const endpoint=authMode==='setup'?'/api/auth/setup':'/api/auth/login';try{const r=await fetch(`${API}${endpoint}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const d=await r.json();if(!r.ok)throw Error(d.error);authPassword.value='';await authStatus();await refreshProtected();}catch(e){authMessage.textContent=e.message;}};
authPassword.addEventListener('keydown',e=>{if(e.key==='Enter')authSubmit.click();});
logoutBtn.onclick=async()=>{await fetch(`${API}/api/auth/logout`,{method:'POST'});currentUser.textContent='Acesso protegido';await authStatus();};
async function refreshProtected(){dashboard();loadOperationalDashboard();loadHistory();loadRules();loadLogs();}
const modules=[{icon:'📊',name:'Spreadsheet Automation',status:'FUNCIONAL V1.0',desc:'Analisa com regras operacionais configuráveis e mantém histórico auditável no SQLite.',tags:['Python','Pandas','OpenPyXL','SQLite']},{icon:'📁',name:'File Organizer',status:'PLANEJADO',desc:'Classifica documentos e organiza arquivos por regras operacionais.',tags:['Python','Filesystem','XML']},{icon:'📧',name:'Daily Report',status:'PLANEJADO',desc:'Consolida mensagens e pendências em relatório operacional.',tags:['Python','Microsoft Graph','API']}];
moduleGrid.innerHTML=modules.map(m=>`<article class="card"><span class="badge">${m.status}</span><div class="icon">${m.icon}</div><h4>${m.name}</h4><p>${m.desc}</p><div class="tags">${m.tags.map(t=>`<span class="tag">${t}</span>`).join('')}</div></article>`).join('');
const esc=v=>String(v??'').replace(/[&<>"']/g,s=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[s]));
const fmtDate=v=>v?new Date(v).toLocaleString('pt-BR'):'—';
function msg(t,e=false){message.textContent=t;message.className='message'+(e?' error':'')}
async function health(){try{let r=await fetch(`${API}/api/health`);if(!r.ok)throw 0;let d=await r.json();apiStatus.textContent='ONLINE';apiDetail.textContent=`Flask + SQLite · v${d.version}`;}catch{apiStatus.textContent='OFFLINE';apiDetail.textContent='Execute: python python/app.py';}}

function formatDuration(minutes){
  if(minutes===null||minutes===undefined)return '—';
  const m=Math.round(Number(minutes));
  if(m<60)return `${m} min`;
  const h=Math.floor(m/60), rem=m%60;
  return rem?`${h}h ${rem}min`:`${h}h`;
}
async function loadOperationalDashboard(){
  try{
    const r=await fetch(`${API}/api/operations/dashboard`);
    if(!r.ok)return;
    const d=await r.json();
    const set=(id,value)=>{const el=document.getElementById(id);if(el)el.textContent=value;};
    set('kpiTotal',d.total||0); set('kpiWaiting',d.waiting||0); set('kpiYard',d.yard||0);
    set('kpiActive',d.active||0); set('kpiFinished',d.finished||0); set('kpiCompleted',d.completed||0);
    set('kpiAvgWait',formatDuration(d.avg_wait_minutes));
    set('kpiAvgOperation',formatDuration(d.avg_operation_minutes));
    set('kpiAvgPermanence',formatDuration(d.avg_permanence_minutes));
    const labels={'AGUARDANDO':'Aguardando','NO PÁTIO':'No pátio','EM OPERAÇÃO':'Em operação','FINALIZADO':'Finalizado','CONCLUÍDA':'Concluída','CANCELADO':'Cancelado'};
    const status=document.getElementById('statusOverview');
    if(status){
      const total=Math.max(d.total||0,1);
      status.innerHTML=Object.entries(labels).map(([key,label])=>{
        const n=(d.by_status&&d.by_status[key])||0, pct=Math.round(n*100/total);
        return `<div class="status-bar-row"><div><span>${label}</span><strong>${n}</strong></div><progress max="100" value="${pct}"></progress><small>${pct}%</small></div>`;
      }).join('');
    }
    const body=document.getElementById('dashboardRecentBody');
    if(body)body.innerHTML=(d.recent||[]).length?(d.recent||[]).map(x=>`<tr><td><strong>${esc(x.operation_code)}</strong></td><td>${esc(x.status)}</td><td>${esc(x.placa||'—')}</td><td>${esc(x.motorista||'—')}</td><td>${esc(x.doca||'—')}</td></tr>`).join(''):'<tr><td colspan="5">Nenhuma operação cadastrada.</td></tr>';
  }catch(e){}
}

async function dashboard(){try{let d=await (await fetch(`${API}/api/dashboard`)).json();dbFiles.textContent=d.files;dbRecords.textContent=d.records;dbOccurrences.textContent=d.occurrences;dbDecisions.textContent=d.decisions;dbKeep.textContent=d.keep;dbRemove.textContent=d.remove;dbReview.textContent=d.review;}catch{}}
async function loadHistory(){try{let r=await fetch(`${API}/api/history`);let d=await r.json();historyBody.innerHTML=d.history.length?d.history.map(x=>`<tr><td><strong>${esc(x.process_code)}</strong></td><td>${esc(x.arquivo)}</td><td>${fmtDate(x.data)}</td><td>${x.registros}</td><td>${x.ocorrencias}</td><td>${x.manter||0}</td><td>${x.remover||0}</td><td>${x.revisar||0}</td><td>${esc(x.status)}</td><td><button class="mini history-open" data-code="${esc(x.process_code)}">Abrir</button></td></tr>`).join(''):'<tr><td colspan="10">Nenhum processamento registrado.</td></tr>';document.querySelectorAll('.history-open').forEach(b=>b.onclick=()=>openHistory(b.dataset.code));}catch{historyBody.innerHTML='<tr><td colspan="10">Não foi possível carregar o histórico.</td></tr>';}}
async function openHistory(code){try{let r=await fetch(`${API}/api/history/${encodeURIComponent(code)}`);let d=await r.json();if(!r.ok)throw Error(d.error);historyDetail.classList.remove('hidden');historyDetailTitle.textContent=`${d.process.process_code} · ${d.process.arquivo}`;historyMeta.innerHTML=`<span><small>Iniciado</small><strong>${fmtDate(d.process.data)}</strong></span><span><small>Finalizado</small><strong>${fmtDate(d.process.finalizado_em)}</strong></span><span><small>Registros</small><strong>${d.process.registros}</strong></span><span><small>Ocorrências</small><strong>${d.process.ocorrencias}</strong></span>`;historyDetailBody.innerHTML=d.decisions.length?d.decisions.map(x=>`<tr><td><strong>${esc(x.hub_id)}</strong></td><td>${esc(x.finding_id)}</td><td>${x.linha??'—'}</td><td>${x.linha_final??'—'}</td><td>${esc(x.tipo)}</td><td>${esc(x.severidade||'—')}</td><td>${esc(x.decisao)}</td><td>${fmtDate(x.data)}</td></tr>`).join(''):'<tr><td colspan="8">Nenhuma decisão registrada.</td></tr>';historyDetail.scrollIntoView({behavior:'smooth',block:'start'});}catch(e){msg(e.message,true)}}
closeHistory.onclick=()=>historyDetail.classList.add('hidden');
health();authStatus().then(ok=>{if(ok)refreshProtected();});
async function loadRules(){try{let r=await fetch(`${API}/api/rules`);let d=await r.json();ruleExact.checked=d.exact_duplicate?.enabled!==false;ruleOperational.checked=d.operational_duplicate?.enabled!==false;ruleRequired.checked=d.required_fields?.enabled!==false;ruleDate.checked=d.datetime_order?.enabled!==false;ruleCompleted.checked=d.completed_without_exit?.enabled!==false;ruleStatus.checked=d.allowed_status?.enabled===true;operationalFields.value=(d.operational_duplicate?.fields||[]).join(', ');requiredFields.value=(d.required_fields?.fields||[]).join(', ');allowedStatuses.value=(d.allowed_status?.values||[]).join(', ');rulesInfo.textContent='Configuração carregada.';}catch{rulesInfo.textContent='Não foi possível carregar as regras.';}}
const splitList=v=>v.split(',').map(x=>x.trim()).filter(Boolean);
saveRules.onclick=async()=>{let current=await (await fetch(`${API}/api/rules`)).json();current.exact_duplicate={...(current.exact_duplicate||{}),enabled:ruleExact.checked};current.operational_duplicate={...(current.operational_duplicate||{}),enabled:ruleOperational.checked,fields:splitList(operationalFields.value)};current.required_fields={...(current.required_fields||{}),enabled:ruleRequired.checked,fields:splitList(requiredFields.value)};current.datetime_order={...(current.datetime_order||{}),enabled:ruleDate.checked};current.completed_without_exit={...(current.completed_without_exit||{}),enabled:ruleCompleted.checked};current.allowed_status={...(current.allowed_status||{}),enabled:ruleStatus.checked,values:splitList(allowedStatuses.value)};let r=await fetch(`${API}/api/rules`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(current)});if(r.ok){rulesInfo.textContent='Regras salvas. Próximas análises usarão esta configuração.';msg('Regras operacionais atualizadas.');}else rulesInfo.textContent='Erro ao salvar regras.';}


analyzeBtn.onclick=async()=>{let f=fileInput.files[0];if(!f)return msg('Selecione um arquivo Excel primeiro.',true);analyzeBtn.disabled=true;msg('Analisando planilha...');let fd=new FormData();fd.append('file',f);try{let r=await fetch(`${API}/api/spreadsheet/analyze`,{method:'POST',body:fd});let d=await r.json();if(!r.ok)throw Error(d.error);token=d.token;currentProcess=d.process_code;render(d);msg(`Análise concluída · ${d.process_code}. Revise as ocorrências e registre suas decisões.`);dashboard();loadHistory();}catch(e){msg(e.message,true)}finally{analyzeBtn.disabled=false}};
function render(d){results.classList.remove('hidden');downloadBtn.classList.add('hidden');rowsMetric.textContent=d.summary.rows;cleanMetric.textContent=d.summary.clean_records;criticalMetric.textContent=d.summary.critical;warningMetric.textContent=d.summary.warning;fileMeta.innerHTML=`<p><strong>${esc(d.filename)}</strong></p><p><strong>${esc(d.process_code)}</strong></p><p>Aba: ${esc(d.sheet)}</p><p>${d.summary.columns} colunas · ${d.summary.rows} registros</p>`;issues.innerHTML=d.issues.map(x=>`<div class="issue">${esc(x)}</div>`).join('');currentFindings=d.findings||[];findingsBody.innerHTML=currentFindings.length?currentFindings.map(f=>`<tr data-finding-id="${esc(f.id)}" data-hub="${esc(f.hub_id)}" data-line="${f.excel_row}" data-type="${esc(f.type)}" data-severity="${esc(f.severity)}" data-message="${esc(f.message)}"><td><strong>${esc(f.hub_id)}</strong><br><small>${f.id}</small></td><td>${f.excel_row}</td><td>${esc(f.type)}</td><td>${esc(f.severity)}</td><td>${esc(f.message)}</td><td><select class="decision" data-id="${f.id}" data-state="${esc(f.decision)}"><option ${f.decision==='Revisar'?'selected':''}>Revisar</option><option ${f.decision==='Manter'?'selected':''}>Manter</option><option ${f.decision==='Remover'?'selected':''}>Remover</option></select></td><td>${f.related_row?`<button class="mini compare" data-id="${f.id}">Comparar</button>`:'—'}</td></tr>`).join(''):'<tr><td colspan="7">Nenhuma ocorrência.</td></tr>';setupReviewUX();previewHead.innerHTML='<tr>'+d.preview.columns.map(c=>`<th>${esc(c)}</th>`).join('')+'</tr>';previewBody.innerHTML=d.preview.rows.map(r=>'<tr>'+d.preview.columns.map(c=>`<td>${esc(r[c])}</td>`).join('')+'</tr>').join('');}
async function saveDecision(id,decision){try{let r=await fetch(`${API}/api/spreadsheet/decision`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token,finding_id:id,decision})});let d=await r.json();if(!r.ok)throw Error(d.error);msg(`${d.process_code} · ${d.hub_id}: decisão ${decision} registrada.`);dashboard();loadHistory();}catch(e){msg(e.message,true)}}
async function compare(id){try{let r=await fetch(`${API}/api/spreadsheet/${token}/finding/${id}`);let d=await r.json();if(!r.ok)throw Error(d.error);comparePanel.classList.remove('hidden');compareTitle.textContent=`${currentProcess} · ${d.finding.hub_id} · linha original ${d.finding.excel_row} x linha ${d.finding.related_row}`;compareReason.textContent=d.finding.message;compareBody.innerHTML=d.fields.map(x=>`<tr><td><strong>${esc(x.field)}</strong></td><td>${esc(x.related)}</td><td>${esc(x.current)}</td></tr>`).join('');comparePanel.scrollIntoView({behavior:'smooth',block:'center'});}catch(e){msg(e.message,true)}}
closeCompare.onclick=()=>comparePanel.classList.add('hidden');
processBtn.onclick=async()=>{if(!token)return msg('Analise um arquivo primeiro.',true);const pending=[...document.querySelectorAll('.decision')].filter(x=>x.value==='Revisar').length;if(pending&&!confirm(`${pending} ocorrência(s) ainda estão como Revisar. Elas serão mantidas na planilha e registradas para auditoria. Deseja gerar o arquivo mesmo assim?`))return;processBtn.disabled=true;msg('Aplicando decisões e gerando planilha...');try{let r=await fetch(`${API}/api/spreadsheet/process`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});let d=await r.json();if(!r.ok)throw Error(d.error);downloadBtn.href=`${API}${d.download_url}`;downloadBtn.textContent=`Baixar ${d.output_filename}`;downloadBtn.classList.remove('hidden');
const sendBtn=document.getElementById('sendToOperationsBtn'),sendInfo=document.getElementById('sendToOperationsInfo');
if(sendBtn){sendBtn.classList.remove('hidden');if(sendInfo)sendInfo.classList.remove('hidden');}
msg(`${d.process_code} concluído. ${d.removed} registro(s) removido(s). Histórico salvo no SQLite.`);dashboard();loadHistory();loadLogs();}catch(e){msg(e.message,true)}finally{processBtn.disabled=false}};
async function loadLogs(){try{let d=await (await fetch(`${API}/api/logs`)).json();activityLog.innerHTML=d.logs.length?d.logs.map(l=>`<div class="log"><span>${l.time}</span><strong>${esc(l.action)}</strong><span>${esc(l.status)}</span></div>`).join(''):'<div class="log"><span>--:--</span><strong>Aguardando execução</strong><span>—</span></div>';}catch{}}


// V0.8 - filtros, busca, contadores e ações seguras em lote
function setupReviewUX(){
  const types=[...new Set(currentFindings.map(f=>f.type).filter(Boolean))].sort();
  typeFilter.innerHTML='<option value="">Todos os tipos</option>'+types.map(t=>`<option>${esc(t)}</option>`).join('');
  reviewSearch.value=''; severityFilter.value=''; typeFilter.value=''; decisionFilter.value='';
  document.querySelectorAll('.decision').forEach(x=>{x.dataset.state=x.value;x.onchange=async()=>{x.dataset.state=x.value;await saveDecision(x.dataset.id,x.value);applyReviewFilters();};});
  document.querySelectorAll('.compare').forEach(x=>x.onclick=()=>compare(x.dataset.id));
  [reviewSearch,severityFilter,typeFilter,decisionFilter].forEach(el=>{el.oninput=applyReviewFilters;el.onchange=applyReviewFilters;});
  clearFilters.onclick=()=>{reviewSearch.value='';severityFilter.value='';typeFilter.value='';decisionFilter.value='';applyReviewFilters();};
  bulkReview.onclick=()=>bulkDecision('Revisar'); bulkKeep.onclick=()=>bulkDecision('Manter');
  applyReviewFilters();
}
function visibleReviewRows(){return [...findingsBody.querySelectorAll('tr[data-finding-id]')].filter(r=>!r.classList.contains('review-row-hidden'));}
function applyReviewFilters(){
  const q=(reviewSearch?.value||'').trim().toLowerCase(), sev=severityFilter?.value||'', typ=typeFilter?.value||'', dec=decisionFilter?.value||'';
  const rows=[...findingsBody.querySelectorAll('tr[data-finding-id]')];
  rows.forEach(r=>{const sel=r.querySelector('.decision');const hay=[r.dataset.hub,r.dataset.line,r.dataset.type,r.dataset.severity,r.dataset.message].join(' ').toLowerCase();const ok=(!q||hay.includes(q))&&(!sev||r.dataset.severity===sev)&&(!typ||r.dataset.type===typ)&&(!dec||sel?.value===dec);r.classList.toggle('review-row-hidden',!ok);});
  const vis=visibleReviewRows(); reviewCounter.textContent=`${vis.length} de ${rows.length} ocorrência(s) exibida(s)`;
  const pending=rows.filter(r=>r.querySelector('.decision')?.value==='Revisar').length; pendingCounter.textContent=`${pending} para revisar`; if(typeof processGuard!=='undefined'&&processGuard) processGuard.textContent=pending?`${pending} ocorrência(s) continuam em Revisar. Elas serão preservadas e registradas no histórico.`:'Todas as ocorrências possuem uma decisão. O processamento está pronto para finalizar.';
}
async function bulkDecision(decision){
  const rows=visibleReviewRows(); if(!rows.length)return msg('Nenhuma ocorrência visível para aplicar a ação.',true);
  const targets=rows.map(r=>r.querySelector('.decision')).filter(s=>s&&s.value!==decision);
  if(!targets.length)return msg(`Todos os itens filtrados já estão como ${decision}.`);
  for(const s of targets){s.value=decision;s.dataset.state=decision;await saveDecision(s.dataset.id,decision);}
  applyReviewFilters(); msg(`${targets.length} ocorrência(s) filtrada(s) marcadas como ${decision}.`);
}

// V1.1-dev1 - Operations Core
let operationsCache=[];
// V1.1-dev2: navegação antiga por scroll substituída pelo shell de views.
async function loadOperations(){
  try{const r=await fetch(`${API}/api/operations`);if(!r.ok)return;const d=await r.json();operationsCache=d.operations||[];[['opTotal','total'],['opWaiting','waiting'],['opActive','active'],['opFinished','finished']].forEach(([id,k])=>{const el=document.getElementById(id);if(el)el.textContent=d.stats[k]});renderOperations();}catch{}
}
function workflowButtons(o){
  if(o.status==='AGUARDANDO')return `<button class="mini op-workflow" data-action="registrar_entrada" data-code="${esc(o.operation_code)}">Registrar entrada</button>`;
  if(o.status==='NO PÁTIO')return `<button class="mini op-workflow" data-action="iniciar_operacao" data-code="${esc(o.operation_code)}">Iniciar operação</button>`;
  if(o.status==='EM OPERAÇÃO')return `<button class="mini op-workflow" data-action="finalizar_operacao" data-code="${esc(o.operation_code)}">Finalizar</button>`;
  if(o.status==='FINALIZADO')return `<button class="mini op-workflow" data-action="registrar_saida" data-code="${esc(o.operation_code)}">Registrar saída</button>`;
  return '';
}
function bindWorkflowButtons(root=document){root.querySelectorAll('.op-workflow').forEach(b=>b.onclick=()=>runWorkflow(b.dataset.code,b.dataset.action))}
function renderOperations(){const q=(opSearch.value||'').trim().toLowerCase();const rows=operationsCache.filter(o=>[o.operation_code,o.status,o.placa,o.motorista,o.transportadora,o.documento,o.carga,o.doca].join(' ').toLowerCase().includes(q));operationsBody.innerHTML=rows.length?rows.map(o=>`<tr><td><strong>${esc(o.operation_code)}</strong></td><td><span class="op-status">${esc(o.status)}</span></td><td>${esc(o.placa||'—')}</td><td>${esc(o.motorista||'—')}</td><td>${esc(o.transportadora||'—')}</td><td>${esc(o.documento||o.carga||'—')}</td><td>${esc(o.doca||'—')}</td><td><div class="op-actions"><button class="mini op-view" data-code="${esc(o.operation_code)}">Ver</button>${workflowButtons(o)}</div></td></tr>`).join(''):'<tr><td colspan="8">Nenhuma operação encontrada.</td></tr>';document.querySelectorAll('.op-view').forEach(b=>b.onclick=()=>viewOperation(b.dataset.code));bindWorkflowButtons(operationsBody);}
async function runWorkflow(code,action){let dock=null;if(action==='iniciar_operacao'){const op=operationsCache.find(x=>x.operation_code===code);if(!op?.doca){dock=prompt('Doca da operação (opcional):','');if(dock===null)return;}}try{const r=await fetch(`${API}/api/operations/${code}/workflow`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,dock})});const d=await r.json();if(!r.ok)throw Error(d.error);await loadOperations();if(!operationDetail.classList.contains('hidden'))await viewOperation(code);await loadLogs();}catch(e){msg(e.message,true)}}
opSearch.oninput=renderOperations;
operationForm.onsubmit=async e=>{e.preventDefault();opFeedback.textContent='Validando cadastros...';if(!await validateOperationMasters())return;opFeedback.textContent='Salvando...';const payload={tipo:opTipo.value,transportadora:opTransportadora.value,motorista:opMotorista.value,placa:opPlaca.value,documento:opDocumento.value,carga:opCarga.value,peso:opPeso.value||null,doca:opDoca.value,entrada_em:opEntrada.value||null,agendado_em:opAgendado.value||null,status:opStatus.value,observacoes:opObservacoes.value,origem:'MANUAL'};try{const r=await fetch(`${API}/api/operations`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const d=await r.json();if(!r.ok)throw Error(d.error);operationForm.reset();opFeedback.textContent=`${d.operation.operation_code} cadastrada.`;await loadOperations();await loadLogs();setTimeout(()=>closeOpModal(manualOperationModal),250);}catch(err){opFeedback.textContent=err.message;}};
async function viewOperation(code){try{const r=await fetch(`${API}/api/operations/${code}`);const d=await r.json();if(!r.ok)throw Error(d.error);const o=d.operation;openOpModal(operationDetail);opDetailTitle.textContent=`${o.operation_code} · ${o.status}`;opDetailMeta.innerHTML=`<span><small>Placa</small><strong>${esc(o.placa||'—')}</strong></span><span><small>Motorista</small><strong>${esc(o.motorista||'—')}</strong></span><span><small>Transportadora</small><strong>${esc(o.transportadora||'—')}</strong></span><span><small>Documento / Carga</small><strong>${esc(o.documento||o.carga||'—')}</strong></span><span><small>Doca</small><strong>${esc(o.doca||'—')}</strong></span><span><small>Entrada</small><strong>${o.entrada_em?fmtDate(o.entrada_em):'—'}</strong></span><span><small>Início</small><strong>${o.inicio_em?fmtDate(o.inicio_em):'—'}</strong></span><span><small>Finalização</small><strong>${o.finalizado_em?fmtDate(o.finalizado_em):'—'}</strong></span><span><small>Saída</small><strong>${o.saida_em?fmtDate(o.saida_em):'—'}</strong></span><span><small>Origem</small><strong>${esc(o.origem||'—')}</strong></span><span><small>Arquivo</small><strong>${esc(o.origem_arquivo||'—')}</strong></span>`;currentOperation=o;operationEdit.classList.add('hidden');const da=document.querySelector('.detail-actions');da.innerHTML=`<button class="mini" id="editOperationBtn" type="button">Editar operação</button>${workflowButtons(o)}`;document.getElementById('editOperationBtn').onclick=openOperationEdit;bindWorkflowButtons(da);opMovesBody.innerHTML=(o.movimentacoes||[]).map(m=>`<tr><td>${fmtDate(m.data)}</td><td>${esc(m.evento)}</td><td>${esc(m.status_anterior||'—')}</td><td>${esc(m.status_novo||'—')}</td><td>${esc(m.usuario_nome||'—')}</td></tr>${m.detalhe?`<tr class="move-detail"><td></td><td colspan="4">${esc(m.detalhe)}</td></tr>`:''}`).join('')||'<tr><td colspan="5">Sem movimentações.</td></tr>';}catch(e){msg(e.message,true)}}
closeOperationDetail.onclick=()=>closeOpModal(operationDetail);
// Acrescenta Operations Core ao ciclo protegido sem alterar a autenticação existente.
const _refreshProtected=refreshProtected;refreshProtected=async function(){await _refreshProtected();await loadOperations();};


// V1.1-dev2 - shell SPA leve: troca de páginas internas sem recarregar o navegador.
const appViews=[...document.querySelectorAll('.app-view')];
const mainNav=[...document.querySelectorAll('.hub-nav .nav-link')];
function openAppView(viewId,{push=true}={}){
  const target=document.getElementById(viewId)||document.getElementById('homeView');
  appViews.forEach(v=>v.classList.toggle('active',v===target));
  mainNav.forEach(b=>b.classList.toggle('active',b.dataset.view===target.id));
  document.querySelectorAll('[data-open-view]').forEach(b=>b.classList.toggle('active',b.dataset.openView===target.id));
  if(push){history.pushState({view:target.id},'',`#${target.id.replace('View','')}`);}
  window.scrollTo({top:0,behavior:'smooth'});
  if(target.id==='homeView') loadOperationalDashboard();
  if(target.id==='operationsView') loadOperations();
  if(target.id==='controlView') loadControlCenter();
  if(target.id==='masterView') loadMasterData();
  if(target.id==='reportsView') loadOperationalReport();
  if(target.id==='historyView'){dashboard();loadHistory();loadLogs();}
}
mainNav.forEach(b=>b.onclick=()=>openAppView(b.dataset.view));
document.querySelectorAll('[data-open-view]').forEach(b=>b.onclick=()=>openAppView(b.dataset.openView));
window.addEventListener('popstate',e=>openAppView(e.state?.view||viewFromHash(),{push:false}));
function viewFromHash(){const key=(location.hash||'#home').slice(1);return ({home:'homeView',control:'controlView',operations:'operationsView',master:'masterView',spreadsheet:'spreadsheetView',reports:'reportsView',history:'historyView'})[key]||'homeView';}
openAppView(viewFromHash(),{push:false});


// V1.1-dev3 - importação operacional e edição auditável
document.addEventListener('click',e=>{if(e.target.classList.contains('op-modal'))closeOpModal(e.target)});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){const m=document.querySelector('.op-modal:not(.hidden)');if(m)closeOpModal(m)}});
let operationImportToken=null, operationImportRecords=[], currentOperation=null;
const manualOperationModal=document.getElementById('manualOperationModal');
const closeManualOperation=document.getElementById('closeManualOperation');
const cancelManualOperation=document.getElementById('cancelManualOperation');
const closeOperationImport=document.getElementById('closeOperationImport');
function openOpModal(el){el.classList.remove('hidden');document.body.classList.add('modal-open')}
function closeOpModal(el){el.classList.add('hidden');if(!document.querySelector('.op-modal:not(.hidden)'))document.body.classList.remove('modal-open')}
showManualOp.onclick=async()=>{opFeedback.textContent='';await loadOperationMasterLists();openOpModal(manualOperationModal)};
showImportOp.onclick=()=>{operationImportFeedback.textContent='';openOpModal(operationImport)};
closeManualOperation.onclick=cancelManualOperation.onclick=()=>closeOpModal(manualOperationModal);
closeOperationImport.onclick=()=>closeOpModal(operationImport);
previewOperationImport.onclick=async()=>{
  const f=operationImportFile.files[0]; if(!f)return operationImportFeedback.textContent='Selecione um arquivo JSON, XML ou TXT.';
  operationImportFeedback.textContent='Lendo arquivo...'; const fd=new FormData();fd.append('file',f);
  try{const r=await fetch(`${API}/api/operations/import/preview`,{method:'POST',body:fd});const d=await r.json();if(!r.ok)throw Error(d.error);operationImportToken=d.token;operationImportRecords=d.records||[];operationImportCount.textContent=`${d.count} registro(s) detectado(s) · ${d.filename}`;operationImportBody.innerHTML=operationImportRecords.map((o,i)=>`<tr><td>${i+1}</td><td>${esc(o.motorista||'—')}</td><td>${esc(o.transportadora||'—')}</td><td>${esc(o.placa||'—')}</td><td>${esc(o.documento||'—')}</td><td>${esc(o.agendado_em||'—')}</td><td>${esc(o.status||'AGUARDANDO')}</td></tr>`).join('');operationImportPreview.classList.remove('hidden');operationImportFeedback.textContent='Confira a pré-visualização antes de criar as operações.';}catch(e){operationImportFeedback.textContent=e.message;operationImportPreview.classList.add('hidden')}
};
confirmOperationImport.onclick=async()=>{
  if(!operationImportToken)return; confirmOperationImport.disabled=true;operationImportFeedback.textContent='Criando operações...';
  try{const r=await fetch(`${API}/api/operations/import/confirm`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:operationImportToken})});const d=await r.json();if(!r.ok)throw Error(d.error);operationImportFeedback.textContent=`${d.created} operação(ões) criada(s).${d.errors?.length?` ${d.errors.length} registro(s) ignorado(s).`:''}`;operationImportPreview.classList.add('hidden');operationImportFile.value='';operationImportToken=null;await loadOperations();await loadLogs();setTimeout(()=>closeOpModal(operationImport),250);}catch(e){operationImportFeedback.textContent=e.message}finally{confirmOperationImport.disabled=false}
};
function localDateValue(v){return v?String(v).slice(0,16):''}
function openOperationEdit(){
  if(!currentOperation)return; const o=currentOperation;operationEdit.classList.remove('hidden');
  editTipo.value=o.tipo||'';editTransportadora.value=o.transportadora||'';editMotorista.value=o.motorista||'';editPlaca.value=o.placa||'';editDocumento.value=o.documento||'';editCarga.value=o.carga||'';editPeso.value=o.peso??'';editDoca.value=o.doca||'';editAgendado.value=localDateValue(o.agendado_em);editEntrada.value=localDateValue(o.entrada_em);editStatus.value=o.status||'AGUARDANDO';editObservacoes.value=o.observacoes||'';editOperationFeedback.textContent='';
}
editOperationBtn.onclick=openOperationEdit;
cancelOperationEdit.onclick=()=>operationEdit.classList.add('hidden');
operationEditForm.onsubmit=async e=>{
  e.preventDefault();if(!currentOperation)return;editOperationFeedback.textContent='Salvando...';const payload={tipo:editTipo.value,transportadora:editTransportadora.value,motorista:editMotorista.value,placa:editPlaca.value,documento:editDocumento.value,carga:editCarga.value,peso:editPeso.value||null,doca:editDoca.value,agendado_em:editAgendado.value||null,entrada_em:editEntrada.value||null,status:editStatus.value,observacoes:editObservacoes.value};
  try{const r=await fetch(`${API}/api/operations/${currentOperation.operation_code}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const d=await r.json();if(!r.ok)throw Error(d.error);editOperationFeedback.textContent='Alterações salvas e registradas no histórico.';await loadOperations();await viewOperation(currentOperation.operation_code);await loadLogs();}catch(err){editOperationFeedback.textContent=err.message}
};

const sendToOperationsBtn=document.getElementById('sendToOperationsBtn');
if(sendToOperationsBtn)sendToOperationsBtn.onclick=async()=>{
  if(!token)return msg('Analise e processe uma planilha primeiro.',true);
  if(!confirm('Criar operações no Operations Core a partir dos registros da planilha tratada? Cada registro será criado como uma nova OP em AGUARDANDO.'))return;
  sendToOperationsBtn.disabled=true;msg('Enviando registros validados para o Operations Core...');
  try{
    const r=await fetch(`${API}/api/spreadsheet/send-to-operations`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
    const d=await r.json();if(!r.ok)throw Error(d.error);
    const failed=(d.errors||[]).length;
    msg(`${d.created} operação(ões) criada(s) no Operations Core${failed?`; ${failed} registro(s) não importado(s)`:''}.`);
    loadOperationalDashboard();
    sendToOperationsBtn.disabled=true;
    sendToOperationsBtn.textContent=`Enviado ao Operations Core · ${d.created} OP(s)`;
  }catch(e){msg(e.message,true);sendToOperationsBtn.disabled=false;}
};

// V1.1-dev8 · Cadastros operacionais
let currentMaster='carriers';
const masterConfig={
 carriers:{title:'transportadora',fields:[['nome','Nome','text'],['documento','CNPJ / documento','text'],['contato','Contato','text'],['telefone','Telefone','text'],['email','E-mail','email']]},
 drivers:{title:'motorista',fields:[['nome','Nome','text'],['documento','CPF / documento','text'],['telefone','Telefone','text'],['transportadora_id','Transportadora','carrier']]},
 vehicles:{title:'veículo',fields:[['placa','Placa','text'],['descricao','Descrição / modelo','text'],['transportadora_id','Transportadora','carrier']]},
 docks:{title:'doca',fields:[['codigo','Código','text'],['descricao','Descrição','text'],['status','Status','dockstatus']]}
};
async function carrierOptions(){
 try{const d=await (await fetch(`${API}/api/master/carriers`)).json();return (d.items||[]).filter(x=>x.ativo).map(x=>`<option value="${x.id}">${esc(x.nome)}</option>`).join('')}catch{return ''}
}
async function renderMasterForm(){
 const cfg=masterConfig[currentMaster], form=document.getElementById('masterFields');
 document.getElementById('masterTitle').textContent=`Novo ${cfg.title}`;
 let carrierOpts=currentMaster==='drivers'||currentMaster==='vehicles'?await carrierOptions():'';
 form.innerHTML=cfg.fields.map(([name,label,type])=>{
   if(type==='carrier')return `<label>${label}<select name="${name}"><option value="">Sem vínculo</option>${carrierOpts}</select></label>`;
   if(type==='dockstatus')return `<label>${label}<select name="${name}"><option>DISPONÍVEL</option><option>INDISPONÍVEL</option><option>MANUTENÇÃO</option></select></label>`;
   return `<label>${label}<input name="${name}" type="${type}"></label>`;
 }).join('');
}
async function loadMasterData(){
 const cfg=masterConfig[currentMaster]; await renderMasterForm();
 const r=await fetch(`${API}/api/master/${currentMaster}`),d=await r.json(),items=d.items||[];
 const masterTitles={carriers:'Transportadoras cadastradas',drivers:'Motoristas cadastrados',vehicles:'Veículos cadastrados',docks:'Docas cadastradas'};
 document.getElementById('masterListTitle').textContent=masterTitles[currentMaster];
 const cols=currentMaster==='carriers'?[['nome','Nome'],['documento','Documento'],['contato','Contato']]:
   currentMaster==='drivers'?[['nome','Nome'],['documento','Documento'],['transportadora_nome','Transportadora']]:
   currentMaster==='vehicles'?[['placa','Placa'],['descricao','Descrição'],['transportadora_nome','Transportadora']]:
   [['codigo','Código'],['descricao','Descrição'],['status','Status']];
 document.getElementById('masterHead').innerHTML='<tr>'+cols.map(c=>`<th>${c[1]}</th>`).join('')+'<th>Situação</th><th>Ação</th></tr>';
 document.getElementById('masterBody').innerHTML=items.length?items.map(x=>'<tr>'+cols.map(c=>`<td>${esc(x[c[0]]||'—')}</td>`).join('')+`<td>${x.ativo?'ATIVO':'INATIVO'}</td><td><button class="mini master-toggle" data-id="${x.id}">${x.ativo?'Desativar':'Ativar'}</button></td></tr>`).join(''):`<tr><td colspan="${cols.length+2}">Nenhum cadastro.</td></tr>`;
 document.querySelectorAll('.master-toggle').forEach(b=>b.onclick=async()=>{await fetch(`${API}/api/master/${currentMaster}/${b.dataset.id}/toggle`,{method:'PATCH'});loadMasterData()});
}
document.querySelectorAll('[data-master]').forEach(b=>b.onclick=()=>{currentMaster=b.dataset.master;document.querySelectorAll('[data-master]').forEach(x=>x.classList.toggle('active',x===b));loadMasterData()});
const masterForm=document.getElementById('masterForm');
const masterCreateModal=document.getElementById('masterCreateModal');
openMasterCreate.onclick=async()=>{await renderMasterForm();openOpModal(masterCreateModal)};
closeMasterCreate.onclick=cancelMasterCreate.onclick=()=>closeOpModal(masterCreateModal);
if(masterForm)masterForm.onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(masterForm).entries());const r=await fetch(`${API}/api/master/${currentMaster}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const d=await r.json();if(!r.ok)return msg(d.error||'Erro no cadastro.',true);masterForm.reset();closeOpModal(masterCreateModal);msg('Cadastro salvo.');loadMasterData()};

// V1.1-dev8.1 · integração dos cadastros com cadastro manual de OP
let opMasterData={carriers:[],drivers:[],vehicles:[],docks:[]},quickKind=null;
const quickMasterModal=document.getElementById('quickMasterModal');
async function loadOperationMasterLists(){
  for(const kind of ['carriers','drivers','vehicles','docks']){
    try{const d=await (await fetch(`${API}/api/master/${kind}`)).json();opMasterData[kind]=(d.items||[]).filter(x=>x.ativo);}catch{opMasterData[kind]=[]}
  }
  carrierList.innerHTML=opMasterData.carriers.map(x=>`<option value="${esc(x.nome)}"></option>`).join('');
  refreshDependentLists();
  opDoca.innerHTML='<option value="">Sem doca</option>'+opMasterData.docks.filter(x=>x.status==='DISPONÍVEL').map(x=>`<option value="${esc(x.codigo)}">${esc(x.codigo)}${x.descricao?' · '+esc(x.descricao):''}</option>`).join('');
}
function selectedCarrier(){
 const name=opTransportadora.value.trim().toLowerCase();return opMasterData.carriers.find(x=>x.nome.toLowerCase()===name);
}
function refreshDependentLists(){
 const c=selectedCarrier(),cid=c?.id;
 const drivers=opMasterData.drivers.filter(x=>!cid||String(x.transportadora_id||'')===String(cid));
 const vehicles=opMasterData.vehicles.filter(x=>!cid||String(x.transportadora_id||'')===String(cid));
 driverList.innerHTML=drivers.map(x=>`<option value="${esc(x.nome)}">${esc(x.transportadora_nome||'')}</option>`).join('');
 vehicleList.innerHTML=vehicles.map(x=>`<option value="${esc(x.placa)}">${esc(x.descricao||'')}</option>`).join('');
}
function exactMaster(kind,value){
 value=(value||'').trim().toLowerCase();const c=selectedCarrier();
 return opMasterData[kind].some(x=>{
   const v=kind==='carriers'?x.nome:kind==='drivers'?x.nome:x.placa;
   const carrierOk=kind==='drivers'||kind==='vehicles'?(!c||String(x.transportadora_id||'')===String(c.id)):true;
   return carrierOk&&String(v||'').trim().toLowerCase()===value;
 });
}
function updateQuickButtons(){
 const pairs=[['carriers',opTransportadora],['drivers',opMotorista],['vehicles',opPlaca]];
 pairs.forEach(([kind,input])=>{const b=input.parentElement.querySelector('.quick-master');b.classList.toggle('hidden',!input.value.trim()||exactMaster(kind,input.value));});
}
opTransportadora.addEventListener('input',()=>{refreshDependentLists();updateQuickButtons()});
opMotorista.addEventListener('input',updateQuickButtons);opPlaca.addEventListener('input',updateQuickButtons);
async function validateOperationMasters(){
 const checks=[['Transportadora','carriers',opTransportadora],['Motorista','drivers',opMotorista],['Veículo','vehicles',opPlaca]];
 for(const [label,kind,input] of checks){
   if(input.value.trim()&&!exactMaster(kind,input.value)){opFeedback.textContent=`${label} não cadastrado para esta operação. Use “+ Cadastrar” antes de continuar.`;updateQuickButtons();return false;}
 }
 if(opDoca.value&&!opMasterData.docks.some(x=>x.codigo===opDoca.value&&x.ativo&&x.status==='DISPONÍVEL')){opFeedback.textContent='Doca inválida ou indisponível.';return false;}
 return true;
}
document.querySelectorAll('.quick-master').forEach(b=>b.onclick=()=>openQuickMaster(b.dataset.kind));
async function openQuickMaster(kind){
 quickKind=kind;const cfg=masterConfig[kind],source=kind==='carriers'?opTransportadora:kind==='drivers'?opMotorista:opPlaca;
 quickMasterTitle.textContent=`Novo ${cfg.title}`;quickMasterFeedback.textContent='';
 let carrierOpts=await carrierOptions();
 quickMasterFields.innerHTML=cfg.fields.map(([name,label,type])=>{
   let preset=(name==='nome'||name==='placa')?source.value.trim():'';
   if(type==='carrier'){const c=selectedCarrier();return `<label>${label}<select name="${name}"><option value="">Sem vínculo</option>${carrierOpts}</select></label>`}
   return `<label>${label}<input name="${name}" type="${type}" value="${esc(preset)}"></label>`;
 }).join('');
 const c=selectedCarrier();if(c&&kind!=='carriers'){const sel=quickMasterFields.querySelector('[name="transportadora_id"]');if(sel)sel.value=c.id}
 openOpModal(quickMasterModal);
}
closeQuickMaster.onclick=cancelQuickMaster.onclick=()=>closeOpModal(quickMasterModal);
quickMasterForm.onsubmit=async e=>{
 e.preventDefault();const data=Object.fromEntries(new FormData(quickMasterForm).entries());
 try{const r=await fetch(`${API}/api/master/${quickKind}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const d=await r.json();if(!r.ok)throw Error(d.error);
   const selected=quickKind==='carriers'?data.nome:quickKind==='drivers'?data.nome:data.placa;
   await loadOperationMasterLists();
   if(quickKind==='carriers')opTransportadora.value=selected;else if(quickKind==='drivers')opMotorista.value=selected;else opPlaca.value=selected.toUpperCase();
   refreshDependentLists();updateQuickButtons();closeOpModal(quickMasterModal);opFeedback.textContent='Cadastro criado e selecionado na operação.';
 }catch(err){quickMasterFeedback.textContent=err.message}
};

// V1.1-dev8.2 · saneamento assistido de registros legados
const legacyAuditModal=document.getElementById('legacyAuditModal');
const legacyLabels={carriers:'Transportadora',drivers:'Motorista',vehicles:'Veículo',docks:'Doca'};
openLegacyAudit.onclick=async()=>{openOpModal(legacyAuditModal);await loadLegacyAudit()};
closeLegacyAudit.onclick=()=>closeOpModal(legacyAuditModal);
async function loadLegacyAudit(){
 legacyAuditFeedback.textContent='Verificando operações históricas...';
 try{
   const d=await (await fetch(`${API}/api/master/legacy-audit`)).json();
   let rows=[],missing=0,total=0;
   for(const kind of ['carriers','drivers','vehicles','docks']){
     for(const x of d[kind]||[]){total++;if(!x.registered)missing++;
       const note=kind==='drivers'&&x.historical_carriers?.length?`<small>Transportadoras nas OPs: ${x.historical_carriers.map(esc).join(', ')}</small>`:'';
       rows.push(`<tr><td>${legacyLabels[kind]}</td><td><strong>${esc(x.value)}</strong>${note}</td><td>${x.uses}</td><td>${x.registered?(x.active?'✓ Cadastrado':'⚠ Inativo'):'⚠ Não cadastrado'}</td><td>${x.registered?'—':`<button class="mini legacy-register" data-kind="${kind}" data-value="${encodeURIComponent(x.value)}">Cadastrar</button>`}</td></tr>`);
     }
   }
   legacyAuditSummary.innerHTML=`<div class="legacy-summary"><strong>${missing}</strong> pendência(s) em <strong>${total}</strong> valor(es) históricos encontrados.</div>`;
   legacyAuditBody.innerHTML=rows.join('')||'<tr><td colspan="5">Nenhum valor histórico encontrado.</td></tr>';
   legacyAuditFeedback.textContent='Nenhuma operação histórica foi modificada.';
   document.querySelectorAll('.legacy-register').forEach(b=>b.onclick=()=>legacyQuickRegister(b.dataset.kind,decodeURIComponent(b.dataset.value)));
 }catch(e){legacyAuditFeedback.textContent=e.message}
}
async function legacyQuickRegister(kind,value){
 currentMaster=kind;closeOpModal(legacyAuditModal);openAppView('masterView');
 document.querySelectorAll('.master-tabs [data-master]').forEach(b=>b.classList.toggle('active',b.dataset.master===kind));
 await loadMasterData();
 const cfg=masterConfig[kind];const first=cfg.fields[0]?.[0];const field=masterFields.querySelector(`[name="${first}"]`);
 if(field)field.value=value;
 openOpModal(masterCreateModal);
 masterTitle.textContent=`Cadastrar ${cfg.title} legado`;
 masterForm.scrollIntoView({behavior:'smooth',block:'center'});
}

// V1.1-dev9 · relatórios e consultas operacionais
function reportParams(){
 const p=new URLSearchParams();
 [['start',reportStart],['end',reportEnd],['status',reportStatus],['transportadora',reportCarrier],['motorista',reportDriver],['placa',reportVehicle],['doca',reportDock]].forEach(([k,e])=>{if(e.value.trim())p.set(k,e.value.trim())});
 return p;
}
function durationLabel(v){if(v===null||v===undefined)return '—';if(v<60)return `${v} min`;return `${(v/60).toFixed(1)} h`}
async function loadReportMasters(){
 const map=[['carriers',reportCarrierList,'nome'],['drivers',reportDriverList,'nome'],['vehicles',reportVehicleList,'placa'],['docks',reportDockList,'codigo']];
 for(const [kind,list,key] of map){try{const d=await (await fetch(`${API}/api/master/${kind}`)).json();list.innerHTML=(d.items||[]).map(x=>`<option value="${esc(x[key]||'')}"></option>`).join('')}catch{}}
}
async function loadOperationalReport(){
 loadOperationalSettings();
 reportFeedback.textContent='Consultando...';await loadReportMasters();
 try{const r=await fetch(`${API}/api/reports/operations?${reportParams()}`);const d=await r.json();if(!r.ok)throw Error(d.error);
 reportTotal.textContent=d.total;reportWait.textContent=durationLabel(d.avg_wait);reportOperation.textContent=durationLabel(d.avg_operation);reportStay.textContent=durationLabel(d.avg_stay);
 reportBody.innerHTML=(d.items||[]).map(o=>`<tr><td>${esc(o.operation_code)}</td><td><span class="status-pill">${esc(o.status)}</span></td><td>${esc(o.transportadora||'—')}</td><td>${esc(o.motorista||'—')}</td><td>${esc(o.placa||'—')}</td><td>${esc(o.doca||'—')}</td><td>${o.entrada_em?fmtDate(o.entrada_em):'—'}</td><td>${durationLabel(o.espera_min)}</td><td>${durationLabel(o.operacao_min)}</td><td>${durationLabel(o.permanencia_min)}</td></tr>`).join('')||'<tr><td colspan="10">Nenhuma operação encontrada.</td></tr>';
 reportFeedback.textContent=`${d.total} operação(ões) no resultado. Médias consideram somente operações com os respectivos horários completos.`;
 }catch(e){reportFeedback.textContent=e.message}
}
runReport.onclick=loadOperationalReport;
clearReport.onclick=()=>{[reportStart,reportEnd,reportCarrier,reportDriver,reportVehicle,reportDock].forEach(x=>x.value='');reportStatus.value='';loadOperationalReport()};
exportReport.onclick=()=>{window.location.href=`${API}/api/reports/operations.csv?${reportParams()}`};

// V1.1-dev10 · central operacional, alertas, docas e parâmetros
async function loadControlCenter(){
 try{
  const r=await fetch(`${API}/api/control-center`),d=await r.json();if(!r.ok)throw Error(d.error);
  ccTotal.textContent=d.total||0;ccWaiting.textContent=d.by_status?.['AGUARDANDO']||0;ccYard.textContent=d.by_status?.['NO PÁTIO']||0;ccOperating.textContent=d.by_status?.['EM OPERAÇÃO']||0;ccAlerts.textContent=(d.alerts||[]).length;
  ccOperations.innerHTML=(d.items||[]).map(o=>`<tr><td>${esc(o.operation_code)}</td><td><span class="status-pill">${esc(o.status)}</span></td><td>${esc(o.placa||'—')}</td><td>${esc(o.motorista||'—')}</td><td>${esc(o.doca||'—')}</td></tr>`).join('')||'<tr><td colspan="5">Nenhuma operação ativa.</td></tr>';
  ccDocks.innerHTML=(d.docks||[]).map(x=>`<article class="dock-card ${x.operation?'occupied':''}"><strong>${esc(x.codigo)}</strong><small>${x.operation?`OCUPADA · ${esc(x.operation.operation_code)}`:'DISPONÍVEL'}</small>${x.operation?`<span>${esc(x.operation.placa||'')} · ${esc(x.operation.status)}</span>`:''}</article>`).join('')||'<p>Nenhuma doca ativa cadastrada.</p>';
  ccAlertBody.innerHTML=(d.alerts||[]).map(a=>`<tr><td>${esc(a.severidade)}</td><td>${esc(a.operation_code)}</td><td>${esc(a.mensagem)}</td><td>${esc(a.doca||'—')}</td></tr>`).join('')||'<tr><td colspan="4">Sem alertas ativos.</td></tr>';
 }catch(e){msg(e.message,true)}
}
refreshControl.onclick=loadControlCenter;
async function loadOperationalSettings(){
 try{const d=await (await fetch(`${API}/api/settings/operational`)).json();settingWait.value=d.alert_wait_min||60;settingOperation.value=d.alert_operation_min||120;settingStay.value=d.alert_stay_min||240}catch{}
}
saveOperationalSettings.onclick=async()=>{
 settingsFeedback.textContent='Salvando...';
 try{const r=await fetch(`${API}/api/settings/operational`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({alert_wait_min:settingWait.value,alert_operation_min:settingOperation.value,alert_stay_min:settingStay.value})});const d=await r.json();if(!r.ok)throw Error(d.error);settingsFeedback.textContent='Parâmetros salvos. A Central Operacional usará os novos limites.';loadControlCenter()}catch(e){settingsFeedback.textContent=e.message}
};

// V1.1 RC1 · microinterações e acessibilidade
document.addEventListener('click',e=>{
 const b=e.target.closest('button');if(!b||b.disabled)return;
 b.setAttribute('aria-busy','false');
});
document.querySelectorAll('.op-modal').forEach(m=>m.setAttribute('aria-hidden',m.classList.contains('hidden')?'true':'false'));
const _openOpModalRC=openOpModal;openOpModal=function(el){_openOpModalRC(el);el.setAttribute('aria-hidden','false');const f=el.querySelector('input,select,textarea,button');if(f)setTimeout(()=>f.focus(),30)};
const _closeOpModalRC=closeOpModal;closeOpModal=function(el){_closeOpModalRC(el);el.setAttribute('aria-hidden','true')};

// V1.1 FC2 · encerramento controlado do aplicativo local
const shutdownApp=document.getElementById('shutdownApp');
if(shutdownApp)shutdownApp.onclick=async()=>{
 if(!confirm('Encerrar completamente o Logistics Automation Hub?'))return;
 shutdownApp.disabled=true;shutdownApp.textContent='Encerrando...';
 try{
   const r=await fetch(`${API}/api/app/shutdown`,{method:'POST'});
   if(!r.ok)throw new Error();
   document.body.innerHTML='<main class="shutdown-screen"><div><h2>Logistics Automation Hub encerrado</h2><p>Você pode fechar esta aba com segurança.</p></div></main>';
 }catch{
   shutdownApp.disabled=false;shutdownApp.textContent='Encerrar aplicativo';
   alert('Não foi possível encerrar o aplicativo.');
 }
};
