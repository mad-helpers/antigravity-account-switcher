#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="AntigravitySwitcher.app"

echo "🔨 Building portable $APP_NAME (v3.0)..."

# Back up existing applet.icns before removing app bundle so builds on Macs
# without /Applications/Antigravity.app never lose the bundled icon.
TMP_ICNS=""
if [ -f "$DIR/$APP_NAME/Contents/Resources/applet.icns" ]; then
    TMP_ICNS="$(mktemp /tmp/switcher_icns.XXXXXX)"
    cp -f "$DIR/$APP_NAME/Contents/Resources/applet.icns" "$TMP_ICNS"
fi

# 1. Compile AppleScript launcher
TMP_AS="$(mktemp /tmp/switcher_build.XXXXXX.applescript)"
cat << 'APPLESCRIPT' > "$TMP_AS"
set appPath to POSIX path of (path to me)
set scriptPath to appPath & "Contents/Resources/switcher_core.py"
do shell script "/usr/bin/python3 " & quoted form of scriptPath
APPLESCRIPT

rm -rf "$DIR/$APP_NAME"
osacompile -o "$DIR/$APP_NAME" "$TMP_AS"
rm -f "$TMP_AS"

# 2. Bundle switcher_core.py and ag_suite/ inside Contents/Resources/
cp -f "$DIR/switcher_core.py" "$DIR/$APP_NAME/Contents/Resources/switcher_core.py"
chmod +x "$DIR/$APP_NAME/Contents/Resources/switcher_core.py"

if [ -d "$DIR/ag_suite" ]; then
    mkdir -p "$DIR/$APP_NAME/Contents/Resources/ag_suite"
    cp -f "$DIR/ag_suite/"*.py "$DIR/$APP_NAME/Contents/Resources/ag_suite/"
    rm -rf "$DIR/$APP_NAME/Contents/Resources/ag_suite/__pycache__" 2>/dev/null || true
fi

# 3. Add High-Res Icon from Antigravity if available, else restore backed-up applet.icns
if [ -f "/Applications/Antigravity.app/Contents/Resources/icon.icns" ]; then
    cp -f "/Applications/Antigravity.app/Contents/Resources/icon.icns" "$DIR/$APP_NAME/Contents/Resources/applet.icns"
elif [ -n "$TMP_ICNS" ] && [ -f "$TMP_ICNS" ]; then
    cp -f "$TMP_ICNS" "$DIR/$APP_NAME/Contents/Resources/applet.icns"
fi

if [ -n "$TMP_ICNS" ] && [ -f "$TMP_ICNS" ]; then
    rm -f "$TMP_ICNS"
fi

# 4. Refresh icon cache
touch "$DIR/$APP_NAME"

echo "✅ Build complete: $DIR/$APP_NAME"
