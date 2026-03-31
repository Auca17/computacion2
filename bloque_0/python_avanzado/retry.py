import random
import time
from functools import wraps
from typing import Any, Callable, Tuple, Type, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def retry(
	max_attempts: int = 3,
	delay: float = 1,
	exceptions: Tuple[Type[BaseException], ...] = (Exception,),
) -> Callable[[F], F]:
	"""Decorador para reintentar una función cuando falla con ciertas excepciones."""

	if max_attempts <= 0:
		raise ValueError("max_attempts debe ser mayor a 0")
	if delay < 0:
		raise ValueError("delay no puede ser negativo")
	if not exceptions:
		raise ValueError("exceptions no puede ser vacío")

	def decorator(func: F) -> F:
		@wraps(func)
		def wrapper(*args: Any, **kwargs: Any) -> Any:
			ultimo_error = None

			for intento in range(1, max_attempts + 1):
				try:
					return func(*args, **kwargs)
				except exceptions as error:
					ultimo_error = error

					if intento < max_attempts:
						print(
							f"Intento {intento}/{max_attempts} falló: {error}. "
							f"Esperando {delay}s..."
						)
						time.sleep(delay)
					else:
						print(f"Intento {intento}/{max_attempts} falló: {error}.")

			raise ultimo_error  # type: ignore[misc]

		return wrapper  # type: ignore[return-value]

	return decorator


@retry(max_attempts=3, delay=1)
def conectar_servidor():
	"""Simula una conexión inestable a servidor."""
	if random.random() < 0.7:
		raise ConnectionError("Servidor no disponible")
	return "Conectado exitosamente"


if __name__ == "__main__":
	try:
		resultado = conectar_servidor()
		print(resultado)
	except ConnectionError:
		print("Falló después de 3 intentos")
