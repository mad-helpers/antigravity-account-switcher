#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Antigravity Account Suite - Lightweight stdio MCP Server (Model Context Protocol) v3.0.0
Organization: mad-helpers (Madgod-xyz & Bombhub-apk)
Repository: https://github.com/mad-helpers/antigravity-account-switcher

Exposes 5 tools to AI Agents (Antigravity, Gemini CLI, Claude Code, VS Code / Cursor):
  - get_quota_status: Live 6-pool quota data for active account or specified account
  - switch_account: Switch active account token in OS Credential Manager / Keychain
  - set_project_quota: Set designated quota payer account for a project (switches OS credential by default)
  - list_saved_accounts: List all registered accounts, token health, and active status
  - diagnose_suite: Run full suite diagnostics (LanguageServer RPC, CDP, sync_daemon, fonts, accounts)
"""

import json
import sys
import traceback
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

if hasattr(sys.stdin, "reconfigure"):
    try:
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from ag_suite import VERSION, quota, store
import migration_engine
import server

SERVER_NAME = "antigravity-account-suite"
SERVER_VERSION = VERSION
PROTOCOL_VERSION = "2024-11-05"


def log_err(msg: str) -> None:
    """Write log messages to stderr so stdout remains 100% clean JSON-RPC."""
    sys.stderr.write(f"[mcp_server] {msg}\n")
    sys.stderr.flush()


def resolve_account(target: str | None) -> str | None:
    """Fuzzy match account key from email, name, or instance alias."""
    return store.resolve_account_key(target)


TOOLS_DEFINITIONS = [
    {
        "name": "get_quota_status",
        "description": (
            "Fetch real-time quota status and 6-pool model limits for Antigravity accounts "
            "(5-Hour & Weekly limits, Gemini 4 Hydrogen, Gemini 4 Argon, Gemini 4 Carbon & Orchestrator, "
            "Gemini 3.8 Flash, Claude 4.6 (Opus & Sonnet), GPT-OSS 120B) plus live session mismatch state."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "Specific account email or instance alias (e.g. 'instance_2', 'user2@example.com') to query (optional; defaults to the currently active account)",
                },
                "include_all": {
                    "type": "boolean",
                    "description": "If true, returns sanitized quota summaries for all saved accounts registered in the suite",
                },
            },
        },
    },
    {
        "name": "switch_account",
        "description": "Switch the active Antigravity account token in the OS Credential Manager (Windows), Keychain (macOS), or secret store (Linux).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "Email address or alias of the saved account to switch to",
                },
                "no_restart": {
                    "type": "boolean",
                    "description": "If true (default), updates the OS credential without terminating/restarting the Antigravity editor process",
                },
            },
            "required": ["account"],
        },
    },
    {
        "name": "set_project_quota",
        "description": "Designate which Google account pays for AI model quota and language server requests for a specific project workspace, switching OS credentials by default.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project ID, project folder name, or directory path",
                },
                "account": {
                    "type": "string",
                    "description": "Email address or alias of the account designated as the quota payer",
                },
                "apply_now": {
                    "type": "boolean",
                    "description": "If true (default), immediately switches the OS credential token to this account (no_restart=true)",
                },
            },
            "required": ["project", "account"],
        },
    },
    {
        "name": "list_saved_accounts",
        "description": "List all registered Antigravity accounts, subscription tiers, remaining session & weekly quotas, has_token/needs_reauth health, and active status.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "diagnose_suite",
        "description": "Run comprehensive health diagnostics on Antigravity LanguageServer RPC, OS Credential Vault, session_mismatch, CDP DevTools port (--remote-debugging-port=0), sync_daemon (:39281), Control Center (:39285), local fonts, and saved account tokens.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def handle_get_quota_status(args: dict) -> dict:
    target_account = args.get("account")
    include_all = bool(args.get("include_all", False))
    auth_state = quota.get_live_ide_auth_state()

    res: dict = {"auth_state": auth_state}
    if target_account:
        resolved_key = resolve_account(target_account)
        if not resolved_key:
            return {
                "success": False,
                "error": f"Account '{target_account}' not found among registered accounts.",
            }
        token_str = store.read_account_token(resolved_key)
        if not token_str:
            return {
                "success": False,
                "error": f"Token missing or unreadable for account '{resolved_key}'.",
            }
        q_data = quota.fetch_quota_and_tier(token_str)
        res["success"] = True
        res["account"] = resolved_key
        res["quota"] = q_data
    else:
        res["success"] = True
        res["active_account"] = quota.fetch_quota_and_tier()

    if include_all:
        res["saved_accounts"] = store.sanitize_manifest_for_client()

    return res


def handle_switch_account(args: dict) -> dict:
    account = args.get("account")
    if not account:
        return {"success": False, "error": "Missing required argument 'account'"}

    no_restart = bool(args.get("no_restart", True))
    resolved_key = resolve_account(account)
    if not resolved_key:
        return {
            "success": False,
            "error": f"Account '{account}' not found among registered accounts.",
        }

    return server.switch_account(resolved_key, no_restart=no_restart)


def handle_set_project_quota(args: dict) -> dict:
    project = args.get("project")
    account = args.get("account")
    if not project or not account:
        return {"success": False, "error": "Missing required arguments 'project' and 'account'"}

    apply_now = bool(args.get("apply_now", True))
    resolved_acc = resolve_account(account) or str(account).strip()

    matched = migration_engine.resolve_project(project)
    if not matched:
        return {
            "success": False,
            "error": f"Project '{project}' not found among discovered projects.",
        }

    res = migration_engine.set_project_quota_account(matched["id"], resolved_acc)
    res["project_name"] = matched["name"]
    res["project_path"] = matched["path"]

    credential_switched = False
    manifest = store.load_manifest()
    manifest_key = store.resolve_account_key(resolved_acc, manifest)
    if apply_now and manifest_key:
        sw = server.switch_account(manifest_key, no_restart=True)
        credential_switched = bool(sw.get("success"))

    auth_state = quota.get_live_ide_auth_state(use_cache=False)
    res["credential_switched"] = credential_switched
    res["auth_state"] = auth_state
    res["live_ide_email"] = auth_state.get("live_ide_email")
    res["credential_email"] = auth_state.get("credential_email")
    res["session_mismatch"] = bool(auth_state.get("session_mismatch", False))
    return res


def handle_list_saved_accounts(args: dict | None = None) -> dict:
    sanitized = store.sanitize_manifest_for_client()
    auth_state = quota.get_live_ide_auth_state()
    curr_email = auth_state.get("credential_email") or auth_state.get("live_ide_email")
    if not curr_email:
        try:
            active_q = quota.fetch_quota_and_tier()
            if active_q and active_q.get("email"):
                curr_email = active_q["email"]
        except Exception:
            pass

    curr_low = str(curr_email or "").lower()
    accounts_list = []
    for k, v in sanitized.items():
        em = str(v.get("email") or k)
        is_active = bool(curr_low and (k.lower() == curr_low or em.lower() == curr_low))
        accounts_list.append({
            "email": em,
            "label": v.get("label") or em,
            "name": v.get("name") or "User",
            "avatar": v.get("avatar") or "",
            "tier": v.get("tier") or "Google AI Pro",
            "tier_code": v.get("tier_code") or "pro",
            "remaining_pct": float(v.get("remaining_pct", 100.0)),
            "weekly_remaining_pct": float(v.get("weekly_remaining_pct", 100.0)),
            "weekly_resets_in": v.get("weekly_resets_in") or "Ready",
            "has_token": bool(v.get("has_token", False)),
            "needs_reauth": bool(v.get("needs_reauth", True)),
            "is_active": is_active,
            "saved_at": v.get("saved_at") or "",
            "instance_id": v.get("instance_id"),
        })

    return {
        "accounts": accounts_list,
        "active_email": curr_email,
        "auth_state": auth_state,
        "total_count": len(accounts_list),
    }


def handle_diagnose_suite(args: dict | None = None) -> dict:
    diag = quota.diagnose_suite()
    return {"success": True, **diag}


TOOL_HANDLERS = {
    "get_quota_status": handle_get_quota_status,
    "switch_account": handle_switch_account,
    "set_project_quota": handle_set_project_quota,
    "list_saved_accounts": handle_list_saved_accounts,
    "diagnose_suite": handle_diagnose_suite,
}


def process_rpc_request(req: dict) -> dict | None:
    """Process a single JSON-RPC 2.0 request dictionary and return a response dict."""
    if not isinstance(req, dict):
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32600, "message": "Invalid Request: expected object"},
        }

    req_id = req.get("id")
    method = req.get("method")

    if req_id is None and method == "notifications/initialized":
        log_err("Client confirmed initialization.")
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS_DEFINITIONS},
        }

    if method == "tools/call":
        params = req.get("params") or {}
        tool_name = params.get("name")
        tool_args = params.get("arguments") or {}

        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Tool '{tool_name}' not found.",
                },
            }

        try:
            result_data = handler(tool_args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result_data, indent=2, ensure_ascii=False),
                        }
                    ],
                    "isError": False,
                },
            }
        except Exception as e:
            log_err(f"Error executing tool '{tool_name}': {e}\n{traceback.format_exc()}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error executing tool '{tool_name}': {str(e)}",
                        }
                    ],
                    "isError": True,
                },
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": -32601,
            "message": f"Method '{method}' not implemented.",
        },
    }


def run_self_test() -> int:
    """Execute dynamic, non-mutating verification tests for all 5 MCP tools."""
    print(f"=== Antigravity MCP Server Self-Test ({SERVER_NAME} v{SERVER_VERSION}) ===")

    # 1. initialize
    init_res = process_rpc_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init_res["result"]["serverInfo"]["name"] == SERVER_NAME
    assert init_res["result"]["serverInfo"]["version"] == "3.0.0"
    print("✓ initialize: OK")

    # 2. tools/list
    list_res = process_rpc_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools = list_res["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    expected = [
        "get_quota_status",
        "switch_account",
        "set_project_quota",
        "list_saved_accounts",
        "diagnose_suite",
    ]
    for exp in expected:
        assert exp in tool_names, f"Missing tool: {exp}"
    print(f"✓ tools/list: OK ({len(tools)} tools registered)")

    # 3. list_saved_accounts (verify sanitization: zero token_file, has_token & needs_reauth present)
    acc_res = process_rpc_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "list_saved_accounts", "arguments": {}},
    })
    assert not acc_res.get("error"), f"list_saved_accounts error: {acc_res}"
    acc_text = acc_res["result"]["content"][0]["text"]
    assert "token_file" not in acc_text, "Leaked token_file in list_saved_accounts!"
    acc_data = json.loads(acc_text)
    assert "accounts" in acc_data and "auth_state" in acc_data
    for acc_entry in acc_data["accounts"]:
        assert "has_token" in acc_entry and "needs_reauth" in acc_entry
    print(f"✓ tools/call (list_saved_accounts): OK ({acc_data['total_count']} accounts found)")

    # 4. get_quota_status (active + include_all)
    q_res = process_rpc_request({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "get_quota_status", "arguments": {"include_all": True}},
    })
    assert not q_res.get("error"), f"get_quota_status error: {q_res}"
    q_text = q_res["result"]["content"][0]["text"]
    assert "token_file" not in q_text, "Leaked token_file in get_quota_status!"
    q_data = json.loads(q_text)
    assert q_data.get("success") is True
    assert "active_account" in q_data and "saved_accounts" in q_data
    print("✓ tools/call (get_quota_status - active & sanitized): OK")

    # 5. get_quota_status with non-existent account
    q_fake = process_rpc_request({
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "get_quota_status", "arguments": {"account": "nonexistent_fake_account_12345@test.com"}},
    })
    q_fake_data = json.loads(q_fake["result"]["content"][0]["text"])
    assert q_fake_data.get("success") is False
    print("✓ tools/call (get_quota_status - non-existent error validation): OK")

    # 6. switch_account with non-existent account (no mutation)
    sw_fake = process_rpc_request({
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {"name": "switch_account", "arguments": {"account": "nonexistent_fake_account_12345@test.com", "no_restart": True}},
    })
    sw_fake_data = json.loads(sw_fake["result"]["content"][0]["text"])
    assert sw_fake_data.get("success") is False
    print("✓ tools/call (switch_account - error validation): OK")

    # 7. set_project_quota (dynamic & non-mutating: backup & restore profile_sync_manifest.json)
    prof_path = Path(migration_engine.PROFILE_SYNC_MANIFEST_PATH)
    orig_prof_bytes = prof_path.read_bytes() if prof_path.is_file() else None
    try:
        curr_projects = migration_engine.list_projects()
        target_proj = curr_projects[0]["id"] if curr_projects else str(SCRIPT_DIR)
        target_acc = (curr_projects[0].get("quota_account") if curr_projects else None) or "user@example.com"
        sp_res = process_rpc_request({
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "set_project_quota",
                "arguments": {
                    "project": target_proj,
                    "account": target_acc,
                    "apply_now": False,
                },
            },
        })
        assert not sp_res.get("error"), f"set_project_quota error: {sp_res}"
        sp_data = json.loads(sp_res["result"]["content"][0]["text"])
        assert sp_data.get("success") is True, f"Failed set_project_quota: {sp_data}"
        assert "session_mismatch" in sp_data and "live_ide_email" in sp_data and "credential_switched" in sp_data
    finally:
        if orig_prof_bytes is not None:
            prof_path.write_bytes(orig_prof_bytes)
        elif prof_path.is_file():
            prof_path.unlink()
        migration_engine.invalidate_migration_caches()
    print("✓ tools/call (set_project_quota - non-mutating restore): OK")

    # 8. diagnose_suite (verify frozen v3.0 schema keys)
    diag_res = process_rpc_request({
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {"name": "diagnose_suite", "arguments": {}},
    })
    assert not diag_res.get("error"), f"diagnose_suite error: {diag_res}"
    diag_data = json.loads(diag_res["result"]["content"][0]["text"])
    assert diag_data.get("success") is True
    for key in (
        "ok",
        "version",
        "system",
        "auth_state",
        "cdp",
        "sync_daemon",
        "control_center",
        "fonts",
        "accounts",
        "issues",
    ):
        assert key in diag_data, f"diagnose_suite missing frozen key: {key}"
    print("✓ tools/call (diagnose_suite - frozen v3.0 schema): OK")

    print("\nAll MCP Server v3.0 tool tests passed successfully!\n")
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "-t", "test"):
        return run_self_test()

    log_err(f"Starting {SERVER_NAME} v{SERVER_VERSION} stdio JSON-RPC server...")

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                log_err("Client closed stdin connection. Exiting gracefully.")
                break

            line_str = line.strip()
            if not line_str:
                continue

            try:
                req_obj = json.loads(line_str)
            except json.JSONDecodeError as err:
                log_err(f"JSON parse error: {err}")
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"},
                }
                sys.stdout.write(json.dumps(err_resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
                continue

            resp_obj = process_rpc_request(req_obj)
            if resp_obj is not None:
                sys.stdout.write(json.dumps(resp_obj, ensure_ascii=False) + "\n")
                sys.stdout.flush()

        except KeyboardInterrupt:
            log_err("KeyboardInterrupt received. Shutting down.")
            break
        except Exception as e:
            log_err(f"Fatal loop exception: {e}\n{traceback.format_exc()}")
            break

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
