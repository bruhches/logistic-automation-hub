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
        pcols = {r['name'] for r in con.execute('PRAGMA table_info(processamentos)')}
        for name, ddl in {
            'process_code': 'ALTER TABLE processamentos ADD COLUMN process_code TEXT',
            'finalizado_em': 'ALTER TABLE processamentos ADD COLUMN finalizado_em TEXT',
            'regras_json': 'ALTER TABLE processamentos ADD COLUMN regras_json TEXT'
        }.items():
            if name not in pcols:
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
