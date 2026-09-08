---
run_at: 2026-09-08T11:28:42+09:00
session: ai/codex/feature-0043-bridge-token-env
scope: DQA 클라이언트 기준 갱신 실패 안내 및 이벤트 회귀
verdict: PASS (배포 전 후보, 라이브 배포 후 별도 확인)
---

### Run — Environment: Windows-browser (실제 Windows Chrome, 후보 자산 주입)
- PB-0008 드라이버의 기존 인증된 검증 프로필에서 별도 탭을 사용했다.
- 후보 connect-modal.js 응답만 주입하고 실제 모듈의 openConnectModal/_status를 호출했다.
  재실행 실패 상태는 테스트로 주입했으며 실제 앱 업데이트 실패를 발생시킨 것은 아니다.
- 화면 문구: DQA 앱을 다시 실행했지만 업데이트가 적용되지 않았습니다.
  알림 영역의 DQA 아이콘을 우클릭해 [업데이트 확인]을 선택해 주세요.
- 텍스트 가시성 true, 1단계 명령 부재, 줄 잘림·overflow 없음. 탭 닫아 테스트 주입 제거.
- Screenshot: artifacts/bridge-token-env-20260908/windows-notice-candidate.png
- 실제 메뉴 근거: feature-0046 src/client/gui.py UPDATE_MENU_LABEL = 업데이트 확인.

### 회귀
- 관련 4파일 집중 검증: 229 PASS (토큰 신규 11건 포함).
- verify_connect_modal_autoclose.mjs: 40/40 PASS.
- verify_launch_runner_behavior.mjs: 18/18 PASS.
- ruff 변경 Python 파일 PASS. UI DOM/스타일/권한 변경 없음.
- UX/design panel PASS. 토큰 전달 실 Windows 검증은 feature-0043 원장 참조.

### 전체 회귀 확정 (2026-09-08 11:35 KST)

- 브리지·클라이언트 전체: **2151 passed, 1 skipped** (198.67s).
- 문구 변경에 따른 기존 6개 단정도 실제 앱 업데이트 안내로 갱신하고 복구 메뉴·터미널 안내 부재를 확인했다.
- 원본: `/tmp/dqa-token-env-regression.log`. Windows 전용 skip은 실제 Windows 경계 실측과 구분한다.
- 동시에 main에 착륙한 #1606 자동 갱신/클라이언트 감독 변경과 병합 후 영향 범위를 재검증한다.
- 최종 병합·배포·설치본 상태 및 실제 첨부 읽기 증거는 PR 설명에 후속 기록한다.

### main 통합 확인

- main `0f58a1de` (#1606)와 병합했다. 자동 복구·감독 구현은 유지하고 양 작업의 FUNCTION/TASK 항목을 보존했다.
- 겹친 안내는 실제 트레이 메뉴 이름을 명시한 문구로 통합하고 이벤트 단위 테스트는 동작을 보존했다.
- 병합 후 영향 8파일 **290 passed (30.83s)**: 토큰 전달·자기갱신·동시 프로세스·감독·UI 복구·모델 선택.
- 양쪽 AGENTS SHA-256 동일, 정책 변경 없음.
