import base64
from pathlib import Path

HOME = Path.home()
FONTS_DIR = HOME / ".gemini" / "antigravity" / "bin" / "assets" / "fonts"
LOCAL_FONTS = Path(__file__).resolve().parent / "assets" / "fonts"

def resolve_font(filename):
    for d in [FONTS_DIR, LOCAL_FONTS]:
        p = d / filename
        if p.exists():
            return p
    return FONTS_DIR / filename

vazir_file = resolve_font("Vazirmatn[wght].woff2")
vazir_b64 = base64.b64encode(vazir_file.read_bytes()).decode('ascii') if vazir_file.exists() else ""
print(f"Vazirmatn b64: {len(vazir_b64)} chars (Ultra-lightweight single font bundle)")

template = '''// ChatGPT Desktop & Codex Enhanced UI Suite (Ultimate Persian & Modern Glass)
// Integrated with Antigravity Account Switcher, Local WOFF2 Fonts (Outfit + Vazirmatn + Estedad), Draggable HUD & KaTeX Math Protection

(() => {
  // Prevent duplicate execution, background workers, or iframe sandboxes
  if (window.__cpe_initialized) return;
  if (window !== window.top) return;
  const href = window.location.href || '';
  if (href.includes('web-sandbox') || href.includes('detached-window')) return;
  window.__cpe_initialized = true;

  // Cleanup legacy or conflicting style tags if any
  ['cpe-vazir-base64', 'cpe-test-fix'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.remove();
  });

  // 1. Embedded Base64 Offline WOFF2 Fonts (Zero CDN dependencies, ultra-lightweight)
  const VAZIRMATN_B64 = "__VAZIR_B64__";

  function safeAppend(el) {
    if (!el) return false;
    const parent = document.head || document.documentElement || document.body;
    if (parent) {
      if (!parent.contains(el)) {
        parent.appendChild(el);
      }
      return true;
    }
    return false;
  }

  function ensureAppended(el) {
    if (safeAppend(el)) return;
    const appendWhenReady = () => {
      safeAppend(el);
    };
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', appendWhenReady, { once: true });
    } else {
      window.addEventListener('load', appendWhenReady, { once: true });
    }
  }

  // Dedicated Portal Root attached to document.documentElement (<html>) completely isolated from React DOM tree
  function getPortalRoot() {
    let portal = document.getElementById('cpe-portal-root');
    if (!portal || !portal.isConnected) {
      if (portal) portal.remove();
      portal = document.createElement('div');
      portal.id = 'cpe-portal-root';
      portal.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483640;overflow:visible;';
      const root = document.documentElement || document.body;
      if (root) {
        root.appendChild(portal);
      }
    }
    return portal;
  }

  function injectBase64Fonts() {
    let fontStyle = document.getElementById('cpe-embedded-fonts');
    if (fontStyle && fontStyle.isConnected && fontStyle.textContent && fontStyle.textContent.length > 500) {
      return;
    }
    if (!fontStyle) {
      fontStyle = document.createElement('style');
      fontStyle.id = 'cpe-embedded-fonts';
      const targetParent = document.head || document.documentElement;
      if (targetParent) {
        targetParent.appendChild(fontStyle);
      } else {
        ensureAppended(fontStyle);
      }
    }
    fontStyle.textContent = `
      @font-face {
        font-family: 'Vazirmatn';
        font-style: normal;
        font-weight: 100 900;
        font-display: swap;
        src: local('Vazirmatn'), local('Vazir'), url('data:font/woff2;base64,${VAZIRMATN_B64}') format('woff2');
      }
    `;

    if (document.fonts) {
      try { document.fonts.load('16px Vazirmatn'); } catch(e) {}
    }
  }
  injectBase64Fonts();

  // 2. Settings Management
  const STORAGE_KEY = 'cpe_chatgpt_suite_settings';
  const DEFAULT_SETTINGS = {
    fontFa: 'Vazirmatn',
    fontEn: 'system',
    theme: 'cyber',
    strokeMode: 'refined',
    rtlAuto: true,
    fontSize: 15
  };

  let cachedSettings = null;
  function loadSettings() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      const s = { ...DEFAULT_SETTINGS, ...saved };
      cachedSettings = s;
      return s;
    } catch (e) {
      cachedSettings = DEFAULT_SETTINGS;
      return DEFAULT_SETTINGS;
    }
  }

  function getSettings() {
    if (!cachedSettings) {
      return loadSettings();
    }
    return cachedSettings;
  }

  window.__cpe_pending_reqs = window.__cpe_pending_reqs || {};
  window.__cpe_on_ipc_reply = function(reqId, result) {
    if (window.__cpe_pending_reqs && window.__cpe_pending_reqs[reqId]) {
      const { resolve } = window.__cpe_pending_reqs[reqId];
      delete window.__cpe_pending_reqs[reqId];
      resolve(result);
    }
  };

  window.callCpeBackend = function(action, data = {}) {
    return new Promise(async (resolve, reject) => {
      // 1. Native CDP IPC binding (completely immune to CSP)
      if (typeof window.__cpe_daemon_ipc === 'function') {
        const reqId = 'req_' + Date.now() + '_' + Math.random().toString(36).slice(2, 7);
        window.__cpe_pending_reqs[reqId] = { resolve, reject };
        try {
          window.__cpe_daemon_ipc(JSON.stringify({ id: reqId, action, ...data }));
        } catch(e) {
          delete window.__cpe_pending_reqs[reqId];
          fallbackHttp(resolve, reject);
        }
        setTimeout(() => {
          if (window.__cpe_pending_reqs && window.__cpe_pending_reqs[reqId]) {
            delete window.__cpe_pending_reqs[reqId];
            fallbackHttp(resolve, reject);
          }
        }, 6000);
        return;
      }

      // 2. HTTP Fallback
      fallbackHttp(resolve, reject);

      async function fallbackHttp(res, rej) {
        for (const port of [39281, 39285]) {
          try {
            let url = `http://127.0.0.1:${port}/api/chatgpt/${action === 'get_status' ? 'status' : action}`;
            let options = { method: 'GET' };
            if (action === 'save_settings' || action === 'save_profile' || action === 'switch') {
              options = {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
              };
            } else if (Object.keys(data).length > 0) {
              const params = new URLSearchParams(data);
              url += '?' + params.toString();
            }
            const r = await fetch(url, options);
            if (r.ok) {
              const j = await r.json();
              return res(j);
            }
          } catch(e) {}
        }
        rej(new Error('No response from backend'));
      }
    });
  };

  function saveSettings(patch) {
    const current = getSettings();
    const updated = { ...current, ...patch };
    cachedSettings = updated;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    } catch (e) {}

    // Sync to Python daemon via native IPC or HTTP
    window.callCpeBackend('save_settings', { settings: patch }).catch(() => {});

    applyThemeAndFont();
    return updated;
  }

  // 3. Design Tokens & Color Palettes
  const THEMES = {
    cyber: {
      name: '⚡️ سایبرپانک نئون (Cyberpunk Neon)',
      accent: '#00f0ff',
      accentGlow: '0 0 16px rgba(0, 240, 255, 0.45)',
      accentSoft: 'rgba(0, 240, 255, 0.14)',
      border: 'rgba(0, 240, 255, 0.28)',
      bg: '#0a0e17',
      bgGradient: 'radial-gradient(ellipse at 50% 0%, #111a2e 0%, #080c14 70%)',
      sidebar: '#060910',
      card: '#101726',
      cardBorder: 'rgba(0, 240, 255, 0.22)',
      composerBg: 'rgba(15, 23, 42, 0.94)',
      text: '#f1f5f9'
    },
    amoled: {
      name: '🖤 آمولد بلک و شیشه‌ای (Pure AMOLED & Glass)',
      accent: '#38bdf8',
      accentGlow: '0 0 14px rgba(56, 189, 248, 0.35)',
      accentSoft: 'rgba(255, 255, 255, 0.08)',
      border: 'rgba(255, 255, 255, 0.18)',
      bg: '#000000',
      bgGradient: '#000000',
      sidebar: '#050505',
      card: '#0d0d0d',
      cardBorder: 'rgba(255, 255, 255, 0.16)',
      composerBg: '#090909',
      text: '#ffffff'
    },
    midnight: {
      name: '🌌 میدنایت ایندیگو (Midnight Indigo)',
      accent: '#818cf8',
      accentGlow: '0 0 16px rgba(129, 140, 248, 0.45)',
      accentSoft: 'rgba(99, 102, 241, 0.15)',
      border: 'rgba(99, 102, 241, 0.25)',
      bg: '#0b0f19',
      bgGradient: 'radial-gradient(ellipse at 50% 0%, #171d33 0%, #090c14 70%)',
      sidebar: '#080b13',
      card: '#141a2e',
      cardBorder: 'rgba(99, 102, 241, 0.22)',
      composerBg: 'rgba(17, 24, 39, 0.94)',
      text: '#f8fafc'
    },
    emerald: {
      name: '🟢 ماتریکس زمردی (Emerald Matrix)',
      accent: '#10b981',
      accentGlow: '0 0 16px rgba(16, 185, 129, 0.45)',
      accentSoft: 'rgba(16, 185, 129, 0.15)',
      border: 'rgba(16, 185, 129, 0.25)',
      bg: '#07100b',
      bgGradient: 'radial-gradient(ellipse at 50% 0%, #0d2116 0%, #050b08 70%)',
      sidebar: '#040a07',
      card: '#0c1f14',
      cardBorder: 'rgba(16, 185, 129, 0.22)',
      composerBg: 'rgba(7, 22, 15, 0.94)',
      text: '#ecfdf5'
    },
    clean_dark: {
      name: '⚪️ دارک اسلیت مدرن (Modern Dark Slate)',
      accent: '#38bdf8',
      accentGlow: '0 0 14px rgba(56, 189, 248, 0.35)',
      accentSoft: 'rgba(56, 189, 248, 0.12)',
      border: 'rgba(255, 255, 255, 0.14)',
      bg: '#111318',
      bgGradient: 'radial-gradient(ellipse at 50% 0%, #1a1e26 0%, #0e1014 70%)',
      sidebar: '#0c0e12',
      card: '#181b22',
      cardBorder: 'rgba(255, 255, 255, 0.12)',
      composerBg: 'rgba(24, 27, 34, 0.94)',
      text: '#f8fafc'
    }
  };

  // 4. Dynamic Style Engine
  let dynamicStyleEl = document.getElementById('cpe-dynamic-styles');
  if (!dynamicStyleEl) {
    dynamicStyleEl = document.createElement('style');
    dynamicStyleEl.id = 'cpe-dynamic-styles';
    ensureAppended(dynamicStyleEl);
  }

  function applyThemeAndFont() {
    injectBase64Fonts();
    const s = getSettings();
    const t = THEMES[s.theme] || THEMES.cyber;
    
    // Combine English (Latin) and Persian (Fa) fonts with ultra-light system fallbacks
    const fontFaPart = "'Vazirmatn', ";
    const fontEnPart = (s.fontEn && s.fontEn !== 'system') ? `'${s.fontEn}', ` : "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif, ";
    const combinedFont = `${fontFaPart}${fontEnPart}sans-serif`;
    const persianFont = `${fontFaPart}sans-serif`;

    // Stroke / Border Configuration
    let strokeCSS = '';
    if (s.strokeMode === 'refined') {
      strokeCSS = `
        /* User Message Card */
        [data-message-author-role="user"] > div:first-child {
          border: 1px solid ${t.cardBorder} !important;
          box-shadow: 0 0 0 1px ${t.cardBorder}, 0 4px 20px rgba(0, 0, 0, 0.35) !important;
        }
        /* Sidebar Separator */
        aside.app-shell-left-panel, #app-shell-sidebar {
          border-right: 1px solid ${t.border} !important;
        }
        /* Single Unified Composer Box */
        div[class*="_ComposerLayoutRoot_"] {
          border: 1px solid ${t.border} !important;
          border-radius: 20px !important;
          box-shadow: 0 0 0 1px ${t.border}, 0 8px 32px rgba(0, 0, 0, 0.5) !important;
        }
        div[class*="_ComposerLayoutRoot_"]:focus-within {
          border-color: ${t.accent} !important;
          box-shadow: 0 0 0 1.5px ${t.accent}, 0 8px 32px rgba(0, 0, 0, 0.55), ${t.accentGlow} !important;
        }
      `;
    } else if (s.strokeMode === 'subtle') {
      strokeCSS = `
        [data-message-author-role="user"] > div:first-child {
          border: 1px solid rgba(255, 255, 255, 0.08) !important;
          box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08) !important;
        }
        aside.app-shell-left-panel, #app-shell-sidebar {
          border-right: 1px solid rgba(255, 255, 255, 0.06) !important;
        }
        div[class*="_ComposerLayoutRoot_"] {
          border: 1px solid rgba(255, 255, 255, 0.14) !important;
          border-radius: 20px !important;
          box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.14), 0 8px 24px rgba(0, 0, 0, 0.4) !important;
        }
        div[class*="_ComposerLayoutRoot_"]:focus-within {
          border-color: rgba(255, 255, 255, 0.28) !important;
          box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.28), 0 8px 24px rgba(0, 0, 0, 0.4) !important;
        }
      `;
    } else if (s.strokeMode === 'glow') {
      strokeCSS = `
        [data-message-author-role="user"] > div:first-child {
          border: 1px solid ${t.accentSoft} !important;
          box-shadow: 0 0 0 1px ${t.accentSoft}, 0 0 14px ${t.accentSoft} !important;
        }
        aside.app-shell-left-panel, #app-shell-sidebar {
          border-right: 1px solid ${t.border} !important;
        }
        div[class*="_ComposerLayoutRoot_"] {
          border: 1px solid ${t.accent} !important;
          box-shadow: 0 0 0 1.5px ${t.accent}, 0 0 20px ${t.accentGlow} !important;
          border-radius: 20px !important;
        }
      `;
    }

    if (!dynamicStyleEl || !dynamicStyleEl.isConnected) {
      dynamicStyleEl = document.getElementById('cpe-dynamic-styles');
      if (!dynamicStyleEl) {
        dynamicStyleEl = document.createElement('style');
        dynamicStyleEl.id = 'cpe-dynamic-styles';
        const targetParent = document.head || document.documentElement;
        if (targetParent) targetParent.appendChild(dynamicStyleEl);
        else ensureAppended(dynamicStyleEl);
      }
    }

    const generatedCss = `
      :root {
        --cpe-font: ${combinedFont};
        --cpe-font-fa: ${persianFont};
        --cpe-font-size: ${s.fontSize}px;
        --cpe-accent: ${t.accent};
        --color-token-main-surface-primary: ${t.bg} !important;
        --color-token-bg-primary: ${t.sidebar} !important;
        --color-background-composer-action-bar: ${t.card} !important;
      }

      /* 1. Universal High-Performance Typography Inheritance */
      body,
      input,
      textarea,
      button,
      select,
      label,
      [data-message-author-role],
      .prose,
      .ProseMirror,
      [contenteditable="true"],
      p,
      li,
      bdi,
      h1, h2, h3, h4, h5, h6 {
        font-family: var(--cpe-font);
      }

      /* Layout Container Direction Protections (Prevent Inverting Grid/Flex & Scroll Anchors) */
      [class*="_transcriptContent_"],
      .thread-scroll-container,
      [class*="thread-scroll-layout"],
      div[data-turn-key],
      div[data-testid*="turn"],
      div[class*="group/user-message"],
      div[class*="_ComposerLayoutRoot_"],
      div[class*="_MainContent_"],
      div[class*="_Workspace_"],
      main {
        direction: ltr !important;
      }

      /* 2. Reading Flow & Line Height */
      [data-message-author-role="assistant"] p,
      [data-message-author-role="user"] p,
      .prose p,
      .cpe-rtl-text {
        line-height: 1.82 !important;
        font-size: var(--cpe-font-size) !important;
        letter-spacing: normal !important;
      }

      /* 3. Background Theming */
      main,
      ._MainContentSurface_yl8z4_2,
      [data-testid="conversation-turn-list"] {
        background: ${t.bg} !important;
        background-image: ${t.bgGradient} !important;
      }

      aside.app-shell-left-panel,
      #app-shell-sidebar,
      nav._Navigation_1uxfp_2 {
        background-color: ${t.sidebar} !important;
      }

      /* 4. Message Bubble Elevation & Cards */
      [data-message-author-role="user"] > div:first-child {
        background: ${t.card} !important;
        border-radius: 18px !important;
        padding: 12px 18px !important;
        color: ${t.text} !important;
      }

      [data-message-author-role="assistant"] {
        color: ${t.text} !important;
      }

      /* 5. Precise Single-Container Chat Composer */
      /* Completely kill borders, backgrounds and outlines on all outer wrapper strips */
      div[class*="thread-scroll-container"],
      div[class*="group/thread-scroll-layout"],
      div[class*="pointer-events-none"][class*="inset-x-0"],
      div[class*="pb-(--thread-composer-bottom-inset)"],
      [data-thread-focus-mode] {
        border: none !important;
        border-top: none !important;
        border-bottom: none !important;
        border-left: none !important;
        border-right: none !important;
        background: transparent !important;
        box-shadow: none !important;
        outline: none !important;
      }

      /* Single sleek card for the actual composer (zero GPU blur overhead) */
      div[class*="_ComposerLayoutRoot_"] {
        background: ${t.composerBg} !important;
        border-radius: 20px !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
        overflow: hidden !important;
      }

      /* Inner input and elements remain completely borderless */
      div[class*="_ComposerLayoutBody_"],
      div[class*="_ComposerLayoutInput_"],
      div[class*="_ComposerLayoutFooter_"],
      div[class*="_AdaptiveFooterInput_"],
      .ProseMirror {
        border: none !important;
        border-top: none !important;
        border-bottom: none !important;
        border-left: none !important;
        border-right: none !important;
        background: transparent !important;
        box-shadow: none !important;
        outline: none !important;
      }

      .ProseMirror {
        color: ${t.text} !important;
        font-size: 15px !important;
        line-height: 1.6 !important;
      }

      /* 6. File Mentions, Links & Diff Cards Matching Theme */
      [class*="_Mention_"],
      [class*="_TableCellFileLink_"],
      a[class*="file"],
      button[class*="file"],
      [class*="file-pill"],
      [class*="file-tag"] {
        color: ${t.accent} !important;
        background: ${t.accentSoft} !important;
        border: 1px solid ${t.border} !important;
        border-radius: 6px !important;
        padding: 1px 7px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        direction: ltr !important;
        display: inline-flex !important;
        align-items: center !important;
        text-decoration: none !important;
        transition: all 0.15s ease !important;
      }

      [class*="_Mention_"]:hover,
      [class*="_TableCellFileLink_"]:hover {
        background: ${t.accent}25 !important;
        border-color: ${t.accent} !important;
      }

      [class*="_Mention_"] [class*="_Label_"],
      [class*="_TableCellFileLink_"] [class*="_Label_"] {
        color: ${t.accent} !important;
        font-family: 'JetBrains Mono', monospace !important;
      }

      /* Diff File Rows and Review Cards */
      [class*="turn-diff-file-row"],
      button[class*="turn-diff-file-row"] {
        transition: background 0.15s ease !important;
      }
      button[class*="turn-diff-file-row"]:hover {
        background: ${t.accentSoft} !important;
      }
      button[class*="turn-diff-file-row"] span[class*="truncate"],
      button[class*="turn-diff-file-row"] span.text-default {
        color: ${t.accent} !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 13px !important;
        font-weight: 500 !important;
      }
      button[class*="turn-diff-file-row"] [class*="tabular-nums"] {
        font-family: 'JetBrains Mono', monospace !important;
      }

      /* Inline Code Badges */
      [class*="_InlineCode_"] {
        color: ${t.accent} !important;
        background: rgba(255, 255, 255, 0.08) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 5px !important;
        padding: 1px 6px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 13px !important;
      }

      /* 7. Sidebar Chat Item Polish */
      #app-shell-sidebar a,
      #app-shell-sidebar li,
      .sidebar-navigation li {
        transition: background 0.15s ease, color 0.15s ease;
      }
      #app-shell-sidebar a:hover,
      #app-shell-sidebar li:hover {
        background: rgba(255, 255, 255, 0.05) !important;
        border-radius: 8px !important;
      }

      /* 8. Monospace Code & File Editor with Persian Vazirmatn Fallback */
      pre, code, kbd, samp, 
      [class*="font-mono"],
      [class*="terminal"],
      pre *, code * {
        font-family: 'JetBrains Mono', 'Fira Code', 'Vazirmatn', Consolas, 'Courier New', monospace !important;
        letter-spacing: normal !important;
      }

      pre {
        direction: ltr !important;
        text-align: left !important;
        unicode-bidi: isolate !important;
        background: #0d1117 !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4) !important;
      }

      /* CodeMirror & File Viewer Panels */
      .cm-editor, .cm-content, .cm-scroller, [data-code], [data-content] {
        font-family: 'JetBrains Mono', 'Fira Code', 'Vazirmatn', Consolas, monospace !important;
        letter-spacing: normal !important;
      }

      /* CodeMirror & File Viewer BiDi Lines (Persian Markdown / Comments / Prose) */
      .cm-line.cpe-rtl-text,
      .cm-content .cpe-rtl-text,
      [data-line].cpe-rtl-text,
      [data-content].cpe-rtl-text,
      .cm-markdown-list-item.cpe-rtl-text {
        direction: rtl !important;
        text-align: right !important;
        font-family: var(--cpe-font-fa), 'Vazirmatn', sans-serif !important;
        letter-spacing: normal !important;
        unicode-bidi: plaintext !important;
      }

      /* 9. Strict Math / LaTeX / KaTeX Formula Protection */
      .katex, .katex-display, .katex-html, span.katex, math, annotation {
        direction: ltr !important;
        text-align: left !important;
        unicode-bidi: isolate !important;
        font-family: KaTeX_Main, KaTeX_Math, 'Times New Roman', serif !important;
      }
      .katex-display {
        display: block !important;
        text-align: center !important;
        margin: 1.2em 0 !important;
        padding: 12px 18px !important;
        background: rgba(255, 255, 255, 0.035) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        overflow-x: auto !important;
        overflow-y: hidden !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25) !important;
      }

      /* 10. BiDi Text Alignment on Leaf Content Elements Only */
      p.cpe-rtl-text,
      li.cpe-rtl-text,
      h1.cpe-rtl-text,
      h2.cpe-rtl-text,
      h3.cpe-rtl-text,
      h4.cpe-rtl-text,
      h5.cpe-rtl-text,
      h6.cpe-rtl-text,
      blockquote.cpe-rtl-text,
      span.cpe-rtl-text {
        direction: rtl !important;
        text-align: right !important;
        font-family: var(--cpe-font-fa), var(--cpe-font) !important;
        letter-spacing: normal !important;
        unicode-bidi: plaintext !important;
      }
      p.cpe-ltr-text,
      li.cpe-ltr-text {
        direction: ltr !important;
        text-align: left !important;
        unicode-bidi: plaintext !important;
      }

      /* Inline Code Badges Inside Persian Sentences (Isolate Direction & Metrics) */
      :not(pre) > code,
      [class*="_InlineCode_"] {
        direction: ltr !important;
        unicode-bidi: isolate !important;
        text-align: left !important;
        font-family: 'JetBrains Mono', 'Fira Code', 'Vazirmatn', Consolas, monospace !important;
        font-size: 0.9em !important;
      }

      /* 11. Accent Highlights */
      .prose a {
        color: ${t.accent} !important;
      }
      ::selection {
        background: ${t.accent}40 !important;
        color: #ffffff !important;
      }

      ${strokeCSS}

      /* 12. Draggable Action HUD Pill */
      #cpe-hud-pill {
        position: fixed;
        top: 14px;
        right: 80px;
        z-index: 2147483645;
        pointer-events: auto !important;
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 5px 12px;
        background: rgba(15, 23, 42, 0.88);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border: 1px solid ${t.border};
        border-radius: 9999px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.55), ${t.accentGlow};
        user-select: none;
        font-family: var(--cpe-font);
        transition: transform 0.15s ease, box-shadow 0.2s ease;
        cursor: grab;
      }

      #cpe-hud-pill:hover {
        border-color: ${t.accent};
        box-shadow: 0 12px 36px rgba(0, 0, 0, 0.65), ${t.accentGlow};
      }

      #cpe-hud-pill:active {
        cursor: grabbing;
      }

      .cpe-hud-btn {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 5px 12px;
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 9999px;
        color: #f1f5f9;
        font-size: 11.5px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.16s ease;
        font-family: inherit;
      }

      .cpe-hud-btn:hover {
        background: ${t.accentSoft};
        color: ${t.accent};
        border-color: ${t.accent};
        transform: scale(1.03);
      }

      /* Modal Dialog */
      .cpe-modal-overlay {
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.72);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        z-index: 2147483646;
        display: flex;
        align-items: center;
        justify-content: center;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.2s ease;
        font-family: var(--cpe-font);
        direction: rtl;
      }

      .cpe-modal-overlay.cpe-open {
        opacity: 1;
        pointer-events: auto !important;
      }

      .cpe-modal-sheet {
        width: 540px;
        max-width: 94vw;
        max-height: 86vh;
        overflow-y: auto;
        background: #0f172a;
        border: 1px solid ${t.border};
        border-radius: 22px;
        padding: 22px;
        box-shadow: 0 25px 60px rgba(0, 0, 0, 0.8), ${t.accentGlow};
        color: #f8fafc;
        transform: scale(0.96);
        transition: transform 0.2s ease;
      }

      .cpe-modal-overlay.cpe-open .cpe-modal-sheet {
        transform: scale(1);
      }
    `;

    if (dynamicStyleEl.textContent !== generatedCss) {
      dynamicStyleEl.textContent = generatedCss;
    }
  }
  window.__chatgpt_enhanced_apply_theme = applyThemeAndFont;

  // 5. Ultra-Fast BiDi & RTL Engine (Zero-Reflow, WeakSet Cached, RAF Scheduled)
  const PERSIAN_REGEX = /[\\u0600-\\u06FF\\u0750-\\u077F\\u08A0-\\u08FF\\uFB50-\\uFDFF\\uFE70-\\uFEFF]/;
  const processedBiDiElements = new WeakSet();
  const pendingBiDiElements = new Set();
  let bidiScheduled = false;
  const LEAF_TEXT_TAGS = {
    P: true,
    LI: true,
    H1: true,
    H2: true,
    H3: true,
    H4: true,
    H5: true,
    H6: true,
    BLOCKQUOTE: true
  };

  function queueElementForBiDi(el) {
    if (!el || el.nodeType !== 1 || processedBiDiElements.has(el)) return;
    const tag = el.tagName;
    if (tag === 'PRE' || tag === 'CODE' || tag === 'SVG' || tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'BUTTON' || tag === 'SCRIPT' || tag === 'STYLE') return;
    if (el.id === 'cpe-portal-root' || el.id === 'cpe-hud-pill') return;

    if (tag === 'DIFFS-CONTAINER') {
      patchDiffsContainers();
      return;
    }

    if (LEAF_TEXT_TAGS[tag]) {
      pendingBiDiElements.add(el);
      return;
    }

    if (el.classList && (el.classList.contains('cm-line') || el.classList.contains('_clipViewport_a3okg_20'))) {
      pendingBiDiElements.add(el);
      return;
    }

    // High performance leaf collector using native getElementsByTagName (avoids CSS selector engine)
    if (el.childElementCount > 0) {
      const ps = el.getElementsByTagName('p');
      for (let i = 0; i < ps.length; i++) {
        const p = ps[i];
        if (!processedBiDiElements.has(p)) pendingBiDiElements.add(p);
      }
      const lis = el.getElementsByTagName('li');
      for (let i = 0; i < lis.length; i++) {
        const li = lis[i];
        if (!processedBiDiElements.has(li)) pendingBiDiElements.add(li);
      }
    }
  }

  function flushBiDi() {
    bidiScheduled = false;
    if (pendingBiDiElements.size === 0) return;
    const s = getSettings();
    if (!s.rtlAuto) {
      pendingBiDiElements.clear();
      return;
    }

    for (const el of pendingBiDiElements) {
      if (!el || !el.isConnected || processedBiDiElements.has(el)) continue;
      processedBiDiElements.add(el);

      // Fast textContent slice avoids triggering layout reflow
      const text = (el.textContent || '').slice(0, 50);
      if (PERSIAN_REGEX.test(text)) {
        el.classList.add('cpe-rtl-text');
      }
    }
    pendingBiDiElements.clear();
  }

  function scheduleBiDi() {
    if (bidiScheduled) return;
    bidiScheduled = true;
    if (typeof requestAnimationFrame === 'function' && document.visibilityState === 'visible') {
      requestAnimationFrame(flushBiDi);
    } else {
      setTimeout(flushBiDi, 20);
    }
  }

  // Cleanup old observer if any on hot-reload
  if (window.__cpe_observer) {
    try { window.__cpe_observer.disconnect(); } catch(e) {}
  }

  const observer = new MutationObserver(mutations => {
    for (let i = 0; i < mutations.length; i++) {
      const m = mutations[i];
      for (let j = 0; j < m.addedNodes.length; j++) {
        const node = m.addedNodes[j];
        if (node.nodeType === 1) {
          queueElementForBiDi(node);
        }
      }
    }
    if (pendingBiDiElements.size > 0) {
      scheduleBiDi();
    }
  });
  window.__cpe_observer = observer;

  // Observe main container to avoid unnecessary sidebar / modal mutations
  const targetObs = document.querySelector('main') || document.body;
  if (targetObs) {
    observer.observe(targetObs, { childList: true, subtree: true });
    queueElementForBiDi(targetObs);
    scheduleBiDi();
  } else {
    document.addEventListener('DOMContentLoaded', () => {
      const root = document.querySelector('main') || document.body;
      if (root) {
        observer.observe(root, { childList: true, subtree: true });
        queueElementForBiDi(root);
        scheduleBiDi();
      }
    }, { once: true });
  }

  // 6. Draggable Floating Action HUD UI
  function renderHUD() {
    let hud = document.getElementById('cpe-hud-pill');
    if (hud && hud.isConnected) {
      return hud;
    }
    if (hud) hud.remove();

    hud = document.createElement('div');
    hud.id = 'cpe-hud-pill';
    hud.style.pointerEvents = 'auto';

    hud.innerHTML = `
      <span id="cpe-hud-drag-handle" style="cursor: grab; display: flex; align-items: center; gap: 4px; padding: 2px 4px; border-radius: 6px; user-select: none;" title="برای جابه‌جایی نوار، اینجا را بگیرید و بکشید">
        <span style="font-size: 13px; color: rgba(255,255,255,0.45); font-family: monospace;">⠿</span>
        <span style="width: 7px; height: 7px; border-radius: 50%; background: #00f0ff; box-shadow: 0 0 8px #00f0ff;"></span>
        <span style="font-size: 11px; font-weight: 700; color: #00f0ff; letter-spacing: 0.5px;">Codex Pro</span>
      </span>
      <button class="cpe-hud-btn" id="cpe-btn-new-chat" title="باز کردن چت جدید (Ctrl+Shift+O)">
        ➕ <span>صفحه جدید</span>
      </button>
      <button class="cpe-hud-btn" id="cpe-btn-switch-account" title="مدیریت و سوئیچ بین اکانت‌ها">
        🔄 <span>اکانت‌ها</span>
      </button>
      <button class="cpe-hud-btn" id="cpe-btn-login" title="ورود و احراز هویت (OAuth، API Key یا پنجره مستقل)">
        🔐 <span>لاگین</span>
      </button>
      <button class="cpe-hud-btn" id="cpe-btn-theme" title="تنظیمات فونت، تم و استروک">
        🎨 <span>تم و فونت</span>
      </button>
    `;

    const portal = getPortalRoot();
    if (portal) {
      portal.appendChild(hud);
    } else {
      ensureAppended(hud);
    }

    // Restore saved position with strict bounds
    try {
      const savedPos = JSON.parse(localStorage.getItem('cpe_hud_pill_pos') || 'null');
      if (savedPos && typeof savedPos.x === 'number') {
        const maxX = Math.max(10, window.innerWidth - 380);
        // STRICT: HUD must remain in top banner area (Y between 8 and 180px)
        const clampedX = Math.min(Math.max(10, savedPos.x), maxX);
        const clampedY = Math.min(Math.max(8, savedPos.y), 180);
        hud.style.left = `${clampedX}px`;
        hud.style.top = `${clampedY}px`;
        hud.style.right = 'auto';
      }
    } catch(e) {}

    // Make HUD Draggable using Pointer Capture ONLY on the drag handle
    const dragHandle = document.getElementById('cpe-hud-drag-handle');
    let isDragging = false;
    let startX = 0, startY = 0;
    let initialLeft = 0, initialTop = 0;

    const stopDragging = (ev) => {
      if (!isDragging) return;
      isDragging = false;
      hud.style.transition = 'transform 0.15s ease, box-shadow 0.2s ease';
      hud.style.cursor = '';
      if (dragHandle) {
        dragHandle.style.cursor = 'grab';
        try {
          if (ev && ev.pointerId && dragHandle.hasPointerCapture(ev.pointerId)) {
            dragHandle.releasePointerCapture(ev.pointerId);
          }
        } catch(err) {}
      }
      document.body.style.userSelect = '';
      const finalRect = hud.getBoundingClientRect();
      try {
        localStorage.setItem('cpe_hud_pill_pos', JSON.stringify({ 
          x: Math.round(finalRect.left), 
          y: Math.min(Math.max(8, Math.round(finalRect.top)), 180) 
        }));
      } catch(e) {}
    };

    if (dragHandle) {
      dragHandle.addEventListener('pointerdown', (e) => {
        if (e.button !== 0) return; // Left mouse click only
        e.preventDefault();
        e.stopPropagation();
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        const rect = hud.getBoundingClientRect();
        initialLeft = rect.left;
        initialTop = rect.top;

        hud.style.transition = 'none';
        dragHandle.style.cursor = 'grabbing';
        document.body.style.userSelect = 'none';
        try {
          dragHandle.setPointerCapture(e.pointerId);
        } catch(err) {}
      });

      dragHandle.addEventListener('pointermove', (ev) => {
        if (!isDragging) return;
        const dx = ev.clientX - startX;
        const dy = ev.clientY - startY;

        let newX = initialLeft + dx;
        let newY = initialTop + dy;

        const maxX = Math.max(10, window.innerWidth - hud.offsetWidth - 10);
        // STRICT TOP CLAMP: Prevent ever moving into bottom area / composer / (+) button
        const maxY = Math.min(180, Math.floor(window.innerHeight * 0.25));
        newX = Math.max(10, Math.min(newX, maxX));
        newY = Math.max(8, Math.min(newY, maxY));

        hud.style.left = `${newX}px`;
        hud.style.top = `${newY}px`;
        hud.style.right = 'auto';
      });

      dragHandle.addEventListener('pointerup', stopDragging);
      dragHandle.addEventListener('pointercancel', stopDragging);
      dragHandle.addEventListener('lostpointercapture', stopDragging);

      // Double-click to instantly dock/reset back to top header
      dragHandle.addEventListener('dblclick', (e) => {
        e.stopPropagation();
        hud.style.top = '14px';
        hud.style.right = '80px';
        hud.style.left = 'auto';
        localStorage.removeItem('cpe_hud_pill_pos');
        showToast('📌 نوار در بالای صفحه فیکس شد');
      });
    }

    window.addEventListener('blur', stopDragging);

    // Button Events
    document.getElementById('cpe-btn-new-chat').onclick = () => {
      const selectors = [
        'a[href="/"]',
        'button[aria-label*="New chat"]',
        'button[aria-label*="چت جدید"]',
        '[data-testid="new-chat-button"]',
        'a[data-testid="create-new-chat-button"]',
        'button[data-testid="create-new-chat-button"]'
      ];
      for (const sel of selectors) {
        try {
          const el = document.querySelector(sel);
          if (el) {
            el.click();
            showToast('➕ گفتگوی جدید باز شد');
            return;
          }
        } catch (e) {}
      }
      window.location.href = 'https://chatgpt.com/';
    };

    document.getElementById('cpe-btn-switch-account').onclick = () => {
      openAccountModal('switch');
    };

    document.getElementById('cpe-btn-login').onclick = () => {
      openAccountModal('login');
    };

    document.getElementById('cpe-btn-theme').onclick = () => {
      openThemeModal();
    };
  }

  // Toast Notification
  function showToast(msg, isErr = false) {
    let t = document.getElementById('cpe-toast');
    if (t) t.remove();
    t = document.createElement('div');
    t.id = 'cpe-toast';
    t.style.cssText = `
      position: fixed;
      bottom: 24px;
      left: 50%;
      transform: translateX(-50%);
      background: ${isErr ? 'rgba(239, 68, 68, 0.95)' : 'rgba(15, 23, 42, 0.95)'};
      color: #fff;
      padding: 10px 22px;
      border-radius: 9999px;
      border: 1px solid ${isErr ? '#ef4444' : 'rgba(0, 240, 255, 0.4)'};
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
      z-index: 2147483647;
      font-size: 13px;
      font-family: var(--cpe-font);
      direction: rtl;
      transition: all 0.3s ease;
      pointer-events: none;
    `;
    t.textContent = msg;
    const portal = getPortalRoot();
    if (portal) portal.appendChild(t);
    else ensureAppended(t);
    setTimeout(() => {
      if (t) {
        t.style.opacity = '0';
        setTimeout(() => t.remove(), 300);
      }
    }, 3500);
  }

  // 7. Modals
  function createModal(id, title, contentHtml) {
    let overlay = document.getElementById(id);
    if (overlay) overlay.remove();

    overlay = document.createElement('div');
    overlay.id = id;
    overlay.className = 'cpe-modal-overlay';

    overlay.innerHTML = `
      <div class="cpe-modal-sheet" style="pointer-events: auto !important;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 12px;">
          <h3 style="margin: 0; font-size: 16px; font-weight: 700; color: #00f0ff;">${title}</h3>
          <button style="background: none; border: none; color: #94a3b8; font-size: 20px; cursor: pointer;" onclick="this.closest('.cpe-modal-overlay').classList.remove('cpe-open')">✕</button>
        </div>
        <div>${contentHtml}</div>
      </div>
    `;

    const portal = getPortalRoot();
    if (portal) portal.appendChild(overlay);
    else ensureAppended(overlay);
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.classList.remove('cpe-open');
    });
    return overlay;
  }

  function openThemeModal() {
    const s = loadSettings();
    const fontsFa = [
      { id: 'Vazirmatn', label: 'وزیرمتن (Vazirmatn - پیش‌فرض وب فارسی / آفلاین)' },
      { id: 'Estedad', label: 'استعداد (Estedad - مدرن، خوانا و هندسی / آفلاین)' },
      { id: 'system', label: 'فونت استاندارد سیستم' }
    ];

    const fontsEn = [
      { id: 'Outfit', label: '✨ Outfit (مدرن، ژئومتریک و اپل‌استایل - پیشنهادی)' },
      { id: 'Inter', label: '▫️ Inter (مینیمال و تکنولوژی)' },
      { id: 'JetBrains Mono', label: '💻 JetBrains Mono (مونو اسپیس برنامه‌نویسی)' },
      { id: 'system', label: 'فونت پیش‌فرض سیستم' }
    ];

    const themes = [
      { id: 'cyber', label: '⚡️ سایبرپانک نئون (Cyan Neon - تم اختصاصی کدکس)' },
      { id: 'amoled', label: '🖤 آمولد بلک و کریستال خالص (Pure AMOLED)' },
      { id: 'midnight', label: '🌌 میدنایت ایندیگو (Midnight Indigo)' },
      { id: 'emerald', label: '🟢 ماتریکس زمردی (Emerald Matrix)' },
      { id: 'clean_dark', label: '⚪️ دارک اسلیت مدرن (Modern Dark Slate)' }
    ];

    const strokeModes = [
      { id: 'refined', label: '💎 کادربندی شیک، مدرن و هماهنگ (Refined Single-Card - توصیه شده)' },
      { id: 'glow', label: '💫 استروک درخشان نئونی در فوکوس (Glow Accent)' },
      { id: 'subtle', label: '▫️ کادربندی بسیار ملایم و محو (Subtle 1px)' }
    ];

    const html = `
      <div style="margin-bottom: 14px;">
        <label style="display: block; font-size: 12px; color: #94a3b8; margin-bottom: 5px;">✍️ انتخاب فونت فارسی (آفلاین WOFF2):</label>
        <select id="cpe-sel-font-fa" style="width: 100%; padding: 10px; border-radius: 10px; background: #1e293b; color: #fff; border: 1px solid rgba(255,255,255,0.15); font-family: inherit;">
          ${fontsFa.map(f => `<option value="${f.id}" ${s.fontFa === f.id ? 'selected' : ''}>${f.label}</option>`).join('')}
        </select>
      </div>

      <div style="margin-bottom: 14px;">
        <label style="display: block; font-size: 12px; color: #94a3b8; margin-bottom: 5px;">🔤 انتخاب فونت انگلیسی و لاتین (آفلاین WOFF2):</label>
        <select id="cpe-sel-font-en" style="width: 100%; padding: 10px; border-radius: 10px; background: #1e293b; color: #fff; border: 1px solid rgba(255,255,255,0.15); font-family: inherit;">
          ${fontsEn.map(f => `<option value="${f.id}" ${s.fontEn === f.id ? 'selected' : ''}>${f.label}</option>`).join('')}
        </select>
      </div>

      <div style="margin-bottom: 14px;">
        <label style="display: block; font-size: 12px; color: #94a3b8; margin-bottom: 5px;">🎨 پالت و تم رنگی فضای کدکس:</label>
        <select id="cpe-sel-theme" style="width: 100%; padding: 10px; border-radius: 10px; background: #1e293b; color: #fff; border: 1px solid rgba(255,255,255,0.15); font-family: inherit;">
          ${themes.map(t => `<option value="${t.id}" ${s.theme === t.id ? 'selected' : ''}>${t.label}</option>`).join('')}
        </select>
      </div>

      <div style="margin-bottom: 14px;">
        <label style="display: block; font-size: 12px; color: #94a3b8; margin-bottom: 5px;">🔲 تنظیم کادر و استروک باکس چت (Stroke Style):</label>
        <select id="cpe-sel-stroke-mode" style="width: 100%; padding: 10px; border-radius: 10px; background: #1e293b; color: #fff; border: 1px solid rgba(255,255,255,0.15); font-family: inherit;">
          ${strokeModes.map(sm => `<option value="${sm.id}" ${s.strokeMode === sm.id ? 'selected' : ''}>${sm.label}</option>`).join('')}
        </select>
      </div>

      <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px; background: rgba(255,255,255,0.04); border-radius: 12px; margin-bottom: 18px;">
        <span style="font-size: 13px;">↔️ راست‌چین‌سازی خودکار متن فارسی (RTL):</span>
        <input type="checkbox" id="cpe-chk-rtl" ${s.rtlAuto ? 'checked' : ''} style="width: 18px; height: 18px; cursor: pointer; accent-color: #00f0ff;">
      </div>

      <button id="cpe-save-theme-btn" style="width: 100%; padding: 12px; background: #00f0ff; color: #000; font-weight: 700; border: none; border-radius: 12px; cursor: pointer; font-size: 14px; font-family: inherit;">
        ذخیره و اعمال فوری
      </button>
    `;

    const modal = createModal('cpe-modal-theme', '🎨 تنظیمات استایل، کادر، فونت‌ها و تم کدکس', html);
    modal.classList.add('cpe-open');

    document.getElementById('cpe-save-theme-btn').onclick = () => {
      const fontFa = document.getElementById('cpe-sel-font-fa').value;
      const fontEn = document.getElementById('cpe-sel-font-en').value;
      const theme = document.getElementById('cpe-sel-theme').value;
      const strokeMode = document.getElementById('cpe-sel-stroke-mode').value;
      const rtl = document.getElementById('cpe-chk-rtl').checked;
      saveSettings({ fontFa: fontFa, fontEn: fontEn, theme: theme, strokeMode: strokeMode, rtlAuto: rtl });
      modal.classList.remove('cpe-open');
      showToast('🎨 تنظیمات تم، فونت‌ها و استروک با موفقیت اعمال شد');
    };
  }

  async function openAccountModal(initialTab = 'switch') {
    let currentTab = initialTab;
    const modal = createModal('cpe-modal-account', '🔐 مرکز مدیریت حساب‌ها و ورود (Auth & Accounts)', `
      <div style="display: flex; gap: 8px; margin-bottom: 16px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 10px;">
        <button id="cpe-tab-btn-switch" style="flex: 1; padding: 9px 12px; border-radius: 10px; border: none; font-weight: 700; font-size: 12.5px; cursor: pointer; font-family: inherit; transition: all 0.2s ease;">
          🔄 مدیریت و سوئیچ اکانت‌ها
        </button>
        <button id="cpe-tab-btn-login" style="flex: 1; padding: 9px 12px; border-radius: 10px; border: none; font-weight: 700; font-size: 12.5px; cursor: pointer; font-family: inherit; transition: all 0.2s ease;">
          🔐 ورود به حساب جدید (Login)
        </button>
      </div>
      <div id="cpe-acc-body" style="min-height: 180px;">
        <div style="text-align: center; padding: 30px; color: #94a3b8; font-size: 13px;">
          ⏳ در حال بارگذاری اطلاعات حساب‌ها...
        </div>
      </div>
    `);
    modal.classList.add('cpe-open');

    // Fetch live status from backend via native CDP IPC (or fallback)
    let data = window.__cpe_initial_data || null;
    try {
      data = await window.callCpeBackend('status');
      window.__cpe_initial_data = data;
    } catch (e) {}

    function renderTabs() {
      const btnSwitch = document.getElementById('cpe-tab-btn-switch');
      const btnLogin = document.getElementById('cpe-tab-btn-login');
      const body = document.getElementById('cpe-acc-body');
      if (!btnSwitch || !btnLogin || !body) return;

      if (currentTab === 'switch') {
        btnSwitch.style.background = '#00f0ff';
        btnSwitch.style.color = '#000';
        btnSwitch.style.boxShadow = '0 0 12px rgba(0, 240, 255, 0.4)';
        btnLogin.style.background = 'rgba(255, 255, 255, 0.06)';
        btnLogin.style.color = '#94a3b8';
        btnLogin.style.boxShadow = 'none';
        renderSwitchTab(body, data);
      } else {
        btnLogin.style.background = '#00f0ff';
        btnLogin.style.color = '#000';
        btnLogin.style.boxShadow = '0 0 12px rgba(0, 240, 255, 0.4)';
        btnSwitch.style.background = 'rgba(255, 255, 255, 0.06)';
        btnSwitch.style.color = '#94a3b8';
        btnSwitch.style.boxShadow = 'none';
        renderLoginTab(body, data);
      }
    }

    function renderSwitchTab(container, d) {
      const profiles = (d && d.profiles && d.profiles.profiles) ? d.profiles.profiles : [];
      const activeProfId = (d && d.profiles && d.profiles.active_profile) ? d.profiles.active_profile : 'default';
      const activeMeta = (d && d.profiles && d.profiles.active_meta) ? d.profiles.active_meta : {};

      let listHtml = '';
      if (profiles.length > 0) {
        listHtml = profiles.map(p => {
          const isActive = p.id === activeProfId || p.is_active;
          return `
            <div style="padding: 10px 14px; background: ${isActive ? 'rgba(0, 240, 255, 0.08)' : 'rgba(255, 255, 255, 0.04)'}; border: 1px solid ${isActive ? 'rgba(0, 240, 255, 0.4)' : 'rgba(255, 255, 255, 0.1)'}; border-radius: 12px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
              <div>
                <div style="font-weight: 700; font-size: 13px; color: ${isActive ? '#00f0ff' : '#f1f5f9'};">
                  ${p.display_name || p.id}
                </div>
                <div style="font-size: 11px; color: #94a3b8; direction: ltr; text-align: right;">
                  ${p.email || 'پروفایل Codex'}
                </div>
              </div>
              <div>
                ${isActive 
                  ? '<span style="font-size: 11px; background: #00f0ff; color: #000; font-weight: 700; padding: 3px 10px; border-radius: 9999px;">فعال</span>'
                  : `<button class="cpe-btn-switch-target" data-id="${p.id}" style="padding: 5px 12px; background: rgba(0, 240, 255, 0.18); border: 1px solid rgba(0, 240, 255, 0.4); color: #00f0ff; border-radius: 8px; font-size: 12px; cursor: pointer; font-weight: 600; font-family: inherit;">🔄 سوئیچ</button>`
                }
              </div>
            </div>
          `;
        }).join('');
      } else {
        listHtml = `
          <div style="padding: 14px; text-align: center; background: rgba(255,255,255,0.03); border-radius: 10px; color: #94a3b8; font-size: 12px; margin-bottom: 8px;">
            حساب فعال: <strong style="color: #00f0ff;">${activeMeta.email || 'Active User'}</strong>
          </div>
        `;
      }

      container.innerHTML = `
        <div style="width: 100%;">
          <div style="margin-bottom: 10px; font-size: 12px; color: #94a3b8; display: flex; justify-content: space-between; align-items: center;">
            <span>پروفایل‌های ذخیره‌شده سشن‌های Codex / ChatGPT:</span>
            ${activeMeta.auth_mode ? `<span style="font-size: 10.5px; background: rgba(255,255,255,0.08); padding: 2px 7px; border-radius: 6px; color: #cbd5e1;">حالت: ${activeMeta.auth_mode}</span>` : ''}
          </div>
          <div style="max-height: 180px; overflow-y: auto; margin-bottom: 14px;">
            ${listHtml}
          </div>

          <div style="background: rgba(255,255,255,0.03); border: 1px dashed rgba(255,255,255,0.15); border-radius: 12px; padding: 12px; margin-bottom: 14px;">
            <div style="font-size: 12px; color: #cbd5e1; margin-bottom: 8px;">💾 ذخیره سشن لاگین‌شده فعلی به عنوان پروفایل:</div>
            <div style="display: flex; gap: 8px;">
              <input type="text" id="cpe-new-prof-name" placeholder="نام نمایشی (مثلاً اکانت کاری یا VIP 2)" style="flex: 1; padding: 8px 12px; border-radius: 8px; background: #1e293b; border: 1px solid rgba(255,255,255,0.15); color: #fff; font-size: 12px; font-family: inherit;">
              <button id="cpe-btn-save-prof" style="padding: 8px 14px; background: #00f0ff; color: #000; border: none; border-radius: 8px; font-weight: 700; font-size: 12px; cursor: pointer; font-family: inherit;">ذخیره</button>
            </div>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
            <button id="cpe-btn-launch-inst2" style="padding: 10px; background: rgba(168, 85, 247, 0.2); border: 1px solid rgba(168, 85, 247, 0.4); color: #c084fc; border-radius: 12px; font-weight: 600; cursor: pointer; font-size: 12px; font-family: inherit;">
              🚀 پنجره دوم همزمان (اکانت ۲)
            </button>
            <button id="cpe-btn-open-hub" style="padding: 10px; background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.15); color: #fff; border-radius: 12px; font-weight: 600; cursor: pointer; font-size: 12px; font-family: inherit;">
              🎛 پنل کامل Antigravity
            </button>
          </div>
        </div>
      `;

      // Switch profile listeners
      container.querySelectorAll('.cpe-btn-switch-target').forEach(btn => {
        btn.onclick = async () => {
          const profId = btn.getAttribute('data-id');
          btn.disabled = true;
          btn.textContent = '⏳ در حال تغییر...';
          try {
            let ok = false;
            try {
              const res = await window.callCpeBackend('switch', { profile_id: profId });
              ok = res && (res.success !== false);
            } catch(e) {}
            if (ok) {
              showToast(`✅ اکانت به '${profId}' سوئیچ شد. در حال بازنشانی...`);
              setTimeout(() => {
                modal.classList.remove('cpe-open');
                window.location.reload();
              }, 1200);
            } else {
              showToast(`❌ خطا در تغییر اکانت`, true);
              btn.disabled = false;
              btn.textContent = '🔄 سوئیچ';
            }
          } catch (e) {
            showToast(`❌ خطا: ${e.message}`, true);
            btn.disabled = false;
            btn.textContent = '🔄 سوئیچ';
          }
        };
      });

      // Save profile listener
      const saveBtn = document.getElementById('cpe-btn-save-prof');
      if (saveBtn) {
        saveBtn.onclick = async () => {
          const inp = document.getElementById('cpe-new-prof-name');
          const val = (inp.value || '').trim();
          if (!val) {
            showToast('لطفاً یک نام وارد کنید', true);
            return;
          }
          saveBtn.disabled = true;
          saveBtn.textContent = '⏳ ...';
          const cleanId = val.toLowerCase().replace(/[^a-z0-9_-]/g, '_');
          try {
            await window.callCpeBackend('save_profile', { profile_id: cleanId, name: val });
            showToast(`✅ اکانت '${val}' ذخیره شد`);
            openAccountModal('switch');
          } catch(e) {
            showToast(`خطا در ذخیره اکانت: ${e.message || e}`, true);
            saveBtn.disabled = false;
            saveBtn.textContent = 'ذخیره';
          }
        };
      }

      // Instance 2 button
      const inst2Btn = document.getElementById('cpe-btn-launch-inst2');
      if (inst2Btn) {
        inst2Btn.onclick = () => {
          window.callCpeBackend('launch', { instance: 2 }).catch(() => {});
          showToast('🚀 پنجره اکانت ۲ اجرا شد.');
          modal.classList.remove('cpe-open');
        };
      }

      // Hub button
      const hubBtn = document.getElementById('cpe-btn-open-hub');
      if (hubBtn) {
        hubBtn.onclick = () => {
          window.open('http://127.0.0.1:39285', '_blank');
          modal.classList.remove('cpe-open');
        };
      }
    }

    function renderLoginTab(container, d) {
      const activeMeta = (d && d.profiles && d.profiles.active_meta) ? d.profiles.active_meta : {};
      const hasActive = activeMeta && activeMeta.exists;
      const currentEmail = activeMeta.email || 'ناشناس';
      const profileList = (d && d.profiles && Array.isArray(d.profiles.profiles)) ? d.profiles.profiles : [];
      const savedProfile = profileList.find(p => p.has_auth);

      container.innerHTML = `
        <div style="width: 100%;">
          <!-- Active Status Notice -->
          <div style="padding: 10px 14px; background: rgba(0, 240, 255, 0.06); border: 1px solid rgba(0, 240, 255, 0.2); border-radius: 12px; margin-bottom: 14px; display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: ${hasActive ? '#10b981' : '#f59e0b'}; box-shadow: 0 0 8px ${hasActive ? '#10b981' : '#f59e0b'};"></span>
              <span style="font-size: 12px; color: #cbd5e1;">وضعیت نشست جاری:</span>
            </div>
            <span style="font-size: 12px; font-weight: 700; color: #00f0ff;">${hasActive ? currentEmail : 'وارد نشده'}</span>
          </div>

          ${(!hasActive && savedProfile) ? `
          <!-- Quick Restore Saved Profile Banner -->
          <div style="padding: 10px 14px; background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">
            <div>
              <div style="font-weight: 700; font-size: 12px; color: #10b981;">نشست ذخیره‌شده آماده: ${savedProfile.email}</div>
              <div style="font-size: 11px; color: #94a3b8;">می‌توانید فوراً این اکانت را فعال و بازیابی کنید.</div>
            </div>
            <button id="cpe-btn-quick-restore" style="padding: 6px 12px; background: #10b981; color: #000; font-weight: 700; border: none; border-radius: 8px; font-size: 11.5px; cursor: pointer; font-family: inherit;">
              ⚡️ فعال‌سازی سریع
            </button>
          </div>
          ` : ''}

          <!-- Option 1: Browser OAuth Login -->
          <div style="padding: 14px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; margin-bottom: 12px;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 16px;">🌐</span>
                <strong style="font-size: 13px; color: #f1f5f9;">ورود رسمی با مرورگر (OpenAI OAuth)</strong>
              </div>
              <span style="font-size: 10.5px; padding: 2px 8px; border-radius: 6px; background: rgba(0, 240, 255, 0.12); color: #00f0ff; border: 1px solid rgba(0, 240, 255, 0.3);">پیشنهادی</span>
            </div>
            <div style="font-size: 11.5px; color: #94a3b8; line-height: 1.5; margin-bottom: 10px;">
              ورود استاندارد رسمی با مرورگر. هم برای نرم‌افزار دسکتاپ و هم نشست کلاینت ذخیره می‌شود.
            </div>
            <button id="cpe-btn-app-signin" style="width: 100%; margin-bottom: 8px; padding: 10px; background: rgba(0, 240, 255, 0.15); border: 1px solid rgba(0, 240, 255, 0.4); color: #00f0ff; font-weight: 700; border-radius: 10px; cursor: pointer; font-size: 12.5px; font-family: inherit; transition: all 0.2s ease;">
              🚀 ورود رسمی در پنجره ChatGPT (Continue to sign in)
            </button>
            <div style="display: flex; gap: 8px;">
              <button id="cpe-btn-oauth-login" style="flex: 1; padding: 9px 12px; background: #00f0ff; color: #000; font-weight: 700; border: none; border-radius: 10px; cursor: pointer; font-size: 12px; font-family: inherit; transition: all 0.2s ease;">
                🔑 شروع لاگین با مرورگر (codex login)
              </button>
              <button id="cpe-btn-web-login" style="padding: 9px 12px; background: rgba(255,255,255,0.08); color: #cbd5e1; font-weight: 600; border: 1px solid rgba(255,255,255,0.15); border-radius: 10px; cursor: pointer; font-size: 11.5px; font-family: inherit; transition: all 0.2s ease;" title="ورود مستقیم به وبسایت ChatGPT">
                🌐 وب ChatGPT
              </button>
            </div>
            <div id="cpe-oauth-direct-box" style="display: none; margin-top: 10px; padding: 10px; background: rgba(0, 240, 255, 0.05); border: 1px dashed rgba(0, 240, 255, 0.3); border-radius: 8px;">
              <div style="font-size: 11px; color: #cbd5e1; margin-bottom: 6px;">لینک احراز هویت اختصاصی:</div>
              <div style="display: flex; gap: 6px;">
                <input id="cpe-oauth-url-inp" readonly style="flex: 1; padding: 6px 8px; border-radius: 6px; background: #0f172a; border: 1px solid rgba(255,255,255,0.15); color: #00f0ff; font-size: 10.5px; font-family: monospace; direction: ltr;">
                <button id="cpe-btn-copy-oauth" style="padding: 6px 10px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: #fff; border-radius: 6px; font-size: 11px; cursor: pointer; font-family: inherit;">کپی</button>
                <button id="cpe-btn-open-oauth" style="padding: 6px 10px; background: #00f0ff; border: none; color: #000; font-weight: 700; border-radius: 6px; font-size: 11px; cursor: pointer; font-family: inherit;">باز کردن</button>
              </div>
            </div>
          </div>

          <!-- Option 2: Isolated Instance 2 -->
          <div style="padding: 14px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
              <span style="font-size: 16px;">🚀</span>
              <strong style="font-size: 13px; color: #f1f5f9;">اجرای پنجره دوم برای ورود همزمان (اکانت ۲)</strong>
            </div>
            <div style="font-size: 11.5px; color: #94a3b8; line-height: 1.5; margin-bottom: 10px;">
              بدون خروج از این اکانت، یک پنجره کاملاً مستقل با حافظه و کش مجزا اجرا کنید و در آن به اکانت دوم خود وارد شوید.
            </div>
            <button id="cpe-btn-login-inst2" style="width: 100%; padding: 10px; background: rgba(168, 85, 247, 0.2); border: 1px solid rgba(168, 85, 247, 0.4); color: #c084fc; font-weight: 600; border-radius: 10px; cursor: pointer; font-size: 12.5px; font-family: inherit; transition: all 0.2s ease;">
              ⚡️ باز کردن محیط ایزوله (ChatGPT Instance 2)
            </button>
          </div>

          <!-- Option 3: API Key Direct Auth -->
          <div style="padding: 14px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
              <span style="font-size: 16px;">🔑</span>
              <strong style="font-size: 13px; color: #f1f5f9;">ورود مستقیم با OpenAI API Key</strong>
            </div>
            <div style="font-size: 11.5px; color: #94a3b8; margin-bottom: 8px;">
              در صورتی که کلید API اختصاصی دارید، آن را در کادر زیر وارد کنید:
            </div>
            <div style="display: flex; gap: 8px;">
              <input type="password" id="cpe-inp-apikey" placeholder="sk-..." style="flex: 1; padding: 8px 12px; border-radius: 8px; background: #1e293b; border: 1px solid rgba(255,255,255,0.15); color: #fff; font-size: 12px; font-family: monospace; direction: ltr;">
              <button id="cpe-btn-apikey-login" style="padding: 8px 14px; background: rgba(0, 240, 255, 0.18); border: 1px solid rgba(0, 240, 255, 0.4); color: #00f0ff; border-radius: 8px; font-weight: 700; font-size: 12px; cursor: pointer; font-family: inherit;">ثبت</button>
            </div>
          </div>

          <!-- Option 4: Sign Out / Logout -->
          <div style="padding: 12px 14px; background: rgba(239, 68, 68, 0.06); border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 14px; display: flex; align-items: center; justify-content: space-between;">
            <div>
              <div style="font-weight: 700; font-size: 12.5px; color: #ef4444;">خروج امن از حساب جاری</div>
              <div style="font-size: 11px; color: #94a3b8;">پاکسازی نشست فعلی برای لاگین با اکانت جدید</div>
            </div>
            <button id="cpe-btn-logout" style="padding: 7px 14px; background: rgba(239, 68, 68, 0.18); border: 1px solid rgba(239, 68, 68, 0.4); color: #ef4444; border-radius: 8px; font-weight: 700; font-size: 12px; cursor: pointer; font-family: inherit;">
              🚪 خروج (Sign Out)
            </button>
          </div>
        </div>
      `;

      // Option 1 OAuth actions & polling
      const btnAppSignin = document.getElementById('cpe-btn-app-signin');
      const btnQuickRestore = document.getElementById('cpe-btn-quick-restore');
      const btnOAuth = document.getElementById('cpe-btn-oauth-login');
      const btnWebLogin = document.getElementById('cpe-btn-web-login');
      const directBox = document.getElementById('cpe-oauth-direct-box');
      const directInp = document.getElementById('cpe-oauth-url-inp');
      const btnCopyOauth = document.getElementById('cpe-btn-copy-oauth');
      const btnOpenOauth = document.getElementById('cpe-btn-open-oauth');

      if (btnAppSignin) {
        btnAppSignin.onclick = () => {
          const btns = Array.from(document.querySelectorAll('button'));
          const nativeBtn = btns.find(b => b.innerText && (b.innerText.includes('Continue to sign in') || b.innerText.includes('Sign in')));
          if (nativeBtn && !nativeBtn.id.startsWith('cpe-')) {
            nativeBtn.click();
            showToast('🚀 ورود رسمی نرم‌افزار فعال شد. لطفاً در مرورگر لاگین کنید.');
          } else {
            window.open('https://chatgpt.com/auth/login', '_blank');
            showToast('🌐 صفحه رسمی ورود ChatGPT باز شد.');
          }
        };
      }

      if (btnQuickRestore && savedProfile) {
        btnQuickRestore.onclick = async () => {
          btnQuickRestore.disabled = true;
          btnQuickRestore.textContent = '⏳ ...';
          try {
            const resp = await window.callCpeBackend('switch', { profile: savedProfile.id });
            if (resp && resp.success) {
              showToast('✅ نشست با موفقیت بازیابی و فعال شد');
              setTimeout(() => window.location.reload(), 800);
            } else {
              showToast(`❌ خطا: ${(resp && resp.message) || 'ناموفق'}`, true);
              btnQuickRestore.disabled = false;
              btnQuickRestore.textContent = '⚡️ فعال‌سازی سریع';
            }
          } catch(e) {
            showToast(`خطا: ${e.message}`, true);
            btnQuickRestore.disabled = false;
            btnQuickRestore.textContent = '⚡️ فعال‌سازی سریع';
          }
        };
      }

      if (btnWebLogin) {
        btnWebLogin.onclick = () => {
          window.open('https://chatgpt.com/auth/login', '_blank');
          showToast('🌐 صفحه رسمی ورود ChatGPT باز شد.');
        };
      }

      if (btnCopyOauth && directInp) {
        btnCopyOauth.onclick = () => {
          if (directInp.value) {
            navigator.clipboard.writeText(directInp.value).then(() => {
              showToast('📋 لینک ورود کپی شد.');
            }).catch(() => {
              directInp.select();
              document.execCommand('copy');
              showToast('📋 لینک ورود کپی شد.');
            });
          }
        };
      }

      if (btnOpenOauth && directInp) {
        btnOpenOauth.onclick = () => {
          if (directInp.value) {
            window.open(directInp.value, '_blank');
          }
        };
      }

      let loginPollTimer = null;
      function startLoginPolling(initialEmail) {
        if (loginPollTimer) clearInterval(loginPollTimer);
        let checks = 0;
        loginPollTimer = setInterval(async () => {
          checks++;
          if (checks > 90) { // ~3.5 minutes
            clearInterval(loginPollTimer);
            return;
          }
          try {
            const data = await window.callCpeBackend('status');
            const activeMeta = (data && data.profiles && (data.profiles.active_meta || data.profiles.active)) || {};
            const nowEmail = activeMeta.email || '';
            if (activeMeta.exists && nowEmail && nowEmail !== initialEmail && nowEmail !== 'Active User') {
              clearInterval(loginPollTimer);
              showToast(`🎉 ورود موفقیت‌آمیز بود! حساب ${nowEmail} متصل گردید.`);
              setTimeout(() => {
                openAccountModal('switch');
              }, 1200);
              return;
            }
          } catch(e) {}
        }, 2500);
      }

      if (btnOAuth) {
        btnOAuth.onclick = async () => {
          btnOAuth.disabled = true;
          btnOAuth.textContent = '⏳ در حال دریافت آدرس ورود و اجرای مرورگر...';
          try {
            const data = await window.callCpeBackend('login', { mode: 'oauth' });
            const ok = data && data.success !== false;
            const authUrl = data && (data.auth_url || (data.message && data.message.auth_url));
            const msg = data && data.message;

            if (authUrl) {
              if (directBox && directInp) {
                directInp.value = authUrl;
                directBox.style.display = 'block';
              }
              try {
                window.open(authUrl, '_blank');
              } catch(e) {}
              showToast('🌐 مرورگر باز شد. لطفاً ورود را در سایت OpenAI تکمیل کنید.');
              btnOAuth.textContent = '🔄 در انتظار تکمیل ورود در مرورگر...';
              startLoginPolling(currentEmail);
            } else if (ok) {
              showToast('🌐 فرآیند ورود آغاز شد.');
              btnOAuth.textContent = '🔄 در انتظار تکمیل ورود...';
              startLoginPolling(currentEmail);
            } else {
              showToast('خطا در اجرای فرآیند ورود: ' + (typeof msg === 'string' ? msg : 'خطای ناشناخته'), true);
              btnOAuth.disabled = false;
              btnOAuth.textContent = '🔑 شروع ورود از طریق مرورگر (codex login)';
            }
          } catch(e) {
            showToast('خطا در ارتباط با سرور: ' + (e.message || e), true);
            btnOAuth.disabled = false;
            btnOAuth.textContent = '🔑 شروع ورود از طریق مرورگر (codex login)';
          }
        };
      }

      // Option 2 Instance 2 action
      const btnInst2 = document.getElementById('cpe-btn-login-inst2');
      if (btnInst2) {
        btnInst2.onclick = () => {
          window.callCpeBackend('launch', { instance: 2 }).catch(() => {});
          showToast('🚀 پنجره مستقل اکانت ۲ اجرا شد');
          modal.classList.remove('cpe-open');
        };
      }

      // Option 3 API Key action
      const btnApiKey = document.getElementById('cpe-btn-apikey-login');
      if (btnApiKey) {
        btnApiKey.onclick = async () => {
          const inp = document.getElementById('cpe-inp-apikey');
          const keyVal = (inp.value || '').trim();
          if (!keyVal) {
            showToast('لطفاً کلید API را وارد کنید', true);
            return;
          }
          btnApiKey.disabled = true;
          btnApiKey.textContent = '⏳ ...';
          try {
            const resp = await window.callCpeBackend('login', { mode: 'api_key', api_key: keyVal });
            if (resp && resp.success) {
              showToast('✅ کلید API با موفقیت ثبت و تایید شد');
              setTimeout(() => window.location.reload(), 1500);
            } else {
              showToast(`❌ خطا در تایید کلید: ${(resp && resp.message) || 'نامعتبر'}`, true);
              btnApiKey.disabled = false;
              btnApiKey.textContent = 'ثبت';
            }
          } catch(e) {
            showToast(`خطا: ${e.message}`, true);
            btnApiKey.disabled = false;
            btnApiKey.textContent = 'ثبت';
          }
        };
      }

      // Option 4 Logout action
      const btnLogout = document.getElementById('cpe-btn-logout');
      if (btnLogout) {
        btnLogout.onclick = async () => {
          if (!confirm('آیا از خروج از نشست فعلی اطمینان دارید؟')) return;
          btnLogout.disabled = true;
          btnLogout.textContent = '⏳ در حال خروج...';
          try {
            await window.callCpeBackend('logout');
            showToast('🚪 خروج انجام شد. اکنون می‌توانید وارد اکانت دیگری شوید.');
            setTimeout(() => {
              modal.classList.remove('cpe-open');
              window.location.reload();
            }, 1200);
          } catch(e) {
            showToast('خطا در خروج از حساب', true);
            btnLogout.disabled = false;
            btnLogout.textContent = '🚪 خروج (Sign Out)';
          }
        };
      }
    }

    // Tab button events
    const tabSwitchBtn = document.getElementById('cpe-tab-btn-switch');
    if (tabSwitchBtn) {
      tabSwitchBtn.onclick = () => {
        currentTab = 'switch';
        renderTabs();
      };
    }
    const tabLoginBtn = document.getElementById('cpe-tab-btn-login');
    if (tabLoginBtn) {
      tabLoginBtn.onclick = () => {
        currentTab = 'login';
        renderTabs();
      };
    }

    renderTabs();
  }

  // 8. Window Exports, Bootstrap & Watchdog
  window.__cpe_open_account_modal = openAccountModal;
  window.__cpe_open_theme_modal = openThemeModal;
  window.__cpe_render_hud = renderHUD;
  window.__cpe_apply_theme = applyThemeAndFont;
  window.__cpe_save_settings = saveSettings;
  window.__cpe_show_toast = showToast;

  function boot() {
    applyThemeAndFont();
    renderHUD();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  if (window.__cpe_watchdog_timer) {
    clearInterval(window.__cpe_watchdog_timer);
    window.__cpe_watchdog_timer = null;
  }

  console.log('[ChatGPT Enhanced] UI Enhancement Suite Successfully Mounted!');
})();
'''

final_script = template.replace("__VAZIR_B64__", vazir_b64)

target_path = Path("chatgpt_theme_injector.js")
target_path.write_text(final_script, encoding="utf-8")
print(f"Written chatgpt_theme_injector.js: {len(final_script)} chars")

global_bin = HOME / ".gemini" / "antigravity" / "bin" / "chatgpt_theme_injector.js"
if global_bin.parent.exists():
    global_bin.write_text(final_script, encoding="utf-8")
    print(f"Synced to global bin: {global_bin}")

