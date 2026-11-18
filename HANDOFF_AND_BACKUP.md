# سند جامع معماری، هندآف و پشتیبان پروژه (Project Handoff & Architecture Backup — v3.0.0)
## سوئیت مدیریت حساب‌ها، پایش زنده ۶ استخر سهمیه، راست‌چین هوشمند و مهاجرت پروژه‌های گوگل آنتی‌گرویتی

**نسخه معماری:** `3.0.0`  
**آدرس مخزن رسمی گیت‌هاب:** `https://github.com/mad-helpers/antigravity-account-switcher.git`  
**سازمان و توسعه‌دهندگان:** **mad-helpers (Madgod-xyz & Bombhub-apk)**  
**شاخه اصلی (Default Branch):** `main`  

---

## ۱. معرفی و هدف پروژه در نسخه v3.0 (Project Mission)
این پروژه یک سوئیت بومی، ماژولار و امن برای کاربران و توسعه‌دهندگان **Google Antigravity 2.33+** در ویندوز، مک و لینوکس است:
1. **هسته یکپارچه `ag_suite/`:** حذف کامل تکرارهای ۴گانه قدیمی و تجمیع منطق مخزن توکن‌ها (`vault.py`)، ذخیره‌سازی اتمیک و پاک‌سازی اطلاعات حساس کلاینت (`store.py`)، موتور ۶ استخر سهمیه و عیب‌یاب (`quota.py`) و فایروال امنیتی CDP/HTTP (`cdp.py`).
2. **پایش زنده ۶ استخر مدل ۲۰۲۶:** پشتیبانی دقیق از `Gemini 4 Hydrogen`، `Gemini 4 Argon`، `Gemini 4 Carbon & Orchestrator`، `Gemini 3.8 Flash`، `Claude 4.6 (Opus & Sonnet)` (شامل خانواده `Claude 5.5`) و `GPT-OSS 120B` به همراه تشخیص بلادرنگ عدم تطابق نشست ادیتور (`session_mismatch`).
3. **پلاگین بومی Antigravity 2.33+ و پنل جانبی Sidecar (`plugin/`):** ارائه پنل شیشه‌ای دوزبانه `Account & Quota Hub` (`sidecar://antigravity-account-suite/account-suite/`) و ۵ ابزار MCP (`get_quota_status`, `switch_account`, `set_project_quota`, `list_saved_accounts`, `diagnose_suite`).
4. **اینجکتور ماژولار و فونت‌های آفلاین محلی:** کامپایل قطعی `src/injector/00..05_*.js` توسط `scripts/build_bundle.py` به `antigravity_quota_injector.js`، سرو محلی فونت‌های `Vazirmatn[wght].woff2`، `Estedad[wght].woff2` و `Outfit[wght].woff2` و موتور Smart RTL v3.
5. **نصب‌کننده‌های جهانی ۱-خطی روی شاخه `main`:** پشتیبانی کامل از `irm .../main/install.ps1 | iex` در ویندوز (ASCII خالص بدون BOM) و `curl -fsSL .../main/install.sh | bash` در مک و لینوکس همراه با پرچم `--remote-debugging-port=0`.

---

## ۲. ساختار دایرکتوری و فایل‌ها (v3.0 Directory Structure)

```text
antigravity-account-switcher/
├── ag_suite/                           # هسته یکپارچه پایتون (بدون وابستگی خارجی)
│   ├── __init__.py                     # نسخه 3.0.0 و اکسپورت ماژول‌ها
│   ├── vault.py                        # تعامل امن با Win32 CredManager، macOS Keychain و Linux secret-tool
│   ├── store.py                        # ذخیره‌سازی اتمیک، sanitize_manifest_for_client و سرو امن فونت‌ها
│   ├── quota.py                        # موتور ۶ استخر سهمیه، کشف LanguageServer و diagnose_suite()
│   └── cdp.py                          # فیلتر اهداف Workbench، التیام DevToolsActivePort و فایروال Origin/CSRF
├── src/injector/                       # ماژول‌های ۶گانه اینجکتور (00 تا 05)
├── scripts/build_bundle.py             # باندلر استاندارد پایتون با قابلیت --check
├── antigravity_quota_injector.js       # خروجی کامپایل‌شده اینجکتور داخل ادیتور
├── app/                                # مرکز کنترل وب شیشه‌ای مایع (پورت 39285)
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── i18n.js
├── plugin/                             # پلاگین بومی Antigravity 2.33+ و Sidecar Aux Pane
│   ├── plugin.json
│   ├── mcp_config.json
│   ├── assets/logo.svg
│   ├── rules/AGENTS.md
│   ├── skills/antigravity-account-suite/SKILL.md
│   └── sidecars/account-suite/{sidecar.json, main.mjs, index.html}
├── assets/fonts/                       # فونت‌های محلی Vazirmatn[wght].woff2, Estedad[wght].woff2, Outfit[wght].woff2
├── legacy/chatgpt/                     # اسکریپت‌های ایزوله‌شده قدیمی ChatGPT/Codex
├── server.py                           # سرور مرکز کنترل (پورت 39285) و عملیات سوئیچ/ری‌استارت/OAuth
├── sync_daemon.py                      # دیمن پس‌زمینه تزریق CDP و API لوکال (پورت 39281)
├── migration_engine.py                 # موتور مهاجرت مکالمات، تخصیص پروژه و resolve_project()
├── quota_engine.py                     # شیم سازگار با نسخه‌های قبلی روی ag_suite
├── switcher_core.py                    # هسته مک و لینوکس (همسان با AntigravitySwitcher.app)
├── cli.py & agy_switch.py              # رابط خط فرمان سراسری (agy-switch و agy-quota)
├── mcp_server.py                       # سرور استاندارد MCP با ۵ ابزار و تست خودکار (--test)
├── install.ps1 & install.bat           # نصب‌کننده جهانی ویندوز (ASCII خالص، سازگار با irm | iex)
├── install.sh & build_app.sh           # نصب‌کننده جهانی مک و لینوکس
└── tests/                              # مجموعه تست‌های خودکار v3.0
```

---

## ۳. راهنمای دستورات کلیدی (CLI & Diagnostics)

| دستور | کاربرد |
| :--- | :--- |
| `agy-quota` | نمایش جدول گرافیکی سهمیه ۵ ساعته، هفتگی و ۶ استخر مدل در ترمینال |
| `agy-switch --doctor` | عیب‌یابی کامل LanguageServer RPC، پورت CDP (`--remote-debugging-port=0`)، دیمن ۳۹۲۸۱، فونت‌ها و توکن‌ها |
| `agy-switch --list` | لیست تمام حساب‌های ذخیره‌شده، وضعیت سلامت توکن (`needs_reauth`) و اکانت فعال |
| `agy-switch --switch <email>` | سوئیچ آنی توکن در مخزن سیستم‌عامل (پیش‌فرض بدون ری‌استارت؛ با `--restart` همراه با ری‌استارت امن) |
| `agy-switch --set-project-quota <proj> <email>` | تخصیص حساب پرداخت‌کننده سهمیه پروژه و سوئیچ خودکار کردشنال سیستم‌عامل |
| `agy-switch --launch-instance instance_2` | اجرای پنجره مجزای آنتی‌گرویتی با پروفایل ایزوله و `--remote-debugging-port=0` |
| `agy-switch --status-json` | خروجی کامل JSON شامل `auth_state` و `saved_accounts` پاک‌سازی‌شده |
| `agy-switch --gui` | باز کردن مرکز کنترل شیشه‌ای روی `http://127.0.0.1:39285/index.html` |
