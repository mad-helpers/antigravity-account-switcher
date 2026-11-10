"""Regression: restart must survive restricted-token (AccessDenied) Antigravity child processes."""
import os, subprocess, sys, pathlib
import psutil

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import server


def test_wait_gone_reports_live_and_dead_processes():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert [p.pid for p in server._wait_gone([psutil.Process(child.pid)], 0.4)] == [child.pid]
    finally:
        child.kill(); child.wait()
    assert server._wait_gone([psutil.Process(os.getpid())], 0.2)  # self is alive
    dead = subprocess.Popen([sys.executable, "-c", "pass"]); dead.wait()
    assert server._wait_gone([psutil.Process(dead.pid)] if psutil.pid_exists(dead.pid) else [], 0.2) == []


def test_wait_gone_never_raises_on_real_antigravity_processes():
    procs = [p for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "antigravity.exe"]
    server._wait_gone(procs, 0.3)  # psutil.wait_procs raised AccessDenied here


if __name__ == "__main__":
    test_wait_gone_reports_live_and_dead_processes()
    test_wait_gone_never_raises_on_real_antigravity_processes()
    print("ok")
