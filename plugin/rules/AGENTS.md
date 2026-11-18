# Antigravity Account Suite, Quota & Smart RTL (v3.0.0)

Use the `antigravity-account-suite` MCP server and sidecar to inspect real-time model quotas, switch Google accounts, assign per-project quota payers, and diagnose IDE telemetry:

- **`get_quota_status(account?, include_all?)`**: Live 5-hour & weekly quota plus all 6 model pools (`Gemini 4 Hydrogen`, `Gemini 4 Argon`, `Gemini 4 Carbon & Orchestrator`, `Gemini 3.8 Flash`, `Claude 4.6 (Opus & Sonnet)`, `GPT-OSS 120B`) and `live_ide_email` / `session_mismatch`.
- **`switch_account(account, no_restart?)`**: Switch OS Credential Manager / Keychain token (`no_restart=true` default for in-place switch).
- **`set_project_quota(project, account, apply_now?)`**: Bind a project/workspace to a designated quota payer account and switch OS credentials (`apply_now=true` default).
- **`list_saved_accounts()`**: List all saved Google accounts, subscription tiers, `has_token`/`needs_reauth` validity, and remaining quota percentages.
- **`diagnose_suite()`**: Run full health diagnostics (`LanguageServer` RPC, `DevToolsActivePort` / `--remote-debugging-port=0` CDP HUD, `sync_daemon` on `127.0.0.1:39281`, `control_center` on `127.0.0.1:39285`, local fonts, `session_mismatch`, and saved token health).
- **Live Aux Pane**: Surface `[Account & Quota Hub](sidecar://antigravity-account-suite/account-suite/)` whenever the user wants an interactive UI for quota bars, 1-click switching, CDP HUD activation, or project quota routing.
