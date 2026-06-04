# Playbooks

반복적인 작업 절차를 표준화한 문서 모음이다.
AI는 해당 작업 수행 시 Playbook의 Steps를 순서대로 따른다.

## 목록

| ID | 이름 | 설명 |
|----|------|------|
| PB-0001 | [new-feature-unit](PB-0001-new-feature-unit.md) | 새 기능 유닛 생성 |
| PB-0002 | [add-shared-module](PB-0002-add-shared-module.md) | shared/ 공통 모듈 추가 |
| PB-0003 | [feature-completion](PB-0003-feature-completion.md) | 기능 완료 및 동기화 |
| PB-0004 | [hotfix](PB-0004-hotfix.md) | 긴급 수정 절차 |
| PB-0005 | [dependency-update](PB-0005-dependency-update.md) | 외부 의존성 업데이트 |
| PB-0006 | [template-migration](PB-0006-template-migration.md) | 공용 템플릿 버전 업 마이그레이션 |
| PB-0008 | [windows-browser-verification](PB-0008-windows-browser-verification.md) | AI 가 실제 Windows 브라우저를 CDP 자동 구동하여 웹/UI 검증 |

## 규칙
- Playbook은 참조 문서이며, AGENTS.md의 우선순위에서 기능 문서와 동일 수준이다.
- 새 Playbook 추가 시 프로젝트 수준 `DECISIONS.md`에 ADR로 기록한다.
- Playbook ID는 `PB-NNNN` 형식으로 순차 부여한다.
