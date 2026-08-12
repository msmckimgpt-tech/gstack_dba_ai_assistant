---
doc_type: TEST
feature_id: feature-0040-db-object-explorer
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Strategy

역할 축 도입의 **주 위험은 허위 부재**다 — 미지원 역할의 0행이 "없다" 로 새면 그 자체가
결함이다. 따라서 단언은 "동작한다" 가 아니라 **"미지원·위임·권한 3상태가 0건으로 뭉개지지
않는다"** 를 문자열 수준에서 고정한다(§16.7 G10 구조 가드).

## 2. Test Cases

| ID | 대상 | 검증 |
|---|---|---|
| TEST-20260812T030000-taxonomy | `db_object_roles` | 6역할 선언 · 수집 5역할 · 벤더/한국어 어휘 정규화 17종 |
| TEST-20260812T030000-absence | 안내문 | UNSUPPORTED 가 '없다' 로 서술되지 않음 · DELEGATED 는 재라우팅 |
| TEST-20260812T030000-matrix | `Dialect` | MySQL/MSSQL 지원상태 · **routine 이 어떤 방언에서도 DELEGATED** |
| TEST-20260812T030000-boundary | dialect SQL | 내부 스키마 제외 · Agent 작업 허용DB 필터 · **빈 allowlist fail-closed** · 시노님 대상 마스킹 · 중괄호 스키마명 |
| TEST-20260812T030000-tools | 도구 | 등록·enum 정합 · 미지원/위임/미상 역할 응답 · 권한 caveat · 상한 포화 표면화 · 실패≠부재 |
| TEST-20260812T030000-graph | 투영 | 라벨 화이트리스트 · 관계/계층 분류 · **key 에 역할 포함** · OBJECT_ON/USES 분리 |
| TEST-20260812T030000-render | 그래프 빌드 | 컨텐츠 방출·클러스터 소속 · 역할별 kind 필터(노드+엣지) · 소유/참조 스타일 구분 · 루틴 미병합 · 미등재 역할 폴백 |

## 3. Test Run History

### Run (2026-08-12) — feature-0040 역할 기반 DB 객체 탐색 (Major §12.3) — **Environment: CLI**

**신규 테스트**
- `unit/feature-0002-agent-core/tests/test_db_object_explorer.py` — **56 PASS**
- `unit/feature-0003-agent-web-ui/tests/headless/test_g6build_dbobjects.js` — **21 PASS**

**회귀 (컨테이너 `mysql-ai-agent:current`, `PYTHONDONTWRITEBYTECODE=1`)**
- agent-core: **2851 passed · 3 skipped · 1 failed** — baseline 2795 passed 대비 +56(신규분)
  이며 **회귀 0**. 유일 failure `test_oauth_exhaustion_gate.py::test_write_failure_after_
  successful_post_cannot_kill_slot_selection` 는 **pre-existing 환경 결함**: 컨테이너 이미지에
  `chattr` 바이너리가 없어 `FileNotFoundError`. **미변경 main 에서 동일 재현 확인**.
- web-ui(feature-0003): **1383 passed · 0 failed**.
- headless 그래프 스위트 전량(24 파일): **1179 PASS 단언 · 실패 파일 0**.
- `bin/migrate-lint.sh`: **PASS** — `0054_db_objects` expand-safe · head 단일성 · MAX_MIGRATION 일치.
- `node --check`: 변경 4 모듈 + 번들 PASS.

**결함 적발(테스트가 실제로 잡은 것 — 카고컬트 아님)**
1. `test_g6build_dbobjects` ① 이 **DbObject 가 `__terms__` 클러스터로 강등**되는 실결함을
   포착 → `graph-state.js` `_metaSchemaComboOf` 에 DbObject 누락이 원인. 수정 후 PASS.
   (칩 색·아이콘은 맞는데 **자리가 틀리는** 형태라 코드 리뷰로는 놓치기 쉬운 결함.)
2. 초판이 `routine` 을 **UNSUPPORTED** 로 판정해 "MySQL 은 프로시저를 지원하지 않습니다"
   라는 거짓을 냈다 → `DELEGATED` 상태 신설 + base 클래스 선점 처리로 구조적 봉인.
   `test_routine_is_delegated_on_every_dialect` 가 신규 방언에도 자동 적용된다.
3. MSSQL cross-DB 경로에서 `r[1:]` 오프셋 오류로 **본문 매칭 열이 조용히 비던** 결함.

**타 feature 테스트 1건 수정 + 역검증**
`test_catcluster_panel_scroll.js` 의 인자-전체 pin 단언 2건을 "focusFam 이 마지막 인자" 로
좁혔다(사유 TASK §4). **뮤테이션 역검증**: 내 번들 67 PASS · baseline 번들 67 PASS(하위호환)
· `focusFam` 제거 시 **65 PASS / 2 FAIL** — 보호 강도가 유지됨을 실증.

### Run (2026-08-12) — **Environment: Windows-browser** (실 Chrome 150 · WebGL)

라이브 `/admin` 은 정적 자산 baked + `db_objects` 미충전이라 배포 전 도달 불가지만,
§16.3 「검증 사전-descope 금지」에 따라 **먼저 실측 경로를 consult** 했다 —
`win-browser.py doctor` 가 브리지 가용을 확인해 **integration-harness 경로**(선례
`20260728T161940-routine-column-edges.md` §7)로 실 Windows Chrome 검증을 수행했다.

전문·스크린샷·재현 레시피는 **파일 소유 feature** 쪽 fragment(§16.3 check #13 규약):
`unit/feature-0003-agent-web-ui/docs/test-runs.d/20260812T0310-feature-0040-db-object-explorer.md`

요약:
- **렌더**: 역할 객체 5종 방출 · 역할 아이콘 접두 · 구리 칩(#b0592a) · 스키마 클러스터 소속 ·
  `OBJECT_ON` 2건 전부 **파선** / `OBJECT_USES` 5건 전부 **실선** (스크린샷 픽셀 확인).
- **인터랙션**: 역할 토글 실 trusted click → 노드 1 + **엣지 2종 함께** 제거, 루틴·테이블
  불변(격리), 재클릭 복원, `aria-pressed` 정합.
- **상세 패널**: 역할별 속성(시점 AFTER · 이벤트 INSERT · 활성) + 대상 테이블 라벨 +
  **AI 능동 분석 진입점** 존재 확인.
- **부수 적발·수정**: 상세 배지가 내부 라벨 `DbObject` 노출 → 역할 한글명으로 교체.

### POST-DEPLOY 잔여 (라이브 실데이터)

배포 + 마이그레이션 0054 + insight cadence 이후 실 스키마에서 재확인:

- [ ] `db_objects` 행 존재 확인(마이그레이션 적용 + insight 1 cadence 경과)
- [ ] 실 스키마 그래프에서 역할 객체 칩이 테이블·루틴과 나란히 렌더
- [ ] 실데이터 트리거의 소유선(파선)·참조선(실선) 육안 구분
- [ ] 역할별 토글 5종 · 상세 패널 속성 · 범례 표시 · pageerror 0
