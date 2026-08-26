---
doc_type: FEATURE_DECISIONS
feature_id: feature-0044-qa-staging-pipeline
status: active
edit_policy: append-only
source_of_truth: true
---

# Feature Decisions

## ADR-20260826T140000-build-once-pull-promote
- Status: proposed (사용자 승인 대기)
- Date: 2026-08-26
- Context: 라이브 배포 전 관문으로 격리망 QA 머신을 도입한다. QA 머신은 VPN 경유로만 접근
  가능하고 아웃바운드는 사내 저장소만 허용된다. 현행 배포 스파인 `bin/deploy-web.sh` 는
  **배포 대상 호스트에서** `git checkout origin/main` + `docker build` 를 수행하는데, 이
  전제가 격리망에서 성립하지 않는다. 사내 미러를 붙여 대상 호스트에서 빌드하더라도, 의존성
  lock 없이는 미러가 시점에 따라 다른 버전을 주므로 개발 머신 이미지와 QA 이미지가 다른
  바이트가 된다 — 그러면 QA 단계 자체의 의미(검증한 것이 배포된다)가 사라진다.
- Decision: **build once, deploy many + pull-based CD + 태그 승격** 3원칙을 채택한다.
  1. 빌드는 사내 GitLab CI 한 곳에서만 수행하고, 산출물을 사내 registry 에 push 한다.
     QA·라이브는 **이미지 다이제스트**로 pull 만 한다(태그가 아니라 다이제스트 — 태그는 이동한다).
  2. 배포는 QA·라이브가 각자 폴링해 당긴다. 개발망이 VPN 너머로 밀지 않는다.
  3. 승격은 재빌드가 아니라 `qa/<tag>` → `promote/<tag>` 태그 이동이다.
  현행 무중단 스파인(롤링·pre-drain·soak·last-good 롤백)은 **유지**하고 이미지 획득 경로만
  교체한다 — 스파인이 이미 `docker-compose.deploy-pin.yml` 로 이미지를 고정하므로 확장
  지점이 존재한다(`--from-manifest`).
- Consequences:
  - (+) dev·QA·live 가 같은 바이트를 쓴다는 것이 다이제스트로 **증명 가능**해진다.
  - (+) 인바운드 방화벽 구멍이 불필요하고, 배포 자격증명이 개발망에 상주하지 않는다.
  - (+) 롤백이 빨라진다 — 이전 다이제스트 이미지가 로컬에 남아 재빌드가 없다.
  - (−) **폐쇄망 빌드 재현성 확보(Phase 1)가 선행 필수**다: Dockerfile `FROM` 파라미터화,
    pip 사내 미러 + 해시 고정, compose 외부 이미지 8종의 미러화와 패치 버전 핀. 실작업량의
    대부분이 여기 있다.
  - (−) 원격이 둘(GitHub 개발 / GitLab 배포)이 되어 정본 규율이 필요하다. QA deploy key 를
    read-only 로 두어 구조적으로 차단한다.
  - (−) 릴리즈 매니페스트라는 새 산출물의 관리 비용이 생긴다. 대신 그 파일이 preflight 의
    검사 기준이 되어 "env 키 누락으로 부분 기동" 같은 실패를 배포 전에 막는다.
- Supersedes: 없음 (현행 로컬 빌드 경로는 제거하지 않고 개발 머신용 fallback 으로 보존)
- Superseded By: —

## ADR-20260826T140100-completion-by-mcp-reachability
- Status: proposed (사용자 승인 대기)
- Date: 2026-08-26
- Context: 이 서비스의 사용자 진입 경로는 웹 화면이 아니라 **개인 머신 AI 런타임의 MCP 연결**
  (feature-0041 도구 표면 + feature-0043 pull 브리지)이다. 컨테이너가 전부 healthy 여도
  VPN DNS 가 `WEB_PUBLIC_HOST` 를 못 풀거나, MCP 클라이언트가 TLS 를 신뢰하지 않거나,
  OAuth discovery 엔드포인트가 404 면 사용자는 진입 자체를 못 한다. 컴포넌트 health 로 완료를
  선언하면 "기동은 됐는데 못 쓴다" 는 재보고가 발생한다(AGENTS.md §16.3 bring-up/access
  완료 기준이 지적하는 바로 그 패턴).
- Decision: 배포 완료 판정에 **사용자 진입 경로 도달성**을 포함한다.
  - 자동: `/livez`·`/readyz` + **OAuth discovery 2종**(`/.well-known/oauth-protected-resource`,
    `/.well-known/oauth-authorization-server`) + `/api/ai/mcp` 프로토콜 응답 + 대화 경로 스모크
    + 브리지 `list_open_requests` 왕복.
  - 수동: VPN 밖 사용자 머신에서 MCP 연결 → 브라우저 OAuth 완주 → 도구 1회 호출 → 웹 렌더 확인.
  - 자동 스모크 실패 시 배포를 롤백하고 **승격 태그를 붙이지 않는 것**으로 라이브를 보호한다.
- Consequences:
  - (+) "배포 성공인데 아무도 못 쓴다" 를 구조적으로 차단한다.
  - (+) TLS·VPN DNS 같은 인프라 의존 조건의 결손이 배포 시점에 드러난다(나중에 사용자 신고로
    드러나지 않는다).
  - (−) 수동 QA 축이 남는다 — OAuth 브라우저 완주는 VPN 밖 실제 클라이언트에서만 검증 가능해
    자동화로 대체할 수 없다.
  - (−) 사내 CA 서명 인증서가 사실상 필수가 된다. MCP 클라이언트에는 브라우저의 예외 승인
    버튼이 없어 self-signed 면 연결 자체가 실패한다.
- Supersedes: 없음
- Superseded By: —
