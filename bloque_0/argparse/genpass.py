import argparse
import secrets
import string
import sys

parser = argparse.ArgumentParser(description="Generador de contraseñas")
parser.add_argument("-n", "--length", type=int, default=12, help="Longitud de la contraseña")
parser.add_argument("--no-symbols", action="store_true", help="Excluir símbolos")
parser.add_argument("--no-numbers", action="store_true", help="Excluir números")
parser.add_argument("--count", type=int, default=1, help="Cantidad de contraseñas")

try:
	args = parser.parse_args()
except SystemExit as e:
	if e.code == 0:
		raise
	sys.exit(1)

if args.length <= 0:
	parser.error("--length debe ser mayor a 0")

if args.count <= 0:
	parser.error("--count debe ser mayor a 0")

caracteres = string.ascii_letters

if not args.no_numbers:
	caracteres += string.digits

if not args.no_symbols:
	caracteres += "!@#$%&"

for _ in range(args.count):
	password = ""
	for _ in range(args.length):
		password += secrets.choice(caracteres)
	print(password)
