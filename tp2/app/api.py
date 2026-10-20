"""Endpoints HTTP de la plataforma."""

import asyncio
import math
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, HttpUrl, ValidationError

from . import config
from .cola import plataforma
from .eventos import publicar
from .limite import limitador
from .estado import ESTADOS, Tarea, registro
from .metricas import calcular_estadisticas

router = APIRouter()


class ParamsDescargar(BaseModel):
    urls: list[HttpUrl] = Field(min_length=1)


class ParamsHashear(BaseModel):
    texto: str
    iteraciones: int = Field(ge=1)


class ParamsEsperar(BaseModel):
    segundos: float = Field(ge=0)


class ParamsSondear(BaseModel):
    host: str = Field(min_length=1)
    puertos: list[Annotated[int, Field(ge=1, le=65535)]] = Field(
        min_length=1, max_length=1024)
    timeout_conexion: float = Field(default=1.0, gt=0, le=10)


class NuevaTarea(BaseModel):
    tipo: Literal["descargar", "hashear", "esperar", "sondear"]
    parametros: dict
    timeout: Optional[float] = Field(default=None, gt=0)
    prioridad: int = Field(default=5, ge=1, le=10)  # 1 = más alta
    reintentos: int = Field(default=0, ge=0, le=5)


MODELOS = {
    "descargar": ParamsDescargar,
    "hashear": ParamsHashear,
    "esperar": ParamsEsperar,
    "sondear": ParamsSondear,
}


@router.post("/tareas", status_code=202)
async def crear_tarea(datos: NuevaTarea, request: Request):
    """Encola una tarea y responde de inmediato."""
    if not plataforma.aceptando:
        raise HTTPException(503, "La plataforma no acepta tareas nuevas")
    cliente = request.client.host if request.client else "desconocido"
    espera = limitador.consumir(cliente)
    if espera > 0:
        plataforma.rechazadas_por_limite += 1
        raise HTTPException(
            429, "Demasiadas solicitudes: límite por cliente",
            headers={"Retry-After": str(max(1, math.ceil(espera)))})
    try:
        params = MODELOS[datos.tipo](**datos.parametros)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_url=False, include_context=False))
    tarea = Tarea(
        tipo=datos.tipo,
        parametros=params.model_dump(mode="json"),
        timeout=datos.timeout or config.TIMEOUT_DEFECTO,
        prioridad=datos.prioridad,
        reintentos=datos.reintentos,
    )
    try:
        plataforma.encolar(tarea)
    except asyncio.QueueFull:
        raise HTTPException(429, "La cola de tareas está llena")
    publicar(tarea)
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
    return calcular_estadisticas()
