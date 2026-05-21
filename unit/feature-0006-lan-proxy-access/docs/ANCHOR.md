---
doc_type: ANCHOR
feature_id: feature-0006-lan-proxy-access
created_at: 2026-04-24T08:24:32Z
status: active
edit_policy: mixed
source_of_truth: true
---

<!--
ANCHOR.md — External Anchor Document (9번째 1급 문서)

이 문서는 기능의 "방향성 stable reference"다. AI-delegated 개발의 폐쇄 루프 문제를
방지하기 위해 외부 관점과 가정된 사용 맥락을 명시적으로 기록한다.

정책 요약 (AGENTS.md §17):
- §1~§3 (stable reference): rewrite 가능. 방향이 바뀌면 명시적으로 갱신한다.
- §4 (외부 검증 로그): append-only. source는 `human:<name>` 만 허용. AI는 §4 writer가 아님.
- Conflict Protocol: AI는 사용자 요청이 §1~§3와 충돌 시 작업을 시작하지 않고
  gstack skill(`/office-hours`, `/plan-ceo-review` 등) 재앵커를 유도한다.
- 24h bootstrap grace: `created_at` 기준 24시간 이내면 §1~§3이 빈칸이어도 verify 통과.
-->

# ANCHOR: feature-0006-lan-proxy-access

## §1. 외부 관점 요약

- **"LAN 프록시가 왜 feature인가? 단순 Caddy 설정이지 않나?"**
  → Windows 호스트에서 WSL 내부 docker 서비스로 TLS 접근하는 **비표준 네트워킹 경로**.
  Windows portproxy + Caddy TLS 조합이 "로컬 dev HTTPS 시나리오 재현"을 가능하게 함.
  설정만이 아니라 **운영 절차 + 스크립트**까지 포함하므로 feature급 관리 필요.
- **"왜 인증서 파일은 여기 없는가?"**
  → `../../../../artifacts/certs/`에 분리. 인증서는 environment-specific, 버전관리
  대상 아님.
- **"이 구성이 정식 배포 환경에도 그대로 적용되나?"**
  → **아니다**. 현재 구성은 **로컬 dev용 transitional 구조**이며, 정식 배포 시에는
  검증된 공인 인증서를 사용하는 웹사이트 배포로 전환 예정. 이 feature의 **일부 구성
  요소만 프로덕션으로 cherry-pick** 되고(Caddy 설정 템플릿, reverse proxy 레이아웃 등),
  Windows portproxy 같은 dev-specific 경로는 배포 단계에서 제거됨.

## §2. 대안 분기

- **Alt-A: nginx 또는 traefik으로 프록시.** 페르소나: 다른 프록시 생태계 친숙 팀.
  안 고른 이유: Caddy의 자동 인증서 발급 + 간결한 설정이 로컬 dev에 최적. 변경 이유 없음.
- **Alt-B: 프록시 없이 각 서비스가 직접 TLS.** 페르소나: "서비스 자가 완결" 선호 팀.
  안 고른 이유: 인증서 분배/갱신을 서비스 수만큼 반복. 단일 진입점(Caddy)이 compact.

## §3. 가정된 사용 시나리오

- **LAN의 다른 기기(폰, 태블릿)에서 웹 UI 접근 실패 이슈:** 새 AI가 "HTTPS 안 된다"
  받음. §1을 읽으면 Windows portproxy 설정이 선행 필요함을 이해하고, `src/windows/`
  스크립트 확인 순서로 진단. "certs를 고쳐라"로 튀지 않는다.
- **정식 배포 준비 시 체리피킹 대상 식별:** 새 AI가 "이 feature를 프로덕션으로 옮겨라"
  요구를 받음. §1의 **"일부 구성 요소만 cherry-pick"** 원칙을 읽고 `src/caddy/Caddyfile`은
  프로덕션 설정 템플릿의 기반으로 유지, `src/windows/`는 dev-only로 제외,
  `artifacts/certs/` 대신 공인 인증서 경로(`/etc/letsencrypt/` 등)로 재배치한다는
  판단 기준을 얻는다.

## §4. 외부 검증 로그 (append-only)
<!-- 완료 cycle마다 최소 1개 엔트리 (release/milestone 또는 방향 전환 검증 시). source: human:<name>, timestamp: ISO8601, challenge: 한 줄, body: ≥ 200자. AI는 §4 writer 아님 — 인간이 직접 append (gstack skill 결과 paste 또는 리뷰어 판단 기록, 카고 컬트 방지). -->

(엔트리 없음 — 일반 TASK cycle 완료 조건은 아님; release/milestone 검토 또는 방향 전환 검증 시 사용)
