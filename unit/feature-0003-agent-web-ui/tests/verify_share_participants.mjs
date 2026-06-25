// verify_share_participants.mjs — feature-0009 gc-share-participants 정적 소스 단언.
// 공유 팝업(openShareDialog)에 '참여 중인 사용자' roster 가 추가됐는지, 기존 게이트된
// 엔드포인트를 재사용하는지, XSS 안전(textContent)·캐시버스터 bump 를 정적으로 검증한다.
// (라이브 렌더 정본은 PB-0008 Windows-browser — 배포 후. 본 테스트는 회귀 가드.)
//
// 실행: node unit/feature-0003-agent-web-ui/tests/verify_share_participants.mjs
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const staticDir = join(here, "..", "src", "static");
const appJs = readFileSync(join(staticDir, "app.js"), "utf8");
const cssTxt = readFileSync(join(staticDir, "styles.css"), "utf8");
const indexHtml = readFileSync(join(staticDir, "index.html"), "utf8");

let pass = 0, fail = 0;
const ok = (cond, name) => {
  if (cond) { pass++; console.log(`  PASS ${name}`); }
  else { fail++; console.error(`  FAIL ${name}`); }
};

// openShareDialog 함수 본문만 추출(다른 함수의 우연 매칭 방지).
const shareStart = appJs.indexOf("async function openShareDialog(");
ok(shareStart >= 0, "openShareDialog 함수 존재");
const shareEnd = appJs.indexOf("\nasync function openConversationSettings(", shareStart);
const shareBody = shareStart >= 0 ? appJs.slice(shareStart, shareEnd > 0 ? shareEnd : shareStart + 8000) : "";

// 1. 팝업 골격에 참여자 섹션 + subhead 추가.
ok(/<div class="share-participants" aria-live="polite"><\/div>/.test(shareBody), "팝업에 .share-participants 컨테이너 추가");
ok(shareBody.includes("참여 중인 사용자"), "'참여 중인 사용자' subhead 라벨");

// 2. loadParticipants 헬퍼 + 기존 게이트된 members 엔드포인트 재사용.
ok(/const loadParticipants = async \(\) =>/.test(shareBody), "loadParticipants 헬퍼 정의");
ok(shareBody.includes("/api/conversations/${encodeURIComponent(cid)}/members"), "기존 GET /members 엔드포인트 재사용(신규 백엔드 없음)");

// 3. owner 우선 정렬 + role 배지.
ok(shareBody.includes("isOwnerMember"), "owner 우선 정렬 분기 존재");
ok(shareBody.includes('roleEl.textContent = "소유자"'), "owner '소유자' 배지");

// 4. XSS 안전 — 사용자명은 textContent(innerHTML 직접 주입 아님), 아바타는 기존 _msgAvatarEl 재사용.
ok(/nameEl\.textContent = name;/.test(shareBody), "사용자명 textContent 주입(XSS 안전)");
ok(shareBody.includes('_msgAvatarEl(m.account_id, name, "user", null,'), "_msgAvatarEl 아바타 재사용(Identicon 폴백 정합)");
ok(!/participantsBox\.innerHTML\s*=\s*[`'"][^`'"]*\$\{[^}]*m\.username/.test(shareBody), "username 을 innerHTML 템플릿에 직접 보간하지 않음");

// 5. 빈/에러 상태 처리.
ok(shareBody.includes("아직 참여 중인 다른 사용자가 없습니다"), "빈 roster 안내 메시지");
ok(shareBody.includes("참여자 목록을 불러오지 못했습니다"), "fetch 실패 안내 메시지");

// 6. 초기 로드 + 링크 생성 후 roster 갱신 배선.
const initCalls = (shareBody.match(/await loadParticipants\(\);/g) || []).length;
ok(initCalls >= 2, `loadParticipants 호출 ≥2 (초기 로드 + joinable 링크 생성 후 갱신) — 실측 ${initCalls}`);

// 7. CSS chip 스타일 추가.
ok(/\.share-participant\s*\{/.test(cssTxt), ".share-participant chip 스타일");
ok(/\.share-participant-role\s*\{/.test(cssTxt), ".share-participant-role 배지 스타일");

// 8. 캐시버스터 존재(구체 값은 후속 cycle 마다 advance — 존재 여부만 회귀 가드).
ok(/app\.js\?v=[0-9a-z-]+/.test(indexHtml), "app.js 캐시버스터 존재");
ok(/styles\.css\?v=[0-9a-z-]+/.test(indexHtml), "styles.css 캐시버스터 존재");

console.log(`\nverify_share_participants: ${pass} passed, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
