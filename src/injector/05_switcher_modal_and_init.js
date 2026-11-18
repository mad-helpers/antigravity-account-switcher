  const SW_I18N = {
    fa: {
      appName: 'مدیریت حساب‌ها',
      appSubtitle: 'مدیریت چنداکانت و سهمیه پروژه‌ها',
      tabAccounts: 'حساب‌ها و سهمیه',
      tabProjects: 'پروژه‌ها و سهمیه',
      activeAccount: 'حساب فعال',
      saveCurrent: 'ذخیره این اکانت',
      savedAccounts: 'حساب‌های ذخیره‌شده',
      noSavedAccounts: 'هنوز اکانتی ذخیره نشده است.',
      switchNow: '⚡️ سوئیچ',
      deleteAccount: 'حذف',
      refresh: '🔄 به‌روزرسانی',
      resetsIn: 'تمدید در',
      author: 'توسعه‌یافته توسط mad-helpers',
      projectsDesc: 'مدیریت دسترسی حساب‌ها و انتخاب حساب پرداخت‌کننده سهمیه برای هر پروژه:',
      syncNow: '🔄 سینک',
      launchDual: '🪟 پنجره مجزا',
      launchDualTitle: 'باز کردن در پنجره مجزای آنتی‌گرویتی',
      noProjectsFound: 'هیچ پروژه‌ای یافت نشد.',
      activeBadge: 'فعال',
      pro: 'پرو',
      ultra: 'اولترا',
      free: 'معمولی'
    },
    en: {
      appName: 'Antigravity Switcher',
      appSubtitle: 'Multi-Account & Project Quota Suite',
      tabAccounts: 'Accounts & Quota',
      tabProjects: 'Projects & Quota',
      activeAccount: 'Active Account',
      saveCurrent: 'Save Account',
      savedAccounts: 'Saved Accounts',
      noSavedAccounts: 'No accounts saved yet.',
      switchNow: '⚡️ Switch',
      deleteAccount: 'Delete',
      refresh: '🔄 Refresh',
      resetsIn: 'Resets in',
      author: 'Developed by mad-helpers',
      projectsDesc: 'Configure account access & quota payer account per project:',
      syncNow: '🔄 Sync',
      launchDual: '🪟 Separate Window',
      launchDualTitle: 'Open in separate Antigravity window',
      noProjectsFound: 'No projects found.',
      activeBadge: 'ACTIVE',
      pro: 'PRO',
      ultra: 'ULTRA',
      free: 'FREE'
    }
  };

  function openSwitcherModal() {
    let modal = document.getElementById('antigravity-switcher-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'antigravity-switcher-modal';
      modal.className = 'aqm-switcher-modal';
      (document.body || document.documentElement).appendChild(modal);

      modal.onclick = (e) => {
        if (e.target === modal) closeSwitcherModal();
      };
      onGlobal(window, 'keydown', (e) => {
        if (e.key === 'Escape' && (modal.classList.contains('aqm-active') || modal.style.visibility === 'visible')) {
          closeSwitcherModal();
        }
      });
    }

    modal.style.position = 'fixed';
    modal.style.inset = '0';
    modal.style.zIndex = '2147483647';
    modal.style.display = 'flex';
    modal.style.alignItems = 'center';
    modal.style.justifyContent = 'center';
    modal.style.background = 'rgba(0, 0, 0, 0.72)';
    modal.style.backdropFilter = 'blur(16px)';
    modal.style.webkitBackdropFilter = 'blur(16px)';
    modal.style.opacity = '1';
    modal.style.pointerEvents = 'auto';
    modal.style.visibility = 'visible';

    modal.classList.add('aqm-active');
    renderSwitcherModal();
    fetchSwitcherState(() => { renderSwitcherModal(); });
  }

  function closeSwitcherModal() {
    const modal = document.getElementById('antigravity-switcher-modal');
    if (modal) {
      modal.classList.remove('aqm-active');
      modal.style.opacity = '0';
      modal.style.pointerEvents = 'none';
      modal.style.visibility = 'hidden';
    }
  }

  function toggleSwitcherModal() {
    const modal = document.getElementById('antigravity-switcher-modal');
    if (modal && (modal.classList.contains('aqm-active') || modal.style.visibility === 'visible')) {
      closeSwitcherModal();
    } else {
      openSwitcherModal();
    }
  }

  function renderSwitcherModal() {
    if (swTab !== 'accounts' && swTab !== 'projects') swTab = 'accounts';
    const modal = document.getElementById('antigravity-switcher-modal');
    if (!modal) return;

    const t = SW_I18N[swLang] || SW_I18N.en;
    const isFa = (swLang === 'fa');
    const dir = isFa ? 'rtl' : 'ltr';
    const fontFamily = "'Vazirmatn', 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";

    const isInst2 = isInstance2Window();
    const activeAcc = { ...(swState.activeAccount || currentUsage || {}) };
    let email = activeAcc.email;
    let assignedEmail = '';
    try { assignedEmail = localStorage.getItem('antigravity:account_email') || window.__antigravity_account || ''; } catch (e) {}
    if (assignedEmail && swState.savedAccounts && swState.savedAccounts[assignedEmail]) {
      email = assignedEmail;
      Object.assign(activeAcc, swState.savedAccounts[assignedEmail]);
    } else if (email && swState.savedAccounts && swState.savedAccounts[email]) {
      Object.assign(activeAcc, swState.savedAccounts[email]);
    } else if (assignedEmail) {
      email = assignedEmail;
    }
    if (!email && swState.savedAccounts) {
      const keys = Object.keys(swState.savedAccounts);
      if (keys.length > 0) email = isInst2 ? (keys[1] || keys[0]) : keys[0];
    }

    let cleanDisplayName = getCleanUserDisplayName(activeAcc.name, email);
    cleanDisplayName = cleanDisplayName ? (cleanDisplayName.charAt(0).toUpperCase() + cleanDisplayName.slice(1)) : 'User';
    if (isInst2 && (!cleanDisplayName || cleanDisplayName.toLowerCase() === 'user')) {
      cleanDisplayName = email ? (email.split('@')[0].split('.')[0].charAt(0).toUpperCase() + email.split('@')[0].split('.')[0].slice(1)) : 'Secondary';
    } else if (cleanDisplayName.toLowerCase() === 'developer') {
      cleanDisplayName = 'Account 1';
    }
    const avatar = activeAcc.avatar || '';
    const tierCode = (activeAcc.tier_code || 'pro').toLowerCase();

    const sess = activeAcc.session || (window.__antigravity_quota && window.__antigravity_quota.session) || {};
    const usedPct = Math.round(sess.used_pct ?? 0);
    const remPct = Math.round(sess.remaining_pct ?? (100 - usedPct));
    const resetsIn = sess.resets_in || 'Ready';

    const savedKeys = Object.keys(swState.savedAccounts || {});
    const savedCount = savedKeys.length;
    const isCurrentSaved = !!(email && swState.savedAccounts && swState.savedAccounts[email]);
    const projectsList = Array.isArray(swState.projects) ? swState.projects : [];

    modal.innerHTML = `
      <div class="aqm-switcher-sheet" style="font-family:${fontFamily};direction:${dir};color:#f8fafc;">
        <div style="padding:12px 18px;border-bottom:1px solid rgba(255,255,255,0.06);display:flex;align-items:center;justify-content:space-between;flex-shrink:0;">
          <div style="display:flex;align-items:center;gap:8px;">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="opacity:0.85;">
              <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
            <span style="font-size:13.5px;font-weight:700;">${escHtml(t.appName)}</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px;">
            <button id="aqm-sw-restart-app-btn" type="button" title="${isFa ? 'ری‌استارت برنامه Antigravity (با حفظ پلاگین)' : 'Restart Antigravity App'}" style="background:rgba(56,189,248,0.1);border:1px solid rgba(56,189,248,0.28);color:#38bdf8;padding:3px 9px;border-radius:9999px;font-size:10.5px;font-weight:700;cursor:pointer;display:inline-flex;align-items:center;gap:4px;outline:none;">
              <span>🔄</span>
              <span>${isFa ? 'ری‌استارت برنامه' : 'Restart App'}</span>
            </button>
            <button id="aqm-lang-toggle-btn" type="button" title="${isFa ? 'Switch to English (EN)' : 'تغییر زبان به فارسی (فا)'}" style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);color:#e2e8f0;padding:3px 9px;border-radius:9999px;font-size:10.5px;font-weight:700;cursor:pointer;outline:none;">
              ${isFa ? 'EN' : 'فا'}
            </button>
            <button id="aqm-sw-modal-close" type="button" style="width:24px;height:24px;border-radius:50%;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);color:#94a3b8;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:11px;">✕</button>
          </div>
        </div>

        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;padding:8px 18px;border-bottom:1px solid rgba(255,255,255,0.06);background:rgba(0,0,0,0.12);flex-shrink:0;flex-wrap:wrap;">
          <div style="display:flex;align-items:center;gap:6px;">
            <button type="button" class="aqm-sw-tab-btn ${swTab === 'accounts' ? 'active' : ''}" id="aqm-tab-btn-accounts">
              <span>👤</span>
              <span>${escHtml(t.tabAccounts)}</span>
            </button>
            <button type="button" class="aqm-sw-tab-btn ${swTab === 'projects' ? 'active' : ''}" id="aqm-tab-btn-projects">
              <span>📁</span>
              <span>${escHtml(t.tabProjects)}</span>
            </button>
          </div>
          <label id="aqm-sw-autorestart-row" style="display:inline-flex;align-items:center;gap:6px;font-size:10.5px;color:#cbd5e1;cursor:pointer;user-select:none;" title="${isFa ? 'اگر فعال باشد، پس از سوئیچ اکانت برنامه به‌طور خودکار ری‌استارت می‌شود' : 'Automatically restart Antigravity after switching accounts'}">
            <input type="checkbox" id="aqm-sw-autorestart-chk" ${swAutoRestart ? 'checked' : ''} style="accent-color:#3b82f6;cursor:pointer;" />
            <span>${isFa ? 'ری‌استارت خودکار پس از سوئیچ' : 'Auto-restart on switch'}</span>
          </label>
        </div>

        <div class="aqm-custom-scroll" style="flex:1;overflow-y:auto;padding:14px 18px;display:flex;flex-direction:column;gap:12px;">
          ${renderMismatchBannerHtml(getSessionMismatchInfo(email), isFa, dir, fontFamily)}

          ${swTab === 'accounts' ? `
            <div class="aqm-sw-card" style="padding:14px 15px;">
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
                <div style="display:flex;align-items:center;gap:10px;">
                  <div style="position:relative;flex-shrink:0;">
                    ${avatar ? `<img src="${escHtml(avatar)}" style="width:34px;height:34px;border-radius:50%;object-fit:cover;border:1px solid rgba(255,255,255,0.18);" />` : `
                      <div style="width:34px;height:34px;border-radius:50%;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700;color:#f8fafc;">${escHtml(cleanDisplayName[0] || 'A')}</div>
                    `}
                    <div style="position:absolute;bottom:0;right:0;width:8px;height:8px;border-radius:50%;background:#10b981;border:1.5px solid #0d1118;"></div>
                  </div>
                  <div>
                    <div style="display:flex;align-items:center;gap:6px;">
                      <span style="font-size:13.5px;font-weight:700;">${escHtml(cleanDisplayName)}</span>
                      <span style="font-size:9px;font-weight:700;padding:1px 6px;border-radius:9999px;background:rgba(251,191,36,0.12);color:#fbbf24;border:1px solid rgba(251,191,36,0.25);text-transform:uppercase;">${escHtml(tierCode.toUpperCase())}</span>
                    </div>
                    <div style="font-size:11px;color:#94a3b8;font-family:'JetBrains Mono',monospace;" dir="ltr">${escHtml(email || '')}</div>
                  </div>
                </div>
                <div style="display:flex;align-items:center;gap:6px;">
                  ${isCurrentSaved ? `
                    <span style="font-size:11px;color:#10b981;font-weight:600;display:inline-flex;align-items:center;gap:4px;padding:3px 8px;background:rgba(16,185,129,0.08);border-radius:9999px;border:1px solid rgba(16,185,129,0.2);">
                      <span>●</span>
                      <span>${isFa ? 'ذخیره در لیست' : 'Saved'}</span>
                    </span>
                  ` : `
                    <button type="button" class="aqm-sw-btn aqm-sw-btn-primary" id="aqm-sw-save-current-btn" title="${escHtml(t.saveCurrent)}">
                      <span>💾</span>
                      <span>${isFa ? 'ذخیره اکانت' : 'Save'}</span>
                    </button>
                  `}
                  <button type="button" class="aqm-sw-btn" id="aqm-sw-refresh-btn" title="${escHtml(t.refresh)}" style="padding:4px 8px;">
                    <span class="${isRefreshing ? 'aqm-rotating' : ''}">🔄</span>
                  </button>
                </div>
              </div>

              <div style="background:rgba(0,0,0,0.18);border-radius:10px;padding:9px 12px;border:1px solid rgba(255,255,255,0.04);">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:5px;font-size:11px;">
                  <span style="color:#cbd5e1;font-weight:600;">${isFa ? 'سهمیه نشست جاری' : 'Session Quota'}</span>
                  <span style="color:#94a3b8;font-size:10.5px;">${escHtml(t.resetsIn)} <b style="color:#f1f5f9;" dir="ltr">${escHtml(resetsIn)}</b></span>
                </div>
                <div style="height:4px;border-radius:9999px;background:rgba(255,255,255,0.06);overflow:hidden;margin-bottom:5px;">
                  <div style="height:100%;width:${remPct}%;background:linear-gradient(90deg, #10b981, #38bdf8);border-radius:9999px;"></div>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:10px;color:#94a3b8;font-family:'JetBrains Mono',monospace;">
                  <span>${remPct}% ${isFa ? 'باقی‌مانده' : 'remaining'}</span>
                  <span>${usedPct}% ${isFa ? 'مصرف‌شده' : 'used'}</span>
                </div>
              </div>
            </div>

            <div>
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;padding:0 2px;">
                <div style="display:flex;align-items:center;gap:6px;">
                  <span style="font-size:12px;font-weight:700;color:#cbd5e1;">${escHtml(t.savedAccounts)}</span>
                  <span style="font-size:10px;padding:0 6px;border-radius:9999px;background:rgba(255,255,255,0.06);color:#94a3b8;font-family:'JetBrains Mono',monospace;">${savedCount}</span>
                </div>
                <button type="button" class="aqm-sw-btn" id="aqm-sw-toggle-add-btn" style="font-size:11px;padding:3px 9px;">
                  <span>${swShowAddPanel ? (isFa ? '✕ بستن' : '✕ Close') : (isFa ? '＋ افزودن حساب' : '＋ Add Account')}</span>
                </button>
              </div>

              ${swShowAddPanel ? `
                <div class="aqm-sw-card" style="border:1px solid rgba(59,130,246,0.25);background:rgba(59,130,246,0.03);margin-bottom:10px;padding:12px 14px;">
                  <div style="font-size:11.5px;font-weight:700;color:#93c5fd;margin-bottom:4px;">${isFa ? 'افزودن حساب جدید به آنتی‌گرویتی' : 'Add New Account'}</div>
                  <div style="font-size:10.5px;color:#94a3b8;margin-bottom:10px;line-height:1.6;">
                    ${isFa
                      ? `حساب فعال شما (<b>${escHtml(cleanDisplayName)}</b>) با امنیت کامل ذخیره است و هیچ داده‌ای پاک نمی‌شود.`
                      : `Your active account (<b>${escHtml(cleanDisplayName)}</b>) is safely saved. Choose an option:`}
                  </div>
                  <div style="display:flex;gap:8px;margin-bottom:8px;">
                    <button type="button" class="aqm-sw-btn aqm-sw-btn-primary" id="aqm-sw-add-oauth-btn" style="flex:1;padding:6px 10px;font-size:11px;">
                      <span>🔑</span>
                      <span>${isFa ? 'ورود با جیمیل جدید (گوگل)' : 'Sign In with Google'}</span>
                    </button>
                    <button type="button" class="aqm-sw-btn" id="aqm-sw-toggle-manual-token-btn" style="flex:1;padding:6px 10px;font-size:11px;">
                      <span>📋</span>
                      <span>${isFa ? 'ورود با توکن دستی' : 'Direct Token Import'}</span>
                    </button>
                  </div>
                  ${swShowTokenInput ? `
                    <div style="display:flex;flex-direction:column;gap:6px;margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.06);">
                      <textarea id="aqm-sw-token-input" placeholder="${isFa ? 'متن توکن یا JSON را اینجا جای‌گذاری کنید...' : 'Paste token or JSON payload here...'}" style="width:100%;height:52px;border-radius:8px;background:rgba(0,0,0,0.3);border:1px solid rgba(255,255,255,0.1);color:#fff;font-size:10.5px;padding:6px 8px;resize:none;font-family:'JetBrains Mono',monospace;outline:none;" dir="ltr"></textarea>
                      <div style="display:flex;justify-content:flex-end;">
                        <button type="button" class="aqm-sw-btn aqm-sw-btn-primary" id="aqm-sw-submit-token-btn" style="padding:4px 12px;font-size:11px;">
                          <span>${isFa ? 'ثبت و ذخیره توکن' : 'Save Token'}</span>
                        </button>
                      </div>
                    </div>
                  ` : ''}
                  ${swOAuthUrl ? `
                    <div id="aqm-oauth-live-box" style="margin-top:10px;padding:12px;border-radius:12px;background:rgba(59,130,246,0.1);border:1px solid rgba(59,130,246,0.3);text-align:center;">
                      <div style="font-size:12px;font-weight:700;color:#93c5fd;margin-bottom:5px;">
                        🌐 ${isFa ? 'صفحه ورود گوگل در مرورگر باز شد' : 'Google Sign-In Opened in Browser'}
                      </div>
                      <a href="${escHtml(swOAuthUrl)}" target="_blank" rel="noreferrer" class="aqm-sw-btn aqm-sw-btn-primary" style="display:inline-block;text-decoration:none;padding:7px 18px;font-size:11.5px;font-weight:700;border-radius:8px;">
                        🔗 ${isFa ? 'ورود به حساب گوگل (کلیک مستقیم)' : 'Direct Google Sign-In Link'}
                      </a>
                    </div>
                  ` : ''}
                </div>
              ` : ''}

              ${savedCount === 0 ? `
                <div class="aqm-sw-card" style="text-align:center;padding:20px 14px;border-style:dashed;">
                  <div style="font-size:11.5px;color:#94a3b8;margin-bottom:8px;">${escHtml(t.noSavedAccounts)}</div>
                  <button type="button" class="aqm-sw-btn aqm-sw-btn-primary" id="aqm-sw-save-current-empty-btn" style="padding:5px 12px;">
                    <span>${escHtml(t.saveCurrent)}</span>
                  </button>
                </div>
              ` : `
                <div style="display:flex;flex-direction:column;gap:5px;max-height:220px;overflow-y:auto;" class="aqm-custom-scroll">
                  ${savedKeys.map(k => {
                    const acc = (swState.savedAccounts && swState.savedAccounts[k]) || {};
                    const isCur = (k === email || acc.email === email);
                    const accEmailStr = acc.email || k;
                    const accShort = getCleanUserDisplayName(acc.name, accEmailStr);
                    const accInitial = accShort.charAt(0).toUpperCase();
                    const needsAuth = getAccountNeedsAuth(acc);
                    return `
                      <div class="aqm-sw-card" style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;gap:8px;${isCur ? 'border-color:rgba(16,185,129,0.3);background:rgba(16,185,129,0.03);' : ''}">
                        <div style="display:flex;align-items:center;gap:9px;min-width:0;">
                          <div style="width:28px;height:28px;border-radius:50%;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);display:flex;align-items:center;justify-content:center;font-size:11.5px;font-weight:700;flex-shrink:0;">
                            ${escHtml(accInitial)}
                          </div>
                          <div style="min-width:0;">
                            <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                              <span style="font-size:12px;font-weight:700;">${escHtml(accShort)}</span>
                              <span style="font-size:8.5px;padding:1px 5px;border-radius:9999px;background:rgba(255,255,255,0.06);color:#94a3b8;text-transform:uppercase;">${escHtml(acc.tier_code || 'PRO')}</span>
                              ${needsAuth ? `
                                <span style="font-size:8.5px;padding:1px 5px;border-radius:9999px;background:rgba(245,158,11,0.15);color:#f59e0b;border:1px solid rgba(245,158,11,0.3);">${isFa ? 'نیاز به ورود' : 'Needs Auth'}</span>
                              ` : ''}
                            </div>
                            <div style="font-size:10.5px;color:#64748b;font-family:'JetBrains Mono',monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" dir="ltr">${escHtml(accEmailStr)}</div>
                          </div>
                        </div>
                        <div style="display:flex;align-items:center;gap:5px;flex-shrink:0;">
                          ${isCur ? `
                            <span style="font-size:10.5px;color:#10b981;font-weight:700;padding:2px 8px;">${escHtml(t.activeBadge)}</span>
                          ` : needsAuth ? `
                            <button type="button" class="aqm-sw-btn aqm-sw-btn-primary" data-action="reauth" data-acc="${escHtml(k)}" data-email="${escHtml(accEmailStr)}" style="padding:3px 10px;font-size:11px;background:linear-gradient(135deg, #f59e0b, #d97706) !important;border-color:rgba(245,158,11,0.5) !important;" title="${isFa ? 'ورود به حساب گوگل' : 'Sign In with Google'}">
                              <span>🔑</span>
                              <span>${isFa ? 'ورود با گوگل' : 'Sign In'}</span>
                            </button>
                          ` : `
                            <button type="button" class="aqm-sw-btn aqm-sw-btn-primary" data-action="switch" data-acc="${escHtml(k)}" style="padding:3px 10px;font-size:11px;" title="${isFa ? 'سوئیچ فوری به این حساب' : 'Switch to this account'}">
                              <span>${escHtml(t.switchNow)}</span>
                            </button>
                            <button type="button" class="aqm-sw-btn" data-action="switch-restart" data-acc="${escHtml(k)}" style="padding:3px 8px;font-size:10.5px;color:#38bdf8;border-color:rgba(56,189,248,0.28);background:rgba(56,189,248,0.08);" title="${isFa ? 'سوئیچ و ری‌استارت کامل برنامه' : 'Switch & Restart App'}">
                              <span>🔄</span>
                            </button>
                            <button type="button" class="aqm-sw-btn" data-action="launch-dual" data-acc="${escHtml(k)}" style="padding:3px 8px;font-size:10.5px;color:#6ee7b7;border-color:rgba(16,185,129,0.28);background:rgba(16,185,129,0.08);" title="${escHtml(t.launchDualTitle)}">
                              <span>🪟</span>
                            </button>
                          `}
                          <button type="button" class="aqm-sw-btn" data-action="delete" data-acc="${escHtml(k)}" title="${escHtml(t.deleteAccount)}" style="padding:3px 7px;font-size:10.5px;color:#94a3b8;border-color:transparent;background:transparent;">
                            <span>✕</span>
                          </button>
                        </div>
                      </div>
                    `;
                  }).join('')}
                </div>
              `}
            </div>
          ` : `
            <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;padding:0 2px;">
              <span style="font-size:11px;color:#94a3b8;line-height:1.5;">${escHtml(t.projectsDesc)}</span>
              <div style="display:flex;align-items:center;gap:6px;">
                <button type="button" class="aqm-sw-btn" id="aqm-proj-allow-all-btn" style="padding:3px 9px;font-size:10.5px;">
                  🌐 ${isFa ? 'فعال‌سازی همه' : 'Allow All'}
                </button>
                <button type="button" class="aqm-sw-btn" id="aqm-proj-isolate-all-btn" style="padding:3px 9px;font-size:10.5px;">
                  🛡️ ${isFa ? 'ایزوله همه' : 'Isolate All'}
                </button>
              </div>
            </div>
            ${projectsList.length === 0 ? `
              <div class="aqm-sw-card" style="text-align:center;padding:22px 14px;border-style:dashed;color:#94a3b8;font-size:11.5px;">
                ${escHtml(t.noProjectsFound)}
              </div>
            ` : `
              <div style="display:flex;flex-direction:column;gap:8px;">
                ${projectsList.map(p => {
                  const acctKeys = savedKeys.length > 0 ? savedKeys : (email ? [email] : []);
                  const assignedSet = new Set((p.assigned_accounts || []).map(a => String(a).toLowerCase()));
                  const quotaAcc = String(p.quota_account || (p.assigned_accounts && p.assigned_accounts[0]) || '').toLowerCase();
                  const dualAcc = p.quota_account || acctKeys.find(k => k.toLowerCase() !== String(email || '').toLowerCase()) || acctKeys[0] || '';
                  return `
                    <div class="aqm-sw-card" style="padding:11px 13px;display:flex;flex-direction:column;gap:8px;">
                      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;">
                        <div style="min-width:0;flex:1;">
                          <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                            <span style="font-size:12.5px;font-weight:700;color:#f8fafc;">${escHtml(p.name || p.id)}</span>
                            <span style="font-size:9.5px;padding:1px 6px;border-radius:9999px;background:rgba(255,255,255,0.06);color:#94a3b8;font-family:'JetBrains Mono',monospace;">💬 ${Number(p.conversation_count || 0)}</span>
                          </div>
                          ${p.path ? `<div style="font-size:10px;color:#64748b;font-family:'JetBrains Mono',monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px;" dir="ltr" title="${escHtml(p.path)}">${escHtml(p.path)}</div>` : ''}
                        </div>
                        <div style="display:flex;align-items:center;gap:5px;flex-shrink:0;">
                          <button type="button" class="aqm-sw-btn aqm-proj-sync-btn" data-pid="${escHtml(p.id)}" style="padding:3px 8px;font-size:10px;" title="${escHtml(t.syncNow)}">
                            ${escHtml(t.syncNow)}
                          </button>
                          <button type="button" class="aqm-sw-btn" data-action="launch-dual" data-acc="${escHtml(dualAcc)}" data-project-path="${escHtml(p.path || '')}" style="padding:3px 8px;font-size:10px;color:#6ee7b7;border-color:rgba(16,185,129,0.3);background:rgba(16,185,129,0.08);" title="${escHtml(t.launchDualTitle)}">
                            ${escHtml(t.launchDual)}
                          </button>
                        </div>
                      </div>
                      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;padding-top:6px;border-top:1px solid rgba(255,255,255,0.05);">
                        <div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap;">
                          <span style="font-size:10px;color:#94a3b8;">${isFa ? 'دسترسی:' : 'Access:'}</span>
                          ${acctKeys.map(k => {
                            const isAssigned = assignedSet.has(k.toLowerCase());
                            const shortName = getCleanUserDisplayName(swState.savedAccounts[k]?.name, k);
                            return `<button type="button" class="aqm-sw-btn aqm-proj-acc-chip" data-pid="${escHtml(p.id)}" data-acc="${escHtml(k)}" data-assigned="${isAssigned ? 'true' : 'false'}" style="padding:2px 8px;font-size:10px;${isAssigned ? 'background:rgba(59,130,246,0.2);border-color:rgba(59,130,246,0.5);color:#93c5fd;' : 'opacity:0.65;'}">${isAssigned ? '✓ ' : ''}${escHtml(shortName)}</button>`;
                          }).join('')}
                        </div>
                        <div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap;">
                          <span style="font-size:10px;color:#94a3b8;">${isFa ? 'پرداخت سهمیه:' : 'Quota Payer:'}</span>
                          ${acctKeys.map(k => {
                            const isQ = quotaAcc === k.toLowerCase();
                            const shortName = getCleanUserDisplayName(swState.savedAccounts[k]?.name, k);
                            return `<button type="button" class="aqm-sw-btn aqm-proj-quota-chip" data-pid="${escHtml(p.id)}" data-acc="${escHtml(k)}" style="padding:2px 8px;font-size:10px;${isQ ? 'background:rgba(16,185,129,0.2);border-color:rgba(16,185,129,0.55);color:#6ee7b7;' : 'opacity:0.65;'}">${isQ ? '💳 ' : ''}${escHtml(shortName)}</button>`;
                          }).join('')}
                        </div>
                      </div>
                    </div>
                  `;
                }).join('')}
              </div>
            `}
          `}
        </div>
      </div>
    `;

    bindMismatchBannerEvents(modal);

    const closeBtn = modal.querySelector('#aqm-sw-modal-close');
    if (closeBtn) closeBtn.onclick = closeSwitcherModal;

    const langBtn = modal.querySelector('#aqm-lang-toggle-btn');
    if (langBtn) {
      langBtn.onclick = () => {
        swLang = (swLang === 'fa') ? 'en' : 'fa';
        try { localStorage.setItem('antigravity:switcher_lang', swLang); } catch (e) {}
        persistUserSettings({ lang: swLang });
        renderSwitcherModal();
        renderBadge();
        const pop = document.getElementById('antigravity-usage-popover');
        if (pop && pop.style.display !== 'none') renderPopover();
      };
    }

    const restartAppBtn = modal.querySelector('#aqm-sw-restart-app-btn');
    if (restartAppBtn) restartAppBtn.onclick = () => restartAntigravityApp();

    const autoRestartChk = modal.querySelector('#aqm-sw-autorestart-chk');
    if (autoRestartChk) {
      autoRestartChk.onchange = () => {
        swAutoRestart = Boolean(autoRestartChk.checked);
        try { localStorage.setItem('antigravity:auto_restart_on_switch', String(swAutoRestart)); } catch (e) {}
      };
    }

    const tabAcc = modal.querySelector('#aqm-tab-btn-accounts');
    if (tabAcc) tabAcc.onclick = () => { swTab = 'accounts'; renderSwitcherModal(); };

    const tabProj = modal.querySelector('#aqm-tab-btn-projects');
    if (tabProj) {
      tabProj.onclick = () => {
        swTab = 'projects';
        renderSwitcherModal();
        if (!swState.projects || swState.projects.length === 0) {
          fetch('http://127.0.0.1:39281/api/projects')
            .then(r => r.json())
            .then(list => {
              if (Array.isArray(list)) {
                swState.projects = list;
                if (swTab === 'projects') renderSwitcherModal();
              }
            }).catch(() => {});
        }
      };
    }

    const saveCurBtn = modal.querySelector('#aqm-sw-save-current-btn') || modal.querySelector('#aqm-sw-save-current-empty-btn');
    if (saveCurBtn) {
      saveCurBtn.onclick = () => {
        showSwitcherToast(isFa ? 'در حال ذخیره اکانت...' : 'Saving account...');
        if (callDaemonIpc('save')) return;
        postJson('http://127.0.0.1:39281/api/save', {})
          .then(r => r.json())
          .then(res => {
            if (res && res.success) {
              showSwitcherToast(isFa ? 'اکانت فعلی با موفقیت ذخیره شد' : 'Account saved successfully');
              fetchSwitcherState(() => { renderSwitcherModal(); });
            } else {
              showSwitcherToast((res && res.error) || (isFa ? 'خطا در ذخیره اکانت' : 'Error saving account'), true);
            }
          })
          .catch(() => { showSwitcherToast(isFa ? 'خطا در اتصال به سرویس لوکال' : 'Connection error', true); });
      };
    }

    const refreshBtn = modal.querySelector('#aqm-sw-refresh-btn');
    if (refreshBtn) {
      refreshBtn.onclick = () => {
        fetchSwitcherState(() => {
          showSwitcherToast(isFa ? 'سهمیه و اکانت‌ها بروزرسانی شد' : 'Updated');
          renderSwitcherModal();
        });
      };
    }

    const toggleAddBtn = modal.querySelector('#aqm-sw-toggle-add-btn');
    if (toggleAddBtn) {
      toggleAddBtn.onclick = () => {
        swShowAddPanel = !swShowAddPanel;
        swShowTokenInput = false;
        renderSwitcherModal();
      };
    }

    const toggleTokenBtn = modal.querySelector('#aqm-sw-toggle-manual-token-btn');
    if (toggleTokenBtn) {
      toggleTokenBtn.onclick = () => {
        swShowTokenInput = !swShowTokenInput;
        renderSwitcherModal();
      };
    }

    const submitTokenBtn = modal.querySelector('#aqm-sw-submit-token-btn');
    if (submitTokenBtn) {
      submitTokenBtn.onclick = () => {
        const input = modal.querySelector('#aqm-sw-token-input');
        const tokVal = input ? input.value.trim() : '';
        if (!tokVal) {
          showSwitcherToast(isFa ? 'لطفاً متن توکن را وارد کنید' : 'Please enter token', true);
          return;
        }
        showSwitcherToast(isFa ? 'در حال اعتبارسنجی و ثبت توکن...' : 'Importing token...');
        if (callDaemonIpc('import', { token: tokVal })) {
          swShowAddPanel = false;
          swShowTokenInput = false;
          return;
        }
        postJson('http://127.0.0.1:39281/api/import', { token: tokVal })
          .then(r => r.json())
          .then(res => {
            if (res && res.success) {
              showSwitcherToast(isFa ? `اکانت ${res.email || ''} با موفقیت افزوده شد` : 'Account imported successfully');
              swShowAddPanel = false;
              swShowTokenInput = false;
              fetchSwitcherState(() => { renderSwitcherModal(); });
            } else {
              showSwitcherToast((res && res.error) || (isFa ? 'فرمت توکن نامعتبر است' : 'Invalid token format'), true);
            }
          })
          .catch(() => { showSwitcherToast(isFa ? 'خطا در ارتباط با سرویس' : 'Service error', true); });
      };
    }

    const addOAuthBtn = modal.querySelector('#aqm-sw-add-oauth-btn');
    if (addOAuthBtn) {
      addOAuthBtn.onclick = () => {
        showSwitcherToast(isFa ? 'در حال باز کردن مرورگر برای ورود به گوگل...' : 'Opening browser for Google sign-in...');
        postJson('http://127.0.0.1:39281/api/oauth_signin', { noRestart: !swAutoRestart })
          .then(r => r.json())
          .then(res => {
            if (res && res.auth_url) {
              swOAuthUrl = res.auth_url;
              renderSwitcherModal();
              try { window.open(res.auth_url, '_blank'); } catch (e) {}
              showSwitcherToast(isFa
                ? `مرورگر باز شد. <a href="${escHtml(res.auth_url)}" target="_blank" rel="noreferrer" style="color:#93c5fd;text-decoration:underline;font-weight:700;">لینک مستقیم</a>`
                : `Browser opened. <a href="${escHtml(res.auth_url)}" target="_blank" rel="noreferrer" style="color:#93c5fd;text-decoration:underline;font-weight:700;">Direct link</a>`);
            }
          })
          .catch(() => { callDaemonIpc('oauth_signin', { noRestart: !swAutoRestart }); });
      };
    }

    modal.querySelectorAll('[data-action="reauth"]').forEach(btn => {
      btn.onclick = (e) => {
        if (e) e.stopPropagation();
        const accKey = btn.getAttribute('data-acc') || btn.getAttribute('data-email');
        showSwitcherToast(isFa ? 'در حال باز کردن صفحه ورود گوگل...' : 'Opening Google sign-in...');
        postJson('http://127.0.0.1:39281/api/oauth_signin', { accountKey: accKey, noRestart: true })
          .then(r => r.json())
          .then(res => {
            if (res && res.auth_url) {
              swOAuthUrl = res.auth_url;
              renderSwitcherModal();
              try { window.open(res.auth_url, '_blank'); } catch (err) {}
            }
          })
          .catch(() => { callDaemonIpc('oauth_signin', { accountKey: accKey, noRestart: true }); });
      };
    });

    modal.querySelectorAll('[data-action="switch"]').forEach(btn => {
      btn.onclick = () => switchAccount(btn.getAttribute('data-acc'));
    });

    modal.querySelectorAll('[data-action="switch-restart"]').forEach(btn => {
      btn.onclick = () => switchAccount(btn.getAttribute('data-acc'), true);
    });

    modal.querySelectorAll('[data-action="launch-dual"]').forEach(btn => {
      btn.onclick = (e) => {
        if (e) e.stopPropagation();
        const accKey = btn.getAttribute('data-acc') || btn.getAttribute('data-email');
        const projectPath = btn.getAttribute('data-project-path') || '';
        launchDualInstanceForAccount(accKey, projectPath, btn);
      };
    });

    modal.querySelectorAll('[data-action="delete"]').forEach(btn => {
      btn.onclick = () => {
        const accKey = btn.getAttribute('data-acc');
        const confirmMsg = isFa ? `آیا از حذف اکانت "${accKey}" از لیست مطمئن هستید؟` : `Delete account "${accKey}" from list?`;
        if (!confirm(confirmMsg)) return;
        if (callDaemonIpc('delete', { accountKey: accKey })) {
          setTimeout(() => fetchSwitcherState(() => renderSwitcherModal()), 300);
          return;
        }
        postJson('http://127.0.0.1:39281/api/delete', { accountKey: accKey, noRestart: true })
          .then(r => r.json())
          .then(res => {
            if (res && res.success) {
              showSwitcherToast(isFa ? 'اکانت از لیست حذف شد' : 'Account removed');
              fetchSwitcherState(() => { renderSwitcherModal(); });
            }
          }).catch(() => {});
      };
    });

    const allowAllBtn = modal.querySelector('#aqm-proj-allow-all-btn');
    if (allowAllBtn) {
      allowAllBtn.onclick = async () => {
        showSwitcherToast(isFa ? 'در حال فعال‌سازی تمام پروژه‌ها برای همه حساب‌ها...' : 'Enabling all projects for all accounts...');
        for (const p of projectsList) {
          if (!callDaemonIpc('toggleProjectAll', { projectId: p.id, state: 'all' })) {
            await postJson('http://127.0.0.1:39281/api/project_toggle_all', { projectId: p.id, state: 'all' }).catch(() => {});
          }
        }
        showSwitcherToast(isFa ? 'تمام پروژه‌ها برای تمام حساب‌ها فعال شدند' : 'All projects enabled for all accounts');
        applyConversationIsolationFilter();
        fetchSwitcherState(() => renderSwitcherModal());
      };
    }

    const isolateAllBtn = modal.querySelector('#aqm-proj-isolate-all-btn');
    if (isolateAllBtn) {
      isolateAllBtn.onclick = async () => {
        showSwitcherToast(isFa ? 'در حال غیرفعال‌سازی همه پروژه‌ها...' : 'Disabling all projects...');
        for (const p of projectsList) {
          if (!callDaemonIpc('toggleProjectAll', { projectId: p.id, state: 'none' })) {
            await postJson('http://127.0.0.1:39281/api/project_toggle_all', { projectId: p.id, state: 'none' }).catch(() => {});
          }
        }
        showSwitcherToast(isFa ? 'همه پروژه‌ها غیرفعال شدند' : 'All projects disabled');
        applyConversationIsolationFilter();
        fetchSwitcherState(() => renderSwitcherModal());
      };
    }

    modal.querySelectorAll('.aqm-proj-acc-chip').forEach(btn => {
      btn.onclick = () => {
        const pid = btn.getAttribute('data-pid');
        const acc = btn.getAttribute('data-acc');
        const nextState = !(btn.getAttribute('data-assigned') === 'true');
        showSwitcherToast(isFa ? `تغییر دسترسی ${acc}...` : `Updating access for ${acc}...`);
        if (callDaemonIpc('assignProject', { projectId: pid, accounts: acc, enabled: nextState })) {
          setTimeout(() => fetchSwitcherState(() => renderSwitcherModal()), 300);
          return;
        }
        postJson('http://127.0.0.1:39281/api/project_assign', { projectId: pid, accounts: acc, enabled: nextState })
          .then(r => r.json())
          .then(res => {
            if (res && res.success) {
              showSwitcherToast(isFa ? 'دسترسی پروژه به‌روزرسانی شد' : 'Project access updated');
              applyConversationIsolationFilter();
              fetchSwitcherState(() => renderSwitcherModal());
            }
          }).catch(() => { showSwitcherToast(isFa ? 'خطا در ارتباط با سرور' : 'Connection error', true); });
      };
    });

    modal.querySelectorAll('.aqm-proj-quota-chip').forEach(btn => {
      btn.onclick = () => {
        const pid = btn.getAttribute('data-pid');
        const acc = btn.getAttribute('data-acc');
        showSwitcherToast(isFa ? `تنظیم حساب کسر سهمیه به ${acc}...` : `Setting quota account to ${acc}...`);
        if (callDaemonIpc('setProjectQuotaAccount', { projectId: pid, account: acc })) {
          setTimeout(() => {
            fetchSwitcherState(() => renderSwitcherModal());
            refreshQuota();
          }, 350);
          return;
        }
        postJson('http://127.0.0.1:39281/api/project_set_quota_account', { projectId: pid, account: acc })
          .then(r => r.json())
          .then(res => {
            if (res && res.success) {
              showSwitcherToast(isFa ? `حساب کسر سهمیه به ${acc} تنظیم شد` : `Quota account updated to ${acc}`);
              fetchSwitcherState(() => renderSwitcherModal());
              refreshQuota();
            }
          }).catch(() => { showSwitcherToast(isFa ? 'خطا در ارتباط با سرور' : 'Connection error', true); });
      };
    });

    modal.querySelectorAll('.aqm-proj-sync-btn').forEach(btn => {
      btn.onclick = () => {
        const pid = btn.getAttribute('data-pid');
        showSwitcherToast(isFa ? 'در حال سینک پروژه...' : 'Syncing project...');
        postJson('http://127.0.0.1:39281/api/project_sync', { projectId: pid, targetAccount: 'instance_2' })
          .then(r => r.json())
          .then(res => {
            if (res && res.success) {
              showSwitcherToast(isFa ? 'پروژه همگام‌سازی شد' : 'Project synced');
              applyConversationIsolationFilter();
              fetchSwitcherState(() => renderSwitcherModal());
            }
          }).catch(() => { showSwitcherToast(isFa ? 'خطا در ارتباط با سرور' : 'Connection error', true); });
      };
    });
  }

  let isTaskRunning = false;

  function startActiveTaskPolling() {
    if (window.__aqm_task_interval) return;
    const accPill = document.getElementById('antigravity-account-pill');
    if (accPill) accPill.classList.add('aqm-consuming');
    refreshQuota();
    window.__aqm_task_interval = setInterval(() => {
      const stopBtn = document.querySelector('button[aria-label*="Stop"], button[data-testid*="stop"], button[title*="Stop"], .codicon-stop-circle, button[aria-label*="Cancel"]');
      if (!stopBtn) {
        stopActiveTaskPolling();
        return;
      }
      refreshQuota();
    }, 3500);
  }

  function stopActiveTaskPolling() {
    isTaskRunning = false;
    if (window.__aqm_task_interval) {
      clearInterval(window.__aqm_task_interval);
      window.__aqm_task_interval = null;
    }
    const accPill = document.getElementById('antigravity-account-pill');
    if (accPill) accPill.classList.remove('aqm-consuming');
    setTimeout(() => { refreshQuota(); }, 600);
  }

  function startDomWatcher() {
    if (window.__aqm_dom_interval) clearInterval(window.__aqm_dom_interval);
    window.__aqm_dom_interval = setInterval(() => {
      const turboBtn = document.querySelector('[data-testid="permissions-selector-trigger"]') ||
        Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.includes('Turbo'));
      const badge = document.getElementById('antigravity-usage-badge');
      const accPill = document.getElementById('antigravity-account-pill');
      const oldPill = document.getElementById('antigravity-usage-pill');
      if (oldPill) oldPill.remove();

      const shouldRelocatePill = turboBtn && accPill && accPill.nextElementSibling !== turboBtn;
      if (!badge || !accPill || shouldRelocatePill) renderBadge();

      const stopBtn = document.querySelector('button[aria-label*="Stop"], button[data-testid*="stop"], button[title*="Stop"], .codicon-stop-circle, button[aria-label*="Cancel"]');
      if (stopBtn) {
        if (!isTaskRunning) {
          isTaskRunning = true;
          startActiveTaskPolling();
        }
        if (accPill && !accPill.classList.contains('aqm-consuming')) accPill.classList.add('aqm-consuming');
      } else {
        if (isTaskRunning) {
          isTaskRunning = false;
          stopActiveTaskPolling();
        }
        if (accPill && accPill.classList.contains('aqm-consuming')) accPill.classList.remove('aqm-consuming');
      }
    }, 1200);
  }

  window.__openSwitcherModal = openSwitcherModal;
  window.__closeSwitcherModal = closeSwitcherModal;
  window.__toggleSwitcherModal = toggleSwitcherModal;
  window.__renderAntigravityBadge = renderBadge;
  window.__aqm_refresh_runtime = () => fetchStoredQuota().then(renderBadge);
  window.__refreshAntigravityQuota = refreshQuota;
  window.__openAntigravityPopover = () => {
    lastPopoverOpenTime = Date.now();
    const pop = getOrCreatePopover();
    renderPopover();
    pop.style.display = 'block';
  };
  window.__closeAntigravityPopover = () => {
    const pop = document.getElementById('antigravity-usage-popover');
    if (pop) pop.style.display = 'none';
  };
  window.__setAntigravityTheme = (themeId) => {
    if (themeId && THEMES[themeId]) {
      currentThemeId = themeId;
      try { localStorage.setItem('antigravity:quota_theme', themeId); } catch (e) {}
      persistUserSettings({ theme: themeId });
    }
    applyAppWorkspaceTheme(getActiveTheme(), false);
    renderBadge();
    renderPopover();
  };
  window.__toggleFullAppTheming = () => {
    applyAppWorkspaceTheme(getActiveTheme(), false);
    renderPopover();
  };
  window.__toggleAntigravityPrivacyMode = (enabled) => {
    isPrivacyMode = (typeof enabled === 'boolean') ? enabled : !isPrivacyMode;
    try { localStorage.setItem('antigravity:privacy_mode', String(isPrivacyMode)); } catch (e) {}
    persistUserSettings({ privacyMode: isPrivacyMode });
    renderPopover();
  };
  window.__setAntigravityFont = (en, fa) => {
    if (en) {
      const cleanEn = sanitizeFontName(en);
      if (cleanEn) { customFontEn = cleanEn; try { localStorage.setItem('antigravity:custom_font_en', cleanEn); } catch (e) {} }
    }
    if (fa) {
      const cleanFa = sanitizeFontName(fa);
      if (cleanFa) { customFontFa = cleanFa; try { localStorage.setItem('antigravity:custom_font_fa', cleanFa); } catch (e) {} }
    }
    persistUserSettings({ fontEn: customFontEn, fontFa: customFontFa });
    ensureFontLoaded(customFontEn);
    ensureFontLoaded(customFontFa);
    applyAppWorkspaceTheme(getActiveTheme(), isFullAppThemingEnabled);
    renderBadge();
    renderPopover();
  };
  window.__importAntigravityFont = (name, url = '', type = 'fa') => {
    const cleanName = sanitizeFontName(name);
    if (!cleanName) return;
    const cleanUrl = sanitizeFontUrl(url);
    const fType = (type === 'en') ? 'en' : 'fa';
    const existingIdx = customImportedFonts.findIndex(f => f.id.toLowerCase() === cleanName.toLowerCase());
    if (existingIdx >= 0) {
      customImportedFonts[existingIdx] = { id: cleanName, name: cleanName, url: cleanUrl, type: fType };
    } else {
      customImportedFonts.push({ id: cleanName, name: cleanName, url: cleanUrl, type: fType });
    }
    try { localStorage.setItem('antigravity:custom_imported_fonts', JSON.stringify(customImportedFonts)); } catch (e) {}
    if (cleanUrl) injectImportedFontStyles();
    if (fType === 'fa') {
      customFontFa = cleanName;
      try { localStorage.setItem('antigravity:custom_font_fa', cleanName); } catch (e) {}
    } else {
      customFontEn = cleanName;
      try { localStorage.setItem('antigravity:custom_font_en', cleanName); } catch (e) {}
    }
    persistUserSettings({ customImportedFonts, fontEn: customFontEn, fontFa: customFontFa });
    ensureFontLoaded(cleanName);
    applyAppWorkspaceTheme(getActiveTheme(), false);
    renderBadge();
    renderPopover();
  };

  window.updateDir = updateDir;
  window.openSwitcherModal = openSwitcherModal;
  window.closeSwitcherModal = closeSwitcherModal;
  window.renderSwitcherModal = renderSwitcherModal;
  window.setRTLActive = (active) => {
    rtlConfig.isRTL = !!active;
    saveRtlConfig();
    syncRtlRuntime();
    renderPopover();
  };
  window.__toggleAntigravityRTL = () => {
    rtlConfig.isRTL = !rtlConfig.isRTL;
    saveRtlConfig();
    syncRtlRuntime();
    renderPopover();
  };
  window.__setAntigravityRtlConfig = (cfg) => {
    if (typeof cfg === 'object' && cfg !== null) {
      rtlConfig = { ...rtlConfig, ...cfg };
      saveRtlConfig();
      syncRtlRuntime();
      renderPopover();
    }
  };

  setTimeout(() => { fetchSwitcherState(); }, 1000);
  startDomWatcher();
  applyAppWorkspaceTheme(getActiveTheme(), isFullAppThemingEnabled);
  syncRtlRuntime();
  ['Outfit', 'Estedad', 'Vazirmatn', customFontEn, customFontFa].forEach(ensureFontLoaded);
  applyConversationIsolationFilter();
  try {
    if (document.body) {
      window.__aqm_iso_timeout = null;
      window.__aqm_iso_observer = new MutationObserver(() => {
        if (!isInstance2Window()) return;
        if (window.__aqm_iso_timeout) return;
        window.__aqm_iso_timeout = setTimeout(() => {
          window.__aqm_iso_timeout = null;
          applyConversationIsolationFilter();
        }, 150);
      });
      window.__aqm_iso_observer.observe(document.body, { childList: true, subtree: true });
    }
    window.__aqm_iso_interval = setInterval(() => {
      if (isInstance2Window()) applyConversationIsolationFilter();
    }, 2000);
  } catch (e) {}
  fetchStoredQuota().then(() => {
    renderBadge();
    refreshQuota();
    applyConversationIsolationFilter();
  });
  renderBadge();
  window.__aqm_runtime_revision = runtimeRevision;
  window.__aqm_runtime_settings = runtimeSettings;
  window.__aqm_runtime_account = runtimeAccount;
