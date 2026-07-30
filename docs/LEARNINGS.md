---
doc_type: LEARNINGS
scope: project
status: active
edit_policy: append-only
source_of_truth: true
---

# AI Learnings

AI 작업 중 발견된 교훈, 패턴, 주의사항을 누적 기록한다.
새 AI 세션은 이 문서의 최근 항목을 참조하여 동일한 실수를 반복하지 않는다.

## 기록 규칙
- 항목 ID: `LRN-YYYYMMDD-NNNN`
- 카테고리: `mistake` | `pattern` | `quirk` | `preference`
- 사용자 확인 후: `verified: true` 추가
- 아카이빙: 20건 초과 시 `_archive/LEARNINGS-archive-NNNN.md`로 이동

---

## Category: mistake

### LRN-20260730-0001 — 워커 소유권을 **컨테이너 hostname** 으로 잡으면, 자가회수는 정확히 "배포로 죽었을 때" 만 조용히 no-op 한다
- Source: `/_dqa:conversation_audit` — 사용자 보고 "요청이 도중에 중단" 근본 진단 (2026-07-30, `FR-ask-orphan-redeploy-dead-air`)
- verified: false (코드/테스트·라이브 데이터 재현까지. "실제 대화 dead-air 소멸" 은 배포 후 실측분)
- Mistake: ask-worker 는 job 을 `claimed_by = f"ask-worker-{gethostname()}-{pid}"` 로 claim 하고, 부팅 시 **자기 이름과 정확히 일치하는** running job 을 회수해 "SIGKILL 잔재 자가 정리" 를 한다고 믿었다. 그런데 배포는 컨테이너를 `--force-recreate` 하고, 재생성된 컨테이너는 **hostname 이 바뀐다**. 즉 이 자가회수는 프로세스만 재시작된 드문 경우에만 작동하고, **실제로 고아가 생기는 유일하게 흔한 경우(배포)에는 항상 0행**이었다. 조용한 no-op 이라 로그에도 남지 않았다. 고아 job 은 "정상 장기 run 을 오회수하지 않으려" 매우 보수적으로 잡아둔 전역 stale 창(실측 450s)을 통째로 기다렸고, 사용자는 답변이 이미 만들어졌는데도 수백 초를 빈 화면으로 기다린 뒤 재실행 실패를 받았다(60일 8대화, dead-air 142~1,649초, 3건 최종 error). 같은 계열의 결함(HOSTNAME 기반 식별이 재배포에 깨짐)이 **같은 날 다른 서브시스템에서 이미 고쳐져 있었다** — 한 곳을 고칠 때 같은 식별 패턴을 쓰는 형제 경로를 전수로 훑지 않은 것이 두 번째 실수다.
- Correct approach: (1) **워커 식별자를 "인스턴스" 와 "역할" 두 축으로 분리한다.** 역할은 배포·재생성에 불변인 소스(오케스트레이터가 주입하는 role/서비스명 env)에서 얻고, 인스턴스는 hostname+pid 로 둔다. 자기 잔재 회수는 인스턴스 축으로, **이전 인스턴스 회수는 역할 축**으로 한다. (2) **역할 경계는 구분자로 못박는다** — `role-` prefix 매칭은 role `x` 가 role `x-y` 의 job 을 삼킨다. 구분자를 감싸고(`[role]-`), role 문자열이 그 구분자를 포함하지 못하게 **단사(injective) 위생**을 건다(단순 제거는 `x-y` 와 `x]-y` 를 같게 만들어 문제를 되살린다). (3) **회수를 임계 추측이 아니라 인계 계약으로 만든다** — 죽기 전에(graceful 종료 예산 안에서) 자기 lease 를 명시 반납하는 것이 가장 확실하다. 임계 기반 회수는 반납이 불가능한 경로(SIGKILL/OOM)의 backstop 으로만 둔다. (4) **회수를 빠르게 만들면 "구 실행자와 신 실행자의 겹침 창" 이 새로 생긴다** — 종전엔 수백 초 뒤 회수라 구 프로세스가 이미 죽어 있었다. 반납 즉시 그 run 에 취소를 마킹해 창을 heartbeat 주기가 아니라 취소 폴링 주기로 좁혀야 한다. (5) **재시도는 부작용이 멱등이어야 한다** — 요청 저장이 run 안에 있으면 재시도마다 사용자 발화가 화면에 한 줄씩 늘어난다. 다만 무조건 skip 은 1차 시도가 저장 전에 죽은 경우 요청문을 통째로 잃으므로, **존재 확인 기반**으로 억제하고 확인 불가 시엔 저장 쪽으로 fail-open 한다.
- Applies to: 재시작·재배포되는 모든 큐 소비자(ask-worker·insight-worker·cron 워커). 본 수정은 ask 경로만 덮었고 insight-worker 는 같은 hostname 기반 식별이 남아 있다.
- 진단 레시피(재사용): ① `ask_jobs` 의 `attempts>1`/`lease_epoch>1` 행을 뽑아 **생성→재시작 간격**을 재면 회수 지연이 즉시 수치화된다(빈도는 낮아도 심각도는 최상). ② 그 간격이 stale 임계와 비슷하면 "자가회수가 안 돌았다" 를 의심하고, 소유자 문자열이 무엇으로 구성되는지 본다. ③ 컨테이너 `CreatedAt`/`StartedAt` 을 job 타임라인 위에 겹쳐 놓으면 배포 기인 여부가 바로 갈린다. ④ **`steps` 를 읽어 죽은 시점에 무엇을 하고 있었는지** 본다 — 이번엔 "답변은 이미 만들었고 자가검증 중" 이어서, 손실이 "요청 접수 실패" 가 아니라 "완성된 답변 폐기" 임이 드러났다. ⑤ 재시도가 만든 흔적(연속 동일 user 메시지)은 별도 corroboration 축이 된다.

### LRN-20260729-0001 — run 시작에 열고 run 내내 재사용하는 원격 연결은 "쓰기 직전 살아있는지" 를 계약으로 두지 않으면, 유휴 절단 한 번이 그 run 전체를 무너뜨린다
- Source: `/_dqa:conversation_audit` — 사용자 보고 "DB와 연결하지 못하는 이슈" 근본 진단 (2026-07-29, `FR-dataplane-conn-stale-no-reconnect`)
- verified: true (배포본 라이브 재현 — 같은 datasource·같은 유휴 232초에서 대조 경로 `DBPROCESS is dead`, 봉인 경로 자동 재연결 성공)
- Mistake: 데이터플레인 연결을 run 시작에 1회 수립해 그 run 의 모든 도구 호출에 재사용하면서 **사용 직전 liveness 검사와 재연결을 두지 않았다**. "연결 수립에 성공했다" 를 "쓸 때도 살아있다" 와 동일시한 것이 오류다. 원격 DB 는 두 방식으로 조용히 죽는다 — (a) **유휴 절단**: 첫 도구까지 LLM 추론이 수 분 걸리는 동안(실측 232초) 서버/중계장비가 유휴 연결을 끊는다(실측 절단 하한 60~120초). (b) **in-run 사망**: 쿼리 타임아웃이 세션을 죽인다. 죽은 뒤엔 그 연결 객체가 영구 불능이라 **남은 도구 호출 전부**가 드라이버 문구로 실패해, 사용자에겐 "DB 접속 자체가 안 됨" 으로 보이는데 서버는 멀쩡하다. 진단을 더 어렵게 만든 것은 **헬스 대시보드가 healthy 였다는 점** — 백그라운드 probe 는 매번 *새* 연결을 열어 성공하므로, 재사용되는 연결의 사망을 구조적으로 볼 수 없다.
- Correct approach: (1) **재사용되는 원격 연결은 "쓰기 직전 살아있음" 을 choke-point 계약으로 둔다** — 마지막 성공 사용 후 임계를 넘겼으면 cheap ping, 실패면 **같은 좌표로** 재연결. 좌표를 재해석하지 말고 원 연결을 만든 호출자의 콜백을 그대로 재호출해야 격리(allowlist·회로차단기·DB pin)가 유지된다. (2) **실패한 문장 자체는 자동 재시도하지 않는다** — 타임아웃으로 죽은 경우 그 쿼리는 서버에 도달했을 수 있어 재실행이 부하를 2배로 만든다. 그 호출만 실패시키고 *다음* 호출부터 복구하면 (a)는 완전 봉인, (b)는 피해가 "run 전체" 에서 "도구 1회" 로 줄어든다. (3) **임계 기반 ping 생략에는 탈출구가 필요** — 끊김이 한 번 관측된 연결은 임계와 무관하게 반드시 ping 한다(실측에서 타임아웃 사망 후 다음 호출까지 4초였다 — 30초 임계였다면 그대로 통과했을 것). (4) **재연결은 세션 스코프 상태를 날린다** — `SET SESSION` 류로 건 보호(쿼리 시간 상한 등)를 재연결 직후 재적용하지 않으면 조용한 보호 공백이 생긴다.
- Applies to: run/세션 수명 동안 원격 연결을 붙잡는 모든 경로. 본 수정은 대화 도구 경로(`tools.execute_tool`)만 덮었고 **insight-worker 배경 스캔(`modules/insight.py` `_ds_conn`)은 같은 노출이 남아 있다**(원장 `FR-insight-worker-conn-stale`, deferred).
- 진단 레시피(재사용): ① 실패 대화와 **성공한 동시각 대화**를 대조해 전면 장애를 먼저 반증한다. ② `agent_runtime.steps` 로 **run 시작 → 첫 도구 간격**을 재면 유휴 사망 가설이 즉시 판별된다. ③ 헬스 테이블이 healthy 인데 실사용이 실패하면 "probe 는 새 연결, 실사용은 재사용 연결" 을 의심한다. ④ 확정은 코드 독해가 아니라 **연결을 실제로 재워 보는 실험**(t=30/60/120/180 tick + 대조 datasource)으로 한다.


### LRN-20260714-0001 — 반복 실행 스크립트(cron)는 "이전 실행이 끝나지 않았을 가능성"을 기본 가정하고 동시성 가드를 갖춰야 한다 — 없으면 실패 누적이 자원 고갈로 전이되어 무관한 서비스까지 무너뜨린다
- Source: 사용자 장애 리포트("로그인 후 빈 화면, 작업 콘솔 미작동") 근본원인 조사 (2026-07-14, feature-0016 §82)
- Mistake: `bin/metadata-graph-sync.sh`(AGE 그래프 동기화)가 root crontab `*/30 * * * *` 로 호출되는데 **동시성 가드(flock 등)가 전혀 없었다**. 이전 실행이 AGE 그래프 노드 lock 경합으로 멈추면(이미 `docs/LEARNINGS.md` 에 "graph-sync 병렬 deadlock" quirk 로 기록돼 있던 클래스), cron 은 그 사실을 모른 채 30분마다 새 실행을 계속 겹쳐 쌓았다. 결과: 최소 ~20시간 동안 `metadata_graph_sync.py` 20개가 동시에 같은 그래프 노드에 대해 서로 잠금 대기(순환 체인, 최대 1h19m)를 형성 → pgbouncer 커넥션 풀(`default_pool_size=20`)이 전량 lock-wait 로 소진 → **그래프 동기화와 무관한** ask-worker(사용자 대화 처리)·insight-worker 전체가 `query_wait_timeout` 으로 연쇄 실패 → 로그인 후 빈 화면·작업 콘솔 미작동(전 사용자 영향). 이미 문서화된 quirk(수동 kill 대응)가 있었음에도 **재발 방지(가드)는 별도 후속으로 남겨진 채 방치**돼 동일 원인이 훨씬 큰 규모로 재발했다.
- Correct approach: (1) **cron/timer 로 호출되는 모든 스크립트는 기본값으로 `flock -n`(또는 동등한 non-blocking lock) 가드를 갖춘다** — "이전 실행이 아직 살아있을 수 있다"를 예외가 아니라 기본 가정으로 둔다. (2) 그 자원(여기서는 AGE 그래프 lock)이 다른 무관한 서비스와 **커넥션 풀을 공유**한다면, 한 반복 작업의 정체가 풀 전체를 고갈시켜 무관한 기능까지 넘어뜨릴 수 있음을 설계 시점에 고려한다 — 실패 격리(pool 분리, 타임아웃 하한)가 없으면 "부수적 배치 작업"이 "핵심 서비스 전역 장애"로 전이된다. (3) 과거에 한 번 발생한 lock-경합 quirk 를 문서화하면서 "재발 방지(가드)"를 즉시 구현하지 않고 후속 과제로 미룬 경우, 그 gap 은 리스트에만 남고 실제로 재발할 때까지 잊혀지기 쉽다 — quirk 기록에 "임시 수동 대응"만 있고 "구조적 방지"가 없으면 그 자체가 미완료 상태임을 명시(예: TODO 항목화)해야 한다.
- Applies to: 모든 cron/timer 기반 반복 스크립트(`crontab -l`/`sudo crontab -l` 로 열거되는 전체), 특히 공유 커넥션 풀(pgbouncer 등)에 접근하는 백그라운드 배치 작업.
- Verified: true (근본원인 라이브 lock-wait 체인 확인 + stray 프로세스 kill 로 즉시 해소 확인 + flock 가드 추가 후 이중 기동 재현 테스트로 재발 차단 확인).

### LRN-20260713-0001 — 웹/UI 기능 완료 보고가 "코드 병합"·"백엔드 통과"에 머물면, 배포 전 사용자 테스트·워커 미반영·client-only 결함을 놓친다
- Source: feature-0003 attach-user-version (사용자 재업로드 첨부 버전 관리) 배포 후 사용자 버그 리포트 조사 (2026-07-13)
- Mistake: 세 겹의 마찰이 겹쳤다. (1) **merge ≠ 배포 완료** — 사용자가 기능을 테스트했으나 그 시각(13:52 KST)이 배포(~15:00 KST)보다 ~1시간 앞서 구코드가 서빙 중이었다(DB CreatedAt 타임스탬프로 확정). (2) **워커 미반영** — 그 기능의 "assistant 변경점 인지" 로직은 `agent_core._build_attachment_context_section`(ask-worker 거주)인데, `deploy-web.sh` 는 web(web-a/web-b)만 재배포하므로 web 배포만으론 반영되지 않는다(deploy-web 의 `worker GIT_COMMIT != web` WARN 을 보고서야 ask-worker 를 별도 재빌드). (3) **백엔드만 검증** — 완료 검증(PB-0008)을 `fetch(FormData)` 백엔드 직접 호출로만 수행해, 사용자가 실제 쓰는 `_uploadComposerAttachment`(ES-module scope, 클라이언트 해시 dedup) 경로를 타지 않아 client-only 결함을 놓칠 뻔했다.
- Correct approach: 배포 검증 체크리스트를 프로세스로 상시화 — ① 배포 완료(양 replica 대상 SHA + soak) 전에는 "사용자 테스트 가능"으로 알리지 않는다 ② 변경이 워커 코드(`agent_core`·워커가 쓰는 `modules`/`shared`)에 닿으면 그 배포에서 워커를 즉시 재빌드(`build <worker> && up -d --no-deps <worker>`) ③ 정적 자산 `?v=` 스탬프 변경 확인 + 사용자 하드 리프레시 안내 ④ 백엔드 API 뿐 아니라 실 사용자 경로(UI)를 라이브 배포본에서 PB-0008 검증 ⑤ 위 통과 후에만 완료 보고. 정본 = feature-0014 RUNBOOK.md §10, `deploy-web.sh post_deploy_checklist` 가 매 배포 자동 출력.
- Verified: true (근본원인 DB 타임스탬프 확정 + 배포 후 라이브 재검증 490→491 체인·finder 정상; 체크리스트 상시화 구현).

### LRN-20260703-0001 — metric 이 기록되는 코드 경로를 "중앙 helper 가 있는 모듈"에서만 grep 하면 실제 라이브 경로를 놓친다
- Source: TASK-20260703-aiops-ttft-latency (AI 운영 현황 지연 p95 재정의)
- Mistake: "어느 경로가 `latency_ms` 를 기록하나" 를 `llm.py` 안에서만 grep 해 `_openai_chat_completion_with_deadline` 를 유일 계측점으로 단정했다. 그러나 이 중앙 래퍼의 유일 호출자 `llm_plan` 은 **호출자가 0인 죽은 코드**였고, 실제 메인 에이전트 추론(`task='agent'`)은 `agent_core._call_llm` 이 래퍼를 우회해 직접 기록한다(TASK-0163 RC1 이 이미 문서화). 잘못된 함수(죽은 코드)를 계측·스트리밍 전환하고 KPI 를 그 컬럼으로 돌려, 배포됐다면 패널이 영구 공백 + 작동하던 지표 폐기(순 회귀)될 뻔했다. 적대 리뷰 패널(2렌즈 독립)이 커밋 전 BLOCKING 으로 적발.
- Correct approach: metric 기록 경로를 찾을 때는 (1) **레포 전역**(`agent_core.py` 포함)에서 `_record_llm_usage`/기록 함수 호출부를 grep, (2) 각 후보 함수의 **호출자 존재를 grep 으로 확인**(dead code 배제), (3) 정책/이력 문서(TASK.md·REPORT.md)에 "이 경로가 중앙 래퍼를 우회한다" 류 단서가 있는지 교차확인. 단일 모듈 grep 으로 계측점을 단정하지 않는다.
- Verified: true (적대 패널 CONFIRMED + `_call_llm` 단일 호출자 재확인).

### LRN-20260415-0001 — Web UI 카드 적층 구조는 항상 외부 스크롤을 유발한다
- Source: feature-0003 UI 개편 작업 (2026-04-15)
- Mistake: `surface-card` 요소를 세로로 쌓으면 콘텐츠 총 높이 > 100vh가 되어 페이지 전체 스크롤이 발생한다. 이는 AI 채팅 앱에서 치명적인 UX 결함이다.
- Correct approach: `app-shell`을 `100vh grid`로 고정하고, 스크롤은 메시지 목록(`.messages { flex:1; overflow-y:auto }`) 영역에만 허용한다. 나머지 영역(topbar, sidebar, composer)은 고정 높이/flex-shrink:0으로 처리한다.

### LRN-20260623-0001 — fingerprint 알고리즘을 바꾸면(casefold 등) 반드시 fp backfill 을 동반해야 — 안 그러면 전수 통찰 재생성 폭주
- Source: TASK-0305 RC2 (insight fingerprint casefold) 라이브 배포 (2026-06-23)
- verified: true
- Mistake: insight-worker 의 schema/table fingerprint 해시 함수(`_compute_schema_fingerprint`/`_compute_table_fingerprints_batch`)에 casefold 정규화를 추가해 배포했더니, **기존에 저장된 8,833개 fingerprint 가 전부 새 해시와 불일치** → 도달가능 datasource 의 모든 테이블이 `reason=fingerprint_changed` 로 판정돼 LLM 재생성(cutover)이 시작됐다. 도달가능분만 ~1,979 테이블 × ~수 시간 + ~2,000 LLM 호출 + 그동안 cutover cycle 이 길어(>180s heartbeat 임계) 워커 health=unhealthy. 코드는 정확했지만 데이터 마이그레이션을 빠뜨린 것이 incident 를 유발.
- Correct approach: fingerprint(또는 해시 키) 계산식을 바꾸는 변경은 **반드시 1회성 backfill 을 동반**한다 — 기존 artifact 는 그대로 두고, 새 알고리즘으로 fingerprint 만 재계산해 KV(`schema_fp:*`/`table_fp:*`)에 덮어쓰면 워커가 "unchanged" 로 skip 해 재생성이 0 이 된다. backfill 은 워커의 **동일 함수**(`_compute_*_fingerprint` + `ds_fact_key`/`ds_object_suffix` + `_save_fingerprint`)와 동일 datasource 컨텍스트(`set_active_datasource`/`set_active_database`)로 작성해야 키·값이 정확히 일치한다(샘플 stored==recomputed 검증 필수). 검증법: 배포 후 `tables_generated` 가 급증하면 cutover 발생 신호 — 즉시 backfill. 도달불가 datasource 는 backfill 대상 아님(어차피 재생성 안 됨).
- Trade-off: backfill 의 downside 는 낮다(키가 틀리면 무효과일 뿐 무해, 라이브 워커와 병행해도 같은 값 저장이라 수렴). casefold 자체의 benefit(log_v2 같은 케이스 진동 churn ~132s/일 제거)은 작으므로, 기존 fingerprint 가 대량(수천)인 환경에선 "casefold + backfill" 을 한 세트로 계획해야 비용 역전이 안 난다.

### LRN-20260623-0003 — 런타임 부트스트랩(_ensure_pg_schema)과 alembic 이 스키마를 이중 생성하면 split-brain — merge 된 마이그가 silent 미적용되고 긴 revision id 는 기록조차 안 됨
- Source: TASK-0306 (insight 내부 진단 중 alembic split-brain 발견) (2026-06-23)
- verified: true
- Mistake: 본 프로젝트는 PG 스키마를 **두 경로**로 만든다 — (1) `modules/memory.py:_ensure_pg_schema` 가 부트 시 `agent_kb_schema.sql` 을 적용, (2) `bin/alembic-migrate.sh` 가 alembic 마이그를 적용. 둘이 어긋나면 `alembic_version` 이 코드 head 보다 뒤처진 split-brain 이 된다. 실측: live `alembic_version=0012` 인데 코드 head=0015. 부트스트랩이 0014/0015 의 **테이블 shape 는 만들었지만**(sample_queries 등), 0013 의 `kb_glossary`/`enum_dictionary` 는 schema.sql 에 없어 **안 만들어짐** → merge 된 ITEM-10 용어/ENUM 기능이 `agent_core` 의 `except Exception` 에 삼켜져 **로그 한 줄 없이 silent dead**. 게다가 `alembic_version.version_num VARCHAR(32)` 인데 revision id `0015_sample_queries_embed_dim_1024`(34자)가 초과 → stamp/upgrade 시 'value too long' 으로 **기록 자체가 불가**(0013=32·0014=28 은 우연히 맞아 가려져 있었음).
- Correct approach: (1) **마이그 적용을 배포 파이프라인의 명시 단계로** — 부트스트랩이 스키마를 만들더라도 `bin/alembic-migrate.sh upgrade`(또는 stamp)를 배포마다 실행해 `alembic_version` 을 head 와 정합. (2) split-brain 해소는 **upgrade head 를 무턱대고 돌리지 말고**(파괴적 마이그가 섞일 수 있음 — 0015 가 무조건 DROP+ADD 였음) 누락분만 타깃 적용(`alembic upgrade <prev>:<rev>`) 후 기존 shape 분은 `stamp` 로 정합. (3) **revision id 길이 ≤ alembic_version 컬럼폭**(기본 32) 유지하거나 컬럼을 넓혀라(본 cycle 에서 128 로 확장 + alembic-migrate.sh CREATE 도 128 로 수정). (4) 기능 호출부의 광범위 `except Exception` 은 **로깅을 동반**해 테이블 부재 같은 환경 결함이 silent dead 되지 않게. (5) 정본 schema.sql 과 alembic 마이그의 객체/차원이 일치하는지 주기 점검(`bin/kb-schema-compare.sh`).
- Applies to: 부트스트랩 SQL + alembic 을 병용하는 모든 스키마 관리. 특히 새 테이블을 추가하는 마이그는 schema.sql 정본에도 반영하지 않으면 fresh-install 과 alembic 경로가 갈린다.

### LRN-20260729T091700-ai-root-ui-copy-bloat — 기능을 만들면 그 설명을 UI 안내에 적고 싶어진다 — 화면이 이미 말하는 것을 글로 반복하면 매 방문마다 읽히는 벽이 된다
- Source: 사용자 지적 (2026-07-29, 3회 누적) — "장황하고 현학적이며 지루한 설명문이 UI 에 추가되는 현상이 프로젝트 개발 중 지속적으로 확인되고 있습니다" / 직전 사례 CHG-20260729-0007 (feature-0021 추론 탭 안내 260자 → 57자)
- verified: true
- Mistake: 새 기능을 붙이면서 **구현 계약을 UI 안내 문단에 옮겨 적는다.** feature-0021 회차 원장 cycle 에서 안내가 이렇게 자랐다 — "대화 단위로 묶여 있고(최근 대화 순), 대화를 펼치면 그 안의 리뷰가 진행 순서대로, 리뷰를 펼치면 자가검증·재검증 회차 단계 전부가 순서대로 나타납니다 — 각 항목은 접기/펼치기 됩니다. … 운영 값은 설정 > AI 자가 리뷰, assistant 작동 지침·스킬은 설정 > 프롬프트에서 확인합니다." 3줄(약 260자) 전부가 **캐럿·배치·좌측 메뉴가 이미 보여주는 것**이다. 사용자 표현: "사용자에게 의미없는 정보가 나열되었습니다."
- 왜 반복되나 (근본 3축):
  1. **설명 대상이 사용자의 필요가 아니라 구현자의 지식이다.** 방금 정렬 계약·상한·폴백을 설계한 상태라 "알려주고 싶은 것"이 많다. 그 목록은 사용자가 그 화면에서 하려는 일과 무관하다.
  2. **문서 문장이 그대로 옮겨온다.** `FUNCTION.md`·PR 본문에 쓴 정확한 계약 문장을 UI 로 복사하면 문서 톤(정합성·완전성)이 따라와, 안내가 계약서가 된다.
  3. **정확성 게이트는 있는데 분량 게이트가 없다.** 안내는 diff 가 작고 "틀린 말"이 아니라 리뷰(단위 테스트·codex·verify-completion)를 전부 통과한다. 아무도 "이 문장이 없으면 뭘 못 하나"를 묻지 않는다.
- Correct approach — **UI 안내에 넣지 않는 4종**:
  ① 화면이 이미 보여주는 조작법(펼치기/접기/정렬/클릭/스크롤) ② 다른 화면 경로(`설정 > …` — 좌측 메뉴가 담당) ③ 내부 구조·계약(정렬 키·상한·폴백·스키마) ④ 설계 정당화("왜 이렇게 만들었는가" — REVIEW.md 가 정본).
  **넣는 것은 둘뿐**: (a) 이 화면이 무엇인지 **1문장**, (b) 비가역·위험·비용이 걸린 행동의 경고. 상세 계약은 `FUNCTION.md` 가 정본이고, 그 수준을 원하는 운영자는 이미 찾아갈 곳이 있다.
- 분량 기준(실측 근거): 섹션 안내 **1문장 ~60자**(추론 탭 교정본 57자). 설정 항목 hint 는 "값의 의미 + 잘못 두면 생기는 일"까지 — 모델·주기·병렬도처럼 오설정 비용이 큰 항목만 2문장 허용.
- 현행 잔여 (지시 시 정리 대상, §8.1 제안 기록): `admin.html` 설정 패널 hint 4건이 임계 초과 — 모델 예산 **335자**, 워커 병렬도 **224자**, 자가 리뷰 **168자**, 작동 지침 **141자**. 앞의 둘은 오설정 비용이 커 일부 유지 근거가 있으나 현재 분량은 과하다.
- How to apply: UI 문자열을 **추가·수정하는 diff 마다** 한 번 자문한다 — *"이 문장이 없으면 사용자가 무엇을 못 하는가?"* 답이 "없음"이면 지운다. 기능 cycle 에서 UI 카피가 늘어났다면 그 자체를 리뷰 항목으로 올린다(정확한 문장도 분량으로 실패할 수 있다). 새 구조를 설명하고 싶으면 UI 가 아니라 `FUNCTION.md` 에 쓴다.

## Category: pattern

### LRN-20260707-0001 — "무중단 안전망" 폴백 모델이 정본보다 컨텍스트가 작으면 대화를 유지가 아니라 *조용히 파괴*한다 — 라우팅 폴백은 능력 등가여야 하거나 깨끗이 실패해야
- Source: conversation_audit FR-edge-fallback-conversation-context-loss (conv …9e0883bb, 2026-07-07)
- Pattern: 가용성을 위해 붙인 LLM 폴백(2026-07-04 interactive-split 의 "두 계정 완전 장애 시 gemma 로 대화 무중단")이 **정본 모델과 컨텍스트 창이 크게 다르면** 오히려 최악의 UX 를 만든다. 실측: 대화가 두 claude 계정 429(rate-limit 버스트) 시 로컬 `gemma4:e2b`(ctx **4096**)로 silent 강등됐고, ~30K 토큰 대화 히스토리가 프롬프트에서 통째로 잘려(llm_usage.prompt_tokens 가 정본 29K → 폴백 3턴 모두 정확히 4096) assistant 가 **직전 자기 답변조차 모른 채** 무관한 일반론을 자신 있게 답하고 "기억한다"고 부인했다. 사용자는 이를 제품 버그로 오인하고 명시 불만("맥락을 잃어버렸나요?") + 신뢰 상실. "무중단"이 아니라 "조용한 파탄"이었다.
- 교훈: (1) **라우팅 폴백은 능력(특히 컨텍스트 창)이 정본과 등가일 때만 사용자 대면 경로에 둔다.** 컨텍스트가 훨씬 작은 모델로의 폴백은 "가용성 유지"가 아니라 "정답처럼 보이는 오답 양산"이다. (2) 등가 폴백이 없으면 **깨끗이 실패**(정직한 재시도 안내)가 silent 강등보다 낫다 — 사용자는 "일시적 한도"는 이해하지만 "AI 가 갑자기 바보가 됨"은 제품 결함으로 귀인한다. (3) 강등이 불가피하면 **반드시 사용자에게 표면화**(어느 경우든 silent 금지). (4) 진단 신호: `llm_usage.resolved_model != 요청 model` + `prompt_tokens` 가 특정 라운드에서 급락(폴백 모델의 고정 ctx) = 컨텍스트 절단 강등의 결정적 지문. 요청 model 만 보면 안 되고 **resolved_model** 을 봐야 한다.
- 봉인 방식: 사용자 대면 대화 답변(task='agent') 전용 edge-free alias 로 라우팅(litellm 체인에서 로컬 모델 도달 불가) + 회귀 가드 테스트로 "대화 기본 모델의 폴백 체인이 anthropic-only" 를 고정(기본 모델·체인 변경 시 자동 적발). 배치/분석 등 비-대화 경로의 gemma 강등은 무영향(alias 분리).
- Applies to: 다중 provider/모델 폴백을 가진 모든 LLM 라우팅. "availability vs quality" 폴백 결정 시 폴백 모델의 컨텍스트/능력이 정본과 등가인지 먼저 확인하고, 아니면 깨끗한 실패 또는 명시 표면화를 기본값으로 한다.
- Verified: true (적대 2렌즈 패널 CONFIRMED + 배포 후 live probe: claude-haiku-4-chat→claude 라우팅 확인, gemma 도달 불가).

### LRN-20260714-0003 — 보안 가드의 read-only allowlist 를 넓힐 때는 "같은 정보 클래스의 형제 표현"을 함께 감사하라 — 한 표현만 풀면 태세 불일치가 같은 마찰로 하루 만에 재발한다
- Source: conversation_audit FR-sysvar-select-denylist-overblock (2026-07-14) — 선행 FR-readonly-query-shapes-overblock(2026-07-13)의 형제-표현 잔재
- Pattern: sql_guard 처럼 "read-only 만 허용" 가드에서 어떤 read-only 표현(예: `SHOW (GLOBAL) VARIABLES/STATUS`)을 사용자 승인하에 allowlist 에 넣으면, **같은 정보를 노출하는 다른 문법 표현**(예: `SELECT @@lower_case_table_names`)이 별도 규칙(여기선 보조 denylist 의 `@@`)으로 여전히 차단된 채 남기 쉽다. 그 결과 `SHOW VARIABLES` 는 되는데 `SELECT @@x` 는 "보안 정책상 차단"되는 **태세 불일치**가 생기고, LLM 이 자연스럽게 고르는 표현이 후자면 어제 고친 것과 **똑같은 마찰**이 하루 만에 재발한다(실측: readonly-shapes 배포 다음날 `denylist match: @@` 차단 1건). 정보노출 관점에선 `SHOW GLOBAL VARIABLES` 가 이미 전체 시스템변수를 덤프하므로 `SELECT @@x`(부분집합)를 막는 건 보안 이득 0·마찰만 유발.
- 교훈: (1) 가드 allowlist 를 넓히는 변경을 할 때, "이 정보/동작을 얻는 **다른 문법 경로**가 무엇이고 그것들도 같은 태세인가"를 한 번에 감사하라 — 한 표현만 풀면 형제 표현이 posture-drift 로 남는다. (2) allowlist 확장의 보안 판단 기준은 "이 표현이 위험한가"가 아니라 **"이미 허용된 표현 대비 노출/동작 델타가 있는가"** — 델타 0 이면 막는 것은 순수 마찰. (3) read-only 정보 노출과 **쓰기/부수효과**는 분리해서 봉인 — `@@` 읽기는 풀되 `SET @@`(쓰기)·`:=`(할당)·shape 게이트(`exp.Set` 거부)는 유지, dialect 별로도 분리(T-SQL `@@` 는 메타 열거 차단 태세라 유지).
- 봉인 방식: MySQL 보조 denylist 에서 `@@` 만 제거(형제 표현 태세 정합) + 쓰기/할당/shape/tsql 불변 회귀 테스트로 고정. 검증: security 적대 서브에이전트 5축(write·노출델타·UNION분기·tsql·난독화) REFUTED + 런타임 가드 실증(`SELECT @@x`=ALLOW·`SET @@`=DENY·tsql `@@`=DENY).
- Applies to: sql_guard·RBAC·allowlist 등 "허용 목록을 승인받아 넓히는" 모든 보안 가드 변경. 한 케이스를 풀면 **같은 능력의 형제 표현/경로**를 동일 커밋에서 감사해 posture-drift 잔재를 남기지 말 것. 신호 검출 측: `denylist match: @@`·`got Union`·`got Show` 처럼 시그니처가 표현별로 갈리면 corroboration 을 표현별 버킷으로 집계해야 형제 잔재를 조기 포착한다.
- Verified: true (코드/테스트/런타임 가드 실증 CONFIRMED; 배포 후 라이브 corroboration `denylist match: @@` distinct_conv 재측정은 다음 audit — 0 유지 시 마찰 소멸 확정).

### LRN-20260714-0004 — LLM 이 "부분 증거(절단 미리보기·차단 응답)를 전수로 단정"하는 환각은 표시 캡의 부작용 — 프롬프트만으로는 안 막히고 구조·피드백·계약 3면을 함께 봉인해야 한다
- Source: conversation_audit FR-partial-evidence-false-verification (conv …e6add7f1 "첨부파일과 실제 DB 비교 검증", 2026-07-14). 사용자 명시 불만 "답변 내 환각이 극심합니다".
- Pattern: 도구 결과를 컨텍스트 보호용으로 **N행 미리보기 절단**하면(여기선 execute_sql 50행), 그 캡은 "표시" 관점에선 옳지만 **분석·대조 과업**에선 모델이 "미열람 행"을 "부재"로 오독한다. 실측(첨부 sha256 대조로 확증): 183행 테이블 목록이 50행에서 잘렸는데 assistant 가 "전수 검증"으로 서술하고 첨부에 **실재하는** `TRUNCATE charactermakinglog`(141행)를 "누락"으로 오진했다. 정정 요청 후에도 61행/50행 절단으로 같은 기전이 반복됐다. 절단 안내가 "CSV 링크 제공" 같은 **표시 지침**뿐이고 "이 목록은 불완전하니 부재를 단정하지 말라"는 **epistemic 정보**를 안 주면, 비결정 LLM 은 계속 미끄러진다.
- 교훈: (1) **부분 증거를 전수로 단정하는 환각은 단일 lever(프롬프트 지시)로 안 막힌다** — 구조(소형 결과는 애초에 절단 없이 char-budget 내 전량 표시)·피드백(절단·차단 응답이 "미열람 행 단정 금지·재조회 유도" 자기교정 정보를 동봉)·계약(SYSTEM_PROMPT 가 부재/전수 단정에 완전 근거를 요구, 불가 시 "미확인" 명시 의무) 3면을 함께 봉인해야 한다. (2) 표시 캡(디스플레이 최적화)과 근거 캡(모델이 결론을 내리는 evidence)은 **다른 관심사** — 컨텍스트 보호용 절단이 근거 캡으로 새면 "적게 보여주기"가 "틀리게 단정하기"로 전이된다. 소형 결과는 목록 대조가 미리보기 안에서 종결되게 하고, 대형만 절단하되 절단은 반드시 epistemic 하게. (3) **"CSV 에 전량 저장됨"은 모델의 근거가 아니다** — 저장 파일은 사용자 다운로드용이라 모델이 읽을 수 없다. "저장했으니 됐다"는 안내는 오히려 모델이 안 본 데이터를 봤다고 착각하게 만든다. (4) 진단 신호: 사용자의 "직접 확인/실제 비교/환각" 명시 + tool 결과의 `행 중 N행만 표시` 절단 마커 + 답변이 그 절단 목록 전체를 "전수"로 서술 = 부분증거 전수단정 지문. ground truth(첨부 원본 sha256)로 대조하면 환각을 결정적으로 확증할 수 있다.
- 봉인 방식: (A) 절단 안내문 epistemic 화(미열람 행 존재/부재/개수 단정 금지·WHERE/집계/NOT IN 재조회 유도·CSV 비가독) (B) `_format_result_sets` char-budget 확장(소형 결과 캡 너머 전량, 광폭/대형은 기존 캡 유지 — 웹 UI step 은 CSV 우선 50행 경로라 무영향) (C) SYSTEM_PROMPT HANDLING RESULTS 4규칙(절단 epistemics·부재/전수 근거 계약·첨부↔DB 양측 조회·서버 옵션 실측). 회귀 테스트로 확장 vs 캡유지·500 상한·legacy 캡·절단 안내·프롬프트 계약 고정.
- Applies to: LLM 에게 도구 결과 미리보기를 잘라 전달하는 모든 경로(SQL 결과·검색 결과·파일 목록·로그 tail 등). 특히 "목록 대조/누락 검증/전/후 비교" 과업에서 절단은 부재 오단정의 직접 입력이 된다. 캡을 둘 땐 반드시 "이건 부분이다"를 모델이 읽을 수 있게 동봉하고, 소형은 애초에 자르지 말 것.
- Verified: true (코드/테스트/런타임 실증 CONFIRMED — ask-worker 배포본 4-lever 로드 실증; 배포 후 라이브 corroboration[절단 노출 대화의 후속 '환각'/'다시 확인' 명시 불만] 재측정은 다음 audit).

### LRN-20260714-0005 — 같은 대화의 서로 다른 근본을 병렬 세션이 각자 고치면, 한 세션의 봉인이 다른 세션의 lever 를 dead code 로 만들 수 있다 — rebase 시 자기 lever 를 재평가해 dead 출하를 피하라(정직)
- Source: conversation_audit FR-partial-evidence-false-verification 의 rebase 재평가 (2026-07-14). 같은 대화 …e6add7f1 를 두 세션이 동시 진단.
- Pattern: 한 라이브 대화가 여러 근본(이 사례: ① 절단 전수단정 ② @@ 옵션 거부)을 동시에 노출하면, 빈번-호출 유지보수 환경에서 **병렬 세션이 각 근본을 다른 friction-id 로 동시에 작업**할 수 있다. 실측: 내 cycle 이 @@ 거부의 L2 교정 힌트(Lever D)를 계획한 사이, 병렬 세션이 sql_guard 에서 MySQL `@@` denylist 를 **아예 제거**(FR-sysvar-select-denylist-overblock)해 `SELECT @@x` 가 통과하게 만들었다. rebase 시점에 내 Lever D 의 "거부 시 힌트" 분기는 **dead 경로**가 됐다(거부가 더는 안 일어남). dead code 를 그대로 출하하면 정직 원칙 위반이자 미래 혼란.
- 교훈: (1) **rebase 후 자기 changeset 의 각 lever 가 여전히 살아있는지 재평가하라** — 병렬로 머지된 관련 작업이 전제(예: "이 입력이 거부된다")를 무너뜨렸으면 그 lever 는 죽는다. base-drift 는 텍스트 충돌만이 아니라 **의미적 전제 충돌**도 만든다. (2) dead 가 된 lever 는 "무해하니 남긴다"가 아니라 **삭제**가 정직 — 안 타는 코드+테스트+docs 는 다음 진단자를 오도한다. 삭제하며 회귀 가드(재도입 방지 테스트)와 사유(왜 dead 인지)를 남긴다. (3) 같은 대화의 형제 근본을 다른 세션이 이미 처리했으면 **그 friction-id 를 cross-ref** 로 명시해 중복·모순을 드러낸다. (4) 이 재평가는 corroboration 재측정만큼 중요한 "매 호출 폐루프"의 일부 — 봉인이 여전히 유효한 문제를 겨냥하는지 확인.
- Applies to: 빈번-호출·병렬 세션 유지보수(conversation_audit·doc_sync·improve_cycle 등)에서 같은 자산(대화·feature)을 여러 세션이 동시에 건드릴 때. cycle-finalize 전 rebase 에서 텍스트 충돌 해소에 그치지 말고 "내 변경의 전제가 아직 성립하나"를 코드로 확인한다.
- Verified: true (병렬 머지 PR #790/#791/#792 확인 + Lever D dead 경로 코드 확인 + 삭제·회귀가드 반영 + 상호 회귀 0 실측).

### LRN-20260714-0001 — 코드 상수 프롬프트의 "행동 계약"은 운영자 DB 프롬프트(global row)가 통째 대체하면 조용히 사라진다 — injection-guard 처럼 compose 시 코드-권위 주입해야 프로덕션에 도달한다
- Source: conversation_audit FR-attachment-update-pasted-not-versioned (2026-07-14, structural 27/34)
- Pattern: 어떤 행동 계약(예: "명시적 갱신요청 → 쿼리 붙여넣기 말고 첨부 새 버전으로 전달")을 **코드 상수 `SYSTEM_PROMPT` 안에만** 넣으면, `compose_system_prompt` 가 운영자의 `websystemprompts` global-scope row 를 **base 로 통째 대체**하는 구조에서 그 지침이 프로덕션 프롬프트에서 약해지거나 사라진다(data/config drift). 실측: attachment-edit 전달 메커니즘·프롬프트 지침이 2026-06-15/16 출하됐는데도 90일간 갱신요청 34대화 중 27(~79%)이 여전히 붙여넣기 — 메커니즘은 있는데 프롬프트가 그 경로로 안 태웠고, 지침이 코드 상수 안이라 운영자 프롬프트 커스터마이즈에 취약했다.
- 교훈: (1) **드리프트되면 안 되는 행동 계약은 base prompt(운영자 대체 가능)에 의존하지 말고, `_INJECTION_GUARD_NOTICE` 처럼 compose 단계에서 base 뒤에 코드가 항상 append** 한다(AUTH-1a 코드 권위선). 이러면 운영자 global row 내용과 무관하게 계약이 effective. (2) 메커니즘 존재 ≠ 사용됨 — 기능을 출하했는데 채택률이 낮으면 "프롬프트가 그 경로로 태우는가"를 **정본 store 집계로 측정**(성공/실패 퍼널)하라. 코드만 보면 "있으니 됐다"고 오판한다. (3) LLM-의존 산출물(파일명 등)의 정합은 프롬프트 지시가 아니라 **코드가 권위적으로 강제**(예: 명명 정규화)해야 drift-proof.
- 봉인 방식: (A2) 강화 지침을 `_ATTACHMENT_DELIVERY_DIRECTIVE` 로 compose parts 에 코드-주입(global row 무관 도달) + (A1) 코드 상수 base 지침도 동반 강화(no-global-row 환경·seed) + (A3) 파일명은 `_next_version_filename` 이 `<stem>_v<n>.<src_ext>` 로 코드-권위 결정(LLM 명명 무관). 검증: 코드/테스트로 "지침 도달·명명 정합" 증명 vs 배포 후 corroboration 재측정으로 "실제 붙여넣기 감소" 는 분리(코드만으로 마찰 소멸 단정 금지).
- Applies to: 프롬프트·가드·라우팅 등 "코드 상수 vs DB 저장 설정" 이 공존하는 모든 경로. 행동 계약을 어디에 두는가(대체 가능 base vs 코드 권위 주입)를 drift 내성 기준으로 결정하라. + conversation_audit 류 채택률 진단은 정본 store 집계 퍼널로.
- Verified: true (적대 3렌즈 패널 — SEC-1 MINOR 봉인·나머지 REFUTED; 배포 후 4서비스 ee4f8de6 런타임 실증. 라이브 대화 붙여넣기 감소는 다음 audit corroboration 재측정 대기 = unverified-live).

### LRN-20260605-0001 — DB cutover 의 read-back 누락은 워커뿐 아니라 "사용자 대면 grounding 경로"까지 조용히 무력화한다
- Source: feature-0002 DB 조회 UX 개선 (TASK-0151, 2026-06-05)
- Pattern: 05-27 MySQL→PG cutover 가 쓰기는 PG 로 옮기고 DROP 까지 했지만, **여러 read 경로가 DROP 된 MySQL 테이블을 `try/except: pass` 로 조회**해 빈 결과를 반환하고 있었다. TASK-0145 는 insight worker 면(livelock)을 고쳤고, TASK-0151 은 **사용자 질의의 스키마 grounding(`_load_schema_list`/`_load_relevant_table_insights` → "KNOWN SCHEMAS" 주입)** 면을 고쳤다. 둘 다 같은 원인의 다른 얼굴이다.
- 교훈: (1) **대규모 cutover 후에는 "쓰기 복구"만이 아니라 모든 read-back/조회 callsite 를 grep 으로 전수 점검**해야 한다 — 특히 `except: pass` 로 감싼 raw `AgentMemory*` SQL 은 실패해도 침묵하므로 "동작하는 것처럼" 보인다. (2) **침묵 fallback(빈 결과)이 가장 위험**하다: grounding 이 비면 LLM 이 환각하지만 에러는 안 나서 모니터링에 안 잡힌다. (3) prompt 가 "이 (외부 주입) 섹션을 신뢰하고 검증하지 말라"고 지시할 때, 그 섹션을 채우는 데이터 경로가 죽으면 prompt 의 강한 지시가 환각을 증폭한다 — **데이터 경로와 prompt 의 신뢰 가정은 한 쌍으로 검증**해야 한다.
- 잔존 점검 대상: `kb_retrieval._load_existing_schema_insights`/`_load_existing_table_insight_map` 도 죽은 `AgentMemoryFacts` VIEW 를 조회한다(insight worker dedup 경로 — 현재 사용자 대면 영향은 없으나 동일 버그 인스턴스, 후속 정리 대상).
- Applies to: cutover/마이그레이션 후속 작업 + 외부 컨텍스트 주입에 의존하는 모든 LLM 경로.

### LRN-20260415-0002 — Web UI 설계는 검증된 상용 앱 패턴을 우선 따른다
- Source: feature-0003 UI 개편 작업 (2026-04-15)
- Pattern: 채팅형 AI 도구 UI는 ChatGPT/Claude 검증 패턴인 `[Topbar | Sidebar + Chat Pane]` 2단 고정 레이아웃을 기본으로 한다. 상태 설명, 마케팅 카피, eyebrow 레이블은 기능적으로 필요할 때만 노출한다. 성공 레퍼런스를 먼저 파악하고 따르는 것이 사용자 피드백 반복보다 효율적이다.
- Applies to: feature-0003 이후 신규 Web UI feature 전체.

### LRN-20260415-0007 — UI 개편 시 기존 데이터 필드가 렌더링 경로에서 누락되지 않도록 검증해야 한다
- Source: feature-0003 쿼리 결과셋 복원 작업 (2026-04-15)
- Mistake: App-Shell UI 전면 개편 후 `renderMessageDetails`를 재작성하는 과정에서 `step.result_summary.preview_table`(인라인 쿼리 결과)이 렌더링 경로에서 누락됐다. 백엔드는 이미 `preview_table` 필드를 포함한 정규화된 데이터를 전송하고 있었으나, 프론트엔드에서 그 필드를 참조하지 않아 CSV 링크만 남게 됐다.
- Correct approach: UI 개편 후 `meta.steps`에 어떤 필드들이 있는지 실제 API 응답으로 먼저 확인(`curl /api/history` + `python3 -c` 파이프)하고, 렌더링 함수가 모든 표시 가능 필드를 커버하는지 체크한 뒤 브라우저로 검증한다. execute_sql 결과는 `result_summary.preview_table.{columns, rows, truncated}` → HTML 테이블로 렌더링해야 한다.
- Applies to: feature-0003 이후 `renderMessageDetails` 또는 step 렌더링을 수정하는 모든 작업.

### LRN-20260415-0006 — 드로어 내 정보가 많아지면 탭으로 분리해야 한다
- Source: feature-0003 프로필 드로어 탭 구조화 작업 (2026-04-15)
- Pattern: 드로어(슬라이드 패널)에 섹션을 수직으로 누적하면 스크롤이 길어지고 정보 계층이 불분명해진다. 권한 현황·활동 정보·비밀번호·API 설정처럼 카테고리가 다른 내용은 탭으로 분리한다. 탭 전환은 `data-*` 속성 기반 JS로 처리하고(`.is-active` + `hidden` 클래스 토글), 탭 헤더에는 계정 컨텍스트(아바타·이름)를 고정 노출해 탭 전환 중에도 현재 계정이 명확히 보이게 한다.
- Applies to: feature-0003 이후 드로어 패널이 3개 이상의 이질적 섹션을 포함할 경우 모두 적용.

### LRN-20260415-0005 — 계정별 설정은 탑바가 아닌 프로필 드로어에 배치한다
- Source: feature-0003 API Vault 통합 작업 (2026-04-15)
- Pattern: API Vault처럼 계정 단위로 저장되는 설정을 탑바에 두면 "전역 도구인가 계정 설정인가"가 모호해진다. ChatGPT·Claude 패턴처럼 계정별 설정은 프로필 드로어 안의 탭(API Vault 탭)으로 이동하고, 탑바는 전역 네비게이션(브랜드, 관리 콘솔)만 남긴다. 드로어로 기능이 이전되면 탑바 버튼도 함께 제거한다.
- Applies to: feature-0003 이후 신규 계정별 설정 추가 시 전체 적용.

### LRN-20260415-0004 — 로그아웃/인증 전환 시 열린 UI 상태와 폼 값을 반드시 초기화한다
- Source: feature-0003 로그아웃 버그 수정 (2026-04-15)
- Mistake: 프로필 드로어가 열린 채 로그아웃하면 인증 화면 위에 드로어가 그대로 남아 UI가 깨진다. 회원가입 후 로그아웃하면 다음 로그인 시 회원가입 폼에 이전 입력값이 노출된다.
- Correct approach: 로그아웃 핸들러 최상단에서 `closeProfile()`을 호출하고, 이후 `loginForm.reset()` / `signupForm.reset()` + 오류 메시지 초기화 + 로그인 탭 복귀를 순서대로 실행한다. 인증 상태를 바꾸는 모든 경로(로그아웃, 세션 만료 처리)에 동일 패턴을 적용한다.
- Applies to: feature-0003 이후 인증 상태 전환이 있는 모든 Web UI feature.

### LRN-20260415-0003 — 브라우저 자동화 접근 시 web 컨테이너는 `ignore_https_errors: true` + HTTPS URL 사용
- Source: feature-0003 브라우저 검증 작업 (2026-04-15)
- Quirk: web 컨테이너는 `ENABLE_WEB_TLS=1` 설정으로 HTTPS로 기동된다. browser 컨테이너에서 `http://web:8000`은 빈 응답을 반환한다. `https://web:8000` + `ignore_https_errors: true` 파라미터를 goto에 전달해야 정상 접근된다.
- Applies to: feature-0004-browser-automation을 이용한 모든 Web UI 검증 시나리오.

### LRN-20260414-0001 — GitHub 자동화 계약은 기계 판독 파일로 먼저 고정 (deprecated 2026-05-15, ADR-0018)
- Source: ADR-0017 (superseded by ADR-0018)
- Pattern (당시): 공개 브랜치 규칙, provider 라벨, 상태 라벨, 커밋 형식, required checks가 문서와 워크플로에 중복되면 쉽게 드리프트가 생긴다. `.github/automation-contract.json`을 정본으로 두고, 쉘 스크립트와 `policy-contract`가 이 파일을 읽게 하면 재발을 줄일 수 있다.
- 현재 적용성: 자동화 스택 자체가 폐기되어 본 패턴은 더 이상 유효하지 않다. PR 머지 게이트는 사람 리뷰 + 로컬 `bin/verify-completion.sh` 로 단순화했다.

### LRN-20260409-0001 — 템플릿 v3.0.0 마이그레이션 시 프로젝트 고유 섹션 보존
- Source: commit `d5ce1a2` (feat(project): 템플릿 v3.0.0 마이그레이션)
- Pattern: AGENTS.md를 Part A~G 구조로 재정렬할 때, 본 프로젝트 고유 섹션(**프로젝트 목표**, **연구 기반 방향 전환**, **웹 기준 업계 표준 반영**, **절대 금지 목록**, **Docker Compose 운영 규칙**, **.env 정책**)은 템플릿의 일반 조항을 덮어쓰지 않고 해당 Part에 그대로 배치한다. 템플릿의 섹션 재편을 기계적으로 따르면 프로젝트 고유 지침이 누락된다.
- Applies to: 차후 템플릿 버전 업 시에도 동일 원칙 적용. 프로젝트 고유 조항의 위치는 CODEBASE_MAP.md 또는 TEMPLATE_CHANGELOG.md의 마이그레이션 체크리스트에 기록한다.

### LRN-20260416-0001 — LLM 도구 호출 순서는 TOOL_DEFINITIONS 배열 순서에 영향받는다
- Source: feature-0002 Planner 자율성 개선 작업 (2026-04-16)
- Pattern: 로컬 LLM이 `search_tables` → `describe_table`을 반복하며 `execute_sql`을 늦게 호출하는 문제가 있었다. `TOOL_DEFINITIONS` 배열에서 `execute_sql`을 맨 앞으로 이동하고 각 도구 description에 사용 조건(예: "최후 수단", "오류 시에만")을 명시하자 탐색 단계가 줄어들었다. 휴리스틱(step count 기반 강제)이 아닌 도구 제시 순서와 자연어 지침만으로 LLM 행동을 교정할 수 있다.
- Applies to: feature-0002 agent_core.py + tools.py의 TOOL_DEFINITIONS 및 SYSTEM_PROMPT 수정 시.

### LRN-20260416-0002 — Progress Strip은 `<details>` 드롭다운으로 높이를 고정해야 한다
- Source: feature-0003 Progress Strip 드롭다운 구조화 (2026-04-16)
- Pattern: step이 누적되며 progress-strip 높이가 증가하면 채팅 영역이 점점 좁아진다. `<details>`/`<summary>` 네이티브 드롭다운으로 전환하고, summary에 `n단계 · 최근 작업` 요약을 표시하며, 펼침 영역은 `max-height: 40vh; overflow-y: auto`로 제한하면 채팅 영역을 보호하면서 전체 진행 상황 확인도 가능하다.
- Applies to: feature-0003 progress strip 구조를 수정하는 모든 작업.

### LRN-20260416-0003 — 다중 결과셋은 팝업이 아닌 말풍선 내 Navigator로 격리 탐색한다
- Source: feature-0003 SQL 결과 Navigator 도입 작업 (TASK-0025, 2026-04-16)
- Pattern: execute_sql step이 여러 개일 때 SQL+결과 테이블을 수직 누적하면 말풍선이 과도하게 길어진다. 반대로 별도 팝업(modal)은 레코드 수에 따라 창 크기가 흔들리고 말풍선 컨텍스트에서 벗어난다. 해결책은 말풍선 내에서 단일 패널을 유지하는 Navigator 패턴이다:
  - `◀` / `쿼리 n/N` 인디케이터 / `▶` + `대상: schema.table` 컨텍스트 헤더를 상시 노출
  - 패널을 한번 생성하고 `.is-active` 클래스로 display 토글 (DOM 재생성 없음 → 상태 안정)
  - 컨테이너에 `tabindex="0"` + `←/→/Home/End` 키보드 조작, 조작법은 버튼 `title` 툴팁으로만 노출(화면 내 상시 출력 금지)
  - 말풍선마다 Navigator 인스턴스를 독립 생성(클로저 상태)해 탐색 범위를 격리
  - 대용량 전체 데이터는 `/api/file`로 CSV fetch 후 클라이언트 파싱해 tbody 교체 + `max-height + overflow:auto`로 영역 보호
- Applies to: feature-0003 에서 말풍선 내 여러 결과셋을 다뤄야 하는 모든 UI (SQL 결과 외에도 step 기반 반복 결과 일반에 확장 가능).

### LRN-20260421-0001 — 한 줄 SQL은 표시 전용 포매터로 키워드 경계 줄바꿈을 적용한다
- Source: feature-0003 SQL 수평 확장 방지 작업 (TASK-0026, 2026-04-21)
- Pattern: LLM이 생성하는 SQL은 종종 한 줄로 길게 이어져 `<pre>` 블록이 말풍선을 수평으로 확장시킨다. `overflow-x: auto`를 쓰면 스크롤바가 생기지만 flex/grid `min-width` 계산으로 부모가 확장되는 경우는 방지하지 못한다. 해결책은 표시 전용 포매터 `formatSqlForDisplay()`를 `pre.textContent` 세팅 직전에 적용하는 것이다:
  - 이미 `\n`이 있으면 원형 유지 (LLM이 이미 포맷한 경우)
  - 문자열 리터럴(`'...'`, `"..."`, `` `...` ``)을 placeholder로 치환해 내부 키워드를 보호한 뒤, 주요 키워드(`SELECT`, `FROM`, `WHERE`, `GROUP BY`, `ORDER BY`, `INNER JOIN` 등) 앞 공백을 `\n`으로 교체
  - 복합 키워드(`LEFT JOIN` 등)가 분리되지 않도록 bare `JOIN`은 키워드 목록에서 제외
  - CSS에 `white-space: pre-wrap; word-break: break-word; overflow-wrap: anywhere` + 컨테이너 `min-width: 0`을 함께 적용해 포매터가 못 잡는 초장문 토큰도 wrap
- Applies to: feature-0003 에서 `sql-block` 렌더링을 수정하거나 SQL 표시 로직을 변경하는 모든 작업.

### LRN-20260421-0002 — 많은 권한 항목은 `<details>` collapsible + summary 카운트 배지로 접근성을 회복한다
- Source: feature-0003 RBAC 33-permission UX 개편 (TASK-0027, 2026-04-21)
- Pattern: 권한이 5그룹 33개로 세분화되자 관리 콘솔에서 "계정 1건당 33개 select × 페이지당 10계정 = 330개 select"가 한 화면에 쌓여 사실상 조작 불가능 상태가 됐다. 해결책은 네이티브 `<details>`/`<summary>` 접힘 + summary에 **실시간 카운트 배지** 노출 + 그룹별 **배치 액션 버튼**이다:
  - summary 구조: `그룹명 + 카운트 배지(상속 N · 허용 M · 거부 K 또는 N/M 선택됨)`
  - 기본 접힘, 선택/override가 있는 그룹만 자동 펼침으로 초기 렌더
  - 배치 액션: "모두 허용/거부/상속" 또는 "모두 선택/해제"를 그룹 헤더에 배치해 클릭 1회로 그룹 전체 반영
  - Profile 드로어처럼 "조회 전용" 맥락에서는 그룹별 `<section>` + pill chip 리스트로 충분 (접힘 불필요)
  - `PERMISSION_GROUP_ORDER = ["console", "account", "role", "conversation", "misc"]` 배열을 프론트 상수로 두고, permission 코드의 앞쪽 토큰(`console.manage` → `console`)으로 폴백 분류하면 백엔드 스키마와 독립된다.
- Applies to: feature-0003 이후 항목 수가 10개를 넘는 선택/편집 UI 전반 (권한 외에도 feature flag, 알림 설정, 역할 매핑 등).

### LRN-20260421-0003 — 백그라운드 서비스/숨은 서브시스템은 전용 문서로 분리해 "서비스 오류"로 오해받지 않게 한다
- Source: feature-0002 Insight 시스템 문서화 (TASK-0028, 2026-04-21)
- Pattern: `insight.py` 1400 줄이 넘는 백그라운드 워커가 5 초마다 DB 에 접속하고 자체 로그(`insight_worker.log`)를 쌓았으나, 어느 문서에도 기능 설명이 없어 사용자가 "서비스가 오류를 반복하고 있다"고 오해했다. 이런 숨은 서브시스템은 `FUNCTION.md` 본문에 몇 줄 추가하는 것만으로는 부족하고, **전용 문서 1종**을 아래 구조로 만들어야 한다:
  - 한 줄 요약 + "사용자 영향(왜 이 시스템이 존재하는가)"
  - 아키텍처 ASCII 다이어그램 (컨테이너/루프/저장소 관계)
  - 실행 경로 — 정상 루프 + fallback 경로(워커 부재 시 인라인 스캔처럼)
  - 저장 형식 (테이블/KV 키 패턴 표)
  - 환경변수 레퍼런스 표 (기본값 + 설명)
  - **"오류 같아 보이지만 정상인 신호" 해석 가이드** — `skip_locked`, `fingerprint_skip` 등
  - 헬스 체크 SQL snippet + **실제 런타임 출력을 문서 작성 시점에 캡처해 증빙**으로 삽입
  - 코드 참조표 (파일:줄번호) — 줄번호는 다른 작업자의 리팩터링 후 쉽게 드리프트하므로 함수명을 함께 적고, 문서 갱신 시 `grep`으로 재검증한다.
- Applies to: 향후 숨은 백그라운드 워커/큐/스케줄러/캐시 갱신 로직이 추가되면 동일 구조로 전용 문서를 작성한다. 기존 숨은 로직도 발견 즉시 동일 패턴으로 문서화한다.

### LRN-20260421-0004 — 관리 콘솔 다건 편집은 per-form save 대신 pending + bulk commit 모델이어야 한다
- Source: feature-0003 관리 콘솔 재구조화 (TASK-0029, 2026-04-21)
- Mistake: admin.js 가 각 계정/역할마다 독립된 `<form>` + 개별 "저장" 버튼을 두고, 저장 성공 후 `loadAdminData()` 로 전체 DOM 을 다시 렌더링했다. 결과: 사용자가 3개 계정을 순차 편집 중 한 계정에서 저장을 누르면 나머지 2개 계정의 pending DOM state 가 사라지는 크리티컬 버그. 사용자 테스트에서 "수정한 내용이 사라진다"는 피드백으로 확인됨.
- Correct approach: AWS IAM 콘솔 패턴을 따른다 —
  1. 편집 이벤트(input/change)는 **서버 호출 없이** JS 측 `pending = { accounts: Map<id, patch>, roles: Map<id, patch>, newRoles: Map<tempId, draft> }` 에만 반영.
  2. patch 값이 서버 원본과 동일해지면 pending 에서 auto-drop (noise 방지).
  3. 하단에 sticky commit bar 를 두고 "변경사항 N건 · 취소 / 모두 적용" 노출. `.has-pending` 클래스로 색상 강조(노란/주황).
  4. "모두 적용" 클릭 시에만 전체 pending entry 를 loop 로 PATCH/DELETE/POST 후 1회만 `loadAdminData()`.
  5. detail pane 은 `mergedAccount(id) = server + pending overlay` 로 렌더 — 리스트와 디테일 양쪽에서 pending 표시(`.has-pending` dot)가 일관되게 보이도록.
  6. 리스트 row 체크박스 기반 bulk 작업도 **즉시 API 호출 금지**. 선택된 각 row 에 대해 `setAccountPending(id, patch)` 만 호출 → 사용자가 commit bar 로 확인 후 적용.
  7. `beforeunload` 에서 pending 이 남아 있으면 이탈 경고.
- Verification: admin.js 의 pending 로직을 단순 node 스크립트로 분리해 "3개 계정 각기 다른 필드 편집 → 전부 pending 유지, revert-to-server 시 auto-drop" 시나리오를 assert 로 재현했다(`/tmp/verify_pending_logic.js`). API 레벨에서 partial PATCH(`is_active` 만 / `role_id` 만 / `permission_overrides` 만) 가 모두 200 OK 를 반환하는 것도 확인해 pending 모델이 서버 계약과 일치함을 검증.
- Applies to: 모든 관리/설정 콘솔 UI. "여러 행을 편집 가능한 테이블" UI 는 기본적으로 이 패턴을 적용한다. 단건 편집이거나 저장 후 즉시 새 화면으로 이동하는 경우는 예외.

### LRN-20260421-0005 — 관리 콘솔은 채팅 app-shell 과 동일한 전폭 grid 레이아웃을 써서 일관성을 유지한다
- Source: feature-0003 관리 콘솔 재구조화 (TASK-0029, 2026-04-21)
- Pattern: admin 페이지에 `max-width: 1100px; margin: 0 auto` 를 걸고 3개 surface-card 를 세로로 스택하면, 채팅 "작업 화면"(app-shell 전폭 grid + sidebar + chat pane) 과 톤이 크게 달라 사용자가 "위화감이 든다" 고 느낀다. 또한 좌우 여백이 정보 표현 공간을 낭비한다. 해결: admin 도 `body.admin-shell { display:grid; grid-template-rows: var(--topbar-h) 1fr auto; height:100vh }` + `.admin-body { grid-template-columns: 220px 1fr }` 구조로 전환해 topbar/sidebar/workspace/commit-bar 4 영역을 채팅 UI 와 동일한 축으로 배치한다. 탭 네비는 sidebar 에 둬 대시보드/계정/역할 영역을 독립 pane(`display:none` 토글)으로 분리하면 "한 화면에 세 섹션이 섞여 검색 범위가 모호해진다"는 피드백도 동시에 해소된다.
- Applies to: feature-0003 이후 모든 internal 관리/설정 UI. 별도 서브 앱(/admin, /settings 등)이라도 동일한 app-shell 골격을 재사용해 시각적 일관성을 유지한다.

### LRN-20260421-0006 — 확장 가능한 본문을 포함한 채팅 말풍선은 고정 폭 + 내부 max-height + scroll anchor 3 종 세트로 설계한다
- Source: feature-0003 말풍선 스크롤 드리프트 이슈 (TASK-0030, 2026-04-21)
- Mistake: assistant 말풍선 안에 `<details>` / SQL / 결과 테이블을 담으면서 `.message { max-width: 82% }` 와 `.message-details-body { /* no cap */ }` 만 적용했더니, 펼침/Navigator 이동/쿼리 결과셋 행 수에 따라 말풍선 크기와 채팅 로그 스크롤 위치가 비결정적으로 튀어 사용자가 방금 보던 문장을 놓치는 UX 버그가 발생했다.
- Correct approach: "확장 가능한 본문을 가진 채팅 말풍선" 은 세 장치를 동시에 적용한다 —
  1. **역할별 max-width 분기** — user 는 좁은 우측 정렬(`max-width: 72%`), assistant 는 `max-width: none` + `align-self: stretch` + `margin-right: 48px` 로 채팅 pane 전폭에 가깝게 고정. 우측 여백(≈48px) 만으로 시각 구분.
  2. **내부 본문 cap** — `.message-details-body { max-height: min(60vh, 520px); overflow: auto; overscroll-behavior: contain; }` 로 펼친 콘텐츠를 말풍선 내부에서 소비. 내부 요소(SQL block, 결과 테이블)에도 2차 cap(`.sql-block { max-height: 240px; overflow: auto }`, `.result-table-wrap { max-height: 320px; overflow: auto }`) 을 걸어 이중 안전망.
  3. **Scroll anchor** — `<summary>` 클릭 핸들러에서 스크롤 컨테이너 기준 `getBoundingClientRect().top` 을 측정 → `requestAnimationFrame` 2 프레임 후 delta 만큼 `scrollContainer.scrollTop` 을 보정. `<details>` 네이티브 동작만으로는 부족하고, 내부 cap + anchor 가 모두 있어야 "펼쳐도 위에 있는 메시지가 튀지 않는다".
- Verification: 브라우저 자동화에서 펼침 전/후 `summary.getBoundingClientRect().top` 동일(delta=0), Navigator 이동 시 `bubble.getBoundingClientRect().width` 불변(705→705), `message-details-body` 의 실계산 max-height 가 432px(60vh @ 720px viewport) 로 확인됨.
- Applies to: 챗봇/로그 뷰어/이벤트 피드 등 "고정 목록 내부에 확장 가능한 row" 가 있는 모든 UI. `<details>` 만으로 충분해 보여도 내부 콘텐츠가 동적이면 반드시 cap + anchor 를 동반한다.

### LRN-20260421-0007 — 마스터-디테일 관리 UI 는 "외부 스크롤 금지 + 컬럼별 내부 스크롤 + 하단 요소 sticky/flex-shrink:0" 로 구성한다
- Source: feature-0003 관리 콘솔 스크롤 정리 (TASK-0031, 2026-04-21)
- Mistake: admin 페이지에 `.admin-workspace { overflow-y: auto }` 를 걸고 양쪽 컬럼을 `align-items: start` 로 둔 채 `.admin-list { max-height: calc(100vh - 320px) }` 하드코딩 cap 만 넣었다. 디테일 pane 이 커지면 workspace 전체가 스크롤되면서 리스트 컬럼의 페이지네이션이 뷰포트 밖으로 밀려 "버튼이 없어진 것처럼" 보이는 UX 버그가 발생.
- Correct approach: 마스터-디테일 관리 UI 는 **외부(페이지 전체) 스크롤을 발생시키지 않는다**. 대신 —
  1. 최상위 shell 은 `height: 100vh; overflow: hidden` + `display: grid; grid-template-rows: topbar 1fr auto` (하단 commit bar 고정).
  2. workspace 는 `overflow: hidden; display: flex; flex-direction: column; min-height: 0` — 자체 스크롤 금지, 자식이 남은 공간을 채우게 위임.
  3. 활성 pane 은 `flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column`. head 영역은 `flex-shrink: 0`.
  4. list-detail 컨테이너는 `flex: 1 1 auto; min-height: 0; align-items: stretch`. 두 컬럼은 각각 `min-height: 0` 을 받아 자체 내부 스크롤을 가진다.
  5. **리스트 컬럼** 내부 수직 흐름: toolbar(shrink 0) + list-head(shrink 0) + `.admin-list`(`flex: 1; min-height: 0; overflow-y: auto`) + 페이지네이션/일괄 액션(`flex-shrink: 0`). 하드코딩 `max-height: calc(100vh - Xpx)` 는 제거 — 부모 flex 레이아웃이 자동 계산한다.
  6. **디테일 컬럼** 은 `overflow-y: auto` 로 내부 스크롤. 저장/삭제 같은 마지막 액션 영역은 **`position: sticky; bottom: 0; background: surface; border-top`** 로 디테일 길이와 무관하게 상시 하단 노출.
  7. 액션 영역의 sticky 가 detail-col padding 과 충돌하면 `margin: 0 -padX -padY` + `padding: padY padX` 로 padding 을 상쇄해 전폭 바로 만든다.
- Verification: 브라우저 자동화로 `document.documentElement.scrollHeight - clientHeight == 0`(외부 스크롤 없음), `detail-col.scrollHeight - clientHeight > 0`(내부 스크롤 활성), 양 컬럼 끝까지 scrollTop 을 밀어도 `.admin-detail-actions.getBoundingClientRect().bottom <= window.innerHeight` 가 유지되는 것을 확인.
- Applies to: 마스터-디테일/리스트-폼/설정 패널 등 "좌측 리스트 + 우측 편집" 레이아웃 전반. Admin · 프로필 · API Vault · 알림 설정 등 향후 유사 화면에 동일 패턴을 재사용한다.

### LRN-20260421-0008 — 권한으로 막힌 버튼은 숨기지 말고 "필요 권한 코드 + 서술"을 안내하는 blocked 상태로 노출한다
- Source: feature-0003 권한 안내 UX (TASK-0032, 2026-04-21)
- Mistake: RBAC 권한 확인이 실패하면 버튼을 `hidden` 토글로 DOM 에서 감추거나 핸들러 초입 `if (!can(X)) return;` 으로 **소리 없이 무시**했다. 동작이 안 보이거나 클릭해도 반응이 없어 사용자는 "왜 안 되는지" 를 알 수 없었고, 관리자에게 정확히 어떤 권한을 요청해야 하는지도 전달되지 않았다. 툴팁도 `title = code` 로 영문 id (`conversation.rename.own`) 만 노출해 비개발자가 해석하기 어려웠다.
- Correct approach: 권한 게이트는 **노출 + 명시** 두 축으로 재설계한다 —
  1. **`PERMISSION_DESCRIPTIONS` flat map** 을 단일 정본으로 둬서 모든 권한 코드를 "~할 수 있습니다" 형태의 완결된 한국어 문장으로 매핑한다. `PERMISSION_LABELS` 는 짧은 라벨(그룹 합계 등 좁은 공간용), `PERMISSION_DESCRIPTIONS` 는 서술 문장용으로 역할을 분리한다. 프로필 권한 pill 툴팁은 `` `${describePermission(code)}\n(${code})` `` 2줄 형식으로 노출해 사람이 읽는 문장과 개발자가 검색할 코드를 동시에 보여준다.
  2. **숨김 vs blocked 상태 분리** — 버튼 hidden 토글은 **컨텍스트**(예: 대화가 없음 → 이름변경 의미 없음, run 실행 중 아님 → 취소 의미 없음) 에만 사용한다. 권한 부재는 `markAccessBlocked(btn, action, conv)` 헬퍼가 `aria-disabled="true"` + `.is-access-blocked` (opacity .42, cursor: help, 중립 색) 을 붙이고, 네이티브 `disabled` 는 쓰지 않는다. 네이티브 `disabled` 는 click 이벤트 자체를 차단해 토스트를 띄울 기회를 잃기 때문이다.
  3. **클릭 경로를 유지한 채 토스트로 안내** — 각 액션 핸들러(`createConversation`, `renameCurrentConversation`, `deleteConversation`, `cancelCurrentRun`, `finalizeCurrentRun`, `sendPrompt`) 는 `if (!can(...)) { showPermissionDeniedToast(action); return; }` 로 교체. `showPermissionDeniedToast` 는 `requiredPermissionsFor(action, conversation)` 로 필요한 권한 코드 집합(any/own 양쪽 포함)을 계산해 `"'이름변경' 권한이 없습니다. 필요 권한: \`conversation.rename.own\` — 본인이 소유한 대화의 이름만 변경…"` 처럼 **동작명 + 코드 + 서술** 3종을 한 문장에 담는다.
  4. `any` 권한이 있으면 own 요구 없이 통과하고, own 만 있으면 `isOwnConversation()` 로 소유 여부를 한 번 더 검증하는 **dual-permission 패턴** 을 `requiredPermissionsFor` 에 집중시켜 호출부는 `action` 문자열만 넘긴다.
  5. 접근 차단 상태에서도 버튼 title 에 동일한 필요 권한 문구가 들어가도록 `markAccessBlocked` 에서 title 을 같이 갱신 — hover 와 click 양쪽에서 동일 정보가 나온다.
  6. `renderAccessNotice()` 처럼 페이지 전체가 잠기는 경우에도 안내 메시지에 필요 권한 코드(예: `` `conversation.ask` ``) 와 "관리자에게 권한 부여를 요청하세요." 를 명시해 **어떤 권한을 누구에게 요청해야 하는지** 를 일관된 톤으로 전달한다.
- Verification: 브라우저 자동화로 (a) bootstrap_admin(31 권한) 은 모든 버튼이 활성·토스트 미발생, (b) 신규 pending 계정(5 권한, `conversation.ask`/`.create`/`.delete.any` 없음) 으로 로그인 시 composer 의 "보내기" · "새 대화" 버튼이 `.is-access-blocked` + `aria-disabled` 로 보이고, 클릭 시 필요 권한 코드가 포함된 토스트가 뜨는 것을 확인. 스크린샷 `artifacts/shared/out/browser/task0032_{01,02,03}_*.png`.
- Applies to: RBAC/기능 플래그/구독 제한 등 권한 게이트가 존재하는 모든 UI. "의미 있는 컨텍스트에서 권한만 부족한 버튼" 은 숨기지 말고 blocked 상태로 노출하고, 클릭 경로를 유지해 **필요 권한 코드 + 서술 + 요청 대상(관리자)** 3요소를 토스트/title 로 안내한다. 권한 코드는 사용자 메시지에 코드블록으로 포함해 복사·검색이 가능하게 한다.

### LRN-20260421-0009 — 스크롤 컨테이너 중첩은 "턱턱" 끊김을 만들고, 결과 테이블에는 RowCount + sticky freeze 가 기본값이어야 한다
- Source: feature-0003 결과셋 말풍선 UX 정리 (TASK-0033, 2026-04-21)
- Mistake: TASK-0030 에서 말풍선 내부 스크롤 격리를 목적으로 `.message-details-body { max-height: min(60vh,520px); overflow: auto; overscroll-behavior: contain }` 를 도입했다. 하지만 내부의 `.sql-block`/`.result-table-wrap` 도 각자 `max-height` + `overscroll-behavior: contain` 을 가지고 있었다. 결과: 같은 말풍선 안에 세로 스크롤 컨테이너가 2-3개 겹치고, 마우스 휠이 "누가 휠을 소비할지" 매 프레임 바뀌면서 사용자 입장에서 **"턱턱" 걸리는** 느낌이 났다. 또 결과 테이블에 RowCount(행 번호) 컬럼이 없고 헤더/첫 열 freeze 도 없어 행/열이 많아지면 위치 파악이 불가능했다.
- Correct approach: "말풍선 안의 확장 본문" 은 스크롤을 중첩하지 말고 **단일 바깥 스크롤 + 단일 내부 스크롤** 원칙을 지킨다. 그리고 결과 테이블은 RowCount + freeze 를 기본값으로 탑재한다 —
  1. **말풍선 body cap 제거** — `.message-details-body` 의 `max-height`/`overflow`/`overscroll-behavior`/`padding-right` 를 모두 제거해 본문이 콘텐츠 높이만큼 자연스럽게 자라게 한다. 채팅 로그(`.messages`) 가 유일한 세로 스크롤 컨테이너가 되고, 같은 말풍선 안에 스크롤바 2개가 동시에 뜨는 상황을 **근본 제거**.
  2. **내부 컨테이너의 `overscroll-behavior: contain` 제거** — `contain` 은 자식이 경계에 닿아도 휠을 부모로 전파하지 않는다. 결과 테이블/SQL 블록 내부에서 끝까지 스크롤하면 "막힌 벽" 느낌이 나며, 사용자는 마우스를 이동해 다시 바깥 스크롤을 잡아야 한다. `auto`(기본)로 되돌리면 경계에서 `.messages` 로 자연스럽게 휠이 넘어가 연속된 흐름이 된다. 단, 내부 `max-height` 는 유지 — 결과 테이블이 100행이면 말풍선이 화면을 완전히 차지해 다른 메시지를 못 보게 되기 때문.
  3. **sticky freeze 는 CSS 만으로 완전 구현** — `.result-table { border-collapse: separate; border-spacing: 0 }` + `thead th { position: sticky; top: 0 }` + `th.col-rownum, td.col-rownum { position: sticky; left: 0 }` + 교차점(`thead th.col-rownum { z-index: 3 }`) 으로 Excel 의 "Freeze first row + first column" 을 정확히 재현. `border-collapse: collapse` 에서는 sticky 셀의 border 가 렌더 타이밍에 따라 사라지므로 **`separate` + `box-shadow: inset` 으로 border 대체** 해야 시각적 경계가 유지된다.
  4. **RowCount 는 가상 컬럼으로 클라이언트에서 prepend** — 백엔드 응답(`preview_table.columns/rows`) 스키마는 건드리지 않고 `buildResultTable()` 에서 `<th class="col-rownum">#</th>` + 각 `<tr>` 앞 `<td class="col-rownum">{i+1}</td>` 를 추가. `loadFullCsvIntoTable()` 의 전체 데이터 교체 경로에도 같은 헬퍼(`appendRowNumCell`)를 재사용. meta 의 `"N열"` 카운트는 데이터 컬럼 수로 유지(사용자 기대와 일치).
  5. Sticky 측정 시 **`<tr>` 이 아니라 개별 `<th>` 요소의 BoundingClientRect** 를 확인. 대부분의 브라우저는 `position: sticky` 를 `<tr>` 에서 무시하고 `<th>`/`<td>` 에서만 적용하므로, `thead tr` 의 rect 는 scroll 만큼 이동해 보여도 내부 `th` 들은 실제로는 고정되어 있다. 검증 자동화 작성 시 함정.
- Verification: 기존 33행 × 3열 결과 테이블을 기준으로 (a) `.message-details-body` 의 `scrollHeight === clientHeight` (내부 스크롤 없음), `overflow = visible`, (b) `.result-table-wrap` `overscroll-behavior = auto`, (c) `thead th.position = sticky`, `td.col-rownum position = sticky, left = 0`, corner `z-index = 3`, (d) `wrap.scrollTop = 200` 시 각 `<th>` 개별 `top` 변동 0, (e) `wrap.scrollLeft = 100` (폭 강제 축소) 시 `td.col-rownum` 좌표 불변(`rnStayed: true`) + 데이터 컬럼은 이동(`dataMoved: true`). 스크린샷에서도 `# | hero_index | participation_count` 헤더가 상단에, `#` 열이 좌측에 고정된 채 행 6-19 가 보임.
- Applies to: 채팅/로그/인사이트 패널 등 **확장 가능한 본문을 포함한 카드형 UI**. 본문 스크롤은 컨테이너 계층마다 함부로 중첩하지 말고, 외부 페이지 스크롤을 대체할 만큼 큰 내부 영역에만 제한적으로 둔다. 또 모든 데이터 테이블(쿼리 결과/로그/리스트 등) 은 **기본값으로 행 번호 컬럼 + 헤더/첫 열 freeze** 를 제공한다 — 사용자가 스크롤 중에도 위치를 잃지 않는 것은 옵션이 아니라 기본 요구사항.

### LRN-20260422-0011 — 장시간 작업 폴링은 `setInterval` 고정 주기가 아니라 순번 기반 `setTimeout` 체인 + AbortController + 적응형 주기로 설계한다
- Source: feature-0003 `/api/progress` 폴링 리팩터 (TASK-0036 부수 변경, TASK-0037 사후 리뷰, 2026-04-22)
- Mistake: 초기 구현은 `state.progressPoller = setInterval(pollProgress, 1500)` 고정 주기였다. `/api/ask` 한 턴이 수분까지 걸리는 실사용 (TASK-0034 복잡 QA 테스트에서 평균 ~3분/턴) 에서 다음 4가지 문제가 동시에 발생:
  1. `setInterval` 은 이전 fetch 완료 여부와 무관하게 tick 을 발화 → `/api/progress` in-flight 요청이 누적되어 서버 커넥션/CPU 낭비
  2. `stopProgressPolling()` 이 `clearInterval` 만 호출 → 이미 발행된 fetch 는 응답이 올 때까지 서버/네트워크 리소스를 계속 소비
  3. `document.hidden` 감지 없음 → 탭을 배경화해도 1.5초마다 폴링이 계속되어 배터리/모바일 셀룰러 트래픽을 불필요하게 씀
  4. 서버는 `after_step` 필터를 받지만 `client_run_id` 가 없어서, 새 run 이 시작된 상황을 감지 못해 클라이언트가 "낡은 run 의 after_step" 으로 계속 요청 → 새 run 의 step 0..K 를 놓침
- Correct approach: 장시간 작업(분 단위) 을 백그라운드에서 추적하는 모든 폴링은 다음 5 원칙을 묶어서 적용한다 —
  1. **순번 기반 `setTimeout` 체인** — `state.progressPollSeq: number` + `scheduleProgressPolling(delayMs, seq)` 로 "[fetch] → [응답] → [다음 fetch 1회 예약]" 단일 체인을 유지. `pollProgress(seq)` 진입부에서 `seq !== state.progressPollSeq || state.progressPollInFlight` 이면 즉시 return — in-flight 요청이 1 을 넘는 게 **코드로 불가능** 하게 강제.
  2. **AbortController 로 취소 경로 완비** — 매 poll 마다 `new AbortController()` 를 `state.progressAbortController` 에 저장하고 fetch signal 로 전달. `stopProgressPolling({abort:true})` 이 `controller.abort()` 를 호출해 in-flight HTTP 를 즉시 끊는다. 대화 전환/로그아웃/상세 본문 닫기 등 "이 폴링이 더 이상 의미 없어진" 모든 경로에서 호출.
  3. **요청당 timeout 상한** — `setTimeout(() => controller.abort(), PROGRESS_FETCH_TIMEOUT_MS=4000)` 으로 서버 응답 지연도 상한 설정. `finally` 에서 `clearTimeout(timeoutId)`. 서버가 죽었을 때도 클라이언트가 무한 대기하지 않음.
  4. **적응형 주기 (상태 → 주기)** — `PROGRESS_POLL_ACTIVE_MS=1200`(새 step 스트리밍 중), `PROGRESS_POLL_IDLE_MS=3000`(기본), `PROGRESS_POLL_HIDDEN_MS=10000`(`document.hidden`), `PROGRESS_POLL_ERROR_MS=8000`(에러 후) 4단계. `scheduleProgressPolling(delayMs)` 진입 시 `document.hidden` 이면 `Math.max(delayMs, PROGRESS_POLL_HIDDEN_MS)` 로 하한을 끌어올려 어떤 경로로 짧은 delay 가 들어와도 탭 배경화 시 자동 감속.
  5. **서버측 delta + run_id 검증** — `/api/progress(conversation_id, after_step, client_run_id)` 3 파라미터. 서버는 `client_run_id` 가 없거나 현재 run_id 와 다르면 `after_step=0` 으로 리셋해 **새 run 의 모든 step 을 한 번에 반환** — 클라이언트는 `runId !== state.progressRunId` 를 `applyProgressPayload` 에서 감지해 캐시를 통째로 교체. `_load_steps_for_run(after_step=N)` 은 `WHERE step_index > N` 을 SQL 레이어에서 걸어 DB 필터링 비용을 O(N) → O(returned) 로 축소.
- 에러 백오프 + 포기: `progressErrorCount` 를 각 예외에서 증가시키고 `errorCount < 3` 이면 `PROGRESS_POLL_ERROR_MS=8000` 으로 재시도, 3회 이상은 `shouldSchedule = false` 로 아예 재스케줄링 중단. 네트워크가 완전히 끊긴 상황에서 지속적으로 실패 요청을 때리지 않는다.
- Verification (정적 검증): (a) `grep -c "setInterval" src/static/app.js` = 0 (고정 주기 루프 제거 확인), (b) 5 개 상수 모두 `scheduleProgressPolling`/`pollProgress` 본문에서 실제 참조, (c) 서버 `/api/progress` (app.py:4381~4426) 가 `client_run_id` 를 선언하고 불일치 시 `next_after_step=0` 재설정 조건이 있음 (line 4405-4406), (d) `curl -sk https://127.0.0.1:18080/api/progress?conversation_id=X` HTTP 401 (인증), 로그인 후 HTTP 200 + JSON 스키마 `{steps, status, status_at, step_count, run_id, conversation_id}` 반환.
- Applies to: 장시간(>수초) 비동기 작업을 클라이언트가 실시간 추적해야 하는 모든 웹 UI. `fetch` 폴링 루프를 새로 작성하거나 기존 `setInterval` 패턴을 발견했을 때 전면 적용. 짧은(<1초) 단일 요청에는 과설계이므로 제외.

### LRN-20260422-0012 — SQL 텍스트에서 `schema.table` 을 추출할 때는 반드시 **FROM/JOIN 구간만 slice** 한 뒤 그 안에서만 찾는다
- Source: feature-0003 `_extract_sql_schema_refs` context-aware 수정 (TASK-0040, 2026-04-22)
- Mistake: 기존 구현은 `_SCHEMA_TABLE_REF_RE = r"\`?([A-Za-z_]\w*)\`?\s*\.\s*\`?([A-Za-z_]\w*)\`?"` 단일 regex 로 SQL 전체에서 `x.y` 토큰을 스캔했다. `SELECT bb.BattleType, be.Star FROM dblog.t bb JOIN dblog.u be ON be.a = bb.a WHERE bb.BattleType = 'X'` 같은 SQL 에서 SELECT 절 / WHERE 절 / ON 절의 **alias.column** 이 전부 `schema.table` 후보로 간주되어 schema refs = `{bb, be, dblog}` 가 되고, Product whitelist=`{dbauth,dbgame,dblog}` 에서 `{bb, be}` 가 허용 외로 판정 → 모든 턴이 `BLOCKED_SCHEMAS=bb,be` 로 거부. TASK-0034 Q4 재수행이 0 턴 성공 상태가 됐다.
- Correct approach: SQL 구문상 `schema.table` 이 나올 수 있는 위치는 명확히 **FROM 절**과 **JOIN 절** 뿐이다. 이 두 키워드 뒤 테이블 리스트 구간만 slice 하고, 그 slice 안에서만 `schema.table` 패턴을 추출한다. Slice lookahead 는 다음 절 키워드 `ON`/`WHERE`/`GROUP BY`/`ORDER BY`/`HAVING`/`LIMIT`/`UNION`/또다른 `JOIN`/`FROM`/`;`/`)`/문장 끝 이전으로 끊는다. 2 단계 스캐너:
  ```python
  _TABLE_LIST_RE = re.compile(
      r"\b(?:FROM|JOIN)\b(.*?)"
      r"(?=\bON\b|\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bHAVING\b"
      r"|\bLIMIT\b|\bUNION\b|\bJOIN\b|\bFROM\b|;|\)|$)",
      re.IGNORECASE | re.DOTALL,
  )
  _INNER_REF_RE = re.compile(
      r"`?([A-Za-z_][A-Za-z0-9_]*)`?\s*\.\s*`?([A-Za-z_][A-Za-z0-9_]*)`?",
  )
  ```
  1 단계 (`_TABLE_LIST_RE.finditer`) 로 FROM/JOIN 다음의 테이블 리스트 구간만 뽑고, 2 단계 (`_INNER_REF_RE.finditer`) 로 그 구간 안에서 `schema.table` 을 찾는다. SELECT/WHERE/ON 은 slice 바깥이라 alias.column 이 남더라도 매칭되지 않는다.
- Verification: in-process 15 케이스 (단일 FROM / FROM+WHERE alias.col / FROM+JOIN+alias.col ON / 혼합 schema / 백틱 / subquery / 비허용 schema 차단 / SELECT 절 alias.col 무시 / semicolon terminator / UNION 경계 / whitespace DOTALL / 중복 refs dedup) 전부 expected refs 일치. TASK-0034 Q4(7 턴) + Q5(5 턴) 재수행이 모든 턴 HTTP 200 으로 완료.
- Applies to: SQL 텍스트를 비파서 방식으로 스캔해서 security decision 을 내리는 모든 코드. "regex 는 context-free — 문법상 구분이 필요하면 **구간 slice 후 내부 검색**" 이 기본 설계. 단일 단계 regex 로 SQL 문맥을 흉내 내려 하면 alias/hint/CTE/subquery 중 하나에서 반드시 오탐이 난다. 규모가 더 커지면 `sqlparse` 같은 경량 파서 도입을 검토한다.

### LRN-20260422-0013 — 에이전트 작업자 스레드 lifecycle 은 클라이언트 HTTP 연결과 독립이어야 하고, 별도 read-only 복구 경로를 제공해야 한다
- Source: feature-0003 클라이언트 타임아웃 시 Attach/Resume 구현 (TASK-0041, 2026-04-22)
- Pattern: 장시간 LLM agent 작업(우리 환경에서 `AGENT_TIMEOUT_SEC≈300s` × 여러 스텝, 실측 Q4 turn7=364s / 전체 1171s 등) 은 서버에서 `asyncio.to_thread(...)` 로 백그라운드 스레드에 분리되어 실행된다. 이 스레드는 FastAPI 의 `/api/ask` HTTP 요청 객체와 lifecycle 이 묶여있지 않다 — 클라이언트가 `httpx.ReadTimeout` 으로 끊어지거나 브라우저 탭을 닫거나 nginx/Cloudflare 가 504 를 던져도 **서버는 완료까지 계속 진행한다**. 결과도 `AgentMemoryMessages` + `AgentMemorySteps` + `AgentMemoryKv(last_status, last_status_run_id, last_duration_ms, last_error)` 에 정상 기록된다. 그러나 이 자원을 클라이언트가 회수할 read-only 경로가 없으면 "서버는 답했는데 유저는 못 본" 상태가 된다.
- Design: `/api/ask` (쓰기, 슬롯풀) 와 분리된 2 개의 read-only 엔드포인트로 복구 경로를 완성한다.
  1. **`GET /api/ask_status?conversation_id=CID`** — 1-shot 스냅샷. `AgentMemoryKv` 5 키를 단일 쿼리로 읽어 `{is_processing, status, status_at, run_id, step_count, duration_ms, has_answer, answer_preview}` 를 반환. 비용이 낮아 페이지 로드 시 auto-attach 여부 판단에 부담 없이 호출 가능.
  2. **`GET /api/ask_result?conversation_id=CID&run_id=RID&wait=N`** (N ≤ 60, 내부 0.5s interval) — long-poll. `_ASK_TERMINAL_STATUSES={done, error, canceled}` 도달 시 assistant(content + meta + steps_count) 전문 반환, 시간 초과 시 `{timeout:true, run_id}` 만 반환하고 클라이언트가 바로 재호출해 체인할 수 있다.
  - 두 엔드포인트는 기존 `conversation.read.own/any` 권한만 재사용하고, `/api/ask` 슬롯풀(WEB_PARALLEL_LIMIT=6) 과는 완전히 분리되어 **attach 가 새로운 실행을 시작시키지 않는다**. 이것이 "재진입으로 인한 중복 실행" 을 막는 핵심 속성이다.
- Clients: 이 인프라를 활용하는 3 경로가 있다 —
  1. **브라우저 `sendPrompt()` catch 분기**: `/api/ask` 가 실패(`TypeError: Failed to fetch`, `AbortError`, 504, 502, …) 하고 `is_processing=true` 이면 `[요청 취소 / 즉시 답변 / 계속 기다리기]` 3 버튼 다이얼로그를 노출. 선택에 따라 `/api/cancel`·`/api/finalize` 를 호출한 뒤 `/api/ask_result` long-poll 로 이어받는다.
  2. **브라우저 boot-time auto-attach**: `initializeWorkspace()` 말미에 현재 대화의 `is_processing` 을 확인하고 true 면 다이얼로그 없이 자동 attach — 페이지 새로고침/탭 닫기 이후 재접속 시에도 이전 요청 결과를 자동 수신.
  3. **테스트 러너 `_attach_run`**: `httpx.ReadTimeout` 분기에서 `{"error":"client-read-timeout"}` 실패로 끝내지 않고 `ask_status` → `ask_result` long-poll 로 해당 턴을 정상 기록. turn dict 에 `attached_after_timeout=True` + `attach_verdict` 를 남겨 사후 분석이 가능.
- Anti-pattern (주의): Server-Sent Events / WebSocket 이 "더 현대적" 해 보이지만, 복구 경로의 목적은 "이미 있는 최종 상태를 꺼내오는 것" 이지 real-time stream 이 아니다. 기존 `AgentMemoryKv` + long-poll 2 엔드포인트만으로 완결되므로 프록시·TLS 종단·재접속 관리가 필요한 stream 인프라를 새로 세우지 않는다.
- Verification: Q4 1171s + Q5 251s 모두 HTTP 200 으로 완료 (단일 턴이 960s 를 안 넘어 attach 가 실제 발동되지는 않았지만, 인프라는 in-container 에서 `ask_status`(38ms)/`ask_result` 동작 확인). `/api/ask_status`/`/api/ask_result` 401 응답으로 라우팅 정상, terminal 상태 대화에 대한 스냅샷 38ms, 브라우저 JS `node --check` OK.
- Applies to: 장시간 LLM/batch 작업을 HTTP 로 시작시키는 모든 웹 UI. 작업자 lifecycle 을 HTTP 연결과 독립시키고, 완료된 작업 결과를 read-only 로 **재조회할 수 있는 별도 경로** 를 설계 초기부터 포함시킨다. 기존 진행 상태 저장소 (`AgentMemoryKv`/`Messages`/`Steps`) 가 있다면 그 위에 얇은 엔드포인트만 더 얹는다 — 새 상태 저장소를 만들지 않는 것이 핵심.

### LRN-20260506-0014 — "엔티티 생성 시점" 은 사용자 의도가 확정되는 시점에 lazy 로 — client-side pending state 패턴
- Source: TASK-0048 (REQ-20260506-0001) "새 대화" lazy 화 (2026-05-06)
- Pattern: UI 의 "신규 X 만들기" 버튼이 즉시 backend row 를 발급하면 사용자가 의도를 확정하지 않은 채로 빈 row 가 누적된다. 해법은 (1) 버튼 클릭 시 client-side pending state (`state.pendingNewConversation` + sentinel ID `__pending__`) 만 진입해 사이드바 placeholder 표시, (2) 첫 의미 있는 행위 (메시지 전송 / 폼 제출 / 저장) 시 backend 의 lazy creation path 를 호출, (3) 응답 ID 를 client 가 채택해 placeholder → 실 entity 로 전환. backend 는 기존 lazy creation path (e.g. `/api/ask` 의 `_resolve_conversation_for_account(create_if_missing=True)`) 가 이미 있는 경우가 많아 추가 endpoint 가 불필요하다. 사용자의 직전 의도 (TASK-0048 의 경우 product_mode/product_id) 는 첫 행위의 body 에 hint 로 첨부해 backend 가 cid 발급 직후 적용한다.
- Anti-pattern (주의): "버튼 클릭 = 즉시 backend POST" 모델은 단순하지만 사용자가 실수로 누르거나 마음을 바꾸면 빈 entity 가 남는다. 또한 destructive cleanup (NOT EXISTS subquery 로 빈 row 삭제) 으로 보정하면 §12.1 사람 승인이 필요한 작업으로 격상된다 — 신규 누적 차단을 client-side lazy 로 해결하는 것이 비용/위험이 가장 낮다.
- Trade-off: lazy create 단계 호출이 timeout/네트워크 오류로 실패하면 backend 가 cid 를 만들었는데 client 는 모르는 buried orphan 케이스가 1 발생 가능. 이는 사이드바 새로고침으로 visible 하게 되므로 데이터 유실은 아니지만 사용자 혼란 가능 — 실패 토스트가 "재시도/사이드바 새로고침" 을 명시해 회복 경로를 안내한다.
- Applies to: 모든 "신규 entity 생성" UX. 특히 LLM 요청처럼 시간이 오래 걸리거나 사용자가 의도를 확정 전에 버튼만 눌러볼 가능성이 있는 흐름. PATCH race 가드 같은 mutation 보호 로직과는 자연스럽게 호환된다 (cid 가 발급되기 전엔 PATCH 가 불가하므로).

### LRN-20260623-0002 — insight-worker 의 "DB 파악 진전 없음" 은 권한(GRANT)보다 네트워크 단절이 지배적일 수 있다 — 사유 telemetry 없이 단정 금지
- Source: TASK-0305 진단 + RC5 라이브 배포 (2026-06-23)
- verified: true
- Pattern: insight-worker 가 등록 datasource 다수를 스캔 못 해 `db_failed` 가 크고 status=degraded 일 때, 코드 주석/직관은 "RO 로그인 per-DB GRANT 누락(perm)" 을 가장 흔한 원인으로 가리킨다(실제로 `bin/datasource-mssql-ro-bootstrap*.sql` 힌트도 그렇다). 그러나 라이브 검증 결과 이 배포에서는 **실패의 100%가 `circuit_open`/`timeout`(네트워크 도달 불가)이고 perm 은 0** 이었다(kr-apne2 지역·내부 QA 망 datasource 가 며칠째 down). GRANT 는 단 하나도 못 고치고, timeout 서버엔 접속이 안 돼 GRANT 실행조차 불가능하다.
- 진단 원칙: db_failed 가 크면 **먼저 사유 분포를 본다** — RC5 가 cycle summary 에 `db_failed_perm`/`db_failed_circuit`/`db_failed_other` 를 노출하고, `agent_runtime.datasource_health.last_scan_outcome`(+`last_error_tag`)에 datasource 별 분류가 영속된다. `perm_failed` 만 GRANT 대상, `circuit_open`/`timeout` 은 네트워크/인프라(터널·방화벽·원격 서버 상태)이며 코드·DB 권한으로 해결 불가. 사유 telemetry 가 없던 게 이 오진을 가능케 한 관측성 공백이었고(RC5 가 메움), 배포 즉시 진실이 드러났다.
- Applies to: insight 커버리지/완료율 정체 진단 전반. "스캔 실패 = GRANT 문제" 로 점프하지 말고 perm vs network 를 먼저 가른다.

### LRN-20260707-0001 — 라벨 달린 설정 목록 UI 는 단일용 위젯 재사용 말고 "정렬 grid + 콘솔 commit-bar" 를 쓴다; UI 완성도·완결성은 PB-0008 시각검증이 유일한 게이트다
- Source: feature-0018 runtime-settings 관리 콘솔 설정 (2026-07-06~07, TASK-20260706T094937·audit-hotfix·UX 재설계). 사용자 확인: "가시성이 대폭 개선됨".
- verified: true
- Pattern (권장): N개의 라벨-값 설정 항목을 나열하는 pane 은 **정렬 grid 행 + 카테고리 섹션 + 콘솔 네이티브 commit-bar** 로 만든다. 구체적으로 (a) 각 행 = 2×2 grid (`[라벨+반영배지] / [설명] // [값입력+단위] / [상태·기본값]`) 로 열 정렬(admin-kv/usage-table 계열), (b) canonical `.admin-field` focus-ring 입력·`.admin-badge`·`.admin-detail-section-title` 재사용, (c) 저장은 **행별 버튼이 아니라** 편집→`adminState.pending.*` 예약→하단 "모두 적용" 배치(계정·시스템프롬프트와 동일). 색-only 신호 금지(pending 은 `.admin-pending-dot`+텍스트 병행), 설명은 1줄 ellipsis 대신 2줄 노출.
- Anti-pattern (실수): 다른 맥락용 위젯(`.admin-quota-editor` — LLM 한도 편집기)을 라벨 목록에 재사용했더니 입력창이 라벨과 미정렬로 우상단 부유·설명 잘림(`고품ᯤ`)·행마다 저장/초기화 버튼 난립으로 "세련되지 못한" UI 가 됐다. 위젯은 만들어진 맥락 밖에서 재사용하면 정렬/밀도/상호작용이 깨진다 — 재사용 전 그 위젯의 grid/layout 가정을 확인한다.
- Meta (process): 이 두 결함(그리고 별개의 "unknown audit action" write-path 버그)은 **단위 테스트·API 테스트·§18.8 3-렌즈 적대 코드리뷰가 모두 통과시킨 뒤 PB-0008 실 Windows 브라우저 검증에서야** 드러났다 — (1) audit action 미등록은 라이브 저장 시에만, (2) 시각 완성도는 코드로 판정 불가. **UI 는 "코드리뷰+단위테스트 통과" 로 완료 선언하지 않는다.** 렌더 결과·정렬·상호작용 e2e(편집→pending→적용→DB roundtrip) 는 §15.4.1 PB-0008 이 유일한 완료 게이트. 재설계 자체도 적대 디자인/UX 렌즈가 배포 전 2 MAJOR(반응형 붕괴·no-override 재-핀 트랩)를 잡았다.
- Applies to: 관리 콘솔의 모든 설정/목록 pane 신규·개편. 디자인 착수 전 기존 디자인 토큰/정돈된 패턴을 매핑(subagent)하고, 완료 전 PB-0008 before/after + 상호작용 e2e 로 검증한다.

### LRN-20260714-0001 — 엔진별 카탈로그 스코프 비대칭: MySQL information_schema 는 인스턴스-전역, SQL Server INFORMATION_SCHEMA/sys 는 DB별
- Source: CHG-20260714T161500-mssql-crossdb-structured-discovery (feature-0002-agent-core), conversation_audit FR-mssql-crossdb-structured-discovery
- Pattern: 스키마 탐색·발견 도구를 dialect-agnostic 하게 짤 때, **MySQL 은 `information_schema` 가 인스턴스 전역이라 한 연결에서 모든 DB(스키마)의 객체가 보이지만, SQL Server 는 `INFORMATION_SCHEMA`/`sys` 카탈로그 뷰가 연결된 DB(catalog) 하나만 노출**한다. MySQL 에서 잘 돌던 "연결 기본 DB 에서 카탈로그 조회" 코드를 MSSQL 에 그대로 쓰면, 제품이 여러 DB 를 allowlist 로 가질 때 primary 밖 객체를 **실존하는데도 "없음"으로 반환**해 assistant 가 give-up 한다(라이브 관측: MSSQL 대화 ~38% 가 describe_table 빈-헤더). 봉인은 발견 도구를 **catalog 인지**로 — 다른 허용 DB 를 `[db].sys.*`/`[db].INFORMATION_SCHEMA.*` 3-part 로 조회하고, 키워드 검색은 허용 DB 전체를 훑어 DB-qualified 위치를 반환한다(freeform 3-part 가 이미 도달하는 범위와 동일 — 보안 경계 확장 0).
- Signal 함의(다음 audit 반영): **MSSQL 대화의 `search_tables`/`describe_table` 빈결과는 "객체 없음" 신호가 아니다** — 다른 catalog 미탐색일 수 있다. conversation_audit 의 search_empty/describe-empty corroboration 은 엔진(MSSQL)·다중 DB 여부로 분해해 해석한다.
- 주의(cross-DB 함수 스코프 함정): `OBJECT_DEFINITION(id)` 은 db_id 인자가 없어 **current(pin) DB 컨텍스트**로 평가된다 — 3-part `OBJECT_ID('[db].[s].[n]')` 로 id 를 얻어도 정의는 pin DB 에서 해소돼 NULL/오답. cross-DB 루틴 정의는 `[db].sys.sql_modules WHERE object_id = OBJECT_ID('[db].[s].[n]')`(양쪽 다 [db] id 공간)로 조회한다. 시스템 스키마(sys/guest/db_*) 차단은 cross-DB 경로에서도 명시 재적용해야 한다(primary 경로 게이트를 우회하지 않게).
- Applies to: 멀티-DB datasource 를 지원하는 모든 dialect-aware 스키마 탐색/발견/insight 코드. 신규 엔진 추가 시 "카탈로그 뷰가 인스턴스-전역인가 DB별인가" 를 먼저 확인.

### LRN-20260729-0001 — "고쳤는데 여전히 재현된다"는 재보고는 **배포 시각과 대조한 뒤** 해석한다
- Source: REV-20260729T113000-model-pick-postdeploy (feature-0003-agent-web-ui), conversation_audit FR-model-pick-lost-on-early-cid
- Pattern: 수정·배포 완료를 보고하면 사용자는 **직전에 겪은 경험**을 근거로 답하는 것이 자연스럽다 — 그 경험이 배포 이전이어도 사용자에게는 "방금 일"이다. 실제 사례: 완료 보고 직후 "이전과 동일하게 폴백된다"는 재보고를 받았으나, 재현 대화의 첫 전송은 **10:33:48** 로 배포(web 컨테이너 `StartedAt` **11:08:44**)보다 35분 앞섰고 배포 후 신규 대화·첨부는 **0건**이었다. 재보고를 액면 그대로 받았다면 멀쩡한 봉인을 뜯어 "2차 수정"을 시작했을 것이다.
- 판정 절차(순서 고정): ① 배포 시각을 **컨테이너 `StartedAt` + edge `/healthz` git_commit** 으로 확정 → ② 재현 사건의 시각을 **사용자 진술이 아니라 원장**(첫 user 메시지·첨부·job 행)에서 뽑음 → ③ 배포 이후 구간에 **사용자 조작 흔적이 존재하는지** 확인(신규 대화·첨부 0건이면 신버전 시도 자체가 없었다는 뜻) → ④ 그래도 남으면 그때 코드 재진단.
- 반대 방향도 같이 본다: 같은 구버전 구간의 **성공 사례**를 찾으면 결함 경로가 좁혀진다. 위 사례에서 10:30 대화(첨부 5건)는 정상, 10:33 대화(첨부 1건)만 강등 → "첨부 유무"가 아니라 **선택→첨부 순서**가 분기점임이 라이브에서 재확인됐다(원 진단 강화).
- 안티패턴: 배포 시각 대조 없이 "브라우저 캐시겠지 / 하드 리프레시 하세요"로 넘기는 것 — 사용자에게 재시도 부담만 전가하고 사실은 확정되지 않는다.
- Applies to: 배포 후 사용자 재보고를 받는 모든 cycle(특히 프론트 정적 자산 변경 — 자산이 이미지에 baked 되어 배포 경계가 뚜렷함).

### LRN-20260729-0002 — 라이브 검증을 사용자에게 되던지기 전에, AI 가 배포본에서 직접 끝낼 수 있다(로그인 벽 포함)
- Source: REV-20260729T113000-model-pick-postdeploy / test-runs.d/20260729T1130-model-pick-postdeploy.md
- Pattern: "실제로 그렇게 실행되는지는 사용자가 한 번 해주셔야 안다"는 결론은 대개 **로그인 벽 + 파일 업로드 UI** 때문에 나온다. 둘 다 우회 아닌 정공법으로 넘을 수 있어, 왕복(사용자 재시도 → 보고 → 판정)을 세션 안에서 닫을 수 있다.
- 레시피: ① 접속 — Windows hosts 에 내부 도메인이 없으면 `mysql-ai.company.local` 은 브라우저에서 DNS 미해소이고 WSL IP 직결은 Caddy 가 `Invalid host header` 로 막는다. 사용자가 실제로 쓰는 주소(공인 IP 등)를 확인해 그걸로 간다. ② 로그인 — `.env` 의 `WEB_BOOTSTRAP_ADMIN_USERNAME`/`_PASSWORD` 로 **검증 전용 세션**(사용자 계정 가장 금지). 입력은 native value setter + `input`/`change` dispatch 후 `form.requestSubmit()`. ③ 첨부 — 파일 다이얼로그 없이 페이지 컨텍스트에서 `new File([...])` + `DataTransfer` 로 `input[type=file].files` 를 채우고 `change` dispatch → 실사용 업로드 경로를 그대로 밟는다. ④ 계측 — 화면이 신뢰 못 할 결함(무음 강등류)이면 `window.fetch` wrap 으로 **요청 본문 원문**을, `showToast` wrap 으로 경보 발동 여부를, 전역 `state` 스냅샷으로 단계별 상태를 잡는다. ⑤ 판정 — 최종 근거는 브라우저가 아니라 **DB 원장**(여기선 `llm_usage` + `kv`).
- 핵심 원칙: **결함 전제 상태를 실제로 통과시킨 뒤** 성립을 확인한다. 위 Run 은 모델 선택 직후 `_modelPickedForConvId=""`(결함 전제)를 관측하고 나서 첨부 업로드의 승계를 봤다 — 전제를 우회한 통과는 검증이 아니다.
- Applies to: PB-0008 라이브 검증 전반. 특히 "표시는 맞는데 실행이 다르다" 류(모델·권한·스코프 무음 강등)에서 화면 기반 검증은 원리적으로 무효하므로 요청 본문/원장 채널을 먼저 깐다.

## Category: quirk

### LRN-20260729-0001 — `docker compose run --no-deps` 는 **이미 떠 있는** 운영 스택으로부터 테스트를 격리하지 않는다 (라이브 설정이 테스트 값으로 롤백된 근본 원인)
- Source: TASK-20260729T1412-test-live-db-isolation (사용자 보고: 관리 콘솔 '에이전트/쿼리 실행 타임아웃' 900초가 반복적으로 90초로 롤백)
- Quirk: `--no-deps` 는 의존 서비스를 **기동하지 않을 뿐**, 이미 실행 중인 컨테이너와의 네트워크 연결을 막지 않는다. `make test` 의 agent 서비스는 `networks: [dbnet, ...]` + `env_file: .env/.env.mysql` + `volumes: ../artifacts/shared:/shared` 를 상속하므로, 운영 스택이 상시 떠 있는 개발 머신에서 pytest 가 **라이브 MySQL(`agent_memory`)과 라이브 공유 스냅샷에 그대로 도달**한다. 그 결과 관리 콘솔 런타임 설정 PUT 테스트가 라이브 `WebRuntimeSettings` 를 실제로 덮어썼다(2026-07-13~29, audit `RemoteAddr=testclient` 150건). CI 는 `.env` 도 운영 스택도 없어 통과하므로 **개발 머신에서만 발현**한다.
- 함께 무너진 전제 2가지:
  - "TestClient 를 context manager 없이 만들면 lifespan 미발화 → DB 미접속" — `get_conn` 은 lifespan 이 아니라 **요청 스코프 Depends** 라 매 요청 실행된다. lifespan 회피로는 커넥션이 막히지 않는다.
  - `assert status_code in (200, 500)` 같은 **양쪽 허용 어서션** — "DB 없으면 500, 있으면 200" 의도였지만, 200(실제 저장) 을 통과로 인정하는 순간 오염이 테스트 성공으로 위장된다.
- Mitigation:
  - 차단은 **커넥션 진입점**에 놓는다. `app._connect_memory` 를 autouse fixture 에서 monkeypatch(raise) 하면 `get_conn` DI 경로와 핸들러 내부 직접 호출을 함께 덮고, monkeypatch 특성상 기존 fake-conn 테스트는 그대로 이긴다. `dependency_overrides[get_conn]` 로 덮으면 fake-conn 검증 패턴들이 깨진다(실측).
  - 컨테이너 backstop 은 **포트만 닫는다**(`-e DB_PORT=1`). `DB_HOST` 를 바꾸면 app 이 그것을 datasource SSRF allowlist 에 implicit 등록하므로(TASK-0214) SSRF 가드 테스트가 오염된다. 공유 볼륨 오염은 `RUNTIME_SETTINGS_SNAPSHOT_PATH` 를 컨테이너 임시 경로로 돌려 끊는다.
  - 부작용이 라이브에 남는 테스트는 **상태 diff 로 검증**한다 — 실행 전후 대상 테이블 md5 + audit 신규 건수. 코드 리딩으로는 "안 건드린다" 를 단정할 수 없다.
- 진단 시그니처(재발 시 즉시 판별): `WebAuditEvents` 에서 `RemoteAddr='testclient'` / `UserAgent='testclient'` / `ActorAccountId=1`(conftest 기본 계정). 사람 변경은 실제 IP + 브라우저 UA 로 남으므로 한 눈에 갈린다.


### LRN-20260326-0001 — `repo/.env`의 운영 의미는 원본 `mysql_ai/.env` 기준으로 보존
- Source: ADR-0014
- Quirk: 본 저장소는 `mysql_ai` 원본의 **템플릿 이관 사본**이다. `.env`의 포트·모델·DB 자격증명은 원본과 같아야 하며, 동시 기동은 하지 않는다.
- Mitigation:
  - `.env.example`는 대체 기본값이 아니라 민감값 제거된 샘플로 취급한다.
  - 원본 의미와 다르게 수정할 필요가 생기면 ADR을 거쳐 승격한다.

### LRN-20260326-0002 — 런타임 산출물은 `../../artifacts/`로만 쓴다
- Source: ADR-0013
- Quirk: `shared/`는 공용 **코드** 예약 영역이며 런타임 산출물(로그/세션/데이터 파일)을 여기에 쓰면 Git 추적 대상이 된다.
- Mitigation: 모든 산출물은 `../../artifacts/` 하위로 쓰고, feature 코드는 그 경로만 참조하도록 helper를 경유한다.

### LRN-20260506-0001 — docker compose v5.1.1 + buildx v0.31.1 는 build 후 provenance metadata file 처리에서 EXIT=1 race 가 있다
- Source: TASK-0048 운영 검증 (2026-05-06)
- Quirk: `docker compose build <svc>` 또는 `compose up --build <svc>` 가 `#15 exporting to image` + `#15 naming to docker.io/library/...` 까지 정상 완료한 뒤 `#16 resolving provenance for metadata file` 단계에서 `open /tmp/.tmp-compose-build-metadataFile-<UUID>.json<NNNN>: no such file or directory` 메시지로 EXIT=1 종료한다. image 자체는 새 sha 로 정상 빌드되어 있다 — compose 측이 임시 파일 path 에 random suffix 를 잘못 붙여 stat/open 이 실패하는 회귀로 보인다 (정상이라면 `*.json` 으로 끝나야 하는데 `*.json<NNNN>` 형태). `--provenance=false`, `BUILDX_NO_DEFAULT_ATTESTATIONS=1`, `COMPOSE_BAKE=true/false` 모두 효과 없음 — compose 본체 경로의 race.
- Mitigation: Makefile 에 `dc-build` reusable 타깃 (SERVICE 변수 인자) 을 추가하고, build 명령을 임시 로그에 캡처해서 EXIT≠0 + 로그에 `compose-build-metadataFile` 문자열 포함 시에만 EXIT=0 으로 정규화한다. 그 외 빌드 오류 (Dockerfile syntax, RUN 단계 실패 등) 는 그대로 전파된다. `web` 타깃은 `up -d --build web` 을 `dc-build SERVICE=web` + `up -d --no-build web` 로 분리해 image 를 미리 만들고 컨테이너 교체만 별도 단계로 수행한다.
- Applies to: `make web` 류의 image 빌드 + 기동 명령. 향후 docker compose 또는 buildx 가 fix 되면 가드를 제거할 수 있다 — 가드는 `compose-build-metadataFile` 문자열 매칭으로만 race 를 흡수하므로 race 가 사라지면 자연스럽게 일반 build 경로로 흐른다.
- Verification: `make web` EXIT=0, 로그에 "[make] note: ... provenance metadata file race 우회 ... compose EXIT=1 무시" 출력 후 `Container repo-web-1 Recreate/Recreated/Started` + `Web UI (HTTPS): https://localhost:18080`. `docker exec repo-web-1 grep -n PENDING_CONV_SENTINEL /app/web/static/app.js` 으로 새 코드 반영 확인.

### LRN-20260604-0001 — WSL2 에서 Windows Chrome CDP 는 항상 127.0.0.1 에만 바인딩된다 (relay 필수)
- Source: feature-0008-windows-browser-testing spike (2026-06-04)
- Quirk: WSL 에서 Windows Chrome 을 `--remote-debugging-port=9222 --remote-debugging-address=0.0.0.0` 로 띄워도, 최신 Chrome 은 보안상 `--remote-debugging-address` 를 무시하고 **127.0.0.1 에만 CDP 를 바인딩**한다 (`netsh netstat` 으로 `TCP 127.0.0.1:9222 LISTENING` 확인). NAT 모드 WSL2 는 Windows loopback 에 직접 도달할 수 없어, 단순히 게이트웨이 IP(`172.x.x.1:9222`)로 접속하면 실패한다. 또한 WSL 경로(UNC) cwd 에서 `cmd.exe` 를 호출하면 "UNC 경로는 지원되지 않습니다" 경고를 **stderr** 로 내보내며 cwd 를 C:\Windows 로 바꾼다 — stdout 파싱 시 마지막 유효 라인만 취하고 cwd 를 `/mnt/c` 로 고정해야 안전하다.
- Mitigation: (1) Chrome 은 127.0.0.1 바인딩 그대로 두고, Windows 측 `netsh portproxy` relay 를 **vEthernet(WSL) IP 한정** 으로 세워 `<wsl-host>:9223 → 127.0.0.1:9222` forward (0.0.0.0 금지 — CDP 는 무인증이라 LAN 노출 시 브라우저 탈취). 또는 mirrored networking(`.wslconfig`)으로 loopback 공유 — 인바운드 hole 불요. (2) Playwright `connect_over_cdp(http_endpoint)` 는 endpoint host 로 ws host 를 정규화하므로 relay 경유 가능. `--remote-allow-origins` 는 `*` 대신 loopback+relay 의 구체 origin 으로 scope (DNS rebinding 방어 유지).
- Applies to: WSL2 에서 실제 Windows 브라우저를 CDP 로 구동하는 모든 작업. `bin/win-browser.py` + `bin/WIN-BROWSER-SETUP.md` 참조.

### LRN-20260707-0002 — 24/7 cron 이 "진단용" 라이브 API 호출을 하면, 그 계정을 쓰는 무관한 다른 시스템(세션 윈도우)까지 오염시킬 수 있다
- Source: CHG-20260707-oauth-cron-static-refresh (unit/feature-0007-bedrock-llm-provider)
- Quirk: `refresh-claude-oauth-token.sh` 가 30분마다 Anthropic `/v1/messages` 에
  `max_tokens=1` ping(계정 사용량 소진을 정적 파일 검사로는 못 잡아 도입된 "라이브
  probe")을 보내자, 이 실 API 호출 자체가 claude-corp 계정의 **5시간 rolling 세션
  윈도우**를 `:00`/`:30` 격자에 계속 재고정시켰다. 그 결과 `session-keepalive-cron.sh`
  (07:35/12:35 에 그 날의 첫 앵커 핑을 보내 업무시간과 윈도우를 정렬하려던 스크립트)가
  이미 30분 전에 리셋된 윈도우를 만나 무력화되고, 리셋 시각이 예측 불가하게 드리프트했다.
  두 스크립트는 서로를 모르고 각자 "합리적인" 일을 했을 뿐인데, **같은 계정의 공유
  자원(rate-limit 윈도우)을 통해 간접 결합**돼 있었다.
- Mitigation: "진단/폴백 판단"을 위한 라이브 API 호출을 cron 에 넣기 전에, (1) 이미
  요청 경로에 반응형 fallback(예: litellm `fallbacks:` 체인)이 있는지 먼저 확인한다
  — 있다면 사전 probe 는 대개 **구조적으로 중복**이다(반응형이 진짜 트래픽 기준으로
  더 정확하다). (2) 정 필요하다면 그 API 호출이 계정의 다른 시간 기반 자원(rate-limit
  윈도우, 세션, quota reset 등)에 부수효과를 주지 않는지 점검한다. (3) 관측이 필요하면
  라이브 호출 대신 이미 발생한 트래픽의 로그(`docker compose logs` 등, 로컬 읽기)를
  집계하는 쪽을 우선한다 — 과금·부수효과 없이 같은 가시성을 얻을 수 있는 경우가 많다.
- Applies to: OAuth/API-key 로테이션, health-check, quota-probe 등 "매 N 분 실제
  외부 호출"을 거는 모든 운영 cron — 특히 같은 자격증명을 대화형 세션(Claude Code
  등)과 공유하는 계정.

## Category: preference

### LRN-20260326-0001 — `AGENTS.md`가 정책 정본, `CLAUDE.md`는 참조 shim
- Source: ADR-0002
- Preference: 저장소 수준 AI 정책은 `AGENTS.md` 하나로만 관리한다. `CLAUDE.md`는 호환성을 위해 유지하되 정책 내용을 중복 서술하지 않는다.

### LRN-20260715-0001 — 데이터소스 스키마명은 서버 실제 case 가 정본 — allowlist/프롬프트 소문자 저장이 case-sensitive 백엔드에서 조회를 조용히 0행으로 만든다
- Source: conversation_audit FR-schema-name-case-drift (product 97 "테이블 구조 정합성 검토")
- Category: pattern
- Frame: 스키마/DB/테이블 **식별자 case 는 데이터·설정 계층에서 임의로 정규화(소문자화)하면 안 된다**. case-sensitive 백엔드(MySQL `lower_case_table_names=0`·case-sensitive collation)에서는 저장된 case 가 서버와 1글자라도 다르면 조회가 **에러 아닌 0행**으로 실패해, LLM 이 "대상 없음"으로 오판·give-up 한다(에러가 아니라 조용한 빈결과라 자기교정도 안 됨). (1) 신호 검출: "유효 테이블 조회도 결과셋 empty" + describe/search 빈결과 반복 + INFORMATION_SCHEMA 전체 나열조차 0행 → **연결은 살아있으나(빠른 실행) 스키마명 case/존재 문제**를 의심(연결 끊김·권한과 구분). (2) 이전 casing 대책이 "모델의 소문자화 금지" 프롬프트 lever 였다면, **데이터(allowlist)·UI(picker `.lower()`)가 소문자를 주입하는 별도 축**을 반드시 확인 — 프롬프트 lever 로는 데이터-drift 를 못 잡는다. (3) 봉인은 **코드 권위선**: 런타임에 서버 실제 case 로 canonicalize(라이브 SCHEMATA, case-insensitive 유일매칭·모호 제외) + write-path 정규화. **보안 게이트는 소문자 비교로 유지**하면 canonicalize 가 접근 경계를 바꾸지 않는다(표기만 교정). (4) 거짓양성 주의: MSSQL/case-insensitive collation 백엔드의 case mismatch 는 무해 — 실패 클래스는 case-sensitive 백엔드만.
- How to apply: 스키마/DB 목록을 소비·저장하는 모든 경로(allowlist resolution·UI picker·auto-classify·grounding)에서 소문자화(`.lower()`)를 **비교용에만** 쓰고 저장/표시/쿼리값은 서버 실제 case 를 보존. 신규 case 이슈 진단 시 metadata graph(동기 snapshot)로 서버 실제 case 를 ground-truth 로 대조.

### LRN-20260724-0001 — 전문(full-text)-반환 도구를 신설해도 상위 에이전트 루프의 전역 결과 캡이 그 도구 목적을 조용히 재절단한다
- Source: conversation_audit FR-procedure-analysis-result-truncated (사용자 "타임아웃된 프로시저 분석" 보고) / CHG-20260724T155534-tool-result-cap-raise
- Category: pattern
- Frame: 새 도구를 "긴 단일-권위 텍스트"(저장 프로시저/함수 정의·DDL·전문 문서)를 반환하도록 설계하면, **핸들러 레벨의 무-절단만으로는 부족**하다. 상위 오케스트레이션(에이전트 도구 루프)이 **모든 도구 결과에 거는 전역 결과 캡**(context sizing)이 그 도구 출력을 다시 잘라 목적을 무력화한다. 실사례: `describe_routine`(프로시저 정의 전문 반환)이 루프의 전역 4000자 하드캡에 재절단돼 사용자가 긴 프로시저를 "한 번에 분석 불가". 전역 캡의 원 목적은 **대량-행 결과의 컨텍스트 폭주 방지**라, 정의-반환 도구의 목적과 구조적으로 충돌한다. (1) 신호/근본 추적: 전문-반환 도구를 신설했는데도 절단 마찰이 재발하면, 근본을 **도구 핸들러가 아니라 상위 루프 캡**(L2)에서 찾아라 — 핸들러는 전문 반환하나 루프가 재절단하는 비대칭이다. (2) 절단 3지점 주의: LLM-facing 되먹임뿐 아니라 **재추론(rederive) 경로·DB 저장 copy**도 같은 캡을 독립 보유할 수 있어 하나만 고치면 히스토리 reload·재답변에서 재발한다 — 전 지점을 단일 상수/헬퍼로 일원화하라.
- How to apply: 도구 결과 캡은 (a) **큰 유한 backstop**(정상 전문 텍스트는 통과·병리적 대량 결과만 차단)으로 두거나 (b) 도구별 정책으로 분기한다. 캡을 config 상수화(`AGENT_TOOL_RESULT_MAX_CHARS`)해 운영자 튜닝·무제한 sentinel 을 열어두고, **절단이 실제 발생할 때만** epistemic note(FR-partial-evidence 계약: 미열람분 존재/부재/개수 전수 단정 금지)를 유지해 완전성 오단정 회귀를 막는다. tradeoff(메시지당 컨텍스트 상한 상향)는 context_length graceful degradation 이 있는지 확인 후 수용.
