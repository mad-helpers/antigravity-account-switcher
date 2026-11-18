---
name: antigravity-account-suite
description: Manage Antigravity accounts, view live 6-pool model quotas, diagnose suite health, and assign per-project quota sources from CLI or MCP
---

# Antigravity Account Suite, 6-Pool Quota & Smart RTL Skill (v3.0.0)

Use this skill when you need to inspect live AI model quotas across all 6 model pools, switch Google accounts in Google Antigravity, assign per-project quota payers, diagnose IDE/CDP telemetry, or open the native Sidecar Aux Pane.

Developed by **[mad-helpers](https://github.com/mad-helpers)** (**[Madgod-xyz](https://github.com/Madgod-xyz)** & **[Bombhub-apk](https://github.com/Bombhub-apk)**) • [Repository](https://github.com/mad-helpers/antigravity-account-switcher).

---

## 1. Quick CLI Reference

The suite provides global CLI binaries in `%USERPROFILE%\.gemini\bin` (Windows) and `~/.local/bin` / `/opt/homebrew/bin` / `/usr/local/bin` (macOS & Linux):

| Command | Action |
| :--- | :--- |
| `agy-quota` | Display real-time 5-hour session quota, weekly rolling limits, and 6-pool breakdown table with progress bars |
| `agy-quota --status-json` | Output machine-readable JSON status of active account, 6 model pools, `auth_state`, saved accounts, and instances |
| `agy-switch --doctor` | Run comprehensive health diagnostics (`LanguageServer` RPC, `session_mismatch`, `--remote-debugging-port=0` CDP HUD, `sync_daemon`, fonts, and saved tokens) |
| `agy-switch --list` | List all saved accounts, subscription tiers (`Pro`, `Ultra`, `Free`), remaining %, token health, and active status |
| `agy-switch --switch <email>` | Switch active account in OS Credential Manager / Keychain (in-place `--no-restart` by default; pass `--restart` to relaunch IDE) |
| `agy-switch --set-project-quota <proj> <email>` | Designate which Google account pays for requests in a project and switch OS credentials immediately (`--no-switch` to skip credential switch) |
| `agy-switch --launch-instance <slot_or_email>` | Launch or focus an isolated concurrent Antigravity window (`instance_2`, `instance_3`, etc.) with `--remote-debugging-port=0` |
| `agy-switch --status-json` | Full structured JSON status payload for autonomous agents |
| `agy-switch --gui` | Launch the iOS Liquid Glass Control Center on `http://127.0.0.1:39285/index.html` |

---

## 2. Real-Time 6-Pool Quota Inspection

### Terminal Formatted Table
```bash
agy-quota
# or
agy-switch --usage
```
Returns:
- **Account Email, Subscription Plan & Session Mismatch Alert:** (`Google AI Pro`, `Ultra`, `Free`, plus live check comparing running IDE account vs OS Credential Vault)
- **Active Session Limit (5-Hour Window):** Used percentage, remaining percentage, and countdown timer until reset.
- **Weekly Rolling Limit (7-Day Aggregate):** Used percentage, remaining percentage, and reset countdown.
- **6-Pool Model Quota Breakdown:**
  - `Gemini 4 Hydrogen`
  - `Gemini 4 Argon`
  - `Gemini 4 Carbon & Orchestrator`
  - `Gemini 3.8 Flash`
  - `Claude 4.6 (Opus & Sonnet)`
  - `GPT-OSS 120B`

### Structured JSON for Agents
```bash
agy-quota --status-json
```
Example JSON structure:
```json
{
  "success": true,
  "version": "3.0.0",
  "active_account": {
    "email": "developer@example.com",
    "tier": "Google AI Pro",
    "live_ide_email": "developer@example.com",
    "credential_email": "developer@example.com",
    "session_mismatch": false,
    "session": {
      "used_pct": 10.8,
      "remaining_pct": 89.2,
      "resets_in": "4 hr 15 min"
    },
    "weekly": {
      "used_pct": 17.5,
      "remaining_pct": 82.5,
      "resets_in": "4 d 18 hr"
    },
    "pools": [
      { "name": "Gemini 4 Hydrogen", "used_pct": 10.8, "remaining_pct": 89.2, "resets_in": "4 hr 15 min" },
      { "name": "Gemini 4 Argon", "used_pct": 10.8, "remaining_pct": 89.2, "resets_in": "4 hr 15 min" },
      { "name": "Gemini 4 Carbon & Orchestrator", "used_pct": 10.8, "remaining_pct": 89.2, "resets_in": "4 hr 15 min" },
      { "name": "Gemini 3.8 Flash", "used_pct": 10.8, "remaining_pct": 89.2, "resets_in": "4 hr 15 min" },
      { "name": "Claude 4.6 (Opus & Sonnet)", "used_pct": 5.0, "remaining_pct": 95.0, "resets_in": "4 hr 40 min" },
      { "name": "GPT-OSS 120B", "used_pct": 5.0, "remaining_pct": 95.0, "resets_in": "4 hr 40 min" }
    ]
  },
  "current_email": "developer@example.com",
  "auth_state": {
    "ls_online": true,
    "ls_port": 51234,
    "live_ide_email": "developer@example.com",
    "credential_email": "developer@example.com",
    "session_mismatch": false
  },
  "saved_accounts": { ... },
  "projects": [ ... ],
  "instances": { "instance_2": false, "instance_3": false }
}
```

---

## 3. Suite Diagnostics (`--doctor` & `diagnose_suite`)

To verify why in-editor HUD, Smart RTL, or account switching is out of sync:
```bash
agy-switch --doctor
# or JSON output:
agy-switch --doctor --json
```
Checks:
- **Language Server Connect-RPC:** Live port discovery & `live_ide_email`.
- **OS Credential Vault:** Compares `credential_email` vs `live_ide_email` (`session_mismatch`).
- **CDP Workbench Port:** Verifies `DevToolsActivePort` and `--remote-debugging-port=0` workbench readiness (required on Antigravity 2.33+).
- **Background Sync Daemon (`127.0.0.1:39281`) & Control Center (`127.0.0.1:39285`):** Health and listener status.
- **Bundled Local Fonts & Saved Account Tokens:** Verifies `Vazirmatn[wght].woff2`, `Estedad[wght].woff2`, `Outfit[wght].woff2`, and flags accounts with `needs_reauth`.

---

## 4. Account Switching & Per-Project Quota Allocation

### Switching Active Account
```bash
agy-switch --switch user2@example.com
# With graceful IDE restart (--remote-debugging-port=0):
agy-switch --switch user2@example.com --restart
```

### Per-Project Quota Payer
Bind any project ID, name, or directory path to a designated quota account (automatically switches the OS credential unless `--no-switch` is passed):
```bash
agy-switch --set-project-quota "/path/to/my-project" user2@example.com
```

---

## 5. Model Context Protocol (MCP) Server & Sidecar Aux Pane

The suite ships a native Antigravity 2.33+ plugin (`~/.gemini/config/plugins/antigravity-account-suite/`) with a zero-dependency stdio MCP server (`~/.gemini/antigravity/bin/mcp_server.py`) and an interactive Sidecar Aux Pane:
- **Aux Pane Link:** `[Account & Quota Hub](sidecar://antigravity-account-suite/account-suite/)`

### 5 Registered MCP Tools:
1. `get_quota_status(account?: string, include_all?: boolean)`:
   Returns 5-hour & weekly quota, all 6 model pools, `auth_state`, and sanitized `saved_accounts`.
2. `switch_account(account: string, no_restart?: boolean)`:
   Switches the OS Credential Manager / Keychain token (`no_restart=true` default).
3. `set_project_quota(project: string, account: string, apply_now?: boolean)`:
   Configures project-level quota payer and switches OS credentials (`apply_now=true` default).
4. `list_saved_accounts()`:
   Returns sanitized array of all saved accounts (`has_token`, `needs_reauth`, tiers, remaining %, `auth_state`).
5. `diagnose_suite()`:
   Returns frozen v3.0 health diagnostics (`ok`, `version`, `system`, `auth_state`, `cdp`, `sync_daemon`, `control_center`, `fonts`, `accounts`, `issues`).
