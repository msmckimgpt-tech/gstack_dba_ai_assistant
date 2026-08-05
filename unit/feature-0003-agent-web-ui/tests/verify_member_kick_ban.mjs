// verify_member_kick_ban.mjs — feature-0009 member-kick-ban 정적 소스 단언.
// 공유 팝업의 owner 전용 추방(kick)/차단(ban)/해제(unban) + '차단된 사용자' 목록이
// owner-게이트로 렌더되고 올바른 엔드포인트를 호출하는지, 캐시버스터 bump 를 정적 검증.
// (라이브 렌더/authz 정본은 PB-0008 + 배포 후. 본 테스트는 회귀 가드.)
//
// 실행: node unit/feature-0003-agent-web-ui/tests/verify_member_kick_ban.mjs
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const staticDir = join(here, "..", "src", "static");
const appJs = readFileSync(join(staticDir, "app.js"), "utf8");
const cssTxt = /* feature-0038 Cycle 1: styles.css → css/ 7분할 — 순차 concat(byte-동치) */ ["base","shell","chat","drawers","admin","profile","search-audit"].map((n) => readFileSync(join(staticDir, `css/${n}.css`), "utf8")).join("");
const indexHtml = readFileSync(join(staticDir, "index.html"), "utf8");

let pass = 0, fail = 0;
const ok = (cond, name) => {
  if (cond) { pass++; console.log(`  PASS ${name}`); }
  else { fail++; console.error(`  FAIL ${name}`); }
};

// openShareDialog 본문만 추출.
const shareStart = appJs.indexOf("async function openShareDialog(");
const shareEnd = appJs.indexOf("\nasync function openConversationSettings(", shareStart);
const s = shareStart >= 0 ? appJs.slice(shareStart, shareEnd > 0 ? shareEnd : shareStart + 14000) : "";
ok(shareStart >= 0, "openShareDialog 함수 존재");

// 1. 팝업 골격에 '차단된 사용자' 섹션(기본 hidden).
ok(/<div class="share-mgr-subhead share-bans-head hidden">차단된 사용자<\/div>/.test(s), "'차단된 사용자' subhead(기본 hidden)");
ok(/<div class="share-bans hidden" aria-live="polite"><\/div>/.test(s), ".share-bans 컨테이너(기본 hidden)");

// 2. loadBans 헬퍼 + owner 전용 GET /bans 엔드포인트.
ok(/const loadBans = async \(\) =>/.test(s), "loadBans 헬퍼 정의");
ok(s.includes("/api/conversations/${encodeURIComponent(cid)}/bans"), "GET /bans 엔드포인트 호출");

// 3. viewer=owner 판정(state.user.id === owner_account_id).
ok(/viewerIsOwner = ownerId != null && state\.user && String\(state\.user\.id\) === String\(ownerId\)/.test(s), "viewerIsOwner = state.user.id === owner_account_id");

// 4. 추방(kick): 기존 DELETE /members/{id} 재사용(신규 백엔드 아님).
ok(s.includes('await apiFetch(`/api/conversations/${encodeURIComponent(cid)}/members/${encodeURIComponent(m.account_id)}`, { method: "DELETE" })'), "추방=기존 DELETE /members/{id} 재사용");

// 5. 차단(ban): POST /members/{id}/ban.
ok(s.includes('/members/${encodeURIComponent(m.account_id)}/ban`, { method: "POST"'), "차단=POST /members/{id}/ban");

// 6. 해제(unban): DELETE /members/{id}/ban (loadBans 안).
ok(s.includes('/members/${encodeURIComponent(b.account_id)}/ban`, { method: "DELETE" })'), "해제=DELETE /members/{id}/ban");

// 7. owner 전용 게이트 — 추방/차단 버튼은 viewerIsOwner && !targetIsOwner 일 때만.
ok(/if \(viewerIsOwner && !targetIsOwner\) \{/.test(s), "추방/차단 버튼: viewerIsOwner && !targetIsOwner 게이트");

// 8. 차단 목록은 owner 에게만 노출(비-owner 면 섹션 숨김 유지).
ok(/if \(viewerIsOwner\) \{\s*await loadBans\(\);/.test(s), "차단 목록 로드: viewerIsOwner 일 때만");
ok(s.includes('bansHead.classList.add("hidden")'), "비-owner: 차단 섹션 hidden 유지");

// 9. 차단 후 roster + 차단목록 동시 갱신.
ok(/showToast\(`\$\{name\} 님을 차단했습니다\.`\);\s*await loadParticipants\(\);\s*await loadBans\(\);/.test(s), "차단 성공 → loadParticipants + loadBans 갱신");

// 10. 사용자명은 textContent(XSS) — 버튼 라벨/확인문구에 innerHTML 보간 없음.
ok(!/participantsBox\.innerHTML\s*=\s*[`'"][^`'"]*\$\{[^}]*\.username/.test(s), "username 을 innerHTML 템플릿에 직접 보간하지 않음");

// 11. CSS: 추방/차단 버튼 + 차단 칩 스타일.
ok(/\.share-participant-btn\s*\{/.test(cssTxt), ".share-participant-btn 스타일");
ok(/\.share-participant\.is-banned\s*\{/.test(cssTxt), ".share-participant.is-banned 스타일");
ok(/\.share-bans\s*\{/.test(cssTxt), ".share-bans 스타일");

// 12. 캐시버스터 bump.
// feature-0014 asset-stamp: 소스는 `?v=dev` placeholder — 빌드(inject_asset_stamp.py)가 content-hash 를
// 일괄 주입한다(수기 bump 계약 폐기). 구 단언(특정 `?v=YYYYMMDD-slug` 토큰)은 스탬프 체계 전환으로
// 무의미 — 자산이 스탬프 관리 대상(placeholder 부착)인지만 검증한다.
ok(/app\.js\?v=dev/.test(indexHtml), "app.js 가 asset-stamp placeholder(?v=dev)");
ok(/css\/chat\.css\?v=dev/.test(indexHtml), "css 번들이 asset-stamp placeholder(?v=dev)");

console.log(`\nverify_member_kick_ban: ${pass} passed, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
