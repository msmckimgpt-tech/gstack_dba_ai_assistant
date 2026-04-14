---
doc_type: TEST
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Policy
- **모든 Web UI 검증은 실제 브라우저 기반으로 수행해야 한다.**
- curl, httpie 등 CLI 기반 API 요청은 백엔드 API 단위 테스트로만 인정한다.
- 프론트엔드 기능(로그인, 테마 전환, 키워드 관리, 대화 흐름 등)은 반드시 브라우저 자동화(feature-0004-browser-automation) 또는 실제 브라우저 조작을 통해 검증한다.
- 브라우저 자동화 API 엔드포인트: `http://localhost:18081` (내부: `http://browser:8000`)
- 스크린샷을 `/shared/` 경로에 저장하여 검증 증빙을 남긴다.

## 2. Test Scope
- Web UI 앱이 새 feature 경로에서 이미지에 포함되는지 확인
- `make web`가 동일 인터페이스로 동작하는지 확인
- 로그인/로그아웃 흐름이 브라우저에서 정상 동작하는지 확인
- 라이트/다크 테마 전환이 동작하는지 확인
- 키워드 CRUD가 UI에서 동작하는지 확인

## 3. Test Cases

### 구조 검증
- TEST-0001: agent Dockerfile이 `feature-0003-agent-web-ui/src`를 `/app/web`로 복사한다
- TEST-0002: `docker-compose.yml`의 `web` 서비스가 새 이미지 경로를 사용한다

### 브라우저 기반 기능 검증
- TEST-0003: 로그인 폼에 사용자명, 표시이름, 역할, 목적을 입력하고 "시작하기" 클릭 시 메인 워크스페이스로 진입한다
- TEST-0004: 로그인 후 상단 바에 사용자 배지(이름, 역할)가 표시된다
- TEST-0005: 로그아웃 버튼 클릭 시 로그인 화면으로 복귀한다
- TEST-0006: 테마 토글 버튼 클릭 시 라이트/다크 테마가 전환된다
- TEST-0007: 키워드 등록 폼에서 키워드 추가 후 목록에 표시된다
- TEST-0008: 키워드 삭제 버튼 클릭 시 목록에서 제거된다

## 4. Test Run History
- 2026-03-26: 구조 검증 기준만 정의함
- 2026-04-06: 로그인 버그 수정 후 브라우저 자동화로 TEST-0003, TEST-0004 통과 확인 (스크린샷: login_test_03_after_click.png)
