import argparse
import os
import sys

parser = argparse.ArgumentParser(description="Lista archivos y directorios")
parser.add_argument("directorio", nargs="?", default=".", help="Directorio a listar")
parser.add_argument("-a", "--all", action="store_true", help="Incluye ocultos")
parser.add_argument("--extension", help="Filtra por extension, por ejemplo .py")

try:
    args = parser.parse_args()
except SystemExit as e:
    if e.code == 0:
        raise
    sys.exit(1)
directorio = args.directorio

if not os.path.exists(directorio):
    print(f"Error: no existe el directorio '{directorio}'")
    sys.exit(1)

if not os.path.isdir(directorio):
    print(f"Error: '{directorio}' no es un directorio")
    sys.exit(1)

extension = args.extension
if extension and not extension.startswith("."):
    extension = "." + extension

try:
    entradas = sorted(os.listdir(directorio))
except OSError:
    print(f"Error: no se puede leer '{directorio}'")
    sys.exit(1)

for nombre in entradas:
    if not args.all and nombre.startswith("."):
        continue

    ruta = os.path.join(directorio, nombre)

    if extension:
        if os.path.isdir(ruta):
            continue
        if not nombre.endswith(extension):
            continue

    if os.path.isdir(ruta):
        print(nombre + "/")
    else:
        print(nombre)
