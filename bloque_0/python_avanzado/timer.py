import time
from contextlib import contextmanager
from typing import Iterator, Optional


class Timer:
	"""Context manager de tiempo con acceso a elapsed en vivo y final."""

	def __init__(self, nombre: Optional[str] = None) -> None:
		"""Inicializa el timer con nombre opcional para imprimir al salir."""
		self.nombre = nombre
		self._start = None
		self._end = None

	def __enter__(self) -> "Timer":
		"""Comienza la medición y devuelve el timer."""
		self._start = time.perf_counter()
		self._end = None
		return self

	def __exit__(self, exc_type, exc_value, traceback) -> None:
		"""Finaliza la medición e imprime si hay nombre."""
		self._end = time.perf_counter()
		if self.nombre:
			print(f"[Timer] {self.nombre}: {self.elapsed:.3f}s")

	@property
	def elapsed(self) -> float:
		"""Tiempo transcurrido en segundos."""
		if self._start is None:
			return 0.0

		if self._end is None:
			return time.perf_counter() - self._start

		return self._end - self._start


class _TimerEstado:
	"""Estado interno para el timer implementado con @contextmanager."""

	def __init__(self) -> None:
		self._start = None
		self._end = None

	@property
	def elapsed(self) -> float:
		"""Tiempo transcurrido en segundos."""
		if self._start is None:
			return 0.0

		if self._end is None:
			return time.perf_counter() - self._start

		return self._end - self._start


@contextmanager
def timer_context(nombre: Optional[str] = None) -> Iterator[_TimerEstado]:
	"""Versión de timer con @contextmanager."""
	estado = _TimerEstado()
	estado._start = time.perf_counter()

	try:
		yield estado
	finally:
		estado._end = time.perf_counter()
		if nombre:
			print(f"[Timer] {nombre}: {estado.elapsed:.3f}s")


if __name__ == "__main__":
	with Timer("Procesamiento de datos"):
		datos = [x**2 for x in range(100000)]

	with Timer() as t:
		time.sleep(0.2)
	print(f"El bloque tardó {t.elapsed:.3f} segundos")

	with Timer() as t:
		time.sleep(0.1)
		print(f"Después del paso 1: {t.elapsed:.3f}s")
		time.sleep(0.1)
		print(f"Después del paso 2: {t.elapsed:.3f}s")

	with timer_context("Contextmanager con decorador") as t2:
		time.sleep(0.15)
	print(f"Medido con timer_context: {t2.elapsed:.3f} segundos")
