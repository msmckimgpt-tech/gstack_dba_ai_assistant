---
doc_type: FUNCTION
feature_id: feature-0004-browser-automation
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
Playwright 기반 브라우저 자동화 서비스와 CLI 제어 스크립트를 관리한다.

## 2. Goal
- REQ-0001: 브라우저 서비스를 기능 단위 구조로 이관한다.
- REQ-0002: `make browser-*` 명령을 새 경로에서 그대로 유지한다.

## 3. In Scope
- `src/app.py`
- `src/ctl.py`
- `src/requirements.txt`
- 브라우저 이미지 Dockerfile

## 4. Out of Scope
- Web UI 비즈니스 로직
- Windows LAN 프록시
- 엄격한 브라우저 업무 시나리오

## 5. Inputs
- `BROWSER_*` 환경값
- 루트 Makefile의 `browser-*` 명령

## 6. Outputs
- 브라우저 HTTP 제어 API
- 세션 기반 자동화 동작
- 스크린샷 파일

## 7. Main Flow
1. browser 서비스가 Playwright를 기동한다.
2. `ctl.py`가 HTTP API를 통해 세션을 제어한다.
3. 스크린샷과 결과 파일을 `/shared/out/browser`에 저장한다.

## 8. Edge Cases
- 브라우저 바이너리 기동 실패
- 세션 누락
- 페이지 타임아웃

## 9. Error Handling
- 세션 미존재는 404로 반환한다.
- 타임아웃은 408로 처리한다.

## 10. Dependencies
### 내부 기능 의존성
- feature-0001-platform-runtime

### 외부 의존성
- Playwright
- FastAPI

### shared 모듈 의존성
- 없음

## 11. Acceptance Criteria
- AC-0001: 브라우저 서비스 코드가 feature 경로로 이관되어 있다.
- AC-0002: 브라우저 Dockerfile이 새 구조 기준으로 빌드된다.
- AC-0003: 루트 `browser-*` 인터페이스가 유지된다.

## 12. Observability
- 스크린샷: `../../../../artifacts/shared/out/browser`
- 로그: `docker compose logs browser`

## 13. Pre-approved Changes
- 비파괴적 경로 재배치와 Docker build 경로 수정
