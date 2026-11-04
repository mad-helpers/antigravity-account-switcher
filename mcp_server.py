#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Antigravity Account Suite - Lightweight stdio MCP Server (Model Context Protocol)
Author: Ethan Carter (Bombhub-apk) & Madgod-xyz
Repository: https://github.com/Bombhub-apk/antigravity-account-switcher

Exposes tools to AI Agents (Antigravity, Gemini CLI, Claude Code, VS Code / Cursor):
  - get_quota_status: Live quota data for active account or specified account
  - switch_account: Switch active account token in OS Credential Manager / Keychain
  - set_project_quota: Set designated quota payer account for a project
  - list_saved_accounts: List all registered accounts and active status
"""

import os
import sys
import json
import traceback
from pathlib import Path

# Set up local import paths
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Ensure standard IO streams are in UTF-8
if hasattr(sys.stdin, 'reconfigure'):
    try:
        sys.stdin.reconfigure(encoding='utf-8')
    except Exception:
        pass
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Import core suite engines
import quota_engine
import migration_engine
import server

SERVER_NAME = "antigravity-account-suite"
SERVER_VERSION = "1.0.1"
PROTOCOL_VERSION = "2024-11-05"

def log_err(msg):
    """Write log messages to stderr so stdout remains 100% clean JSON-RPC."""
    sys.stderr.write(f"[mcp_server] {msg}\n")
    sys.stderr.flush()

def resolve_account(target):
    """Fuzzy match account key from email, name, or instance alias."""
    if not target:
        return None
    manifest = server.load_manifest()
    clean = target.strip().lower()

    # 1. Exact key match
    for k in manifest.keys():
        if k.lower() == clean:
            return k

    # 2. Email, name, or instance_id match
    for k, v in manifest.items():
        if v.get('email', '').lower() == clean:
            return k
        if v.get('name', '').lower() == clean:
            return k
        if v.get('instance_id', '').lower() == clean:
            return k

    # 3. Substring match
    for k in manifest.keys():
        if clean in k.lower():
            return k

    return None

TOOLS_DEFINITIONS = [
    {
        "name": "get_quota_status",
        "description": "Fetch real-time quota status and model pool limits for Antigravity accounts (session & weekly limits, Gemini 3.8 Flash High, Gemini 3.1 Pro, Claude Sonnet 4.6, GPT-OSS 120B).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "Specific account email or instance alias (e.g. 'instance_2', 'user2@example.com') to query (optional; defaults to the currently active account)"
                },
                "include_all": {
                    "type": "boolean",
                    "description": "If true, returns quota summaries for all saved accounts registered in the suite"
                }
            }
        }
    },
    {
        "name": "switch_account",
        "description": "Switch the active Antigravity account token in the OS Credential Manager (Windows) or Keychain (macOS). Updates active quota cache and reloads editor credentials.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "Email address or alias of the saved account to switch to"
                },
                "no_restart": {
                    "type": "boolean",
                    "description": "If true, updates the OS credential without terminating/restarting the Antigravity editor process (default: false)"
                }
            },
            "required": ["account"]
        }
    },
    {
        "name": "set_project_quota",
        "description": "Designate which Google account pays for AI model quota and language server requests for a specific project workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project ID, project folder name, or directory path"
                },
                "account": {
                    "type": "string",
                    "description": "Email address or alias of the account designated as the quota payer"
                }
            },
            "required": ["project", "account"]
        }
    },
    {
        "name": "list_saved_accounts",
        "description": "List all registered Antigravity accounts, their subscription tiers, remaining session & weekly quotas, instance allocations, and currently active status.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]

def handle_get_quota_status(args):
    target_account = args.get("account")
    include_all = bool(args.get("include_all", False))

    res = {}
    if target_account:
        resolved_key = resolve_account(target_account)
        if not resolved_key:
            return {
                "success": False,
                "error": f"Account '{target_account}' not found among registered accounts."
            }
        manifest = server.load_manifest()
        entry = manifest.get(resolved_key, {})
        tok_file = entry.get('token_file')
        token_str = None
        if tok_file and os.path.exists(tok_file):
            try:
                with open(tok_file, 'r', encoding='utf-8') as f:
                    token_str = f.read().strip()
            except Exception:
                pass

        if not token_str:
            return {
                "success": False,
                "error": f"Token file missing or unreadable for account '{resolved_key}'."
            }

        q_data = quota_engine.fetch_quota_and_tier(token_str)
        res["success"] = True
        res["account"] = resolved_key
        res["quota"] = q_data
    else:
        res["success"] = True
        res["active_account"] = quota_engine.fetch_quota_and_tier()

    if include_all:
        manifest = server.load_manifest()
        all_accounts = {}
        for k, v in manifest.items():
            all_accounts[k] = {
                "email": v.get("email", k),
                "name": v.get("name", "User"),
                "tier": v.get("tier", "Google AI Pro"),
                "remaining_pct": v.get("remaining_pct", 100.0),
                "weekly_remaining_pct": v.get("weekly_remaining_pct", 100.0),
                "saved_at": v.get("saved_at", ""),
                "instance_id": v.get("instance_id")
            }
        res["saved_accounts"] = all_accounts

    return res

def handle_switch_account(args):
    account = args.get("account")
    if not account:
        return {"success": False, "error": "Missing required argument 'account'"}
    
    no_restart = bool(args.get("no_restart", False))
    resolved_key = resolve_account(account)
    if not resolved_key:
        return {
            "success": False,
            "error": f"Account '{account}' not found among registered accounts."
        }

    res = server.switch_account(resolved_key, no_restart=no_restart)
    return res

def handle_set_project_quota(args):
    project = args.get("project")
    account = args.get("account")
    if not project or not account:
        return {"success": False, "error": "Missing required arguments 'project' and 'account'"}

    resolved_acc = resolve_account(account) or account.strip()

    projects = migration_engine.list_projects()
    matched_pid = None
    matched_name = None
    proj_clean = project.strip().lower()
    norm_arg = os.path.normpath(project).lower()

    for p in projects:
        p_id = p.get('id', '')
        p_name = p.get('name', '')
        p_path = p.get('path', '')
        p_norm_path = os.path.normpath(p_path).lower() if p_path else ''
        if p_id.lower() == proj_clean or (p_norm_path and (p_norm_path == norm_arg or norm_arg in p_norm_path)) or p_name.lower() == proj_clean:
            matched_pid = p_id
            matched_name = p_name
            break

    if not matched_pid:
        for p in projects:
            p_id = p.get('id', '')
            p_name = p.get('name', '')
            p_path = p.get('path', '')
            if proj_clean in p_name.lower() or (p_path and proj_clean in p_path.lower()):
                matched_pid = p_id
                matched_name = p_name
                break

    if not matched_pid:
        candidates = [
            project,
            os.path.join(os.getcwd(), project),
            os.path.join(str(SCRIPT_DIR.parent), project),
            os.path.join(str(SCRIPT_DIR), project)
        ]
        for c in candidates:
            if os.path.isdir(c):
                matched_pid = os.path.basename(os.path.normpath(c))
                matched_name = matched_pid
                break

    if not matched_pid:
        return {
            "success": False,
            "error": f"Project '{project}' not found among discovered projects."
        }

    res = migration_engine.set_project_quota_account(matched_pid, resolved_acc)
    res["project_name"] = matched_name
    return res

def handle_list_saved_accounts(args=None):
    manifest = server.load_manifest()
    curr_email = None
    try:
        active_q = quota_engine.fetch_quota_and_tier()
        if active_q and active_q.get('email'):
            curr_email = active_q['email']
    except Exception:
        pass

    curr_cred = quota_engine.get_windows_credential() if sys.platform == 'win32' else quota_engine.get_keychain_token()

    accounts_list = []
    for k, v in manifest.items():
        is_active = False
        tok_file = v.get('token_file', '')
        if curr_email and (k.lower() == curr_email.lower() or v.get('email', '').lower() == curr_email.lower()):
            is_active = True
        elif curr_cred and tok_file and os.path.exists(tok_file):
            try:
                with open(tok_file, 'r', encoding='utf-8') as f:
                    if f.read().strip() == curr_cred.strip():
                        is_active = True
            except Exception:
                pass

        accounts_list.append({
            "email": v.get("email", k),
            "label": v.get("label", k),
            "name": v.get("name", "User"),
            "tier": v.get("tier", "Google AI Pro"),
            "tier_code": v.get("tier_code", "pro"),
            "remaining_pct": v.get("remaining_pct", 100.0),
            "weekly_remaining_pct": v.get("weekly_remaining_pct", 100.0),
            "is_active": is_active,
            "saved_at": v.get("saved_at", ""),
            "instance_id": v.get("instance_id")
        })

    return {
        "accounts": accounts_list,
        "active_email": curr_email,
        "total_count": len(accounts_list)
    }

TOOL_HANDLERS = {
    "get_quota_status": handle_get_quota_status,
    "switch_account": handle_switch_account,
    "set_project_quota": handle_set_project_quota,
    "list_saved_accounts": handle_list_saved_accounts
}

def process_rpc_request(req):
    """Processes a single JSON-RPC 2.0 request dictionary and returns a response dict."""
    if not isinstance(req, dict):
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32600, "message": "Invalid Request: expected object"}
        }

    req_id = req.get("id")
    method = req.get("method")

    # Notifications do not receive a response
    if req_id is None and method == "notifications/initialized":
        log_err("Client confirmed initialization.")
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION
                }
            }
        }

    elif method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {}
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS_DEFINITIONS
            }
        }

    elif method == "tools/call":
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
                    "message": f"Tool '{tool_name}' not found."
                }
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
                            "text": json.dumps(result_data, indent=2, ensure_ascii=False)
                        }
                    ],
                    "isError": False
                }
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
                            "text": f"Error executing tool '{tool_name}': {str(e)}"
                        }
                    ],
                    "isError": True
                }
            }

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not implemented."
            }
        }

def run_self_test():
    """Execute internal verification tests for all tools."""
    print(f"=== Antigravity MCP Server Self-Test ({SERVER_NAME} v{SERVER_VERSION}) ===")
    
    # 1. Test initialize
    init_res = process_rpc_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    })
    assert init_res["result"]["serverInfo"]["name"] == SERVER_NAME, "Init serverInfo mismatch"
    print("✓ initialize: OK")

    # 2. Test tools/list
    list_res = process_rpc_request({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    })
    tools = list_res["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    expected = ["get_quota_status", "switch_account", "set_project_quota", "list_saved_accounts"]
    for exp in expected:
        assert exp in tool_names, f"Missing tool: {exp}"
    print(f"✓ tools/list: OK ({len(tools)} tools registered)")

    # 3. Test list_saved_accounts call
    acc_res = process_rpc_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "list_saved_accounts", "arguments": {}}
    })
    assert not acc_res.get("error"), f"list_saved_accounts error: {acc_res}"
    acc_data = json.loads(acc_res["result"]["content"][0]["text"])
    assert "accounts" in acc_data, "Expected 'accounts' key"
    print(f"✓ tools/call (list_saved_accounts): OK ({acc_data['total_count']} accounts found)")

    # 4. Test get_quota_status call (active account)
    q_res = process_rpc_request({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "get_quota_status", "arguments": {"include_all": True}}
    })
    assert not q_res.get("error"), f"get_quota_status error: {q_res}"
    q_data = json.loads(q_res["result"]["content"][0]["text"])
    assert q_data.get("success") is True, f"get_quota_status failed: {q_data}"
    assert "active_account" in q_data or "quota" in q_data, "Expected quota data"
    print("✓ tools/call (get_quota_status - active): OK")

    # 5. Test get_quota_status call with non-existent account (must return error, not silent fallback!)
    q_fake = process_rpc_request({
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "get_quota_status", "arguments": {"account": "nonexistent_fake_account_12345@test.com"}}
    })
    q_fake_data = json.loads(q_fake["result"]["content"][0]["text"])
    assert q_fake_data.get("success") is False, f"Expected failure for fake account, got {q_fake_data}"
    print("✓ tools/call (get_quota_status - non-existent error validation): OK")

    # 6. Test switch_account call with non-existent account (validation without altering live token)
    sw_fake = process_rpc_request({
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {"name": "switch_account", "arguments": {"account": "nonexistent_fake_account_12345@test.com", "no_restart": True}}
    })
    sw_fake_data = json.loads(sw_fake["result"]["content"][0]["text"])
    assert sw_fake_data.get("success") is False, f"Expected failure for fake account, got {sw_fake_data}"
    print("✓ tools/call (switch_account - error validation): OK")

    # 7. Test set_project_quota call and preserve previous assignment
    # Read current quota account for gravity suitch accont
    curr_projects = migration_engine.list_projects()
    prev_payer = None
    for p in curr_projects:
        if "gravity suitch accont" in p.get("name", ""):
            prev_payer = p.get("quota_account")
            break

    sp_res = process_rpc_request({
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "set_project_quota",
            "arguments": {
                "project": "sample-project",
                "account": "user2@example.com"
            }
        }
    })
    assert not sp_res.get("error"), f"set_project_quota error: {sp_res}"
    sp_data = json.loads(sp_res["result"]["content"][0]["text"])
    assert sp_data.get("success") is True, f"Failed set_project_quota: {sp_data}"
    
    # Restore if had previous payer
    if prev_payer:
        migration_engine.set_project_quota_account("38a862ea-ade2-428a-b094-ff969a0e51c1", prev_payer)
    print("✓ tools/call (set_project_quota): OK")

    print("\nAll MCP Server tool tests passed successfully!\n")
    return 0

def main():
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
                    "error": {"code": -32700, "message": "Parse error"}
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

if __name__ == '__main__':
    sys.exit(main() or 0)
