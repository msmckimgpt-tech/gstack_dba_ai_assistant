---
run_at: 2026-08-24T14:35:00+09:00
session: ai/root/feature-0003-agent-web-ui
scope: stale 표시 임계 파생(A) + 마지막 활동 시각 정직화(B) — conv-audit FR-stale-threshold-below-llm-attempt-cap
verdict: 사전 미수행(사유 있음) — POST-DEPLOY PB-0008 로 수행
---

# Run — PB-0008 시각검증 (Environment: Windows-browser — POST-DEPLOY 예정, 사전 미수행 사유 명시)

- 변경 소유: 본 feature(`CHG-20260824T142000-stale-threshold-attempt-cap`,
  `REV-20260824T142000-stale-threshold-attempt-cap`).
- 시각 표면 2곳: ① 대화 부제 `최근 갱신 … · 상태 …`(app.js — effective 시각 우선 + 상태 한국어화)
  ② 사이드바 `.conv-dot.is-stale-error` hover 툴팁의 "마지막 활동"(sidebar.js).

## 사전 미수행 사유 (재현 조건이 데이터 상태에 종속)

두 표면은 **`last_status='processing'` + 무갱신 시간이 임계 초과** 인 대화가 있어야 렌더된다.
그 상태를 인위적으로 만들려면 `agent_runtime.kv`(`last_status`/`last_status_at`) 또는 `steps` 에
**write** 가 필요한데, 이 변경을 낳은 `/_dqa:conversation_audit` 는 대화 저장소에 대해
**읽기 전용**(SELECT/집계만, UPDATE·DELETE·DDL 금지)을 불변 제약으로 둔다. 라이브에 write 하는
방식으로는 검증하지 않는다.

사고 대화(`…816ab7f3`)는 감사 도중 **12:52:00 에 `done` 으로 정상 종결**되어(재개된 run 이 답변
완성) 재현 대상 자체가 사라졌다. 30일 전체에서 gap ≥1200s 는 그 1건뿐이라 대체 대화도 없다.

즉 이 표면의 실측은 **"같은 조건이 라이브에서 다시 발생할 때"** 만 가능하다 — 그래서
POST-DEPLOY 관측으로 이월한다(원장 `FR-stale-threshold-below-llm-attempt-cap` 의 "라이브 실측
필요분" 과 동일 항목).

## 사전 확보한 기계 증명 (시각검증 대체가 아니라 보완)

- 프론트 **소스 잠금 2종**: 부제와 사이드바 툴팁이 **둘 다** `last_activity_effective_at` 를 우선
  참조한다(한쪽만 고치면 같은 화면에 서로 다른 "마지막 활동" 이 보이는 회귀) · 부제 상태 칸에
  원시 enum `${conversation.status}` 가 남아 있지 않다.
- 폴백 계약: 서버가 신규 필드를 못 실으면 `last_activity_at` → `created_at` 순으로 폴백 →
  구 payload 에서 **종전과 동일 렌더**(신규 필드 부재가 화면을 깨지 않는다).
- `pendingStatusLabel` 은 동일 모듈 함수 선언이라 호출 위치에서 유효(§18.8 codex 확인).
- 판정·직렬화 축: 신규 19 PASS · 관련 3파일 42 PASS(임계 불변식 · 사고 재현 입력 · offset→UTC ·
  terminal 반환) · ruff clean · ESM `node --check` 통과.

## POST-DEPLOY 계획 (실 Windows Chrome)

1. 배포 후 `processing` 대화가 20~33분 무진전 구간에 들어간 시점에 사이드바 dot 이
   **주황(is-processing) 유지**인지(붉은 stale 로 넘어가지 않는지) 확인 — 봉인 A 의 사용자 표면.
2. 실제로 stale 이 정당하게 뜬 대화에서 툴팁 "마지막 활동" 이 `steps` 최종 시각과 일치하는지
   (요청 접수 시각이 아닌지) 대조 — 봉인 B.
3. 부제가 `상태 작업 중단 감지`(한국어)로 표시되고 `stale_error` 원시 문자열이 화면에 없는지.
4. 콘솔 에러 0 + 판독 가능한 확대 캡처.
