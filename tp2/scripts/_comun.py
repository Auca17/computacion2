"""Utilidades compartidas por los scripts de medición (corren en el host)."""

import asyncio
import time

import httpx


async def crear_tarea(cliente: httpx.AsyncClient, tipo: str, parametros: dict,
                      timeout: float = 120) -> str:
    """Hace POST /tareas y devuelve el id."""
    r = await cliente.post("/tareas", json={
        "tipo": tipo, "parametros": parametros, "timeout": timeout})
    r.raise_for_status()
    return r.json()["id"]


async def esperar_fin(cliente: httpx.AsyncClient, id_tarea: str,
                      intervalo: float = 0.05) -> dict:
    """Consulta la tarea cada `intervalo` s hasta que termina."""
    while True:
        tarea = (await cliente.get(f"/tareas/{id_tarea}")).json()
        if tarea["estado"] in ("completada", "fallida", "cancelada"):
            return tarea
        await asyncio.sleep(intervalo)


async def ejecutar_lote(cliente: httpx.AsyncClient, tipo: str,
                        parametros: dict, n: int,
                        intervalo: float = 0.05) -> dict:
    """Postea `n` tareas a la vez y espera a que todas terminen.

    Devuelve el tiempo total, la espera media en cola (iniciada - creada)
    y la cantidad de tareas que no terminaron como completadas.
    """
    inicio = time.perf_counter()
    ids = await asyncio.gather(
        *(crear_tarea(cliente, tipo, parametros) for _ in range(n)))
    tareas = await asyncio.gather(
        *(esperar_fin(cliente, i, intervalo) for i in ids))
    total = time.perf_counter() - inicio
    esperas = [t["iniciada"] - t["creada"] for t in tareas
               if t["iniciada"] is not None]
    return {
        "total": total,
        "espera_media": sum(esperas) / len(esperas) if esperas else 0.0,
        "no_completadas": sum(t["estado"] != "completada" for t in tareas),
    }


def percentil(valores: list[float], p: float) -> float:
    """Percentil `p` (0-100) por rango más cercano."""
    ordenados = sorted(valores)
    indice = min(len(ordenados) - 1, round(p / 100 * (len(ordenados) - 1)))
    return ordenados[indice]


def tabla(encabezados: list[str], filas: list[list]) -> str:
    """Tabla en formato Markdown (legible también en consola)."""
    lineas = ["| " + " | ".join(encabezados) + " |",
              "|" + "|".join("---" for _ in encabezados) + "|"]
    lineas += ["| " + " | ".join(str(c) for c in f) + " |" for f in filas]
    return "\n".join(lineas)
