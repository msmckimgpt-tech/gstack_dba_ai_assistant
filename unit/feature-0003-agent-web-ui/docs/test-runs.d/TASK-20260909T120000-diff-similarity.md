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
Evidence: `/tmp/dqa-diff-tests.log` — Python 91 passed (3.73s); `/tmp/dqa-diff-node.log` — Node diff 128 PASS; `/tmp/dqa-diff-tree-node.log` — 계보 UI 24 PASS; codenav-lint 및 신규 Python ruff PASS.
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

전체 pytest 진행 중: `/tmp/dqa-diff-full-tests.log`. 원격 동기화 및 web-only 배포 결과는 후속 갱신한다.
