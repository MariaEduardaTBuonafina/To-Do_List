import argparse
import requests
import sys
import json


def make_parser():
    parser = argparse.ArgumentParser(description='Cliente CLI para o servidor ToDo')
    parser.add_argument('--server', default='http://localhost:8000', help='URL base do servidor')
    sub = parser.add_subparsers(dest='cmd')

    p_create = sub.add_parser('create', help='Criar uma nova tarefa')
    p_create.add_argument('--titulo', required=True)
    p_create.add_argument('--descricao')
    p_create.add_argument('--status', choices=['pendente', 'completo'])

    sub.add_parser('list', help='Listar todas as tarefas')

    p_get = sub.add_parser('get', help='Visualizar tarefa por id')
    p_get.add_argument('id', type=int)

    p_update = sub.add_parser('update', help='Atualizar tarefa')
    p_update.add_argument('id', type=int)
    p_update.add_argument('--titulo')
    p_update.add_argument('--descricao')
    p_update.add_argument('--status', choices=['pendente', 'completo'])

    p_delete = sub.add_parser('delete', help='Deletar tarefa por id')
    p_delete.add_argument('id', type=int)

    return parser


def main():
    parser = make_parser()
    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    base = args.server.rstrip('/')

    try:
        if args.cmd == 'create':
            payload = {'titulo': args.titulo}
            if args.descricao:
                payload['descricao'] = args.descricao
            if args.status:
                payload['status'] = args.status
            r = requests.post(f'{base}/tasks', json=payload)
            if r.status_code == 201:
                print('Tarefa criada:')
                print(r.json())
            else:
                print('Erro ao criar:', r.status_code, r.text)

        elif args.cmd == 'list':
            r = requests.get(f'{base}/tasks')
            if r.status_code == 200:
                tasks = r.json()
                if not tasks:
                    print('Nenhuma tarefa encontrada.')
                    return
                for t in tasks:
                    print(f"[{t['id']}] {t['titulo']} - {t['status']} (criado: {t['criado_em']})")
                    if t.get('descricao'):
                        print('   ', t['descricao'])
            else:
                print('Erro ao listar:', r.status_code, r.text)

        elif args.cmd == 'get':
            r = requests.get(f'{base}/tasks/{args.id}')
            if r.status_code == 200:
                print(json.dumps(r.json(), ensure_ascii=False, indent=2))
            else:
                print('Erro:', r.status_code, r.text)

        elif args.cmd == 'update':
            payload = {}
            if args.titulo:
                payload['titulo'] = args.titulo
            if args.descricao is not None:
                payload['descricao'] = args.descricao
            if args.status:
                payload['status'] = args.status
            if not payload:
                print('Nada para atualizar. Use --titulo, --descricao ou --status')
                return
            r = requests.put(f'{base}/tasks/{args.id}', json=payload)
            if r.status_code == 200:
                print('Atualizado:')
                print(r.json())
            else:
                print('Erro ao atualizar:', r.status_code, r.text)

        elif args.cmd == 'delete':
            r = requests.delete(f'{base}/tasks/{args.id}')
            if r.status_code in (200, 204):
                print('Tarefa deletada com sucesso.')
            else:
                print('Erro ao deletar:', r.status_code, r.text)

    except requests.exceptions.ConnectionError:
        print('❌ Não foi possível conectar ao servidor. Verifique se ele está rodando em', base)


if __name__ == '__main__':
    main()
