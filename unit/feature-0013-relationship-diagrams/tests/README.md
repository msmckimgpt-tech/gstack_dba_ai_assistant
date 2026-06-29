# Tests

## 개요
이 디렉토리는 기능의 테스트 코드와 테스트 유틸리티를 포함한다.

## 구조
```
tests/
├── README.md               # 이 문서 (테스트 실행 방법 설명)
├── (자동 테스트 코드)       # 실행 가능한 테스트 파일
└── mock-bin/               # 목 바이너리 (선택, 외부 의존성 시뮬레이션)
```

## 테스트 실행 방법
<!-- 이 기능의 테스트 실행 명령어를 기입한다 -->
```bash
# 예시 (Python pytest)
pytest tests/

# 예시 (Bash smoke test)
bash tests/run_smoke_tests.sh

# 예시 (Node.js)
npm test
```

## 테스트 유형
- **자동 테스트**: 이 디렉토리의 실행 가능한 테스트 코드
- **수동 테스트**: `../docs/TEST.md`에 기록된 수동 시나리오
- **통합 테스트**: `/repo/tests/integration/`에 기능 간 통합 테스트

## 테스트 결과 기록
테스트 실행 결과는 `../docs/TEST.md` §3 Test Run History에 append-only로 기록한다.

## 참고
- 테스트 정의 및 결과: `../docs/TEST.md`
- 기능 명세: `../docs/FUNCTION.md`
- 프로젝트 테스트 정책: `/repo/docs/CONVENTIONS.md` §6
