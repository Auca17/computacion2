"""
Interfaz gráfica en la terminal usando curses.
Muestra varios paneles con info de procesos y el sistema.
Usa diccionarios compartidos de multiprocessing para leer datos sin tocar /proc.
"""

import curses
import time

# ---

VIEW_KEYS = [
    ("1", "r", "resumen",    "Resumen"),
    ("2", "m", "memoria",    "Memoria"),
    ("3", "f", "fds",        "FDs"),
    ("4", "t", "threads",    "Threads"),
    ("5", "s", "senales",    "Señales"),
    ("6", "p", "scheduling", "Scheduling"),
    ("7", "g", "sistema",    "Sistema"),
]

# intervalos minimos de refresco para cada vista
MIN_INTERVALS = {
    "resumen": 0.5,
    "memoria": 1.0,
    "fds": 2.0,
    "threads": 0.5,
    "senales": 5.0,
    "scheduling": 5.0,
    "sistema": 1.0,
}

# modos de ordenamiento, se cambian con la tecla 'c'
SORT_MODES = ["cpu", "rss", "pid"]

# colores que uso para la interfaz
CP_HEADER   = 1
CP_SELECTED = 2
CP_PINNED   = 3
CP_FOOTER   = 4
CP_ALERT    = 5
CP_GOOD     = 6
CP_TITLE    = 7


class Display:
    """
    Clase principal que dibuja la interfaz curses.
    Guarda el estado de la UI (cursor, filtros, etc).
    """

    def __init__(self, snapshot, intervals, stop_event, verbose_flag, sig_handler=None):
        """Inicializa la clase con las variables compartidas y estado."""
        self._snapshot = snapshot
        self._intervals = intervals
        self._stop_event = stop_event
        self._verbose = verbose_flag
        self._sig_handler = sig_handler

        # acá guardo el estado de la UI
        self._current_view = "resumen"
        self._cursor = 0           # indice de la lista de pids
        self._scroll_top = 0       # primera fila que se ve
        self._pinned_pid = None    # pid fijado (o None)
        self._sort_mode_idx = 0    # indice de SORT_MODES
        self._filter_cmd = ""      # filtro por comando
        self._filter_user = ""     # filtro por usuario
        self._show_help = False    # para saber si muestro la ventanita de ayuda
        self._detail_scroll = 0    # scroll del panel de abajo

    def set_filters(self, cmd_filter, user_filter):
        """Actualiza los filtros de comando y usuario."""
        self._filter_cmd = cmd_filter or ""
        self._filter_user = user_filter or ""
        self._cursor = 0
        self._scroll_top = 0

    # ---

    def run(self, stdscr):
        """Bucle principal de curses, se llama con curses.wrapper."""
        self._stdscr = stdscr
        self._init_curses()

        # TODO: quizas mejorar el refresco para que no gaste tanta cpu
        while not self._stop_event.is_set():
            if self._sig_handler:
                self._sig_handler.process_pending()
            try:
                self._draw(stdscr)
                self._handle_input(stdscr)
            except curses.error:
                # la terminal es muy chica o hubo un error al dibujar, sigo nomas
                pass

    # ---

    def _init_curses(self):
        """Configura los colores y el input de curses."""
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()
        curses.halfdelay(5)  # espera 500 ms maximo por tecla

        # inicializo los pares de colores
        curses.init_pair(CP_HEADER,   curses.COLOR_WHITE,  curses.COLOR_BLUE)
        curses.init_pair(CP_SELECTED, curses.COLOR_BLACK,  curses.COLOR_CYAN)
        curses.init_pair(CP_PINNED,   curses.COLOR_BLACK,  curses.COLOR_YELLOW)
        curses.init_pair(CP_FOOTER,   curses.COLOR_WHITE,  curses.COLOR_BLUE)
        curses.init_pair(CP_ALERT,    curses.COLOR_RED,    -1)
        curses.init_pair(CP_GOOD,     curses.COLOR_GREEN,  -1)
        curses.init_pair(CP_TITLE,    curses.COLOR_YELLOW, -1)

    # ---

    def _handle_input(self, stdscr):
        """Lee las teclas y hace cosas dependiendo de qué se apretó."""
        try:
            key = stdscr.getch()
        except curses.error:
            return

        if key == -1:
            return

        # apretó la q para salir
        if key == ord("q"):
            self._stop_event.set()
            return

        # si apretan h o ? muestro u oculto la ayuda
        if key in (ord("h"), ord("?")):
            self._show_help = not self._show_help
            return

        # si la ayuda esta abierta, cualquier otra tecla la cierra
        if self._show_help:
            self._show_help = False
            return

        # cambiar de vista con los numeros
        for num_key, letter, snap_key, _ in VIEW_KEYS:
            if key == ord(num_key) or key == ord(letter):
                self._current_view = snap_key
                self._detail_scroll = 0
                return

        # flechitas para moverse
        if key == curses.KEY_UP:
            self._cursor = max(0, self._cursor - 1)
            return
        if key == curses.KEY_DOWN:
            self._cursor += 1  # el limite lo pongo al dibujar
            return

        # scroll en el panel de abajo
        if key == curses.KEY_PPAGE:
            self._detail_scroll = max(0, self._detail_scroll - 5)
            return
        if key == curses.KEY_NPAGE:
            self._detail_scroll += 5
            return

        # fijar un proceso
        if key in (10, 13, curses.KEY_ENTER):
            pids = self._get_pid_list()
            if pids and 0 <= self._cursor < len(pids):
                pid = pids[self._cursor]
                self._pinned_pid = None if self._pinned_pid == pid else pid
            return

        # filtrar por comando
        if key == ord("/"):
            self._filter_cmd = self._read_input(stdscr, "Filter cmd: ")
            self._cursor = 0
            self._scroll_top = 0
            return

        # filtrar por usuario
        if key == ord("u"):
            self._filter_user = self._read_input(stdscr, "Filter user: ")
            self._cursor = 0
            self._scroll_top = 0
            return

        # cambiar el modo de ordenamiento
        if key == ord("c"):
            self._sort_mode_idx = (self._sort_mode_idx + 1) % len(SORT_MODES)
            self._cursor = 0
            self._scroll_top = 0
            return

        # cambiar la velocidad de refresco
        if key == ord("+") or key == ord("="):
            self._adjust_interval(0.5)
            return
        if key == ord("-") or key == ord("_"):
            self._adjust_interval(-0.5)
            return

        # si redimensionan la ventana
        if key == curses.KEY_RESIZE:
            curses.update_lines_cols()
            return

    def _read_input(self, stdscr, prompt):
        """Muestra un prompt abajo de todo y lee lo que escribe el usuario."""
        h, w = stdscr.getmaxyx()
        curses.echo()
        curses.curs_set(1)
        curses.nocbreak()
        curses.halfdelay(255)  # espero a que termine de escribir

        try:
            stdscr.move(h - 1, 0)
            stdscr.clrtoeol()
            stdscr.addnstr(h - 1, 0, prompt, w - 1, curses.color_pair(CP_FOOTER))
            stdscr.refresh()
            buf = stdscr.getstr(h - 1, len(prompt), w - len(prompt) - 1)
            return buf.decode("utf-8", errors="replace").strip()
        except curses.error:
            return ""
        finally:
            curses.noecho()
            curses.curs_set(0)
            curses.cbreak()
            curses.halfdelay(5)

    def _adjust_interval(self, delta):
        """Cambia el tiempo de refresco de la vista actual."""
        key = self._current_view
        if key not in self._intervals:
            return
        val = self._intervals[key]
        minimum = MIN_INTERVALS.get(key, 0.5)
        new_val = max(minimum, val.value + delta)
        val.value = new_val

    # ---

    def _get_resumen_data(self):
        """Devuelve el diccionario de datos de resumen."""
        snap = self._snapshot.get("resumen")
        if not snap:
            return {}
        return snap.get("data", {})

    def _get_pid_list(self):
        """Filtra y ordena la lista de PIDs según la configuración actual."""
        data = self._get_resumen_data()
        if not data:
            return []

        pids = []
        for pid, info in data.items():
            # me fijo si pasa el filtro de comando
            if self._filter_cmd:
                cmd = info.get("cmd", "")
                if self._filter_cmd.lower() not in cmd.lower():
                    continue
            # me fijo si pasa el filtro de usuario
            if self._filter_user:
                user = info.get("user", "")
                if self._filter_user.lower() not in user.lower():
                    continue
            pids.append(pid)

        # ordeno la lista segun el modo elegido
        mode = SORT_MODES[self._sort_mode_idx]
        if mode == "cpu":
            pids.sort(key=lambda p: data[p].get("cpu_pct", 0.0), reverse=True)
        elif mode == "rss":
            pids.sort(key=lambda p: data[p].get("rss_kb", 0), reverse=True)
        else:
            pids.sort()

        return pids

    def _selected_pid(self):
        """Devuelve el PID seleccionado o pineado."""
        pids = self._get_pid_list()
        if self._pinned_pid is not None:
            return self._pinned_pid
        if pids and 0 <= self._cursor < len(pids):
            return pids[self._cursor]
        return None

    # ---

    def _draw(self, stdscr):
        """Dibuja toda la pantalla de nuevo."""
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        
        # si la terminal es muy chica, no dibujo nada y muestro un error
        if h < 5 or w < 40:
            self._draw_too_small(stdscr, h, w)
            stdscr.noutrefresh()
            curses.doupdate()
            return

        if self._show_help:
            self._draw_help_overlay(stdscr, h, w)
            stdscr.noutrefresh()
            curses.doupdate()
            return

        # la vista del sistema ocupa toda la pantalla
        if self._current_view == "sistema":
            self._draw_header(stdscr, w)
            self._draw_sistema_full(stdscr, h, w)
            self._draw_footer(stdscr, h, w)
            stdscr.noutrefresh()
            curses.doupdate()
            return

        # layout comun: header | lista de procesos | detalles | footer
        self._draw_header(stdscr, w)
        proc_end = max(3, int(h * 0.6))
        self._draw_process_list(stdscr, 1, proc_end, w)
        self._draw_detail_panel(stdscr, proc_end, h - 1, w)
        self._draw_footer(stdscr, h, w)

        stdscr.noutrefresh()
        curses.doupdate()

    def _draw_too_small(self, stdscr, h, w):
        """Avisa si la terminal es muy chica."""
        msg = "Terminal too small"
        try:
            stdscr.addnstr(h // 2, max(0, (w - len(msg)) // 2), msg, w - 1,
                           curses.color_pair(CP_ALERT) | curses.A_BOLD)
        except curses.error:
            pass

    # ---

    def _draw_header(self, stdscr, w):
        """Dibuja la barra de arriba con estadísticas generales."""
        view_label = ""
        for _, _, snap_key, label in VIEW_KEYS:
            if snap_key == self._current_view:
                view_label = label
                break

        # saco datos basicos de sistema para el header
        sys_data = self._snapshot.get("sistema")
        cpu_str = mem_str = load_str = "—"
        if sys_data and "data" in sys_data:
            sd = sys_data["data"]
            cpu_info = sd.get("cpu", {})
            idle = cpu_info.get("idle_pct", 100.0)
            cpu_str = f"{100.0 - idle:.1f}%"
            mem_info = sd.get("memory", {})
            total = mem_info.get("total", 1)
            free = mem_info.get("free", 0) + mem_info.get("buffers", 0) + mem_info.get("cached", 0)
            used_pct = ((total - free) / total * 100.0) if total > 0 else 0.0
            mem_str = f"{used_pct:.1f}%"
            load_info = sd.get("load", {})
            load_str = f"{load_info.get('load1', 0.0):.2f}"

        interval_val = ""
        if self._current_view in self._intervals:
            interval_val = f" [{self._intervals[self._current_view].value:.1f}s]"

        sort_label = SORT_MODES[self._sort_mode_idx].upper()
        verbose_str = " (VERBOSE)" if self._verbose.value else ""

        line = (f" Process Monitor │ {view_label}{interval_val}{verbose_str} │ "
                f"CPU:{cpu_str}  Mem:{mem_str}  Load:{load_str}  "
                f"Sort:{sort_label}")
        line = line.ljust(w)

        try:
            stdscr.addnstr(0, 0, line, w - 1,
                           curses.color_pair(CP_HEADER) | curses.A_BOLD)
        except curses.error:
            pass

    # ---

    def _draw_process_list(self, stdscr, start_row, end_row, w):
        """Dibuja la lista de procesos con scroll."""
        data = self._get_resumen_data()
        pids = self._get_pid_list()

        # dibujo las cabeceras de las columnas
        hdr = self._format_proc_row("PID", "USER", "ST", "CPU%", "RSS(KB)",
                                    "THR", "COMMAND", w)
        try:
            stdscr.addnstr(start_row, 0, hdr, w - 1,
                           curses.color_pair(CP_TITLE) | curses.A_BOLD)
        except curses.error:
            pass

        if not pids:
            try:
                stdscr.addnstr(start_row + 1, 0, "  [No data yet]", w - 1,
                               curses.color_pair(CP_ALERT))
            except curses.error:
                pass
            return

        visible_rows = end_row - start_row - 1  # le resto el header
        
        # trato de que el cursor no se vaya de los limites
        self._cursor = max(0, min(self._cursor, len(pids) - 1))

        # muevo el scroll si el cursor se va de la pantalla
        if self._cursor < self._scroll_top:
            self._scroll_top = self._cursor
        elif self._cursor >= self._scroll_top + visible_rows:
            self._scroll_top = self._cursor - visible_rows + 1

        for i in range(visible_rows):
            idx = self._scroll_top + i
            row = start_row + 1 + i
            if row >= end_row:
                break
            if idx >= len(pids):
                break

            pid = pids[idx]
            info = data.get(pid, {})
            line = self._format_proc_row(
                str(info.get("pid", pid)),
                _trunc(info.get("user", "?"), 10),
                info.get("state", "?"),
                f"{info.get('cpu_pct', 0.0):5.1f}",
                str(info.get("rss_kb", 0)),
                str(info.get("threads", 0)),
                _trunc(info.get("cmd", ""), w - 52),
                w,
            )

            attr = curses.A_NORMAL
            if pid == self._pinned_pid:
                attr = curses.color_pair(CP_PINNED) | curses.A_BOLD
            elif idx == self._cursor:
                attr = curses.color_pair(CP_SELECTED)

            # pongo el pinito si esta fijado
            prefix = "▶" if pid == self._pinned_pid else " "
            line = prefix + line[1:]

            try:
                stdscr.addnstr(row, 0, line, w - 1, attr)
            except curses.error:
                pass

    @staticmethod
    def _format_proc_row(pid, user, state, cpu, rss, thr, cmd, w):
        """Le da formato a una fila de la lista de procesos para que quede alineada."""
        # armo el string de la fila con anchos fijos para que quede como tabla
        return (f" {pid:>7s}  {user:<10s}  {state:^3s}  {cpu:>6s}  "
                f"{rss:>9s}  {thr:>4s}  {cmd}").ljust(w)

    # ---

    def _draw_detail_panel(self, stdscr, start_row, end_row, w):
        """Dibuja el panel de abajo con detalles del proceso."""
        # dibujo una linea separadora
        try:
            stdscr.addnstr(start_row, 0, "─" * w, w - 1,
                           curses.color_pair(CP_TITLE))
        except curses.error:
            pass

        pid = self._selected_pid()
        avail_rows = end_row - start_row - 1
        content_start = start_row + 1

        if pid is None:
            try:
                stdscr.addnstr(content_start, 0, "  Select a process",
                               w - 1, curses.color_pair(CP_ALERT))
            except curses.error:
                pass
            return

        view = self._current_view
        if view == "resumen":
            lines = self._detail_resumen(pid)
        elif view == "memoria":
            lines = self._detail_memoria(pid)
        elif view == "fds":
            lines = self._detail_fds(pid)
        elif view == "threads":
            lines = self._detail_threads(pid)
        elif view == "senales":
            lines = self._detail_senales(pid)
        elif view == "scheduling":
            lines = self._detail_scheduling(pid)
        else:
            lines = ["  [Unknown view]"]

        # hago el scroll del panel de abajo
        if self._detail_scroll > len(lines):
            self._detail_scroll = max(0, len(lines) - avail_rows)
        visible = lines[self._detail_scroll:self._detail_scroll + avail_rows]

        for i, line in enumerate(visible):
            row = content_start + i
            if row >= end_row:
                break
            try:
                stdscr.addnstr(row, 0, line, w - 1)
            except curses.error:
                pass

    # ---

    def _detail_resumen(self, pid):
        """Detalles para la vista de resumen."""
        snap = self._snapshot.get("resumen")
        if not snap or pid not in snap.get("data", {}):
            return ["  [No resumen data for this process]"]
        d = snap["data"][pid]
        return [
            f"  PID:      {d.get('pid', '?')}",
            f"  PPID:     {d.get('ppid', '?')}",
            f"  UID/GID:  {d.get('uid', '?')} / {d.get('gid', '?')}",
            f"  User:     {d.get('user', '?')}",
            f"  State:    {d.get('state', '?')}",
            f"  Command:  {d.get('cmd', '?')}",
            f"  CPU%:     {d.get('cpu_pct', 0.0):.2f}%",
            f"  Threads:  {d.get('threads', '?')}",
            f"  RSS (KB): {d.get('rss_kb', '?')}",
        ]

    def _detail_memoria(self, pid):
        """Detalles para la vista de memoria."""
        snap = self._snapshot.get("memoria")
        if not snap or pid not in snap.get("data", {}):
            return ["  [No memory data for this process]"]
        d = snap["data"][pid]
        segs = d.get("segments", {})
        return [
            f"  VmSize:   {d.get('vm_size', 0):>10d} KB",
            f"  VmRSS:    {d.get('vm_rss', 0):>10d} KB",
            f"  VmHWM:    {d.get('vm_hwm', 0):>10d} KB",
            f"  VmData:   {d.get('vm_data', 0):>10d} KB",
            f"  VmStk:    {d.get('vm_stk', 0):>10d} KB",
            f"  VmExe:    {d.get('vm_exe', 0):>10d} KB",
            f"  VmLib:    {d.get('vm_lib', 0):>10d} KB",
            f"  VmSwap:   {d.get('vm_swap', 0):>10d} KB",
            "",
            f"  Page Faults  minor: {d.get('minflt', 0)}  "
            f"major: {d.get('majflt', 0)}",
            f"  Children     minor: {d.get('cminflt', 0)}  "
            f"major: {d.get('cmajflt', 0)}",
            "",
            "  Memory Segments (KB):",
            f"    text:   {segs.get('text', 0):>8d}",
            f"    data:   {segs.get('data', 0):>8d}",
            f"    heap:   {segs.get('heap', 0):>8d}",
            f"    stack:  {segs.get('stack', 0):>8d}",
            f"    shared: {segs.get('shared', 0):>8d}",
            f"    other:  {segs.get('other', 0):>8d}",
        ]

    def _detail_fds(self, pid):
        """Detalles para la vista de FDs."""
        snap = self._snapshot.get("fds")
        if not snap or pid not in snap.get("data", {}):
            return ["  [No FD data for this process]"]
        fds = snap["data"][pid]
        if not fds:
            return ["  No open file descriptors"]
        lines = [f"  {'FD':>4s}  {'Type':<12s}  Target"]
        lines.append("  " + "─" * 50)

        limit = len(fds)
        truncated = False
        if not self._verbose.value and limit > 5:
            limit = 5
            truncated = True

        for entry in fds[:limit]:
            fd = entry.get("fd", "?")
            target = entry.get("target", "?")
            fd_type = entry.get("type", "?")
            lines.append(f"  {fd:>4}  {fd_type:<12s}  {target}")

        if truncated:
            lines.append(f"  [... {len(fds) - 5} more FDs hidden. Send SIGUSR2 to toggle verbose mode ...]")
        return lines

    def _detail_threads(self, pid):
        """Detalles para la vista de threads."""
        snap = self._snapshot.get("threads")
        if not snap or pid not in snap.get("data", {}):
            return ["  [No thread data for this process]"]
        threads = snap["data"][pid]
        if not threads:
            return ["  No threads"]
        lines = [f"  {'TID':>7s}  {'Name':<16s}  {'St':>2s}  "
                 f"{'CPU%':>6s}  {'VolCSW':>8s}  {'NonVolCSW':>10s}"]
        lines.append("  " + "─" * 60)
        for t in threads:
            lines.append(
                f"  {t.get('tid', '?'):>7}  "
                f"{_trunc(t.get('name', '?'), 16):<16s}  "
                f"{t.get('state', '?'):>2s}  "
                f"{t.get('cpu_pct', 0.0):>6.1f}  "
                f"{t.get('vol_ctxt', 0):>8}  "
                f"{t.get('nonvol_ctxt', 0):>10}"
            )
        return lines

    def _detail_senales(self, pid):
        """Detalles de señales bloqueadas/ignoradas."""
        snap = self._snapshot.get("senales")
        if not snap or pid not in snap.get("data", {}):
            return ["  [No signal data for this process]"]
        d = snap["data"][pid]
        lines = []
        for label, key in [("Blocked",        "blocked"),
                           ("Ignored",        "ignored"),
                           ("Caught",         "caught"),
                           ("Pending",        "pending"),
                           ("Shared Pending", "shared_pending")]:
            sigs = d.get(key, [])
            sig_str = ", ".join(sigs) if sigs else "(none)"
            lines.append(f"  {label + ':':<18s} {sig_str}")
        return lines

    def _detail_scheduling(self, pid):
        """Detalles del scheduler y prioridades."""
        snap = self._snapshot.get("scheduling")
        if not snap or pid not in snap.get("data", {}):
            return ["  [No scheduling data for this process]"]
        d = snap["data"][pid]
        return [
            f"  Nice:             {d.get('nice', '?')}",
            f"  Priority:         {d.get('priority', '?')}",
            f"  Policy:           {d.get('policy', '?')}",
            f"  RT Priority:      {d.get('rt_priority', '?')}",
            f"  CPU Affinity:     {d.get('cpu_affinity', '?')}",
            f"  Vol Ctx Sw:       {d.get('vol_ctxt', '?')}",
            f"  Nonvol Ctx Sw:    {d.get('nonvol_ctxt', '?')}",
            f"  User Time (ut):   {d.get('utime', '?')}",
            f"  System Time (st): {d.get('stime', '?')}",
            f"  SID:              {d.get('sid', '?')}",
            f"  PGID:             {d.get('pgid', '?')}",
        ]

    # ---

    def _draw_sistema_full(self, stdscr, h, w):
        """Dibuja la vista a pantalla completa del sistema."""
        snap = self._snapshot.get("sistema")
        if not snap or "data" not in snap:
            try:
                stdscr.addnstr(2, 0, "  [No system data yet]", w - 1,
                               curses.color_pair(CP_ALERT))
            except curses.error:
                pass
            return

        d = snap["data"]
        row = 2

        def put(r, text, attr=curses.A_NORMAL):
            """Escribe una línea y avanza a la siguiente."""
            if r >= h - 1:
                return r
            try:
                stdscr.addnstr(r, 0, text, w - 1, attr)
            except curses.error:
                pass
            return r + 1

        def section(r, title):
            """Dibuja el titulo de una seccion."""
            r = put(r, "")
            return put(r, f"  ── {title} ──",
                       curses.color_pair(CP_TITLE) | curses.A_BOLD)

        # info de la CPU
        cpu = d.get("cpu", {})
        row = section(row, "CPU")
        row = put(row, f"  User: {cpu.get('user_pct', 0):.1f}%   "
                       f"System: {cpu.get('system_pct', 0):.1f}%   "
                       f"Idle: {cpu.get('idle_pct', 0):.1f}%   "
                       f"IOWait: {cpu.get('iowait_pct', 0):.1f}%")

        # promedios de carga (load average)
        load = d.get("load", {})
        row = section(row, "Load Averages")
        row = put(row, f"  1m: {load.get('load1', 0):.2f}   "
                       f"5m: {load.get('load5', 0):.2f}   "
                       f"15m: {load.get('load15', 0):.2f}")

        # uso de la memoria
        mem = d.get("memory", {})
        total = mem.get("total", 1)
        free = mem.get("free", 0)
        buffers = mem.get("buffers", 0)
        cached = mem.get("cached", 0)
        used = total - free - buffers - cached
        used_pct = (used / total * 100) if total > 0 else 0
        row = section(row, "Memory")
        row = put(row, f"  Total: {_kb_human(total)}   "
                       f"Used: {_kb_human(used)} ({used_pct:.1f}%)   "
                       f"Free: {_kb_human(free)}   "
                       f"Buffers: {_kb_human(buffers)}   "
                       f"Cached: {_kb_human(cached)}")
        swap_total = mem.get("swap_total", 0)
        swap_free = mem.get("swap_free", 0)
        swap_used = swap_total - swap_free
        row = put(row, f"  Swap Total: {_kb_human(swap_total)}   "
                       f"Swap Used: {_kb_human(swap_used)}   "
                       f"Swap Free: {_kb_human(swap_free)}")

        # tiempo encendido
        uptime = d.get("uptime", 0)
        boot_time = d.get("boot_time", 0)
        row = section(row, "Uptime")
        row = put(row, f"  Uptime: {_fmt_uptime(uptime)}   "
                       f"Boot: {_fmt_epoch(boot_time)}")

        # cuantos procesos hay
        procs = d.get("processes", {})
        row = section(row, "Processes")
        row = put(row, f"  Total: {procs.get('total', 0)}   "
                       f"Running: {procs.get('running', 0)}   "
                       f"Sleeping: {procs.get('sleeping', 0)}   "
                       f"Stopped: {procs.get('stopped', 0)}   "
                       f"Zombie: {procs.get('zombie', 0)}   "
                       f"Threads: {procs.get('threads_total', 0)}")

        # los que mas cpu gastan
        top_cpu = d.get("top_cpu", [])
        if top_cpu:
            row = section(row, "Top 3 by CPU")
            for entry in top_cpu[:3]:
                row = put(row, f"    PID {entry.get('pid', '?'):>7}  "
                               f"CPU: {entry.get('cpu_pct', 0):>5.1f}%  "
                               f"{entry.get('cmd', '?')}",
                          curses.color_pair(CP_GOOD))

        # los que mas memoria gastan
        top_mem = d.get("top_mem", [])
        if top_mem:
            row = section(row, "Top 3 by Memory")
            for entry in top_mem[:3]:
                row = put(row, f"    PID {entry.get('pid', '?'):>7}  "
                               f"RSS: {_kb_human(entry.get('rss_kb', 0)):>9s}  "
                               f"{entry.get('cmd', '?')}",
                          curses.color_pair(CP_GOOD))

    # ---

    def _draw_footer(self, stdscr, h, w):
        """Dibuja la barra de abajo con los atajos de teclado."""
        filters = ""
        if self._filter_cmd:
            filters += f" cmd:'{self._filter_cmd}'"
        if self._filter_user:
            filters += f" user:'{self._filter_user}'"

        pinned = ""
        if self._pinned_pid is not None:
            pinned = f" pinned:{self._pinned_pid}"

        line = (f" 1-7:view  ↑↓:nav  Enter:pin  /:filter  "
                f"u:user  c:sort  +/-:interval  h:help  q:quit"
                f"{filters}{pinned}")
        line = line.ljust(w)
        try:
            stdscr.addnstr(h - 1, 0, line[:w - 1], w - 1,
                           curses.color_pair(CP_FOOTER))
        except curses.error:
            pass

    # ---

    def _draw_help_overlay(self, stdscr, h, w):
        """Dibuja el cuadrito de ayuda en el medio de la pantalla."""
        help_lines = [
            "╔══════════════════════════════════════════╗",
            "║         PROCESS MONITOR — HELP           ║",
            "╠══════════════════════════════════════════╣",
            "║  1 / r    Resumen view                   ║",
            "║  2 / m    Memoria view                   ║",
            "║  3 / f    FDs view                       ║",
            "║  4 / t    Threads view                   ║",
            "║  5 / s    Señales view                   ║",
            "║  6 / p    Scheduling view                ║",
            "║  7 / g    Sistema view (full screen)     ║",
            "║  ↑ / ↓    Navigate process list          ║",
            "║  PgUp/Dn  Scroll detail panel            ║",
            "║  Enter    Pin / unpin selected process    ║",
            "║  /        Filter by command substring     ║",
            "║  u        Filter by username substring    ║",
            "║  c        Cycle sort: CPU → RSS → PID    ║",
            "║  + / -    Adjust view poll interval       ║",
            "║  h / ?    Toggle this help overlay        ║",
            "║  q        Quit                            ║",
            "╠══════════════════════════════════════════╣",
            "║      Press any key to close help         ║",
            "╚══════════════════════════════════════════╝",
        ]

        start_row = max(0, (h - len(help_lines)) // 2)
        box_width = len(help_lines[0])
        start_col = max(0, (w - box_width) // 2)

        for i, line in enumerate(help_lines):
            row = start_row + i
            if row >= h:
                break
            try:
                stdscr.addnstr(row, start_col, line, w - start_col - 1,
                               curses.color_pair(CP_TITLE) | curses.A_BOLD)
            except curses.error:
                pass


# ---

def _trunc(text, max_len):
    """Corta el texto si es muy largo y le pone puntitos."""
    if len(text) <= max_len:
        return text
    return text[:max(0, max_len - 1)] + "…"


def _kb_human(kb):
    """Convierte los KB a MB o GB para que se lea mejor."""
    if kb < 1024:
        return f"{kb} KB"
    elif kb < 1024 * 1024:
        return f"{kb / 1024:.1f} MB"
    else:
        return f"{kb / (1024 * 1024):.1f} GB"


def _fmt_uptime(seconds):
    """Convierte los segundos en días, horas y minutos."""
    s = int(seconds)
    days, s = divmod(s, 86400)
    hours, s = divmod(s, 3600)
    mins, secs = divmod(s, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def _fmt_epoch(epoch):
    """Convierte el timestamp a una fecha normal."""
    if not epoch:
        return "—"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(epoch))
