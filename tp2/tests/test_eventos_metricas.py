"""Pruebas del WebSocket /eventos y de GET /metricas."""

import asyncio

from fastapi.testclient import TestClient

from app import config
from app.main import app

from .conftest import crear, esperar_estado


def test_eventos_recibe_cambios_de_estado():
    with TestClient(app) as c:
        with c.websocket_connect("/eventos") as ws:
            id_ = c.post("/tareas", json={
                "tipo": "esperar", "parametros": {"segundos": 0.05}}
            ).json()["id"]
            mensajes = [ws.receive_json() for _ in range(3)]
    assert [m["estado"] for m in mensajes] == [
        "pendiente", "ejecutando", "completada"]
    assert all(m["id"] == id_ and m["tipo"] == "esperar" for m in mensajes)


def test_eventos_cancelacion():
    with TestClient(app) as c:
        with c.websocket_connect("/eventos") as ws:
            id_ = c.post("/tareas", json={
                "tipo": "esperar", "parametros": {"segundos": 30}}
            ).json()["id"]
            assert ws.receive_json()["estado"] == "pendiente"
            assert ws.receive_json()["estado"] == "ejecutando"
            c.delete(f"/tareas/{id_}")
            assert ws.receive_json()["estado"] == "cancelada"


def test_apagado_cierra_websockets_abiertos():
    # Si el servidor no cerrara la conexión, salir del cliente se colgaría
    with TestClient(app) as c:
        c.websocket_connect("/eventos").__enter__()


async def test_metricas_formato_prometheus(cliente):
    id_ = (await crear(cliente, "esperar", {"segundos": 0})).json()["id"]
    await esperar_estado(cliente, id_, "completada")
    await asyncio.sleep(0.05)  # el worker libera su cupo tras el estado final
    r = await cliente.get("/metricas")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "version=0.0.4" in r.headers["content-type"]
    lineas = r.text.splitlines()
    assert 'tareas_total{estado="completada"} 1' in lineas
    assert 'tareas_total{estado="pendiente"} 0' in lineas
    assert f"workers_total {config.WORKERS}" in lineas
    assert "workers_ocupados 0" in lineas
    assert "cola_tamano 0" in lineas
    assert any(l.startswith('tarea_duracion_segundos_promedio{tipo="esperar"}')
               for l in lineas)
    assert "# TYPE tareas_total gauge" in lineas
