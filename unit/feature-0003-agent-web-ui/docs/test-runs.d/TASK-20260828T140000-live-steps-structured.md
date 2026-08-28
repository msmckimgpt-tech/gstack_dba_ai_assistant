---
run_at: 2026-08-28T14:00:00+09:00
session: ai/root/feature-0043-live-steps-structured
scope: feature-0043 진행 표시 구조화 · 내부 동작 단계 · 진행 신호 기반 타임아웃
verdict: PARTIAL — 계약·배선 PASS / 화면 재확인은 브리지 재기동 후 사용자 테스트
---

# Run — 진행 표시 구조화 (TASK-20260828T140000)

Environment: **Windows-browser 미수행 (이번 turn 중 브리지 끊김)** + 컨테이너 pytest/ruff PASS

## 브리지 상태

이번 세션 앞부분에서는 브리지가 살아 있어 PB-0008 을 수행했다
(`TASK-20260828T120000-pb0008-bridge-live.md` — 제목·단계 사유 PASS). 그 뒤 Chrome 이 종료돼
`doctor` 가 `bridge_mode: null` 로 바뀌었고, 이 변경의 화면 재확인은 하지 못했다.

```
{"ok": false, "win_host": "172.26.144.1", "bridge_mode": null,
 "issues": ["동작 중인 CDP 브리지 없음 — Windows Chrome 미기동이거나 WSL→Windows relay 미구성."]}
```

`launch` 로 다시 띄울 수 있으나, 그 격리 프로필에는 `bootstrap_admin` 세션만 있어 admin 러너와
계정이 어긋난다(같은 제약이 deferred 검증에서도 남아 있다).

## 대신 검증한 것

- `make test` 전량 green(컨테이너) · ruff All checks passed
- 신규 `test_live_steps_structured.py` 16건 + 러너 타임아웃 계약 4건
  - 진행 단계의 **출처**(`agent_runtime.steps`)와 **키**(`work`·`reason`·`action`·`*_source`)
  - 옛 클라이언트용 종전 키(`datasource`·`schema`·`rows`) 유지
  - 생애주기 activity 배선(claim·submit) + 지어내기 금지선 문서화
  - 표시층 통일: 진행 중·말풍선 둘 다 `buildStepDetailEl`, 옛 문자열 조립 부재
  - lease 갱신 배선 3곳(`run_structure_tool`·`read_task_attachment`·`get_task_context`)
    + 점유자 스코프 + 제출 후 갱신 금지 + 실패 흡수
  - 러너: 기본 상한 없음 · 0일 때 검사 skip · 취소 유지 · opt-in 플래그
- 기존 계약 3건 갱신(진행 단계 출처 · 필터 공유 · 러너 타임아웃)

## 배포 후 사용자 확인 항목

1. 질문 전송 직후 대기 말풍선 안의 진행 표시가 **카드 형태**인지(도구 배지 + 작업 + 근거),
   `list_schemas 3행` 같은 평문 나열이 아닌지.
2. 실행 단계에 「내부 동작」 배지가 붙은 단계(가져옴·정리함)가 보이는지.
3. 긴 조사(10분 이상)가 **중간에 끊기지 않는지** — "AI 호출이 …초를 넘겨 중단했습니다" 가
   더는 나오지 않아야 한다. (러너를 새 코드로 재기동해야 적용된다.)
