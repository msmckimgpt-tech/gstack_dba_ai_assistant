---
run_at: 2026-09-02T11:00:00+09:00
session: ai/root/kb-prompt-grounding
scope: KB 근거 자동 주입 — 도구 호출에 기대지 않는다 (20260902T110000-kb-prompt-grounding)
verdict: PASS
---

### Run 0 — 결함 발견 (Environment: Windows-browser · 부트스트랩 계정에 AI 연결 · 라이브 배포본)
사용자 요청으로 부트스트랩 계정에 브리지 러너를 붙여 **실제 대화를 완주**시켰다.
직전 두 cycle 이 만든 도달 경로가 **라이브에서 여전히 0 기여**였다.

    질문: "steam_billing_log 의 status 코드값이 각각 무슨 뜻이고 …"
    AI  : "steam_billing_log 라는 테이블 자체가 등록 메타데이터 어디에도 없습니다"

같은 시각 같은 제품에서 `get_task_context` 를 직접 부르면 그 정의가 **분명히 나온다**.
- 도구 호출 기록 **0건**(실행 단계 패널·UI 전수 검색).
- 원인: `compose_prompt` 의 도구 목록에 `get_task_context` 가 **없다** —
  `list_schemas`·`describe_schema`·`describe_table`·`search_tables`·`get_table_indexes`·
  `get_foreign_keys`·`execute_sql` 뿐이다. 없는 도구는 부를 수 없다.

**이 결함은 단위 테스트·핸들러 직접 호출로는 절대 안 나온다** — 「AI 가 부를지 말지」에 달려
있었기 때문이다. 라이브 대화를 완주시켜야만 보인다.

### Run 1 — 단위 (Environment: bare-runner pytest)
- `test_kb_prompt_grounding.py` **8 passed** — 러너 배치 5건(본문 삽입·미제공 시 생략·질문보다
  앞·재조사 금지 안내·job 우회) + 서버 계약 3건(응답 필드·원문 매칭·상한/절단 고지).

### Run 2 — 뮤테이션 (baseline GREEN 확인 후) — **7/7 KILL**
P1 응답에서 `kb_context` 제거 · P2 근거 조립 미호출 · P3 래핑된 질문으로 매칭 ·
P4 상한/절단 고지 제거 · P5 러너가 블록 미배치 · P6 근거를 질문 뒤로 · P7 재조사 금지 문구 제거.

### Run 3 — 컨테이너 전건
`COMPOSE_PROJECT_NAME=repo make test` → **rc=0 · FAILED 0 · 6,957 tests** · ruff clean.
러너 두 사본 **sha256 동치**.

### Run 4 — 라이브 대화 전후 대조 (Environment: Windows-browser · 실제 AI 완주)
브랜치 소스만 bind-mount 한 별도 서버(18101) + 브랜치 러너. **같은 질문**을 배포본과 대조.

| | 배포본(수정 전) | 브랜치(수정 후) |
|---|---|---|
| 프롬프트 크기 | 3,535자 | **4,659자** (KB 근거 +1,124) |
| `steam_billing_log.status` | **"등록 메타데이터 어디에도 없습니다"** | **`Approved`=승인 · `Refunded`=환불 · `Succeeded`=결제성공** |
| `billingsummary.BillingType` | **"세 스키마 어느 목록에도 없습니다"** | **`Payment`=결제 · `Refund`=환불** |
| 관계 층 활용 | — | `billing_rep.steambillinglog.SequenceID → billing_web.steam_billing_log.SequenceID` 를 스스로 인용해 두 테이블 대응 설명 |
| 미정의 항목 | — | "`Approved` 와 `Succeeded` 의 단계 차이는 정의가 없어 **미확인**" (정직하게 남김) |

**답변 품질 변화가 처음으로 실측됐다** — 직전 두 cycle 은 「번들에 실린다」까지만 증명했다.

### Run 5 — 정직: 러너 갱신이 필요했다
처음 브랜치 서버에 **구버전 러너**로 붙였더니 서버는 `kb_context` 를 보냈는데 프롬프트는
그대로였다(배치가 러너 쪽 `compose_prompt` 에 있다). 서버가 `hb.stale_build` 경고를 띄워
이를 알렸고, 러너를 브랜치 빌드로 바꾸자 경고가 사라지고 근거가 실렸다.
→ 코드 주석과 FUNCTION AC-2 의 「러너 버전과 무관하게 도달」 주장을 **정정**했다.

### Run 6 — 부수 관측 (이 cycle 무관, 기록만)
Fable 5 로 라우팅된 시도 2건이 `safeguards flagged this message` 로 exit 1. 모델을 Opus 로
되돌리자 정상 완주. 프롬프트 내용이 아니라 **모델 선택**의 문제이며, 컴포저의 모델 선택이
새 대화에 승계되지 않는 동작도 함께 관측했다(별건).

### Run 7 — POST-DEPLOY (배포 후 기록)
