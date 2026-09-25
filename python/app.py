from pathlib import Path
import sys,uuid,json,os,secrets,webbrowser,threading,shutil,csv,io,unicodedata,re,xml.etree.ElementTree as ET
from datetime import datetime
from flask import Flask,request,jsonify,send_from_directory,session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash,check_password_hash
# Recursos empacotados e dados mutáveis ficam separados.
# Release Candidate: dados do usuário ficam sob a identidade B.A Dev Lab.
PROJECT_BASE=Path(__file__).resolve().parents[1]
RESOURCE_BASE=Path(getattr(sys,'_MEIPASS',PROJECT_BASE)) if getattr(sys,'frozen',False) else PROJECT_BASE

# Dados mutáveis SEMPRE ficam fora da pasta do programa, inclusive em execução pelo
# código-fonte. Isso permite apagar/substituir a pasta da versão sem perder usuários,
# operações, PROC, histórico ou configurações.
local_appdata=Path(os.environ.get('LOCALAPPDATA') or (Path.home()/'AppData'/'Local'))
DATA_BASE=Path(os.environ.get('HUB_DATA_ROOT_OVERRIDE') or (local_appdata/'BA Dev Lab'/'Logistics Automation Hub'))
LEGACY_DATA_BASE=local_appdata/'LogisticsAutomationHub'

# Migração conservadora do diretório legado usado pelas versões anteriores.
# Se o destino novo ainda não existe, copia tudo. Se já existe mas o banco ainda não,
# copia somente o banco legado, sem sobrescrever dados existentes.
legacy_db=LEGACY_DATA_BASE/'database'/'logistics_hub.db'
new_db=DATA_BASE/'database'/'logistics_hub.db'
if LEGACY_DATA_BASE.exists():
    if not DATA_BASE.exists():
        DATA_BASE.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(LEGACY_DATA_BASE,DATA_BASE)
    elif legacy_db.exists() and not new_db.exists():
        new_db.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(legacy_db,new_db)
DATA_BASE.mkdir(parents=True,exist_ok=True)
os.environ['HUB_DATA_ROOT']=str(DATA_BASE)
sys.path.insert(0,str(Path(__file__).resolve().parent))

from modules.spreadsheet.processor import SpreadsheetProcessor
from database import init_db,create_process,save_decision,finish,stats,history,process_detail,user_count,create_user,get_user,get_user_by_id,create_operation,list_operations,get_operation,update_operation_status,operations_stats,operational_dashboard,update_operation,create_operations_batch,advance_operation_workflow,list_master_data,create_master_data,toggle_master_data,find_active_master,legacy_master_audit,operational_report,get_system_settings,save_system_settings,dock_board,refresh_operational_alerts,operations_control_center

app=Flask(__name__,static_folder=str(RESOURCE_BASE),static_url_path='')
app.config['MAX_CONTENT_LENGTH']=16*1024*1024
SECRET_FILE=DATA_BASE/'config'/'session_secret.txt';SECRET_FILE.parent.mkdir(parents=True,exist_ok=True)
if not SECRET_FILE.exists(): SECRET_FILE.write_text(secrets.token_hex(32),encoding='utf-8')
app.secret_key=os.environ.get('HUB_SECRET_KEY') or SECRET_FILE.read_text(encoding='utf-8').strip()
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax')
INPUT=DATA_BASE/'data'/'input';OUTPUT=DATA_BASE/'data'/'output';LOG=DATA_BASE/'logs'/'activity.jsonl'
INPUT.mkdir(parents=True,exist_ok=True);OUTPUT.mkdir(parents=True,exist_ok=True);LOG.parent.mkdir(parents=True,exist_ok=True)
processor=SpreadsheetProcessor();analyses={};init_db()
RULES_FILE=DATA_BASE/'config'/'spreadsheet_rules.json'
DEFAULT_RULES_FILE=RESOURCE_BASE/'config'/'spreadsheet_rules.json'
if not RULES_FILE.exists() and DEFAULT_RULES_FILE.exists():
    RULES_FILE.write_text(DEFAULT_RULES_FILE.read_text(encoding='utf-8'),encoding='utf-8')
def load_rules():
    return json.loads(RULES_FILE.read_text(encoding='utf-8'))
def save_rules(data):
    RULES_FILE.parent.mkdir(parents=True,exist_ok=True);RULES_FILE.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def log(action,status):
    with LOG.open('a',encoding='utf-8') as f:f.write(json.dumps({'time':datetime.now().strftime('%H:%M:%S'),'action':action,'status':status},ensure_ascii=False)+'\n')
@app.get('/')
def home():return app.send_static_file('index.html')
@app.before_request
def protect_api():
    public={'/api/auth/status','/api/auth/setup','/api/auth/login','/api/health'}
    if request.path.startswith('/api/') and request.path not in public and not session.get('user_id'):
        return jsonify(error='Autenticação necessária.'),401
@app.get('/api/health')
def health():return jsonify(status='online',module='operations-core',version='1.1-FC2',data_root=str(DATA_BASE),database=str(DATA_BASE/'database'/'logistics_hub.db'))
@app.get('/api/auth/status')
def auth_status():
    count=user_count(); configured=count>0
    user=get_user_by_id(session.get('user_id')) if session.get('user_id') else None
    response=jsonify(configured=configured,authenticated=bool(user),user=user,user_count=count)
    response.headers['Cache-Control']='no-store, no-cache, must-revalidate, max-age=0'
    return response
@app.post('/api/auth/setup')
def auth_setup():
    if user_count()>0:return jsonify(error='Configuração inicial já concluída.'),409
    d=request.get_json(silent=True) or {}; username=(d.get('username') or '').strip(); password=d.get('password') or ''; nome=(d.get('nome') or '').strip()
    if len(username)<3 or len(password)<8 or len(nome)<2:return jsonify(error='Informe nome, usuário (3+ caracteres) e senha (8+ caracteres).'),400
    uid=create_user(username,generate_password_hash(password),nome);session['user_id']=uid;log('Usuário administrador criado','Concluído');return jsonify(ok=True,user=get_user_by_id(uid))
@app.post('/api/auth/login')
def auth_login():
    d=request.get_json(silent=True) or {};u=get_user(d.get('username') or '')
    if not u or not check_password_hash(u['password_hash'],d.get('password') or ''):return jsonify(error='Usuário ou senha inválidos.'),401
    session['user_id']=u['id'];return jsonify(ok=True,user={'id':u['id'],'username':u['username'],'nome':u['nome']})
@app.post('/api/auth/logout')
def auth_logout():session.clear();return jsonify(ok=True)

@app.post('/api/spreadsheet/analyze')
def analyze():
    if 'file' not in request.files or not request.files['file'].filename:return jsonify(error='Nenhum arquivo enviado.'),400
    f=request.files['file'];name=secure_filename(f.filename)
    if Path(name).suffix.lower() not in {'.xlsx','.xlsm'}:return jsonify(error='Use .xlsx ou .xlsm.'),400
    token=uuid.uuid4().hex;path=INPUT/f'{token}_{name}';f.save(path)
    try:
        rules=load_rules();a=processor.analyze(path,rules);pid,process_code=create_process(token,name,a['summary']['rows'],len(a['findings']),rules);analyses[token]={'rules':rules,'path':path,'filename':name,'analysis':a,'pid':pid,'process_code':process_code,'decisions':{x['id']:x['decision'] for x in a['findings']}};log(f'{process_code} · Análise','Concluída')
        return jsonify(token=token,process_code=process_code,filename=name,sheet=a['sheet'],summary=a['summary'],issues=a['issues'],findings=[{k:v for k,v in x.items() if k not in {'row_index','related_index'}} for x in a['findings']],preview=a['preview'])
    except Exception as e:path.unlink(missing_ok=True);log('Análise','Erro');return jsonify(error=str(e)),400
@app.get('/api/spreadsheet/<token>/finding/<fid>')
def compare(token,fid):
    item=analyses.get(token)
    if not item:return jsonify(error='Análise expirada.'),404
    c=processor.comparison(item['analysis'],fid);return jsonify(c) if c else (jsonify(error='Ocorrência não encontrada.'),404)
@app.post('/api/spreadsheet/decision')
def decision():
    d=request.get_json(silent=True) or {};item=analyses.get(d.get('token'));choice=d.get('decision');fid=d.get('finding_id')
    if not item:return jsonify(error='Análise expirada.'),404
    if choice not in {'Manter','Remover','Revisar'}:return jsonify(error='Decisão inválida.'),400
    f=next((x for x in item['analysis']['findings'] if x['id']==fid),None)
    if not f:return jsonify(error='Ocorrência não encontrada.'),404
    item['decisions'][fid]=choice;f['decision']=choice;save_decision(item['pid'],f);return jsonify(ok=True,decision=choice,process_code=item['process_code'],hub_id=f.get('hub_id'))
@app.post('/api/spreadsheet/process')
def process():
    token=(request.get_json(silent=True) or {}).get('token');item=analyses.get(token)
    if not item:return jsonify(error='Análise expirada.'),404
    out=OUTPUT/f"{Path(item['filename']).stem}_TRATADO_V10_{item['process_code']}.xlsx"
    try:
        now=datetime.now().isoformat(timespec='seconds')
        result=processor.process(item['path'],out,item['analysis'],item['decisions'],item['process_code'],now);item['processed_output']=out
        for f in item['analysis']['findings']: save_decision(item['pid'],f)
        finish(item['pid']);log(f"{item['process_code']} · Processamento V1.0",'Concluído');return jsonify(process_code=item['process_code'],output_filename=out.name,removed=result['removed'],download_url=f'/api/download/{out.name}')
    except Exception as e:return jsonify(error=str(e)),500

@app.post('/api/spreadsheet/send-to-operations')
def spreadsheet_send_to_operations():
    data=request.get_json(silent=True) or {}
    token=data.get('token')
    item=analyses.get(token)
    if not item:return jsonify(error='Análise expirada. Analise a planilha novamente.'),404
    source=item.get('processed_output')
    if not source or not Path(source).exists():
        return jsonify(error='Gere a planilha tratada antes de enviar para o Operations Core.'),400
    try:
        import pandas as pd
        header_idx=item['analysis']['header_idx']
        df=pd.read_excel(source,sheet_name=item['analysis']['sheet'],header=header_idx,engine='openpyxl').dropna(how='all')
        def norm(value):
            text=unicodedata.normalize('NFKD',str(value)).encode('ascii','ignore').decode().lower()
            return re.sub(r'[^a-z0-9]+','_',text).strip('_')
        aliases={
            'tipo':['tipo','tipo_operacao','operacao'],
            'transportadora':['transportadora','carrier'],
            'motorista':['motorista','driver','nome_motorista'],
            'placa':['placa','placa_veiculo','veiculo','vehicle'],
            'documento':['documento','n_documento_carga','numero_documento_carga','nota','nf','pedido','ordem'],
            'carga':['carga','produto','descricao'],
            'peso':['peso','weight'],
            'doca':['doca','dock'],
            'entrada_em':['entrada_em','entrada','data_entrada'],
            'agendado_em':['agendado_em','agendamento','data_agendada','data_hora','datahora'],
            'observacoes':['observacoes','observacao','obs']
        }
        normalized={norm(c):c for c in df.columns}
        def value(row,field):
            for alias in aliases[field]:
                col=normalized.get(alias)
                if col is not None:
                    v=row.get(col)
                    if pd.notna(v):return v.isoformat() if hasattr(v,'isoformat') else str(v).strip()
            return None
        records=[]
        for idx,row in df.iterrows():
            rec={field:value(row,field) for field in aliases}
            # Formato histórico do Logistics: Data Entrada + Hora Entrada em colunas separadas.
            if not rec.get('entrada_em'):
                date_col=normalized.get('data_entrada'); time_col=normalized.get('hora_entrada')
                if date_col is not None:
                    dv=row.get(date_col); tv=row.get(time_col) if time_col is not None else None
                    if pd.notna(dv):
                        try:
                            base=pd.to_datetime(dv)
                            if tv is not None and pd.notna(tv):
                                t=pd.to_datetime(str(tv)).time()
                                base=base.replace(hour=t.hour,minute=t.minute,second=t.second)
                            rec['entrada_em']=base.isoformat()
                        except Exception: pass
            rec['status']='AGUARDANDO'
            rec['origem']='PLANILHA_VALIDADA'
            rec['origem_arquivo']=item['filename']
            rec['origem_registro']=int(idx)+1
            if rec.get('placa') or rec.get('documento') or rec.get('carga') or rec.get('motorista'):
                records.append(rec)
        if not records:return jsonify(error='Nenhum registro identificável foi encontrado para criar operações.'),400
        created,errors=create_operations_batch(records,session.get('user_id'),item['filename'])
        log(f"{item['process_code']} · Operations Core",f"{len(created)} operação(ões) criada(s)")
        return jsonify(ok=True,created=len(created),errors=errors,operations=[x['operation_code'] for x in created],process_code=item['process_code'])
    except Exception as e:
        return jsonify(error=str(e)),400

@app.get('/api/rules')
def get_rules():return jsonify(load_rules())
@app.put('/api/rules')
def put_rules():
    data=request.get_json(silent=True) or {}
    save_rules(data);log('Regras operacionais','Atualizadas');return jsonify(ok=True,rules=data)
@app.get('/api/dashboard')
def dashboard():return jsonify(stats())
@app.get('/api/history')
def get_history():return jsonify(history=history())
@app.get('/api/history/<process_code>')
def get_history_detail(process_code):
    d=process_detail(process_code)
    return jsonify(d) if d else (jsonify(error='Processamento não encontrado.'),404)
@app.get('/api/control-center')
def control_center_api(): return jsonify(operations_control_center())

@app.get('/api/alerts')
def alerts_api(): return jsonify(refresh_operational_alerts())

@app.get('/api/docks/board')
def docks_board_api(): return jsonify(items=dock_board())

@app.route('/api/settings/operational',methods=['GET','PUT'])
def operational_settings_api():
    if request.method=='GET':return jsonify(get_system_settings())
    try:return jsonify(save_system_settings(request.get_json(silent=True) or {}))
    except (ValueError,TypeError):return jsonify(error='Os limites devem ser números inteiros positivos.'),400

@app.get('/api/integration/schema')
def integration_schema_api():
    return jsonify(version='1.0',resource='operations',accepted_origins=['API','TMS','WMS','INTEGRACAO'],
      fields=['tipo','transportadora','motorista','placa','documento','carga','peso','doca','agendado_em','entrada_em','observacoes'])

@app.get('/api/reports/operations')
def operations_report_api():
    return jsonify(operational_report(request.args))

@app.get('/api/reports/operations.csv')
def operations_report_csv():
    report=operational_report(request.args)
    output=io.StringIO(); w=csv.writer(output,delimiter=';')
    w.writerow(['OP','Status','Transportadora','Motorista','Placa','Doca','Entrada','Início','Finalização','Saída','Espera (min)','Operação (min)','Permanência (min)'])
    for r in report['items']:
        w.writerow([r.get('operation_code'),r.get('status'),r.get('transportadora'),r.get('motorista'),r.get('placa'),r.get('doca'),r.get('entrada_em'),r.get('inicio_em'),r.get('finalizado_em'),r.get('saida_em'),r.get('espera_min'),r.get('operacao_min'),r.get('permanencia_min')])
    from flask import Response
    return Response('\ufeff'+output.getvalue(),mimetype='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=relatorio_operacional.csv'})

@app.get('/api/master/legacy-audit')
def master_legacy_audit_api():
    return jsonify(legacy_master_audit())

@app.post('/api/master/<kind>/validate')
def master_validate_api(kind):
    if kind not in {'carriers','drivers','vehicles','docks'}:return jsonify(error='Cadastro inválido.'),404
    d=request.get_json(silent=True) or {}
    items=find_active_master(kind,d.get('value'),d.get('carrier_id'))
    return jsonify(valid=bool(items),items=items)

@app.get('/api/master/<kind>')
def master_list_api(kind):
    if kind not in {'carriers','drivers','vehicles','docks'}:return jsonify(error='Cadastro inválido.'),404
    return jsonify(items=list_master_data(kind))

@app.post('/api/master/<kind>')
def master_create_api(kind):
    if kind not in {'carriers','drivers','vehicles','docks'}:return jsonify(error='Cadastro inválido.'),404
    data=request.get_json(silent=True) or {}
    required='nome' if kind in {'carriers','drivers'} else ('placa' if kind=='vehicles' else 'codigo')
    if not str(data.get(required,'')).strip():return jsonify(error=f'Campo {required} é obrigatório.'),400
    try:
        item_id=create_master_data(kind,data);return jsonify(ok=True,id=item_id),201
    except Exception as e:return jsonify(error=str(e)),400

@app.patch('/api/master/<kind>/<int:item_id>/toggle')
def master_toggle_api(kind,item_id):
    if kind not in {'carriers','drivers','vehicles','docks'}:return jsonify(error='Cadastro inválido.'),404
    return jsonify(ok=toggle_master_data(kind,item_id))

@app.get('/api/operations/dashboard')
def operations_dashboard_api():
    return jsonify(operational_dashboard())

@app.get('/api/operations')
def operations_list_api():return jsonify(operations=list_operations(),stats=operations_stats())
@app.post('/api/operations')
def operations_create_api():
    d=request.get_json(silent=True) or {}
    if not (d.get('placa') or d.get('documento') or d.get('carga')):return jsonify(error='Informe ao menos placa, documento ou carga para identificar a operação.'),400
    try:
        op=create_operation(d,session.get('user_id'));log(f"{op['operation_code']} · Operação",'Criada');return jsonify(ok=True,operation=op),201
    except Exception as e:return jsonify(error=str(e)),400
@app.get('/api/operations/<code>')
def operations_detail_api(code):
    op=get_operation(code);return jsonify(operation=op) if op else (jsonify(error='Operação não encontrada.'),404)
@app.post('/api/operations/<code>/workflow')
def operations_workflow_api(code):
    try:
        d=request.get_json(silent=True) or {}
        op=advance_operation_workflow(code,d.get('action'),session.get('user_id'),d.get('detail') or '',d.get('dock'))
        if not op:return jsonify(error='Operação não encontrada.'),404
        log(f"{code} · Workflow",op['status']);return jsonify(ok=True,operation=op)
    except ValueError as e:return jsonify(error=str(e)),400

@app.patch('/api/operations/<code>/status')
def operations_status_api(code):
    d=request.get_json(silent=True) or {}
    try:
        op=update_operation_status(code,d.get('status'),session.get('user_id'),d.get('detail') or '')
        if not op:return jsonify(error='Operação não encontrada.'),404
        log(f"{code} · Status",op['status']);return jsonify(ok=True,operation=op)
    except ValueError as e:return jsonify(error=str(e)),400



IMPORT_ALIASES={
 'tipo':['tipo','tipo_operacao','operacao'], 'transportadora':['transportadora','carrier'],
 'motorista':['motorista','driver','nome_motorista'], 'placa':['placa','veiculo','vehicle','placa_veiculo'],
 'documento':['documento','nota','nf','pedido','ordem'], 'carga':['carga','produto','descricao'],
 'peso':['peso','weight'], 'doca':['doca','dock'], 'entrada_em':['entrada_em','entrada','data_entrada'],
 'agendado_em':['agendado_em','agendamento','data_agendada','horario','data_hora','datahora'],
 'observacoes':['observacoes','observacao','obs'], 'status':['status']
}
def _norm_key(k):
    import unicodedata,re
    x=unicodedata.normalize('NFKD',str(k)).encode('ascii','ignore').decode().lower().strip()
    return re.sub(r'[^a-z0-9]+','_',x).strip('_')
def _map_record(raw):
    normalized={_norm_key(k):v for k,v in (raw or {}).items()}
    out={}
    for target,aliases in IMPORT_ALIASES.items():
        for a in aliases:
            if a in normalized and normalized[a] not in (None,''):
                out[target]=normalized[a];break
    out['status']=(str(out.get('status') or 'AGUARDANDO')).upper()
    return out

def _parse_import_file(file_storage):
    name=secure_filename(file_storage.filename); ext=Path(name).suffix.lower(); raw=file_storage.read()
    if ext=='.json':
        data=json.loads(raw.decode('utf-8-sig')); rows=data if isinstance(data,list) else data.get('operacoes') or data.get('operations') or data.get('registros') or [data]
    elif ext=='.xml':
        root=ET.fromstring(raw.decode('utf-8-sig')); candidates=list(root)
        if len(candidates)==1 and list(candidates[0]): candidates=list(candidates[0])
        rows=[{child.tag:child.text for child in list(node)} for node in candidates if list(node)]
        if not rows and list(root): rows=[{child.tag:child.text for child in list(root)}]
    elif ext=='.txt':
        text=raw.decode('utf-8-sig'); sample=text[:4096]
        try: dialect=csv.Sniffer().sniff(sample,delimiters=';,\t|')
        except csv.Error: dialect=csv.excel; dialect.delimiter=';'
        rows=list(csv.DictReader(io.StringIO(text),dialect=dialect))
    else: raise ValueError('Formato não suportado. Use .json, .xml ou .txt.')
    if not rows: raise ValueError('Nenhum registro estruturado encontrado no arquivo.')
    return name,[_map_record(x) for x in rows]

@app.post('/api/operations/import/preview')
def operations_import_preview():
    if 'file' not in request.files or not request.files['file'].filename:return jsonify(error='Selecione um arquivo JSON, XML ou TXT.'),400
    try:
        name,rows=_parse_import_file(request.files['file']); token=uuid.uuid4().hex
        analyses['opimport_'+token]={'filename':name,'records':rows}
        return jsonify(token=token,filename=name,count=len(rows),records=rows[:200])
    except Exception as e:return jsonify(error=str(e)),400

@app.post('/api/operations/import/confirm')
def operations_import_confirm():
    d=request.get_json(silent=True) or {}; item=analyses.get('opimport_'+str(d.get('token') or ''))
    if not item:return jsonify(error='Pré-importação expirada. Selecione o arquivo novamente.'),404
    records=d.get('records') if isinstance(d.get('records'),list) else item['records']
    created,errors=create_operations_batch(records,session.get('user_id'),item['filename'])
    log(f"Importação operacional · {item['filename']}",f"{len(created)} criada(s)")
    return jsonify(ok=True,created=len(created),errors=errors,codes=[x['operation_code'] for x in created])

@app.put('/api/operations/<code>')
def operations_update_api(code):
    d=request.get_json(silent=True) or {}
    try:
        op=update_operation(code,d,session.get('user_id'))
        if not op:return jsonify(error='Operação não encontrada.'),404
        log(f'{code} · Operação','Editada');return jsonify(ok=True,operation=op)
    except ValueError as e:return jsonify(error=str(e)),400

@app.post('/api/app/shutdown')
def app_shutdown():
    def _stop():
        import time
        time.sleep(0.35)
        os._exit(0)
    threading.Thread(target=_stop,daemon=True).start()
    return jsonify(ok=True,message='Aplicativo encerrando.')

@app.get('/api/download/<path:name>')
def download(name):return send_from_directory(OUTPUT,name,as_attachment=True)
@app.get('/api/logs')
def logs():
    rows=[]
    if LOG.exists():
        for line in LOG.read_text(encoding='utf-8').splitlines()[-8:]:
            try:rows.append(json.loads(line))
            except:pass
    return jsonify(logs=list(reversed(rows)))
if __name__=='__main__':
    url='http://127.0.0.1:5000'
    # Em builds --windowed, stdout/stderr podem não existir.
    # A inicialização não depende do console.
    # Abre o navegador padrão após o servidor começar a inicializar.
    threading.Timer(1.2, lambda: webbrowser.open(url, new=2)).start()
    app.run(host='127.0.0.1',port=5000,debug=False,use_reloader=False)
