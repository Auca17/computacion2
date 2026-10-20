"""Implementación de los tres tipos de tarea."""

import asyncio
import hashlib
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Optional

import httpx

from . import config

ITERACIONES_POR_BLOQUE = 200_000


def hashear_bloque(digest: bytes, iteraciones: int) -> bytes:
    """Aplica SHA-256 `iteraciones` veces sobre `digest` (función CPU-bound).

    Es de nivel módulo para que pueda enviarse a otro proceso (picklable).
    """
    for _ in range(iteraciones):
        digest = hashlib.sha256(digest).digest()
    return digest


async def esperar(parametros: dict, executor: Optional[ProcessPoolExecutor]):
    """Duerme sin bloquear el event loop."""
    segundos = parametros["segundos"]
    await asyncio.sleep(segundos)
    return {"esperado": segundos}


async def _descargar_url(cliente: httpx.AsyncClient, url: str) -> dict:
    """Descarga una URL; un fallo se informa como entrada de error."""
    inicio = time.perf_counter()
    try:
        respuesta = await cliente.get(url)
        return {
            "url": url,
            "estado_http": respuesta.status_code,
            "bytes": len(respuesta.content),
            "segundos": round(time.perf_counter() - inicio, 4),
        }
    except Exception as exc:
        return {
            "url": url,
            "error": f"{type(exc).__name__}: {exc}",
            "segundos": round(time.perf_counter() - inicio, 4),
        }


async def descargar(parametros: dict, executor: Optional[ProcessPoolExecutor]):
    """Descarga todas las URLs concurrentemente."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as cliente:
        return await asyncio.gather(
            *(_descargar_url(cliente, url) for url in parametros["urls"])
        )


async def hashear(parametros: dict, executor: Optional[ProcessPoolExecutor]):
    """SHA-256 iterado, en bloques dentro de un ProcessPoolExecutor.

    Entre bloque y bloque se hace `await`: el event loop sigue libre y la
    cancelación puede entrar entre bloques.
    """
    digest = hashlib.sha256(parametros["texto"].encode()).digest()
    restantes = parametros["iteraciones"] - 1

    if config.MODO_CPU == "bloqueante":
        # Intencionalmente bloquea el event loop (solo para la medición).
        return hashear_bloque(digest, restantes).hex()

    loop = asyncio.get_running_loop()
    while restantes > 0:
        bloque = min(ITERACIONES_POR_BLOQUE, restantes)
        digest = await loop.run_in_executor(
            executor, hashear_bloque, digest, bloque
        )
        restantes -= bloque
    return digest.hex()


EJECUTORES = {"descargar": descargar, "hashear": hashear, "esperar": esperar}
