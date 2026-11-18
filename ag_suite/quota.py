# -*- coding: utf-8 -*-
"""Connect-RPC & CloudCode 6-pool quota engine, LanguageServer discovery, and suite diagnostics."""

import copy
import datetime
import json
import os
import re
import ssl
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from . import cdp, store, vault

ORDERED_POOLS = [
    "Gemini 4 Hydrogen",
    "Gemini 4 Argon",
    "Gemini 4 Carbon & Orchestrator",
    "Gemini 3.8 Flash",
    "Claude 4.6 (Opus & Sonnet)",
    "GPT-OSS 120B",
]

_SSL_UNVERIFIED = ssl._create_unverified_context()
_LOOPBACK_HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_LOOPBACK_HTTPS = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPSHandler(context=_SSL_UNVERIFIED),
)

_LS_LOCK = threading.Lock()
_LS_CACHE = {"port": None, "csrf": None, "time": 0.0, "instance_id": None}
_LS_CACHE_TTL = 30.0

_AUTH_LOCK = threading.Lock()
_AUTH_CACHE: dict[str, dict] = {}
_AUTH_CACHE_TTL = 5.0

_QUOTA_LOCK = threading.Lock()
_QUOTA_CACHE: dict[str, dict] = {}
_QUOTA_CACHE_TTL = 30.0


def format_countdown(iso_str) -> tuple[str, str, int]:
    """Return (countdown_text, local_time_str, seconds_remaining) for a reset timestamp."""
    if not iso_str:
        return "N/A", "N/A", 0
    try:
        if isinstance(iso_str, dict) and "seconds" in iso_str:
            dt = datetime.datetime.fromtimestamp(int(iso_str["seconds"]), tz=datetime.timezone.utc)
        elif isinstance(iso_str, (int, float)):
            dt = datetime.datetime.fromtimestamp(int(iso_str), tz=datetime.timezone.utc)
        elif isinstance(iso_str, str):
            raw = iso_str.strip()
            if raw.isdigit():
                dt = datetime.datetime.fromtimestamp(int(raw), tz=datetime.timezone.utc)
            else:
                dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
        else:
            return "N/A", "N/A", 0

        secs = int((dt - datetime.datetime.now(datetime.timezone.utc)).total_seconds())
        local_time = dt.astimezone().strftime("%I:%M %p")
        if secs <= 0:
            return "Ready", local_time, 0
        d = secs // 86400
        h = (secs % 86400) // 3600
        m = (secs % 3600) // 60
        parts = []
        if d > 0:
            parts.append(f"{d} d")
        if h > 0:
            parts.append(f"{h} hr")
        if (m > 0 and d == 0) or (d == 0 and h == 0):
            parts.append(f"{m} min")
        return " ".join(parts) or "Ready", local_time, secs
    except Exception:
        return "N/A", "N/A", 0


def invalidate_ls_cache(instance_id: str | None = None) -> None:
    """Clear Language Server discovery cache."""
    with _LS_LOCK:
        if instance_id is None or _LS_CACHE.get("instance_id") == (instance_id or "default"):
            _LS_CACHE.update({"port": None, "csrf": None, "time": 0.0, "instance_id": None})
    with _AUTH_LOCK:
        _AUTH_CACHE.clear()


def _probe_ls_csrf_from_port(ls_port: int) -> str | None:
    if not ls_port or int(ls_port) in cdp.EXCLUDED_LOCAL_PORTS:
        return None
    try:
        req = urllib.request.Request(f"https://127.0.0.1:{int(ls_port)}/")
        with _LOOPBACK_HTTPS.open(req, timeout=1.0) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        m_csrf = re.search(r'"csrfToken"\s*:\s*"([^"]+)"', html)
        return m_csrf.group(1) if m_csrf else None
    except Exception:
        return None


def _probe_ls_rpc_ready(ls_port: int, csrf: str) -> bool:
    if not ls_port or not csrf or int(ls_port) in cdp.EXCLUDED_LOCAL_PORTS:
        return False
    try:
        req = urllib.request.Request(
            f"https://127.0.0.1:{int(ls_port)}/exa.language_server_pb.LanguageServerService/GetServerConfiguration",
            headers={
                "Content-Type": "application/json",
                "Connect-Protocol-Version": "1",
                "x-codeium-csrf-token": csrf,
            },
            data=b"{}",
        )
        with _LOOPBACK_HTTPS.open(req, timeout=0.6) as resp:
            return resp.status == 200
    except Exception:
        return False


def _extract_csrf_from_cmdline(cmdline: list[str]) -> str | None:
    for i, arg in enumerate(cmdline):
        s_arg = str(arg)
        if s_arg == "--csrf_token" and i + 1 < len(cmdline):
            return str(cmdline[i + 1]).strip()
        if s_arg.startswith("--csrf_token="):
            return s_arg.split("=", 1)[1].strip()
    m = re.search(r"--csrf_token[\s=]+([A-Za-z0-9-]+)", " ".join(str(x) for x in cmdline))
    return m.group(1) if m else None


def _discover_ls_via_cdp(instance_id: str | None) -> tuple[int | None, str | None]:
    dt_paths = [vault.get_platform_paths(instance_id)["devtools_port_path"]]
    if instance_id and vault._normalize_instance_id(instance_id) != "instance_1":
        dt_paths.append(vault.get_platform_paths("instance_1")["devtools_port_path"])

    for dt_path in dt_paths:
        if not dt_path.is_file():
            continue
        try:
            first_line = dt_path.read_text(encoding="utf-8", errors="ignore").splitlines()[0].strip()
            cdp_port = int(first_line)
        except Exception:
            continue

        targets = None
        for suffix in ("/json/list", "/json"):
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{cdp_port}{suffix}")
                with _LOOPBACK_HTTP.open(req, timeout=1.0) as r:
                    data = json.loads(r.read().decode("utf-8", errors="ignore"))
                    if isinstance(data, list):
                        targets = data
                        break
            except Exception:
                continue
        if not targets:
            continue

        candidate_ports: list[int] = []
        for t in targets:
            if not isinstance(t, dict):
                continue
            url = str(t.get("url") or "").strip()
            t_type = t.get("type")
            is_wb = cdp.is_antigravity_workbench_target(t)
            is_local_sub = (
                t_type in ("page", "iframe", "webview")
                and re.match(r"^https://(?:127\.0\.0\.1|localhost):(\d+)(/.*)?$", url, re.I) is not None
                and not urllib.parse.urlparse(url).path.lower().startswith(("/sidecar", "/oauth2callback"))
            )
            if not (is_wb or is_local_sub):
                continue
            for m in re.finditer(r"https?://(?:127\.0\.0\.1|localhost):(\d+)", url, re.I):
                p_num = int(m.group(1))
                if p_num not in cdp.EXCLUDED_LOCAL_PORTS and p_num not in candidate_ports:
                    candidate_ports.append(p_num)

        for ls_port in candidate_ports:
            csrf = _probe_ls_csrf_from_port(ls_port)
            if csrf:
                return ls_port, csrf
    return None, None


def _discover_ls_via_psutil(instance_id: str | None) -> tuple[int | None, str | None]:
    try:
        import psutil
    except ImportError:
        return None, None

    norm_inst = vault._normalize_instance_id(instance_id)
    folder_needle = vault.normalize_instance_folder(norm_inst).lower()
    matched_procs = []
    fallback_procs = []

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            pname = (proc.info.get("name") or "").lower()
            if "language_server" not in pname:
                continue
            cmdline = proc.info.get("cmdline") or []
            csrf = _extract_csrf_from_cmdline(cmdline)
            if not csrf:
                continue
            cmd_low = " ".join(str(x).lower() for x in cmdline)
            if norm_inst == "instance_1":
                if "antigravity-instance" not in cmd_low:
                    matched_procs.append((proc, csrf))
                else:
                    fallback_procs.append((proc, csrf))
            else:
                if folder_needle in cmd_low or norm_inst in cmd_low:
                    matched_procs.append((proc, csrf))
                else:
                    fallback_procs.append((proc, csrf))
        except Exception:
            continue

    for proc, csrf in matched_procs + fallback_procs:
        try:
            net_fn = getattr(proc, "net_connections", None) or getattr(proc, "connections", None)
            if not net_fn:
                continue
            ports = []
            for conn in net_fn(kind="tcp"):
                if getattr(conn, "status", None) == "LISTEN" and getattr(conn, "laddr", None):
                    if conn.laddr.ip == "127.0.0.1" and int(conn.laddr.port) > 1024:
                        p_num = int(conn.laddr.port)
                        if p_num not in cdp.EXCLUDED_LOCAL_PORTS and p_num not in ports:
                            ports.append(p_num)
            for p_num in sorted(ports, reverse=True):
                if _probe_ls_rpc_ready(p_num, csrf):
                    return p_num, csrf
        except Exception:
            continue
    return None, None


def _discover_ls_via_os_cli() -> tuple[int | None, str | None]:
    sys_name = vault.get_current_system()
    if sys_name == "windows":
        try:
            res = subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name LIKE 'language_server%'\" | Select-Object -ExpandProperty CommandLine",
                ],
                capture_output=True, text=True, timeout=3.0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
            )
            m_tok = re.search(r"--csrf_token[\s=]+([A-Za-z0-9-]+)", res.stdout or "")
            if not m_tok:
                return None, None
            csrf = m_tok.group(1)
            res_net = subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    "Get-NetTCPConnection -State Listen | Where-Object { $_.LocalAddress -eq '127.0.0.1' } | Select-Object -ExpandProperty LocalPort",
                ],
                capture_output=True, text=True, timeout=3.0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
            )
            for tok in (res_net.stdout or "").split():
                if tok.isdigit() and int(tok) > 40000:
                    if _probe_ls_rpc_ready(int(tok), csrf):
                        return int(tok), csrf
        except Exception:
            pass
        return None, None

    try:
        res = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True, text=True, timeout=2.0)
        for line in (res.stdout or "").splitlines():
            if "language_server" not in line.lower():
                continue
            m_tok = re.search(r"--csrf_token[\s=]+([A-Za-z0-9-]+)", line)
            m_pid = re.match(r"^\s*(\d+)\s+", line)
            if not (m_tok and m_pid):
                continue
            csrf, pid = m_tok.group(1), m_pid.group(1)
            lsof_res = subprocess.run(
                ["lsof", "-nP", "-a", "-p", pid, "-iTCP", "-sTCP:LISTEN"],
                capture_output=True, text=True, timeout=2.0,
            )
            for m_p in re.finditer(r"127\.0\.0\.1:(\d+)", lsof_res.stdout or ""):
                p_num = int(m_p.group(1))
                if p_num not in cdp.EXCLUDED_LOCAL_PORTS and _probe_ls_rpc_ready(p_num, csrf):
                    return p_num, csrf
    except Exception:
        pass
    return None, None


def discover_language_server(instance_id: str | None = None, use_cache: bool = True) -> tuple[int | None, str | None]:
    """Discover local Antigravity Language Server HTTPS port and CSRF token with 30s cache."""
    inst_key = str(instance_id or "default").strip() or "default"
    if use_cache:
        with _LS_LOCK:
            if (
                _LS_CACHE.get("port")
                and _LS_CACHE.get("csrf")
                and _LS_CACHE.get("instance_id") == inst_key
                and (time.time() - _LS_CACHE.get("time", 0.0)) < _LS_CACHE_TTL
            ):
                return _LS_CACHE["port"], _LS_CACHE["csrf"]

    ls_port, csrf = _discover_ls_via_cdp(instance_id)
    if not (ls_port and csrf):
        ls_port, csrf = _discover_ls_via_psutil(instance_id)
    if not (ls_port and csrf):
        try:
            import psutil  # noqa: F401
        except ImportError:
            ls_port, csrf = _discover_ls_via_os_cli()

    if ls_port and csrf:
        with _LS_LOCK:
            _LS_CACHE.update({"port": ls_port, "csrf": csrf, "time": time.time(), "instance_id": inst_key})
        return ls_port, csrf
    return None, None


def call_ls_rpc(ls_port: int, csrf: str, method: str, payload: dict | None = None, timeout: float = 3.5) -> dict:
    """Invoke Connect-RPC method on local Antigravity Language Server bypassing proxies."""
    url = f"https://127.0.0.1:{int(ls_port)}/exa.language_server_pb.LanguageServerService/{method}"
    req = urllib.request.Request(
        url,
        headers={
            "Content-Type": "application/json",
            "Connect-Protocol-Version": "1",
            "x-codeium-csrf-token": csrf,
            "User-Agent": "antigravity",
        },
        data=json.dumps(payload or {}).encode("utf-8"),
    )
    with _LOOPBACK_HTTPS.open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_live_ide_auth_state(instance_id: str | None = None, use_cache: bool = True) -> dict:
    """Compare live running Language Server email with OS vault credential email."""
    norm_inst = vault._normalize_instance_id(instance_id)
    if use_cache:
        with _AUTH_LOCK:
            entry = _AUTH_CACHE.get(norm_inst)
            if entry and (time.time() - entry.get("time", 0.0)) < _AUTH_CACHE_TTL:
                return dict(entry["data"])

    if norm_inst == "instance_1":
        cred_tok = vault.get_keychain_token()
        cred_email = vault.extract_token_email(cred_tok) if cred_tok else None
    else:
        cred_email = store.get_instance_active_account(norm_inst)
        if cred_email in ("primary_account", "secondary_account"):
            cred_email = None

    ls_online = False
    live_ide_email = None
    ls_port, csrf = discover_language_server(instance_id=instance_id, use_cache=use_cache)
    if ls_port and csrf:
        try:
            u_resp = call_ls_rpc(ls_port, csrf, "GetUserStatus", timeout=2.0)
            em = ((u_resp or {}).get("userStatus") or {}).get("email")
            ls_online = True
            live_ide_email = str(em).lower().strip() if em and "@" in str(em) else None
        except Exception:
            invalidate_ls_cache(instance_id)
            ls_port = None
            ls_online = False

    session_mismatch = bool(
        ls_online
        and live_ide_email
        and cred_email
        and live_ide_email.lower().strip() != cred_email.lower().strip()
    )

    state = {
        "ls_online": ls_online,
        "ls_port": ls_port if ls_online else None,
        "live_ide_email": live_ide_email,
        "credential_email": cred_email.lower().strip() if cred_email else None,
        "session_mismatch": session_mismatch,
    }
    with _AUTH_LOCK:
        _AUTH_CACHE[norm_inst] = {"data": dict(state), "time": time.time()}
    return state


def _get_bucket_rem(bucket: dict | None) -> float:
    if not isinstance(bucket, dict):
        return 1.0
    rem = bucket.get("remainingFraction")
    if rem is None and isinstance(bucket.get("remaining"), dict):
        rem = bucket["remaining"].get("value")
    try:
        return max(0.0, min(1.0, float(rem))) if rem is not None else 1.0
    except Exception:
        return 1.0


def _classify_model_pool(model_id: str, display_name: str, rem: float, reset_time) -> str | None:
    m_low = str(model_id or "").lower()
    d_low = str(display_name or model_id or "").lower()
    if m_low.startswith(("tab_", "chat_")):
        return None
    if "argon" in m_low or "argon" in d_low:
        return "Gemini 4 Argon"
    if "hydrogen" in m_low or "hydrogen" in d_low or "flash-worker-agy" in m_low:
        return "Gemini 4 Hydrogen"
    if "claude" in m_low or "claude" in d_low:
        return "Claude 4.6 (Opus & Sonnet)"
    if "gpt" in m_low or "gpt" in d_low:
        return "GPT-OSS 120B"
    if "carbon" in m_low or "carbon" in d_low or "orchestrator" in m_low or "orchestrator" in d_low or "pro" in m_low:
        return "Gemini 4 Carbon & Orchestrator"
    if "flash" in m_low or "flash" in d_low:
        if not reset_time and rem >= 1.0 and "preview" in m_low:
            return None
        return "Gemini 3.8 Flash"
    return None


def _build_quota_pools(groups: list, models: dict) -> tuple[dict, dict, list[dict]]:
    """Build normalized (session, weekly, 6-pool list) supporting shared & Argon-specific buckets."""
    gemini_w_bucket = gemini_5h_bucket = None
    p3_w_bucket = p3_5h_bucket = None
    argon_w_bucket = argon_5h_bucket = None

    for g in groups or []:
        if not isinstance(g, dict):
            continue
        g_disp = str(g.get("displayName", "") or "").lower()
        for b in g.get("buckets", []):
            if not isinstance(b, dict):
                continue
            bid = str(b.get("bucketId", "") or "")
            bid_low = bid.lower()
            if bid == "gemini-weekly":
                gemini_w_bucket = b
            elif bid == "gemini-5h":
                gemini_5h_bucket = b
            elif bid == "3p-weekly":
                p3_w_bucket = b
            elif bid == "3p-5h":
                p3_5h_bucket = b
            elif "argon" in bid_low or "argon" in g_disp:
                if "weekly" in bid_low or "wtu" in bid_low:
                    argon_w_bucket = b
                elif "5h" in bid_low:
                    argon_5h_bucket = b

    pools_map: dict[str, dict] = {}
    for m_id, m_info in (models or {}).items():
        if not isinstance(m_info, dict):
            continue
        quota = m_info.get("quotaInfo")
        if not isinstance(quota, dict) or not quota:
            continue
        try:
            rem = max(0.0, min(1.0, float(quota.get("remainingFraction", 1.0))))
        except Exception:
            rem = 1.0
        reset_time = quota.get("resetTime")
        disp = str(m_info.get("displayName", m_id) or m_id)
        cat = _classify_model_pool(m_id, disp, rem, reset_time)
        if not cat:
            continue

        if cat not in pools_map:
            pools_map[cat] = {"rem": rem, "reset_time": reset_time, "display": disp}
        elif rem < pools_map[cat]["rem"]:
            pools_map[cat]["rem"] = rem
            if reset_time:
                pools_map[cat]["reset_time"] = reset_time
        elif rem == pools_map[cat]["rem"] and reset_time and not pools_map[cat]["reset_time"]:
            pools_map[cat]["reset_time"] = reset_time

    gw_rem = _get_bucket_rem(gemini_w_bucket)
    g5_rem = _get_bucket_rem(gemini_5h_bucket)
    p3w_rem = _get_bucket_rem(p3_w_bucket)
    p35_rem = _get_bucket_rem(p3_5h_bucket)

    gw_reset = gemini_w_bucket.get("resetTime") if gemini_w_bucket else None
    g5_reset = gemini_5h_bucket.get("resetTime") if gemini_5h_bucket else None
    p3w_reset = p3_w_bucket.get("resetTime") if p3_w_bucket else None
    p35_reset = p3_5h_bucket.get("resetTime") if p3_5h_bucket else None

    if not gemini_5h_bucket:
        for gc in ("Gemini 4 Hydrogen", "Gemini 4 Argon", "Gemini 4 Carbon & Orchestrator", "Gemini 3.8 Flash"):
            if gc in pools_map:
                if pools_map[gc]["rem"] < g5_rem:
                    g5_rem = pools_map[gc]["rem"]
                if not g5_reset and pools_map[gc]["reset_time"]:
                    g5_reset = pools_map[gc]["reset_time"]

    if not p3_5h_bucket:
        for pc in ("Claude 4.6 (Opus & Sonnet)", "GPT-OSS 120B"):
            if pc in pools_map:
                if pools_map[pc]["rem"] < p35_rem:
                    p35_rem = pools_map[pc]["rem"]
                if not p35_reset and pools_map[pc]["reset_time"]:
                    p35_reset = pools_map[pc]["reset_time"]

    argon_w_rem = _get_bucket_rem(argon_w_bucket) if argon_w_bucket else gw_rem
    argon_w_reset = argon_w_bucket.get("resetTime") if argon_w_bucket else gw_reset
    if argon_5h_bucket:
        argon_5h_rem = _get_bucket_rem(argon_5h_bucket)
        argon_5h_reset = argon_5h_bucket.get("resetTime")
    elif argon_w_bucket:
        argon_5h_rem = argon_w_rem
        argon_5h_reset = argon_w_reset
    else:
        argon_5h_rem = g5_rem
        argon_5h_reset = g5_reset

    gw_cd, gw_lr, gw_sec = format_countdown(gw_reset)
    g5_cd, g5_lr, g5_sec = format_countdown(g5_reset)
    p3w_cd, p3w_lr, p3w_sec = format_countdown(p3w_reset)
    p35_cd, p35_lr, p35_sec = format_countdown(p35_reset)
    argon_w_cd, _, _ = format_countdown(argon_w_reset)
    argon_5h_cd, argon_5h_lr, argon_5h_sec = format_countdown(argon_5h_reset)

    pools = []
    for name in ORDERED_POOLS:
        if "Claude" in name or "GPT" in name:
            base_rem, base_reset, base_cd, base_lr, base_sec = p35_rem, p35_reset, p35_cd, p35_lr, p35_sec
            w_rem, w_cd = p3w_rem, p3w_cd
        elif "Argon" in name:
            base_rem, base_reset, base_cd, base_lr, base_sec = (
                argon_5h_rem, argon_5h_reset, argon_5h_cd, argon_5h_lr, argon_5h_sec
            )
            w_rem, w_cd = argon_w_rem, argon_w_cd
        else:
            base_rem, base_reset, base_cd, base_lr, base_sec = g5_rem, g5_reset, g5_cd, g5_lr, g5_sec
            w_rem, w_cd = gw_rem, gw_cd

        if name in pools_map:
            p_data = pools_map[name]
            if p_data["rem"] < base_rem:
                base_rem = p_data["rem"]
                if p_data["reset_time"]:
                    base_reset = p_data["reset_time"]
                    base_cd, base_lr, base_sec = format_countdown(base_reset)
            elif not base_reset and p_data["reset_time"]:
                base_reset = p_data["reset_time"]
                base_cd, base_lr, base_sec = format_countdown(base_reset)

        pools.append({
            "name": name,
            "used_pct": round((1.0 - base_rem) * 100, 1),
            "remaining_pct": round(base_rem * 100, 1),
            "resets_in": base_cd,
            "reset_time": base_lr,
            "reset_secs": base_sec,
            "reset_iso": str(base_reset) if base_reset else "",
            "weekly_rem": round(w_rem * 100, 1),
            "weekly_pct": round((1.0 - w_rem) * 100, 1),
            "weekly_resets": w_cd,
        })

    primary_session = {
        "name": "5-Hour Limit",
        "used_pct": round((1.0 - g5_rem) * 100, 1),
        "remaining_pct": round(g5_rem * 100, 1),
        "resets_in": g5_cd,
        "reset_time": g5_lr,
        "reset_secs": g5_sec,
        "reset_iso": str(g5_reset) if g5_reset else "",
    }
    weekly_payload = {
        "name": "Weekly Limit",
        "used_pct": round((1.0 - gw_rem) * 100, 1),
        "remaining_pct": round(gw_rem * 100, 1),
        "resets_in": gw_cd,
        "reset_time": gw_lr,
        "reset_secs": gw_sec,
        "reset_iso": str(gw_reset) if gw_reset else "",
    }
    return primary_session, weekly_payload, pools


def _manifest_fallback_quota(email: str, m_entry: dict | None = None) -> dict:
    """Return offline single-account 6-pool payload from manifest metadata (never 0% Argon bug)."""
    if m_entry is None:
        m_entry = store.load_manifest().get(email, {})
    rem = float(m_entry.get("remaining_pct", 100.0))
    w_rem = float(m_entry.get("weekly_remaining_pct", 100.0))
    w_res = str(m_entry.get("weekly_resets_in") or "Ready")
    used = round(100.0 - rem, 1)
    w_used = round(100.0 - w_rem, 1)

    pools = [
        {
            "name": name,
            "used_pct": used,
            "remaining_pct": round(rem, 1),
            "resets_in": "Ready",
            "reset_time": "Ready",
            "reset_secs": 0,
            "reset_iso": "",
            "weekly_rem": round(w_rem, 1),
            "weekly_pct": w_used,
            "weekly_resets": w_res,
        }
        for name in ORDERED_POOLS
    ]

    return {
        "email": email,
        "name": m_entry.get("name") or (email.split("@")[0].split(".")[0].capitalize() if "@" in email else email),
        "avatar": m_entry.get("avatar", ""),
        "tier": m_entry.get("tier", "Google AI Pro"),
        "tier_code": m_entry.get("tier_code", "pro"),
        "stale": True,
        "session": {
            "name": "5-Hour Limit",
            "used_pct": used,
            "remaining_pct": round(rem, 1),
            "resets_in": "Ready",
            "reset_time": "Ready",
            "reset_secs": 0,
            "reset_iso": "",
        },
        "weekly": {
            "name": "Weekly Limit",
            "used_pct": w_used,
            "remaining_pct": round(w_rem, 1),
            "resets_in": w_res,
            "reset_time": "Ready",
            "reset_secs": 0,
            "reset_iso": "",
        },
        "pools": pools,
    }


def _tier_code_from_name(tier_name: str, fallback: str = "pro") -> str:
    low = str(tier_name or "").lower()
    if "ultra" in low:
        return "ultra"
    if "enterprise" in low:
        return "enterprise"
    if "pro" in low:
        return "pro"
    if "free" in low:
        return "free"
    return fallback


def _persist_quota_summary(res_payload: dict) -> None:
    paths = vault.get_platform_paths()
    store.atomic_write_json(paths["active_quota_path"], res_payload)

    email = res_payload.get("email")
    if not email or "@" not in str(email):
        return
    m_data = store.load_manifest()
    if email in m_data and isinstance(m_data[email], dict):
        m_data[email]["remaining_pct"] = res_payload["session"]["remaining_pct"]
        m_data[email]["weekly_remaining_pct"] = res_payload["weekly"]["remaining_pct"]
        m_data[email]["weekly_resets_in"] = res_payload["weekly"]["resets_in"]
        m_data[email]["tier"] = res_payload["tier"]
        m_data[email]["tier_code"] = res_payload["tier_code"]
        store.save_manifest(m_data)


def fetch_quota_from_language_server(instance_id: str | None = None) -> dict | None:
    """Fetch live quota, tier, and mismatch state directly from Antigravity Language Server."""
    ls_port, csrf = discover_language_server(instance_id=instance_id)
    if not ls_port or not csrf:
        return None
    try:
        user_status_data = call_ls_rpc(ls_port, csrf, "GetUserStatus")
        quota_summary_data = call_ls_rpc(ls_port, csrf, "RetrieveUserQuotaSummary")
        models_data = call_ls_rpc(ls_port, csrf, "GetAvailableModels")
        code_assist_data = call_ls_rpc(ls_port, csrf, "GetLoadCodeAssist")
    except Exception:
        invalidate_ls_cache(instance_id)
        return None

    try:
        user_status = (user_status_data or {}).get("userStatus", {})
        email = user_status.get("email")
        user_name = user_status.get("name")
        avatar_url = user_status.get("profilePictureUrl", "")

        tier_obj = user_status.get("userTier", {})
        tier_name = tier_obj.get("name") or "Google AI Pro"
        if not tier_name or tier_name == "Antigravity":
            paid_tier = ((code_assist_data or {}).get("response") or {}).get("paidTier", {}).get("name")
            if paid_tier:
                tier_name = paid_tier

        tier_code = _tier_code_from_name(tier_name)
        clean_name = "User"
        if email and "@" in email:
            clean_name = email.split("@")[0].split(".")[0].capitalize()
        elif user_name:
            clean_name = user_name.split()[0].capitalize()

        groups = ((quota_summary_data or {}).get("response") or {}).get("groups", [])
        models = ((models_data or {}).get("response") or {}).get("models", {})
        primary_session, weekly_payload, pools = _build_quota_pools(groups, models)

        cred_tok = vault.get_keychain_token()
        cred_email = vault.extract_token_email(cred_tok) if cred_tok else None
        live_email = str(email).lower().strip() if email and "@" in str(email) else None
        session_mismatch = bool(live_email and cred_email and live_email != cred_email.lower().strip())

        res_payload = {
            "email": email or "Unknown",
            "name": clean_name,
            "avatar": avatar_url or "",
            "tier": tier_name,
            "tier_code": tier_code,
            "live_ide_email": live_email,
            "credential_email": cred_email,
            "session_mismatch": session_mismatch,
            "session": primary_session,
            "weekly": weekly_payload,
            "pools": pools,
        }
        _persist_quota_summary(res_payload)
        return res_payload
    except Exception:
        return None


def _cloudcode_post(endpoint: str, access_token: str, timeout: float = 4.5) -> dict:
    req = urllib.request.Request(
        f"https://daily-cloudcode-pa.googleapis.com/v1internal:{endpoint}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": "antigravity",
        },
        data=b"{}",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_quota_and_tier(token_str=None, force_refresh: bool = False) -> dict | None:
    """Fetch 6-pool quota via live Language Server (when matching) or CloudCode REST API."""
    now = time.time()
    token_claim = vault.extract_token_email(token_str) if token_str else None
    cache_key = token_claim.lower().strip() if token_claim else "default"

    if not force_refresh:
        with _QUOTA_LOCK:
            entry = _QUOTA_CACHE.get(cache_key)
            if entry and (now - entry.get("time", 0.0)) < _QUOTA_CACHE_TTL:
                return copy.deepcopy(entry["data"])

    ls_quota = fetch_quota_from_language_server()
    if ls_quota and ls_quota.get("email"):
        ls_email = str(ls_quota["email"]).lower().strip()
        if not token_claim or token_claim == ls_email:
            with _QUOTA_LOCK:
                _QUOTA_CACHE[ls_email] = {"data": copy.deepcopy(ls_quota), "time": now}
                _QUOTA_CACHE["default"] = {"data": copy.deepcopy(ls_quota), "time": now}
            return ls_quota

    if not token_str:
        token_str = vault.get_keychain_token()
        if token_str and not token_claim:
            token_claim = vault.extract_token_email(token_str)
            if token_claim:
                cache_key = token_claim
                if not force_refresh:
                    with _QUOTA_LOCK:
                        entry = _QUOTA_CACHE.get(cache_key)
                        if entry and (now - entry.get("time", 0.0)) < _QUOTA_CACHE_TTL:
                            return copy.deepcopy(entry["data"])

    access_token, refresh_token = vault.parse_token_payload(token_str)
    if not access_token and not refresh_token:
        with _QUOTA_LOCK:
            if cache_key in _QUOTA_CACHE:
                return copy.deepcopy(_QUOTA_CACHE[cache_key]["data"])
        return _manifest_fallback_quota(token_claim) if token_claim else None

    models_data = None
    refreshed_str = None
    for attempt in range(3):
        if access_token:
            try:
                data = _cloudcode_post("fetchAvailableModels", access_token, timeout=5.0)
                if isinstance(data, dict) and "models" in data:
                    models_data = data
                    break
            except Exception:
                pass
        if refresh_token and attempt < 2:
            fresh = vault.ensure_fresh_token(token_str, account_email=token_claim, force_refresh=True)
            new_acc, _ = vault.parse_token_payload(fresh)
            if new_acc:
                access_token = new_acc
                refreshed_str = fresh if isinstance(fresh, str) else json.dumps(fresh, ensure_ascii=False)
        time.sleep(0.25)

    if not models_data:
        with _QUOTA_LOCK:
            if cache_key in _QUOTA_CACHE:
                return copy.deepcopy(_QUOTA_CACHE[cache_key]["data"])
        return _manifest_fallback_quota(token_claim) if token_claim else None

    tok_dict = vault.decode_token_dict(refreshed_str or token_str) or {}
    id_claims: dict = {}
    id_tok = tok_dict.get("id_token")
    if isinstance(id_tok, str) and "." in id_tok:
        parts = id_tok.split(".")
        if len(parts) >= 2:
            id_claims = vault._b64_json_decode(parts[1]) or {}

    email = id_claims.get("email") or vault.extract_token_email(tok_dict, check_manifest=False) or token_claim
    user_name = id_claims.get("name")
    avatar_url = id_claims.get("picture")

    try:
        req_u = urllib.request.Request(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        with urllib.request.urlopen(req_u, timeout=3.0) as r:
            u_info = json.loads(r.read().decode("utf-8"))
            email = u_info.get("email") or email
            user_name = u_info.get("name") or user_name
            avatar_url = u_info.get("picture") or avatar_url
    except Exception:
        pass

    manifest = store.load_manifest()
    man_info = manifest.get(email, {}) if email else {}
    if not avatar_url:
        avatar_url = man_info.get("avatar", "")

    tier_name = man_info.get("tier", "Google AI Pro")
    tier_code = man_info.get("tier_code", "pro")
    try:
        tier_data = _cloudcode_post("loadCodeAssist", access_token, timeout=3.0)
        raw_tier = (tier_data.get("paidTier") or {}).get("name") or (tier_data.get("currentTier") or {}).get("name") or ""
        if raw_tier:
            clean_tier = raw_tier.replace("Antigravity", "").strip()
            detected_code = _tier_code_from_name(clean_tier, fallback=tier_code)
            if detected_code != "free" or man_info.get("tier_code") not in ("pro", "ultra", "enterprise"):
                tier_code = detected_code
                tier_name = clean_tier or tier_name
    except Exception:
        pass

    summary_data = None
    try:
        summary_data = _cloudcode_post("retrieveUserQuotaSummary", access_token, timeout=4.0)
    except Exception:
        pass

    groups = (summary_data or {}).get("groups", []) if isinstance(summary_data, dict) else []
    models = (models_data or {}).get("models", {})
    primary_session, weekly_payload, pools = _build_quota_pools(groups, models)

    clean_name = "User"
    if email and "@" in email:
        clean_name = email.split("@")[0].split(".")[0].capitalize()
    elif user_name:
        clean_name = str(user_name).split()[0].capitalize()

    auth_state = get_live_ide_auth_state(use_cache=True)
    res_payload = {
        "email": email or "Unknown",
        "name": clean_name,
        "avatar": avatar_url or "",
        "tier": tier_name,
        "tier_code": tier_code,
        "live_ide_email": auth_state.get("live_ide_email"),
        "credential_email": auth_state.get("credential_email"),
        "session_mismatch": bool(auth_state.get("session_mismatch", False)),
        "session": primary_session,
        "weekly": weekly_payload,
        "pools": pools,
    }

    final_email = str(res_payload["email"]).lower().strip()
    final_key = final_email if "@" in final_email else cache_key
    with _QUOTA_LOCK:
        if final_key in _QUOTA_CACHE:
            old = _QUOTA_CACHE[final_key].get("data", {})
            if res_payload["tier_code"] == "free" and old.get("tier_code") in ("pro", "ultra", "enterprise"):
                res_payload["tier_code"] = old["tier_code"]
                res_payload["tier"] = old["tier"]
            if not res_payload["avatar"] and old.get("avatar"):
                res_payload["avatar"] = old["avatar"]
        _QUOTA_CACHE[final_key] = {"data": copy.deepcopy(res_payload), "time": time.time()}
        if not token_claim and final_key != "default":
            _QUOTA_CACHE["default"] = {"data": copy.deepcopy(res_payload), "time": time.time()}

    return res_payload


def fetch_quota(force_refresh: bool = False) -> dict | None:
    """Compatibility wrapper preserving top-level session/weekly/pools schema."""
    data = fetch_quota_and_tier(force_refresh=force_refresh)
    if not data:
        return None
    session = data.get("session") or {}
    weekly = data.get("weekly")
    if not weekly or (weekly.get("remaining_pct", 100.0) >= 99.9 and data.get("pools")):
        for p in data.get("pools", []):
            w_rem = p.get("weekly_rem")
            if w_rem is not None and float(w_rem) < 99.9:
                weekly = {
                    "name": "Weekly Limit",
                    "remaining_pct": float(w_rem),
                    "used_pct": round(100.0 - float(w_rem), 1),
                    "resets_in": p.get("weekly_resets") or "Ready",
                }
                break
    if not weekly:
        weekly = {
            "name": "Weekly Limit",
            "remaining_pct": session.get("remaining_pct", 100.0),
            "used_pct": session.get("used_pct", 0.0),
            "resets_in": "Ready",
        }
    return {
        "email": data.get("email", "Unknown"),
        "name": data.get("name", "User"),
        "avatar": data.get("avatar", ""),
        "tier": data.get("tier", "Google AI Pro"),
        "tier_code": data.get("tier_code", "pro"),
        "live_ide_email": data.get("live_ide_email"),
        "credential_email": data.get("credential_email"),
        "session_mismatch": bool(data.get("session_mismatch", False)),
        "session": session,
        "weekly": weekly,
        "pools": data.get("pools", []),
    }


def diagnose_suite(instance_id: str = "instance_1") -> dict:
    """Return frozen health & configuration diagnostics for CLI --doctor and MCP diagnose_suite."""
    sys_name = vault.get_current_system()
    auth_state = get_live_ide_auth_state(instance_id=instance_id, use_cache=False)
    dt_path = vault.get_platform_paths(instance_id)["devtools_port_path"]
    dt_exists = dt_path.is_file()

    cdp_port = None
    workbench_ready = False
    if dt_exists:
        try:
            first_line = dt_path.read_text(encoding="utf-8", errors="ignore").splitlines()[0].strip()
            if first_line.isdigit():
                cdp_port = int(first_line)
                workbench_ready = cdp.is_valid_cdp_port(cdp_port, require_workbench=True, timeout=0.35)
        except Exception:
            workbench_ready = False
    if not workbench_ready:
        live_ports = cdp.discover_live_cdp_ports()
        norm_inst = vault._normalize_instance_id(instance_id)
        if norm_inst in live_ports:
            cdp_port = live_ports[norm_inst]
            workbench_ready = True

    daemon_listening = cdp.is_port_open(39281, timeout=0.25)
    daemon_healthy = False
    if daemon_listening:
        try:
            req = urllib.request.Request("http://127.0.0.1:39281/health")
            with _LOOPBACK_HTTP.open(req, timeout=0.6) as resp:
                daemon_healthy = resp.status == 200
        except Exception:
            daemon_healthy = False

    cc_listening = cdp.is_port_open(39285, timeout=0.25)

    search_dirs = store.get_font_search_dirs()
    primary_font_dir = next((d for d in search_dirs if d.is_dir()), search_dirs[0])
    available_fonts = []
    missing_fonts = []
    for fname in store.REQUIRED_FONTS:
        fpath, _ = store.resolve_font_asset(fname)
        if fpath is not None:
            available_fonts.append(fname)
        else:
            missing_fonts.append(fname)
    fonts_ok = len(missing_fonts) == 0

    sanitized_accounts = store.sanitize_manifest_for_client()
    needs_reauth_count = sum(1 for entry in sanitized_accounts.values() if entry.get("needs_reauth"))

    remote_debug_required = bool(auth_state["ls_online"] and not workbench_ready)
    issues: list[str] = []
    if auth_state["session_mismatch"]:
        issues.append(
            f"Session mismatch: IDE is running '{auth_state['live_ide_email']}' while OS credential is '{auth_state['credential_email']}'."
        )
    if remote_debug_required:
        issues.append("Antigravity is running without active workbench CDP debugging (--remote-debugging-port=0 missing).")
    if not daemon_healthy:
        issues.append("Background sync_daemon on 127.0.0.1:39281 is offline or unhealthy.")
    if not fonts_ok:
        issues.append(f"Missing local font assets: {', '.join(missing_fonts)}")
    if needs_reauth_count > 0:
        issues.append(f"{needs_reauth_count} saved account(s) require Google sign-in / token refresh.")

    ok = bool(
        daemon_healthy
        and not auth_state["session_mismatch"]
        and not remote_debug_required
        and fonts_ok
        and needs_reauth_count == 0
    )

    return {
        "ok": ok,
        "version": "3.0.0",
        "system": sys_name,
        "auth_state": auth_state,
        "cdp": {
            "port": cdp_port,
            "workbench_ready": workbench_ready,
            "devtools_port_file": str(dt_path),
            "devtools_port_file_exists": dt_exists,
            "remote_debugging_flag_required": remote_debug_required,
        },
        "sync_daemon": {
            "port": 39281,
            "listening": daemon_listening,
            "healthy": daemon_healthy,
        },
        "control_center": {
            "port": 39285,
            "listening": cc_listening,
        },
        "fonts": {
            "ok": fonts_ok,
            "dir": str(primary_font_dir),
            "available": available_fonts,
            "missing": missing_fonts,
        },
        "accounts": {
            "saved_count": len(sanitized_accounts),
            "needs_reauth_count": needs_reauth_count,
            "active_email": auth_state.get("live_ide_email") or auth_state.get("credential_email"),
        },
        "issues": issues,
    }
