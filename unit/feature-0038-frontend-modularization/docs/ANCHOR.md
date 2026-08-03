---
doc_type: ANCHOR
feature_id: feature-0038-frontend-modularization
created_at: 2026-08-03T18:00:00+09:00
status: active
edit_policy: mixed
source_of_truth: true
---

<!--
ANCHOR.md — External Anchor Document (9번째 1급 문서)
정책 요약 (AGENTS.md §18): §1~§3 rewrite 가능 / §4 append-only·human-only /
Conflict Protocol / 24h bootstrap grace.
-->

# ANCHOR: feature-0038-frontend-modularization

## §1. 외부 관점 요약

- **"왜 동작 변경이 하나도 없는 리팩터에 unit 하나를 통째로 쓰지?"**
  → risk_grade Critical (라이브 web app 런타임 회귀) + 다중 cycle initiative 라서다.
  백엔드 분할(feature-0012)과 동일한 구조 — 코드는 feature-0003 에 거주하고, 본 unit 은
  계획·게이트·검증 기록의 홈이다. 근거는 "머지 충돌"이 아니라 **파일 크기로 인한 AI
  로드·편집 정확도 저하**(app.js 충돌 최근 60일 0건 — ssot ROADMAP §3b 실측).
- **"왜 번들러(vite 등)를 안 쓰고 `<script>`/`<link>` 나열이지?"**
  → 본 스택은 무번들 + 빌드 시 `?v=` content-hash 스탬프(inject_asset_stamp.py) 체계다.
  번들러 도입은 배포 스파인·캐시 무결성·테스트 하네스 전부를 재설계하는 별도 initiative 로,
  behavior-neutral 분할과 섞으면 롤백 단위가 깨진다.

## §2. 대안 분기

- **Alt-A: big-bang 일괄 분할 (한 PR 로 3파일 전부).** 페르소나: 리팩터를 빨리 끝내고
  싶은 소규모 팀. 안 고른 이유: 로드맵 게이트가 명시 금지 — 라이브 web app 에서 회귀
  원인 격리·롤백 단위가 소멸한다. 추출 단위별 PR/배포가 정책 요구.
- **Alt-B: 번들러 도입 후 ES module 트리로 재구성.** 페르소나: 프론트 전담 개발자가
  있는 제품 팀. 안 고른 이유: §1 참조 — 배포/캐시/테스트 인프라 전면 재설계가 필요해
  Critical 리팩터와 결합 시 위험이 곱해진다. 분할 완료 후 별도 검토 가능.
- **Alt-C: app.js 를 classic script 순차 분할 (module 전환 없이).** 페르소나: 실행
  타이밍 변화를 극도로 회피하는 운영 팀. 채택 유보 이유: admin.js↔graph/ 의 module
  선례가 이미 라이브 검증됐고 이중 인스턴스화 가드(asset-stamp)가 module 전제라
  일관성이 낫다. 단 Cycle 7 게이트 실패 시 **fallback 경로로 유지**한다.

## §3. 가정된 사용 시나리오

- **6개월 후 다른 AI 세션이 "작업 화면 진행 표시가 안 풀린다" 회귀를 고칠 때:**
  현재는 app.js 13,165줄 전체를 로드해야 progress 폴러를 찾는다(컨텍스트 상한 초과로
  부분 로드 → 오편집 위험 — "요청 미수행" 증상의 실제 기여 요인). 분할 후에는
  `app/progress.js` 하나만 열면 되고, 소스-추출형 테스트도 그 파일만 바라본다.
  이것이 본 initiative 의 수혜자이자 성공 판정 기준이다.

## §4. 외부 검증 로그 (append-only)

(엔트리 없음 — 일반 TASK cycle 완료 조건은 아님)
