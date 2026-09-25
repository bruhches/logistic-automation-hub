from pathlib import Path
import os
import sqlite3
from datetime import datetime

BASE = Path(os.environ.get('HUB_DATA_ROOT') or Path(__file__).resolve().parents[1])
DB = BASE / 'database' / 'logistics_hub.db'
DB.parent.mkdir(parents=True, exist_ok=True)


def connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    return con


def init_db():
    with connect() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS processamentos(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          token TEXT UNIQUE,
          process_code TEXT UNIQUE,
          arquivo TEXT,
          data TEXT,
          registros INTEGER,
          ocorrencias INTEGER,
          status TEXT,
          finalizado_em TEXT,
          regras_json TEXT
        );
        CREATE TABLE IF NOT EXISTS usuarios(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          nome TEXT NOT NULL,
          ativo INTEGER NOT NULL DEFAULT 1,
          criado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS operacoes(
          id INTEGER PRIMARY KEY AUTOINCREMENT, operation_code TEXT UNIQUE,
          status TEXT NOT NULL DEFAULT 'AGUARDANDO', tipo TEXT, transportadora TEXT,
          motorista TEXT, placa TEXT, documento TEXT, carga TEXT, peso REAL, doca TEXT,
          entrada_em TEXT, inicio_em TEXT, finalizado_em TEXT, saida_em TEXT,
          observacoes TEXT, origem TEXT NOT NULL DEFAULT 'MANUAL', criado_por INTEGER,
          criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL,
          FOREIGN KEY(criado_por) REFERENCES usuarios(id)
        );
        CREATE TABLE IF NOT EXISTS movimentacoes_operacao(
          id INTEGER PRIMARY KEY AUTOINCREMENT, operacao_id INTEGER NOT NULL,
          evento TEXT NOT NULL, status_anterior TEXT, status_novo TEXT, detalhe TEXT,
          usuario_id INTEGER, data TEXT NOT NULL,
          FOREIGN KEY(operacao_id) REFERENCES operacoes(id) ON DELETE CASCADE,
          FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        );
        CREATE TABLE IF NOT EXISTS transportadoras(
          id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE, documento TEXT,
          contato TEXT, telefone TEXT, email TEXT, ativo INTEGER NOT NULL DEFAULT 1,
          criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS motoristas(
          id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, documento TEXT,
          telefone TEXT, transportadora_id INTEGER, ativo INTEGER NOT NULL DEFAULT 1,
          criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL,
          FOREIGN KEY(transportadora_id) REFERENCES transportadoras(id)
        );
        CREATE TABLE IF NOT EXISTS veiculos(
          id INTEGER PRIMARY KEY AUTOINCREMENT, placa TEXT NOT NULL UNIQUE, descricao TEXT,
          transportadora_id INTEGER, ativo INTEGER NOT NULL DEFAULT 1,
          criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL,
          FOREIGN KEY(transportadora_id) REFERENCES transportadoras(id)
        );
        CREATE TABLE IF NOT EXISTS docas(
          id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT NOT NULL UNIQUE, descricao TEXT,
          status TEXT NOT NULL DEFAULT 'DISPONÍVEL', ativo INTEGER NOT NULL DEFAULT 1,
          criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS decisoes(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          processamento_id INTEGER,
          finding_id TEXT,
          hub_id TEXT,
          linha INTEGER,
          linha_final INTEGER,
          tipo TEXT,
          severidade TEXT,
          decisao TEXT,
          data TEXT,
          FOREIGN KEY(processamento_id) REFERENCES processamentos(id),
          UNIQUE(processamento_id,finding_id)
        );
        ''')
        con.executescript('''
        CREATE TABLE IF NOT EXISTS system_settings(
          chave TEXT PRIMARY KEY, valor TEXT NOT NULL, atualizado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS operational_alerts(
          id INTEGER PRIMARY KEY AUTOINCREMENT, operation_id INTEGER NOT NULL, tipo TEXT NOT NULL,
          mensagem TEXT NOT NULL, severidade TEXT NOT NULL DEFAULT 'ATENÇÃO', ativo INTEGER NOT NULL DEFAULT 1,
          criado_em TEXT NOT NULL, resolvido_em TEXT,
          FOREIGN KEY(operation_id) REFERENCES operacoes(id),
          UNIQUE(operation_id,tipo,ativo)
        );
        ''')
        defaults={'alert_wait_min':'60','alert_operation_min':'120','alert_stay_min':'240'}
        now=datetime.now().isoformat(timespec='seconds')
        for k,v in defaults.items():
            con.execute('INSERT OR IGNORE INTO system_settings(chave,valor,atualizado_em) VALUES(?,?,?)',(k,v,now))
        pcols = {r['name'] for r in con.execute('PRAGMA table_info(processamentos)')}
        for name, ddl in {
            'process_code': 'ALTER TABLE processamentos ADD COLUMN process_code TEXT',
            'finalizado_em': 'ALTER TABLE processamentos ADD COLUMN finalizado_em TEXT',
            'regras_json': 'ALTER TABLE processamentos ADD COLUMN regras_json TEXT'
        }.items():
            if name not in pcols:
                con.execute(ddl)
        ocols = {r['name'] for r in con.execute('PRAGMA table_info(operacoes)')}
        for name, ddl in {
            'agendado_em': 'ALTER TABLE operacoes ADD COLUMN agendado_em TEXT',
            'origem_arquivo': 'ALTER TABLE operacoes ADD COLUMN origem_arquivo TEXT',
            'origem_registro': 'ALTER TABLE operacoes ADD COLUMN origem_registro TEXT'
        }.items():
            if name not in ocols:
                con.execute(ddl)
        dcols = {r['name'] for r in con.execute('PRAGMA table_info(decisoes)')}
        for name, ddl in {
            'hub_id': 'ALTER TABLE decisoes ADD COLUMN hub_id TEXT',
            'linha_final': 'ALTER TABLE decisoes ADD COLUMN linha_final INTEGER',
            'severidade': 'ALTER TABLE decisoes ADD COLUMN severidade TEXT'
        }.items():
            if name not in dcols:
                con.execute(ddl)
        # Migração: execuções antigas ganham um código estável sem perder histórico.
        old = con.execute("SELECT id FROM processamentos WHERE process_code IS NULL OR TRIM(process_code)='' ORDER BY id").fetchall()
        for row in old:
            con.execute('UPDATE processamentos SET process_code=? WHERE id=?', (f"PROC-{row['id']:06d}", row['id']))
        con.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_process_code ON processamentos(process_code)')
        # V1.1-dev5: normaliza status legado para o novo workflow operacional.
        con.execute("UPDATE operacoes SET status='EM OPERAÇÃO' WHERE status='EM ANDAMENTO'")


def create_process(token, arquivo, registros, ocorrencias, regras=None):
    now = datetime.now().isoformat(timespec='seconds')
    with connect() as con:
        cur = con.execute(
            'INSERT INTO processamentos(token,arquivo,data,registros,ocorrencias,status,regras_json) VALUES(?,?,?,?,?,?,?)',
            (token, arquivo, now, registros, ocorrencias, 'ANALISADO', __import__('json').dumps(regras or {},ensure_ascii=False))
        )
        pid = cur.lastrowid
        code = f'PROC-{pid:06d}'
        con.execute('UPDATE processamentos SET process_code=? WHERE id=?', (code, pid))
        return pid, code


def save_decision(pid, finding):
    with connect() as con:
        con.execute('''
        INSERT INTO decisoes(processamento_id,finding_id,hub_id,linha,linha_final,tipo,severidade,decisao,data)
        VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(processamento_id,finding_id) DO UPDATE SET
          hub_id=excluded.hub_id, linha=excluded.linha, linha_final=excluded.linha_final,
          tipo=excluded.tipo, severidade=excluded.severidade, decisao=excluded.decisao, data=excluded.data
        ''', (
            pid, finding['id'], finding.get('hub_id'), finding['excel_row'], finding.get('final_excel_row'),
            finding['type'], finding.get('severity'), finding.get('decision', 'Revisar'),
            datetime.now().isoformat(timespec='seconds')
        ))


def finish(pid):
    with connect() as con:
        con.execute("UPDATE processamentos SET status='PROCESSADO', finalizado_em=? WHERE id=?",
                    (datetime.now().isoformat(timespec='seconds'), pid))


def stats():
    with connect() as con:
        p = con.execute('SELECT COUNT(*) n, COALESCE(SUM(registros),0) r, COALESCE(SUM(ocorrencias),0) o FROM processamentos').fetchone()
        d = con.execute('''SELECT
            SUM(CASE WHEN decisao='Manter' THEN 1 ELSE 0 END) manter,
            SUM(CASE WHEN decisao='Remover' THEN 1 ELSE 0 END) remover,
            SUM(CASE WHEN decisao='Revisar' THEN 1 ELSE 0 END) revisar,
            COUNT(*) total
            FROM decisoes''').fetchone()
    return {
        'files': p['n'], 'records': p['r'], 'occurrences': p['o'], 'decisions': d['total'] or 0,
        'keep': d['manter'] or 0, 'remove': d['remover'] or 0, 'review': d['revisar'] or 0
    }


def history(limit=50):
    with connect() as con:
        rows = con.execute('''
        SELECT p.id,p.process_code,p.arquivo,p.data,p.finalizado_em,p.registros,p.ocorrencias,p.status,
          SUM(CASE WHEN d.decisao='Manter' THEN 1 ELSE 0 END) manter,
          SUM(CASE WHEN d.decisao='Remover' THEN 1 ELSE 0 END) remover,
          SUM(CASE WHEN d.decisao='Revisar' THEN 1 ELSE 0 END) revisar
        FROM processamentos p LEFT JOIN decisoes d ON d.processamento_id=p.id
        GROUP BY p.id ORDER BY p.id DESC LIMIT ?
        ''', (limit,)).fetchall()
    return [dict(r) for r in rows]


def process_detail(process_code):
    with connect() as con:
        p = con.execute('SELECT * FROM processamentos WHERE process_code=?', (process_code,)).fetchone()
        if not p:
            return None
        ds = con.execute('''SELECT finding_id,hub_id,linha,linha_final,tipo,severidade,decisao,data
                            FROM decisoes WHERE processamento_id=? ORDER BY linha,finding_id''', (p['id'],)).fetchall()
    return {'process': dict(p), 'decisions': [dict(x) for x in ds]}


def user_count():
    with connect() as con:
        return con.execute('SELECT COUNT(*) n FROM usuarios').fetchone()['n']

def create_user(username, password_hash, nome):
    now = datetime.now().isoformat(timespec='seconds')
    with connect() as con:
        cur = con.execute('INSERT INTO usuarios(username,password_hash,nome,ativo,criado_em) VALUES(?,?,?,?,?)',
                          (username.strip().lower(), password_hash, nome.strip(), 1, now))
        return cur.lastrowid

def get_user(username):
    with connect() as con:
        row = con.execute('SELECT * FROM usuarios WHERE username=? AND ativo=1', (username.strip().lower(),)).fetchone()
    return dict(row) if row else None

def get_user_by_id(user_id):
    with connect() as con:
        row = con.execute('SELECT id,username,nome,ativo,criado_em FROM usuarios WHERE id=? AND ativo=1', (user_id,)).fetchone()
    return dict(row) if row else None

# V1.1-dev1 - Operations Core
def create_operation(data, user_id):
    now=datetime.now().isoformat(timespec='seconds')
    allowed={'AGUARDANDO','NO PÁTIO','EM OPERAÇÃO','FINALIZADO','CONCLUÍDA','CANCELADO'}
    status=(data.get('status') or 'AGUARDANDO').strip().upper()
    if status not in allowed: status='AGUARDANDO'
    vals=(status,(data.get('tipo') or '').strip(),(data.get('transportadora') or '').strip(),(data.get('motorista') or '').strip(),(data.get('placa') or '').strip().upper(),(data.get('documento') or '').strip(),(data.get('carga') or '').strip(),data.get('peso') or None,(data.get('doca') or '').strip(),data.get('entrada_em') or None,data.get('agendado_em') or None,(data.get('observacoes') or '').strip(),(data.get('origem') or 'MANUAL').strip().upper(),(data.get('origem_arquivo') or '').strip(),str(data.get('origem_registro') or '').strip(),user_id,now,now)
    with connect() as con:
        cur=con.execute('INSERT INTO operacoes(status,tipo,transportadora,motorista,placa,documento,carga,peso,doca,entrada_em,agendado_em,observacoes,origem,origem_arquivo,origem_registro,criado_por,criado_em,atualizado_em) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',vals)
        oid=cur.lastrowid; code=f'OP-{oid:06d}'
        con.execute('UPDATE operacoes SET operation_code=? WHERE id=?',(code,oid))
        con.execute('INSERT INTO movimentacoes_operacao(operacao_id,evento,status_novo,detalhe,usuario_id,data) VALUES(?,?,?,?,?,?)',(oid,'CRIACAO',status,'Operação criada',user_id,now))
    return get_operation(code)

def list_operations(limit=200):
    with connect() as con:
        rows=con.execute('SELECT o.*,u.nome criado_por_nome FROM operacoes o LEFT JOIN usuarios u ON u.id=o.criado_por ORDER BY o.id DESC LIMIT ?',(limit,)).fetchall()
    return [dict(r) for r in rows]

def get_operation(code):
    with connect() as con:
        row=con.execute('SELECT o.*,u.nome criado_por_nome FROM operacoes o LEFT JOIN usuarios u ON u.id=o.criado_por WHERE o.operation_code=?',(code,)).fetchone()
        if not row:return None
        moves=con.execute('SELECT m.*,u.nome usuario_nome FROM movimentacoes_operacao m LEFT JOIN usuarios u ON u.id=m.usuario_id WHERE m.operacao_id=? ORDER BY m.id DESC',(row['id'],)).fetchall()
    d=dict(row);d['movimentacoes']=[dict(x) for x in moves];return d

def update_operation_status(code,status,user_id,detail=''):
    # Mantido para compatibilidade. O workflow da dev5 deve usar advance_operation_workflow.
    allowed={'AGUARDANDO','NO PÁTIO','EM OPERAÇÃO','FINALIZADO','CONCLUÍDA','CANCELADO'}
    status=(status or '').strip().upper()
    if status not in allowed: raise ValueError('Status inválido.')
    now=datetime.now().isoformat(timespec='seconds')
    with connect() as con:
        row=con.execute('SELECT id,status FROM operacoes WHERE operation_code=?',(code,)).fetchone()
        if not row:return None
        old=row['status']
        con.execute('UPDATE operacoes SET status=?, atualizado_em=? WHERE id=?',(status,now,row['id']))
        con.execute('INSERT INTO movimentacoes_operacao(operacao_id,evento,status_anterior,status_novo,detalhe,usuario_id,data) VALUES(?,?,?,?,?,?,?)',(row['id'],'ALTERACAO_STATUS',old,status,detail or 'Status atualizado',user_id,now))
    return get_operation(code)

def advance_operation_workflow(code, action, user_id, detail='', dock=None):
    transitions={
        'registrar_entrada': ('AGUARDANDO','NO PÁTIO','ENTRADA_REGISTRADA'),
        'iniciar_operacao': ('NO PÁTIO','EM OPERAÇÃO','OPERACAO_INICIADA'),
        'finalizar_operacao': ('EM OPERAÇÃO','FINALIZADO','OPERACAO_FINALIZADA'),
        'registrar_saida': ('FINALIZADO','CONCLUÍDA','SAIDA_REGISTRADA'),
    }
    if action not in transitions: raise ValueError('Ação operacional inválida.')
    expected,new_status,event=transitions[action]
    now=datetime.now().isoformat(timespec='seconds')
    with connect() as con:
        row=con.execute('SELECT * FROM operacoes WHERE operation_code=?',(code,)).fetchone()
        if not row:return None
        if row['status'] != expected:
            raise ValueError(f'Ação não permitida para o status atual ({row["status"]}).')
        updates={'status':new_status,'atualizado_em':now}
        if action=='registrar_entrada': updates['entrada_em']=now
        elif action=='iniciar_operacao':
            updates['inicio_em']=now
            chosen=(str(dock).strip() if dock is not None and str(dock).strip() else (row['doca'] or '').strip())
            if chosen:
                master=con.execute("SELECT * FROM docas WHERE lower(codigo)=lower(?) AND ativo=1",(chosen,)).fetchone()
                if not master: raise ValueError(f'Doca {chosen} não está ativa/cadastrada.')
                conflict=con.execute("SELECT operation_code FROM operacoes WHERE id<>? AND lower(TRIM(doca))=lower(?) AND status='EM OPERAÇÃO' LIMIT 1",(row['id'],chosen)).fetchone()
                if conflict: raise ValueError(f'Doca {chosen} já está ocupada pela {conflict["operation_code"]}.')
                updates['doca']=chosen
        elif action=='finalizar_operacao': updates['finalizado_em']=now
        elif action=='registrar_saida': updates['saida_em']=now
        sets=', '.join(f'{k}=?' for k in updates)
        con.execute(f'UPDATE operacoes SET {sets} WHERE id=?',(*updates.values(),row['id']))
        extra=detail or {
            'registrar_entrada':'Entrada registrada',
            'iniciar_operacao':'Operação iniciada',
            'finalizar_operacao':'Operação finalizada',
            'registrar_saida':'Saída registrada',
        }[action]
        if action=='iniciar_operacao' and updates.get('doca'):
            extra += f' · Doca {updates["doca"]}'
        con.execute('INSERT INTO movimentacoes_operacao(operacao_id,evento,status_anterior,status_novo,detalhe,usuario_id,data) VALUES(?,?,?,?,?,?,?)',(row['id'],event,row['status'],new_status,extra,user_id,now))
    return get_operation(code)

def operations_stats():
    with connect() as con:
        rows=con.execute('SELECT status,COUNT(*) n FROM operacoes GROUP BY status').fetchall();total=con.execute('SELECT COUNT(*) n FROM operacoes').fetchone()['n']
    by={r['status']:r['n'] for r in rows}
    return {'total':total,'waiting':by.get('AGUARDANDO',0)+by.get('NO PÁTIO',0),'active':by.get('EM OPERAÇÃO',0),'finished':by.get('FINALIZADO',0)+by.get('CONCLUÍDA',0),'cancelled':by.get('CANCELADO',0)}



def operational_dashboard():
    with connect() as con:
        rows = con.execute(
            "SELECT operation_code,status,transportadora,motorista,placa,doca,"
            "agendado_em,entrada_em,inicio_em,finalizado_em,saida_em,origem,criado_em,atualizado_em "
            "FROM operacoes ORDER BY id DESC"
        ).fetchall()

    status_keys = ['AGUARDANDO','NO PÁTIO','EM OPERAÇÃO','FINALIZADO','CONCLUÍDA','CANCELADO']
    by_status = {key: 0 for key in status_keys}
    wait_minutes = []
    operation_minutes = []
    permanence_minutes = []

    def parse_dt(value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None

    for row in rows:
        item = dict(row)
        status = item.get('status') or 'AGUARDANDO'
        by_status[status] = by_status.get(status, 0) + 1
        created = parse_dt(item.get('criado_em'))
        entry = parse_dt(item.get('entrada_em'))
        start = parse_dt(item.get('inicio_em'))
        finish = parse_dt(item.get('finalizado_em'))
        exit_dt = parse_dt(item.get('saida_em'))
        wait_from = entry or created
        if wait_from and start and start >= wait_from:
            wait_minutes.append((start - wait_from).total_seconds() / 60)
        if start and finish and finish >= start:
            operation_minutes.append((finish - start).total_seconds() / 60)
        permanence_from = entry or created
        if permanence_from and exit_dt and exit_dt >= permanence_from:
            permanence_minutes.append((exit_dt - permanence_from).total_seconds() / 60)

    def avg(values):
        return round(sum(values) / len(values), 1) if values else None

    recent = []
    for row in rows[:8]:
        item = dict(row)
        recent.append({key: item.get(key) for key in [
            'operation_code','status','placa','motorista','transportadora',
            'doca','origem','atualizado_em'
        ]})

    return {
        'total': len(rows),
        'by_status': by_status,
        'waiting': by_status.get('AGUARDANDO', 0),
        'yard': by_status.get('NO PÁTIO', 0),
        'active': by_status.get('EM OPERAÇÃO', 0),
        'finished': by_status.get('FINALIZADO', 0),
        'completed': by_status.get('CONCLUÍDA', 0),
        'cancelled': by_status.get('CANCELADO', 0),
        'avg_wait_minutes': avg(wait_minutes),
        'avg_operation_minutes': avg(operation_minutes),
        'avg_permanence_minutes': avg(permanence_minutes),
        'recent': recent
    }


def update_operation(code, data, user_id):
    allowed={'AGUARDANDO','NO PÁTIO','EM OPERAÇÃO','FINALIZADO','CONCLUÍDA','CANCELADO'}
    fields=['tipo','transportadora','motorista','placa','documento','carga','peso','doca','entrada_em','agendado_em','observacoes']
    now=datetime.now().isoformat(timespec='seconds')
    with connect() as con:
        row=con.execute('SELECT * FROM operacoes WHERE operation_code=?',(code,)).fetchone()
        if not row:return None
        changes=[]; values=[]
        for f in fields:
            if f in data:
                val=data.get(f)
                if isinstance(val,str): val=val.strip()
                if f=='placa' and val: val=val.upper()
                if f=='peso' and val in ('',None): val=None
                if val != row[f]:
                    changes.append(f'{f}: {row[f] if row[f] not in (None, "") else "—"} → {val if val not in (None, "") else "—"}')
                values.append(val)
            else: values.append(row[f])
        # Status é controlado pelo workflow; edição altera somente dados cadastrais.
        status=row['status']
        con.execute('UPDATE operacoes SET tipo=?,transportadora=?,motorista=?,placa=?,documento=?,carga=?,peso=?,doca=?,entrada_em=?,agendado_em=?,observacoes=?,status=?,atualizado_em=? WHERE id=?',(*values,status,now,row['id']))
        if changes:
            con.execute('INSERT INTO movimentacoes_operacao(operacao_id,evento,status_anterior,status_novo,detalhe,usuario_id,data) VALUES(?,?,?,?,?,?,?)',(row['id'],'EDICAO',row['status'],status,'; '.join(changes),user_id,now))
    return get_operation(code)

def create_operations_batch(records, user_id, source_file=''):
    created=[]; errors=[]
    for i,data in enumerate(records,1):
        try:
            d=dict(data); d['origem']=d.get('origem') or 'IMPORTACAO'; d['origem_arquivo']=source_file; d['origem_registro']=d.get('origem_registro') or i
            if not (d.get('placa') or d.get('documento') or d.get('carga') or d.get('motorista')):
                raise ValueError('Registro sem identificador mínimo (placa, documento, carga ou motorista).')
            created.append(create_operation(d,user_id))
        except Exception as e: errors.append({'linha':i,'erro':str(e)})
    return created,errors

def list_master_data(kind):
    tables={'carriers':'transportadoras','drivers':'motoristas','vehicles':'veiculos','docks':'docas'}
    table=tables[kind]
    with connect() as con:
        if kind in {'drivers','vehicles'}:
            rows=con.execute(f'''SELECT x.*,t.nome transportadora_nome FROM {table} x
                                LEFT JOIN transportadoras t ON t.id=x.transportadora_id ORDER BY x.id DESC''').fetchall()
        else: rows=con.execute(f'SELECT * FROM {table} ORDER BY id DESC').fetchall()
    return [dict(r) for r in rows]

def create_master_data(kind,data):
    now=datetime.now().isoformat(timespec='seconds')
    with connect() as con:
        if kind=='carriers':
            cur=con.execute('INSERT INTO transportadoras(nome,documento,contato,telefone,email,criado_em,atualizado_em) VALUES(?,?,?,?,?,?,?)',
                (data.get('nome','').strip(),data.get('documento'),data.get('contato'),data.get('telefone'),data.get('email'),now,now))
        elif kind=='drivers':
            cur=con.execute('INSERT INTO motoristas(nome,documento,telefone,transportadora_id,criado_em,atualizado_em) VALUES(?,?,?,?,?,?)',
                (data.get('nome','').strip(),data.get('documento') or None,data.get('telefone'),data.get('transportadora_id') or None,now,now))
        elif kind=='vehicles':
            cur=con.execute('INSERT INTO veiculos(placa,descricao,transportadora_id,criado_em,atualizado_em) VALUES(?,?,?,?,?)',
                (data.get('placa','').strip().upper(),data.get('descricao'),data.get('transportadora_id') or None,now,now))
        elif kind=='docks':
            cur=con.execute('INSERT INTO docas(codigo,descricao,status,criado_em,atualizado_em) VALUES(?,?,?,?,?)',
                (data.get('codigo','').strip().upper(),data.get('descricao'),data.get('status') or 'DISPONÍVEL',now,now))
        return cur.lastrowid

def toggle_master_data(kind,item_id):
    tables={'carriers':'transportadoras','drivers':'motoristas','vehicles':'veiculos','docks':'docas'}
    table=tables[kind];now=datetime.now().isoformat(timespec='seconds')
    with connect() as con:
        row=con.execute(f'SELECT ativo FROM {table} WHERE id=?',(item_id,)).fetchone()
        if not row:return False
        con.execute(f'UPDATE {table} SET ativo=?,atualizado_em=? WHERE id=?',(0 if row['ativo'] else 1,now,item_id))
    return True

def find_active_master(kind, value, carrier_id=None):
    value=(value or '').strip()
    if not value:return []
    with connect() as con:
        if kind=='carriers':
            rows=con.execute("SELECT * FROM transportadoras WHERE ativo=1 AND lower(nome)=lower(?)",(value,)).fetchall()
        elif kind=='drivers':
            if carrier_id:
                rows=con.execute("SELECT * FROM motoristas WHERE ativo=1 AND lower(nome)=lower(?) AND transportadora_id=?",(value,carrier_id)).fetchall()
            else: rows=con.execute("SELECT * FROM motoristas WHERE ativo=1 AND lower(nome)=lower(?)",(value,)).fetchall()
        elif kind=='vehicles':
            rows=con.execute("SELECT * FROM veiculos WHERE ativo=1 AND upper(placa)=upper(?)",(value,)).fetchall()
        elif kind=='docks':
            rows=con.execute("SELECT * FROM docas WHERE ativo=1 AND status='DISPONÍVEL' AND upper(codigo)=upper(?)",(value,)).fetchall()
        else:return []
    return [dict(r) for r in rows]

def legacy_master_audit():
    """Valores textuais usados em OPs que ainda não têm correspondente ativo/inativo no cadastro mestre."""
    specs={
      'carriers':('transportadora','transportadoras','nome'),
      'drivers':('motorista','motoristas','nome'),
      'vehicles':('placa','veiculos','placa'),
      'docks':('doca','docas','codigo'),
    }
    out={}
    with connect() as con:
        for kind,(op_col,table,master_col) in specs.items():
            vals=con.execute(f"""SELECT {op_col} value, COUNT(*) uses
                FROM operacoes WHERE TRIM(COALESCE({op_col},''))<>''
                GROUP BY lower(TRIM({op_col})) ORDER BY {op_col}""").fetchall()
            items=[]
            for row in vals:
                value=row['value'].strip()
                master=con.execute(f"SELECT * FROM {table} WHERE lower(TRIM({master_col}))=lower(?) LIMIT 1",(value,)).fetchone()
                # Para motorista, o nome sozinho não define vínculo; mostramos transportadoras históricas para decisão humana.
                carriers=[]
                if kind=='drivers':
                    carriers=[r['transportadora'] for r in con.execute("""SELECT DISTINCT transportadora FROM operacoes
                        WHERE lower(TRIM(motorista))=lower(?) AND TRIM(COALESCE(transportadora,''))<>'' ORDER BY transportadora""",(value,)).fetchall()]
                items.append({'value':value,'uses':row['uses'],'registered':bool(master),'active':bool(master['ativo']) if master else False,
                              'master_id':master['id'] if master else None,'historical_carriers':carriers})
            out[kind]=items
    return out

def operational_report(filters=None):
    filters=filters or {}; where=[]; args=[]
    mapping={'status':'status','transportadora':'transportadora','motorista':'motorista','placa':'placa','doca':'doca'}
    for key,col in mapping.items():
        v=(filters.get(key) or '').strip()
        if v: where.append(f"lower({col})=lower(?)");args.append(v)
    start=(filters.get('start') or '').strip(); end=(filters.get('end') or '').strip()
    if start: where.append("COALESCE(entrada_em,agendado_em,criado_em)>=?");args.append(start)
    if end: where.append("COALESCE(entrada_em,agendado_em,criado_em)<=?");args.append(end+'T23:59:59' if len(end)==10 else end)
    sql="SELECT * FROM operacoes"+(" WHERE "+" AND ".join(where) if where else "")+" ORDER BY id DESC"
    with connect() as con: rows=[dict(r) for r in con.execute(sql,args).fetchall()]
    def mins(a,b):
        if not a or not b:return None
        try:return round((datetime.fromisoformat(b)-datetime.fromisoformat(a)).total_seconds()/60,1)
        except:return None
    for r in rows:
        r['espera_min']=mins(r.get('entrada_em'),r.get('inicio_em'))
        r['operacao_min']=mins(r.get('inicio_em'),r.get('finalizado_em'))
        r['permanencia_min']=mins(r.get('entrada_em'),r.get('saida_em'))
    def avg(k):
        vals=[r[k] for r in rows if r[k] is not None];return round(sum(vals)/len(vals),1) if vals else None
    return {'items':rows,'total':len(rows),'avg_wait':avg('espera_min'),'avg_operation':avg('operacao_min'),'avg_stay':avg('permanencia_min')}

def get_system_settings():
    with connect() as con:return {r['chave']:r['valor'] for r in con.execute("SELECT chave,valor FROM system_settings")}
def save_system_settings(data):
    allowed={'alert_wait_min','alert_operation_min','alert_stay_min'};now=datetime.now().isoformat(timespec='seconds')
    with connect() as con:
        for k in allowed:
            if k in data:
                v=str(max(1,int(data[k])));con.execute("""INSERT INTO system_settings(chave,valor,atualizado_em) VALUES(?,?,?)
                    ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor,atualizado_em=excluded.atualizado_em""",(k,v,now))
    return get_system_settings()
def dock_board():
    with connect() as con:
        docks=[dict(r) for r in con.execute("SELECT * FROM docas WHERE ativo=1 ORDER BY codigo")]
        ops=[dict(r) for r in con.execute("""SELECT * FROM operacoes WHERE TRIM(COALESCE(doca,''))<>'' AND status IN ('NO PÁTIO','EM OPERAÇÃO','FINALIZADO') ORDER BY id DESC""")]
    by={}
    for o in ops:by.setdefault(o['doca'].strip().lower(),o)
    for d in docks:d['operation']=by.get(d['codigo'].strip().lower())
    return docks
def refresh_operational_alerts():
    settings=get_system_settings(); now=datetime.now(); created=0
    with connect() as con:
        ops=[dict(r) for r in con.execute("SELECT * FROM operacoes WHERE status NOT IN ('CONCLUÍDA','CANCELADO')")]
        for o in ops:
            checks=[]
            def elapsed(field):
                try:return (now-datetime.fromisoformat(o[field])).total_seconds()/60 if o.get(field) else None
                except:return None
            wait=elapsed('entrada_em') if not o.get('inicio_em') else None
            operation=elapsed('inicio_em') if o.get('inicio_em') and not o.get('finalizado_em') else None
            stay=elapsed('entrada_em') if o.get('entrada_em') and not o.get('saida_em') else None
            if wait is not None and wait>=int(settings['alert_wait_min']):checks.append(('ESPERA',f"{o['operation_code']} aguardando há {round(wait)} min"))
            if operation is not None and operation>=int(settings['alert_operation_min']):checks.append(('OPERAÇÃO',f"{o['operation_code']} em operação há {round(operation)} min"))
            if stay is not None and stay>=int(settings['alert_stay_min']):checks.append(('PERMANÊNCIA',f"{o['operation_code']} no local há {round(stay)} min"))
            active_types={x[0] for x in checks}
            existing=[dict(r) for r in con.execute("SELECT * FROM operational_alerts WHERE operation_id=? AND ativo=1",(o['id'],))]
            for a in existing:
                if a['tipo'] not in active_types:con.execute("UPDATE operational_alerts SET ativo=0,resolvido_em=? WHERE id=?",(now.isoformat(timespec='seconds'),a['id']))
            for typ,msg in checks:
                if not any(a['tipo']==typ for a in existing):
                    con.execute("INSERT INTO operational_alerts(operation_id,tipo,mensagem,severidade,criado_em) VALUES(?,?,?,?,?)",(o['id'],typ,msg,'ATENÇÃO',now.isoformat(timespec='seconds')));created+=1
        rows=[dict(r) for r in con.execute("""SELECT a.*,o.operation_code,o.status,o.doca,o.placa,o.motorista FROM operational_alerts a JOIN operacoes o ON o.id=a.operation_id WHERE a.ativo=1 ORDER BY a.id DESC""")]
    return {'items':rows,'created':created}
def operations_control_center():
    with connect() as con:
        rows=[dict(r) for r in con.execute("""SELECT * FROM operacoes WHERE status NOT IN ('CONCLUÍDA','CANCELADO') ORDER BY id DESC""")]
    counts={}
    for r in rows:counts[r['status']]=counts.get(r['status'],0)+1
    return {'items':rows,'by_status':counts,'total':len(rows),'docks':dock_board(),'alerts':refresh_operational_alerts()['items']}
