---
doc_type: CONVENTIONS
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
---

# Conventions

## 1. 네이밍
- 기능 폴더: `feature-<nnnn>-<purpose>`
- 문서 파일명: 대문자 고정
- 테스트 파일명: 대상 코드와 대응되도록 유지
- 산출물 폴더명: 목적 중심으로 명확하게 작성
- 런타임 산출물은 이 문서 기준 `../../artifacts/<purpose>` 패턴을 사용

## 2. 문서 작성 규칙
- 현재 상태 문서는 최신 상태만 유지한다.
- 이력 문서는 append-only를 기본으로 한다.
- 불확실한 내용은 단정형 문장으로 쓰지 않는다.
- 각 문서 상단에는 메타데이터 블록을 둔다.

## 3. 추적성 규칙
문서와 코드에 아래 식별자 사용을 권장한다.
- `REQ-XXXX`
- `AC-XXXX`
- `CHG-YYYYMMDD-XXXX`
- `REV-YYYYMMDD-XXXX`
- `ADR-XXXX`
- `TEST-XXXX`

## 4. 커밋 및 변경 단위
- 하나의 의미 있는 작업 단위 안에서 코드와 문서를 함께 갱신한다.
- 서로 무관한 변경은 가능한 한 분리한다.
- 대규모 구조 변경은 결정 문서와 함께 진행한다.

## 4.1 경로 규칙
- Git-tracked 문서와 설정에는 호스트 파일시스템 절대경로를 사용하지 않는다.
- 문서의 파일 참조는 현재 문서 위치 기준 상대경로를 사용한다.
- Docker 컨테이너 내부 경로(`/app`, `/shared`, `/certs`, `/etc/mysql/...`, `/var/lib/mysql`)는 절대경로를 유지한다.

## 5. 주석 및 보고
- 코드 주석은 구현 의도와 제약을 설명하는 데 사용한다.
- 문서는 사람과 다른 AI가 빠르게 맥락을 파악하도록 작성한다.
- `REPORT.md`는 간결하고 실행 가능한 정보 위주로 유지한다.
- 검증 범위가 제한적이면 `REPORT.md`와 `TEST.md`에 명시한다.

## 6. 테스트 프레임워크 및 실행
- 프로젝트의 테스트 실행 방법은 `PROJECT.md` §8에서 정의한다.
- 각 기능의 `tests/` 폴더에는 실행 가능한 테스트 코드를 둔다.
- 수동 테스트 시나리오는 `TEST.md`에 기록한다.
- 테스트 결과는 `TEST.md` §3 Test Run History에 append-only로 기록한다.
- 구조/기동 검증과 도메인 검증은 별도 항목으로 구분한다.

## 7. AI 에이전트 매핑 규칙
- 이 저장소의 정본 정책 파일은 `../AGENTS.md`이다.
- Claude Code: `../CLAUDE.md` → `../AGENTS.md` 참조
- 다른 도구용 호환 파일이 필요하면 AGENTS.md 참조 파일로만 둔다.

## 8. 용어집

| 용어 | 정의 |
|------|------|
| unit | 기능 단위 작업 폴더 (`../unit/<feature-id>/`) |
| feature-id | 기능 폴더의 고유 식별자 |
| source of truth | 특정 사실의 정본 문서 |
| rewrite | 문서 전체를 최신 상태로 덮어쓰는 수정 정책 |
| append-only | 기존 항목을 수정/삭제하지 않고 새 항목만 추가하는 수정 정책 |
| runtime artifacts | 로그, 세션, MySQL 데이터, 인증서처럼 `../../artifacts`에 저장되는 파일 |
| execution root | `docker-compose.yml`, `Makefile`, `.env`가 위치한 저장소 실행 루트 |
