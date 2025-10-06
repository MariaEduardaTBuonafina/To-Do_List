import json
import re
import sqlite3
import datetime
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_PATH = 'tasks.db'
HOST = '0.0.0.0'
PORT = 8000


def init_db():
    """Cria a tabela 'tarefas' caso não exista."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS tarefas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descricao TEXT,
            status TEXT NOT NULL DEFAULT 'pendente',
            criado_em TEXT NOT NULL
        );
    ''')
    conn.commit()
    conn.close()


class TaskHandler(BaseHTTPRequestHandler):
    """Manipulador principal das rotas HTTP /tasks e /tasks/<id>."""

    def _send_cors_headers(self):
        """Adiciona cabeçalhos CORS para compatibilidade com navegadores."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def send_json(self, obj, status=200):
        """Envia uma resposta JSON padronizada."""
        if status == 204:
            self.send_response(204)
            self._send_cors_headers()
            self.end_headers()
            return

        self.send_response(status)
        self._send_cors_headers()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode('utf-8'))

    def _parse_id(self):
        """Extrai e valida o ID da URL, se houver."""
        m = re.match(r'^/tasks(?:/(\d+))?/?$', self.path)
        if not m:
            return None, {'error': 'Rota não encontrada'}, 404
        task_id = m.group(1)
        if task_id:
            try:
                return int(task_id), None, None
            except ValueError:
                return None, {'error': 'ID inválido'}, 400
        return None, None, None

    def _require_json(self):
        """Valida se o Content-Type é JSON e retorna o corpo decodificado."""
        ct = self.headers.get('Content-Type', '')
        if 'application/json' not in ct:
            self.send_json({'error': 'Content-Type deve ser application/json'}, 400)
            return None
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length).decode('utf-8') if length > 0 else '{}'
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            self.send_json({'error': 'JSON inválido'}, 400)
            return None

    def _execute(self, sql, params=(), commit=False, fetchone=False, fetchall=False, retry=3):
        """Executa comandos SQL com retentativa em caso de 'database locked'."""
        for attempt in range(retry):
            try:
                conn = sqlite3.connect(DB_PATH)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(sql, params)
                result = None
                if commit:
                    conn.commit()
                if fetchone:
                    result = cur.fetchone()
                if fetchall:
                    result = cur.fetchall()
                conn.close()
                return result
            except sqlite3.OperationalError as e:
                if 'locked' in str(e).lower() and attempt < retry - 1:
                    time.sleep(0.05 * (attempt + 1))
                    continue
                else:
                    raise

    def do_OPTIONS(self):
        """Responde pré-voos de CORS."""
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        """Lista todas as tarefas ou retorna uma específica."""
        task_id, err, code = self._parse_id()
        if err:
            self.send_json(err, code)
            return

        try:
            if task_id is None:
                rows = self._execute(
                    'SELECT id, titulo, descricao, status, criado_em FROM tarefas ORDER BY id;',
                    fetchall=True
                )
                tasks = [dict(row) for row in rows]
                self.send_json(tasks)
            else:
                row = self._execute(
                    'SELECT id, titulo, descricao, status, criado_em FROM tarefas WHERE id = ?;',
                    (task_id,), fetchone=True
                )
                if not row:
                    self.send_json({'error': 'Tarefa não encontrada'}, 404)
                else:
                    self.send_json(dict(row))
        except Exception as e:
            traceback.print_exc()
            self.send_json({'error': 'Erro interno ao consultar tarefas'}, 500)

    def do_POST(self):
        """Cria uma nova tarefa."""
        if not re.match(r'^/tasks/?$', self.path):
            self.send_json({'error': 'Rota não encontrada'}, 404)
            return

        data = self._require_json()
        if data is None:
            return

        titulo = data.get('titulo')
        descricao = data.get('descricao', '')
        status = data.get('status', 'pendente')

        if not titulo:
            self.send_json({'error': 'Campo "titulo" é obrigatório'}, 400)
            return

        criado_em = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'

        try:
            self._execute(
                'INSERT INTO tarefas (titulo, descricao, status, criado_em) VALUES (?, ?, ?, ?);',
                (titulo, descricao, status, criado_em), commit=True
            )
            row = self._execute(
                'SELECT * FROM tarefas ORDER BY id DESC LIMIT 1;', fetchone=True
            )
            self.send_json({'message': 'Tarefa criada com sucesso', 'tarefa': dict(row)}, 201)
        except Exception:
            traceback.print_exc()
            self.send_json({'error': 'Erro interno ao criar tarefa'}, 500)

    def do_PUT(self):
        """Atualiza parcialmente uma tarefa."""
        task_id, err, code = self._parse_id()
        if err:
            self.send_json(err, code)
            return
        if task_id is None:
            self.send_json({'error': 'ID da tarefa é obrigatório'}, 400)
            return

        data = self._require_json()
        if data is None:
            return

        fields, params = [], []
        for key in ('titulo', 'descricao', 'status'):
            if key in data:
                fields.append(f'{key} = ?')
                params.append(data[key])

        if not fields:
            self.send_json({'error': 'Nenhum campo para atualizar'}, 400)
            return

        params.append(task_id)
        try:
            row = self._execute('SELECT * FROM tarefas WHERE id = ?;', (task_id,), fetchone=True)
            if not row:
                self.send_json({'error': 'Tarefa não encontrada'}, 404)
                return

            sql = f"UPDATE tarefas SET {', '.join(fields)} WHERE id = ?;"
            self._execute(sql, tuple(params), commit=True)
            row = self._execute('SELECT * FROM tarefas WHERE id = ?;', (task_id,), fetchone=True)
            self.send_json({'message': 'Tarefa atualizada', 'tarefa': dict(row)})
        except Exception:
            traceback.print_exc()
            self.send_json({'error': 'Erro interno ao atualizar tarefa'}, 500)

    def do_DELETE(self):
        """Remove uma tarefa pelo ID."""
        task_id, err, code = self._parse_id()
        if err:
            self.send_json(err, code)
            return
        if task_id is None:
            self.send_json({'error': 'ID da tarefa é obrigatório'}, 400)
            return

        try:
            row = self._execute('SELECT * FROM tarefas WHERE id = ?;', (task_id,), fetchone=True)
            if not row:
                self.send_json({'error': 'Tarefa não encontrada'}, 404)
                return

            self._execute('DELETE FROM tarefas WHERE id = ?;', (task_id,), commit=True)
            self.send_json({}, 204)
        except Exception:
            traceback.print_exc()
            self.send_json({'error': 'Erro interno ao deletar tarefa'}, 500)

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {self.command} {self.path} -> {fmt % args}")


if __name__ == '__main__':
    init_db()
    print(f"Servidor rodando em http://{HOST}:{PORT}")
    with ThreadingHTTPServer((HOST, PORT), TaskHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor encerrado.")
            httpd.server_close()