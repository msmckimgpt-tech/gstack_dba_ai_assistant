---
run_at: 2026-09-01T12:40:00+09:00
session: ai/claude/metadata-term-scope
scope: feature-0002-agent-core (cross-cut feature-0003 · feature-0043)
verdict: PASS
---

# Run — 용어 통용범위(term_tier) 축 + 브리지 자율수집 복원

## Environment: CLI (pytest / 컨테이너 `make test`)

웹 UI 표면 변경 있음(`static/admin/metadata.js` 폼 필드·배지) → **PB-0008 Windows-browser
시각검증 필요**. 아래 `Environment: Windows-browser` 항 참조.

## 1. 단위·계약 테스트

| 대상 | 결과 |
|---|---|
| `make test` (컨테이너, 전 feature) | **PASS** rc=0 · ruff `All checks passed!` |
| `tests/test_glossary_term_tier.py` (신규 20건) | PASS |
| `tests/test_kb_glossary_enum.py` (계약 갱신 + 신규 2건) | PASS |
| `unit/feature-0003-agent-web-ui/tests/test_bridge_glossary_terms.py` (신규 14건) | PASS |
| worktree 전체 로컬 pytest | 4974 passed / 13 failed — 13건은 **main 과 동일한 선재 실패** (`test_scratch`·`test_share_redaction_invariant` 의 `/app` 경로 의존). 컨테이너에서는 전건 PASS. |

## 2. 뮤테이션 실증 (§16.7 G11-b — 「수정 전 코드에서 FAIL 함을 1회 실증」)

격리 사본(`scratchpad/mut`)에 **수정 전 동작 4종**을 주입하고 실행. 앵커 미발견 시 즉시 중단
하도록 해 「적용되지 않은 뮤턴트를 통과로 오인」하는 자기충족을 차단했고, `diff -q` 로 파일
반영을 확인했다.

| 뮤턴트 | 되돌린 것 | 결과 |
|---|---|---|
| M1 | 결정적 general 강등 제거(= 프롬프트만 고친 상태) | **KILL** — `test_reported_general_terms_are_demoted_even_when_llm_says_product` |
| M2 | general 미등록 가드 제거(= tier 축 도입 전) | **KILL** — `test_general_term_is_not_written_to_glossary_but_is_recorded` |
| M3 | 판정 이력 조회를 단일 scope 로 회귀 | 1차 **생존** → 테스트가 vacuous 임을 확인, scope 집합을 파라미터로 단언하도록 보강 후 **KILL** |
| M4 | 러너 `#GLOSSARY:` 파싱 제거 | **KILL** — 브리지 파싱 6건 |

## 3. 라이브 데이터 dry-run (읽기 전용 — 변경 없음)

라이브 `agent_kb.kb_glossary` 의 `source='auto'` 724행 스냅샷에 `glossary_tier_sweep.plan()`
적용:

- 범용 회수 대상 **69행** (lexicon 67 · sql-keyword 2), 9개 제품 scope 분포
- 중복 삭제 대상 **36행** — 전부 `same-scope-variant`
- 교차 제품 **28개 표면형** — 삭제 없음(보고 전용)
- 유지 **619행**

분류 정확도 표본 검사: 사용자 지적 3종(`복제 이벤트`·`Online DDL`·`시점 복구`) 전건 general.
제품 고유 용어 14종(`튜닝인덱스`·`인덱스 비중`·`SponsorCode`·`CharacterID`·`characterbounty`
·`TF_Raw_JSON`·`sp_InsertSteamBillingLog` 등) **오강등 0건**.

## 4. Environment: Windows-browser — 미수행(사유 명시)

`visual_verification_scope: always` 대상(웹 자산 변경). **이 cycle 에서는 수행하지 않았다** —
변경된 화면(메타데이터 > 용어사전의 통용범위 select·배지·전역 상속 행)은 **alembic 0057 이
라이브에 적용된 뒤**라야 실제 값이 렌더된다(컬럼 부재 시 목록 조회가 500). 배포 후
POST-DEPLOY 시각검증으로 수행하고 그 Run 을 이 fragment 에 추가한다.

확인 대상(배포 후):
1. 용어 등록 폼에 「통용 범위」 select 노출 · 제품 scope 기본값 `이 제품 전용` / 공용 scope 기본값 `전역(모든 제품)`
2. 제품 scope 목록에 전역 상속 행이 `전역 상속 · 여기서 편집 불가` 배지로 표시되고 클릭이 편집을 열지 않음
3. 검토 큐 상태 필터에 `일반 용어로 제외됨` 선택지 노출 · 그 항목의 버튼이 `그래도 등록`
