#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Antigravity Account Switcher & Quota Monitor - CLI Tool
Author: Ethan Carter (Bombhub-apk) & Madgod-xyz
Repository: https://github.com/Bombhub-apk/antigravity-account-switcher

Commands:
  --usage, usage             View live model quotas, countdowns, and reset status
  --list, list               List all registered accounts and active status
  --switch <email>           Switch active Antigravity account token
  --set-project-quota <proj> <email>   Set designated quota payer for project
  --launch-instance <inst>   Launch or focus isolated concurrent Antigravity instance
  --status-json, status-json Output comprehensive JSON status
  --save                     Save current active session to manifest
  --logout                   Log out current active session
  --gui                      Open the iOS Liquid Glass GUI
"""

import os
import re
import sys
import json
import time
import argparse
from pathlib import Path

# Add script directory to sys.path to guarantee local module imports
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Enable Windows 10/11 ANSI color support
if sys.platform == 'win32':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        h_out = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(h_out, ctypes.byref(mode)):
            kernel32.SetConsoleMode(h_out, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass

# Import core suite engines
import quota_engine
import migration_engine
import server

# ANSI Terminal Colors
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

ANSI_STRIP_RE = re.compile(r'\x1b\[[0-9;]*[mK]')

def strip_ansi(s):
    """Strip ANSI escape sequences to compute true visible terminal width."""
    return ANSI_STRIP_RE.sub('', s)

def visible_width(s):
    """Returns number of columns consumed by string in terminal."""
    return len(strip_ansi(s))

def box_line(content, inner_width):
    """Wraps content with cyan borders and ensures exact padding."""
    vlen = visible_width(content)
    pad = max(0, inner_width - vlen)
    return f"{CYAN}│{RESET}{content}{' ' * pad}{CYAN}│{RESET}"

def make_bar(pct, width=20):
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

def get_active_account_email():
    """Detect the currently active account email from credential manager / token."""
    try:
        data = quota_engine.fetch_quota_and_tier()
        if data and data.get('email'):
            return data.get('email')
    except Exception:
        pass
    
    # Fallback checking active_instance_1.txt
    try:
        f = Path.home() / ".gemini" / "accounts" / "active_instance_1.txt"
        if f.exists():
            em = f.read_text(encoding='utf-8').strip()
            if em:
                return em
    except Exception:
        pass
    return None

def cmd_usage(args=None):
    """Display real-time model quotas and countdowns in terminal."""
    print(f"\n{BRIGHT_CYAN}⚡ Querying live Antigravity quota and model limits...{RESET}")
    data = quota_engine.fetch_quota_and_tier()
    if not data or data.get('error'):
        print(f"{RED}❌ Could not retrieve Antigravity usage. Please check internet connection or sign in.{RESET}\n")
        return 1

    email = data.get('email', 'Unknown')
    name = data.get('name', 'User')
    tier = data.get('tier', 'Google AI Pro')
    sess = data.get('session') or {}
    weekly = data.get('weekly') or {}
    pools = data.get('pools') or []

    s_used = float(sess.get('used_pct', 0.0))
    s_rem = float(sess.get('remaining_pct', 100.0 - s_used))
    s_resets = sess.get('resets_in', 'Ready')
    s_bar = make_bar(s_used, 20)

    w_used = float(weekly.get('used_pct', 0.0))
    w_rem = float(weekly.get('remaining_pct', 100.0 - w_used))
    w_resets = weekly.get('resets_in', 'Ready')
    w_bar = make_bar(w_used, 20)

    inner_width = 68
    print()
    print(f"{CYAN}┌{'─' * inner_width}┐{RESET}")
    title = "ANTIGRAVITY ACCOUNT SUITE • QUOTA MONITOR"
    t_pad = max(0, (inner_width - len(title)) // 2)
    print(box_line((' ' * t_pad) + f"{BOLD}{BRIGHT_WHITE}{title}{RESET}", inner_width))
    sub = f"  Account: {BOLD}{email}{RESET}  |  Plan: {BRIGHT_GREEN}{tier}{RESET}"
    print(box_line(sub, inner_width))
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
        print(box_line(f"  {BOLD}{WHITE}Individual Model Quota Breakdown:{RESET}", inner_width))
        for p in pools:
            p_name = p.get('name', 'Model')
            p_used = float(p.get('used_pct', 0.0))
            p_rem = float(p.get('remaining_pct', 100.0 - p_used))
            p_res = p.get('resets_in', 'Ready')
            p_bar = make_bar(p_used, 16)
            p_name_padded = p_name[:22].ljust(22)
            m_line = f"  • {BOLD}{p_name_padded}{RESET} {p_bar} {p_used:5.1f}%  {DIM}({p_res}){RESET}"
            print(box_line(m_line, inner_width))
            
    print(f"{CYAN}└{'─' * inner_width}┘{RESET}\n")
    return 0

def cmd_list(args=None):
    """List all registered accounts with tier, remaining %, active status."""
    manifest = server.load_manifest()
    curr_email = get_active_account_email()
    curr_cred = quota_engine.get_windows_credential() if sys.platform == 'win32' else quota_engine.get_keychain_token()

    print(f"\n{BOLD}{BRIGHT_CYAN}🚀 Registered Antigravity Accounts:{RESET}")
    print(f"{DIM}Author: Ethan Carter (Bombhub-apk) & Madgod-xyz{RESET}\n")

    if not manifest:
        print(f"{YELLOW}⚠️  No saved accounts found in ~/.gemini/accounts/manifest.json.{RESET}")
        print(f"Use {BRIGHT_WHITE}agy-switch --save{RESET} to save your current active account.\n")
        return 0

    idx = 1
    for email, entry in manifest.items():
        is_active = False
        tok_file = entry.get('token_file', '')
        if curr_email and (email.lower() == curr_email.lower() or entry.get('email', '').lower() == curr_email.lower()):
            is_active = True
        elif curr_cred and tok_file and os.path.exists(tok_file):
            try:
                with open(tok_file, 'r', encoding='utf-8') as f:
                    tok_content = f.read().strip()
                if tok_content == curr_cred.strip():
                    is_active = True
            except Exception:
                pass

        active_marker = f"{BRIGHT_GREEN}[ACTIVE ●]{RESET}" if is_active else f"{DIM}[INACTIVE]{RESET}"
        tier = entry.get('tier', 'Google AI Pro')
        rem = entry.get('remaining_pct', 100.0)
        weekly_rem = entry.get('weekly_remaining_pct', 100.0)
        saved_at = entry.get('saved_at', 'Unknown')
        inst = entry.get('instance_id')
        inst_label = f" {MAGENTA}({inst}){RESET}" if inst else ""

        print(f"  {BOLD}{idx}.{RESET} {BRIGHT_WHITE}{email}{RESET}{inst_label} {active_marker}")
        print(f"     Tier: {YELLOW}{tier}{RESET} | Session Rem: {BRIGHT_GREEN}{rem:.1f}%{RESET} | Weekly Rem: {CYAN}{weekly_rem:.1f}%{RESET}")
        print(f"     Saved At: {DIM}{saved_at}{RESET}\n")
        idx += 1

    return 0

def find_account_key(target):
    """Fuzzy match account key from email, name, or instance alias."""
    if not target:
        return None
    manifest = server.load_manifest()
    target_clean = target.strip().lower()
    
    # 1. Exact key match
    for k in manifest.keys():
        if k.lower() == target_clean:
            return k
            
    # 2. Email, name, or instance_id match
    for k, v in manifest.items():
        if v.get('email', '').lower() == target_clean:
            return k
        if v.get('name', '').lower() == target_clean:
            return k
        if v.get('instance_id', '').lower() == target_clean:
            return k
            
    # 3. Substring match
    for k in manifest.keys():
        if target_clean in k.lower():
            return k
            
    return None

def cmd_switch(account_arg, no_restart=False):
    """Switch active Antigravity account token."""
    account_key = find_account_key(account_arg)
    if not account_key:
        print(f"{RED}❌ Account '{account_arg}' not found in saved accounts.{RESET}")
        print(f"Run {BRIGHT_WHITE}agy-switch --list{RESET} to see available accounts.")
        return 1

    print(f"\n{BRIGHT_CYAN}🔄 Switching active Antigravity account to: {BOLD}{account_key}{RESET}...")
    res = server.switch_account(account_key, no_restart=no_restart)
    if res.get('success'):
        print(f"{BRIGHT_GREEN}✓ Successfully switched active account to {BOLD}{account_key}{RESET}!")
        if no_restart:
            print(f"{DIM}Note: Restart was skipped (--no-restart). Token updated in Credential Manager.{RESET}")
        else:
            print(f"{DIM}Antigravity process restarted and loaded fresh credentials.{RESET}")
        print()
        return 0
    else:
        err = res.get('error', 'Unknown error')
        print(f"{RED}❌ Failed to switch account: {err}{RESET}\n")
        return 1

def cmd_set_project_quota(project_arg, account_arg):
    """Set designated quota payer account for a project."""
    account_key = find_account_key(account_arg)
    if not account_key:
        account_key = account_arg.strip()

    projects = migration_engine.list_projects()
    matched_pid = None
    matched_name = None
    matched_path = None

    proj_clean = project_arg.strip().lower()
    norm_arg = os.path.normpath(project_arg).lower()

    for p in projects:
        p_id = p.get('id', '')
        p_name = p.get('name', '')
        p_path = p.get('path', '')
        p_norm_path = os.path.normpath(p_path).lower() if p_path else ''

        if p_id.lower() == proj_clean:
            matched_pid = p_id
            matched_name = p_name
            matched_path = p_path
            break
        if p_norm_path and (p_norm_path == norm_arg or norm_arg in p_norm_path):
            matched_pid = p_id
            matched_name = p_name
            matched_path = p_path
            break
        if p_name.lower() == proj_clean:
            matched_pid = p_id
            matched_name = p_name
            matched_path = p_path
            break

    # Substring search if still not found
    if not matched_pid:
        for p in projects:
            p_id = p.get('id', '')
            p_name = p.get('name', '')
            p_path = p.get('path', '')
            if proj_clean in p_name.lower() or (p_path and proj_clean in p_path.lower()):
                matched_pid = p_id
                matched_name = p_name
                matched_path = p_path
                break

    if not matched_pid:
        # Check candidate directory locations
        candidates = [
            project_arg,
            os.path.join(os.getcwd(), project_arg),
            os.path.join(str(SCRIPT_DIR.parent), project_arg),
            os.path.join(str(SCRIPT_DIR), project_arg)
        ]
        for c in candidates:
            if os.path.isdir(c):
                matched_pid = os.path.basename(os.path.normpath(c))
                matched_name = matched_pid
                matched_path = os.path.abspath(c)
                break

    if not matched_pid:
        print(f"{RED}❌ Project '{project_arg}' not found.{RESET}")
        print(f"Available projects:")
        for p in projects:
            print(f"  • {BOLD}{p.get('name')}{RESET} ({p.get('id')}) - Path: {DIM}{p.get('path')}{RESET}")
        return 1

    print(f"\n{BRIGHT_CYAN}⚙️  Assigning quota payer for project '{BOLD}{matched_name}{RESET}' -> {BOLD}{account_key}{RESET}...")
    res = migration_engine.set_project_quota_account(matched_pid, account_key)
    if res.get('success'):
        print(f"{BRIGHT_GREEN}✓ Project '{matched_name}' is now configured to consume quota from {BOLD}{account_key}{RESET}!")
        print(f"{DIM}Project ID: {matched_pid} | Path: {matched_path}{RESET}\n")
        return 0
    else:
        print(f"{RED}❌ Failed to set project quota payer.{RESET}\n")
        return 1

def cmd_launch_instance(instance_or_account):
    """Launch or bring to focus an isolated concurrent Antigravity instance."""
    resolved = find_account_key(instance_or_account) or instance_or_account.strip()
    print(f"\n{BRIGHT_CYAN}🚀 Launching Antigravity instance for '{BOLD}{resolved}{RESET}'...")
    res = server.launch_dual_instance(resolved)
    if res.get('success'):
        msg = res.get('msg', 'Instance launched/focused successfully.')
        print(f"{BRIGHT_GREEN}✓ {msg}{RESET}\n")
        return 0
    else:
        err = res.get('error', 'Failed to launch instance')
        print(f"{RED}❌ {err}{RESET}\n")
        return 1

def cmd_status_json():
    """Output machine-readable JSON status for scripts and agents."""
    try:
        active = quota_engine.fetch_quota_and_tier()
    except Exception:
        active = None

    manifest = server.load_manifest()
    curr_email = get_active_account_email()
    projects = migration_engine.list_projects()
    
    # Check concurrent instances status
    instances_status = {
        f"instance_{i}": server.is_instance_running(f"Antigravity-Instance{i}")
        for i in range(2, 6)
    }

    out = {
        "success": True,
        "active_account": active,
        "current_email": curr_email,
        "saved_accounts": manifest,
        "projects": projects,
        "instances": instances_status,
        "timestamp": time.time()
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0

def cmd_save():
    """Save current active account to manifest."""
    print(f"\n{BRIGHT_CYAN}💾 Saving currently active Antigravity session to manifest...{RESET}")
    res = server.save_current_account()
    if res.get('success'):
        email = res.get('account', 'Account')
        print(f"{BRIGHT_GREEN}✓ Account '{email}' saved successfully to ~/.gemini/accounts/manifest.json!{RESET}\n")
        return 0
    else:
        print(f"{RED}❌ Failed to save account: {res.get('error', 'No active session')}{RESET}\n")
        return 1

def cmd_logout():
    """Log out from current active Antigravity account."""
    print(f"\n{YELLOW}⚠️  Logging out active Antigravity account...{RESET}")
    if sys.platform == 'win32':
        import ctypes
        CredDelete = ctypes.windll.advapi32.CredDeleteW
        CredDelete('gemini:antigravity', 1, 0)
        CredDelete('gemini', 1, 0)
    elif sys.platform == 'darwin':
        import subprocess
        subprocess.run(['security', 'delete-generic-password', '-s', 'gemini', '-a', 'antigravity'], capture_output=True)
    server.restart_antigravity()
    print(f"{BRIGHT_GREEN}✓ Logged out successfully. Sign in with your next Google account!{RESET}\n")
    return 0

def cmd_gui():
    """Launch the standalone iOS Liquid Glass GUI."""
    if sys.platform == 'win32':
        ps_script = SCRIPT_DIR / "switcher_windows.ps1"
        import subprocess
        subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps_script)])
    else:
        server.launch_gui()
    return 0

def print_help():
    print(f"""{BOLD}{BRIGHT_CYAN}Antigravity Account Switcher & Quota Monitor CLI{RESET}
{DIM}Cross-Platform Management Suite • Ethan Carter (Bombhub-apk) & Madgod-xyz{RESET}

{BOLD}USAGE:{RESET}
  agy-switch [COMMAND / OPTIONS]
  agy-quota [OPTIONS]
  python cli.py [COMMAND / OPTIONS]

{BOLD}COMMANDS & OPTIONS:{RESET}
  {BRIGHT_GREEN}--usage, usage{RESET}                       Display real-time model quotas, progress bars, and reset timers
  {BRIGHT_GREEN}--list, list{RESET}                         List all saved accounts with subscription tier & active status
  {BRIGHT_GREEN}--switch <account>{RESET}                   Switch active account in Credential Manager / Keychain
  {BRIGHT_GREEN}--set-project-quota <proj> <account>{RESET} Designate which account pays for prompts in a project
  {BRIGHT_GREEN}--launch-instance <inst>{RESET}             Launch or focus isolated concurrent Antigravity instance
  {BRIGHT_GREEN}--status-json, status-json, --json{RESET}   Output complete JSON payload for agents & automation
  {BRIGHT_GREEN}--save, save{RESET}                         Save current active session to manifest
  {BRIGHT_GREEN}--logout, logout{RESET}                     Log out from active account to sign into a new one
  {BRIGHT_GREEN}--gui, gui{RESET}                           Launch the iOS Liquid Glass GUI
  {BRIGHT_GREEN}--no-restart{RESET}                         Skip restarting the IDE when switching accounts
  {BRIGHT_GREEN}--help, -h{RESET}                           Show this help message

{BOLD}EXAMPLES:{RESET}
  agy-quota
  agy-switch --list
  agy-switch --switch bombhub.apk@gmail.com
  agy-switch --switch instance_2 --no-restart
  agy-switch --set-project-quota "gravity suitch accont" bombhub.apk@gmail.com
  agy-switch --launch-instance instance_2
  agy-switch --status-json
""")

def main():
    raw_args = sys.argv[1:]
    if not raw_args:
        # Default behavior with no arguments: open the Liquid Glass GUI
        return cmd_gui()

    # Extract global flags like --no-restart
    no_restart = '--no-restart' in raw_args
    filtered_args = [a for a in raw_args if a != '--no-restart']

    if not filtered_args:
        print(f"{RED}❌ Please specify a command or account along with --no-restart.{RESET}")
        return 1

    first = filtered_args[0].lower().strip()

    if first in ('-h', '--help', 'help'):
        print_help()
        return 0

    if first in ('-u', '--usage', 'usage', 'quota', '--quota'):
        return cmd_usage()

    if first in ('-l', '--list', 'list', 'accounts', '--accounts'):
        return cmd_list()

    if first in ('-s', '--switch', 'switch'):
        if len(filtered_args) < 2:
            print(f"{RED}❌ Please specify the account email or alias to switch to.{RESET}")
            print("Example: agy-switch --switch bombhub.apk@gmail.com")
            return 1
        return cmd_switch(filtered_args[1], no_restart=no_restart)

    if first in ('--set-project-quota', 'set-project-quota', 'set-quota', '--set-quota'):
        if len(filtered_args) < 3:
            print(f"{RED}❌ Please provide both <project_id_or_path> and <account_email>.{RESET}")
            print("Example: agy-switch --set-project-quota \"gravity suitch accont\" bombhub.apk@gmail.com")
            return 1
        return cmd_set_project_quota(filtered_args[1], filtered_args[2])

    if first in ('--launch-instance', 'launch-instance', 'launch', '--launch'):
        if len(filtered_args) < 2:
            print(f"{RED}❌ Please specify the instance slot or account email.{RESET}")
            print("Example: agy-switch --launch-instance instance_2")
            return 1
        return cmd_launch_instance(filtered_args[1])

    if first in ('--status-json', 'status-json', '--json', 'json'):
        return cmd_status_json()

    if first in ('--save', 'save'):
        return cmd_save()

    if first in ('--logout', 'logout'):
        return cmd_logout()

    if first in ('--gui', 'gui'):
        return cmd_gui()

    if first in ('--ide-theme', 'ide-theme', '--setup-ide', 'setup-ide'):
        import setup_ide_theme
        return 0 if setup_ide_theme.setup_ide_theme() else 1

    # If first argument looks like an email or known account or instance alias, treat as switch
    matched = find_account_key(filtered_args[0])
    if matched:
        return cmd_switch(matched, no_restart=no_restart)

    print(f"{RED}❌ Unknown command or option: '{raw_args[0]}'{RESET}")
    print_help()
    return 1

if __name__ == '__main__':
    sys.exit(main() or 0)
