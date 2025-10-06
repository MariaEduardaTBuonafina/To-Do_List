-- scripts/init_db.sql
CREATE TABLE IF NOT EXISTS tarefas (
id INTEGER PRIMARY KEY AUTOINCREMENT,
titulo TEXT NOT NULL,
descricao TEXT,
status TEXT NOT NULL DEFAULT 'pendente',
criado_em TEXT NOT NULL
);