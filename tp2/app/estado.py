"""Registro en memoria de las tareas y sus estados."""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from . import config

log = logging.getLogger("plataforma")

ESTADOS = ("pendiente", "ejecutando", "completada", "fallida", "cancelada")


@dataclass
class Tarea:
    """Registro de una tarea y su ciclo de vida."""

    tipo: str
    parametros: dict
    timeout: float
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    estado: str = "pendiente"
    resultado: Optional[Any] = None
    error: Optional[str] = None
    creada: float = field(default_factory=time.time)
    iniciada: Optional[float] = None
    finalizada: Optional[float] = None

    def duracion(self) -> Optional[float]:
        """Segundos entre inicio y fin, o None si no terminó."""
        if self.iniciada is None or self.finalizada is None:
            return None
        return self.finalizada - self.iniciada

    def a_dict(self) -> dict:
        """Representación serializable de la tarea."""
        return {
            "id": self.id,
            "tipo": self.tipo,
            "parametros": self.parametros,
            "estado": self.estado,
            "resultado": self.resultado,
            "error": self.error,
            "creada": self.creada,
            "iniciada": self.iniciada,
            "finalizada": self.finalizada,
            "timeout": self.timeout,
        }


# Registro único de tareas: id -> Tarea
registro: dict[str, Tarea] = {}


def _conteo_por_estado(tareas: list[dict]) -> dict[str, int]:
    """Cantidad de tareas por estado."""
    return {e: sum(1 for t in tareas if t["estado"] == e) for e in ESTADOS}


def volcar_registro() -> Path:
    """Escribe todo el registro en DIR_VOLCADOS/estado_<timestamp>.json.

    Se usa una escritura síncrona: ocurre durante el apagado, cuando ya no
    quedan workers ni peticiones que el bloqueo pueda demorar.
    """
    ahora = time.time()
    tareas = [t.a_dict() for t in registro.values()]
    destino = Path(config.DIR_VOLCADOS)
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / f"estado_{time.strftime('%Y%m%d-%H%M%S', time.localtime(ahora))}.json"
    contenido = {
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ahora)),
        "total": len(tareas),
        "por_estado": _conteo_por_estado(tareas),
        "tareas": tareas,
    }
    ruta.write_text(json.dumps(contenido, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return ruta


def reportar_volcado_previo() -> None:
    """Informa por log el volcado más reciente, sin restaurar las tareas."""
    volcados = sorted(Path(config.DIR_VOLCADOS).glob("estado_*.json"))
    if not volcados:
        log.info("No hay volcados previos en %s", config.DIR_VOLCADOS)
        return
    ruta = volcados[-1]
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        log.info("Volcado previo: %s, %d tareas, por estado: %s",
                 ruta, datos["total"], datos["por_estado"])
    except (OSError, ValueError, KeyError) as exc:
        log.warning("No se pudo leer el volcado previo %s: %s", ruta, exc)
