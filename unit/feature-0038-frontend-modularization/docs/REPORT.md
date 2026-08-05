---
doc_type: REPORT
feature_id: feature-0038-frontend-modularization
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
**ITEM-P5b 잔여(프론트 3파일 모듈 분할) initiative 완결** — PLAN-APPROVED(mckim 2026-08-03)
후 10 cycle 전건 머지·배포·POST-DEPLOY PB-0008 PASS (PR #1124/#1125/#1128/#1129/#1130/
#1132/#1133/#1141/#1142/#1143). 재발 방지 = CONVENTIONS §14. 로드맵 ITEM-P5b done.

**최종 구조 (2026-08-04 실측)**
- styles.css(9,328) → **소멸**, `css/` 7파일 (cascade 순서 보존, concat byte-parity 증명)
- admin.js **14,007 → 4,804줄 (-66%)** + `admin/` 9모듈(usage·aiops·settings·audit·
  accounts·roles·datasources·products·metadata, 계 9,354줄)
- app.js **13,216* → 11,119줄** + ES module 전환 + `app/` 4모듈(auth·profile·sidebar·
  messages, 계 2,161줄)  *Cycle 8 착수 시점 실측(병렬 세션 증분 포함)

## 2. Progress
- Done: 계획 승인 · Cycle 1~10 완결(TEST Run-001~043) · Final(CONVENTIONS §14·ROADMAP
  ITEM-P5b done·STATUS/wiki 정합)
- Done(후속, 2026-08-05): Phase A~B3 완결 — state-편입(#1147) · sidebar 추출(#1148) ·
  composer 추출(#1149) · progress 추출(#1150), 전건 배포+POST-DEPLOY PB-0008 PASS.
  **app.js 11,119 → 8,082줄(-27%)** · sidebar.js 1,138 · composer.js 2,140 · progress.js 460
- **AC-3 (오케스트레이터 ≤~3,000줄) 정직 보고 — 부분 달성**:
  admin.js 4,804줄 잔여 = 코어 유틸·권한 grid 인프라(계정/역할 공유)·pending/batch-apply
  엔진·대시보드·archives·sampleReview·탭 디스패치/바인딩. app.js 11,119줄 잔여 =
  composer/첨부·progress 폴러 3계층·그룹 대화·검색·메시지 편집/피드백·바인딩 init.
  **차단 요인(전부 문서화)**: 공유 가변 let(_dqaDrag·_sidebarCatchupTimer 류)의 양방향
  재할당 결합은 byte-동치 원칙 하 이동 불가 — state 편입 mini-change(비-중립·별도 승인)
  가 선행돼야 다음 감축이 가능. 이는 계획의 "심볼 단위 재실측" 조항으로 각 cycle 에서
  적발·기록해 온 구조적 한계이며, 무리한 이동(런타임 TypeError)보다 잔류가 정답.

## 3. Recent Changes
- 2026-08-03~04: 10 cycle 추출·배포 (CHG 11건 — MODIFY.md) + Final 정합
- 총 변경 횟수: 제품 코드 PR 10건 머지 + Final PR

## 4. Open Issues
- Cycle 7 (app.js `type="module"` 전환) 이 유일한 비-기계적 변환 지점 — 단독 cycle 격리
  + classic 순차 분할 fallback 을 계획에 명시함

## 5. Test Status
- 자동 테스트: cycle 별 make test RC=0 + §18.8 적대 패널 10회(BLOCK 4회 전건 흡수) — TEST §3 Run-001~043
- 수동 테스트: PB-0008 Windows-browser Run 11건 (사전 CSS QA + POST-DEPLOY 전 cycle)
- 미검증 항목: TEST §4 참조 (pre-existing 하네스 red 는 §8 목록)

## 6. Blocked Items
- 없음 (plan-review 대기는 §7 로 표기 — 비-승인 작업 없음)

## 7. Human Attention Needed
- 없음 — 후속 2축 완결: 하네스 정리(PR #1146) + 오케스트레이터 감축 Phase A~B3
  (PR #1147~#1150, 전건 배포·POST-DEPLOY PASS).

## 8. Suggested Improvements
- (기록만, C9 발견) `renderConversationList`(~520줄)의 후속 분리는 공유 DnD 상태
  `let _dqaDrag` 를 `state.dqaDrag` 프로퍼티로 편입하는 **비-중립 mini-change**(1클래스
  치환 + 테스트) 승인 후 가능 — byte-동치 원칙 하에서는 양방향 binding-write 결합으로 불가.
- (기록만) 분할 완료 후 verify-completion 또는 pre-commit 에 "단일 프론트 파일 N줄 초과
  WARN" 기계 게이트 추가 검토 — CONVENTIONS 문면 컨벤션의 enforcement 보강.
- ~~(기록만, C3 패널 발견) `tests/verify_admin_tab_gating.mjs` 2건 FAIL pre-existing~~
  → **2026-08-05 해소** — feature-0003 `harness-repair` cycle (CHG-20260805T1042) 이 ai-console
  탭 통합(feature-0021) 미추종 stale 앵커로 판정·현행 계약으로 갱신 + OR 게이트 3항목 개별 검증 추가.
- ~~(기록만, C8 패널 발견) `tests/win-browser-settings-notif.scenario.json` page 전역 의존~~
  → **2026-08-05 해소** — 전 블록 DOM 이벤트 경유 전환 + A(게이팅 매트릭스)는
  `verify_notify_gating.mjs` 신설 이관, 실 Windows Chrome 20스텝 전건 OK. (동일 죽은-전역 패턴이
  mention-hl-notify·notify-nobracket 시나리오에 잔존 + 시나리오 17개 base_url `:18080` stale —
  후속 후보로 feature-0003 REVIEW 에 이관 기록.)
- ~~(기록만, C4 패널 발견) `tests/verify_perm_self_scope.mjs` classic-script 주입 파손~~
  → **2026-08-05 해소** — `esm-classic-inject.mjs` 공용 strip 으로 perm_self_scope·db_rule_pending·
  ds_accordion_collapse 3건 복구. **CI 비배선 구조 자체는 잔존**(mjs 40개가 make test 밖 —
  배선 여부는 별도 검토 후보).
- ~~(C6 부채 상환 후 잔여) pre-existing red 목록 (db_rule_ui … bs_inline_desc/list_detail)~~
  → **2026-08-05 전건 해소** — feature-0003 `harness-repair` cycle 이 전수 실측(red 23 — §8 기록
  12 + Cycle 7~10 ESM 전환·jsdom 환경 소실로 추가 11)로 재확정 후 **40/40 green**. 원인 6유형·
  수리 상세는 feature-0003 CHG-20260805T1042 / REV-20260805T1042 참조.
