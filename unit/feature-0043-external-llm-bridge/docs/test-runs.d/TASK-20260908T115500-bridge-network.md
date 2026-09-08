# DQA 호스트 네트워크와 CA 전달 검증

- Environment: 실제 Windows 설치된 DQA + WebView2 / 동봉 Python 3.14.7 / WSL Codex 0.153.4.
- Task: TASK-20260908T115500-bridge-network / Issue #1607 (첫 PR #1609 후속).

## 첫 배포의 실제 도달 및 한계

- 7da91830 web-a/web-b 배포·90초 soak PASS, 관측 창 Caddy no upstreams available 0.
- 일반 서버 대화 스모크는 web-only로 skip. 실제 앱 작업을 별도로 수행했다.
- 사용자는 DQA 앱만 실행하는 경로. 현재 구 설치본은 트레이 메뉴가 5개라 [종료] ID를
  실제 메뉴에서 확인했다. 새 소스의 [업데이트 확인] 메뉴 존재와 구 설치본 상태를 구별한다.
- DQA 앱의 Codex(WSL) 선택·연결로 내부 구성요소 자동 수신, 대기 중 표시 확인.
  서버/PC SHA-256 d875c9ee8b11e95315a0b2b959715e7f125818ef62f1331cc7c4711f4aa307a4.
- 검증용 새 대화에 65바이트 SQL 첨부를 업로드했다. 사용자 원본 SQL 리뷰 대화는 변경하지 않았다.
- task t__srshhWNSdGOU93V, 첨부 1282, session 01a07ee9-d956-7841-b358-365dcddd96d8.
  도구는 getenv 이후 실제 read_task_attachment POST를 시도했으나 EPERM. 기본 read-only,
  approval never. 사용자 config의 sandbox_mode/default_permissions/approval_policy 키는 미설정.
- 첫 번째 줄을 미확인이라고 답한 실제 화면까지 확인. 성공으로 기록하지 않는다.

## 후속 수정의 권한 경계 실측

- 공식 근거: https://learn.chatgpt.com/docs/permissions 의 read-only + network allowlist.
  domain 규칙만으로는 부족하며 features.network_proxy를 함께 활성화해야 강제된다.
- 실제 codex sandbox: DQA /livez 200, example.com proxy 403, 파일 write EPERM.
- 같은 이름 프로필에 먼저 extends=:workspace 및 domains={*=allow}를 주입한 대조에서도
  제품의 전체 table override 이후 위 결과 동일. 넓은 기존 규칙 잔류 없음.
- 실제 Windows Python→생성 번들→WSL Codex sandbox: token_present=true, ca_exists=true,
  DQA CA로 TLS검증 200, 다른 host403, write_denied=true. 실제 사용자 토큰 대신 더미 사용.
- SSL_CERT_FILE 등 CLI 자체 TLS 환경은 건드리지 않고 BRIDGE_CA만 전달한다.
- 집중 103 passed/1 skipped, 변경 Python ruff PASS. 전체 브리지 회귀 및 security 확인 진행.
- 실제 앱 본문 재조회와 임시 CDP/relay 정리 결과는 후속 PR 설명으로 보강한다.

## 배포 전 확정 (2026-09-08T12:04:07+09:00)

- 전체 브리지 **1658 passed, 1 skipped** (160.12s), 변경 Python ruff PASS.
- Security 구현 확인 PASS, 앞선 설정 결합 우려는 실측으로 해소.
- 정책 SHA-256 양쪽 동일: 024a8b53b67f2b14e35986aca68ecc8f59470c7e312b0f0f92cb79b91026df1d.
