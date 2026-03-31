from datetime import datetime
from functools import wraps
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def log_llamada(func: F) -> F:
	"""Decorador que registra llamadas y retornos de una función."""

	@wraps(func)
	def wrapper(*args: Any, **kwargs: Any) -> Any:
		marca = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

		argumentos = [repr(arg) for arg in args]
		argumentos.extend(f"{clave}={repr(valor)}" for clave, valor in kwargs.items())
		argumentos_texto = ", ".join(argumentos)

		print(f"[{marca}] Llamando a {func.__name__}({argumentos_texto})")
		resultado = func(*args, **kwargs)

		marca = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print(f"[{marca}] {func.__name__} retornó {repr(resultado)}")

		return resultado

	return wrapper  # type: ignore[return-value]


@log_llamada
def sumar(a, b):
	"""Suma dos números y devuelve el resultado."""
	if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
		raise TypeError("sumar espera números")
	return a + b


@log_llamada
def saludar(nombre, entusiasta=False):
	"""Devuelve un saludo para el nombre indicado."""
	if not isinstance(nombre, str) or not nombre:
		raise ValueError("nombre debe ser string no vacío")
	sufijo = "!" if entusiasta else "."
	return f"Hola, {nombre}{sufijo}"


if __name__ == "__main__":
	resultado = sumar(3, 5)
	print(f"Resultado final: {resultado}")

	saludo = saludar("Ana", entusiasta=True)
	print(f"Saludo final: {saludo}")
