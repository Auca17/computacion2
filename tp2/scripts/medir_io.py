"""Medición 1: 20 descargas secuenciales contra 20 concurrentes.

Uso (con el stack levantado): python scripts/medir_io.py [--n 20] [--ms 500]
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from _comun import crear_tarea, esperar_fin, tabla  # noqa: E402


def urls(base: str, n: int, ms: int) -> list[str]:
    """URLs distintas (parámetro `i`) contra el servidor lento."""
    return [f"{base}/demora?ms={ms}&i={i}" for i in range(n)]


async def tarea_concurrente(api, lista):
    """Una tarea `descargar` con todas las URLs."""
    inicio = time.perf_counter()
    id_tarea = await crear_tarea(api, "descargar", {"urls": lista})
    tarea = await esperar_fin(api, id_tarea)
    total = time.perf_counter() - inicio
    tiempos = [r["segundos"] for r in tarea["resultado"]]
    return total, tiempos


async def tareas_secuenciales(api, lista):
    """Una tarea `descargar` de 1 URL por vez, esperando cada una."""
    inicio = time.perf_counter()
    for url in lista:
        id_tarea = await crear_tarea(api, "descargar", {"urls": [url]})
        await esperar_fin(api, id_tarea)
    return time.perf_counter() - inicio


async def referencia_directa(lista):
    """for + await contra gather, directo desde el host (sin la API)."""
    async with httpx.AsyncClient() as c:
        inicio = time.perf_counter()
        for url in lista:
            await c.get(url)
        secuencial = time.perf_counter() - inicio
        inicio = time.perf_counter()
        await asyncio.gather(*(c.get(url) for url in lista))
        return secuencial, time.perf_counter() - inicio


async def main(args):
    lista_api = urls(args.base_interna, args.n, args.ms)
    lista_host = urls(args.base_host, args.n, args.ms)
    ideal_seq = args.n * args.ms / 1000
    async with httpx.AsyncClient(base_url=args.api, timeout=120) as api:
        total_conc, tiempos = await tarea_concurrente(api, lista_api)
        total_seq = await tareas_secuenciales(api, lista_api)
    dir_seq, dir_gather = await referencia_directa(lista_host)

    print(f"\nMedición 1: {args.n} descargas de /demora?ms={args.ms}\n")
    print(tabla(
        ["Modo", "Tiempo total (s)", "Speedup"],
        [[f"{args.n} tareas de 1 URL, una por vez", f"{total_seq:.3f}", "1.00x"],
         [f"1 tarea con {args.n} URLs (gather)", f"{total_conc:.3f}",
          f"{total_seq / total_conc:.2f}x"]]))
    print(f"\nTiempos propios por URL de la tarea concurrente: "
          f"min {min(tiempos):.3f} s, max {max(tiempos):.3f} s, "
          f"media {sum(tiempos) / len(tiempos):.3f} s")
    print(f"Tiempo ideal secuencial: {ideal_seq:.3f} s; "
          f"ideal concurrente: {args.ms / 1000:.3f} s")
    print("\nReferencia directa con httpx desde el host (sin la API):\n")
    print(tabla(
        ["Estrategia", "Tiempo total (s)", "Speedup"],
        [["for con await", f"{dir_seq:.3f}", "1.00x"],
         ["asyncio.gather", f"{dir_gather:.3f}", f"{dir_seq / dir_gather:.2f}x"]]))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--api", default="http://localhost:8000")
    p.add_argument("--base-interna", default="http://lento:8001",
                   help="URL del servidor lento vista desde el contenedor api")
    p.add_argument("--base-host", default="http://localhost:8001",
                   help="URL del servidor lento vista desde el host")
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--ms", type=int, default=500)
    asyncio.run(main(p.parse_args()))
