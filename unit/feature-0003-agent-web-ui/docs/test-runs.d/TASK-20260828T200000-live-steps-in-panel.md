---
run_at: 2026-08-28T20:00:00+09:00
session: ai/root/feature-0043-live-steps-in-panel
scope: feature-0043 진행 표시를 말풍선 details·사이드 패널에서 갱신(제3 블록 폐기)
verdict: PARTIAL — 계약 PASS / 화면 확인은 배포 후
---

# Run — 진행 표시 자리 통합 (TASK-20260828T200000)

Environment: **Windows-browser 미수행(수정본이 아직 배포 전)** + 컨테이너 pytest/ruff PASS

## 제보 화면

```
말풍선:  ▶ 실행 단계        ← 접힌 드롭다운(1단계)
         [단계 보기 (1)]     ← 개수 멈춤
         ─────────────────
         내부 동작 …         ← 드롭다운 밖에 카드가 계속 쌓임
사이드 패널: 1단계            ← 열어 둔 시점 그대로
```

진행 표시가 `.bridge-live-steps` **제3 블록**에만 쌓였고, 완료본이 쓰는 두 자리는 아무도
갱신하지 않았다.

## 검증

- `make test` 전량 green · ruff All checks passed
- 신규 `test_live_steps_in_panel.py` 7건 — 제3 블록 생성 금지 · details 갱신(펼침 유지) ·
  개수와 클릭 대상 동시 갱신(리스너 중복 방지) · 패널 run 스코프 · 옛 블록 정리 · export 단일성
- 기존 계약 1건 갱신(`buildStepDetailEl` 직접 호출 → `renderMessageDetails` 경로)

## 배포 후 확인 항목

1. 질문 전송 후 「▶ 실행 단계」를 펼쳐 두면 단계가 **그 안에서** 늘어나는지.
2. 「단계 보기 (N)」의 N 이 진행에 따라 늘고, 눌렀을 때 **최신 목록**이 열리는지.
3. 사이드 패널을 열어 둔 채 진행하면 패널이 **함께 갱신**되는지.
4. 이전 답변의 패널을 열어 둔 상태에서 새 질문이 돌 때, 그 패널이 **덮어쓰이지 않는지**.
