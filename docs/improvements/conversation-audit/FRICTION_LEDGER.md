# FRICTION_LEDGER — conversation_audit 마찰 원장 (단일 정본)

`/_dqa:conversation_audit` 의 진행 원장(§C5). 항목 = `friction-id` 1개. **content·PII·원본 데이터 값 비전재**(집계 수치·익명 라벨·마스킹만). status 는 측정으로만 `verified` 로 닫힌다(거짓 done 방지). 별도 큐 파일 신설 금지 — 이 파일이 진행 원장.

status enum: `triaged`→`fixed:undeployed`|`fixed:deployed:unverified-live`|`fixed:deployed:verified`|`deferred`|`report-only`|`rejected`|`needs-human`|`blocked:<reason>`|`awaiting-merge:PR#<n>`|`regressed`.

---

## FR-redteam-first-pass-unabortable — fixed:deployed:unverified-live (L7↔L2 구조; 자가 검증 대기 구간에 사용자 탈출구·진행 표시 부재)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트(신규 **25** PASS + headless **13** PASS ·
  기존 red-team 127 PASS · `make test` 전량 exit 0 · ruff clean · 역검증 **4종** 판별력 확인) +
  **§18.8 backend/qa 패널 BLOCKING 3 · MAJOR 12 전건 흡수**(MINOR 12 중 8 흡수 · 4 는 선재/범위 밖
  명시) + **배포 완료**(2026-08-07, PR #1195 merge main `6b0f50c0` → `make deploy-web` 전체 스코프,
  soak 통과·롤백 0, gateway 드리프트 0). 병렬 세션 머지로 rebase 1회(원장 헤더 충돌 → union 해소:
  신규 항목 유지 + 다른 세션의 `verified` 상태 채택), rebase 후 회귀 재실행 exit 0 ·
  verify-completion(post-commit) PASS.
  **5서비스 GIT_COMMIT=`6b0f50c0` running/healthy**(web-a·web-b·ask-worker·insight-worker·ops-scheduler).
  **배포본 런타임 실증(ask-worker)**: `_await_review_interruptible` 적재 True · 출하 상수
  (poll 1.0 / poll_max 3.0 / tick 15.0 / backoff 2.0 / tick_max 120.0 / grace 5.0 / ratio 0.1 /
  abort_grace 0.5) · **양쪽 배선 2회** True · `verify_incomplete` True · `review_wait_giveup` True ·
  `copy_context` True. web-a 서빙 `admin.js` 에 `review_wait_giveup` 3건 · `리뷰 미완료` 1건.
  web /healthz `status=ok · mysql_ok · pg_ok · git_commit=6b0f50c0`.
  **라이브 대화 실측 미수행** → `unverified-live`.
- **source**: 사용자 명시 호출 `/_dqa:conversation_audit "안녕 처음 사용하는데 리뷰 가능할까?"`
  (2026-08-07) — "해당 대화에서 assistant의 응답이 더 이상 진행되지 않는 이슈".
- **last_seen**: 2026-08-07 · **seen_count**: 1 · **seen_distinct_conv**: 1(보고) / 아래 corroboration 별도
- **modality**: 1:1 · **product_id(마스킹)**: P-119 · **conv(마스킹)**: `…226e27aa` · run `…bfc5ec3e`
  · 계정(마스킹) A-27, **첫 사용 사용자**(대화 4건 전부 단발)
- **symptom_confidence**: high (사용자 명시 보고 + DB 실측) ·
  **rootcause_confidence**: high (duration_breakdown + redteam_reviews + llm_usage + 코드 file:line 삼각측량)
- **suspected_layers**: **L7**(표면 — 진행 표시가 갱신되지 않아 "멈춤"으로 읽힘) ↔
  **L2**(계약 — 리뷰어 대기 구간이 취소·'즉시 답변'을 듣지 않음). L6(리뷰어 호출 자체의 무응답)은
  **직접 유발 조건이나 근본 아님**(아래 분리).
- **증상(signal)**: `E-USR` 명시 보고 + `I-SIL` 침묵 이탈(첫 인사 턴 이후 대화가 2메시지로 종료).
- **실측(정직 분리 — 무엇이 느렸나)**:
  - 답변 본문 생성 **9.6초**(`inference_detail.llm_ms=9644`, `tool_calls=0`, `llm_calls=1`).
  - 총 소요 **312.0초**(`total_ms=312034`), 그중 **red-team 300.1초**(`redteam_ms=300086`).
  - `redteam_reviews` #283: `verdict=error` · `stop_reason=review_error` · `latency_ms=300038` ·
    `reasoning_level=max`. `llm_usage` 에 redteam 행 **없음** = 응답을 아예 받지 못하고 상한까지 대기.
  - 리뷰어 정상 지연은 **p50 20.4초 / max 54.5초**(14일, haiku 209건) → 300초는 분포 밖.
  - 운영 설정 `REDTEAM_TIMEOUT_SEC=300`(콘솔 최댓값). 즉 **1회 실패 = 사용자 5분 대기**.
- **confirmed_root_cause**: **리뷰어를 기다리는 구간에 사용자 탈출구가 없었다.**
  `redteam.py` `orchestrate_review` 의 `abort_fn`(취소·'즉시 답변')과 `progress_fn` 은 **반복 수정
  루프에만** 걸려 있고, 최초 검증 패스(`run_review`)와 재검증 호출은 상한까지 블로킹하며 어떤
  신호도 보지 않았다. `agent_core.py` 쪽도 red-team 진입 전(6473)과 재도출 내부(6631) 사이에
  취소 체크가 없다. 그래서 (a) 화면은 "답변을 자가 검증하는 중"에서 정지 (b) 버튼이 듣지 않음
  (c) 이미 완성된 답변이 300초 인질이 됐다. 코드 주석이 "사용자는 언제든 그 시점 답변을 받을 수
  있다"고 선언하는데 **첫 패스가 그 계약의 예외**였다. 재발경로 = **ux contract + 구조**.
  - **L6(리뷰어 300초 무응답)은 별개 축**: 그 시각 게이트웨이는 한산했고(동시 LLM 호출 0),
    컨테이너 로그는 이후 재시작(03:00Z)으로 소실돼 공급자측 원인은 **미확정(inconclusive)**.
    다만 그 원인이 무엇이든 **사용자를 5분 붙잡는 것은 별개의 결함**이라 이번 봉인 대상은 탈출구다.
- **corroboration**: **structural**(30일, `duration_breakdown` 보유 assistant 턴 347건 기준)
  - red-team 이 **총 응답시간의 과반**인 턴 **52건**
  - `redteam_ms > 120초` **19턴 / 15 대화** · `> 60초` 35턴
  - 리뷰 `verdict=error`(대기만 하고 이득 0) **12 / 247**, `latency ≥ 290초` **11건**
  - 도구 0회의 사소한 턴 40건 중에도 60초 초과 9건 → 인사·스몰토크도 예외가 아니다.
- **거짓양성 기각(`refuted`)**: F1 무해 아님(첫 사용자 이탈) · F3 기수정 아님(`git log` 확인) ·
  F4 의도된 동작 아님(위 계약 위반) · 보안 가드와 무관.
- **triage**: S=5 · F=4(structural) · L=4 · C=5 · R=3 → **32**, disposition=**fix-now**.
  위험등급 **Major**(§12.3 코어 LLM 전달 경로) → attended human-decision. 사용자가 봉인 범위
  **A(사각지대 해소만)** 명시 선택 — 타임아웃 값 조정·리뷰 스킵 게이팅은 **범위 밖**.
- **봉인**: `_await_review_interruptible` — 리뷰어 1패스를 워커 스레드에 맡기고 1초 주기 폴링으로
  ① 중단 신호 즉시 반영 ② 15초 주기 진행 표시(경과/상한/탈출 안내). 중단 감지 시 0.5초 유예로
  **반환 직전인 판정은 살리고**(콘솔의 "무엇이 남았는지" 보존), 넘기면 버리고 초안 즉시 전달.
  최초·재검증 **양쪽** 배선. `verdict` enum 불변 — 중단은 `stop_reason="aborted"` 로만 구분.
- **초판 정정 3건(정직)**:
  ① 첫 구현은 "진입 전 abort 면 리뷰 skip" 이었으나 그러면 중단 시에도 findings 를 기록하던 기존
     관측 계약이 깨진다 — 기존 회귀 테스트가 FAIL 로 잡아냈다. 유예 방식으로 대체.
  ② **보안 채널 검증 중 발견한 회귀**: 호출을 워커 스레드로 옮기면 ContextVar 가 전파되지 않아
     `_record_llm_usage` 의 `get_active_datasource()` 폴백이 빈 값을 보고 `llm_usage.target_scope`
     가 통째로 NULL 이 된다(라이브 14일 redteam **295건 중 218건**이 이 폴백으로 채워져 있었다).
     `contextvars.copy_context().run` 으로 수정 + 회귀 테스트. `llm.py` 에 같은 함정 주석이 이미
     있었다 — **스레드 경계를 옮기는 변경의 표준 점검 항목**.
  ③ 초판 문서가 "콘솔 라벨('사용자 즉시 답변/취소')이 이미 있으니 그대로 쓴다"고 적었으나
     **거짓이었다** — 그 라벨은 `unresolved>0` 분기에서만 렌더되는데 이 경로는 `unresolved=0` 이라
     구조적으로 도달 불가였고, 콘솔은 중단을 "리뷰 수행 실패"로 표시하며 사용자 중단이 리뷰어
     오류율(이 감사가 근거로 쓴 그 지표)을 부풀린다. admin.js 수정으로 흡수.
- **§18.8 패널 흡수(가장 중요한 것)**: 초판 테스트는 대기 상수를 낮추는 autouse fixture 를 써서
  **`_REVIEW_ABORT_POLL_SEC=1.0 → 300.0` 뮤턴트가 전 스위트를 통과**했다 — 그 값이 곧 이 감사가
  고치려던 인시던트 그 자체다(저장소의 알려진 `test-env-override-skip-vacuous-pass` 패턴).
  fixture 를 autouse 해제하고 **출하 값을 직접 읽는 상수 계약 테스트**를 세웠다. 그 밖에
  ① 대기 포기 시점이 리뷰어 상한과 무관해도 통과(운영 결과 = p50 20초 리뷰를 6초에 전부 버리고
  리뷰어 실패로 기록) ② **재검증 중단이 '검증하지 않은 결함' 고지를 사용자 답변에 찍음**(직전
  판정은 *수정 이전* 답변에 대한 것) ③ abort 폴링이 메모리 DB 왕복을 ~300배로 증폭 ④ 진행 표시가
  tick 마다 DB step 행 INSERT ⑤ verify 쪽 progress 배선만 지워도 통과(고치려던 비대칭의 재생산)
  — 전건 흡수.
- **fix**: `CHG-20260807T130000-redteam-abortable-review`(TASK-20260807T130000-redteam-abortable-review) /
  **코드 거주 primary `feature-0002-agent-core`**(기능 소유 `feature-0021-redteam-review` — cross-ref only).
- **rc_ids**: RC-1(첫 패스 무-탈출구) · RC-2(재검증 무-탈출구) · RC-3(진행 표시 미갱신) ·
  **batch-id**: B-20260807T130000-redteam-abortable-review
- **범위 밖(deferred/watch)**: ① `REDTEAM_TIMEOUT_SEC=300` 운영값이 성공 분포(p50 20초) 대비 과대
  ② 도구 0회·검증 대상 사실이 없는 인사 턴에도 `max` 강도 리뷰가 도는 게이팅 ③ 리뷰어 호출
  300초 무응답의 공급자측 원인(로그 소실, 별 트랙) ④ '즉시 답변' 버튼의 권한 게이트
  (`conversation.finalize.own`) — 권한 없는 사용자에겐 탈출구 자체가 없다.
- **라이브 실측 필요분(§정직)**: ① 실제 대화에서 대기 중 '즉시 답변'·취소가 즉시 듣는지
  ② 진행 표시가 실제로 갱신돼 보이는지(실 브라우저) ③ 관리 콘솔 'AI 추론' 탭에서 중단된 리뷰가
  **"리뷰 미완료 — 사용자 '즉시 답변'/취소"** 로, 대기 포기가 **"리뷰어 응답 지연 — 대기 포기"** 로
  뜨는지(PB-0008 — 이 조합의 행은 배포 후에야 생기므로 배포 전 실화면 검증 불가, headless 13 PASS 로
  로직만 고정) ④ 배포 후 `redteam_ms > 120초` 턴 비율과 `stop_reason IN ('aborted','review_wait_giveup')`
  발생 추이 — 다음 audit 의 corroboration 재측정 대상.
- **선재 결함 이월(이번 범위 밖)**: `verify_error` 분기도 재검증 미완료인데 직전(수정 이전) BLOCK 을
  `unresolved` 로 세어 같은 오귀속을 낸다(§18.8 backend 패널이 "둘 다 정리할 가치" 로 지적). 이번
  승인 범위(A=사각지대 해소)에 없어 손대지 않았다 — 별 cycle.

## FR-attach-delivery-truncated-by-output-cap — fixed:deployed:verified (L6↔L2 구조; 전달 payload 가 답변 출력 예산을 잠식)

- **status**: `fixed:deployed:verified` — 코드/테스트(신규 **56** PASS[33+23] · **뮤테이션 9/9 KILLED** ·
  컨테이너 정본 회귀 실패 0 · ruff clean) + §18.8 security/backend+qa 패널 **BLOCK → [P1] 4 · [P2] 9 ·
  [P3] 6 전건 흡수** + **배포 완료**(2026-08-06, PR #1178 merge main `d04ab2f2` → `make deploy-web`
  전체 스코프, soak 통과·롤백 0, **4서비스 GIT_COMMIT=d04ab2f2 running/healthy**).
  병렬 세션 머지로 rebase 1회(FUNCTION.md 말미 append 충돌 → union 해소), rebase 후 컨테이너 정본
  회귀 재실행 실패 0.
  **배포본 런타임 실증(ask-worker)**: 도구 노출 True · `_TOOL_HANDLERS` 라우팅 True · datasource-free
  True · `_bind_tool_delivered_attachments` 적재 True · 절단 감지 + latch True · 패치 정상 적용 ·
  **잘린 패치 거부**(선언 -3/+3, 실제 -1/+1) · **문맥 없는 삽입 거부** · DELIVERY FACTS floor True.
  **라이브 대화 실측 완료(2026-08-07, `fixed:deployed:verified`)** — 배포본 web UI(실 Windows Chrome,
  PB-0008)에서 4파일 동시 갱신을 1턴에 요청해 전 축을 실측했다. 상세는
  `unit/feature-0002-agent-core/docs/test-runs.d/REV-20260807T130000-attach-delivery-live.md`.
  - **도구 채택 4/4** — 모델이 첫 라이브 사용에서 `update_attachment` 를 파일당 1회씩 호출(steps 4·5·6·8).
  - **다중 파일 완주 4/4** — 도구 응답의 러닝 카운터가 1→2→3→4 로 증가, 오류 0.
  - **답변↔실재 일치** — 답변이 주장한 "4개 파일 모두 갱신"이 저장소 실제와 일치(원 마찰의 소멸 조건).
  - **다운로드 칩 렌더 4/4**(패널 P1) — `.message-bubble-attach-chip.has-download` 4개,
    `v2 · AI 수정` 배지 + 다운로드 화살표. 스크린샷 evidence 첨부.
  - **패치 적용 4/4 1회차 성공** — 다운로드 실물 대조: 122줄(SELECT 120줄 전량 보존),
    삽입 위치가 정확히 2번째 줄, 마커 1회만, CRLF 드리프트 없음.
  - **★ completion_tokens 분리 실증**(사용자가 요구한 구조 조건) — 4×7KB 전달의 총 답변
    completion_tokens 는 **1,973**(1486+269+218). 본문이 답변 출력창에 실리지 않음을 수치로 확인.
- **source**: 사용자 보고(2026-08-06) — "assistant 가 모든 첨부파일들을 갱신했다고 전달받았지만
  정작 갱신된 첨부파일은 하나 뿐". 대화 제목 `파일 개선사항 지속적 갱신`.
- **last_seen**: 2026-08-06 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **modality**: 1:1 · **product_id(마스킹)**: P-97 · **conv(마스킹)**: `…1d8ed346` · run `…2fd932dc`
- **symptom_confidence**: high (사용자 보고 + DB 실측) · **rootcause_confidence**: high (토큰 실측 +
  코드 file:line + 첨부 테이블 대조)
- **suspected_layers**: **L6**(출력 상한 — 응답이 잘림) ↔ **L2**(도구/전달 계약: 절단 미감지 · 전달
  결과 미피드백). L7 은 무관.
- **증상(signal)**: `E-USR` 명시 보고 + `E-AST` 허위 완료 선언. 답변 서두 "…6개 파일을 전부
  갱신했습니다" + 파일별 표/diff, 말미는 raw SQL **중간 절단**.
- **confirmed_root_cause**: **전달 payload 가 답변 서술과 같은 출력 창을 공유한다.**
  `completion_tokens = 100,000`(= `agent_max_output` 상한 정확히 도달). 파일 전문 6개(하나 8.5KB)를
  한 응답에 담다 잘렸고, 완성된 `attachment-edit` 블록은 첫 파일뿐 → 새 버전 1건(878)만 생성.
  요약이 **먼저** 쓰였기에 절단 후에도 "전부 갱신" 문장이 남았다.
  부수 사실: `_ASSISTANT_EDIT_COUNT_CAP=5` 라 6건은 절단이 없었어도 하나는 못 갔다.
  왜 아무도 못 잡았나 — (a) `finish_reason` 을 코드 **어디에서도 읽지 않았다**(grep 0건) (b) red-team 은
  materialize **이전**에 도는 구조라 실제 전달 결과를 볼 수 없고, 초안의 블록 수조차 사실로 받지 못했다.
  재발경로 = **구조**(예산 공유) + model limit.
- **사용자 지시로 방향 전환(중요)**: 초판 제안은 감지(finish_reason)·리뷰어 대조·순서 변경 3종이었으나
  사용자가 "첨부 수정은 completion_tokens 과 별개로 작동해야 한다. 구조개선을 검토해달라" 고 지적.
  셋 다 **예산 공유 전제를 남긴 증상 대응**이었고(파일이 더 많거나 크면 순서 변경도 깨진다) 구조 개선으로
  재설계했다. 승인 범위 **①+②**.
- **봉인**: ① `update_attachment` 도구(파일당 독립 출력 창 + 성공/실패 즉시 피드백 + 스코프·가드 공유 +
  run 상한 20) ② `patch`(unified diff) 전달(fail-closed 적용기 — 선언 길이 권위·문맥 없는 hunk 거부·
  모호 다중일치 거부·전체 미적용·줄바꿈 보존) ③ `finish_reason` 절단 감지(초안 확정 시 latch → 사용자
  경고 + 리뷰어 사실) ④ red-team `DELIVERY FACTS`(허위 완료 `honesty` BLOCK, floor 프레이밍으로 오탐 가드)
  ⑤ 프롬프트: 도구 우선 · 성공 응답 없인 주장 금지 · 전달 먼저 요약 나중 · 블록 경로는 폴백 강등.
- **§18.8 패널 BLOCK 흡수(가장 중요한 것)**: 초판은 도구로 만든 첨부를 **답변 메시지에 바인딩하지
  않아** 다운로드 칩이 하나도 뜨지 않았다(`MetaJson.message_id=0` → `_load_assistant_attachments_by_message`
  가 버림). 파일은 생성되고 이전 버전은 supersede 되는데 사용자에겐 아무것도 안 보이고, 하필 도구
  결과와 절단 경고가 "칩으로 확인하세요" 를 가리켰으며 `delivered=6` 이 리뷰어에게 사실로 제시돼
  **허위 완료를 리뷰어가 승인**하는 구조였다 — 고치려던 gap 의 한 층 아래 재생산. 또 패치 적용기가
  **무음 오적용 3종**(문맥 없는 삽입 한 줄 앞 · 잘린 패치 부분 적용 후 성공 반환 · 후행 산문 파일 기록)을
  냈고, 절단 경고는 red-team revise 가 지웠다(경고가 필요할수록 확실히 사라지는 자기무력화).
- **corroboration**: 단일 대화이나 **구조적**(전달 payload 가 예산을 공유하는 한 파일 수·크기에 따라
  재발 확정). disposition=fix-now — 근본이 코드 file:line confirmed + 사용자 명시 지시.
- **fix**: `CHG-20260806T160000-attach-delivery-tool`(TASK-20260806T1600) /
  **코드 거주 primary `feature-0002-agent-core`** + secondary cross-ref `feature-0003-agent-web-ui`
  (칩 바인딩 `_bind_tool_delivered_attachments`) / `REV-20260806T160000-attach-delivery-tool`.
- **rc_ids**: RC-1(예산 공유 구조) · RC-2(절단 미감지) · RC-3(전달 결과 미피드백) ·
  **batch-id**: B-20260806T160000-attach-delivery-tool
- **범위 밖(deferred/watch)**: ① 짧은 `content` 가드(모델이 절단된 preview 를 읽고 전문이라 착각하는
  경우 — 선재, 별 항목) ② 턴당 최대 버전 수가 블록 5 + 도구 20 = 25 로 늘어난 점(용량 상한으로만 유계)
  ③ 도구 경로 audit 에 request IP 부재(워커 경로와 동일, 선재).
- **라이브 실측 필요분(§정직)**: ① 모델이 실제로 도구를 채택하는지 ② 다중 파일 전달이 완주하는지
  ③ **다운로드 칩이 실제로 뜨는지**(패널이 잡은 결함이라 최우선) ④ 패치 경로 적용 성공률.

## FR-redteam-attach-excerpt-cap-false-grounding-block — fixed:deployed:unverified-live (L2↔L1; 리뷰어 발췌가 head-only 라 캡 밖 근거가 '무근거'로 보임)

- **status**: `fixed:deployed:unverified-live` — 2026-08-07 라이브 실측 중 **부수 발견**(원 마찰
  검증 턴에서 재현) → 사용자 지시로 수정. **배포 완료**(PR #1196 merge main `4c7a8f27` →
  `make deploy-web` 전체 스코프, soak 통과·롤백 0, 4서비스 `GIT_COMMIT=4c7a8f27` running/healthy).
  병렬 세션 머지로 rebase 1회(import 블록 union 해소) 후 전량 회귀·뮤테이션 **재실행**.
  **배포본 런타임 실증(ask-worker)**: 원 마찰(꼬리 근거)이 verbatim·패러프레이즈·초안없음
  **셋 다** 리뷰어에게 도달 · 예산 소진 1,200/1,200(구 동작 하한 보장) · 1줄 minified JSON 이
  `lines shown in full: none` 으로 **허위 완전성 주장 없음** · 761자 첨부 5개에서 **거짓 FULL 라벨 0**
  + 전 파일 고지 · 면책 경계 4종 프롬프트 탑재 확인.
  **라이브 대화 실측 미수행** → `unverified-live`(정확한 답변에서 경고 배너가 실제로 사라지는지는
  다음 실사용 턴에서 측정).
- **source**: 자체 실측(2026-08-07). 사용자 보고 아님.
- **last_seen**: 2026-08-07 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **symptom_confidence**: high · **rootcause_confidence**: high(코드 위치 + 라이브 런 삼각측량)
- **suspected_layers**: L2↔L1
- **증상**: 첨부 파일의 **뒤쪽 영역**을 근거로 한 정확한 답변에, red-team 이 grounding 축
  BLOCK("파일을 읽은 근거가 없습니다")을 걸고 → 수정 실패 → 사용자에게
  `⚠️ 내부 자가 검증 미해소` 배너가 붙은 채 전달된다. **답변 내용은 옳았다.**
- **confirmed_root_cause.location** (3중):
  1. `unit/feature-0002-agent-core/src/modules/redteam.py` — `build_attachment_digest()` 의
     `excerpt = _strip_review_sentinels(body)[:_ATTACH_PER_FILE_CAP_CHARS]`(파일당 **1200자
     head-only** 절단). 캡 밖 영역을 근거로 삼은 답변은 리뷰어 시야에서 근거가 사라진다.
  2. 같은 함수의 산문 가드("Excerpts are TRUNCATED — absence here is not proof …")가 **실효
     없었다** — 리뷰어가 그 문장을 받고도 정확히 그 오판(BLOCK)을 냈다. 산문 경고로는 안 막힌다.
  3. `_REDERIVE_ALWAYS_AXES=("sql",)` · `_REDERIVE_LEVEL_GATED_AXES=("completeness",)` —
     **`grounding` 은 도구 재추론 대상 축이 아니다**. 그래서 "read_attachment 로 읽어라"는
     fix_hint 를 텍스트 재작성 패스가 이행할 방법이 원천적으로 없다 → `revise_failed` 구조적 확정.
- **라이브 증거**: run `20260807040816-3a3b6f52` — `verdict=revise · block_count=1 ·
  revision_applied=false · revision_rounds=0 · unresolved_block_count=1 ·
  stop_reason=revise_failed`. 대상 첨부 7,046자(캡 1,200자의 5.9배), 변경점은 마지막 줄.
  재작성 시도는 실제로 호출됐다(`llm_usage` agent p=47138 **c=425**) — 과거
  prefill 결함(c=3)과는 **다른 원인**이므로 그 회귀가 아니다.
- **영향**: 대용량 첨부를 다루는 정확한 답변마다 경고 배너가 붙는다. 배너는 fail-safe(정직)
  방향이라 **위해는 없으나**, 반복되면 배너 자체가 신뢰를 잃어 진짜 BLOCK 을 가린다(경보 피로).
- **후보 방향(미결정)**: ① 발췌를 head-only 대신 **답변이 인용한 구간 중심**으로 선택
  ② `grounding` 을 rederive 적격 축에 포함(도구로 실제 읽어 해소 가능하게)
  ③ 절단 사실을 산문이 아닌 **구조적 사실**(캡·총길이·미표시 구간)로 제공.
- **fix**: `CHG-20260807T160000-redteam-attach-excerpt-anchoring`
  (`unit/feature-0002-agent-core/src/modules/redteam.py`) — **봉인 3축**:
  1. **발췌를 초안이 인용한 구간에 앵커**(`_draft_probes` + `_select_excerpt_spans`). 예산(파일당
     1,200자)은 **그대로 두고 쓰는 위치만** 바꿨다 — 캡을 키우는 것은 더 큰 파일에서 같은 실패가
     재발하므로 오답이다. 앞머리 창은 파일 정체성 확인용으로 항상 유지.
  2. **절단 표기를 산문 → 구조적 사실**: `[PARTIAL EXCERPT — SHOWN lines A-B of N; NOT SHOWN
     lines C-D (unknown to you, not absent)]`. 기존 산문 경고("absence here is not proof")를
     받고도 리뷰어가 정확히 그 오판을 냈다는 것이 실측이라, 사실 줄에 직접 붙였다.
     `[FULL FILE SHOWN]` 일 때만 부재 추론이 허용된다는 것도 명시.
  3. **리뷰어 규칙**(`REDTEAM_REVIEW_PROMPT`): 기존 규칙은 본문 없는 "ALSO ATTACHED" 파일만
     다뤄 **본문이 실렸으나 발췌가 잘린 파일**에는 적용되지 않는 것으로 읽혔다. 그 구멍을 막고,
     "no tool runs" 를 첨부 근거 부재로 읽지 말 것도 추가(첨부 본문은 도구가 아니라 프롬프트로
     도달한다). **과교정 방지**: 실제로 보여준 줄과 **모순되는** 주장은 여전히 BLOCK.
- **§18.8 적대 패널(backend+qa)이 초판을 반려 — BLOCKING 4 · MAJOR 4 · MINOR 7 전건 흡수**.
  판정 요지: *초판 수정이 원 버그를 세 경로로 재도입했다.* ① 앞머리 420자만 쓰고 남은 780자를
  probe 히트에만 배정해 **히트 0이면 버렸다**(한국어 답변 ↔ 영문 파일은 verbatim 매칭이 구조적
  0건 → 전달량 1,200→420자, 미탐 62%→87%) ② span 은 문자인데 coverage 는 줄이라 1줄 minified
  JSON 이 `NOT SHOWN lines none`(=다 봤다)으로 **거짓 완전성**을 진술 ③ 파일당 캡으로
  `[FULL FILE SHOWN]` 을 붙인 뒤 총예산이 본문을 잘라 "전문을 봤는데 없다"는 **정당화된** BLOCK 을
  만듦 ④ "no tool runs 는 근거 부재 아님" 규칙이 `ALSO ATTACHED`(본문이 프롬프트에 없고 도구로만
  도달)까지 덮어 **날조 탐지가 가장 확실한 경우를 보호**.
  해소: 남은 예산 전액을 앞머리 연장에 소진 + 꼬리 창 예약(`sum(span)==min(본문,캡)` 불변식) ·
  문자 기준 coverage + 완전히 보인 줄만 SHOWN · 블록 단위 적재(초과 시 ALSO ATTACHED 강등) ·
  면책을 발췌 있는 파일로 한정 + `[FULL FILE SHOWN]` 에선 부재가 증거 · 상류 절단은 `M+` 하한 +
  `SOURCE ALSO TRUNCATED` · 모순 규칙 축 한정 · 본문의 coverage 마커 위조 중화 · sanitized 통일.
- **검증(패널 반영 후)**: 신규 39건 + 기존 계약 1건 강화 · **뮤테이션 24종 중 23 KILLED**
  (1건은 등가 뮤턴트로 근거 기록) · 호스트 전량 회귀 3,998 collected(실패는 선재
  `test_share_redaction_invariant.py` 7건뿐, `git stash` 로 확인) · ruff clean ·
  **배포본 컨테이너 재현**(수정 전 마커 부재 → 수정 후 포함) · 패널이 제시한 실패 입력
  (1줄 minified JSON · 761자 첨부 3~5개 · 64KB 상류 절단 · sentinel 폭탄 · 마커 위조 본문 ·
  한국어 패러프레이즈 초안)을 그대로 재현해 전부 해소 확인.
  뮤테이션이 테스트 결함을 **5회** 적발했다 — 모듈 grep 이 규칙 삭제를 가림 · probe 미매칭
  fixture · 창 병합으로 예산 상한 미발동 · 꼬리 창이 대소문자 폴백을 가림 · 예산 소진이 개수
  상한을 가림. 매번 프로덕션이 아니라 **테스트**가 결함이었다.
- **정직**: 초판에서 "예산 불변 · 회귀 없음" 을 문서 4곳에 적었으나 **거짓이었다**(캡은 불변,
  전달량은 1/3). 패널이 반증했고 전부 정정했다. 노출 경계만 보고 안전을 결론내면 **검출력 축**을
  놓친다는 교훈을 SECURITY §41 에 남겼다.
- **rc_ids**: RC-LM1 · **batch-id**: redteam-attach-excerpt

## FR-datasource-eager-connect-blocks-datasource-free-turn — rejected (의도된 동작 — 사용자 판단 2026-08-07)

- **status**: `rejected` — **의도된 동작**(사용자 판단 2026-08-07). 아래 관측·근본원인은 사실이나,
  이를 결함으로 보지 않기로 했다: **datasource 연결이 성립하지 않은 상태에서 작업을 수행하면
  assistant 답변 품질을 보증할 수 없으므로 차단하는 방향이 옳다.** 제안했던 lazy 연결·degraded
  진입(①②③)은 전부 채택하지 않는다 — 부분적으로만 접지된 답변을 내보내는 것이 조용한 오답의
  원천이 되기 때문이다. 재발견 시 이 항목으로 합류하고 재진단하지 않는다(§C5 rejected).
- **source**: 자체 실측(2026-08-07). 사용자 보고 아님.
- **last_seen**: 2026-08-07 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **symptom_confidence**: high · **rootcause_confidence**: high(코드 위치 + 실패 런)
- **suspected_layers**: L8↔L2
- **증상**: 첨부 파일만 편집하면 되는 요청(=datasource 를 전혀 쓰지 않는 턴)이, 대화에 바인딩된
  제품의 datasource 가 회로차단(`DatasourceCircuitOpen`) 상태면 **도구 루프에 진입도 못 하고**
  런 전체가 중단된다. 사용자에게는 "데이터소스 응답 지연" 안내만 남는다.
- **confirmed_root_cause.location**: `unit/feature-0002-agent-core/src/agent_core.py` —
  `run_agent` 가 런 시작 시 primary datasource 를 **선연결**하고, 실패 시 `return result` 로
  즉시 종료한다(멀티 datasource 분기 ~5767-5779, 단일 분기도 동형). 이 턴이 datasource 를
  필요로 하는지와 무관하게 걸리는 **무조건 전제조건**이다.
- **라이브 증거**: `ask_jobs` id=615 — `status=error`, `steps: []`, `answer: ""`,
  error=회로차단 사용자 문구. 동일 요청을 **로컬 도달 가능한 제품(MV)** 으로 바꾸자 즉시 성공
  (id=616, `update_attachment` 4회). 즉 요청 자체는 datasource 와 무관했다.
- **영향**: 사외 datasource 가 넓게 불안정한 시간대에는 첨부 편집·문서 질의 같은
  **datasource-free 작업까지 전부 불가**해진다. 실측 시점 워커 로그에 `conn_health down` 이
  16개 scope 이상 동시 발생.
- **후보 방향(전부 기각)**: ~~① 선연결을 lazy 로 이동~~ ~~② degraded 진입 + datasource-free 도구만
  노출~~ ~~③ "조회 불가·첨부 작업 가능" 안내~~ — 셋 다 "접지되지 않은 상태에서의 답변"을 허용하는
  방향이라 품질 보증 기준과 충돌한다. **다시 제안하지 말 것.**
- **fix**: 해당 없음(기각) · **rc_ids**: RC-LM2 · **batch-id**: 해당 없음

## FR-read-attachment-preview-looks-partial — fixed:deployed:unverified-live (L7 표시 오인 + L2 완전성 계약 부재)

- **status**: `fixed:undeployed` — 코드/테스트(신규 **17** PASS[실 함수 경유] · 기존 read_attachment
  16 PASS · headless JS **17 assert** PASS · `make test` 전량 exit 0 · ruff clean ·
  **구코드 대비 12/17 FAIL** 로 판별력 확인) + §18.8 backend+qa 패널 **BLOCK → [P1] 2 · [P2] 9 ·
  [P3] 6 전건 흡수** + **배포 완료**(2026-08-06, PR #1161 merge main `2cab05f3` → `make deploy-web`
  전체 스코프, post-cutover soak 90s 통과·롤백 0, **4서비스 GIT_COMMIT=2cab05f3 running/healthy**).
  **배포본 런타임 실증(ask-worker)**: 전문 → `전체 42줄 **전문**` · 문자상한(100줄×700자) →
  `1~85번째 줄 / 전체 100줄 (미열람: 뒤 15줄)` + `줄 중간에서 잘렸고 그 조각줄은 버렸습니다`
  (초판이 `남은 0줄` 허위를 내던 바로 그 입력) · EOF 초과 → `**전달된 줄 없음**` ·
  단계 요약 플래그 `{preview_truncated, result_chars}` · `result_capped_for_model` True.
  web-a 정적 자산에 `_buildStepPreviewNote` 2건 · `.step-result-preview-note` 1건 반영 확인.
  **라이브 대화 실측 미수행** → `unverified-live`.
  **배포 절차 기록(정직)**: 1차 시도는 로그 리다이렉트 경로 부재로 `make` 가 **실행조차 되지 않았고**
  (`PIPE_EXIT=1`), 서비스별 GIT_COMMIT 이 구 커밋(`e21606d2`)에 머물러 있어 발견했다 — 파이프 exit 이
  아니라 **서비스별 GIT_COMMIT** 으로 판정한다는 규칙이 실제로 미배포를 잡아낸 사례다. 재실행으로 성공.
  **패널이 잡은 P1 2건(내 초판 결함)**: ① 초판 테스트가 `read_attachment_content` 를 통째로 stub 해
  실 슬라이싱을 안 태웠고, 그 사각에서 **문자 상한(60,000자) 경로가 정량화된 허위**를 냈다 —
  `end_line` 이 자르기 전 청크 길이라 "남은 400줄" 이 실제로는 600줄(1,000줄×150자 실측)이었고,
  MUST 계약이 가리킨 `start_line=601` 때문에 **401~600 이 어떤 호출로도 오지 않는 구멍**이 됐다.
  다른 형태는 `남은 0줄 미열람` + `반드시 이어 읽으십시오` 라는 자기모순. 게다가 같은 변경이 도구
  설명에서 `max_lines` 축소를 금지해 **상한 발동 빈도를 스스로 올렸다**. ② 패널 주석이
  `assistant 에게는 결과 전문이 전달되었습니다` 를 **무조건** 단정 — `_cap_tool_result` 가 먼저
  자르면 거짓이고, **모델이 `max_lines` 를 줄인 단계**(이 감사가 찾은 유일한 진짜 미열람)에 안심
  문구를 덮어 **true-positive 를 false-negative 로 바꾼다**.

- **라이브 실측(2026-08-07) 미도달 — `unverified-live` 유지**: 2회의 라이브 턴(첨부 4건 갱신 ·
  신규 버전 변경점 질의) 모두 모델이 `read_attachment` 를 **호출하지 않고** 주입된 첨부 컨텍스트로
  답했다. 즉 완전성 계약(전문/부분 머리말 · MUST-이어읽기)이 **실행되지 않아 관측 자체가 불가**했다.
  이 축을 재려면 인라인 상한을 넘는 대용량 첨부로 도구 경로를 강제해야 한다(다음 실측 설계 항목).
- **source**: 사용자 라이브 실측 중 보고(2026-08-05) — "assistant 가 `read_attachment` 로 파일을 조회할 때
  마치 일부분만 조회하는 것처럼 동작. 웹 출력 간소화인지 실제 미열람인지 검토 필요".
- **last_seen**: 2026-08-05 · **seen_count**: 1 · **seen_distinct_conv**: 1(보고) / 41회·8대화(도구 전체)
- **modality**: 1:1 (fork) · **conv(마스킹)**: `…843232a3`([Fork] 실무 처리사항…, run `…acd234ec`)
- **symptom_confidence**: high (사용자 명시 보고) · **rootcause_confidence**: high (DB 실측 + 코드 file:line)
- **suspected_layers**: **L7**(표시 — 단계 패널이 500자 발췌를 절단 표시 없이 렌더) +
  **L2**(도구 결과가 완전성을 스스로 진술하지 않음)
- **판정(정직 분리)**:
  - **보고된 건은 실제 결함 아님** — step 6~8 실측: `1~42/전체 42줄` · `1~32/전체 32줄` ·
    `1~28/전체 28줄`, 절단 마커 **0**, assistant 수신 tool 메시지 **1,485 / 692 / 1,213자**.
    같은 스텝의 표시용 preview 는 **500자 캡**(`agent_core._build_step_result_summary`). 즉 **전문 수신**.
  - **오인의 직접 원인 2가지**: (a) 전문인데도 헤더가 `1~42번째 줄 / 전체 42줄` 이라 부분처럼 읽힘
    (b) 단계 보기 사이드 패널(`app.js` `_renderStepSidePanelBody`)이 `rs.preview` 를 **발췌 표시 없이**
    `<pre>` 로 렌더. 본문 채팅의 `buildStepBlocks` 는 non-SQL 스텝을 `work — reason` 한 줄로만 그리므로
    이 표면은 사이드 패널 한정.
  - **실재하는 미열람(드묾, 별개)**: 라이브 **41회 / 8대화** 중 절단 **2회**, 둘 다 **모델이 스스로
    `max_lines` 지정**(3 · 250). 그중 `SP_LOG_SCHEDULE_improved_v2.sql`(327줄 중 250줄)은
    **이어 읽지 않고 판단**(`…36a7790b`, 2026-07-31). **시스템 기본 600줄 캡 발동 0회.**
- **confirmed_root_cause**: 도구 결과가 "이 응답이 전문인가" 를 **문구로 구분하지 않았고**(전문·부분이
  같은 범위 표기), 절단 시에도 **이어읽는 방법만** 알려줄 뿐 **언제 반드시 이어 읽어야 하는지**를 계약으로
  못박지 않았다. 표시층은 별도로 무음 절단(500자)이었다. 재발경로 = `ux contract` + `model limit`.
- **봉인(사용자 승인 "이어읽기 계약까지 강화", AskUserQuestion 2026-08-05)**:
  (1) 헤더 전문/부분 분기(`start_line>1` 은 전문 아님) (2) 절단 시 **남은 줄 수 + MUST 이어읽기 계약**
  + 미이어읽기 시 **확인 범위 명시 의무** (3) 도구 description 에서 `max_lines` 임의 축소 금지
  (4) 표시층에 `preview_truncated`/`preview_full_chars` 플래그 + 패널 발췌 주석(feature-0003).
  **표시 캡은 상향하지 않음** — steps 는 전 도구 공유 저장 경로라 execute_sql 대량 결과까지 커진다.
- **corroboration**: 표시 오인은 **structural**(모든 도구·모든 절단 스텝에 해당) / 실제 미열람은
  **idiosyncratic**(41회 중 1회). disposition=fix-now 근거: 표시는 저위험 문구·플래그, 계약은 근본이
  코드 file:line confirmed 이고 재발 경로가 확실(대형 SQL 파일 리뷰는 상시 작업).
- **fix**: `CHG-20260805T190000-read-attach-completeness`(TASK-20260805T1900) /
  **코드 거주 primary `feature-0002-agent-core`** + secondary cross-ref `feature-0003-agent-web-ui`
  (`CHG-20260805T190000-step-preview-excerpt-note`) / `REV-20260805T190000-read-attach-completeness`.
- **rc_ids**: RC-1(L7 무음 절단 표시) · RC-2(L2 완전성 계약 부재) ·
  **batch-id**: B-20260805T190000-read-attach-completeness
- **정정(§2.5 — 초판 주장 2건이 틀렸다)**: ① "CI 가 JS 를 검증하지 않는다" → 저장소에
  `unit/feature-0003-agent-web-ui/tests/headless/` **29개 headless JS 회귀 테스트 관행**이 있다.
  관행대로 `test_step_preview_note.js` 신설(주석 유무·길이 폴백·**모델 수신분 단정 금지**·모델측 절단
  경고·`textContent` 강제·표 분기 포함). ② 표시 캡 유지 사유 "공유 저장 경로" → 도구별 분기는
  `tool_name` 으로 가능하므로 **틀렸다**. 실제 사유는 **steps 가 run 진행 중 폴링으로 반복 전송**되어
  캡 상향이 매 payload 에 곱해진다는 것.
- **범위 밖(deferred/watch)**: ① `read_attachment` 전용 표시 캡 상향(기술적으로 가능 — 폴링 전송량과
  맞바꾸는 판단이라 별도 항목) ② CRLF 정규화로 "전문" 이 바이트 동일을 뜻하지는 않음(선재)
  ③ 인라인 재사용 경로와 스토리지 경로의 `.strip()`·디코딩 차이(선재).
- **라이브 실측 필요분(§정직)**: ① 절단 발생 시 모델이 **실제로 이어 읽는지**(절단 자체가 41회 중
  2회로 드물어 자연 발생을 기다려야 한다) ② 패널 주석은 headless 로 **로직**을 고정했을 뿐
  **실 브라우저 렌더는 배포 후** 확인.

## FR-attachment-change-false-absence — fixed:deployed:unverified-live (L1 seal gap + model limit; 첨부 축 부재-단정을 막는 코드-권위 사실 부재)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트(신규 **24** PASS · `make test` 전량 exit 0 ·
  ruff clean · **뮤테이션 8/8 KILLED**) + §18.8 3채널 검증(아래, 패널 BLOCK 전건 흡수) + dogfood +
  **배포 완료**(2026-08-05, PR #1155 merge main `70df13a3` → `make deploy-web` 전체 스코프,
  post-cutover soak 90s 통과, 롤백 0).
  **4서비스 running/healthy** — ask-worker·insight-worker `70df13a3`, web-a·web-b `8b46bdec`
  (배포 직후 병렬 세션이 PR #1156 을 머지·배포. `70df13a3` 은 `8b46bdec` 의 **조상**이라 4서비스 모두
  본 변경을 포함한다 — `git merge-base --is-ancestor` 로 확인).
  **배포본 런타임 실증(ask-worker, 라이브 agent_memory/PG 연결)**: 신규 심볼 6종 적재 True ·
  실패 대화 데이터로 `compose_system_prompt` 실행 → 사실 **updated 8 / no-delta 0 / added 4 / other 1** ·
  `## ATTACHMENT SET` 이 `## LIVE-DB GROUNDING` **뒤 최종 위치**(프롬프트 마지막 문장까지 확인) ·
  부정 단정 침묵 계약 True(A·B 양쪽) · 리뷰어 프롬프트 floor 규칙 True / 대칭 BLOCK 제거 True.
  web /healthz `status=ok · mysql_ok · pg_ok`.
  **라이브 대화 실측 미수행** → `unverified-live`.

- **라이브 실측(2026-08-07) 1건 양성 관측 — 상태는 `unverified-live` 유지**: 첨부를 새 버전으로
  다시 올린 뒤 "직전 버전 대비 무엇이 바뀌었는지"를 물었을 때 assistant 가 **부재-단정 없이**
  신규 버전을 인식하고 변경점(맨 끝 1줄 추가)을 정확히 서술했다. 다만 ① 표본 1건 ② 원 보고의
  fork 시나리오가 아님 ③ 빈도 감소 시계열 부재 → §C5 의 `verified` 요건 미충족이라 승격하지 않는다.
- **source**: 사용자 명시 호출 `/_dqa:conversation_audit "추가 쿼리 리뷰 요청"` (2026-08-05) —
  "다른 대화를 fork된 대화에서, 첨부파일을 v2로 갱신하였지만 assistant가 이를 인식하지 못하는 이슈".
- **last_seen**: 2026-08-05 · **seen_count**: 1 · **seen_distinct_conv**: 1 (90일)
- **modality**: 1:1 (fork) · **product_id(마스킹)**: P-119 · **conv(마스킹)**: `…2dce99c7`
  (topic "추가 쿼리 리뷰 요청", `…a6fe00cf` 에서 fork, 43 메시지, run `…9f0d1a4c`)
- **symptom_confidence**: high (사용자 명시 보고 + 답변 원문 직접 관측) ·
  **rootcause_confidence**: high (주입 컨텍스트 실측 재구성 + 토큰 정합 + 코드 file:line 삼각측량)
- **suspected_layers**: **L1**(프롬프트 합성 — 부재 단정 금지 규칙 부재 + 표식이 중간 위치) ·
  **L6**(모델 한계 — 0행 프로브의 축 넘어 일반화). L4/L3 은 **데이터로 기각**(아래 refuted).
- **증상(signal)**: `E-USR`(사용자 명시 보고) + `E-AST`(환각 — 자기 프롬프트 안의 diff 와 정면 모순).
  답변: "## 확인 결과: 새로 첨부되거나 변경된 파일이 없습니다 … 13개 파일은 모두 지난 라운드에서 이미
  리뷰를 마친 것과 동일한 내용입니다". **실제**: v2 갱신 8 · 신규 4 · 이월 1 = 13.
- **거짓양성 기각(`refuted`, 정직 — 다음 진단자가 재추적하지 않도록)**:
  - **"컨텍스트가 안 들어갔다"(L3/L4) → REFUTED**. 배포본 ask-worker 로 그 턴을 재구성한 결과
    `★신규` **12** · `🔄v2` **8** · 본문 13건 전량 인라인(절단 0) · `## FILE UPDATES` v1→v2 unified
    diff **8건**, 첨부 섹션 38,013자가 **정상 생성**됐다.
  - **"프론트가 신규 표식을 안 보냈다" → REFUTED**. `ask_jobs.payload.new_attachment_ids` = 12건 정상.
  - **"인라인 파일이 워커 읽기 전에 삭제됐다"(경합) → REFUTED**. worker mode 는 web 이 정리하지 않는다
    (`if not app._is_worker_mode()`), 정리 주체는 워커. 잔존 동일-대화 인라인 파일에 v2 본문 13건 확인.
  - **"섹션이 프롬프트에서 빠졌다" → REFUTED(정량)**. 재구성 프롬프트 실측 **66,131 prompt tokens**
    vs 실제 run **91,054**(차이는 도구정의+지식주입). 섹션 부재 시나리오는 약 43k 로 불일치.
  - **"항상 깨지는 경로다" → REFUTED**. 같은 패턴(fork + v2 재업로드) `…72c11c4b`(2026-07-15)·
    `…774ada22`(2026-08-04)는 **정상 인식**. 결정적 파손이 아닌 **비결정 실패**다.
- **confirmed_root_cause**: 첨부 축의 **범주적 부재 단정을 막는 코드-권위 사실이 없었다**.
  (1) `agent_core.py` `compose_system_prompt` — `★신규`/`🔄vN`/diff 는 전부 첨부 섹션(offset **25,840**
  of 72,488)에만 있고, `_GROUNDING_AUTHORITY_DIRECTIVE` 같은 **last-writer 권위 위치의 대응물이 없다**.
  (2) 기존 봉인 `FR-false-absence-zero-row-catalog-scope`·LIVE-DB GROUNDING 은 **DB 축 전용**이라 이 축을
  덮지 않는다. (3) `modules/redteam.py` — 리뷰어의 evidence digest 에 "이번 턴에 무엇이 새로 왔는가" 가
  없어 모순을 **볼 근거가 없었다**(실측 `redteam_reviews` #260 verdict=`pass`).
  **직접 인과**: 답변 직전 라이브 DB 프로브 3연속 0행(`search_tables`×2·`search_routines`) → 모델이 그
  부재를 첨부 축으로 일반화. steps 기록상 4~6단계에서는 신규 파일(`T_gunzlog_masangcreatorshistory.sql`)을
  **정확히 인지**하고 있었다 → 마지막 합성 단계에서 뒤집혔다.
  **fork 의 역할(정직)**: fork 는 코드 결함이 아니라 **오판 확률을 극대화하는 조건**이다 — 복사된 이전
  라운드 히스토리가 "이미 다 리뷰했다" 는 강한 사전확률을 만들고, 첨부 복사본(v1)과 새 v2 를 구분하는
  신호가 `★`/`🔄` 표식뿐이다. 재발경로 = **model limit**(코드 결함 아님 → 입력·피드백 정형화로 봉인).
- **봉인(A+C+B, 사용자 승인 2026-08-05 AskUserQuestion)**:
  (A) `compose_system_prompt` **말미**에 코드-권위 `## ATTACHMENT SET — AUTHORITATIVE FACTS` 블록
  (건수+파일명, 부재 단정 금지, "0행은 DB 축 증거일 뿐", 신규 0건 시 대칭 진술, **평가의 자유는 유지**).
  (C) 사용자 턴 말미 매니페스트 한 줄(생성 지점 최근접, LLM 전달용 한정 — 저장본 불변).
  (B) **red-team 리뷰어 능동 검출** — find/verify 두 패스에 사실 블록을 **초안 앞**에 싣고, 부재 단정 ↔
  사실 모순을 `grounding` **BLOCK** 으로 규정(반대 방향도 대칭). 사용자 지정: 정규식 사후 게이트가 아니라
  리뷰어가 능동 검출.
  세 소비자는 **단일 계산**(`_ATTACHMENT_TURN_FACTS_CTX`)을 공유하고, `compose_system_prompt` 첫 문장에서
  항상 클리어해 워커 스레드 재사용 시 교차-대화 오사실을 차단한다. **보안 회귀 0** — 표식·diff·인라인 상한·
  IDOR/sender 스코프 전부 불변, 비신뢰 파일명은 평탄화 후 주입.
- **corroboration**: **idiosyncratic** — 90일 `new_attachment_ids>0` 인 118 job / 92 대화 중 부재 단정
  **distinct_conv 1**(이 건). 동일 패턴 fork 3건 중 2건은 정상. **disposition=fix-now 근거**: 빈도가 아니라
  (a) S 최상위(요청 자체가 거절되고 사용자가 직접 이슈 제기) (b) 근본이 코드 file:line 까지 confirmed
  (c) **서버가 이미 정확히 아는 축**이라 코드-권위 사실로 결정화 가능 — 명백한 구조결함 예외.
- **disposition 근거**: Major(§12.3 코어 LLM 경로) → attended human-decision. 사용자가 **A+C+B** 명시 선택.
- **fix**: `CHG-20260805T160000-attach-change-false-absence`(TASK-20260805T1600) /
  **코드 거주 `feature-0002-agent-core`**(리뷰어 기능 소유는 feature-0021-redteam-review — cross-ref) /
  `REV-20260805T160000-attach-change-false-absence`.
- **§18.8 검증 채널(정직)**: codex(1순위) **quota 소진으로 실행 불가**(Aug 9 까지) → built-in
  `/security-review` 인라인 수행 → 보안 1건 흡수(권위 블록의 비신뢰 파일명 미평탄화) → **사용자 승인 후
  backend/qa subagent 패널 호출 → BLOCK**. **[P1] 5 · [P2] 8 전건 흡수**:
  ① **부정 분기 제거** — `new_attachment_ids` 는 클라이언트 신호라 "비어 있음 ≠ 첨부 없음" 인데 초판은
  그 상태에서 "이번 턴 첨부 없음" 을 코드-권위로 선언하고 리뷰어에게 반대 주장을 BLOCK 시켰다.
  **봉인이 이 마찰을 스스로 생산하는 구조**였다(qa 프로브 재현). 신규 0건이면 전면 침묵으로 수정.
  ② 리뷰어 블록 **무음 절단**(join 후 900자 슬라이스 → 파일명 중간 절단 + 뒷줄 소실; 관측 사례 8+4 가
  정확히 이 경계) → 건별 캡 + `외 N건 생략` 표기. ③ `version_diff` 는 text/csv 재업로드에서만 생성되는데
  버전>1이면 무조건 "FILE UPDATES 에 있다" 고 가리켜 **fabrication forcing** → `updated`/`updated_no_delta`
  분리. ④ 동일 파일 재업로드(sha256 일치 시 기존 행 재사용)에서 **"내용 동일" 이라는 참인 답변을 금지**
  → 금지 범위를 "제공 사실의 부정" 하나로 축소. ⑤ **배선 seam 무방비** — qa 뮤테이션 10종 중 6종(A삭제·
  위치이동·C합치기삭제·verify패스·bounded게이트·0행경로)이 초판 18건 + 관련 224건을 전부 통과했고,
  위치 계약 테스트는 자기가 만든 문자열을 검사하는 tautology 였다 → 배선 테스트 신설 후 **자체 뮤테이션
  8/8 KILLED** 로 역검증. P2: bare except → logger.warning · 로컬 스냅샷 + run_agent 토큰 튜플 · AI
  생성본 제외 · `carried`→`other` · 빈 파일명 placeholder · 캡 경계 · 기존 grounding endswith 계약 명문화.
- **dogfood(배포 전 최대치, 패널 흡수 후 재실행)**: 실패 대화 데이터로 새 코드 실측 — 사실
  **updated(diff) 8 / no-delta 0 / added 4 / other 1** 정확 · 권위 블록 offset **49,741/51,707 = 최종
  위치**(LIVE-DB GROUNDING 45,590 뒤, 프롬프트 마지막 줄까지 확인) · 기존 표식 회귀 0(`★신규` 12·
  `🔄v2` 8·diff 헤더 8) · A 블록 1,968자(3.8%) · C 151자.
  (1차 dogfood 는 인라인 본문이 남아 있어 프롬프트 69,813자였고, 2차는 그 임시 파일이 reaper 로 회수된
  뒤라 51,707자다 — 사실 계산이 **인라인 본문 유무와 무관**하게 동일했다는 부수 확인이 된다.)
- **회귀 테스트**: 신규 **24**(배선 seam 포함) + 기존 grounding 스위트 21 PASS · `make test` 전량
  **exit 0** · ruff clean · **뮤테이션 8/8 KILLED**.
- **rc_ids**: RC-1(L1 seal gap) · RC-2(L6 축-넘어 일반화) · **batch-id**: B-20260805T160000-attach-change-false-absence
- **범위 밖(deferred/watch)**: ① **동일 파일 재업로드의 `★신규` 오라벨** — sha256 일치 시 서버가 기존
  행을 재사용하는데 프론트가 그 pill 을 `source:"new"` 로 덮어 `new_attachment_ids` 에 실린다. 이번
  수정은 "내용 동일" 결론을 허용해 **피해를 없앴지만** 라벨 자체는 여전히 부정확하다(근본은
  feature-0003 composer). ② PG 첨부 조회 분기는 conftest 고정으로 **어떤 테스트도 실행하지 않는다** —
  배포본 dogfood 로만 덮였다.
- **라이브 실측 필요분(§정직)**: 코드/테스트/dogfood 는 "사실이 정확히 계산되어 최종 위치에 실린다" 까지만
  증명한다. **"실제 대화에서 부재 단정이 사라지는지"**·**"리뷰어가 실제로 BLOCK 을 올리는지"**·
  **"권위 블록이 평가 품질을 과도하게 누르지 않는지"** 는 배포 후 실측분(미수행). 다음 audit 이
  corroboration(부재 단정 distinct_conv / `redteam_reviews` 의 해당 축 BLOCK 발생)을 재측정한다.
- **필요한 사람 액션(1줄)**: 배포 완료 — 남은 것은 **라이브 실측**(같은 시나리오에서 부재 단정 소멸 ·
  `redteam_reviews` 의 해당 축 BLOCK 발생 · 권위 블록이 평가 품질을 누르지 않는지) + `/_dqa:doc_sync`.

## FR-attachment-created-at-tz-skew-9h — deferred (L4 저장 시각 +9h; 이번 마찰의 원인 아님, 사용자 결정으로 별도 항목 이월)

- **status**: `deferred` — 사용자 결정(2026-08-05, AskUserQuestion): "별도 항목으로 이월". 코드 변경 없음.
- **last_seen**: 2026-08-05 · **seen_count**: 1 · **seen_distinct_conv**: 해당 없음(데이터 전역)
- **rootcause_confidence**: high (DDL + 서버 TZ + 미러 코드 file:line + 30일 집계 4중 확인)
- **suspected_layers**: **L4**(데이터 로드·스키마 — 저장 시각 의미 불일치)
- **증상(signal)**: `core_attachments.created_at` 이 같은 행의 `superseded_at`·`core_conversations`·
  `core_messages` 대비 **일관되게 +9시간**. 실측: 30일 표본 최빈 **9.00h**(관측 대화에서 첨부 생성
  `23:14:32+09` vs 같은 사건의 supersede `14:14:53+09`).
- **confirmed_root_cause**: MySQL `WebConversationAttachments.CreatedAt datetime(6) NOT NULL DEFAULT
  CURRENT_TIMESTAMP(6)` 가 **서버 로컬 시각**으로 기록되는데(`@@time_zone=SYSTEM`, `NOW()`=14:42 vs
  `UTC_TIMESTAMP()`=05:42), PG 미러 `attachment_pg_mirror._dt_to_pg`(:140-151)가 그 naive 값을
  **UTC 로 간주**해 `timestamptz` 로 넣는다. `SupersededAt` 은 앱이 UTC 로 써서 정상 → 같은 행 안에서
  두 시각이 9시간 어긋난다. 재발경로 = **코드 결함**(경계에서의 시각 의미 가정).
- **영향(미조사 — deferred 사유)**: 첨부 간 정렬은 전부 같은 방향으로 치우쳐 **순서 자체는 보존**
  (`_collect_matched_attachment_names` ORDER BY created_at). 화면 표시·기간 필터·share window 등
  **다른 테이블과 시각을 비교하는 경로**의 영향 범위는 미조사. 기존 행 backfill 여부도 미결정.
- **이번 마찰과의 관계**: **무관**(원인 아님). `FR-attachment-change-false-absence` 진단 중 부수 발견.
- **필요한 사람 액션(1줄)**: 별도 cycle 로 영향 범위(표시·필터·window) 조사 후 미러 변환 교정 + 기존 행
  backfill 여부 결정.

## FR-loadgate-blind-coaching — fixed:deployed:verified (L2 거부 피드백 + L5 LIMIT 미반영 추정; 부하게이트가 재작성 방향을 못 줘 추론이 정체)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트(신규 **31** PASS · feature-0002 전체 **2360 passed / 30 skipped** · ruff clean) + **§18.8 codex 3렌즈에서 [P1] 2건 출하차단 판정 → 9건 전부 흡수·역검증 생존 0** + verify-completion PASS + **배포 완료**(2026-07-31, PR #1112 merge main `97af7d27` → `make deploy-web` 전체 스코프. **4서비스 GIT_COMMIT=97af7d27 running/healthy**: web-a·web-b·ask-worker·insight-worker, post-cutover soak 통과).
  **배포본 런타임 실증(ask-worker, 라이브 datasource EXPLAIN)** — 새 심볼 3종 적재 True · `guard_mode=gate`·임계 1,000,000 확인 · **① 마찰 재현 케이스 `SELECT * FROM tf_log_05_item LIMIT 5` → est 13,891,780 → 5 로 보정 → PASS**(종전 차단) · **② 전역 집계 `COUNT(*)` → 차단 유지 + 진단(`접근형태=전체 인덱스 스캔·사용 인덱스=LogType·스캔 파티션=26개`) + "전역 집계는 LIMIT 으로 안 줄어든다" + `search_tables approx_rows` 대안 부착** · **③ P1 회귀 케이스 `-- LIMIT 5` 주석 위장 → 차단 유지**(우회 없음).
  **라이브 대화 재현 A/B 대조(2026-08-03, 사용자 요청 검증)** — 배포본 ask-worker 에서 원 대화가 무산됐던 **같은 조사**(1062 PK 중복 · 1264 ContentsResult 범위 초과 원인 규명)를 재현했다. 콘솔 경로(`account_id` 미지정)로 돌려 **라이브 사용자 대화 테이블을 오염시키지 않았다**.

  | 지표 | BEFORE(원 대화 `…36a7790b`) | AFTER(배포본 재현) |
  |---|---|---|
  | 부하게이트 차단 | **6회** | 4회 |
  | 차단 메시지에 `[실행계획]` 진단 | **0 / 6** | **4 / 4 (100%)** |
  | 전역집계 불가 사실 고지 | 0 | 3 |
  | `approx_rows` 대안 안내 | 0 | 2 |
  | 같은 대상 반복 차단 escalation | 0 | **2** (설계대로 발동) |
  | 차단 직후 **또** 차단(막다른 길) | 4 | 2 |
  | **조사 목적 달성** | **무산**(6연속 차단 후 다른 경로로 우회) | **완수**(17 steps · 6,078자 답변에 원인 + 대안 3종) |

  **재작성 궤적(코칭이 실제로 방향을 이끌었다는 직접 증거)**: 차단(`대상 tf_log_05_item — 접근형태=전체 행 스캔(인덱스 미사용)…`) → 모델이 **대상을 작은 `TF_ErrorLog` 로 전환 + `ErrorNum IN (…) … LIMIT 10`** 으로 재작성 → 성공. 이후 또 차단되자 **`SequenceID BETWEEN … LIMIT 20` 으로 범위 축소** → 성공 → 실제 데이터(SequenceID 49435127~49435131 행)를 조회해 답변 완성. 원 대화에서는 같은 지점에서 형태만 바꾼 재제출이 6회 반복되고 조사가 끝났다.
  **답변 품질**: 요청 범위와 에러 범위의 **불일치를 스스로 짚었고**(1264 는 요청 범위 밖), 차단으로 인한 제약을 답변 서두에 **명시**했다(투명성). 대안으로 `REPLACE INTO` / `ON DUPLICATE KEY UPDATE` / 원본 정규화 3종 제시.
  **재현 한정(정직)**: ① **RC-2(LIMIT 상한 보정)는 이 재현에서 발동하지 않았다** — 모델이 순수 `LIMIT n`(WHERE 없는) 조회를 내지 않았기 때문. 그 레버는 배포본 직접 실측(위)에서만 확인됐다. ② 콘솔 경로라 `scratch_import` 가 "대화 컨텍스트 없음" 으로 1회 거부됐다(재현 방법의 부작용, 실사용 경로에는 없음). ③ **모집단 빈도 감소는 미측정** — 배포 직후라 실사용 표본이 없다. 다음 audit 이 corroboration(`무거운 쿼리로 추정됩니다` distinct_conv / `execute_sql` 대비 rate)을 재측정한다. **본 `verified` 판정의 근거는 "통제된 A/B 재현에서 봉인이 설계대로 작동하고 목적 수행이 회복됐다" 까지이며, "라이브 모집단에서 마찰 빈도가 줄었다" 는 아직 주장하지 않는다.**
  **배포 1차 시도 실패 기록(정직)**: 첫 `make deploy-web` 은 insight-worker 가 300s 내 healthy 미도달 → **워커군 last-good 롤백**으로 끝나, web 만 신코드·워커는 구코드인 부분 완료였다(이번 수정의 실행 주체가 ask-worker 라 그 상태로는 **마찰 수정이 라이브에 미도달**). 원인은 이번 변경이 아니라 기동 직후 외부 datasource 다수 도달 불가(timeout·blocked_target·MSSQL 로그인 실패)로 헬스체크가 늦게 붙은 것 — 안정 후 **멱등 재실행으로 성공**(insight-worker 20s 내 healthy). `make` 종료코드가 파이프에 가려 0 으로 보인 점도 함께 기록한다.
- **source**: 사용자 명시 호출 `/_dqa:conversation_audit "에러로그 분석 및 원인 대안 제시"` (2026-07-31) — "테이블을 조회할 때 '무거운 쿼리' 에 대한 블로킹이 너무 심하게 나타난다('LIMIT 1' 임에도)".
- **last_seen**: 2026-07-31 · **seen_count**: 1 · **seen_distinct_conv**: 12(전체) / **10**(30일)
- **modality**: 1:1 동기 · **product_id(마스킹)**: P-7 · **conv(마스킹)**: `…36a7790b`(topic "프로시저 테스트 에러 로그 분석 및 해결방안", 105 메시지)
- **symptom_confidence**: high (사용자 명시 불만 + 한 대화 **6연속 차단** 직접 관측) · **rootcause_confidence**: high (코드 file:line + **라이브 EXPLAIN 실측** + 전사 삼각측량 일치)
- **suspected_layers**: **L2**(거부 피드백 — 자기교정 정보 부재) + **L5**(부하 가드 추정 산식)
- **증상(signal)**: `E-SYS`(도구 거부 반복 — 메시지 6499·6501·6503·6505·6511·6513 이 **동일 문구**) + `E-USR`(명시 불만). 모델은 매 차단마다 형태만 바꿔 재제출했고(컬럼 축소 → 범위 축소 → 집계 변경), 6회 후 목적을 포기하고 다른 경로로 우회했다.
- **거짓양성 기각(`refuted`, 정직)**: 사용자가 지목한 "`LIMIT 1` 인데 차단" 그 쿼리는 `COUNT(*)`·`AVG()` **집계**라 LIMIT 과 무관하게 전체 스캔이 맞다 — **게이트 판정 자체는 정당**. 전체 차단 25건 중 **24건이 집계**(`COUNT(|SUM(|AVG(|GROUP BY`), LIMIT 있고 집계 없는 건 1건. 따라서 "가드가 과차단한다 → 임계를 낮추자/집계를 통과시키자" 는 **부하 회귀**이며 채택하지 않았다(F4 — 거부는 기능). 결함을 거부 *자체* → 거부 *피드백*으로 **위치 재지정**했고, 그와 **별개로** 실재하는 오판(순수 LIMIT)만 좁게 되돌렸다.
- **결정적 증거(라이브 EXPLAIN 실측, product 7 데이터소스 · 읽기 전용)**:
  | 쿼리 형태 | est | 판정 | 실제 |
  |---|---|---|---|
  | `SELECT * FROM <로그테이블> LIMIT 5` | 13,903,018 | 차단 | **5행 — 오판** |
  | `WHERE <비인덱스컬럼> IN (…) LIMIT 10` | 6.1M~15.2M | 차단 | 풀스캔(`type=ALL`·`key=None`) — 정당 |
  | `COUNT(*), MIN, MAX … LIMIT 1` | 13.9M | 차단 | 전체 인덱스 스캔 — 정당 |
  | `WHERE <파티션키> >= '2026-07-31'` | **1** | **통과** | 파티션 4/26 프루닝 — **재작성 경로가 실재** |
  마지막 행이 핵심이다: 통과하는 재작성이 **존재하는데** 게이트 메시지가 그 방향(인덱스·파티션 선두 컬럼)을 알려주지 않았다.
- **confirmed_root_cause**: **RC-1** `unit/feature-0002-agent-core/src/modules/tools.py` gate 분기(구 :2628-2641) — EXPLAIN 이 이미 산출한 계획 사실(`type`/`key`/`possible_keys`/`partitions`)을 **버리고** 정적 일반론("필요 컬럼만·WHERE 한정·서버측 집계·LIMIT")만 반환. 모델이 그 넷을 **이미 적용한** 쿼리를 냈으므로 정보량 0 → 재작성 루프. 특히 **전역 집계는 재작성으로 가벼워질 수 없는데** 계속 재작성을 요구받았다. **RC-2** `.../modules/dialects.py` `_parse_explain_rows_product`(:21-55) — `EXPLAIN.rows` 는 **LIMIT 미반영 스캔 상한**인데 이를 "예상 처리 행수"로 사용. 재발경로 = **코드 결함**(model limit 대응: 거부 피드백 정형화) — data/config drift 아님.
- **선행 작업과의 계보**: TASK-0304 가 게이트를 "차단" → "재작성 코칭" 으로 reframe 했으나 **코칭 내용이 정적**이었다. 즉 이번 결함은 그 reframe 의 미완성분이다.
- **corroboration**: **structural** — 30일 distinct_conv **10** / 대화 129건의 **7.8%**, 차단 23건 / `execute_sql` 386건의 **6.0%**(전체 기간 12 대화·25건, 2026-06-18 최초).
- **봉인(①+②, 사용자 승인 2026-07-31)**: (①) `_heavy_query_coach()` — 차단 메시지에 계획 진단(접근형태·사용/후보 인덱스·스캔 파티션 수) + 원인별 지시(인덱스 미사용이면 `get_table_indexes`/`describe_table` 로 선두·파티션 키 확인 후 좁히기 / **전역 집계면 "컬럼 축소·LIMIT 으로는 안 줄어든다"는 사실 + `search_tables` 의 `approx_rows` 대안**) + **같은 run 2회 이상 차단 시 `confirm_heavy=true` 를 최후수단→명시 선택지로 승격**. 계획 사실 없는 엔진(MSSQL)은 기존 문구 폴백(골든). (②) `MySQLDialect.estimate_load` 가 **조기 종료 보장 형태 한정**(단일 SIMPLE plan row / 집계·WHERE·ORDER BY·GROUP BY·HAVING·DISTINCT·UNION·JOIN·서브쿼리·CTE 부재 / filesort·temporary 부재 / **문 끝** LIMIT)으로 `min(est, n+offset)` **하향 전용** 보정. 임계·게이트 모드·`confirm_heavy` 신뢰 정책·MSSQL fail-closed·MySQL fail-open **전부 불변**.
- **disposition 근거**: Major(§12.3 — 코어 LLM 도구 경로·거부 로직) → attended human-decision. structural corroboration + 코드 file:line confirmed(high) + 라이브 EXPLAIN 으로 오판·정당을 분리 실증 → fix-now. 사용자가 AskUserQuestion 으로 **두 레버 모두 + 임계 유지** 명시 선택 → 승인 후 구현.
- **fix**: `CHG-20260731T184300-loadgate-blind-coaching`(AC-0604/AC-0605) / **코드 거주 `feature-0002-agent-core`** / `REV-20260731T184300-loadgate-blind-coaching`(§18.8.2 제약-없는-채널 → codex backend+security+qa. **[P1] 2건** — 주석 속 가짜 LIMIT·`SQL_CALC_FOUND_ROWS` 가 실제 전체 스캔을 통과시켰다: **봉인이 막으려던 부하 회귀를 봉인 자신이 만들고 있었다**. [P2] 5 + [P3] 2 포함 전부 흡수, 1건은 코드가 아니라 문서 정정)
- **rc_ids**: RC-1(L2) · RC-2(L5) · **batch-id**: B-20260731T184300-loadgate-blind-coaching
- **dogfood(배포 전 가능한 최대치)**: 라이브 EXPLAIN 계획 4건을 **새 코드로 판정** — 순수 LIMIT 2건(13.9M/30.5M) → **5/3 보정 PASS**, 집계·인덱스미사용 2건 **차단 유지 + 진단 문구 부착** 확인.
- **라이브 실측 필요분(§정직)**: 코드/테스트·dogfood 는 "새 코드가 오판을 되돌리고 정당 차단에 진단을 붙인다" 까지만 증명한다. **"실제 대화에서 차단이 줄고 재작성이 성공하는지"** 는 배포 후 실측분(미수행) → 다음 audit 이 corroboration(`무거운 쿼리로 추정됩니다` distinct_conv / `execute_sql` 대비 rate) 재측정 → 감소 시 `verified`, 재증가 시 `regressed`.
- **후속(이월)**: ① `scratch_import` 병렬 게이트(`⚠ 무거운 반입으로 추정됩니다`)의 코칭 문구 미적용(LIMIT 보정은 dialect 층이라 자동 적용) — 같은 friction-id 후속. ② **임계 1,000,000행의 로그 도메인 적합성** = `report-only`(운영 판단) — 대상 테이블이 1,300만~3,000만행이라 인덱스 미사용 조건은 사실상 상시 차단. 사용자 결정(2026-07-31): **코드만 수정·임계 유지**. 봉인 ①이 재작성 경로를 열어주므로 임계 유지로도 목적 수행이 가능한지가 다음 audit 의 측정 대상.
- **필요한 사람 액션(1줄)**: PR 생성·deploy confirm(Major — override 불가) → 배포 후 라이브 대화에서 차단 빈도·재작성 성공률 실측 + `/_dqa:doc_sync`.

## FR-operator-global-prompt-shadows-code-seals — needs-human (L1 data/config drift; 운영자 global row 가 코드 상수를 통째 대체해 2026-06-18 이후 프롬프트 봉인 전량 미도달)

- **status**: `fixed:deployed:verified` — **라이브 census 재측정 완료(2026-07-31)**. 사용자 지시("후속 이슈가 있다면 해당 부분도 적용을 검토해주세요") + 범위 승인 **A+B**(AskUserQuestion 2026-07-31) 로 봉인.
  **배포**: PR #1114 merge main `954adc87` → `make deploy-web` 전체 스코프(web-a/web-b 무중단 롤링 + insight-worker/ask-worker 재생성 + gateway reconcile, soak 90s 통과). **4서비스 GIT_COMMIT=954adc87 running/healthy**.
  **라이브 census 재측정(이 항목을 `verified` 로 닫는 근거 — 측정으로만 done)**: 배포본 ask-worker 에서 실 `agent_memory` 연결로 `compose_system_prompt` 호출 → composed **13,604자 → 17,830자**, **필수 seal 9종 전량 LIVE**(첨부↔실DB 양측조회 · 0행≠부재 · 절단통지 · 완전성 명시신호 · 식별자 대소문자 · check_table_coverage · 시간방향 계약 · 첨부갱신 · 신규스크립트첨부). 수정 전 측정에서 **부재 확정 5종이 전부 도달로 전환**됐다.
  **모순 제거 실증**: 억제 지시 0 · 첨부우선 지시 0. **보안 carve-out 실증**: `IT OVERRIDES NOTHING ELSE.` True · "보안·프라이버시 규칙이 이긴다" True · 운영자 마스킹 정책 보존 True. **last-writer 실증**: composed prompt 가 이 상수로 끝남 True(운영자 scope row·첨부 섹션보다 뒤).
  **잔여**: 실제 대화에서의 행동 변화(리뷰가 적용 후 기준으로 쓰이는지)는 `FR-review-frames-live-db-as-spec` 의 라이브 실측분에 귀속 — 다음 audit 이 corroboration 으로 측정. **(A) 코드 권위선**: `_GROUNDING_AUTHORITY_DIRECTIVE` 신설 + `compose_system_prompt` **반환 직전** append(운영자 global row 뿐 아니라 product/role/account scope row 보다도 뒤 = last-writer). **(B) 라이브 데이터 교정 완료**(아래). 코드 부분 배포 전.
  **초기 판정 정정**: 처음엔 "수정 방향이 사람 결정" 이라 `needs-human` 으로 열었으나, 운영자 row 를 실제로 대조해 보니 **덮어쓰기 안(a)은 배제**가 옳았고(운영자 고유 PII 정책 소실), **replace→merge 안(b)도 배제**가 옳았다(영문 원본+한국어 재작성 중복) — 실제 해는 제3안인 **코드-append 권위선 + 문제 2줄만 국소 교정**이었다. 선택지를 두 개로 좁혀 사람에게 넘긴 것이 성급했다.
- **source**: `FR-review-frames-live-db-as-spec` 배포 후 라이브 compose 실증 중 **부수 발견**(2026-07-31). 내 계약이 도달하는지 확인하다가 **다른 것들이 도달하지 않음**을 발견했다.
- **last_seen**: 2026-07-31 · **seen_count**: 1 · **seen_distinct_conv**: n/a(대화 신호 아닌 구성 측정)
- **rootcause_confidence**: **high** — 배포본 ask-worker 에서 직접 측정. `compose_system_prompt` 는 `WebSystemPrompts` scope='global' row 가 있으면 **코드 상수 `SYSTEM_PROMPT` 를 통째로 대체**한다(`base_prompt = str(_brow[0])`). 라이브 global row = **15,978자 / UpdatedAt 2026-06-18 13:58:25**, 코드 상수 = **20,575자**. 따라서 2026-06-18 이후 `SYSTEM_PROMPT` **본문에만** 추가된 규칙은 프로덕션에 **존재하지 않는다**.
- **측정(배포본 실측, marker 부재 확정)**: 아래는 라이브 composed prompt 및 코드-append guidance 상수 전체(16,825자)에서 **둘 다 부재** 확인분 —
  - `ZERO ROWS IS NOT ABSENCE` (FR-false-absence-zero-row-catalog-scope, 원장 `fixed:deployed:verified`)
  - `COMPARING an attachment against the live DB` (FR-partial-evidence-false-verification)
  - `COMPLETENESS COMES FROM AN EXPLICIT COMPLETENESS SIGNAL` (FR-false-truncation-belief, 원장 `fixed:deployed:verified`)
  - `TRUNCATION NOTICES / PREVIEW-TRUNCATED` (동)
  - `IDENTIFIER CASE` (FR-schema-name-case-drift)
  - `check_table_coverage` 유도 (REQ-20260714-attach-table-coverage)
  - `## ATTACHED FILES` 섹션 전체
- **도달하는 것(대조군)**: `compose_system_prompt` 의 `parts` 로 **코드가 always-append** 하는 것들만 살아 있다 — `_INJECTION_GUARD_NOTICE` · `_ATTACHMENT_DELIVERY_DIRECTIVE` · `_ATTACHMENT_NEW_DELIVERY_DIRECTIVE` · **`_ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE`(이번 cycle)**. `_run_agent_core` 가 뒤에 붙이는 `_DATA_GROUNDING_GUIDANCE`/`_MYSQL_DIALECT_GUIDANCE`/`_ACTIVE_INTERPRETATION_GUIDANCE` 등도 코드 경로라 살아 있다.
- **의미(정직 표기)**: 위 봉인들의 **프롬프트 레버 부분**은 라이브에서 무효다. 단 각 마찰의 **도구/코드 레버**(`search_routines`·`_catalog_scope_hint`·완전성 신호 emitter·`describe_routine` offset·`check_table_coverage` 도구 자체 등)는 코드라 정상 작동하므로 봉인이 통째로 무효인 것은 아니다. 그러나 원장이 두 항목을 `fixed:deployed:verified` 로 닫은 근거에는 프롬프트 레버가 포함돼 있었으므로, **그 verified 판정의 일부 전제가 라이브에서 성립하지 않았다**.
- **왜 이번 수정은 영향을 안 받았나(설계 검증)**: 본 cycle 의 계약을 `SYSTEM_PROMPT` 본문이 아니라 `parts` always-append 로 넣은 것이 정확히 이 drift 를 겨냥한 것이었고(FR-attachment-update-pasted-not-versioned 의 AUTH-1a 선례), 실측이 그 선택을 검증했다. 같은 cycle 에서 §ATTACHED FILES 에 넣은 **미러 1줄은 라이브에 도달하지 않는다** — 코드 상수 경로(운영자 row 부재·bootstrap)에서만 유효한 이중화로 남는다.
- **활성 모순(정밀 진단에서 추가 발견 — 단순 누락이 아니었다)**: 라이브 row 의 `## 첨부 파일` 절에 REQ-20260714-attach-review-grounding 이 **환각 유발로 판정해 코드에서 제거하고 회귀 테스트로 고정한 두 지시**가 한국어로 살아 있었다 — "사용자가 명시적으로 실행/검증을 요청하지 않는 한 execute_sql 을 돌리지 마십시오" + "첨부 지침이 일반적인 '데이터베이스를 조회하라' 지침보다 우선합니다". 당시 §18.8 패널이 MAJOR 로 못박은 실패 모드(*"동적본만 고치고 정적본을 남기면 takes precedence 가 verify 를 이긴다"*)가 **그대로 라이브 상태**였다.
- **선행 마찰의 실제 기전 규명**: 이것이 `FR-review-frames-live-db-as-spec` 의 A/B 대조쌍(동일 입력, 도구 0회 `…4348bc34` ↔ 12회 `…a2efa955`)이 갈린 원인이다 — 정적(운영자) "조회하지 마라·첨부 우선" vs 동적(코드) "반드시 라이브 검증하라" 가 한 프롬프트 안에서 정면 충돌해 run 마다 어느 쪽을 따를지 갈렸다. 선행 cycle 의 시간-방향 계약은 DB-확인 분기의 **프레임**을 고쳤고, 이 cycle 이 **모순 자체**를 없앤다.
- **운영자 row 는 stale 사본이 아니다(대조 결과)**: 한국어 재작성 + 코드에 **없는** 운영자 고유 정책 3절(`보안 경계 — 읽기전용·권한·인젝션` / `민감 데이터 처리 — 최소 노출·마스킹`(재식별 방지 포함) / `데이터소스 선택`)을 담고 있다. 코드 상수로 덮어쓰면 PII 정책이 소실되고, replace→merge 로 바꾸면 영문 원본과 한국어 재작성이 양쪽 다 실려 중복·모순이 커진다 → 둘 다 배제.
- **봉인 A(코드, drift-proof)**: `_GROUNDING_AUTHORITY_DIRECTIVE` — 부재 5종 규칙 + 두 억제 지시를 **언어 무관 의미로 지목**해 무력화. override 는 **첨부 검토 맥락 한정**이고 보안·프라이버시 7종은 carve-out(명령계층·읽기전용·allowlist·데이터소스·마스킹·재식별·쿼리부하), 충돌 시 "보안·프라이버시 규칙이 이긴다". 배치는 `compose_system_prompt` **반환 직전** — 초기 `parts` 에 두면 뒤에 누적되는 scope row 가 다시 덮는다(§18.8 codex R2 P2 로 교정).
- **봉인 B(라이브 데이터, 적용 완료 2026-07-31)**: 운영자 global row id=20 에서 **문제의 두 줄만** 교체(9,219→9,294자, diff 2 hunk). 백업 `artifacts/websystemprompts-global-backup-20260803T032541Z.txt`(15,978 bytes). 적용 후 라이브 실증 — 억제 지시 0 / 첨부우선 지시 0 / 운영자 마스킹·재식별·데이터소스 정책 **전량 보존** / "내부 품질 리뷰는 DB 불필요"(과차단 회귀 방지) 와 "실 DB 현재 상태 주장 시 도구 확인 의무" 양쪽 LIVE.
- **fix**: `CHG-20260731T030000-grounding-authority-directive` / **코드 거주 `feature-0002-agent-core`** / `REV-20260731T030000-grounding-authority-directive`(§18.8.2 codex **3라운드** — R1 P1 1건+P2 4건 → R2 P1 폐쇄+P2 3건 → R3 신규 P1/결함 0+P2 1건, **전건 수정**). 신규 테스트 18건 + 전체 2377 passed.
- **재발 방지(census)**: `REQUIRED_LIVE_SEALS` 9종이 **코드-append 영역**에 존재하고 composed prompt 에 도달하며 **작동 조항**까지 살아 있는지 테스트가 고정한다. 새 grounding 규칙을 `SYSTEM_PROMPT` 본문에만 추가하면 이 census 가 FAIL 한다 — 2026-06-18 이후 5종이 조용히 유실된 경로를 구조적으로 차단.
- **라이브 실측 필요분(§정직)**: B 는 배포본에서 실증 완료. **A 는 배포 후 라이브 census 재측정**(운영자 row 대체 조건에서 9 seal 전량 도달) 필요.
- **필요한 사람 액션(1줄)**: 운영자 global row 를 현재 코드 상수로 재동기화할지, 는 **불필요**(A+B 로 해소). 남은 것은 A 배포 승인 + 배포 후 census 재측정. **불변 규칙: 새 프롬프트 규칙은 `SYSTEM_PROMPT` 본문이 아니라 코드 append 로 넣는다** — census 테스트가 이를 강제한다.

## FR-review-frames-live-db-as-spec — fixed:undeployed (L1 시간 방향 계약 부재; 리뷰가 '적용 후'가 아닌 '현재 DB' 기준으로 불평)

- **status**: `fixed:deployed:verified(framing)` — **라이브 육안 실측 완료(2026-08-03, PB-0008 Windows-browser)**. 사용자 보고 프레임("현재 DB 기준으로 불평하듯")이 **동일 입력에서 재현되지 않았다**. 단 같은 답변에 미검증 부재 단정 1건이 남아 접지 축은 별 항목(`FR-review-precondition-assumed-not-verified`)으로 분리 — 그래서 무조건 `verified` 가 아니라 축 한정 표기.
  **재현 설계(통제)**: 실제 Windows Chrome 으로 새 대화 생성 → 제품 119(GZ_QA_G) 선택 → **원본 5파일 재업로드(sha256 5/5 일치)** → 동일 요청문 20자 → `#sendBtn` 실제 클릭. 모델 claude-haiku(원 대화와 동일). 재현 대화 `20260803081201-969946a2`.
  **화면 확인(증적 `unit/feature-0002-agent-core/docs/test-runs.d/evidence/20260803-review-framing-after-*.png`)**: 도입부가 **"마이그레이션/신규 기능 추가 스크립트 … 실제 DB 현황(BEFORE)과 비교"** 로 시간 방향을 명시 · 최상단이 파일별 논리·설계 리뷰(BEFORE 는 `## 0. 배포 순서 의존성(가장 중요)`) · 미배포 상태가 `📊 적용 전제` **단일 절**에 ✅ 로만 기재(BEFORE 는 "아직 존재하지 않습니다" 가 핵심 지적) · 🔴🟡🟢 배지가 **적용 후에도 남는 결함**(중복 결제 멱등성·PK 설계·인덱스·에러코드·주석)에만 부착 · 배포 순서는 말미 Q&A 로 강등.
  **동반 확인**: `search_routines` **본문 매칭 위치** 컬럼이 라이브 동작 — 호출부 4건은 `CALL 'Log_AccountUpdateCash'(…)` 문맥 조각 표시, 이름 매칭 1건은 `(본문 외 매칭)` + 사유 주석(§18.8 codex P2 교정이 실제로 반영됨).
  상세: `docs/test-runs.d/20260803T1720-review-framing-live-pb0008.md`.
- **(이전) status**: `fixed:deployed:unverified-live` — 코드/테스트(신규 27 PASS · feature-0002 전체 2114 passed/30 skipped · `make test` RC=0 4회 연속) + §18.8 codex 3렌즈([P1] 0 · [P2] 4 중 2 흡수·2 근거 수용) + verify-completion PASS + **배포 완료**(2026-07-31, PR #1102 merge main `2ecfe4b5` → `make deploy-web` 전체 스코프: web-a/web-b 무중단 롤링 + insight-worker/ask-worker 재생성 + gateway reconcile, post-cutover soak 90s 통과. **4서비스 GIT_COMMIT=2ecfe4b5 running/healthy**, edge `/healthz` ok·mysql_ok·pg_ok).
  **배포본 런타임 실증(ask-worker)**: 시간 방향 계약 적재 True · BEFORE/AFTER True · `PRECONDITION`+`결함/문제/위험` 금지 True · 🔴/🟡 배지 금지 True · "실행되지 않았다/실패했다" 금지 True · "적용 전제 / 배포 순서" 절 계약 True · **라이브 대조 강제 문구 존속 True**(회귀 0) · L2 힌트 미발견 오류에 발동 True·3분기 True·무관 오류 잡음 0 True · MySQL/MSSQL `MATCH_SNIPPET` True · 전체열거 상수 `''` True · `(본문 외 매칭)` 라벨 True.
  **라이브 compose 경로 실증(가장 중요)**: 실 `agent_memory` 연결로 `compose_system_prompt` 호출 → 결과(13,604자)에 `REVIEWING A PROPOSED CHANGE — TIME DIRECTION` **도달 확인**. 즉 운영자 global row 가 base 를 대체하는 실제 프로덕션 조건에서도 계약이 살아 있다(AUTH-1a 설계 검증). **라이브 대화 실측 미수행** → `unverified-live`.
- **source**: 사용자 명시 호출 `/_dqa:conversation_audit "SQL 쿼리 코드 리뷰"` (2026-07-30) — "곧 적용될 쿼리 구조를 기준으로 답변하는게 아니라 항상 현재DB를 기준으로 불평하듯 주의사항을 전달".
- **last_seen**: 2026-07-30 · **seen_count**: 1 · **seen_distinct_conv**: 12 (60일 서명 노출)
- **modality**: 1:1 동기(대상) + 그룹 비동기(`…b5f40d99`) · **product_id(마스킹)**: P-119 외(117/114/109) · **conv(마스킹)**: `…a2efa955`(topic "SQL 쿼리 코드 리뷰") · 대조군 `…4348bc34` · `…b5f40d99` · `…7af6ae1c` · `…5cef7aa2` · `…eb3f79c0` · `…a48a40c8` · `…a8b43197`
- **symptom_confidence**: high (사용자 명시 보고 + 라이브 A/B 대조쌍 재현) · **rootcause_confidence**: high (프롬프트 file:line + PG core_messages/core_attachments 삼각측량 + 통제된 A/B 대조)
- **suspected_layers**: **L1**(프롬프트 합성 — 첨부↔실 DB **차이의 해석 계약**이 없어 프레임이 모델 재량) · L2 동반(미발견 도구 오류가 결함 신호로 읽힘)
- **증상(signal)**: `E-USR` 명시 보고 + `I-FALSE` 허위 결함 단정 + `I-SIL`(대상 대화 최종답 이후 무응답 종료). 대상 답변은 최상단을 "0. 배포 순서 의존성 (가장 중요)" 로 열고 "`gunzlog.steampaymenthistory` 테이블은 **아직 존재하지 않습니다**", "`concurrentusers5rocks_gunz` 는 현재 `ServerID` 컬럼도, PK도 **전혀 없습니다**" 를 핵심 지적으로 배치했다 — **둘 다 사용자가 같이 첨부한 `T_*.sql` 이 만들어내는 것**이다. `…b5f40d99` 는 미적용 마이그레이션을 두고 "스크립트의 **동적 ALTER 로직이 실제로 실행되지 않았거나 실패한 상태**입니다" 라고 단정(허위 결함)했고, 답변 4건이 "예상 구조 vs 실제 구조" 표로 미배포 상태를 🔴 **결함**·"데이터 무결성 위험" 으로 채점했다.
- **결정적 증거(A/B 대조쌍)**: 동일 5개 파일(sha256 **일치**, attachment 647~651 ↔ 652~656)·동일 요청문("첨부파일의 쿼리 리뷰를 진행해주세요.")이 **3분 간격** 두 대화로 갈렸다 — `…4348bc34`(16:43, **도구 0회**)는 논리·성능·보안·운영 축의 코드 리뷰(사용자가 원한 형태), `…a2efa955`(16:46, 도구 12회)는 현재-DB 부재 지적 중심. 입력이 같고 출력 프레임만 갈렸다는 것은 **결함이 모델 능력이 아니라 계약 부재**라는 직접 증거다.
- **confirmed_root_cause**: `agent_core.py` SYSTEM_PROMPT §ATTACHED FILES(:119-124)와 첨부 주입 INSTRUCTION(`_build_attachment_context_section`, :~1272)이 "첨부 vs 실 DB 주장은 반드시 라이브 검증"(FR-partial-evidence 계보)만 규정하고 **그 차이가 무엇을 의미하는지(시간 방향)** 는 규정하지 않는다. 여기에 누적된 부재·완전성 grounding(:104-111 — FR-partial-evidence·FR-false-absence·FR-false-truncation 봉인)이 "존재 여부" 를 극도로 부각시켜, 모델의 기본 프레임이 **라이브 DB=정본 스펙 / 첨부=그에 미달하는 후보** 로 굳었다. 재발경로 = `model limit`(계약 없는 자리를 기본 프레임이 채움) + `data/config drift`(코드 상수가 운영자 global row 로 대체 가능) → **코드가 권위선**.
- **선행 봉인의 2차효과(계보)**: FR-false-truncation-belief 가 FR-partial-evidence 의 역방향 과발동이었던 것과 **같은 축**이다 — grounding 을 강화할수록 "존재/부재" 판정이 답변의 중심으로 올라오고, 그 판정에 **시간 방향**이 없으면 미적용 상태가 결함으로 읽힌다.
- **corroboration**: **structural** — 60일 `.sql` 첨부 대화 **96건 중 12 distinct_conv(≈12.5%)** 의 장문 답변이 현재-DB 부재 프레이밍을 담는다. 도구측 미발견 오류(`doesn't exist`/`Unknown column`/1146 등)는 같은 기간 7 distinct_conv.
- **거짓양성 기각(`refuted`)**: ① **red-team 자가검증 증폭 아님** — 대상 두 대화의 `redteam_reviews`(171·173) 모두 `verdict=pass`·`revision_applied=false`·`block_count=0`. ② **라이브 대조 자체는 결함 아님(F4)** — 같은 답변의 "기존 1,710행에 (ReportTime, PublisherID) 중복 0건 → PK 추가 충돌 없이 성공" 은 라이브 대조의 **정확한 용법**이며, 선행 FR-mssql-crossdb 계열이 고친 것은 정반대(대조 없이 리뷰). 따라서 수정은 대조를 줄이는 방향이 아니라 **차이의 분류**를 정하는 방향이어야 한다(보안·정확성 회귀 방지의 축).
- **봉인(A+B+C, 사용자 승인)**: (A) `_ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE` 를 `compose_system_prompt` `parts` 에 always-append — 라이브 DB=BEFORE / 첨부 세트=AFTER, 변경이 도입하는 차이는 적용 전제이지 결함 아님(결함 어휘·심각도 배지·"실행 실패" 단정 금지). 운영자 global row drift 무관(AUTH-1a). (B) 출력 구조 계약 — 전제는 "적용 전제 / 배포 순서" 한 절, 배지·결함 목록은 적용 후에도 남는 문제에만, 본문은 적용 후 상태 기준. (C) L2 `_proposed_change_hint()` — 미발견 시그니처에만 **3분기** 분류 교정(적용 전제 ↔ 진짜 선행 누락 ↔ 권한·스코프·오타, 교차확인 전 단정 금지). **라이브 대조 강제·0행≠부재 규칙 불변**(회귀 테스트로 고정). 가드/allowlist/RBAC 무변경.
- **disposition 근거**: Major(§12.3 — 코어 시스템 프롬프트, 모든 첨부 리뷰 답변에 영향) → attended human-decision. structural corroboration + 코드 file:line confirmed(high) + A/B 대조쌍으로 계약 부재 직접 실증 → fix-now. 사용자가 AskUserQuestion 으로 범위 **A+B+C 전부** 명시 선택(2026-07-30) → PLAN-APPROVED 후 구현.
- **fix**: `CHG-20260730T190000-review-proposed-change-framing` / **코드 거주 `feature-0002-agent-core`** / `REV-20260730T190000-review-proposed-change-framing`(§18.8.2 제약-없는-채널 우선 → codex 3렌즈 security+backend+regression, **[P1] 0건**, [P2] 4건 중 스니펫 라벨 오단정·힌트 일방면책 2건 흡수 수정, 컬럼 가변·본문 노출 2건 근거 기록 수용).
- **rc_ids**: RC-1 · **batch-id**: B-20260730T190000-review-proposed-change-framing
- **후속 규명(2026-07-31, 중요)**: A/B 대조쌍이 갈린 **실제 기전**이 후속 조사에서 확정됐다 — 라이브 운영자 프롬프트에 "명시 요청 없이 execute_sql 금지"+"첨부 지침 우선"(코드에서는 2026-07-14 제거된 환각 유발 지시)이 살아 있어, 동적 INSTRUCTION 의 "반드시 라이브 검증" 과 한 프롬프트 안에서 **정면 충돌**했다. 도구 0회 run 은 정적 억제를, 12회 run 은 동적 검증을 따랐다. 본 cycle 의 시간-방향 계약은 DB-확인 분기의 **프레임**을 고쳤고, 모순 자체는 `FR-operator-global-prompt-shadows-code-seals` 가 제거했다(PR #1114, main `954adc87` 배포).
- **라이브 실측 필요분(§정직)**: 코드/테스트는 "계약이 항상 주입되고, 운영자 global row 대체를 견디며, 선행 grounding 을 약화하지 않고, 미발견 힌트가 3분기로 붙는다" 까지만 증명한다. **"실제 리뷰가 적용 후 기준으로 쓰이는지"** 는 배포 후 실측분(미수행) → 배포 후 동일 5파일 재리뷰 + 다음 audit 이 corroboration(SQL 첨부 대화의 현재-DB 부재 프레이밍 distinct_conv) 재측정 → 감소 시 `verified`, 재증가 시 `regressed`.
- **필요한 사람 액션(1줄)**: PR 생성·deploy confirm(Major — override 불가) → 배포 후 동일 첨부로 라이브 재리뷰 + `/_dqa:doc_sync`.

## FR-review-precondition-assumed-not-verified — triaged (L1 2차효과 의심; 시간-방향 계약이 '적용 후 가정'으로 과교정돼 적용 가능성 검증을 건너뜀)

- **status**: `fixed:deployed:unverified-live` — corroboration 측정 후 봉인(사용자 지시 + 범위 승인 **A+C**) + **배포 완료**(2026-08-03, PR #1126 merge main `99d09137` → `make deploy-web` 전체 스코프, soak 통과, **4서비스 GIT_COMMIT=99d09137 healthy**).
  **배포본 런타임 실증(ask-worker)**: 계약 9요소 전부 LIVE — 검증-또는-미확인 · 미확인=1급 값 · 거부/스코프/미조회⇒미확인 · **0행 범위 조건부**(과교정 방지) · 커버리지 명시 시에만 부재 · 첨부 `IF NOT EXISTS`≠증거 · 미확인은 공짜 아님 · 조회 시도 의무 · `verify > 미확인 > guess`. 라이브 `compose_system_prompt`(19,764자)에 계약 도달 확인, 선행 seal(`ZERO ROWS IS NOT ABSENCE`) 공존. (미러는 운영자 global row 대체로 미도달 — `FR-operator-global-prompt-shadows-code-seals` 의 기지 조건이며 bootstrap 경로 전용이라 결함 아님.)
  **배포 시 1회 실패·재실행(정직 기록)**: 1차 배포는 insight-worker 헬스 미도달로 워커군이 last-good 롤백돼 **web 만 신코드** 인 부분 완료로 끝났다(`DEPLOY_RC=2`) — 즉 그 시점엔 프롬프트 수정이 **라이브에 없었다**. 원인은 내 코드가 아니라 배포 창의 일시적 네트워크 버스트(모든 datasource `probe-tcp timeout`; 롤백본에서도 동일 증상, 이후 양 워커에서 동일 datasource 직접 probe 는 정상). insight-worker 자체 회복 후 재실행(멱등)해 RC=0.
  **완료 판정(측정으로만)**: 배포 직후 스냅샷 = 미검증 47.8% / `미확인` **2개**(0개→2개, 첫 사용). 90일 창이라 과거 대화가 지배하므로 즉시 움직이지 않는다 — **새 리뷰 대화가 쌓인 뒤** `python3 bin/measure-precondition-grounding.py --days 30` 로 재측정해 **비율 < 47.8% + `미확인` 증가**면 `verified`, 재증가면 `regressed`.
- **corroboration(측정 완료 — structural)**: 90일 `.sql` 첨부 대화 87건에서 객체 상태 단정 **90건 중 43건(47.8%)**이 그 대화의 어떤 도구 결과에도 그 객체명이 없다. **`미확인` 표기는 0건** — 이 서비스는 지금껏 객체 상태에 "미확인" 을 한 번도 쓴 적이 없다. 관측 구간 2026-05-28~08-03.
- **귀속 정정(중요·정직)**: 최초 보고에서 이를 "내가 만든 계약 결함(2차효과)" 으로 단정했으나 **측정이 그것을 반증했다**. 이 행동은 시간-방향 계약(2026-07-30 출하) **이전부터 광범위**하다. 정확한 진단은 (1) **오래된 구조적 공백** — 상태 단정에 객체별 검증을 요구하는 규칙이 없었고 `미확인` 이 출력 값으로 제시된 적이 없다, (2) **내 계약의 기여** — `적용 전제` 절이 그 단정에 표 형태의 눈에 띄는 자리를 줬고 "stated as fact" 가 확정 압력을 더했다(원인 아닌 **가중 요인**). rootcause_confidence low → **high**.
- **source**: `FR-review-frames-live-db-as-spec` 봉인의 **라이브 육안검증 중 부수 발견** — 사용자 지시("실제 웹브라우저 조작을 통해 육안검증까지").
- **last_seen**: 2026-08-03 · **seen_count**: 1 · **seen_distinct_conv**: 1(재현 대화 `20260803081201-969946a2`)
- **symptom_confidence**: high (ground truth 직접 대조로 오류 확정) · **rootcause_confidence**: low (관측 확정, 코드 경로 미추적 — 프롬프트 2차효과 **가설**)
- **suspected_layers**: **L1**(시간-방향 계약의 2차효과 가설) ↔ **L6**(모델이 검증 의무를 건너뜀)
- **증상(signal)**: `I-FALSE` 미검증 부재 단정. 답변의 `적용 전제` 표가 `ConcurrentUsers5Rocks_gunz 테이블 | ✅ 신규 생성 예정 | **현재 미존재**` 라고 적었으나, 같은 datasource 직접 조회 결과 **실존**(`gunzlog.concurrentusers5rocks_gunz`, 약 **1,478,400행**, `ServerID` 컬럼 없음). 그 run 의 도구 호출 4건 중 **이 테이블을 조회한 것은 0건**이다.
- **실질 손해(중요)**: BEFORE 답변(…a2efa955)은 이 테이블이 실존·PK 부재임을 확인하고 "PK 추가가 기존 데이터 중복으로 실패할 수 있다 → (ReportTime,PublisherID) 중복 0건" 까지 검증했다. AFTER 답변은 미존재로 **가정**해 그 검증을 건너뛰어 **148만 행 테이블에 3중 복합 PK 를 추가하는 실제 마이그레이션 리스크를 놓쳤다**.
- **방향 반전**: 원 마찰이 "현재 DB 기준 과잉 불평" 이었다면 이 잔여는 **"적용 후를 가정한 과소 검증"** 이다. 시간-방향 계약이 명시한 라이브 대조 목적 **(a) 적용 가능성**(새 PK/UNIQUE 를 위반하는 기존 데이터)이 지켜지지 않았다 — 계약 문구는 이를 요구하므로 **계약 공백이 아니라 준수 실패**이며, 그래서 수정 후보가 프롬프트 강화인지 도구 강제인지 아직 미확정(rootcause low).
- **red-team 은 이 건을 못 잡았다**: `verdict=revise`·`block_count=1`·`unresolved=1` 로 BLOCK 은 냈으나 지적은 (i) 첨부 excerpt PK 근거 부재 (ii) `Log_AccountUpdateCash` 정의 미확인 두 건이고 `현재 미존재` 오단정은 미포함. 또한 **`revision_applied=false`·`revision_rounds=0`** — 수정 라운드가 돌지 않아 `⚠️ 내부 자가 검증 미해소` 배너와 함께 전달(정직하나 BLOCK→수정 미연결). **별도 추적**: feature-0021.
- **disposition 근거**: `report-only`/`triaged` — 단일 관측 + corroboration 미측정 + rootcause low + 수정 후보가 Major(코어 프롬프트). Phase 7 의 "명백한 구조결함" 예외를 쓰려면 코드 file:line 확정이 필요한데 아직 없다(모델 준수 실패일 수 있음).
- **봉인(A 계약)**: `_ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE` 에서 **"stated as fact" 제거 → "모든 행은 검증된 사실이거나 `미확인`"**. `미확인` 을 1급 값으로 승격(미검증 존재/미존재가 정직한 미확인보다 나쁘다 — 사용자가 그걸 믿고 행동한다). 권한거부·스코프경고·미조회 ⇒ 미확인(부재 아님). **0행은 범위 조건부** — 정확한 식별자 + 도구가 커버리지를 명시한 경우에만 그 범위 내 부재로 말하고 범위 병기(과교정 방지). 첨부의 `CREATE TABLE IF NOT EXISTS` 는 현재 존재 증거 아님. **미확인은 공짜가 아님** — 결정이 걸린 객체는 최소 1회 조회 시도 의무(`verify > 미확인 > guess`). SYSTEM_PROMPT 미러도 동일 3요소 정합.
- **봉인(C 감지기)**: `bin/measure-precondition-grounding.py` — 상태 단정 ↔ 도구 호출 대조를 재현 가능하게 재는 **스크린**(지표 아님, 오탐·누락 명시). RO 트랜잭션 + statement_timeout + `ON_ERROR_STOP` + 빈 결과 fail-closed. 감지기 자체를 회귀 테스트 10건으로 고정 — §18.8 R3 가 **성공 신호(`미확인` 카운터)가 영원히 0** 이던 감지기 결함을 잡았기 때문(감지기가 조용히 틀리면 "수정이 작동한다" 는 거짓 결론이 난다).
- **fix**: `CHG-20260803T190000-precondition-verified-or-unknown` / **코드 거주 `feature-0002-agent-core`** / `REV-20260803T190000-precondition-verified-or-unknown`(codex 3라운드 — R1 [P1]1+[P2]3 → R2 [P1]2+[P2]3 → R3 [P1]0+[P2]1, 전건 수정).
- **완료 판정(측정으로만)**: 배포 후 `python3 bin/measure-precondition-grounding.py --days 30` 재실행 → **미검증 비율이 baseline 47.8% 아래로** + **`미확인` 객체 수 > 0**(현재 0) 이면 `fixed:deployed:verified`. 재증가 시 `regressed`.
- **필요한 사람 액션(1줄)**: PR·deploy confirm(Major — override 불가) → 배포 후 위 감지기 재실행.

## FR-routine-content-scan-missing — rejected (F3 이미 구현·배포·라이브 사용중; 체감 갭만 개선)

- **status**: `rejected` — **도구 부재가 아니다**. `search_routines`(FR-false-absence-zero-row-catalog-scope lever A, 2026-07-28 배포 PR #991 main `21b67ade`)가 이미 **이름 + 정의 본문(`ROUTINE_DEFINITION`) + 주석**을 검색한다(`dialects.py` MySQL:337-/MSSQL:678- · `tools._tool_search_routines`). 신설 대신 표현 갭만 개선.
- **source**: 위 audit 과 동일 호출 — "assistant가 단일 함수 및 프로시저를 확인하는 도구는 있지만 특정 내용을 포함하는 함수 및 프로시저를 탐색하는 도구가 없어 추가가 필요합니다 (scan)".
- **last_seen**: 2026-07-30 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **기각 근거(데이터)**: ① 사용자가 지목한 바로 그 대화(`…a2efa955`)에서 **실제로 동작**했다 — msg 6317 이 keyword `Log_AccountUpdateCash` 로 **이름에 그 문자열이 없는 호출자 4개**(`Game_BuyCashItem_Steam`·`Game_ConvertCash`·`Game_GiftCashItem_Steam`·`Steam_AccountChargeCash`)를 반환했다. 이름 검색만으로는 구조적으로 불가능한 결과이므로 본문 검색이 살아 있음을 증명한다. ② 같은 대화 msg 6331/6332 도 `search_routines` 호출. ③ 30일 사용량 **23회 / 7 distinct_conv**. ④ 도구 정의(`TOOL_DEFINITIONS`)에 "이름뿐 아니라 **정의 본문**도 검색" 명시.
- **실재한 갭(개선 출하)**: 결과가 `schema | routine | type` 목록뿐이라 **어느 부분이 매칭됐는지** 알려면 후보마다 `describe_routine` 을 다시 불러야 했다 — 후보가 여러 개면 그 왕복이 탐색을 접게 만든다. 사용자 선택(AskUserQuestion 2026-07-30)에 따라 **매칭 스니펫 컬럼** 출하: `REQ-20260730-routine-match-snippet`(같은 CHG). 빈 스니펫은 `(본문 외 매칭)` + 원인 주석(이름·주석 매칭 또는 LIKE 와일드카드)으로 표기 — `(이름 매칭)` 단정은 §18.8 codex P2 로 기각됨.
- **교훈(원장 기록)**: 사용자가 "도구가 없다" 고 보고해도 **도구 부재 ≠ 도구 미인지**다. 이 건의 실체는 결과 표현이 근거를 안 보여줘 도구가 한 일이 사용자·모델 양쪽에 안 보였던 것이다. 부재 보고는 라이브 호출 로그(`core_messages.name`)로 먼저 반증한다.

## FR-datetime-tz-server-vs-stored — fixed:undeployed (L1 grounding 지침 lever)

- **status**: `fixed:undeployed` — L1 프롬프트 lever(`_DATA_GROUNDING_GUIDANCE` 신설·항상 주입) 출하, 배포 전. 배포 후 시각-필터 질의에서 저장값 TZ 추측 대신 확인·가정 명시 관측 시 `fixed:deployed:unverified-live` 로 전이.
- **source**: DQA 마찰개선사항_20260722_v2.md B-1(라이브 대화 아닌 AI 작업자 집계작업 관측 — provenance 정직 표기). `/_template:entry` 로 검토·개선.
- **last_seen**: 2026-07-22 · **seen_count**: 1 · **seen_distinct_conv**: 1 (FGT 집계 세션)
- **symptom_confidence**: high (작업자 명시 + 데이터 교차검증으로 재현) · **rootcause_confidence**: high (동작 원인 명확 — 프롬프트에 저장값 TZ grounding 부재)
- **suspected_layers**: **L1**(프롬프트 grounding 부재) — 모델이 `@@time_zone`(서버 설정)을 저장값 의미로 오해석
- **증상(signal)**: `I-FALSE` 거짓 확신 — assistant 가 서버 TZ 설정(Asia/Tokyo)만 보고 "저장값=JST → -9h=UTC" 라고 확신 오판. 실제 저장 DATETIME 은 UTC(MySQL DATETIME 은 TZ 미저장) → 집계 기간 9시간 어긋날 뻔(전 시트 오염 위험). 사용자 경고 + 오픈시각↔가입 램프업 정렬 교차검증으로 겨우 정정.
- **confirmed_root_cause(요지)**: 시스템 프롬프트에 "서버 TZ 설정 ≠ 저장값 의미(naive DATETIME 은 TZ 미저장)" grounding 이 없어, 모델이 `@@time_zone`/`NOW() vs UTC_TIMESTAMP()` 를 저장값 기준 TZ 로 오추론. 게임-무관·모든 MySQL datasource 일반.
- **fix**: TASK-20260722-dqa-data-grounding / `feature-0002-agent-core` `_DATA_GROUNDING_GUIDANCE`(타임존 블록: 서버 TZ≠저장값 명시 + 불확실 시 알려진 기준점 데이터 교차검증 + 변환 가정 답변 명시 + 미확정 시 임의 offset 금지). Major(core 시스템 프롬프트). test_gc_dialect_context 3건.
- **필요한 사람 액션(1줄)**: (후속·별도) datasource 메타데이터에 "저장값 기준 TZ" 명시 필드 + 시각-필터 질의 시 자동 표면화(스키마·UI 붙는 큰 lever) — 이번엔 즉효 프롬프트 grounding 만.

## FR-enum-code-hallucination — fixed:undeployed (L1 grounding 지침 lever; D-2 분리저장 동반)

- **status**: `fixed:undeployed` — L1 프롬프트 lever(`_DATA_GROUNDING_GUIDANCE` ENUM·분리저장 블록) 출하, 배포 전.
- **source**: DQA 마찰개선사항_20260722_v2.md D-1(+D-2 분리저장). 라이브 대화 아닌 집계작업 관측(provenance 정직).
- **last_seen**: 2026-07-22 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **symptom_confidence**: high (정본 LogType 사전과 대조로 오류 확정) · **rootcause_confidence**: high
- **suspected_layers**: **L1↔L4**(프롬프트 grounding 부재 + KB ENUM 사전 미매칭 시 폴백 없음)
- **증상(signal)**: `I-FALSE` — CurrencyType 코드를 기억으로 "3=Stamina" 환각(정본 4=스태미너). 코드 오지정 시 완전히 틀린 집계. 병행 D-2: 재화가 Gold/GemV2/Currency 테이블 분리 → "전체 재화" 를 한 테이블만 집계하면 조용한 누락.
- **confirmed_root_cause(요지)**: GLOSSARY & ENUM VALUES 주입 인프라(L1574)는 있으나 미매칭 시 모델이 환각으로 코드↔의미를 지어냄. 프롬프트에 "코드 의미 추측 금지 → 사전/샘플링 grounding 또는 미보유 고백" 지침 부재.
- **fix**: TASK-20260722-dqa-data-grounding / `feature-0002-agent-core` `_DATA_GROUNDING_GUIDANCE`(ENUM 블록: 코드 의미 지어내기 금지 + GLOSSARY & ENUM VALUES·`get_sample_rows`/`GROUP BY` 분포 확인·미보유 고백 / 분리저장 블록: "전체 X" 커버리지 명시). Major(core). test 포함.
- **필요한 사람 액션(1줄)**: (해당 게임 KB 데이터) KR_LIVE 제품 ENUM 사전에 CurrencyType/ChangeReasonType 정본 적재는 데이터 입력(코드 아님) — 지침이 미보유 시 환각 대신 고백을 강제하므로 안전판 확보.

## FR-scratch-result-csv-missing — fixed:undeployed (L7 결과추출 lever)

- **status**: `fixed:undeployed` — scratch_sql 결과 CSV export 구현, 배포 전.
- **source**: DQA 마찰개선사항_20260722_v2.md F-5/C-3.
- **last_seen**: 2026-07-22 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **symptom_confidence**: high · **rootcause_confidence**: high (코드 경로 확정)
- **suspected_layers**: **L7**(결과 추출/다운로드) — scratch 결과가 inline 절단 + `/shared/out` CSV 미export
- **증상(signal)**: `E-AST` 대량 결과 회수 곤란 — cross-DS 병합(scratch_sql) 결과가 미리보기(~200행) 절단 + CSV 미저장 → 수백 행 결과를 사용자가 회수 불가(execute_sql 은 CSV 저장됨과 비대칭).
- **confirmed_root_cause**: `scratch.run_sql` 이 미리보기 상한까지만 fetch 하고 `save_csv` 미호출. execute_sql 은 전체 fetch + save_csv + "CSV 저장:" emit → 웹 `CSV_PATH_RE` 파싱으로 다운로드 링크 생성. scratch 만 그 경로 부재.
- **fix**: TASK-20260722-dqa-scratch-csv-export / 코드 `feature-0002-agent-core`(정본 feature-0022) — `run_sql` export 상한(100000)까지 전체 fetch + `_tool_scratch_sql` save_csv parity. 프론트 무변경(기존 CSV_PATH_RE 재사용). Minor(비파괴 결과추출). test_scratch 3건.
- **필요한 사람 액션(1줄)**: 없음(자기완결) — 배포 후 라이브 e2e(대량 scratch 병합→CSV 다운로드)로 verify.

## FR-nl2sql-schema-discovery-giveup — fixed:deployed:unverified-live (L1+casing 프롬프트 lever; L2 deferred)

- **status**: `fixed:deployed:unverified-live` — **부분 수정**: L1 프롬프트 lever(능동 해석 modality 무관 일반화 → 1:1 도 주입; assume-vs-ask·give-up 금지) + casing 프롬프트 lever(MySQL 식별자 표기 보존·소문자화 금지) 출하·배포. **단 L2 lever(거부/에러 피드백에 교정 힌트 부착)는 미구현 — report-only 유지**(single-conv idiosyncratic·Major, corroboration 임계 미달 → 임계 돌파 시 plan 후 promote). live 재감사 측정 전이라 `unverified-live`(거짓 `verified` 금지).
- **fix(요지)**: TASK-20260629T142624-active-interp-modality / `feature-0002-agent-core` / REV-20260629T142624 (§18.8 AGENT-TEAM 패널, BLOCKER1+MAJOR3 전부 적대검증 REFUTED). PLAN-APPROVED. 가드 경계 불변(advisory 프롬프트 일반화 한정).
- **last_seen**: 2026-06-26 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **modality**: 1:1 동기 · **product_id(마스킹)**: P-94 · **conv(마스킹)**: …91655acc
- **symptom_confidence**: high (명시 신호) · **rootcause_confidence**: med (코드 경로 후보 확정, file:line 단정은 추가조사 필요 → `inconclusive→med`)
- **suspected_layers**: **L2↔L8** (datasource 스키마 dialect/casing + tool 피드백 모순) + **L1** (프롬프트: ambiguous 요청에 assume-vs-ask 정책)
- **증상(signal)**: `E-AST` 과도 재질문·장황 무행동 — NL2SQL assistant 가 turn1 에서 tool 8회(search_tables×4·execute_sql×3·describe_table) 소비 후 스키마를 못 특정해 **포기**, 사용자에게 "스테이지 정의?/기준?/기간?" 대량 재질문. 사용자는 turn2 에서 짧게 재지시(`E-USR` over-spec/좌절 신호).
- **confirmed_root_cause(요지)**: assistant 가 존재하지 않는 스키마명(`dbgame`/`dblog`, 추정 lowercase)을 추측 → `execute_sql` 가 `1049 Unknown database 'dbgame'` 반환·`SCHEMA()=NULL`(기본 DB 미선택). 동시에 `describe_table` 는 같은 경로에 응답을 돌려줘 **tool 간 모순 피드백** → 모델이 자기교정 못 하고 give-up. 재발 메커니즘 = `data/config drift`(datasource↔스키마 바인딩) + `model limit`(거부/에러 피드백에 교정 힌트 부재, L2).
- **corroboration**: 최근 14일 `Unknown database/1049` 시그니처 = **distinct_conv 1** → **idiosyncratic**(임계 미달, 전역수정 자격 없음). 표본 부족.
- **disposition 근거**: 수정 후보가 프롬프트(assume-vs-ask)·tool 거부 피드백(교정 힌트)·datasource 스키마 해소(casing) 로 **Major**(코어 LLM 경로). 단일 대화 + idiosyncratic + Major → `report-only`. 자동 fix-now 금지(저흔적 이탈 예외는 Minor 한정).
- **필요한 사람 액션(1줄)**: ~~(b) 모호 요청에 1회 합리적 가정 후 진행 vs 재질문 기준(L1)~~ **→ 출하**(능동 해석 일반화 + casing 프롬프트, TASK-20260629T142624). **잔여 (a)**: `search_tables`/`describe_table`/`execute_sql` 거부·0행에 **교정 힌트**(올바른 datasource·스키마 casing 후보) 부착(L2 코드 lever) — single-conv idiosyncratic·Major 라 report-only 유지, corroboration 임계 돌파 시 plan 후 재triage. 코드 거주: `feature-0002-agent-core`.

## FR-resultset-table-narration-mismatch — report-only

- **status**: `report-only` · **last_seen**: 2026-06-26 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **modality**: 1:1 · **conv(마스킹)**: …91655acc
- **symptom_confidence**: med-high · **rootcause_confidence**: low (표면 관측, 코드 경로 미추적)
- **suspected_layers**: **L7** (표시·표 렌더 truncation) ↔ **L3** (narration 이 표시 안 된 행을 인용)
- **증상(signal)**: `I-FALSE` 거짓 성공 — turn2 최종답이 표 헤더 "상위 7개" 라 쓰고 **5행만 렌더**, 첨부 CSV 는 "전체 7행", 그런데 서술("주요 발견사항")은 **표에 없는 행**(상위에 안 뜬 고-도전 스테이지)을 핵심 근거로 인용 → 사용자가 보는 표와 서술이 불일치. 추가로 랭킹이 n=1 짜리 0% 행을 통계적 무의미하게 상위 배치. turn2 직후 **user 무응답 종료(`I-SIL` 침묵 이탈)**.
- **disposition 근거**: 단일 대화 표본, 코드 경로 미추적(rootcause low) → `report-only`. 표/서술 정합·min-attempt 임계는 표시 계약(L7) 또는 결과 요약 프롬프트(L1) 결정 필요.
- **필요한 사람 액션(1줄)**: 결과 표 truncation 정책과 narration 의 "표시된 행만 인용" 계약을 정할지 결정(L7/L1). corroboration(표/CSV 행수 불일치 빈도) 미측정 — 정량화 어려움, 추가 신호원 discovery 필요.

## FR-diff-lineno-prefix-leak — fixed:deployed:unverified-live

- **status**: `fixed:deployed:unverified-live` (Minor 수정·테스트 PASS·적대패널 SAFE → **배포 완료** PR #467 머지 main `5942a25` + web 재배포(`/healthz` git_commit=`5942a25` live·서빙 app.js byte-identical main). 다음 audit corroboration(```diff+`\d+→` distinct_conv) 재측정 0 유지 시 `verified`. PB-0008 실 Windows 브라우저 시각검증은 WSL 미실행 — 사용자 확인 권장.)
- **last_seen**: 2026-06-29 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **modality**: 1:1 동기 · **conv(마스킹)**: …356708b8 (topic "계정 연동 및 보상 일괄 수령 쿼리 구성", assistant msg id 4058)
- **symptom_confidence**: high (사용자 명시 보고 `E-USR` + 데이터 재현) · **rootcause_confidence**: high (코드+DB+전사 삼각측량, file:line 확정)
- **suspected_layers**: **L1↔L6**(프롬프트 금지지침 vs 모델 준수 실패)가 **L7**(렌더러)에서 표면화
- **증상(signal)**: assistant 가 ```diff 블록 context 줄에 `45→\t…` 줄번호+화살표 prefix 를 그대로 출력 → 웹 렌더러가 코드 본문으로 표시해 줄 표현 깨짐(변경줄만 표준 `+`/`-`).
- **confirmed_root_cause**: agent_core `_number_file_lines`(feature-0002, TASK-0256e)가 첨부 본문 각 줄에 `<N>→` 줄번호 prefix 주입(의도된 기능). 프롬프트(agent_core.py:770-778)가 "diff 안 `<N>→` 금지" 지시하나 모델이 가끔 context 줄에 복사(model limit). 웹 렌더러 `buildDiffRows`(feature-0003 app.js·share.js)가 누출 미정규화 → `45→` 가 코드로 렌더. 재발경로=model limit → **렌더러를 결정론적 최후 방어선으로 봉인**(모델 누출 무관 매번 차단·기존 저장 메시지도 render-time 정상화).
- **corroboration**: 전체 기간 ```diff 사용 대화 20건 중 누출 1건 → **idiosyncratic**(빈도 임계 미달). 단 **사용자 명시요청 + RC 코드 확정 + 결정론적 저위험 봉인** → fix-now(자기-주입 artifact 정규화라 과적합 아님).
- **fix**: `CHG-20260629T172122-diff-lineno-prefix-leak` (코드 거주 **feature-0003-agent-web-ui**: app.js·share.js `buildDiffRows` 누출 정규화 `/^\s*(\d+)→/` + `tests/verify_diff_lineno_leak.mjs` 30/30 PASS). 위험등급 **Minor**(L7 display-only). 적대패널 `[SUBAGENT:adversarial-correctness]` REFUTED(BLOCKING 0, H2 오매칭=cosmetic NIT).
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260629T172122-diff-lineno-leak
- **deferred(cross-ref)**: agent_core 프롬프트 강화(feature-0002, Major·core LLM 경로) — 별도 batch. 렌더러 봉인이 누출 비가시화하므로 우선순위 낮음.
- **라이브 실측 필요분(§정직)**: 코드/테스트는 "렌더러가 누출 prefix 를 떼고 정상 diff 생성" 증명. "실제 사용자 화면 소멸" 은 배포 후 PB-0008 실 Windows 브라우저 실측분(미수행). 다음 audit 에서 corroboration(```diff+`\d+→` distinct_conv) 재측정 → 0 유지 시 `verified`.

## FR-edge-fallback-conversation-context-loss — fixed:deployed:unverified-live (L6↔L8 라우팅; 대화 답변 edge 폴백 봉인)

- **status**: `fixed:deployed:unverified-live` — 대화 답변(task='agent') 경로에서 edge(gemma) 폴백을 **구조적으로 완전 제거**해 배포. gemma 는 `-chat` 체인에서 도달 불가(config + G5 체인 가드 테스트로 고정). 두 계정 완전 장애 시 gemma 강등 대신 429/401 → 기존 LLM-error 핸들러가 "요청량 한도… 잠시 후 재시도" 정직 실패. **라이브 실측(실제 rate-limit 상황에서 gemma 미개입)은 rate-limit 조건 재현 의존이라 강제 불가** → corroboration 재측정이 0 유지 시 `verified`.
- **fix(요지)**: CHG-20260707T100640-no-edge-conversation-answer / **코드 거주 `feature-0002-agent-core`**(+ config `feature-0007`, 헬퍼 `shared`) / REV-20260707T100640-no-edge-conversation-answer (§18.8 적대 2렌즈 패널 backend/correctness C1~C5 + security/regression/litellm S1~S5 전부 REFUTE→CONFIRMED, NIT→G5 체인 가드 반영). PLAN-APPROVED(사용자 2026-07-07 결정 + 구현+검증+배포). PR #600 merge(main 2d590ce0) → ask-worker+web 재빌드(7381ef3b) + bedrock-gateway 재생성 + live probe(claude-haiku-4-chat→claude, gemma 아님) 확인.
- **last_seen**: 2026-07-06 (마찰 관측일; 수정 후 신규 gemma agent 턴 0) · **seen_count**: 1 · **seen_distinct_conv**: 2
- **modality**: 1:1 동기 · **product_id(마스킹)**: P-117 · **conv(마스킹)**: …9e0883bb (topic "DB 설계 및 JSON 데이터 구성 검토", owner admin)
- **symptom_confidence**: high (사용자 명시 불만 "? 맥락을 잃어버렸나요?" + 데이터 재현) · **rootcause_confidence**: high (코드+DB(llm_usage.resolved_model)+전사 삼각측량, file:line 확정)
- **suspected_layers**: **L6↔L8** (모델 라우팅/폴백 — litellm fallback 체인이 대화 답변까지 로컬 edge 모델에 도달; ctx 4096 이 히스토리 절단)
- **증상(signal)**: `E-USR` 명시 불만 + `E-AST` 맥락 무시 + `I-FALSE` 거짓 성공 — turn2(4341)에서 assistant 가 방금 자기가 쓴 9053자 리뷰(4339)조차 "설계 내용 미명시"라며 무관한 일반론(Orders 테이블·MongoDB) 환각 → 사용자 "? 맥락을 잃어버렸나요?"(4342) → turn3(4343) "이전 대화를 기억한다" 부인하면서도 여전히 맥락 부재.
- **confirmed_root_cause**: turn2~4 가 요청 모델 `claude-haiku-4` 인데 실제 서빙(llm_usage.resolved_model)이 `gemma4:e2b`(로컬 edge-fallback, ctx 4096)로 silent 강등 — prompt_tokens 세 턴 모두 정확히 **4096**(turn1=29K)로 ~30K 토큰 대화 히스토리가 통째로 절단돼 맥락 소실. 원인 체인 = `litellm_config.yaml` fallback `claude-haiku-4 → root → edge-fallback(gemma)`, 두 claude OAuth 계정이 429(오늘 rate-limit 버스트) 시 gemma 우회. 재발 메커니즘 = **infra capacity → degradation 정책**(2026-07-04 "무중단 안전망"이 실제로는 "조용한 파탄"). 봉인 = 대화 답변 전용 edge-free alias(`claude-haiku-4-chat`) + `_call_llm` 라우팅(표면 계약 아닌 라우팅 정책 축소) + 기존 깨끗한-실패 핸들러 재사용.
- **corroboration**: 최근 14일 task='agent' resolved_model gemma = **distinct_conv 2 / 4콜, 전량 2026-07-06(수정 전)**. 총 agent 대화 40 중 ~5%, 오늘 집중(만성 아님·재발경로는 반복 확실). 배포 후 2시간 신규 gemma agent 턴 0. distinct_conv 2>1 이라 순수 idiosyncratic 은 아니나, **근본이 코드/config 정본까지 confirmed(high) + 심각도 최상(대화 파탄·명시 불만·신뢰 상실)** → fix-now(사용자 결정으로 Major promote).
- **disposition 근거**: Major(코어 LLM 경로·가용성 정책, 2026-07-04 결정 함의) → attended human-decision. 사용자가 AskUserQuestion 으로 "gemma 완전 차단·명백한 실패처리" 명시 결정(2026-07-04 무중단 결정을 대화 경로에 한해 override) → PLAN-APPROVED 후 구현+검증+배포.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260707T100640-no-edge-conversation-answer
- **범위 밖(인지)**: context-feeding aux(summary/topic)·prompt_gen·node_analysis 는 여전히 gemma(ctx 4096) 강등 가능 — 사용자가 assistant 답변 경로로 명시 한정. 필요 시 후속 audit.
- **라이브 실측 필요분(§정직)**: 코드/테스트/게이트웨이 probe 는 "대화 답변이 edge-free alias 로만 claude 에 라우팅되고, 실패 시 정직 안내" 증명. "실제 rate-limit 시 gemma 미개입" 은 rate-limit 조건 재현 의존(강제 불가) → 다음 audit 에서 corroboration(task='agent' resolved_model gemma distinct_conv) 재측정 → 0 유지 시 `verified`, 재증가 시 `regressed`.
- **post-deploy 게이트웨이 오류 조사(2026-07-07 별도 investigation, no-op)**: 배포 직후(10:31~10:41 KST) `bedrock-gateway` 로그에 `claude-haiku-4-chat`→`-root` 양쪽 모두 `max_tokens must be greater than thinking.budget_tokens`(400, req `…qkA5N9…`/`…qkBzx…`) 1회 발생(10:37:18) 확인·조사. **근본원인=코드 결함 아님**: 실패 시각 기준 `ask-worker`/`insight-worker` 이미지(10:32:18 재빌드, dangling image 직접 오픈해 확증)가 이미 본 fix 코드 보유 — stale-image 가설 기각. `_call_llm`(유일 caller, `agent_core.py:2665`)은 claude-* 모델에 `max_tokens=20000`(`_CLAUDE_MAX_TOKENS["agent"]`)을 항상 주입해 게이트웨이의 고정 `thinking.budget_tokens=5000`(litellm_config.yaml)과 충돌할 코드 경로 자체가 없음(정적 추적 완료, 호출부 전체 1곳). 게이트웨이에 직접 재현 테스트: `max_tokens≥5000`→200 정상, `max_tokens<5000`→위와 문자열까지 동일한 400 재현. 컨테이너 기동 이후 전체 로그에 이 오류는 이 1회뿐(재발 0). **결론**: 위 "live probe(...) 확인" 절차(앱을 우회해 게이트웨이에 직접 보낸 수동 확인 호출)가 `max_tokens` 미설정/과소 설정으로 보낸 1회성 프로브 아티팩트 — 실 사용자 대화 트래픽 영향 없음(해당 request들에 연계된 실 conversation_id 없음). 코드 수정 불필요, `status`/corroboration 수치 변경 없음.

## FR-readonly-query-shapes-overblock — fixed:deployed:unverified-live (L5 sql_guard shape 과차단; read-only allowlist 정확 확장 + write-node defense)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트(전체 회귀 1899 PASS·§18.8 패널 MAJOR1 수정) + **배포 완료**(2026-07-13, PR #761 merge main `9892fc3b` → deploy-web 무중단 web-a/b + ask-worker/insight-worker 재빌드·재생성, 4서비스 GIT_COMMIT=9892fc3b; ask-worker 런타임 실증: UNION·SHOW CREATE TABLE·SHOW VARIABLES 허용 / 데이터수정CTE·UNION-agent_memory분기·SHOW GRANTS 차단 확인; web /healthz=9892fc3b). **라이브 대화 실측 미수행** → `unverified-live`. 다음 audit 에서 "보안 정책상 차단된 SQL" corroboration 재측정(UNION/Show 시그니처 감소) 시 `verified`.
- **fix(요지)**: CHG-20260713T171821-readonly-query-shapes / **코드 거주 `feature-0002-agent-core`** / REV-20260713T171821-readonly-query-shapes (§18.8 적대 3렌즈 패널 security+backend+qa — API 세션한도 조기종료→인라인 자기검증 완료, MAJOR1[데이터수정CTE 우회] 수정, 나머지 REFUTED). 사용자 승인=UNION + 읽기전용 SHOW(AskUserQuestion 2026-07-13).
- **last_seen**: 2026-07-13 · **seen_count**: 1 · **seen_distinct_conv**: 9 (corroboration structural)
- **modality**: 1:1 (추정) · **conv(마스킹)**: topic "동적 쿼리 및 테이블 변경사항 추가 리뷰"(`20260713074503-5cef7aa2`, product 95) 외 8
- **symptom_confidence**: high (사용자 명시 보고 + DB 재현) · **rootcause_confidence**: high (코드+PG agent_runtime 집계+전사 삼각측량)
- **suspected_layers**: **L5**(sql_guard SELECT/CTE-only shape 게이트가 read-only 패턴 과차단) — 실질 보안(쓰기·allowlist·금지함수·multi-statement)과 무관한 shape 가정 오류
- **증상(signal)**: `E-SYS`/`E-USR` — "보안 정책상 차단된 SQL". corroboration(PG core_messages 30일): `only SELECT/CTE allowed, got Union`(8, 최대)·`got Show`(5, SHOW CREATE TABLE/VARIABLES)·parse-fail(12)·multi-statement(4)·MSSQL db_id/db_name(3). 대상 대화 차단 2건 = `SHOW CREATE TABLE gunzgame.attendence`(테이블 변경 리뷰)·`SHOW VARIABLES LIKE 'lower_case_table_names'`.
- **confirmed_root_cause**: `sql_guard.py validate_sql_for_sandbox` shape 게이트가 root=`exp.Select`/`With` 만 허용 → 최상위 UNION(`exp.Union`)·읽기전용 SHOW(`exp.Show`)를 non-SELECT 라는 이유만으로 거부. 이전 describe_routine(FR-show-create-routine-blocked)은 프로시저 subset만 봉인. 재발경로 = model/guard 가정 오류(read-only 패턴을 unsafe 로 오분류).
- **봉인**: shape allowlist 를 read-only 로 정확 확장 — (a) set-op(UNION/INTERSECT/EXCEPT of SELECTs, 분기별 forbidden-schema/lock/into/금지함수 검사 유지) (b) read-only SHOW 화이트리스트(CREATE TABLE/VIEW·COLUMNS·INDEX·TABLE STATUS·VARIABLES/STATUS; GRANTS/DATABASES/PROCESSLIST 계속 차단; PROCEDURE/FUNCTION→describe_routine) + 대상 `.db` allowlist 강제. **부수 하드닝(§18.8 security 패널 MAJOR)**: write/DDL 노드 defense-in-depth — 데이터수정CTE(`WITH c AS (DELETE…) SELECT`)·중첩 write 거부(pre-existing 잠복). sql_guard SELECT-only 의 **실질 보안 불변식 유지**(보안 회귀 0).
- **corroboration**: structural — 30일 9 distinct conv·14건(UNION 8·Show 5 최대 버킷). 전역 수정 자격 충족.
- **disposition 근거**: Critical(sql_guard 허용범위) → attended 승인. structural corroboration + 코드 file:line confirmed + read-only 안전성(per-branch 검사·write-node defense) → fix-now.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260713T171821-readonly-query-shapes
- **범위 밖(deferred, report-only)**: parse-fail(12, sqlglot dialect/파싱 한계 — L2 에러개선 별도 RC)·multi-statement(4, SQLi 방어 의도 유지)·MSSQL db_id/db_name(3, 메타 enumeration 의도 차단). 임계 돌파 시 별도 audit.
- **라이브 실측 필요분(§정직)**: 코드/테스트/런타임 실증은 "UNION·read-only SHOW 통과 + write/DDL·비-readonly SHOW·multi-statement 차단". "실제 대화에서 동적쿼리·테이블변경 리뷰 마찰 소멸" 은 배포 후 라이브 실측분(미수행) → 다음 audit corroboration 재측정.

## FR-show-create-routine-blocked — fixed:deployed:unverified-live (L2 거부 피드백 + capability gap; 전용 도구 봉인)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트 완료(전체 회귀 1868 PASS·§18.8 패널 MAJOR1·MINOR2 수정) + **배포 완료**(2026-07-13, PR #749 merge main `6841eba2` → deploy-web 무중단 web-a/web-b + ask-worker/insight-worker 재빌드·재생성, 4서비스 GIT_COMMIT=6841eba2; ask-worker 런타임 실증 describe_routine∈TOOL_DEFINITIONS·핸들러·`_safe_ident("x\\")=="x"` 확인, web /healthz git_commit=6841eba2). **라이브 대화 실측 미수행** → `unverified-live`. 다음 audit 에서 동일 시나리오(프로시저 정의 요청) 재현/corroboration 재측정 시 `verified`.
- **fix(요지)**: CHG-20260713T140405-describe-routine-tool / **코드 거주 `feature-0002-agent-core`**(+ narration companion `feature-0003`) / REV-20260713T140405-describe-routine-tool (§18.8 적대 3렌즈 패널 security+backend+qa, MAJOR1[백슬래시 인젝션]+MINOR2[파라미터 교차오염·narration fallback] 전건 수정). 사용자 승인 방식=Option 1(전용 도구+유도), AskUserQuestion 2026-07-13.
- **last_seen**: 2026-07-13 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **modality**: 1:1 (추정) · **conv(마스킹)**: topic "재사용 쿼리의 PK 관리 문제 추가 리뷰" (사용자 명시 보고)
- **symptom_confidence**: high (사용자 명시 보고 `E-USR` + 코드 경로 재현) · **rootcause_confidence**: high (코드 file:line 삼각측량 확정)
- **suspected_layers**: **L2**(거부/에러 피드백에 교정 힌트 부재 — 진짜 결함) + capability gap; L5(sql_guard SELECT/CTE-only)은 의도된 기능(F4, 불변)
- **증상(signal)**: `E-USR` — assistant 가 저장 프로시저 로직(PK 관리) 검토를 위해 `execute_sql` 로 `SHOW CREATE PROCEDURE gunzgame.Game_AccountAttendence` 실행 → sql_guard 가 non-SELECT(`exp.Show`)로 거부(`only SELECT/CTE allowed`). 거부 메시지가 `list_schemas/describe_table` 만 안내하고 루틴 정의 조회 경로 미제시 → assistant 막힘.
- **confirmed_root_cause**: (1) L5 `sql_guard.py:~500` SELECT/CTE-only 가 SHOW 를 거부(의도된 보안 기능·유지). (2) **L2**: `tools.py` 거부 hint 가 루틴 정의 경로 미안내 + LLM 노출 도구가 핵심 4개(execute_sql/describe_table/search_tables/get_sample_rows)뿐이라 루틴 본문 조회 수단 부재(`agent_core.py:3634 _run_tool_defs=TOOL_DEFINITIONS`). 접근 권한 자체는 이미 열림(`information_schema.ROUTINES` always-allow) — 막힌 것은 SHOW CREATE 구문형태. 재발 메커니즘 = `model limit`(거부 피드백 교정 힌트) + capability gap.
- **봉인**: 전용 구조화 도구 `describe_routine`(read-only 카탈로그, `_struct_schema_access_error` allowlist 게이트, RO GRANT backstop) + SHOW CREATE 거부 시 L2 유도 힌트. sql_guard SELECT/CTE-only 불변식 미변경(보안 회귀 0). 부수 근본강화: `_safe_ident` 역슬래시 봉인(구조화 도구 전반 MySQL 리터럴 breakout 차단, §18.8 security 패널).
- **corroboration**: 미측정(단일 대화·사용자 명시 보고). **disposition=fix-now** 근거: capability gap 이 **코드 file:line 정본까지 confirmed(rootcause high)** 인 명백한 구조결함 — 빈도 corroboration 없이 fix-now 자격(저흔적/명백결함 예외). 단 위험등급 Major(신규 LLM 노출 도구·정의 표면화) → 사용자 승인(Option 1) 후 구현.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260713T140405-describe-routine
- **라이브 실측 필요분(§정직)**: 코드/테스트는 "describe_routine 이 정의 반환 + SHOW CREATE 유도 + sql_guard 불변" 증명. "실제 대화에서 프로시저 검토 마찰 소멸" 은 배포 후 동일 시나리오(프로시저 정의 요청) 재현/라이브 대화 실측분(미수행). 배포 후 `fixed:deployed:unverified-live`.

## FR-attachment-update-pasted-not-versioned — fixed:deployed:unverified-live (L1 프롬프트 drift+model limit; 첨부 갱신 전달 선호 + 명명 정합 코드-권위 봉인)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트(타깃 36 PASS·§18.8 3렌즈 패널 SEC-1[MINOR] 봉인·나머지 REFUTED) + verify-completion + **배포 완료**(2026-07-14, PR #771 merge main `ee4f8de6` → deploy-web 무중단 롤링 web-a/web-b + ask-worker/insight-worker 재빌드·재생성, **4서비스 GIT_COMMIT=ee4f8de6** running/healthy; ask-worker 런타임 실증 A1 SYSTEM_PROMPT attachment-edit 강화·A2 `_ATTACHMENT_DELIVERY_DIRECTIVE` 주입, web-a 런타임 실증 A3 명명 `report_v2.csv`+v3→`report_v3.csv`(이중접미 방지)·safe_ext; web /healthz=ee4f8de6·mysql_ok·pg_ok). **라이브 대화 실측 미수행** → `unverified-live`. 다음 audit 에서 corroboration(갱신요청 대화의 assistant 버전 생성 비율↑·```sql 붙여넣기 distinct_conv↓) 재측정 → 개선 시 `verified`, 재증가 시 `regressed`.
- **fix(요지)**: CHG-20260713T185846-attach-update-versioned / **코드 거주 primary `feature-0002-agent-core`**(프롬프트) + secondary cross-ref `feature-0003-agent-web-ui`(명명 CHG-20260713T185846-attach-filename-consistency) / REV-20260713T185846-attach-update-versioned. Scope A PLAN-APPROVED(AskUserQuestion 2026-07-13). Major(코어 LLM 경로) → PR/deploy confirm.
- **last_seen**: 2026-07-13 · **seen_count**: 1 · **seen_distinct_conv**: 27 (corroboration structural)
- **modality**: 1:1/그룹 혼합(추정) · **product(마스킹)**: 다수 · **conv(마스킹)**: 갱신요청 34대화(masked hash 다수), 대표 실패 …098d425c(붙여넣기)·…282d7382(기능 출하 前 블록 미materialize 경계 아티팩트)
- **symptom_confidence**: high (사용자 명시 지시 `E-USR` + DB 재현) · **rootcause_confidence**: high (코드+PG core_messages/attachments 집계+전사 삼각측량)
- **suspected_layers**: **L1**(프롬프트 합성 — 첨부 전달 지침이 좁게 게이팅·"brand-new SQL" 예외와 경쟁·코드 상수 안이라 운영자 global row drift 에 취약) + **L4/naming**(materialize 명명이 LLM-의존)
- **증상(signal)**: `E-USR` 명시 지시 + `E-AST` — assistant 가 개선안 제안 후 명시적 갱신요청에도 답변에 쿼리를 붙여넣고(```sql) 다운로드 가능한 새 첨부 버전을 안 만듦.
- **confirmed_root_cause**: attachment-edit 전달 메커니즘(TASK-0275/0286, 2026-06-15/16 출하)은 존재하나 (1) SYSTEM_PROMPT [agent_core.py 154-169] 가 "corrected file back" 으로 좁게 게이팅 + "brand-new SQL → ```sql 무방"(:152)·일반 출력 지침과 경쟁 (2) 지침이 코드 상수 안에 있어 운영자 `agent_memory.websystemprompts` global row(9219자, 지침 포함)가 상수를 통째 대체할 때 강도가 drift (3) 명명이 LLM `filename` 생략 시에만 정합(`_next_version_filename`). 재발경로 = `data/config drift`(코드 상수↔운영자 프롬프트) + `model limit`(약한 계약).
- **corroboration**: **structural** — 90일 text/csv 첨부(user) 보유 88대화 중 명시적 갱신요청 34, 그중 assistant 버전 생성 성공 **3(~9%)** vs ```sql 붙여넣기+버전無 **27(~79%)**. assistant 버전 생성 전 기간 **4건뿐**. 기능 출하(06-15/16) 후에도 실패 지속(7월 이후 7대화) → **F3(이미 고쳐짐) 기각**. 전역 수정 자격 충족.
- **봉인**: (A1) SYSTEM_PROMPT 첨부 전달 섹션 강화(명시 갱신요청→attachment-edit 필수·brand-new SQL 예외 배제·filename 생략·미첨부 시 재첨부 요청). (A2) `_ATTACHMENT_DELIVERY_DIRECTIVE` 코드-권위 주입(compose_system_prompt parts, base 뒤 항상 — global row drift 봉인, injection-guard 선례). (A3, feature-0003) `_next_version_filename` idempotent(이중접미 방지) + materialize 명명 코드-권위(`<stem>_v<n>.<src_ext>`, 확장자 부재 시 kind 기반 안전값 강제[SEC-1]). **보안 회귀 0**(materialize 가드·확장자 차단 불변).
- **disposition 근거**: structural corroboration + 코드 file:line confirmed(high) + 저위험 봉인(가드 불변) → fix-now. Major(코어 LLM 경로) → Scope A 사용자 승인 후 구현.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260713T185846-attach-update-versioned
- **범위 밖(deferred/watch)**: text-inline count cap 초과 대화에서 메타엔 뜨나 content 미주입 시 "MUST" 가 fabrication 유도 가능(QA-2 MINOR, pre-existing·라이브-eval 관찰) · directive/base 섹션 중복(drift-seal floor, 동기유지) · version=chain MAX+1(의도).
- **라이브 실측 필요분(§정직)**: 코드/테스트/패널은 "갱신요청→attachment-edit 유도·명명 정합·확장자 안전" 증명. "실제 대화 붙여넣기 감소·버전 생성 비율 상승" 은 배포 후 라이브 실측분(미수행) → 다음 audit corroboration(갱신요청 34대화 대비 assistant 버전 생성 비율·```sql 붙여넣기 distinct_conv) 재측정 → 개선 시 `verified`, 미개선/재증가 시 `regressed`.

## FR-mssql-crossdb-structured-discovery — fixed:deployed:unverified-live (L4↔L8 catalog 스코프 + L1/L2; 구조화 발견 도구 DB(catalog) 인지 봉인)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트(전체 회귀 1980 PASS·§18.8 3렌즈 패널 MAJOR3 전건 수정)·라이브 QA 수정 실증 + **배포 완료**(2026-07-14, PR #790 merge main `b364e964` → `deploy-web` 무중단 롤아웃 web-a/web-b + ask-worker/insight-worker 재빌드·gateway reconcile, soak 통과; **4서비스 GIT_COMMIT=b364e964 healthy**; 배포 이미지 baked 코드 end-state 실증 — describe_columns([Shop],T_ItemInfo)=15컬럼·routine cross-DB([Shop].sys.sql_modules)=1345자). **라이브 대화 실측 미수행** → `unverified-live`. 다음 audit corroboration(MSSQL describe_table 빈-헤더율·search_tables 빈결과율 감소) 재측정 시 `verified`.
- **fix(요지)**: CHG-20260714T161500-mssql-crossdb-structured-discovery / **코드 거주 `feature-0002-agent-core`** / REV-20260714T161500-mssql-crossdb-discovery. 사용자 승인=**완전 DB인지**(AskUserQuestion 2026-07-14).
- **last_seen**: 2026-07-14 · **seen_count**: 1 · **seen_distinct_conv**: 11 (MSSQL 60일 describe_table 빈-헤더 기준)
- **modality**: 1:1 (추정) · **product_id(마스킹)**: P-117 외(114/111/91) · **conv(마스킹)**: `20260714065456-d705e0c7`(topic "쿼리 리뷰 — itemBuyOnce→itemBuyLimit", product 117) 외
- **symptom_confidence**: high (사용자 명시 불만 "다시, 제대로 검토해주세요" + DB/라이브 재현) · **rootcause_confidence**: high (코드+PG 대화집계+라이브 QA 서버+전사 4중 삼각측량)
- **suspected_layers**: **L4↔L8**(구조화 발견 도구가 pin 된 primary DB catalog 하나만 조회 — SQL Server INFORMATION_SCHEMA/sys 는 DB별) + **L1**(schema_name 파라미터가 DB 를 스키마로 오인 유도·프롬프트는 DB 목록 주나 도구가 실행 못 함) + **L2**(빈결과에 다른 DB 안내 없어 give-up)
- **증상(signal)**: `E-USR` 명시 불만 + `E-AST` 장황 무행동 — assistant 가 "실제 DB 참조 리뷰" 요청에 `describe_table(schema_name="Shop", ...)`·`search_tables("Item"/"Buy"/…)` 반복 호출 후 전부 빈결과 → "테이블이 생성되지 않은 것으로 보입니다" 오판·포기 → 첨부 파일만으로 리뷰(사용자 "다시, 제대로 검토해주세요").
- **confirmed_root_cause**: SQL Server `INFORMATION_SCHEMA`/`sys` 카탈로그가 **DB(catalog)별**(MySQL 인스턴스-전역 information_schema 와 비대칭)인데, 구조화 발견 8도구가 pin 된 primary DB(`allow_dbs[0]`, SortOrder 첫 DB — product 117=`_INDY_STATISTIC`)만 조회. 제품 데이터는 수십 개 허용 DB(product 117=`Shop`/`9DRAGONS_ITEM`/`CASHITEMDB`… 30여 개, 전부 allowlist·freeform 3-part 도달 가능)에 분산 → primary 밖 객체 발견 불가. assistant 는 DB명을 `schema_name` 에 투입(관측: describe_table 빈-헤더 schema 인자 대부분 DB명). **라이브 QA(mssql-web-qa) 재현**: primary `_INDY_STATISTIC` 에서 `Shop.dbo.T_ItemInfo`(15컬럼)·`L_Item_Buy_Log`(사용자 작업 참조 테이블) 미발견 → `[Shop].INFORMATION_SCHEMA` 3-part 로 발견. 재발경로 = **capability gap**(도구가 가드가 이미 허용한 DB 에 못 닿음).
- **봉인**: 구조화 발견 도구를 **DB(catalog) 인지**로 — `[db].` 3-part 카탈로그 조회(dialects `_cat(db)`) + `search_tables` 대상 DB 미지정 시 허용 DB 전체 검색(per-DB graceful·CAP 40)·DB-qualified 반환 + `database` 툴 파라미터·schema_name↔DB 재해석·`db.schema` 분해 + 빈결과 L2 교정 힌트 + `_MSSQL_DIALECT_GUIDANCE` 다중 DB 지침. **보안 경계 불변**(유효 허용 DB만·시스템 DB/스키마·agent_memory 3중 차단·`_safe_ident`+allowlist). routine 정의는 `[db].sys.sql_modules`(OBJECT_DEFINITION current-DB 스코프 회피).
- **corroboration**: **structural** — MSSQL 60일 29대화 중 describe_table 빈-헤더 11(~38%)·search_tables 빈결과 9, 오늘까지 지속, 4+ product(91/111/114/117). 전역 수정 자격 충족.
- **disposition 근거**: Critical(§12.3 데이터소스 접근 모델) → attended 사람 승인. structural corroboration + 4중 삼각측량 confirmed(high) + 경계-불변 봉인(freeform 도달범위와 동일) → fix-now.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260714T161500-mssql-crossdb-discovery
- **범위 밖(deferred)**: allowlist display 값 `_safe_ident` 미적용(악성 admin config 한정 방어심화, MINOR) · cross-DB 검색 CAP 40 초과 DB(명시 안내·`database` 지정 유도) · describe_columns 스키마 미상 시 동명-다스키마는 이제 eff_schema 해석으로 단일화(dbo 우선).
- **라이브 실측 필요분(§정직)**: 코드/테스트/라이브 QA 는 "cross-DB describe/search/routine 이 다른 허용 DB 객체를 도달"·"시스템 스키마 차단 유지" 증명. "실제 리뷰 대화에서 발견 성공·give-up 소멸" 은 배포 후 실측분 → 다음 audit corroboration(MSSQL describe_table 빈-헤더율·search_tables 빈결과율 감소) 재측정 → 개선 시 `verified`.

## FR-sysvar-select-denylist-overblock — fixed:deployed:unverified-live (L5 sql_guard @@ denylist 과차단; read-only 시스템변수 SELECT 허용)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트(가드+cross-db 175 타깃 PASS·전체 회귀 신규 실패 0[4 실패=baseline test debt, stash 대조 실증]·§18.8 3렌즈 패널 전건 REFUTED) + **배포 완료**(2026-07-14, PR #792 merge main `9dce3caa` → `deploy-web` 무중단 롤아웃 web-a/web-b + ask-worker/insight-worker 재빌드·gateway reconcile, soak 통과; **4서비스 GIT_COMMIT=9dce3caa healthy**; 배포본 ask-worker 런타임 가드 실증 — `SELECT @@lower_case_table_names, @@version`=ALLOW / `SET @@GLOBAL.sql_mode`=DENY / tsql `SELECT @@VERSION`=DENY; web /healthz=9dce3caa·mysql_ok·pg_ok). **라이브 대화 실측 미수행** → `unverified-live`. 다음 audit corroboration(`denylist match: @@` distinct_conv) 재측정 0 유지 시 `verified`.
- **fix(요지)**: CHG-20260714T153113-sysvar-select-guard / **코드 거주 `feature-0002-agent-core`** / REV-20260714T153113-sysvar-select-guard (§18.8 security 적대 서브에이전트 5축 REFUTED + backend/qa 인라인 실증 REFUTED). 사용자 승인=**denylist @@ 제거**(AskUserQuestion 2026-07-14). 선행 CHG-20260713T171821-readonly-query-shapes 의 태세 정합 후속.
- **last_seen**: 2026-07-14 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **modality**: 1:1 동기 · **product_id(마스킹)**: P-119 · **conv(마스킹)**: `20260714050748-e6add7f1`(topic "초기화 쿼리 환경 옵션 검토")
- **symptom_confidence**: high (사용자 명시 지시 "환경 옵션 직접 확인 후 판단" + DB 재현) · **rootcause_confidence**: high (코드 file:line + PG core_messages 차단 로그 + 전사 삼각측량)
- **suspected_layers**: **L5**(sql_guard 보조 denylist `@@` 가 read-only 시스템변수 SELECT 를 과차단 — 실질 write/쓰기 보안과 무관한 정보-클래스 태세 불일치)
- **증상(signal)**: `E-SYS`/`E-USR` — assistant 가 `SELECT @@lower_case_table_names, @@version`(단일 read-only SELECT)로 대소문자 옵션을 직접 확인하려다 `denylist match: @@` 차단 → 재시도(SHOW VARIABLES) 없이 "MySQL 설정 확인 불가"로 OS 기본값 추정 대체 → 사용자의 "환경 옵션 직접 확인" 명시 요구 좌절. 거부 힌트도 "단일 SELECT/CTE 만 허용"이라 오도(해당 쿼리는 단일 SELECT).
- **confirmed_root_cause**: `sql_guard.py:123` MySQL `_DENYLIST_PATTERNS` 의 `re.compile(r"@@")` 가 시스템 변수 읽기 SELECT 를 차단. CHG-20260713T171821 로 read-only `SHOW (GLOBAL) VARIABLES/STATUS`(전체 시스템변수 노출)가 사용자 승인하에 허용된 뒤라 그 **부분집합**인 `SELECT @@x` 만 막는 태세 불일치 잔재. 재발경로 = **guard 가정 오류**(read-only 정보-클래스를 unsafe 로 오분류; FR-readonly-query-shapes-overblock 와 동류 L5).
- **봉인**: MySQL denylist 에서 `@@` 제거. **보안 회귀 0**: (1) 정보노출 델타 0(`SHOW GLOBAL VARIABLES` 가 이미 전량 노출) (2) write 경로 0(`SET @@`·`SET @`=`\bSET\s+@` denylist, `SET GLOBAL x`(무-@@)=shape 게이트 `exp.Set` 거부, `:=`=denylist) (3) forbidden-schema/lock/into/write-node/금지함수는 `find_all` 전수 순회로 `@@` 와 독립(UNION/CTE 분기 무영향) (4) **T-SQL denylist `@@` 유지**(MSSQL 메타 열거 차단 태세 불변).
- **corroboration**: 30일 `denylist match: @@` = **distinct_conv 1**(2026-07-14, 어제 readonly-shapes 배포 후 유일 차단) → **idiosyncratic**(빈도 임계 미달). 단 **근본이 코드 file:line confirmed(high) + 명백한 태세 불일치 + 재발경로 확실**(환경옵션 확인은 초기화/DDL 쿼리 리뷰 상시 단계) → 명백한 구조결함 fix-now. 선행 FR-readonly-query-shapes(structural, 9 conv)의 직접 태세 후속.
- **disposition 근거**: Critical(§12.3 sql_guard 허용범위) → attended 사람 승인(AskUserQuestion). 코드 confirmed + read-only 안전성(정보노출 델타 0·write 경로 0) → fix-now.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260714T153113-sysvar-select-guard
- **배포 note(§정직)**: `deploy-web` soak 가 첫 2회 edge /healthz 단발 프로브 window(web-a/web-b 동시 recreate 후 Caddy 재해석 + cutover blip)에서 롤백 판정 → 3회차 배포 시 실시간 edge 프로브로 9dce3caa 가 soak 내내 200(mysql/pg true) 유지 실증 후 성공(transient 확증, 코드 결함 아님 — 런타임 diff 는 sql_guard 7줄뿐이며 /healthz 는 mysql+pg ping 만 검사, sql_guard 미경유).
- **라이브 실측 필요분(§정직)**: 코드/테스트/런타임 가드 실증은 "`SELECT @@x` 허용 + write/tsql 차단 유지" 증명. "실제 대화에서 환경옵션 확인 마찰 소멸" 은 배포 후 라이브 실측분(미수행) → 다음 audit corroboration(`denylist match: @@` distinct_conv) 재측정 → 0 유지 시 `verified`, 재증가 시 `regressed`.

## FR-partial-evidence-false-verification — fixed:deployed:unverified-live (L2/L1 부분 증거 전수 단정 환각; 절단 미리보기 epistemics + byte-bounded 확장 + grounding 계약)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트(신규 `test_partial_evidence_grounding.py` 10 PASS + 전체 회귀 feature-0002+0003 EXIT=0·§18.8 3렌즈 패널[API 세션한도→인라인 자기검증] BLOCKING/MAJOR 0) + **배포 완료**(2026-07-14, PR #793 merge main `244e6bec` → `deploy-web` 무중단 web-a/web-b + ask-worker/insight-worker 재빌드·gateway reconcile, soak 통과; **4서비스 GIT_COMMIT=244e6bec healthy**; ask-worker 런타임 실증 — `expand_char_budget`/`_TOOL_PREVIEW_ROWS_MAX` 7건 로드·`_server_variable_redirect` 0건(Lever D 철회 반영)·SYSTEM_PROMPT `PREVIEW-TRUNCATED`/`SERVER OPTIONS` 2건; web /healthz=244e6bec·mysql_ok·pg_ok). **라이브 대화 실측 미수행** → `unverified-live`. 배포 시점 baseline: 30일 절단 노출 8/49 대화·'환각' 명시 2건(90일). 다음 audit corroboration 재측정 감소 시 `verified`.
- **fix(요지)**: CHG-20260714T063200-partial-evidence-grounding / **코드 거주 `feature-0002-agent-core`** / REV-20260714T063200-partial-evidence-grounding. 출하 lever = A(절단 epistemics)+B(byte-bounded 확장)+C(grounding 계약). PLAN-APPROVED A+B+C+D + PR/배포 인가(AskUserQuestion 2026-07-14). Major(코어 LLM 경로).
- **last_seen**: 2026-07-14 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **modality**: 1:1 동기 · **product_id(마스킹)**: P-119 · **conv(마스킹)**: `20260714050748-e6add7f1`(topic "첨부파일과 실제 DB 비교 검증")
- **symptom_confidence**: high (사용자 명시 불만 "답변 내 환각이 극심합니다" `E-USR` + ground truth 첨부 sha256 대조 재현) · **rootcause_confidence**: high (코드+DB(PG core_messages)+전사+첨부 원본 삼각측량, file:line 확정)
- **suspected_layers**: **L2**(도구 피드백 — 절단 미리보기가 자기교정 정보 미동봉, `_format_result_sets`/execute_sql 안내문) + **L1**(프롬프트 — 부재/전수 단정에 근거 계약 부재) + render 표시 캡 구조
- **증상(signal)**: `E-USR` 명시 불만 + `E-AST` 환각(ground-truth 대조) + `I-FALSE` 거짓 성공 — ① `execute_sql` 183행 결과가 50행 미리보기 절단(gunzlog 전량 미열람)됐는데 "전수 검증"처럼 서술 + 첨부에 **실재하는** `TRUNCATE charactermakinglog`(첨부 141행)를 "누락"으로 오진 ② 정정 턴(사용자 "실제 첨부파일을 확인하며 비교")도 61행/50행 절단으로 동일 반복 ③ `@@lower_case_table_names` 거부 후 문서 기본값(0) 추측 → 실측(1) 반대 결론.
- **confirmed_root_cause**: 재발경로 = `model limit`(비결정 LLM 이 절단·차단이라는 부분 증거를 전수로 오단정). 봉인은 (A) 도구 피드백 정형화 — 절단 안내문에 "미열람 행 단정 금지·재조회 유도·CSV 비가독" epistemic 동봉 (B) 표시 캡 구조 보정 — 소형 결과는 char-budget(12,000자)·행 상한(500) 내 전량 표시해 목록 대조가 미리보기 내 종결(광폭/대형은 기존 캡; 웹 UI step 은 CSV 우선 50행 경로라 무영향) (C) 프롬프트 grounding 계약 — SYSTEM_PROMPT 4규칙(절단 epistemics·부재/전수 근거 계약·첨부↔DB 양측 조회·옵션 실측). ③번 @@ 근본은 병렬 세션 CHG-20260714T153113(FR-sysvar-select-denylist-overblock)이 가드-허용으로 처리 → 애초 계획 Lever D(@@ 거부 힌트)는 dead 경로가 되어 **출하 철회**(정직 — dead code 미출하).
- **corroboration**: 30일 절단 노출(`행 중 50행만 표시`) **8/49 대화(~17%)** structural surface; '환각' 명시 불만은 90일 이 대화가 최초(now 2). 절단 자체는 흔하나(structural) "전수 단정 환각"으로 귀결되는 빈도는 저-흔적(명시 불만 희소) — **근본이 코드 file:line confirmed(high) + 재발경로 확실(대형 목록↔첨부 대조는 쿼리 리뷰 상시 단계) + 저위험 봉인(표시 계약·가드 불변)** → 명백한 구조결함 fix-now.
- **disposition 근거**: Major(코어 LLM 프롬프트·도구 피드백; sql_guard 허용범위·RBAC·PII 불변 → Critical 아님) → attended PLAN-APPROVED. 코드 confirmed + 저위험 봉인 → fix-now.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260714T063200-partial-evidence-grounding
- **동시수정 note(§13.1)**: 본 cycle 중 feature-0002 표준 worktree 를 병렬 세션 2건이 순차 머지(MSSQL cross-DB PR #790/#791, sysvar-guard PR #792) → rebase 2회. sysvar-guard 가 같은 대화 …e6add7f1 의 ③번 @@ 근본을 가드-허용으로 처리해 본 Lever D 를 철회(중복 회피·정직). base-drift 는 union merge + Lever D 재평가로 해소, 상호 회귀 0(내 테스트 + MSSQL 테스트 동시 PASS 실측).
- **라이브 실측 필요분(§정직)**: 코드/테스트/런타임 실증은 "절단 시 자기교정 안내·소형 결과 전량 노출·부재/전수 근거 계약·옵션 실측 유도" 증명. "실제 대화에서 부분증거 전수 단정 환각 소멸" 은 배포 후 라이브 실측분(미수행) → 다음 audit corroboration(절단 노출 대화의 후속 '환각'/'다시 확인' 명시 불만 재발) 재측정 → 감소 시 `verified`, 재증가 시 `regressed`.
- **라이브 실측 결과(직접 재현, 2026-07-14)**: 원 마찰 입력(첨부 2개 #528 `GunZ_Init_Query.sql`·#529 `P_gunzgame_Game_CharacterInsert.sql` — conv …e6add7f1, P-119)을 **배포본**(ask-worker `GIT_COMMIT=244e6bec`)의 실 `agent_core` + 실 gunzgame/gunzlog DB 로 격리 재현(write 전면 차단·turn1·max_steps 12, RO). **✓ 원 증상 소멸**: 재현 답변이 첨부 141행 `TRUNCATE charactermakinglog` 를 "✓ TRUNCATE / OK"(실 DB 12행 대조)로 정확 인식 — 원 대화의 "누락 ❌" 오진 재현 안 됨; gunzlog 절단대상 5개 실 DB 행수 grounding(양측 조회) 실증. **✗ 잔존 false-missing 환각 1건**: 재현 답변이 `gunzlog.LoginEventLog`(첨부 **162행에 활성 `TRUNCATE` 실재**·실 DB BASE TABLE 24행)를 "초기화 쿼리에서 언급되지 않은 누락"으로 오판하고 **이미 존재하는 TRUNCATE 추가**를 필수(Critical)로 권장 — 원 마찰과 **동일 계열**(쿼리에 있는 테이블을 '누락'으로 단정)이 다른 테이블에서 재발. (나머지 `errorlog`·`missionfirstdiscover` 2건은 정확 — 쿼리 부재 & DB 존재 대조 확인.) **판정**: 배포 grounding 수정이 원 증상+양측조회는 봉인했으나 **false-missing 계열(model-limit — 소형 인라인 첨부의 스캔 누락)은 미완봉** → `verified` 미충족, `unverified-live` **유지**. 잔존 결함은 CHG-20260714T210000 ③(첨부 섹션 execute_sql 억제 제거)로 **해소되지 않음**(재현에서 grounding 은 이미 활성 — 억제가 원인 아님) → 별도 triage.
- **잔존 false-missing 후속 봉인(2026-07-15, 사용자 결정 arc)**: (1) **case 프롬프트 레버** CHG-20260714T221500(PR #800 merge `244e6bec`→후속 배포 `ee3424c3`) — grounding 계약에 식별자 case-fold 비교 규칙 추가. **재-재현(배포본 ee3424c3) 결과 = 부분작동**: 모델이 case 를 인지하기 시작(diff 에서 `LoginEventLog`→`logineventlog` 정규화 제안)했으나 여전히 요약표에 '누락' 오기재 + `lower_case_table_names` 미실측 → 프롬프트 레버는 model-limit 을 확률적으로만 완화. (2) 사용자 **"코드로 결정론적 봉인"**(Option C, AskUserQuestion) → **결정론 도구** CHG-20260714T233000-attach-table-coverage(PR #803 merge main `3c8e78df`, deploy-web 4서비스 GIT_COMMIT=3c8e78df, ask-worker `check_table_coverage` in TOOL_DEFINITIONS/_TOOL_HANDLERS 런타임 실증). 첨부↔실DB 테이블 커버리지 대조를 모델 추론→코드(조작-동사 대상 추출·case-fold·주석분리·절단캐비엣·USE귀속)로 이관 → 대소문자만 다른 조작(첨부 CamelCase↔DB 소문자)을 코드가 정확 집계해 false-missing 을 프롬프트 준수 무관하게 봉인. §18.8 적대 2렌즈 패널 REV-20260714T233000(BLOCKING2 B1 절단·B2 주석·MAJOR1 M1 이름등장 오집계 전건 재설계 수정·보안 5벡터 REFUTED), 유닛 12 PASS(seal 포함). **status 는 `unverified-live` 유지** — 도구 로직 결정론은 코드+유닛으로 증명됐으나, (a) 모델이 도구를 호출하는지의 end-to-end 라이브 재-재현은 배포 직후 외부 gunzgame DB(`10.120.8.200`) unreachable(err 2003)로 미완(외부 인프라·코드 무관), (b) `verified` 는 이 원장 정의상 다음 audit corroboration(절단 노출 대화의 '환각'/'다시 확인' 재발 감소)으로 닫는다. 외부 DB 복구 시 동일 입력 재-재현으로 결정론 봉인 end-to-end 실증 가능.

## FR-schema-name-case-drift — fixed:deployed:unverified-live (L8↔L4 allowlist 스키마명 대소문자 drift; 런타임 canonicalize + grounding graph 교정 + write-path 정규화)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트(신규 `test_schema_name_case_drift.py` 24 + `test_product_databases_case_normalize.py` 2 + 전체 회귀 2113 passed/2 skipped) + §18.8 3렌즈 적대 패널(security REFUTED·backend/qa MAJOR3 봉인)→재검증 READY-TO-SHIP + verify-completion PASS + **배포 완료**(2026-07-15, PR #823 merge main `b3c8cd34` → web-a/b `deploy-web` + ask/insight-worker `--workers-only` 재빌드·gateway reconcile, **4서비스 GIT_COMMIT=b3c8cd34 running/healthy**; healthz ok/mysql_ok/pg_ok). **배포본 런타임 실증**: ask-worker(baked b3c8cd34)의 `_canonical_schema_name` 이 실 mysql-mv-qa-game(10.103.204.59)에서 `dev_1_1_1_20`→`DEV_1_1_1_20` 해소, datasource 프로브 `dev_1_1_1_20`=0테이블 / `DEV_1_1_1_20`=63테이블(fix 0→63). **대화 end-to-end(배포 agent 가 실 대화에서 canonicalize 호출·마찰 소멸) 미수행** → `unverified-live`. 다음 audit corroboration(대상 4 product describe_table 빈-헤더율·search_tables 빈결과율 감소) 재측정 시 `verified`.
- **fix(요지)**: CHG-20260715T082345-schema-name-case-drift / **코드 거주 primary `feature-0002-agent-core`**(런타임 A) + secondary cross-ref `feature-0003-agent-web-ui`(write-path 정규화 B, CHG-20260715T082345-picker-case-preserve) / REV-20260715T082345-schema-name-case-drift. 사용자 승인=**A + B(ingestion)**(AskUserQuestion 2026-07-15). Critical(§12.3 데이터소스 바인딩) → PR/deploy confirm(전건 승인).
- **last_seen**: 2026-07-15 · **seen_count**: 1 · **seen_distinct_conv**: 1(대상) / **config drift**: 85 case-mismatch 중 MySQL 실패클래스 ~18행·4 product(94/97/110/121)·다수 MySQL datasource
- **modality**: 1:1 동기 · **product_id(마스킹)**: P-97 · **conv(마스킹)**: `20260715070720-c202bcf8`("테이블 구조 정합성 검토")
- **symptom_confidence**: high (사용자 명시 보고 + DB/라이브 재현) · **rootcause_confidence**: high (allowlist DB + metadata graph + 전사 + 라이브 datasource 프로브 4중 삼각측량, file:line 확정)
- **suspected_layers**: **L8↔L4**(datasource allowlist 스키마명이 서버 실제 case 와 drift → 데이터 로드 0행) + 부차 **L2**(빈결과에 case 교정 힌트 부재 — give-up)
- **증상(signal)**: `E-USR`(사용자 보고) + `E-SYS`(빈 결과셋 brute-force) + `E-AST`(장황 무행동·첨부만 리뷰) — `describe_table(schema_name="dev_1_1_1_20", datasource="mysql-mv-qa-game")`·`search_tables`·`INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='dev_1_1_1_20'` 반복 → 전부 0행/빈결과(SHOW TABLES sql_guard 차단은 부차) → "테이블 없음" 오판·give-up.
- **confirmed_root_cause**: allowlist `WebProductDatabases.SchemaName` 소문자 저장(`dev_1_1_1_20`; admin manual/admin.js `.toLowerCase()`), 서버 `DEV_1_1_1_20`(대문자, 63테이블). case-sensitive MySQL(lctn=0, Linux)에서 저장 case literal 쿼리 0행. `_datasource_allow_schemas`(agent_core.py:3153)는 저장 case 보존(의도)이라 코드는 옳으나 데이터가 소문자 → grounding·쿼리 잘못된 case. 이전 FR-nl2sql casing 프롬프트 lever(모델 소문자화 금지)로 미해결(데이터 자체 소문자). 재발경로 = **data/config drift**(allowlist casing ≠ 서버 casing) → 코드 권위선 봉인.
- **corroboration**: **structural** — allowlist 205 중 85 case mismatch; MySQL 실패확정 클래스(소문자 stored → 서버 대/혼합) ~18행·4 product·다수 MySQL datasource. (MSSQL 67 = catalog case-insensitive → 무해 거짓양성 기각.)
- **봉인**: (A, feature-0002) execute_tool 단일 choke 라이브 SCHEMATA case-map canonicalize(MySQL·모호 제외·인용 제거·프로브실패 재시도·conn 캐시) + 라우터 refresh_case + `_correct_allow_schemas_case_via_graph`(run-start grounding·전 datasource·live-fixed skip). (B, feature-0003) admin_products write-path 서버-실제-case 정규화(`list_server_databases`·SSRF 선행·degrade-safe). **보안 회귀 0**: 접근 게이트(소문자 allowlist set) 불변 — canonicalize 는 authorize 된 스키마 표기만 서버 실제값으로 교정(경계 무변).
- **disposition 근거**: structural corroboration + 4중 삼각측량 confirmed(high) + 경계-불변 봉인 → fix-now. Critical → attended 승인.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260715T082345-schema-name-case-drift
- **범위 밖(deferred, §정직)**: 단일-ds freeform grounding(활성 drift 제품 0·구조화 arg-canonicalize 봉인) · admin.js `.toLowerCase()` 자체(프론트·visual verification·write-path 정규화가 상쇄) · datasource-scoped picker 실제 case 표시 · 기존 저장 소문자 18행 백필(admin 별도 — A 런타임 + 재저장 write-path 가 점진 seal) · SCHEMATA 프로브 sql_guard/breaker 미경유(security MINOR, 비-경계).
- **라이브 실측 필요분(§정직)**: 코드/테스트/datasource 프로브는 "canonicalize 로직 정확·게이트 불변·0→63 flip". "실제 대화에서 describe/search 가 DEV_1_1_1_20 63테이블 반환·give-up 소멸" 은 배포 후 원 입력 재현분(미수행) → 다음 audit corroboration 재측정.

## FR-procedure-analysis-result-truncated — fixed:deployed:unverified-live (L2 도구결과 전역 4000자 캡; 대형 backstop 상향)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트(신규 `test_tool_result_cap.py` 6 PASS + feature-0002+0003 전체 회귀 exit=0·FAILED/ERROR 0) + §18.8 3렌즈 적대 패널(backend+security+qa) **SHIP**(BLOCKING/MAJOR 0·4 REFUTED·NIT 3 반영) + verify-completion PASS + **배포 완료**(2026-07-24, PR #935 merge main `64daae28` → `deploy-web` 전체 롤아웃, 워커 `a1982ca3`·web `3264cf9d` 재빌드·gateway reconcile·soak 통과; 4서비스 전부 내 머지 64daae28 포함). **ask-worker 런타임 baked 실증**: `AGENT_TOOL_RESULT_MAX_CHARS=100000` 로드·10530자 프로시저(>4000) `_cap_tool_result` **전문 반환·절단 0**(옛 4000 캡이면 잘렸을 입력)·초대형 150k→100k+`(truncated)` note backstop; web-a/web-b docker healthy + baked healthcheck exit=0. **실제 긴 프로시저 describe_routine 라이브 대화 e2e 는 미수행** → `unverified-live`(런타임 baked 실증이 강하게 시사·`_cap_tool_result` 가 describe_routine 출력의 유일 캡). 다음 audit 에서 동일 시나리오 재현/corroboration(도구결과 절단 노출률) 재측정 시 `verified`.
- **fix(요지)**: CHG-20260724T155534-tool-result-cap-raise / **코드 거주 `feature-0002-agent-core`** / REV-20260724T155534-tool-result-cap-raise (subagent a2af724b865cf671a). 사용자 결정=**전 도구 대형 캡**(AskUserQuestion 2026-07-24 — 3안[정의 도구만 무제한/전 도구 무제한/전 도구 대형 캡] 중 도구별 분기 없는 유한 backstop). Major(§12.3 코어 LLM 루프) → 사용자 scope 결정 후 구현 + PR/deploy confirm(전건 승인).
- **last_seen**: 2026-07-24 · **seen_count**: 1 · **seen_distinct_conv**: 1 (사용자 직접 보고)
- **modality**: (사용자 직접 보고 — 대화 미지정) · **conv(마스킹)**: "타임아웃된 프로시저 분석" 사용자 명시 보고
- **symptom_confidence**: high (사용자 명시 보고 `E-USR`) · **rootcause_confidence**: high (코드 file:line 삼각측량 확정)
- **suspected_layers**: **L2**(도구 결과 → LLM 되먹임 전역 4000자 캡이 `describe_routine` 정의 전문 반환을 재절단 — 진짜 결함)
- **증상(signal)**: `E-USR` — assistant 가 긴 저장 프로시저를 추론·내부 도구로 분석할 때 정의 본문이 4000자에서 잘려 한 번에 탐색 불가 → 나머지를 못 채워 반복 재조회·포기(타임아웃).
- **confirmed_root_cause**: `agent_core.py` 도구 루프 3지점(메인 루프·rederive 루프·PG `core_messages` 저장 copy)의 `tool_result[:4000]` 전역 하드캡. `describe_routine`(FR-show-create-routine-blocked, 정의 본문 **전문 반환**)을 재절단해 도구 목적 무력화. 재발경로 = **capability/design gap**(전역 컨텍스트-보호 캡이 정의-반환 도구 목적과 충돌). **describe_routine 개선의 직접 후속 갭.**
- **봉인**: `shared/config.py` `AGENT_TOOL_RESULT_MAX_CHARS`(env override, 기본 **100000**, `cap<=0`=무제한) + `agent_core._cap_tool_result` 헬퍼(초과 시에만 `... (truncated)` note — FR-partial-evidence epistemic 계약 보존). 3지점 상수화. 저장은 PG `agent_runtime.core_messages.content`=text(무제한, overflow 0). **보안 회귀 0**: sql_guard/RBAC/datasource 바인딩/PII/datamark 경계 불변(순수 context-sizing).
- **corroboration**: 미측정(단일·사용자 명시 보고; 외부 게임 datasource 거주 프로시저라 빈도 실측 불가). **disposition=fix-now** 근거: **명백한 구조결함**(코드 file:line confirmed·rootcause high) + describe_routine 개선 직접 후속 갭 — 빈도 corroboration 없이 fix-now 자격(명백결함 예외). Major → 사용자 scope 결정(AskUserQuestion) 후 구현.
- **수용 tradeoff(MINOR, §18.8 패널 by-design)**: 메시지당 컨텍스트/비용 상한 상향(describe_routine 최대 100k·execute_sql 자체 캡 ~12k). 히스토리 reload 는 메시지 수(50) 윈도우라 대형 결과 누적 시 context_length 도달 가능 — 단 `classify_llm_provider_error` context_length 분류(persist_health=False·글로벌 배너 미오염)로 **graceful degradation** + 유한·env 튜닝 가능. 사용자 결정의 명시 수용 범위. 후속 lever(캡 하향/byte-기준 윈도우)는 필요 시 별도.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260724T155534-tool-result-cap-raise
- **라이브 실측 필요분(§정직)**: 코드/테스트/패널/런타임 baked 실증은 "긴 도구 결과가 캡 미만이면 전문 도달·경계·절단 시 note 보존"을 배포본에서 증명. "실제 대화에서 긴 프로시저 describe_routine 분석 마찰 소멸"은 배포 후 라이브 e2e 분(미수행) → 다음 audit corroboration 재측정 → 유지 시 `verified`, 재발 시 `regressed`.

---

### 메타 (이 원장의 첫 기록)

- 첫 audit: 2026-06-29, `/_dqa:conversation_audit account=mckim conversation="게임 스테이지 성공률 통계"` (dogfood 검증 run). 두 마찰 모두 **report-only** — 스킬의 과적합 가드(단일 대화·Major·idiosyncratic → 자동수정 보류)가 의도대로 작동.
- 문서 정합(STATUS·wiki)은 `/_dqa:doc_sync` 위임. 본 원장은 ledger·LEARNINGS 만 관할.

## FR-brandnew-script-attachment-delivery-gap — fixed:undeployed (L2↔L4 capability gap + **L6 실행경로 소유권**; source-less 첨부 생성 경로 + worker-side 후처리)

- **status**: `fixed:undeployed` — 코드/테스트(신규 27 + 회귀, 전체 2369 PASS) + §18.8 AGENT-TEAM 패널(security MAJOR RBAC + backend MINOR 전부 in-cycle 반영) 완료, 배포 전. 배포 후 원 마찰 대화(…f1c535ec) 동일입력 재현으로 거부 소멸 관측 시 `fixed:deployed:unverified-live` → 다음 audit corroboration 재측정 시 `verified`.
- **source**: `/_dqa:conversation_audit` 라이브 대화 직접 탐색(사용자 명시 scope "스크립트 첨부파일 전달 요청" + "assistant 가 '첨부파일' 항목에 실제 쿼리도 생성하도록 구성"). 명시 지시 promote.
- **last_seen**: 2026-07-24 · **seen_count**: 1 · **seen_distinct_conv**: 1(직접 확정) — corroboration 120일 생성물 파일전달 명시요청 distinct_conv 2(오늘 건 포함)
- **modality**: 1:1 동기 · **conv(마스킹)**: …f1c535ec · **msg**: user 1382/1383(중복 재전송 I-INT), assistant 1384(capability-gap 거부)
- **symptom_confidence**: high (사용자 명시 지시 `E-USR` + 중복 재전송 `I-INT` + assistant 거부 `E-AST` 전사 재현) · **rootcause_confidence**: high (코드 file:line + DB 전사 + 프롬프트 삼각측량)
- **suspected_layers**: **L2↔L4**(capability gap — 첨부 생성 경로가 편집(source 필수)만 존재, brand-new root 첨부 생성 코드 부재) + **L1**(프롬프트가 brand-new SQL 을 inline ```sql 로 유도, 첨부 전달은 편집-only 게이팅)
- **증상(signal)**: `E-USR@…f1c535ec#1382` 명시 지시 + over-spec("답변 본문이 아닌") · `I-INT@…f1c535ec#1383` 중복 재전송(마찰) · `E-AST@…f1c535ec#1384` capability-gap 거부(정직한 거부, 환각 아님) — assistant 가 개선 스크립트를 다운로드 첨부로 못 만들고 우회안(빈 파일 첨부 or 본문 재붙여넣기)만 제시.
- **confirmed_root_cause**: 첨부 생성 경로 `_parse_attachment_edit_blocks`(src_id≤0 skip)·`_materialize_assistant_attachment_edits`(source 첨부 로드·버전체이닝 필수)가 **기존 첨부 편집만** 지원 → source(사용자 첨부 파일)가 없으면(예: `describe_routine` 으로 DB 조회·생성한 스크립트) 첨부 전달 불가. 프롬프트(agent_core.py:158 "brand-new SQL → inline ```sql", `_ATTACHMENT_DELIVERY_DIRECTIVE` 편집-only)가 이를 강화. 재발경로 = **capability gap**(기능 부재).
- **corroboration**: 생성물 파일전달 명시요청 = **idiosyncratic**(distinct_conv 2, 저빈도) 이나 **근본이 코드 file:line 으로 confirmed 된 capability gap** → Phase 7 "명백한 구조결함" fix-now(저빈도=저검출성, 저심각도 아님) + 사용자 명시 지시. (리뷰 요청 "첨부 쿼리 리뷰"류 28대화는 편집 경로로 이미 처리 — 별개.)
- **봉인**: (feature-0003 primary) source-less `attachment-new` 경로 — `_attachment_block_spans` 공통 헬퍼(edit/new 공존 경계) + `_parse_attachment_new_blocks` + `_materialize_assistant_attachment_new`(root 첨부 v1·CreatedByRole=assistant, 편집 경로 보안 가드 전부 공유 + **업로드 RBAC 게이트**) + `_strip_attachment_new_blocks` + ask 배선 + app.js 배지/토스트. (feature-0002 cross-ref) `_ATTACHMENT_NEW_DELIVERY_DIRECTIVE` 코드-권위 주입(AUTH-1a) + base 섹션 + inline 예외. **보안 회귀 0**(확장자 allowlist·크기/개수 캡·account/conv scope·업로드 권한 게이트 추가).
- **fix**: CHG-20260724T181106-brandnew-script-attachment / **primary `feature-0003-agent-web-ui`** + secondary cross-ref `feature-0002-agent-core`(CHG-20260724T181106-attach-new-directive) / REVIEW REV-20260724T181106-brandnew-script-attachment. Major(코어 LLM 경로 + 새 첨부 쓰기 경로) → PLAN-APPROVED(AskUserQuestion 2026-07-24) → PR/deploy 별도 confirm.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260724T181106-brandnew-script-attachment
- **라이브 실측 필요분(§정직)**: 코드/테스트/패널은 "attachment-new 경로 동작·보안 가드·프롬프트 주입"을 증명. "실제 대화에서 사용자가 첨부로 받는지" 는 배포 후 라이브 실측분(미수행) → 배포 후 원 마찰 입력(…f1c535ec, "전체 스크립트 개선안을 첨부파일로") 동일 재현 + 다음 audit corroboration(생성물 파일전달 거부 distinct_conv↓) 재측정 → 개선 시 `verified`, 재증가 시 `regressed`.
- **필요한 사람 액션(1줄)**: PR 생성·deploy confirm(Major — override 불가) → 배포 후 POST-DEPLOY PB-0008 라이브 재현 + doc_sync(STATUS/wiki/릴리즈노트 정합).

### 후속 (2026-07-27) — 1차 배포 후 라이브 미동작 → 후처리 소유권 재배치 (2차 수정, 배포 전)

- **재발 관측**: 1차 수정(cdee8f74, 07-24 배포) 후에도 사용자 보고 "첨부파일 생성 기능을 인지하지 못함"(admin 대화 `기능 추가 파일 요청` = 원 대화 …f1c535ec 재사용).
- **실측 판정(중요 — 1차 수정은 절반만 작동)**: assistant 는 `attachment-new` 블록을 **정상 emit**(프롬프트 lever 작동, msg 1389 파서 well-formed open L18/close L328). 그러나 ① 첨부 0건 ② raw 블록이 답변에 노출. MySQL 전체 assistant **root(v1) 첨부 0건**(편집 chain 12건은 정상 — 모두 짧은 run).
- **2차 RC(삼각측량 high)**: 첨부 후처리(materialize+strip)가 **web `/api/ask` 동기 핸들러에만** 존재. 프로덕션은 worker 모드라 답변 생성 주체는 ask-worker 이고 web 은 long-poll 일 뿐 — 장기 run(msg 1388→1389 **11분**) 중 클라이언트/프록시 연결이 끊기면 web 이 후처리 지점에 미도달. worker 는 raw 메시지만 저장. 재발경로 = **아키텍처 소유권 오배치**(편집·신규 경로 공통 잠재 결함이 장기 run 에서 발현).
- **2차 봉인**: 후처리 소유자를 **ask-worker** 로 이전 — `_postprocess_attachment_blocks`(materialize+strip+step) + `run_agent(defer_terminal_status=)` 로 **KV terminal 을 후처리 뒤로 지연**(독자는 KV terminal 을 보고 답변을 읽으므로 이 순서가 노출을 막는 핵심) + `_finalize_deferred_terminal`(finally 보장) + 기동 시 import 워밍업. web 은 **증거 기반 게이트**(블록 잔존 시에만 self-heal)로 전환.
- **fix**: CHG-20260727T105326-worker-attachment-postprocess / **primary `feature-0002-agent-core`** + cross-ref `feature-0003-agent-web-ui`(CHG-20260727T105326-web-postprocess-gate) / REVIEW REV-20260727T105326-worker-attachment-postprocess. Major. PLAN-APPROVED(2026-07-27).
- **§18.8 2라운드**: BLOCKER 2건(web strip 미게이팅 → 블록 삭제 저장으로 **원 결함보다 악화** / KV terminal 이 run_agent 내부라 순서계약 무효) + MAJOR 2 + MINOR 3 + LOW 2 → 전부 in-cycle 반영, 2nd pass 재검증 CLOSED.
- **검증**: pytest **2384 PASS**(신규 12). **라이브 실측은 배포 후**(원 입력 재현 + assistant root 첨부 ≥1 + 워커 로그) — 그 전까지 `fixed:undeployed` 유지(거짓 done 금지).
- **배포 주의(운영)**: web 이 worker 후처리를 전제 → **워커 포함 전체 스코프 배포**(`make deploy-web`). `--web-only` 금지(혼합 창은 증거 기반 게이트가 self-heal 하지만 순서는 지킨다).
- **교훈(LRN 후보)**: "web 동기 핸들러에 붙인 후처리는 worker 실행 모델에서 **연결 수명에 종속**된다 — 답변 완료 시점을 아는 실행 주체가 후처리를 소유해야 하고, 공개 시점(terminal 신호)은 후처리 뒤여야 한다." 1차 수정이 기능은 맞았으나 **실행 경로 소유권**을 놓쳐 라이브에서 0% 동작한 사례.

## FR-false-truncation-belief — fixed:deployed:verified (L2↔L1 허위 절단 인식; 완전성 신호 대칭 + 루틴 정의 offset 페이징)

- **status**: `fixed:deployed:verified` — **라이브 실측 완료(2026-07-28)**. 아래 '라이브 실측' 절 참조. 코드/테스트 + §18.8 적대 3렌즈 패널 완료 + **배포 완료**(2026-07-27, PR #963 merge main `ef24448c` → `make deploy-web` 전체 스코프 무중단 롤아웃: web-a/web-b 롤링 + insight-worker/ask-worker 재빌드 + gateway reconcile, post-cutover soak 90s 통과; **4서비스 GIT_COMMIT=ef24448c**; web `/healthz`=ef24448c·mysql_ok·pg_ok·insight_heartbeat 2s). **배포본 ask-worker 런타임 실측**: 열린 절단신호 목록 부착 True · "침묵 ≠ 완전" 계약 True · 구 `NO MARKER = COMPLETE` 제거 True · 산술 종료조건(`B == T` + 본문 문구 불신) True · auto 창 산정 **99,000**(= 캡 100k − 여유) · 250,000자 정의 머리말 `[정의 구간 0~99000 / 총 250000자 … 마지막 구간: 아니오]` · 전역 캡 통과 후 `offset=` 안내 생존 True · 60,000자 정의 **미분할** True(조각화 회귀 0) · 셀 절단 stats 분리(row=False/cell=True) True · offset 형식오류 명시 True. **라이브 대화 실측 미수행** → `unverified-live`. 다음 audit corroboration(assistant 의 "도구 한계/프리뷰 한계" 시그니처 distinct_conv, 절단 마커 없는 결과 뒤 불완전 주장) 재측정에서 감소 시 `verified`, 재증가 시 `regressed`.
- **source**: `/_dqa:conversation_audit "문서 내부 조회 프로시저 탐색"` 라이브 대화 직접 탐색 + 사용자 명시 지시("'도구 한계' 이슈 해소, `describe_routine` 프로시저 본문을 글자수 제한 없이 조회").
- **last_seen**: 2026-07-27 · **seen_count**: 1 · **seen_distinct_conv**: 1(대상) / 노출면 6대화(CSV 안내문 부착 대화 전량이 실제 절단 없음)
- **modality**: 1:1 동기 · **conv(마스킹)**: `20260727081131-1dc26d26`(topic "문서 내부 조회 프로시저 탐색") · **msg**: assistant 5611·5619
- **symptom_confidence**: high (사용자 명시 지시 `E-USR` + 전사/집계 재현) · **rootcause_confidence**: high (코드 file:line + PG core_messages 전사 + 90일 집계 삼각측량)
- **suspected_layers**: **L2**(도구 결과 피드백 — CSV 안내문이 절단 트리거 어휘를 상시 부착 + 완전성 확인 신호 부재) ↔ **L1**(SYSTEM_PROMPT PREVIEW-TRUNCATED 트리거가 "미리보기" 단어 단독으로 발동)
- **증상(signal)**: `E-USR`(사용자 명시 지시) + `E-AST`(장황 무행동·자기-축소) — 도구는 **절단을 전혀 하지 않았는데**(describe_routine 11건 전부 전문 반환·execute_sql 181행 전량 렌더) assistant 가 "총 181개 프로시저가 발견되었으나 **도구 프리뷰 한계로 전체 목록 확인이 불가능**합니다"(5619)·"⚠️ 불완전한 결과"(5611)라며 분석을 3건으로 축소.
- **거짓양성 정직 기각(F1, 사용자 지목분)**: 사용자가 지목한 "`describe_routine` 본문 글자수 절단" 은 **라이브에서 미발현** — PG 전 기간 describe_routine 결과 33건 중 `AGENT_TOOL_RESULT_MAX_CHARS`(100k) 초과 0건·`(truncated)` note 0건, 대상 대화 최대 6,898자. 절단이 아니라 **절단 오인**이 마찰의 실체였다. 다만 캡이 유한하다는 구조적 gap 은 실재 → 사용자 결정에 따라 캡 완화가 아닌 **offset 페이징**으로 봉인.
- **confirmed_root_cause**: (1) `tools.py` execute_sql/scratch_sql 이 CSV 저장 시 **절단 여부와 무관하게 항상** "핵심 **미리보기**(수 행)만" 안내문을 부착(주석에 "절단 여부와 무관하게 항상 안내" 명시). (2) `agent_core.py` SYSTEM_PROMPT PREVIEW-TRUNCATED 규칙의 트리거가 `"... 행 중 N행만 표시" / "미리보기"` 라 **단어 단독**으로 발동 → 완전한 결과를 절단으로 오인. (3) 절단 경고는 강한 반면 완전 표시엔 `(N 행)` 뿐이라 **완전성 확인 신호가 없어** 오귀속이 교정되지 않음(비대칭). 재발경로 = `model limit` + 도구 피드백 어휘 설계 결함. **FR-partial-evidence-false-verification(2026-07-14) 수정의 2차효과**(절단 epistemic 계약의 역방향 과발동).
- **corroboration**: 90일 — CSV 안내문 노출 6대화가 **전부 실제 절단 없음**(오발동 노출면), 그중 1대화에서 완전성 오귀속 명시 발현("도구 한계"/"프리뷰 한계" 시그니처 distinct_conv 1). 빈도는 **idiosyncratic**(임계 미달)이나, **근본이 코드 file:line 으로 confirmed(high) + 재발경로 확실**(CSV 저장되는 모든 execute_sql 에 트리거 어휘 상시 부착) + **사용자 명시 지시** → Phase 7 "명백한 구조결함" fix-now.
- **봉인(4 lever, §18.8 패널 반영 후 확정)**: (A1) CSV 안내문에서 트리거 어휘 제거(execute_sql·scratch_sql parity). (A2) 절단이 **없을 때** 완전성 명시 — 강한 절단 경고와 대칭. 단 완전성 단정은 **행·셀·export 3축 모두 미절단일 때만**(패널 BLOCKER: `_format_result_sets` 의 셀 100자 절단이 행 플래그에 미집계돼, 3,179자 프로시저 본문을 103자만 보여준 결과에 "절단되지 않았습니다" 가 붙던 **허위 완전성** — 원 마찰의 정반대 방향) + 셀 절단 시 명시 마커 + 0행 대칭 신호. (A3) SYSTEM_PROMPT — 절단 신호를 **열린 집합**으로 두고 완전성 추론을 **침묵 기반 → 긍정 신호 기반**으로 반전(`NO MARKER = COMPLETE` 폐기; 패널이 절단 통지 19곳 census 로 **미매칭 13곳**을 실증 — 닫힌 화이트리스트는 무통지 절단을 "완전" 으로 단정시킨다) + `CHUNKED ROUTINE DEFINITIONS` 종료조건을 **머리말 산술**로(루틴 본문에 "마지막 구간입니다" 를 심어 조기 종료를 유발하는 위조 실증 → 프레임을 본문보다 앞에 두고 `B == T` 로만 종료). (B) `describe_routine(offset)` 문자 페이징 — 창은 **0=auto(= 캡-여유)** 로 잡아 **캡이 어차피 자를 지점부터만** 쪼개고(구 고정 50k 창은 캡 이하 50k~98k 정의까지 불필요하게 조각내 부분 열람 위험을 새로 만들었다), `room<=0`·캡 무제한·음수는 **윈도잉 비활성**(구 `max(1_000, cap-2_000)` 바닥값은 작은 캡에서 조각 꼬리를 잘라 전량 도달 경로를 사망시켰다). offset 형식오류=명시 오류, 범위초과=0 클램프 + 사실 통지(날조된 열람 이력 금지). **보안 회귀 0**(sql_guard·allowlist·`_safe_ident`·RBAC·PII·datamark 경계 불변 — 적대 security 렌즈가 게이트 순서·SQLi·oracle·secret 5축 실측 반증: 차단 스키마는 DB 쿼리 실행 0회).
- **disposition 근거**: Major(§12.3 — 코어 LLM 프롬프트 + 도구 결과 피드백 경로; sql_guard 허용범위·RBAC·PII 불변이라 Critical 아님) → attended. 사용자 AskUserQuestion(2026-07-27)으로 **scope 결정**: 캡 무제한화 제외, 허위 절단 봉인 + offset 페이징. 검증 방식도 사용자 선택(서브에이전트 패널).
- **fix**: CHG-20260727T175800-false-truncation-belief / **코드 거주 `feature-0002-agent-core`**(+ `shared/config.py` 상수) / REV-20260727T175800-false-truncation-belief(§18.8 적대 3렌즈 — BLOCKER 2 / MAJOR 8 / MINOR 7 / NIT 3 → 12건 in-cycle 반영, 4건 정직 이연, 1건 by-design 수용). 신규 `tests/test_false_truncation_belief.py` **23 PASS**(실전형 본문 전량 복원·셀 절단 억제·본문 위조 방어·창 산정 전수 포함) + 컨테이너 `make test` **2,428건 중 2,422 PASS / 4 FAIL(전부 pre-existing 환경 의존 — `git archive HEAD` 무변경 체크아웃에서 동일 실패 재현으로 확증) / 2 skip** + ruff PASS.
- **수용된 트레이드오프(by-design)**: 초대형 정의 페이징에 회차 예산 없음(4MB 루틴 ≈ 42회 호출, 조각이 `role=tool` 히스토리로 이후 턴 재전송). **전량 도달이 사용자 명시 요구**라 강제 상한은 요구 위반 → auto 창·총 문자수 사전 고지·`AGENT_MAX_STEPS` 유한성·음수 kill-switch 로 완화(선행 FR-procedure-analysis-result-truncated 의 동일 축 수용과 정합).
- **라이브 실측(2026-07-28, 배포본 `8db72012` ⊃ `ef24448c`)** — 재현 대화 `20260728012534-a56ec98e`(product 117 WEB_QA / `mssql-web-qa`, model `claude-haiku-4` — 원 대화와 동일 조건), 3 turn:
  - **① 오귀속 소멸(주 판정축)**: 원 마찰 시그니처(`도구 프리뷰 한계`·`프리뷰 한계`·`미리보기 제한`·`도구 한계`·`전체 목록 확인이 불가`·`불완전한 결과`) **3 turn 전부 0건**. 특히 turn2 는 원 시나리오와 동형인 **대량 완전 결과**(테이블 291개 카운트 + 200행 렌더 목록)를 다뤘는데 도구 한계를 지어내지 않고 "291개 전부 나열됨"으로 정상 종결.
  - **② 기전 확인(도구 결과 실물)**: 배포 후 tool 결과에서 신규 완전성 신호 4건 · 0행 대칭 신호 2건 · 셀 절단 마커 3건 · 신규 CSV 안내문(`핵심 몇 행만 인용`) 9건, **구 트리거 어휘(`핵심 미리보기(수 행)만`) 0건**.
  - **③ §18.8 BLOCKER 수정 실증**: msg 5691 — 20행 **완전** 결과인데 셀 13개가 100자에서 잘리자 완전성 단정이 **억제**되고 `(긴 셀 값 13개가 100자에서 잘렸습니다 — … 당신은 보지 못했습니다)` 마커만 부착. 구 코드였다면 "20행 전부입니다 — 절단되지 않았습니다"가 붙었을 입력이다.
  - **④ 진짜 절단은 그대로 경고**: 루틴 482건 목록(msg 5701·5707)은 미리보기 절단 → 기존 epistemic 경고 유지 + 완전성 미부착. 신호 3축(완전/행절단/셀절단)이 라이브에서 정확히 분기함.
  - **⑤ 원 불만 문구 해소**: 사용자 원문 "프로시저 내용이 일부만 나타나고 나머지 내용이 잘렸습니다"(원 대화 msg 5632) 대상인 `MSP_SELECT_COMMENT_LIST` 를 재조회 → **2,386자 전문 수신, 말미 `END` 까지 완결 확인**, 절단 주장 0건.
  - **⑥ corroboration 추이**: 오귀속 시그니처 distinct_conv **배포 전 1 → 배포 후 0**. **분모 정직 표기**: 배포 후 유기 트래픽이 assistant 메시지 23건/대화 4건으로 작아 통계적 확정력은 제한적 — 판정의 결정적 근거는 ⑥이 아니라 **①(동일 시나리오 직접 재현)과 ②③④(기전 실물 확인)** 이다.
  - **⑦ offset 페이징은 실데이터로 미도달(정직)**: 전 기간 `describe_routine` 정의 결과 35건의 **최대 7,732자 · 평균 2,407자**로 auto 창 99,000자에 한참 못 미쳐 `[정의 구간` 머리말 발생 **0건**. 즉 페이징은 라이브에서 관측될 수 없는 조건이며, 동작 자체는 **배포본 직접 호출**로 검증(250,000자 정의 → `[정의 구간 0~99000 / 총 250000자 … 마지막 구간: 아니오]`, 전역 캡 통과 후 `offset=` 안내 생존, 60,000자 정의 미분할). 사용자 요구("캡 초과 범위도 여러 번 호출로 도달")는 **구조적으로 충족**되었고 발현만 데이터 의존.
- **실측 중 관측된 별개 축(신규 friction 으로 분리 기록)**: turn1 에서 모델이 2부분 명명 `INFORMATION_SCHEMA.ROUTINES` (SQL Server 는 현재 DB 한정)로 0행을 받고 **"프로시저 0개 · 전혀 정의되지 않았습니다"라며 부재를 단정**했다(실제 472 PROC + 10 FUNC = 482). 신규 0행 대칭 신호가 부착돼 있었음에도 막지 못했고, turn2 에서 압박하자 "초기 조회에서 오류를 범했습니다"로 자기정정. **본 변경이 유발한 것이 아님을 baseline 대조로 확인** — 배포 전 구간(06-01~07-27) 0행 tool 결과 89건 중 직후 부재 단정 5건(31개 대화)로 **이미 존재하던 실패 모드**이며, 신규 신호는 그 base rate 를 없애기에 불충분했을 뿐이다. → `FR-false-absence-zero-row-catalog-scope` 로 분리.
- **후속 triage(이 cycle 이 도입하지 않은 pre-existing gap — A3 반전으로 무해화되었으나 emitter 미수정)**: ① `graph_navigate` 노드/관계 60개 절단 무통지(`neighborhood()['truncated']` 미노출) ② MSSQL `ROUTINE_DEFINITION` 4000자 카탈로그 폴백 무표식 ③ comment `[:40]`/`[:30]`·EXPLAIN `StmtText[:80]`·sandbox 샘플 `[:77]` 무통지 ④ 답변 collapse 마커 문구를 `전체 N행 중 M행 표시` 로 정합(프론트는 URL 기준 파싱이라 안전 — 실측) ⑤ 절단 통지 emitter 를 단일 헬퍼(SSOT)로 통합 + 프롬프트↔emitter census 정합 테스트.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260727T175800-false-truncation-belief
- **라이브 실측 필요분(§정직)**: 코드/테스트는 "완전한 결과에 완전성 명시·트리거 어휘 부재·절단 시 기존 경고 유지·offset 으로 전량 복원" 을 증명. **"실제 대화에서 assistant 가 없는 도구 한계를 더는 지어내지 않는지" 는 배포 후 라이브 실측분**(미수행) → 배포 후 동일 입력 재현 + 다음 audit corroboration(assistant 의 "도구 한계/프리뷰 한계" 시그니처 distinct_conv, 절단 마커 없는 tool 결과 뒤 불완전 주장) 재측정 → 감소 시 `verified`, 재증가 시 `regressed`.
- **필요한 사람 액션(1줄)**: PR 생성·deploy confirm(Major — override 불가) → 배포 후 라이브 재현 + `/_dqa:doc_sync`(STATUS·wiki 정합).

## FR-false-absence-zero-row-catalog-scope — fixed:deployed:verified (L1↔L4 0행→부재 단정; 루틴 열거 도구 부재 + 카탈로그 스코프 미인지)

- **status**: `fixed:deployed:verified` — **라이브 재실측 완료(2026-07-28)**. 사용자 지시로 근본 규명 후 수정, §18.8 적대 3렌즈 **2라운드** 통과, PR #991 merge main `21b67ade` → `make deploy-web` 전체 스코프(4서비스 GIT_COMMIT=21b67ade, soak 통과, `/healthz` ok). 사용자 **범위 결정: RC-B 포함**(보안 경계 재검토).
- **라이브 재실측(재현 대화 `20260728031510-16927f9b`, product 117 / `claude-haiku-4` — 마찰 대화와 동일 조건, 동일 질문)**:
  - **수정 전**: "masangsoftweb 에는 저장 프로시저가 **전혀 정의되지 않았습니다** / 전체 프로시저 개수 **0개**" (ground truth 482건).
  - **수정 후**: "SELECT 키워드를 포함하는 프로시저: **총 421개**" + 원 대화가 찾았던 **`MSP_SELECT_BOARD_CONTENT`** 를 정의 본문까지 제시(원 사용자 목표 달성). **오귀속·부재 단정 시그니처 각 0건.**
  - **신규 도구 실사용 확인**: `search_routines` 가 루프에서 호출됨(msg 5775~5782) — 빈 결과에는 "이 한 번의 빈 결과로 '루틴이 없다' 고 단정하지 마세요" 부착.
  - **실패 고지 실전 발동(§18.8 MAJOR 수정의 라이브 실증)**: 실행 중 MSSQL 연결이 끊기자(`Not connected to any MS SQL server`) 도구가 "⚠ 다음 DB 는 **조회하지 못했습니다** … 존재/부재는 **미확인**입니다 — 단정하지 마세요. (허용 DB 전부가 조회 실패라 이 검색은 아무것도 확인하지 못했습니다)" 를 냈다. 구 코드였다면 "검색 결과가 없습니다" 로 위장돼 정확히 이 FR 의 오판을 재생산했을 상황이다. 그 run 의 최종 답변도 부재를 지어내지 않고 "탐색을 충분히 진행하지 못했다" 고 정직 보고(`20260728031608-b7832c89`).
  - **배포본 런타임 실측**: `search_routines` 노출 True · 프롬프트 `CATALOG VIEWS ARE PER-DATABASE` True · `sys` 경계 SSOT(대체 관용구 포함) True · `sys.objects`/`sys.partitions` ALLOW · `sys.databases`/`master.sys.objects`/**별칭 그림자**(`FROM sys.objects AS sys CROSS APPLY sys.fn_get_sql(...)`) BLOCK · 사용자 UDF `dbo.dm_calc_total()` ALLOW(과차단 없음).
- **source**: `/_dqa:conversation_audit` FR-false-truncation-belief 사후 라이브 실측(재현 대화 `20260728012534-a56ec98e` turn1).
- **last_seen**: 2026-07-28 · **seen_count**: 1(실측) · **seen_distinct_conv**: 1 / 배포 전 base rate 5건(31개 대화)
- **modality**: 1:1 동기 · **symptom_confidence**: high(실측 재현 + ground truth 대조) · **rootcause_confidence**: medium(2부분 명명 가설은 강하나 코드 fix 미검증)
- **suspected_layers**: **L1**(프롬프트 — 0행을 부재 증거로 승격) + **L2**(도구 피드백이 dialect 스코프 함정을 알려주지 않음)
- **증상(signal)**: `I-FALSE`(허위 부재 단정). SQL Server 에서 `INFORMATION_SCHEMA.ROUTINES` 는 **연결의 현재 DB 한정**인데 모델이 2부분 명명으로 조회 → 0행 → **"masangsoftweb 에는 저장 프로시저가 전혀 정의되지 않았습니다 / 전체 프로시저 개수 0개"** 단정. **ground truth 는 472 PROCEDURE + 10 FUNCTION = 482건**(3부분 명명 `masangsoftweb.INFORMATION_SCHEMA.ROUTINES` 로 확인). 사용자가 되물으니 자기정정.
- **오귀인 방지(중요)**: 이 실패는 **FR-false-truncation-belief 수정이 만든 것이 아니다**. 배포 전 구간(2026-06-01~07-27) 0행 tool 결과 **89건 중 직후 부재 단정 5건 / 31개 대화**로 이미 존재하던 base rate 이며, 신규 0행 대칭 신호(`'없다/누락됐다' 고 단정하기 전에 …확인하세요`)는 그것을 **없애지 못했을 뿐**이다.
- **후보 lever(미채택 — 사람 결정 필요)**: (a) 0행 안내문을 "0행 ≠ 데이터 없음" 우선 프레이밍으로 강화(현 문구는 "이 조건에 맞는 행이 없습니다"가 앞서 완전성 신호로 오독될 여지). (b) dialect 인지 힌트 — SQL Server 에서 메타뷰 2부분 명명 0행 시 "`db.INFORMATION_SCHEMA.X` 3부분 명명으로 교차확인" 안내(`describe_routine` 은 이미 허용 DB 목록을 안내하나 `execute_sql` 0행 경로엔 없음). (c) SYSTEM_PROMPT §ABSENCE 에 "메타뷰 0행은 카탈로그 스코프를 먼저 의심" 규칙 추가.
- **suspected_layers 정정(규명 후)**: 표층은 L1 이지만 실체는 **L4(도구 능력 공백)** 이다 — 루틴을 *열거*하는 구조화 도구가 없어 모델이 카탈로그 SQL 을 손으로 써야 했고, MSSQL 정본 경로(`sys.*`)마저 가드가 닫아 **구조적으로 항상 0행인 쿼리**로 몰렸다.
- **ground truth**: product 117 의 접근 DB 를 `(SortOrder, SchemaName)` 정렬한 첫 항목이 `_INDY_STATISTIC`(SortOrder 10) → 연결은 거기 auto-pin. `masangsoftweb` 은 28개 허용 DB 중 하나라, 그 DB 의 메타뷰 `ROUTINE_CATALOG` 는 절대 `masangsoftweb` 이 될 수 없다. 실제 루틴 수 **472 PROCEDURE + 10 FUNCTION**.
- **계보(중요)**: 프로젝트가 **이미 봉인한 실패 모드의 누락된 형제**다 — `FR-mssql-crossdb-structured-discovery`(2026-07-14)가 "MSSQL 카탈로그 뷰는 DB별 → pin 된 DB만 보고 없음으로 오판"을 **구조화 도구에 한해** 고쳤는데, 루틴 열거는 도구 자체가 없어 freeform 으로 샜다.
- **봉인(5 lever)**: (A) `search_routines` 신설 — 허용 DB 전체 sweep + **정의 본문 검색** + CLR/확장 타입 포함 + keyword 선택(열거) + per-DB 실패·상한 포화 **명시 고지**. (B) freeform `sys` 전면차단 → **DB 스코프 카탈로그 뷰 화이트리스트 21종**(서버 스코프·`synonyms`·`guest`/`db_*`·메타데이터 함수는 계속 차단). (C) MSSQL 프롬프트 `CATALOG VIEWS ARE PER-DATABASE`(2-part + 다른 카탈로그 필터 = 절대 0행, 빈 카탈로그 결과는 스코프의 증거이지 존재의 증거 아님) + `sys` 경계 문구를 화이트리스트 SSOT 로 생성. (D) `_catalog_scope_hint` — **행 수 무관·AST 기반**, 3-part 엔 미부착, 진단 시 완전성 단정 억제. (E) 0행 문구 부재-부정 우선 + 프롬프트 규칙을 메타데이터 맥락으로 한정(정당한 업무 0행 과교정 방지).
- **fix**: CHG-20260728T114459-false-absence-catalog-scope / **코드 거주 `feature-0002-agent-core`**(+ feature-0003 step 서술 1곳) / REV-20260728T114459-false-absence-catalog-scope.
- **후속 triage 진행(별칭 그림자 함수 우회, 2026-07-28)**: 패널이 pre-existing 으로 분리했던 항목을 사용자 지시로 수정 → CHG/REV-20260728T133431-alias-shadowed-function-namespace. **증명 가능한 축 봉인**(table-source 위치 면제 금지 = UDT 메서드가 문법적으로 불가능한 자리의 행집합 유출 / 4·5-part linked server 와 그 경유 M1·`agent_memory` / `Paren`·미지 노드 무판정 통과) + **존재 열거 oracle 차단**(모호 경로의 서버 오류 원문 미노출 — `Msg 916`↔`4121` 차이로 allowlist 밖 객체를 전제조건 없이 열거할 수 있었다). **미해결 잔여**: 스칼라 위치 `alias.col.method()` ↔ `db.schema.func()` 모호성은 SQL 텍스트만으로 해소 불가하고, 면제 제거는 re-gate(7차)가 MAJOR 로 못박은 UDT 메서드 지원 계약을 깬다(CLR 메서드명은 열거 원리 불가). **권위적 경계는 per-DB USER/GRANT** — `bin/datasource-mssql-ro-bootstrap.sql` 이 단일 TARGET_DB 에만 USER 를 만들고 `db_datareader` 를 제거하며 허용 스키마 SELECT-only 로 부여하므로 미허용 DB 에는 principal 자체가 없다. **의존성**: 이 결론은 부트스트랩 준수를 전제 — 수동 `db_datareader`/전역 USER 부여 시 잔여가 실착취로 승격된다(datasource 추가 시 반드시 해당 스크립트로 프로비저닝).
- **잔여 확정 — 서버 이름 해석으로 닫힘(라이브 실증 2026-07-28)**: 스칼라 위치 모호성을 "미해결 잔여" 로 남겼으나, QA SQL Server **2017(14.0.3238.1) Web Edition** 에 직접 프로브해 **착취 불가**로 확정했다. ① 별칭=미존재 DB명 → `Msg 207 Invalid column name 'dbo'` ② 별칭=**실존** DB명(`Shop`/`Web_SR`) → `Msg 207` **①과 완전히 동일** ③ 별칭 없음(동일 3-part) → `Msg 4121 Cannot find … function`. 즉 SQL Server 는 `alias.col.method()` 를 **별칭 우선(컬럼)** 으로 해석하므로 테이블을 DB 명으로 별칭 지어 cross-DB 함수를 부를 수 없고, 오류 문구가 **DB 존재 여부에 불변**이라 열거 oracle 도 성립하지 않는다. → 가드의 스칼라 면제는 서버 동작과 **의미적으로 일치**하며, per-DB GRANT 는 유일 방어선이 아니라 defense-in-depth 로 내려간다. **적대 검증 1R BLOCKER-1 은 게이트 레벨 ALLOW 만 근거로 한 판정이었고(서버 미검증), 이 실증이 그 전제를 반증한다.**
- **부수 철회**: 위 oracle 을 막으려 넣은 서버 오류 원문 은폐(`_sql_error_message`)는 근거를 잃어 **철회**했다 — 얻는 것 없이 `Invalid column name 'dbo'` 같은 자기교정 정보만 가리는 순손실이었다. APPLY(table-source)·4/5-part·`Paren`/미지 노드 봉인은 그대로 유효(그 위치들은 컬럼 해석이 문법적으로 불가해 서버가 반드시 함수로 해석).
- **필요한 사람 액션(1줄)**: PR 생성·deploy confirm(Major + 보안 경계 완화 — override 불가) → 배포 후 동일 질문으로 라이브 재실측.

## FR-model-pick-lost-on-early-cid — fixed:deployed:verified (L7↔L6 조기 cid 전환이 모델 선택 귀속을 유실 → 서버 기본값 강등)

- **status**: `fixed:deployed:verified` (2026-07-29 11:30 전이) — FE 귀속 승계(A) + 표시-집행 정합
  감지(C) 출하 → PR #1032 머지(main `bc920534`) → 배포(web `StartedAt` 11:08:44 KST, edge
  `/healthz` `git_commit=36618965`, 서빙 `app.js?v=7529ce4ce347` 에 4 심볼 baked) → **PB-0008 라이브
  실증 PASS**. 판정은 화면이 아니라 이 항목이 못박은 정본으로 냈다 — `llm_usage` id 69372
  `model=claude-sonnet-4` / `resolved_model=claude-sonnet-4-chat`(강등 0) + `kv model:<acct>` 행
  **생성**(값 `claude-sonnet-4`). 사용자 시나리오 [새 대화 → sonnet 선택 → 첨부 업로드 → 전송] 전
  구간을 3중 계측(요청 본문·경보 채널·상태 스냅샷)으로 재현했고, 결함 전제 상태(`_modelPickedForConvId=""`)
  까지 실제로 통과한 뒤 승계가 성립함을 관측했다(= 경로를 우회한 통과가 아님).
  **잔여(이월)**: 관측 표본 corroboration(30일 non-default 선택 대화의 첫 요청 오전송 3/5) 재측정은
  배포 직후 표본 부재 → 다음 audit. 재증가 시 `regressed` 로 되돌린다.
  근거: `unit/feature-0003-agent-web-ui/docs/test-runs.d/20260729T1130-model-pick-postdeploy.md` ·
  REV-20260729T113000-model-pick-postdeploy.
- **사용자 재보고 귀속(2026-07-29)**: 완료 보고 후 사용자가 "이전과 동일하게 폴백"을 재보고했으나,
  그 재현 대화(…2211841a)의 첫 전송은 **10:33:48** 로 배포 **11:08:44** 보다 35분 앞섰고 배포 후
  신규 대화·첨부는 **0건**이었다 → 구자산 세션 경험(수정 실패 아님). 오히려 같은 오전 대조군
  (…a8b43197 10:30 첨부 5건 = sonnet 정상 / …2211841a 10:33 첨부 1건 = haiku 강등)이 분기점을
  "첨부 유무"가 아니라 **선택→첨부 순서**로 재확인해 아래 root cause 의 경로 특정을 강화한다.
  교훈: 재보고는 **배포 시각과 대조한 뒤** 해석한다(`docs/LEARNINGS.md`).
- **source**: 사용자 명시 호출 `/_dqa:conversation_audit` (2026-07-28) — 지정 대화 2건 + turn 중 추가 관측
  진술("sonnet 모델로 요청한 즉시 haiku 모델로 폴백").
- **last_seen**: 2026-07-28 · **seen_count**: 1 · **seen_distinct_conv**: 4 (지정 2 + 인접 재시도 1 + 사용자 재현 1)
- **modality**: 1:1 동기 · **product_id(마스킹)**: P-117 · **account(마스킹)**: A-10 ·
  **conv(마스킹)**: …f70af5fc(`쿼리 리뷰 : 게시글 기능`) · …d887c4c9(`쿼리 리뷰 : 홈페이지 공지 기능 추가`) ·
  …f434dc11(인접 재시도·대조군) · …18be31a2(사용자 재현)
- **symptom_confidence**: high (사용자 명시 보고 + 라이브 데이터 재현) · **rootcause_confidence**: high
  (코드 file:line + PG 3테이블 + 전사 삼각측량, 대조군으로 경로 분리 확정)
- **suspected_layers**: **L7↔L6** — L7(FE 상태 전환에서 선택 귀속 미이관)이 근본, L6(모델 결정)에서 발현.
  **L6 라우팅 폴백은 아니다**(초기 가설 `refuted` — 아래).
- **증상(signal)**: `E-USR` 명시 불만 + `I-SIL` 재시작 이탈 — 같은 요청을 4개 대화에서 반복 재시도
  (18:32 / 18:37 / 18:39 / 18:55), 중간 sonnet run 은 사용자 취소로 종료. 사용자 표현 "조용히 haiku 로
  변경되며 나머지 작업을 진행".
- **거짓양성 기각(`refuted`)**: ① **LLM 라우팅 폴백 가설 기각** — `llm_usage.model`(요청 alias)이 이미
  `claude-haiku-4` 였다. 폴백이면 `model=sonnet` / `resolved_model=haiku` 로 갈라졌을 것이며, 실제
  `resolved_model` 은 `claude-haiku-4-chat`(정상 해소)이다. 선행 `FR-edge-fallback-conversation-context-loss`
  의 재발이 아니다. ② **sonnet run 취소(`ask_jobs.status=error`, "요청이 취소되었습니다")는 별개 결함이
  아님** — `cancel_requested` KV 가 찍힌 사용자 중단이며, haiku 로 가는 것을 보고 끊은 **결과**다.
- **confirmed_root_cause**: 모델 선택 귀속(`_modelPickedForConvId`)은 선택 시점의 `activeConversationId`
  로 잡혀 새 대화(pending)에서는 빈 문자열이다. **첨부 업로드**가 early-cid 를 발급해 활성 대화를 실 cid
  로 전환(`app.js` lazy→real)하면서 이 귀속을 승계하지 않아, 전송 시 `_shouldSendModelField()` 가 false
  → `askBody.model` 누락 → 서버(`conversations.py` ask)가 `API_DEFAULT_MODEL`(haiku)로 채우고
  `model_explicit=False` 라 KV 저장도 skip. 화면 선택기는 고른 모델을 계속 표시 → **완전한 무음 강등**.
  덧붙여 첫 전송 후 hydration 이 저장값 부재로 선택을 비워 **선택기까지 기본값으로 되돌아간다**(사용자가
  "즉시 폴백"을 화면에서 본 기전). 재발 메커니즘 = **ux contract**(상태 전환 시 귀속 이관 누락).
  결정적 지문: 재현 대화에 `kv model:<acct>` 행 **부재**(미동봉) vs `reasoning_level` 정상 저장(항상
  전송되는 비대칭). 대조군 …f434dc11 — 대화 확정 후 재선택한 2차 요청은 정상 sonnet 전송 + KV 저장.
- **corroboration**: 최근 30일, non-default 모델 선택이 KV 로 확증된 대화 5건 중 **3건이 첫 요청을 사용자
  선택과 다른 모델로 전송**(선택 저장이 첫 job 이후 = 유실 후 재선택 패턴) → **structural**. 초기에 쓴
  거친 프록시("대화 생성↔첫 메시지 gap" 별 model KV 부재율 93% vs 86%)는 **판별력 없음으로 폐기** —
  기본값 실행도 KV 행이 남지 않아 미동봉과 구분되지 않는다(측정 함정 기록).
- **disposition 근거**: Major(§12.3 — 모델 라우팅 입력 + haiku→sonnet 실행 증가라는 외부 비용 방향) →
  attended human-decision. 사용자가 AskUserQuestion 으로 봉인 범위 **A+C** 명시 선택(2026-07-28) →
  PLAN-APPROVED 후 구현·검증.
- **fix**: `CHG-20260728T191126-model-pick-early-cid` / **코드 거주 `feature-0003-agent-web-ui`**
  (`src/static/app.js` — `_adoptComposerModelPickToConv` 승계 2지점 + `_modelSelectionSilentlyDropped`
  표면화) / `REV-20260728T191126-model-pick-early-cid` (§18.8 `contract` 매칭 backend+security+qa
  인라인 적대검증 — S1~S3·C1~C5·Q1~Q2 전건 REFUTED/해소, BLOCKING 0). 서버 무변경.
  테스트 `verify_model_persist.mjs` 32 → **49 PASS**(E/W/S9~S11 신설) · 서버측 pytest 57건 rc=0.
- **rc_ids**: RC-1 · **batch-id**: B-20260728T191126-model-pick-early-cid
- **라이브 실측(2026-07-29 이행 완료)**: 코드/테스트는 "고른 모델이 요청에 실린다 + 미동봉이면
  표면화된다"까지만 증명했고, "실제 대화가 고른 모델로 **실행**됨"은 배포 후에만 반증 가능한 잔여였다.
  → 배포본에서 PB-0008 이행 **PASS**(`REV-20260729T113000-model-pick-postdeploy`). 정본 판정:
  `llm_usage` id 69372 `model=claude-sonnet-4`/`resolved_model=claude-sonnet-4-chat` + `kv model:1` 행
  생성. **잔여는 corroboration 추세 재측정 1건**(30일 오전송 3/5 → 다음 audit; 재증가 시 `regressed`).
- **kv 지문 판독(3분기 — 오독 방지)**: 위 root cause 의 "행 부재" 서술을 정밀화한다. 서버는
  `model_explicit` 일 때만 저장하되 **값이 세션 기본값과 같으면 빈 값으로 지운다**(기본값 이탈만 저장,
  적대 리뷰 C2). 따라서 `kv model:<acct>` 는 — **행 부재 = 미동봉**(이번 결함의 지문) / **빈 값 행 =
  기본값과 같은 모델의 명시 동봉** / **값 있는 행 = 비-기본 모델 명시 동봉**. 재현 대화 …2211841a 에
  두 단계가 모두 남아 있다(10:33 첫 전송 시 행 부재 → 10:59:02 빈 값 행 = hydration 이 선택기를 기본값
  으로 되돌린 뒤 이어 보낸 전송). 빈 값 행을 미동봉으로 읽으면 향후 같은 류를 오진한다.
- **범위 밖(인지)**: 기본값(`API_DEFAULT_MODEL`) 자체와 "'+ 새 대화'는 haiku 로 시작" 정책은 불변 —
  사용자 명시 선택만 보존한다. 그룹 대화의 계정별 모델 스코프도 무변경.

## FR-dataplane-conn-stale-no-reconnect — fixed:deployed:unverified-live (L4↔L8 데이터플레인 연결 재사용에 liveness·재연결 부재)

- **status**: `fixed:deployed:unverified-live` — PR #1036 → main `d2b0e317`, 전체 롤아웃 `50c5a854`
  (web-a/web-b 롤링 + insight-worker/ask-worker + gateway reconcile, soak 통과). 4개 서빙 컨테이너
  전부에서 봉인 심볼·설정 적재 확인.
  **메커니즘은 배포본에서 라이브 실증됨** — 사고와 같은 datasource(`mssql-web-qa`)로 같은 유휴
  (232초)를 재현: 대조(봉인 미경유 원 conn 직접 사용) `DBPROCESS is dead or not enabled` 로 사망,
  봉인 경로는 `dataplane_conn_reconnected` 로그와 함께 자동 재연결되어 쿼리 성공(`재연결됨=True`).
  `verified` 로 닫지 않는 이유(§C5): 배포 후 **실사용자 대화**에 대한 corroboration 재측정
  (끊김 시그니처 distinct_conv 감소)이 아직 남았다 — 다음 audit 이 재측정해 전이시킨다.
  **재진단 금지**: 근본은 확정·봉인됐다. 다음 호출은 corroboration 수치만 갱신할 것.
- **source**: 사용자 명시 호출 — "쿼리 리뷰 : WEB_QA / DB와 연결하지 못하는 이슈".
- **last_seen**: 2026-07-29 · **seen_count**: 3 · **seen_distinct_conv**: 3 (60일)
- **symptom_confidence**: high (사용자 직접 보고 + 전사에 오류 문자열 명시)
  · **rootcause_confidence**: high (코드 + 라이브 재현 실험 + 전사 삼각측량, 대조군 확보)
- **suspected_layers**: **L4↔L8** — 데이터플레인 연결 수명주기(로드 경로)와 datasource/중계장비
  절단 정책(엔진 설정)의 경계. L2 2차 증상(오도하는 거부 피드백) 동반.
- **증상(signal)**: `E-SYS` 도구 실행 오류 반복(허용 DB 28개 전부 `Not connected to any MS SQL
  server`) → `I-FALSE` 답변이 실 DB 대조 없는 정적 분석으로 강등(assistant 가 스스로 "🔴 라이브
  검증 필요" 로 정직 표기). 2차: 부하게이트가 "쿼리를 좁히라" 로 오도해 모델이 ping 쿼리까지 축소.
- **confirmed_root_cause(요지)**: 데이터플레인 연결은 run 시작에 1회 수립되어 그 run 의 모든 도구
  호출에 재사용되는데(`agent_core.run_agent` 단일 경로 / `tools._DatasourceRouter.conn_for` 라우터
  경로), 사용 직전 liveness 검사도 재연결도 없다. 연결이 죽는 두 경로:
  (a) **유휴 사망** — 첫 도구까지 LLM 추론이 수 분(실측 232초. `agent_runtime.steps` 로 run 시작
      10:30:10.7 → 첫 도구 10:34:03.8). 라이브 실험: 대상 datasource 는 60~120초 유휴에 절단
      (t=60 ALIVE → t=120 `DBPROCESS is dead` → t=180 `Not connected…`), 대조 datasource 는 생존.
  (b) **in-run 사망** — 쿼리 타임아웃이 세션을 죽인 뒤(FreeTDS 20003→20047) 4초 만에 온 다음
      도구부터 전부 실패(2026-07-28 관측). 같은 대화의 **다음 run**(새 연결)은 완전 정상.
  죽은 뒤엔 남은 도구 전부가 드라이버 문구로 실패해 사용자 요청이 통째로 무너진다.
- **거짓양성 기각(`refuted`)**: ① `agent_runtime.datasource_health` 는 해당 datasource 를
  **healthy** 로 표시 — 백그라운드 probe 가 매번 **새 연결**을 열기 때문(운영 신호와 실사용 괴리).
  ② 같은 분에 타 제품 대화는 정상 동작(추론 지연 12초) → 전면 장애 반증. ③ TCP 도달·현재 연결
  모두 정상 → 인프라 다운·자격증명 문제 아님. ④ 제품 접근목록은 사고 시각 전후 불변(2026-06-18
  생성) → 설정 변경 기인 아님.
- **corroboration**: structural — 60일 3 대화·3일에 오류 문자열 관측(적은 절대수). 메커니즘 축은
  30일 146 run 중 첫 도구까지 120초 초과 3건(2.1%)이며, 첨부가 큰 쿼리 리뷰 워크로드에 집중된다.
  빈도는 낮으나 Phase 7.4 "명백한 구조결함" 분기 충족(삼각측량 confirmed + 재발경로 infra drift
  + 코드 정본 확정) → 국소-봉인 fix-now.
- **재발경로**: `infra capacity`(중계장비/서버 유휴 절단) + 모델 지연 drift — 둘 다 우리가 통제
  불가 → **코드가 권위선**(재사용 choke-point 의 liveness 계약).
- **fix**: TASK-20260729T110000-dataplane-conn-liveness / `feature-0002-agent-core`
  `CHG-20260729T110000-dataplane-conn-liveness`. Major(코어 데이터플레인 경로) — 사람 승인 완료.
  적대 리뷰 §18.8 3렌즈(codex) CONCERN → 지적 3건 반영(연결 객체 동일성 격리·재연결 후 쿼리 상한
  재적용·end-to-end 테스트), 1건 이월(아래). 테스트 25건 신규.
- **동반 수정**: `_search_tables_mssql` 의 per-DB 실패 삼킴 제거 — 사고 당시 **아무것도 조회하지
  못한 상태를 "검색 결과가 없습니다" 로 위장**해 모델이 테이블 부재를 전제로 리뷰를 진행했다.
  형제 `_search_routines_mssql` 이 이미 받은 하드닝의 대칭 적용(`FR-false-absence-zero-row-catalog-scope`
  와 같은 류가 자매 함수에 남아 있던 것).
- **필요한 사람 액션(1줄)**: 없음 — 배포·라이브 실증 완료. (선택) 대형 첨부 쿼리 리뷰를 실제
  대화에서 1건 돌려 사용자 표면에서도 확인.

## FR-insight-worker-conn-stale — deferred (같은 근본의 배경 스캔 판, 별 cycle)

- **status**: `deferred` — `FR-dataplane-conn-stale-no-reconnect` 의 적대 리뷰(§18.8 QA MAJOR)가
  드러낸 자매 노출면. 사실로 확인했고 **미검증을 완료로 보고하지 않기 위해** 원장에 남긴다.
- **last_seen**: 2026-07-29(코드 독해 기준) · **seen_count**: 0 (라이브 마찰 미관측)
- **rootcause_confidence**: med — 코드 경로는 확정(`modules/insight.py` 가 `connect_with_retry` 로
  만든 `_ds_conn` 을 스캔 내내 직접 재사용, `execute_tool` liveness choke-point 미경유),
  실제 발생 빈도·영향은 미측정.
- **suspected_layers**: L4↔L8 (동일)
- **왜 이번 batch 에 넣지 않았나**: 소비자·실패면·복구정책이 다르다(배경 스캔은 실패를 degraded 로
  기록하고 다음 cadence 에 재시도 — 사용자 요청이 즉시 무너지는 대화 경로와 심각도가 다르다).
  Major 변경의 blast radius 를 한 cycle 에 겹치지 않는다(Phase 7.3 응집 한계).
- **필요한 사람 액션(1줄)**: 별도 cycle 로 insight 스캔 루프에 동일 liveness 계약 적용 여부 판단
  (선행 측정: 스캔 중 `db_failed`/degraded 중 끊김 시그니처 비율).

## FR-ask-orphan-redeploy-dead-air — fixed:undeployed (L4↔인프라 경계; 재배포가 진행 중 답변을 삼키고 회수가 수백초 지연)

- **status**: `fixed:deployed:unverified-live` — **배포 완료**(2026-07-30, PR #1088 merge main
  `76dbfedd` → `deploy-web` 전체 롤아웃: web-a/web-b 무중단 롤링 + insight-worker/ask-worker
  재생성 + gateway reconcile, soak 통과. **4서비스 GIT_COMMIT=76dbfedd healthy**, edge
  `/healthz` ok·mysql_ok·pg_ok). 배포본 런타임 실증: `worker_role=ask_worker`(compose 주입,
  재생성 불변) · `role_prefix=ask-worker[ask_worker]-` · `drain=60` · `role_stale=60` · 봉인 심볼
  6종 적재. **라이브 대화 corroboration 재측정 전** → `unverified-live`.
  후속 `TASK-20260730T172000-dedup-param-cast` 로 봉인 C 활성화(아래 POST-DEPLOY 절).
- **source**: 사용자 명시 호출 `/_dqa:conversation_audit` (2026-07-30) — 지정 대화 "레거시 호환성을
  고려한 실제 DB 기반 쿼리 리뷰", "요청이 도중에 중단된 것으로 추측".
- **last_seen**: 2026-07-30 · **seen_count**: 1 · **seen_distinct_conv**: 8 (60일 고아 재큐 기준)
- **modality**: 그룹 비동기(`is_group=t`) · **product_id(마스킹)**: P-119 · **account(마스킹)**: A-10 ·
  **conv(마스킹)**: …b5f40d99
- **symptom_confidence**: high (사용자 명시 보고 + 라이브 데이터 완전 재현)
  · **rootcause_confidence**: high (코드 file:line + `ask_jobs`/`steps`/`core_messages`/`messages`
  + 컨테이너 타임스탬프 4중 삼각측량)
- **suspected_layers**: **L4↔인프라 경계** — 큐/워커 lifecycle(코드)과 배포 재생성(인프라)의 경계.
  L7 에서 표면화(스피너 8분 고착·사용자 메시지 중복 표시).
- **증상(signal)**: `E-USR` 명시 보고 + `I-INT` 중복 메시지 + `I-FALSE` — job 483 이 15:38 에 답변
  초안까지 만들고 red-team 자가검증 중 15:41:32 에 배포로 죽었고, 회수가 15:49:18 에야 일어났다.
  재실행은 사용자 메시지를 한 번 더 저장한 뒤 LLM timeout 으로 최종 error. **사용자는 14분을
  기다려 중복 메시지와 오류만 받았다.**
- **confirmed_root_cause**: `modules/ask.py` `_worker_id()` 가 `socket.gethostname()`(=컨테이너 id)
  기반이라 컨테이너 **재생성**마다 값이 바뀐다 → `ask_jobs.reclaim_worker_jobs_on_boot` 의
  `claimed_by = worker_id` 정확일치가 **항상 0행**. `bin/deploy-web.sh` 는 워커를
  `--force-recreate` 하므로 **"배포로 죽은 job" 은 자가회수가 구조적으로 불가능**했고, 전역 stale
  sweeper 의 `AGENT_ASK_WORKER_STALE_SEC`(런타임 실측 450s) 창을 통째로 기다렸다. 부수 결함:
  재실행이 `agent_core._save_message(user)` 를 다시 돌아 사용자 메시지를 중복 저장.
  재발경로 = **infra(배포마다 재생성) — 단 우리 통제 안** → 코드가 권위선.
- **corroboration**: **structural** — 60일 고아 재큐 **8건 / 8 distinct_conv**(전체 482 job ·
  209 대화 ≈ 3.8%), 생성→재시작 dead-air **142~1,649초**(중앙값 ~700s), **3건 최종 error**.
  중복 사용자 메시지(연속 동일 user 행) **9건 / 9 distinct_conv**.
- **거짓양성 기각(`refuted`)**: ① 같은 대화 07-29 17:38~17:39 사용자 3건 무응답은 **그룹
  `@assistant` 멘션 게이트**(`conversations.py` `group_requires_mention`, 의도된 동작 F4) — 결함
  아님. ② `FR-dataplane-conn-stale-no-reconnect` 재발 아님(연결 절단 시그니처 부재, 워커 프로세스
  소실이 원인). ③ 진행 중 병렬 cycle(FE 말풍선 `enqpre-run-handoff`, 이미 머지된 llm-timeout)과
  파일 중첩 없음 — F3 중복 기각.
- **봉인**: (A) 종료 시 lease 명시 반납 + 반납 직후 cancel 마킹(겹침 창을 heartbeat 주기 → cancel
  폴링 주기로 축소) (B) worker identity 를 재생성 불변 role 로 분리(`AGENT_WORKER_ROLE` >
  `AGENT_SESSION` > hostname) + `ask-worker[<role>]-` 경계 + 같은 role 의 죽은 이전 인스턴스를
  `ROLE_STALE_SEC`(60s)로 회수(SIGKILL backstop) (C) 재시도에서만 근거 기반 중복 저장 억제.
  **전역 `STALE_SEC` 불변**, cap 회계는 전역 sweep 과 동일, 보안 경계 무변경.
- **disposition 근거**: Major(§12.3 — 코어 워커 lifecycle·동시성) → attended human-decision.
  사용자가 AskUserQuestion 으로 봉인 범위 **A+B+C** 명시 선택(2026-07-30) → PLAN-APPROVED 후 구현.
  structural corroboration + 코드 file:line confirmed(high) → fix-now.
- **fix**: `CHG-20260730T160000-ask-redeploy-handoff` / **코드 거주 `feature-0002-agent-core`**
  (+ `shared/config.py` knob 2종) / `REV-20260730T160000-ask-redeploy-handoff`
  (§18.8.2 제약-없는-채널 우선 → codex 적대 2라운드 backend+security+qa, P1 5건 전건 수정 → P1 0건).
- **rc_ids**: RC-1(회수 지연) · RC-2(중복 저장) · **batch-id**: B-20260730T160000-ask-redeploy-handoff
- **범위 밖(deferred/인지)**: ① 재시도가 1차 시도의 답변 초안·red-team 라운드를 재사용하지 않는다
  (전량 재실행) — 부분 산출 이월은 별 cycle. ② `insight-worker` 도 같은 hostname 기반 식별을 쓰나
  소비자·복구 정책이 다르다(배경 스캔은 다음 cadence 재시도) — 응집 범위 밖. ③ 반납 후 cancel
  마킹이 KV 장애로 실패하면 fencing 이 기존 heartbeat 경로(≤10s)로 복귀(수용, REVIEW 근거 기록).
- **라이브 실측 필요분(§정직)**: 코드/테스트는 "인계 계약이 동작함" 까지만 증명한다. **"실제 대화의
  dead-air 소멸"** 은 배포 후 실측분(미수행) → 다음 audit 이 corroboration(`attempts>1` 재큐의
  생성→재시작 중앙값 · 연속 동일 user 메시지 distinct_conv) 재측정 → 감소 시 `verified`, 재증가 시
  `regressed`.
- **POST-DEPLOY 실측 (2026-07-30, 정직 기록)**:
  - **결함의 심각도가 진단 시점보다 크다**: 회수 창 `AGENT_ASK_WORKER_STALE_SEC` 는
    `AGENT_TIMEOUT_SEC` 파생(`max(timeout×3,…)+180`)이라, 병렬 세션이 timeout 을 90→**900** 으로
    올린 뒤 창이 450s → **2,880s(48분)** 로 함께 커져 있었다. 즉 **LLM 타임아웃을 튜닝하면 고아
    job 의 무응답 상한이 조용히 같이 커지는 결합**이 있다. 본 봉인의 `ROLE_STALE_SEC` 는
    `AGENT_TIMEOUT_SEC` 와 무관한 고정 60s 라 이 결합을 끊는다.
  - **라이브 재현·회복 관측**: 배포 직전 job 485(대상 대화, 15:57 요청)가 16:10 타 세션 배포로
    죽어 **42분 좀비**였고, 전역 sweeper 가 16:59:44 에 회수 → 신규 워커(새 형식
    `ask-worker[ask_worker]-…`)가 17:00:08 claim → **17:02:07 답변 완료**. 사용자 원 요청 해소.
  - **전환기 공백(1회성)**: 구 형식 `claimed_by` 로 claim 된 job 은 새 role 패턴에 매칭되지 않아
    본 봉인이 구제하지 못한다. 이번 배포로 고아가 된 job 488 은 **사용자 승인 하에 1회 수동
    requeue**(sweeper 와 동일 전이, `pending`+`lease_epoch++`) → 신규 워커가 ~0.4s 안에 재claim.
    배포 이후 claim 되는 job 부터 봉인 발효.
  - **봉인 C 는 배포 시점에 무력이었다**: job 485 재시도가 사용자 메시지를 다시 중복 저장
    (6301↔6322). 원인 = 판정 SQL 의 `%(mirror_sender)s IS NULL` 파라미터에 타입 컨텍스트가 없어
    PG 가 쿼리를 거부 → `_read_runtime_pg` 예외 흡수 → fail-open 저장. FakeConn 테스트가 실 SQL 을
    실행하지 않아 못 잡았다(적대 리뷰 P2 로 이미 지적됐던 공백). 수정
    `CHG-20260730T172000-dedup-param-cast`(`::text`/`::bigint` 캐스트 + 실 PG 5케이스 검증).
