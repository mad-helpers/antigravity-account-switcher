"""
Antigravity IDE Theme, Persian Fonts, Neon Glow & Live Customizer Suite
Permanent installer for Antigravity IDE:
- Embeds Vazirmatn, Estedad, Outfit WOFF2 fonts + Local Vazir/Vazirmatn support
- Floating Draggable HUD Pill (Theme Customizer + Account Switcher) like ChatGPT Enhanced
- Live Interactive Theme & Neon Customization Modal (Cyberpunk, SynthWave, AMOLED, Midnight, Emerald, Sunset, Clean Dark)
- High Neon Glow, Refined Glass & Subtle stroke options
- Live instant preview on dropdown / slider change without reload
- Status bar button & Global Hotkeys (Alt+T for Theme, Alt+A for Accounts)
- Full Smart BiDi for Monaco Editor (Persian Markdown lines RTL, Code blocks LTR)
- Universal Persian Typography & RTL for Antigravity Agent Chat & Prose
- Updates product.json SHA-256 base64 checksums to eliminate corrupt installation warnings
- Configures User settings.json with optimal Markdown and Persian defaults
"""

import os
import sys
import json
import base64
import hashlib
import shutil
import re
from pathlib import Path

# Fix console encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HOME = Path.home()
IDE_APP_DIR = Path(os.getenv("LOCALAPPDATA", str(HOME / "AppData" / "Local"))) / "Programs" / "Antigravity IDE" / "resources" / "app"
IDE_USER_SETTINGS = Path(os.getenv("APPDATA", str(HOME / "AppData" / "Roaming"))) / "Antigravity IDE" / "User" / "settings.json"

FONT_SOURCES = [
    Path(__file__).resolve().parent / "assets" / "fonts",
    HOME / ".gemini" / "antigravity" / "bin" / "assets" / "fonts",
    IDE_APP_DIR / "out" / "vs" / "workbench" / "fonts",
]

def find_font_file(filename):
    for d in FONT_SOURCES:
        p = d / filename
        if p.exists():
            return p
    return None

def compute_checksum(file_path):
    content = file_path.read_bytes()
    h = hashlib.sha256(content).digest()
    return base64.b64encode(h).decode('ascii').rstrip('=')

def setup_ide_theme():
    print("=" * 60)
    print("⚡️ Setting up Antigravity IDE Live Theme, Neon Glow & Font Suite")
    print("=" * 60)

    if not IDE_APP_DIR.exists():
        print(f"❌ Antigravity IDE not found at: {IDE_APP_DIR}")
        return False

    out_dir = IDE_APP_DIR / "out"
    wb_dir = out_dir / "vs" / "workbench"
    fonts_dest_1 = wb_dir / "fonts"
    fonts_dest_2 = out_dir / "fonts"

    fonts_dest_1.mkdir(parents=True, exist_ok=True)
    fonts_dest_2.mkdir(parents=True, exist_ok=True)

    # 1. Locate and copy font files
    font_files = {
        "Vazirmatn": "Vazirmatn[wght].woff2",
        "Estedad": "Estedad[wght].woff2",
        "Outfit": "Outfit[wght].woff2"
    }

    font_b64 = {}
    for name, filename in font_files.items():
        src = find_font_file(filename)
        if src and src.exists():
            if src != fonts_dest_1 / filename:
                shutil.copy2(src, fonts_dest_1 / filename)
            if src != fonts_dest_2 / filename:
                shutil.copy2(src, fonts_dest_2 / filename)
            raw = src.read_bytes()
            font_b64[name] = base64.b64encode(raw).decode('ascii')
            print(f"✓ Copied {filename} ({len(raw)} bytes)")
        else:
            print(f"⚠️ Font file not found: {filename}")
            font_b64[name] = ""

    vazir_b64 = font_b64.get("Vazirmatn", "")
    estedad_b64 = font_b64.get("Estedad", "")
    outfit_b64 = font_b64.get("Outfit", "")

    # 2. Build antigravity-custom-theme.css (Permanent Foundational Theme & Neon CSS)
    theme_css = f"""/* Antigravity IDE Permanent Modern Theme & Persian Typography Suite */
/* Generated automatically by setup_ide_theme.py */

/* --- 1. Embedded Web Fonts --- */
@font-face {{
  font-family: 'Outfit';
  font-style: normal;
  font-weight: 100 900;
  font-display: swap;
  src: url('./fonts/Outfit[wght].woff2') format('woff2'),
       url('../../../fonts/Outfit[wght].woff2') format('woff2'),
       url('data:font/woff2;base64,{outfit_b64}') format('woff2');
}}

@font-face {{
  font-family: 'Vazirmatn';
  font-style: normal;
  font-weight: 100 900;
  font-display: swap;
  src: url('./fonts/Vazirmatn[wght].woff2') format('woff2'),
       url('../../../fonts/Vazirmatn[wght].woff2') format('woff2'),
       url('data:font/woff2;base64,{vazir_b64}') format('woff2');
}}

@font-face {{
  font-family: 'Estedad';
  font-style: normal;
  font-weight: 100 900;
  font-display: swap;
  src: url('./fonts/Estedad[wght].woff2') format('woff2'),
       url('../../../fonts/Estedad[wght].woff2') format('woff2'),
       url('data:font/woff2;base64,{estedad_b64}') format('woff2');
}}

/* --- 2. Color Palettes & Neon Themes --- */
:root,
[data-agy-theme="cyber"] {{
  --agy-bg: #080c14;
  --agy-bg-gradient: radial-gradient(ellipse 95% 70% at 50% -10%, rgba(0, 240, 255, 0.16) 0%, rgba(14, 28, 54, 0.72) 42%, #080c14 85%);
  --agy-accent: #00f0ff;
  --agy-accent-glow: 0 0 20px rgba(0, 240, 255, 0.55);
  --agy-accent-soft: rgba(0, 240, 255, 0.15);
  --agy-border: rgba(0, 240, 255, 0.32);
  --agy-card: #0f1728;
  --agy-card-border: rgba(0, 240, 255, 0.26);
  --agy-sidebar: #060910;
  --agy-composer-bg: rgba(15, 23, 42, 0.95);
  --agy-text: #f1f5f9;
  --vscode-font-family: 'Outfit', 'Vazirmatn', 'Vazirmatn UI', 'Vazir', 'Estedad', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
  --cpe-font: 'Outfit', 'Vazirmatn', 'Vazirmatn UI', 'Vazir', 'Estedad', sans-serif;
  --cpe-accent: #00f0ff;
  --cpe-accent-glow: 0 0 18px rgba(0, 240, 255, 0.55);
  --cpe-accent-soft: rgba(0, 240, 255, 0.15);
  --cpe-border: rgba(0, 240, 255, 0.32);
  --vscode-editor-background: transparent !important;
  --vscode-sideBar-background: transparent !important;
  --vscode-sideBarTitle-background: transparent !important;
  --vscode-sideBarSectionHeader-background: transparent !important;
  --vscode-activityBar-background: rgba(6, 9, 16, 0.72) !important;
  --vscode-titleBar-activeBackground: rgba(6, 9, 16, 0.72) !important;
  --vscode-statusBar-background: rgba(6, 9, 16, 0.8) !important;
  --vscode-editorGroupHeader-tabsBackground: transparent !important;
  --vscode-editorGroupHeader-noTabsBackground: transparent !important;
  --vscode-tab-activeBackground: rgba(255, 255, 255, 0.08) !important;
  --vscode-tab-inactiveBackground: transparent !important;
  --vscode-tab-border: transparent !important;
  --vscode-tab-activeBorder: var(--agy-accent) !important;
  --vscode-tab-activeBorderTop: transparent !important;
  --vscode-focusBorder: var(--agy-accent) !important;
  --vscode-button-background: var(--agy-accent) !important;
  --vscode-button-foreground: #000000 !important;
  --vscode-button-hoverBackground: var(--agy-accent) !important;
  --vscode-menu-background: #0f1728 !important;
  --vscode-menu-foreground: #f1f5f9 !important;
  --vscode-menu-selectionBackground: var(--agy-accent-soft) !important;
  --vscode-menu-selectionForeground: var(--agy-accent) !important;
  --vscode-menu-selectionBorder: var(--agy-accent) !important;
  --vscode-menu-separatorBackground: rgba(255, 255, 255, 0.1) !important;
  --vscode-menu-border: var(--agy-border) !important;
  --vscode-dropdown-background: #0f1728 !important;
  --vscode-dropdown-foreground: #f1f5f9 !important;
  --vscode-dropdown-border: var(--agy-border) !important;
}}

[data-agy-theme="synthwave"] {{
  --agy-bg: #0d071a;
  --agy-bg-gradient: radial-gradient(ellipse 95% 70% at 50% -10%, rgba(255, 0, 127, 0.18) 0%, rgba(42, 12, 64, 0.75) 42%, #0d071a 85%);
  --agy-accent: #ff007f;
  --agy-accent-glow: 0 0 22px rgba(255, 0, 127, 0.65);
  --agy-accent-soft: rgba(255, 0, 127, 0.18);
  --agy-border: rgba(255, 0, 127, 0.38);
  --agy-card: #1a0d30;
  --agy-card-border: rgba(255, 0, 127, 0.32);
  --agy-sidebar: #080312;
  --agy-composer-bg: rgba(24, 13, 46, 0.95);
  --agy-text: #fff0f8;
  --vscode-editor-background: transparent !important;
  --vscode-sideBar-background: transparent !important;
  --vscode-sideBarTitle-background: transparent !important;
  --vscode-sideBarSectionHeader-background: transparent !important;
  --vscode-activityBar-background: rgba(8, 3, 18, 0.75) !important;
  --vscode-titleBar-activeBackground: rgba(8, 3, 18, 0.75) !important;
  --vscode-statusBar-background: rgba(8, 3, 18, 0.8) !important;
  --vscode-editorGroupHeader-tabsBackground: transparent !important;
  --vscode-editorGroupHeader-noTabsBackground: transparent !important;
  --vscode-tab-activeBackground: rgba(255, 255, 255, 0.08) !important;
  --vscode-tab-inactiveBackground: transparent !important;
  --vscode-focusBorder: var(--agy-accent) !important;
  --vscode-button-background: var(--agy-accent) !important;
  --vscode-button-foreground: #ffffff !important;
  --vscode-button-hoverBackground: var(--agy-accent) !important;
}}

[data-agy-theme="amoled"] {{
  --agy-bg: #000000;
  --agy-bg-gradient: radial-gradient(ellipse 95% 70% at 50% -10%, rgba(56, 189, 248, 0.12) 0%, rgba(10, 22, 38, 0.5) 40%, #000000 80%);
  --agy-accent: #38bdf8;
  --agy-accent-glow: 0 0 16px rgba(56, 189, 248, 0.45);
  --agy-accent-soft: rgba(255, 255, 255, 0.08);
  --agy-border: rgba(255, 255, 255, 0.2);
  --agy-card: #0d0d0d;
  --agy-card-border: rgba(255, 255, 255, 0.16);
  --agy-sidebar: #040404;
  --agy-composer-bg: #080808;
  --agy-text: #ffffff;
  --vscode-editor-background: transparent !important;
  --vscode-sideBar-background: transparent !important;
  --vscode-sideBarTitle-background: transparent !important;
  --vscode-sideBarSectionHeader-background: transparent !important;
  --vscode-activityBar-background: rgba(4, 4, 4, 0.75) !important;
  --vscode-titleBar-activeBackground: rgba(4, 4, 4, 0.75) !important;
  --vscode-statusBar-background: rgba(4, 4, 4, 0.8) !important;
  --vscode-editorGroupHeader-tabsBackground: transparent !important;
  --vscode-editorGroupHeader-noTabsBackground: transparent !important;
  --vscode-tab-activeBackground: rgba(255, 255, 255, 0.08) !important;
  --vscode-tab-inactiveBackground: transparent !important;
  --vscode-focusBorder: var(--agy-accent) !important;
  --vscode-button-background: var(--agy-accent) !important;
  --vscode-button-foreground: #000000 !important;
  --vscode-button-hoverBackground: var(--agy-accent) !important;
}}

[data-agy-theme="midnight"] {{
  --agy-bg: #0a0e1a;
  --agy-bg-gradient: radial-gradient(ellipse 95% 70% at 50% -10%, rgba(129, 140, 248, 0.18) 0%, rgba(25, 32, 66, 0.75) 42%, #0a0e1a 85%);
  --agy-accent: #818cf8;
  --agy-accent-glow: 0 0 20px rgba(129, 140, 248, 0.55);
  --agy-accent-soft: rgba(99, 102, 241, 0.16);
  --agy-border: rgba(99, 102, 241, 0.3);
  --agy-card: #12182c;
  --agy-card-border: rgba(99, 102, 241, 0.26);
  --agy-sidebar: #060912;
  --agy-composer-bg: rgba(18, 24, 44, 0.95);
  --agy-text: #f8fafc;
  --vscode-editor-background: transparent !important;
  --vscode-sideBar-background: transparent !important;
  --vscode-sideBarTitle-background: transparent !important;
  --vscode-sideBarSectionHeader-background: transparent !important;
  --vscode-activityBar-background: rgba(6, 9, 18, 0.75) !important;
  --vscode-titleBar-activeBackground: rgba(6, 9, 18, 0.75) !important;
  --vscode-statusBar-background: rgba(6, 9, 18, 0.8) !important;
  --vscode-editorGroupHeader-tabsBackground: transparent !important;
  --vscode-editorGroupHeader-noTabsBackground: transparent !important;
  --vscode-tab-activeBackground: rgba(255, 255, 255, 0.08) !important;
  --vscode-tab-inactiveBackground: transparent !important;
  --vscode-focusBorder: var(--agy-accent) !important;
  --vscode-button-background: var(--agy-accent) !important;
  --vscode-button-foreground: #000000 !important;
  --vscode-button-hoverBackground: var(--agy-accent) !important;
}}

[data-agy-theme="emerald"] {{
  --agy-bg: #06100a;
  --agy-bg-gradient: radial-gradient(ellipse 95% 70% at 50% -10%, rgba(16, 185, 129, 0.18) 0%, rgba(12, 44, 26, 0.75) 42%, #06100a 85%);
  --agy-accent: #10b981;
  --agy-accent-glow: 0 0 20px rgba(16, 185, 129, 0.55);
  --agy-accent-soft: rgba(16, 185, 129, 0.16);
  --agy-border: rgba(16, 185, 129, 0.3);
  --agy-card: #0c2014;
  --agy-card-border: rgba(16, 185, 129, 0.26);
  --agy-sidebar: #030805;
  --agy-composer-bg: rgba(10, 26, 17, 0.95);
  --agy-text: #ecfdf5;
  --vscode-editor-background: transparent !important;
  --vscode-sideBar-background: transparent !important;
  --vscode-sideBarTitle-background: transparent !important;
  --vscode-sideBarSectionHeader-background: transparent !important;
  --vscode-activityBar-background: rgba(3, 8, 5, 0.75) !important;
  --vscode-titleBar-activeBackground: rgba(3, 8, 5, 0.75) !important;
  --vscode-statusBar-background: rgba(3, 8, 5, 0.8) !important;
  --vscode-editorGroupHeader-tabsBackground: transparent !important;
  --vscode-editorGroupHeader-noTabsBackground: transparent !important;
  --vscode-tab-activeBackground: rgba(255, 255, 255, 0.08) !important;
  --vscode-tab-inactiveBackground: transparent !important;
  --vscode-focusBorder: var(--agy-accent) !important;
  --vscode-button-background: var(--agy-accent) !important;
  --vscode-button-foreground: #000000 !important;
  --vscode-button-hoverBackground: var(--agy-accent) !important;
}}

[data-agy-theme="sunset"] {{
  --agy-bg: #140c06;
  --agy-bg-gradient: radial-gradient(ellipse 95% 70% at 50% -10%, rgba(245, 158, 11, 0.18) 0%, rgba(55, 26, 10, 0.75) 42%, #140c06 85%);
  --agy-accent: #f59e0b;
  --agy-accent-glow: 0 0 20px rgba(245, 158, 11, 0.55);
  --agy-accent-soft: rgba(245, 158, 11, 0.16);
  --agy-border: rgba(245, 158, 11, 0.3);
  --agy-card: #24140b;
  --agy-card-border: rgba(245, 158, 11, 0.26);
  --agy-sidebar: #0a0502;
  --agy-composer-bg: rgba(32, 18, 9, 0.95);
  --agy-text: #fffbeb;
  --vscode-editor-background: transparent !important;
  --vscode-sideBar-background: transparent !important;
  --vscode-sideBarTitle-background: transparent !important;
  --vscode-sideBarSectionHeader-background: transparent !important;
  --vscode-activityBar-background: rgba(10, 5, 2, 0.75) !important;
  --vscode-titleBar-activeBackground: rgba(10, 5, 2, 0.75) !important;
  --vscode-statusBar-background: rgba(10, 5, 2, 0.8) !important;
  --vscode-editorGroupHeader-tabsBackground: transparent !important;
  --vscode-editorGroupHeader-noTabsBackground: transparent !important;
  --vscode-tab-activeBackground: rgba(255, 255, 255, 0.08) !important;
  --vscode-tab-inactiveBackground: transparent !important;
  --vscode-focusBorder: var(--agy-accent) !important;
  --vscode-button-background: var(--agy-accent) !important;
  --vscode-button-foreground: #000000 !important;
  --vscode-button-hoverBackground: var(--agy-accent) !important;
}}

[data-agy-theme="clean_dark"] {{
  --agy-bg: #0e1117;
  --agy-bg-gradient: radial-gradient(ellipse 95% 70% at 50% -10%, rgba(56, 189, 248, 0.12) 0%, rgba(26, 32, 44, 0.7) 42%, #0e1117 85%);
  --agy-accent: #38bdf8;
  --agy-accent-glow: 0 0 14px rgba(56, 189, 248, 0.35);
  --agy-accent-soft: rgba(56, 189, 248, 0.12);
  --agy-border: rgba(255, 255, 255, 0.15);
  --agy-card: #181b22;
  --agy-card-border: rgba(255, 255, 255, 0.14);
  --agy-sidebar: #0c0e12;
  --agy-composer-bg: rgba(24, 27, 34, 0.94);
  --agy-text: #f8fafc;
  --vscode-editor-background: transparent !important;
  --vscode-sideBar-background: transparent !important;
  --vscode-sideBarTitle-background: transparent !important;
  --vscode-sideBarSectionHeader-background: transparent !important;
  --vscode-activityBar-background: rgba(12, 14, 18, 0.75) !important;
  --vscode-titleBar-activeBackground: rgba(12, 14, 18, 0.75) !important;
  --vscode-statusBar-background: rgba(12, 14, 18, 0.8) !important;
  --vscode-editorGroupHeader-tabsBackground: transparent !important;
  --vscode-editorGroupHeader-noTabsBackground: transparent !important;
  --vscode-tab-activeBackground: rgba(255, 255, 255, 0.08) !important;
  --vscode-tab-inactiveBackground: transparent !important;
  --vscode-focusBorder: var(--agy-accent) !important;
  --vscode-button-background: var(--agy-accent) !important;
  --vscode-button-foreground: #000000 !important;
  --vscode-button-hoverBackground: var(--agy-accent) !important;
}}

/* --- 3. Shell Background & Transparent Layers --- */
html,
body {{
  background-color: var(--agy-bg) !important;
  background-image: var(--agy-bg-gradient) !important;
  background-attachment: scroll !important;
  background-size: cover !important;
  background-repeat: no-repeat !important;
}}

.monaco-workbench,
#root,
.jetski-root,
#jetski-root {{
  background: transparent !important;
  background-color: transparent !important;
  background-image: none !important;
}}

/* Secondary Sidebar (Auxiliary Bar) - where Agent panel lives */
.monaco-workbench .part.auxiliarybar,
.monaco-workbench .part.auxiliarybar > .content,
.monaco-workbench .part.auxiliarybar .composite,
.monaco-workbench .part.auxiliarybar .title,
.monaco-workbench .part.auxiliarybar .pane-body,
.monaco-workbench .part.auxiliarybar .pane-header,
.monaco-workbench .part.auxiliarybar .pane,
.monaco-workbench .part.auxiliarybar iframe,
.monaco-workbench .part.auxiliarybar webview,
.monaco-workbench .part.auxiliarybar .monaco-scrollable-element,
.monaco-workbench .part.auxiliarybar .split-view-view {{
  background: transparent !important;
  background-color: transparent !important;
}}

/* Context Menus, Dropdown Menus & Modals - Strictly Top Stacking & Solid Surface */
.context-view,
.context-view.fixed,
.monaco-menu-container,
.monaco-menu,
.menubar-menu-items,
.menubar-menu-items-holder,
.menubar .menubar-menu-items-holder,
.monaco-dropdown,
.monaco-dropdown-menu,
.monaco-action-bar.vertical {{
  position: absolute !important;
  z-index: 2147483640 !important;
  background-color: #0f1728 !important;
  background: #0f1728 !important;
  border: 1px solid var(--agy-border, rgba(0, 240, 255, 0.35)) !important;
  border-radius: 10px !important;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.95), var(--agy-accent-glow) !important;
  opacity: 1 !important;
  visibility: visible !important;
}}

.menubar .menubar-menu-items-holder {{
  position: fixed !important;
  z-index: 2147483640 !important;
}}

.context-view * {{
  z-index: 2147483641 !important;
}}

.monaco-menu .monaco-action-bar .action-item {{
  color: #f1f5f9 !important;
  background: transparent !important;
}}

.monaco-menu .monaco-action-bar .action-item.focused,
.monaco-menu .monaco-action-bar .action-item:hover {{
  background-color: var(--agy-accent-soft, rgba(0, 240, 255, 0.16)) !important;
  color: var(--agy-accent, #00f0ff) !important;
  border-radius: 6px !important;
}}

.monaco-menu .monaco-action-bar .action-label {{
  color: inherit !important;
}}

.monaco-menu .monaco-action-bar .keybinding {{
  color: #94a3b8 !important;
  opacity: 0.8 !important;
}}

.monaco-dialog-box,
.monaco-dialog-modal,
.modal-container,
.monaco-modal {{
  position: fixed !important;
  z-index: 2147483642 !important;
  background: #0f1728 !important;
  border: 1px solid var(--agy-border, rgba(0, 240, 255, 0.35)) !important;
  border-radius: 16px !important;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.95), var(--agy-accent-glow) !important;
}}

/* Tabs & Editor Group Headers - Solid Surface & High Stacking (Prevents clipping & falling behind) */
.monaco-workbench .part.editor > .content .editor-group-container > .title,
.editor-group-container > .title,
.tabs-and-actions-container,
.tabs-container,
.editor-group-header {{
  position: relative !important;
  z-index: 20 !important;
  background: rgba(10, 14, 24, 0.92) !important;
  backdrop-filter: blur(8px) !important;
  -webkit-backdrop-filter: blur(8px) !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
}}

.tabs-container .tab {{
  background: rgba(15, 23, 42, 0.75) !important;
  border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
  color: #94a3b8 !important;
  position: relative !important;
  z-index: 21 !important;
}}

.tabs-container .tab.active {{
  background: var(--agy-card, #0f1728) !important;
  color: #ffffff !important;
  border-bottom: 2px solid var(--agy-accent) !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35), var(--agy-accent-glow) !important;
}}

/* Clear all opaque backgrounds on editor and agent containers so neon halo shines through */
.monaco-workbench .part.editor,
.monaco-workbench .part.editor > .content,
.monaco-workbench .part.editor .editor-group-container,
.monaco-workbench .part.editor .editor-group-container > .editor-container,
.monaco-workbench .part.editor .editor-instance,
.monaco-workbench .part.editor .split-view-view,
.monaco-workbench .part.editor .grid-view-container,
.gettingStartedContainer,
.gettingStartedSlideDetails,
.welcome-page,
.welcome-page .welcome-page-content,
.getting-started-category,
.welcome-card,
.monaco-editor,
.monaco-editor-background,
.overflow-guard,
.margin,
.monaco-editor .inputarea.ime-input,
.jetski-root,
[class*="jetski-root"],
#root,
#jetski-root,
.bg-agent-convo-background,
.bg-background,
.bg-sidebar-background,
.bg-editor-background,
.bg-ide-editor-background,
.bg-card,
.bg-muted,
main.flex-1,
div[class*="bg-background"],
div[class*="bg-sidebar-background"],
div[class*="bg-agent-convo-background"],
div[class*="bg-zinc"],
div[class*="bg-[#18181b]"],
div[class*="bg-[#09090b]"],
div[class*="bg-[#121212]"],
div[class*="bg-neutral"],
div[class*="bg-slate"] {{
  background: transparent !important;
  background-color: transparent !important;
}}

/* Translucent titlebar and chrome panels with strict stacking */
.monaco-workbench .part.titlebar,
.part.titlebar {{
  position: relative !important;
  z-index: 5000 !important;
  background: rgba(6, 9, 16, 0.92) !important;
  backdrop-filter: blur(8px) !important;
  -webkit-backdrop-filter: blur(8px) !important;
  border-bottom: 1px solid var(--agy-border) !important;
}}

.monaco-workbench .part.statusbar {{
  background: rgba(6, 9, 16, 0.85) !important;
  backdrop-filter: blur(20px) !important;
  -webkit-backdrop-filter: blur(20px) !important;
  border-top: 1px solid var(--agy-border) !important;
}}

.monaco-workbench .part.activitybar {{
  background: rgba(6, 9, 16, 0.85) !important;
  backdrop-filter: blur(20px) !important;
  -webkit-backdrop-filter: blur(20px) !important;
  border-right: 1px solid var(--agy-border) !important;
}}

.monaco-workbench .part.sidebar {{
  background: rgba(6, 9, 16, 0.82) !important;
  backdrop-filter: blur(20px) !important;
  -webkit-backdrop-filter: blur(20px) !important;
  border-right: 1px solid var(--agy-border) !important;
}}

/* Neon buttons with radiant glow */
.monaco-button,
.monaco-text-button,
button.getting-started-action {{
  background: var(--agy-accent) !important;
  color: #000000 !important;
  font-weight: 700 !important;
  border-radius: 12px !important;
  border: 1px solid var(--agy-accent) !important;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.4), var(--agy-accent-glow) !important;
  transition: all 0.2s ease !important;
}}

.monaco-button:hover,
.monaco-text-button:hover,
button.getting-started-action:hover {{
  box-shadow: 0 6px 26px rgba(0, 0, 0, 0.6), var(--agy-accent-glow) !important;
  transform: translateY(-1px) !important;
}}

.monaco-button.secondary,
.monaco-text-button.secondary {{
  background: rgba(255, 255, 255, 0.05) !important;
  color: #ffffff !important;
  border: 1px solid var(--agy-border) !important;
  border-radius: 12px !important;
}}

.getting-started-category,
.welcome-card,
[class*="workspace-item"],
[class*="extension-card"] {{
  background: var(--agy-card) !important;
  border: 1px solid var(--agy-card-border) !important;
  border-radius: 14px !important;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45) !important;
  backdrop-filter: blur(12px) !important;
}}

/* Tabs with neon active border */
.tabs-container .tab.active {{
  background: var(--agy-card) !important;
  border-bottom: 2px solid var(--agy-accent) !important;
  box-shadow: 0 -2px 14px rgba(0, 0, 0, 0.4), var(--agy-accent-glow) !important;
}}

/* Composer box inside Agent Chat Panel */
div[class*="chat-input-container"],
div[class*="_ComposerLayoutRoot_"],
div[class*="composer-container"] {{
  background: var(--agy-composer-bg) !important;
  border: 1px solid var(--agy-accent) !important;
  border-radius: 20px !important;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5), var(--agy-accent-glow) !important;
  backdrop-filter: blur(20px) !important;
  -webkit-backdrop-filter: blur(20px) !important;
}}

/* User chat bubble */
[data-message-author-role="user"] > div:first-child {{
  background: var(--agy-card) !important;
  border: 1px solid var(--agy-card-border) !important;
  border-radius: 16px !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35) !important;
}}

/* Quick Input / Command Palette */
.quick-input-widget {{
  border-radius: 16px !important;
  background: var(--agy-composer-bg) !important;
  backdrop-filter: blur(28px) saturate(180%) !important;
  border: 1px solid var(--agy-border) !important;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.7), var(--agy-accent-glow) !important;
}}

/* --- 4. Universal IDE Typography --- */
body,
.monaco-workbench,
.monaco-shell,
.part,
.part.titlebar,
.part.sidebar,
.part.activitybar,
.part.statusbar,
.monaco-list,
.monaco-tree,
.action-label,
.label-name,
.quick-input-widget,
.monaco-inputbox input,
.monaco-select-box,
.interactive-session,
.chat-widget,
.rendered-markdown,
.font-sans,
[class*="font-sans"],
[class*="chat"],
[class*="agent"],
[class*="sidebar"],
[class*="jetski"] {{
  font-family: 'Outfit', 'Vazirmatn', 'Vazirmatn UI', 'Vazir', 'Estedad', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}}

/* --- 5. Persian BiDi in Chat, Prose & Markdown Previews --- */
.rendered-markdown p,
.rendered-markdown li,
.rendered-markdown h1,
.rendered-markdown h2,
.rendered-markdown h3,
.rendered-markdown h4,
.rendered-markdown h5,
.rendered-markdown h6,
.rendered-markdown blockquote,
.chat-item p,
.chat-response-text,
[class*="chat-message"] p,
[class*="chat-turn"] p,
[class*="prose"] p,
[class*="prose"] li,
[class*="prose"] h1,
[class*="prose"] h2,
[class*="prose"] h3,
[class*="markdown"] p,
[class*="markdown"] li,
.bidi-auto {{
  unicode-bidi: plaintext !important;
  text-align: start !important;
  line-height: 1.85 !important;
  letter-spacing: -0.01em !important;
}}

[dir="rtl"],
.rtl,
.bidi-rtl,
:lang(fa),
:lang(ar) {{
  direction: rtl !important;
  text-align: right !important;
  font-family: 'Vazirmatn', 'Vazirmatn UI', 'Vazir', 'Estedad', sans-serif !important;
}}

[dir="ltr"],
.ltr,
.bidi-ltr {{
  direction: ltr !important;
  text-align: left !important;
}}

textarea,
input,
[contenteditable="true"],
[class*="composer"],
[class*="chat-input"] {{
  font-family: 'Outfit', 'Vazirmatn', 'Estedad', sans-serif !important;
  unicode-bidi: plaintext !important;
}}

/* --- 6. Monaco Editor Persian & Markdown BiDi Engine --- */
.monaco-editor[data-mode-id="markdown"],
.monaco-editor[data-mode-id="plaintext"],
.editor-instance[aria-label*=".md"],
.editor-instance[aria-label*=".markdown"],
.monaco-editor[data-uri*=".md"],
.monaco-editor[data-uri*=".markdown"] {{
  font-family: 'Vazirmatn', 'Vazirmatn UI', 'Vazir', 'Estedad', 'Outfit', sans-serif !important;
}}

.monaco-editor[data-mode-id="markdown"] .view-line,
.monaco-editor[data-mode-id="plaintext"] .view-line,
.editor-instance[aria-label*=".md"] .view-line,
.editor-instance[aria-label*=".markdown"] .view-line,
.monaco-editor[data-uri*=".md"] .view-line,
.monaco-editor[data-uri*=".markdown"] .view-line {{
  font-family: 'Vazirmatn', 'Vazirmatn UI', 'Vazir', 'Estedad', 'Outfit', sans-serif !important;
  line-height: 1.85 !important;
}}

.monaco-editor .view-line.bidi-rtl-line,
.editor-instance[aria-label*=".md"] .view-line.bidi-rtl-line,
.editor-instance[aria-label*=".markdown"] .view-line.bidi-rtl-line,
.monaco-editor[data-uri*=".md"] .view-line.bidi-rtl-line {{
  direction: rtl !important;
  text-align: right !important;
  width: calc(100% - 24px) !important;
  font-family: 'Vazirmatn', 'Vazirmatn UI', 'Vazir', 'Estedad', sans-serif !important;
}}

.monaco-editor .view-line.bidi-rtl-line > span,
.editor-instance[aria-label*=".md"] .view-line.bidi-rtl-line > span,
.editor-instance[aria-label*=".markdown"] .view-line.bidi-rtl-line > span,
.monaco-editor[data-uri*=".md"] .view-line.bidi-rtl-line > span {{
  direction: rtl !important;
  unicode-bidi: plaintext !important;
  font-family: 'Vazirmatn', 'Vazirmatn UI', 'Vazir', 'Estedad', sans-serif !important;
}}

.monaco-editor .view-line.bidi-ltr-line,
.editor-instance[aria-label*=".md"] .view-line.bidi-ltr-line,
.monaco-editor .view-line:has([class*="fenced"]),
.monaco-editor .view-line:has([class*="code-block"]) {{
  direction: ltr !important;
  text-align: left !important;
  unicode-bidi: isolate !important;
}}

/* Code Blocks, Terminals & Formulas (100% LTR & Monospace) */
.terminal,
.terminal *,
.xterm,
.xterm *,
pre,
code,
kbd,
samp,
.monaco-tokenized-source,
[class*="code-block"],
.rendered-markdown pre,
.rendered-markdown code,
pre *,
code * {{
  direction: ltr !important;
  text-align: left !important;
  unicode-bidi: isolate !important;
  font-family: Consolas, 'Cascadia Code', 'Courier New', monospace !important;
}}

.katex,
.katex *,
.katex-display,
.katex-html,
math,
math * {{
  direction: ltr !important;
  text-align: left !important;
  unicode-bidi: isolate !important;
}}

/* Slim Sleek Scrollbars */
.monaco-scrollable-element > .scrollbar > .slider {{
  border-radius: 8px !important;
  background: rgba(255, 255, 255, 0.15) !important;
  transition: background 0.15s ease !important;
}}

.monaco-scrollable-element > .scrollbar > .slider:hover {{
  background: var(--agy-accent) !important;
}}

/* Floating Draggable Action HUD Pill - Placed in titlebar right to avoid blocking window title */
#agy-hud-pill {{
  position: fixed !important;
  top: 6px !important;
  right: 180px !important;
  left: auto !important;
  transform: none !important;
  z-index: 2147483647 !important;
  display: flex !important;
  align-items: center !important;
  gap: 6px !important;
  padding: 4px 12px !important;
  background: rgba(15, 23, 42, 0.92) !important;
  backdrop-filter: blur(28px) saturate(180%) !important;
  -webkit-backdrop-filter: blur(28px) saturate(180%) !important;
  border: 1px solid var(--agy-border) !important;
  border-radius: 9999px !important;
  box-shadow: 0 10px 35px rgba(0, 0, 0, 0.75), var(--agy-accent-glow) !important;
  user-select: none !important;
  font-family: var(--cpe-font) !important;
  transition: box-shadow 0.2s ease, border-color 0.2s ease !important;
  cursor: grab !important;
}}

#agy-hud-pill:hover {{
  border-color: var(--agy-accent) !important;
  box-shadow: 0 12px 42px rgba(0, 0, 0, 0.8), var(--agy-accent-glow) !important;
}}

.agy-hud-btn {{
  display: inline-flex !important;
  align-items: center !important;
  gap: 5px !important;
  padding: 4px 10px !important;
  background: rgba(255, 255, 255, 0.08) !important;
  border: 1px solid rgba(255, 255, 255, 0.14) !important;
  border-radius: 9999px !important;
  color: #f1f5f9 !important;
  font-size: 11px !important;
  font-weight: 600 !important;
  cursor: pointer !important;
  transition: all 0.16s ease !important;
  font-family: inherit !important;
}}

.agy-hud-btn:hover {{
  background: var(--agy-accent-soft) !important;
  color: var(--agy-accent) !important;
  border-color: var(--agy-accent) !important;
  transform: scale(1.04) !important;
}}

/* Modal Overlay & Sheet */
.agy-modal-overlay {{
  position: fixed !important;
  inset: 0 !important;
  background: rgba(0, 0, 0, 0.75) !important;
  backdrop-filter: blur(18px) !important;
  -webkit-backdrop-filter: blur(18px) !important;
  z-index: 1000000 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  opacity: 0 !important;
  pointer-events: none !important;
  transition: opacity 0.2s ease !important;
  font-family: var(--cpe-font) !important;
  direction: rtl !important;
}}

.agy-modal-overlay.agy-open {{
  opacity: 1 !important;
  pointer-events: auto !important;
}}

.agy-modal-sheet {{
  width: 540px !important;
  max-width: 94vw !important;
  max-height: 88vh !important;
  overflow-y: auto !important;
  background: #0f172a !important;
  border: 1px solid var(--agy-border) !important;
  border-radius: 22px !important;
  padding: 24px !important;
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.85), var(--agy-accent-glow) !important;
  color: #f8fafc !important;
  transform: scale(0.96) !important;
  transition: transform 0.2s ease !important;
}}

.agy-modal-overlay.agy-open .agy-modal-sheet {{
  transform: scale(1) !important;
}}

#agy-toast {{
  position: fixed !important;
  bottom: 32px !important;
  left: 50% !important;
  transform: translateX(-50%) translateY(20px) !important;
  background: rgba(15, 23, 42, 0.95) !important;
  border: 1px solid var(--agy-border) !important;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6), var(--agy-accent-glow) !important;
  color: #f8fafc !important;
  padding: 9px 20px !important;
  border-radius: 9999px !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  z-index: 1000002 !important;
  opacity: 0 !important;
  pointer-events: none !important;
  transition: all 0.25s ease !important;
  font-family: var(--cpe-font) !important;
  direction: rtl !important;
}}

#agy-toast.agy-toast-show {{
  opacity: 1 !important;
  transform: translateX(-50%) translateY(0) !important;
}}
"""

    custom_theme_path = wb_dir / "antigravity-custom-theme.css"
    custom_theme_path.write_text(theme_css, encoding="utf-8")
    print(f"✓ Created {custom_theme_path.name} ({len(theme_css)} chars)")

    # 3. Create antigravity-ide-enhancer.js (Trusted-types safe enhancer, live customizer & HUD)
    enhancer_js = """// Antigravity IDE Runtime BiDi, Theme Customizer & Neon Suite
// Fully integrated with Custom Themes (Cyberpunk, Synthwave, AMOLED, etc.), Fonts, HUD Pill & Modal
(() => {
  if (window.__agy_ide_enhancer_loaded) return;
  window.__agy_ide_enhancer_loaded = true;

  const STORAGE_KEY = 'agy_ide_theme_settings';
  const PERSIAN_REGEX = /[\\u0600-\\u06FF\\u0750-\\u077F\\uFB50-\\uFDFF\\uFE70-\\uFEFF]/;

  // Safe DOM helper that bypasses Trusted Types without throwing TypeError
  function setHTML(el, htmlString) {
    if (!el) return;
    try {
      const parser = new DOMParser();
      const doc = parser.parseFromString(htmlString, 'text/html');
      while (el.firstChild) el.removeChild(el.firstChild);
      while (doc.body.firstChild) el.appendChild(doc.body.firstChild);
    } catch (e) {
      try { el.innerHTML = htmlString; } catch (e2) {}
    }
  }

  // 1. Color Palettes & Themes
  const THEMES = {
    cyber: {
      name: '⚡️ سایبرپانک نئون (Cyan Neon - فیروزه‌ای درخشان)',
      accent: '#00f0ff',
      accentGlow: '0 0 20px rgba(0, 240, 255, 0.6)',
      accentSoft: 'rgba(0, 240, 255, 0.16)',
      border: 'rgba(0, 240, 255, 0.35)',
      bg: '#080c14',
      bgGradient: 'radial-gradient(ellipse 95% 70% at 50% -10%, rgba(0, 240, 255, 0.16) 0%, rgba(14, 28, 54, 0.72) 42%, #080c14 85%)',
      sidebar: '#060910',
      card: '#0f1728',
      cardBorder: 'rgba(0, 240, 255, 0.28)',
      composerBg: 'rgba(15, 23, 42, 0.95)',
      text: '#f1f5f9'
    },
    synthwave: {
      name: '💜 سینت‌ویو ۸۴ (SynthWave Neon - سرخابی و بنفش)',
      accent: '#ff007f',
      accentGlow: '0 0 22px rgba(255, 0, 127, 0.65)',
      accentSoft: 'rgba(255, 0, 127, 0.18)',
      border: 'rgba(255, 0, 127, 0.38)',
      bg: '#0d071a',
      bgGradient: 'radial-gradient(ellipse 95% 70% at 50% -10%, rgba(255, 0, 127, 0.18) 0%, rgba(42, 12, 64, 0.75) 42%, #0d071a 85%)',
      sidebar: '#080312',
      card: '#1a0d30',
      cardBorder: 'rgba(255, 0, 127, 0.32)',
      composerBg: 'rgba(24, 13, 46, 0.95)',
      text: '#fff0f8'
    },
    amoled: {
      name: '🖤 آمولد بلک و شیشه‌ای (Pure AMOLED & Glass)',
      accent: '#38bdf8',
      accentGlow: '0 0 16px rgba(56, 189, 248, 0.45)',
      accentSoft: 'rgba(255, 255, 255, 0.08)',
      border: 'rgba(255, 255, 255, 0.2)',
      bg: '#000000',
      bgGradient: 'radial-gradient(ellipse 95% 70% at 50% -10%, rgba(56, 189, 248, 0.12) 0%, rgba(10, 22, 38, 0.5) 40%, #000000 80%)',
      sidebar: '#040404',
      card: '#0d0d0d',
      cardBorder: 'rgba(255, 255, 255, 0.16)',
      composerBg: '#080808',
      text: '#ffffff'
    },
    midnight: {
      name: '🌌 میدنایت ایندیگو (Midnight Indigo - سرمه‌ای نیلی)',
      accent: '#818cf8',
      accentGlow: '0 0 20px rgba(129, 140, 248, 0.55)',
      accentSoft: 'rgba(99, 102, 241, 0.16)',
      border: 'rgba(99, 102, 241, 0.3)',
      bg: '#0a0e1a',
      bgGradient: 'radial-gradient(ellipse 95% 70% at 50% -10%, rgba(129, 140, 248, 0.18) 0%, rgba(25, 32, 66, 0.75) 42%, #0a0e1a 85%)',
      sidebar: '#060912',
      card: '#12182c',
      cardBorder: 'rgba(99, 102, 241, 0.26)',
      composerBg: 'rgba(18, 24, 44, 0.95)',
      text: '#f8fafc'
    },
    emerald: {
      name: '🟢 ماتریکس زمردی (Emerald Matrix - سبز نئونی)',
      accent: '#10b981',
      accentGlow: '0 0 20px rgba(16, 185, 129, 0.55)',
      accentSoft: 'rgba(16, 185, 129, 0.16)',
      border: 'rgba(16, 185, 129, 0.3)',
      bg: '#06100a',
      bgGradient: 'radial-gradient(ellipse 95% 70% at 50% -10%, rgba(16, 185, 129, 0.18) 0%, rgba(12, 44, 26, 0.75) 42%, #06100a 85%)',
      sidebar: '#030805',
      card: '#0c2014',
      cardBorder: 'rgba(16, 185, 129, 0.26)',
      composerBg: 'rgba(10, 26, 17, 0.95)',
      text: '#ecfdf5'
    },
    sunset: {
      name: '🌅 سان‌ست ویپرویو (Sunset Vaporwave - طلایی و کهربایی)',
      accent: '#f59e0b',
      accentGlow: '0 0 20px rgba(245, 158, 11, 0.55)',
      accentSoft: 'rgba(245, 158, 11, 0.16)',
      border: 'rgba(245, 158, 11, 0.3)',
      bg: '#140c06',
      bgGradient: 'radial-gradient(ellipse 95% 70% at 50% -10%, rgba(245, 158, 11, 0.18) 0%, rgba(55, 26, 10, 0.75) 42%, #140c06 85%)',
      sidebar: '#0a0502',
      card: '#24140b',
      cardBorder: 'rgba(245, 158, 11, 0.26)',
      composerBg: 'rgba(32, 18, 9, 0.95)',
      text: '#fffbeb'
    },
    clean_dark: {
      name: '⚪️ دارک اسلیت مدرن (Modern Dark Slate)',
      accent: '#38bdf8',
      accentGlow: '0 0 14px rgba(56, 189, 248, 0.35)',
      accentSoft: 'rgba(56, 189, 248, 0.12)',
      border: 'rgba(255, 255, 255, 0.15)',
      bg: '#0e1117',
      bgGradient: 'radial-gradient(ellipse 95% 70% at 50% -10%, rgba(56, 189, 248, 0.12) 0%, rgba(26, 32, 44, 0.7) 42%, #0e1117 85%)',
      sidebar: '#0c0e12',
      card: '#181b22',
      cardBorder: 'rgba(255, 255, 255, 0.14)',
      composerBg: 'rgba(24, 27, 34, 0.94)',
      text: '#f8fafc'
    }
  };

  const DEFAULT_SETTINGS = {
    theme: 'cyber',
    fontFa: 'Vazirmatn',
    fontEn: 'Outfit',
    strokeMode: 'glow',
    fontSize: 14.5,
    rtlAuto: true
  };

  function loadSettings() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      return { ...DEFAULT_SETTINGS, ...saved };
    } catch (e) {
      return DEFAULT_SETTINGS;
    }
  }

  function saveSettings(patch) {
    const current = loadSettings();
    const updated = { ...current, ...patch };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    } catch (e) {}
    applyThemeAndFont();
    return updated;
  }

  // 2. Dynamic Style Injection Engine
  let dynamicStyleEl = document.getElementById('agy-dynamic-theme-style');
  if (!dynamicStyleEl) {
    dynamicStyleEl = document.createElement('style');
    dynamicStyleEl.id = 'agy-dynamic-theme-style';
    (document.head || document.documentElement).appendChild(dynamicStyleEl);
  }

  function applyThemeAndFont() {
    const s = loadSettings();
    const t = THEMES[s.theme] || THEMES.cyber;

    // Set theme attribute on root and body for immediate CSS rule cascading
    document.documentElement.setAttribute('data-agy-theme', s.theme);
    if (document.body) document.body.setAttribute('data-agy-theme', s.theme);

    const fontEnPart = (s.fontEn && s.fontEn !== 'system') ? `'${s.fontEn}', ` : '';
    const fontFaPart = (s.fontFa && s.fontFa !== 'system') ? `'${s.fontFa}', ` : "'Vazirmatn', ";
    const combinedFont = `${fontEnPart}${fontFaPart}-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`;

    const glowShadow = s.strokeMode === 'glow' ? t.accentGlow : (s.strokeMode === 'refined' ? `0 0 10px ${t.accentSoft}` : 'none');

    dynamicStyleEl.textContent = `
      :root {
        --cpe-font: ${combinedFont};
        --cpe-font-size: ${s.fontSize}px;
        --cpe-accent: ${t.accent};
        --cpe-accent-glow: ${t.accentGlow};
        --cpe-border: ${t.border};
        --agy-bg: ${t.bg};
        --agy-bg-gradient: ${t.bgGradient};
        --agy-accent: ${t.accent};
        --agy-accent-glow: ${t.accentGlow};
        --agy-accent-soft: ${t.accentSoft};
        --agy-border: ${t.border};
        --agy-card: ${t.card};
        --agy-card-border: ${t.cardBorder};
        --agy-sidebar: ${t.sidebar};
        --agy-composer-bg: ${t.composerBg};
        --agy-text: ${t.text};
        --vscode-editor-background: transparent !important;
        --vscode-sideBar-background: transparent !important;
        --vscode-sideBarTitle-background: transparent !important;
        --vscode-sideBarSectionHeader-background: transparent !important;
        --vscode-editorGroupHeader-tabsBackground: transparent !important;
        --vscode-editorGroupHeader-noTabsBackground: transparent !important;
        --vscode-tab-inactiveBackground: transparent !important;
        --vscode-tab-activeBackground: rgba(255, 255, 255, 0.08) !important;
      }

      body,
      .monaco-workbench,
      .monaco-shell,
      .part,
      .action-label,
      .label-name,
      .quick-input-widget,
      .font-sans,
      [class*="font-sans"],
      [class*="chat"],
      [class*="agent"],
      [class*="jetski"] {
        font-family: var(--cpe-font) !important;
      }
    `;
  }

  // 3. Process Monaco Editor Lines (Smart BiDi)
  function processMonacoLine(line) {
    if (!line || line.nodeType !== 1) return;
    if (!line.classList || !line.classList.contains('view-line')) return;
    const text = line.textContent || '';
    if (!text.trim()) return;

    if (PERSIAN_REGEX.test(text)) {
      if (!line.classList.contains('bidi-rtl-line')) {
        line.classList.add('bidi-rtl-line');
        line.classList.remove('bidi-ltr-line');
        line.setAttribute('dir', 'rtl');
        line.style.setProperty('direction', 'rtl', 'important');
        line.style.setProperty('text-align', 'right', 'important');
        line.style.setProperty('width', 'calc(100% - 24px)', 'important');
        line.style.setProperty('font-family', "'Vazirmatn', 'Vazirmatn UI', 'Vazir', 'Estedad', sans-serif", 'important');
      }
    } else {
      if (!line.classList.contains('bidi-ltr-line')) {
        line.classList.add('bidi-ltr-line');
        line.classList.remove('bidi-rtl-line');
        line.setAttribute('dir', 'ltr');
        line.style.removeProperty('direction');
        line.style.removeProperty('text-align');
        line.style.removeProperty('width');
        line.style.removeProperty('font-family');
      }
    }
  }

  // 4. Process Chat & Markdown elements
  function processElement(el) {
    if (!el || el.nodeType !== 1) return;
    const tag = el.tagName.toLowerCase();
    if (tag === 'pre' || tag === 'code' || tag === 'script' || tag === 'style') return;
    if (el.classList && (el.classList.contains('terminal') || el.classList.contains('katex') || el.classList.contains('xterm'))) return;

    if (el.classList && el.classList.contains('view-line')) {
      processMonacoLine(el);
      return;
    }

    if (['p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'div', 'span', 'textarea'].includes(tag)) {
      const text = el.innerText || el.textContent || '';
      if (text.length > 1 && PERSIAN_REGEX.test(text)) {
        if (!el.classList.contains('bidi-rtl')) {
          el.classList.add('bidi-rtl');
          el.setAttribute('dir', 'rtl');
          el.style.setProperty('direction', 'rtl', 'important');
          el.style.setProperty('text-align', 'right', 'important');
          el.style.setProperty('font-family', "'Vazirmatn', 'Vazirmatn UI', 'Vazir', 'Estedad', sans-serif", 'important');
        }
      }
    }
  }

  function scanAll(root = document.body) {
    if (!root) return;
    const lines = root.querySelectorAll('.view-lines .view-line');
    for (let i = 0; i < lines.length; i++) {
      processMonacoLine(lines[i]);
    }

    const blocks = root.querySelectorAll('.rendered-markdown p, .rendered-markdown li, [class*="chat"] p, [class*="message"] p, [class*="turn"] p, .prose p, .prose li');
    for (let i = 0; i < blocks.length; i++) {
      processElement(blocks[i]);
    }
  }

  // 5. Toast System
  function showToast(msg) {
    let t = document.getElementById('agy-toast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'agy-toast';
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.classList.add('agy-toast-show');
    setTimeout(() => {
      t.classList.remove('agy-toast-show');
    }, 2800);
  }

  // 6. Modal Factory
  function createModal(id, title, bodyHtml) {
    let m = document.getElementById(id);
    if (m) m.remove();

    m = document.createElement('div');
    m.id = id;
    m.className = 'agy-modal-overlay';
    
    setHTML(m, `
      <div class="agy-modal-sheet">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.12); padding-bottom: 14px;">
          <h3 style="margin: 0; font-size: 16px; font-weight: 700; color: #fff;">${title}</h3>
          <button class="agy-modal-close" style="background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); color: #cbd5e1; width: 28px; height: 28px; border-radius: 50%; cursor: pointer; font-size: 14px; display: flex; align-items: center; justify-content: center;">✕</button>
        </div>
        <div class="agy-modal-body">
          ${bodyHtml}
        </div>
      </div>
    `);

    document.body.appendChild(m);

    const closeBtn = m.querySelector('.agy-modal-close');
    if (closeBtn) closeBtn.onclick = () => m.classList.remove('agy-open');
    m.onclick = (e) => {
      if (e.target === m) m.classList.remove('agy-open');
    };
    return m;
  }

  // 7. Theme & Neon Customizer Modal
  function openThemeModal() {
    const s = loadSettings();

    const themesList = [
      { id: 'cyber', label: '⚡️ سایبرپانک نئون (Cyan Neon - فیروزه‌ای درخشان)' },
      { id: 'synthwave', label: '💜 سینت‌ویو ۸۴ (SynthWave - سرخابی نئونی و بنفش)' },
      { id: 'amoled', label: '🖤 آمولد بلک و شیشه‌ای (Pure AMOLED & Glass)' },
      { id: 'midnight', label: '🌌 میدنایت ایندیگو (Midnight Indigo - سرمه‌ای نیلی)' },
      { id: 'emerald', label: '🟢 ماتریکس زمردی (Emerald Matrix - سبز نئونی)' },
      { id: 'sunset', label: '🌅 سان‌ست ویپرویو (Sunset Vaporwave - طلایی و کهربایی)' },
      { id: 'clean_dark', label: '⚪️ دارک اسلیت مدرن (Modern Dark Slate)' }
    ];

    const fontsFa = [
      { id: 'Vazirmatn', label: 'وزیرمتن (Vazirmatn - استاندارد و مدرن)' },
      { id: 'Estedad', label: 'استعداد (Estedad - هندسی و پویا)' },
      { id: 'Vazir', label: 'وزیر کلاسیک (Vazir)' },
      { id: 'system', label: 'فونت پیش‌فرض سیستم' }
    ];

    const fontsEn = [
      { id: 'Outfit', label: 'Outfit (مدرن و تمیز - توصیه شده)' },
      { id: 'JetBrains Mono', label: 'JetBrains Mono (تک‌فاصله برنامه‌نویسی)' },
      { id: 'Consolas', label: 'Consolas (کلاسیک ویندوز)' },
      { id: 'Cascadia Code', label: 'Cascadia Code' }
    ];

    const strokeModes = [
      { id: 'glow', label: '🌟 درخشش نئونی کامل و خیره‌کننده (High Neon Glow)' },
      { id: 'refined', label: '💎 کادربندی شیشه‌ای و نئون ملایم (Refined Glass Glow)' },
      { id: 'subtle', label: '▫️ حالت مینیمال و خطی (Subtle 1px)' }
    ];

    const html = `
      <div style="margin-bottom: 14px;">
        <label style="display: block; font-size: 12px; color: #94a3b8; margin-bottom: 6px;">🎨 انتخاب پالت رنگ و تم Antigravity:</label>
        <select id="agy-sel-theme" style="width: 100%; padding: 10px; border-radius: 10px; background: #1e293b; color: #fff; border: 1px solid rgba(255,255,255,0.18); font-family: inherit;">
          ${themesList.map(t => `<option value="${t.id}" ${s.theme === t.id ? 'selected' : ''}>${t.label}</option>`).join('')}
        </select>
      </div>

      <div style="margin-bottom: 14px;">
        <label style="display: block; font-size: 12px; color: #94a3b8; margin-bottom: 6px;">💫 شدت روشنایی نئون و کادر (Neon Glow Effect):</label>
        <select id="agy-sel-stroke" style="width: 100%; padding: 10px; border-radius: 10px; background: #1e293b; color: #fff; border: 1px solid rgba(255,255,255,0.18); font-family: inherit;">
          ${strokeModes.map(m => `<option value="${m.id}" ${s.strokeMode === m.id ? 'selected' : ''}>${m.label}</option>`).join('')}
        </select>
      </div>

      <div style="margin-bottom: 14px;">
        <label style="display: block; font-size: 12px; color: #94a3b8; margin-bottom: 6px;">✍️ انتخاب فونت فارسی (آفلاین WOFF2):</label>
        <select id="agy-sel-font-fa" style="width: 100%; padding: 10px; border-radius: 10px; background: #1e293b; color: #fff; border: 1px solid rgba(255,255,255,0.18); font-family: inherit;">
          ${fontsFa.map(f => `<option value="${f.id}" ${s.fontFa === f.id ? 'selected' : ''}>${f.label}</option>`).join('')}
        </select>
      </div>

      <div style="margin-bottom: 14px;">
        <label style="display: block; font-size: 12px; color: #94a3b8; margin-bottom: 6px;">🔤 انتخاب فونت انگلیسی و رابط کاربری:</label>
        <select id="agy-sel-font-en" style="width: 100%; padding: 10px; border-radius: 10px; background: #1e293b; color: #fff; border: 1px solid rgba(255,255,255,0.18); font-family: inherit;">
          ${fontsEn.map(f => `<option value="${f.id}" ${s.fontEn === f.id ? 'selected' : ''}>${f.label}</option>`).join('')}
        </select>
      </div>

      <div style="margin-bottom: 14px;">
        <div style="display: flex; justify-content: space-between; font-size: 12px; color: #94a3b8; margin-bottom: 6px;">
          <span>📏 اندازه فونت (Font Size):</span>
          <span id="agy-val-font-size" style="color: #00f0ff; font-weight: 700;">${s.fontSize}px</span>
        </div>
        <input type="range" id="agy-rng-font-size" min="13" max="18" step="0.5" value="${s.fontSize}" style="width: 100%; accent-color: #00f0ff; cursor: pointer;">
      </div>

      <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px; background: rgba(255,255,255,0.05); border-radius: 12px; margin-bottom: 20px;">
        <span style="font-size: 13px;">↔️ راست‌چین‌سازی خودکار متن فارسی (Smart BiDi):</span>
        <input type="checkbox" id="agy-chk-rtl" ${s.rtlAuto ? 'checked' : ''} style="width: 18px; height: 18px; cursor: pointer; accent-color: #00f0ff;">
      </div>

      <div style="display: flex; gap: 10px;">
        <button id="agy-btn-reset-theme" style="flex: 1; padding: 12px; background: rgba(255,255,255,0.08); color: #cbd5e1; border: 1px solid rgba(255,255,255,0.18); border-radius: 12px; cursor: pointer; font-size: 13px; font-family: inherit;">
          بازنشانی
        </button>
        <button id="agy-btn-save-theme" style="flex: 2; padding: 12px; background: #00f0ff; color: #000; font-weight: 700; border: none; border-radius: 12px; cursor: pointer; font-size: 14px; font-family: inherit; box-shadow: 0 0 16px rgba(0, 240, 255, 0.45); transition: all 0.2s ease;">
          ذخیره و تایید
        </button>
      </div>
    `;

    const modal = createModal('agy-modal-theme', '🎨 تنظیمات تم رنگی، نئون و فونت Antigravity IDE', html);
    modal.classList.add('agy-open');

    const rng = document.getElementById('agy-rng-font-size');
    const valLbl = document.getElementById('agy-val-font-size');
    
    // Live instantaneous update trigger
    const triggerLive = () => {
      const theme = document.getElementById('agy-sel-theme').value;
      const strokeMode = document.getElementById('agy-sel-stroke').value;
      const fontFa = document.getElementById('agy-sel-font-fa').value;
      const fontEn = document.getElementById('agy-sel-font-en').value;
      const fontSize = parseFloat(document.getElementById('agy-rng-font-size').value);
      const rtlAuto = document.getElementById('agy-chk-rtl').checked;
      saveSettings({ theme, strokeMode, fontFa, fontEn, fontSize, rtlAuto });
    };

    document.getElementById('agy-sel-theme').onchange = triggerLive;
    document.getElementById('agy-sel-stroke').onchange = triggerLive;
    document.getElementById('agy-sel-font-fa').onchange = triggerLive;
    document.getElementById('agy-sel-font-en').onchange = triggerLive;
    document.getElementById('agy-chk-rtl').onchange = triggerLive;
    if (rng && valLbl) {
      rng.oninput = () => {
        valLbl.textContent = `${rng.value}px`;
        triggerLive();
      };
    }

    document.getElementById('agy-btn-reset-theme').onclick = () => {
      saveSettings(DEFAULT_SETTINGS);
      modal.classList.remove('agy-open');
      showToast('🔄 تنظیمات تم و نئون به حالت پیش‌فرض بازگشت');
    };

    document.getElementById('agy-btn-save-theme').onclick = () => {
      triggerLive();
      modal.classList.remove('agy-open');
      showToast('🎨 تم و جلوه‌های نئون با موفقیت ذخیره شدند');
    };
  }

  // 8. Accounts Management Modal
  async function openAccountsModal() {
    const modal = createModal('agy-modal-account', '🔐 مدیریت حساب‌ها و سوییچر Antigravity', `
      <div style="padding: 12px 14px; background: rgba(0, 240, 255, 0.08); border: 1px solid rgba(0, 240, 255, 0.25); border-radius: 14px; margin-bottom: 14px; display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #00f0ff; box-shadow: 0 0 10px #00f0ff;"></span>
          <span style="font-size: 12.5px; color: #cbd5e1;">وضعیت سوییچر خودکار:</span>
        </div>
        <span style="font-size: 12px; font-weight: 700; color: #00f0ff;">فعال و آماده</span>
      </div>

      <div style="font-size: 12.5px; color: #94a3b8; line-height: 1.7; margin-bottom: 16px;">
        برای جابه‌جایی سریع بین توکن‌ها، تخصیص سهمیه هوشمند و مدیریت اکانت‌ها می‌توانید پنل مدیریت را باز کنید:
      </div>

      <div style="display: flex; flex-direction: column; gap: 10px;">
        <button id="agy-btn-launch-gui" style="padding: 12px; background: #00f0ff; color: #000; border: none; border-radius: 12px; font-weight: 700; font-size: 13px; cursor: pointer; font-family: inherit; box-shadow: 0 0 14px rgba(0, 240, 255, 0.35);">
          🚀 باز کردن پنل گرافیکی سوییچر اکانت (GUI)
        </button>
      </div>
    `);
    modal.classList.add('agy-open');

    const guiBtn = document.getElementById('agy-btn-launch-gui');
    if (guiBtn) {
      guiBtn.onclick = () => {
        window.open('http://127.0.0.1:39285', '_blank');
        showToast('🚀 پنل سوییچر باز شد');
        modal.classList.remove('agy-open');
      };
    }
  }

  // 9. Floating Draggable Action HUD Pill
  function renderHUD() {
    if (window !== window.top) return; // Only show on top workbench window

    let hud = document.getElementById('agy-hud-pill');
    if (hud) return; // Already exists

    hud = document.createElement('div');
    hud.id = 'agy-hud-pill';

    setHTML(hud, `
      <span id="agy-hud-drag-handle" style="cursor: grab; display: flex; align-items: center; gap: 6px; padding: 2px 4px; user-select: none;" title="برای جابه‌جایی نوار، اینجا را بگیرید و بکشید">
        <span style="font-size: 13px; color: rgba(255,255,255,0.45); font-family: monospace;">⠿</span>
        <span style="width: 8px; height: 8px; border-radius: 50%; background: #00f0ff; box-shadow: 0 0 8px #00f0ff;"></span>
        <span style="font-size: 11px; font-weight: 700; color: #00f0ff; letter-spacing: 0.5px;">AGY Pro</span>
      </span>
      <div style="display: flex; align-items: center; gap: 3px; border-right: 1px solid rgba(255,255,255,0.15); border-left: 1px solid rgba(255,255,255,0.15); padding: 0 6px;">
        <button class="agy-quick-theme-btn" data-theme="cyber" title="سایبرپانک نئون (فیروزه‌ای)" style="background: none; border: none; cursor: pointer; font-size: 13px; padding: 2px; border-radius: 4px; transition: transform 0.15s ease;">⚡️</button>
        <button class="agy-quick-theme-btn" data-theme="synthwave" title="سینت‌ویو ۸۴ (سرخابی و بنفش)" style="background: none; border: none; cursor: pointer; font-size: 13px; padding: 2px; border-radius: 4px; transition: transform 0.15s ease;">💜</button>
        <button class="agy-quick-theme-btn" data-theme="emerald" title="ماتریکس زمردی (سبز)" style="background: none; border: none; cursor: pointer; font-size: 13px; padding: 2px; border-radius: 4px; transition: transform 0.15s ease;">🟢</button>
        <button class="agy-quick-theme-btn" data-theme="sunset" title="افق سان‌ست (طلایی)" style="background: none; border: none; cursor: pointer; font-size: 13px; padding: 2px; border-radius: 4px; transition: transform 0.15s ease;">🌅</button>
        <button class="agy-quick-theme-btn" data-theme="amoled" title="آمولد خالص (مشکی مطلق)" style="background: none; border: none; cursor: pointer; font-size: 13px; padding: 2px; border-radius: 4px; transition: transform 0.15s ease;">🖤</button>
      </div>
      <button class="agy-hud-btn" id="agy-btn-theme" title="تنظیمات تم رنگی، درخشش نئون و فونت‌ها (Alt + T)">
        🎨 <span>تم و نئون</span>
      </button>
      <button class="agy-hud-btn" id="agy-btn-accounts" title="مدیریت و سوئیچ بین اکانت‌ها (Alt + A)">
        🔄 <span>اکانت‌ها</span>
      </button>
    `);

    // Mount inside document.body
    const mountParent = document.body || document.documentElement;
    mountParent.appendChild(hud);

    // Quick theme click listeners
    hud.querySelectorAll('.agy-quick-theme-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const th = btn.getAttribute('data-theme');
        if (th && THEMES[th]) {
          saveSettings({ theme: th });
          showToast(`🎨 تم ${THEMES[th].name.split('(')[0].trim()} فعال شد`);
        }
      });
      btn.addEventListener('mouseenter', () => btn.style.transform = 'scale(1.25)');
      btn.addEventListener('mouseleave', () => btn.style.transform = 'scale(1)');
    });

    // Restore saved position only if explicitly dragged with v2 key
    try {
      const savedPos = JSON.parse(localStorage.getItem('agy_hud_pill_pos_v2') || 'null');
      if (savedPos && typeof savedPos.x === 'number') {
        const maxX = Math.max(10, window.innerWidth - 380);
        const maxY = Math.max(10, window.innerHeight - 50);
        hud.style.left = `${Math.min(Math.max(10, savedPos.x), maxX)}px`;
        hud.style.top = `${Math.min(Math.max(6, savedPos.y), maxY)}px`;
        hud.style.transform = 'none';
      }
    } catch(e) {}

    // Dragging Logic
    let isDragging = false;
    let startX = 0, startY = 0;
    let initialLeft = 0, initialTop = 0;

    hud.addEventListener('mousedown', (e) => {
      if (e.target.closest('button') || e.target.closest('.agy-hud-btn') || e.target.closest('.agy-quick-theme-btn')) return;
      isDragging = true;
      startX = e.clientX;
      startY = e.clientY;
      const rect = hud.getBoundingClientRect();
      initialLeft = rect.left;
      initialTop = rect.top;

      hud.style.transform = 'none';
      hud.style.left = `${initialLeft}px`;
      hud.style.top = `${initialTop}px`;
      hud.style.transition = 'none';
      hud.style.cursor = 'grabbing';
      document.body.style.userSelect = 'none';

      const onMouseMove = (ev) => {
        if (!isDragging) return;
        const dx = ev.clientX - startX;
        const dy = ev.clientY - startY;

        let newX = initialLeft + dx;
        let newY = initialTop + dy;

        const maxX = window.innerWidth - hud.offsetWidth - 10;
        const maxY = window.innerHeight - hud.offsetHeight - 10;
        hud.style.left = `${Math.max(10, Math.min(newX, maxX))}px`;
        hud.style.top = `${Math.max(6, Math.min(newY, maxY))}px`;
      };

      const onMouseUp = () => {
        if (!isDragging) return;
        isDragging = false;
        hud.style.transition = 'box-shadow 0.2s ease';
        hud.style.cursor = 'grab';
        document.body.style.userSelect = '';
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);

        const finalRect = hud.getBoundingClientRect();
        try {
          localStorage.setItem('agy_hud_pill_pos_v2', JSON.stringify({ x: finalRect.left, y: finalRect.top }));
        } catch(e) {}
      };

      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    });

    // Buttons
    const btnTheme = document.getElementById('agy-btn-theme');
    const btnAccounts = document.getElementById('agy-btn-accounts');
    if (btnTheme) btnTheme.onclick = () => openThemeModal();
    if (btnAccounts) btnAccounts.onclick = () => openAccountsModal();
  }

  // 10. Native Status Bar Integration
  function attachStatusBarButton() {
    if (document.getElementById('agy-statusbar-theme-btn')) return;
    const bar = document.querySelector('.part.statusbar .right-items') || 
                document.querySelector('.part.statusbar') || 
                document.getElementById('status.bar');
    if (!bar) return;

    const btn = document.createElement('div');
    btn.id = 'agy-statusbar-theme-btn';
    btn.className = 'statusbar-item right';
    btn.style.cssText = 'cursor: pointer; display: inline-flex; align-items: center; gap: 4px; padding: 0 8px; font-size: 11px; font-weight: 600; color: #00f0ff; line-height: 22px; user-select: none;';
    btn.title = 'تنظیمات تم رنگی، نئون و فونت Antigravity (Alt + T)';
    setHTML(btn, `<span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:#00f0ff; box-shadow:0 0 6px #00f0ff;"></span> 🎨 تم و نئون`);
    btn.onclick = () => openThemeModal();
    bar.appendChild(btn);
  }

  // 11. Global Keyboard Shortcuts
  window.addEventListener('keydown', (e) => {
    if (e.altKey && (e.key === 't' || e.key === 'T' || e.key === 'ف')) {
      e.preventDefault();
      openThemeModal();
    }
    if (e.altKey && (e.key === 'a' || e.key === 'A' || e.key === 'ش')) {
      e.preventDefault();
      openAccountsModal();
    }
    if (e.key === 'Escape') {
      const openModal = document.querySelector('.agy-modal-overlay.agy-open');
      if (openModal) openModal.classList.remove('agy-open');
    }
  });

  // Cross-window sync (when changed in one panel/window, update all)
  window.addEventListener('storage', (e) => {
    if (e.key === STORAGE_KEY) {
      applyThemeAndFont();
    }
  });

  // 12. Observers & Initialization
  applyThemeAndFont();

  const observer = new MutationObserver(mutations => {
    for (const m of mutations) {
      if (m.target && m.target.nodeType === 1 && m.target.classList && m.target.classList.contains('view-line')) {
        processMonacoLine(m.target);
      }
      for (const node of m.addedNodes) {
        if (node.nodeType === 1) {
          if (node.classList && node.classList.contains('view-line')) {
            processMonacoLine(node);
          } else {
            const nestedLines = node.querySelectorAll ? node.querySelectorAll('.view-line') : [];
            for (let i = 0; i < nestedLines.length; i++) {
              processMonacoLine(nestedLines[i]);
            }
          }
          processElement(node);
        }
      }
    }
  });

  const startAll = () => {
    applyThemeAndFont();
    renderHUD();
    attachStatusBarButton();
    if (document.body) {
      observer.observe(document.body, { childList: true, subtree: true, characterData: true });
      scanAll(document.body);
    }
    setInterval(() => {
      if (document.body) scanAll(document.body);
      if (!document.getElementById('agy-hud-pill') && window === window.top) {
        renderHUD();
      }
      attachStatusBarButton();
    }, 400);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startAll, { once: true });
  } else {
    startAll();
  }
})();
"""
    enhancer_path = wb_dir / "antigravity-ide-enhancer.js"
    enhancer_path.write_text(enhancer_js, encoding="utf-8")
    print(f"✓ Created {enhancer_path.name}")

    # 4. Patch workbench.desktop.main.css
    wb_css_path = wb_dir / "workbench.desktop.main.css"
    if wb_css_path.exists():
        wb_css_content = wb_css_path.read_text(encoding="utf-8")
        import_stmt = "@import url('./antigravity-custom-theme.css');\n"
        if import_stmt not in wb_css_content:
            bak = wb_css_path.with_suffix(".css.bak")
            if not bak.exists():
                shutil.copy2(wb_css_path, bak)
            wb_css_path.write_text(import_stmt + wb_css_content, encoding="utf-8")
            print("✓ Injected theme import into workbench.desktop.main.css")
        else:
            print("✓ workbench.desktop.main.css already includes custom theme import")

    # 5. Patch jetskiMain.tailwind.css
    jetski_css_path = out_dir / "jetskiMain.tailwind.css"
    if jetski_css_path.exists():
        jetski_css = jetski_css_path.read_text(encoding="utf-8")
        import_stmt_jetski = "@import url('./vs/workbench/antigravity-custom-theme.css');\n"
        if import_stmt_jetski not in jetski_css:
            bak = jetski_css_path.with_suffix(".css.bak")
            if not bak.exists():
                shutil.copy2(jetski_css_path, bak)
            jetski_css_path.write_text(import_stmt_jetski + jetski_css, encoding="utf-8")
            print("✓ Injected theme import into jetskiMain.tailwind.css")
        else:
            print("✓ jetskiMain.tailwind.css already includes custom theme import")

    # 6. Inject Enhancer into workbench.desktop.main.js & jetskiAgent/main.js
    marker_start = "/* --- ANTIGRAVITY IDE THEME & ENHANCER SUITE BEGIN --- */"
    marker_end = "/* --- ANTIGRAVITY IDE THEME & ENHANCER SUITE END --- */"
    bundle_snippet = f"\n\n{marker_start}\n{enhancer_js}\n{marker_end}\n"

    wb_js_path = wb_dir / "workbench.desktop.main.js"
    if wb_js_path.exists():
        wb_js_content = wb_js_path.read_text(encoding="utf-8")
        bak_wb_js = wb_js_path.with_suffix(".js.bak")
        if not bak_wb_js.exists():
            shutil.copy2(wb_js_path, bak_wb_js)

        if marker_start in wb_js_content and marker_end in wb_js_content:
            before, rest = wb_js_content.split(marker_start, 1)
            _, after = rest.split(marker_end, 1)
            wb_js_content = f"{before}{marker_start}\n{enhancer_js}\n{marker_end}{after}"
            wb_js_path.write_text(wb_js_content, encoding="utf-8")
            print("✓ Updated enhancer code inside workbench.desktop.main.js")
        else:
            wb_js_path.write_text(wb_js_content + bundle_snippet, encoding="utf-8")
            print("✓ Injected enhancer code into workbench.desktop.main.js")

    # Also inject into jetskiAgent.js (agent module entrypoint)
    jetski_agent_js = out_dir / "vs" / "code" / "electron-browser" / "workbench" / "jetskiAgent.js"
    if jetski_agent_js.exists():
        js_content = jetski_agent_js.read_text(encoding="utf-8")
        bak_jetski = jetski_agent_js.with_suffix(".js.bak")
        if not bak_jetski.exists():
            shutil.copy2(jetski_agent_js, bak_jetski)

        if marker_start in js_content and marker_end in js_content:
            before, rest = js_content.split(marker_start, 1)
            _, after = rest.split(marker_end, 1)
            js_content = f"{before}{marker_start}\n{enhancer_js}\n{marker_end}{after}"
            jetski_agent_js.write_text(js_content, encoding="utf-8")
            print("✓ Updated enhancer code inside jetskiAgent.js")
        else:
            jetski_agent_js.write_text(js_content + bundle_snippet, encoding="utf-8")
            print("✓ Injected enhancer code into jetskiAgent.js")

    jetski_js_path = out_dir / "jetskiAgent" / "main.js"
    if jetski_js_path.exists():
        jetski_js_content = jetski_js_path.read_text(encoding="utf-8")
        bak_jetski_main = jetski_js_path.with_suffix(".js.bak")
        if not bak_jetski_main.exists():
            shutil.copy2(jetski_js_path, bak_jetski_main)

        if marker_start in jetski_js_content and marker_end in jetski_js_content:
            before, rest = jetski_js_content.split(marker_start, 1)
            _, after = rest.split(marker_end, 1)
            jetski_js_content = f"{before}{marker_start}\n{enhancer_js}\n{marker_end}{after}"
            jetski_js_path.write_text(jetski_js_content, encoding="utf-8")
            print("✓ Updated enhancer code inside jetskiAgent/main.js")
        else:
            jetski_js_path.write_text(jetski_js_content + bundle_snippet, encoding="utf-8")
            print("✓ Injected enhancer code into jetskiAgent/main.js")

    # 7. Patch workbench.html & workbench-jetski-agent.html
    html_files = [
        out_dir / "vs" / "code" / "electron-browser" / "workbench" / "workbench.html",
        out_dir / "vs" / "code" / "electron-browser" / "workbench" / "workbench-jetski-agent.html"
    ]

    for html_path in html_files:
        if not html_path.exists():
            continue
        content = html_path.read_text(encoding="utf-8")
        bak = html_path.with_suffix(".html.bak")
        if not bak.exists():
            shutil.copy2(html_path, bak)

        # 7a. Remove stale rtl-agents block if present
        if "<!-- RTL-AGENTS-BEGIN -->" in content:
            content = re.sub(r'\s*<!-- RTL-AGENTS-BEGIN -->.*?<!-- RTL-AGENTS-END -->', '', content, flags=re.DOTALL)

        # 7b. Update CSP to permit data: and fonts.jsdelivr
        if "font-src" in content and "data:" not in content.split("font-src")[1].split(";")[0]:
            content = content.replace("font-src\n\t\t\t\t\t'self'", "font-src\n\t\t\t\t\t'self'\n\t\t\t\t\tdata:\n\t\t\t\t\thttps://cdn.jsdelivr.net")

        # 7c. Add link to stylesheet in <head> if not present
        link_tag = '\t<link rel="stylesheet" href="../../../workbench/antigravity-custom-theme.css">\n'
        if "antigravity-custom-theme.css" not in content:
            content = content.replace("</head>", f"{link_tag}</head>")

        # 7d. Remove external enhancer script tags from HTML (now natively in bundles)
        content = re.sub(r'\s*<script src="(?:\.\./)+workbench/antigravity-ide-enhancer\.js"[^>]*></script>', '', content)

        # 7e. Ensure agent webview has continuous fixed neon gradient and transparent divs
        if html_path.name == "workbench-jetski-agent.html":
            agent_style = """\t<style id="agy-agent-bg-override">
\t\t:root {
\t\t\t--vscode-editor-background: transparent !important;
\t\t\t--vscode-sideBar-background: transparent !important;
\t\t\t--vscode-input-background: rgba(15, 23, 42, 0.88) !important;
\t\t}
\t\thtml, body {
\t\t\tbackground-color: var(--agy-bg, #080c14) !important;
\t\t\tbackground-image: var(--agy-bg-gradient, radial-gradient(ellipse 95% 70% at 50% -10%, rgba(0, 240, 255, 0.16) 0%, rgba(14, 28, 54, 0.72) 42%, #080c14 85%)) !important;
\t\t\tbackground-attachment: fixed !important;
\t\t\tbackground-size: cover !important;
\t\t\tbackground-repeat: no-repeat !important;
\t\t}
\t\t.jetski-root, #root, [class*="jetski-root"], main.flex-1,
\t\t.bg-agent-convo-background, .bg-background, .bg-sidebar-background, .bg-editor-background,
\t\tdiv[class*="bg-background"], div[class*="bg-sidebar-background"], div[class*="bg-agent-convo-background"],
\t\tdiv[class*="bg-zinc"], div[class*="bg-[#18181b]"], div[class*="bg-[#09090b]"], div[class*="bg-[#121212]"], div[class*="bg-neutral"], div[class*="bg-slate"] {
\t\t\tbackground: transparent !important;
\t\t\tbackground-color: transparent !important;
\t\t}
\t</style>\n"""
            if "agy-agent-bg-override" not in content:
                content = content.replace("</head>", f"{agent_style}</head>")
            else:
                content = re.sub(r'\t<style id="agy-agent-bg-override">.*?</style>\n', lambda m: agent_style, content, flags=re.DOTALL)

        html_path.write_text(content, encoding="utf-8")
        print(f"✓ Patched {html_path.name}")

    # 7. Update product.json Checksums dynamically across all tracked entries
    prod_file = IDE_APP_DIR / "product.json"
    if prod_file.exists():
        with open(prod_file, "r", encoding="utf-8") as f:
            prod_data = json.load(f)

        checksums = prod_data.get("checksums", {})
        tracked_keys = list(checksums.keys())

        updated_count = 0
        for rel in tracked_keys:
            target = out_dir / rel
            if target.exists():
                new_sum = compute_checksum(target)
                if checksums.get(rel) != new_sum:
                    checksums[rel] = new_sum
                    updated_count += 1

        prod_data["checksums"] = checksums
        bak_prod = prod_file.with_suffix(".json.bak")
        if not bak_prod.exists():
            shutil.copy2(prod_file, bak_prod)

        with open(prod_file, "w", encoding="utf-8") as f:
            json.dump(prod_data, f, indent=4)
        print(f"✓ Updated product.json checksums ({updated_count} hashes updated) - ZERO corruption warnings!")

    # 8. Update User settings.json with optimal font and markdown configurations
    if IDE_USER_SETTINGS.parent.exists():
        settings = {}
        if IDE_USER_SETTINGS.exists():
            try:
                with open(IDE_USER_SETTINGS, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except Exception:
                settings = {}

        # Universal Editor settings
        settings["editor.fontFamily"] = "Consolas, 'Vazirmatn', 'Vazirmatn UI', 'Vazir', 'Estedad', 'JetBrains Mono', monospace"
        settings["editor.fontLigatures"] = True
        settings["editor.fontSize"] = 14.5
        settings["editor.lineHeight"] = 1.65
        settings["editor.unicodeHighlight.nonBasicASCII"] = False

        # Dedicated Markdown settings
        settings["[markdown]"] = {
            "editor.fontFamily": "'Vazirmatn', 'Vazirmatn UI', 'Vazir', 'Estedad', 'Outfit', sans-serif",
            "editor.fontSize": 15.5,
            "editor.lineHeight": 28,
            "editor.wordWrap": "on",
            "editor.quickSuggestions": {
                "comments": "off",
                "strings": "off",
                "other": "off"
            }
        }

        # Dedicated Plaintext settings
        settings["[plaintext]"] = {
            "editor.fontFamily": "'Vazirmatn', 'Vazirmatn UI', 'Vazir', 'Estedad', 'Outfit', sans-serif",
            "editor.fontSize": 15.5,
            "editor.lineHeight": 28,
            "editor.wordWrap": "on"
        }

        # Built-in Markdown Preview
        settings["markdown.preview.fontFamily"] = "'Vazirmatn', 'Vazirmatn UI', 'Vazir', 'Estedad', 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
        settings["markdown.preview.fontSize"] = 15.5
        settings["markdown.preview.lineHeight"] = 1.85

        # Chat & Terminal settings
        settings["chat.editor.fontFamily"] = "'Outfit', 'Vazirmatn', 'Estedad', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
        settings["chat.editor.fontSize"] = 14.5
        settings["terminal.integrated.fontFamily"] = "Consolas, 'Cascadia Code', monospace"
        settings["terminal.integrated.fontSize"] = 13.5

        IDE_USER_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        with open(IDE_USER_SETTINGS, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
        print("✓ Updated Antigravity IDE User settings.json with optimal font & Markdown configurations")

    print("=" * 60)
    print("✨ SUCCESS: Antigravity IDE design, Persian fonts, Neon Glow & Customizer suite PERMANENTLY installed!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    setup_ide_theme()
