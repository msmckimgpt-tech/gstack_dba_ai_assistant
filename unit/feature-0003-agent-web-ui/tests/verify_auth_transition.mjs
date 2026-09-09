// Execute production startup and auth presentation functions against the real HTML.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const require = createRequire(import.meta.url);
const { parse } = require('acorn');
const { JSDOM } = require(require.resolve('jsdom', { paths: ['/tmp', process.cwd()] }));
const base = new URL('../src/static/', import.meta.url);
const source = name => readFileSync(new URL(name, base), 'utf8');
function fn(file, name) {
  const code = source(file);
  const node = parse(code, { ecmaVersion: 'latest', sourceType: 'module' }).body
    .map(n => n.declaration || n).find(n => n.type === 'FunctionDeclaration' && n.id.name === name);
  assert.ok(node, `${name} exists in production source`);
  return code.slice(node.start, node.end);
}
const authFunctions = ['showAuthOverlay', 'hideAuthOverlay', 'showStartupPending', 'showStartupError', 'consumeNextTarget'];
const production = authFunctions.map(n => fn('app/auth.js', n)).join('\n')
  + '\n' + fn('app/next-target.js', 'safeNextTarget')
  + '\n' + fn('app.js', 'restoreSession');
const html = source('index.html');
const session = { authenticated: true, user: { username: 'fixture' }, products: [] };
let passed = 0;
function check(label, action) { action(); passed++; console.log('PASS ' + label); }
function fixture({ search = '', api = async () => session, workspace = async () => {} } = {}) {
  const dom = new JSDOM(html, { url: 'https://example.invalid/' + search });
  const document = dom.window.document;
  let destination;
  const context = vm.createContext({
    document, URL, URLSearchParams, state: {},
    window: { location: { search, origin: 'https://example.invalid', replace: v => { destination = v; } } },
    authOverlayEl: document.getElementById('authOverlay'),
    apiFetch: api, initializeWorkspace: workspace,
    refreshOAuthLoginButtons() {}, showOAuthErrorIfPresent() {},
    loadVaultOptions: async () => {}, renderAccountState() {}, renderAccessNotice() {}, renderComposer() {},
  });
  vm.runInContext(production, context);
  const visible = id => !document.getElementById(id).classList.contains('hidden');
  return { context, document, visible, destination: () => destination, close: () => dom.window.close() };
}

let f = fixture();
check('HTML hides login before any JavaScript or session response', () => assert.equal(f.visible('authOverlay'), false));
check('HTML provides pending status and blocks workspace input', () => {
  assert.ok(f.visible('startupOverlay'));
  assert.ok(f.document.getElementById('appFrame').hasAttribute('inert'));
});
f.close();

let resolveSession, resolveWorkspace, suppliedSession, apiCalls = 0;
f = fixture({
  api: () => { apiCalls++; return new Promise(r => { resolveSession = r; }); },
  workspace: value => { suppliedSession = value; return new Promise(r => { resolveWorkspace = r; }); },
});
const restore = f.context.restoreSession();
check('delayed session never shows login', () => assert.equal(f.visible('authOverlay'), false));
resolveSession(session);
await new Promise(r => setImmediate(r));
check('delayed workspace keeps pending, not login', () => {
  assert.ok(f.visible('startupOverlay'));
  assert.equal(f.visible('authOverlay'), false);
});
resolveWorkspace(); await restore;
check('authenticated workspace is usable and reuses the validated session', () => {
  assert.equal(f.visible('startupOverlay'), false);
  assert.equal(f.visible('authOverlay'), false);
  assert.equal(f.document.getElementById('appFrame').inert, false);
  assert.equal(suppliedSession, session);
  assert.equal(apiCalls, 1);
});
f.context.showAuthOverlay();
check('explicit logout still shows login and blocks workspace', () => {
  assert.ok(f.visible('authOverlay'));
  assert.equal(f.document.getElementById('appFrame').inert, true);
});
f.close();

for (const [label, api, workspace, login] of [
  ['signed out', async () => ({ authenticated: false }), async () => { throw Error('must not initialize'); }, true],
  ['expired HTTP 401', async () => { throw Object.assign(Error('expired'), { status: 401 }); }, async () => {}, true],
  ['server HTTP 500', async () => { throw Object.assign(Error('server'), { status: 500 }); }, async () => {}, false],
  ['network failure', async () => { throw TypeError('network'); }, async () => {}, false],
  ['workspace failure', async () => session, async () => { throw Error('workspace'); }, false],
  ['workspace session expiration', async () => session, async () => { throw Object.assign(Error('expired'), { status: 401 }); }, true],
]) {
  f = fixture({ api, workspace });
  await f.context.restoreSession();
  check(label + ' selects the correct screen', () => {
    assert.equal(f.visible('authOverlay'), login);
    assert.equal(f.visible('startupOverlay'), !login);
    assert.equal(f.visible('startupRetryBtn'), !login);
    assert.equal(f.document.getElementById('appFrame').inert, true);
    if (!login) assert.equal(f.document.activeElement.id, 'startupRetryBtn');
  });
  if (!login) {
    f.context.apiFetch = async () => session;
    f.context.initializeWorkspace = async () => {};
    await f.context.restoreSession();
    check(label + ' recovers on retry without login', () => {
      assert.equal(f.visible('authOverlay'), false);
      assert.equal(f.visible('startupOverlay'), false);
      assert.equal(f.document.getElementById('appFrame').inert, false);
    });
  }
  f.close();
}
for (const forced of [false, true]) {
  let workspaceCalls = 0;
  f = fixture({ search: '?next=/ai/connect',
    api: async () => ({ ...session, user: { must_change_password: forced } }),
    workspace: async () => { workspaceCalls++; },
  });
  await f.context.restoreSession();
  check('next uses current password-change requirement: ' + forced, () => {
    assert.equal(Boolean(f.destination()), !forced);
    assert.equal(workspaceCalls, forced ? 1 : 0);
    assert.equal(f.visible('authOverlay'), false);
  });
  f.close();
}

// Exercise the production workspace body, including failures after conversation loading.
function workspaceFixture({ search = '', user = session.user, refresh, askStatus = async () => ({ is_processing: false }) } = {}) {
  const workspaceSession = { ...session, user };
  const result = fixture({ search, api: async () => workspaceSession });
  const { context } = result;
  Object.assign(context.window.location, { pathname: '/' });
  context.window.history = {
    replaceState(_state, _title, target) {
      const url = new URL(target, 'https://example.invalid');
      context.window.location.search = url.search;
    },
  };
  Object.assign(context, {
    _branchViewCacheClear() {}, applyLlmProviderStatus() {}, startLlmHealthPolling() {}, pollLlmHealth() {},
    restartClientPanel() {}, applyProductHydration() {},
    refreshWorkspace: refresh || (async id => { context.state.activeConversationId = id; }),
    fetchAskStatus: askStatus,
  });
  vm.runInContext(fn('app/auth.js', 'showForceChangePasswordModal')
    + '\n' + fn('app.js', 'initializeWorkspace'), context);
  return result;
}

const destinations = [];
f = workspaceFixture({
  search: '?conversation=target-123',
  refresh: async (id, options) => {
    destinations.push({ id, allowCurrentFallback: options.allowCurrentFallback });
    if (destinations.length === 1) throw Object.assign(Error('conversation loading failed'), { status: 503 });
    f.context.state.activeConversationId = id;
  },
});
await f.context.restoreSession();
check('failed workspace preserves the requested conversation for retry', () => {
  assert.equal(f.context.window.location.search, '?conversation=target-123');
  assert.ok(f.visible('startupRetryBtn'));
  assert.equal(f.visible('authOverlay'), false);
});
await f.context.restoreSession();
check('workspace retry opens the original conversation and then cleans its URL', () => {
  assert.deepEqual(destinations, [
    { id: 'target-123', allowCurrentFallback: true },
    { id: 'target-123', allowCurrentFallback: true },
  ]);
  assert.equal(f.context.state.activeConversationId, 'target-123');
  assert.equal(f.context.window.location.search, '');
  assert.equal(f.visible('startupOverlay'), false);
});
f.close();

for (const status of [503, 401]) {
  f = workspaceFixture({
    search: '?conversation=password-change-target',
    user: { ...session.user, must_change_password: true },
    askStatus: async () => { throw Object.assign(Error('last startup request failed'), { status }); },
  });
  await f.context.restoreSession();
  check(`late workspace HTTP ${status} cannot leave a password modal over recovery`, () => {
    assert.equal(f.document.getElementById('forceChangePasswordModal'), null);
    assert.equal(f.visible('authOverlay'), status === 401);
    assert.equal(f.visible('startupRetryBtn'), status !== 401);
    assert.equal(f.context.window.location.search, '?conversation=password-change-target');
    if (status !== 401) assert.equal(f.document.activeElement.id, 'startupRetryBtn');
  });
  let finishStatus;
  f.context.fetchAskStatus = () => new Promise(resolve => { finishStatus = resolve; });
  const recovery = f.context.restoreSession();
  await new Promise(resolve => setImmediate(resolve));
  check(`recovery after HTTP ${status} waits for the last request before showing the password modal`, () => {
    assert.equal(typeof finishStatus, 'function');
    assert.equal(f.document.getElementById('forceChangePasswordModal'), null);
    assert.ok(f.visible('startupOverlay'));
    assert.equal(f.visible('authOverlay'), false);
  });
  finishStatus({ is_processing: false });
  await recovery;
  check(`successful recovery after HTTP ${status} presents the required password change`, () => {
    assert.ok(f.document.getElementById('forceChangePasswordModal'));
    assert.equal(f.visible('startupOverlay'), false);
    assert.equal(f.visible('authOverlay'), false);
    assert.equal(f.context.window.location.search, '');
  });
  f.close();
}

for (const method of ['password', 'totp', 'signup']) {
  for (const outcome of ['success', 'failure']) {
    const user = { ...session.user, must_change_password: method !== 'signup' };
    const freshSession = { ...session, user };
    f = workspaceFixture({ user });
    let finishSession, failSession, sessionRequests = 0;
    const authRequests = [];
    Object.assign(f.context, {
      loginErrorEl: f.document.getElementById('loginError'),
      signupErrorEl: f.document.getElementById('signupError'),
      showToast() {},
      apiFetch: async (url, options) => {
        if (url === '/api/session') {
          sessionRequests++;
          if (sessionRequests === 1) return new Promise((resolve, reject) => {
            finishSession = resolve; failSession = reject;
          });
          return freshSession;
        }
        assert.equal(options.method, 'POST');
        authRequests.push(url);
        if (url === '/api/auth/login' && method === 'totp') {
          return { totp_required: true, totp_token: 'fixture-token' };
        }
        assert.ok(['/api/auth/login', '/api/auth/login/totp', '/api/auth/signup'].includes(url));
        return { user };
      },
    });
    vm.runInContext(['handleLogin', 'showTotpLoginPrompt', 'handleSignup']
      .map(name => fn('app/auth.js', name)).join('\n'), f.context);
    f.context.showAuthOverlay();
    let submission;
    if (method === 'signup') {
      submission = f.context.handleSignup({ preventDefault() {} });
    } else if (method === 'totp') {
      await f.context.handleLogin({ preventDefault() {} });
      f.document.getElementById('totpLoginCode').value = '123456';
      f.document.getElementById('totpLoginSubmit').click();
    } else {
      submission = f.context.handleLogin({ preventDefault() {} });
    }
    await new Promise(resolve => setImmediate(resolve));
    check(`${method} authentication keeps pending during delayed session (${outcome})`, () => {
      assert.equal(typeof finishSession, 'function');
      assert.ok(f.visible('startupOverlay'));
      assert.equal(f.visible('authOverlay'), false);
      assert.equal(f.document.getElementById('appFrame').inert, true);
      assert.equal(f.document.getElementById('totpLoginModal'), null);
      assert.equal(f.document.getElementById('forceChangePasswordModal'), null);
    });
    if (outcome === 'failure') failSession(Object.assign(Error('session temporarily unavailable'), { status: 503 }));
    else finishSession(freshSession);
    await submission;
    await new Promise(resolve => setImmediate(resolve));
    if (outcome === 'failure') {
      check(`${method} authentication session failure exposes usable recovery`, () => {
        assert.ok(f.visible('startupOverlay'));
        assert.ok(f.visible('startupRetryBtn'));
        assert.equal(f.document.activeElement.id, 'startupRetryBtn');
        assert.equal(f.visible('authOverlay'), false);
        assert.equal(f.document.getElementById('appFrame').inert, true);
        assert.equal(f.document.getElementById('forceChangePasswordModal'), null);
        assert.equal(f.context.loginErrorEl.textContent, '');
        assert.equal(f.context.signupErrorEl.textContent, '');
      });
      await f.context.restoreSession();
    }
    check(`${method} authentication finishes ${outcome === 'failure' ? 'retry' : 'startup'} with the required password-change state`, () => {
      assert.equal(f.visible('startupOverlay'), false);
      assert.equal(f.visible('authOverlay'), false);
      assert.equal(f.document.getElementById('appFrame').inert, false);
      assert.equal(Boolean(f.document.getElementById('forceChangePasswordModal')), user.must_change_password);
      assert.equal(sessionRequests, outcome === 'failure' ? 2 : 1);
      assert.deepEqual(authRequests, method === 'totp'
        ? ['/api/auth/login', '/api/auth/login/totp']
        : [method === 'signup' ? '/api/auth/signup' : '/api/auth/login']);
    });
    f.close();
  }
}

// Prepare the same production functions for the isolated native WebView2 fixture.
if (process.env.AUTH_TRANSITION_FIXTURE) {
  const { writeFileSync } = await import('node:fs');
  writeFileSync(process.env.AUTH_TRANSITION_FIXTURE, production);
}
console.log(`${passed} passed`);
