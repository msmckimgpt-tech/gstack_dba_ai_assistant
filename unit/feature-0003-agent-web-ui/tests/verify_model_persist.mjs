// verify_model_persist.mjs
// feature-0003 model-persist:
//   대화 중 assistant 에게 **마지막으로 요청했던 모델**을 새로고침·대화 복귀 후에도 보존하고,
//   '+ 새 대화'는 세션 기본값(API_DEFAULT_MODEL=claude-haiku-4)에서 시작한다(사용자 요구).
//
//   서버측 계약(KV 저장 + /api/history 반환)은 tests/test_model_persist.py 가 검증한다.
//   본 파일은 프론트의 두 축을 검증한다:
//     G*  _modelHydrationShouldSkip — 미전송 선택 보존 vs 대화 복귀 시 저장값 복원 판정(순수 함수).
//     M*  _composerCurrentModel     — selectedModel 이 비면 세션 기본값으로 폴백(신규 대화 = haiku).
//     S*  구조 계약 — loadHistory hydration / '+ 새 대화' 리셋 / 모델 로컬 미러 부재.
//
//   순수 로직(DOM 무의존)이라 jsdom 불필요. 실제 화면 정본은 PB-0008 Windows-browser.
//
// 실행: node verify_model_persist.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const appJs = readFileSync(join(STATIC, "app.js"), "utf8");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// app.js 의 함수 선언(`function name(`)을 paren/brace 매칭으로 추출.
function extractFn(src, name) {
  const start = src.indexOf(`function ${name}(`);
  if (start < 0) return null;
  let paren = 0, sigEnd = -1;
  for (let j = src.indexOf("(", start); j < src.length; j++) {
    if (src[j] === "(") paren++;
    else if (src[j] === ")") { paren--; if (paren === 0) { sigEnd = j; break; } }
  }
  let depth = 0, end = -1;
  for (let i = src.indexOf("{", sigEnd); i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  return src.slice(start, end);
}

const srcSkip = extractFn(appJs, "_modelHydrationShouldSkip");
const srcCurrent = extractFn(appJs, "_composerCurrentModel");
const srcReset = extractFn(appJs, "_resetComposerModelSelection");
const srcShouldSend = extractFn(appJs, "_shouldSendModelField");
// conversation_audit 2026-07-28 (FR-model-pick-lost-on-early-cid): pending→early-cid 승계 + 무음 강등 감지.
const srcAdopt = extractFn(appJs, "_adoptComposerModelPickToConv");
const srcDropped = extractFn(appJs, "_modelSelectionSilentlyDropped");
ok("[추출] 순수 함수 6종(hydrationSkip·currentModel·reset·shouldSend·adoptPick·silentlyDropped)",
  Boolean(srcSkip && srcCurrent && srcReset && srcShouldSend && srcAdopt && srcDropped));

// `state` 를 주입 가능한 형태로 함수들을 재구성한다(_composerCurrentModel 은 전역 state 참조).
const factory = new Function("state",
  `${srcSkip}\n${srcCurrent}\n${srcReset}\n${srcShouldSend}\n${srcAdopt}\n${srcDropped}\n`
  + "return { _modelHydrationShouldSkip, _composerCurrentModel, _resetComposerModelSelection,"
  + " _shouldSendModelField, _adoptComposerModelPickToConv, _modelSelectionSilentlyDropped };");

function newState(patch = {}) {
  return {
    selectedModel: null,
    _modelPickedAt: 0,
    _modelPickedForConvId: null,
    _modelHydratedAt: 0,
    session: { default_model: "claude-haiku-4" },
    modelCatalog: { default_model: "claude-haiku-4" },
    ...patch,
  };
}

// ── G: hydration skip 판정 ─────────────────────────────────────────────────────

// G1: 아무 선택도 없던 초기 상태 → hydration 수행(저장값 복원).
{
  const st = newState();
  const { _modelHydrationShouldSkip: skip } = factory(st);
  ok("G1 초기 상태는 hydration 수행(새로고침 후 저장값 복원)", skip(st, "conv-1") === false);
}

// G2: 같은 대화에서 마지막 hydration 이후 선택 → skip(미전송 선택 보존).
{
  const st = newState({ _modelPickedForConvId: "conv-1", _modelPickedAt: 200, _modelHydratedAt: 100 });
  const { _modelHydrationShouldSkip: skip } = factory(st);
  ok("G2 같은 대화의 미전송 선택은 주기 재로드가 되돌리지 않는다", skip(st, "conv-1") === true);
}

// G3: 다른 대화로 전환 → 그 대화의 저장값으로 hydration.
{
  const st = newState({ _modelPickedForConvId: "conv-1", _modelPickedAt: 200, _modelHydratedAt: 100 });
  const { _modelHydrationShouldSkip: skip } = factory(st);
  ok("G3 다른 대화 로드는 그 대화의 저장 모델로 hydration", skip(st, "conv-2") === false);
}

// G4: conv-1 → conv-2(hydration 으로 _modelHydratedAt 전진) → conv-1 복귀 → 저장값 복원.
{
  const st = newState({ _modelPickedForConvId: "conv-1", _modelPickedAt: 200, _modelHydratedAt: 300 });
  const { _modelHydrationShouldSkip: skip } = factory(st);
  ok("G4 다른 대화를 들렀다 돌아오면 저장값(마지막 요청 모델)이 복원된다", skip(st, "conv-1") === false);
}

// G5: pending(미생성) 컨텍스트에서의 선택(convId="")이 실 대화 로드를 막지 않는다.
{
  const st = newState({ _modelPickedForConvId: "", _modelPickedAt: 200, _modelHydratedAt: 100 });
  const { _modelHydrationShouldSkip: skip } = factory(st);
  ok("G5 pending 선택이 실 대화 hydration 을 가로막지 않는다", skip(st, "conv-9") === false);
}

// ── M: 현재 모델 결정(신규 대화 기본값) ─────────────────────────────────────────

// M1: selectedModel=null → 세션 기본값(haiku).
{
  const st = newState();
  const { _composerCurrentModel: cur } = factory(st);
  ok("M1 선택 없음 → 세션 기본값 haiku('+ 새 대화' 계약)", cur() === "claude-haiku-4");
}

// M2: 복원된 selectedModel 이 세션 기본값보다 우선.
{
  const st = newState({ selectedModel: "claude-sonnet-4" });
  const { _composerCurrentModel: cur } = factory(st);
  ok("M2 복원된 대화 모델이 기본값보다 우선", cur() === "claude-sonnet-4");
}

// ── R: 리셋 헬퍼 + 대화 컨텍스트 이탈 경로(적대 리뷰 B1/C1) ──────────────────────

// R1: 리셋은 선택과 픽 마커를 모두 비운다 → 이후 hydration 이 가드에 걸리지 않는다.
{
  const st = newState({ selectedModel: "claude-opus-4", _modelPickedForConvId: "conv-1", _modelPickedAt: 500 });
  const { _resetComposerModelSelection: reset, _composerCurrentModel: cur, _modelHydrationShouldSkip: skip } = factory(st);
  reset(st);
  ok("R1 리셋 후 현재 모델 = 세션 기본값 haiku", cur() === "claude-haiku-4");
  ok("R1b 리셋 후 픽 마커 해제 → 다음 hydration 정상 수행", skip(st, "conv-1") === false);
}

// R2: 리셋은 hydration 시각을 되돌리지 않는다(단조 전진 — 과거 픽이 되살아나지 않게).
{
  const st = newState({ _modelHydratedAt: 900 });
  const { _resetComposerModelSelection: reset } = factory(st);
  reset(st);
  ok("R2 _modelHydratedAt 은 리셋 대상이 아니다", st._modelHydratedAt === 900);
}

// R3: 대화 컨텍스트를 떠나는 4개 경로가 모두 리셋 헬퍼를 호출한다(B1/C1 재발 방지).
{
  const callSites = [
    ["beginPendingConversation('+ 새 대화')", "beginPendingConversation"],
    ["selectConversation(대화 전환 대기 창)", "selectConversation"],
    ["handleLogout(계정 경계)", "handleLogout"],
  ];
  for (const [label, fnName] of callSites) {
    const fn = extractFn(appJs, fnName);
    ok(`R3 ${label} 가 _resetComposerModelSelection 호출`,
      Boolean(fn) && /_resetComposerModelSelection\(state\)/.test(fn));
  }
  // loadHistory 는 대형 async 함수라 본문 전체 대신 '활성 대화 없음' early-return 블록만 검사.
  const lh = extractFn(appJs, "loadHistory");
  const earlyBlock = lh ? lh.slice(0, lh.indexOf("const params")) : "";
  ok("R3 loadHistory 활성 대화 없음 분기가 _resetComposerModelSelection 호출",
    /_resetComposerModelSelection\(state\)/.test(earlyBlock));
  // 2R 적대 리뷰 B-B: 이 분기는 랜딩/pending 에 '머무는 동안' 반복 호출되므로 반드시 가드된
  // 호출이어야 한다(무조건 리셋 = 미전송 선택 소실). 가드 없는 호출로 회귀하면 실패한다.
  ok("R3b loadHistory 랜딩 분기 리셋은 미전송 선택 가드를 통과한 경우에만",
    /if\s*\(!_modelHydrationShouldSkip\(state,\s*""\)\)\s*_resetComposerModelSelection\(state\)/
      .test(earlyBlock));
}

// R4: '+ 새 대화'에서 고른(미전송) 모델은 랜딩 상태 재로드(refreshWorkspace→loadHistory)에도 살아남는다.
{
  const st = newState({ selectedModel: "claude-sonnet-4", _modelPickedForConvId: "", _modelPickedAt: 700, _modelHydratedAt: 100 });
  const { _modelHydrationShouldSkip: skip } = factory(st);
  ok("R4 pending/랜딩 컨텍스트의 미전송 선택은 재로드에도 보존", skip(st, "") === true);
}

// R5: 랜딩으로 '진입'하는 경우(직전 대화에서 hydration 되었거나 그 대화에서 고른 값)는 리셋된다.
{
  const stHydrated = newState({ selectedModel: "claude-sonnet-4", _modelHydratedAt: 500 });
  const { _modelHydrationShouldSkip: skipA } = factory(stHydrated);
  ok("R5a 직전 대화에서 hydration 된 값은 랜딩 진입 시 리셋 대상", skipA(stHydrated, "") === false);
  const stPickedElsewhere = newState({ _modelPickedForConvId: "conv-A", _modelPickedAt: 700, _modelHydratedAt: 100 });
  const { _modelHydrationShouldSkip: skipB } = factory(stPickedElsewhere);
  ok("R5b 다른 대화에서 고른 값도 랜딩 진입 시 리셋 대상", skipB(stPickedElsewhere, "") === false);
}

// ── D: 전송 시 model 필드 동봉 판정(적대 리뷰 C-A — 저장값 clobber 차단) ─────────
{
  const st = newState();
  const { _shouldSendModelField: send } = factory(st);
  ok("D1 신규 대화(lazy-create)는 항상 동봉(덮어쓸 저장값 없음)", send(st, "", true) === true);

  const stPicked = newState({ _modelPickedForConvId: "conv-A" });
  const { _shouldSendModelField: sendB } = factory(stPicked);
  ok("D2 이 대화에서 명시로 고른 경우 동봉(진짜 선택은 기록)", sendB(stPicked, "conv-A", false) === true);

  const stHyd = newState({ _modelHydratedForConvId: "conv-A" });
  const { _shouldSendModelField: sendC } = factory(stHyd);
  ok("D3 이 대화를 hydration 한 경우 동봉(화면 값이 그 대화 기준)", sendC(stHyd, "conv-A", false) === true);

  const stDesync = newState({ _modelHydratedForConvId: "conv-B", _modelPickedForConvId: "conv-B" });
  const { _shouldSendModelField: sendD } = factory(stDesync);
  ok("D4 hydration 안 된 대화로는 미동봉(서버가 기존 저장값 보존)",
    sendD(stDesync, "conv-A", false) === false);
}

// ── E: pending → early-cid 귀속 승계 ──────────────────────────────────────────
// conversation_audit 2026-07-28 FR-model-pick-lost-on-early-cid 회귀 가드.
// 라이브 실측 결함: 사용자가 새 대화(pending)에서 sonnet 을 고른 뒤 **첨부파일을 올리면**
// early-cid 가 발급되며 activeConversationId 가 실 cid 로 바뀐다. 그때 선택 귀속
// (_modelPickedForConvId="")을 승계하지 않아 _shouldSendModelField 가 false → askBody.model
// 누락 → 서버가 API_DEFAULT_MODEL(haiku)로 채움 → 화면은 sonnet, 실행은 haiku(조용한 강등).
{
  // E1: 결함 재현 — 승계 전에는 미동봉(이 단정이 깨지면 결함 전제가 바뀐 것).
  const stBefore = newState({ selectedModel: "claude-sonnet-4", _modelPickedForConvId: "", _modelPickedAt: 900 });
  const { _shouldSendModelField: sendBefore } = factory(stBefore);
  ok("E1 [결함 재현] pending 선택을 승계하지 않으면 실 cid 전송에 model 미동봉",
    sendBefore(stBefore, "conv-early", false) === false);

  // E2: 승계 후에는 동봉 — 사용자가 고른 모델이 그대로 전송된다(수정의 핵심 단정).
  const stAfter = newState({ selectedModel: "claude-sonnet-4", _modelPickedForConvId: "", _modelPickedAt: 900 });
  const { _adoptComposerModelPickToConv: adopt, _shouldSendModelField: sendAfter } = factory(stAfter);
  ok("E2 pending(빈 귀속) 선택은 early-cid 로 승계된다", adopt(stAfter, "conv-early", null) === true);
  ok("E2b 승계 후 실 cid 전송에 model 동봉(선택 모델이 강등되지 않음)",
    sendAfter(stAfter, "conv-early", false) === true);
  ok("E2c 승계는 귀속만 바꾸고 선택값 자체는 보존", stAfter.selectedModel === "claude-sonnet-4");

  // E3: 선택하지 않은 상태(null)는 승계 대상이 아니다 — 리셋 semantics 보존
  //     ('+ 새 대화'는 haiku 로 시작한다는 계약을 승계가 우회하지 않는다).
  const stNull = newState({ _modelPickedForConvId: null });
  const { _adoptComposerModelPickToConv: adoptNull, _shouldSendModelField: sendNull } = factory(stNull);
  ok("E3 미선택(null)은 승계하지 않음(새 대화 기본값 계약 보존)",
    adoptNull(stNull, "conv-early", null) === false && stNull._modelPickedForConvId === null);
  ok("E3b 미선택이면 실 cid 전송은 여전히 미동봉", sendNull(stNull, "conv-early", false) === false);

  // E4: pendingSentinel 키에 귀속된 선택도 승계(sendPrompt 경로는 busyKey=sentinel 을 넘긴다).
  const stSentinel = newState({ selectedModel: "claude-opus-5", _modelPickedForConvId: "pending-42" });
  const { _adoptComposerModelPickToConv: adoptSent } = factory(stSentinel);
  ok("E4 pendingSentinel 귀속 선택도 승계", adoptSent(stSentinel, "conv-early", "pending-42") === true);
  ok("E4b 승계 결과가 새 cid", stSentinel._modelPickedForConvId === "conv-early");

  // E5: 다른 **실 대화**에서 고른 값은 승계 금지 — 오귀속(직전 대화 선택 누출) 차단.
  const stOther = newState({ selectedModel: "claude-sonnet-4", _modelPickedForConvId: "conv-B" });
  const { _adoptComposerModelPickToConv: adoptOther } = factory(stOther);
  ok("E5 다른 대화 귀속 선택은 승계하지 않음(오귀속 차단)",
    adoptOther(stOther, "conv-early", "pending-9") === false && stOther._modelPickedForConvId === "conv-B");

  // E6: cid 미발급이면 no-op(빈 문자열로 귀속을 덮지 않는다).
  const stNoCid = newState({ _modelPickedForConvId: "" });
  const { _adoptComposerModelPickToConv: adoptNoCid } = factory(stNoCid);
  ok("E6 새 cid 가 없으면 no-op", adoptNoCid(stNoCid, "", null) === false && stNoCid._modelPickedForConvId === "");
}

// ── W: 표시-집행 불일치(조용한 강등) 감지 ─────────────────────────────────────
{
  const stDrop = newState({ selectedModel: "claude-sonnet-4", _modelPickedForConvId: "" });
  const { _modelSelectionSilentlyDropped: dropA } = factory(stDrop);
  ok("W1 명시 선택이 있는데 미동봉이면 무음 강등으로 감지",
    dropA(stDrop, "conv-early", false) === true);

  const stNoPick = newState({ selectedModel: null, _modelPickedForConvId: "" });
  const { _modelSelectionSilentlyDropped: dropB } = factory(stNoPick);
  ok("W2 선택이 없으면(기본값 사용) 강등이 아님 — 오탐 없음",
    dropB(stNoPick, "conv-early", false) === false);

  const stSent = newState({ selectedModel: "claude-sonnet-4", _modelPickedForConvId: "conv-A" });
  const { _modelSelectionSilentlyDropped: dropC } = factory(stSent);
  ok("W3 동봉되는 경우는 강등이 아님", dropC(stSent, "conv-A", false) === false);

  const stLazy = newState({ selectedModel: "claude-sonnet-4", _modelPickedForConvId: "" });
  const { _modelSelectionSilentlyDropped: dropD } = factory(stLazy);
  ok("W4 lazy-create 는 항상 동봉이라 강등이 아님", dropD(stLazy, "", true) === false);
}

// ── S: 구조 계약 ───────────────────────────────────────────────────────────────

// S1: loadHistory 가 payload.model 로 selectedModel 을 hydration + hydration 시각 전진.
{
  const hasHydration = /state\.selectedModel\s*=\s*_pm\s*\|\|\s*null/.test(appJs)
    && /payload\.model/.test(appJs)
    && /state\._modelHydratedAt\s*=\s*Date\.now\(\)/.test(appJs);
  ok("S1 loadHistory 가 payload.model 로 모델 선택기를 hydration", hasHydration);
}

// S2: 리셋 헬퍼가 selectedModel 과 두 픽 마커를 모두 비운다(구현 계약).
{
  ok("S2 리셋 헬퍼가 선택 + 픽 마커 3종을 모두 비운다",
    Boolean(srcReset)
    && /state\.selectedModel\s*=\s*null/.test(srcReset)
    && /state\._modelPickedAt\s*=\s*0/.test(srcReset)
    && /state\._modelPickedForConvId\s*=\s*null/.test(srcReset));
}

// S3: 모델은 localStorage 미러를 두지 않는다 — 두면 '+ 새 대화'가 직전 모델을 물려받아
//     "새 대화는 haiku" 요구를 깬다(추론 강도는 미러가 있으나 요구가 반대라 의도적 비대칭).
//     검출기는 "localStorage 접근과 같은 줄에 model 어휘" 를 넓게 훑는다(키 이름 무관).
{
  const mirrorLines = appJs.split("\n").filter(
    (ln) => /localStorage\.(get|set)Item/.test(ln) && /model/i.test(ln));
  ok("S3 모델 선택에는 localStorage 미러가 없다(새 대화 상속 방지)",
    mirrorLines.length === 0);
  // 검출기 자체가 죽어 있지 않은지 확인(추론 강도 미러는 실제로 존재해야 한다 — 대조군).
  const reasoningMirror = /localStorage\.getItem\(REASONING_PREF_LS_KEY\)/.test(appJs);
  ok("S3b 검출 대조군 — 추론 강도 localStorage 미러는 존재(비대칭이 의도적임을 고정)",
    reasoningMirror === true);
}

// S4: pending 대화 entry 가 요청 모델을 캡처한다(cid 없는 컨텍스트 복원용).
{
  ok("S4 pending 대화 entry 에 model 캡처",
    /model:\s*_composerCurrentModel\(\),/.test(appJs));
}

// S5: 전송 body 의 model 은 항상 싣는 게 아니라 _shouldSendModelField 게이트를 통과할 때만.
{
  const sp = extractFn(appJs, "sendPrompt");
  ok("S5 askBody.model 은 clobber 가드를 통과할 때만 동봉",
    Boolean(sp)
    && /_shouldSendModelField\(state,\s*targetConvId,\s*isLazyCreate\)/.test(sp)
    && /askBody\.model\s*=\s*_composerCurrentModel\(\)/.test(sp));
}

// S6: hydration 이 대상 대화 id 를 기록해야 D3/D4 판정이 성립한다.
{
  ok("S6 hydration 이 _modelHydratedForConvId 기록",
    /state\._modelHydratedForConvId\s*=\s*_loadGenConvId/.test(appJs));
}

// S7: 최종 안전망 리터럴이 서버 기본값(haiku)과 일치 — 카탈로그 미로드 시 상위 모델 오전송 방지.
{
  // 주석은 제거하고 코드만 본다(주석에 구 리터럴을 설명으로 남겨도 통과해야 한다).
  const codeOnly = (srcCurrent || "").split("\n").filter((ln) => !/^\s*\/\//.test(ln)).join("\n");
  ok("S7 _composerCurrentModel 최종 fallback = claude-haiku-4",
    /\|\|\s*"claude-haiku-4"/.test(codeOnly) && !/claude-sonnet-4/.test(codeOnly));
}

// S8: moveConversationToFolder 가 loadConversations 후 히스토리를 재로드(hydration 공백 차단).
{
  const fn = extractFn(appJs, "moveConversationToFolder");
  ok("S8 폴더 이동이 activeConversationId 재지정 후 loadHistory 로 정합",
    Boolean(fn) && /await loadConversations\(/.test(fn) && /await loadHistory\(\)/.test(fn));
}

// S9: early-cid 전환 지점이 **모두** 귀속 승계를 호출한다(conversation_audit 2026-07-28).
//     activeConversationId 를 pending 에서 실 cid 로 바꾸는 지점이 승계 없이 추가되면 같은
//     조용한 강등이 재발하므로, 전환 라인 수와 승계 호출 수를 함께 고정한다.
{
  const transitions = appJs.split("\n").filter(
    (ln) => /state\.activeConversationId\s*=\s*earlyCid\s*;/.test(ln)).length;
  const adoptions = appJs.split("\n").filter(
    (ln) => /_adoptComposerModelPickToConv\(state,\s*earlyCid/.test(ln)).length;
  ok(`S9 early-cid 전환(${transitions}곳) 마다 귀속 승계 호출(${adoptions}곳)`,
    transitions > 0 && adoptions === transitions);
}

// S10: 첨부 업로드 경로는 pendingSentinel 을 비우기 **전에** 승계해야 한다(키 유실 방지).
{
  const idxAdopt = appJs.indexOf("_adoptComposerModelPickToConv(state, earlyCid, pendingKey");
  const idxClear = appJs.indexOf("state.pendingSentinel = null;", idxAdopt);
  ok("S10 첨부 경로 승계가 pendingSentinel 초기화보다 앞",
    idxAdopt > 0 && idxClear > idxAdopt);
}

// S11: 미동봉 분기가 무음으로 끝나지 않는다 — 감지 + 사용자 표면화(showToast).
{
  const sp = extractFn(appJs, "sendPrompt");
  ok("S11 미동봉 시 무음 강등 감지 + 사용자 표면화",
    Boolean(sp)
    && /_modelSelectionSilentlyDropped\(state,\s*targetConvId,\s*isLazyCreate\)/.test(sp)
    && /showToast\(/.test(sp.slice(sp.indexOf("_modelSelectionSilentlyDropped"))));
}

console.log(`\n${failed === 0 ? "ALL PASS" : "FAILED"}  passed=${passed} failed=${failed}`);
process.exit(failed === 0 ? 0 : 1);
