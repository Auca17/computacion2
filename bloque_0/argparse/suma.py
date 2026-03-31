import argparse
import sys

parser = argparse.ArgumentParser(description="Suma numeros pasados por linea de comandos.")
parser.add_argument("numeros", nargs="*", help="Numeros a sumar")
try:
	args = parser.parse_args()
except SystemExit as e:
	if e.code == 0:
		raise
	sys.exit(1)

total = 0.0
hay_decimal = False

for valor in args.numeros:
	try:
		if any(c in valor for c in ".eE"):
			hay_decimal = True
		total += float(valor)
	except ValueError:
		print(f"Valor invalido: {valor}")
		print("Uso: suma.py <numero1> <numero2> ...")
		sys.exit(1)

if not hay_decimal and total.is_integer():
	print(f"Suma: {int(total)}")
else:
	print(f"Suma: {total}")
