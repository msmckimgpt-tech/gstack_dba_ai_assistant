// 위임한 콘솔 작업의 결과를 기다린다 — 관리 콘솔과 프로필 화면의 **공용** 헬퍼.
//
// ## 왜 별도 모듈인가 (TASK-20260909T000000-prompt-autogen-delivery)
//
// 이 코드는 원래 `admin/llm-state.js` 안에 있었고, 그 모듈은 `admin.js` 의 `adminState` 를
// import 한다. 그래서 **관리 콘솔 밖에서는 쓸 수 없었다** — 프로필의 '내 프롬프트 > 자동
// 작성' 은 같은 위임 응답을 받으면서도 그것을 해석할 수단이 없어, 서버가 정상 위임한 작업의
// 결과가 화면에 영영 도달하지 않았다(라이브 실증 2026-09-08: 요청 200 OK · 러너 3초 만에
// 제출 완료 · 화면은 무반응).
//
// 위임 응답은 **즉시 결과를 주지 않는다**(`bridge_pending: true`). 호출부가 그것을 모르면
// 응답을 스트림으로 읽다가 조용히 버리거나 `undefined` 를 폼에 채운다. 그 간극을 여기서
// 메우고, 세 자동작성 화면이 **같은 한 곳**을 쓰게 한다.
//
// **주기 폴링이 아니라 서버 국면을 따라간다**는 원칙은 대화 축(P0-J)과 같지만, 여기서는
// 블로킹 대기(`wait_for_request`)에 해당하는 것이 없다 — 폼 화면이라 SSE 를 새로 여는
// 비용보다 짧은 간격 폴링이 단순하다. 대신 **상한을 두고**, 끝나면 정직하게 말한다.

/** 재시도해도 달라지지 않는 실패에 붙이는 표지. 문구가 아니라 **값**으로 구분한다. */
function _terminal(message) {
  const err = new Error(message);
  err.terminal = true;
  return err;
}

const _JOB_POLL_MS = 2000;
const _JOB_POLL_MAX_MS = 10 * 60 * 1000;   // 러너 lease(30분)보다 짧다 — 화면이 먼저 포기한다

/** `signal` 이 이미 끊겼으면 즉시 중단. abort 는 사용자 조작이므로 표지 없이 던진다
 *  (호출부가 `name === "AbortError"` 로 조용히 흡수하는 관례를 그대로 쓰게). */
function _abortError() {
  const err = new Error("aborted");
  err.name = "AbortError";
  return err;
}

/** `ms` 대기. 도중에 abort 되면 남은 시간을 기다리지 않고 즉시 깨어난다 —
 *  기다리는 동안 abort 를 무시하면 재진입 시 앞선 폴링이 최대 2초 더 살아 있다. */
function _sleep(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal && signal.aborted) { reject(_abortError()); return; }
    const t = setTimeout(() => {
      if (signal) signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    function onAbort() { clearTimeout(t); reject(_abortError()); }
    if (signal) signal.addEventListener("abort", onAbort, { once: true });
  });
}

/**
 * 위임 응답이면 결과가 올 때까지 기다렸다가 **최종 결과**를 돌려준다.
 *
 * @param {object} resp        서버 응답(위임이면 `bridge_pending: true`)
 * @param {function} onPhase   국면이 바뀔 때마다 호출(사용자에게 진행을 보인다)
 * @param {object} [opts]
 * @param {AbortSignal} [opts.signal] 재진입·취소 시 폴링을 끊는다. 없으면 상한까지 돈다.
 * @returns {Promise<object>}  위임이 아니면 `resp` 그대로. 위임이면 `{result, applied, ...}`.
 * @throws {Error}             취소·반영실패·상한초과 — 호출측이 사용자에게 사유를 보인다.
 *                             abort 는 `name === "AbortError"`.
 *
 * 위임이 아니면 **원본을 그대로 통과**시킨다 — 호출부가 게이트 상태를 분기하지 않아도 되게.
 */
export async function awaitDelegatedResult(resp, onPhase, opts) {
  if (!resp || resp.bridge_pending !== true) return resp;
  const signal = (opts && opts.signal) || null;
  // 폴백은 **프로필 경로**다. 이 헬퍼를 쓰는 화면 중에는 관리 권한이 없는 계정이 여는 것
  // (프로필 '내 프롬프트')이 있고, admin 경로는 `console.access` 를 요구해 그 계정에게는
  // 403 이다. 서버가 `poll_url` 을 주므로 폴백이 쓰일 일은 드물지만, 드물게 쓰일 때
  // 권한이 더 좁은 쪽으로 떨어지면 그 화면만 조용히 죽는다.
  const url = resp.poll_url || ("/api/profile/ai-jobs/" + encodeURIComponent(resp.task_id));
  const started = Date.now();
  let lastPhase = "";
  for (;;) {
    if (Date.now() - started > _JOB_POLL_MAX_MS) {
      // 조용히 포기하지 않는다 — 작업은 아직 살아 있을 수 있고, 그 사실을 말해야 한다.
      throw _terminal("연결된 AI 의 응답을 기다리다 시간이 초과됐습니다. "
        + "작업은 취소되지 않았으니 'AI 운영 현황 > 위임 작업 현황' 에서 확인하세요.");
    }
    await _sleep(_JOB_POLL_MS, signal);
    let body;
    try {
      const res = await fetch(url, { credentials: "same-origin", signal: signal || undefined });
      body = await res.json().catch(() => ({}));
      if (!res.ok) {
        // ⚠ **재시도해도 달라지지 않는 상태는 즉시 멈춘다** (codex 적대 리뷰 P2).
        //
        // 401(세션 만료)·403(권한 상실)·404(작업 없음)를 "일시적 실패" 로 다루면 상한까지
        // 매 tick 재요청하고, 사용자에게는 **원인 대신 타임아웃**이 표시된다 — 그가 할 일은
        // 다시 로그인하는 것인데 화면은 기다리라고 말한다.
        if (res.status === 401 || res.status === 403 || res.status === 404) {
          throw _terminal(
            res.status === 401 ? "로그인이 만료되었습니다. 다시 로그인한 뒤 시도하세요."
              : res.status === 403 ? "이 작업을 조회할 권한이 없습니다."
                : "작업 기록을 찾을 수 없습니다.");
        }
        // 그 외(5xx·네트워크)는 일시적일 수 있다 — 다음 tick 에 다시 묻는다.
        continue;
      }
    } catch (e) {
      // 위에서 던진 종료 사유는 그대로 올린다. 그 외(파싱·네트워크)만 재시도한다.
      //
      // ⚠ 메시지 문자열로 구분하지 않는다 — 문구를 고치는 날 재시도 루프가 조용히
      //   되살아난다. 표지를 값으로 붙여 판정이 문구와 무관하게 한다.
      if (e && e.terminal === true) throw e;
      // abort 는 재시도 대상이 아니다 — 사용자가 그만두라고 한 것이다.
      if (e && e.name === "AbortError") throw e;
      continue;
    }
    if (body.phase && body.phase !== lastPhase) {
      lastPhase = body.phase;
      if (typeof onPhase === "function") onPhase(body.phase, body);
    }
    if (body.phase === "done") {
      // ⚠ 「제출됐다」와 「AI 가 해냈다」는 다르다.
      //
      // 러너는 자기 AI 가 실패하면 **그 사실을 안내문으로 적어 제출한다** — 대화 축에서는
      // 옳은 설계다(침묵보다 낫다). 그런데 폼 축에서는 그 안내문이 곧 "결과물" 이 되어
      // 프롬프트 입력란을 덮는다. 사용자가 편집 중이던 본문이 오류 문장으로 사라지고,
      // 화면은 그것을 완료라고 말한다. 서버가 그 대체 제출을 표시해 주므로 여기서 가른다.
      if (body.degraded === true) {
        throw _terminal("연결된 AI 가 작업을 끝내지 못했습니다"
          + (body.degraded_reason ? ": " + body.degraded_reason : "."));
      }
      return body;
    }
    if (body.phase === "apply_failed") {
      throw _terminal("AI 가 답했지만 반영하지 못했습니다: " + (body.apply_error || "사유 미기록"));
    }
    if (body.phase === "canceled") throw _terminal("작업이 취소되었습니다.");
    // ⚠ **모르는 국면에서 기다리지 않는다** (codex 적대 리뷰 P2).
    //
    // 서버가 국면을 늘리면(예: `failed`) 이 루프는 그것을 진행 중으로 읽고 상한까지 돈다 —
    // 실패가 타임아웃으로 위장되고, 그 위장은 서버를 고친 사람에게 보이지 않는다.
    // 아는 진행 국면만 계속하고, 나머지는 즉시 멈춘다(allowlist).
    if (body.phase !== "waiting" && body.phase !== "working") {
      throw _terminal("작업이 예기치 않은 상태로 끝났습니다: " + (body.phase || "(미상)"));
    }
  }
}

/** 위임 진행 국면을 사람 말로. 화면마다 다른 문구를 지어내지 않게 한 곳에 둔다. */
export function jobPhaseLabel(phase) {
  return ({
    waiting: "연결된 AI 가 가져가기를 기다리는 중…",
    working: "연결된 AI 가 처리 중…",
    done: "완료",
    apply_failed: "반영 실패",
    canceled: "취소됨",
  })[phase] || "처리 중…";
}

/**
 * 자동작성 응답이 **위임 봉투**인가 — 스트림으로 읽으면 안 되는 응답인가.
 *
 * 세 자동작성 화면은 전환 이전부터 SSE(`text/event-stream`)를 읽어 왔고, 위임이 붙은 뒤로는
 * 같은 URL 이 상황에 따라 JSON 을 준다. 그 갈림을 화면마다 다르게 판정하면 한 화면만 고쳐지고
 * 나머지는 계속 조용히 버린다 — 이 함수가 그 판정의 단일 지점이다.
 *
 * @param {Response} resp  fetch 응답(아직 본문을 읽지 않은 상태)
 */
export function looksDelegatedEnvelope(resp) {
  const ctype = String((resp && resp.headers && resp.headers.get("content-type")) || "");
  return ctype.toLowerCase().indexOf("application/json") >= 0;
}
