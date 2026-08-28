---
run_at: 2026-08-28T18:00:00+09:00
session: ai/root/feature-0043-live-steps-placement
scope: feature-0043 진행 표시 자리·귀속 — 말풍선 안 렌더 · 자기 run 각인 · progress 이중 렌더 차단
verdict: PARTIAL — 계약·배선 PASS / 화면 확인은 **배포 후**(수정본이 아직 라이브에 없음)
---

# Run — 진행 표시 자리·귀속 정합 (TASK-20260828T180000)

Environment: **Windows-browser 브리지 정상**(relay @ `172.26.144.1:9223`)이나 **이 수정은
배포 전**이라 라이브에서 확인할 수 없다 + 컨테이너 pytest/ruff PASS

## 왜 이번엔 "브리지 불가" 가 아니라 "배포 전" 인가

직전 검증(`TASK-20260828T160000`)에서 브리지로 라이브 화면을 확인했고, 그때 **바로 이 결함**이
사용자 스크린샷으로 드러났다. 즉 화면 검증이 가능해졌기 때문에 발견된 회귀다.

지금 고친 코드는 아직 `main` 에 없다 — 라이브를 열어도 **이전 코드의 화면**이 보인다.
`verify-completion` 을 통과시키려고 그 화면을 "확인했다" 고 적으면 그건 거짓이므로, 배포 후
확인을 잔여로 남긴다.

## 무엇이 틀렸었나 (사용자 스크린샷 기준)

```
[새 질문]
Assistant  연결된 AI 가 이 질문을 가져갔습니다. 조사·작성 중입니다.
           ▶ 쿼리 결과
           [단계 보기 (21)]        ← ① 직전 답변의 단계 수
──────────────────────────────     ← 말풍선 경계
내부 동작  질문을 가져왔습니다 …    ← ② 카드가 말풍선 밖으로 흘러나옴
read_task_attachment …
SQL 실행 …
```

| # | 뿌리 | 조치 |
|---|---|---|
| ① | 대기 말풍선 meta 에 `run_id` 각인 부재 → `_load_steps_for_message` 가 "이 시각 이전 최근 run"(직전 답변)으로 폴백 | placeholder 저장 시 `run_id = task_id` |
| ② | 앵커(`data-bridge-task`)가 **메시지 행**에 부착 — 행은 아바타·메타·말풍선의 바깥 컨테이너 | 앵커를 `.message-bubble` 로 이동 |
| ③ | `/api/progress` run 폴백이 브리지 run 을 잡아 **내부 progress-strip** 도 켬(이중 렌더) | `run_id NOT LIKE 't\_%'` 로 제외 |

③ 은 직전 cycle(P0-Z)이 만든 회귀다 — 사후 이관만 걸러내던 `bridge-ledger` 필터를, 호출 시점
기록이 다른 출처(`derived`·`external-ai`·`bridge-runtime`)로 우회했다.

## 검증한 것

- `make test` — **내 변경으로 인한 신규 실패 0**.
  (feature-0008 `test_verify_session.py` 4건은 **main 에서도 동일하게 실패**하는 기존 항목.)
- 신규 `test_live_steps_placement.py` 7건 — run_id 각인 · 앵커 위치(행 부착 금지) ·
  placeholder 한정 · 브리지 run 제외 · **접두 규칙이 생성부와 일치**(갈리면 제외가 무효) ·
  사후 이관 제외 유지.
- ruff All checks passed.

## 배포 후 확인 항목

1. 새 질문을 보냈을 때 대기 말풍선의 「단계 보기」가 **그 질문의 단계 수**를 가리키는지
   (직전 답변의 수가 아닌지).
2. 진행 단계 카드가 **말풍선 안**에 그려지는지(밖으로 흘러나오지 않는지).
3. 진행 중 화면에 단계가 **한 번만** 그려지는지(말풍선 안 + progress-strip 이중 렌더 없음).
