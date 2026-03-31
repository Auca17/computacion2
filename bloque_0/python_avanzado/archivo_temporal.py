from contextlib import contextmanager
import os
from typing import Iterator, TextIO


@contextmanager
def archivo_temporal(nombre: str) -> Iterator[TextIO]:
	"""Crea un archivo temporal y lo borra al salir del contexto.

	Args:
		nombre: Nombre/ruta del archivo temporal.

	Yields:
		Archivo abierto en modo lectura/escritura.
	"""
	if not isinstance(nombre, str) or not nombre.strip():
		raise ValueError("nombre debe ser un string no vacío")

	archivo = open(nombre, "w+", encoding="utf-8")
	try:
		yield archivo
	finally:
		archivo.close()
		if os.path.exists(nombre):
			os.remove(nombre)


if __name__ == "__main__":
	with archivo_temporal("test.txt") as f:
		f.write("Datos de prueba\n")
		f.write("Más datos\n")
		f.seek(0)
		print(f.read())

	assert not os.path.exists("test.txt")
	print("Archivo temporal eliminado correctamente")
