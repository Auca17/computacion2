import argparse
import os
import sys


parser = argparse.ArgumentParser(description="Busca enlaces simbólicos rotos de forma recursiva")
parser.add_argument("directorio", help="Directorio donde buscar")
parser.add_argument("--delete", action="store_true", help="Ofrece borrar enlaces rotos")
parser.add_argument("--quiet", action="store_true", help="Solo muestra el conteo")

try:
	args = parser.parse_args()
except SystemExit as e:
	if e.code == 0:
		raise
	sys.exit(1)

if not os.path.exists(args.directorio):
	print(f"Error: no existe '{args.directorio}'", file=sys.stderr)
	sys.exit(1)

if not os.path.isdir(args.directorio):
	print(f"Error: '{args.directorio}' no es un directorio", file=sys.stderr)
	sys.exit(1)

rotos = []

for root, dirs, files in os.walk(args.directorio):
	nombres = dirs + files

	for nombre in nombres:
		path = os.path.join(root, nombre)

		try:
			es_link = os.path.islink(path)
		except OSError:
			continue

		if not es_link:
			continue

		try:
			existe_destino = os.path.exists(path)
		except OSError:
			existe_destino = False

		if existe_destino:
			continue

		try:
			destino = os.readlink(path)
		except OSError:
			destino = "(destino no disponible)"

		rotos.append((path, destino))

if args.quiet:
	print(len(rotos))
	sys.exit(0)

print(f"Buscando enlaces simbólicos rotos en {args.directorio}...")
print()

if not rotos:
	print("No se encontraron enlaces rotos")
	print()
	print("Total: 0 enlaces rotos")
	sys.exit(0)

print("Enlaces rotos encontrados:")
for path, destino in rotos:
	print(f"  {path} -> {destino} (no existe)")

print()
print(f"Total: {len(rotos)} enlaces rotos")

if args.delete:
	print()
	for path, _ in rotos:
		respuesta = input(f"¿Eliminar {path}? [s/N] ")
		if respuesta.strip().lower() != "s":
			continue

		try:
			os.unlink(path)
			print("  Eliminado")
		except OSError:
			print("  Error: no se pudo eliminar", file=sys.stderr)
