import argparse
import datetime
import os
import stat
import sys

try:
	import pwd
except ImportError:
	pwd = None

try:
	import grp
except ImportError:
	grp = None


def formatear_fecha(timestamp):
	return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def formatear_tamano(bytes_size):
	kb = bytes_size / 1024
	return f"{bytes_size} bytes ({kb:.2f} KB)"


def tipo_archivo(modo):
	if stat.S_ISREG(modo):
		return "archivo regular"
	if stat.S_ISDIR(modo):
		return "directorio"
	if stat.S_ISLNK(modo):
		return "enlace simbólico"
	if stat.S_ISCHR(modo):
		return "dispositivo de caracteres"
	if stat.S_ISBLK(modo):
		return "dispositivo de bloques"
	if stat.S_ISFIFO(modo):
		return "pipe/FIFO"
	if stat.S_ISSOCK(modo):
		return "socket"
	return "tipo desconocido"


def nombre_usuario(uid):
	if pwd is None:
		return str(uid)
	try:
		return pwd.getpwuid(uid).pw_name
	except KeyError:
		return str(uid)


def nombre_grupo(gid):
	if grp is None:
		return str(gid)
	try:
		return grp.getgrgid(gid).gr_name
	except KeyError:
		return str(gid)


parser = argparse.ArgumentParser(description="Muestra información detallada de un archivo")
parser.add_argument("ruta", help="Ruta del archivo o directorio a inspeccionar")

try:
	args = parser.parse_args()
except SystemExit as e:
	if e.code == 0:
		raise
	sys.exit(1)

ruta = args.ruta

if not os.path.lexists(ruta):
	print(f"Error: no existe '{ruta}'", file=sys.stderr)
	sys.exit(1)

try:
	info = os.lstat(ruta)
except OSError:
	print(f"Error: no se puede leer metadata de '{ruta}'", file=sys.stderr)
	sys.exit(1)

tipo = tipo_archivo(info.st_mode)

if stat.S_ISLNK(info.st_mode):
	try:
		destino = os.readlink(ruta)
		tipo = f"{tipo} -> {destino}"
	except OSError:
		tipo = f"{tipo} (destino no disponible)"

permisos_legibles = stat.filemode(info.st_mode)[1:]
permisos_octal = oct(info.st_mode & 0o777)[2:]

usuario = nombre_usuario(info.st_uid)
grupo = nombre_grupo(info.st_gid)

print(f"Archivo: {ruta}")
print(f"Tipo: {tipo}")
print(f"Tamaño: {formatear_tamano(info.st_size)}")
print(f"Permisos: {permisos_legibles} ({permisos_octal})")
print(f"Propietario: {usuario} (uid: {info.st_uid})")
print(f"Grupo: {grupo} (gid: {info.st_gid})")
print(f"Inodo: {info.st_ino}")
print(f"Enlaces duros: {info.st_nlink}")
print(f"Creación: {formatear_fecha(info.st_ctime)}")
print(f"Última modificación: {formatear_fecha(info.st_mtime)}")
print(f"Último acceso: {formatear_fecha(info.st_atime)}")

if stat.S_ISDIR(info.st_mode):
	try:
		cantidad = len(os.listdir(ruta))
		print(f"Contenido: {cantidad} elementos")
	except OSError:
		print("Contenido: no se pudo listar (permisos insuficientes)")
