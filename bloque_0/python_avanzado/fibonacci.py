from typing import Iterator, Optional


def fibonacci(limite: Optional[int] = None) -> Iterator[int]:
	"""Genera números de Fibonacci.

	Si limite es None, la secuencia es infinita.
	Si limite es un entero, genera valores menores a limite.
	"""
	if limite is not None:
		if not isinstance(limite, int):
			raise TypeError("limite debe ser int o None")
		if limite < 0:
			raise ValueError("limite no puede ser negativo")

	a = 0
	b = 1

	while True:
		if limite is not None and a >= limite:
			break

		yield a
		a, b = b, a + b


if __name__ == "__main__":
	"""Ejemplos de uso del generador Fibonacci."""
	fib = fibonacci()

	print("Primeros 10 números:")
	for _ in range(10):
		print(next(fib))

	print("Siguientes dos:")
	print(next(fib))
	print(next(fib))

	print("Con límite 100:")
	for n in fibonacci(limite=100):
		print(n)

	print("Con límite 0 (caso borde):")
	print(list(fibonacci(limite=0)))
