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
| `PROCESOS_CPU` | `os.cpu_count()` | Procesos del `ProcessPoolExecutor` |
| `MAX_CONEXIONES` | `20` | Conexiones simultáneas por tarea en `descargar`/`sondear` (`Semaphore`) |
| `ENVEJECIMIENTO_S` | `5` | Cada cuántos segundos de espera una tarea "sube" un nivel de prioridad (bonus) |
| `BACKOFF_BASE` | `1` | Base (s) del backoff exponencial de reintentos (bonus) |
| `RATE_LIMIT_POR_SEG` / `RATE_LIMIT_RAFAGA` | `20` / `40` | Tasa y ráfaga de `POST` por cliente (bonus) |

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

Cuerpo del `POST`: `tipo` (`descargar`, `hashear`, `esperar` o `sondear`),
`parametros`, y opcionales `timeout` (s), `prioridad` (1 = más alta … 10,
defecto 5) y `reintentos` (0–5, defecto 0).

Códigos de error: `404` id inexistente, `409` cancelar una tarea ya terminada,
`422` cuerpo inválido, `429` cola llena o límite de tasa del cliente (con
`Retry-After`), `503` la plataforma se está apagando.

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

# Tarea propia: sondear puertos TCP (bonus)
curl -X POST localhost:8000/tareas -H 'Content-Type: application/json' \
  -d '{"tipo":"sondear","parametros":{"host":"lento","puertos":[8001,22,80]}}'

# Prioridad alta y hasta 3 reintentos con backoff (bonus)
curl -X POST localhost:8000/tareas -H 'Content-Type: application/json' \
  -d '{"tipo":"descargar","parametros":{"urls":["http://noexiste.invalid"]},"prioridad":1,"reintentos":3}'

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
python -m pytest -q        # 37 tests, ~6 s
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
  │  descargar ─► httpx + TaskGroup + Semaphore   │
  │  sondear   ─► open_connection + TaskGroup     │
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
3. Según el tipo: las descargas se hacen a la vez en un `asyncio.TaskGroup`
   (hasta `MAX_CONEXIONES` simultáneas); el hash se calcula en otro proceso;
   la espera es un `asyncio.sleep`.
4. Al terminar queda `completada` (con resultado), `fallida` (con motivo) o
   `cancelada`. Si falló y le quedan reintentos, vuelve a `pendiente` y se
   reencola tras un backoff exponencial. Cada cambio de estado se publica en
   `/eventos`.
5. `GET /tareas/{id}` lee el registro en memoria.

### Estructura

```
tp2/
  app/
    main.py        lifespan (arranque/apagado) y uvicorn
    api.py         endpoints HTTP y validación
    cola.py        ColaConPrioridad y Plataforma: workers, cancelación,
                   reintentos, apagado
    tareas.py      descargar / hashear / esperar / sondear
    limite.py      rate limiting por cliente (cubeta de tokens)
    estado.py      Tarea, registro en memoria, volcado JSON
    config.py      variables de entorno
    eventos.py     WebSocket /eventos
    metricas.py    /estadisticas y /metricas (Prometheus)
  servidor_lento/  servidor de demora para las mediciones
  celery_app/      el pool reimplementado con Celery (bonus, profile "celery")
  scripts/         medir_io.py, medir_bloqueo.py, medir_techo.py, resultados.md,
                   comparar_celery.py, resultados_celery.md
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
  cancelar la tarea, el `asyncio.TaskGroup` cancela todas las descargas hijas
  y **espera a que terminen** antes de salir del bloque (concurrencia
  estructurada, clase 21), y el `async with` del cliente cierra las conexiones
  abiertas. No quedan sockets ni corrutinas huérfanas. Se eligió `TaskGroup` y
  no `gather` justamente por eso: con `gather`, si una hija lanza una excepción
  las hermanas siguen corriendo sueltas. Además cada descarga atrapa sus
  propios errores (una URL caída es una entrada de error, no un fallo de la
  tarea), y un `Semaphore(MAX_CONEXIONES)` limita las conexiones simultáneas
  (clase 20).
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

> Esta medición se tomó cuando `descargar` usaba `asyncio.gather`; hoy usa
> `TaskGroup` con `Semaphore(20)`. Con 20 URLs y un límite de 20 conexiones el
> comportamiento es el mismo (todas a la vez). La comparación con Celery
> (sección 8), tomada después del cambio, dio 0,65 s para el mismo caso.

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
| `Plataforma._worker` consume de una `asyncio.Queue` compartida | Productor-consumidor, igual que con threads pero con corrutinas: no hace falta lock porque el event loop no interrumpe entre `await`s | 11 (sincronización), 20, 21 |
| Todo el servidor en un hilo con un event loop | El event loop es un `select`/`epoll` sobre los sockets: atiende al que está listo | 17 (I/O multiplexing), 18 |
| `async def` / `await` en workers y tareas | Corrutinas como evolución de los generadores (`yield` → `send()` → `await`); `await` es el punto donde se cede el control | 18 |
| `descargar` con `asyncio.TaskGroup` | Concurrencia de I/O sobre sockets TCP sin threads; concurrencia estructurada | 13-14 (sockets), 20, 21 |
| `Semaphore(MAX_CONEXIONES)` en `descargar`/`sondear` | Limitar cuántas corrutinas usan un recurso a la vez | 20 |
| Tarea `sondear` con `asyncio.open_connection` | Conexión TCP (el `connect()` de sockets) hecha asíncrona; cerrar con `close()` + `wait_closed()` | 13-14, 20 |
| `ColaConPrioridad` hereda de `asyncio.Queue` | Productor-consumidor con prioridad y envejecimiento contra inanición | 11, 21 |
| `LimitadorTasa` sin lock | Estado compartido sin lock: `consumir` no tiene `await`, nada se intercala | 11, 20 |
| `hashear` en `ProcessPoolExecutor` con `run_in_executor` | `concurrent.futures`, futures y procesos para CPU-bound | 8-9 (multiprocessing), 21, 22 |
| Elegir procesos y no threads para el hash | El GIL impide paralelismo de CPU entre threads | 10 (threading) |
| `asyncio.timeout`, `task.cancel()`, `CancelledError` | Cancelación cooperativa y timeouts | 20 |
| `asyncio.Queue(maxsize=...)` + `put_nowait` → `429` | Cola acotada y *backpressure*: rechazar en vez de acumular | 21 |
| Apagado con SIGTERM/SIGINT vía `lifespan` | Señales y terminación ordenada de procesos | 6 (señales), 20, 21 |
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
- **Sin autenticación.** El rate limiting identifica al cliente por IP: detrás
  de un proxy o NAT, muchos clientes comparten la misma cubeta, y las cubetas
  de IPs viejas nunca se borran.
- **Los reintentos no distinguen errores transitorios de permanentes**: un
  tarea que siempre va a fallar (por ejemplo, un `hashear` que excede su
  timeout) se reintenta igual hasta agotar los intentos.
- **Una tarea en backoff no recibe la gracia del apagado**: no está en la cola,
  así que `cola.join()` no la espera y se cancela de inmediato al apagar.
- **El rate limit se aplica antes de validar el cuerpo**: un `POST` inválido
  (`422`) también gasta un token del cliente.
- **Un solo proceso de API**: no escala horizontalmente porque el estado está en
  memoria.

---

## 7. Lo que aprendí

Lo más valioso de este trabajo fue entender que "asíncrono" no significa
"paralelo". Antes pensaba que poner `async` delante de una función ya la hacía
correr en segundo plano. Construyendo la plataforma entendí que hay **un solo
hilo** y que todo depende de que cada corrutina devuelva el control en sus
`await`. La medición del event loop bloqueado fue la que me lo dejó claro: ver
un `GET` simple tardar casi 8 segundos solo porque había un hash corriendo en el
mismo hilo vale más que cualquier explicación teórica.

Usé inteligencia artificial como apoyo durante todo el desarrollo, y me ayudó
mucho a comprender conceptos y a destrabarme en problemas en los que me quedaba
estancado: por qué cancelar una tarea mataba al worker, por qué un cálculo que
ya está en otro proceso no se puede interrumpir, o en qué orden apaga uvicorn
las cosas al recibir una señal. Me sirvió como un tutor al que preguntarle
"¿por qué pasa esto?" hasta entenderlo, y después verificarlo con pruebas y
mediciones propias. Lo que me llevo es saber qué preguntar y poder explicar
cada decisión del código.

En lo técnico, me quedo con estas cosas:

- **Cooperación del event loop**: `time.sleep()` o un cálculo puro congelan todo
  el servidor; `asyncio.sleep()` y la I/O de red ceden el control.
- **I/O-bound vs CPU-bound**: la I/O se resuelve con concurrencia
  (`asyncio.gather` dio un speedup de 18×); la CPU necesita procesos
  (`ProcessPoolExecutor` + `run_in_executor`) por el GIL.
- **Cancelación limpia**: `task.cancel()` actúa en el próximo `await`;
  `CancelledError` se atrapa para registrar el estado y se vuelve a lanzar,
  nunca se traga. Para cancelar un cálculo CPU hubo que partirlo en bloques.
- **`asyncio.wait` vs `await task`**: esperar la tarea interna con
  `asyncio.wait` evita que su cancelación mate al worker.
- **Productor-consumidor sin locks**: una `asyncio.Queue` acotada, con
  `put_nowait` y `429` como *backpressure*; no hace falta `Lock` porque nada
  interrumpe entre dos `await`.
- **Timeouts** con `asyncio.timeout()`, y por qué no funcionan sobre código que
  nunca hace `await`.
- **Apagado ordenado**: señales, el `lifespan` de FastAPI, el PID 1 en Docker
  con `CMD` en forma exec, y `stop_grace_period` para que Docker no mate el
  proceso antes de volcar el estado.
- **Medir en vez de suponer**: el techo del pool resultó ser ⌈N / WORKERS⌉ para
  tareas de I/O y la cantidad de núcleos para las de CPU, dos límites distintos
  que no habría distinguido sin medirlos.

---

## 8. Extensiones opcionales (bonus)

Las ocho extensiones de la consigna están implementadas.

| # | Extensión | Dónde | Cómo se prueba |
|---|-----------|-------|----------------|
| 1 | WebSocket `/eventos` | `app/eventos.py` | `tests/test_eventos_metricas.py` |
| 2 | Prioridades | `app/cola.py` (`ColaConPrioridad`) | `tests/test_bonus.py` |
| 3 | Reintentos con backoff exponencial | `app/cola.py` (`_fallar`, `_reencolar_tras`) | `tests/test_bonus.py` |
| 4 | Rate limiting por cliente | `app/limite.py` | `tests/test_bonus.py` |
| 5 | Métricas Prometheus `/metricas` | `app/metricas.py` | `tests/test_eventos_metricas.py` |
| 6 | Tests con `pytest-asyncio` | `tests/` (37 tests) | `python -m pytest -q` |
| 7 | Celery | `celery_app/`, `scripts/comparar_celery.py` | `scripts/resultados_celery.md` |
| 8 | Tarea propia `sondear` | `app/tareas.py` | `tests/test_bonus.py` |

### 8.1 WebSocket `/eventos`

Cada cliente conectado tiene su propia `asyncio.Queue(maxsize=100)`. Cada
cambio de estado llama a `publicar()`, que hace `put_nowait` en todas: si un
cliente lento tiene el buffer lleno, se le descarta el mensaje. Así un cliente
lento **nunca frena a los workers**. Al apagar, se manda un centinela `None` a
cada cola para cerrar las conexiones.

### 8.2 Prioridades y cómo se evita la inanición

`ColaConPrioridad` hereda de `asyncio.Queue` y redefine solo los métodos
internos `_init`, `_put` y `_get`, igual que lo hace la propia
`asyncio.PriorityQueue` de la biblioteca estándar. Así siguen funcionando sin
cambios `maxsize`, `put_nowait` (y el `429`), `task_done` y `join` (que usa el
apagado).

Con prioridad pura, una tarea de prioridad 10 podría no ejecutarse nunca si
siempre llegan tareas de prioridad 1: eso es **inanición**. Para evitarlo se
usa **envejecimiento**: al sacar de la cola se calcula

```
prioridad_efectiva = prioridad - espera_en_cola / ENVEJECIMIENTO_S
```

Cada `ENVEJECIMIENTO_S` segundos (5 por defecto) de espera, la tarea "sube" un
nivel. Una tarea de prioridad 10 que espera 45 s ya vale como una de prioridad
1 recién llegada, así que su espera máxima está acotada. A igual valor gana la
que llegó antes (FIFO). La búsqueda es lineal (O(n) con n ≤ `MAX_COLA`) porque
la prioridad efectiva cambia con el tiempo y un heap quedaría desordenado.

### 8.3 Reintentos con backoff exponencial

El `POST` acepta `reintentos` (0 a 5). Si una tarea falla (excepción o
timeout, **nunca** una cancelación) y le quedan intentos:

1. vuelve a `pendiente`, guarda el error en `errores` y suma `intentos`;
2. se programa un **temporizador** (`asyncio.create_task`) que duerme
   `BACKOFF_BASE × 2^(intento-1)` segundos (1 s, 2 s, 4 s…) con un ±20 % de
   *jitter* para que muchas tareas que fallaron juntas no reintenten todas en
   el mismo instante;
3. al vencer, la tarea se vuelve a encolar.

El worker **no espera el backoff**: queda libre al instante para otra tarea.
Un `DELETE` durante el backoff cancela el temporizador, y el apagado cancela
todos los temporizadores pendientes. El campo `proximo_intento` dice cuándo se
reintenta, y `/metricas` cuenta `reintentos_programados_total`.

### 8.4 Rate limiting por cliente

Es una **cubeta de tokens** por IP (`app/limite.py`). Cada cliente arranca con
`RATE_LIMIT_RAFAGA` tokens (40), que se recargan a `RATE_LIMIT_POR_SEG` (20)
por segundo, y cada `POST /tareas` gasta uno. Sin tokens, la respuesta es `429`
con la cabecera `Retry-After` (segundos hasta tener un token). Permite ráfagas
cortas pero limita la tasa sostenida. No usa lock: `consumir()` no tiene
`await`, así que nada se intercala a mitad de la cuenta.

### 8.5 Métricas Prometheus

`GET /metricas` devuelve el formato de texto de Prometheus, armado a mano y
sin dependencias. Expone tareas por estado, workers ocupados y totales, tamaño
de la cola, duración promedio por tipo, reintentos programados y rechazos por
límite. Los números salen de la misma función que `/estadisticas`.

### 8.6 Tests

Son 37 tests con `pytest-asyncio`. Hablan con la app por HTTP sin red
(`httpx.ASGITransport`). Cubren:

- API y códigos de error;
- cancelación de tareas pendientes y en ejecución (`esperar`, `hashear`), y que
  el worker sobreviva;
- timeouts y excepciones;
- cola llena (`429`) y apagado (`503` y volcado);
- WebSocket y métricas;
- todos los bonus: orden por prioridad, envejecimiento, reintentos exitosos,
  agotados y cancelados durante el backoff, rate limit, `sondear` y el límite
  de concurrencia del `Semaphore`.

### 8.7 Celery: el pool reimplementado y comparado

`celery_app/tareas.py` implementa las mismas tres tareas como tareas de Celery,
con Redis como broker y como backend de resultados. `hashear` reusa
`hashear_bloque`, así que el resultado es idéntico. Los servicios `redis` y
`celery_worker` están detrás del *profile* `celery`, así que el
`docker compose up --build` obligatorio no cambia:

```bash
docker compose --profile celery up --build -d
MSYS_NO_PATHCONV=1 docker compose --profile celery run --rm --no-deps \
  -e PYTHONPATH=/srv -v ./scripts:/srv/scripts celery_worker \
  python scripts/comparar_celery.py --salida /srv/scripts/resultados_celery.md
```

Las dos versiones se midieron con el mismo paralelismo: 4 workers asyncio
contra 4 procesos de Celery.

| Prueba | API asyncio | Celery |
|--------|------------:|-------:|
| 20 × `esperar(1 s)` | 5,31 s | 5,31 s |
| 8 × `hashear` (~1 s c/u) | 2,60 s | 2,19 s |
| 20 descargas de 0,5 s, en 1 tarea | 0,65 s | 0,63 s |
| 20 descargas de 0,5 s, en 20 tareas | — | 2,90 s |
| Cancelar un `esperar(30)` | 0,02 s (`DELETE`) | 0,01 s (`revoke(terminate=True)`) |
| Latencia de encolar (media) | 10,6 ms (`POST`) | 1,4 ms (`.delay()`) |

**Interpretación**:

- **Cuando el límite es el paralelismo, el framework no importa.** Con 4
  workers contra 4 procesos, las esperas empatan.
- **Para I/O gana la concurrencia dentro de un proceso.** Una tarea con 20
  descargas concurrentes (asyncio) tarda 0,65 s. Las mismas 20 descargas como
  tareas sueltas en Celery tardan 2,90 s, porque cada proceso hace una a la
  vez. Un worker de Celery es un proceso que bloquea mientras espera la red, y
  por eso adentro de una tarea de Celery `time.sleep` es correcto.
- **La cancelación es distinta en el fondo.** Nosotros cancelamos una
  corrutina en su próximo `await` y el worker sigue vivo. Celery con
  `terminate=True` **mata el proceso hijo** con SIGTERM y el pool levanta otro
  (los PID pasaron de [8, 9, 10, 11] a [8, 9, 10, 64]). Es más brusco: lo que
  ese proceso tenía a medio hacer se pierde sin limpieza.
- **Celery encola más barato** (publicar en Redis contra un viaje HTTP con
  validación). A cambio suma dos servicios (Redis y los workers); la ventaja es
  que las tareas quedan en el broker, fuera del proceso que las encoló.
- **Conclusión**: para este TP, asyncio alcanza y es más simple. Celery
  conviene cuando el trabajo tiene que repartirse entre varias máquinas, o
  cuando las tareas tienen que sobrevivir a la caída de la API.

### 8.8 Tarea propia: `sondear`

Chequea puertos TCP de un host de forma concurrente. Para cada puerto intenta
`asyncio.open_connection(host, puerto)` con un timeout: si conecta, informa
`abierto` y la latencia en ms, y cierra la conexión con `close()` +
`wait_closed()`. Si la rechazan o no responde, informa `abierto: false` y el
motivo. Usa el mismo `TaskGroup` + `Semaphore` que `descargar`.

Se eligió porque une las dos mitades del cuatrimestre: es el `connect()` de
los sockets TCP de las clases 13-14, pero asíncrono como en la clase 20.
Además es I/O puro: sondea hasta `MAX_CONEXIONES` puertos a la vez, y cada
tanda tarda lo que el puerto más lento, no la suma.
