---
doc_type: MODIFY
feature_id: feature-0044-qa-staging-pipeline
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260826-0001
- Date: 2026-08-26
- Related Requirement: REQ-20260826-qa-staging-pipeline
- Summary: unit 신규 개설 + 격리망 QA 머신 CI/CD 전 과정 설계 제안서 작성. 코드 변경 없음.
- Files:
  - `unit/feature-0044-qa-staging-pipeline/docs/FUNCTION.md` (신규 — 범위·계약·비범위·AC)
  - `unit/feature-0044-qa-staging-pipeline/docs/CICD_DESIGN.md` (신규 — 전 과정 절차·근거·트레이드오프)
  - `unit/feature-0044-qa-staging-pipeline/docs/ANCHOR.md` (신규 — 외부 관점·대안 4안·사용 시나리오)
  - `unit/feature-0044-qa-staging-pipeline/docs/{TASK,REPORT,REVIEW,TEST,MODIFY,DECISIONS}.md` (신규)
  - `docs/STATUS.md` (인덱스 등록 — AGENTS.md §4)
  - `wiki/Features/feature-0044-qa-staging-pipeline.md` · `wiki/Features/_Index.md` · `wiki/Log.md`
- Impact: 실행 표면 변경 0. 배포·런타임 무영향. 후속 구현 cycle 의 설계 근거가 된다.
- Rollback Notes: 문서 전용 변경이므로 되돌리기는 커밋 revert 로 충분하다. 런타임 상태·데이터
  영향이 없어 롤백 절차가 필요 없다.

## CHG-20260827-0001
- Date: 2026-08-27
- Related Requirement: REQ-20260826-qa-staging-pipeline
- Summary: 사용자 결정 수집(AskUserQuestion 3라운드 11문항) 결과로 설계를 rev.2 로 전면 개정.
  코드 변경 없음. **rev.1 의 두 전제가 뒤집혔다** — ① 사내 GitLab·컨테이너 레지스트리가
  존재하지 않고(SVN 을 산출물 저장소로 구축 예정) ② 라이브도 QA 와 함께 전용 호스트로 분리한다.
- Files:
  - `docs/CICD_DESIGN.md` (전면 개정 — GitLab CI 5스테이지 → `release-build.sh` 1개,
    Registry pull → `docker save` tar 릴레이 + sha256/image_id 2중 대조, git 태그 승격 →
    `promoted/current.json`, 라이브 분리 절차 §7-1 신설, **권장 스펙 §6 신설**)
  - `docs/FUNCTION.md` (전제 10축 표 · In Scope P0-A~G 재편 · AC 7→10항)
  - `docs/TASK.md` (Phase 재편 7단계 · Blocked 4건 · Requested Scope 7항)
  - `docs/DECISIONS.md` (ADR 2건 append — registry-free 릴레이 / 라이브 호스트 분리)
  - `docs/ANCHOR.md` (§1~§3 갱신 — 전제 변경 반영)
  - `docs/REPORT.md` · `docs/REVIEW.md` · `docs/TEST.md` 갱신
- Impact: 실행 표면 변경 0. 배포·런타임 무영향. 후속 구현 cycle 의 설계 근거가 rev.1 → rev.2 로 대체된다.
- Rollback Notes: 문서 전용. revert 로 충분하며 런타임 영향이 없다. 다만 rev.1 로 되돌리면
  존재하지 않는 인프라(GitLab CI · Registry)를 전제한 설계로 회귀하므로 실익이 없다.
