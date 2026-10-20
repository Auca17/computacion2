"""Implementación de los tres tipos de tarea."""

import asyncio
import contextlib
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


async def _en_paralelo(funcion, elementos: list) -> list:
    """Corre `funcion(elemento)` para cada elemento, concurrentemente.

    TaskGroup da concurrencia estructurada: todas las hijas terminan antes de
    salir del bloque y, si se cancela la tarea, se cancelan juntas. El
    Semaphore limita las conexiones simultáneas a MAX_CONEXIONES. El
    resultado conserva el orden de `elementos`.
    """
    limite = asyncio.Semaphore(config.MAX_CONEXIONES)

    async def limitada(elemento):
        async with limite:
            return await funcion(elemento)

    async with asyncio.TaskGroup() as grupo:
        hijas = [grupo.create_task(limitada(e)) for e in elementos]
    return [hija.result() for hija in hijas]


async def descargar(parametros: dict, executor: Optional[ProcessPoolExecutor]):
    """Descarga todas las URLs concurrentemente (máx. MAX_CONEXIONES a la vez).

    `_descargar_url` captura sus propios errores, así que ninguna hija hace
    fallar al TaskGroup. Al cancelar, `async with` cierra las conexiones.
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as cliente:
        return await _en_paralelo(
            lambda url: _descargar_url(cliente, url), parametros["urls"])


async def _sondear_puerto(host: str, puerto: int, timeout: float) -> dict:
    """Intenta conectar a un puerto TCP; informa abierto/cerrado y latencia."""
    inicio = time.perf_counter()
    try:
        _, escritor = await asyncio.wait_for(
            asyncio.open_connection(host, puerto), timeout)
    except TimeoutError:  # antes que OSError, de la que es subclase
        return {"puerto": puerto, "abierto": False,
                "motivo": f"timeout: sin respuesta en {timeout} s"}
    except OSError as exc:
        return {"puerto": puerto, "abierto": False,
                "motivo": f"{type(exc).__name__}: {exc}"}
    ms = round((time.perf_counter() - inicio) * 1000, 2)
    escritor.close()
    with contextlib.suppress(OSError):
        await escritor.wait_closed()
    return {"puerto": puerto, "abierto": True, "ms": ms}


async def sondear(parametros: dict, executor: Optional[ProcessPoolExecutor]):
    """Chequea concurrentemente qué puertos TCP de un host están abiertos."""
    return await _en_paralelo(
        lambda puerto: _sondear_puerto(
            parametros["host"], puerto, parametros["timeout_conexion"]),
        parametros["puertos"])


async def hashear(parametros: dict, executor: Optional[ProcessPoolExecutor]):
    """SHA-256 iterado, en bloques dentro de un ProcessPoolExecutor.

    Entre bloque y bloque se hace `await`: el event loop sigue libre y la
    cancelación puede entrar entre bloques. Al cancelar, el bloque que ya está
    en el proceso termina por su cuenta (a lo sumo un bloque de trabajo
    desperdiciado) y su resultado se descarta; no se encolan más.
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


EJECUTORES = {"descargar": descargar, "hashear": hashear, "esperar": esperar,
              "sondear": sondear}
