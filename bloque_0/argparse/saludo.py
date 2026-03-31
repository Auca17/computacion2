import argparse
import sys

parser = argparse.ArgumentParser(description="Saluda al nombre indicado.")
parser.add_argument("nombre", nargs="*", help="Nombre a saludar")
try:
    args = parser.parse_args()
except SystemExit as e:
    if e.code == 0:
        raise
    sys.exit(1)

if not args.nombre:
    print("Uso: saludo.py <nombre>")
    sys.exit(1)

nombre = " ".join(args.nombre)
print(f"Hola, {nombre}!")

