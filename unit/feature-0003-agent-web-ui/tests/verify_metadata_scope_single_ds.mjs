// verify_metadata_scope_single_ds.mjs
// metadata-scope-single-ds-ui: "메타데이터" 거버넌스 패널의 '데이터소스' 선택 UI 를 단일화한 변경의 회귀 가드.
//
// 배경(수정 전):
//   데이터소스 selector 가 두 곳에 중복 존재했다 —
//     (1) 패널 헤더 #metadataScopeSelect ("데이터소스") = 메타데이터 저장/조회 스코프(저장 target).
//     (2) "스키마 골격 가져오기" 내부 #metadataBootstrapDs ("데이터소스 *") = 스키마 introspection 대상.
//   둘은 완전히 독립이라, 헤더 스코프=A 인데 부트스트랩 DS=B 로 고르면 "B 스키마 골격을 A 스코프로 저장"
//   하는 조용한 불일치(footgun)가 가능했다(저장은 항상 헤더 스코프 _metaBootstrapSave → scopeKey).
//
// 수정:
//   부트스트랩 전용 DS selector(#metadataBootstrapDs)를 제거하고, 부트스트랩 데이터소스를 상단 스코프에서
//   상속한다(_metaScopeDatasourceKey → _metaBootstrapSyncToScopeDs). 스코프가 가리키는 데이터소스가
//   곧 introspection 소스가 되어 스코프↔소스 불일치가 구조적으로 불가능해진다.
//   공용(common) 스코프는 실제 스키마가 없어 부트스트랩 불가 → 관리 콘솔 list-detail empty-state
//   (.admin-detail-empty) 컨벤션을 재사용한 #metadataBootstrapEmpty 안내로 대체(비활성 잔재/더미 컨트롤 없음).
//
//   불변식: 저장 경로(_metaBootstrapSave)는 여전히 adminState.metadata.scopeKey 로 저장 — 변경 없음.
//   부트스트랩은 구체 데이터소스 스코프에서만 노출되므로 저장 스코프와 골격 소스가 항상 동일하다.
//
// 본 테스트(정적 소스 단언 — jsdom 불필요):
//   [A] 중복 제거 — #metadataBootstrapDs select / _metaBootstrapPopulateDs 부재.
//   [B] 상속 구조 — empty-state/head/dsName 마크업 + _metaBootstrapSyncToScopeDs + 스코프 핸들러 연동.
//   [C] 저장 불변식 — _metaBootstrapSave 가 scopeKey 로 저장(footgun 제거 후에도 보존).
//   [D] cache-buster 동반 bump + empty-state CSS.
//
// 실행: node tests/verify_metadata_scope_single_ds.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const adminJs = /* feature-0038 Cycle 6: 메타데이터 콘솔 → admin/metadata.js 분리 — 합본 검사 */ readFileSync(join(STATIC, "admin.js"), "utf8")
  + readFileSync(join(STATIC, "admin/metadata.js"), "utf8")
  + readFileSync(join(STATIC, "admin/datasources.js"), "utf8");
const adminHtml = readFileSync(join(STATIC, "admin.html"), "utf8");
const adminCss = /* feature-0038 Cycle 1: styles.css → css/ 7분할 — 순차 concat(byte-동치) */ ["base","shell","chat","drawers","admin","profile","search-audit"]
  .map((n) => readFileSync(join(STATIC, `css/${n}.css`), "utf8")).join("");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}
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

// ── [A] 중복 데이터소스 selector 제거 ────────────────────────────────────────
ok("[A1] admin.html 에 부트스트랩 전용 DS select(#metadataBootstrapDs) 부재",
   !/id=["']metadataBootstrapDs["']/.test(adminHtml));
ok("[A2] admin.js 에 _metaBootstrapPopulateDs(드롭다운 채움 함수) 부재",
   !/_metaBootstrapPopulateDs/.test(adminJs));
ok("[A3] admin.js 가 더 이상 #metadataBootstrapDs element 를 읽지 않음",
   !/getElementById\(["']metadataBootstrapDs["']\)/.test(adminJs));

// ── [B] 스코프 상속 구조 ─────────────────────────────────────────────────────
ok("[B1] empty-state 요소(#metadataBootstrapEmpty)가 list-detail .admin-detail-empty 컨벤션 사용",
   /class=["'][^"']*\badmin-detail-empty\b[^"']*["'][^>]*id=["']metadataBootstrapEmpty["']/.test(adminHtml)
   || /id=["']metadataBootstrapEmpty["'][^>]*class=["'][^"']*\badmin-detail-empty\b/.test(adminHtml));
ok("[B2] 부트스트랩 헤더에 토글 숨김용 #metadataBootstrapHead id 부여", /id=["']metadataBootstrapHead["']/.test(adminHtml));
ok("[B3] 노트에 상속 데이터소스명 표기 슬롯(#metadataBootstrapDsName)", /id=["']metadataBootstrapDsName["']/.test(adminHtml));

const syncToScope = extractFn(adminJs, "_metaBootstrapSyncToScopeDs");
ok("[B4] _metaBootstrapSyncToScopeDs(스코프 DS 상속) 함수 존재", Boolean(syncToScope));
ok("[B5] 상속 함수가 스코프 DS 변경 시 골격/스키마 리셋 + 스키마 재로드",
   Boolean(syncToScope) && /bootstrap\.tables\s*=\s*\[\]/.test(syncToScope) && /_metaBootstrapLoadSchemas\(\)/.test(syncToScope));

const syncVis = extractFn(adminJs, "_metaSyncBootstrapVisibility");
ok("[B6] _metaSyncBootstrapVisibility 가 스코프 DS(_metaScopeDatasourceKey)로 분기",
   Boolean(syncVis) && /_metaScopeDatasourceKey\(\)/.test(syncVis));
ok("[B7] 공용(common) 스코프 분기에서 empty-state 노출 + 상속 함수 호출",
   Boolean(syncVis) && /metadataBootstrapEmpty/.test(syncVis) && /_metaBootstrapSyncToScopeDs\(/.test(syncVis));

const bindCtl = extractFn(adminJs, "_metaBindControls");
// metadata-list-detail: 스코프 핸들러는 _metaRenderDetail(우측 상세 코디네이터) 경유로 부트스트랩
//   가시성을 동기화한다(bootstrap 모드면 _metaRenderDetail 가 _metaSyncBootstrapVisibility 호출).
//   직접 호출에서 코디네이터 경유로 바뀐 정당한 리팩토링 — 동기화 보장은 _metaRenderDetail 가 책임.
ok("[B8] 스코프 변경 핸들러가 우측 상세 코디네이터(_metaRenderDetail) 경유로 부트스트랩 동기화",
   Boolean(bindCtl) && /metadataScopeSelect[\s\S]*_metaRenderDetail\(\)/.test(bindCtl));
const renderDetailB8 = extractFn(adminJs, "_metaRenderDetail");
ok("[B8b] _metaRenderDetail 가 bootstrap 모드에서 _metaSyncBootstrapVisibility 호출",
   Boolean(renderDetailB8) && /_metaSyncBootstrapVisibility\(\)/.test(renderDetailB8));

// ── [C] 저장 불변식(footgun 제거 후에도 보존) ───────────────────────────────
const saveSrc = extractFn(adminJs, "_metaBootstrapSave");
ok("[C1] 부트스트랩 저장은 여전히 헤더 스코프(scopeKey)로 저장",
   Boolean(saveSrc) && /scope\s*=\s*adminState\.metadata\.scopeKey/.test(saveSrc) && /scope_key:\s*scope/.test(saveSrc));

// ── [D] cache-buster 동반 bump + empty-state CSS ────────────────────────────
// feature-0038 Cycle 1: styles.css 는 css/ 7분할 + cache-buster 는 소스 `?v=dev` 고정
// (빌드 inject_asset_stamp.py 가 content-hash 일괄 주입 — 수기 bump 계약 폐기).
// 신계약: admin.js 와 css/base.css 참조가 모두 placeholder(?v=dev)로 존재해 빌드 주입 대상임을 검증.
const _jsV = (adminHtml.match(/admin\.js\?v=([0-9a-z-]+)/) || [])[1];
const _cssV = (adminHtml.match(/css\/base\.css\?v=([0-9a-z-]+)/) || [])[1];
ok("[D1] admin.js·css/base.css 가 동일 cache-buster placeholder(?v=dev)", _jsV === "dev" && _cssV === "dev");
ok("[D2] empty-state 정렬 CSS(.admin-meta-bootstrap-empty) 존재", /\.admin-meta-bootstrap-empty\b/.test(adminCss));

console.log(`\n  ${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
