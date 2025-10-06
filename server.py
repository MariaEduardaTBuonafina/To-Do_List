from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sqlite3
import re
import urllib.parse
import datetime
import argparse

DB_FILE = 'tasks.db'


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tarefas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL,
        descricao TEXT,
        status TEXT NOT NULL DEFAULT 'pendente',
        criado_em TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()


def row_to_dict(row):
    return {
        'id': row['id'],
        'titulo': row['titulo'],
        'descricao': row['descricao'],
        'status': row['status'],
        'criado_em': row['criado_em']
    }


class TaskHandler(BaseHTTPRequestHandler):
    # enviar respostas JSON
    def send_json(self, obj, status=200):
        if status == 204:
            self.send_response(204)
            self.end_headers()
            return
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def parse_path(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        m = re.match(r'^/tasks(?:/(\\d+))?/?$', path)
        if m:
            return ('/tasks', m.group(1))
        return (path, None)

    # listar tarefas
    def do_GET(self):
        route, task_id = self.parse_path()
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        if route == '/tasks' and task_id is None:
            cur.execute('SELECT * FROM tarefas ORDER BY id')
            rows = cur.fetchall()
            tasks = [row_to_dict(r) for r in rows]
            self.send_json(tasks, 200)
            conn.close()
            return

        if route == '/tasks' and task_id is not None:
            cur.execute('SELECT * FROM tarefas WHERE id=?', (task_id,))
            row = cur.fetchone()
            conn.close()
            if row:
                self.send_json(row_to_dict(row), 200)
            else:
                self.send_json({'error': 'Tarefa não encontrada'}, 404)
            return

        self.send_json({'error': 'Rota não encontrada'}, 404)
        conn.close()

    # criar tarefa
    def do_POST(self):
        route, task_id = self.parse_path()
        if route != '/tasks' or task_id is not None:
            self.send_json({'error': 'Rota não encontrada'}, 404)
            return

        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8') if length else ''
        try:
            data = json.loads(body)
        except Exception:
            self.send_json({'error': 'JSON inválido'}, 400)
            return

        titulo = data.get('titulo')
        descricao = data.get('descricao')
        status = data.get('status', 'pendente')

        if not titulo:
            self.send_json({'error': 'Campo \"titulo\" obrigatório'}, 400)
            return

        criado_em = datetime.datetime.utcnow().isoformat()
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute('INSERT INTO tarefas (titulo, descricao, status, criado_em) VALUES (?,?,?,?)',
                    (titulo, descricao, status, criado_em))
        conn.commit()
        task_id = cur.lastrowid
        conn.close()

        self.send_json({
            'id': task_id,
            'titulo': titulo,
            'descricao': descricao,
            'status': status,
            'criado_em': criado_em
        }, 201)

    # atualizar tarefa
    def do_PUT(self):
        route, task_id = self.parse_path()
        if route != '/tasks' or task_id is None:
            self.send_json({'error': 'Rota não encontrada'}, 404)
            return

        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8') if length else ''
        try:
            data = json.loads(body)
        except Exception:
            self.send_json({'error': 'JSON inválido'}, 400)
            return

        allowed = ['titulo', 'descricao', 'status']
        updates = []
        values = []
        for key in allowed:
            if key in data:
                updates.append(f"{key}=?")
                values.append(data[key])

        if not updates:
            self.send_json({'error': 'Nenhum campo válido para atualizar'}, 400)
            return

        values.append(task_id)
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute('SELECT id FROM tarefas WHERE id=?', (task_id,))
        if cur.fetchone() is None:
            conn.close()
            self.send_json({'error': 'Tarefa não encontrada'}, 404)
            return

        sql = 'UPDATE tarefas SET ' + ', '.join(updates) + ' WHERE id=?'
        cur.execute(sql, values)
        conn.commit()

        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT * FROM tarefas WHERE id=?', (task_id,))
        row = cur.fetchone()
        conn.close()
        self.send_json(row_to_dict(row), 200)

    # deletar tarefa
    def do_DELETE(self):
        route, task_id = self.parse_path()
        if route != '/tasks' or task_id is None:
            self.send_json({'error': 'Rota não encontrada'}, 404)
            return

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute('SELECT id FROM tarefas WHERE id=?', (task_id,))
        if cur.fetchone() is None:
            conn.close()
            self.send_json({'error': 'Tarefa não encontrada'}, 404)
            return

        cur.execute('DELETE FROM tarefas WHERE id=?', (task_id,))
        conn.commit()
        conn.close()
        self.send_json({}, 204)

    # log personalizado
    def log_message(self, format, *args):
        print(f"[server] {self.address_string()} - - {format % args}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Servidor ToDo (Backend AV1)')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', default=8000, type=int)
    args = parser.parse_args()

    init_db()

    server = ThreadingHTTPServer((args.host, args.port), TaskHandler)
    print(f'Servidor rodando em http://{args.host}:{args.port} (Ctrl+C para parar)')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nEncerrando...')
        server.server_close()
