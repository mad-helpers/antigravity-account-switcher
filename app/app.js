/* ==========================================================================
   Antigravity Switcher & Migration Suite - Control Center Controller
   Author: mad-helpers (https://github.com/mad-helpers/antigravity-account-switcher)
   ========================================================================== */

let currentLang = 'en';
let toastTimer = null;

const CANONICAL_POOLS = [
  { name: 'Gemini 4 Hydrogen', match: /hydrogen|flash-worker/i },
  { name: 'Gemini 4 Argon', match: /argon/i },
  { name: 'Gemini 4 Carbon & Orchestrator', match: /carbon|orchestrator|3\.1 pro/i },
  { name: 'Gemini 3.8 Flash', match: /flash/i },
  { name: 'Claude 4.6 (Opus & Sonnet)', match: /claude|sonnet|opus/i },
  { name: 'GPT-OSS 120B', match: /gpt|oss/i }
];

let state = {
  activeAccount: null,
  authState: null,
  cdpConnected: false,
  cdpTargets: [],
  savedAccounts: {},
  conversations: [],
  projects: [],
  tasks: [],
  runningInstances: [],
  runningAccounts: {},
  isFallback: false,
  activeModalTab: 'projects',
  migration: {
    sourceAccount: null,
    targetAccount: null,
    mode: 'copy',
    structure: 'separate',
    dualSync: false,
    selectedIds: new Set(),
    selectedProjectId: ''
  }
};

function escHtml(v) {
  return String(v ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[c]));
}

function getAccountNeedsAuth(acc) {
  return Boolean(acc && (acc.needs_reauth || acc.has_token === false));
}

async function postJson(url, bodyObj = {}) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(bodyObj || {})
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok && data && typeof data === 'object' && !data.error) {
    return { success: false, error: `HTTP ${res.status}` };
  }
  return data;
}

function showAppToast(msg, isError = false) {
  const el = document.getElementById('appToast');
  if (!el) return;
  el.textContent = String(msg || '');
  el.className = `app-toast show${isError ? ' error' : ''}`;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.classList.remove('show');
  }, 4200);
}

document.addEventListener('DOMContentLoaded', () => {
  detectInitialLanguage();
  initApplication();
  startCountdownTicker();
  setInterval(() => {
    if (!document.hidden) initApplication(true);
  }, 15000);
});

function detectInitialLanguage() {
  const saved = localStorage.getItem('antigravity:switcher_lang') || localStorage.getItem('agy_switcher_lang');
  if (saved && translations[saved]) {
    currentLang = saved;
  } else {
    currentLang = 'en';
  }
  const langSelect = document.getElementById('langSelect');
  if (langSelect) langSelect.value = currentLang;
  applyTranslations();
}

function toggleQuickFaEn() {
  const next = currentLang === 'fa' ? 'en' : 'fa';
  changeLanguage(next);
}

function changeLanguage(lang) {
  if (!translations[lang]) return;
  currentLang = lang;
  try {
    localStorage.setItem('antigravity:switcher_lang', lang);
    localStorage.setItem('agy_switcher_lang', lang);
  } catch (e) {}
  const langSelect = document.getElementById('langSelect');
  if (langSelect) langSelect.value = lang;
  if (lang === 'fa' || lang === 'en') {
    postJson('/api/settings', { lang }).catch(() => {});
  }
  applyTranslations();
  renderAll();
  if (document.getElementById('migrationModal')?.classList.contains('active')) {
    renderProjectList();
    renderTaskList();
    renderConversationPicker();
  }
}

function applyTranslations() {
  const tObj = translations[currentLang] || translations.en;
  document.documentElement.lang = currentLang;
  document.documentElement.dir = tObj.dir;
  document.body.style.fontFamily = tObj.font;

  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (tObj[key]) el.innerText = tObj[key];
  });

  const quickBtn = document.getElementById('langQuickToggle');
  if (quickBtn) {
    quickBtn.textContent = currentLang === 'fa' ? 'EN' : 'فا';
  }

  const searchInput = document.getElementById('convSearchInput');
  if (searchInput && tObj.searchPlaceholder) searchInput.placeholder = tObj.searchPlaceholder;
  const tokenInput = document.getElementById('manualTokenInput');
  if (tokenInput && tObj.tokenPlaceholder) tokenInput.placeholder = tObj.tokenPlaceholder;
}

function t(key) {
  return (translations[currentLang] && translations[currentLang][key]) || (translations.en && translations.en[key]) || key;
}

async function initApplication(silent = false) {
  try {
    if (window.INITIAL_PAYLOAD && !silent) {
      handlePayload(window.INITIAL_PAYLOAD, false);
      return;
    }
    const res = await fetch('/api/state').then(r => (r.ok ? r.json() : null)).catch(() => null);
    if (res && (res.activeAccount || res.savedAccounts)) {
      handlePayload(res, false);
      return;
    }
    if (!silent) loadFallbackData();
  } catch (err) {
    if (!silent) loadFallbackData();
  }
}

function handlePayload(data, isFallback = false) {
  state.activeAccount = data.activeAccount || null;
  state.authState = data.authState || null;
  state.cdpConnected = Boolean(data.cdpConnected);
  state.cdpTargets = Array.isArray(data.cdpTargets) ? data.cdpTargets : [];
  state.savedAccounts = data.savedAccounts || {};
  state.conversations = Array.isArray(data.conversations) ? data.conversations : state.conversations;
  state.projects = Array.isArray(data.projects) ? data.projects : state.projects;
  state.tasks = Array.isArray(data.tasks) ? data.tasks : state.tasks;
  state.runningInstances = data.runningInstances || [];
  state.runningAccounts = data.runningAccounts || {};
  state.isFallback = isFallback;
  renderAll();
}

function getSecondaryAccountEmail() {
  const keys = Object.keys(state.savedAccounts || {});
  const activeEmail = state.activeAccount ? state.activeAccount.email : null;
  const secondary = keys.find(k => k !== activeEmail);
  return secondary || keys[0] || '';
}

function getPrimaryAccountEmail() {
  const keys = Object.keys(state.savedAccounts || {});
  return (state.activeAccount && state.activeAccount.email) || keys[0] || '';
}

function isAccount2(accountStr) {
  if (!accountStr) return false;
  const lower = String(accountStr).toLowerCase();
  const secondary = getSecondaryAccountEmail().toLowerCase();
  return lower.includes('instance2') || lower.includes('instance_2') || (secondary && lower === secondary) ||
    (state.activeAccount && state.activeAccount.instanceId === 'instance_2');
}

function loadFallbackData() {
  handlePayload({
    activeAccount: {
      email: "developer@example.com",
      name: "Developer",
      avatar: "",
      tier: "Google AI Pro",
      tier_code: "pro",
      session: {
        name: "Gemini 3.8 Flash",
        used_pct: 12.0,
        remaining_pct: 88.0,
        resets_in: "4 hr 12 min",
        reset_secs: 15120,
        reset_iso: new Date(Date.now() + 252 * 60 * 1000).toISOString()
      },
      weekly: {
        remaining_pct: 94.0,
        used_pct: 6.0,
        resets_in: "5d"
      },
      pools: [
        { name: "Gemini 4 Hydrogen", used_pct: 10.0, remaining_pct: 90.0, weekly_rem: 95.0, resets_in: "4 hr 12 min" },
        { name: "Gemini 4 Argon", used_pct: 12.0, remaining_pct: 88.0, weekly_rem: 94.0, resets_in: "4 hr 12 min" },
        { name: "Gemini 4 Carbon & Orchestrator", used_pct: 8.0, remaining_pct: 92.0, weekly_rem: 96.0, resets_in: "4 hr 12 min" },
        { name: "Gemini 3.8 Flash", used_pct: 12.0, remaining_pct: 88.0, weekly_rem: 94.0, resets_in: "4 hr 12 min" },
        { name: "Claude 4.6 (Opus & Sonnet)", used_pct: 0.0, remaining_pct: 100.0, weekly_rem: 100.0, resets_in: "4 hr 59 min" },
        { name: "GPT-OSS 120B", used_pct: 0.0, remaining_pct: 100.0, weekly_rem: 100.0, resets_in: "4 hr 59 min" }
      ]
    },
    savedAccounts: {},
    projects: [],
    tasks: [],
    conversations: [],
    cdpConnected: false
  }, true);
}

function hasWebViewBridge() {
  return Boolean(
    (window.chrome && window.chrome.webview) ||
    (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.nativeBridge)
  );
}

function callNative(action, payload = {}) {
  const req = { action, payload, timestamp: Date.now() };
  if (window.chrome && window.chrome.webview) {
    window.chrome.webview.postMessage(req);
    return Promise.resolve({ handledByWebview: true });
  }
  if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.nativeBridge) {
    window.webkit.messageHandlers.nativeBridge.postMessage(req);
    return Promise.resolve({ handledByWebview: true });
  }
  return postJson('/api/' + action, payload);
}

function normalizePools(rawPools, sessRem, sessUsed, sessReset) {
  const list = Array.isArray(rawPools) ? rawPools : [];
  return CANONICAL_POOLS.map(slot => {
    const found = list.find(p => slot.match.test(String(p?.name || '')));
    const rem = found && found.remaining_pct !== undefined
      ? Number(found.remaining_pct)
      : (found && found.used_pct !== undefined ? 100 - Number(found.used_pct) : Number(sessRem ?? 100));
    const used = found && found.used_pct !== undefined ? Number(found.used_pct) : Math.max(0, 100 - rem);
    return {
      name: slot.name,
      used_pct: Math.round(used * 10) / 10,
      remaining_pct: Math.round(rem * 10) / 10,
      resets_in: found?.resets_in || sessReset || 'Ready'
    };
  });
}

function renderAll() {
  renderCdpStatusBanner();
  renderSessionMismatchBanner();
  renderActiveAccount();
  renderDualInstanceControls();
  renderSavedAccounts();
}

function renderCdpStatusBanner() {
  const el = document.getElementById('cdpStatusBanner');
  if (!el) return;
  if (state.isFallback) {
    el.style.display = 'flex';
    el.className = 'status-banner warn';
    el.innerHTML = `<span>⚠️ ${escHtml(t('demoModeNotice'))}</span>`;
    return;
  }
  const isLive = Boolean(
    state.cdpConnected ||
    (Array.isArray(state.cdpTargets) && state.cdpTargets.length > 0) ||
    (Array.isArray(state.runningInstances) && state.runningInstances.length > 0)
  );
  el.style.display = 'flex';
  if (isLive) {
    el.className = 'status-banner ok';
    el.innerHTML = `<span>🟢 ${escHtml(t('cdpLive'))}</span>`;
  } else {
    el.className = 'status-banner warn';
    el.innerHTML = `
      <span>⚠️ ${escHtml(t('cdpInactive'))}</span>
      <button type="button" class="btn btn-warn" style="min-height:30px;padding:5px 11px;font-size:11.5px;" onclick="restartAntigravityFromApp()">
        <span>⚡️</span>
        <span>${escHtml(t('cdpEnableBtn'))}</span>
      </button>
    `;
  }
}

function renderSessionMismatchBanner() {
  const bannerEl = document.getElementById('sessionMismatchBanner');
  if (!bannerEl) return;
  const acc = state.activeAccount || {};
  const auth = state.authState || {};
  const isPrimaryWindow = !acc.instanceId || acc.instanceId === 'instance_1';
  const isMismatch = isPrimaryWindow && (
    auth.session_mismatch === true || (auth.session_mismatch !== false && acc.session_mismatch === true)
  );
  if (!isMismatch) {
    bannerEl.style.display = 'none';
    bannerEl.innerHTML = '';
    return;
  }
  const credEmail = auth.credential_email || acc.credential_email || acc.email || '';
  const liveEmail = auth.live_ide_email || acc.live_ide_email || '';
  const msgHtml = currentLang === 'fa'
    ? `⚠️ ناهماهنگی نشست: کلید سیستم روی <code class="ltr mono">${escHtml(credEmail)}</code> است ولی نشست فعال IDE هنوز روی <code class="ltr mono">${escHtml(liveEmail)}</code> است.`
    : `⚠️ Session mismatch: OS Credential Manager is on <code class="ltr mono">${escHtml(credEmail)}</code> while the running IDE session is still on <code class="ltr mono">${escHtml(liveEmail)}</code>.`;
  bannerEl.style.display = 'flex';
  bannerEl.className = 'status-banner danger';
  bannerEl.innerHTML = `
    <div>${msgHtml}</div>
    <div class="session-mismatch-actions">
      <button type="button" class="btn btn-glass" style="min-height:30px;padding:5px 10px;font-size:11.5px;" onclick="restartAntigravityFromApp()">
        <span>🔄</span>
        <span>${escHtml(t('restartToApply'))}</span>
      </button>
      <button type="button" class="btn btn-glass" style="min-height:30px;padding:5px 10px;font-size:11.5px;" onclick="executeLaunchDual('${escHtml(credEmail)}')">
        <span>🪟</span>
        <span>${escHtml(t('openSeparateWindow'))}</span>
      </button>
    </div>
  `;
}

function renderDualInstanceControls() {
  const select = document.getElementById('dualTargetAccountSelect');
  if (!select) return;
  select.innerHTML = '';
  const activeEmail = (state.activeAccount && state.activeAccount.email) || '';
  const entries = Object.entries(state.savedAccounts || {});
  const secondaries = entries.filter(([k, acc]) => (acc.email || k) !== activeEmail);
  const btn = document.getElementById('launchDualBtn');

  if (secondaries.length === 0) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.innerText = t('noSavedAccounts');
    select.appendChild(opt);
    if (btn) btn.disabled = true;
    return;
  }
  if (btn) btn.disabled = false;
  secondaries.forEach(([k, acc]) => {
    const opt = document.createElement('option');
    opt.value = k;
    opt.innerText = `${acc.label || acc.email || k} (${acc.tier || 'PRO'})`;
    select.appendChild(opt);
  });
}

async function executeLaunchDual(accountKey) {
  let target = accountKey;
  if (!target) {
    const select = document.getElementById('dualTargetAccountSelect');
    target = select ? select.value : '';
  }
  if (!target) {
    showAppToast(t('noSavedAccounts'), true);
    return;
  }
  const btn = document.getElementById('launchDualBtn');
  const originalText = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳</span> <span>${escHtml(t('dualLaunching'))}</span>`;
  }
  try {
    const res = await postJson('/api/launch_dual', { accountKey: target });
    if (res && res.needs_reauth) {
      showAppToast(res.error || t('needsAuth'), true);
      await signInWithGoogle(target);
      return;
    }
    if (res && res.success) {
      showAppToast(res.msg || t('dualLaunched'));
      await initApplication(true);
    } else {
      showAppToast((res && res.error) || 'Failed to launch secondary instance', true);
    }
  } catch (e) {
    showAppToast('Failed to connect to launcher service', true);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  }
}

function renderActiveAccount() {
  const acc = state.activeAccount;
  if (!acc) {
    document.getElementById('userName').innerText = t('noSavedAccounts');
    document.getElementById('userEmail').innerText = '';
    return;
  }

  document.getElementById('userName').innerText = acc.name || (acc.email ? acc.email.split('@')[0] : 'Account');
  document.getElementById('userEmail').innerText = acc.email || '';

  const avatarImg = document.getElementById('userAvatar');
  const avatarPlaceholder = document.getElementById('userAvatarPlaceholder');
  if (acc.avatar) {
    avatarImg.src = acc.avatar;
    avatarImg.style.display = 'block';
    avatarPlaceholder.style.display = 'none';
  } else {
    avatarImg.style.display = 'none';
    avatarPlaceholder.style.display = 'flex';
    avatarPlaceholder.innerText = ((acc.email && acc.email[0]) || 'A').toUpperCase();
  }

  const tierEl = document.getElementById('tierBadge');
  const tierCode = (acc.tier_code || 'pro').toLowerCase();
  tierEl.className = `tier-badge ${tierCode}`;
  tierEl.innerText = acc.tier || t('tierPro');

  const sess = acc.session || {};
  const used = Math.round((sess.used_pct ?? 0) * 10) / 10;
  const rem = Math.round((sess.remaining_pct !== undefined ? sess.remaining_pct : (100 - used)) * 10) / 10;

  const fillEl = document.getElementById('quotaProgressFill');
  fillEl.style.width = Math.min(100, Math.max(0, rem)) + '%';
  fillEl.className = 'liquid-progress-fill';
  if (rem <= 15) fillEl.classList.add('critical');
  else if (rem <= 35) fillEl.classList.add('warning');

  document.getElementById('quotaUsedText').innerText = `${used}% ${t('used')}`;
  document.getElementById('quotaRemainingText').innerText = `${rem}% ${t('remaining')}`;

  const countdownText = sess.resets_in && sess.resets_in !== 'N/A'
    ? `⏱ ${t('resetsIn')} ${sess.resets_in}`
    : t('noActiveLimit');
  document.getElementById('quotaCountdown').innerText = countdownText;

  const weekly = acc.weekly || {};
  const wkRem = Math.round((weekly.remaining_pct ?? acc.weekly_remaining_pct ?? 100) * 10) / 10;
  const wkReset = weekly.resets_in || acc.weekly_resets_in || '';
  const wkTextEl = document.getElementById('weeklySummaryText');
  const wkFillEl = document.getElementById('weeklyProgressFill');
  if (wkTextEl) wkTextEl.innerText = `${wkRem}% ${t('remaining')}${wkReset ? ` (${wkReset})` : ''}`;
  if (wkFillEl) wkFillEl.style.width = Math.min(100, Math.max(0, wkRem)) + '%';

  const grid = document.getElementById('modelsGrid');
  grid.innerHTML = '';
  const pools = normalizePools(acc.pools, rem, used, sess.resets_in);
  pools.forEach(p => {
    const chip = document.createElement('div');
    chip.className = 'model-chip';
    chip.innerHTML = `
      <div class="model-chip-top">
        <span class="model-chip-name ltr" title="${escHtml(p.name)}">${escHtml(p.name)}</span>
        <span class="model-chip-reset ltr mono">${escHtml(p.resets_in)}</span>
      </div>
      <div class="model-bar">
        <div class="model-bar-fill" style="width: ${Math.min(100, Math.max(0, p.remaining_pct))}%;"></div>
      </div>
      <div class="model-chip-status mono">
        <span style="color:var(--text-muted);">${p.used_pct}% ${escHtml(t('used'))}</span>
        <span style="color:var(--accent-cyan); font-weight:700;">${p.remaining_pct}% ${escHtml(t('remaining'))}</span>
      </div>
    `;
    grid.appendChild(chip);
  });
}

function renderSavedAccounts() {
  const container = document.getElementById('savedAccountsList');
  container.innerHTML = '';
  const accounts = Object.entries(state.savedAccounts || {});
  document.getElementById('accountsCountBadge').innerText = accounts.length;

  if (accounts.length === 0) {
    container.innerHTML = `
      <div class="liquid-card" style="text-align:center; padding: 24px; color:var(--text-muted); font-size:13px;">
        ${escHtml(t('noSavedAccounts'))}
      </div>
    `;
    return;
  }

  const runningAccs = Object.values(state.runningAccounts || {}).map(x => String(x || '').toLowerCase());
  const activeEmail = String((state.activeAccount && state.activeAccount.email) || '').toLowerCase();

  accounts.forEach(([key, acc]) => {
    const emailStr = acc.email || key;
    const isActive = activeEmail && emailStr.toLowerCase() === activeEmail;
    const needsAuth = getAccountNeedsAuth(acc);
    const isRunning = runningAccs.includes(key.toLowerCase()) || runningAccs.includes(emailStr.toLowerCase());

    const card = document.createElement('div');
    card.className = 'account-item-card';

    const tierCode = (acc.tier_code || 'pro').toLowerCase();
    const remPct = acc.remaining_pct !== undefined ? `${Math.round(acc.remaining_pct)}%` : '100%';
    const wkPct = acc.weekly_remaining_pct !== undefined ? ` • W: ${Math.round(acc.weekly_remaining_pct)}%` : '';

    card.innerHTML = `
      <div class="account-info">
        <div class="account-avatar-small">${escHtml((emailStr[0] || 'G').toUpperCase())}</div>
        <div class="account-labels">
          <h4>
            <span>${escHtml(acc.label || acc.name || emailStr)}</span>
            <span class="tier-badge ${escHtml(tierCode)}" style="font-size:9.5px; padding:1px 7px;">${escHtml(acc.tier || 'PRO')}</span>
            ${isActive ? `<span class="tier-badge pro" style="font-size:9.5px; padding:1px 7px;">● ${escHtml(t('activeBadge'))}</span>` : ''}
            ${needsAuth ? `<span class="badge-tag badge-isolated">${escHtml(t('needsAuth'))}</span>` : ''}
          </h4>
          <p class="ltr mono">${escHtml(emailStr)} • <span style="color:var(--accent-cyan); font-weight:600;">${escHtml(remPct)} ${escHtml(t('remaining'))}${escHtml(wkPct)}</span></p>
        </div>
      </div>

      <div class="account-actions">
        ${!isActive ? (needsAuth ? `
          <button type="button" class="btn btn-warn" style="min-height:32px; padding:6px 11px; font-size:12px;" onclick="signInWithGoogle('${escHtml(key)}')">
            <span>🔑</span>
            <span>${escHtml(t('signInGoogle'))}</span>
          </button>
        ` : `
          <button type="button" class="btn btn-primary" style="min-height:32px; padding:6px 11px; font-size:12px;" onclick="switchToAccount('${escHtml(key)}', false)">
            <span>⚡️</span>
            <span>${escHtml(t('switchNow'))}</span>
          </button>
          <button type="button" class="btn btn-glass" style="min-height:32px; padding:6px 10px; font-size:12px;" onclick="switchToAccount('${escHtml(key)}', true)" title="${escHtml(t('switchRestartBtn'))}">
            <span>🔄</span>
          </button>
          <button type="button" class="btn btn-glass" style="min-height:32px; padding:6px 10px; font-size:12px;" title="${escHtml(isRunning ? t('focusWindow') : t('launchDualBtn'))}" onclick="executeLaunchDual('${escHtml(key)}')">
            <span>🪟</span>
          </button>
        `) : ''}
        <button type="button" class="btn btn-ghost-danger" style="min-height:32px; padding:6px 9px; font-size:12px;" title="Delete" onclick="deleteAccount('${escHtml(key)}')">
          <span>🗑</span>
        </button>
      </div>
    `;
    container.appendChild(card);
  });
}

function toggleAddAccountDrawer(forceState = null) {
  const drawer = document.getElementById('addAccountDrawer');
  if (!drawer) return;
  const open = (forceState !== null) ? Boolean(forceState) : !drawer.classList.contains('open');
  drawer.classList.toggle('open', open);
}

function toggleTokenInputBox() {
  const box = document.getElementById('manualTokenBox');
  if (!box) return;
  box.style.display = (box.style.display === 'none' || !box.style.display) ? 'flex' : 'none';
}

async function startOAuthSignIn() {
  await signInWithGoogle(null);
}

async function signInWithGoogle(accountKey = null) {
  try {
    const payload = accountKey ? { accountKey, noRestart: true } : { noRestart: true };
    const res = await postJson('/api/oauth_signin', payload);
    if (res && res.auth_url) {
      const box = document.getElementById('oauthDirectLinkBox');
      if (box) {
        box.style.display = 'block';
        box.innerHTML = `<a href="${escHtml(res.auth_url)}" target="_blank" rel="noreferrer" style="color:var(--accent-cyan); font-weight:700; text-decoration:underline;">🔗 ${escHtml(t('signInGoogle'))}</a>`;
      }
      try { window.open(res.auth_url, '_blank'); } catch (e) {}
      showAppToast(t('oauthOpened'));
    } else {
      showAppToast((res && res.error) || 'OAuth unavailable', true);
    }
  } catch (e) {
    showAppToast('Failed to start OAuth sign-in', true);
  }
}

async function submitManualToken() {
  const input = document.getElementById('manualTokenInput');
  const tok = input ? input.value.trim() : '';
  if (!tok) {
    showAppToast(t('tokenPlaceholder'), true);
    return;
  }
  try {
    const res = await postJson('/api/import', { token: tok });
    if (res && res.success) {
      if (input) input.value = '';
      toggleAddAccountDrawer(false);
      showAppToast(t('tokenImported'));
      await initApplication();
    } else {
      showAppToast((res && res.error) || 'Invalid token', true);
    }
  } catch (e) {
    showAppToast('Failed to import token', true);
  }
}

async function restartAntigravityFromApp() {
  try {
    const res = await postJson('/api/restart', {});
    if (res && res.success) {
      showAppToast(res.msg || t('restartNotice'));
    } else {
      showAppToast((res && res.error) || 'Failed to restart Antigravity', true);
    }
  } catch (e) {
    showAppToast('Failed to connect to launcher service', true);
  }
}

async function switchToAccount(key, restartApp = false) {
  if (hasWebViewBridge()) {
    await callNative('switch', { accountKey: key, noRestart: !restartApp });
    showAppToast(`${t('switching')} ${key}`);
    return;
  }
  try {
    const res = await postJson('/api/switch', { accountKey: key, noRestart: !restartApp });
    if (res && res.needs_reauth) {
      showAppToast(res.error || t('needsAuth'), true);
      return;
    }
    if (res && res.success) {
      await initApplication();
      const auth = res.authState || res.auth_state || state.authState || {};
      const msg = `${t('switchDone')} ${key}${auth.session_mismatch ? ` — ${t('restartNotice')}` : ''}`;
      showAppToast(msg);
    } else {
      showAppToast((res && res.error) || t('switchFailed'), true);
    }
  } catch (e) {
    showAppToast(t('switchFailed'), true);
  }
}

async function saveCurrentAccount() {
  if (hasWebViewBridge()) {
    await callNative('save', {});
    showAppToast(t('accountSaved'));
    return;
  }
  try {
    const res = await postJson('/api/save', {});
    if (res && res.success) {
      await initApplication();
      showAppToast(t('accountSaved'));
    } else {
      showAppToast((res && res.error) || t('saveFailed'), true);
    }
  } catch (e) {
    showAppToast(t('saveFailed'), true);
  }
}

async function logoutAndAddNew() {
  toggleAddAccountDrawer(true);
}

async function refreshLiveData() {
  if (hasWebViewBridge()) await callNative('refresh', {});
  await initApplication();
}

async function deleteAccount(key) {
  if (!confirm(t('deleteConfirm'))) return;
  if (hasWebViewBridge()) {
    await callNative('delete', { accountKey: key });
    delete state.savedAccounts[key];
    renderAll();
    return;
  }
  try {
    const res = await postJson('/api/delete', { accountKey: key });
    if (res && res.success) {
      delete state.savedAccounts[key];
      showAppToast(t('accountDeleted'));
      await initApplication();
    } else {
      showAppToast((res && res.error) || t('deleteFailed'), true);
    }
  } catch (e) {
    showAppToast(t('deleteFailed'), true);
  }
}

// ==============================================================================
// MODAL & MIGRATION HUB LOGIC
// ==============================================================================

async function openMigrationModal(sourceAccountKey) {
  state.migration.sourceAccount = sourceAccountKey || (state.activeAccount ? state.activeAccount.email : null);
  const targetSelect = document.getElementById('modalTargetAccountSelect');
  if (targetSelect) {
    targetSelect.innerHTML = '';
    Object.keys(state.savedAccounts).forEach(key => {
      if (key !== state.migration.sourceAccount) {
        const opt = document.createElement('option');
        opt.value = key;
        opt.innerText = key;
        targetSelect.appendChild(opt);
      }
    });
    if (targetSelect.options.length === 0) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.innerText = t('noSavedAccounts');
      targetSelect.appendChild(opt);
    }
  }

  await Promise.all([fetchProjectsList(), fetchTasksList(), fetchConversationsList()]);
  populateProjectFilterDropdown();
  switchModalTab(state.activeModalTab || 'projects');

  const modal = document.getElementById('migrationModal');
  if (modal) modal.classList.add('active');
}

function closeMigrationModal() {
  const modal = document.getElementById('migrationModal');
  if (modal) modal.classList.remove('active');
}

function switchModalTab(tabName) {
  state.activeModalTab = tabName;
  const btnProjects = document.getElementById('modalTabProjectsBtn');
  const btnTasks = document.getElementById('modalTabTasksBtn');
  const btnConvs = document.getElementById('modalTabConversationsBtn');
  if (btnProjects) btnProjects.className = `modal-tab-btn ${tabName === 'projects' ? 'active' : ''}`;
  if (btnTasks) btnTasks.className = `modal-tab-btn ${tabName === 'tasks' ? 'active' : ''}`;
  if (btnConvs) btnConvs.className = `modal-tab-btn ${tabName === 'conversations' ? 'active' : ''}`;

  const paneP = document.getElementById('paneProjects');
  const paneT = document.getElementById('paneTasks');
  const paneC = document.getElementById('paneConversations');
  const startBtn = document.getElementById('startMigrationBtn');
  if (paneP) paneP.style.display = (tabName === 'projects') ? 'flex' : 'none';
  if (paneT) paneT.style.display = (tabName === 'tasks') ? 'flex' : 'none';
  if (paneC) paneC.style.display = (tabName === 'conversations') ? 'flex' : 'none';
  if (startBtn) startBtn.style.display = (tabName === 'conversations') ? 'inline-flex' : 'none';

  if (tabName === 'projects') renderProjectList();
  else if (tabName === 'tasks') renderTaskList();
  else if (tabName === 'conversations') renderConversationPicker();
}

async function fetchProjectsList() {
  try {
    const res = await fetch('/api/projects').then(r => r.json()).catch(() => null);
    if (Array.isArray(res)) state.projects = res;
    else if (res && Array.isArray(res.projects)) state.projects = res.projects;
  } catch (e) {}
}

function renderProjectList() {
  const container = document.getElementById('projectCardList');
  if (!container) return;
  container.innerHTML = '';
  if (!state.projects || state.projects.length === 0) {
    container.innerHTML = `<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:12px;">No projects found</div>`;
    return;
  }
  const savedKeys = Object.keys(state.savedAccounts || {});

  state.projects.forEach(p => {
    const card = document.createElement('div');
    card.className = 'project-item-card';
    const isShared = p.is_shared;
    const isInst2 = p.is_instance2_enabled;
    const badgeClass = isShared ? 'badge-shared' : 'badge-account1';
    const badgeText = isShared ? t('sharedBadge') : (isInst2 ? t('account2OnlyBadge') : t('account1OnlyBadge'));

    const currentQuotaAcc = p.quota_account || (p.assigned_accounts && p.assigned_accounts[0]) || '';
    const quotaOptions = Array.from(new Set([...savedKeys, ...(currentQuotaAcc ? [currentQuotaAcc] : [])]));
    const optionsHtml = [
      `<option value="">${escHtml(t('defaultPayer'))}</option>`,
      ...quotaOptions.map(accKey => {
        const selected = currentQuotaAcc && accKey.toLowerCase() === currentQuotaAcc.toLowerCase() ? 'selected' : '';
        return `<option value="${escHtml(accKey)}" ${selected}>💳 ${escHtml(accKey)}</option>`;
      })
    ].join('');

    card.innerHTML = `
      <div class="project-info-main">
        <div class="project-title-row">
          <span class="project-title-text">${escHtml(p.name || p.id)}</span>
          <span class="badge-tag ${badgeClass}">${escHtml(badgeText)}</span>
          <span class="badge-tag" style="background:rgba(255,255,255,0.06);color:var(--text-muted);">💬 ${Number(p.conversation_count || 0)}</span>
        </div>
        <div class="project-path-text ltr" title="${escHtml(p.path)}">${escHtml(p.path || 'No folder path')}</div>
      </div>
      <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
        <select class="lang-select project-quota-select" aria-label="${escHtml(t('quotaPayer'))}" title="${escHtml(t('quotaPayer'))}" onchange="setProjectQuotaAccount('${escHtml(p.id)}', this.value)">
          ${optionsHtml}
        </select>
        <label class="ios-switch" title="${escHtml(t('assignToAccount2'))}">
          <input type="checkbox" ${isInst2 ? 'checked' : ''} onchange="toggleProjectAssignment('${escHtml(p.id)}', this.checked)" />
          <span class="ios-slider"></span>
        </label>
        <button type="button" class="btn btn-glass" style="min-height:30px; padding:4px 9px; font-size:11px;" onclick="syncProjectExplicit('${escHtml(p.id)}')" title="${escHtml(t('syncProjectNow'))}">
          <span>⇄ ${escHtml(t('syncProjectNow'))}</span>
        </button>
        <button type="button" class="btn btn-ghost-danger" style="min-height:30px; padding:4px 8px; font-size:11px;" onclick="unlinkProjectExplicit('${escHtml(p.id)}')" title="${escHtml(t('removeFromAccount2'))}">
          <span>✕</span>
        </button>
      </div>
    `;
    container.appendChild(card);
  });
}

async function setProjectQuotaAccount(projectId, account) {
  try {
    const res = await postJson('/api/project_set_quota_account', { projectId, account });
    if (res && res.success) {
      showAppToast(t('payerUpdated'));
      await Promise.all([fetchProjectsList(), initApplication(true)]);
      renderProjectList();
    } else {
      showAppToast((res && res.error) || 'Failed to update quota payer', true);
      await fetchProjectsList();
      renderProjectList();
    }
  } catch (e) {
    showAppToast('Failed to connect to server', true);
  }
}

async function unlinkProjectExplicit(projectId) {
  const targetAcc = getSecondaryAccountEmail();
  try {
    const res = await postJson('/api/project_unlink', { projectId, account: targetAcc });
    if (res && res.success) {
      await fetchProjectsList();
      renderProjectList();
    }
  } catch (e) {
    showAppToast('Failed to unlink project', true);
  }
}

async function toggleProjectAssignment(projectId, enableInInstance2) {
  const targetAcc = getSecondaryAccountEmail();
  try {
    if (enableInInstance2) {
      await postJson('/api/project_sync', { projectId, targetAccount: targetAcc, includeConversations: false });
    } else {
      await postJson('/api/project_unlink', { projectId, account: targetAcc });
    }
    await fetchProjectsList();
    renderProjectList();
  } catch (e) {
    showAppToast('Failed to update project profile assignment', true);
  }
}

async function syncProjectExplicit(projectId) {
  const targetAcc = getSecondaryAccountEmail();
  try {
    const res = await postJson('/api/project_sync', { projectId, targetAccount: targetAcc, includeConversations: true });
    if (res && res.success) {
      showAppToast(t('migrationSuccess'));
      await fetchProjectsList();
      renderProjectList();
    }
  } catch (e) {
    showAppToast('Error syncing project', true);
  }
}

function filterProjects(query) {
  const q = query.toLowerCase().trim();
  document.querySelectorAll('#projectCardList .project-item-card').forEach(card => {
    card.style.display = card.innerText.toLowerCase().includes(q) ? 'flex' : 'none';
  });
}

async function fetchTasksList() {
  try {
    const res = await fetch('/api/tasks').then(r => r.json()).catch(() => null);
    if (Array.isArray(res)) state.tasks = res;
    else if (res && Array.isArray(res.tasks)) state.tasks = res.tasks;
  } catch (e) {}
}

function renderTaskList() {
  const container = document.getElementById('taskCardList');
  if (!container) return;
  container.innerHTML = '';
  if (!state.tasks || state.tasks.length === 0) {
    container.innerHTML = `<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:12px;">No scheduled tasks found</div>`;
    return;
  }
  state.tasks.forEach(task => {
    const card = document.createElement('div');
    card.className = 'task-item-card';
    const isIsolated = task.isolated_from_account2;
    const isEnabled = task.enabled;
    const isAcc2 = isAccount2(state.activeAccount && state.activeAccount.email);
    const isOwnerAcc1 = !task.owner_account || !isAccount2(task.owner_account);
    const isLocked = isAcc2 && isIsolated && isOwnerAcc1;
    const isoBadgeClass = isLocked ? 'badge-disabled' : (isIsolated ? 'badge-isolated' : 'badge-shared');
    const isoBadgeText = isLocked ? t('taskLockedBadge') : (isIsolated ? t('taskIsolatedBadge') : t('taskSharedBadge'));

    card.innerHTML = `
      <div class="task-info-main">
        <div class="task-title-row">
          <span class="task-title-text">${escHtml(task.name)}</span>
          <span class="badge-tag ${isoBadgeClass}">${escHtml(isoBadgeText)}</span>
          <span class="badge-tag ${isEnabled ? 'badge-shared' : 'badge-disabled'}">${escHtml(isEnabled ? t('taskEnabled') : t('taskDisabled'))}</span>
        </div>
        <div class="task-desc-text">${escHtml(task.description || task.name)} • Next: ${escHtml(task.next_run || 'N/A')}</div>
      </div>
      <div style="display:flex; align-items:center; gap:8px;">
        <button type="button" class="btn btn-glass" ${isLocked ? 'disabled' : ''} style="min-height:30px; padding:4px 9px; font-size:11px;" onclick="toggleTaskIsolationExplicit('${escHtml(task.name)}', ${!isIsolated})">
          <span>${isIsolated ? '🛡 ' + escHtml(t('unisolateTaskBtn')) : '🔒 ' + escHtml(t('isolateTaskBtn'))}</span>
        </button>
        <label class="ios-switch" title="Toggle Task State">
          <input type="checkbox" ${isLocked ? 'disabled' : ''} ${isEnabled ? 'checked' : ''} onchange="toggleTaskActiveState('${escHtml(task.name)}', this.checked)" />
          <span class="ios-slider"></span>
        </label>
      </div>
    `;
    container.appendChild(card);
  });
}

async function toggleTaskIsolationExplicit(taskName, isolate) {
  try {
    const res = await postJson('/api/task_isolate', {
      taskName,
      ownerAccount: getPrimaryAccountEmail(),
      isolateFromAccount2: isolate,
      account: state.activeAccount ? state.activeAccount.email : getPrimaryAccountEmail()
    });
    if (res && res.success) {
      await fetchTasksList();
      renderTaskList();
    } else {
      showAppToast((res && res.error) || t('taskPermissionDenied'), true);
      await fetchTasksList();
      renderTaskList();
    }
  } catch (e) {
    showAppToast('Failed to update task isolation', true);
  }
}

async function toggleTaskActiveState(taskName, enable) {
  try {
    const res = await postJson('/api/task_toggle', {
      taskName,
      enable,
      account: state.activeAccount ? state.activeAccount.email : getPrimaryAccountEmail()
    });
    if (res && res.success) {
      showAppToast(t('taskToggleSuccess'));
      await fetchTasksList();
      renderTaskList();
    } else {
      showAppToast((res && res.error) || t('taskPermissionDenied'), true);
      await fetchTasksList();
      renderTaskList();
    }
  } catch (e) {
    showAppToast('Failed to toggle task state', true);
  }
}

async function fetchConversationsList() {
  try {
    const res = await fetch('/api/conversations').then(r => r.json()).catch(() => null);
    if (Array.isArray(res)) state.conversations = res;
    else if (res && Array.isArray(res.conversations)) state.conversations = res.conversations;
  } catch (err) {}
}

function populateProjectFilterDropdown() {
  const sel = document.getElementById('convProjectFilterSelect');
  if (!sel) return;
  sel.innerHTML = `<option value="" data-i18n="allProjects">${escHtml(t('allProjects'))}</option>`;
  const projectsSeen = new Map();
  state.conversations.forEach(c => {
    if (c.project_id && !projectsSeen.has(c.project_id)) {
      projectsSeen.set(c.project_id, c.project_name || c.project_id);
    }
  });
  projectsSeen.forEach((name, pid) => {
    const opt = document.createElement('option');
    opt.value = pid;
    opt.innerText = name;
    sel.appendChild(opt);
  });
}

function onFilterProjectChange(projectId) {
  state.migration.selectedProjectId = projectId;
  renderConversationPicker();
}

function renderConversationPicker() {
  const container = document.getElementById('conversationPickerList');
  if (!container) return;
  container.innerHTML = '';
  let filtered = state.conversations || [];
  if (state.migration.selectedProjectId) {
    filtered = filtered.filter(c => c.project_id === state.migration.selectedProjectId);
  }
  if (filtered.length === 0) {
    container.innerHTML = `<div style="padding:16px; text-align:center; color:var(--text-muted); font-size:12px;">No conversations match filter</div>`;
    return;
  }
  filtered.forEach(c => {
    const isChecked = state.migration.selectedIds.has(c.id);
    const item = document.createElement('label');
    item.className = 'conv-item';
    item.innerHTML = `
      <input type="checkbox" value="${escHtml(c.id)}" ${isChecked ? 'checked' : ''} onchange="toggleConversationSelection('${escHtml(c.id)}', this.checked)" />
      <div style="display:flex; flex-direction:column; flex:1; min-width:0;">
        <span class="conv-title">${escHtml(c.title || c.id)}</span>
        <span style="font-size:10.5px; color:var(--text-dim);">${escHtml(c.project_name || 'Outside of Project')}</span>
      </div>
      <span class="conv-date">${escHtml(c.size_kb || 0)} KB • ${escHtml(c.last_modified || '')}</span>
    `;
    container.appendChild(item);
  });
}

function toggleConversationSelection(id, checked) {
  if (checked) state.migration.selectedIds.add(id);
  else state.migration.selectedIds.delete(id);
}

function toggleSelectAllConversations(selectAll) {
  state.migration.selectedIds.clear();
  if (selectAll) {
    let list = state.conversations || [];
    if (state.migration.selectedProjectId) list = list.filter(c => c.project_id === state.migration.selectedProjectId);
    list.forEach(c => state.migration.selectedIds.add(c.id));
  }
  renderConversationPicker();
}

function filterConversations(query) {
  const q = query.toLowerCase().trim();
  document.querySelectorAll('#conversationPickerList .conv-item').forEach(item => {
    item.style.display = item.innerText.toLowerCase().includes(q) ? 'flex' : 'none';
  });
}

function selectMigrationMode(mode) {
  state.migration.mode = mode;
  document.getElementById('modeCopyCard').className = `radio-card ${mode === 'copy' ? 'selected' : ''}`;
  document.getElementById('modeCutCard').className = `radio-card ${mode === 'move' ? 'selected' : ''}`;
}

function selectStructureMode(struct) {
  state.migration.structure = struct;
  document.getElementById('structSeparateCard').className = `radio-card ${struct === 'separate' ? 'selected' : ''}`;
  document.getElementById('structMergeCard').className = `radio-card ${struct === 'merge' ? 'selected' : ''}`;
}

async function executeMigration() {
  const target = document.getElementById('modalTargetAccountSelect').value;
  if (!target) {
    showAppToast('Please select a target account.', true);
    return;
  }
  const selectedList = Array.from(state.migration.selectedIds);
  if (selectedList.length === 0) {
    showAppToast(t('selectConversations'), true);
    return;
  }
  const btn = document.getElementById('startMigrationBtn');
  btn.disabled = true;
  btn.innerText = t('migrating');
  const payload = {
    sourceAccount: state.migration.sourceAccount,
    targetAccount: target,
    conversationIds: selectedList,
    mode: state.migration.mode,
    structure: state.migration.structure,
    dualSync: document.getElementById('dualSyncCheckbox').checked,
    projectId: state.migration.selectedProjectId || null
  };
  try {
    const res = await callNative('migrate', payload);
    if (res && res.success === false) {
      showAppToast(res.error || 'Migration failed', true);
    } else {
      showAppToast(t('migrationSuccess'));
      closeMigrationModal();
    }
  } catch (e) {
    showAppToast('Migration failed', true);
  } finally {
    btn.disabled = false;
    btn.innerText = t('startMigration');
  }
}

function startCountdownTicker() {
  setInterval(() => {
    if (!state.activeAccount || !state.activeAccount.session) return;
    const sess = state.activeAccount.session;
    if (!sess.reset_iso) return;
    const el = document.getElementById('quotaCountdown');
    if (!el) return;
    const diff = Math.floor((new Date(sess.reset_iso).getTime() - Date.now()) / 1000);
    if (diff > 0) {
      const h = Math.floor(diff / 3600);
      const m = Math.floor((diff % 3600) / 60);
      const s = diff % 60;
      let str = '';
      if (h > 0) str += `${h}h `;
      str += `${m}m ${s}s`;
      el.innerText = `⏱ ${t('resetsIn')} ${str}`;
    } else {
      el.innerText = t('noActiveLimit');
    }
  }, 1000);
}
