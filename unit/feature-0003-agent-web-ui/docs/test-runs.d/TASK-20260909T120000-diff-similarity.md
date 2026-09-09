---
run_at: 2026-09-09T03:06:28.577234+00:00
session: codex:root:01a08411-5b5d-7691-890c-509a2b60ed6d
scope: TASK-20260909T120000-diff-similarity
verdict: PASS
---

# SQL 유사 diff 검증

Environment: CLI
Result: PASS
Scenario: 정렬·원문 보존·patch 복원·인가/계보 회귀
Evidence: `/tmp/dqa-diff-tests.log` — Python 90 passed (3.73s), 별도 API 제한 전달1 passed (0.51s); `/tmp/dqa-diff-node.log` — Node diff 128 PASS; `/tmp/dqa-diff-tree-node.log` — 계보 UI 24 PASS; codenav-lint 및 신규 Python ruff PASS.
Command: `PYTHONPATH=unit/feature-0002-agent-core/src:unit/feature-0003-agent-web-ui/src:. python3 -m pytest -q unit/feature-0003-agent-web-ui/tests/test_attachment_diff_similarity.py unit/feature-0003-agent-web-ui/tests/test_attachment_version_diff.py unit/feature-0003-agent-web-ui/tests/test_attach_version_branching.py --tb=short --disable-warnings -o addopts=''`

Environment: DQA-client
Result: PASS
Build: 격리 제품 Shell + 현 worktree Python builder/JS/CSS, WebView2 152.0.4191.66; 파일별 SHA256은 result.json.
Scenario: 재현 SQL fixture의 좌우·단일열·전체맥락·SQL 색·계산 제한 안내
Evidence: `/root/download/docker/mysql_ai_delegated_dev/artifacts/diff-similarity-20260909/native-final-current/result.json` — 21/21. 같은 디렉터리 `split.png`, `unified.png`, `alignment-limit.png` 실제 WebView2 캡처. 신규 `tests/windows/verify_diff_similarity.py`로 재현.
Boundary: 서비스 응답 envelope는 fixture이고 Python 계산·JS/CSS·native Shell은 제품 코드다. 초기 제한 안내 검사 1건이 script text 포함으로 오탐되어 대상 요소 검사로 수정 후 통과했다. 사용자 설치본/프로파일 무접촉.

Environment: DQA-client
Result: NOT-RUN
Build: 설치 DQAConnect.exe PID 29732 / 소유 WebView2 PID 38028 발견
Scenario: 실제 사용자 첨부·계보 간 API 왕복
Reason: 설치본 WebView2 프로세스에 remote-debugging-port가 없으며 사용자 앱 종료/재설치 없이 연결할 지원 자동화 경로를 확보하지 못함.
Alternative: 위 격리 제품 Shell/WebView2에서 정렬 21건 실측; endpoint fake 기반 인가·계보 회귀.
Next: 배포 후 사용 중 DQA에서 같은 파일 두 버전을 다시 비교하는 실사용 확인. 로컬 브리지/로그인은 변경 범위가 아니다.

## 전체 회귀 및 배포

최초 전체 pytest: **8,358 passed / 16 failed / 40 skipped**, 564.16s (`/tmp/dqa-diff-full-tests.log`). 실패를 숨기거나 전체 PASS로 합산하지 않는다.

- 환경 13건: 호스트 psycopg 부재6·컨테이너 전용 web.app import7. 의존성을 가진 제품 이미지에 현재 소스를 복사하고 `--network none` 및 테스트 DB 격리 변수로 재검증: **45 passed** (`/tmp/dqa-diff-container-tests.log`). 라이브 컨테이너/DB 접속 없음.
- 기존 테스트 3건: main 대조에서 route·도구 목록2건은 이미 선행 수정되어 PASS. 최신 main merge로 수용했다. side-panel 하네스1건은 누락 주변 의존 stub을 추가하고 열림 전제 검사를 보강해 **Node69 PASS + pytest 단건 PASS**.
- 추가 API 정렬 제한 전달 단건 **1 PASS** (`/tmp/dqa-diff-api-limit.log`). 집중 원래90건과 별도 실행이다.
- 환경 재검증 중 Docker snap CLI가 호스트 `/tmp` 파일을 읽지 못해 task artifacts 경로로 staging을 옮겼다. 부분 복사 때 root conftest가 요구한 bridge source 부재를 보완한 뒤 성공했다.
- 전체 suite를 같은 환경에서 다시 실행한 것은 아니다. 실패 원인을 각각 해소·재검증한 근거를 위와 같이 구분한다. 원격 동기화 및 web-only 배포 결과는 후속 기록한다.

최신 main(a8abac5f) 통합 후 diff/계보/API·route golden·사이드패널·bridge tool 기대 **94 passed**, 11.86s (`/tmp/dqa-diff-final-tests.log`).
