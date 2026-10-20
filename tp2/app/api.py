"""Endpoints HTTP de la plataforma."""

import asyncio
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl, ValidationError

from . import config
from .cola import plataforma
from .estado import ESTADOS, Tarea, registro

router = APIRouter()


class ParamsDescargar(BaseModel):
    urls: list[HttpUrl] = Field(min_length=1)


class ParamsHashear(BaseModel):
    texto: str
    iteraciones: int = Field(ge=1)


class ParamsEsperar(BaseModel):
    segundos: float = Field(ge=0)


class NuevaTarea(BaseModel):
    tipo: Literal["descargar", "hashear", "esperar"]
    parametros: dict
    timeout: Optional[float] = Field(default=None, gt=0)


MODELOS = {
    "descargar": ParamsDescargar,
    "hashear": ParamsHashear,
    "esperar": ParamsEsperar,
}


@router.post("/tareas", status_code=202)
async def crear_tarea(datos: NuevaTarea):
    """Encola una tarea y responde de inmediato."""
    if not plataforma.aceptando:
        raise HTTPException(503, "La plataforma no acepta tareas nuevas")
    try:
        params = MODELOS[datos.tipo](**datos.parametros)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_url=False, include_context=False))
    tarea = Tarea(
        tipo=datos.tipo,
        parametros=params.model_dump(mode="json"),
        timeout=datos.timeout or config.TIMEOUT_DEFECTO,
    )
    try:
        plataforma.encolar(tarea)
    except asyncio.QueueFull:
        raise HTTPException(429, "La cola de tareas está llena")
    return {"id": tarea.id, "estado": tarea.estado}


@router.get("/tareas")
async def listar_tareas(estado: Optional[str] = None):
    """Lista las tareas, con filtro opcional por estado."""
    if estado is not None and estado not in ESTADOS:
        raise HTTPException(422, f"Estado inválido; use uno de {ESTADOS}")
    return [t.a_dict() for t in registro.values()
            if estado is None or t.estado == estado]


@router.get("/tareas/{id_tarea}")
async def obtener_tarea(id_tarea: str):
    """Estado y resultado de una tarea."""
    tarea = registro.get(id_tarea)
    if tarea is None:
        raise HTTPException(404, "Tarea inexistente")
    return tarea.a_dict()


@router.delete("/tareas/{id_tarea}")
async def cancelar_tarea(id_tarea: str):
    """Cancela una tarea pendiente o en ejecución."""
    tarea = registro.get(id_tarea)
    if tarea is None:
        raise HTTPException(404, "Tarea inexistente")
    if tarea.estado not in ("pendiente", "ejecutando"):
        raise HTTPException(409, f"La tarea ya está {tarea.estado}")
    await plataforma.cancelar(tarea)
    return tarea.a_dict()


@router.get("/estadisticas")
async def estadisticas():
    """Totales por estado, duraciones promedio y ocupación de workers."""
    por_estado = {e: 0 for e in ESTADOS}
    duraciones: dict[str, list[float]] = {}
    for t in registro.values():
        por_estado[t.estado] += 1
        if t.duracion() is not None:
            duraciones.setdefault(t.tipo, []).append(t.duracion())
    todas = [d for lista in duraciones.values() for d in lista]
    return {
        "total": len(registro),
        "por_estado": por_estado,
        "duracion_promedio": sum(todas) / len(todas) if todas else None,
        "duracion_promedio_por_tipo": {
            tipo: sum(lista) / len(lista) for tipo, lista in duraciones.items()
        },
        "workers_ocupados": plataforma.ocupados,
        "workers_total": config.WORKERS,
        "tamanio_cola": plataforma.cola.qsize() if plataforma.cola else 0,
    }
