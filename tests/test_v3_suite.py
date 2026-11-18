#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comprehensive v3.0 verification suite for Antigravity Account Switcher & Quota Monitor."""

import base64
import hashlib
import inspect
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ag_suite
from ag_suite import cdp, quota, store, vault
import cli
import mcp_server
import migration_engine
import quota_engine
import server
import switcher_core
import sync_daemon

NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def test_install_ps1_pure_ascii_no_bom_and_wrapped():
    ps1_path = ROOT / "install.ps1"
    raw = ps1_path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "install.ps1 MUST NOT start with UTF-8 BOM"
    bad_bytes = [i for i, b in enumerate(raw) if b not in (9, 10, 13) and not (32 <= b <= 126)]
    assert not bad_bytes, f"install.ps1 contains non-ASCII bytes at offsets: {bad_bytes[:10]}"

    text = raw.decode("ascii")
    assert "function Install-AntigravitySuite" in text
    assert "Install-AntigravitySuite @args" in text
    assert "--remote-debugging-port=0" in text
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        assert not stripped.lower().startswith("param("), "install.ps1 must not begin with top-level param("
        break


def test_main_branch_urls_and_file_parities():
    url_files = (
        "install.ps1",
        "install.sh",
        "README.md",
        "README_FA.md",
        "docs/index.html",
        "HANDOFF_AND_BACKUP.md",
        "skills/antigravity-account-suite/SKILL.md",
        "plugin/skills/antigravity-account-suite/SKILL.md",
    )
    for rel in url_files:
        p = ROOT / rel
        assert p.is_file(), f"Missing {rel}"
        content = p.read_text(encoding="utf-8")
        assert "/master/" not in content, f"Stale /master/ URL found in {rel}"
        assert "mad-helpers/antigravity-account-switcher" in content, f"Missing mad-helpers repo URL in {rel}"

    skill_a = (ROOT / "skills/antigravity-account-suite/SKILL.md").read_bytes()
    skill_b = (ROOT / "plugin/skills/antigravity-account-suite/SKILL.md").read_bytes()
    assert hashlib.sha256(skill_a).hexdigest() == hashlib.sha256(skill_b).hexdigest(), "SKILL.md copies diverged"

    sw_a = (ROOT / "switcher_core.py").read_bytes()
    sw_b = (ROOT / "AntigravitySwitcher.app/Contents/Resources/switcher_core.py").read_bytes()
    assert hashlib.sha256(sw_a).hexdigest() == hashlib.sha256(sw_b).hexdigest(), "switcher_core.py copies diverged"

    assert not (ROOT / "app" / "runtime_window.html").exists(), "app/runtime_window.html must be removed"

    mcp_cfg = (ROOT / "plugin" / "mcp_config.json").read_text(encoding="utf-8")
    assert not re.search(r"(?i)(?:c:[\\/]+users[\\/]|/users/|/home/)", mcp_cfg), "plugin/mcp_config.json contains hardcoded user path"


def test_ag_suite_vault_and_store_contracts():
    assert ag_suite.VERSION == "3.0.0"
    assert vault.delete_keychain_tokens is vault.clear_keychain_token

    raw_json = json.dumps({
        "token": {"access_token": "ya29.acc1", "refresh_token": "1//ref1", "expiry": "2030-01-01T00:00:00+00:00"},
        "email": "Dev@Example.com",
    })
    assert vault.parse_token_payload(raw_json) == ("ya29.acc1", "1//ref1")
    assert vault.parse_token_payload("ya29.bare_tok") == ("ya29.bare_tok", None)

    b64_keyring = "go-keyring-base64:" + base64.b64encode(raw_json.encode("utf-8")).decode("ascii")
    dec = vault.decode_token_dict(b64_keyring)
    assert isinstance(dec, dict) and dec["token"]["access_token"] == "ya29.acc1"
    assert vault.extract_token_email(b64_keyring, check_manifest=False) == "dev@example.com"

    with tempfile.TemporaryDirectory() as td:
        thome = Path(td)
        with mock.patch.object(Path, "home", return_value=thome), \
             mock.patch.object(vault, "get_current_system", return_value="linux"), \
             mock.patch("shutil.which", return_value=None):
            assert vault.write_keychain_token(raw_json) is True
            cred_path = vault.get_platform_paths()["active_cred_path"]
            assert cred_path.is_file()
            if os.name != "nt":
                assert (cred_path.stat().st_mode & 0o777) == 0o600
            assert vault.parse_token_payload(vault.get_keychain_token()) == ("ya29.acc1", "1//ref1")
            assert vault.clear_keychain_token() is True
            assert not cred_path.exists()

        with mock.patch.object(Path, "home", return_value=thome):
            s1 = store.load_user_settings()
            s1["rtl"]["enabled"] = False
            s2 = store.load_user_settings()
            assert s2["rtl"]["enabled"] is True, "DEFAULT_USER_SETTINGS must be deep-copied"

            ok, merged = store.save_user_settings({"rtl": {"align": "left"}})
            assert ok is True
            assert merged["rtl"]["align"] == "left"
            assert merged["rtl"]["enabled"] is True
            assert merged["rtl"]["font"] == "Vazirmatn"

            tf_valid = thome / "valid.token"
            tf_valid.write_text(raw_json, encoding="utf-8")
            manifest = {
                "dev@example.com": {
                    "email": "dev@example.com",
                    "token_file": str(tf_valid),
                    "remaining_pct": 88.0,
                },
                "stale@example.com": {
                    "email": "stale@example.com",
                    "token_file": str(thome / "missing.token"),
                },
            }
            sanitized = store.sanitize_manifest_for_client(manifest)
            assert "token_file" not in json.dumps(sanitized)
            assert sanitized["dev@example.com"]["has_token"] is True
            assert sanitized["dev@example.com"]["needs_reauth"] is False
            assert sanitized["stale@example.com"]["has_token"] is False
            assert sanitized["stale@example.com"]["needs_reauth"] is True

            log_p = thome / "test_daemon.log"
            log_p.write_bytes(b"x" * (2 * 1024 * 1024 + 16))
            assert store.rotate_log_if_needed(log_p) is True
            assert Path(f"{log_p}.1").is_file() and not log_p.exists()

    f_plain, m_plain = store.resolve_font_asset("Vazirmatn[wght].woff2")
    f_enc, m_enc = store.resolve_font_asset("Vazirmatn%5Bwght%5D.woff2")
    assert f_plain is not None and f_plain == f_enc and m_plain == "font/woff2"
    assert store.resolve_font_asset("../server.py") == (None, None)
    assert store.resolve_font_asset("..%2Fserver.py") == (None, None)


def test_ag_suite_cdp_and_quota_6_pools():
    wb_vs = {
        "type": "page",
        "url": "vscode-file://vscode-app/workbench.html",
        "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1",
    }
    wb_https = {
        "type": "page",
        "url": "https://127.0.0.1:51234/workbench",
        "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/2",
    }
    ext_web = {
        "type": "page",
        "url": "https://example.com/ai/",
        "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/3",
    }
    sidecar_t = {
        "type": "page",
        "url": "https://127.0.0.1:51234/sidecar/account-suite",
        "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/4",
    }
    daemon_t = {
        "type": "page",
        "url": "https://127.0.0.1:39281/",
        "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/5",
    }
    assert cdp.is_antigravity_workbench_target(wb_vs) is True
    assert cdp.is_antigravity_workbench_target(wb_https, ls_port=51234) is True
    assert cdp.is_antigravity_workbench_target(wb_https, ls_port=59999) is False
    assert cdp.is_antigravity_workbench_target(ext_web) is False
    assert cdp.is_antigravity_workbench_target(sidecar_t) is False
    assert cdp.is_antigravity_workbench_target(daemon_t) is False
    assert cdp.select_workbench_target([ext_web, sidecar_t, wb_vs]) == wb_vs

    groups = [
        {
            "displayName": "Gemini",
            "buckets": [
                {"bucketId": "gemini-5h", "remainingFraction": 0.75, "resetTime": "2030-01-01T05:00:00Z"},
                {"bucketId": "gemini-weekly", "remainingFraction": 0.60, "resetTime": "2030-01-07T00:00:00Z"},
            ],
        },
        {
            "displayName": "Third Party",
            "buckets": [
                {"bucketId": "3p-5h", "remainingFraction": 0.40, "resetTime": "2030-01-01T04:00:00Z"},
                {"bucketId": "3p-weekly", "remainingFraction": 0.50, "resetTime": "2030-01-07T00:00:00Z"},
            ],
        },
    ]
    models = {
        "claude-opus-5-5": {"displayName": "Claude Opus 5.5", "quotaInfo": {"remainingFraction": 0.35}},
        "gemini-pro-orchestrator": {"displayName": "Gemini Pro Orchestrator", "quotaInfo": {"remainingFraction": 0.65}},
    }
    sess, weekly, pools = quota._build_quota_pools(groups, models)
    assert len(pools) == 6
    by_name = {p["name"]: p for p in pools}
    assert list(by_name.keys()) == quota.ORDERED_POOLS
    assert by_name["Gemini 4 Argon"]["remaining_pct"] == 75.0, "Argon must inherit gemini-5h (never 0% bug)"
    assert by_name["Gemini 4 Argon"]["weekly_rem"] == 60.0
    assert by_name["Claude 4.6 (Opus & Sonnet)"]["remaining_pct"] == 35.0
    assert by_name["Gemini 4 Carbon & Orchestrator"]["remaining_pct"] == 65.0

    with quota._QUOTA_LOCK:
        quota._QUOTA_CACHE.clear()
        quota._QUOTA_CACHE["acc1@example.com"] = {
            "data": {"email": "acc1@example.com", "tier": "Google AI Ultra", "session": {"remaining_pct": 92.0}},
            "time": time.time(),
        }
    with mock.patch.object(quota, "fetch_quota_from_language_server", return_value={"email": "acc1@example.com", "session": {"remaining_pct": 92.0}}), \
         mock.patch.object(quota, "_cloudcode_post", side_effect=RuntimeError("offline")), \
         mock.patch.object(store, "load_manifest", return_value={"acc2@example.com": {"email": "acc2@example.com", "remaining_pct": 44.0}}):
        tok2 = json.dumps({"token": {"access_token": "ya29.acc2"}, "email": "acc2@example.com"})
        q2 = quota.fetch_quota_and_tier(tok2, force_refresh=True)
        assert q2["email"] == "acc2@example.com"
        assert q2["session"]["remaining_pct"] == 44.0
        assert quota._QUOTA_CACHE["acc1@example.com"]["data"]["email"] == "acc1@example.com"

    with mock.patch.object(quota, "discover_language_server", return_value=(54321, "csrf-123")), \
         mock.patch.object(quota, "call_ls_rpc", return_value={"userStatus": {"email": "ide@example.com"}}), \
         mock.patch.object(vault, "get_keychain_token", return_value=json.dumps({"email": "vault@example.com"})):
        auth = quota.get_live_ide_auth_state("instance_1", use_cache=False)
        assert set(auth.keys()) == {"ls_online", "ls_port", "live_ide_email", "credential_email", "session_mismatch"}
        assert auth["ls_online"] is True
        assert auth["ls_port"] == 54321
        assert auth["live_ide_email"] == "ide@example.com"
        assert auth["credential_email"] == "vault@example.com"
        assert auth["session_mismatch"] is True

        diag = quota.diagnose_suite("instance_1")
        assert set(diag.keys()) == {
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
        }
        assert diag["fonts"]["ok"] is True


def test_rce_custom_command_blocked_and_http_firewall():
    sig = inspect.signature(migration_engine.run_guarded_task)
    assert list(sig.parameters.keys()) == ["task_name"], f"run_guarded_task must accept only task_name, got {sig}"
    blocked = migration_engine.run_guarded_task("unregistered_rce_task")
    assert blocked.get("success") is False

    for handler_cls in (server.SwitcherHTTPHandler, sync_daemon.QuotaHttpHandler):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        httpd.daemon_threads = True
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        base = f"http://127.0.0.1:{port}"
        try:
            # 1. Evil Origin -> 403 without CORS header
            for method, path, body in (
                ("GET", "/api/state", None),
                ("POST", "/api/switch", b'{"accountKey":"a@b.c"}'),
            ):
                req = urllib.request.Request(
                    base + path,
                    data=body,
                    method=method,
                    headers={"Origin": "https://evil.example", "Content-Type": "application/json"},
                )
                try:
                    NO_PROXY_OPENER.open(req, timeout=2.0)
                    raise AssertionError(f"{handler_cls.__name__} did not block evil Origin on {method} {path}")
                except urllib.error.HTTPError as e:
                    assert e.code == 403
                    assert e.headers.get("Access-Control-Allow-Origin") is None

            # 2. Sec-Fetch-Site: cross-site -> 403
            req_cs = urllib.request.Request(
                base + "/api/switch",
                data=b'{"accountKey":"a@b.c"}',
                method="POST",
                headers={"Sec-Fetch-Site": "cross-site", "Content-Type": "application/json"},
            )
            try:
                NO_PROXY_OPENER.open(req_cs, timeout=2.0)
                raise AssertionError("Failed to block Sec-Fetch-Site: cross-site")
            except urllib.error.HTTPError as e:
                assert e.code == 403

            # 3. POST without Content-Type: application/json -> 403
            req_ct = urllib.request.Request(
                base + "/api/settings",
                data=b"theme=cyber",
                method="POST",
                headers={"Content-Type": "text/plain"},
            )
            try:
                NO_PROXY_OPENER.open(req_ct, timeout=2.0)
                raise AssertionError("Failed to block POST with text/plain Content-Type")
            except urllib.error.HTTPError as e:
                assert e.code == 403

            # 4. POST /api/task_run_guarded strips custom_command
            req_rce = urllib.request.Request(
                base + "/api/task_run_guarded",
                data=json.dumps({"taskName": "nonexistent_task", "custom_command": "echo PWNED"}).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with NO_PROXY_OPENER.open(req_rce, timeout=2.0) as resp:
                rce_data = json.loads(resp.read().decode("utf-8"))
                assert rce_data.get("success") is False

            # 5. GET /api/state with vscode-file:// Origin -> 200, echoed Origin, zero token_file, <100ms cached
            req_st = urllib.request.Request(
                base + "/api/state",
                headers={"Origin": "vscode-file://vscode-app"},
            )
            with NO_PROXY_OPENER.open(req_st, timeout=3.0) as resp:
                assert resp.status == 200
                assert resp.headers.get("Access-Control-Allow-Origin") == "vscode-file://vscode-app"
                raw_state = resp.read().decode("utf-8")
                assert "token_file" not in raw_state
                st_data = json.loads(raw_state)
                expected_keys = {
                    "activeAccount",
                    "savedAccounts",
                    "instanceId",
                    "projects",
                    "conversations",
                    "tasks",
                    "allowedConversations",
                    "runningInstances",
                    "runningAccounts",
                    "cdpConnected",
                    "cdpTargets",
                    "authState",
                }
                assert expected_keys.issubset(set(st_data.keys()))

            t0 = time.perf_counter()
            with NO_PROXY_OPENER.open(req_st, timeout=2.0) as resp:
                assert resp.status == 200
                resp.read()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            assert elapsed_ms < 100.0, f"{handler_cls.__name__} cached /api/state took {elapsed_ms:.1f}ms (>100ms)"

            # 6. GET /fonts/Vazirmatn%5Bwght%5D.woff2 & /fonts/Vazirmatn[wght].woff2 -> 200, traversal -> 403
            for f_url in ("/fonts/Vazirmatn%5Bwght%5D.woff2", "/fonts/Vazirmatn[wght].woff2"):
                with NO_PROXY_OPENER.open(base + f_url, timeout=2.0) as resp:
                    assert resp.status == 200
                    assert resp.headers.get("Content-Type") == "font/woff2"
                    assert resp.headers.get("Access-Control-Allow-Origin") == "*"
                    assert len(resp.read()) > 50000

            try:
                NO_PROXY_OPENER.open(base + "/fonts/..%2Fserver.py", timeout=2.0)
                raise AssertionError("Font path traversal was not blocked")
            except urllib.error.HTTPError as e:
                assert e.code == 403
        finally:
            httpd.shutdown()
            httpd.server_close()


def test_sidecar_mcp_cli_and_ui_contracts():
    # Sidecar self-test
    res_sc = subprocess.run(
        ["node", str(ROOT / "plugin" / "sidecars" / "account-suite" / "main.mjs"), "--test"],
        capture_output=True,
        text=True,
    )
    assert res_sc.returncode == 0, f"sidecar main.mjs --test failed: {res_sc.stdout} {res_sc.stderr}"

    # UI files check for needsAuth and postJson
    for ui_rel in ("app/app.js", "plugin/sidecars/account-suite/index.html", "antigravity_quota_injector.js"):
        txt = (ROOT / ui_rel).read_text(encoding="utf-8")
        assert "acc.needs_reauth || acc.has_token === false" in txt, f"Missing needs_reauth || has_token === false in {ui_rel}"
        assert "const needsAuth =" in txt, f"Missing const needsAuth in {ui_rel}"
        assert "!acc.token_file" not in txt, f"Forbidden !acc.token_file found in {ui_rel}"
        assert "postJson" in txt, f"Missing postJson in {ui_rel}"

    # MCP self-test
    res_mcp = subprocess.run(
        [sys.executable, str(ROOT / "mcp_server.py"), "--test"],
        capture_output=True,
        text=True,
    )
    assert res_mcp.returncode == 0, f"mcp_server.py --test failed: {res_mcp.stdout} {res_mcp.stderr}"

    # CLI --doctor mock test
    fake_diag = {
        "ok": True,
        "version": "3.0.0",
        "system": "linux",
        "auth_state": {
            "ls_online": True,
            "ls_port": 51111,
            "live_ide_email": "dev@example.com",
            "credential_email": "dev@example.com",
            "session_mismatch": False,
        },
        "cdp": {
            "port": 9222,
            "workbench_ready": True,
            "devtools_port_file": "/tmp/DevToolsActivePort",
            "devtools_port_file_exists": True,
            "remote_debugging_flag_required": False,
        },
        "sync_daemon": {"port": 39281, "listening": True, "healthy": True},
        "control_center": {"port": 39285, "listening": False},
        "fonts": {"ok": True, "dir": str(ROOT / "assets" / "fonts"), "available": list(store.REQUIRED_FONTS), "missing": []},
        "accounts": {"saved_count": 1, "needs_reauth_count": 0, "active_email": "dev@example.com"},
        "issues": [],
    }
    with mock.patch.object(cli.quota, "diagnose_suite", return_value=fake_diag):
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            assert cli.cmd_doctor(as_json=True) == 0
        parsed_doc = json.loads(buf.getvalue())
        assert parsed_doc["ok"] is True and parsed_doc["auth_state"]["ls_port"] == 51111

        buf_txt = io.StringIO()
        with mock.patch("sys.stdout", buf_txt):
            assert cli.cmd_doctor(as_json=False) == 0
        assert "Doctor Diagnostics" in buf_txt.getvalue()


def test_daemon_low_cpu_cdp_filter_and_recovery_guards():
    import sync_daemon
    assert sync_daemon.QuotaHttpHandler.timeout == 5.0
    assert server.SwitcherHTTPHandler.timeout == 5.0

    class FakeProc:
        def __init__(self, pid, name, cmdline):
            self.info = {"pid": pid, "name": name}
            self._cmdline = cmdline
            self.called_net = False

        def cmdline(self):
            return self._cmdline

        def net_connections(self, kind="tcp"):
            self.called_net = True
            return []

    no_cdp_proc = FakeProc(101, "Antigravity.exe", ["C:\\Program Files\\Antigravity\\Antigravity.exe"])
    child_proc = FakeProc(102, "Antigravity.exe", ["Antigravity.exe", "--type=renderer", "--remote-debugging-port=0"])
    other_proc = FakeProc(103, "explorer.exe", ["explorer.exe"])
    fake_psutil = type("FakePsutil", (), {"process_iter": staticmethod(lambda attrs=None: [no_cdp_proc, child_proc, other_proc])})
    with mock.patch.dict(sys.modules, {"psutil": fake_psutil}):
        assert cdp.discover_live_cdp_ports() == {}
    assert no_cdp_proc.called_net is False, "must skip net_connections when --remote-debugging-port is absent"
    assert child_proc.called_net is False

    # Stale unchanged DevToolsActivePort must not be re-probed within TTL unless mtime changes
    cdp.invalidate_devtools_cache()
    with tempfile.TemporaryDirectory() as tmp:
        pf = Path(tmp) / "DevToolsActivePort"
        pf.write_text("59998\n/devtools/browser\n", encoding="utf-8")
        with mock.patch.object(cdp, "is_valid_cdp_port", return_value=False) as m_probe:
            assert cdp._read_valid_port_file(pf) is None
            assert cdp._read_valid_port_file(pf) is None
            assert m_probe.call_count == 1
    cdp.invalidate_devtools_cache()

    # Recover helper must do nothing when daemon /health reports 200 OK
    with mock.patch.object(sync_daemon, "_is_daemon_http_healthy", return_value=True):
        sync_daemon._recover_unhealthy_daemon()

    font_data = sync_daemon._load_bundled_font_data()
    for family in ("Vazirmatn", "Estedad", "Outfit"):
        assert family in font_data and font_data[family].startswith("data:font/woff2;base64,"), family

    injector_js = (ROOT / "antigravity_quota_injector.js").read_text(encoding="utf-8")
    assert "window.__antigravity_font_data" in injector_js

    from legacy.chatgpt import chatgpt_cdp_daemon
    with mock.patch.object(chatgpt_cdp_daemon, "expected_codex_executable", side_effect=AssertionError("should not probe closed port")):
        assert chatgpt_cdp_daemon.is_owned_codex_port(59997) is False


if __name__ == "__main__":
    test_install_ps1_pure_ascii_no_bom_and_wrapped()
    test_main_branch_urls_and_file_parities()
    test_ag_suite_vault_and_store_contracts()
    test_ag_suite_cdp_and_quota_6_pools()
    test_rce_custom_command_blocked_and_http_firewall()
    test_sidecar_mcp_cli_and_ui_contracts()
    test_daemon_low_cpu_cdp_filter_and_recovery_guards()
    print("ALL V3 SUITE TESTS PASSED!")
