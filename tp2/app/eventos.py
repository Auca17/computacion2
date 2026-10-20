"""Difusión de cambios de estado a los clientes WebSocket (`/eventos`)."""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .estado import Tarea

router = APIRouter()

TAMANIO_BUFFER = 100  # mensajes pendientes por cliente antes de descartar

# Una cola acotada por cliente conectado
_clientes: set[asyncio.Queue] = set()


def publicar(tarea: Tarea) -> None:
    """Avisa a todos los clientes el estado actual de la tarea.

    Nunca bloquea: si el buffer de un cliente lento está lleno, el mensaje
    se descarta para ese cliente y los workers siguen sin demora.
    """
    mensaje = {"id": tarea.id, "tipo": tarea.tipo, "estado": tarea.estado,
               "error": tarea.error}
    for cola in _clientes:
        try:
            cola.put_nowait(mensaje)
        except asyncio.QueueFull:
            pass


def cerrar_todos() -> None:
    """Pide a cada conexión que termine (se usa al apagar el servidor)."""
    for cola in _clientes:
        try:
            cola.put_nowait(None)
        except asyncio.QueueFull:
            cola.get_nowait()  # se hace lugar para la señal de cierre
            cola.put_nowait(None)


@router.websocket("/eventos")
async def eventos(ws: WebSocket) -> None:
    """Envía un JSON por cada cambio de estado de cualquier tarea."""
    await ws.accept()
    cola: asyncio.Queue = asyncio.Queue(maxsize=TAMANIO_BUFFER)
    _clientes.add(cola)
    # Detecta la desconexión del cliente mientras se espera en la cola
    escucha = asyncio.create_task(ws.receive_text())
    try:
        while True:
            siguiente = asyncio.create_task(cola.get())
            hechas, _ = await asyncio.wait(
                {siguiente, escucha}, return_when=asyncio.FIRST_COMPLETED)
            if siguiente not in hechas:
                siguiente.cancel()
                break  # el cliente se fue
            mensaje = siguiente.result()
            if mensaje is None:
                await ws.close()  # apagado del servidor
                break
            await ws.send_json(mensaje)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        escucha.cancel()
        _clientes.discard(cola)
