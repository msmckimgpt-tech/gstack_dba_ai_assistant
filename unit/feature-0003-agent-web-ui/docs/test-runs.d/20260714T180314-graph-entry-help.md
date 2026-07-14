---
run_at: 2026-07-14T18:03:14+09:00
session: graph-entry-help (ai/claude/feature-0003-graph-entry-help)
scope: 그래프 뷰 첫 입장 조작 도움말 팝업(닫기·재확인 가능, localStorage 1회 자동노출) + 중간버튼 팬 커서 grabbing 표식 (feature-0003 web/UI 프론트, 그래프 도메인 정본 feature-0016)
verdict: PASS (코드/정적 검증) · Windows-browser 라이브 DEFERRED(배포 후)
---

### Run (2026-07-14) — graph-entry-help: 첫 입장 도움말 팝업 + 중간버튼 커서 (Minor §12.3 — feature-0003 web/UI 자산, frontend-only, additive) — **Environment: node --check + 정적 구조 검증**

- 변경 파일(3, additive): `static/admin.html`(❓ 도움말 버튼 + `#metadataGraphHelp` 오버레이 마크업) · `static/graph/graph.css`(`.amg-help-*` 스타일) · `static/graph/graph-core.js`(`_metaGraphShowHelp`/`Hide`/`MaybeAutoHelp`/`BindHelp` + `_metaShowGraph` 훅 + 중간버튼 `mousedown` 커서 표식).
- 문법/구조: `node --check --input-type=module`(graph-core.js) **PASS** · admin.html 도움말 블록 `amg-help` 20 매치·태그 균형 · graph.css 중괄호 **215/215 균형** · 새 심볼(`_metaGraphBindHelp`/`MaybeAutoHelp`/`ShowHelp`/`HideHelp`/`_META_HELP_SEEN_KEY`) 전수 존재.
- 로직 계약(코드 정독 확인):
  - 첫 진입 자동노출: `_metaShowGraph`(진입 1회, admin.js `graphInitialized` 가드) → `_metaGraphMaybeAutoHelp` → `localStorage("metaGraphHelpSeen") !== "1"` 일 때만 표시. localStorage 접근 실패는 try/catch 로 '미확인=노출' 안전 강등(기존 metaGraphHiddenKinds/metaGraphDetailW 관례 동일).
  - 닫기 4경로: ✕(`#metadataGraphHelpClose`)·"알겠습니다"(`#metadataGraphHelpOk`)·배경(`data-amg-help-close`/오버레이 여백 target 판정)·Esc(document capture keydown, 표시 중에만 등록·해제). 모든 닫기가 `_metaGraphHideHelp` → seen 플래그 set + ❓ 버튼 포커스 복귀.
  - 재확인: ❓ `#metadataGraphHelpBtn` → `_metaGraphShowHelp`(seen 무관 항상 표시).
  - 바인딩 멱등: `_metaGraph._helpBound` 가드(재진입 이중 바인딩 차단).
  - 중간버튼 커서: `#metadataGraphCanvas` `mousedown` button===1 → `preventDefault`(기존 autoscroll 억제) + `cursor="grabbing"`; 복원은 mouseup(단 `buttons & 4` 여전 눌림이면 유지 — 팬 중 깜빡임 방지)·window `blur`(뗌 이벤트 유실 대비). 캔버스 명시 cursor 부재 → 자식 `<canvas>` 상속(렌더러 무관).
- 비변경: 백엔드/엔드포인트/RBAC/스키마 0 · 기존 그래프 상호작용(팬·노드드래그·우클릭·줌·미니맵)·이벤트 바인딩 0 · cache-buster `?v=dev` placeholder(빌드 content-hash 자동주입) 수기편집 없음.
- §18.8: 3파일·비파괴·additive·백엔드/RBAC 무변경 Minor → 패널 skip.
- 결과: 코드/정적 검증 **PASS**.

### Run (2026-07-14) — 도움말 팝업·중간버튼 커서 시각검증 — **Environment: Windows-browser (배포 후 라이브로 이연)**

- **미수행 사유(§15.4.1 baked 자산)**: 정적 자산(admin.html/graph.css/graph-core.js)은 web 이미지에 baked → merge + `deploy-web` 재배포 후에만 서빙 자산·런타임 실측 가능(feature-0003 web/UI 자산의 확립 패턴). win-browser relay 로 라이브 시각검증 가능(PB-0008) → **POST-DEPLOY 라이브 append 예정**.
- **배포 후 계획(PB-0008, win-browser.py relay @ https://localhost/admin 그래프 뷰)**:
  - (a) **첫 입장 자동노출**: `localStorage.removeItem("metaGraphHelpSeen")` 후 그래프 뷰 진입(또는 새 프로필/시크릿) → 조작 안내 팝업 자동 1회 노출.
  - (b) **닫기 4경로**: ✕·"알겠습니다"·배경 클릭·Esc 각각으로 닫힘 + `localStorage.getItem("metaGraphHelpSeen")==="1"` 확인.
  - (c) **재진입 무자동노출·재확인**: 닫은 뒤 탭 이탈→재진입 시 자동노출 없음, ❓ 도움말 버튼 클릭 시 재노출.
  - (d) **중간버튼 커서**: 캔버스에서 가운데 버튼 누른 채 드래그 → 커서 `grabbing`·팬 동작 정상, 버튼 뗌 시 커서 복원(getComputedStyle 캔버스 cursor eval).
  - (e) **회귀/무결**: 그래프 렌더·기존 상호작용 정상, pageerror 0, 스크린샷.
- 결과: 정적 검증 PASS · 라이브 시각검증 **DEFERRED(배포 후)**.
