#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backward-compatible quota engine shim delegating to ag_suite."""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from ag_suite import VERSION  # noqa: F401
from ag_suite.cdp import (  # noqa: F401
    check_local_http_request,
    discover_live_cdp_ports,
    get_devtools_targets,
    heal_devtools_port_file,
    is_antigravity_workbench_target,
    is_port_open,
    is_valid_cdp_port,
    select_workbench_target,
)
from ag_suite.quota import (  # noqa: F401
    ORDERED_POOLS,
    _build_quota_pools,
    _manifest_fallback_quota,
    call_ls_rpc,
    diagnose_suite,
    discover_language_server,
    fetch_quota,
    fetch_quota_and_tier,
    fetch_quota_from_language_server,
    format_countdown,
    get_live_ide_auth_state,
    invalidate_ls_cache,
)
from ag_suite.store import (  # noqa: F401
    DEFAULT_USER_SETTINGS,
    load_manifest,
    load_user_settings,
    resolve_account_key,
    resolve_font_asset,
    rotate_log_if_needed,
    sanitize_manifest_for_client,
    save_manifest,
    save_user_settings,
)
from ag_suite.vault import (  # noqa: F401
    ANTIGRAVITY_OAUTH_SCOPES,
    CREDENTIAL_TARGETS,
    OAUTH_CLIENT_ID,
    OAUTH_CLIENT_SECRET,
    check_token_has_aicode,
    clear_keychain_token,
    decode_token_dict,
    delete_keychain_tokens,
    ensure_fresh_token,
    extract_token_email,
    get_current_system,
    get_keychain_token,
    get_platform_paths,
    get_windows_credential,
    normalize_token_payload,
    parse_token_payload,
    write_keychain_token,
)


def _run_self_tests() -> int:
    import base64
    import tempfile

    raw_json = json.dumps({"token": {"access_token": "ya29.test", "refresh_token": "1//rt"}, "id_token_email": "User@Example.COM"})
    b64_tok = "go-keyring-base64:" + base64.b64encode(raw_json.encode("utf-8")).decode("ascii")
    assert parse_token_payload(raw_json) == ("ya29.test", "1//rt")
    assert parse_token_payload(b64_tok) == ("ya29.test", "1//rt")
    assert parse_token_payload("ya29.bare") == ("ya29.bare", None)
    assert extract_token_email(b64_tok, check_manifest=False) == "user@example.com"

    groups = [{"buckets": [
        {"bucketId": "gemini-5h", "remainingFraction": 0.85},
        {"bucketId": "gemini-weekly", "remainingFraction": 0.90},
        {"bucketId": "3p-5h", "remainingFraction": 0.70},
        {"bucketId": "3p-weekly", "remainingFraction": 0.75},
    ]}]
    models = {
        "gemini-pro-orchestrator-g1-pro": {"quotaInfo": {"remainingFraction": 0.85}},
        "claude-opus-5-5": {"quotaInfo": {"remainingFraction": 0.70}},
        "gpt-oss-120b": {"quotaInfo": {"remainingFraction": 0.70}},
    }
    _, _, pools = _build_quota_pools(groups, models)
    assert [p["name"] for p in pools] == ORDERED_POOLS
    argon_pool = next(p for p in pools if p["name"] == "Gemini 4 Argon")
    assert argon_pool["remaining_pct"] == 85.0 and argon_pool["weekly_rem"] == 90.0

    with tempfile.TemporaryDirectory() as tmp:
        font_dir = Path(tmp) / "fonts"
        font_dir.mkdir()
        (font_dir / "Vazirmatn[wght].woff2").write_bytes(b"wOF2")
        p_dec, mime = resolve_font_asset("Vazirmatn%5Bwght%5D.woff2", extra_dirs=[font_dir])
        assert p_dec is not None and p_dec.name == "Vazirmatn[wght].woff2" and mime == "font/woff2"
        assert resolve_font_asset("../secret.py", extra_dirs=[font_dir]) == (None, None)

        tf = Path(tmp) / "a.token"
        tf.write_text(raw_json, encoding="utf-8")
        san = sanitize_manifest_for_client({"a@b.com": {"email": "a@b.com", "token_file": str(tf)}})
        assert "token_file" not in san["a@b.com"] and san["a@b.com"]["has_token"] is True

    wb = {"type": "page", "url": "vscode-file://vscode-app/index.html", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1"}
    ext = {"type": "page", "url": "https://example.com/ai/", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/2"}
    assert select_workbench_target([ext, wb]) == wb
    assert select_workbench_target([ext]) is None

    assert check_local_http_request({}, "GET", "/fonts/Vazirmatn%5Bwght%5D.woff2") == (True, "*")
    assert check_local_http_request({"Origin": "vscode-file://vscode-app", "Content-Type": "application/json"}, "POST", "/api/switch") == (True, "vscode-file://vscode-app")
    assert check_local_http_request({"Origin": "https://evil.com", "Content-Type": "application/json"}, "POST", "/api/switch")[0] is False
    assert check_local_http_request({"Origin": "null", "Content-Type": "application/json"}, "POST", "/api/switch")[0] is False
    assert check_local_http_request({"Origin": "http://127.0.0.1:39285"}, "POST", "/api/switch")[0] is False
    assert check_local_http_request({"Sec-Fetch-Site": "cross-site"}, "GET", "/api/state")[0] is False

    print("quota_engine self-tests passed.")
    return 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--test":
        sys.exit(_run_self_tests())
    if arg == "--doctor":
        print(json.dumps(diagnose_suite(), indent=2, ensure_ascii=False))
        sys.exit(0)
    res = fetch_quota_and_tier()
    print(json.dumps(res or {"error": "No active session found"}, indent=2, ensure_ascii=False))
