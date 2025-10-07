import argparse
import requests
import sys
import json

def main():
    parser = argparse.ArgumentParser(description="Cliente para a API de tarefas (To-Do List)")
    parser.add_argument("--server", "-s", default="http://localhost:8000", help="URL base do servidor")
    sub = parser.add_subparsers(dest="cmd")

    # req create
    p_create = sub.add_parser("create", help="Criar nova tarefa")
    p_create.add_argument("--titulo", "-t", required=True)
    p_create.add_argument("--descricao", "-d", default="")
    p_create.add_argument("--status", default="pendente")

    # mostra lista
    p_list = sub.add_parser("list", help="Listar todas as tarefas")

    # req get
    p_get = sub.add_parser("get", help="Obter tarefa pelo ID")
    p_get.add_argument("id", type=int)

    # req update
    p_update = sub.add_parser("update", help="Atualizar tarefa")
    p_update.add_argument("id", type=int)
    p_update.add_argument("--titulo", default=None)
    p_update.add_argument("--descricao", default=None)
    p_update.add_argument("--status", default=None)

    # req delete
    p_delete = sub.add_parser("delete", help="Remover tarefa")
    p_delete.add_argument("id", type=int)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(0)

    base = args.server.rstrip("/")
    try:
        if args.cmd == "create":
            payload = {"titulo": args.titulo, "descricao": args.descricao, "status": args.status}
            r = requests.post(f"{base}/tasks", json=payload)
            print("Status:", r.status_code)
            print(json.dumps(r.json(), ensure_ascii=False, indent=2))

        elif args.cmd == "list":
            r = requests.get(f"{base}/tasks")
            print("Status:", r.status_code)
            print(json.dumps(r.json(), ensure_ascii=False, indent=2))

        elif args.cmd == "get":
            r = requests.get(f"{base}/tasks/{args.id}")
            print("Status:", r.status_code)
            print(json.dumps(r.json(), ensure_ascii=False, indent=2))

        elif args.cmd == "update":
            payload = {}
            if args.titulo is not None:
                payload["titulo"] = args.titulo
            if args.descricao is not None:
                payload["descricao"] = args.descricao
            if args.status is not None:
                payload["status"] = args.status

            if not payload:
                print("Nenhum campo informado para atualização.")
                sys.exit(1)

            r = requests.put(f"{base}/tasks/{args.id}", json=payload)
            print("Status:", r.status_code)
            print(json.dumps(r.json(), ensure_ascii=False, indent=2))

        elif args.cmd == "delete":
            r = requests.delete(f"{base}/tasks/{args.id}")
            print("Status:", r.status_code)
            if r.status_code not in (204,):
                print(json.dumps(r.json(), ensure_ascii=False, indent=2))
            else:
                print("Tarefa removida com sucesso.")

    except requests.exceptions.ConnectionError:
        print("Erro: não foi possível conectar ao servidor.")
    except requests.exceptions.RequestException as e:
        print("Erro durante a requisição:", e)


if __name__ == "__main__":
    main()