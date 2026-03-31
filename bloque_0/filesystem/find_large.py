import argparse
import os
import sys


def parse_size(value):
	text = value.strip().upper()
	if not text:
		raise argparse.ArgumentTypeError("--min-size no puede estar vacío")

	multipliers = {
		"K": 1024,
		"M": 1024 * 1024,
		"G": 1024 * 1024 * 1024,
	}

	suffix = text[-1]
	if suffix in multipliers:
		number_text = text[:-1]
		if not number_text.isdigit():
			raise argparse.ArgumentTypeError("Formato inválido. Usa por ejemplo: 100K, 1M, 2G")
		return int(number_text) * multipliers[suffix]

	if text.isdigit():
		return int(text)

	raise argparse.ArgumentTypeError("Formato inválido. Usa bytes o sufijos K/M/G")


def human_size(size):
	if size >= 1024 * 1024 * 1024:
		return f"{size / (1024 * 1024 * 1024):.1f} GB"
	if size >= 1024 * 1024:
		return f"{size / (1024 * 1024):.1f} MB"
	if size >= 1024:
		return f"{size / 1024:.1f} KB"
	return f"{size} B"


parser = argparse.ArgumentParser(description="Busca archivos o directorios grandes de forma recursiva")
parser.add_argument("directorio", help="Directorio donde buscar")
parser.add_argument("--min-size", type=parse_size, default=0, help="Tamaño mínimo (ej: 100K, 1M, 2G)")
parser.add_argument("--type", choices=["f", "d"], default="f", help="f=archivo, d=directorio")
parser.add_argument("--top", type=int, help="Muestra solo los N más grandes")

try:
	args = parser.parse_args()
except SystemExit as e:
	if e.code == 0:
		raise
	sys.exit(1)

if args.top is not None and args.top <= 0:
	print("Error: --top debe ser mayor a 0", file=sys.stderr)
	sys.exit(1)

if not os.path.exists(args.directorio):
	print(f"Error: no existe '{args.directorio}'", file=sys.stderr)
	sys.exit(1)

if not os.path.isdir(args.directorio):
	print(f"Error: '{args.directorio}' no es un directorio", file=sys.stderr)
	sys.exit(1)

resultados = []

for root, dirs, files in os.walk(args.directorio):
	if args.type == "f":
		for filename in files:
			path = os.path.join(root, filename)
			try:
				size = os.path.getsize(path)
			except OSError:
				continue

			if size >= args.min_size:
				resultados.append((path, size))
	else:
		for dirname in dirs:
			path = os.path.join(root, dirname)
			try:
				size = os.path.getsize(path)
			except OSError:
				continue

			if size >= args.min_size:
				resultados.append((path, size))

resultados.sort(key=lambda item: item[1], reverse=True)

if args.top is not None:
	resultados = resultados[: args.top]
	print(f"Los {args.top} archivos más grandes:")

for index, (path, size) in enumerate(resultados, start=1):
	if args.top is not None:
		print(f"  {index}. {path} ({human_size(size)})")
	else:
		print(f"{path} ({human_size(size)})")

total_size = sum(size for _, size in resultados)
etiqueta = "archivos" if args.type == "f" else "directorios"
print(f"Total: {len(resultados)} {etiqueta}, {human_size(total_size)}")
