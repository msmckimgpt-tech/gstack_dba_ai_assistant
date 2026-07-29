---
run_at: 2026-07-29T05:10:00Z
session: ai/root/feature-0030-ask-timeout-extension
scope: [timeout-extension, composer-banner, rbac, runtime-settings, cancel-responsiveness]
verdict: PASS (핵심 경로 라이브 실증 / 2항목 라이브 미재현 — 단위 테스트 커버, §3 정직 표기)
---

### Run (2026-07-29) — feature-0030 실행시간 연장 — **Environment: Windows-browser (PB-0008)**

cycle: `ai/root/feature-0030-ask-timeout-extension` · CHG-20260729T032307-timeout-extension ·
배포 `80cc7aeb`(web-a/web-b/insight-worker/ask-worker, soak 통과).

- **Bridge**: relay @ `http://172.26.144.1:9223` · Chrome/150.0.7871.115 (`doctor` ok=true)
- **URL**: `https://localhost/` (Caddy :443) · 계정 `bootstrap_admin`
- **Evidence**: `artifacts/shared/win-browser-shots-0030/01_banner_prompted.png` ·
  `02_banner_granted.png`
- **검증용 설정 조정**: `AGENT_TIMEOUT_SEC` 900→60(예산 180s), `PROMPT_PCT` 80→10.
  검증 후 **원복 완료**(900 / 80 재확인). 진행 중 요청 0건 시점을 골라 라이브 영향 회피.

#### 1. PASS — 라이브 실증

| 항목 | 결과 |
|---|---|
| 관리 콘솔 설정 3종 노출 | `AGENT_TIMEOUT_EXTENSION_{ENABLED,PROMPT_PCT,MAX_SEC}` 이 '쿼리·에이전트 실행' 카테고리에 default 1/80/0 · apply_mode=live 로 노출 |
| 신규 권한 카탈로그 | `conversation.extend.{own,any}` 등록(description 45/63자 — catchup abort 임계 255 이내) |
| 권한 backfill (codex P1-4) | `own` → 7역할(admin·dba·dev_server·dos_web·operator·sales·usermanager) · **`any` 는 어느 역할에도 미부여** · 마커 `conversation-extend-perms-v1` 기록 |
| KV 프롬프트 발행 | run 시작 13:59:00 → 프롬프트 13:59:22, `run_id` 일치, `deadline_at=05:02:00Z`(=시작+180s) 정확 |
| 승인 흔적 리셋 (codex P1-2) | prompt 발행 시 `timeout_ext_granted` 가 빈 값으로 리셋됨 |
| `/api/progress` 노출 | `timeout_extension:{prompted:true, granted:false, deadline_at, run_id}` 동봉 |
| **배너 노출** | 컴포저 위 주황 배너 "⏱ 응답 시간 한도에 근접했습니다. 계속 추론할까요?" + [계속 추론], 기존 '즉시 답변'·중단 버튼과 공존 (스크린샷 01) |
| **승인 → 전환** | 클릭 후 배너가 회색 "시간 제한 없이 끝까지 추론하는 중입니다."로 전환·버튼 숨김, 서버 `timeout_ext_granted=1`(14:03:50) + `run_id` 일치 기록 (스크린샷 02) |
| terminal 정리 | 종료된 run 의 `timeout_ext_prompted`/`granted` 가 빈 값으로 정리됨 |
| 무인증 차단 | `POST /api/extend` 무인증 401 |
| **승인 중 '중단' 응답성 (codex P1-3 핵심 계약)** | 무제한 연장이 승인된 run(경과 9분+)에 '중단' → **2초** 만에 terminal 반영. 연장이 탈출구를 막지 않음을 라이브 실증 |

#### 2. 관측 — 승인 run vs 미승인 run 수명 대조

- 미승인 run(13:58:12 시작, 프롬프트 발행됨, 승인 안 함): **187초에 done**.
- 승인 run(13:59:00 시작, 14:03:50 승인): **529초+ 계속 processing** → '중단'으로 종료.

승인 run 이 훨씬 오래 살아남은 것은 사실이나, 두 run 의 red-team 반복 횟수가 달라
**인과를 단정하지 않는다**(§3).

#### 3. 라이브 미재현 (정직 표기) — 단위 테스트로 커버

1. **"승인이 예산 컷을 넘기게 한다"의 인과**: 승인 시점(14:03:50)에 그 run 은 이미 예산
   (14:02)을 넘겨 red-team 반복 수정 단계에 있었다. red-team 은 run 루프 예산 체크 **밖**이라,
   그 run 의 생존이 승인 때문인지 red-team 때문인지 라이브에서 분리되지 않는다.
   → 단위 테스트 `test_budget_survives_with_unlimited_grant` /
   `test_budget_breaks_without_grant` / `test_budget_breaks_after_capped_grant_exhausted` 커버.
2. **"미승인 시 타임아웃 종료 메시지"**: 대조 시도 2건이 예산 내(107초) 또는 예산 직후
   (187초)에 **자연 완료(done)** 되어 타임아웃 종료 경로에 진입하지 않았다.
   → 단위 테스트 `test_budget_breaks_without_grant` 커버.

두 항목의 라이브 재현에는 red-team 을 끄고(`REDTEAM_ENABLED=0`) 예산을 더 줄여야 하는데,
라이브 설정을 추가로 흔드는 비용이 이득을 넘어 수행하지 않았다. 필요 시 스테이징에서 재현한다.

#### 4. 잔여 위험 실측 (codex P2-3 — REVIEW.md 에 기록된 항목의 라이브 확인)

프롬프트 발행이 **루프 재진입에 의존**하는 구조적 한계가 라이브에서 관측됐다:
같은 설정(임계 18초)에서 한 run 은 22초에 발행됐지만, 다른 run 은 82초까지 미발행이었다
(긴 LLM 호출·적은 라운드 수로 루프 상단 재진입이 없었음). 예산 초과 시점 재발행 + 20초 유예가
최후 방어선으로 남아 있으나, **임계 시점 발행 자체는 보장되지 않는다**.
