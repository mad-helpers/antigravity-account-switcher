"""Regression & v3 bundle verification for antigravity_quota_injector.js and sync_daemon injection."""
import pathlib
import subprocess
import sys
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import migration_engine
import server
import sync_daemon

REQUIRED_INJECTOR_MODULES = (
    "00_guard_and_boot.js",
    "01_fonts_and_styles.js",
    "02_smart_rtl.js",
    "03_quota_state_and_ipc.js",
    "04_hud_popover.js",
    "05_switcher_modal_and_init.js",
)

RENDERED_SELECTORS = (
    "aqm-pop-lang-btn",
    "aqm-pop-restart-btn",
    "aqm-refresh-btn",
    "aqm-privacy-btn",
    "aqm-close-btn",
    "aqm-drag-handle",
    "aqm-mode-rem-btn",
    "aqm-mode-used-btn",
    "data-switch-quick",
    "aqm-account-switcher-trigger",
    "aqm-tab-btn-quota",
    "aqm-tab-btn-fonts",
    "aqm-tab-btn-rtl",
    "aqm-theme-dropdown",
    "data-theme-id",
    "data-font-en",
    "data-font-fa",
    "aqm-toggle-import-btn",
    "aqm-import-file",
    "aqm-import-name",
    "aqm-import-url",
    "aqm-import-submit-btn",
    "data-delete-imported-font",
    "aqm-rtl-toggle-row",
    "aqm-rtl-force-row",
    "aqm-rtl-at-row",
    "aqm-rtl-lh-slider",
    "aqm-rtl-fs-slider",
    "aqm-sw-modal-close",
    "aqm-lang-toggle-btn",
    "aqm-sw-restart-app-btn",
    "aqm-sw-autorestart-chk",
    "aqm-tab-btn-accounts",
    "aqm-tab-btn-projects",
)

UNRENDERED_DEAD_STUBS = (
    "aqm-theme-menu-trigger",
    "aqm-drawer-close-btn",
    "aqm-full-theme-row",
)


class Boom:
    @staticmethod
    def get_allowed_conversations(_):
        raise FileExistsError("dangling junction")


def test_safe_allowed_convs_swallows_store_errors():
    assert sync_daemon._safe_allowed_convs(Boom, "a@b.c") == []


def test_no_undefined_names():
    assert hasattr(migration_engine, "platform") and hasattr(server, "urllib")


def test_bundle_reproducibility_and_modules():
    for mod in REQUIRED_INJECTOR_MODULES:
        p = ROOT / "src" / "injector" / mod
        assert p.is_file() and p.stat().st_size > 100, f"Missing injector module: {mod}"
    res = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_bundle.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"build_bundle --check failed: {res.stdout} {res.stderr}"


def test_compiled_injector_contracts():
    code = (ROOT / "antigravity_quota_injector.js").read_text(encoding="utf-8")
    assert "window.top !== window.self" in code
    assert "/sidecar" in code
    assert "3.0.0" in code
    assert "acc.needs_reauth || acc.has_token === false" in code
    assert "const needsAuth =" in code
    assert "!acc.token_file" not in code
    assert "function postJson(" in code
    assert "'Content-Type': 'application/json'" in code or '"Content-Type": "application/json"' in code
    assert "__aqm_rtl_observer" in code
    assert "detectElementDir" in code
    assert "unicode-bidi: plaintext" in code
    assert "setRangeText" in code

    for sel in RENDERED_SELECTORS:
        assert sel in code, f"Missing mandatory rendered selector in injector: {sel}"
    for dead in UNRENDERED_DEAD_STUBS:
        assert dead not in code, f"Dead unrendered stub selector still present: {dead}"


def test_get_injector_script_sanitizes_and_skips_empty(tmp_path=None):
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        empty_js = pathlib.Path(td) / "empty.js"
        empty_js.write_text("   \n  ", encoding="utf-8")
        with mock.patch.object(sync_daemon, "INJECTOR_PATH", empty_js):
            assert sync_daemon.get_injector_script() == ""

        fake_manifest = {
            "dev@example.com": {
                "email": "dev@example.com",
                "token_file": "/secret/path/dev.token",
                "remaining_pct": 85.0,
            }
        }
        with mock.patch.object(sync_daemon.store, "load_manifest", return_value=fake_manifest), \
             mock.patch.object(sync_daemon, "get_account_profile_data", return_value={"email": "dev@example.com", "token_file": "/secret/path/dev.token"}):
            script = sync_daemon.get_injector_script(instance_id="instance_1", account_email="dev@example.com")
            assert script
            assert "/secret/path/dev.token" not in script


if __name__ == "__main__":
    test_safe_allowed_convs_swallows_store_errors()
    test_no_undefined_names()
    test_bundle_reproducibility_and_modules()
    test_compiled_injector_contracts()
    test_get_injector_script_sanitizes_and_skips_empty()
    print("ok")
