"""Compara la API asyncio con el pool equivalente en Celery + Redis.

Corre dentro de un contenedor (ve `api`, `lento` y `redis` por nombre):

    docker compose --profile celery up --build -d
    docker compose --profile celery run --rm --no-deps \
        -e PYTHONPATH=/srv -v ./scripts:/srv/scripts celery_worker \n        python scripts/comparar_celery.py --salida /srv/scripts/resultados_celery.md

Ambos sistemas tienen paralelismo 4 (WORKERS=4 vs --concurrency=4).
"""

import argparse
import asyncio
import hashlib
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comun import crear_tarea, esperar_fin, tabla  # noqa: E402

from app.tareas import hashear_bloque  # noqa: E402
from celery_app.tareas import app, descargar, esperar, hashear  # noqa: E402

API = os.environ.get("API_URL", "http://api:8000")
LENTO = os.environ.get("LENTO_URL", "http://lento:8001")
FINALES = ("completada", "fallida", "cancelada")


def segundos(valor: float) -> str:
    return f"{valor:.2f}"


def calibrar_iteraciones() -> int:
    """Iteraciones de SHA-256 que tardan ~1 s en esta máquina."""
    inicio = time.perf_counter()
    hashear_bloque(hashlib.sha256(b"x").digest(), 200_000)
    por_seg = 200_000 / (time.perf_counter() - inicio)
    return int(round(por_seg, -4))


async def lote_api(cliente, tipo, parametros, cantidad) -> float:
    inicio = time.perf_counter()
    ids = await asyncio.gather(
        *(crear_tarea(cliente, tipo, parametros) for _ in range(cantidad)))
    await asyncio.gather(*(esperar_fin(cliente, i) for i in ids))
    return time.perf_counter() - inicio


def lote_celery(tarea, argumentos: list[tuple]) -> float:
    inicio = time.perf_counter()
    resultados = [tarea.apply_async(a) for a in argumentos]
    for r in resultados:
        r.get(timeout=300)
    return time.perf_counter() - inicio


async def comparar_esperar(cliente) -> str:
    t_api = await lote_api(cliente, "esperar", {"segundos": 1}, 20)
    t_cel = await asyncio.to_thread(lote_celery, esperar, [(1,)] * 20)
    return tabla(["Sistema", "Total 20 x esperar(1 s) [s]"],
                 [["API asyncio (4 workers)", segundos(t_api)],
                  ["Celery (concurrency 4)", segundos(t_cel)]])


async def comparar_hashear(cliente, iteraciones: int) -> str:
    texto = "comparacion"
    t_api = await lote_api(
        cliente, "hashear", {"texto": texto, "iteraciones": iteraciones}, 8)
    t_cel = await asyncio.to_thread(
        lote_celery, hashear, [(texto, iteraciones)] * 8)
    return (f"{iteraciones:,} iteraciones por tarea (~1 s)\n\n" + tabla(
        ["Sistema", "Total 8 x hashear [s]"],
        [["API asyncio (4 workers + ProcessPool)", segundos(t_api)],
         ["Celery (concurrency 4, prefork)", segundos(t_cel)]]))


async def comparar_descargas(cliente) -> str:
    urls = [f"{LENTO}/demora?ms=500"] * 20
    t_api = await lote_api(cliente, "descargar", {"urls": urls}, 1)
    t_cel20 = await asyncio.to_thread(
        lote_celery, descargar, [([u],) for u in urls])
    t_cel1 = await asyncio.to_thread(lote_celery, descargar, [(urls,)])
    return tabla(
        ["Sistema", "Total 20 descargas de 500 ms [s]"],
        [["API: 1 tarea con 20 URLs (gather)", segundos(t_api)],
         ["Celery: 20 tareas de 1 URL", segundos(t_cel20)],
         ["Celery: 1 tarea con 20 URLs (asyncio.run + gather)",
          segundos(t_cel1)]])


def pids_pool() -> list[int]:
    stats = app.control.inspect(timeout=3).stats() or {}
    return sorted(p for s in stats.values() for p in s["pool"]["processes"])


async def comparar_cancelacion(cliente) -> str:
    # Nuestra API: DELETE sobre una tarea esperar(30) en ejecución
    id_api = await crear_tarea(cliente, "esperar", {"segundos": 30})
    await asyncio.sleep(1)
    inicio = time.perf_counter()
    await cliente.delete(f"/tareas/{id_api}")
    final = await esperar_fin(cliente, id_api, intervalo=0.01)
    t_api = time.perf_counter() - inicio

    # Celery: revoke(terminate=True) sobre el mismo tipo de tarea
    antes = pids_pool()
    resultado = esperar.apply_async((30,))
    await asyncio.sleep(1)
    inicio = time.perf_counter()
    app.control.revoke(resultado.id, terminate=True)
    while resultado.state not in ("REVOKED", "SUCCESS", "FAILURE"):
        await asyncio.sleep(0.01)
    t_cel = time.perf_counter() - inicio
    estado_cel = resultado.state
    await asyncio.sleep(2)  # tiempo para que el pool reponga el proceso
    despues = pids_pool()
    return tabla(
        ["Sistema", "Hasta estado final [s]", "Estado", "Efecto en workers"],
        [["API: DELETE (cancela el asyncio.Task)", segundos(t_api),
          final["estado"], "ninguno: el worker (corrutina) sigue vivo"],
         ["Celery: revoke(terminate=True)", segundos(t_cel), estado_cel,
          f"el proceso hijo se mata con SIGTERM y el pool lo repone; "
          f"PIDs antes={antes} despues={despues}"]])


async def comparar_latencia_envio(cliente, n: int = 50) -> str:
    tiempos_api = []
    ids = []
    for _ in range(n):
        inicio = time.perf_counter()
        r = await cliente.post("/tareas", json={
            "tipo": "esperar", "parametros": {"segundos": 0}})
        tiempos_api.append(time.perf_counter() - inicio)
        ids.append(r.json()["id"])
    tiempos_cel = []
    for _ in range(n):
        inicio = time.perf_counter()
        esperar.delay(0)
        tiempos_cel.append(time.perf_counter() - inicio)
    tiempos_api.sort()
    tiempos_cel.sort()

    def fila(nombre, t):
        return [nombre, f"{sum(t) / n * 1000:.2f}",
                f"{t[n // 2] * 1000:.2f}", f"{t[-1] * 1000:.2f}"]
    return tabla(["Sistema", "Media [ms]", "Mediana [ms]", "Máx [ms]"],
                 [fila("API: POST /tareas", tiempos_api),
                  fila(".delay() (publica en Redis)", tiempos_cel)])


async def main(salida: str | None) -> None:
    iteraciones = calibrar_iteraciones()
    cabecera = (f"Fecha: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
                f"Máquina (contenedor): {platform.platform()}, "
                f"{os.cpu_count()} CPU\n"
                f"Config: API WORKERS=4 (MODO_CPU=executor), "
                f"Celery concurrency={app.conf.worker_concurrency} "
                f"(prefetch=1, acks_late), broker={app.conf.broker_url}\n")
    secciones = [cabecera]
    async with httpx.AsyncClient(base_url=API, timeout=60) as cliente:
        pruebas = [
            ("(a) I/O simulado: 20 x esperar(1 s)", comparar_esperar(cliente)),
            ("(b) CPU: 8 x hashear", comparar_hashear(cliente, iteraciones)),
            ("(c) Descargas: 20 x lento ms=500", comparar_descargas(cliente)),
            ("(d) Cancelación de esperar(30) tras 1 s",
             comparar_cancelacion(cliente)),
            ("(e) Latencia de envío de una tarea",
             comparar_latencia_envio(cliente)),
        ]
        for titulo, corrutina in pruebas:
            print(f"Ejecutando {titulo}...", flush=True)
            secciones.append(f"## {titulo}\n\n{await corrutina}\n")
    informe = "\n".join(secciones)
    print("\n" + informe)
    if salida:
        Path(salida).write_text(informe, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--salida", help="archivo Markdown donde guardar")
    asyncio.run(main(parser.parse_args().salida))
