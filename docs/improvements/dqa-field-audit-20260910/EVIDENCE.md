---
doc_type: EVIDENCE_LEDGER
initiative: dqa-field-audit-20260910
scope: DQA 실무 검증 개선 요구서(2026-09-10) 재현·원인 근거 원장
task_id: META-0076-dqa-field-audit
baseline_commit: 36c5940f
created_at: 2026-09-10
edit_policy: append-only
---

# 근거 원장 — DQA 실무 검증 개선 요구서(DQA-01~09)

이 문서는 요구서(`01_DQA_실무검증_개선요구서.md`)의 관측을 **당시 작업 기록**과 **현재 코드**에서 무엇으로 확인했는지 항목별로 고정한다.
설계(`DESIGN.md`)의 각 ITEM 은 이 원장의 근거 ID 를 인용한다. 근거 없는 결함 단정은 하지 않는다.

- 근거 루트(WSL 경로): `/mnt/e/Masang/MSSQL/BackupDB/20260903/dqa-work` (요구서 §7). 본 원장은 **파일명·집계 수치·필드명만** 인용하며 원문 로그·SQL 본문·계정 식별자 값을 복제하지 않는다.
- 근거 등급: `[기록]` = 보관된 요청·실행·검증 결과에서 확인 · `[관찰]` = 당시 개선 목록의 서술(현 코드 재현 필요) · `[코드]` = 현재 코드(`36c5940f`)에서 file:line 으로 확인 · `[사용자]` = 요청자 확정.

## E-00 대화·실행 개요 `[기록]`

| 항목 | 값 | 출처 |
|---|---|---|
| 대화 | `20260909063217-b51df002`, Product 91(`DK`, mode pinned), runtime codex, 제출 경로 DQA Web UI | `admin-conversation.json` |
| 실행 4회 | `t_-Kg9_FC37xDQKTy9`(290 steps) · `t_iVYpn33H3OUuivwb`(86) · `t_0uctBN9MvFVXyDoG`(4) · `t_mWsdiG4lQxWBk1Wr`(22) | `admin-history.json` `messages[*].meta` |
| 1차 실행 시간 | total 1,526,000ms = 25분 26초 (queued 1,137,000ms = 18분 57초 · inference 389,000ms) | `messages[1].meta.duration_breakdown` |
| 2차 실행 시간 | total 938,000ms (queued 541,000 · inference 397,000) | `messages[3].meta.duration_breakdown` |
| step 레코드 필드 | `step_index, action, tool, work, work_source, reason, reason_source, args, sql, result_summary, error, created_at, run_id` — **호출별 고유 ID 필드 없음** | `messages[1].meta.steps[*]` |

## E-01 계정별 실행기 인수 (DQA-01)

- E-01a `[사용자]` mckim 계정의 `내 AI 실행` 요청을 이미 열린 admin 클라이언트가 흡수한 뒤 진행하지 않음 → 웹도 admin 으로 로그인해 진행. (`DQA-IMPROVEMENTS.md` 실행·관리 P1 1행)
- E-01b `[기록]` `conversation_id` 를 생략한 `/api/ask` 호출은 현재 대화를 재사용 (`DQA-IMPROVEMENTS.md` P2 6행). 별도 새 대화 응답은 `conversation.json` (`"output": "새 대화: …"`, `product_mode: pinned`).
- E-01c `[코드]` 러너 점유는 선착순 원자 UPDATE(`WHERE ClaimedBy IS NULL`) — 같은 계정 내 러너 경합은 `TASK-20260901T173000-stale-runner-yield.md` §2 / `TASK-20260901T183000-newest-runner-wins.md` §1~3 가 「연결 순서」축으로 정리(계정이 다르면 예외 — 사용자 규칙). **계정 간 경계는 그 규칙의 전제이지 검증 대상이 아니었다** → 코드 매핑에서 claim 시 요청 계정 = 러너 계정 대조 유무를 확정(§E-01d).
- E-01d `[코드]` claim 경계 실측 — `routers/ai_tools.py:2725 claim_request` 의 계정 대조는 `_dispatch_scope_sql(:380)` 의 `(Kind=chat AND Origin=web AND AccountId=%s)` 에 **암묵**적으로만 존재하고, 본문 `runner_instance`(:2754) 는 토큰의 heartbeat 인스턴스와 대조 없이 기록되며, 거절은 산문 404(:2789)/409(:2792) 로 기계 판독 reason 이 없다. 30분 lease(`shared/bridge_tasks.py:113`) 외 인수 대기 제한·시도 횟수 컬럼 없음(`_bootstrap_schema.py:2497-2527`). 웹 채팅 중복 방지 없음(콘솔 잡만 `open_job_exists:1179`). `/api/ask` 는 `lazy_create` 불리언 + `_repair_current_conversation`(`conversations.py:5533-5556`) 으로 현재 대화를 조용히 재사용. 클라이언트 `client/core.py:1233 connection_identity` 는 `account_id` 를 받아 폐기, `client/bridge.py:481-520` 은 세션/토큰 동일성만으로 상주 러너 재사용.

## E-02 도구 승인 오류·실행 상태 (DQA-02)

- E-02a `[기록]` 승인 필요 오류 9건: `permission-failures.json` — 4:55:30Z~4:56:44Z 사이 9회, 메시지 유형 2종(`This Bash command contains multiple operations. The following part requires approval: cd … && python dqa_query.py server_info` 2회 · `This command requires approval` 7회). 즉 러너 AI 가 **셸 경유 보조 스크립트**로 조사를 시도했고 하네스 권한 프롬프트에 막혔다.
- E-02b `[관찰]` 위 반복 중 bridge 상태 `working`, 일반 진행 API 는 빈 단계 목록 (`DQA-IMPROVEMENTS.md` P1 3행). `admin-status.json` 은 종료 후 스냅샷(`is_processing=false, status="", step_count=0`)이라 당시 불일치 자체의 기록은 아니다.
- E-02c `[기록]` **무거운 쿼리 보호로 미실행된 호출의 `error` 가 빈 문자열**: 1차 실행 heavy 차단 16건(execute_sql 104건 중), 2차 실행 10건 — 전부 `error=''`, 차단 사실은 `result_summary.preview` 의 안내 문구(`⚠ 무거운 쿼리로 추정됩니다 (예상 처리 ~N행 > 임계 1,000,000행) — 실행하지 않았습니다 …`)에만 존재. 1차 실행 전체에서 `error` 비어 있지 않은 step = **0건**.
- E-02d `[기록]` 1차 실행 step 290건 중 `tool=''`(action=activity, work_source=bridge-runtime) 146건 — 진행 안내 행이 도구 호출 행과 같은 `step_index` 공간을 공유.

## E-03 비공개 Product 초기 권한 (DQA-03)

- E-03a `[관찰]` 비공개 Product 990002 생성 후 생성자·관리자 접근 불가, 권한 부여도 자기 권한 초과 403. 재현 Product 는 비활성, 권한 확대 없음 (`DQA-IMPROVEMENTS.md` P1 4행).
- E-03b `[코드]` 원인 확정 — `unit/feature-0003-agent-web-ui/src/routers/admin_products.py:1259-1325` `admin_create_product` 트랜잭션: `WebProducts` INSERT(:1262) → 동적 권한 `product.access.<key>` INSERT(:1282) → **`default_role_access=true` 일 때만 역할 grant(:1301-1308)**. 비공개(`DefaultRoleAccess=0`)면 아무 주체에게도 grant 되지 않은 채 commit(:1310). 소유자 컬럼·멤버십 테이블 없음(접근 = RBAC 동적 권한 코드 단일 모델, `web_context.py:3631-3637` `_product_permission_code`).
- E-03c `[코드]` 403 의 원인 — 부여 경로 2곳이 「행위자가 보유한 권한 코드」로만 부여 허용: `routers/admin_accounts.py:593-620` `_enforce_override_self_scope`(403 변환 :207-208) · `routers/admin_roles.py:464-495` `_enforce_role_permission_self_scope`. 비공개 Product 의 코드는 **누구도 보유하지 않으므로 모든 부여 경로가 영구 403** (admin 역할명 우회 없음 — 유지해야 할 올바른 동작). `docs/SECURITY.md:1144-1170` §28.6 자기 잠금 경로가 같은 구조를 이미 기술.
- E-03d `[코드]` 감사 행은 별도 두 번째 트랜잭션(:1327-1354) — 「생성」이 이미 2 commit.
- E-03e `[코드]` 기존 테스트에 `POST /api/admin/products` 를 실행하는 케이스 **0건**; self-scope 가드의 `product.access.*` 케이스 0건.

## E-04 대용량 전수 결과 (DQA-04)

- E-04a `[기록]` 2차 실행 step 36 `execute_sql` `error='반환 행수 89,623행이 건당 상한 10,000행을 넘어 결과를 돌려주지 않았습니다.'` — DB 실행 후 결과 미반환(부하는 발생, 파일 없음).
- E-04b `[기록]` 1차 응답은 전수 요청에 상위 50행 표본을 첨부하고 표본임을 명시(`dqa-answer-1.md:107` 「캐릭터별 확정 전수 결과는 미완료 … 50행은 … 표본」).
- E-04c `[기록]` 전수 검증본: `followup-verification-summary.json` usage_rows 89,623 / usage_points 18,524,408 / candidate_rows 3,782 / distinct_log_names 3,112(단일 2,756·복수 264·미매칭 92) — DQA 첨부가 아닌 별도 검증 재실행 결과(출처 구분 유지).
- E-04d `[코드]` 외부 SQL 호출은 `routers/ai_tools.py:3935-3937` 에서 `_suppress_csv=True`, `:3973-3991` 에서 `total_rows > cap`(`_sql_max_rows:441-453`, 기본 10,000) 이면 **이미 메모리에 적재된 결과를 버리고** 413. 코어 `_tool_execute_sql(modules/tools.py:3045)` 은 `tools.py:20` alias 로 `shared/db.py:996 execute_sql` 을 호출해 전량 적재; `render.py:62-74 save_csv` 는 전량 쓰기·체크섬·TTL 없음; `_stats_out(:3187-3190)` 은 `total_rows`·`csv_paths` 만.

## E-05 집계 정의·데이터 범위 (DQA-05)

- E-05a `[사용자]` LogTime 은 KST 그대로 저장(2차 요청 본문 「사용자 확정사항」). 서비스 설명의 UTC 와 상이.
- E-05b `[기록]` 정규 로그만 사용 시 누락되는 사용 포인트 5,645,490 을 DQA 가 원본/Load/Error 계보에서 보완(`DQA-IMPROVEMENTS.md` 정확성 P1 4행).
- E-05c `[기록]` 이름 매칭 단일/복수/미매칭 혼재(E-04c), 계정 단위 잔액 3,101,567 vs 기간 순변동 3,007,817(차이 93,750 미확정) — `DQA-STATISTICS-REPORT.md` §5.
- E-05d `[기록]` 1차 실행 rationale 에 「서버253 … 실제 시간 커버리지 … 집계 기준을 확정」 단계가 명시 — 시간대·범위 확정이 매 실행 조사 비용으로 반복됨.

## E-06 첨부 실패·선택 재전달 (DQA-06)

- E-06a `[기록]` 2차 답변 말미 배너: `⚠️ 첨부 전달 실패 — 아래 파일은 새 버전으로 저장되지 않았습니다. · 사유 미상 3건 — 블록 형식 오류이거나 한 답변의 첨부 개수 상한을 넘었을 수 있습니다.` (`dqa-answer-2.md:82-84`) — **파일명·단계·오류 코드 없음**.
- E-06b `[기록]` 3차 요청은 사용자가 누락 3건을 파일명으로 특정해 재첨부만 요청(`messages[4]` 본문 「첨부 3건 전달 실패를 확인 … 3개만 첨부」) → 4 step, 88초로 성공. 개수 상한이 원인이라는 근거는 없음.
- E-06c `[기록]` 첨부 메타 스냅샷 `admin-attachments.json` 은 `sha256, status=uploaded, version_number, root_attachment_id, superseded, lifecycle_state` 필드를 보유 — 버전·계보 모델은 존재.

## E-07 비용 보호·조사 결과 재사용 (DQA-07)

- E-07a `[기록]` 1차 execute_sql 104회 중 heavy 미실행 16회, 2차 24회 중 10회(E-02c). 안내 문구가 예상 처리 행수·임계(1,000,000)·`confirm_heavy=true` 우회를 설명하나, **판단 근거(추정 방식·계획 출처)는 step 레코드에 별도 필드가 없다**.
- E-07b `[기록]` 2차 step 32 예상 처리 `~873,153,351,052행` — 계획 원문 미대조. 계산 오류로 단정하지 않음(요구서 DQA-07).
- E-07c `[기록]` 같은 무기 집계가 종료일 유무와 무관하게 ~53억 행 추정 → 2회 미실행 후 명시 heavy 실행, 실제 7.44초/5.63초 (`DQA-IMPROVEMENTS.md` 「재집계 부하 추정」).

## E-08 미리보기 잘림·병렬 호출 추적성 (DQA-08)

- E-08a-code `[코드]` 중복 원인 체인 — `routers/ai_tools.py:1729-1790 _insert_bridge_step` 은 `pg_advisory_xact_lock(:1749)` 뒤 `INSERT … SELECT COALESCE(MAX(step_index),0)+1` 을 실행하지만, 연결은 `_pg()(:564)` → `modules/runtime_backend.py:1208 _get_pg_runtime_conn` → `shared/db.py:1073 _pg_connect(autocommit=True)(:1119)` 라 문장 단위 트랜잭션이다. xact 락은 SELECT 문장 종료 시 즉시 해제되어 INSERT 를 덮지 못하고, 병렬 두 호출이 같은 MAX 를 읽어 같은 번호를 쓴다(fit review 재검증 일치).
- E-08a `[기록]` **`step_index` 중복**: 1차 실행 {4: describe_schema×2(15:33:07.961 동시각, 다른 schema_name), 5: activity×2, 12: describe_table×2, 13: activity×2} · 2차 실행 {12: read_task_attachment×2, 13: activity×2, 74: execute_sql×2(다른 SQL)} — 병렬 도구 호출이 같은 번호를 받고, 고유 호출 ID 필드가 없어 결과·오류·첨부를 호출에 정확히 연결할 수 없다.
- E-08b `[기록]` `preview_truncated=true` 는 `result_summary` JSON 안에 있고(1차 75건·2차 24건), 잘린 지점이 표 행 중간(`| CharacterDragonCube | 812 ` 로 끝남 — 셀 값 중간 절단).
- E-08b-code `[코드]` 잘림 불일치의 구조 — `agent_core.py:5764-5786 _build_step_result_summary` 가 마크다운을 `_STEP_PREVIEW_CAP_CHARS=500`(:5761) 로 **문자 절단** 후 `preview_truncated` 를 세우고, `render.py:158-192 parse_result_preview_table` 은 그 잘린 텍스트를 다시 파싱하며 `startswith("|")` 행을 빈 셀 패딩으로 정상 행 승격(:180-186), `truncated` 는 잘려 나간 꼬리의 정규식(:187) 으로 판정 → `preview_truncated=true ∧ preview_table.truncated=false` 와 반행 값(`1`) 이 구조적으로 발생한다. 프론트 `static/app/messages.js:313` 은 `truncated:false` 하드코딩.

## E-09 연결 진단·입력 검증·좁은 화면·역할 전달 (DQA-09)

- E-09a `[관찰]` WSL 호스트 주소 172.28.64.1 실패 → 172.26.144.1 로 갱신 후 약 19ms 검사 통과 (`DQA-IMPROVEMENTS.md` P2 5행). 주소 자동 변경은 요구 밖.
- E-09b `[관찰]` Product Description 초과 입력 시 `Data too long for column 'Description'` 내부 DB 오류 반환 (`DQA-IMPROVEMENTS.md` 「추가 재현」). `[코드]` `admin_products.py:1241-1252` 생성 검증에 길이 검사 없음 · `:1313-1320`/`:1470-1476` 예외 문자열을 `_json_error(…, 500)` 로 그대로 반환 · DDL `Description VARCHAR(255)`(`_bootstrap_schema.py:755`) · 프론트 `static/admin/products.js:817-830` input 에 `maxlength` 없음 · `static/admin.js:3928-3931` 일괄 실패 토스트가 첫 실패 사유를 계산만 하고 미표시.
- E-09c `[관찰]` 약 574px 폭에서 사이드바·새 대화 진입 경로 비노출 (`DQA-IMPROVEMENTS.md` P2 8행). `[코드]` `static/css/profile.css:487-499` `@media (max-width: 680px) { .sidebar { display: none } }` — 유일한 「새 대화」 진입 `index.html:113-117 #newConversationBtn` 이 사이드바 안에만 있고 토글 버튼 없음; 680 임계는 `app.js:3815`·`profile.js:846` 에도 하드코딩.
- E-09d `[관찰]` Windows 런타임 기록 `system_delivery=user_body` (`DQA-IMPROVEMENTS.md` P2 7행). `[코드]` `unit/feature-0043-external-llm-bridge/docs/PROMPT_DELIVERY.md` 가 전달 3분기(Claude `--append-system-prompt` / Codex·미지원 → user 본문 앞 / Windows 길이 초과 → stdin 본문)를 정본으로 기술 — 본문 폴백은 **설계된 동작**이며 `system_delivery` 필드는 그 진단용. 요구는 「지원되는 구조화 입력으로 역할 보존」 → 파일 전달(`--append-system-prompt-file`) 등 대체 채널의 실 Windows 검증이 필요(DESIGN §ITEM-09d).

## 회귀검증 기준값 (요구서 §5 — 고정 복원본 한정, 코드 상수 금지)

| 대상 | 값 | 출처 |
|---|---|---|
| 프리미엄 사용 전수 | 89,623행 / 18,524,408포인트 | `followup-verification-summary.json` |
| 일별 사용(08-27~09-03) | 977,367 / 3,261,183 / 3,104,502 / 2,909,370 / 2,497,670 / 2,451,119 / 2,490,488 / 832,709 | 요구서 §5 |
| 이름 매칭 | 고유 3,112 = 단일 2,756 + 복수 264 + 미매칭 92 · 후보 행 3,782(합산 단위 아님) | `followup-verification-summary.json` |
| 플로린 | 4,393,189,877 + 2,900,000 = 4,396,089,877 | `followup-verification-summary.json` |

이 값들은 fixture 가 아닌 **실 복원본 통합검증**에서만 쓴다. 단위 테스트는 0 / 10,000 / 10,001 / 89,623 행 경계를 합성 데이터로 검증한다.
