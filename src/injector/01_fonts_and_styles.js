  // Local-first bundled WOFF2 fonts; external webfonts load lazily only on explicit selection.
  let localFontsStyle = document.getElementById('aqm-local-fonts');
  if (!localFontsStyle) {
    localFontsStyle = document.createElement('style');
    localFontsStyle.id = 'aqm-local-fonts';
    safeAppendToHead(localFontsStyle);
  }
  localFontsStyle.textContent = `
    @font-face {
      font-family: 'Vazirmatn';
      font-style: normal;
      font-weight: 100 900;
      font-display: swap;
      src: local('Vazirmatn'), url("http://127.0.0.1:39281/fonts/Vazirmatn[wght].woff2") format("woff2");
    }
    @font-face {
      font-family: 'Estedad';
      font-style: normal;
      font-weight: 100 900;
      font-display: swap;
      src: local('Estedad'), url("http://127.0.0.1:39281/fonts/Estedad[wght].woff2") format("woff2");
    }
    @font-face {
      font-family: 'Outfit';
      font-style: normal;
      font-weight: 100 900;
      font-display: swap;
      src: local('Outfit'), url("http://127.0.0.1:39281/fonts/Outfit[wght].woff2") format("woff2");
    }
  `;

  const LAZY_WEBFONT_URLS = {
    'Sahel': 'https://cdn.jsdelivr.net/gh/rastikerdar/sahel-font@v3.4.0/dist/font-face.css',
    'Shabnam': 'https://cdn.jsdelivr.net/gh/rastikerdar/shabnam-font@v5.0.1/dist/font-face.css',
    'Samim': 'https://cdn.jsdelivr.net/gh/rastikerdar/samim-font@v4.0.5/dist/font-face.css',
    'Lalezar': 'https://fonts.googleapis.com/css2?family=Lalezar&display=swap',
    'Fredoka': 'https://fonts.googleapis.com/css2?family=Fredoka:wght@400;500;600;700&display=swap',
    'Space Grotesk': 'https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&display=swap',
    'Plus Jakarta Sans': 'https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap',
    'Noto Sans Arabic': 'https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@400;500;600;700&display=swap',
    'Inter': 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap',
    'JetBrains Mono': 'https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;600;700&display=swap'
  };

  let customImportedFonts = [];
  try {
    const fromSettings = Array.isArray(userSettings.customImportedFonts) ? userSettings.customImportedFonts : [];
    let fromStorage = [];
    try {
      const savedImported = localStorage.getItem('antigravity:custom_imported_fonts');
      if (savedImported) fromStorage = JSON.parse(savedImported) || [];
    } catch (e) {}
    const map = new Map();
    [...fromStorage, ...fromSettings].forEach(f => {
      if (!f || !f.id) return;
      const key = f.id.toLowerCase();
      const existing = map.get(key);
      if (!existing || (!existing.data && f.data)) {
        map.set(key, f);
      }
    });
    customImportedFonts = Array.from(map.values());
  } catch (e) {
    customImportedFonts = [];
  }

  function sanitizeFontName(name) {
    if (!name || typeof name !== 'string') return '';
    return name.replace(/[^a-zA-Z0-9\s\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF\-_]/g, '').trim().slice(0, 50);
  }

  function sanitizeFontUrl(url) {
    if (!url || typeof url !== 'string') return '';
    const trimmed = url.trim();
    if (!trimmed || !/^https?:\/\//i.test(trimmed)) return '';
    return trimmed.replace(/[^a-zA-Z0-9\:\/\.\_\-\?\&\=\%\+\@\;\,\#]/g, '').slice(0, 500);
  }

  function getFontFormatFromFileName(fileName) {
    if (!fileName) return 'woff2';
    const ext = fileName.split('.').pop().toLowerCase();
    if (ext === 'woff2') return 'woff2';
    if (ext === 'woff') return 'woff';
    if (ext === 'ttf') return 'truetype';
    if (ext === 'otf') return 'opentype';
    return 'woff2';
  }

  function deriveFontNameFromFile(fileName) {
    if (!fileName) return '';
    return sanitizeFontName(fileName.replace(/\.[^/.]+$/, '').replace(/[-_]+/g, ' ').trim());
  }

  function cleanFontName(fontStr) {
    if (!fontStr) return '';
    return fontStr.replace(/,\s*(sans-serif|serif|monospace|system-ui)/gi, '').replace(/['"]/g, '').trim();
  }

  function injectImportedFontStyles() {
    customImportedFonts.forEach(f => {
      if (!f || !f.id) return;
      const safeId = sanitizeFontName(f.id);
      if (!safeId) return;
      if (f.data && typeof f.data === 'string' && /^data:/i.test(f.data)) {
        const styleId = `aqm-cfont-data-${encodeURIComponent(safeId.replace(/\s+/g, '-'))}`;
        let styleEl = document.getElementById(styleId);
        if (!styleEl) {
          styleEl = document.createElement('style');
          styleEl.id = styleId;
          const formatStr = f.format ? ` format("${sanitizeFontName(f.format)}")` : '';
          styleEl.textContent = `@font-face { font-family: '${safeId}'; src: url("${f.data}")${formatStr}; font-display: swap; }`;
          safeAppendToHead(styleEl);
        }
        try {
          if (typeof FontFace !== 'undefined' && document.fonts) {
            const fontFace = new FontFace(safeId, `url("${f.data}")`);
            fontFace.load().then(loadedFace => document.fonts.add(loadedFace)).catch(() => {});
          }
        } catch (e) {}
      } else if (f.url && f.url.trim()) {
        const cleanUrl = sanitizeFontUrl(f.url);
        if (!cleanUrl) return;
        const id = `aqm-cfont-${encodeURIComponent(safeId.replace(/\s+/g, '-'))}`;
        if (!document.getElementById(id)) {
          const link = document.createElement('link');
          link.id = id;
          link.rel = 'stylesheet';
          link.href = cleanUrl;
          safeAppendToHead(link);
        }
      }
    });
  }
  injectImportedFontStyles();

  function ensureFontLoaded(fontName) {
    if (!fontName || fontName === 'default') return;
    const cdnUrl = LAZY_WEBFONT_URLS[fontName];
    if (cdnUrl) {
      const linkId = `aqm-lazy-font-${encodeURIComponent(fontName.replace(/\s+/g, '-'))}`;
      if (!document.getElementById(linkId)) {
        const link = document.createElement('link');
        link.id = linkId;
        link.rel = 'stylesheet';
        link.href = cdnUrl;
        safeAppendToHead(link);
      }
    }
    try {
      if (document.fonts && document.fonts.load) {
        document.fonts.load(`14px "${fontName}"`).catch(() => {});
      }
    } catch (e) {}
  }

  let style = document.getElementById('aqm-styles');
  if (!style) {
    style = document.createElement('style');
    style.id = 'aqm-styles';
    safeAppendToHead(style);
  }
  style.textContent = `
    @keyframes aqm-pulse-dot {
      0%, 100% { transform: scale(1); opacity: 1; filter: drop-shadow(0 0 5px currentColor); }
      50% { transform: scale(0.75); opacity: 0.5; filter: drop-shadow(0 0 1px currentColor); }
    }
    @keyframes aqm-spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
    @keyframes aqm-pop-in {
      0% { opacity: 0; transform: translateY(8px) scale(0.97); }
      100% { opacity: 1; transform: translateY(0) scale(1); }
    }
    .aqm-rotating {
      animation: aqm-spin 0.75s cubic-bezier(0.4, 0, 0.2, 1) infinite !important;
      display: inline-block !important;
    }
    .aqm-model-row {
      transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.2s ease;
    }
    .aqm-model-row:hover {
      transform: translateY(-1px);
      box-shadow: 0 4px 16px -2px rgba(0, 0, 0, 0.4);
    }
    .aqm-task-active,
    #antigravity-account-pill.aqm-consuming {
      border-color: #fbbf24 !important;
      box-shadow: 0 0 14px rgba(251, 191, 36, 0.85), inset 0 0 6px rgba(251, 191, 36, 0.4) !important;
      animation: aqm-yellow-pulse 1.6s infinite ease-in-out !important;
    }
    @keyframes aqm-yellow-pulse {
      0%, 100% {
        box-shadow: 0 0 14px rgba(251, 191, 36, 0.85), inset 0 0 6px rgba(251, 191, 36, 0.4);
        border-color: #fbbf24;
      }
      50% {
        box-shadow: 0 0 6px rgba(251, 191, 36, 0.4), inset 0 0 2px rgba(251, 191, 36, 0.2);
        border-color: #f59e0b;
      }
    }
    .aqm-custom-scroll::-webkit-scrollbar { width: 4px; }
    .aqm-custom-scroll::-webkit-scrollbar-track { background: transparent; }
    .aqm-custom-scroll::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.15);
      border-radius: 10px;
    }
    .aqm-switcher-modal {
      position: fixed !important;
      inset: 0 !important;
      background: rgba(0, 0, 0, 0.68) !important;
      backdrop-filter: blur(18px) !important;
      -webkit-backdrop-filter: blur(18px) !important;
      z-index: 2147483647 !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      opacity: 0 !important;
      pointer-events: none !important;
      visibility: hidden !important;
      transition: opacity 0.2s cubic-bezier(0.16, 1, 0.3, 1), visibility 0.2s !important;
    }
    .aqm-switcher-modal.aqm-active {
      opacity: 1 !important;
      pointer-events: auto !important;
      visibility: visible !important;
    }
    .aqm-switcher-sheet {
      width: 560px !important;
      max-width: 92vw !important;
      height: 540px !important;
      max-height: 88vh !important;
      border-radius: 18px !important;
      background: rgba(13, 17, 24, 0.94) !important;
      backdrop-filter: blur(30px) saturate(180%) !important;
      -webkit-backdrop-filter: blur(30px) saturate(180%) !important;
      border: 1px solid rgba(255, 255, 255, 0.08) !important;
      box-shadow: 0 20px 60px -10px rgba(0, 0, 0, 0.75), inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
      display: flex !important;
      flex-direction: column !important;
      overflow: hidden !important;
      transform: scale(0.97) translateY(6px) !important;
      transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1) !important;
      user-select: none !important;
      font-family: 'Vazirmatn', 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
      letter-spacing: normal !important;
      line-height: 1.65 !important;
      -webkit-font-smoothing: antialiased !important;
    }
    .aqm-switcher-modal.aqm-active .aqm-switcher-sheet {
      transform: scale(1) translateY(0) !important;
    }
    .aqm-sw-tab-btn {
      padding: 5px 14px !important;
      border-radius: 9999px !important;
      font-size: 11.5px !important;
      font-weight: 600 !important;
      cursor: pointer !important;
      transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease !important;
      border: 1px solid transparent !important;
      background: transparent !important;
      color: #94a3b8 !important;
      display: flex !important;
      align-items: center !important;
      gap: 6px !important;
      letter-spacing: normal !important;
    }
    .aqm-sw-tab-btn:hover { color: #f8fafc !important; }
    .aqm-sw-tab-btn.active {
      background: rgba(255, 255, 255, 0.08) !important;
      border-color: rgba(255, 255, 255, 0.12) !important;
      color: #ffffff !important;
      box-shadow: 0 1px 6px rgba(0, 0, 0, 0.2) !important;
    }
    .aqm-sw-card {
      background: rgba(255, 255, 255, 0.02) !important;
      border: 1px solid rgba(255, 255, 255, 0.06) !important;
      border-radius: 14px !important;
      padding: 13px 15px !important;
      transition: background-color 0.15s ease, border-color 0.15s ease !important;
      letter-spacing: normal !important;
    }
    .aqm-sw-card:hover {
      background: rgba(255, 255, 255, 0.035) !important;
      border-color: rgba(255, 255, 255, 0.09) !important;
    }
    .aqm-sw-btn {
      display: inline-flex !important;
      align-items: center !important;
      justify-content: center !important;
      gap: 5px !important;
      padding: 4px 11px !important;
      border-radius: 9999px !important;
      font-size: 11px !important;
      font-weight: 600 !important;
      cursor: pointer !important;
      transition: transform 0.15s ease, background-color 0.15s ease, border-color 0.15s ease !important;
      border: 1px solid rgba(255, 255, 255, 0.1) !important;
      background: rgba(255, 255, 255, 0.04) !important;
      color: #f1f5f9 !important;
      letter-spacing: normal !important;
    }
    .aqm-sw-btn:hover {
      background: rgba(255, 255, 255, 0.08) !important;
      border-color: rgba(255, 255, 255, 0.18) !important;
    }
    .aqm-sw-btn:active { transform: scale(0.97) !important; }
    .aqm-sw-btn-primary {
      background: #3b82f6 !important;
      border-color: #60a5fa !important;
      color: #ffffff !important;
      box-shadow: 0 2px 8px rgba(59, 130, 246, 0.25) !important;
    }
    .aqm-sw-btn-primary:hover {
      background: #2563eb !important;
      box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4) !important;
    }
    .aqm-sw-toast {
      position: absolute !important;
      top: 14px !important;
      left: 50% !important;
      transform: translateX(-50%) translateY(-14px) !important;
      opacity: 0 !important;
      padding: 6px 14px !important;
      border-radius: 9999px !important;
      font-size: 11px !important;
      font-weight: 600 !important;
      z-index: 10000005 !important;
      transition: opacity 0.2s cubic-bezier(0.16, 1, 0.3, 1), transform 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
      pointer-events: none !important;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4) !important;
      background: rgba(15, 23, 42, 0.95) !important;
      border: 1px solid rgba(255, 255, 255, 0.14) !important;
      color: #ffffff !important;
      letter-spacing: normal !important;
    }
    .aqm-sw-toast.show {
      transform: translateX(-50%) translateY(0) !important;
      opacity: 1 !important;
      pointer-events: auto !important;
    }
    .aqm-sw-toast a {
      pointer-events: auto !important;
      cursor: pointer !important;
    }
  `;

  const THEMES = {
    neutral: {
      id: 'neutral',
      nameFa: 'هماهنگ با سیستم',
      nameEn: 'System Neutral',
      fontEn: "'Outfit', sans-serif",
      fontFa: "'Vazirmatn', sans-serif",
      cardBg: 'linear-gradient(155deg, rgba(18, 22, 31, 0.96) 0%, rgba(11, 14, 20, 0.98) 100%)',
      cardBorder: 'rgba(255, 255, 255, 0.12)',
      cardShadow: '0 24px 60px -10px rgba(0, 0, 0, 0.75), 0 0 1px rgba(255, 255, 255, 0.15)',
      accent: '#38bdf8',
      accentSecondary: '#818cf8',
      accentGrad: 'linear-gradient(90deg, #38bdf8 0%, #6366f1 100%)',
      accentGlow: '0 0 12px rgba(56, 189, 248, 0.25)',
      textColor: '#f8fafc',
      subText: '#94a3b8',
      itemBg: 'rgba(255, 255, 255, 0.04)',
      itemBorder: 'rgba(255, 255, 255, 0.08)',
      itemHoverBorder: 'rgba(255, 255, 255, 0.2)',
      dotColor: '#10b981',
      chipBg: 'rgba(255, 255, 255, 0.08)',
      chipColor: '#e2e8f0',
      isDark: true
    },
    midnight: {
      id: 'midnight',
      nameFa: 'شیشه نیمه‌شب',
      nameEn: 'Midnight Glass',
      fontEn: "'Outfit', sans-serif",
      fontFa: "'Vazirmatn', sans-serif",
      cardBg: 'linear-gradient(155deg, rgba(8, 12, 22, 0.97) 0%, rgba(4, 6, 12, 0.99) 100%)',
      cardBorder: 'rgba(56, 189, 248, 0.22)',
      cardShadow: '0 24px 64px -10px rgba(0, 0, 0, 0.88), 0 0 1px rgba(56, 189, 248, 0.2)',
      accent: '#22d3ee',
      accentSecondary: '#34d399',
      accentGrad: 'linear-gradient(90deg, #22d3ee 0%, #10b981 100%)',
      accentGlow: '0 0 12px rgba(34, 211, 238, 0.28)',
      textColor: '#f8fafc',
      subText: '#94a3b8',
      itemBg: 'rgba(15, 23, 42, 0.55)',
      itemBorder: 'rgba(148, 163, 184, 0.12)',
      itemHoverBorder: 'rgba(34, 211, 238, 0.35)',
      dotColor: '#34d399',
      chipBg: 'rgba(34, 211, 238, 0.1)',
      chipColor: '#e2e8f0',
      isDark: true
    }
  };

  let currentThemeId = 'neutral';
  if (userSettings.theme && THEMES[userSettings.theme]) {
    currentThemeId = userSettings.theme;
  } else {
    try {
      const savedTheme = localStorage.getItem('antigravity:quota_theme');
      if (savedTheme && THEMES[savedTheme]) currentThemeId = savedTheme;
    } catch (e) {}
  }

  let isFullAppThemingEnabled = true;
  if (userSettings.fullTheming !== undefined) {
    isFullAppThemingEnabled = Boolean(userSettings.fullTheming);
  } else {
    try {
      const savedAppTheming = localStorage.getItem('antigravity:full_app_theming');
      if (savedAppTheming !== null) isFullAppThemingEnabled = (savedAppTheming === 'true');
    } catch (e) {}
  }

  let customFontEn = (userSettings.fontEn && userSettings.fontEn !== 'default') ? userSettings.fontEn : 'default';
  if (customFontEn === 'default') {
    try {
      const savedEn = localStorage.getItem('antigravity:custom_font_en');
      if (savedEn) customFontEn = savedEn;
    } catch (e) {}
  }

  let customFontFa = (userSettings.fontFa && userSettings.fontFa !== 'default') ? userSettings.fontFa : 'default';
  if (customFontFa === 'default') {
    try {
      const savedFa = localStorage.getItem('antigravity:custom_font_fa');
      if (savedFa) customFontFa = savedFa;
    } catch (e) {}
  }

  function getActiveTheme() {
    return THEMES[currentThemeId] || THEMES.neutral;
  }

  function getEffectiveFonts(theme = getActiveTheme()) {
    const safeTheme = theme || getActiveTheme() || THEMES.neutral;
    const rawEn = (customFontEn !== 'default') ? cleanFontName(customFontEn) : cleanFontName(safeTheme.fontEn || 'Outfit');
    const rawFa = (customFontFa !== 'default') ? cleanFontName(customFontFa) : cleanFontName(safeTheme.fontFa || 'Vazirmatn');
    const fontEn = `'${rawEn}', sans-serif`;
    const fontFa = `'${rawFa}', sans-serif`;
    const fullFamily = `'${rawEn}', '${rawFa}', sans-serif`;
    return { rawEn, rawFa, fontEn, fontFa, fullFamily };
  }

  function applyAppWorkspaceTheme(theme = getActiveTheme(), enabled = isFullAppThemingEnabled) {
    const { fontEn, fontFa, fullFamily } = getEffectiveFonts(theme);

    let typoStyle = document.getElementById('aqm-typography-style');
    if (!typoStyle) {
      typoStyle = document.createElement('style');
      typoStyle.id = 'aqm-typography-style';
      safeAppendToHead(typoStyle);
    }
    typoStyle.textContent = `
      #antigravity-usage-popover { font-family: ${fullFamily} !important; }
      #antigravity-usage-popover [data-font="en"] { font-family: ${fontEn} !important; }
      #antigravity-usage-popover [data-font="fa"] { font-family: ${fontFa} !important; }
      #antigravity-usage-popover [data-font="mono"] { font-family: 'JetBrains Mono', monospace !important; }

      div.h-screen.w-screen > div.shrink-0 {
        position: relative !important;
        z-index: 99999 !important;
      }
      [data-radix-popper-content-wrapper],
      [role="menu"],
      [data-radix-menu-content],
      [role="dialog"] {
        z-index: 100000 !important;
        pointer-events: auto !important;
      }

      .markdown, [class*="prose"], .theme-standalone p, .theme-standalone li, .theme-standalone span,
      [data-testid*="user-input"], [data-testid*="user-input-step"] *, [data-testid*="chat-message"] *:not(pre):not(code),
      [class*="leading-relaxed"] *:not(pre):not(code), .line-content,
      [class*="conversation"] p, [class*="conversation"] span,
      [class*="conversation"] div:not([class*="code"]):not(pre),
      [class*="markdown-body"] *:not(pre):not(code),
      [contenteditable="true"], [contenteditable="true"] *, [data-lexical-text="true"], textarea[data-testid="ask-question-writein"] {
        font-family: ${fullFamily} !important;
      }
      .theme-standalone h1, .theme-standalone h2, .theme-standalone h3, .theme-standalone h4,
      [class*="conversation"] h1, [class*="conversation"] h2, [class*="conversation"] h3, [class*="conversation"] h4 {
        font-family: ${fullFamily} !important;
        letter-spacing: -0.01em;
      }
      .katex, .katex-display, .katex-html, math {
        font-family: KaTeX_Main, ${fullFamily} !important;
      }
      :not(pre) > code {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.9em !important;
      }
    `;

    const oldColorStyle = document.getElementById('aqm-app-workspace-theme');
    if (oldColorStyle) oldColorStyle.remove();

    if (typeof applyRtlStyles === 'function') applyRtlStyles();
  }
