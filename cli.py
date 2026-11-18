#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Antigravity Account Switcher & Quota Monitor - CLI Tool (v3.0.0)
Organization: mad-helpers (Madgod-xyz & Bombhub-apk)
Repository: https://github.com/mad-helpers/antigravity-account-switcher

Commands:
  --usage, usage                       View live 6-pool model quotas, countdowns, and reset status
  --list, list                         List all registered accounts and active status
  --switch <email>                     Switch active Antigravity account token
  --set-project-quota <proj> <email>   Set designated quota payer for project (switches OS credential unless --no-switch)
  --launch-instance <inst>             Launch or focus isolated concurrent Antigravity instance
  --doctor, doctor                     Run suite diagnostics (LS RPC, CDP, sync_daemon, fonts, accounts)
  --status-json, status-json           Output comprehensive JSON status
  --save                               Save current active session to manifest
  --logout                             Log out current active session
  --gui                                Open the iOS Liquid Glass Control Center GUI (http://127.0.0.1:39285/index.html)
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

if sys.platform == "win32":
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        h_out = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(h_out, ctypes.byref(mode)):
            kernel32.SetConsoleMode(h_out, mode.value | 0x0004)
    except Exception:
        pass

from ag_suite import VERSION, quota, store, vault
import migration_engine
import server

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
BRIGHT_CYAN = "\033[96m"
GREEN = "\033[32m"
BRIGHT_GREEN = "\033[92m"
YELLOW = "\033[33m"
BRIGHT_YELLOW = "\033[93m"
RED = "\033[31m"
MAGENTA = "\033[35m"
WHITE = "\033[37m"
BRIGHT_WHITE = "\033[97m"

ANSI_STRIP_RE = re.compile(r"\x1b\[[0-9;]*[mK]")


def strip_ansi(s: str) -> str:
    """Strip ANSI escape sequences to compute visible terminal width."""
    return ANSI_STRIP_RE.sub("", s)


def visible_width(s: str) -> int:
    """Return number of columns consumed by string in terminal."""
    return len(strip_ansi(s))


def box_line(content: str, inner_width: int) -> str:
    """Wrap content with cyan borders and exact padding."""
    vlen = visible_width(content)
    pad = max(0, inner_width - vlen)
    return f"{CYAN}│{RESET}{content}{' ' * pad}{CYAN}│{RESET}"


def make_bar(pct: float, width: int = 20) -> str:
    """Generate a colored progress bar based on percentage used."""
    pct = max(0.0, min(100.0, float(pct or 0.0)))
    fill = min(width, max(0, int(round((pct / 100.0) * width))))
    empty = width - fill

    if pct < 50.0:
        bar_color = BRIGHT_GREEN
    elif pct < 80.0:
        bar_color = BRIGHT_YELLOW
    else:
        bar_color = RED

    return f"{bar_color}{'█' * fill}{DIM}{'░' * empty}{RESET}"


def get_active_account_email() -> str | None:
    """Detect the currently active account email from live auth state or active_instance_1.txt."""
    try:
        auth = quota.get_live_ide_auth_state()
        if auth.get("credential_email"):
            return auth["credential_email"]
        if auth.get("live_ide_email"):
            return auth["live_ide_email"]
    except Exception:
        pass

    try:
        data = quota.fetch_quota_and_tier()
        if data and data.get("email"):
            return data.get("email")
    except Exception:
        pass

    try:
        f = vault.get_platform_paths()["accounts_dir"] / "active_instance_1.txt"
        if f.is_file():
            em = f.read_text(encoding="utf-8").strip()
            if em:
                return em
    except Exception:
        pass
    return None


def find_account_key(target: str | None) -> str | None:
    """Fuzzy match account key from email, name, or instance alias."""
    return store.resolve_account_key(target)


def cmd_usage(args=None) -> int:
    """Display real-time 6-pool model quotas and countdowns in terminal."""
    print(f"\n{BRIGHT_CYAN}⚡ Querying live Antigravity quota and 6-pool model limits...{RESET}")
    data = quota.fetch_quota_and_tier()
    if not data or data.get("error"):
        print(f"{RED}❌ Could not retrieve Antigravity usage. Please check internet connection or sign in.{RESET}\n")
        return 1

    email = data.get("email", "Unknown")
    tier = data.get("tier", "Google AI Pro")
    sess = data.get("session") or {}
    weekly = data.get("weekly") or {}
    pools = data.get("pools") or []
    mismatch = bool(data.get("session_mismatch"))
    live_ide = data.get("live_ide_email")
    cred_em = data.get("credential_email")

    s_used = float(sess.get("used_pct", 0.0))
    s_rem = float(sess.get("remaining_pct", 100.0 - s_used))
    s_resets = sess.get("resets_in", "Ready")
    s_bar = make_bar(s_used, 20)

    w_used = float(weekly.get("used_pct", 0.0))
    w_rem = float(weekly.get("remaining_pct", 100.0 - w_used))
    w_resets = weekly.get("resets_in", "Ready")
    w_bar = make_bar(w_used, 20)

    inner_width = 72
    print()
    print(f"{CYAN}┌{'─' * inner_width}┐{RESET}")
    title = f"ANTIGRAVITY ACCOUNT SUITE v{VERSION} • QUOTA MONITOR"
    t_pad = max(0, (inner_width - len(title)) // 2)
    print(box_line((" " * t_pad) + f"{BOLD}{BRIGHT_WHITE}{title}{RESET}", inner_width))
    sub = f"  Account: {BOLD}{email}{RESET}  |  Plan: {BRIGHT_GREEN}{tier}{RESET}"
    print(box_line(sub, inner_width))
    if mismatch and live_ide and cred_em:
        mm_line = f"  {YELLOW}⚠ Mismatch: IDE='{live_ide}' vs Vault='{cred_em}'{RESET}"
        print(box_line(mm_line, inner_width))
    print(f"{CYAN}├{'─' * inner_width}┤{RESET}")
    print(box_line(f"  {BOLD}{WHITE}Active Session Quota (5-Hour Window):{RESET}", inner_width))
    s_line = f"  {s_bar} {BOLD}{s_used:5.1f}% used{RESET} ({s_rem:5.1f}% rem)  {DIM}Reset: {s_resets}{RESET}"
    print(box_line(s_line, inner_width))
    print(box_line("", inner_width))
    print(box_line(f"  {BOLD}{WHITE}Weekly Rolling Quota (7-Day Aggregate):{RESET}", inner_width))
    w_line = f"  {w_bar} {BOLD}{w_used:5.1f}% used{RESET} ({w_rem:5.1f}% rem)  {DIM}Reset: {w_resets}{RESET}"
    print(box_line(w_line, inner_width))

    if pools:
        print(f"{CYAN}├{'─' * inner_width}┤{RESET}")
        print(box_line(f"  {BOLD}{WHITE}6-Pool Model Quota Breakdown:{RESET}", inner_width))
        for p in pools:
            p_name = p.get("name", "Model")
            p_used = float(p.get("used_pct", 0.0))
            p_res = p.get("resets_in", "Ready")
            p_bar = make_bar(p_used, 14)
            p_name_padded = p_name[:30].ljust(30)
            m_line = f"  • {BOLD}{p_name_padded}{RESET} {p_bar} {p_used:5.1f}%  {DIM}({p_res}){RESET}"
            print(box_line(m_line, inner_width))

    print(f"{CYAN}└{'─' * inner_width}┘{RESET}\n")
    return 0


def cmd_list(args=None) -> int:
    """List all registered accounts with tier, remaining %, token status, and active status."""
    sanitized = store.sanitize_manifest_for_client()
    auth_state = quota.get_live_ide_auth_state()
    cred_email = (auth_state.get("credential_email") or get_active_account_email() or "").lower()
    live_email = (auth_state.get("live_ide_email") or "").lower()

    print(f"\n{BOLD}{BRIGHT_CYAN}🚀 Registered Antigravity Accounts (v{VERSION}):{RESET}")
    print(f"{DIM}Organization: mad-helpers (Madgod-xyz & Bombhub-apk){RESET}\n")

    if not sanitized:
        print(f"{YELLOW}⚠️  No saved accounts found in ~/.gemini/accounts/manifest.json.{RESET}")
        print(f"Use {BRIGHT_WHITE}agy-switch --save{RESET} to save your current active account.\n")
        return 0

    for idx, (email, entry) in enumerate(sanitized.items(), start=1):
        em_low = str(entry.get("email") or email).lower()
        is_active = bool(cred_email and (em_low == cred_email or email.lower() == cred_email))
        is_ide = bool(live_email and (em_low == live_email or email.lower() == live_email))
        needs_reauth = bool(entry.get("needs_reauth") or entry.get("has_token") is False)

        badges = []
        if is_active:
            badges.append(f"{BRIGHT_GREEN}[ACTIVE ●]{RESET}")
        else:
            badges.append(f"{DIM}[INACTIVE]{RESET}")
        if is_ide and not is_active:
            badges.append(f"{YELLOW}[RUNNING IN IDE]{RESET}")
        if needs_reauth:
            badges.append(f"{RED}[NEEDS RE-AUTH ⚠]{RESET}")

        tier = entry.get("tier", "Google AI Pro")
        rem = float(entry.get("remaining_pct", 100.0))
        weekly_rem = float(entry.get("weekly_remaining_pct", 100.0))
        saved_at = entry.get("saved_at") or "Unknown"
        inst = entry.get("instance_id")
        inst_label = f" {MAGENTA}({inst}){RESET}" if inst else ""

        print(f"  {BOLD}{idx}.{RESET} {BRIGHT_WHITE}{email}{RESET}{inst_label} {' '.join(badges)}")
        print(f"     Tier: {YELLOW}{tier}{RESET} | Session Rem: {BRIGHT_GREEN}{rem:.1f}%{RESET} | Weekly Rem: {CYAN}{weekly_rem:.1f}%{RESET}")
        print(f"     Saved At: {DIM}{saved_at}{RESET}\n")

    return 0


def cmd_switch(account_arg: str, no_restart: bool = True) -> int:
    """Switch active Antigravity account token."""
    account_key = find_account_key(account_arg)
    if not account_key:
        print(f"{RED}❌ Account '{account_arg}' not found in saved accounts.{RESET}")
        print(f"Run {BRIGHT_WHITE}agy-switch --list{RESET} to see available accounts.")
        return 1

    print(f"\n{BRIGHT_CYAN}🔄 Switching active Antigravity account to: {BOLD}{account_key}{RESET}...")
    res = server.switch_account(account_key, no_restart=no_restart)
    if res.get("success"):
        print(f"{BRIGHT_GREEN}✓ Successfully switched active account to {BOLD}{account_key}{RESET}!")
        auth_state = res.get("authState") or quota.get_live_ide_auth_state(use_cache=False)
        if auth_state.get("session_mismatch") and no_restart:
            live_em = auth_state.get("live_ide_email")
            print(
                f"{YELLOW}⚠️  Note: Running IDE session is still on '{live_em}'. "
                f"Use --restart or --launch-instance {account_key} to apply inside the editor window.{RESET}"
            )
        restart = res.get("restart") or {}
        if no_restart:
            print(f"{DIM}Restart skipped (default; use --restart to request a graceful relaunch).{RESET}")
        elif restart.get("launched") is True or restart.get("completed") is True:
            print(f"{DIM}Antigravity relaunch requested with --remote-debugging-port=0.{RESET}")
        else:
            print(f"{YELLOW}Account switched; safe restart was not completed. Check the application and restart log.{RESET}\n")
            return 2
        print()
        return 0

    err = res.get("error", "Unknown error")
    print(f"{RED}❌ Failed to switch account: {err}{RESET}\n")
    return 1


def cmd_set_project_quota(project_arg: str, account_arg: str, apply_now: bool = True) -> int:
    """Set designated quota payer account for a project and switch OS credentials unless --no-switch."""
    account_key = find_account_key(account_arg) or account_arg.strip()
    matched = migration_engine.resolve_project(project_arg)
    if not matched:
        projects = migration_engine.list_projects()
        print(f"{RED}❌ Project '{project_arg}' not found.{RESET}")
        print("Available projects:")
        for p in projects:
            print(f"  • {BOLD}{p.get('name')}{RESET} ({p.get('id')}) - Path: {DIM}{p.get('path')}{RESET}")
        return 1

    matched_pid = matched["id"]
    matched_name = matched["name"]
    matched_path = matched["path"]

    print(f"\n{BRIGHT_CYAN}⚙️  Assigning quota payer for project '{BOLD}{matched_name}{RESET}' -> {BOLD}{account_key}{RESET}...")
    res = migration_engine.set_project_quota_account(matched_pid, account_key)
    if not res.get("success"):
        print(f"{RED}❌ Failed to set project quota payer.{RESET}\n")
        return 1

    print(f"{BRIGHT_GREEN}✓ Project '{matched_name}' is now configured to consume quota from {BOLD}{account_key}{RESET}!")
    print(f"{DIM}Project ID: {matched_pid} | Path: {matched_path}{RESET}")

    manifest = store.load_manifest()
    resolved_manifest_key = store.resolve_account_key(account_key, manifest)
    if apply_now and resolved_manifest_key:
        sw_res = server.switch_account(resolved_manifest_key, no_restart=True)
        if sw_res.get("success"):
            print(f"{BRIGHT_GREEN}✓ OS Credential Vault switched to {BOLD}{resolved_manifest_key}{RESET} (in-place, no restart).{RESET}")

    auth_state = quota.get_live_ide_auth_state(use_cache=False)
    live_em = auth_state.get("live_ide_email")
    mismatch = bool(auth_state.get("session_mismatch"))
    if live_em:
        print(f"{DIM}Live IDE Account: {live_em} | Session Mismatch: {mismatch}{RESET}")
    if mismatch:
        print(
            f"{YELLOW}⚠️  Running IDE window is still signed into {live_em}. "
            f"Use --restart or --launch-instance {account_key} to apply in-window.{RESET}"
        )
    print()
    return 0


def cmd_launch_instance(instance_or_account: str) -> int:
    """Launch or bring to focus an isolated concurrent Antigravity instance."""
    resolved = find_account_key(instance_or_account) or instance_or_account.strip()
    print(f"\n{BRIGHT_CYAN}🚀 Launching Antigravity instance for '{BOLD}{resolved}{RESET}'...")
    res = server.launch_dual_instance(resolved)
    if res.get("success"):
        msg = res.get("msg", "Instance launched/focused successfully.")
        print(f"{BRIGHT_GREEN}✓ {msg}{RESET}\n")
        return 0
    err = res.get("error", "Failed to launch instance")
    print(f"{RED}❌ {err}{RESET}\n")
    return 1


def cmd_status_json() -> int:
    """Output machine-readable JSON status for scripts and agents."""
    try:
        active = quota.fetch_quota_and_tier()
    except Exception:
        active = None

    sanitized_manifest = store.sanitize_manifest_for_client()
    auth_state = quota.get_live_ide_auth_state()
    curr_email = (
        auth_state.get("credential_email")
        or auth_state.get("live_ide_email")
        or (active.get("email") if isinstance(active, dict) else None)
        or get_active_account_email()
    )
    projects = migration_engine.list_projects()

    instances_status = {}
    for i in range(2, 6):
        try:
            instances_status[f"instance_{i}"] = bool(server.is_instance_running(f"Antigravity-Instance{i}"))
        except Exception:
            instances_status[f"instance_{i}"] = False

    out = {
        "success": True,
        "version": VERSION,
        "active_account": active,
        "current_email": curr_email,
        "auth_state": auth_state,
        "saved_accounts": sanitized_manifest,
        "projects": projects,
        "instances": instances_status,
        "timestamp": time.time(),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_doctor(as_json: bool = False) -> int:
    """Run suite diagnostics consuming frozen ag_suite.quota.diagnose_suite() schema."""
    diag = quota.diagnose_suite()
    if as_json:
        print(json.dumps(diag, indent=2, ensure_ascii=False))
        return 0

    auth = diag.get("auth_state") or {}
    cdp_info = diag.get("cdp") or {}
    daemon = diag.get("sync_daemon") or {}
    cc = diag.get("control_center") or {}
    fonts = diag.get("fonts") or {}
    accounts = diag.get("accounts") or {}
    issues = diag.get("issues") or []

    print(f"\n{BOLD}{BRIGHT_CYAN}🩺 Antigravity Account Suite v{diag.get('version', VERSION)} • Doctor Diagnostics ({diag.get('system', 'unknown')}){RESET}\n")

    ls_badge = (
        f"{BRIGHT_GREEN}ONLINE (port {auth.get('ls_port')}){RESET}"
        if auth.get("ls_online")
        else f"{YELLOW}OFFLINE{RESET}"
    )
    print(f"  • {BOLD}Language Server RPC:{RESET}   {ls_badge} | IDE Email: {BOLD}{auth.get('live_ide_email') or 'N/A'}{RESET}")

    cred_em = auth.get("credential_email") or "N/A"
    mm_badge = f"{YELLOW}MISMATCH ⚠️{RESET}" if auth.get("session_mismatch") else f"{BRIGHT_GREEN}IN SYNC ✓{RESET}"
    print(f"  • {BOLD}OS Credential Vault:{RESET}   {BOLD}{cred_em}{RESET} ({mm_badge})")

    cdp_badge = (
        f"{BRIGHT_GREEN}READY (port {cdp_info.get('port')}){RESET}"
        if cdp_info.get("workbench_ready")
        else f"{YELLOW}INACTIVE (launch with --remote-debugging-port=0){RESET}"
    )
    print(f"  • {BOLD}CDP Workbench Port:{RESET}    {cdp_badge}")

    dm_badge = (
        f"{BRIGHT_GREEN}HEALTHY (127.0.0.1:{daemon.get('port', 39281)}){RESET}"
        if daemon.get("healthy")
        else f"{RED}OFFLINE{RESET}"
    )
    print(f"  • {BOLD}Sync Daemon (39281):{RESET}   {dm_badge}")

    cc_badge = (
        f"{BRIGHT_GREEN}LISTENING (127.0.0.1:{cc.get('port', 39285)}){RESET}"
        if cc.get("listening")
        else f"{DIM}ON-DEMAND (127.0.0.1:{cc.get('port', 39285)}){RESET}"
    )
    print(f"  • {BOLD}Control Center:{RESET}        {cc_badge}")

    f_badge = (
        f"{BRIGHT_GREEN}OK ({len(fonts.get('available') or [])} bundled){RESET}"
        if fonts.get("ok")
        else f"{YELLOW}MISSING ({', '.join(fonts.get('missing') or [])}){RESET}"
    )
    print(f"  • {BOLD}Local Font Assets:{RESET}     {f_badge}")

    print(
        f"  • {BOLD}Saved Accounts:{RESET}        {BOLD}{accounts.get('saved_count', 0)}{RESET} total | "
        f"Needs Re-Auth: {BOLD}{accounts.get('needs_reauth_count', 0)}{RESET} | "
        f"Active: {BOLD}{accounts.get('active_email') or 'N/A'}{RESET}"
    )

    if issues:
        print(f"\n  {BOLD}{YELLOW}Detected Issues:{RESET}")
        for issue in issues:
            print(f"    • {issue}")
    else:
        print(f"\n  {BRIGHT_GREEN}✓ All suite components are healthy!{RESET}")
    print()
    return 0


def cmd_save() -> int:
    """Save current active account to manifest."""
    print(f"\n{BRIGHT_CYAN}💾 Saving currently active Antigravity session to manifest...{RESET}")
    res = server.save_current_account()
    if res.get("success"):
        email = res.get("account", "Account")
        print(f"{BRIGHT_GREEN}✓ Account '{email}' saved successfully to ~/.gemini/accounts/manifest.json!{RESET}\n")
        return 0
    print(f"{RED}❌ Failed to save account: {res.get('error', 'No active session')}{RESET}\n")
    return 1


def cmd_logout(no_restart: bool = False) -> int:
    """Log out from current active Antigravity account."""
    print(f"\n{YELLOW}⚠️  Logging out active Antigravity account...{RESET}")
    vault.clear_keychain_token()
    if not no_restart:
        server.restart_antigravity()
    print(f"{BRIGHT_GREEN}✓ Logged out successfully. Sign in with your next Google account!{RESET}\n")
    return 0


def cmd_gui() -> int:
    """Launch or reuse the Control Center HTTP server on http://127.0.0.1:39285/index.html."""
    port = getattr(server, "PORT", 39285)
    url = f"http://127.0.0.1:{port}/index.html"
    health_url = f"http://127.0.0.1:{port}/api/state"

    if sys.platform != "win32" and hasattr(server, "launch_gui"):
        server.launch_gui()
        return 0

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    ready = False
    try:
        with opener.open(health_url, timeout=0.8) as r:
            ready = r.status == 200
    except Exception:
        ready = False

    if not ready:
        py_dir = Path(sys.executable).resolve().parent
        pyw = py_dir / "pythonw.exe"
        py_exe = str(pyw if pyw.is_file() else Path(sys.executable))
        flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)) if sys.platform == "win32" else 0
        subprocess.Popen(
            [py_exe, str(SCRIPT_DIR / "server.py"), "--server-only"],
            cwd=str(SCRIPT_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )
        for _ in range(15):
            time.sleep(0.2)
            try:
                with opener.open(health_url, timeout=0.6) as r:
                    if r.status == 200:
                        break
            except Exception:
                pass

    edge_paths = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ]
    chrome_paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
    ]
    browser = next((p for p in (edge_paths + chrome_paths) if p and os.path.isfile(p)), None)
    if browser:
        subprocess.Popen([browser, f"--app={url}", "--window-size=620,860", "--disable-features=Translate"])
    else:
        import webbrowser

        webbrowser.open(url)
    return 0


def print_help() -> None:
    print(
        f"""{BOLD}{BRIGHT_CYAN}Antigravity Account Switcher & Quota Monitor CLI v{VERSION}{RESET}
{DIM}Cross-Platform Management Suite • mad-helpers (Madgod-xyz & Bombhub-apk){RESET}

{BOLD}USAGE:{RESET}
  agy-switch [COMMAND / OPTIONS]
  agy-quota [OPTIONS]
  python cli.py [COMMAND / OPTIONS]

{BOLD}COMMANDS & OPTIONS:{RESET}
  {BRIGHT_GREEN}--usage, usage{RESET}                       Display real-time 6-pool quotas, progress bars, and reset timers
  {BRIGHT_GREEN}--list, list{RESET}                         List all saved accounts with subscription tier & active status
  {BRIGHT_GREEN}--switch <account>{RESET}                   Switch active account in Credential Manager / Keychain
  {BRIGHT_GREEN}--set-project-quota <proj> <account>{RESET} Designate which account pays for prompts in a project
  {BRIGHT_GREEN}--no-switch{RESET}                          Do not switch OS credential immediately during --set-project-quota
  {BRIGHT_GREEN}--launch-instance <inst>{RESET}             Launch or focus isolated concurrent Antigravity instance
  {BRIGHT_GREEN}--doctor, doctor{RESET}                     Diagnose LanguageServer RPC, CDP, sync_daemon, fonts, and tokens
  {BRIGHT_GREEN}--status-json, status-json, --json{RESET}   Output complete JSON payload for agents & automation
  {BRIGHT_GREEN}--save, save{RESET}                         Save current active session to manifest
  {BRIGHT_GREEN}--logout, logout{RESET}                     Log out from active account to sign into a new one
  {BRIGHT_GREEN}--gui, gui{RESET}                           Launch the Liquid Glass Control Center (127.0.0.1:39285)
  {BRIGHT_GREEN}--restart{RESET}                            Request a graceful IDE restart after switching
  {BRIGHT_GREEN}--no-restart{RESET}                         Skip restarting the IDE (default; retained for compatibility)
  {BRIGHT_GREEN}--help, -h{RESET}                           Show this help message

{BOLD}EXAMPLES:{RESET}
  agy-quota
  agy-switch --list
  agy-switch --doctor
  agy-switch --doctor --json
  agy-switch --switch developer@example.com
  agy-switch --switch instance_2 --no-restart
  agy-switch --set-project-quota "my-project" developer@example.com
  agy-switch --launch-instance instance_2
  agy-switch --status-json
"""
    )


def main() -> int:
    raw_args = sys.argv[1:]
    if not raw_args:
        return cmd_gui()

    if "--restart" in raw_args and "--no-restart" in raw_args:
        print(f"{RED}Choose either --restart or --no-restart, not both.{RESET}")
        return 1

    no_restart = "--restart" not in raw_args
    apply_now = "--no-switch" not in raw_args
    as_json = any(a.lower() in ("--json", "--status-json") for a in raw_args)
    filtered_args = [a for a in raw_args if a not in ("--restart", "--no-restart", "--no-switch")]

    if not filtered_args:
        print(f"{RED}❌ Please specify a command or account along with the option flags.{RESET}")
        return 1

    first = filtered_args[0].lower().strip()

    if first in ("-h", "--help", "help"):
        print_help()
        return 0

    if first in ("-u", "--usage", "usage", "quota", "--quota"):
        return cmd_usage()

    if first in ("-l", "--list", "list", "accounts", "--accounts"):
        return cmd_list()

    if first in ("--doctor", "doctor", "--diagnose", "diagnose"):
        return cmd_doctor(as_json=as_json)

    if first in ("-s", "--switch", "switch"):
        if len(filtered_args) < 2:
            print(f"{RED}❌ Please specify the account email or alias to switch to.{RESET}")
            print("Example: agy-switch --switch developer@example.com")
            return 1
        return cmd_switch(filtered_args[1], no_restart=no_restart)

    if first in ("--set-project-quota", "set-project-quota", "set-quota", "--set-quota"):
        if len(filtered_args) < 3:
            print(f"{RED}❌ Please provide both <project_id_or_path> and <account_email>.{RESET}")
            print('Example: agy-switch --set-project-quota "my-project" developer@example.com')
            return 1
        return cmd_set_project_quota(filtered_args[1], filtered_args[2], apply_now=apply_now)

    if first in ("--launch-instance", "launch-instance", "launch", "--launch"):
        if len(filtered_args) < 2:
            print(f"{RED}❌ Please specify the instance slot or account email.{RESET}")
            print("Example: agy-switch --launch-instance instance_2")
            return 1
        return cmd_launch_instance(filtered_args[1])

    if first in ("--status-json", "status-json", "--json", "json"):
        return cmd_status_json()

    if first in ("--save", "save"):
        return cmd_save()

    if first in ("--logout", "logout"):
        return cmd_logout(no_restart=no_restart)

    if first in ("--gui", "gui"):
        return cmd_gui()

    matched = find_account_key(filtered_args[0])
    if matched:
        return cmd_switch(matched, no_restart=no_restart)

    print(f"{RED}❌ Unknown command or option: '{raw_args[0]}'{RESET}")
    print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
