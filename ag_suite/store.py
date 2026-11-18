# -*- coding: utf-8 -*-
"""Atomic manifest/settings persistence, client sanitization, log rotation, and font asset resolution."""

import copy
import json
import os
import tempfile
import urllib.parse
from pathlib import Path

from . import vault

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FONTS = (
    "Vazirmatn[wght].woff2",
    "Estedad[wght].woff2",
    "Outfit[wght].woff2",
)

FONT_MIME_TYPES = {
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
}

DEFAULT_USER_SETTINGS = {
    "theme": "cyber",
    "mode": "remaining",
    "fullTheming": True,
    "privacyMode": False,
    "fontEn": "default",
    "fontFa": "Vazirmatn",
    "customImportedFonts": [],
    "rtl": {
        "enabled": True,
        "align": "right",
        "direction": "rtl",
        "font": "Vazirmatn",
    },
    "lang": "fa",
}


def atomic_write_text(path: Path | str, content: str) -> bool:
    """Atomically write UTF-8 text via sibling temporary file and os.replace."""
    target = Path(path)
    tmp_path = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, target)
        return True
    except Exception:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        return False


def atomic_write_json(path: Path | str, data) -> bool:
    """Atomically serialize data to JSON on disk."""
    return atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def _read_json_dict(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_manifest() -> dict:
    """Load saved accounts manifest from `~/.gemini/accounts/manifest.json`."""
    paths = vault.get_platform_paths()
    paths["accounts_dir"].mkdir(parents=True, exist_ok=True)
    return _read_json_dict(paths["manifest_path"])


def save_manifest(manifest: dict) -> bool:
    """Persist saved accounts manifest atomically."""
    paths = vault.get_platform_paths()
    paths["accounts_dir"].mkdir(parents=True, exist_ok=True)
    return atomic_write_json(paths["manifest_path"], manifest if isinstance(manifest, dict) else {})


def read_account_token(account_key: str, manifest: dict | None = None) -> str | None:
    """Read raw token content for a manifest account key safely from disk."""
    m = manifest if manifest is not None else load_manifest()
    entry = m.get(account_key) if isinstance(m, dict) else None
    candidates: list[Path] = []
    if isinstance(entry, dict) and entry.get("token_file"):
        candidates.append(Path(entry["token_file"]))
    safe_name = "".join(c if c.isalnum() or c in ("@", ".", "_", "-") else "_" for c in str(account_key or ""))
    if safe_name:
        candidates.append(vault.get_platform_paths()["accounts_dir"] / f"{safe_name}.token")
    for p in candidates:
        if p.is_file():
            try:
                val = p.read_text(encoding="utf-8", errors="ignore").strip()
                if val:
                    return val
            except Exception:
                pass
    return None


def sanitize_manifest_for_client(manifest: dict | None = None) -> dict:
    """Strip local secret paths/tokens and normalize has_token + needs_reauth flags."""
    source = manifest if manifest is not None else load_manifest()
    if not isinstance(source, dict):
        return {}
    sanitized: dict[str, dict] = {}
    for key, entry in source.items():
        if not isinstance(entry, dict):
            continue
        email = str(entry.get("email") or key)
        tf = entry.get("token_file")
        raw_tok = None
        if tf and os.path.isfile(tf):
            try:
                raw_tok = Path(tf).read_text(encoding="utf-8", errors="ignore").strip()
            except Exception:
                raw_tok = None
        if not raw_tok:
            raw_tok = read_account_token(key, {key: entry})
        acc_tok, ref_tok = vault.parse_token_payload(raw_tok)
        has_token = bool(raw_tok and (acc_tok or ref_tok))
        needs_reauth = bool(entry.get("needs_reauth", False) or not has_token)

        sanitized[key] = {
            "label": entry.get("label") or email,
            "name": entry.get("name") or (email.split("@")[0].split(".")[0].capitalize() if "@" in email else email),
            "avatar": entry.get("avatar") or "",
            "email": email,
            "tier": entry.get("tier") or "Google AI Pro",
            "tier_code": entry.get("tier_code") or "pro",
            "remaining_pct": float(entry.get("remaining_pct", 100.0)),
            "weekly_remaining_pct": float(entry.get("weekly_remaining_pct", 100.0)),
            "weekly_resets_in": entry.get("weekly_resets_in") or "Ready",
            "has_token": has_token,
            "needs_reauth": needs_reauth,
            "saved_at": entry.get("saved_at") or "",
            "instance_id": entry.get("instance_id"),
        }
    return sanitized


def resolve_account_key(target: str | None, manifest: dict | None = None) -> str | None:
    """Fuzzy-resolve account key by exact key, email, display name, instance_id, or substring."""
    if not target:
        return None
    m = manifest if manifest is not None else load_manifest()
    if not isinstance(m, dict) or not m:
        return None
    clean = str(target).strip().lower()
    if not clean:
        return None

    for k in m:
        if str(k).lower() == clean:
            return k
    for k, v in m.items():
        if not isinstance(v, dict):
            continue
        for field in ("email", "name", "instance_id"):
            if str(v.get(field) or "").strip().lower() == clean:
                return k
    for k, v in m.items():
        em = str(v.get("email") or "").lower() if isinstance(v, dict) else ""
        if clean in str(k).lower() or (em and clean in em):
            return k
    return None


def get_primary_account(manifest: dict | None = None) -> str:
    """Return the primary account identifier without hardcoded user credentials."""
    m = manifest if manifest is not None else load_manifest()
    if isinstance(m, dict) and m:
        first_key = next(iter(m.keys()))
        first_val = m[first_key]
        if isinstance(first_val, dict) and first_val.get("email"):
            return str(first_val["email"])
        return str(first_key)
    tok = vault.get_keychain_token()
    if tok:
        em = vault.extract_token_email(tok, check_manifest=False)
        if em:
            return em
    return "primary_account"


def get_secondary_account(manifest: dict | None = None) -> str:
    """Return the secondary account identifier from manifest if configured."""
    m = manifest if manifest is not None else load_manifest()
    if isinstance(m, dict) and len(m) > 1:
        keys = list(m.keys())
        sec_val = m[keys[1]]
        if isinstance(sec_val, dict) and sec_val.get("email"):
            return str(sec_val["email"])
        return str(keys[1])
    return "secondary_account"


def is_account2(email: str | None, manifest: dict | None = None) -> bool:
    """Return True if account alias or email maps to a non-primary / secondary slot."""
    if not email:
        return False
    norm = str(email).strip().lower()
    if norm in ("instance_2", "secondary_account") or "account2" in norm:
        return True
    m = manifest if manifest is not None else load_manifest()
    sec = get_secondary_account(m).lower()
    if sec != "secondary_account" and norm == sec:
        return True
    prim = get_primary_account(m).lower()
    if prim != "primary_account" and "@" in prim and "@" in norm:
        return norm != prim
    return False


def write_active_instance_account(instance_id: str, email: str) -> None:
    """Persist active_<instance_id>.txt atomically."""
    if not instance_id or not email:
        return
    clean_inst = vault._normalize_instance_id(instance_id)
    target = vault.get_platform_paths()["accounts_dir"] / f"active_{clean_inst}.txt"
    atomic_write_text(target, str(email).strip())


def update_app_storage_account(
    email: str,
    quota_data: dict | None = None,
    instance_id: str = "instance_1",
) -> None:
    """Synchronize Antigravity's per-instance app_storage.json with account identity & quota."""
    if not email:
        return
    paths = vault.get_platform_paths(instance_id)
    st_path = paths["storage_path"]
    s_data = _read_json_dict(st_path)
    s_data["antigravity:account_email"] = email
    s_data["agy.onboarding.lastLoginUsername"] = email
    s_data["jetski.onboarding.lastLoginUsername"] = email
    if quota_data is not None:
        s_data["antigravity:active_quota"] = json.dumps(quota_data, ensure_ascii=False)
    atomic_write_json(st_path, s_data)


def get_instance_active_account(instance_id: str = "instance_1", is_dual_launching: bool = False) -> str:
    """Resolve active Google email for primary or secondary Antigravity instances."""
    norm_inst = vault._normalize_instance_id(instance_id)
    paths = vault.get_platform_paths(norm_inst)
    saved_manifest = load_manifest()

    if norm_inst != "instance_1":
        f_inst = paths["accounts_dir"] / f"active_{norm_inst}.txt"
        if f_inst.is_file():
            try:
                acc = f_inst.read_text(encoding="utf-8").strip()
                if acc and (not saved_manifest or acc in saved_manifest):
                    return acc
            except Exception:
                pass

        s_data = _read_json_dict(paths["storage_path"])
        for field in ("antigravity:account_email", "agy.onboarding.lastLoginUsername", "jetski.onboarding.lastLoginUsername"):
            acc = s_data.get(field)
            if acc and (not saved_manifest or acc in saved_manifest):
                return str(acc)

        for email, data in saved_manifest.items():
            if isinstance(data, dict) and data.get("instance_id") == norm_inst:
                return str(data.get("email") or email)

        digits = "".join(c for c in norm_inst if c.isdigit())
        if digits.isdigit():
            idx = int(digits) - 1
            keys = list(saved_manifest.keys())
            if 0 <= idx < len(keys):
                return str(keys[idx])

        return get_secondary_account(saved_manifest)

    if not is_dual_launching:
        tok = vault.get_keychain_token()
        if tok:
            token_em = vault.extract_token_email(tok, check_manifest=True)
            if token_em:
                write_active_instance_account("instance_1", token_em)
                st_data = _read_json_dict(paths["storage_path"])
                if st_data.get("antigravity:account_email") != token_em:
                    update_app_storage_account(token_em, instance_id="instance_1")
                return token_em

    f_inst1 = paths["accounts_dir"] / "active_instance_1.txt"
    if f_inst1.is_file():
        try:
            acc = f_inst1.read_text(encoding="utf-8").strip()
            if acc:
                return acc
        except Exception:
            pass

    st_data = _read_json_dict(paths["storage_path"])
    for field in ("antigravity:account_email", "agy.onboarding.lastLoginUsername", "jetski.onboarding.lastLoginUsername"):
        if st_data.get(field):
            return str(st_data[field])

    return get_primary_account(saved_manifest)


def _merge_settings_dict(base: dict, patch: dict) -> dict:
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k] = _merge_settings_dict(dict(base[k]), v)
        else:
            base[k] = copy.deepcopy(v)
    return base


def load_user_settings(instance_id: str | None = None, account_email: str | None = None) -> dict:
    """Load deep-copied user settings with account and instance overrides."""
    base = copy.deepcopy(DEFAULT_USER_SETTINGS)
    saved = _read_json_dict(vault.get_platform_paths()["user_settings_path"])
    if not saved:
        return base

    top_patch = {k: v for k, v in saved.items() if k not in ("instances", "accounts")}
    _merge_settings_dict(base, top_patch)

    accounts_map = saved.get("accounts")
    if account_email and isinstance(accounts_map, dict):
        acc_patch = accounts_map.get(account_email) or accounts_map.get(str(account_email).lower())
        if isinstance(acc_patch, dict):
            _merge_settings_dict(base, acc_patch)

    instances_map = saved.get("instances")
    if instance_id and isinstance(instances_map, dict):
        inst_patch = instances_map.get(instance_id)
        if isinstance(inst_patch, dict):
            _merge_settings_dict(base, inst_patch)

    return base


def save_user_settings(
    patch: dict,
    instance_id: str | None = None,
    account_email: str | None = None,
) -> tuple[bool, dict | str]:
    """Atomically persist user settings while deep-merging nested dicts."""
    try:
        settings_path = vault.get_platform_paths()["user_settings_path"]
        raw = _read_json_dict(settings_path)
        if not isinstance(raw.get("instances"), dict):
            raw["instances"] = {}
        if not isinstance(raw.get("accounts"), dict):
            raw["accounts"] = {}

        if isinstance(patch, dict):
            instance_id = instance_id or patch.get("instance_id")
            account_email = account_email or patch.get("account")
            clean_patch = {k: v for k, v in patch.items() if k not in ("instance_id", "account")}
        else:
            clean_patch = {}

        if instance_id:
            inst_cur = raw["instances"].get(instance_id)
            inst_cur = dict(inst_cur) if isinstance(inst_cur, dict) else {}
            raw["instances"][instance_id] = _merge_settings_dict(inst_cur, clean_patch)

        if account_email:
            acc_cur = raw["accounts"].get(account_email)
            acc_cur = dict(acc_cur) if isinstance(acc_cur, dict) else {}
            raw["accounts"][account_email] = _merge_settings_dict(acc_cur, clean_patch)

        _merge_settings_dict(raw, clean_patch)
        if not atomic_write_json(settings_path, raw):
            return False, "Failed to write user_settings.json"
        return True, load_user_settings(instance_id=instance_id, account_email=account_email)
    except Exception as exc:
        return False, str(exc)


def rotate_log_if_needed(log_path: str | Path, max_bytes: int = 2 * 1024 * 1024) -> bool:
    """Rotate a log file to `<log_path>.1` when size reaches max_bytes."""
    target = Path(log_path)
    try:
        if not target.is_file() or target.stat().st_size < max_bytes:
            return False
        backup = Path(f"{target}.1")
        os.replace(target, backup)
        return True
    except Exception:
        return False


def get_font_search_dirs(extra_dirs: list[Path] | None = None) -> list[Path]:
    """Return ordered list of existing font asset directories."""
    paths = vault.get_platform_paths()
    candidates = [
        REPO_ROOT / "assets" / "fonts",
        paths["bin_dir"] / "assets" / "fonts",
        *(extra_dirs or []),
    ]
    out: list[Path] = []
    seen: set[str] = set()
    for d in candidates:
        key = str(d)
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def resolve_font_asset(
    raw_name: str,
    extra_dirs: list[Path] | None = None,
) -> tuple[Path | None, str | None]:
    """Safely resolve URL-encoded or plain font filenames inside bundled font directories."""
    decoded = urllib.parse.unquote(str(raw_name or "")).strip().lstrip("/")
    if decoded.lower().startswith("fonts/"):
        decoded = decoded[6:]
    if not decoded or "\x00" in decoded or "/" in decoded or "\\" in decoded or ".." in decoded:
        return None, None

    ext = Path(decoded).suffix.lower()
    mime = FONT_MIME_TYPES.get(ext)
    if not mime:
        return None, None

    for font_dir in get_font_search_dirs(extra_dirs=extra_dirs):
        if not font_dir.is_dir():
            continue
        base_resolved = font_dir.resolve()
        candidate = (base_resolved / decoded).resolve()
        if candidate.parent == base_resolved and candidate.is_file():
            return candidate, mime

    return None, None
