#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Antigravity Account Switcher & Project Migration Suite (macOS & CLI Entry)
Organization: mad-helpers (https://github.com/mad-helpers/antigravity-account-switcher)
"""

import argparse
import html
import json
import os
import platform
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def _bootstrap_sys_path() -> None:
    resolved = Path(__file__).resolve()
    candidates = [resolved.parent]
    if len(resolved.parents) > 3:
        candidates.append(resolved.parents[3])
    candidates.append(Path.home() / ".gemini" / "antigravity" / "bin")
    for p in reversed(candidates):
        s = str(p)
        if p.is_dir() and s not in sys.path:
            sys.path.insert(0, s)


_bootstrap_sys_path()

from ag_suite import quota, store, vault  # noqa: E402

GITHUB_REPO_URL = "https://github.com/mad-helpers/antigravity-account-switcher"
AUTHOR_NAME = "mad-helpers (Madgod-xyz & Bombhub-apk)"
OAUTH_CLIENT_ID = vault.OAUTH_CLIENT_ID
OAUTH_CLIENT_SECRET = vault.OAUTH_CLIENT_SECRET


def _accounts_dir() -> str:
    return str(vault.get_platform_paths()["accounts_dir"])


def _usage_dashboard_path() -> str:
    return str(vault.get_platform_paths()["accounts_dir"] / "usage_dashboard.html")


ACCOUNTS_DIR = _accounts_dir()
MANIFEST_PATH = str(vault.get_platform_paths()["manifest_path"])
USAGE_DASHBOARD_PATH = _usage_dashboard_path()


def _escape_as(text: str) -> str:
    return str(text or "").replace("\\", "\\\\").replace('"', '\\"')


def get_arch_label() -> str:
    m = platform.machine()
    if m == "arm64":
        return "Apple Silicon (M1/M2/M3/M4)"
    if m in ("x86_64", "i386"):
        return "Intel (x86_64)"
    return m


def run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def play_sound(sound_name: str = "Hero") -> None:
    sound_path = f"/System/Library/Sounds/{sound_name}.aiff"
    if os.path.exists(sound_path):
        subprocess.Popen(["afplay", sound_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def osascript(script: str) -> str:
    _, out, _ = run_cmd(["osascript", "-e", script])
    return out


def notify(msg: str, title: str = "Antigravity Switcher", sound: bool = True) -> None:
    if sound:
        play_sound("Hero")
    osascript(f'display notification "{_escape_as(msg)}" with title "{_escape_as(title)}"')


def open_github() -> None:
    run_cmd(["open", GITHUB_REPO_URL])


def show_about() -> None:
    play_sound("Glass")
    as_script = f'''
    tell application "System Events"
        activate
        set res to display dialog "Antigravity Account Switcher v3.0\\n\\nMaintainers: {_escape_as(AUTHOR_NAME)}\\nGitHub: {_escape_as(GITHUB_REPO_URL)}" buttons {{"Close", "Open GitHub"}} default button 2 with icon note
        return button returned of res
    end tell
    '''
    if "Open GitHub" in osascript(as_script):
        open_github()


def fetch_antigravity_usage(token_str: str | None) -> dict | None:
    return quota.fetch_quota_and_tier(token_str)


def get_current_keychain_token() -> str | None:
    return vault.get_keychain_token()


def extract_email_from_token(token_str: str | None) -> str | None:
    email = vault.extract_token_email(token_str)
    if email:
        return email
    access_token, _ = vault.parse_token_payload(token_str)
    if access_token:
        try:
            req = urllib.request.Request(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                info = json.loads(resp.read().decode("utf-8"))
                if info.get("email"):
                    return str(info["email"]).lower().strip()
        except Exception:
            pass
    return None


def load_manifest() -> dict:
    return store.load_manifest()


def save_manifest(manifest: dict) -> bool:
    return store.save_manifest(manifest)


def make_ascii_bar(pct: float, width: int = 20) -> str:
    filled = max(0, min(width, int(round((float(pct or 0.0) / 100.0) * width))))
    return "#" * filled + "-" * (width - filled)


def print_claude_cli_usage(usage: dict | None) -> None:
    if not usage:
        print("\nCould not retrieve Antigravity usage. Please ensure you are signed in.\n")
        return

    email = usage.get("email", "Unknown")
    tier = usage.get("tier", "Antigravity")
    sess = usage.get("session") or {}
    used = float(sess.get("used_pct", 0.0))
    rem = float(sess.get("remaining_pct", 100.0 - used))
    countdown = sess.get("resets_in", "N/A")
    reset_time = sess.get("reset_time", "N/A")

    CYAN = "\033[38;2;56;189;248m"
    INDIGO = "\033[38;2;129;140;248m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RESET = "\033[0m"

    bar = make_ascii_bar(used, width=22)
    bar_color = GREEN if used < 60 else (YELLOW if used < 85 else CYAN)

    print(f"\n{CYAN}{BOLD}=== ANTIGRAVITY USAGE ==={RESET}")
    print(f"Plan: {INDIGO}{tier}{RESET} | Account: {BOLD}{email}{RESET}")
    print(f"Session: {bar_color}[{bar}] {used:.1f}% used{RESET} ({rem:.1f}% rem) | Resets: {countdown} ({reset_time})")
    if usage.get("session_mismatch"):
        print(f"{YELLOW}Warning: Running IDE session ({usage.get('live_ide_email')}) differs from OS credential ({usage.get('credential_email')}).{RESET}")
    for p in usage.get("pools", []):
        p_used = float(p.get("used_pct", 0.0))
        p_bar = make_ascii_bar(p_used, width=16)
        p_col = GREEN if p_used < 60 else (YELLOW if p_used < 85 else CYAN)
        print(f"  - {p.get('name', 'Pool'):<30} {p_col}[{p_bar}] {p_used:>5.1f}%{RESET} {DIM}({p.get('resets_in', 'Ready')}){RESET}")
    print()


def generate_claude_html_dashboard(all_accounts_data: dict, active_key: str) -> str:
    os.makedirs(_accounts_dir(), exist_ok=True)
    dash_path = _usage_dashboard_path()
    safe_json = json.dumps(all_accounts_data, ensure_ascii=False).replace("</", "<\\/")
    safe_active = html.escape(str(active_key or ""), quote=True)
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Antigravity Usage</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    :root {{ --bg:#0B0F19; --card:#131B2E; --border:#232F4D; --text:#F1F5F9; --muted:#94A3B8; --accent:#38BDF8; --bar:#1E293B; --green:#22C55E; --warn:#F59E0B; }}
    body {{ background: var(--bg); color: var(--text); min-height: 100vh; padding: 24px 18px; display: flex; justify-content: center; }}
    .wrap {{ width: 100%; max-width: 440px; display: flex; flex-direction: column; gap: 14px; }}
    .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 16px; }}
    .row {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; }}
    .bar {{ width: 100%; height: 8px; border-radius: 8px; background: var(--bar); overflow: hidden; margin-top: 8px; }}
    .fill {{ height: 100%; background: var(--accent); }}
    select {{ width: 100%; background: var(--card); border: 1px solid var(--border); color: var(--text); padding: 8px 10px; border-radius: 8px; }}
  </style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <div class="row"><strong id="email">Loading...</strong><span id="tier" style="color:var(--accent)">PRO</span></div>
    <div id="reset" style="font-size:12px;color:var(--muted);margin-top:6px;">Resets: --</div>
    <div style="font-size:24px;font-weight:800;margin-top:10px;" id="pct">0%</div>
    <div class="bar"><div class="fill" id="fill"></div></div>
  </div>
  <select id="sel" style="display:none"></select>
  <div id="pools" style="display:flex;flex-direction:column;gap:8px;"></div>
  <div style="font-size:11px;color:var(--muted);text-align:center;">{html.escape(AUTHOR_NAME)}</div>
</div>
<script>
const dataMap = {safe_json};
let activeKey = "{safe_active}";
function render(k) {{
  const d = dataMap[k]; if (!d) return;
  document.getElementById("email").textContent = d.email || k;
  document.getElementById("tier").textContent = d.tier || "Pro";
  const s = d.session || {{}};
  const used = Number(s.used_pct || 0);
  document.getElementById("pct").textContent = used + "% used";
  document.getElementById("fill").style.width = Math.min(100, Math.max(0, used)) + "%";
  document.getElementById("reset").textContent = "Resets: " + (s.resets_in || "Ready");
  const poolsEl = document.getElementById("pools");
  poolsEl.innerHTML = "";
  (d.pools || []).forEach(p => {{
    const card = document.createElement("div"); card.className = "card";
    const u = Number(p.used_pct || 0);
    card.innerHTML = `<div class="row"><span>${{p.name}}</span><span>${{u}}% used</span></div><div class="bar"><div class="fill" style="width:${{u}}%"></div></div>`;
    poolsEl.appendChild(card);
  }});
}}
const keys = Object.keys(dataMap);
if (keys.length > 1) {{
  const sel = document.getElementById("sel"); sel.style.display = "block";
  keys.forEach(k => {{ const o = document.createElement("option"); o.value = k; o.textContent = k; o.selected = k === activeKey; sel.appendChild(o); }});
  sel.onchange = () => render(sel.value);
}}
render(activeKey || keys[0]);
</script>
</body>
</html>
"""
    store.atomic_write_text(dash_path, html_content)
    return dash_path


def open_claude_usage_window(target_key: str | None = None) -> None:
    manifest = load_manifest()
    curr_token = get_current_keychain_token()
    all_data = {}
    active_key = None

    if curr_token:
        active_usage = fetch_antigravity_usage(curr_token)
        if active_usage:
            active_email = active_usage.get("email", "Active Account")
            active_key = active_email
            all_data[active_email] = active_usage

    for k, entry in manifest.items():
        tok = store.read_account_token(k, manifest)
        if not tok:
            continue
        if curr_token and tok == curr_token and active_key:
            all_data[k] = all_data[active_key]
            active_key = k
        else:
            u = fetch_antigravity_usage(tok)
            if u:
                all_data[k] = u

    if not all_data:
        osascript('tell application "System Events" to display alert "Error" message "Could not retrieve Antigravity usage. Please sign in to Antigravity first." as critical')
        return

    chosen_key = target_key if (target_key and target_key in all_data) else (active_key or next(iter(all_data.keys())))
    dashboard_path = generate_claude_html_dashboard(all_data, chosen_key)
    play_sound("Glass")
    chrome_path = "/Applications/Google Chrome.app"
    if os.path.exists(chrome_path):
        subprocess.Popen(["open", "-na", "Google Chrome", "--args", f"--app=file://{dashboard_path}", "--window-size=460,720"])
    else:
        run_cmd(["open", dashboard_path])


def save_current_account(custom_label: str | None = None) -> bool:
    token = get_current_keychain_token()
    if not token:
        osascript('tell application "System Events" to display alert "Error" message "No active Antigravity account found in Keychain. Please sign in first." as critical')
        return False

    email = extract_email_from_token(token)
    if not email:
        email = osascript('tell application "System Events" to text returned of (display dialog "Enter email or name for this account:" default answer "my-account@gmail.com")')
        if not email:
            return False

    key = custom_label if custom_label else email
    acc_dir = Path(_accounts_dir())
    acc_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in ("@", ".", "_", "-") else "_" for c in key)
    token_file = str(acc_dir / f"{safe_name}.token")
    store.atomic_write_text(token_file, token)

    manifest = load_manifest()
    manifest[key] = {
        "label": key,
        "email": email,
        "token_file": token_file,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_manifest(manifest)
    play_sound("Glass")
    notify(f"Account '{key}' saved successfully!", sound=False)
    print(f"Account saved: {key}")
    return True


def _restart_macos_antigravity() -> None:
    osascript('tell application "Antigravity" to quit')
    deadline = time.time() + 5.0
    while time.time() < deadline:
        code, _, _ = run_cmd(["pgrep", "-f", "/Applications/Antigravity.app"])
        if code != 0:
            break
        time.sleep(0.25)
    else:
        run_cmd(["pkill", "-9", "-f", "/Applications/Antigravity.app"])
        time.sleep(0.5)
    run_cmd(["open", "-a", "/Applications/Antigravity.app", "--args", "--remote-debugging-port=0"])


def switch_to_account(account_key: str) -> bool:
    manifest = load_manifest()
    resolved = store.resolve_account_key(account_key, manifest)
    if not resolved or resolved not in manifest:
        osascript(f'tell application "System Events" to display alert "Error" message "Account \'{_escape_as(account_key)}\' not found in saved list." as critical')
        return False

    token = store.read_account_token(resolved, manifest)
    if not token:
        osascript(f'tell application "System Events" to display alert "Error" message "Token file for \'{_escape_as(resolved)}\' is missing." as critical')
        return False

    fresh = vault.ensure_fresh_token(token, account_email=manifest[resolved].get("email") or resolved, force_refresh=True)
    if fresh:
        token = fresh if isinstance(fresh, str) else json.dumps(fresh, ensure_ascii=False)

    if not vault.write_keychain_token(token):
        osascript('tell application "System Events" to display alert "Error" message "Failed to update OS Keychain." as critical')
        return False

    email = manifest[resolved].get("email") or resolved
    store.write_active_instance_account("instance_1", email)
    store.update_app_storage_account(email, instance_id="instance_1")
    quota.invalidate_ls_cache("instance_1")
    _restart_macos_antigravity()

    play_sound("Hero")
    notify(f"Switched to {resolved}!", sound=False)
    print(f"Successfully switched to: {resolved}")
    return True


def logout_and_add_account() -> None:
    curr = get_current_keychain_token()
    if curr:
        ans = osascript('tell application "System Events" to button returned of (display dialog "Would you like to save the current account before logging out?" buttons {"Yes, Save First", "No, Just Logout", "Cancel"} default button 1)')
        if ans == "Cancel" or not ans:
            return
        if ans == "Yes, Save First":
            save_current_account()

    vault.clear_keychain_token()
    _restart_macos_antigravity()
    play_sound("Blow")
    osascript('tell application "System Events" to display dialog "Logged out! Antigravity is reopening with CDP enabled so you can sign in with another Gmail." buttons {"OK"} default button 1 with icon note')


def main_menu() -> None:
    manifest = load_manifest()
    curr_token = get_current_keychain_token()
    active_usage = fetch_antigravity_usage(curr_token) if curr_token else None
    active_email = active_usage.get("email") if active_usage else (extract_email_from_token(curr_token) if curr_token else None)

    active_key = None
    if active_email:
        active_key = store.resolve_account_key(active_email, manifest)

    items = []
    for k in sorted(manifest.keys()):
        items.append(f"[ACTIVE] {k}" if k == active_key else f"Switch to: {k}")

    items.append("-----------------------------")
    curr_display = active_email or active_key or ("Active Session" if curr_token else "Not Signed In")
    items.append("View Usage & Limits")
    items.append(f"Save Current Account ({curr_display})")
    items.append("Add New Gmail (Logout & Sign In)")
    if manifest:
        items.append("Remove a Saved Account")
    items.append("-----------------------------")
    items.append("About & GitHub (mad-helpers)")

    items_as = "{" + ", ".join(f'"{_escape_as(it)}"' for it in items) + "}"
    prompt = f"Antigravity Account Switcher v3.0\\n{get_arch_label()} - {AUTHOR_NAME}\\nActive: {curr_display}"
    choice = osascript(f'''
    tell application "System Events"
        activate
        set chosen to choose from list {items_as} with prompt "{_escape_as(prompt)}" default items {{"{_escape_as(items[0])}"}} OK button name "Select" cancel button name "Cancel"
    end tell
    if chosen is false then return ""
    return item 1 of chosen
    ''')
    if not choice or "-----" in choice:
        return

    if choice.startswith("Switch to: "):
        switch_to_account(choice.replace("Switch to: ", "", 1).strip())
    elif choice.startswith("[ACTIVE] "):
        play_sound("Tink")
        osascript('tell application "System Events" to display dialog "This account is already active!" buttons {"OK"} default button 1 with icon note')
    elif choice == "View Usage & Limits":
        open_claude_usage_window(active_key)
    elif choice.startswith("Save Current Account"):
        save_current_account()
    elif choice.startswith("Add New Gmail"):
        logout_and_add_account()
    elif choice.startswith("About"):
        show_about()
    elif choice.startswith("Remove a Saved Account"):
        del_items = "{" + ", ".join(f'"{_escape_as(k)}"' for k in manifest.keys()) + "}"
        del_choice = osascript(f'''
        tell application "System Events"
            activate
            set delChosen to choose from list {del_items} with prompt "Select an account to remove:" OK button name "Delete" cancel button name "Cancel"
        end tell
        if delChosen is false then return ""
        return item 1 of delChosen
        ''')
        if del_choice and del_choice in manifest:
            tf = manifest[del_choice].get("token_file")
            if tf and os.path.exists(tf):
                try:
                    os.remove(tf)
                except Exception:
                    pass
            del manifest[del_choice]
            save_manifest(manifest)
            play_sound("Submarine")
            notify(f"Removed account {del_choice}", sound=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"Antigravity Account Switcher v3.0 by {AUTHOR_NAME}")
    parser.add_argument("-u", "--usage", action="store_true", help="Display Antigravity usage in terminal")
    parser.add_argument("--gui", action="store_true", help="Open interactive Control Center GUI")
    parser.add_argument("--list", action="store_true", help="List saved accounts")
    parser.add_argument("--switch", type=str, help="Switch to specific account")
    parser.add_argument("--save", nargs="?", const="", help="Save current account with optional name")
    parser.add_argument("--logout", action="store_true", help="Log out from current account")
    parser.add_argument("--migrate", action="store_true", help="List conversations available for migration")
    parser.add_argument("--doctor", action="store_true", help="Run suite diagnostics")
    parser.add_argument("--github", action="store_true", help="Open GitHub project page")
    parser.add_argument("--about", action="store_true", help="Display creator & project info")
    args = parser.parse_args()

    if args.usage:
        curr = get_current_keychain_token()
        if not curr:
            print("\nNo active Antigravity session found in credential vault. Please sign in first.\n")
            sys.exit(1)
        print_claude_cli_usage(fetch_antigravity_usage(curr))
    elif args.doctor:
        print(json.dumps(quota.diagnose_suite(), indent=2, ensure_ascii=False))
    elif args.gui:
        import server
        server.launch_gui()
    elif args.list:
        m = load_manifest()
        curr_em = extract_email_from_token(get_current_keychain_token())
        print(f"\nAntigravity Accounts [{get_arch_label()}] - {GITHUB_REPO_URL}\n")
        for k, v in m.items():
            active = " [ACTIVE]" if curr_em and curr_em == str(v.get("email") or k).lower() else ""
            print(f" * {k} [{v.get('tier', 'Pro')}]{active} (Saved: {v.get('saved_at', 'N/A')})")
        print()
    elif args.switch:
        sys.exit(0 if switch_to_account(args.switch) else 1)
    elif args.save is not None:
        sys.exit(0 if save_current_account(args.save if args.save else None) else 1)
    elif args.logout:
        logout_and_add_account()
    elif args.migrate:
        import migration_engine
        print(json.dumps(migration_engine.list_conversations(), indent=2, ensure_ascii=False))
    elif args.github:
        open_github()
    elif args.about:
        show_about()
    else:
        try:
            import server
            server.launch_gui()
        except Exception:
            main_menu()
