#!/bin/bash
# ==============================================================================
# Antigravity Account Switcher, Quota & Smart RTL Suite v3.0 - Universal Installer
# Supports macOS (Apple Silicon & Intel) and Linux (x86_64 & arm64)
# Organization: mad-helpers (https://github.com/mad-helpers/antigravity-account-switcher)
# ==============================================================================
set -e

NO_RESTART_DAEMON=0
if [ "${AGY_NO_RESTART_DAEMON:-0}" = "1" ]; then
    NO_RESTART_DAEMON=1
fi
for arg in "$@"; do
    case "$arg" in
        --no-restart-daemon|-NoRestartDaemon)
            NO_RESTART_DAEMON=1
            ;;
    esac
done

OS_NAME="$(uname -s)"
ARCH="$(uname -m)"

echo "[*] Installing Antigravity Account Switcher, Quota & Smart RTL Suite v3.0..."
echo "[*] Organization: mad-helpers (Madgod-xyz & Bombhub-apk)"
echo "[*] Repository:   https://github.com/mad-helpers/antigravity-account-switcher"
echo "[*] Detected OS:  $OS_NAME ($ARCH)"

SCRIPT_SOURCE="${BASH_SOURCE[0]:-}"
CANDIDATE_DIR=""
if [ -n "$SCRIPT_SOURCE" ] && [ -f "$SCRIPT_SOURCE" ]; then
    CANDIDATE_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
fi

GEMINI_ROOT="$HOME/.gemini"
mkdir -p "$GEMINI_ROOT"

TMP_BOOTSTRAP=""
cleanup() {
    if [ -n "$TMP_BOOTSTRAP" ] && [ -d "$TMP_BOOTSTRAP" ]; then
        rm -rf "$TMP_BOOTSTRAP" 2>/dev/null || true
    fi
}
trap cleanup EXIT

if [ -n "$CANDIDATE_DIR" ] && [ -f "$CANDIDATE_DIR/ag_suite/__init__.py" ]; then
    DIR="$CANDIDATE_DIR"
    echo "[*] Using local repository checkout: $DIR"
else
    INSTALL_REPO_DIR="$GEMINI_ROOT/antigravity-account-switcher"
    echo "[*] Bootstrapping repository from GitHub (main branch) to $INSTALL_REPO_DIR..."
    BOOTSTRAPPED=0
    if command -v git >/dev/null 2>&1; then
        if [ -d "$INSTALL_REPO_DIR/.git" ]; then
            if git -C "$INSTALL_REPO_DIR" fetch origin main --depth 1 >/dev/null 2>&1 && \
               git -C "$INSTALL_REPO_DIR" reset --hard origin/main >/dev/null 2>&1; then
                BOOTSTRAPPED=1
            fi
        else
            rm -rf "$INSTALL_REPO_DIR"
            if git clone --branch main --depth 1 "https://github.com/mad-helpers/antigravity-account-switcher.git" "$INSTALL_REPO_DIR" >/dev/null 2>&1; then
                BOOTSTRAPPED=1
            fi
        fi
    fi

    if [ "$BOOTSTRAPPED" -eq 0 ] || [ ! -f "$INSTALL_REPO_DIR/ag_suite/__init__.py" ]; then
        TMP_BOOTSTRAP="$(mktemp -d /tmp/agy-suite-install.XXXXXX)"
        TAR_URL="https://github.com/mad-helpers/antigravity-account-switcher/archive/refs/heads/main.tar.gz"
        echo "[*] Downloading archive $TAR_URL..."
        curl -fsSL "$TAR_URL" | tar -xz -C "$TMP_BOOTSTRAP"
        EXTRACTED_DIR="$TMP_BOOTSTRAP/antigravity-account-switcher-main"
        if [ ! -d "$EXTRACTED_DIR" ]; then
            EXTRACTED_DIR="$(find "$TMP_BOOTSTRAP" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
        fi
        mkdir -p "$INSTALL_REPO_DIR"
        cp -Rf "$EXTRACTED_DIR/"* "$INSTALL_REPO_DIR/"
    fi
    DIR="$INSTALL_REPO_DIR"
    echo "[OK] Repository ready at $DIR"
fi

TARGET_APP="$GEMINI_ROOT/antigravity"
TARGET_BIN="$TARGET_APP/bin"
PLUGIN_DEST="$GEMINI_ROOT/config/plugins/antigravity-account-suite"
SKILL_DEST="$GEMINI_ROOT/config/skills/antigravity-account-suite"

mkdir -p \
    "$TARGET_BIN/ag_suite" \
    "$TARGET_BIN/legacy/chatgpt" \
    "$TARGET_BIN/app" \
    "$TARGET_BIN/assets/fonts" \
    "$PLUGIN_DEST" \
    "$SKILL_DEST"

# 1. Deploy ag_suite, legacy/chatgpt, runtime Python, JS, UI, and local fonts
if [ -d "$DIR/ag_suite" ]; then
    cp -f "$DIR/ag_suite/"*.py "$TARGET_BIN/ag_suite/"
fi

if [ -d "$DIR/legacy/chatgpt" ]; then
    cp -Rf "$DIR/legacy/chatgpt/"* "$TARGET_BIN/legacy/chatgpt/"
fi

for pyf in "$DIR"/*.py; do
    [ -f "$pyf" ] || continue
    base="$(basename "$pyf")"
    case "$base" in
        test_*|_verify_*|inspect_*|check_*|compare_*|deep_audit*|diff_servers*|build_injector*|setup_ide_theme*)
            continue
            ;;
    esac
    cp -f "$pyf" "$TARGET_BIN/$base"
done

if [ -f "$DIR/antigravity_quota_injector.js" ]; then
    cp -f "$DIR/antigravity_quota_injector.js" "$TARGET_APP/antigravity_quota_injector.js"
    cp -f "$DIR/antigravity_quota_injector.js" "$TARGET_BIN/antigravity_quota_injector.js"
fi

if [ -d "$DIR/app" ]; then
    cp -Rf "$DIR/app/"* "$TARGET_BIN/app/"
    rm -f "$TARGET_BIN/app/runtime_window.html" 2>/dev/null || true
fi

if [ -d "$DIR/assets/fonts" ]; then
    cp -Rf "$DIR/assets/fonts/"* "$TARGET_BIN/assets/fonts/"
fi

echo "[OK] Deployed ag_suite, runtime files, UI assets, and local fonts to $TARGET_BIN"

# 2. Deploy Native Antigravity 2.33+ Plugin & Skill
if [ -d "$DIR/plugin" ]; then
    cp -Rf "$DIR/plugin/"* "$PLUGIN_DEST/"
    mkdir -p "$PLUGIN_DEST/assets/fonts" "$PLUGIN_DEST/sidecars/account-suite/fonts"
    if [ -d "$DIR/assets/fonts" ]; then
        cp -Rf "$DIR/assets/fonts/"* "$PLUGIN_DEST/assets/fonts/"
        cp -Rf "$DIR/assets/fonts/"* "$PLUGIN_DEST/sidecars/account-suite/fonts/"
    fi
    cat > "$PLUGIN_DEST/mcp_config.json" <<EOF
{
  "mcpServers": {
    "antigravity-account-suite": {
      "command": "python3",
      "args": [
        "$TARGET_BIN/mcp_server.py"
      ],
      "env": {
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
EOF
    echo "[OK] Deployed native Antigravity plugin to $PLUGIN_DEST"
fi

if [ -f "$DIR/skills/antigravity-account-suite/SKILL.md" ]; then
    cp -f "$DIR/skills/antigravity-account-suite/SKILL.md" "$SKILL_DEST/SKILL.md"
    echo "[OK] Installed SKILL.md to $SKILL_DEST"
fi

# 3. Create Antigravity CDP Launcher script (--remote-debugging-port=0)
LAUNCHER_SH="$TARGET_BIN/launch-antigravity-cdp.sh"
cat > "$LAUNCHER_SH" <<'EOF'
#!/bin/bash
export GOMEMLIMIT="3GiB"
export GOGC="50"
if [ "$(uname -s)" = "Darwin" ]; then
    open -a "/Applications/Antigravity.app" --args --remote-debugging-port=0 "$@"
else
    exec antigravity --remote-debugging-port=0 "$@"
fi
EOF
chmod +x "$LAUNCHER_SH"

# 4. Setup CLI shortcuts (agy-switch & agy-quota) pointing to cli.py
CLI_TARGET="$TARGET_BIN/cli.py"
chmod +x "$CLI_TARGET" 2>/dev/null || true

install_cli_wrappers() {
    local bin_dir="$1"
    cat > "$bin_dir/agy-switch" <<EOF
#!/bin/bash
if [ \$# -eq 0 ]; then
    exec python3 "$CLI_TARGET" --gui
else
    exec python3 "$CLI_TARGET" "\$@"
fi
EOF
    cat > "$bin_dir/agy-quota" <<EOF
#!/bin/bash
if [ \$# -eq 0 ]; then
    exec python3 "$CLI_TARGET" --usage
else
    exec python3 "$CLI_TARGET" "\$@"
fi
EOF
    chmod +x "$bin_dir/agy-switch" "$bin_dir/agy-quota"
}

INSTALLED_CLI=false
if [ -d "/opt/homebrew/bin" ] && [ -w "/opt/homebrew/bin" ]; then
    install_cli_wrappers "/opt/homebrew/bin"
    echo "[OK] Registered agy-switch & agy-quota in /opt/homebrew/bin"
    INSTALLED_CLI=true
fi
if [ -d "/usr/local/bin" ] && [ -w "/usr/local/bin" ]; then
    install_cli_wrappers "/usr/local/bin"
    echo "[OK] Registered agy-switch & agy-quota in /usr/local/bin"
    INSTALLED_CLI=true
fi
if [ "$INSTALLED_CLI" = false ]; then
    mkdir -p "$HOME/.local/bin"
    install_cli_wrappers "$HOME/.local/bin"
    echo "[OK] Registered agy-switch & agy-quota in $HOME/.local/bin"
fi

# 5. Platform-specific App Bundle / Desktop Entry & Background Service
if [ "$OS_NAME" = "Darwin" ]; then
    if [ -f "$DIR/build_app.sh" ] && command -v osacompile >/dev/null 2>&1; then
        "$DIR/build_app.sh" || true
    fi
    if [ -d "$DIR/AntigravitySwitcher.app" ]; then
        if [ -d "/Applications" ] && [ -w "/Applications" ]; then
            rm -rf "/Applications/AntigravitySwitcher.app"
            cp -R "$DIR/AntigravitySwitcher.app" "/Applications/AntigravitySwitcher.app"
        else
            mkdir -p "$HOME/Applications"
            rm -rf "$HOME/Applications/AntigravitySwitcher.app"
            cp -R "$DIR/AntigravitySwitcher.app" "$HOME/Applications/AntigravitySwitcher.app"
        fi
        if [ -d "$HOME/Desktop" ]; then
            rm -rf "$HOME/Desktop/AntigravitySwitcher.app"
            cp -R "$DIR/AntigravitySwitcher.app" "$HOME/Desktop/AntigravitySwitcher.app"
        fi
        echo "[OK] Installed AntigravitySwitcher.app bundle."
    fi

    LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
    PLIST_PATH="$LAUNCH_AGENTS_DIR/com.madhelpers.antigravity.quota.plist"
    mkdir -p "$LAUNCH_AGENTS_DIR"
    cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.madhelpers.antigravity.quota</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/env</string>
        <string>python3</string>
        <string>$TARGET_BIN/sync_daemon.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$TARGET_BIN</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF
    if [ "$NO_RESTART_DAEMON" -eq 0 ]; then
        launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
        launchctl load -w "$PLIST_PATH" >/dev/null 2>&1 || \
            nohup python3 "$TARGET_BIN/sync_daemon.py" >/dev/null 2>&1 &
    fi
else
    APPS_DIR="$HOME/.local/share/applications"
    mkdir -p "$APPS_DIR"
    cat > "$APPS_DIR/antigravity-cdp.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Antigravity IDE (CDP HUD & Smart RTL)
Comment=Launch Google Antigravity with CDP debugging enabled
Exec=$LAUNCHER_SH %F
Terminal=false
Categories=Development;IDE;
EOF
    cat > "$APPS_DIR/antigravity-switcher.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Antigravity Account Switcher
Comment=Antigravity Account Switcher, 6-Pool Quota & Smart RTL Control Center
Exec=python3 $CLI_TARGET --gui
Terminal=false
Categories=Development;Utility;
EOF
    echo "[OK] Installed Linux desktop launchers in $APPS_DIR"

    SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
    mkdir -p "$SYSTEMD_USER_DIR"
    cat > "$SYSTEMD_USER_DIR/antigravity-quota.service" <<EOF
[Unit]
Description=Antigravity Quota & Smart RTL Sync Daemon (v3.0)
After=network.target

[Service]
Type=simple
WorkingDirectory=$TARGET_BIN
ExecStart=/usr/bin/env python3 $TARGET_BIN/sync_daemon.py
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF
    if [ "$NO_RESTART_DAEMON" -eq 0 ]; then
        if command -v systemctl >/dev/null 2>&1 && systemctl --user status >/dev/null 2>&1; then
            systemctl --user daemon-reload >/dev/null 2>&1 || true
            systemctl --user enable --now antigravity-quota.service >/dev/null 2>&1 || true
            systemctl --user restart antigravity-quota.service >/dev/null 2>&1 || true
        else
            pkill -f "sync_daemon.py" >/dev/null 2>&1 || true
            nohup python3 "$TARGET_BIN/sync_daemon.py" >/dev/null 2>&1 &
        fi
    fi
fi

if [ "$NO_RESTART_DAEMON" -eq 0 ]; then
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        if curl -fsS "http://127.0.0.1:39281/health" >/dev/null 2>&1; then
            echo "[OK] Quota & CDP Sync Daemon is online at http://127.0.0.1:39281/health"
            break
        fi
        sleep 0.4
    done
else
    echo "[*] Skipped daemon restart (--no-restart-daemon)."
fi

echo ""
echo "[OK] Installation v3.0.0 complete on $OS_NAME ($ARCH)!"
echo "  - CLI: 'agy-quota', 'agy-switch --doctor', 'agy-switch --status-json', 'agy-switch --gui'"
echo "  - Sidecar Aux Pane: sidecar://antigravity-account-suite/account-suite/"
