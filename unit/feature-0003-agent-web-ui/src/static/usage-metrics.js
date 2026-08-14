// usage-metrics.js — LLM 사용량 **지표 정의의 단일 정본** (usage-metric-charts, 2026-08-13).
//
// 관리 콘솔(`admin/usage.js`)과 사용자 프로필(`app/profile.js`)은 서로 다른 번들이지만 **같은
// 원장(agent_runtime.llm_usage)** 을 본다. 지표 목록·라벨·가산성 규칙이 두 곳에 복제되면 한쪽만
// 고쳐져 "같은 값인데 화면마다 이름·구성이 다른" 상태가 된다 — 저장소가 `modal-dismiss.js` /
// `hangul-qwerty.js` 로 확립한 "복제가 곧 결함 기전" 규약을 여기에도 적용한다.
//
// 두 화면이 공유하는 것은 **정의**이고, 렌더(크기·클래스·상호작용)는 각자의 것이다.
export const USAGE_METRICS = [
  // stackable=false → 모델별 분해가 성립하지 않는 지표. `requests` 는 distinct run_id 라 한 요청이
  //   여러 모델을 횡단하면 모델별 distinct 의 합이 전체보다 커진다(그대로 쌓으면 막대가 요약 카드
  //   값을 넘는다). 이 지표는 버킷 총계를 단일 막대로 그리고 그 사실을 캡션으로 알린다.
  { key: "requests", label: "요청", money: false, stackable: false },
  { key: "calls", label: "호출", money: false, stackable: true },
  { key: "total_tokens", label: "총 토큰", money: false, stackable: true },
  { key: "prompt_tokens", label: "입력", money: false, stackable: true },
  { key: "completion_tokens", label: "출력", money: false, stackable: true },
  // cache=true → **입력의 부분집합**(prompt_tokens 가 이 둘을 포함한다). 합산해 총량을 만들지
  //   않도록 선택 시 화면이 그 관계를 1줄로 알린다.
  { key: "cache_read_tokens", label: "캐시 읽기", money: false, stackable: true, cache: true },
  { key: "cache_write_tokens", label: "캐시 쓰기", money: false, stackable: true, cache: true },
  { key: "cost_usd", label: "추정 비용", money: true, stackable: true },
];

export const USAGE_METRIC_DEFAULT = "total_tokens";

// 미지·미설정 키는 기본 지표로 폴백한다(저장된 선택이 폐기된 키여도 화면이 죽지 않는다).
export function usageMetricOf(key) {
  return USAGE_METRICS.find((m) => m.key === key)
    || USAGE_METRICS.find((m) => m.key === USAGE_METRIC_DEFAULT);
}

// 선택 지표에서 오해가 생기는 경우에만 쓰는 1줄 안내(§16.8 예산 — 각 60자 이내).
// 그 외 지표는 빈 문자열 = 아무것도 붙이지 않는다.
export function usageMetricNote(metric) {
  if (!metric) return "";
  if (!metric.stackable) return "요청은 모델을 넘나들어 모델별로 나누지 않습니다.";
  if (metric.cache) return "캐시 읽기·쓰기는 입력에 포함된 내역입니다.";
  return "";
}

// 선택 지표와 나란히 보여줄 보조 지표 — 기본은 비용, 선택이 비용이면 총 토큰(같은 차트 중복 방지).
export function usageSideMetric(metric) {
  return usageMetricOf(metric && metric.key === "cost_usd" ? "total_tokens" : "cost_usd");
}
