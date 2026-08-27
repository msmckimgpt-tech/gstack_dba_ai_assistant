---
doc_type: REPORT
feature_id: feature-0045-zd-bridge-continuity
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary

배포 게이트가 브리지 축(개인 AI 의 대기·조사)을 보게 만들고, **대기는 비우고 작업은 기다리는**
비대칭 드레인을 도입했다. 개인 AI 가 붙는 MCP 표면은 2 replica 가 되어 교체 중에도 후보가 남는다.
코드·계약 검증은 끝났고, 남은 것은 라이브 배포 중 실측이다.

## 2. Progress
- Planned: 라이브 배포 중 브리지 연결 유지 실측(`bridge_continuity_summary` 로그)
- In Progress: 없음
- Done: 관측·드레인·게이트 확장·MCP 2-replica·점유 회수·러너 백오프·quiesce 4축·테스트 46건

## 3. Recent Changes
- 총 변경 횟수: 1 (CHG-20260827-0001)

## 4. Open Issues

- **첫 배포에서 실측된 결함 1건 — 수정 완료(CHG-0003)**: `sweep_legacy_ext_tool_mcp` 의 조회
  실패가 `set -e` 로 배포를 중단시켰다. 그 배포에서 web·MCP 는 신 코드로 갔고 워커·gateway 만
  구 코드로 남았다(혼합 버전은 expand/contract 로 안전). 재배포로 마무리한다.

- **강행 경로는 남아 있다.** 상한(180s)을 넘기면 진행 중 왕복이 끊긴다. 그때 **작업**은 회수로
  보존되지만 이미 쓴 토큰·조사는 버려진다. 배포 보고가 그 사실을 숨기지 않는다.
- **MCP 라우트에 active health 가 없다.** 이 전송은 GET 에 4xx 로 답하는 것이 정상이고 코드가
  SDK 버전마다 달라 단일 `health_status` 고정이 위험하다. passive 격리 + 재시도로 대체했다.
- 최초 전환 배포는 `ext-tool-mcp` → `ext-tool-mcp-a/b` 이므로 구 컨테이너 정리
  (`sweep_legacy_ext_tool_mcp`)가 한 번 돈다. 그 순간만 MCP 가 짧게 비므로, **이번 배포
  한 번은** 개인 AI 재연결이 필요할 수 있다(이후 배포부터 무중단).

## 5. 운영 주의 — 배포가 중단된 상태에서의 수동 정리 순서

**배포 스파인이 중간에 죽으면 "이미 한 일" 과 "아직 안 한 일" 의 경계가 로그에 드러나지
않는다.** 실제로 2026-08-27 첫 배포에서 이런 일이 있었다:

1. 배포가 `rollout_mcp_phase` 안에서 죽었다 → **`reconcile_caddy` 는 아직 안 돌았다**.
2. 엣지는 여전히 구 upstream(`ext-tool-mcp:8971`)을 가리키고 있었다.
3. 그 상태에서 구 컨테이너를 먼저 지웠고 → `/api/ai/mcp` 가 **약 2분간 502**.

정리 순서는 **엣지가 무엇을 가리키는지 확인한 뒤**다:

```bash
# 1) 엣지가 보는 설정 확인 — 신 upstream 을 이미 가리키는가?
docker exec repo-caddy-1 grep -c 'ext-tool-mcp-a' /etc/caddy/Caddyfile
# 0 이면 아직 구 설정 → 먼저 caddy 를 재생성해 신 설정을 로드한다
docker compose -f docker-compose.yml -f ../artifacts/deploy/docker-compose.deploy-pin.yml \
  up -d --no-deps --force-recreate caddy
# 2) 그 다음에야 구 컨테이너 정리
docker rm -f repo-ext-tool-mcp-1
```

가장 안전한 것은 **손으로 정리하지 않고 배포를 재실행**하는 것이다(스파인은 멱등이다).

## 5. Test Status
- 자동 테스트: `unit/feature-0045-zd-bridge-continuity/tests/` 46건 PASS
  (앱 계약 10 · 스파인 20 · 토폴로지 8 · 내부 창구 8)
- 회귀: feature-0014(41) · feature-0020 · feature-0041 · feature-0043 스위트 PASS
- 미검증 항목: 라이브 롤링 중 실제 브리지 연결 유지(배포 시점 실측)

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- 없음 (deploy_scope: included — cycle 종료 후 자율 배포)

## 8. Suggested Improvements

- **claim heartbeat**: 지금은 lease(30분) + 강행 시 회수로 러너 생존을 추정한다. 러너가
  주기 신호를 보내면 회수가 정확해지지만, "폴링 금지" 요구와 부딪히므로 별도 판단이 필요하다.
- **admission fence**: quiesce 의 settle 재확인은 완전한 barrier 가 아니다(feature-0020 이
  이미 정직하게 남긴 잔여 창). 앱 측 fence 는 별 cycle 대상.
