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
Evidence: `/root/download/docker/mysql_ai_delegated_dev/artifacts/diff-similarity-20260909/logs/dqa-diff-tests.log` — Python 90 passed (3.73s), 별도 API 제한 전달1 passed (0.51s); `/root/download/docker/mysql_ai_delegated_dev/artifacts/diff-similarity-20260909/logs/dqa-diff-node.log` — Node diff 128 PASS; `/root/download/docker/mysql_ai_delegated_dev/artifacts/diff-similarity-20260909/logs/dqa-diff-tree-node.log` — 계보 UI 24 PASS; codenav-lint 및 신규 Python ruff PASS.
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

최초 전체 pytest: **8,358 passed / 16 failed / 40 skipped**, 564.16s (`/root/download/docker/mysql_ai_delegated_dev/artifacts/diff-similarity-20260909/logs/dqa-diff-full-tests.log`). 실패를 숨기거나 전체 PASS로 합산하지 않는다.

- 환경 13건: 호스트 psycopg 부재6·컨테이너 전용 web.app import7. 의존성을 가진 제품 이미지에 현재 소스를 복사하고 `--network none` 및 테스트 DB 격리 변수로 재검증: **45 passed** (`/root/download/docker/mysql_ai_delegated_dev/artifacts/diff-similarity-20260909/logs/dqa-diff-container-tests.log`). 라이브 컨테이너/DB 접속 없음.
- 기존 테스트 3건: main 대조에서 route·도구 목록2건은 이미 선행 수정되어 PASS. 최신 main merge로 수용했다. side-panel 하네스1건은 누락 주변 의존 stub을 추가하고 열림 전제 검사를 보강해 **Node69 PASS + pytest 단건 PASS**.
- 추가 API 정렬 제한 전달 단건 **1 PASS** (`/root/download/docker/mysql_ai_delegated_dev/artifacts/diff-similarity-20260909/logs/dqa-diff-api-limit.log`). 집중 원래90건과 별도 실행이다.
- 환경 재검증 중 Docker snap CLI가 호스트 `/tmp` 파일을 읽지 못해 task artifacts 경로로 staging을 옮겼다. 부분 복사 때 root conftest가 요구한 bridge source 부재를 보완한 뒤 성공했다.
- 전체 suite를 같은 환경에서 다시 실행한 것은 아니다. 실패 원인을 각각 해소·재검증한 근거를 위와 같이 구분한다. 원격 동기화 및 web-only 배포 결과는 아래 배포본 대조에 기록한다.

최신 main(a8abac5f) 통합 후 diff/계보/API·route golden·사이드패널·bridge tool 기대 **94 passed**, 11.86s (`/root/download/docker/mysql_ai_delegated_dev/artifacts/diff-similarity-20260909/logs/dqa-diff-final-tests.log`).


## 배포본 대조

- 구현 PR [#1646](https://github.com/msmckimgpt-tech/gstack_dba_ai_assistant/pull/1646) main 반영: `46b70e26`.
- `repo-web-a-1`·`repo-web-b-1`의 `GIT_COMMIT=46b70e26` 일치. 정렬 helper·builder·endpoint·JS 4개 파일은 저장소와 모두 일치(JS는 빌드용 자산 버전 문자열만 정규화하여 비교).
- 두 컨테이너에서 순수 정렬 helper를 불러 fixture를 계산: DQA Shell에서 표시한 26행 정렬과 정확히 일치, 좌우 원문 행 소실·중복 없음, 계산 제한 없음. 앱 시작/DB/API 접속 없이 확인했다.
- 근거: `/root/download/docker/mysql_ai_delegated_dev/artifacts/diff-similarity-20260909/deployed-result.json`, 재현 `verify-deployed.py`.
- `bash bin/deploy-web.sh --web-only` **exit 0**. 두 replica ready·90초 soak PASS. 진행 중 스트림/bridge 왕복은 양쪽0 확인 후 교체했고 web-b 대기1은 드레인으로 교대했다. 신규 마이그레이션0. Caddy 변경 없음. 로그: `artifacts/diff-similarity-20260909/logs/dqa-diff-deploy.log`(wrapper 기준).
- compose build 종료1은 snap metadata-file 오류였다. 기존 배포 스크립트가 실제 이미지 산출 및 GIT_COMMIT 일치를 확인하여 계속했고 최종 정상 종료했다. 이미지 `mysql-ai-web:46b70e26`, SHA256 `5f302efa724e5dcef29f565f66648592e67143e40d15fffd22a5ce35ec02f7c4`.
- Caddy HTTPS 실제 JS **200**, 자산 stamp `707243eb7376` 및 정규화 내용 일치. CA 검증 유지. 호스트 DNS 조회가 불가해 배포 스크립트와 동일한 `--resolve host:443:127.0.0.1`로 호스트 Caddy를 확인했다. 근거: 같은 artifacts의 `served-asset-result.json`, `served-attach-diff.js`.
- scope=web이므로 worker/gateway·대화 스모크 미수행. 위 배포본 확인은 설치 DQA의 실제 사용자 첨부/API 검증을 대신하지 않는다. 두 축을 전체 클라이언트 E2E PASS로 합산하지 않는다.
