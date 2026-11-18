import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { basename, dirname, extname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const HOME = process.env.USERPROFILE || process.env.HOME || homedir();
const DAEMON_BASE = 'http://127.0.0.1:39281';
const CONTROL_CENTER_BASE = 'http://127.0.0.1:39285';

export const GET_TIMEOUT_MS = 5000;
export const POST_TIMEOUT_MS = 30000;
const HEALTH_CACHE_TTL_MS = 3500;

export const DEFAULT_FONT_DIRS = [
  join(HERE, 'fonts'),
  join(HERE, '..', '..', 'assets', 'fonts'),
  join(HERE, '..', '..', '..', 'assets', 'fonts'),
  join(HOME, '.gemini', 'antigravity', 'bin', 'assets', 'fonts'),
];

const FONT_MIME_TYPES = {
  '.woff2': 'font/woff2',
  '.woff': 'font/woff',
  '.ttf': 'font/ttf',
  '.otf': 'font/otf',
};

const BUNDLED_FONT_FILES = [
  'Vazirmatn[wght].woff2',
  'Outfit[wght].woff2',
  'Estedad[wght].woff2',
];

let daemonStartup = null;
let lastDaemonHealthyAt = 0;

export class MockResponse {
  constructor(body, init = {}) {
    this.body = body;
    this.status = init.status ?? 200;
    this.contentType = init.contentType || (init.headers && init.headers['Content-Type']) || 'text/plain';
    this.headers = { ...(init.headers || {}) };
    if (init.contentType && !this.headers['Content-Type']) {
      this.headers['Content-Type'] = init.contentType;
    }
  }
}

export class MockSidecarApp {
  constructor() {
    this.pages = new Map();
    this.apis = new Map();
    this.running = false;
  }

  page(route, handler) {
    this.pages.set(route, handler);
  }

  api(route, handler, method = 'GET') {
    const key = `${String(method || 'GET').toUpperCase()} ${route}`;
    this.apis.set(key, handler);
  }

  run() {
    this.running = true;
  }
}

export function sanitizeFontName(rawName) {
  let decoded = '';
  try {
    decoded = decodeURIComponent(String(rawName || '')).trim().replace(/^\/+/, '');
  } catch (_) {
    return null;
  }
  if (decoded.toLowerCase().startsWith('account-suite/')) {
    decoded = decoded.slice('account-suite/'.length).replace(/^\/+/, '');
  }
  if (decoded.toLowerCase().startsWith('fonts/')) {
    decoded = decoded.slice('fonts/'.length).replace(/^\/+/, '');
  }
  if (
    !decoded ||
    decoded.includes('\0') ||
    decoded.includes('/') ||
    decoded.includes('\\') ||
    decoded.includes('..')
  ) {
    return null;
  }
  const safeName = basename(decoded);
  if (!safeName || safeName !== decoded) return null;
  const ext = extname(safeName).toLowerCase();
  const mime = FONT_MIME_TYPES[ext];
  if (!mime) return null;
  return { safeName, mime };
}

export function findLocalFont(rawName, fontDirs = DEFAULT_FONT_DIRS) {
  const clean = sanitizeFontName(rawName);
  if (!clean) return null;
  for (const dir of fontDirs) {
    const candidate = join(dir, clean.safeName);
    if (existsSync(candidate)) {
      return { path: candidate, mime: clean.mime, safeName: clean.safeName };
    }
  }
  return null;
}

async function daemonHealthy(fetchImpl = fetch) {
  if (Date.now() - lastDaemonHealthyAt < HEALTH_CACHE_TTL_MS) return true;
  try {
    const res = await fetchImpl(`${DAEMON_BASE}/health`, {
      signal: AbortSignal.timeout(1500),
    });
    if (res && res.ok) {
      lastDaemonHealthyAt = Date.now();
      return true;
    }
  } catch (_) {}
  lastDaemonHealthyAt = 0;
  return false;
}

function resolveDaemonScript() {
  const candidates = [
    join(HOME, '.gemini', 'antigravity', 'bin', 'sync_daemon.py'),
    join(HERE, '..', '..', '..', 'sync_daemon.py'),
  ];
  for (const c of candidates) {
    if (existsSync(c)) return c;
  }
  return candidates[0];
}

export async function ensureDaemonRunning(deps = {}) {
  const fetchImpl = deps.fetchImpl || fetch;
  if (deps.skipAutoStart) {
    const ok = await daemonHealthy(fetchImpl);
    return ok ? { ok: true } : { ok: false, error: 'Quota daemon offline (auto-start disabled).' };
  }
  if (await daemonHealthy(fetchImpl)) return { ok: true };
  if (!daemonStartup) {
    daemonStartup = (async () => {
      try {
        const daemonScript = resolveDaemonScript();
        if (process.platform === 'win32') {
          try {
            const taskProc = spawn('schtasks.exe', ['/Run', '/TN', 'AntigravityQuotaMonitor'], {
              detached: true,
              stdio: 'ignore',
              windowsHide: true,
            });
            taskProc.on('error', () => {});
            taskProc.unref();
          } catch (_) {}

          await new Promise((r) => setTimeout(r, 600));
          if (await daemonHealthy(fetchImpl)) return { ok: true };

          if (existsSync(daemonScript)) {
            const child = spawn('pythonw.exe', [daemonScript, '--recover-stale'], {
              cwd: dirname(daemonScript),
              detached: true,
              stdio: 'ignore',
              windowsHide: true,
            });
            child.on('error', () => {
              try {
                const fallback = spawn('python', [daemonScript, '--recover-stale'], {
                  cwd: dirname(daemonScript),
                  detached: true,
                  stdio: 'ignore',
                  windowsHide: true,
                });
                fallback.on('error', () => {});
                fallback.unref();
              } catch (_) {}
            });
            child.unref();
          }
        } else if (existsSync(daemonScript)) {
          const child = spawn('python3', [daemonScript, '--recover-stale'], {
            cwd: dirname(daemonScript),
            detached: true,
            stdio: 'ignore',
          });
          child.on('error', () => {
            try {
              const fallback = spawn('python', [daemonScript, '--recover-stale'], {
                cwd: dirname(daemonScript),
                detached: true,
                stdio: 'ignore',
              });
              fallback.on('error', () => {});
              fallback.unref();
            } catch (_) {}
          });
          child.unref();
        }
      } catch (err) {
        return { ok: false, error: err.message };
      }

      for (let i = 0; i < 20; i += 1) {
        await new Promise((r) => setTimeout(r, 200));
        if (await daemonHealthy(fetchImpl)) return { ok: true };
      }
      return { ok: false, error: 'Quota daemon on 127.0.0.1:39281 did not become healthy in time.' };
    })().finally(() => {
      daemonStartup = null;
    });
  }
  return daemonStartup;
}

export async function forwardDaemon(path, method = 'GET', data = null, deps = {}) {
  const fetchImpl = deps.fetchImpl || fetch;
  const ensureFn = deps.ensureDaemonFn || (() => ensureDaemonRunning(deps));
  const upperMethod = String(method || 'GET').toUpperCase();
  const timeoutMs = upperMethod === 'POST' ? POST_TIMEOUT_MS : GET_TIMEOUT_MS;
  const targetPath = path.startsWith('/') ? path : `/${path}`;

  const ready = await ensureFn();
  const bases = ready && ready.ok ? [DAEMON_BASE, CONTROL_CENTER_BASE] : [CONTROL_CENTER_BASE, DAEMON_BASE];
  const headers =
    upperMethod === 'POST'
      ? { 'Content-Type': 'application/json', Accept: 'application/json' }
      : { Accept: 'application/json' };
  const body = upperMethod === 'POST' ? JSON.stringify(data || {}) : undefined;

  let lastErr = ready && ready.error ? ready.error : 'Daemon unreachable';
  for (const base of bases) {
    try {
      const res = await fetchImpl(`${base}${targetPath}`, {
        method: upperMethod,
        headers,
        body,
        signal: AbortSignal.timeout(timeoutMs),
      });
      if (res && res.ok) {
        const json = await res.json().catch(() => ({}));
        return json;
      }
      if (res) {
        const errPayload = await res.json().catch(() => null);
        if (errPayload && typeof errPayload === 'object') return errPayload;
        lastErr = `HTTP ${res.status}`;
      }
    } catch (err) {
      if (base === DAEMON_BASE) lastDaemonHealthyAt = 0;
      lastErr = err.message;
    }
  }
  return { success: false, status: 'offline', error: lastErr };
}

export async function serveFontHandler(rawFontName, deps = {}) {
  const ResponseImpl = deps.ResponseImpl || MockResponse;
  const fetchImpl = deps.fetchImpl || fetch;
  const fontDirs = deps.fontDirs || DEFAULT_FONT_DIRS;
  const ensureFn = deps.ensureDaemonFn || (() => ensureDaemonRunning(deps));

  const notFound = () =>
    new ResponseImpl('Not Found', {
      status: 404,
      contentType: 'text/plain; charset=utf-8',
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
        'Cache-Control': 'no-store',
      },
    });

  const clean = sanitizeFontName(rawFontName);
  if (!clean) return notFound();

  if (!deps.skipLocalFonts) {
    const localHit = findLocalFont(clean.safeName, fontDirs);
    if (localHit) {
      try {
        return new ResponseImpl(readFileSync(localHit.path), {
          status: 200,
          contentType: localHit.mime,
          headers: {
            'Content-Type': localHit.mime,
            'Access-Control-Allow-Origin': '*',
            'Cache-Control': 'public, max-age=86400',
          },
        });
      } catch (_) {}
    }
  }

  try {
    await ensureFn();
  } catch (_) {}

  for (const base of [DAEMON_BASE, CONTROL_CENTER_BASE]) {
    try {
      const upstream = await fetchImpl(`${base}/fonts/${encodeURIComponent(clean.safeName)}`, {
        method: 'GET',
        signal: AbortSignal.timeout(GET_TIMEOUT_MS),
      });
      if (upstream && upstream.ok) {
        const buf = Buffer.from(await upstream.arrayBuffer());
        if (buf.length > 0) {
          return new ResponseImpl(buf, {
            status: 200,
            contentType: clean.mime,
            headers: {
              'Content-Type': clean.mime,
              'Access-Control-Allow-Origin': '*',
              'Cache-Control': 'public, max-age=86400',
            },
          });
        }
      }
    } catch (_) {}
  }

  return notFound();
}

export function registerSidecarRoutes(app, deps = {}) {
  const ResponseImpl = deps.ResponseImpl || MockResponse;
  const indexHtmlPath = deps.indexHtmlPath || join(HERE, 'index.html');

  const serveRoot = () => {
    const html = readFileSync(indexHtmlPath, 'utf8');
    return new ResponseImpl(html, {
      status: 200,
      contentType: 'text/html; charset=utf-8',
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-cache',
      },
    });
  };

  app.page('/', serveRoot);
  app.page('/index.html', serveRoot);
  app.page('/account-suite/', serveRoot);
  app.page('/account-suite/index.html', serveRoot);

  for (const fontFile of BUNDLED_FONT_FILES) {
    const encoded = encodeURIComponent(fontFile);
    const handler = () => serveFontHandler(fontFile, deps);
    const encodedHandler = () => serveFontHandler(encoded, deps);
    app.page(`/fonts/${fontFile}`, handler);
    app.page(`/fonts/${encoded}`, encodedHandler);
    app.page(`/account-suite/fonts/${fontFile}`, handler);
    app.page(`/account-suite/fonts/${encoded}`, encodedHandler);
  }

  const getRoutes = [
    '/api/state',
    '/api/accounts',
    '/api/projects',
    '/api/conversations',
    '/api/tasks',
    '/api/settings',
    '/api/dual_status',
    '/api/instances_status',
    '/api/health',
    '/health',
    '/quota',
  ];

  for (const route of getRoutes) {
    const handler = async (data) => {
      const qs = new URLSearchParams();
      if (data && typeof data === 'object') {
        for (const [k, v] of Object.entries(data)) {
          if (v !== undefined && v !== null && v !== '') qs.set(k, String(v));
        }
      }
      const target = route === '/api/health' ? '/health' : route;
      const suffix = qs.toString() ? `?${qs.toString()}` : '';
      return forwardDaemon(`${target}${suffix}`, 'GET', null, deps);
    };
    app.api(route, handler, 'GET');
    if (route.startsWith('/api/')) {
      app.api(route.slice(4), handler, 'GET');
    }
  }

  const postRoutes = [
    '/api/switch',
    '/api/restart',
    '/api/restart_app',
    '/api/launch_dual',
    '/api/launch_instance',
    '/api/oauth_signin',
    '/api/save',
    '/api/logout',
    '/api/delete',
    '/api/import',
    '/api/settings',
    '/api/project_set_quota_account',
    '/api/project_assign',
    '/api/project_toggle_all',
    '/api/project_sync',
    '/api/project_unlink',
    '/api/task_set_quota_account',
    '/api/task_assign',
    '/api/task_toggle_all',
    '/api/task_isolate',
    '/api/task_toggle',
    '/api/task_run_guarded',
    '/api/conversation_assign',
    '/api/migrate',
  ];

  for (const route of postRoutes) {
    const handler = async (data) => forwardDaemon(route, 'POST', data || {}, deps);
    app.api(route, handler, 'POST');
    if (route.startsWith('/api/')) {
      app.api(route.slice(4), handler, 'POST');
    }
  }
}

async function runSelfTests() {
  const calls = [];
  const mockFetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    if (String(url).endsWith('/health')) {
      return {
        ok: true,
        status: 200,
        json: async () => ({ status: 'ok', version: '3.0.0' }),
      };
    }
    if (String(url).includes('/fonts/Vazirmatn%5Bwght%5D.woff2')) {
      return {
        ok: true,
        status: 200,
        arrayBuffer: async () => new Uint8Array([0x77, 0x4f, 0x46, 0x32]).buffer,
      };
    }
    if (String(url).includes('/fonts/MissingFont.woff2')) {
      return {
        ok: false,
        status: 404,
        arrayBuffer: async () => new Uint8Array([0x4e, 0x6f]).buffer,
      };
    }
    if (String(url).endsWith('/api/switch')) {
      return {
        ok: true,
        status: 200,
        json: async () => ({ success: true, account: 'user@example.com' }),
      };
    }
    throw new Error('ECONNREFUSED');
  };

  const mockApp = new MockSidecarApp();
  registerSidecarRoutes(mockApp, {
    ResponseImpl: MockResponse,
    fetchImpl: mockFetch,
    ensureDaemonFn: async () => ({ ok: true }),
    skipLocalFonts: true,
  });

  // 1. Page route check
  const rootRes = mockApp.pages.get('/')();
  assert.equal(rootRes.status, 200);
  assert.ok(String(rootRes.body).includes('Account & Quota Hub'));

  // 2. Health API route check
  const healthRes = await mockApp.apis.get('GET /health')({});
  assert.equal(healthRes.status, 'ok');
  assert.equal(healthRes.version, '3.0.0');

  // 3. URL-encoded & plain [wght] font 200 OK
  const fontPlain = await mockApp.pages.get('/fonts/Vazirmatn[wght].woff2')();
  assert.equal(fontPlain.status, 200);
  assert.equal(fontPlain.headers['Content-Type'], 'font/woff2');
  assert.equal(fontPlain.headers['Access-Control-Allow-Origin'], '*');

  const fontEncoded = await mockApp.pages.get('/fonts/Vazirmatn%5Bwght%5D.woff2')();
  assert.equal(fontEncoded.status, 200);
  assert.equal(fontEncoded.headers['Content-Type'], 'font/woff2');

  // 4. Upstream 404 font MUST NOT cache error bodies (must return 404 with Cache-Control: no-store)
  const missingFont = await serveFontHandler('MissingFont.woff2', {
    ResponseImpl: MockResponse,
    fetchImpl: mockFetch,
    ensureDaemonFn: async () => ({ ok: true }),
    skipLocalFonts: true,
  });
  assert.equal(missingFont.status, 404);
  assert.equal(missingFont.headers['Cache-Control'], 'no-store');

  // 5. Path traversal rejected with 404 no-store
  const traversalFont = await serveFontHandler('../secret.woff2', {
    ResponseImpl: MockResponse,
    fetchImpl: mockFetch,
    ensureDaemonFn: async () => ({ ok: true }),
  });
  assert.equal(traversalFont.status, 404);
  assert.equal(traversalFont.headers['Cache-Control'], 'no-store');

  // 6. Offline fallback for /api/state
  const stateOffline = await mockApp.apis.get('GET /api/state')({});
  assert.equal(stateOffline.success, false);
  assert.equal(stateOffline.status, 'offline');

  // 7. POST forwarding sets Content-Type: application/json and 30000ms timeout
  const swRes = await mockApp.apis.get('POST /api/switch')({ accountKey: 'user@example.com', noRestart: true });
  assert.equal(swRes.success, true);
  const swCall = calls.find((c) => c.url.endsWith('/api/switch'));
  assert.ok(swCall, 'Expected POST /api/switch call');
  assert.equal(swCall.opts.method, 'POST');
  assert.equal(swCall.opts.headers['Content-Type'], 'application/json');
  assert.equal(POST_TIMEOUT_MS, 30000);
  assert.equal(GET_TIMEOUT_MS, 5000);

  console.log('sidecar main.mjs self-tests passed.');
}

if (process.argv.includes('--test')) {
  await runSelfTests();
} else if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const { Response, SidecarApp } = await import('sidecar_sdk');
  const app = new SidecarApp();
  registerSidecarRoutes(app, { ResponseImpl: Response });
  app.run();
}
