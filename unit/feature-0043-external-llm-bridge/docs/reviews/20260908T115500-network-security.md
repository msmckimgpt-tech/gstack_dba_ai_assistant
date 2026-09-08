# Security review — DQA task network profile

- Timestamp: 2026-09-08T12:04:07+09:00
- Reviewer: /root/security_review (source read in feature-0043-bridge-network worktree)
- Scope: invoke.py, handler.py, prompt.py, test_runner_dqa_network.py

## 1. Blocking issues
(no findings)

## 2. Cross-domain concerns
(no findings)

## 3. Challenge to current spec

hostname 검증과 이스케이프 뒤 프로필 table 전체를 교체한다. 토큰은 argv 설정에 없고
custom 명령에는 권한 플래그를 추가하지 않는다. 실패·명령줄 길이 처리에서 제한을 제거한
재시도 경로는 없다. BRIDGE_CA는 자식에만 적용하고 전역 TLS 환경은 덮지 않는다.
WSL에서 CA만 /up, 토큰은 /u다. 프롬프트의 토큰 출력 권고도 제거했다.
보장 범위는 정확한 호스트 allowlist와 기존 서버 측 토큰 검사이며 URL path 제한은 아니다.
앞선 설정 결합·실패 폴백 우려는 실제 충돌 대조·회귀·코드 검토로 해소했다.
테스트 코드는 직접 검토했고 실행·Windows 실측은 main의 증거에 근거한다.

## 4. Verdict
PASS — 확정된 보안 결함 없음.
