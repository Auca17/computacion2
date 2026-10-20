"""Estadísticas de la plataforma y su exposición en formato Prometheus."""

from fastapi import APIRouter, Response

from . import config
from .cola import plataforma
from .estado import ESTADOS, registro

router = APIRouter()


def calcular_estadisticas() -> dict:
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


def _metrica(lineas: list[str], nombre: str, tipo: str, ayuda: str,
             muestras: list[tuple[str, float]]) -> None:
    """Agrega una métrica con sus líneas HELP, TYPE y muestras."""
    lineas.append(f"# HELP {nombre} {ayuda}")
    lineas.append(f"# TYPE {nombre} {tipo}")
    for etiquetas, valor in muestras:
        lineas.append(f"{nombre}{etiquetas} {valor}")


@router.get("/metricas")
async def metricas() -> Response:
    """Métricas en formato de exposición de texto de Prometheus."""
    est = calcular_estadisticas()
    lineas: list[str] = []
    _metrica(lineas, "tareas_total", "gauge", "Tareas por estado",
             [(f'{{estado="{e}"}}', n) for e, n in est["por_estado"].items()])
    _metrica(lineas, "workers_ocupados", "gauge", "Workers ejecutando una tarea",
             [("", est["workers_ocupados"])])
    _metrica(lineas, "workers_total", "gauge", "Workers configurados",
             [("", est["workers_total"])])
    _metrica(lineas, "cola_tamano", "gauge", "Tareas esperando en la cola",
             [("", est["tamanio_cola"])])
    _metrica(lineas, "tarea_duracion_segundos_promedio", "gauge",
             "Duración promedio por tipo de tarea",
             [(f'{{tipo="{t}"}}', round(d, 6))
              for t, d in est["duracion_promedio_por_tipo"].items()])
    return Response("\n".join(lineas) + "\n",
                    media_type="text/plain; version=0.0.4")
