"""Pruebas de prioridades, reintentos, rate limiting, sondeo y concurrencia."""

import asyncio

import httpx

from app import config, tareas
from app.cola import plataforma

from .conftest import crear, esperar_estado


async def ocupar_workers(cliente):
    """Lanza tareas largas hasta ocupar los workers; devuelve sus ids."""
    ids = []
    for _ in range(config.WORKERS):
        id_ = (await crear(cliente, "esperar", {"segundos": 30})).json()["id"]
        await esperar_estado(cliente, id_, "ejecutando")
        ids.append(id_)
    return ids


# --- Prioridades -----------------------------------------------------------

async def test_prioridad_menor_valor_corre_primero(cliente):
    ocupadas = await ocupar_workers(cliente)
    baja = (await crear(cliente, "esperar", {"segundos": 30},
                        prioridad=9)).json()["id"]
    alta = (await crear(cliente, "esperar", {"segundos": 30},
                        prioridad=1)).json()["id"]
    await cliente.delete(f"/tareas/{ocupadas[0]}")  # libera un worker
    await esperar_estado(cliente, alta, "ejecutando")
    assert (await cliente.get(f"/tareas/{baja}")).json()["estado"] == "pendiente"


async def test_envejecimiento_evita_inanicion(cliente, monkeypatch):
    monkeypatch.setattr(config, "ENVEJECIMIENTO_S", 0.05)
    ocupadas = await ocupar_workers(cliente)
    vieja = (await crear(cliente, "esperar", {"segundos": 30},
                         prioridad=10)).json()["id"]
    await asyncio.sleep(0.6)  # 12 puntos menos: 10 - 12 < 1 (la nueva)
    nueva = (await crear(cliente, "esperar", {"segundos": 30},
                         prioridad=1)).json()["id"]
    await cliente.delete(f"/tareas/{ocupadas[0]}")
    await esperar_estado(cliente, vieja, "ejecutando")
    assert (await cliente.get(f"/tareas/{nueva}")).json()["estado"] == "pendiente"


async def test_prioridad_invalida_422(cliente):
    for valor in (0, 11):
        r = await crear(cliente, "esperar", {"segundos": 0}, prioridad=valor)
        assert r.status_code == 422


# --- Reintentos ------------------------------------------------------------

def ejecutor_que_falla(monkeypatch, fallos):
    """Reemplaza `esperar` por uno que falla `fallos` veces (None = siempre)."""
    llamadas = []

    async def inestable(parametros, executor):
        llamadas.append(1)
        if fallos is None or len(llamadas) <= fallos:
            raise ValueError(f"falla {len(llamadas)}")
        return {"ok": True}

    monkeypatch.setitem(tareas.EJECUTORES, "esperar", inestable)
    return llamadas


async def test_reintentos_hasta_completar(cliente, monkeypatch):
    monkeypatch.setattr(config, "BACKOFF_BASE", 0.01)
    llamadas = ejecutor_que_falla(monkeypatch, 2)
    antes = plataforma.reintentos_programados
    id_ = (await crear(cliente, "esperar", {"segundos": 0},
                       reintentos=2)).json()["id"]
    tarea = await esperar_estado(cliente, id_, "completada")
    assert tarea["intentos"] == 3 and len(llamadas) == 3
    assert len(tarea["errores"]) == 2 and "falla 1" in tarea["errores"][0]
    assert plataforma.reintentos_programados - antes == 2


async def test_reintentos_agotados_queda_fallida(cliente, monkeypatch):
    monkeypatch.setattr(config, "BACKOFF_BASE", 0.01)
    ejecutor_que_falla(monkeypatch, None)
    id_ = (await crear(cliente, "esperar", {"segundos": 0},
                       reintentos=1)).json()["id"]
    tarea = await esperar_estado(cliente, id_, "fallida")
    assert tarea["intentos"] == 2 and len(tarea["errores"]) == 2
    assert "ValueError" in tarea["error"]


async def test_sin_reintentos_falla_de_inmediato(cliente, monkeypatch):
    ejecutor_que_falla(monkeypatch, None)
    id_ = (await crear(cliente, "esperar", {"segundos": 0})).json()["id"]
    tarea = await esperar_estado(cliente, id_, "fallida")
    assert tarea["intentos"] == 1 and not plataforma.temporizadores


async def test_backoff_no_ocupa_worker(cliente, monkeypatch):
    monkeypatch.setattr(config, "BACKOFF_BASE", 30)
    ejecutor_que_falla(monkeypatch, None)
    id_ = (await crear(cliente, "esperar", {"segundos": 0},
                       reintentos=1)).json()["id"]
    async with asyncio.timeout(5):
        while not plataforma.temporizadores:
            await asyncio.sleep(0.01)
    await asyncio.sleep(0.05)  # el worker libera su cupo tras el fallo
    tarea = (await cliente.get(f"/tareas/{id_}")).json()
    assert tarea["estado"] == "pendiente" and tarea["proximo_intento"]
    assert plataforma.ocupados == 0


async def test_delete_en_backoff_cancela_y_no_reejecuta(cliente, monkeypatch):
    monkeypatch.setattr(config, "BACKOFF_BASE", 0.2)
    llamadas = ejecutor_que_falla(monkeypatch, None)
    id_ = (await crear(cliente, "esperar", {"segundos": 0},
                       reintentos=3)).json()["id"]
    async with asyncio.timeout(5):
        while not plataforma.temporizadores:
            await asyncio.sleep(0.01)
    r = await cliente.delete(f"/tareas/{id_}")
    assert r.json()["estado"] == "cancelada"
    assert not plataforma.temporizadores
    await asyncio.sleep(0.5)
    assert len(llamadas) == 1
    assert (await cliente.get(f"/tareas/{id_}")).json()["estado"] == "cancelada"


async def test_cancelacion_no_dispara_reintento(cliente):
    id_ = (await crear(cliente, "esperar", {"segundos": 30},
                       reintentos=3)).json()["id"]
    await esperar_estado(cliente, id_, "ejecutando")
    await cliente.delete(f"/tareas/{id_}")
    await asyncio.sleep(0.1)
    tarea = (await cliente.get(f"/tareas/{id_}")).json()
    assert tarea["estado"] == "cancelada" and tarea["intentos"] == 1
    assert not plataforma.temporizadores


async def test_apagar_cancela_temporizadores(cliente, monkeypatch):
    monkeypatch.setattr(config, "BACKOFF_BASE", 30)
    ejecutor_que_falla(monkeypatch, None)
    id_ = (await crear(cliente, "esperar", {"segundos": 0},
                       reintentos=1)).json()["id"]
    async with asyncio.timeout(5):
        while not plataforma.temporizadores:
            await asyncio.sleep(0.01)
    await plataforma.apagar(0.05)
    assert not plataforma.temporizadores
    assert (await cliente.get(f"/tareas/{id_}")).json()["estado"] == "cancelada"


# --- Rate limiting ---------------------------------------------------------

async def test_rate_limit_429_con_retry_after(cliente, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_POR_SEG", 0.5)
    monkeypatch.setattr(config, "RATE_LIMIT_RAFAGA", 2)
    antes = plataforma.rechazadas_por_limite
    for _ in range(2):
        assert (await crear(cliente, "esperar", {"segundos": 0})).status_code == 202
    r = await crear(cliente, "esperar", {"segundos": 0})
    assert r.status_code == 429
    assert r.json()["detail"] == "Demasiadas solicitudes: límite por cliente"
    assert int(r.headers["Retry-After"]) >= 1
    assert plataforma.rechazadas_por_limite - antes == 1
    texto = (await cliente.get("/metricas")).text
    assert "rechazadas_por_limite_total" in texto
    assert "reintentos_programados_total" in texto


async def test_rate_limit_se_recarga(cliente, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_POR_SEG", 50)
    monkeypatch.setattr(config, "RATE_LIMIT_RAFAGA", 1)
    assert (await crear(cliente, "esperar", {"segundos": 0})).status_code == 202
    await asyncio.sleep(0.05)
    assert (await crear(cliente, "esperar", {"segundos": 0})).status_code == 202


# --- Sondear ---------------------------------------------------------------

async def test_sondear_puerto_abierto_y_cerrado(cliente):
    servidor = await asyncio.start_server(lambda r, w: w.close(),
                                          "127.0.0.1", 0)
    abierto = servidor.sockets[0].getsockname()[1]
    cerrado_srv = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
    cerrado = cerrado_srv.sockets[0].getsockname()[1]
    cerrado_srv.close()
    await cerrado_srv.wait_closed()
    try:
        id_ = (await crear(cliente, "sondear", {
            "host": "127.0.0.1", "puertos": [abierto, cerrado],
            "timeout_conexion": 3})).json()["id"]
        tarea = await esperar_estado(cliente, id_, "completada")
    finally:
        servidor.close()
        await servidor.wait_closed()
    primero, segundo = tarea["resultado"]
    assert primero["puerto"] == abierto and primero["abierto"] is True
    assert primero["ms"] >= 0
    assert segundo["puerto"] == cerrado and segundo["abierto"] is False
    assert segundo["motivo"]


async def test_sondear_valida_parametros(cliente):
    for params in ({"host": "x", "puertos": [0]},
                   {"host": "x", "puertos": [70000]},
                   {"host": "x", "puertos": []},
                   {"host": "x", "puertos": [80], "timeout_conexion": 11}):
        assert (await crear(cliente, "sondear", params)).status_code == 422


# --- Concurrencia estructurada y configuración -----------------------------

async def test_descargar_limita_conexiones_y_conserva_orden(monkeypatch):
    monkeypatch.setattr(config, "MAX_CONEXIONES", 2)
    activas = maximo = 0

    async def responder(request):
        nonlocal activas, maximo
        activas += 1
        maximo = max(maximo, activas)
        await asyncio.sleep(0.05)
        activas -= 1
        return httpx.Response(200, content=request.url.path.encode())

    real = httpx.AsyncClient
    monkeypatch.setattr(
        tareas.httpx, "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(responder)))
    urls = [f"http://sitio/{i}" for i in range(6)]
    resultado = await tareas.descargar({"urls": urls}, None)
    assert [r["url"] for r in resultado] == urls
    assert [r["bytes"] for r in resultado] == [2] * 6
    assert maximo == 2


async def test_procesos_cpu_configurable(cliente, monkeypatch):
    monkeypatch.setattr(config, "PROCESOS_CPU", 2)
    await plataforma.detener()
    plataforma.iniciar()  # el cliente ya había iniciado con el valor anterior
    assert plataforma.executor._max_workers == 2
