"""Registro en memoria de las tareas y sus estados."""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

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
