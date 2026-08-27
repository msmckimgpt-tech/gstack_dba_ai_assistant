---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: active
ai_generated: true
feature_id: feature-0045-zd-bridge-continuity
linked_unit: unit/feature-0045-zd-bridge-continuity
created: 2026-08-27
sources:
  - ../../unit/feature-0045-zd-bridge-continuity/docs/FUNCTION.md
  - ../../unit/feature-0045-zd-bridge-continuity/docs/ANCHOR.md
---

# Feature — 브리지 배포 연속성 (zd-bridge-continuity)

> 사람용 입구. 정본: [[../../unit/feature-0045-zd-bridge-continuity/docs/FUNCTION|FUNCTION.md]].

## 목차

- [한 줄 요약](#한-줄-요약)
- [상태](#상태)
- [왜 필요했나](#왜-필요했나)
- [책임 경계](#책임-경계)
- [관련 정본](#관련-정본)
- [관련 노트](#관련-노트)
- [Open questions](#open-questions)

## 한 줄 요약

웹브라우저–개인 AI 브리지가 **연결된 채 요청을 주고받는 중에도** 배포가 그 작업을 끊지 않도록,
배포 게이트에 브리지 축을 더하고 대기는 교대시키되 진행 중 왕복은 완주를 기다리게 만든 재구성.

## 상태

- 단계: shipped (2026-08-27 · 라이브 배포 `e7d54f70` · **끊김 0 실측**)
- 위험도: Major
- 검증: 46건(앱 계약 10 · 스파인 20 · 토폴로지 8 · 내부 창구 8)

## 왜 필요했나

무중단 배포는 [[feature-0014-zero-downtime-deploy]] 에서 이미 만들었다. 깨진 것은 스파인이
아니라 **계기판**이다 — [[feature-0043-external-llm-bridge]] 전환으로 추론 주체가 개인 머신
AI 로 넘어가면서 사용자 작업은 `WebAiTasks` + 브리지 왕복 위에서 일어나게 됐는데, 게이트가 보는
신호(`active_streams` · `ask_jobs`)는 그 둘 중 어느 것도 세지 않는다.

즉 개인 AI 가 붙어 대기하고 질문을 조사하는 **바로 그 순간에도** 배포는 0 을 읽고 "조용하다" 고
판정했다. 무중단이 깨진 것이 아니라, **무중단이라고 믿게 만드는 계기판**이 남은 것이다.

## 책임 경계

| 축 | 무엇 |
|---|---|
| 관측 | `bridge_drain.py` — 대기(`bridge_waiters`)와 작업(`bridge_inflight`)을 **따로** 센다 |
| 드레인 | `/livez` 503(엣지 후보 제외) + 도구 경로 503 `X-Bridge-Draining`(어댑터 재라우팅) |
| 게이트 | `predrain` 이 작업만 기다린다(상한 180s). 대기는 드레인으로 즉시 빈다 |
| 표면 | `ext-tool-mcp-a/b` 2 replica + Caddy LB + stateless + 전용 롤링 |
| 손실 방지 | 강행 시에만 점유 회수 — `ClaimedBy` 보존, lease 만 만료(먼저 끝내는 쪽이 이긴다) |
| 러너 | 대기엔 sleep 없음(유지) · **재연결**에만 백오프(busy-loop 제거) |
| 정직성 | quiesce 4번째 축 + 배포 보고 `bridge_continuity_summary` |

## 관련 정본

- `unit/feature-0045-zd-bridge-continuity/docs/FUNCTION.md` · `ANCHOR.md` · `DECISIONS.md`
- `bin/deploy-web.sh` · `bin/lib/quiesce.sh`
- `unit/feature-0003-agent-web-ui/src/bridge_drain.py`

## 관련 노트

- [[feature-0014-zero-downtime-deploy]] — 무중단 스파인 본체
- [[feature-0020-zd-deploy-all]] — 워커·gateway 롤아웃 확장
- [[feature-0043-external-llm-bridge]] — 이 기능이 지키려는 그 축
- [[feature-0041-external-ai-tool-surface]] — MCP 표면 정본

## Open questions

- 강행(상한 초과) 시 이미 쓴 토큰·조사는 되돌릴 수 없다. 작업만 보존된다.
- claim heartbeat 도입 여부 — 회수가 정확해지지만 "폴링 금지" 요구와 부딪힌다.
