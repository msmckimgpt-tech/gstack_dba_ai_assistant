// ITEM-09 batch3 — graph.js L570~L630 pure move: graph-perf-bg: 논블로킹 유틸.
// 규약: 공개 표면은 graph/graph.js(barrel) 가 re-export — admin.js 는 barrel 만 import.
// 모듈 간/admin 순환 import 는 ES live-binding + 호출시점 사용이라 안전(ITEM-09 batch1 실증).
import { _metaGraph } from "./graph-state.js?v=dev";
import { _metaNodeStates } from "./graph-roleviz.js?v=dev";
import { _metaRenderedIdFor } from "./graph-core.js?v=dev";
const G6 = window.G6;  // UMD 전역 bridge (admin.html classic script 선행 로드)

// ── graph-perf-bg: 논블로킹 유틸(펼침/확장이 메인스레드를 얼리지 않도록) ──
// 무거운 setData+draw 직전에 브라우저가 busy 상태를 실제로 페인트하도록 두 번의 rAF 후 넘긴다.
//   단일 rAF 는 같은 프레임에 병합될 수 있고, microtask(Promise.resolve)는 페인트를 유발하지 못하므로 둘 다 부적합.
function _metaRaf() {
  return new Promise((res) => {
    if (typeof window !== "undefined" && window.requestAnimationFrame) window.requestAnimationFrame(() => res());
    else setTimeout(res, 0);
  });
}
function _metaYieldPaint() { return _metaRaf().then(() => _metaRaf()); }

// graph-perf-bg fix: 노드에 "적용할" state = 영속 마커(_metaNodeStates) + 명령형 busy(_busyKeys).
//   busy 를 signature 에 포함시켜 _metaGraphRefreshStates(2.5s 폴)가 fetch 창 도중 busy 를 덮어써 지우지 못하게 한다.
function _metaStateSig(key) {
  const st = _metaNodeStates(key);              // 매 호출 새 배열 — push 안전
  if (_metaGraph._busyKeys.has(key)) st.push("busy");
  return st;
}
// node-role-viz: 캐시 서명 = state 서명 + 역할 suffix. 역할은 G6 state 가 아니라 **build 시 칩 색/라벨로
//   bake 되는 style** 이라 setElementState 로 반영할 수 없다 — 대신 서명에 포함시켜 refreshStates 가
//   "역할 도착"을 변화로 감지하고 rebuild(_metaG6Apply)로 승격하게 한다. setElementState 에는 넘기지 않는다.
function _metaCacheSig(key) {
  const role = _metaGraph.roles.get(key);
  return _metaStateSig(key).join("|") + (role ? "#R=" + role : "");
}
function _metaSigRole(sig) {
  const i = (sig || "").indexOf("#R=");
  return i >= 0 ? sig.slice(i + 3) : "";
}
// 요소 state 적용 단일 진입점 — 적용과 동시에 _stateCache signature 를 동기화한다.
//   불변식: _stateCache.get(key) === 요소에 마지막 적용된 state 의 signature. 명령형 writer(busy·selected)도 이 경로를 쓰면
//   refreshStates 가 "변화 없음"으로 오판해 필요한 재적용을 건너뛰는 false-negative 가 원천 차단된다.
function _metaApplyState(key) {
  const g = _metaGraph.graph;
  if (!g || !key || !_metaGraph.nodes.has(key)) return;
  const st = _metaStateSig(key);
  // graph-initview: 렌더된 요소 id 로 매핑(접힌 스키마 카드=SC:) — 카드 게이팅으로 미렌더인 모델 키에
  // setElementState 하면 async reject 가 pageerror 로 새므로 skip + promise reject 흡수.
  const el = _metaRenderedIdFor(key);
  if (el) { try { Promise.resolve(g.setElementState(el, st)).catch(() => {}); } catch (_) {} }
  _metaGraph._stateCache.set(key, _metaCacheSig(key));   // node-role-viz: 역할 suffix 포함(불변식 유지)
}

// 클릭 노드에 임시 busy 하이라이트(명령형). **_metaNodeStates 에는 넣지 않는다**(rebuild 마다 재-bake 되어 영구
//   하이라이트로 굳음) — 대신 _busyKeys 로 소유 op(seq)와 함께 추적해 rebuild(_metaG6Apply)·reset 시 일괄 소멸.
//   on=true: seq 소유권 기록. on=false: op-scoped 해제 — seq 를 주면 그 op 가 여전히 소유할 때만 해제하여, 같은 key 를
//   재트리거한 신 op 의 busy 를 뒤늦게 resolve 된 stale op 가 지우지 못하게 한다(seq 미지정이면 무조건 해제).
function _metaSetBusy(key, on, seq) {
  if (!key) return;
  if (!_metaGraph._busyTs) _metaGraph._busyTs = new Map();   // §57.8: stale busy TTL 소거용
  if (on) {
    _metaGraph._busyKeys.set(key, seq == null ? -1 : seq);
    _metaGraph._busyTs.set(key, Date.now());
  } else {
    if (seq != null && _metaGraph._busyKeys.get(key) !== seq) return;   // 신 op 가 이미 같은 key busy 소유 — stale op 는 건드리지 않음
    _metaGraph._busyKeys.delete(key);
    _metaGraph._busyTs.delete(key);
  }
  _metaApplyState(key);
}


export { _metaApplyState, _metaCacheSig, _metaSetBusy, _metaSigRole, _metaStateSig, _metaYieldPaint };
