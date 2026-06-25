"""Index of running stack processes by label and port.

We kept having to forensically work out which PID was which menhir/neo4j/dashboard
(orphaned throwaways accumulate). This discovers listening TCP ports + their owning
process and labels each against a curated port map and command-line patterns, so
`archolith-bench ports` shows what is running where at a glance.

Discovery uses PowerShell on Windows (the host); on other platforms it falls back to
probing the known ports directly. Read-only -- it never starts or kills anything.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
from dataclasses import dataclass

# Curated label map for the benchmark/menhir stack. Authoritative over cmdline guesses.
KNOWN_PORTS: dict[int, str] = {
    8100: "menhir (default/prod HTTP)",
    8101: "menhir (benchmark throwaway)",
    8200: "archolith-bench dashboard (web)",
    8787: "menhir explorer",
    8082: "menhir scheduler",
    8081: "local llama (llm/embed)",
    7687: "neo4j (default, bolt)",
    7688: "neo4j (benchmark throwaway, bolt)",
    7474: "neo4j (default, http)",
    7475: "neo4j (benchmark throwaway, http)",
    3001: "langfuse (web)",
    9800: "archolith-context proxy",
}

# cmdline substring -> label, used when the port is not in KNOWN_PORTS.
_CMD_PATTERNS: list[tuple[str, str]] = [
    ("menhir.cli serve-watch", "menhir serve-watch (watchdog)"),
    ("menhir.exe serve", "menhir serve"),
    ("menhir.cli serve", "menhir serve"),
    ("menhir.api.server", "menhir server"),
    ("menhir-explorer", "menhir explorer"),
    ("dashboard --serve", "archolith-bench dashboard"),
    ("longmemeval-menhir", "archolith-bench memory run"),
    ("archolith-bench", "archolith-bench"),
    ("neo4j", "neo4j"),
]

_RELEVANT = ("menhir", "archolith", "neo4j", "langfuse", "llama", "longmemeval")


@dataclass
class ProcEntry:
    port: int
    pid: int | None
    label: str
    cmd: str

    @property
    def known(self) -> bool:
        return self.port in KNOWN_PORTS


def label_for(port: int, cmd: str) -> str:
    if port in KNOWN_PORTS:
        return KNOWN_PORTS[port]
    low = (cmd or "").lower()
    for needle, lbl in _CMD_PATTERNS:
        if needle.lower() in low:
            return lbl
    return "?"


def _is_relevant(port: int, cmd: str) -> bool:
    if port in KNOWN_PORTS:
        return True
    low = (cmd or "").lower()
    return any(tok in low for tok in _RELEVANT)


def _port_listening(port: int, host: str = "127.0.0.1", timeout: float = 0.2) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def _discover_windows() -> list[ProcEntry]:
    ps = (
        "$ErrorActionPreference='SilentlyContinue';"
        "$procs=@{}; Get-CimInstance Win32_Process | ForEach-Object { $procs[[int]$_.ProcessId]=$_.CommandLine };"
        "Get-NetTCPConnection -State Listen | Select-Object -Unique LocalPort,OwningProcess | ForEach-Object {"
        " [pscustomobject]@{ port=[int]$_.LocalPort; pid=[int]$_.OwningProcess; cmd=$procs[[int]$_.OwningProcess] } }"
        " | ConvertTo-Json -Depth 2"
    )
    try:
        out = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return []
    if not out:
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    entries: list[ProcEntry] = []
    for row in data:
        port = int(row.get("port") or 0)
        cmd = str(row.get("cmd") or "")
        pid = row.get("pid")
        entries.append(ProcEntry(port=port, pid=int(pid) if pid else None, label=label_for(port, cmd), cmd=cmd))
    return entries


def _discover_fallback() -> list[ProcEntry]:
    """Non-Windows / no-PowerShell: probe the curated ports for liveness only."""
    entries: list[ProcEntry] = []
    for port, lbl in KNOWN_PORTS.items():
        if _port_listening(port):
            entries.append(ProcEntry(port=port, pid=None, label=lbl, cmd=""))
    return entries


def _dedupe_by_port(entries: list[ProcEntry]) -> list[ProcEntry]:
    """One row per port. Docker forwards a port via several backend PIDs; prefer the
    most informative owner (a non-docker process) when there is a choice."""
    best: dict[int, ProcEntry] = {}
    for e in entries:
        cur = best.get(e.port)
        if cur is None:
            best[e.port] = e
            continue
        cur_docker = "docker" in (cur.cmd or "").lower()
        new_docker = "docker" in (e.cmd or "").lower()
        if cur_docker and not new_docker:
            best[e.port] = e
    return list(best.values())


def discover() -> list[ProcEntry]:
    entries = _discover_windows() if sys.platform.startswith("win") else []
    if not entries:
        entries = _discover_fallback()
    entries = _dedupe_by_port(entries)
    entries.sort(key=lambda e: (e.port not in KNOWN_PORTS, e.port))
    return entries


def filter_relevant(entries: list[ProcEntry], *, show_all: bool = False) -> list[ProcEntry]:
    return entries if show_all else [e for e in entries if _is_relevant(e.port, e.cmd)]


def render(entries: list[ProcEntry], *, show_all: bool = False) -> str:
    rows = filter_relevant(entries, show_all=show_all)
    lines = [f"{'PORT':>6}  {'LABEL':<34}{'PID':>8}  CMD", f"{'-' * 6}  {'-' * 34}{'-' * 8}  {'-' * 30}"]
    if not rows:
        lines.append("  (no matching listening ports)")
    for e in rows:
        cmd = (e.cmd or "").strip()
        if len(cmd) > 70:
            cmd = "..." + cmd[-67:]
        lines.append(f"{e.port:>6}  {e.label:<34}{(e.pid if e.pid is not None else '-')!s:>8}  {cmd}")
    return "\n".join(lines)
