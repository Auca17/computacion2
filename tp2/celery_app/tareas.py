"""Aplicación Celery con tareas equivalentes a las de la API asyncio.

Celery es solo un bonus de comparación: la plataforma obligatoria sigue
usando la cola implementada con asyncio.
"""

import asyncio
import hashlib
import os
import time

import httpx
from celery import Celery

from app.tareas import hashear_bloque

BROKER = os.environ.get("CELERY_BROKER", "redis://redis:6379/0")
CONCURRENCIA = int(os.environ.get("CELERY_CONCURRENCIA", "4"))

app = Celery("tareas", broker=BROKER, backend=BROKER)
app.conf.update(
    worker_concurrency=CONCURRENCIA,
    # Cada proceso toma una sola tarea por vez: reparto parejo, como la
    # cola compartida de nuestros N workers.
    worker_prefetch_multiplier=1,
    # El mensaje se confirma al terminar: si el proceso muere, se reentrega.
    task_acks_late=True,
    task_track_started=True,
    result_expires=3600,
)


@app.task
def esperar(segundos: float) -> dict:
    """Espera `segundos`.

    Acá time.sleep es correcto: un worker de Celery es un proceso común (no
    hay event loop que bloquear) y dormir solo ocupa a ese proceso.
    """
    time.sleep(segundos)
    return {"esperado": segundos}


@app.task
def hashear(texto: str, iteraciones: int) -> str:
    """SHA-256 iterado; mismo resultado que la tarea `hashear` de la API."""
    digest = hashear_bloque(
        hashlib.sha256(texto.encode()).digest(), iteraciones - 1)
    return digest.hex()


async def _descargar_url(cliente: httpx.AsyncClient, url: str) -> dict:
    inicio = time.perf_counter()
    try:
        r = await cliente.get(url)
        return {"url": url, "estado_http": r.status_code,
                "bytes": len(r.content),
                "segundos": round(time.perf_counter() - inicio, 4)}
    except Exception as exc:
        return {"url": url, "error": f"{type(exc).__name__}: {exc}",
                "segundos": round(time.perf_counter() - inicio, 4)}


async def _descargar_todas(urls: list[str]) -> list[dict]:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as c:
        return await asyncio.gather(*(_descargar_url(c, u) for u in urls))


@app.task
def descargar(urls: list[str]) -> list[dict]:
    """Descarga las URLs concurrentemente.

    Se usa `asyncio.run` con `gather` (en vez de un cliente síncrono
    secuencial) para que una tarea de 20 URLs sea comparable con la nuestra:
    la concurrencia de I/O vive dentro de la tarea; Celery solo reparte
    tareas entre procesos.
    """
    return asyncio.run(_descargar_todas(urls))
