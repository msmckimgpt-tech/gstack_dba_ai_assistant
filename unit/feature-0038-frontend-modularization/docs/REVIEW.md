---
doc_type: REVIEW
feature_id: feature-0038-frontend-modularization
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260803T174500-css-split
- Related Change: CHG-20260803T174500-css-split (Cycle 1 — ITEM-P5b 잔여, PLAN-APPROVED by mckim 2026-08-03)
- Reason: ssot-consolidation ROADMAP ITEM-P5b 실측 갱신(2026-08-03) — 백엔드는
  feature-0012 완결, 잔여 실체는 프론트 3파일(+23~59% 증가 중). styles.css 가
  가장 저위험(선언적·byte-parity 증명 가능)이라 Cycle 1 로 선행하고, 이 cycle 에서
  롤백 리허설을 실증해 이후 JS cycle 의 절차를 고정한다.
- Alternatives Considered:
  - 사용처 기준 재그룹(페이지별 CSS 분리 — index 전용/admin 전용): 셀렉터 사용처
    전수 분석이 필요해 behavior-neutral 증명이 불가능 → 기각. 순차 분할은 "concat ==
    원본" 이 증명이 된다. 재그룹은 분할 정착 후 후속 개선으로 이연.
  - `@import` 체인: 직렬 로딩 성능 저하 + 프로젝트 선례(link 나열, graph.css) 위배 → 기각.
- Risks:
  - **pre-existing 주석 결함 1건 보존**: 구 styles.css L5577 (`admin.css` L1880)
    `/* … --text*/ …` 가 주석을 조기 종료시키고 잔여 토큰이 무효 CSS 로 error-recovery
    되는 상태 — 원본에 이미 존재하며 분할 후에도 같은 파일 내에 온전히 보존되어 동작
    동일. 본 cycle 은 behavior-neutral 계약이라 **수정하지 않고 기록만** 한다 (후속
    cycle 또는 별도 Minor fix 후보).
  - 분할 파일 수 7 = HTTP 요청 증가: Caddy HTTP/2 + immutable 스탬프 캐시로 무시 가능.
  - stale PoC 참조: `unit/feature-0016-metadata-graph/pixi-migration/poc/integration-harness.html`
    이 구 styles.css 절대경로를 참조 — 개발용 PoC(비서빙)이고 feature-0016 활성 세션
    영역이라 본 cycle 에서 손대지 않음 (REPORT §8 기록).
- Open Questions: 없음
- Human Approval Needed: 완료 — PLAN-APPROVED by mckim on 2026-08-03 (TASK.md §2.1,
  risk_grade Critical 은 ROADMAP ITEM-P5b 지정 등급. 본 cycle 실변경은 byte-parity
  증명이 있는 CSS 물리 분할로 회귀 표면 최소)

## REV-20260803T181500-css-split-panel [SUBAGENT:qa] — SHIP
- Related Change: CHG-20260803T174500-css-split (Cycle 1)
- 패널: fresh-context 적대 1렌즈(qa/frontend — behavior-neutrality 반박 시도, 전 항목 실측 명령 동반). **BLOCKING 0 / MAJOR 0 / MINOR 2.**
- 실측 확인: ① concat byte-identical(322,993B, sha256 일치·link 순서 정합) ② html 배선(7-link 순서·구 링크 잔존 0·graph.css 후순 유지·vendor pin 미접촉·share.html 무변경) ③ per-file 파싱(주석 토크나이저·brace 스캐너 전 파일 균형·고아 `}` 0·`--text*/` quirk 는 파일 중앙 보존) ④ 잔여 참조 0(런타임/테스트 실읽기 기준·JS 동적 stylesheet 조작 0·synthetic fixture 2건은 실파일 미참조) ⑤ 테스트 5파일 순서 정합 + py_compile/ruff PASS ⑥ inject_asset_stamp 재귀 커버·vendor 제외 오폭 없음·decide_cache_control 경로 무관·deploy asset_stamp_verify 커버.
- MINOR 흡수: ② 3연속 빈 줄 코스메틱 → 본 commit 에서 정리. ① CSS 요청 수 1→7(head 내 render-blocking 이라 FOUC 없음·HTTP/2) → 수용(기록만).
- 판정: **SHIP** — behavior-neutral 주장 반박 실패.
- Timestamp: 2026-08-03T18:15:00+09:00
