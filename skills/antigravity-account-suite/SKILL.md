---
name: antigravity-account-suite
description: Manage Antigravity accounts, view live model quotas, and assign per-project quota sources from CLI
---

# Antigravity Account Suite & Quota Monitor Skill

Use this skill when you need to inspect live AI model quotas, switch Google accounts in Google Antigravity, assign per-project quota sources, or orchestrate concurrent Antigravity instances.

Developed by **[Ethan Carter (Bombhub-apk)](https://github.com/Bombhub-apk)** & **[Madgod-xyz](https://github.com/Madgod-xyz)**.

---

## 1. Quick CLI Reference

The suite provides global CLI binaries in `%USERPROFILE%\.gemini\bin`:

| Command | Action |
| :--- | :--- |
| `agy-quota` | Display real-time 5-hour session quota, weekly rolling limits, and per-model breakdown table with progress bars |
| `agy-quota --status-json` | Output machine-readable JSON status of active account, model pools, saved accounts, and instances |
| `agy-switch --list` | List all saved accounts, subscription tiers (`Pro`, `Ultra`, `Free`), remaining %, and active status |
| `agy-switch --switch <email>` | Instantly switch active account in OS Credential Manager / Keychain |
| `agy-switch --switch <email> --no-restart` | Switch OS credential immediately without restarting the Antigravity editor process |
| `agy-switch --set-project-quota <proj> <email>` | Designate which Google account pays for language server requests in a specific project |
| `agy-switch --launch-instance <slot_or_email>` | Launch or focus an isolated concurrent Antigravity window (`instance_2`, `instance_3`, etc.) |
| `agy-switch --status-json` | Full structured JSON status payload for autonomous agents |
| `agy-switch` | Launch the iOS Liquid Glass Desktop GUI |

---

## 2. Real-Time Quota Inspection

### Terminal Formatted Table
```bash
agy-quota
# or
agy-switch --usage
```
Returns:
- **Account Email & Subscription Plan:** (e.g. `Google AI Pro`, `Ultra`, `Free`)
- **Active Session Limit (5-Hour Window):** Used percentage, remaining percentage, and countdown timer until reset.
- **Weekly Rolling Limit (7-Day Aggregate):** Used percentage, remaining percentage, and reset date/time.
- **Model Pool Breakdown:**
  - `Gemini 3.8 Flash High`
  - `Gemini 3.1 Pro`
  - `Claude Sonnet 4.6`
  - `GPT-OSS 120B`

### Structured JSON for Agents
```bash
agy-quota --status-json
```
Example JSON structure:
```json
{
  "success": true,
  "active_account": {
    "email": "developer@example.com",
    "tier": "Google AI Pro",
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
      {
        "name": "Gemini 3.8 Flash High",
        "used_pct": 10.8,
        "remaining_pct": 89.2,
        "resets_in": "4 hr 15 min"
      }
    ]
  },
  "current_email": "developer@example.com",
  "saved_accounts": { ... },
  "projects": [ ... ],
  "instances": { "instance_2": false, "instance_3": false }
}
```

---

## 3. Account Switching & Token Management

### Switching Active Account
When an account exhausts its prompt quota or when working on an account-specific workspace:
```bash
agy-switch --switch user2@example.com
```
To update the OS Credential Manager without restarting the editor window:
```bash
agy-switch --switch user2@example.com --no-restart
```

### Saving Active Session to Manifest
```bash
agy-switch --save
```

### Logging Out
```bash
agy-switch --logout
```

---

## 4. Per-Project Quota Allocation

You can bind any project or directory to a designated quota account. Subsequent language server prompts in that project will consume quota from that designated account:
```bash
agy-switch --set-project-quota "/path/to/my-project" user2@example.com
```
Accepts:
- Exact Project ID (e.g. `38a862ea-ade2-428a-b094-ff969a0e51c1`)
- Project folder name (e.g. `my-project`)
- Absolute or relative directory path

---

## 5. Model Context Protocol (MCP) Server Integration

The suite includes a zero-dependency stdio MCP server located at:
`%USERPROFILE%\.gemini\antigravity\bin\mcp_server.py`

### MCP Tools:
1. `get_quota_status(account?: string, include_all?: boolean)`:
   Fetches live model limits, session reset countdowns, and weekly usage.
2. `switch_account(account: string, no_restart?: boolean)`:
   Switches the OS Credential Manager token and active quota cache.
3. `set_project_quota(project: string, account: string)`:
   Configures project-level quota payer.
4. `list_saved_accounts()`:
   Returns array of all saved accounts, active state, tiers, and remaining percentages.

### MCP Configuration Snippet

#### For Gemini CLI / Antigravity / Claude Code (`mcp_config.json` or `settings.json`):
```json
{
  "mcpServers": {
    "antigravity-account-suite": {
      "command": "python",
      "args": [
        "%USERPROFILE%\\.gemini\\antigravity\\bin\\mcp_server.py"
      ],
      "env": {
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

---

## 6. Autonomous Quota Exhaustion & Failover Workflow

When an autonomous agent encounters rate limits (`429 Too Many Requests` or `RESOURCE_EXHAUSTED`):

1. **Query Available Accounts:**
   ```bash
   agy-switch --status-json
   ```
2. **Select Account with Highest Remaining Quota:**
   Parse `saved_accounts` and choose the account with the highest `remaining_pct` and `weekly_remaining_pct`.
3. **Execute Seamless In-Place Switch:**
   ```bash
   agy-switch --switch <target_account_email> --no-restart
   ```
4. **Retry the Prompt/Action:**
   Verify `active_account` in `active_quota.json` is updated, and proceed without interrupting user workflows.
