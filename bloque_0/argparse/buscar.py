import argparse
import sys

parser = argparse.ArgumentParser(description="Busca un patron en archivos o stdin")
parser.add_argument("patron", help="Patron a buscar")
parser.add_argument("archivos", nargs="*", help="Archivos donde buscar")
parser.add_argument("-i", "--ignore-case", action="store_true", help="Ignora mayusculas/minusculas")
parser.add_argument("-n", "--line-number", action="store_true", help="Muestra numero de linea")
parser.add_argument("-c", "--count", action="store_true", help="Solo muestra cantidad")
parser.add_argument("-v", "--invert", action="store_true", help="Muestra lineas que no coinciden")

try:
	args = parser.parse_args()
except SystemExit as e:
	if e.code == 0:
		raise
	sys.exit(1)

patron = args.patron
if args.ignore_case:
	patron = patron.lower()

hay_error = False

if args.archivos:
	total = 0

	for archivo in args.archivos:
		try:
			f = open(archivo, "r", encoding="utf-8")
		except OSError:
			print(f"Error: no se puede leer '{archivo}'", file=sys.stderr)
			hay_error = True
			continue

		numero = 0
		coincidencias = 0

		for linea in f:
			numero += 1
			texto = linea.rstrip("\n")

			base = texto
			if args.ignore_case:
				base = base.lower()

			coincide = patron in base
			if args.invert:
				coincide = not coincide

			if coincide:
				coincidencias += 1
				if not args.count:
					print(f"{archivo}:{numero}: {texto}")

		f.close()

		if args.count:
			print(f"{archivo}: {coincidencias} coincidencias")

		total += coincidencias

	if args.count and len(args.archivos) > 1:
		print(f"Total: {total} coincidencias")

else:
	if sys.stdin.isatty():
		print("Error: debe indicar archivos o pasar datos por stdin", file=sys.stderr)
		sys.exit(1)

	numero = 0
	coincidencias = 0

	for linea in sys.stdin:
		numero += 1
		texto = linea.rstrip("\n")

		base = texto
		if args.ignore_case:
			base = base.lower()

		coincide = patron in base
		if args.invert:
			coincide = not coincide

		if coincide:
			coincidencias += 1
			if not args.count:
				if args.line_number:
					print(f"{numero}: {texto}")
				else:
					print(texto)

	if args.count:
		print(f"Total: {coincidencias} coincidencias")

if hay_error:
	sys.exit(1)
