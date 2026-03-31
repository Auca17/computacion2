from typing import Iterable, Iterator, List, TypeVar

T = TypeVar("T")


def chunked(iterable: Iterable[T], size: int) -> Iterator[List[T]]:
	"""Divide un iterable en bloques (chunks) de tamaño fijo.

	Args:
		iterable: Colección o iterable de entrada.
		size: Tamaño de cada bloque (debe ser > 0).

	Yields:
		Listas con hasta `size` elementos.
	"""
	if size <= 0:
		raise ValueError("size debe ser mayor a 0")

	buffer: List[T] = []
	for item in iterable:
		buffer.append(item)
		if len(buffer) == size:
			yield buffer
			buffer = []

	if buffer:
		yield buffer


if __name__ == "__main__":
	print("Lista normal:")
	for bloque in chunked([1, 2, 3, 4, 5], 2):
		print(bloque)

	print("Lista vacía (caso borde):")
	print(list(chunked([], 3)))

	try:
		list(chunked([1, 2, 3], 0))
	except ValueError as e:
		print(f"Error controlado: {e}")
