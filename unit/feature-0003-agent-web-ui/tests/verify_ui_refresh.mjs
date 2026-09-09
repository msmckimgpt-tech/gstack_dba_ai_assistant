import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";

const root = new URL("../src/static/", import.meta.url);
const source = name => readFileSync(new URL(name, root), "utf8");
const { createUiRefresh } = await import(`data:text/javascript;base64,${Buffer.from(source("ui-refresh.js")).toString("base64")}`);
const storage = () => {
  const values = new Map();
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
};
const release = (generation, revision = "bbbbbbb", stamp = "bbbbbbbbbbbb") =>
  ({ status: "complete", generation, release: revision, asset_stamp: stamp });
let checks = 0;
const test = async (name, fn) => { await fn(); checks++; console.log(`PASS ${name}`); };

await test("completion waits for a safe point and applies once", async () => {
  let data = { status: "pending" }, safe = false, applied = 0, prepared = 0, notes = 0;
  const check = createUiRefresh({ stamp: "aaaaaaaaaaaa", storage: storage(),
    fetchRelease: async () => data, canApply: () => safe, prepare: () => { prepared++; },
    apply: () => { applied++; }, notify: () => { notes++; } });
  await check();
  data = release(1);
  await check(); await check();
  assert.equal(applied, 0); assert.equal(prepared, 0); assert.equal(notes, 1);
  safe = true;
  await check(); await check();
  assert.equal(applied, 1); assert.equal(prepared, 1);
});

await test("backend-only deployment reloads an already open page", async () => {
  let data = release(1, "aaaaaaa", "aaaaaaaaaaaa"), applied = 0;
  const check = createUiRefresh({ stamp: "aaaaaaaaaaaa", storage: storage(), fetchRelease: async () => data,
    canApply: () => true, prepare: () => true, apply: () => { applied++; } });
  await check(); await check(); assert.equal(applied, 0);
  data = release(2, "bbbbbbb", "aaaaaaaaaaaa");
  await check(); assert.equal(applied, 1);
});

await test("pending, offline, malformed and stale generations cannot reload", async () => {
  let data = release(5, "aaaaaaa", "aaaaaaaaaaaa"), applied = 0;
  const check = createUiRefresh({ stamp: "aaaaaaaaaaaa", storage: storage(), fetchRelease: async () => {
    if (data instanceof Error) throw data; return data;
  }, canApply: () => true, prepare: () => true, apply: () => { applied++; } });
  await check();
  for (const value of [new Error("offline"), { status: "pending" }, null, release(4),
    release(6, "javascript:alert(1)"), release(6, "bbbbbbb", "dev"), release(NaN), release(2**54)]) {
    data = value; await check();
  }
  assert.equal(applied, 0);
  data = release(7); await check(); assert.equal(applied, 1);
});

await test("input arriving during the request is protected", async () => {
  let resolve, safe = true, applied = 0, calls = 0;
  const check = createUiRefresh({ stamp: "aaaaaaaaaaaa", storage: storage(), fetchRelease: () => {
    calls++; return new Promise(done => { resolve = done; });
  }, canApply: () => safe, prepare: () => true, apply: () => { applied++; } });
  const pending = check(); await check();
  safe = false; resolve(release(1)); await pending;
  assert.equal(calls, 1); assert.equal(applied, 0);
});

await test("failed navigation is bounded across page instances", async () => {
  const store = storage(); let applied = 0;
  for (let attempt = 0; attempt < 4; attempt++) {
    const check = createUiRefresh({ stamp: "aaaaaaaaaaaa", storage: store, now: () => 5000,
      fetchRelease: async () => release(1), canApply: () => true, prepare: () => true,
      apply: () => { applied++; } });
    await check();
  }
  assert.equal(applied, 2);
});

await test("storage or snapshot failure cannot discard the current page", async () => {
  for (const prepare of [() => false, () => { throw Error("quota"); }]) {
    const check = createUiRefresh({ stamp: "aaaaaaaaaaaa", storage: storage(), fetchRelease: async () => release(1),
      canApply: () => true, prepare, apply: () => assert.fail("unexpected navigation") });
    await check();
  }
});

const require = createRequire(import.meta.url);
const { JSDOM } = require(require.resolve("jsdom", { paths: ["/tmp", process.cwd()] }));
const dom = new JSDOM('<textarea id="promptInput"></textarea>', { url: "https://fixture.local" });
dom.window.HTMLElement.prototype.getClientRects = function () { return this.hidden || this.classList.contains("hidden") ? [] : [{}]; };
const context = vm.createContext({ window: dom.window, document: dom.window.document, console,
  startUiRefresh: () => () => {}, captureAttachmentDiffState: () => null, restoreAttachmentDiffState: async () => {} });
vm.runInContext(source("app/deploy-refresh.js").replace(/^import .*;\n/gm, "").replace(/^export /gm, "")
  + "\nglobalThis.testApi = { appRefreshSafe, readAppRefreshResume };", context);
const api = context.testApi;
const safeState = () => ({ user: { id: 9 }, composerAttachments: { byConv: {} } });

await test("all conversation execution and attachment buckets block navigation", async () => {
  assert.equal(api.appRefreshSafe(safeState()), true);
  assert.equal(api.appRefreshSafe({ ...safeState(), composerAttachments: { byConv: { saved: { items: [{ id: 1, status: "ready", source: "session", selected: false }] } } } }), true);
  for (const patch of [ { busyConversations: new Set(["other"]) }, { myAskInFlight: new Set(["other"]) },
    { askAbortControllers: new Map([["other", {}]]) }, { pendingConversationEntries: new Map([["new", {}]]) },
    { composerAttachments: { byConv: { other: { items: [{ status: "ready", selected: true }] } } } },
    { composerAttachments: { uploadingCount: 1 } }, { composerAttachments: { lazyConvCreating: true } },
    { sidebarRenameDraft: {} }, { dqaDrag: {} }, { uiMutations: 1 } ]) {
    assert.equal(api.appRefreshSafe({ ...safeState(), ...patch }), false);
  }
});

await test("drafts and editing dialogs are protected; a restorable diff can update", async () => {
  const input = dom.window.document.querySelector("textarea");
  input.value = "SELECT private draft"; assert.equal(api.appRefreshSafe(safeState()), false);
  input.value = "";
  const dialog = dom.window.document.createElement("div"); dialog.setAttribute("role", "dialog");
  dom.window.document.body.append(dialog);
  assert.equal(api.appRefreshSafe(safeState()), false);
  dialog._dqaUiSnapshot = () => ({});
  assert.equal(api.appRefreshSafe(safeState()), true);
  dialog.remove();
});

await test("resume metadata is bound to the account and expires", async () => {
  const store = storage(); const key = "dqa.uiRefresh.resume.v1";
  store.setItem(key, JSON.stringify({ account: "9", at: Date.now(), conversationId: "mine" }));
  assert.equal(api.readAppRefreshResume({ id: 9 }, store).conversationId, "mine");
  assert.equal(api.readAppRefreshResume({ id: 10 }, store), null);
  assert.equal(store.getItem(key), null);
  store.setItem(key, JSON.stringify({ account: "9", at: Date.now() - 300001, conversationId: "mine" }));
  assert.equal(api.readAppRefreshResume({ id: 9 }, store), null);
});

console.log(`${checks} UI refresh scenarios PASS`);
