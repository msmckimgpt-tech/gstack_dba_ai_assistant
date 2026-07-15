---
run_at: 2026-07-16T00:39:01+09:00
session: ai/claude/feature-0003-graph-cluster-detail-collapse
scope: 스키마 클러스터 상세 패널 목록에 컨텐츠 카테고리(sim-group)별 접기/펼치기(collapsible) 추가 — 헤딩 disclosure 토글 + 모두 접기/펼치기 + 재렌더 접힘 유지 (20260716T0039-graph-cluster-detail-collapse)
verdict: 정적 PASS · POST-DEPLOY PB-0008 라이브 DEFERRED
---

### Run 1 — 문법/균형 검증 (Environment: node --check + CSS balance)
- `graph-ctxmenu.js`·`graph-state.js` ESM `node --check` PASS.
- `graph.css` brace 221:221 · comment `/*`:`*/` 66:66 (주석 `*/` 조기종료 hazard 없음 — CHG-20260714T184717 회귀 방지 불변식 준수). 단일 파일 아님(3파일: ctxmenu·state·css).

### Run 2 — 정적·로직 검증 (Environment: 코드 리뷰)
- **헤딩 disclosure**: 그룹 `<li class="amgr-ct-group" role="button" tabindex="0" aria-expanded data-group-key>` + 캐럿 `▾`/`▸`. 초기 렌더는 `_metaGraph.panelGroupCollapsed.has(sg.key)` 로 헤딩 `is-collapsed` + 멤버 행 `amgr-ct-collapsed`(display:none) + 캐럿/aria 초기값 일치.
- **토글 순회**: `_toggleCtGroup(grp)` = `grp.nextElementSibling` while 루프로 **다음 `.amgr-ct-group` 헤딩 전까지의 멤버 행만** `amgr-ct-collapsed` 토글(마지막 그룹은 끝까지). 캐럿 텍스트·`aria-expanded`·`panelGroupCollapsed` 동기 갱신.
- **click 분기**: `ul` click 위임에서 `closest(".amgr-ct-group[data-group-key]")` 먼저 판정→토글 후 return; 아니면 `_rowKeyOf`(행) 조회. 헤딩 자식(캐럿/라벨/count/trunc) 클릭도 closest 로 헤딩 승격. 행/헤딩 상호배타(헤딩엔 `data-node-key` 없음, 행엔 `data-group-key` 없음).
- **키보드**: `keydown` Enter/Space 가 포커스된 헤딩 토글(Space `preventDefault` 로 스크롤 방지). 행(button)은 네이티브 Enter/Space=click 유지.
- **모두 접기/펼치기**: `#metaGraphCtCollapseAll` — `anyExpanded ? 접기 : 펼치기` 로 대상 그룹만 `_toggleCtGroup`. getElementById 는 매 렌더 새 버튼(innerHTML 재생성)에 바인딩 → 누적 없음.
- **위임 누적**: `_toggleCtGroup` 는 공통 스코프, click/keydown 위임은 `ul`(매 렌더 재생성)에 부착 → GC 로 누적 없음(fulllist 와 동형).
- **회귀/XSS**: 전체 출력(ROW_CAP)·집계/개수·행 클릭 조회·hover pan 불변. `sg.label`·`data-group-key`(sg.key) 는 `esc()` 경유. sg.key 의 제어문자 은 HTML 속성값/`getAttribute`(원문 반환)에서 유효(선택자 미사용 — closest+classList 로만 처리).
- **§18.8 적대 리뷰 MINOR 2 수정 반영**: (#1) '모두 접기/펼치기' 라벨 stale → `_syncCollapseAllLabel()`(전 그룹 상태 재계산)을 `_toggleCtGroup` 말미 호출; (#2) 로컬 `esc`(2262)에 `.replace(/"/g,"&quot;")` 추가(`data-group-key` 등 속성 breakout 방지, 파일 내 강한 esc 와 정합). 재검증 `node --check` PASS.
- 결과 **PASS(정적)** — §18.8 적대 리뷰 상세는 REVIEW.md(REV-20260716T003901) 참조.

### Run 3 — POST-DEPLOY 라이브 시각검증 (Environment: Windows-browser, PB-0008 relay) — **PASS**
- 배포: PR #835 → main 00454608 + `sudo -E bin/deploy-web.sh` 무중단 롤링(web-a/web-b·워커 recreate·soak 통과). 서빙 자산 `panelGroupCollapsed`·`_toggleCtGroup` grep=10(web-a).
- 방법: win-browser.py 실 Windows Chrome relay, https://localhost/admin(로그인 세션) → 그래프 뷰 > mssql-dk-dev(DK온라인) > dk_data_release_main(423항목·66 컨텐츠 카테고리) 상세.
- 결과 **PASS**:
  1. **collapse UI 노출**: 섹션 헤더 "테이블·함수·프로시저 (423) ▾ 모두 접기"(collapse-all 버튼), 66 그룹 헤딩(data-group-key) + 66 캐럿.
  2. **그룹 헤딩 토글**: "NPC 콘텐츠"(41 멤버) 라벨 자식 click → 이벤트 위임 승격 → 접힘(멤버 41행 표시→41행 display:none, 캐럿 ▾→▸, aria-expanded=false); 재click → 펼침(41행 복원·▾).
  3. **모두 접기/펼치기**: 버튼 click → 66/66 그룹 접힘·전 행 숨김·라벨 "▾ 모두 접기"→"▸ 모두 펼치기"; 재click → 66 펼침·라벨 복원. (라벨-동작 정합 = MINOR #1 수정 실증.)
  4. **재렌더 접힘 유지(핵심)**: "NPC 콘텐츠" 접기 → 다른 그룹 행(UnderageGamePlayLimit) click 로 노드 상세 이동 → "← 뒤로" 클러스터 상세 재렌더 → **"NPC 콘텐츠" 여전히 접힘**(caret ▸·41행 숨김). `panelGroupCollapsed`(sg.key="panel:dk_data_release_mainbe:0", 제어문자 포함) 매칭 정상.
  5. **키보드 토글**: "퀘스트 시스템" 헤딩 포커스 → Enter 접힘 / Space 펼침(Space 스크롤 없음).
  6. **행 클릭 조회 불변**: 행 code 자식 click → 노드 상세(TABLE UnderageGamePlayLimit) 정상. **pageerror 0**·docReady complete.
  7. 스크린샷 육안: `▸ NPC 콘텐츠 41`(접힘·행 없음)·`▾ 퀘스트 시스템 10`(펼침·10행·포커스)·`▸ 성 시스템 3`(접힘) 공존 + 헤더 "▾ 모두 접기" 버튼.
- visual_verification_scope: always — 충족. evidence: collapse_evidence.png.
