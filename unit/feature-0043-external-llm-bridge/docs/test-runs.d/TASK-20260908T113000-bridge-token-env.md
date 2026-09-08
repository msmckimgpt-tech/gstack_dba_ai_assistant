---
run_at: 2026-09-08T11:26:45+09:00
session: ai/codex/feature-0043-bridge-token-env
scope: Windows DQA 내부 프로세스의 WSL 토큰 전달 및 클라이언트 안내
verdict: PASS (배포 전 코드 검증, 통합·라이브 확인 후속)
---

## 재현 및 수정 검증
- 2026-09-08 11:02 task t_rS0NLnHV4BU5aQ6_: Windows runner → WSL Codex 0.153.4.
  원본 도구 출력 BRIDGE_TOKEN 환경변수 없음. 서버 401/403에 도달하기 전 중단.
- 실제 Windows PowerShell→WSL Python 더미: WSLENV 부재 False, BRIDGE_TOKEN/u True.
- 실제 DQA 동봉 Windows Python 3.14.7에서 수정된 생성 번들의 ask_local_ai→Popen→WSL Python:
  token_matches=true, control_matches=true, parent_wslenv_unchanged=true, exit=0.
  실제 토큰 원문 대신 발급된 적 없는 더미로 OS 경계 자체를 확인했다.
- 신규 11건 + WSL 탐지·프롬프트 suite: 46 PASS.
- 회귀에서 6건 실패를 확인: 1건은 실제 설치 CLI를 탐지하던 fixture, 1건은 app stub import
  순서 의존, 3건은 화면 구조 변경 뒤 첫 참조/고정 바이트로 잘못 자르던 테스트,
  1건은 실제 남아 있던 사라진 1단계 명령 안내(주석도 문자열로 잡는 테스트 결함 동반).
  탐지 경계 고정·실제 순수 판정 AST 실행·이벤트/함수 경계 검사·DQA 메뉴 안내로 수정.
- 수정된 관련 4파일: 229 passed in 6.93s.
- ruff: 변경 Python 소스/신규 테스트 PASS.
- 보안·UX·design panel PASS. 토큰/인증 정책 및 사용자 Codex 설정 무변경.

## 완료 시 확인
- 전체 브리지·클라이언트 회귀 결과.
- 배포본 SHA/사용자 DQA 내부 자동 갱신과 정상 대기.
- UI 수정 문구 Windows-browser 확인.

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
