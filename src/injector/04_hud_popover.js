  let lastPopoverOpenTime = 0;

  function getOrCreatePopover() {
    let pop = document.getElementById('antigravity-usage-popover');
    if (!pop) {
      pop = document.createElement('div');
      pop.id = 'antigravity-usage-popover';
      pop.style.position = 'fixed';
      pop.style.zIndex = '999999';
      pop.style.width = '445px';
      pop.style.boxSizing = 'border-box';
      pop.style.padding = '18px 20px';
      pop.style.borderRadius = '24px';
      pop.style.backdropFilter = 'blur(32px) saturate(210%)';
      pop.style.webkitBackdropFilter = 'blur(32px) saturate(210%)';
      pop.style.animation = 'aqm-pop-in 0.2s cubic-bezier(0.16, 1, 0.3, 1)';
      pop.style.display = 'none';

      pop.addEventListener('click', (e) => e.stopPropagation());
      pop.addEventListener('mousedown', (e) => e.stopPropagation());
      pop.addEventListener('pointerdown', (e) => e.stopPropagation());

      (document.body || document.documentElement).appendChild(pop);
    }

    if (!window.__aqm_click_bound) {
      window.__aqm_click_bound = true;
      onGlobal(document, 'click', (e) => {
        const p = document.getElementById('antigravity-usage-popover');
        const ap = document.getElementById('antigravity-account-pill');
        if (p && p.style.display !== 'none') {
          if (Date.now() - lastPopoverOpenTime < 250) return;
          if (!p.contains(e.target) && (!ap || !ap.contains(e.target))) {
            p.style.display = 'none';
          }
        }
      });
    }
    return pop;
  }

  function renderPopover() {
    const turboBtn = document.querySelector('[data-testid="permissions-selector-trigger"]') ||
      Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.includes('Turbo'));
    const trigger = document.querySelector('[data-testid="model-selector-trigger"]');
    const anchor = document.getElementById('antigravity-account-pill') || turboBtn || trigger || document.getElementById('antigravity-quota-dock');
    let customPos = null;
    try {
      customPos = JSON.parse(localStorage.getItem('antigravity:popover_pos') || 'null');
    } catch (e) {}
    if (!anchor && !customPos) return;

    const theme = getActiveTheme();
    const { fontEn, fontFa, fullFamily } = getEffectiveFonts(theme);
    applyAppWorkspaceTheme(theme, isFullAppThemingEnabled);

    const pop = getOrCreatePopover();
    pop.style.background = theme.cardBg;
    pop.style.border = `1px solid ${theme.cardBorder}`;
    pop.style.boxShadow = theme.cardShadow;
    pop.style.color = theme.textColor;
    pop.style.fontFamily = fullFamily;

    const rect = anchor ? anchor.getBoundingClientRect() : { left: 24, top: window.innerHeight - 80, bottom: window.innerHeight - 40 };
    const popWidth = 445;
    const popHeight = 470;

    if (customPos && customPos.left !== undefined && customPos.top !== undefined) {
      let l = parseFloat(customPos.left);
      let t = parseFloat(customPos.top);
      l = Math.min(Math.max(12, l), Math.max(12, window.innerWidth - popWidth - 12));
      t = Math.min(Math.max(12, t), Math.max(12, window.innerHeight - popHeight - 12));
      pop.style.left = l + 'px';
      pop.style.top = t + 'px';
      pop.style.bottom = 'auto';
    } else {
      let desiredLeft = Math.max(12, rect.left - 20);
      if (desiredLeft + popWidth > window.innerWidth - 12) {
        desiredLeft = Math.max(12, window.innerWidth - popWidth - 12);
      }
      let desiredTop = rect.top - popHeight - 14;
      if (desiredTop < 12) {
        desiredTop = (rect.bottom + 14 + popHeight <= window.innerHeight - 12) ? (rect.bottom + 14) : 12;
      }
      pop.style.left = desiredLeft + 'px';
      pop.style.top = desiredTop + 'px';
      pop.style.bottom = 'auto';
    }
    pop.style.overflow = 'visible';

    try {
      const p = localStorage.getItem('antigravity:privacy_mode');
      if (p !== null) isPrivacyMode = (p !== 'false');
    } catch (e) {}

    const isFa = swLang !== 'en';
    const uiDir = isFa ? 'rtl' : 'ltr';
    const uiFont = isFa ? fontFa : fontEn;

    const isRem = (displayMode === 'remaining');
    const sessRem = Math.round(currentUsage.session?.remaining_pct ?? (100 - Math.round(currentUsage.session?.used_pct ?? 0)));
    const sessUsed = Math.round(currentUsage.session?.used_pct ?? (100 - sessRem));
    const sessReset = currentUsage.session?.resets_in || 'Ready';
    const sessResetTime = currentUsage.session?.reset_time || '';

    const mainPct = isRem ? sessRem : sessUsed;
    const subPct = isRem ? sessUsed : sessRem;
    const mainLabel = isFa ? (isRem ? 'مانده' : 'مصرف') : (isRem ? 'Left' : 'Used');
    const subLabel = isFa ? (isRem ? 'مصرف' : 'مانده') : (isRem ? 'Used' : 'Left');

    const weeklyRem = Math.round(currentUsage.weekly?.remaining_pct ?? (100 - Math.round(currentUsage.weekly?.used_pct ?? 0)));
    const weeklyUsed = Math.round(currentUsage.weekly?.used_pct ?? (100 - weeklyRem));
    const weeklyShow = isRem ? weeklyRem : weeklyUsed;

    const activeModel = getActiveModelName();
    const rawPools = Array.isArray(currentUsage.pools) ? currentUsage.pools : [];
    const pools = (rawPools.length > 0 ? rawPools : [
      { name: 'Gemini 4 Hydrogen', used_pct: sessUsed, remaining_pct: sessRem, weekly_rem: weeklyRem, weekly_pct: weeklyUsed, resets_in: sessReset },
      { name: 'Gemini 4 Argon', used_pct: sessUsed, remaining_pct: sessRem, weekly_rem: weeklyRem, weekly_pct: weeklyUsed, resets_in: sessReset },
      { name: 'Gemini 4 Carbon & Orchestrator', used_pct: sessUsed, remaining_pct: sessRem, weekly_rem: weeklyRem, weekly_pct: weeklyUsed, resets_in: sessReset },
      { name: 'Gemini 3.8 Flash', used_pct: sessUsed, remaining_pct: sessRem, weekly_rem: weeklyRem, weekly_pct: weeklyUsed, resets_in: sessReset },
      { name: 'Claude 4.6 (Opus & Sonnet)', used_pct: 0, remaining_pct: 100, weekly_rem: 100, weekly_pct: 0, resets_in: 'Ready' },
      { name: 'GPT-OSS 120B', used_pct: 0, remaining_pct: 100, weekly_rem: 100, weekly_pct: 0, resets_in: 'Ready' }
    ]).map(p => {
      const displayPoolName = mapRawPoolName(p.name || 'Model Pool');
      return {
        name: p.name || displayPoolName,
        svg: getPoolIconSvg(displayPoolName),
        isActive: isPoolActiveForModel(displayPoolName, activeModel),
        used_pct: p.used_pct,
        remaining_pct: p.remaining_pct,
        weekly_rem: p.weekly_rem !== undefined ? p.weekly_rem : weeklyRem,
        weekly_pct: p.weekly_pct !== undefined ? p.weekly_pct : weeklyUsed,
        resets_in: p.resets_in || sessReset
      };
    });

    let poolsHtml = '';
    for (const p of pools) {
      const pRem = Math.round(p.remaining_pct ?? (100 - (p.used_pct || 0)));
      const pUsed = Math.round(p.used_pct ?? (100 - pRem));
      const pWeekRem = Math.round(p.weekly_rem ?? (100 - (p.weekly_pct || 0)));
      const pWeekUsed = Math.round(p.weekly_pct ?? (100 - pWeekRem));
      const r = p.resets_in || 'Ready';
      const showVal = isRem ? pRem : pUsed;
      const showWeek = isRem ? pWeekRem : pWeekUsed;
      const statusColor = showVal > 35 ? theme.accent : (showVal > 15 ? '#fbbf24' : '#f43f5e');

      poolsHtml += `
        <div class="aqm-model-row" style="height:36px;box-sizing:border-box;display:grid;grid-template-columns:minmax(0, 1fr) 88px 64px;align-items:center;gap:10px;padding:0 12px;border-radius:11px;background:${p.isActive ? (theme.isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.05)') : theme.itemBg};border:1px solid ${p.isActive ? theme.itemHoverBorder : theme.itemBorder};font-size:12px;direction:ltr;">
          <div style="display:flex;align-items:center;gap:8px;min-width:0;overflow:hidden;">
            <div style="width:20px;height:20px;border-radius:6px;background:rgba(255,255,255,0.06);display:flex;align-items:center;justify-content:center;flex-shrink:0;">
              ${p.svg}
            </div>
            <span data-font="en" style="font-weight:600;color:${theme.textColor};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;letter-spacing:-0.01em;font-size:11.8px;font-family:${fontEn};" title="${escHtml(p.name)}">${escHtml(p.name)}</span>
            ${p.isActive ? `<span style="width:6px;height:6px;border-radius:50%;background:${theme.dotColor};box-shadow:0 0 6px ${theme.dotColor};flex-shrink:0;animation:aqm-pulse-dot 2s infinite ease-in-out;" title="${isFa ? 'مدل انتخاب‌شده فعلی' : 'Active Model'}"></span>` : ''}
          </div>
          <div style="display:flex;flex-direction:column;gap:3px;align-items:flex-end;">
            <div style="display:flex;align-items:center;gap:4px;font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;color:${statusColor};" data-font="mono">
              <span dir="ltr">${showVal}%</span>
              <span data-font="en" style="font-family:${fontEn};font-size:9px;color:${theme.subText};font-weight:500;opacity:0.8;">(${escHtml(r)})</span>
            </div>
            <div style="width:100%;height:3px;border-radius:9999px;background:rgba(255,255,255,0.08);overflow:hidden;">
              <div style="height:100%;width:${showVal}%;border-radius:9999px;background:${theme.accentGrad};"></div>
            </div>
          </div>
          <div style="display:flex;flex-direction:column;gap:3px;align-items:flex-end;">
            <div style="display:flex;align-items:center;gap:3px;font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:600;color:${theme.chipColor};" data-font="mono">
              <span style="font-size:8.5px;color:${theme.subText};font-weight:500;">W:</span>
              <span dir="ltr">${showWeek}%</span>
            </div>
            <div style="width:100%;height:2.5px;border-radius:9999px;background:rgba(255,255,255,0.06);overflow:hidden;">
              <div style="height:100%;width:${showWeek}%;border-radius:9999px;background:${theme.accentSecondary || theme.accent};"></div>
            </div>
          </div>
        </div>
      `;
    }

    const BUILTIN_FONTS_EN = [
      { id: 'default', label: isFa ? 'پیش‌فرض' : 'Default' },
      { id: 'Fredoka', label: 'Fredoka' },
      { id: 'Outfit', label: 'Outfit' },
      { id: 'Space Grotesk', label: 'Space' },
      { id: 'JetBrains Mono', label: 'Mono' },
      { id: 'Inter', label: 'Inter' },
      { id: 'Plus Jakarta Sans', label: 'Jakarta' }
    ];
    const BUILTIN_FONTS_FA = [
      { id: 'default', label: isFa ? 'پیش‌فرض' : 'Default' },
      { id: 'Vazirmatn', label: isFa ? 'وزیرمتن' : 'Vazirmatn' },
      { id: 'Estedad', label: isFa ? 'استعداد' : 'Estedad' },
      { id: 'Sahel', label: isFa ? 'ساحل' : 'Sahel' },
      { id: 'Shabnam', label: isFa ? 'شبنم' : 'Shabnam' },
      { id: 'Samim', label: isFa ? 'صمیم' : 'Samim' },
      { id: 'Lalezar', label: isFa ? 'لاله‌زار' : 'Lalezar' },
      { id: 'Noto Sans Arabic', label: isFa ? 'نوتو عربی' : 'Noto Arabic' },
      { id: 'IRANSansX', label: isFa ? 'ایران‌سنس' : 'IRANSansX' },
      { id: 'B Yekan', label: isFa ? 'یکان' : 'Yekan' }
    ];

    const importedEn = customImportedFonts.filter(f => f.type === 'en');
    const importedFa = customImportedFonts.filter(f => f.type === 'fa');

    const { accEmail, accName, accAvatar, accTierCode, initialChar, tierBadgeBg, tierBadgeColor, tierBadgeBorder } = getActiveAccountInfo();
    const displayEmail = isPrivacyMode ? '••••••••••••@gmail.com' : (accEmail || 'user@example.com');

    let quickSwitchChipsHtml = '';
    if (swState.savedAccounts) {
      const otherAccounts = Object.keys(swState.savedAccounts).filter(k => k.toLowerCase() !== (accEmail || '').toLowerCase());
      if (otherAccounts.length > 0) {
        quickSwitchChipsHtml = otherAccounts.map(k => {
          const acc = swState.savedAccounts[k] || {};
          const shortName = acc.name || k.split('@')[0];
          return `<button type="button" data-switch-quick="${escHtml(k)}" title="${escHtml(isFa ? `سوئیچ آنی به ${k}` : `Quick switch to ${k}`)}" style="display:inline-flex;align-items:center;gap:4px;padding:2px 7px;border-radius:6px;background:rgba(255,255,255,0.06);border:1px solid ${theme.itemBorder};color:${theme.textColor};font-size:9px;font-weight:600;cursor:pointer;white-space:nowrap;transition:background-color 0.15s ease,border-color 0.15s ease;">
            <span style="color:#fbbf24;font-size:9px;">⚡️</span>
            <span dir="ltr">${escHtml(shortName)}</span>
          </button>`;
        }).join('');
      } else {
        quickSwitchChipsHtml = `<span style="font-size:9px;color:${theme.subText};opacity:0.75;font-family:${uiFont};">${isFa ? 'تنها ۱ حساب ذخیره است' : 'Only 1 saved account'}</span>`;
      }
    }

    const mismatchBannerHtml = renderMismatchBannerHtml(getSessionMismatchInfo(accEmail), isFa, uiDir, uiFont);

    pop.innerHTML = `
      <div id="aqm-drag-handle" style="display:flex;justify-content:space-between;align-items:center;direction:ltr;cursor:grab;user-select:none;padding-bottom:8px;border-bottom:1px solid ${theme.itemBorder};" title="${isFa ? 'جهت جابه‌جایی پنجره بکشید (دوبار کلیک برای بازنشانی موقعیت)' : 'Drag to move window (double-click to reset position)'}">
        <div style="display:flex;align-items:center;gap:9px;">
          <div style="position:relative;width:32px;height:32px;border-radius:50%;overflow:hidden;border:1.5px solid ${theme.cardBorder};background:${theme.chipBg};display:flex;align-items:center;justify-content:center;box-shadow:inset 0 1px 1px rgba(255,255,255,0.2);">
            ${accAvatar ? `<img src="${escHtml(accAvatar)}" style="width:100%;height:100%;object-fit:cover;" onerror="this.style.display='none';if(this.nextElementSibling)this.nextElementSibling.style.display='flex';" />` : ''}
            <span style="${accAvatar ? 'display:none;' : 'display:flex;'}width:100%;height:100%;align-items:center;justify-content:center;font-weight:800;font-size:12px;color:#fff;background:linear-gradient(135deg, #3b82f6, #8b5cf6);">${escHtml(initialChar)}</span>
            <span style="position:absolute;bottom:0;right:0;width:7px;height:7px;border-radius:50%;background:#10b981;border:1.5px solid #0f172a;box-shadow:0 0 6px #10b981;"></span>
          </div>
          <div>
            <div style="display:flex;align-items:center;gap:5px;">
              <span data-font="en" style="font-weight:700;font-size:13px;letter-spacing:-0.02em;color:${theme.textColor};font-family:${fontEn};">${escHtml(accName)}</span>
              <span style="font-size:8.5px;font-weight:800;padding:1px 5px;border-radius:9999px;background:${tierBadgeBg};color:${tierBadgeColor};border:1px solid ${tierBadgeBorder};text-transform:uppercase;">${escHtml(accTierCode.toUpperCase())}</span>
            </div>
            <div style="display:flex;align-items:center;gap:5px;margin-top:0.5px;">
              <span data-font="en" style="font-size:10px;color:${theme.subText};opacity:0.85;font-family:${fontEn};">${escHtml(displayEmail)}</span>
              <button id="aqm-privacy-btn" type="button" title="${isPrivacyMode ? (isFa ? 'نمایش ایمیل' : 'Show Email') : (isFa ? 'مخفی‌سازی ایمیل' : 'Hide Email')}" style="background:none;border:none;cursor:pointer;font-size:9.5px;padding:0;line-height:1;color:${theme.subText};opacity:0.75;">
                ${isPrivacyMode ? '🔒' : '👁'}
              </button>
            </div>
          </div>
        </div>

        <div style="display:flex;align-items:center;gap:5px;">
          <button id="aqm-pop-lang-btn" type="button" title="${isFa ? 'تغییر زبان به انگلیسی (EN)' : 'Switch Language to Persian (فا)'}" style="display:flex;align-items:center;justify-content:center;height:24px;padding:0 7px;border-radius:9999px;background:${theme.itemBg};border:1px solid ${theme.itemBorder};color:${theme.textColor};font-size:9.5px;font-weight:700;cursor:pointer;">
            ${isFa ? 'EN' : 'فا'}
          </button>
          <button id="aqm-pop-restart-btn" type="button" title="${isFa ? 'ری‌استارت برنامه Antigravity' : 'Restart Antigravity App'}" style="display:flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:${theme.itemBg};border:1px solid ${theme.itemBorder};color:#38bdf8;font-size:11px;cursor:pointer;">
            🔄
          </button>
          <button id="aqm-refresh-btn" type="button" title="${isFa ? 'همگام‌سازی لحظه‌ای سهمیه' : 'Refresh Live Quota'}" style="display:flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:${theme.itemBg};border:1px solid ${theme.itemBorder};color:${theme.accent};cursor:pointer;">
            <span class="${isRefreshing ? 'aqm-rotating' : ''}">${SVGS.refresh}</span>
          </button>
          <button id="aqm-close-btn" type="button" title="${isFa ? 'بستن پنجره' : 'Close'}" style="display:flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:${theme.itemBg};border:1px solid ${theme.itemBorder};color:${theme.subText};font-size:10.5px;cursor:pointer;">
            ✕
          </button>
        </div>
      </div>

      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;padding:6px 0;border-bottom:1px solid ${theme.itemBorder};direction:${uiDir};">
        <div style="display:flex;align-items:center;gap:5px;overflow-x:auto;max-width:300px;" class="aqm-custom-scroll">
          <span style="font-size:9.5px;color:${theme.subText};font-weight:600;white-space:nowrap;font-family:${uiFont};">${isFa ? 'سوئیچ سریع:' : 'Quick Switch:'}</span>
          ${quickSwitchChipsHtml}
        </div>
        <button id="aqm-account-switcher-trigger" type="button" title="${isFa ? 'مدیریت کامل حساب‌ها' : 'Manage Accounts'}" style="display:inline-flex;align-items:center;gap:4px;padding:2.5px 8px;border-radius:7px;background:${theme.itemBg};border:1px solid ${theme.itemBorder};color:${theme.accent};font-size:9.5px;font-weight:700;cursor:pointer;white-space:nowrap;font-family:${uiFont};">
          <span>${isFa ? '⚡️ مدیریت حساب‌ها' : '⚡️ Accounts'}</span>
        </button>
      </div>

      <div style="display:flex;padding:2px;border-radius:10px;background:rgba(0,0,0,0.28);border:1px solid ${theme.itemBorder};margin:8px 0 9px 0;direction:${uiDir};">
        <button id="aqm-tab-btn-quota" type="button" style="flex:1;padding:4px 0;border:none;border-radius:7px;background:${activePopoverTab === 'quota' ? theme.accentGrad : 'transparent'};color:${activePopoverTab === 'quota' ? '#080d16' : theme.subText};font-size:10.5px;font-weight:700;cursor:pointer;font-family:${uiFont};display:flex;align-items:center;justify-content:center;gap:4px;">
          <span>📊</span><span>${isFa ? 'سهمیه و مدل‌ها' : 'Quota & Models'}</span>
        </button>
        <button id="aqm-tab-btn-fonts" type="button" style="flex:1;padding:4px 0;border:none;border-radius:7px;background:${activePopoverTab === 'fonts' ? theme.accentGrad : 'transparent'};color:${activePopoverTab === 'fonts' ? '#080d16' : theme.subText};font-size:10.5px;font-weight:700;cursor:pointer;font-family:${uiFont};display:flex;align-items:center;justify-content:center;gap:4px;">
          <span>🔤</span><span>${isFa ? 'فونت و تایپوگرافی' : 'Typography'}</span>
        </button>
        <button id="aqm-tab-btn-rtl" type="button" style="flex:1;padding:4px 0;border:none;border-radius:7px;background:${activePopoverTab === 'rtl' ? theme.accentGrad : 'transparent'};color:${activePopoverTab === 'rtl' ? '#080d16' : theme.subText};font-size:10.5px;font-weight:700;cursor:pointer;font-family:${uiFont};display:flex;align-items:center;justify-content:center;gap:4px;">
          <span>✍️</span><span>${isFa ? 'راست‌چین هوشمند' : 'Smart RTL'}</span>
        </button>
      </div>

      <div style="max-height:360px;overflow-y:auto;padding-right:2px;" class="aqm-custom-scroll">
        <div id="aqm-tab-content-quota" style="display:${activePopoverTab === 'quota' ? 'block' : 'none'};">
          ${mismatchBannerHtml}
          <div style="display:flex;justify-content:flex-end;margin-bottom:6px;">
            <div style="display:flex;padding:2px;border-radius:9999px;background:rgba(0,0,0,0.25);border:1px solid ${theme.itemBorder};">
              <button id="aqm-mode-rem-btn" type="button" style="background:${isRem ? theme.accentGrad : 'transparent'};color:${isRem ? '#0b111e' : theme.subText};border:none;padding:2px 7px;border-radius:9999px;font-size:9.5px;font-weight:700;cursor:pointer;font-family:${uiFont};">${isFa ? 'مانده' : 'Remaining'}</button>
              <button id="aqm-mode-used-btn" type="button" style="background:${!isRem ? theme.accentGrad : 'transparent'};color:${!isRem ? '#0b111e' : theme.subText};border:none;padding:2px 7px;border-radius:9999px;font-size:9.5px;font-weight:700;cursor:pointer;font-family:${uiFont};">${isFa ? 'مصرف' : 'Used'}</button>
            </div>
          </div>

          <div style="margin-top:8px;padding:14px 16px;border-radius:16px;background:${theme.itemBg};border:1px solid ${theme.itemBorder};box-shadow:inset 0 1px 1px rgba(255,255,255,0.08);">
            <div style="display:flex;justify-content:space-between;align-items:center;direction:ltr;">
              <div>
                <div data-font="en" style="font-size:11px;color:${theme.subText};font-weight:600;letter-spacing:0.04em;text-transform:uppercase;font-family:${fontEn};">
                  ${isFa ? 'سهمیه نشست ۵ ساعته' : '5-Hour Session Quota'}
                </div>
                <div style="display:flex;align-items:center;gap:5px;font-size:10.5px;color:${theme.subText};margin-top:3px;font-family:${uiFont};">
                  <span>${isFa ? 'بازنشانی در' : 'Resets at'}</span>
                  <span style="font-weight:700;color:${theme.textColor};font-family:'JetBrains Mono',monospace;" data-font="mono" dir="ltr">${escHtml(sessResetTime)}</span>
                  <span style="opacity:0.4;">•</span>
                  <span style="color:${theme.accent};font-weight:600;">${escHtml(sessReset)} ${isFa ? 'مانده' : 'left'}</span>
                </div>
              </div>
              <div style="text-align:right;direction:${uiDir};">
                <div style="display:flex;align-items:baseline;gap:5px;justify-content:flex-end;">
                  <span style="font-family:'JetBrains Mono',monospace;font-size:26px;font-weight:800;color:${theme.accent};letter-spacing:-0.03em;text-shadow:${theme.accentGlow};line-height:1;" data-font="mono" dir="ltr">${mainPct}%</span>
                  <span style="font-size:11.5px;color:${theme.subText};font-weight:600;font-family:${uiFont};">${mainLabel}</span>
                </div>
                <div style="font-size:10px;color:${theme.subText};margin-top:2px;font-family:${uiFont};">
                  ${subLabel}: <strong style="color:${theme.textColor};font-family:'JetBrains Mono',monospace;" data-font="mono" dir="ltr">${subPct}%</strong>
                </div>
              </div>
            </div>
            <div style="margin-top:11px;height:6px;border-radius:9999px;background:rgba(255,255,255,0.08);overflow:hidden;">
              <div style="height:100%;width:${mainPct}%;background:${theme.accentGrad};border-radius:9999px;box-shadow:${theme.accentGlow};"></div>
            </div>
            <div style="margin-top:10px;padding-top:8px;border-top:1px solid ${theme.itemBorder};display:flex;justify-content:space-between;align-items:center;direction:ltr;">
              <div style="display:flex;align-items:center;gap:6px;font-size:10.5px;color:${theme.subText};font-family:${uiFont};">
                <span style="font-weight:600;color:${theme.textColor};">${isFa ? 'سهمیه هفتگی:' : 'Weekly Quota:'}</span>
                <span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:${theme.chipColor};" data-font="mono" dir="ltr">${weeklyShow}%</span>
                <span>${mainLabel}</span>
                <span style="opacity:0.5;">(${escHtml(currentUsage.weekly?.resets_in || 'Ready')})</span>
              </div>
              <div style="width:80px;height:3.5px;border-radius:9999px;background:rgba(255,255,255,0.08);overflow:hidden;">
                <div style="height:100%;width:${weeklyShow}%;background:${theme.accentSecondary || theme.accent};border-radius:9999px;"></div>
              </div>
            </div>
          </div>

          <div data-font="en" style="display:flex;justify-content:space-between;align-items:center;margin-top:14px;margin-bottom:7px;padding:0 4px;font-size:10px;font-weight:700;letter-spacing:0.06em;color:${theme.subText};direction:ltr;font-family:${fontEn};">
            <span>${isFa ? 'استخر مدل‌های فعال (ACTIVE POOLS)' : 'ACTIVE MODEL POOLS'}</span>
            <span>${isFa ? 'نشست • هفتگی' : 'SESSION • WEEKLY'}</span>
          </div>
          <div style="display:flex;flex-direction:column;gap:5px;">
            ${poolsHtml}
          </div>
          <div style="margin-top:13px;border-top:1px solid ${theme.itemBorder};"></div>
        </div>

        <div id="aqm-tab-content-fonts" style="display:${activePopoverTab === 'fonts' ? 'block' : 'none'};direction:${uiDir};">
          <div style="margin:9px 0 7px 0;border-top:1px solid ${theme.itemBorder};padding-top:7px;">
            <div style="font-size:11px;font-weight:800;color:${theme.textColor};margin-bottom:6px;padding:0 2px;display:flex;justify-content:space-between;align-items:center;font-family:${uiFont};">
              <span>${isFa ? 'تایپوگرافی و فونت' : 'Typography & Fonts'}</span>
              <span data-font="en" style="font-size:8.5px;color:${theme.accent};font-family:${fontEn};">Persian & English</span>
            </div>

            <div id="aqm-theme-dropdown" style="display:flex;align-items:center;justify-content:space-between;gap:6px;margin-bottom:7px;padding:5px 7px;border-radius:8px;background:rgba(255,255,255,0.03);border:1px solid ${theme.itemBorder};">
              <span style="font-size:9.5px;color:${theme.subText};font-family:${uiFont};">${isFa ? 'پوسته کارت HUD:' : 'HUD Card Surface:'}</span>
              <div style="display:flex;gap:4px;">
                ${Object.values(THEMES).map(th => `
                  <button type="button" data-theme-id="${th.id}" style="background:${currentThemeId === th.id ? theme.accentGrad : 'rgba(255,255,255,0.06)'};color:${currentThemeId === th.id ? '#080d16' : theme.textColor};border:1px solid ${currentThemeId === th.id ? theme.cardBorder : 'rgba(255,255,255,0.08)'};padding:2px 7px;border-radius:6px;font-size:9px;font-weight:700;cursor:pointer;font-family:${uiFont};">
                    ${isFa ? th.nameFa : th.nameEn}
                  </button>
                `).join('')}
              </div>
            </div>

            <div style="margin-bottom:7px;">
              <div style="font-size:9.5px;color:${theme.subText};margin-bottom:3px;font-family:${uiFont};">${isFa ? 'فونت انگلیسی و کد:' : 'English & Code Font:'}</div>
              <div style="display:flex;gap:3px;flex-wrap:wrap;">
                ${BUILTIN_FONTS_EN.map(item => `
                  <button type="button" data-font-en="${item.id}" style="background:${customFontEn === item.id ? theme.accentGrad : 'rgba(255,255,255,0.06)'};color:${customFontEn === item.id ? '#080d16' : theme.textColor};border:1px solid ${customFontEn === item.id ? theme.cardBorder : 'rgba(255,255,255,0.08)'};padding:2px 6px;border-radius:6px;font-size:9px;font-weight:700;cursor:pointer;font-family:${item.id === 'default' ? uiFont : `'${item.id}', sans-serif`};">
                    ${escHtml(item.label)}
                  </button>
                `).join('')}
                ${importedEn.map(item => `
                  <div style="display:inline-flex;align-items:center;background:${customFontEn === item.id ? theme.accentGrad : 'rgba(255,255,255,0.06)'};border:1px solid ${customFontEn === item.id ? theme.cardBorder : 'rgba(255,255,255,0.08)'};border-radius:6px;padding:2px 3px 2px 6px;gap:3px;">
                    <button type="button" data-font-en="${escHtml(item.id)}" style="background:none;border:none;color:${customFontEn === item.id ? '#080d16' : theme.textColor};font-size:9px;font-weight:700;cursor:pointer;padding:0;font-family:'${escHtml(item.id)}', sans-serif;">
                      ${item.data ? '📁 ' : ''}${escHtml(item.name)}
                    </button>
                    <button type="button" data-delete-imported-font="${escHtml(item.id)}" title="${isFa ? 'حذف فونت' : 'Remove font'}" style="background:none;border:none;color:${customFontEn === item.id ? '#080d16' : theme.subText};cursor:pointer;font-size:9.5px;padding:0 1px;line-height:1;opacity:0.75;">✕</button>
                  </div>
                `).join('')}
              </div>
            </div>

            <div>
              <div style="font-size:9.5px;color:${theme.subText};margin-bottom:3px;font-family:${uiFont};">${isFa ? 'فونت فارسی و توضیحات:' : 'Persian & RTL Font:'}</div>
              <div style="display:flex;gap:3px;flex-wrap:wrap;">
                ${BUILTIN_FONTS_FA.map(item => `
                  <button type="button" data-font-fa="${item.id}" style="background:${customFontFa === item.id ? theme.accentGrad : 'rgba(255,255,255,0.06)'};color:${customFontFa === item.id ? '#080d16' : theme.textColor};border:1px solid ${customFontFa === item.id ? theme.cardBorder : 'rgba(255,255,255,0.08)'};padding:2px 7px;border-radius:6px;font-size:9.5px;font-weight:700;cursor:pointer;font-family:${item.id === 'default' ? uiFont : `'${item.id}', sans-serif`};">
                    ${escHtml(item.label)}
                  </button>
                `).join('')}
                ${importedFa.map(item => `
                  <div style="display:inline-flex;align-items:center;background:${customFontFa === item.id ? theme.accentGrad : 'rgba(255,255,255,0.06)'};border:1px solid ${customFontFa === item.id ? theme.cardBorder : 'rgba(255,255,255,0.08)'};border-radius:6px;padding:2px 3px 2px 7px;gap:3px;">
                    <button type="button" data-font-fa="${escHtml(item.id)}" style="background:none;border:none;color:${customFontFa === item.id ? '#080d16' : theme.textColor};font-size:9.5px;font-weight:700;cursor:pointer;padding:0;font-family:'${escHtml(item.id)}', sans-serif;">
                      ${item.data ? '📁 ' : ''}${escHtml(item.name)}
                    </button>
                    <button type="button" data-delete-imported-font="${escHtml(item.id)}" title="${isFa ? 'حذف فونت' : 'Remove font'}" style="background:none;border:none;color:${customFontFa === item.id ? '#080d16' : theme.subText};cursor:pointer;font-size:9.5px;padding:0 1px;line-height:1;opacity:0.75;">✕</button>
                  </div>
                `).join('')}
              </div>
            </div>

            <div style="margin-top:7px;padding-top:6px;border-top:1px dashed ${theme.itemBorder};">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;">
                <span style="font-size:9.5px;font-weight:700;color:${theme.textColor};font-family:${uiFont};">${isFa ? 'ایمپورت فونت سفارشی' : 'Import Custom Font'}</span>
                <button id="aqm-toggle-import-btn" type="button" style="background:${theme.chipBg};border:1px solid ${theme.itemBorder};border-radius:6px;color:${theme.accent};font-size:9px;font-weight:700;cursor:pointer;padding:2px 6px;font-family:${uiFont};">
                  ${isImportFormOpen ? (isFa ? 'بستن فرم ▲' : 'Close Form ▲') : (isFa ? '➕ افزودن فونت' : '➕ Add Font')}
                </button>
              </div>
              <div id="aqm-import-form" style="display:${isImportFormOpen ? 'flex' : 'none'};flex-direction:column;gap:5px;background:rgba(0,0,0,0.3);padding:8px;border-radius:10px;border:1px solid ${theme.itemBorder};margin-bottom:4px;">
                <div>
                  <input id="aqm-import-file" type="file" accept=".woff2,.woff,.ttf,.otf" style="display:none;" />
                  <label for="aqm-import-file" id="aqm-import-file-label" style="display:flex;align-items:center;justify-content:space-between;gap:6px;padding:5px 8px;border-radius:7px;background:rgba(255,255,255,0.05);border:1px dashed ${stagedFontFile ? '#10b981' : theme.itemBorder};color:${stagedFontFile ? '#10b981' : theme.accent};font-size:9.5px;font-weight:700;cursor:pointer;font-family:${uiFont};user-select:none;">
                    <span style="display:flex;align-items:center;gap:6px;">
                      <span style="font-size:11px;">📁</span>
                      <span id="aqm-import-file-text">${stagedFontFile ? `✓ ${escHtml(stagedFontFile.fileName)} (${stagedFontFile.sizeKb} KB)` : (isFa ? 'انتخاب یا آپلود فایل فونت (TTF, WOFF2, OTF)' : 'Select or Upload Font File (TTF, WOFF2, OTF)')}</span>
                    </span>
                    <span id="aqm-import-file-badge" style="font-size:8px;padding:1px 5px;border-radius:4px;background:${stagedFontFile ? 'rgba(16,185,129,0.2)' : 'rgba(255,255,255,0.08)'};color:${stagedFontFile ? '#10b981' : theme.subText};font-family:'JetBrains Mono',monospace;">${stagedFontFile ? escHtml(stagedFontFile.format.toUpperCase()) : (isFa ? 'فایل محلی' : 'Local File')}</span>
                  </label>
                </div>
                <div style="display:flex;align-items:center;gap:5px;font-size:8px;color:${theme.subText};margin:1px 0;font-family:${uiFont};">
                  <div style="flex:1;height:1px;background:${theme.itemBorder};opacity:0.6;"></div>
                  <span>${isFa ? 'یا وارد کردن نام فونت / لینک وب‌فونت' : 'or enter font name / webfont URL'}</span>
                  <div style="flex:1;height:1px;background:${theme.itemBorder};opacity:0.6;"></div>
                </div>
                <input id="aqm-import-name" type="text" value="${stagedFontFile ? escHtml(stagedFontFile.name) : ''}" placeholder="${isFa ? 'نام فونت (مثلاً IRANSansX یا Dana)' : 'Font Name (e.g. IRANSansX or Inter)'}" style="width:100%;box-sizing:border-box;background:rgba(255,255,255,0.06);border:1px solid ${theme.itemBorder};border-radius:6px;padding:4px 7px;font-size:9.5px;color:${theme.textColor};outline:none;font-family:${uiFont};direction:${uiDir};" />
                <input id="aqm-import-url" type="text" placeholder="${isFa ? 'لینک وب‌فونت یا CSS (اختیاری اگر فایل یا فونت سیستم دارید)' : 'Webfont or CSS URL (optional if local/system font)'}" style="width:100%;box-sizing:border-box;background:rgba(255,255,255,0.06);border:1px solid ${theme.itemBorder};border-radius:6px;padding:4px 7px;font-size:9px;color:${theme.textColor};outline:none;font-family:'JetBrains Mono',monospace;direction:ltr;" />
                <div style="display:flex;justify-content:space-between;align-items:center;margin-top:2px;">
                  <div style="display:flex;gap:8px;font-size:9px;color:${theme.subText};align-items:center;">
                    <label style="display:flex;align-items:center;gap:3px;cursor:pointer;font-family:${uiFont};">
                      <input type="radio" name="aqm-import-type" value="fa" checked style="accent-color:${theme.accent};" />
                      ${isFa ? 'فارسی' : 'Persian'}
                    </label>
                    <label style="display:flex;align-items:center;gap:3px;cursor:pointer;font-family:${uiFont};">
                      <input type="radio" name="aqm-import-type" value="en" style="accent-color:${theme.accent};" />
                      ${isFa ? 'انگلیسی' : 'English'}
                    </label>
                  </div>
                  <button id="aqm-import-submit-btn" type="button" style="background:${theme.accentGrad};color:#060d13;border:none;border-radius:6px;padding:3.5px 10px;font-size:9.5px;font-weight:700;cursor:pointer;box-shadow:${theme.accentGlow};font-family:${uiFont};">
                    ${isFa ? 'افزودن و اعمال' : 'Add & Apply'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div id="aqm-tab-content-rtl" style="display:${activePopoverTab === 'rtl' ? 'block' : 'none'};direction:${uiDir};">
          <div style="margin:8px 0;border-top:1px solid ${theme.itemBorder};padding-top:7px;">
            <div style="font-size:11px;font-weight:800;color:${theme.textColor};margin-bottom:6px;padding:0 2px;display:flex;justify-content:space-between;align-items:center;font-family:${uiFont};">
              <span>${isFa ? 'پشتیبانی راست‌چین و فارسی (Smart RTL)' : 'Smart RTL & Persian Suite'}</span>
              <span style="font-size:8.5px;color:${theme.accent};font-family:'JetBrains Mono',monospace;">Alt + R</span>
            </div>

            <div id="aqm-rtl-toggle-row" style="display:flex;justify-content:space-between;align-items:center;padding:5px 7px;cursor:pointer;border-radius:8px;user-select:none;background:rgba(255,255,255,0.035);margin-bottom:4px;">
              <div style="display:flex;flex-direction:column;">
                <span style="font-size:10px;font-weight:700;color:${theme.textColor};font-family:${uiFont};">${isFa ? 'راست‌چین هوشمند' : 'Smart Auto-RTL'}</span>
                <span style="font-size:8.5px;color:${theme.subText};font-family:${uiFont};">${isFa ? 'تنظیم خودکار جهت پاراگراف‌ها بر اساس زبان' : 'Auto-detect paragraph direction by language'}</span>
              </div>
              <div style="width:30px;height:17px;border-radius:9999px;background:${rtlConfig.isRTL ? theme.accent : 'rgba(255,255,255,0.18)'};position:relative;">
                <div style="width:13px;height:13px;border-radius:50%;background:#ffffff;position:absolute;top:2px;${rtlConfig.isRTL ? 'left:2px;' : 'right:2px;'};box-shadow:0 1px 3px rgba(0,0,0,0.35);"></div>
              </div>
            </div>

            <div id="aqm-rtl-force-row" style="display:flex;justify-content:space-between;align-items:center;padding:5px 7px;cursor:pointer;border-radius:8px;user-select:none;background:rgba(255,255,255,0.035);margin-bottom:4px;">
              <div style="display:flex;flex-direction:column;">
                <span style="font-size:10px;font-weight:700;color:${theme.textColor};font-family:${uiFont};">${isFa ? 'اجبار راست‌چین (Force RTL)' : 'Force Full RTL'}</span>
                <span style="font-size:8.5px;color:${theme.subText};font-family:${uiFont};">${isFa ? 'راست‌چین کامل تمام پیام‌ها و چت‌ها' : 'Force right-to-left layout across all chat messages'}</span>
              </div>
              <div style="width:30px;height:17px;border-radius:9999px;background:${rtlConfig.forceRTL ? theme.accent : 'rgba(255,255,255,0.18)'};position:relative;">
                <div style="width:13px;height:13px;border-radius:50%;background:#ffffff;position:absolute;top:2px;${rtlConfig.forceRTL ? 'left:2px;' : 'right:2px;'};box-shadow:0 1px 3px rgba(0,0,0,0.35);"></div>
              </div>
            </div>

            <div id="aqm-rtl-at-row" style="display:flex;justify-content:space-between;align-items:center;padding:5px 7px;cursor:pointer;border-radius:8px;user-select:none;background:rgba(255,255,255,0.035);margin-bottom:6px;">
              <div style="display:flex;flex-direction:column;">
                <span style="font-size:10px;font-weight:700;color:${theme.textColor};font-family:${uiFont};">${isFa ? 'اصلاح کلید @ با Shift+2' : 'Fix @ Key on Shift+2'}</span>
                <span style="font-size:8.5px;color:${theme.subText};font-family:${uiFont};">${isFa ? 'تایپ @ به جای کاما در کیبورد فارسی' : 'Insert @ symbol on Shift+2 when using Persian keyboard'}</span>
              </div>
              <div style="width:30px;height:17px;border-radius:9999px;background:${rtlConfig.fixAtSign ? theme.accent : 'rgba(255,255,255,0.18)'};position:relative;">
                <div style="width:13px;height:13px;border-radius:50%;background:#ffffff;position:absolute;top:2px;${rtlConfig.fixAtSign ? 'left:2px;' : 'right:2px;'};box-shadow:0 1px 3px rgba(0,0,0,0.35);"></div>
              </div>
            </div>

            <div style="display:flex;gap:6px;background:rgba(0,0,0,0.25);padding:6px 8px;border-radius:8px;border:1px solid ${theme.itemBorder};">
              <div style="flex:1;">
                <div style="display:flex;justify-content:space-between;font-size:9px;color:${theme.subText};margin-bottom:3px;font-family:${uiFont};">
                  <span>${isFa ? 'فاصله خطوط:' : 'Line Height:'}</span>
                  <span style="font-family:'JetBrains Mono',monospace;color:${theme.textColor};">${escHtml(rtlConfig.lineHeight)}</span>
                </div>
                <input id="aqm-rtl-lh-slider" type="range" min="1.2" max="2.4" step="0.1" value="${escHtml(rtlConfig.lineHeight)}" style="width:100%;accent-color:${theme.accent};cursor:pointer;height:3px;" />
              </div>
              <div style="flex:1;">
                <div style="display:flex;justify-content:space-between;font-size:9px;color:${theme.subText};margin-bottom:3px;font-family:${uiFont};">
                  <span>${isFa ? 'اندازه قلم:' : 'Font Size:'}</span>
                  <span style="font-family:'JetBrains Mono',monospace;color:${theme.textColor};">${escHtml(rtlConfig.fontSize)}px</span>
                </div>
                <input id="aqm-rtl-fs-slider" type="range" min="12" max="22" step="1" value="${escHtml(rtlConfig.fontSize)}" style="width:100%;accent-color:${theme.accent};cursor:pointer;height:3px;" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div style="margin-top:9px;display:flex;justify-content:space-between;align-items:center;font-size:10.5px;direction:ltr;">
        <div style="display:flex;align-items:center;gap:6px;color:${theme.subText};font-size:10px;font-family:${uiFont};">
          <span style="width:5.5px;height:5.5px;border-radius:50%;background:#10b981;box-shadow:0 0 7px rgba(16,185,129,0.8);animation:aqm-pulse-dot 2s infinite ease-in-out;"></span>
          <span style="opacity:0.88;">${isFa ? 'پایش بهینه مصرف • خودترمیم‌گر' : 'Live Quota Monitor • Self-Healing'}</span>
        </div>
        <div data-font="en" style="font-size:10px;color:${theme.subText};opacity:0.75;font-family:${fontEn};letter-spacing:0.02em;">
          Antigravity Quota HUD
        </div>
      </div>
    `;

    bindMismatchBannerEvents(pop);

    const tabQuota = pop.querySelector('#aqm-tab-btn-quota');
    const tabFonts = pop.querySelector('#aqm-tab-btn-fonts');
    const tabRtl = pop.querySelector('#aqm-tab-btn-rtl');
    if (tabQuota) tabQuota.onclick = (e) => { e.stopPropagation(); activePopoverTab = 'quota'; renderPopover(); };
    if (tabFonts) tabFonts.onclick = (e) => { e.stopPropagation(); activePopoverTab = 'fonts'; renderPopover(); };
    if (tabRtl) tabRtl.onclick = (e) => { e.stopPropagation(); activePopoverTab = 'rtl'; renderPopover(); };

    pop.querySelectorAll('[data-switch-quick]').forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        switchAccount(btn.getAttribute('data-switch-quick'));
      };
    });

    const closeBtn = pop.querySelector('#aqm-close-btn');
    if (closeBtn) closeBtn.onclick = (e) => { e.stopPropagation(); pop.style.display = 'none'; };

    const refreshBtn = pop.querySelector('#aqm-refresh-btn');
    if (refreshBtn) refreshBtn.onclick = (e) => { e.stopPropagation(); refreshQuota(); };

    const popLangBtn = pop.querySelector('#aqm-pop-lang-btn');
    if (popLangBtn) {
      popLangBtn.onclick = (e) => {
        e.stopPropagation();
        swLang = (swLang === 'fa') ? 'en' : 'fa';
        try { localStorage.setItem('antigravity:switcher_lang', swLang); } catch (err) {}
        persistUserSettings({ lang: swLang });
        renderBadge();
        renderPopover();
        const modal = document.getElementById('antigravity-switcher-modal');
        if (modal && modal.classList.contains('aqm-active') && typeof renderSwitcherModal === 'function') {
          renderSwitcherModal();
        }
      };
    }

    const popRestartBtn = pop.querySelector('#aqm-pop-restart-btn');
    if (popRestartBtn) popRestartBtn.onclick = (e) => { e.stopPropagation(); restartAntigravityApp(); };

    const privacyBtn = pop.querySelector('#aqm-privacy-btn');
    if (privacyBtn) {
      privacyBtn.onclick = (e) => {
        e.stopPropagation();
        isPrivacyMode = !isPrivacyMode;
        try { localStorage.setItem('antigravity:privacy_mode', String(isPrivacyMode)); } catch (err) {}
        persistUserSettings({ privacyMode: isPrivacyMode });
        renderPopover();
      };
    }

    const modeRemBtn = pop.querySelector('#aqm-mode-rem-btn');
    if (modeRemBtn) {
      modeRemBtn.onclick = (e) => {
        e.stopPropagation();
        displayMode = 'remaining';
        try { localStorage.setItem('antigravity:quota_mode', 'remaining'); } catch (err) {}
        persistUserSettings({ mode: 'remaining' });
        renderBadge();
        renderPopover();
      };
    }

    const modeUsedBtn = pop.querySelector('#aqm-mode-used-btn');
    if (modeUsedBtn) {
      modeUsedBtn.onclick = (e) => {
        e.stopPropagation();
        displayMode = 'used';
        try { localStorage.setItem('antigravity:quota_mode', 'used'); } catch (err) {}
        persistUserSettings({ mode: 'used' });
        renderBadge();
        renderPopover();
      };
    }

    const switcherTrigger = pop.querySelector('#aqm-account-switcher-trigger');
    if (switcherTrigger) {
      switcherTrigger.onclick = (e) => {
        e.stopPropagation();
        switcherTrigger.style.transform = 'scale(0.92)';
        setTimeout(() => { switcherTrigger.style.transform = ''; }, 160);
        if (typeof toggleSwitcherModal === 'function') toggleSwitcherModal();
      };
    }

    pop.querySelectorAll('[data-theme-id]').forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        const tid = btn.getAttribute('data-theme-id');
        if (!THEMES[tid]) return;
        currentThemeId = tid;
        try { localStorage.setItem('antigravity:quota_theme', tid); } catch (err) {}
        persistUserSettings({ theme: tid });
        applyAppWorkspaceTheme(getActiveTheme(), isFullAppThemingEnabled);
        renderBadge();
        renderPopover();
      };
    });

    pop.querySelectorAll('[data-font-en]').forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        const fn = btn.getAttribute('data-font-en');
        customFontEn = fn;
        try { localStorage.setItem('antigravity:custom_font_en', fn); } catch (err) {}
        persistUserSettings({ fontEn: fn });
        ensureFontLoaded(fn);
        applyAppWorkspaceTheme(getActiveTheme(), isFullAppThemingEnabled);
        renderBadge();
        renderPopover();
      };
    });

    pop.querySelectorAll('[data-font-fa]').forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        const fn = btn.getAttribute('data-font-fa');
        customFontFa = fn;
        try { localStorage.setItem('antigravity:custom_font_fa', fn); } catch (err) {}
        persistUserSettings({ fontFa: fn });
        ensureFontLoaded(fn);
        applyAppWorkspaceTheme(getActiveTheme(), isFullAppThemingEnabled);
        renderBadge();
        renderPopover();
      };
    });

    const toggleImportBtn = pop.querySelector('#aqm-toggle-import-btn');
    if (toggleImportBtn) {
      toggleImportBtn.onclick = (e) => {
        e.stopPropagation();
        isImportFormOpen = !isImportFormOpen;
        renderPopover();
      };
    }

    const importNameInput = pop.querySelector('#aqm-import-name');
    const importUrlInput = pop.querySelector('#aqm-import-url');
    if (importNameInput) {
      importNameInput.onclick = (e) => e.stopPropagation();
      importNameInput.onkeydown = (e) => e.stopPropagation();
    }
    if (importUrlInput) {
      importUrlInput.onclick = (e) => e.stopPropagation();
      importUrlInput.onkeydown = (e) => e.stopPropagation();
    }

    const importFileInput = pop.querySelector('#aqm-import-file');
    const importFileLabel = pop.querySelector('#aqm-import-file-label');
    const importFileText = pop.querySelector('#aqm-import-file-text');
    const importFileBadge = pop.querySelector('#aqm-import-file-badge');
    if (importFileInput) {
      importFileInput.onclick = (e) => e.stopPropagation();
      importFileInput.onchange = (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) return;
        if (file.size > 8 * 1024 * 1024) {
          if (importFileText) importFileText.textContent = isFa ? 'خطا: فایل بیشتر از ۸ مگابایت است!' : 'Error: file exceeds 8 MB!';
          if (importFileLabel) importFileLabel.style.borderColor = '#ef4444';
          return;
        }
        const fmt = getFontFormatFromFileName(file.name);
        const suggestedName = deriveFontNameFromFile(file.name);
        if (importNameInput && (!importNameInput.value || importNameInput.value.trim() === '')) {
          importNameInput.value = suggestedName;
        }
        const reader = new FileReader();
        reader.onload = (loadEvt) => {
          stagedFontFile = {
            name: suggestedName,
            fileName: file.name,
            format: fmt,
            sizeKb: Math.round(file.size / 1024),
            data: loadEvt.target.result
          };
          if (importFileText) importFileText.textContent = `✓ ${file.name} (${stagedFontFile.sizeKb} KB)`;
          if (importFileLabel) {
            importFileLabel.style.borderColor = '#10b981';
            importFileLabel.style.color = '#10b981';
          }
          if (importFileBadge) {
            importFileBadge.textContent = fmt.toUpperCase();
            importFileBadge.style.background = 'rgba(16, 185, 129, 0.2)';
            importFileBadge.style.color = '#10b981';
          }
        };
        reader.onerror = () => {
          if (importFileText) importFileText.textContent = isFa ? 'خطا در بارگذاری فایل!' : 'Failed to load font file!';
          if (importFileLabel) importFileLabel.style.borderColor = '#ef4444';
        };
        reader.readAsDataURL(file);
      };
    }

    const importSubmitBtn = pop.querySelector('#aqm-import-submit-btn');
    if (importSubmitBtn) {
      importSubmitBtn.onclick = (e) => {
        e.stopPropagation();
        const rawName = importNameInput ? importNameInput.value.trim() : '';
        const cleanName = sanitizeFontName(rawName || (stagedFontFile ? stagedFontFile.name : ''));
        if (!cleanName) {
          if (importNameInput) {
            importNameInput.style.borderColor = '#ef4444';
            importNameInput.placeholder = isFa ? 'نام فونت الزامی است!' : 'Font name is required!';
            importNameInput.focus();
          }
          return;
        }
        const cleanUrl = sanitizeFontUrl(importUrlInput ? importUrlInput.value.trim() : '');
        const typeRadio = pop.querySelector('input[name="aqm-import-type"]:checked');
        const fType = typeRadio ? typeRadio.value : 'fa';
        const fontEntry = { id: cleanName, name: cleanName, url: cleanUrl, type: fType };
        if (stagedFontFile && stagedFontFile.data) {
          fontEntry.data = stagedFontFile.data;
          fontEntry.format = stagedFontFile.format;
          fontEntry.fileName = stagedFontFile.fileName;
          fontEntry.sizeKb = stagedFontFile.sizeKb;
        }
        const existingIdx = customImportedFonts.findIndex(f => f.id.toLowerCase() === cleanName.toLowerCase());
        if (existingIdx >= 0) {
          if (!fontEntry.data && customImportedFonts[existingIdx].data) {
            fontEntry.data = customImportedFonts[existingIdx].data;
            fontEntry.format = customImportedFonts[existingIdx].format;
            fontEntry.fileName = customImportedFonts[existingIdx].fileName;
            fontEntry.sizeKb = customImportedFonts[existingIdx].sizeKb;
          }
          customImportedFonts[existingIdx] = fontEntry;
        } else {
          customImportedFonts.push(fontEntry);
        }
        try {
          localStorage.setItem('antigravity:custom_imported_fonts', JSON.stringify(customImportedFonts));
        } catch (err) {
          try {
            const light = customImportedFonts.map(f => ({ id: f.id, name: f.name, type: f.type, url: f.url, fileName: f.fileName, format: f.format, sizeKb: f.sizeKb }));
            localStorage.setItem('antigravity:custom_imported_fonts', JSON.stringify(light));
          } catch (e2) {}
        }
        injectImportedFontStyles();
        if (fType === 'fa') {
          customFontFa = cleanName;
          try { localStorage.setItem('antigravity:custom_font_fa', cleanName); } catch (err) {}
        } else {
          customFontEn = cleanName;
          try { localStorage.setItem('antigravity:custom_font_en', cleanName); } catch (err) {}
        }
        persistUserSettings({ customImportedFonts, fontEn: customFontEn, fontFa: customFontFa });
        ensureFontLoaded(cleanName);
        applyAppWorkspaceTheme(getActiveTheme(), isFullAppThemingEnabled);
        stagedFontFile = null;
        isImportFormOpen = false;
        renderBadge();
        renderPopover();
      };
    }

    pop.querySelectorAll('[data-delete-imported-font]').forEach(delBtn => {
      delBtn.onclick = (e) => {
        e.stopPropagation();
        const fid = delBtn.getAttribute('data-delete-imported-font');
        const linkEl = document.getElementById(`aqm-cfont-${encodeURIComponent(fid.replace(/\s+/g, '-'))}`);
        if (linkEl) linkEl.remove();
        const styleEl = document.getElementById(`aqm-cfont-data-${encodeURIComponent(fid.replace(/\s+/g, '-'))}`);
        if (styleEl) styleEl.remove();
        customImportedFonts = customImportedFonts.filter(f => f.id !== fid);
        try { localStorage.setItem('antigravity:custom_imported_fonts', JSON.stringify(customImportedFonts)); } catch (err) {}
        if (customFontFa === fid) {
          customFontFa = 'default';
          try { localStorage.setItem('antigravity:custom_font_fa', 'default'); } catch (err) {}
        }
        if (customFontEn === fid) {
          customFontEn = 'default';
          try { localStorage.setItem('antigravity:custom_font_en', 'default'); } catch (err) {}
        }
        persistUserSettings({ customImportedFonts, fontEn: customFontEn, fontFa: customFontFa });
        applyAppWorkspaceTheme(getActiveTheme(), isFullAppThemingEnabled);
        renderBadge();
        renderPopover();
      };
    });

    const rtlToggleRow = pop.querySelector('#aqm-rtl-toggle-row');
    if (rtlToggleRow) {
      rtlToggleRow.onclick = (e) => {
        e.stopPropagation();
        rtlConfig.isRTL = !rtlConfig.isRTL;
        saveRtlConfig();
        syncRtlRuntime();
        renderPopover();
      };
    }
    const rtlForceRow = pop.querySelector('#aqm-rtl-force-row');
    if (rtlForceRow) {
      rtlForceRow.onclick = (e) => {
        e.stopPropagation();
        rtlConfig.forceRTL = !rtlConfig.forceRTL;
        saveRtlConfig();
        syncRtlRuntime();
        renderPopover();
      };
    }
    const rtlAtRow = pop.querySelector('#aqm-rtl-at-row');
    if (rtlAtRow) {
      rtlAtRow.onclick = (e) => {
        e.stopPropagation();
        rtlConfig.fixAtSign = !rtlConfig.fixAtSign;
        saveRtlConfig();
        renderPopover();
      };
    }
    const rtlLhSlider = pop.querySelector('#aqm-rtl-lh-slider');
    if (rtlLhSlider) {
      rtlLhSlider.onclick = (e) => e.stopPropagation();
      rtlLhSlider.oninput = (e) => {
        rtlConfig.lineHeight = e.target.value;
        saveRtlConfig();
        applyRtlStyles();
      };
    }
    const rtlFsSlider = pop.querySelector('#aqm-rtl-fs-slider');
    if (rtlFsSlider) {
      rtlFsSlider.onclick = (e) => e.stopPropagation();
      rtlFsSlider.oninput = (e) => {
        rtlConfig.fontSize = e.target.value;
        saveRtlConfig();
        applyRtlStyles();
      };
    }

    const dragHandle = pop.querySelector('#aqm-drag-handle');
    if (dragHandle) {
      dragHandle.onmousedown = (e) => {
        if (e.target.closest('button') || e.target.closest('input') || e.target.closest('label') || e.target.closest('a')) return;
        e.preventDefault();
        e.stopPropagation();
        const popRect = pop.getBoundingClientRect();
        const startMouseX = e.clientX;
        const startMouseY = e.clientY;
        const startLeft = popRect.left;
        const startTop = popRect.top;
        pop.style.bottom = 'auto';
        pop.style.top = startTop + 'px';
        pop.style.left = startLeft + 'px';
        dragHandle.style.cursor = 'grabbing';
        let hasMoved = false;

        function onMouseMove(moveEvent) {
          moveEvent.preventDefault();
          hasMoved = true;
          const newLeft = Math.min(Math.max(10, startLeft + (moveEvent.clientX - startMouseX)), window.innerWidth - popRect.width - 10);
          const newTop = Math.min(Math.max(10, startTop + (moveEvent.clientY - startMouseY)), window.innerHeight - popRect.height - 10);
          pop.style.left = newLeft + 'px';
          pop.style.top = newTop + 'px';
        }
        function onMouseUp() {
          window.removeEventListener('mousemove', onMouseMove);
          window.removeEventListener('mouseup', onMouseUp);
          dragHandle.style.cursor = 'grab';
          if (hasMoved) {
            try {
              const pos = { left: pop.style.left, top: pop.style.top };
              localStorage.setItem('antigravity:popover_pos', JSON.stringify(pos));
              persistUserSettings({ popoverPos: pos });
            } catch (err) {}
          }
        }
        onGlobal(window, 'mousemove', onMouseMove);
        onGlobal(window, 'mouseup', onMouseUp);
      };

      dragHandle.ondblclick = (e) => {
        if (e.target.closest('button') || e.target.closest('input')) return;
        e.stopPropagation();
        try {
          localStorage.removeItem('antigravity:popover_pos');
          persistUserSettings({ popoverPos: null });
        } catch (err) {}
        const tBtn = document.querySelector('[data-testid="permissions-selector-trigger"]') ||
          Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.includes('Turbo'));
        const trig = document.querySelector('[data-testid="model-selector-trigger"]');
        const anch = document.getElementById('antigravity-account-pill') || tBtn || trig;
        if (anch) {
          const r = anch.getBoundingClientRect();
          pop.style.left = Math.max(16, r.left - 20) + 'px';
          pop.style.bottom = (window.innerHeight - r.top + 14) + 'px';
          pop.style.top = 'auto';
        }
      };
    }
  }

  function togglePopover(e) {
    if (e) {
      e.stopPropagation();
      try { e.preventDefault(); } catch (err) {}
    }
    const pop = getOrCreatePopover();
    if (pop.style.display === 'none' || !pop.style.display) {
      lastPopoverOpenTime = Date.now();
      renderPopover();
      pop.style.display = 'block';
    } else {
      pop.style.display = 'none';
    }
  }

  function renderBadge() {
    const trigger = document.querySelector('[data-testid="model-selector-trigger"]');
    const theme = getActiveTheme();
    const { fullFamily } = getEffectiveFonts(theme);

    let dock = document.getElementById('antigravity-quota-dock');
    let badge = document.getElementById('antigravity-usage-badge');
    if (trigger) {
      if (dock) dock.style.display = 'none';
      if (!badge) {
        badge = document.createElement('div');
        badge.id = 'antigravity-usage-badge';
        const svg = trigger.querySelector('svg');
        if (svg && svg.parentNode) {
          try { svg.parentNode.insertBefore(badge, svg); } catch (e) { trigger.appendChild(badge); }
        } else {
          trigger.appendChild(badge);
        }
      }
      badge.style.display = 'inline-flex';
      badge.style.alignItems = 'center';
      badge.style.gap = '6px';
      badge.style.marginLeft = '6px';
      badge.style.marginRight = '2px';
      badge.style.padding = '2px 8px';
      badge.style.borderRadius = '9999px';
      badge.style.fontSize = '11px';
      badge.style.fontWeight = '700';
      badge.style.fontFamily = `'JetBrains Mono', ${fullFamily}`;
      badge.style.background = theme.chipBg;
      badge.style.border = `1px solid ${theme.cardBorder}`;
      badge.style.color = theme.accent;
      badge.style.cursor = 'default';
      badge.style.pointerEvents = 'none';
      badge.style.userSelect = 'none';
      badge.style.boxShadow = '0 1px 4px rgba(0,0,0,0.2)';
    } else {
      if (badge) badge.remove();
      if (!dock) {
        dock = document.createElement('div');
        dock.id = 'antigravity-quota-dock';
        dock.style.position = 'fixed';
        dock.style.bottom = '18px';
        dock.style.right = '24px';
        dock.style.zIndex = '999998';
        dock.style.display = 'flex';
        dock.style.alignItems = 'center';
        dock.style.gap = '8px';
        dock.style.padding = '4px 6px';
        dock.style.borderRadius = '9999px';
        dock.style.background = 'rgba(15, 23, 42, 0.72)';
        dock.style.backdropFilter = 'blur(12px)';
        dock.style.webkitBackdropFilter = 'blur(12px)';
        dock.style.border = '1px solid rgba(255, 255, 255, 0.12)';
        dock.style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.45)';
        (document.body || document.documentElement).appendChild(dock);
      } else {
        dock.style.display = 'flex';
      }
    }

    const oldPill = document.getElementById('antigravity-usage-pill');
    if (oldPill) oldPill.remove();

    const isRem = (displayMode === 'remaining');
    const sessRem = Math.round(currentUsage.session?.remaining_pct ?? (100 - Math.round(currentUsage.session?.used_pct ?? 0)));
    const sessUsed = Math.round(currentUsage.session?.used_pct ?? (100 - sessRem));
    const sessReset = currentUsage.session?.resets_in || 'Ready';
    const weekRem = Math.round(currentUsage.weekly?.remaining_pct ?? (100 - Math.round(currentUsage.weekly?.used_pct ?? 0)));
    const weekUsed = Math.round(currentUsage.weekly?.used_pct ?? (100 - weekRem));
    const weekReset = currentUsage.weekly?.resets_in || 'Ready';
    const badgeSess = isRem ? sessRem : sessUsed;
    const badgeWeek = isRem ? weekRem : weekUsed;

    const titleTooltip = `Gemini Quota HUD\n• 5-Hour: ${sessRem}% Remaining (${sessUsed}% Used) - Resets in: ${sessReset}\n• Weekly: ${weekRem}% Remaining (${weekUsed}% Used) - Resets in: ${weekReset}\nClick to view full HUD`;

    if (badge) {
      const badgeSig = `${badgeSess}|${badgeWeek}|${theme.dotColor}|${theme.id}`;
      if (badge.dataset.aqmSig !== badgeSig) {
        badge.dataset.aqmSig = badgeSig;
        badge.title = titleTooltip;
        badge.innerHTML = `
          <span style="width:5.5px;height:5.5px;border-radius:50%;background:${theme.dotColor};box-shadow:0 0 7px ${theme.dotColor};animation:aqm-pulse-dot 2s infinite ease-in-out;"></span>
          <span dir="ltr">${badgeSess}%</span>
          <span style="opacity:0.35;font-weight:400;margin:0 1px;">|</span>
          <span style="opacity:0.85;font-size:10px;font-weight:600;" dir="ltr">W: ${badgeWeek}%</span>
        `;
      }
    }

    let accPill = document.getElementById('antigravity-account-pill');
    if (!accPill) {
      accPill = document.createElement('button');
      accPill.id = 'antigravity-account-pill';
      accPill.type = 'button';
    }

    const turboBtn = document.querySelector('[data-testid="permissions-selector-trigger"]') ||
      Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.includes('Turbo'));

    if (turboBtn && turboBtn.parentElement) {
      if (accPill.nextElementSibling !== turboBtn) turboBtn.insertAdjacentElement('beforebegin', accPill);
    } else if (trigger && trigger.parentElement) {
      if (accPill.previousElementSibling !== trigger) trigger.insertAdjacentElement('afterend', accPill);
    } else if (dock && accPill.parentElement !== dock) {
      dock.appendChild(accPill);
    }

    accPill.style.display = 'inline-flex';
    accPill.style.alignItems = 'center';
    accPill.style.justifyContent = 'center';
    accPill.style.width = '28px';
    accPill.style.height = '28px';
    accPill.style.minWidth = '28px';
    accPill.style.minHeight = '28px';
    accPill.style.marginRight = '6px';
    accPill.style.marginLeft = '2px';
    accPill.style.padding = '0';
    accPill.style.borderRadius = '50%';
    accPill.style.position = 'relative';
    accPill.style.background = 'rgba(15, 23, 42, 0.78)';
    accPill.style.backdropFilter = 'blur(10px)';
    accPill.style.webkitBackdropFilter = 'blur(10px)';
    accPill.style.border = '1.5px solid rgba(255, 255, 255, 0.22)';
    accPill.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.35)';
    accPill.style.cursor = 'pointer';
    accPill.style.userSelect = 'none';
    accPill.style.transition = 'transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.2s ease';
    accPill.style.flexShrink = '0';
    accPill.style.boxSizing = 'border-box';

    const { accEmail, accName, accAvatar, accTierCode, initialChar } = getActiveAccountInfo();
    const accPillSig = `${accEmail}|${accName}|${accAvatar}|${accTierCode}|circle_v5`;
    if (accPill.dataset.aqmSig !== accPillSig) {
      accPill.dataset.aqmSig = accPillSig;
      accPill.title = `Antigravity Control HUD (${accName})`;
      accPill.innerHTML = `
        ${accAvatar ? `<img src="${escHtml(accAvatar)}" style="width:100%;height:100%;border-radius:50%;object-fit:cover;display:block;pointer-events:none;" onerror="this.style.display='none';if(this.nextElementSibling)this.nextElementSibling.style.display='flex';" />` : ''}
        <span style="${accAvatar ? 'display:none;' : 'display:flex;'}width:100%;height:100%;align-items:center;justify-content:center;border-radius:50%;background:linear-gradient(135deg, #3b82f6, #8b5cf6);color:#ffffff;font-weight:800;font-size:11px;pointer-events:none;">${escHtml(initialChar)}</span>
        <span style="position:absolute;top:0;right:0;width:7px;height:7px;border-radius:50%;background:#10b981;border:1.5px solid #0f172a;box-shadow:0 0 6px #10b981;animation:aqm-pulse-dot 2s infinite ease-in-out;pointer-events:none;"></span>
      `;
    }

    accPill.onclick = (e) => togglePopover(e);
    accPill.onpointerdown = (e) => { if (e) e.stopPropagation(); };
    accPill.onmouseenter = () => {
      accPill.style.transform = 'scale(1.1)';
      if (!accPill.classList.contains('aqm-consuming')) accPill.style.borderColor = '#10b981';
    };
    accPill.onmouseleave = () => {
      accPill.style.transform = '';
      if (!accPill.classList.contains('aqm-consuming')) accPill.style.borderColor = 'rgba(255, 255, 255, 0.22)';
    };

    const pop = document.getElementById('antigravity-usage-popover');
    if (pop && pop.style.display !== 'none' && !pop.matches(':hover')) {
      renderPopover();
    }
  }
