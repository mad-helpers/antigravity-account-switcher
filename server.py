#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Antigravity Switcher & Migration Local Server (v3.0.0)
Organization: mad-helpers (https://github.com/mad-helpers/antigravity-account-switcher)
Description:
    Unified local HTTP runtime (:39285 Control Center) and shared route/account engine
    consumed by sync_daemon (:39281), cli.py, and mcp_server.py.
    Dependency direction: sync_daemon -> server -> {ag_suite, migration_engine}.
"""

import datetime
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ag_suite import VERSION, cdp, quota, store, vault  # noqa: E402
import migration_engine  # noqa: E402

LOG_FILE = Path.home() / ".gemini" / "antigravity" / "server.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
store.rotate_log_if_needed(LOG_FILE)


class SafeLogStream:
    def __init__(self, log_path: Path):
        self.log_path = Path(log_path)
        self._f = None
        try:
            self._f = open(self.log_path, "a", encoding="utf-8", buffering=1)
        except Exception:
            pass

    def write(self, s):
        try:
            if self._f:
                self._f.write(s)
                self._f.flush()
        except Exception:
            pass

    def flush(self):
        try:
            if self._f:
                self._f.flush()
        except Exception:
            pass


if "pythonw" in (sys.executable or "").lower():
    _safe_stream = SafeLogStream(LOG_FILE)
    sys.stdout = _safe_stream
    sys.stderr = _safe_stream
else:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        _safe_stream = SafeLogStream(LOG_FILE)
        sys.stdout = _safe_stream
        sys.stderr = _safe_stream

PORT = 39285
DAEMON_PORT = 39281
SCRIPT_DIR = str(ROOT_DIR)
_FALLBACK_APP_DIR = Path.home() / ".gemini" / "antigravity" / "bin" / "app"
APP_DIR = str(ROOT_DIR / "app") if (ROOT_DIR / "app").is_dir() else str(_FALLBACK_APP_DIR)
ACCOUNTS_DIR = str(vault.get_platform_paths()["accounts_dir"])
MANIFEST_PATH = str(vault.get_platform_paths()["manifest_path"])
USER_SETTINGS_PATH = vault.get_platform_paths()["user_settings_path"]
DEFAULT_USER_SETTINGS = store.DEFAULT_USER_SETTINGS
ANTIGRAVITY_OAUTH_SCOPES = vault.ANTIGRAVITY_OAUTH_SCOPES

_LOOPBACK_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

_STATE_CACHE_LOCK = threading.Lock()
_ACTIVE_QUOTA_CACHE: dict[str, dict] = {}
_ACTIVE_QUOTA_TTL = 45.0
_QUOTA_REFRESH_IN_FLIGHT: set[str] = set()

_STRIPPED_LAUNCH_ENV_EXACT = frozenset({
    "ELECTRON_RUN_AS_NODE",
    "NODE_OPTIONS",
    "NODE_PATH",
    "AGY_REQUIRE_AUTHENTICATED_UI_BOOTSTRAP",
    "AGY_BROWSER_ACTIVE_PORT_FILE",
})
_STRIPPED_LAUNCH_ENV_PREFIXES = (
    "ANTIGRAVITY_CSRF_",
    "ANTIGRAVITY_LS_",
    "ANTIGRAVITY_SIDECAR_",
    "ANTIGRAVITY_PROJECT_",
    "ANTIGRAVITY_SOURCE_",
    "ANTIGRAVITY_EXECUTABLE_",
    "ANTIGRAVITY_AGENTAPI_",
    "ANTIGRAVITY_APP_DATA_",
    "ANTIGRAVITY_NODE_",
)


def _clean_launch_env(base_env: dict | None = None) -> dict[str, str]:
    """Return a clean env dict stripping Electron/Node sidecar vars (prevents Antigravity.exe running as Node)."""
    src = os.environ if base_env is None else base_env
    return {
        k: v
        for k, v in src.items()
        if k.upper() not in _STRIPPED_LAUNCH_ENV_EXACT
        and not k.upper().startswith(_STRIPPED_LAUNCH_ENV_PREFIXES)
    }

_DEVTOOLS_CACHE_LOCK = threading.Lock()
_DEVTOOLS_TARGETS_CACHE: dict = {"data": None, "time": 0.0}
_DEVTOOLS_TARGETS_TTL = 5.0

_BROADCAST_LOCK = threading.Lock()
_broadcast_hook = None
_eval_hook = None

_launch_dual_lock = threading.Lock()
_last_dual_launch_time = 0.0
_dual_launch_in_progress = False

_oauth_lock = threading.Lock()
_active_oauth = {"running": False, "auth_url": "", "start_time": 0.0, "target": None}


def register_broadcast_hook(fn) -> None:
    """Register an in-process broadcast callback (used by sync_daemon at startup)."""
    global _broadcast_hook
    with _BROADCAST_LOCK:
        _broadcast_hook = fn


def register_eval_hook(fn) -> None:
    """Register an in-process JS evaluation callback across CDP windows."""
    global _eval_hook
    with _BROADCAST_LOCK:
        _eval_hook = fn


def _poke_sync_daemon_async() -> None:
    """Non-blockingly trigger :39281 /sync?force=1 from separate processes (:39285/CLI/MCP)."""
    def _poke():
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{DAEMON_PORT}/sync?force=1")
            with _LOOPBACK_OPENER.open(req, timeout=0.25):
                pass
        except Exception:
            pass

    threading.Thread(target=_poke, daemon=True).start()


def _notify_daemon_broadcast(extra_toast=None, target_account=None, allow_poke: bool = True) -> None:
    invalidate_state_caches()
    with _BROADCAST_LOCK:
        hook = _broadcast_hook
    if hook is not None:
        try:
            hook(extra_toast=extra_toast, target_account=target_account)
        except TypeError:
            try:
                hook()
            except Exception:
                pass
        except Exception:
            pass
    elif allow_poke:
        _poke_sync_daemon_async()


def _eval_via_hook(js_code: str) -> None:
    with _BROADCAST_LOCK:
        fn = _eval_hook
    if fn is not None:
        try:
            fn(js_code)
        except Exception:
            pass


def invalidate_state_caches() -> None:
    """Clear short-lived quota, CDP target, and migration caches."""
    with _STATE_CACHE_LOCK:
        _ACTIVE_QUOTA_CACHE.clear()
    with _DEVTOOLS_CACHE_LOCK:
        _DEVTOOLS_TARGETS_CACHE["data"] = None
        _DEVTOOLS_TARGETS_CACHE["time"] = 0.0
    cdp.invalidate_devtools_cache()
    try:
        migration_engine.invalidate_migration_caches()
    except Exception:
        pass


def load_manifest() -> dict:
    return store.load_manifest()


def save_manifest(manifest: dict) -> bool:
    ok = store.save_manifest(manifest)
    invalidate_state_caches()
    return ok


def load_user_settings(instance_id=None, account_email=None) -> dict:
    return store.load_user_settings(instance_id=instance_id, account_email=account_email)


def save_user_settings(patch, instance_id=None, account_email=None):
    return store.save_user_settings(patch, instance_id=instance_id, account_email=account_email)


def write_token_to_credential_manager(token) -> bool:
    return vault.write_keychain_token(token)


def is_dual_launching() -> bool:
    """Return True if a dual instance launch is currently swapping credentials temporarily."""
    return _dual_launch_in_progress


def get_devtools_targets(use_cache: bool = True) -> list[dict]:
    """Return active Antigravity CDP targets with thread-safe 5s caching."""
    now = time.time()
    if use_cache:
        with _DEVTOOLS_CACHE_LOCK:
            cached = _DEVTOOLS_TARGETS_CACHE.get("data")
            if cached is not None and (now - _DEVTOOLS_TARGETS_CACHE.get("time", 0.0)) < _DEVTOOLS_TARGETS_TTL:
                return [dict(item) for item in cached]

    targets = cdp.get_devtools_targets(
        account_resolver=lambda iid: store.get_instance_active_account(iid, is_dual_launching=_dual_launch_in_progress),
        use_cache=use_cache,
    )
    with _DEVTOOLS_CACHE_LOCK:
        _DEVTOOLS_TARGETS_CACHE["data"] = [dict(item) for item in targets]
        _DEVTOOLS_TARGETS_CACHE["time"] = time.time()
    return [dict(item) for item in targets]


def ensure_daemon_running() -> bool:
    """Check if sync_daemon HTTP server is healthy on :39281; start it detached if absent."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{DAEMON_PORT}/health")
        with _LOOPBACK_OPENER.open(req, timeout=0.8) as resp:
            if resp.status == 200:
                return True
    except Exception:
        pass

    sys_name = vault.get_current_system()
    bin_dir = vault.get_platform_paths()["bin_dir"]
    daemon_script = bin_dir / "sync_daemon.py"
    if not daemon_script.exists():
        daemon_script = ROOT_DIR / "sync_daemon.py"
    if not daemon_script.exists():
        return False

    if sys_name == "windows":
        try:
            result = subprocess.run(
                ["schtasks.exe", "/Run", "/TN", "AntigravityQuotaMonitor"],
                capture_output=True,
                timeout=8,
                creationflags=0x08000000,
            )
            if result.returncode == 0:
                time.sleep(0.5)
                try:
                    with _LOOPBACK_OPENER.open("http://127.0.0.1:39281/health", timeout=0.9) as resp:
                        if resp.status == 200:
                            return True
                except Exception:
                    pass
        except Exception:
            pass
        try:
            py_exe = shutil.which("pythonw.exe") or sys.executable
            subprocess.Popen(
                [py_exe, str(daemon_script), "--recover-stale"],
                cwd=str(bin_dir if bin_dir.exists() else daemon_script.parent),
                env=_clean_launch_env(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000,
            )
            return True
        except Exception as e:
            print(f"[WATCHDOG] Failed to spawn Windows sync_daemon: {e}", flush=True)
            return False

    try:
        subprocess.Popen(
            [sys.executable, str(daemon_script), "--recover-stale"],
            cwd=str(bin_dir if bin_dir.exists() else daemon_script.parent),
            env=_clean_launch_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception as e:
        print(f"[WATCHDOG] Failed to spawn sync_daemon: {e}", flush=True)
        return False


def _antigravity_executable_paths():
    """Supported Windows installations, in launch-preference order."""
    roots = [
        (os.environ.get("LOCALAPPDATA"), ("Programs", "antigravity")),
        (os.environ.get("ProgramFiles"), ("Antigravity",)),
        (os.environ.get("ProgramFiles(x86)"), ("Antigravity",)),
    ]
    return list(dict.fromkeys(os.path.join(root, *parts, "Antigravity.exe") for root, parts in roots if root))


def _windows_process_session_id(pid):
    """Read the Windows logon session without sending any process control request."""
    import ctypes
    from ctypes import wintypes

    session = wintypes.DWORD()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    query = kernel32.ProcessIdToSessionId
    query.argtypes = [wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    query.restype = wintypes.BOOL
    if not query(int(pid), ctypes.byref(session)):
        raise OSError(ctypes.get_last_error(), "Cannot establish process session ownership")
    return int(session.value)


def _primary_antigravity_processes():
    """Find the primary profile in every supported install, excluding other instances."""
    import psutil

    current_user = psutil.Process().username()
    if not isinstance(current_user, str) or not current_user.strip():
        raise RuntimeError("Cannot establish current user ownership")
    current_user = current_user.casefold()
    current_session = _windows_process_session_id(os.getpid())
    if not isinstance(current_session, int) or current_session < 0:
        raise RuntimeError("Cannot establish current Windows session")
    expected = {os.path.normcase(os.path.abspath(path)) for path in _antigravity_executable_paths()}
    expected_engines = {
        os.path.normcase(os.path.join(os.path.dirname(path), "resources", "bin", "language_server.exe"))
        for path in expected
    }
    primary_data = os.path.normcase(os.path.abspath(str(vault.get_platform_paths("instance_1")["profile_dir"])))
    mains, engines = [], []
    for process in psutil.process_iter(["pid", "name", "exe", "cmdline", "username"]):
        try:
            info = process.info
            name = (info.get("name") or "").lower()
            args = info.get("cmdline") or []
            if name in ("antigravity.exe", "language_server.exe") and not info.get("exe"):
                candidate_user = info.get("username")
                if isinstance(candidate_user, str) and candidate_user.strip() and candidate_user.casefold() != current_user:
                    continue
                raise RuntimeError("Cannot establish application executable ownership")
            exe = os.path.normcase(os.path.abspath(info.get("exe") or ""))
            if not (
                (name == "antigravity.exe" and exe in expected)
                or (name == "language_server.exe" and exe in expected_engines)
            ):
                continue
            process_user = info.get("username")
            if not isinstance(process_user, str) or not process_user.strip():
                raise RuntimeError("Cannot establish application process user ownership")
            if process_user.casefold() != current_user:
                continue
            process_session = _windows_process_session_id(process.pid)
            if not isinstance(process_session, int) or process_session < 0:
                raise RuntimeError("Cannot establish application process session ownership")
            if not isinstance(info.get("cmdline"), (list, tuple)) or not info["cmdline"]:
                raise RuntimeError("Cannot establish application profile ownership")
            same_session = process_session == current_session
            if name == "language_server.exe" and exe in expected_engines:
                app_data = None
                for index, argument in enumerate(args):
                    if argument == "--app_data_dir" and index + 1 < len(args):
                        app_data = args[index + 1]
                    elif argument.startswith("--app_data_dir="):
                        app_data = argument.split("=", 1)[1]
                if app_data == "antigravity":
                    if not same_session:
                        raise RuntimeError("Primary database writer belongs to another session of this user")
                    engines.append(process)
                continue
            if name != "antigravity.exe" or exe not in expected:
                continue
            if any(str(a).startswith(("--type=", "--import")) for a in args):
                continue
            data_dir = None
            for index, argument in enumerate(args):
                if argument.startswith("--user-data-dir="):
                    data_dir = argument.split("=", 1)[1].strip('"')
                elif argument == "--user-data-dir" and index + 1 < len(args):
                    data_dir = args[index + 1].strip('"')
            if data_dir and os.path.normcase(os.path.abspath(data_dir)) != primary_data:
                continue
            if not same_session:
                raise RuntimeError("Primary application belongs to another session of this user")
            mains.append(process)
        except psutil.NoSuchProcess:
            continue
    return mains, engines


def restart_language_server():
    """Restart through the owning app; never terminate an SQLite writer alone."""
    return restart_antigravity()


def _wait_gone(procs, timeout):
    """psutil.wait_procs raises AccessDenied on restricted-token processes (sidecars); poll pid existence instead."""
    import psutil

    deadline = time.time() + timeout
    alive = list(procs)
    while alive:
        alive = [p for p in alive if psutil.pid_exists(p.pid)]
        if not alive or time.time() >= deadline:
            break
        time.sleep(0.2)
    return alive


def _reapply_active_account():
    """Re-assert the chosen primary account before relaunch after shutdown."""
    try:
        paths = vault.get_platform_paths("instance_1")
        active_file = paths["accounts_dir"] / "active_instance_1.txt"
        if not active_file.is_file():
            return
        email = active_file.read_text(encoding="utf-8").strip()
        if not email:
            return
        manifest = load_manifest()
        token = store.read_account_token(email, manifest)
        if not token:
            return
        token_email = vault.extract_token_email(token)
        if token_email and token_email.lower().strip() != email.lower().strip():
            return
        live_email = vault.extract_token_email(vault.get_keychain_token())
        if live_email and live_email.lower().strip() != email.lower().strip():
            fresh = vault.ensure_fresh_token(token, account_email=email, force_refresh=True)
            write_token_to_credential_manager(fresh)
        store.update_app_storage_account(email, instance_id="instance_1")
        print(f"[RESTART] Re-applied active account {email} before relaunch.", flush=True)
    except Exception as error:
        print(f"[RESTART] Could not re-apply active account: {error!r}", flush=True)


def restart_antigravity(force=False):
    """Gracefully close Antigravity, clean stale port files, and relaunch with --remote-debugging-port=0."""
    sys_name = vault.get_current_system()
    if sys_name == "windows":
        import psutil

        try:
            primary_data = os.path.normcase(os.path.abspath(str(vault.get_platform_paths("instance_1")["profile_dir"])))
            mains, engines = [], []
            exe = None
            for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
                try:
                    info = proc.info
                    name = (info.get("name") or "").lower()
                    if name not in ("antigravity.exe", "language_server.exe"):
                        continue
                    p_exe = info.get("exe") or ""
                    args = info.get("cmdline") or []
                    if any(str(a).startswith("--import") for a in args):
                        continue  # sidecar plugin hosts exit with the app and reject wait()
                    if name == "antigravity.exe" and p_exe and os.path.exists(p_exe) and not exe:
                        exe = p_exe
                    data_dir = None
                    for idx, arg in enumerate(args):
                        if arg.startswith("--user-data-dir="):
                            data_dir = arg.split("=", 1)[1].strip('"')
                        elif arg == "--user-data-dir" and idx + 1 < len(args):
                            data_dir = args[idx + 1].strip('"')
                    if data_dir and os.path.normcase(os.path.abspath(data_dir)) != primary_data:
                        continue
                    if name == "antigravity.exe":
                        mains.append(proc)
                    else:
                        engines.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if not exe or not os.path.exists(exe):
                exe = next((path for path in _antigravity_executable_paths() if os.path.exists(path)), None)
            if not exe or not os.path.exists(exe):
                print("[RESTART] Refused: owning executable is unavailable", flush=True)
                return False

            top_mains = [p for p in mains if not any(str(a).startswith("--type=") for a in (p.info.get("cmdline") or []))]
            for process in (top_mains or mains):
                try:
                    subprocess.run(
                        [
                            "powershell",
                            "-NoProfile",
                            "-Command",
                            f"Get-Process -Id {int(process.pid)} -ErrorAction SilentlyContinue | ForEach-Object {{ $_.CloseMainWindow() | Out-Null }}",
                        ],
                        capture_output=True,
                        creationflags=0x08000000,
                        timeout=4,
                    )
                except Exception:
                    pass

            alive = _wait_gone(mains + engines, 4)
            if alive:
                for p in alive:
                    try:
                        p.terminate()
                    except Exception:
                        pass
                still_alive = _wait_gone(alive, 4)
                for p in still_alive:
                    try:
                        p.kill()
                    except Exception:
                        pass

            # Clean up sidecar hosts (1-level or via cmd.exe agy-node wrapper) spawned by the closed primary instance.
            owned_pids = {p.pid for p in mains + engines}
            if owned_pids:
                wrapper_pids = set()
                wrapper_procs = []
                sidecar_procs = []
                for proc in psutil.process_iter(["pid", "name", "ppid", "cmdline"]):
                    try:
                        info = proc.info
                        pname = (info.get("name") or "").lower()
                        cmd = info.get("cmdline") or []
                        if pname == "cmd.exe" and info.get("ppid") in owned_pids and any("agy-node" in str(a).lower() for a in cmd):
                            wrapper_pids.add(proc.pid)
                            wrapper_procs.append(proc)
                        elif pname == "antigravity.exe" and any(str(a).startswith("--import") for a in cmd):
                            sidecar_procs.append((proc, info.get("ppid")))
                    except Exception:
                        continue
                valid_parents = owned_pids | wrapper_pids
                for proc, ppid in sidecar_procs:
                    if ppid in valid_parents:
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                for proc in wrapper_procs:
                    try:
                        proc.terminate()
                    except Exception:
                        pass

            for stale_name in ("DevToolsActivePort", "SingletonLock"):
                stale_file = os.path.join(primary_data, stale_name)
                if os.path.exists(stale_file):
                    try:
                        os.remove(stale_file)
                    except Exception:
                        pass

            _reapply_active_account()
            quota.invalidate_ls_cache("instance_1")
            invalidate_state_caches()
            time.sleep(0.5)

            env = _clean_launch_env()
            env.setdefault("GOMEMLIMIT", "3GiB")
            env.setdefault("GOGC", "50")
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 1
            si.lpDesktop = r"WinSta0\Default"
            proc = subprocess.Popen(
                [exe, "--remote-debugging-port=0"],
                cwd=os.path.dirname(exe),
                env=env,
                startupinfo=si,
                creationflags=0x00000200,
                close_fds=True,
            )
            time.sleep(0.4)
            exit_code = proc.poll()
            if exit_code not in (None, 0):
                print(f"[RESTART] Relaunched {exe} exited immediately with code {exit_code}.", flush=True)
                return False
            print(f"[RESTART] Launched {exe} cleanly with --remote-debugging-port=0.", flush=True)
            return True
        except Exception as error:
            print(f"[RESTART] Safe restart did not complete: {error!r}", flush=True)
            return False

    if sys_name == "macos":
        try:
            subprocess.run(["osascript", "-e", 'tell application "Antigravity" to quit'], capture_output=True)
            deadline = time.time() + 5.0
            while time.time() < deadline:
                res = subprocess.run(["pgrep", "-f", "/Applications/Antigravity.app"], capture_output=True)
                if res.returncode != 0:
                    break
                time.sleep(0.25)
            _reapply_active_account()
            quota.invalidate_ls_cache("instance_1")
            invalidate_state_caches()
            subprocess.Popen(["open", "/Applications/Antigravity.app", "--args", "--remote-debugging-port=0"], env=_clean_launch_env())
            return True
        except Exception as error:
            print(f"[RESTART] macOS restart failed: {error!r}", flush=True)
            return False

    return False


def restart_after_account_switch():
    """Request a graceful restart and report launcher status."""
    try:
        launched = restart_antigravity() is True
    except Exception as error:
        print(f"[RESTART] Safe restart raised {type(error).__name__}", flush=True)
        launched = False
    result = {
        "requested": True,
        "launched": launched,
        "completed": False,
        "status": "launch_requested" if launched else "refused",
    }
    if not launched:
        result["error"] = "Safe restart did not complete; see the restart log for the reason."
    print(f"[RESTART RESULT] {result['status']}", flush=True)
    return result


def is_instance_running(inst_dir_or_name) -> bool:
    """Check if an Antigravity root process with a given user-data-dir is running."""
    if not inst_dir_or_name:
        return False
    needle = inst_dir_or_name.name.lower() if hasattr(inst_dir_or_name, "name") else str(inst_dir_or_name).lower()
    needle_alt = needle.replace("instance_", "instance")
    try:
        import psutil

        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            name = (p.info.get("name") or "").lower()
            if "antigravity" in name:
                cmd = p.info.get("cmdline") or []
                if any(str(arg).startswith(("--type=", "--import")) for arg in cmd):
                    continue
                if any(needle in str(arg).lower() or needle_alt in str(arg).lower() for arg in cmd):
                    return True
    except Exception:
        pass
    return False


def is_instance2_running() -> bool:
    return is_instance_running("Antigravity-Instance2")


def focus_instance(inst_dir) -> bool:
    """Bring an Antigravity instance window to the foreground using strict workbench CDP targeting."""
    focused = False
    sys_name = vault.get_current_system()
    inst_dir = Path(inst_dir)
    dir_name = inst_dir.name

    port_file = inst_dir / "DevToolsActivePort"
    if port_file.exists():
        try:
            lines = port_file.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
            port = int(lines[0]) if lines and lines[0].strip().isdigit() else 0
            if port > 0:
                targets = cdp.fetch_cdp_targets_list(port, timeout=1.0) or []
                page = cdp.select_workbench_target(targets)
                if page and page.get("webSocketDebuggerUrl"):
                    import asyncio
                    import websockets

                    async def _cdp_bring_front():
                        async with websockets.connect(page["webSocketDebuggerUrl"], ping_timeout=1.5) as ws:
                            await ws.send(json.dumps({"id": 1, "method": "Page.bringToFront"}))
                            await ws.recv()

                    asyncio.run(_cdp_bring_front())
                    focused = True
        except Exception:
            pass

    if sys_name == "windows":
        try:
            import ctypes
            from ctypes import wintypes
            import psutil

            inst_pids = set()
            for p in psutil.process_iter(["pid", "name", "cmdline"]):
                name = (p.info.get("name") or "").lower()
                if "antigravity" in name:
                    cmd = p.info.get("cmdline") or []
                    if any(dir_name.lower() in str(arg).lower() for arg in cmd):
                        inst_pids.add(p.info["pid"])

            if inst_pids:
                user32 = ctypes.windll.user32
                WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                matched_hwnds = []

                def enum_cb(hwnd, lparam):
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value in inst_pids:
                        buf = ctypes.create_unicode_buffer(256)
                        user32.GetClassNameW(hwnd, buf, 256)
                        cls = buf.value
                        if cls == "Chrome_WidgetWin_1" or user32.GetWindowTextLengthW(hwnd) > 0:
                            matched_hwnds.append(hwnd)
                    return True

                user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
                for hwnd in matched_hwnds:
                    user32.ShowWindow(hwnd, 1)
                    user32.ShowWindow(hwnd, 9)
                    user32.BringWindowToTop(hwnd)
                    user32.keybd_event(0x12, 0, 0, 0)
                    user32.SetForegroundWindow(hwnd)
                    user32.keybd_event(0x12, 0, 2, 0)
                    focused = True
        except Exception:
            pass
    elif sys_name == "macos":
        try:
            subprocess.run(["osascript", "-e", 'tell application "Antigravity" to activate'], capture_output=True)
            focused = True
        except Exception:
            pass

    return focused


def focus_instance2() -> bool:
    return focus_instance(vault.get_platform_paths("instance_2")["profile_dir"])


def get_instance_dir_for_account(account_key):
    """Resolve or assign an isolated user-data-dir for an account."""
    appdata = vault.get_platform_paths()["appdata_root"]
    manifest = load_manifest()
    resolved_key = store.resolve_account_key(account_key, manifest) or account_key
    entry = manifest.setdefault(resolved_key, {})
    target_email = str(entry.get("email") or resolved_key).lower().strip()

    assigned_inst = entry.get("instance_id")
    if assigned_inst and assigned_inst != "instance_1":
        num = "".join(filter(str.isdigit, str(assigned_inst)))
        if num:
            inst_dir = appdata / f"Antigravity-Instance{num}"
            storage_p = inst_dir / "app_storage.json"
            if storage_p.exists():
                try:
                    acc = json.loads(storage_p.read_text(encoding="utf-8")).get("antigravity:account_email")
                    if not acc or acc.lower().strip() == target_email:
                        return assigned_inst, inst_dir
                except Exception:
                    return assigned_inst, inst_dir
            else:
                return assigned_inst, inst_dir

    used_slots = set()
    try:
        for inst_dir in sorted(appdata.glob("Antigravity-Instance*")):
            if not inst_dir.is_dir():
                continue
            dir_name = inst_dir.name
            num_str = "".join(filter(str.isdigit, dir_name))
            if num_str and num_str.isdigit():
                used_slots.add(int(num_str))

            storage_p = inst_dir / "app_storage.json"
            if storage_p.exists():
                try:
                    acc = json.loads(storage_p.read_text(encoding="utf-8")).get("antigravity:account_email")
                    if acc and acc.lower().strip() == target_email:
                        inst_id = f"instance_{num_str}" if num_str else dir_name.lower().replace("-", "_")
                        entry["instance_id"] = inst_id
                        manifest[resolved_key] = entry
                        save_manifest(manifest)
                        return inst_id, inst_dir
                except Exception:
                    pass
    except Exception:
        pass

    for acc, data in manifest.items():
        if acc.lower().strip() == target_email or not isinstance(data, dict):
            continue
        i_id = str(data.get("instance_id") or "")
        num = "".join(filter(str.isdigit, i_id))
        if num and num.isdigit():
            used_slots.add(int(num))

    slot = 2
    while slot in used_slots:
        slot += 1

    while (appdata / f"Antigravity-Instance{slot}").exists():
        cand_storage = appdata / f"Antigravity-Instance{slot}" / "app_storage.json"
        if cand_storage.exists():
            try:
                c_acc = json.loads(cand_storage.read_text(encoding="utf-8")).get("antigravity:account_email")
                if c_acc and c_acc.lower().strip() == target_email:
                    break
            except Exception:
                pass
        slot += 1

    inst_id = f"instance_{slot}"
    target_dir = appdata / f"Antigravity-Instance{slot}"
    target_dir.mkdir(parents=True, exist_ok=True)
    entry["instance_id"] = inst_id
    manifest[resolved_key] = entry
    save_manifest(manifest)
    return inst_id, target_dir


def launch_dual_instance(account_key, project_path=None):
    """Launch or focus an isolated concurrent Antigravity instance with --remote-debugging-port=0."""
    global _last_dual_launch_time, _dual_launch_in_progress
    with _launch_dual_lock:
        now = time.time()
        if now - _last_dual_launch_time < 2.0:
            return {"success": True, "msg": "در حال آماده‌سازی پنجره..."}
        _last_dual_launch_time = now

        manifest = load_manifest()
        resolved_key = store.resolve_account_key(account_key, manifest) if account_key else None
        if not resolved_key and not account_key:
            active_email = ""
            try:
                active_q = quota.fetch_quota_and_tier()
                if active_q and active_q.get("email"):
                    active_email = active_q["email"]
            except Exception:
                pass
            if not active_email and manifest:
                active_email = list(manifest.keys())[0]
            for k, v in manifest.items():
                if k.lower() != active_email.lower() and (v.get("email") or "").lower() != active_email.lower():
                    resolved_key = k
                    break

        entry = manifest.get(resolved_key) if resolved_key else None
        if not entry:
            return {"success": False, "error": f"حساب '{account_key}' در لیست حساب‌ها یافت نشد"}
        account_key = resolved_key

        target_token = store.read_account_token(account_key, manifest)
        if not target_token:
            return {
                "success": False,
                "needs_reauth": True,
                "account": account_key,
                "error": f"حساب '{account_key}' نیاز به ورود مجدد دارد. لطفاً روی دکمه ورود با گوگل کلیک کنید.",
            }

        token_email = vault.extract_token_email(target_token)
        if token_email and token_email.lower().strip() != str(entry.get("email") or account_key).lower().strip():
            entry["needs_reauth"] = True
            entry["token_file"] = ""
            manifest[account_key] = entry
            save_manifest(manifest)
            return {
                "success": False,
                "needs_reauth": True,
                "account": account_key,
                "error": f"توکن ذخیره شده متعلق به '{token_email}' است و با حساب '{account_key}' تطابق ندارد. لطفاً روی دکمه ورود با گوگل کلیک کنید.",
            }

        if not vault.check_token_has_aicode(target_token):
            entry["needs_reauth"] = True
            manifest[account_key] = entry
            save_manifest(manifest)
            return {
                "success": False,
                "needs_reauth": True,
                "missing_aicode": True,
                "account": account_key,
                "error": f"حساب '{account_key}' با مجوزهای قدیمی ثبت شده و دسترسی لازم برای مدل‌های هوش مصنوعی (aicode) را ندارد. لطفاً یک‌بار روی دکمه ورود با گوگل کلیک کنید تا دسترسی فعال شود.",
            }

        target_token = vault.ensure_fresh_token(target_token, account_email=account_key, force_refresh=True)
        sys_name = vault.get_current_system()
        inst_id, target_inst_dir = get_instance_dir_for_account(account_key)

        if not project_path:
            try:
                prof_man = migration_engine.load_profile_sync_manifest()
                for _, pdata in prof_man.get("project_profiles", {}).items():
                    assigned = pdata.get("assigned_accounts", [])
                    if any(account_key.lower() in a.lower() for a in assigned):
                        cand_path = pdata.get("path")
                        if cand_path and os.path.exists(cand_path):
                            project_path = cand_path
                            break
            except Exception:
                pass

        if is_instance_running(target_inst_dir):
            if focus_instance(target_inst_dir):
                return {
                    "success": True,
                    "account": account_key,
                    "instance_id": inst_id,
                    "user_data_dir": str(target_inst_dir),
                    "project_path": project_path or "",
                    "msg": f"پنجره حساب {account_key} فعال شد",
                }
            try:
                import psutil

                needle = target_inst_dir.name.lower()
                for p in psutil.process_iter(["pid", "name", "cmdline"]):
                    if "antigravity" in (p.info.get("name") or "").lower():
                        cmd = p.info.get("cmdline") or []
                        if any(needle in str(arg).lower() for arg in cmd):
                            p.kill()
                time.sleep(0.5)
            except Exception:
                pass

        primary_token = vault.get_keychain_token()
        active_email = vault.extract_token_email(primary_token) if primary_token else ""
        if not active_email:
            active_email = store.get_instance_active_account("instance_1", is_dual_launching=True)
        if not primary_token and active_email and active_email in manifest:
            primary_token = store.read_account_token(active_email, manifest)

        if sys_name == "windows":
            target_inst_dir.mkdir(parents=True, exist_ok=True)
            for f_name in ("DevToolsActivePort", "lockfile", "SingletonLock", "SingletonCookie", "SingletonSocket"):
                f_p = target_inst_dir / f_name
                if f_p.exists():
                    try:
                        f_p.unlink()
                    except Exception:
                        pass

            designated_pid = ""
            try:
                prof_man = migration_engine.load_profile_sync_manifest()
                for pid, pdata in prof_man.get("project_profiles", {}).items():
                    if project_path and (pdata.get("path", "").lower() == str(project_path).lower() or pid == project_path):
                        designated_pid = pid
                        break
                    if not designated_pid and any(account_key.lower() in a.lower() for a in pdata.get("assigned_accounts", [])):
                        designated_pid = pid
            except Exception:
                pass

            try:
                storage_p = target_inst_dir / "app_storage.json"
                s_data = json.loads(storage_p.read_text(encoding="utf-8")) if storage_p.exists() else {}
                if designated_pid:
                    s_data["new-convo-last-selected-project"] = designated_pid
                s_data["antigravity:instance_id"] = inst_id
                s_data["antigravity:account_email"] = account_key
                s_data["agy.onboarding.lastLoginUsername"] = account_key
                s_data["jetski.onboarding.lastLoginUsername"] = account_key
                s_data["agy.onboarding.lastLoginIsGcpTos"] = "false"
                s_data["jetski.onboarding.lastLoginIsGcpTos"] = "false"
                if project_path:
                    s_data["antigravity:designated_project"] = project_path
                sec_quota = quota.fetch_quota_and_tier(target_token)
                if sec_quota:
                    s_data["antigravity:active_quota"] = json.dumps(sec_quota, ensure_ascii=False)
                store.atomic_write_json(storage_p, s_data)
            except Exception:
                pass

            store.write_active_instance_account(inst_id, account_key)

            exe = next((p for p in _antigravity_executable_paths() if os.path.exists(p)), None)
            if not exe:
                try:
                    import psutil

                    for p in psutil.process_iter(["name", "exe"]):
                        if "antigravity" in (p.info.get("name") or "").lower() and p.info.get("exe"):
                            if os.path.exists(p.info["exe"]):
                                exe = p.info["exe"]
                                break
                except Exception:
                    pass
            if not exe:
                return {"success": False, "error": "فایل اجرایی Antigravity.exe یافت نشد"}

            _dual_launch_in_progress = True
            write_token_to_credential_manager(target_token)

            proc_env = _clean_launch_env()
            tok_str = target_token if isinstance(target_token, str) else json.dumps(target_token, ensure_ascii=False)
            proc_env["ANTIGRAVITY_TOKEN"] = tok_str
            proc_env["ANTIGRAVITY_ACCOUNT"] = account_key
            proc_env["ANTIGRAVITY_INSTANCE_ID"] = inst_id
            proc_env["GEMINI_CLI_AUTH_TOKEN"] = tok_str
            proc_env["GOOGLE_OAUTH_TOKEN"] = tok_str
            proc_env["CLOUDCODE_AUTH_TOKEN"] = tok_str

            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 1
            si.lpDesktop = r"WinSta0\Default"

            CREATE_NEW_PROCESS_GROUP = 0x00000200
            CREATE_BREAKAWAY_FROM_JOB = 0x01000000
            cmd = [exe, f"--user-data-dir={str(target_inst_dir)}", "--remote-debugging-port=0"]
            if project_path and os.path.exists(project_path):
                cmd.append(project_path)

            existing_ls_pids = set()
            try:
                import psutil

                for p in psutil.process_iter(["pid", "name"]):
                    if "language_server" in (p.info.get("name") or "").lower():
                        existing_ls_pids.add(p.info["pid"])
            except Exception:
                pass

            try:
                proc = subprocess.Popen(cmd, env=proc_env, startupinfo=si, creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB)
            except Exception:
                proc = subprocess.Popen(cmd, env=proc_env, startupinfo=si, creationflags=CREATE_NEW_PROCESS_GROUP)

            def _post_launch_worker(target_acc, orig_pids, target_dir_path, target_inst_id):
                global _dual_launch_in_progress
                port_ready = False
                target_port_file = Path(target_dir_path) / "DevToolsActivePort"
                poll_deadline = time.time() + 12.0

                while time.time() < poll_deadline:
                    time.sleep(0.5)
                    if target_port_file.exists():
                        try:
                            lines = target_port_file.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
                            if lines and lines[0].strip().isdigit():
                                p_num = int(lines[0].strip())
                                if cdp.is_valid_cdp_port(p_num, require_workbench=True, timeout=0.2):
                                    port_ready = True
                                    break
                        except Exception:
                            pass
                    try:
                        live_ports = cdp.discover_live_cdp_ports()
                        if target_inst_id in live_ports:
                            cdp.heal_devtools_port_file(target_port_file, live_ports[target_inst_id])
                            port_ready = True
                            break
                    except Exception:
                        pass

                if port_ready:
                    ls_deadline = time.time() + 8.0
                    try:
                        import psutil

                        while time.time() < ls_deadline:
                            time.sleep(0.5)
                            found_ls = any(
                                "language_server" in (p.info.get("name") or "").lower() and p.info["pid"] not in orig_pids
                                for p in psutil.process_iter(["pid", "name"])
                            )
                            if found_ls:
                                break
                    except Exception:
                        pass
                    time.sleep(2.0)

                try:
                    if primary_token:
                        fresh_primary = vault.ensure_fresh_token(primary_token, account_email=active_email)
                        write_token_to_credential_manager(fresh_primary)
                        print(
                            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [MULTI-INSTANCE] Restored primary token ({target_inst_id} -> {target_acc}).",
                            flush=True,
                        )
                finally:
                    _dual_launch_in_progress = False
                    invalidate_state_caches()

                for _ in range(10):
                    time.sleep(0.5)
                    if focus_instance(target_dir_path):
                        break

            threading.Thread(
                target=_post_launch_worker,
                args=(account_key, existing_ls_pids, target_inst_dir, inst_id),
                daemon=True,
            ).start()

            clean_name = entry.get("name") or account_key.split("@")[0]
            return {
                "success": True,
                "pid": proc.pid,
                "account": account_key,
                "instance_id": inst_id,
                "user_data_dir": str(target_inst_dir),
                "msg": f"پنجره جدید ({clean_name}) با موفقیت اجرا شد",
            }

        if sys_name == "macos":
            app_path = "/Applications/Antigravity.app"
            if not os.path.exists(app_path):
                return {"success": False, "error": "Antigravity.app not found on macOS"}
            target_inst_dir.mkdir(parents=True, exist_ok=True)
            store.write_active_instance_account(inst_id, account_key)
            store.update_app_storage_account(account_key, instance_id=inst_id)
            _dual_launch_in_progress = True
            write_token_to_credential_manager(target_token)
            cmd = ["open", "-n", "-a", app_path, "--args", f"--user-data-dir={str(target_inst_dir)}", "--remote-debugging-port=0"]
            if project_path and os.path.exists(project_path):
                cmd.append(project_path)
            proc = subprocess.Popen(cmd)

            def _restore_primary_mac():
                global _dual_launch_in_progress
                try:
                    deadline = time.time() + 12.0
                    port_file = target_inst_dir / "DevToolsActivePort"
                    while time.time() < deadline:
                        time.sleep(0.5)
                        if port_file.exists():
                            break
                        if inst_id in cdp.discover_live_cdp_ports():
                            break
                    if primary_token:
                        write_token_to_credential_manager(primary_token)
                finally:
                    _dual_launch_in_progress = False
                    invalidate_state_caches()

            threading.Thread(target=_restore_primary_mac, daemon=True).start()
            return {
                "success": True,
                "pid": proc.pid,
                "account": account_key,
                "instance_id": inst_id,
                "user_data_dir": str(target_inst_dir),
            }

        return {"success": False, "error": "Multi-instance launch is optimized for Windows/macOS"}


def switch_account(account_key, no_restart=True):
    """Switch active Antigravity account in OS vault and return frozen v3.0 schema."""
    manifest = load_manifest()
    resolved_key = store.resolve_account_key(account_key, manifest)
    default_restart = {
        "requested": not bool(no_restart),
        "launched": False,
        "completed": False,
        "status": "not_requested" if no_restart else "refused",
    }

    if not resolved_key or resolved_key not in manifest:
        return {
            "success": False,
            "account": str(account_key or ""),
            "email": "",
            "quota": {},
            "authState": quota.get_live_ide_auth_state("instance_1", use_cache=True),
            "restart": default_restart,
            "error": f"Account '{account_key}' not found",
        }

    entry = manifest[resolved_key]
    email_canon = str(entry.get("email") or resolved_key).lower().strip()
    token = store.read_account_token(resolved_key, manifest)

    if not token:
        entry["needs_reauth"] = True
        manifest[resolved_key] = entry
        save_manifest(manifest)
        return {
            "success": False,
            "needs_reauth": True,
            "account": resolved_key,
            "email": email_canon,
            "quota": {},
            "authState": quota.get_live_ide_auth_state("instance_1", use_cache=True),
            "restart": default_restart,
            "error": f"حساب '{resolved_key}' نیاز به ورود مجدد دارد. لطفاً روی دکمه ورود با گوگل کلیک کنید.",
        }

    token_email = vault.extract_token_email(token)
    if token_email and token_email.lower().strip() != email_canon:
        entry["needs_reauth"] = True
        entry["token_file"] = ""
        manifest[resolved_key] = entry
        save_manifest(manifest)
        return {
            "success": False,
            "needs_reauth": True,
            "account": resolved_key,
            "email": email_canon,
            "quota": {},
            "authState": quota.get_live_ide_auth_state("instance_1", use_cache=True),
            "restart": default_restart,
            "error": f"توکن ذخیره شده متعلق به '{token_email}' است و با حساب '{resolved_key}' تطابق ندارد. لطفاً روی دکمه ورود با گوگل کلیک کنید.",
        }

    if not vault.check_token_has_aicode(token):
        entry["needs_reauth"] = True
        manifest[resolved_key] = entry
        save_manifest(manifest)
        return {
            "success": False,
            "needs_reauth": True,
            "missing_aicode": True,
            "account": resolved_key,
            "email": email_canon,
            "quota": {},
            "authState": quota.get_live_ide_auth_state("instance_1", use_cache=True),
            "restart": default_restart,
            "error": f"حساب '{resolved_key}' با مجوزهای قدیمی ثبت شده و دسترسی لازم برای مدل‌های هوش مصنوعی (aicode) را ندارد. لطفاً یک‌بار روی دکمه ورود با گوگل کلیک کنید تا دسترسی فعال شود.",
        }

    fresh_token = vault.ensure_fresh_token(token, account_email=email_canon, force_refresh=True)
    if fresh_token:
        token = fresh_token
    write_token_to_credential_manager(token)

    quota_data = None
    try:
        fresh_q = quota.fetch_quota_and_tier(token, force_refresh=True)
        if fresh_q and fresh_q.get("session"):
            quota_data = fresh_q
            quota_data["email"] = email_canon
            if not quota_data.get("name"):
                quota_data["name"] = entry.get("name") or (email_canon.split("@")[0].split(".")[0].capitalize() if "@" in email_canon else "User")
    except Exception:
        quota_data = None

    if not quota_data:
        quota_data = quota._manifest_fallback_quota(email_canon, entry)

    entry["remaining_pct"] = quota_data.get("session", {}).get("remaining_pct", entry.get("remaining_pct", 100.0))
    entry["weekly_remaining_pct"] = quota_data.get("weekly", {}).get("remaining_pct", entry.get("weekly_remaining_pct", 100.0))
    entry["weekly_resets_in"] = quota_data.get("weekly", {}).get("resets_in", entry.get("weekly_resets_in", "Ready"))
    entry["tier"] = quota_data.get("tier", entry.get("tier", "Google AI Pro"))
    entry["tier_code"] = quota_data.get("tier_code", entry.get("tier_code", "pro"))
    entry["needs_reauth"] = False
    entry["last_Active"] = time.strftime("%Y-%m-%d %H:%M:%S")
    manifest[resolved_key] = entry
    save_manifest(manifest)

    store.atomic_write_json(vault.get_platform_paths("instance_1")["active_quota_path"], quota_data)
    store.write_active_instance_account("instance_1", email_canon)
    store.update_app_storage_account(email_canon, quota_data=quota_data, instance_id="instance_1")

    quota.invalidate_ls_cache("instance_1")
    invalidate_state_caches()

    try:
        ensure_daemon_running()
    except Exception:
        pass

    auth_state = quota.get_live_ide_auth_state("instance_1", use_cache=False)
    quota_data["live_ide_email"] = auth_state.get("live_ide_email")
    quota_data["credential_email"] = auth_state.get("credential_email")
    quota_data["session_mismatch"] = bool(auth_state.get("session_mismatch", False))

    result = {
        "success": True,
        "account": resolved_key,
        "email": email_canon,
        "quota": quota_data,
        "authState": auth_state,
        "restart": {"requested": False, "launched": False, "completed": False, "status": "not_requested"},
    }
    if not no_restart:
        result["restart"] = restart_after_account_switch()
        if result["restart"]["status"] == "refused":
            result["warning"] = "حساب تغییر یافت؛ راه‌اندازی مجدد ایمن انجام نشد. وضعیت برنامه را بررسی کنید."

    with _BROADCAST_LOCK:
        has_hook = _broadcast_hook is not None
    if not has_hook:
        _poke_sync_daemon_async()

    return result


def save_current_account():
    """Save active OS credential account atomically to ~/.gemini/accounts."""
    token = vault.get_keychain_token()
    if not token:
        return {"success": False, "error": "No active account found in credential manager"}

    quota_data = quota.fetch_quota_and_tier(token)
    email = (quota_data.get("email") if quota_data else None) or vault.extract_token_email(token, check_manifest=False) or "unknown@antigravity.ai"
    email = str(email).lower().strip()
    tier = (quota_data.get("tier") if quota_data else None) or "Free"
    tier_code = (quota_data.get("tier_code") if quota_data else None) or "free"
    rem = (quota_data.get("session", {}).get("remaining_pct") if quota_data else 100.0)
    w_rem = (quota_data.get("weekly", {}).get("remaining_pct") if quota_data else 100.0)
    w_res = (quota_data.get("weekly", {}).get("resets_in") if quota_data else "Ready")

    acc_dir = vault.get_platform_paths()["accounts_dir"]
    acc_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in ("@", ".", "_", "-") else "_" for c in email)
    token_file = str(acc_dir / f"{safe_name}.token")
    tok_out = token if isinstance(token, str) else json.dumps(token, ensure_ascii=False)
    store.atomic_write_text(token_file, tok_out)

    clean_name = (quota_data.get("name") if quota_data else "") or (email.split("@")[0].split(".")[0].capitalize() if "@" in email else email)
    avatar = (quota_data.get("avatar") if quota_data else "") or ""
    manifest = load_manifest()
    manifest[email] = {
        "label": email,
        "name": clean_name,
        "avatar": avatar,
        "email": email,
        "tier": tier,
        "tier_code": tier_code,
        "remaining_pct": rem,
        "weekly_remaining_pct": w_rem,
        "weekly_resets_in": w_res,
        "token_file": token_file,
        "needs_reauth": False,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_manifest(manifest)
    return {"success": True, "account": email, "email": email, "tier": tier}


def import_token(token_str):
    """Import an OAuth token payload and register the account in manifest."""
    if not token_str or not str(token_str).strip():
        return {"success": False, "error": "توکن خالی است"}
    token_str = str(token_str).strip()
    quota_data = quota.fetch_quota_and_tier(token_str)
    if not quota_data:
        acc_tok, ref_tok = vault.parse_token_payload(token_str)
        if not acc_tok and not ref_tok:
            return {"success": False, "error": "فرمت توکن نامعتبر است"}
        email = vault.extract_token_email(token_str, check_manifest=False) or f"imported_{int(time.time())}@antigravity.ai"
        tier = "Google AI"
        tier_code = "pro"
        rem = 100.0
        w_rem = 100.0
        w_res = "Ready"
    else:
        email = quota_data.get("email") or vault.extract_token_email(token_str, check_manifest=False) or f"account_{int(time.time())}@gmail.com"
        tier = quota_data.get("tier") or "Free"
        tier_code = quota_data.get("tier_code") or "free"
        rem = quota_data.get("session", {}).get("remaining_pct", 100.0)
        w_rem = quota_data.get("weekly", {}).get("remaining_pct", 100.0)
        w_res = quota_data.get("weekly", {}).get("resets_in", "Ready")

    email = str(email).lower().strip()
    acc_dir = vault.get_platform_paths()["accounts_dir"]
    acc_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in ("@", ".", "_", "-") else "_" for c in email)
    token_file = str(acc_dir / f"{safe_name}.token")
    store.atomic_write_text(token_file, token_str)

    clean_name = (quota_data.get("name") if quota_data else "") or (email.split("@")[0].split(".")[0].capitalize() if "@" in email else email)
    avatar = (quota_data.get("avatar") if quota_data else "") or ""
    manifest = load_manifest()
    manifest[email] = {
        "label": email,
        "name": clean_name,
        "avatar": avatar,
        "email": email,
        "tier": tier,
        "tier_code": tier_code,
        "remaining_pct": rem,
        "weekly_remaining_pct": w_rem,
        "weekly_resets_in": w_res,
        "token_file": token_file,
        "needs_reauth": False,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_manifest(manifest)
    return {"success": True, "account": email, "email": email, "tier": tier}


def logout_account(no_restart=False):
    """Clear OS credential vault and optionally trigger graceful Antigravity restart."""
    vault.clear_keychain_token()
    active_file = vault.get_platform_paths("instance_1")["accounts_dir"] / "active_instance_1.txt"
    try:
        if active_file.is_file():
            active_file.unlink()
    except Exception:
        pass
    quota.invalidate_ls_cache("instance_1")
    invalidate_state_caches()
    if not no_restart:
        restart_antigravity()
    return {"success": True}


def delete_account(account_key):
    """Remove an account from manifest.json AND delete its .token file(s) from disk."""
    manifest = load_manifest()
    resolved = account_key if account_key in manifest else store.resolve_account_key(account_key, manifest)
    if not resolved or resolved not in manifest:
        return {"success": False, "error": "Account not found in list"}

    entry = manifest.get(resolved)
    acc_dir = vault.get_platform_paths()["accounts_dir"]
    candidates: list[Path] = []
    if isinstance(entry, dict) and entry.get("token_file"):
        candidates.append(Path(entry["token_file"]))
    for raw_id in (resolved, entry.get("email") if isinstance(entry, dict) else None):
        if raw_id:
            safe_id = "".join(c if c.isalnum() or c in ("@", ".", "_", "-") else "_" for c in str(raw_id).strip())
            if safe_id:
                candidates.append(acc_dir / f"{safe_id}.token")
    for tf in candidates:
        try:
            if tf.is_file():
                tf.unlink()
        except Exception:
            pass

    del manifest[resolved]
    save_manifest(manifest)
    return {"success": True, "deleted": resolved}


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_running_browser_profile(process_name="chrome.exe"):
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Get-CimInstance Win32_Process | Where-Object {{ $_.Name -eq '{process_name}' -and $_.CommandLine -notmatch '--type=' }} | Select-Object -ExpandProperty CommandLine",
            ],
            text=True,
            timeout=4,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        for line in out.splitlines():
            if "--profile-directory=" in line:
                m = re.search(r'--profile-directory=["\']?([^"\']+)["\']?', line)
                if m:
                    return m.group(1).strip()
    except Exception:
        pass
    return None


def open_browser_url(url: str) -> bool:
    sys_name = vault.get_current_system()
    if sys_name == "windows":
        chrome_candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        chrome_exe = next((p for p in chrome_candidates if os.path.exists(p)), None)
        active_profile = get_running_browser_profile("chrome.exe")

        opened = False
        if chrome_exe:
            try:
                cmd_args = [chrome_exe]
                if active_profile:
                    cmd_args.append(f"--profile-directory={active_profile}")
                cmd_args.append(url)
                subprocess.Popen(cmd_args)
                opened = True
            except Exception:
                pass
        if not opened:
            try:
                subprocess.Popen(["rundll32.exe", "url.dll,FileProtocolHandler", url])
                opened = True
            except Exception:
                pass
        if not opened:
            try:
                subprocess.Popen(["explorer.exe", url])
                opened = True
            except Exception:
                pass
        return opened

    if sys_name == "macos":
        try:
            subprocess.Popen(["open", url])
            return True
        except Exception:
            pass

    import webbrowser

    try:
        webbrowser.open(url)
        return True
    except Exception:
        return False


def run_google_oauth_flow(target_account=None, on_url=None, on_complete=None):
    """Run local OAuth2 loopback flow with deadline loop and access_token validation."""
    save_current_account()

    port = find_free_port()
    redirect_uri = f"http://localhost:{port}/oauth2callback"
    params = {
        "client_id": vault.OAUTH_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": vault.ANTIGRAVITY_OAUTH_SCOPES,
        "access_type": "offline",
        "prompt": "select_account consent",
    }
    if target_account:
        params["login_hint"] = target_account.strip()

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    result = {"success": False, "email": None, "error": None}

    if on_url:
        try:
            on_url(auth_url)
        except Exception:
            pass

    class OAuthCallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/oauth2callback":
                self.send_response(404)
                self.end_headers()
                return
            qs = urllib.parse.parse_qs(parsed.query)
            code = qs.get("code", [None])[0]
            error = qs.get("error", [None])[0]
            if error:
                result["error"] = f"Google OAuth error: {error}"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<html><body style='background:#111;color:#fff;text-align:center;padding:50px;'><h2>Google Sign-in Canceled</h2></body></html>")
                return
            if code:
                try:
                    exchange_params = urllib.parse.urlencode({
                        "client_id": vault.OAUTH_CLIENT_ID,
                        "client_secret": vault.OAUTH_CLIENT_SECRET,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        "https://oauth2.googleapis.com/token",
                        data=exchange_params,
                        headers={"User-Agent": "Mozilla/5.0"},
                    )
                    with urllib.request.urlopen(req, timeout=10.0) as resp:
                        tok_data = json.loads(resp.read().decode("utf-8"))

                    access_tok = tok_data.get("access_token")
                    if not access_tok:
                        raise RuntimeError("Google did not return an access token")
                    refresh_tok = tok_data.get("refresh_token")
                    expires_in = tok_data.get("expires_in", 3600)

                    exp_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=expires_in)
                    exp_iso = exp_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

                    token_payload = {
                        "token": {
                            "access_token": access_tok,
                            "token_type": tok_data.get("token_type", "Bearer"),
                            "refresh_token": refresh_tok,
                            "expiry": exp_iso,
                            "scope": tok_data.get("scope", vault.ANTIGRAVITY_OAUTH_SCOPES),
                        },
                        "auth_method": "consumer",
                        "id_token": tok_data.get("id_token"),
                    }
                    token_str = json.dumps(token_payload, ensure_ascii=False)

                    quota_data = quota.fetch_quota_and_tier(token_str)
                    email = quota_data.get("email") if quota_data else None
                    if not email:
                        try:
                            req_u = urllib.request.Request(
                                "https://www.googleapis.com/oauth2/v3/userinfo",
                                headers={"Authorization": f"Bearer {access_tok}"},
                            )
                            with urllib.request.urlopen(req_u, timeout=5.0) as resp_u:
                                email = json.loads(resp_u.read().decode("utf-8")).get("email")
                        except Exception:
                            pass
                    if not email:
                        email = vault.extract_token_email(token_str, check_manifest=False)
                    if not email:
                        email = target_account or f"account_{int(time.time())}@gmail.com"
                    email = str(email).lower().strip()

                    if target_account and email != target_account.lower().strip():
                        err_msg = f"شما با حساب ({email}) وارد شدید، اما حساب مورد نظر ({target_account}) است."
                        result["error"] = err_msg
                        result["success"] = False
                        err_html = (
                            f"<!DOCTYPE html><html dir='rtl' lang='fa'><head><meta charset='utf-8'>"
                            f"<title>Account Mismatch</title></head>"
                            f"<body style='background:#07090e;color:#f8fafc;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;'>"
                            f"<div style='background:#1e1212;border:1px solid #ef4444;border-radius:20px;padding:32px;max-width:460px;text-align:center;'>"
                            f"<h2>عدم تطابق حساب گوگل</h2><p>{email} != {target_account}</p></div></body></html>"
                        )
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(err_html.encode("utf-8"))
                        return

                    acc_dir = vault.get_platform_paths()["accounts_dir"]
                    acc_dir.mkdir(parents=True, exist_ok=True)
                    safe_name = "".join(c if c.isalnum() or c in ("@", ".", "_", "-") else "_" for c in email)
                    token_file = str(acc_dir / f"{safe_name}.token")
                    store.atomic_write_text(token_file, token_str)

                    tier = quota_data.get("tier") if quota_data else "Google AI"
                    tier_code = quota_data.get("tier_code") if quota_data else "pro"
                    rem = quota_data.get("session", {}).get("remaining_pct", 100.0) if quota_data else 100.0
                    w_rem = quota_data.get("weekly", {}).get("remaining_pct", 100.0) if quota_data else 100.0
                    w_res = quota_data.get("weekly", {}).get("resets_in", "Ready") if quota_data else "Ready"
                    clean_name = (quota_data.get("name") if quota_data else "") or (email.split("@")[0].split(".")[0].capitalize() if "@" in email else email)
                    avatar = (quota_data.get("avatar") if quota_data else "") or ""

                    manifest = load_manifest()
                    manifest[email] = {
                        "label": email,
                        "name": clean_name,
                        "avatar": avatar,
                        "email": email,
                        "tier": tier,
                        "tier_code": tier_code,
                        "remaining_pct": rem,
                        "weekly_remaining_pct": w_rem,
                        "weekly_resets_in": w_res,
                        "token_file": token_file,
                        "needs_reauth": False,
                        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    save_manifest(manifest)

                    result["success"] = True
                    result["email"] = email
                    result["tier"] = tier

                    ok_html = (
                        f"<!DOCTYPE html><html dir='rtl' lang='fa'><head><meta charset='utf-8'>"
                        f"<title>ورود موفقیت‌آمیز | Antigravity</title></head>"
                        f"<body style='background:#07090e;color:#f8fafc;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;'>"
                        f"<div style='background:#121826;border:1px solid #10b981;border-radius:24px;padding:36px;max-width:440px;text-align:center;'>"
                        f"<h2>حساب گوگل با موفقیت متصل شد</h2><p>{email}</p></div></body></html>"
                    )
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(ok_html.encode("utf-8"))
                except Exception as e:
                    result["error"] = str(e)
                    self.send_response(500)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(f"<html><body style='background:#111;color:#fff;text-align:center;padding:50px;'><h2>Error</h2><p>{e}</p></body></html>".encode("utf-8"))

        def log_message(self, format, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", port), OAuthCallbackHandler)
    open_browser_url(auth_url)

    deadline = time.time() + 180
    while time.time() < deadline and not (result["success"] or result["error"]):
        httpd.timeout = max(1, min(5, deadline - time.time()))
        httpd.handle_request()
    httpd.server_close()
    if not (result["success"] or result["error"]):
        result["error"] = "Google sign-in timed out"

    if on_complete:
        on_complete(result)

    return result


def start_shared_oauth_flow(target_account=None, auto_switch=False) -> str:
    """Start or reuse an OAuth login session and optionally auto-switch/restart on completion."""
    with _oauth_lock:
        now = time.time()
        if (
            _active_oauth["running"]
            and (now - _active_oauth["start_time"] < 120)
            and _active_oauth["auth_url"]
            and (_active_oauth.get("target") == target_account)
        ):
            try:
                open_browser_url(_active_oauth["auth_url"])
            except Exception:
                pass
            return _active_oauth["auth_url"]

        _active_oauth["running"] = True
        _active_oauth["auth_url"] = ""
        _active_oauth["start_time"] = now
        _active_oauth["target"] = target_account

    try:
        save_current_account()
    except Exception:
        pass

    auth_url_holder = []

    def _on_url(u):
        with _oauth_lock:
            _active_oauth["auth_url"] = u
        auth_url_holder.append(u)
        safe_url = json.dumps(u)
        toast_msg = json.dumps(
            f'مرورگر باز شد. اگر باز نشد، <a href="{u}" target="_blank" style="color:#93c5fd;text-decoration:underline;font-weight:700;">اینجا کلیک کنید</a>',
            ensure_ascii=False,
        )
        js_code = f"""(() => {{
            try {{ window.open({safe_url}, '_blank'); }} catch(e) {{}}
            if (typeof window.__showSwitcherToast === 'function') {{
                window.__showSwitcherToast({toast_msg});
            }}
            if (typeof window.__onOAuthUrlReady === 'function') {{
                window.__onOAuthUrlReady({safe_url});
            }}
        }})()"""
        _eval_via_hook(js_code)

    def _done(res):
        with _oauth_lock:
            _active_oauth["running"] = False
        success = res.get("success", False)
        email = res.get("email", "")
        will_switch = bool(success and auto_switch and email)
        msg = (
            f"حساب {email} با موفقیت افزوده شد!" + (" در حال سوئیچ و ری‌استارت..." if will_switch else "")
            if success
            else (res.get("error") or "انصراف یا خطا در ورود گوگل")
        )
        _notify_daemon_broadcast(extra_toast={"msg": msg, "isErr": not success})
        if will_switch:
            try:
                sw = switch_account(email, no_restart=True)
                if sw.get("success"):
                    time.sleep(0.8)
                    r_res = restart_after_account_switch()
                    launched = r_res.get("launched") is True and r_res.get("status") == "launch_requested"
                    _notify_daemon_broadcast(
                        extra_toast={
                            "msg": (
                                "حساب تغییر یافت؛ اجرای برنامه درخواست شد. آماده‌بودن برنامه هنوز تأیید نشده است."
                                if launched
                                else "حساب تغییر یافت؛ راه‌اندازی مجدد ایمن انجام نشد. وضعیت برنامه را بررسی کنید."
                            ),
                            "isErr": not launched,
                            "restart": r_res,
                        },
                        target_account=email,
                    )
                else:
                    _notify_daemon_broadcast(
                        extra_toast={"msg": sw.get("error") or "سوئیچ خودکار به حساب جدید انجام نشد", "isErr": True}
                    )
            except Exception as err:
                print(f"[OAUTH] Auto-switch error: {err!r}", flush=True)

    threading.Thread(
        target=lambda: run_google_oauth_flow(target_account=target_account, on_url=_on_url, on_complete=_done),
        daemon=True,
    ).start()

    for _ in range(25):
        if auth_url_holder:
            break
        time.sleep(0.08)

    return auth_url_holder[0] if auth_url_holder else ""


def _safe_allowed_convs(account: str) -> list[str]:
    try:
        return migration_engine.get_allowed_conversations(account, use_cache=True)
    except Exception:
        return []


def _schedule_quota_refresh(cache_key: str, account_email, instance_id: str = "instance_1") -> None:
    """Refresh stale quota in a single background thread per key so /api/state stays <100ms."""
    with _STATE_CACHE_LOCK:
        if cache_key in _QUOTA_REFRESH_IN_FLIGHT:
            return
        _QUOTA_REFRESH_IN_FLIGHT.add(cache_key)

    def _worker():
        try:
            get_account_profile_data(account_email, force_refresh=True, instance_id=instance_id)
        except Exception:
            pass
        finally:
            with _STATE_CACHE_LOCK:
                _QUOTA_REFRESH_IN_FLIGHT.discard(cache_key)

    threading.Thread(target=_worker, daemon=True).start()


def get_account_profile_data(account_email, manifest=None, force_refresh=False, instance_id="instance_1"):
    """Fetch 6-pool profile/quota payload for an account with short-lived caching and zero token leaks."""
    if manifest is None:
        manifest = load_manifest()

    target = str(account_email or "").strip()
    if target in ("primary_account", "secondary_account") and target not in manifest:
        target = ""

    resolved = store.resolve_account_key(target, manifest) if target else None
    cache_key = str((resolved or target or "default")).lower().strip()
    stale_cached = None

    if not force_refresh:
        with _STATE_CACHE_LOCK:
            cached = _ACTIVE_QUOTA_CACHE.get(cache_key)
            if cached:
                if (time.time() - cached.get("time", 0.0)) < _ACTIVE_QUOTA_TTL:
                    return dict(cached["data"])
                stale_cached = dict(cached["data"])

        if vault._normalize_instance_id(instance_id) == "instance_1" and target:
            aq_path = vault.get_platform_paths("instance_1")["active_quota_path"]
            if aq_path.is_file():
                try:
                    age = time.time() - aq_path.stat().st_mtime
                    aq_data = json.loads(aq_path.read_text(encoding="utf-8"))
                    if isinstance(aq_data, dict) and str(aq_data.get("email") or "").lower().strip() == target.lower() and aq_data.get("pools"):
                        if age < _ACTIVE_QUOTA_TTL:
                            with _STATE_CACHE_LOCK:
                                _ACTIVE_QUOTA_CACHE[cache_key] = {"data": dict(aq_data), "time": time.time()}
                            return aq_data
                        if stale_cached is None:
                            stale_cached = aq_data
                except Exception:
                    pass

        if stale_cached is not None:
            _schedule_quota_refresh(cache_key, account_email, instance_id=instance_id)
            return stale_cached

    entry = manifest.get(resolved, {}) if resolved else {}
    if not force_refresh and isinstance(entry.get("quota"), dict) and entry["quota"].get("pools"):
        q_data = dict(entry["quota"])
        with _STATE_CACHE_LOCK:
            _ACTIVE_QUOTA_CACHE[cache_key] = {"data": dict(q_data), "time": time.time()}
        return q_data

    # On non-forced reads with known manifest metadata, return immediately and refresh in background.
    if not force_refresh and (resolved or (target and "@" in target)):
        fallback = quota._manifest_fallback_quota(str(entry.get("email") or resolved or target), entry or {})
        if entry.get("avatar") and not fallback.get("avatar"):
            fallback["avatar"] = entry["avatar"]
        with _STATE_CACHE_LOCK:
            _ACTIVE_QUOTA_CACHE[cache_key] = {"data": dict(fallback), "time": time.time() - (_ACTIVE_QUOTA_TTL - 5.0)}
        _schedule_quota_refresh(cache_key, account_email, instance_id=instance_id)
        return fallback

    tok_str = store.read_account_token(resolved, manifest) if resolved else None
    q_data = None
    if tok_str:
        try:
            q_cand = quota.fetch_quota_and_tier(tok_str, force_refresh=force_refresh)
            if isinstance(q_cand, dict):
                q_email = str(q_cand.get("email") or "").lower().strip()
                expected = str(entry.get("email") or resolved or "").lower().strip()
                if not expected or not q_email or q_email == expected:
                    q_data = q_cand
        except Exception:
            q_data = None

    if not q_data and not resolved and not target:
        try:
            q_data = quota.fetch_quota_and_tier(force_refresh=force_refresh)
        except Exception:
            q_data = None

    if not q_data and (resolved or (target and "@" in target)):
        q_data = quota._manifest_fallback_quota(str(entry.get("email") or resolved or target), entry or {})

    if not q_data:
        return None

    for secret_k in ("token_file", "access_token", "refresh_token", "id_token"):
        q_data.pop(secret_k, None)

    if entry.get("avatar") and not q_data.get("avatar"):
        q_data["avatar"] = entry["avatar"]

    with _STATE_CACHE_LOCK:
        _ACTIVE_QUOTA_CACHE[cache_key] = {"data": dict(q_data), "time": time.time()}
    return q_data


def build_api_state_payload(
    req_inst: str | None = None,
    req_acc: str | None = None,
    include_convs: bool = False,
    include_tasks: bool = False,
    force: bool = False,
    cdp_connected_override: bool | None = None,
) -> dict:
    """Build identical <100ms cached /api/state schema for both :39281 and :39285."""
    norm_inst = vault._normalize_instance_id(req_inst)
    manifest = load_manifest()
    sanitized_accounts = store.sanitize_manifest_for_client(manifest)

    target_acc = req_acc or store.get_instance_active_account(norm_inst, is_dual_launching=_dual_launch_in_progress)
    active_account = get_account_profile_data(target_acc, manifest=manifest, force_refresh=force, instance_id=norm_inst)

    try:
        projects = migration_engine.list_projects(use_cache=True)
    except Exception:
        projects = []

    conversations = migration_engine.list_conversations() if include_convs else []
    tasks = migration_engine.list_scheduled_tasks() if include_tasks else []

    allowed_map = {
        "instance_1": _safe_allowed_convs("instance_1"),
        "instance_2": _safe_allowed_convs("instance_2"),
    }
    if norm_inst not in allowed_map:
        allowed_map[norm_inst] = _safe_allowed_convs(norm_inst)

    targets = get_devtools_targets(use_cache=True)
    running_instances = [t["instance_id"] for t in targets]
    running_accounts = {
        t["instance_id"]: t.get("default_account") or store.get_instance_active_account(t["instance_id"], is_dual_launching=_dual_launch_in_progress)
        for t in targets
    }
    cdp_connected = bool(cdp_connected_override) if cdp_connected_override is not None else bool(targets)
    auth_state = quota.get_live_ide_auth_state(instance_id=norm_inst, use_cache=not force)

    if isinstance(active_account, dict):
        active_account.setdefault("live_ide_email", auth_state.get("live_ide_email"))
        active_account.setdefault("credential_email", auth_state.get("credential_email"))
        active_account.setdefault("session_mismatch", bool(auth_state.get("session_mismatch", False)))

    return {
        "activeAccount": active_account,
        "savedAccounts": sanitized_accounts,
        "instanceId": norm_inst,
        "projects": projects,
        "conversations": conversations,
        "tasks": tasks,
        "allowedConversations": allowed_map,
        "runningInstances": running_instances,
        "runningAccounts": running_accounts,
        "cdpConnected": cdp_connected,
        "cdpTargets": targets,
        "authState": auth_state,
    }


def _load_legacy_chatgpt_manager():
    try:
        from legacy.chatgpt import chatgpt_account_manager as cpm
        return cpm
    except ImportError:
        try:
            import chatgpt_account_manager as cpm
            return cpm
        except ImportError:
            return None


def _send_cors_headers(handler: BaseHTTPRequestHandler, cors_origin: str | None) -> None:
    if cors_origin:
        handler.send_header("Access-Control-Allow-Origin", cors_origin)
        if cors_origin != "*":
            handler.send_header("Vary", "Origin")
        handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        handler.send_header("Access-Control-Allow-Headers", "Content-Type")


def send_json_response(
    handler: BaseHTTPRequestHandler,
    status: int,
    payload,
    cors_origin: str | None = None,
) -> None:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
    handler.send_header("Connection", "close")
    _send_cors_headers(handler, cors_origin)
    handler.end_headers()
    handler.wfile.write(raw)


def _handle_font_request(handler: BaseHTTPRequestHandler, clean_path: str, cors_origin: str | None) -> None:
    raw_name = clean_path[len("/fonts/"):]
    decoded = urllib.parse.unquote(raw_name).strip().lstrip("/")
    if (
        not decoded
        or "\x00" in decoded
        or "/" in decoded
        or "\\" in decoded
        or ".." in decoded
        or Path(decoded).suffix.lower() not in store.FONT_MIME_TYPES
    ):
        send_json_response(handler, 403, {"success": False, "error": "Forbidden font path"}, cors_origin=cors_origin)
        return

    font_path, mime = store.resolve_font_asset(raw_name)
    if font_path is None or not mime:
        send_json_response(handler, 404, {"success": False, "error": "Font not found"}, cors_origin=cors_origin)
        return

    data = font_path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", mime)
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "public, max-age=86400")
    handler.send_header("Connection", "close")
    _send_cors_headers(handler, cors_origin or "*")
    handler.end_headers()
    handler.wfile.write(data)


def handle_http_options(handler: BaseHTTPRequestHandler) -> None:
    allowed, cors_or_err = cdp.check_local_http_request(handler.headers, "OPTIONS", handler.path)
    if not allowed:
        send_json_response(handler, 403, {"success": False, "error": cors_or_err}, cors_origin=None)
        return
    handler.send_response(200)
    handler.send_header("Content-Length", "0")
    handler.send_header("Connection", "close")
    _send_cors_headers(handler, cors_or_err)
    handler.end_headers()


def handle_http_get(
    handler: BaseHTTPRequestHandler,
    allow_static: bool = False,
    cdp_connected_override: bool | None = None,
    sync_quota_fn=None,
) -> bool:
    """Handle local firewall check and all shared GET routes. Returns True if handled."""
    allowed, cors_or_err = cdp.check_local_http_request(handler.headers, "GET", handler.path)
    if not allowed:
        send_json_response(handler, 403, {"success": False, "error": cors_or_err}, cors_origin=None)
        return True
    cors_origin = cors_or_err

    parsed = urllib.parse.urlparse(handler.path)
    clean_path = parsed.path
    qs = urllib.parse.parse_qs(parsed.query)

    if clean_path in ("/health", "/api/health"):
        send_json_response(handler, 200, {"status": "ok", "version": VERSION}, cors_origin=cors_origin)
        return True

    if clean_path.startswith("/fonts/"):
        _handle_font_request(handler, clean_path, cors_origin)
        return True

    if clean_path in ("/api/state", "/api/accounts"):
        req_inst = qs.get("instance", [None])[0] or qs.get("instance_id", [None])[0]
        req_acc = qs.get("account", [None])[0]
        include_convs = str(qs.get("include_convs", ["0"])[0]).lower() in ("1", "true")
        include_tasks = str(qs.get("include_tasks", ["0"])[0]).lower() in ("1", "true")
        force = str(qs.get("force", ["0"])[0]).lower() in ("1", "true")
        payload = build_api_state_payload(
            req_inst=req_inst,
            req_acc=req_acc,
            include_convs=include_convs,
            include_tasks=include_tasks,
            force=force,
            cdp_connected_override=cdp_connected_override,
        )
        send_json_response(handler, 200, payload, cors_origin=cors_origin)
        return True

    if clean_path in ("/sync", "/quota", "/api/quota"):
        req_inst = qs.get("instance", [None])[0] or qs.get("instance_id", [None])[0]
        force = str(qs.get("force", ["0"])[0]).lower() in ("1", "true") or "force" in parsed.query
        if callable(sync_quota_fn):
            usage = sync_quota_fn(req_inst=req_inst, force=force)
        else:
            norm_inst = vault._normalize_instance_id(req_inst)
            target_acc = store.get_instance_active_account(norm_inst, is_dual_launching=_dual_launch_in_progress)
            usage = get_account_profile_data(target_acc, force_refresh=force, instance_id=norm_inst) or {}
        send_json_response(handler, 200, usage or {}, cors_origin=cors_origin)
        return True

    if clean_path == "/api/conversations":
        send_json_response(handler, 200, migration_engine.list_conversations(), cors_origin=cors_origin)
        return True

    if clean_path == "/api/projects":
        send_json_response(handler, 200, migration_engine.list_projects(), cors_origin=cors_origin)
        return True

    if clean_path == "/api/tasks":
        send_json_response(handler, 200, migration_engine.list_scheduled_tasks(), cors_origin=cors_origin)
        return True

    if clean_path == "/api/settings":
        inst = qs.get("instance_id", [None])[0] or qs.get("instance", [None])[0]
        acc = qs.get("account", [None])[0]
        send_json_response(handler, 200, load_user_settings(instance_id=inst, account_email=acc), cors_origin=cors_origin)
        return True

    if clean_path in ("/api/dual_status", "/api/instances_status"):
        targets = get_devtools_targets(use_cache=True)
        running_instances = [t["instance_id"] for t in targets]
        running_accounts = {
            t["instance_id"]: t.get("default_account") or store.get_instance_active_account(t["instance_id"])
            for t in targets
        }
        payload = {
            "instance2_running": len(running_instances) > 1 or is_instance2_running(),
            "running_instances": running_instances,
            "running_accounts": running_accounts,
            "targets": targets,
            "instances": {f"instance_{i}": is_instance_running(f"Antigravity-Instance{i}") for i in range(2, 6)},
        }
        send_json_response(handler, 200, payload, cors_origin=cors_origin)
        return True

    if clean_path in ("/api/launch_dual", "/api/launch_instance"):
        acc = qs.get("accountKey", [None])[0] or qs.get("account", [None])[0] or qs.get("email", [None])[0]
        proj = qs.get("projectPath", [None])[0] or qs.get("path", [None])[0]
        send_json_response(handler, 200, launch_dual_instance(acc, project_path=proj), cors_origin=cors_origin)
        return True

    if clean_path == "/open_switcher":
        threading.Thread(target=launch_gui, kwargs={"port": PORT}, daemon=True).start()
        send_json_response(handler, 200, {"status": "opened"}, cors_origin=cors_origin)
        return True

    if clean_path.startswith("/api/chatgpt/"):
        cpm = _load_legacy_chatgpt_manager()
        if not cpm:
            send_json_response(handler, 200, {"success": False, "error": "Legacy ChatGPT module not available"}, cors_origin=cors_origin)
            return True
        if clean_path == "/api/chatgpt/status":
            send_json_response(
                handler,
                200,
                {"status": "ok", "profiles": cpm.list_profiles(), "settings": cpm.load_settings()},
                cors_origin=cors_origin,
            )
            return True
        if clean_path == "/api/chatgpt/launch":
            inst = int(qs.get("instance", ["1"])[0])
            new_win = qs.get("new_window", ["0"])[0] in ("1", "true")
            ok, msg = cpm.launch_chatgpt(instance_num=inst, new_window=new_win)
            send_json_response(handler, 200, {"success": ok, "message": msg}, cors_origin=cors_origin)
            return True
        if clean_path == "/api/chatgpt/login":
            mode = qs.get("mode", ["oauth"])[0]
            api_key = qs.get("api_key", [None])[0]
            ok, msg = cpm.trigger_codex_login(mode=mode, api_key=api_key)
            resp = (
                {"success": ok, "auth_url": msg.get("auth_url"), "message": msg.get("message", "")}
                if isinstance(msg, dict)
                else {"success": ok, "message": str(msg)}
            )
            send_json_response(handler, 200, resp, cors_origin=cors_origin)
            return True
        if clean_path == "/api/chatgpt/logout":
            ok, msg = cpm.trigger_codex_logout()
            send_json_response(handler, 200, {"success": ok, "message": msg}, cors_origin=cors_origin)
            return True

    if allow_static:
        handler._cors_origin = cors_origin  # type: ignore[attr-defined]
        handler._serving_static = True  # type: ignore[attr-defined]
        return False

    send_json_response(handler, 404, {"success": False, "error": "Not Found"}, cors_origin=cors_origin)
    return True


def handle_http_post(handler: BaseHTTPRequestHandler, on_switch_cb=None, oauth_fn=None) -> None:
    """Handle local firewall check and all shared POST routes on :39281 and :39285."""
    allowed, cors_or_err = cdp.check_local_http_request(handler.headers, "POST", handler.path)
    if not allowed:
        send_json_response(handler, 403, {"success": False, "error": cors_or_err}, cors_origin=None)
        return
    cors_origin = cors_or_err

    try:
        length = max(0, int(handler.headers.get("Content-Length") or 0))
    except ValueError:
        length = 0
    raw_body = handler.rfile.read(length).decode("utf-8", errors="replace") if length > 0 else "{}"
    try:
        data = json.loads(raw_body) if raw_body.strip() else {}
        if not isinstance(data, dict):
            data = {}
    except Exception:
        send_json_response(handler, 400, {"success": False, "error": "Invalid JSON body"}, cors_origin=cors_origin)
        return

    clean_path = urllib.parse.urlparse(handler.path).path
    resp = {"success": False, "error": f"Unknown endpoint: {clean_path}"}
    should_broadcast = False
    extra_toast = None
    target_account = None

    try:
        if clean_path == "/api/settings":
            inst = data.get("instance_id")
            acc = data.get("account")
            ok, res = save_user_settings(data, instance_id=inst, account_email=acc)
            resp = {"success": ok, "settings": res}
            should_broadcast = bool(ok)

        elif clean_path == "/api/switch":
            acc_key = data.get("accountKey") or data.get("account") or data.get("email")
            no_restart = bool(data.get("noRestart", True))
            resp = switch_account(acc_key, no_restart=True)
            if resp.get("success"):
                resp["restart"] = {
                    "requested": not no_restart,
                    "launched": False,
                    "completed": False,
                    "status": "pending" if not no_restart else "not_requested",
                }
                if callable(on_switch_cb):
                    on_switch_cb(resp)
                target_account = resp.get("account") or acc_key
                extra_toast = {
                    "msg": f"حساب به {resp.get('email') or acc_key} تغییر یافت.",
                    "isErr": False,
                    "restart": resp["restart"],
                }
                should_broadcast = True
                if not no_restart:
                    def _do_restart():
                        time.sleep(0.8)
                        r_res = restart_after_account_switch()
                        launched = r_res.get("launched") is True and r_res.get("status") == "launch_requested"
                        _notify_daemon_broadcast(
                            extra_toast={
                                "msg": (
                                    "حساب تغییر یافت؛ اجرای برنامه درخواست شد. آماده‌بودن برنامه هنوز تأیید نشده است."
                                    if launched
                                    else "حساب تغییر یافت؛ راه‌اندازی مجدد ایمن انجام نشد. وضعیت برنامه را بررسی کنید."
                                ),
                                "isErr": not launched,
                                "restart": r_res,
                            }
                        )

                    threading.Thread(target=_do_restart, daemon=True).start()

        elif clean_path in ("/api/restart", "/api/restart_app"):
            threading.Thread(target=restart_after_account_switch, daemon=True).start()
            resp = {"success": True, "msg": "Restarting Antigravity..."}

        elif clean_path in ("/api/launch_dual", "/api/launch_instance"):
            acc_key = data.get("accountKey") or data.get("account") or data.get("email")
            project_path = data.get("projectPath") or data.get("path")
            resp = launch_dual_instance(acc_key, project_path=project_path)

        elif clean_path == "/api/oauth_signin":
            tgt_acc = data.get("accountKey") or data.get("email")
            if "auto_switch" in data:
                auto_sw = bool(data["auto_switch"])
            elif "autoSwitch" in data:
                auto_sw = bool(data["autoSwitch"])
            else:
                auto_sw = not bool(data.get("noRestart", False))
            runner = oauth_fn or start_shared_oauth_flow
            auth_url = runner(target_account=tgt_acc, auto_switch=auto_sw)
            resp = {"success": True, "auth_url": auth_url, "auto_switch": auto_sw}

        elif clean_path == "/api/save":
            resp = save_current_account()
            should_broadcast = bool(resp.get("success"))

        elif clean_path == "/api/import":
            resp = import_token(data.get("token", ""))
            should_broadcast = bool(resp.get("success"))

        elif clean_path == "/api/logout":
            resp = logout_account(no_restart=bool(data.get("noRestart", False)))
            should_broadcast = bool(resp.get("success"))

        elif clean_path == "/api/delete":
            acc_key = data.get("accountKey") or data.get("account") or data.get("email")
            resp = delete_account(acc_key)
            should_broadcast = bool(resp.get("success"))

        elif clean_path == "/api/migrate":
            resp = migration_engine.migrate_conversations(
                data.get("conversationIds", []),
                data.get("sourceAccount"),
                data.get("targetAccount"),
                mode=data.get("mode", "copy"),
                structure=data.get("structure", "separate"),
                dual_sync=data.get("dualSync", False),
                project_id=data.get("projectId"),
            )
            should_broadcast = bool(resp.get("success"))

        elif clean_path == "/api/project_assign":
            resp = migration_engine.set_project_assignment(
                data.get("projectId"),
                data.get("accounts") or data.get("account", []),
                sync_mode=data.get("syncMode", "shared"),
                enabled=data.get("enabled"),
            )
            should_broadcast = bool(resp.get("success"))

        elif clean_path == "/api/project_toggle_all":
            resp = migration_engine.toggle_project_all(
                data.get("projectId"),
                state=data.get("state", "all"),
            )
            should_broadcast = bool(resp.get("success"))

        elif clean_path == "/api/project_set_quota_account":
            tgt_acc = data.get("account") or data.get("quotaAccount")
            resp = migration_engine.set_project_quota_account(data.get("projectId"), tgt_acc)
            if resp.get("success") and tgt_acc and not bool(data.get("noSwitch", False)):
                sw = switch_account(tgt_acc, no_restart=True)
                resp["credential_switched"] = bool(sw.get("success"))
                resp["authState"] = sw.get("authState")
            should_broadcast = bool(resp.get("success"))

        elif clean_path == "/api/project_sync":
            resp = migration_engine.sync_project_to_account(
                data.get("projectId"),
                data.get("targetAccount"),
                include_conversations=data.get("includeConversations", False),
            )
            should_broadcast = bool(resp.get("success"))

        elif clean_path == "/api/project_unlink":
            resp = migration_engine.unlink_project_from_account(data.get("projectId"), data.get("account"))
            should_broadcast = bool(resp.get("success"))

        elif clean_path == "/api/task_set_quota_account":
            resp = migration_engine.set_task_quota_account(
                data.get("taskName") or data.get("name"),
                data.get("account") or data.get("quotaAccount"),
            )
            should_broadcast = bool(resp.get("success"))

        elif clean_path == "/api/task_assign":
            resp = migration_engine.set_task_account_assignment(
                data.get("taskName") or data.get("name"),
                data.get("accounts") or data.get("account", []),
                enabled=data.get("enabled"),
            )
            should_broadcast = bool(resp.get("success"))

        elif clean_path == "/api/task_toggle_all":
            resp = migration_engine.toggle_task_all(
                data.get("taskName") or data.get("name"),
                state=data.get("state", "all"),
            )
            should_broadcast = bool(resp.get("success"))

        elif clean_path == "/api/task_isolate":
            t_name = data.get("taskName") or data.get("name")
            owner = data.get("ownerAccount") or store.get_primary_account()
            iso = data.get("isolateFromAccount2", data.get("isolate", True))
            insts = data.get("allowedInstances")
            req_acc = data.get("account") or data.get("callerAccount")
            resp = migration_engine.set_task_isolation(
                t_name,
                owner,
                isolate_from_account2=iso,
                allowed_instances=insts,
                requesting_account=req_acc,
            )
            should_broadcast = bool(resp.get("success"))

        elif clean_path == "/api/task_toggle":
            t_name = data.get("taskName") or data.get("name")
            enb = data.get("enable", data.get("enabled", True))
            req_acc = data.get("account") or data.get("callerAccount")
            resp = migration_engine.toggle_task_state(t_name, enable=enb, requesting_account=req_acc)
            should_broadcast = bool(resp.get("success"))

        elif clean_path == "/api/task_run_guarded":
            t_name = data.get("taskName") or data.get("name")
            resp = migration_engine.run_guarded_task(t_name)

        elif clean_path == "/api/conversation_assign":
            resp = migration_engine.assign_conversation_account(
                data.get("conversationId"),
                data.get("account"),
                action=data.get("action", "add"),
            )
            should_broadcast = bool(resp.get("success"))

        elif clean_path.startswith("/api/chatgpt/"):
            cpm = _load_legacy_chatgpt_manager()
            if not cpm:
                resp = {"success": False, "error": "Legacy ChatGPT module not available"}
            elif clean_path == "/api/chatgpt/switch":
                profile_id = data.get("profile_id") or data.get("profileId")
                if profile_id:
                    ok, msg = cpm.switch_profile(profile_id)
                    resp = {"success": ok, "message": msg}
                else:
                    resp = {"success": False, "error": "Missing profile_id"}
            elif clean_path == "/api/chatgpt/save_profile":
                p_id = data.get("profile_id") or data.get("profileId")
                name = data.get("display_name") or data.get("name")
                if p_id:
                    ok, res = cpm.save_current_profile(p_id, display_name=name)
                    resp = {"success": ok, "data": res}
                else:
                    resp = {"success": False, "error": "Missing profile_id"}
            elif clean_path == "/api/chatgpt/settings":
                ok, res = cpm.save_settings(data)
                resp = {"success": ok, "settings": res}
            elif clean_path == "/api/chatgpt/login":
                mode = data.get("mode", "oauth")
                api_key = data.get("api_key")
                ok, msg = cpm.trigger_codex_login(mode=mode, api_key=api_key)
                resp = (
                    {"success": ok, "auth_url": msg.get("auth_url"), "message": msg.get("message", "")}
                    if isinstance(msg, dict)
                    else {"success": ok, "message": str(msg)}
                )
            elif clean_path == "/api/chatgpt/logout":
                ok, msg = cpm.trigger_codex_logout()
                resp = {"success": ok, "message": msg}

        if should_broadcast:
            _notify_daemon_broadcast(
                extra_toast=extra_toast,
                target_account=target_account,
                allow_poke=(clean_path != "/api/switch"),
            )
    except Exception as e:
        resp = {"success": False, "error": str(e)}

    try:
        send_json_response(handler, 200, resp, cors_origin=cors_origin)
    except Exception:
        pass


class SwitcherHTTPHandler(SimpleHTTPRequestHandler):
    timeout = 5.0

    def __init__(self, *args, **kwargs):
        self._cors_origin = None
        self._serving_static = False
        super().__init__(*args, directory=APP_DIR, **kwargs)

    def end_headers(self):
        if getattr(self, "_serving_static", False):
            _send_cors_headers(self, getattr(self, "_cors_origin", None))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self._serving_static = False
        handle_http_options(self)

    def do_GET(self):
        self._serving_static = False
        if handle_http_get(self, allow_static=True):
            return
        try:
            super().do_GET()
        finally:
            self._serving_static = False

    def do_POST(self):
        self._serving_static = False
        handle_http_post(self)

    def log_message(self, format, *args):
        return


def is_port_in_use(port: int) -> bool:
    return cdp.is_port_open(port, timeout=0.15)


def _is_control_center_healthy(port: int) -> bool:
    for path in ("/api/health", "/health"):
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{int(port)}{path}")
            with _LOOPBACK_OPENER.open(req, timeout=0.6) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
    return False


def start_server(port: int = PORT) -> int:
    actual_port = port
    while is_port_in_use(actual_port):
        actual_port += 1

    threading.Thread(target=ensure_daemon_running, daemon=True).start()
    ThreadingHTTPServer.allow_reuse_address = True
    srv = ThreadingHTTPServer(("127.0.0.1", actual_port), SwitcherHTTPHandler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return actual_port


def _open_app_window(url: str) -> None:
    sys_name = vault.get_current_system()
    if sys_name == "windows":
        edge_paths = [
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        ]
        chrome_paths = [
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        ]
        browser = next((p for p in (edge_paths + chrome_paths) if os.path.exists(p)), None)
        if browser:
            subprocess.Popen([browser, f"--app={url}", "--window-size=620,860", "--disable-features=Translate"])
            return
    elif sys_name == "macos":
        if os.path.exists("/Applications/Google Chrome.app"):
            subprocess.Popen(["open", "-na", "Google Chrome", "--args", f"--app={url}", "--window-size=620,860"])
        else:
            subprocess.Popen(["open", url])
        return

    import webbrowser

    webbrowser.open(url)


def launch_gui(port: int = PORT):
    """Open Control Center GUI, reusing an already healthy :39285 instance instead of spawning orphans."""
    reused = _is_control_center_healthy(port)
    actual_port = port if reused else start_server(port)
    url = f"http://127.0.0.1:{actual_port}/index.html"
    _open_app_window(url)
    print(f"Antigravity Switcher GUI running at {url}")
    if reused:
        return actual_port
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    return actual_port


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--launch", "--launch-instance", "--focus"):
        target = sys.argv[2] if len(sys.argv) > 2 else store.get_secondary_account()
        res = launch_dual_instance(target)
        print(f"Multi-instance launch result for {target}: {res}")
        sys.exit(0 if res.get("success") else 1)
    elif len(sys.argv) > 1 and sys.argv[1] == "--server-only":
        p = start_server()
        print(f"Server started on port {p}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    else:
        launch_gui()
