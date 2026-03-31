import argparse
import json
import sys

parser = argparse.ArgumentParser(description="Procesa archivos JSON")
parser.add_argument("archivo", help="Archivo JSON o - para stdin")

grupo = parser.add_mutually_exclusive_group(required=True)
grupo.add_argument("--keys", action="store_true", help="Lista claves del primer nivel")
grupo.add_argument("--get", metavar="KEY", help="Obtiene un valor por ruta con puntos")
grupo.add_argument("--pretty", action="store_true", help="Imprime JSON formateado")
grupo.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), help="Modifica un valor")

parser.add_argument("-o", "--output", default="-", help="Archivo de salida (default: stdout)")

try:
	args = parser.parse_args()
except SystemExit as e:
	if e.code == 0:
		raise
	sys.exit(1)


def parsear_valor(texto):
	try:
		return json.loads(texto)
	except json.JSONDecodeError:
		return texto


def obtener_ruta(data, ruta):
	actual = data
	partes = ruta.split(".")

	for parte in partes:
		if isinstance(actual, list):
			try:
				indice = int(parte)
			except ValueError:
				raise ValueError(f"Indice invalido: {parte}")

			if indice < 0 or indice >= len(actual):
				raise ValueError(f"Indice fuera de rango: {indice}")

			actual = actual[indice]

		elif isinstance(actual, dict):
			if parte not in actual:
				raise ValueError(f"Clave inexistente: {parte}")
			actual = actual[parte]

		else:
			raise ValueError("La ruta no se puede seguir")

	return actual


def asignar_ruta(data, ruta, valor):
	partes = ruta.split(".")
	actual = data

	for parte in partes[:-1]:
		if isinstance(actual, list):
			try:
				indice = int(parte)
			except ValueError:
				raise ValueError(f"Indice invalido: {parte}")

			if indice < 0 or indice >= len(actual):
				raise ValueError(f"Indice fuera de rango: {indice}")

			actual = actual[indice]

		elif isinstance(actual, dict):
			if parte not in actual:
				raise ValueError(f"Clave inexistente: {parte}")
			actual = actual[parte]

		else:
			raise ValueError("La ruta no se puede seguir")

	ultima = partes[-1]

	if isinstance(actual, list):
		try:
			indice = int(ultima)
		except ValueError:
			raise ValueError(f"Indice invalido: {ultima}")

		if indice < 0 or indice >= len(actual):
			raise ValueError(f"Indice fuera de rango: {indice}")

		actual[indice] = valor

	elif isinstance(actual, dict):
		actual[ultima] = valor

	else:
		raise ValueError("No se puede asignar en esa ruta")


try:
	if args.archivo == "-":
		data = json.load(sys.stdin)
	else:
		with open(args.archivo, "r", encoding="utf-8") as f:
			data = json.load(f)
except OSError:
	print(f"Error: no se puede leer '{args.archivo}'", file=sys.stderr)
	sys.exit(1)
except UnicodeDecodeError:
	print("Error: no se puede decodificar el archivo como UTF-8", file=sys.stderr)
	sys.exit(1)
except json.JSONDecodeError:
	print("Error: JSON invalido", file=sys.stderr)
	sys.exit(1)

salida = ""

try:
	if args.keys:
		if not isinstance(data, dict):
			print("Error: el JSON no es un objeto en el primer nivel", file=sys.stderr)
			sys.exit(1)
		salida = "\n".join(data.keys())

	elif args.get:
		valor = obtener_ruta(data, args.get)
		salida = json.dumps(valor, ensure_ascii=False)

	elif args.pretty:
		salida = json.dumps(data, indent=4, ensure_ascii=False)

	elif args.set:
		ruta = args.set[0]
		valor_texto = args.set[1]
		valor = parsear_valor(valor_texto)
		asignar_ruta(data, ruta, valor)
		salida = json.dumps(data, ensure_ascii=False)

except ValueError as e:
	print(f"Error: {e}", file=sys.stderr)
	sys.exit(1)

if args.output == "-":
	print(salida)
else:
	try:
		with open(args.output, "w", encoding="utf-8") as f:
			f.write(salida)
			f.write("\n")
	except OSError:
		print(f"Error: no se puede escribir '{args.output}'", file=sys.stderr)
		sys.exit(1)

	if args.set:
		print(f"Guardado en {args.output}")
