  let rtlConfig = {
    isRTL: true,
    forceRTL: false,
    fixAtSign: true,
    lineHeight: '1.6',
    fontSize: '16'
  };
  try {
    if (userSettings.rtl) {
      const parsedRtl = typeof userSettings.rtl === 'string' ? JSON.parse(userSettings.rtl) : userSettings.rtl;
      rtlConfig = { ...rtlConfig, ...parsedRtl };
    } else {
      const savedRtl = localStorage.getItem('antigravity:rtl_config');
      if (savedRtl) rtlConfig = { ...rtlConfig, ...JSON.parse(savedRtl) };
    }
  } catch (e) {}

  function saveRtlConfig() {
    try { localStorage.setItem('antigravity:rtl_config', JSON.stringify(rtlConfig)); } catch (e) {}
    if (typeof persistUserSettings === 'function') persistUserSettings({ rtl: rtlConfig });
  }

  function applyRtlStyles() {
    let rtlStyle = document.getElementById('aqm-rtl-engine-style');
    if (!rtlConfig.isRTL) {
      if (rtlStyle) rtlStyle.remove();
      return;
    }
    if (!rtlStyle) {
      rtlStyle = document.createElement('style');
      rtlStyle.id = 'aqm-rtl-engine-style';
      safeAppendToHead(rtlStyle);
    }

    const forceRtlRule = rtlConfig.forceRTL ? `
      .prose p, .prose li, .prose h1, .prose h2, .prose h3, .prose h4, .prose blockquote,
      [data-testid="chat-message"] p, [data-testid="chat-message"] li,
      .markdown-body p, .markdown-body li,
      .leading-relaxed p, .leading-relaxed li {
        direction: rtl !important;
        text-align: right !important;
        unicode-bidi: isolate !important;
      }
    ` : '';

    rtlStyle.textContent = `
      .prose p, .prose li, .prose h1, .prose h2, .prose h3, .prose h4, .prose h5, .prose h6, .prose blockquote,
      .markdown-body p, .markdown-body li, .markdown-body h1, .markdown-body h2, .markdown-body h3,
      .leading-relaxed p, .leading-relaxed li, .leading-relaxed h1, .leading-relaxed h2, .leading-relaxed h3,
      [data-testid="chat-message"] p, [data-testid="chat-message"] li,
      label[for^="ask-opt-"] {
        unicode-bidi: plaintext !important;
        text-align: start !important;
      }

      ul:not(#_)[dir="rtl"], ol:not(#_)[dir="rtl"],
      [dir="rtl"] ul:not(#_), [dir="rtl"] ol:not(#_),
      ul[dir="rtl"], ol[dir="rtl"] {
        padding-left: 0 !important;
        padding-right: 1.25rem !important;
      }
      [dir="rtl"] ul:not(#_) ul:not(#_), [dir="rtl"] ul:not(#_) ol:not(#_),
      [dir="rtl"] ol:not(#_) ul:not(#_), [dir="rtl"] ol:not(#_) ol:not(#_),
      ul[dir="rtl"] ul, ul[dir="rtl"] ol,
      ol[dir="rtl"] ul, ol[dir="rtl"] ol {
        padding-left: 0 !important;
        padding-right: 2.5rem !important;
      }

      [class*="thinking"], [data-testid*="thinking"],
      [class*="thinking"] p, [class*="thinking"] li, [data-testid*="thinking"] p, [data-testid*="thinking"] li {
        unicode-bidi: plaintext !important;
        text-align: start !important;
      }

      pre, code, :not(pre) > code, pre *, code *, .katex, .katex-display, a[href^="file:"],
      [class*="thinking"] pre, [class*="thinking"] code,
      .line-content, [class*="code-block"] {
        unicode-bidi: isolate !important;
        direction: ltr !important;
        text-align: left !important;
      }

      [contenteditable="true"], [contenteditable="true"] p, textarea[data-testid="ask-question-writein"] {
        unicode-bidi: plaintext !important;
        text-align: start !important;
      }

      .prose p, .prose li, .markdown-body p, [data-testid="chat-message"] p, [data-testid="chat-message"] .leading-relaxed,
      .leading-relaxed, [data-testid="user-input-step"], [data-testid="user-input-step"] div,
      [data-lexical-text="true"], [contenteditable="true"], [contenteditable="true"] p, label[for^="ask-opt-"] {
        line-height: ${rtlConfig.lineHeight} !important;
      }
      .prose, [data-testid="chat-message"], .markdown-body, .leading-relaxed, [contenteditable="true"], [contenteditable="true"] p {
        font-size: ${rtlConfig.fontSize}px !important;
      }

      [role="navigation"][aria-label="Sidebar"] *,
      [role="navigation"][aria-label="Sidebar"] .truncate,
      [data-testid="chat-message"] .truncate,
      [class*="conversation"] .truncate {
        unicode-bidi: plaintext !important;
        text-align: start !important;
      }

      ${forceRtlRule}
    `;
  }

  const RTL_CHAR_REGEX = /[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/;
  const RTL_CHAR_GLOBAL = /[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/g;
  const LTR_CHAR_GLOBAL = /[A-Za-z\u00C0-\u024F]/g;
  const STRONG_CHAR_REGEX = /[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]|[A-Za-z\u00C0-\u024F]/;

  function detectElementDir(text) {
    const cleaned = String(text || '')
      .replace(/`[^`\n]+`/g, ' ')
      .replace(/\b(?:https?|vscode-file|file):\/\/[^\s<>"'`)\]]+/gi, ' ')
      .replace(/\b[A-Za-z]:[\\\/][^\s<>"'`)\]]+/g, ' ')
      .replace(/\\\\[^\s<>"'`)\]]+/g, ' ')
      .replace(/(?:^|[\s(])\/(?:[A-Za-z0-9._-]+\/)+[A-Za-z0-9._-]*/g, ' ');
    const rtlCount = (cleaned.match(RTL_CHAR_GLOBAL) || []).length;
    if (rtlCount < 1) return 'ltr';
    const ltrCount = (cleaned.match(LTR_CHAR_GLOBAL) || []).length;
    const firstStrong = cleaned.match(STRONG_CHAR_REGEX);
    const firstStrongIsRtl = firstStrong ? RTL_CHAR_REGEX.test(firstStrong[0]) : false;
    return (rtlCount >= ltrCount * 0.45 || firstStrongIsRtl) ? 'rtl' : 'ltr';
  }

  function isRtlProtectedElement(el) {
    if (!el || el.nodeType !== 1) return true;
    const tag = el.tagName;
    if (tag === 'PRE' || tag === 'CODE') return true;
    if (el.id && (el.id.startsWith('aqm-') || el.id.startsWith('antigravity-'))) return true;
    return Boolean(el.closest(
      '#antigravity-usage-popover, #antigravity-switcher-modal, #antigravity-quota-dock, [id^="aqm-"], [class*="aqm-"], pre, code, .katex, .katex-display'
    ));
  }

  function getElementTextExcludingCode(el) {
    if (!el) return '';
    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') return el.value || '';
    if (!el.querySelector || !el.querySelector('pre, code, .katex, a[href^="file:"]')) {
      return el.textContent || '';
    }
    let out = '';
    const walk = (node) => {
      for (let c = node.firstChild; c; c = c.nextSibling) {
        if (c.nodeType === 3) {
          out += c.nodeValue;
        } else if (c.nodeType === 1) {
          const tag = c.tagName;
          if (
            tag === 'PRE' ||
            tag === 'CODE' ||
            c.classList?.contains('katex') ||
            (tag === 'A' && (c.getAttribute('href') || '').startsWith('file:'))
          ) {
            continue;
          }
          walk(c);
        }
      }
    };
    walk(el);
    return out;
  }

  function applyDirAttr(el, text) {
    const trimmed = String(text || '').trim();
    if (!trimmed) {
      if (el.getAttribute('data-aqm-dir') === '1') {
        el.removeAttribute('dir');
        el.removeAttribute('data-aqm-dir');
      }
      return;
    }
    const targetDir = detectElementDir(trimmed);
    if (el.getAttribute('dir') !== targetDir) {
      el.setAttribute('dir', targetDir);
    }
    if (el.getAttribute('data-aqm-dir') !== '1') {
      el.setAttribute('data-aqm-dir', '1');
    }
  }

  function debouncedUpdateDir() {
    if (window.__aqm_rtl_debounce_timer) clearTimeout(window.__aqm_rtl_debounce_timer);
    window.__aqm_rtl_debounce_timer = setTimeout(() => {
      window.__aqm_rtl_debounce_timer = null;
      updateDir();
    }, 120);
  }

  function updateDir(root = document) {
    if (!rtlConfig.isRTL) return;
    const base = (root && root.querySelectorAll) ? root : document;
    const chatSelector = '.prose, .markdown, .markdown-body, .leading-relaxed, [data-testid="chat-message"], [class*="thinking"], [class*="conversation"]';

    const editables = new Set();
    base.querySelectorAll('[contenteditable="true"] p, [data-lexical-editor="true"] p, [contenteditable="true"], textarea, input[type="text"], input:not([type])').forEach(el => editables.add(el));
    if (base !== document && base.matches && base.matches('[contenteditable="true"], [contenteditable="true"] p, [data-lexical-editor="true"] p, textarea, input[type="text"], input:not([type])')) {
      editables.add(base);
    }
    editables.forEach(el => {
      if (isRtlProtectedElement(el)) return;
      if (el.hasAttribute('contenteditable') && el.querySelector('p')) return;
      const text = (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') ? (el.value || '') : (el.textContent || '');
      applyDirAttr(el, text);
    });

    const blockSel = 'p, li, ul, ol, blockquote, h1, h2, h3, h4, h5, h6, table, td, th';
    const blocks = [];
    if (base !== document && base.matches && base.matches(blockSel)) blocks.push(base);
    base.querySelectorAll(blockSel).forEach(el => blocks.push(el));
    for (const el of blocks) {
      if (isRtlProtectedElement(el)) continue;
      if (!el.closest(chatSelector)) continue;
      if (el.tagName === 'P' && el.closest('[contenteditable="true"], [data-lexical-editor="true"]')) continue;
      applyDirAttr(el, getElementTextExcludingCode(el));
    }
  }

  function clearDir() {
    document.querySelectorAll('[data-aqm-dir="1"]').forEach(el => {
      if (!isRtlProtectedElement(el)) {
        el.removeAttribute('dir');
        el.removeAttribute('data-aqm-dir');
      }
    });
  }

  function syncRtlObserver() {
    if (window.__aqm_rtl_observer) {
      window.__aqm_rtl_observer.disconnect();
      window.__aqm_rtl_observer = null;
    }
    if (!rtlConfig.isRTL || !document.body || typeof MutationObserver === 'undefined') return;
    window.__aqm_rtl_observer = new MutationObserver((mutations) => {
      if (!rtlConfig.isRTL) return;
      const hasExternal = mutations.some(m => {
        const node = m.target && m.target.nodeType === 3 ? m.target.parentElement : m.target;
        return node && !isRtlProtectedElement(node);
      });
      if (hasExternal) debouncedUpdateDir();
    });
    window.__aqm_rtl_observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  function syncRtlRuntime() {
    applyRtlStyles();
    syncRtlObserver();
    if (rtlConfig.isRTL) updateDir(); else clearDir();
  }

  if (!window.__aqm_rtl_listener_bound) {
    window.__aqm_rtl_listener_bound = true;
    onGlobal(document.body || document, 'input', debouncedUpdateDir, { capture: true, passive: true });

    onGlobal(document, 'keydown', (e) => {
      if (e.altKey && e.code === 'KeyR') {
        e.preventDefault();
        rtlConfig.isRTL = !rtlConfig.isRTL;
        saveRtlConfig();
        syncRtlRuntime();
        if (typeof renderPopover === 'function') renderPopover();
        return;
      }
      if (
        rtlConfig.fixAtSign &&
        !e.ctrlKey &&
        !e.metaKey &&
        !e.altKey &&
        e.code === 'Digit2' &&
        e.shiftKey &&
        (e.key === '٬' || e.key === '،' || e.key === '²')
      ) {
        const rawTarget = e.target;
        const targetEl = (rawTarget && rawTarget.nodeType === 3 ? rawTarget.parentElement : rawTarget) || document.activeElement;
        const editableHost = targetEl && targetEl.closest ? targetEl.closest('[contenteditable="true"], [data-lexical-editor="true"], textarea, input') : null;
        if (!editableHost) return;
        e.preventDefault();
        if (editableHost.tagName === 'TEXTAREA' || editableHost.tagName === 'INPUT') {
          try {
            const start = editableHost.selectionStart ?? editableHost.value.length;
            const end = editableHost.selectionEnd ?? editableHost.value.length;
            if (typeof editableHost.setRangeText === 'function') {
              editableHost.setRangeText('@', start, end, 'end');
            } else {
              editableHost.value = editableHost.value.slice(0, start) + '@' + editableHost.value.slice(end);
            }
          } catch (err) {
            editableHost.value = (editableHost.value || '') + '@';
          }
          editableHost.dispatchEvent(new Event('input', { bubbles: true }));
        } else {
          const prevText = editableHost.textContent || '';
          const sel = window.getSelection();
          const prevNode = sel && sel.rangeCount ? sel.anchorNode : null;
          const prevOffset = sel && sel.rangeCount ? sel.anchorOffset : -1;
          try {
            editableHost.dispatchEvent(new InputEvent('beforeinput', {
              bubbles: true,
              cancelable: true,
              inputType: 'insertText',
              data: '@'
            }));
          } catch (err) {}
          const curText = editableHost.textContent || '';
          const curNode = sel && sel.rangeCount ? sel.anchorNode : null;
          const curOffset = sel && sel.rangeCount ? sel.anchorOffset : -1;
          if (curText === prevText && curNode === prevNode && curOffset === prevOffset) {
            document.execCommand('insertText', false, '@');
          }
        }
      }
    }, { capture: true });
  }
