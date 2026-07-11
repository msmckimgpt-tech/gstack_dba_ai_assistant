---
doc_type: ANCHOR
feature_id: feature-0014-zero-downtime-deploy
created_at: 2026-06-30T12:00:00Z
status: active
edit_policy: mixed
source_of_truth: true
---

# ANCHOR: feature-0014-zero-downtime-deploy 무중단 배포 구조

## §1. 외부 관점 요약
"단일 호스트 Docker Compose 인데 왜 web 을 굳이 2개(web-a/web-b)나 띄우고 Caddy
로드밸런싱·롤링 스크립트까지 만들지? 그냥 `up -d web` 한 줄이면 되잖아?"
→ 이유: 이 프로젝트는 `deploy_scope: included` 라서 **머지마다 web 이 자동 재배포**되고,
5개 worktree 가 동시에 머지하는 고병렬 환경이다. 단일 컨테이너 recreate 는 매번 Caddy 502
blip 을 만들고, 하루에도 여러 번 사용자가 그 중단을 체감한다. 오케스트레이터(k8s/Swarm)
없이 단일 호스트에서 **구조적으로 항상 ≥1 healthy upstream** 을 보장하는 최소 수단이
"Caddy 뒤 2-replica + one-at-a-time 롤링"이다. 복잡도의 대부분은 토폴로지가 아니라
**고병렬 자동배포를 무인으로 안전하게** 만드는 부분(flock 직렬화·origin/main coalesce·
TLS preflight·migrate 게이트·post-cutover soak 롤백)에 있다.

## §2. 대안 분기
- **Alt-A: 단일 인스턴스 + Caddy dial-retry(Tier 1).** 페르소나: 변경 최소화를 원하는 운영자.
  안 고른 이유: Caddy 의 keepalive/DNS 캐싱 때문에 단일 `web:8000` 으로는 retry 가 갈 곳이
  없어(유일 upstream 이 죽으면 재시도 불가) 효과가 near-zero 도 불확실. host-port 이전·
  deploy 스파인은 어차피 Tier 2 와 공유 전제라 곧장 Tier 2 가 버리는 작업이 없다.
- **Alt-B: blue-green by network-alias + caddy reload.** 페르소나: 한 번에 한 버전만 노출하길
  원하는 팀. 안 고른 이유: alias 토글에 atomic replace 가 없어 connect-new/disconnect-old/
  reconnect 가 thrash 하고 Caddy reload 까지 필요 — 2-upstream LB 보다 복잡하면서 atomicity 는
  더 나쁨(심사 env_fit 6).
- **Alt-C: 오케스트레이터(k8s/Swarm) 롤링.** 페르소나: 멀티노드 클러스터 팀. 안 고른 이유:
  단일 WSL2 호스트에 오케스트레이터 도입은 과한 운영 부담이고 기존 compose 자산 전면 재작성.

## §3. 가정된 사용 시나리오
사내 직원 사용자가 `https://mysql-ai.company.local` 에서 어시스턴트와 대화 중이다. 같은 시각
다른 개발자의 feature PR 이 머지되어 cycle-finalize 가 web 자동 재배포를 트리거한다. 사용자는
방금 질문을 보냈고 ask-worker 가 답을 생성 중이다 — 배포가 진행되는 동안에도 페이지는 502 없이
응답하고, 폴링 중인 run 상태도 끊기지 않으며, 사용자는 배포가 일어났다는 사실 자체를 알지
못한다. (단, admin 이 그 순간 프롬프트 자동생성 SSE 를 돌리고 있었다면 deploy-web.sh 의
pre-drain 게이트가 그 스트림이 끝날 때까지 해당 replica recreate 를 미룬다.)

## §4. 외부 검증 로그 (append-only)
(엔트리 없음 — 일반 TASK cycle 완료 조건은 아님. 라이브 롤링 zero-502 부하 + non-root dry-run 검증은 운영자 수행 후 human 이 append 예정.)
