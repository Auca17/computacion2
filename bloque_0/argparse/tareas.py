import argparse
import json
import sys
from pathlib import Path

ARCHIVO_TAREAS = Path.home() / ".tareas.json"


def cargar_tareas():
	if not ARCHIVO_TAREAS.exists():
		return []

	try:
		with open(ARCHIVO_TAREAS, "r", encoding="utf-8") as f:
			data = json.load(f)
	except (OSError, json.JSONDecodeError, UnicodeDecodeError):
		print("Error: no se pudieron leer las tareas", file=sys.stderr)
		sys.exit(1)

	if not isinstance(data, list):
		print("Error: archivo de tareas invalido", file=sys.stderr)
		sys.exit(1)

	return data


def guardar_tareas(tareas):
	try:
		with open(ARCHIVO_TAREAS, "w", encoding="utf-8") as f:
			json.dump(tareas, f, ensure_ascii=False, indent=2)
	except OSError:
		print("Error: no se pudieron guardar las tareas", file=sys.stderr)
		sys.exit(1)


def buscar_tarea_por_id(tareas, tarea_id):
	for tarea in tareas:
		if tarea.get("id") == tarea_id:
			return tarea
	return None


parser = argparse.ArgumentParser(description="Gestor de tareas")
subparsers = parser.add_subparsers(dest="comando")

parser_add = subparsers.add_parser("add", help="Agrega una tarea")
parser_add.add_argument("descripcion", help="Descripcion de la tarea")
parser_add.add_argument(
	"--priority",
	choices=["baja", "media", "alta"],
	default="media",
	help="Prioridad de la tarea",
)

parser_list = subparsers.add_parser("list", help="Lista tareas")
grupo_list = parser_list.add_mutually_exclusive_group()
grupo_list.add_argument("--pending", action="store_true", help="Solo pendientes")
grupo_list.add_argument("--done", action="store_true", help="Solo completadas")
parser_list.add_argument(
	"--priority",
	choices=["baja", "media", "alta"],
	help="Filtra por prioridad",
)

parser_done = subparsers.add_parser("done", help="Marca una tarea como completada")
parser_done.add_argument("id", type=int, help="ID de la tarea")

parser_remove = subparsers.add_parser("remove", help="Elimina una tarea")
parser_remove.add_argument("id", type=int, help="ID de la tarea")

try:
	args = parser.parse_args()
except SystemExit as e:
	if e.code == 0:
		raise
	sys.exit(1)

if args.comando is None:
	parser.print_help()
	sys.exit(1)

tareas = cargar_tareas()

if args.comando == "add":
	nuevo_id = 1
	if tareas:
		ids = [tarea.get("id", 0) for tarea in tareas]
		nuevo_id = max(ids) + 1

	nueva_tarea = {
		"id": nuevo_id,
		"descripcion": args.descripcion,
		"done": False,
		"priority": args.priority,
	}

	tareas.append(nueva_tarea)
	guardar_tareas(tareas)

	if args.priority == "media":
		print(f"Tarea #{nuevo_id} agregada")
	else:
		print(f"Tarea #{nuevo_id} agregada (prioridad: {args.priority})")

elif args.comando == "list":
	for tarea in tareas:
		if args.pending and tarea.get("done"):
			continue
		if args.done and not tarea.get("done"):
			continue
		if args.priority and tarea.get("priority") != args.priority:
			continue

		estado = "x" if tarea.get("done") else " "
		texto = f"#{tarea.get('id')} [{estado}] {tarea.get('descripcion', '')}"

		prioridad = tarea.get("priority", "media")
		if prioridad != "media":
			texto += f" [{prioridad.upper()}]"

		print(texto)

elif args.comando == "done":
	tarea = buscar_tarea_por_id(tareas, args.id)
	if tarea is None:
		print(f"Error: no existe la tarea #{args.id}", file=sys.stderr)
		sys.exit(1)

	tarea["done"] = True
	guardar_tareas(tareas)
	print(f"Tarea #{args.id} completada")

elif args.comando == "remove":
	tarea = buscar_tarea_por_id(tareas, args.id)
	if tarea is None:
		print(f"Error: no existe la tarea #{args.id}", file=sys.stderr)
		sys.exit(1)

	respuesta = input(f"Eliminar \"{tarea.get('descripcion', '')}\"? [s/N] ")
	if respuesta.strip().lower() != "s":
		print("Cancelado")
		sys.exit(0)

	nuevas_tareas = []
	for item in tareas:
		if item.get("id") != args.id:
			nuevas_tareas.append(item)

	guardar_tareas(nuevas_tareas)
	print(f"Tarea #{args.id} eliminada")
