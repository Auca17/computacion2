"""Limitación de tasa por cliente con cubeta de tokens."""

import time

from . import config


class LimitadorTasa:
    """Cubeta de tokens por clave: se recarga `RATE_LIMIT_POR_SEG` por segundo.

    La cubeta guarda hasta `RATE_LIMIT_RAFAGA` tokens. No usa locks: todo
    corre en un único hilo (el event loop) y `consumir` no tiene `await`,
    así que ninguna otra corrutina puede intercalarse a mitad de la cuenta.
    """

    def __init__(self) -> None:
        # ip -> (tokens disponibles, instante de la última actualización)
        self._cubetas: dict[str, tuple[float, float]] = {}

    def reiniciar(self) -> None:
        """Olvida todas las cubetas."""
        self._cubetas.clear()

    def consumir(self, clave: str) -> float:
        """Gasta un token; devuelve 0 si pudo o los segundos de espera si no."""
        ahora = time.monotonic()
        tokens, ultimo = self._cubetas.get(clave, (config.RATE_LIMIT_RAFAGA, ahora))
        tokens = min(config.RATE_LIMIT_RAFAGA,
                     tokens + (ahora - ultimo) * config.RATE_LIMIT_POR_SEG)
        if tokens >= 1:
            self._cubetas[clave] = (tokens - 1, ahora)
            return 0.0
        self._cubetas[clave] = (tokens, ahora)
        return (1 - tokens) / config.RATE_LIMIT_POR_SEG


limitador = LimitadorTasa()
