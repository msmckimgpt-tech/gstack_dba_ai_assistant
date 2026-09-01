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
