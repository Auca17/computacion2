# TP2 — Plataforma de Tareas Distribuidas

**Computación II — Universidad de Mendoza — 2026**

Servicio HTTP al que se le encargan trabajos (`descargar`, `hashear`, `esperar`),
que los ejecuta de forma concurrente en un pool de workers asíncronos y permite
consultar su estado y resultado, cancelarlos y ver estadísticas en vivo.

---

## 1. Descripción y uso

### Levantar

```bash
cd tp2
docker compose up --build
```

Quedan dos servicios:

| Servicio | Puerto | Qué es |
|----------|--------|--------|
| `api` | `8000` | La plataforma (FastAPI + cola + workers) |
| `lento` | `8001` | Servidor auxiliar con `GET /demora?ms=N`, usado para mediciones reproducibles |

Documentación interactiva: <http://localhost:8000/docs>.

### Configuración (variables de entorno)

| Variable | Defecto | Qué controla |
|----------|---------|--------------|
| `WORKERS` | `4` | Cantidad de corrutinas worker |
| `TIMEOUT_DEFECTO` | `30` | Timeout (s) de una tarea si el `POST` no indica otro |
| `GRACIA_APAGADO` | `10` | Segundos que el apagado espera a las tareas en curso |
| `MODO_CPU` | `executor` | `executor` o `bloqueante` (este último solo para la medición 2) |
| `MAX_COLA` | `1000` | Tamaño máximo de la cola; si se llena, `POST` responde `429` |
| `DIR_VOLCADOS` | `/datos` | Carpeta de los volcados `estado_<timestamp>.json` (montada en `./datos`) |

Ejemplo: `WORKERS=16 docker compose up --build`.

### Endpoints

| Método | Ruta | Qué hace |
|--------|------|----------|
| `POST` | `/tareas` | Encola una tarea. Responde `202` con `id` y estado inicial |
| `GET` | `/tareas?estado=...` | Lista las tareas, con filtro opcional por estado |
| `GET` | `/tareas/{id}` | Estado y resultado de una tarea |
| `DELETE` | `/tareas/{id}` | Cancela una tarea pendiente o en ejecución |
| `GET` | `/estadisticas` | Totales por estado, tiempos promedio, workers ocupados, tamaño de cola |
| `GET` | `/metricas` | Lo mismo en formato Prometheus (bonus) |
| `WS` | `/eventos` | Cambios de estado en tiempo real (bonus) |

Estados: `pendiente` → `ejecutando` → `completada` | `fallida` | `cancelada`.

Códigos de error: `404` id inexistente, `409` cancelar una tarea ya terminada,
`422` cuerpo inválido, `429` cola llena, `503` la plataforma se está apagando.

### Ejemplos con `curl`

```bash
# Descargar varias URLs concurrentemente
curl -X POST localhost:8000/tareas -H 'Content-Type: application/json' \
  -d '{"tipo":"descargar","parametros":{"urls":["http://lento:8001/demora?ms=500","https://example.com"]}}'
# -> {"id":"3f2a9c1b","estado":"pendiente"}

# Hash SHA-256 iterado (CPU-bound)
curl -X POST localhost:8000/tareas -H 'Content-Type: application/json' \
  -d '{"tipo":"hashear","parametros":{"texto":"hola","iteraciones":5000000}}'

# Esperar 30 s con timeout de 5 s (termina fallida por timeout)
curl -X POST localhost:8000/tareas -H 'Content-Type: application/json' \
  -d '{"tipo":"esperar","parametros":{"segundos":30},"timeout":5}'

# Consultar
curl localhost:8000/tareas
curl 'localhost:8000/tareas?estado=ejecutando'
curl localhost:8000/tareas/3f2a9c1b

# Cancelar (también si está ejecutando)
curl -X DELETE localhost:8000/tareas/3f2a9c1b

# Estadísticas y métricas
curl localhost:8000/estadisticas
curl localhost:8000/metricas
```

Para ver eventos en vivo: `websocat ws://localhost:8000/eventos` (o cualquier
cliente WebSocket).

### Tests

```bash
cd tp2
pip install -r requirements.txt
python -m pytest -q        # 21 tests, ~2 s
```

### Apagado ordenado

`docker compose stop api` (SIGTERM) o `Ctrl+C` (SIGINT): la API deja de aceptar
tareas, espera hasta `GRACIA_APAGADO` segundos a las que están en curso, cancela
las restantes y vuelca todo a `./datos/estado_<timestamp>.json`. Al volver a
arrancar, el log informa el volcado previo.

---

## 2. Arquitectura

```
                 Cliente HTTP / WebSocket
                          │
                          ▼
  ┌───────────────────────────────────────────────┐
  │  API FastAPI (api.py)        un solo proceso, │
  │  POST/GET/DELETE /tareas     un solo hilo,    │
  │  /estadisticas /metricas     un event loop    │
  │  WS /eventos (eventos.py)                     │
  └──────┬─────────────────────────────▲──────────┘
         │ put_nowait (429 si llena)   │ lee/escribe
         ▼                             │
  ┌──────────────────┐        ┌────────┴─────────┐
  │ asyncio.Queue    │        │ registro (dict)  │
  │ maxsize=MAX_COLA │        │ id -> Tarea      │
  └──────┬───────────┘        └────────▲─────────┘
         │ await get()                 │ estado/resultado
         ▼                             │
  ┌───────────────────────────────────────────────┐
  │ Pool: WORKERS corrutinas (cola.py)            │
  │  cada tarea corre en su propio asyncio.Task   │
  │  con asyncio.timeout(...)                     │
  │                                               │
  │  descargar ─► httpx.AsyncClient + gather      │
  │  esperar   ─► asyncio.sleep                   │
  │  hashear   ─► run_in_executor ──┐             │
  └─────────────────────────────────┼─────────────┘
                                    ▼
                     ┌──────────────────────────┐
                     │ ProcessPoolExecutor      │
                     │ (un proceso por núcleo)  │
                     │ SHA-256 en bloques de    │
                     │ 200.000 iteraciones      │
                     └──────────────────────────┘
```

### Flujo de una tarea

1. `POST /tareas` valida el cuerpo con Pydantic, crea un `Tarea` en estado
   `pendiente`, lo mete en la cola con `put_nowait` y responde `202` **sin
   esperar**. Si la cola está llena, `429`.
2. Un worker libre hace `await cola.get()`, marca la tarea `ejecutando` y la
   lanza en un `asyncio.Task` propio, envuelto en `asyncio.timeout(timeout)`.
3. Según el tipo: las descargas se hacen todas a la vez con `asyncio.gather`;
   el hash se calcula en otro proceso; la espera es un `asyncio.sleep`.
4. Al terminar queda `completada` (con resultado), `fallida` (con motivo) o
   `cancelada`. Cada cambio de estado se publica en `/eventos`.
5. `GET /tareas/{id}` lee el registro en memoria.

### Estructura

```
tp2/
  app/
    main.py        lifespan (arranque/apagado) y uvicorn
    api.py         endpoints HTTP y validación
    cola.py        Plataforma: cola, workers, cancelación, apagado
    tareas.py      descargar / hashear / esperar
    estado.py      Tarea, registro en memoria, volcado JSON
    config.py      variables de entorno
    eventos.py     WebSocket /eventos
    metricas.py    /estadisticas y /metricas (Prometheus)
  servidor_lento/  servidor de demora para las mediciones
  scripts/         medir_io.py, medir_bloqueo.py, medir_techo.py, resultados.md
  tests/           pytest-asyncio
```

---

## 3. Decisiones de diseño

### ¿Por qué `asyncio.Queue` y no `queue.Queue`?

`queue.Queue` está pensada para **threads**: su `get()` bloquea el hilo que la
llama con un lock del sistema operativo. En una corrutina eso congelaría el
event loop entero (el único hilo del servidor), y con él la API.

`asyncio.Queue.get()` es una corrutina: si la cola está vacía, el worker
**cede el control** con `await` y el event loop sigue atendiendo peticiones.
Además no necesita locks: todo corre en un solo hilo y el event loop solo
cambia de corrutina en un `await`, así que entre un `await` y el siguiente
ninguna otra corrutina puede tocar la cola ni el registro. Por eso el pool de
workers no tiene ningún `Lock`.

La cola es **acotada** (`maxsize=MAX_COLA`) y el `POST` usa `put_nowait`: si
está llena se responde `429` al instante, en vez de bloquear la petición o
crecer sin límite (*backpressure* explícito).

### ¿Cómo evitás que una tarea CPU-bound congele la API?

El event loop es un solo hilo. Una función que hace cálculo puro (un `for`
con SHA-256) nunca llega a un `await`, entonces no le devuelve el control al
loop hasta terminar: durante ese tiempo no se atiende ninguna petición. Eso es
exactamente lo que muestra la medición 2 en modo `bloqueante` (un `GET` tardó
**7,8 s** en vez de 3 ms).

La solución es `loop.run_in_executor(ProcessPoolExecutor, hashear_bloque, ...)`:
el cálculo corre en **otro proceso** y el worker espera el resultado con
`await`, liberando el loop.

Se eligió **procesos y no threads** por el GIL: con `ThreadPoolExecutor` el
loop tampoco se bloquearía del todo, pero los hilos de Python compiten por el
GIL con el propio event loop y no hay paralelismo real de CPU entre varias
tareas `hashear`. Con procesos cada hash usa su propio núcleo e intérprete.

`hashear_bloque` está definida a **nivel de módulo** porque el
`ProcessPoolExecutor` serializa (pickle) la función para mandarla al proceso
hijo, y con el método `spawn` (macOS/Windows) el hijo reimporta el módulo; por
eso también el arranque está protegido con `if __name__ == "__main__":`.

### ¿Cómo implementaste la cancelación, y qué pasa con los recursos a medio usar?

Cada tarea en ejecución corre en **su propio `asyncio.Task`**, guardado en
`plataforma.en_ejecucion`. `DELETE /tareas/{id}`:

- si está `pendiente`: se marca `cancelada`; el worker la descarta al sacarla
  de la cola;
- si está `ejecutando`: se llama `task.cancel()`, que lanza `CancelledError`
  **en el próximo `await`** de la tarea. `_ejecutar` lo atrapa, marca
  `cancelada` y lo **re-lanza** (la cancelación nunca se traga).

El worker espera a esa tarea interna con `asyncio.wait({interna})`, que no
propaga la cancelación de la tarea interna: así cancelar una tarea no mata al
worker, que sigue consumiendo la cola.

Recursos a medio usar, según el tipo:

- **`descargar`**: el `httpx.AsyncClient` se usa dentro de `async with`. Al
  cancelar, `asyncio.gather` cancela todas las descargas hijas y el `async with`
  cierra las conexiones abiertas. No quedan sockets ni corrutinas huérfanas.
- **`esperar`**: `asyncio.sleep` se cancela al instante.
- **`hashear`**: un cálculo que ya está corriendo en otro proceso **no se puede
  interrumpir** (`future.cancel()` solo sirve si aún no empezó). Por eso el hash
  se parte en **bloques de 200.000 iteraciones**, con un `await` entre bloque y
  bloque: la cancelación entra en ese `await`, la tarea queda `cancelada` de
  inmediato y el bloque que ya estaba en el proceso termina solo (a lo sumo
  una fracción de segundo de CPU desperdiciada) y su resultado se descarta. No
  se mata ningún proceso, así que el pool sigue sano.

Los **timeouts** usan el mismo mecanismo: `asyncio.timeout(t)` cancela la tarea
al vencer y convierte la cancelación en `TimeoutError`, que se registra como
`fallida` con el motivo `timeout: superó t segundos`.

### ¿Qué pasa si un worker lanza una excepción no capturada?

No llega a pasar: `_ejecutar` atrapa cualquier `Exception` de la tarea, la
registra en el log con su traceback, marca la tarea `fallida` con el tipo y el
mensaje del error, y el worker vuelve al `while True` a tomar la siguiente. Un
`try/finally` asegura que siempre se haga `cola.task_done()` y se descuente el
contador de workers ocupados.

Si no existiera ese `try`, la excepción terminaría la corrutina worker: el
`asyncio.Task` quedaría con la excepción guardada (Python solo avisaría con
"Task exception was never retrieved" al recolectarlo), el pool perdería un
worker en silencio y, con todos muertos, las tareas quedarían `pendiente`
para siempre. Hay un test que lo verifica (`test_worker_sobrevive_a_excepcion`).

### Otras decisiones

- **`httpx` y no `aiohttp`**: API casi idéntica a `requests`, timeouts claros,
  y el mismo cliente sirve para los tests (`ASGITransport`) y los scripts de
  medición. `aiohttp` es algo más rápido, pero no hace diferencia a esta escala.
- **Señales vía `lifespan`**: uvicorn instala los manejadores de SIGINT/SIGTERM
  y, al recibirlos, ejecuta la parte de apagado del `lifespan` de FastAPI. Ahí
  se hace todo el apagado ordenado. Funciona igual en Linux, en Docker y en
  Windows (donde `loop.add_signal_handler` no existe).
- **Un solo proceso de uvicorn**: el estado vive en memoria; con varios
  procesos cada uno tendría su propio registro.
- **Servicio `lento`**: medir contra internet da números que dependen de la
  conexión; un servidor con demora fija hace la medición reproducible.

---

## 4. Mediciones

Entorno: Docker Desktop (motor Linux) en Windows 10, 8 CPU lógicas
(`os.cpu_count()` = 8 en el host y en el contenedor). Salidas completas en
[`scripts/resultados.md`](scripts/resultados.md). Cada experimento se corrió
una vez.

### 4.1 Concurrencia I/O — `scripts/medir_io.py`

20 descargas de `http://lento:8001/demora?ms=500` (cada una tarda 0,5 s).

| Modo | Tiempo total |
|------|-------------:|
| Secuencial (20 tareas de 1 URL, una tras otra) | 12,15 s |
| Concurrente (1 tarea de 20 URLs, `gather`) | 0,66 s |
| **Speedup** | **18,5×** |

Referencia directa desde el script: `for` con `await` 10,07 s contra
`asyncio.gather` 0,55 s (18,2×).

**Interpretación**: lo concurrente tarda lo que la descarga más lenta (~0,5 s)
más un poco de overhead, no la suma (20 × 0,5 = 10 s). Mientras una descarga
espera la respuesta, el event loop avanza las demás: el tiempo de espera de red
se superpone. El secuencial suma además ~2 s de overhead de crear 20 tareas y
consultarlas por HTTP. Esta es la diferencia entre un `for` con `await` (espera
a cada una antes de lanzar la siguiente) y `asyncio.gather` (lanza todas y
espera el conjunto).

### 4.2 El event loop bloqueado — `scripts/medir_bloqueo.py`

Un `hashear` de 20.000.000 de iteraciones (~7,9 s) mientras el cliente hace
`GET /tareas` cada 100 ms.

| Modo | Muestras | Promedio | p50 | Máximo |
|------|---------:|---------:|----:|-------:|
| Sin carga (línea base) | — | 3,8 ms | — | — |
| `MODO_CPU=executor` | 80 | 3,4 ms | 3,3 ms | 5,5 ms |
| `MODO_CPU=bloqueante` | 7 | 1116 ms | 4,3 ms | **7790 ms** |

**Interpretación**: con executor la API ni se entera de que hay un hash
corriendo (latencia igual a la línea base). Sin executor, durante casi 8 s el
servidor **no respondió nada**: en 8 s solo se completaron 7 peticiones, y la
que llegó durante el hash esperó hasta que terminó (~7,8 s, unas 2.000 veces la
latencia normal). No es que la API "ande lenta": el único hilo está ocupado
calculando y nadie atiende el socket. Ese es el punto de la materia: asyncio es
concurrencia **cooperativa**, y el código CPU-bound no coopera.

### 4.3 Techo del pool — `scripts/medir_techo.py`

**`esperar(1 s)`, N tareas lanzadas a la vez:**

| N | WORKERS=4 | WORKERS=16 |
|--:|----------:|-----------:|
| 4 | 1,10 s | 1,1 s |
| 8 | 2,07 s | 1,1 s |
| 16 | 4,09 s | 1,1 s |
| 32 | 8,08 s | 2,09 s |
| 64 | 16,0 s | 4,14 s |

Espera promedio en cola con N=64: 7,46 s (W=4) contra 1,50 s (W=16).

**`descargar` (10 URLs de 0,5 s), N tareas:**

| N | WORKERS=4 | WORKERS=16 |
|--:|----------:|-----------:|
| 1 | 0,61 s | 0,69 s |
| 4 | 0,62 s | 0,70 s |
| 16 | 2,26 s | 1,05 s |
| 64 | 9,03 s | 5,19 s |

**`hashear` (2.000.000 iteraciones), N tareas, WORKERS=16:**

| N | 1 | 2 | 4 | 8 | 16 |
|---|--:|--:|--:|--:|---:|
| Tiempo | 0,89 s | 1,05 s | 1,34 s | 3,31 s | 13,16 s |

**Interpretación**: hay dos techos distintos.

- Para **I/O** (`esperar`, `descargar`) el límite es la **cantidad de workers**:
  cada tarea ocupa un worker de principio a fin aunque esté solo esperando, así
  que el tiempo total es ≈ ⌈N / WORKERS⌉ × duración. Con 4 workers el codo está
  en N=4; con 16, en N=16. El event loop no es el cuello de botella: podría
  sostener miles de esperas, pero el pool solo deja pasar `WORKERS` a la vez.
  Subir `WORKERS` mueve el techo casi gratis (cada worker es una corrutina, unos
  KB de memoria).
- Para **CPU** (`hashear`) el límite son los **núcleos**: con `WORKERS=16` no
  hay espera en cola, pero el `ProcessPoolExecutor` tiene 8 procesos y la CPU
  es finita. Hasta N≈4 el tiempo casi no crece; desde ahí se degrada. Subir
  `WORKERS` acá no ayuda.

Dos números que **no quedan explicados** por estas mediciones (se reportan tal
cual):

- `hashear` se degrada más que linealmente de N=8 a N=16 (3,3 s → 13,2 s, ×4
  para ×2 tareas). La hipótesis es que las 8 CPU lógicas son 4 núcleos físicos
  con hyperthreading, más el límite de CPU de la VM de Docker Desktop, pero no
  se verificó.
- `descargar` con N=64 y W=16 tarda 5,19 s contra ~2,5 s esperables. No se
  investigó; podría ser el servidor `lento` (un solo proceso) saturado con 160
  conexiones simultáneas.

---

## 5. Conceptos del curso aplicados

| Parte del código | Concepto | Clase |
|------------------|----------|-------|
| `Plataforma._worker` consume de una `asyncio.Queue` compartida | Productor-consumidor, igual que con threads pero con corrutinas: no hace falta lock porque el event loop no interrumpe entre `await`s | 11 (sincronización), 21 |
| Todo el servidor en un hilo con un event loop | El event loop es un `select`/`epoll` sobre los sockets: atiende al que está listo | 17 (I/O multiplexing), 18 |
| `async def` / `await` en workers y tareas | Corrutinas como evolución de los generadores (`yield` → `send()` → `await`); `await` es el punto donde se cede el control | 18 |
| `descargar` con `asyncio.gather` | Concurrencia de I/O sobre sockets TCP sin threads | 13-14 (sockets), 20 |
| `hashear` en `ProcessPoolExecutor` con `run_in_executor` | `concurrent.futures`, futures y procesos para CPU-bound | 8-9 (multiprocessing), 22 |
| Elegir procesos y no threads para el hash | El GIL impide paralelismo de CPU entre threads | 10 (threading) |
| `asyncio.timeout`, `task.cancel()`, `CancelledError` | Cancelación cooperativa y timeouts | 21 |
| Apagado con SIGTERM/SIGINT vía `lifespan` | Señales y terminación ordenada de procesos | 6 (señales) |
| API REST, códigos 202/404/409/422/429/503, WebSocket | HTTP y FastAPI | 19 |
| `Dockerfile` en forma exec (python es PID 1) | Contenedores; PID 1 recibe el SIGTERM de `docker stop` | 1-2 (Docker) |

---

## 6. Limitaciones conocidas

- **El registro crece sin límite**: las tareas terminadas nunca se borran de
  memoria. Con muchas tareas grandes (resultados de `descargar` con muchas
  URLs), la memoria es lo primero que se agota. La cola acotada limita las
  pendientes, no las terminadas.
- **Sin persistencia real**: el volcado JSON solo se informa al arrancar, no se
  restaura. Si el proceso muere con `SIGKILL` no hay volcado.
- **Una tarea de I/O ocupa un worker entero** aunque solo espere. Con
  `WORKERS=4` y 4 descargas lentas, todo lo demás espera en la cola.
- **`hashear` cancelada desperdicia hasta un bloque de CPU** (el bloque que ya
  estaba en el proceso termina igual).
- **El `503` durante el apagado casi nunca se ve**: uvicorn cierra el socket de
  escucha *antes* de ejecutar el apagado del `lifespan`, así que una petición
  nueva recibe "conexión rechazada". El `503` solo cubre peticiones que ya
  estaban dentro.
- **Un WebSocket abierto demora el apagado**: uvicorn espera a las conexiones
  abiertas (hasta `GRACIA_APAGADO + 5` s) antes de correr el `lifespan`, y el
  cierre de los WebSocket ocurre recién ahí.
- **`stop_grace_period` es fijo (30 s)** en `docker-compose.yml`: si se sube
  `GRACIA_APAGADO` por encima de ~10 s hay que subirlo también, o Docker mata el
  proceso con SIGKILL antes del volcado.
- **Sin autenticación ni rate limiting por cliente.**
- **Un solo proceso de API**: no escala horizontalmente porque el estado está en
  memoria.

---

## 7. Lo que aprendí

<!--
Escribir 2-3 párrafos personales. Preguntas guía:
- ¿Qué entendiste del event loop que antes no tenías claro?
- ¿Qué te sorprendió de las mediciones (el GET de 7,8 s, el speedup de 18×)?
- ¿Qué fue lo más difícil: la cancelación, el apagado, distinguir I/O de CPU?
- ¿Qué harías distinto si lo empezaras de nuevo?
-->

*(pendiente)*
