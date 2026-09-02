// 대화 상태 → 사이드바 상태 dot 의 **시각 배선 단일 정본**.
//
// 왜 별도 모듈인가 (배선이 끊겼던 이력):
//   종전에는 dot 클래스를 `is-${status}` 로 **세 곳에서 각각** 조립했고(사이드바 일반 행 ·
//   사이드바 인라인 이름변경 행 · 폴링 중 DOM 직접 갱신), CSS 어휘는 그와 따로 자랐다. 그
//   결과 —
//     · `done` / `error` / `canceled` 는 CSS 규칙이 아예 없어 종료 상태가 전부 기본 회색,
//     · CSS 에 있던 `.conv-dot.is-completed` 는 아무도 만들지 않는 죽은 규칙(백엔드 어휘는
//       `completed` 가 아니라 `done`),
//     · `stale_error` 는 CSS 가 하이픈(`is-stale-error`)인데 코드는 언더스코어를 만들어
//       어긋났다 — 같은 줄에서 부여하는 `title` 툴팁만 떠서 「글씨는 뜨는데 색은 안 변한다」.
//   즉 처리 중(주황)만 살아 있고 나머지는 전부 무색이라 "상태값에 따라 색이 안 변한다" 로
//   보였다. 조립을 여기 하나로 모아, 어휘가 바뀌면 한 곳만 바뀌게 한다.
//
// 의존이 없어야 한다 (leaf):
//   `app.js` 와 `app/sidebar.js` 는 서로를 import 한다. 공용 헬퍼를 둘 중 하나에 두면
//   순환이 되어 초기화 순서에 따라 TDZ 로 터진다. 이 파일은 무엇도 import 하지 않는다.
//
// 계약은 `tests/test_conv_status_dot_wiring.py` 가 강제한다:
//   T1 백엔드가 쓰는 상태 리터럴 ⊆ 아래 키   T2 아래 클래스 ⊆ CSS `.conv-dot.*` 규칙
//   T3 dot 클래스를 배정하는 곳은 이 모듈뿐   T4 상태 modifier 전반의 CSS 커버리지

/**
 * 상태값 → { cls: dot modifier 클래스, label: 사용자 언어 }.
 *
 * label 은 툴팁으로 쓴다 — 색만으로 상태를 전달하면 색각 이상 사용자가 읽지 못한다.
 *
 * 값의 출처:
 *   processing / done / error / canceled — 서버가 KV(`last_status`)에 쓰는 실제 리터럴
 *                                          (`set_run_status`).
 *   stale_error                          — 서버 파생(`_compute_display_status`: processing
 *                                          이 만료 시간 동안 갱신 없음).
 *   pending / starting / failed          — 프런트 전용. 대화가 서버에 만들어지기 전
 *                                          in-flight 항목과 첫 폴링 이전 구간.
 */
export const CONV_DOT_STATUS = Object.freeze({
  pending:     Object.freeze({ cls: "is-pending",     label: "대기 중" }),
  starting:    Object.freeze({ cls: "is-starting",    label: "시작 중" }),
  processing:  Object.freeze({ cls: "is-processing",  label: "처리 중" }),
  done:        Object.freeze({ cls: "is-done",        label: "완료" }),
  error:       Object.freeze({ cls: "is-error",       label: "오류" }),
  failed:      Object.freeze({ cls: "is-error",       label: "전송 실패" }),
  canceled:    Object.freeze({ cls: "is-canceled",    label: "취소됨" }),
  stale_error: Object.freeze({ cls: "is-stale-error", label: "작업 중단 감지" }),
});

/** 서버·프런트가 섞어 쓰는 표기를 하나로 — 공백·대소문자만 흡수한다(구분자는 바꾸지 않는다). */
export function normalizeConvStatus(status) {
  return String(status || "").trim().toLowerCase();
}

/**
 * dot 요소에 그대로 넣을 `className` 문자열.
 *
 * 모르는 상태는 **modifier 없이 기본 회색**으로 떨어뜨린다. 종전처럼 `is-<모르는값>` 을
 * 만들어 두면 CSS 가 없어 어차피 무색인데 "클래스는 붙어 있으니 배선은 됐다" 로 읽혀
 * 이번 결함이 오래 숨었다. 어휘가 늘면 위 표에 등재하는 것이 유일한 경로이고, T1 이
 * 서버 어휘와의 누락을 CI 에서 잡는다.
 */
export function conversationDotClass(status) {
  const entry = CONV_DOT_STATUS[normalizeConvStatus(status)];
  return entry ? `conv-dot ${entry.cls}` : "conv-dot";
}

/** 상태의 사용자 언어 라벨. 모르는 상태는 빈 문자열(툴팁을 지어내지 않는다). */
export function conversationDotLabel(status) {
  const entry = CONV_DOT_STATUS[normalizeConvStatus(status)];
  return entry ? entry.label : "";
}
