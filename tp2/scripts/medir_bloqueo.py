"""Medición 2: latencia de GET /tareas durante un `hashear` pesado.

Uso: python scripts/medir_bloqueo.py --modo executor|bloqueante
El modo es el de la API en ejecución (MODO_CPU); acá solo se rotula.
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from _comun import crear_tarea, esperar_fin, percentil, tabla  # noqa: E402


async def sondear(api, detener: asyncio.Event, intervalo: float, timeout: float):
    """GET /tareas cada `intervalo` s; devuelve las latencias (s)."""
    latencias = []
    while not detener.is_set():
        inicio = time.perf_counter()
        try:
            await api.get("/tareas", timeout=timeout)
            latencias.append(time.perf_counter() - inicio)
        except httpx.TimeoutException:
            latencias.append(timeout)
        await asyncio.sleep(intervalo)
    return latencias


def fila(nombre, lat):
    ms = [x * 1000 for x in lat]
    return [nombre, len(ms), f"{sum(ms) / len(ms):.1f}",
            f"{percentil(ms, 50):.1f}", f"{percentil(ms, 95):.1f}",
            f"{max(ms):.1f}"]


async def main(args):
    async with httpx.AsyncClient(base_url=args.api, timeout=120) as api:
        detener = asyncio.Event()
        base = asyncio.create_task(sondear(api, detener, args.intervalo, 60))
        await asyncio.sleep(args.base_segundos)
        detener.set()
        lat_base = await base

        detener = asyncio.Event()
        sonda = asyncio.create_task(sondear(api, detener, args.intervalo, 60))
        await asyncio.sleep(0.5)  # unas muestras previas a la carga
        inicio = time.perf_counter()
        id_tarea = await crear_tarea(api, "hashear", {
            "texto": "medicion", "iteraciones": args.iteraciones})
        tarea = await esperar_fin(api, id_tarea, intervalo=0.2)
        duracion = time.perf_counter() - inicio
        detener.set()
        lat_carga = await sonda

    print(f"\nMedición 2: GET /tareas durante hashear de "
          f"{args.iteraciones:,} iteraciones (MODO_CPU={args.modo})\n")
    print(tabla(["Situación", "Muestras", "Media (ms)", "p50 (ms)",
                 "p95 (ms)", "Máx (ms)"],
                [fila("Sin carga (línea base)", lat_base),
                 fila(f"Durante hashear ({args.modo})", lat_carga)]))
    print(f"\nEstado final del hash: {tarea['estado']}; "
          f"duración total desde el POST: {duracion:.2f} s")
    print(f"Máxima latencia / media en reposo: "
          f"{max(lat_carga) / (sum(lat_base) / len(lat_base)):.0f}x")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--api", default="http://localhost:8000")
    p.add_argument("--modo", choices=["executor", "bloqueante"],
                   required=True, help="MODO_CPU con el que corre la API")
    p.add_argument("--iteraciones", type=int, default=10_000_000)
    p.add_argument("--intervalo", type=float, default=0.1)
    p.add_argument("--base-segundos", type=float, default=3)
    asyncio.run(main(p.parse_args()))
