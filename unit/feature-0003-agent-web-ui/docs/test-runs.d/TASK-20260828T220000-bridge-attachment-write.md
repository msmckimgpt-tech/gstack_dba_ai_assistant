# TASK-20260828T220000 — 브리지 첨부 **쓰기** 결손 실증과 복원

## 1. 무엇을 확인했나

사용자 제보: "assistant가 첨부된 파일을 수정하여 버전관리는 진행하거나 새로운 첨부파일을
추가하는 동작이 가능했습니다."

브리지 전환 후 그 동작이 **말만 되고 실제로는 안 되는 상태**임을 라이브에서 확정했다.

## 2. 결손 실증 (라이브 `87d1beec`, 2026-08-28)

| 단계 | 실행 | 결과 |
|---|---|---|
| 첨부 업로드 | `POST /api/conversations/20260828031049-b13a4b02/attachments` (field=`file`) | 첨부 **id 1246** `sample.sql` v1 |
| 질문 | "첨부된 sample.sql 을 수정해줘. LIMIT 을 10에서 50으로 바꾸고, 주석을 (v2)로 갱신해서 새 버전으로 저장해줘." (`attachment_ids:[1246]`) | 실 `claude` 러너가 처리 |
| 개인 AI 답변 | `attachment-edit` 블록 포함 여부 | **True** — 규약을 정확히 지켜 만들었다 |
| 파일 | `GET /api/attachments/1246/versions` | **v1 만 존재** — 새 버전 없음 |
| 첨부 목록 | 대화 첨부 목록 | `1246 sample.sql v1 user` — assistant 생성물 0건 |
| 답변 본문 | 화면 | 블록이 strip 되지 않아 **원문 diff 노출** + "요청하신 두 곳만 수정했습니다" |

**판정**: 거짓 성공. 사용자에게는 "고쳤다는데 파일이 안 바뀐" 상태 — 기능이 없는 것보다 나쁘다.

근본 원인(코드 확정): `grep -c "_materialize_assistant_attachment" routers/ai_tools.py` → **0**.
브리지 전달 경로에 첨부 후처리가 **아예 없었다**.

## 3. P0-E 의 근거가 틀렸다

P0-E 는 이 축을 의도적으로 열지 않았고 근거는 「개인 AI 가 이 관례를 모른다」였다.
**사실이 아니다** — 규약은 `agent_core` base `SYSTEM_PROMPT`(213·229행)에 있고,
`_bridge_system_prompt` → `compose_system_prompt` 를 통해 개인 AI 에게 **이미 전달되고 있었다.**
위 실측이 그 증거다(안내 없이 형식까지 정확한 블록 생성).

빠진 것은 안내가 아니라 **서버의 처리**였다.

## 4. 조치 — 두 번째 구현을 만들지 않았다

후처리 시퀀스를 `shared/attachment_write.py` 로 올리고 **두 경로가 같이 부른다**:

| 경로 | 전 | 후 |
|---|---|---|
| ask-worker (`modules/ask.py`) | 자체 구현 ~150행 | 정본 호출 |
| 브리지 (`routers/ai_tools.py`) | **없음** | 정본 호출 |
| 동기 inproc (`_ask_impl`) | 자체 구현 | **그대로**(응답 shape·step 기록이 얽힘 — 잔여로 명시) |

`ops` 파라미터로 web 원시연산 네임스페이스를 받는다 — 그래서 shared 가 web 을 끌고 오지
않고, worker 테스트의 fake 주입도 **정본을 그대로 시험**할 수 있다.

## 5. 회귀 (신규 12건 · 기존 9건 강화)

`unit/feature-0043-external-llm-bridge/tests/test_bridge_attachment_write.py`

- **배선 3** — 전달 경로가 후처리를 실제로 부르는가 · 메시지 저장 **뒤**인가 · 회수 store 에
  정리본이 가는가. (헬퍼만 시험하면 "아무도 부르지 않는 세계" 가 통과한다)
- **한 벌 3** — worker·브리지가 같은 함수를 쓰는가 · 브리지가 materialize/strip 을 직접
  부르지 않는가 · `app.X` 로 노출되는가
- **거짓 성공 금지 8** — fence 계수(인용·들여쓰기 제외) · 사유 있는 미전달 고지 · 사유 미상
  건수 고지 · **부분 실패**(2건 중 1건) 고지 · 도구 전달분이 블록 실패를 상쇄하지 못함 ·
  cap 합산 · `answer_persisted` 게이트 · 실패 run 은 skip 하되 strip
- **중복 안내 금지 1** — 러너 프롬프트가 규약을 재정의하지 않는다

기존 `test_ask_worker_attachment_postprocess.py` 9건은 **약화하지 않고 강화**했다: fake 가
정본 함수에 stub 원시연산을 물리므로, 이제 그 단언들이 **실제 조립**(순서·cap 합산·미전달
계수·strip 정책)을 검증한다.

## 6. 병렬 대화 동시 진행 — 교차오염 없음 (같은 세션 관측)

러너(`--workers 3`)가 두 task 를 **동시에** 처리하고 각 답변이 자기 대화에 앉았다.

| task | 대화 | 질문 | 답변 |
|---|---|---|---|
| `t_0SYezZmS8g_duN0g` | `…031049-b13a4b02` | sample.sql 수정 | 첨부 편집 답변 |
| `t_7_genWa0SGQcg4c3` | `…032010-7607846a` | 접근 가능한 데이터소스 | `mssql-dk-dev` 1건 |

두 답변 모두 `제출 완료 (대화 반영=True)`, 내용이 각자 질문과 일치 — 섞이지 않았다.

## 7. 남은 것

- 배포 후 같은 첨부 시나리오 재실행(1246 → v2 생성 확인, `attachment-new` 생성 확인)
- 동기 inproc 경로의 세 번째 구현 수렴(별도 cycle)

## 8. 배포 전 라이브 검증 (bind-mount, 2026-08-28)

브랜치 코드를 `docker cp` 로 `repo-web-a-1`/`repo-web-b-1` 에 주입하고 재기동해 **머지 전에**
실동작을 확인했다(§ 미머지 브랜치 무접촉 검증). 실 `claude` CLI 러너(`--workers 2`) 연결.

| # | 시나리오 | 결과 |
|---|---|---|
| 1 | 첨부 1246 수정 + `daily_count.sql` 신규 요청 | 첨부 **1247**(sample.sql, assistant) · **1248**(daily_count.sql, assistant) 생성. 답변에서 블록 제거됨 |
| 2 | `attachment-edit`(source=1246) 명시 요청 | 첨부 **1249** 생성 + 답변에 `📎 수정본 sample.sql (v1)` 마커 |
| 3 | assistant 계보 편집(source=1249) | **1249 v1 → 1251 v2** — 버전 체인 연장 확인 |
| 4 | 실 Windows 브라우저 화면 판독(PB-0008) | 블록 헤더(`{"source_attachment_id"`) **미노출** · 첨부 칩 표시 · 📎 전달 마커 4종 · 거짓 실패 고지 없음 |

**시나리오 2의 v1 은 결함이 아니다.** source 1246 은 **사용자 업로드** 첨부이고, 2026-08-06
결정에 따라 assistant 편집본은 사용자 계보에 끼어들지 않고 **새 root 체인의 v1 로 분기**한다
(사람이 올린 최신본을 AI 가 supersede 하지 않는다). 버전 연장은 **assistant 계보에서** 일어나며
시나리오 3이 그것을 실증한다(v1 → v2).

**PB-0008 판독 방법 주의**: 렌더된 코드블록은 innerText 에 ``` 를 남기지 않으므로 fence 문자로
판정하면 **거짓 음성**이 난다. 블록 헤더 JSON(`{"source_attachment_id"`)과 `pre/code` 의 언어
클래스를 함께 봤다. `ORDER BY level DESC` 5건은 AI 가 의도적으로 보여준 ```diff 이며 설계대로다
(변경점은 diff, 전문은 첨부).

- Environment: Windows-browser (PB-0008 relay, Chrome/151.0.7922.170, `https://localhost/?conversation=20260828031049-b13a4b02`)
- 대상 배포본: 미머지 브랜치 `ai/claude/feature-0043-bridge-attachment-write` (bind-mount)
