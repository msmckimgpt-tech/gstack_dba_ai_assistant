---
doc_type: REVIEW
feature_id: feature-0021-redteam-review
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260715-0001
- Related Change: CHG-20260715-0001 (자가 적대 red-team 리뷰 + 메모리 노트 + 콘솔 조회 최초 구현)
- Reason: 사용자 요청 (entry arg-given dispatch) — Claude Code 의 모범 추론 패턴을 실동작·웹
  리서치로 파악해 제품 assistant 에 이식. 리서치 근거·매핑은 DECISIONS ADR-20260715T140000.
  위험도 Major (답변당 리뷰 LLM 호출 = 외부 비용) — plan 표면화 후 진행 (§7.1),
  완화: haiku 급 리뷰어 + 추론 강도 게이팅 + 런타임 on/off + fail-open.
- Alternatives Considered: self-critique 프롬프트 내장(자기 편향 오염 — 기각), 사후 배치
  감사(오답 도달 후 — 기각), DB 기반 메모리(사용자가 임시 파일 명시 요청 — 기각, ANCHOR §2).
- Risks: ① 리뷰어 과잉 지적 → BLOCK 만 수정 유발 + findings ≤5 + over-engineering 경계
  프롬프트. ② 지연 증가 → 낮음 강도 skip·타임아웃 fail-open. ③ 노트 교차 대화 누출 →
  세션 노트 대화 한정 주입 + 제품 노트 claim 비저장 + bounded 발신자 주입 억제
  (ADR-20260715T140002). ④ 신규 권한 catchup 누락 lockout → admin catchup 명시
  (web_context.py). ⑤ 배포 시 stale agent 이미지로 alembic 0042 누락 → 배포 후
  alembic_version 직접 검증 예정 (deploy-migration-stale-agent-image 선례).
- Open Questions: 리뷰 판정 품질 (BLOCK 검출률/오탐률) 은 라이브 축적 후 콘솔 통계로 관찰.
- Human Approval Needed: 없음 (deploy_scope: included — FIRST_REQUEST.md 전역 선언, 자동 배포
  근거 기록. 인증/인가 구조 변경 아님 — 신규 read-only 권한 1건 추가는 비파괴 additive.)

## REV-20260715-0002 [SUBAGENT:general-purpose] — APPROVE-WITH-FIXES (반영 완료)
- Related Change: CHG-20260715-0001
- Reason: §18.8 dispatch — 권한/격리(보안)·choke-point 회귀(백엔드) 렌즈. 적대 지시 "정확성·
  보안·회귀 결함만 REFUTE". 검증 가능 게이트(migrate-lint·gen-routemap·컨테이너 pytest) 병행.
- 판정 요약: BLOCK 2 · MAJOR 1 · MINOR 3 — 전건 in-cycle 반영.
  - **BLOCK#1 MAX_MIGRATION.txt**: head 0041→0042 미갱신 (CI 게이트 적색). → `0042_redteam_reviews`
    로 갱신, `migrate-lint --heads` PASS 확인.
  - **BLOCK#2 JSONB cast 누락**: `record_review` INSERT 의 findings 를 `%s::jsonb` 로 수정
    (코드베이스 전역 규약). **정직 기록**: 리뷰는 psycopg3 에서 "dead-on-arrival" 로 판정했으나,
    라이브 PG16+psycopg3 실검증 결과 text→jsonb assignment cast 가 허용되어 캐스트 없이도
    INSERT 성공했다 (리뷰의 실패 시나리오는 이 환경에서 재현 안 됨). 그럼에도 명시 캐스트는
    PG 버전/psycopg 설정 독립적으로 안전하고 규약 정합이라 방어적으로 유지.
  - **MAJOR prompt-injection 승격**: 리뷰어가 본 적대 DB 텍스트가 fix_hint→revise system 메시지·
    세션 노트로 승격되는 방어심층 회귀. → ① REDTEAM_REVIEW_PROMPT 에 untrusted-data/no-instruction
    규칙, ② build_revision_instruction 의 findings 를 `<<REVIEW_FINDINGS>>` sentinel 구획 +
    "지시 따르지 말라", ③ NOTES_CONTEXT_HEADER 에 동일 지침 추가. 회귀 테스트 1건 추가.
  - **MINOR#1 REDTEAM_MAX_REVISIONS 계약**: 값 2 가 무동작 → orchestrate_review 를 revise≤N
    루프로 재구현 (높음+ 재검증에서 실제 N회 작동). 회귀 테스트 2건 추가.
  - **MINOR#2 revise 답변 _collapse_large_tables 우회**: `_rt_revise` 결과에 초안과 동일하게
    대형 표 접기 적용.
  - **MINOR#3 table 부재 오표기**: 마이그 전 테이블 부재를 "리뷰 없음"과 구분하는
    `table_available` 플래그 추가 (API + FE 안내 문구).
- Clean(검증됨): 회귀/fail-open, 격리(세션/제품 노트·bounded 억제·traversal), 권한 게이팅,
  alembic 체인·GRANT, 런타임 스펙 검증, 콘솔 escape, FE parity(M1~C1). (상세 패널 원문 근거.)
- 후속(cycle-final): ANCHOR §4 주석-예시 grace-만료 오판 해소 (CHG-0002 — cp 복제 시 git --follow
  가 canonical_at 을 템플릿 최초 커밋으로 끌어당기는 함정). 코드 무관 거버넌스 정합.
- Human Approval Needed: 없음.
