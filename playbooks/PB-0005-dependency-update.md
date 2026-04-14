---
playbook_id: PB-0005
name: dependency-update
description: 외부 의존성 업데이트 (보안 패치·라이브러리 bump)
trigger: manual
scope: project
---

# Playbook: 의존성 업데이트

외부 패키지·컨테이너 이미지·SDK 버전을 올리는 절차. 보안 패치, 호환성 유지, 성능 개선이 주된 동기다. 기능 추가가 아니므로 feature 단위 TASK 큐가 아니라 **프로젝트 단위**로 관리한다.

## Prerequisites
- 업데이트 대상 목록이 확정되었다 (단일 패키지 또는 그룹).
- 변경 범위가 Minor 이상(호환성 깨짐 가능성 있음)이면 `DECISIONS.md`에 ADR 초안을 준비한다 (AGENTS.md §11.3 승인 등급 참조).
- `.env` / `.env.example` 에 의존성 버전 고정 키가 있다면 함께 갱신 대상에 포함한다.

## Steps

1. `chore/dep-<package>-<version>` 브랜치를 main에서 생성한다.
2. 현재 버전 → 목표 버전의 **changelog / release notes**를 읽고 breaking change 여부를 판단한다.
   - Major 버전 bump인 경우: ADR 필수. 사람 승인 대기.
   - Minor / Patch: 자율 진행 가능(단, 보안 등급 변경은 Critical로 취급).
3. 의존성 파일을 수정한다.
   - Python: `requirements.txt` / `pyproject.toml`
   - Node: `package.json` / `package-lock.json`
   - Container: `Dockerfile`의 `FROM` / `apt-get install` 버전
   - SDK: `AGENTS.md`·`CLAUDE.md`의 모델명 갱신 필요 여부 확인
4. 영향 범위를 확인한다.
   - Grep으로 해당 패키지의 import/호출 지점을 나열.
   - API 시그니처 변경 있으면 호출부 수정.
5. 빌드·테스트를 실행한다.
   - 컨테이너 기반 프로젝트: `make worker-up` / `make build` 재실행.
   - 통합 테스트: `tests/integration/`.
6. 결과 기록.
   - `/repo/docs/MODIFY.md` (또는 `CHANGELOG.md`)에 "deps: <pkg> a.b.c → x.y.z" 이력.
   - Breaking change 있었으면 `/repo/docs/LEARNINGS.md`에 `quirk` 또는 `pattern`으로 append.
   - Major bump는 `/repo/docs/DECISIONS.md`에 ADR로 확정.
7. `/repo/docs/CODEBASE_MAP.md` §5 External Interfaces에 버전 정보가 있으면 갱신한다.
8. Git 커밋.
   ```
   chore(deps): bump <package> a.b.c → x.y.z

   - <파일>: 버전 지정 변경
   - <영향 받은 호출부>: 시그니처 대응
   ```
9. AGENTS.md §16.3 Git 동기화 절차를 수행한다 (PB-0003과 동일).

## Validation
- [ ] 대상 패키지 버전이 실제로 바뀌었다 (lock 파일 포함)
- [ ] 빌드가 성공한다
- [ ] 관련 자동 테스트가 통과한다
- [ ] Breaking change가 있었다면 호출부 수정이 반영되었다
- [ ] MODIFY.md / LEARNINGS.md / (Major의 경우) DECISIONS.md에 기록되었다
- [ ] CODEBASE_MAP.md §5가 최신 버전을 반영한다 (해당되는 경우)
- [ ] 커밋 메시지가 `chore(deps):` prefix를 사용한다

## 주의 사항
- **보안 업데이트**: CVE 대응은 지연 없이 수행하되, 호환성 검증은 건너뛰지 않는다. 우회 수단이 있는 경우라도 **임시 mitigation은 LEARNINGS.md에 기록**하고 본 수정까지 추적한다.
- **트랜지티브 의존성**: 직접 의존성만 bump 했는데 간접 의존성이 깨지는 경우가 흔하다. lock 파일 diff를 반드시 커밋에 포함한다.
- **SDK 모델 버전**: Anthropic 등 LLM SDK 모델명은 AGENTS.md / CLAUDE.md / FIRST_REQUEST.md에 하드코딩되어 있을 수 있다. grep으로 일관성 확인.
