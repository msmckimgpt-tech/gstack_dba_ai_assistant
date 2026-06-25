---
playbook_id: PB-0006
name: template-migration
description: 공용 템플릿 버전 업 마이그레이션 절차
trigger: manual
scope: project
---

# Playbook: 템플릿 버전 업 마이그레이션

`ai_delegated_dev_template`이 새 버전(예: v3.0.0 → v3.1.0)으로 갱신되었을 때, 본 프로젝트에 **선택적으로** 반영하는 절차. 템플릿의 모든 변경이 모든 프로젝트에 적합하지는 않으므로, 변경 단위별 수용/기각 판단이 중요하다.

## Prerequisites
- `ai_delegated_dev_template/TEMPLATE_CHANGELOG.md`에서 신버전의 변경 목록과 마이그레이션 가이드를 확인했다.
- 현재 프로젝트의 `template_version` (각 feature `docs/AGENTS.md` frontmatter 또는 `/repo/docs/DECISIONS.md`의 최신 migration ADR)을 확인했다.
- 프로젝트 고유 커스터마이징 목록을 파악했다 (AGENTS.md의 프로젝트 전용 섹션, `.env` 특이 키, 추가 Makefile 타깃 등).

## Steps

1. project-level task issue를 만들거나 확인한 뒤 공개 브랜치 `issue/<issue-number>-<short-slug>`를 main에서 생성한다.
2. 신버전 TEMPLATE_CHANGELOG를 읽고 **수용/기각 매트릭스**를 작성한다.
   - 각 변경 항목에 대해: 본 프로젝트가 해당 기능을 필요로 하는가?
   - 기각하는 경우 이유를 `DECISIONS.md` ADR 초안에 기록.
3. **파일 추가** (신규 파일):
   - `.aiignore`, `docs/LEARNINGS.md`, `docs/CODEBASE_MAP.md`, `playbooks/PB-*` 등이 신버전에 새로 생겼다면 복사.
   - 복사 후 **프로젝트 도메인에 맞게 커스터마이징** (예: `.aiignore`에 프로젝트 artifacts 경로 추가).
4. **정책 파일 병합** (`AGENTS.md`):
   - 템플릿의 신규 섹션 구조를 기준으로 재정렬하되, **프로젝트 고유 섹션은 보존**한다.
   - 섹션 번호가 바뀌면 모든 교차 참조(CONTRIBUTING.md, README.md, FIRST_REQUEST.md, 각 feature 문서)를 grep으로 찾아 갱신.
   - 구 섹션 번호 → 신 섹션 번호 매핑을 마이그레이션 ADR에 기록.
5. **_template 갱신** (`unit/_template/docs/*.md`):
   - 신버전의 TASK.md / REPORT.md / AGENTS.md 구조 변경이 있다면 반영.
   - 기존 feature의 문서 구조는 **소급 변경하지 않는다** (done 상태 feature 보존).
   - 신규 feature가 새 구조를 자동으로 사용하도록 한다.
6. **불변 규칙 보강**:
   - `.gitignore`에 새 패턴(예: `artifacts/`의 세부 하위 경로)이 추가되었는지 확인.
   - `CONVENTIONS.md` §용어집에 새 용어가 있으면 머지.
7. **smoke 검증**:
   - `make help` / `make status` / 주요 빌드 타깃이 여전히 동작하는지 확인.
   - 깨진 교차 참조 grep: `grep -rn "§[0-9]" AGENTS.md docs/ *.md` 후 missing section 없음을 확인.
8. **마이그레이션 ADR 기록** (`/repo/docs/DECISIONS.md`): ADR ID 는 **timestamp+slug**
   `ADR-<YYYYMMDDTHHMMSS>-<slug>` (순번 `ADR-NNNN` fallback — AGENTS.md §6·§13.1,
   ADR-20260625T023049-spec-anchor-timestamp-id):
   ```
   ## ADR-<YYYYMMDDTHHMMSS>-template-migration-vX-Y-Z
   - Status: accepted
   - Date: YYYY-MM-DD
   - Context: 템플릿 vX.Y.Z로 개선되어 <요약>
   - Decision: 템플릿 vX.Y.Z 마이그레이션 적용. 수용 <N>개 / 기각 <M>개
   - Consequences:
     - <추가된 파일 목록>
     - 섹션 번호 이동: 구 §A → 신 §B
     - 기각 항목: <이유>
     - template_version: vX.Y.Z로 갱신
   ```
9. **LEARNINGS.md append**: 이번 마이그레이션에서 발견한 프로젝트 고유 이슈(예: 특정 섹션이 기존 커스터마이징과 충돌)를 `pattern` 또는 `quirk`로 기록.
10. Git 커밋.
    ```
    feat(project): 템플릿 vX.Y.Z 마이그레이션 — <요약> (#<issue-number>)
    ```
11. AGENTS.md §16.5 Git 동기화 절차 수행 (PB-0003과 동일).

## Validation
- [ ] 신규 파일이 프로젝트 도메인에 맞게 커스터마이징되어 복사되었다
- [ ] 기존 feature 문서는 소급 변경되지 않았다
- [ ] 섹션 번호 이동 시 교차 참조가 모두 업데이트되었다 (`grep -rn "§"`로 확인)
- [ ] 프로젝트 고유 섹션이 AGENTS.md 재구성 중 손실되지 않았다
- [ ] DECISIONS.md에 마이그레이션 ADR이 append 되었다
- [ ] LEARNINGS.md에 마이그레이션 과정에서 얻은 교훈이 기록되었다 (없으면 "추가 없음" 명시)
- [ ] 기각한 템플릿 변경 항목이 이유와 함께 ADR에 기록되었다
- [ ] smoke 테스트(`make help` 등)가 통과한다
- [ ] 커밋 메시지가 `type(scope): summary (#issue-number)` 규칙을 따른다

## 주의 사항
- **프로젝트 고유 섹션 보존이 최우선**: 템플릿의 일반 조항을 기계적으로 복사해서 프로젝트 고유 조항을 덮어쓰면 안 된다. 충돌 시 **프로젝트 고유 조항 우선**.
- **과거 feature의 문서 구조는 보존**: done 상태 feature의 TASK.md/REPORT.md를 신규 템플릿 구조로 소급 변환하지 않는다 (역사 왜곡 방지).
- **선택적 수용**: 템플릿의 모든 개선이 모든 프로젝트에 맞지는 않는다. 사용하지 않는 playbook 추가 등은 기각 가능.
- **병렬 작업 중이면 지연**: feature 작업이 활발한 시점에는 마이그레이션이 병합 충돌을 키운다. 각 feature가 STATUS=done/review로 수렴한 직후가 적기.
