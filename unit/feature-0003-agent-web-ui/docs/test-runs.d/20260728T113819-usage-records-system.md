---
run_at: 2026-07-28T11:38:19+09:00
session: ai/claude/feature-0003-usage-records
scope: [usage-records, system-usage, drilldown, navigation, pb0008, contrast, responsive]
verdict: PARTIAL PASS (핵심 요구 4/4 라이브 확정 / 후순위 표기 2건 POST-DEPLOY 이관)
---

### Run (2026-07-28) — LLM 사용량 '사용 기록' 시스템 사용분 편입 — **Environment: Windows-browser (PB-0008) + 라이브 DB 실측**

CHG-20260728T113819-usage-records-system. 접속 `bin/win-browser.py goto --url https://localhost/admin`
(200, Chrome/150.0.7871.115), 계정 `bootstrap_admin`. eval 게이트 `1+1 → 2` PASS.

**검증 방식 주의**: 미머지 변경이라 web-a/web-b 에 `docker cp` 로 임시 반영 후 검증했다
(PB-0008 미머지 QA 관례). 이 방식의 한계는 아래 §잔여 참조.

#### ① 여집합 정합 (라이브 PG 실측 — 최근 30일)

```
total = 15,373 호출
  conv_side (INNER JOIN + owner NOT NULL) =    897
  sys_side  (NOT(joinable AND owner NOT NULL)) = 14,476
  897 + 14,476 = 15,373  ← 누락·중복 0
```
집계 SQL 실행 17.99ms · 데이터소스 해소 SQL 13.81ms (유계).
토큰 기준으로는 대화 37.4M vs **시스템 36.4M** — 종전 목록이 전체의 약 **49% 를 누락**하고
있었음을 라이브에서 확정.

#### ② 모달 명칭 + 통합 표 — PASS

- 모델 도넛 세그먼트 클릭 → 제목 **`claude-haiku-4 · 사용 기록`** (종전 "대화 목록").
- 헤더 `[구분, 대화 / 작업 · 대상, 주체, 호출, 토큰, 추정 비용, 최근 사용]`.
- 283행 = 대화 83 + 시스템 200, **토큰 큰 순 병합 정렬**. 예: 3행째가 시스템
  `콘텐츠 그룹 라벨 · mssql-qa-idc / 인사이트 워커 / 875호출 / 2,257,480토큰 / $7.35`.
- 안내문 `대화 행은 새 탭에서 해당 대화로, 시스템 행은 그 작업이 다룬 객체의 관리 화면으로 이동합니다.`
- 증적: `docs/evidence/pb0008-usage-records-modal-20260728.png`

#### ③ "(시스템)" 역할 클릭 회귀 수정 — PASS

역할 막대 `(시스템)` → 계정 드릴 `(시스템)` 막대 클릭 →
제목 `(시스템) · 사용 기록`, **시스템 200행 / 대화 0행**.
종전에는 `_usage_account_ids_for_role → None` + 프론트 early-return 으로 **아무 일도 일어나지
않았다**(막대는 36,406,543 토큰 표시). 상위 3행 실측:
`콘텐츠 그룹 라벨 · mssql-qa-idc(879)` · `테이블 분석(1,196)` · `용어사전 후보(228)`.

#### ④ "어떤 작업 / 어떤 객체" 표기 — PASS

- 작업명이 taxonomy 한글 라벨로 표시(`그래프 노드 분석`·`콘텐츠 그룹 라벨`·`용어사전 후보`·
  `ENUM 코드 후보`·`제품 분류 제안`·`답변 적대 검증`). 신규 편입 4 task 가 raw 문자열로
  노출되지 않음을 확인.
- 대상 객체를 monospace 로 병기(`dbGame.usp_mod_pet_misc()` · `log_v2.tf_info_table` ·
  `gunzgame.accountitem` · `mssql-qa-idc`).
- 주체를 사람이 읽는 워커명으로(`인사이트 워커` / `요청 처리 워커`).

#### ⑤ 클릭 → 해당 화면 이동 — PASS

| 클릭한 행 | 결과 |
|---|---|
| `콘텐츠 그룹 라벨 · mssql-qa-idc` | `activeTab=graph`, `graphScopeSelect.value=mssql-06656002eda6`, 라벨 `mssql-qa-idc` — **데이터소스 자동 해소** |
| `테이블 분석` | `activeTab=metadata`, `metaSubtab=tables`, 목록 153건 |
| `스키마 분석 · log_v2` | `activeTab=metadata`, `metaSubtab=tables`, **검색창 `log_v2` 자동 주입** |
| `용어사전 후보` | `activeTab=metadata`, `metaSubtab=glossary` |
| `에이전트 추론`(대상 없음) | `AI 운영 현황 > 운영 현황` 폴백 |

이동 성공 시 모달 자동 닫힘 확인.

#### ⑥ 모호 표기(정직 저하) — PASS (in-cycle 결함 수정 후)

최초 검증에서 `log_v2`(실제로는 3개 데이터소스에 걸침)가 **모호 안내 없이** 이동했다.
원인 = `scope_ambiguous` 를 record 최상위에만 싣고 `nav` 에 누락. 수정 후 재검증:
**107행**에 `(데이터소스 여럿 — 화면까지 이동)` 표기, 해당 행 클릭 시 데이터소스 스코프를
바꾸지 않고 화면까지만 이동.

#### ⑦ 대비 실측 (getComputedStyle 기반, 실 Chromium)

| 선택자 | 대비 | 판정 |
|---|---|---|
| `.usage-rec-badge--sys` | 6.63 | PASS |
| `.usage-rec-badge--conv` | 4.75 | PASS |
| `.usage-rec-link` | 5.17 | PASS |
| `.usage-rec-target` | 5.17 | PASS |
| `.usage-rec-goto` | 7.11 | PASS |
| `.usage-rec-note` | 4.12 → **7.11** | 최초 FAIL(AA 4.5 미달) → `--text-muted`→`--text-2` 수정 후 PASS |

#### ⑧ 폭/잘림 — PASS(1차) → 사용자 피드백 반영 후 **재실측 필요**

- 720px 고정폭에서 7열이 되며 `최근 사용` 열이 잘림을 캡처로 포착 → `min(940px,94vw)` 로 1차 수정,
  `tableWidth 776 < wrapWidth 885`, 전체 일시 표시 확인.
- 이후 사용자 피드백("본문 열 과도 줄바꿈 + 반응형 확장 필요")으로 **반응형**
  `min(1240px,96vw)` + 부수 열 `width:1%` 배분 + `overflow-wrap:anywhere` 로 재수정.
  모달 실폭 1199px(뷰포트 1249) 까지는 확인했으나 **열 재배분 결과는 미실측**(아래 §잔여).

### 잔여 — POST-DEPLOY 로 이관 (2건)

두 항목은 코드가 아니라 **검증 환경** 때문에 pre-deploy 확정에 실패했다:

1. **주체 열 3분기**(실재 대화 링크 / `삭제된 대화` / 워커명) — 미확정.
2. **열 폭 재배분 + 줄바꿈 해소**(사용자 피드백 반영분) — 미확정.

**사유 (근본원인 규명 완료, 제품 결함 아님)**:

- `graph/graph-core.js` 등이 `import { adminState } from "../admin.js?v=dev"` 로 admin.js 를
  **고정 URL 로 재-import** 한다. 정상 빌드에서는 `bin/.../inject_asset_stamp.py` 가 HTML 과
  **first-party JS import specifier 의 `?v=` 를 함께 재작성**해 단일 인스턴스가 되지만,
  `docker cp` 임시 반영은 빌드를 거치지 않아 **entry 와 graph import 가 서로 다른 URL** 이 되고
  브라우저가 admin.js 를 **두 인스턴스**로 로드했다. 캐시에 남은 구버전 인스턴스가 이벤트를
  처리해, 서버 파일·로드 URL 이 모두 신버전인데도 화면은 구버전 렌더를 보였다
  (분기 마커 주입으로 확정).
- 동시에 **다른 세션이 web 롤링 배포**(`mysql-ai-web:0062acb3`)를 진행 중이어서 web-a 가
  SIGKILL·재생성되며 임시 반영분이 소거됐다(11:29~11:36). 라이브 조작을 즉시 중단했다.

실 배포본에서는 asset stamp 가 entry·import 양쪽에 동일 주입되어 단일 인스턴스가 되므로 위
아티팩트가 재현되지 않는다. 따라서 두 항목은 **머지·배포 후 POST-DEPLOY PB-0008** 로 확정한다.

**Verdict: PARTIAL PASS** — 사용자 요청 4개 축(① 시스템 내역 편입 ② 명칭 '사용 기록'
③ 작업·객체 인지 ④ 클릭 이동)은 라이브에서 모두 확정. 표기 세부 2건만 POST-DEPLOY 이관.
