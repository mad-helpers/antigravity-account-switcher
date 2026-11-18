#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Antigravity Quota Auto-Sync Daemon (v3.0.0)
Organization: mad-helpers (https://github.com/mad-helpers/antigravity-account-switcher)
Runs in background and provides:
  - Hardened local HTTP API on 127.0.0.1:39281 (full parity with :39285)
  - Strict workbench-only CDP injector & live state broadcaster
"""

import asyncio
import json
import os
import shutil
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    import websockets
except ImportError:
    websockets = None

LOG_FILE = Path.home() / ".gemini" / "antigravity" / "quota_monitor.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

# Only prepend POSIX tool paths on non-Windows hosts; always join with os.pathsep.
if os.name != "nt":
    EXTRA_PATHS = [
        str(Path.home() / ".local" / "bin"),
        "/usr/local/bin",
        "/opt/homebrew/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]
    _cur_parts = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    os.environ["PATH"] = os.pathsep.join(EXTRA_PATHS + [p for p in _cur_parts if p not in EXTRA_PATHS])

from ag_suite import cdp, quota, store, vault  # noqa: E402
import migration_engine  # noqa: E402
import server  # noqa: E402

store.rotate_log_if_needed(LOG_FILE)

try:
    if sys.stdout is None or not hasattr(sys.stdout, "write"):
        sys.stdout = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    elif hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if sys.stderr is None or not hasattr(sys.stderr, "write"):
        sys.stderr = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    elif hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        store.rotate_log_if_needed(LOG_FILE)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
    except Exception:
        pass


def find_node_binary() -> str:
    w = shutil.which("node")
    if w:
        return w
    candidates = [
        Path.home() / ".local" / "bin" / "node",
        Path("/usr/local/bin/node"),
        Path("/opt/homebrew/bin/node"),
        Path("/usr/bin/node"),
        Path("C:/Program Files/nodejs/node.exe"),
        Path("C:/Program Files (x86)/nodejs/node.exe"),
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return "node"


def get_platform_paths():
    paths = vault.get_platform_paths("instance_1")
    storage = paths["storage_path"]
    devtools = paths["devtools_port_path"]
    global_quota = paths["active_quota_path"]
    history = paths["antigravity_dir"] / "quota_history.json"

    injector = CURRENT_DIR / "antigravity_quota_injector.js"
    if not injector.exists():
        for cand in (
            paths["bin_dir"] / "antigravity_quota_injector.js",
            paths["antigravity_dir"] / "antigravity_quota_injector.js",
        ):
            if cand.exists():
                injector = cand
                break

    return storage, devtools, global_quota, history, injector


STORAGE_PATH, DEVTOOLS_PORT_PATH, GLOBAL_QUOTA_PATH, HISTORY_PATH, INJECTOR_PATH = get_platform_paths()
USER_SETTINGS_PATH = vault.get_platform_paths()["user_settings_path"]
DEFAULT_USER_SETTINGS = store.DEFAULT_USER_SETTINGS


def load_user_settings(instance_id=None, account_email=None) -> dict:
    return store.load_user_settings(instance_id=instance_id, account_email=account_email)


def save_user_settings(patch, instance_id=None, account_email=None):
    return store.save_user_settings(patch, instance_id=instance_id, account_email=account_email)


def get_primary_account() -> str:
    return store.get_primary_account()


def get_secondary_account() -> str:
    return store.get_secondary_account()


PRIMARY_ACCOUNT = get_primary_account()
SECONDARY_ACCOUNT = get_secondary_account()


def is_account2(email) -> bool:
    return store.is_account2(email)


def get_instance_active_account(instance_id="instance_1") -> str:
    return store.get_instance_active_account(instance_id, is_dual_launching=server.is_dual_launching())


def is_port_open(port, host="127.0.0.1", timeout=0.5) -> bool:
    return cdp.is_port_open(port, host=host, timeout=timeout)


def is_valid_cdp_port(port, timeout=0.15) -> bool:
    return cdp.is_valid_cdp_port(port, require_workbench=True, timeout=timeout)


def discover_live_cdp_ports() -> dict[str, int]:
    return cdp.discover_live_cdp_ports()


def _heal_devtools_port_file(port_file_path, live_port) -> bool:
    return cdp.heal_devtools_port_file(port_file_path, live_port)


def get_devtools_targets(use_cache: bool = True) -> list[dict]:
    return server.get_devtools_targets(use_cache=use_cache)


def get_all_devtools_ports() -> list[int]:
    return [t["port"] for t in get_devtools_targets(use_cache=True)]


def get_devtools_port() -> int | None:
    targets = get_devtools_targets(use_cache=True)
    return targets[0]["port"] if targets else None


_active_cdp_connections: dict[str, dict] = {}
_cdp_conns_lock = threading.Lock()
_cached_usage = None
_last_sync_time = 0.0
_sync_lock = threading.Lock()
_cached_account_info = None
_cached_account_time = 0.0


def _safe_allowed_convs(m_eng, account) -> list[str]:
    """A broken conversations store (e.g. dangling junction) must not blank the injected plugin."""
    try:
        return m_eng.get_allowed_conversations(account) if hasattr(m_eng, "get_allowed_conversations") else []
    except Exception as e:
        log(f"[WARN] get_allowed_conversations failed: {e!r}")
        return []


def get_account_profile_data(account_email, manifest=None, force_refresh=False):
    return server.get_account_profile_data(account_email, manifest=manifest, force_refresh=force_refresh)


def get_injector_script(usage=None, instance_id="instance_1", account_email=None) -> str:
    if not INJECTOR_PATH.exists():
        return ""
    try:
        code = INJECTOR_PATH.read_text(encoding="utf-8")
        if not code or not code.strip():
            return ""

        actual_account = account_email or get_instance_active_account(instance_id)
        manifest = store.load_manifest()
        sanitized_accounts = store.sanitize_manifest_for_client(manifest)

        instance_usage = None
        if usage and usage.get("email") and str(usage.get("email")).lower().strip() == str(actual_account).lower().strip():
            instance_usage = dict(usage)
        else:
            instance_usage = get_account_profile_data(actual_account, manifest=manifest)

        if not instance_usage and usage:
            instance_usage = dict(usage)

        if isinstance(instance_usage, dict):
            for secret_k in ("token_file", "access_token", "refresh_token", "id_token"):
                instance_usage.pop(secret_k, None)

        allowed_convs = _safe_allowed_convs(migration_engine, actual_account)
        try:
            projects = migration_engine.list_projects(use_cache=True)
        except Exception:
            projects = []

        targets = get_devtools_targets(use_cache=True)
        running_accounts = {t["instance_id"]: get_instance_active_account(t["instance_id"]) for t in targets}
        auth_state = quota.get_live_ide_auth_state(instance_id=instance_id, use_cache=True)

        accounts_payload = json.dumps(
            {
                "activeAccount": instance_usage,
                "savedAccounts": sanitized_accounts,
                "projects": projects,
                "allowedConversations": allowed_convs,
                "runningAccounts": running_accounts,
                "cdpConnected": bool(targets),
                "authState": auth_state,
                "instanceId": instance_id,
            },
            ensure_ascii=False,
        )
        usage_json = json.dumps(instance_usage or {}, ensure_ascii=False)
        saved_manifest_json = json.dumps(sanitized_accounts, ensure_ascii=False)
        allowed_convs_json = json.dumps(allowed_convs, ensure_ascii=False)
        user_settings_json = json.dumps(
            load_user_settings(instance_id=instance_id, account_email=actual_account),
            ensure_ascii=False,
        )

        return (
            "(() => {\n"
            f"  window.__antigravity_instance = {json.dumps(instance_id)};\n"
            f"  window.__antigravity_account = {json.dumps(actual_account)};\n"
            f"  window.__antigravity_quota = {usage_json};\n"
            f"  window.__antigravity_accounts = {accounts_payload};\n"
            f"  window.__antigravity_user_settings = {user_settings_json};\n"
            "  try {\n"
            "    const __s = window.__antigravity_user_settings || {};\n"
            "    if (__s.theme) localStorage.setItem('antigravity:quota_theme', __s.theme);\n"
            "    if (__s.mode) localStorage.setItem('antigravity:quota_mode', __s.mode);\n"
            "    if (__s.fullTheming !== undefined) localStorage.setItem('antigravity:full_app_theming', String(__s.fullTheming));\n"
            "    if (__s.privacyMode !== undefined) localStorage.setItem('antigravity:privacy_mode', String(__s.privacyMode));\n"
            "    if (__s.fontEn) localStorage.setItem('antigravity:custom_font_en', __s.fontEn);\n"
            "    if (__s.fontFa) localStorage.setItem('antigravity:custom_font_fa', __s.fontFa);\n"
            "    if (__s.lang) localStorage.setItem('antigravity:switcher_lang', __s.lang);\n"
            "    if (__s.rtl) localStorage.setItem('antigravity:rtl_config', typeof __s.rtl === 'string' ? __s.rtl : JSON.stringify(__s.rtl));\n"
            "    if (__s.customImportedFonts) localStorage.setItem('antigravity:custom_imported_fonts', JSON.stringify(__s.customImportedFonts));\n"
            "    if (__s.popoverPos) localStorage.setItem('antigravity:popover_pos', JSON.stringify(__s.popoverPos));\n"
            "  } catch(e) {}\n"
            f"  try {{ localStorage.setItem('antigravity:instance_id', {json.dumps(instance_id)}); }} catch(e) {{}}\n"
            f"  try {{ localStorage.setItem('antigravity:account_email', {json.dumps(actual_account)}); }} catch(e) {{}}\n"
            f"  try {{ localStorage.setItem('antigravity:allowed_conversations', {allowed_convs_json}); }} catch(e) {{}}\n"
            "  try { localStorage.setItem('antigravity:active_quota', JSON.stringify(window.__antigravity_quota)); } catch(e) {}\n"
            f"  try {{ localStorage.setItem('antigravity:accounts_manifest', JSON.stringify({saved_manifest_json})); }} catch(e) {{}}\n"
            + code
            + "\n"
            "  if (typeof window.__renderAntigravityBadge === 'function') window.__renderAntigravityBadge();\n"
            "})();\n"
        )
    except Exception as e:
        log(f"[INJECTOR ERROR] get_injector_script failed: {e!r}")
        return ""


def inject_badge_via_devtools(port, usage=None, instance_id="instance_1", account_email=None) -> None:
    with _cdp_conns_lock:
        conn = _active_cdp_connections.get(instance_id)
    if conn and conn.get("ws") and conn.get("loop"):
        try:
            script = get_injector_script(usage, instance_id=instance_id, account_email=account_email or conn.get("account"))
            if script:
                asyncio.run_coroutine_threadsafe(
                    conn["ws"].send(
                        json.dumps({
                            "id": int(time.time() * 1000) % 1000000,
                            "method": "Runtime.evaluate",
                            "params": {"expression": script},
                        })
                    ),
                    conn["loop"],
                )
        except Exception:
            pass


def sync_quota_once(force: bool = False, inject: bool = False):
    global _cached_usage, _last_sync_time
    now = time.time()
    with _sync_lock:
        cur_active = get_instance_active_account("instance_1")
        if not force and _cached_usage and (now - _last_sync_time < 3.0):
            if str(_cached_usage.get("email") or "").lower().strip() == str(cur_active).lower().strip():
                return _cached_usage

        if server.is_dual_launching():
            return _cached_usage or {}

        usage = quota.fetch_quota(force_refresh=force)
        if not usage or not usage.get("session"):
            return _cached_usage or {}

        _cached_usage = usage
        _last_sync_time = now

        if usage.get("email"):
            store.update_app_storage_account(usage["email"], quota_data=usage, instance_id="instance_1")
        store.atomic_write_json(GLOBAL_QUOTA_PATH, usage)

        if inject:
            port = get_devtools_port()
            if port:
                inject_badge_via_devtools(port, usage)

        return usage


def _eval_all_instances(js_code: str) -> None:
    """Run JS in every connected Antigravity workbench window."""
    with _cdp_conns_lock:
        conns = list(_active_cdp_connections.values())
    for c in conns:
        try:
            if c.get("ws") and c.get("loop"):
                asyncio.run_coroutine_threadsafe(
                    c["ws"].send(
                        json.dumps({
                            "id": int(time.time() * 1000) % 1000000,
                            "method": "Runtime.evaluate",
                            "params": {"expression": js_code},
                        })
                    ),
                    c["loop"],
                )
        except Exception:
            pass


def start_shared_oauth_flow(target_account=None, auto_switch=False) -> str:
    server.register_broadcast_hook(broadcast_all_instances)
    server.register_eval_hook(_eval_all_instances)
    return server.start_shared_oauth_flow(target_account=target_account, auto_switch=auto_switch)


def _http_sync_quota(req_inst: str | None = None, force: bool = False):
    norm_inst = vault._normalize_instance_id(req_inst)
    if force:
        server.invalidate_state_caches()

    if norm_inst != "instance_1":
        target_acc = get_instance_active_account(norm_inst)
        sec_path = vault.get_platform_paths(norm_inst)["active_quota_path"]
        usage = None
        if force:
            usage = get_account_profile_data(target_acc, force_refresh=True)
            if usage:
                store.atomic_write_json(sec_path, usage)
        if not usage and sec_path.exists():
            try:
                usage = json.loads(sec_path.read_text(encoding="utf-8"))
            except Exception:
                usage = None
        if not usage or str(usage.get("email") or "").lower().strip() != str(target_acc).lower().strip():
            usage = get_account_profile_data(target_acc, force_refresh=True)
    else:
        target_acc = get_instance_active_account("instance_1")
        usage = sync_quota_once(force=force, inject=False)
        if not usage or str(usage.get("email") or "").lower().strip() != str(target_acc).lower().strip():
            usage = get_account_profile_data(target_acc, force_refresh=force)

    if force:
        threading.Thread(target=broadcast_all_instances, daemon=True).start()
    return usage or {}


def _on_http_switch(resp: dict) -> None:
    global _cached_account_info, _cached_account_time, _cached_usage, _last_sync_time
    q = resp.get("quota")
    _cached_account_info = q
    _cached_account_time = time.time()
    if q:
        _cached_usage = q
        _last_sync_time = time.time()


class QuotaHttpHandler(BaseHTTPRequestHandler):
    timeout = 5.0

    def do_OPTIONS(self):
        server.handle_http_options(self)

    def do_GET(self):
        try:
            with _cdp_conns_lock:
                has_cdp = bool(_active_cdp_connections)
            server.handle_http_get(
                self,
                allow_static=False,
                cdp_connected_override=True if has_cdp else None,
                sync_quota_fn=_http_sync_quota,
            )
        except Exception as e:
            log(f"[HTTP GET ERROR] {e!r}")
            try:
                server.send_json_response(self, 500, {"success": False, "error": str(e)}, cors_origin=None)
            except Exception:
                pass

    def do_POST(self):
        server.handle_http_post(self, on_switch_cb=_on_http_switch, oauth_fn=start_shared_oauth_flow)

    def log_message(self, format, *args):
        return


def start_http_server(port: int = 39281) -> None:
    server.register_broadcast_hook(broadcast_all_instances)
    server.register_eval_hook(_eval_all_instances)
    ThreadingHTTPServer.allow_reuse_address = True
    for attempt in range(40):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port), QuotaHttpHandler)
            srv.daemon_threads = True
            log(f"[INFO] HTTP server successfully listening on port {port}")
            srv.serve_forever()
            break
        except Exception as e:
            log(f"[WARN] HTTP server bind attempt {attempt + 1}/40 failed: {e}")
            time.sleep(1.5)


async def cdp_broadcast_state(ws, extra_toast=None, instance_id="instance_1", account_email=None) -> None:
    try:
        manifest = store.load_manifest()
        sanitized_accounts = store.sanitize_manifest_for_client(manifest)

        target_account = account_email or get_instance_active_account(instance_id)
        if not target_account or (manifest and store.resolve_account_key(target_account, manifest) is None):
            target_account = get_primary_account()

        with _cdp_conns_lock:
            if instance_id in _active_cdp_connections:
                _active_cdp_connections[instance_id]["account"] = target_account

        active_acc = get_account_profile_data(target_account, manifest=manifest)
        allowed_convs = _safe_allowed_convs(migration_engine, target_account)
        try:
            projects = migration_engine.list_projects(use_cache=True)
        except Exception:
            projects = []

        running_accounts = {}
        try:
            for t in get_devtools_targets(use_cache=True):
                acc = t.get("default_account")
                if acc:
                    running_accounts[t["instance_id"]] = acc
        except Exception:
            pass

        auth_state = quota.get_live_ide_auth_state(instance_id=instance_id, use_cache=True)

        payload = json.dumps(
            {
                "activeAccount": active_acc,
                "savedAccounts": sanitized_accounts,
                "runningAccounts": running_accounts,
                "conversations": [],
                "projects": projects,
                "tasks": [],
                "allowedConversations": allowed_convs,
                "cdpConnected": True,
                "authState": auth_state,
                "instanceId": instance_id,
            },
            ensure_ascii=False,
        )

        toast_js = ""
        if extra_toast:
            msg = json.dumps(extra_toast.get("msg", ""), ensure_ascii=False)
            is_err = "true" if extra_toast.get("isErr") else "false"
            toast_js = f"if (typeof window.__showSwitcherToast === 'function') window.__showSwitcherToast({msg}, {is_err});"

        eval_script = f"""(() => {{
            window.__antigravity_instance = {json.dumps(instance_id)};
            window.__antigravity_account = {json.dumps(target_account)};
            window.__antigravity_accounts = {payload};
            try {{ localStorage.setItem('antigravity:instance_id', {json.dumps(instance_id)}); }} catch(e) {{}}
            try {{ localStorage.setItem('antigravity:account_email', {json.dumps(target_account)}); }} catch(e) {{}}
            try {{ localStorage.setItem('antigravity:allowed_conversations', JSON.stringify({json.dumps(allowed_convs)})); }} catch(e) {{}}
            try {{ localStorage.setItem('antigravity:accounts_manifest', JSON.stringify({json.dumps(sanitized_accounts, ensure_ascii=False)})); }} catch(e) {{}}
            if (typeof window.__onSwitcherStateUpdate === 'function') {{
                window.__onSwitcherStateUpdate(window.__antigravity_accounts);
            }}
            {toast_js}
        }})()"""

        await ws.send(
            json.dumps({
                "id": int(time.time() * 1000) % 1000000,
                "method": "Runtime.evaluate",
                "params": {"expression": eval_script},
            })
        )
    except Exception as e:
        log(f"[CDP STATE ERROR] [{instance_id}] {e!r}")


def broadcast_all_instances(extra_toast=None, target_account=None) -> None:
    """Invalidate short-lived caches and push updated state to all connected CDP workbench pages."""
    server.invalidate_state_caches()
    with _cdp_conns_lock:
        conns = list(_active_cdp_connections.values())
    for c in conns:
        try:
            if c.get("ws") and c.get("loop"):
                inst_id = c.get("instance_id", "instance_1")
                acc = (target_account or c.get("account")) if inst_id == "instance_1" else c.get("account")
                asyncio.run_coroutine_threadsafe(
                    cdp_broadcast_state(c["ws"], extra_toast=extra_toast, instance_id=inst_id, account_email=acc),
                    c["loop"],
                )
        except Exception:
            pass


def _restart_switched_account(srv):
    """Finish an explicitly requested restart and publish its outcome."""
    time.sleep(0.8)
    try:
        result = srv.restart_after_account_switch()
    except Exception as error:
        result = {
            "requested": True,
            "launched": False,
            "completed": False,
            "status": "refused",
            "error": "Restart worker failed: " + type(error).__name__,
        }
    log("[RESTART RESULT] " + json.dumps(result, ensure_ascii=False))
    launched = result.get("launched") is True and result.get("status") == "launch_requested"
    broadcast_all_instances(
        {
            "msg": (
                "حساب تغییر یافت؛ اجرای برنامه درخواست شد. آماده‌بودن برنامه هنوز تأیید نشده است."
                if launched
                else "حساب تغییر یافت؛ راه‌اندازی مجدد ایمن انجام نشد. وضعیت برنامه را بررسی کنید."
            ),
            "isErr": not launched,
            "restart": result,
        }
    )
    return result


async def cdp_handle_action(ws, action, data, instance_id="instance_1", default_account=None) -> None:
    try:
        log(f"[CDP IPC ACTION] [{instance_id}] {action}")
        if action == "getState":
            await cdp_broadcast_state(ws, instance_id=instance_id, account_email=default_account)
        elif action == "save":
            res = server.save_current_account()
            broadcast_all_instances({
                "msg": "اکانت فعلی با موفقیت ذخیره شد" if res.get("success") else (res.get("error") or "خطا در ذخیره اکانت"),
                "isErr": not res.get("success"),
            })
        elif action == "restart_app":
            log(f"[CDP RESTART APP] Explicit restart requested from {instance_id}")
            broadcast_all_instances({
                "msg": "در حال راه‌اندازی مجدد برنامه Antigravity... / Restarting Antigravity...",
                "isErr": False,
            })
            threading.Thread(target=lambda: _restart_switched_account(server), daemon=True).start()
        elif action == "switch":
            acc_key = data.get("accountKey") or data.get("account") or data.get("email")
            no_restart = data.get("noRestart", True)
            log(f"[CDP SWITCH] Target: {acc_key} (no_restart={no_restart})")
            res = server.switch_account(acc_key, no_restart=True)
            if res.get("success"):
                res["restart"] = {
                    "requested": not bool(no_restart),
                    "launched": False,
                    "completed": False,
                    "status": "pending" if not no_restart else "not_requested",
                }
                _on_http_switch(res)
                with _cdp_conns_lock:
                    if instance_id in _active_cdp_connections:
                        _active_cdp_connections[instance_id]["account"] = res.get("account") or acc_key
                broadcast_all_instances(
                    {
                        "msg": f"حساب به {res.get('email') or acc_key} تغییر یافت." + (" در حال ری‌استارت..." if not no_restart else ""),
                        "isErr": False,
                        "restart": res["restart"],
                    },
                    target_account=res.get("account") or acc_key,
                )
                if not no_restart:
                    threading.Thread(target=lambda: _restart_switched_account(server), daemon=True).start()
            else:
                if res.get("needs_reauth"):
                    start_shared_oauth_flow(target_account=acc_key)
                await cdp_broadcast_state(
                    ws,
                    {"msg": res.get("error") or "خطا در جابجایی حساب", "isErr": True},
                    instance_id=instance_id,
                    account_email=default_account,
                )
        elif action == "import":
            tok = (data.get("token") or "").replace("\r", "").replace("\n", "").strip()
            res = server.import_token(tok)
            broadcast_all_instances({
                "msg": f"اکانت {res.get('email', '')} با موفقیت افزوده شد" if res.get("success") else (res.get("error") or "خطا در ثبت توکن"),
                "isErr": not res.get("success"),
            })
        elif action == "delete":
            ak = data.get("accountKey") or data.get("account") or data.get("email")
            res = server.delete_account(ak)
            broadcast_all_instances({
                "msg": "اکانت از لیست حذف شد" if res.get("success") else (res.get("error") or "خطا در حذف"),
                "isErr": not res.get("success"),
            })
        elif action == "launch_dual":
            ak = data.get("accountKey") or data.get("account") or data.get("email")
            p_path = data.get("projectPath") or data.get("path")
            log(f"[CDP LAUNCH DUAL] Request received for account: {ak}, project: {p_path}")
            res = server.launch_dual_instance(ak, project_path=p_path)
            log(f"[CDP LAUNCH DUAL RESULT] {res}")
            display_name = ak or "اکانت دوم"
            success = res.get("success", False)
            if res.get("needs_reauth"):
                start_shared_oauth_flow(target_account=ak)
            msg = res.get("msg") or (f"پنجره دوم با اکانت {display_name} اجرا شد" if success else (res.get("error") or "خطا در اجرای پنجره دوم"))
            broadcast_all_instances({"msg": msg, "isErr": not success})
        elif action == "oauth_signin":
            tgt = data.get("accountKey") or data.get("email")
            if "auto_switch" in data:
                auto_sw = bool(data["auto_switch"])
            elif "autoSwitch" in data:
                auto_sw = bool(data["autoSwitch"])
            else:
                auto_sw = not bool(data.get("noRestart", False))
            start_shared_oauth_flow(target_account=tgt, auto_switch=auto_sw)
        elif action == "migrate":
            res = migration_engine.migrate_conversations(
                data.get("conversationIds", []),
                data.get("sourceAccount", ""),
                data.get("targetAccount", ""),
                mode=data.get("mode", "copy"),
                structure=data.get("structure", "separate"),
                dual_sync=data.get("dualSync", False),
                project_id=data.get("projectId"),
            )
            broadcast_all_instances({
                "msg": f"انتقال {res.get('migrated_count', 0)} گفتگو با موفقیت انجام شد" if res.get("success") else (res.get("error") or "خطا در انتقال"),
                "isErr": not res.get("success"),
            })
        elif action in ("assignProject", "setProjectAssignment"):
            res = migration_engine.set_project_assignment(
                data.get("projectId"),
                data.get("accounts") or data.get("account", []),
                sync_mode=data.get("syncMode", "shared"),
                enabled=data.get("enabled"),
            )
            broadcast_all_instances({
                "msg": "تنظیمات دسترسی پروژه بروزرسانی شد" if res.get("success") else (res.get("error") or "خطا در تخصیص پروژه"),
                "isErr": not res.get("success"),
            })
        elif action == "toggleProjectAll":
            st = data.get("state", "all")
            res = migration_engine.toggle_project_all(data.get("projectId"), state=st)
            broadcast_all_instances({
                "msg": f"پروژه برای {'همه اکانت‌ها فعال' if st == 'all' else 'همه اکانت‌ها غیرفعال'} شد" if res.get("success") else "خطا در تغییر وضعیت پروژه",
                "isErr": not res.get("success"),
            })
        elif action in ("setProjectQuotaAccount", "set_project_quota_account"):
            p_id = data.get("projectId")
            acc = data.get("account") or data.get("quotaAccount")
            res = migration_engine.set_project_quota_account(p_id, acc)
            if res.get("success") and acc and not bool(data.get("noSwitch", False)):
                server.switch_account(acc, no_restart=True)
            broadcast_all_instances({
                "msg": f"حساب کسر سهمیه پروژه به {acc} تنظیم شد" if res.get("success") else "خطا در تنظیم حساب سهمیه",
                "isErr": not res.get("success"),
            })
        elif action in ("setTaskQuotaAccount", "set_task_quota_account"):
            t_name = data.get("taskName") or data.get("name")
            acc = data.get("account") or data.get("quotaAccount")
            res = migration_engine.set_task_quota_account(t_name, acc)
            broadcast_all_instances({
                "msg": f"حساب کسر سهمیه تسک به {acc} تنظیم شد" if res.get("success") else "خطا در تنظیم حساب سهمیه",
                "isErr": not res.get("success"),
            })
        elif action in ("runGuardedTask", "run_guarded_task"):
            t_name = data.get("taskName") or data.get("name")
            res = migration_engine.run_guarded_task(t_name)
            broadcast_all_instances({
                "msg": res.get("msg") or res.get("error") or "دستور تسک اجرا شد",
                "isErr": not res.get("success"),
            })
        elif action == "syncProject":
            tgt = data.get("targetAccount") or get_secondary_account()
            res = migration_engine.sync_project_to_account(
                data.get("projectId"),
                tgt,
                include_conversations=data.get("includeConversations", False),
            )
            broadcast_all_instances({
                "msg": f"پروژه با موفقیت به {tgt} سینک شد" if res.get("success") else (res.get("error") or "خطا در سینک پروژه"),
                "isErr": not res.get("success"),
            })
        elif action == "unlinkProject":
            acc = data.get("account") or get_secondary_account()
            res = migration_engine.unlink_project_from_account(data.get("projectId"), acc)
            broadcast_all_instances({
                "msg": f"پروژه با موفقیت از {acc} جدا شد" if res.get("success") else (res.get("error") or "خطا در جداسازی پروژه"),
                "isErr": not res.get("success"),
            })
        elif action in ("assignTask", "setTaskAssignment"):
            res = migration_engine.set_task_account_assignment(
                data.get("taskName") or data.get("name"),
                data.get("accounts") or data.get("account", []),
                enabled=data.get("enabled"),
            )
            broadcast_all_instances({
                "msg": "تنظیمات دسترسی تسک بروزرسانی شد" if res.get("success") else (res.get("error") or "خطا در تخصیص تسک"),
                "isErr": not res.get("success"),
            })
        elif action == "toggleTaskAll":
            st = data.get("state", "all")
            res = migration_engine.toggle_task_all(data.get("taskName") or data.get("name"), state=st)
            broadcast_all_instances({
                "msg": f"تسک برای {'همه اکانت‌ها فعال' if st == 'all' else 'همه اکانت‌ها غیرفعال'} شد" if res.get("success") else "خطا در تغییر وضعیت تسک",
                "isErr": not res.get("success"),
            })
        elif action == "isolateTask":
            t_name = data.get("taskName") or data.get("name")
            owner = data.get("ownerAccount") or get_primary_account()
            iso = data.get("isolateFromAccount2", data.get("isolate", True))
            insts = data.get("allowedInstances")
            req_acc = get_secondary_account() if instance_id == "instance_2" else (data.get("account") or data.get("callerAccount") or default_account)
            res = migration_engine.set_task_isolation(
                t_name,
                owner,
                isolate_from_account2=iso,
                allowed_instances=insts,
                requesting_account=req_acc,
            )
            broadcast_all_instances({
                "msg": f"ایزولاسیون تسک {t_name} اعمال شد" if res.get("success") else (res.get("error") or "خطا در ایزولاسیون تسک"),
                "isErr": not res.get("success"),
            })
        elif action == "toggleTask":
            t_name = data.get("taskName") or data.get("name")
            enb = data.get("enable", data.get("enabled", True))
            acc = get_secondary_account() if instance_id == "instance_2" else (data.get("account") or data.get("callerAccount") or default_account)
            res = migration_engine.toggle_task_state(t_name, enable=enb, requesting_account=acc)
            broadcast_all_instances({
                "msg": res.get("msg") or res.get("error") or "وضعیت تسک تغییر کرد",
                "isErr": not res.get("success"),
            })
        elif action == "assignConversation":
            res = migration_engine.assign_conversation_account(
                data.get("conversationId"),
                data.get("account"),
                action=data.get("action", "add"),
            )
            broadcast_all_instances({
                "msg": "تخصیص گفتگو بروزرسانی شد" if res.get("success") else "خطا در تخصیص گفتگو",
                "isErr": not res.get("success"),
            })
        elif action in ("save_user_settings", "saveSettings"):
            inst = data.get("instance_id") or instance_id
            acc = data.get("account") or default_account
            ok, _ = save_user_settings(data, instance_id=inst, account_email=acc)
            log(f"[SETTINGS] Saved user settings via CDP for {inst} / {acc}: {ok}")
    except Exception as e:
        log(f"[CDP ACTION ERROR] [{instance_id}] {e!r}")


async def cdp_instance_worker(instance_id, port, default_account) -> None:
    if websockets is None:
        return
    loop = asyncio.get_running_loop()
    log(f"[CDP] Starting worker for {instance_id} on port {port}")
    health_task = None
    try:
        targets = await asyncio.to_thread(cdp.fetch_cdp_targets_list, port, 2.0)
        if not targets:
            return
        ls_port, _ = await asyncio.to_thread(quota.discover_language_server, instance_id, True)
        page = cdp.select_workbench_target(targets, ls_port=ls_port)
        if not page or not page.get("webSocketDebuggerUrl"):
            return

        page_id = page.get("id")
        ws_url = page["webSocketDebuggerUrl"]
        log(f"[CDP] [{instance_id}] Connecting to workbench {ws_url} (url={page.get('url', '')[:60]})")

        async with websockets.connect(
            ws_url,
            ping_interval=30,
            ping_timeout=25,
            max_size=16 * 1024 * 1024,
        ) as ws:
            with _cdp_conns_lock:
                _active_cdp_connections[instance_id] = {
                    "ws": ws,
                    "port": port,
                    "account": default_account,
                    "loop": loop,
                    "instance_id": instance_id,
                    "page_id": page_id,
                }

            async def inject_full_bundle(reason="init"):
                await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
                await ws.send(json.dumps({"id": 2, "method": "Page.enable"}))
                await ws.send(json.dumps({"id": 3, "method": "DOMStorage.enable"}))
                await ws.send(json.dumps({"id": 4, "method": "Runtime.addBinding", "params": {"name": "__aqm_daemon_ipc"}}))
                with _cdp_conns_lock:
                    cur_acc = _active_cdp_connections.get(instance_id, {}).get("account") or default_account
                init_script = get_injector_script(_cached_usage, instance_id=instance_id, account_email=cur_acc)
                if not init_script:
                    log(f"[CDP] [{instance_id}] Injector script empty ({reason}); skipping inject.")
                    return
                await ws.send(json.dumps({
                    "id": 5,
                    "method": "Page.addScriptToEvaluateOnNewDocument",
                    "params": {"source": init_script},
                }))
                await ws.send(json.dumps({
                    "id": 6,
                    "method": "Runtime.evaluate",
                    "params": {"expression": init_script},
                }))
                await cdp_broadcast_state(ws, instance_id=instance_id, account_email=cur_acc)
                log(f"[CDP] [{instance_id}] Injected plugin bundle ({reason}).")

            await inject_full_bundle("connect")

            async def _dom_health_watchdog():
                while True:
                    await asyncio.sleep(3.5)
                    try:
                        cur_targets = await asyncio.to_thread(cdp.fetch_cdp_targets_list, port, 1.5)
                        cur_wb = [
                            t for t in (cur_targets or [])
                            if cdp.is_antigravity_workbench_target(t, ls_port=ls_port)
                        ]
                        if cur_wb and page_id and not any(t.get("id") == page_id for t in cur_wb):
                            log(f"[CDP] [{instance_id}] Workbench page replaced; reconnecting to new target.")
                            await ws.close()
                            return

                        await ws.send(json.dumps({
                            "id": 777001,
                            "method": "Runtime.evaluate",
                            "params": {
                                "expression": "Boolean(typeof window.__renderAntigravityBadge === 'function' && (document.getElementById('antigravity-account-pill') || document.getElementById('antigravity-usage-badge')))",
                                "returnByValue": True,
                            },
                        }))
                    except Exception:
                        return

            health_task = asyncio.create_task(_dom_health_watchdog())

            if instance_id == "instance_1" and not server.is_dual_launching():
                token = vault.get_keychain_token()
                if token:
                    m = store.load_manifest()
                    acc_info = quota.fetch_quota_and_tier(token)
                    email = acc_info.get("email") if acc_info else None
                    if email and store.resolve_account_key(email, m) is None:
                        log(f"[AUTO-SAVE] Saving newly active account {email}")
                        server.save_current_account()
                        await cdp_broadcast_state(ws, instance_id=instance_id, account_email=default_account)

            async for msg in ws:
                try:
                    d = json.loads(msg)
                    if d.get("id") == 777001:
                        alive_ok = d.get("result", {}).get("result", {}).get("value", True)
                        if not alive_ok:
                            log(f"[CDP WATCHDOG] [{instance_id}] Plugin missing in DOM — auto-healing now!")
                            await inject_full_bundle("watchdog-heal")
                        continue

                    method = d.get("method")
                    if method == "Runtime.bindingCalled" and d.get("params", {}).get("name") == "__aqm_daemon_ipc":
                        payload_raw = d.get("params", {}).get("payload", "{}")
                        payload = json.loads(payload_raw)
                        action = payload.get("action")
                        if action:
                            with _cdp_conns_lock:
                                cur_acc = _active_cdp_connections.get(instance_id, {}).get("account") or default_account
                            await cdp_handle_action(ws, action, payload, instance_id=instance_id, default_account=cur_acc)

                    elif method in ("DOMStorage.domStorageItemAdded", "DOMStorage.domStorageItemUpdated"):
                        params = d.get("params", {})
                        if params.get("key") == "antigravity:switcher_command":
                            try:
                                val = json.loads(params.get("newValue", "{}"))
                                action = val.get("action")
                                if action:
                                    with _cdp_conns_lock:
                                        cur_acc = _active_cdp_connections.get(instance_id, {}).get("account") or default_account
                                    await cdp_handle_action(ws, action, val, instance_id=instance_id, default_account=cur_acc)
                            except Exception:
                                pass

                    elif method in ("Page.loadEventFired", "Page.frameNavigated", "Runtime.executionContextsCleared"):
                        await inject_full_bundle(method)
                except Exception as e:
                    log(f"[CDP MSG ERROR] [{instance_id}] {e!r}")

    except Exception as e:
        log(f"[CDP WORKER ERROR] [{instance_id}] {e!r}")
    finally:
        if health_task:
            try:
                health_task.cancel()
            except Exception:
                pass
        with _cdp_conns_lock:
            _active_cdp_connections.pop(instance_id, None)
        log(f"[CDP WORKER CLOSED] [{instance_id}]")


async def cdp_supervisor_loop() -> None:
    if websockets is None:
        log("[CDP] websockets package unavailable; CDP injection disabled, HTTP runtime remains active.")
        return

    running_tasks = {}
    running_ports = {}
    while True:
        try:
            targets = await asyncio.to_thread(get_devtools_targets, False)
            for inst_id, task in list(running_tasks.items()):
                if task.done():
                    running_tasks.pop(inst_id, None)
                    running_ports.pop(inst_id, None)

            for tgt in targets:
                inst_id = tgt["instance_id"]
                new_port = tgt["port"]
                if inst_id in running_tasks and running_ports.get(inst_id) != new_port:
                    log(f"[CDP SUPERVISOR] Port changed for {inst_id}: {running_ports.get(inst_id)} -> {new_port}")
                    try:
                        running_tasks[inst_id].cancel()
                    except Exception:
                        pass
                    running_tasks.pop(inst_id, None)

                if inst_id not in running_tasks or running_tasks[inst_id].done():
                    running_tasks[inst_id] = asyncio.create_task(
                        cdp_instance_worker(inst_id, new_port, tgt["default_account"])
                    )
                    running_ports[inst_id] = new_port
        except Exception as e:
            log(f"[CDP SUPERVISOR ERROR] {e!r}")

        await asyncio.sleep(2.0 if targets else 8.0)


def start_cdp_supervisor() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(cdp_supervisor_loop())


def acquire_daemon_lock(path=None):
    """Keep one service per user store; never terminate another process."""
    path = Path(path) if path is not None else vault.get_platform_paths()["antigravity_dir"] / "quota_daemon.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+b")
    try:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            Path(str(path) + ".pid").write_text(str(os.getpid()), encoding="utf-8")
        except Exception:
            pass
        return handle
    except OSError:
        handle.close()
        return None


def _is_daemon_http_healthy(port: int = 39281) -> bool:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(2):
        try:
            with opener.open(f"http://127.0.0.1:{int(port)}/health", timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def _recover_unhealthy_daemon(lock_path=None) -> None:
    """Terminate a wedged sync_daemon.py process ONLY when its /health endpoint fails."""
    if _is_daemon_http_healthy():
        return
    lp = Path(lock_path) if lock_path is not None else vault.get_platform_paths()["antigravity_dir"] / "quota_daemon.lock"
    pid_file = Path(str(lp) + ".pid")
    pids = []
    try:
        if pid_file.is_file():
            raw = pid_file.read_text(encoding="utf-8").strip()
            if raw.isdigit():
                pids.append(int(raw))
    except Exception:
        pass
    try:
        import psutil
        me = os.getpid()
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = (proc.info.get("name") or "").lower()
                if "python" not in pname or proc.info["pid"] == me:
                    continue
                cmd = " ".join(proc.cmdline() or []).lower()
                if "sync_daemon.py" in cmd and "--once" not in cmd:
                    if proc.info["pid"] not in pids:
                        pids.append(proc.info["pid"])
            except Exception:
                continue
        for pid in pids:
            if pid == me:
                continue
            try:
                p = psutil.Process(pid)
                cmd = " ".join(p.cmdline() or []).lower()
                if "sync_daemon.py" in cmd and (time.time() - p.create_time()) > 8.0:
                    log(f"[RECOVER] Stopping unhealthy sync_daemon.py PID={pid}")
                    p.kill()
                    p.wait(timeout=2.0)
            except Exception:
                pass
    except ImportError:
        pass


def refresh_all_accounts_tokens() -> None:
    """Refresh tokens and manifest quota summaries for currently registered accounts only."""
    try:
        manifest = store.load_manifest()
        if not manifest:
            return

        updated_manifest = False
        for acc_name, entry in list(manifest.items()):
            if not isinstance(entry, dict):
                continue
            try:
                t_str = store.read_account_token(acc_name, manifest)
                if not t_str:
                    continue

                expected = str(entry.get("email") or acc_name).lower().strip()
                tok_email = vault.extract_token_email(t_str)
                if tok_email and tok_email.lower().strip() != expected:
                    log(f"[SYNC WARNING] Token for '{acc_name}' belongs to '{tok_email}'; flagging reauth.")
                    entry["needs_reauth"] = True
                    entry["token_file"] = ""
                    updated_manifest = True
                    continue

                fresh_str = vault.ensure_fresh_token(t_str, account_email=expected)
                q = quota.fetch_quota_and_tier(fresh_str, force_refresh=True)
                if q:
                    sess = q.get("session") or {}
                    week = q.get("weekly") or {}
                    if sess.get("remaining_pct") is not None:
                        entry["remaining_pct"] = float(sess["remaining_pct"])
                    if week.get("remaining_pct") is not None:
                        entry["weekly_remaining_pct"] = float(week["remaining_pct"])
                    if week.get("resets_in"):
                        entry["weekly_resets_in"] = week["resets_in"]
                    entry["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    updated_manifest = True
            except Exception:
                pass

        if updated_manifest:
            store.save_manifest(manifest)
    except Exception:
        pass


def start_optional_theme_service(config_path=None) -> None:
    """Attach optional legacy Codex theme injector if explicitly enabled."""
    config_path = Path(config_path) if config_path is not None else vault.get_platform_paths()["antigravity_dir"] / "theme_services.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(config, dict) or config.get("codex_theme") is not True:
            return
    except (OSError, ValueError):
        return

    def _load_chatgpt_cdp_daemon():
        try:
            from legacy.chatgpt import chatgpt_cdp_daemon as ccd
            return ccd
        except ImportError:
            try:
                import chatgpt_cdp_daemon as ccd
                return ccd
            except ImportError:
                return None

    if _load_chatgpt_cdp_daemon() is None:
        log("[THEME] Legacy ChatGPT CDP module not present; skipping optional theme service.")
        return

    def supervise():
        while True:
            try:
                ccd = _load_chatgpt_cdp_daemon()
                if ccd is None:
                    return
                asyncio.run(ccd.daemon_loop(ports=[9223, 9224], poll_interval=6.0))
            except Exception:
                log("[THEME] Passive Codex theme connection failed; retrying.")
                time.sleep(3)

    threading.Thread(target=supervise, daemon=True).start()
    log("[THEME] Passive Codex theme service enabled; automatic app relaunch is disabled.")


def daemon_loop() -> None:
    owner_lock = acquire_daemon_lock()
    if owner_lock is None and "--recover-stale" in sys.argv:
        _recover_unhealthy_daemon()
        owner_lock = acquire_daemon_lock()
    if owner_lock is None:
        log("[INFO] Existing service owns this store; leaving it running.")
        return

    server.register_broadcast_hook(broadcast_all_instances)
    server.register_eval_hook(_eval_all_instances)

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [INFO] Quota Monitor active; automatic application restarts disabled.", flush=True)
    start_optional_theme_service()

    threading.Thread(target=start_http_server, daemon=True).start()
    threading.Thread(target=start_cdp_supervisor, daemon=True).start()
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [CDP] Native CDP supervisor thread started.", flush=True)

    try:
        refresh_all_accounts_tokens()
    except Exception:
        pass

    try:
        sync_quota_once(force=True, inject=True)
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [SYNC] Initial quota sync & injection completed.", flush=True)
    except Exception as e:
        print(f"[ERROR] Initial sync error: {e}", flush=True)

    last_heartbeat_time = time.time()
    last_injected_port = None
    last_verify_time = 0.0

    while True:
        time.sleep(3)
        now = time.time()

        try:
            targets = get_devtools_targets(use_cache=True)
            if targets:
                if (targets != last_injected_port) or (now - last_verify_time > 30):
                    last_verify_time = now
                    last_injected_port = targets
                    if _cached_usage:
                        for tgt in targets:
                            inject_badge_via_devtools(
                                tgt["port"],
                                _cached_usage,
                                instance_id=tgt["instance_id"],
                                account_email=tgt["default_account"],
                            )
                    else:
                        sync_quota_once(force=True, inject=True)
            else:
                last_injected_port = None
        except Exception:
            pass

        if now - last_heartbeat_time >= 900:
            last_heartbeat_time = now
            try:
                refresh_all_accounts_tokens()
                sync_quota_once(force=False)
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [HEARTBEAT] Passive quota heartbeat and account tokens refreshed.", flush=True)
            except Exception:
                pass


if __name__ == "__main__":
    try:
        if "--once" in sys.argv:
            sync_quota_once(force=True)
            print("Synced successfully.")
        else:
            daemon_loop()
    except Exception:
        import traceback

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[FATAL] {time.strftime('%Y-%m-%d %H:%M:%S')} {traceback.format_exc()}\n")
