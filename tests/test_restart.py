"""Regression: restart must survive restricted-token (AccessDenied) Antigravity child processes and pass --remote-debugging-port=0."""
import inspect
import os
import pathlib
import subprocess
import sys
import types

try:
    import psutil
except ImportError:
    class _ShimProcess:
        def __init__(self, pid):
            self.pid = int(pid)
            self.info = {"name": ""}

    def _pid_exists(pid):
        try:
            os.kill(int(pid), 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        st = pathlib.Path(f"/proc/{int(pid)}/stat")
        if st.is_file():
            try:
                return " Z " not in st.read_text(errors="ignore")
            except Exception:
                pass
        return True

    psutil = types.ModuleType("psutil")
    psutil.Process = _ShimProcess
    psutil.pid_exists = _pid_exists
    psutil.process_iter = lambda attrs=None: []
    sys.modules["psutil"] = psutil

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import server


def test_wait_gone_reports_live_and_dead_processes():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert [p.pid for p in server._wait_gone([psutil.Process(child.pid)], 0.4)] == [child.pid]
    finally:
        child.kill()
        child.wait()
    assert server._wait_gone([psutil.Process(os.getpid())], 0.2)  # self is alive
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    assert server._wait_gone([psutil.Process(dead.pid)] if psutil.pid_exists(dead.pid) else [], 0.2) == []


def test_wait_gone_never_raises_on_real_antigravity_processes():
    procs = [p for p in psutil.process_iter(["name"]) if (p.info.get("name") or "").lower() == "antigravity.exe"]
    server._wait_gone(procs, 0.3)  # psutil.wait_procs raised AccessDenied here


def test_restart_and_dual_launch_include_remote_debugging_flag():
    restart_src = inspect.getsource(server.restart_antigravity)
    dual_src = inspect.getsource(server.launch_dual_instance)
    assert "--remote-debugging-port=0" in restart_src
    assert "--remote-debugging-port=0" in dual_src
    assert "discover_live_cdp_ports" in dual_src
    assert "_clean_launch_env" in restart_src
    assert "_clean_launch_env" in dual_src


def test_clean_launch_env_strips_electron_run_as_node_and_sidecar_vars():
    polluted = {
        "PATH": "C:\\Windows",
        "ELECTRON_RUN_AS_NODE": "1",
        "NODE_OPTIONS": "--max-old-space-size=4096",
        "NODE_PATH": "C:\\fake\\node_modules",
        "AGY_REQUIRE_AUTHENTICATED_UI_BOOTSTRAP": "1",
        "ANTIGRAVITY_CSRF_TOKEN": "csrf-secret",
        "ANTIGRAVITY_LS_ADDRESS": "localhost:51622",
        "ANTIGRAVITY_SIDECAR_UI_TOKEN": "ui-secret",
        "USERPROFILE": "C:\\Users\\dev",
    }
    cleaned = server._clean_launch_env(polluted)
    assert cleaned["PATH"] == "C:\\Windows"
    assert cleaned["USERPROFILE"] == "C:\\Users\\dev"
    for bad in (
        "ELECTRON_RUN_AS_NODE",
        "NODE_OPTIONS",
        "NODE_PATH",
        "AGY_REQUIRE_AUTHENTICATED_UI_BOOTSTRAP",
        "ANTIGRAVITY_CSRF_TOKEN",
        "ANTIGRAVITY_LS_ADDRESS",
        "ANTIGRAVITY_SIDECAR_UI_TOKEN",
    ):
        assert bad not in cleaned, f"{bad} leaked into cleaned launch env"


if __name__ == "__main__":
    test_wait_gone_reports_live_and_dead_processes()
    test_wait_gone_never_raises_on_real_antigravity_processes()
    test_restart_and_dual_launch_include_remote_debugging_flag()
    test_clean_launch_env_strips_electron_run_as_node_and_sidecar_vars()
    print("ok")
