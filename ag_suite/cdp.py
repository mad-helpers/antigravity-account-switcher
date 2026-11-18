# -*- coding: utf-8 -*-
"""Strict Antigravity workbench CDP target validation, port discovery, and local HTTP/CSRF firewall."""

import json
import re
import socket
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from . import store, vault

EXCLUDED_LOCAL_PORTS = frozenset({39281, 39285, 8780})

_LOOPBACK_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_DEVTOOLS_CACHE_LOCK = threading.Lock()
_DEVTOOLS_TARGETS_CACHE = {"data": None, "time": 0.0}
_DEVTOOLS_CACHE_TTL = 5.0
_STALE_PORTFILE_CACHE: dict[str, tuple[int, float]] = {}
_STALE_PORTFILE_TTL = 30.0

_WS_PAGE_RE = re.compile(r"^wss?://(127\.0\.0\.1|localhost):\d+/devtools/page/", re.I)
_LOOPBACK_HTTPS_RE = re.compile(r"^https://(?:127\.0\.0\.1|localhost):(\d+)(/.*)?$", re.I)
_TRUSTED_ORIGIN_RE = re.compile(
    r"^(?:vscode-file://[A-Za-z0-9._-]+|https?://(?:127\.0\.0\.1|localhost)(?::\d+)?)$",
    re.I,
)
_STATIC_UI_PATHS = frozenset({"/", "/index.html", "/styles.css", "/app.js", "/i18n.js", "/favicon.ico"})


def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.15) -> bool:
    """Return True if a loopback TCP port accepts connections within timeout."""
    try:
        p = int(port)
        if p <= 0 or p > 65535:
            return False
        with socket.create_connection((host, p), timeout=timeout):
            return True
    except Exception:
        return False


def is_antigravity_workbench_target(target: dict, ls_port: int | None = None) -> bool:
    """Return True iff CDP target is a real Antigravity IDE workbench page (never external web/WcvBrowser)."""
    if not isinstance(target, dict) or target.get("type") != "page":
        return False

    ws_url = str(target.get("webSocketDebuggerUrl") or "").strip()
    if not _WS_PAGE_RE.match(ws_url):
        return False

    url = str(target.get("url") or "").strip()
    if not url or url.startswith(("chrome-extension://", "devtools://", "data:", "about:")):
        return False

    if url.startswith("vscode-file://"):
        return True

    m = _LOOPBACK_HTTPS_RE.match(url)
    if not m:
        return False

    port_num = int(m.group(1))
    if port_num in EXCLUDED_LOCAL_PORTS:
        return False
    if ls_port is not None and port_num != int(ls_port):
        return False

    subpath = (m.group(2) or "/").lower()
    if subpath.startswith(("/sidecar", "/oauth2callback")):
        return False

    return True


def select_workbench_target(targets: list[dict], ls_port: int | None = None) -> dict | None:
    """Select the primary Antigravity workbench target from CDP /json/list output."""
    candidates = [t for t in (targets or []) if is_antigravity_workbench_target(t, ls_port=ls_port)]
    if not candidates:
        return None
    for t in candidates:
        if str(t.get("url") or "").startswith("vscode-file://"):
            return t
    return candidates[0]


def fetch_cdp_targets_list(port: int, timeout: float = 0.25) -> list[dict] | None:
    """Fetch `/json/list` from a local CDP port bypassing system HTTP proxies."""
    try:
        p = int(port)
    except Exception:
        return None
    if p <= 0 or p in EXCLUDED_LOCAL_PORTS or not is_port_open(p, timeout=timeout):
        return None
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{p}/json/list")
        with _LOOPBACK_OPENER.open(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            return data if isinstance(data, list) else None
    except Exception:
        return None


def is_valid_cdp_port(port: int, require_workbench: bool = True, timeout: float = 0.15) -> bool:
    """Validate that a local port serves CDP /json/list and optionally hosts a real workbench page."""
    data = fetch_cdp_targets_list(port, timeout=timeout)
    if data is None:
        return False
    if require_workbench:
        return select_workbench_target(data) is not None
    return True


def discover_live_cdp_ports() -> dict[str, int]:
    """Scan root Antigravity processes for live workbench-verified CDP ports."""
    found: dict[str, int] = {}
    try:
        import psutil
    except ImportError:
        return found

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if "antigravity" not in name:
                continue
            cmd = proc.info.get("cmdline")
            if cmd is None and hasattr(proc, "cmdline"):
                cmd = proc.cmdline()
            cmd = cmd or []
            if any(str(a).startswith(("--type=", "--import")) for a in cmd):
                continue
            if cmd and not any("--remote-debugging-port" in str(a) for a in cmd):
                continue

            inst_id = "instance_1"
            for arg in cmd:
                low = str(arg).lower()
                if "antigravity-instance" in low:
                    tail = low.split("antigravity-instance", 1)[1]
                    num = "".join(c for c in re.split(r"[\\/\"]", tail)[0] if c.isdigit())
                    if num:
                        inst_id = f"instance_{num}"
                    break

            net_fn = getattr(proc, "net_connections", None) or getattr(proc, "connections", None)
            if not net_fn:
                continue
            for conn in net_fn(kind="tcp"):
                if getattr(conn, "status", None) == "LISTEN" and getattr(conn, "laddr", None):
                    if conn.laddr.ip != "127.0.0.1":
                        continue
                    cand_port = int(conn.laddr.port)
                    if is_valid_cdp_port(cand_port, require_workbench=True, timeout=0.2):
                        found[inst_id] = cand_port
                        break
        except Exception:
            continue
    return found


def heal_devtools_port_file(port_file_path: Path, live_port: int) -> bool:
    """Atomically repair DevToolsActivePort only if live_port exposes a real workbench target."""
    if not is_valid_cdp_port(live_port, require_workbench=True, timeout=0.2):
        return False

    ws_path = "/devtools/browser"
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{int(live_port)}/json/version")
        with _LOOPBACK_OPENER.open(req, timeout=0.3) as resp:
            vdata = json.loads(resp.read().decode("utf-8", errors="ignore"))
            ws_url = str(vdata.get("webSocketDebuggerUrl") or "")
            if "/devtools/" in ws_url:
                ws_path = "/devtools/" + ws_url.split("/devtools/", 1)[1]
    except Exception:
        pass

    return store.atomic_write_text(Path(port_file_path), f"{int(live_port)}\n{ws_path}\n")


def _read_valid_port_file(port_file: Path) -> int | None:
    if not port_file.is_file():
        return None
    try:
        key = str(port_file)
        st = port_file.stat()
        mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))
        cached = _STALE_PORTFILE_CACHE.get(key)
        now = time.time()
        if cached and cached[0] == mtime_ns and (now - cached[1]) < _STALE_PORTFILE_TTL:
            return None
        lines = port_file.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
        if lines and lines[0].strip().isdigit():
            val = int(lines[0].strip())
            if is_valid_cdp_port(val, require_workbench=True, timeout=0.15):
                _STALE_PORTFILE_CACHE.pop(key, None)
                return val
        _STALE_PORTFILE_CACHE[key] = (mtime_ns, now)
    except Exception:
        pass
    return None


def invalidate_devtools_cache() -> None:
    """Clear cached CDP targets so fresh ports are probed immediately."""
    with _DEVTOOLS_CACHE_LOCK:
        _DEVTOOLS_TARGETS_CACHE["data"] = None
        _DEVTOOLS_TARGETS_CACHE["time"] = 0.0
        _STALE_PORTFILE_CACHE.clear()


def get_devtools_targets(account_resolver=None, use_cache: bool = True) -> list[dict]:
    """Return validated primary and secondary Antigravity CDP targets with 5s TTL caching."""
    if use_cache:
        with _DEVTOOLS_CACHE_LOCK:
            cached = _DEVTOOLS_TARGETS_CACHE.get("data")
            if cached is not None and (time.time() - _DEVTOOLS_TARGETS_CACHE.get("time", 0.0)) < _DEVTOOLS_CACHE_TTL:
                return [dict(item) for item in cached]

    resolver = account_resolver or store.get_instance_active_account
    paths_primary = vault.get_platform_paths("instance_1")
    appdata_root = paths_primary["appdata_root"]

    targets: list[dict] = []
    seen_ports: set[int] = set()
    discovered_map: dict[str, int] | None = None

    primary_port_file = paths_primary["devtools_port_path"]
    primary_port = _read_valid_port_file(primary_port_file)
    if not primary_port:
        discovered_map = discover_live_cdp_ports()
        if "instance_1" in discovered_map:
            primary_port = discovered_map["instance_1"]
            heal_devtools_port_file(primary_port_file, primary_port)

    if primary_port and primary_port not in seen_ports:
        seen_ports.add(primary_port)
        targets.append({
            "instance_id": "instance_1",
            "port": primary_port,
            "default_account": resolver("instance_1"),
        })

    if appdata_root.is_dir():
        for p in sorted(appdata_root.glob("Antigravity-Instance*")):
            if not p.is_dir():
                continue
            digits = "".join(c for c in p.name if c.isdigit())
            inst_id = f"instance_{digits}" if digits else p.name.lower().replace("-", "_")
            port_file = p / "DevToolsActivePort"
            sec_port = _read_valid_port_file(port_file)
            if not sec_port:
                if discovered_map is None:
                    discovered_map = discover_live_cdp_ports()
                if inst_id in discovered_map:
                    sec_port = discovered_map[inst_id]
                    heal_devtools_port_file(port_file, sec_port)
            if sec_port and sec_port not in seen_ports:
                seen_ports.add(sec_port)
                targets.append({
                    "instance_id": inst_id,
                    "port": sec_port,
                    "default_account": resolver(inst_id),
                })

    if use_cache:
        with _DEVTOOLS_CACHE_LOCK:
            _DEVTOOLS_TARGETS_CACHE["data"] = [dict(item) for item in targets]
            _DEVTOOLS_TARGETS_CACHE["time"] = time.time()

    return targets


def _hget(headers, key: str) -> str:
    if not headers:
        return ""
    val = headers.get(key)
    if val is not None:
        return str(val).strip()
    low = key.lower()
    for k, v in headers.items():
        if str(k).lower() == low:
            return str(v).strip()
    return ""


def check_local_http_request(headers, method: str, path: str) -> tuple[bool, str | None]:
    """Validate local HTTP Origin, Sec-Fetch-Site, and JSON Content-Type for :39281 / :39285."""
    clean_path = urllib.parse.urlparse(str(path or "/")).path
    method_up = str(method or "GET").strip().upper()

    if method_up in ("GET", "OPTIONS") and (
        clean_path in ("/health", "/api/health") or clean_path.startswith("/fonts/")
    ):
        return True, "*"

    if _hget(headers, "Sec-Fetch-Site").lower() == "cross-site":
        return False, "Cross-site request blocked"

    origin = _hget(headers, "Origin")
    if not origin:
        cors_origin = None
    elif _TRUSTED_ORIGIN_RE.match(origin):
        cors_origin = origin
    else:
        return False, "Untrusted Origin"

    if method_up in ("GET", "HEAD", "OPTIONS") and clean_path in _STATIC_UI_PATHS:
        return True, cors_origin

    if method_up == "POST":
        ctype = _hget(headers, "Content-Type").lower()
        if not ctype.startswith("application/json"):
            return False, "Content-Type must be application/json"

    return True, cors_origin
