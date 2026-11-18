  if (
    typeof location !== 'undefined' &&
    (
      !/^(https:\/\/(127\.0\.0\.1|localhost)(:\d+)?\/|vscode-file:\/\/)/.test(location.href) ||
      (location.pathname || '').startsWith('/sidecar') ||
      (typeof window !== 'undefined' && window.top !== window.self)
    )
  ) {
    return;
  }

  const runtimeRevision = '3.0.0';
  const runtimeSettings = JSON.stringify(window.__antigravity_user_settings || {});
  const runtimeAccount = window.__antigravity_account || '';
  // A routine quota refresh must preserve open panels, focus, and pending input.
  if (
    window.__aqm_runtime_revision === runtimeRevision &&
    window.__aqm_runtime_settings === runtimeSettings &&
    window.__aqm_runtime_account === runtimeAccount &&
    typeof window.__aqm_refresh_runtime === 'function' &&
    document.getElementById('antigravity-account-pill')
  ) {
    window.__aqm_refresh_runtime();
    return;
  }
  window.__aqm_runtime_revision = null;

  [
    'antigravity-usage-popover',
    'antigravity-switcher-modal',
    'antigravity-account-pill',
    'antigravity-usage-pill',
    'aqm-test-vazir',
    'antigravity-rtl-style',
    'rtl-widget-style',
    'aqm-switcher-styles'
  ].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.remove();
  });
  const oldRtlWidget = document.querySelector('.rtl-widget-container');
  if (oldRtlWidget) oldRtlWidget.remove();

  [
    '__aqm_dom_interval',
    '__aqm_task_interval',
    '__aqm_rtl_interval',
    '__aqm_iso_interval'
  ].forEach(key => {
    if (window[key]) {
      clearInterval(window[key]);
      window[key] = null;
    }
  });
  ['__aqm_rtl_debounce_timer', '__aqm_iso_timeout'].forEach(key => {
    if (window[key]) {
      clearTimeout(window[key]);
      window[key] = null;
    }
  });
  [
    '__aqm_token_observer',
    '__aqm_submenu_observer',
    '__aqm_dom_observer',
    '__aqm_rtl_observer',
    '__aqm_iso_observer'
  ].forEach(key => {
    if (window[key]) {
      window[key].disconnect();
      window[key] = null;
    }
  });

  if (Array.isArray(window.__aqm_timers)) {
    window.__aqm_timers.forEach(id => { clearInterval(id); clearTimeout(id); });
    window.__aqm_timers = [];
  }
  if (window.__aqm_global_events) {
    window.__aqm_global_events.abort();
  }
  window.__aqm_global_events = new AbortController();
  window.__aqm_rtl_listener_bound = false;
  window.__aqm_click_bound = false;

  function onGlobal(target, type, listener, options = {}) {
    if (!target || typeof target.addEventListener !== 'function') return;
    target.addEventListener(type, listener, { ...options, signal: window.__aqm_global_events.signal });
  }

  function safeAppendToHead(el) {
    try {
      const target = document.head || document.documentElement || document.body;
      if (target) {
        target.appendChild(el);
      } else {
        onGlobal(document, 'DOMContentLoaded', () => {
          (document.head || document.documentElement || document.body)?.appendChild(el);
        }, { once: true });
      }
    } catch (e) {}
  }

  function escHtml(v) {
    return String(v ?? '').replace(/[&<>"']/g, c => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    }[c]));
  }

  function isAccount2(email) {
    if (!email) return false;
    const norm = String(email).toLowerCase().trim();
    if (norm === 'instance_2' || norm === 'secondary_account' || norm.includes('account2')) return true;
    let primary = '';
    try {
      const manifest = JSON.parse(localStorage.getItem('antigravity:accounts_manifest') || '{}');
      primary = Object.keys(manifest)[0] || '';
    } catch (e) {}
    if (primary && norm === primary.toLowerCase().trim()) return false;
    return true;
  }

  function isInstance2Window() {
    if (window.__antigravity_instance && window.__antigravity_instance !== 'instance_1') return true;
    if (window.__antigravity_instance === 'instance_1') return false;
    try {
      const lsInst = localStorage.getItem('antigravity:instance_id');
      if (lsInst && lsInst !== 'instance_1') return true;
      if (lsInst === 'instance_1') return false;
      const acc = localStorage.getItem('antigravity:account_email');
      if (acc && (acc.toLowerCase().includes('instance2') || acc.toLowerCase().includes('instance3') || acc.startsWith('instance_'))) {
        return true;
      }
    } catch (e) {}
    if (window.__antigravity_accounts) {
      const aInst = window.__antigravity_accounts.instanceId || window.__antigravity_accounts.instance_id;
      if (aInst && aInst !== 'instance_1') return true;
      if (aInst === 'instance_1') return false;
    }
    return false;
  }

  const userSettings = (typeof window !== 'undefined' && window.__antigravity_user_settings) || {};
  let swLang = (userSettings && userSettings.lang) || '';
  if (!swLang) {
    try { swLang = localStorage.getItem('antigravity:switcher_lang') || ''; } catch (e) {}
  }
  if (swLang !== 'fa' && swLang !== 'en') swLang = 'fa';
