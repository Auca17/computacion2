# Monitor de Procesos y Threads — TP Nº 1

**Computación II — Universidad de Mendoza — 2026**

---

## Descripción general

Monitor de sistema en tiempo real para Linux, similar a `htop`, que inspecciona la **anatomía interna** de cada proceso y sus threads. Toda la información se extrae leyendo `/proc` directamente (sin `psutil` ni herramientas equivalentes).

El monitor es un **sistema multiproceso**: 7 analizadores independientes recolectan datos en paralelo, cada uno con su propio ritmo de refresco. Un snapshot global en memoria compartida (`Manager dict`) centraliza los resultados, y una interfaz de texto (TUI) basada en `curses` renderiza los datos con 7 vistas alternables.

### Cómo se usa

```bash
# Clonar y levantar
git clone <repo-url>
cd tp1
docker compose up --build
```

El contenedor se inicia en modo interactivo. La TUI aparece de inmediato con la vista Resumen activa.

### Keybindings

| Tecla | Acción |
|-------|--------|
| `1`–`7` o `r/m/f/t/s/p/g` | Cambiar de vista |
| `↑` `↓` | Navegar por la lista de procesos |
| `Enter` | Pin/unpin del proceso seleccionado |
| `/` | Filtrar por nombre de comando |
| `u` | Filtrar por usuario |
| `c` | Toggle ordenamiento (CPU% / RSS / PID) |
| `+` / `-` | Ajustar intervalo de la vista activa |
| `q` | Salir limpiamente |
| `h` / `?` | Ayuda |

### Señales del monitor

```bash
# Desde otra terminal (obtener PID del monitor con docker top)
kill -SIGHUP <pid>    # Recarga config.json
kill -SIGUSR1 <pid>   # Dump snapshot a dump_<timestamp>.json
kill -SIGUSR2 <pid>   # Toggle modo verbose
kill -SIGINT <pid>    # Shutdown limpio (equivale a Ctrl+C)
kill -SIGTERM <pid>   # Shutdown limpio
```

---

## Diagrama de arquitectura

```
       ┌──────────────────────────────────────┐
       │           SNAPSHOT GLOBAL            │
       │      (Manager dict compartido)       │
       │  ┌─────────────────────────────────┐ │
       │  │ "resumen"   : {...}  ts: ...    │ │
       │  │ "memoria"   : {...}  ts: ...    │ │
       │  │ "fds"       : {...}  ts: ...    │ │
       │  │ "threads"   : {...}  ts: ...    │ │
       │  │ "senales"   : {...}  ts: ...    │ │
       │  │ "scheduling": {...}  ts: ...    │ │
       │  │ "sistema"   : {...}  ts: ...    │ │
       │  └─────────────────────────────────┘ │
       └────────▲─────────────────────▲───────┘
                │ escriben            │ lee
   ┌────────────┼─────────┬──────────┴────────┐
   │            │         │                    │
┌──▼──────┐ ┌───▼─────┐ ┌─▼──────┐  ...  ┌────▼─────┐
│Resumen  │ │Memoria  │ │FDs     │       │ Display  │
│cada 2s  │ │cada 3s  │ │cada 5s │       │ TUI      │
└─────────┘ └─────────┘ └────────┘       │ (curses) │
                                          └──────────┘
   7 analizadores (Process),
   cada uno con su propio ritmo

   Intervalos ajustables via
   multiprocessing.Value('d')
```

### Flujo de datos

1. Cada **analizador** (proceso independiente, `daemon=True`) ejecuta un loop infinito:
   - Lee datos de `/proc` usando funciones de `procfs.py`
   - Escribe los resultados en `snapshot[clave]` (Manager dict)
   - Duerme `interval.value` segundos (ajustable en tiempo real)

2. El **Display** (proceso principal, curses) lee del snapshot y renderiza.

3. El **SignalHandler** usa el patrón **self-pipe** con `signal.set_wakeup_fd()` para manejar señales de forma async-signal-safe.

---

## Decisiones de diseño

### ¿Por qué `Manager.dict()` y no `Value`/`Array`?

El snapshot contiene datos heterogéneos y anidados (dicts de dicts, listas de dicts, strings, floats). `Value` y `Array` solo soportan tipos C primitivos — no podrían almacenar la estructura compleja del snapshot. `Manager.dict()` serializa automáticamente objetos Python arbitrarios vía Proxy, lo que permite:

- Cada analizador escriba un dict completo atómicamente: `snapshot["resumen"] = {"data": {...}, "ts": ...}`
- El display lea cualquier clave sin conocer la estructura interna de antemano
- Los datos anidados (segmentos de memoria, listas de FDs, señales decodificadas) se transporten sin problemas

El tradeoff es performance: cada lectura/escritura pasa por un socket Unix al proceso Manager. Para un monitor con ciclos de 2-10 segundos, esto es irrelevante.

**Sí usamos `Value` para los intervalos** (`multiprocessing.Value('d', 2.0)`), porque son un único float que el display ajusta con `+`/`-` y el analizador lee en cada ciclo. Aquí `Value` es perfecto: tipo primitivo, acceso rápido, sin overhead de serialización.

### ¿Por qué `curses` y no `rich`?

- **Control total sobre el terminal**: `curses` permite posicionar el cursor, manejar input no bloqueante (`halfdelay`), usar pads para scroll, y responder a `KEY_RESIZE`. `rich` está diseñado para output estático/semi-estático, no para TUIs interactivas con navegación.
- **Sin dependencias externas**: `curses` es parte de la stdlib de Python en Linux. El `requirements.txt` queda vacío.
- **Educativo**: `htop`, `top`, `vim` — todos usan ncurses. Aprender `curses` conecta directamente con cómo funcionan las herramientas de sistema reales.

### ¿Cómo se manejan las race conditions?

1. **Escritura atómica al snapshot**: Cada analizador escribe `snapshot[clave] = {...}` como una asignación única. El Manager Proxy serializa esta operación, garantizando que el display nunca lee un dict a medio escribir.

2. **Procesos que desaparecen**: Los procesos de Linux pueden terminar entre la lectura de `/proc/<pid>/stat` y `/proc/<pid>/status`. Todos los analizadores envuelven la recolección por PID en `try/except` — si un proceso desaparece, simplemente se omite del resultado.

3. **Intervalos compartidos**: Los `Value('d')` se leen/escriben atómicamente por hardware (un double de 64 bits, alineado). No necesitan lock explícito.

4. **Shutdown coordinado**: Un `multiprocessing.Event` (`stop_event`) se comparte con todos los procesos. Cuando el display sale o llega SIGINT/SIGTERM, se setea el evento y los analizadores terminan limpiamente en su próximo ciclo.

### ¿Por qué los intervalos elegidos por defecto?

| Vista | Intervalo | Justificación |
|-------|-----------|---------------|
| Resumen | 2s | CPU% y estados cambian frecuentemente; 2s es buen balance |
| Memoria | 3s | Las métricas de memoria cambian más lento que CPU |
| FDs | 5s | Los FDs abiertos raramente cambian segundo a segundo |
| Threads | 2s | El CPU% por thread necesita resolución temporal similar al resumen |
| Señales | 10s | Las máscaras de señales casi nunca cambian |
| Scheduling | 10s | Nice/priority/policy son casi estáticos |
| Sistema | 2s | El CPU global y load cambian frecuentemente |

### ¿Por qué el patrón self-pipe para señales?

Los signal handlers de Python son limitados: solo pueden setear flags o escribir a un pipe. No pueden llamar funciones complejas como serializar JSON o leer archivos. El patrón self-pipe (`signal.set_wakeup_fd`) permite:

1. El handler solo hace `self._received_signals.append(signum)` — mínimo y seguro.
2. El byte de wakeup se escribe automáticamente al pipe.
3. El loop principal drena el pipe y procesa las señales fuera del contexto del handler. Esto es exactamente lo que dice la documentación de `signal.set_wakeup_fd()` y lo que vimos en clase 6.
4. **Integración con el Display y refresco en caliente**: El `SignalHandler` está enlazado directamente al objeto `Display` que corre en el hilo principal. El loop de curses procesa señales pendientes en cada iteración. Al recibir `SIGHUP`, se recargan de inmediato los intervalos y los filtros de comando/usuario configurados en `config.json`. Al recibir `SIGUSR2`, se conmuta el modo verbose, lo que de inmediato expande la lista de FDs visibles (mostrando la lista completa en lugar de los 5 por defecto) y muestra `(VERBOSE)` en la barra superior.

---

## Conceptos del curso aplicados

### Clase 3 — Procesos: Fundamentos y `/proc`

Todo el módulo `procfs.py` implementa la lectura directa de `/proc`. Por ejemplo, para obtener el estado de un proceso leemos `/proc/<pid>/stat` y parseamos el campo 3 (R=Running, S=Sleeping, D=Disk Sleep, T=Stopped, Z=Zombie). Esto conecta directamente con la anatomía de un proceso vista en clase: cada carpeta numérica en `/proc` es un proceso vivo, y sus archivos son la ventana del kernel al userspace.

### Clase 4 — fork, exec, wait (zombies)

En la vista Sistema, detectamos procesos zombie contando cuántos tienen estado `Z` en `/proc/<pid>/stat`. Un zombie es un proceso que terminó (`exit()`) pero cuyo padre no llamó a `wait()` — el kernel mantiene la entrada en la tabla de procesos para que el padre pueda leer el exit status. El monitor muestra el conteo de zombies en la vista global como indicador de procesos huérfanos o padres que no hacen `wait()`.

### Clase 5 — Pipes y File Descriptors

La vista FDs lista todos los file descriptors abiertos de un proceso leyendo los symlinks de `/proc/<pid>/fd/`. Cada FD es un número que apunta a un recurso (archivo, socket, pipe, TTY). Usamos `os.readlink()` para resolver el destino y clasificamos el tipo. Esto es exactamente la tabla de FDs del proceso que vimos en clase.

### Clase 6 — Señales

Dos aspectos:

1. **Lectura de señales de los procesos monitoreados**: La vista Señales decodifica las máscaras hexadecimales de 64 bits de `/proc/<pid>/status` (SigBlk, SigIgn, SigCgt, SigPnd, ShdPnd). Cada bit representa una señal — bit 0 = señal 1 (SIGHUP), bit 1 = señal 2 (SIGINT), etc. `decode_signal_mask()` convierte esto a nombres legibles.

2. **Manejo de señales del monitor**: Usamos `signal.set_wakeup_fd()` (patrón self-pipe de clase 6) para que SIGINT/SIGTERM hagan shutdown limpio, SIGHUP recargue configuración, SIGUSR1 haga dump, y SIGUSR2 toggle verbose.

### Clase 7 — mmap y memoria compartida

El snapshot global usa `multiprocessing.Manager().dict()` — memoria compartida gestionada. El Manager crea un proceso servidor que mantiene el dict real; los demás procesos acceden vía proxies que se comunican por socket Unix. Esto es más flexible que `mmap` directo porque soporta objetos Python complejos, aunque con mayor overhead. Para los intervalos usamos `Value('d')` que sí usa memoria compartida directa (mmap bajo el capó).

### Clase 8-9 — Multiprocessing

Los 7 analizadores son `multiprocessing.Process` con `daemon=True`. Cada uno corre en su propio proceso con su propio espacio de memoria, PID, y ciclo de vida. La comunicación es via `Manager.dict()` (clase 9) y `multiprocessing.Value` para los intervalos. El `stop_event` (`multiprocessing.Event`) coordina el shutdown.

### Clase 10 — Threading y GIL

La vista Threads muestra los LWPs (Light Weight Processes) de cada proceso, leídos de `/proc/<pid>/task/`. En Linux, cada thread es un LWP con su propio TID visible en `/proc`. El display no usa threads para la recolección (la arquitectura es multiproceso), pero el GIL de Python es la razón por la que no usamos threads para el trabajo pesado — los analizadores necesitan paralelismo real (CPU-bound parseo de `/proc`), no concurrencia (I/O-bound).

---

## Limitaciones conocidas

1. **No hay persistencia de FD symlinks en mock**: Los tests no pueden crear symlinks reales en todos los OS, por lo que `list_fds()` no se testea con fixtures estáticas sino que se valida en runtime sobre Linux real.

2. **CPU% en la primera iteración**: La primera lectura de CPU% siempre da 0% porque no hay deltas previos. A partir del segundo ciclo los valores son correctos.

3. **Procesos efímeros**: Un proceso que aparece y desaparece entre dos ciclos de un analizador nunca será visible. Esto es inherente al modelo de polling.

4. **Resolución de UID a username**: Usa `pwd.getpwuid()` que puede no resolver UIDs de usuarios en namespaces de contenedores. Fallback a mostrar el número.

5. **Escalabilidad**: Con miles de procesos, los analizadores que recorren todos los PIDs (resumen, memoria) toman más tiempo. No hay paginación ni límite — se procesan todos.

6. **Proceso Manager como SPOF**: Si el proceso Manager de `multiprocessing` muere, todo el sistema pierde el snapshot. No hay recovery automático.

---

## Cómo correr y testear

### Requisitos

- Docker y Docker Compose instalados

### Levantar

```bash
docker compose up --build
```

El monitor arranca automáticamente en la terminal interactiva.

### Señales (desde otra terminal)

```bash
# Obtener el PID del proceso monitor dentro del contenedor
docker compose exec monitor ps aux | grep main.py

# Enviar señales
docker compose exec monitor kill -SIGUSR1 <pid>   # Dump snapshot
docker compose exec monitor kill -SIGHUP <pid>     # Reload config
docker compose exec monitor kill -SIGUSR2 <pid>    # Toggle verbose
```

### Configuración

Editar `config.json` antes de levantar, o enviar SIGHUP para recargar en caliente:

```json
{
    "intervalos": {
        "resumen": 2.0,
        "memoria": 3.0,
        "fds": 5.0,
        "threads": 2.0,
        "senales": 10.0,
        "scheduling": 10.0,
        "sistema": 2.0
    },
    "filtros": {
        "usuario": null,
        "comando": null
    },
    "verbose": false
}
```

---

## Estructura del repositorio

```
tp1/
├── README.md                 ← este archivo
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── config.json               ← configuración (intervalos, filtros)
└── src/
    ├── main.py               ← entry point y orquestador
    ├── procfs.py             ← helpers para parsear /proc
    ├── recolector.py         ← utilidad para listar PIDs
    ├── display.py            ← TUI con curses (7 vistas)
    ├── senales.py            ← handlers de señales del monitor
    └── analizadores/
        ├── resumen.py        ← PID, estado, CPU%, RSS, comando
        ├── memoria.py        ← VmSize, VmRSS, segments, faults
        ├── fds.py            ← file descriptors abiertos
        ├── threads.py        ← LWPs con CPU% y estado
        ├── senales.py        ← máscaras de señales decodificadas
        ├── scheduling.py     ← nice, priority, policy, affinity
        └── sistema.py        ← CPU global, memoria, load, totales
```

---

## Decisiones sobre la TUI

Elegí `curses` sobre `rich` por tres razones:

1. **Interactividad nativa**: `curses` maneja input de teclado (incluyendo teclas especiales como flechas, Enter, resize) de forma integrada con `halfdelay(5)` para un loop de 500ms. Con `rich` habría que agregar `prompt_toolkit` o un thread separado para capturar input.

2. **Layout preciso**: El monitor tiene tres zonas (header, lista de procesos, panel de detalle) que necesitan posicionamiento absoluto. `curses` con `addnstr()` y control de filas/columnas es la herramienta correcta.

3. **Colores**: 7 pares de colores definidos para header (blanco sobre azul), fila seleccionada (negro sobre cyan), proceso pinneado (negro sobre amarillo), alertas (rojo), valores positivos (verde), y títulos (amarillo).

---

## Lo que aprendí

Antes de este TP, `/proc` era una carpeta más que veía cuando navegaba el filesystem de Linux. Después de pasar semanas leyendo `stat`, `status`, `maps`, `fd/` y `task/` para cada proceso del sistema, entiendo que `/proc` es literalmente la ventana del kernel hacia el userspace — una API en forma de filesystem que te deja inspeccionar en tiempo real todo lo que el sistema operativo sabe sobre un proceso. Lo que más me sorprendió fue que los archivos de `/proc` no existen en disco: el kernel los genera al momento de la lectura. Por eso `ls -l` muestra tamaño 0 pero `cat` devuelve contenido.

La parte más difícil fue diseñar la comunicación entre los 7 analizadores y el display. Empecé queriendo usar pipes para todo (como en clase 5), pero rápidamente me di cuenta de que cuando tenés 7 productores y un consumidor que necesita acceso aleatorio a los datos de cualquiera de ellos, un `Manager.dict()` es mucho más natural. Aprendí que cada mecanismo de IPC tiene su lugar: pipes para streams, `Value` para datos simples de alta frecuencia, y `Manager` para estructuras complejas donde la comodidad vale más que los microsegundos de overhead. No hay un "mejor" mecanismo — hay tradeoffs.

Lo otro que me quedó grabado es la importancia de async-signal-safety. Cuando un signal handler puede interrumpir tu código en CUALQUIER punto, hacer un `print()` inocente adentro puede causar un deadlock si justo interrumpiste otro `print()` que tenía el lock de stdout. El patrón self-pipe me pareció elegante: reducís el handler a lo mínimo (setear un flag o escribir un byte), y movés toda la lógica real al loop principal donde es seguro hacer lo que quieras.

---
