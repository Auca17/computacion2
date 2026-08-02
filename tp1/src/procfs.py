"""
procfs.py - Funciones para leer el sistema de archivos /proc de Linux.

Lee los datos de /proc (o la carpeta de prueba).
No usa librerías externas, solo lo básico de Python.
"""

import os
import re
import signal

# ---
# Base path (puede cambiar si usamos Docker o hacemos tests)
PROC_BASE = os.environ.get("PROC_BASE", "/proc")

# ---

# TODO: buscar si hay más campos en /proc/<pid>/stat que nos sirvan después.
# Estos son los campos de stat que necesitamos (el índice cuenta desde 0)
_STAT_FIELDS = {
    0: "pid",
    1: "comm",
    2: "state",
    3: "ppid",
    4: "pgrp",
    5: "session",
    6: "tty_nr",
    7: "tpgid",
    8: "flags",
    9: "minflt",
    10: "cminflt",
    11: "majflt",
    12: "cmajflt",
    13: "utime",
    14: "stime",
    15: "cutime",
    16: "cstime",
    17: "priority",
    18: "nice",
    19: "num_threads",
    21: "starttime",
    39: "rt_priority",
    40: "policy",
}

# Políticas de scheduling (sacadas de sched.h)
SCHED_POLICIES = {
    0: "OTHER",
    1: "FIFO",
    2: "RR",
    3: "BATCH",
    5: "IDLE",
    6: "DEADLINE",
}

# ---
# Funciones básicas
# ---

def read_file(path):
    # Lee un archivo y lo devuelve como texto. Si falla, devuelve string vacío.
    try:
        # errors="replace" para evitar que crashee si hay basura en el archivo
        with open(path, "r", errors="replace") as f:
            return f.read()
    except (OSError, IOError):
        return ""


def _safe_int(value, default=0):
    # Convierte un texto a número, si no puede devuelve 0 por defecto.
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


# Alias público para que otros módulos puedan importarlo
safe_int = _safe_int

# ---


def list_pids(proc_base=None):
    # Busca todas las carpetas en /proc que sean números (los PIDs).
    base = proc_base or PROC_BASE
    pids = []
    try:
        for entry in os.listdir(base):
            if entry.isdigit():
                pids.append(int(entry))
    except OSError:
        pass
    # devuelvo la lista ordenada para que sea más prolijo
    return sorted(pids)


# ---

def parse_stat(pid, proc_base=None):
    # Lee /proc/<pid>/stat y arma un diccionario con los datos.
    base = proc_base or PROC_BASE
    content = read_file(os.path.join(base, str(pid), "stat"))
    if not content:
        return {}
    return _parse_stat_line(content)


def _parse_stat_line(content):
    # Procesa la línea de stat, ojo que el nombre puede tener espacios o paréntesis
    first_paren = content.find("(")
    last_paren = content.rfind(")") # rfind busca desde el final
    if first_paren == -1 or last_paren == -1:
        return {}

    pid_str = content[:first_paren].strip()
    comm = content[first_paren + 1:last_paren]
    # dividimos el resto de los campos por espacio
    rest = content[last_paren + 1:].strip().split()

    fields = [pid_str, comm] + rest
    result = {}
    for idx, name in _STAT_FIELDS.items():
        if idx < len(fields):
            val = fields[idx]
            if name in ("comm", "state"):
                result[name] = val
            else:
                result[name] = _safe_int(val)
    return result


# ---

def parse_status(pid, proc_base=None):
    # Lee /proc/<pid>/status que tiene formato clave: valor.
    base = proc_base or PROC_BASE
    path = os.path.join(base, str(pid), "status")
    return _parse_status_file(path)


def _parse_status_file(path):
    # Función interna que parsea el archivo de status línea por línea
    data = {}
    content = read_file(path)
    for line in content.splitlines():
        parts = line.split(":\t", 1) # separo por :\t para agarrar clave y valor
        if len(parts) == 2:
            data[parts[0].strip()] = parts[1].strip()
    return data


# ---

def parse_cmdline(pid, proc_base=None):
    # Lee el comando con el que se corrió el proceso.
    base = proc_base or PROC_BASE
    content = read_file(os.path.join(base, str(pid), "cmdline"))
    # Los argumentos vienen separados por un byte nulo, los cambio a espacio
    return content.replace("\x00", " ").strip()


# ---

def parse_maps(pid, proc_base=None):
    # Agrupa los segmentos de memoria de un proceso (text, data, heap, etc.).
    base = proc_base or PROC_BASE
    content = read_file(os.path.join(base, str(pid), "maps"))
    segments = {"text": 0, "data": 0, "heap": 0, "stack": 0, "shared": 0, "other": 0}

    for line in content.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        addr_range = parts[0]
        perms = parts[1]
        pathname = parts[5] if len(parts) > 5 else ""

        # calculo el tamaño en KB usando las direcciones en hexa
        try:
            start_hex, end_hex = addr_range.split("-")
            size_bytes = int(end_hex, 16) - int(start_hex, 16)
            size_kb = size_bytes // 1024
        except (ValueError, IndexError):
            continue

        # TODO: revisar si me falta algún otro tipo de segmento
        # Clasifico según el nombre o permisos
        if pathname == "[heap]":
            segments["heap"] += size_kb
        elif pathname == "[stack]" or pathname.startswith("[stack:"):
            segments["stack"] += size_kb
        elif "s" in perms:
            segments["shared"] += size_kb
        elif "x" in perms:
            segments["text"] += size_kb
        elif "w" in perms:
            segments["data"] += size_kb
        else:
            segments["other"] += size_kb

    return segments


# ---

def list_fds(pid, proc_base=None):
    # Lista los archivos y conexiones abiertos por el proceso (file descriptors).
    base = proc_base or PROC_BASE
    fd_dir = os.path.join(base, str(pid), "fd")
    fds = []
    try:
        entries = os.listdir(fd_dir)
    except OSError:
        return fds

    for entry in sorted(entries, key=lambda x: _safe_int(x, 999999)):
        target = ""
        try:
            # leo a dónde apunta el link simbólico
            target = os.readlink(os.path.join(fd_dir, entry))
        except OSError:
            target = "[permission denied]"

        fd_type = _classify_fd(target)
        fds.append({"fd": _safe_int(entry), "target": target, "type": fd_type})

    return fds


def _classify_fd(target):
    # Me dice qué tipo de recurso es según el target (socket, pipe, archivo normal, etc).
    if target.startswith("socket:"):
        return "socket"
    elif target.startswith("pipe:"):
        return "pipe"
    elif "/dev/pts/" in target or "/dev/tty" in target:
        return "tty"
    elif target.startswith("anon_inode:"):
        return "anon_inode"
    elif target.startswith("/") or target.startswith("./"):
        return "file"
    else:
        return "unknown"


# ---
# Threads (hilos)
# ---

def list_threads(pid, proc_base=None):
    # Saca la lista de hilos de la carpeta task del proceso.
    base = proc_base or PROC_BASE
    task_dir = os.path.join(base, str(pid), "task")
    tids = []
    try:
        for entry in os.listdir(task_dir):
            if entry.isdigit():
                tids.append(int(entry))
    except OSError:
        pass
    return sorted(tids)


def parse_thread_stat(pid, tid, proc_base=None):
    # Lee el stat de un hilo en particular. Usa el mismo parser que el del proceso.
    base = proc_base or PROC_BASE
    content = read_file(os.path.join(base, str(pid), "task", str(tid), "stat"))
    if not content:
        return {}
    return _parse_stat_line(content)


def parse_thread_comm(pid, tid, proc_base=None):
    # Nombre del hilo.
    base = proc_base or PROC_BASE
    content = read_file(os.path.join(base, str(pid), "task", str(tid), "comm"))
    return content.strip()


def parse_thread_status(pid, tid, proc_base=None):
    # Status del hilo, igual que en el proceso general.
    base = proc_base or PROC_BASE
    path = os.path.join(base, str(pid), "task", str(tid), "status")
    return _parse_status_file(path)


# ---

def decode_signal_mask(hex_mask):
    # Pasa la máscara de señales (en hexa) a una lista con los nombres.
    # Usa signal.Signals del módulo signal de Python, que conoce todos los
    # números de señal del SO sin necesitar un diccionario hardcodeado.
    try:
        mask = int(hex_mask, 16)
    except (ValueError, TypeError):
        return []

    signals = []
    for bit in range(64):
        if mask & (1 << bit):
            sig_num = bit + 1  # los números de señal arrancan en 1
            try:
                name = signal.Signals(sig_num).name  # ej: 'SIGINT', 'SIGTERM'
            except ValueError:
                # número de señal sin nombre estándar en esta plataforma
                name = f"SIG{sig_num}"
            signals.append(name)
    return signals


# ---

def parse_proc_stat(proc_base=None):
    # Lee datos del CPU de todo el sistema y otras cosas como boot time.
    base = proc_base or PROC_BASE
    content = read_file(os.path.join(base, "stat"))
    result = {"cpu": {}, "btime": 0, "processes": 0}

    for line in content.splitlines():
        if line.startswith("cpu "):
            parts = line.split()
            keys = ["user", "nice", "system", "idle", "iowait",
                    "irq", "softirq", "steal"]
            # agarro cada valor y lo meto en su clave
            for i, key in enumerate(keys):
                result["cpu"][key] = _safe_int(parts[i + 1]) if i + 1 < len(parts) else 0
        elif line.startswith("btime "):
            result["btime"] = _safe_int(line.split()[1])
        elif line.startswith("processes "):
            result["processes"] = _safe_int(line.split()[1])

    return result


# ---

def parse_loadavg(proc_base=None):
    # Parsea la carga promedio de /proc/loadavg.
    base = proc_base or PROC_BASE
    content = read_file(os.path.join(base, "loadavg")).strip()
    parts = content.split()
    result = {"load1": 0.0, "load5": 0.0, "load15": 0.0, "running": 0, "total": 0}
    if len(parts) >= 3:
        try:
            result["load1"] = float(parts[0])
            result["load5"] = float(parts[1])
            result["load15"] = float(parts[2])
        except ValueError:
            pass
    if len(parts) >= 4:
        run_total = parts[3].split("/")
        if len(run_total) == 2:
            result["running"] = _safe_int(run_total[0])
            result["total"] = _safe_int(run_total[1])
    return result


# ---

def parse_meminfo(proc_base=None):
    # Diccionario con el uso de RAM sacado de meminfo (en KB).
    base = proc_base or PROC_BASE
    content = read_file(os.path.join(base, "meminfo"))
    result = {}
    for line in content.splitlines():
        parts = line.split(":")
        if len(parts) == 2:
            key = parts[0].strip()
            val_parts = parts[1].strip().split()
            result[key] = _safe_int(val_parts[0]) if val_parts else 0
    return result


# ---

def parse_uptime(proc_base=None):
    # Cuánto tiempo lleva prendida la compu.
    base = proc_base or PROC_BASE
    content = read_file(os.path.join(base, "uptime")).strip()
    parts = content.split()
    result = {"uptime": 0.0, "idle": 0.0}
    if len(parts) >= 2:
        try:
            result["uptime"] = float(parts[0])
            result["idle"] = float(parts[1])
        except ValueError:
            pass
    return result


# ---

def get_username(uid):
    # Trata de buscar el nombre de usuario de un UID leyendo /etc/passwd (vía librería pwd)
    try:
        import pwd
        return pwd.getpwuid(uid).pw_name
    except (KeyError, ImportError):
        return str(uid)


# ---

def calc_cpu_percent(prev_utime, prev_stime, curr_utime, curr_stime,
                     total_elapsed_ticks):
    # Calcula qué porcentaje de CPU usó este proceso en base a los ticks (jiffies).
    # TODO: preguntarle al profe si esta fórmula está bien para todos los Linux
    if total_elapsed_ticks <= 0:
        return 0.0
    delta_proc = (curr_utime - prev_utime) + (curr_stime - prev_stime)
    return (delta_proc / total_elapsed_ticks) * 100.0


# ---

def get_memory_fields(status_dict):
    # Saca solo los campos de memoria de status y los deja como enteros en KB.
    fields = {
        "vm_size": "VmSize",
        "vm_rss": "VmRSS",
        "vm_data": "VmData",
        "vm_stk": "VmStk",
        "vm_exe": "VmExe",
        "vm_lib": "VmLib",
        "vm_hwm": "VmHWM",
        "vm_swap": "VmSwap",
    }
    result = {}
    for our_key, proc_key in fields.items():
        raw = status_dict.get(proc_key, "0 kB")
        # separo para sacarle el "kB" del final
        result[our_key] = _safe_int(raw.split()[0]) if raw else 0
    return result


def get_scheduling_policy_name(policy_num):
    # Pasa el número de política de sched a nombre.
    return SCHED_POLICIES.get(policy_num, f"UNKNOWN({policy_num})")
