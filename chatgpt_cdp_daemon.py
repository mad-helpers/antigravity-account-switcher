#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChatGPT Desktop & Codex Chrome DevTools Protocol (CDP) Injector Daemon
Connects to ChatGPT Desktop instances and injects Persian fonts, themes, and HUD action pill.
Works for both outer Electron pages and inner chat webviews.
Optimized for instant (< 300ms) startup injection and persistent reload retention.
"""

import os
import sys
import json
import time
import asyncio
import logging
import urllib.request
from pathlib import Path

try:
    import websockets
except ImportError:
    websockets = None

CURRENT_DIR = Path(__file__).resolve().parent
INJECTOR_JS_PATH = CURRENT_DIR / "chatgpt_theme_injector.js"
LOG_FILE = CURRENT_DIR / "chatgpt_cdp_daemon.log"

logger = logging.getLogger("chatgpt_cdp")
logger.setLevel(logging.INFO)
if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
    try:
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)
    except Exception:
        pass
if sys.stdout is not None and not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(sh)

def load_injector_script():
    if not INJECTOR_JS_PATH.exists():
        return ""
    try:
        header = ""
        try:
            import chatgpt_account_manager as cpm
            profiles = cpm.list_profiles()
            settings = cpm.load_settings()
            init_data = json.dumps({"profiles": profiles, "settings": settings}, ensure_ascii=False)
            header = f"window.__cpe_initial_data = {init_data};\n"
        except Exception:
            pass

        with open(INJECTOR_JS_PATH, "r", encoding="utf-8") as f:
            return header + f.read()
    except Exception as e:
        logger.error(f"Failed to read injector script: {e}")
        return ""

def get_open_targets(port):
    """Fetches list of debuggable targets from Chromium DevTools port with ultra-fast 127.0.0.1 priority."""
    # Fast path: 127.0.0.1 is local loopback and answers in 1-5ms
    url = f"http://127.0.0.1:{port}/json/list"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ChatGPT-Enhanced-Daemon"})
        with urllib.request.urlopen(req, timeout=0.25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list) and data:
                return data
    except Exception:
        pass

    try:
        url = f"http://localhost:{port}/json/list"
        req = urllib.request.Request(url, headers={"User-Agent": "ChatGPT-Enhanced-Daemon"})
        with urllib.request.urlopen(req, timeout=0.25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list) and data:
                return data
    except Exception:
        pass

    return []

def is_valid_chatgpt_target(t):
    """Checks whether a target is a valid main ChatGPT surface (page or app, rejecting sandboxes/workers/overlays)."""
    ws_url = t.get("webSocketDebuggerUrl")
    if not ws_url:
        return False
    t_type = t.get("type", "")
    t_url = (t.get("url") or "").lower()
    t_title = (t.get("title") or "").lower()

    # Reject internal chrome extensions, devtools panels, detached background windows, avatar overlays, sandboxes, or embedded pricing popups
    if any(x in t_url for x in [
        "devtools://", "chrome-extension://", "web-sandbox", "codex-sandbox",
        "detached-window", "avatar-overlay", "#pricing"
    ]):
        return False

    # Accept main page/app surfaces hosting chatgpt or codex app
    if t_type in ("page", "app", "webview"):
        if "chatgpt.com" in t_url or "app://-/index.html" in t_url:
            return True
        return any(x in (t_url + " " + t_title) for x in ["chatgpt", "codex"])

    return False

async def send_cdp_cmd(ws, msg_id, method, params, timeout=5.0):
    await ws.send(json.dumps({"id": msg_id, "method": method, "params": params}))
    start_t = time.time()
    while time.time() - start_t < timeout:
        remaining = timeout - (time.time() - start_t)
        if remaining <= 0:
            break
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            data = json.loads(raw)
            if data.get("id") == msg_id:
                return data
        except asyncio.TimeoutError:
            break
    return None

async def handle_target_ipc(ws, raw_msg):
    """Handles bidirectional native IPC calls from ChatGPT webview, bypassing CSP completely."""
    try:
        msg = json.loads(raw_msg)
        if msg.get("method") == "Runtime.bindingCalled" and msg.get("params", {}).get("name") == "__cpe_daemon_ipc":
            payload_str = msg["params"].get("payload", "{}")
            payload = json.loads(payload_str)
            req_id = payload.get("id")
            action = payload.get("action")
            import chatgpt_account_manager as cpm
            resp = {}

            if action == "login":
                mode = payload.get("mode", "oauth")
                api_key = payload.get("api_key")
                ok, res = cpm.trigger_codex_login(mode=mode, api_key=api_key)
                if isinstance(res, dict):
                    resp = {"success": ok, "auth_url": res.get("auth_url"), "message": res.get("message", "")}
                else:
                    resp = {"success": ok, "message": str(res)}

            elif action in ("status", "get_status"):
                profiles = cpm.list_profiles()
                settings = cpm.load_settings()
                resp = {"status": "ok", "profiles": profiles, "settings": settings}

            elif action == "switch":
                prof_id = payload.get("profile_id")
                ok, res = cpm.switch_profile(prof_id)
                resp = {"success": ok, "message": res}

            elif action == "save_profile":
                prof_id = payload.get("profile_id")
                name = payload.get("name")
                ok, res = cpm.save_current_profile(prof_id, display_name=name)
                resp = {"success": ok, "profile": res}

            elif action == "save_settings":
                ok, res = cpm.save_settings(payload.get("settings", {}))
                resp = {"success": ok, "settings": res}

            elif action == "logout":
                ok, res = cpm.trigger_codex_logout()
                resp = {"success": ok, "message": res}

            elif action == "launch":
                inst = int(payload.get("instance", 1))
                new_win = bool(payload.get("new_window", False))
                ok, res = cpm.launch_chatgpt(instance_num=inst, new_window=new_win)
                resp = {"success": ok, "message": res}

            # Reply to the webview
            reply_code = f"window.__cpe_on_ipc_reply && window.__cpe_on_ipc_reply({json.dumps(req_id)}, {json.dumps(resp, ensure_ascii=False)});"
            await ws.send(json.dumps({
                "id": int(time.time() * 1000) % 1000000,
                "method": "Runtime.evaluate",
                "params": {"expression": reply_code}
            }))
    except Exception as e:
        logger.error(f"Error handling CPE IPC: {e}")

async def target_worker(t_id, ws_url):
    """Dedicated persistent worker for an active ChatGPT DevTools target."""
    logger.info(f"[CPE WORKER] Starting worker for target {t_id}")
    try:
        async with websockets.connect(ws_url, ping_interval=15, ping_timeout=10, close_timeout=3) as ws:
            logger.info(f"[CPE WORKER] Connected to target {t_id}")
            # Enable Runtime and Page domains
            await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
            await ws.send(json.dumps({"id": 2, "method": "Page.enable"}))
            await ws.send(json.dumps({"id": 3, "method": "Runtime.addBinding", "params": {"name": "__cpe_daemon_ipc"}}))

            # Inject script & register for automatic evaluation on ANY future navigation / reload
            script = load_injector_script()
            if script:
                # 1. Register script to run on any new document before other scripts
                await ws.send(json.dumps({
                    "id": 4,
                    "method": "Page.addScriptToEvaluateOnNewDocument",
                    "params": {"source": script}
                }))
                # 2. Evaluate immediately in current document context
                await ws.send(json.dumps({
                    "id": 5,
                    "method": "Runtime.evaluate",
                    "params": {"expression": script, "userGesture": True}
                }))

            # Guardian task: periodically checks HUD presence and keeps IPC binding alive
            guardian_ids = set()
            async def guardian():
                while True:
                    await asyncio.sleep(2.5)
                    try:
                        chk_id = int(time.time() * 1000) % 1000000
                        guardian_ids.add(chk_id)
                        await ws.send(json.dumps({
                            "id": chk_id,
                            "method": "Runtime.evaluate",
                            "params": {
                                "expression": "Boolean(document.getElementById('cpe-hud-pill'))",
                                "returnByValue": True
                            }
                        }))
                    except Exception as e:
                        logger.debug(f"[CPE WORKER] Guardian exception: {e}")
                        break

            guardian_task = asyncio.create_task(guardian())

            hud_verified = False
            try:
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue

                    method = msg.get("method")
                    msg_id = msg.get("id")

                    # Handle native IPC
                    if method == "Runtime.bindingCalled" and msg.get("params", {}).get("name") == "__cpe_daemon_ipc":
                        await handle_target_ipc(ws, raw)

                    # Re-assert binding and re-inject on true document navigation / reload only
                    # Note: Excluded Runtime.executionContextCreated because ChatGPT creates dozens of worker contexts during chat!
                    elif method in ("Page.frameNavigated", "Page.loadEventFired"):
                        await ws.send(json.dumps({"id": 80, "method": "Runtime.addBinding", "params": {"name": "__cpe_daemon_ipc"}}))
                        fresh_script = load_injector_script()
                        if fresh_script:
                            await ws.send(json.dumps({
                                "id": 81,
                                "method": "Runtime.evaluate",
                                "params": {"expression": fresh_script, "userGesture": True}
                            }))

                    # Guardian response check: match any sent guardian check ID
                    elif msg_id in guardian_ids and "result" in msg and "result" in msg.get("result", {}):
                        guardian_ids.discard(msg_id)
                        val = msg["result"]["result"].get("value")
                        if val is True:
                            if not hud_verified:
                                hud_verified = True
                                logger.info(f"[CPE WORKER] HUD pill verified active and present on target {t_id}")
                        elif val is False:
                            hud_verified = False
                            logger.info(f"[CPE WORKER] HUD pill missing on target {t_id}, restoring HUD...")
                            # Lightweight restore: don't evaluate 450 KB, just call __cpe_render_hud()
                            restore_expr = """
                            (() => {
                                if (typeof window.__cpe_render_hud === 'function') {
                                    window.__cpe_render_hud();
                                    return true;
                                }
                                return false;
                            })()
                            """
                            await ws.send(json.dumps({
                                "id": 85,
                                "method": "Runtime.evaluate",
                                "params": {"expression": restore_expr, "returnByValue": True}
                            }))

                    # If lightweight restore failed because suite wasn't loaded at all, do full injection
                    elif msg_id == 85 and "result" in msg and "result" in msg.get("result", {}):
                        restored = msg["result"]["result"].get("value")
                        if not restored:
                            logger.info(f"[CPE WORKER] Full suite re-injection needed on target {t_id}")
                            fresh_script = load_injector_script()
                            if fresh_script:
                                await ws.send(json.dumps({"id": 82, "method": "Runtime.addBinding", "params": {"name": "__cpe_daemon_ipc"}}))
                                await ws.send(json.dumps({
                                    "id": 83,
                                    "method": "Runtime.evaluate",
                                    "params": {"expression": fresh_script, "userGesture": True}
                                }))
            finally:
                guardian_task.cancel()

    except asyncio.CancelledError:
        logger.info(f"[CPE WORKER] Worker cancelled for target {t_id}")
    except Exception as e:
        logger.info(f"[CPE WORKER] Target disconnected or error for {t_id}: {e}")

async def check_and_inject_target(ws_url, script, force=False):
    """Connects via WebSocket, binds IPC, and injects if needed."""
    if not websockets or not ws_url or not script:
        return False
    try:
        async with websockets.connect(ws_url, ping_interval=None, ping_timeout=5, close_timeout=2) as ws:
            # Bind native IPC & Page domain
            await ws.send(json.dumps({"id": 9, "method": "Runtime.enable"}))
            await ws.send(json.dumps({"id": 10, "method": "Page.enable"}))
            await ws.send(json.dumps({"id": 11, "method": "Runtime.addBinding", "params": {"name": "__cpe_daemon_ipc"}}))
            await ws.send(json.dumps({
                "id": 12,
                "method": "Page.addScriptToEvaluateOnNewDocument",
                "params": {"source": script}
            }))

            if not force:
                check_resp = await send_cdp_cmd(ws, 1, "Runtime.evaluate", {
                    "expression": "Boolean(document.getElementById('cpe-hud-pill'))",
                    "returnByValue": True
                }, timeout=2.0)
                has_pill = check_resp.get("result", {}).get("result", {}).get("value") if check_resp else False
                if has_pill:
                    return False

            # Inject the suite
            eval_resp = await send_cdp_cmd(ws, 2, "Runtime.evaluate", {
                "expression": script,
                "returnByValue": True,
                "userGesture": True
            }, timeout=5.0)
            if eval_resp and "exceptionDetails" in eval_resp.get("result", {}):
                ex = eval_resp["result"]["exceptionDetails"]
                logger.error(f"Injection failed with exception on {ws_url[:40]}: {ex.get('text', '')} - {ex.get('exception', {}).get('description', '')}")
                return False

            logger.info(f"Enhanced suite successfully injected into: {ws_url[:50]}...")
            return True
    except Exception as e:
        logger.debug(f"Target WebSocket error for {ws_url}: {e}")
        return False

async def scan_and_inject_once(ports=[9223, 9224], force=False):
    script = load_injector_script()
    if not script:
        return 0

    success_count = 0
    for port in ports:
        targets = get_open_targets(port)
        for t in targets:
            if is_valid_chatgpt_target(t):
                ws_url = t.get("webSocketDebuggerUrl")
                ok = await check_and_inject_target(ws_url, script, force=force)
                if ok:
                    success_count += 1
    return success_count

async def daemon_loop(ports=[9223, 9224], poll_interval=0.4):
    logger.info(f"ChatGPT CDP Injector Daemon active on ports {ports} (poll_interval={poll_interval}s)")
    workers = {}  # t_id -> asyncio.Task
    while True:
        try:
            current_target_ids = set()
            for port in ports:
                targets = get_open_targets(port)
                for t in targets:
                    if is_valid_chatgpt_target(t):
                        t_id = t.get("id") or t.get("webSocketDebuggerUrl")
                        ws_url = t.get("webSocketDebuggerUrl")
                        current_target_ids.add(t_id)
                        if t_id not in workers or workers[t_id].done():
                            workers[t_id] = asyncio.create_task(target_worker(t_id, ws_url))

            # Cancel workers for closed targets
            for t_id in list(workers.keys()):
                if t_id not in current_target_ids:
                    workers[t_id].cancel()
                    del workers[t_id]

            await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            for w in workers.values():
                w.cancel()
            break
        except Exception as e:
            logger.error(f"Daemon loop error: {e}")
            await asyncio.sleep(poll_interval)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ChatGPT CDP Injector")
    parser.add_argument("--once", action="store_true", help="Inject once and exit")
    parser.add_argument("--force", action="store_true", help="Force inject even if pill exists")
    parser.add_argument("--ports", nargs="+", type=int, default=[9223, 9224], help="DevTools ports to probe")
    args = parser.parse_args()

    if args.once:
        count = asyncio.run(scan_and_inject_once(ports=args.ports, force=args.force))
        print(f"Injected into {count} targets.")
    else:
        # Prevent multiple background daemons from running concurrently
        lock_file_path = CURRENT_DIR / "chatgpt_cdp_daemon.lock"
        try:
            lock_f = open(lock_file_path, "a+")
            import msvcrt
            msvcrt.locking(lock_f.fileno(), msvcrt.LK_NBLCK, 1)
        except Exception:
            logger.info("Another ChatGPT CDP Daemon is already running. Exiting.")
            sys.exit(0)

        try:
            asyncio.run(daemon_loop(ports=args.ports))
        except KeyboardInterrupt:
            print("Stopped.")
