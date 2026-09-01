---
run_at: 2026-09-01T12:40:00+09:00
session: ai/claude/metadata-term-scope
scope: feature-0003-agent-web-ui (cross-cut — 정본 feature-0002)
verdict: PASS(CLI) / DEFERRED(Windows-browser)
---

# Run — 메타데이터 콘솔 통용범위 축 · 브리지 용어 수신

## Environment: CLI

| 대상 | 결과 |
|---|---|
| `make test` (컨테이너 전 feature) | **PASS** rc=0 · ruff `All checks passed!` |
| `tests/test_bridge_glossary_terms.py` (신규 14건) | PASS — 러너 마커 파싱 6 · 서버 수신 4 · 프롬프트 계약 2 · 상한 2 |
| `tests/test_metadata_glossary_enum.py` · `test_metadata_glossary_autoreg.py` | PASS (계약 갱신: `term_tier`·`inherited`·`inherited_count`) |
| `node --check static/admin/metadata.js` (ESM) | PASS |

## Environment: Windows-browser — **이 cycle 미수행 (사유 명시)**

`visual_verification_scope: always` 대상(웹 자산 변경: `static/admin/metadata.js` 폼 필드·배지,
`admin_metadata.py` 응답 필드). 그러나 **배포 전에는 이 화면을 검증할 수 없다**:

변경된 화면이 읽는 `kb_glossary.term_tier` · `glossary_feedback.term_tier` 컬럼은 alembic 0057
이 만든다. 라이브에 그 마이그레이션이 적용되기 전에는 `list_glossary_admin` 의 SELECT 가
`UndefinedColumn` 으로 실패해 목록 조회 자체가 503 이 된다 — 지금 브라우저를 띄우면 **바뀐
화면이 아니라 조회 실패 화면**을 검증하게 되고, 그 PASS/FAIL 은 이 변경에 대해 아무것도 말하지
않는다(§16.7 G4 — 경계를 건드리지 않은 케이스의 판정은 false-PASS 다).

따라서 §16.3 deploy-backed 완료 기준의 순서를 따른다:
**cycle-finalize(머지) → 라이브 재배포(마이그레이션 포함) → POST-DEPLOY 시각검증**.
그 Run 은 이 fragment 에 `Environment: Windows-browser` 항으로 **추가 기록**한다.

### POST-DEPLOY 확인 대상 (PB-0008)

1. 메타데이터 > 용어 사전 > 등록 폼에 「통용 범위」 select 노출.
   제품 scope 선택 시 기본값 `이 제품 전용`, 공용 scope 선택 시 `전역(모든 제품)`.
2. 제품 scope 목록에 전역(`common`) 용어가 `전역 상속 · 여기서 편집 불가` 배지로 함께 표시되고,
   그 행을 클릭해도 편집 폼이 열리지 않는다(삭제·유사어 버튼도 없다).
3. 검토 큐 상태 필터에 `일반 용어로 제외됨` 선택지가 있고, 그 항목의 승급 버튼 라벨이
   `그래도 등록` 이다.
4. 관리 콘솔 시스템 > 설정 최하단 「현재 미적용 기능」 집계에 `용어사전 자율수집` ·
   `ENUM 코드사전 자율수집` 2항목이 사유와 함께 노출된다(연결된 AI 가 없을 때).

---

## Environment: Windows-browser — POST-DEPLOY 실측 (2026-09-01T12:56+09:00, 배포본 `40340f53`)

앞 절의 「배포 후 수행」 약속의 이행. `bin/win-browser.py`(relay, Chrome/151.0.7922.170) +
`session-login`(bootstrap_admin) 으로 라이브 `https://localhost/admin` 을 실제 Windows
브라우저에서 구동해 확인했다.

### 선행 — 마이그레이션 라이브 적용 (이 검증의 전제)

```
alembic_version = 0058_glossary_term_tier
kb_glossary.term_tier       varchar DEFAULT 'product'   (기존 732행 전건 backfill)
glossary_feedback.term_tier 존재
ck_glossary_feedback_status = pending|auto_promoted|promoted|rejected|skipped_general
인덱스 = ix_kb_glossary_tier · ix_glossary_feedback_tier · ix_kb_glossary_term_norm
```

⚠ 리비전이 **0058** 인 이유: 병렬 세션이 같은 날 `0057_redteam_review_source` 를 먼저 머지해
§13.1 감지-후-재번호를 적용했다(`down_revision = 0057_redteam_review_source`).

### 확인 결과 (전건 PASS)

| # | 확인 대상 | 실측 |
|---|---|---|
| 1 | 등록 폼 「통용 범위」 select | **노출**. 라벨 `통용 범위`, 선택지 `이 제품 전용` / `전역(모든 제품)` / `일반 DB 용어` |
| 1b | 기본값이 보고 있는 scope 를 따르는가 | 제품 scope(`product.gz_qa_g`) → `product` · 공용 scope(`common`) → `org` |
| 2 | 전역 상속 행 표시 | 제품 목록 239건 중 **7건이 `inherited`**, 배지 `전역 상속 · 여기서 편집 불가` |
| 2b | 상속 행이 편집 불가인가 | `role` 속성 **null**(버튼 아님) — 클릭이 편집 폼을 열지 않는다 |
| 3 | 검토 큐 상태 필터 | `pending / auto_promoted / promoted / rejected / **skipped_general(일반 용어로 제외됨)** / all` |
| 4 | API 응답 필드 | `term_tier` 가 목록·검토 큐 양쪽 항목에 존재 · `inherited_count=7` · `?status=skipped_general` 조회 200 |

부수 관측(무관 but 정합): 우측 패널에 `AI 일괄 자동완성은(는) 지금 실행할 수 없습니다 — 이
서비스는 서버 계정 AI 를 쓰지 않습니다…` 안내가 정상 노출(= `feature_blocked_message` 경로).

### 캡처

`artifacts/pb0008-glossary-term-tier/` (git 밖, AGENTS.md §2)
— `1-review-filter.png`(검토 큐 81건) · `2-inherited-badge.png`(전역 상속 배지) ·
`3-tier-select-form.png`(통용 범위 select).

### 배포 검증 체크리스트 (feature-0014 RUNBOOK §10)

- [1] web-a·web-b = `mysql-ai-web:40340f53`, soak 통과
- [2] 전 서비스 이미지 SHA 일치 (`agent:40340f53` × 4 · `web:40340f53` × 2)
- [1b] 대화 스모크 PASS (전환 모드 — 서버 LLM 차단 확인)
- [2b] surge 잔존 **0**
- [5] 엣지 무중단 실측 — `no upstreams available` **0건**
