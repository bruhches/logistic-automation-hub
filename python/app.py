from pathlib import Path
import sys,uuid,json,os,secrets,webbrowser,threading,shutil
from datetime import datetime
from flask import Flask,request,jsonify,send_from_directory,session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash,check_password_hash
# Recursos empacotados e dados mutáveis ficam separados.
# Release Candidate: dados do usuário ficam sob a identidade B.A Dev Lab.
PROJECT_BASE=Path(__file__).resolve().parents[1]
RESOURCE_BASE=Path(getattr(sys,'_MEIPASS',PROJECT_BASE)) if getattr(sys,'frozen',False) else PROJECT_BASE
if getattr(sys,'frozen',False):
    local_appdata=Path(os.environ.get('LOCALAPPDATA') or (Path.home()/'AppData'/'Local'))
    DATA_BASE=local_appdata/'BA Dev Lab'/'Logistics Automation Hub'
    LEGACY_DATA_BASE=local_appdata/'LogisticsAutomationHub'
    # Migração única e conservadora: preserva o Build 3 e copia seus dados apenas
    # quando o novo diretório ainda não existe. Assim, usuário/histórico não somem.
    if not DATA_BASE.exists() and LEGACY_DATA_BASE.exists():
        DATA_BASE.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(LEGACY_DATA_BASE,DATA_BASE)
else:
    DATA_BASE=PROJECT_BASE
DATA_BASE.mkdir(parents=True,exist_ok=True)
os.environ['HUB_DATA_ROOT']=str(DATA_BASE)
sys.path.insert(0,str(Path(__file__).resolve().parent))

from modules.spreadsheet.processor import SpreadsheetProcessor
from database import init_db,create_process,save_decision,finish,stats,history,process_detail,user_count,create_user,get_user,get_user_by_id

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
def health():return jsonify(status='online',module='spreadsheet',version='1.0')
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
        result=processor.process(item['path'],out,item['analysis'],item['decisions'],item['process_code'],now)
        for f in item['analysis']['findings']: save_decision(item['pid'],f)
        finish(item['pid']);log(f"{item['process_code']} · Processamento V1.0",'Concluído');return jsonify(process_code=item['process_code'],output_filename=out.name,removed=result['removed'],download_url=f'/api/download/{out.name}')
    except Exception as e:return jsonify(error=str(e)),500
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
