"""Medición 3: techo del pool al subir la concurrencia.

Uso: python scripts/medir_techo.py --exp esperar|hashear|descargar [--etiqueta ...]
La API debe estar levantada con el WORKERS que se quiere medir (se rotula
con --workers, que solo es informativo).
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from _comun import ejecutar_lote, tabla  # noqa: E402


async def barrer(api, tipo, parametros, ns, intervalo):
    """Ejecuta un lote por cada N y arma las filas de la tabla."""
    filas = []
    for n in ns:
        r = await ejecutar_lote(api, tipo, parametros, n, intervalo)
        filas.append([n, f"{r['total']:.2f}", f"{r['espera_media']:.2f}",
                      r["no_completadas"]])
    return filas


async def main(args):
    print(f"CPUs del host: {os.cpu_count()} (os.cpu_count)")
    print(f"WORKERS de la API: {args.workers}\n")
    encabezado = ["N tareas", "Tiempo total (s)", "Espera media en cola (s)",
                  "No completadas"]
    async with httpx.AsyncClient(base_url=args.api, timeout=300) as api:
        if args.exp == "esperar":
            print("esperar(1 s)\n")
            ns, params = [1, 2, 4, 8, 16, 32, 64], {"segundos": 1}
            tipo = "esperar"
        elif args.exp == "hashear":
            print(f"hashear con {args.iteraciones:,} iteraciones\n")
            ns, params = [1, 2, 4, 8, 16], {
                "texto": "techo", "iteraciones": args.iteraciones}
            tipo = "hashear"
        else:
            print(f"descargar de 10 URLs a ms={args.ms}\n")
            ns, tipo = [1, 4, 16, 64], "descargar"
            params = {"urls": [f"{args.base_interna}/demora?ms={args.ms}&i={i}"
                               for i in range(10)]}
        filas = await barrer(api, tipo, params, ns, args.intervalo)
    print(tabla(encabezado, filas))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--api", default="http://localhost:8000")
    p.add_argument("--base-interna", default="http://lento:8001")
    p.add_argument("--exp", choices=["esperar", "hashear", "descargar"],
                   required=True)
    p.add_argument("--workers", type=int, default=4,
                   help="WORKERS de la API (solo rótulo)")
    p.add_argument("--iteraciones", type=int, default=2_000_000)
    p.add_argument("--ms", type=int, default=500)
    p.add_argument("--intervalo", type=float, default=0.05)
    asyncio.run(main(p.parse_args()))
