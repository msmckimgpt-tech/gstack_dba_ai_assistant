import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
let JSDOM;
try { ({JSDOM} = await import(process.env.DQA_JSDOM || "jsdom")); }
catch (error) {
  if (error.code !== "ERR_MODULE_NOT_FOUND") throw error;
  process.stderr.write("DOM verification requires node and jsdom (set DQA_JSDOM).\n");
  process.exit(2);
}
const root = process.argv[2];
const staticRoot = `${root}/unit/feature-0003-agent-web-ui/src/static`;
const source = readFileSync(`${staticRoot}/app/client-bridge.js`, "utf8");
const realTimeout = global.setTimeout;
const tick = () => new Promise((resolve) => realTimeout(resolve, 10));
const win = {id:"claude", name:"claude", where:"windows", path:"C:/claude.exe", usable:true};
const wsl = {id:"claude (WSL · Ubuntu · alice)", name:"claude", where:"wsl", distro:"Ubuntu", user:"alice", path:"/home/alice/bin/claude", usable:true};
const codex = {id:"codex (WSL · Ubuntu · root)", name:"codex", where:"wsl", distro:"Ubuntu", user:"root", path:"/root/bin/codex", usable:true};
let serial = 0;
async function scenario({runtimes=[win,codex], preferences={}, fail=false, tokenFail=false, legacy=false, progressive=false, standalone=false, coordinates=true, resident=true, bridgeGone=false, pendingAck=false, ackFailure=false}={}) {
  const dom = new JSDOM(readFileSync(`${staticRoot}/${standalone ? "ai-connect" : "index"}.html`, "utf8"), {url:"https://service.test/"+(coordinates?"?client_port=1234&client_nonce=secret":"")});
  for (const name of ["document","location","history","sessionStorage","URLSearchParams","Event","HTMLElement"]) global[name] = dom.window[name];
  global.window = dom.window;
  global.setInterval = () => 0;
  global.setTimeout = (fn, ms) => realTimeout(fn, ms === 2600 || ms === 800 ? 1 : ms);
  const calls = [], toasts = [], statuses = [], connected = new Map(), intervals = [];
  global.setInterval = (fn, ms) => { intervals.push({fn, ms}); return intervals.length; };
  let isResident = resident;
  let failure = fail, snapshots = 0, confirmed = !pendingAck;
  global.fetch = async (url, init) => {
    const action = String(url).split("/").pop();
    const body = JSON.parse(init.body || "{}");
    calls.push({url, action, body, headers:init.headers, credentials:init.credentials});
    if (bridgeGone && action !== "token") throw new Error("DQA 앱에 연결하지 못했습니다.");
    let result = {ok:true};
    if (action === "token") return {ok:!tokenFail, json:async()=>({connection_session:"fixture",launch:{protocol:"dqa-connect://start?token=fixture"}})};
    if (action === "status") result = {ok:true, resident:isResident, connection_session:"fixture", connections:[...connected.values()], client_features:legacy?[]:["platform_connections"]};
    if (action === "discover" || action === "discovery_status") {
      snapshots++;
      result = {ok:true,runtimes,preferences,discovering:progressive&&snapshots===1,
                completed_platforms:progressive&&snapshots===1?["codex"]:["claude","codex","gemini"]};
    }
    if (action === "connection_status") result = {ok:true,state:ackFailure?"failed":confirmed?"ready":"pending",detail:"fixture capability failure"};
    if (action === "connect") {
      result.pending = pendingAck;
      if (failure) result = {ok:false, detail:"fixture connection failure"};
      else connected.set(runtimes.find((r)=>r.id===body.id).name, runtimes.find((r)=>r.id===body.id));
    }
    if (action === "update_check") result = {ok:true,available:{version:"1.2.0"}};
    return {ok:true,json:async()=>result};
  };
  let attentions = 0;
  const mod = await import("data:text/javascript;base64,"+Buffer.from(source).toString("base64")+"#"+(serial++));
  assert.equal(mod.initClientPanel((m)=>statuses.push(m),(m)=>toasts.push(m),()=>attentions++),coordinates);
  await tick(); await tick();
  return {confirm:()=>{confirmed=true;},dom,mod,calls,toasts,statuses,connected,intervals,attention:()=>attentions,residency:(v)=>{isResident=v;},fail:()=>{failure=false;},doc:dom.window.document};
}
const results = {};
{
  const denied = {...codex, id:"codex (WSL · Ubuntu · blocked)", user:"blocked", usable:false, answers:false,
    logged_in:true, can_login_here:false, error_code:"permission_denied", detail:"실행 권한이 없습니다 (Permission denied)."};
  const s=await scenario({runtimes:[codex,denied],preferences:{codex:denied.id}});
  assert.deepEqual(s.calls.filter(c=>c.action==="connect").map(c=>c.body.id),[codex.id]);
  const card=s.doc.querySelector('[data-platform="codex"]');
  assert(card.textContent.includes("blocked") && card.textContent.includes("Permission denied"));
  assert.equal(card.querySelectorAll('input[type="radio"]').length,0);
  assert.equal(card.querySelectorAll('.connect-ai-unavailable button').length,0);
  const login=await scenario({runtimes:[{...codex,usable:false,logged_in:false,answers:null,can_login_here:true,detail:"로그인이 필요합니다."}]});
  assert(login.doc.querySelector('.connect-ai-unavailable button').textContent.includes("로그인"));
  results.denied_visible_but_never_connected=true;
}

{
  const s = await scenario();
  assert.deepEqual(s.calls.filter(c=>c.action==="connect").map(c=>c.body.id).sort(),[win.id,codex.id].sort());
  assert.equal(s.doc.querySelectorAll('input[type="radio"]').length,0);
  assert.equal(s.doc.querySelectorAll('[data-state="connected"]').length,2);
  assert.equal(s.toasts.length,2);
  const requests=s.calls.filter(c=>c.action==="token");
  assert(requests.every(c=>c.credentials==="same-origin"&&!c.headers?.["X-DQA-Nonce"]));
  assert(s.calls.filter(c=>c.action!=="token").every(c=>String(c.url).startsWith("http://127.0.0.1:1234/")&&c.headers["X-DQA-Nonce"]==="secret"));
  assert(!s.dom.window.location.search.includes("secret"));
  s.mod.initClientPanel(()=>{},()=>{});
  s.doc.getElementById("connectClientRefresh").click(); await tick();
  assert.equal(s.calls.filter(c=>c.action==="connect").length,2);
  results.unique_and_idempotent=true;
}
{
  const s=await scenario({runtimes:[win,wsl,codex]});
  assert.deepEqual(s.calls.filter(c=>c.action==="connect").map(c=>c.body.id),[codex.id]);
  assert.equal(s.doc.querySelectorAll('input[type="radio"]').length,2);
  assert(s.doc.querySelector('[data-platform="claude"]').textContent.includes("Ubuntu · alice"));
  const radio=[...s.doc.querySelectorAll('input[type="radio"]')].find(r=>r.value===wsl.id);
  radio.checked=true;radio.dispatchEvent(new s.dom.window.Event("change"));await tick();
  assert.equal(s.calls.filter(c=>c.action==="connect").at(-1).body.id,wsl.id);
  assert.equal(s.toasts.length,2);
  assert.equal(s.doc.getElementById("connectClientPanel").hidden,false);
  results.duplicates_are_local=true;
}
{
  const s=await scenario({runtimes:[win,wsl,codex],preferences:{claude:wsl.id}});
  assert.deepEqual(s.calls.filter(c=>c.action==="connect").map(c=>c.body.id).sort(),[wsl.id,codex.id].sort());
  [...s.doc.querySelectorAll('[data-platform="claude"] button')].find(b=>b.textContent==="위치 변경").click();
  const radio=[...s.doc.querySelectorAll('input[type="radio"]')].find(r=>r.value===win.id);
  radio.checked=true;radio.dispatchEvent(new s.dom.window.Event("change"));await tick();
  assert.equal(s.connected.get("claude").id,win.id);
  const missing=await scenario({runtimes:[win,wsl],preferences:{claude:"removed"}});
  assert.equal(missing.calls.filter(c=>c.action==="connect").length,0);
  results.cached_selection=true;
}
{
  const s=await scenario({fail:true,runtimes:[win]});
  assert.equal(s.toasts.length,0);
  assert.equal(s.doc.querySelector('[data-platform="claude"]').dataset.state,"error");
  s.fail();[...s.doc.querySelectorAll("button")].find(b=>b.textContent==="다시 연결").click();await tick();
  assert.equal(s.toasts.length,1);
  const denied=await scenario({tokenFail:true,runtimes:[win]});
  assert.equal(denied.calls.filter(c=>c.action==="connect").length,0);
  assert.equal(denied.toasts.length,0);
  assert.equal(denied.attention(),1);
  const unavailable=await scenario({bridgeGone:true});
  assert.equal(unavailable.attention(),1);
  results.failure_retry_and_auth=true;
}
{
  const s=await scenario({progressive:true});
  assert.equal(s.calls.filter(c=>c.action==="connect")[0].body.id,codex.id);
  results.progressive=true;
}
{
  const s=await scenario({legacy:true});
  assert.equal(s.calls.filter(c=>c.action==="connect").length,0);
  s.doc.getElementById("connectClientUpdate").click();await tick();
  assert(s.calls.some(c=>c.action==="update_apply"));
  results.old_client_upgrade=true;
}
{
  const s=await scenario({standalone:true});
  assert.equal(s.calls.filter(c=>c.action==="connect").length,2);
  assert.equal(s.doc.querySelectorAll('[data-state="connected"]').length,2);
  results.standalone_parity=true;
}
{
  const s = await scenario({coordinates:false});
  assert.equal(s.calls.length,0); assert.equal(s.doc.getElementById("connectClientPanel").hidden,true);
  assert.equal(await s.mod.bridgeCall("connect", {}),null);
  results.web_without_client=true;
}
{
  const s = await scenario({standalone:true});
  assert(s.doc.getElementById("connectClientResidency").textContent.includes("닫아도"));
  assert(s.calls.findIndex(c=>c.action==="status") < s.calls.findIndex(c=>c.action==="discover"));
  s.residency(false); s.intervals[0].fn(); await tick();
  assert(s.doc.getElementById("connectClientResidency").textContent.includes("닫으면"));
  assert(s.intervals[0].ms <= 30000);
  const gone = await scenario({bridgeGone:true});
  assert(gone.statuses.some(m=>m.includes("연결하지 못했습니다")));
  assert.equal(gone.toasts.length,0);
  results.residency_and_failure=true;
}
{
  const s = await scenario({runtimes:[win,wsl,codex]});
  assert.equal(s.attention(),1);
  s.mod.suspendClientPanel();
  const before = s.calls.length;
  s.doc.getElementById("connectClientRefresh").click(); await tick();
  assert.equal(s.calls.length,before);
  s.mod.restartClientPanel(); await tick();
  assert(s.calls.length>before);
  results.session_lifecycle=true;
}
{
  const s=await scenario({runtimes:[win],pendingAck:true});
  assert.equal(s.toasts.length,0);
  assert.equal(s.doc.querySelector('[data-platform="claude"]').dataset.state,"connecting");
  s.confirm();await tick();await tick();assert.equal(s.toasts.length,1);
  const f=await scenario({runtimes:[win],pendingAck:true,ackFailure:true});
  assert.equal(f.toasts.length,0);
  assert.equal(f.doc.querySelector('[data-platform="claude"]').dataset.state,"error");
  results.confirm_before_toast=true;
}
console.log(JSON.stringify(results));
