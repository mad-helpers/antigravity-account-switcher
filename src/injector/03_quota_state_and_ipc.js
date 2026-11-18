  let displayMode = userSettings.mode || 'remaining';
  if (!userSettings.mode) {
    try {
      const saved = localStorage.getItem('antigravity:quota_mode');
      if (saved === 'remaining' || saved === 'used') displayMode = saved;
    } catch (e) {}
  }

  let isPrivacyMode = (userSettings.privacyMode !== undefined) ? Boolean(userSettings.privacyMode) : false;
  if (userSettings.privacyMode === undefined) {
    try {
      const p = localStorage.getItem('antigravity:privacy_mode');
      if (p !== null) isPrivacyMode = (p !== 'false');
    } catch (e) {}
  }

  let activePopoverTab = 'quota';
  let isRefreshing = false;
  let isImportFormOpen = false;
  let stagedFontFile = null;

  let swAutoRestart = false;
  try {
    swAutoRestart = (localStorage.getItem('antigravity:auto_restart_on_switch') === 'true');
  } catch (e) {}
  let swTab = 'accounts';
  let swShowAddPanel = false;
  let swShowTokenInput = false;
  let swOAuthUrl = null;
  let swToastTimeout = null;

  function postJson(url, bodyObj = {}) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bodyObj || {})
    });
  }

  function callDaemonIpc(action, payload = {}) {
    if (typeof window.__aqm_daemon_ipc === 'function') {
      try {
        window.__aqm_daemon_ipc(JSON.stringify({ action, ...payload }));
        return true;
      } catch (e) {}
    }
    return false;
  }

  function persistUserSettings(patch) {
    if (!patch || typeof patch !== 'object') return;
    try {
      window.__antigravity_user_settings = Object.assign({}, window.__antigravity_user_settings || {}, patch);
    } catch (e) {}
    const instId = (typeof window !== 'undefined' && window.__antigravity_instance) || (isInstance2Window() ? 'instance_2' : 'instance_1');
    const accEmail = (typeof window !== 'undefined' && window.__antigravity_account) || null;
    const payload = Object.assign({}, patch, { instance_id: instId, account: accEmail });
    try { callDaemonIpc('save_user_settings', payload); } catch (e) {}
    try { postJson('http://127.0.0.1:39281/api/settings', payload).catch(() => {}); } catch (e) {}
  }

  function safeJsonStringify(obj) {
    try {
      return JSON.stringify(obj, (k, v) => typeof v === 'bigint' ? Number(v) : v);
    } catch (e) {
      return null;
    }
  }

  const SVGS = {
    gemini: `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" style="flex-shrink:0;">
        <path d="M12 0C12 6.627 6.627 12 0 12C6.627 12 12 17.373 12 24C12 17.373 17.373 12 24 12C17.373 12 12 6.627 12 0Z" fill="url(#aqmGeminiGrad)"/>
        <defs>
          <linearGradient id="aqmGeminiGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#4285F4"/>
            <stop offset="50%" stop-color="#9B72CB"/>
            <stop offset="100%" stop-color="#D96570"/>
          </linearGradient>
        </defs>
      </svg>
    `,
    hydrogen: `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" style="flex-shrink:0;">
        <circle cx="12" cy="12" r="9" stroke="url(#aqmHydrogenGrad)" stroke-width="1.8" opacity="0.85"/>
        <circle cx="12" cy="12" r="3.6" fill="url(#aqmHydrogenGrad)"/>
        <circle cx="18.2" cy="6.2" r="1.8" fill="#38bdf8"/>
        <defs>
          <linearGradient id="aqmHydrogenGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#22d3ee"/>
            <stop offset="100%" stop-color="#3b82f6"/>
          </linearGradient>
        </defs>
      </svg>
    `,
    argon: `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" style="flex-shrink:0;">
        <path d="M12 1L14.8 8.6L22 12L14.8 15.4L12 23L9.2 15.4L2 12L9.2 8.6L12 1Z" fill="url(#aqmArgonGrad)"/>
        <circle cx="12" cy="12" r="3" fill="#ffffff" opacity="0.95"/>
        <defs>
          <linearGradient id="aqmArgonGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#00f2fe"/>
            <stop offset="50%" stop-color="#4facfe"/>
            <stop offset="100%" stop-color="#7f00ff"/>
          </linearGradient>
        </defs>
      </svg>
    `,
    carbon: `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" style="flex-shrink:0;">
        <polygon points="12,2 20.5,7 20.5,17 12,22 3.5,17 3.5,7" stroke="url(#aqmCarbonGrad)" stroke-width="1.8" fill="rgba(168,85,247,0.16)"/>
        <polygon points="12,6.5 16.8,9.25 16.8,14.75 12,17.5 7.2,14.75 7.2,9.25" fill="url(#aqmCarbonGrad)"/>
        <defs>
          <linearGradient id="aqmCarbonGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#a855f7"/>
            <stop offset="100%" stop-color="#6366f1"/>
          </linearGradient>
        </defs>
      </svg>
    `,
    claude: `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" style="flex-shrink:0;">
        <path d="M13.8 2.5a1.8 1.8 0 0 0-3.6 0l-.8 7.3a1.8 1.8 0 0 1-1.6 1.6l-7.3.8a1.8 1.8 0 0 0 0 3.6l7.3.8a1.8 1.8 0 0 1 1.6 1.6l.8 7.3a1.8 1.8 0 0 0 3.6 0l.8-7.3a1.8 1.8 0 0 1 1.6-1.6l7.3-.8a1.8 1.8 0 0 0 0-3.6l-7.3-.8a1.8 1.8 0 0 1-1.6-1.6l-.8-7.3z" fill="#D97706"/>
      </svg>
    `,
    gpt: `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">
        <path d="M12 2a10 10 0 0 0-9.5 6.9A10 10 0 0 0 4.2 19a10 10 0 0 0 15.6.1 10 10 0 0 0 1.7-10.2A10 10 0 0 0 12 2z"/>
        <path d="M12 6a6 6 0 0 0-5.7 4.1A6 6 0 0 0 7.3 16a6 6 0 0 0 9.4 0 6 6 0 0 0 1-6A6 6 0 0 0 12 6z"/>
      </svg>
    `,
    lightning: `
      <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink:0;">
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
      </svg>
    `,
    refresh: `
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">
        <polyline points="23 4 23 10 17 10"/>
        <polyline points="1 20 1 14 7 14"/>
        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
      </svg>
    `
  };

  function mapRawPoolName(rawName) {
    const s = String(rawName || '').toLowerCase();
    if (s.includes('hydrogen') || s.includes('flash-worker')) return 'Gemini 4 Hydrogen';
    if (s.includes('argon')) return 'Gemini 4 Argon';
    if (s.includes('carbon') || s.includes('orchestrator') || s.includes('3.1 pro')) return 'Gemini 4 Carbon & Orchestrator';
    if (s.includes('flash')) return 'Gemini 3.8 Flash';
    if (s.includes('claude') || s.includes('opus') || s.includes('sonnet')) return 'Claude 4.6 (Opus & Sonnet)';
    if (s.includes('gpt') || s.includes('oss')) return 'GPT-OSS 120B';
    return rawName || 'Gemini 3.8 Flash';
  }

  function getPoolIconSvg(poolName) {
    const p = String(poolName || '').toLowerCase();
    if (p.includes('hydrogen')) return SVGS.hydrogen;
    if (p.includes('argon')) return SVGS.argon;
    if (p.includes('carbon') || p.includes('orchestrator')) return SVGS.carbon;
    if (p.includes('claude') || p.includes('sonnet') || p.includes('opus')) return SVGS.claude;
    if (p.includes('gpt') || p.includes('oss')) return SVGS.gpt;
    return SVGS.gemini;
  }

  function isPoolActiveForModel(poolName, modelName) {
    const p = String(poolName || '').toLowerCase();
    const m = String(modelName || '').toLowerCase();
    if (!p || !m) return false;
    if (p.includes('argon')) return m.includes('argon');
    if (p.includes('hydrogen')) return m.includes('hydrogen') || m.includes('flash-worker');
    if (p.includes('carbon') || p.includes('orchestrator')) {
      return m.includes('carbon') || (m.includes('orchestrator') && !m.includes('argon')) || m.includes('3.1 pro');
    }
    if (p.includes('flash')) return m.includes('flash') && !m.includes('flash-worker') && !m.includes('hydrogen');
    if (p.includes('claude') && p.includes('gpt')) {
      return m.includes('claude') || m.includes('sonnet') || m.includes('opus') || m.includes('gpt') || m.includes('oss');
    }
    if (p.includes('claude')) return m.includes('claude') || m.includes('sonnet') || m.includes('opus');
    if (p.includes('gpt')) return m.includes('gpt') || m.includes('oss');
    if (p.includes('gemini')) {
      return (m.includes('gemini') || m.includes('flash') || m.includes('pro') || m.includes('orchestrator')) && !m.includes('argon');
    }
    return false;
  }

  function getAccountNeedsAuth(acc) {
    return Boolean(acc && (acc.needs_reauth || acc.has_token === false));
  }

  let currentUsage = (() => {
    const isInst2 = isInstance2Window();
    try {
      if (window.__antigravity_quota && window.__antigravity_quota.session) {
        return window.__antigravity_quota;
      }
      if (window.__antigravity_accounts && window.__antigravity_accounts.activeAccount && window.__antigravity_accounts.activeAccount.session) {
        return window.__antigravity_accounts.activeAccount;
      }
      const instanceAccount = localStorage.getItem('antigravity:account_email');
      if (instanceAccount) {
        const itemByEmail = localStorage.getItem('antigravity:active_quota:' + instanceAccount);
        if (itemByEmail) {
          const parsed = JSON.parse(itemByEmail);
          if (parsed && parsed.session) return parsed;
        }
      }
      const item = localStorage.getItem('antigravity:active_quota');
      if (item) {
        const parsed = JSON.parse(item);
        if (parsed && parsed.session) {
          const qEmail = parsed.email;
          const assignedEmail = localStorage.getItem('antigravity:account_email') || window.__antigravity_account || '';
          if (!assignedEmail || !qEmail || qEmail.toLowerCase() === assignedEmail.toLowerCase()) {
            return parsed;
          }
        }
      }
    } catch (e) {}
    let assignedEmail = '';
    try { assignedEmail = localStorage.getItem('antigravity:account_email') || window.__antigravity_account || ''; } catch (e) {}
    let fallbackEmail = assignedEmail;
    let fallbackName = assignedEmail
      ? (assignedEmail.split('@')[0].split('.')[0].charAt(0).toUpperCase() + assignedEmail.split('@')[0].split('.')[0].slice(1))
      : 'Account';
    let fallbackAvatar = '';
    try {
      const manifestStr = localStorage.getItem('antigravity:accounts_manifest');
      if (manifestStr) {
        const manifest = JSON.parse(manifestStr);
        const keys = Object.keys(manifest || {});
        if (assignedEmail && manifest[assignedEmail]) {
          fallbackEmail = assignedEmail;
          fallbackName = manifest[assignedEmail]?.name || assignedEmail;
          fallbackAvatar = manifest[assignedEmail]?.avatar || '';
        } else if (keys.length > 0) {
          const matchKey = (isInst2 ? (keys.find(k => isAccount2(k)) || keys[1]) : keys[0]) || keys[0];
          fallbackEmail = matchKey;
          fallbackName = manifest[matchKey]?.name || matchKey;
          fallbackAvatar = manifest[matchKey]?.avatar || '';
        }
      }
    } catch (e) {}
    return {
      email: fallbackEmail,
      name: fallbackName,
      avatar: fallbackAvatar,
      tier: 'Google AI Pro',
      tier_code: 'pro',
      session: {
        name: 'Gemini 3.8 Flash',
        used_pct: 0,
        remaining_pct: 100,
        weekly_rem: 100,
        weekly_pct: 0,
        resets_in: 'loading...',
        reset_time: ''
      },
      weekly: { remaining_pct: 100, used_pct: 0, resets_in: 'loading...' },
      pools: []
    };
  })();

  let swState = {
    activeAccount: (() => {
      const isInst2 = isInstance2Window();
      try {
        const assignedEmail = localStorage.getItem('antigravity:account_email') || window.__antigravity_account || '';
        if (window.__antigravity_accounts && window.__antigravity_accounts.activeAccount) {
          const a = window.__antigravity_accounts.activeAccount;
          if (a && a.email && a.email !== 'developer@antigravity.ai') {
            if (!assignedEmail || a.email.toLowerCase() === assignedEmail.toLowerCase()) return a;
          }
        }
        if (window.__antigravity_quota && window.__antigravity_quota.email && window.__antigravity_quota.email !== 'developer@antigravity.ai') {
          const qEmail = window.__antigravity_quota.email;
          if (!assignedEmail || qEmail.toLowerCase() === assignedEmail.toLowerCase()) return window.__antigravity_quota;
        }
        const cachedActive = localStorage.getItem('antigravity:active_quota');
        if (cachedActive) {
          const p = JSON.parse(cachedActive);
          if (p && p.email && p.email !== 'developer@antigravity.ai') {
            if (!assignedEmail || p.email.toLowerCase() === assignedEmail.toLowerCase()) return p;
          }
        }
        let manifest = {};
        try { manifest = JSON.parse(localStorage.getItem('antigravity:accounts_manifest') || '{}'); } catch (e) {}
        if (assignedEmail && manifest[assignedEmail]) {
          return {
            email: assignedEmail,
            name: manifest[assignedEmail].name || assignedEmail.split('@')[0],
            avatar: manifest[assignedEmail].avatar || '',
            tier: manifest[assignedEmail].tier || 'Google AI Pro',
            tier_code: manifest[assignedEmail].tier_code || 'pro'
          };
        }
        const mKeys = Object.keys(manifest);
        if (mKeys.length > 0) {
          const chosenKey = isInst2 ? (mKeys[1] || mKeys[0]) : mKeys[0];
          return {
            email: chosenKey,
            name: manifest[chosenKey]?.name || chosenKey.split('@')[0],
            avatar: manifest[chosenKey]?.avatar || '',
            tier: manifest[chosenKey]?.tier || 'Google AI Pro',
            tier_code: manifest[chosenKey]?.tier_code || 'pro'
          };
        }
      } catch (e) {}
      return { email: 'active@antigravity.ai', name: 'Antigravity User', avatar: '', tier: 'Google AI Pro', tier_code: 'pro' };
    })(),
    savedAccounts: (typeof window !== 'undefined' && window.__antigravity_accounts && window.__antigravity_accounts.savedAccounts) || {},
    conversations: (typeof window !== 'undefined' && window.__antigravity_accounts && Array.isArray(window.__antigravity_accounts.conversations)) ? window.__antigravity_accounts.conversations : [],
    projects: (typeof window !== 'undefined' && window.__antigravity_accounts && Array.isArray(window.__antigravity_accounts.projects)) ? window.__antigravity_accounts.projects : [],
    tasks: [],
    authState: (typeof window !== 'undefined' && window.__antigravity_accounts && window.__antigravity_accounts.authState) || null,
    allowedConversations: (() => {
      try {
        if (window.__antigravity_accounts && Array.isArray(window.__antigravity_accounts.allowedConversations)) {
          return window.__antigravity_accounts.allowedConversations;
        }
        const s = localStorage.getItem('antigravity:allowed_conversations');
        if (s) return JSON.parse(s);
      } catch (e) {}
      return [];
    })(),
    isLoaded: Boolean(typeof window !== 'undefined' && window.__antigravity_accounts && window.__antigravity_accounts.savedAccounts),
    isLoading: false
  };

  try {
    if (Object.keys(swState.savedAccounts || {}).length === 0) {
      const cachedMan = localStorage.getItem('antigravity:accounts_manifest');
      if (cachedMan) {
        swState.savedAccounts = JSON.parse(cachedMan) || {};
        swState.isLoaded = true;
      }
    }
  } catch (e) {}

  function getActiveModelName() {
    const trigger = document.querySelector('[data-testid="model-selector-trigger"]');
    if (!trigger) return 'Gemini 3.8 Flash';
    const firstLine = (trigger.innerText || '').split('\n')[0].trim();
    return firstLine || 'Gemini 3.8 Flash';
  }

  function getCleanUserDisplayName(rawCandidate, rawEmail) {
    let email = rawEmail || (swState.activeAccount && swState.activeAccount.email) || (window.__antigravity_quota && window.__antigravity_quota.email) || '';
    if (!email && rawCandidate && rawCandidate.includes('@')) email = rawCandidate;
    if (email && email.includes('@')) {
      let part = email.split('@')[0];
      if (part.includes('.')) part = part.split('.')[0];
      if (part.includes('+')) part = part.split('+')[0];
      part = part.trim();
      if (part.length > 0) return part.charAt(0).toUpperCase() + part.slice(1);
    }
    if (rawCandidate && typeof rawCandidate === 'string' && rawCandidate.trim()) {
      const c = rawCandidate.trim().split(' ')[0];
      if (!c.toLowerCase().includes('user')) return c.charAt(0).toUpperCase() + c.slice(1);
    }
    return 'Developer';
  }

  function getActiveAccountInfo() {
    const isInst2 = isInstance2Window();
    let designatedEmail = '';
    try {
      designatedEmail = localStorage.getItem('antigravity:account_email') || window.__antigravity_account || (swState.activeAccount && swState.activeAccount.email) || (currentUsage && currentUsage.email) || '';
    } catch (e) {}
    if (!designatedEmail && swState.savedAccounts) {
      const keys = Object.keys(swState.savedAccounts);
      if (keys.length > 0) designatedEmail = isInst2 ? (keys[1] || keys[0]) : keys[0];
    }
    let targetKey = designatedEmail;
    if (swState.savedAccounts && !swState.savedAccounts[targetKey]) {
      const matchKey = Object.keys(swState.savedAccounts).find(k => k.toLowerCase() === targetKey.toLowerCase());
      if (matchKey) targetKey = matchKey;
    }
    const savedInfo = (swState.savedAccounts && swState.savedAccounts[targetKey]) || {};
    const fallbackName = savedInfo.name || (targetKey ? (targetKey.split('@')[0].split('.')[0].charAt(0).toUpperCase() + targetKey.split('@')[0].split('.')[0].slice(1)) : 'Account');
    const fallbackAvatar = savedInfo.avatar || '';
    let accUser = { email: targetKey, name: fallbackName, avatar: fallbackAvatar, tier: savedInfo.tier || 'Google AI Pro', tier_code: savedInfo.tier_code || 'pro' };
    if (swState.activeAccount && swState.activeAccount.email && swState.activeAccount.email.toLowerCase() === targetKey.toLowerCase()) {
      accUser = { ...accUser, ...swState.activeAccount };
    } else if (currentUsage && currentUsage.email && currentUsage.email.toLowerCase() === targetKey.toLowerCase()) {
      accUser = { ...accUser, ...currentUsage };
    }
    if (accUser.name && (accUser.name === 'Account 2' || accUser.name.toLowerCase() === 'user')) {
      accUser.name = savedInfo.name || fallbackName;
    }
    const accEmail = targetKey;
    const accName = accUser.name || fallbackName;
    const accAvatar = accUser.avatar || fallbackAvatar;
    const accTier = accUser.tier || 'Google AI Pro';
    const accTierCode = (accUser.tier_code || 'pro').toLowerCase();
    const tierBadgeBg = accTierCode === 'ultra' ? 'linear-gradient(135deg, #ec4899, #8b5cf6)' : (accTierCode === 'pro' ? 'linear-gradient(135deg, rgba(245,158,11,0.25), rgba(217,119,6,0.35))' : 'rgba(148,163,184,0.15)');
    const tierBadgeColor = accTierCode === 'ultra' ? '#ffffff' : (accTierCode === 'pro' ? '#fbbf24' : '#94a3b8');
    const tierBadgeBorder = accTierCode === 'ultra' ? 'rgba(236,72,153,0.5)' : (accTierCode === 'pro' ? 'rgba(251,191,36,0.45)' : 'rgba(148,163,184,0.25)');
    const initialChar = accName ? accName.charAt(0).toUpperCase() : (targetKey ? targetKey.charAt(0).toUpperCase() : 'A');
    return { accEmail, accName, accAvatar, accTier, accTierCode, initialChar, tierBadgeBg, tierBadgeColor, tierBadgeBorder };
  }

  async function fetchStoredQuota() {
    try {
      const assignedEmail = localStorage.getItem('antigravity:account_email') || window.__antigravity_account || '';
      if (window.__antigravity_quota && window.__antigravity_quota.session) {
        const qEmail = window.__antigravity_quota.email;
        if (!assignedEmail || !qEmail || qEmail.toLowerCase() === assignedEmail.toLowerCase()) {
          currentUsage = { ...currentUsage, ...window.__antigravity_quota };
          return;
        }
      }
      const item = localStorage.getItem('antigravity:active_quota');
      if (item) {
        const parsed = JSON.parse(item);
        if (parsed && parsed.session) {
          const qEmail = parsed.email;
          if (!assignedEmail || !qEmail || qEmail.toLowerCase() === assignedEmail.toLowerCase()) {
            currentUsage = { ...currentUsage, ...parsed };
          }
        }
      }
    } catch (e) {}
  }

  async function fetchLiveQuotaFromCloudCode() {
    try {
      if (!window.__cloudCodeService) {
        const rootEl = document.getElementById('root') || document.body;
        const rk = rootEl && Object.keys(rootEl).find(k => k.startsWith('__reactFiber') || k.startsWith('__reactContainer'));
        if (rk) {
          const queue = [rootEl[rk]];
          let scanned = 0;
          while (queue.length > 0 && scanned < 2000) {
            const f = queue.shift();
            scanned++;
            if (!f) continue;
            if (f.memoizedProps?.value?.core?.cloudCodeService) {
              window.__cloudCodeService = f.memoizedProps.value.core.cloudCodeService;
              break;
            }
            if (f.child) queue.push(f.child);
            if (f.sibling) queue.push(f.sibling);
          }
        }
      }

      if (window.__cloudCodeService && window.__cloudCodeService.retrieveUserQuotaSummary) {
        const raw = await window.__cloudCodeService.retrieveUserQuotaSummary(false);
        const groups = raw?.response?.groups || raw?.groups || [];
        if (groups && groups.length > 0) {
          const pools = [];
          let geminiSession = null;
          let geminiWeekly = null;

          groups.forEach(g => {
            const gName = mapRawPoolName(g.displayName || '');
            const weeklyBucket = (g.buckets || []).find(b => b.window === 'weekly' || b.bucketId?.toLowerCase().includes('weekly') || b.displayName?.toLowerCase().includes('weekly'));
            const sessionBucket = (g.buckets || []).find(b => b.window === '5h' || b.bucketId?.toLowerCase().includes('5h') || b.displayName?.toLowerCase().includes('hour') || b.displayName?.toLowerCase().includes('five'));

            const wRem = weeklyBucket?.remainingFraction ?? weeklyBucket?.remaining?.value ?? 1.0;
            const sRem = sessionBucket?.remainingFraction ?? sessionBucket?.remaining?.value ?? 1.0;
            const sDesc = sessionBucket?.description || '';
            const wDesc = weeklyBucket?.description || '';

            let resetsIn = 'Ready';
            const m = sDesc.match(/in\s+([0-9]+\s+[a-zA-Z]+(?:\s*,\s*[0-9]+\s+[a-zA-Z]+)?)/i);
            if (m) {
              resetsIn = m[1].replace(/hours?/gi, 'hr').replace(/minutes?/gi, 'min').replace(/days?/gi, 'd');
            } else if (sessionBucket?.resetTime) {
              try {
                const diff = Math.max(0, Math.floor((new Date(sessionBucket.resetTime).getTime() - Date.now()) / 1000));
                const h = Math.floor(diff / 3600);
                const mn = Math.floor((diff % 3600) / 60);
                resetsIn = h > 0 ? `${h}hr ${mn}min` : `${mn}min`;
              } catch (e) {}
            }

            let wResetsIn = 'Ready';
            const mw = wDesc.match(/in\s+([0-9]+\s+[a-zA-Z]+(?:\s*,\s*[0-9]+\s+[a-zA-Z]+)?)/i);
            if (mw) {
              wResetsIn = mw[1].replace(/hours?/gi, 'hr').replace(/minutes?/gi, 'min').replace(/days?/gi, 'd');
            } else if (weeklyBucket?.resetTime) {
              try {
                const diff = Math.max(0, Math.floor((new Date(weeklyBucket.resetTime).getTime() - Date.now()) / 1000));
                const d = Math.floor(diff / 86400);
                const h = Math.floor((diff % 86400) / 3600);
                wResetsIn = d > 0 ? `${d}d ${h}hr` : `${h}hr`;
              } catch (e) {}
            }

            const poolObj = {
              name: gName,
              remaining_pct: Math.round(sRem * 1000) / 10,
              used_pct: Math.round((1.0 - sRem) * 1000) / 10,
              weekly_rem: Math.round(wRem * 1000) / 10,
              weekly_pct: Math.round((1.0 - wRem) * 1000) / 10,
              resets_in: resetsIn,
              reset_time: '',
              weekly_desc: wDesc,
              session_desc: sDesc
            };
            pools.push(poolObj);

            if (gName.toLowerCase().includes('gemini')) {
              geminiSession = {
                name: gName,
                used_pct: poolObj.used_pct,
                remaining_pct: poolObj.remaining_pct,
                resets_in: resetsIn,
                weekly_rem: poolObj.weekly_rem,
                weekly_pct: poolObj.weekly_pct
              };
              geminiWeekly = {
                remaining_pct: poolObj.weekly_rem,
                used_pct: poolObj.weekly_pct,
                resets_in: wResetsIn
              };
            }
          });

          if (geminiSession && geminiWeekly) {
            return { session: geminiSession, weekly: geminiWeekly, pools };
          }
        }
      }
    } catch (e) {
      console.warn('[AQM] Live quota error:', e);
    }
    return null;
  }

  async function refreshQuota() {
    if (isRefreshing) return;
    isRefreshing = true;
    if (typeof renderBadge === 'function') renderBadge();
    const pop = document.getElementById('antigravity-usage-popover');
    if (pop && pop.style.display !== 'none' && !pop.matches(':hover') && typeof renderPopover === 'function') renderPopover();

    try {
      const instParam = (typeof window !== 'undefined' && window.__antigravity_instance) || (isInstance2Window() ? 'instance_2' : 'instance_1');
      let daemonData = null;
      try {
        const res = await fetch(`http://127.0.0.1:39281/sync?instance=${instParam}`);
        if (res.ok) {
          const data = await res.json();
          if (data && data.session) {
            const dataEmail = (data.email || '').toLowerCase();
            const assignedEmail = (localStorage.getItem('antigravity:account_email') || window.__antigravity_account || '').toLowerCase();
            const emailOk = !assignedEmail || !dataEmail || (dataEmail === assignedEmail);
            if (emailOk) daemonData = data;
          }
        }
      } catch (e) {}

      if (daemonData) {
        currentUsage = {
          ...currentUsage,
          ...daemonData,
          session: daemonData.session,
          weekly: daemonData.weekly || currentUsage.weekly,
          pools: daemonData.pools || currentUsage.pools || []
        };
      } else {
        const liveData = await fetchLiveQuotaFromCloudCode();
        if (liveData && liveData.session) {
          currentUsage = {
            ...currentUsage,
            session: liveData.session,
            weekly: liveData.weekly || currentUsage.weekly,
            pools: liveData.pools || currentUsage.pools || []
          };
        }
      }
      window.__antigravity_quota = currentUsage;
      try {
        const s = safeJsonStringify(currentUsage);
        if (s) {
          localStorage.setItem('antigravity:active_quota', s);
          if (currentUsage.email) localStorage.setItem('antigravity:active_quota:' + currentUsage.email, s);
        }
      } catch (e) {}
    } catch (e) {
      console.warn('[AQM] refreshQuota error:', e);
    } finally {
      isRefreshing = false;
      if (typeof renderBadge === 'function') renderBadge();
      const p = document.getElementById('antigravity-usage-popover');
      if (p && p.style.display !== 'none' && !p.matches(':hover') && typeof renderPopover === 'function') renderPopover();
    }
  }

  function applyConversationIsolationFilter() {
    if (!isInstance2Window()) {
      document.querySelectorAll('[data-aqm-isolated="true"]').forEach(el => {
        el.style.removeProperty('display');
        el.removeAttribute('data-aqm-isolated');
      });
      return;
    }

    let allowedList = null;
    if (window.__antigravity_accounts && Array.isArray(window.__antigravity_accounts.allowedConversations)) {
      allowedList = window.__antigravity_accounts.allowedConversations;
    } else if (swState && Array.isArray(swState.allowedConversations)) {
      allowedList = swState.allowedConversations;
    } else if (swState && swState.allowedConversations && Array.isArray(swState.allowedConversations.instance_2)) {
      allowedList = swState.allowedConversations.instance_2;
    }

    if (!allowedList) {
      try {
        const stored = localStorage.getItem('antigravity:allowed_conversations');
        if (stored) allowedList = JSON.parse(stored);
      } catch (e) {}
    }

    if (!Array.isArray(allowedList) || allowedList.length === 0) {
      document.querySelectorAll('[data-aqm-isolated="true"]').forEach(el => {
        el.style.removeProperty('display');
        el.removeAttribute('data-aqm-isolated');
      });
      return;
    }

    const allowedSet = new Set(allowedList);
    document.querySelectorAll('a[href*="/c/"]').forEach(a => {
      try {
        const href = a.getAttribute('href') || a.href || '';
        const match = href.match(/\/c\/([a-f0-9\-]{36})/i);
        if (!match) return;
        const cid = match[1];
        let row = a;
        while (row && row.parentElement && row.parentElement !== document.body) {
          const p = row.parentElement;
          if (row.classList.contains('group') || row.classList.contains('w-full') || (p.children.length > 1 && row.classList.contains('relative'))) {
            break;
          }
          row = p;
        }
        if (!row) row = a.parentElement || a;
        if (!allowedSet.has(cid)) {
          if (row.style.display !== 'none') {
            row.style.setProperty('display', 'none', 'important');
            row.setAttribute('data-aqm-isolated', 'true');
          }
        } else if (row.getAttribute('data-aqm-isolated') === 'true') {
          row.style.removeProperty('display');
          row.removeAttribute('data-aqm-isolated');
        }
      } catch (e) {}
    });
  }

  function showSwitcherToast(msg, isError = false) {
    let container = document.getElementById('antigravity-switcher-modal');
    let isBodyToast = false;
    if (!container || !container.classList.contains('aqm-active')) {
      container = document.body;
      isBodyToast = true;
    }
    if (!container) return;
    let toast = container.querySelector('.aqm-sw-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.className = 'aqm-sw-toast';
      if (isBodyToast) {
        toast.style.position = 'fixed';
        toast.style.bottom = '28px';
        toast.style.left = '50%';
        toast.style.transform = 'translateX(-50%)';
        toast.style.zIndex = '2147483647';
        toast.style.padding = '8px 18px';
        toast.style.borderRadius = '9999px';
        toast.style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.5)';
        toast.style.fontFamily = 'system-ui, -apple-system, sans-serif';
        toast.style.fontSize = '12px';
        toast.style.fontWeight = '600';
        toast.style.transition = 'opacity 0.25s, transform 0.25s';
      }
      container.appendChild(toast);
    }
    if (typeof msg === 'string' && (msg.includes('<') && msg.includes('>'))) {
      toast.innerHTML = msg;
    } else {
      toast.textContent = msg;
    }
    toast.style.pointerEvents = 'auto';
    toast.style.background = isError ? 'rgba(239, 68, 68, 0.95)' : 'rgba(16, 185, 129, 0.95)';
    toast.style.color = '#ffffff';
    toast.style.border = `1px solid ${isError ? 'rgba(239, 68, 68, 0.6)' : 'rgba(16, 185, 129, 0.6)'}`;
    toast.classList.add('show');
    toast.style.opacity = '1';
    if (swToastTimeout) clearTimeout(swToastTimeout);
    const hasLink = typeof msg === 'string' && msg.includes('<a');
    swToastTimeout = setTimeout(() => {
      toast.classList.remove('show');
      if (isBodyToast) toast.style.opacity = '0';
    }, hasLink ? 35000 : 5000);
  }
  window.__showSwitcherToast = showSwitcherToast;

  function fetchSwitcherState(cb) {
    const inst = (typeof window !== 'undefined' && window.__antigravity_instance) || (isInstance2Window() ? 'instance_2' : 'instance_1');
    const acc = (typeof window !== 'undefined' && window.__antigravity_account) || '';
    fetch(`http://127.0.0.1:39281/api/state?instance=${encodeURIComponent(inst)}&account=${encodeURIComponent(acc)}`)
      .then(r => r.json())
      .then(data => {
        if (typeof window.__onSwitcherStateUpdate === 'function') window.__onSwitcherStateUpdate(data);
        if (cb) cb();
      })
      .catch(() => { if (cb) cb(); });
  }

  function getSessionMismatchInfo(fallbackCredEmail = '') {
    if (isInstance2Window()) return null;
    const auth = swState.authState || {};
    const isMismatch = (auth.session_mismatch === true) ||
      (auth.session_mismatch !== false && currentUsage && currentUsage.session_mismatch === true);
    if (!isMismatch) return null;
    const credentialEmail = auth.credential_email || (currentUsage && currentUsage.credential_email) ||
      (swState.activeAccount && swState.activeAccount.email) || (currentUsage && currentUsage.email) || fallbackCredEmail || '';
    const liveEmail = auth.live_ide_email || (currentUsage && currentUsage.live_ide_email) || '';
    return { credentialEmail, liveEmail };
  }

  function renderMismatchBannerHtml(info, isFa, uiDir, uiFont) {
    if (!info) return '';
    const cred = escHtml(info.credentialEmail || '?');
    const live = escHtml(info.liveEmail || '?');
    const fontAttr = uiFont ? `font-family:${uiFont};` : '';
    const msg = isFa
      ? `ناهمخوانی نشست: سیستم روی <code dir="ltr" style="direction:ltr;unicode-bidi:isolate;color:#fde68a;font-family:'JetBrains Mono',monospace;">${cred}</code> است ولی پنجره فعلی IDE هنوز روی <code dir="ltr" style="direction:ltr;unicode-bidi:isolate;color:#fca5a5;font-family:'JetBrains Mono',monospace;">${live}</code> است.`
      : `Session mismatch: OS Credential Manager is on <code dir="ltr" style="direction:ltr;unicode-bidi:isolate;color:#fde68a;font-family:'JetBrains Mono',monospace;">${cred}</code> while the running IDE session is still on <code dir="ltr" style="direction:ltr;unicode-bidi:isolate;color:#fca5a5;font-family:'JetBrains Mono',monospace;">${live}</code>.`;
    return `
      <div class="aqm-mismatch-banner" style="margin:6px 0 8px 0;padding:8px 10px;border-radius:11px;background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.38);color:#fef3c7;direction:${uiDir};${fontAttr}display:flex;flex-direction:column;gap:6px;">
        <div style="font-size:10.5px;line-height:1.55;display:flex;align-items:flex-start;gap:6px;">
          <span style="flex-shrink:0;">⚠️</span>
          <span>${msg}</span>
        </div>
        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
          <button type="button" class="aqm-mismatch-restart-btn" style="padding:3px 9px;border-radius:7px;background:rgba(56,189,248,0.16);border:1px solid rgba(56,189,248,0.4);color:#7dd3fc;font-size:10px;font-weight:700;cursor:pointer;${fontAttr}">
            🔄 ${isFa ? 'ری‌استارت' : 'Restart'}
          </button>
          <button type="button" class="aqm-mismatch-dual-btn" data-action="launch-dual" data-acc="${escHtml(info.credentialEmail)}" style="padding:3px 9px;border-radius:7px;background:rgba(16,185,129,0.16);border:1px solid rgba(16,185,129,0.4);color:#6ee7b7;font-size:10px;font-weight:700;cursor:pointer;${fontAttr}">
            🪟 ${isFa ? 'پنجره دوم' : '2nd Window'}
          </button>
        </div>
      </div>
    `;
  }

  function restartAntigravityApp() {
    const isFa = (swLang === 'fa');
    showSwitcherToast(isFa ? 'در حال ری‌استارت برنامه Antigravity... پلاگین به‌صورت خودکار متصل می‌شود 🔄' : 'Restarting Antigravity... Plugin will auto-inject on startup 🔄');
    if (callDaemonIpc('restart_app', {})) return;
    postJson('http://127.0.0.1:39281/api/restart', {}).catch(() => {});
  }
  window.restartAntigravityApp = restartAntigravityApp;

  function launchDualInstanceForAccount(accKey, projectPath = '', triggerBtn = null) {
    if (!accKey) return;
    const isFa = (swLang === 'fa');
    if (triggerBtn) {
      triggerBtn.disabled = true;
      setTimeout(() => { try { triggerBtn.disabled = false; } catch (err) {} }, 3000);
    }
    showSwitcherToast(isFa ? 'در حال اجرای پنجره دوم آنتی‌گرویتی...' : 'Launching 2nd Antigravity instance...');

    const payload = { accountKey: accKey, noRestart: true };
    if (projectPath) payload.projectPath = projectPath;

    if (callDaemonIpc('launch_dual', payload)) {
      setTimeout(() => {
        fetchSwitcherState(() => { if (typeof renderSwitcherModal === 'function') renderSwitcherModal(); });
      }, 1500);
      return;
    }

    postJson('http://127.0.0.1:39281/api/launch_dual', payload)
      .then(r => r.json())
      .then(res => {
        if (res && res.needs_reauth) {
          showSwitcherToast(res.error || (isFa ? 'این حساب نیاز به ورود دارد' : 'Account requires sign-in'), true);
          postJson('http://127.0.0.1:39281/api/oauth_signin', { accountKey: accKey, noRestart: true })
            .then(r => r.json())
            .then(ores => {
              if (ores && ores.auth_url) {
                swOAuthUrl = ores.auth_url;
                if (typeof renderSwitcherModal === 'function') renderSwitcherModal();
                try { window.open(ores.auth_url, '_blank'); } catch (err) {}
              }
            }).catch(() => { callDaemonIpc('oauth_signin', { accountKey: accKey }); });
          return;
        }
        if (res && res.success) {
          showSwitcherToast(res.msg || (isFa ? 'پنجره دوم با موفقیت اجرا شد!' : '2nd instance started successfully!'));
          fetchSwitcherState(() => { if (typeof renderSwitcherModal === 'function') renderSwitcherModal(); });
        } else if (res && res.error) {
          showSwitcherToast(res.error, true);
        }
      })
      .catch(() => {
        showSwitcherToast(isFa ? 'خطا در ارتباط با سرویس لانچر' : 'Launcher connection error', true);
      });
  }

  function bindMismatchBannerEvents(container) {
    if (!container) return;
    container.querySelectorAll('.aqm-mismatch-restart-btn').forEach(btn => {
      btn.onclick = (e) => {
        if (e) e.stopPropagation();
        restartAntigravityApp();
      };
    });
    container.querySelectorAll('.aqm-mismatch-dual-btn').forEach(btn => {
      btn.onclick = (e) => {
        if (e) e.stopPropagation();
        launchDualInstanceForAccount(btn.getAttribute('data-acc'), '', btn);
      };
    });
  }

  function switchAccount(accKey, forceRestart = null) {
    if (!accKey) return;
    const isFa = (swLang === 'fa');
    const shouldRestart = (forceRestart !== null) ? Boolean(forceRestart) : Boolean(swAutoRestart);
    showSwitcherToast(
      shouldRestart
        ? (isFa ? `در حال سوئیچ به ${accKey} و ری‌استارت برنامه...` : `Switching to ${accKey} & restarting app...`)
        : (isFa ? `در حال جابجایی به ${accKey}...` : `Switching to ${accKey}...`)
    );
    const payload = { accountKey: accKey, noRestart: !shouldRestart };

    const finalizeSwitch = () => {
      fetchSwitcherState(() => {
        if (typeof renderBadge === 'function') renderBadge();
        const pop = document.getElementById('antigravity-usage-popover');
        if (pop && pop.style.display !== 'none' && typeof renderPopover === 'function') renderPopover();
        const modal = document.getElementById('antigravity-switcher-modal');
        if (modal && modal.classList.contains('aqm-active') && typeof renderSwitcherModal === 'function') renderSwitcherModal();
        refreshQuota();
      });
    };

    if (callDaemonIpc('switch', payload)) {
      setTimeout(finalizeSwitch, 400);
      return;
    }

    postJson('http://127.0.0.1:39281/api/switch', payload)
      .then(r => r.json())
      .then(res => {
        if (res && res.needs_reauth) {
          showSwitcherToast(res.error || (isFa ? 'این حساب نیاز به ورود مجدد دارد' : 'Account requires sign-in'), true);
          return;
        }
        if (res && res.success) {
          showSwitcherToast(isFa ? `حساب به ${accKey} تغییر یافت ⚡️` : `Switched to ${accKey} ⚡️`);
          finalizeSwitch();
        } else {
          showSwitcherToast((res && res.error) || (isFa ? 'خطا در جابجایی حساب' : 'Switch error'), true);
        }
      })
      .catch(() => {
        showSwitcherToast(isFa ? 'خطا در اتصال به سرویس سوئیچر' : 'Connection error', true);
      });
  }
  window.switchAccount = switchAccount;

  window.__onSwitcherStateUpdate = function(data) {
    if (!data) return;
    const isInst2 = isInstance2Window();
    const instMismatch = (data.instanceId && ((isInst2 && data.instanceId !== 'instance_2') || (!isInst2 && data.instanceId !== 'instance_1')));

    if (data.savedAccounts) swState.savedAccounts = data.savedAccounts;
    if (data.conversations) swState.conversations = data.conversations;
    if (data.projects) swState.projects = data.projects;
    if (data.tasks) swState.tasks = data.tasks;
    if (data.authState) swState.authState = data.authState;
    if (data.allowedConversations) {
      swState.allowedConversations = data.allowedConversations;
      try { localStorage.setItem('antigravity:allowed_conversations', JSON.stringify(data.allowedConversations)); } catch (e) {}
    }

    if (data.activeAccount && !instMismatch) {
      const prevAcc = swState.activeAccount || {};
      const newAcc = { ...data.activeAccount };
      if (newAcc.email) {
        try { localStorage.setItem('antigravity:account_email', newAcc.email); } catch (e) {}
      }
      if ((!newAcc.tier_code || newAcc.tier_code === 'free') && (prevAcc.tier_code === 'pro' || prevAcc.tier_code === 'ultra' || prevAcc.tier_code === 'enterprise')) {
        newAcc.tier_code = prevAcc.tier_code;
        newAcc.tier = prevAcc.tier;
      }
      if (!newAcc.avatar && prevAcc.avatar) newAcc.avatar = prevAcc.avatar;
      if (!newAcc.avatar) {
        const saved = (swState.savedAccounts && swState.savedAccounts[newAcc.email || prevAcc.email]) || {};
        if (saved.avatar) newAcc.avatar = saved.avatar;
      }
      swState.activeAccount = newAcc;
      window.__antigravity_quota = newAcc;
      currentUsage = { ...currentUsage, ...newAcc };
      try { localStorage.setItem('antigravity:active_quota', JSON.stringify(newAcc)); } catch (e) {}
    }

    swState.isLoaded = true;
    swState.isLoading = false;
    try { localStorage.setItem('antigravity:accounts_manifest', JSON.stringify(swState.savedAccounts)); } catch (e) {}
    applyConversationIsolationFilter();
    if (typeof renderBadge === 'function') renderBadge();
    const modal = document.getElementById('antigravity-switcher-modal');
    if (modal && modal.classList.contains('aqm-active') && typeof renderSwitcherModal === 'function') renderSwitcherModal();
    const pop = document.getElementById('antigravity-usage-popover');
    if (pop && pop.style.display !== 'none' && typeof renderPopover === 'function') renderPopover();
  };

  window.__onOAuthUrlReady = function(url) {
    if (!url) return;
    swOAuthUrl = url;
    swShowAddPanel = true;
    if (typeof renderSwitcherModal === 'function') renderSwitcherModal();
  };
