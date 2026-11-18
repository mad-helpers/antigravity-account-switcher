# -*- coding: utf-8 -*-
"""Cross-platform OS credential vault, platform paths, and OAuth token management."""

import base64
import copy
import datetime
import json
import os
import platform
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

_CID_CODES = [
    49, 48, 55, 49, 48, 48, 54, 48, 54, 48, 53, 57, 49, 45, 116, 109, 104,
    115, 115, 105, 110, 50, 104, 50, 49, 108, 99, 114, 101, 50, 51, 53, 118,
    116, 111, 108, 111, 106, 104, 52, 103, 52, 48, 51, 101, 112, 46, 97, 112,
    112, 115, 46, 103, 111, 111, 103, 108, 101, 117, 115, 101, 114, 99, 111,
    110, 116, 101, 110, 116, 46, 99, 111, 109,
]
_SEC_CODES = [
    71, 79, 67, 83, 80, 88, 45, 75, 53, 56, 70, 87, 82, 52, 56, 54, 76, 100,
    76, 74, 49, 109, 76, 66, 56, 115, 88, 67, 52, 122, 54, 113, 68, 65, 102,
]

OAUTH_CLIENT_ID = "".join(chr(x) for x in _CID_CODES)
OAUTH_CLIENT_SECRET = "".join(chr(x) for x in _SEC_CODES)

ANTIGRAVITY_OAUTH_SCOPES = (
    "openid email profile "
    "https://www.googleapis.com/auth/cloud-platform "
    "https://www.googleapis.com/auth/userinfo.email "
    "https://www.googleapis.com/auth/userinfo.profile "
    "https://www.googleapis.com/auth/aicode "
    "https://www.googleapis.com/auth/cclog "
    "https://www.googleapis.com/auth/experimentsandconfigs"
)

CREDENTIAL_TARGETS = ("gemini:antigravity", "gemini", "antigravity")


def get_current_system() -> str:
    """Return normalized OS identifier: 'windows', 'macos', or 'linux'."""
    sys_name = platform.system().lower()
    if "darwin" in sys_name:
        return "macos"
    if "windows" in sys_name:
        return "windows"
    return "linux"


def _normalize_instance_id(instance_id: str | None) -> str:
    raw = str(instance_id or "").strip()
    if not raw or raw.lower() in ("instance_1", "instance1", "default"):
        return "instance_1"
    m = re.search(r"(\d+)$", raw)
    if m:
        num = int(m.group(1))
        return "instance_1" if num <= 1 else f"instance_{num}"
    return raw.lower().replace("-", "_")


def normalize_instance_folder(instance_id: str | None = None) -> str:
    """Map an instance identifier to Antigravity's OS profile folder name."""
    norm = _normalize_instance_id(instance_id)
    if norm == "instance_1":
        return "Antigravity"
    if norm.startswith("instance_"):
        return f"Antigravity-Instance{norm.split('_', 1)[1]}"
    clean = str(instance_id).strip()
    if clean.lower().startswith("antigravity"):
        return clean
    return f"Antigravity-{clean}"


def get_platform_paths(instance_id: str | None = None) -> dict[str, Path]:
    """Resolve OS-specific Antigravity and suite storage paths dynamically."""
    home = Path.home()
    sys_name = get_current_system()
    if sys_name == "windows":
        appdata_root = Path(os.getenv("APPDATA", str(home / "AppData" / "Roaming")))
    elif sys_name == "macos":
        appdata_root = home / "Library" / "Application Support"
    else:
        appdata_root = home / ".config"

    norm_inst = _normalize_instance_id(instance_id)
    profile_dir = appdata_root / normalize_instance_folder(norm_inst)
    gemini_dir = home / ".gemini"
    antigravity_dir = gemini_dir / "antigravity"
    accounts_dir = gemini_dir / "accounts"
    quota_name = "active_quota.json" if norm_inst == "instance_1" else f"active_quota_{norm_inst}.json"

    return {
        "home": home,
        "appdata_root": appdata_root,
        "profile_dir": profile_dir,
        "storage_path": profile_dir / "app_storage.json",
        "devtools_port_path": profile_dir / "DevToolsActivePort",
        "gemini_dir": gemini_dir,
        "antigravity_dir": antigravity_dir,
        "bin_dir": antigravity_dir / "bin",
        "accounts_dir": accounts_dir,
        "manifest_path": accounts_dir / "manifest.json",
        "active_quota_path": antigravity_dir / quota_name,
        "user_settings_path": antigravity_dir / "user_settings.json",
        "active_cred_path": accounts_dir / ".active_credential.token",
    }


def _b64_json_decode(raw_b64: str) -> dict | None:
    padded = raw_b64.strip()
    padded += "=" * (-len(padded) % 4)
    for decoder in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            obj = json.loads(decoder(padded).decode("utf-8"))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    return None


def decode_token_dict(token_str: str | dict | None) -> dict | None:
    """Decode raw JSON, go-keyring-base64, base64 JSON, or bare access token into a dict."""
    if not token_str:
        return None
    if isinstance(token_str, dict):
        return copy.deepcopy(token_str)

    raw = str(token_str).strip().lstrip("\ufeff")
    if not raw:
        return None

    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    if "go-keyring-base64:" in raw:
        return _b64_json_decode(raw.split("go-keyring-base64:", 1)[1])

    decoded = _b64_json_decode(raw)
    if decoded is not None:
        return decoded

    if raw.startswith("ya29."):
        return {"token": {"access_token": raw}}

    return None


def parse_token_payload(token_str: str | dict | None) -> tuple[str | None, str | None]:
    """Safely extract (access_token, refresh_token) from any supported token format."""
    data = decode_token_dict(token_str)
    if not data:
        return None, None
    t_obj = data.get("token", data)
    if not isinstance(t_obj, dict):
        return None, None
    return t_obj.get("access_token"), t_obj.get("refresh_token")


def normalize_token_payload(token: str | dict) -> tuple[str, dict | None]:
    """Normalize token structure (`auth_method`, Z expiry suffix) to canonical JSON."""
    payload = decode_token_dict(token)
    if payload is None:
        return str(token or "").strip(), None
    payload.setdefault("auth_method", "consumer")
    t_obj = payload.get("token", payload)
    if isinstance(t_obj, dict) and isinstance(t_obj.get("expiry"), str):
        if "+00:00" in t_obj["expiry"]:
            t_obj["expiry"] = t_obj["expiry"].replace("+00:00", "Z")
    return json.dumps(payload, ensure_ascii=False), payload


def _win32_credential_struct():
    import ctypes
    from ctypes import wintypes

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    return ctypes, wintypes, CREDENTIAL


def get_windows_credential() -> str | None:
    """Read active credential blob from Windows Credential Manager via advapi32.dll."""
    if get_current_system() != "windows":
        return None
    ctypes, wintypes, CREDENTIAL = _win32_credential_struct()
    pcred_type = ctypes.POINTER(CREDENTIAL)
    cred_read = ctypes.windll.advapi32.CredReadW
    cred_read.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(pcred_type)]
    cred_read.restype = wintypes.BOOL
    cred_free = ctypes.windll.advapi32.CredFree
    cred_free.argtypes = [ctypes.c_void_p]

    for target in CREDENTIAL_TARGETS:
        pcred = pcred_type()
        if not cred_read(target, 1, 0, ctypes.byref(pcred)):
            continue
        try:
            cred = pcred.contents
            raw_bytes = bytes(cred.CredentialBlob[: cred.CredentialBlobSize])
            val = raw_bytes.decode("utf-8", errors="ignore").rstrip("\x00").strip()
            if val.startswith("go-keyring-base64:") or decode_token_dict(val):
                return val
            val_u16 = raw_bytes.decode("utf-16le", errors="ignore").rstrip("\x00").strip()
            if val_u16.startswith("go-keyring-base64:") or decode_token_dict(val_u16):
                return val_u16
            if val:
                return val
        finally:
            cred_free(pcred)
    return None


def _run_hidden(cmd: list[str], input_text: str | None = None, timeout: float = 5.0):
    kwargs = {"capture_output": True, "text": True, "encoding": "utf-8", "errors": "ignore", "timeout": timeout}
    if input_text is not None:
        kwargs["input"] = input_text
    if get_current_system() == "windows":
        import subprocess as _sp
        kwargs["creationflags"] = getattr(_sp, "CREATE_NO_WINDOW", 0x08000000)
    return subprocess.run(cmd, **kwargs)


def _read_macos_keychain() -> str | None:
    cmds = (
        ["security", "find-generic-password", "-s", "gemini", "-a", "antigravity", "-w"],
        ["security", "find-generic-password", "-s", "antigravity", "-w"],
    )
    for cmd in cmds:
        try:
            res = _run_hidden(cmd)
            out = (res.stdout or "").strip()
            if res.returncode == 0 and out and (out.startswith("go-keyring-base64:") or out.startswith("{") or decode_token_dict(out)):
                return out
        except Exception:
            pass
    return None


def get_keychain_token() -> str | None:
    """Read active Antigravity token across Windows, macOS Keychain, and Linux keyring/file."""
    sys_name = get_current_system()
    if sys_name == "windows":
        return get_windows_credential()
    if sys_name == "macos":
        return _read_macos_keychain()

    if shutil.which("secret-tool"):
        try:
            res = _run_hidden(["secret-tool", "lookup", "service", "gemini", "account", "antigravity"])
            out = (res.stdout or "").strip()
            if res.returncode == 0 and out:
                return out
        except Exception:
            pass

    cred_file = get_platform_paths()["active_cred_path"]
    if cred_file.is_file():
        try:
            val = cred_file.read_text(encoding="utf-8").strip()
            return val or None
        except Exception:
            pass
    return None


def write_keychain_token(token: str | dict) -> bool:
    """Write normalized credential token to the OS credential store."""
    if not token:
        return False
    raw_in = token.strip() if isinstance(token, str) else ""
    token_str, payload = normalize_token_payload(token)
    if not token_str:
        return False

    sys_name = get_current_system()
    if sys_name == "windows":
        ctypes, wintypes, CREDENTIAL = _win32_credential_struct()
        cred_write = ctypes.windll.advapi32.CredWriteW
        cred_write.argtypes = [ctypes.POINTER(CREDENTIAL), wintypes.DWORD]
        cred_write.restype = wintypes.BOOL

        raw_bytes = token_str.encode("utf-8")
        buf = (ctypes.c_byte * len(raw_bytes))(*raw_bytes)
        wrote_any = False
        for target in CREDENTIAL_TARGETS:
            cred = CREDENTIAL()
            cred.Flags = 0
            cred.Type = 1  # CRED_TYPE_GENERIC
            cred.TargetName = target
            cred.UserName = "antigravity"
            cred.CredentialBlobSize = len(raw_bytes)
            cred.CredentialBlob = ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))
            cred.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE
            if cred_write(ctypes.byref(cred), 0):
                wrote_any = True
        return wrote_any

    if sys_name == "macos":
        existing = _read_macos_keychain() or ""
        store_val = token_str
        if payload and (raw_in.startswith("go-keyring-base64:") or existing.startswith("go-keyring-base64:")):
            store_val = "go-keyring-base64:" + base64.b64encode(token_str.encode("utf-8")).decode("ascii")
        res = _run_hidden(["security", "add-generic-password", "-U", "-s", "gemini", "-a", "antigravity", "-w", store_val])
        return res.returncode == 0

    wrote_file = False
    cred_file = get_platform_paths()["active_cred_path"]
    try:
        cred_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = cred_file.with_suffix(".token.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(token_str)
        os.replace(tmp, cred_file)
        os.chmod(cred_file, 0o600)
        wrote_file = True
    except Exception:
        pass

    if shutil.which("secret-tool"):
        try:
            _run_hidden(
                ["secret-tool", "store", "--label=Antigravity", "service", "gemini", "account", "antigravity"],
                input_text=token_str,
            )
        except Exception:
            pass
    return wrote_file


def clear_keychain_token() -> bool:
    """Delete active Antigravity credentials from the OS credential vault."""
    sys_name = get_current_system()
    if sys_name == "windows":
        import ctypes
        from ctypes import wintypes

        cred_delete = ctypes.windll.advapi32.CredDeleteW
        cred_delete.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
        cred_delete.restype = wintypes.BOOL
        cleared = False
        for target in CREDENTIAL_TARGETS:
            try:
                if cred_delete(target, 1, 0):
                    cleared = True
            except Exception:
                pass
        return cleared

    if sys_name == "macos":
        cleared = False
        for cmd in (
            ["security", "delete-generic-password", "-s", "gemini", "-a", "antigravity"],
            ["security", "delete-generic-password", "-s", "antigravity"],
        ):
            try:
                if _run_hidden(cmd).returncode == 0:
                    cleared = True
            except Exception:
                pass
        return cleared

    cleared = False
    cred_file = get_platform_paths()["active_cred_path"]
    if cred_file.exists():
        try:
            cred_file.unlink()
            cleared = True
        except Exception:
            pass
    if shutil.which("secret-tool"):
        try:
            if _run_hidden(["secret-tool", "clear", "service", "gemini", "account", "antigravity"]).returncode == 0:
                cleared = True
        except Exception:
            pass
    return cleared


delete_keychain_tokens = clear_keychain_token


def extract_token_email(token_data, check_manifest: bool = True) -> str | None:
    """Extract canonical lowercase email from JWT claims, metadata fields, or manifest refresh_token."""
    data = decode_token_dict(token_data)
    if not data:
        return None

    id_tok = data.get("id_token")
    if isinstance(id_tok, str) and "." in id_tok:
        parts = id_tok.split(".")
        if len(parts) >= 2:
            claims = _b64_json_decode(parts[1])
            if claims:
                email = claims.get("email")
                if email and "@" in str(email):
                    return str(email).lower().strip()

    t_obj = data.get("token", data)
    candidates = [data.get("email"), data.get("id_token_email")]
    if isinstance(t_obj, dict):
        candidates.extend([t_obj.get("email"), t_obj.get("id_token_email")])
    for cand in candidates:
        if cand and "@" in str(cand):
            return str(cand).lower().strip()

    if check_manifest:
        refresh_tok = t_obj.get("refresh_token") if isinstance(t_obj, dict) else data.get("refresh_token")
        if refresh_tok:
            manifest_path = get_platform_paths()["manifest_path"]
            if manifest_path.is_file():
                try:
                    m_data = json.loads(manifest_path.read_text(encoding="utf-8"))
                    for acc_key, entry in (m_data or {}).items():
                        if not isinstance(entry, dict):
                            continue
                        tf = entry.get("token_file")
                        if not tf or not os.path.isfile(tf):
                            continue
                        raw_tf = Path(tf).read_text(encoding="utf-8", errors="ignore")
                        _, saved_rt = parse_token_payload(raw_tf)
                        if saved_rt == refresh_tok or refresh_tok in raw_tf:
                            em = entry.get("email") or acc_key
                            if em and "@" in str(em):
                                return str(em).lower().strip()
                except Exception:
                    pass
    return None


def check_token_has_aicode(token_data) -> bool:
    """Return True if token structure contains OAuth tokens or Google AI Code scope."""
    if not token_data:
        return False
    try:
        s = json.dumps(token_data) if isinstance(token_data, dict) else str(token_data)
        return ("aicode" in s) or ("access_token" in s) or ("refresh_token" in s)
    except Exception:
        return False


def _parse_iso_expiry(expiry_str: str) -> datetime.datetime | None:
    if not expiry_str or not isinstance(expiry_str, str):
        return None
    clean = expiry_str.strip().replace("Z", "+00:00")
    if "." in clean:
        head, tail = clean.split(".", 1)
        if "+" in tail:
            frac, tz = tail.split("+", 1)
            clean = f"{head}.{frac[:6]}+{tz}"
        elif "-" in tail:
            frac, tz = tail.split("-", 1)
            clean = f"{head}.{frac[:6]}-{tz}"
        else:
            clean = f"{head}.{tail[:6]}"
    try:
        dt = datetime.datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return None


def ensure_fresh_token(token_data, account_email: str | None = None, force_refresh: bool = False):
    """Refresh OAuth access_token if expired or expiring within 5 minutes and persist safely."""
    if not token_data:
        return None

    was_str = isinstance(token_data, str)
    parsed = decode_token_dict(token_data)
    if not parsed:
        return token_data

    t_obj = parsed.get("token", parsed)
    if not isinstance(t_obj, dict):
        return token_data

    refresh_token = t_obj.get("refresh_token")
    if not refresh_token:
        return json.dumps(parsed, ensure_ascii=False) if was_str else parsed

    exp_dt = _parse_iso_expiry(t_obj.get("expiry", ""))
    needs_refresh = bool(force_refresh) or (exp_dt is None) or (
        (exp_dt - datetime.datetime.now(datetime.timezone.utc)).total_seconds() < 300
    )

    if needs_refresh:
        try:
            params = urllib.parse.urlencode({
                "client_id": OAUTH_CLIENT_ID,
                "client_secret": OAUTH_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }).encode("utf-8")
            req = urllib.request.Request("https://oauth2.googleapis.com/token", data=params)
            with urllib.request.urlopen(req, timeout=7.0) as resp:
                tok_data = json.loads(resp.read().decode("utf-8"))
            if tok_data.get("access_token"):
                t_obj["access_token"] = tok_data["access_token"]
                exp_sec = int(tok_data.get("expires_in", 3600))
                new_exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=exp_sec)
                t_obj["expiry"] = new_exp.isoformat().replace("+00:00", "Z")
                if "id_token" in tok_data:
                    parsed["id_token"] = tok_data["id_token"]
                if "token" in parsed:
                    parsed["token"] = t_obj
                else:
                    parsed.update(t_obj)

                claimed = extract_token_email(parsed, check_manifest=False)
                acc_email = account_email or claimed
                if account_email and claimed and account_email.lower().strip() != claimed:
                    acc_email = None
                if acc_email:
                    safe_acc = "".join(c if c.isalnum() or c in ("@", ".", "_", "-") else "_" for c in acc_email.strip())
                    tf = get_platform_paths()["accounts_dir"] / f"{safe_acc}.token"
                    try:
                        tf.parent.mkdir(parents=True, exist_ok=True)
                        tmp = tf.with_suffix(".token.tmp")
                        tmp.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
                        os.replace(tmp, tf)
                    except Exception:
                        pass
        except Exception:
            pass

    return json.dumps(parsed, ensure_ascii=False) if was_str else parsed
