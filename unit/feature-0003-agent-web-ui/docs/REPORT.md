---
doc_type: REPORT
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## TASK-20260909T120000-diff-similarity — 2026-09-09

DQA 첨부 diff의 원문 완전 일치 기반 정렬을 공백·대소문자 정규화 앵커와 구문 유사도 정렬로 개선했다. 원문이 다른 줄은 계속 replace이며 문자열과 인용 식별자는 정렬에서도 구별한다. 반복 SQL·잘못 닫힌 인용 입력의 성능 문제를 독립 리뷰로 적발·해소했다. 계산 제한은 안내로 표시한다.

집중 Python 91건, Node diff 128건·계보 24건, 실제 제품 Shell/WebView2 fixture 21건 PASS. 전체 회귀·원격 반영·배포 진행 중. 설치된 사용자 DQA와 실제 첨부/API 왕복은 아직 미검증이다. 실행 경로·원본 캡처는 `test-runs.d/TASK-20260909T120000-diff-similarity.md`에 기록한다. 정책 SHA256 `a28388df8ae641cb3e1a19fd3850543cdc197adbc56bc858807d74ae1694b4f2`, 작업/브랜치는 TASK 정본.

## TASK-20260908T125500-step-tool-syntax-leak — 2026-09-08

**실행 단계 패널에서 도구 호출 구문 제거** (Major §12.3 — 표시 계층 + 비신뢰 입력 처리.
스키마·RBAC·엔드포인트·마이그레이션 델타 **0**).

사용자 제보: 「실행 단계에서 나타나는 각 도구의 구문이 그대로 클라이언트에 노출」. 캡처에서
제목은 `search_tables {'keyword': 'masangsoft_member_channeling_gzr'}`, 배지는
`search_tables`·`read_task_attachment` 였다.

**원인은 추정이 아니라 실측으로 확정했다** — 라이브 `agent_runtime.steps` 에서
`work_source='external-ai'` **30행 중 19행(63%)** 이 그 형태. 이 `work` 는 연결된 개인 AI 가
`POST /api/ai/tools/<name>` 본문에 실어 보내는 값이고, 브리지 프롬프트(`feature-0043`)는
`reason` 만 규정하고 `work` 는 **규정조차 하지 않는다**. 즉 계약 없는 비신뢰 입력을 서버가
그대로 저장하고 화면이 그대로 그렸다. 프롬프트에 규칙을 더하지 않은 이유: 프롬프트 계약은
지시이지 집행이 아니고(같은 판단이 그 파일 주석에 이미 있다), 러너는 사용자 PC 에 있어 낡은
빌드가 남는다. **서버가 판정하고 서버가 대체한다.**

**적대 검증 2라운드를 거쳐 설계를 재작성했다.** 라운드 1 에서 4명 전원 BLOCK — 뿌리는
초판 판정기였다. 「인용 없는 snake_case 로 시작」 규칙이 라이브 원장 **9,759행 전건 재생**에서
412행을 걸렀는데 그중 실제 도구 구문은 **18행뿐**이고 394행(96%)이 정상 제목이었다(손익비
1:22). 이 도메인은 **테이블 이름이 곧 사용자의 어휘**다. 지금 서명은 둘뿐이다 — (a) 인자 매핑
리터럴 (b) **서버 도구 census 의 이름**. 재설계 후 같은 재생에서 버려지는 제목은 **19건**이고
버려진 사유 **0건**, 잔존 유출 **0건**이다.

**조치 4갈래** — (1) 판정기(`_step_text_is_tool_syntax`) 정본 1곳 + 표시용 대체는 이미 있던
`_derive_step_work` 파생 문구. (2) 세 이음매(적재·완료 표시·진행 표시)가 **같은 판정·같은 대체**
를 쓴다 — 표시 두 경로를 함께 고쳐야 이미 적재된 행(사용자가 지금 열어 보는 대화)이 복구되고
제출 순간 제목이 바뀌지 않는다. (3) 사유(reason)는 파생 대체가 없는 축이라 「선두 식별자」 규칙을
끈다. (4) 파생 폴백과 배지가 식별자를 내보내던 두 갈래도 함께 닫았다(파생 꼬리 문구 표 + 일반
강등, 배지 표 7종 → 30종, 미지 도구 `"도구"`).
**저장된 원문은 건드리지 않는다** — 판정은 표시층 전용이라 감사·되돌림 근거가 남는다.

**적대 검증이 결함 2건을 잡았고 둘 다 이 cycle 에서 수정했다.** (1) 라운드 1 이 **판정 축 자체를 뒤집었다** — 「선두 식별자」 규칙은
폐기됐고, 지금 서명은 (a) 호출 형태의 인자 매핑 리터럴과 (b) 서버 도구 census 의 이름 둘뿐이다.
(2) 라운드 2 가 **내 수정이 만든 신규 결함 2건**을 잡았다 — 「전수」를 선언한 프런트 가드가
`app.js` 한 파일만 보고 있어 `app/progress.js` 회귀가 무증상 통과했고(모수를 프런트 전 모듈로
확장), 폴백 제목이 라벨을 되풀이해 「테이블 구조 · 테이블 구조 단계」가 나왔다(폴백 여부를
호출측에 전달). 그 밖에 `intent` 를 완료 payload 에서도 제거하고, census 를 레지스트리 조회로
바꾸고(폴백은 조회 실패 시에만), 표시 경로의 **사유 파생은 되돌렸다** — 규칙을 좁혀 사유 손실이
0 이 된 지금 그 파생은 AI 가 말한 적 없는 근거를 구분 없이 렌더하는 신규 노출면일 뿐이다.

**검증** — 라이브 원장 **9,759행 전건 재생**: 버려진 제목 19건(인자 리터럴 14 + 도구명 언급 5)
· 버려진 사유 **0건** · 잔존 유출 **0건**. 신규 테스트 **66건 PASS**(적대 인자 벡터 · census 전
도구의 진행/완료 동치 · 전각·제로폭 우회 · 결함 주입 대조군 4종 + 조치 봉인 8종). 행위 하네스(node) **17항목 PASS**,
결함 주입본 **8 FAIL** 실증. 전체 집합의 **선재 실패 19건은 `origin/main` 원본에서 동일**하게
실패함을 확인했다(차집합 0 — 회귀 아님). ruff clean.

**미검증** — **DQA 클라이언트 화면 실측 미수행**. 실행 중인 앱의 WebView2 에
`--remote-debugging-port` 가 없고(실측: `Win32Process.CommandLine`), DQAConnect.exe 가 여는
`127.0.0.1:63817` 은 `/json/version` 에 **405** 를 돌려주는 로컬 브리지 HTTP 라 CDP 가 아니다.
PB-0009 3번 항목대로 포트를 추정하거나 사용자 앱을 종료하지 않았다. 배포 후 사람 관찰 + 캡처로
재검증한다. **배지 폭은 headless Chromium 실렌더로 측정했다** — 340px 에서 30종 전건 헤더 1행,
300px 에서는 예외 2종(`describe_routine`·`search_routines`, 각 74.8px)만 시각 요소가 2행이며
비예외 최대 65.3px 는 전건 1행이다.
## TASK-20260908-prompt-layer-delivery

여섯 계층의 요청 순서·최종 CLI 전달을 검증하고 조회 실패 은폐를 수정했다. DB 오류는 bridge의 strict 조립에서 차단하며 기존 placeholder에 원인을 기록하고 5초 비동기 간격으로 재시도한다. 최초 점유자와 일치하는 경우에만 해제한다. 제품 표시명 조회 오류는 내용 조회를 막지 않는다. 집중 회귀 180건과 bridge 전체 1,700건(1 skip), 독립 backend/security/QA 리뷰를 통과했다. DQA 앱 화면 시나리오는 실행 중 앱의 CDP 미개방으로 NOT-RUN이며 source 검토와 구분한다. 출하 결과는 해당 PR의 최종 Git/배포 기록을 따른다. [상세 Run](test-runs.d/TASK-20260908-prompt-layer-delivery.md).


## TASK-20260908T150000-attachment-boundary — 첨부 경계 감사

- 상태: PR #1629 병합 및 e8fd398b 전체 배포 완료. 120 pytest·3패널·배포본 56검사 PASS.
- 실측: 대화 …8c73806a의 assistant 파일 10개 중 6개에 다음 설명/diff 혼입. PostgreSQL replica SELECT + MinIO GET으로 확인; 실제 byte와 저장 SHA-256 10/10 일치. 사용자/첨부 원문 비전재, 운영 데이터 write 0.
- RC: `_attachment_block_spans`의 마지막 bare fence 탐색이 다음 설명/diff를 흡수. `_strip_attachment_*_blocks`가 파일별 완료 문장을 자동 부착. `FR-attachment-last-fence-captures-answer`.
- 변경: 앞방향 fence 경계, 긴 outer 종료 우선, 코드 인용 비실행; 성공 자동 안내 제거; bridge/worker 빈 성공본문 보존; 권위 프롬프트에 내용 분리·원본 주석 보존·반복 완료문구 생략.
- 검증: 관련 6개 모듈 pytest 120 PASS(경계 21건), ROUTEMAP 재생성/codenav-lint PASS. 패널 초기 P2와 인용·empty recall 빈틈 해소 후 3명 PASS.
- 한계: 기존 손상 파일 자동 복원, 사용자 AI 재질의, 실제 DQA 화면은 미실측. 테스트는 서버 처리 계약 증거이며 실제 사용자 대화 마찰 소멸을 단정하지 않는다.
- 정책: `/root/download/docker/mysql_ai_delegated_dev/.worktrees/feature-0003-agent-web-ui/AGENTS.md`; SHA-256 `a28388df8ae641cb3e1a19fd3850543cdc197adbc56bc858807d74ae1694b4f2`; main 동일 해시. Session `01a07f94-148f-7253-a515-1a7a66a97cea`; 2026-09-08T06:09:53.549929+00:00.
- 배포 권한: 현재 사용자 수정 요청 + AGENTS §16.5.1 included. 정본 무중단 스파인 사용. 권한·스키마·비용 계약 변경 없음.
- 배포 실측 (2026-09-08T06:27:43.349266+00:00): `bash bin/deploy-web.sh` exit 0, web-a/b·MCP a/b·insight/ask/ops-scheduler 7서비스 e8fd398b. ready/90초 soak PASS, ask 본체·surge 각각 6초 정상 종료·surge 정리. 서버 LLM 스모크는 호출 차단 계약 PASS이며 실제 사용자 AI 생성 성공을 뜻하지 않는다.
- 동일 배포본에서 서비스별 파서/strip 8검사(총 56) 및 권위 지침 확인 PASS. web-b에서 저장 파일 10개를 읽어 byte/SHA 일치 확인 후 재구성 입력에 파서를 적용해 혼입 6개 후속 답변 제외 확인. DB/object write 0. web-a 암호화키·첨부 저장 자격증명 존재 확인(값 미출력).


## TASK-20260908T120000-connect-discovery-ux — DQA 1.2.0

DQA 클라이언트의 로그인 완료 경로에서 공용 `client-bridge.js` 패널을 시작한다. AI별 카드에 탐색/연결/연결됨/위치 선택/실패를 구분한다. 위치가 하나인 플랫폼 또는 유효한 저장 위치는 자동 연결하고, 같은 AI의 중복 위치만 radio를 표시한다. 성공 토스트는 공용 앱 toast에 플랫폼·위치를 담아 순서대로 노출한다. 하나의 연결이 끝나도 남은 선택 화면을 닫지 않는다.

Issue #1615. 자동 연결·중복 위치 선택·클라이언트 캐시·모델 등록 후 toast를 구현했다. 최신 main의 아이콘/자동 복구를 통합했다. 검증과 릴리스 결과는 `test-runs.d/20260908T123400-connect-discovery.md`에 기록한다.

## TASK-20260908T124500-attach-folder-tree — 2026-09-08

첨부 전달의 단위를 **파일에서 폴더(디렉토리 트리)** 로 넓혔다. 사용자 요청(2026-09-08):
"폴더 또한 전달할 수 있도록 · 디렉토리 트리도 보존 · assistant 또한 이러한 구조를 인지".

**무엇이 없었나**: 컴포저는 파일 여러 개는 받았지만(`multiple`) **폴더는 못 골랐고**, 폴더를
드롭하면 `dataTransfer.files` 가 그것을 버려 아무 일도 일어나지 않았다. 서버는 `OriginalFilename`
(basename)만 저장해 그 파일이 원래 어느 폴더의 어디에 있었는지 알 방법이 없었고, assistant 는
평평한 파일 목록만 봤다.

**세 면을 함께 고쳤다** — (1) 입구: 폴더 선택 input(`webkitdirectory`) + 드롭 디렉토리 **재귀
순회**(`webkitGetAsEntry`, `readEntries` 를 빈 배열까지 반복 — 안 하면 큰 폴더 뒷부분이 조용히
사라진다), 300개 상한은 **자르지 않고 멈춘다**(일부만 올리면 사용자는 전부 올라간 줄 알고
assistant 에게 없는 파일을 묻는다). (2) 저장: `RelativePath`(MySQL, fast+slow 부트스트랩 양쪽
online DDL) · `relative_path`(PG alembic `0059`, expand-only) + dual-write 미러 3면, fork·assistant
편집본이 경로를 승계. (3) 인지: 프롬프트 파일 라인의 `path="..."` 와 `DIRECTORY STRUCTURE` 트리
블록, `read_attachment` 의 경로 지칭.

**이 변경의 load-bearing 부분은 버전 체인 스코프다.** 스코프가 `(conv, account, filename)` 인 채로
폴더를 받으면 `src/config.json` 과 `test/config.json` 이 한 체인으로 합쳐져 **서로를 supersede** 한다
— 사용자가 올린 파일이 목록에서 사라진다. 컬럼만 추가하고 스코프를 두면 기능이 아니라 데이터
손실이므로 같은 cycle 안에 넣었다. 경로 있는 행과 없는 행도 서로 배제한다(폴더 안 `a.txt` ≠ 따로
올린 `a.txt`).

**경로는 신뢰하지 않는다** — `webkitRelativePath` 는 브라우저가 보내는 사용자 입력이다.
traversal·절대경로·드라이브 접두·제어문자를 제거하고 깊이 32·길이 1024 를 건다. 위험한 값은
**거절이 아니라 폴더 정보 폐기**(파일 자체는 올라간다 — 경로는 부가 정보이지 업로드의 전제가 아니다).
경로의 마지막 세그먼트는 업로드된 파일명으로 고정한다(둘이 어긋나면 목록·트리가 실제 파일과 다른
것을 가리킨다).

**무회귀 설계**: 폴더 첨부가 없는 대화의 프롬프트는 종전과 **동치**(트리 블록 미렌더 — 테스트로
고정). 마이그레이션 전 배포(row 가 짧음)에서는 폴더 없는 종전 동작으로 자연 폴백한다.

**§18.8 full panel 이 P1 3건을 잡았고, 그 셋이 이 cycle 의 실질 내용을 바꿨다.**
① 파일명이 ```` ``` ```` 이면 트리 블록이 프롬프트 코드펜스를 닫아 뒤따르는 권위 블록이 통째로
산문으로 새어 나갔다 — 구획을 datamark sentinel 로 바꾸고 이름을 평탄화했다(라이브 실측 확인).
② 백엔드는 「다른 폴더의 동명 파일은 다른 파일」로 고쳤는데 **프론트가 basename 으로 묶어**
「⇄ 계보 비교」가 무관한 두 파일을 버전처럼 diff 했다 — 그룹 키를 같은 술어로 통일.
③ 폴더 배지가 컴포저 pill 에만 있어, 목록을 열거나 대화를 다시 열면 **사용자는 폴더를 못 봤다**
— 「트리를 보존한다」면서 보는 것이 모델뿐이면 요청의 절반이다. 서버 목록 행에도 실었다.
P2 10건(서버측 개수 상한 부재 · 컬럼 부재 시 첨부 섹션 통째 소실 · 드롭 순회 무피드백 · pill
flex 방향이 주석과 정반대 · 트리 토큰 무상한 등)과 P3 5건도 반영했다. 상세는 REVIEW entry.

**검증**: 신규 테스트 40건 PASS(리뷰 반영분 회귀 8건 포함) · 컨테이너 `make test` exit 0 ·
**main 대비 실패 차집합 0**. 기존 테스트 1건이 INSERT 바인딩 **위치 하드코딩**(`ins[10]`) 때문에
컬럼 추가로 깨졌고, 위치가 아니라 내용으로 찾도록 고쳐 같은 취약성을 없앴다.

**시각검증(§16.6 · PB-0008)**: 실 Windows Chrome + 격리 컨테이너(라이브 web 이미지 + 본 branch
`src` 마운트, 라이브 스택 무접촉)에서 폴더 업로드 end-to-end 실측 — `src/config.json` 과
`test/config.json` 이 **둘 다 v1 로 공존**(핵심 결함 회피의 직접 증거) · traversal 무해화 ·
프롬프트 인젝션 중화 · 목록 폴더 칩 6/6 렌더 · 행 높이 55px 균일. 캡처
`docs/evidence/attach-folder-tree-list.png`. **라운드 2 재확인에서 시각 캡처가 새 결함을 하나 더
잡았다** — 긴 폴더 칩이 행 버튼을 다음 줄로 밀어 행 높이가 갈리던 것(element 상태만 봤다면
놓쳤을 픽셀-클래스). 폭 상한 + 마지막 2단 표기로 해소 후 재실측.

### shared/ 변경 (§13.2.2 F2 — 단일 mutator 지정)

- **신규** `shared/attachment_path.py` — 본 worktree(`ai/claude/feature-0003-attach-folder-tree`)가
  이 cycle 의 **단일 mutator** 다. 신규 파일 추가이며 기존 shared 모듈은 수정하지 않았다.
- shared 에 둔 이유: 경로 정규화·트리 렌더를 web(feature-0003 업로드·목록)과 agent-core
  (feature-0002 LLM 컨텍스트)가 **같은 규칙으로** 써야 한다. 정규화가 갈리면 저장된 경로와
  프롬프트에 그려지는 트리가 어긋나고, 그 어긋남은 "assistant 가 없는 파일을 말한다" 로
  사용자에게 도달한다(`shared/share_window.py` 가 같은 이유로 shared 에 있다).

### 게이트 결과

- `bin/migrate-lint.sh` — PASS (head 단일 `0059_attachment_relative_path` · expand-safe).
- `bin/mysql-ddl-lint.sh` — PASS (신규 ALTER 가 `ALGORITHM=INPLACE, LOCK=NONE` 명시).

**남은 것**: assistant 가 **새 파일을 특정 폴더 안에** 만드는 것(`attachment-new` 경로 지정)은
범위 밖 — 현재 AI 생성 신규 파일은 경로 NULL(폴더 밖)이다. 기존 첨부의 경로는 존재한 적 없는
정보라 backfill 하지 않는다. **미수행 검증 2축**: 실제 폴더 드래그&드롭 제스처(브라우저 자동화로
OS 파일 드롭을 합성할 수 없다 — 코드 경로는 테스트로, 결과는 배포 후 실사용으로 확인) · 실 LLM
답변에서의 구조 인지(개인 AI 브리지 미연결 — 프롬프트에 실리는 문자열 자체는 직접 실측했다).
**유니코드 look-alike 분리자**(`／` 등)는 폴딩하지 않는다 — 표시 spoofing 축이고 경로가 어떤
resolve 에도 쓰이지 않아 실피해가 없으며, 폴딩은 전각 문자를 쓰는 정당한 파일명을 훼손한다.
경로를 파일시스템·아카이브에 **결합하는 소비자**(폴더 보존 ZIP 내보내기 등)가 생기면 그때
NFC 정규화와 함께 도입한다.


## TASK-20260908T113000-bridge-token-env — 2026-09-08

갱신 실패 안내 MSG_RELAUNCH_NO_UPDATE를 실제 트레이 [업데이트 확인] 경로로 수정. DQA 클라이언트 단독 사용 기준 유지. 내부 토큰 전달 복구는 feature-0043 소유.
집중 회귀 검증 및 UX/design 리뷰 후 PR·배포 진행. 최종 배포 증거는 PR과 feature-0043 검증 원장 참조.


## 1. Summary

**2026-09-07 TASK-20260907T060000 — 칩 툴팁 2문단 축약 · 컴포저 안내 문단 제거** (Minor §12.3 — `static/index.html` · `static/css/chat.css` · `static/app/composer.js` · `static/app/connect-modal.js` + `routers/ai_tools.py` 출처 허용집합. 데이터·권한·스키마 델타 **0**). 사용자 제보 두 건. **① 툴팁이 «너무 장황»** — 최장 상태가 4문장·140자였다(「러너는 실행 중이지만 아직 그 AI 가 응답한다는 것을 확인하지 못했습니다 … 지금 질문을 보내도 접수는 되지만…」). 전부 참이고 diff 도 작아 **어떤 정확성 게이트에도 걸리지 않는다**(AGENTS.md §16.8 의 문제 진술 그대로). 6종을 모두 **2문단**(상한 3)으로 줄이고 내부 어휘를 대상 사용자 어휘로 낮췄다 — 「머신을 재시작했다면」→「컴퓨터를 다시 켰다면」 · 「러너가 서버 배포본과 다릅니다」→「연결 프로그램이 최신본이 아닙니다」(§16.8 B-2). 칩 **라벨**(연결 안 됨/대기 안 함/답할 수 없음/업데이트 필요/확인 중/대기 중)은 불변. **② 컴포저 위 안내 문단이 «의도하지 않은 UI» 이고 높이 정합을 깼다** — `#composerActionsSelectorNote` 의 DOM·CSS·JS 배선을 제거했다. 이 문단은 **두 번** 레이아웃을 깼다(2026-09-02 `.composer-box` 플렉스 항목이라 입력창을 옆으로 밀었고, 입력창 위로 옮긴 뒤엔 자기 줄로 컴포저 **높이**를 바꿔 사이드바 프로필 행과 어긋났다). 두 번 다 «자리를 옮겨» 고쳤으므로 이번엔 «두지 않는다» 를 계약으로 잠갔다 — 조건부로 나타나 높이를 바꾸는 요소는 어디에 두든 정합을 흔든다. 서버 필드(`model_selector_reason`·`runner_download_url`)는 판정·진단 근거라 유지, 화면 소비처 하나만 제거. **검증** — PB-0008 실 Windows 브라우저(격리 컨테이너 `https://172.26.154.233:18099`, 라이브 web 이미지 + 본 branch `src` 마운트, 라이브 스택 무접촉): 안내 요소 **0** · 파싱된 `.composer-actions-note` 규칙 **0** · 툴팁 **2문단 33자** · `.sidebar-profile` bottom **889** ↔ `.composer-wrap` bottom **889** **일치** · `+` 메뉴 4항목 정상 렌더. 스크린샷 2장(`step_09`·`step_13`). **테스트** — 툴팁 문단·문자 예산 게이트 신설(분량 축은 정확성 게이트가 원리적으로 못 잡는다) · 안내 문단 «제거» 계약 2건 · `verify_selector_note.mjs` 제거(검증 대상 소멸) · 어휘 단정 재조준 1건. ⚠ **대가**: 「왜 선택기가 없는가」를 말하던 유일한 화면 표면이 사라졌다. 남은 자리는 프로필 행의 연결 칩(상태 + 다음 행동)과 연결 모달이며, 같은 주기의 feature-0043 수정이 그 상태 자체를 드물게 만든다(러너가 목록을 실제로 얻는다).

**2026-09-01 20260901T1900-conv-status-dot-wiring — 사이드바 대화 상태 배지의 색 배선 복원 + 동종 배선 끊김 전수 판정 게이트** (Minor §12.3 — feature-0003 `static/app/conv-status.js`(신규) + `static/app/sidebar.js` + `static/app.js` + `static/css/{shell,profile,search-audit}.css` + 신규 계약 테스트 9건 + 감사 스크립트. 데이터·권한·API·스키마 델타 **0**). **사용자 지적 2건**: assistant 에게 요청을 보냈을 때 좌측 사이드바 대화 뱃지 색이 상태값에 따라 안 바뀐다 / 이와 같이 배선이 끊긴 기능들을 모두 정합하게. **① 원인은 단일 버그가 아니라 어휘가 세 갈래로 갈린 배선이었다** — dot 클래스를 `is-${status}` 로 **세 곳에서 각각** 조립(사이드바 일반 행 · 인라인 이름변경 행 · 폴링 중 DOM 직접 갱신)했고 CSS 는 그와 따로 자랐다. 배포본 실측에서 **151개 항목 중 133개(`is-done` 110 · `is-error` 21 · `is-canceled` 2)가 상태를 정확히 알면서 computed background 가 전부 `rgb(196,196,201)` 기본 회색**이었다. CSS 가 가진 `.conv-dot.is-completed` 는 **아무도 만들지 않는 죽은 규칙**(서버 완료 리터럴은 `done`)이고, `stale_error` 는 CSS 가 하이픈·코드가 언더스코어라 어긋나 **같은 줄의 `title` 툴팁만 뜨고 색은 안 변하는 비대칭**을 만들었다. 세 결함 모두 **파일을 따로 보면 정상으로 읽힌다** — 클래스는 붙고, CSS 문법은 맞고, 서버는 상태를 정확히 쓴다. 끊긴 것은 그 사이의 짝이다. **조치** — 어휘 정본 leaf 모듈 `app/conv-status.js` 를 두고 조립 지점 **4곳 전부**를 그것만 쓰게 했다(`app.js` ↔ `app/sidebar.js` 는 서로 import 하므로 공용 헬퍼는 leaf 여야 순환 TDZ 가 안 난다). CSS 는 흩어져 있던 규칙(`shell.css` + `profile.css`)을 한 블록으로 모으고 7상태를 채웠다 — **정의가 두 파일로 갈린 것 자체가 어휘 drift 를 못 보게 한 원인**이다. 모르는 상태는 modifier 없이 기본 회색으로 degrade 한다(종전처럼 `is-<모르는값>` 을 만들면 무색인데 "클래스는 붙었으니 배선은 됐다" 로 읽혀 이번 결함이 오래 숨었다). 색-only 의존을 없애려 상태 라벨을 `title` 로 부여. **② 전송 직후 표면도 함께** — `is-pending-inflight`·`is-pending-failed` 는 CSS 규칙이 **0건**이라 보내는 중인지 실패했는지가 일반 항목과 똑같이 보였고, 실패 행의 dot 은 행이 실패를 아는데도 `is-pending`(대기 색)이었다. **③ 「모두 정합하게」는 전수 열거로 닫았다** — 상태 modifier 축을 전수 감사해(`scripts/audit_state_class_wiring.py`) 무스타일 11건을 판정: 수정 3종(conv-dot 7상태 · in-flight 2종 · `is-inherited` 읽기 전용 행) · **근거 달린 화이트리스트 7종**(`is-gap`·`is-plain`·`is-source`·`is-unified`·`is-chain`·`is-group`·`is-enabled` — 각각 왜 시각 규칙이 필요 없는지 명시). 계약 테스트 T4 가 이 판정을 CI 게이트로 잠가, 앞으로 CSS 없는 상태 클래스를 추가하면 **적색이 나고 근거를 적어야만 통과**한다. **검증**: 컨테이너 `make test` **6829 passed / 15 skipped / 0 failed**(3회) · 배선 계약 **10건 PASS** · **회귀 뮤턴트 10종 전건 KILL** · **PB-0008 실측** — 배포본 결함 재현(133건 동색) ↔ 수정본(`done` `rgb(22,163,74)` · `error` `rgb(220,38,38)` · `canceled` `rgb(128,125,114)`), 전송 시퀀스 `pending`(파랑)→`processing`(주황)→**`done`(초록)** 전이, 동일 화면 스크린샷 2장. **라이브 실측이 초판 결함 2건을 잡았다** — 미지 상태 전이 시 직전 툴팁 잔존 / 폴링이 사이드바의 stale 구체 문구("마지막 활동: `<시각>`")를 일반 라벨로 퇴화(conv-audit 봉인 B 계약의 회귀). `data-title-status` 이음매로 해소 후 재실측 PASS. **§18.8 검증(`/codex review`, `[P1]` 0 · `[P2]` 5)은 구현이 아니라 게이트의 사각지대 5건을 잡았다** — 상태 writer 를 하드코딩 목록으로 들고 있어 실제 writer 하나를 못 보고 변수 인자 호출을 조용히 건너뛴 점 · CSS 를 셀렉터 이름으로만 확인해 빈 규칙이 통과하던 점 · 툴팁 이음매를 아무 테스트도 건드리지 않던 점 · 감사가 `${…}` 를 통째로 비워 조건식 전용 클래스가 양쪽 집합에서 동시에 사라지던 점 · 직접-조립 탐지가 줄 단위라 줄바꿈 우회가 되고 호출 수 최소치가 실제보다 낮던 점. 다섯 건 모두 **재현 확인 후 수정**했고 각각에 대응하는 뮤턴트로 KILL 을 실증했다. ⚠ 다만 툴팁 이음매 T5 는 **소스 형태 검사**다 — CI 가 pytest 전용이라 브라우저 실행을 게이트에 넣을 수 없고, 실제 동작 근거는 PB-0008 실측이다(둘을 같은 강도로 읽지 않는다). **미수행**: 실 LLM run end-to-end 전이(개인 AI 브리지 러너 미연결 — 전송 버튼 `is-access-blocked`. 폴링 함수 실 구동으로 같은 배선을 덮음) · POST-DEPLOY 배포본 자산 재확인.

## 8. 개선 제안 (기록만 — §8.1, 사용자 지시 없이 실행하지 않음)

**컴포저 높이는 여전히 조건부로 바뀐다 (적대리뷰 P2, 2026-09-07 · 이 cycle 밖)**

이번에 지운 안내 문단의 제거 근거(「자기 줄을 차지해 컴포저 높이를 흔든다」)가 남은 형제
둘에 **그대로 성립한다** — `.composer-gate`(`display:flex; margin:0 0 8px`)와
`.timeout-extend-banner`(동일)는 정적 흐름 행이다(`.gc-guide-tip` 만 `position:absolute`).
둘 중 하나가 켜지는 순간 `.composer-box` 하단이 이동해 사이드바 프로필 행과 다시 어긋난다.
즉 이번 수정은 **증상 인스턴스 하나**를 없앴고 근본 원인(컴포저 높이 비고정)은 남아 있다.

처방(미실행): 컴포저 영역의 높이를 고정하고 조건부 행을 그 안에서 겹치게(absolute) 두거나,
사이드바 프로필 행을 컴포저 하단이 아니라 뷰포트 하단에 앵커한다. 어느 쪽이든 레이아웃
결정이라 사용자 판단이 필요하다.

**`model_selector_reason`·`runner_download_url` 의 소비처가 0 이다 (같은 리뷰)**

안내 문단 제거로 두 필드를 화면에서 읽는 곳이 사라졌다. 이 저장소는 2026-09-02 적대리뷰에서
`caps_pending` 을 「소비처 없는 필드는 남기지 않는다」로 제거했고 그 규칙을 AST 테스트가 강제
중이라, 규칙의 적용면이 갈린 상태다. 다만 두 값은 **서버 판정의 근거이자 진단 필드**이고
`test_caps_live_sync.py` 가 그 문안을 계약으로 잠그고 있어, 제거는 서버 계약과 그 테스트를
함께 다루는 별도 cycle 이 맞다.

**`test_shutdown_finalizer_marks_this_process_processing` 은 벽시계에 매인 테스트다 (관측 2026-09-07, 이 cycle 밖)**

전체 `make test` 에서 간헐 실패했고 단독 실행은 통과한다. 실패 시 캡처 로그가 원인을 그대로
말한다 — `shutdown finalize: 시간 예산 초과`. `_finalize_inflight_runs_on_shutdown` 은
`deadline = time.monotonic() + 8.0` 을 잡은 뒤 루프에 들어가는데, 그 사이의
`_active_ask_job_conversation_ids()` 를 **테스트가 모킹하지 않는다**(`_patch_common` 은
`_open_memory_connection`·`list_processing_conversation_ids`·`load_memory_kv`·`set_run_status`
넷만 patch). worker mode 면 그 함수가 `_pg_connect()` 를 실제로 시도하고, `make test` 는
`AGENT_KB_PG_PORT=1` 로 그 연결을 **의도적으로 막아 둔다** — 즉 실패 타임아웃이 예산 안에
들어오느냐가 머신 부하에 달린다. 부하가 높으면 8초를 넘겨 루프가 첫 회에 break 하고
`calls == 0` 이 된다.

이 cycle 의 변경과 무관하다: 스테이징에 `app.py`·`_conv_store.py` 가 없고, 테스트 실행
순서상 이 파일(feature-0003)이 이 cycle 이 추가한 스레드(feature-0043)보다 **앞서** 돈다.

처방(미실행 — 사용자 지시 대기): `_patch_common` 이 `_active_ask_job_conversation_ids` 를
함께 patch 하거나, 예산 검사를 루프 진입 **전** 1회로 옮겨 「후보가 있는데 한 건도 못 본」
상태를 만들지 않게 한다. 전자가 좁고 안전하다.

**CSS 규칙이 0건인 «장식» 클래스 76건** — 본 cycle 의 상태 modifier 축 감사에서 함께 드러난 잔여다.
상태 배선(기능 인지)이 아니라 레이아웃·장식 축이라 이번 범위에서 제외했다. 판단 기준은
「그 클래스가 없으면 사용자가 상태·기능을 인지하지 못하는가」였고, 아래는 전부 "아니오" 다.
재현: `python3 unit/feature-0003-agent-web-ui/scripts/audit_state_class_wiring.py` 와 같은 방식의
base-클래스 축 감사.

- **가장 큰 군집 — 프로필 화면 권한 섹션 (`perm-*` 11개)**: `app.js` 가 `perm-section` /
  `perm-pills` / `permission-pill` / `perm-section-meta*` 등을 부여하는데 CSS 는 **0건**이다.
  같은 화면 개념의 관리 콘솔 쪽(`admin.js`)은 `permission-*` 이름을 쓰고 CSS 가 갖춰져 있다 —
  **이름 축이 두 갈래로 갈린 drift**. 기능은 동작하나 프로필의 권한 목록이 무스타일로 나열된다.
  고치려면 11개 규칙의 디자인 결정이 필요해 별도 cycle 이 맞다.
- 나머지 65건은 `attach-diff-*`(17) · `admin-*`(17) · `cov-*`(7) · `aiops-act-*`(5) 등
  화면별 장식 클래스. 목록은 감사 스크립트로 언제든 재생성된다.

**`is-group` 은 제거 후보** — `sidebar.js` 가 부여하지만 CSS·JS 어디서도 읽지 않는다. 그룹 대화의
시각은 `.conv-item-group-badge` 가 전담하므로 이 클래스는 현재 아무 일도 하지 않는다.

## 1. Summary

**2026-09-01 20260901T1740-side-panel-exclusive-postdeploy — 라이브 배포본 실측**(doc-only). 선행 cycle `side-panel-exclusive` 의 §16.3 deploy-backed 완료 조건 2 를 채운다. 배포 판정 4축: PR #1475 머지 `cce7df5e` ⊂ 라이브 `d3ead999`(web-a·b `GIT_COMMIT` 동일) · 컨테이너 내 `side-panels.js` 실재 · `/healthz` 200 · 엣지 `no upstreams available` 0. **PB-0008 POST-DEPLOY 16 step ok** — 라이브 자산 스탬프 `9763bcf30835` 모듈로 실행(PRE-DEPLOY 는 `?v=dev` 격리 빌드라 서로 다른 대상). 접근성(`aria-hidden`/`inert`)·상태 복원(휴지통 모드 유지 / × 닫기 리셋 / 대화 전환 시 폐기) 전 축 재현. **정직**: `deploy-web.sh` 는 멱등 no-op 이었다(병렬 세션이 이미 상위 커밋 배포) — 완료 근거는 명령 이력이 아니라 라이브 실측이다. 잔류물 정리 완료(격리 컨테이너 2개 제거·임시 env 삭제·브라우저 종료).

**2026-09-01 20260901T170000-lineage-row-compaction — 계보 내부 되풀이 제거 + 행 한 줄 간소화** (Minor §12.3 — feature-0003 `static/app/composer.js` + `static/css/chat.css` + 회귀 4건. 데이터·권한·API·노출면 델타 **0**). **사용자 지적 2건**: 파일 제목과 중복된 문자열이 계보 내부에 남아 있다 / 각 계보가 두 줄(업로드 주체 · 파일 정보+버튼)인데 한 줄로 간소화 가능한지 검토. **① 되풀이** — 카드 하나에서 같은 파일명이 **6회**(머리 1 + 계보행 2 + 버전행 3) 실리고 있었고, 계보 안내문(「AI가 만든 계보 · 다른 파일에서 갈라짐 · 파일 N개 · 다른 계보 M개」)의 네 사실은 이미 전부 카드 머리·행 칩·토글이 **구조로** 말하고 있었다. 버전 행의 파일명과 안내문을 걷어내 **6회 → 1회**로 줄였고, 화면에 상시 떠 있던 raw enum `uploaded`(텍스트 첨부에서 정상이자 영구 상태 — 사용자가 할 것이 없다)도 감췄다. ⚠ **지운 것은 화면 문구뿐** — 파일명은 `title`·`aria-label`·「원문 보기」 클릭 대상에 그대로 남고, 모르는 status enum 은 계속 원문 노출한다(조용히 삼키면 새 실패 상태가 사라진다). **② 한 줄** — 버전 행이 2줄이던 **근거가 파일명이었다**("한 줄에 몰면 240px 에서 이름 가용폭 2자"). 그 근거가 사라져 **전 폭에서 한 줄(20px)** 로 복원됐다. 계보 행은 `.attach-list-item-meta` 를 `display: contents` 로 투명화해 액션과 정보 텍스트가 메타 **안에서** 폭을 다투던 구조를 풀었고(실측: info 205px 중 메타 62px), 정보 손실 0 인 폭 되찾기(간격 8→4px · 여백 축소 · 레일 12→9px · 카드 패딩 7→5px · 분기 칩 문구→글리프 `⤷` + `aria-hidden`(말은 title·aria 유지) · `9KB · +8KB`→`9KB +8KB`)로 **사람 업로드 행이 280px 에서 두 줄 → 한 줄**이 됐다. **AI 수정본 행은 62px 이 모자라 기본 폭에서 불가**하다(필요 268 / 가용 206) — 되찾으려면 `버전 2개 ▾`(52px)·`+8KB`(34px)·`8/31`(30px) 중 하나를 빼야 하고 셋 다 정보 손실이라 **임의로 빼지 않고 수치로 남겨 선택을 사용자에게 돌렸다**(「잘림 대신 줄바꿈」이 이 패널의 기존 원칙 — 넘칠 때 자르면 「버전 N개」 같은 유일한 진입점이 사라진다). **검증**: pytest `feature-0003`+`feature-0002`+`feature-0023` **5177 passed / 5 skipped** · `node --check` · **PB-0008 폭 4구간 실측**(240/260/280/320 행 높이). **캡처가 결함 1건 포착** — 분기 칩을 글리프 한 자로 줄이자 파선 pill 안에 `⤷` 만 남아 «빈 동그라미» 로 보였다(테두리 제거로 수정; 「색 단독 의존 금지」는 파선 대신 글리프가 충족). **미수행**: POST-DEPLOY 재확인(배포 후) · ⚠ `test_query_embed_visibility.py` 2건은 **main 기준선 동일 실패**(본 변경 무관, 스위트 순서 의존).

## 1. Summary

**2026-09-01 20260901T163000-attach-lineage-uploader — 공유 대화에서 계보를 «누가 올렸는지»로 가른다 + 그룹 카드 되풀이 제거** (Minor §12.3 — feature-0003 `routers/_conv_store.py`(payload 필드 1개 추가) + `routers/conversations.py`(표시명 IN 조회) + `static/app/composer.js` + `static/css/chat.css` + 신규 회귀 11건. 스키마·권한·엔드포인트·파괴적 변경 **0**). **사용자 지적 3건**: 공유 대화에서 각 계보가 구분되는지 / 아이콘·파일명 중복 최소화 / assistant 가 계보 현황을 파악해 답변할 수 있는지. **세 번째부터 확인한 것이 나머지 둘의 성격을 바꿨다** — `_build_attachment_context_section` 을 라이브 대화(`20260813083932`, 계정 10·50)에 대해 **실제로 렌더**해 보니 `## FILE VERSION LINEAGES` 가 이미 `uploaded by jmkimmasangsoft.com` / `uploaded by admin` 으로 계보를 이름으로 가르고 per-lineage↔overall latest 두 축과 타 멤버 read-only 경계까지 싣고 있었다(caller 10·50 양쪽 확인). 즉 **결함은 「모델이 모른다」가 아니라 「같은 사실이 화면에 도달하지 않는다」** 였다 — 목록 직렬화가 `AccountId` 를 버려서, 화면은 사람이 올린 계보를 전부 「사용자 계보」로 뭉뚱그렸고 **공유 대화의 서로 다른 멤버 계보 8행이 글자 하나 다르지 않았다**. 선행 cycle 이 세운 "소유권 단정 금지" 는 *데이터가 없어서* 였지 원칙이 아니었으므로, 사실이 생긴 만큼만 말하도록 열었다. **조치** — ① payload 에 `account_id` + `uploader_username`(WebAccounts IN 조회 1회, **fail-soft**: 실패해도 목록은 나가고 미해소는 `null`, 「업로더 미상」으로 표시하지 「내 파일」로 격하하지 않는다) ② 표시는 **공유 대화 한정**(저장소 단일 술어 `isGroupConversation`) — 1:1 은 업로더가 늘 자기 자신이라 이름이 정보 0 이면서 240px 이름줄만 먹는다 ③ **되풀이 제거**: 카드 하나에 파일명 3회·아이콘 3회 실리던 것을 아이콘은 머리로 통합, 행의 1차 라벨을 파일명 → **계보 정체성**으로. ⚠ 요소 자체는 지우지 않았다 — 「원문 보기」 클릭 대상이자 접근성 이름이라 `title`·`aria-label` 은 파일명을 유지한다(화면에서 지운 것을 AT 에서도 지우면 안 된다) ④ 정체성이 라벨로 올라갔으므로 **분기 칩은 분기 사실 전용**(`⤷ 갈라짐`)으로 좁히고 색축도 라벨로 이전 — 한 사실을 두 곳에서 말하지 않는다. **검증**: pytest `feature-0003`+`feature-0002`+`feature-0023` **5167 passed / 5 skipped**(신규 11건) · `node --check` · `ast.parse` · **PB-0008 경계 3경로** — 공유(`jmkimmasangsoft.com`/`admin` 분리 · 행 아이콘 **0** · 머리 아이콘 4) / 1:1(`사용자 업로드`·`AI 수정본`, 이름 없음) / 단독 계보(카드 없음 · 아이콘 **2/2 유지** · 라벨 = 파일명) + 240px 폭 무손실. **캡처가 결함 1건 포착** — 카드 머리가 접힐 때 아이콘만 자기 줄로 떨어져 파일명과 분리되던 것을 한 덩어리(`min-width: 0`)로 묶어 수정. **미수행/이월**: POST-DEPLOY 재확인(배포 후 별도 Run) · ⚠ `test_query_embed_visibility.py` 2건이 전체 스위트에서 실패하나 **main(`afcd1a42`) 기준선에서도 동일 재현** — web-ui 테스트의 `sys.modules` 스텁 미정리로 agent-core 테스트의 `parents[3]` 가 IndexError. 본 변경 무관이며 **CI 결제 정지로 드러나지 않고 있다**, 별도 cycle 대상.

## 1. Summary

**2026-09-01 20260901T1153-side-panel-exclusive — 우측 사이드 패널은 한 번에 하나만** (Minor §12.3 — frontend-only: `static/app/side-panels.js`(신규) + `static/app.js` + `static/app/profile.js` + `static/app/composer.js`. 백엔드·스키마·RBAC·엔드포인트 변경 **0**). **사용자 요청**: "사이드바는 하나만 열릴 수 있도록 구성해주세요. (실행 단계, 첨부파일, 유저 프로필 등)". **결함**: 우측 오버레이 패널 3종(`#attachSidePanel` z180 · `#stepSidePanel` z181 · `#profileDrawer` z200 + backdrop z195)이 `position: fixed; right:0` 로 **같은 자리**를 쓰면서 서로를 모른 채 각자 `hidden` 만 벗겼다. main 빌드 실측: 첨부 → 단계 → 프로필 순으로 열면 **셋 다 OPEN** 이고 화면에는 위의 하나만 보인다 — 아래 패널은 «열린 채 가려져» 닫기 버튼·리사이즈 핸들까지 접근 불가가 된다. **조치**: 의존성 0 인 등록부 `app/side-panels.js` 를 choke point 로 두고 각 소유 모듈이 자기 close 를 등록(`registerSidePanel`), **모든 열기가 `openSidePanel(key, openFn)` 을 통과**한다(배타를 opener 가 기억하는 구조가 아니라 호출 누락이라는 실패 모드 자체가 없다). 숨은 패널은 `inert`/`aria-hidden`(+CSS `visibility:hidden` 폴백)으로 Tab·스크린리더에서도 빠지고, 배타로 자동 닫힌 첨부 패널은 **같은 대화에서 다시 열 때만** 목록 모드·스크롤이 복원된다. **등록부가 DOM 을 직접 감추지 않는 것이 설계의 핵심** — 실행 단계는 라이브 티커 정지가, 프로필은 backdrop 내림이 «닫기» 의 일부라 DOM 만 만지면 규칙이 두 벌이 되어 갈린다(하네스 C3·C4 가 그 두 실패를 각각 잠근다). 첨부는 흩어져 있던 열기 1·닫기 3 경로를 `openAttachSidePanel`/`closeAttachSidePanel` 로 모았다. **검증**: `make test` 전량 6466 outcome **0 FAIL**(ruff clean) · jsdom 행위 하네스 67 PASS(정본 함수 본문 실행, stub 금지) · **뮤테이션 20종 전건 KILL**(각 주입 적용을 `grep -c` 변화로 확인 — 자기충족 역검증 회피) · 구조 가드 pytest 9축(형태-무관 `hidden` 해제 위치 · 표식 강제 census · 우회 6축 · 등록 형태 · leaf 불변식 · CSS 폴백) · **PB-0008 실 Windows 브라우저** 격리 컨테이너 **16 step ok** + BEFORE 겹침 재현 캡처. **§18.8 적대 패널(ux·design) 3회 리뷰 + 2회 수정 라운드** — ①BLOCK×2(P1 6, 제품 결함) → ②BLOCK×2(P1 2, 제품 회귀 1) → ③ux CONCERN·design BLOCK×2(**제품 건전** 판정, 지적은 가드·문서 정확성 축) → 수정 완료. 사용자가 상한을 1회 연장했고, 3라운드 연속 «제품 동작 건전» 판정. 잔여는 REVIEW.md 「후속 과제」 5건(Esc · 대화별 모드 승격 · 단일 dock · 계산 가시성 술어 · active 분기 슬롯 클로버). **미검증(정직)**: 「프로필이 열린 상태에서 첨부 열기」는 backdrop 이 클릭을 먹어 실 브라우저로 도달 불가 — 방어적 계약이며 jsdom C4 가 담당한다.
**2026-09-01 POST-DEPLOY 실측 (말풍선 여닫이 제거)** — 배포 `786815f2`(web-a·web-b 동일 SHA, 엣지 `no upstreams available` **0건**, 자산 `?v=cd84170acd28`)에서 **부재 확인 4/4 PASS**. 서빙 `messages.js` (23,668 bytes)에 `renderMessageDetails`·`buildSqlNavigator`·`buildStepBlocks` 전부 부재 — `location.reload(true)` 후 스탬프 붙은 실 서빙 사본을 읽어 Chrome 모듈 캐시 축을 갈라냈다. 기준선과 **같은 대화**(`20260901030637-95dc8844`)에서 `.message-details` **1→0** · `.message-detail-block` 2→0 · `.step-detail-list` 1→0 · `.sql-navigator` 1→0. **대체 표시면은 수치까지 그대로**다 — 「단계 보기」 버튼 `[77, 2, 2]` 불변, 클릭 시 패널 배지 「77단계」(카드 37 + 내부 동작 40 = 77), 카드 결과셋 토글 37개가 `hidden true→false` 로 동작. 이 «77» 이 이 작업의 요지다 — 제거된 여닫이는 같은 답변에서 SQL 17건 + 비-SQL 일부만 보였고 패널은 77단계 전부를 소요시간·근거와 함께 보여준다. **제거 변경의 시각검증은 전·후 두 번이라야 성립한다**(「없다」만 보면 애초에 없던 것과 구별되지 않는다) — 기준선 fragment 와 이 fragment 가 그 쌍이다. **여전히 미검증**: 브리지 **진행 중** 화면의 입구 «없으면 생성»(개인 AI 러너 미연결로 진행 중 run 생성 불가 — 구조 단언까지만 잠김) · 구형 메시지(`steps` 없음) 표시면 소실의 라이브 실측(해당 형식 메시지를 찾지 못함, 소실 자체는 코드상 확정). 상세: `docs/test-runs.d/TASK-20260901T1430-remove-query-result-details-postdeploy.md`.
**2026-09-01 20260901T1330-remove-query-result-details — 말풍선 「▼ 쿼리 결과」 여닫이 제거** (Minor §12.3 — 프론트 표시면 제거. `static/app/messages.js`·`app.js`·`app/composer.js`·`css/chat.css` + 계약 테스트 3종 방향 전환. 백엔드·스키마·RBAC·엔드포인트 **0**). **사용자 요청**: "`▼ 쿼리 결과` 펼치기에 대한 UI는 더 이상 의미없는 구조로 확인됩니다. (이미 `단계 보기` 기능을 통해 사이드바에서 더 정확하고 의미있는 데이터를 조회 가능) 해당 UI를 정리해주세요." **「정리」가 다의어라 §12 로 승격해 결정을 받았다** — 고른 독해(블록 전체 삭제) vs 버린 독해(결과셋 범위만 제거)를 요청 문구만으로 가를 수 없었다. 함께 사라지는 것(**CSV 다운로드 링크 · 「전체 데이터 보기」** — 이 블록에만 있었고 「단계 보기」 패널에 대체재가 없다)을 **결정 전에** 고지하고 「제거 + CSV 이관」을 권장안으로 올렸으나, 사용자가 **「제거만」**을 선택했다(의식적 트레이드오프). **제거 범위는 조립 경로 전체** — `renderMessageDetails`·`buildStepBlocks`·`bubbleVisibleSteps`·`buildSqlNavigator`·`buildSqlStepPanel`·`loadFullCsvIntoTable`·`appendDetailBlock`·`extractFirstTableRef`·`formatSqlForDisplay` + 생산자가 사라진 CSS 12규칙. 표시면을 지우고 그것을 만들던 함수를 남기면 다음 사람이 그 자리를 살아 있는 것으로 읽는다. 남긴 것은 **다른 소비처가 있는 것만**(`buildResultTable`·`parseCsv`·`.sql-block` = 본문 인라인 경로, `.sql-toggle-btn`·`.sql-result-toggle-wrap` = 「단계 보기」 패널 카드). **이번 변경의 실질은 호출부가 no-op 이 되지 않게 한 것**이다 — 브리지 진행 표시(`_renderBridgeSteps`)가 이 여닫이를 통째로 다시 그리는 방식이었고, 그냥 지우면 진행 중 말풍선에 단계로 들어갈 입구가 **하나도 남지 않는다**(placeholder 말풍선은 `meta.steps` 없이 그려져 app.js 가 「단계 보기」 버튼을 붙이지 못한다). 이제 그 함수는 사이드 패널을 갱신하고 말풍선 버튼을 **없으면 만든다**. **계약 테스트는 방향을 뒤집었다** — 종전 단언들은 이 여닫이를 *다듬는* 계약(스크롤 대상·범위 분리·페이징 죽은코드)을 잠그고 있었으므로, 잠글 대상이 아니라 **되살아나면 안 되는 것**으로 재정의했다. **검증**: 컨테이너 pytest 9스위트 전건 PASS(rc=0) · `node --check` ESM 3파일 PASS · **PRE-DEPLOY 기준선 실측(PB-0008)** — 라이브 대화 `20260901030637-95dc8844` 에서 제거 대상 4요소 직접 관측(`.message-details` summary=「쿼리 결과」 · 블록 `["단계","쿼리 결과"]` · `.step-detail-list` 1 · 네비게이터 「쿼리 1/17」·결과 표 14). 「제거했다」를 「원래 없었다」와 구별하려면 **전·후 두 번**이라야 하고 이것이 그 절반이다. **미수행**: POST-DEPLOY 부재 확인 4항목(사전 열거) · 브리지 진행 중 입구 생성의 라이브 관측(개인 AI 러너 미연결 — `내 AI가 실행 중이 아닙니다` 배너 실측, 구조 단언으로만 잠김). **범위 밖(명시)**: 공유 뷰(`share.js`) — 그쪽엔 「단계 보기」 패널이 없어 대체재가 없다.

**2026-09-01 POST-DEPLOY 실측 (중단 보존 2 cycle)** — 배포 `b793e7ea`(엣지 무중단 0건)에서 **도달 4/4 PASS**: 서빙 `app.js?v=3c9d838b3ed0` 에 `_reloadForPreservedInterrupt`·`preserve_reasoning: true`·새 토스트 문구, `/api/ai/manifest`·`/api/ai/openapi.json` 에 파라미터 + `"default": true`. **중단 왕복 12항목은 미수행** — `#sendBtn` 이 `is-access-blocked`("내 AI 가 연결되어 있지 않습니다")라 질문 전송 자체가 차단되고, 라이브가 feature-0043 전환 모드라 답변을 만드는 개인 AI 러너가 0개이며 재기동에는 사람이 발급하는 `mat_` 토큰이 필요하다. **미검증 축을 숨기지 않는다**: 계약(실호출 40건)·뮤테이션(4종 KILL)·도달(4/4)이 통과했다는 사실이 "사용자가 그 화면을 본다" 를 대신하지 않는다. 상세: `docs/test-runs.d/TASK-20260901T121000-interrupt-preserve-postdeploy.md`.

**2026-09-01 20260901T0315-interrupt-preserve-bridge — 중단 보존을 «사용자가 실제로 타는 경로»(브리지)까지** (Minor §12.3 — feature-0003 `routers/conversations.py` + feature-0002 `agent_core.py`(`header` 파라미터) + 신규 12건. 스키마·RBAC·엔드포인트 **0**, 비파괴 텍스트 추가). **앞 cycle 의 미완 부분을 잇는다.** `REQ-20260901T020746` 을 배포하고 나서야 스모크 로그가 드러냈다 — 라이브는 `feature-0043` 전환 모드(`[llm-gate] 서버 계정 LLM 호출 차단 … 추론은 사용자 개인 AI 런타임이 수행`)라 **사용자가 실제로 누르는 '중단' 은 앞 cycle 이 고친 서버 run 경로를 지나가지 않는다**. 앞 cycle 이 브리지를 "미커버(구조적으로 부분 추론 없음)" 로 적은 것은 절반만 맞았다 — 부분 추론이 없다는 것은 사실이나, 개인 AI 가 **우리 도구를 부른 내역**은 우리 안에 있다(`_record_bridge_step` 이 인자·사유까지 `agent_runtime.steps` 에 적재). **브리지 3축 전수 확인**: 화면·이력(취소 안내 말풍선 교체)과 단계 접이식(말풍선이 `run_id = task_id` 각인 유지)은 **이미 성립**했고, **다음 요청의 맥락만** 비어 있었다 — 브리지가 개인 AI 에게 넘기는 대화 맥락(`_recent_conversation_context`)은 표시 store 의 **content 텍스트만** 읽고 steps·meta 를 보지 않는다. 그래서 중단 뒤 "아까 그거 이어서" 라고 물어도 개인 AI 는 직전에 무엇을 조사했는지 몰랐다. **조치**: `_bridge_progress_tail` 이 그 task 의 steps 를 `agent_core._build_interrupted_note(header=…)` 로 렌더해 취소 안내 뒤에 **task 루프 안에서** 덧붙인다(루프 밖이면 여러 대기 질문 동시 취소 시 남의 조사가 내 질문 아래 붙는다). 머리말이 **미완 라벨** 역할을 한다. **빌더를 공유한 이유**: 같은 사실을 두 벌로 만들면 두 경로의 화면이 갈리고 약한 쪽이 사용자가 보는 진실이 된다. **degrade**: 조회 실패·단계 부재는 모두 종전 안내 그대로 — 단계 기록은 취소의 조건이 아니며, 예외를 올리면 이미 확정된 취소의 화면 표시조차 사라진다. 검증: `make test` 전건 green · 신규 12 PASS · 뮤테이션 1종 KILL(꼬리 미부착 → 배선 테스트 red). **미커버(구조적)**: 개인 AI 의 부분 추론 자체(러너 쪽) · 회수 store 는 의도적으로 미사용(시스템 안내를 LLM turn 으로 위조하지 않는 기존 설계이며, 브리지 맥락 조립이 표시 store 를 읽으므로 승계는 성립).

**2026-09-01 20260901T0207-interrupt-context-preserve — 중단(interrupt)이 추론·맥락·단계를 버리지 않는다** (Minor §12.3 — feature-0003 `routers/{conversations,ai_discovery}.py` + `static/app.js`, feature-0002 `agent_core.py`, 신규 테스트 2종 28건. 스키마·마이그레이션·RBAC·신규 엔드포인트 **0**, 비파괴 메시지 1건 추가·가역). **사용자 요청**: "대화 중 assistant에게 요청했던 작업을 중단(interrupt) 하더라도 추론했던 내용, 맥락, 단계가 손실되지는 않도록 구성해주세요." **근본원인은 계산이 아니라 «기본값의 방향»**이었다 — `preserve_reasoning` 보존 축은 이미 있었고 진행 중 새 발화로 끼어드는 경로만 그것을 켰다. 명시 '중단' 버튼은 플래그를 보내지 않았고 `/api/cancel` 이 `bool(data.get(...))` 로 미지정을 폐기로 접어, 그 경로에서 ① 화면(진행 카드 삭제 + 앵커 메시지 없음) ② 이력 ③ 다음 요청의 LLM 맥락(`core_messages` 미기록)이 **동시에** 비었다. **두 번째 구멍**: 보존 본문의 근거인 `steps` 는 도구 step 만 담아, 사용자가 중단을 누르는 전형적 시점(도구 호출 전 "추론 중")에는 보존 경로에 태워도 남길 문장이 0 이었다. **조치 4** — (a) `/api/cancel` 기본값을 **보존**으로 전환하되 명시 falsy 만 폐기(기본값을 프런트가 아니라 **서버**에 둔 이유: 이 엔드포인트는 외부 AI 도구 표면에도 공개돼 있어 프런트만 고치면 계약이 호출자에 따라 갈린다), (b) 보존 본문을 **미완 라벨 + 진행 단계 + 근거** 3구획으로(`_build_interrupted_note`), (c) 도구 호출 전 중단을 **활동 trail** 폴백으로 커버, (d) 프런트가 뒤늦게 쓰이는 보존분을 **유한 3회**(1.5s·4s·10s, `preserveScroll`) 재확인해 새로고침 없이 올린다. **가장 중요한 판단 2가지**: ① **미완 라벨은 meta 가 아니라 본문에** — 보존분은 recall 을 타고 다음 run 의 입력이 되는데 모델이 보는 것은 본문 텍스트뿐이고 `interrupted: true` meta 는 화면 전용이다. 라벨이 없으면 중간 기록이 확정 결론으로 읽혀, 방향을 바꾸려 중단한 사용자에게 폐기된 가설 위에서 답을 잇는다(사용자 결정의 단서 — "방향이 틀려서 재요청한 경우도 LLM이 충분히 판단할 수 있는 구조로"). ② **단계 UI 는 새 저장 경로 없이 앵커 1건으로 복구** — 취소해도 `agent_runtime.steps` 행은 남고(`_purge_run_steps` 호출부 0) history 조립부가 assistant 메시지마다 그 run 의 steps 를 붙이므로, 빠져 있던 것은 데이터가 아니라 **앵커가 될 메시지**였다(별도 스냅샷을 만들면 같은 사실의 두 번째 사본이 생겨 어긋날 표면만 는다). 검증: `make test` 전건 green · 신규 28 PASS(엔드포인트 실호출 + 본문 실호출 + 배선) · **뮤테이션 3종 KILL**(결함 원형 복원 M1 포함). §18.8 채널 = codex 3회 시도 실패 후 사용자 승인 carve-out(`[SKIPPED:upstream-tool-carveout]`). **미커버**: 브리지(개인 AI) 축은 러너가 최종 답변만 제출해 부분 추론이 구조적으로 없음(현행 취소 안내 말풍선이 이미 화면 보존을 충족) · 재개(이어서 진행) 버튼은 사용자 결정으로 별도 cycle · **Windows-browser 실측은 POST-DEPLOY 이월**(중단 UX 는 진행 중 run 이 실재해야 관측 가능 — 측정 항목 9건을 `test-runs.d/TASK-20260901T020746-interrupt-context-preserve.md` 에 사전 열거).

**2026-08-31 20260831T193000-attach-lineage-visibility — 첨부 «계보 비교 가시성» 재설계** (Minor §12.3 — feature-0003 프론트 `static/app/composer.js` + `static/app/attach-diff.js` + `static/css/chat.css` + 신규 회귀 18건. 백엔드·스키마·RBAC·엔드포인트·payload 변경 **0**). **사용자 제보(반복 수렴)**: "사용자 및 AI가 수정한 첨부파일 간 계보가 비교하기에 가시성이 떨어진다 … 디자인적 관점으로 … 많은 사용자가 공유하는 첨부파일 간 버전관리에서 모범적으로." **선행 cycle 이 이미 계보를 화면에 올렸는데도 불만이 재수렴한 이유**는 «존재를 말하는 것»과 «견주기 쉬운 것»이 다른 문제였기 때문이다 — REQ-20260828 은 정보를 *추가*했고 이번 제보는 *구조가 안 보인다*였다. **웹 리서치로 원칙을 먼저 세웠다**(NN/g 공통영역·시각위계 / GitKraken 커밋그래프 레인·change gauge / Google Docs 작성자 색축 / Figma 브랜치 리뷰 = 1급 액션). 공통 관찰: 성숙한 도구는 **컨테이너가 artifact 이름을 말하고 행은 갈래를 가르는 정보만 싣는다**. 우리 화면은 정반대로 행마다 같은 파일명을 되풀이하며 «누구의 갈래인가»를 서수(`계보 1/2`) 뒤에 감췄다. **결함 7종 진단** — ① 평면 형제 행(같은 파일의 갈래와 무관한 파일이 시각적 동급) ② 분기가 산문·툴팁에만(보려면 읽어야 함) ③ 「계보」가 네 곳에서 다른 뜻으로 반복 ④ 비교 진입 2단계(펼쳐야 버튼) ⑤ 작성 주체 색축 미성립 ⑥ 변경 규모 신호 부재 ⑦ 서수는 정체성이 아님. **조치**: 같은 파일명의 계보를 **공통영역 카드**로 감싸고(NN/g: enclosure 가 근접성을 압도 — 간격만으로는 전달되지 않으며 이미 그 상태가 제보의 원인이었다), 그룹 본문에 **레일 + elbow + 분기 들여쓰기**로 분기를 *그리고*, 카드 머리에 **그룹 레벨 `⇄ 계보 비교`**(클릭 1회로 계보 축 착지 — `openAttachmentDiffModal` 에 `preselect.axis` 추가)를 1급 액션으로 올렸다. 서수 `계보 1/2` → 정체성 `사용자 계보` / `⤷ AI 계보`(서수는 title 로 보존), 첫 계보 대비 **크기 델타 칩**(`+8KB`)으로 규모를 선행 노출하되 **«내용 차이»라고 말하지 않는다**(같은 크기의 전혀 다른 파일에서 화면이 거짓말하게 된다 — 실 내용 차이는 모달의 `+182/−21` 이 담당). 그룹 안에서는 **위계를 역전**했다 — 파일명은 머리가 이미 말했으므로 낮추고(크기·굵기·색) 계보 칩에 1순위를 넘기되, 클릭 대상(원문 보기)·접근성 이름은 파일명 그대로 유지해 a11y 를 깎지 않았다. **자기 결함 1건 — 실측이 잡았다**: 색축을 넣었는데 성립하지 않았다. 인접 규칙이 쓰던 `var(--muted)` 가 이 저장소에 **정의되지 않은 토큰**이라 조용히 무시됐고 사용자 계보 칩이 본문색 그대로 렌더됐다(문법상 완전히 정상이라 CSS 를 읽는 것만으로는 드러나지 않는다). 라이브 `getComputedStyle` 이 `rgb(38,37,30)` 을 반환해 포착 → `--text-muted` 로 교정 후 재실측(중립 `rgb(128,125,114)` / AI `rgb(37,99,235)`), 회귀로 잠갔다 — 「방어를 넣었다 ≠ 방어가 성립한다」의 CSS 판. **검증**: pytest `feature-0003` + `feature-0002` 전건 PASS(신규 `test_attach_lineage_group_ui.py` 18건 — «만들고 안 씀» 배선 사각을 잡는 단언 포함) · `node --check` ESM PASS · **PB-0008 실 Windows 브라우저**(§13.2.9 격리 컨테이너 `web-verify-lineage` + asset stamp 재주입 — 공유 트리·라이브 web-a/b 무수정) 구조(그룹 2 · in-group 4/4 · is-branch 2) · 픽셀(확대 캡처로 레일·elbow·240px wrap 판독) · computed(색축) · **인터랙션 2 surface 개별 실행**(그룹 머리 / 버전 박스 — 둘 다 축 `time` · 제목 「계보 비교」 · `+182/−21`). **첫 라이브 시도의 `groups: 0` 을 «미구현»으로 읽지 않고 캐시 축을 갈라낸 것**이 이 검증의 전제다(서버 파일이 신버전이어도 Chrome 모듈 캐시가 구버전을 실행하는 기지 함정). **미수행**: POST-DEPLOY 재확인(배포 후 별도 Run) · 실 diff 통계의 목록 노출(계보당 API 왕복 비용 — 크기 델타로 대체하고 경계를 문구로 밝힘).

## 1. Summary

**2026-08-31 20260831T1445-conv-last-activity-updatedat — "최근 갱신" 이 첫 턴 시각에 고정되던 결함** (Minor §12.3 — `feature-0002/src/modules/runtime_backend.py` + `feature-0003/src/routers/_conv_store.py` + 신규 테스트 2종. 스키마·마이그레이션·RBAC·엔드포인트·프론트 **0**). **사용자 제보**: "요청을 전송하여 대화가 갱신되었는데도 최근 갱신 일자가 첫 대화를 작성했던 부분에서 변경되지 않은 이슈" (대화 `dk_game_integrate 랭킹 자동화 프로시저 명명 제안`). **라이브 실측으로 재현 확정** — 대화 `20260828073505-be34624d` 의 `core_conversations.updated_at` 이 08-28 16:38:07 에 고정된 채 마지막 메시지는 **08-31 10:54:39**(2일 18시간 16분 어긋남). 전수 측정 355 대화 중 **19건** 동일 상태이며 전부 2턴 이상 대화다(단일 턴은 생성=마지막이라 증상이 드러나지 않았다). **근본원인은 활동 시각을 올리는 write 가 «자동 제목 부여» 경로에만 있었던 것**이다 — `_conv_update_topic_if_auto` 의 `SET topic=…, updated_at=now()` 가 유일한 전진 지점이고 그 UPDATE 는 제목이 placeholder 일 때만 행을 잡으므로, 첫 턴에 제목이 확정된 뒤로는 후속 턴이 쌓여도 컬럼이 움직이지 않았다. 메시지 저장 경로에는 갱신이 아예 없었다. **왜 이 대화에서만 눈에 띄었는가 — 표시 축이 하나뿐이었다**: 부제는 `last_activity_effective_at || last_activity_at` 순으로 읽고 앞의 값은 KV `last_status_at` 파생이라, 서버 LLM 경로는 KV 가 있어 증상이 가려졌고 KV 를 쓰지 않는 **브리지(개인 AI 연결)** 경로는 폴백이 비어 고정값이 그대로 노출됐다(그 대화 KV 키 실측 0건). 같은 컬럼을 읽는 목록 정렬(`ORDER BY c.updated_at DESC`)도 첫 턴 시각 기준이라 활발한 대화가 상단으로 오지 못하는 2차 증상이 함께 있었다. **조치 2겹** — ① 표시 store 쓰기 choke-point(`PgRuntimeBackend.save_memory_message`, 미분기·브랜치 두 경로)에서 `touch_conversation` 으로 활동 시각을 전진시킨다. 축을 표시 store 로 잡은 이유는 회수 store 가 tool turn 까지 담아 한 run 에 수십 건이 쌓이는 반면 표시 store 는 화면에 뜨는 단위라 사용자가 읽는 "최근 갱신" 의 의미와 겹치기 때문이고, `_PG_UPSERT_CONVERSATION` 을 재사용하지 않은 이유는 그 UPSERT 가 행 부재 시 INSERT 하고 COALESCE 로 다른 컬럼을 덮어 topic 없는 유령 대화를 만들기 때문이다. touch 실패는 흡수한다 — 메시지는 이미 별개 커밋으로 저장됐고, 예외를 올리면 브리지 경로가 **저장 성공한 질문을 취소**한다. ② 표시 축을 `_effective_activity_at` 으로 **KV·행 max** 로 바꿨다(우선순위 아님 — 서버 LLM 으로 시작해 브리지로 이어간 대화는 KV 가 첫 run 시각에 멈춘 채 남으므로 KV 를 무조건 우선하면 같은 결함이 되살아난다). tz 를 모르는 값은 비교에서 제외해 MySQL naive DATETIME 이 KST 환경에서 9시간 미래로 max 를 점거하는 입구를 막았다(`_iso_or_empty` 가 봉인한 CHG-20260527-0001 과 동류). **검증**: 신규 테스트 2종 **20 PASS** + **뮤테이션 3종 KILL**(touch 호출 제거 → 2건 FAIL, 표시 축 되돌림 → 구조 단언 FAIL) + 전량 회귀 실패 0. **POST-DEPLOY**: 라이브 배포 `b35fa376`(web-a/b·워커 동일 SHA · 엣지 `no upstreams available` **0건** · surge 잔존 0 · 대화 스모크 PASS) → 기존 **19건 백필**(마지막 메시지 시각으로, 잔여 drift 0, 백업 대비 19/19 일치) → 배포본 안에서 표면 값 실측(지목 대화의 프런트 수신 값 `2026-08-31T01:54:39+00:00` = KST 10:54:39 = 마지막 메시지 시각). **백필 중 사후 발견 — 1차 시도는 틀렸고 즉시 정정했다**: `core_conversations` 에 `trg_core_conv_updated_at`(BEFORE UPDATE → `set_updated_at()`, 무조건 `now()`)이 걸려 있어 과거 시각으로의 UPDATE 가 실행 시각으로 덮였다(19행이 15:12:48 로 밀림). `SET LOCAL session_replication_role='replica'` 로 트리거를 우회해 정정했고 정본 절차를 feature-0002 MODIFY 에 남겼다. 이 트리거의 존재는 진단을 반증하지 않는다 — 트리거는 그 테이블을 UPDATE 할 때만 발동하고 메시지 INSERT 는 그 테이블을 건드리지 않으므로, 자동 제목 부여 외에 발동할 계기 자체가 없었다. **미수행**: PB-0008 육안 확인(프론트 자산 변경 0 → check #13 skip 판정, 지목 대화가 사용자 소유라 admin 세션으로 같은 화면 도달 불가 — 최종 육안은 사용자 화면에 위임).

## 1. Summary

**2026-08-25 20260825T1030-ctxmenu-order-parity — 폴더·대화 우클릭 메뉴 순서 정합** (Minor §12.3 — feature-0003 프론트 `static/app/sidebar.js` 항목 순서 4줄 + `static/app.js` 주석 + 하네스. 백엔드·RBAC·스키마·엔드포인트·동작 배선 **0**). **사용자 요청**: "'이름 변경' 기능에 대한 순서가 대화/폴더의 우클릭 구성에서 각각 달라 UX가 부정합하여 개선이 필요합니다." **실측해 보니 어긋난 곳은 두 군데였다** — 폴더 `하위 폴더 추가 · **이름 변경** · **설정** · 최상위로 꺼내기` vs 대화 `**이름 변경** · 공유 · 이동 · **설정**`. 공통 항목 `이름 변경`(2번째↔1번째)과 `설정`(3번째 중간↔마지막)이 모두 자리가 달라, 같은 목록에서 같은 조작을 하는데 대상 종류에 따라 커서를 옮길 위치가 바뀌었다(직전 cycle 이 대화에 '이름 변경' 을 추가하며 드러난 비대칭). **조치**: 공통 규칙 `[이름 변경] → [고유 액션] → [이동 류] → [설정]` 을 양쪽에 적용 — 공통 항목을 **양쪽 끝에 고정**(첫=이름 변경 / 끝=설정)하고 그 사이에만 각자의 고유 액션을 둔다. 폴더 = `이름 변경 · 하위 폴더 추가 · 최상위로 꺼내기 · 설정`, 대화 = `이름 변경 · 공유 · 이동 · 설정`(이미 규칙과 일치해 무변경). '이름 변경' 한 항목만 옮기지 않은 이유는 같은 성격의 부정합(`설정`)이 남아 다음 지적을 부르기 때문이다. **폴더를 대화에 맞춘 근거**: '이름 변경' 은 가장 잦은 단일 조작이라 첫 자리, '설정' 은 하위 팝업을 여는 무거운 항목이라 끝자리가 관례이며, 대화가 이미 그 형태라 변경 표면이 4줄로 작다. **검증**: 하네스 §9b 신설 — 두 `buildItems` 를 **실제 실행**해 라벨 순서를 수집하고 각 메뉴 순서·공통 항목 첫/끝 고정·조건부 항목 3케이스(최상위 폴더 · 깊이 상한 · 폴더 권한 없는 대화)를 단정(73 → **80 PASS**), **뮤테이션 2종 KILL**(구 순서 복원 · 설정 중간 배치), 기존 사이드바 하네스 5종 회귀 0. **PB-0008 실측**(라이브 이미지 + 변경 static bind-mount, 실제 우클릭으로 렌더된 항목 판독): 하위 폴더 4항목 · 최상위 폴더 3항목 · 대화 4항목 전부 규칙 준수. **잔류물**: 검증용 폴더 2개 생성 후 삭제(200/404-cascade). **미수행**: 각 항목의 동작 재검증(배선 무변경 — 직전 cycle 에서 실측), 키보드 내비게이션 순서(DOM 순서와 동일).

## 1. Summary

**2026-08-24 20260824T1730-sidebar-rename-focus — 이름 변경이 끝나기 전에 확정되던 오확정 봉인 + 대화 '이름 변경' 메뉴** (Minor §12.3 — feature-0003 프론트 `static/app/sidebar.js` · `static/app.js` · `static/css/shell.css` + 신규 하네스·계측기. 백엔드·라우터·RBAC·스키마·엔드포인트 **0**). **사용자 요청**: ① "명칭을 변경하고 있을 때 아직 명칭 변경이 완료되지 않았는데도 포커스를 잃어버려 의도치 않은 명칭으로 설정되는 이슈 … 사용자의 조작이 아닌, DQA 내 별도의 작업으로 인해 이러한 이슈가 나타나는지 검토 및 수정" ② "폴더와 같이 대화 또한 우클릭 목록 내 `이름 변경` 항목을 추가". **사용자 가설은 사실이었다**: 좌측 목록을 사용자 조작 없이 다시 그리는 경로가 3종 실재한다 — 주기 unread 배지 동기화(`_maybeSyncConversationListUnread`, **7초**) · 대화 전환 후 catchup(`_scheduleSidebarCatchup`, 1.2초) · AI 응답 진행 중 상태 갱신(`app/composer.js` 다수). `_renderConversationListDom` 이 `innerHTML=""` 로 **전량 재구성**하므로 편집 중이던 `<input>` 이 떨어져 나가고, 종전 핸들러는 그 detach 로 발생한 `blur` 를 곧바로 확정으로 처리했다(입력 중 문자열이 그대로 저장). 한글 IME 조합 중 blur·조합 확정 Enter 도 같은 경로로 잘린 이름을 저장시켰다. "가끔" 의 정체는 **편집 시간이 재렌더 주기와 겹칠 때**다. **조치는 3겹** — ③ **무시**: 확정 규칙을 폴더·대화 공용 빌더 `_buildInlineRenameInput` 한 곳으로 모으고 `_inlineRenameDetaching`(렌더 구간) · `!isConnected`(DOM 이탈) · IME 조합 중 blur 를 확정에서 제외(Enter 는 `isComposing`/`keyCode 229` 필터). ① **억제**: 편집 중 주기 동기화 skip(throttle 갱신 **전** 반환 → 편집 종료 즉시 재개) + catchup 재예약. ② **보존**: 억제할 수 없는 경로를 위해 렌더를 capture→렌더→restore 로 감싸 값·커서·포커스를 되살리되 **포커스는 원래 갖고 있었을 때만**(다른 입력창에서 타이핑 중인 사용자에게서 뺏지 않는다). **요청 ②**: 대화 `···`/우클릭 메뉴 **첫 항목**에 `이름 변경` 추가(순서 `이름 변경 · 공유 · 이동 · 설정`), 선택 시 폴더와 동일하게 **모달 없이 그 자리에서** 인라인 편집. 서버 경로는 설정 팝업과 같은 `PATCH /api/conversations/{cid}/title`, 권한은 추상 action `conversation.rename`(§16.7 G6 무음 fall-through 회피) + 확정 시 `canRenameConversation` 2차 검사로 **권한 없으면 요청 자체가 나가지 않는다**. 편집 중 행은 `<button>` → `<div class="conv-item is-renaming">`(interactive content 중첩 회피, `data-conversation-id` 유지로 직전 cycle 의 FLIP 재배치 트윈과 정합). **§18.8 codex 적대 리뷰가 [P1] 1 · [P2] 3 을 추가로 잡았고 전건 흡수**: ① [P1] **IME 조합 세션은 값 복사로 보존되지 않는다**(조합은 노드에 묶인 세션이라 재구성으로 끊기고, 그 뒤 Enter 가 미완성 문자열을 정상 확정 처리) → 조합 중에는 **재구성 자체를 보류**하고 `compositionend` 에서 flush(라이브 실측: 조합 중 재렌더 2회에도 `same_node: true`). ② [P2] 조합 중 blur 를 무시만 하면 결론이 나지 않아 편집이 영구히 열린다 → blur 를 **보류**하고 `compositionend` 가 확정. ③ [P2] 대상 행이 사라진 **고아 편집 세션**이 억제를 영구화 → 렌더 후 세션 회수 + 억제에 **60초 상한**. ④ [P2] PATCH 성공 후 **재조회 실패를 "변경 실패" 로 보고**하던 거짓 보고 → 저장/재조회 분리(폴더 경로 동반 정정). **검증**: 전용 하네스 `tests/verify_sidebar_inline_rename.mjs` **73 PASS**(초안 51 → 리뷰 반영 후 73)(DOM 스텁 위에서 실제 함수 본문 실행) + **G11-b 결함 주입 실증**(가드 3종 제거 시 9 FAIL, 첫 FAIL 이 사용자 보고 증상과 동일한 미완성 이름 PATCH) + **뮤테이션 8종 전건 KILL** + 기존 사이드바 하네스 7종 회귀 0(구조 변경으로 깨진 텍스트 단언 2건은 계약을 유지한 채 갱신). **PB-0008 실측**(실 Windows Chrome, 라이브 web 이미지 + 변경 static bind-mount 컨테이너 `https://localhost:18099`, 계측기 `tests/pb0008_sidebar_rename_focus.py`): 편집 중 재렌더 2회에도 **PATCH 0건** + 값·커서·포커스 유지 · 편집 중 9초간 `/api/conversations` 폴링 **0건**(종료 후 재개 1건) · Enter 확정은 PATCH 1건으로 정상 · 대화 우클릭 메뉴 `["이름 변경","공유","이동","설정"]` 에서 선택 시 모달 0개 + 인라인 전환 · **CDP `Input.imeSetComposition` 으로 한글 조합 중 Enter+재렌더에도 PATCH 0건**. **잔류물**: 검증용 임시 폴더 5개 삭제(200), 대화 1건 제목 변경 후 원복(200) — 그 대화의 `updated_at` 만 갱신됨. **측정 정정**: 1차 실측의 "편집 종료 후 9초 폴링 1건" 은 억제 해제의 근거가 못 됐다 — **편집 없는 기준선도 16초에 1건**이었다. 창을 16초로 늘려 "편집 중 0건 → 확정 후 1건(기준선 동일)" 로 다시 측정했다. **미검증**: 다중 사용자 동시 편집, 한글 조합 종료 시 값 유지(프로브가 조합을 비우며 종료해 관측 불가 — 값·커서 복원은 비-IME 경로로 확인), Chromium 외 브라우저의 detach-blur 동작(봉인은 브라우저 동작에 의존하지 않도록 2중 가드로 설계).

## 1. Summary

**2026-08-24 20260824T1644-sidebar-reorder-anim — 좌측 대화목록 명칭 변경 시 재배치를 부드러운 전환으로** (Minor §12.3 — feature-0003 프론트 `static/app/sidebar.js` · `static/app.js` · `static/css/shell.css`. 백엔드·스키마·권한·엔드포인트·**정렬 규칙 변경 0**). **사용자 요청**: "작업화면 좌측 대화목록 내 요소들의 명칭을 수정할 때 정렬 기준에 따라 순식간에 재배치되어 사용자의 시야에서 사라지는 이슈 … 부드러운 애니메이션으로 재배치되도록". **원인은 두 경로였고 둘 다 정렬 자체는 정상이다**: ① 대화 제목 — `PATCH /api/conversations/{id}/title` 이 `_conv_update_topic` 을 통해 `updated_at = now()` 를 갱신하고 목록 정렬 키가 `c.updated_at AS last_activity_at` desc 라 그 대화가 최상단·'오늘' 그룹으로 옮겨간다. ② 폴더 이름 — 폴더 정렬이 `sort_order` → `name` localeCompare 라 가나다 위치가 바뀐다. 공통 증폭 요인은 `renderConversationList` 가 `innerHTML=""` 후 **전량 재구성**한다는 것 — 요소가 교체되므로 CSS transition 이 원리적으로 걸리지 않아, 재배치가 항상 **전환 없는 순간이동**이었다. **조치**: 정렬을 건드리지 않고 전환만 보이게 한다. FLIP(재구성 직전 좌표 스냅샷 → 재구성 → 새 좌표와의 차이만큼 역이동 후 `transform` 트윈)을 코디네이터로 넣고, 렌더 함수는 wrapper(`renderConversationList`) + DOM 본체(`_renderConversationListDom`)로 갈랐다. 시야 유지는 3축 — 재구성으로 clamp 된 스크롤 복원 · 대상이 접힌 날짜 그룹/폴더로 옮겨갔으면 **조상만** 펼침(대상이 안 그려지면 전환할 것도 없다) · 대상이 스크롤 밖이면 시야로 끌어오되 그 보정을 **FLIP 측정 사이**에 넣어 "스크롤 점프 + 재배치" 가 한 번의 연속 이동으로 합쳐지게 했다. 접근성은 `_prefersReducedMotion`(OS 신호 + 인앱 '애니메이션 효과' 설정) **단일 게이트**를 공유하되, 트윈·강조만 끄고 **시야 유지는 유지**한다. 애니메이션은 명칭 변경이 예약한 **1회의 렌더**에만 적용되고(TTL 4초, 소비 즉시 비움) 예약 없는 렌더는 좌표 측정조차 하지 않아 기존 경로와 동일하다. **실측(PB-0008, 실 Windows Chrome + 미머지 자산 bind-mount 컨테이너)**: 6월 그룹 대화의 제목을 바꾸자 화면 y **442 → 233** 이동이 **19 프레임 트윈**(324~621ms)으로 이어졌고 강조는 1.1초 유지됐다(변경 전이라면 이 구간이 0 프레임). 폴더 경로도 트윈 확인. 계측기는 `tests/pb0008_sidebar_reorder_measure.py` 로 자산화했다 — 정지 스크린샷으로는 순간이동/트윈을 구분할 수 없어 **rAF 궤적**을 정본 증거로 둔다(창을 전면화하지 않으면 Chrome throttle 로 애니메이션이 아예 안 돌아 거짓 판정이 난다는 함정도 기록). **검증**: 전용 하네스 73 PASS + **뮤테이션 5종 전건 KILL**, 사이드바 관련 기존 하네스 5종(118건) 회귀 0, 컨테이너 `make test` 에서 본 변경 관련 실패 0(무관 1건은 main 에서도 동일 실패). **미검증**: 스크롤 밖 대상 추종은 검증 계정 목록이 한 화면에 들어와 라이브 재현 불가 — 하네스 좌표 계약으로만 잠갔다.

**2026-08-13 20260813T1600-graph-expand-perf — 그래프 뷰 '노드 펼침' 체감 지연 근본 개선** (Major §12.3 — feature-0003 `static/graph/{graph-renderer-pixi,graph-core,graph-ctxmenu}.js` 3모듈. 백엔드·스키마·권한·엔드포인트·마이그레이션 **0**, 표시 결과 **불변**). **사용자 요청**: "'그래프 뷰' 에서, 노드를 펼칠 때 체감될 정도로 느리게 펼쳐집니다. 성능적인 병목 이슈의 원인을 파악 후 개선해주세요." **추정하지 않고 먼저 귀속했다** — 실 Windows Chrome(자기 세션 전용 인스턴스)에 CDP `Profiler`(200µs) + `longtask` 옵서버 + 상태줄 `MutationObserver` 를 걸어, 693 노드 스키마에서 16-컬럼 테이블 1개를 펼치는 동작의 시간이 **어디로 가는지** 함수 단위로 갈랐다. 결과는 세 축이었다. **R1(지배항)** 오브젝트 풀 diff 의 `nodeSig` 가 `style` 을 통째로 직렬화해 **x/y 를 서명에 포함**한다 — 컬럼 하나를 펼치면 masonry 가 재균형돼 형제 수백 개가 이동하고, "서명이 달라졌으니 다른 요소" 로 판정돼 **전부 destroy→re-create** 됐다(`made 538` · `labelsCreated 524` · `drawMs 210ms`; 프로파일 상위가 `experimentalLetterSpacing`·GC 로, 비용의 정체는 **라벨 재생성**이었다). **R2** 더블클릭 판별용 340ms 타이머가 *모델 변경* 만 미루면 되는데 **네트워크까지 함께 미뤄**, 클릭 후 ~500ms 가 지나서야 컬럼 조회가 시작됐다 — 체감 시간의 3분의 1 이상이 아무 일도 하지 않는 대기였다. **R3** 배치-정렬 메모이즈(§73)의 위상 서명이 `nodes` 전량 해시인데 **컬럼도 그 Map 에 산다**(`label:"Column"`) — 메모이즈가 겨냥한 바로 그 조작(컬럼 펼침)이 매번 캐시를 날려 relOrder(barycenter 4-sweep)+simGroups 를 전 모델 재계산시켰다. 코드 주석은 "컬럼은 서명에서 자연 제외" 라고 **사실과 반대로** 적혀 있었고, 기존 테스트 T3 도 그 사실을 알면서 검증을 우회하고 있었다(주석에 그대로 남아 있었다) — 선언과 실제의 괴리가 성능 결함으로 굳은 사례다. **조치**: ① 위치를 뺀 `nodeShapeSig`/`comboShapeSig` 로 **"모양이 같으면 재배치, 다르면 재생성"** 으로 판정을 바꿨다(근거: `_drawNode`/`_drawCombo` 의 자식이 전부 로컬 좌표계라 위치는 컨테이너 `position.set` 하나로 끝난다 — 표시 결과 불변이 **구조적으로** 보장된다). 엣지는 destroy/new 대신 `_paintEdge` **in-place 재-path**(드래그 경로가 이미 쓰던 수단). ② 클릭 즉시 컬럼 GET 2건을 **선-fetch**(모델·카메라·상태 무접촉)하고 340ms 뒤 펼침이 그 promise 를 이어받는다 — 더블클릭이면 버려지고(GET 이라 부작용 0), 상세 조회도 **같은 promise 를 공유**해 **선재 중복 왕복 1건까지 제거**했다. ③ `_metaTopoSig` 에서 Column 제외 + 오기 주석 정정. **실측 개선(중앙값, 개선 전 n=4 vs 개선 후 n=3, 같은 브라우저·같은 좌표)**: 클릭→펼침 완료 **915ms → 556ms(−39%)** · 메인스레드 블로킹 **344ms → 133ms(−61%)**(최장 단일 longtask 365ms → 77ms) · pixi `drawMs` **210ms → 35ms(−83%)** · 오브젝트 재생성 **537 → 21(−96%)** · 라벨 재생성 **523 → 19(−96%)**. 접기 경로도 동형(`drawMs 14.2ms`). **개선본은 main 을 건드리지 않고 자기 worktree 로 빌드한 격리 preview 컨테이너**(§13.2.9, 공유 트리·공유 `.env` 무수정, 포트 18098)에서 측정한 뒤 회수했다. **§18.8.1 codex 적대검증 2라운드에서 P1(GATE) 1건 + P2 4건이 나왔고 전건 반영**했다 — 선-fetch 캐시가 모델 리셋에서 비워지지 않던 세대 오염(P1), 부분 펼침 테이블에서 소비자 없는 낭비 요청, 배열 `slice()` 만으로는 막히지 않는 **노드 객체 aliasing**(`ordinal` 제자리 변형), 검색 prune 경로 미커버, TTL 과다(20s→8s). **미수용 2건은 선재 결함으로 분류**해 원장에 남겼다(상세 조회의 세대 가드 부재 · 상세 backfill 과 펼침의 `/columns` 중복 — 둘 다 `main` 에 이미 있고 본 변경이 만든 경로가 아니다). **PB-0008 실 Windows 브라우저 PASS** — 같은 조작 후 렌더가 개선 전과 **육안 동일**(펼친 컬럼 16행·"−" 컨트롤·선택 링·masonry 좌표·미니맵까지; 차이는 상태줄 토스트 문구뿐), 드래그·접기·트윈 정상, `pageerror` **0건**. **세션 격리(§16.6 v3.44.0)**: 기본 포트에 붙었을 때 실제로 **다른 세션의 탭**이 잡히는 것을 관측해, 전용 CDP 포트·전용 프로파일로 자기 인스턴스를 새로 띄워 그 안에서만 조작했다. **검증 합계**: 헤드리스 graph 계열 **1,283 PASS / 0 FAIL** — 신규 `test_graph_expand_prefetch.js` 15(선-fetch 계약: 중복억제·promise 공유·소비·실패 흡수·리셋/prune 무효화·aliasing 차단) · `test_pixi_adapter.js` **T31 씬-diff 13 신규**(이동=재배치·모양변경=재생성·엣지 in-place) · `test_g6build_layoutmemo.js` **T7 6 신규**(컬럼 ingest 캐시 적중 + **적중==fresh 좌표 완전 동일** — 메모이즈가 stale 을 만들지 않음). **배포·POST-DEPLOY 검증 완료**: PR #1255 → main `16da577f` → `deploy-web-only` 무중단 롤링(web-a·web-b 동일 SHA, 엣지 `no upstreams available` **0건**, soak 통과). **라이브 재측정 n=3 이 격리 프리뷰 수치를 그대로 재현**했다 — 클릭→펼침 **544ms** · 블로킹 **134ms** · `drawMs` **32.8ms** · 재생성 **21** · 라벨 재생성 **19**(프리뷰 556/133/35/21/19). 서빙 자산에 `nodeShapeSig`·`_metaGraphPrefetchColumns`·`_metaColPrefetchClear` 배선 확인, 라이브 3테이블 펼침 렌더 정상, `pageerror` 0. **잔여**: ① **재배치 이동 트윈 360ms**(`MOVE_TWEEN_MS`, 2026-08-13 사용자 요청으로 도입)는 **의도된 연출이라 건드리지 않았다** — 다만 위 개선으로 처리 시간이 줄어 체감 시간에서 차지하는 비중이 커졌으므로(556ms 중 360ms 가 연출) 조정 여부는 사용자 판단 사항으로 표면화한다(§16.6 "증상-가림(애니 제거) 금지" 준수 — 성능으로 위장해 연출을 지우지 않는다). ② 스키마 **첫 펼침**(693 노드 신규 생성)은 재사용 여지가 없어 개선 대상이 아니며 실제로 변화가 없었다. ③ 측정 모집단은 **단일 모델·단일 컬럼 수·단일 줌**의 n=4/n=3 이다 — 모델 크기별 스케일링은 미측정. ④ 선재 결함 2건(위) 후속. ⑤ §18.8 은 subagent panel 이 아니라 codex + 헤드리스 + PB-0008 채널(상위 도구 제약 하 §18.8.2 carve-out, 미커버 축은 REVIEW 에 `[SKIPPED:tool-restricted:backend-load-measurement]` 명시). 정본 = TASK `20260813T1600-graph-expand-perf` · FUNCTION `REQ-20260813T160000-graph-expand-perf` AC-GXP-1~4 · MODIFY/REVIEW `…-graph-expand-perf` · TEST `docs/test-runs.d/REV-20260813T160000-graph-expand-perf.md`.

**2026-08-13 20260813T1550-rail-async-relayout — 우측 스크롤 ↔ 대화 뱃지 정합 (mermaid 지연 렌더)** (Minor §12.3 — feature-0003 `static/app.js` 단독 + 신규 실브라우저 하네스. 백엔드·라우터·RBAC·스키마·마이그레이션·신규 엔드포인트 **0**). **사용자 보고**: "채팅 화면의 우측 스크롤과 대화 뱃지의 영역이 정합하지 않는다 — 답변에 mermaid 형식이 나타날 경우 확인되는 것으로 추측된다." **추측은 정확했고, 원인은 타이밍이었다** — `layoutMessagePointRail()` 은 **호출 시점의** `messageLog.scrollHeight` 와 각 메시지 `getBoundingClientRect()` 로 막대의 `top%`/`height%` 를 인라인 지정하는데, 그 재호출 트리거는 다섯 곳(렌더 · prepend 보정 · 페이징 복원 · 창 확장 · `window.resize`)뿐이고 **콘텐츠 자체의 비동기 성장이 그 어디에도 없었다**. ```mermaid 는 `renderMermaidDiagrams()` 가 `Promise` 뒤에 SVG 를 넣으므로(mermaid-render.js), pending div(소스 텍스트 몇 줄) 기준으로 배치가 끝난 **뒤에** 높이가 수백 px 뛴다. 그 순간부터 스크롤바 thumb 은 실제 `scrollHeight` 를, rail 막대는 옛 비율을 따르므로 둘이 갈라진다. 같은 성장이 `renderMessages` 가 방금 맞춘 "맨 아래" 도 깨뜨려 최신 답변이 화면 밖으로 밀렸다 — 사용자가 본 것은 한 원인의 두 얼굴이다. **대조군이 이미 저장소 안에 있었다**: 공유 대화 뷰(`share.js setupSharePointRail`)는 주석까지 달아 이 축을 ResizeObserver 로 해결해 뒀고(bottom pin 도 동형), **메인 채팅 뷰만 미적용**이었다 — §16.7 **G8**(결정의 적용면 전수감사)의 전형이며, 따라서 이 cycle 은 새 설계가 아니라 **검증된 패턴의 적용면 확장**이다. **설계에서 load-bearing 한 결정 4건**: ① **관찰 대상은 `messageLog` 가 아니라 메시지 row** — `.messages` 는 flex 자식으로 `flex:1; min-height:0; overflow-y:auto` 라 콘텐츠가 늘어도 **자기 box 크기가 변하지 않아** ResizeObserver 가 발화하지 않는다(공유 뷰는 문서 스크롤이라 컨테이너 관찰로 충분했다 — 같은 결함 클래스, 다른 스크롤 컨텍스트). row(`[data-message-id]`)는 rail dot 이 참조하는 것과 **같은 element 집합**이다. ② **재고정 → 배치 순서** — 배치 계산이 `messageLogEl.scrollTop` 을 쓰므로 반대로 하면 같은 프레임에서 다시 어긋난다. ③ **`scroll` 은 pin 해제 트리거가 아니다** — pin 자신의 `scrollTop` 변경이 scroll 을 유발해 첫 성장에서 자가 해제된다(공유 뷰와 동일 판단). 대신 휠·터치·스크롤 의도 키 + **명시적 위치 조작 4경로**(rail/검색 점프 · prepend 보존 · 페이징 복원 · 창 확장)에서 해제한다 — 그 경로들은 모두 `renderMessages` 뒤에 위치를 다시 정하므로 해제하지 않으면 pin 이 그 결정을 되돌린다. ④ **무한 pin 금지** — settle 600ms(성장 신호마다 리셋) + ceiling 8s 강제 해제. **검증에서 하네스 자체가 한 번 무효였다**: 초판이 메시지 row 높이를 `min-height` 로 만들었더니 flex-shrink 가 아이템을 눌러 **라이브와 거동이 갈렸고**(이미지 성장이 12px 로만 관측), 실 콘텐츠(spacer) 기반으로 교체해 min-content 하한 = 라이브 동형으로 정정했다. "성장이 실제로 일어났는가" 를 T2a/T7a 로 **먼저 단정**해 vacuous PASS 를 차단했다. **codex 적대 리뷰가 [P1] 2 · [P2] 2 를 냈고 전건이 실제 결함이었다** — ① `_liveSyncTick` 의 "보던 위치 유지" 분기가 pin 해제 목록에서 빠져 있었다(적용면 누락) ② `#pendingAssistantBubble` 은 `data-message-id` 가 없어 관찰에서 빠지는데 progress step 이 쌓이며 `scrollHeight` 를 바꾸고, 게다가 progress.js 가 그 row 를 **`replaceChild` 로 교체**하므로 한 번 observe 해도 연결이 끊긴다 → pending 포함 + **`MutationObserver`(childList)로 교체 추적**(호출부마다 재관찰을 심는 점수정 대신 클래스 잠금, §16.7 G10) ③ 네이티브 스크롤바 클릭·드래그는 wheel/touch/key 를 안 만든다 → 컨테이너 `pointerdown` ④ ResizeObserver 부재 환경의 settle 600ms 가 첫 폴백 직후 만료 → `마지막 폴백+400ms` 로 연장(W8 로 불변식 잠금). **그중 ③의 반영 초판이 라이브 회귀를 만들었고, 그것을 잡은 것은 하네스가 아니라 PB-0008 이었다**: "pin 이 설정한 `scrollTop` 과 불일치 = 사용자 조작" 휴리스틱은 **뷰포트 위쪽** 성장 시 브라우저 스크롤 앵커링의 자동 조정을 사용자 조작으로 오판해 진입 맨-아래 고정을 깨뜨렸다(`gap=1,611px` — **수정 전과 같은 증상**). 그 시점 헤드리스 26축은 전건 통과였다 — 성장이 뷰포트 **아래쪽**에서만 일어나 경계를 건드리지 않았기 때문이고, 진짜 경계축은 "성장이 뷰포트 위인가 아래인가" 였다(§16.7 **G4** 의 정확한 실례). scroll 값 비교로는 *브라우저 자동 조정*과 *사용자 조작*을 원리적으로 구분할 수 없으므로 `pointerdown`(의미론적 "사용자가 눌렀다")으로 교체하고, **T11**(위쪽 성장 시 pin 유지)·**W5b**(폐기 휴리스틱 재발 방지)로 클래스를 잠갔다. **검증**: 신규 실브라우저 하네스 `verify_point_rail_async_relayout.py` **26/26 PASS**, `--baseline`(신설 배선 미주입)에서 **T2 178.2px · T4 맨아래 507px 밀림 · T7 이미지 97.96px** FAIL 로 결함이 재현되고 T8 재현 판정 OK(§16.7 **G4** 경계 양측 — load-bearing 증거) · 기존 프론트 검증 `verify_*.mjs` **57/57** · feature-0003 pytest 전건 PASS. **PB-0008 실 Chrome/150 PASS — 라이브 대조 실험**: §13.2.9 격리 프리뷰 **2개**(worktree 자산 :18097 / main 자산 :18096, 라이브 이미지·env 공유 → **자산만 다른 대조**)를 띄우고 **사용자가 이슈를 보고한 그 대화**(`20260812082809-e4263afd` "스키마 개선 BEFORE/AFTER 다이어그램" · mermaid SVG 3개 실렌더)에서 측정 — 뱃지↔메시지 구간 최대 오차 **86.58px → 0.11px**, 진입 시 맨-아래 gap **1,631px → 0px**, thumb 정합 불일치 0. 상호작용은 **자기 생성 탭**에서 실측(막대 60% 클릭 정밀 점프 4206→2629 · **실 휠 입력** 후 위치 유지 2629→1729 · 두 경우 모두 정합 유지 · JS 오류 0). **세션 격리 실사례(기록)**: 검증 도중 공유 CDP 의 `pages[0]` 이 **병렬 세션의 `/admin` 탭으로 바뀐 것을 관측**(read-only eval 1회 + `messageLog` 부재로 실패한 `scrollTop` 대입 1회 도달, 남의 화면 미변경) → `context.new_page()` 자기 탭으로 전환해 이후 전부 그 탭에서 수행하고 종료 시 그 탭만 닫았다(§16.6 v3.44.0 (a)(b)(c)). **잔여**: ① 배포 후 baked 자산 POST-DEPLOY 재실측(Run 3) ② `End` 키가 `#messageLog` 를 스크롤하지 않는 것은 앱 기존 동작으로 본 변경과 무관(관측만 기록) ③ §18.8 은 subagent panel 이 아니라 codex + 실측 채널(상위 도구 제약 하 §18.8.2 carve-out). 정본 = TASK `20260813T1550-rail-async-relayout` · FUNCTION `(rail-async-relayout, 2026-08-13)` AC-…-1~5 · MODIFY/REVIEW `…-rail-async-relayout` · TEST `docs/test-runs.d/20260813T155000-rail-async-relayout.md`.

**2026-08-13 20260813T1543-attach-list-name-sort — 첨부 목록을 파일명 순으로 정렬** (Minor §12.3 — feature-0003 `routers/conversations.py` + `static/release-notes-data.js` + 신규 pytest. 신규 엔드포인트·권한 코드·스키마·마이그레이션·프론트 정렬 코드 **0**). **사용자 요청**: "프로젝트 내 서비스에서, 첨부파일이 명칭 순으로 정렬되도록 구성해주세요." (첨부 패널 스크린샷 동반 — `…_08_`, `…_01_`, `…_02_` 가 업로드 순으로 흩어진 화면). **종전 순서는 `ORDER BY Id ASC`(업로드 순)** 라, 한 작업에서 만든 `01_`~`09_` 파일이 올린 차례대로 흩어져 이름을 알고도 목록을 훑어야 했다. **설계에서 load-bearing 한 결정 4건**: ① **정렬을 SQL 이 아니라 파이썬에** — 목록 read 경로가 MySQL 정본과 PG mirror 두 벌이라 `ORDER BY` 에 맡기면 두 엔진의 collation 차이가 곧 "경로에 따라 순서가 다름" 이 되고, `_02_` < `_10_` 수치 비교도 SQL 로는 자연스럽지 않다. 두 경로가 **합류한 뒤** 한 함수(`_natural_filename_key`)로 정렬한다. ② **휴지통은 정렬과 절단을 분리** — `LIMIT 200` 은 "무엇을 보여줄지" 의 경계라 이름순으로 바꾸면 이름이 앞선 오래된 삭제분이 200칸을 채워 **방금 지운 파일이 휴지통에서 사라진다**(복구 실패 체감). SQL 은 `DeletedAt DESC` 로 두고 표시만 재배열. ③ **일괄 다운로드는 체인을 쪼개지 않는다** — 행별 이름으로 정렬하면 AI 편집으로 개명된 버전이 제 체인에서 떨어져 ZIP 안에서 흩어지므로, 그룹(root) 사이만 **그 체인의 최신 이름**(= 패널에 보이는 이름)으로 줄 세우고 그룹 안은 `VersionNumber` ASC 유지. ④ **프론트 정렬 추가 0** — 서버 응답이 SSOT 라 컴포저 첨부 칩·전체 다운로드 매니페스트가 자동 정합(같은 규칙 두 벌은 이 모듈이 반복 기록한 결함 기전). **범위를 넓히지 않은 곳**: `/versions`(버전 순서는 이름과 무관)와 **LLM 컨텍스트 첨부 주입 순서**(화면 목록이 아니라 답변 품질 축). **검증의 판별력이 이 cycle 의 교훈**: 첫 PB-0008 시도의 대상 대화가 `probe_a~d.sql` 이라 **이미 알파벳순**이어서 통과해도 아무것도 증명하지 못했다 → 검색으로 39첨부 대화(`08051122_`·`v2_`·`v2_1_`·`v3_` 접두 혼재)를 열고, **수정 전 코드를 마운트한 baseline 컨테이너(:18098)** 와 같은 대화·같은 브라우저로 A/B 하여 순서가 코드 차이에서 온다는 것을 직접 보였다(수정 전 = 업로드 순 = DB `Id ASC` 일치 / 수정 후 = 39건 완전 이름순). `v2_1_…` 이 `v2_D_…` 앞에 서는 것이 자연 정렬의 실측 증거다. **검증**: 신규 pytest **12 passed**(사전순 역단언·절단 SQL 불변·PG alias 계약 포함) · 첨부·대화 회귀 **391 passed** · ruff clean · **PB-0008 실 Chrome/150 PASS**(자기 생성 탭만 조작, 병렬 세션 탭 2개 무접촉, **라이브 데이터 변경 0** — 열람 경로만). 전체 스위트의 유일 실패 `test_oauth_exhaustion_gate` 는 컨테이너 `chattr` 부재로 **pristine main 동일 재현** → 귀책 아님. **codex 적대 리뷰 2라운드가 실제 결함 3건을 끌어냈다**: ① 같은 패널 `#attachSidePanelList` 에 **렌더러가 둘**(서버 목록 + 컴포저 bucket)이라 서버만 정렬하면 업로드 직후엔 삽입 순서가 남는 것 — `_renderAttachmentPills` 두 목록에 `byName` 정렬 + 신규 하네스가 **정렬 호출 개수(2)** 로 잠금 ② PG 경로가 snake_case 로 바뀌면 정렬이 *조용히* 무의미해지는 것 → 두 표기 fallback ③ 4,300자리 초과 숫자열의 `int()` `ValueError` 로 목록 전체 500 → `float("inf")` 강등(0 강등은 `a1.txt` 보다 앞서는 거짓 순서). 반영 후 2라운드 **P1 없음(P1_COUNT=0)**. **잔여**: 배포 후 baked 자산 POST-DEPLOY 재실측 · 업로드 **직후** pill 순서의 실브라우저 실측(프리뷰가 라이브 DB 를 보므로 업로드 실측 = 라이브 데이터 변경이라 하네스로 대체). 정본 = TASK `20260813T1543-attach-list-name-sort` · FUNCTION `(REQ-20260813-attach-name-sort, 2026-08-13)` AC-…-1~4 · MODIFY/REVIEW `…-attach-list-name-sort` · TEST `docs/test-runs.d/20260813T154300-attach-list-name-sort.md`.

**2026-08-13 20260813T1224-attach-source-compare — 문서 원문 화면에서의 버전 비교 + "비교할 것이 없으면 원문" 수렴 + 목록 비교 버튼 기본쌍** (Minor §12.3 — feature-0003 `routers/attachments.py`(payload 필드 추가)·`static/app/attach-diff.js`·`static/app/composer.js`·`static/css/chat.css` + 신규 하네스. 신규 엔드포인트·권한 코드·스키마·마이그레이션 **0**). **사용자 요청 3항목**: ① "첨부파일의 '문서 원문' 화면에서도 버전 간 비교를 수행할 수 있도록" ② "같은 버전이나 / 버전 간 변경사항이 없는 경우에는 문서 원문을 그대로 출력" ③ "기본적인 '버전 비교' 버튼은 [가장 원본인 버전 → 가장 최신의 버전] 으로 비교". **출발점은 두 화면의 비대칭이었다** — 원문 보기 모달은 비교 진입점이 **0** 이었고 그 계약이 docstring 에 명시돼 있었으며(“버전 선택기를 두지 않는다”), 반대로 비교 모달에서 **같은 버전 두 개**를 고르면 "서로 다른 두 버전을 선택하세요" 안내만 남아 **본문이 0 인 화면**이 됐다. 내용이 동일한 쌍(`identical`)은 이미 원문을 출력하고 있었으므로(08-07), "비교할 것이 없다" 는 **한 사실**에 두 화면이 서로 다르게 답하고 있었다. **설계에서 load-bearing 한 결정 4건**: ① **in-place 전환**(다른 모달을 띄우지 않는다) — 요청 후단이 "같은 화면에서 원문으로 되돌아오는" 흐름을 전제하고, 창이 갈리면 보던 위치·켜 둔 토글이 리셋된다. ② **체인은 `/source` 가 함께 준다**(신규 `versions`) — `/versions` 는 버전마다 MinIO presign 을 만들고(이 화면엔 쓰이지 않는 비용) 왕복도 2회가 되어 "원문 모달의 요청은 `/source` 하나" 라는 기존 계약(하네스 A8)을 깬다. 노출은 `/versions` 응답의 **부분집합**(서명 URL·ObjectKey 없음)이고 게이트는 무변경. ③ **체인 조회 fail-soft** — `versions: []` 는 프론트에서 곧 "선택기 없음" = 종전 동작이라, 실패의 영향이 **추가된 기능에만** 갇힌다(원문 보기가 그 조회에 종속되면 쿼리 한 번의 실패가 "내용을 볼 수 없음" 으로 번진다). ④ **방향은 오래된→새로운 정규화** — 기준으로 더 새 버전을 골랐다고 좌우가 뒤집히면 같은 쌍이 진입 경로에 따라 두 방향으로 보인다. **변경의 절반은 복제 제거였다**: 원문 모달이 비교를 수행하게 되면서 판정·렌더·문구 사본이 **세 벌**이 될 자리였고(이 모듈이 반복 기록한 결함 기전 — 08-06 `.has-content` 단일열 의미 반전, 08-11 `code-highlight` 로컬 키워드 복제), `_bodyState`(본문 유무·원문 뷰·diff 표 유무의 단일 판정면) · `_renderSourceBody`(원문 화면 렌더, 두 모달 공유) · `_sourceStatsText`/`_diffStatsText`/`_sourceClipped` · `_mdBlockedNotice`/`_mdFallbackNotice` · 서버 `_version_side`(`/diff` nested 사본 승격)로 모았다. 회귀 잠금은 문자열이 아니라 **함수 정의 개수**로 걸었다(새 사본이 생기면 개수가 어긋난다 — §16.7 G10). **CSS 트랩 1건**: `.attach-source-cmpctl` 은 `.attach-diff-ctl` 의 `display:inline-flex` 를 물려받아 UA `[hidden]{display:none}` 를 이긴다 → 전용 `[hidden]` 규칙 추가. jsdom 은 `.hidden` 속성만 보므로 이 축은 CSS 로만 닫힌다(선행 cycle 이 hl 토글에서 같은 기전을 적발·문서화했다). **두 모달의 diff 전용 컨트롤 노출 정책이 다른 것은 의도**다 — 비교 모달은 상시 노출+비활성(기본 화면이 diff 라 위치를 외운다), 원문 모달은 비교 상태에서만 노출(기본 화면이 원문이라 상시 노출하면 대부분의 시간에 쓸 수 없는 컨트롤이 떠 있다). **검증**: 신규 하네스 `verify_attach_source_compare.mjs` **72 PASS/0 FAIL**(URL 별 응답 stub — 한 모달이 `/source`·`/diff` 를 모두 부르므로 단일 응답 stub 으로는 방향 정규화·재요청 0 축이 vacuous 하게 통과한다) · 기존 첨부 하네스 6종 **559 checks green**(리팩터로 계약이 옮겨간 소스-grep 축 3건은 취지 보존해 갱신) · pytest 신규 5축 + 첨부 2파일 **71 passed**(전체 스위트 실패 1건은 컨테이너 `chattr` 부재로 **pristine main 동일 재현** — 귀책 아님). **PB-0008 실 Chrome/150 PASS** — 격리 프리뷰 컨테이너 + 라이브 7버전 체인(`probe_a.sql`)으로 5단계 실측: 원문 화면(126행·선택기 215×26px·diff 컨트롤 rect 0×0) → v1 기준 비교(`v1 → v7`·`+5 / -0`·gap 114줄) → 같은 버전 복귀 **fetch 0회 계측** → 목록 버튼 `v1(최초) ↔ v7(최신)` → 비교 모달 같은 버전 → 원문 121행 + 사유 배너, 종전 안내문 소멸. **세션 격리 실사례(기록)**: 공유 CDP 포트에 병렬 세션이 붙어 `win-browser.py` 의 `pages[0]` 이 **남의 탭(`/admin`)으로 바뀐 것**을 검증 도중 관측 → `context.new_page()` 로 자기 생성 탭을 만들어 그 탭에서만 조작·캡처하고 종료 시 그 탭만 닫았다(§16.6 v3.44.0 (a)(b)(c) — 남의 탭은 건드리지 않았다). **잔여**: ① 배포 후 baked 자산 POST-DEPLOY 재실측 ② `identical` 화면의 라이브 조합은 체인에 해시 동일 쌍이 없어 하네스에서만 검증(라이브는 같은-버전 경로로 대체 실측) ③ §18.8 은 subagent panel 이 아니라 하네스+실측 채널(상위 도구 제약 하 §18.8.2 carve-out). 정본 = TASK `20260813T1224-attach-source-compare` · FUNCTION `(attach-source-compare, 2026-08-13)` AC-…-1~5 · MODIFY/REVIEW `…-attach-source-compare` · TEST `docs/test-runs.d/20260813T122457-attach-source-compare.md`.

**2026-08-12 20260812T2030-attach-md-render — 첨부 `.md` 를 마크다운 문서로 렌더** (Minor §12.3 — feature-0003 `static/app/attach-diff.js`·`static/css/chat.css` + 신규 하네스·PB-0008 시나리오. 백엔드·라우터·권한·스키마·마이그레이션·신규 엔드포인트 **0**). **사용자 재지시**: "요구사항이 잘 못 구현되었습니다. 구문 색이 아니라, 실제 마크다운 구성으로 출력되도록 구현해주세요." **선행 cycle 의 오해석 정정이다** — `attach-md-highlight` 는 "`.md` 포맷도 내부적으로 처리" 를 *구문 하이라이트*로 읽었는데, 요청의 본질은 "포맷을 색으로 구분" 이 아니라 **"포맷대로 보여 달라"** 였다. **그러나 선행 작업을 되돌리지 않았다**: 원문 보기(토글 off)와 **변경이 있는 diff** 화면은 줄 대조가 목적이라 렌더하면 기능 자체가 사라진다 — 두 기능은 대체가 아니라 **같은 화면의 두 모드**이고, 그래서 렌더 토글은 diff 화면에 노출되지 않는다(하네스 G5/G6 가 그 경계를 잠근다). **설계에서 load-bearing 한 결정 3건**: ① **파이프라인 신규 제작 0** — 답변 말풍선과 같은 `markdownToHtml`(`marked.parse` → enhance(diff/sql/attachment-edit/mermaid) → `DOMPurify.sanitize`)을 그대로 import 한다. 같은 `.md` 가 대화에 인용될 때와 첨부로 열릴 때 다르게 보이면 그 자체가 결함이고, 파이프라인을 두 벌 두면 한쪽만 갱신되는 것이 이 모듈이 반복 기록한 결함 기전이다. ② **토글 기본 켬 + 원문 복귀 보존** — 요청은 렌더지만 원문 확인 수단을 없애지 않는다(첨부는 계약 문서일 수 있어 바이트 그대로를 봐야 하는 상황이 있다). 복귀 시 **byte 무손실**이 계약. ③ **렌더 중 구문색 토글 숨김** — 칠할 원문 줄이 화면에 없어 거짓 어포던스가 된다. **보안이 이 cycle 의 실질 리스크였다**: 첨부 본문을 HTML 로 렌더하는 것은 신규 표면이고, 말풍선과 같은 sanitize 로도 **원격 리소스 fetch** 축은 닫히지 않는다 — `![](https://attacker/x.gif)` 한 줄이면 그 문서를 여는 **모든 그룹 멤버**의 IP·열람 시각이 업로더가 고른 서버로 샌다(스크립트 실행이 아니라 **로드 자체가 신호**라 DOMPurify 가 막지 않는다). 응답 헤더를 **실제로 조회**하니 CSP 는 `report-only` 라 브라우저도 차단하지 않았다 — 이름만 보고 "CSP 가 있으니 막힌다" 로 넘어갔다면 오판이었다(§16.7 G7-a). → sanitize **이후** DOM 에서 교차 출처 미디어를 중립화(URL 은 텍스트 칩으로 노출 + 건수 배너, 숨기지 않는다)하고 `iframe/object/embed` 는 출처 무관 제거, 교차 출처 링크는 `rel="noopener noreferrer nofollow"`. 칩 텍스트는 `textContent` 로만 넣어 하드닝이 새 XSS 경로가 되지 않게 했다. **codex 적대 리뷰가 6라운드에 걸쳐 [P1] 7건을 냈고 전건이 실제 결함이었다** — ① URL 검사가 `src`/`data` 뿐이라 `srcset`·`poster`·`xlink:href` 가 새고 프로토콜 상대 URL(`//evil`)이 문자열 검사를 통과 ② **라이브 DOM 에 먼저 파싱한 뒤 제거**해 비콘이 이미 나간 뒤였다 ③ 공용 sanitize 프로필이 `style`/`form`/`input` 을 허용(CSS url 비콘·인증 앱 위 피싱) ④ **mermaid 가 하드닝 이후 라이브 DOM 에 SVG 를 주입**하고 `themeCSS` 로 외부 `url()` 을 심을 수 있었다 ⑤ **같은 출처 이미지를 허용**해 `![](/api/ai/oauth/authorize?redirect_uri=…)` 한 줄로 **열람자 세션의 인가 코드가 발급**되는 GET-CSRF(같은 출처는 정보 유출이 아니라 **권한 행사**다 — "같은 출처면 안전" 전제가 틀렸다) ⑥ 그 이미지 경로를 닫고도 **같은 출처 링크 클릭**으로 같은 권한이 쓰이는 경로가 남아 있었다(부분 수정이 전체 수정처럼 보이던 사례) → 같은 출처 링크는 비활성화 + URL 노출 ⑦ `style` 을 막아도 **사용자 `class` 가 앱 CSS 를 빌려 UI 를 위장**(`share-mgr-backdrop` = `position:fixed; z-index:9999`) → 렌더러 생성 클래스 allowlist + `id` 제거. ②·④·⑤·⑥·⑦ 은 **이 기능의 목적 자체를 무효화**하던 결함이고, 그 시점의 코드는 하네스 66건과 PB-0008 을 이미 통과한 상태였다 — 통과가 안전을 뜻하지 않는다. 근본 착오는 방어를 sanitize *이후* DOM 정리로 설계한 것이었고, 지금은 `<template>`(inert)에서 중립화한 **뒤** 라이브로 옮긴다(순서가 방어의 본체). 부수로 `input` 금지가 GFM 작업 목록의 **체크 상태를 지우던 기능 회귀**를 글리프(`☑`/`☐`) 치환으로 해소했다 — 보안 조치가 요청받은 기능을 깎지 않게. **뮤테이션이 살아남아 검사를 고친 것도 3건**(죽은 2차 방어선 · `enhanceMermaidBlocks` 미로드로 vacuous 하던 mermaid 축 · 특정 문자열만 배제하던 구조 검사) — 생존은 코드가 아니라 검사의 결함 신호로 다뤘다. **PB-0008 증거도 한 번 무효였다**: 초판 시나리오가 렌더를 손으로 다시 써서 **고치기 전 구현을 촬영**하고 있었고, 정본 함수를 잘라 실행하도록 재작성 후 재촬영했다. **검증**: 신규 하네스 **102 PASS/0 FAIL** — 스텁이 아니라 **배포되는 vendor**(`marked.umd.js`+`purify.min.js`)를 jsdom 에 실제 로드해 렌더 계약·보안 경계를 그 라이브러리의 실동작으로 검사한다(스텁으로는 이 축이 성립하지 않는다). **뮤테이션 14종 전건 KILL**. 형제 하네스 4종 회귀 0(77/125/61/146). **PB-0008 실 Windows Chrome/150 PASS — 정본 `_renderMarkdownInto` 를 그대로 실행하며 기대값 대조를 eval 안에서 수행(어긋나면 throw — 종전엔 컨테이너 가시성만 봐서 측정 실패도 PASS 할 수 있었다)**: `renderOk` · **`tasks 2 / checked 1`**(체크 상태 보존) · **`mermaidCode 1 / svg 0`**(코드블록 강등) · **`inputs 0`** · **`networkImgs 0`(로드되는 이미지는 `data:` 뿐) · `blockedMedia 2` · `deadLinks 1` · `appLinksLeft 0` · `remoteAttrLeaks 0`**(모달 body 전체에서 자동요청 속성의 외부 출처 0) · 표 전용 wrap 1 · `h1 20 > h2 17 > h3 15 > p 14px`(hierarchyOk) · 외부링크 `rel/target` 정확 · **markersGone**. 세션 격리(§16.6 v3.44.0) 전용 포트·프로파일, `reused:false`. **캡처 함정 1건(기록)**: 초판 캡처가 앱 진입 `page-fade-in` 도중 촬영돼 서식·대비를 **판독할 수 없었다** — 흐린 캡처를 근거로 PASS 하지 않고 애니메이션 종료 대기를 시나리오에 넣어 재촬영했다(§16.6 다운그레이드 금지). **배포·POST-DEPLOY 검증 완료**: `105fa2b7`(`--web-only` 무중단 롤링 — web-a/web-b 동일 SHA, 엣지 `no upstreams available` **0건**). 배포본의 **실제 모듈**을 라이브에서 import 해 신규 배선 9축(inert template · 첨부 sanitize 프로필 · 클래스 allowlist · `data:` 한정 미디어 · 링크 비활성화 · mermaid 미렌더 · CSS 규칙 2종 · export) 도달을 단정했다. **잔여(정직 표기)**: ① 라이브 `.md` 첨부를 실 계정으로 여는 **조합** 대조는 타 사용자 대화 데이터 접근이라 수행하지 않았다 — 경로의 조각은 각각 실측, 조합만 미실측. ①-b 브라우저의 **실 네트워크 요청 계측**은 도구가 CDP Network 를 노출하지 않아 미수행(방어는 구조 + DOM census 로 확인) ② **mermaid 다이어그램은 첨부 화면에서 렌더하지 않는다**(코드블록 표시) — 말풍선에서는 종전대로 렌더되며, 첨부에서 그림으로 보려면 생성 SVG 를 inert DOM 에서 재정화하는 별 cycle 이 필요하다(REPORT §8 원장 후보) ③ §18.8 은 subagent panel 이 아니라 codex + PB-0008 실측 채널(상위 도구 제약 하 §18.8.2 carve-out). 정본 = TASK `20260812T2030-attach-md-render` · FUNCTION `(attach-md-render, 2026-08-12)` AC-AMR-1~6 · MODIFY/REVIEW `…-attach-md-render` · TEST `docs/test-runs.d/20260812T2030-attach-md-render.md`.

## 1. Summary

**2026-08-12 20260812T1817-hangul-qwerty-search — 한/영 자판 전환을 잊고 친 검색어도 결과를 내게** (Minor §12.3 — 신규 primitive 2벌(`static/hangul-qwerty.js` · `shared/hangul_qwerty.py`) + 클라이언트 13곳·서버 6경로 배선 + 신규 하네스 2종. 권한·스키마·마이그레이션·신규 엔드포인트 **0**). **사용자 요청**: "텍스트 박스에 한글 자판으로 입력하더라도 대응되는 영어 자판의 검색결과를 출력(반대도 가능)" + 예시 4쌍(`ㅎㅋ=gz`·`ㅈ듀=web`·`rmffhqjf=글로벌`·`tmzlem=스키드`). 첨부 화면 2건은 각각 대화 하단 '이 대화의 제품'(`ㅈ듀` → "검색 결과가 없습니다")과 관리 콘솔 '제품 관리'(`ㅎㅋ` → "제품이 없습니다")였다. **제시된 예시 4개가 전부 이 서비스의 실제 제품을 겨냥한 것**이었다 — `gz`=건즈 4종, `web`=웹 2종, `글로벌`=글로벌 2종, `스키드`=스키드러쉬. 즉 사용자는 존재하는 제품을 찾다가 매번 빈 화면을 봤다. **구현**: 두벌식(KS X 5002) 한↔영 변환 — 한→영은 음절 분해, 영→한은 **IME 와 동일한 조합 오토마타**(받침 뒤 모음이 오면 받침을 다음 음절 초성으로 이월; `rmffhqjf`→`글로벌` 이 이 규칙에 의존). 검색어에서 **후보 배열**(첫 항목은 항상 원문)을 만들어 원문과 후보를 OR 로 부분일치한다. **정본은 단일 정의 2벌**: ESM 번들이 둘(작업 화면·관리 콘솔)이고 서버는 web·agent 두 서비스가 쓰므로 JS 는 `static/`, Python 은 **`shared/`**(§17) — 매핑표 복제 0이며 하네스가 두 파일을 파싱해 값 단위로 대조한다. **배포 전에 잡은 결함 2건**: ① 처음 primitive 를 feature-0003 의 `src/modules/` 에 뒀는데, 이미지 레이아웃상 `from modules import` 는 **feature-0002 패키지**를 가리켜 런타임 ImportError 가 되고 호출부가 fail-soft 라 "기능이 조용히 죽은 채 배포" 되었을 것이다 — Dockerfile 실판독으로 선차단하고 `shared/` 로 옮겼다. ② **1자 변환 후보의 오탐** — 기존 하네스가 `dk` → `아` 가 "글로벌 라이브" 까지 잡는 것을 FAIL 로 포착했다. 사용자 의도는 잘못 친 검색어의 *구제*이지 정상 결과의 *확장*이 아니므로 후보 최소 길이 2자 게이트를 넣었다(요청 예시 4건은 전부 2자 이상이라 무손실). **회귀 0 설계**: 변환 대상이 없는 검색어는 후보가 1개라 조립 SQL 이 종전과 **문자열 동치**이며 pytest 가 이를 기계 단언한다. 서버 비용은 EXISTS 를 후보마다 반복하지 않고 **서브쿼리 안쪽에서 컬럼만 OR 전개**해 서브쿼리 수를 보존했다(`LIKE ANY(ARRAY[…])` 는 PG 문법상 `ESCAPE` 와 병용 불가라 미채택 — SECURITY §8.3 규약 우선). **검증**: 신규 mjs **48 PASS**(변환 왕복 13쌍·후보 계약·JS↔Python 매핑표 대조·배선 census, 뮤테이션 역검증 2종) · 신규 pytest **39 PASS** · feature-0003 프론트 mjs **54 suite 전건 PASS** · pytest 전 스위트가 **main 기준선과 동일**(사전 실패 `test_oauth_exhaustion_gate`=`chattr` 부재 1건만 — 같은 이미지로 main 을 별도 실행해 실패 집합 일치 확인) · **PB-0008 실 Windows Chrome/150 PASS** — 격리 프리뷰 컨테이너(`:18099`, 라이브 web-a/web-b·Caddy 무접촉)에서 사용자 보고 화면 2곳 실측: 제품 관리 `ㅎㅋ` → **4 / 19**(GZ 4종), 제품 드롭업 `ㅈ듀` → **2건**(WEB 2종, "검색 결과 없음" 미표시), `rmffhqjf`→글로벌 2건, `tmzlem`→스키드러쉬 1건, 원문 `건즈`→4건(회귀 0), `dk`→DK 3건(오탐 0). **서버 SQL 경로**도 라이브 대조: `비교`(원문) 20건 ↔ `qlry`(그 영타) **동일 20건·동일 첫 결과**, 대조군 `zzqlryzz` 0건. **범위 밖(원장)**: AI 도구가 스스로 만드는 내부 질의(`file_ops` 대화 검색, `schema.py` 테이블 후보)는 사용자 타이핑이 아니라 자판 오타가 성립하지 않아 의도적 미적용. 정본 = TASK `20260812T1817-hangul-qwerty-search` · FUNCTION `REQ-20260812-hangul-qwerty-search` AC-…-1~5 · MODIFY/REVIEW `…-hangul-qwerty-search` · TEST `docs/test-runs.d/REV-20260812T181700-hangul-qwerty-search.md`.

**2026-08-12 20260812T1830-attach-md-highlight — 첨부 `.md` 구문 하이라이트** (Minor §12.3 — feature-0003 `static/code-highlight.js` + CSS **주석만** + 하네스·PB-0008 시나리오. 백엔드·라우터·권한·스키마·마이그레이션·신규 엔드포인트 **0**). **사용자 요청**: "프로젝트 내 서비스에서, 첨부파일 중 '.md' 파일에 대한 포멧도 내부적으로 처리할 수 있도록 구성해주세요." **먼저 범위를 좁혔다**: 요청이 "포맷 처리" 라 서버 파이프라인을 전수로 훑었더니 `.md` 는 이미 전부 열려 있었다 — `_EXTENSION_KIND_MAP`(md·markdown→`text`)·`_MIME_KIND_HINTS`(`text/markdown`)·`_VERSION_DIFF_TEXT_KINDS`·원문 보기 `ATTACH_SOURCE_VIEWABLE_KINDS`·`_ASSISTANT_NEW_ALLOWED_EXT` 전부 통과한다. 막힌 곳은 프론트 `code-highlight.js` 의 `LANGS` **한 곳**뿐이었고, 그래서 `.md` 첨부는 업로드·인라인·diff·원문 보기까지 되면서 **화면에서만 구조가 산문과 같은 색**이었다. 선행 cycle(`20260806T1853-attach-diff-syntax`)이 모듈 헤더에 "차후 Markdown 추가" 를 예고해 둔 그 자리이고, "내부적으로" 는 그 모듈의 원칙(**vendor 무추가 경량 토크나이저**)과 정확히 대응한다. **설계에서 load-bearing 한 결정 3건**: ① **새 팔레트 변수 0** — 기존 9종 재사용(제목=keyword·강조=type·코드/URL=string·링크라벨=func·참조라벨=key·인용/fence=comment·리스트/구분선=punct·표 파이프=delim·체크박스=bool). 변수를 늘리면 대비 계산 하네스의 검증면이 함께 넓어지는데 markdown 은 기존 의미로 전부 표현되므로 넓힐 이유가 없다 — AC-AVD-24(WCAG AA)·AC-AVD-27(적용) 계약을 그대로 상속한다. ② **`_강조_` 의도적 미지원** — 이 화면의 `.md` 는 DB·SQL 문서가 다수라 `snake_case`·`__dunder__` 가 흔하고, 인식하면 **없는 강조를 만든다**("무색 > 오색"). ③ **fence 내부는 markdown 으로 읽힘을 수용** — 라인 독립 원칙(맥락 축약 뷰가 중간을 생략하므로 상태를 이어붙이면 색이 통째로 어긋난다)의 기존 절충을 뒤집지 않고, fence 줄 자체를 칠해 경계를 읽힌다. **성능은 재고 고쳤다**: 링크 대안이 2차 비용 지점이라 초판이 `"[".repeat(4000)` 에서 **2.98ms**, 가드 우회형 `…[[[[](x)` 에서 **2.18ms** 였다 → ① `](`·`)` 부재 시 링크 대안을 끈 정규식 ② 라벨·URL 200자 상한 + **라벨에서 `[` 제외** ③ `[` 런·산문 런 대안 → 최악 **0.72ms**, 실제 경로인 산문 920자는 **토큰 1개 0.002ms**. **codex 적대 리뷰(§18.8.2 제약 없는 채널)가 실제 결함을 끌어냈다** — [P1] 0건이지만 [P2] 3건 중 하나가 진짜였다: 표 정렬행 판정이 "`|`·`-` 포함 + 문자집합" 이라 **리스트 항목 `- |` 이 줄 전체 회색**이 됐다(셀 문법 확인 + "선두 `|` 없으면 2셀 이상" 으로 축소). 나머지 둘도 반영 — 연속 `|` 를 한 토큰으로 묶어 병리 입력 span 4,000개 → 1개, 그리고 "시나리오가 배포 모듈 대신 사본을 주입해 fail-open" 지적에 **배포본 실물 probe** step 을 넣어 배포 전 baseline(`has_md:false`, `langs:sql,json,yaml,xml,csv,tsv`)을 실측해 뒀다. **검증**: 하네스 **146 PASS/0 FAIL**(오색 금지 negative 5축 + fuzz 1,400건 무손실 + XSS + 실모달 배선 H13/H14 + 비용 4축) · 형제 하네스 회귀 0(77/125/61) · **PB-0008 실 Windows Chrome/150 PASS** — §16.6 v3.44.0 세션 격리를 지켜 **전용 CDP 포트(9242)·전용 프로파일**로 자기 인스턴스만 조작했고(`reused:false`), 배포된 실 CSS 위 실 `attach-diff-code` 구조에 31행을 렌더해 computed 색 9종이 `base.css` 정본과 일치함을 확인, 판독 가능한 확대 캡처 3장 확보. **배포·POST-DEPLOY 검증 완료**: `d0241c93` (`--web-only` 무중단 롤링 — web-a/web-b 동일 SHA, 엣지 `no upstreams available` **0건**). 선언했던 잔여 2건 종결 — 시나리오 step 3 의 배포본 실물 probe 가 `has_md: false → true`·`langs` 에 `md` 추가로 **뒤집혔고**(codex P2-3 종결), 라이브 페이지에서 `import('/static/code-highlight.js')` 한 **서빙 모듈로 직접 렌더**해 computed 색 정본 일치·무손실·span 외 태그 0 과 `- |` 수정을 배포 산출물에서 재확인했다. **남은 미실측 1건(정직 표기)**: 라이브 `.md` 첨부 3건의 원문 보기 모달을 실 계정으로 여는 **조합** 대조는 타 사용자 대화 데이터 접근이라 수행하지 않았다 — 그 경로의 두 조각(배포본 모듈→실 CSS→픽셀 / `_renderSource`→`_paintCell`→`paintCodeInto` 배선)은 각각 실측했고, 조합만 미실측임을 명시한다. ③ fence 내부 오색은 위 ③ 결정의 알려진 대가이며 회피가 아니라 기록이다. ④ §18.8 은 subagent panel 이 아니라 codex + PB-0008 실측 채널로 수행했다(상위 우선순위 도구 제약 하 §18.8.2 carve-out, REVIEW 에 채널·근거 명시). 정본 = TASK `20260812T1830-attach-md-highlight` · FUNCTION `(attach-md-highlight, 2026-08-12)` AC-AMD-1~6 · MODIFY/REVIEW `…-attach-md-highlight` · TEST `docs/test-runs.d/20260812T1830-attach-md-highlight.md`.

## 1. Summary

**2026-08-12 20260812T1726-dbpicker-layout-stability — '+ 데이터베이스 추가' 목록이 체크할 때마다 밀리는 문제** (Minor §12.3 — feature-0003 `static/admin/products.js`·`static/css/admin.css` + 신규 하네스 2종. 백엔드·라우터·권한·스키마·마이그레이션·신규 엔드포인트 **0**). **사용자 보고**: "참조할 DB 목록에서 체크박스를 활성화/비활성화 할 때, 추가/제거되는 요소에 따라 목록의 위치가 상대적으로 밀려나는 현상이 나타나 사용하기 번거롭습니다." **고치기 전에 쟀다**: 실 chromium 으로 수정 전 이동량이 단일 체크 **38.3px** · 해제 37.4px · 연속 3회 누적 **114.3px** · 정규식 일괄 114.3px · 데이터소스 picker 42.0px 임을 확보했다. 항목 행 높이가 29px 이므로 이것은 "성가심" 이 아니라 **다음 클릭이 다른 DB 에 떨어지는 오클릭 위험**이다 — 이 대조가 없었다면 1px 짜리 게이트를 세우고 스스로 만족했을 것이다. **기전**: `.cov-db-editor` 가 `[등록 DB 목록] → [picker]` 순서라, 체크 한 번마다 `redrawChips()` 가 **위쪽** 목록에 행을 더해 열려 있는 드롭다운을 통째로 밀었다. 같은 결함이 `+ 데이터소스 추가` 에도 있었다(토글이 위쪽 accordion 을 재구성). **수정은 사후 보정이 아니라 순서**: 두 picker 를 각자의 재구성 대상 **앞**으로 옮겼다. 대안이던 스크롤 보정은 위쪽에서 행이 *제거*될 때 필요한 보정량이 현재 `scrollTop` 보다 크면 음수 스크롤이 불가능해 **원리적으로 실패**하고(상단 근처에서 정확히 그렇다), 목록 높이 동결은 빈 목록에서 1행 박스가 되며, `position:fixed` 포털은 클리핑 때문에 절대배치를 의도적으로 버린 TASK-0240 결정을 되돌리게 된다. 순서 변경은 코드 3줄에 사후 계산 0, 모든 스크롤 위치·모든 변경량에서 성립하고 IA 로도 "액션 → 그 결과 목록" 이라 자연스럽다. **함께 봉인한 것**: degraded 배너 삽입점을 picker 위 → 목록 위(비동기 배너가 같은 밀림을 재생산하지 않게) · 선택 카운트(`선택됨 N개`)를 검색 toolbar 노출 임계(후보 6개) 미만에서도 상시 노출(목록이 아래로 내려간 뒤 유일한 즉시 피드백) · 두 picker 의 드롭다운 **내부** `scrollTop` 보존(정규식 일괄·× 제거·insight 도착마다 맨 위로 튀던 것) · `max-height` 220px → `min(50vh, 420px)`(sticky toolbar 112px 가 절반을 먹어 후보 130개 중 **3~4행**만 보이던 것 → **10행**). **codex 적대 리뷰가 실제 결함을 하나 끌어냈다(P2)**: 내가 등록 DB 빈 목록의 "아래에서" 만 고치고, `_renderDsAccordion()` 의 "바인딩된 데이터소스 없음 — … **아래에서** 데이터소스를 선택해 추가하세요" 를 놓쳤다 — picker 를 앞으로 옮긴 뒤 그 문구는 **반대 방향을 가리킨다**. 문구 교체에 그치지 않고 **파일 전수 census**(사용자 문자열의 "아래에서" 잔존 0)를 회귀 축으로 세웠다: 방향 지시어는 위치를 옮길 때마다 갈라지므로 개별 수정이 아니라 census 로 잠가야 한다. P1(Windows-browser 기록 부재)도 반영. **하네스가 vacuous 하지 않음을 스스로 증명**: 두 하네스 모두 축마다 "순서를 되돌리면 반드시 실패" 를 함께 단언한다. jsdom 축의 핵심은 순서 비교가 아니라 **토글 전후 picker 상류 마크업 바이트 동일** — 나중에 누가 picker 위에 요약 배지를 넣으면 순서 단언은 통과해도 이 축이 red 다. **검증**: 신규 jsdom **25 PASS** · 신규 실 chromium **13 PASS**(축마다 뮤테이션 역검증) · feature-0003 프론트 mjs **53 suite 전건 PASS**(0 fail) · pytest **4,287 수집 EXIT=0**(사전 실패 `test_oauth_exhaustion_gate` = `chattr` 부재, main baseline 동일 재현분 제외) · **PB-0008 실 Windows Chrome/150 PASS** — bind-mount 격리 컨테이너(`:18099`, 라이브 web-a/web-b·Caddy 무접촉)에서 후보 130개 실화면에 **실 트러스티드 클릭**: 이동 **0px** + 같은 화면 좌표의 `elementFromPoint` 가 동일 DB 유지, 역검증에서 38px/74px 재현. 모든 토글은 클라이언트 pending 이며 `모두 적용` 미클릭 — 종료 후 서버 정본 재확인(`webproductdatabases` 16/1 · 바인딩 2행)으로 **라이브 데이터 변경 0**. **잔여(정직 표기)**: ① 드롭다운 가시 행 수(AC-…-4)는 프리뷰 1차 측정이 **220px** 로 나왔다 — 배포 스탬프가 같은 URL 이라 구 CSS 가 `immutable` 로 붙들린 알려진 함정이며, 고유 쿼리 stylesheet 로 실제 서빙 파일을 재측정해 420px/10행을 확인했고 **배포본 재확인을 POST-DEPLOY 로 이월**한다. ② pending 0→1 로 넘어가는 **첫** 토글에서 하단 커밋 바가 나타나며 스크롤 컨테이너가 56px 짧아진다 — 컨텐츠 y 는 그대로라 밀림은 아니지만 바닥까지 스크롤된 상태였다면 clamp 로 한 번 튈 수 있다. 별개 기전이고 커밋 바 상시 숨김은 2026-07-28 사용자 요구(graph-noise-reduce)로 **의도적으로 내린 결정**이라 부수효과로 뒤집지 않고 관측만 등재한다(§13.1 명시 비활성화 블록 = 운영자 의도 보존). ③ §18.8 은 subagent panel 이 아니라 codex + 실측 채널로 수행했다(세션의 상위 우선순위 도구 제약 하 §18.8.2 carve-out, REVIEW 에 채널·근거 명시). 정본 = TASK `20260812T1726-dbpicker-layout-stability` · FUNCTION `REQ-20260812T172625-dbpicker-layout-stability` AC-…-1~5 · MODIFY/REVIEW `…-db-picker-layout-stability` · TEST `docs/test-runs.d/20260812T172625-dbpicker-layout-stability.md`.

## 1. Summary

**2026-08-11 20260811T1845-attach-diff-bubble-chip — 말풍선 수정본 첨부 칩의 diff 진입 버튼** (Minor §12.3 — feature-0003 `static/app/messages.js`·`static/css/chat.css` + 신규 하네스. 백엔드·라우터·권한·스키마·마이그레이션·신규 엔드포인트 **0**). **사용자 요청**: "서비스 내 assistant가 답변을 전달할 때, 첨부파일의 수정이 나타났다면 해당 수정에 따라 diff 패널이 출력될 수 있도록 버튼을 구성해주세요." (칩 `usp_replication_stea… 7 KB [v5 · AI 수정] ↓` 캡처 동반). **문제의 정체**: 비교 모달·서버 diff 계산은 `(attach-version-diff, 2026-08-06)` 이후 전부 있었고 없었던 것은 **진입점**이다 — 그 모달로 가는 길이 첨부 사이드 패널에만 있어, 답변이 방금 만든 수정을 보려면 패널 열기 → 파일 찾기 → "버전 N개 ▾" 펼치기 → `⇄` 의 4단계였다. 변경을 만든 화면에서 그 변경으로 가는 길이 없었던 것. **구현**: 칩 빌더(`_buildMessageAttachChip`)에 `⇄` 를 얹고 누를 때 lazy 로 체인을 조회해 정본 모달을 연다. 렌더러 복제 0(하네스가 소스에서 잠금) — 복제가 곧 결함 기전이었던 전례(`attach-diff-unified-bg`·`modal-dismiss.js`)를 반복하지 않는다. **이 변경의 실질은 preselect**: 모달 기본값은 "직전↔최신" 이라 체인 v1~v7 에서 v2 칩을 누르면 `6↔7`(이 답변과 무관한 쌍)이 열린다. `to` = 이 칩의 버전, `from` = 체인에 **실제로 남아 있는** 직전 버전으로 지정했고, `thisVer - 1` 을 쓰지 않는 이유는 중간 버전이 삭제된 체인에서 없는 번호를 지정하면 `<select>` 가 조용히 첫 옵션으로 떨어져 **엉뚱한 쌍이 "이 수정" 으로 보이는 무음 오표시**가 되기 때문이다(라이브 실측에서 그 대비가 그대로 확인됐다 — 체인 7버전, preselect `1↔2`). **버튼 조건은 작성 주체가 아니라 짝의 존재**(`version_number > 1` + id): v1(AI 신규 생성)은 비교할 짝이 없어 버튼을 두지 않고, 사용자 재업로드 v2 에는 둔다 — AI 수정본만 좁히면 같은 화면에서 비대칭이 되고 칩 버전 배지는 이미 양쪽에 붙는다. **codex 적대 리뷰(P1 0 · P2 4)가 구현 결함을 끌어냈다**: 지적 중 하나는 "중복 클릭 테스트가 vacuous(게이트를 stub 에 연결하지 않고 클릭 1회)" 였고, 그것을 정직하게 고치자 **구현이 red 로 뒤집혔다** — `btn.disabled` 는 trusted 클릭만 막고 프로그램 dispatch 는 리스너를 실행하므로 dispatch 3회에 왕복 3회·모달 3개였다. 상태 플래그(`dataset.diffBusy`) 재진입 가드로 해소. 나머지 3건도 반영: 403 중복 토스트(공통 처리가 이미 냄 → 재표시 억제) · 하드코딩 `rgba`(색 토큰 규칙 위반 → `--primary-soft`/`--primary`) · Windows-browser Run 기록 부재. **hover 는 대비 실측이 설계를 바꿨다**: 토큰으로 옮기자 흰 칩(`--surface`)과 `--primary-soft` 의 배경 대비가 **1.09** 여서 hover 가 사실상 보이지 않았다(글자색 대비는 4.75 AA). 형제 `.message-action-btn:hover` 가 border-color 를 함께 바꾸는 것과 같은 취지로 `inset` 그림자 테두리를 더했고, `inset` 이라 **레이아웃 이동 0**(옆 `↓` 좌표 Δ0 실측)이다. **검증**: 신규 하네스 **47 PASS** · **뮤테이션 12/12 red** · 기존 mjs 전수 **50 suite / 1,684 체크 / 0 FAIL** · 실브라우저 기하 55 PASS · **PB-0008 실 Windows Chrome/150 전축 PASS**(칩 4개 `⇄` 렌더 20×17px · 실제 마우스 클릭 → `버전 비교 — probe_a.sql` 모달이 `v1·사용자 ↔ v2·AI 수정` 로 열림 · 체인 옵션 7개 전량 · 페이지 이동 0 · hover 렌더를 2.6× 확대로 비-hover 형제 3칩과 대조 판독 · pageerror 0) — 전부 **bind-mount 프리뷰 컨테이너(`:18099`)** 에서 수행해 라이브 무접촉·데이터 변경 0(호출은 읽기 전용 `GET /versions`). **잔여(정직 표기)**: trusted hover 는 `bin/win-browser.py` 에 CDP mouseMoved 서브커맨드가 없어 **같은 선언을 주입한 렌더 결과**로 판독(선택자 발동만 우회, 전이 애니메이션 미관측) · 칩 본체 클릭의 다운로드 유지는 jsdom + 뮤테이션 M2 로 잠갔고 실브라우저는 OS 다운로드 경로라 자동 판독 미도달 · 히트 영역 20×17 은 WCAG 24×24 미만이나 저장소 칩·행 액션 공통의 **선재** 트레이드오프(원장 등재) · POST-DEPLOY 라이브 재확인은 배포 후. 정본 = TASK `20260811T1845-attach-diff-bubble-chip` · FUNCTION `REQ-20260811-attach-diff-bubble-chip` AC-ADBC-1~11 · MODIFY/REVIEW `…-attach-diff-bubble-chip` · TEST `docs/test-runs.d/20260811T1845-attach-diff-bubble-chip.md`.

## 1. Summary

**2026-08-11 20260811T1500-attach-diff-mark-underscore — 줄 안 변경 마크가 `_` 를 가리던 문제 수정** (Minor §12.3 — feature-0003 `static/css/chat.css` **선언 1종** + 회귀 잠금 테스트. 백엔드·API·RBAC·스키마·JS 로직 **0**). **사용자 지적**: "글자 단위 변경사항이 화면에 나타나는 부분을 확인했습니다. 다만, 해당 변경을 강조하는 하이라이트 밑줄이 특정 문자의 가독성을 떨어뜨리는 이슈가 확인되었습니다(`'_'` 문자 등)." **재현**: 실제 프로젝트 CSS 를 그대로 올리고 마크 규칙만 되돌려 렌더하니 `legacy_gy_pay` 가 **`legacygypay` + 밑줄 하나**로, `my_flag, __init__` 의 `__init__` 이 **`init`** 으로 읽혔다. **원인**: 마크를 `box-shadow: inset 0 -2px` 로 그렸는데, `inset` 은 바를 **content box 안쪽 맨 아래** — 즉 `_` 글자가 놓이는 바로 그 자리 — 에 놓는다. 두 가로 획이 붙어 하나로 보인 것이다. 직전 cycle 이 `text-decoration` 을 버리고 `box-shadow` 로 간 이유는 **탭 위 도포**였는데, 그 교체에서 바의 *수직 위치*는 검토 대상이 아니었다. **수정**: 바깥 그림자 `box-shadow: 0 2px` 로 교체 — 같은 두께를 content box **바로 아래**에 그려 글자와 바 사이에 빈 픽셀 행이 생긴다(실측 1행). **대비 논거가 그대로 유지되는 이유**: 바깥 그림자는 CSS 규정상 border box 안쪽으로 그려지지 않는다. 글자 영역의 마크색 픽셀을 세어 **0** 임을 실측했으므로 "마크는 배경을 칠하지 않는다 = 구문 토큰 AA 4.5:1 이 3면 그대로" 라는 기존 근거가 성립한다. **후보를 눈이 아니라 렌더로 골랐다**: `padding-bottom+inset`·바깥 그림자·배경색 간격·윗줄(overline) 4종을 같은 표 맥락에 렌더해 비교했고, 윗줄은 `_` 문제는 없지만 바가 **위쪽 줄에 붙어 보여** 귀속이 흐려졌으며, 배경색 간격은 행 배경색(추가/삭제 상이)을 하드코딩해야 해서, `padding-bottom` 은 인라인 박스 기하를 바꿔서 각각 탈락했다. **무회귀 실측**: 탭 도포 **192px 유지**(직전 cycle 이 고친 원 결함) · 행 높이 19px 불변 · `box-decoration-break: clone` 유지 · 쪽별 색 유지. **회귀 잠금 신설**: 기하 하네스 **M6** 이 마크 구간에 `_` 를 넣고 캡처해 **글자 잉크 최하단과 바 최상단 사이 빈 픽셀 행**을 직접 센다 — computed style 로는 잡히지 않고 렌더된 픽셀로만 드러나는 축이다(§16.6). mjs **D6a2** 가 `inset` 재도입을 소스에서 막는다. **부수 적발**: 기하 **M3b 의 클립 영역**이 span 박스 안쪽만 캡처하고 있어, 바가 박스 바깥으로 이동하자 마크가 있는데도 0px 로 세어 **거짓 FAIL** 을 냈다(하네스 아티팩트, 수정). 픽셀 검사는 "무엇을 캡처하는가" 가 곧 계약이라는 사례다. **검증**: 실브라우저 기하 **55 PASS** · jsdom **125 PASS** · mjs 전수 **50 suite OK** · pytest 전 스위트(백엔드 무영향). **§18.8 정직 표기**: 적대 3자 검토는 받지 않았다 — 판정 근거가 시각이라 bundle-only 리뷰어가 검증할 수 없어 자체 실측으로 대체했고, 절차와 수치를 fragment 에 전부 남겼다(`[SKIPPED:css-only-visual-fix]`). **잔여**: PB-0008 실 Windows 브라우저는 배포 후. 정본 = TASK `20260811T1500-attach-diff-mark-underscore` · FUNCTION `(attach-diff-intraline, 2026-08-07)` AC-ADI-13 · MODIFY/REVIEW `…-attach-diff-mark-underscore` · TEST `docs/test-runs.d/20260811T1500-attach-diff-mark-underscore.md`.

## 1. Summary

**2026-08-07 20260807T1400-attach-diff-intraline — 첨부 버전 diff 줄 안(글자 단위) 변경 구간 표시** (Minor §12.3 — feature-0003 `routers/_conv_store.py`·`routers/attachments.py` + `static/app/attach-diff.js`·`css/{base,chat}.css`. **신규 권한·스키마·마이그레이션 0**, 응답은 가산만). **사용자 재요청**: "문장 단위 diff를 표시해달라는 요청이 아직 수행되지 않았습니다. 여전히 line 단위 차이만 나타나고 있는 상태이며 **각 글자 단위의 차이점은 출력되지 않는** 형태라 작업 완수가 필요합니다." — `(attach-version-diff, 2026-08-06)` 가 §범위 밖 원장에 "단어 단위 intra-line 하이라이트" 로 미뤄 둔 항목의 완수(cross-session resume). **구조**: 구간 계산은 **서버 단독**(2열·단일열이 같은 마크를 보게 하는 기존 불변식의 연장 — 프론트가 각자 계산하면 두 뷰가 갈린다). 토큰이 **정렬 앵커**를 잡고(ASCII 단어 런 / **CJK 한 글자** / 공백 런 / 그 외 한 글자) 바뀐 조각 안에서 다시 **자소 단위로 좁힌다** — 토큰만 쓰면 `m.last_login_at`→`m.last_logout_at` 이 식별자 전체를 칠해 사용자의 원 불만이 한 단계 아래에서 반복되고, 문자만 쓰면 `SELECT`↔`INSERT` 가 색종이가 된다. 프론트는 **덧그리기**다 — 구문 하이라이트가 이미 만든 텍스트 노드를 문자 오프셋으로 쪼개 `<span>` 으로 감싸므로 두 강조가 독립 레이어로 공존하고, 세그먼트 총합이 셀 원문과 다르면 **아무것도 그리지 않는다**(어긋난 위치의 마크는 없느니만 못하다). **가장 중요한 판단 2가지**: ① **마크에 배경을 쓸 수 없다** — 구문 토큰 9색은 세 실배경에서 AA 4.5:1 로 잠겨 있고(하네스 G2 가 매 실행 재계산) 같은 색조를 얹으면 알파 **0.20 에서도 `number` 가 삭제 행에서 3.40** 으로 떨어진다(계산 실측). ② **상한은 대리값이 아니라 실제 비용이어야 한다** — 초판은 행 수만 제한해 폭 2000자 × 1500행에서 **411초**였고, 이를 "토큰쌍 예산" 으로 바꿨더니 §18.8 backend 패널이 그 통화마저 실패함을 실측했다(같은 명목 예산에서 실제 시간 **83배** 차 · 토큰화가 검사보다 먼저라 **예산을 한 푼도 안 쓰고 1,039ms** 소모 · 정밀화 비용이 게이트 뒤에 더해져 1.33배 초과). 최종은 **행별 문자쌍 컷(토큰화 이전 O(1)) + 패스 경과시간 0.5s + 응답 바이트 512KB** 3겹이고, 패널이 든 최악 입력이 **2997→5.3ms · 2367→4.1ms · 1079→2.7ms · 1039→2.1ms**, 정밀화 탈출 사례 266→0.00ms 로 떨어졌다. **§18.8 패널 3도메인 P1 4 · P2 5 · P3 다수 전건 흡수**: **탭 위 마크 0px**(`text-decoration` 은 탭 advance 를 칠하지 않는다 — 들여쓰기 변경이 이 기능의 주 대상인데 화면이 비었다 → `inset box-shadow` 로 교체, 실측 0→156px) · **정밀화 부재로 주 사례가 무응답**(sha256 한 글자 변경이 비율 컷에 걸려 마크도 배너도 없었다) · **정밀화가 자소 클러스터를 가름**(ZWJ 가족 이모지·keycap·국기 — 토큰화에만 보호를 걸고 정밀화는 raw code point 였다. 기존 B27 이 vacuous 였다는 지적도 실재) · **브랜치 자체 테스트 red**(계약을 바꾸며 갱신 누락) · 렌더 노드 폭증(6,000행에서 chunk span 60,000개 → 렌더-측 예산 12,000) · 배너 톤·문구(정밀도 절단이 내용 절단과 같은 amber → `is-note` 분리, "길어서" 는 화면과 어긋난 설명이라 제거) · 이색형 대비(삭제쪽을 `#7f1d1d` 로 어둡게 잡아 **명도를 쪽 구분 채널로**) · 과장 마킹(짧은 equal 흡수가 `년 `·CSV 구분자를 "바뀌었다" 고 칠했다 → 흡수 규칙 제거) · 악센트 라틴(`isascii()` 로 좁혀 `café` 가 마크 0개) · 무음 실패·재적용 중첩·기본 마크색·두 렌더러 분기 불일치. 패널이 **확인해 준 것**: XSS 무첨가(신규 경로 전부 textContent, 주입 실측 0 요소) · UTF-16↔코드포인트 오프셋 드리프트 없음 · 토큰 왕복 무손실 32만 표본 · 세그먼트 계약 무위반 5.6만 표본 · 2열/단일열 마크 문자집합 동일. **부수 성과 — 죽어 있던 게이트 복구**: `verify_attach_diff_geometry.py` 가 구문 하이라이트 cycle 이후 `detectCodeLanguage is not defined` 로 **전 케이스 미실행**이었다(main 에서도 재현). 이 화면의 유일한 배포 전 픽셀 게이트라 정본 `code-highlight.js` 인라인으로 살렸고, 그 덕에 탭 0px 회귀 잠금(M3b)을 여기에 심을 수 있었다. **검증**: pytest **4,018 PASS / 0 FAIL** · ruff clean · jsdom 124 PASS · mjs 전수 **49 suite OK** · 실브라우저 기하 **54 PASS** · 구문 하이라이트 113 PASS(토큰 대비 무회귀). **정직 표기**: PB-0008 실 Windows 브라우저는 **배포 후 잔여**(AC-ADI-9, `visual_verification_scope: always`) · 응답 페이로드 증가(+1.2MB)는 512KB 상한으로 완화했을 뿐 원인은 남음 · 1~2글자 마크의 시각적 약함은 배경을 못 쓰는 제약의 결과 · 형제 cycle `attach-diff-identical-source` 와 같은 파일을 건드려 rebase 로 흡수(pytest T-ID `B7` 충돌은 내 것만 B20~ 로 재번호). 정본 = TASK `20260807T1400-attach-diff-intraline` · FUNCTION `(attach-diff-intraline, 2026-08-07)` AC-ADI-1~12 · MODIFY/REVIEW `…-attach-diff-intraline` · TEST `docs/test-runs.d/20260807T1400-attach-diff-intraline.md`.

## 1. Summary

**2026-08-07 20260807T1700-gc-guide-esc-capture — 안내 툴팁 Esc 양보가 라이브에서 무효였던 결함** (Minor §12.3 — feature-0003 `static/app/composer.js` **1줄**(리스너 등록 옵션) + 하네스. 백엔드·API·RBAC·스키마 0). **적발 경로가 이 cycle 의 핵심**: 선행 cycle 은 하네스 61 PASS + **뮤테이션 5/5 KILLED** + `verify-completion` PASS + §18.8 ux·design 패널 전건 반영으로 배포됐는데, **PB-0008 라이브 실측이 8축 중 #8 에서 결함을 잡았다** — 멘션 자동완성이 열린 채 Esc 를 누르면 안내까지 함께 닫혔다. **근본 원인은 로직이 아니라 핸들러 실행 순서**다: 우리 Esc 핸들러가 버블 단계라, 먼저 등록된 멘션 AC 의 핸들러가 AC 를 이미 닫은 **뒤에** 돌아 `_gcGuideOtherOverlayOpen()` 이 "열려 있지 않다" 로 오판했다. 양보 판정은 **다른 핸들러가 상태를 바꾸기 전** 이뤄져야 하므로 **capture 등록**(`…, true`)으로 고쳤다 — 같은 파일의 `_attachShareRangeEsc` 가 정확히 같은 이유로 이미 capture 를 쓰고 있었다(선례를 따르지 않은 것이 결함이었다). **더 중요한 것은 하네스가 왜 통과시켰는가**: 가짜 DOM 에 경쟁 핸들러가 없어 "양보한다" 는 단언이 *우리 함수만 존재하는 세계* 에서만 참인 **vacuous pass** 였다. 단언이 형식적이어서가 아니다 — 뮤테이션 5/5 를 죽였다 — **합성(composition)을 재현하지 않은 것**이 사각이었다. 그래서 점수정에 그치지 않고 하네스를 고쳤다: 가짜 document 를 **capture → bubble 2단계 디스패치**로 바꾸고 `installCompetingOverlayEsc()` 로 "그 오버레이가 먼저 자기를 닫는" 라이브 조건을 주입하며, 경쟁 핸들러 없음/있음 **양쪽**과 **과잉 양보**(오버레이가 없는데 안 닫힘)까지 반대 방향으로 단정한다(§16.7 G4·G10). **검증**: **68/68 PASS**, capture→버블 되돌림 뮤테이션 **6 red**, `node --check` PASS, mjs 전수 49 suite exit 0. **피해 범위(정직)**: 이 결함으로도 안내가 **영구 소진되지는 않았다** — 라이브에서 `localStorage=null` 을 실측 확인했고, 앞선 ux BLOCKING #1 수정(닫기≠소진 분리)이 그 경로를 이미 끊어 뒀다. 잔여 영향은 "그 로드에서 안내가 함께 사라짐" 이었다. **배포·검증 완료**: `f60d67c5` — PB-0008 재실측 **8/8 PASS**(#8 은 실제 버블 경로에서 `acAfter=false` + `tipAfter=true` 동시 확인, #7 과잉 양보 반대방향도 PASS). 정본 = TASK `20260807T1700-gc-guide-esc-capture` · MODIFY/REVIEW 동명 · TEST `docs/test-runs.d/20260807T1500-gc-first-use-guide.md`(선행 fragment 에 Run append).

## 1. Summary

**2026-08-07 20260807T1500-gc-first-use-guide — 그룹 대화 기능 첫 사용 1회 가이드 툴팁** (Minor §12.3 — feature-0003 `static/index.html`·`static/app/composer.js`·`static/css/chat.css` frontend-only. **백엔드·API·RBAC·스키마·마이그레이션 0**). **사용자 요청**: 그룹대화 참여 기능을 **처음 쓸 때**(각 그룹대화의 처음이 아니라) 간단한 가이드를 툴팁으로 — 팝업은 화면을 가리므로 금지, 일반 대화·`@assistant` 요청 방법 포함, 각 줄 30자 이하 한 줄. **설계에서 결정적인 것은 소진 단위**: "각 대화의 처음" 과 "기능의 처음" 을 가르는 것은 키를 무엇으로 잡느냐 하나이며, 대화 id 로 잡으면 요구와 정반대(방마다 반복)가 된다 → 키 = **계정(username)**, `localStorage mad.gcFirstUseGuide.v1`. **노출 판정 위치**: `renderComposer` 말미 1회 — 이 feature 의 선행 결함 `gc-unread-read-fix` 는 같은 성격의 처리를 *일부 진입 경로에만* 걸어 "복원된 대화는 아무리 봐도 배지가 안 줄던" 누락을 냈다. 그래서 대화 전환·새로고침 복원·폴링이 전부 지나는 choke-point 를 골랐다. **§18.8 적대 패널(ux·design)이 양쪽 BLOCK 을 냈고, 그중 하나는 설계의 핵심을 뒤집었다** — 초판은 확인·입력·Esc 세 경로 모두를 영구 소진으로 처리했는데, 안내가 뜬 순간 반사적으로 타이핑한 신규 참여자는 **한 줄도 못 읽고** 복구 경로 없이 온보딩을 잃는다(재열기 UI 가 없다). → **닫기와 소진을 분리**했다: "다시 안 보기" 클릭만 영구, 입력·Esc 는 그 로드에서만 숨김(다음 방문에 다시 뜸). 두 번째 BLOCK 은 **거짓 안내** — `conversation.ask` 가 없거나 대화가 `blocked` 인 계정에게 "@assistant 를 붙이면 AI가 답해요" 로 유일한 1회 기회를 소비시키던 것 → 발화 가능 게이트 추가(표시도 소진도 없음). design 은 **`z-index:60` 이 같은 자리(`bottom: calc(100%+6px)`)를 쓰는 `#mentionAutocomplete`(50)를 가린다**는 것을 짚었다 — 안내 2·3번째 줄이 사용자에게 `@` 입력을 시키므로 그 가림은 *정상 경로*에서 일어난다 → z 40 으로 낮춰 멘션 AC·드롭 오버레이 아래로. caret 도 `calc(100% - 4px)` 라 `.composer-wrap`(top padding 8px) 안으로 12px 파고들어 LLM 제한/시간연장 배너 위에 흰 노치를 그리고 있었다 → `calc(100% + 6px)` 로 카드·caret 전체를 밖에. **다크 모드 지적은 실측 후 반대로 조치했다(G7-a)**: 반영하려다 `css/base.css` 를 확인하니 `prefers-color-scheme` 블록이 **0개**이고 `--surface` 는 항상 `#ffffff` 다(라이트 단일 테마) — 여기에 다크 override 를 넣어 강조색을 밝은 파랑으로 올리면 OS 가 다크일 때 **흰 카드 위 연파랑(≈1.8:1)** 이 되어 오히려 못 읽는다. 넣지 않고 토큰(`--gc-guide-*`)만 남겼으며, 하네스가 "base.css 에 다크 토큰 없음" 이라는 **전제**를 함께 단정해 전제가 바뀌면 red 로 드러난다. **대비는 계산해서 고쳤다** — 본문에 쓰려던 `--text-muted`(#807d72)가 흰 배경 **4.12:1** 로 12px AA 미달이라 전용 토큰 `#4a4841`(**9.15:1**)로 교체(제목 15.38 · 닫기 5.17). **문구도 계약과 대조해 두 줄을 고쳤다**: 첨부는 열람만 전원 공유이고 **LLM 주입은 발신자 본인 것 한정**(F1)이라 "멤버 모두가 봅니다" 는 오도 → `첨부는 전원 공유, AI엔 내 것만`; `@이름` 은 LLM 미호출이라 윗줄(`@assistant`→응답)과 대비되게 `@이름 은 알림만, AI 미호출`. 권한별로 갈리는 ☰ 말풍선 액션은 §16.7 G3(주장한 affordance 와 배선의 괴리)를 피해 넣지 않았다. **검증**: `verify_gc_first_use_guide.mjs` **61 PASS** — 문자열 grep 이 아니라 실제 함수 본문을 가짜 DOM/localStorage 클로저에서 구동하며, 요구의 핵심([1회] 두 번째 그룹 대화 미재노출 · [임시닫기] 다음 방문 재노출 · [게이트] 발화 불가 무소진 · [Esc 양보] 5종 · [스택] 두 파일의 실 z 값 비교)을 **경계 양측**으로 단정한다. **뮤테이션 5/5 KILLED**(입력-소진 복원 · 게이트 제거 · Esc 양보 제거 · z 60 · caret wrap 잠식) — 단언이 형식적이지 않음의 실증. **미검증(정직 표기)**: 실 렌더에서 각 안내가 **한 줄로 떨어지는지**(문자열 길이 단언이 못 보는 축), caret 지시 방향, 멘션 AC 와의 실제 스택 순서는 브라우저가 정본이며 이 환경에 브라우저 바이너리가 없다 — **PB-0008 배포 후 실측 완료** — 1차(`f81c5bcb`) 7/8 에서 Esc 양보 결함 적발 → 수정 후 재실측(`f60d67c5`) **8/8 PASS**. 각 안내가 실제로 한 줄로 렌더됨(`linesPerItem [1,1,1,1,1]`)·카드 전체가 composer-wrap 밖·멘션 AC 가 카드 위임을 실화면으로 확인했다. 정본 = TASK `20260807T1500-gc-first-use-guide` · FUNCTION `(gc-first-use-guide, 2026-08-07)` AC-GCG-1~9 · MODIFY/REVIEW `…-gc-first-use-guide` · TEST `docs/test-runs.d/20260807T1500-gc-first-use-guide.md` · 기능 정본 feature-0009-group-conversation.

## 1. Summary

**2026-08-07 20260807T0640-attach-diff-syntax-css-fix — 구문 하이라이트 keyword 규칙 미적용 hotfix** (Minor §12.3 — `css/chat.css` 주석 2줄 + 테스트. 백엔드·API·RBAC·스키마 0). 직전 cycle 배포본 `6cd4afd2` 의 **PB-0008 라이브 실측**이 적발: `code-tok-keyword` 의 computed color 가 `rgb(38,37,30)`(=`--text` 기본값)·weight 400 으로 **규칙이 파일에 있는데 적용되지 않았다**(number·comment 는 정상). **원인** — 설명 문단을 기존 주석의 닫는 `*/` **뒤에** 붙여 여는 `/*` 가 없는 고아 블록이 생겼고, CSS 파서가 `**굵기는 … */` 를 셀렉터로 읽기 시작해 **바로 다음 규칙 하나를 통째로 삼켰다**(keyword 만 죽고 type 이후 정상 = 실측과 일치). **왜 하네스가 통과했는가** — F/G 섹션의 CSS 단언이 전부 문자열 grep 이라 "규칙이 적법한 위치에 있는가" 를 묻지 않았고, jsdom CSSOM 으로 바꿔도 **깨진 버전이 13 규칙을 그대로 인식**해 잡히지 않는다(실측 확인). **조치** — 주석 병합 + 결정적으로 잡히는 정적 가드 F8(고아 `*/`)·F9(미닫힘)·F10(주석 제거 후 셀렉터 위치에 한글·`**` 누출)을 chat.css·base.css 양쪽에. 하네스 **113 PASS**, 결함 재주입 시 F8·F10 **2중 검출**. **교훈**: CSS 는 문자열 검사로 검증되지 않는다 — "규칙이 실제로 적용되는가" 의 정본은 실 브라우저 computed style 이며, `visual_verification_scope: always` 가 이 결함을 잡은 것이 그 근거다. **배포·검증 완료**: `6a3b1a97` — keyword computed `rgb(124,58,237)`/600 실측 PASS. 정본 = TASK `20260807T0640-attach-diff-syntax-css-fix`.

## 1. Summary

**2026-08-06 20260806T1853-attach-diff-syntax — 첨부 버전 diff 파일 유형별 구문 하이라이트** (Minor §12.3 — feature-0003 `static/code-highlight.js`(신규)·`static/app.js`·`static/app/attach-diff.js`·`css/{base,chat}.css` frontend-only. **백엔드·API·RBAC·스키마·마이그레이션 0**). **사용자 요청**: "첨부파일의 버전 간 diff 를 비교하는 화면에서 파일 유형에 따른 확장 하이라이트(SQL 예약어 등)". 범위(사용자 confirm) = **SQL + 구조화 데이터 우선, 차후 확장 가능한 구조**. **왜**: diff 배경(초록/빨강)은 "이 줄이 바뀌었다" 까지만 말하고, 바뀐 것이 테이블명인지 값인지 주석인지는 토큰 색이 있어야 갈린다(`SET status = status` 류에서 변경 지점을 눈으로 못 찾는다). **구조**: `code-highlight.js` 를 저장소 단일 primitive 로 신설 — 언어 레지스트리 `LANGS`(sql/json/yaml/xml/csv/tsv, `{label, exts, tokenize}`)에 한 항목 추가하면 확장이 끝나고 호출자는 불변. **SQL 예약어·타입 목록의 정본을 이 모듈로 이전**하고 `app.js`(답변 말풍선)가 import — 세 벌이 될 목록을 한 벌로(modal-dismiss 의 "복제가 곧 결함 기전"). diff 두 렌더러는 **같은 `_paintCell`** 을 부른다(2열·단일열이 같은 응답의 두 표현이라는 기존 불변식의 연장). **의도된 절충 3가지**: ① **라인 독립 토큰화** — 행 사이로 블록주석 상태를 이어붙이면 `gap` 생략 지점 이후 색이 통째로 어긋나고 그 오염은 조용하다(무색 > 오색) ② **미지원 확장자는 무색** — `dump.sql.gz` 를 SQL 로 칠하지 않는다 ③ **`sql-tok-*` 무변경** — 말풍선은 어두운 코드블록 배경, 첨부 diff 표는 문서 배경(라이트)이라 팔레트를 공유하면 한쪽이 반드시 저대비가 된다. **토글**: 확장자 오판 탈출구로 `.attach-diff-hl` pill(감지 시만 노출 = 거짓 어포던스 회피 · 기본 켬 · `aria-pressed` · off 는 `lang` 미전달이라 "끔 = 종전 동작" 이 구조로 보장). **fuzz 가 실결함을 잡았다**: CSV/TSV 토크나이저에 catch-all 대안이 없어 **짝 없는 따옴표 1글자가 소실**(결정적 PRNG 1,200 표본 중 152건 · 표본 13건으로는 통과). 깨진·잘린 CSV 는 실제로 들어오고, 원문 손실은 사용자가 **존재하지 않는 diff** 를 보게 만드는 유일하게 조용히 치명적인 축이라 fuzz 를 상설 가드로 남겼다. **검증**: 신규 하네스 **77 PASS**(판정 14·토큰 28·무손실 2·XSS 7·렌더 통합 19·CSS·정본 7) · 기존 diff 하네스 **85 PASS**(primitive 를 스텁 아닌 실물로 주입) · **mjs 전수 46 suite 전건 OK** · **뮤테이션 5/5 KILLED**(M5 innerHTML 조립에서 실제 `<script>` 가 DOM 에 파싱되어 D2/D3 red — XSS 단언이 형식적이지 않음을 실증). **정직 표기**: jsdom 은 **색을 보지 못한다** — 색 대비·6,000행 체감은 PB-0008 이 정본이며 AC-1·AC-6 은 그때까지 미확정. 기하 하네스는 이 환경에 playwright 브라우저 바이너리가 없어 미실행(span=inline 이라 열 폭 무영향이 근거이나 측정하지 않았다). **§18.8 패널 3도메인 = BLOCK 2(ux·design)+CONCERN 1(security), P1 4·P2 7·P3 4 전건 흡수**: ① **대비를 계산하지 않은 것이 최대 결함** — "jsdom 은 색을 못 본다 → PB-0008 이월" 은 틀린 이월이었고(대비비는 브라우저 없이 계산 가능) 계산하니 **27조합 중 12조합 AA 미달**(type 은 흰 배경도 3.68) → 6종 명도 강하 + number→teal(로즈는 삭제 빨강과 같은 arc = "추가 행 안의 삭제 표식") + var→보라(앰버면 string 과 이색형 ΔE 0.75) → **하네스 G2 가 매 실행 재계산**(계산 가능한 축을 사람 눈에 맡기지 않는다) ② delim 배경 칩이 1.14:1 로 자기 목적 미달인데 글자 대비를 3.52 까지 끌어내리고 20열 CSV 에서 행 배경(1차 신호)을 벌집처럼 뚫음 → 굵기로 대체 ③ **거짓 어포던스를 다른 축에서 재현** — 주석에 "무색 파일에 끄기 버튼 금지" 라 써 두고 파일명은 지원인데 **본문이 없는** 6종(바이너리·조회실패·동일·행0·에러·from===to)에서 토글이 켜진 채 떠 있었다 → 노출 판정을 렌더 결과 기반으로 ④ **토글 축 테스트가 vacuous** — 버튼 속성만 단언해 `lang` 상수화·`rerender` 제거·localStorage no-op **4종 뮤테이션 전부 생존**(뮤테이션 5종을 돌렸지만 전부 하이라이트 축이었다 = 커버리지도 축별로 봐야 한다) → H 섹션이 실제 모달을 몰아 **셀 span 수**를 본다 ⑤ **성능 방어가 잘못된 층** — `MAX_LINE_LEN` 은 줄 하나를 막지만 비용은 길이에 2차라 상한 근처에 집중, 4,000자 7.99ms → 1MB 원본 **4.4초 main-thread 정지**(그룹 멤버가 심은 첨부로 교차 도달) → 정규식 모호성 4곳 수정으로 선형화(**0.609ms**, 성장률 1.92×) ⑥ 오색 차단(XML 산문 `word =`·YAML 문장 중간 `on`) — "무색 > 오색" 자기 선언을 판정에 걸었다 ⑦ pill→checkbox 통일(10px 옆 같은 성격 on/off 가 다른 위젯·다른 announce 였다)·라벨 "강조"→"구문 색"(이 제품에서 "강조"=선택적 emphasis 라 행 필터로 오독). 패널이 **확인해 준 것**: XSS 무첨가 720 DOM 단언 · 무손실 **2,309,424 표본** 손실 0 · 다크 override 미도입 판단 정당 · share.js 사본 byte-identical. **흡수 후**: 하네스 **108 PASS**(A~I) · 기존 85 PASS · mjs 전수 46 suite OK · **뮤테이션 9/9 KILLED**. **배포·검증 완료**: `6cd4afd2` 배포 → **PB-0008 이 CSS 결함 1건 적발**(keyword 규칙 미적용 — 고아 주석이 삼켰다) → hotfix `6a3b1a97` 재배포 후 재실측 **전건 PASS**(keyword `rgb(124,58,237)`/600 · 끔 span 12→0 텍스트 불변 · 단일열 parity · 2버전 체인). 미측정 2건은 REPORT §8 원장(비교불가 유형 라이브 표본 0 · 6,000행 체감). 정본 = TASK `20260806T1853-attach-diff-syntax` · MODIFY/REVIEW `…-attach-diff-syntax` · test-runs.d `20260806T1853-attach-diff-syntax.md`.

## 1. Summary

**2026-08-06 20260806T2000-attach-chain-merge — 분열 첨부 체인 병합 도구 + 첨부 날짜 compact 표기** (**Critical §12.3** — 라이브 첨부 메타데이터 rewrite. feature-0003 `scripts/attach_chain_merge.py`(신설) + `static/app/composer.js`. **스키마·마이그레이션·RBAC·엔드포인트 0**). **사용자 지시**: "갈라진 첨부파일에 대해서는 하나의 체인으로 합쳐주세요. 범위가 너무 넓다면 최근 1주일 범위만 / 첨부파일이 첨부된 날짜도 compact하게 출력". 선행 cycle `attach-multi-upload` 이 **분열 기전**(편집본이 다른 파일명으로 저장)을 막았고, 본 cycle 이 **이미 갈라진 데이터**를 정리한다. **범위 판단은 재고 나서 했다** — "너무 넓은가" 를 답하려면 수치가 있어야 한다: 전수 실측 결과 활성 780 row 중 분열 **155 row / 62 논리파일 / 14 대화**(최근 7일은 25/67/4). row 수가 적고 되돌릴 수단을 함께 만들므로 **전체 대상**으로 정하고 `--days 7` 경로는 보존했다 — 최근 7일만 하면 오래된 대화는 갈라진 채 남아 "한 파일이 목록에 여러 줄" 이라는 원 문제가 절반만 해소된다. **병합 규칙**: 논리 파일 = `(conv, account, base(filename))`(`base` = 끝의 `_v<n>` 제거)를 **CreatedAt 오름차순**으로 정렬해 root/version 재부여 + 파일명 통일 + HMAC 재계산, `SupersededAt` 은 **다음 버전의 CreatedAt**(최신 1건만 NULL — `NOW()` 일괄 스탬프는 "언제까지 최신이었나" 를 지운다). `ObjectKey`·MinIO 객체·본문·`Sha256` 불변. **파괴성 설계 — 되돌릴 수 있게 만드는 것이 1순위**: 기본 dry-run · 스냅샷 JSON + **사람이 직접 실행 가능한 롤백 SQL** 동시 생성(`--rollback` 경로도 제공) · 단일 트랜잭션 + `UNIQUE(root,version)` 회피 **2단계 UPDATE**(오프셋에 `Id` 를 더해 대상 행끼리도 무충돌) · PG 미러 동기화(라이브 목록 read 가 PG 우선 — 어긋나면 같은 첨부가 두 줄) · **사후 재검증 잔여 0**(아니면 exit 2). **오병합 방지**: base 이름 row 없이 사용자가 직접 `_v<n>` 로 올린 그룹은 제외(실측 0건이나 가드 유지, C6b 가 반대 방향으로 "과하지 않은지" 를 단정) · 대화·계정 경계 불침범. **첨부 날짜**: 목록 메타줄에 한 토막(오늘 `14:20` / 올해 `8/6` / 그 외 `25/8/6`, 전체는 title) + 버전 이력 행 시각. **백엔드 변경 0** — `created_at` 이 이미 응답에 있었다. ⚠️ **시간대를 기억이 아니라 실측으로 확정했다(G7-a)**: `CreatedAt` 은 MySQL `NOW()` 기반 **로컬(KST) naive**(18:50 업로드 → `2026-08-06T18:50:29`, `UTC_TIMESTAMP()`=10:04, TZ=Asia/Seoul)라 오프셋 없는 문자열을 그대로 파싱해야 맞다 — 선행 cycle 의 `restorable_until`(UTC·`Z` 보정 필요)과 **반대**라, 그 보정을 이식하면 9시간 어긋난다(뮤테이션 D1 이 잠금). **검증**: pytest **신규 17건**(2단계 UPDATE 순서·실패 롤백·SupersededAt live 1건 포함) + mjs **신규 18건**(시간대 3 · 뮤테이션 역검증 3) · 전 스위트 **exit 0** · 전수 mjs **46 스위트** · verify-completion PASS. **§18.8 채널(정직)**: codex 사용량 한도(리셋 08-09) + subagent 상위 지시 제약 → 인라인 검토 + 기계적 점검으로 대체, `[SKIPPED:tool-restricted:panel]`. **잔여**: **라이브 `--apply` 는 배포 후**(결과는 POST-DEPLOY 기록으로) · 병합 후 목록 줄 수가 줄어든다(3줄 → 1줄 + "버전 3개 ▾", **데이터 손실 0** — 이전 버전은 버전 이력에서 접근) · `MetaJson.version_diff` 는 저장 시점 텍스트라 새 이웃과 어긋날 수 있으나 화면 비교(`/diff`)는 요청 시점 계산이라 무영향. 정본 = TASK `20260806T2000-attach-chain-merge` · FUNCTION `REQ-20260806-attach-chain-merge` AC-ACM-1~5 · MODIFY/REVIEW `…-attach-chain-merge` · TEST `docs/test-runs.d/REV-20260806T200000-attach-chain-merge.md`.

**2026-08-07 20260807T0430-attach-diff-scroll-block — 상호작용 스크롤 보존 + 문단 단위 하이라이트** (Minor §12.3 — feature-0003 `static/app/attach-diff.js`·`static/css/chat.css` frontend-only. **백엔드·API·RBAC·스키마 0**). **사용자 보고·요청**: 상호작용(펼치기 · 동일한 줄도 모두 보기 · 2열/단일열 교체) 시 스크롤이 최상단으로 이동 / line 단위 외 **문단 단위 하이라이트**도. **① 원인**: `_renderBody` 가 본문을 비우고 **scroller 요소를 새로 만들어** 스크롤이 요소와 함께 사라진다. **픽셀 복원은 틀린 답** — 전개는 행을 삽입하고 2열↔단일열은 `replace` 를 1행↔2행으로 바꿔 같은 픽셀이 다른 줄을 가리킨다. 사용자가 지키려는 것은 스크롤 값이 아니라 **보고 있던 내용**이므로 **줄번호 앵커**(`data-lno`)로 보존한다(같은 줄 없으면 가장 가까운 이하 줄). **의도된 비대칭** — 버전 쌍 변경은 최상단으로: 같은 비교의 표시 변경과 다른 비교로 갈아탄 것은 다르고, 후자에서 위치를 유지하면 사용자가 어디를 보는지 모른다. 경계 **양측**을 다 테스트했다(S1~S4·S6 보존 / S5 초기화) — 한쪽만 보면 "항상 보존" 이라는 과한 계약이 굳는다(직전 cycle 의 높이 고정과 같은 실패 형태). **② 문단 하이라이트**: 줄 배경만으로는 "5줄이 한 덩어리로 바뀜" 과 "1줄씩 5곳이 바뀜" 이 같아 보인다. `_assignBlocks` 로 연속 비-equal 행을 블록화(gap 이 끊는다 — 생략 구간을 건너 이어붙이면 없는 연속을 그린다)하고 좌측 accent 바 + 여러 줄 블록의 시작·끝 경계선 + 줄번호 배경 한 단계로 표시한다(1줄 블록은 accent 만 — 선을 그으면 노이즈). 계산을 **한 곳**에 두어 2열·단일열이 같은 경계를 본다. **부수 적발 — 선행 결함 1건**: 실측 중 `delete` 행의 **빈 우측 셀**이 danger 배경(`rgba(220,38,38,0.12)`)인 것을 발견했다 — 우측 파일에는 없는 내용을 "여기 삭제된 것이 있다" 로 읽힌다. 내가 넣은 accent 규칙("내용 있는 쪽에만")과 줄 배경 규칙이 **같은 화면에서 충돌**하고 있었다 → `has-content` 로 좁히고 빈 자리는 중립 filler. **검증**: 헤드리스 **44/44**(S1~S6 스크롤 · B1~B8 블록, 실측 토글 `487→486` 줄 27 유지 · 펼치기 `584→583` 줄 32 유지 · 버전 변경 `top=0`) · mjs **84 PASS**(A1c 구조 가드 11건) · 전수 mjs **44 suite OK** · **뮤테이션 역검증 3/4**. **정직 표기**: `_restoreScrollAnchor` 의 rAF 2회는 방어적이며 현재 호출 지점에서 필수가 아니다 — `offsetTop` 이 동기 레이아웃을 강제해 즉시 실행도 동작하고, **rAF 제거 뮤테이션이 S1~S6 전부 생존**했다(비대칭 비율 S6 추가 후 재시도해도 구별 못함). "테스트가 있으니 검증됨" 으로 쓰지 않고 근거를 코드 주석에 남겼다. **잔여**: 배포 + PB-0008(스크롤 4종 + 블록 시각 판독 + 선행 47축 회귀). 정본 = TASK `20260807T0430-attach-diff-scroll-block` · FUNCTION `(attach-diff-scroll-block, 2026-08-07)` AC-AVD-15~18 · MODIFY/REVIEW `…-attach-diff-scroll-block` · TEST `docs/test-runs.d/20260807T0430-attach-diff-scroll-block.md`.

**2026-08-06 20260806T1820-attach-multi-upload — 폴더 단위 첨부 경로 · 중복 스킵 UX · 편집본 버전 체인 통합** (Major §12.3 — feature-0003 `static/index.html`·`static/app/composer.js` + `routers/_conv_store.py`·`routers/attachments.py`. **스키마·마이그레이션·RBAC·엔드포인트 shape 0**). **사용자 보고**: "내용에 차이가 나타나는 파일들임에도 '동일한 파일' 이슈가 나타나며 블로킹" (대화 `구 로그 테이블 DROP 유지 결정`, 대상 = `D:\…\dev-GunzPlus\Schema\*` 22개). **가장 중요한 결과 — 전제가 실측과 어긋났다(§16.7 G7-a)**: 로컬 22개의 sha256 을 계산해 그 대화(`20260806052006-3f48cbb7`)의 활성 첨부와 전수 대조한 결과 **22/22 가 내용 동일**이었다. 파일 mtime 은 갱신됐지만 내용은 그대로였고, 앞선 17:33 시도에서 통과한 6개는 그 시점에 실제로 달랐던 것이다. **따라서 dedup 판정을 완화하지 않았다** — 완화했다면 진짜 중복이 매번 새 버전으로 쌓여 버전 이력이 무의미해진다. 고친 것은 판정이 아니라 **판정 주변의 경로·알림·체인**이다. **실재한 결함 5**: ① `#attachFileInput` 에 `multiple` 부재 → 대화상자가 1개만 고르게 함(22개면 22회) ② change 핸들러가 `files[0]` 만 처리 ③ **`.composer-wrap` 이 `#chatPane` 의 자손**(DOM 파싱 확증)인데 양쪽 drop 핸들러가 모두 업로드해 **첫 파일이 2회 업로드**되고 두 번째가 dedup 에 걸려 "이미 첨부된 파일입니다" **오탐 토스트** — 사용자가 본 현상의 실제 기전 중 하나 ④ 중복 스킵을 **빨간 에러**로, 그것도 파일마다(단일 토스트 엘리먼트라 서로 덮어씀) ⑤ assistant 편집본이 `<원본>_v<n>.<ext>` 라는 **다른 파일명**으로 저장 → 체인 스코프가 `(conv, account, OriginalFilename)` 이라 원본이 head 에서 빠지고 사용자 재업로드가 **새 root(v1)** 를 만든다(라이브 실측: 그 대화 한 곳에만 분열 쌍 **9건**). **변경**: `multiple` + 전량 순회 · `_uploadComposerAttachments` 배치 래퍼(집계 후 **요약 1회** `첨부 22개 중 6개 업로드 · 16개 변경 없음(건너뜀)`, 단건은 기존 개별 토스트 유지) · 스킵을 **정보 톤 + "이미 최신입니다(내용 동일) — 건너뜀"** 으로(오류가 아니라 no-op) · composer drop 은 chatPane 자손이면 **위임**(chatPane 부재 시 자체 처리 폴백 — 삭제가 아니라 위임인 이유) · 편집본 파일명 **원본 승계**(LLM filename 무시 → 실행파일 확장자 승격 경로가 정의상 소멸, SEC-1 강화) · 버전 구분은 **표시 계층으로 이동**(다운로드 응답·저장명만 `_v{n}`, DB 값 불변이라 dedup·체인 무회귀). **검증**: 신규 하네스 `verify_attach_multi_upload.mjs` **28 PASS**(정적 5 · **jsdom 실행 8** · 집계 9 · 저장명 3 · **뮤테이션 역검증 3** — `files[0]` 복원·drop 가드 제거·`multiple` 제거를 모두 red 로 검출) · pytest N3(계약 전환)·N4(안전 확장자 불변)·**N5**(체인 단일성)·**N6**(표시명 분리) · 전 스위트 **exit 0, 실패 0** · 전수 mjs **45 suite** 통과. **§18.8 검증 채널(정직 기록)**: `codex review` 는 **사용량 한도 소진**(리셋 2026-08-09)으로 물리적 불가, subagent panel 은 상위 우선순위 지시로 제약 → §18.8.2 carve-out 에 따라 **인라인 보안 검토**(HIGH/MEDIUM 0건 — path traversal 은 `safe_filename` 이 차단, Content-Disposition 방어 무변경, 인가 경계 무변경) + 기계적 계약 점검으로 대체하고 `[SKIPPED:tool-restricted:panel]` 로 ux·design·backend 미검증 범위를 명시했다. **잔여**: PB-0008 실 Windows 브라우저 라이브 검증(정적 자산이 이미지에 baked 되어 **배포 후**) · **기존 분열 체인 9쌍 소급 병합 미수행**(파괴적 데이터 변경 §12.3 — 별도 승인 대상, §8 원장) · 단일 토스트 엘리먼트 구조 자체는 불변(배치가 회피할 뿐). 정본 = TASK `20260806T1820-attach-multi-upload` · FUNCTION `REQ-20260806-attach-multi-upload` AC-AMU-1~5 · MODIFY/REVIEW `…-attach-multi-upload` · TEST `docs/test-runs.d/REV-20260806T183000-attach-multi-upload.md`.

**2026-08-07 20260807T0320-attach-diff-height — 비교 모달 높이를 고정에서 상한으로** (Minor §12.3 — feature-0003 `static/css/chat.css` **1선언**. JS·백엔드·RBAC·스키마 0). **적발 경로**: 선행 cycle(`20260807T0200-attach-diff-ux`, 배포본 `b23df012`) 의 PB-0008 라이브 캡처 **판독**. 자동 **44축 전부 PASS** 했는데 캡처를 보니 짧은 diff 에서 표 아래에 큰 빈 영역이 남았다(내용 y≈495 종료 / 패널 940). **원인은 결함이 아니라 내가 세운 계약이었다** — 사용자 요청 "모달이 작아 내용을 모두 출력하기 제한된다" 를 `height: 94vh` **고정**으로 구현했고, 필요한 것은 **상한 확대**였다. 더 나쁜 것은 그 고정을 **테스트가 요구사항으로 굳힌 것**이다(선행 T9 의 "높이 ≥ 88vh" 단언) — 잘못된 계약이 자동 검증의 인증을 받아 정상으로 통과했다. **교훈**: 요청을 계약으로 옮길 때 **그 계약이 요청보다 강하지 않은지** 확인해야 한다. 강한 계약은 테스트를 통해 요구사항으로 굳어 다음 사람이 되돌리기 어려워진다. **수정**: `height: 94vh` 제거(= `max-height: 94vh` 만). 내용에 맞춰 자라고 뷰포트 94% 에서 멈추며 넘치면 `.attach-diff-scroller` 가 스크롤한다. **검증 재설계** — 높이 축을 **경계 양측**으로 나눴다(§16.7 G4): T9 는 폭만 검사 · **T9b** 짧은 diff 는 상한 미만(빈 영역 없음, 실측 244px) · **T9c** 긴 diff(120행)는 상한에 닿음(846px=94vh) · **T9d** 넘치면 표 컨테이너가 스크롤(페이지 세로 오버플로 False). 한쪽만 보면 이번 결함이 다시 통과한다. 헤드리스 **25/25** · 전수 mjs 44 suite OK · pytest 무영향. **적발 수단이 자동 게이트가 아니라 캡처 판독이었다는 점**이 §16.7 G9-a 의 세 번째 실증이다(앞선 둘은 열 폭 4등분 · calc-무시). **잔여**: 배포 + PB-0008 높이 2케이스 재검증. 정본 = TASK `20260807T0320-attach-diff-height` · FUNCTION `(attach-diff-height, 2026-08-07)` AC-AVD-10(개정) · MODIFY/REVIEW `…-attach-diff-height` · TEST `docs/test-runs.d/20260807T0320-attach-diff-height.md`.

**2026-08-07 20260807T0200-attach-diff-ux — 비교 모달 확대 · 줄번호 여백 · 중앙선 드래그 · gap 국소 전개** (Minor §12.3 — feature-0003 `routers/_conv_store.py`(응답 additive) + `static/app/attach-diff.js`·`static/css/chat.css`. **RBAC·스키마·마이그레이션 0**). **사용자 지적·요청 4건**(스크린샷 2장 동반): 모달이 작아 내용이 잘림 · 줄번호 열 여백 과다 · '좌우 2열' 중앙선 드래그 조절 · "동일한 N줄 생략" 클릭 시 그 구간만 국소 표시("동일한 줄도 모두 보기" 비활성 시). **줄번호 여백은 선행 결함과 같은 뿌리** — 사용자가 본 화면은 배포본 `d46a6b04` 로 열 폭이 4등분돼 줄번호 열이 284px 였다(`20260807T0030-attach-diff-colgroup` 이 이미 수정·push 대기 중이었다). **가장 중요한 발견 — 선행 수정이 절반만 듣고 있었다**: `<colgroup>` 계약을 세운 선행 cycle 의 헤드리스 기하 8/8 통과는 **줄번호 열에 대해서만** 참이었다. 좌우 code 열의 `calc((100% - 4ch - 24px) * ratio)` 는 Chrome 이 무시해 auto(균등 분배)로 떨어졌고, **기본 비율 0.5 가 균등 분배와 같은 수치를 내서 테스트가 구별하지 못했다** — 사용자의 드래그 요청을 구현하다 비율이 안 바뀌는 것을 하네스가 잡아 드러났다. 교훈: "기본값이 우연히 같은 값을 내는" 단언은 판별력이 없다. **5형태 대조 실측으로 경계 확정**: `calc(0.3*(100%-4ch-24px))` 무시 · `calc(30% - 12px)` 무시 · `30%` honor(281/655) · `300px` honor · 퍼센트 없는 `calc(2ch+12px)` honor ⇒ 줄번호는 절대 calc 로 colgroup 에, **좌우 code 는 렌더 후 실측 기반 plain %** 로 지정하고 창 크기 변화 시 재적용. 그 형태를 다시 쓰지 못하도록 mjs 가 소스에서 금지한다. **변경**: 모달 `94vh × calc(100vw - 24px)` + backdrop 여백 24→12px + body flex(잔여 높이 전부) · 줄번호 자릿수 기반 `calc(Nch + 12px)` + padding 축소 · `.attach-diff-splitter`(11px 히트영역 · document 레벨 리스너 · 키보드 ←/→/Home · localStorage 영속) · gap 을 버튼화하고 서버가 실어 준 줄번호 범위로 **전체 맥락 1회 캐시 후 그 구간만 splice**(축약 로직 프론트 재구현 0 — 재구현하면 서버·클라이언트 두 축약이 갈라져 같은 쌍에 다른 화면이 나온다). **드래그 초판 결함도 하네스가 잡았다** — `pointermove` 를 핸들에만 바인딩해 포인터가 11px 핸들을 벗어나는 첫 이동(32px)에 이벤트가 끊겼다(`mousedown` 은 성립하는데 비율 불변). 저장소 기존 리사이저(`setupAttachSidePanelResize`)와 동형인 document 레벨로 교정 — 기존 패턴을 따르는 것이 새 패턴을 발명하는 것보다 안전하다는 실증. **하네스 방식 전환**: 함수 개별 추출이 모듈 상수·상호 호출이 늘 때마다 깨져(이 cycle 2회) 헤드리스·mjs 모두 **모듈 전체 로드**(import 만 스텁)로 바꿨다 — 로직 재구현 0 을 유지하면서 깨짐이 사라지고, 부수로 헤드리스가 `openAttachmentDiffModal` 전체 흐름(드래그·전개)을 실제 구동한다. **실측 결과**: 모달 1416×846 / 뷰포트 1440×900 · 줄번호 3자리 **30px**(옛 48px)·5자리 42px · 드래그 `[662,662] → [395,929]`(합 보존) · gap 전개 rows 5→16 · gap 2→1 · 전체맥락 조회 1회. **검증**: 헤드리스 기하·상호작용 **22/22**(T7 colgroup 제거 시 균등분배 재현 포함) · mjs **73 PASS** · 전수 mjs **44 suite OK** · pytest 신규 **24건** · 정본 `make test` 전수. **미검증(정직 표기)**: ux·design 의 가독성·시각 위계 **판단**(기하는 숫자로 잠갔으나 "읽기 좋은가" 는 별 축) · Chromium 단일 엔진 · **PB-0008 배포 후 잔여**. 정본 = TASK `20260807T0200-attach-diff-ux` · FUNCTION `(attach-diff-ux, 2026-08-07)` AC-AVD-10~14 · MODIFY/REVIEW `…-attach-diff-ux`.

**2026-08-07 20260807T0030-attach-diff-colgroup — diff 표 열 폭 계약을 `<colgroup>` 정본으로 + 감지축 신설** (Minor §12.3 — feature-0003 `static/app/attach-diff.js`·`static/css/chat.css` frontend-only. **백엔드·API·RBAC·스키마 0 · 제품 Python 변경 0**). **적발 경로**: 선행 cycle `20260806T2320-attach-version-diff` 의 **POST-DEPLOY PB-0008**. 자동 게이트는 전부 통과했고(pytest 22 · mjs 57 · verify-completion PASS) 실 브라우저 캡처를 **판독해서야** 좌우 열이 표 폭을 채우지 못하고 가운데로 몰린 것이 보였다. **근본 원인(라이브 실측)**: `table-layout: fixed` 는 열 폭을 **첫 행의 셀**에서 가져오는데, 맥락 축약 뷰의 첫 행은 흔히 `gap`(`colspan=4`) 이라 개별 열 폭이 정의되지 않아 브라우저가 표를 **균등 분할**한다 — `.attach-diff-lineno{width:48px}`·`.attach-diff-code{width:calc(50% - 48px)}` 가 **통째로 무시됐다**(표 1136px / 네 열 전부 **284px**). 파일 앞부분에 동일 줄이 4줄 이상이면 gap 이 맨 위에 오므로 사실상 **거의 항상** 발현한다. **변경**: `_appendColgroup` 신설(2열 4 col · 단일열 3 col) + CSS 폭 정본을 `.attach-diff-col-*` 로 이관 + `td` width 3건 **삭제**(정본이 둘이면 다음 사람이 안 먹는 쪽을 고친다). **왜 점수정으로 끝내지 않았나 — 문제의 본질은 감지축 부재**: `colgroup` 3줄이면 결함은 닫히지만, 이 클래스(레이아웃 산출물)에 대해 pytest·jsdom·정적 스캔·verify-completion 이 **원리적으로 눈이 없고** 유일한 감지 수단이 "배포 후 사람이 캡처를 본다" 였다. 그 상태를 유지하면 같은 클래스가 다음에도 배포를 통과한다 → 실 chromium 기하 실측을 **배포 전** 게이트로 신설(`tests/headless/verify_attach_diff_geometry.py`). **가드가 load-bearing 임의 증명**: T7 이 `colgroup` 을 제거한 뒤 다시 재어 `[284,284,284,284]` — **라이브 관측치와 동일** — 를 확인한다. 즉 "지금 통과한다" 가 아니라 "그 결함이 들어오면 red 가 된다" 를 증명한다. **검증**: 헤드리스 기하 **8/8**(T7 역재현 포함) · mjs 하네스 **65 PASS**(A1b 구조 가드 7건: colgroup 유무·열 수·클래스·첫 자식·CSS 가 col 타깃·**td width 잔존 0**·결함 조건 존재) · 전수 mjs **44 suite OK** · pytest 는 제품 Python 무변경이라 선행 배포본과 동일(정본 `make test` 기준). **정직 기록**: 본 세션 임시 pytest 러너가 `PYTHONPATH` 를 덮어써 이미지 baked `/app`(= `web` 패키지)을 떨어뜨려 `test_share_redaction_invariant` 7건이 실패했다 — **손대지 않은 main 에서 동일 재현**되어 코드 회귀가 아님을 확인했고 판정은 정본 러너로 갈음한다. **잔여**: 배포 + PB-0008 재검증(선행 31항목 + 기하 실측 4항목 — 이번엔 육안이 아니라 숫자로). 정본 = TASK `20260807T0030-attach-diff-colgroup` · FUNCTION `(attach-diff-colgroup, 2026-08-07)` AC-AVD-9 · MODIFY/REVIEW `…-attach-diff-colgroup` · TEST `docs/test-runs.d/20260807T0030-attach-diff-colgroup.md`.

**2026-08-06 20260806T2320-attach-version-diff — 첨부 버전 diff 비교 화면(임의 쌍·다단계)** (Major §12.3 — feature-0003 `routers/attachments.py`·`routers/_conv_store.py`·`app.py` + `static/app/attach-diff.js`(신설)·`static/app/composer.js`·`static/css/chat.css`. **신규 권한 코드·스키마·마이그레이션 0**, 기존 엔드포인트 응답 shape 무변경). **사용자 요청**: "서비스 내 대화에서 첨부파일이 여러 버전이 있을 때, 각 파일들 간의 diff를 비교할 수 있는 화면을 구성해주세요. 해당 파일의 직전/직후의 diff 뿐만 아니라, 여러 단계의 차이가 나는 버전 간 비교도 진행할 수 있어야 합니다." **사용자 결정(AskUserQuestion)**: 전용 모달 + 2열/단일열 둘 다 + 토글. **간극(실측)**: 버전 체인·`GET …/versions`·"버전 N개 ▾" 목록은 이미 있었고(TASK-0274/0285, REQ-20260713) 없던 것은 **비교 자체**다 — `MetaJson.version_diff` 는 업로드 시점의 **직전↔신규 1쌍**만 담고(용도=LLM 컨텍스트 주입) 프론트 diff 렌더 코드가 0이었다. 다단계 쌍은 저장 대상이 아니다(쌍 수가 체인 길이의 제곱) → **요청 시점 계산**. **변경**: ① `_load_attachment_version_chain`(체인 로더 — `/versions` 의 중복 SQL 추출·공유, PG 미러 우선·MySQL 폴백) ② `_build_version_diff_view` — **한 번의 `SequenceMatcher` opcode 패스에서 unified 문자열과 좌우 정렬 rows 를 함께** 산출(두 경로면 같은 두 버전에 서로 다른 결과를 보일 수 있고 그때 사용자는 어느 쪽을 믿을지 알 수 없다). 맥락 축약은 `gap` 행으로 **생략 줄 수를 표면화** ③ `GET /api/attachments/{id}/diff` — 권한은 기준 첨부의 `conversation.attachment.read.{own,any}` **재사용**(신규 권한 0), 체인 밖 버전은 400 이 아니라 **404**(존재 여부 oracle 차단), 바이너리는 `comparable:false` + 메타 비교로 **강등해 답한다**(빈 diff = "차이 없음" 오독 방지), 절단 3종(원본 1MB cap ×2 · 행 6000)을 응답 필드와 화면 배너 **양쪽에** 표면화 ④ 프론트 전용 모달 — from/to 독립 선택기 · `⇄` 맞바꾸기 · 2열/단일열 토글(재요청 없이 같은 응답 재렌더) · "동일한 줄도 모두 보기" · `reqSeq` 경쟁 가드 · diff 본문 `textContent` 전용 ⑤ 진입점 2종 — 박스 머리 "⇄ 버전 비교"(직전↔최신)와 **구버전 행 `⇄`**(그 버전↔최신 = 다단계 직행, 최신 행에는 미노출). **자체 적대 검증에서 결함 2건 적발·수정(초판을 그대로 출하했다면 라이브에 남았다)**: **[P1] D21 bytes-deny 우회** — diff 행은 파일 **본문**이라 승인 대기 계정 판정을 metadata 조회(signed URL 만 보류)가 아니라 **본문 다운로드(403)와 동형**으로 맞춰야 하는데 초판에 게이트가 없었다 → 원본 조회 **앞**에 403(회귀 잠금이 `storage.reads == []` 까지 단언해 "403 주고 뒤에서 읽는" 구현을 배제) · **[P2] 체인 스코프를 가정으로 둔 것** — 체인 로더가 root 로 전체를 반환하며 "같은 conversation·account 귀속" 을 전제했다(기존 `/versions` 도 동일). 그 전제가 깨진 행 하나면 기준 첨부 게이트가 덮지 못하는 첨부가 응답에 실린다 → `scope_row` 로 **필터**(fail-closed) + 제외 건수 warning, 두 엔드포인트 모두. **검증**: pytest **신규 22건** · 전수 회귀 **3,806 passed · 3 skipped · 0 failed**(exit 0) · **뮤테이션 역검증 7/7**(404→400 · 맥락 축약 · 행 상한 · D21 게이트 · scope_row 누락 · 스코프 필터) · 헤드리스 mjs **신규 57건**(jsdom 에서 정본 렌더 함수를 실제 실행) + 전수 **44 suite OK** · `acorn-globals` 자유 식별자 0 · `gen-routemap` 재생성(223→224) · `codenav-lint` OK · route 골든 parity(added 1 / removed 0 / order drift 0). **§18.8 검증 채널(정직 기록)**: dispatch 표가 요구하는 subset 은 ux+design+backend+security+qa 이나, `codex review` 는 **사용량 한도 소진**(8/9 까지)으로 물리적 불가하고 Agent tool 은 **상위 우선순위 지시로 금지**돼 §18.8.2 carve-out 에 따라 `[SKIPPED:tool-restricted:ux,design,backend,qa]` 로 미검증 범위를 명시했다. **현 시점 미검증 축**: 모달의 레이아웃·정렬·간격·가독성(jsdom 은 픽셀을 보지 못한다) — **PB-0008 실 Windows 브라우저 검증이 유일한 backstop 이며 배포 후 수행**(신규 JS 는 스탬프 미주입 + 모듈 캐시 이중 인스턴스로 `docker cp` 사전 QA 가 불가). **범위 밖(§8 원장)**: 말풍선 첨부 칩 진입점(진입점 2개면 §16.6 복수 surface 개별 검증 필요) · 바이너리 내용 비교 · 단어 단위 intra-line 하이라이트 · 포커스 트랩(전 표면 공통). 정본 = TASK `20260806T2320-attach-version-diff` · FUNCTION `(attach-version-diff, 2026-08-06)` · MODIFY/REVIEW `…-attach-version-diff` · TEST `docs/test-runs.d/20260806T2320-attach-version-diff.md`.

**2026-08-06 20260806T1825-attach-suffix-toggle — 다운로드 파일명 버전 접미사(`_v2`) 토글** (**Minor §12.3** — 비파괴 표시 옵션, 권한·스키마·마이그레이션 0. feature-0003 `routers/{_conv_store,attachments,conversations}.py`·`app.py`·`static/{index.html,app/composer.js,css/chat.css}`). **사용자 요청**: "첨부파일을 다운로드 받을 때 접미사(`_v2`, `_v3` 등)가 포함되는 상태로 받을지 토글할 수 있는 체크박스를 적절히 구성 — 단일 파일 / 전체 파일 다운로드 모두 대응". **실측이 바꾼 범위**: 기존 문서·주석은 접미가 "전 버전 일괄 다운로드에서 붙는 것" 으로만 서술했으나, 저장 경로(`_next_version_filename`)를 읽어 **AI 편집본은 저장명 자체가 `report_v2.csv`** 임을 확인했다 — 그 서술만 믿고 `scope=all` 스위치를 달았다면 사용자가 겪는 다수 경우(최신본 1개 받기)는 그대로 남았다. **동반 적발**: 접미 규칙이 서버 `_zip_entry_name`(무조건 부착)과 프론트 `_versionedFilename`(무조건 부착) **두 벌**로 있어 AI 편집본을 `scope=all` 로 받으면 `report_v2_v2.csv` 가 나왔다(역검증으로 재현 확인). **구현**: 규칙 정본 `_download_filename_with_version(raw, version_number, keep|strip|force)` 하나를 두고 단일 다운로드·ZIP·매니페스트가 모두 경유 — `strip` 은 `_v<VersionNumber>` 가 **일치할 때만** 제거해 사용자가 지은 `plan_v2.docx`(v1)를 왜곡하지 않고, `force` 는 떼고 붙여 idempotent. 이름 결정 권위를 서버로 모으고(프론트는 `X-Attachment-Download-Name` 헤더 / 매니페스트 `download_filename` 채택, `_versionedFilename` 제거) 토글 상태는 `localStorage` 1개를 패널·모달 체크박스가 공유한다. 일괄 다운로드의 `version_suffix` **미지정 기본은 scope 별**(all→force, latest→keep)이라 파라미터를 모르는 기존 호출자의 결과가 불변. **자기 리뷰로 잡은 2건**: ① 매니페스트가 ZIP 과 다른 이름 경로를 써서 접미 제거 시 개별 저장만 같은 이름 3개가 됐다 — 모달이 약속한 "구분 번호가 붙습니다" 가 한쪽에서 거짓이 되므로 ZIP 과 같은 함수로 통일. ② 그러자 단건 응답 헤더가 매니페스트의 dedup 이름을 덮어써 중복이 되살아났다 — 일괄 개별 저장만 `preferGivenName` 으로 호출자 이름 우선(단건 응답은 묶음을 모른다). **§18.8 패널 3종 전건 흡수(codex 할당량 소진 → 사용자 승인 후 subagent, §18.8.2)**: security PASS + P3 2건(단일 경로 정제 비대칭 · 400 이 인증보다 앞) · backend/qa BLOCK — **핵심 배선 행위 테스트가 0건이라 ZIP 이 토글을 완전히 무시하도록 만들어도 69건 전건 통과**했음이 뮤테이션으로 실증(라우트를 직접 통과시키는 B1~B6 신설 후 같은 뮤턴트로 red 재확인) · `rsplit(".",1)` 이 선행점/끝점 이름을 파괴 · ZIP 이 실패 행 이름을 소비하지 않아 manifest 와 재배정 불일치 · ux BLOCK — **P1 `모든 버전` 라디오 힌트가 토글 OFF 에서 체크박스와 정면 모순(사용자 대면 거짓 진술)** · localStorage 쓰기 실패 시 표시-집행 괴리 · 탭 간 동기화 부재 · 충돌 경고가 SR 에 무음. **계약 정정**: 라벨 "포함"→"**유지**" — 켜도 없던 표시를 새로 만들지는 않는다(사용자 재업로드 버전은 저장명에 애초에 접미 없음). **rebase 정합**: 머지 대기 중 main 의 `attach-multi-upload` 가 단일 다운로드에 "v2 이상은 응답 파일명에만 접미 부착" 을 도입했다 — 이는 backend/qa 패널의 P2("토글 ON 인데 사용자 재업로드 체인에는 안 붙는다")를 main 이 먼저 해결한 것이라, 그 규칙을 **`auto` 모드로 흡수**해 규칙 함수 하나로 통일했다(단일·`scope=latest` 기본=auto, `scope=all` 기본=force → **목록 ⬇ 와 ⤓ '최신 버전만' 의 이름이 일치**). **검증**: pytest **82건**(신규 37 + 기존 45) · **PB-0008 실 Windows Chrome 31 step 전건 PASS**(패널 흡수 후 재실행 — 두 안내 상호 정합 · `aria-live` · 모달 높이 417↔416px · 매니페스트 12건 전량 고유) · 서버 계약 실측(단일 4모드 · ZIP 실물 엔트리명 · 이중접미 역검증) — 전부 bind-mount 프리뷰 컨테이너(`:18099`)에서 수행해 **라이브 무접촉**. **캡처 판독 정정**: 모달 토글이 위 두 라디오 그룹과 같은 테두리 박스라 "세 번째 라디오 그룹" 으로 읽혀 구분선 아래로 내렸고, 첫 CSS 수정이 화면에 반영되지 않은 원인은 캐시가 아니라 **소스 순서**(같은 특이성에서 뒤 규칙이 승) 였다. **잔여(정직 표기)**: 모달 focus trap 부재·닫힌 패널의 탭 순서 잔류·첨부 0건에서 ⤓ 미비활성은 **선재 셸 특성**이라 원장 등재만(ux 패널 판정) · 브라우저 저장 대화상자의 실제 파일명은 OS 대화상자라 자동화가 닿지 못해 미확인(서버 결정 이름 → `link.download` 배선까지 검증) · `localStorage` 는 기기·프로필 단위라 다른 기기는 기본값으로 시작(계정 설정 승격은 Minor 범위 밖) · 접미 제거 + 전 버전 조합은 id 구분 접미가 붙어 "깨끗한 이름" 기대와는 다르며 모달 힌트로 고지하는 선에서 멈췄다. **배포 완료(2026-08-07)**: PR #1183 → main `abdf13bd` → `make deploy-web` exit 0(soak·워커 롤아웃 포함) → POST-DEPLOY PB-0008 **31 step 전건 PASS**(배포본 이미지 baked 자산, 라이브 무접촉). 정본 = TASK `20260806T1825-attach-suffix-toggle` · FUNCTION `REQ-20260806-attach-suffix-toggle` · MODIFY/REVIEW `…-attach-suffix-toggle` · TEST `docs/test-runs.d/20260806T1825-attach-suffix-toggle.md`.

**2026-08-06 20260806T1541-attach-manage — 대화 첨부 삭제(버전 선택)·복구·일괄 다운로드** (**Critical §12.3** — 파괴적 데이터 삭제 + 인가 경계 변경, PLAN-APPROVED 2026-08-06. feature-0003 `routers/{attachments,conversations,_audit_infra}.py`·`app.py`·`static/{app/composer.js,app.js,index.html,css/chat.css}`. **신규 테이블·마이그레이션·권한 코드 0**). **사용자 요청**: "첨부파일 목록 중 특정 첨부파일 삭제(일부, 모든 버전에 대해 선택할 수 있도록) / 모든 첨부파일 다운로드 기능 추가(압축, 개별 등 취사 선택 가능)". **정책 충돌 선처리**: 이 요청은 8일 전 사용자 지시로 삭제 UI 를 철회시킨 `ADR-20260729T163000-attach-append-only` 를 정면으로 뒤집는다 — 착수 전 그 사실과 함께 삭제 강도(soft-delete+휴지통)·삭제 주체(업로더+대화 소유자)·다운로드 범위를 확인받고 새 ADR 로 supersede 했다. **실측이 바꾼 설계**: `lifecycle_state` 4-state 와 `restorable_until`(retention 30일)이 **이미 직렬화되고 있었으나 소비처가 0곳**이라 복구 경로가 실재하지 않았고, 삭제 인가는 열람 헬퍼를 재사용해 **그룹 멤버 전원**이 남의 첨부를 지울 수 있었다(선행 ADR 이 "별도 판단 대상"으로 이월한 미해결 이슈 — UI 를 되살리면 함께 살아난다). **구현**: `_manage_gate_for_conversation`(업로더 본인 OR 대화 소유자 + 현재 멤버십, `upload.any` 는 관리 경로) · `DELETE ?scope=version|chain` + 최신 삭제 시 직전 버전 승격 · `POST /restore`(retention·사유 화이트리스트 통과분만) · `?state=deleted` 휴지통 · `GET .../attachments/download`(`format=zip|manifest` × `scope=latest|all`). **§18.8 적대 패널 4도메인 전건 흡수 — codex 채널이 할당량 소진이라 사용자 1회 확인 후 subagent 로 대체(§18.8.2, 자체 SKIP 금지)**: security P1×3(신규 audit 액션 2종이 builder allowlist 부재 → `ValueError` 를 `_audit_user_action` 이 삼켜 **감사 행 0** · 일괄 다운로드가 공유창 window 미적용으로 bounded 멤버가 floor 이전 첨부 전량 ZIP 반출 = SECURITY §21.2 AR-2/CSO F3 위반 · staged/worktree 괴리) · backend P1×2(**라이브 env 실측 `ATTACHMENTS_READ_BACKEND=postgres`** — PG read 가 프로덕션 목록 경로인데 미러에 강등 형제가 빠져 같은 첨부가 두 줄로 뜸 · 테스트 red) · qa P1×7(fake cursor 가 WHERE·params 를 흉내내지 않아 `RootAttachmentId NULL` 루트 누락·엉뚱한 행 승격·`ConversationId` 스코핑 삭제 뮤테이션이 전부 생존) · ux P1×2(**`_refreshAttachPanelAfterMutation` 이 부른 `_renderAttachmentPills()` 가 같은 컨테이너를 덮어 삭제 직후 방금 지운 파일이 그대로 보임** · 240px 파일명 가용폭 37.8px≈3자·버전 행 23.2px≈2자 붕괴). **자기모순 2건이 특히 뼈아프다** — CSS 주석에 "폭 회귀를 되풀이하지 않는다" 고 적어놓고 그 회귀를 냈고, "pill 정합" 을 주석으로 선언한 함수가 정합을 달성하지 못했다. **검증**: 신규 pytest **45건**(params 값 단정으로 재작성 — SQL 문자열만 보면 바인딩 오류가 통과한다) · **PB-0008 실 Windows Chrome 폭 실측 PASS**(240/280/360px 전 구간, 파일명 103.3/143.3/223.3px·배지·토글 잘림 0) + **역검증에서 수정 전 배치가 FAIL 재현**(240px 46.9px) · route golden 224→226(제거 0) · ROUTEMAP 재생성. **잔여(정직 표기)**: 삭제·복구·다운로드 **e2e 흐름**은 라이브 서버·MinIO·PG 미러가 함께 필요하고 정적 자산이 이미지에 baked 되어 사전 QA 가 성립하지 않아 **POST-DEPLOY 이월**(fragment 에 체크리스트 8항목) · 복구 시 size cap 우회 · ZIP 동시성 제한 · 엔드포인트 레벨 요청 테스트 · 개별 다운로드·목록의 window 선재 갭. 정본 = TASK `20260806T1541-attach-manage` · FUNCTION `REQ-20260806-attach-manage` · DECISIONS `ADR-20260806T154100-attach-manage` · MODIFY/REVIEW `…-attach-manage` · TEST `docs/test-runs.d/20260806T1541-attach-manage.md`.
**2026-08-06 20260806T1830-modal-dismiss-siblings — 배경 dismiss 를 저장소 단일 primitive 로 통일(전 표면)** (Minor §12.3 — feature-0003 `static/modal-dismiss.js`(신설)·`app.js`·`app/profile.js`·`admin/{usage,audit}.js`·`graph/graph-core.js` frontend-only. **백엔드·API·RBAC·스키마 0**). **사용자 요청**: "동형 오버레이의 형태 또한 정합하게 구성해주세요"(선행 cycle 완료 보고에서 표면화한 잔존 3곳 승인). **왜 공용 모듈인가**: ESM 번들이 둘(작업 화면 `app.js` / 관리 콘솔 `admin.js`)이라 primitive 를 한쪽에 두면 다른 쪽은 **복제**할 수밖에 없고, **그 복제가 애초에 이 결함을 만든 기전**이다(판정이 9곳에 흩어져 6곳 `click`·3곳 `mousedown` 으로 굳어 있었다). **변경**: `static/modal-dismiss.js` 를 정본으로 신설하고 `app.js` 가 import 후 **re-export**(sidebar 무회귀), 전 표면 11곳 배선 — 승인받은 3곳(프로필 사용 내역 `mousedown` 단독 · 관리 콘솔 사용 기록 `mousedown` 단독 · 감사 purge `click`) + **요청 범위 밖 2건(명시)**: 그래프 뷰 도움말 오버레이(마지막 남은 배경-클릭 dismiss)와 **대화 검색 모달**(같은 계약을 손수 중복 구현 — 전용 상태 플래그 2개 제거). **프로필 드로어는 의도적 제외** — backdrop 과 패널이 `index.html:410-411` 에서 **형제**라 target 승격이 구조적으로 불가(양 리뷰어 독립 검증). **§18.8 패널(ux SHIP / design BLOCK) 지적 전건 반영 — 넷 중 셋이 "이 cycle 이 한 일을 내 산출물이 거짓 인증"**: ① census 가 "전 트리" 라 단정했으나 실제로는 **33개 중 6개 하드코딩** — TREE 밖 신규 파일에 옛 패턴을 심어도 73/73 통과(뮤테이션 실증) → 재귀 walk + 핸들러 본문 경계 판정으로 교체 ② **vacuous 단언 2건**(우클릭·비-primary)이 `press()` 헬퍼 탓에 판정 단계에 도달조차 못해 가드를 지워도 생존 → click 명시 발화·순서 교정으로 재작성 ③ ESC 리스너 하드닝이 **절반**(재렌더 경로 누수 잔존)인데 정규식 단언이 "누수 0" 을 인증 → `overlay._modalClose` 로 완결 + **수명 실측** 테스트로 교체 ④ `FUNCTION.md` AC-0168 이 삭제된 구현을 계약으로 기술 → primitive 위임으로 갱신. 추가로 purge 모달 **중복 인스턴스 가드**(없으면 겹친 오버레이의 중복 id 로 위쪽 모달 버튼에 핸들러가 안 붙어 파괴적 플로우가 조작 불능) + 잠재 TDZ 순서 교정 + stale 주석 정정. **자체 적발**: 도움말에 이중 바인딩했다가 CSS 확인 결과 자식이 `inset:0` 으로 전면을 덮어 오버레이 바인딩이 dead code 이고 내 주석이 사실과 달라 단일 표면으로 축소. **검증**: 하네스 **76 pass/0 fail**(동작 18 + 배선 52 + 리스너 수명 실측 6) · **뮤테이션 역검증 6종** 전부 의도한 단언만 red(그중 3종은 교정 전 생존 = vacuous 였다) · PB-0008 실 Windows Chrome **10/10**(negative 에서 사용자 보고 현상 3건 재현) · `make test` 회귀 · 전수 mjs red 21건 = main baseline 동일. **범위 경계**: 드롭다운·컨텍스트 메뉴의 `document` 레벨 outside-click 해제는 같은 뿌리지만 **다른 UX 범주**라 대상 밖 — "배경 dismiss 잔존 0" 은 그 경계 안에서만 참. **잔여**: 배포 후 신규 전환 5종 라이브 재확인 · 포커스 트랩 부재(전 표면 공통·기존). 정본 = TASK `20260806T1830-modal-dismiss-siblings` · FUNCTION `(modal-dismiss-siblings, 2026-08-06)` · REVIEW `REV-20260806T183000-modal-dismiss-siblings` · TEST `docs/test-runs.d/20260806T1830-modal-dismiss-siblings.md`.

**2026-08-06 20260806T0327-share-sender-nickname — 공유 링크 화면의 발화자 배지를 메시지별 발신자(닉네임)로** (Major §12.3 — feature-0003 `static/{share.js,share.css}` + `routers/share.py` payload 불리언 1개. **RBAC·스키마·마이그레이션 변경 0**). **사용자 보고**: "서비스 내 대화를 공유하여 링크를 통해 생성된 대화 내역에서 각 사용자는 닉네임이 아닌 '사용자' 라는 명칭이 고정되며 나타나고 있습니다. 고유한 닉네임이 공유된 링크 웹페이지에서 나타나도록 개선해주세요." **근본 원인**: `share.js renderMessage()` 가 배지를 `roleLabel(msg.role)` 로만 채워 user 역할이면 무조건 "사용자" — 작업 화면(`app.js`)이 갖는 `sender_username`→`사용자 <id>`→소유자 폴백 계층이 공유 뷰에는 이식되지 않았다(msg-speaker-attribution 각인의 **소비처 누락**). **데이터는 이미 있었다(실측)**: 라이브 활성 공유 링크를 익명 호출해 payload 를 확인한 결과 그룹 발신 메시지에 `{"group_chat":true,"sender_username":"admin","sender_account_id":10}` 이 그대로 실려 나오고 있었다 — `_share_load_messages` 가 표시 store `meta_json` 을 통째 전달하기 때문. 즉 서버에 없어서가 아니라 **화면이 그 값을 안 쓰고 있었다** → 백엔드 무변경으로 해소. **변경**: `senderLabel(msg)` 신설 — 지배 규칙은 **"발화 시점에 각인된 사실일 때만 사람 이름"**(0순위: `attribution_inferred` 추론 각인은 이름·id 둘 다 미사용 → 1: `sender_username` → 2: `사용자 <id>`(소유자명 오귀속 금지) → 3: 대화 소유자명(**1:1 확인 시에만**) → 4: 종전 `사용자`). 말풍선 배지와 우측 point rail 툴팁/aria 를 그 **단일 출처**로 통일(한 화면 두 이름 방지), `render()` 가 payload 로 폴백 기준·그룹 게이트 갱신, `routers/share.py` 가 `conversation.is_group` **불리언 1개**를 추가(fail-closed — 조회 실패·행 부재는 그룹 간주). 레이아웃은 `.share-role-badge` 폭 제한 + ellipsis **와 함께** `.share-message-time { flex:0 0 auto; nowrap }`(배지만 막으면 시각 표기가 눌려 2줄로 접힌다) + ≤720px 절단 대신 `flex-wrap`, `title` 은 실제 절단 시에만. **사용자 결정(2026-08-06)**: 노출 범위 = 모든 열람자(익명 포함) · 각인 없는 과거 메시지 = 대화 소유자명 폴백. **표시 경계 근거**: `docs/SECURITY.md §21.7` — 백엔드 노출면은 사실상 불변이나 **실질 열람자는 넓어진다**(종전엔 개발자도구로 응답을 뜯는 사람만 봤다)는 점과 잔여 위험 2종(표시명 PII · 내부 계정 PK 육안 노출)을 정직 기록. window 격리와는 직교(렌더되는 메시지에만 라벨이 붙고, 발화하지 않은 멤버 명부는 여전히 비노출). **§18.8 적대 패널 2렌즈(security·ux) CONCERN medium 5건 전건 in-cycle 흡수** — ① fork 보정의 추론 각인이 원본 대화 owner 이름을 익명 화면에 확정 표기하던 경로 ② 그룹 legacy 행의 소유자명 오귀속 ③ §21.7 노출집합 과소서술 ④ 시각 표기가 밀려 2줄로 접히던 CSS 회귀(패널 360px 실측) ⑤ `title` 무조건 부여로 인한 중복 툴팁·중복 낭독. codex 채널이 사용량 한도로 막혀 **사용자 1회 확인 후** subagent 패널로 대체했다(§18.8.2 — 자체 SKIP 하지 않음). 패널은 동시에 주장 A(발신자명이 이전부터 payload 에 있었음)·XSS 실행 경로 0·window 격리 직교·`inline-flex→inline-block` 무회귀를 코드로 확증했다. **검증**: mjs `verify_share_sender_nickname.mjs` **17/17 green**(배포 소스에서 함수를 추출해 실행 — 로직을 테스트에 재구현하지 않음) · pytest `test_share_sender_nickname.py` 2건 · `make test` 전 스위트 **exit=0**(1회차 `test_shutdown_finalizer` FAIL 은 `시간 예산 초과` flake — 격리·전체 재실행 모두 통과, 본 cycle Python 무접촉) · ruff clean. **잔여**: PB-0008 실 Windows 브라우저 시각검증은 정적 자산이 web 이미지에 baked 되는 구조상 **배포 후** 수행. 차기 후보 = assistant 발화자(제품)의 메시지별 해석(공유 뷰는 여전히 대화 단위 제품 1개), mjs 하네스의 CI 배선. 정본 = TASK `20260806T0327-share-sender-nickname` · FUNCTION `(share-sender-nickname, 2026-08-06)` · MODIFY/REVIEW `…-share-sender-nickname` · SECURITY §21.7.

---

**2026-08-06 20260806T1144-modal-backdrop-dismiss — 사이드바 항목(대화/폴더) 모달: 바깥 배경 "누름+뗌 모두 배경"일 때만 종료** (Minor §12.3 — feature-0003 `static/app.js`·`static/app/sidebar.js` frontend-only. **백엔드·API·RBAC·스키마·마이그레이션 변경 0**). **사용자 요청**: "대화화면 좌측의 항목(대화/폴더) 요소들의 설정 모달에서 바깥의 어두운 배경을 클릭했을때만(mouse down + up) 모달이 종료되도록 구성해주세요. 현재는 마우스를 down or up 되었을 때 모두 종료되는 현상이 확인되었습니다." **근본 원인**: 좌측 항목에서 열리는 backdrop 모달이 전부 `backdrop.addEventListener("click", e => { if (e.target === backdrop) close(); })` 였는데, DOM `click` 의 target 은 mousedown/mouseup 두 지점의 **공통 조상**이라 패널 안에서 시작한 드래그가 배경에서 끝나면(그 반대도) target 이 backdrop 으로 **승격**돼 닫혔다 — 폴더 지침 textarea 에서 드래그 선택 중 손이 밖으로 나가면 작성분이 통째로 사라진다. **변경**: 판정을 `click` 에서 떼어내 `pointerdown`(누름)·`pointerup`(뗌) **2단 계약**으로 옮기고(둘 다 backdrop 자신일 때만 성립), **실행만** 이어지는 `click` 이 트리거하는 primitive `bindBackdropDismiss` 를 신설해 6개 모달(대화 설정·공유·공유 링크 설정·참여 허용 확인·폴더 설정·폴더로 이동)에 단일 배선. 상태는 **제스처 1회분**만 산다 — `pointerup` 이 누름을, `click` 이 장전을 소비하고, 선행 pointerdown 없이 오는 click 은 정의상 합성이라 `e.isTrusted` 로 배제한다. 터치·펜의 **implicit pointer capture** 는 배경에서 시작한 제스처에 한해 무조건 해제한다(패널 안 제스처의 캡처는 터치 텍스트 선택이 의존). **§18.8 ux·design 적대 패널이 2 라운드에 걸쳐 BLOCK** 했고 지적이 전부 실재해 반영: ① **implicit pointer capture** — 해제하지 않으면 터치에서 계약이 "누른 위치만" 으로 무너져 **원 결함이 그대로 남아 있었다** ② **ghost click** — `pointerup` 에서 노드를 제거하면 터치 compat click 이 배경 아래 사이드바 항목을 누른다 ③ **장전 잔류** — 두 리뷰어가 **독립적으로 실제 헬퍼를 실행해** 실증: click 을 발행하지 않는 제스처가 장전을 무기한 남겨 뒤이은 click 하나가 누른 적 없는 모달을 닫았다(내 코드 주석의 "합성 click 은 dismiss 를 일으키지 않는다" 단정이 상태 의존적으로 거짓이었다) ④ 캡처 해제의 fail-open 게이트·`pointerup` 의 중복 button 검사·부정확한 주석 근거. **검증**: 신규 하네스 `verify_modal_backdrop_dismiss.mjs` **48 pass/0 fail** + **역검증 5종**(옛 `click` 단독 11 fail · 캡처 해제 삭제 1 · `pointerup` 실행 3 · `downOk` 미소비 1 · `isTrusted` 미검사 1 — 각 방어가 독립적으로 load-bearing) · **PB-0008 실 Windows Chrome PASS 10/10** — 합성 JS 이벤트가 아니라 CDP trusted 입력(`Input.dispatchMouseEvent`/`dispatchTouchEvent`)으로 마우스·터치 제스처를 실측했고, **같은 하네스를 수정 전 구현으로 돌린 negative control 에서 사용자가 보고한 현상 3건이 그대로 재현**(안→밖·밖→안·지침 드래그 이탈이 전부 모달을 닫음) · `make test` 회귀 · `verify_*.mjs` 전수 red 21건 = main baseline 동일 집합(신규 red 0). **커버리지 정정(정직성)**: 1차 "6곳 전수" 근거는 식별자 `backdrop` 키잉 grep 이라 **변수명의 부재만** 증명했고, design 리뷰어 반증으로 `overlay` 명명 동형 3곳(`app/profile.js:306` **사용자향·mousedown 단독** · `admin/usage.js:662` · `admin/audit.js:317`)이 확인됐다 — 요청이 "좌측 항목 모달" 로 명시 스코프돼 이번 cycle 미적용, §8 원장 등재 + 사용자 표면화. **잔여**: 배포 후 라이브 작업 화면에서 실제 6개 모달 육안 재확인(fragment Run 3 append) · 위 3곳 · 포커스 트랩 부재(기존) · 미저장 지침 dirty-guard. 정본 = TASK `20260806T1144-modal-backdrop-dismiss` · FUNCTION `(modal-backdrop-dismiss, 2026-08-06)` · MODIFY/REVIEW `…-modal-backdrop-dismiss` · TEST `docs/test-runs.d/20260806T1144-modal-backdrop-dismiss.md`.

**2026-08-04 20260804T0610-msg-speaker-attribution — 대화내역 발화자(사용자 · assistant 제품)의 사후 변경 차단** (Major §12.3 — feature-0003 `static/app.js`·`routers/{_conv_store,conversations}.py`·`app.py` + feature-0002 `agent_core.py`. **신규 권한·엔드포인트·스키마·마이그레이션 0**). **사용자 보고**: "서비스 내 대화내역에 남는 대상(사용자, assistant의 product) 들이 기존 내용과 정합하도록 구성해주세요. 현재는 대화를 fork 하거나, product를 바꿈으로서 이전에 진행했던 대화의 발화자가 실시간으로 변경되어 버리는 부정합". **근본 원인**: 발화자가 메시지에 각인되지 않고 **렌더 시점의 대화 설정**에서 파생됐다 — assistant 는 `renderMessages` 상단에서 `state.pinnedProductId`(컴포저 제품 칩)로 만든 **단일 값**을 전 말풍선이 공유했고(칩을 바꾸는 순간 과거 답변 아바타가 전부 새 제품으로 바뀜, 전환 토스트 "다음 답변부터 적용됩니다" 와 정면 배치), user 는 `agent_core` 가 발신자 meta 를 **그룹 발신에만** 각인해 1:1 메시지가 미각인 → FE 가 대화의 **현재 owner** 로 폴백 → fork 본(owner=복제자)에서 원저자의 질문이 전부 복제자 이름으로 표시. **변경**: ① **저장 시점 각인**(1차) — `_answer_product_attribution`/`_lookup_account_username` 신설, user 미러 meta 를 1:1 까지 확대(`group_chat` 마커는 종전 게이트 유지), assistant 미러 **4경로 전부**(정상 답변·max_steps 초과·중단 보존·오류)에 `product_mode/product_id/product_key/product_name` 각인 ② **freeze-on-change**(2차) — `PATCH …/product` 가 바인딩 교체 **직전** 미각인 답변을 **직전 제품**으로 고정 ③ **fork/duplicate 보정**(2차) — `_conv_copy_messages(attribution_defaults=…)` 가 미각인 행에 **강등 전 원본 제품 + 원본 owner** 를 고정 ④ **렌더 정합** — `_assistantSpeakerFor()` 가 메시지별 각인에서 해석(라벨·시드는 스냅샷 우선, 아이콘만 현재 제품), user 는 발신자 기반 판정, 전환 성공 후 `loadHistory({preserveScroll:true})`. 보정은 **미각인 행 한정 + 추가만 + fail-open**, 추론분은 `attribution_inferred: true` 로 구분. **검증**: 신규 테스트 29(agent-core 13 + web 16) · 전체 스위트 EXIT=0 · ruff clean · **codex 적대 리뷰 P1 4건 전건 반영**(부분 각인 행 덮어쓰기 · 판독불가 meta 삭제 + SELECT~UPDATE race · fork 한 축 실패가 다른 축 폐기 · sender-id-only 행의 owner 오귀속) · **PB-0008 실 Windows Chrome PASS** — kumin 대화를 bootstrap_admin 이 fork 해도 `kumin`·`건즈 글로벌 QA` 유지, 칩을 `GZ_QA_G`→`KR_QA` 로 실제 전환해도 과거 6행 불변(새로고침 후에도), legacy 미각인 대화에서는 칩과 어긋난 제품으로 렌더되던 버그를 **라이브 재현 후** freeze 가 직전 제품으로 정정. **잔여**: fork·제품 전환을 겪지 않은 legacy 대화는 미각인으로 남아 종전 폴백(그 상태에서는 표시가 정확) — 전량 일괄 backfill 은 라이브 전 대화 meta 를 쓰는 대규모 변경이라 불채택. auto 모드 답변의 "AI" 배지 확정과 그룹 다중 발신자 fork 는 단위 테스트만(라이브 미실측, 사유 명시). 정본 = TASK `20260804T0610-msg-speaker-attribution` · FUNCTION `(msg-speaker-attribution, 2026-08-04)` · MODIFY/REVIEW `…-msg-speaker-attribution` · TEST `docs/test-runs.d/20260804T0610-msg-speaker-attribution.md`.

---

**2026-08-03 20260803T1549-aiops-taxonomy-unmapped — `AI 운영 현황 > 운영 현황` 의 '미분류 활동' 3종 재배치** (Minor §12.3 — `shared/model_catalog.py` `TASK_TAXONOMY` 3행 + feature-0003 회귀 테스트. **엔드포인트·RBAC·스키마·프론트·마이그레이션 변경 0**). 사용자 요청: "미분류 활동으로 구성된 항목들을 적절하게 재배치". **진단(라이브 PG 실측)**: `agent_runtime.llm_usage` DISTINCT task 16종 중 3종이 taxonomy 미등록이라 `taxonomy_for()` 폴백으로 `ai.other.unmapped` 에 누적 — `analysis_verify`(1,258회, feature-0036 분석문 사실성 판정) · `cluster_summary`(332회, feature-0034 콘텐츠 그룹 요약 L2) · `domain_summary`(4회, feature-0037 스키마=도메인 합성 요약 L3). 셋 다 `conversation_id='__insight_worker__'` 단일이고 target 축이 객체/데이터소스/스키마라 insight 분석 파이프라인 산출물로 확정 → **`ai.insight.analyze`(인사이트 분석)** 로 편입(라벨: 콘텐츠 그룹 요약 / 도메인 종합 요약 / 분석문 사실성 검증). 부수로 Attention 의 "미분류 AI 활동" 배지가 사라지고 `LLM 사용량 > 사용 기록` 의 raw task 문자열이 사람이 읽는 작업명으로 노출된다. **재발 방지**: 같은 결함이 2026-07-28 에도 4종으로 발생한 반복 패턴이라 dict 대조가 아니라 **호출부 AST 전수 게이트**를 걸었다 — `_record_llm_usage` 의 task 리터럴(직접·래퍼 경유 19종)이 전부 taxonomy 에 있어야 하고, 정적 확정이 불가능한 경로(f-string 파생)는 파생 규칙을 선언해 산출 집합 동치를 요구하며, **미확정 경로(`*args`/`**kwargs`/지역변수/재바인딩/shadowing/별칭 참조)는 통과 대신 실패**한다(fail-closed). **검증**: `test_ai_ops.py` 22 PASS · 전체 스위트 EXIT=0 · ruff PASS · taxonomy 변이 7종 + 미확정 경로 변이 12종 전건 적발(대조군만 통과) · codex 적대 리뷰 8라운드(제품 코드 지적 0, 전부 게이트 정밀화). **잔여**: `getattr` 문자열·exec 등 AST 밖 경로는 원리상 정적 확정 불가 — 게이트 계약을 "미확정을 조용히 통과시키지 않는다"로 명시. POST-DEPLOY 라이브 대조는 배포 후 `docs/test-runs.d/20260803T1549-aiops-taxonomy-unmapped.md` §4 에 기록.

**2026-07-29 TASK-20260729T2010-progress-enqpre-handoff — 요청 직후 말풍선이 '시작 중…' 에 박제되던 결함: enqueue sentinel → 실제 run 승계** (Major §12.3 — feature-0003 프론트 `static/app.js` 단독. **백엔드·RBAC·스키마·엔드포인트·alembic 변경 0**). **사용자 재보고(스크린샷)**: "여전히 요청을 보낸 직후에는 다음 말풍선에서 변동사항이 없다(다른 대화로 전환 후 복귀하면 정상)" — 화면은 상태 '처리 중' · 단계 '시작 중…' · **경과시간 1분 50초**. 즉 폴링은 살아 있고 응답도 받는데 **steps 만 반영되지 않는** 상태로, 선행 cycle(TASK-20260729T1750, 폴러 사망 축)과 **원인이 독립**이다. **근본 원인**: 워커 모드 `/api/ask` 는 enqueue 시점에 `enqpre-<uuid>` **sentinel** 을 KV run_id 로 선기록하고(`routers/_conv_store.py` — enqueue~claim 갭의 '처리중' 가교 + TASK-0241 orphan clobber 가드용), ask-worker 가 claim 하면 **claim 별 실제 run_id**(`modules/ask.py` `_new_run_id()` → `agent_core` `set_run_status`)로 덮어쓴다. 전송 직후 첫 폴(0ms)이 그 sentinel 을 받아 `progressRunId` 로 고정하면, 실제 run 으로의 **정상 승계**가 feature-0009 **foreign-run 가드**에 "다른 사용자의 동시 run" 으로 오인돼 **매 응답이 early-return 으로 버려졌다** → 상태는 첫 응답 1회만, steps 는 영원히 빈 채 박제(경과시간은 별도 타이머라 계속 흐름). 워커 claim 이 tick 1~2초 뒤이므로 첫 응답이 sentinel 인 것이 정상 타이밍 = **사실상 매 요청 재현**. **변경**: `ENQUEUE_SENTINEL_RUN_PREFIX`/`_isEnqueueSentinelRunId`/`_adoptRunId` 신설 + **채택 choke-point 를 `resetProgressTracking` 단일화**(전송 직후·`loadHistory` `last_run_id`·`ask_status` attach 전 경로) → sentinel 은 추적 id 로 채택하지 않고 실제 run 을 그때 채택 · `applyProgressPayload` run 채택·`pendingBubble.runId` 동일 필터 + 가드에 2중 방어 · `startProgressPolling`/`loadHistory` 전환 판정도 채택값 기준(진행 중 steps 헛초기화 방지). **그룹 foreign-run 불변식 무손상** — 가드는 "실제 run vs 실제 run" 에만 적용된다. **검증**: 신규 `verify_enqpre_run_handoff.mjs` **27 PASS / 0 FAIL**(C1 미채택·**C2 승계+steps 반영**·C3 그룹 보존·C4 terminal 보존·C5 2중 방어·C6 채택 규약·정적 5), **수정 전 코드에선 18건 FAIL**(C2 포함) · 기존 `verify_progress_poll_resilience` 45 · `verify_run_detect_poll` 35 · `verify_model_persist` 49 PASS 회귀 0 · `make test` **FAILED 0**·ruff PASS. **진단 누락 정직 기록**: 선행 cycle 의 PB-0008 1차 관측에 이미 `runId: "enqpre-ae58dc20…"` + `stepText: "시작 중…"` 이 찍혀 있었는데 "아직 단계 없음" 으로 읽고 넘겼다 — 관측 로그의 정체불명 id 를 그 자리에서 추적하지 않아 같은 증상을 두 번 고쳤다. **POST-DEPLOY PB-0008 라이브 PASS**(배포본 `6a8f7f5a`): BEFORE/AFTER 동일 시나리오 대조 — sentinel 구간 추적 id 빈 값 유지 → t+20s 실제 run `20260730070324-ffbd546c` 채택 → **프론트 steps 가 서버 step_count 추종(3→6)** + 화면 단계가 실제 내용('AI 가 질문을 분석…' → '답변을 자가 검증하는 중 (red-team 리뷰)')으로 갱신 + '6단계 보기' 노출, **대화 전환 없이**. BEFORE 는 서버 3→6→7 을 보내는데 프론트 끝까지 0·'시작 중…' 박제. 부기(정직): 큐 대기 구간의 상태 라벨이 '처리 중'(sentinel 반영) → '시작 중'(정직 표시)으로 바뀌었고 실행 시작 시 즉시 '처리 중'+실제 단계로 넘어간다. **후속 과제**: codex P1-1(그룹 동시 전송 1~2초 창의 foreign 오귀속)은 서버 `run_is_mine`(ask_jobs.account_id) correlation 이 필요 — 프론트 단독 해결 불가. 정본: TASK/CHG/REV-20260729T201000-progress-enqpre-handoff · FUNCTION REQ-20260729T201000(AC-EPH-1~4).

---

**2026-07-29 metadata-product-scope — 지식베이스 메타데이터 스코프 축을 '데이터소스' → '제품' 으로 전면 재구성** (Major §12.3 — cross-cut: `shared/config.py` 축 정의 · feature-0002 읽기/쓰기 seam · feature-0003 admin API·콘솔. **신규 권한 0 · 스키마/마이그레이션 0**). **사용자 요청**: "관리 콘솔 > 지식베이스 > 메타데이터 에서 사용하는 정보들이 '데이터 소스' 단위로 구성되어 있지만, 실제 사용자들은 제품(Product) 단위로 작업 범위를 인식합니다. 실제 사용자들이 인식하는 범위와 모든 메타데이터의 구성이 정합하도록 전면적으로 재구성해주세요." **진단(라이브 실측)**: 축이 **양방향으로** 어긋나 있었다 — 1제품↔N데이터소스(`KR_LIVE`·`KR_QA` 각 **7개 DS**, `MV_QA` 3개)에서는 한 제품의 메타데이터가 조각나고, 1데이터소스↔N제품(`mssql-qa-idc` 하나를 **FH_QA·CC_QA·DK_QA·SR_QA·AO_QA 5개 제품**이 공유)에서는 테이블설명 153·컬럼설명 1,046건이 5개 제품 것으로 뒤섞였다. **화면 문제로 끝나지 않았다** — 질의 시점 주입 스코프가 `[활성 datasource, common]` 이라 `KR_LIVE` 용어 85건이 `mysql-kr-an1-auth` 에만 등록돼 나머지 6개 DS 질의에서는 미주입이었다(사용자는 "제품에 등록했다"고 인식하지만 실제로는 7분의 1에서만 작동). **변경**: ① 스코프 키 `product.<ProductKey>` 신설 + 활성 제품 ContextVar(`set_active_product`/`get_active_product_scope`/`is_product_scope_unresolved`) ② KB 읽기 seam 4곳(용어사전·ENUM·테이블/컬럼 설명·샘플쿼리) + describe_table 오버레이를 제품 축으로 — 제품은 run 전체에 고정이라 멀티-DS 라우팅과 무관하게 같은 사전이 주입된다 ③ 자율수집 쓰기도 제품 귀속, **제품 해소 실패 시 수집 중단**(`common` 폴백은 cross-product 누출) ④ `GET /api/admin/metadata/scopes` 신설 + scope 검증 축 교체 + 부트스트랩을 **제품 접근DB(`WebProductDatabases`) allowlist** 로 한정(밖은 404, 카탈로그 미가용은 503 fail-closed, 호출자 `datasource` override 제거) ⑤ 콘솔 스코프 선택기·목록·검토큐·스키마 골격·안내 문구를 제품 축으로(그래프 뷰 pane 은 datasource 축 유지 — 물리 스키마 투영, 사용자 결정상 범위 밖) ⑥ **expand/contract** — 배포↔이관 창에 레거시 ds-scope 꼬리 읽기(`AGENT_KB_LEGACY_DS_SCOPE_READ`, 기본 on)로 기존 메타데이터 비가시를 막고 이관 후 contract ⑦ ENUM self-heal sweep 을 제품 스코프로(단일 DS 제품 한정 — 다중 DS 제품은 `known_schemas` 불완전로 오삭제 위험) ⑧ 이관 스크립트 `scripts/kb_scope_rescope.py`(7테이블·백업 강제·SQLSTATE 23505 한정 중복 병합·`--verify-contract`). **데이터 처리(사용자 승인)**: 실측 5,405건 중 **5,130건(95.0%)이 제품에 결정론적 귀속 가능**(단일제품 DS 2,004 + 공유DS schema 귀속 3,126) → 이관, 모호 257건 삭제, common 18건 불변. 전량 삭제 지시였으나 실측 결과를 보고해 "귀속 가능분 이관 + 모호분만 삭제" 로 재확정받았다. **검증**: `make test` 전 스위트 PASS·ruff clean, **codex 적대 리뷰 10라운드(P1 12건 + P2 3건 흡수 → 최종 0건)**, 이관 dry-run 라이브 대조. §18.8 `ux`/`design` subagent 는 세션 도구 제약으로 `[SKIPPED:tool-restricted:ux,design]`(§18.8.2 상위 지시 carve-out), 대체 채널로 커버. POST-DEPLOY = 라이브 이관 → contract → PB-0008 시각검증. 정본 = TASK `20260729T2130-metadata-product-scope` · FUNCTION `REQ-20260729T213000-metadata-product-scope` · MODIFY `CHG-20260729T213000-metadata-product-scope` · REVIEW `REV-20260729T213000-metadata-product-scope`.

### Git 동기화 결과 (metadata-product-scope)
- 커밋: (아래 cycle commit) (`ai/root/metadata-product-scope`)
- verify-completion: PASS
- Push: 완료
- main 병합: PR 경유
- 충돌 해결: 없음

**2026-07-29 TASK-20260729T1750-progress-poll-resilience — assistant 말풍선이 '처리 중' 에서 갱신되지 않고 대화 전환-복귀로만 되살아나던 결함** (Major §12.3 — feature-0003 프론트 `static/app.js` 단독. **백엔드·RBAC·스키마·엔드포인트·alembic 변경 0**). **사용자 보고(재발)**: "요청을 전송한 후 assistant 말풍선이 '요청 중' 에서 갱신되지 않고, 다른 대화로 전환했다가 돌아오면 현황이 갱신된다." **근본 원인 — 회복 타이머가 전부 사라진다(3중)**: ① `pollProgress` 의 `errorCount < 3` 게이트가 **연속 3회 실패 시 재스케줄을 영구 포기** → 이 대화의 유일한 갱신 채널(`/api/progress`)이 소멸. 3연속은 흔한 조건이다(롤링 배포 창 — 라이브 엣지 로그에 5.0s dial-timeout·`/api/ask` 502 실측 · 4초 fetch 타임아웃 · 20~30초 네트워크 순단 × 8초 백오프). ② 유휴 감지기 `detectNewRun` 의 dormant 판정 근거가 `progressRunId || pendingBubble` 인데 **이 둘은 폴러가 죽어도 남는 잔여값** → 감지기도 영구 dormant. ③ `loadHistory` processing 분기가 감지기를 아예 정지. → 서버는 답변을 정상 완료했는데 화면만 박제되고, **대화 전환-복귀(`loadHistory` 재실행)가 유일한 복구 경로**였다 = 사용자가 보고한 그 동작. **변경(5건, 전부 비파괴·가역)**: **F1** 실패 시 포기 대신 지수 백오프(8s→16s→32s→상한 60s) 무한 재시도 + 성공 시 리셋 · **F2** dormant 판정을 "폴러 생존"(`progressPoller || progressPollInFlight`) 사실로 교정하고 baseline 분기의 `runId !== progressRunId` 비교 제거(이 비교가 "죽은 폴러가 추적하던 바로 그 run" 을 회복 대상에서 배제하던 마지막 자물쇠) · **F3** 감지기를 **watchdog 으로 승격** — processing 중에도 무장하되 폴러 생존 시 dormant(fetch 0회, 네트워크 비용 0), 폴러가 끊긴 순간에만 깨어나 `loadHistory` 로 회복(사용자가 수동으로 하던 복구의 자동화) · **F4** 탭 재가시 판정에 `display_status`·`pendingBubble` 포함 + 감지기 항상 재무장 · **F5** `online` 이벤트 훅(회선 복구 시 백오프 잔여 대기 없이 즉시 재무장). 소진된 `setTimeout` tick 이 stale id 로 남지 않게 콜백 진입 시 참조 정리(F2 판정의 진실 소스). **§18.8 대체 리뷰가 실제 회귀를 잡았다**: 세션 지시(Agent tool 금지)와 정책 충돌을 자체 SKIP 하지 않고 사용자 확인 후 `/codex review` 로 대체한 결과 **P1 1건**을 적발 — 그룹 대화에서 내 run `R1` 추적 중 폴러가 죽고 다른 멤버의 `R2` 가 슬롯을 점유하면, watchdog 의 감지 fetch 가 `client_run_id` 를 싣지 않아 `R2` 를 받고 `loadHistory` 가 폴링을 남의 run 으로 갈아태워 **내 run 의 per-run terminal marker 를 영영 못 받는다**(= 고치려던 고착의 다른 경로 재현). 수정 전에는 `pendingBubble` dormant 가드가 막던 경로를 내가 열었다. **수정(F6)** 은 codex 제안보다 한 걸음 앞에서 끊었다 — *죽은 폴러의 회복은 그 폴러를 되살리는 것*이지 서버에 "현재 슬롯 run" 을 묻는 것이 아니므로, `progressRunId` 가 있으면 **fetch 없이** 그 run 으로 폴링만 재기동한다(foreign run 을 받을 기회 소멸 + 네트워크 비용 0). **P2**(감지 fetch 가 abort 되지 않아 재무장이 비멱등)도 `state.runDetectAbortController` 로 수정(**F7**). 나머지 P2(서버 오류 지속 시 60초당 1회 무기한)는 수용 — 상한을 되살리면 본 cycle 이 고친 결함이 그대로 복원되고, 서버측 stale 판정이 `processing` 영구 잔존을 막으며 숨김 탭은 완전 정지한다(정상 폴링 대비 1/50 부하). **검증**: 신규 `verify_progress_poll_resilience.mjs` **45 PASS / 0 FAIL**(가짜 state·fetch·timer 로 두 함수를 실제 구동 — 정적 문자열 tautology 회피), **수정 전 코드에 되돌리면 12건 FAIL**(`[F1-persist]`·`[F2-watchdog]` 포함)로 회귀 가드 유효성 실증 · 기존 `verify_run_detect_poll.mjs` 를 새 계약으로 갱신(28→**35 PASS / 0 FAIL**) — FAIL 했던 6건은 **옛 결함을 고정하던 단언**이라 그대로 두면 회귀 가드가 아니라 결함 보호막이 된다(dormant 의 본래 의도는 폴러 생존 기준으로 보존 + "폴러 사망→watchdog 회복" S4b 신설) · feature-0003 mjs 스위트 main 대조 **신규 실패 0** · `make test` **13 FAILED = main baseline 동일**(worktree 격리 네트워크의 attachment PG 의존, 본 변경 Python 무접촉)·ruff PASS. **범위 밖(정직)**: `/api/ask` 가 200~300초 동기 응답으로 연결이 끊기는 문제(엣지 로그 `status=0` 다수)는 별개 축 — 본 cycle 은 그 상황에서 **화면이 죽지 않게** 하는 복원력만 다룬다. **POST-DEPLOY PB-0008 라이브 PASS**(배포본 `8df5edb9`, 실 Windows Chrome/150 전용 탭·타 세션 탭 무접촉): ① 실 사용자 경로(전송→pending→답변 도착) 무회귀 ② **순단 3연속 실패에도 폴링 생존**(수정 전이면 여기서 영구 정지)+백오프 **8→16→32s** 실측 ③ 폴러 강제 사망 → **감지기가 15초 내 되살림**(내 run_id 유지 = codex P1 수정분 F6 실증) ④ `online` 이벤트 → **4초 내 재개+errorCount 리셋** ⑤ 콘솔 에러 0. **미실증(정직)**: OS 레벨 NIC 단절은 재현하지 않고 `fetch` 레벨 차단으로 대체(클라이언트 폴링 관점에서 동일한 실패 신호), 1차 검증용 대화 1건이 라이브에 잔존. 정본: TASK/CHG/REV-20260729T175000-progress-poll-resilience · Run=test-runs.d/20260729T175000-progress-poll-resilience.md.

---
**2026-07-29 TASK-20260729T1742-product-picker-keynav — 제품 선택 드롭업: 검색 후 방향키 순회 + Enter 선택** (Minor §12.3 — frontend-only `static/app.js`·`static/styles.css`. **백엔드·RBAC·스키마·엔드포인트·마이그 0**). **사용자 요청**: "제품 명칭을 검색한 후 방향키('↓') 입력 시 이후 방향키를 통해 검색된 목록에 대하여 순회 … (최상단에서 다시 '↑' 입력 시 검색 텍스트박스로 복귀) … 'enter' 키를 누를 경우 해당 제품을 선택." **진단**: 제품 ≥6 이면 sticky 검색칸이 뜨고 열릴 때 자동 포커스까지 되지만(REQ-20260618-0317·AC-PPSC-3) 그 뒤가 끊겨 있었다 — 항목은 `div[role=menuitem][tabindex=0]` 이라 **Tab 으로만** 도달하고 `↓` 는 브라우저 기본 스크롤만 일으켰다. 즉 "검색으로 좁히고 → 마우스로 클릭" 이라는 반쪽 키보드 흐름. Tab 순회조차 검색으로 숨겨진 항목(`.hidden`)·선택 불가한 열람 전용 행(`.is-view-only`)을 훑어 결과 목록과 어긋났다. **변경**: ① `productDropupNavItems(menu)` — 순회 대상 = 보이는 + 선택 가능한 항목만 ② `focusProductDropupItem` — `focus({preventScroll:true})` + 메뉴 자신의 `scrollTop` 최소 보정(위로 갈 땐 sticky 검색칸 높이 차감, `scrollIntoView` 미사용 = 조상 스크롤 오염 회피) ③ `moveProductDropupFocus` — ↑/↓ 이동, **최상단 ↑ → 검색칸 복귀**(+`scrollTop=0`), wrap-around 없음 ④ 검색칸 `keydown`(ArrowDown, IME 가드 `isComposing` + 레거시 `keyCode 229`) ⑤ 항목 `keydown` 확장 — Enter/Space 는 **기존 `_select` 그대로**(신규 선택 경로 0) ⑥ `.product-dropup-item:focus-visible` 커서 가시화(마우스 클릭엔 링 없음). **동반 수정(codex 적대 리뷰 P2 — 기존 결함)**: `_select` 가 `closeProductDropup()` 만 호출하고 `openProductDropup()` 이 문서에 건 바깥클릭·Escape capture 리스너를 해제하지 않아, 항목 선택으로 닫으면 리스너가 남고 **닫힌 뒤 Escape 가 포커스를 제품 chip 으로 튕겼다**(클릭 선택에도 있던 결함). 해제 함수를 `_productDropupDetach` 에 보관해 `closeProductDropup` 을 단일 해제 지점으로 정리. **검증**: 신규 `tests/headless/verify_product_dropup_keynav.py` **27/27 PASS** — 하네스가 DOM 을 흉내내지 않고 **실 `renderProductDropupMenu`/`openProductDropup`/`closeProductDropup` 원문 + 실 CSS** 를 돌려 재렌더·자동 포커스·문서 리스너 배선까지 검증(T14 리스너 누수 가드·T15 Escape 무회귀·T16 재렌더 후 배선·T0/T17 침묵 실패 차단). 기존 `verify_product_dropup_scroll.py` 11/11 PASS · `node --check` · `make test` 회귀. §18.8 `ux`/`design` subagent 는 세션 도구 제약으로 `[SKIPPED:tool-restricted:ux,design]`, 대체 채널(codex + 헤드리스 + PB-0008)로 커버. POST-DEPLOY PB-0008 라이브 검증은 배포 후 수행(`visual_verification_scope: always`). 정본 = TASK `20260729T1742-product-picker-keynav` · FUNCTION `REQ-20260729T174200-product-picker-keynav`(AC-PPKN-1~4) · REVIEW `REV-20260729T174200-product-picker-keynav` · Run `docs/test-runs.d/20260729T1742-product-picker-keynav.md`.

**2026-07-29 TASK-20260729T1455-conv-search-attach-name — 대화 검색에 첨부 파일명 축 추가** (Major §12.3 — feature-0003 단독 거주: 검색 SQL `routers/_conv_store.py` · 매칭 근거 수집 `routers/_prompt_context.py` · 응답 `routers/conversations.py` · 프론트 `static/{app.js,index.html,styles.css}` · 정책 `docs/SECURITY.md §8.2·§8.6`. **신규 권한·엔드포인트·스키마·alembic 마이그 0**). **사용자 요청**: "서비스 내 대화를 검색하는 기능에서, 대화 내 첨부된 파일의 명칭도 검색 대상에 포함할 수 있도록 개선." **진단**: 검색 매칭 축이 제목 + 메시지 본문 2종뿐이라 "그 엑셀 올렸던 대화" 를 파일명으로 되찾을 수 없었다. 또 검색 대상 필드는 `SECURITY.md §8.2` 가 **열거로 고정한 정책 표면**이라 축 추가는 정책 갱신을 동반해야 정합이 유지된다(그래서 Minor 가 아닌 Major). **변경**: ① PG 라이브 경로(`_list_conversations_pg`)와 MySQL 폴백(`_list_conversations`) 검색 WHERE 의 OR 체인에 첨부 EXISTS 추가 — `core_attachments.original_filename ILIKE` / `WebConversationAttachments.OriginalFilename LIKE … ESCAPE '!'`, 양쪽 다 첨부 **목록과 같은 가시성**(`deleted_at/superseded_at IS NULL` = 미삭제 + 버전 최신)으로 한정해 "삭제한 파일이 검색으로만 되살아나는" 비대칭을 차단 ② `_collect_matched_attachment_names` 신설(`ROW_NUMBER()` conv 당 최신 3건 · 예외 시 빈 dict fail-soft) → 검색 응답 `matched_attachments` ③ 검색 결과 행에 📎 파일명 칩(`_searchHighlight` 경유 = escapeHtml 보존), 표시 게이트 = **본인 대화 항상 / 타 계정 대화는 기존 snippet opt-in chip**(§8.6 정책선 계승) ④ placeholder·빈 상태 카피 갱신 ⑤ SECURITY §8.2 에 축 추가 + 노출면 확대 0 판정 근거 5항 기재. **인가 판정 — 초안이 틀렸고 적대 리뷰가 잡았다**: 초안은 "결과에 오른 대화의 첨부 파일명은 첨부 목록 API 로 이미 열람 가능" 을 노출면 근거로 삼았으나, `conversation.list.any`(관리자)와 `conversation.attachment.read.any`("운영자 한정")는 **독립 권한 코드**라 전자만 가진 계정에서 그 전제가 거짓이다. 그 계정에게 초안은 파일명 매칭(= "그 대화에 이 파일명이 있는가" oracle)과 `matched_attachments`(파일명 직접 반환)를 모두 열어 첨부 조회 게이트를 우회시켰다. 프론트 `mine || snippet_opt_in` 은 UI 절제일 뿐 방어가 아니다(DevTools·직접 API). → **`app._search_attachment_axis` 단일 판정점 신설 + 검색 EXISTS 자체를 권한으로 게이팅**(축을 끄면 근거뿐 아니라 oracle 도 사라진다 — 근거만 막으면 파일명 추측이 성립), `.own` 은 EXISTS 를 본인 소유·멤버 대화로 좁힘(`_account_can_access_conversation` own 판정과 동형), self_id 부재는 fail-closed, 엔드포인트 수집 스코프도 동일 판정. SECURITY §8.2.1 로 정책 정정. **동반 수정(P2 4건)**: ① PG 검색 절의 `ESCAPE '!'` 유실 복원(§8.3 위반 — AR-M4 포팅 때 유실, 수집 헬퍼와 semantics 불일치도 해소) ② 헬퍼 fail-soft 를 경계 전체로 확대 ③ **검색 실패 폴백에서 첨부 캐시 리셋 누락**(보강 테스트가 적발 — 이전 검색 파일명 칩 잔존) ④ 테스트가 소스 문자열 검사(tautology)라 실제 동작 미검증. **재검증(2차)**: 수정본을 같은 형식으로 재검토시켜 P1·escape·fail-soft·캐시 리셋 **"해결됨" 확인**, 신규 P2 3건도 전건 수정 — ① `own` 스코프 판정을 엔드포인트 items 필드(`is_member`)로 하던 것이 **PG 경로만 그 필드를 채워** MySQL 폴백에서 멤버 대화 근거가 조용히 비던 불일치(AC-4 위반) → 판정을 **SQL 로 이관**(`scope_account_id` + 대화 조인) ② 프론트 응답 경합(늦은 이전 응답이 새 결과·칩을 덮어씀) → `requestGen` 세대 토큰(성공·실패 양 경로) ③ §8.4 `max_execution_time` 이 **MySQL 연결 전용**이라 라이브(PG) 검색에 runaway 상한이 없던 것 → 목록·수집 PG 쿼리에 `SET statement_timeout = 3000`. **검증**: 테스트를 fake 커넥션으로 **실제 SQL·params 를 캡처**하는 실행 기반 **30건**으로 재작성(권한 게이트 A1~A6·가시성 V1~V2·비용 회귀 G1·escape 리터럴화 E1~E3·수집 C1~C6·엔드포인트/수집 스코프 P1~P6·프론트 F1~F5) 전건 PASS · 전체 스위트를 worktree·main 양쪽에서 돌려 `FAILED` diff → **신규 실패 0**(잔여 21 은 main 과 동일한 라이브 DB 의존 환경성) · ruff PASS. **비용 회귀 0**: 첨부 EXISTS·수집 모두 검색어 게이트 안에만 존재(테스트 G1 이 실제 SQL 로 고정). **범위 밖·미해소(정직)**: 첨부 *내용* 검색은 질적으로 다른 노출면이라 제외 · 첨부는 공유 [from,to] window 로 클립되지 않는 conversation 단위 스토어라 본 변경이 window 격리를 새로 깨지 않으나 첨부 window 도입은 목록·검색·recall 을 한 cycle 로 다뤄야 함 · **P2 성능은 미해소** — `ILIKE '%q%'` 인덱스 미사용, `max_execution_time` 은 CPU 상한 아님 → 라이브 `EXPLAIN ANALYZE` 는 POST-DEPLOY(기존 본문 축이 이미 동일 성질). §18.8 subagent 패널은 세션 상위지시(`Agent` tool 금지)와 상충해 **사용자 확인 후** `/codex review`(§18.8.1 경로 2, `[CODEX:*]` = check #9 accepted)로 대체. **잔여**: POST-DEPLOY PB-0008 라이브 시각검증(`visual_verification_scope: always`) · 첨부 EXISTS EXPLAIN 실측. 정본: TASK/CHG/REV-20260729T145500-conv-search-attach-name · FUNCTION REQ-20260729-conv-search-attach-name(AC-1~5) · Run=test-runs.d/20260729T145500-conv-search-attach-name.md.

---

**2026-07-28 TASK-20260728T161940-routine-column-edges — 함수/프로시저 사용 관계선을 실제 참조 컬럼에 연결(테이블 펼침 시)** (Major §12.3 — cross-cut 코드 거주: 프론트 `static/graph/{graph-core,graph-ctxmenu}.js` + 백엔드 feature-0002 `modules/{routines,metadata_graph}.py`. **alembic 마이그 0**·RBAC/엔드포인트 계약 무변경. 정본 feature-0016 `20260728T1541-routine-column-edges`). **사용자 요청**: 함수·프로시저가 테이블에만 연결되고 연관 컬럼에 붙지 않음 — 접힘은 기존대로, 펼침 시 실제 [읽기/쓰기] 참조 컬럼에 관계선 구성. **근본 원인**: FK(`REFERENCES`)는 엣지 양끝이 Column 키라 `renderEndpoint` 3단 승격이 자동 동작하지만, `ROUTINE_USES` 는 SSOT(`routine_objects.referenced_tables`)부터 **테이블 단위**라 승격할 컬럼 끝점이 없었다(프론트 단독 해결 불가). **변경**: ① 정의 파싱이 **테이블이 확정된 컬럼만** read/write 로 추출(alias 수식·INSERT 컬럼리스트·UPDATE SET 좌변 / 비수식 미추정·미실재·모호 alias·크로스-DB 폐기 = 사용자 결정 '보수적') → `referenced_tables[].cols` (jsonb additive, 다음 sync 자동 backfill) ② AGE `ROUTINE_USES` 속성 `ref_columns` 투영 + `schema_tables`/`neighborhood` 응답 동봉 ③ 빌드가 **컬럼이 렌더 중일 때만** 사용선을 컬럼별 분해(미렌더 컬럼은 테이블로 relation_type 별 1선 승격 · 렌더 컬럼 0이면 분해 포기 = 접힘 완전 불변) ④ 상세 패널 참조 컬럼 병기(`✎`=쓰기). **검증**: **PB-0008 실 Windows Chrome 150 PASS**(격리 harness — 접힘 3선 전부 테이블 / 펼침 `sp_UpdateUser`→`T_User.UserID`(읽기)·`Point`(쓰기)·`Name`(쓰기) 개별 연결 + 미렌더 컬럼 테이블 승격 + `ref_columns` 없는 대조군 무회귀 + 상세 `UserID, ✎Point, ✎Name` · pageerror 0) · 헤드리스 신규 `test_graph_routine_colref.js` **30 PASS** + 그래프 전 스위트 18개 **0 FAIL**(722 PASS) · pytest 신규 `test_routine_column_refs.py` **27건** · 전체 **2740 passed / 15 failed**(15건 전부 baseline — main 대조 동일) · ruff PASS. **테스트가 실제 결함 2건 적발·수정**(접힘 상태 선 2개 분기 회귀 · `_fetch_columns` cursor 예외가 routine upsert 전체를 죽이던 경로). **검증 경로 정직 기록**: 라이브 주입 QA 는 병렬 세션 6+ 의 브라우저·라이브 공유로 타 세션 오염 위험이 확인돼 **즉시 원복**(web-a/web-b md5 원본 일치·`/livez` 200) 후 격리 harness + CDP 신규 탭으로 전환. §18.8 패널은 세션 정책상 미수행 — REVIEW 에 [SKIPPED:session-policy-no-subagent] + 자체 적대 검토 H1~H6. **잔여**: 실데이터 e2e(배포 후 routine 재-introspect + graph sync 선행)는 POST-DEPLOY. 정본: TASK/CHG/REV-20260728T161940-routine-column-edges · Run=test-runs.d/20260728T161940-routine-column-edges.md.

**2026-07-28 TASK-20260728T162000-graph-catcluster-scroll-polish — 카테고리 선택 스크롤 polish: 280ms EaseOutExpo + 헤딩 점멸/멤버 파도(알파 선형 감쇠)** (Minor §12.3 — feature-0003 web/UI 프론트 `graph-ctxmenu.js` + `graph.css`, 비파괴, 백엔드/RBAC/스키마/엔드포인트 무변경. 정본 feature-0016). **사용자 피드백 2건**(직전 cycle 수용 후): "스크롤이 이동하는 속도를 좀 더 신속하게 (대화 로그 우측 막대뱃지 클릭 이동과 정합하게)" / "카테고리 스키마 점멸 + 하위 자식 요소를 파도 형태로 순차 점멸(알파는 점점 선형적으로 연하게)". **수정**: ① 브라우저 native `scrollTo({behavior:'smooth'})`(duration 이 명세 미정의 — Chrome 은 거리 비례로 늘려 17,000px 목록에서 수 초)를 **대화 뷰 point-rail 정본과 동일한 280ms EaseOutExpo**(`1-2^(-10t)`, `app.js` `POINT_SCROLL_DURATION_MS` / `share.js` 동형)로 교체하고 rAF 직접 구동 + `maxTop` 클램프 + 세대 토큰 선점. ② 도착 연출을 **헤딩 2회 점멸(760ms) + 멤버 행 파도 순차 점멸(420ms, delay = 90 + 26×i)** 로 재설계하고 알파(`--amgr-wave-a`)를 첫 행 0.5 → 마지막 행 0 **선형 감쇠**. 대상은 다음 헤딩 전까지의 **보이는** 행 최대 24개(패널 뷰포트 분량, 접힌 행 제외), 종료 시 클래스·인라인 변수 전량 제거, 새 선택은 직전 연출 즉시 원복. 구현은 CSS 애니메이션(컴포지터) + JS 1회 주입이라 레이아웃 비용 0. **검증**: 헤드리스 `test_catcluster_panel_scroll.js` **36 → 65 PASS / 0 FAIL**(rAF·`performance.now` test double 프레임 구동 — 곡선 계약·≤20프레임 정착·파도 지연/알파 선형·경계·상한·정리·선점·reduced-motion·폴백) · 회귀 328 PASS · **PB-0008 실 Windows Chrome/150**(격리 컨테이너 §13.2.9 — 라이브 무접촉): 스크롤 샘플 t=420ms 2,147 → t=827ms **1,698 정착**(직전 구현은 동일 거리에서 수 초), 헤딩 +6px, 파도 delay `90/116/142/168ms` · alpha `0.500/0.333/0.167/0.000`, 31-멤버 그룹 파도 프레임 캡처, 잔여 0, 콘솔 에러 0. **검증 마찰(정직)**: 병렬 AI 세션 4곳이 같은 Chrome 을 공유해 `win-browser.py`(항상 `pages[0]`)가 남의 탭을 잡아, 같은 relay 로 **내 탭만 URL 선택**하는 전용 드라이버로 수행(타 세션 무접촉). §18.8 패널은 세션 정책(하네스 `Agent` tool 금지)으로 [SKIPPED:session-policy-no-subagent] + 자체 적대 검토 H1~H8. 정본: TASK/CHG/REV-20260728T162000-graph-catcluster-scroll-polish · Run=test-runs.d/20260728T162000-graph-catcluster-scroll-polish.md.

---

**2026-07-28 TASK-20260728T161326-graph-analyzed-halo-fit — AI 분석 완료 컬럼 노드의 상태 테두리가 노드보다 비대: halo 기하를 노드 모양·크기에 비례화** (Minor §12.3 — feature-0003 web/UI 프론트 `static/graph/graph-renderer-pixi.js` 단일 모듈, 렌더 기하 보정·비파괴, 백엔드/RBAC/스키마/엔드포인트 무변경. 정본 feature-0016). **사용자 리포트**: "`그래프 뷰` 에서 AI분석이 완료된 컬럼 노드에서, 노드 크기에 비해 테두리가 너무 비대하게 구성되어 있어 적절하게 재구성이 필요합니다."(스크린샷 — `masangsoft_modules` 컬럼 목록 전체가 하나의 세로 보라 관). **진단**: 컬럼 노드는 `type:"circle"` + `style.size = 11`(숫자)인데 `_applyNodeStates` 가 **모든 노드를 rect 로 가정**해 `h = Array.isArray(size) ? size[1] : 24` 를 적용 → 원형 노드에 **h=24 기본값**이 대체 투입되고 여백 3 + 두께 3 이 얹혀 **11px 점 주위에 17×30 세로 알약**이 그려졌다. 컬럼 행 간격(~24px)보다 halo 높이(30px)가 커서 이웃 halo 가 겹치며 관으로 융합된 것이 리포트 화면의 정체다 — 지배 원인은 두께가 아니라 **모양·크기 계약의 부재**. **수정**: 순수 기하 함수 **`PixiAdapterPure.haloGeom(n, i, lineWidth)`** 신설 — ① circle 노드는 **원형 halo**(반지름 = 노드 반지름 + 여백), ② 두께·여백·동심링 간격을 노드 최소변에 비례(`k = clamp(min(w,h)/24, 0.4, 1)`; 24 = 테이블 칩 높이라 **모든 rect 노드에서 k=1 → 종전 수치 그대로**), ③ 두께 하한 1px. 원형에서는 4변 대시가 성립하지 않아 **`dashArcs(r, dash)`**(호 길이 → 라디안 구간)로 running/busy 점선을 직선 대시와 같은 화면 길이로 재현. 11px 컬럼 기준 두께 3 → **1.375px**, halo 외곽 지름 **30 → 15.1px**. **검증**: `test_pixi_adapter.js` **205 PASS**(T27 15건 신설 — rect 좌표·radius·lw 전건 회귀 대조 포함) · 그래프 전 헤드리스 스위트 **677 PASS / 0 FAIL** · 드로잉 경로 스텁 계수로 런어웨이 0 · **PB-0008 실 Windows Chrome/150 relay** 4× 확대 before/after: BEFORE 는 `gunzgame.mail` 컬럼 4개가 세로 보라 관으로 융합, AFTER 는 `masangsoftweb.masangsoft_documents`(사용자 리포트와 동일 화면) 컬럼마다 **얇은 링이 개별 분리**되고 테이블 칩 halo 는 불변 · 주입 QA **원복 완료**(서빙 `haloGeom` 0건 · `/livez` 200). `make test` pytest 15건 실패는 attachment/runtime_settings **worktree 격리 네트워크 환경성 baseline**(본 변경은 Python 무접촉, ruff PASS). §18.8 패널은 세션 정책(하네스 `Agent` tool 금지)으로 [SKIPPED:session-policy-no-subagent] + 자체 적대 검토 H1~H5. 정본: TASK/CHG/REV-20260728T161326-graph-analyzed-halo-fit · Run=test-runs.d/20260728T161326-graph-analyzed-halo-fit.md.

---

**2026-07-28 TASK-20260728T160000-graph-catcluster-focus — 접힌 카테고리 클러스터 하위 테이블 추적 시 카메라가 '스키마 클러스터 중앙'으로 오이동하던 결함 수정** (Minor §12.3 — feature-0003 web/UI 프론트 `static/graph/{graph-core,graph-ctxmenu}.js` 2모듈, 비파괴, 백엔드/RBAC/스키마/엔드포인트 무변경. 정본 feature-0016. `/_template:entry` arg-given). **사용자 보고**: "그래프 뷰에서 '카테고리 클러스터'가 접힌 상태에서 하위 테이블 노드의 위치를 추적할 경우(상세 패널 내 테이블 요소 클릭, 테이블 노드가 선택된 상태에서 '이 노드로 이동' 등) 테이블 노드의 상위 객체인 '카테고리 클러스터'가 아닌 '스키마 클러스터'의 중앙 위치로 카메라가 이동한다." **근본원인**: 미렌더 노드의 카메라 승격 사다리 `_metaRenderedAncestorFor` 가 *모델 계층*(key 파싱: 컬럼→테이블→스키마)으로만 서 있고, **실제 렌더를 게이팅하는 두 클러스터 계층** — 컨텐츠 카테고리(sim-group, `groupCollapsed` 면 멤버 미방출·`GB:/GH:/GX:` 헤더만) 와 제품 카테고리 밴드(`catCollapsed` 면 멤버 스키마 클러스터 통째 미방출·`CAT:` 밴드만) — 를 건너뛰었다. 두 계층은 key 로 파생되지 않고 build 가 만드는 역인덱스(`groupOf`/`catMembers`)로만 알 수 있어 키 파싱 사다리엔 보이지 않았다. 게다가 `_metaColParent` 는 (컬럼 전제 함수라) **테이블 키를 받으면 소속 스키마**를 돌려주므로, 사다리가 실패하지 않고 **잘못된 대상으로 성공**해 카메라가 스키마 combo 중앙으로 갔다(= 보고 증상). 제품 카테고리 밴드가 접힌 경우엔 승격 대상이 아예 없어(null) 카메라가 움직이지 않고 "표시할 수 없습니다"로 끝났다. **수정**: 사다리를 `컬럼 → 소속 테이블 → 컨텐츠 카테고리(GB:) → 스키마 클러스터(combo | SC:) → 제품 카테고리 밴드(CAT:)` 로 완성 — 신설 `_metaGroupElementFor`/`_metaCategoryElementFor` 가 두 역인덱스를 `renderedIds` 로 **게이팅**해 stale 항목의 허위 카메라 이동을 차단한다. **접힘은 사용자 지속 의도라 자동 펼침은 하지 않고 시선만 옮긴다**(A13 이 승격 경로의 `expand/toggle` 부재를 정적 고정). 상태줄도 `_metaAncestorKindKo` 로 **실제 승격 대상 종류**를 표기 — 종전 "소속 테이블" 단정은 이 결함의 은폐 장치였다(실제로는 스키마로 갔는데 안내는 테이블). `_metaGraphAnimateFocus` 앵커 해소(본 루프 + 폴백 번들)에도 같은 사다리를 폴백으로 걸어, 모델 키로 들어오는 호출(관계 추적 등)이 1.2s 헛돌다 카메라가 아예 안 움직이던 사각을 없앴다. **검증**: 신규 헤드리스 `test_graph_ancestor_focus.js` **32 PASS / 0 FAIL**(사다리 5단 전수·두 접힘 계층·stale 게이팅·명칭/조사 불변식·자동펼침 부재) · 회귀 **364 PASS**(dbgroups 78 · pixi 190 · edge_flow 43 · reveal 17 · catcluster_panel_scroll 36) · `node --check`(ESM) PASS · **PB-0008 실 Windows Chrome/150 라이브**(§13.2.9 격리 컨테이너 `:18098` — 라이브 web-a/web-b·공유 checkout 무접촉) 6 시나리오 PASS: `mssql-web-qa`/`masangsoftweb` 에서 컨텐츠 카테고리 `이벤트 아이템 지급`(40) 접힘 → `🎯 이 노드로 이동` 클릭 시 **대상 블록 거리 1189→3px 정착**, 같은 조작에서 **스키마 클러스터 중앙 거리 40→1148px**(오이동 대상 결정적 이탈) · 제품 카테고리 밴드 `국내 웹 - QA`(23 DB·1,056 테이블) 접힘 → 밴드 2px 정착(종전 미이동) · 전부 펼침 회귀 2px · 콘솔 에러 0 · 스크린샷 4매. **라이브에서만 잡힌 결함 1건**: 상태줄 조사 `카테고리(으)로` → `로` 정정(전 라벨이 모음/ㄹ 받침) + 조사 불변식 테스트 추가 → **정정본으로 6 시나리오 전건 재측정**. §18.8 패널은 세션 상위 지시(하네스 `Agent` tool 금지)로 `[SKIPPED:tool-restricted:ux,design]` + 자체 적대 검토 H1~H6(§18.8.2 carve-out). **범위 확대 정직 표기**: GB 승격은 접힘뿐 아니라 **뷰포트 컬링으로 미렌더인 테이블**에도 적용된다(종전 스키마 combo → 더 가까운 조상으로 개선). 정본: TASK/CHG/REV-20260728T160000-graph-catcluster-focus · FUNCTION REQ-20260728T160000-graph-catcluster-focus(AC-CCF-1~4) · Run=test-runs.d/20260728T160000-graph-catcluster-focus.md · 증적 `artifacts/shared/win-browser-shots-catcluster-focus/*.png`.
**2026-07-28 TASK-20260728T162844-graph-hover-flow — 상세 패널 hover 강조: (방향·읽기/쓰기) 관계선 특정 + 데이터 흐름 애니메이션** (Minor §12.3 — feature-0003 web/UI 프론트 `static/graph/` 3모듈, 비파괴, 백엔드/RBAC/스키마/엔드포인트 무변경. 정본 feature-0016). **사용자 리포트**: "상세 패널 내 참조관계를 개별 확인하려고 mouse-hover 하이라이트를 구성했는데, 연결선 중 [읽기/쓰기]에 따라 곡선의 형태를 구분하고 있지만 **하이라이트는 구분에 관계없이 하나의 관계선만** 나타난다 … 실제 [읽기/쓰기]에 따른 곡선이 하이라이트 되도록 + 하이라이트 처리된 부분은 **실제 데이터 흐름을 나타내는 애니메이션**으로 연출". **진단**: 같은 두 노드 사이의 관계선은 **1:N** 이다 — 왕복 REFERENCES 는 곡률 왼쪽 고정 규칙 때문에 반대편 호(§83 A2), ROUTINE_USES 는 집계 키에 `relation_type` 이 들어가 읽기/쓰기가 별개 선(§83 C1). 그런데 hover spec 이 `[self끝점, 상대]` 순서라 **방향을 담지 못했고**, `_edgeStyleBetween` 이 정/역·종류 구분 없이 **첫 매칭**을 반환했다 — 방향도 종류도 판별 축이 아니었다. **수정**: ① 관계 행 3종이 모델 엣지의 실제 `(source,target)` + `relation_type` 을 `data-edge-src/tgt/rel-type` 로 싣고(`_metaHoverEdgeSpec`, 구 마크업 레거시 폴백), `_metaGraphSetHoverHighlight` 가 방향 객체 `{from,to,relType}` 로 전달한다. ② 신규 `_edgeMatchBetween` 이 **방향(1순위) > relation_type(2순위)** 로 관계선을 특정하고, 역방향 등록 엣지는 곡률 부호 반전 + `startArrow`/`endArrow` 교환으로 `(sid→tid)` 프레임에 정규화한다(교환 누락 시 호는 맞고 흐름만 거꾸로 흐르는 비대칭이 남는다). ③ `dashPolyline(pts,dash,phase)` 위상 인자 + hover 전용 rAF(`_startHoverFlow`)로 흰 대시가 흐름 방향으로 이동하고, 화살촉은 도착 끝에 **정적**으로 남아 정지 캡처·`prefers-reduced-motion` 에서도 방향이 읽힌다. ④ 강조 굵기·화살촉·대시 주기/속도를 화면 픽셀 기준으로 정규화(§85 정합 — 종전 model 고정 3.5px 는 줌인 리본·줌아웃 실종), 오버레이 Graphics 는 교체 시 **파기**(hover 는 행마다 발생 — detach 만 하면 GPU 지오메트리 누적). **검증**: 신규 헤드리스 `test_graph_hover_flow.js` **41 PASS / 0 FAIL** + **구현 이전 어댑터 적대 대조**로 두 축 회귀 재현(`OLD: 참조함 호 cy 26.0 == 참조받음 26.0 → 같은 호` · `OLD: 읽기·쓰기 화살표 동일`) · 그래프 전 스위트 **733 PASS / 0 FAIL** · `node --check`(ESM) 3모듈 PASS · **PB-0008 실 Windows Chrome 150 라이브 PASS**(§13.2.9 격리 컨테이너 :18097 — 라이브 web-a/web-b 무접촉): 참조함/참조받음 화살촉 반전 + 강조 픽셀 차 441px, 읽기/쓰기 대상선 분기 3,517px, 같은 hover 420ms 프레임 차 151px(대시 진행), 페이지 에러 0, 스크린샷 3매. Python 변경 0 → pytest/ruff 해당 없음(PR CI 재확인). §18.8 은 세션 상위지시(Agent tool 금지) carve-out 하에 `[CODEX:graph-hover-flow]` PASS + 기계 대조 + 라이브 관측으로 수행, subagent 패널만 `[SKIPPED:tool-restricted:ux,design-subagent]` 명시. 정본: TASK/CHG/REV-20260728T162844-graph-hover-flow · Run=test-runs.d/20260728T162844-graph-hover-flow.md.

---

**2026-07-28 TASK-20260728T152000-graph-catcluster-panel-scroll — 캔버스 컨텐츠 카테고리 선택 → '스키마 클러스터' 목록을 그 카테고리 위치로 스크롤** (Minor §12.3 — feature-0003 web/UI 프론트 `static/graph/` 3모듈 + CSS, 비파괴, 백엔드/RBAC/스키마/엔드포인트 무변경. 정본 feature-0016). **사용자 요청**: "그래프 뷰에서 카테고리 클러스터를 선택했을 경우, '스키마 클러스터' 항목에서 해당 카테고리 클러스터 위치로 스크롤 되도록 구성해주세요."(스크린샷에서 캔버스 `문피아 계정 이전` 그룹 박스와 우측 패널의 동명 헤딩을 함께 지목). **진단**: 컨텐츠 카테고리(sim-group) 박스/헤더 클릭은 소속 스키마 클러스터 상세를 열지만 패널은 항상 목록 처음부터 렌더한다. `cluster-detail-fulllist` 로 그룹당 캡을 없앤 뒤 목록이 수백~수천 행(라이브 `masangsoftweb` = 카테고리 93 · 595행 · 17,277px)이라 방금 고른 카테고리를 사용자가 직접 찾아 내려가야 했다. **수정**: 캔버스 그룹 키의 **fam**(구분자 뒤 토큰)을 좌클릭(GB/GH)·우클릭('소속 스키마 상세') 경로에서 `ById(comboId, focusFam)` → `RenderClusterDetail(…, focusFam)` → **`_metaGraphFocusPanelGroup(fam)`** 으로 전달해, 렌더 직후 같은 fam 의 패널 헤딩으로 **aside `scrollTop` 국소 스크롤**(sticky 이력 바 높이 + 6px 보정) + 1.8s 도착 강조(`.amgr-ct-group.is-focus`) + 상태줄 `목록을 '<라벨>' 위치로 이동` 표기. 캔버스 키(`<comboId>|fam`)와 패널 키(`panel:<name>|fam`)는 `_metaSimGroups` 의 schemaId 네임스페이스가 달라 **fam 만 대조**하며, 미매칭이면 graceful no-op(잘못된 그룹 점프 불가). 연타 대비 세대 토큰 `_panelFocusSeq`, `prefers-reduced-motion` 은 즉시 스크롤. **검증**: 신규 헤드리스 `test_catcluster_panel_scroll.js` **36 PASS / 0 FAIL**(호출부 인자 매핑·CSS 클래스 존재 포함) · 회귀 `test_detail_dbgroups` 78 · `test_pixi_adapter` 190 PASS · **PB-0008 실 Windows Chrome/150**(격리 컨테이너 §13.2.9 — 라이브 web-a/web-b 무접촉) 7 시나리오 PASS: 최하단 16,661 → `문피아 계정 이전` 정착 1,667(헤딩 +53px = navH 47 + 6) · `소셜회원관리` 12,392 · 우클릭 경로 `게임라우팅` 15,134 · 강조 부여/1.8s 자동 해제 · 스키마 카드 경로 무개입 · 콘솔 에러 0 · 스크린샷 5매. §18.8 패널은 세션 정책(하네스 `Agent` tool 금지)으로 [SKIPPED:session-policy-no-subagent] + 자체 적대 검토 H1~H8. 정본: TASK/CHG/REV-20260728T152000-graph-catcluster-panel-scroll · Run=test-runs.d/20260728T152000-graph-catcluster-panel-scroll.md.

---

**2026-07-28 TASK-20260728T152141-graph-edge-hairline — 줌아웃 관계선 깨짐·계단·끊김: hairline 처리(1물리픽셀 + alpha 보상)** (Minor §12.3 — feature-0003 web/UI 프론트 `static/graph/` 2모듈, 렌더 품질 보정·비파괴, 백엔드/RBAC/스키마/엔드포인트 무변경. 정본 feature-0016 §87). **사용자 질의**: "줌 아웃 시 관계선 깨짐 + 계단현상 + 끊겨보이는 이슈 … anti-aliasing 적용이 과도한 조치일지, 더 모범적인 렌더링 방법이 있을지 검토". **검토 결론**: **AA 는 이미 켜져 있다**(`antialias: true` + `resolution: devicePixelRatio` + `autoDensity`) — 증상이 남아 있다는 사실이 'AA 부재 가설' 의 반증이다. **원인은 선 폭이 1물리픽셀 미만**(§86 기본 0.6px 는 dpr 1 에서 전 줌 서브픽셀, 줌아웃 시 하한 0.25px). MSAA 는 픽셀당 유한 샘플의 커버리지를 평균할 뿐이라 폭 0.3px 선의 커버리지가 0/25/50/75% 로 **양자화**되고, 그 밝기 튐이 끊김·계단으로 읽힌다(샘플 증설은 단계만 촘촘하게 하고 fill rate 만 먹음). **채택**: **hairline 처리**(Mapbox GL·deck.gl·Skia/Cairo 표준) — `w_screen < 1/dpr` 이면 폭을 정확히 1물리픽셀로 올리고 모자란 두께분을 alpha 에 곱한다(`edgeHairline(base, zoom, dpr)` → `{w, fade}`, `_paintEdge` 가 `alpha *= fade`). 커버리지가 균일해져 증상이 원천 소멸하고, '가늘기' 는 alpha 가 연속 표현하며, 비용은 산술 몇 줄이다. **base 재조정 동반**: 기본 굵기 0.6→**1.0px**(개수 축 1.00/1.54/2.08/2.60 포화) — 0.6px 는 항상 hairline 경로를 타 개수 축이 상시 alpha 로 흘러 §86 채널 직교화가 무력했다. **검증**: 동일 줌(fit−2) **4× 확대 대조**에서 현행은 대각선이 점선처럼 끊기고 밀집 밴드가 픽셀 노이즈로 튀는 반면 hairline 은 **연속 실선**으로 이어짐(라이브 육안, `hl-compare.png`) · 1픽셀 구멍 **740→635**(측정 영역에 카드 테두리가 섞여 개선폭 과소평가) · 페이지 에러 0 · `test_graph_edge_flow.js` **73 PASS**(A13 신설 6건 — 무보정/폭 승격/alpha 보상/극단 줌아웃 폭 유지/alpha 단조/**dpr 2 임계**, A11 을 실효 잉크량 기준 재작성) · 그래프 전 스위트 **656 PASS / 0 FAIL** · 주입 QA 후 **이미지 원본 원복**(잔재 0). §18.8 패널은 세션 정책상 미수행 — REVIEW 에 [SKIPPED:session-policy-no-subagent] + 자체 적대 검토 H1~H5. 정본: TASK/CHG/REV-20260728T152141-graph-edge-hairline · Run=test-runs.d/20260728T152141-graph-edge-hairline.md.

---

**2026-07-28 TASK-20260728T142745-graph-edge-encoding — 줌 두께 정책 구간 분리(줌인 고정·줌아웃 비례) + 인코딩 축 재배치(굵기=개수 / 진하기=신뢰도)** (Minor §12.3 — feature-0003 web/UI 프론트 `static/graph/` 3모듈, 비파괴, 백엔드/RBAC/스키마/엔드포인트 무변경. 정본 feature-0016 §86). **사용자 리포트**: "극단적으로 줌아웃을 할 경우에는 해당 선의 굵기가 보존되어 화면을 전체적으로 가려버리는 이슈 … 기본적으로 관계선은 가느다랗게, 연결 부위의 신뢰성이 높을수록 진하게, 많을수록 굵게". **진단**: 두께의 줌 정책을 §84(줌아웃만 화면 고정 → 줌인 구간 부풂)와 §85(전 구간 화면 고정 → 줌아웃 도포)로 **같은 축의 양극에서 반대로 밀었다**. 확대에서는 "더 굵어지지 마라", 축소에서는 "콘텐츠와 함께 물러나라"는 요구가 다르므로 단일 정책으로 둘을 만족할 수 없다. **수정**: ① **구간 분리** `w_screen = clamp(base·min(1, zoom/ZFULL), MIN, base)`, `w_model = w_screen/zoom` (ZFULL=1 · MIN **0.25px** — 0.4 는 base 0.6 대비 비율이 커서 zoom 0.67 이하가 하한에 붙어 비례 구간이 평탄해짐을 실측 확인). ② **채널 직교화** — **굵기 = 관계 개수**(1건 0.60px · 4건 1.10 · 16건 1.60 · 64건 2.10 · 2.20 포화, 로그), **진하기 = 신뢰성**(trusted 0.85 > 루틴 확정참조 0.72 > candidate 0.5 > 교차DB 0.5 > inferred 0.38, SCHEMA_REF 중립 0.55), 색=종류 · 화살촉=방향 · 곡률=왕복 분리. 기본은 가느다랗게(0.6px). ③ **다발(strands) 제거** — 개수를 굵기가 담아 중복이고, 줌아웃에서 픽셀을 3~4배 먹어 도포 현상에 기여했다(§83 '부모 볼륨=가닥' → §86 '개수=굵기' 통합). 설계 근거: 개수는 양적 변수라 크기 채널에, 신뢰도는 순서적 변수라 명도 채널에 맞는다(종전은 반대 매핑). **검증**: 라이브(mssql-qa-idc) 극단 줌아웃에서 **보라색 도포 소멸** 육안 확인 · fit 관계선 구간 잉크 **43.19%→38.95%** · 페이지 에러 0 · `test_graph_edge_flow.js` **66 PASS**(A11 줌 구간별 정책 6건 재작성 · B1 개수→굵기 · B2 채널 직교화) · 그래프 전 스위트 **649 PASS / 0 FAIL** · 주입 QA 후 **이미지 원본 원복**(잔재 0 · `/livez` 200). **프로세스 사고(자체 적발·정정)**: 셸 cwd 가 main worktree 로 되돌아간 상태에서 상대경로 편집 3파일이 `repo/` 에 적용(§13.2.7 F0) → `git diff` 추출 · main `git checkout` 복원(status 0) · 본 worktree `git apply` 이관. 커밋 전이라 원격 영향 없음. §18.8 패널은 세션 정책상 미수행 — REVIEW 에 [SKIPPED:session-policy-no-subagent] + 자체 적대 검토 H1~H5. 정본: TASK/CHG/REV-20260728T142745-graph-edge-encoding · Run=test-runs.d/20260728T142745-graph-edge-encoding.md.

---

**2026-07-28 TASK-20260728T135111-graph-edge-screenspace — 관계선 굵기 변성 제거(screen-space 고정) + 프로시저·함수 관계선 실선화·LOD 해제** (Minor §12.3 — feature-0003 web/UI 프론트 `static/graph/` 3모듈, 렌더 좌표계 변경·비파괴, 백엔드/RBAC/스키마/엔드포인트 무변경. 정본 feature-0016 §85). **사용자 리포트(스크린샷 2매)**: "카메라 줌 수준, 포커스 인/아웃에 따라 관계선의 굵기가 변성" + "줌 아웃으로 인한 [프로시저/함수] 관계선 축약 제거 후 디자인 개선(점선 → 실선, 신뢰도에 비례하여 굵기 구성)". **근본원인(R1)**: 굵기가 model 좌표라 world scale 이 그대로 곱해진다. 직전 §84 가 줌아웃 소실만 막으려 `max(1, …)` 로 **바닥만** 걸어, 임계 줌을 경계로 화면 고정 구간과 model 고정(줌 비례 확대) 구간이 갈리며 굵기 거동이 두 체제로 쪼개졌다 — 확대 시 선·화살촉·다발이 리본처럼 부푸는 현상의 원인. **수정**: ① **screen-space 고정**(`edgeScreenScale = 1/zoom`) — 굵기·화살촉·다발 간격을 화면 픽셀로 해석해 어떤 줌에서도 동일 두께, 굵기는 오직 의미(신뢰도·종류)만 인코딩(Neo4j Bloom·Gephi·Cytoscape 관례). 곡률·오프셋 *위치* 는 model 기하 유지. ② **줌 재동기화**(`_syncEdgeZoom`/`_repaintAllEdges`) — 굵기는 페인트 시점 zoom 으로 bake 되므로 줌 변화가 로그 0.22(≈25%) 초과 시 전 엣지 in-place 재페인트(rAF 코얼레싱·`destroy` 정리). 휠 한 틱마다 전량 재페인트는 프레임을 무너뜨리고, 임계 내 오차(±12%)는 육안 미식별. ③ **ROUTINE_USES LOD 축약 제거**(직접·집계 두 경로, REFERENCES 는 유지) — 실선+화면 고정 굵기+밀도 누적 전환 후에는 "전체보기에서 루틴 관계 통째 소실" 의 손실이 더 크다. ④ **점선 폐지 → 신뢰도 굵기 단일 축** — ROUTINE_USES `[2,3]`·candidate `[6,4]`·교차DB `[2,4]` 대시 전량 제거, 굵기 서열(화면 px) **trusted 1.6 > ROUTINE_USES 1.3 > candidate 1.0 > 교차DB 1.0~1.15 > inferred 0.75**(종류=색, 방향=화살촉). ROUTINE_USES 는 AGE 속성이 `relation_type`·`cross_ds` 뿐인 **확정 참조**(루틴 본문 파싱)라 trusted 바로 아래. **검증**: 라이브 동일 스코프 3 줌 레벨(fit/+3/+6) 관계선 두께 실측 **중앙값 1.0/1.0/2.0px**(확대해도 두꺼워지지 않음 — +6 의 2.0 은 얇은 inferred 가 화면 밖으로 나간 구성 변화), 리본 현상 소멸 육안, 페이지 에러 0 · `test_graph_edge_flow.js` **61 PASS**(A11 화면 굵기 불변 4건·A12 줌 재동기화 4건 신설, B2/C0 실선·신뢰도 계약) · 그래프 전 스위트 **632 PASS / 0 FAIL** · 주입 QA 후 **이미지 원본 원복**(잔재 0 · `/livez` 200). §18.8 패널은 세션 정책상 미수행 — REVIEW 에 [SKIPPED:session-policy-no-subagent] + 자체 적대 검토 H1~H5. **잔여**: 루틴 노드 표시 스코프에서 사용선 육안(AC-GES-5) — POST-DEPLOY PB-0008. 정본: TASK/CHG/REV-20260728T135111-graph-edge-screenspace · Run=test-runs.d/20260728T135111-graph-edge-screenspace.md.

---

**2026-07-28 TASK-20260728T123838-graph-edge-legibility — 그래프 관계선 육안 검증 → 디자인 부정합 3건 보정** (Minor §12.3 — feature-0003 web/UI 프론트 `static/graph/` 3모듈, §83 후속 시각 보정·비파괴, 백엔드/RBAC/스키마/엔드포인트 무변경. 정본 feature-0016 §84. `/_template:entry` arg-given). **사용자 요청**: "육안검증을 수행하며, 디자인적으로 부정합한 부분을 탐색 후 개선 / 주로 DB단위로 AI 능동 분석이 완료된 항목들을 중심으로". **검증 스코프**: `node_analysis_runs` 집계로 분석 완료 상위를 특정(masangsoftweb 2,574 · cc_data_main 745 · gunzgame 709 · fhgame1 538) 후 DB 밴드가 가장 많은 **mssql-qa-idc** 를 주 스코프로 PB-0008 라이브 관측. **적발(3건)**: **F1(MAJOR)** 전체보기에서 관계선이 사실상 비가시 — 굵기가 model 좌표라 fit(zoom 0.2~0.55)에서 서브픽셀이 되고 안티앨리어싱이 alpha 까지 깎음(픽셀 실측 대비 **27~37/255**, 대조군 카드 테두리 161, 저밀도 구간 ink 0.12%). §83 의 "겹칠수록 진해짐" 이 밀집부에서만 성립하고 단독 관계선은 지워지는 비대칭. **F2(MINOR)** 곡률 상한 44 가 접힌 카드 높이(`_METLAY.CARDH=44`)와 같아 호가 이웃 행 카드 위로 부풀음. **F3(MINOR)** 분석 완료 halo(3px 불투명) ≫ 관계선(0.85px α0.32) 로 "분석 상태"가 "관계 구조"를 압도. **개선**: F1 → `edgeWidthBoost()` 로 **가장 얇은 선이 화면 1.15px 를 갖도록 전 엣지 동일 배율**(개별 clamp 는 굵기 서열을 뭉갬 — 기준선 하나로 배율 산출, 화살촉 상하한도 동일 배율) + alpha 바닥 상향(기본 0.32→0.58·색 `#94a3b8`→`#7c8b9e` 외 6종, 누적은 1겹 0.58→2겹 0.82→3겹 0.93 으로 보존); F2 → 곡률 상한 44→**26**(카드 높이 59%·행 간격 절반), 계수 0.15→0.13, 왕복 분리 하한 5 불변; F3 → halo 는 보존(사용자가 탐색 기준으로 사용)하고 관계선 대비를 1.9배 올려 균형. **바닥값은 라이브 2회 실측으로 확정** — 1차(α0.44/화면 0.85px)는 대비 44 로 불충분했고 2차(α0.58/1.15px)에서 목표 대역 진입. **검증**: 라이브 전후 픽셀 실측 **27→51 · 37→55**(밴드 간 흐름 육안 판독 가능) · 확대 시 곡선이 카드 여백 안에 머묾 · 페이지 에러 0 · 헤드리스 `test_graph_edge_flow.js` **56 PASS**(§84 A11 4건 신설) · 그래프 전 스위트 **627 PASS / 0 FAIL** · `node --check` PASS · 주입 QA 후 **이미지 원본 원복 완료**(잔재 0, `/livez` 200). §18.8 subagent 패널은 세션 정책상 미수행 — REVIEW 에 [SKIPPED:session-policy-no-subagent] + 자체 적대 검토 H1~H5. 정본: TASK/CHG/REV-20260728T123838-graph-edge-legibility · Run=test-runs.d/20260728T133000-graph-edge-legibility.md.

---

**2026-07-28 TASK-20260728T114015-graph-edge-flow — 그래프 뷰 관계선: 직선 → 방향성 곡선 · 얇고 반투명한 밀도 누적 · 상위 부모 관계 수에 비례한 다발 볼륨** (Major §12.3 — feature-0003 web/UI 프론트 `static/graph/{graph-renderer-pixi,graph-roleviz,graph-core}.js` 3모듈, 렌더 어휘 변경·비파괴, 백엔드/RBAC/스키마/엔드포인트 무변경. 정본 feature=feature-0016-metadata-graph §83, 코드 거주 feature-0003. `/_template:entry` arg-given). **사용자 요청**: ① 직선 관계선을 부드러운 곡선으로, 곡선 방향은 각 참조 방향(읽기·쓰기 둘 다면 관계선도 2개) ② 가늘게+약간 투명하게 해서 특정 노드에 많이 겹칠수록 진하고 명시적으로 ③ 상위 부모 내부 객체가 다른 객체에 관계된 개수에 비례해 관계선 볼륨도 풍부하게 ④ 우아한 디자인 + 공격적 최적화 (+ 같은 turn 추가 요청: 세련된 상용 그래프 뷰 형태 웹 리서치 참조). **레퍼런스**(리서치): Gephi 의 "두 노드 연결선에 수직인 컨트롤 포인트" 베지어 정의 · Cytoscape.js 의 평행 엣지 자동 bezier(`control-point-step-size`) — dbt Explorer 가 채택한 렌더러 · 엣지 번들링+반투명이 clutter 를 줄이고 고수준 패턴을 드러낸다는 정보시각화 결과, 단 **과도한 번들링은 경로 추적 정확도·속도를 떨어뜨린다**는 사용자 연구 → 강한 force-directed 번들링은 미채택하고 **저곡률(0.15)+alpha 누적**만 취해 추적성을 보존. **변경**: (a) `PixiAdapterPure` 에 곡선 순수 로직 신설 — `edgeArc`(진행방향 **왼쪽 고정** 수직 오프셋 → A→B 와 B→A 가 자동으로 반대편 호)·`quadPoints`·`curveSegs`(화면 픽셀 기준 adaptive)·`dashPolyline`(폴리라인 전체 대시 **위상 연속**)·`strandOffsets`, `hitTestEdge` 를 곡선 인지로 확장(직선 거리 판정은 호의 배만큼 어긋나 "보이는 선이 안 잡히는" 괴리 발생). (b) `_paintEdge` 재작성 — 실선은 네이티브 `quadraticCurveTo`, 화살촉은 **끝 접선** 각도(직선 각도로 그리면 호와 꺾임)+선 굵기 연동 크기·선보다 높은 alpha, 라벨은 곡선 중점 `Q(0.5)`, 가닥마다 **개별 `stroke()`** 호출(한 번에 몰아 stroke 하면 겹침 대비가 사라짐). `setHoverHighlight` 강조선도 같은 호 위에 겹치도록 `_edgeStyleBetween`(역방향이면 곡률 부호 반전) 신설. (c) 스타일 3종 재설계 — 기본 REFERENCES 1.4→0.85px/α0.32(색은 `#cbd2db`→`#94a3b8` 로 한 단계 진하게: 옅은 색×낮은 alpha 는 겹치기 전까지 아예 안 보이는 구간이 생긴다)·candidate 1.05/α0.5·trusted 3→1.5/α0.62·ROUTINE_USES 0.9/α0.42·crossDs 1.1/α0.52·USES 1.0/α0.5, 전 분기에 곡률 주입. SCHEMA_REF 는 굵기 단독 인코딩(상한 2.4px 에서 count 100 과 1000 이 구별 안 됨)을 **다발 가닥**(`log2` 스케일 1~4가닥 + 가닥 수에 따른 간격 확장)으로 대체. (d) `_metaG6Build` 집계 키에 `relation_type` 포함 → **읽기/쓰기가 별개 관계선 2개**로 방출되고 각자 화살표 방향 유지(종전에는 한 덩어리로 병합한 뒤 `delete s.startArrow` 로 방향까지 삭제 — 적대 프로브로 OLD=1선·방향 0 재현), 집계 굵기 가산(+0.8) 제거 후 가닥으로 대체. **최적화**: 실선 샘플링 0 · 대시만 adaptive(줌아웃 시 자동 감소) · 드래그 중 1가닥·저해상도 강등 + `dragend` 에서 `_lowFiTouched` 전량 고품질 복원(`_objSig` 재사용 함정 차단) · 단일 가닥은 모듈 상수 배열 재사용(최다 호출 경로 GC 제거). **검증**: 신규 `test_graph_edge_flow.js` **48 PASS**(곡선 기하 10·스타일 어휘 11·빌드 계약 7 + 부속) · 그래프 전 스위트 **536 PASS / 0 FAIL** · 적대 검증(main 번들 대조로 OLD 1선·방향 소실 재현) · pytest 전량 PASS · ruff PASS · **라이브 PB-0008 PASS**(실 Windows Chrome 150: 곡선 렌더·밀집 구간 진해짐·SCHEMA_REF count 47→4가닥 다발·콘솔 에러 0). §18.8 subagent 패널은 **본 세션 사용자 환경 정책(Agent tool 미허용)으로 미수행** — REVIEW 에 [SKIPPED:session-policy-no-subagent] + 자체 적대 검토 기록. **잔여**: 읽기/쓰기 2선 육안·곡선 우클릭 히트테스트·드래그 추종은 **POST-DEPLOY PB-0008**(검증 중 병렬 세션 재배포로 주입본 2회 소실 → 라이브 경합 회피 위해 원본 원복 후 중단, `visual_verification_scope: always`). 정본: TASK/CHG/REV-20260728T114015-graph-edge-flow · Run=test-runs.d/20260728T114015-graph-edge-flow.md.

---

**2026-07-28 TASK-20260728T113000-graph-noise-reduction — 그래프 뷰 시각 노이즈 제거: 상시 설명문 → ⓘ hover 툴팁 · 빈 커밋 바 숨김** (Minor §12.3 — feature-0003 web/UI 프론트 `static/{graph/graph-ctxmenu.js, graph/graph.css, admin.html, styles.css}` 단독, frontend-only·비파괴; 백엔드/API/RBAC/스키마/데이터 fetch 무변경). `/_template:entry` arg-given dispatch. **요청**(스크린샷 3곳 지목): "그래프 뷰에서 시각적으로 noisy 한 부분을 최대한 제거. 과도한 설명문이나 사용자가 한 번 인지한 후 더 이상 확인하지 않아도 되는 설명은 최대한 제거, 혹은 mouse-hover 툴팁으로 전환." **원칙 — 삭제가 아니라 이동**: 상시 표면 → 요청 시 표면(hover `title`). 실제 삭제는 *다른 곳에 정본이 있는 중복*에만 적용(empty-state 조작 안내 → 정본 = ❓ 도움말 오버레이 / 제품 카테고리 일반 문단 → 정본 = 카드 배지 + 범례 탭). **변경**: ① `_metaSecHelp()` 공용 마커 신설(`.amgr-sec-help` ⓘ, `title`+`tabindex=0`+`aria-label`, `&<>"` 이스케이프) — 컬럼 / 관계 / 사용하는 함수·프로시저 섹션의 `admin-meta-detail-note` 문단 3건을 `<h4>` 옆 툴팁으로 이관(사용자 지목 2건 포함). ② 관계 상세·클러스터 상세 서두는 **수치만** 남기고 설명 문장 제거, 제품 카테고리 일반 문단 제거(`미분류`만 1줄). ③ empty-state 2문단 → `.admin-detail-empty` 1줄(다른 pane 컨벤션 정합, 정적·동적 양쪽). ④ AI 능동 분석 box = 상태만(`분석 결과 없음`), 설명은 버튼/label/textarea `title` 로. ⑤ 절단 경고는 유지하되 1줄 압축(무음 절단 방지 계약 보존). ⑥ **커밋 바** `.admin-commit-bar:not(.has-pending){display:none}` — `0건 pending` + 비활성 `취소`/`모두 적용` 은 정보·동작이 0 이고 편집 개념 없는 pane 에서 캔버스 세로 공간만 점유했다. **CSS 1규칙·JS 무변경**(기존 `refreshPendingUI()` 의 `.has-pending` 토글에 얹음 → 상태 소스 단일 유지), 변경 발생 시 자동 재노출, 상시 상태는 사이드바 `#adminPendingSummary` 가 계속 담당. **범위 정직 표기**: ⑥ 은 사용자가 그래프 뷰에서 지목했지만 커밋 바가 **관리 콘솔 전역** 요소라 전 pane 에 적용된다(pane 화이트리스트 대안은 pane 추가마다 썩어 미채택 — REVIEW 참조). **검증**: 헤드리스 `test_detail_dbgroups.js` ⑰ 블록 신설(+14 assert — 문구가 아니라 **접근 경로**를 단정: 툴팁 존재 ∧ 본문 문단 부재 ∧ 정보 보존 4종) → **78 PASS / 0 FAIL** · `test_graph_reveal.js` 17 PASS · `node --check`(ESM) PASS · **PB-0008 라이브 PASS**(실 Windows Chrome/150 via relay, `docker cp` 스테이징: 상세 패널 `p.admin-meta-detail-note` **0건**, `h4=["컬럼 (2) ⓘ","사용하는 함수·프로시저 (10) · 읽기 3 · 쓰기 7 ⓘ","AI 능동 분석"]`, 툴팁 전문 실측, 패널 텍스트 **852→512자**, 커밋 바 `display:none`(0건) ↔ `flex`+`has-pending`(1건 pending) **왕복**, 좌하단 `변경 없음` 유지). **라이브에서만 잡힌 결함 1건**: 툴팁 조사 `함수·프로시저**을**` → `를`(종성 없는 명사) 정정 — 헤드리스는 통과했고 실화면 판독에서 포착. **한계 정직 표기**: native `title` 툴팁은 OS 레이어 렌더라 **스크린샷 미캡처** — 내용은 DOM 실측, 픽셀 클래스(레이아웃) 변경만 스크린샷(§16.6 변경-클래스 분기 준수). 검증 중 다른 세션 롤링 배포 3회로 스테이징이 두 번 덮여 그때마다 rebase·재주입·재측정(최종 판독은 전부 패치 서빙 시점). §18.8 subagent 패널은 **본 세션 사용자 환경 정책(Agent tool 미허용)으로 미수행** — REVIEW 에 자체 적대 검토로 정직 기록. `test_detail_colsel.js`·`test_graph_colnav.js` 하네스 실행 실패는 **main baseline 에서도 동일 재현**(ITEM-09 ES-module 리팩터 잔재, pre-existing·본 cycle 범위 밖). **상태**: 구현·검증 완료 → cycle-final(PR·머지·배포) 진행. deploy_scope: included(FIRST_REQUEST.md 전역 §12.2) — 배포 후 main 기반 PB-0008 재확인 예정. worktree `ai/claude/feature-0003-graph-noise-reduction`(base main 86c5900b → rebase **0062acb3**). 정본: TASK/CHG/REV-20260728T113000-graph-noise-reduction · FUNCTION REQ-20260728-graph-noise-reduction(AC-GNR-1~6) · Run=test-runs.d/20260728T113000-graph-noise-reduction.md · 증적 `artifacts/pb0008/feature-0003-graph-noise-reduction/*.png`.

---

**2026-07-27 TASK-20260727T180036-share-bar-layout — 공유 대화 뷰: 액션 버튼을 하단 바 우측으로 · '조회 N회'를 페이지 상단으로 · 바 크기는 유지하고 hover 시에만 확장** (Minor §12.3 — feature-0003 web/UI 프론트 `static/{share.html,share.css}` 단독, frontend-only·비파괴, 백엔드/RBAC/스키마/엔드포인트/`share.js` 무변경). 사용자 요청(`/_template:entry` arg-given): "['링크 복사', '내 계정에서 fork'] 버튼들을 bottom-bar 내부의 우측으로 / bottom-bar 의 '조회 N회' 는 페이지 상단으로" + 같은 turn 추가 요청 "하단 바 크기는 기존을 거의 유지, 늘려야 하면 mouse-hover 반응형 + 자연스러운 애니메이션". **변경**: `.share-actions` 그룹(링크 복사·대화에 참여·내 계정에서 fork·로그인 링크 4종)을 헤더에서 `<footer class="share-footer">` 안 안내문 뒤로 통째 이동(바가 `space-between` 이라 우측 정렬) — 조건부 노출(hidden)인 참여/로그인만 헤더에 남기면 같은 액션군이 상·하로 쪼개지므로 그룹 경계를 지켰다. `#shareViewCount` 는 헤더 `.share-meta` 마지막 항목으로 이동(class 를 `share-meta-item` 으로 정렬, 소유자·범위·제품·만료와 같은 줄). **바 높이**: 액션을 품고도 기본 높이를 지키려 바 세로 패딩 8→6px + 버튼 규격 `2px 10px`/`0.75rem` 으로 축소 → **변경 전 35.0px → 변경 후 35.2px(Δ+0.2px)**. **hover 확장**: `@media (hover:hover)` 에서 `:hover`·`:focus-within`(키보드 대응) 시 패딩 10px·버튼 `6px 13px`/`0.8125rem`·배경 불투명·상단 그림자를 `transition .18s ease` 로 적용(35.2→52.5px, 버튼 31.5px). 터치(`hover:none`)는 확장 규격 상시 적용, `prefers-reduced-motion` 은 transition 만 off. **검증**: 헤드리스 chromium 실 레이아웃 **8/8 PASS**(실 share.html+share.css, 변경 전 기준값은 `git show main:` 원본 렌더로 실측) · 구조 회귀 `tests/test_share_bar_layout.py` **5 PASS** · `make test` 전체 실패 15건이 clean main baseline 과 **차집합 0**(회귀 없음) · ruff PASS · 시각 증거 before/after/hover 3건. §18.8 subagent 패널은 **본 세션 사용자 환경 정책(Agent tool 미허용)으로 미수행** — REVIEW 에 [SKIPPED:session-policy-no-subagent] + 자체 적대 검토 H1~H7(하단 여백·print 숨김·:empty 규칙·point rail z-order·좁은 화면 wrap·확장 클릭 간섭·share.js DOM 의존)로 정직 기록. **상태**: **완결** — PR #958 머지(main 486a587c) → `make deploy-web-only`(web-a/web-b 486a587c soak 통과) → **POST-DEPLOY PB-0008 라이브 PASS**(실 Windows Chrome/150, 익명 아닌 로그인 상태의 실 공유 링크: AC-SBL-1 액션 4종이 하단 바 우측·바 우측 여백 16px·헤더에 액션 0 · AC-SBL-2 `조회 16회`가 헤더 `.share-meta` 4번째 항목 · AC-SBL-3 기본 바 높이 35px(헤드리스 35.2px 와 정합) · AC-SBL-4 hover 시 53px·패딩 6→10px·상단 그림자·배경 불투명, transition 0.18s · `링크 복사` 클릭 → `복사됨 ✓`(is-copied) · 최하단 스크롤(scrollY=maxY=8303)에서 마지막 메시지 bottom 732 < 바 top 783 으로 미가림 · 버튼 hit-test 통과 · 페이지 에러 0, evidence/pb0008-share-bar-layout-live-{default,hover,header,copied}-20260727.png). 정본: TASK/CHG/REV-20260727T180036-share-bar-layout · Run=test-runs.d/20260727T180036-share-bar-layout.md.

---

**2026-07-27 TASK-20260727T160748-product-picker-scroll — 작업 화면 제품 선택 드롭업이 열릴 때 현재 선택 제품을 목록 중앙에 스크롤** (Minor §12.3 — feature-0003 web/UI 프론트 `static/app.js` 단독, additive·비파괴, RBAC/스키마/백엔드/엔드포인트 무변경). 사용자 요청("현재 선택한 product 가 중앙에 위치하도록 스크롤을 위치시켜주세요. 현재는 항상 최상단이라 상대적인 위치를 찾기 불편합니다") — `openProductDropup()` 이 매번 메뉴를 재렌더해 `scrollTop=0`(최상단)으로 시작하던 것을, `scrollProductDropupToSelected(menu)` 로 `.is-selected` 항목을 목록 세로 중앙(±1px)에 놓는다(경계는 `[0, scrollHeight-clientHeight]` clamp — 첫/마지막 항목은 최상단/최하단에 멈추되 여전히 보임). 선택 항목이 없으면(auto) 스크롤 무간섭. 호출 2곳 = 드롭업 open + `renderProductChip()` 의 열린-상태 재렌더(재렌더가 scrollTop 을 0 으로 리셋하므로 복원). 검색 입력 자동 포커스는 `focus({preventScroll:true})` 로 바꿔 포커스發 자동 스크롤이 정렬을 되돌리지 않게 했다. `scrollIntoView({block:"center"})` 는 조상(페이지) 스크롤까지 움직여 미채택. **검증**: 헤드리스 chromium 145 실 레이아웃 11/11 PASS(실 app.js 함수 + 실 styles.css — offsetParent 계약 실측·중앙 정렬·가시성·양단 clamp·무선택 무간섭·짧은 목록·menu 부재 무예외·검색칸 유무 양 경로) · `node --check` PASS · 시각 증거 before/after 2건. §18.8 subagent 패널은 **본 세션 사용자 환경 정책(Agent tool 미허용)으로 미수행** — REVIEW 에 [SKIPPED:session-policy-no-subagent] + 자체 적대 검토 H1~H8 로 정직 기록. **상태**: **완결** — PR #955 머지(main b30bb45d) → `make deploy-web-only`(web-a/web-b soak 통과) → **POST-DEPLOY PB-0008 라이브 PASS**(실 Windows Chrome/150: AC-PPSC-1 centerDelta=0 · AC-PPSC-2 양단 clamp · AC-PPSC-3 검색 포커스 유지 · 페이지 에러 0, evidence/pb0008-product-picker-scroll-live-20260727.png). 정본: TASK/CHG/REV-20260727T160748-product-picker-scroll · Run=test-runs.d/20260727T160748-product-picker-scroll.md.

---

**2026-07-27 TASK-20260727T113640-model-persist — 대화별 "마지막 요청 모델" 보존 + '+ 새 대화'=haiku 유지** (Minor §12.3 — feature-0003 web/UI 프론트 `static/{app.js,index.html}` + 백엔드 `routers/conversations.py`; 스키마/RBAC/신규 엔드포인트 0, `/api/history` 응답 필드 1개 additive). `/_template:entry` arg-given dispatch. **요청**: "대화 중 assistant 에게 마지막으로 요청했던 모델을 기준으로 새로고침이나 다른 대화에서 돌아왔을 때 그 선택을 보존. 다만 '+ 새 대화' 로 선택되는 모델은 haiku 그대로." **진단(3중 결함)**: composer 모델 선택 `state.selectedModel` 이 **메모리 전용 전역** — ① 새로고침 시 소실(기본값 복귀) ② 대화를 바꿔도 전역값 잔존 → 직전 대화 모델이 다른 대화로 누출 ③ 선택 후 '+ 새 대화' 를 눌러도 그대로 이어져 "새 대화=haiku" 계약 파손. 추론 강도(reasoning-effort)는 이미 대화별 KV 영속 + `/api/history` hydration 이 있었으나 모델엔 대응 경로 부재. **수정(추론 강도와 동형, additive)**: 백엔드 — `_model_kv_key(account)`(키 `model:<account_id>`, 그룹 대화 계정별 격리) 신설, `ask()` 는 클라이언트 **명시** model 일 때만 KV 저장하되 **세션 기본값과 같으면 빈 값으로 해제**(기본값 이탈만 저장 → 이후 기본 모델 상향이 기존 대화에 반영), `history()` 가 `_is_safe_model_name`+`_is_allowed_api_model` 재검증 후 payload `model` 반환(`DENY` window·열람 불가 시 `""`). 프론트 — `loadHistory` 비-append 로드 hydration, `_modelHydrationShouldSkip`(미전송 선택 보존)·`_resetComposerModelSelection`(컨텍스트 이탈 리셋) 순수 함수 2종 + 리셋 4 호출지점('+ 새 대화'·대화 전환 즉시·활성대화없는 랜딩·로그아웃), pending 대화 entry 모델 캡처/복원, 모델 라벨 초기 placeholder 중립화. **의도적 비대칭**: 모델은 localStorage 미러를 두지 않는다(미러가 있으면 새 대화가 직전 모델 상속 → 요구 파손) — 대조군 포함 테스트로 고정. **검증**: `tests/test_model_persist.py` **14 PASS**(계정별 격리·열람불가/DENY·allowlist 밖 400+KV 미도달·기본값 해제·미지정 재dispatch 미덮어씀) · `tests/verify_model_persist.mjs` **32 PASS**(hydration 가드 5·기본값 폴백 2·리셋/미전송보존 R1~R5·전송 clobber 가드 D1~D4·구조계약 S1~S8) · `node --check`/`py_compile`/ruff PASS · `make test` 전체 회귀 0(선존 FAIL 4건은 **clean main 84f2e5ab 에서도 동일 재현** 확인 → 무관) · **§18.8 [SUBAGENT] 적대 패널 2라운드 — 둘 다 BLOCK, 지적 10건 전건 in-cycle 수정**(1R: B1 랜딩·로그아웃 미커버 / C1 전환 대기 창 영구 오염 / C2 기본값 영구 고정 / C3 그룹 타멤버 누출·과금 / C4 테스트 위양성. 2R: **B-B 1R 수정이 만든 자체 회귀**(랜딩 재로드가 미전송 선택 삭제) / C-A `moveConversationToFolder` hydration 공백 → 저장값 clobber / C-B 최종 fallback 리터럴 sonnet / C-C 열린 메뉴 하위 재렌더 / C-D `model:unknown` 공유 슬롯. B-A 스테이징 지적은 검토 시점 타이밍 아티팩트로 확인·재확인 관례화). **완결(2026-07-27)**: verify PASS → PR #953 머지(main **8cfa00b0**) → `make deploy-web-only` 무중단 롤링(web-a/web-b 8cfa00b0·90s soak PASS·Caddy no-drift) → **POST-DEPLOY PB-0008 라이브 PASS**(실 Windows Chrome/150 via win-browser relay, https://localhost/ bootstrap_admin: **AC-MP-1** sonnet 선택·전송 후 `/api/history payload.model=claude-sonnet-4` 서버왕복 + 재로드 시 라벨 `모델: claude-sonnet` 복원 / **AC-MP-2** 타 대화 전환 시 `claude-haiku` → 복귀 시 `claude-sonnet`(전역 누출 0) / **AC-MP-3** '+ 새 대화' = `모델: claude-haiku`(직전 sonnet 미상속). 시각증거 evidence/pb0008-model-persist-{restore,newconv}-20260727.png · 콘솔 에러 0). **AC-MP-9(미전송 선택 보존)는 라이브 미검증** — 유발 트리거(사이드바 일괄삭제·제품변경 실패 롤백)가 라이브 테넌트에서 파괴적/유발 불가 → 단위검증(R3b/R4/R5)만 커버하고 미수행 사유를 test-runs.d 에 명시(검증으로 오인 금지). **사용자 요청 해소**. deploy_scope: included(FIRST_REQUEST.md 전역 §12.2). 선존 동작 부기 — 인자 없는 새로고침은 `initializeWorkspace` 가 직전 대화를 자동 선택하지 않는 기존 설계라 빈 화면 시작(본 변경 무관). 검증용 테스트 대화 `20260727032348-82e678df` 는 계정에 남겨 둠(정리는 사용자 판단). worktree `ai/claude/feature-0003-model-persist`(base main 84f2e5ab). REV/CHG/TASK-20260727T113640-model-persist + REV-20260727T124500-postverify.

---

**2026-07-27 TASK-20260727T102027-sql-diff-highlight — ```diff``` 코드블록 내 SQL 구문 하이라이트** (Minor §12.3 — feature-0003 web/UI 프론트 `static/{app.js,share.js,styles.css,share.css}` 단독, frontend-only, vendor 무추가; sql-md-highlight 후속). `/_template:entry` arg-given dispatch. **요청**: "diff 구문을 나타내는 부분에서도 SQL 하이라이트가 적용되도록 구성해주세요." **진단**: 직전 sql-md-highlight 는 ```sql 블록만 처리 — `enhanceDiffBlocks` 는 diff 라인 코드를 plain textContent 로만 넣어 diff 내 SQL 미하이라이트(+/-/context 색만). **수정**: ① SQL 토크나이저 코어를 `sqlTokenizeToFragment(text)→DocumentFragment` 로 추출(```sql·diff 공용), `highlightSqlInto` wrapper 화. ② `looksLikeSql(text)` 게이트(verb 핵심 DML/DDL ∧ clause SQL 구조 키워드, `\b` 경계로 camelCase 오탐 억제) — SQL diff 에만 적용해 비-SQL 파일 diff 오색칠 방지. ③ `enhanceDiffBlocks`: sqlMode 면 diff 라인 코드를 `sqlTokenizeToFragment` 로 토큰화(textContent-only) + `pre.diff-sql`. add/del 은 배경 tint·좌측 border·gutter(+/-) 로 유지, 라인 평문색은 기본 #c0caf5(토큰이 syntax색 — GitHub 식). ④ CSS `.sql-tok-*` 셀렉터 일반화(`pre.sql-block`→`.message-content .sql-tok-*`, 토크나이저 전용 클래스라 bleed 없음) + `.diff-block.diff-sql .diff-line` 기본색. **검증**: headless chromium(chromium-1208, 실 vendor marked+DOMPurify, app.js 추출 실소스) **21/21 PASS**(회귀 ```sql 유지·SQL diff 토큰 하이라이트·add/del 보존·평문 기본색·배경 tint 유지·gutter 보존·텍스트 무손실·비-SQL diff 무영향·게이트 오탐억제[JS·Python]·XSS 무력화) · `node --check` · §18.8 [SUBAGENT] 적대 패널 · 시각증거 evidence/sql-diff-highlight-20260727.png. **완결(2026-07-27)**: verify PASS → PR #948 머지(main **8d69490c**) → `make deploy-web-only` 무중단 롤링(web-a/web-b 8d69490c·healthy·RestartCount 0) → **POST-DEPLOY PB-0008 라이브 PASS**(실 Windows Chrome/150 via win-browser relay, https://localhost/ bootstrap_admin: 배포본 markdownToHtml eval[SQL diff] → `pre.diff-block.diff-sql`·sql-tok 9·getComputedStyle keyword #bb9af7·string #9ece6a·number #ff9e64·평문 기본 #c0caf5·add/del 배경 tint·**hunk 미토큰화**·gutter 보존·script 0·콘솔 에러 0, evidence/pb0008-sql-diff-live-20260727.png). **사용자 요청 해소**. deploy_scope: included(§12.2). §18.8 [SUBAGENT] SHIP-WITH-FIXES→MAJOR(looksLikeSql 오탐)+MINOR3 in-cycle 수정. worktree `ai/claude/feature-0003-sql-diff-highlight`(base 01ad5060)·postverify `feature-0003-sql-diff-highlight-postverify`. REV/CHG/TASK/AC-20260727T102027 + REV/CHG-20260727T110000-postverify.

---

**2026-07-24 TASK-20260724T180458-sql-md-highlight — assistant markdown 답변 ```sql``` 코드블록 구문 하이라이트** (Minor §12.3 — feature-0003 web/UI 프론트 `static/{app.js,share.js,styles.css,share.css}` 단독, frontend-only, vendor 무추가; 백엔드/스키마/RBAC 0). `/_template:entry` arg-given dispatch. **요청**: "서비스 내 assistant 가 md 형식으로 쿼리를 전달할 때, sql 관련 하이라이트가 적용된 상태로 전달하도록 구성해주세요. 현재는 md 내 plaintext 와 같이 전달하고 있어 가독성이 떨어집니다." **진단**: 렌더 파이프라인(`markdownToHtml`=`marked.parse`→`enhance*Blocks`→`DOMPurify.sanitize`)에 syntax highlighter(highlight.js/prism) 부재 → ```sql``` 블록이 `<pre><code class="language-sql">` 로만 렌더돼 색 없는 monospace(plaintext). **수정**: 경량 SQL 토크나이저 `enhanceSqlBlocks(html)` 신설(기존 `enhanceDiffBlocks` 패턴 정합, 외부 vendor 무추가) — comment/string/number/keyword/type/function(`(` 휴리스틱)/variable 을 `<span class="sql-tok-*">` 로 감싼다(토큰 텍스트 `textContent`-only → XSS 무첨가·DOMPurify 통과). 체인 `marked.parse`→`enhanceDiffBlocks`→**`enhanceSqlBlocks`**→`enhanceAttachmentEditBlocks`→mermaid→sanitize, lang 필터로 diff/mermaid/attachment 와 disjoint. app.js(메인)·share.js(공유 뷰 로컬 미러, byte-identical). CSS = diff-block 과 동일 Tokyo Night 팔레트(pre 항상 다크 → 테마 분기 불필요, 사용자 말풍선만 sql-block 배경 다크 고정). **검증**: headless chromium(chromium-1208, 실 vendor marked+DOMPurify) 파이프라인 **23/23 PASS**(토큰화·텍스트 무손실·DOMPurify span/class 보존·XSS 라이브 DOM 무력화·비-SQL disjoint·getComputedStyle 색 실측) · `node --check` · **§18.8 [SUBAGENT] 적대 패널 6/6축 PASS(SHIP·BLOCK/MAJOR 0·jsdom 주입 열거 + 1.12M자 ReDoS)** · 시각증거 evidence/sql-md-highlight-20260724.png · **verify-completion PASS**(CHECK#13 Windows-browser fragment 포함). **완결(2026-07-24)**: verify PASS → PR #946 머지(main **0313b135**) → `make deploy-web-only` 무중단 롤링(web-a/web-b 0313b135·90s soak PASS·caddy no-drift·asset stamp `?v=dev` 잔존 0·마이그레이션 없음) → **POST-DEPLOY PB-0008 라이브 PASS**(실 Windows Chrome/150 via win-browser relay, https://localhost/ bootstrap_admin: 배포본 `markdownToHtml` eval → `pre.sql-block`·sql-tok 26토큰·getComputedStyle Tokyo Night 색 정확[keyword #bb9af7/600·func #7aa2f7·string #9ece6a·number #ff9e64·comment #737aa2·pre #1a1b26]·텍스트 무손실·script 주입 0·콘솔 에러 0, evidence/pb0008-sql-highlight-live-20260724.png). **사용자 요청 해소**. deploy_scope: included(FIRST_REQUEST.md 전역 §12.2). worktree `ai/claude/feature-0003-sql-md-highlight`(base main 28ec78b3, rebase→89d219b5)·postverify `ai/claude/feature-0003-sql-md-highlight-postverify`. REV/CHG/TASK/AC-20260724T180458-sql-md-highlight + REV/CHG-20260724T184500-sql-md-highlight-postverify.

---

**2026-07-24 TASK-20260724T123600-csv-download-wiring — assistant "CSV 다운로드 가능" 답변의 실제 다운로드 배선 누락 수정 (conv-audit csv-inline-no-download)** (Major, cross-cut — feature-0003 web/UI 프론트 `static/{app.js,share.js,styles.css}` + cross-cut 코드 거주 feature-0002 `agent_core.py`·`modules/tools.py`). `/_template:entry` arg-given dispatch. **요청**: "서비스 내 대화에서 csv 파일이 다운로드 가능하다는 assistant의 답변이 확인되었지만, 실제 csv 다운로드 기능에 대한 배선이 누락되어 관련된 기능을 사용할 수 없는 상태" (대화 '킹스레이드 배틀 로그 차원별 집계' / bootstrap_admin). **진단(DB 실측)**: 대화 `20260724022429-515c0fd9` assistant 8메시지 중 5개가 "다운로드하실 수 있습니다"라고 하면서 다운로드 수단이 전무(예: msg 1342 = ChapterIndex/DungeonIndex/Difficulty 차원별 집계 191행을 인라인 ```csv``` 텍스트로 붙이고 "위 데이터를 CSV 형식으로 다운로드하실 수 있습니다"만). **근본원인**: 답변→다운로드 링크 후처리기 `_collapse_large_tables` 가 **Markdown 표(`|...|`)만 인식하고 ```csv``` fenced 블록은 blind spot** → 모델이 결과를 ```csv``` 로 붙이면(지배 패턴) 링크 미주입 dead-end. `/api/file` 엔드포인트·권한 게이트(`conversation.file.read.*`)·`/shared/out` 파일저장은 정상. **수정(3계층)**: (1) **프론트(app.js/share.js) — `enhanceCsvBlockDownloads`**: 모든 ```csv``` 코드블록에 클라이언트 Blob "📥 CSV 다운로드" 버튼(UTF-8 BOM·Excel 한글). sanitize 이후 라이브 DOM(enhanceDiffBlocks/enhanceFilePreviewLinks 동형). 서버 파일 유무 무관 항상 다운로드 보장 — LLM 준수·csv_paths 영속에 비의존. 백엔드가 /api/file 링크를 뒤에 주입한 절단-미리보기 블록엔 버튼 skip(오도 방지). (2) **백엔드(agent_core.py) — `_collapse_large_csv_blocks`**: 대형 ```csv``` 블록을 MD표와 동일 처리(값 토큰 매칭으로 저장 CSV 찾아 헤더+미리보기 접기 + `📎 [전체 N행 미리보기](/api/file?path=)` 주입, 매칭 실패 시 데이터 손실 없이 원문 유지). 초안·redteam 3경로 체인. (3) **가이던스(tools.py) — execute_sql·scratch_sql**: "저장된 CSV 는 다운로드 버튼으로 자동 제공 — 링크 직접 생성 불필요, 전체 데이터 붙여넣기 금지" 항상(절단 무관) 안내. **검증**: 전체 pytest **2303 passed / 2 skipped**(신규 `test_collapse_csv_block_download.py` 6 + 기존 collapse 5 무회귀 + 가이던스 문구 정합 2건 갱신) · jsdom `verify_csv_block_download.mjs` **18 PASS**(버튼 삽입·멱등·/api/file skip·빈블록·비-csv) · `node --check` · **CHECK#13** = test-runs.d Windows-browser fragment. **완결(2026-07-24)**: verify PASS → PR #926 머지(main **dc316152**) → `make deploy-web` 무중단 롤링(web-a/web-b + insight/ask-worker = dc316152·soak 통과·gateway/caddy no-drift·롤백 0) → **POST-DEPLOY PB-0008 라이브 PASS**(win-browser 실 Windows Chrome, 대화 515c0fd9 '도전 던전 전투 로그…' 16메시지: 인라인 ```csv``` 블록 아래 "📥 CSV 다운로드" 버튼 렌더·클릭 시 Blob text/csv size=2603 다운로드·콘솔 에러 0). 서빙 app.js/share.js/styles.css 신 심볼 curl 확증. **사용자 요청 해소**. worktree `ai/claude/csv-download-wiring`(base main e88cce6f, rebase→dc316152)·postverify `ai/claude/csv-download-postverify`. REV/CHG/TASK/TEST-20260724T123600-csv-download-wiring + REV-20260724T133000-csv-download-wiring-postverify.

---

**2026-07-24 TASK-20260724T112446-share-scroll-bottom — 공유 대화 링크 화면 진입 시 문서 스크롤 맨 아래(최신 메시지) 고정** (Minor §12.3 — feature-0003 web/UI 프론트 `static/share.js` 단독; 백엔드/스키마/RBAC/엔드포인트 0). `/_template:entry` arg-given dispatch. **요청**: "공유된 대화 링크 화면에 진입 시, 화면 스크롤이 가장 아래부터 위치하도록 구성해주세요." **현상**: `/share/{token}` 뷰가 `fetchShare→render` 후 스크롤 미조작 → 진입 시 문서 맨 위(첫 메시지)에서 시작. 대화는 시간순 append 라 최신은 맨 아래 → 진입 즉시 최신을 보려면 매번 아래로 스크롤 필요(메신저/채팅 관례 위배). **수정(frontend-only, `share.js` 단독)**: 초기 fetch→render 체인에 `engageInitialBottomPin()` 1회 호출 — 진입 즉시 `scrollShareToBottom()`(문서 맨 아래, 기존 clamp idiom 재사용), 지연 렌더(표/mermaid/이미지/point rail 로 문서 높이 증가) 동안 `#shareMessages` ResizeObserver 재고정(미지원 시 `[150,400,1000,2500]ms`+load 폴백), 사용자 조작(wheel/touch/keydown)·3s 타임아웃 시 pin 해제(리스너 remove + observer disconnect, 멱등). **무회귀**: `pageBranchShare`(feature-0019 버전 페이징 위치보존)·`scrollShareMessageIntoCenter`(rail 점프)에서 `releaseShareBottomPin()` 선행 → 진입 pin 이 기존 스크롤 로직/사용자 조작과 충돌 안 함. **검증**: `node --check` PASS · §18.8 적대 프론트 리뷰(REV-20260724T112446-share-scroll-bottom) · **CHECK#13** = test-runs.d Windows-browser fragment(PRE-COMMIT 문법+리뷰 PASS + POST-DEPLOY 라이브 계획; headless 는 layout 부재로 문서 스크롤 실측 불가 사유 명시 — 카고컬트 방지). **완결(2026-07-24)**: verify PASS → PR #918 머지(main **94b4003a**) → `make deploy-web-only` 무중단 롤링(web-a/web-b·90s soak PASS·이미지 mysql-ai-web:94b4003a) → **POST-DEPLOY PB-0008 라이브 PASS**(win-browser 실 Windows Chrome, 실 공유 링크 16-메시지 대화: AC-SSB-1 진입 scrollY 53282==maxY·atBottom=true / AC-SSB-3 top 스크롤 후 stayedAtTop·snap-back 없음 / AC-SSB-2 최종 54118px 안착 / pageerror 0). 서빙 `/static/share.js`(47,901B) 신 심볼 5종·dead window-load 리스너 소멸 curl 확증. **사용자 요청 해소**. deploy_scope: included(FIRST_REQUEST.md 전역 §12.2). worktree `ai/claude-corp/feature-0003-share-scroll-bottom`(base main 1dc3a6a2)·postverify `feature-0003-share-scroll-postverify`(base 94b4003a). REV/CHG/TASK/TEST-20260724T112446-share-scroll-bottom + REV/CHG-20260724T140000-share-scroll-bottom-postverify.

---

**2026-07-24 TASK-20260724T020632-aiops-model-canonical — '운영 현황' 서브탭 잔존 raw 모델 표기 canonical 정합 (usage-model-canonical 후속)** (Minor §12.3 — feature-0003 `ai_ops.py` 단일 + test; admin.js/스키마/RBAC/엔드포인트 계약 0). `/_template:entry` 후속 요청("나머지 범위 또한 실제값과 정합"). **범위**: 직전 PR#914 가 남긴 유일한 raw 모델 그룹핑 = `감사 > AI 운영 현황 > 운영 현황` 서브탭. **변경 3곳**: (1) categories 집계 `COALESCE(resolved_model, model)` → `canonical_usage_model_sql(...)` — taxonomy 카테고리 롤업이라 모델 차원 미노출; calls/tokens 불변(정수 sum), cost 는 round 재결합으로 최하위 4번째 소수(≈$0.0001) 미세 변동 가능(더 정확) — 마지막 raw 그룹핑 제거(SSOT 일관·향후 재분점 예방). (2) `_query_activity` '최근 활동' feed 주 배지 `model` → `canonical_usage_model(served)` — 활동 목록 모델명이 도넛과 동일 canonical 실 모델명으로 표시. **`req_model`·`resolved_model` 은 raw 보존** → 상세 '요청 alias → 서빙 모델' 라우팅 audit 유지(예: 폴백행 배지=`edge`, 상세=`claude-haiku-4 → gemma4:e2b`). (3) **[적대 리뷰 M1 수정]** `admin.js` 활동 상세 폴백 `srvM = r.resolved_model || r.model` → `|| r.req_model` — 배지 canonical 화로 `r.model` 이 canonical 이 되어 resolved=NULL+비canonical req(auto 등) 행에서 날조 화살표(auto→edge)를 만들던 것을 차단(상세=100% raw). 비용 무변경. **검증**: §18.8 적대 리뷰([SUBAGENT] SHIP-WITH-FIXES → M1/m1/m2 3건 반영) · 전체 pytest **2287 passed / 2 skipped**(test_ai_ops 갱신 + 신규 canonical/NULL-resolved 2건) · admin.js `node --check` · **Windows-browser modelDetail eval 4시나리오 PASS**(정상변형·gemma폴백=실화살표 / NULL+auto=`auto` 날조없음 / NULL+haiku=단일). **전 코드베이스 raw COALESCE 모델 그룹핑 0건**(grep). admin.js 변경 → check #13(scope=always) 활성, test-runs.d Windows-browser fragment 동반. **잔여**: 배포(web-only) → POST-DEPLOY 라이브 PB-0008(운영 현황 배지·활동 상세 라우팅). worktree `ai/claude-corp/aiops-model-canonical`(base main 71813eb3). REV/CHG/TASK-20260724T020632-aiops-model-canonical. **← 직전 usage-model-canonical(PR#914) 의 follow-up §8.1 항목 해소.**

---

**2026-07-24 TASK-20260724T012954-usage-model-canonical — 관리 콘솔 LLM 사용량 '모델별 비중' 중복 명칭 모델 분점 해소** (Minor §12.3 — feature-0003 백엔드 집계 + shared; admin.js/스키마/RBAC/엔드포인트 계약 0). `/_template:entry` arg-given dispatch. **신고**: `감사 > AI 운영 현황 > LLM 사용량` 서브탭의 '모델별 비중' 도넛에서 중복 명칭 모델들이 차트를 나누어 점유. **근본원인**: `admin_usage.admin_llm_usage` 의 `by_model`(및 by_account/by_day_model)이 `COALESCE(resolved_model, model)` 를 그대로 GROUP BY — 이 값에 같은 논리 모델의 여러 표기(litellm 라우팅 변형 alias `-interactive`/`-chat`/`-root`/`-interactive-root`/`-chat-root`, 실 모델 ID `claude-haiku-4-5-20251001`, edge 폴백 실모델 `gemma4:e2b`)가 섞여 한 모델이 N 세그먼트로 분점(litellm_config.yaml 상 `claude-haiku-4*` 6 alias 전부 anthropic/claude-haiku-4-5 라우팅 확인). **수정(근본, SSOT)**: `shared/model_catalog.py` 에 `canonical_usage_model()`(Python) + `canonical_usage_model_sql()`(PG `starts_with` CASE — LIKE '%' 회피로 파라미터 쿼리 이스케이프 불필요) 추가. 규칙 `claude-haiku-4*`→`claude-haiku-4`·`claude-sonnet-4*`→`claude-sonnet-4`·`gemma*`/`edge`/`edge-fallback`/`auto`/`core`/`code`→`edge`·그 외 원본 유지(self-surface). `admin_usage.py`(by_model·by_account·by_day_model GROUP BY + `_query_usage_conversations` 필터·모델 분해)·`profile.py`(개인 사용량 도넛·드릴다운 일관성)·`admin_console.py`(대시보드 '모델별 토큰' 위젯) 에 적용. by_model row 는 `model==resolved_model==canonical` 로 채워 프론트(modelKeyOf/도넛 라벨/색맵/칩/드릴다운) **무변경** 정합. **부수 gap 해소**: `_estimate_llm_cost_usd` 단가 조회 키 canonical 화 — 단가표(`_LLM_PRICE_USD_PER_1M`)가 base alias 만 등록해 변형/실ID 가 비용 $0 로 오표시되던 gap 을 모든 app.X 호출부에 중앙 정정(edge/gemma 는 미등록→0 로컬 무료 유지, gemma 폴백 호출 haiku 단가 과대계상 정정). **검증**: 전체 pytest **2280 passed / 2 skipped**(기존 baseline), 신규 test_c1~c4 + test_q2_model_filter 갱신 · 실 PG(90일) 실측 **7 세그먼트 → 3 실제 모델 병합**(claude-haiku-4 64,552,777 tok · edge 30,431,975 · claude-sonnet-4 785,900; run_id distinct canonical 그룹 dedup). **범위 밖(follow-up §8.1)**: `ai_ops.py` 운영 현황 task×model(별도 축). **잔여**: 배포(백엔드 baked — web/워커 재빌드) → POST-DEPLOY PB-0008 라이브 도넛 시각검증. worktree `ai/claude-corp/usage-model-canonical`(base main 29ef0baf). REV/CHG/TASK-20260724T012954-usage-model-canonical.

---

**2026-07-23 TASK-20260723T080415-floating-menu-close-fix — floating 메뉴(특히 폴더 '···') 안 닫히던 결함 수정** (Minor §12.3 — feature-0003 web/UI 프론트 단독; RBAC/스키마/엔드포인트 0). universal-ctxmenu 후속 사용자 신고. **신고**: 우클릭 확장은 정합하나 폴더 '···' 메뉴가 열린 뒤 다른 항목 클릭 등으로 **닫히지 않음**. **근본원인**: `closeFloatingMenus()` 가 제거 대상 id 를 `["convItemMenu","bubbleMsgMenu"]` 로 하드코딩 — feature-0024 폴더 메뉴(`id="folderMenu"`) 추가 시 목록 누락 → 바깥클릭/ESC/scroll/toggle 어느 경로도 폴더 메뉴 제거 못함(공존·트리거 상태 잔존 동반). universal-ctxmenu(우클릭)가 폴더 메뉴를 쉽게 열게 되며 pre-existing drift 표면화. **수정(drift-proof SSOT, app.js+styles.css)**: `openFloatingMenu` 가 생성 메뉴에 `data-floating-menu` 마커 부여, `closeFloatingMenus` 가 `[data-floating-menu]` **id 무관 일괄 제거**(신규 메뉴 자동 포함)+폴더 트리거 `is-open` 리셋 추가. 정합 3건(folderMenu=1급 승격): share-range ESC 가드·unread-sync skip 가드에 folderMenu 포함 + `.conv-folder-menu-trigger.is-open{opacity:1}` CSS. **비변경**: conv-item '···'·말풍선 '☰' 닫힘(마커 제거가 superset), 백엔드/RBAC 0. **검증**: `node --check` PASS · §18.8 적대 리뷰(general-purpose) **SHIP**(BLOCKING/MAJOR 0·NIT 3 fold-in). **완결(2026-07-23)**: verify PASS → PR #902 머지(main **57ecc758**) → `deploy-web.sh --web-only`(soak PASS·스탬프 8373a9f479e2) → **POST-DEPLOY PB-0008 라이브 PASS**(win-browser Chrome 150, 배포본 57ecc758, 테스트 폴더 생성→검증→삭제: AC-1 바깥클릭·AC-2 ESC·AC-3 scroll·AC-4 토글+트리거 상태 복원 닫힘·AC-5 conv-item 무회귀·errCount 0 — **사용자 신고 결함 해소**). worktree `ai/claude/feature-0003-floating-menu-close-fix`(base main 66bd3419). REV/TEST-20260723T080415-floating-menu-close-fix.

---

**2026-07-23 TASK-20260723T071355-universal-ctxmenu — 서비스 UI 우클릭 = 보편 확장 메뉴 단축** (Major §12.3 — feature-0003 web/UI app.js 단독; 백엔드/스키마/RBAC/엔드포인트 0). `/_template:entry` arg-given dispatch. **요청**: 각 요소 우클릭이 그 요소의 기존 확장 메뉴로 동작 — 대화 목록·폴더 헤더='···', 대화 로그(말풍선)='☰', "등과 같이". **구현(frontend-only, app.js 2지점)**: ① `openFloatingMenu` 커서 앵커(`_floatingMenuAnchorPoint`, 1회 소비·finally 방어 해제) — 우클릭이면 커서 위치, 버튼 클릭이면 기존 trigger-rect(anchor=null byte-동치·회귀 0). ② 단일 `document` 위임 contextmenu 핸들러 + `_CTX_MENU_TARGETS` 설정표(`.conv-item`→`.conv-item-menu-trigger` / `.conv-folder-header`→`.conv-folder-menu-trigger` / `.message`→`.message-menu-trigger`) — 호스트 매칭 시 기존 트리거 **synthetic click** 재발화(권한 게이트·항목·토글 100% 재사용, 중복 0). "등과 같이"=표 한 줄 추가로 확장점. **기본 우클릭 양보**: input/textarea/select·`a[href]`·미디어(img/svg/canvas/video — mermaid 다이어그램 보존)·contentEditable·`_hasSelectionWithin`(`Range.intersectsNode` — 답변/SQL 텍스트 선택 복사 보존)·키보드 contextmenu(0,0)는 trigger 폴백. **비변경**: 기존 '···'/'☰' 버튼 클릭 동작·위치·admin.js·그래프 우클릭(graph-ctxmenu.js 소유)·백엔드. **검증**: `node --check` PASS(2회) · §18.8 적대 리뷰(general-purpose, REV-20260723T071355-universal-ctxmenu) **SHIP**(BLOCKING/MAJOR 0, MINOR 3 in-cycle 반영). **범위 밖(follow-up)**: 관리 콘솔(admin.js) 다수 메뉴 우클릭. **완결(2026-07-23)**: verify PASS → PR #897 머지(main **c6f7f98a**) → `deploy-web.sh --web-only` 무중단 롤링(soak PASS·자산 스탬프 `e6d39fde416f`) → **POST-DEPLOY PB-0008 라이브 PASS**(win-browser Chrome 150, 배포본 c6f7f98a: AC-1 대화항목→'···' 커서개방·AC-2 폴더헤더→폴더메뉴·AC-3 말풍선→'☰'·AC-4 텍스트선택 후 native 보존·AC-5 버튼 클릭 byte-동치·pageerror 0). deploy_scope: included(FIRST_REQUEST.md 전역·§12.2 사전 승인). worktree `ai/claude/feature-0003-universal-ctxmenu`(base main e52e88fc). REV/TEST-20260723T071355-universal-ctxmenu.

---

**2026-07-16 TASK-20260716T051931-ds-test-gate-fix — 작업화면 데이터소스 '연결 테스트' 버튼 렌더 회귀 수정** (Minor §12.3 — feature-0003 web/UI app.js 1줄; 백엔드/스키마/RBAC/엔드포인트 0). `/_template:entry` 회귀 신고 대응. **신고**: 07-13 출하·PB-0008 PASS 한 작업화면 데이터소스 '연결 테스트' 버튼이 이후 다른 세션 작업으로 회귀(미표시). **근본원인**: perm-atomic-split(`8e01cc24`, 07-15 Critical)이 DS 테스트 버튼 프론트 게이트를 `!viewOnly && canOpenAdminConsole() && Boolean(state.user?.permissions?.["datasource.test"])` 로 변경 — 그러나 이 코드베이스는 TASK-0098 로 프론트 `state.user.permissions` 의존성을 제거("표시 허용 + backend 403 fallback" — `can()` 컨벤션)했고 `/api/session`(system.py)은 `user.permissions` 를 직렬화하지 않는다(라이브 b8658bee 세션 실측 `hasPermissions:false`) → 게이트 항상 false → **버튼 전부 미렌더**. **수정(app.js 1줄)**: `Boolean(state.user?.permissions?.["datasource.test"])` → `can("datasource.test")`(display-permissive, 컨벤션 정합). 순 게이트 = `!viewOnly && canOpenAdminConsole()`(07-13 출하 동작 복구). datasource.test 미보유자는 백엔드 403(`admin_test_datasource` console.access+datasource.test 요구, 불변) → apiFetch 공통 토스트. **보안 무영향**(백엔드 enforcement 불변, 표시 계층만 복구). **비변경**: 상단 토스트·throttle·admin.js·백엔드 전부 온전(diff 로 회귀 범위 = 1559 한 줄 국한 확인). **검증**: `node --check` PASS · 회귀 하네스 short-circuit 무영향 · §18.8 1줄 컨벤션 복구·display-only·보안 posture 불변으로 full 패널 skip. **잔여**: verify-completion → 머지·push → web 재배포(deploy_scope: included) → POST-DEPLOY PB-0008 라이브 복구 확인. **관련 flag**: 동일 커밋 app.js ≈L2006 권한 표시 UI 도 부재 `state.user.permissions` 의존 — 별도 feature 소유(본 scope 밖). worktree `ai/claude-corp/feature-0003-ds-test-gate-fix`(base main b8658bee). REV-20260716T051931-ds-test-gate-fix.

---

**2026-07-16 20260716T0128-graph-cluster-detail-group-hoverpan — 스키마 클러스터 상세: 컨텐츠 카테고리 헤딩 hover 시 카메라 팬(다른 객체와 동일)** (Minor §12.3 — feature-0003 web/UI 프론트 단독 1파일. collapse 후속. 그래프 도메인 정본 feature-0016). **사용자 요청**: 상세 패널의 다른 객체(테이블/함수 행)처럼 컨텐츠 카테고리 그룹 헤딩 hover 시 해당 위치로 카메라 부드럽게 이동. **구현(frontend-only 1파일)**: 헤딩에 `data-pan-key = sg.tables[0].key`(그룹 **첫 멤버 노드 key**) 부여 + 기존 `ul` hover 위임을 `_panTargetOf`(행 data-node-key **또는** 헤딩 data-pan-key)로 확장 → `_metaGraphHoverPan`(200ms intent·미렌더 graceful no-op, 행과 동일 메커니즘·노드로 팬). 첫 멤버는 항상 실 노드라 진입경로·fam 정합 무관하게 견고(초판 캔버스 GB-박스 타깃 → §18.8 리뷰 콤보경로 fam-divergence caveat 제거 위해 전환). **비변경**: 헤딩 클릭(접기/펼치기)·행 클릭·행 hover·collapse/전체출력·백엔드/RBAC/스키마 0(순수 additive). **검증**: `node --check` PASS · §18.8 [SUBAGENT] 적대 리뷰 6축 diff 도입 결함 0(#1 caveat → 첫 멤버 전환으로 소거) · **완결(2026-07-16)**: verify PASS → PR #838 머지(main d2c72fdc) → web 재배포(soak PASS) → **POST-DEPLOY PB-0008 라이브 PASS**(DK dk_data_release_main 66그룹 data-pan-key=첫 멤버; 헤딩 hover→카메라 팬 "NPC 콘텐츠"↔"게임 콘텐츠 조회" 서로 다른 영역·미니맵 이동·행 불변·pageerror 0). POST-DEPLOY CHG-20260716T015146-graph-cluster-detail-group-hoverpan-postverify. worktree `ai/claude/feature-0003-graph-cluster-detail-group-hoverpan`(base main 0433efbb). REV/CHG/TEST-20260716T012805-graph-cluster-detail-group-hoverpan.

---

**2026-07-16 20260716T0039-graph-cluster-detail-collapse — 스키마 클러스터 상세: 컨텐츠 카테고리별 접기/펼치기(collapsible)** (Minor §12.3 — feature-0003 web/UI 프론트 단독 3파일. cluster-detail-fulllist 후속. 그래프 도메인 정본 feature-0016). **사용자 요청**: 전체 출력(fulllist) 후속으로 상세 패널에서 컨텐츠 카테고리별 접기/펼치기 구성(대형 스키마 긴 목록 탐색성). **구현(frontend-only 3파일)**: (1) `graph-state.js` `_metaGraph.panelGroupCollapsed`(Set<sg.key>) 신설 — 접힘 상태 유지(같은 클러스터 재렌더 간). (2) `graph-ctxmenu.js` 그룹 헤딩=disclosure(`role=button`·`aria-expanded`·캐럿 ▾/▸·`data-group-key`, 초기 `panelGroupCollapsed` 반영) + `rowHTML(t,collapsed)`(행 `amgr-ct-row-li`+`amgr-ct-collapsed`) + 섹션 헤더 '모두 접기/펼치기'(`#metaGraphCtCollapseAll`) + 이벤트 위임 확장(`_toggleCtGroup` = 헤딩~다음 헤딩 전 멤버 행 display 토글, click 헤딩 분기 우선·keydown Enter/Space). (3) `graph.css` 헤딩 cursor/hover/focus·캐럿·`amgr-ct-collapsed{display:none}`·collapse-all. **비변경**: 전체 출력(캡)·집계/membership/hiddenKinds·행 클릭·hover·백엔드/RBAC/스키마 0(순수 additive UI). **검증**: `node --check`(2파일) PASS · CSS 균형 221:221·66:66 · §18.8 [SUBAGENT] 적대 리뷰 7축 BLOCK/MAJOR 0(MINOR 2 수정) · **완결(2026-07-16)**: verify PASS → PR #835 머지(main 00454608) → web 재배포(soak PASS) → **POST-DEPLOY PB-0008 라이브 PASS**(DK dk_data_release_main 66그룹: 헤딩 클릭 접기/펼치기·모두 접기/펼치기[라벨 정합]·재렌더 접힘 유지[행 클릭→뒤로→여전 접힘]·키보드 Enter/Space·행 클릭 불변·pageerror 0). worktree `ai/claude/feature-0003-graph-cluster-detail-collapse`(base main e2cc1c80). REV/CHG/TEST-20260716T003901-graph-cluster-detail-collapse · POST-DEPLOY CHG-20260716T005817-graph-cluster-detail-collapse-postverify.

---

**2026-07-15 20260715T2316-graph-edge-drag-perf — 그래프 드래그 관계선 재그림 per-frame 부하 최적화** (Minor §12.3 — feature-0003 web/UI 프론트 단독, PixiJS 렌더러 hot-path. graph-edge-follow-drag 후속. 그래프 도메인 정본 feature-0016. `/_template:entry` arg-given dispatch). **사용자 실측**: 관계선 추종은 정상이나 드래그 프레임당 재그림 부하 심함 → 후속 최적화. **병목(적대 리뷰 F1 확증)**: `_refreshIncidentEdges` 가 프레임마다 `_built.edges` 전량 O(E) 스캔 + incident 엣지 `destroy`→`new Graphics()` 재생성(GPU 지오메트리 재할당+GC churn), 허브/대형 스키마 드래그 시 프레임당 수백~수천 Graphics 폐기·재생성 + `_moveElement`↔`translateElementTo` 이중 호출. **수정(3 lever, frontend-only 1파일 + 테스트)**: ① **인접 인덱스** `_edgeIndex`(node→incident edge[], `draw()` 구성·`setData` 무효화) + `_incidentEdges` dedup 반환 = O(incident)(폴백 O(E)); ② **in-place Graphics 재사용** `_paintEdge`(clear+라벨자식 destroy 후 재-path, `_drawEdge`=`_paintEdge(new Graphics())` 위임 — 신규·full draw byte-동일), 재사용 가드 `old.parent===world && typeof old.clear==='function'`; ③ **rAF 코얼레싱** `_scheduleEdgeRefresh`(이동 id 누적→프레임당 1회 refresh+render, 이중 호출 병합, 비-rAF 동기 폴백, dragend `_flushEdgeRefresh` 즉시, destroy cancel). 노드 좌표·hit-grid 는 동기 유지. **정확성 불변**: cross-category 추종(OR 판정)·full draw diff·_objSig·zIndex 페인트 순서. **비변경**: 팬/줌·상태·미니맵·hover·우클릭·백엔드/RBAC/스키마 0. **검증**: `node --check` PASS · 헤드리스 96/0 · §18.8 적대 리뷰(결함 없음+지적 4건 반영). **완결(2026-07-16)**: verify PASS → PR #832 머지(main bfb1aa98) → `deploy-web.sh` 무중단 롤링(soak PASS) → **POST-DEPLOY PB-0008 라이브 PASS**(win-browser PixiJS: root 제품 카테고리 + gunzgame 409객체 dense-edge 드래그 추종 정확·옛 위치 잔상 0 / 40 pointermove=30.4ms·동기 burst 중 rAF 0=단일 프레임 코얼레싱 / pageerror 0). worktree `ai/claude/feature-0003-graph-edge-drag-perf`(base main 41cf76c5). REV/CHG/TEST-20260715T231656-graph-edge-drag-perf.

---

**2026-07-15 20260715T2237-graph-cluster-detail-fulllist — 스키마 클러스터 상세: 컨텐츠 카테고리 목록 전체 출력(캡 사실상 해제 + 행 상호작용 이벤트 위임)** (Minor §12.3 — feature-0003 web/UI 프론트 단독 1파일. cluster-detail-cap 후속. 그래프 도메인 정본 feature-0016). **사용자 보고(스크린샷)**: 컨텐츠 카테고리 일부만 집계 — `(3/5)`·다수 `(0/N)`. 원인·전체 출력 가능 여부 문의. **진단**: 직전 cluster-detail-cap 의 전역 상한 ROW_CAP=500 + 그룹당 25 — 멤버 총합 500 초과 스키마에서 500행 소진 후 그룹 헤딩+0행/경계 부분 표시. **수정(frontend-only 1파일)**: (1) **캡 사실상 해제** — 그룹당 캡 제거, 전역 안전가드 ROW_CAP 500→5000 → 5000 미만 스키마 전체 멤버 렌더(헤딩 항상 방출·`(shown/n)` 유지), flat 폴백 500→5000. (2) **행 상호작용 이벤트 위임** — 수천 행 대비 클릭/hover 를 per-row(`_metaBindHoverPan` 5리스너) → 컨테이너 `ul.amgr-cluster-tables` 위임(O(1), ul 재생성으로 누적 없음, mouseover/out·focusin/out+`_hoverKey`+`relatedTarget`로 hover 의미 보존). **비변경**: 집계/membership/hiddenKinds/sim-group/헤딩/XSS·백엔드/RBAC/스키마 0. **검증**: `node --check` PASS · §18.8 [SUBAGENT] 적대 리뷰 6축 결함 0 · **완결(2026-07-15)**: verify PASS → PR #830 머지(main 41cf76c5) → web 재배포(soak PASS) → **POST-DEPLOY PB-0008 라이브 PASS**(DK온라인 dk_data_release_main 423항목=123테이블+300함수·프로시저 상세: 컨텐츠 카테고리 66그룹 전량·423행·(0/N) 0·routine-only 43그룹·스크롤 12423px; 이벤트 위임 클릭 승격 조회; pageerror 0. ROW_CAP=5000 결정론적 전체 렌더로 사용자 >500 스키마 동일 커버). **후속 옵션**: 매우 큰 평면 목록 UX 는 컨텐츠 카테고리 접기/펼치기로 별도 개선 가능. worktree `ai/claude/feature-0003-graph-cluster-detail-fulllist`(base main fb6410b4). REV/CHG/TEST-20260715T223744-graph-cluster-detail-fulllist · POST-DEPLOY CHG-20260715T231304-graph-cluster-detail-fulllist-postverify.

---

**2026-07-15 20260715T2152-graph-cluster-detail-cap — 스키마 클러스터 상세: 목록 행 캡이 함수·프로시저 컨텐츠 카테고리를 통째 숨기던 문제 수정** (Minor §12.3 — feature-0003 web/UI 프론트 단독 1파일. cluster-detail-routines POST-DEPLOY PB-0008 후속. 그래프 도메인 정본 feature-0016). **트리거**: cluster-detail-routines 배포 후 라이브 검증에서 gunzgame 클러스터 상세(409항목=테이블 115+함수·프로시저 294)의 집계·개수는 정확("테이블·함수·프로시저 (409)", "함수·프로시저 294개")하나 **목록에 렌더된 컨텐츠 카테고리는 앞쪽 테이블 be: 클러스터 10개(80행)뿐**, 함수·프로시저 컨텐츠 카테고리 0개 노출을 적발. **근본원인**: `_metaGraphRenderClusterDetail` sim-group 렌더가 전역 80행 캡 도달 시 이후 그룹 통째 skip(`if (emitted >= 80) return`); sim-group 순서 be:(테이블) 우선 → 대형 스키마에서 앞 테이블 그룹이 80행 소진 → 뒤 routine 컨텐츠 카테고리(헤딩 포함) 전체 렌더 누락. **수정(frontend-only 1파일)**: (1) `if (emitted >= 80) return` 제거 → **모든 컨텐츠 카테고리 헤딩 항상 방출**, (2) 멤버 행 캡을 그룹당 PER_GROUP=25 + 전역 ROW_CAP=500 로 재구성(`min(sg.n,25,max(0,500-emitted))`), (3) flat 폴백 `slice(0,80)`→`500`. **회귀**: 소형 스키마 동일; 그룹 멤버 >25 인 그룹만 25+`(25/n)` 표식(gunzgame 32→25). **비변경**: 집계/membership/hiddenKinds/백엔드/RBAC/스키마 0. **검증**: `node --check` PASS · §18.8 [SKIPPED] 적대 자가검토(display-cap) · **완결(2026-07-15)**: verify PASS → PR #828 머지(main cdee785e) → web 재배포(soak PASS) → **POST-DEPLOY PB-0008 라이브 PASS**(gunzgame 상세: 컨텐츠 카테고리 그룹 72개·함수·프로시저-only 그룹 **51개** 노출[수정 전 0]·⚙ Game_AllItemGet 클릭→routine 노드 상세·캔버스 정합·pageerror 0). worktree `ai/claude/feature-0003-graph-cluster-detail-cap`(base main 1b370dfd). REV/CHG/TEST-20260715T215241-graph-cluster-detail-cap · POST-DEPLOY CHG-20260715T220941-graph-cluster-detail-postverify.

---

**2026-07-15 20260715T2119-graph-cluster-detail-routines — 스키마 클러스터 상세 패널: 함수·프로시저만 있는 컨텐츠 카테고리 누락 수정** (Minor §12.3 — feature-0003 web/UI 프론트 단독 1파일. 그래프 도메인 정본 feature-0016. `/_template:entry` arg-given dispatch). **사용자 보고**: "상세 패널의 컨텐츠 카테고리가 테이블만 대상으로 집계돼, 목록에 나타나지 않는 컨텐츠 카테고리가 있다. 함수·프로시저만 포함된 대상에서 이슈 — 해당 항목도 상세 패널에서 조회되게." **진단**: 캔버스 build(`graph-core.js` L64~L78)는 Table 과 Routine(함수·프로시저)을 **모두 `g.tables`** 에 넣어 `_metaSimGroups` 로 함께 sim-group(컨텐츠 카테고리)화하나, 스키마 클러스터 상세 패널의 두 진입점(`_metaGraphShowClusterDetailById`·`_metaGraphShowClusterDetailLocal`)과 렌더(`_metaGraphRenderClusterDetail`)는 `label === "Table"` 만 집계 → Routine-only 컨텐츠 카테고리(예: "상점 아이템 명칭")가 캔버스엔 보여도 목록 누락 + 캔버스와 불일치. membership `_metaSchemaComboOf(Routine)`==`_metaCatParent(n.key,n.fqn)` 는 Table 과 동일 predicate. **수정(frontend-only 1파일 `graph-ctxmenu.js`)**: 두 진입점이 `label === "Routine"` 도 동일 predicate 로 수집(ById 는 모델에서 — 패널=화면 내 스키마라 모델 보장) → 렌더에 `routines` 전달; `_metaGraphRenderClusterDetail` 이 `members=tables.concat(routines)` 로 `_metaSimGroups` 계산·렌더(Routine 행 = ƒ/⚙ 보라 칩·클릭 시 `_metaGraphShowDetail` API 조회). 설명/섹션 제목/그룹 aria-label 병합집합 반영, 테이블 개수·cap 절단은 테이블 기준 유지. **캔버스 정합**: 패널 컨텐츠 카테고리 목록이 캔버스와 일치, Table-only 스키마 회귀 0. **비변경**: 제품 카테고리 패널·캔버스 build·우클릭·드래그·상태·백엔드/RBAC/스키마/엔드포인트 0. **검증**: `node --check` PASS · §18.8 적대 리뷰([SUBAGENT] hiddenKinds parity MAJOR → 수정) · **완결(2026-07-15)**: verify PASS → PR #827 머지(main 1b370dfd) → web 재배포 → **POST-DEPLOY PB-0008 집계 PASS**("테이블·함수·프로시저 (409)"·"함수·프로시저 294개" — routine 집계 입증; 시각 조회는 80행 캡으로 후속 cluster-detail-cap 에서 완결). worktree `ai/claude/feature-0003-graph-cluster-detail-routines`(base main 114e4214). REV/CHG/TEST-20260715T211911-graph-cluster-detail-routines · POST-DEPLOY CHG-20260715T220941-graph-cluster-detail-postverify.

---

**2026-07-15 20260715T1819-graph-edge-follow-drag — 그래프 뷰 노드/제품 카테고리 드래그 시 관계선 미추종 수정** (Minor §12.3 — feature-0003 web/UI 프론트 단독, PixiJS 렌더러. 그래프 도메인 정본 feature-0016. `/_template:entry` arg-given dispatch). **사용자 보고**: "좌클릭 드래그로 제품 카테고리를 옮길 때 관계선이 옮기기 전 위치에 그대로 출력됨(줌 아웃으로만 갱신)". **사용자 정정**: "내부 엣지는 상대위치 정합해 무해하나 **다른 제품 카테고리로 가는 cross-category 엣지**의 연결선 구조 갱신이 필요". **진단**: PixiJS 렌더러에서 엣지는 절대 model 좌표(a,b)를 Graphics path 에 bake 한 **world 직속 독립 오브젝트**(`_drawEdge`) — 노드 Container 이동으로 미추종. 드래그 경로 `_moveElement`/`translateElementTo` 는 노드 style/position 만 옮기고 `_render()`(단순 repaint)만 호출 → incident 엣지 옛 좌표 유지. full `draw()`(줌 밴드 LOD rebuild)만 `edgeSig(e,a,b)` 끝점 변경을 감지해 recreate → "줌 아웃해야 갱신" 회귀. **카테고리 드래그 경로 확인**: `graph-core._metaNodeDragStart`(CAT/CATH)가 전 구성원 노드를 `translateElementTo` 로 이동 → 이 chokepoint 커버. **수정(frontend-only 1파일 + 테스트)**: `graph-renderer-pixi.js` 신규 `_refreshIncidentEdges(movedIds)` — source **또는** target 이 이동집합에 포함된 엣지만 증분 재그림(destroy→`_drawEdge`→addChild·`_objs`/`_objSig` 갱신, full draw() 보다 저렴) · `_moveElement`(노드/combo 분기)·`translateElementTo` 에서 `_render()` 직전 호출 · `test_pixi_adapter.js` T23 7종 신규. **cross-category 보장(사용자 정정)**: OR 판정 — 한끝만 이동해도 재그림, 이동 끝점 새 좌표 + 미이동 끝점 현재 좌표로 구조 갱신. **비변경**: 팬/줌·상태·미니맵·hover-fx·우클릭 메뉴·클릭·백엔드/RBAC/스키마 0. full `draw()` diff 경로 불변. **한계(정직·deferred)**: 허브 노드(수천 incident 엣지) per-frame 재그림 비용 — full draw() 보다 저렴·정확성 필수 최소치, rAF 스로틀은 후속(§76). **검증**: `node --check` PASS · 헤드리스 T23 7종 ALL PASS 73/0 · §18.8 적대 리뷰 correctness 결함 없음. **완결(2026-07-15)**: verify-completion PASS → PR #824 머지(main 0f26cec1) → `deploy-web.sh` 무중단 롤링(soak PASS·워커 롤아웃, deploy_scope: included) → **POST-DEPLOY PB-0008 라이브 PASS**(win-browser 실 Windows Chrome, PixiJS 루트 뷰에서 제품 카테고리 "건즈-개발·1" 드래그 → cross-category 관계선이 줌 없이 새 위치 실시간 추종·옛 위치 잔상 0·pageerror 0). worktree `ai/claude/feature-0003-graph-edge-follow-drag`(base main b3c8cd34). REV/CHG/TEST-20260715T181939-graph-edge-follow-drag · POST-DEPLOY CHG-20260715T190000-graph-edge-follow-drag-postverify.

---

**2026-07-15 TASK-20260715T135725-graph-ctxmenu-content-category — 그래프 우클릭 3대상 정합: 컨텐츠 카테고리(sim-group) 전용 메뉴 신설 + band-wins 철회** (Major §12.3 — feature-0003 프론트 단독, 핵심 상호작용 경로. graph-ctxmenu-band-priority 정정. `/_template:resume` 재개). **사용자 정정(band-wins 배포 후)**: "'제품 카테고리 밴드'를 '각 내부 노드를 컨텐츠 단위로 묶은 클러스터(=컨텐츠 카테고리)'로 착각하여 잘못 요청했다. 기존 우클릭 대상 구조·작동을 정합하게 — 제품 카테고리 밴드:카테고리 / 스키마 클러스터:스키마 / (추가) 컨텐츠 카테고리:컨텐츠 카테고리." **진단**: 그래프 3층 클러스터 — ①제품 카테고리 밴드(cat-bg) ②스키마 클러스터(combo) ③컨텐츠 카테고리(sim-group GB/GH/GX, graph-simgroups 가 내부적으로 "content-cluster"·"컨텐츠 신호"로 명명, 스키마 내부 유사 테이블 그룹). 사용자가 ①↔③ 혼동 → band-priority 전제 무효. **사용자 결정(AskUserQuestion)**: 컨텐츠 카테고리=sim-group 확인 + band-wins 철회. **수정(5파일 frontend-only)**: `graph-renderer-pixi.js` band-wins 철회(`_pickContext` 제거, 우클릭=`_pick` WYSIWYG, `_pick` 3-tier 불변) · `graph-ctxmenu.js` 신규 `_metaGraphCtxForContentCategory`(배지 '컨텐츠 카테고리'+label·테이블수 / 소속 스키마 상세 / 접기·펼치기 묶음 / 묶음명 복사)+export · `graph-core.js` GB/GH/GX→`_metaGraphCtxForContentCategory` 재라우팅 + `_metaGraph.groupInfo`(groupKey→{label,n,schema}) 신설·emission 적재 · `graph-state.js` groupInfo 초기화 · `test_pixi_adapter.js` T22 교체. **비변경**: 좌클릭(GB/GH 상세·GX 접기)·드래그(sim-group 리지드 이동)·제품 카테고리 밴드/스키마 클러스터 메뉴·백엔드/RBAC/스키마 0. **검증**: `node --check`(4파일) PASS · 헤드리스 T22 교체(컨텐츠 카테고리 라우팅·band-wins 철회·`_pickContext` 부재) ALL PASS 66/0 · §18.8 적대 패널. **잔여**: verify-completion → PR·머지 → web 재배포(deploy_scope: included) → POST-DEPLOY PB-0008(sim-group 우클릭→컨텐츠 카테고리 / 스키마 클러스터→스키마 복원 / 밴드 여백→카테고리). worktree `ai/claude/feature-0003-graph-ctxmenu-content-category`(base main a1206960). REV/CHG-20260715T135725-graph-ctxmenu-content-category.

---

**2026-07-15 20260715T1132-enum-bundle-flex-fix — ENUM 검토 큐 묶음 카드 flex 압축 붕괴 수정** (Minor §12.3 — feature-0003 web/UI CSS 전용. enum-review-bundle POST-DEPLOY PB-0008 적발 후속). **트리거**: enum-review-bundle 배포 후 라이브 시각검증에서 묶음 카드가 12px sliver 로 붕괴(내용 회색 바)됨을 적발. **근본원인(라이브 확정)**: `#metadataList` 는 `overflow-y:auto`+`flex-direction:column`(height 373px) 스크롤 컨테이너 — `.admin-meta-bundle` 기본 `flex-shrink:1` 이라 8카드가 flex 압축되고 카드 `overflow:hidden` 이 내용(164px)을 클리핑 → sliver. flat-list `.admin-meta-row`(overflow visible)는 미발현이던 잠복 결함. **수정(CSS 1선언)**: `styles.css` `.admin-meta-bundle` `flex-shrink: 0` — 자연 높이 유지, 목록은 컨테이너 스크롤(라이브 주입 12px→166px 실증). **비변경**: JS/HTML/백엔드/RBAC/엔드포인트/스키마 0. **잔여**: verify → 머지 → 재배포 → POST-DEPLOY PB-0008 재검증(카드 정상 높이). worktree `ai/claude/feature-0003-enum-bundle-flex-fix`(base main f6cb0b14). REV/CHG-20260715T113208-enum-bundle-flex-fix.

---

---

**2026-07-15 TASK-20260715T114608-graph-ctxmenu-band-priority — 제품 카테고리 밴드 우클릭 band-wins** (Major §12.3 — feature-0003 프론트 단독, 핵심 상호작용 경로). graph-ctxmenu-hittest 후속. **사용자 보고**: "제품 카테고리 밴드 우클릭이 여전히 스키마 클러스터로 작동". **진단(라이브 PB-0008 정밀)**: hittest fix 는 정확(hit 경계=가시 박스 일치)하나 밴드 안 스키마 클러스터 박스가 밴드를 시각적으로 채워 "밴드 우클릭"=박스→스키마. hit-test 결함 아닌 겹침 우선순위 설계 → **사용자 결정 "밴드 우선"**. **수정(1파일, 우클릭 경로 한정)**: `graph-renderer-pixi.js` 신규 `_pickContext`(combo/schema-card 가 cat-bg 피복 시 카테고리 밴드로 승격) + `up` button===2 만 적용. **좌클릭/드래그 불변**(클러스터 펼치기·이동 보존). 테이블·컬럼·헤더(CATH/CATX/GX/GH/GB)·밴드밖 클러스터 불변. 트레이드오프(사용자 수용): 밴드 내 클러스터 우클릭 스키마 메뉴는 좌클릭 드릴로 대체. **검증**: `node --check` PASS · T22 회귀 6종(ALL PASS 68/0) · §18.8 적대 패널. **잔여**: verify → PR·머지 → web 재배포(deploy_scope: included) → POST-DEPLOY PB-0008(밴드 클러스터 박스→카테고리 / 테이블→노드 / 밴드밖→스키마 / 좌클릭 펼치기 정상). worktree `ai/claude/feature-0003-graph-ctxmenu-band-priority`(base main f6cb0b14). REV-20260715T114608-graph-ctxmenu-band-priority.

**2026-07-15 20260715T1053-enum-review-bundle — ENUM 코드사전 검토 큐: 구조 묶음 단위 승인 체크리스트 + 일괄 등록** (Major §12.3 — feature-0003 web/UI 프론트 + admin_metadata/kb_glossary 백엔드, additive·비파괴. `/_template:entry` arg-given dispatch). **사용자 요청**: `관리 콘솔 > 지식베이스 > 메타데이터 > ENUM 코드사전` 검토 큐에서 ENUM값을 **구조 묶음 단위**로 구성 + 각 검토 **승인 여부 체크리스트**(전체 승인/일부만 승인 해제) 후 **등록**. **진단**: 현행 ENUM 검토 큐(`renderFeedbackQueue` kind=enum)는 개별 `table.column · code` 후보를 1건씩 승급/거부하는 flat list — 묶음/일괄/체크리스트 없음. `enum_feedback` UNIQUE `(scope,schema,table,column,code)` → **한 컬럼 = 한 구조 묶음**(코드↔라벨 후보 집합)이 자연 그룹. **구현**: (백엔드 core) `kb_glossary.py` `bulk_promote_enum_feedback` — 기존 `promote_enum_feedback` 단일 트랜잭션 loop; (백엔드 web) `admin_metadata.py` `POST /api/admin/metadata/enum-feedback/bulk-promote`(RBAC `kb.enum.curate`) — body `{feedback_ids:[int]}` 정규화(int·양수·dedup·≤200) → bulk 승급 → audit `enum.feedback.bulk_promote`; (프론트) `admin.js` enum 경로를 `_metaRenderEnumBundles`(묶음 그룹) + `_metaBuildEnumBundle`(전체 승인 마스터 체크[indeterminate] + 코드별 체크박스 + 힌트 + '등록(N)') + `_enumBundleRegister`(bulk-promote) 로 재구성; (CSS) `.admin-meta-bundle*`. **비파괴**: 미선택(해제)은 pending 유지(거부 아님). **비변경**: 개별 promote/reject·glossary/sample 큐·RBAC 정의·스키마/마이그레이션·인증 0. **검증(로컬)**: `node --check` admin.js PASS · agent 컨테이너 targeted pytest 28/0(core 2 + web 6 신규) · `gen-routemap --check` up-to-date(203 routes, 신규 route 반영). **잔여**: verify-completion → commit → PR·머지 → web 재배포(deploy_scope: included) → **POST-DEPLOY PB-0008 라이브 시각검증**(묶음 카드·전체 승인/일부 해제 토글·등록 후 코드사전 반영, visual_verification_scope: always). worktree `ai/claude/feature-0003-enum-review-bundle`(base main 7f169007). REV/CHG-20260715T105337-enum-review-bundle.

---

**2026-07-15 20260715T1034-perm-atomic-split — 권한 최소 단위 원자화(추가/수정/삭제 분리) + 레거시 묶음 grid 숨김** (Critical §12.3 인증/인가 — perm-category-hier 후속, 사용자 승인: 전체 분리+묶음 숨김 / 검수 단일 유지·원본 사전 read 하위 종속). **사용자 재보고**: "여전히 권한이 [등록/수정/삭제] 혹은 [등록/거부/(삭제 권한이 없음)] 형태로 통합". **구현**: (backend) 원자 23종(사전 4종×read/create/update/delete + product 3 + datasource 4[test 포함]) + `_PERMISSION_BUNDLE_IMPLIES` transitive 함의(개별 DENY 우선·R9 pin) + `LEGACY_BUNDLE_PERMISSIONS` 7종 + admin catchup 23 + `_backfill_atomic_perm_split_v1`(1회 멱등, category-access-v1 선행) + 엔드포인트 액션별 전환(admin_metadata 22·admin_products·admin_datasources `_ds_write_common(action_perm)`·연결테스트=datasource.test·suggest=update 분리맵·bootstrap=create∧update); (frontend) DEPS 원자 트리(검수→원본 read 하위)·legacy grid 필터(BE/FE 3자 parity R10)·서브탭 C/U/D 맵+버튼 게이팅·metadata 탭 게이트 read+curate·app.js legacy 숨김+ds-conn-test test 게이트+라벨 23. **저장 wipe 없음**(preservedHidden TASK-0300 확인). **검증**: 785/0 + jsdom 47/0 + ROUTEMAP 재생성(--check 0) + 컨테이너 make test 신규 회귀 0(기지 환경기인 4건만). **완결(2026-07-15)**: PR #810 머지(8098aee1) → deploy-web(soak 통과) → **배포 후 실증 PASS**(`atomic-perm-split-v1` 마커·admin 원자 23종·묶음 보유 role=admin 뿐[usermanager 비대상 정상·접근 상실 0]·PB-0008 라이브 — 레거시 묶음 grid 0건·원자 트리 read→CRUD/검수·토글 접힘/펼침·상태 무오염). worktree `ai/root/feature-0003-perm-atomic-split`(base main 3c8e78df). REV/ADR-20260715T103406 · REV-20260715T113000-postverify.

---

**2026-07-15 20260715T1029-graph-help-text-responsive — 그래프 도움말 팝업 텍스트 줄바꿈 + 반응형 크기** (Minor §12.3 — feature-0003 web/UI 프론트 단독, CSS 전용. 그래프 도메인 정본 feature-0016). **사용자 피드백 2건**(graph-entry-help 배포본): ① "설명 텍스트 문단이 중간에 잘린 상태로 줄바꿈"(어절 중간 orphan 음절) ② "팝업이 고정 크기가 아닌 브라우저 자체 크기에 반응하여 변형". **진단**: `.amg-help-card` 가 `word-break: normal`(CJK 기본 = 글자 사이 아무 데서나 끊김 → "탐색하세"/"요." orphan) + `width: min(460px, 100%)`(460px 고정 상한 → 큰 화면에서 고정감). **수정(1파일 CSS)**: `graph/graph.css` `.amg-help-card` — `word-break: keep-all; overflow-wrap: anywhere;`(어절 단위 줄바꿈, word-break 상속으로 카드 내 전체 텍스트) + `width: min(clamp(320px, 90%, 520px), 100%)`(캔버스=브라우저 폭에 320~520px 유동, 좁은 화면 100% 바운드). 세로 max-height:100%+overflow-y:auto 유지. **검증**: graph.css `/*`:`*/` 63:63·중괄호 215:215 균형(주석 hazard 없음) · 라이브 win-browser eval — keep-all 어절 줄바꿈 스크린샷(orphan 소거·넓어진 카드로 다수 설명 1줄) + 반응형 다중 폭 실측(300→268·360→320·617→520·1100→520, 오버플로 0). **잔여**: verify-completion → commit → PR·머지 → web 재배포(deploy_scope: included) → POST-DEPLOY PB-0008 재검증. worktree `ai/claude/feature-0003-graph-help-wordbreak`(base main 14f54e64). REV/CHG-20260715T102912-graph-help-text-responsive.

---

**2026-07-15 TASK-20260715T102901-graph-ctxmenu-hittest — 그래프 뷰 우클릭 메뉴 오라우팅(스키마↔제품카테고리 뒤바뀜) hit-test 층서 수정** (Major §12.3 — feature-0003 프론트 단독, 핵심 상호작용 경로). `/_template:resume` 후속(graph-ctxmenu-category 배포 후 사용자 잔존 보고). **사용자 보고**: 스키마 클러스터 우클릭→카테고리 메뉴 / 제품 카테고리 밴드 우클릭→스키마 메뉴 (뒤바뀜); 카테고리 헤더는 정상. **진단**: dispatch 라우팅은 정확하나 `e.target.id` 를 정하는 hit-test 가 오targeting. 근본 — `PixiGraphAdapter._pick()` 이 `hitTest(built.nodes)` 로 어떤 node 든 먼저 반환하고 그때만 `hitTestCombo`(스키마 클러스터 배경) 폴백. CAT 밴드 배경이 **node**(`data.kind:"cat-bg"`, z=`_METZ.CAT_BG`=-1, size=멤버 클러스터 전체 bbox+패딩)로 built.nodes 에 있어 멤버 클러스터를 덮음 → 스키마 클러스터 빈 배경(combo, z=0, 폴백 대상) 우클릭을 CAT node 가 가로채 카테고리 메뉴로 감; 반대로 밴드 위 카드(z=4)가 CAT 를 눌러 스키마 메뉴로 샘. 과거 GROUP_BG `-2→1` 승격과 동일 부류의 미수정 잔재. **수정(1 파일, hit-test 층서만)**: `graph-renderer-pixi.js` — `hitTest(…,filter)` 인자 추가 + `_pick` 3-tier(실요소 cat-bg제외 > combo > cat-bg) + `_isCatBg`. 시각 z(-1) 불변. **비변경**: dispatch·메뉴함수·노드방출·좌클릭·드래그·백엔드/RBAC/스키마 0. **검증**: `node --check` PASS · `tests/headless/test_pixi_adapter.js` T21 회귀 6종 추가(witness+3tier, ALL PASS 62/0) · §18.8 적대 패널. **잔여**: verify-completion → commit → PR·머지 → web 재배포(deploy_scope: included) → POST-DEPLOY PB-0008 라이브(스키마 클러스터→클러스터 메뉴 / 밴드 여백·헤더→카테고리 메뉴 / 카드→노드). worktree `ai/claude/feature-0003-graph-ctxmenu-hittest`(base main 14f54e64). REV-20260715T102901-graph-ctxmenu-hittest.

---

**2026-07-14 20260714T1819-perm-category-hier — 관리 콘솔 권한 체계를 nav 카테고리 '접근' 계층으로 재구성** (Critical §12.3 인증/인가 — 신규 접근 권한 5종 + 탭 게이트 전환 + 1회 backfill; 사용자 승인 A안, `/_template:entry` arg-given dispatch). **사용자 요청**: "계정 및 역할의 권한 체계가 구조적으로 난잡 — ① 최상위=카테고리별 '접근'(=조회) ② 같은 카테고리 권한은 접근 하위 종속(추가/수정/삭제·탭 조회 재귀·승인/작동) ③ 상위 활성화 시 하위 UI 펼침". **진단**: 카테고리 접근 게이트 부재(console.access 아래 평면)·감사 4탭 조회 권한 3개 그룹 산재(audit/conversation_any/console)·system.runtime.* 종속 미선언+settings 탭 게이트 누락·insight.reset 그룹 오배치(실표면=제품 상세)·conversation.create 루트. **구현**: (backend `web_context.py`) 신규 `console.{account,product,audit,kb,system}.access` 5종 + GroupName 재배치(usage/aiops/archive→audit, insight.reset→product — code·enforcement 불변) + admin catchup 5종·dba audit.access + `_CONSOLE_CATEGORY_ACCESS_LEAVES` + `_backfill_console_category_access_v1`(1회 멱등 `console-category-access-v1`: ①console.access+세부 보유 role ②세부 ALLOW override 계정 ③console.access override×역할 세부 조합 — 접근 무손실); (frontend `admin.js`) `PERMISSION_DEPENDENCIES` 카테고리 계층 재구성(+system.runtime.*·create 종속) + `ADMIN_TAB_CATEGORY_ACCESS`(canSeeTab=카테고리 접근 AND && 탭 권한 OR) + settings 게이트 runtime 보강 + 그룹 순서/라벨(kb="지식베이스"); (`app.js`) 그룹 라벨(quota/datasource/kb)/`PERMISSION_GROUP_OVERRIDES`/접근 5종 라벨. **엔드포인트 require_permission 불변**(접근 권한=nav 노출 게이트+부여 계층, 역함의 없음 — SECURITY §22 신설·CONVENTIONS §10.6 정합). **검증(로컬)**: 권한 타깃 50 PASS · feature-0003 스위트 785/0 · jsdom 탭 게이팅 47/0(release-notes 상시 노출로 stale 하던 시스템 라벨 기대 2건 정정 포함). **완결(2026-07-14)**: §18.8 inline 적대+라이브 MySQL dry-run(REV) → make test(잔여 실패=환경 기인 확정) → verify-completion PASS → PR #801 머지(7e375ebc) → deploy-web(scope=all, soak 통과) → **배포 후 실증 PASS**(seed catchup 정상·`console-category-access-v1` 마커·접근 5종 admin/usermanager(backfill 구제)/dba 부여·PB-0008 라이브 — grid 접근 5종 depth0·감사 4탭 조회 depth1·상위 토글→하위 접힘/펼침·admin 13탭). worktree `ai/root/feature-0003-perm-category-hier`(base main f44623f3). REV-20260714T181936-perm-category-hier · ADR-20260714T181936-perm-category-hier.

---

**2026-07-14 20260714T184717-graph-help-overlay-fix — 그래프 도움말 팝업 mis-position 근본원인 수정** (Minor §12.3 — feature-0003 web/UI 프론트 단독, CSS 주석 텍스트 국한. `/_template:resume` 재개, 그래프 도메인 정본 feature-0016). **사용자 요청**(graph-entry-help 배포 직후): "도움말 팝업을 그래프 뷰 중앙에 위치시키고 좌측 하단 줌 컨트롤과 겹치는 문제 해결." (원본 세션이 진단 중 세션한도 도달로 중단 → resume 로 이어받음.) **증상**: 배포본(1f705a9e) 그래프 뷰에서 `#metadataGraphHelp` 오버레이가 중앙 모달이 아니라 캔버스 아래로 밀려 좌하단 줌 컨트롤과 겹침(초기엔 "짧은 뷰포트 minor UX" 로 오진). **근본원인(라이브 CDP 확정)**: `.amg-help-overlay` 스타일 주석의 토큰 목록 `--surface/--border/--text*/--primary` 에서 `--text*` 뒤 `/` 와 결합해 **`*/` 서브스트링**이 생겨 CSS 주석이 조기 종료 → 이후 텍스트가 깨진 CSS 로 유입 → 바로 아래 `.amg-help-overlay { position:absolute … }` 규칙이 파서에서 통째 드롭 → position `static` 폴백 → flex column 흐름상 캔버스 아래 렌더·줌 겹침. (`getComputedStyle` 전 속성 기본값 + `sheet.cssRules` 에 bare 규칙 부재 + 격리 파싱은 정상 → 직전 주석 문맥 문제로 특정. `/*`:`*/` 개수 61:62→61:61.) **수정(1파일, 주석 텍스트 국한)**: `graph/graph.css` 주석 토큰 구분자 `/`→`·`(`--surface·--border·--text*·--primary`)로 `*/` 제거 + 재발 방지 NOTE. CSS 선언/선택자/미디어쿼리 무변경(git diff +4/-2). **검증**: (a) 수정본 파싱 시 `.amg-help-overlay` 규칙 복구·`position:absolute`(rule 204→205); (b) 라이브 규칙 주입 geometry — 카드 canvas-wrap 정중앙(dx:0 dy:0)·줌 컨트롤 미겹침(card_overlaps_zoom:false, 카드 하단 694<줌 상단 704); (c) §18.8 SUBAGENT 적대검증 PASS(주석 델리미터 61/61·잔여 hazard 없음·diff 주석 국한). **잔여**: verify-completion → commit → PR·머지 → web 재배포(deploy_scope: included) → **POST-DEPLOY PB-0008 재검증**(재배포 자산 `.amg-help-overlay` position=absolute·팝업 중앙·줌 미겹침). worktree `ai/claude/feature-0003-graph-entry-help-postdeploy`(base main 1f705a9e). REV/CHG-20260714T184717-graph-help-overlay-fix.

---

**2026-07-14 TASK-20260714T180125-graph-ctxmenu-category — 그래프 뷰 '제품 카테고리 밴드' 우클릭을 전용 메뉴로 정합** (Minor §12.3 — feature-0003 프론트 단독, additive). `/_template:entry` arg-given dispatch. **사용자 요청**: 그래프 뷰 우클릭 정합 — ① '제품 카테고리 밴드' 우클릭에서 '스키마 클러스터' 우클릭 동작이 나타나는 문제 수정, ② 밴드 우클릭 동작 구성. **진단**: 카테고리 밴드(CAT:/CATH:/CATX: 합성 노드, graph-category §55 A) 우클릭은 `node:contextmenu` 로 도달하나 현행 main `graph-core.js` L2085 가 `_metaGraphCtxHide()` **stopgap** 으로 메뉴만 숨김(주석 "무반응 방지 후속 여지"=전용 메뉴 미구성). 사용자가 본 "클러스터 메뉴 노출"은 그 stopgap(커밋 2e168614, 그래프 JS 분리) **이전 배포본** 잔존 동작 — 당시 CAT 특례 부재로 Pixi hit-test 가 밑 combo 로 fall-through(`combo:contextmenu`→`_metaGraphCtxForCombo`). 두 증상 동일 수정으로 해소. **수정(2 파일, additive)**: (ctxmenu) 신규 `_metaGraphCtxForCategory(catKey,x,y)` — 헤더 배지 '카테고리' + 카테고리 상세(`_metaGraphShowCategoryDetail`) + 밴드 접기/펼치기(`catCollapsed` 토글+`_metaG6Apply`) + 카테고리명 복사, export; (core) L2085 CAT 분기 `_metaGraphCtxHide()` → `_metaGraphCtxForCategory(String(id).replace(/^CAT(H|X)?:/,""), p.x, p.y)`, import. **비변경**: 좌클릭(CATX 토글·CAT/CATH 상세)·드래그·combo/node/edge/canvas 메뉴·백엔드/RBAC/스키마 0. **검증**: `node --check`(module) 양 파일 PASS · dispatch/의존심볼 grep 정합 · §18.8 적대적 자가검토 4가설 refute(REV [SKIPPED:frontend-ui-minor-additive-no-backend-no-rbac]). **잔여**: verify-completion → commit → PR·머지 → web 재배포(deploy_scope: included) → **POST-DEPLOY PB-0008**(밴드 우클릭=카테고리 메뉴 / 클러스터 메뉴 미노출, visual_verification_scope: always). worktree `ai/claude/feature-0003-graph-ctxmenu-category`(base main f44623f3). REV-20260714T180125-graph-ctxmenu-category.

---

**2026-07-14 20260714T1803-graph-entry-help — 그래프 뷰 첫 입장 조작 도움말 팝업 + 중간버튼 커서 표식** (Minor §12.3 — feature-0003 web/UI 프론트 단독, 비파괴 additive, 백엔드/RBAC/스키마 무변경. `/_template:entry` arg-given. 그래프 도메인 정본 feature-0016). **사용자 요청**: 그래프 뷰 첫 입장 시 조작 도움말 팝업(닫기·재확인 가능) + 마우스 중간 버튼 클릭 시 커서 적절 변경. **구현(3파일 additive)**: ① 도움말 팝업 — `admin.html` 툴바 `❓ 도움말` 버튼(`#metadataGraphHelpBtn`) + 캔버스 wrap(role=img 밖 형제) 내 `#metadataGraphHelp` 오버레이(role=dialog·8개 조작 안내·읽기전용 고지); `graph/graph.css` `.amg-help-*`(캔버스 wrap 기준 절대배치·z-index 40·중앙 카드+반투명 backdrop, 토큰만 써 라이트/다크 자동); `graph/graph-core.js` `_metaGraphShowHelp/Hide/MaybeAutoHelp/BindHelp` — **첫 진입 1회 자동노출**(`localStorage("metaGraphHelpSeen")` 미확인 시, 기존 metaGraphHiddenKinds 관례) + 닫으면 seen set(다음 세션 무자동노출) + 닫기 4경로(✕·알겠습니다·배경·Esc capture)·a11y 포커스·재확인 ❓ 버튼·바인딩 멱등(`_helpBound`). ② 중간버튼 커서 — 기존 container 중간버튼 `mousedown` 핸들러(§REQ①, autoscroll preventDefault)에 `cursor="grabbing"` 표식 추가·mouseup(buttons&4 유지 가드)·blur 복원. 캔버스 명시 cursor 부재 → 자식 `<canvas>` 상속(렌더러 PixiJS/G6 무관). **검증**: `node --check`(graph-core.js) PASS · admin.html/graph.css 구조 균형 · 심볼 전수 존재. **PB-0008 라이브 = POST-DEPLOY 이연**(정적 baked, visual_verification_scope: always, test-runs.d fragment 기록). **잔여**: verify-completion → commit(사용자 confirm) → PR·머지 → web 재배포(deploy_scope: included) → POST-DEPLOY 라이브(자동노출·닫기·재확인·중간버튼 커서·pageerror 0). worktree `ai/claude/feature-0003-graph-entry-help`(base main f44623f3).

---

**2026-07-14 TASK-20260714T053522-step-scroll-raf — 펼친 "결과 보기" 가로 스크롤 layout-timing 0-clamp 후속 수정** (Minor §12.3 — feature-0003 프론트 단독, additive). step-scroll-preserve(REQ-...T015432) **배포 후 사용자 재보고**: "가로 스크롤이 지속적으로 초기화 여전"(character 테이블 구조 결과셋 스크린샷). **진단**: 배포 자산에 라운드1 수정 반영됨(서빙 심볼 13회 확인)·경로도 맞음(사이드 패널 `_renderStepSidePanelBody`) → 실브라우저 **`scrollLeft` layout-timing 문제**로 좁힘. 동기 복원이 재렌더 직후 결과 표(`.result-table-wrap`) layout 확정 전에 `scrollLeft` 를 써서 브라우저가 `scrollWidth`(overflow 미확정)로 **0-clamp**(세로는 짧은 결과라 overflow 없어 미관측·동일 취약). 라운드1 jsdom 테스트는 scrollLeft 를 clamp 없이 verbatim 저장해 이 결함을 놓침(교훈: scroll clamp 는 jsdom 검증 불가·layout 의존은 real-browser/배포후 실측이 정본). **수정(`static/app.js` additive)**: 공용 `_applyStepPanelScroll`(내부 결과+외부 목록 복원) + `_scheduleStepPanelScroll`(동기 1회 + `requestAnimationFrame` 1회 재적용 → layout 확정 후 0-clamp 복구). 두 렌더 경로(`_renderStepSidePanelBody`·`renderProgress`)의 인라인 복원을 스케줄러로 대체(동기 유지 + rAF 추가라 회귀 표면 0). **검증**: `node --check` PASS · `verify_step_result_scroll_preserve.mjs` **29/29 PASS**(+5: rAF 배선·동기+rAF 이중 복원·0-clamp 복구 경로·큐 소진). **로컬 real-browser 미재현**(chromium 다운로드 환경 차단) — 근본원인 well-known + additive 라 배포 진행, 최종 확인=배포 후 사용자/PB-0008. **잔여**: verify-completion → commit → PR·머지 → web 재배포 → 사용자 실측 확인. worktree `ai/claude/feature-0003-step-scroll-raf`(base main a890e47e). REV-20260714T053522-step-scroll-raf.

---

**2026-07-14 TASK-20260714T105200-graph-analyze-perm — 그래프 AI 능동 분석 '실행' 권한을 조회에서 분리한 하위 권한(`metadata.graph.analyze`)** (Critical §12.3 인증/인가 — feature-0003 RBAC backend + frontend 버튼 게이팅). 사용자 요청: "그래프 뷰의 `AI 능동 분석` 실행 권한은 하위 권한으로 구분… 권한이 없을 경우 관련된 버튼 UI가 나타나지 않도록." graph-perm-split(2026-07-13) 후 `metadata.graph.read` 가 조회+분석실행을 함께 커버하던 것을, 분석 실행(LLM 호출·KB 갱신·비용 유발 특권)만 떼어 별도 통제. **하위호환 = A안(최소권한, backfill 없음)**: graph.read 만으론 analyze 미부여(함의/역함의 없음), admin 은 seed catchup 으로 획득, 현재 graph.read 보유자 admin 뿐이라 실질 영향 0. **구현**: (backend) 신규 `metadata.graph.analyze`(group=kb, admin catchup 포함) + 실행 POST 2개(`/graph/analyze` 노드·`/graph/analyze-schema` 스키마) → `require_permission('metadata.graph.analyze')`, GET status/node/columns 는 graph.read 유지; (frontend) 종속맵 `graph.analyze→graph.read` + 능동 분석 트리거 UI **5곳**(노드 상세 AI 섹션·노드/스키마/combo 우클릭·클러스터 카드 버튼) `can("metadata.graph.analyze")` 게이팅(미렌더+바인딩 skip). **검증**: 권한 단위테스트(graph.read 만으론 analyze 미부여·독립부여·admin catchup·종속 pin) + feature-0003 전체 스위트 PASS(회귀 0) · §18.8 보안 렌즈 적대 리뷰. **잔여**: verify-completion → 머지 → web 재배포 → 배포 후 실증(graph.read-only 계정 버튼 미노출·POST 403 / graph.analyze 계정 버튼·실행 정상). worktree `ai/claude/feature-0003-graph-analyze-perm`(base ee4f8de6). REV-20260714T105200-graph-analyze-perm.

---

**2026-07-14 TASK-20260714T015432-step-scroll-preserve — 실행 단계 폴링 갱신 시 펼친 "결과 보기" 스크롤 보존** (Minor §12.3 — feature-0003 프론트 단독, RBAC/스키마/백엔드/엔드포인트 무변경, 비파괴). `/_template:entry` arg-given dispatch. **사용자 보고**: 서비스 assistant 에 요청해 내부 실행 단계가 진행될 때, 각 단계 갱신마다 펼쳐 둔 "결과 보기"(step 결과 표/미리보기)의 스크롤이 초기값(맨 위)으로 되돌아감 — "단계 진행에 따른 기존 항목들에 대한 스크롤 보존" 요청. **진단**: 라이브 폴링 재렌더 2경로 — 사이드 패널 `_renderStepSidePanelBody`(`refreshStepSidePanel`@폴링)·인라인 progress 카드 `renderProgress`(`pollProgress`→`applyProgressPayload`) — 가 컨테이너를 `innerHTML=""` 로 통째 재작성. 펼침 상태는 `state.stepResultExpanded`+`_stepResultKey` 로 이미 복원되나 **스크롤 위치는 미복원** → 결과 표(`.result-table-wrap` max-height min(60vh,460px))·미리보기(`.step-result-preview` max-height 120px)·외부 목록(`.step-side-panel-body`/`.progress-steps` overflow-y:auto) 전부 0 초기화. **수정(`static/app.js` only)**: ① `buildStepDetailEl` 결과 wrap 에 `data-step-result-key=stepKey`(펼침 영속화와 동일 `_stepResultKey`) 부여. ② 제네릭 헬퍼 `_snapshotStepResultScroll`/`_restoreStepResultScroll`(컨테이너 무관 `[data-step-result-key]` 비-hidden 의 top/left 캡처·복원, 접힘·미매칭·null 방어). ③ `_renderStepSidePanelBody`·④ `renderProgress` 모두 재렌더 전 스냅샷(외부 prevScrollTop + 내부 결과) → `innerHTML=""` → 복원(내부 결과 + 외부: 하단추종=최하단 / 미추종=이전 위치 유지, 기존 미추종 0 리셋 제거). **비변경**: 펼침/토글·하단추종 자동스크롤·step dedup 키·백엔드/엔드포인트/RBAC/스키마 0. **§18.8**: 단일 파일·비파괴·백엔드 무변경 Minor → 패널 skip(REV `[SKIPPED:frontend-ui-minor-single-file-no-backend-no-rbac]`, 적대 자가검토 4가설 refute). **검증**: `node --check app.js` PASS · 신규 `tests/verify_step_result_scroll_preserve.mjs`(jsdom@22 소스추출 격리) **23/23 PASS**(배선 양경로·capture/restore 계약·펼침만 캡처·접힘 skip·새 단계 무영향·방어). **잔여**: verify-completion → commit(사용자 confirm) → PR·머지 → web 재배포 → **POST-DEPLOY PB-0008**(라이브 다단계 run 폴링 중 펼친 결과·외부 목록 스크롤 유지, 비결정적 재현이라 배포 후 잔여, visual_verification_scope: always). worktree `ai/claude/feature-0003-step-scroll-preserve`(base main 0524d5a7). REV-20260714T015432-step-scroll-preserve.

---

**2026-07-13 TASK-20260713T185600-graph-perm-descfix — graph-perm-split 배포 후 seed catchup 1406 hotfix** (feature-0003 backend 부트스트랩 robustness). graph-perm-split(PR #765) **배포 후 실증**에서 `WebSchemaMigrations` 미생성·backfill 미실행 적발 → web-a 로그 `seed catchup skipped: 1406 (22001): Data too long for column 'Description'`. **근본원인**: `kb.ingest.manual` 설명을 301자로 늘렸는데 `WebPermissions.Description` = VARCHAR(255) → `_ensure_permission_catalog` INSERT 1406 → 감싸는 `_ensure_seed_catchup`(운영 재기동 fast path) **전체 skip** → `_ensure_seed_roles`·graph-perm backfill·기타 catchup 통째 미실행. **CI(`--no-deps`)가 컬럼 제약 미검출**(graph-perm-split 보안 리뷰가 지적한 "부트스트랩 DB 통합테스트 부재" 갭이 실사고로 실현). **영향 실측**: 그래프 접근 상실 사용자 **0명**(유일 묶음 보유 role=admin, 이미 explicit graph.read 보유·비-admin 묶음 보유자 부재) — 단 seed catchup 전체가 매 startup 차단되는 부트스트랩 fragility 는 즉시 수정. **수정(2건)**: (1) `_ensure_permission_catalog` 가 label/description 을 컬럼 길이(128/255)로 **방어적 클립**(단일 긴 문자열이 전 catchup 을 차단하던 fragility 제거·재발 방지), (2) `kb.ingest.manual` 설명 301→205자 단축(온전 저장). 전 권한 desc≤255·label≤128 AST 전수 확인(잘림 0). **검증**: py_compile OK · feature-0003 전체 스위트 PASS(회귀 0). **잔여**: verify-completion → 머지 → web 재배포 → **재실증**(web 로그 `seed catchup skipped` 소멸 + `WebSchemaMigrations` graph-perm-split-v1 row). worktree `ai/claude/feature-0003-graph-perm-descfix`(base b2e86880). REV-20260713T185600-graph-perm-descfix.

---

**2026-07-13 TASK-20260713T181800-graph-perm-split — 그래프 뷰 권한(`metadata.graph.read`)을 '메타데이터 관리' 묶음(`kb.ingest.manual`)에서 분리** (Critical §12.3 인증/인가 구조 변경 — feature-0003 RBAC backend + frontend 표시계층 + 1회 데이터 backfill; 사용자 승인 B안). `/_template:entry` arg-given dispatch. 사용자 요청: "그래프 뷰가 별도의 탭으로 분리됨에 따라, 권한 또한 '메타데이터 관리'로부터 별도로 분리." **현황 진단**: 그래프 뷰는 이미 별도 최상위 탭(feature-0016 §45, PR #738)이나 권한은 미분리 — `kb.ingest.manual`("메타데이터 관리 전체 묶음")이 `_METADATA_MANUAL_IMPLIES` 로 `metadata.graph.read` 를 여전히 자동 함의(묶음만 있어도 그래프 탭 접근). 프론트도 탭 게이트/종속맵이 묶음을 인정. **결정(AskUserQuestion)**: 하위호환 = **B안(분리 + 기존 접근 보존, 비파괴)** — A안(완전 분리, 기존 보유자 접근 상실) 대비 현재 접근 회수 없음, 프로젝트의 일관된 "기존 배포 무손실" 패턴 정합. **구현**: (1) `web_context.py` `_METADATA_MANUAL_IMPLIES` 에서 `metadata.graph.read` 제거(편집 4종만 함의) + 묶음 설명·graph 라벨("그래프 뷰 조회")/설명 갱신. (2) 신규 `_backfill_graph_perm_split_v1(conn)`(`_ensure_seed_roles` 말미 호출) — 분리 전환 **1회만** (a) `kb.ingest.manual` 보유 role→`metadata.graph.read` role 권한, (b) 묶음 ALLOW override 계정→graph.read ALLOW override(graph.read DENY 는 존중) 로 그때의 effective 접근을 명시 grant 로 고정. **1회 guard**: 신규 `WebSchemaMigrations` 마커 테이블(`_bootstrap_schema.py` DDL) — 매 startup 재실행 시 분리 이후 신규 묶음까지 graph 획득해 분리 무력화되므로 정확히 1회. (3) `admin.js` 탭 게이트 `graph:["metadata.graph.read"]`(묶음 인정 제거) + 종속맵 graph.read 부모 `kb.ingest.manual`→`console.access`(직속 승격). (4) `admin.html` 게이트 주석. **비변경**: `metadata.graph.read` code/catalog·admin explicit catchup(admin 무영향)·백엔드 enforcement 단일 choke `_apply_permission_overrides`·편집 4종 함의·엔드포인트 shape 0. **검증**: 권한 단위테스트(`test_metadata_perm_split.py` R3/R3c/R3d·`test_permission_dependency_map.py` t5/m3) + **feature-0003 전체 스위트 PASS(회귀 0)** — 초기 2 실패는 복사한 `.env` 의 `AGENT_RUNTIME_READ_BACKEND=postgres`·`AGENT_TIMEOUT_SEC=300` 이 `--no-deps` DB-less 에서 유발한 환경 기인(base main 동일 재현·env 중립화 시 소멸, 본 변경 무관 확정). + §18.8 보안 렌즈 적대 리뷰(권한상승·접근상실·멱등·enforcement·SQL). **잔여**: verify-completion → commit(사용자 confirm) → 머지·push → web 재배포(정적 baked + 마이그 startup) → 배포 후 DB 마커·라이브 권한 그리드 + PB-0008 Windows-browser(묶음-only 계정 그래프 탭 미노출·graph.read 계정 노출). worktree `ai/claude/feature-0003-graph-perm-split`(base fbaf94f4). REV-20260713T181800-graph-perm-split.

---

**2026-07-13 TASK-20260713T094624-ds-conn-test — 작업화면 제품 드롭업의 데이터소스 라벨을 '연결 테스트' 버튼으로 + 관리 콘솔식 단발성 Toast(입력창 비가림 상단 표시)** (Major §12.3 — feature-0003 web/UI(app.js/admin.js/styles.css) primary + 백엔드 throttle(routers/admin_datasources.py); 스키마/마이그/신규 RBAC/신규 엔드포인트 무). `/_template:entry` arg-given dispatch. **사용자 요청**: 채팅 작업화면 제품 목록에서 연결된 데이터소스의 연결 여부 테스트 버튼(데이터소스 라벨 클릭) + 관리 콘솔 '연결 테스트'처럼 단발성 Toast, 단 작업화면 토스트는 기존 입력창을 가리지 않도록 화면 상단부터 표시. **현황 진단**: 관리 콘솔 실시간 연결 테스트 `POST /api/admin/datasources/{key}/test` 는 `console.access`+`datasource.manage` 관리자 권한 요구, 채팅 화면엔 수동 프로브 없이 백그라운드 모니터 캐시 상태(`conn_status`)만 `/api/session` 으로 노출됨. **설계(AskUserQuestion 2결정)**: ① 테스트 방식 = **A2** 관리자 엔드포인트 재사용(별도 RBAC 추가 없음) + 남용 방지 프론트/백 재시도 텀. ② 상단 토스트 = **C2** 작업화면 전체(`#toast` id 오버라이드 상단 앵커, admin `#adminToast` 하단 불변). **구현**: (1) `static/app.js` — `buildProductDropupItem` 데이터소스 배지를 `canOpenAdminConsole()` 게이트 하에 실제 `<button>`('연결 테스트') 로 렌더(단일=그 DS, 멀티="N개 데이터소스"→전체 순차 테스트+요약 토스트), 클릭 stopPropagation 으로 제품선택과 분리, 중첩 `<button>` 회피 위해 **행 요소를 `<button>`→`<div role=menuitem tabindex>` (click+keydown Enter/Space 로 선택 복원)**; `runDatasourceConnTest` 가 프론트 per-key/조합키 쿨다운(4s, `.has()` sentinel)·진행 중 `disabled`·결과/403/429 를 상단 토스트로 표시. (2) `static/styles.css` — `#toast { top: calc(--topbar-h + 14px); bottom:auto; max-width: min(460px, 100vw-32px) }`(작업화면 전 토스트 상단화·narrow clamp·bg transition), `button.product-dropup-item-ds--test`(at-rest 테두리 어포던스·min 24px 터치타깃·hover 틴트·:disabled). (3) `routers/admin_datasources.py` — `admin_test_datasource` 에 per-(account,key) 쿨다운(env `AGENT_DS_TEST_COOLDOWN_SEC` 기본 3s, resolve/SSRF 이후·probe 직전 게이트, 미경과 시 probe 없이 **429 throttled** — 부하 급증 방지, in-process·per-replica coarse). (4) `static/admin.js` — 공유 엔드포인트 429 graceful: 배지 lazy probe 는 'down' 오분류 대신 직전 상태 유지, 상세/제품바인딩 '연결 테스트' 버튼은 중립 토스트. (5) 회귀 테스트 하네스(`verify_profile_icon_consistency.mjs`)에 `canOpenAdminConsole` 스텁 추가 + 신규 throttle 계약 테스트 2건. **비변경**: 스키마/마이그/신규 RBAC/신규 엔드포인트 0·무권한 사용자 배지는 기존 display-only span(회귀 0)·관리 콘솔 토스트 위치·index.html 캐시버스터(빌드 content-hash 자동 주입, 수기 bump 안 함). **§18.8 적대 패널(3 렌즈, REV-20260713T094624-ds-conn-test)**: backend+security(BLOCKING/MAJOR 0, NIT 4+MINOR 1 반영)·frontend+QA(HIGH 테스트 하네스 붕괴·MED-HIGH `pointer-events:none` 더블클릭 라우팅·MED 쿨다운 sentinel 전건 수정)·UX+a11y(MAJOR 중첩 인터랙티브·at-rest 어포던스·접근가능한 이름 전건 수정) → **SHIP-WITH-FIXES → 반영 후 SHIP**. **검증**: `node --check`(app.js·admin.js module)·`py_compile`·CSS 1780/1780·타깃 pytest 6/6·**전체 feature-0002+0003 = 1902 passed / 2 skipped / 0 failed(회귀 0)**. **잔여**: verify-completion → 머지·push → web 재배포(deploy_scope: included, frontend+backend→web 이미지) → **POST-DEPLOY PB-0008 실 Windows 브라우저 라이브 검증**(win-browser relay 172.26.144.1:9223 열림 — 데이터소스 버튼·상단 토스트·입력창 비가림·429 쿨다운·admin 회귀 0). worktree `ai/claude-corp/feature-0003-ds-conn-test`(base main 469fa20d). §8 개선 제안: 공통 `_append_ds_test_throttle` 공유 store(멀티 replica 정밀 억제)·게이트를 datasource.manage 세션 플래그로 정밀화.

---

**2026-07-13 TASK-20260713T053423-attach-user-version — 사용자 재업로드 첨부 버전 관리(해시 대조 → 버전 체인 편입 + assistant 인지 + 과거 버전 비교 정합)** (Major §12.3 — feature-0003 첨부 업로드 경로 + cross-cut feature-0002 LLM 컨텍스트; 스키마/마이그/RBAC/엔드포인트 shape 무변경). `/_template:entry` arg-given dispatch. 사용자 요청: 대화 중 같은 파일 재첨부 시 완전히 동일하지 않으면(해시 대조) 버전을 올려 다시 첨부, assistant 가 갱신 인지, 과거 버전 비교 정합. **현황 진단**: 버전 인프라(sha256·RootAttachmentId·VersionNumber·CreatedByRole·SupersededAt + 버전 조회 API·`v{n}` 배지)는 TASK-0274/0285 로 완비돼 있으나 **assistant 파일 수정(materialize)에서만** 체인이 채워지고 사용자 재업로드는 매번 별개 첨부(root=NULL, v1)를 만들었다(sha256 저장되나 dedup 미사용). 본 작업은 그 체인을 **사용자 업로드 경로로 확장**. **설계(사용자 승인 3결정)**: 파일명 자동감지 / 버전 표식+변경점 diff 주입 / 체인 정합+assistant 비교(신규 UI 최소). **구현**: ① `_conv_store.py` 신규 `_find_latest_same_name_attachment`(대화 내 `(ConversationId,AccountId,OriginalFilename)` 최신 head 조회 — 그룹 대화 타 멤버·타 대화 혼입 차단)·`_compute_version_diff`(unified diff, size-cap) + `app.py` p15 rebind. ② `conversations.py upload_conversation_attachment`: sha256 후 prior head 조회 → **해시 일치=기존 최신 버전 재사용(멱등, 새 row·MinIO 미생성, `reused_existing_version:true`)** / **불일치=같은 root 체인 v(MAX+1)·`CreatedByRole='user'` INSERT + 직전 supersede + 체인 전체 PG dual-write**(prior 없으면 root=NULL·v1·MetaJson=NULL → 기존 default byte-동치). ③ `agent_core.py _build_attachment_context_section`: SELECT 에 버전 컬럼 3개 append(기존 positional index 0~8 보존)·`version_number>1` 파일 라인에 🔄v{n} 표식(사용자 재업로드/AI 수정 구분)·`MetaJson.version_diff` 를 `## FILE UPDATES` 섹션으로 `_datamark_untrusted` 후 ```diff``` 주입. ④ `static/app.js`: 버전 인지 toast(`_attachUploadDoneMessage`)·pill `sha256`/`version_number` 필드·클라이언트 dedup 을 이름+크기 → **sha256 해시 대조**로 정밀화(`_sha256HexOfFile` — 동일 내용만 차단, 변경분은 통과해 백엔드 버전 판정). **비변경**: 버전 스키마/마이그(모든 컬럼 기존재)·RBAC/신규 엔드포인트·assistant materialize 경로(무리팩터 — 회귀 방지 위해 별도 헬퍼로 구현)·기존 목록 `SupersededAt IS NULL` 필터·버전 조회 API/배지 재사용. **검증**: py_compile 4 + node --check PASS · 첨부 버전 테스트 31 PASS(신규 `test_attachment_versioning.py` +6, `test_attachment_user_version_context.py` +5) · **전체 스위트 EXIT=0**(회귀 0 — 기존 9-tuple 컨텍스트 테스트는 `len(row)>10` 가드로 보호). **잔여**: §18.8 적대 보안 렌즈(IDOR·체인 무결성·injection) → verify-completion → 머지·push → web 재배포(deploy_scope: included) → PB-0008 실 Windows 브라우저(재업로드→"새 버전 v2" toast·버전 배지·assistant 변경점 인지). worktree `ai/claude/feature-0003-attach-user-version`(base main 87767ebe).

---

**2026-07-09 TASK-20260709-ask-timeout-nonblocking — 응답 지연 시 화면 전체를 덮던 타임아웃 복구 모달 제거(조용한 자동 재연결로 대체)** (Minor §12.3 — feature-0003 프론트 단독, 백엔드/스키마/RBAC/엔드포인트 무변경). 사용자 신고(/_template:entry arg-given): "작업 화면에서 assistant 에 요청 후 오래 걸리면 화면 전체를 가리는 답변-지연 경고창이 떠 불편 — 삭제하거나 기존 작업을 방해하지 않는 UI로." 후속 지시: "자동 재연결은 필수, 사용자는 그 작동을 알 필요 없음." **진단**: `static/app.js sendPrompt()` 의 `/api/ask` 실패 + `is_processing=true` 경로가 `showTimeoutRecoveryDialog`(fixed inset0·z-index 9999 backdrop + "요청 취소/즉시 답변/계속 기다리기" 3버튼 모달)를 `await` 로 띄워 사용자 진행을 강제 중단. 이 3액션은 이미 컴포저 인라인 어포던스로 상시 존재 — 취소=전송버튼 "중단" 모핑(TASK-0157, `cancelCurrentRun`→`/api/cancel`), 즉시 답변=`composerFinalizeBtn`(TASK-0158, `finalizeCurrentRun`→`/api/finalize`), 계속 대기=`attachAndWaitForResult` 기본 동작 → 모달은 중복 UI. **변경(frontend only)**: ① `is_processing` 분기를 모달·토스트 없이 `attachAndWaitForResult(askCid,{runId})` 직접 호출(조용한 long-poll 재연결)로 교체 — 답변 유실 방지 + 화면 미가림, 재연결 사실은 사용자에게 미표면화. ② dead code 된 `showTimeoutRecoveryDialog` 함수 제거(tombstone 주석 대체). ③ `docs/DESIGN-entry-points.md` 의 "모달 패턴 예시=`showTimeoutRecoveryDialog`" 참조 2곳을 잔존 `.share-mgr-backdrop`/`.share-mgr-panel` CSS-클래스 패턴(`showTotpLoginPrompt`)으로 갱신. ④ `index.html` app.js 캐시버스터 `?v=20260709-ask-timeout-nonblocking`. **비변경**: 서버 `/api/ask_status`·`/api/ask_result` long-poll·`attachAndWaitForResult` 루프·boot-time auto-attach·resume 경로(이미 모달 없이 attach)·30분 상한 종료 토스트 전부 보존. RBAC/스키마/마이그/엔드포인트 0. **§18.8 적대 서브에이전트 패널(2라운드)**: R1 에서 **MAJOR(H1)** 적발 — 모달 제거가 노출한 pre-existing 잠복 버그(신규 대화 첫 메시지 타임아웃 `earlyCid` 흐름에서 `myAskInFlight`/`busyConversations` 키가 sentinel→earlyCid 미이관 → `_myAskInFlightHere()` false → 인라인 "중단" 무동작; `askAbortControllers` 만 이관되던 비대칭). **동반수정**: early-cid 활성 블록에 두 set 이관 + `renderComposer()`(abort controller 이관과 대칭), finally 에 `askKey` dual-delete(leak 방지). R2 재검 전항목 REFUTED → **VERDICT: SHIP**(REV-20260709T130000-ask-timeout-nonblocking, NIT 1 무해 accept). **검증**: `node --check app.js` PASS(2회) · 코드 내 `showTimeoutRecoveryDialog` 실참조 0(설명 주석만 잔존). **잔여**: verify-completion → 머지·push → web 재배포(deploy_scope: included, frontend-only→web 이미지) → PB-0008 Windows-browser 라이브 실측(타임아웃 유발 시 화면 미가림·답변 자동 수신·기존/신규 대화 양 흐름 인라인 취소/즉시답변 동작). worktree `ai/claude/ask-timeout-nonblocking`(base aa9f7a57).

---

**2026-07-06 TASK-20260706T013532-reasoning-effort — 대화 화면 사용자 지정 추론 강도(낮음/일반/높음/매우 높음) 선택기** (Major §12.3 — feature-0003 web/UI·API primary + cross-unit feature-0002 agent-core·shared/model_catalog). `/_template:resume` 재개: 세션 `insight-worker gemma fallback 처리 구성`(PR #592 완료·머지) 말미에 제기됐다가 아키텍처 조사 착수 직후 세션 한도로 중단된 요청을 이어받아 완수. **결정(2026-07-04)**: 매핑="끄기 없이 4단계"(낮음도 최소 thinking)·저장="대화별 영구 저장"·UI="composer '+' 액션 메뉴". **구현**: (1) `shared/model_catalog.py` 레벨→budget override 매핑(낮음2000/높음10000/매우높음16000, **일반=override 없음**)·`normalize_reasoning_level`·`thinking_budget_for_level`·`model_supports_thinking`(claude-* 만). (2) `agent_core.py` `_call_llm` 이 thinking 지원 모델 + 명시 레벨일 때만 요청 단위 `extra_body.thinking.budget_tokens` 주입 → LiteLLM 이 alias 고정 thinking 을 요청 단위 override(litellm_config.yaml 무변경). `run_agent`/`_run_agent_core`/worker `_payload_to_kwargs` 배선. (3) `conversations.py` `/api/ask` normalize·검증(부재=None=override 없음)·명시레벨 KV 저장·run_kwargs 캡처 + `/api/history` KV hydration. (4) `static/{index.html,app.js,styles.css}` composer '+' 메뉴 "추론 강도" 항목 + 4단계 secondary 팝업(모델 선택자 미러)·`askBody.reasoning_level`·localStorage 미러·대화 전환 hydration(N1 seq 가드)·비-thinking 모델 비활성. **비변경**: 보조 LLM 호출(summary/topic/validate)·스키마/마이그(KV 재사용)·RBAC/신규 엔드포인트 0. **§18.8 적대 패널(REV-20260706T013532-reasoning-effort)**: BLOCKING 2 적발 — **B1**(일반=고정 budget 이면 sonnet config 16000 조용히 강등) → **일반=no-override 로 수정** + 회귀 가드 테스트; **B2**(extra_body override 미검증) → **라이브 게이트웨이 프로브로 실증**(budget 1024 vs 16000 → 동일 프롬프트 reasoning 2073자 vs 6914자·completion 1377 vs 5935토큰 = override 확실 동작). NIT: N1(hydration clobber) 수정, N2(모델 체인) 검증-동일, N3(KV 읽기 backend) graceful. **검증**: `py_compile` 5 + `node --check` PASS · 신규 `test_reasoning_effort.py` 12 PASS(B1 가드 포함) · 전체 스위트 회귀 0(worktree 코드 대조). **잔여**: verify-completion → 머지·push → web 재빌드·재배포(deploy_scope: included, frontend+backend → web 이미지) → /healthz + PB-0008 Windows-browser 라이브 실측. worktree `ai/claude/feature-0003-reasoning-effort`(base 943b3a2b).

---

**2026-07-02 TASK-20260702-aiops-conv-link-fix — AI 운영 현황 '최근 활동' 상세 시스템 sentinel 대화 링크 깨짐 수정** (Minor §12.3 — feature-0003 프론트 단독, 백엔드/스키마/RBAC 무변경. TASK-20260702-audit-nav-ux 후속 — PB-0008 라이브 적발). **발견**: audit-nav-ux(bc2a0fa6) 배포 후 실 Windows 브라우저 PB-0008 검증에서 '최근 활동' 첫 행(insight worker `table_insight`) 클릭 시 상세 '연결 대화' 가 `/?conversation=__insight_worker__` 열 수 없는 링크로 렌더됨을 적발. insight/ask 워커·자율 sweep 등 활동 대부분이 예약 sentinel conversation_id(`__insight_worker__`·`__ask_worker__`·`__global__`·`__kb_manual__` — 전부 `__` 접두, shared/config.py·kb_ingest.py)를 쓰는데 `!= NULL` 이라 링크로 처리 → 다수 행이 빈 대화로 이동하는 깨진 링크. **수정(frontend only)**: `static/admin.js` `aiOpsActivityRowsHtml` 에 `isSysConv = cid && cid.slice(0,2)==="__"` 가드 — sentinel=안내(sentinel id 표기)·링크 없음, 실 사용자 대화(비-`__`)=`/?conversation=<id>` 링크 유지, NULL=기존 일반 안내. `static/admin.html` cache-buster `admin.js?v=20260702-aiops-conv-link-fix`. **비변경**: 백엔드 `_query_activity`·엔드포인트·스키마·RBAC·마이그 0(conversation_id 페이로드는 audit-nav-ux 그대로). **검증**: `node --check` PASS · `make test` **exit 0**(백엔드 무변경 회귀, feature-0002+0003) · PB-0008 재검증(배포 후 sentinel 행=안내·링크 없음, 실대화 행=링크). worktree `ai/claude/feature-0003-aiops-conv-link-fix`(base 4ec15191). REV-20260702T193000-aiops-conv-link-fix.

---

**2026-07-02 TASK-20260702-audit-nav-ux — 감사 카테고리 순서 재구성 + 항목 툴팁 + AI 운영 현황 '최근 활동' 클릭 상세 확장** (Minor §12.3 — feature-0003 프론트 UI + 읽기전용 additive 백엔드, RBAC/스키마/인가/파괴적 변경 무. /_template:entry arg-given dispatch). 사용자 요청: "`관리 콘솔 > AI 운영 현황`에서 (1) `감사` 카테고리 순서 재구성: 감사 로그·보관 대화·LLM 사용량·AI 운영 현황 (2) 각 항목 hover 시 상세설명 툴팁 (3) 운영 현황 '최근 활동' 클릭 시 상세 확장 — 구조는 `프로필 > 사용 내역 > 차트`·`LLM 사용량 > 차트` 그래프 클릭→대화 목록 드릴다운 참조." **구현**: (1) `admin.html` 감사 그룹에서 `보관 대화`(archives) 버튼을 `LLM 사용량`(usage) 앞으로 이동 — 권한 게이팅(ADMIN_TAB_PERMISSIONS)·서브탭·applyAdminTabVisibility 그룹경계 동적계산 모두 data-admin-tab 키 기반이라 DOM 순서 변경만으로 불변. (2) 감사 그룹 4개 탭 버튼에 네이티브 `title` 상세설명 — admin.html 기존 title 관례와 정합. (3) 참조 드릴다운(요약→상세)을 **인라인 아코디언**으로 구현: `admin.js aiOpsActivityRowsHtml` 를 "클릭 요약 행(role=button/tabindex/aria-expanded/caret) + 숨김 상세 패널"로 재구성 + `renderAiOps` 에 aiOpsActivityList 위임 click/keydown 토글 배선(페이징 '더 보기' append 행도 상속). 상세: 작업(label+task)·요청→서빙 모델(model→resolved_model)·토큰(프롬프트/완료/합계)·추정 비용·지연·run_id·**연결 대화**(conversation_id 있으면 `/?conversation=<id>` 새 탭 링크 — showUsageConvModal 대화 open 규약 재사용, 없으면 "시스템·자율 호출 미귀속" 정직 안내). 백엔드는 신규 엔드포인트 없이 `_query_activity`(overview activity feed + `/api/admin/ai-ops/activity` 페이징 공용 헬퍼) SELECT 컬럼 확장(model·resolved_model·run_id·conversation_id) + dict additive 필드 → 페이징 자동 상속, 기존 필드(id/task/category/label/model(served)/total_tokens/cost_usd/latency_ms/created_at) byte-동치 보존(writer 가 빈 resolved_model 을 NULL 강제 → `r[3] or r[2]` == 기존 `COALESCE`). **변경**: `static/admin.html`(순서·title·cache-buster `admin.js?v=20260702-audit-nav-ux`), `static/admin.js`(aiOpsActivityRowsHtml·_toggleAiOpsActRow·bindAiOpsActivityToggle·renderAiOps 배선), `routers/ai_ops.py`(_query_activity), `tests/test_ai_ops.py`(_act_rows 11열 + 신규 필드 assert). 신규 RBAC/스키마/마이그/파괴적 변경 0. **검증**: `py_compile`(ai_ops.py)·`node --check`(admin.js) PASS · `make test` **exit 0**(feature-0002+0003 전량, test_ai_ops.py **15/15**) · ruff PASS · §18.8 적대 패널(3-렌즈: 백엔드 correctness/보안·프론트 XSS/UX·테스트 정합) **VERDICT: SHIP**(BLOCKING/MAJOR/MINOR 0, NIT 3 비차단) → REV-20260702T190000-audit-nav-ux. **잔여**: verify-completion → 머지·push → web 재배포(deploy_scope: included) → PB-0008 Windows-browser 라이브 실측(순서·툴팁·활동 클릭 상세·대화 링크). worktree `ai/claude/feature-0003-admin-audit-ux`(base 44d958cd). PB-0008 = 배포 후 라이브(baked 자산 사유, TEST.md §3).

---

**2026-07-02 TASK-20260702T021700-attach-count-scope — "+" 메뉴 "첨부파일 목록" 개수 배지 대화 전환 후 stale 수정** (Minor §12.3 — feature-0003 프론트 단독, frontend-only). 사용자 보고: assistant 에 첨부 파일을 전달한 뒤 다른 대화창으로 전환해도 요청 입력줄 "+" 메뉴 "첨부파일 목록" 우측 개수 배지가 이전 대화의 첨부 개수를 그대로 표시(오른쪽 첨부 사이드 패널은 "첨부 파일이 없습니다" 로 정상 — 배지만 stale). **진단**: 배지 textContent 는 `_renderAttachmentPills()`(app.js:7344 clear/:7349 set) 에서만 mutate. 기존 대화 전환 `switchConversation`(:5853)은 `_loadConversationAttachments`(:5883)→`_renderAttachmentPills` 로 재렌더하나, **비-switch 컨텍스트 경로가 이 훅을 누락** — (1) `beginPendingConversation`("새 대화") (2) `_switchToPendingConversationContext`(pending 항목 클릭) (3) `deleteConversation`/`bulkDeleteConversations`/`leaveConversation`(활성 대화 삭제·보관·나가기 → `refreshWorkspace`→`loadConversations`→`loadHistory` 랜딩, §18.8 적대검증 적발 갭). **수정(frontend only)**: `static/app.js` — (1)(2) 두 pending 함수 `renderComposer()` 뒤 + `loadHistory` 두 exit(빈 early-return·정상 종료)에 `_renderAttachmentPills()` 추가(총 4지점). loadHistory 가 switchConversation·refreshWorkspace 공통 sink 이라 삭제/나가기/빈-랜딩 전량 단일 지점 커버. `static/index.html` app.js 캐시버스터 `?v=20260702-attach-count-scope`. 신규 로직/상태/API/RBAC/스키마 0. **검증**: `node --check` PASS · §18.8 적대검증 REV-20260702T021700-attach-count-scope 초기 FAIL(MAJOR 1: delete/leave 갭)→loadHistory 수정 반영 후 정합(BLOCKING 0), logout MINOR 는 비가시·재로그인 자동정정이라 무수정. **잔여**: verify-completion → 머지·push → web 재배포(deploy_scope: included, frontend-only → web 이미지) → 배포 후 사용자 실화면(첨부 후 새 대화·전환·삭제/나가기 랜딩 배지 정정). worktree `ai/claude/feature-0003-attach-count-scope`(base 15e0befc). REV-20260702T021700-attach-count-scope. PB-0008 = 배포 후 라이브(baked 자산·relay 사용자 Chrome 점유 사유, TEST.md §3).

**2026-07-02 TASK-20260702-metadata-perm-hier — 메타데이터(지식베이스) 권한 종속관계 정합화** (Major §12.3 — feature-0003 프론트 단독, RBAC enforcement/스키마/백엔드/엔드포인트 무변경 · UI 표시 계층만). 사용자 요청: "다른 권한 구성과 같이 종속적인 관계가 정합하도록 구성. `지식베이스 > 메타데이터` 권한이 다른 권한 포맷과 차이 확인." **진단**: `admin.js` `PERMISSION_DEPENDENCIES`(childCode→선행 parentCode)는 UI progressive-disclosure **표시 계층**(authz enforcement 아님 — 백엔드는 이 맵을 강제에 미사용, app.py 4개 참조 전부 주석). 관리 권한의 다른 그룹은 전부 "그룹 게이트(read)→세부(manage)" 2단 계층(account.read→console.access + account.*→account.read; role/quota/datasource/product/audit 동형)인데 **메타데이터(kb 그룹)만 평면** — 5개 `metadata.{glossary,enum,table,column}.manage`·`metadata.graph.read` 가 전부 `console.access` 직속이고 묶음 `kb.ingest.manual` 은 맵 부재 고아 root → `_orderItemsAsTree` 가 kb 그룹을 7개 flat 나열. **해법(B안 유지)**: 이미 존재하는 묶음 `kb.ingest.manual`("메타데이터 관리 전체 묶음")을 그룹 게이트로 삼아 정합화 — `kb.ingest.manual→console.access`(타 그룹 base 동형) + 세부 5개 `metadata.*→kb.ingest.manual`(묶음 아래 nest). 결과 `console.access→kb.ingest.manual(묶음)→{용어사전·ENUM·테이블·컬럼·그래프뷰}` 2단 계층. 백엔드 `_METADATA_MANUAL_IMPLIES`(묶음이 5개 함의)와 의미 정합. **enforcement·기존 grant·함의 전부 불변**(맵은 표시 전용). 개별 metadata.* 부여는 "세부 권한 더 보기"로 여전히 가능(B안 보존). **§18.8 NIT-1 흡수**: 메타데이터를 게이트 하위로 옮기며, 역할이 개별 metadata.* 를 (묶음 없이) 부여한 계정을 override 편집기에서 열 때 도달성 cue("N개 부여됨")가 사라지는 회귀 발견 → `isGrantedForReach`(explicit + override 상속-부여) 예측자로 reachability 카운트 복원(checkbox 모드 무영향). **변경(frontend only)**: `static/admin.js`(PERMISSION_DEPENDENCIES 5+1 엔트리 + isGrantedForReach), `static/admin.html`(cache-buster `20260702-metadata-perm-hier`), `tests/test_permission_dependency_map.py`(t5 계층 pin + t6 도달성). **검증**: `node --check` PASS · `test_permission_dependency_map.py` 18개(기존 16 V/M/T + t5/t6) PASS · §18.8 SUBAGENT 적대 패널 VERDICT PASS(BLOCKING 0 — 개별부여 회귀·기존 grant 은닉·enforcement·implies 상호작용·커버리지 5축 refute; NIT-1 수정·NIT-2 테스트 흡수). 백엔드/route/RBAC enforcement/스키마/마이그 0. **잔여**: verify-completion → 머지·push → web 재배포(deploy_scope: included) → 배포 후 라이브 권한 그리드 2단 계층 + 개별부여 도달성 실측. worktree `ai/claude/feature-0003-metadata-perm-hier`(base 654c05ff). REV-20260702T010000-metadata-perm-hier.

---

**2026-07-01 TASK-20260701T100738-convswitch-opacity-guard — 좌측 대화 선택 시 대화창 미표시 방어 하드닝** (Minor §12.3 — feature-0003 프론트 단독). 사용자 보고(/_template:entry, 유저 admin): "작업 화면에서 좌측 대화 항목을 선택해도 대화창에 내용이 안 뜬다 — 선택이 아예 안 먹는 것처럼". **조사**: 현재 배포본(b3175b6)에서 재현 실패 — 백엔드 `/api/use_conversation`·`/api/history` 200+메시지 정상(curl 재현), 프론트도 fresh 브라우저에서 admin 과 동일 role(id 3, "admin") 계정으로 headless 10대화·race·PB-0008 Windows 전부 정상 렌더(opacity 1). 캐시버스터도 정상 동기화(2167cd0 이 app.js stamp f→g bump). → **stale client**(캐시된 구버전 app.js / 장시간 열어둔 탭) 유력. 사용자 결정: 재발 불가하도록 방어 하드닝 배포. **근본 취약점(코드)**: `static/app.js` `selectConversation` conv-switch-fade 의 begin(opacity:0)↔commit(opacity:1) 사이 risk window(pending 리셋·스냅샷·`stopProgressPolling`)가 try 밖 → 예외 시 opacity:0 잔류로 대화창 빈 화면 가능. **변경(static/app.js)**: risk window 를 try 안으로 + 성공/catch 중복 commit 을 단일 `finally` 로 이관 → begin 실행된 모든 경로에서 commit 1회 보장(opacity 복구 구조화), 에러 전파·post-processing·렌더 순서 전부 보존. `index.html` cache-buster bump(`20260701-convswitch-opacity-guard` — stale 사용자에게 새 코드 강제). **검증**: `node --check` PASS · §18.8 적대 리뷰 VERDICT PASS(6점) · 프리뷰 인젝션 후 headless 5대화 op1 · **PB-0008 Windows-browser** 대화 A op1·msg4, A→B 전환 렌더(스크린샷 pb0008_convselect.png). 백엔드/RBAC/스키마/마이그/엔드포인트 0. **잔여**: verify-completion → 머지·push → web 재배포(deploy_scope: included) → 배포 후 최종 확인. worktree `ai/claude/feature-0003-convswitch-opacity-guard`(base 7bca9b2). REV-20260701T100738-convswitch-opacity-guard.

---

**2026-06-30 TASK-20260630T174000-metadata-bs-prefill — 스키마 골격 가져오기 시 기존 저장된 테이블/컬럼 설명 prefill** (Minor §12.3 — feature-0003 프론트 단독, RBAC/스키마/백엔드/엔드포인트 무변경, 비파괴). 사용자 보고(/_template:entry): 관리콘솔 > 메타데이터 > 테이블 설명/컬럼 설명에서 "스키마 골격을 가져왔을 때 기존에 입력된 정보가 확인되지 않음". **근본원인(코드 근거)**: 백엔드 `/api/admin/metadata/bootstrap`(`admin_bootstrap`)은 **설계상 의도적으로 골격(테이블/컬럼 이름·타입)만** 반환하고 설명은 미영속한다(주석: "UI 가 설명 빈칸을 prefill"). 그러나 프론트 `_metaBootstrapRenderResult`(admin.js)가 입력란 생성 시 `adminState.metadata.items`(loadMetadata 가 현재 scope·서브탭 기준 적재한 저장 설명)와 매칭해 `inp.value` 를 채우는 **prefill 로직이 애초 누락** → 골격 import 시 기존 설명이 항상 빈칸. (최근 metadata-bs-inline-desc/list-detail/paging 리팩터가 깬 게 아니라 미구현 상태였음.) **부수 회귀 차단**: prefill 만 추가하면 `_metaBootstrapSave` 가 비어있지 않은 전 행을 `source:"bootstrap"` 으로 재저장 → 기존 `source:"manual"` 설명까지 덮어쓰는 provenance 오염 발생 → prefill 과 **변경분만 저장**을 한 묶음으로 처리. **변경(frontend only, admin.js)**: ① `_metaBootstrapRenderResult` 가 items 를 `(schema,table[,column])` JSON.stringify 키로 색인한 `_descByKey` 구축 → 테이블/컬럼 입력란에 `inp.value` prefill + `inp.dataset.original` 원본 기록. ② `loadMetadata` 가 items 갱신 후 부트스트랩 모드(골격 존재)면 render 재호출 → 스코프/서브탭 전환·저장 후에도 prefill 정합. ③ `_metaBootstrapSave` 가 `desc && desc !== dataset.original` 인 행만 POST(미변경 prefill 재저장 안 함 → source 보존), post-save 는 loadMetadata 재렌더로 저장분+기존 재표시(dataset.original 최신화 → 중복 저장 차단, 빈칸 비우기 루프 폐기). ④ AI 일괄생성(`_metaBootstrapApplyDescriptions`)은 빈 입력란만 채우므로 prefill 보존 — 정합. ⑤ save-info 안내문 갱신. **키 정규화(read 경로 정합)**: 색인/조회 헬퍼(`_metaBootstrapBuildDescIndex`/`_metaBootstrapDescLookup`)가 schema 소문자 + 빈-schema 폴백(정확-schema 우선)으로 키잉 — read 경로 `kb_metadata.load_column_descriptions_for_table`(`LOWER(schema_name)=LOWER() OR schema_name=''`)와 동일 → 수동 폼 입력(임의 케이스)·MSSQL DB명 케이스·레거시 빈-schema 저장분도 매칭. **작업 위치 보존**: items-갱신 경로(loadMetadata/post-save)는 전체 재렌더 대신 in-place `_metaBootstrapRefreshPrefill`(value·original·hint 만) → 검색어·페이지·펼침 보존. **불변식**: `.admin-meta-bs-desc[data-kind=...]` 셀렉터·골격 수집 구조·백엔드 계약 전부 불변. **§18.8 적대 패널(8-가설)**: FIX-THEN-SHIP(BLOCKER 0·MAJOR 1·MINOR 2) → MAJOR-H2(post-save 전체 재렌더가 검색/페이지/펼침 리셋)·MINOR-H3(prefill 정확매치라 케이스/빈-schema 비대칭 누락) 수정 → 재검 SHIP. MINOR-H6(prefill 후 비움=삭제 불가) pre-existing 수용. **검증**: `node --check` PASS · admin.js NUL 0 · 신규 `verify_metadata_bs_prefill.mjs` 44/44(케이스 무관·빈-schema 폴백·정확 우선·dataset.original·in-place 검색보존·변경감지·키 충돌 회피) + 인접 inline-desc 30·list-detail 33·paging 32·scope-single-ds 15 회귀 0. cache-buster lockstep bump(admin.js·styles.css → `20260630-metadata-bs-prefill`). 백엔드/route/엔드포인트/RBAC/스키마/마이그 0. **잔여**: verify-completion → 머지·push → web 재배포(deploy_scope: included) → PB-0008 Windows 브라우저 시각검증(골격 가져오기 시 기존 설명 prefill·미변경 저장 0·수정행만 저장·source 보존·저장 후 검색/페이지 보존). worktree `ai/claude/feature-0003-metadata-bs-prefill`(base dcb3e02). REV-20260630T174000-metadata-bs-prefill.

---

**2026-06-30 TASK-20260630T160000-metadata-list-detail — 메타데이터 패널 list-detail 2단 재구성(좌측 목록 선택 → 우측 상세 편집)** (Major §12.3 — feature-0003 프론트 단독, RBAC/스키마/백엔드/엔드포인트 무변경). 사용자 요청: 메타데이터 UI 를 다른 카테고리(계정/제품/데이터소스/감사)처럼 한 항목 선택 후 우측 상세조정하는 형태로 재구성 — 위/아래 스크롤이 잦다. **현황 파악(코드 근거)**: 메타데이터 pane 은 단일 컬럼 수직 스택(헤더→서브탭→부트스트랩→폼→목록)이고, 행 '수정' 버튼이 `_metaStartEdit`→목록 **위**의 폼으로 `scrollIntoView({behavior:'smooth'})` 점프 → 사용자가 지적한 스크롤 마찰의 정체. 다른 카테고리는 `.admin-list-detail`(grid 2단: 좌측 .admin-list-col + 우측 .admin-detail-col, 각자 overflow-y:auto). **결정(Q&A)**: list-detail 채택. 부트스트랩 '스키마 골격 가져오기'(단일 항목 모델에 1:1 없음)=**우측 상세 모드**(좌측 툴바 버튼 진입). 거버넌스 안내문=우측 empty-state 로 이동. **변경(프론트)**: ① `admin.html` — 메타데이터 pane 을 2단 list-detail 로. 좌측 검색(#metadataSearch)+카운트+목록(#metadataList), 우측 #metadataDetail(empty-state #metadataDetailEmpty | 폼 #metadataForm | 부트스트랩 #metadataBootstrap). '+ 새 항목'(#metadataNewBtn)·'스키마 골격 가져오기'(#metadataBootstrapOpenBtn). ② `admin.js` — `detailMode(empty|form|bootstrap)`·`selectedId`·`search` 상태 + 코디네이터 `_metaRenderDetail`(모드 유효성 보정→세 컨테이너 배타 가시성, form/bootstrap 위임) + 헬퍼 `_metaSyncListActive`·`_metaSyncListToolbar`·`_metaItemMatchesSearch`. 행 클릭=선택→우측 편집(role=button·keydown target 게이트, '수정'버튼·scrollIntoView 폐기, 삭제/유사어 stopPropagation). 스코프/서브탭/2차보기/init/submit/delete 코디네이터 경유. ③ `styles.css` — pane 단일 스크롤 제외(컬럼 독립 스크롤), 폼 카드 chrome 제거, 행 선택 스타일. cache-buster `20260630-metadata-list-detail` 동반 bump. **불변식**: CRUD·부트스트랩·검토 큐·유사어 데이터 경로 기존 함수 재사용(렌더 위치만 이동). 권한 게이트·백엔드 계약 무변경. **검증**: `node --check` PASS · 신규 `verify_metadata_list_detail.mjs` 33/33 + scope-single-ds 15·inline-desc 30·paging 32 green. **§18.8 적대 패널**: SHIP(BLOCKING 0), MAJOR-2(keydown 이중발화) 수정+잠금, MAJOR-1(검색-편집 desync) 편집보존 의도 수용, NIT-1 정리. 백엔드/route/엔드포인트/RBAC/스키마/마이그 0. **잔여**: verify-completion → rebase onto origin/main(base drift 6) → 머지·push → web 재배포(deploy_scope: included) → PB-0008 Windows 브라우저 시각검증(좌우 2단·행 선택→우측 편집·컬럼 독립 스크롤·스크롤 점프 해소). worktree `ai/claude/metadata-list-detail`(base e820825). REV-20260630T160000-metadata-list-detail.

---

**2026-06-30 TASK-20260630T110910-metadata-ds-single-ui — 메타데이터 패널 '데이터소스' 선택 UI 단일화(헤더 스코프 상속) + 공용 스코프 empty-state** (Major §12.3 — feature-0003 프론트 단독, RBAC/스키마/백엔드/엔드포인트 무변경). 사용자 요청: 관리 콘솔 > 메타데이터 > 테이블/컬럼 설명에서 '데이터소스' UI 가 "스키마 골격 가져오기" 기능과 메타데이터 패널 양쪽에 동시 존재해 혼란 → 각 역할 파악 후 단일 UI 정리. **현황 파악(코드 근거)**: 데이터소스 selector 2개 — (1) 패널 헤더 `#metadataScopeSelect`("데이터소스") = 메타데이터 저장/조회 **스코프**(5서브탭 전체, 저장 target `_metaBootstrapSave`→`scopeKey`), (2) "스키마 골격 가져오기" 내부 `#metadataBootstrapDs`("데이터소스 *") = 스키마 introspection **소스**(테이블/컬럼 서브탭만). 둘은 **완전 독립**이라 헤더 스코프=A·부트스트랩 DS=B 로 어긋나면 "B 골격을 A 스코프로 저장"하는 조용한 불일치(footgun) 가능. **결정(사용자 2-step Q&A)**: 비활성 잔재·더미 selector 금지 → **중복 근원 제거** = 부트스트랩 전용 DS selector 폐기, 데이터소스는 헤더 스코프 상속. 공용(common)은 실제 스키마 없어 부트스트랩 불가 → list-detail `.admin-detail-empty` 컨벤션 정합 **empty-state** 안내. **변경(프론트)**: ① `admin.html` — `데이터소스 *`/`#metadataBootstrapDs` 제거 + `#metadataBootstrapEmpty`(공용 안내)·`#metadataBootstrapHead`·노트 상속 DS 표기(`#metadataBootstrapDsName`). ② `admin.js` — `_metaBootstrapPopulateDs`→`_metaBootstrapSyncToScopeDs`(스코프 DS 상속·DS 변경 시 골격/스키마 리셋·재로드), `_metaSyncBootstrapVisibility` 공용/구체 DS 분기, `_metaBindBootstrap` DS 바인딩 제거, 스코프 change 핸들러가 가시성 동기화 호출. ③ `styles.css` — `.admin-meta-bootstrap-empty` 보강. cache-buster admin.js·styles.css 동반 bump `20260630-metadata-ds-single-ui`. **불변식**: `_metaBootstrapSave` 는 변함없이 `scopeKey` 저장, `bootstrap.datasource`=`_metaScopeDatasourceKey()`(기존 옵션과 동일 `ds.key`) → 백엔드 `/api/admin/metadata/bootstrap*` 계약 동일. 구체 DS 스코프에서만 부트스트랩 노출 → 저장 스코프=골격 소스 항상 일치(footgun 구조적 제거). **검증**: `node --check` PASS · 신규 `verify_metadata_scope_single_ds.mjs` 14/14 + 기존 inline-desc 32/32·paging 회귀 0. 백엔드/route/엔드포인트/RBAC/스키마/마이그 0. **잔여**: verify-completion → 머지·push → web 재배포(deploy_scope: included) → PB-0008 Windows 브라우저 시각검증(공용=empty-state, 구체 DS=단일 데이터소스 컨트롤·상속 노트, 스코프 전환 시 골격 리셋, 중복 selector 부재). worktree `ai/claude/metadata-datasource-unify`(base 8baa707). REV 는 verify 단계 적대 패널 후 부여.

---

**2026-06-29 TASK-20260629T181648-point-scroll-easeoutexpo — 공유 대화 뷰 우측 스크롤바 가이드 뱃지(point rail) 추가 + 가이드 뱃지 클릭 스크롤 단축·EaseOutExpo** (Minor §12.3 — frontend 표현계층, anonymous 공유 노출면). 사용자 요청: 공유 기능으로 전달한 대화에도 우측 스크롤바 대화 가이드 뱃지 UI 구성 + 가이드 뱃지 클릭 시 소요시간을 지금보다 짧게 + Easing 을 EaseOutExpo 로. **현황 파악**: 메인 UI(index.html+app.js)에는 우측 point rail(`renderMessagePointRail`/`#messagePointRail`/`.message-point-dot`)이 이미 있었으나 클릭은 native `scrollIntoView({behavior:'smooth'})`(가변·통상 ≥400ms), 공유 뷰(share.*)에는 rail 자체 부재. **변경**: ① 메인 — rail dot 클릭만 `scrollMessagePointIntoCenter`(`_animatePointScroll`+`_easeOutExpo`, `POINT_SCROLL_DURATION_MS=280`, `messageLogEl.scrollTop` 보간)로 교체(기존 rail 렌더/배치/active 로직·다른 scrollIntoView 4곳 보존). ② 공유 — `share.html` `<nav id="sharePointRail">` + `share.js` 메시지 `share-msg-${idx}` anchor + `setupSharePointRail`/`renderSharePointRail`/`layoutSharePointRail`/`highlightSharePoint`(window 스크롤이라 position:fixed 미니맵, dot top%=문서좌표 비율) + `scrollShareMessageIntoCenter`(`shareEaseOutExpo`+`SHARE_POINT_SCROLL_DURATION_MS=280`, `window.scrollTo` 보간) + scroll(highlight)/resize·ResizeObserver·load(layout) 리스너 + `share.css` rail 미니맵 스타일(focus-visible·reduced-motion·≤720px 숨김). cache-buster bump(share.css/share.js→`20260629-share-scroll-guide`, app.js→`20260629-point-scroll-easeoutexpo`). **검증**: node --check(app.js·share.js) PASS · §18.8 적대 패널 7-lens VERDICT SHIP(BLOCKER 0·MAJOR 0, EaseOutExpo 수치검증·ResizeObserver 루프 부재·XSS 무첨가; G-MINOR focus-visible 흡수). 백엔드/RBAC/스키마/마이그/엔드포인트 0. **잔여**: verify-completion(PASS 9/9) → 머지·push → web 재배포(deploy_scope: included) → PB-0008 Windows 브라우저 시각검증(메인/공유 양 뷰 rail·클릭 단축·EaseOutExpo). worktree `ai/claude/share-scroll-guide-badge`(base 60c0d45). REV-20260629T181648-point-scroll-easeoutexpo.

---

**2026-06-29 TASK-20260629T170913-glossary-role-fieldname-fix — 용어사전 역할 드롭다운/라벨이 실제 역할(dba·admin·sales) 미표시하던 버그 수정** (Minor §12.3 — 프런트 전용). resume(glossary-role-single-ui 배포본 시각검증 후속): 사용자가 "역할 드롭다운에 실제 역할이 안 뜨는데 의도인지" 문의. **판정 = 버그(의도 아님)**. 권한(role.read) 게이트가 아니라 **필드명 불일치** — `/api/admin/roles` 정본 직렬화 role 객체는 `{id,key,name,...}`(역할 관리·계정 화면 전부 `.key`/`.name`)인데 glossary `_metaPopulateRoleFilter`/`_metaRoleLabel` 만 `.role_key`/`.role_name`(미존재)로 읽어 전 역할 스킵→드롭다운 정적 옵션만. **라이브 실증(PB-0008)**: 현 admin 계정 role.read 보유, `/api/admin/roles` 200·8역할 반환, role 객체 키 `["id","key","name",...]`(role_key 부재), `adminState.roles.length=8`인데 드롭다운 옵션 2개뿐. **수정**: admin.js 4 참조 `role_key/role_name → key/name`(단일 진실원 헬퍼 2개 → 필터·배지·태그·유사어/관계 라벨 6 호출부 정상화) + admin.html cache-buster bump. node --check PASS. 백엔드/RBAC/스키마/마이그 0. **잔여**: verify-completion → 머지·push → web 재배포 → PB-0008 재검증(드롭다운 실제 역할 노출). worktree `ai/claude/glossary-role-fieldname-fix`(base 54dbfe3). REV-20260629T170913-glossary-role-fieldname-fix.

---

**2026-06-29 TASK-20260629-metadata-bs-flexclip — 메타데이터 부트스트랩 결과 패널 flex-shrink 클리핑 수정 (PB-0008 적발)** (Minor §12.3 — 프런트 CSS 전용, feature-0003). resume `테이블 설명 AI 자동완성 및 UI 버그 수정`: 원본 작업(metadata-table-desc-fix=MSSQL database 차원/테이블명 정상화/테이블 설명 AI 자동완성 grounding, metadata-bs-collapse=접기·검색 재설계)은 PR #461/#463 으로 머지·배포 완료. 사용자 요청 = **PB-0008 실 Windows 브라우저 시각검증 진행 + 추가 UI 버그 수정**. **PB-0008 시각검증(실 Windows Chrome, win-browser relay)**: ① MSSQL 골격 테이블명 **정상** — `mssql-qa-idc`/`Account` 17개 실테이블(`tblAccount`·`tblAccountBlockLog`·`tblAccountChannel`…)·132 컬럼, tempdb #temp 0(시스템 DB/스키마 필터 정상, 129 실 DB 목록). ② 엔진별 라벨 분기 **정상**(MSSQL='데이터베이스', MySQL='스키마'; `mssql_local`은 로컬 미가동=환경). ③ **테이블 설명 AI 자동완성 작동** — `tblAccount` 단건 suggest 가 grounding 된 한국어 설명 자동 생성("사용자의 로그인 계정과 인증 정보…권한 레벨·차단 상태…접속 서버 정보"). **④ 추가 UI 버그 적발·수정**: 부트스트랩 결과 패널이 다수 테이블 시 ~1행만 보이고 pane 스크롤도 안 돼 나머지 테이블 확인 불가. **근본원인**: `.admin-pane[data-admin-pane=metadata]`(flex column·고정 height·overflow-y:auto)의 flex 자식 `.admin-meta-bootstrap`(overflow:hidden) 이 flex `min-height:auto`=0 으로 무한 압축(flex-shrink:1)→90px 내부 클립 + pane scrollHeight==clientHeight 로 스크롤 미발생. metadata-table-desc-fix 의 `.admin-meta-bootstrap-result` max-height:460px 제거는 옳았으나 flex-shrink 가 별도 클리핑 경로. headless Playwright 는 max-height:none 만 확인해 놓침 → **PB-0008 실브라우저가 적발(playbook 가치)**. **수정**: `.admin-meta-bootstrap { flex-shrink: 0 }`(+근본원인 주석) → 자연높이 보존, pane overflow-y:auto 가 스크롤 담당. styles.css cache-buster bump(admin.html·index.html → `20260629-metadata-bs-flexclip`). 백엔드/JS/RBAC/스키마/마이그 0. **§18.8 적대 CSS 회귀 리뷰(5축) VERDICT: SAFE**(BLOCKING/NIT 0 — 셀렉터 격리·형제 안전·cache-buster 정합·문법 정상, 반증 실패). **완료**: verify-completion --pre-commit PASS(9) → commit `54dbfe3`(Task-Cycle) → push → main ff-merge(dad75c3→54dbfe3)·push → **web 재배포(deploy_scope: included)**: `docker compose build web` + `up -d --no-deps web`(repo-web-1 Up healthy, /healthz mysql_ok·pg_ok). **재배포본 PB-0008 재검증 PASS**: serve `styles.css?v=20260629-metadata-bs-flexclip`(admin/index) + baked `.admin-meta-bootstrap{flex-shrink:0}` + 하드 리로드 후 실 CSS 로 pane scrollHeight 2364(펼침)/1531(접힘)>clientHeight 684=스크롤 발생·17 테이블 전부 표시(스크린샷 40). 클리핑 해소 확정. worktree cleanup 완료. worktree `ai/claude/metadata-bootstrap-flex-clip-fix`(base dad75c3). REV-20260629T165743-metadata-bs-flexclip. **cycle 완료.**

---

**2026-06-29 TASK-20260629T141637-glossary-role-single-ui — 메타데이터 용어사전 역할 선택 UI 단일화(단일 역할 컨텍스트) + 등록 mis-scope 가드** (Minor §12.3 — 프런트 전용, RBAC/스키마/백엔드 무변경). resume: "용어사전 자동 등록 기능"은 완료·배포됐고, 배포본에서 사용자가 결함 2건을 보고. **결함①(역할 UI 2곳)**: 메타데이터 > 용어사전에 역할 선택 UI 가 두 곳(툴바 역할 필터 + 등록 폼 역할 select)이라 각 동작 식별이 어려움. **결함②(역할 미노출)**: 역할 드롭다운에 '전체 역할'·'공용'만 보이고 실제 `계정 > 역할`이 안 보임. **결정(AskUserQuestion)**: ①=단일 역할 컨텍스트(툴바 하나가 목록 필터+신규 등록 대상 결정, 폼 select 폐기), ②=권한 부여로 해결(코드 변경 없음 — `role.read` 게이트). **수정(①, 프런트 `admin.js`/`admin.html`)**: `_METADATA_FIELDS.glossary` 의 role_key roleselect 제거·죽은 렌더 블록·미사용 `_metaRoleOptions` 제거 → 툴바 `metadataRoleFilter` 가 유일 역할 UI. `_metaGlossaryTargetRole(editing)`(단일 진실원)이 role_key 주입(생성=컨텍스트/전체→공용 '*', 수정=기존 보존). 읽기전용 '등록 대상 역할' 배지+노트. cache-buster `?v=20260629-glossary-role-single-ui`. **§18.8 적대 패널 3-agent(2-lens+재검증)**: BLOCKING 2 흡수 — F2(등록/수정 성공 토스트에 대상 역할 표기, mis-scope 사후 인지) · F5(툴바 역할 변경 시 배지 stale 해소, 폼 입력 보존). NIT 흡수 F1(‘전체 역할’→공용 귀속 노트)·로직 헬퍼화. 재검증 VERDICT 클린. **알려진 trade-off(F3, 수용·고지)**: 폼 select 제거로 용어 역할 이동(공용↔역할) 직접 편집 UI 소실(백엔드 PUT 은 지원, 재등록 경로는 glossary_relations 미승계) — 이동 필요 시 후속 affordance. **비변경**: 백엔드·RBAC·스키마/마이그·목록 배지·유사어·검토 큐. **검증**: node --check PASS · 적대 패널 클린 · Windows 브라우저(PB-0008) 라이브 렌더 후 완료 선언 · web 재배포(deploy_scope: included). worktree `ai/claude/glossary-role-single-ui`(base 3dfe81c). **결함②**: 코드 외 — 용어사전 관리 역할/계정에 `role.read` 권한 부여 시 실제 역할 노출(사용자 안내). **잔여**: verify-completion → 머지·push → web 재배포 → 라이브 검증. REV-20260629T141637-glossary-role-single-ui.

---
**2026-06-29 TASK-20260629-metadata-bs-collapse — 메타데이터 부트스트랩 결과 패널 접기+검색 재설계 + 잘림(cache-buster) 근본수정** (**Major §12.3** — feature-0003 프론트 단독). 사용자 보고(metadata-bootstrap-mssql-db 배포 후속): (1) 스키마 골격 펼침 시 패널 내부 UI 가 여전히 잘려 각 테이블 확인 불가, (2) 다수 테이블 시 여백 과다. **진단**: (1) 잘림은 직전 metadata-bootstrap-mssql-db 가 `styles.css` 의 `.admin-meta-bootstrap-result` 460px 캡을 제거·서버 배포까지 했으나 `admin.html` 의 `styles.css?v=`/`admin.js?v=` cache-buster 미bump → 브라우저가 stale CSS(캡 생존) 로드(서버 반영, 미전파). 이전 cycle 의 cache-buster 누락이 근본원인. (2) 결과가 수백 테이블을 전부 펼쳐 평면 렌더. **수정(사용자 AskUserQuestion — 재설계 방향=접기+검색/필터)**: cache-buster bump(admin.html 2종 + index.html `styles.css` → 20260629-metadata-bs-collapse) + 부트스트랩 결과 재설계 — 테이블별 기본 접힘 한 줄 헤더(button: caret+이름+입력상태 힌트)·클릭 토글, 테이블명 검색 필터·모두펼치기/접기·`표시/전체` 카운트, 결과 gap 10→4px 조밀화. 접기·필터는 시각 토글(class/`display`)만 → 입력값 DOM 보존, 저장(`_metaBootstrapSave`)·AI 일괄생성(`_metaBootstrapApplyDescriptions`)·apply 가 descendant 셀렉터로 접힌/필터된 입력까지 전체 수집(회귀 0). **검증**: node --check PASS. §18.8 적대 frontend 패널(value-loss·state-machine·XSS·AI-fill·binding·edge·max-height 7축) BLOCKER 0·diff CLEAN, MINOR(모두펼치기 라벨 desync) 수정 흡수(`allExpanded` 상태 제거→DOM 기준 동기화), MAJOR(tables↔columns 서브탭 전환 시 부트스트랩 미재렌더 mode 불일치)는 pre-existing·scope 밖 수용(follow-up 권고). 백엔드/route/스키마/RBAC/마이그 0. worktree `ai/claude/metadata-bootstrap-collapse-search`(base 3dfe81c). **잔여**: verify-completion → 머지·push → web 재배포(cache-buster 반영) → PB-0008 Windows 브라우저 검증. REV-20260629T142631-metadata-bs-collapse.

**2026-06-29 TASK-20260629T120711-attach-id-space — 첨부 영속 레이어에 message_id_space 추가 (H5(b) follow-up 완결)** (**Major §12.3** — feature-0003 단독, 스키마 마이그 없음). 사용자 요청: "동일한 message.id 키를 쓰는 첨부 영속 레이어의 같은 이슈를 마저 처리." 선행 TASK-20260629T022055-feedback-id-space(피드백 레이어 H5(b) 해소)가 REVIEW '잔여'로 별도 feature 에 미룬 첨부 레이어를 동일 패턴으로 완수. **문제(H5(b) 첨부)**: `_load_assistant_attachments_by_message`(MetaJson.message_id 단일 키 그룹핑)·`_attach_assistant_attachments`(메시지 id 단일 키 매칭)가 message.id 두 IDENTITY 공간(표시 store `agent_runtime.messages.id` vs core `core_messages.id`) 숫자 겹침에 노출 → core 메시지가 같은 숫자의 display 첨부를 잘못 표시하는 wrong-bubble 가능. **수정**: id_space 차원 추가 → (message_id, message_id_space) 복합 키(`_attach_user_feedback` 와 대칭). materialize 가 MetaJson 에 `message_id_space="display"` 영속(message_id 출처 `_load_latest_assistant_message` 가 표시 store 전용 → 항상 display), 로더·attacher 가 복합 키로 그룹핑·매칭(미설정/legacy 행 'display' 간주). **비변경**: 프론트(서버가 채운 `_attachments` 렌더)·share·cache-buster·DB 스키마/마이그 0 → 정상 display 경로 동작 동일. **검증**: 대상 test_task0285 11/11(A3 cross-space·L4 core/display 분리 신규)·`make test` 전체 exit=0(두 feature 회귀 0)·ruff·py_compile. 적대 self-review(H5(b) 첨부 closure, stale int-key 소비자 0·join 테이블 범위 밖 확인). worktree `ai/claude/attach-id-space`(base 40c0de0). **잔여**: verify-completion → 머지·push → 배포(web 코드 재빌드, deploy_scope: included). REV-20260629T120711-attach-id-space.

---
**2026-06-29 TASK-20260629-glossary-review-nest — 용어 검토 큐 IA 중첩(메타데이터 > 용어사전 > 용어 검토 큐)** (**Minor §12.3**, 프런트 전용, feature-0003). 사용자 요청(/_template:entry): 검토 큐를 메타데이터 최상위 서브탭(전) → **용어사전 하위 2차 보기 탭**(후)으로 이동. **구현**: 최상위 서브탭에서 `glossary-review` 제거 → 용어사전 하위에 2차 보기 strip `#metadataGlossaryViews`(`용어 목록`/`용어 검토 큐`, `.admin-meta-gview` 필 스타일) + 내부 상태 `glossaryView`. 기존 `sub==="glossary-review"` 분기를 `_metaIsGlossaryReview()`(subTab==="glossary" && glossaryView==="review")로 치환(_metaRenderForm·loadMetadata·_metaSyncToolbarVisibility). 배지 `#glossaryReviewBadge` 를 review 보기 버튼으로 이전. **권한 보존 설계**: 용어사전 서브탭 = `_metaSubtabVisible`(kb.ingest.manual OR kb.glossary.curate, 중첩으로 인한 curate-only 접근 단절 방지), 2차 보기 `_GLOSSARY_VIEW_PERM`(목록=ingest.manual, 검토 큐=glossary.curate) + `_metaSyncGlossaryViews` 가 권한 없는 보기를 첫 표시 보기로 보정(curate-only → 자동 검토 큐, ingest-only → 자동 목록). 백엔드/route/엔드포인트 무변경. **적대 검증 워크플로(3 lens: 상태머신·권한·회귀, BLOCKER 0)**: MAJOR 1건(3 lens 동일근본) — 부모 `ADMIN_TAB_PERMISSIONS.metadata` 가 `kb.glossary.curate` 누락 → curate-only 사용자가 메타데이터 탭 자체에 진입 불가하여 내 OR 게이트가 dead path(변경 목표 무력화, pre-existing 갭이나 본 변경이 큐를 더 깊이 중첩). **수정**: 탭 게이트에 `kb.glossary.curate` 추가(서버 403 이 실경계 — backend `admin_list_glossary_feedback` 는 curate 단독 200, 표시 확장 안전). MINOR/NIT(메타 탭 재진입 strip/배지 sync, gview 이중 sync 제거, aria-selected) 전부 흡수. **검증**: node --check PASS, 잔여 functional `glossary-review` 참조 0, 백엔드/route/테스트 무변경. worktree `ai/claude/glossary-review-nest`(base 1d0ace4). 잔여: verify-completion → 머지·push → web 재배포. REV-20260629T120000-glossary-review-nest.

**2026-06-29 TASK-20260629T114221-metadata-bootstrap-mssql-db — 관리 콘솔 메타데이터 부트스트랩 MSSQL database 차원 미처리 수정 + 패널 잘림 해소 + 테이블 설명 AI 자동완성 정상화** (**Major §12.3** — cross-engine 골격 introspection, feature-0003 app.py·admin.js·admin.html·styles.css). 사용자 보고(/_template:entry): 메타데이터 > 테이블 설명에서 (1) 데이터소스·스키마별 테이블 설명 AI 자동완성 구성, (2) 테이블 명칭이 모두 올바르지 않은 값, (3) 패널 내부 공간 미확장으로 UI 내부 잘림(컬럼 설명 탭 동일). **진단**: (1) 의 AI 자동완성(단건 `tables/suggest`·일괄 `bootstrap/describe`)은 이미 구현돼 있었고, 핵심 결함은 **MSSQL 골격이 `tempdb` 임시테이블(`#…`)을 노출**한 것. 부트스트랩이 `database=None` 으로 연결 → `shared/db.py:_connect_mssql` 의 보안 설계(default_db 미지정 시 중립 tempdb 고정, 무자격 2-part 쿼리 차단)로 tempdb 연결 → 임시테이블 열거. 스키마 드롭다운도 sys.schemas raw 라 고정 역할 스키마 오염. MySQL 은 schema==database 라 원래 정상. table/column_descriptions DB 0행 → 저장목록 아닌 골격 경로 확정. **수정(설계: 사용자 AskUserQuestion — MSSQL은 server>db>schema>table 4계층을 3-키 모델에 schema_name=database 로 매핑)**: 부트스트랩 unit 을 엔진별 분기(MySQL=schema / MSSQL=database via `list_server_databases`, 시스템 DB/스키마·센티넬 필터) + MSSQL 골격은 선택 DB 로 연결해 비시스템 SQL 스키마 평탄수집(`_bootstrap_collect_skeleton_mssql`, 저장 schema_name=DB) + 단건 suggest grounding(`_metadata_introspect_table`) 동일 엔진분기 + 프론트 라벨 '데이터베이스/스키마' 분기 + `.admin-meta-bootstrap-result` max-height:460px 제거(pane overflow 와 이중 스크롤이 잘림 원인). **검증(라이브 전부 PASS)**: app 내부 introspection 직호출 + 실 HTTPS API(curl) + Playwright 브라우저 eval — MSSQL 129 실 DB(tempdb 없음)·GunzGame 88 실테이블(temp 0)·라벨 '데이터베이스 *'·maxHeight none·단건 suggest grounded(29컬럼). RBAC/스키마/마이그 0. worktree `ai/claude/metadata-table-desc-fix`(base 0f69e6d). PB-0008 Windows-browser 는 배포 후 사용자 확인 권장. REV-20260629T114221-metadata-bootstrap-mssql-db.

**2026-06-29 TASK-20260629T022055-feedback-id-space — 피드백 고유성 키에 id_space 추가 (H5(b) follow-up)** (**Major §12.3** — 스키마 마이그 0022 + cross-feature 0002+0003). 사용자 요청: 선행 TASK-20260629T014345-feedback-unique-vote 의 적대 리뷰가 수용·문서화한 H5(b) 잔여 한계 완수("확인된 후속 권고사항도 마저 완수"). **문제(H5(b))**: `/api/history` 의 `message.id` 가 표시 store(`agent_runtime.messages.id`)와 core fallback(`core_messages.id`) 두 독립 IDENTITY 공간서 올 수 있어(숫자 겹침), 0021 의 (created_by, message_id) 키가 fork·마이그 경로전환 시 (a) cross-space DB 충돌(다른 답변 같은 키 → UPSERT 가 남의 투표 덮음) (b) wrong-bubble 복원 가능. **수정**: 답변 식별에 **id_space**("display"|"core") 차원 추가 → 키 (created_by, message_id, message_id_space). `/api/history` 4개 빌더가 `m["id_space"]` 노출(core 빌더 2 + display 빌더 2), `_load_user_feedback_by_message`/`_attach_user_feedback` 가 (mid, space) 복합 키로 복원·매칭, `post_sample_feedback`·`record_feedback`·`app.js` 가 전 경로 일관 전달. 마이그 0022 + 부트스트랩 `agent_kb_schema.sql`: `message_id_space varchar(16) NOT NULL DEFAULT 'display'` + 3-col 부분 UNIQUE **신규명** `ux_sample_feedback_user_msg_space_vote`(구 2-col drop — same-name no-op trap 회피). 기본 'display' 라 하위호환(미전송 클라/기존 행 정합). cache-buster `?v=20260629b-feedback-id-space`. 잔여: 첨부 영속 레이어(동일 특성)는 별도 feature 범위. **검증**: flywheel 13/13(3-col ON CONFLICT·id_space 단언)·curation 15/15(id_space 전달)·두 feature 전체 회귀 0, py_compile·node --check·chain linear(0021→0022 단일 head). self-review(H5(b) closure). worktree `ai/claude/feedback-id-space-tag`(base 3ed6abb). **잔여**: verify-completion → 머지·push → 배포(0022 적용 + web 재빌드). REV-20260629T022055-feedback-id-space.

**2026-06-29 TASK-20260629T014345-feedback-unique-vote — 답변당 사용자별 고유 피드백(👍/👎) 강제 — 새로고침·대화 전환 후 중복 부여 차단** (**Major §12.3** — 스키마 마이그 + cross-feature: web `feature-0003`(app.py endpoint·history·app.js·styles.css·index.html) + core `feature-0002`(alembic 0021·sample_feedback.py)). 사용자 보고(/_template:entry): assistant 답변 피드백(👍/👎) 부여 후 다른 대화 전환·새로고침 시 같은 답변에 재부여 가능 — 답변당 고유 피드백만 가능해야 함. **결정(AskUserQuestion)**: 재투표 **변경 허용**(👍↔👎 전환, UPSERT last-write-wins, 답변당 1행). **진단**: 중복 차단이 두 계층 모두 부재 — ① 프론트 `_buildSampleFeedbackControls` 의 dedup 이 `data-done` DOM 플래그뿐이라 `renderMessages()` 재생성(새로고침·전환) 시 소실 + POST 가 답변 식별자 미전송, ② 코어 `record_feedback` 가 무조건 INSERT(테이블에 message_id·UNIQUE 부재, 마이그 0014). 답변은 표시 store `agent_runtime.messages.id`(= 프론트 `message.id`, 첨부 영속과 동일 id 공간)로 식별 → (created_by, message_id) 고유성 강제. **수정(5요소)**: **A** 마이그 0021 — `sample_feedback.message_id` + 부분 UNIQUE `ux_sample_feedback_user_msg_vote (created_by, message_id) WHERE message_id IS NOT NULL AND created_by IS NOT NULL AND suggested=false`(과거 행·익명·"샘플 등록" 제외 → 무손실·멱등). **B** `record_feedback` INSERT→UPSERT(`ON CONFLICT … DO UPDATE`)+`RETURNING id`(lastval 제거). **C** `post_sample_feedback` body `message_id` 파싱·전달. **D** `/api/history` 가 `_load_user_feedback_by_message`/`_attach_user_feedback` 로 assistant 메시지에 현재 사용자 투표(`m["feedback"]`) 주입 — 새로고침·전환 복원. **E** 프론트 POST 에 `message_id` 포함 + 기존 투표 활성표시(변경 허용, busy 가드만). **F** CSS `.is-active` + cache-buster `?v=20260629-feedback-unique-vote`. **가드**: D+E 가 UX 증상 차단, A+B 가 직접 API 포함 어떤 경로든 DB 계층에서 중복 권위 차단. "샘플 등록"(suggested=true)은 부분 인덱스 제외 → 검수 큐 동작 보존. **검증**: test_sample_flywheel 15/15(param 보정+ON CONFLICT/RETURNING 단언+신규 vote-UPSERT 키)·test_sample_feedback_curation 15/15(record 반환 id+message_id 전달) PASS, 두 feature 전체 스위트 회귀 0(`test_share_redaction_invariant` 는 컨테이너 전용 `web.app` import 라 로컬 한정 환경 실패, 본 변경 무관). `py_compile`(sample_feedback.py·app.py·0021)·`node --check`(app.js) PASS. 마이그 chain linear(0020→0021 단일 head). 적대 backend 리뷰(H1~H7) 동반. worktree `ai/claude/sample-feedback-unique-vote`(base 63874f2). **잔여**: verify-completion --pre-commit → 머지·push → 배포(마이그 0021 적용 동반 — deploy_scope 판정/confirm). REV-20260629T014345-feedback-unique-vote.
**2026-06-29 TASK-20260629-glossary-conv-autoreg — 용어사전 대화 자율등록 + 역할 분리 + 유사어 참조** (**Major §12.3**, cross-feature: core/migration/hook `feature-0002` + web/UI `feature-0003`, ADR-20260629T101500). 요청(/_template:entry): 「관리 콘솔 > 메타데이터 > 용어사전」이 사용자 대화로부터 assistant 판단 하에 자율 등록되도록 + ① 역할별 용어 비중복 ② 유사 의미 시 참조. 기존 용어사전(ITEM-10, kb_glossary)은 **수동 등록만·"자동학습 없음"(KB poisoning 방어, 의도된 거버넌스)** 이었다. **결정(AskUserQuestion)**: ① 등록 자율성 = **하이브리드 자동승급** — 대화 답변 직후 LLM(`llm_glossary_suggest`)이 용어 후보를 추론(`agent_core._glossary_autopropose` hook, best-effort·ask 비차단), `confidence ≥ 0.85` 면 **자동 등록(source='auto')** + `glossary_feedback`(auto_promoted) 감사 추적(되돌리기 가능), 미만은 **검토 큐**(pending)→권한 `kb.glossary.curate` 가 promote/reject. 라이브 반영 게이트(검수·되돌리기)를 유지해 기존 poisoning 거버넌스를 깨지 않고 "자율"을 충족(sample_feedback 플라이휠 패턴 재사용). ② 역할 분리 = `kb_glossary.role_key` 차원 추가, UNIQUE(scope_key,**role_key**,term)로 역할별 독립 namespace(겹침 방지), `role_key='*'`=공용; 읽기는 [현재 역할,'*']만 주입(타 역할 전용 용어 미노출); **자동 제안 기본 귀속=공용**(사용자 결정). ③ 유사어 = `glossary_relations`(synonym/similar/see_also, 역할 경계 횡단). **산출물**: 마이그 0023(role_key/source ADD·UNIQUE 재정의·glossary_feedback·glossary_relations·GRANT, 기존 행 backfill 동작 불변); 코어 `kb_glossary.py`(role read·하이브리드 라우터·검토 큐·관계·추론) + `llm.py`(GLOSSARY_SUGGEST_PROMPT) + `shared/config.py`(4 flag); web `app.py`(role_key 검증·검토 큐 3종·유사어 3종·권한 kb.glossary.curate·audit); 관리 UI `admin.html/admin.js/styles.css`(역할 select/배지/필터·검토 큐 서브탭·유사어 패널, XSS=textContent). **검증**: 코어 `test_kb_glossary_enum.py` 21 + 웹 신규 `test_metadata_glossary_autoreg.py` 13 + 기존 metadata 회귀 갱신 + route_snapshot 6 신규 라우트 갱신 → 전체 **1222 passed**(잔여 7 fail = `web.app` 컨테이너 레이아웃 의존, 본 변경 무관). ruff·py_compile·node --check·단일 alembic head PASS.

**2026-06-26 TASK-20260626-ask-dedup-idempotency — assistant 요청이 2번 중복 전송/처리되는 결함 수정 (worker-mode enqueue 멱등화)** (**Major §12.3** — /api/ask send/concurrency 라이브 경로, cross-feature: web `feature-0003`(app.py·app.js) + core `feature-0002`(ask_jobs.py)). 사용자 보고(/_template:entry): "서비스에서 assistant 에게 요청을 보낼 때 2번 중복되어 전송" — 명료화(AskUserQuestion): **요청도 2번·답변도 2번, 항상(첫 요청부터)**. **진단(코드+라이브 DB/로그 교차)**: 프론트는 `/api/ask` 를 sendPrompt(8320)에서 정확히 1회 POST(이벤트 이중바인딩·apiFetch 재시도 없음), 백엔드 enqueue 도 `_dispatch_ask_run_worker`(11321) 1곳뿐. 그러나 `agent_runtime.ask_jobs` 에 **동일 페이로드 job 2개**가 실측됨(conv 94b96f5f job148/149 Δ460ms, conv cbb5bde0 job153/154 Δ20s; 둘 다 attempts=1·done — requeue 아님). 단일 워커 직렬 처리 → 두 번째 run 의 user 메시지 재삽입이 ~1분 뒤 찍혀 "요청·답변 2회". **근본 원인(Caddy 로그 스모킹건)**: 워커 모드 `/api/ask` 는 run 종료까지 HTTP 연결을 수십 초~분 잡는데(in-handler long-poll attach), **web 컨테이너 재생성(배포/자동화)** 시 그 연결이 끊겨 `POST /api/ask` 가 24~109s 후 **502 EOF**(+`connection refused`·공인 IP 112.185.196.95 오해석 dial — docker DNS 갭 폴백). 끊기면 복구용 `/api/ask_status` 도 같은 불안정으로 실패 → 프론트가 in-flight run 을 못 보고 사용자가 **재전송 → 두 번째 job**. 첫 job 은 out-of-process 워커에서 살아남아 완료 → **답변 2개**. 워커 enqueue 에 **멱등성(dedup)이 전무**한 게 핵심 코드 결함. **수정(A+B+C, 사용자 AskUserQuestion=전체)**: **A(정본, ask_jobs.py)** `enqueue_ask_job(dedup_message=...)` — INSERT WHERE 에 `NOT EXISTS(같은 conv+account+user_message 의 pending/running)` 가드(INSERT 와 동일 statement = commit 된 중복에 atomic) + 신규 `find_active_dup_ask_job` 로 INSERT 억제 시 기존 job_id 반환; `_dispatch_ask_run_worker._enqueue` 가 사전 dedup 검사(기존 run 의 KV/run_id 보존 — sentinel 미덮어쓰기)→없으면 enqueue(dedup_message)→억제 시 재조회로 '슬롯가득(429)' vs '중복(기존 attach)' 구분. 중복이면 새 job 없이 기존 run 에 attach 해 동일 결과 동기 응답 → **메커니즘 무관(빠른 재발사·끊김 재시도 모두) 중복 차단**. **B(app.js retry-safety)** 기존 대화 `/api/ask` 실패 시 복구 status 조회를 0.7s×3 재시도 → web 일시 불안정에 in-flight run 을 안정 포착해 불필요 재전송 억제. **C(web 불안정 트리거)** 라이브 프록시/배포 인프라 변경은 blind 수정 위험이 커 원인 문서화로 처리(크래시 루프 아님 — RestartCount=0, 배포 재생성이 트리거; A 가 트리거 하에서도 중복 근절). **검증**: `test_ask_jobs.py` 신규 5건(dedup NOT EXISTS 절·param·suppressed None·find helper) 포함 **21/21 PASS** + `py_compile`(ask_jobs.py·app.py) + `node --check`(app.js) PASS. 스키마/RBAC/마이그 0(런타임 멱등 — 신규 컬럼·인덱스 없음, payload->>user_message 비교). worktree `ai/claude/ask-dedup-idempotency`(base 15ef5f4). **§18.8 적대 패널 SHIP-WITH-FIXES → 흡수 후 SHIP**(BLOCKER/MAJOR 0, MINOR 3 흡수: stale-running 제외·cache-buster bump·attachment-key accepted trade-off). **완료**: verify-completion --pre-commit PASS(9) → commit 721519b → main rebase(base-behind 483c4c0 doc-sync)+ff-merge(0818b0a) → origin push → **web+ask-worker 재빌드·재기동**(deploy_scope: included, 둘 다 Up healthy, baked dedup 코드 + `app.js?v=20260626-ask-dedup-idempotency` + healthz OK 확인). **배포 검증 중 라이브 PG 회귀 적발·즉시 HOTFIX**: dedup NOT EXISTS 가 `%(cid)s`/`%(account_id)s` 재사용 → PG `AmbiguousParameter(text vs character varying)` → 워커 모드 신규 /api/ask 전부 500날 회귀(단위 FakeConn 미포착, 라이브 enqueue 직접 실행으로 적발). 전용 파라미터 `%(dcid)s`/`%(daccount)s` + alias `d` 분리, 라이브 PG 수정 SQL 직접 실행 재검증 + 회귀 테스트 단언 추가 → 재빌드·재배포. **cycle 완료.** REV-20260626T134920-ask-dedup-idempotency.

**2026-06-26 TASK-20260626T025055-product-chip-always-enabled — 제품 선택 chip 을 요청 처리 중에도 항상 활성화** (**Minor §12.3** — frontend + backend PATCH 가드, TASK-0047 race 가드 완화, RBAC 무변경, ADR-WEB-0006). 사용자 보고(/_template:entry): assistant 에게 요청을 보낼 때(대화 "요청 처리 중") composer 제품 선택 chip(`#productChip`, 예: 'KR_QA')이 비활성화 — 이제 항상 활성화여야 함. **진단(적대 검증 subagent 가 ③ 적발)**: 차단이 세 계층(전부 TASK-0047 turn-immutability) — ① `renderProductChip()` busy→`chipEl.disabled`+`is-disabled`(`openProductDropup` 가드로 드롭업 차단), ② `setActiveProduct()` busy→토스트 후 변경 거부, ③ **백엔드 `PATCH …/product`(app.py:12370) `_conversation_is_processing`→409**. ①②만 풀면 owner 클릭이 409 토스트로 실패(활성처럼 보이나 동작 안 함)라 셋 다 제거. **수정**: `src/static/app.js` 2블록(renderProductChip busy 분기·setActiveProduct reject 가드 제거) + `src/app.py` `update_conversation_product` 409 가드+docstring 제거(권한·UPDATE·응답 shape 무변경) + `index.html` cache-buster `?v=20260626-product-chip-always-enabled`. **안전성(SUBAGENT VERDICT SAFE)**: 제품은 `/api/ask` 슬롯 후 1회 read(11676-11704)→run_kwargs baked(11995-12013)→worker payload 로 캡처, worker `_payload_to_kwargs`(ask.py:85-104)·`run_agent` 재조회 0, PATCH 단일 row UPDATE 부수효과 0 → 처리 중 변경은 진행 중 답변 비오염·데드락 없음·다음 요청부터 적용(토스트 문구와 정합). 409/race 가드는 데이터 정합성 아닌 보수적 UX 가드(손상 위험 0). **검증**: `node --check app.js`·`py_compile app.py`·`ruff check app.py`(All passed) PASS + 잔여 chip disable 신호 grep 0 + `isCurrentConvBusy` 타 용도(send/stop 5072) 무영향. 스키마/RBAC/마이그 0. 리뷰 REV-20260626T025055-product-chip-always-enabled [SUBAGENT:adversarial-product-race] 5축 반증 실패 SAFE. worktree `ai/claude/feature-0003-agent-web-ui`(base c11cc27). **완료**: verify-completion --pre-commit PASS(9) → commit f049fee → main ff-merge(c11cc27..f049fee) → origin push → web 재배포(deploy_scope: included, `sudo docker compose build web && up -d --no-deps web`). 배포 검증: `repo-web-1` Up healthy + baked index.html 서빙 `app.js?v=20260626-product-chip-always-enabled` + baked app.py 409 제거(grep 0) + web healthz OK, ask-worker 미재빌드(web-only). **cycle 완료.**

**2026-06-25 TASK-20260625-role-account-prompt-autogen — 역할 '전체 제품 프롬프트' + 프로필 '제품별 개인 프롬프트' 자동 작성** (**Major §12.3** — 외부 LLM dispatch 2개 scope 확장 + 역할 scope 교차사용자 대화 집계). 사용자 요청(/_template:entry): `관리 콘솔 > 역할 > 제품 사용 > 전체 제품 프롬프트` 와 `작업 화면 > 프로필 > 프롬프트 > [각 제품]` 의 자동 완성 구성 — 역할 성격·소속 사용자 대화 내역, 프로필은 역할·제품·대화 패턴 반영. **결정(AskUserQuestion)**: ① on-demand 버튼만(자율 sweep·자동저장 없음 — 개인 프롬프트 무동의 생성·비용 회피) ② 기능만 구성(seed 라이브 생성은 운영자). **진단**: 제품 자동작성(TASK-0309/0237)은 `scope='product'` 에만 존재 — 요청한 두 위치(`scope='role'` 전체 제품 프롬프트·`scope='account'` 제품별 개인 프롬프트)는 수동 입력만. 합성 순서는 agent-core `compose_system_prompt`(global→product→role→account)가 이미 처리. **구현(`src/app.py`)**: ① `_collect_conversation_signals_pg`(topic·summary 수집을 product_id/account_ids 필터로 일반화, 빈 account_ids→PG 미접근 누출 가드) ② `_describe_role_character`(권한코드→성격 서술) ③ `_assemble_role_prompt_llm_request`(역할 성격+소속 계정 대화 패턴+접근 가능 제품) ④ `_assemble_account_prompt_llm_request`(역할+제품 용도+본인 대화 패턴, 개인 선호 레이어=스키마 미중복) ⑤ 공유 응답 헬퍼 `_prompt_generate_json_response`/`_prompt_generate_stream_response` 추출(제품 엔드포인트도 리팩터, SSE 브릿지 중복 제거) ⑥ 엔드포인트 4종 `POST|GET /api/admin/roles/{id}/prompt/generate[/stream]`(admin) · `POST|GET /api/auth/me/system-prompt/generate[/stream]`(self+product access). **정적**: admin.js `buildSystemPromptEditor` `autoGenerateRoleId` + 역할 카드 '자동 작성' 버튼 + scope-aware meta; index.html `#generatePromptBtn` + app.js `generateAccountPrompt()` SSE. **privacy**: 모든 scope 가 원문 아닌 집계 메타(제목·요약)만 사용(제품 경로 house style), role=owner_account_id 필터+admin 게이트, account=본인만 + LLM 토큰 quota 게이트. 스키마/RBAC 카탈로그 변경 0. **§18.8 적대 패널(2렌즈) SHIP-WITH-FIXES ×2 → 흡수**: MAJOR-1(account 자동작성 quota 우회 → `_check_account_token_quota`=429) · MAJOR-2(프로필 에디터 dirty 가드로 자동작성 본문 제품전환 소실 방지) + MINOR(재진입 가드·`.helper-text-warn`) + NIT(스크롤 보존); 반증 실패=안전(IDOR 없음·빈 account_ids PG 미접근·SQLi 없음·리팩터 byte-equivalent). **검증**: `test_auto_role_prompt.py`(7)·`test_auto_account_prompt.py`(5) 신규 + 회귀(product prompt 12·stream 3·truncation 4) = **33/33 PASS**(agent 이미지) + `py_compile`·ruff(app.py)·`node --check` admin.js/app.js·CSS brace(1572/1572) PASS. 정적 캐시버스터 `?v=20260625-role-account-prompt-autogen`(index/admin × styles/app/admin.js). worktree `ai/claude/role-account-prompt-autogen`(base 7e6aab8). **완료(진행)**: verify-completion --pre-commit → 머지 → web 재배포(deploy_scope: included, static baked) → PB-0008 Windows-browser 실렌더(역할 카드·프로필 자동작성 버튼·SSE 스트리밍, WARN-only). REV-20260625T173000-role-account-prompt-autogen.

**2026-06-25 TASK-20260625T020249-admin-metadata-relocate — 관리 콘솔 사이드바 IA: '메타데이터' 탭을 '감사' 그룹에서 신설 '지식베이스' 그룹으로 재배치 (+ '샘플 검수' 동반 이동)** (REV-20260625T020249-admin-metadata-relocate [SUBAGENT:adversarial-3lens-PASS] **SHIP**, **Minor §12.3** — 정적 DOM 재배치, `src/static/admin.html` only). 사용자 요청(`/_template:entry`): '메타데이터' 탭이 '감사'에 위치하는 게 어색 — `시스템 > 설정 > 메타데이터` 이동 검토·적용 + 더 좋은 구조도 검토. **IA 결정(AskUserQuestion)**: 사용자 원안('시스템' 그룹 이동) 대신, KB 거버넌스 성격인 메타데이터(kb.ingest.manual)+샘플 검수(kb.sample.curate)를 신설 '지식베이스' 그룹으로 묶고 '감사'를 순수 모니터링(감사 로그·LLM 사용량·보관 대화)으로 정리. **구현**: `admin.html` nav 에서 metadata/sample-review 버튼을 '감사' 그룹에서 제거 → '시스템' 그룹 직전 신설 `admin-tab-group-divider`+`<div class="admin-tab-group-label">지식베이스</div>` 아래로 메타데이터→샘플 검수 순 재배치(버튼 속성 보존). 최종 순서: 대시보드 → 계정 → 제품 → 감사 → **지식베이스** → 시스템. **회귀 0**: admin.js 탭 가시성(`applyAdminTabVisibility` DOM순서 동적)·권한 게이팅(`ADMIN_TAB_PERMISSIONS` 키)·pane 매칭(`switchTab` data-admin-pane)·클릭 바인딩(data-admin-tab) 전부 그룹 위치 비의존 → JS/CSS/RBAC/스키마/pane 본문 무변경. **검증**: diff(admin.html 11+/5-) + §18.8 적대 3-렌즈 서브에이전트 **BLOCKER/MAJOR 0 SHIP**(MINOR 1: 사이드바 '지식베이스' vs 권한그리드 `kb:"지식베이스(KB) 검수"` 용어 미세 불일치 — 후속 통일 추적). worktree `ai/claude/admin-metadata-relocate`(base 2a73c64). **완료(진행)**: verify-completion --pre-commit → 머지 → web 재배포(deploy_scope: included, static baked) → PB-0008 Windows-browser UI 실렌더(배포 후, WARN-only). REV-20260625T020249-admin-metadata-relocate.

**2026-06-25 TASK-0309 — 제품 insight 분석률 95% 도달 시 제품 프롬프트 무인 자동완성 (1회성)** (**Major §12.3** — 자율 LLM(Bedrock) dispatch + 자율 DB write, REVIEW REV-20260625T161500-auto-product-prompt). 사용자 요청(/_template:entry): `관리 콘솔 > 제품`에서 '제품 프롬프트' 미입력 제품을 대상으로 분석률이 95% 넘는 순간 자체적으로 자동완성·저장 + 임의 insight 초기화로 재상승해도 1회성으로 미재실행. **결정(AskUserQuestion)**: 전용 worktree(`ai/claude/auto-product-prompt`, base 262a065) + 백그라운드 주기 sweep(관리자 미접속에도 무인 동작). **구현(`src/app.py` 단일 파일)**: ① 1회성 마커 `WebProducts.AutoPromptGeneratedAt`(멱등 ALTER) — insight reset(PG만 삭제)을 견딤 ② `_collect_product_prompt_context` 인증 게이트에서 request-less 조립 코어 `_assemble_product_prompt_llm_request` 분리(엔드포인트 blast-radius 0) ③ `_autonomous_generate_product_prompt`(조립→동기 LLM→마커 FOR UPDATE 잠금+재검사→upsert(system)+마커+audit 를 autocommit=False 명시 tx commit) ④ `_auto_prompt_sweep_once`(미입력 우선검사→backoff→coverage 캐시→`pct>=임계`→cycle 상한→생성) ⑤ `_start_auto_prompt_sweep_loop` daemon thread(`AGENT_AUTO_PROMPT_SWEEP_SEC` 기본 180·0=비활성, `_start_db_rule_reconcile_loop` 패턴). 임계 `AGENT_AUTO_PROMPT_COVERAGE_THRESHOLD` 기본 95.0. 수동 '자동작성' 버튼 무변경 보존. **적대 리뷰(REV-20260625T161500-auto-product-prompt) BLOCKER 1 + MAJOR 2 흡수**: B1(autocommit=True → 명시 tx + FOR UPDATE 로 1회성 불변식 부분실패 보호) · M1(실패 backoff `AGENT_AUTO_PROMPT_FAIL_BACKOFF_SEC` 기본 3600) · M2(cycle 상한 `AGENT_AUTO_PROMPT_MAX_PER_CYCLE` 기본 3); MINOR(record_llm_usage 우회=수동경로 동일 기존갭 등) 수용. **검증**: `tests/test_auto_product_prompt.py` 12/12 PASS(T3=reset 생존·T10=마커 UPDATE 실패 rollback·T11=backoff·T12=cycle 상한 회귀 가드 포함) + `test_insight_coverage.py` 5/5 무회귀 + `py_compile` + ruff PASS. ANCHOR §1~§3 충돌 없음(System Prompt 가 web-ui 거주 — 계층 정합). **완료(진행)**: verify-completion → 머지 → web 재배포(deploy_scope: included) → 라이브 확인.

**2026-06-24 TASK-20260624-scope-key-unify — 메타데이터/샘플 admin scope_key 축을 질의 read 축으로 통일 (ds-scoped 死data 수정)** (REV-20260624T160000-scope-key-unify [SUBAGENT:scope-key-unify-review] **SHIP**, **Major §12.3** — scope 경계, ITEM-10/11/03 공유 admin 경로). **발견**: `/_template:resume` 의 ITEM-11 Phase 2 작동검증 중 구조 감사(4 dim)가 scope-key 축 불일치 死data 적발 — admin write=datasource 라벨, 질의 read=엔드포인트 해시(`get_active_datasource`)라 DB-등록 ds 의 ds-scoped 설명/샘플이 'common' 외 영영 안 읽힘. 라이브 재현 확정(라벨 'mysql-local' 저장 → 해시 읽기 len 0). 이 배포 DS 20+ 전부 WebDatasources(.env 0), KB 테이블 0행(잠복). **수정**: write 측(`_metadata_valid_scope_keys`·`/api/admin/datasources` scope_key·admin.js 드롭다운)을 read 와 동일식 `ds.get('scope_key') or ds.get('key')`(DB=해시·.env=라벨)로 통일 + 탭 게이트 OR(kb.sample.curate)·bootstrap source='bootstrap'. read(feature-0002) 무변경. **적대 검증**: 첫 fix(`_dsr.scope_key`)의 .env 축 반전 BLOCKER 패널 적발 → 교정(read 동일식) → 재확인 agent RESOLVED(7항목). **검증**: phase2 29(양방향 scope 회귀 2 신규)+glossary/enum 13+flywheel 12 PASS, KB 0행(orphan 없음·백필 불요). worktree base 73bc222. **완료(진행)**: verify-completion → 머지 → web 재배포(deploy_scope: included) → 死data 수정 라이브 재검증. **MINOR(out-of-scope)**: insight_health 의 .env ds 키 불일치(TASK-0255 pre-existing). REV-20260624T160000-scope-key-unify.

**2026-06-24 TASK-20260624-item11-phase2 — 메타데이터 거버넌스 포탈 Phase 2: 테이블/컬럼 설명 사전 + KB 주입/overlay + 스키마 부트스트랩 + 샘플 admin (ROADMAP dba-ai-nl2sql ITEM-11 Phase 2 → ITEM-11 done)** (REV-20260624T133000-item11-phase2 [SUBAGENT:item11-phase2-backend+security+injection] **SHIP**, **Major §12.3** — 신규 RBAC 표면+KB 주입 경로 신설+부트스트랩 introspection, cross-feature: web `feature-0003`(app.py +747·admin.{html,js}·styles.css) + core `feature-0002`(kb_metadata.py 신규·sample_queries·agent_core·tools·agent_kb_schema.sql·alembic 0017)). MVP-1(용어/ENUM CRUD)에 이어 ITEM-11 잔여 완성. **범위**: PLAN-APPROVED 2a+2b 한 컷(D1 신규테이블·D2 B+A 주입/overlay·D3 curate+하이브리드 C). **구현**: ① 신규 PG `table_descriptions`/`column_descriptions`(alembic 0017 멱등·단일 head·GRANT) + `kb_metadata.py` read/overlay/admin CRUD(id+scope_key 가드) ② `_build_knowledge_context` datamark 주입 + `describe_table` native-빈 컬럼 overlay ③ admin 메타데이터 탭 3 서브뷰 + RO 부트스트랩 UI(미영속) ④ 샘플 admin 검수(POST 없음)+하이브리드 C 임베딩. **비변경**: 기존 sample register/search·MVP-1 glossary/enum·core/tools 경로(순수 additive, 삭제 0). **검증**: phase2 27/27 + MVP-1 회귀 13/13 + sample_flywheel 회귀 12/12 PASS, py_compile + node --check(admin.js) + alembic 단일 head 확인. §18.8 적대 패널 2회(1차 SHIP-WITH-FIXES — B1 부트스트랩 SQLi + M2 alembic 위치 흡수 / 2차 resume 재검증 3-lens 전원 SHIP·BLOCKER 0). worktree `ai/claude/feature-0003-agent-web-ui`(base b652dc1). **완료(진행)**: verify-completion --pre-commit PASS → 머지(PR) → web+ask-worker 재배포(deploy_scope: included, 마이그 0017 superuser 적용+GRANT) → healthz/smoke. **PB-0008 Windows-browser UI 시각검증은 배포 후 수동(WARN-only)**. REV-20260624T133000-item11-phase2.

**2026-06-23 TASK-20260623T031910-ds-conn-bg-decouple — 관리 콘솔 > 제품: 데이터소스 연결확인을 동기 render 경로에서 백그라운드로 분리** (Major §12.3, backend `src/app.py`(3 async 경로) + frontend `src/static/{admin.js,styles.css}`). 사용자 요청(/_template:entry): `관리 콘솔 > 제품 > [각 항목]` 진입 시 연결 불안정 데이터소스 접근 시 timeout 까지 나머지 UI 갱신이 멈춤 → 모든 연결 확인을 백그라운드로, 내부 UI 갱신과 분리. **범위(AskUserQuestion)**: 전체 분리(Layer 1+2). **진단**: `admin_datasource_databases`(제품 항목 진입 경로)가 `async def` 안에서 동기 `_db.list_server_databases_classified()`(live connect 8s)를 `asyncio.to_thread` 없이 호출 → **이벤트 루프 전체 8s 블록 = 모든 요청 정지**. preview + rule create/update reconcile 도 동일. 백그라운드 `conn_health`(TASK-0250 캐시 3-state)를 이 경로가 미사용 + `should_fast_fail` 은 `down` 만 즉시실패·`unstable` 은 8s 대기. **수정**: ① backend — `admin_datasource_databases` 가 `conn_health.status_for(ds)` 캐시 먼저 읽어 unstable/down 이면 connect 생략·`{degraded:true}` 즉시 반환(`?force=1` 시만 실제 열거), 실제 열거·preview·reconcile 모두 `await asyncio.to_thread(...)` 오프로드 + 실패 `record_foreground_result` 피드백. ② frontend `admin.js` — `_refreshAccessibleDbs(key,{force})` 가 `degraded` 응답 시 `_setAccessDbDegraded` 배너("연결 불안정/끊김 — DB 목록 보류 + [새로고침]" → `?force=1` 재시도), 제품 상세 즉시 렌더(fire-and-forget) 유지. ③ `styles.css` 배너. **비변경**: `_reconcile_one_db_rule` 내부(M3/M4/M5)·RBAC·스키마·엔드포인트 shape·conn_health 모듈·`/db-insights`(sync def, 이미 threadpool) 0(필드 `conn_status`/`degraded` 추가만). **검증**: `py_compile app.py` + `node --check admin.js` + CSS brace balance + conn_health web startup(`@app.on_event("startup")`) 와이어링·`scope_key` 정합 확인. worktree `ai/claude/ds-conn-bg-decouple`(base 14d8b13). **완료**: verify-completion --pre-commit PASS(9) → 머지(PR #374, main `b2236fe`; base-behind rebase 충돌해소 admin.html·FUNCTION.md keep-both) → web 재배포(deploy_scope: included, repo-web-1 Up healthy, 서빙 `admin.js?v=20260623-ds-conn-bg-decouple`·conn_health 게이트·to_thread baked) → **PB-0008 Windows-browser PASS**(실 Chrome/149: ①이벤트 루프 비차단 — down `?force=1` **8024ms** 블록 중 동시 healthy **44ms** 완료 ②degraded fast-path 38ms `degraded:true` ③healthy 무회귀 db14 ④시각 배너 "데이터소스 연결 끊김 — DB 목록 로드를 보류했습니다…"+[새로고침](`role=status`, 제품95 건즈국내QA) ⑤force 버튼 disabled→"확인 중…"→재활성). evidence `artifacts/pb0008-ds-conn-bg-decouple/{degraded-banner-down-ds,healthy-product-no-banner}.png`. **cycle 완료.** REV-20260623T031910-ai-claude-ds-conn-bg-decouple.

**2026-06-19 TASK-20260619T120000-db-rule-pending-batch — 관리 콘솔 > 제품 > 정규식 자동 규칙: 즉시 반영을 pending → "모두 적용" 으로 재배선** (REV-20260619T120000-ai-claude-db-rule-pending-batch, **Major §12.3 — 보안 경계**, frontend `src/static/{admin.js,styles.css,admin.html}` + backend `src/app.py` + 신규 `tests/verify_db_rule_pending.mjs`). 사용자 요청(/_template:entry): 관리 콘솔 내 모든 변경은 pending 후 일괄적용으로 구성되도록 정책에 검증과정 명시 + 프로젝트 메모리 기억. 보고된 위배: `관리 콘솔 > 제품 > [각 제품] > '데이터 소스 & 접근 가능 데이터베이스' > 정규식 자동 규칙` 수정 시 별도 Pending 없이 즉시 반영. **범위 결정(AskUserQuestion)**: 범위 A — 규칙 편집 동작만 pending, 확정 규칙의 백그라운드 자동 동기화는 보존. **진단**: 규칙 에디터(`cov-db-rule`)의 add/edit/delete/approve 핸들러가 클릭 즉시 `apiFetch(…/db-rules)` → 즉시 reconcile → allowlist 즉변 + GET `/db-rules` 가 `trigger="view"` lazy reconcile 로 조회만으로 GRANT → 전역 pending → "모두 적용" 모델 우회. **수정**: ① `admin.js` — `adminState.pending.productDbRules`(키 `productId::dsKey`, ops creates/updates/deletes/approves) + helpers + `pendingChangeCount`/`refreshPendingUI`/`buildPendingWidgetBody`/`cancelAllPending`/stale GC 통합 + 규칙 에디터 핸들러 스테이징 재배선 + 카드 optimistic 오버레이(추가/수정/삭제/승인 대기 배지·취소) + `applyAllPending` replay(creates→updates→approves→deletes, 성공 시 엔트리 정리). ② `styles.css` staged 배지. ③ `admin.html` 캐시버스터 `?v=20260619-db-rule-pending`. ④ `app.py` GET `/db-rules` view-trigger reconcile 제거(조회=무변경). **비변경**: rule reconcile/preview 로직·백그라운드 동기화 루프(확정 규칙)·RBAC·스키마·엔드포인트 shape 0. 정책 `CONVENTIONS.md §10.7` 신설 + 프로젝트 메모리 `project_admin_pending_batch_apply.md`. **검증**: `node -c admin.js` + `py_compile app.py` + CSS brace balance(1417/1417) + 신규 `tests/verify_db_rule_pending.mjs` **jsdom 18/18 PASS**(스테이징 시 쓰기 0 / "모두 적용"만 쓰기 / 엔드포인트·body·순서·정리·no-op guard) + make test 컨테이너 회귀 확인. worktree `ai/claude/db-rule-pending-batch`(base 28e76d6). **잔여**: verify-completion --pre-commit → 머지 → web 재배포(deploy_scope: included) → PB-0008 Windows-browser 시각검증(대기 배지 + "모두 적용" 일괄 반영 + 조회만으로 미반영). REV-20260619T120000-ai-claude-db-rule-pending-batch.

**2026-06-18 TASK-20260618T025220-ds-acc-collapsed-default — 관리 콘솔 > 제품: 제품 선택 시 접근 가능 DB 목록 기본 접힘** (REV-20260618T025220-ai-claude-ds-acc-collapsed-default [SKIPPED:frontend-ui-default-value-no-backend-no-rbac], **Minor §12.3**, frontend-only `src/static/admin.js` 1줄 + `admin.html` 캐시버스터 + `tests/verify_ds_accordion_collapse.mjs` 단언 반전). 사용자 요청: 기본적으로 제품 항목을 선택했을 경우 데이터베이스 목록이 접혀 있도록(REQ-20260618-0314 접기 토글 후속 — 토글은 됐으나 기본 펼침이었음). **수정**: datasource accordion 접힘 상태 `_dsBodyCollapsed`(렌더 함수 클로저) 초기값 `false`(펼침) → `true`(접힘). `renderProductDetail` 이 제품 상세를 열면 편집 대상 datasource 의 DB 편집기(`.ds-acc-body`)가 접힌 채 시작(caret ▸·aria false·is-active 해제·title "클릭하면 펼쳐서 DB 편집") → 하단 UI 바로 접근. 머리 클릭 토글·다른 datasource 전환 시 자동 펼침(`_switchEditDs`/`_afterBindChange` 의 `false` 리셋)은 불변(REQ-0314 보존). **비변경**: 백엔드·RBAC·스키마·엔드포인트·데이터·CSS 0. 캐시버스터 `?v=20260618-ds-acc-collapsed-default`. **검증**: `node -c admin.js` + `tests/verify_ds_accordion_collapse.mjs` **19/19 PASS**(초기 접힘·클릭 펼침·재클릭 접힘·하단 버튼 도달). worktree `ai/claude/ds-acc-collapsed-default`(base da227eb). **완료**: verify-completion --pre-commit PASS(9 checks) → 머지(PR #328 merge, main `1ad1519`) → web 재배포(deploy_scope: included, repo-web-1 Up·mysql_ok·pg_ok, 서빙 `admin.js?v=20260618-ds-acc-collapsed-default`·`let _dsBodyCollapsed = true` baked 1 hit) → **PB-0008 Windows-browser PASS**(실 Chrome/149, bootstrap_admin·단일 datasource 제품 KR `mysql-local`: 선택 직후 **클릭 없이** `.ds-acc-body` 미생성·caret ▸·aria false·행 유지·하단 '+ 데이터소스 추가' viewport 내 도달 = 기본 접힘 실증 → 머리 클릭 펼침[body 생성·caret ▾·picker 버튼] → 재클릭 접힘 토글 무회귀). evidence `artifacts/pb0008-ds-acc-collapsed-default/default-collapsed-on-select.png`. CHG/REV-20260618T025220-ai-claude-ds-acc-collapsed-default, evidence CHG/REV-20260618T025848-ai-claude-ds-acc-collapsed-default-evidence.

**2026-06-18 TASK-20260618T022150-ds-acc-collapsible — 관리 콘솔 > 제품: 펼쳐진 데이터소스의 접근 가능 DB 목록 접기 가능하게** (REV-20260618T022150-ai-claude-ds-acc-collapsible [SKIPPED:frontend-ui-presentation-toggle-no-backend-no-rbac], **Minor §12.3**, frontend-only `src/static/admin.js` + `admin.html` 캐시버스터 + 신규 `tests/verify_ds_accordion_collapse.mjs`). 사용자 요청: `관리 콘솔 > 제품` 탭에서 펼쳐진 데이터소스의 접근 가능 데이터베이스 목록을 접을 수 있게 — 데이터소스가 하나뿐일 때 DB 목록이 안 접혀 하단 UI(데이터소스 추가·제품 프롬프트·삭제) 접근이 번거로움. **진단**: "데이터 소스 & 접근 가능 데이터베이스" accordion(TASK-0238, `_renderDsAccordion`)의 행 머리(`.ds-acc-head`) 클릭이 `_switchEditDs(key)` 만 호출하는데 `_switchEditDs` 가 `nk === _editDsKey` 이면 early-return(admin.js:6526~) → 이미 편집 대상인 행 재클릭 무반응 = 접기 불가. 단일 데이터소스는 항상 편집 대상이라 `.ds-acc-body`(접근 DB 편집기) 영구 펼침. **수정**: 렌더 함수 클로저 `let _dsBodyCollapsed = false`(기본 펼침=기존 동작 보존) + `_renderDsAccordion` 에서 `isActive`→`isEditTarget`(키 일치)·`isExpanded`(= isEditTarget && !_dsBodyCollapsed) 분리(is-active·aria-expanded·caret ▾/▸·body 생성·head title 모두 isExpanded 기준) + head 클릭이 이미 편집 대상이면 `_dsBodyCollapsed` 토글·재렌더, 아니면 `_switchEditDs` 전환 + `_switchEditDs`·`_afterBindChange`(편집대상 제거 분기)에서 `_dsBodyCollapsed=false` 리셋(전환/이동 시 자동 펼침). **비변경**: 백엔드·RBAC·스키마·엔드포인트·데이터·CSS 0(접힌 행=기존 비활성 행 렌더). 캐시버스터 `?v=20260618-ds-acc-collapsible`. **검증**: `node -c admin.js` + 신규 `tests/verify_ds_accordion_collapse.mjs` **19/19 PASS**(jsdom — 초기 펼침 회귀 없음·토글1 접힘[body 제거·is-active 해제·aria-expanded false·caret ▸·행 유지·하단 '+ 데이터소스 추가' 도달]·토글2 재펼침). worktree `ai/claude/ds-acc-collapsible`(base 65930a5). **완료**: verify-completion --post-commit PASS(9 checks) → 식별자 충돌(타 세션 TASK-20260618T021526 가 REQ-0313/AC-0570 선점)→**REQ-0314/AC-0571 재번호 + rebase(admin.html 캐시버스터·TASK/FUNCTION append keep-both)** → 머지(PR #323 merge, main `9069518`) → web 재배포(deploy_scope: included, repo-web-1 Up·mysql_ok·pg_ok, 서빙 `admin.js?v=20260618-ds-acc-collapsible`·`_dsBodyCollapsed` baked 10 hit) → **PB-0008 Windows-browser PASS**(실 Chrome/149, bootstrap_admin·**단일 datasource 제품 KR(id=1, `mysql-local`)** = 사용자 보고 시나리오 정확 일치: 초기 펼침[body display:block·is-active·aria true·caret ▾, '+ 데이터소스 추가' top 912px > viewport 836px = 화면 밖] → 데이터소스 머리 클릭 접힘[`.ds-acc-body` 제거·데이터소스 행 유지·is-active 해제·aria false·caret ▸·title "클릭하면 펼쳐서 DB 편집", '+ 데이터소스 추가' 912→685px viewport 내 진입 = 하단 UI 도달] → 재클릭 재펼침[body 재생성·caret ▾·title "클릭하면 접기"] 토글 사이클 PASS). evidence `artifacts/pb0008-ds-acc-collapsible/ds-acc-collapsed.png`(접힌 `▸ mysql-local` + 삭제 버튼 화면 내). CHG/REV-20260618T022150-ai-claude-ds-acc-collapsible, evidence CHG/REV-20260618T024209-ai-claude-ds-acc-collapsible-evidence.

**2026-06-18 TASK-20260618T010417-date-group-collapse — 작업 화면 좌측 대화목록 첫 진입 시 최근 일자 그룹만 펼침** (REV-20260618T010417-ai-claude-date-group-collapse [SKIPPED:frontend-ui-entry-defaults-no-backend-no-rbac], **Minor §12.3**, frontend-only `src/static/app.js` + `index.html` 캐시버스터 + 신규 `tests/verify_date_group_collapse.mjs`). 사용자 요청: 서비스를 처음 진입할 때 `작업 화면 > 좌측 대화목록` 에서 가장 최근 일자 그룹을 제외한 나머지 오래된 일자 그룹은 접힌 상태로. **사용자 결정**(AskUserQuestion): "처음 진입" = 매 페이지 진입(reload)마다 재적용 — 날짜 그룹 키(`__today__`/`__yesterday__`/`YYYY-MM-DD`/`__other__`)가 상대적이라 타 계정 그룹의 영구 1회 seed 패턴은 다음 날 무의미. **진단**: 내 대화 날짜 그룹 접힘은 `state.collapsedDateGroups`(localStorage `mad.collapsedGroups.v1`)로 결정되는데 첫 진입 시 오래된 그룹 키가 set 에 없어 전부 펼침이 기본(app.js `renderConversationList` ~L1993). **수정**: 모듈 스코프 `let _dateGroupsSeededThisLoad`(페이지 로드당 리셋) + `_seedDateGroupsCollapsedOnce(sortedDateKeys)` — `renderConversationList` 의 `sortedDateKeys` 정렬 직후·`forEach` 렌더 전 1회 호출하여 `sortedDateKeys[0]`(최근)은 `delete`(펼침 보장), 나머지는 `add`(접힘). 빈 키면 플래그 미설정(대화 미로드 시 다음 렌더 재시도). localStorage 영속 안 함(`_saveCollapsedGroups` 미호출) → reload 마다 재적용, 같은 로드 내 사용자 펼침 토글은 1회-게이트가 존중. 캐시버스터 `?v=20260618-date-group-collapse`. **비변경**: 백엔드·RBAC·스키마·엔드포인트·데이터 0, 타 계정 그룹 `_seedOthersCollapsedOnce`·owner 토글·날짜 그룹 클릭 토글 영속 비변경(직교). **검증**: `verify_date_group_collapse.mjs` 22/22 PASS(fresh seed·강제펼침·빈키 재시도·세션 토글 존중·단일 그룹·`__other__`·비영속·배선 순서) + 기존 `verify_conv_entry_defaults.mjs` 20/20 무회귀 + node --check. worktree `ai/claude/date-group-collapse`(base 3250ac5). **완료**: verify-completion --pre-commit PASS(9 checks) → 머지(PR #319 squash, main `32b5e8f`) → web 재배포(deploy_scope: included, repo-web-1 Up·mysql_ok·pg_ok, 서빙 `app.js?v=20260618-date-group-collapse`·`_seedDateGroupsCollapsedOnce` baked) → **PB-0008 Windows-browser PASS**(실 Chrome/148, bootstrap_admin·대화 109개: 첫 진입 6개 날짜 그룹 중 가장 최근 "6월 10일 (수)"만 펼침·나머지 5개 접힘·VERDICT PASS; clean-room `localStorage.clear()`→reload 로 seed 매-진입 재발화 + 날짜키 비영속(reload 후 `mad.collapsedGroups.v1`=`["__others__"]`만, 날짜 키 0) 실증; 세션 내 펼침 토글 1회-게이트 존중 PASS). evidence `artifacts/pb0008-date-group-collapse/entry-recent-only-expanded.png`. CHG/REV-20260618T010417-ai-claude-date-group-collapse, evidence CHG/REV-20260618T011645-ai-claude-date-group-collapse-evidence.

**2026-06-17 TASK-0300 — 관리 콘솔 계정/역할 권한 편집 self-scope (privilege escalation 방지)** (REV-20260617-0307 [SUBAGENT:perm-self-scope-security] **SHIP-WITH-FIXES→SHIP**, **Critical §12.3 — 인가/RBAC**, `src/app.py` + `src/static/admin.js`/`admin.html` + 신규 `tests/{test_perm_self_scope.py,verify_perm_self_scope.mjs}`). 사용자 요청: `관리 콘솔 > 계정` 에서 자기 자신이 보유한 권한을 넘어서는 권한은 숨김 처리 + 설정 불가. **사용자 결정**: ① 미보유 권한 = allow·deny 모두 불가(완전 숨김) ② 범위 = 계정+역할 ③ (외부리뷰 후) 역할 *배정* 도 차단 ④ product.access self-scope 포함 유지. **진단**: `admin_update_account`/`admin_update_role`/`admin_create_role` 에 self-scope 가드 부재 → 관리자가 본인 미보유 권한을 타 계정 override·역할 permission_codes 로 부여 가능(escalation). 부수 리스크: override/codes 전체 교체+delete-all-then-insert 라 프론트가 행을 숨기면 숨긴 권한 기존값 누락→삭제(데이터 손실). **수정**: 백엔드 정본 — `_actor_editable_permission_codes`(effective 보유 권한) + `_enforce_override_self_scope`(계정) + `_enforce_role_permission_self_scope`(역할) + `_role_grant_excess_for_actor`(역할 배정). 미보유 권한 설정/부여/배정 시 403 + 범위 밖 기존값 merge 보존. wiring 4경로(account override·role update·role create·role assign). 프론트 admin.js — `renderPermissionGrid(opts.allowedCodes)` 미보유 행 숨김(빈 그룹/section 제거·product_access 컨테이너 보존) + 계정/역할 상세 wiring + 제품카드 필터 + 역할 드롭다운 배정불가 역할 숨김 + onChange 숨긴값 보존 + 안내문구. 캐시버스터 `?v=20260617-task0300-perm-self-scope`. **비변경**: 스키마·엔드포인트 shape·RBAC 카탈로그·기존 `*.manage` 게이트 0(직교). **검증**: `test_perm_self_scope.py` 18 PASS(ast 추출 실 helper 4종 — escalation 403·deny 차단·merge 보존·역할 add/remove/create·배정 초과) + `verify_perm_self_scope.mjs` 13 PASS(실 `renderPermissionGrid` jsdom — 미보유 행 숨김·빈 그룹 제거·컨테이너 보존·하위호환) + node --check + py ast.parse. **outside-voice 적대 보안 리뷰 SHIP-WITH-FIXES**(우회경로 전수 직접 0·merge/lockout/editable 안전 10/10): MAJOR-1(역할 배정 우회)→배정 가드 흡수(사용자 결정), MINOR-1(product.access)→포함 유지(사용자 결정), MINOR-2(비대칭)→docstring NOTE. worktree `ai/claude/admin-perm-self-scope`(base c4c8770). **완료**: 머지(main `a9effd6`, PR #313 squash) → web 재빌드 배포(deploy_scope: included, 서빙 `?v=20260617-task0300-perm-self-scope`·app.py 가드 baked) → **라이브 403 검증 PASS**(실 제한계정 pgpark/usermanager: 미보유 audit.purge allow·deny 403, 보유 account.read allow 200, admin 역할 배정 403) + **PB-0008 Windows-browser PASS**(실 Chrome render-injection: 미보유 행 숨김·빈 그룹 제거·컨테이너 보존·account 행 computed flex·offsetParent≠null) → 마감. CHG/REV-20260617-0307, evidence CHG/REV-20260617-0308.

**2026-06-16 TASK-20260616T100304-conv-entry-defaults — 작업 화면 첫 진입 기본값: 타 계정 대화 접힘 + 빈 대화 화면** (REV-20260616T100304-ai-claude-conv-entry-defaults [SKIPPED:frontend-ui-entry-defaults-no-backend-no-rbac], **Major §12.3**, frontend-only `src/static/{app.js,index.html}` + 신규 `tests/verify_conv_entry_defaults.mjs`). 사용자 요청: ① 작업 화면 첫 진입 시 "타 계정 대화"는 접혀 있도록, ② 대화 화면 또한 비어 있는 상태로. **진단**: ① "타 계정 대화" 그룹(`__others__`)의 접힘은 `state.collapsedDateGroups`(localStorage `mad.collapsedGroups.v1`)로 결정되는데 첫 진입 시 set 이 비어 펼침이 기본(app.js renderConversationList). ② bootstrap `initializeWorkspace` 가 서버 직전 대화(`session.conversation_id`)를 `_preferCid` 로 자동 선택 + `loadConversations` 가 `payload.current` 로 폴백해 항상 직전 대화 로드. **수정**: ① `_seedOthersCollapsedOnce()` — seed 플래그(`mad.othersCollapsedSeed.v1`)가 없을 때만 1회 `__others__` 를 접힘 set 에 추가·영속(이후 사용자가 펼치면 그 선호 존중, date 그룹 토글과 독립). ② `loadConversations(_, {allowCurrentFallback})` 옵션 신설 — `initializeWorkspace` 가 fresh 진입 시 `false` 로 호출해 `payload.current` 자동선택 차단(빈 화면). **회귀 방지**: deep-link(`?conversation=`, TASK-0263)는 `allowCurrentFallback=true` 보존, 진행 중 요청 resume(TASK-0041)은 서버 current 가 처리 중이면 그 대화를 선택(status 공유로 중복 fetch 회피). 다른 refresh 호출자는 default `true` 라 무회귀. **비변경**: RBAC/스키마/엔드포인트/백엔드 0. **검증**: node --check PASS + `verify_conv_entry_defaults.mjs` 20/20 PASS(seed fresh/respect, 빈 진입/폴백/resume-select/pending-guard, init 배선) + 백엔드 무변경(회귀 자명 0). cache-buster `?v=20260616-conv-entry-defaults`. worktree `ai/claude/conv-entry-defaults`(base 3f0d352, rebase→origin/main). **완료**: PR #293 squash 머지(main `b5f2434`) → web 재배포(서빙 `?v=20260616-conv-entry-defaults`·`_seedOthersCollapsedOnce` baked·healthz git_commit=b5f2434 mysql_ok·pg_ok) → **PB-0008 Windows-browser PASS**(실 Chrome/148, bootstrap_admin·대화 104개·타 계정 대화 50건): 요구2=서버 직전 대화 존재(`session.conversation_id` set)인데도 첫 진입 `activeConversationId=""`·제목 "대화를 선택하세요"; 요구1=첫 진입 시 "타 계정 대화" 그룹 `is-collapsed`·`aria-expanded=false`·owner 헤더 0개(50건 숨김)·`mad.othersCollapsedSeed.v1=1`. clean-room(`localStorage.clear()`→reload) seed 재발화 + 빈 화면 동시 재현, 펼침 토글 reload 후 유지(선호 존중). evidence `artifacts/pb0008-conv-entry-defaults/entry-others-collapsed-empty-chat.png`. CHG/REV-20260616T163634-ai-claude-conv-entry-defaults-pb0008.

**2026-06-16 TASK-0291 — 관리 콘솔 계정 탭 배지 개수 활성 계정만 집계** (REV-20260616-0300 [SKIPPED:frontend-only-display-count], **Minor §12.3**, frontend-only `src/static/admin.js` 1곳 + 캐시버스터). 사용자 요청: `관리 콘솔 > 계정` 항목 개수를 활성화된 계정만 집계 — 비활성·삭제는 목록 필터에서 확인 가능하므로 배지엔 실제 중요한 정보(활성 수)만 노출. **진단**: 사이드바 계정 탭 배지 `#tabCountAccounts`(`refreshPendingUI`)가 `adminState.accounts.length`(전체)를 표시. 목록 내부 카운트 `#accountListCount`(`renderAccountList`)는 이미 `filteredAccounts()` 기반 filter-aware. **수정**: `refreshPendingUI` 의 `tabCountAccounts` 집계를 `adminState.accounts.filter((a) => a.is_active && !a.deleted_at).length`(활성 정의 = `filteredAccounts()` 의 `'active'` 분기와 동일)로 변경. 캐시버스터 `admin.html ?v=20260616-task0291-account-active-count`. **비변경**: 백엔드/RBAC/스키마/엔드포인트 0, `#accountListCount`(filter-aware) 비변경, 역할/제품/데이터소스 탭 배지 비변경(요청 범위=계정 한정). **검증**: node --check PASS, 백엔드 무변경(회귀 자명 0). worktree `ai/claude/task0291-account-active-count`(base eecc75c). **완료**: PR #287 squash 머지(main 9bdb9f8) → web 재배포(서빙 `admin.js?v=20260616-task0291-account-active-count`·`activeAccountCount` baked 2hit·healthz git_commit=9bdb9f8 mysql_ok·pg_ok) → **PB-0008 Windows-browser PASS**(win-browser eval 실측: 계정 탭 배지 `#tabCountAccounts`=**7** = 활성 필터 목록 `#accountListCount`=**7명** 일치 + 전체 **28명**[7활성+1비활성+20삭제]과 분리 → 배지가 전체 아닌 활성만 집계 확인. evidence `artifacts/pb0008-task0291/account-tab-active-count.png`). CHG/REV-20260616-0300, evidence CHG/REV-20260616-0301.

### Git 동기화 결과 (TASK-0291)
- 커밋: aaaaf25 → origin/main(3f0d352, TASK-0288/0290 전진) rebase(523eb64, FUNCTION.md+admin.html 충돌 해소·AC-0532→0538·REV/CHG-0299→0300 재번호 — TASK-0288 선점 회피) → PR #287 squash 머지 main `9bdb9f8`.
- verify-completion: PASS (9/9; CHECK#13 Windows-browser WARN-only → 배포 후 PB-0008 PASS 로 충족).
- Push: 완료. main 병합: 완료(squash). 충돌 해결: AI 자율 rebase(2파일, ID 재번호 6건).
- 로컬/원격 브랜치 정리: 완료(worktree remove + branch -d + push --delete).

**2026-06-16 TASK-0287 — 말풍선 첨부 칩 다운로드 실패 수정** (REV-20260616-0297 [SKIPPED:frontend-only-download-method], **Minor §12.3**, frontend-only `src/static/app.js` 1곳 + 캐시버스터). 사용자 보고: 첨부파일 목록 다운로드는 되지만 말풍선 안 첨부 칩은 다운로드 실패. **진단**: 목록은 `_downloadAttachmentById`(raw fetch + blob, TASK-0284), 말풍선 칩(`_buildMessageAttachChip`, TASK-0285)은 `<a href download>` **navigation** 방식. TASK-0284 가 octet-stream 프록시(`/api/attachments/{id}/download`)에서 navigation 다운로드 실패로 목록을 fetch+blob 으로 전환했으나 말풍선 칩에는 미적용. **수정**: 칩 click 핸들러를 `att.id` 있으면 `_downloadAttachmentById`(목록과 동일 fetch+blob) 호출로 통일, signed_url 폴백만 navigation 유지. **비변경**: 백엔드/RBAC/엔드포인트/`_downloadAttachmentById` 0. **검증**: node --check PASS, 백엔드 무변경(회귀 자명 0). 캐시버스터 `?v=20260616-task0287-bubble-chip-dl`. worktree `ai/claude/bubble-chip-download-fix`(base 7ec211d). **완료**: PR #281 squash 머지(main c5b4823) → web 재배포(baked `_downloadAttachmentById(att.id` 1곳·서빙 `?v=20260616-task0287-bubble-chip-dl`) → **PB-0008 PASS**(win-browser 실측: `_buildMessageAttachChip({id,...})` 칩 click → window.fetch monkeypatch 로 **chipUsesFetch=true**[fetch `/api/attachments/88888/download` 호출, navigation `<a>` 아님]·credentials=same-origin·has-download 확인. 목록과 동일 fetch+blob 경로 검증). 실 다운로드는 목록(`_downloadAttachmentById`)이 사용자에게 작동하므로 칩도 동일 동작. CHG/REV-20260616-0298.

**2026-06-16 TASK-0286 — 첨부 수정본 전달: 전체 본문 노출 제거 + 변경점만(diff) + 파일 명시 전달** (REV-20260616-0295 [SUBAGENT:attach-edit-strip-security] **SHIP-WITH-FIXES**, **Major §12.3**, TASK-0275/0285 후속). 사용자 보고: assistant 가 파일(첨부)을 전달하지 않고 첨부 본문 전체를 채팅에 텍스트로 출력 — 변경점만 전달 + 수정 파일 명시 전달 요청. **진단**: attachment-edit(파일화) 인프라(TASK-0275)는 있으나 ⓐ 시스템 프롬프트 사용법 부재(assistant 가 전체 본문 출력), ⓑ materialize 후 블록 잔존 노출, ⓒ 프론트 미처리. **수정**: A.(agent_core SYSTEM_PROMPT) "DELIVERING THE EDITED FILE — attachment-edit" 섹션(diff=변경점 / attachment-edit=전체 본문 숨김·첨부화 / 전체 본문 코드블록 금지). B.(app.py) 라인 기반 `_attachment_edit_block_spans`(본문 내 ``` 허용) → `_parse` 재구현 + 신규 `_strip_attachment_edit_blocks`(블록 제거→"📎 수정본 전달" 치환) + `_update_assistant_message_content`(render_output + DB content 둘 다 → history·LLM 재컨텍스트 본문 제거). C.(app.js/share.js) `enhanceAttachmentEditBlocks`(블록→`.attachment-edit-note`, 과거 메시지·share 안전망). **비변경**: RBAC·스키마·엔드포인트 shape 0. **검증**: 신규 `test_task0286_attach_edit_strip.py` 10 PASS + make test 컨테이너 전체 회귀 0(PYTEST_EXIT=0, ruff clean) + py_compile + node --check + CSS brace + 캐시버스터 `?v=20260616-task0286-attach-edit-diff`. **outside-voice SHIP-WITH-FIXES**: MAJOR(lazy 정규식이 파일 본문 내 ``` 에서 조기 종료→strip 잔여 누출 + 첨부 절단)를 **라인 기반 파서로 흡수**(회귀 S6/S7); IDOR·XSS·멱등·재컨텍스트 refute. worktree `ai/claude/attach-edit-diff-only`(base dd84ca8). **완료**: PR #278 squash 머지(main b884b67) → web+ask-worker 재빌드(baked: web app.py 5곳·ask-worker agent_core DELIVERING·서빙 `?v=task0286`) + **라이브 WebSystemPrompts global row 멱등 append**(`_connect_memory`, SHOWING CHANGES 다음 DELIVERING 섹션 삽입, 6837→8536자, 백업 `/tmp/sysprompt_global_backup_task0286.txt`) → **PB-0008 Windows-browser PASS**(실 Chrome/148 render-injection: `markdownToHtml`(diff + attachment-edit 텍스트) → fullBodyHidden=true[전체 본문 SECRET_FULL_BODY 미노출]·diffPresent=true[변경점 유지]·`.attachment-edit-note`("📎 수정된 첨부 파일 (orders_v2.sql)", rgb(37,99,235))·attachEditBlockGone=true). 백엔드 strip=pytest 10 PASS(S1~S7 embedded-fence 회귀). 실 e2e(첨부 업로드→assistant 수정→strip→칩)는 LLM 의존이라 합성 render-injection + 단위 테스트로 검증, 실사용 시 자연 재현. evidence `artifacts/pb0008-task0286/attach-edit-diff-only.png`. CHG/REV-20260616-0296.

**2026-06-16 TASK-0285 — 첨부 버전 현황 표면화 ②③④** (REV-20260616-0293 [SUBAGENT:attach-surfacing-security] **SHIP**, **Major §12.3**, TASK-0275 후속 보완). 사용자 요청(TASK-0275 배포 후 보완): ② `'+' > 첨부파일 목록`의 각 파일 버전 현황 표시, ③ assistant 말풍선 안에 첨부 명시 표시(사용자 말풍선처럼), ④ assistant 요청 시 진행 단계에 첨부 수정 명시 출력. (쿼리 리뷰 워크플로① 는 사용자 결정으로 후속 cycle.) **진단**: TASK-0275 인프라(materialize·버전 체인·`/versions`·직렬화 버전 필드)는 이미 존재하나 "노출·연결"이 빠짐. **수정**: ② (app.py) `list_conversation_attachments` 에 version_count/ai_version_count `GROUP BY COALESCE(RootAttachmentId, Id)` 집계 + (app.js) 목록 항목 버전 배지·"버전 N개 ▾" 펼침(/versions lazy)·`_downloadAttachmentById`/`_renderAttachmentVersionsBox` 헬퍼. ③ (app.py) `_load_assistant_attachments_by_message`(MetaJson.message_id 그룹핑) + `_attach_assistant_attachments` + `_get_history`(PG·MySQL) 주입 + (app.js) `_buildMessageAttachChip`(user/assistant 공통·버전 배지) + renderMessages 칩 조건 assistant 포함 + assistant 말풍선 칩 배경 CSS. ④ (app.py) ask materialize 후처리에 `save_memory_step`(attachment_edit/materialize_attachment, work/reason 직접 저장) + 응답 render_steps 즉시 반영. **비변경**: RBAC 카탈로그/스키마/엔드포인트 shape 0(응답 필드 추가 + 신규 헬퍼만). **보안(IDOR)**: history 첨부 직렬화는 ConversationId 스코프만이나 유일 호출경로 `/api/history` 의 대화 접근권 게이트로 차단, 첨부 AccountId=대화 소유자 고정. **검증**: 신규 `test_task0285_attach_surfacing.py` 9 PASS + make test 컨테이너 전체 회귀 0(PYTEST_EXIT=0, ruff clean) + py_compile + node --check + CSS brace(1242=1242) + 캐시버스터 `?v=20260616-task0285-attach-surfacing`. **outside-voice 적대 보안 리뷰 SHIP**(7개 위협 IDOR/signed_url/SQLi/MetaJson조작/fail-soft/run_id 전부 refute, MINOR=steps UNIQUE 부재 cosmetic 기록만). worktree `ai/claude/attach-version-surfacing`(base d932bba=main). **완료**: PR #275 squash 머지(main 1c4737d) → web 재배포(baked `_load_assistant_attachments_by_message` 3곳 + 서빙 `?v=20260616-task0285-attach-surfacing`, ask/insight-worker 무관) → **PB-0008 Windows-browser PASS**.

### Git 동기화 + PB-0008 결과 (TASK-0285)
- 커밋: 661321a → rebase origin/main → PR #275 squash 머지 main `1c4737d`. 원격/로컬 브랜치 정리 완료(multi-worktree 라 gh `--delete-branch` 로컬 후처리 실패 → 수동 worktree remove + branch -D + push --delete).
- verify-completion: PASS(CHECK#13 WARN-only — PB-0008 후속). 배포: 자동 동기화 §16.3 + `deploy_scope: included` — web 재빌드/재기동 완료.
- **PB-0008 PASS** — 실 Chrome/148 render-injection computed 실측. 라이브에 assistant 수정본 데이터 0건(TASK-0275 배포 후 실사용 미발생)이라 실 e2e 대신 `_buildMessageAttachChip`/`_renderAttachmentVersionsBox` 합성 데이터 주입 → jsdom 이 못 잡는 CSS 캐스케이드(ai-edited 배지 색 #2563eb, assistant 말풍선 칩 배경 흰 surface, 버전 박스 2행+버전별 다운로드)를 실 브라우저 computed 로 확증. evidence `artifacts/pb0008-task0285/attach-version-surfacing.png`. 실 데이터(첨부 업로드→assistant 수정→버전 생성)는 실사용 시 자연 발생. CHG/REV-20260616-0294.

**2026-06-16 TASK-20260616T022652-ai-claude-sidebar-resize — 대화창 좌측 사이드바 너비 드래그 조절** (REV-20260616T022652-ai-claude-sidebar-resize [SKIPPED:frontend-ui-resize-no-backend-no-rbac], **Minor §12.3**, frontend-only `src/static/{index.html,styles.css,app.js}` + 신규 `tests/verify_sidebar_resize.mjs`). 사용자 요청: 좌측 대화 사이드바 영역의 크기 조절. **진단**: 좌측 사이드바는 `.app-shell` grid 첫 컬럼(`--sidebar-w: 252px` 고정)으로 조절 수단이 없었으나, 우측 패널 3종(`#stepSidePanelResizer`/`#profileDrawerResizer`/`#attachSidePanelResizer`)에 이미 drag-resize + `localStorage` 영속 패턴이 존재. **수정**: 동일 패턴을 좌측에 미러링 — `.app-shell` 자식 `#sidebarResizer` 핸들(경계 `left:var(--sidebar-w)` 추종, `overflow:hidden` 클리핑 회피)을 두고, 드래그가 `--sidebar-w` CSS 변수를 `[180, min(640, 50%vw)]` clamp(우변=clientX). mouseup 시 `localStorage["web.sidebar.width"]` 영속, 더블클릭 reset, 모바일(≤680)에선 핸들 숨김 + override 제거(기존 반응형 보존). **비변경**: RBAC/스키마/엔드포인트/백엔드/기존 우측 resizer 0. **검증**: node --check + CSS brace(1222=1222) + jsdom 23/23 + make test 회귀 0(REAL_MAKE_EXIT=0). cache-buster `?v=20260616-sidebar-resize`. worktree `ai/claude/sidebar-resize`(base 3b49ee2=main).

### Git 동기화 결과 (TASK-20260616T022652-ai-claude-sidebar-resize)
- 커밋: 7e43b51 (ai/claude/sidebar-resize, base 3b49ee2) → squash 머지 main 6f1242b (PR #267).
- verify-completion: PASS. Push / PR / main 병합 / 배포: 자동 동기화 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포(healthz git_commit=6f1242b, 서빙 자산 baked) 완료.
- **PB-0008: PASS** — 실 Chrome/148 드래그 시 사이드바 폭 실제 변화(252→380, chat-column reflow)·clamp(180/624)·새로고침 복원(340)·더블클릭 reset 실측. evidence `artifacts/pb0008-sidebar-resize/sidebar-resized-340.png`. CHG/REV-20260616T024150-ai-claude-sidebar-resize-pb0008.

**2026-06-16 TASK-0283 — 관리 콘솔 제품 아이콘 편집 UI 를 유저 프로필과 동일한 ✎ 오버레이로 통일** (REV-20260616-0291 [SKIPPED:frontend-icon-edit-ui-no-backend-no-rbac], **Minor §12.3**, frontend-only `src/static/admin.js` 1곳 + dead CSS 제거 + cache-buster). 사용자 보고: `관리 콘솔 > 제품 > [항목] > 프로필 아이콘` 의 수정버튼 UI 를 유저 프로필과 동일하게. 현재 "아이콘" 텍스트박스가 제품 아이콘(36px) 영역을 크게 침범. **원인**: 제품 상세(admin.js `renderProductDetail`)가 `.admin-avatar-edit`(absolute `bottom:-22px`) 안에 "아이콘"·"제거" 텍스트 pill 2개를 배치 → 텍스트 버튼 폭이 아바타보다 넓어 좌우 spill·침범. 유저 프로필(index.html `.profile-avatar-edit`)은 ✎ 펜슬을 아바타 우하단에 원형 오버레이(`.profile-avatar-change`)하고 "사진 제거"는 텍스트 링크(`.profile-avatar-remove`)로 분리. **수정**: 텍스트 pill 폐기 → 아바타를 `.profile-avatar-edit` 래퍼로 감싸 `.profile-avatar-change`(✎) 오버레이 + 숨김 input, "아이콘 제거"는 `.profile-avatar-remove` 링크로 idText 하단 분리(유저 프로필과 동일 클래스 재사용 → 시각 동형, 신규 CSS 0). dead `.admin-avatar-edit/change/remove` 규칙 제거(사용처 0건). **비변경**: 아이콘 PUT/DELETE 엔드포인트·5MB 가드·toast·renderProductDetail 재렌더·applyAvatar/Identicon·`canManage` 게이트 0. **검증**: node --check admin.js PASS. cache-buster `?v=20260616-product-icon-edit`. worktree `ai/claude/task0283-product-icon-edit`(base 2e5778a=main). **완료**: PR #265 머지(main 245446f) → web 재배포(deploy_scope: included, repo-web-1 healthy) → **PB-0008 Windows-browser PASS**(✎ 원형 오버레이 computed 실측·구 pill 부재·침범 0·유저 프로필 동형; evidence `artifacts/pb0008-task0283/product-icon-edit-overlay.png`, CHG/REV-20260616-0292).

### Git 동기화 결과 (TASK-0283)
- 커밋: 8792171 (ai/claude/task0283-product-icon-edit, base 2e5778a) → squash 머지 main 245446f(PR #265). 증거 docs-only: CHG/REV-20260616-0292.
- verify-completion: PASS. Push / PR / main 병합 / 배포: 자동 동기화 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포 완료.
- PB-0008: PASS(완료).
- 잔여: PB-0008(제품 상세 아이콘 편집 ✎ 오버레이·침범 0 시각검증).

**2026-06-15 TASK-20260615T182907-product-list-row-icon-layout-fix — 제품 관리 목록 행 UI 뒤틀림 핫픽스** (REV-20260615-0286 [SKIPPED:frontend-layout-bugfix-no-backend-no-rbac], **Minor §12.3**, frontend-only `src/static/admin.js` 1곳). 사용자 보고: 제품 관리 목록 UI 뒤틀림. **원인**: 직전 cycle(PR #249)이 목록 행에 아이콘 추가 시 `row.append(cb, avatar, meta)` 로 avatar 를 row 최상위 2번째 칸에 둬 `.admin-list-row` 3열 grid(`auto 1fr auto`)가 깨짐(avatar 가 1fr·meta 가 auto 칸으로 밀림). **수정**: avatar 를 `meta` 첫 줄 `titleRow`(`admin-list-row-title` flex) 안에 name 과 함께 묶고 `row.append(cb, meta)` 2자식 복원 — 계정 목록 행과 동형, grid 정상. **비변경**: 아이콘 렌더·CSS·chip·드롭업·상세·row click·cov 배지 0. **검증**: node --check + **jsdom 19/19 PASS**(기존 14 + [3] 행 레이아웃 회귀 5) + make test 회귀 0. worktree `ai/claude/product-icon-pb0008-record`(base origin/main rebase). **잔여**: 머지 → web 재배포 → PB-0008 재검증(목록 행 정렬 정상).

### Git 동기화 결과 (TASK-20260615T182907-product-list-row-icon-layout-fix)
- 커밋: <cycle commit hash> (ai/claude/product-icon-pb0008-record, base origin/main rebase)
- Push / PR / main 병합 / 배포: 자동 동기화 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동.
- 잔여: PB-0008(제품 관리 목록 행 정렬·아이콘·텍스트 위치 정상 재검증).

**2026-06-15 TASK-0277b — 보관 대화 row ellipsis 실작동 핫픽스 (TASK-0277 후속, PB-0008 실측 발견)** (REV-20260615-0283 [SKIPPED:frontend-ui-consistency-no-backend], **Minor §12.3**, frontend-only `src/static/styles.css` 1 규칙 + 캐시버스터 + jsdom 계약). **발견**: TASK-0277(PR #250) 배포 후 PB-0008 실 브라우저 실측에서, 줄바꿈 차단(rowH 56px 고정)은 됐으나 **ellipsis 가 발동 안 함**(긴 문자열 주입 시 `.admin-archive-row-line` 이 콘텐츠 폭 2858px 로 팽창, topic scrollW===clientW===2714 → clipped:false). **원인**: `.admin-archive-row` 는 `.admin-list-row`(grid, `align-items:center`) + `.admin-archive-row`(flex column) 두 클래스를 함께 가지는데, `.admin-list-row` 의 `align-items:center` 가 flex 컬럼에 상속돼 각 줄이 row 폭(330px)으로 stretch 되지 않음 → 자식 span 이 shrink 못 해 `text-overflow:ellipsis` 미발동. jsdom 은 CSS 규칙 존재만 검사(cascade/layout 미계산)라 25 PASS 통과 — **실 브라우저 검증의 필요성을 입증**. **수정**: `.admin-archive-row` 에 `align-items: stretch` 추가. 라이브 실험 사전확인: line 2858→308px, topic clientW 164·scrollW 2714 → clipped:true, rowH 56(2줄) 유지. 캐시버스터 `?v=20260615-task0277b-archive-row-ellipsis`. jsdom 계약 단언 추가(26 PASS) + node --check + CSS brace(1210=1210) + make test 회귀 0. worktree `ai/claude/archive-row-ellipsis-fix`(base 61e0151=main). **잔여**: 머지 → web 재배포(deploy_scope: included) → PB-0008 재검증(clipped:true).

### Git 동기화 결과 (TASK-0277b)
- 커밋: <cycle commit hash> (ai/claude/archive-row-ellipsis-fix, base 61e0151)
- verify-completion: <pre-commit 결과>
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → push→PR→머지→cleanup→web 재배포 자동.
- 잔여: PB-0008 재검증(보관 대화 row ellipsis 실작동 clipped:true).

**2026-06-15 TASK-0277 — 관리 콘솔 "보관 대화" 탭 UI 정합 다듬기 (TASK-0276 list-detail 위 후속)** (REV-20260615-0281 [SKIPPED:frontend-ui-consistency-no-backend], **Minor §12.3**, frontend-only `src/static/{admin.html,admin.js,styles.css}` + 신규 jsdom 테스트). 사용자 요청 2건(frontend-only — 백엔드/RBAC/엔드포인트 무변경): [문제1] 보관 대화 pane header↔filter 사이의 `<p class="admin-pane-note">`(3문장 안내)가 다른 탭(계정·역할·제품·감사 로그)에 없는 큰 여백 → 밀도 불일치. [문제2] `#archiveList` 의 각 `.admin-archive-row` 가 topic·소유자·보관자 문자열 길이에 따라 줄바꿈되어 구성 뒤틀림. **진단**: [문제1] `admin-pane-note` 는 admin.html 전체에서 보관 대화 pane 단일 사용처(다른 탭은 header→filter 직결) — 밀도 불일치의 유일 원인. [문제2] `.admin-archive-row-line { flex-wrap: wrap }` + owner/by span 의 nowrap/ellipsis/`min-width:0` 부재가 근본 원인. **수정(frontend-only)**: ① (admin.html) pane-note 제거 + 우측 `#archiveDetail` 빈 상태(`admin-detail-empty`)에 `admin-archive-detail-note` 안내 이동(정보 보존·밀도 정합). ② (admin.js) `renderArchiveDetail` 빈 분기도 동일 안내 carry(static 정합). ③ (styles.css) `.admin-archive-row-line` flex-wrap 제거 + align-items:baseline/min-width:0; topic/owner/by span 에 nowrap+ellipsis+overflow:hidden+min-width:0(줄바꿈 대신 절단); ts flex:0 0 auto+nowrap(비절단·우측 정렬 유지); 사용처 0건 `.admin-pane-note` 규칙 제거. 캐시버스터 `?v=20260615-task0277-archives-ui-align`. **비변경**: 백엔드/`/api/admin/conversations/archived` 응답 계약/RBAC/탭 가시성/`renderArchiveList` 템플릿 로직/`_archiveEsc` 0. **검증**: node --check admin.js + CSS brace(1207=1207) + **jsdom 25/25 PASS**(`tests/verify_archive_tab_ui.mjs` — 안내 이동·밀도·row 2줄 고정·CSS anti-wrap 계약) + make test 컨테이너 **전체 회귀 0**(ruff clean, MAKE_EXIT=0). worktree `ai/claude/archive-tab-ui-polish`(base 6d35c44=main). **잔여**: 머지 → web 재배포(`deploy_scope: included`) → PB-0008 Windows-browser(짧은/긴 topic·긴 username 혼재 레이아웃 안정).

### Git 동기화 결과 (TASK-20260615T182907-product-list-row-icon-layout-fix)
- 커밋: <cycle commit hash> (ai/claude/product-icon-pb0008-record, base origin/main rebase)
- Push / PR / main 병합 / 배포: 자동 동기화 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동.
- 잔여: PB-0008(제품 관리 목록 행 정렬·아이콘·텍스트 위치 정상 재검증).

**2026-06-15 TASK-0277 — 관리 콘솔 "보관 대화" 탭 UI 정합 다듬기 (TASK-0276 list-detail 위 후속)** (REV-20260615-0281 [SKIPPED:frontend-ui-consistency-no-backend], **Minor §12.3**, frontend-only `src/static/{admin.html,admin.js,styles.css}` + 신규 jsdom 테스트, 머지됨 #250). 보관 대화 pane 의 [문제1] header↔filter `admin-pane-note` 큰 여백(밀도 불일치) → 우측 빈 상태로 안내 이동, [문제2] row 문자열 줄바꿈 뒤틀림 → flex-wrap 제거 + nowrap/ellipsis/min-width:0 절단. jsdom 25 PASS + make test 회귀 0. 캐시버스터 `?v=20260615-task0277-archives-ui-align`.

**2026-06-15 TASK-20260615T180923-product-icon-chip-list — 제품 프로필 아이콘을 대화창 chip + 제품 관리 목록 행에도 표시** (REV-20260615-0280 [SKIPPED:frontend-ui-consistency-no-backend-no-rbac], **Minor §12.3**, frontend-only `src/static/{index.html,app.js,admin.js,styles.css}` + 신규 jsdom 테스트). 사용자 요청(profile-icon-consistency 후속): 제품 프로필 아이콘(Identicon)을 (1) 대화창 제품 chip 과 (2) 제품 관리 탭 목록 행에도 뱃지 아이콘으로 표현. **수정(frontend-only, 4 src)**: ① index.html chip 에 `#productChipIcon` span 추가. ② app.js `renderProductChip` — pinned 제품이면 아이콘(설정 이미지 or Identicon 폴백) 표시, auto 면 hidden. ③ admin.js `renderProductList` — 각 행에 `applyAvatar(seed=product_key)` 아이콘(`admin-avatar admin-avatar-sm`, 계정 목록 동형). ④ styles.css `.composer-product-chip-icon`(16px 원형) 신설 + chip max-width 180→200, 행 아이콘은 직전 cycle `.admin-avatar > svg` 원형 클립 재사용. 캐시버스터 `?v=20260615-product-icon-chip-list`. **비변경**: 백엔드/RBAC/스키마/엔드포인트 0(icon_url 기존 직렬화 필드 소비). **정합**: chip·목록 행·드롭업·관리 상세·작업화면 프로필이 모두 동일 `identiconSvg(product_key)` → 동일 제품 동일 아이콘. **검증**: node --check + CSS brace(1211) + **jsdom 14/14 PASS**(`tests/verify_product_icon_chip_list.mjs`) + make test 컨테이너 **회귀 0**. worktree `ai/claude/product-icon-chip-list`(base 6d35c44=main). **잔여**: 머지 → web 재배포(`deploy_scope: included`) → PB-0008 Windows-browser 시각검증.

### Git 동기화 결과 (TASK-20260615T180923-product-icon-chip-list)
- 커밋: <cycle commit hash> (ai/claude/product-icon-chip-list, base 6d35c44)
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동.
- 잔여: PB-0008(대화창 chip 아이콘·제품 관리 목록 행 아이콘 시각검증).

**2026-06-15 TASK-20260615T172210-profile-icon-consistency — 제품 프로필 아이콘 정합화 + 대화 드롭업 항목 레이아웃·너비 + 제품 명칭 표기 순서** (REV-20260615-0277 [SKIPPED:frontend-ui-consistency-no-backend-no-rbac], **Major §12.3**, frontend-only `src/static/{admin.js,app.js,styles.css,index.html,admin.html}` + 신규 jsdom 테스트). 사용자 요청 3건: (1) `관리 콘솔 > 제품 > [각 항목]` 제품 프로필 아이콘을 `작업 화면 > 프로필` 과 정합하게, (2) 대화 화면 요청 텍스트박스의 제품 선택 목록/항목에 [네트워크 상태 배지·프로필 아이콘·제품 명칭·데이터 소스] 적절 배치 + 명칭 잘림 해소(너비 확대), (3) 명칭 표기 `제품 명칭 (제품 약어)` → `(제품 약어) 제품 명칭`. **진단**: 작업화면 프로필(app.js `applyAvatar`/`identiconSvg`, TASK-0268)은 이미지 미설정 시 결정론적 Identicon SVG 폴백이나, 관리 콘솔 제품 아이콘(admin.js `renderProductDetail`)·대화 드롭업 아이콘은 이니셜 텍스트 또는 미표시 → 비정합. 드롭업 항목 순서 [아이콘(설정 시만)→dot→명칭→ds] + 메뉴 max-width 280px(명칭 잘림). **수정(frontend-only, 5 src)**: ① admin.js 에 app.js 헬퍼 3개 byte-identical 이식 + 제품 아이콘 `applyAvatar(seed=product_key)` → 미설정 시 Identicon(작업화면 정합). ② `buildProductDropupItem` 자식 순서 [dot→아이콘→명칭→ds] 재배열 + pinned 아이콘 항상 표시(이미지 or Identicon 폴백). ③ styles.css 메뉴 너비 min 220→300/max 280→min(420px,92vw) + 아이콘 18px 원형 + admin-avatar 이미지·SVG 원형 클립. ④ 명칭 조합 7곳(app.js 4·admin.js 3) `(${product_key}) ${name}`. 캐시버스터 `?v=20260615-profile-icon-consistency`. **비변경**: 백엔드/RBAC/스키마/엔드포인트/icon 업로드·conn_status 경로 0(app.py `_list_products` name/product_key 분리 반환 — 조합은 프론트 전담). **검증**: node --check + CSS brace(1198) + **jsdom 격리 23/23 PASS**(`tests/verify_profile_icon_consistency.mjs` — identicon app↔admin byte-identical·결정론·드롭업 순서·Identicon 폴백·img 분기·명칭 7곳) + make test 컨테이너 **전체 회귀 0**(ruff clean, 2 skip, MAKE_EXIT=0). worktree `ai/claude/profile-icon-consistency`(base a9760ab=main). **잔여**: 머지 → web 재배포(`deploy_scope: included`) → PB-0008 Windows-browser 시각검증.

### Git 동기화 결과 (TASK-20260615T172210-profile-icon-consistency)
- 커밋: <cycle commit hash> (ai/claude/profile-icon-consistency, base a9760ab)
- verify-completion: <pre-commit 결과>
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Major(frontend-only 비파괴) + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동.
- 잔여: PB-0008(관리 콘솔 제품 Identicon·대화 드롭업 항목 순서/너비·명칭 `(약어) 명칭` 시각검증).

**2026-06-15 TASK-0270 — 계정 override 편집기 게이트: "허용" 및 "상속(허용)"(역할 부여) 시 자식 펼침** (REV-20260615-0270 [SKIPPED:ui-disclosure-gate-no-enforcement], **Minor §12.3**, frontend-only `src/static/admin.js` + 테스트/문서). 사용자 요청(역할 트리 완료 후): 계정 override 편집기에도 동일 tree(이미 renderPermissionGrid 공유로 적용) + 게이트가 **'허용' 또는 '상속(허용)'**(override 값이 상속이면서 역할이 그 권한을 부여)일 때 펼쳐지도록. **진단**: 기존 override `gateSatisfied = (value==="allow")` 만 — "상속"(inherit) 게이트는 역할이 부여해도 자식이 안 펼쳐짐(도달성 갭). **수정(admin.js)**: ① `_applyPermissionDisclosure(.., inheritedGrants)` + override `gateSatisfied = value==="allow" || (value==="inherit" && inheritedGrants.has(code))`. ② `renderPermissionGrid` opts 에 `inheritedGrants`(Set) 수용 + recompute 에 전파. ③ 계정 override 호출부: 계정 역할의 `permission_codes`(상속 baseline)로 `inheritedGrants` 구성해 전달. **상속 baseline 정확성**: 백엔드 계정 effective = `_apply_permission_overrides(role_permission_map, …)` 로 frontend `role.permission_codes`(=`_load_role_permission_codes`=WebRolePermissions, 자동부여 audit.read.own 도 seed 시 영속)와 **동일 출처** → role.permission_codes 가 정확한 상속 집합. **비변경**: 역할(checkbox) 모드 게이트(체크)·enforcement(권한 체크 code 기반)·override 저장 경로(select 값 그대로 읽음)·disclosure 가시성/도달성/트리 로직·RBAC 0. **검증**: `test_permission_dependency_map.py` **16 PASS**(신규 V7: 상속(허용)→펼침·상속(거부)→숨김·명시 거부 우선·허용 무관 펼침; override 포팅에 inherited 추가) + make test 컨테이너 **회귀 0**(exit=0) + node --check + **jsdom 실 DOM 8/8**(상속(허용)/상속(거부)/거부 우선/허용/운영 권한 list.own 상속허용). 캐시버스터 `?v=20260615-task0270-inherit-gate`. worktree `ai/claude/account-override-inherit-gate`(base 73755e9=main). **잔여**: 배포(web 만 — `deploy_scope: included`) + PB-0008(계정 override 편집기 상속(허용) 게이트 펼침 시각검증).

### Git 동기화 결과 (TASK-0270)
- 커밋: <cycle commit hash> (ai/claude/account-override-inherit-gate, base 73755e9)
- verify-completion: <pre-commit 결과>
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동.
- 잔여: PB-0008(계정 override 편집기 — 상속(허용) 게이트가 자식 펼침; TASK-0269 운영 권한 2그룹 트리 PB-0008 도 동반 기록).

**2026-06-15 TASK-0269 — 운영 권한 대화 그룹을 `내 대화 권한`/`전체 대화 권한` 2개로 분리 + "목록 조회" 게이트 카테고리 트리** (REV-20260615-0269 [SUBAGENT:rbac-adversarial] **SHIP**, **Minor §12.3**, frontend-only `src/{app.py,static/admin.js,static/app.js,static/admin.html,static/index.html}` + 테스트/문서). 사용자 요청(역할 권한 트리 후속): 운영 권한 대화를 `내 대화 권한`/`전체 대화 권한` 2그룹으로 분리하고, 기존 `.any→.own` 1:1 종속 대신 `대화 생성·조회(기반) > 요청 실행·제목 변경·삭제·중단 …(동작)` 카테고리로 묶기. 사용자 AskUserQuestion 확정: 게이트 = **목록 조회**. **수정**: ① (app.py) `PERMISSION_DEFINITIONS` 의 conversation 권한 `group` 을 코드 기반 분리 — `.any`(10) → `conversation_any`, 나머지(create/ask/list.own/*.own/share, 13) → `conversation_own`. 권한 code·label·description·enforce **불변**(group=UI 분류 메타만). ② (admin.js + app.js) `PERMISSION_GROUP_ORDER`/`LABELS`(내 대화 권한/전체 대화 권한)/`ADMIN_·WORK_SCREEN_PERMISSION_SECTIONS` operate 그룹 = [conversation_own, conversation_any, product, attachment] + app.js `permissionGroupOf`(.any→conversation_any/그외 conversation_own). ③ (admin.js) `PERMISSION_DEPENDENCIES` 재정의 — create/list.own/list.any = 루트(기반), 내 동작(read.own/ask/file.read.own/rename.own/delete.own/cancel.own/finalize.own/duplicate.own/share.create/attachment.*.own) → `conversation.list.own`, 전체 동작(*.any) → `conversation.list.any`. **동작**: 내 대화 목록 조회 체크 → 내 동작 노출, 전체 대화 목록 조회 체크 → 전체 동작 노출(트리·disclosure·도달성 보존은 TASK-0267/0264 로직 그대로 적용). **적대 리뷰 SHIP**(REV-0269 [SUBAGENT]): enforcement byte-identical(코드 불변·권한 체크는 group 아닌 code 기반)·group 소비자(catalog API·groupedPermissions·permissionGroupOf) 전부 새 문자열 graceful·신규 dep 무순환·cross-group stray 0·`GroupName VARCHAR(32)` 무절단·`ON DUPLICATE KEY UPDATE` 멱등(마이그 불요) 전부 refute. **검증**: `test_permission_dependency_map.py` **15 PASS**(M4 list 게이트·V2 운영 루트·T2 그룹 분리+게이트 중첩 갱신) + make test 컨테이너 **전체 회귀 0**(exit=0, 백엔드 RBAC 테스트 무회귀) + node --check(admin.js·app.js) + **jsdom 실 DOM 20/20**(2그룹 분리·라벨·list 게이트 내/전체·트리 depth·누락 0). 캐시버스터 `?v=20260615-task0269-conv-split`(admin.html·index.html). worktree `ai/claude/conv-perm-own-any-split`(base c34f0f9=main). **잔여**: 배포(web 만 — `deploy_scope: included`) + PB-0008(2그룹 분리·게이트 트리 시각검증).

### Git 동기화 결과 (TASK-0269)
- 커밋: <cycle commit hash> (ai/claude/conv-perm-own-any-split, base c34f0f9)
- verify-completion: <pre-commit 결과>
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동.
- 잔여: PB-0008(운영 권한 = 내 대화 권한/전체 대화 권한 2그룹, 각 "목록 조회" 게이트가 동작 권한 노출) + 후속 TASK-0270(계정 override 편집기 게이트 = 허용/상속(허용) 시 펼침).

**2026-06-15 TASK-0273 — 대화 삭제 → soft-archive(보관) + admin 조회 + 맥락 참조** (REV-20260615-0273 [SUBAGENT:archive-security] **SHIP**, **Critical §12.3** — 파괴적 삭제 동작 의미 변경 + 신규 admin 데이터 접근 + 스키마 마이그레이션, `app.py` + `agent_runtime_schema.sql` + alembic 0007 + `src/static/{app.js,admin.js,admin.html,styles.css,index.html}` + 신규 테스트). 사용자 요청: 대화 "삭제" → 해당 계정에서 안 보이는 보관 + 맥락 참조 + 오용 방지 admin 조회. **사용자 결정(AskUserQuestion 3)**: 보관=진행 차단(동결), admin 조회=신규 권한 `conversation.archive.read.any`, 맥락 참조=fork 게이트 완화. **스키마(3중 멱등, TASK-0248 동형)**: `core_conversations.archived_at`/`archived_by_account_id` — alembic `0007_core_conv_archived`(down=0006) + bootstrap SQL + app.py MySQL 폴백. **삭제→archive**: `_delete_conversation_impl` 가 `delete_conversation_records`(hard-delete: kv/core_conversations/fact_entries/rag_documents/rag_objects 전삭제) 대신 `_archive_conversation`(UPDATE archived_at, archived_at IS NULL 가드) 호출 — 데이터·MinIO 첨부 **보존**. 응답 키 deleted/deleted_pending 유지(프론트 호환). **목록 숨김**: `_list_conversations_pg`/`_list_conversations` 둘 다 `archived_at IS NULL`(소유자·admin 브라우징·검색·날짜 경로 공통). **진행 차단**: `_conversation_block_info` 가 blocked_at OR archived_at → /api/ask 403. **admin 조회**: 신규 권한(catalog + admin seed 자동 + admin catchup 명시) + `GET /api/admin/conversations/archived`(권한 게이트, 메타만[제목/소유자/일시/보관자], q bound param) + admin 콘솔 "보관 대화" 탭(권한 없으면 숨김). **fork 참조**: 접근/fork 경로에 archived 필터 없음 → 보관 대화 참조·복제 가능(사본은 정상 대화). 삭제 UI 라벨 "보관". **비변경**: 기존 RBAC 카탈로그(신규 1 권한만)·메시지 본문 경로 0. **검증**: 신규 `test_conversation_archive.py` **7 PASS** + 기존 block_conv 테스트 SQL 갱신 + make test 컨테이너 **전체 회귀 0**(ALL=0) + ruff + py_compile + node --check + **라이브 라운드트립**(archive→목록 숨김·PG archived_at/by 기록·/api/ask 403·admin 보관 조회 count=2). **라이브 검증이 2개 실 버그 포착·수정**: ① PG archived 컬럼 미적용(web DML-only role — superuser ALTER 필요), ② admin 권한 catchup 누락(신규 권한이 기존 admin 역할에 자동 grant 안 됨 → `_ensure_seed_roles` admin catchup 목록에 추가). **outside-voice 적대적 보안 리뷰 SHIP**(REV-0272, BLOCKER 0 — 데이터 보존 의도적·목록 숨김 전 경로·진행 차단·admin only·q bound·멱등 스키마 PASS; MINOR[deploy-order·count 드리프트] 비차단). [[feedback_outside_voice_for_rbac]]·[[feedback_sql_builder_live_pg_gate]] 정합. 캐시버스터 `?v=20260615-task0273-archive`. worktree `ai/claude/conversation-archive`(base f6ccb7b). **배포: migrate-first 필수**(alembic 0007 superuser 선행). **잔여**: 머지 → make migrate → web 재배포 → PB-0008.

### Git 동기화 결과 (TASK-0273)
- 커밋: <cycle commit hash> (ai/claude/conversation-archive, base 머지 후 origin)
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + `deploy_scope: included` → PR→머지→**make migrate(alembic 0007)**→web 재배포 자동. **migrate-first**(web DML-only).
- 잔여: 머지 후 라이브 migrate + 재배포 + PB-0008.

**2026-06-15 TASK-0267 — 권한 grid 트리(tree) UI 재구성: 2열 grid 뒤틀림 해소 + "더 보기 부여됨" 빨강 가시성** (REV-20260615-0267 [SKIPPED:ui-tree-layout-no-logic-change], **Minor §12.3**, frontend-only `src/static/{admin.js,styles.css,admin.html}` + 테스트/문서). 사용자 보고(`관리 권한` 정상 확인 후 `운영 권한` 테스트 중): ① 도달성 보존 "더 보기 · N개 부여됨" 빨강 하이라이트가 운영 권한에서 안 보임 ② 항목 숨김 시 기존 항목이 **뒤틀림** → 상위 권한에 **tree 형태 UI** 요청. **진단**: `.permission-grid-list` 가 `display:grid; grid-template-columns: repeat(2, ...)`(2열) — 행 숨김 시 남은 항목이 2열로 재배치(가로 reflow)돼 뒤틀림. 빨강 badge 는 **로직·CSS 정상**(라이브 실측 checkbox/override 둘 다 `rgb(180,35,31)`)이나 2열 뒤틀림에 "더 보기" 버튼이 묻혀 안 보인 것. **수정**: ① (admin.js) 신규 `_orderItemsAsTree(items)` — 그룹 내 권한을 `PERMISSION_DEPENDENCIES` 트리 DFS 순서(부모 먼저, 자식 들여쓰기)로 정렬, 각 row 에 `data-perm-depth`. 그룹 내 루트=depth 0(부모 없음 / 부모가 다른 그룹, 예: account.read 부모 console.access), 자식=depth+1. 누락 안전망(렌더 누락 0). ② (styles.css) `.permission-grid-list` 를 **2열 grid → 단일 열 flex column** + depth 들여쓰기(`[data-perm-depth="1"] margin-left` + 좌측 가이드 border + 가로 tick 연결선) → 자식 숨김 시 부모는 제자리, **가로 reflow 0**(뒤틀림 해소). `.permission-group-more` 를 flex(grid-column 제거 → align-self) 로, 구 `.permission-row-dependent` accent 제거(depth 기반 대체). **비변경**: disclosure 가시성·게이트·도달성(그룹 유지/배지)·저장 경로·`has-granted` 빨강 CSS·RBAC·엔드포인트 0(순수 렌더 순서+레이아웃). **검증**: `test_permission_dependency_map.py` **15 PASS**(기존 11 + 신규 T1~T4: 트리 정렬 부모-자식 순서·depth 정합·own→any 중첩·account.read 루트·grid-list 단일열 CSS 계약) + make test 컨테이너 **회귀 0**(exit=0) + node --check + CSS brace(1167) + **jsdom 실 DOM 14/14**(트리 순서·depth·누락0·숨김 시 부모 순서 유지). 캐시버스터 `?v=20260615-perm-tree-ui`. worktree `ai/claude/perm-tree-ui`(base f0279c3=main). **잔여**: 배포(web 만 — `deploy_scope: included`) + PB-0008(단일 열 트리·들여쓰기·운영 권한 "부여됨" 빨강 가시성 시각검증).

### Git 동기화 결과 (TASK-0267)
- 커밋: <cycle commit hash> (ai/claude/perm-tree-ui, base f0279c3)
- verify-completion: <pre-commit 결과>
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동.
- 잔여: PB-0008 — 트리(단일 열) 레이아웃·자식 들여쓰기·운영 권한 "더 보기 · N개 부여됨" 빨강 가시성·뒤틀림 0 실측.

**2026-06-15 TASK-0268 — 사용자 프로필 / 제품 아이콘 이미지 + Identicon 기본** (동시세션 TASK-0267[perm-tree] 선점으로 0267→0268 재번호; REV-20260615-0268 [SUBAGENT:image-upload-security] **SHIP**, **Major §12.3** — 신규 스키마 컬럼 2 + 이미지 업로드/서빙 엔드포인트 6, `src/app.py` + `src/static/{app.js,admin.js,styles.css,index.html,admin.html}` + 신규 테스트). 사용자 요청: 프로필 이미지·제품 아이콘 설정 가능 + 기본은 Identicon/Gravatar. **사용자 결정(AskUserQuestion)**: Gravatar 미사용(email 컬럼 없음·외부 의존 0) → **Identicon 단독**, **프론트 생성**. **백엔드**: ① WebAccounts.AvatarObjectKey + WebProducts.IconObjectKey 멱등 ALTER — slow path(`_ensure_web_tables`) **및** fast-path(`_ensure_seed_catchup`→신규 `_ensure_avatar_icon_schema`) 양쪽(운영 재기동은 fast-path 만 타므로 한쪽만 두면 'Unknown column' — **라이브 검증서 포착·수정**, [[feedback_sql_builder_live_pg_gate]] 적중). ② `_serialize_account`→`avatar_url`, `_list_products`→`icon_url`(object key sha256 캐시버스터). ③ 엔드포인트: `PUT/DELETE /api/auth/me/avatar`(self-service 로그인만) + `GET /api/avatars/{id}`, `PUT/DELETE /api/admin/products/{id}/icon`(product.manage) + `GET /api/products/{id}/icon`. MinIO prefix `avatars/<id>/`·`product-icons/<id>/`(uuid+ext — 파일명 미사용→traversal 0). ④ `_sniff_image`(매직바이트 png/jpg/webp만, **클라 MIME 불신**, SVG/GIF 거부=XSS 차단) + 크기 cap(아바타 2MB/아이콘 5MB) + `_serve_image_object`(content-type 역추론 + `nosniff` + `inline`). **프론트**: `identiconSvg(seed)`(해시 5x5 대칭 SVG, 외부 의존 0·결정론적) + `applyAvatar`(이미지 or Identicon, onerror 폴백) — 사이드바·드로어·제품 드롭업·admin 제품 상세 적용 + 업로드/제거 UI. **비변경**: 기존 RBAC(product.manage 재사용, 신규 권한 0)·기존 엔드포인트·메시지 경로 0. email/Gravatar 미도입. **검증**: 신규 `test_avatar_icon_upload.py` **8 PASS**(매직바이트·SVG/거짓MIME 거부·크기·object key·URL 헬퍼·서빙 content-type·권한 403) + make test 컨테이너 **전체 회귀 0**(PYTEST_EXIT=0) + ruff + node --check + CSS brace(1175=1175) + **Playwright 격리**(Identicon 결정론·구분·렌더) + **라이브 라운드트립**(PNG 업로드→`/api/avatars/1?v=...`→서빙 200 image/png·nosniff, SVG 거부, 삭제→null; fast-path 스키마 누락 버그 라이브서 포착·수정). **outside-voice 적대적 보안 리뷰 SHIP**(REV-0268, BLOCKER 0 — SVG차단·MIME불신·traversal 0·본인강제·권한게이트·멱등스키마 PASS; MAJOR[nosniff]는 1줄 흡수). [[feedback_outside_voice_for_rbac]] 정합. 캐시버스터 `?v=20260615-task0268-avatar`. worktree `ai/claude/profile-product-avatar`(base f6ccb7b=main). **잔여**: 배포(web) + PB-0008.

### Git 동기화 결과 (TASK-0268)
- 커밋: <cycle commit hash> (ai/claude/profile-product-avatar, base f6ccb7b)
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동. app.py(스키마 ALTER + 엔드포인트) + 정적자산 → web 재빌드만.
- 잔여: 정식 배포 후 라이브 재확인(임시 복사본 → 정식 이미지) + PB-0008.

**2026-06-15 TASK-0266 — TASK-0263 핫픽스: usage/conversations 의 interval 파라미터 PG 문법 오류** (동시세션 TASK-0264/0265 선점으로 0265→0266 재번호; **Minor §12.3**, `src/app.py` 1줄 + 회귀 가드 테스트). TASK-0263 배포(머지 후 web 재빌드) 직후 `GET /api/admin/usage/conversations` 가 **HTTP 500** — web 로그 `psycopg.errors.SyntaxError: syntax error at or near "$1" ... interval $1`. **근본 원인**: `_query_usage_conversations` 가 `now() - interval %s`(params=`["{days} days"]`)로 days 를 파라미터화했는데, PG 는 `interval` 키워드 뒤 파라미터 placeholder(`interval $1`)를 **불허**(문자열 리터럴 문법만 허용). admin_llm_usage 는 `interval '{days} days'`(int 보간, days 는 clamp 라 안전)라 무관했으나, 핫스팟에서 파라미터화하려다 문법 위반. **단위 테스트(fake cursor)는 SQL 을 실제 실행하지 않아 통과**시켰고 — **라이브 엔드포인트 검증(실 PG)에서만 포착**. **수정(app.py 1줄)**: `now() - interval %s` → `now() - %s::interval`(캐스트 문법은 파라미터 허용, days 바인드 유지 — 다른 win 패턴 무변경). **회귀 가드**: `test_q2b_interval_cast_not_bare_param`(생성 SQL 에 `%s::interval` 존재 + bare `interval %s` 부재 정적 검증). **검증**: test_usage_conversations.py **12 PASS**(기존 11 + 가드) + py_compile + **라이브 검증**(worktree app.py 임시 web 적용: admin 전체 34건 HTTP 200·좌표/본문 누출 0, 일자 차원 필터 2026-06-15 1건·차트 by_day 정합, profile 200). **교훈**: SQL 빌더 변경은 fake cursor 단위테스트로 불충분 — **라이브 엔드포인트(실 PG) 검증을 게이트화**([[feedback_frontend_real_browser_gate]] 의 백엔드 판). worktree `ai/claude/usage-conv-interval-fix`(base 9ce9ea7=main). **잔여**: 정식 web 재빌드(현재 임시 복사본 실행 중) + PB-0008.

### Git 동기화 결과 (TASK-0266)
- 커밋: <cycle commit hash> (ai/claude/usage-conv-interval-fix, base ac7c1a2)
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Minor 핫픽스 → PR→머지→cleanup→web 재배포 자동.
- 잔여: 정식 배포 후 라이브 재확인(임시 복사본 → 정식 이미지).

**2026-06-15 TASK-0263 — LLM 사용량 차트 hover 비용 + 클릭→집계 기여 대화목록 모달** (REV-20260615-0263 [SUBAGENT:security-adversarial] **SHIP**, **Major §12.3** — 신규 read 엔드포인트 2개 + admin 타 사용자 대화 메타 인가 표면, `src/app.py` + `src/static/{admin.js,app.js,styles.css,index.html,admin.html}` + 신규 테스트). 사용자 요청: 사용량 차트에 (a) hover 시 모델별 비용 표시, (b) 클릭 시 그 집계 사용량의 대화목록 표시 — 작업 화면 프로필 + 관리 콘솔 양쪽. **사용자 결정(AskUserQuestion)**: 대화목록=**모달/드로어 패널**, admin 범위=**기존 권한 재사용**(신규 RBAC 0). **현황 진단**: admin 도넛은 이미 hover 비용 있음·역할 막대는 계정 drill-down 만(대화목록 아님), 일별 차트·프로필은 비용·클릭 전무, "집계→대화목록"은 양쪽 신규. **백엔드(app.py)**: ① 신규 `GET /api/admin/usage/conversations`(console.usage.read **AND** conversation.list.any — 사용량 권한만으론 타 계정 대화 제목 노출 차단) + `GET /api/profile/usage/conversations`(로그인, owner=self 강제·role/account_id 파라미터 무시로 권한 상승 차단). ② `_query_usage_conversations`: `llm_usage ⋈ core_conversations`(INNER JOIN + `conversation_id IS NOT NULL` — insight/시스템 비대화 usage 제외)로 차원 필터(model=`COALESCE(resolved,model)` / account_ids(역할 역매핑) / day=`to_char(date_trunc(gran))` / owner)된 대화별 호출·토큰·비용·models[] fold. 차원 SQL 은 `admin_llm_usage` 집계와 **동일 규칙**(차트 수치↔대화목록 정합). 좌표/비번/메시지 본문 비노출(메타만), `_USAGE_CONV_LIMIT=200`+truncated. ③ `_usage_account_ids_for_role`(시스템→None·역할없음·역할명), `_enrich_usage_conv_owner_meta`(admin 만 owner 사용자명/역할). ④ by_day_model·by_model 에 `cost_usd` 추가(hover 비용), profile totals.cost_usd. **프론트**: admin.js renderStacked(일별)·renderStackedHBar tooltip 에 모델별 비용 병기 + 차트 요소 `data-usage-model/day` 후크 + `bindUsageDrill`·`openUsageConversations`·`showUsageConvModal`(deep-link `/?conversation=`). 계정 drill 행 클릭→대화 모달. app.js renderProfileUsageStacked/Donut `<title>`에 비용 + 클릭 후크 + 본인 전용 모달 + 추정비용 카드 + `initializeWorkspace` 가 `?conversation=` deep-link 선호 활성화. styles.css usage-conv 모달(admin 넓은 판 + profile 독립 판). **비변경**: RBAC 카탈로그·스키마·기존 엔드포인트 shape(필드 추가만)·메시지 본문 경로 0. **검증**: 신규 `test_usage_conversations.py` **11 PASS**(대화별 fold·INNER JOIN·차원 WHERE/params·좌표 비노출·빈 account 단락·admin AND 게이트 403×2·시스템역할 빈목록·profile 권한상승 차단·역할→계정 역매핑) + make test 컨테이너 **전체 회귀 0**(PYTEST_EXIT=0) + ruff clean + node --check app.js/admin.js + CSS brace(1156=1156) + py_compile + **Playwright 격리**(차트 막대 클릭→model/day 차원 추출→모달 opener). **outside-voice 적대적 보안 리뷰 SHIP**(REV-0263, BLOCKER/MAJOR 0 — SQLi 0[파라미터화+화이트리스트 gran/fmt], AND-게이트, profile self-scope, 메타only+admin-only owner enrich, INNER JOIN+NULL 가드, 차트정합; MINOR 1[대형 역할 wide IN — admin 신뢰경로]). [[feedback_outside_voice_for_rbac]] 정합. 캐시버스터 `?v=20260615-task0263-usage-drill`. worktree `ai/claude/usage-drilldown-conversations`(base 05592b0... TASK-0261 머지 후 fe87981 위). **잔여**: 배포(web) + 라이브 엔드포인트 검증 + PB-0008.

### Git 동기화 결과 (TASK-0263)
- 커밋: <cycle commit hash> (ai/claude/usage-drilldown-conversations, base fe87981)
- verify-completion: <pre-commit 결과>
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동. app.py(read 엔드포인트) + 정적자산 → web 재빌드만(ask/insight-worker 무변경).
- 잔여: 라이브 엔드포인트 검증(차원 필터 대화목록 반환) + PB-0008(차트 hover 비용·클릭 모달·deep-link).

**2026-06-15 TASK-0264 — 권한 disclosure 추가 단순화: 게이트 미충족 시 부여된 세부 권한도 "더 보기" 뒤로 숨김(forceVisible 제거)** (REV-20260615-0264 [SUBAGENT:rbac-adversarial] SHIP-WITH-FIXES→흡수→SHIP, **Minor §12.3**, frontend-only `src/static/{admin.js,styles.css,admin.html}` + 테스트/문서). 사용자 보고: "`세부 권한 N개 더 보기` 를 클릭하지 않아도 기본적으로 항목이 노출되는 버그 — 최대한 단순화하여 숨겨지도록". **원인**: TASK-0257 의 비파괴 `forceVisible`(부여된 권한+조상을 게이트 OFF 라도 항상 표시)이, 게이트 OFF 인데 일부 세부 권한이 부여된 역할에서 그 부여 항목을 "더 보기" 클릭 없이 노출(사용자가 이전 AskUserQuestion 에서 "비파괴" 를 택했으나 실사용 후 "최대한 숨김" 으로 전환). **수정(admin.js)**: `_applyPermissionDisclosure` 에서 `forceVisible` 제거 → row 는 **게이트 체인이 충족(선행 권한 모두 양성)돼야만** 노출(부여 여부 무관). 게이트 reveal(`계정 조회` 체크 → 나머지 표시)·마스터 게이트(`관리 콘솔 접근`)·own→any 는 불변. **부여 항목 도달성 보존**(적대 리뷰 안전속성): `_refreshGroupDisclosure` 가 부여 항목이 있는 그룹은 게이트 OFF 라도 **vanish 안 함**(`grantedCount>0`) + "더 보기 · N개 부여됨"(`.has-granted` 강조) 표면화 → 부여된 권한이 영구히 가려지지 않고 "더 보기" 로 도달, 그룹 헤더 `N/M 선택` 카운트도 부여 수 노출. 저장 경로(`querySelectorAll(':checked')`/select)는 hidden row 도 그대로 읽어 **저장 누락 0**. orphan 경고칩(`_setPermOrphanWarn`/`_permLabel`)은 부여+게이트OFF 행이 이제 숨겨져 무의미 → 제거. **적대 리뷰 SHIP-WITH-FIXES → 흡수**: 안전 카테고리(부여 도달불가/저장누락/섹션숨김trap/리스너중복/게이트시맨틱) **전부 refute**; MINOR 1건 흡수 — **계정 override 편집기는 컨테이너가 `.override-grid`(≠`.permission-grid`)라 TASK-0258 의 `.permission-grid [data-perm-code][hidden]` 강제 규칙이 override 행에 미적용**(`.field{display:flex}` 가 `[hidden]` override → 안 숨겨짐) → CSS 셀렉터를 컨테이너 무관 `[data-perm-code][hidden]` 로 unscope(test_c1 도 unscoped 검증으로 강화). **검증**: `test_permission_dependency_map.py` **11 PASS**(V1/V4/V5/V6 새 동작: 게이트 OFF 부여 항목 숨김 + 게이트 충족 시 도달; C1 unscoped CSS 계약) + make test 컨테이너 **전체 회귀 0**(exit=0) + node --check + CSS brace(1130=1130) + **jsdom 실 DOM 17/17**(부여 account.delete 게이트OFF 숨김·그룹 유지·"부여됨" 배지·더보기 클릭 도달·저장 누락0·override). 캐시버스터 `?v=20260615-perm-collapse-granted`. worktree `ai/claude/perm-disclosure-collapse-granted`(base 033ec9d=main). **잔여**: 배포(web 만 — `deploy_scope: included`) + PB-0008(계정 override 모드 행 숨김 computed display 실측 포함).

### Git 동기화 결과 (TASK-0264)
- 커밋: <cycle commit hash> (ai/claude/perm-disclosure-collapse-granted, base 033ec9d)
- verify-completion: <pre-commit 결과>
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동.
- 잔여: PB-0008 — 게이트 OFF 시 부여 세부 권한도 숨김 + "더 보기 · N개 부여됨" + 계정 override 모드 행 computed display:none 실측.

**2026-06-15 TASK-0261 — 대화 화면 제품 드롭업 datasource 네트워크 상태 배지** (**Minor §12.3**, `src/app.py` + `src/static/{app.js,styles.css,index.html}` + 신규 테스트). 사용자 요청: 대화 화면 제품 선택 드롭업의 제품 dot 이 "현재는 회색, 파란색만 표시 중" → datasource 연결 상태를 반영. **진단**: dot 은 지금까지 **모드 표시**(auto=회색/`--text-muted`, pinned=파랑/`--primary`)일 뿐 네트워크 상태와 무관했다. conn-health-monitor(TASK-0250)가 admin 콘솔엔 `conn_status` 를 주지만 대화 화면 제품 목록(`_list_products`)엔 미첨부였음. **수정(백엔드)**: 신규 `_attach_product_conn_status(conn, products)` — conn_health 모니터의 사전계산 `snapshot()`(추가 probe 없음)을 `datasources.resolve(key)→scope_key` 로 매핑(admin 의 `all_datasources→scope_key` 와 동일 키)해 각 product 의 `datasources[]` 항목에 `conn_status`{status,elapsed_ms,checked_at} 첨부 + product 레벨 `conn_status_overall`(바인딩 **최악 상태**: unstable>unknown>healthy). 좌표/비밀번호 비노출(status/elapsed/checked_at 만). conn_health 미가용·resolve 실패 graceful(unknown), 바인딩 없는 기본 단일 MySQL 제품은 overall=None. `/api/session`·`/api/auth/me` 두 대화 부트스트랩 호출 직후에만 enrich(admin 경로 _list_products 무영향). **수정(프론트)**: `buildProductDropupItem` 이 `connStatusOverall` 을 받아 dot 에 `.product-dropup-item-dot--conn`+`.is-ok/.is-fail/.is-unknown` 클래스 + title/aria-label. `connStatusMeta(status)` 헬퍼(healthy→연결됨/초록, unstable→연결 불안정/빨강, unknown→상태 확인 중/중립). datasource 배지 tooltip 에 각 datasource 상태 라벨 병기. styles.css 에 conn 상태 dot 색(selector specificity 0,3,0 > 모드 규칙 0,2,0 → 모드색 override). **비변경**: RBAC·스키마·엔드포인트 shape(응답 필드 추가만)·conn_health 모니터·share 0. **검증**: 신규 `test_product_conn_status.py` **8 PASS**(단일 healthy / 멀티 최악 unstable / unknown 우선순위 / 바인딩없음 None / 좌표 비노출 / graceful×2 / 빈목록) + make test 컨테이너 **전체 회귀 0**(PYTEST_EXIT=0) + ruff clean + node --check app.js + CSS brace(1128=1128) + py_compile. **Playwright headless chromium 격리**(healthy=초록 rgb(22,163,74)/unstable=빨강 rgb(220,38,38)/unknown=중립/바인딩없음=pinned 파랑 유지 — CSS override 실증) — [[feedback_frontend_real_browser_gate]]. 라이브 conn_health 실측(mysql-kr-an2-*=unstable, mysql-local/mssql-*=healthy)으로 enrich 소스 유효 확인. 캐시버스터 `?v=20260615-task0261-conn-badge`. worktree `ai/claude/product-conn-badge`(base 05592b0=main). **잔여**: 배포(web 재빌드) + PB-0008 Windows 시각검증(드롭업 dot 색이 상태 반영).

### Git 동기화 결과 (TASK-0261)
- 커밋: <cycle commit hash> (ai/claude/product-conn-badge, base 05592b0)
- verify-completion: <pre-commit 결과>
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동. app.py(read-only enrich) + 정적자산 변경 → web 재빌드만(ask/insight-worker 무변경).
- 잔여: PB-0008 — 드롭업에서 unstable datasource 제품 dot=빨강, healthy=초록 확인(실브라우저).

**2026-06-15 TASK-0260 — 답변 결과셋 ◀▶ 전환 시 확장 높이 보존(스크롤 점프 제거)** (**Minor §12.3**, frontend-only `src/static/{app.js,share.js,index.html,share.html}`). 사용자 보고: assistant 답변 안에서 결과셋을 ◀▶ 버튼으로 전환할 때, 결과셋마다 높이가 달라 스크롤 위치가 jump. **근본 원인**: `buildSqlNavigator` 의 `.sql-nav-panels` 가 min-height 없이 display 토글(`.is-active`)만 해서, 활성 패널 높이로 컨테이너가 매 전환 재조정 → `.result-table-wrap` 의 `max-height: min(60vh,460px)` 때문에 결과셋별 높이 편차가 커 큰 결과셋(예 460px)→작은 결과셋(예 40px) 전환 시 컨테이너가 급격히 줄며 아래 콘텐츠가 위로 점프. **수정(app.js + share.js)**: navigator 인스턴스별 `maxPanelHeight` 추적 + `preserveHeight()`(panels.scrollHeight 가 더 크면 `panels.style.minHeight` floor 갱신). `update()` 가 전환 **전(나가는 패널)·후(들어오는 패널)** 2회 측정 → 지금까지 본 최대 높이를 바닥으로 박아 **축소만 방지·확장은 허용**. 초기 `update()` 는 DOM attach 전이라 scrollHeight=0 → floor 무변(무해). **비변경**: CSS(styles.css/share.css) 0 — min-height 는 JS inline 동적 설정. 백엔드/스키마/RBAC/엔드포인트 0. **검증**: `node --check` app.js/share.js PASS + **Playwright headless chromium 격리 검증**(buildSqlNavigator 핵심 로직 동형 재현: 큰 1000px→작은 2행 전환 시 panels.h 불변[minHeight=1000px floor]·아래콘텐츠 점프 **0px**; **수정 전 대조 = 960px 점프** 재현으로 회귀 가드 유효성 확인) — [[feedback_frontend_real_browser_gate]] 정합. 캐시버스터 `?v=20260615-task0260-sqlnav-height`(index.html app.js·share.html share.js). worktree `ai/claude/sqlnav-height-preserve`(base 038cacb=main). **잔여**: 배포(web 만 — frontend) + PB-0008 Windows 시각검증(CHECK#13 WARN-only).

### Git 동기화 결과 (TASK-0260)
- 커밋: <cycle commit hash> (ai/claude/sqlnav-height-preserve, base 038cacb)
- verify-completion: <pre-commit 결과>
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동. frontend-only(JS) 라 web 재빌드만.
- 잔여: 최종 PB-0008 — 다중 결과셋 답변에서 ◀▶ 전환 시 스크롤 점프 없음(실브라우저).

**2026-06-15 TASK-0258 — TASK-0257 핫픽스: 권한 disclosure 의 hidden row 가 실브라우저에서 안 숨겨지던 CSS override 버그** (**Minor §12.3**, frontend-only `src/static/{styles.css,admin.html}` + 회귀 테스트). TASK-0257 배포 후 **PB-0008 Windows-browser 시각검증 중 발견**: 마스터 게이트 그룹 vanish(`.permission-group[hidden]`)는 정상이나, **within-group 행 게이팅이 실브라우저에서 무력**(예: `관리 콘솔 접근` 체크 후 `계정 조회`만 보여야 하는데 계정 권한 7개가 다 보임). **근본 원인**: `.permission-toggle-card{display:flex}`(author rule, specificity 0,1,0)가 UA 의 `[hidden]{display:none}`(0,1,0)를 **동일 specificity·후순위로 override** → JS 가 `el.hidden=true` 를 줘도 computed `display:flex` 라 행이 계속 렌더. eval 은 `.hidden===true` 를 읽어 정상으로 보였고, **jsdom 은 CSS 캐스케이드/렌더링이 없어 30/30 통과**시킴 → **실브라우저(PB-0008)만 검출 가능한 클래스**([[feedback_visual_verify_on_design_change]]·TASK-0236 교훈 입증). **수정(styles.css 1규칙)**: `.permission-section[hidden], .permission-group[hidden], .permission-grid [data-perm-code][hidden] { display:none !important; }` — disclosure 의 section/group/row 모든 숨김 대상에 display:none 강제(프로젝트 기존 `.search-modal-overlay[hidden]{display:none}` 선례와 동형). 캐시버스터 `?v=20260615-perm-disclosure-hidefix`. **검증**: 신규 회귀 가드 `test_c1_hidden_rows_force_display_none`(styles.css 에 `[data-perm-code][hidden]` display:none !important + group/section 규칙 존재 정적 검증) 포함 **11 PASS**(기존 10 + C1) + make test 컨테이너 **전체 회귀 0**(make exit=0) + CSS brace(1125=1125) + **실브라우저 수정 CSS 주입 후 computed display 재확인**(account.read=flex, 나머지 6개=none, 표시 1개). **잔여**: 배포(web 만 — `deploy_scope: included`) + 최종 PB-0008 확인. worktree `ai/claude/perm-disclosure-hidden-css`(base 4782fd3=main, TASK-0257 직후).

### Git 동기화 결과 (TASK-0258)
- 커밋: <cycle commit hash> (ai/claude/perm-disclosure-hidden-css, base 4782fd3)
- verify-completion: <pre-commit 결과>
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동. frontend-only(CSS) 라 web 재빌드만.
- 잔여: 최종 PB-0008 — `관리 콘솔 접근` 체크 후 계정 그룹에서 `계정 조회`만 보이고 나머지 접힘(실브라우저 display:none 확인).

**2026-06-15 TASK-0257 — 관리 콘솔 계정·역할 권한 편집기 점진적 세분화(progressive disclosure)** (REV-20260615-0257 [SUBAGENT:rbac-adversarial] SHIP-WITH-FIXES→흡수→**SHIP**, **Major §12.3** (권한 편집 surface), frontend-only `src/static/{admin.js,styles.css,admin.html}` + `docs/CONVENTIONS.md` §10.6 + 신규 테스트). 사용자 요청: `관리 콘솔 > 계정, 역할 > [각 항목]` 의 카테고리별 권한 UI 를 종속성 기반으로 점진적으로 세분화 — `관리 콘솔 접근(console.access)` 체크 시 관리 권한 내부 항목 표시, `계정 조회(account.read)` 체크 시 나머지 계정 권한 표시, 운영 권한도 동일, **UI 뒤틀림 방지**. **설계**: 선언적 종속성 맵 `PERMISSION_DEPENDENCIES`(child→선행 parent, 31엔트리) — 관리 권한 section 은 `console.access` 가 **마스터 게이트**(account.read/role.read/audit.read.own/system_prompt.global.read 의 부모=console.access → OFF 시 계정·역할·감사·설정 그룹 통째 vanish), 각 그룹 base 가 세부 권한 게이트; 운영 권한은 마스터 게이트 없이 `.any`(전체)→`.own`(내) 종속. **비파괴(사용자 확정)**: 이미 부여된(체크/override 허용·거부) 권한과 그 조상은 게이트 무관 **항상 표시**(forceVisible 조상 마킹), disclosure 는 row 를 *접을* 뿐 *제거*하지 않고 저장 경로(`querySelectorAll('input:checked')`)는 hidden row 도 그대로 읽음 → 권한 조용한 회수 0. 각 그룹 "세부 권한 N개 더 보기" 로 강제 노출 + orphan 경고칩(부여됐으나 게이트 OFF — checkbox 모드). **§10.6 정합**: section/group 정렬·DOM 구조 불변, row 단위 hidden 토글로만 동작(레이아웃 뒤틀림 0, reveal 즉시 토글·애니메이션 없음). **mode 분기(적대 리뷰 MAJOR 흡수)**: 그룹/섹션 통째 vanish 는 checkbox(역할) 모드만 — 마스터 게이트 체크박스가 항상 보이는 복원 레버라 trap 없음; override(계정) 모드는 게이트 select 가 그 자신도 접힐 수 있어 그룹 vanish 시 "더 보기" 탈출구까지 사라져 도달 불가 → **그룹/섹션 비숨김**(§10.6 "전체 표시" 정합) + row 만 접고 "더 보기" 항상 도달 가능. **outside-voice 적대 리뷰(REV-0257)**: SHIP-WITH-FIXES — #1 안전속성(부여 권한 미숨김·저장 누락 0) **400k fuzz refute**, 저장경로/perf/제품그룹/맵정합/§10.6 정렬 전부 refute; MAJOR(override 그룹 도달불가 trap) + MINOR(dead branch) 흡수. **비변경**: 백엔드 RBAC enforce·권한 code·persistence·엔드포인트·스키마 0(순수 편집기 표시 UX). **검증**: 신규 `test_permission_dependency_map.py` **10 PASS**(맵 정합 M1~M4 + 가시성 불변식 V1~V6 — 비파괴/마스터게이트/own→any/orphan/override) + make test 컨테이너 **전체 회귀 0**(진행 100%·skip 2·F/E 0·make exit=0)+ruff clean + node --check + CSS brace(1113=1113) + **jsdom 실 DOM 검증 30/30**(마스터게이트 vanish·그룹 reveal·intra-group 게이팅·orphan 칩·저장경로 안전·override no-vanish·"더 보기" 도달/클릭). 캐시버스터 `?v=20260615-perm-disclosure`. worktree `ai/claude/perm-progressive-disclosure`(base f8845cc=main). 동시세션 번호충돌 대비 머지 직전 origin/main 재확인(origin max=0256(diff 작업 선점)→0257).

### Git 동기화 결과 (TASK-0257)
- 커밋: <cycle commit hash> (ai/claude/perm-progressive-disclosure, base f8845cc)
- verify-completion: <pre-commit 결과>
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동 진행. ask/insight-worker 코드 무변경(frontend-only)이라 web 재빌드만으로 충분.
- 잔여: PB-0008 Windows-browser 시각검증(역할: console.access 체크→그룹 등장·account.read 체크→세부 노출; 계정 override: 그룹 비숨김·더 보기 도달) — 배포 후.

**2026-06-15 TASK-0254 — 제품 프롬프트 '자동 작성' 스트리밍 스크롤 stick-to-bottom** (REV-20260615-0254 [SUBAGENT:frontend-adversarial] SHIP-WITH-FIXES→흡수→**SHIP**, **Minor §12.3**, frontend-only `src/static/admin.js`). 사용자 보고: `관리 콘솔 > 제품 > [항목] > 제품 프롬프트` 의 '자동 작성'(TASK-0237 SSE 토큰 스트리밍) 동작 중, 작성되는 본문 상단을 읽으려 위로 스크롤해도 텍스트가 갱신될 때마다 스크롤이 최하단으로 끌려감. 요구: 갱신 중에도 스크롤을 자유롭게 둘 수 있게 + 최하단일 때만 갱신을 따라 내려가게. **진단**: `handleFrame` 의 `token` 분기가 매 토큰마다 무조건 `textarea.scrollTop = textarea.scrollHeight`. **수정(admin.js)**: `token` 분기는 append **직전** `atBottom = scrollHeight - scrollTop - clientHeight <= 8`(8px=분수픽셀/clamp 오차) 판정 → append 후 `atBottom` 일 때만 최하단 추종(위로 스크롤 상태면 위치 유지). 첫 토큰은 `value=""` 직후 빈 상태→atBottom=true→정상 추종, 비-오버플로 상태는 `scrollHeight==clientHeight`→항상 atBottom→수동 관찰 무회귀. `done` 분기는 서버 `done.prompt`(app.py:16519 `.strip()`)가 누적(un-stripped)과 길이 달라질 수 있어 동일하면 재할당 생략 + `maxTop=max(0,scrollHeight-clientHeight)` clamp(`atBottom?maxTop:min(prevTop,maxTop)`)로 재할당發 점프 흡수. 캐시버스터 `?v=20260615-task0254-prompt-stream-scroll`. **outside-voice 적대 리뷰(REV-0254)**: NOT-SHIP 0 — 첫토큰/8px 임계/측정 순서/비-오버플로 무회귀 전부 반박, LOW 1건(done strip 길이차 점프) 흡수. **비변경**: SSE 백엔드 계약·프레임 파싱·abort·pending 저장·meta 표시·styles.css 0(순수 클라이언트 렌더). **검증**: `node --check`(admin.js) PASS + 서버 `.strip()` 사실 확인(app.py:16519) + make test 컨테이너 **회귀 0 PASS**(진행 100%·skip 2·fail/error 0·make exit=0)+ruff clean + verify-completion 9 checks PASS(CHECK#13 WARN=PB-0008 후속). worktree `ai/claude/task0254-prompt-stream-scroll`(base 9c9a5b3=main).

### Git 동기화 결과
- 커밋: <PR push 시 cycle commit hash> (ai/claude/task0254-prompt-stream-scroll, base 9c9a5b3)
- verify-completion: PASS (pre-commit, feature-0003-agent-web-ui — 9 checks, CHECK#13 WARN=PB-0008 후속)
- Push / PR / main 병합 / 배포: 자동 동기화 정책 §16.3 — BLOCKED 없음 + Minor + `deploy_scope: included` → PR→머지→cleanup→web 재배포 자동 진행. ask/insight-worker 코드 무변경(frontend-only)이라 web 재빌드만으로 충분.
- 잔여: PB-0008 Windows-browser 시각검증(스트리밍 중 위로 스크롤 유지 / 최하단 추종) — 배포 후.

**2026-06-12 TASK-0253 — 관리 콘솔 head-of-line blocking 2건 제거** (REV-20260612-0253 [SUBAGENT:concurrency+SSRF-adversarial] SHIP-WITH-FIXES→흡수→**SHIP**, **Minor §12.3**, frontend+backend). TASK-0250 배포 후 PB-0008 시각검증 중 사용자 발견 2건. **(A) datasource ↻ 새로고침 지연**: 제품 상세 "+ 데이터소스 추가" 드롭다운 ↻ 클릭 시 N개 배지가 "확인 중…"에 9초+ 묶임. 진단(브라우저 실측): 개별 `/test` 45~194ms 인데 동시 11개 시 8~18s. 원인 = `admin_test_datasource`(async def)가 동기 블로킹 `_db.probe_datasource()`(도달불가 시 connection_timeout 8s 점유)를 await/executor 없이 직접 호출 → **이벤트 루프 블로킹** → 동시 /test 직렬화 + 프론트 refresh 가 같은 key 를 force:false(rebuild)+force:true(Promise.all) **2벌** probe(4-cap 세마포어 2배 점유). **(B) 제품 분석 완료율 일괄 대기**: 진입 시 좌측 제품 목록·우측 "insight 분석 완료율"·DB 행 전부 "분석 측정 중…"이 가장 느린 제품 라이브 DB 조회까지 끝나야 한꺼번에 갱신(빠른 제품 개별 즉시표시 안 됨). 원인 = `admin_products_insight_coverage`(동기 def, Starlette 스레드풀 병렬 가능)인데 프론트가 전체 제품을 **1회 fetch + 전역 `productCoverageLoading` 플래그**로 묶음. 둘 다 TASK-0250 이 datasource 연결 도메인에서 제거한 head-of-line 패턴의 잔존. **수정(2 src + 2 test, feature-0003)**: (A) probe 를 `await asyncio.to_thread(_db.probe_datasource, …)` 스레드풀 이관(`/api/ask` `asyncio.to_thread(run_agent)` 기존 패턴) → 이벤트 루프 비블로킹 → N개 /test 가 가장 느린 1건(≤timeout) 안에 완료. 프론트 refresh 는 `_rebuildDsAddList(true)` 단일 경로(중복 Promise.all 제거, `_kickDsConn(force)` 전파). (B) `loadProductInsightCoverage` 를 제품별 `?product_id=N` **단건 병렬 호출**(동시성 cap `_COV_FETCH_MAX=4` via `_runWithConcurrency`) + 전역 플래그 → 제품별 `productCoverageLoadingIds` Set + 끝나는 제품만 즉시 렌더. 백엔드 단건은 대상 제품만 계산 후 break. 캐시버스터 `?v=20260612-task0253-headofline`. **outside-voice 적대 리뷰(REV-0253)**: BLOCKER 0(SSRF pinned-IP/DNS-rebinding 유지·커넥션 누수 없음·break 안전·로딩 stuck 없음 전부 반박). 흡수: MAJOR-2(N-fan-out 공용 anyio 스레드풀[40] 고갈 → 프론트 cap 4 추가), MINOR-2(force 경로 in-flight dedup 부재 → force 무관 합류), MINOR-3(테스트 fake 시그니처 keyword-only 정합); MAJOR-1(테스트 agent 이미지 밖 미실행)은 `make test` green 충족. **검증**: 신규 `test_datasource_test_nonblocking.py`(3: to_thread passthrough/errno 비유출/**동시 probe 비블로킹** 0.3s×5 직렬 1.5s→병렬 ~0.3s) + `test_insight_coverage_endpoint.py`(5: 단건 대상만/**무관 제품 미계산**/전체 무회귀/403/400) **8 PASS** + make test 컨테이너 **전체 회귀 0** + ruff clean + node --check + py_compile. worktree `ai/claude/head-of-line-fix`(base 3a97b86=main 12f5c5e).

**확장 방향 (대규모 — 후속 cycle 후보)**: 제품 수가 수십~수백으로 늘면 매 진입의 N-fan-out(클라이언트 단건 병렬) 자체가 부담이 될 수 있다. 그때 유효한 방향:
1. **백엔드 background 사전계산 worker** — TASK-0250 `conn_health` 모니터 패턴을 완료율에 이식. worker 가 주기적으로 제품별 coverage 를 미리 계산해 두면 화면 진입 시 라이브 DB 조회 없이 즉시 표시(현 on-demand fan-out 제거).
2. **Redis 등 외부 캐시서버에 완료율 스냅샷 저장** — 현재 인메모리 `_insight_cov_cache`(TTL)는 **프로세스 로컬**이라 web/ask-worker/insight-worker 다중 인스턴스 간 공유가 안 된다. Redis 로 옮기면 (a) 인스턴스 공유로 cache hit 율 ↑, (b) 위 background worker 가 계산해 Redis 에 쓰고 web 이 읽는 자연스러운 합류 지점이 된다. 단건 API 도 Redis hit 시 DB 조회 0. (도입 시 datasource 연결 상태[conn_health snapshot]도 같은 Redis 로 공유 가능.)

### Git 동기화 결과
- 커밋: <PR push 시 cycle commit hash> (ai/claude/head-of-line-fix, base 3a97b86)
- verify-completion: <pre-commit 실행 후 갱신>
- Push / PR / main 병합 / 배포: D~E 단계 진행 후 본 항목 갱신(자동 동기화 정책 §16.3 — BLOCKED 없음 + deploy_scope: included → PR→머지→web 재배포). ask/insight-worker 는 코드 무변경이나 동일 agent-common 이미지라 web 재빌드만으로 충분(완료율/probe 변경은 web 프로세스 한정).

**2026-06-12 TASK-0248 — 관리 콘솔 제품 삭제 시 참조 대화 차단(blocked) 전환** (REV-20260612-0248 [SUBAGENT:security+correctness-adversarial, 2-agent] SHIP-WITH-FIXES→흡수→**SHIP**, **Major §12.3** — 파괴적 삭제 + 접근 차단 + cross-store, feature-0002 스키마 교차). 사용자 요청: "관리 콘솔 > 제품에서 각 제품을 삭제할 때, 참조되는 대화가 있더라도 삭제가 가능하도록. 기존의 대화는 막힌 상태(더 이상 대화를 진행할 수 없도록) 전환." + 명확화: "대화 공유는 가능하지만, 대화 자체는 차단으로 진행." → 차단 대화도 **공유(읽기전용)·이력 열람 가능, 새 메시지 진행만 불가**. 설계 승인(AskUserQuestion): **영속 플래그**(`blocked_at`/`blocked_reason`). **구현**: (스키마, feature-0002) alembic `0005_core_conv_blocked`(down_revision=0004, ADD COLUMN IF NOT EXISTS) + 부트스트랩 SQL 멱등 ALTER + app.py MySQL 폴백 parity. (백엔드, app.py) `_conversation_block_info`(fail-open)·`_block_conversations_for_product`(`UPDATE ... WHERE product_id AND blocked_at IS NULL`, backend-aware, 재차단방지) 신설; `admin_delete_product` 가 in_use>0 거부(400) 제거 → cascade 삭제 commit **후** 차단(cross-store "삭제 먼저, 차단 나중") → `{ok, product_id, blocked_conversations}`; `/api/ask` 기존대화 분기가 소유권 직후 blocked→403(slot 前); list PG/MySQL parity 에 blocked 노출. (프런트) canAsk/sendPrompt 가드·composer 입력 disabled+안내·헤더 🚫·목록 "차단" 배지·admin confirm/토스트. 캐시버스터 `?v=20260612-task0248-blocked-conv`. **설계 보존**: fork=차단 전파 안 함(접근불가 제품 auto 강등→원본차단·사본 새 일반대화 정합), share-create=차단 대화 허용(읽기전용). **outside-voice 2-agent 적대 리뷰(REV-0248)**: 백엔드 BLOCKER 0 — probe ①②③④⑤⑦ PASS(특히 ③ cross-store fail-closed 백스톱 **실재 확인**: 제품 cascade 삭제로 WebProducts 행 소멸→`_account_has_product_access` False→ask 403, 차단 UPDATE 실패와 무관하게 진행 차단), probe ⑥(PG 컬럼 부재 시 list SELECT·COUNT 가드 부재로 500)은 **migrate-first 배포 계약으로 흡수**(코드 무변경 — web=DML-only role, alembic 0005 가 정본 적용 경로, 기존 `resolved_model`[TASK-0163] 동일 패턴; 배포 E 단계 `make migrate` 선행 + F 단계 컬럼 psql 실측 게이트); 프런트 **SHIP**(우회 송신 경로 0 — sendPrompt 단일 진입+백엔드 403 이중차단, 공유/이력/fork 요구사항 전부 충족), M-2(admin.js 혼입 의혹)=stale base `git diff` 오탐. **동시세션**: conn-health-monitor(TASK-0250, PR #196 f2a390b)·coverage-multi-ds(0249) active → 머지 직전 origin/main 재확인 후 **f2a390b 위로 rebase**(admin.html 캐시버스터 충돌 1건 해결, app.py/admin.js conn-health+0248 자동 병합 양립). **검증**: 신규 `test_product_delete_block_conv.py` **7 PASS** + make test 컨테이너 **전체 회귀 0**(600 passed/2 skip) + node --check + py_compile + CSS brace 1108=1108 + ruff clean. worktree `ai/claude/task0248-product-delete-blocked-conv`(base ff59f8f→f2a390b 재적용). **잔여**: 배포(make migrate 先 → web 재빌드) + 라이브 검증 + PB-0008 Windows 시각검증.

### Git 동기화 결과
- 커밋: <PR push 시 cycle commit hash> (ai/claude/task0248-product-delete-blocked-conv, base f2a390b 재적용)
- verify-completion: PASS (pre-commit, feature-0003-agent-web-ui)
- Push / PR / main 병합 / 배포: D~E 단계 진행 후 본 항목 갱신(자동 동기화 정책 §16.3 — BLOCKED 없음 + Major → 사람 확인 없이 PR→squash 머지→cleanup, deploy_scope: included).
- 충돌 해결: AI 자율 — rebase 시 admin.html admin.js 캐시버스터 충돌 1건(내 버전 채택), app.py/admin.js conn-health(origin PR#196)+TASK-0248 자동 병합.

**2026-06-12 TASK-0246 — "+ 데이터소스 추가" 드롭다운 항목 열 정렬(고정 열 폭 grid)** (REQ-20260612-0246/AC-0460, REV-20260612-0246 [SKIPPED:trivial-grid-align] + REV-20260612-0247 [SKIPPED:trivial-css-1line] 정련, **Minor §12.3**, CSS-only). TASK-0244 follow-up. 사용자: "`+ 데이터소스 추가` 목록 폭이 문자열 길이에 따라 일정하도록(현재 들쭉날쭉)". **진단(라이브 측정)**: 항목 폭(542px)은 일정하나 `.admin-ds-picker-item` 이 `display:flex` + 이름 `flex:1 1 auto` 라 행마다 엔진 pill(x961/936/967)·좌표(x1011/986/1018)·연결배지(x1105/1080/1080)의 시작 x 가 어긋나 세로 미정렬. **수정(styles.css 단일 블록)**: `.admin-db-picker-item.admin-ds-picker-item` `display:flex`→**`display:grid`** + `grid-template-columns: auto minmax(0,1fr) 56px 124px 104px`(고정 트랙=모든 행 동일 geometry, 이름만 `1fr` 가변 흡수) + 엔진/좌표/연결배지 전부 `justify-self:start`(정련 CHG-0246b — sibling `.cov-db-row`[TASK-0245] 컨벤션·사용자 컬럼 정렬 선호 [[feedback_row_list_column_alignment]] 정합) + 긴 값 ellipsis+title. **비변경**: admin.js·probe·백엔드·RBAC·`.cov-db-row`(동시세션 0245)·DB picker 0(복합 셀렉터 격리). **동시세션 충돌**: db-row-align cycle 이 TASK-0245·CHG/REV/REQ-0245·AC-0385 선점(PR #189/#191) → §13.1 재번호 0245→0246(AC→0460), origin/main(14a296f) 위로 재적용. **배포·검증 완료**: PR #192(grid, main 6756522) + PR #194(정련, main 9c2db34) 머지·push, web 재빌드·재기동(healthz git_commit=9c2db34). **PB-0008 Windows-browser 실측 PASS**: /admin > 제품 "킹스레이드(KR)" > "+ 데이터소스 추가"(datasource 5개) 컬럼 left 좌표 측정 — name/엔진/좌표/연결배지 **전 열 행별 left spread=0px**(각 677/874/938/1070, 수정 전 spread ~31px 들쭉날쭉 해소). 긴 좌표 ellipsis 흡수. 스크린샷 `/tmp/pb0008-ds-picker-colalign-final.png`. worktree `ai/claude/task0246-*`(base f9d8207→14a296f 재적용).

### Git 동기화 결과
- 커밋/PR/배포: main 9c2db34(PR #192 grid + #194 정련) 머지·push·web 재배포·PB-0008 PASS 완료. (TEST.md Run + 본 REPORT docs 후속 #195 예정)


**2026-06-12 TASK-0244 — 관리 콘솔 제품 "+ 데이터소스 추가" 드롭다운 폰트 정합 + 연결 상태 표면화** (REQ-20260612-0244, REV-20260612-0244 [SUBAGENT:design+correctness] **SHIP**, **Major §12.3**, frontend-only). 사용자 요청 2건: 제품 상세(관리 콘솔 > 제품 > [항목]) 데이터소스 탭의 `+ 데이터소스 추가` 목록이 ① 폰트/시각이 다른 UI와 이질, ② 각 데이터소스 연결 상태를 알 수 없음. **진단**: 목록 항목이 `${ds.key} — ${ds.engine} @ ${ds.host}:${ds.port}` 단일 raw `<span>`(무클래스)라 같은 화면 accordion 행(`.ds-acc-name`+`.ds-acc-engine` pill)·`+ 데이터베이스 추가` picker(`.admin-db-picker-name` 구조)와 폰트/정렬이 어긋남. 연결 상태는 `⋯ > 연결 테스트`(일회성 토스트)로만 확인 가능. **수정(frontend-only, admin.js/styles.css/admin.html)**: ① `_rebuildDsAddList` 항목을 `[체크박스 · 이름(.admin-db-picker-name 재사용) · 엔진 pill(.admin-ds-picker-engine = .ds-acc-engine 토큰 1:1) · 좌표(.admin-ds-picker-coord muted) · 연결상태 배지(.admin-ds-conn)]` 구조로 재구성 + 헤더 "데이터소스 · 연결 상태" + ↻ 새로고침. ② `_probeDatasourceConn`/`_paintDsConnBadge` 신설 — 드롭다운 열림 시 `/api/admin/datasources/{key}/test`(기존 엔드포인트) lazy probe → `확인 중… → 연결됨·{ms} / 연결 실패`(원인 tooltip) 배지(`●`점+한글 라벨, 색맹 비의존). `adminState.datasourceConnStatus` Map 세션 캐시(매 토글 재렌더 재probe 방지) + in-flight dedup(`_dsConnInflight`) + **동시 probe 4개 cap 세마포어**(`_dsConnAcquire`/`_dsConnRelease` — 도달불가 다수 + 8s connection_timeout 시 web 스레드 동시 점유 방지, REV nit 선반영). **비변경**: 백엔드 app.py·RBAC(console.access·canDs)·스키마·엔드포인트 shape·datasource 바인딩 스테이징 흐름 0. 캐시버스터 `?v=20260612-ds-picker-status`. **검증**: node --check admin.js PASS + CSS brace 균형 + outside-voice subagent 적대적 디자인/정합 리뷰 **SHIP**(BLOCKER 0). **배포·라이브 검증 완료**: PR #187 main 2b9205a 머지·push, web 재빌드(`sha256:6b05c6…`)·재기동(healthy, healthz git_commit=2b9205a). **PB-0008 Windows-browser 실측 PASS**: /admin > 제품 "킹스레이드(KR)" > "+ 데이터소스 추가" → 3 datasource 가 [이름·엔진 pill·좌표·연결배지] 정합 구조로 렌더(엔진 pill 이 accordion `[mssql]` pill 과 동일 시각), 연결 상태 = `mssql-qa-idc ● 연결 실패`(OperationalError tooltip)·`mssql_local ● 연결됨·8.7ms`·`mysql-local ● 연결됨·8.9ms`(ok/fail/ms 3종 정확). 스크린샷 `/tmp/pb0008-ds-picker-status.png`. worktree `ai/claude/task0244-ds-picker-status`(base f9d8207).

### Git 동기화 결과
- 커밋/PR/배포: main 2b9205a(PR #187) 머지·push·web 재배포·PB-0008 PASS 완료. (TEST.md Run + 본 REPORT 기록 docs 후속 커밋)

**2026-06-12 TASK-0241 — 요청 취소 즉시 처리 + 취소 직후 채팅창 재사용/재요청** (REQ-20260612-0241, REV-20260612-0241 [SUBAGENT:concurrency-adversarial] 2-pass: 1차 BLOCKER 2·HIGH 2·MEDIUM 2 → 흡수 → 2차 **SHIP**, **Major §12.3**, cross-cutting feature-0002+0003). 사용자 보고: "중단을 눌러도 응답이 끝날 때까지 기다린다 — 취소 직후 채팅창 사용·재요청이 가능하게, 부작용도 모두 고려." **진단**: 백엔드 취소 로직(`/api/cancel`+cancel 플래그+agent 루프 폴링)은 정상. 진짜 결함은 **프런트가 `/api/ask` long-poll 을 `await` 하고 busy 해제를 그 `finally` 에서만** 함(app.js sendPrompt) → worker mode 의 동기 응답 계약상 run 종료까지 입력창이 잠김. 추가로 즉시-재요청을 허용하면 같은 conversation 의 old(취소)/new run 동시성 부작용 노출. **수정**: ① **프런트(app.js)** — `cancelCurrentRun` optimistic: busy/입력창 즉시 해제 + pending 말풍선·진행폴링·경과타이머 정리 + in-flight `/api/ask` fetch **abort**(AbortController, `state.askAbortControllers`) + 포커스 + `/api/cancel` 백그라운드 발사. sendPrompt 의 catch 가 `state.userCanceledKeys` 로 사용자 취소를 식별해 에러 토스트/타임아웃 복구 다이얼로그 억제. early-cid(sentinel↔cid) 키 이중성은 `cancelKeys`=양쪽 키 취소 + `askKey` 정렬 + 발사 직전 취소 재확인으로 처리. ② **백엔드(app.py)** — `/api/cancel` 이 pending/running 무관 즉시 KV `canceled`(only_if_current_run) 기록 → orphan `/api/ask` attach 가 슬롯 즉시 반납. attach 루프에 `request.is_disconnected()` + job-aware(`_get_ask_job_status`) 종료로 웹 슬롯 누수 차단. **enqueue 선기록에 sentinel run_id**(`enqpre-<uuid>`) — KV `last_status_run_id` 가 직전(취소) run 으로 남아 orphan terminal write 가 가드를 우회·새 요청 processing 을 클로버하던 BLOCKER 차단. ③ **agent_core.py + memory.py** — `set_run_status(only_if_current_run=True)` supersede 가드: 저장된 last_status_run_id 가 *다른* run 이면 write skip(취소된 orphan 이 새 run 상태 클로버 방지). agent 루프 terminal write(canceled/done/error) 3곳 적용. claim/sentinel takeover 는 default(무조건) 유지. **3중 정합**: sentinel(enqueue) + only_if_current_run(terminal/cancel) + 무조건 takeover(claim, agent_core:2472) → 나열 가능한 모든 인터리빙에서 새 run 보존·취소전용 canceled 오삭제 없음(2차 리뷰 확인). orphan run 은 현재 LLM step(동기, 인터럽트 불가) 종료 후 답변 **기록 없이** 종료. **검증**: 신규 `test_set_run_status_supersede.py` 5건 + 전체 pytest(회귀 0, F/E 0, 2 skip) + ruff All checks passed + node --check + py_compile. **follow-up(별 cycle, LOW)**: never-claimed pending job + sentinel KV 잔존(pending-job TTL reaper 부재 — 본 변경 이전부터의 class, 악화 아님; 20분 후 stale_error·max_wait 슬롯반납으로 완화). **PB-0008 후속 수정(main bb661bf)**: 검증 중 발견 — `cancelCurrentRun` 이 폴링을 멈춰 자동 재렌더 트리거가 사라지자 `clearPendingBubble`(state 만 null)이 DOM `#pendingAssistantBubble` 을 못 지워 "처리 중" 말풍선 잔류 → cancelCurrentRun 에 `renderMessages()` 추가로 즉시 제거(사용자 메시지 유지). 캐시버스터 `?v=20260612-cancel-immediate-2`. **배포·검증 완료**: main bb661bf, web+ask-worker 재빌드·재생성(healthy), 서빙 app.js 신규 마커 + app.py/agent_core/memory.py 가드 baking 확인. **PB-0008 Windows-browser 실측 PASS**: 다단계 run 전송 → busy(중단 모핑·입력잠김·pending 표시) → 중단 클릭 직후 동기 `disabled:true→false`·`mode:stop→send`·`hasPending:true→false`(말풍선 제거)·`focused:promptInput`, 재요청 즉시 수락(429 없음), orphan bail(8s) 후에도 상태 안정·허위 답변 없음. worktree `ai/claude/task0241-cancel-immediate`(base 9fbb185).

### Git 동기화 결과
- 커밋/PR/배포: main bb661bf 머지·push·배포(web+ask-worker)·PB-0008 검증 완료

## 1. Summary

**2026-06-12 TASK-0235 — 새 대화 첫 메시지 작업 단계 진행상황 실시간 표시** (REQ-20260612-0235, REV-20260612-0235 [SUBAGENT:newconv-progress-adversarial-concurrency] CONCERN→흡수, **Major §12.3**, 동시세션 insight-reset·prompt-autogen·ds-a11y·ds-label cycle 이 TASK-0231/0232/0233/0234 선점→§13.1 재번호 0232→0235). 사용자 보고: "새 대화 생성 후 assistant 에게 첫 요청을 보냈을 때 작업 단계 진행상황이 안 나타나고 '시작 중' 출력만 확인됨. 각 단계와 클릭 시 사이드바로 상세 확인 가능하게." **진단**: 진행 단계 한줄 표시(`renderPendingAssistantBubble`)·"N단계 보기"→사이드바(`openStepSidePanel`/`#stepSidePanel`/`_renderStepSidePanelBody`) UI 는 TASK-0061 에서 **이미 구현**됨. 진짜 결함은 **데이터 공급 비대칭** — 기존 대화는 send 직전 `startProgressPolling()` 시작(app.js:5476)하지만, 새 대화(lazy_create)는 `conversation_id` 가 `/api/ask`(블로킹 — worker enqueue 후 long-poll attach 또는 inproc `asyncio.to_thread`) 응답 전까지 없어 폴링을 못 켜고, ask 완료(run 종료 시점) 후에야 폴링 시작 → 처리 내내 step 0 → pending bubble 이 "시작 중…" 고착. **수정(frontend-only, app.js+index.html)**: lazy_create 시 staged 첨부 있을 때만 `/api/new_conversation` 으로 cid 를 선발급하던 분기(TASK-0106)를 **첨부 유무 무관 일반화**. cid 확정 직후 ① `state.activeConversationId` 전환 + optimistic conversation entry 선등재 ② `startProgressPolling({reset:true})` 즉시 시작 → 새 대화 첫 메시지에서도 step 실시간 누적 → pending bubble 단계 표시 + "N단계 보기" 버튼/사이드바 활성화. 후처리 블록(5587-5614)은 `pendingSentinel===busyKey` 가드가 early 전환으로 false 가 되어 중복 폴링 없음(non-lazy lifecycle 로 수렴). **적대적 동시성 리뷰 CONCERN 2 흡수**(REV-20260612-0235): #3 — early-cid 발급 후 ask 실패 시 빈 대화 고아화 회귀 → `earlyCidActivated` 플래그 도입(활성 전환 시 catch 가 lazy 에러 경로 대신 **non-lazy 복구 경로**(fetchAskStatus→is_processing 시 대기/취소/즉시답변)로 분기 → 빈 대화는 실 run 컨테이너가 되고 worker 모드 살아있는 run 도 회수). #2 — 빈 대화에 명시 cid `/api/ask` 가 user message 저장+run 시작? → `run_agent` 내부 `save_memory_message` 책임(agent_core:1379/2273), 기존 staged-attachment 흐름이 동일 패턴 사용 중인 검증된 경로로 확인. race 안전: 첫 poll 이 processing 선기록(worker app.py:8346 / inproc agent_core:2472) 전 도달해 status="" 받아도 폴링 중단 조건(`status && !=="processing"`) 아님 → 다음 tick 포착. **비변경**: 백엔드 app.py·PG/웹 스키마·RBAC·엔드포인트·시크릿 0(병렬 insight-reset worktree 가 app.py 점유 중 — 의도적 회피). 캐시버스터 `app.js?v=20260611-newconv-progress-steps`. **검증**: node --check app.js PASS. **잔여**: verify-completion → 머지 → web 재배포 → PB-0008 Windows-browser 시각검증(새 대화 첫 요청 → 단계 실시간 표시 + 사이드바 열림). worktree `ai/claude/newconv-progress-steps`(base c77111d).

### Git 동기화 결과
- 커밋/PR/배포: 진행 중 (cycle-finalize 시 갱신)

## 1. Summary

**2026-06-11 TASK-0231 — insight 분석 초기화 (관리 콘솔 > 제품 > 접근 가능 데이터베이스 단위)** (REQ-20260611-0228, REV-20260611-0231 [SUBAGENT:security] BLOCK(MAJOR 3)→흡수, **Critical §12.3**, 동시세션 SSRF·UI-통합·멀티datasource cycle 이 TASK-0228/0229/0230 선점→§13.1 재번호 0228→0231). 사용자 요청: insight 분석 완료율 화면에서 분석 내용을 초기화하는 수단 — "분석한 내용 자체가 잘못되었을 경우 대응 방법이 없다"는 gap. 사용자 결정(AskUserQuestion): **개별 DB 단위** + **삭제만**(worker 자동 재분석). **구현**: ① 신규 RBAC `insight.reset`(console 그룹, admin 한정 — audit.purge 동급 파괴적; PERMISSION_DEFINITIONS + admin seed catchup, operator/sales/pending 미부여). ② 공용 헬퍼 `_resolve_product_insight_scope` — 완료율 계산 `_compute_product_insight_coverage` 와 reset 이 **동일 scope/allow_null/engine** 식별자 사용 + scope alias 집합(hash/.env label/NULL) 반환. ③ `POST /api/admin/products/{pid}/insight-reset`(body `{db, dry_run}`) — 라이브 카탈로그 조회로 해당 DB 의 `(schema, table)` 쌍 확보 후 **rag_objects 를 완료율 분자와 동일한 (schema_name, table_name) 교집합 + schema 노드로 삭제**(M1: object_key LIKE 가 MSSQL 2-tier 레거시 catalog-less 키를 놓쳐 완료율 divergence 유발하던 것을 해소 — 2-tier/3-tier 무관 완료율 0 보장). fact_entries/rag_documents/kv 는 키 패턴(scope alias 전체 + 라이브 schema 기반, LIKE ESCAPE '\\') 삭제. **fingerprint(schema_fp/table_fp)+refresh_at 동반 삭제가 핵심** — 안 지우면 worker 가 fingerprint_changed 미발생으로 재분석 skip. `dry_run=true`=건수만, `false`=**audit start-event 먼저 commit(실패 시 삭제 중단, M3 fail-safe)** → 단일 PG tx 4종 DELETE + rollback 안전망 → complete-event + 완료율 캐시 clear. 보안 게이트: 권한 403 + 제품 WebProductDatabases 바인딩 DB 만 허용(임의 주입 400) + db 누락 400 + 카탈로그 조회 실패 502. ④ 프런트(admin.js/html/css, TASK-0229 통합 DB 리스트 위로 rebase): per-DB 행 "초기화" 버튼(권한자만) → `resetProductDbInsight`(dry-run 미리보기 → DB명 typed-confirm + "공유 제품 완료율도 함께 0" 경고 → 실삭제 → 완료율 새로고침), 위험색 버튼 CSS + grid 6컬럼, 캐시버스터 `?v=20260611-db-coverage-insight-reset`. **outside-voice 적대적 보안 리뷰 MAJOR 3 흡수**(REV-20260611-0230): M1(MSSQL rag_objects 2-tier 레거시 누락 → 완료율 divergence, 라이브 168행 재현) → (schema,table) 교집합 통일, M2(scope alias 미삭제 → fingerprint 잔존) → alias 집합 전체 삭제, M3(audit 후행 best-effort) → start-event 선행 commit fail-safe. SQL인젝션/권한/IDOR/트랜잭션은 리뷰 PASS. **검증**: 신규 `test_insight_reset.py` 14건 PASS + make test **505 passed/2 skipped(회귀 0)** + ruff All checks passed + py_compile + node --check. 라이브 PG 실측으로 키 패턴 매칭·MSSQL 2-tier/3-tier 분포 검증. worktree `ai/claude/insight-reset`(origin/main 77f2ef6 위로 rebase). **잔여**: verify-completion → 머지 → web 재배포 → 라이브 dry-run/실삭제 검증 + PB-0008 시각검증.

### Git 동기화 결과
- 커밋/PR/배포: 진행 중 (cycle-finalize 시 갱신)

## 1. Summary

**2026-06-11 TASK-0229 — 관리 콘솔 제품 상세 "접근 가능 데이터베이스" UI 통합 (gstack 디자인 리뷰)** (REQ-20260611-0229, REV-20260611-0229 [SKIPPED:frontend-ia-merge-no-backend], **Minor §12.3**, 동시세션 SSRF cycle TASK-0228 선점→§13.1 재번호). 사용자 보고 2건: (1) 제품 상세의 `접근 가능 데이터베이스` 섹션에서 위쪽 "insight 분석 완료율" per-DB breakdown 리스트와 아래쪽 사용자 등록 DB chip 목록이 **같은 DB 집합을 두 번 표시**(1:1 매칭)해 분리 의미가 없다 → 하나로 통합. (2) 시스템/메타데이터 DB(MySQL 4종/MSSQL 3종)가 각각 별도 locked chip 으로 나열돼 산만 → 단일 묶음 칩 + hover 상세. **gstack `/design-review` 메서드론**(general-purpose design subagent)으로 통합 IA 도출: "분석 대상(사용자 DB)=한 행에 진척+제거를 담은 단일 리스트, 비-분석 대상(시스템 DB)=접근성 갖춘 단일 묶음 칩". **데이터 정합 검증**: 백엔드 `_compute_product_insight_coverage` 의 `accessible = _list_product_databases(conn, pid)` → `per_db` 의 DB 집합이 사용자 등록 DB(draft chip)와 **정확히 동일**, 시스템 DB 는 `availableDatabases.metadata_schemas` 별도 출처라 per_db 에 미포함 → 조인 키 `per_db.db ↔ draft.schema_name`(소문자) 자연 정합. **수정(admin.js + styles.css + admin.html, 3파일)**: ① `buildProductCoverageDetail` 을 "요약 헤더(제목+전체% 배지+새로고침)+전체 진행 바"로 축소(per-DB breakdown 리스트 제거 — 각 행으로 흡수). ② `buildDbCoverageCells(covRow, measuring)` 신설 — 통합 리스트 한 행의 진척 셀(마이크로바+통계 m/n+상태칩 DB✓/연결불가/측정대기). ③ `buildSystemDbChip(lockedChips)` 신설 — 시스템 DB 단일 묶음 칩(`시스템 DB N개 · 고정`) + `title`/`aria-label`/`tabindex=0` + hover **및** focus/focus-within 커스텀 툴팁(키보드·터치 접근성 병행). ④ `redrawChips` 재작성 — 시스템 묶음 칩(상단) + 사용자 DB 통합 리스트(`cov-db-row` grid 5컬럼: 이름·마이크로바·통계·상태칩·제거 ×). 빈 상태 메시지. ⑤ 컨테이너 `admin-chip-wrap`→`cov-db-wrap`(flex column). **CSS**: `.cov-db-wrap`/`.cov-db-row`(grid)/`.cov-microbar(-fill)`/`.cov-db-status*`/`.cov-db-remove`/`.sysdb-chip(-tip*)` 신설·재구성, 기존 디자인 토큰만 사용(신규 hex 0), 8px 그리드·11~13px 위계 유지. 캐시버스터 `?v=20260611-db-coverage-unified`. **권한/스키마/암호화/엔드포인트/백엔드(app.py)/coverage 데이터 모양 0** — frontend-only IA 재구성. **검증**: node --check admin.js PASS + CSS brace balance(1031/1031) + verify-completion. **잔여**: web 재배포 + PB-0008 Windows-browser 시각검증. worktree `ai/claude/product-db-coverage-merge`(base e93b181).

### Git 동기화 결과
- 커밋/PR/배포: 진행 중 (cycle-finalize 시 갱신)

## 1. Summary

**2026-06-11 TASK-0228 — datasource SSRF 사설망 경계 env 토글 + 의도적 비활성화** (REQ-20260611-0228, REV-20260611-0228 [SUBAGENT:security] BLOCK→흡수→PASS, **Major §12.3 — 보안 다운그레이드, 사용자 명시 승인**). 사용자 보고: `관리 콘솔 > 데이터소스` 에서 새 데이터소스(host=`10.200.50.80`) 생성 시 "호스트 차단(SSRF): 사설/링크로컬 IP 차단(allowlist 필요): 10.200.50.80" 에러. **근본 원인**: `_ssrf_check_host`(app.py)가 RFC1918 사설 IP 를 SSRF 방어로 차단하는 설계(TASK-0205/0214). `10.200.50.80`=`10.0.0.0/8` 사설 대역 → 차단. 정당한 사내 host 는 `AGENT_DATASOURCE_HOST_ALLOWLIST` 등재 필요. **코드 버그 아님** — 사내 운영(대부분 사설망 IP)과 SSRF 방어 기본값의 불일치. **사용자 결정**: SSRF 방어 구성을 복원 가능한 형태로 보존(태그)하고 현재는 사설 경계 의도적 비활성화. **구현**: ① `_ssrf_private_guard_enabled()` 신규 — env `AGENT_DATASOURCE_SSRF_GUARD_ENABLED`(기본 `1`=활성 secure-by-default; `0`/`false`/`no`/`off`=비활성). ② `_ssrf_check_host()` 토글 분기 — 비활성 시 **RFC1918(`is_private`)만 완화**. ③ `GET /api/admin/datasources` 에 `ssrf_private_guard_enabled` + admin.js 안내 분기(`?v=20260611-ssrf-private-guard-toggle`). ④ ADR-0030 + SECURITY §11 + .env.secret.example(복원 절차/태그) + 자동 메모리. **불변식(토글 무관 항상 유지)**: 클라우드 메타데이터 IP(IPv4-mapped IPv6 형 `::ffff:...` 포함)·loopback(127.x/::1)·link-local(169.254.x/fe80::)·reserved·multicast 차단 + DNS rebinding pin + fail-closed 에러 경로. **outside-voice 적대적 보안 리뷰 BLOCK→흡수**(REV-20260611-0228): (A/B) 토글 OFF 시 IPv4-mapped 메타데이터 IP 가 `str(ip).endswith` 정규화 빗나감으로 통과 → `ip.ipv4_mapped` 언래핑 비교로 수정. (C) 토글이 loopback/link-local 까지 개방 → `is_private` 한정 + loopback/link-local 상시 차단으로 수정. **검증**: py_compile + node --check PASS, 신규 31 PASS + datasource 회귀 0, 통합 trace 11 케이스 ALL PASS. **잔여**: 운영 `.env.secret` 토글=0 설정 + web 재배포 + PB-0008 Windows-browser(host=10.200.50.80 데이터소스 생성 성공) 시각검증. worktree `ai/claude/ssrf-host-guard-toggle`(base e93b181).

### Git 동기화 결과
- 커밋/PR/배포: 진행 중 (cycle-finalize 시 갱신)

## 1. Summary

**2026-06-11 TASK-0227 — 실행 단계 사이드 패널 갱신 시 "결과 보기" 펼침 상태 유지** (REQ-20260611-0227, REV-20260611-0227 [SKIPPED:frontend-ui-state-persist-no-backend], **Minor §12.3**). 사용자 보고: assistant 답변의 `실행 단계`를 사이드바에 펼쳐놓고 한 단계의 `결과 보기`로 결과셋을 확인 중일 때, 실행 단계가 폴링으로 갱신되면 보던 결과셋이 닫혀버린다. **근본 원인**: 폴링으로 새 단계가 도착하면 `applyProgressPayload`(app.js)가 `refreshStepSidePanel`→`_renderStepSidePanelBody`를 호출하고, 이 함수가 `body.innerHTML=""`로 패널 DOM 전체를 비운 뒤 모든 단계를 재생성한다. 그런데 각 단계의 "결과 보기" 펼침 여부는 순전히 DOM 로컬 변수(`resultBody.hidden`, `buildStepDetailEl` 내부)로만 존재 → 재렌더 시 전부 기본값(닫힘)으로 리셋. 스크롤 위치는 이미 `wasAtBottom` 스냅샷/복원하면서 펼침 상태는 미보존하던 비대칭. **수정(app.js + index.html, 2파일)**: ① `state.stepResultExpanded`(Set) 신설 — 펼친 단계의 안정 키 영속화. ② `_stepResultKey(step, idx)` 헬퍼 — `progressSteps` dedup과 동일한 `step_index:created_at` 키(둘 다 없으면 `idx:` fallback)로 같은 단계가 재렌더를 거쳐도 동일 키 유지. ③ `buildStepDetailEl(non-compact)` 결과 토글이 초기 `hidden`/버튼 라벨("결과 보기/닫기")/`aria-expanded`를 Set에서 복원, 토글 클릭 시 add/delete. ④ run 전환 시(`resetProgressTracking` + `applyProgressPayload`의 runId 변경 분기) `state.stepResultExpanded.clear()`로 다른 run의 동일 step 키 혼동 방지. **권한/스키마/암호화/엔드포인트/백엔드(app.py) 0** — frontend-only. `buildSqlStepPanel`(완료 메시지 SQL 결과)은 run 완료 후 폴링 정지로 재렌더되지 않아 본 버그 무관(범위 밖). 캐시버스터 `?v=20260611-step-result-persist`. **검증**: node --check app.js PASS + verify-completion **PASS(9/9 checks)**. **잔여**: web 재배포 + PB-0008 Windows-browser 시각검증. worktree `ai/claude/step-panel-result-persist`(base de52f08).

### Git 동기화 결과
- 커밋/PR/배포: 진행 중 (cycle-finalize 시 갱신)

## 1. Summary

**2026-06-11 TASK-0223 — 제품별 insight-worker 분석 완료율 UI (관리 콘솔 > 제품)** (REQ-20260611-0223, REV-20260611-0223 [SUBAGENT:insight-coverage-matching-semantics], **Major §12.3**). 사용자 요청: `관리 콘솔 > 제품` 각 항목에 insight-worker 의 객체 분석 완료율(%)을 표시 — 비율 모수 = 제품 `접근 가능 데이터베이스`(WebProductDatabases) 의 객체, 분자 = PG 내 해당 DB/테이블 통찰값(rag_objects). **구현**: (db.py) `list_information_schema_tables` — datasource information_schema `(schema,table)` flag-무관 직결 열거(`connect()` flag-gated 경로 우회). (app.py) `_compute_product_insight_coverage` + `GET /api/admin/products/insight-coverage`(`console.access`, 90s TTL 캐시). **catalog-driven 매칭** — 라이브 카탈로그 (schema,table) ∩ rag_objects (conv=`__global__`, scope=`common`, object_type∈{schema,table}) **set 교집합 dedup**: MSSQL `schema_name=dbo` 차원·NULL/hash 이중기록을 모두 해소. datasource scope=엔드포인트 해시(`_dsr.scope_key`, .env 라벨 폴백)+기본 엔드포인트면 `datasource_key IS NULL` 폴백. 분모는 resolve된 datasource RO 좌표 직결(SSRF 가드+pinned IP, 5s timeout, per-datasource 실패 격리→measurable:false). MSSQL 비-default_db=미스캔 flag. (admin.js/styles.css) 제품 목록 배지(`분석 N%` 등급색) + 상세 `접근 가능 데이터베이스` 섹션 per-DB breakdown(테이블 analyzed/total·DB✓/✗·미스캔) + 새로고침. 캐시버스터 `?v=20260611-insight-coverage`. **권한/스키마/암호화/insight write 경로 변경 0**(read-only 통계). **검증**: outside-voice 적대적 설계리뷰 [SUBAGENT] NOT-SHIP 5건이 catalog-driven 구현으로 전부 해소 확인. make test pytest **444 passed/2 skipped** + ruff All checks passed(머지 후 `_log` F821·conversation_id 버그 2건 hotfix 포함) + node --check + py_compile. **라이브 실측**: product 1/7/8(MySQL)=100%(dbauth 9/9·dbgame 98/98·dblog 279/279 등), product 91(MSSQL `mssql_local` agent_ro 로그인실패)=graceful 측정불가. **PB-0008 Windows-browser 시각검증 PASS**(목록 3× 녹색 `분석 100%`+1× `분석 측정 불가`, 상세 `insight 분석 완료율 100%` `389/389 객체` per-DB breakdown). worktree `ai/claude/task0223-product-insight-coverage`(base c769612).

### Git 동기화 결과
- 커밋: 15f1fa7 (ai/claude/task0223-product-insight-coverage) → PR #161 머지 (main b46cbd4) + hotfix cde2610(_log→logging) + 0e37b8e(conversation_id `__global__`)
- verify-completion: PASS (9 of 9 checks, CHECK#13 Windows-browser WARN→PB-0008 충족)
- Push: 완료
- main 병합: 완료 (PR #161 merge + hotfix 직접 push)
- 배포: make dc-build SERVICE=web + up -d (healthz git_commit=0e37b8e 베이킹 확인)
- 충돌 해결: 없음

## 1. Summary

**2026-06-11 TASK-0218 — 관리 콘솔 대시보드 CloudWatch 스타일 사람-친화 재구성** (REQ-20260611-0218, REV-20260611-0218 [CODEX+SUBAGENT:cloudwatch-dashboard-design], **Major §12.3**). TASK-0210 위젯 그리드를 AWS CloudWatch 류 운영 대시보드로. gstack `/design-review` 메서드론 + cross-model(Codex+subagent) 디자인 감사 강한 합의 반영: (위계) 9개 동일 비중 → 주 metric 크게(primary)+보조 작게, 카탈로그 활동-우선. (신선도) `days` 윈도우 audits/conversations/accounts 전파(거짓 컨트롤 정직화)+수동 새로고침+auto-refresh(off/30/60s)+마지막 갱신 시각. (추세) 전기간 대비 ▲▼% 델타 배지(의미별 색)+순수 SVG sparkline(lib 0). (fail-loud) overview/위젯 실패 배너+재시도. (drill-down) 위젯→관리 탭. (편집) native HTML5 drag+↑↓ 폴백. (접근성) 포커스 링·aria-live·aria-label·aria-pressed. (polish) Top-N 비율막대·radius --r-md·8px. 백엔드 `_dash_widget_*` window/primary/delta/spark/tab + helper 2. **권한/스키마/시크릿/신규 엔드포인트 0**(응답 shape 확장 + 비파괴 read). make test MAKE_EXIT=0(`test_dashboard_overview.py` 17, 회귀 0)+node/py_compile+내 코드 ruff 클린. 캐시버스터 `?v=20260611-dashboard-cloudwatch`. worktree `ai/claude/dashboard-cloudwatch-ux`(base 1c98a16). flag(내 코드 아님): app.py:14133 `_log` F821(TASK-0216 머지본 잠복).

## 1. Summary

**2026-06-11 TASK-0210 — 관리 콘솔 대시보드 보강(카테고리별 위젯 그리드 + per-account 커스터마이즈/영속)** (REQ-20260611-0210, REV-20260611-0210, **Major §12.3**). 사용자 요청: 관리 콘솔 대시보드("운영 현황")가 빈약(계정 metric 6개 + 권한 drift + pending, 전부 클라 `adminState.accounts` 배열 필터 계산 — 계정 증가 시 비확장)하니 각 카테고리별 풍부 + "사용자별로 확장성 있게" 보충. AskUserQuestion 으로 **종합(RBAC 뷰어 스코프 + 계정별 분해 + 서버 집계) + 각 사용자별 커스텀 구성/수정 가능 + 영속성** 확정. **구현(4파일 + 신규 테스트)**: (백엔드 app.py) ① `_ensure_web_tables()` 에 `WebDashboardPreferences(AccountId PK, Content MEDIUMTEXT JSON-text)` 멱등 추가(MySQL 웹테이블군 정합). ② `GET /api/admin/overview` — 위젯 카탈로그(`_DASHBOARD_WIDGETS`) 각 항목이 표시 권한을 가지며 actor 보유 권한 위젯만 데이터 생성·반환(**권한 경계=데이터 노출 경계**). 위젯 7종(accounts/roles/products/datasources/conversations[PG]/audits[`audit.read.any`]/usage[`console.usage.read`, PG])은 각각 독립 try/except 격리. `days` 는 `max(1,min(365,int()))` clamp 후 PG interval 삽입(인젝션 차단). ③ `GET/PUT /api/admin/dashboard/preferences` — actor.id 한정 self-service(신규 RBAC 권한 0, `console.access` 게이트), PUT 은 `_sanitize_dashboard_prefs`(알려진 키·bool·int 만, 미지/중복/과대 거부). (프런트) admin.js `renderDashboard` 재작성 → 서버 overview+prefs fetch 후 위젯 그리드 + 편집 모드(표시 토글·↑↓ 순서, 외부 라이브러리 없음) + 저장/기본값복원; grant_health·pending 은 client 위젯으로 흡수. admin.html 위젯 그리드·집계기간 select·편집 toolbar; styles.css `.dashboard-widget*`(기존 토큰 재사용). 캐시버스터 `?v=20260611-dashboard-widgets`. **권한 카탈로그/시크릿/웹 외 스키마 변경 0**. **검증**: make test MAKE_EXIT=0 전체 PASS(신규 `test_dashboard_overview.py` 11 PASS — overview RBAC 스코프 operator(usage/audits 부재)·admin(전부 존재)·403·sanitize·기본값·영속 round-trip, 회귀 0) + node --check + py_compile + ruff 통과. outside-voice 적대적 보안리뷰(위젯 권한 경계/IDOR/인젝션). worktree `ai/claude/admin-dashboard-enrich`(base f2054b5).

## 1. Summary

**2026-06-10 TASK-0197 — assistant 말풍선 타임스탬프 옆 소요시간 표시** (REQ-20260610-0197, REV-20260610-0197 [SKIPPED:frontend-only-no-rbac-no-schema-no-secret], **Minor §12.3**). assistant 응답 완료 시 각 대화 bubble 의 타임스탬프 옆에 소요시간 표시. `message.meta.duration_ms`(agent_core mirror_meta 기존 저장 필드) > 0 인 assistant 메시지에 한해 `renderMessages()` 에서 기존 `formatElapsed()` 재사용 + `.message-meta-duration` span 추가. user 메시지·duration 없는 메시지는 기존 textContent 유지. styles.css `.message-meta-duration { font-size:10px; opacity:0.7 }`. 캐시버스터 bump. 백엔드/RBAC/스키마/시크릿 무변경. node --check PASS. worktree `ai/claude/response-duration-display`.

### Git 동기화 결과
- 커밋: 143f039 (ai/claude/response-duration-display)
- verify-completion: PASS (9 of 9 checks)
- Push: 완료 (origin ai/claude/response-duration-display)
- main 병합: 해당없음 (PR 생성 대기 — §16.3 Step 6)
- 충돌 해결: 없음

## 1. Summary

**2026-06-10 TASK-0188 — 공유 대화 페이지 markdown 미적용 수정 + 수신자 가독성 디자인** (REQ-20260610-0188, REV-20260610-0188 [SKIPPED:frontend-only-no-rbac-no-schema-no-secret], **Minor §12.3** — frontend-static-only). 사용자 보고: 공유 링크(`/share/{token}`) 로 전달받은 대화가 markdown 미적용 raw 텍스트(`**`, `|`, `#`, 코드펜스 그대로)로 보임. **근본 원인**: `share.html` 이 메인 UI 의 markdown 파이프라인 라이브러리(`vendor/marked.umd.js` + `vendor/purify.min.js`)를 미로드 + `share.js renderMessage` 가 `content.textContent = msg.content` 로 평문 렌더 — 메인 채팅은 `markdownToHtml()`(marked.parse → DOMPurify.sanitize)로 렌더하는데 공유뷰만 누락. **수정(3파일, 백엔드·API·스키마 무변경)**: ① `share.html` — marked+purify 로드(share.js 앞 순서) + css/js 캐시버스터 `?v=20260610-share-md` + 헤더 브랜드 라벨 + "링크 복사" 버튼. ② `share.js` — `renderMarkdownContent()` 신규(메인과 동일 marked+DOMPurify, 라이브러리 부재 시 평문 폴백) + sql 코드블록 "쿼리 보기" 토글 이식(`collapseSqlCodeBlocks`) + 외부 링크 `target=_blank rel=noopener`(`markExternalLinks`) + 역할 배지(사용자/어시스턴트) + 링크복사 핸들러(clipboard API + execCommand 폴백). ③ `share.css` — 렌더된 markdown 요소 전반 스타일(제목 h1~h4·리스트·인용·인라인/블록 코드·**GFM 표**(DB 질의 응답 핵심)·hr·img·링크) + 역할 배지/메시지 좌측 accent border + 반응형(≤600px) + **인쇄/PDF 스타일시트**(수신자 보고서 보관 — actions/footer 숨김, SQL 토글 펼침, pre 줄바꿈). **보안**: 익명 페이지 XSS 표면은 메인 앱과 동일한 DOMPurify.sanitize 로 차단 — 데이터 노출/redaction(backend) 무변경. node --check share.js PASS. 검증: Windows-browser(PB-0008) 배포 후. 동시세션 다수(0182~0186 선점)→0188 재번호. worktree `ai/claude/share-md-render`.
## 1. Summary

**2026-06-10 TASK-0181 — 역할/계정 차트 모델별 stacked + 상세 표 요청(메시지) 수** (REQ-20260610-0181, REV-20260610-0181 [SKIPPED:read-agg], **Minor §12.3**). 역할별·계정별 [토큰|비용] 막대를 모델별 누적으로 분해(전역 modelColor 색 일관 + renderStackedHBar) + 작업 화면 요청 수(distinct run_id) 컬럼. 백엔드 by_account models[]·requests 집계 확장(RBAC/스키마 무변경). make test 282 passed/5 skipped.
## 1. Summary

**2026-06-10 TASK-0180 — 차트 카테고리별 행 레이아웃 + 일별 폭 채움 + 상세 표 여백** (REQ-20260610-0180, REV-20260610-0180 [SKIPPED:css-layout], **Minor §12.3**). 사용자 피드백(몰아넣기 불쾌·상세 표 여백). 명시적 행 구조(4:1 trend / 역할별 토큰·비용 / 계정별 토큰·비용) + 일별 차트 viewBox=clientWidth 로 넓은 카드 폭 채움 + 상세 표 카드화. 순수 레이아웃, 백엔드 무변경. node --check PASS.
## 1. Summary

**2026-06-10 TASK-0179 — LLM 사용량 차트 넓은 화면 가로 여백 해소 (CSS grid)** (REQ-20260610-0179, REV-20260610-0179 [SKIPPED:css-layout], **Minor §12.3**). 넓은 모니터에서 차트가 좌측만 차지하던 것을 `.admin-usage-charts` grid 다열 배치로 채움(일별 2칸, 나머지 1칸씩, 좁으면 wrap). 순수 레이아웃, 백엔드 무변경. node --check PASS.
## 1. Summary

**2026-06-10 TASK-0178 — LLM 사용량 화면 여백 컴팩트화** (REQ-20260610-0178, REV-20260610-0178 [SKIPPED:css-spacing], **Minor §12.3**). 사용자 보고(여백 과다). TASK-0177 디자인 정렬에서 카드·섹션·차트 패딩이 누적된 것을 축소 — `.admin-usage-card/section/metric` 패딩·margin 하향, 일별 차트 SVG 높이 252→196, HBar 막대 간격 축소. 순수 spacing(CSS/SVG), 백엔드/구조 무변경. node --check PASS.
## 1. Summary

**2026-06-10 TASK-0177 — LLM 사용량 상세 표 추정 비용 컬럼 + gstack 디자인 관점 정렬** (REQ-20260610-0177, REV-20260610-0177 [SKIPPED:frontend-design], **Minor §12.3**). (A) 역할별·계정별 상세 표에 추정 비용 컬럼(차트와 일치) + 숫자 우측정렬·tabular-nums. (B) general-purpose subagent 의 gstack design-review 관점 적대적 리뷰를 받아 usage pane 디자인 정렬: 요약 `.metric-card` 통일, 임의 hex→디자인 토큰, 차트 surface 카드 구획, 8px spacing/타이포 위계 클래스, 표·툴팁 클래스化. styles.css(admin-usage-* 신규)+admin.html+admin.js, 백엔드 무변경. node --check PASS. 캐시버스터 bump. Windows-browser(PB-0008) 검증 배포 후.

**2026-06-09 TASK-0176 — LLM 사용량 역할별·계정별 추정 비용 차트** (REQ-20260609-0176, REV-20260609-0176 [SKIPPED:frontend-viz], **Minor §12.3**). 사용자 요청(역할·계정별 추정 비용도 차트로). 백엔드 `admin_llm_usage` by_account 를 계정×모델 분해로 집계해 계정별 추정 비용(`cost_usd`) 산출 + `_aggregate_usage_by_role` 가 역할별 재합산. 프론트 `renderHBar` 에 valueFmt(usd) 추가 + 역할별/계정별 추정 비용 가로 막대 차트(의존성 0 SVG, hover usd, 비용 0 행 제외). 권한/엔드포인트/스키마 신규 0(기존 컬럼 + TASK-0166 단가 재사용). make test 269 passed/5 skipped. 비용은 claude 등 과금 모델 추정만(로컬=$0). 동시세션 0168~0175 선점→0176 재번호.

**2026-06-09 TASK-0169 — out-of-process ask-worker 실행모델 + 라이브 cutover** (REQ-20260609-0168, REV-20260609-0169, **Critical §12.3**, PLAN-APPROVED). `/api/ask` 의 in-process `asyncio.to_thread(run_agent)` 실행을 전용 `ask-worker`(ask_jobs 큐 claim)로 분리 → web 재배포/SIGTERM 이 in-flight run 을 죽이는 orphan 구조 제거(TASK-0159/0160/0164 이월 B 종결, 두 backstop 격하). flag `AGENT_ASK_EXECUTION_MODE`(기본 inprocess) — 배포 자체는 무변경 shadow, cutover 는 env 전환·즉시 rollback. **web(app.py)**: `_dispatch_ask_run`(inprocess|worker) + readiness gate(503) + 단일문 slot enforce + 내부 attach loop + `result_json` shape 패리티 + backstop ownership-aware(B1) + cancel-pending(2g) + 첨부 temp `/shared`(M6). **agent-core(feature-0002)**: ask_jobs 마이그레이션 0003 + `ask_jobs.py`(atomic claim B2/slot M5/lease fencing B3/sweep) + `ask.py`(worker loop·시간기반 heartbeat·reaper) + `--ask-worker`·healthcheck + `set_run_status` 순서 M4 + `_clear_cancel_request` run_id-scoped MJ-2. docker-compose `ask-worker` 서비스(stop_grace 70s). **거버넌스**: outside-voice 적대적 리뷰 2회(설계 전 "구현 불가" 판정 → BLOCKER 3+MAJOR 4 흡수; 구현 diff → BL-1/MJ-1/MJ-2 추가 수정). make test 회귀 0 + ruff + verify-completion PASS(양 feature). **라이브 cutover 전수 검증**(main 584b8dd): 마이그레이션 0003 적용(live=0003, agent_kb_rw 권한 OK) → web+ask-worker 배포(healthz git_commit 일치) → flag=worker. 실측 — ① ask enqueue→worker claim(atomic,lease=1)→run→동기 응답 shape 패리티, exactly-once(attempts=1); ② **web force-recreate 중 in-flight run 생존**(동일 run_id·done·backstop 미오염, AC-0327); ③ 부하 9동시→6×200+3×429(M5); ④ **PB-0008 Windows-browser** browser→worker→browser 왕복 PASS. **hotfix**: `_ask_worker_ready` naive/aware datetime tz 버그(readiness 영구 503) 라이브 포착·수정. **이월**: worker SIGTERM 장기 run 즉시중단(현 sweeper backstop)·on_event→lifespan. git: main FF 584b8dd(동시세션 0166/0167/0168 선점 → 0169 재번호, base rebase ×2), worktree `ai/claude/ask-worker` 정리.

**2026-06-09 TASK-0167 — 관리 콘솔 작은 화면 세로 잘림 수정 (CSS)** (REQ-20260609-0167, REV-20260609-0167 [SKIPPED:css-only], **Minor §12.3**). 사용자 보고(작은 브라우저 화면에서 화면이 잘림). admin-shell/admin-workspace 가 100vh+overflow:hidden 인데 usage pane 만 자체 overflow-y 누락 → 차트·표로 길어진 usage pane 이 작은 화면에서 세로 스크롤 불가로 하단 잘림. styles.css 의 usage pane 에 overflow-y:auto 추가(dashboard 패턴). CSS 셀렉터 1개 + 캐시버스터. 권한/엔드포인트/스키마/JS/HTML 구조 무변경.

**2026-06-09 TASK-0166 — LLM 사용량 차트 고도화** (REQ-20260609-0166, REV-20260609-0166 [SKIPPED:frontend-viz], **Minor §12.3**). TASK-0165 후속(사용자 지적 누락): 계정별 차트·hover 상세·막대 정확한 값·시간 단위 선택·추가 지표. 백엔드 `admin_llm_usage` 에 granularity(시/일/주/월, date_trunc 화이트리스트) + prompt/completion 분해 + 추정 비용(`_estimate_llm_cost_usd`, claude 근사·로컬 0) 추가. 프론트(의존성 0 SVG): 계정별 가로 막대 차트, 커스텀 hover 툴팁(전 차트, 값/비중/호출/비용), 막대 위 총합 값 라벨, 집계단위 드롭다운, 요약 비용 카드 + 모델별 표 prompt/completion·비용 컬럼. 권한/엔드포인트/스키마/시크릿 신규 0. node --check/py_compile + make test 218 passed/5 skipped(회귀 0). 비용은 추정(로컬=$0). Windows-browser(PB-0008) 검증 배포 후.

**2026-06-09 TASK-0164 — LLM 사용량 화면 차트화 (상용 AI 대시보드 구조 참조)** (REQ-20260609-0164, REV-20260609-0164 [SKIPPED:frontend-viz], **Minor §12.3**). TASK-0163 후속(사용자 요청 "상용 ai 제공 서비스 구조 참조 차트 형식"). 표 위주 화면을 Anthropic Console / OpenAI Usage 류로 시각화 — ① 일별 토큰 모델별 누적(stacked) 세로 막대, ② 모델별 비중 도넛(% 범례), ③ 역할별 가로 막대. 백엔드는 `by_day_model`(일별 × resolved_model 토큰) 집계만 추가(기존 컬럼·비파괴 read, 스키마 0). 프론트는 **순수 SVG·의존성 0**(CDN 회피 — 정적자산 baked·WSL 내부). 기존 표는 `<details>` 접이식 보존. 권한 `console.usage.read`(admin)/엔드포인트/스키마/시크릿 신규 0. node --check/py_compile PASS. Windows-browser(PB-0008) screenshot 검증 배포 후 수행.

**2026-06-09 TASK-0163 (cross-feature, 주관 feature-0002) — LLM 사용량 admin 계정별/역할별 집계 + 모델 해소 표시** (REQ-20260609-0163, REV-20260609-0163, **Major §12.3**). 본 feature 면(엔드포인트+프론트): `admin_llm_usage`(GET /api/admin/usage) 가 by_model `COALESCE(resolved_model, model)` 집계(별칭+실제 모델 노출) + by_account 를 이미 열린 MySQL conn 으로 `WebAccounts⋈WebRoles` username·role enrich(추가 conn 0) + 신규 순수 헬퍼 `_aggregate_usage_by_role` Python 폴딩(account None→`(시스템)`, role None→`(역할 없음)`) + 응답 `by_role`. `admin.html` 역할별 표(#usageByRole) + `admin.js loadUsage` by_role 렌더·계정 username/역할·모델 `별칭 → 해소`·캐시버스터 bump. 권한 `console.usage.read`(admin) **무변경 — RBAC/엔드포인트 신규 0**. 토큰 계측 복구(메인 추론이 회계 chokepoint 우회하던 RC1)·`resolved_model` 마이그레이션·in-process 동시 ask race 수정은 feature-0002 주관. 검증: make test 215 passed/5 skipped + node --check + outside-voice 적대적 diff 리뷰 NEEDS-TWEAK→PASS(BLOCKER 1 흡수).

**2026-06-08 TASK-0157 완료 — 요청 중단(interrupt) 진입점 복구** (REQ-20260608-0157, REV-20260608-0157 [SKIPPED:frontend-only-no-rbac-no-schema-no-secret], **Minor** §12.3 — frontend-only). 사용자 보고: 요청 후 "중단" 기능이 화면에 안 나타나고 진입 경로가 없음. **/investigate 근본 원인**: 취소 기능 자체(`/api/cancel` 엔드포인트 + 에이전트 루프 `_cancel_requested_for_run` 폴링 4지점 + RBAC `conversation.cancel.own/.any`)는 백엔드·루프 전부 정상. 그러나 진입 UI 인 중단(`#cancelBtn`)·즉시 답변(`#finalizeBtn`) 버튼이 커밋 `4ba71f5`(실행 단계 → `#stepSidePanel` 이전) 에서 **영구 숨김(`style="display:none"` 인라인 + "hidden permanently" 주석)된 `#progressCard` 안에 고아로 남음**. `renderProgress()` 의 `progressCardEl.classList.remove("hidden")` 가 인라인 style 우선순위에 가려 무효 → 부모가 영구 `display:none` → 자식 버튼은 `hidden` 토글과 무관하게 영원히 미렌더. 새 거처 `#stepSidePanel` 에는 닫기 버튼만 존재. 정상 동작 중 취소 진입점 0개(네트워크 끊김 복구 다이얼로그만 예외). **수정(사용자 선택: ChatGPT 패턴 — send→stop 모핑)**: (1) `renderComposer()` 가 `isCurrentConvBusy()` 동안 `#sendBtn` 에 `.is-stop`(위험색) + stop square 아이콘 + `aria-label="중단"` 적용, native `disabled` 를 풀어 클릭이 통과하게 함. (2) `#sendBtn` click 핸들러가 busy 면 `cancelCurrentRun()`, 아니면 `sendPrompt()` 분기. (3) hover 의 전송 모드 툴팁은 중단 모드에서 숨김. (4) 중단 권한 없으면 `is-access-blocked`+토스트(기존 `conversation.ask` 패턴 동형). 변경 2파일: `static/app.js`(아이콘 상수 + renderComposer morph + click 분기 + tooltip 가드) + `static/styles.css`(`.send-btn.is-stop`). **index.html 무변경** — 영구 숨김 strip 을 되살리지 않아 기존 TMI 정리 UX 와 충돌 없음. node --check PASS. backend/RBAC/DB schema/endpoint/secret 무변경. **이월(TODOS)**: 즉시 답변(finalize) 진입점은 동일 근본 원인으로 여전히 미노출 — 사용자가 단일-버튼 send-morph 를 선택하여 본 cycle 범위 밖. worktree `ai/claude/send-stop-button`(base d7826f5 — 작업 중 동시 머지된 #123 TASK-0156 inline-table-collapse 위로 rebase, 번호 충돌로 TASK-0156→0157 재부여).

---

**2026-05-28 TASK-0123 완료 — UX 2차 보완 7개 항목 구현** (CHG-20260528-0123, REV-20260528-0123 [SKIPPED:frontend-only], REQ-20260528-0123, **Minor** §12.3 — frontend-only, backend / RBAC / DB schema / endpoint contract 무변경). stop-hook 피드백으로 식별된 UX 미완료 항목 7개를 일괄 구현. **(1) 입력창 높이 일치** — `.composer-box` padding `9px→7px` 축소 (프로필 버튼 48px = padding 8×2 + icon 32px; composer 48px = padding 7×2 + textarea 34px, 정렬 맞춤). **(2) 파일 즉시 업로드 + ingest 병렬** — `_uploadComposerAttachment()` lazy 분기 완전 재작성: 파일 선택 시점에 즉시 `/api/new_conversation` 으로 cid 발급 + 업로드 + `state.composerAttachments.lazyConvCreating` 경쟁 방지 플래그. 대화 목록에 "(파일 첨부 중)" 임시 항목 삽입 + 렌더 갱신. **(3) 말풍선 첨부파일 표시** — 업로드 응답의 `signed_url` 을 bucket item 에 저장 + `_sendAttachmentSnapshot` 에 포함 + `refreshWorkspace()` 후 `lastUserMsg._attachments = snapshot` 재주입 (loadHistory 가 attachments 를 덮어쓰는 문제 해결). **(4) 첨부파일 다운로드** — chip 에 `has-download` class + click 핸들러 (presigned GET). styles.css 에 `.attach-chip-dl` + hover 효과. **(5) 공유뷰 CSV 다운로드** — `share.js` 에 `downloadRowsAsCsv()` helper (BOM UTF-8, RFC4180 escape) + SQL 결과표 하단 "CSV 다운로드" 버튼. `share.css` 에 `.share-csv-download-btn`. (공유뷰 file attachment 는 backend 가 permission-gated 로 숨김 → SQL 결과 CSV 로 대체). **(6) LLM step/thinking 표시** — `renderProgress()` 에 `progressCardEl.open = true` + `renderPendingAssistantBubble()` 의 step details `detailsEl.open = true` (step 도착 시 자동 펼침). **(7) 첫 대화 상태 dot 갱신** — lazy-create 성공 path 에서 `startProgressPolling` 직전 `state.conversations` 에 신규 conv 최소 항목 추가 + `renderConversationList()` 호출 → polling 첫 tick 에서 dot 갱신 가능. node --check PASS. worktree `ux-compact-redesign` (branch `ai/root/ux-compact-redesign`), commit `095f9b1`. docker cp 배포 완료 (repo-web-1:/app/web/static/).

---

**2026-05-26 TASK-0108 완료 — Sprint 3 (B: DDL/KB 보강) admin-only manual KB ingest** (CHG-20260526-0108, REV-20260526-0002, REQ-20260526-0108, **Major** §12.3 — RBAC 신규 코드 + admin endpoint + manual KB fact ingest path). BRIEFING-attachment-multi-cycle.md §6.3 Sprint 3 Cycle 3 implementation. admin 콘솔 "스키마 정의서 KB 등록" pane 에서 text/markdown/.sql 첨부 본문을 `AgentMemoryFactEntries` 의 manual fact (SourceType='manual' 고정, Weight=90 고정, ConversationId='__kb_manual__' reserved sentinel, FactKey=ScopeKey) 로 등록. 동일 ScopeKey 재ingest 시 기존 active row 는 Weight=0 으로 logical supersede (Status 컬럼 추가 회피, `AgentMemoryFacts` VIEW 의 Weight DESC tie-break 가 자연 hide → 회귀 0). **핵심 산출** 7건: (a) `app.py` PERMISSION_DEFINITIONS 에 `attachment.kb.write.any` 1 코드 + SEED admin/dba role catchup + 신규 endpoint `GET /api/admin/attachments` (list) + `POST /api/admin/attachments/kb-ingest` (ingest), (b) `unit/feature-0002-agent-core/src/modules/kb_ingest.py` 신규 (~205 LOC, ingest_manual + 4-step SELECT FOR UPDATE + ON DUPLICATE KEY UPDATE Id=LAST_INSERT_ID(Id)), (c) `admin.html` sidebar 의 "KB 등록" tab + workspace 의 `<section data-admin-pane="kb-ingest">` (list-detail layout), (d) `admin.js` `adminState.kbIngest` + `mountKbIngestPane` + load/render/submit handlers + client regex validation, (e) `tests/test_kb_ingest.py` 10 unit test (FakeConn — happy/supersede/reactivate/mixed/edge case, 10 PASS), (f) `tests/test_kb_ingest_rbac.py` 8 e2e RBAC 시나리오 (사용자 운영 turn 실행), (g) `AGENTS.md` §11.3 신설 — KB Fact 등록 정책 (Source/SourceType/Weight/ConversationId 4열 + supersede 정책). **outside-voice review (Codex `codex-cli 0.130.0`, `REV-20260526-0002`) Verdict BLOCK → PASS 전환 (Critical 5 + Nice-to-have 1 본 cycle 내 흡수)**: (B-1) 동시 ingest race → SELECT FOR UPDATE 명시 lock + reactivated 명시 계산 / (B-2) source_type/weight client spoofable → 서버 상수 고정 (request body 무시) / (B-3) admin endpoint = `console.access` AND `attachment.kb.write.any` / (B-4) audit fail-soft → transactional audit (실패 시 rollback) / (B-5) scope_key regex `^[A-Za-z0-9_.\-]{1,96}$` + audit hash prefix only. py_compile + node --check + 10 unit PASS. base = main HEAD (5448611 — KB Postgres bootstrap fix 흡수 후, dual-write 영역 자연 정합). **Runtime 검증 (사용자 운영 turn)**: docker compose build memory-init web + up -d --force-recreate web → admin 콘솔 → "KB 등록" tab → text/markdown 첨부 1건 ingest → AgentMemoryFactEntries 의 ConversationId='__kb_manual__' Weight=90 row + WebAuditEvents 의 attachment.kb.ingest row + ChangeJson 의 scope_key_hash_prefix 확인.

**2026-05-22 TASK-0107 완료 — 첨부 sandbox 활성화 + LLM context inject + drag&drop UX 확장** (CHG-20260522-0107, REV-20260522-0107, REQ-20260522-0107, **Major** §12.3 — LLM 동작 변경 + sandbox SQL 동선 + UI 진입점 확장). 사용자 직접 보고 2건 일괄 fix. **(1) 파일 첨부 후 LLM 이 "실제 내용을 직접 볼 수 없습니다" 응답** — TASK-0094 sandbox ingest 파이프라인 정의는 있었으나 caller 미ship → MetaJson 에 sandbox_table_name 미기록 → ATTACHED FILES 영역이 schema 명을 모름 → LLM SQL tool 이 SELECT 시도 안 함. **수정 (3-phase)**: Phase A — `app.py` upload endpoint audit dispatch 직후 `threading.Thread(daemon=True)` spawn (kind=csv|xlsx). 신규 helper `_ingest_attachment_background` 가 storage_minio bytes 받기 → `CREATE SCHEMA IF NOT EXISTS agent_attachment_<sha256(cid)[:32]>` (root user 단일-user MVP — 4-user 분리는 후속 cycle, .env 비밀번호 미설정) → `_open_memory_connection(database=schema)` → `sandbox_ingest.ingest_attachment` → MetaJson 에 sandbox_schema_name + sandbox_table_name (csv) 또는 sheets[] (xlsx) 기록 + UploadStatus='ingested'. 실패 → `_mark_ingest_failed` 가 'failed' + degraded_reason. `db.py` connect() 에 `agent_attachment_*` 패턴 → primary 라우팅 강제 (replica latency / 미배포 환경 안전). Phase B — `agent_core.py` `_build_attachment_context_section` 강화: information_schema.columns SELECT (column명 + data_type) + `SELECT * FROM <schema>.<table> LIMIT 5` sample rows (markdown 표, 80자 truncate, pipe escape, table cap 20) + 명시 INSTRUCTION ("first try to answer from the sample rows above. If more data is needed, call execute_sql … Do NOT ask the user to paste the file contents"). UploadStatus='uploaded' / 'failed' 분기 별 안내. **(2) drag&drop 영역 협소 + 새 대화 시 첨부 차단** — composer-wrap 만 drop zone + pendingSentinel 미발급 시점에 `_uploadComposerAttachment` 가 "대화 컨텍스트 미정" toast 로 차단. **수정**: index.html 에 chat-pane 자식 `#chatDropOverlay` (점선 카드 + 아이콘) 추가, styles.css 에 `.chat-drop-overlay` (absolute inset 0 + backdrop-filter blur + fade-in 120ms) + `.chat-pane { position: relative }`. app.js `_bindComposerAttachmentEvents` 에 chat-pane scope 핸들러 + `_isFileDrag()` types Files guard + dragCounter 중첩 추적 + window dragend/drop reset (drop miss 방어) + chat-pane 밖 drop 시 브라우저 기본 동작 preventDefault. `_uploadComposerAttachment` 진입 시 컨텍스트 미정 검출 → `conversation.create` 권한 검증 → `pendingNewConversation=true` + `_newPendingSentinel()` + 모든 render 호출 → 기존 lazy-create path 재사용. py_compile + node --check PASS. backend RBAC / DB schema / endpoint contract / D11 consent / D13 server-side bytes 무변경. worktree `ai/claude/0107-attachment-content`.

---

**2026-05-22 TASK-0106 완료 — 첨부 storage 모듈 import 경로 + lazy-create 첨부 staging** (CHG-20260522-0106, REV-20260522-0106 [SKIPPED:no-rbac-no-schema-no-secret-handling], REQ-20260522-0106, **Major** §12.3 — 외부 storage 통합 + 사용자 노출 첨부 동선 회복). 사용자 직접 보고 2건 일괄 fix. **(1) 첨부 업로드 시 `storage 모듈 import 실패` toast** — `app.py` 의 `from modules import storage_minio` (3 callsite: vision inline `_prepare_vision_inline_images` L6044, upload endpoint L7555, metadata endpoint L7771) + `from modules import sandbox_schema` (grant drift health L11862) 가 잘못된 namespace 검색. **근본 원인**: Dockerfile 이 feature-0002-agent-core 의 unified namespace (14 module cross-injection) 를 `/app/modules` 로 copy + feature-0003-agent-web-ui 의 module 은 `/app/web/modules` 로 별도 copy. `storage_minio.py` 와 `sandbox_schema.py` 는 후자에 위치. `from web.modules import …` 로 4 callsite 교체. `attachment_reconciliation.py` 의 `_delete_minio_object()` 는 docker container (`/app/web/modules`) + host dev (sibling sys.path) 양쪽 호환을 위해 `try: from web.modules import storage_minio / except ImportError: sys.path 삽입 fallback` 의 dual-mode 보강. **(2) "+ 새 대화" 클릭 후 첫 메시지 전 첨부 차단** — `_uploadComposerAttachment()` 의 `if (isLazy) showToast("첨부는 대화가 생성된 후 가능합니다...")` 즉시 차단. lazy-create (TASK-0048) 가 backend cid 발급을 첫 send 까지 지연시키므로 cid 필수의 `/api/conversations/{cid}/attachments` 호출 불가했던 부수 효과. **수정 (Option A — client-side staging)**: lazy 분기에서 즉시 차단 대신 pendingSentinel bucket 에 `{status: "staged", _localFile: File}` 보관 + "첨부가 추가되었습니다 (첫 메시지와 함께 업로드됩니다)" toast. `sendPrompt()` 의 lazy-create attachment_ids 빌드 후 staged ≥1 감지 시 `/api/new_conversation` 으로 cid 즉시 발급 → `_flushStagedAttachmentsToCid(earlyCid, pendingKey)` 신규 helper 가 staged 일괄 업로드 (성공 시 target bucket 으로 이동, 실패는 status="failed" pill) → askBody 를 `lazy_create=true` 에서 `conversation_id=earlyCid` 즉시-cid 모드로 전환 + `attachment_ids` union (기존 ready snapshot + 새 uploadedIds). staged 가 0 인 lazy-create 는 기존 단일 호출 유지 (TASK-0048 정신: "+ 새 대화" 시 빈 row 누적 방지). pill rendering 에 `data-staged="true"` 속성 + "(첫 메시지와 함께 업로드)" tooltip + `_toggleAttachmentPill()` 의 staged 토글 = remove (실수 클릭 자연스러움). py_compile + node --check PASS. backend / RBAC / DB schema / endpoint contract / 암호화 알고리즘 / D11 consent gate / D13 server-side bytes / D7 MIME / D8 size cap / D12 HMAC 모두 무변경. worktree `ai/claude/0106-attachment-fix`.

---

**2026-05-22 TASK-0105 완료 — Profile Drawer '내 감사 로그' 탭 제거 (일반 사용자 비노출)** (CHG-20260522-0008, REV-20260522-0008 [SKIPPED:frontend-only], REQ-20260522-0008, **Minor** §12.3). 사용자 직접 요청 — 일반 사용자에게 Profile Drawer 내 '내 감사 로그' 탭이 노출되어선 안 됨. TASK-0089 가 추가한 `profileAuditTab` 버튼 + `data-profile-pane="audit"` 패널 + 관련 JS 함수 9개 (`_profileAuditEscapeHtml` / `_profileAuditFormatDt` / `_profileAuditHasReadPermission` / `updateProfileAuditTabVisibility` / `_profileAuditReadFilters` / `_profileAuditClearFilters` / `loadProfileAuditList` / `renderProfileAuditList` / `renderProfileAuditDetail` / `attachProfileAuditHandlers`) + `state.profileAudit` 초기값 + `profile-audit-*` CSS 블록 전체를 index.html / app.js / styles.css 에서 제거. backend `/api/profile/audits` 및 `/api/profile/audits/{event_id}` endpoint 무변경 (admin 도구 또는 향후 정책 변경 대응 가능). admin 콘솔 '감사 로그' 탭 무변경. node --check + py_compile PASS. worktree `ai/claude/0105/remove-audit-tab`.

---

**2026-05-22 TASK-0104 완료 — 외부 노출 web 컨테이너 HTTPS 종단 활성화** (CHG-20260522-0007, REV-20260522-0007 [SKIPPED:non-policy-doc], REQ-20260522-0007, **Major** §12.3 — 외부 사용자 전원 영향 + 자격증명 처리 동선의 secure-channel 요건 충족). 외부 사용자가 `https://112.185.196.20:18080/` 로 접속할 수 없던 이슈 보고. **근본 원인**: `repo/.env` 는 `ENABLE_WEB_TLS=1` + `WEB_TLS_CERT_FILE` / `WEB_TLS_KEY_FILE` 가 설정되었고 `docker-compose.yml` 의 web entrypoint 에는 `if [ "$ENABLE_WEB_TLS" = '1' ]; ... --ssl-keyfile ...` 분기가 있으나, dev 편의용으로 작성된 `docker-compose.override.yml` (gitignored, `.example` template 추적) 가 entrypoint 자체를 평문 HTTP uvicorn 으로 강제 override 하고 있었음. compose 자동 merge 로 dev override 가 base 설정을 덮어써서 external-exposed 시나리오에서도 평문 HTTP 만 listening. TASK-0103 (CHG-20260522-0006) 에서 클라이언트 secure-context guard 는 추가했지만 secure channel 자체가 비활성 상태. **수정**: (1) `docker-compose.override.yml` 의 web entrypoint 를 `--ssl-keyfile /certs/mysql-ai.company.local/privkey.pem --ssl-certfile /certs/mysql-ai.company.local/fullchain.pem` 포함한 HTTPS 종단으로 교체 (same-port 18080 HTTPS-only 정책 — 사용자 결정). (2) `docker-compose.override.yml.example` 에는 Variant A (local dev plain HTTP, gstack browse / curl 편의용) / Variant B (외부-노출 HTTPS, 본 cycle default) 두 형태를 주석으로 명시 — 운영자 선택 가능. (3) 기존 인증서 (`../artifacts/certs/mysql-ai.company.local/{fullchain,privkey}.pem`) 는 SAN 에 `IP Address:112.185.196.20` 이미 포함되어 있어 재발급 불필요. 호스트 포트 매핑 (`${WEB_PORT}:8000` = `18080:8000`) 그대로. **외부 영향**: 같은 포트의 HTTP 동시 제공은 안 되며, 기존 HTTP 18080 사용자는 모두 HTTPS 로 전환 필요. self-signed 인증서이므로 첫 접속 시 브라우저가 `NET::ERR_CERT_AUTHORITY_INVALID` 경고를 표시 — `고급 → 진행` 으로 우회. **검증**: `sudo docker compose up -d web` 으로 재기동 후 (1) 컨테이너 로그 `Uvicorn running on https://0.0.0.0:8000` 확인. (2) `curl -sk https://112.185.196.20:18080/` → HTTP 200 + `<title>DQA — Database Query Assistant</title>` 응답. (3) `curl http://112.185.196.20:18080/` → 연결 실패 (예상 — TLS 종단으로 변경됨). backend / RBAC / endpoint contract / DB schema / Python 코드 / Frontend 클라이언트 코드 무변경. TASK-0103 의 "blocked banner" 가드는 후방 안전망으로 유지되며, 본 cycle 로 정상 동선 (HTTPS) 이 회복되면서 모든 외부 사용자에게 WebCrypto SubtleCrypto 가 정상 동작.

---

**2026-05-22 TASK-0103 완료 — API Vault secure context 사전 차단 + UX 안내** (CHG-20260522-0006, REV-20260522-0006 [SKIPPED:non-policy-doc], REQ-20260522-0006, **Major** §12.3 — 외부 사용자 전원 영향 + 자격증명 처리 동선). 외부 사용자가 `http://112.185.196.20:18080/` 로 접속하여 OpenAI API Key 를 입력했을 때 모호한 toast 만 출력되며 저장 안 되는 이슈 보고. **근본 원인**: `encryptPlainApiKey()` 가 `window.crypto.subtle.importKey` 를 호출하는데, WebCrypto SubtleCrypto 는 **secure context (HTTPS / localhost) 에서만 정의**됨 (MDN). 외부 IP 의 HTTP 접속 환경에서는 `window.crypto.subtle = undefined` → `Cannot read properties of undefined (reading 'importKey')` 예외 → catch 블록의 `showToast(error.message ...)` 가 사용자에게 원인을 명확히 전달하지 않음. 서버는 `/api/api-vault/options` 응답에 `requires_secure_context: True` 를 내려주었으나 클라이언트가 이 신호를 활용하지 않아 사전 가드 부재. **수정**: (1) `isVaultCryptoAvailable()` helper 추가 (`window.isSecureContext && window.crypto.subtle`). (2) `updateVaultReadiness()` 에 `blocked` 신규 상태 — banner 빨간 dot + "현재 접속 (...) 은 보안 컨텍스트가 아니어서 API 키를 암호화할 수 없습니다. HTTPS 또는 localhost 로 접속해 주세요." 안내. `state.apiVaultOptions.public_url` 이 https 면 보안 접속 주소도 표기. (3) `syncVaultSteps()` 가 `cryptoOk = false` 시 모든 step 을 `data-state="disabled"` (CSS 의 `pointer-events:none + opacity 0.55` 활용) + `saveVaultBtn.disabled = true`. (4) `encryptPlainApiKey()` 진입 시점에도 `isVaultCryptoAvailable()` 사전 검증 — UI 우회 시도 시 명시적 한국어 안내 throw. (5) `vault-banner[data-state="blocked"]` 에 빨간 색상 토큰 추가 (styles.css). cache-bust `v=20260522-vault-secure-context` (index.html). backend / RBAC / endpoint contract / DB schema / 암호화 알고리즘 (PBKDF2 + AES-GCM) 무변경. `docker compose build web` + `up -d --no-deps web` 으로 배포 — 30 초 다운타임. 외부 IP HTTP 환경에서 사용자가 즉시 사유 진단 가능 + saveVaultBtn 비활성으로 우발적 시도 차단. 근본 해결 (HTTPS 종단점 추가) 는 후속 인프라 작업으로 분리.

---

**2026-05-22 TASK-0102 완료 — topbar `관리 콘솔` 버튼 role fallback gate** (CHG-20260522-0005, REV-20260522-0005 [SKIPPED:non-policy-doc], REQ-20260522-0005, **Minor** §12.3). 테스트에서 `sales` 역할 사용자에게 topbar 관리 콘솔 버튼이 노출되는 현상 확인. **근본 원인**: TASK-0100 에서 추가한 `console_access` 플래그가 서버 미재시작 또는 구버전 서버 실행 시 존재하지 않아 fallback 경로가 없었음. **수정**: `canOpenAdminConsole()` 에 `role.key` 기반 fallback 추가 — `console_access` 가 서버 응답에 포함된 경우 그것을 사용, 없으면 `role.key === "admin"` 으로 fallback. role 필드는 TASK-0098 이전부터 항상 직렬화되므로 서버 버전 무관하게 존재. app.js + index.html(cache-bust `v=20260522-admin-topbar-rbac`) 변경. backend / RBAC / DB / endpoint 무변경.

---

**2026-05-22 TASK-0100 완료 — `관리 콘솔` 버튼 RBAC gate 수정** (CHG-20260522-0004, REV-20260522-0004 [SKIPPED:non-policy-doc], REQ-20260522-0004, **Minor** §12.3). TASK-0098 의 `can()` 단순화(`Boolean(state.user)`) side-effect 로 인해 `canOpenAdminConsole()` 이 로그인한 모든 사용자에게 `true` 반환 → `관리 콘솔` 버튼이 admin 역할 이외의 사용자(operator/sales/pending) 에게도 노출되던 이슈 수정. **수정 방식**: `_serialize_account()` 에 `console_access: _account_has_permission(account, "console.access")` 최소 플래그 추가 + `canOpenAdminConsole()` 이 `Boolean(state.user?.console_access)` 을 검사하도록 변경. TASK-0098 의 "permissions 전체 노출 차단" 설계를 유지하면서 UI gate 에 필요한 최소 정보만 전달. backend RBAC catalog / DB schema / endpoint contract 무변경. py_compile + node --check PASS. cache-bust `v=20260522-console-access-gate`. worktree `ai/claude/issue-admin-console-btn-rbac`.

---

**2026-05-22 TASK-0099 완료 (docs-only tracker hygiene) — audit subsystem followup backlog 8/8 closure marker** (CHG-20260522-0003, REV-20260522-0003 [SKIPPED:doc-only-tracker-hygiene], REQ-20260522-0003, **Minor** §12.3). TASK-0073 audit subsystem followup backlog 의 8 entries (TASK-0086 ~ 0093) 8/8 완료를 tracker 에 정확히 반영. TASK.md 의 stale `[ ]` 체크박스 2건 close: (1) line 152 TASK-0072 (main 통합 `f298f90` + post-deploy hotfix bundle TASK-0074/0075/0076/0077/0078/0079/0080 deployed but 상태 `outside-voice-review` 미갱신), (2) line 2767 TASK-0073 `AGENT_AUDIT_ENABLED=0 + AGENT_MODE=prod` startup fail-closed acceptance (TASK-0092 의 7 vector matrix V1-V3 fail-closed scenario 가 정확히 검증). TASK-0073 의 acceptance criteria 7건 모두 close. docs-only cycle — 코드 / RBAC / 스키마 / endpoint 변경 0. outside voice trigger 미해당 (`feedback_outside_voice_for_rbac` 미발동).

### TASK-0073 audit subsystem followup backlog 8/8 완료 (2026-05-20~22)

| TASK | 등급 | Summary | CHG | REV |
|---|---|---|---|---|
| TASK-0086 | Major §12.3 | `WebAccountActivity` legacy table DROP + dual write 종료 | CHG-20260520-0005 | REV-20260520-0005 [AGENT-TEAM:codex] |
| TASK-0087 | Major §12.3 | 외부 LAN trust 강화 — Caddy XFF 정규화 + `_get_client_ip()` 조건부 trust | CHG-20260520-0010 | REV-20260520-0010 [AGENT-TEAM:codex] |
| TASK-0088 | Minor §12.3 | `slow_query_log` 통합 ADR-0020 Decoupled 채택 (docs only) | CHG-20260520-0007 | REV-20260520-0007 [AGENT-TEAM:codex] |
| TASK-0089 | Minor §12.3 | 작업 화면 audit drawer UX (profile drawer "내 감사 로그" 탭) | CHG-20260520-0009 | REV-20260520-0009 [AGENT-TEAM:codex] |
| TASK-0090 | Minor §12.3 | CSV streaming export (hard cap 50k 제거 + keyset cursor pagination) | CHG-20260520-0008 | REV-20260520-0008 [AGENT-TEAM:codex] |
| TASK-0091 | Major §12.3 | PATCH admin/products audit before-state full snapshot + audit integrity fix | CHG-20260520-0006 | REV-20260520-0006 [AGENT-TEAM:codex] |
| TASK-0092 | Minor §12.3 | `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` startup fail-closed 7 vector matrix 검증 | CHG-20260520-0004 | REV-20260520-0004 [AGENT-TEAM:codex] |
| TASK-0093 | Minor §12.3 | `bin/verify-completion.sh check_12` audit endpoint routing 정적 검사 | CHG-20260520-0003 | REV-20260520-0003 [AGENT-TEAM:codex] |
| TASK-0099 | Minor §12.3 | Audit followup backlog tracker hygiene (docs-only closure) | CHG-20260522-0003 | REV-20260522-0003 [SKIPPED] |

**8 audit followup task 의 외부 voice review 결과 요약**: 각 task 모두 Codex outside voice (consult mode, model_reasoning_effort=high) 흡수 후 Plan v2 redesign. 사용자 명시 결정으로 1 finding (TASK-0087 Major #1) 만 거부, 나머지 47 findings 모두 흡수.

---

**2026-05-22 TASK-0098 ship (PR #49) — Profile Drawer 탭 재구성 + 권한 정보 API 단위 차단** (CHG-20260522-0002, REV-20260522-0002 [AGENT-TEAM:codex-outside-voice], REQ-20260522-0002, **Critical** §12.3). 사용자 직접 요청 (2026-05-21). Profile Drawer 탭 5 → 4 = `[프롬프트, 보안 및 계정, API Vault, 내 감사 로그(gated)]` (보안+계정 통합 + "활동 정보" 최상단). "권한 현황" 패널 운영자 전용 분류 — 일반 사용자 UI + `/api/auth/me` 양쪽 차단. `/api/admin/me` 신규 endpoint 분리 (console.access gate, Codex F1 blocker fix). `_serialize_account(account, *, include_permissions: bool = False)` 시그너처 + 7 self callsite 자동 permissions 제거 + admin 3 callsite 명시 보존. frontend `can()` = `Boolean(state.user)` 단순화 ("표시 허용 + 실행은 backend 403 fallback" 패턴, Codex F5). `apiFetch` 403 공통 toast + backend 403 메시지 5 패턴 9 callsite normalize. admin.js `/api/auth/me` → `/api/admin/me` 전환. TASK-0089 "내 감사 로그" 탭 보존. tests 신규 9 시나리오 (4+5). Codex outside voice 6 findings 흡수 + 사용자 메모 `feedback_outside_voice_for_rbac` 정책 적용. **PR #49 multi-race rebase**: 본 cycle 원래 4 commit (base 8888130) → main stale 진행 (#45 v3.10.0 + #47 TASK-0089 + #48/#50 + #52/#61 TASK-0094 첨부 multi-cycle Sprint 1 + DQA 브랜딩 + TASK-0095/0096 v2) 흡수 후 main HEAD `20f0344` 위 단일 squash commit. ID reassign: TASK-0094→TASK-0098 / REQ-20260521-0001→REQ-20260522-0002 / AC-0199~0207→AC-0226~0234 / CHG·REV-20260521-0001~0004→CHG·REV-20260522-0002 / cache-bust `v=20260522-task-0098-perms`. 원래 4 commit backup branch `backup/profile-tabs-restructure-pre-rebase` 보존. py_compile + node --check + verify-completion --pre-commit PASS. 실 컨테이너 9 시나리오 smoke + UI dogfood 2 role 사용자 위임. worktree `ai/claude/profile-tabs-restructure`.

---

**이전 cycle (TASK-0087)**:

**2026-05-21 TASK-0087 완료 (Phase A~E 일괄) — 외부 LAN trust 강화** (CHG-20260520-0010, REV-20260520-0010 [AGENT-TEAM:codex-outside-voice], REQ-20260520-0002, **Major** §12.3). TASK-0073 audit subsystem followup backlog 의 마지막 항목 (TASK-0086~0093 8건의 8번째 = 0087). TASK-0073 Eng review E3 의 deferred 항목 (`_get_client_ip(request)` X-Forwarded-For 무조건 trust = 사내 LAN + Caddy proxy 전제, 외부 LAN/공개 인터넷 노출 시 IP spoof 위험) 을 명시적 정책 + 코드로 lock-in. Plan v1 (RFC1918 trust + silent skip + Caddy reverse_proxy 내부 trusted_proxies) → Codex outside voice review 6 findings (Major 5 + Minor 1) → Plan v2 (Caddy XFF 정규화 + mode-aware fail-loud + XFF IP 검증) 흡수. 사용자 명시 결정: RFC1918 default 유지 (사내 dev/staging 전제) + docker-compose port mapping 변경 별 cycle. 본 변경은 feature-0003 + feature-0006 dual ownership.

**Phase 별 요약**:
- **Phase A** — `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile` 의 `reverse_proxy web:8000` 블록에 `header_up X-Forwarded-For {client_ip}` 추가. Caddy 가 받은 임의 XFF 를 본인이 본 TCP peer IP 로 덮어쓴다. 단일 hop 정규화 → multi-hop / spoof 차단.
- **Phase B** — `unit/feature-0003-agent-web-ui/src/app.py` 의 `_get_client_ip()` 재작성:
  - imports 에 `ipaddress`, `sys` 추가
  - `_parse_trusted_proxies(raw)` helper: 콤마 분리 + `ipaddress.ip_network(token, strict=False)` 파싱. invalid 토큰은 prod/staging `RuntimeError`, dev/test stderr WARNING + skip
  - module-level `WEB_TRUSTED_PROXIES`
  - `ENABLE_WEB_TLS_PROXY=1` + empty env 조합 startup gate (prod/staging RuntimeError, dev/test WARNING)
  - `_is_trusted_proxy(host)` helper
  - `_get_client_ip(request)`: direct_ip 가 trusted proxy 일 때만 XFF 첫 토큰 사용 + `ipaddress.ip_address(first)` 검증 + 실패 시 direct_ip fallback
- **Phase C** — `docs/SECURITY.md §9.7` 갱신 — 기존 3 bullet "deferred to feature-0006" 마커를 8 bullet 정책 (Caddy XFF 정규화 / 조건부 trust / XFF token 검증 / RFC1918 사용자 명시 결정 trade-off / mode-aware fail-loud / proxy mode + empty / schema 호환 / share token 미래 결합) 으로 교체.
- **Phase D** — feature-0003 + feature-0006 양쪽 docs 갱신 (TASK / MODIFY / REVIEW / REPORT / TEST / FUNCTION).
- **Phase E** — verify-completion + commit + cycle-finalize.

**Verification**:
- py_compile PASS (app.py 51 lines 추가)
- Caddyfile validate: `docker compose run --rm caddy caddy validate --config /etc/caddy/Caddyfile` 정상 (live 검증 사용자 위임)
- Codex outside voice review 6 findings (Major 5 + Minor 1) — Verdict NEEDS_REVISION → Plan v2 흡수 (5 흡수 + 1 사용자 명시 거부)
- TEST.md §4 8 시나리오 추가 (trusted+valid XFF / trusted+invalid XFF / trusted+empty 첫항목 / untrusted+XFF spoof 차단 / IPv6 trusted+XFF / invalid env prod fatal / proxy mode + empty prod fatal / caddy validate)

**Backward 호환**: `WEB_TRUSTED_PROXIES` 미설정 = `_get_client_ip()` 가 항상 direct_ip 반환 (caddy 환경에서는 caddy container IP). proxy mode + empty env warning/fatal 로 회귀 가시화. 운영자가 RFC1918 권장값 설정 시 기존 audit IP 품질 유지.

**TASK-0073 audit subsystem followup backlog 완료**: TASK-0086 (DROP) + TASK-0088 (slow_query_log ADR) + TASK-0089 (drawer UX) + TASK-0090 (CSV streaming) + TASK-0091 (product audit snapshot) + TASK-0092 (audit prod fail-closed) + TASK-0093 (verify-completion check_12) + **TASK-0087 (외부 LAN trust) — 본 cycle 완료** → 8건 모두 완료.

---

**2026-05-21 TASK-0095 완료 (Phase A~F 일괄, Phase G verify-completion + commit 진행 예정) — 시스템 프롬프트 누적 구조 최상위 GLOBAL layer 신설** (CHG-20260521-0003, REV-20260521-0003 [SELF-REVIEW], REQ-20260521-0003, **Major** §12.3). 사용자 직접 요청 — "최상위 전역 프롬프트도 구성해주세요. Product / Role / Account 에 기본적으로 처음 누적되어 요청사항에 적용될 부분입니다." 4 layer (BASE → Product → Role → Account) 의 BASE 가 코드 상수 hard-code 라 운영자 수정 불가하던 구조를 5 layer (GLOBAL → Product → Role → Account, BASE = code constant fallback) 로 확장. WebSystemPrompts 테이블의 scope discriminator 가 이미 'global' 을 수용 (VARCHAR(16)) — schema 무변경. RBAC 권한 2 종 신설 (`system_prompt.global.read` / `.write`, group=`settings`, admin only 자동 grant). 관리 콘솔 sidebar 에 신규 `설정` 탭 + 확장 가능한 `admin-settings-section` sub-section 패턴 도입 — 차후 운영 항목 추가 시 동일 패턴으로 sub-section 누적. AC-0011 갱신 + AC-0199 ~ AC-0204 신설.

**Phase 별 요약**:
- **Phase A** — `agent_core.compose_system_prompt(conn, ...)` 함수 진입부에 GLOBAL row fetch + graceful fallback (row 없음 / 빈 본문 / 조회 실패 → 코드 상수 SYSTEM_PROMPT 회귀).
- **Phase B** — `_ensure_seed_global_system_prompt(conn)` helper 신설, 부트스트랩에서 idempotent 호출. agent_core import 실패 / seed 본문 빈 경우 silent skip.
- **Phase C** — `PERMISSION_DEFINITIONS` 에 2 권한 추가. `_ensure_seed_roles` admin catchup list 에 두 권한 코드 추가.
- **Phase D** — GET/PUT `/api/admin/system-prompts` scope allowlist 에 `global` 추가 + `system_prompt.global.read/.write` 권한 가드.
- **Phase E** — `admin.html` `설정` 탭 + `admin-settings-section` sub-section 패턴, `admin.js` switchTab handler + mountSettingsSections() + buildSystemPromptEditor scope='global' 분기, `app.js` PERMISSION_GROUP_ORDER + permissionGroupOf + LABELS/DESCRIPTIONS 동기화, `styles.css` sub-section CSS rules.
- **Phase F** — FUNCTION/MODIFY/REVIEW/REPORT 갱신.
- **Phase G** — verify-completion + commit + main fast-forward (다음).

**Verification**: py_compile PASS (agent_core.py + app.py), node --check PASS (admin.js + app.js). live runtime smoke (관리 콘솔 `설정` 탭 진입 + 본문 수정 + LLM 호출 시 적용 확인) 사용자 검증 위임.

**Follow-up (CHG-20260521-0004 / REV-20260521-0004)**: live deploy 후 사용자 요청 "기능적인 검증 및 스크린샷을 통하여 UI 구성도 검증해주세요." 진행 중 발견된 hot-fix — fast-path catchup `_ensure_seed_catchup(conn)` 에 `_ensure_seed_global_system_prompt(conn)` 호출 누락. CHG-20260521-0003 가 slow path (`_ensure_web_tables`) 에만 helper 를 두었지만 기존 배포는 fast path 만 타기 때문에 GLOBAL row 가 자동 seed 안 되어 textarea 빈 채 노출. `_ensure_seed_role_system_prompts(conn)` 직후 1줄 추가로 보정. idempotent — 양쪽 path 호출 시에도 INSERT 1회만.

**Follow-up (TASK-0096 / CHG-20260521-0005 / REV-20260521-0005, REQ-20260521-0004, Minor §12.3 — `설정` pane sub-sidebar + panel 확장 패턴)**: 사용자 직접 요청 — TASK-0095 검증 완료 후속, "`설정` 탭 내부 화면을 `계정`, `역할`, `제품` 과 같이 패널을 분리해줄 수 있을까요? 차후 `전역 시스템 프롬프트` 항목 외에도 설정 내 많은 항목이 추가될 예정인데 현재는 확장성이 너무 좁게 구현되어 있습니다." 단일 sub-section 누적 구조 → 좌측 sub-sidebar (항목 nav) + 우측 panel 의 2-column grid 확장 패턴으로 전환. 새 항목 추가 절차 = nav button + panel article + `SETTINGS_PANEL_MOUNTERS` 등록 3 단계, panel 마운트는 첫 활성화 시 1회 lazy 실행. UI restructure only — 데이터/API/권한 무영향. AC-0210 신설, AC-0203 갱신 (sub-section → panel 명명).

**Follow-up v2 (TASK-0096 / CHG-20260521-0006 / REV-20260521-0006, REQ-20260521-0004, Minor §12.3 — `설정` pane 을 계정/역할/제품 과 동일한 list-detail 패턴으로 정렬 + 검색창)**: 사용자 직접 follow-up 피드백 — "계정, 역할, 제품 탭과 일관된 디자인이 아닌것으로 확인되었습니다. 검색창을 포함하여, 해당 탭들과 일관된 디자인으로 구성해주세요." v1 의 sub-sidebar (`admin-settings-shell` + `admin-settings-nav`) 변형이 다른 admin pane (계정/역할/제품) 의 5단 master-detail 패턴과 시각 일관성 부족. v2 에서 sub-sidebar 전용 클래스 일괄 제거 후 `admin-list-detail` (좌측 `admin-list-col` (검색창 + section-label + nav rows) + 우측 `admin-detail-col` (panel)) 그대로 차용. nav row 는 `.admin-list-row.admin-list-row--nav` 변형 (체크박스 슬롯 hidden). 검색창 = `admin-search` 재사용 + row 의 `data-settings-tab/-group/-keywords` + textContent 합집합 substring 매칭. AC-0210 갱신 (list-detail + 검색 hook 표기) + AC-0203 갱신 (panel 정렬 후 sentence 보강).

---

**2026-05-21 TASK-0094 PLAN-APPROVED — 첨부 multi-cycle (A CSV + B DDL/KB + C Vision + D PDF RAG) BRIEFING Revision 2 lock-in** (CHG-20260521-0001, REV-20260521-0001 [SUBAGENT:codex], REQ-20260521-0001, **Critical** §12.3). Codex outside-voice review 2 회 흡수 (REV-20260520-0001 1차 17 Valid + REV-20260521-0002 2차 Critical 3 + Major 11 + Minor 2 — F8 만 사용자 명시 거부). D1~D21 21 결정 lock-in. 코드/스키마/RBAC catalog 변경 0 — 계획 문서 only. Sprint 1 (Cycle 0 Foundation + Cycle 1 CSV ingest) implementation 진입 가능. D14 SQL allowlist guard 통과를 Sprint 1 ship 조건.

### Git 동기화 결과 (TASK-0094)
- 커밋: 90df7c4 (ai/claude/0087/attachment-briefing → issue/39-task-0094-attachment-briefing) + follow-up b8dcbfc (issue/43-task-0094-cleanup, REPORT 사후 기록 — 본 entry)
- verify-completion: PASS (10/10 checks, 재시도 1회 — CHECK#3/#8/#9 FAIL 후 MODIFY/REVIEW append + .gitignore 갱신으로 PASS)
- Push: 완료 (issue/39 + issue/43 → origin)
- PR: #40 (closes #39, MERGED 2026-05-21T02:15:30Z) + #44 (closes #43, REPORT 사후 기록 follow-up)
- 병합 상태: PR #40 main 통합 완료. PR #44 conflict resolve 후 main 통합 진행 중.
- 충돌 해결: PR #44 의 REPORT.md / MODIFY.md / REVIEW.md / TASK.md 가 origin/main 의 PR #42 (TASK-0090) merge 후 발생한 conflict — main 의 변경과 본 follow-up 의 변경 모두 보존하여 resolve.
- 다음 단계: Sprint 1 implementation 진입 — 별 worktree `ai/claude/0094/sprint-1-foundation-csv` (또는 호환 `ai/claude/0087/sprint-1-...`). 본 worktree 는 §15 R-F10 cleanup 조건 따라 merge 직후 cleanup 권장.

---

**2026-05-20 TASK-0089 완료 (Phase A~G 일괄) — 작업 화면 profile drawer "내 감사 로그" 탭 신설** (CHG-20260520-0009, REV-20260520-0009, REQ-20260520-0004, **Minor** §12.3 — 신규 backend endpoint 2 + frontend 3 + Codex outside voice 5 findings 흡수 v2 redesign).

**본 cycle Phase 별 변경 요약**:
- **Phase A** — backend 2 endpoint (`/api/profile/audits` + `/api/profile/audits/{event_id}`) 신설. 기존 audit helper 재사용 + `scope="own"` 강제 (Codex C2).
- **Phase B** — index.html drawer-tab + drawer-pane (filter row mini + 1-column list + pagination + inline detail). cache-bust `v=20260520-profile-audit`.
- **Phase C** — app.js: state.profileAudit + helper 6 + loader + renderer 2 + handlers + tab visibility + tab click branch + renderProfile wire.
- **Phase D** — styles.css `.profile-audit-*` ~15 클래스 (drawer 폭 적응 + ChangeJson 수평 스크롤).
- **Phase E** — py_compile + node --check PASS + routing smoke (신규 endpoint 2 등록 확인).
- **Phase F** — docs 6 + FUNCTION AC-0194.
- **Phase G** — verify-completion + commit + cycle-finalize.

**Codex outside voice 5 findings 흡수**:
- C1 URL mismatch → `/api/profile/audits` 신설
- C2 `.any > .own` → backend `scope="own"` 강제
- C3 CSV export drawer 위험 → 미노출
- C4 drawer 폭 → 1-column + inline detail + `<pre>` 수평 스크롤
- C5 권한 race → tab visibility + 403 graceful

### Git 동기화 결과 (§16.3 Step 6)

PR description body 명시 — REPORT.md 갱신 별 commit 회피 (cycle-finalize 패턴).

### 후속 단계 (별 cycle)

- drawer 에서 자기 audit CSV export (`/api/profile/audits/export.csv` + scope="own", Minor)
- TASK-0073 backlog 1 entry 남음 (TASK-0087, 외부 LAN trust feature-0006 위임)
- SECURITY.md §8 strict-string-equality (TASK-0092 followup)
- `_migrate_web_account_activity_to_audit()` 제거 (TASK-0086 followup)
- 동시 export 제한 + EXPLAIN 분석 (TASK-0090 followup)

---

## 1.archived TASK-0090 Summary (2026-05-20)

**2026-05-20 TASK-0090 완료 (Phase A~D 일괄) — `/api/admin/audits/export.csv` CSV streaming export 전환** (CHG-20260520-0008, REV-20260520-0008, REQ-20260520-0005, **Minor** §12.3 — hard cap 50k 제거 + StreamingResponse + keyset cursor + max_id high-water + self-audit, Codex outside voice 5 findings 흡수 v2 redesign).

**본 cycle Phase 별 변경 요약**:
- **Phase A** — `export_audit_events_csv` endpoint 전면 재작성. 2-phase 구조 (auth conn + max_id capture + start audit → sync generator with streaming-only conn + chunked SELECT + byte-threshold flush + try/finally + complete audit). 신규 helper `_audit_export_filter_hash()`, const `_AUDIT_EXPORT_CHUNK_SIZE=500` / `_AUDIT_EXPORT_FLUSH_BYTES=65536`. `StreamingResponse` import.
- **Phase B** — py_compile + lightweight smoke 모두 PASS.
- **Phase C** — docs 6 갱신.
- **Phase D** — verify-completion + commit + cycle-finalize.

**Codex outside voice 5 findings 흡수**:
- C1 async + sync mysql blocking → sync generator + streaming-only conn
- C2 consistent snapshot → max_id high-water mark
- C3 query plan EXPLAIN → future cycle
- C4 cap 제거 = DoS → SECURITY 갱신 + export self-audit
- C5 cleanup → generator 내부 try/finally

**Self-audit ActionCode 신설**: `audit.export.start` / `audit.export.complete` / `audit.export.aborted`.

### Git 동기화 결과 (§16.3 Step 6)

PR description body 명시 — REPORT.md 갱신 별 commit 회피 (cycle-finalize 패턴).

### 후속 단계 (별 cycle)

- 동시 export 제한 (multi-worker semaphore 정합 검토 + advisory lock, Minor)
- representative filters EXPLAIN FORMAT=JSON 분석 (Minor, live mysql)
- TASK-0073 backlog 2 entries 남음 (TASK-0087/0089)
- SECURITY.md §8 strict-string-equality 계약 (TASK-0092 followup)
- `_migrate_web_account_activity_to_audit()` 제거 (TASK-0086 followup)

---

## 1.archived TASK-0088 Summary (2026-05-20)

**2026-05-20 TASK-0088 완료 (Phase A~D 일괄) — `slow_query_log` 통합 ADR-0020 Decoupled 채택 (docs only)** (CHG-20260520-0007, REV-20260520-0007, REQ-20260520-0003, **Minor** §12.3 — ADR-0019 Codex C1 lock-in 의 final 결론, Codex outside voice 5 findings 흡수 v2 redesign).

**본 cycle Phase 별 변경 요약**:
- **Phase A** — `docs/DECISIONS.md` ADR-0020 신설. 4 section + Options 검토 + Recommended performance path + Security policy + Consequences. ADR-0019 의 "별 cycle 분리" 라인 cross-reference 추가.
- **Phase B** — `docs/SECURITY.md §9.9` ADR-0020 cross-reference + raw SQL = 민감 로그 정책 + PS digest-first 권유. + docs 5 갱신 (TASK §2.6 + MODIFY CHG-0007 + REVIEW REV-0007 + TEST §4 + 본 REPORT).
- **Phase C** — verify-completion + commit.
- **Phase D** — cycle-finalize (issue + push + PR + merge + cleanup).

**ADR-0020 핵심 결정**:
- **Option C — Decoupled 채택**: slow_query_log 와 WebAuditEvents 통합 안 함.
- **주 근거**: raw SQL text PII 차단 (PasswordHash/Token/API key/임시 비밀번호/raw LLM prompt literal).
- **Option A reject** (Sidecar ETL): semantic pollution + raw SQL PII + ChangeJson/table bloat + actor/target 의미 부재.
- **Option B reject** (별 endpoint): raw SQL exfiltration + mount/race + DoS + `audit.read.any` 권한 의미 오염 + MySQL `TABLE` log destination 우회.
- **운영 성능 관측 권유**: `performance_schema`/`sys` digest views (1차) + slow_query_log incident enable (2차).
- **외부 SaaS/multi-tenant trigger**: `performance-log.read` permission + redaction/sampling + threat model ADR 선행.

**Codex outside voice 5 findings 흡수**:
- C1 current state framing 정정 (not enabled, forward-looking)
- C2 raw SQL PII 차단 = 주 근거 (1순위)
- C3 Option A reject 재작성 (4 구체 사유)
- C4 Option B reject 재작성 (5 구체 사유)
- C5 performance_schema digest-first 권유 추가

### Git 동기화 결과 (§16.3 Step 6)

PR description body 명시 — REPORT.md 갱신 별 commit 회피 (cycle-finalize 패턴, TASK-0093/0092/0086/0091 답습).

### 후속 단계

- 외부 SaaS/multi-tenant 진입 시 별 cycle (Major §12.3) — 4 선행 조건 충족 후 (`performance-log.read` + redaction/sampling + retention + threat model ADR)
- `performance_schema` digest views 운영자 access policy (별 cycle 또는 SECURITY.md §9 갱신)
- TASK-0073 backlog 3 entries 남음 (TASK-0087/0089/0090) — 각 별 cycle

---

## 1.archived TASK-0091 Summary (2026-05-20)

**2026-05-20 TASK-0091 완료 (Phase A~F 일괄) — PATCH admin/products audit before-state full snapshot + audit integrity fix** (CHG-20260520-0006, REV-20260520-0006, REQ-20260520-0006, ~~Minor~~→**Major** §12.3 — Codex outside voice 5 findings 흡수, audit integrity 결함 fix 포함 scope 확장).

**본 cycle Phase 별 변경 요약**:
- **Phase A** — 신규 helper `_audit_product_snapshot(conn, product_id)` (~line 2127): single-row WebProducts snapshot + `SELECT ... FOR UPDATE` + `system_prompt_summary` (SECURITY §9.2 정합, content 본문 제외).
- **Phase B** — `admin_update_product()` 명시 transaction (autocommit=False + before snapshot + UPDATE + default_cleared_product_ids + after snapshot + audit + commit + finally autocommit=True). Codex C2 audit integrity fix.
- **Phase B-2** — `_AUDIT_BUILDER_PRODUCT_FIELDS` 7→8 field 확장 (+is_default/+sort_order/+system_prompt_summary, -databases/-system_prompt). builder branch `default_cleared_product_ids` 명시 처리.
- **Phase C** — py_compile PASS + sentinel smoke PASS (SENTINEL drop / databases drop / sort_order delta / is_default delta / default_cleared_product_ids / system_prompt_summary).
- **Phase D** — docs 6 갱신: TASK §2.5 / MODIFY CHG-0006 / REVIEW REV-0006 / 본 REPORT / TEST §4 / FUNCTION AC-0192.
- **Phase E** — verify-completion PASS + commit.
- **Phase F** — cycle-finalize (issue + push + PR + merge + main worktree pull + 본 worktree cleanup).

**Codex outside voice 5 findings 흡수**:
- C1 system_prompt full content → summary only (SECURITY §9.2)
- C2 autocommit/transaction → 명시 transaction + SELECT FOR UPDATE
- C3 list scan → single-row helper + databases 제외
- C4 allowlist 누락 → +is_default/+sort_order + default_cleared_product_ids
- C5 rollback → C1 ACCEPT 로 자동 해소

**핵심 발견 (Codex C2)**: 본 cycle 의 Minor 등급 추정이 **audit integrity 결함** 노출 — `admin_update_product()` 가 autocommit=True default 라 UPDATE 가 즉시 commit, audit fail 시 rollback 가능 0 인 상태. scope ~~Minor~~→Major 확장하여 일괄 fix.

**Sentinel smoke 결과** (Phase C):
- `'TASK-0091-SENTINEL' in body: False` ✓ (system_prompt full drop)
- `'should_not_leak' in body: False` ✓ (databases drop)
- sort_order 100→50, is_default False→True, default_cleared_product_ids [5,9] ✓
- system_prompt_summary: {present: True, content_len: 1234/2000, updated_at}

### Git 동기화 결과 (§16.3 Step 6)

PR description body 명시 — REPORT.md 갱신 별 commit 회피 (§16.3 Step 7 권장, TASK-0093/0092/0086 cycle 답습).

### 후속 단계

- admin.product.create / delete 의 audit 도 allowlist 확장 결과 자동 정합 — 별 sentinel test 권유 (Minor)
- admin.product.databases.update audit 의 system_prompt summary 패턴 도입 검토 (별 cycle)
- SECURITY.md §8 strict-string-equality 계약 명시 (TASK-0092 followup)
- rollback window (1~2 cycle) 종료 후 _migrate_web_account_activity_to_audit() 제거 (TASK-0086 followup)
- TASK-0073 backlog 4 entries 남음 (TASK-0087/0088/0089/0090) — 각 별 cycle

---

## 1.archived TASK-0086 Summary (2026-05-20)

**2026-05-20 TASK-0086 완료 (Phase A0~J 일괄) — `WebAccountActivity` legacy table DROP + dual write 종료** (CHG-20260520-0005, REV-20260520-0005, REQ-20260520-0001, **Major** §12.3 — 파괴적 DROP + dual write 단일화 + Codex outside voice 5 findings 흡수 v2 redesign).

**본 cycle Phase 별 변경 요약**:
- **Phase A** (backup + 검증): mysqldump 8 옵션 (Codex C4) + scratch restore rehearsal + 1:1 정합 (74=74). backup file `artifacts/mysql-backup/WebAccountActivity-20260520T074927Z.sql` (11,950 bytes, digest `a09e7898d1ce88711f7a850ab5fbcc91`).
- **Phase B** (사용자 명시 ack): DROP 진행 ack 받음.
- **Phase C** (코드 변경 3): `_log_search_activity()` legacy INSERT 제거 + `_ensure_web_account_activity_schema()` 호출×2+정의 제거 + `_migrate_web_account_activity_to_audit()` rollback window 보존 + docstring 갱신. py_compile PASS.
- **Phase D+E** (lightweight smoke): host-mounted code + docker run import → `IMPORTED OK` + 함수 정의 부재/존재 정합 확인.
- **Phase F** (DROP): `DROP TABLE IF EXISTS WebAccountActivity` 실행 → `DROP completed`.
- **Phase G** (verify): `tables_remaining=0` + mirror 74 row 변동 없음.
- **Phase H** (docs 5 + tests 1 갱신): 본 REPORT.md + TASK §2.4 + MODIFY CHG-20260520-0005 + REVIEW REV-20260520-0005 + TEST §4 prepend + SECURITY §9.8 + test_audit_migration.py M3 제거.
- **Phase I** (verify-completion + commit): 본 단계 진행.
- **Phase J** (cycle-finalize): issue + push + PR + merge + main worktree pull + 본 worktree cleanup.

**Codex outside voice 5 findings 흡수**:
- **C1** Option A 불가능 → helper Option B (호출+정의 명시 제거, migration helper 만 rollback window 보존)
- **C2** dispatcher-only = mirror failure 가 audit 누락 → lightweight smoke + tests M3 제거
- **C3** "single tx DROP" 표현 → "single statement" 정정 (MySQL DDL implicit commit)
- **C4** Backup 검증 강화 → mysqldump 8 옵션 + scratch restore + canonical digest
- **C5** Rollback 2 시나리오 분리 (DB restore only / code revert + DB restore)

**핵심 baseline (Phase A 검증)**:
- WebAccountActivity legacy = **74 rows** (id 1~74, MatchedCount sum=502)
- WebAuditEvents `conversation.search.body` mirror = **74 rows** (1:1 정합)
- 초기 흡수 (RequestId='account-activity:%') = 68 row (TASK-0073 Phase A2 의 1회 호출)
- dual write 추가 (RequestId=NULL + ChangeJson._legacy_source) = 6 row

### Git 동기화 결과 (§16.3 Step 6)

PR description body 에 명시 — REPORT.md 갱신 별 commit 회피 (§16.3 Step 7 권장, TASK-0093/0092 cycle 답습).

### Rollback runbook (2 시나리오, Codex C5)

- **시나리오 1 — DB restore only**: 코드는 그대로, backup SQL 로 table 복구. `_migrate_web_account_activity_to_audit()` 의 SHOW TABLES check 가 다시 true → 재 migration 시 idempotent skip (기존 marker). 단 새 search 는 dispatcher only 라 table 이 다시 비어감.
- **시나리오 2 — code revert + DB restore** (완전 rollback): `git revert <CHG-20260520-0005>` + `docker compose restart web` + DB restore. dual write 부활 + 새 search 가 양쪽에 들어감.

### 후속 단계

- **rollback window 종료 후** (1~2 cycle): `_migrate_web_account_activity_to_audit()` helper 자체 제거 별 cycle (Minor §12.3).
- function rename `_log_search_activity()` → `_audit_conversation_search()` 별 cycle (Minor §12.3, caller 안정성 검토 후).
- SECURITY.md §8 strict-string-equality 계약 명시 (TASK-0092 followup, V6 결과 기반).
- TASK-0073 backlog 5 entries 남음 (TASK-0087, 0088, 0089, 0090, 0091) — 각 별 cycle.

---

## 1.archived TASK-0092 Summary (2026-05-20)

**2026-05-20 TASK-0092 완료 (Phase A0~E 일괄) — `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` startup fail-closed 7 vector matrix 검증 (TASK-0073 Phase E 위임 1 건 해소)** (CHG-20260520-0004, REV-20260520-0004, REQ-20260520-0007, **Minor** §12.3 — live container spawn + Codex outside voice 5 findings 흡수 v2 redesign).

**본 cycle Phase 별 변경 요약**:
- **Phase A0** (`.env` + image 가용성 확인): `repo-web:latest` image 가용 (435MB, 이미 build). `.env` 부재 — inline `-e` 만 사용 (compose 우회).
- **Phase A** (7 vector live spawn): `docker run --rm --entrypoint python repo-web:latest -c "import web.app"` 형태 단발 spawn. 7 vector 명세된 환경변수 조합으로 호출.
- **Phase B** (검증, **7 vector PASS (7/7)**):
  - V1 (`AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod`) → rc=1 + 3 substring + Traceback 부재 ✓
  - V2 (audit=0 + mode=unset) → rc=1 + `AGENT_MODE=(unset → prod)` 정합 ✓
  - V3 (audit=0 + mode=staging) → rc=1 + `AGENT_MODE=staging` 정합 ✓
  - V4 (audit=0 + mode=dev) → rc=0 + `IMPORTED OK` ✓ dev/test bypass
  - V5 (audit=1 + mode=prod) → rc=0 + `IMPORTED OK` ✓ positive control
  - V6 (audit=true + mode=prod) → rc=1 + `[FATAL]` ✓ Codex C3 strict-string-equality 계약
  - V7 (모두 unset) → rc=0 + `IMPORTED OK` ✓ default `1` + default prod
- **Phase C** (docs 5 갱신): 본 REPORT.md + TASK.md §2.3 + MODIFY.md CHG-20260520-0004 + REVIEW.md REV-20260520-0004 + TEST.md **§4** append.
- **Phase D** (verify-completion + commit): `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` PASS 후 사용자 명시 confirm 후 commit.
- **Phase E** (cycle-finalize 패턴): issue + push + PR + merge + main worktree pull + 본 worktree cleanup.

**Outside voice 흡수 5 findings 결정**:
- C1 테스트 명령 오류 → `--entrypoint python` + `import web.app` 정정
- C2 compose 오염 → `docker run` 직접 호출 (compose 우회)
- C3 flag parsing 계약 → V6 추가 (`"true"` fail-closed 검증)
- C4 stderr 검증 → 3 substring + Traceback 부재
- C5 docs §3 → §4 정정 (Test Run History)

**핵심 발견 (V6)**: `AGENT_AUDIT_ENABLED="true"` 는 fail-closed 됨 — strict string equality (`os.getenv(...).strip() == "1"`). 운영자가 truthy 표현 (`"true"`/`"yes"`/`"01"`) 명시 시 prod 시작 차단. SECURITY.md §8 의 strict-string-equality 계약 명시 별 cycle 후속 권고.

### Git 동기화 결과 (§16.3 Step 6)

PR description body 에 명시 — REPORT.md 갱신 별 commit 회피 (§16.3 Step 7 권장 패턴, TASK-0093 cycle 답습).

### 후속 단계

- **SECURITY.md §8 strict-string-equality 계약 명시** 별 cycle (Minor §12.3) — V6 결과 기반.
- TASK-0073 backlog 6 entries 남음 (TASK-0086, 0087, 0088, 0089, 0090, 0091) — 각 별 cycle.
- 본 cycle 종료 후 worktree archive — 다음 task 진입 시 별 worktree (`ai/claude/00XX/<slice>`) 권장.

---

## 1.archived TASK-0093 Summary (2026-05-20)

**2026-05-20 TASK-0093 완료 (Phase A~F 일괄) — verify-completion check_12 audit endpoint routing 정적 검사 신설** (CHG-20260520-0003, REV-20260520-0003, REQ-20260520-0008, **Minor** §12.3 — TASK-0073 Phase E hotfix CHG-20260520-0001 의 routing 회귀 fragility 보강. Codex outside voice 5 findings + 2 minimum-fix 흡수 후 v2 redesign 적용).

**본 cycle Phase 별 변경 요약**:
- **Phase A** (`bin/verify-completion.sh` 갱신): `check_12_audit_endpoint_routing()` + `_check_audit_routing_order()` pure helper split (line ~936-1010). `main()` 의 line 1123 에 호출 추가. footer 의 "9 checks" → "10 checks: 7 pilot + worktree binding + repo immutability + audit endpoint routing" (line 1126·1129). META mode footer 는 그대로 (check_12 는 feature-specific). `bash -n` syntax PASS.
- **Phase B** (production positive): production app.py 호출 → `CHECK#12 PASS audit endpoint routing order`. line 9522 max-static < line 9732 detail.
- **Phase C** (5 fixture negative test, production app.py 미수정):
  - `valid.py` (정합 ordering) → PASS
  - `wrong_order.py` (event_id BEFORE static siblings) → FAIL "ordering" + line number hint
  - `no_detail.py` (detail 부재) → FAIL "detail endpoint missing — possible route removal or refactor"
  - `no_siblings.py` (정적 GET sibling 부재) → FAIL "no static GET siblings — audit route layout changed"
  - `refactored.py` (APIRouter prefix) → FAIL "routes not found in expected form — manual review required"
- **Phase D** (5 other-feature SKIP + 1 missing-app structural FAIL): feature-0001/0002/0004/0005/0006 호출 → rc=0, no output. target feature + app.py 부재 → FAIL "expected app.py at <path> but file is missing".
- **Phase E** (docs 5 갱신): 본 REPORT.md + TASK.md §2.2 + MODIFY.md CHG-20260520-0003 + REVIEW.md REV-20260520-0003 + TEST.md.
- **Phase F** (최종 verify-completion + commit): `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` META mode PASS (check_12 자동 skip 정합) + 사용자 명시 commit confirm.

**Outside voice 흡수 5 findings 결정**:
- C1 SKIP→FAIL structural (회귀 방지 게이트 의도 정합)
- C2 grep 패턴 fragility (C1 통합, AST 파서 미도입 — Minor scope)
- C3 `/purge` method-aware mismatch → sibling list 자동 제외
- C4 Inline 4-path → auto-discovery (`@app.get("/api/admin/audits/<non-{>")` 패턴)
- C5 Production app.py 임시 이동 risk → temp fixture + helper split

**in-cycle fix (Phase C debug)**: `set -euo pipefail` + grep no-match (exit 1) 시 `|| true` fallback 처리. log_check 호출 보장.

**Git 동기화 결과** (§16.5 Step 6): `ai/claude/0086/audit-followup` worktree 의 단일 commit. 본 cycle 의 base 는 f41e4f8 (CHG-20260520-0002 backlog staging). 사용자 명시 confirm 후 commit + push 진행. 후속 cycle (TASK-0086~0092 7 entries) 은 별 cycle 별 별 PLAN-APPROVED.

---

## 1.archived TASK-0073 Summary (2026-05-19~20)

**2026-05-19 TASK-0073 진행 중 (Phase A1~D 완료, Phase E 컨테이너 검증 + 최종 commit) — 모든 계정 행위 audit subsystem 도입** (CHG-20260519-0017~0024, REV-20260519-0013~0020, REQ-20260519-0001, **Critical** §12.3 — 인증·인가 + PII 수집 + RBAC 4 신규 + Tx split + dispatcher SPOF + Codex outside voice 14 findings + Eng review E1-E9 lock-in).

**Phase 별 변경 요약**:
- **Phase A1** (CHG-0017): `record_audit_event()` dispatcher + `AGENT_AUDIT_ENABLED` prod startup fail-closed gate (Codex C5) + `bin/verify-completion.sh check_11_audit_dispatcher` SPOF guard (Eng E7).
- **Phase A2** (CHG-0018): WebAccountActivity 흡수 + `_migrate_web_account_activity_to_audit(conn)` helper (idempotent SQL marker `RequestId='account-activity:<id>'`) + `_log_search_activity` signature transparent dual write wrap (Codex C2).
- **Phase A3** (CHG-0019): `PERMISSION_DEFINITIONS` +4 (`audit.read.own/.any/.export/.purge`) + permission group `audit` + admin/operator/sales/dba/pending 5 role catchup loop (Eng E9, Codex C8/C9/C10).
- **Phase A4** (CHG-0020): 5 audit read endpoint (`/api/admin/audits` + detail + export.csv + actors facet + resources facet) + chunked PK purge `POST /api/admin/audits/purge` (Eng E1 Actor OR Target self filter + E8 의사코드 + 30s deadline + idempotency_key).
- **Phase A5** (CHG-0021): admin 11 mutation endpoint Same tx audit hook + 16 ActionCode `build_audit_change_json` builder (Codex C6 allowlist) + `_audit_admin_mutation` helper.
- **Phase A6** (CHG-0022): user 5 endpoint fail-open audit + `_audit_user_action` helper. `/api/ask`, share create / revoke / public view (ActorType='anonymous', Eng E4) / fork.
- **Phase B** (CHG-0023): 3 test 파일. 실 실행은 Phase E 컨테이너 가동 후 사용자 위임.
- **Phase C** (CHG-0024): Frontend admin "감사 로그" 탭 + filter + list-detail + CSV export gated + PERMISSION_GROUP_ORDER 'audit'.
- **Phase D** (이번 commit): `docs/SECURITY.md §9` + `docs/DECISIONS.md ADR-0019` + `docs/ARCHITECTURE.md §4·§6` + `docs/CONVENTIONS.md §10.6` + `docs/STATUS.md` + 본 REPORT.md / TEST.md.

**Git 동기화 결과** (§16.5 Step 6):
- 커밋: 8 phase commits (`bf21886` A1 / `88d6fa4` A2 / `2e45cb4` A3 / `e21ab15` A4 / `4ed5f0d` A5 / `5f42ba6` A6 / `c801104` B / `2ddf9b5` C / Phase D 진행 중).
- worktree: `ai/claude/0073/agent-audit` (`.worktrees/0073-agent-audit/`, §13.2 manual parallel AI worktree).
- verify-completion: 모든 phase PASS (9 checks: 7 pilot + worktree binding + audit dispatcher).
- Push: 보류 (sandbox SSH 인증 차단 — 본 session 종료 후 사용자가 직접 push).
- PR: 미생성 (사용자 결정).
- 충돌 해결: 없음.

**남은 위험 / 후속**:
- Phase E HTTP smoke 실 실행 (admin/operator 자격 + 컨테이너 가동 후 사용자 검증).
- WebAccountActivity 별 cycle DROP (data backup + dual write 검증 후).
- `_get_client_ip` 외부 LAN trust 강화 (feature-0006-lan-proxy-access 후속).
- 작업 화면 audit 자기 view drawer (별 cycle UX).

상세 진행: `docs/MODIFY.md` CHG-20260519-0017~0024 + `docs/REVIEW.md` REV-20260519-0013~0020.

---

(이전 cycle Summary — TASK-0085 lazy-create 사이드바 optimistic pending entry, CHG-0016 / REV-0012)

**2026-05-19 TASK-0085 완료 — lazy-create 사이드바 optimistic pending entry (송신 직후 다른 대화 전환 시 새 대화 entry 잠시 소실 UX 회귀 fix + 클릭 swap 으로 작업 step 현황 출력 지원)** (CHG-20260519-0016, REV-20260519-0012, REQ-20260519-0014, Minor §12.3 — frontend state machine + rendering refactor 5 영역, backend / RBAC / endpoint / audit / DB 무변경).

**배경**: 사용자 직접 요청 — "+ 새 대화 에서 요청을 보내면, 해당 대화가 사용자 입장에서(웹브라우저에서) 즉시 활성화된 대화 객체로 받아들이도록 구성" + "현재는 + 새 대화 에서 요청 후 다른 대화로 전환할 때, 이전에 요청한 신규 대화가 잠시동안 목록에서 사라지는 이슈" + click UX 결정 "대화 내부 진입도 가능하도록 구성해주세요. 작업 step 현황의 출력을 위해서입니다".

**원인**: TASK-0048 의 lazy-create 패턴이 backend conversation row 등재를 `/api/ask` 응답 시점까지 지연. frontend 의 `state.conversations` (사이드바 list) 는 응답 도착 시 `refreshWorkspace` 가 backend `/api/conversations` 결과로 통째 replace — 그 사이 (응답 도착 전) 사용자가 다른 대화로 전환하면 `selectConversation` 이 `state.pendingNewConversation=false` set + `appendPendingItem` 작성 중 placeholder 도 사라짐. 결과: 새 대화 entry 가 사이드바에서 완전 소실 → 응답 도착 후 refreshWorkspace 시점에야 다시 표시.

**Fix design (multi-pending optimistic list entry)**:
- `state.pendingConversationEntries: Map<sentinel, { sentinel, message, started_at, status }>` 신설. multi-pending 지원 — TASK-0082 unique sentinel design 정합.
- `sendPrompt()` lazy-create 진입 시점에 entry add + `renderConversationList()` 호출 — 사이드바 즉시 표시.
- success path: closure 일치 여부와 무관하게 본 send 의 sentinel entry 만 delete (실 cid entry 는 `refreshWorkspace` 가 등재).
- catch path: status="failed" set + 3 s 후 자동 delete. 사용자에게 toast + 사이드바 양방향 안내.
- `renderConversationList()` 의 `hasPending` split: `hasDraftPending` + `hasInFlightPending`. combined prepend 로 둘 다 own 그룹에 표시.
- 신규 `appendInFlightPendingItems()` + `_switchToPendingConversationContext(entry)` helper.

**회귀 시나리오 5 종 검증** (코드 trace 기반):
- ①+ 새 대화 송신 직후 다른 대화 클릭 → state.pendingConversationEntries 에 entry 보존, 사이드바에 in-flight 표시 지속.
- ②응답 도착 → success path 가 본 sentinel entry delete + refreshWorkspace 가 실 cid entry 등재. optimistic → 실 entry 자연 swap.
- ③catch (네트워크 timeout 등) → "전송 실패" 표시 3 s 후 cleanup. 입력란 활성화로 사용자 즉시 재시도 가능.
- ④pending entry 클릭 → `_switchToPendingConversationContext` 가 sentinel 컨텍스트로 swap. pendingBubble 복원으로 elapsed timer 이어짐. 응답 도착 시 closure 일치 → 자동 cid binding + polling 시작.
- ⑤multi-pending 동시 진행 → 각 sentinel 별 분리 보존.

**검증**: `node --check app.js` PASS. backend / RBAC / endpoint / audit / DB 무변경. cache-bust `v=20260519-unique-sentinel` → `v=20260519-pending-entries`.

**Worktree 격리**: 본 작업은 다른 AI 작업자의 main 영역 변경과 격리하기 위해 worktree `ai/claude/0083/pending-list-entry` 에서 진행 후 main 으로 fast-forward merge.

**Trace**: REQ-20260519-0014 → TASK-0085 → CHG-20260519-0016 → REV-20260519-0012. TASK-0048 lazy-create + TASK-0082 unique sentinel design 의 자연 연속.

---

**2026-05-19 TASK-0082 완료 — lazy-create unique sentinel design (첫 in-flight 중 + 새 대화 클릭 시 input 비활성 회귀 근본 fix, TASK-0081 followup)** (CHG-20260519-0012, REV-20260519-0008, REQ-20260519-0010, Minor §12.3 — frontend state machine refactor 5 군데, backend / RBAC / endpoint / audit / DB 무변경).

**배경**: TASK-0081 fix 후 사용자 추가 보고 — "대화 요청을 보낸 후, + 새 대화 버튼을 클릭한 후에도 요청 텍스트 입력칸이 활성화되지 않는 이슈". TASK-0081 의 stale guard + catch cleanup 만으로는 첫 lazy-create in-flight 중 + 새 대화 클릭 시나리오를 cover 못 함.

**원인 (TASK-0081 보다 근본)**: `app.js` 의 글로벌 단일 sentinel (`PENDING_CONV_SENTINEL = "__pending__"`) 가 lazy-create busy tracking 의 토큰. 첫 send 가 in-flight 일 때 busyConversations 에 sentinel 점유 → 사용자가 + 새 대화 클릭해도 두 번째 컨텍스트의 `isCurrentConvBusy()` 가 same sentinel 검사로 true 반환 → `renderComposer()` 가 `promptInputEl.disabled = true` 유지 → input 활성화 안 됨. 추가로 TASK-0081 의 guard 분기는 in-flight 시 early return 으로 renderComposer 호출조차 skip — input.disabled state update 자체 안 됨. 두 결함 합쳐서 사용자 증상.

**Fix**: 각 lazy-create 진입마다 unique sentinel 부여하는 design.

- `state.pendingSentinel` field 추가 — 활성 lazy-create 의 unique sentinel 보관.
- `_newPendingSentinel()` helper — `${prefix}_${Date.now()}_${random 6 char}` 패턴, 16M 분리.
- `isCurrentConvBusy()` 의 sentinel 검사를 글로벌 단일 → `state.pendingSentinel` 점유 여부로 변경.
- `beginPendingConversation()` 의 TASK-0081 guard 제거 + `state.pendingSentinel = _newPendingSentinel()` 명시 부여. 항상 reset 흐름 진입.
- `sendPrompt()` 의 busyKey 를 `state.pendingSentinel` 으로 closure capture. success / catch path 의 cleanup 은 `if (state.pendingSentinel === busyKey)` 일치 검사 후에만 실행.

이 design 의 핵심: 첫 sendPrompt 의 closure 에 capture 된 옛 sentinel ("A") 은 본 함수의 finally 가 책임지고 cleanup. 사용자가 그 사이 + 새 대화 클릭으로 두 번째 컨텍스트 진입하면 `state.pendingSentinel` 은 새 sentinel ("B") 으로 갱신. 첫 send 의 success/catch path 는 closure key ("A") 와 `state.pendingSentinel` ("B") 의 불일치를 보고 두 번째 컨텍스트 state 보존. 두 번째 send 의 busyKey 는 "B" — 본 send 의 finally 가 "B" 만 cleanup.

**회귀 시나리오 4 종 검증** (코드 trace 기반):
- ①첫 송신 in-flight 중 + 새 대화 클릭 → state.pendingSentinel 이 "A" → "B" 로 swap. renderComposer 의 isCurrentConvBusy 가 busyConversations.has("B") = false → busy=false → **input 활성화** ✓. 사용자 두 번째 prompt 작성 + send → busyKey="B" → in-flight. 첫 응답 도착 시 closure mismatch 로 두 번째 컨텍스트 보존. 두 번째 응답 도착 시 closure 일치로 normal cleanup. 사이드바에 양쪽 conv 표시.
- ②catch 분기 종료 후 + 새 대화 → catch 에서 closure 일치 cleanup (state.pendingSentinel = null). 이후 + 새 대화 클릭 시 새 sentinel 부여. 정상 진행.
- ③응답 후 + 새 대화 (정상 흐름) → success path 의 closure 일치 cleanup. 이후 + 새 대화 시 새 sentinel.
- ④pending bubble error 표시 → closure mismatch 시 cleanup skip 하지만 bubble UI 는 별도 (state.pendingBubble). AC-0077 유지.

**TASK-0081 와의 관계**: TASK-0081 의 stale guard (`pendingNewConversation && busyConversations.has(sentinel)`) 와 catch cleanup 정책은 본 design 으로 자연 흡수. 각 진입이 새 sentinel 으로 reset 하므로 stale state 자체가 컨텍스트 분리로 해소. catch cleanup 도 closure-aware 로 유지하되 closure mismatch 시 skip 으로 두 번째 컨텍스트 보호.

**검증**: `node --check app.js` PASS. backend / RBAC / endpoint / audit / DB 무변경 (py_compile 대상 없음). cache-bust `v=20260519-pending-recovery` → `v=20260519-unique-sentinel` (index.html). smoke 시나리오 4 종은 사용자 환경 직접 확인 권장.

**Trace**: REQ-20260519-0010 → TASK-0082 → CHG-20260519-0012 → REV-20260519-0008.

---

**2026-05-19 TASK-0081 완료 — beginPendingConversation stale flag 회복 가드 + sendPrompt catch 분기 pendingNewConversation cleanup (두 번째 새 대화 send 차단 회귀 fix)** (CHG-20260519-0011, REV-20260519-0007, REQ-20260519-0009, Minor §12.3 — frontend state machine 2 군데 변경, backend / RBAC / endpoint / audit / DB 무변경).

**배경**: 사용자 직접 보고 — "새 대화에서 요청을 보낸 후, 다시 새 대화로 별개의 요청을 보내려고 했을 때 진행되지 않는 이슈". 증상 추가 확인: "두 번째 send 를 진행하는 상호작용 (요청 UI 버튼, Ctrl+Enter) 가 막혀있다".

**원인**: `app.js` 의 lazy-create state machine 2 군데 결함. (1) `beginPendingConversation()` (line 2988~3012) 의 early-return guard 가 `state.pendingNewConversation === true` 단독 검사로 stale state 와 정당한 in-flight 점유를 구분 못 함. 첫 lazy-create 가 network/timeout 으로 catch 분기에 진입한 경우 `state.pendingNewConversation` flag 가 cleanup 되지 않은 채 남음 → 사용자가 "+ 새 대화" 다시 클릭 → 가드가 stale flag 만 보고 입력란 포커스만 잡고 return → `state.activeConversationId = ""` reset 도 실행 안 됨. (2) `sendPrompt()` 의 lazy-create catch 분기 (line 3533~3551) 가 `state.pendingBubble` 의 error 영역만 처리하고 `state.pendingNewConversation` 자체는 cleanup 안 함. 결과: 두 번째 새 대화로 send 시도 시 (a) 진입조차 차단되거나 (b) 진입했어도 `sendPrompt()` 의 line 3437 `isCurrentConvBusy()` 가 `pendingNewConversation=true && busyConversations.has(sentinel)` 검사에서 막힘.

**Fix**:
- (a) `beginPendingConversation()` early-return 조건을 `state.pendingNewConversation && state.busyConversations.has(PENDING_CONV_SENTINEL)` 로 좁힘 — 첫 lazy-create 가 실제 in-flight (sentinel 점유) 일 때만 진입 보류. stale state 면 통과해 정상 reset 흐름 진입.
- (b) `sendPrompt()` lazy-create catch 분기 진입 시점에 `state.pendingNewConversation = false` 1 줄 명시 cleanup. pending bubble error 표시 / toast 안내 로직은 무변경. busyConversations sentinel cleanup 은 finally 의 기존 `state.busyConversations.delete(busyKey)` 가 담당.

**회귀 시나리오 5 종 검증** (코드 trace 기반):
- ①정상 첫 송신 후 두 번째 새 대화 진입 + send → 통과. (success path 의 line 3524 `pendingNewConversation = false` + finally sentinel delete 후 sentinel 부재 → guard 가 false → 정상 reset 진입).
- ②첫 송신 timeout 에러 후 두 번째 새 대화 → catch 의 신규 `pendingNewConversation = false` cleanup + sentinel delete (finally) → 두 번째 클릭 시 guard 통과 → 정상 진입.
- ③첫 송신 in-flight 중 사용자가 "+ 새 대화" 클릭 → guard 가 sentinel 점유 검사로 진입 보류 (의도된 동작 — sentinel 중복 race 방지).
- ④AC-0077 pending bubble error 표시: `state.pendingBubble` 별도 state 라 cleanup 과 무관 — 빨간 오류 영역 + toast 안내 그대로 노출.
- ⑤AC-0072~0077 lazy-create 정상 success 흐름 무영향: line 3522~3528 의 success path 변경 없음, polling 시작도 그대로.

**검증**: `node --check app.js` PASS. backend / RBAC / endpoint / audit / DB 무변경 (py_compile 대상 변경 없음). cache-bust `v=20260519-chat-pane-flex` → `v=20260519-pending-recovery` (index.html). smoke 시나리오 5 종은 사용자 환경 직접 확인 권장.

**Trace**: REQ-20260519-0009 → TASK-0081 → CHG-20260519-0011 → REV-20260519-0007.

---

**2026-05-18 TASK-0071 완료 — shell grid row hotfix (cascade root of TASK-0068~0070 layout chain)** (CHG-20260518-0008, REV-20260518-0008, REQ-20260518-0009, Minor §12.3 — CSS 2 줄 hotfix, RBAC / endpoint / 데이터 / JS 무변경).

**배경**: 사용자 3 차 screenshot 보고. TASK-0070 의 list-detail row fix 이후에도 dashboard pane 처럼 list-detail 을 사용하지 않는 화면에서 큰 viewport (height 800+) + 짧은 content 조합 시 sidebar / commit-bar 가 viewport 의 약 70% 위치까지만 차지하고 그 아래 회색 빈 영역이 viewport bottom 까지 노출.

**원인**: `.app-shell` / `.admin-shell` 의 `display: grid; height: 100vh` 만 정의하고 `grid-template-rows` 미정의 → default `auto` → single row track height = 자식 max-content. grid container 100vh 와 track height 의 mismatch 시 track 아래 빈 영역. 이전 cycle 들의 fix 는 column 안의 stretch chain 만 해결 — column 의 height 결정 layer (grid track) 는 미처리. cascade 의 root.

**환경 차이**: 본 환경 (chrome headless) 에서는 grid track 이 100vh 차지 동작이라 TASK-0069 부터 정상 보였음. 사용자 환경에서는 max-content 동작이라 노출. browser engine / DPI / timing 등 환경별 grid algorithm 차이가 회귀 timing 결정.

**Fix**: `.app-shell` 과 `.admin-shell` 양쪽에 `grid-template-rows: minmax(0, 1fr)` 추가 (2 줄, 동일 패턴 일관성). `minmax(0, 1fr)` 은 CSS Grid spec 의 명시적 단일 row stretch 패턴 — 환경 의존성 제거.

**Layout cascade 완성**:
```
.app-shell / .admin-shell { height: 100vh; grid-template-rows: minmax(0, 1fr) }  ← TASK-0071 (cascade root)
  └ chat-column / admin-column  (grid item, row full height)
      └ .chat-pane / .admin-workspace  { flex: 1 1 auto }  ← TASK-0069
          └ .admin-pane.is-active  { flex: 1 1 auto }
              └ .admin-list-detail  { grid-template-rows: minmax(0, 1fr) }  ← TASK-0070
                  └ list-col / detail-col  (row stretch)
      └ commit-bar  (flex-shrink: 0, viewport bottom sticky)
```

**검증**: 1320x900 viewport 에서 admin-shell h=900 (viewport 와 일치), admin-column h=900, commit-bar bottom=900 (viewport bottom 정확히 sticky), gridTemplateRows="900px" (1fr 의 computed 값). Screenshot `/tmp/admin-dashboard-fixed.png` — sidebar (brand → 탭 → pending footer) 가 viewport 전체 height 차지 + admin-column (topbar → dashboard content + 자연 빈 영역 → commit-bar 가 viewport bottom). 회색 빈 영역 사라짐. 작업 화면 (`/`) 도 동일 fix 자연 적용. cache-bust `v=20260518-shell-grid-rows` (admin.html + index.html 양쪽).

본 cycle 이 TASK-0066 (ChatGPT 패턴 layout) 부터 시작된 layout 재구조화의 최종 stretch fix. cascade 완성 후 회귀 없이 안정.

---

**2026-05-18 TASK-0070 완료 — admin list-detail grid row hotfix (TASK-0069 잔여 회귀)** (CHG-20260518-0007, REV-20260518-0007, REQ-20260518-0008, Minor §12.3 — CSS 1 줄 hotfix, RBAC / endpoint / 데이터 / JS 무변경).

**배경**: 사용자 2 차 screenshot 보고. TASK-0069 의 `.admin-workspace { flex: 1 1 auto }` fix 이후에도 `역할` / `제품` 등 항목이 적은 pane 의 큰 viewport (height 800+) 에서 list-col / detail-col box 가 viewport 의 일부만 차지하고 그 아래 회색 빈 영역 잔존. 항목 많은 `계정` (26 row) 이나 좁은 화면에선 row content 가 자연 채워 노출 안 됨 — 1 차 검증 (720 viewport) 에서 놓침.

**원인**: `.admin-list-detail { display: grid; grid-template-columns: ...; align-items: stretch }` 의 `grid-template-rows` 미정의 → default `auto` → row height = content. `align-items: stretch` 는 row 내부 column 분배만 — row 자체 height 결정 X. flex grow chain (admin-column → workspace → pane → list-detail) 의 끝지점이라 fix 가 cascade 의 마지막 단계.

**Fix**: `.admin-list-detail` 에 `grid-template-rows: minmax(0, 1fr)` 1 줄 추가. `minmax(0, ...)` 으로 자식 min-content 무시 — 자식의 `min-height: 0` 와 정합. 다른 속성 무변경.

**검증**: 큰 viewport (1320x900) 에서 `제품` pane (3 items) — `listDetail h=682`, `listCol h=682`, `detailCol h=682` (이전엔 약 200 정도만), `cbar y=839 / bottom=900` (viewport bottom sticky). screenshot `/tmp/admin-products-fixed.png` — box 가 commit-bar 까지 stretch + 회색 빈 영역 사라짐. 다른 pane 도 동일 fix 자연 적용 (`.admin-list-detail` 공통 rule). cache-bust `v=20260518-admin-list-rows`.

검증 viewport 다양성 부족이 회귀 1 cycle 연장한 점 기록 (REV-20260518-0007). 후속 cycle 검증 시 720 / 900 / 1080 / mobile (480) 등 multiple viewport snapshot 으로 stretch chain 종단 확인 권장.

---

**2026-05-18 TASK-0069 완료 — admin workspace flex hotfix (TASK-0068 회귀 차단)** (CHG-20260518-0006, REV-20260518-0006, REQ-20260518-0007, Minor §12.3 — CSS 1 줄 hotfix, RBAC / endpoint / 데이터 / JS 무변경).

**배경**: 사용자 screenshot 보고. admin `역할 관리` (및 다른 list-detail pane) 에서 commit-bar 가 workspace content 바로 아래에 좁게 위치하고 그 아래로 큰 회색 빈 영역이 admin-column 의 bottom 까지 노출. 원인: TASK-0068 에서 commit-bar 를 admin-shell grid (3rd row) → admin-column flex column item 으로 이전한 후 `.admin-workspace` 의 `flex: 1` 명시 누락. flex column 안에서 workspace 가 자기 content 만큼만 차지 → 남은 공간 노출 + commit-bar 가 sticky bottom 효과 상실.

**Fix**: `.admin-workspace` 에 `flex: 1 1 auto` 1 줄 추가. 다른 속성 (overflow / padding / min-* 0 / display flex column) 무변경. `.admin-pane.is-active { flex: 1 1 auto }` 가 의미를 가지려면 부모 workspace 가 stretch 되어야 함 — cascade 출발점에 flex grow.

**검증**: `SKIP_INIT=1 make web` 재배포 OK. DOM (browser headless `/admin` → 역할 tab): `wsHeight=607, wsBottom=659, cbarTop=659, cbarBottom=720, colHeight=720` → `workspaceTouchesCommitBar=true` (둘 사이 빈 공간 없음) + `commitBarAtBottom=true` (commit-bar 가 column bottom 에 정확히 위치). screenshot `/tmp/admin-roles-fixed.png` — list-detail 이 workspace 의 남은 height 전부 차지 + commit-bar viewport bottom sticky + 회색 빈 영역 사라짐. cache-bust `v=20260518-admin-workspace-flex`.

후속 검토 (REV-20260518-0006 Risks): dashboard pane 의 scroll 동작 (overflow-y: auto) 정상 여부는 사용자 직접 확인 권장 — 단일 rule 변경이라 자연 적용되지만 dashboard 전용 시각 검증 별도.

---

**2026-05-18 TASK-0068 완료 — 관리 콘솔 layout 정합 (ChatGPT 패턴 통일) + 새로고침/로그아웃 버튼 제거** (CHG-20260518-0005, REV-20260518-0005, REQ-20260518-0006, Minor §12.3 — admin layout 정합 + 미사용 UI 정리. backend / endpoint / RBAC / 데이터 영역 무변경).

**배경**: TASK-0066 / 0067 follow-up — 사용자 명시. 작업 화면을 ChatGPT 패턴으로 재구조화한 후 관리 콘솔도 같은 layout 으로 통일. 사용자 직접 테스트에서 `새로고침` / `로그아웃` 버튼이 거의 사용 안 되는 것으로 확인 → 제거.

**변경**: (1) `.admin-shell` grid 가 `grid-template-rows: topbar-h | 1fr | auto` → `grid-template-columns: 220px minmax(0, 1fr)` 으로 단순화 (작업 화면 `.app-shell` 과 동일 패턴). `.admin-body` wrapper 폐기. (2) `.admin-sidebar` 의 첫 영역에 `.sidebar-brand` (작업 화면과 동일 brand "MA MySQL AI") 추가. 기존 admin brand "관리 콘솔" 은 페이지 컨텍스트라 topbar 의 `.chat-title` 로 이전 + subtitle "계정 · 역할 · 제품 · 시스템 프롬프트 운영" 동봉. (3) 신규 `.admin-column` (flex column) — sidebar 옆 영역. 안에 topbar (좌측 정렬 제목 + `#backToAppBtn` 우측) → workspace → commit-bar 순서로 flex 배치. (4) `#refreshAdminBtn` / `#adminLogoutBtn` element 제거 + admin.js click handler 제거. `#backToAppBtn` 만 유지. (5) `.admin-sidebar` padding 을 child 들 (sidebar-brand / admin-tabs / sidebar-foot) 로 분배. (6) 반응형 mobile `.admin-shell { grid-template-columns: 1fr }` 정렬.

**검증**: `node --check admin.js` PASS, `SKIP_INIT=1 make web` 재배포 OK. Browser headless `/admin`: `refreshBtnPresent=false`, `logoutBtnPresent=false`, `backBtnPresent=true`, `brandInSidebar=true`, `adminColumnPresent=true`, `oldAdminBodyPresent=false`, `topbarHeight=52`, `topbarInfoText="관리 콘솔 ... 시스템 프롬프트 운영"`, `gridCols="220px 1060px"`. Screenshot `/tmp/admin-merged.png` — 좌측 admin-sidebar (brand + 대시보드 (active) + 계정 카테고리 + 제품 카테고리 + pending 변경 footer) + 우측 admin-column (topbar 좌측 정렬 "관리 콘솔" + 부제 + 우측 끝 "작업 화면" 버튼 / Overview metric cards / commit bar) — 작업 화면과 100% 일관된 ChatGPT 패턴. cache-bust `v=20260518-admin-layout` (admin.html / admin.js).

후속 cycle 권장: 작업 화면 프로필 drawer 의 "로그아웃" 이 admin 페이지에서도 접근 가능한지 확인 (현재 admin 에는 drawer 없음 — 로그아웃 path 가 작업 화면 경유). dead CSS (`.topbar-brand`, `.product-chip-*`, `.admin-body`) 일괄 정리 별 cycle.

---

**2026-05-18 TASK-0067 완료 — 제품 칩 composer 이전 + custom drop-up dropdown (ChatGPT 모델 선택 패턴)** (CHG-20260518-0004, REV-20260518-0004, REQ-20260518-0005, Minor §12.3 — UI 위치 이전 + native select → custom dropdown, backend / endpoint / RBAC / 데이터 영역 무변경).

**배경**: TASK-0066 의 layout 통합 후 사이드바 영역도 확장하기 위한 사용자 follow-up. ChatGPT 의 모델 선택 UI 패턴 — chip 을 composer 영역 우측 (textarea / sendBtn 사이) 에 두고 click 시 drop-up dropdown 으로 옵션 표시.

**변경**: (1) `.sidebar-head` 의 `.product-chip-wrap` 제거 → sidebar-head 에는 `#newConversationBtn` 만 (sidebar vertical 공간 확장). (2) `.composer-box` 안에 `.composer-product-chip-wrap` 신설 — `button#productChip` (dot + compact label + arrow) + `div#productDropupMenu`. (3) 기존 native `<select id="productSelect">` 폐기 → custom button + custom menu (drop-up 보장). (4) JS: `renderProductChip` 재작성, 신규 `renderProductDropupMenu` / `buildProductDropupItem` / `openProductDropup` / `closeProductDropup`. chip click handler 가 dropdown toggle. `setActiveProduct` 본체 무변경 (backend `PATCH /api/conversations/{cid}/product` 호출 그대로).

**디자인 정책**: chip label = compact (`product_key` 만, chip width 보존) + aria-label = full (`{name} ({product_key})`). menu z=50, drop-up (`bottom: calc(100% + 6px)`), max-height 320px. busy 시 chip.disabled + aria-disabled (race 가드 보존).

**검증**: `node --check` PASS, `SKIP_INIT=1 make web` 재배포 OK. Browser headless: `chipInComposer=true` (chip 이 composer-box 안), 기존 native select 부재, sidebar-head 가 "새 대화" 만, chip click → menu 4 items (auto + KR + MV + GZ_KR) 정상 + `dropUp=true` (menuY=459 < chipY=644), KR item click → chip label "KR" + chip mode=pinned + toast "제품을 킹스레이드로 바꿨어요. 다음 답변부터 적용됩니다." 정상. backend endpoint 호출 정상. cache-bust `v=20260518-product-composer`.

후속 cycle 권장: dead CSS rule (`.product-chip-wrap` / `.product-chip*` / `.topbar-brand`) 정리. arrow key keyboard navigation (REQ-20260518-0005 의 후속 가능).

---

**2026-05-18 TASK-0066 완료 — ChatGPT 패턴 layout 재구조화 (헤더 영역 통합)** (CHG-20260518-0003, REV-20260518-0003, REQ-20260518-0004, Minor §12.3 — UI layout, RBAC / endpoint / 데이터 / JS 시그니처 무변경).

**배경**: TASK-0065 follow-up. 헤더 4 버튼 제거로 `.chat-header` 가 거의 비어 있어 `.topbar` (관리 콘솔) 과 영역 통합이 자연스러움.

**사용자 결정** (in-cycle): topbar 에 대화 제목 통합 + 좌측 정렬 (중앙 정렬 금지) + brand `[MA] MySQL AI` 를 sidebar 영역으로 이전 (ChatGPT UI 명시). chat-pane 상단 chat-header 제거로 채팅 영역 확장.

**변경**: `.app-shell` grid 가 2-row (topbar | app-body) → 2-column (sidebar | chat-column) 로 단순화. `.app-body` wrapper 폐기. `.sidebar-brand` (height = topbar-h = 52px, border-bottom) 신설 — sidebar 의 첫 영역, topbar 와 baseline 정렬. `.chat-column` (flex column) 신설 — sidebar 옆 영역. topbar 가 chat-column 의 첫 child 로 이전 (대화 제목 좌측 정렬 + loadMoreBtn + 관리 콘솔 우측). `.chat-header` 폐기 — `.chat-title` / `.chat-subtitle` typography 만 보존. 반응형 mobile (max-width: 680px) 도 `.app-shell { grid-template-columns: 1fr }` 으로 변환.

**검증**: DOM `.app-shell.gridTemplateColumns = "252px 1028px"` / `.sidebar-brand` 정상 mount + "MA MySQL AI" / `.topbar.height = 52px` / 기존 `.chat-header` DOM 부재 — 모두 확인. browser screenshot (`/tmp/layout-merged.png`): 좌측 sidebar (brand + 제품 칩 + 새 대화 + conv list + 프로필) / 우측 chat-column (topbar 좌측 정렬 제목 "SQL 쿼리 계속 완성 요청" + `최근 갱신 ... 메시지 22 · 소유자 admin` 부제 + 우측 끝 `관리 콘솔` + sticky 분기선 "2026년 4월 16일" + 메시지 영역 확장) — ChatGPT 패턴 정확 구현 + 직전 cycle 변경 (sticky / "···" menu) 무회귀. cache-bust `v=20260518-topbar-merge`. JS 변경 0.

---

**2026-05-18 TASK-0065 완료 — TASK-0063 직접 테스트 follow-up 3 항목 (헤더 4 버튼 제거 + trigger 우측 하단 + 분기선 sticky)** (CHG-20260518-0002, REV-20260518-0002, REQ-20260518-0003, Minor §12.3 — UI 정리, RBAC / endpoint / 데이터 영역 무변경).

**변경**: (1) `chat-header-tools` 의 `forkConversationBtn` / `shareConversationBtn` / `renameConversationBtn` / `deleteConversationBtn` 4 element 제거. conv-item "···" menu 가 단일 진입점. backend helper 는 menu makeItem + message-bubble actions 에서 여전히 호출 — 무변경. (2) `.conv-item-menu-trigger` 위치 `top: 6px` → `bottom: 6px` (owner badge 와 시각 충돌 해결). `.conv-item` 에 `padding-right: 32px` 보정. (3) `.message-date-divider` 에 `position: sticky; top: 0; z-index: 5` + `padding: 4px 0`. label 배경 `var(--surface-2)` (반투명) → `var(--surface-1, #ffffff)` (불투명) + `box-shadow: 0 1px 2px rgba(0,0,0,.04)` elevation. hover 시 `box-shadow: 0 2px 6px rgba(37,99,235,.18)` 강화.

**검증**: `node --check` PASS, `SKIP_INIT=1 make web` 재배포 OK. Browser smoke (`gstack /browse` headless): 헤더 4 버튼 부재 확인 (snapshot 의 `chat-header-tools` 영역에 `loadMoreBtn` 만), active conv-item trigger DOM `getComputedStyle` 가 `bottom: 6px / right: 6px / opacity: 1` (우측 하단 정상), 2 분기선 conversation 에서 `messageLog.scrollTop = 600` 깊이 스크롤 시 첫 분기선 "2026년 4월 15일" 이 messageLog 상단에 sticky stick 됨 (screenshot 첨부) — Slack 패턴 정확 구현. cache-bust `v=20260518-header-cleanup`.

---

**2026-05-18 TASK-0063 완료 — 작업 화면 conv-item "···" menu (복사 / 공유 / 제목 변경 / 삭제) + 캘린더 시간 이동 분기선 trigger** (CHG-20260518-0001, REV-20260518-0001, REQ-20260518-0001, **Major** §12.3 — RBAC catalog 확장 2 + 신규 endpoint 1 + 파괴적 액션 menu 통합). Codex outside voice review 의 10 risk 모두 반영 + 사용자 4 결정 채택 (full self-fork / 신규 권한 분리 / 헤더 share 유지 / 헤더 calendar 제거 + 년 jump 조건부).

**Backend**: `PERMISSION_DEFINITIONS` 에 `conversation.duplicate.own/.any` 2 건 추가 (catalog 34→36). SEED_ROLE_DEFINITIONS operator/sales 에 `.own` grant, admin 은 set(PERMISSION_CODES) 로 둘 다 자동 포함. `_ensure_seed_roles` 의 admin catchup tuple 에 duplicate.own/.any 추가, operator/sales catchup loop 을 (share.create, duplicate.own) 리스트 기반으로 일반화. 신규 endpoint `POST /api/conversations/{cid}/duplicate` — read-gate 먼저 (404 단일 wording → metadata leak 차단), `.any` superset semantics, `_fork_conversation_impl` 재활용, grapheme-safe `사본:` prefix. `_ensure_seed_catchup` 의 catalog hydrate 호출을 seed_roles 앞으로 이동 (회귀 fix — 이전 순서로는 admin/operator/sales catchup 의 _permission_id_map lookup 이 신규 권한 id=0 받아 skip).

**Frontend**: `renderConversationList()` 의 conv-item 마다 `.conv-item-menu-trigger` 추가 (hover/active fade). click → `openConversationItemMenu(cid, triggerEl)` 가 fixed-position dropdown mount (a11y role=menu/menuitem, ESC + outside-click + scroll/resize close, viewport clamping). menu items 는 rename/delete pattern (visible + is-access-blocked + toast). `duplicateConversationFromMenu(cid)` 신설. `createConversationShare({conversationId})` / `renameCurrentConversation(cid)` / `deleteConversation(cid)` 가 cid 인자 수용. `renderMessages()` 에 `.message-date-divider` (Slack pill) 삽입 + click → `openHistoryCalendarAt(dateKey, divider)`. `openHistoryCalendar` 를 `openHistoryCalendarAt(dateKey?, anchorEl?)` 로 리팩토링 — anchorEl 가 주어지면 popover 가 fixed-position 으로 분기선 하단 mount. popover header 의 `#calendarNav` 슬롯에 `‹ › [Y년 M월] (« »)` 동적 nav — 년 jump 는 `(newestYear - oldestYear) >= 1` 일 때만 노출. 헤더 `historyCalendarBtn` 제거. outside-click 으로 popover close 시 `.message-date-divider` 도 trigger pair 로 인정.

**검증**: python compile / node --check 통과. `SKIP_INIT=1 make web` 재배포 PASS. DB 직접 확인 — `WebPermissions` 의 `conversation.duplicate.own/.any` row hydrate 정상, role grant — admin (.any + .own) / operator (.own) / sales (.own). browser headless smoke (`gstack /browse`): 좌측 conv-item "···" trigger 정상 표시, dropdown 4 항목 (복사 / 공유 / 제목 변경 / 삭제 — danger 색) mount, 채팅 로그 "YYYY년 M월 D일" 분기선 표시 + click → popover anchored 오픈, 월 nav (‹ ›) 정상 (테스트 환경 데이터 1년 미만이라 « » 미노출 = 조건 충족 안됨 = 정상). 헤더 historyCalendarBtn 부재 확인. cache-bust `v=20260518-conv-menu`.

후속 cycle 권장 (REV-20260518-0001 Risks):
- 헤더 share 의 hide-vs-disable 패턴을 menu 와 일치 (visible + is-access-blocked) 시키는 정합화 (Codex risk 8 잔여).
- `_ensure_permission_catalog` 가 IsDynamic 컬럼을 명시 INSERT 하도록 강화 (Codex risk 2 — 별 배포 환경 대비).
- 년 jump 버튼의 노출 조건을 `>= 12 months` 또는 `>= 365 days` 로 정밀화 (현재 `>= 1 year diff` 는 같은 해 1월/12월 데이터에서는 숨김).

---

**2026-05-15 TASK-0061 round 2 — /qa 심층 검증 완료, 추가 fix 0건** (browser session `483add52718b4a93`). Phase 4 (Point rail) 의 dot click → smooth scroll + active dot id 갱신 (`291`) 정상. Phase 5 (캘린더) 의 월 prev/next 이동 + has-messages day "15" 선택 → 시각 list 1 개 표시 + screenshot `/shared/out/browser/shot_20260515_091222.png` 정상. Phase 3 stale / Phase 6 비번 reset / Phase 8 bulk delete 는 destructive endpoint 라 운영 환경 사용자 명시 시점에 실 호출 검증 권고 (1차 cycle 의 응답 형식 / 권한 / DOM 요소 검증으로 contract 확정 완료). 본 cycle PR (#27) 은 추가 fix 없이 ship 가능.

**2026-05-15 TASK-0061 완료 — GOAL.md 8 항목 Web UI 합본 cycle (실시간 step / lazy polling / stale 감지 / point rail / 캘린더 / 비밀번호 초기화 / select-all fix / bulk delete)** (CHG-20260515-0003, REV-20260515-0003, REQ-20260515-0003~0010, **Major** §12.3 — Phase 6 Critical 분면 포함, 사용자 일괄 승인 + 보안 권장안 채택). 

**Phase 1+2 (답변 버블 실시간 + 신규 대화 첫 polling)**: `state.pendingBubble` + `renderPendingAssistantBubble()` + 1초 elapsed timer + `applyProgressPayload` 동기화. lazy-create 분기에서 cid 발급 즉시 `startProgressPolling({reset:true})` 호출.

**Phase 3 (stale processing 만료 감지)**: backend `_compute_display_status` + `_last_step_at_for_run` + env `WEB_PROGRESS_STALE_TIMEOUT_SECONDS=1200` (20분). `/api/progress` / `/api/ask_status` / `/api/ask_result` / `_list_conversations` 일관 stale 처리 (status=`stale_error`, is_stale=true, is_processing=false). frontend `.conv-dot.is-stale-error` (빨간 토큰) + tooltip + 1회 toast 안내.

**Phase 4 (Point rail)**: `#messagePointRail` + `renderMessagePointRail()` + scroll observer 로 viewport 중앙 dot highlight. 좁은 화면 hidden.

**Phase 5 (캘린더/시각 이동)**: backend `/api/history_dates` 가 `AgentMemoryMessages` 정본 기준 (이전 `AgentCoreMessages`). frontend `historyCalendarBtn` + `#historyCalendarPopover` (월간 grid + 시각 list) + `/api/history_anchor` smooth scroll.

**Phase 6 (관리자 주관 비밀번호 초기화, Critical)**: `WebAccounts.MustChangePassword TINYINT(1) NOT NULL DEFAULT 0` 컬럼 idempotent ALTER. 신규 endpoint `POST /api/admin/accounts/{id}/password-reset` — `secrets.token_urlsafe(12)` 임시 비번 + `MustChangePassword=1` + 대상 계정 `WebAuthSessions IsRevoked=1`. self-reset 거부. `_serialize_account` + `_fetch_account_rows` 에 `must_change_password` 노출. `/api/auth/me` PATCH 가 비번 변경 성공 시 `MustChangePassword=0`. frontend Account detail 의 `adminPasswordResetBtn` + 1회 표시 modal + 강제 변경 modal (login + initializeWorkspace 직후 hook).

**Phase 7 (admin select-all 현재 페이지 fix)**: `currentPageAccounts()` helper 신설. `accountSelectAll` change handler 와 `updateAccountSelectAllCheckbox()` 가 동일 helper 사용 — 현재 페이지 row 만 토글, 다른 페이지 선택 보존.

**Phase 8 (내 대화 Ctrl/Shift 다중 선택 + bulk delete)**: `state.conversationSelected: Set<string>` + Ctrl/Meta toggle + Shift range. own 그룹만 `.conv-item-checkbox` 노출. `.conv-bulk-bar`. backend `_delete_conversation_impl` helper 추출 + `POST /api/delete_conversations` partial success endpoint. ≥10 typed-confirm + processing 강제 삭제 confirm.

검증: python compile / node --check 통과. `make web` 재배포 PASS. browser (http://web:8000) DOM 5개 신규 element + login + bulk bar + 캘린더 popover 2026-04 + `/api/progress` display_status + `/api/history_dates` AgentMemoryMessages 응답 + `/api/delete_conversations` empty=400 validation + pending bubble spinner/elapsed/bubble 정상 + admin currentPageAccounts()=15 / filteredAccounts()=26 (다른 페이지 보존) + `adminPasswordResetBtn` "비밀번호 초기화" 노출 확인. cache-bust `v=20260515-task-0061`.

**2026-05-15 TASK-0060 완료 — 실제 접근 DB 기반 Product / Role 시스템 프롬프트 정비 + Role 공통 누적 적용 fix** (CHG-20260515-0002, REQ-20260515-0002, Minor §12.3). 현재 Product는 `KR(킹스레이드)`와 `MV(마이크로볼츠)` 두 개다. `KR`은 `dbgame,dblog,dbauth`, `MV`는 `account_db,dev_1_1_1_20,have_00,log_v2,global_db`가 접근 DB로 등록되어 있다. `information_schema`와 제한적 집계로 주요 테이블/행 수/시간 범위를 확인한 뒤 `WebSystemPrompts`에 Product prompt 2건과 Role common prompt 5건(`pending/operator/admin/sales/dba`, `ProductId IS NULL`)을 upsert했다. `log_v2`는 DB는 존재하지만 테이블 0개로 확인되어 MV prompt에 명시했다. 기존 runtime은 Role×Product prompt가 있으면 `전 Product 공통` Role prompt를 fallback으로만 사용했으므로, feature-0002 `compose_system_prompt()`를 공통 누적 방식으로 수정했다. 검증: py_compile 통과, 신규 unittest 2건 통과, SQL readback 완료, web 컨테이너 내부 `compose_system_prompt(product_id=1, role_id=16, product_mode="pinned")` 결과에 `PRODUCT CONTEXT` + `ROLE GUIDANCE` + `### 전 Product 공통` 포함 확인.

**2026-05-12 TASK-0056 완료 — 작업 화면·관리 콘솔 권한 정렬 분리** (CHG-20260512-0002, REQ-20260512-0002, **Major** §12.3). 사용자 보고: "작업 화면에서 접근하는 권한과 관리 콘솔에서 접근하는 권한을 수정할 때 해당 권한들의 순서가 혼용되어 있어 각 화면에 알맞게 순서 및 섹션을 구분 필요". 두 화면이 같은 group 순서 (`console→account→role→conversation→[product]→misc`) 로 묶여 있어 화면 맥락 (자기시점 / 관리자시점) 이 정반대인데도 admin 메타권한이 두 곳 모두 위에 노출되던 문제. **분리 안**: 작업 화면 = "운영 권한 (conversation/product) → 관리 권한 (console/account/role) → 기타" + 관리 권한 묶음은 보유 시만 표시. 관리 콘솔 = "관리 권한 → 운영 권한 → 기타" 2단 section 헤더로 시각 분리. (1) [`docs/CONVENTIONS.md §10.6`](../../../docs/CONVENTIONS.md) 화면별 권한 섹션·정렬 정책 신설 — 화면별 section 순서 표, 정합 규칙 6 줄, 동적 권한 (`product.access.<key>`, `system_prompt.*`) 처리, 새 group key fallback 정책. (2) **admin.js**: 새 상수 `ADMIN_PERMISSION_SECTIONS`, 새 함수 `sectionedGroupedPermissions(opts)`, `renderPermissionGrid` 가 outer `.permission-section` 으로 inner `<details data-perm-group>` 을 감싸도록 수정. (3) **app.js**: `PERMISSION_GROUP_ORDER` 에 `product` 추가 (작업 화면 측 누락 fix), `PERMISSION_GROUP_LABELS.product = "제품"`, 새 상수 `WORK_SCREEN_PERMISSION_SECTIONS`, `permissionGroupOf()` 가 `system_prompt.` 접두사를 product 로 매핑, `PERMISSION_LABELS` / `_DESCRIPTIONS` 에 `product.manage` / `system_prompt.manage.role.any` 추가, `buildPermissionPills` 가 2단 묶음 (`.perm-section-meta`) 으로 렌더 + 빈 section 자동 hide. (4) **styles.css**: 작업 화면 `.perm-section-meta*` 5 클래스, 관리 콘솔 `.permission-section*` 5 클래스 (`data-perm-section="manage"` 살짝 파랑 / `"operate"` 살짝 녹색), section 간 gap 중첩 제거. (5) cache-bust `v=20260512-perm-sections` (admin.html / index.html). **DB schema / backend RBAC catalog / endpoint guard / system prompt assembly 변경 0** — frontend 렌더링 + 정책 문서만 수정, 인가 모델 무영향. node --check 양 파일 통과. **후속**: (a) `make web` 재배포 + 시각 검증 (사용자 환경 — 일반 사용자 / admin 양 시점). (b) 새 group key 가 백엔드에 추가될 때 두 상수 (`WORK_SCREEN_PERMISSION_SECTIONS` / `ADMIN_PERMISSION_SECTIONS`) 에 명시 매핑 — 미매핑 시 "기타" fallback. (c) CONVENTIONS.md §10.6 의 "policy-contract 자동 contract 정의" 후속 cycle 등록.

**2026-05-12 TASK-0055 완료 — 관리 콘솔 카테고리별 다중선택 UX 정합 컨벤션 v0.2 도입 + 코드 통일** (CHG-20260512-0001, REV-20260512-0001, REQ-20260512-0001, Major §12.3, 사용자 명시 AI 자율 commit/push). 사용자 raw feedback "관리 콘솔의 카테고리 별 다중선택 UI 가 계정=우상단 / 역할=좌하단 / 제품=다중선택 부재 로 일관성 없음. 차후 작업에서도 이러한 경향이 나타나지 않도록 방향을 정합적으로 명시" 대응. 본 cycle = **정책 + gstack design 외부 시각 + Core+keyboard+advanced 코드 통일 합본**. (1) **정책 정립**: [project-level `docs/CONVENTIONS.md §10`](../../../docs/CONVENTIONS.md) 신설 (다중선택 적용 룰 / DOM anchor 표준 / 자료구조 invariant / 단위 어휘 / 신규 카테고리 체크리스트) + [feature-local `docs/DESIGN.md`](./DESIGN.md) 신규 (14 섹션, HTML 구조 / CSS 토큰 / Set invariant / runtime assertion / §5 컴포넌트 set / §6 cross-page banner / §7 typed-confirm / §8 RBAC partial-fail UI / §9 keyboard map / §10 a11y / §11 렌더 cycle / §12 Products 마이그레이션 plan / §13 open questions / §14 모던 레퍼런스 거부 근거). (2) **외부 design 시각** (general-purpose subagent + worker-design framework 차용) 으로 v0.1 → v0.2 흡수: dimension rating IA 6 / Visual 5 / Interaction 6 / Consistency 7 / A11y 4 의 5 gap (cross-page selection / empty·loading·error state / optimistic rollback / confirm 컨벤션 / RBAC gating) 전부 반영. 모던 레퍼런스 (Linear floating pill / GitHub select-all menu / Notion morph / Stripe cross-page banner / Vercel inline action) 의 차용·거부 근거 명시. (3) **코드 통일** — admin.html (Accounts bulk anchor 헤더→list 하단, Products multi-select HTML 신설, 모든 카테고리 role/aria-live/cross-page banner), styles.css (`--z-bulk-bar` / `--z-bulk-banner` / `--bulk-bar-bottom` / `--bulk-bar-elev` 토큰, `.admin-bulk-actions` sticky, `.admin-bulk-cross-page`, `.kbd-hint`, `.toast-skipped`), admin.js (`BULK_ENTITY_UNIT` / `BULK_ACTION_LABEL` / `CONFIRM_TYPED_THRESHOLD` 상수, `confirmBulkAction` / `runBulkActionWithPartialFail` / `assertBulkBarContract` / `renderCrossPageBanner` / `applyShiftRangeSelect` 헬퍼, Accounts/Roles/Products 의 `render*List` / `render*BulkBar` / `bulk*SetActive` / `bulk*Delete` 전면 통일, `productSelected: Set<number>` 신설, `accountLastClickIdx` / `roleLastClickIdx` / `productLastClickIdx` 신설, Esc 글로벌 핸들러, `productSelectAll` listener, initialize 끝에 `assertBulkBarContract` 호출). 사이즈: admin.js 2645 → 3080 lines (+435), admin.html 219 → 250 lines (+31), styles.css 2976 → 3052 lines (+76). cache-bust `v=20260512-bulk-contract-v02`. **node --check admin.js 통과**. **후속 검증 항목**: (a) 실제 `make web` 기동 + 브라우저 시각 검증 (사용자 환경) — 본 cycle 은 코드 변경 + 정적 검증까지. (b) `setProductMetaPending(_delete: true)` 의 backend apply path 검증 — backend 가 product `_delete` 키를 수용하는지 확인 필요. (c) e2e/screenshot test 가 `#accountsBulkBar` 의 기존 위치 selector 에 의존하는지 정리. (d) `assertBulkBarContract` 의 CI 화 (jsdom 또는 e2e snapshot). (e) `window.prompt()` 기반 typed-confirmation 의 modern modal upgrade (v0.3 후보).

**2026-05-07 TASK-0053 follow-up 2 — pending row UI 뒤틀림 fix + 제품별 접근 카드 list 를 권한 grid 의 'product' 그룹 details 안으로 이전** (CHG-20260507-0001, REV-20260507-0001). 사용자 직접 보고 두 이슈. (1) `.admin-list-row.has-pending::before { content: "" }` placeholder rule 의 pseudo-element 가 CSS Grid 의 4번째 grid item 으로 참여해 cb/main/chips layout 이 row 2 까지 밀리던 버그 → pseudo-element 제거 + `border-color` 로 대체. (2) `buildRoleProductCardList` / `buildAccountProductOverrideList` 에 `opts.embed` 추가 + `renderRoleDetail` / `renderAccountDetail` 가 권한 grid 안의 `details[data-perm-group="product"]` 를 찾아 그 안에 append. 사용자가 "제품" 그룹 collapse 시 정적 권한 + product 별 카드가 함께 접힘. DOM 좌표 비교 + screenshot 시각 검증 통과.

**2026-05-06 TASK-0053 완료 — 신규 제품 default 정책 토글 (Product 주체) + 권한 grid 의 product sub-catalog + Role/Account detail 의 product 카드** (REQ-20260506-0006, Major §12.3, AI 자율 commit/push). 사용자 follow-up: 신규 product 가 추가될 때마다 각 role 마다 비활성화하는 번거로움 해소 + product 가 많아질 때 Role/Account detail 에서 가시성 향상. 사용자 in-cycle 설계 전환으로 정책 주체를 Role → Product 로 변경 (`WebProducts.DefaultRoleAccess` 컬럼). admin UI 토글은 Product detail 에 위치. 권한 grid 의 dynamic `product.access.*` 가 별도 product subcatalog 카드로 분리되어 Role detail 은 product 별 (access 토글 + role-scope prompt) collapsible card list, Account detail 은 product 별 override (allow/deny/inherit) flat card list. E2E smoke: product 생성 시 `default_role_access=false` → 6 role 모두 grant 0 / `=true` → 6 role 모두 grant. backend `/api/admin/products` 응답에 `default_role_access` 노출, `/api/admin/roles` 에서는 이전 시도 잔재 `default_product_access` 필드 제거 확인.

**2026-05-06 TASK-0052 완료 — 계정·역할 → 제품 권한 상속/override 모델 도입** (REQ-20260506-0005, **Critical** §12.3, AI 자율 commit/push 모드). Codex outside voice 의 9 finding 모두 통합. Phase 1A (catalog 인자화, commit `4dd1d0a`) → Phase 1B (catalog DB-driven + product 권한 backfill + 명시적 트랜잭션 + caller-update) → Phase 1C (G1-G8 8 endpoint guards + admin_update_account RoleId 손실 pre-existing 버그 fix) → Phase 1D (admin UI PERMISSION_GROUP_ORDER 'product') → Phase 2 (HTTP smoke 6/6 P0 직접 + lifecycle T13/T16 cascade + bug fix 검증). bootstrap stderr 메시지 `[TASK-0052 Phase 1B catchup] product access backfill: 7 permission/role-permission rows added` 운영 transparency 확인. catalog 33 → 34 (`product.access.kr` 추가). admin 이 deny override 적용 시 G1/G2/G7/G8 모두 HTTP 403 정상. Phase 2 P2 (sessions/me filter, end-user FE chip filter) 와 F8 (admin lockout 보호) 는 별 cycle 분리.

**2026-05-06 TASK-0052 Phase 1A 진입 — RBAC engine catalog 인자화 refactor** (REQ-20260506-0005, Critical §12.3) — Codex outside voice (Claim 1) 가 발견한 정적 `PERMISSION_CODES` 가정에 5 hot path 가 hardwired 되어 있던 문제의 1 단계 해소. `_resolve_permission_catalog(conn=None)` 헬퍼 신설 + 5 함수 시그니처를 catalog 인자 받는 형태로 확장 (default None = 기존 정적 동작). `/api/admin/permissions` 1 곳만 신규 plumbing 경로로 전환해 Phase 1B 의 DB-driven catalog 도입 surface 를 미리 검증. **동작 변경 0** (33 codes 정확히 동일), `make web` 재배포 + HTTP smoke 통과. Phase 1B (WebPermissions IsDynamic/ProductId 컬럼 + product 권한 backfill SQL + caller-update) / Phase 1C (8 endpoint guard) / Phase 1D (admin UI group label) 는 별 cycle 분리. plan 정본은 [BRIEFING-c5-permission-product-access.md](./BRIEFING-c5-permission-product-access.md).

**2026-05-06 관리 콘솔 일괄 저장 정책 회복 + 메타 4 종 시각화 + DB 라이브 enum** (TASK-0051, REQ-20260506-0004) — 관리 콘솔에 남아 있던 인라인 save 버튼 3 종 (`프롬프트 저장` / `제품 정보 저장` / `DB 목록 저장`) 을 footer `모두 적용` 단일 commit 흐름에 통합하고, 메타데이터 4 스키마(`information_schema`/`mysql`/`sys`/`performance_schema`) 를 회색 disabled chip + `항상 접근` 라벨로 강제 노출(REV-20260422-0006 정책 시각화), 자유 텍스트 chip 입력을 `GET /api/admin/databases/available` 라이브 enum 기반 picker 로 교체했다. C5 (계정·역할 → 제품 권한 상속/override 모델) 는 다음 cycle 의 `/plan-eng-review` 후 진행으로 분리 권고.

**2026-05-06 빈 대화 누적 이슈 일괄 해결** — TASK-0048 (신규 누적 차단, lazy 화), TASK-0049 (누적분 정리, 88→46 conversations), TASK-0050 (`make web` 의 docker compose + buildx race 회피로 운영 검증 가능화) 의 3개 TASK 가 같은 cycle 에서 동시 마감되었다. 운영 데이터에서 빈 대화는 0 건이며 신규 row 측 차단 로직이 컨테이너에 반영되어 활성 상태다 (`docker exec repo-web-1 grep PENDING_CONV_SENTINEL`).

"새 대화" 버튼은 더 이상 `POST /api/new_conversation` 을 즉시 호출하지 않는다 (TASK-0048, REQ-20260506-0001). 클릭 시 client-side `state.pendingNewConversation=true` 로만 진입해 사이드바 "내 대화" 그룹 상단에 `conv-item is-own is-active is-pending` placeholder ("새 대화 (작성 중)" / 부제 "첫 메시지를 입력하세요") 가 표시되고 composer 가 활성 상태로 떨어진다. 사용자가 첫 메시지를 보내면 `sendPrompt()` 가 `/api/ask` 에 `conversation_id: ""` + `product_mode` + `product_id` (사용자 직전 의도) 를 첨부해 호출하고, backend `/api/ask` 의 `request_conversation_id` 가 비어있는 lazy creation 분기에서 `_resolve_conversation_for_account(create_if_missing=True)` 직후 hint 를 `AgentCoreConversations.product_id/product_mode` 에 셋업 + `_save_account_product_pref` 호출로 `WebAccounts.ProductPref*` 미러까지 갱신한다. 응답의 `conversation_id` 를 client 가 채택하고 placeholder 가 사라진다. 빈 대화 누적이 신규 row 측에서 차단된다 — 사용자가 버튼만 누르고 메시지를 보내지 않으면 backend 에는 아무 row 가 생기지 않는다. PATCH race 가드(TASK-0047 AC-0013) 와 attach/resume(TASK-0041 AC-0018) 는 cid 가 있을 때만 의미가 있어 lazy 분기에서 의도적으로 비활성화 — pending 단계 ask 실패는 "다시 시도하거나 사이드바 새로고침" 안내 토스트로 fallback. 기존 누적된 빈 대화의 일괄 정리는 destructive 변경이라 §12 사람 승인이 필요하므로 본 TASK 범위 외 — 후속 작업으로 명시.

사용자가 진입(로그인 직후) 또는 진행 중 대화에서 대상 **제품(Product)** 을 사이드바 헤더 칩에서 선택할 수 있고, `auto` 옵션으로 일반 대화를 이어갈 수 있도록 UX 와 데이터 모델을 확장했다 (TASK-0047). `AgentCoreConversations.product_mode VARCHAR(8) NOT NULL DEFAULT 'pinned'` 컬럼과 `WebAccounts.ProductPrefMode/ProductPrefPinnedId` 두 컬럼이 추가되었고, 신규 `PATCH /api/conversations/{cid}/product` 엔드포인트가 권한·소유자·진행 중 ask race(`AgentMemoryKv.last_status='processing'` ⇒ 409) 가드와 함께 도입되었다. `compose_system_prompt(... ,product_mode='auto')` 분기는 PRODUCT/role/account 의 product 한정 prompt 를 모두 건너뛰고 `[AUTO MODE]` 한 줄만 inject 하며, web 레이어가 `allowed_schemas=[]` (메타 4 스키마 한정) 으로 cross-product leak 을 차단한다. Frontend 는 `state.productMode/pinnedProductId/activeProductId` 3-필드 분리 + `setActiveProduct()` optimistic + PATCH + localStorage 미러(`mad.productPref.v1`) + `<select>` busy disabled tooltip 을 갖췄다. 사용자 가시 한글 라벨 "상품" 은 모두 "제품" 으로 일괄 치환되었고, 코드 식별자(`Product`/`product_id`/`WebProducts`/`ProductKey`) 는 보존했다. **본 turn 은 사용자 검토 없이 4인 agent team(UX/Frontend Architect/Backend Engineer/QA-Flow Validator) 합의 + Codex CLI 교차검증** 으로 진행됐다 — 운영 반영 전에 [`docs/BRIEFING-product-selector-v1.md`](./BRIEFING-product-selector-v1.md) 의 R-01..R-16 검증 + D-01..D-05 사람 결정이 필요하다.

System Prompt 를 Product → Role → Account 3 계층으로 조립하도록 재설계하고, Product 단위의 DB 접근 whitelist 를 agent tools 레벨에서 강제하도록 도입했다. `WebProducts` / `WebProductDatabases` / `WebSystemPrompts` 신규 테이블과 `AgentCoreConversations.product_id` 컬럼을 추가해 모든 대화가 Product 컨텍스트에 귀속되고, `compose_system_prompt` 가 base SYSTEM_PROMPT 뒤로 `## PRODUCT CONTEXT` → `## ROLE GUIDANCE` → `## ACCOUNT PREFERENCES` 블록을 순차 append 한다. 관리 콘솔에는 `상품 카테고리` 그룹 구분선과 함께 `상품 (Products)` 탭(Product CRUD + 접근 DB chip + Product scope prompt 편집기) 이 추가되었고, Roles detail 에 Role scope prompt 편집기가, 프로필 드로우에 `프롬프트` 탭(Account scope) 이 각각 추가되었다. whitelist 정책은 TASK-0039 에서 메타데이터 4 스키마(`information_schema`/`sys`/`mysql`/`performance_schema`) 를 Product 설정과 무관하게 항상 bypass 하도록 재조정했다 — agent 의 DB 구조 탐색을 보장하면서도 `agent_memory` 차단은 유지해 타 계정 데이터 노출을 막는다. TASK-0046 (REQ-20260425-0001) 에서 프로필 드로어의 API Vault 탭을 Linear Wizard 3-step 구조로 재설계하고 키 갈아끼움 진입점을 "저장된 키 삭제" → confirm → wizard 재진입 → 새 입력 → 저장 1 경로로 단일화했다.

## 2. Progress
- Planned: Phase 2 P2 (sessions/me filter, end-user FE chip filter), F8 (admin lockout 보호) — 별 cycle 분리
- In Progress: TASK-0052 Phase 1B/1C/1D + Phase 2 P0 완료, TASK-0034 복잡 QA 성능 테스트 (Q4/Q5 재수행 — TASK-0040/0041/0046 선행 완료 상태)
- Done: TASK-0052 Phase 1A (4dd1d0a), TASK-0051 관리 콘솔 일괄 저장, TASK-0050 make web buildx race 회피, TASK-0049 누적 빈 대화 일괄 정리, TASK-0048 lazy "새 대화", (이전 항목 below)
- Done: TASK-0050 make web buildx race 회피, TASK-0049 누적 빈 대화 일괄 정리, TASK-0048 "새 대화" lazy 화, TASK-0047 Product Selector + Auto 모드, TASK-0046 API Vault 패널 Linear Wizard 재설계, TASK-0041 클라이언트 타임아웃 시 Attach/Resume, TASK-0040 schema whitelist 정규식 context-aware 수정, TASK-0039 메타데이터 스키마 whitelist bypass 정책, TASK-0036 System Prompt Depth + Product DB whitelist, TASK-0035 대화 사이드바 구분/정렬 + 대화/말풍선 fork, (이전) RBAC table cutover, role CRUD, account role assignment, tri-state override, account soft delete, own/any 대화 권한 분기, 제목 변경 API, `clear_memory` 제거, `console.access` 기반 읽기 전용 관리자 셸, 브라우저/API 검증

## 3. Recent Changes
- 2026-05-19 (TASK-0080, REQ-20260519-0008, Minor §12.3 — `_collect_matched_excerpts` AgentMemoryMessages + AgentCoreMessages UNION): TASK-0077 followup. 사용자 직접 확인 — core-only conv 의 snippet 부재 회귀 노출. backend `_collect_matched_excerpts` 의 SELECT 를 두 table UNION ALL + `ROW_NUMBER OVER (PARTITION BY cid ORDER BY msg_id DESC)` 으로 conv 별 더 최근 매칭 1건 선택. `COLLATE utf8mb4_unicode_ci` 통일. RBAC / audit / endpoint contract / line-based clip 로직 무변경. cache-bust `v=20260519-snippet-line` → `v=20260519-chat-pane-flex` (TASK-0079 와 묶음).
- 2026-05-19 (TASK-0079, REQ-20260519-0007, Minor §12.3 — `.chat-pane` flex layout hotfix, TASK-0066 cascade 잔여 결함): 사용자 screenshot 보고 — 짧은 대화 + 큰 viewport 조합에서 composer 아래 viewport bottom 까지 회색 빈 영역 노출. 원인: `.chat-column` flex container 안 `.chat-pane` 의 flex 미정의 → 자식 max-content 만 차지 → `.messages-wrap (flex: 1)` 의 grow chain 끊김. TASK-0066 ChatGPT 패턴 layout 재구조화 시점 누락 + TASK-0068~0071 cascade hotfix chain 이 admin 영역만 다뤘음. Fix: `.chat-pane` 에 `flex: 1 1 auto; min-height: 0` 추가 (CSS 2 line). backend / RBAC / endpoint / JS 무변경. cache-bust `v=20260519-chat-pane-flex` (TASK-0080 과 묶음). make web 재배포 OK (29 초 후 healthy).
- 2026-05-19 (TASK-0078, REQ-20260519-0006, Minor §12.3 — search modal 3 항목 추가 hotfix of TASK-0077): 사용자 직접 테스트 보고 3 항목. (1) **mouseup race 보강** — TASK-0077 의 mousedownOnOverlay-only flag 부족. modal 바깥 mousedown → modal 안 mouseup 시 click target = overlay 가 되어 close 됨. Fix: `state.searchModal.mouseupOnOverlay` 도 추가 추적, click 시 mousedown + mouseup + target 3 개 모두 overlay 일 때만 close (양 끝점 모두 backdrop 인 의도적 click 만). (2) **preset 텍스트 "부터" 제거** — "1시간 전부터" → "1시간 전" 5 버튼 모두. (3) **snippet 본문 발췌 line-based clip** — `_collect_matched_excerpts` 가 매칭 위치의 line 경계 (`\n` 직후 ~ `\n` 직전) 를 찾아 line 전체 반환. line ≤ 220 char 면 그대로, 초과 시 매칭 위치 ±60 char clip + "…". `.search-snippet` CSS line-clamp 2 → 3 + line-height 1.45 + max-height 4.6em. cache-bust `v=20260519-search-presets` → `v=20260519-snippet-line`. py_compile + node --check PASS, make web 24 초 후 healthy.
- 2026-05-19 (TASK-0077, REQ-20260519-0005, Minor §12.3 — search modal 5 항목 hotfix bundle of TASK-0072/0076): 사용자 직접 테스트 보고 5 항목 모두 반영. (1) min char 3→2 (backend `_normalize_search_query` + frontend gate/placeholder/highlight). (2) 소유자 facet DOM + JS 전부 제거 (효용성 낮음 — 사용자 결정). backend `owner_id` 파라미터는 호환 위해 유지. (3) 기간 popover 에 preset 5 종 (1시간/1일/1주/1개월/1년 전부터 지금까지). click 시 from/to 자동 + popover input sync + 즉시 적용. (4) mouseup race fix — `state.searchModal.mousedownOnOverlay` flag 로 click = mousedown + mouseup 둘 다 overlay 일 때만 close. modal 안 text drag 후 backdrop mouseup 시 close 안 됨. (5) snippet 본문 excerpt — backend `_collect_matched_excerpts` 신설 (MySQL 8.0 `ROW_NUMBER() OVER (PARTITION BY ConversationId ORDER BY Id DESC)` 으로 conv 별 최근 매칭 message content 의 매칭 위치 ±40 char clip + "…"). endpoint 가 `matched_excerpts: {conv_id: "..."}` 응답에 첨부. frontend `renderSearchModalResults` 가 snippet 영역에 excerpt + highlight. TASK-0072 의 audit/RBAC 정책 무변경 (snippet opt-in chip + .any 한정 + WebAccountActivity audit). cache-bust `v=20260519-search-facets` → `v=20260519-search-presets`. py_compile + node --check PASS, make web 재배포 OK (8초 후 healthy).
- 2026-05-19 (TASK-0076, REQ-20260519-0004, Minor §12.3 — search modal UX 3 결함 hotfix bundle of TASK-0072): 사용자 직접 테스트 보고 3 항목 — facet click 무동작 / 키보드 ↑↓ scroll 미동작 / 매칭 message bubble jump 미동작. frontend only fix (backend / RBAC / audit / endpoint 무변경). (1) 제품 facet DOM 제거 (사용자 결정: 대화 중 product 변경 가능 → 필터 부적합). 소유자 facet popover (`/api/admin/accounts` 1 회 캐시, .any 한정, "전체" + 각 계정 role label). 기간 facet popover (`<input type="date">` from/to + 적용/지우기). (2) ArrowDown/Up 시 active row 의 `scrollIntoView({block:'nearest'})`. Enter 도 click 과 동일 jump 적용. (3) result click / Enter 시 `state.searchModal.pendingJumpQuery/Conv` 저장 → `selectConversation` 끝 (loadHistory + renderMessages 직후) `_jumpToSearchMatchedMessage()` 호출 → `messageLogEl .message` 의 textContent lowercase compare → 첫 매칭 row `scrollIntoView({behavior:'smooth', block:'center'})` + `.is-search-matched` class 1.8 s pulse animation. cache-bust `v=20260519-modal-contrast` → `v=20260519-search-facets` (styles.css + app.js). make web 재배포 후 healthy. node --check PASS.
- 2026-05-19 (TASK-0074, REQ-20260519-0002, Minor §12.3 — search modal 색상 가독성 hotfix of TASK-0072): site theme = light (`--bg #f4f4f5` / `--surface #ffffff` / `--text #18181b`) 환경에서 TASK-0072 modal 의 미정의 var fallback (dark hardcode `#1f2429`) + site 의 검은 text inherit 충돌 → 어두운 배경 위 검은 텍스트 = 가독성 0 (사용자 screenshot 보고 "사용자가 이용할 수 없을 정도의 색상 구성"). Fix: modal CSS 100여 줄을 site 의 기존 토큰 (`--surface` / `--text` / `--border` / `--text-muted` / `--primary` / `--primary-soft` / `--bg`) 으로 일관 적용. backdrop dark overlay (`rgba(15,23,42,0.48)`) 는 modal pop 강조 유지. highlight bg `#fde68a` + `font-weight: 600` (light theme 위 WCAG AA 충분). owner badge "내" = `--primary-soft` bg + `--primary` border + `--primary-dark` text triple. result row hover/active = `--primary-soft`. cache-bust `v=20260518-conv-search` → `v=20260519-modal-contrast` (styles.css + app.js 양쪽 동일). backend / RBAC / audit / endpoint 무변경. TASK-0073 Phase A0 (WebAuditEvents) 와 file overlap 없음 (styles.css + index.html cache-bust vs app.py DDL + docs). make web 재배포 12 초 후 healthy.
- 2026-05-18 (TASK-0072, REQ-20260518-0010, **Critical** §12.3 — 타 계정 대화 검색·필터 + WebAccountActivity audit log)
  - **Phase A0 (audit infra)**: `WebAccountActivity` (`Id, AccountId, Action, TargetOwnerId, QueryHash CHAR(64), MatchedCount, CreatedAt`) + `_log_search_activity()` helper. SHA-256 hash, 평문 query 저장 금지. slow + fast path 양쪽 보장.
  - **Phase A1 (`_list_conversations` 확장)**: 3 sub-spec — (a) SQL composition order: `.own` owner_id WHERE 가 q 보다 항상 먼저 AND; (b) `hidden_ids` SQL push (`NOT IN`); (c) Python re-sort 삭제 (SQL `ORDER BY` 단일화). 새 파라미터 6: `q`/`owner_id`/`product_id`/`date_from`/`date_to`/`cursor`. `LIKE %s ESCAPE '!'` + `!`/`%`/`_` 3 char escape. min 3 char raw input. `WebAccounts.DeletedAt IS NULL` 필터. collation audit (process 당 1 회).
  - **Phase A2 (`/api/conversations` search mode)**: search params 1 개 이상이면 search mode 분기. body-search 시 `_search_rate_limit_check` 10 req/min (429), `SET SESSION max_execution_time=3000ms`, `_log_search_activity` audit INSERT. cursor pagination 응답 (`next_cursor`). q < 3 char / post-escape 0 → 400. byte-equal owner_id response.
  - **Phase B (test)**: `tests/test_search_rbac.py` 6 시나리오 (cross-account leak / byte-equal owner_id / cursor disjoint / q<3 → 400 / rate limit 11 → 429). 실행은 Phase E 컨테이너 가동 + admin/operator 비밀번호 필요.
  - **Phase C (frontend Spotlight modal)**: 사용자 변형 채택 — 사이드바 "+ 새 대화" 우측 같은 높이에 돋보기 icon (Cmd/Ctrl+K). modal: input(min 3 char + 300ms 디바운스) + 4 facet chip (owner/product/date/snippet, `.any` 만 owner+snippet) + result list (highlight + snippet opt-in) + "더 보기" cursor pagination + a11y (Esc/ArrowUp/Down/Enter, focus 복원). cache-bust `v=20260518-conv-search`.
  - **Phase D**: FUNCTION (REQ-20260518-0010 + AC-0151~AC-0158, 8 개) + MODIFY (CHG-20260518-0010) + REVIEW (REV-20260518-0010, outside voice 3 verdict + D1~D3 + 5 결정 + 6 risk) + TEST (§2 case 추가) + SECURITY §8 + STATUS row.
  - **Phase E**: `make web` + browser smoke + `verify-completion --pre-commit` + commit 사용자 확인 후.
  - **outside voice 3 verdict (REVIEW.md REV-20260518-0010)**: security FIX-FIRST → 4 must-fix 흡수, adversarial Blocker → 3 sub-spec + 6 risk 흡수, ux NEEDS-TWEAK → Spotlight modal 패턴 채택. memory 정책 `feedback_outside_voice_for_rbac` 강제 적용.
  - **D1/D2/D3 결정**: D1 A (LIKE + 안전망; FULLTEXT 별 cycle — 한국어 ngram + Critical migration interleave 회피), D2 A (snippet 항상 OFF + opt-in), D3 B (cursor `updated_at DESC, conversation_id DESC`).
  - **검증 통과**: `python3 -m py_compile app.py` / `python3 -m py_compile test_search_rbac.py` / `node --check app.js` 모두 PASS.
- 2026-05-15 (TASK-0060): Product prompt 2건 + Role common prompt 5건 DB upsert. DB 분석 결과: `KR` 주요 구조는 `dbgame`(현재 상태) / `dblog`(대용량 로그) / `dbauth`(인증·기기), `MV` 주요 구조는 `account_db`(계정) / `dev_1_1_1_20`(기준정보) / `have_00`(보유·매치 이력) / `global_db`(서버·이벤트) / `log_v2`(테이블 0개). Role common prompt 누적 적용을 위해 feature-0002 `compose_system_prompt()` 수정 및 테스트 추가.
- 2026-05-08 Git 동기화 (PR #2 + PR #3 → main)
  - **PR #2** (`feat/adopt-external-anchor-v3.2.0-rc` → `main`, merge commit `eafe4c2`): 72 commits / 137 files / +28320 / -9018. TASK-0046~0053 + 정책 v3.6.0 진화 + 빈 대화 누적 차단 + 관리 콘솔 일괄 저장 회복. main 의 v3.0.0 마이그레이션 commit (`639130b`) 와 본 브랜치의 v3.6.0 진화 conflict (10 files: AGENTS.md / CONTRIBUTING.md / unit/_template/docs/TASK.md / docs/{CODEBASE_MAP,LEARNINGS}.md / playbooks/{PB-0001~0004,README}.md) 는 §3.2 + §16.6 자율 해결 원칙에 따라 본 브랜치(v3.6.0) 우선으로 합병 commit `ae53965` 생성. CI 의 `policy-contract` fail (브랜치 `feat/*` 가 `issue/<번호>-<short-slug>` 자동화 계약 외) + `selfhosted-runtime-smoke` fail (runner 의 `repo-agent` 이미지 누락) + `ai-review` fail (워크플로우 heredoc EOF delimiter 버그) 은 모두 PR 본문 자체와 무관한 인프라 이슈로 사용자 직접 지시 (§3.1 우선순위 1) 에 따라 admin merge 수행.
  - **PR #3** (`issue/1-github-bootstrap` → `main`, merge commit `3fd4272`): 단일 commit `38702cd` — self-hosted runner + 로컬 claude CLI 전환. 머지 전 main 의 `.github/workflows/{ai-execute,ai-review,ai-triage}.yml` 이 `runs-on: ubuntu-latest` + `anthropics/claude-code-action@v1` 로 남아있어 commit 메시지의 "Pro/Max OAuth 토큰이 2026-02-20 이후 거부" 회귀가 노출된 상태였다. 머지 후 main 의 ai-execute.yml 이 `runs-on: [self-hosted, linux]` + 로컬 `claude -p ...` 호출로 정렬됨을 확인 — 운영 정합성 회복.
  - **누적된 main 상태**: `3fd4272` ← `eafe4c2` ← `ae53965` ← `d9272a8` (TASK-0053 follow-up) ... ← `639130b` (이전 main 끝).
  - **feat 브랜치 후속**: main 대비 behind 3 (PR #2/PR #3 의 merge commits + ae53965 가 feat 에 없음). feat 에서 추가 작업 시 `git pull origin main` 또는 rebase 로 catch-up 권고.

- 2026-05-07 (TASK-0053 follow-up, CHG-20260507-0001, REV-20260507-0001)
  - **Issue 1 (UI 뒤틀림 fix)**: `.admin-list-row.has-pending::before { content: ""; }` placeholder rule 이 CSS Grid 의 4번째 grid item 으로 참여해 cb/main/chips 의 column/row 위치가 어긋나던 버그. DOM 좌표 분석으로 확인 (수정 전 cb x=70 column 2, chips x=11 y=73 row 2 col 1 / 수정 후 cb x=11 column 1, chips x=270 column 3 — row 1 정상). pseudo-element 자체 제거 + `.admin-list-row.has-pending { border-color }` 로 시각 표시 유지.
  - **Issue 2 (제품 카드 위치)**: `buildRoleProductCardList(role, disabled, opts={embed})` / `buildAccountProductOverrideList(account, disabled, opts={embed})` 시그니처에 embed 옵션 추가. `renderRoleDetail` / `renderAccountDetail` 가 `permWrap/overrideWrap.querySelector('details[data-perm-group="product"]')` 로 product 그룹 details 를 찾아 그 안에 product 카드 list 를 append (없으면 fallback). embed=true 모드에서는 별도 section title 생략 (부모 details summary 의 "제품" 라벨과 중복 회피), hint 단축.
  - **CSS**: `.admin-product-card-list-embedded` 신규 변형 (margin-top + padding-top + dashed border-top) — 부모 details 안에서 정적 권한과 시각적 분리.
  - **검증**: node --check + make web 재배포. DOM 좌표 검증 (sales row 정상 + product group 안에 cards 3 개). screenshot 으로 시각 확인.
  - **다음 단계**: 운영 사용 시점에 동일 패턴 (grid 의 ::before pseudo 가 grid item 으로 참여) 의 회귀 방지 — LEARNINGS.md 등재 권고.

- 2026-05-06 (TASK-0053, REQ-20260506-0006, CHG-20260506-0027, REV-20260506-0014)
  - **backend (Phase A — Product 주체)**: `WebProducts.DefaultRoleAccess TINYINT(1) NOT NULL DEFAULT 1` 신규 컬럼. POST `/api/admin/products` body 에 `default_role_access` 수용 + INSERT 시 컬럼 set + transaction 내 backfill 분기. PATCH `/api/admin/products/{id}` 에서도 수용. `_list_products` SELECT/응답에 포함. `_ensure_product_access_permissions(conn)` (catchup) 의 backfill SQL 이 product 의 `DefaultRoleAccess` 값 따라 분기.
  - **backend (이전 시도 정리)**: `WebRoles.DefaultProductAccess` 관련 코드 제거 — `_load_role_by_id`/`_list_roles` SELECT/GROUP BY/응답 dict 에서 컬럼 삭제, `admin_update_role` 의 body 수용/UPDATE 컬럼 제거. 컬럼 자체는 destructive DROP 회피로 DB 잔존 (다음 cleanup cycle 에서 DROP COLUMN).
  - **frontend (Phase A)**: Product detail 에 토글 1 row 추가 ("신규 역할 자동 접근"). `merged.default_role_access` + `setProductMetaPending` + `applyAllPending` 의 productMeta PATCH body + `describePatchKeys` 라벨. Role detail 의 토글은 제거 (이전 시도 잔재 — mergedRole/setRolePending/applyAllPending/startNewRole 모두 정정).
  - **frontend (Phase B)**: `groupedPermissions(opts={excludeDynamic})` + `dynamicProductPermissions()` 헬퍼 신설. `renderPermissionGrid` 가 옵션 통과. Role detail 과 Account detail 의 grid 호출이 `excludeDynamic: true` 로 dynamic `product.access.*` 분리. onChange 핸들러는 dynamic 권한들 union 으로 보존.
  - **frontend (Phase C)**: `buildRoleProductCardList(role, disabled)` 신설 — product 별 collapsible card 안에 access 토글 + role-scope system prompt textarea (fixedProductId=Number(id)) 묶음. "전 Product 공통" generic card (fixedProductId=0) 마지막에. `buildAccountProductOverrideList(account, disabled)` 신설 — product 별 flat card 에 override select. Role detail 의 단일 buildSystemPromptEditor 호출은 product 카드의 textarea 로 흡수.
  - **styles.css**: `.admin-product-card-list` / `.admin-product-card` (open 상태 / head / toggle / info / body / flat / generic) 스타일 추가. 토큰 사용.
  - **admin.html**: cache-bust `v=20260506-c5-product-cards`.
  - **검증**: py_compile + node check + make web 재배포. Schema (`DESC WebProducts` 에 DefaultRoleAccess 추가) + role API 에서 default_product_access 제거 + /api/admin/products 에 default_role_access 노출 확인. **Phase A E2E smoke**: 신규 product DE (`default_role_access=false`) → 6 role 모두 grant 0, JP (`=true`) → 6 role 모두 grant. **Phase B/C DOM smoke** (browse): admin-product-card 정상 카운트, 권한 grid 에서 dynamic 코드 제외 확인.
  - **다음 단계**: 운영자 검토 — product 생성 시 토글로 정책 결정. 기존 product 의 정책 변경은 PATCH /api/admin/products 의 default_role_access 변경 (단, 기존 grant 는 보존). `WebRoles.DefaultProductAccess` 컬럼 잔재는 다음 cleanup cycle 에서 DROP COLUMN.

- 2026-05-06 (TASK-0052 Phase 1B/1C/1D + Phase 2, REQ-20260506-0005, CHG-20260506-0026, REV-20260506-0013)
  - **backend (Phase 1B)**: `unit/feature-0003-agent-web-ui/src/app.py` — `_resolve_permission_catalog(conn=None)` body 를 DB-driven 으로 교체 (정적 + WebPermissions IsDynamic=1 union, graceful fallback). `_product_permission_code` / `_ensure_dynamic_permissions_schema` / `_ensure_product_access_permissions` 헬퍼 신설. bootstrap (slow + fast path) 에서 자동 backfill. caller 7 곳 (account list / role survivor / admin update / list_roles / load_role_by_id / role create / role update) update.
  - **backend (Phase 1B 트랜잭션, Codex Claim 2)**: `POST /api/admin/products` 와 `DELETE /api/admin/products/{id}` 가 `conn.autocommit=False` + 명시적 commit/rollback. POST 는 product+permission row+role grant 한 트랜잭션, DELETE 는 cascade (SystemPrompts/ProductDatabases/RolePermissions/AccountPermissionOverrides/Permissions/Products) 한 트랜잭션.
  - **backend (Phase 1C, G1-G8 8 가드)**: `_account_has_product_access(account, product_id_or_key, *, conn=None)` 단일 진입점. G1 PATCH conv product / G2 new_conversation / G3 ask body hint / G4 ask 기존 conv product_id_for_run (Codex Claim 3 핵심) / G5 fork + product_mode 'auto' 보존 fix (Codex Claim 4) / G6 _save_account_product_pref defense-in-depth / G7 GET sysprompt / G8 PUT sysprompt — 권한 없으면 403.
  - **backend pre-existing 버그 fix**: `admin_update_account` 가 `target.get("role")` (항상 None) 으로 fallback 해 PATCH 마다 RoleId=0 으로 덮어쓰던 회귀를 `target.get("role_id")` 직접 조회로 fix. body 에 role_id 미명시인 PATCH 가 더 이상 admin role 손상 안 함.
  - **frontend (Phase 1D)**: `unit/feature-0003-agent-web-ui/src/static/admin.js` — `PERMISSION_GROUP_ORDER += "product"`, `PERMISSION_GROUP_LABELS["product"] = "제품"`. 기존 renderPermissionGrid 가 자동으로 'product' 그룹 (정적 product.manage / system_prompt.manage.role.any + 동적 product.access.<key>) 노출.
  - **markup**: `unit/feature-0003-agent-web-ui/src/static/admin.html` cache-bust `v=20260506-c5-product-perms`.
  - **운영 transparency**: bootstrap stderr `[TASK-0052 Phase 1B catchup] product access backfill: 7 permission/role-permission rows added` 메시지 (1 perm row + 6 role grants — 모든 6 role 에 KR access 자동 grant, D2-A 호환성 우선).
  - **검증 (Phase 2 P0)**: (a) `python3 -m py_compile` PASS / `node --check admin.js` PASS / `make web` 재배포. (b) `/api/admin/permissions` count 33 → 34 (KR 추가) → POST FR 후 35 → DELETE FR 후 34 복귀. (c) admin effective `product.access.kr=True` (D2-A backfill). (d) deny override 후 G1/G2/G7/G8 모두 HTTP 403. (e) cleanup 후 admin 34/34 회복. (f) admin_update_account RoleId 보존 fix 검증: PATCH override 후 role 'admin' 보존, 33/34 true. G3/G4 는 model validation 단계 차단으로 정적 코드 검증으로 대체 (G1/G2 와 동일 패턴).
  - **NOT in scope (별 cycle)**: Phase 2 P2 (`/api/sessions/me` filter, end-user FE chip filter), F8 (admin lockout 보호 survivor 로직 확장).
  - **다음 단계**: 운영자 검토 — D2-A 호환성 backfill 로 모든 role 이 KR 에 default-grant 상태. 권한 회수가 필요한 (role × product) 조합은 admin 콘솔의 deny override 로 적용 (`PATCH /api/admin/accounts/{id}` body `{"permission_overrides":{"product.access.kr":"deny"}}` 또는 admin UI 의 권한 grid).

- 2026-05-06 (TASK-0052 Phase 1A, REQ-20260506-0005, CHG-20260506-0025, REV-20260506-0012)
  - **backend (RBAC engine refactor)**: `unit/feature-0003-agent-web-ui/src/app.py` — `Iterable` import 추가, 신규 `_resolve_permission_catalog(conn=None)` 헬퍼 (Phase 1A 시점은 정적 `(PERMISSION_DEFINITIONS, PERMISSION_CODES, PERMISSION_DEFINITION_MAP)` 반환, Phase 1B 가 conn 으로 WebPermissions union), 5 함수 시그니처 확장 (`_empty_permission_map`/`_apply_permission_overrides`/`_validate_permission_codes`/`_normalize_override_payload`/`_permission_catalog_payload` 모두 catalog kwarg 추가, default None = 기존 정적 사용 → 회귀 0).
  - **plumbing 검증 endpoint**: `/api/admin/permissions` (L5761) 만 신규 경로 (`_resolve_permission_catalog(conn) → _permission_catalog_payload(catalog=...)`) 로 전환. Phase 1B 의 DB-driven 전환 surface 를 미리 검증. 다른 callsite (account list / role detail 의 `_apply_permission_overrides` 등) 는 Phase 1B 에서 caller-update.
  - **검증**: (a) `python3 -m py_compile` 통과. (b) `make web` 재배포 (`repo-web-1 Recreated/Started`). (c) `docker exec repo-web-1 grep -c "_resolve_permission_catalog\|catalog_codes" /app/web/app.py` → 17 hits. (d) bootstrap_admin login + `/api/admin/permissions` HTTP 200 + count=33 codes (이전과 정확히 동일, 첫 3 `console.access`/`console.manage`/`account.read`, 마지막 3 `conversation.finalize.any`/`product.manage`/`system_prompt.manage.role.any`).
  - **Plan 정본**: [BRIEFING-c5-permission-product-access.md](./BRIEFING-c5-permission-product-access.md). Phase 1A 는 briefing §4 의 1A 항목 ✓.
  - **다음 단계**: Phase 1B (WebPermissions IsDynamic/ProductId 컬럼 + 제품 권한 backfill SQL + `_resolve_permission_catalog(conn)` body 를 DB query 로 교체 + 다른 callsite caller-update). 별 cycle 진입 권장.

- 2026-05-06 Git 동기화 결과 (commit 85f674d)
  - 커밋: `85f674d` (`feat/adopt-external-anchor-v3.2.0-rc`) — TASK-0048/0049/0050/0051 + 정책 변경 흡수 + verify-completion §4 strip fix 32 files / +2493 / -295.
  - verify-completion: PASS (pre + post-commit 모두 6/6)
  - Push: 완료 — `git push origin feat/adopt-external-anchor-v3.2.0-rc` 정상 (`a7122f8..85f674d`)
  - PR: 보류 — 현재 브랜치 `feat/adopt-external-anchor-v3.2.0-rc` 는 internal feat/* 형식이라 `docs/GITHUB_AUTOMATION.md` 의 공개 PR 브랜치 규칙(`issue/<번호>-<short-slug>`) 에 부합하지 않고 GitHub issue 가 본 cycle 에 묶이지 않았다. 사용자가 이미 origin 에 같은 이름으로 작업 중인 internal develop 브랜치라 push 만 진행. PR 전환은 별도 issue 발급 + `issue/*` 통합 시 진행.
  - 병합 상태: 수동 검토 — internal feat/* 브랜치이므로 자동 merge 후보 아님.
  - 충돌 해결: 없음.

- 2026-05-06 (TASK-0048 후속 fix, CHG-20260506-0024)
  - **버그 보고**: 사용자 보고 — "대화 삭제 시 새 대화가 그대로 남는 이슈". 사용자가 active 대화를 삭제했는데 사이드바에 또 빈 대화가 등장.
  - **근본 원인**: backend `_repair_current_conversation` 의 호출처 5 곳이 `create_if_missing=_account_has_permission(account, "conversation.create")` 로 자동 생성하던 분기. 특히 `/api/delete_conversation` 응답의 `current` 필드가 자동 생성된 새 cid 였고 frontend 가 그것을 active 로 채택해 사이드바에 다시 등장. 또 `_build_conversations_payload` (`/api/conversations`), `/api/session`, `/api/history` 의 conv resolver 도 동일하게 자동 생성 중이라 사용자가 어떤 경로로 list 를 fetch 해도 빈 대화가 자동으로 나타날 수 있었다 — TASK-0048 의 lazy 정책을 backend 가 우회하던 회귀.
  - **fix**: 호출처 5 곳을 `create_if_missing=False` 로 일괄 전환 (`/api/ask` 의 lazy creation 단일 경로만 `True` 보존). lazy 정책을 backend 전 경로에 일관 적용.
  - **검증**: HTTP API 시나리오 (a) `/api/conversations` 호출 시 row delta=0, (b) `/api/session` 호출 시 delta=0, (c) `/api/new_conversation` 으로 빈 대화 1건 생성 후 즉시 `/api/delete_conversation` → 응답 `{"deleted":"...","current":""}`, row delta=-1 (이전엔 자동 생성된 새 cid 가 current 에 들어와서 net delta=0 으로 빈 대화가 또 생기던 것). frontend 는 current="" 를 받으면 헤더 "대화를 선택하세요" + 사이드바 empty-state 로 떨어진다.
  - **회귀 표면**: 마지막 대화를 삭제한 사용자에게 backend 가 자동으로 새 대화를 만들어주지 않는다 — 의도된 결과. 사용자가 "새 대화" 버튼을 명시적으로 눌러야 한다 (TASK-0048 lazy 정책의 일관성).

- 2026-05-06 (TASK-0051, REQ-20260506-0004, CHG-20260506-0023, REV-20260506-0011)
  - **frontend (admin)**: `unit/feature-0003-agent-web-ui/src/static/admin.js` — `adminState.pending` 에 `productMeta` / `productDatabases` / `systemPrompts` 3 buckets 추가 + `availableDatabases` 캐시 추가. `setProductMetaPending` / `setProductDatabasesPending` / `setSystemPromptPending` / `getSystemPromptPending` 헬퍼 신설. `pendingChangeCount` / `refreshPendingUI` / `cancelAllPending` / `loadAdminData` 가 신규 buckets 합산·표시·clear·GC 흐름에 합류. `applyAllPending` 6 단계로 확장 (productMeta PATCH → productDatabases PUT → systemPrompts PUT 3 단계 추가).
  - **frontend (admin) — 인라인 save 제거**: `renderProductDetail` 의 `saveMetaBtn` (제품 정보 저장) / `saveDbBtn` (DB 목록 저장) 두 버튼 제거. `buildSystemPromptEditor` 의 `saveBtn` (프롬프트 저장) / `clearBtn` (비우기) 두 버튼 제거. 모두 입력 변경 시 즉시 pending 등록 + footer "모두 적용" 단일 commit 흐름에 통합.
  - **frontend (admin) — 메타데이터 locked chip + DB picker**: 제품 detail 의 chip wrap 에 메타 4 종(`information_schema`/`mysql`/`sys`/`performance_schema`) 을 `is-locked` 클래스 + `항상 접근` 소형 라벨 + tooltip 으로 강제 prepend (× 버튼 없음). 자유 텍스트 chip 입력을 `<select>` picker (loadAdminData 시점의 user_schemas 스냅샷 + 메타·`agent_memory`·이미 등록된 schema 제외) 로 교체.
  - **frontend (admin) — system prompt textarea pending**: 안내 한 줄 ("변경사항은 하단 '모두 적용' 버튼으로 일괄 저장됩니다") 추가. textarea `input` 이벤트 → `setSystemPromptPending`. `refresh()` 가 pending entry 우선으로 textarea 값 복원해 reload race 방지.
  - **frontend (admin) — dashboard pending**: `dashboardPendingList` 에 "제품 정보" / "제품 DB" / "프롬프트 (제품/역할/계정)" 3 카테고리 row 추가. `describePatchKeys` 에 `is_default`/`sort_order` 라벨 추가.
  - **backend**: `unit/feature-0003-agent-web-ui/src/app.py` 신규 `GET /api/admin/databases/available` 엔드포인트. `console.access` 게이트 후 `_open_memory_connection(database=None)` 으로 `SHOW DATABASES` 실행, `metadata_schemas`(고정 4 종 + `present` flag) / `user_schemas`(메타·`agent_memory`·`MEMORY_DB`·정규식 위반 제외 + 정렬) 분리 반환. 모듈 상수 `_DATABASES_AVAILABLE_METADATA` / `_DATABASES_AVAILABLE_INTERNAL` / `_DATABASES_AVAILABLE_NAME_RE` 추가.
  - **markup/style**: `admin.html` cache-bust `v=20260506-batch-commit` (styles.css, admin.js). `styles.css` 에 `.admin-chip.is-locked`, `.admin-chip-locked-hint`, `.admin-db-picker-row`, `.admin-db-picker` (+ disabled 상태) 추가. 토큰(`--text-muted`/`--border-subtle`) 만 사용.
  - **검증**: (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` 통과. (b) `node --check unit/feature-0003-agent-web-ui/src/static/admin.js` 통과. (c) `grep` 으로 3 개 인라인 save 버튼 라벨/핸들러 변수 모두 admin.js 에서 0 hit. (d) `/api/admin/databases/available` 가 FE/BE 양쪽 1 hit. **컨테이너 재빌드(`make web`) + 브라우저 UX smoke 는 사용자 환경에서 진행 예정** (재빌드 후 cache-bust 가 반영되어야 신규 admin.js 가 로드됨).
  - **C5 분리**: 계정·역할 → 제품 권한 상속/override 모델은 다음 cycle 분리. 사유: 신규 테이블 2 개(`WebRoleProductAccess`/`WebAccountProductAccessOverrides`) + 기존 RBAC override 모델(TASK-0024) 우선순위 합성 정의 + `compose_system_prompt` product 조회 경로 영향 분석이 필요. 진입 전 `/plan-eng-review` 권고.


- 2026-05-06 (TASK-0050, REQ-20260506-0003, CHG-20260506-0022)
  - **build infra**: `repo/Makefile` — `dc-build SERVICE=...` reusable 가드 타깃 추가 + `web` 타깃을 `dc-build SERVICE=web` + `up -d --no-build web` 2단계로 분리. docker compose v5.1.1 + buildx v0.31.1 의 provenance metadata file race 를 흡수 (image 빌드는 정상 + 로그에 `compose-build-metadataFile` 포함될 때만 EXIT=0 정규화).
  - **검증**: `make web` EXIT=0, `[make] note: ...provenance metadata file race 우회...` 메시지, `Container repo-web-1 Recreate/Recreated/Started`, `Web UI (HTTPS)` 노출 + 새 코드 deploy 확인.

- 2026-05-06 (TASK-0049, REQ-20260506-0002, CHG-20260506-0021)
  - **cleanup**: `repo/bin/cleanup-empty-conversations.sh` 추가 (executable). dry-run 기본 + `--execute` 명시 시 DELETE, processing 보호 + 최근 N분 보호 + owner-account 옵션. SQL 주입 방지 정수 정규식 검증.
  - **운영 적용**: dry-run 으로 `would_delete=42` 확인 후 `--execute` 로 정리. 결과: 88 conversations / 42 empty / 46 non-empty → 46 conversations / 0 empty / 46 non-empty.
  - **idempotent**: 향후 재실행 시 추가 누적이 없으면 0 건 정리됨 (TASK-0048 이 신규 누적을 차단하므로).

- 2026-05-06 (TASK-0048, REQ-20260506-0001, CHG-20260506-0020, REV-20260506-0010)
  - **frontend**: `unit/feature-0003-agent-web-ui/src/static/app.js` — `state.pendingNewConversation` + `PENDING_CONV_SENTINEL` 도입, `beginPendingConversation()` 신설, `renderConversationList()` 가 pending placeholder 를 "내 대화" 그룹 상단에 prepend, `renderConversationHeader()` 가 pending 시 "새 대화" + 부제 표시, `selectConversation()` 이 pending 자동 종료, `sendPrompt()` 의 lazy create 분기가 `/api/ask` body 에 `product_mode`/`product_id` hint 첨부, 응답 `conversation_id` 채택 후 pending 종료, lazy create 단계 ask 실패는 attach 다이얼로그 대신 재시도 토스트. `newConversationBtn.click` 핸들러를 `createConversation()` → `beginPendingConversation()` 로 교체.
  - **backend**: `unit/feature-0003-agent-web-ui/src/app.py` `/api/ask` 의 lazy creation 분기 (`request_conversation_id` 비어 있을 때) 에 body `product_mode`/`product_id` hint 수용 + `AgentCoreConversations.product_id/product_mode` 셋업 + `_save_account_product_pref` 호출. 기존 대화 경로(`request_conversation_id` 명시) 는 hint 무시 — `PATCH /api/conversations/{cid}/product` race 가드 단독 진실 보존. hint 적용 실패는 ask 자체를 막지 않고 default fallback.
  - **markup/style**: `index.html` cache-bust `v=20260506-pending-conv` (styles.css, app.js). `styles.css` 에 `.conv-item.is-pending` 1 selector 그룹 추가 (border-dashed + faded text + cursor:default, 토큰만 사용).
  - **검증**: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`, `node --check unit/feature-0003-agent-web-ui/src/static/app.js` (재빌드 단계).
  - **후속 처리 완료** (TASK-0049, TASK-0050 으로 분리 마감):
    - 누적된 빈 대화 일괄 정리: TASK-0049 로 진행 (88→46, 42 정리). `bin/cleanup-empty-conversations.sh` 가 영구 도구로 남음 (idempotent — 신규 누적 없으면 0건).
    - `make web` 운영 검증 차단 이슈: TASK-0050 의 Makefile dc-build 가드로 해결. 본 cycle 에서 새 코드를 운영 컨테이너에 deploy 검증.
  - **남은 후속 작업**:
    - lazy create 단계 ask 실패 시 buried orphan (backend cid 발급 후 client 모름) 케이스를 자동 회수하는 경로는 본 turn 에 의도적 미구현 — 사용자에게 사이드바 새로고침으로 위임. 향후 attach API 를 cid 없이 trigger 할 수 있도록 확장 시 검토.
    - frontend 시각 검증 (§8.2 강제 검증): Playwright spec 또는 dogfooding 으로 (1) 새 대화 버튼 클릭 → 사이드바 placeholder 등장 + network round trip 0회 확인, (2) 첫 메시지 전송 → cid 채택 + product hint backend 반영 확인, (3) pending 상태에서 다른 대화 선택 → placeholder 사라짐, (4) pending ask 실패 시 토스트 안내. **API key 환경 + 브라우저 접근이 필요해 본 turn 의 코드 inspection + 컨테이너 deploy 검증 후 사용자 dogfooding 으로 위임.**

- 2026-04-30 (TASK-0047 후속 검증, CHG-20260430-0019, REV-20260430-0009)
  - **버그 수정**: `_runtime_tables_available` 가 테이블만 검사하던 fast-path 에 신규 컬럼(`product_mode`/`ProductPrefMode`/`ProductPrefPinnedId`) probe 와 errno 1054 분기를 추가해, 기존 배포에서 신규 컬럼 마이그레이션이 자동 트리거되도록 했다 (BRIEFING R-09 closed).
  - **Playwright QA 28-check** 작성 및 실행 — `repo/.gstack/qa-reports/qa-product-selector.cjs`. 결과: 28/28 PASS, healthScore=100, console.error=0. PATCH 4 케이스 / new_conversation 2 케이스 / UI select 인터랙션 / hydrate / **PATCH race guard (last_status='processing' → 409)** 모두 자동 검증.
  - 빌드 학습: `docker compose --build` 가 BuildKit layer cache 로 `COPY src/...` 단계를 stale 하게 잡는 케이스를 만나 `docker compose build --no-cache web` 으로 강제 재빌드. LEARNINGS 후보.

- 2026-04-29 (TASK-0047, agent team 4 합의 + Codex CLI 교차검증)
  - `unit/feature-0002-agent-core/src/agent_core.py` — `compose_system_prompt(... ,product_mode='pinned'|'auto')` 분기 추가 (auto 시 `[AUTO MODE]` 한 줄 inject + product 한정 prompt 건너뜀, role/account scope 는 `ProductId IS NULL` fallback 만 사용). `run_agent`/`_run_agent_core` 시그니처에 `product_mode` 전달.
  - `unit/feature-0003-agent-web-ui/src/app.py` — DDL 2 컬럼(AgentCoreConversations.product_mode, WebAccounts.ProductPrefMode/ProductPrefPinnedId), 헬퍼 5종(`_normalize_product_mode`, `_load_account_product_pref`, `_save_account_product_pref`, `_load_conversation_product`, `_conversation_is_processing`), `/api/session` 응답 확장(`product_pref`, `conversation_product`), `/api/new_conversation` body 확장(`mode`, pref upsert), `/api/ask` 분기(mode='auto' → product_id None + allowed_schemas=[]), 신규 `PATCH /api/conversations/{cid}/product` (권한·소유자·race 가드).
  - `unit/feature-0003-agent-web-ui/src/static/index.html` — 사이드바 헤더에 product chip 추가, cache-bust `?v=20260429-product-selector`.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` — `.product-chip*` 스타일 신설(70 줄), mobile ≤720px 분기.
  - `unit/feature-0003-agent-web-ui/src/static/app.js` — state 3-필드 분리, `renderProductOptions`/`renderProductChip`/`applyProductHydration`/`setActiveProduct`/localStorage 헬퍼 6종 신규, `initializeWorkspace`/`refreshWorkspace`/`selectConversation`/`createConversation`/`renderComposer`/`initialize` 흐름에 hydrate + lockout + select change 바인딩 추가.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`, `admin.js`, `unit/feature-0003-agent-web-ui/src/app.py` — "상품" → "제품" 일괄 치환 (코드 식별자 보존).
  - 문서: `docs/TASK.md` §2/§3.1 갱신, `docs/MODIFY.md` CHG-20260429-0018, `docs/REVIEW.md` REV-20260429-0008, `docs/REPORT.md` (this), 신규 `docs/BRIEFING-product-selector-v1.md` (R-01..R-16 + D-01..D-05).
  - 검증: `python3 -m py_compile` (app.py / agent_core.py), `node --check src/static/app.js` 모두 통과. in-process `compose_system_prompt` auto 분기 테스트 통과.

- 2026-04-25 (TASK-0046, REQ-20260425-0001)
  - `src/static/index.html`
    - L246-L334 vault 패널 markup 재구성: `vault-banner` (readiness tri-state) + `ol.vault-stepper > li.vault-step × 3` (Step 1 사용할 API 키 / Step 2 passphrase / Step 3 암호화 후 저장) + `vault-saved` (information only) + `vault-danger-zone` ("저장된 키 삭제" 1 개) + `details.vault-advanced` (cipher 직접 붙여넣기, 기본 접힘). cache-bust `v=20260425-vault-final`.
  - `src/static/styles.css`
    - L1420-L1582 신규 클래스: `.vault-banner` / `.vault-banner-dot[data-state]` / `.vault-stepper` / `.vault-step[data-state="active|done|disabled"]` / `.vault-step-num` / `.vault-step-head/title/body/hint` / `.vault-saved` / `.vault-danger-zone` / `.btn-danger-link` / `.vault-advanced[-body]` (약 170 줄).
  - `src/static/app.js`
    - vault state helper 군 재작성: `updateVaultStatus` → `updateVaultReadiness` rename + `computeVaultReadiness` 의 진실 출처를 input value 에서 storage 로 통일. `syncVaultSteps` 가 `cipherSaved` 만으로 saved-default ↔ wizard 입력 모드 전환. `renderVaultSavedCard` 가 saved card + danger zone 동시 hidden 토글. saveVault 흐름이 평문 → encrypt → cipher 채움 → localStorage 저장 한 줄로 통합. `clearVaultBtn` 핸들러에 `confirm("저장된 암호화 키를 삭제할까요? ...")` 가드 추가.  신규 `vaultImportCipherBtn` 핸들러로 `v1:` prefix 검증 후 ciphertext 직접 import. **단일 진입점 정책**: `vaultReplaceBtn` / `replacingVault` flag / `enterReplaceMode` / `cancelReplaceMode` 모두 제거 — 키 갈아끼움 경로 1 개만 유지.
  - 검증: `repo/.gstack/qa-reports/qa-vault.cjs` (Playwright Node) 28/28 PASS, healthScore 100, console.error 0 건. 사용자 직접 브라우저 검증 4 시나리오(저장 완료 / 새로고침 / 삭제 후 새 키 입력 / confirm 취소) 모두 만족.
  - 문서: `docs/TASK.md` §1/§2 갱신, `docs/MODIFY.md` CHG-20260425-0017, `docs/REPORT.md` (this), `docs/REQUEST.md` (REQ-20260425-0001 Outcome) → `docs/REQUEST_ARCHIVE.md` move.

- 2026-04-22 (TASK-0041)
  - `src/app.py`
    - `_ASK_TERMINAL_STATUSES = frozenset({"done","error","canceled"})` / `_ASK_SUCCESS_STATUSES = frozenset({"done","canceled"})` 상수
    - `_load_run_meta_kv(conn, cid)` — `AgentMemoryKv` 의 5 키(`last_status` · `last_status_at` · `last_status_run_id` · `last_duration_ms` · `last_error`) 를 단일 쿼리로 조회
    - `_build_ask_status_snapshot(conn, cid)` — `{conversation_id, is_processing, status, status_at, run_id, step_count, duration_ms, error, has_answer, answer_preview, _latest_assistant}` 스냅샷 빌더
    - `GET /api/ask_status` — 1-shot. 권한 `conversation.read.own/any`. 응답은 `_latest_assistant` 제외(long-poll 전용)
    - `GET /api/ask_result?conversation_id=&run_id=&wait=<=60` — long-poll. `deadline=loop.time()+wait_s`, `poll_interval=0.5`. terminal 시 assistant dict 반환, 시간 초과 시 `{timeout:true, run_id?}`. `/api/ask` 슬롯풀(WEB_PARALLEL_LIMIT=6) 과 분리되어 attach 가 새 실행을 시작시키지 않는다.
  - `src/static/app.js`
    - 상수 `ASK_ATTACH_POLL_WAIT_SEC=45` / `ASK_ATTACH_MAX_TOTAL_SEC=1800`
    - `fetchAskStatus(cid)` — 실패 시 null 반환하는 안전 래퍼
    - `showTimeoutRecoveryDialog({statusText})` — 3 버튼 모달(`요청 취소`/`즉시 답변`/`계속 기다리기`) + Escape dismiss. 인라인 스타일로만 구성되어 HTML/CSS 변경 없이 동작
    - `attachAndWaitForResult(cid, {runId})` — `/api/ask_result?wait=45` long-poll 루프, run_id 한 번 고정, terminal 시 `refreshWorkspace(cid)` + 토스트. 최대 1800s
    - `sendPrompt()` — `apiFetch("/api/ask",...)` 를 try/catch 로 감싸 실패 시 `fetchAskStatus` → `is_processing=true` 이면 다이얼로그 → 사용자 선택에 따라 `/api/cancel`·`/api/finalize` 호출 후 `attachAndWaitForResult` 로 이어받음
    - `initializeWorkspace()` 끝에 boot-time auto-attach — 페이지 로드 시 현재 대화가 `is_processing=true` 이면 자동으로 busy 상태 + progress polling + attach 재개, "이전에 남아있던 응답 요청을 이어받습니다." 토스트
  - `tests/task0034_runner.py`
    - 상수 `ATTACH_TIMEOUT_SEC=960.0` / `ATTACH_POLL_WAIT_SEC=45`
    - `_steps_from_attach(meta)` 헬퍼
    - `_attach_run(client, cid, message, t0)` — ask_status 로 run_id/initial_status 확보 → ask_result long-poll 반복 → turn dict 에 `attached_after_timeout=True` + `attach_verdict` + `attach_run_id`/`attach_initial_status` 메타 기록
    - 기존 `httpx.ReadTimeout` 분기: `{"error":"client-read-timeout"}` 반환 대신 `_attach_run(...)` 로 정상 복구
  - 검증: py_compile 3 파일 통과, `node --check app.js` JS OK, `make web` 재빌드 후 새 이미지(sha256:665515...) 반영, `/api/ask_status` / `/api/ask_result` 401 응답으로 라우팅 확인, terminal 상태 스냅샷 38ms, `python3 tests/task0034_runner.py --target api --only Q4,Q5` 재수행 실행
  - 문서: `docs/TASK.md` §1/§2 + TASK-0041 상세 설계 블록(1236 라인대) + Completion Checklist 체크, `docs/MODIFY.md` CHG-20260422-0014, `docs/REVIEW.md` REV-20260422-0007, `docs/FUNCTION.md` 에 신규 2 엔드포인트, `../../docs/LEARNINGS.md` LRN-20260422-0013(작업자 스레드 lifecycle ≠ 클라이언트 연결)

- 2026-04-22 (TASK-0040)
  - `../feature-0002-agent-core/src/modules/tools.py`
    - `_SCHEMA_TABLE_REF_RE` 단일 단계 regex 를 제거하고 `_TABLE_LIST_RE` + `_INNER_REF_RE` 2 단계 스캐너로 교체.
      - 1 단계: `\b(?:FROM|JOIN)\b(.*?)(?=\bON\b|\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bHAVING\b|\bLIMIT\b|\bUNION\b|\bJOIN\b|\bFROM\b|;|\)|$)` (IGNORECASE|DOTALL) — FROM/JOIN 키워드 다음 절 시작 직전까지의 테이블 리스트 구간만 slice
      - 2 단계: slice 내부에서만 `\`?(schema)\`?\s*\.\s*\`?(table)\`?` 패턴으로 schema 토큰 추출
    - SELECT/WHERE/ON 절의 alias.column 토큰은 FROM/JOIN slice 바깥이라 더 이상 매칭되지 않는다.
  - 검증: in-process 15 테스트 케이스 (단일 FROM / FROM+WHERE alias.col / FROM+JOIN+alias.col ON / 혼합 schema / 백틱 / subquery / 비허용 schema 차단 / SELECT 절 alias.col 무시 / semicolon terminator / UNION 경계 / whitespace DOTALL / 중복 refs dedup) 전부 expected refs 일치. Q4-like SQL 은 `{dblog}` 만 검출, `_whitelist_violation` 이 `{dbauth,dbgame,dblog}` whitelist 에서 None 반환. 비허용 `dbstat.foo` 는 여전히 차단.
  - 문서: `docs/TASK.md` §1/§2 + TASK-0040 상세 설계 블록 + Completion Checklist 체크, `docs/MODIFY.md` CHG-20260422-0013, `docs/REVIEW.md` REV-20260422-0007(TASK-0040/0041 통합), `../../docs/LEARNINGS.md` LRN-20260422-0012(SQL 정규식 문맥 의존성)

- 2026-04-22 (TASK-0039)
  - `../feature-0002-agent-core/src/modules/tools.py`
    - L24~33 `_SYSTEM_SCHEMAS` 단일 frozenset 을 `_METADATA_SCHEMAS = {information_schema, sys, mysql, performance_schema}` (whitelist bypass) + `_INTERNAL_SCHEMAS = {agent_memory}` (whitelist 차단 유지) 두 frozenset 으로 분리. `_SYSTEM_SCHEMAS` 는 union 으로 유지해 `_is_user_schema`/`search_tables` UX 필터 동작 보존.
    - L81~103 `_whitelist_violation` 의 `allowed = set(_ACTIVE_SCHEMA_ALLOWLIST) | {"information_schema"}` 를 `_METADATA_SCHEMAS` 전체로 확장. 차단 에러 메시지에 "메타데이터 스키마(information_schema/sys/mysql/performance_schema) 는 항상 접근 가능" 안내를 추가.
  - 검증: 컨테이너 in-process 8 케이스(whitelist=None / 메타데이터 4 종 bypass / 허용 user schema / 혼합 통과 / agent_memory 차단 / 비허용 user schema 차단 / `_is_user_schema` UX 필터 보존) + `execute_tool` 경로로 information_schema / performance_schema / sys / mysql / agent_memory / 비허용 user schema 각 케이스 기대 동작 확인. `mysql.user` tool-level bypass 후 실제 행 반환(MySQL GRANT 열림) → REV-20260422-0006 에 2 차 방어 필요성 기록.
  - 문서: `docs/TASK.md` §1/§2/§3.1 + TASK-0039 상세 설계, `docs/MODIFY.md` CHG-20260422-0012, `docs/REVIEW.md` REV-20260422-0006 (REV-20260421-0005 일부 supersede), `docs/FUNCTION.md` AC-0010 보강.

- 2026-04-22 (TASK-0038)
  - `../feature-0002-agent-core/src/agent_core.py`
    - L26~32 `from modules.config import` 에 `AGENT_OPENAI_MAX_RETRIES` 추가
    - L1134~1139 `client = OpenAI(**client_kwargs)` → `OpenAI(**client_kwargs, timeout=max(5,int(AGENT_TIMEOUT_SEC)), max_retries=max(0,int(AGENT_OPENAI_MAX_RETRIES)))` 로 확장. OpenAI SDK client-level timeout 이 내부 httpx 에 상속돼 `chat.completions.create` 모든 호출에 wall-clock 상한이 걸린다.
  - `tests/task0034_runner.py`
    - L52~56 `ASK_TIMEOUT_SEC=600.0` → `ASK_TIMEOUT_SEC=960.0` 및 산정 근거 주석(`max(AGENT_TIMEOUT_SEC*3, AGENT_EARLY_FINALIZE_MS/1000)=900s` + 60s buffer) 추가. 서버가 항상 클라이언트보다 먼저 자기-타임아웃을 친다.
  - 검증: `docker compose up -d --force-recreate web` 후 bootstrap_admin 로그인 + `gpt-5.4-mini` 간단 질의 `/api/ask` HTTP 200, wall=5s, steps=1, list_schemas 정상.

- 2026-04-22 (TASK-0037, 문서화 전용)
  - `/api/progress` 폴링 루프 리팩터(27127b9, TASK-0036 번들) 에 대한 사후 리뷰 및 학습 기록. 코드 변경 없음.
  - 검증: `grep -c "setInterval" src/static/app.js` = 0, 5개 적응형 상수(`PROGRESS_FETCH_TIMEOUT_MS=4000` / `PROGRESS_POLL_ACTIVE_MS=1200` / `PROGRESS_POLL_IDLE_MS=3000` / `PROGRESS_POLL_HIDDEN_MS=10000` / `PROGRESS_POLL_ERROR_MS=8000`) 모두 `scheduleProgressPolling`/`pollProgress` 에서 실제 참조, 서버 `/api/progress` (app.py:4381~4426) 가 `client_run_id` 파라미터를 수용하고 서버 최신 run_id 와 불일치 시 `next_after_step=0` 으로 리셋(app.py:4405-4406).
  - 문서: `docs/TASK.md` §2/§3.1 + TASK-0037 상세 설계 블록, `docs/MODIFY.md` CHG-20260422-0010, `docs/LEARNINGS.md` LRN-20260422-0011(장시간 작업 폴링 5원칙).

- 2026-04-21 (TASK-0036)
  - `../feature-0002-agent-core/src/agent_core.py`
    - `compose_system_prompt(mem_conn, *, product_id, role_id, account_id)` 신규. `WebSystemPrompts` 에서 scope=product → role → account 순으로 조회해 base `SYSTEM_PROMPT` 뒤에 `## PRODUCT CONTEXT ({ProductKey})` / `## ROLE GUIDANCE ({RoleKey})` / `## ACCOUNT PREFERENCES` 블록을 append. role/account 는 `ProductId=X` 우선, 없으면 `ProductId IS NULL` fallback
    - `run_agent(...)` 는 `allowed_schemas` + `product_id`/`role_id`/`account_id` kwargs 를 받는 얇은 래퍼로 재구성, 본문은 `_run_agent_core` 로 rename. try/finally 로 `set_active_schema_allowlist`/`clear_active_schema_allowlist` 세팅/복원
  - `../feature-0002-agent-core/src/modules/tools.py`
    - 모듈-전역 `_ACTIVE_SCHEMA_ALLOWLIST: set[str]|None = None` + `set_active_schema_allowlist()` / `clear_active_schema_allowlist()` / `_whitelist_violation(refs)` / `_extract_sql_schema_refs(sql)` 신규
    - 모든 DB 도구(`execute_sql`, `explain_query`, `describe_schema`, `describe_table`, `search_tables`, `get_sample_rows`, `get_table_indexes`, `get_foreign_keys`, `list_schemas`) 가 호출 직전 스키마 참조를 `_whitelist_violation` 으로 검사. `execute_sql` 은 `schema.table` 정규식 추출
    - `_is_user_schema` 에 whitelist 교집합 조건 추가 → `list_schemas` 출력 post-filter
    - 보안 수정: `_whitelist_violation` 에서 `_SYSTEM_SCHEMAS` bypass 제거. `information_schema` 만 예외(스키마 카탈로그 조회 용도)
  - `src/app.py`
    - 신규 테이블 `WebProducts` / `WebProductDatabases` / `WebSystemPrompts` CREATE (idempotent) + `AgentCoreConversations.product_id` ALTER. `_runtime_tables_available` probe list 에 신규 3 테이블 포함(기존 배포 자동 마이그레이션)
    - `PERMISSION_DEFINITIONS` 에 `product.manage` / `system_prompt.manage.role.any` 추가 및 기존 admin 역할에 보정 부여, `SEED_PRODUCT_DEFINITIONS` 로 ProductKey=`KR` + DB(`dbgame`/`dblog`/`dbauth`) seed, `_ensure_seed_products()`
    - 신규 헬퍼: `_get_default_product_id`, `_list_products`, `_product_allowed_schemas`, `_load_system_prompt`, `_upsert_system_prompt`
    - 신규 admin API: `GET/POST/PATCH/DELETE /api/admin/products`, `PUT /api/admin/products/{id}/databases`, `GET/PUT /api/admin/system-prompts`
    - 신규 self API: `GET/PUT /api/auth/me/system-prompt`
    - `/api/new_conversation`, `/api/fork_conversation` 가 `AgentCoreConversations.product_id` 를 (body.product_id → 원본 product_id → default) 순으로 해석/기록
    - `/api/ask` 가 대화 `product_id` 해석 → `_product_allowed_schemas` 로 whitelist 추출 → `run_agent(..., product_id=, role_id=, account_id=, allowed_schemas=)` 호출
    - 세션 응답(`/api/session`, `/api/auth/me`) 에 `products` / `default_product_id` 추가
  - `src/static/admin.html`
    - `계정 카테고리` / `상품 카테고리` 그룹 라벨 + 구분선 추가, 신규 `상품 (Products)` 탭 + `<section data-admin-pane="products">` 추가 (master-detail). cache-bust `v=20260421-sysprompt`
  - `src/static/admin.js`
    - `adminState.products/productSearch/selectedProductId/productDbDraft` 확장
    - `renderProductList()` / `renderProductDetail()` / `startNewProduct()` / `filteredProducts()` 신규
    - 공용 `buildSystemPromptEditor({scope, productId, roleId, accountId, fixedProductId, title, hint})` — Product scope / Role scope / Account scope 편집기 공통 렌더러
    - Role detail 에 Role scope prompt 편집기 통합 (권한 `system_prompt.manage.role.any` 게이트)
    - `loadAdminData()` 가 `/api/admin/products` 도 조회, `refreshPendingUI()` 가 `tabCountProducts` 갱신, `initialize()` 에서 productSearch/newProductBtn 이벤트 바인딩
  - `src/static/index.html`
    - 프로필 드로우 탭에 `프롬프트` 추가 + `<div data-profile-pane="prompt">` (Product 드롭다운 + textarea + 저장/초기화) 신규. cache-bust `v=20260421-sysprompt`
  - `src/static/app.js`
    - `state.products` / `state.default_product_id` 도입 및 세션 bootstrap 에 연동
    - `fetchAccountPromptRow(productId)` / `initAccountPromptEditor()` / `saveAccountPrompt(forceDelete)` 추가, profile 탭 전환 시 `prompt` 탭이 열리면 `initAccountPromptEditor()` 실행
  - `src/static/styles.css`
    - `.admin-tab-group-label`, `.admin-tab-group-divider`, `.admin-chip-wrap`, `.admin-chip`, `.admin-chip-remove`, `.admin-chip-input-row`, `.admin-prompt-textarea`, `.admin-inline-row`, `.admin-detail-hint` 추가

- 2026-04-21 (TASK-0035)
  - `src/app.py`
    - `POST /api/fork_conversation` 추가 (new_conversation 바로 아래, L3192). body: `{source_conversation_id, from_message_id?}` → 응답 `{conversation_id, source, copied, from_message_id, topic}`
    - 권한: `conversation.create` + `_account_can_access_conversation(..., read.own/read.any)`. 위반 시 403, 원본 미존재 404, 빈 body 400
    - 원본 topic (`AgentCoreConversations.topic` 우선, fallback `AgentMemoryKv.topic`) 에 `[Fork] ` 접두사 추가. `AgentMemoryMessages` 는 `(ConversationId, Role, Content, CreatedAt, MetaJson)` 을 **원본 CreatedAt 그대로** 재삽입, `MetaJson.forked_from_conversation_id` / `forked_from_message_id` 추가. `_is_internal_message` 은 skip.
    - 중간 실패 시 `delete_conversation_records(conn, new_cid)` 로 롤백
    - 성공 시 `_set_account_current_conversation` 으로 새 대화를 활성화
  - `src/static/index.html`
    - `chat-header-tools` 에 `#forkConversationBtn` ("대화 복사") 추가
    - `styles.css`, `app.js` 의 cache-bust 쿼리를 `v=20260421-fork` 로 갱신
  - `src/static/app.js`
    - `renderConversationList` 이 `state.conversations` 을 `own` / `others` 로 파티션 → `.conv-group-title` 헤더("내 대화" / "타 계정 대화 (N)") + `.conv-item.is-own` / `.is-other` / `.conv-owner-badge` 노출
    - `renderMessages` 가 대화 소유 계정 기준으로 `is-own-message` / `is-other-message` 클래스 + `나 (<username>)` / `<owner_username>` meta 라벨 적용, 각 메시지에 호버 시 노출되는 `여기서 분기` 버튼 삽입
    - 신규 `forkConversation({fromMessageId})` + `forkConversationBtn` wiring, `renderComposer` 에서 fork 버튼 가시성/disabled 제어
  - `src/static/styles.css`
    - `.conv-group-title`, `.conv-item.is-own` (primary 좌측 바 + 틴트), `.conv-item.is-other`, `.conv-owner-badge.is-own/.is-other` 추가
    - `.message.is-user.is-own-message` / `.is-other-message` 톤 분기, `.message-actions` / `.message-action-btn` (호버 시 opacity 상승 pill 액션) 추가

- (이전) RBAC cutover (CHG-20260416-0007)
  - `src/app.py`
    - `WebPermissions`, `WebRoles`, `WebRolePermissions`, `WebAccountPermissionOverrides`를 기준으로 최종 권한을 계산하도록 재구성
  - legacy `Role`/`Can*` 컬럼은 마이그레이션 원본으로만 사용하고, cutover 후 런타임 read/write 경로에서 분리
  - `GET/PATCH/DELETE /api/admin/accounts`, `GET/POST/PATCH/DELETE /api/admin/roles`, `GET /api/admin/permissions`를 새 RBAC 계약으로 재작성
  - `PATCH /api/conversations/{conversation_id}/title` 추가. 대화 조회/제목 변경/삭제/중단/즉시답변/파일 조회를 `own`/`any` 권한으로 재배선
  - `conversation.ask`는 자신의 대화 또는 새 대화에만 허용하고, 타 계정 대화 이어쓰기는 차단
  - 계정 삭제는 soft delete(`IsActive=0`, `DeletedAt`, `DeletedByAccountId`, 세션 폐기)로 고정
  - `/api/clear_memory`를 410으로 전환하고 legacy `clear conversations` 계약을 런타임에서 제거
- `src/static/index.html`, `src/static/app.js`, `src/static/styles.css`
  - 세션 payload의 role을 문자열이 아닌 `{ id, key, name }` 구조로 소비하고, 버튼 노출은 최종 permission만 기준으로 처리
  - 관리자 콘솔 버튼, rename/delete/cancel/finalize 버튼, 접근 안내 문구를 `console.access`, `conversation.*` 권한에 맞춰 재구성
  - 현재 대화가 own/others 인지에 따라 제목 변경/삭제 버튼이 반영되도록 렌더링 로직 추가
- `src/static/admin.html`, `src/static/admin.js`
  - `Accounts` 섹션에서 role 선택, 활성/비활성, soft delete, tri-state override 매트릭스를 제공
  - `Roles` 섹션에서 role 생성/수정/삭제, 기본 가입 역할 지정, permission checklist를 제공
  - `console.access`만 있는 계정도 `/admin` 셸은 열 수 있고, object read 권한이 없으면 읽기 전용 빈 상태를 표시
- 문서
  - `docs/TASK.md`, `docs/REPORT.md`, `docs/MODIFY.md`, `docs/TEST.md`를 새 RBAC 계약과 검증 결과 기준으로 갱신
  - `docs/STATUS.md`에 feature-0003 최신 갱신일과 개편 요약을 반영

## 4. Open Issues
- 없음

## 5. Notes
- legacy `Role`/`Can*` 컬럼은 DB 스키마에 남아 있지만, 현재 런타임은 새 RBAC table만 읽고 판단한다. 컬럼 drop migration은 별도 DB 정리 과제로 분리한다.

## 6. Test Status
- 코드 문법 검증: `python3 -m py_compile src/app.py`, `node --check src/static/app.js`, `node --check src/static/admin.js`
- 정적/검색 검증:
  - 휴리스틱 금지 grep: `ACCOUNT_ROLE_*`, `is_admin`, `is_pending`, `_normalize_role(...)`, legacy `can_*` 권한 판정 경로가 런타임에 남지 않았는지 확인
- TASK-0035 전용 HTTP 검증 (2026-04-21):
  - bootstrap_admin 로그인 후 `POST /api/fork_conversation {source_conversation_id: "20260421075518-571abdb6"}` → HTTP 200, `copied=6`, 새 대화 `20260421082459-c039abbd`, topic `[Fork] dblog 에서 ... `
  - 같은 계정에서 `{source_conversation_id, from_message_id: 153}` → HTTP 200, `copied=3`, 새 대화 `20260421082523-d9fbb21b`
  - 새 대화의 `/api/history` 응답에서 3개 메시지가 `meta.forked_from_message_id = 146, 152, 153` 으로 추적되는지 확인
  - 인증 없는 호출은 401, 빈 body 는 400, 존재하지 않는 source 는 404 반환 확인
- HTTP 검증:
  - bootstrap admin 로그인 후 role 목록/permission catalog/account 목록 조회
  - 임시 기본 signup role 생성 후 회원가입 계정의 기본 role 자동 부여 확인
  - `console.access` 단독 계정이 `/api/admin/permissions`는 조회 가능하지만 `/api/admin/accounts`, `/api/admin/roles`는 403인지 확인
  - account role assignment + override allow/deny 적용 후 최종 permissions가 기대값과 일치하는지 확인
  - `conversation.list.any`/`read.any` 허용 계정이 타 계정 대화를 조회할 수 있고, `conversation.ask`는 타 계정 대화에 이어쓰기 할 수 없는지 확인
  - `conversation.rename.any` override 후 타 계정 대화 제목 변경 가능 여부 확인
  - `/api/clear_memory`가 410을 반환하는지 확인
  - 마지막 관리 가능 계정/role 보호 규칙이 빈 permission set 갱신을 차단하는지 확인
  - soft delete 후 로그인 차단과 기존 세션 폐기 확인
- 브라우저 검증:
  - 관리자 로그인 후 `/admin` 진입, role 생성/수정/기본 가입 역할 전환 확인
  - 브라우저 회원가입 계정에 기본 signup role이 반영되는지 확인
  - 관리자 콘솔에서 계정 role을 `pending -> custom role -> pending`으로 바꿀 수 있는지 확인
  - own conversation에서 제목 변경/삭제 버튼이 노출되는지 확인
  - 타 계정 대화는 `read/list.any`만 있을 때 버튼이 숨겨지고, `rename/delete.any` 허용 후 버튼이 노출되는지 확인
  - 삭제된 계정이 `deleted` 필터에 표시되고, 삭제된 role이 역할 목록에서 제거되었는지 확인
  - 삭제된 계정 브라우저 로그인 차단 확인
  - 스크린샷:
    - `/shared/out/browser/rbac_admin_home_76309029.png`
    - `/shared/out/browser/rbac_admin_roles_76309029.png`
    - `/shared/out/browser/rbac_user_own_76309029.png`
    - `/shared/out/browser/rbac_user_other_76309029.png`

## 7. Blocked Items
- 없음

## 8. Human Attention Needed
- **[20260812T1817 관측 등재 · 조치 불요] 자판 교차 검색의 쿼리 비용은 데이터 증가 시 재평가.**
  대화 본문 검색은 선행 인덱스가 없는 `%…%` 스캔이며(본 변경 이전과 동일한 성질), 자판 후보가
  붙으면 컬럼 비교가 최대 2배가 된다. 라이브 실측(현행 규모: 대화 349 · 코어메시지 7,164 ·
  메시지 1,956)에서 **108.2ms → 203.2ms**, PG `statement_timeout` 3,000ms 대비 **6.8%** 로
  여유가 크다. **단일 표본 기준**이므로, 데이터가 10배 규모가 되면 timeout 근접 여부를 다시
  측정해야 한다. 완화 장치: 후보 상한 2× · 1자 검색어 확장 차단 · per-account 10req/min
  rate limit. (근거: REV-20260812T181700-hangul-qwerty-search [CODEX] P2-5)
- **[20260806T1820 잔여 · 사용자 결정 필요] 이미 갈라진 첨부 버전 체인 9쌍의 소급 병합.**
  이번 cycle 은 **앞으로** 편집본이 원본 파일명을 승계하게 해 분열 기전을 제거했지만, 이미 만들어진
  `x.sql` / `x_v2.sql` 쌍(대화 `20260806052006-3f48cbb7` 실측 9건)은 **그대로 남는다** — 목록에
  두 항목으로 계속 보인다. 병합하려면 기존 row 의 `OriginalFilename`·`RootAttachmentId`·
  `VersionNumber`·`SupersededAt` 를 다시 쓰는 **파괴적 데이터 변경**(§12.3)이라 별도 승인 대상이다.
  판단 재료: 병합 시 버전 번호 재배열 규칙(시각순 vs 기존 번호 보존)과 되돌리기 계획이 필요하다.
- **[20260806T1820 구조 잔여] 토스트가 단일 엘리먼트라 연속 알림이 서로를 덮는다.**
  배치 업로드는 요약 1회로 이를 회피하지만, 다른 경로(여러 비동기 작업이 연달아 끝나는 흐름)에서는
  같은 문제가 남는다. 큐잉·스택 토스트로 바꾸는 것은 전 표면 영향이라 별 cycle 대상.
- **[20260807T0030 신설 감지축] 프론트 레이아웃 계약은 헤드리스 기하 실측으로 잠근다.**
  `tests/headless/verify_attach_diff_geometry.py` 가 실 chromium 에 실 CSS·실 렌더 함수를 올려
  열 폭을 숫자로 검사한다. **jsdom(mjs) 하네스는 레이아웃을 계산하지 않으므로 이 축을 대체하지
  못한다** — 새 표·그리드·flex 계약을 추가할 때 같은 패턴을 쓸 것. CI 배선은 미완(로컬 게이트).
- **[20260806T2320 잔여] 첨부 버전 비교의 PB-0008 시각검증이 배포 후로 남았다.** 신규 JS
  (`static/app/attach-diff.js`)는 스탬프 미주입 + 모듈 캐시 이중 인스턴스로 `docker cp` 사전 QA 가
  불가하므로 서빙본에서만 유효하게 검증된다. **그 전까지 모달의 레이아웃·정렬·간격·가독성은
  미검증**이다(jsdom 은 픽셀을 보지 못한다). 수행 항목 9종은
  `docs/test-runs.d/20260806T2320-attach-version-diff.md` §4 에 열거돼 있다.
- **[20260806T2320 범위 밖] 말풍선 첨부 칩에서의 비교 진입.** 현재 진입점은 첨부 사이드 패널
  한 곳이다. 말풍선 칩에도 열면 §16.6 「복수 surface 개별 실행 검증」 대상이 되어(코드패스가 갈릴 수
  있다) 별 cycle 로 둔다.
- **[20260806T2320 범위 밖] 바이너리 첨부 내용 비교와 단어 단위 intra-line 하이라이트.** 전자는
  xlsx 시트/pdf 텍스트 추출이라는 별 문제이고, 후자는 현재 줄 단위 교체 하이라이트로 갈음한다.
- **[20260806T2320 관측 대상] 체인 스코프 필터의 warning.** `_load_attachment_version_chain` 이
  conversation/account 스코프 밖 행을 제외하면 warning 을 남긴다. 정상 데이터에서는 0건이어야 하므로,
  이 로그가 실제로 찍히면 **체인 편입 경로에 결함이 있다는 신호**다(로그를 소음으로 취급하지 말 것).
- **[20260806T1830 후속] 모달 포커스 트랩·포커스 복원이 전 표면에 없다.** `aria-modal="true"` 를
  선언하면서 Tab 이 다이얼로그 밖으로 나가고, 닫은 뒤 포커스가 `<body>` 로 떨어진다(검색 모달·
  그래프 도움말은 일부 포커스 처리 있음 — 11개 표면 중 갈림). 스크린리더 사용자 영향. 기존 결함.
- **[20260806T1830 후속] 드롭다운·컨텍스트 메뉴의 `document` 레벨 outside-click 해제 5+곳**
  (`admin/products.js`·`admin/datasources.js`·`graph/graph-core.js`)은 같은 뿌리(click target 승격)를
  공유하지만 **다른 UX 범주**라 이번 통일 대상이 아니다. 사용자가 그 축까지 정합을 원하면 별도 cycle.
- **[20260806T1830 후속] `admin/accounts.js` 임시 비밀번호 모달은 배경 dismiss 자체가 없다.**
  시각적으로 동일한 `.admin-modal-overlay` 인데 바깥을 눌러도 아무 일이 없다(위험은 없으나 정합 이탈).
- **[20260806T1830 후속] 검색 모달에서 날짜 popover 가 열린 채 배경 1클릭이 popover 와 모달을
  동시에 닫는다** — 입력한 질의·결과가 함께 사라진다. 구/신 구현 동일(본 cycle 회귀 아님).
- ~~**[20260806T1144 후속] 배경 dismiss 구 패턴이 남은 오버레이 3곳**~~ → **해소**
  (`20260806T1830-modal-dismiss-siblings`, 사용자 승인 후 전건 전환 + 그래프 도움말·검색 모달까지
  통합). 아래 원 항목은 이력으로 보존.
- **[해소됨 · 이력] 배경 dismiss 구 패턴이 남은 오버레이 3곳.**
  이번 cycle 은 사용자 요청 스코프("좌측 항목(대화/폴더) 설정 모달")의 6종만 `bindBackdropDismiss`
  로 전환했다. 변수명이 `backdrop` 이 아니라 `overlay` 라 최초 sweep 에서 누락됐다가 §18.8 design
  리뷰어 반증으로 확인된 동형 3곳이 남아 있다 — **사용자 결정 필요**:
  | 위치 | 화면 | 현재 동작 | 비고 |
  |---|---|---|---|
  | `static/app/profile.js:306` | 프로필 > 사용 내역 > 대화 목록 | `mousedown` 단독 | **사용자향** — 누르기만 해도 닫힘(요청 문구의 "down 됐을 때 종료" 그 자체) |
  | `static/admin/usage.js:662` | 관리 콘솔 > 사용 기록 | `mousedown` 단독 | 관리자 전용 |
  | `static/admin/audit.js:317` | 관리 콘솔 > 감사 > purge | `click` | 원 결함과 동형 |
  셋 다 읽기 전용 표/폼이라 작성분 소실 피해면은 없다(각 파일 확인). 전환은 `bindBackdropDismiss`
  import + 1줄 교체로 동일하다.
- **[20260806T1144 후속] `.share-mgr-backdrop` 에 `overflow` 선언이 없다.** `padding:24px` +
  `align-items:center` 와 결합하면 패널이 뷰포트보다 높은 짧은 화면(노트북 가로모드 등)에서 위아래가
  잘리고 스크롤바가 없어 접근이 불가하다. `openFolderSettings`(textarea rows=9 + 저장/삭제 버튼)와
  `openMoveConversationDialog`(목록)이 후보. `overflow-y:auto` 를 넣어도 지금은 실행 단계가 `click`
  이라 스크롤바 드래그가 dismiss 를 유발하지 않는다(그 부작용은 이미 봉인됨).
- **[20260806T1144 후속] 이 모달군에 포커스 트랩·포커스 복원이 없다.** `aria-modal="true"` 인데
  Tab 이 다이얼로그 밖으로 나가고, 닫은 뒤 포커스가 `<body>` 로 떨어진다(기존 결함 — 본 cycle 회귀
  아님). 스크린리더 사용자에게 영향.
- **[20260806T1144 후속] 미저장 폴더 지침 dirty-guard 부재.** 배경 1회 클릭은 여전히
  `openFolderSettings` 의 작성 중 지침을 확인 없이 파기한다(계약대로 닫힌 경우). 변경 시 확인이
  본질적 처방.
- `.env`에 추가한 `WEB_BOOTSTRAP_ADMIN_USERNAME`, `WEB_BOOTSTRAP_ADMIN_PASSWORD`는 현재 개발 부트스트랩용 값이다. 실제 운영 전에는 반드시 교체해야 한다.
- **TASK-0051 후속: 컨테이너 재빌드 + UX smoke** — `make web` 재빌드 후 `/admin` 진입해 (i) 메타 4 종 chip 회색 + × 없음 / (ii) DB picker 옵션 채워짐(메타·`agent_memory` 제외) / (iii) 제품 detail 의 name·desc·active·default·sort 입력 변경 시 footer 카운트 증가 / (iv) `+ 추가` / chip × / textarea 변경이 footer 단일 commit 으로 수렴 / (v) 시스템 프롬프트 textarea 변경이 productSelect 전환 후에도 보존 / (vi) `취소` 클릭 시 모든 신규 buckets clear 를 확인.
- **C5 (TASK-0052) 본체 cycle 완료 (2026-05-06)** — 운영자 검토 필요: D2-A 호환성 backfill 로 모든 6 role 이 KR 제품에 default-grant. 본 cycle 의 보안 효과 (G1-G8 가드) 가 실효를 발휘하려면 운영자가 권한 회수가 필요한 (role × product) 조합에 admin 콘솔 deny override 를 적용해야 함. 참고: [BRIEFING-c5-permission-product-access.md](./BRIEFING-c5-permission-product-access.md). `/plan-eng-review` (Section 1~4) + Codex outside voice (gpt-5.5, reasoning=high) 통합. 핵심 결정: D1-B (권한 코드 + 기존 override 재사용 — 단 RBAC engine DB-driven 마이그레이션을 C5 본체로 흡수) / D2-A (호환성 우선 backfill, **NOT secure-by-default** — 마이그레이션 report 후 운영자 검토) / D3-A (Product CRUD 자동 연동 + 명시적 트랜잭션) / D4 변경 (Codex Claim 6 수용: end-user `/api/session` filter + admin `/api/admin/products` 전체 유지). Codex 가 9 finding 을 catch — 그 중 5 개가 plan 골격을 흔드는 critical (정적 catalog 가정 / autocommit 기본 / 기존 conv `product_id_for_run` 가드 누락 / 추가 endpoint 4 곳 가드 / info 노출). 30 test case (smoke + DOM + negative HTTP) 정의. 다음 cycle 진입 시 TASK-0052 발급 + briefing 의 §3-§5 를 TASK.md §2.1 로 채택. **Phase 1A (RBAC engine 마이그레이션) 은 product 권한 도입 없이 단독 deploy 가능** — 분리 commit 권장.

### §8 원장 추가 (2026-08-06, attach-diff-syntax)

- **`share.js` 의 SQL 예약어 3번째 복제** — 공유 대화 뷰 번들은 classic `<script>` 로 로드되어 ESM
  import 를 쓸 수 없다(구조적 제약). `code-highlight.js` 정본화가 `app.js` 까지만 닿았으므로,
  예약어를 추가할 때 `share.js` 를 함께 봐야 한다. 근본 해소 = share 번들 ESM 전환(별 축).
- **`sql-tok-*` ↔ `code-tok-*` prefix 이원화** — 배경(어두운 코드블록 vs 라이트 표)이 달라 값이
  다른 것이지 중복은 아니다. 통합하려면 CSS 2파일 + 두 번들 회귀를 함께 봐야 한다.
- **전역 다크 팔레트 부재** — 첨부 diff 토큰 색은 라이트 기준 1벌이다. 전역 다크가 도입되면
  `base.css` 의 `--code-tok-*` 9줄에 다크 override 를 추가해야 한다(지금 넣으면 검증 불가 코드).
- **확장 대기 유형** — Python·JS/TS·Shell·Markdown·INI/conf 는 레지스트리 한 항목씩이며 사용자
  결정("차후 확장될 수 있습니다")에 따라 요청 시 추가한다.

### §8 원장 추가 (2026-08-07, attach-diff-syntax POST-DEPLOY)

- **`tests/verify_attach_multi_upload.mjs` red (범위 밖·선행)** — `_versionedFilename` 함수 미발견으로
  스위트가 예외 종료한다. 원인은 `attach-suffix-toggle`(PR #1183)이 그 함수를 서버로 이관하며 하네스를
  갱신하지 않은 것이고, **main 에서도 동일하게 red** 임을 대조 확인했다(내 cycle 무관·해당 파일 무접촉).
  CI 가 pytest 전용이라 이 red 는 조용히 썩는다 — 하네스 계약을 서버 이관 후 규약으로 갱신하는 별 cycle 필요.
- **CSS 는 문자열 검사로 검증되지 않는다** — 이번 cycle 이 실증했다(고아 주석이 `keyword` 규칙을
  삼켰고 문자열 grep·jsdom CSSOM 둘 다 통과). 정적 가드(F8/F9/F10)는 *이 실패 모드*를 잡을 뿐이고
  "규칙이 적용되는가" 의 정본은 실 브라우저 computed style 이다. 다른 CSS 축을 추가할 때도 같은 전제.
- **비교 불가 유형 라이브 표본 부재** — `Kind ∉ (text,csv)` 인 v2+ 체인이 라이브에 0건이라 토글
  미노출 축은 실화면으로 확인할 수 없었다(하네스 H9~H11 이 응답 합성으로 커버). 그런 첨부가 생기면
  다음 PB-0008 에서 실측 추가.

### §8 원장 추가 (2026-08-07, attach-diff-intraline)

- **응답 페이로드 증가** — `left_segs`/`right_segs` 가 원문 조각을 그대로 재전송해 6,000행 CSV
  기준 응답이 +1.2MB(×1.56) 커진다(§18.8 backend 패널 실측). 512KB 세그먼트 상한으로 **완화**
  했을 뿐 원인은 남는다. 델타/오프셋 인코딩은 프론트 계약을 복잡하게 만들어 별 cycle 판단.
- **1~2글자 마크의 시각적 약함** — 2px × ~6px. 배경을 못 쓰는 제약(구문 토큰 AA)의 결과이고
  굵기는 이 표에서 keyword 전용이라 쓸 수 없다. 리뷰어 판정도 "찾을 수는 있다". 라이브 표본으로
  재평가 필요.
- **초록 마크가 teal `number` 토큰과 1.09:1** — 좌/우 위치 중복 인코딩으로 완화되나, 값을 바꾸면
  구문 팔레트의 AA 계산을 다시 흔든다.
- **마크의 보조기술 노출 부재**(WCAG 1.3.1) — 기존 행 단위 색 처리와 동일한 성질이라 이 cycle
  신규 회귀는 아니다. 표 전체의 접근성 표기는 별 cycle.
- **기하 하네스가 조용히 죽어 있던 기간** — 구문 하이라이트 cycle(2026-08-06) 이후 이번 복구
  전까지 `verify_attach_diff_geometry.py` 는 전 케이스 미실행이었다. 그 사이 cycle 들이 "헤드리스
  기하 PASS" 로 보고했는지 확인이 필요하고, **하네스가 0건 실행일 때 exit 0 이 되지 않도록**
  최소 실행 건수 가드를 두는 것이 재발 방지책이다(별 cycle).

## TASK-0256 — assistant 답변 diff 블록 (2026-06-15)

### 변경
- 프롬프트(feature-0002): `agent_core.SYSTEM_PROMPT` OUTPUT 섹션 뒤 "SHOWING CHANGES — USE A MARKDOWN DIFF BLOCK" — 첨부/쿼리 리뷰·편집 시 변경을 ```diff 블록으로 제시.
- 렌더(feature-0003): `enhanceDiffBlocks`(app.js/share.js) — marked.parse→enhance→DOMPurify.sanitize. `language-diff` 블록을 라인별 `<span class="diff-line ...">` 재구성. styles.css/share.css 팔레트. 캐시버스터 bump.

### 라이브 배포 절차 (deploy_scope: included)
1. web + ask-worker 재빌드/재기동:
   `sudo docker compose build web ask-worker && sudo docker compose up -d --no-deps web ask-worker`
2. 라이브 WebSystemPrompts global row 갱신 (멱등·백업). 컨테이너 내 1회 실행:
   ```
   sudo docker compose exec -T web python - <<'PY'
   import app, agent_core
   M = "## SHOWING CHANGES — USE A MARKDOWN DIFF BLOCK"
   sec = agent_core.SYSTEM_PROMPT[agent_core.SYSTEM_PROMPT.find(M):].rstrip()
   c = app._open_memory_connection()
   row = app._load_system_prompt(c, scope="global")
   old = row["content"] if row else ""
   open("/tmp/task0256_global_prompt_backup.txt","w").write(old)
   if row and M in old:
       print("ALREADY-APPLIED")
   elif row:
       app._upsert_system_prompt(c, scope="global", content=old.rstrip()+"\n\n"+sec+"\n"); c.commit(); print("APPENDED")
   else:
       app._upsert_system_prompt(c, scope="global", content=agent_core.SYSTEM_PROMPT); c.commit(); print("SEEDED-FULL")
   PY
   ```
   - 백업: 컨테이너 `/tmp/task0256_global_prompt_backup.txt` (롤백 시 동일 헬퍼로 복원).
   - 멱등: 마커 존재 시 무변경. 기존 admin 커스터마이즈 보존(append-only).
3. PB-0008 Windows-browser 시각검증: 첨부 SQL 리뷰 요청 → 답변의 ```diff 블록이 +초록/-빨강 라인으로 구분되는지 (메인 채팅 + 공유 뷰).

## TASK-20260619T034522-oauth-google-foundation — Google 계정(OAuth) 로그인 토대 (2026-06-19)

### 1. Summary
사내 웹서비스 편입을 위한 **Google OAuth 2.0 / OpenID Connect 로그인 토대**를 비파괴로 구축했다(사용자 요청 "검토 우선 + 기반작업", REQ-20260619-0327, Critical §12.3). 검토 결과 현재는 자체 인증(username/password, PBKDF2 310k, 쿠키 세션 `mysql_ai_session`, RBAC)만 존재하고 Google/OAuth 는 전무했으며, 세션·인가 인프라(`_issue_auth_session`·`_set_session_cookie`·`WebRolePermissions`)를 그대로 재사용할 수 있어 "로그인 수단"만 추가하는 형태로 편입했다.

핵심 = **기본 비활성**: `_oauth_google_configured()`(flag AND client_id AND secret AND redirect_uri)가 False 면 `/api/auth/oauth/google/start`·`/callback` 은 404 로 런타임 인증 경로에 무영향이다. credential(`.env.oauth`) 주입 + `WEB_OAUTH_GOOGLE_ENABLED=1` 시에만 동작하며, 기존 비번 로그인은 공존한다.

### 2. 사용자 결정 (AskUserQuestion 2026-06-19)
① 비파괴 토대 구축 ② 모든 Google 계정 허용(도메인 무제한) ③ 자동 생성 + pending 승인 대기(email 일치 시 link) ④ 기존 비번 로그인 공존.

### 3. 구현
- **DB**(비파괴): `WebAccounts` 멱등 ALTER — `Email`/`AuthProvider`/`OAuthSubject` NULL + UNIQUE(AuthProvider,OAuthSubject)·UNIQUE(Email). `_ensure_oauth_identity_schema`, fast+slow 양 경로.
- **Backend**: Authorization Code + PKCE(S256) + HMAC 서명 state(CSRF/TTL) + ID token claim 검증(iss/aud/exp/nonce/email_verified/도메인) + 계정 매핑(subject/email-link/pending-create). 외부 의존 0(stdlib urllib+base64+hashlib+hmac). 엔드포인트 3종 + helper 9종.
- **Frontend**: 로그인 화면 Google 버튼(기본 hidden → `/api/auth/oauth/config` enabled 시 노출), `?oauth_error=` 안내, CSS, 캐시버스터 bump(index+admin).
- **인프라**: `.env.oauth`(gitignored, optional env_file) + `.env.oauth.example`(발급/활성 절차).

### 4. 검증
- `tests/test_oauth_google_foundation.py` 29/29 통과. 전체 회귀 0(사전존재 product-delete 2건은 base 동일, 무관). py_compile OK. 상세 = docs/TEST.md §4.
- outside-voice 적대 보안 리뷰: (REVIEW.md REV-20260619T-...-oauth-google-foundation 참조).

### 5. 보안 한계 (SECURITY.md §14.3/14.4 — 활성화/배포 전 보완 TODO)
- ID token **JWKS RS256 서명 검증 미구현**(현재 백채널 TLS+claim 검증). 활성화/외부 배포 전 필수 추가.
- 모든-도메인 허용 → 외부 노출 시 pending 계정 abuse(도메인 한정/사전등록 전환 검토). pending 승인 게이트가 1차 방어.
- `.env.oauth` agent-common 공유(web-only scoping 후속). state-secret 멀티워커.

### 6. 잔여 (활성화 cycle — 사용자 후속 결정)
Google Cloud Console OAuth Client 등록(외부 선행) → credential 주입 + flag=1 → JWKS 서명 검증 추가 → web 배포 → 라이브 e2e + PB-0008 → outside-voice 본 리뷰.

---

## gc-settings-archive-leave (feature-0009 cross-cut cycle) — Git 동기화 결과
- 작업: 대화 ··· 메뉴 '보관' → 설정 팝업 '대화 관리' 섹션 이동 + 보관 권한 없는 그룹 참여자 '나가기'(self-leave). frontend only(app.js·styles.css·index.html), 백엔드/스키마 무변경. CHG/REV-20260624T031337.
- 커밋: `ai/claude/gc-settings-archive-leave` worktree 의 cycle commit (hash=push 후 git log).
- verify-completion: **PASS** (feature-0003 9/9 + feature-0009 9/9, wiki·windows-browser informational PASS). 재시도 1회(CHECK#2 checkbox delta 보강).
- Push: **자동 진행**(§16.3 Step 4 — BLOCKED 없음 + Critical/Major 승인 대기 없음). branch `ai/claude/gc-settings-archive-leave` → origin.
- main 병합: **보류**(PR 생성·머지·web 배포는 외부 영향 — 사용자 confirm 후 진행).
- 충돌 해결: 없음(신규 branch, base main `165906b`).
- 잔여: PR 생성·머지(cycle-finalize) · web 재배포(static baked + 캐시버스터 `archive-leave`) · PB-0008 Windows-browser 실렌더 검증.

## TASK-20260702-graphview-webgl-polish — 그래프 뷰 WebGL 외곽선 선명화 + 단일클릭 컬럼 토글 (/_template:resume 재개, 2026-07-02)
### Summary
- `/_template:resume` 로 원본 세션 cfbede21(계정 session-limit 중단) 재개. 그 세션이 WebGL 배포 후 육안 후속 2건(줌인 외곽선 뭉개짐·컬럼 단독 토글 부재)을 `graphview-webgl-polish` worktree 에 미커밋 구현했으나 (a) 접힘→재펼침 버그 미수정 (b) 리뷰/docs/랜딩 미완 상태였음. 재개하여 완수.
- 결과: WebGL `webglTexSize:4096`+`pixelRatio:2`(WebGL 경로 한정), 단일클릭 컬럼 인라인 토글(`_metaGraphToggleColumns`, 300ms tap 타이머로 더블클릭 이웃확장과 구분), 접힘 시 `introspected.delete` 버그 수정, #519(graph-perf2) 결정론 컬럼 배치 재정합.
### Recent Changes
- 병합: origin/main `042613eb` ff → stash pop 재적용. admin.html 캐시버스터 충돌·admin.js 자동병합 해소(실 충돌 마커 0).
- 코드: `static/admin.js`(+condition pixelRatio·webglTexSize·`_metaGraphToggleColumns`·tap 타이머·collapse Set 해제·세로-스택 seed) · `static/admin.html`(캐시버스터 lockstep).
- 검증: `node --check` PASS. §18.8 적대 패널 REV-20260702T000000-graphview-webgl-polish VERDICT PASS(BLOCKING 0), NIT1(canvas-2D 폴백 pixelRatio 회귀) 즉시 수정.
### Git 동기화 결과
- verify-completion → commit(Task-Cycle: feature-0003-agent-web-ui) → push → PR → main merge → cycle-finalize → web 재배포(deploy_scope: included) → /healthz. (진행 시 hash·PR#·배포결과 갱신.)
### 잔여
- PB-0008 Windows-browser 라이브(단일클릭 컬럼 펼침/접힘·**재펼침 재출현**·줌인 선명·더블클릭 무회귀) — 배포 후 사용자 실화면 확인 권장.

## TASK-20260702-graph-panel-perms — 그래프 뷰 UX 3건 + 메타데이터 탭 권한 세분화(B안) (/_template:entry arg-given, PLAN-APPROVED, 2026-07-02)
### Summary
- 사용자 4건 요청(관리 콘솔 > 메타데이터): 그래프 뷰 상세 패널 드래그 리사이즈 · 확장 테이블 접기 버튼(박스 우측하단) · 첫 컬럼명 미표시 버그 · 메타데이터 탭 권한 세분화. 사용자 결정(AskUserQuestion): 권한=**B안 기능별 manage**, 진행=**1개 cycle 전체**.
- 권한 세분화는 **비파괴·가역**: `kb.ingest.manual` 을 catalog umbrella 로 유지하고 `_apply_permission_overrides` 함의로 세부 권한 5개를 effective 자동 부여 → DB 마이그레이션 없이 기존 grant 무손실. 백엔드 28 핸들러 + 프론트 게이트를 세부 권한으로 전환.
### Recent Changes
- 병합: 착수 후 origin/main 이 2커밋(#521/#522 graphview-webgl-polish) 전진 → rebase(stash→ff 344a5a80→pop). admin.js/admin.html 자동병합(실 충돌 마커 0), 편집 마커 전량 잔존.
- 코드: `app.py`(+권한 정의·함의·catchup·서버 서브탭 맵) · `routers/admin_metadata.py`(28 핸들러) · `static/admin.js`(리사이저·접기버튼·컬럼수정·권한맵) · `static/styles.css` · `static/admin.html`(캐시버스터 lockstep) · `tests/test_metadata_perm_split.py`(신규).
- 검증: `node --check`·`py_compile` PASS. 신규 9/9 + 영향 테스트 무회귀. `test_route_parity_p5b`(192→193)는 origin/main 기존 결함(route 무추가로 무관). §18.8 적대 패널 2 렌즈.
### Git 동기화 결과
- verify-completion --pre-commit → commit(Task-Cycle: feature-0003-agent-web-ui) → push → PR → main merge → cycle-finalize → web 재빌드·재배포(deploy_scope: included) → /healthz. (진행 시 hash·PR#·배포결과 갱신.)
### 잔여
- PB-0008 Windows-browser 라이브(드래그 리사이즈·접기 버튼 클릭·첫 컬럼명 표시) — 그래프 canvas 인터랙션 자동화 회귀 이력이라 **배포 후 사용자 실화면 확인 권장**. 권한 세분화는 단위테스트+적대 패널로 확증(백엔드 로직·비파괴 함의).
### 개선 제안(§8.1, 기록만)
- `test_route_parity_p5b` golden 스냅샷이 origin/main 에서 stale(192 vs 실제 193) — feature-0012(P5b) 소관으로 golden 갱신 필요(본 cycle 범위 밖, route 추가한 feature 가 갱신 대상).
- graph.read 가 그래프 뷰 내장 AI 분석(analyze, KB mutation)을 포함 — 추후 분석 트리거를 별도 권한으로 분리할지 검토 여지(현 B안은 "그래프 뷰 기능=1권한").

## 2026-07-02 — AI 운영 관제 패널 배포 후속 운영 (aiops-panel post-deploy)
- **PB-0008 라이브 PASS**: 패널 배포(c5e259db) 후 실 Windows 브라우저 실측 — 렌더·권한 게이팅·대시보드 타일 deep-link 전부 PASS(TEST.md). 
- **마이그 0030 hotfix**: 배포 자동 마이그레이션이 stale agent 이미지로 0030(llm_usage.latency_ms)을 미적용(deploy exit 0)한 것을 포착 → superuser 로 직접 적용·검증. 근본원인·근본수정은 아래.
- **배포 마이그 근본수정(PR #530, feature-0014-migrate-fresh-image)**: `deploy-web.sh` 가 마이그를 이미지 빌드 전에 stale `docker compose run agent` 로 돌려 신규 마이그를 head 오판(silent-skip)하던 회귀 수정 — build→migrate reorder + `MIGRATE_ALEMBIC_IMAGE`(방금 빌드한 이미지로 alembic) + gen_sql fail-loud. feature-0017 의 race-retry 와 결합. §18.8 BLOCKING 0.
- **워커 재빌드(15e0befc)**: insight/ask-worker 를 계측 포함 코드로 재빌드·recreate(healthy) — 워커 wrapper 경유 LLM 호출(insight/aux)이 latency 기록. (환경상 datasource circuit_open 이라 insight LLM 호출 라이브 미발생.)
- **잔여(별도 검토)**: main `agent` task(`agent_core._call_llm`)는 중앙 래퍼 미경유라 latency 미기록 — LLM 볼륨 최대 경로. latency KPI 완결하려면 이 경로 계측 필요(승인 범위 밖, 확장 제안).

## 2026-07-07 — 지식베이스 메타데이터 채택 인박스 + ENUM 대화 자율수집 (kb-candidate-adoption)
- **요청/범위**: 대화에서 용어사전·ENUM 코드사전 후보를 수집하고 관리 콘솔에서 채택하도록 UI 재구성(단순 목록 → 채택 구조). 사용자 결정: 전체 한 사이클 + 통합 채택 인박스(웹서비스 내 유사구조 리서치 후 적용). Major §12.3 (cross-unit feature-0002·shared).
- **핵심 발견(절반 gap)**: 용어사전은 `_glossary_autopropose`+`glossary_feedback`(0021/0023)로 대화 후보수집·검토큐·승급/거부가 **이미 구현**(기본 ON). ENUM 코드사전은 CRUD만·후보수집/채택 파이프라인 **전무**. → ENUM 을 용어사전 대칭으로 신설 + 두 사전 후보를 한 화면에 통합.
- **백엔드(ENUM parity)**: 마이그 `0039_enum_feedback`(검토큐 테이블 + `enum_dictionary.source` + GRANT, 비파괴·멱등) · `kb_glossary.py`(enum feedback 함수군 + `infer_enum_suggestions` + enum CRUD source) · `llm.py`(`ENUM_SUGGEST_PROMPT`/`llm_enum_suggest`) · `config.py`(`AGENT_ENUM_*`, threshold 0.9 보수적) · `agent_core.py`(`_enum_autopropose`, best-effort) · `app.py`(권한 `kb.enum.curate`) · `admin_metadata.py`(enum-feedback list/promote/reject + admin_list_enums source).
- **UI(통합 채택 인박스)**: 지식베이스 하위 별도 탭 `adoption`(리서치 IA 권고 — ENUM 후보는 용어사전 하위 부적합). 대시보드 카드 그리드 + 검토 큐 행 어휘 재사용 — 신뢰도/상태별 그룹 카드, 종류(용어/ENUM) 배지, 개별 채택·거부·되돌리기 + 그룹 일괄 채택, 사이드바 pending 배지(용어+ENUM 합계). 보유 권한 종류만 fetch·조작. XSS textContent-only.
- **검증**: 신규 코어 14 + web 경계 9 테스트 PASS. 기존 enum-list 계약(source) + route 골든(197→200) 갱신. 호스트 전체 1581 passed. 컨테이너 make test 유일 실패(routine_dbanalysis, `postgres-replica` 미해석)는 main 격리 실행에서도 동일 재현 → 사전존재 --no-deps env 실패로 확정(본 변경 무관). ruff PASS.
- **잔여**: PB-0008 Windows-browser 시각검증 = 정적 자산 baked·브리지 실 Chrome 필요 → **POST-DEPLOY** 수행(TEST.md §3 CHECK#13 사유 기록). 배포 시 `0039` 자동 마이그 적용 후 `alembic_version` 직접 검증(stale agent 이미지 마이그 누락 방어).
- **후속 제안(§8.1, 기록만)**: ① 개별 "편집 후 채택"(승급 전 정의/라벨 수정) — 현재는 as-is 채택(용어사전 기존 동작과 동일), 필요 시 promote override 파라미터로 확장 · ② ENUM 후보 수집을 쿼리 결과/스키마 introspection 기반으로 보강(현재 LLM 대화 추론만) · ③ 샘플 검수 큐도 채택 인박스로 흡수 통합 검토.

## 2026-07-07 — 메타데이터 콘솔 IA 통합(2차 보기 일반화) + 5서브뷰 디자인 폴리시 (metadata-console-redesign)
- **트리거**: 직전 채택 인박스(REV-…-kb-candidate-adoption) 배포 후 사용자 실사용 피드백 — 최상위 `채택 인박스` 탭이 `용어사전 > 용어 검토 큐`와 겹치고 실질 종속(위 후속제안 ③의 역방향 결론: 흡수 대신 **분산 편입**이 정답). `샘플 검수` 탭도 동형. + 5서브뷰 디자인 저급. 사용자 결정: 구조 통합 + **전체 디자인 폴리시(감사 Top 10)**.
- **접근(ultracode)**: Workflow #1(이해 5리더: 2차보기 템플릿·샘플/채택 제거면·디자인 감사·이전 교훈) → 설계 확정 → 채택인박스 제거(직접) → Step2-5 구현 위임(고강도 에이전트, 정밀 스펙) → §18.8 3렌즈 적대 패널 → findings 수정 위임 → 재검증.
- **구조**: glossary 하드코딩 2차 보기(`subTab==="glossary"`)를 서브탭 파라미터화(`_METADATA_REVIEW`·`viewBySub`·`_metaSyncViews` 동적 버튼·`_metaIsReview`·`loadFeedbackQueue(kind)`). 채택 인박스 전량 제거(백엔드·enum-feedback API·`kb.enum.curate` 유지). ENUM→`ENUM 코드사전 > {목록|검토 큐}`, 샘플검수→`샘플쿼리 > {목록|검수 큐}`(#metadataList 재타깃), 최상위 탭 2개 제거.
- **디자인(감사 Top 10 전부)**: `--surface-2` 토큰·rich empty+skeleton·enums/columns 테이블 카드 그룹핑(싱글턴 flat)·행 카드 기하·위계·폼 grid+인라인검증·SQL 프리뷰·필터바·배지 semantic 토큰(provenance=neutral)·이모지 제거+KPI. 기존 세련된 어휘 이식(신규 디자인 언어 0), light-only 준수.
- **적대 검증의 값**: §18.8 패널이 위임 구현의 **실 blocking 회귀**(kb.enum.curate 게이트 누락 → enum-curate 단독 사용자 ENUM 검토 큐 접근 완전 상실) + MAJOR(ENUM 그룹 column 드롭) + HIGH(다크 토큰 회귀) 등 10건 적발 → 전부 수정. 위임+적대검증 파이프라인이 단독 구현보다 결함을 더 잡음을 실증.
- **검증**: node --check OK · 제거 심볼 grep-0 · route 골든 불변 · 호스트 전체 **1637 passed**(회귀 0) · CSS 균형. XSS clean(순수 DOM 전환).
- **잔여**: PB-0008 Windows-browser 시각검증 = POST-DEPLOY(정적 baked). UI-only 라 배포 = web 재빌드만(worker/마이그 불필요). m2(샘플 배지 백엔드 limit 캡)는 accept — 필요 시 백엔드에 uncapped pending count 추가 검토.

## 2026-07-08 — 메타데이터 콘솔 잔여 디자인 폴리시 5건 (metadata-console-polish)
- **트리거**: metadata-console-redesign(35e8cb14) 배포 후 사용자 요청으로 **실 Windows 브라우저(PB-0008) 적대적 미적 검증** 수행 — win-browser relay 로 로그인→전 5서브뷰·2차 보기·컬럼 카드 그룹핑(108그룹)·편집 폼 라이브 캡처·판정. 구조 통합·rich empty·이모지 제거·선택 상태 복구 전부 라이브 확인, 잔여 미세 폴리시 5건 도출. 사용자 결정: 전부 적용+재배포.
- **폴리시**: #1 2차 보기 필 위계 역전(borderless 경량 chip) · #2 list-detail sprawl(메타 전용 스코프 균형) · #3 그룹 cards-in-card nesting(divider 평탄화) · #4 반복 timestamp(경량+그룹 내 숨김) · #5 신뢰도 배지 매몰(accent 분리). 순수 시각 CSS + confidence 배지 클래스 1개 — 로직/백엔드/구조 0.
- **검증**: node --check OK · CSS 균형 · route 골든 불변 · 호스트 1662 passed(회귀 0). REVIEW [SKIPPED:minor-css-polish-post-visual-review](적대 미적 검증이 이미 선행). POST-DEPLOY PB-0008 라이브 재확인이 정본 증적.
- **의의**: "구현→적대 검증→라이브 시각 검증→잔여 폴리시" 루프로, 코드 리뷰·단위 테스트로는 못 잡는 미적 위계/밀도 결함(nav 역전·nesting·sprawl·배지 매몰)을 실화면 근거로 교정.

## 2026-07-08 — 메타데이터 콘솔 UX 이슈 4건 (metadata-console-ux2)
- **트리거**: metadata-console-polish 배포 후 사용자 실사용 피드백 — ① 텍스트 밀집(좁은 좌측 목록) ② 검토/검수 큐 항목이 클릭해도 우측으로 안 펼쳐짐(선택 불가) ③ ENUM 기존 컬럼에 코드 추가 진입점 부재 ④ 샘플 검수 큐에 mermaid 원문 노출.
- **수정**: #1 list 폭 확대+행 가독성 · #2 검토/검수 큐 행 클릭→우측 read-only 상세(넓은 패널에서 전체 확인, #1·#2·#4 통합 해소) · #3 ENUM 그룹 "+코드 추가" pre-fill · #4 공용 mermaid 헬퍼 재사용(다이어그램 렌더). UI 단독, 백엔드 0.
- **검증**: node --check·CSS 균형·route 불변·호스트 1662 passed(회귀 0). §18.8 병렬 패널이 세션 사용량 한도로 미실행 → 메인 루프 적대 자기검증(블로킹 0)+PB-0008 라이브로 대체. 한도 리셋 후 서브에이전트 패널 재실행 가능.

## 문서 아카이빙 압축 정보 (§5.5, 20260711T115053)
- MODIFY.md 총 변경 424건 = 아카이브 408(`_archive/MODIFY-archive-20260711T115053.md`) + 현행 16(최근).
- REVIEW.md 총 리뷰 405건 = 아카이브 389(`_archive/REVIEW-archive-20260711T115053.md`) + 현행 16(최근).
- 이관은 verbatim(무손실 재구성 md5 검증) · 아카이브 파일명은 timestamp 규약(ADR-20260710T231146) 첫 적용.

## staged-flush 첨부 new_attachment_ids 라벨 대칭 — deferred ②-frontend (2026-07-15)
- **계기**: 첨부-답정합 실데이터 감사 deferred ②-frontend. ② 서브에이전트가 share-window `[from,to]` 는 라이브-ask 첨부 경로에 없음(비보안)을 확인 — friction(1) "이전 세션 파일만" 은 프론트 라벨 비대칭 + backend cap-note(②-backend CHG-20260715T060000 별도)였다.
- **RC**: 신규 대화 staged 첨부가 flush-업로드 후 `attachment_ids` 에만 union 되고 `new_attachment_ids` 엔 누락(스냅샷 시점 status="staged"≠"ready") → 프롬프트 ★/◆ 라벨(agent_core `_build_attachment_context_section`)이 ◆세션 으로 오라벨 → assistant "새 파일 반영 안 됨" 오판.
- **수정(CHG-20260715T110000)**: app.js lazy-create+staged 블록에서 `uploadedIds` 를 `new_attachment_ids` 에도 union(attachment_ids 대칭). 라벨-only(접근 스코프는 attachment_ids) → IDOR/인가 무영향.
- **검증**: `node --check` PASS + de-risk(대칭 로직 분석·적대 패널·서버측 소비 추적). 라이브 PB-0008(신규 대화 staged 첨부 ★신규 인지·"반영 안 됨" 미발생)은 정적자산 web 이미지 baked → 배포 후 실측(TEST.md §3).
- **②-frontend 로 axis ② 마감**: friction(2) xlsx 접근은 이미 수정됨(491310e5+958df646). friction(1) 은 ②-backend(cap-note 정직화)+②-frontend(라벨 대칭) 양면 봉인.

## assistant 진행상황/답변 실시간 전파 — 유휴 관찰자 run-감지 폴러 (realtime-progress-propagation, 2026-07-21)
- **계기**: 사용자 신고 — 타 계정 대화 모니터링 중 해당 사용자가 요청을 보내면 관찰자 화면에 assistant 말풍선이 실시간으로 안 뜨고, 다른 대화로 갔다 돌아와야 표시됨. 그룹 대화의 타 멤버 요청도 동일.
- **RC**: 진행상황 폴링(`pollProgress`)이 (a) 본인 `sendPrompt` / (b) `loadHistory` 가 대화 (재)로드 시 `last_status==processing` 감지 시에만 시작. 대화를 이미 열어둔 채 유휴로 보는 관찰자에게는 **새 run 시작을 감지할 배경 폴링이 부재** → 재진입(loadHistory 재실행)해야 표시. 서버 `/api/progress`·`/api/history` 는 `conversation.read.any` 로 관찰자에게도 live 반환하므로 순수 프론트 결함.
- **수정(app.js, +133, frontend-only)**: 유휴 run-감지 폴러 추가. 대화 열림+활성 run 추적 없음 → `/api/progress`(client_run_id 없이) ~4s(숨김 15s) 폴링, 서버 `run_id` 가 baseline 과 달라지면 검증된 `loadHistory()` 위임(전환-복귀와 동일 경로: 메시지 재로드+pending 말풍선+활성 폴링 시작). 활성 폴링 중 dormant. `loadHistory`(idle arm/processing·no-conv stop, `!append`)·`selectConversation`·`handleLogout`·`visibilitychange` 배선. 감지 범위 = 모든 대화(사용자 선택 — 내 1:1 멀티탭 포함). 백엔드 무변경(`/api/progress` 가 terminal run_id 도 노출 → baseline 프론트 완결; 병행 feature-0012 라우터분할 충돌 표면 0).
- **feature-0009 정합**: `applyProgressPayload` 의 foreign-run 불변식(내 run 갈아타기 금지) 존중 — detector 는 활성 `progressRunId`/pendingBubble 존재 시 dormant.
- **검증**: 유닛 `verify_run_detect_poll.mjs` 23/23 PASS(감지 결정 매트릭스+정적 배선) · feature-0003 pytest RC=0(무회귀) · 실브라우저(Windows Chrome 150) — 유휴 대화에서 detector 폴링 확인→ 새 processing run 주입→ **재로드 없이** "처리 중" 말풍선 실시간 등장(net 로그+스크린샷). 검증 후 라이브 서비스 배포본 원복.

## 20260722T020408-msg-edit-textarea-contrast — 메시지 '수정' 편집 UI 글자 비가시 수정 + 편집 폼 재구성 (Minor §12.3, frontend-only 표시전용)
- **계기**: 사용자 신고 — 보낸 요청 메시지를 '수정' 기능으로 편집할 때 텍스트박스 색과 글자 색이 같아 글자가 안 보임(제공 스크린샷: 파란 말풍선 속 빈 흰 textarea). "실제 사람이 쓸 수 있게 UI 재구성" 요청.
- **RC**: 편집 UI(`_startInlineEdit`)가 파란 user 말풍선(`.message.is-user .message-bubble` `color:#fff`) 안으로 삽입되는데 `.message-edit-textarea` 가 흰 배경(`var(--surface)`)에 `color:inherit` → 말풍선의 흰 글자색을 상속 → 흰 글자 on 흰 배경(대비 1:1). 순수 표시 결함.
- **수정(styles.css + app.js, 표시전용)**: textarea 전경색을 `var(--text)` 로 명시 + `.message-edit-box` color 리셋(상속 차단) + 편집 진입 시 파란 말풍선을 중립 편집 패널로 전환하는 `.message-bubble-editing`(0,4,0) 신설 + app.js `classList.add`. 재구성 결과: textarea 진한 글자(대비 15.38:1), '요청사항 수정(재답변)'=파란 primary 버튼, '단순 수정'/'취소'=중립 pill — 배경과 싸우지 않는 표준 편집 폼.
- **무영향**: 백엔드·편집 엔드포인트·브랜치/IDOR·RBAC·스키마 0. feature-0019 ANCHOR §1-§3 무충돌. 라이트 전용 콘솔이라 다크 분기 불요.
- **검증**: `node --check` PASS · headless Chromium 실측(수정본 15.38:1 / 수정전 1.0:1 버그 재현 · 말풍선 중립 전환 · 재답변버튼 5.17:1) + 스크린샷 · POST-DEPLOY PB-0008 Windows-browser(잔여).

## 20260722T122635-shared-branch-readonly-paging — 공유/그룹·익명 공유-링크 뷰 편집 버전 읽기전용 페이징 (Major §12.3, PLAN-APPROVED design-review C)
- **계기**: 사용자 — 공유 대화 및 '링크 공유' 출력 화면에서 편집 버전 페이징이 정합 동작하도록. 현재 브랜치된 대화 공유 시 비활성 버전 평면 노출(pager 없음).
- **방향(설계리뷰 C)**: 읽기전용. active_leaf 불변(공유 근거 무결성), 기존 브랜치 read 가시성만 확장. 새 재답변 그룹 잠금 유지.
- **구현**: 두 로더(in-app `_get_history` / 익명 공유 `_share_load_messages`) 공용 `_branch_enrich_display` — active-path 필터 + 가시성-scoped 버전 메타. 읽기전용 네비 = `override_active_leaf`(비영속) + `branch_view` 파라미터 + `_branch_resolve_readonly_leaf`(가시 범위 검증 fail-closed). 프론트 app.js(그룹 읽기전용 pager)·share.js/css(공유 뷰 pager).
- **보안(핵심)**: 멤버 window / 공유 id-범위 밖 버전은 카운트·sibling_ids·존재·내용 모두 fail-closed 차단(익명 공유 뷰 누출 방지). active_leaf DB 불변.
- **검증**: 보안 단위 10 PASS(범위밖 형제 배제·resolver fail-closed) · py_compile 5 + node --check 2 · §18.8 적대 보안 리뷰 · 양 surface PB-0008(POST-DEPLOY).

## 20260723T024724-paging-scroll-preserve — 브랜치 페이징 스크롤 위치 보존 (Minor §12.3, frontend-only UX)
- **계기**: 사용자 — 편집 버전 페이징 시 스크롤이 맨 아래로 튀어 연속 페이징 번거로움.
- **RC**: `renderMessages` 매 재렌더 맨-아래 스크롤 + 비-append loadHistory 의 `_applyRenderWindowSoon` rAF 재-스크롤 + 공유 뷰 innerHTML 교체.
- **수정**: `loadHistory({preserveScroll})`(저장 top 복원 + window-soon 생략, rAF) + `_pageBranch`/`refreshWorkspace` 배선 + share.js window.scrollY 보존. append/일반 로드 무변경.
- **검증**: `node --check` 2 · POST-DEPLOY 실브라우저 scrollTop 실측(jsdom 부적합 — layout 의존).

## 20260723T033143-paging-scroll-longhistory — 긴 이력 페이징 스크롤 보존 회귀 (Minor §12.3)
- 계기: admin '간단한 덧셈 계산' 3→4 페이징 스크롤 보존 실패. RC: preserveScroll 이 window-soon 생략 + renderCount=3 리셋 → 긴 버전 스레드서 브랜치 메시지(pager) 창 밖. 수정: preserveScroll 시 전체 렌더. 백엔드 정상(curl). POST-DEPLOY PB-0008.

## 20260724T053457-metadata-review-ds-scope — 메타데이터 거버넌스 검토 큐 datasource 필터 + 자동승급 목록 정합 + 등록 시각 표시 (Major §12.3, frontend-only)
- **계기**: 사용자(`/_template:entry`) — `관리 콘솔 > 지식베이스 > 메타데이터 > [용어사전/ENUM 코드사전/샘플쿼리]`: ① 출력 요소가 선택 데이터소스로 필터 안 됨(검토 큐) ② 검토 큐 자동 승급 항목이 목록에서 조회 안 됨 ③ 각 요소 등록 시점 미표시.
- **RC**: ①/② scope-decoupling — 목록(`loadMetadata`)은 상단 데이터소스 셀렉터(`scopeKey`, 기본 common)를 `?scope_key=` 로 전송하나 검토·검수 큐 로더(`loadFeedbackQueue`/`loadSampleReview`)는 미전송 → 큐가 전 datasource 무필터. 자동승급 항목은 대화 datasource scope 로 기록돼 common 목록엔 미조회. 백엔드 3개 큐 엔드포인트는 이미 optional scope_key 지원(프론트 결함). ③ `_metaListRow` 가 updated_at 만 표시.
- **수정**: (frontend admin.js) `_metaReviewScopeParam` 신규(특정 ds→scope_key, 공용→전체 triage=Option A)로 3개 큐 로더에 scope 전송(Fix 1) → 큐·목록 셀렉터 공유로 자동승급 항목 정합(Fix 2) + `_metaListRow`/`renderFeedbackQueue`/`_metaRenderReviewDetail`/`_metaBuildEnumBundle` 등록 시각 표시(Fix 3). (§18.8 반영) 배지도 scoped 로 정합 — `kb_glossary.count_glossary_feedback`/`count_enum_feedback` additive `scope_key` 파라미터 + admin_metadata 엔드포인트 `scope_filter` 전달(Finding 1 MAJOR), `_metaPrimeReviewBadge` scope 전송 + scope-change 재-prime(Finding 2), sample 날짜 `등록 <_metaFmtDt>` 통일(Finding 3).
- **무영향**: RBAC·스키마·마이그·인증 0. 백엔드는 count 2함수 additive scope 파라미터 + 엔드포인트 인자 전달뿐(미지정 byte-동치·admin 전용 호출). 목록 경로 무변경. auto-promote write↔list read scope 정규화 동일.
- **검증**: `node --check`(ESM) PASS · `verify_metadata_list_detail.mjs` baseline 신규 회귀 0(26 PASS/3 FAIL·[D] crash=pre-existing 하니스, clean main 동일) · py_compile · pytest 116 PASS(metadata 44 + glossary/enum 72) · §18.8 적대 리뷰(SUBAGENT, SHIP-WITH-FIXES→3건 반영) · 정적 자산 baked → POST-DEPLOY PB-0008 Windows-browser 라이브. 정본 REVIEW REV-20260724T053457-metadata-review-ds-scope · MODIFY CHG-20260724T053457-metadata-review-ds-scope · TASK-20260724T053457-metadata-review-ds-scope.
- **[POST-DEPLOY 완결 2026-07-24] PR #931 main 병합(2b22b5ff) → make deploy-web 무중단(web-a/b·워커·gateway 2b22b5ff soak PASS) → PB-0008 Windows-browser 라이브 PASS**: 실 Windows Chrome(https://localhost/admin) — 검토 큐 datasource 필터(공용 96건→mysql-kr-an1-auth 16건, 전 행 해당 scope)·배지 정합(96→16, §18.8 Finding 1 MAJOR)·자동승급 목록 가시(용어 목록 84 중 82 자동등록)·전 행 등록 시각·pageerror 0. 사용자 원 3결함 전부 해소. 스크린샷 scratchpad metadata-ds-list-registered.png. postverify=REV/CHG-20260724T053457-metadata-review-ds-scope-postverify.

### [feature-0003] FR-brandnew-script-attachment-delivery-gap — assistant 신규 스크립트 첨부 전달 (Major, 2026-07-24, conversation_audit)
- **계기**: `/_dqa:conversation_audit` 라이브 대화 마찰 — 대화 …f1c535ec(2026-07-24, 1:1)에서 사용자가 "전체 스크립트 개선안을 첨부파일로 전달해주세요.(답변 본문이 아닌)" 중복 재전송(I-INT), assistant 는 "describe_routine 으로 생성한 결과라 원본 첨부가 없어 전달 불가" 거부(msg 1384).
- **RC**: 첨부 생성 경로가 기존 첨부 편집(`attachment-edit`, source_attachment_id 필수)만 존재 — brand-new 스크립트를 다운로드 첨부로 만드는 경로 전무. 프롬프트도 brand-new SQL 을 inline ```sql 로 유도. 재발경로=capability gap. corroboration 120일 생성물 파일전달 명시요청 2대화(근본 코드 file:line confirmed → fix-now).
- **수정**: source-less `attachment-new` 경로(root 첨부 생성, feature-0003) + 코드-권위 프롬프트 지침(feature-0002 cross-ref). 보안 가드 편집 경로와 전부 공유 + 업로드 RBAC 게이트.
- **무영향**: 편집 경로·스키마·마이그·RBAC 스키마 0. 순수 additive(업로드 권한 게이트 추가). 보안 회귀 0.
- **검증**: pytest 2369 PASS · §18.8 AGENT-TEAM(security MAJOR RBAC + backend MINOR 배지/cap/파서) 전부 반영. 라이브 실측=POST-DEPLOY PB-0008(배포 후 동일입력 재현).
- 정본 REVIEW REV-20260724T181106-brandnew-script-attachment · MODIFY CHG-20260724T181106-brandnew-script-attachment · 원장 FRICTION_LEDGER FR-brandnew-script-attachment-delivery-gap.

### [cross-ref] 첨부 후처리 web 게이팅 — worker 이전 후속 (2026-07-27)
primary=feature-0002 CHG-20260727T105326-worker-attachment-postprocess. web 은 후처리를 증거 기반으로만 수행(정상 경로 no-op, 워커 미완 시 self-heal)하고 worker 결과를 응답으로 전달. 정본 REVIEW=feature-0002 REV-20260727T105326-worker-attachment-postprocess.

## 20260728T113819-usage-records-system — LLM 사용량 드릴다운 '사용 기록' — 시스템 사용분 편입 + 화면 이동 (Major §12.3)
- **계기**: 사용자(`/_template:entry`) — `관리 콘솔 > 감사 > AI 운영 현황 > LLM 사용량` 차트 클릭 목록에 **'시스템' 사용 내역이 없음**. 명칭을 "대화 목록"→"**사용 기록**" 으로 바꾸고, 시스템 내역도 **어떤 작업으로 어떤 객체에서** 썼는지 인지 가능해야 하며 **클릭 시 해당 화면 이동**이 되어야 한다. 추가 요청(같은 turn): 본문 열 과도 줄바꿈 해소 + 팝업 **반응형 확장**.
- **RC**: 드릴다운이 `_query_usage_conversations`(INNER JOIN `core_conversations` + `owner NOT NULL`) 단일 경로 — 라이브 최근 30일 기준 **14,476 호출 / 36.4M 토큰(전체 토큰의 약 49%)** 이 대화 비귀속이라 목록에서 전량 누락. `(시스템)` 역할은 `_usage_account_ids_for_role → None` + 프론트 early-return 으로 **클릭해도 무동작**. 부수적으로 `redteam`/`enum_suggest`/`cluster_label`/`product_classify` 4 task 가 `TASK_TAXONOMY` 미등록이라 사람이 읽는 작업명 부재.
- **수정**: (백엔드) `_query_usage_system_records` — 대화 목록의 **정확한 여집합**을 `(task, target, actor)` 로 집계, 응답에 `system_items` **additive**(기존 `items` 무변경 → 소비자 회귀 0). `_resolve_usage_target_scopes` — `table_descriptions`∪`routine_objects`∪`rag_objects` union 으로 target→데이터소스 역해소(객체 우선·스키마 폴백, 모호 시 **추측 금지**). `_usage_system_nav` + `shared/model_catalog.USAGE_TASK_NAV`(task→화면 **SSOT**, 미등록은 AI 운영 현황 폴백). (프론트) 대화+시스템 **통합 표**(구분 배지·토큰 순 병합) + `applyUsageNav` in-page 이동(스코프→탭→서브탭→검색어) + `(시스템)` 막대 클릭 경로 복구 + 반응형 폭·열 배분.
- **무영향**: 마이그레이션 0 · 스키마 0 · **신규 RBAC 0**(기존 `console.usage.read`+`conversation.list.any` 게이트 불변) · profile(`/api/profile/usage/conversations`) 경로 무변경.
- **검증**: pytest **2,591 PASS / 2 skipped**(신규 14 케이스) · ruff clean · 라이브 PG 여집합 정합 **897+14,476=15,373=전체**(누락·중복 0, 집계 18ms/해소 14ms) · PB-0008 라이브 **PARTIAL PASS**(요구 4축 확정, 표기 2건 POST-DEPLOY). 정본 TASK-/CHG-/REV-20260728T113819-usage-records-system · test-runs.d/20260728T113819-usage-records-system.md.
- **라이브에서 잡은 in-cycle 결함 2건**: ① `scope_ambiguous` 를 `nav` 에 누락 → "데이터소스 여럿" 안내가 107행에서 조용히 소실(수정+회귀 가드) ② 비-sentinel actor 무조건 대화 링크 → **삭제된 대화 404** 위험(`bool_or(c.conversation_id IS NOT NULL)` 로 3분기).
- **후속(미착수)**: `llm_usage` 에 데이터소스 차원이 없어 target 역해소가 8,399 distinct 중 상당수 모호(dev/qa 동명 스키마). 근본 해소는 `llm_usage.target_scope` 추가 cycle 필요 — 현재는 "화면까지만 이동 + 모호 명시" 로 정직 저하.
- **[POST-DEPLOY 잔여]** 주체 열 3분기 표기 · 열 폭 재배분 실측 2건. pre-deploy 미확정 사유는 제품 결함이 아니라 **검증 환경 아티팩트** — `docker cp` 임시 반영이 `inject_asset_stamp.py` 를 우회해 `graph/*.js` 의 `admin.js?v=dev` 고정 import 와 entry URL 이 갈라지며 admin.js 가 **2 인스턴스**로 로드됨(캐시된 구 인스턴스가 이벤트 처리). 동시에 타 세션 web 롤링 배포와 겹쳐 임시 반영분이 소거됨. 실 배포본은 stamp 가 entry·import 양쪽에 동일 주입되어 재현 없음.

### [POST-DEPLOY 완결 2026-07-28] usage-records-system — PR #984 머지(`6d7fe391`) → `bin/deploy-web.sh` 무중단 배포(soak 통과) → PB-0008 라이브 **PASS**
선행 cycle 이 이관한 2건 종결: ① 주체 열 3분기(삭제된 대화 5 · 소유자 없는 대화 링크 1 · **raw id 0**) ② 열 폭 — 실측 중 **결함 발견·수정**(공용 `.admin-usage-table { max-width:640px }` 상속으로 테이블이 min-content 763px 로 수축 → 본문 열 239px 붕괴 = 사용자 보고 '과도 줄바꿈'의 진범. `max-width:none` 해제 후 테이블 1144px / 본문 열 **620px** / 단일행 18/20). 반응형 96vw 확인. 선행 cycle 의 pre-deploy 미확정이 환경 아티팩트였음도 확증(배포본 stamp 정합 `7fc11a708399` → admin.js 단일 인스턴스). 정본 TASK-/CHG-/REV-20260728T115900-usage-records-postverify · test-runs.d/20260728T115900-usage-records-postverify.md.

### [POST-DEPLOY 완결 2026-07-28] usage-records-hint-tooltip — PR #992 머지 → 배포 `0f956416` → PB-0008 **PASS**
행 2번째 줄 이동 안내 제거 확정: `.usage-rec-sub/-goto/-note` 노드 0 · 행 높이 **25/25 단일 줄** · 툴팁 이중 escape(`&gt;`) **0건** · 모호 정직 표기 툴팁 **107건 보존**(정보 손실 없음) · 이동 동작·대화 행 회귀 없음(시스템 200 / 대화 86). 정본 test-runs.d/20260728T121500-usage-records-hint-tooltip.md §POST-DEPLOY.

### [POST-DEPLOY 완결 2026-07-29] model-pick-early-cid — PR #1032 머지(`bc920534`) → 배포(11:08:44 KST, edge `36618965`) → PB-0008 라이브 **PASS**
선행 cycle 이 배포 후 잔여로 남긴 실측 종결. 배포본 실 Windows Chrome 150 에서 사용자 시나리오
[새 대화 → sonnet 선택 → 첨부 업로드 → 전송] 전 구간 계측: 선택 직후 `_modelPickedForConvId=""`
(결함 전제 재현) → 첨부 업로드가 early-cid `…2e511059` 발급하며 **귀속 승계** → 전송 본문
`model="claude-sonnet-4"` 동봉 → 무음 강등 경보 미발동. 정본 판정은 화면이 아니라 원장에서 —
`llm_usage` id 69372 `model=claude-sonnet-4`/`resolved_model=claude-sonnet-4-chat`(강등 0) ·
`kv(…2e511059, model:1)=claude-sonnet-4`(행 생성, 구버전 결함의 지문이 이 행의 부재였음).

**사용자 재보고는 배포 전 세션이었다**: 완료 보고 후 "이전과 동일하게 폴백"을 재보고받았으나 재현
대화(`…2211841a`) 첫 전송 **10:33:48** < 배포 **11:08:44**, 배포 후 신규 대화·첨부 **0건**. 같은 오전
대조군(`…a8b43197` 10:30 첨부 5건 sonnet 정상 vs 10:33 첨부 1건 haiku 강등)이 분기점을 **선택→첨부
순서**로 재확인해 선행 진단을 강화했다. 마찰 원장 `FR-model-pick-lost-on-early-cid` →
**`fixed:deployed:verified`**(잔여: corroboration 추세 재측정 1건, 다음 audit).
정본 TASK-/CHG-/REV-20260729T113000-model-pick-postdeploy · test-runs.d/20260729T1130-model-pick-postdeploy.md ·
교훈 `docs/LEARNINGS.md` LRN-20260729-0001/0002.

### [PRE-LANDING 2026-08-04] share-join-btn-visibility — 공유 링크 '대화에 참여' 버튼 노출 조건 확대
사용자 리포트("공유 링크에 fork 만 있고 그룹 대화 참여 버튼이 없다")의 근본은 **버튼 누락이 아니라
표시 조건**이었다. 라이브 실측: 링크(share `Id=81`)는 `Joinable=1` 정상이고, 로그인 열람자는 그 대화의
**소유자 본인**(`account_id=10`, `conversation_members.role='owner'`)이라 서버 `can_join`(= 로그인 &&
joinable && **!already_member**)이 false → `share.js` 의 `can_join` 단독 게이트가 버튼을 사유 없이 숨겼다.
`can_fork` 는 소유자 여부를 보지 않아 fork 만 남은 것. 라이브 서빙 자산에 버튼 DOM 은 존재
(`web-a` `GIT_COMMIT=03665d28`) — 구버전 배포 가설은 배제됐다.

사용자 결정(AskUserQuestion)은 "소유자에게도 참여 버튼 노출". 표시 판정을
`is_authenticated && (can_join || joinable)` 로 넓혔다(`shouldShowJoin`).

**적대 리뷰(codex)가 초안을 뒤집은 지점(P1)**: 표시만 넓히고 클릭을 그대로 join 으로 보내면, 기존
**windowed 멤버**가 버튼을 누를 때 서버가 `stamp_member_visibility(is_new_member=False)` 로 가시 범위를
**교집합 축소**한다(owner·기존 full 멤버는 skip, windowed 멤버는 좁아지고 **복구 경로 없음**). 종전엔
`already_member` 면 버튼이 없어 UI 로 그 경로에 닿지 않았는데, 표시를 넓히면 닿게 된다. → 이미 멤버인
클릭은 **join 을 호출하지 않고** `viewer.conversation_id`(멤버 한정 신규 응답 필드)로 곧바로 이동하도록
설계를 바꿨다. 서버 인가·window 로직은 무변경.

- **남은 리스크(낮음)**: `viewer.conversation_id` 는 `already_member` 일 때만 실리므로 익명·비멤버
  식별자 누출은 없다(B3 로 고정). ban 된 계정에는 종전과 동일하게 버튼이 보이고 클릭 시 서버 403 —
  본 변경으로 나빠지지 않았으나, "보이는데 실패하는 버튼" 계열 마찰은 `can_fork` 에도 동일하게 존재한다
  (§8.1 후속 제안 — 이번 범위 밖).
- **후속(필수)**: PB-0008 Windows-browser 실측이 **미수행**이다(변경분 미배포). PR 머지 → 배포 후
  ① 소유자 진입 시 버튼 가시 ② 클릭 시 대화 이동 + 네트워크 `/join` 요청 **0건** ③ fork·링크 복사 무회귀
  ④ 버전 페이징 후 클릭 1회 = 요청 1회 를 실측해 `docs/test-runs.d/20260804T0458-share-join-btn-visibility.md`
  §5 에 POST-DEPLOY 절로 append 한다. **미검증을 완료로 보고하지 않는다.**
- 정본: TASK/CHG/REV `20260804T0458-share-join-btn-visibility` · fragment 동명 파일.
## 20260804T0454-prompt-autogen-wiring — 사용자별(개인·계정·역할) 시스템 프롬프트 자동 생성 배선 복구 (Major §12.3)
사용자 요청: "각 사용자 별 시스템 프롬프트 자동 생성(개인·계정·역할)의 배선이 끊긴 부분을 전역 점검 후
수정". 전역 점검 결과 **호출 경로는 전부 관통**했고(엔드포인트 4종·프론트 버튼·`compose_system_prompt`
3층 누적 — 역할 28 실호출 45.4s/4605자 정상 산출), 끊긴 곳은 **접지 신호와 관측·정리 배선**이었다.

- **W1 대화 요약 writer 완전 부재**: `_refresh_summary_after_step`/`_refresh_summary_after_ask` 호출자 0
  (유일 호출자 `agent_cli.py` 가 죽은 코드로 삭제, `68ed7a76` 2026-06-02). → `agent_runtime.summary`
  **0행**(대화 296건). 제품·역할·개인 자동작성 3종의 "실제 분석 사례 요약" 접지가 **한 번도 생성된 적
  없음**(`meta.summary_count` 항상 0). 개인·역할은 DB 인사이트 축이 없어 요약+topic 이 접지의 전부라
  그중 하나가 죽은 채였다. 해소: `refresh_conversation_summary()` 신설 + `run_post_answer_curation()`
  에서 ask 당 1회 호출(사용자 대기 0, 게이트=기존 `AGENT_SUMMARY_REFRESH`).
- **W2 topic 신호 오염 27.5%**(계정 4 실측 40건 중 placeholder 3·중복 3·인사 3·raw 절단 2) → 정제기
  `_normalize_signal_topics` 를 role/account/product 3경로 공통 적용 + 원본 조회창 3배 확대.
- **W3 자동작성 실패 서버측 무로그** → SSE·JSON 양 경로 `logging.warning`.
- **W4 역할 삭제 시 프롬프트 고아행**(제품 경로엔 있던 cascade 가 역할 경로에만 부재) → cascade 추가 +
  기존 고아 3건 백업 후 정리(잔존 0).

### 개선 제안(§8.1, 기록만 — 사용자 지시 없이 실행 안 함)
1. **인가 비대칭(선재)**: 역할 프롬프트 자동작성의 접지(topic·summary)는 `owner_account_id IN (역할
   소속)` 으로 **타 사용자 대화 메타**를 읽는데 게이트는 `system_prompt.manage.role.any` 단독이다.
   현재는 그 권한 보유 역할(admin)이 `conversation.read.any` 도 보유해 미발현이나, 둘을 분리 부여하면
   열람 권한 없는 대화의 메타가 프롬프트 생성 컨텍스트로 흘러간다. topic 축은 이미 라이브였고 본 cycle
   이 summary 축까지 켜므로 노출 폭이 넓어진다 — 게이트에 `conversation.read.any` 동반 요구를 추가할지
   검토 필요.
2. **`_set_run_deadline()` 호출자 0**: `CURRENT_RUN_DEADLINE_TS` 가 항상 0.0 이라 `_near_run_deadline()`
   은 상시 False — aux-skip 예산 가드(`AGENT_AUX_SKIP_NEAR_DEADLINE_MS`)가 현재 무동작이다. 설정은
   존재하는데 코드 경로가 없는 W1 과 **동형 패턴**. 별도 cycle 로 활성화 또는 정직한 제거 판단 필요.
3. **역할×제품 프롬프트에 자동작성 부재**: `buildSystemPromptEditor` 는 `autoGenerateRoleId` 를 지원하나
   역할 '전체 제품' 카드에만 전달되고 제품별 카드에는 없다(백엔드도 product-scoped role 생성 미지원).
4. **관리 콘솔에 계정 스코프 프롬프트 편집기 부재**: `scope:"account"` 를 지원하는 공용 에디터가 있으나
   호출부가 프로필(본인)뿐 — 관리자가 특정 사용자의 개인 프롬프트를 보거나 생성할 수단이 없다(설계상
   self-service 결정이었는지 재확인 필요).

### [POST-DEPLOY 완결 2026-08-04] share-join-btn-visibility — PR #1134 머지(`d23f0a0d`) → 배포 → PB-0008 **PASS**
선행 cycle 이 잔여로 남긴 라이브 실측 종결. 사용자가 리포트한 상황과 동형인 *소유자 본인이 자기
joinable 공유 링크를 여는* 케이스(share `Id=77` · 대화 `20260722015451-d23ad939` · 계정
`bootstrap_admin`)로 실 Windows Chrome 150 에서 6축 검증했다 — ① '대화에 참여' 버튼 가시
② 배포본 응답이 `can_join=false`·`already_member=true` 인데도 노출(**종전 코드면 숨겨졌을 조건**)
③ 클릭 시 `/api/share/*/join` 요청 **0건**(요청 캡처 직접 관측 — 적대 리뷰 P1 회피 실증)
④ `?conversation=<cid>` deep-link 이동 후 목표 대화 열림 ⑤ fork·링크 복사·로그인 링크 무회귀
⑥ 익명 뷰 `viewer.conversation_id=null`. 증거 `artifacts/pb0008/20260804-share-join-btn-owner.png`.

**남은 리스크**: 없음(이번 범위). 선행 cycle 이 `[SKIPPED:tool-restricted:ux,design]` 로 남긴
화면 배치·가시성 미검증 범위가 본 실측으로 해소됐다.

**후속 제안(§8.1, 이번 범위 밖)**: `can_fork` 는 ban 된 계정에도 `true` 라 fork 버튼이 보이고 클릭
시 서버 403 이 난다 — "보이는데 실패하는 버튼" 계열 마찰로 참여 버튼과 동일 계보다. 별도 cycle 로
다룰 가치가 있다(본 변경으로 나빠지지 않았음).

정본: TASK/CHG/REV `20260804T0620-share-join-btn-postdeploy` · fragment
`20260804T0458-share-join-btn-visibility.md` §5.

### [POST-DEPLOY 완결 2026-08-04] prompt-autogen-wiring — 2단 배포 후 라이브 실증 PASS (1차에서 실효 0 을 검출해 2차로 종결)
- 1차: PR #1135 머지 → 배포 `c4701a17`(web·insight-worker·ask-worker·ops-scheduler 전량). **배포본
  실호출 검증에서 `saved=False` · `agent_runtime.summary` 0행 유지** — writer 복구가 코드상 옳았는데도
  라이브 실효 0. 로그 `load_memory_context: PG partial failure (summary=False msgs=True kv=True)`.
- 진단: `_read_runtime_pg` 계약("`None`=읽기 실패")과 `load_summary` 의 "행 없음도 `None`" 이 충돌 →
  요약 미보유 대화 전부가 PG 실패로 오판 → conn=None 폴백에서 예외 → **첫 요약을 영원히 못 쓰는
  부트스트랩 교착**. feature-0002 `TASK-20260804T0630-summary-bootstrap-deadlock` 으로 분리 수정.
- 2차: PR #1138 머지 → 배포 `fba8ee9f` 전량. **라이브 재실증 PASS**:
  - 요약 writer — `refresh_conversation_summary()` `saved=True`(12.7s), `agent_runtime.summary`
    **0행 → 1행**, 저장 본문 육안 확인.
  - 자동작성 접지 — account(계정 10)·role(admin) 양쪽 `meta.summary_count` **0 → 1**(종전 상시 0),
    "내 과거 분석 사례" 요약 블록 실제 생성 확인.
  - topic 정제 — 계정 10 의 40건에서 placeholder `새 대화` **0** · 중복 **0** · 개행 raw 절단 **0**
    (정제 전 동일 축 실측 잡음 27.5%).
- **교훈(정직 표기)**: 1차 cycle 의 단위 테스트는 `load_memory_context` 를 통째로 스텁했고 결함이 바로
  그 함수의 분기에 있었다. **배포 후 실호출 검증이 아니었으면 "고쳤다" 고 보고한 채 라이브는 그대로**
  였을 사안 — 스텁 경계가 결함 지점과 겹치면 단위 테스트는 구조적으로 눈이 먼다.
- 정본: TASK-20260804T0454-prompt-autogen-wiring · TASK-20260804T0630-summary-bootstrap-deadlock ·
  REV-20260804T045449 · REV-20260804T063000.

- 2026-08-07 `attach-diff-unified-bg`: 직전 cycle 이 넣고 배포한 **단일열 줄 배경 소실 회귀**를
  자기 적발·수정. 배경 규칙을 `.has-content` 로 좁힐 때 2열 렌더러만 갱신해, 단일열의 내용 있는
  변경 줄이 danger/ok 를 잃고 "대응 내용 없음" 중립 filler 를 받았다(**의미 반전**). 배포 후
  확대 캡처 판독 → 라이브 실측으로 확정 → 1줄 수정 + 재발 차단 4축(헤드리스 B9/B9b 동작층,
  mjs A1d 구조층 — 부여 지점 개수 대칭). 뮤테이션 4/4. 헤드리스 46/46 · mjs 88 PASS.

## 20260807T1300-attach-diff-identical-source — 내용 동일 시 문서 원문 출력 (Minor §12.3)

**요청**: "서비스 내 첨부파일 diff 부분에서, 파일 내용이 동일하다면 문서 원문을 출력하도록
구성해주세요."

**종전 결함**: 맥락 축약은 *변경 지점 주변만 남기는* 연산이라 변경이 0개면 남는 행도 0개다 —
파일 전체가 `gap` 한 줄로 접혔고 프론트는 배너만 두고 return 했다. **화면에 본문이 한 줄도 없었다.**

**변경**: 서버 `_build_version_diff_view` 가 `identical` 을 축약 대상에서 제외해 원문 전량을 방출하고
(정본 1곳 — 프론트가 축약 로직을 재구현하면 두 구현이 갈라진다), 프론트 `_renderSource` 가 줄번호 +
본문 2열 표로 렌더한다. 신규 권한·스키마·마이그레이션·엔드포인트 shape 변경 0.

**적대 리뷰(§18.8 ux·design, 사용자 승인 하에 호출)에서 드러난 것 — 이번 cycle 의 핵심**:
위험은 렌더가 아니라 **말**이었다. "문서 원문" 은 전량을 봤을 때만 쓸 수 있는 단어인데 초판은
세 경우 모두에서 그 단어를 썼다 — ① 행 상한 절단(**이번 변경으로 처음 도달 가능해진 상태**.
종전엔 identical → gap 1행이라 6,000행을 넘을 수 없었다), ② 원본 1MB cap, ③ `splitlines()` 가
흡수하는 줄 종단자 차이(CRLF↔LF·마지막 줄 개행 — sha256 은 다른데 `identical=True`).
화면의 세 요약(절단 배너·안내 배너·요약 배지)이 각자 다른 근거로 만들어져 서로를 반박했다
("차이가 많아 앞쪽 6000행" + "문서 원문(20000줄)" + "차이 없음" 동시 표시). 해소는 판정을 한 곳
(`_identicalFlags`)으로 모으는 것 — 서버에서 `identical` 을 한 번만 판정하게 한 것과 같은 처방.

**부수 적발(선행 결함)**: `el.hidden = true` 가 **CSS 층에서 무력화**돼 있었다. author
`.attach-diff-hltoggle{display:inline-flex}` 가 UA `[hidden]{display:none}` 를 이겨, 선행 cycle 의
"칠할 본문이 없으면 하이라이트 토글 숨김"(AC-AVD-23)이 화면에서 작동하지 않았다. 같은 기전을
쓰려다 드러났고 override 규칙으로 봉인.

**검증**
- `tests/verify_attach_diff_identical_source.mjs` **61 PASS**(D 섹션은 모달을 실제로 열어 4상태
  컨트롤을 실측 — 정적 정규식으로는 "코드에 그런 줄이 있다" 까지만 알 수 있다)
- 뮤테이션 3/3 red — 판정면 되돌리기(D4·D6) · 절단 게이트 무력화(B8d·B8e·B8f) ·
  sha 판정 무력화(B9·B9b)
- `tests/test_attachment_version_diff.py` B7·B7b·B7c·E15 신규
- 선행 하네스 회귀 — `verify_attach_version_diff.mjs` 89 · `verify_attach_diff_syntax_highlight.mjs`
  113 · `verify_diff_lineno_leak.mjs` 30 전부 PASS
- pytest 전량 · PB-0008 라이브 시각검증 — 아래 "Git 동기화 결과" 참조

### 개선 제안(§8.1, 기록만 — 사용자 지시 없이 실행 안 함)

- **`[hidden]` 트랩의 계열 종결**: 같은 함정을 `profile.css`·`shell.css`·`search-audit.css`·
  `chat.css` 4파일 9지점이 각각 **클래스 열거**로 막고 있다. `base.css` 에
  `[hidden]:not([hidden="until-found"]) { display: none !important; }` 한 줄이면 계열이 끝나지만,
  기존 9지점을 함께 회수해야 정본이 둘이 되지 않는다 — 별 cycle 감. (design 리뷰 R4)
- **identical 화면의 메타 요약 표**: "내용이 같다" 를 받은 사용자의 다음 질문은 "그럼 왜 버전이
  둘인가" 다. 바이너리 identical 화면은 이미 작성 주체·크기·시각·sha256 표를 준다 — 텍스트
  identical 에도 같은 표를 재사용하면 두 화면의 비대칭이 사라진다. (ux 리뷰 권고 4)
- **`verify_attach_diff_syntax_highlight.mjs` I1 은 부하 의존 flake**: "최악 적대 입력 <
  1.0ms/line" 임계가 호스트 부하에 따라 0.735~1.164ms 로 흔들린다(같은 커밋에서 4회 실행 중 1회
  red). 이번 변경은 토큰화를 건드리지 않으므로 무관하지만, 절대 시간 임계는 공유 호스트에서
  구조적으로 flaky 하다 — 상대 비교(I2 처럼 길이 2배당 증가율)로 바꾸는 편이 낫다.
- **원문 뷰의 대용량 체감 미측정**: identical 이면 `rows` 가 각 줄을 `left`/`right` 두 벌로 싣는다.
  "줄 수는 적고 줄이 긴" 파일(minify 된 `.json`/`.js`)에서 payload·렌더 비용이 종전 gap 1행 대비
  크게 늘 수 있다. 하이라이트 성능 하네스(I1)는 4,000자/줄까지만 본다.

### [POST-DEPLOY 완결 2026-08-07] attach-diff-identical-source — PR #1192 머지(`ca801d46`) → 배포 → PB-0008 라이브 **PASS**

- 배포 `bin/deploy-web.sh` scope=all — web-a/web-b 롤링(soak 통과) + insight/ask/ops 워커 전량
  `mysql-ai-agent:ca801d46` + gateway 드리프트 없음(무접촉).
- 라이브 서버: 기본 `context=3` 요청에 `rows=5 types=['equal']` gap 0 (배포 전 동일 요청은
  `rows=1 types=['gap']` — 본문 0줄).
- 라이브 화면: 원문 5행 렌더 + 구문 색 + `aria-label` · diff 전용 컨트롤 비활성 ·
  배너/배지가 sha 불일치를 정확히 표기. 정상 diff 회귀(2열 6행·gap 전개 버튼·토글 왕복) PASS.
- 검증용 대화 삭제 완료(잔존 0). fragment
  `docs/test-runs.d/20260807T1300-attach-diff-identical-source.md` POST-DEPLOY 절 참조.

## 20260807T1900-attach-source-view — 첨부 행 클릭 = 문서 원문 보기 (Minor §12.3)

**요청**: "별도로 추가된 버전이 없는 첨부파일 또한, 클릭했을 때 문서 원문이 출력되도록 구성해주세요."

**종전 결함**: 첨부 목록의 행은 클릭 대상이 아니었고(⬇·🗑·"버전 N개 ▾" 만 배선), 내용을 보는 유일한
길이 비교 모달이었는데 그 진입점은 `versions.length > 1` 게이트 뒤에 있다 — **버전이 하나뿐인
첨부(대다수)는 내려받지 않고는 내용을 볼 수 없었다.**

**변경**: `GET /api/attachments/{id}/source` 신설(권한·D21 게이트를 `/diff` 와 동형, 신규 권한 코드 0)
+ `openAttachmentSourceModal`(비교 모달의 identical 화면과 **같은 `_renderSource`**) + 목록 행 배선.

**설계 결정 — 버전 파라미터 없음**: 초안에는 `?version=` 쿼리와 모달 버전 선택기가 있었으나, 체인의
각 버전이 **자기 id** 를 가지므로 경로 id 하나로 대상이 특정된다. 식별 경로가 둘이면 그 중 하나만
스코프 검사를 통과하는 비대칭이 생길 수 있고, 어느 호출부도 채우지 않는 select 는 죽은 컨트롤이다.

### 이번 cycle 의 지배적 실패 양상 — "primitive 는 옮겼는데 계약은 절반만 옮겼다"

§18.8 패널 2건(security · ux+design)이 **같은 결함을 다른 축에서** 지적했다. 새 화면이 형제 화면의
렌더 함수를 재사용했지만, 그 화면이 직전 cycle 들에서 **주석·문서로 이미 봉인해 둔 계약**을 함께
옮기지 않았다:

| 이미 봉인돼 있던 계약 | 새 화면에서의 재발 |
|---|---|
| 재렌더는 스크롤 앵커를 뜬다(AC-AVD-15) | 구문 색 토글이 최상단으로 튐 — 원문 뷰는 축약이 없어 잃는 거리가 더 크다 |
| click target 은 mousedown/mouseup 의 **공통 조상**(`modal-dismiss.js`) | 파일명 드래그 선택 후 손 떼면 모달이 열림 |
| 절단이면 "원문" 이라는 말을 쓰지 않는다(`_identicalFlags`) | 제목·통계가 절단을 무시하고 단정 유지 |

**교훈**: "같은 primitive 를 쓴다" 는 렌더 함수 재사용만으로 성립하지 않는다. 그 함수가 사는 화면의
**계약 전체**(스크롤·판정·어포던스·포커스)를 옮겨야 한다.

### 증폭을 고치다 무음 절단을 만들 뻔한 자리 (기록 가치 최상)

security 패널이 `get_object_bytes` 전체 적재(최대 25× 증폭)를 지적해 ranged read 로 바꿨는데,
그러면 **`len(raw) > cap` 절단 판정이 영원히 거짓**이 된다 — 성능을 고치는 변경이 §16.7 G9-b(무음
절단 금지)를 깨는 형태였다. 판정을 DB 정본 크기(`SizeBytes`)로 옮기고 pytest E10 이 고정한다.

### 자기 결함 2건 (첫 전량 실행에서 적발)

- 내가 쓴 E7 단언이 응답 payload 의 `version` **메타 키**를 잡아 자기 자신을 red 로 만들었다
  (단언 대상은 쿼리 파싱이지 문자열이 아니다).
- 신규 route 로 `route_snapshot_p5b.json` 골든 drift — 의도된 게이트라 골든 갱신(227→228, 포맷 유지로
  최소 diff).

### 검증

- `tests/verify_attach_source_view.mjs` **77 PASS**(패널 반영으로 59→77) · 뮤테이션 2/2 red
- `tests/test_attachment_source_view.py` S1~S6 · E1~E13
- 선행 하네스 회귀 61 / 91 / 113 / 30 PASS
- pytest 전량 · PB-0008 — 아래 "Git 동기화 결과" 참조

### 개선 제안(§8.1, 기록만 — 사용자 지시 없이 실행 안 함)

- **§21 window clip 을 첨부 read 4경로에 일괄 적용**: 목록·다운로드·비교·원문 전부 미적용이다
  (`docs/SECURITY.md §21.5` 6번에 수용 근거와 함께 등재). 한 경로만 봉인하면 같은 행의 ⬇ 가 열린 채
  보호가 착시가 되므로 **4경로 동시 봉인 + 404 균질화**를 한 cycle 로 다뤄야 한다.
- **말풍선 첨부 칩의 클릭 의미가 정반대**: 대화 본문에서 첨부를 만나는 가장 흔한 표면인데 클릭이
  다운로드다. 목록은 이제 원문 보기라 두 표면의 규칙이 갈렸다.
- **6,000행 원문의 렌더 체감 미측정**: 하이라이트 토글마다 전량 재렌더(`paintCodeInto` 동기)이고,
  구문 색 성능 하네스(I1)는 4,000자/줄까지만 본다.
- **`/diff` 의 503 렌더 분기는 여전히 도달 불가**: payload `error` 동봉으로 문구는 정확해졌지만
  `_renderBody` 의 `source_unavailable` 분기 자체는 죽은 코드로 남아 있다(정리는 별건).
- **stash 잔재 2건**: 이번 cycle 중 `git stash -q -- <path>` 가 경로 한정으로 동작하지 않아 전체
  트리가 stash 됐다(작업 손실은 없었고 트리 무결성 재확인). 단일 파일 되돌리기는 `git checkout --`
  만 쓸 것. 남은 stash 는 현재 트리와 동일 내용이라 무해하나 정리 대상.

### [POST-DEPLOY 완결 2026-08-11] attach-source-view — PR #1199 머지(`bc8d0597`) → 배포 → PB-0008 라이브 **PASS**

- 배포 `bin/deploy-web.sh` scope=all — web-a/web-b 롤링(soak 통과) + 워커 전량 `mysql-ai-agent:bc8d0597`.
- 라이브 서버: `/source` 가 원문 5행 + `lines_partial=false` + `no-store`/`nosniff` 헤더 반환
  (배포 전 같은 요청은 404 — 엔드포인트 자체가 없었다).
- 라이브 화면 7축 PASS: 단일 버전 원문(키보드 Enter) · 접근성 구조(행 `role=null`, 파일명 버튼) ·
  포커스 복귀 · 행 안 버튼 격리 · 버전 이력 👁 구버전(v1, 121행) · 스크롤 보존 900→899 ·
  비교 모달 회귀(형제 cycle intraline 머지 후에도 정상).
- 검증용 대화 삭제 완료(잔존 0). fragment
  `docs/test-runs.d/20260807T1900-attach-source-view.md` POST-DEPLOY 절 참조.

## 20260811T1200-attach-version-action-align — 버전 이력 행 액션 열 정렬 (Minor §12.3)

**사용자 보고**(스크린샷): "버전비교 버튼의 유무에 따라, 문서 원문을 조회하는 버튼의 위치가
뒤틀리는 것을 확인했습니다."

**기전**: 액션 컨테이너가 `margin-left: auto` 오른쪽 정렬 flex 라, 행마다 버튼 **개수**가 다르면
있는 버튼이 통째로 밀린다. 직전 cycle 이 추가한 👁 이 맨 앞 슬롯이라 그 밀림이 가장 눈에 띄었을
뿐, 기전은 `⇄` 가 최신 행에만 없다는 **선행 구조**다. negative control 로 24px 드리프트 재현.

**범위 확장(자체 발견)**: 같은 결함 클래스가 목록 **3종**에 있다 — 활성 첨부 목록(`🗑`, 서버
`can_manage` 가 행별 술어)·휴지통(`⇤`, 체인 머리만). 한쪽만 고치면 같은 증상이 다른 화면에 남는다.

### 이번 cycle 에서 가장 값진 것 — "추정 수치는 틀렸는데 기전은 옳았다"

§18.8 패널이 "`min-width: 22px` 는 활성 목록 버튼(12px 글꼴/5px padding)에서 바인딩되지 않아 잔여
미정렬이 남는다" 고 계산했다. 그 **수치는 실측으로 기각**됐다 — 두 컨테이너 버튼 실폭이 모두
22.00px. 여기서 지적 전체를 기각했다면 진짜 결함을 놓쳤을 것이다.

구조적 지적("`min-width` 는 바닥이지 고정이 아니다")은 **옳았고**, 글꼴 확대 A/B 로 실제 열 깨짐을
재현했다 — `min-width` 방식은 버튼이 22→24px 가 되며 그 행의 `👁` 이 1135→**1133** 으로 밀린다.
브라우저 "최소 글꼴 크기" 접근성 설정으로 11px 이 승격되는 경로에서 **원증상이 복귀**할 수 있었다.
`flex: 0 0 22px; min-width: 0` 으로 못을 박아 해소.

**교훈**: 리뷰 지적은 **수치와 기전을 분리해 판정**해야 한다. 수치가 틀렸다고 기전까지 기각하면
"실측했으니 괜찮다" 는 잘못된 안심으로 끝난다.

### 검증

- `tests/verify_attach_version_action_align.mjs` **34 PASS**(패널 반영으로 23→28→34) ·
  **뮤테이션 7/7 red**(M1 이 사용자 보고 상태 `[3,4,4]` 를 정확히 재현, M6 이 슬롯 오배치를 겨냥)
- 선행 하네스 회귀 124 / 77 / 61 / 113 / 30 PASS
- PB-0008 좌표 실측 — 4버전 체인 열 단일값 · negative control 24px · 폭 규칙 A/B ·
  활성 목록 DOM-level control(1180→1204→1180)
- pytest 전량 — 아래 "Git 동기화 결과" 참조. (첫 실행에서 `test_shutdown_finalizer.py` 1건 red 였으나
  단독 3회 재실행 전부 green — 이번 cycle 은 **파이썬 무변경**이라 무관한 flake.)

### 개선 제안(§8.1, 기록만 — 사용자 지시 없이 실행 안 함)

- **액션이 5번째로 늘면 grid 로 전환**: 지금은 예약 슬롯 + `margin-left:auto` 유지가 정당하지만
  (AC-AVA-4 를 지키려면 grid 도 조건부 modifier 가 필요해 복잡도가 같다), 슬롯 삽입 위치 관리가
  세 함수에 흩어진 비용이 그때는 grid 선언 비용을 넘는다.
- **활성 목록 실행 테스트**: `_loadConversationAttachmentList` 가 async + `apiFetch` 라 이번엔
  구조 단언 + DOM-level control 로 대체했다. 렌더 부분을 순수 함수로 떼면 휴지통처럼 실행 가능해진다.
- **휴지통 `↩` 예약**: 지금은 서버가 관리 불가 행을 응답에서 제외해 열이 갈리지 않는다. 그 전제가
  바뀌면 예약이 필요하다(코드 주석에 전제 기록).

### [POST-DEPLOY 완결 2026-08-11] attach-version-action-align — PR #1207 머지(`04f2ecf5`) → 배포 → PB-0008 라이브 **PASS**

- 배포 `bin/deploy-web.sh` scope=all — web-a/web-b 롤링(soak 통과) + 워커 전량.
- 라이브 좌표: `probe_b.sql` 2버전 체인에서 두 행 슬롯 수 4로 동일, 열별 x 단일값
  (`👁`1135 · `⇄`1159 · `⬇`1183 · `🗑`1207), 버튼 실폭 22.00px. 스크린샷에서 최신 행의 비교
  자리가 비고 나머지 아이콘이 세로 정렬 — **사용자 보고 뒤틀림 해소 확인**.
- 라이브 데이터는 읽기만. fragment
  `docs/test-runs.d/20260811T1200-attach-version-action-align.md` POST-DEPLOY 절 참조.

### [2026-08-12] metadata-pane-refresh — 메타데이터 pane 입력 UI 통합 표 재구성 (Major §12.3, 표시 계층 전용)

**요청**: "서비스 내 메타데이터 입력창이 다른 화면에 비해 촌스럽다는 의견을 받았습니다. 다른
모범적인 웹사이트를 참조하여 세련된 형태로 재구성해줄 수 있을까요?"
사용자 결정: 시각 방향 = **통합 표 + 프리미티브**, 범위 = **메타데이터 pane 전체**.

**진단** — 결함 다수가 취향이 아니라 **이 pane 만 앱 토큰·계약을 안 쓰는** 것이었다:
포커스 halo 부재(다른 폼은 3px) · 박스-안-박스 격자(행 카드 + 내부 테두리 입력 × 30) ·
raw `●`/`○` 글리프(`--tag-*` 토큰 미사용) · 등폭 하드코딩(`var(--mono)` 미사용) · 전각 `＋`
(다른 pane 은 ASCII) · 저장 버튼 2줄 줄바꿈 · 회색 패널 3중 중첩 · 컬럼명 가변 폭.

**변경**: `css/search-audit.css`(주) + `admin.html`(sticky 열 헤더 markup, `＋`→`+`) +
`admin/metadata.js`(글리프 제거·3단 상태·헤더 가시성 동기). **백엔드·라우터·권한·스키마·
마이그레이션 0.** 골격 그리드의 **DOM 셀렉터 계약은 1개도 바꾸지 않아** 입력값 유실 회귀 표면을
정의상 0 으로 뒀다.

**검증**: 신규 `verify_metadata_pane_refresh.mjs` **80 checks**(뮤테이션 10/10 KILLED) +
`headless/verify_metadata_pane_refresh_render.py` **30 checks**(실렌더) · 기존 metadata 하네스
5종 154 checks green · mjs 53 파일 전건 green · pytest **4312 passed / 1 failed**(pristine main
동일 재현 = 선재 red) · **PB-0008 실 Chrome 150** 격리 컨테이너 PASS(125테이블 실데이터, 열 정렬
편차 **0.00px/30행**, 라이브 데이터 변경 0).

**사전 검증이 배포 전에 잡은 결함 2건**: ① 상태 라벨·열 헤더 WCAG AA 미달(4.12 / 3.58) →
`--text-2` 승격(7.11 / 6.18). ② sticky `top:0` 이 스크롤러 padding 18px 띠를 남겨 직전 행이 헤더
위에 비침 → `top: calc(-1 * var(--meta-grid-head-inset))` + 하네스 결합 검사.

**§8 후속 / 남은 리스크**
- **POST-DEPLOY 라이브 재확인 필요** — 본 Run 은 §13.2.9 격리 컨테이너(베이스 `d619259d`)
  기준이다. JS/HTML 변경 포함이라 `docker cp` 프리뷰는 원리적으로 불충분(모듈 캐시·스탬프
  미주입) → 배포 후 baked 자산 재실측이 완료 조건.
- 반응형(확대 200% · 폭 <720px) 미측정. 통합 표 열 폭이 `clamp()` 라 붕괴 위험은 낮으나 실측 아님.
- `.admin-meta-scope-select` 는 **그래프 뷰 pane 과 공유** — chevron·halo 개선이 그쪽에도 적용
  되나(의도된 정합) 그래프 pane 은 실측하지 않았다.
- `--meta-grid-head-inset` 은 `.admin-detail-col` padding-top 에 결합돼 있다. 하네스가 동치를
  검사하므로 drift 는 검증에서 잡히지만, 공유 클래스 padding 변경 시 이 토큰도 함께 갱신해야 한다.

### [2026-08-13] usage-metric-charts — 사용량 요약 카드 = 차트 지표 선택기 + 프롬프트 캐시 계측·활성화 (Major §12.3)

**요청**: "[요청, 호출, 총 토큰, 입력, 출력, 비용] 패널 클릭 시 차트도 해당 값으로 부드럽게 재구성"
+ "가능하다면 cache hit 된 입출력도 항목 추가".

#### 이번 cycle 에서 가장 값진 것 — "가능하다면" 을 먼저 실측한 것

두 번째 요청은 **데이터가 이미 있다는 전제**를 깔고 있었다. 코드를 쓰기 전에 그 전제를 실측한 결과
전제가 틀렸다: `llm_usage` 에 캐시 컬럼이 없었고(라이브 스키마 조회), 앱은 `cache_control` 을 한 번도
보낸 적이 없었으며(repo 전역 grep 0건), 그래서 **캐시 hit 자체가 존재하지 않았다**. 계측만 붙였다면
사용자는 "항목은 생겼는데 영원히 0" 인 화면을 받았을 것이다. 실측을 근거로 범위를 사용자에게 되물어
캐싱 활성화까지 포함하는 결정을 받았다.

부수적으로 얻은 사실 하나가 비용 계산을 바꿨다 — 게이트웨이 응답에서 `prompt_tokens = 5039` 가
`순수입력 37 + 캐시쓰기 5002` 였다. **캐시는 입력의 부분집합**이므로, 캐싱을 켜는 순간 기존 비용식은
캐시 적중분을 정가로 계산해 최대 10배 과대 계상하게 된다. 요청에 없던 항목이지만 켜는 것과 한 몸이라
같은 cycle 에서 정정했다.

#### 적대 리뷰가 잡아준 것 — "전부 통과한다" 는 세어 보기 전엔 주장이다

codex 리뷰가 P1 2 · P2 5 를 냈고 그중 하나가 내 **문서 주장 자체의 오류**였다: "LLM 요청은 두
chokepoint 를 통과하는 것이 전부" 라고 썼는데 실제로는 직접 호출이 16곳 있었다. 세어 보니 캐시
임계를 넘는 프롬프트를 쓰는 곳은 그중 하나(`NODE_ANALYSIS_PROMPT` 9,124자, 노드마다 반복)뿐이라
거기에 명시 적용하고, 나머지는 "임계 미달이라 no-op" 임을 **수치와 함께** 서술로 정정했다.
§16.7 G7(a) 가 말하는 "이름·설계 의도는 증거가 아니다" 의 실례였다.

P1 하나(모델 부분 선택 + 요청 지표에서 카드와 차트가 다른 모집단)는 실제 정합성 결함이라 조합
자체를 차단했고, 하나(모든 SQL 예외를 컬럼 부재로 오인)는 재실행도 실패하면 예외가 전파되므로
"무음 0" 이 성립하지 않음을 확인해 부분 refute 하되, **근거 없이 원인을 단정하던 로그**는 관측
시점(재실행 성공 후)으로 옮겼다.

#### 검증

- pytest **4,364 passed / 4 skipped**. 환경 제약 1건(`chattr` 부재)은 main 동일 재현 — 귀책 아님.
- 실 Chromium 렌더 하네스 **25 PASS** — 막대비가 지표 값 비율과 일치(3:1 → 0.6 → 7:1),
  **전환 중 노드 동일성 + 90ms 시점 높이가 시작·끝 사이**(= 점프가 아니라 이동), 비-가산 지표 단일
  막대, 안내 60자 예산, 상태 복귀 무오염.
- 테스트 더블 정정 — `_NoTargetCur` 가 "첫 실행만 실패" 라 사다리 3단에서 컬럼 부재를 재현하지
  못하던 것을 고쳤다(무음 통과 차단).

#### 잔여 리스크 · 후속 (§8.1 — 기록만)

- **POST-DEPLOY 필수**: ① PB-0008 실 Windows Chrome 카드 클릭 전환 육안·캡처 ② 배포 후 실제 대화
  1회 → `llm_usage.cache_read_tokens` 에 0 이 아닌 값이 적재되는지 **DB 실조회**(주장한 affordance 를
  실제로 구동해 확인) ③ 캐시 카드가 라이브 데이터로 값을 표시하는지.
- **캐시 지표는 소급되지 않는다** — 배포 직후 0 으로 보이는 것은 정상이며 신규 호출로 채워진다.
- 캐싱 5분 TTL 특성상 **간헐적 대화는 적중률이 낮고 cache write(1.25x)만 발생**할 수 있다. 실제
  적중률은 배포 후 화면의 캐시 읽기/쓰기 비율로 관측 가능하며, 지속적으로 write 편중이면 임계·부착
  위치 재검토가 필요하다(현재는 관측 수단을 갖춘 것까지가 범위).
- 대화 히스토리 incremental 캐싱(마지막 user/assistant 블록 추가 브레이크포인트)은 범위 밖 —
  system 접두 캐싱만으로 이번 요청의 관측 목적은 충족된다.

---

## 20260813T1812 — 공유받은 그룹 대화 폴더 drag&drop (folder-dnd-shared-group)

사용자 요청: "서비스 내 다른 계정으로부터의 그룹 대화 또한, drag&drop으로 폴더 별 이동이 가능하도록
구성해주세요."

### 상태

**완료 — 배포·라이브 검증 종결.** 프론트 게이트 수정 · jsdom 31 PASS · 프론트 `.mjs` 60개 전수 회귀
없음 · main `763ad65d` 배포(web-a·web-b 파리티, 무중단 0건) · **POST-DEPLOY PB-0008 전 항목 PASS**
(공유받은 그룹 대화 `draggable="true"` 라이브 확인 · 폴더 배정/해제 서버 왕복 · 크로스-계정 격리
실측 · `pageerror` 0). Run 기록 = `docs/test-runs.d/REV-20260813T181200-folder-dnd-shared.md`.

### 무엇이 문제였나

폴더 배정은 처음부터 **계정별 오버레이**로 설계됐고(FUNCTION.md REQ-20260723-folder-organize,
ANCHOR §1 "각자 자기 방식대로 정리"), 백엔드 `PATCH /api/conversations/{cid}/folder` 와 '···' 메뉴
'이동' 은 공유받은 그룹 대화를 이미 허용했다. 그런데 사이드바 **드래그 게이트만** 소유자(`mine`)로
좁혀져 있어, 공유 그룹 대화는 폴더 안에 보이면서도 끌 수 없었다 — 표시-집행 불일치 1지점.

### 수정

`isFolderScopedConversation(item)`(owner || is_member) 을 신설해 **폴더 파티션과 드래그 게이트가 같은
판정을 공유**한다. 백엔드·스키마·권한 변경 0.

### Git 동기화 결과

- 커밋: `bb3c6a33` (branch `ai/claude/feature-0024-folder-dnd-shared`) → PR #1257 → main `763ad65d`
- verify-completion: PASS (`--pre-commit feature-0003-agent-web-ui`)
- Push: 완료 / PR #1257 머지 완료 (§16.3 Step 4 조건표 — BLOCKED·Critical/Major 승인 대기 없음)
- main 병합 후 배포: `deploy_scope: included`(FIRST_REQUEST.md 전역) — `sudo make deploy-web-only`
  무중단 롤링 + soak 통과, web-a·web-b `mysql-ai-web:763ad65d`, 엣지 중단 0건
- worktree/branch cleanup: `bin/cycle-finalize.sh --pr 1257` 완료 (REGISTRY Active → Closed)
- 충돌 해결: 없음

### POST-DEPLOY 결과 (visual_verification_scope: always — 2026-08-13, 배포 763ad65d)

라이브 시나리오는 **제품 경로만** 사용해 구성했다(admin 대화 공유 링크 → 테스트 계정 가입·`operator`
부여 → join). admin 계정에는 `is_member` 대화가 0건이라(148건은 관리자 `.any` 열람) DB 직접 조작 없이
실제 "다른 계정으로부터의 그룹 대화" 를 만든 뒤 검증하고, 사후 전량 정리했다.

1. **PASS** — 공유받은 그룹 대화 항목이 라이브 DOM 에서 `conv-item is-other is-group` +
   **`draggable="true"`**. 드래그 → 폴더 헤더 드롭 → 서버 `folder_id=35`, 재로드 후 폴더 하위(22px
   들여쓰기) 유지 + 카운트 배지 1. 증적 `docs/test-runs.d/evidence/folder-dnd-shared-in-folder.png`.
2. **PASS** — root 드롭 존(헤더 폴더 아이콘) 힌트 "여기로 놓으면 폴더에서 빼기" + 서버 `folder_id=null`.
3. **PASS** — admin 재로그인 시 `GET /api/folders`=`[]`(테스트 폴더 미노출), 같은 대화의 admin 관점
   `folder_id=null` → 폴더 이름·구조·배정이 소유자 뷰에 새지 않음.
4. **PASS** — `error`·`unhandledrejection` 리스너로 드래그 왕복 2회 수행, 오류 0건.
5. 채널 한계 — OS 레벨 native drag 는 재현하지 않았다(CDP `Input.dispatchDragEvent` 미사용). native
   경로와 합성 `DragEvent` 경로의 유일한 분기점인 `draggable` 속성 부여를 라이브 DOM 으로 확인했다.

### 잔여 리스크 · 후속 (§8.1 — 기록만)

- **선재 결함(본 cycle 범위 밖)**: 관리자 `.any` 열람 "타 계정 대화" 는 '···' 메뉴 '이동' 이 노출되고
  서버 배정도 성공하지만, 그 그룹은 폴더 파티션 대상이 아니라 **폴더 하위에 렌더되지 않는다**(무음
  실패). 해소 방향 두 가지 — ⓐ 그 그룹에서 '이동' 항목을 숨김 ⓑ 폴더 파티션을 `.any` 열람까지 확대.
  폴더가 개인 오버레이라는 설계상 ⓐ 가 정합적이나 사용자 결정 사항이라 기록만 한다.
- 릴리즈노트(in-app `release-notes-data.js`)는 큐레이션 대상 — 본 변경은 `release_notes_scope` 미선언
  이므로 이번 cycle 에서 기재하지 않았다(doc_sync 소관).
- 다중 선택 드래그(여러 대화 한 번에 폴더 이동)는 범위 밖 — 멀티선택은 여전히 자기 대화 전용.

---

## 20260813T1930 — 그룹 멤버 프론트 권한 게이트 정합 (member-scope-gates)

> ⚠ **정정됨 (2026-08-13, `20260813T2010-member-leave-branch`)** — 아래 A-1~A-4 서술의 전제가 틀렸다.
> `can(permission)` 은 인자를 버리고 로그인 여부만 반환하므로(display-permissive) 중단·즉시답변·
> 연장은 멤버가 **원래 막히지 않았고**, 그 predicate 교체는 no-op(의미 명료화)이다. "연장 배너가
> 떠도 승인 불가 → 타임아웃" 은 사실이 아니다. 실효 결함은 (a) B 축 오도 안내 2건 (b) 설정 팝업의
> **보관/나가기 분기 사망**(멤버 나가기 경로 부재)이며 (b) 는 후속 cycle 에서 수정했다. 정정 상세 =
> 아래 `## 20260813T2010` 섹션 · `docs/LEARNINGS.md LRN-20260813-display-permissive-can-invalidates-gate-audit`.

사용자 감사 요청: "별도로 표시-집행 불일치가 나타나는 부분이나, 소유자가 과도하게 좁혀진 이슈가
나타난 부분이 있는지 검토해주세요." → 감사 후 사용자가 **A+B+C 수정 범위 승인**.

### 감사 방법

백엔드 `_account_can_access_conversation` 호출 **33지점을 전수 스캔**해 각 라우트의 2차 owner 게이트
(`_conversation_owned_by_account` / `_conversation_owner_account_id`) 유무로 분류하고, 프론트 게이트
(`requiredPermissionsFor` · `can*Conversation` · 안내문 조건)와 대조했다. `operator`(일반 사용자)
역할 시드 권한(`.own` 보유 / `.any` 미보유)까지 확인해 실제로 차단이 발생하는지 판정했다.

### 확정된 결함 (수정 완료)

| # | 증상 | 서버 | 프론트(수정 전) |
|---|---|---|---|
| A-1 | 멤버가 자기 run **중단** 불가 + "권한 없음" 거짓 사유 | 멤버 허용 | owner-only |
| A-2 | **즉시 답변** 불가 | 멤버 허용 | owner-only |
| A-3 | **실행시간 연장** — 배너는 뜨는데 승인 불가 → run 타임아웃 | 멤버 허용 | owner-only |
| A-4 | `···` > **설정** 차단 → **그룹 대화 나가기 UI 경로 소실** (+ 토스트 사유 "공유 링크 관리") | 멤버 허용(self-leave 명시) | owner-only |
| B | 멤버에게 "읽기 전용 / 조회만 가능" 오도 안내 2지점 | 발화 허용 | `!isOwnConversation` |
| C | `canAskInConversation` 멤버 누락(dead 경로라 실효 0, 재사용 시 폭발) + dead `disabled` 변수 | — | — |

### 수정

`isOwnScopeConversation`(owner ‖ `is_member`) 신설 + `requiredPermissionsFor` 가 `own`/`ownScope`
두 변수를 분리 보유. 서버가 2차 owner 게이트를 두는 액션(rename·delete·duplicate·joinable·shares)은
`own` 유지 — **비대칭이 정답**이며 그 분기 개수까지 구조 테스트가 센다.

### Git 동기화 결과

- 커밋: (본 cycle) — branch `ai/claude/feature-0003-member-scope-gates`
- verify-completion: PASS (`--pre-commit feature-0003-agent-web-ui`)
- Push / PR / main 병합: §16.3 Step 4 조건표 자동 (BLOCKED·Critical/Major 승인 대기 없음)
- 배포: `deploy_scope: included`(전역) 에 따라 이어서 수행
- 충돌 해결: (핫스팟 경고 — 같은 파일 편집 중인 활성 브랜치 2개, 머지 시점 확인)

### POST-DEPLOY 필수 (visual_verification_scope: always)

멤버 계정으로 라이브 실측: ① 중단 버튼 활성 + 클릭 시 서버 취소 ② 즉시 답변 버튼 활성
③ `···` > 설정 팝업 열림 + '나가기' 노출 ④ "읽기 전용 대화" 안내 미표시 ⑤ 제목 변경·보관은 여전히
차단(대조군) ⑥ `pageerror` 0.

### 잔여 리스크 · 후속 (§8.1 — 기록만, 사용자 승인 범위 밖)

- **D-1**: `buildPermissionPills`(app.js) 가 `state.user?.permissions` 를 읽지만 `/api/session` 은 그
  맵을 직렬화하지 않고(TASK-0098 의도) **호출처도 없다**(dead). 되살리면 항상 "활성 권한 없음" —
  삭제 후보.
- **D-2**: 대화 검색 결과 배지가 멤버 대화를 "타 계정" 으로 표기(사이드바는 내 대화 파티션) — 라벨
  불일치, 코스메틱.
- **D-3**: 관리자 `.any` 열람 대화의 `···` > '이동' 은 서버 배정이 성공해도 폴더 하위에 렌더되지
  않는다(무음 실패) — 숨김 vs 파티션 확대는 사용자 결정 필요.
- 실행시간 연장의 타임아웃 실피해는 코드 경로 대조로 확정했고, 타임아웃까지 기다린 라이브 재현은
  하지 않았다.

---

## 20260813T2010 — 감사 결론 정정 + 멤버 '나가기' 분기 복원 (member-leave-branch)

### 정정 (선행 cycle 의 오진)

`can(permission)` 은 `void permission; return Boolean(state.user)` — 인자를 버린다(TASK-0098
display-permissive "넓게 표시 + 백엔드 403"). 따라서 선행 cycle 이 "확정 결함" 으로 보고한
**중단·즉시답변·실행시간 연장은 멤버가 원래 막히지 않았다**. 그 predicate 교체는 동작 무변화
(의미 명료화)이며, "연장 배너가 떠도 승인 불가 → run 타임아웃" 은 **사실이 아니다**. 실효였던 것은
오도 안내 2건(`isOwnConversation` 단독 조건 — `can()` 무관)이고, 라이브에서 소거를 확인했다.

오진 원인: 판정 함수(`can()`)의 정의를 확인하지 않고 코드 대조를 "확정" 으로 불렀다. 재발 방지는
`docs/LEARNINGS.md` `LRN-20260813-display-permissive-can-invalidates-gate-audit`(규칙 5개).

### 그 오진이 가리고 있던 실효 결함 (본 cycle 수정)

같은 `can()` 특성 때문에 '대화 설정' 팝업의 `canArchive` 가 항상 true → 코드 주석이 설계한
"멤버에게는 보관 대신 '나가기'" **분기가 죽어 있었다**. 라이브 실측(멤버 계정):

- 팝업 `dangerBtn.textContent === "보관"`, 팝업 내 '나가기' 문구 **부재**
- `POST /api/delete_conversations` → `failed:[{reason:"forbidden"}]` (보관 안 됨)
- `PATCH …/title` → `403 "소유자만 대화 제목을 변경할 수 있습니다."`

→ 멤버는 그룹 대화를 **나갈 UI 경로가 없었다**(서버는 self-leave 를 허용하는데도). 판정을
`isOwnConversation(conversation) || canOpenAdminConsole()` 로 교체해 복원.

### 테스트 측 교훈 (거짓 PASS 2회)

기존 `verify_settings_archive_leave.mjs` 는 `includes("canDeleteConversation(conversation)")` 로
"그 함수를 쓴다" 만 잠갔다 — 함수가 상수 true 라 분기가 죽는다는 사실은 문자열로 볼 수 없다.
정정 중에는 **내가 쓴 주석의 구 코드 인용**이 같은 단언을 또 통과시켰다. 두 지점 모두 **주석 제외
코드 라인만** 검사하도록 바꾸고, 행위(렌더된 라벨 + 호출된 액션)를 잠그는 실 DOM 테스트를 신설했다.

### Git 동기화 결과

- 커밋: (본 cycle) — branch `ai/claude/feature-0003-member-leave-branch`
- verify-completion: PASS (`--pre-commit feature-0003-agent-web-ui`)
- Push / PR / main 병합: §16.3 Step 4 자동 · 배포: `deploy_scope: included`

### POST-DEPLOY 결과 (2026-08-13, 배포 `660e9fcf` — 전 항목 PASS)

① 멤버 계정 '설정' 팝업 danger 버튼 = **'나가기'** + 안내 "이 그룹 대화에서 나갑니다…"
(증적 `docs/test-runs.d/evidence/member-leave-btn-live.png`) ② 클릭 → self-leave 수행 → 대화가
목록에서 사라짐 + `…/members` 404 ③ 소유자(admin)는 같은 팝업에서 **'보관'** 유지(분기 양방향 정확)
④ `pageerror` 0. 선행 B 축(오도 안내 소거)도 같은 계정에서 재확인. 테스트 데이터 정리 완료.

### 잔여 (§8.1 — 기록만)

- 제목 입력이 멤버에게 활성이고 서버 403 — display-permissive 컨벤션상 의도된 현 동작(테스트로 고정).
  UX 를 더 정확히 하려면 per-code `can()` 도입이 필요하고, 그건 TASK-0098 결정을 되돌리는 별 작업이다.
- 선행 cycle 의 D 항목(dead `buildPermissionPills` · 검색 배지 라벨 · `.any` 대화 폴더 '이동' 무음
  실패)은 여전히 미해결 — 사용자 결정 대기.

## 20260814T0100-attach-version-branching — 첨부 버전 계보를 작성 주체별로 분기

사용자 요청("첨부 버전 관리를 사용자별 트리로 — assistant 도 독자적인 버전 관리")의 산출.
assistant 수정본이 사용자 계보에 `v+1` 로 편입되고 사용자 최신본을 supersede 하던 구조를,
**작성 주체별 별도 계보**로 나눴다(스키마 변경 0 — 분기 지점은 MetaJson). 사용자 후속 결정에 따라
"최신" 의 두 축(**계보 내** / **시간순**)을 프롬프트 계보 블록과 API `lineages` 로 함께 노출한다.

### 잔여 (§8.1 — 기록만)

- **버전 모달 기준 토글 UI 미구현**: API 축(`lineages`)은 실렸으나 `attach-diff.js` 는 아직 계보 내
  축만 그린다. 목록에서는 기존 `AI 수정` 배지로 계보가 구분돼 보이므로 사용자가 막히지는 않는다 —
  트리 시각화·기준 토글은 후속 cycle 대상.
- **업로드 경로의 INSERT↔supersede 비원자성(선재 결함, 적대 리뷰 [P1] 지적)**: 새 row 를 commit 한
  뒤 supersede 하고 그 실패를 삼켜, 같은 체인에 live head 가 둘 남을 수 있다. 이번 cycle 은 신규
  조회가 그 상태를 **두 계보로 오인하지 않도록**(root 당 1건 dedupe) 방어만 했다. 근본 해소는 두
  문장을 한 트랜잭션으로 묶는 별 작업이며 업로드 경로 회귀 검증이 따로 필요하다.
- **기존 혼합 체인 39건 미백필**(사용자 결정): 과거 이력은 있는 그대로 둔다. 새 수정본부터 분기.

### usage-records-sort-page (2026-08-14) — '사용 기록' 표 정렬·페이지네이션

사용자 요청("사용 기록 표를 column 에 따라 정렬 + 페이지네이션")의 산출. 표시층 단독 변경으로,
백엔드 엔드포인트·집계·RBAC·응답 스키마는 건드리지 않았다. 정렬·페이징은 이미 받은 결과셋
안에서 클라이언트가 처리하며, 서버가 상한으로 절단했다는 사실은 종전대로 문구로 밝힌다.

구현 중 jsdom 하네스가 결함 1건을 적발했다 — 정렬이 `merged` 배열의 순서를 바꾸는데 시스템 행의
화면 이동(nav)을 그 배열 인덱스로 되짚고 있어, 정렬 후에는 다른 객체의 관리 화면으로 이동했다.
불변 색인으로 수정하고 구조 잠금 테스트를 걸었다.

#### 잔여 (§8.1 — 기록만)

- **PB-0008 라이브 실측은 배포 후**: sticky 열 머리 안의 정렬 버튼 렌더, 정렬 전환 시 열 폭 안정성,
  페이저 배치는 jsdom 이 보지 못한다. 배포 뒤 실 Windows 브라우저로 확인하고 TEST.md 에 기록한다.
- **profile(self) 판 미적용**: 작업 화면의 본인 사용량 모달(`app/profile.js`)은 독립 구현이라 이번
  범위 밖이다. 요청이 관리 콘솔 표를 지목했고, self 판은 본인 대화 범위라 행 수도 훨씬 적다.
  필요해지면 같은 패턴을 옮기면 된다.

#### usage-records-sort-page POST-DEPLOY 종결 (2026-08-14, fce6d64c)

정렬·페이지네이션·nav·키보드·페이저 가시성 전 축을 실 Windows 브라우저에서 확인했다(TEST.md
POST-DEPLOY Run). 라이브에서 나온 결함 1건(페이저가 50행 아래에 숨음)은 후속 cycle 로 즉시 해소.

이월:
- **열 폭 재계산(≤4%)**: 정렬·페이지 이동으로 표시 행이 바뀌면 auto table-layout 이 열 폭을 다시
  잡는다. 기능 결함은 아니나 페이지 전환 시 표가 미세하게 움찔한다. 고정하려면 현재의 열 폭 배분
  전략(부수 열 `width:1%` + 본문 열이 잔여 흡수)을 `table-layout: fixed` + colgroup 으로 바꿔야
  하고, 그건 본문 열 붕괴(과거 실측 결함)를 다시 부를 수 있어 별도 검증이 필요하다.
- **profile(self) 판 미적용**: 작업 화면의 본인 사용량 모달은 독립 구현이라 정렬·페이징이 없다.

### profile-usage-sort-page (2026-08-14) — 프로필 사용 내역 표 정렬·페이지네이션

관리 콘솔 '사용 기록' 표와 같은 조작을 작업 화면 프로필 판에도 적용했다. 두 모달은 독립 구현이라
로직을 옮겨 심되, 규칙 동일성(기본 정렬·첫 클릭 방향·페이지 크기·포커스 복원)은 **테스트가 두
소스를 대조해** 잠갔다 — 한쪽만 바뀌면 red.

부수적으로 두 화면 공통 결함 2건을 함께 고쳤다: 작은따옴표 속성 이스케이프 누락(관리 콘솔은 타인
대화 제목을 보므로 stored 경로 실재), sticky 열 머리가 실제 스크롤러에 붙지 않던 문제.

#### 잔여 (§8.1 — 기록만)

- **요청-응답 경합(선재, 양 화면 공통)**: 차트를 클릭해 로딩 중 다른 차트를 클릭하거나 모달을
  닫으면, 먼저 보낸 요청의 응답이 나중에 도착해 현재 모달을 덮거나 닫은 모달을 되살릴 수 있다
  (`openUsageConversations` / `openProfileUsageConversations` 둘 다 요청 세대를 추적하지 않는다).
  이번 변경이 만든 것이 아니고, 한쪽만 고치면 두 화면 규칙 정합이 깨져 **양쪽을 함께** 다뤄야 한다.
  요청 범위 밖이라 이월한다.
- **좁은 폭 페이저 축의 검출력 부재**: `verify_usage_pager_layout.py` L2 는 줄바꿈을 제거한
  뮤턴트도 통과한다 — 현재는 회귀 가드일 뿐 결함을 잡는 축이 아니다(정직 표기).
- **열 폭 재계산(≤4%, 직전 cycle 이월 유지)**: 페이지 전환 시 auto table-layout 이 열 폭을 다시 잡는다.

#### profile-usage-sort-page POST-DEPLOY 종결 (2026-08-14, ac1403c4)

프로필 판의 정렬·페이지네이션·키보드·sticky 열 머리, 그리고 관리 콘솔 판의 재확인(스크롤러
단일화 영향 + 가로 넘침 무회귀)을 실 Windows 브라우저에서 확인했다(TEST.md POST-DEPLOY Run).
두 화면이 같은 규칙으로 동작함을 라이브에서 확증했다.

### step-panel-timing (2026-08-14) — 실행 단계 패널에 단계별 시각·간격·누적 경과 표기

실행 단계 사이드 패널의 각 단계 카드 헤더 우측에 `기록 시각(HH:MM:SS) · +직전 간격 · 누적 경과`
를 표기했다. 데이터는 새로 만들지 않았다 — 모든 단계는 이미 PG `agent_runtime.steps.created_at`
(timestamptz, DB 기본값)을 갖고 있고 라이브 폴링·완료 조회·히스토리 전 경로가 이 값을 프론트에
실어 나르고 있었다. 따라서 backend 무변경이고, **과거 대화의 단계도 소급 표기**된다.

구현에서 사실 기반 표기 원칙을 지켰다: created_at 은 "단계가 기록된 시각"(activity=착수 시점,
tool=결과 확보 시점)이므로 간격은 '직전 기록→이 기록 사이 경과'로 정의했다 — 작업별 순수
소요시간을 단정하는 표기가 아니다(툴팁에 의미를 명시). created_at 이 경로에 따라 ISO "T" 와
psycopg 공백 표기 두 가지로 도착하는 것을 파싱 폴백으로 흡수했고, 시각이 없는 레거시 단계는
표기를 생략한다(fail-soft — 표기 실패가 패널 렌더를 깨지 않는다).

"기존 텍스트와 충돌 금지" 요건은 CSS 계약으로 보장했다: 시간 요소는 `margin-left:auto` 우측
정렬 + `nowrap`, 헤더는 `flex-wrap:wrap` — 패널이 좁아지면(최소 300px) 겹치는 대신 자기 줄로
내려간다. 폴링 재렌더마다 숫자가 갱신되므로 `tabular-nums` 로 폭 흔들림도 막았다.

**POST-DEPLOY 실측 (2026-08-14 19:2x, 라이브 `ee4eb08d`)** — 배포 직전 남겨 둔 PB-0008 시각검증을
실제 Windows Chrome/150 으로 닫았다. 검증 축 4건 전부 PASS: 헤더 우측 정렬 13/13 편차 `0.00px` ·
리사이저를 실제로 끌어 도달한 최소 폭 300px 에서 겹침·가로스크롤 0 · 폭이 모자란 경계에서는
겹치는 대신 자기 줄로 하강(top 2→25px) · 라이브 run 진행 중 패널을 **재오픈하지 않고** 폴링
재렌더만으로 3→4단계 갱신(새 라벨 `19:26:39 · +7.4초 · 누적 8.1초`, 누적 단조) · 2026-08-14
완료 대화의 13단계 전부에 소급 표기(backend 무변경 주장의 실증). 판정은 시나리오가 하고
(표기 정규식·기하·computed CSS 계약), 근거는 라이브 패널 DOM 을 2.2× 확대한 판독 가능한 캡처로
남겼다 — 패널이 뷰포트의 300~340px 조각이라 전체화면 캡처만으로는 10.5px 표기를 읽을 수 없다.
축 ③ 은 합성으로 대체 불가라(폴링 갱신이 `state.stepSidePanelLive` 게이트 뒤) 참여자가 나뿐인
**새 대화**에 질의 1건을 보냈다 — 타 세션·공유방 무접촉. 상세는 `TEST.md` POST-DEPLOY Run.

### Git 동기화 결과 (POST-DEPLOY cycle)
- 커밋: (본 cycle commit) — `ai/claude-corp/step-panel-timing`
- verify-completion: PASS
- Push: 완료
- main 병합: PR 로 진행
- 충돌 해결: 없음

### step-timing-attribution (2026-08-24) — 단계 시간이 한 칸씩 밀려 표기되던 오귀속 해소

`step-panel-timing` 이 넣은 `+직전 간격` 표기는 **구조적으로 한 칸 밀렸다**. step 은 종류마다
기록 시점이 반대이기 때문이다 — 내부 동작은 LLM 호출 *직전*(착수 시각), 도구는 결과를 받은
*뒤*(종료 시각). 그래서 `내부동작 → 도구` 간격에는 추론 시간과 도구 시간이 함께 들어 있는데
그것을 통째로 도구에 붙이면서, 0.4초짜리 SQL 이 "2분 3초" 로 보이고 정작 2분을 쓴 추론 단계는
"0.0초" 로 보였다. 사용자가 이것을 보고 알려 줬고, 추정하지 않고 라이브 run
`20260824021929-c71393cf` 의 원본 `created_at` 을 직접 세어 확인했다(도구→도구 간격만 정확했다).

**고친 방식**: 표시층에 근거를 하나 더 준다. 백엔드는 도구 실행 시간을 이미 재고 있었으므로
(`duration_breakdown` 계측) 그 값을 `result_summary.elapsed_ms` 로 실어 보낸다 — 새로 재지
않고, 스키마·마이그레이션·웹 쿼리도 건드리지 않는다(`result_summary` 는 이미 두 DB 백엔드와
3개 조회 경로를 전부 통과하는 표시층 부가정보 모음이다). 프론트는 `_computeStepTimings` 로
간격을 **그 동안 실제로 돌던 단계**에 귀속한다: 도구는 자기 실측, 내부 동작은
`t다음 − t자신 − 다음도구실측`.

**모르는 값을 지어내지 않는 것이 이 변경의 핵심 규율이다.** 실측이 없는 과거 대화에서
`내부동작→도구` 구간은 두 시간이 섞여 있어 분리할 수 없다 — 그래서 도구의 소요 칸을 **비우고**
툴팁이 사유를 밝히며, 내부 동작 소요는 도구 실행분이 섞인 근사임을 `~` 로 표시한다. 반대로
`도구→도구`·`내부동작→내부동작` 은 실측 없이도 정확하므로 그대로 보여 준다. 표기도
`시작 시각 · 이 단계 소요 · 누적` 으로 바꿔, 누적은 각 단계의 **종료 시점** 기준이라 단조 증가한다.

`result_summary` 를 dict 로 강제 생성하는 부분이 기존 소비자를 깨지 않는지는 소스로 확인했다 —
프론트 결과 박스는 `tableEl || preview` 로 **내용 기반** 게이트라 `{elapsed_ms}` 만으로는 열리지
않고, `_step_csv_paths`·`normalize_step_result_summary` 도 키 기반이라 영향이 없다.

### Git 동기화 결과 (step-timing-attribution)
- 커밋: (본 cycle commit) — `ai/claude-corp/step-timing-attribution`
- verify-completion: PASS
- Push: 완료
- main 병합: PR 로 진행
- 충돌 해결: 없음

## 2026-08-27T16:05:00+09:00 — 브리지 답변 직후 스크롤 최하단 고착 해소 (TASK-20260827T160500-bridge-progress-scroll)

**상태: 코드 완료 · 라이브 배포 검증 대기** (BLOCKED 없음)

- **증상**: 개인 AI 연결 상태에서 질문→답변 직후 화면이 반복해서 맨 아래로 끌려가 스크롤을 붙잡을
  수 없다(약 3분 지속).
- **원인**: 브리지 답변 전달 직후 심기는 사후 원장 step(`work_source='bridge-ledger'`)을
  `/api/progress` 의 steps fallback 이 "진행 중" 으로 오독 → `/api/history`(유휴)와 갈림 →
  프런트 감지기가 `loadHistory()`(preserveScroll 없음)를 지연 0ms 로 반복 위임.
- **수정**: ① fallback 집계에서 원장 제외(WHERE 절) ② 감지기의 재로드 위임을 `(대화, run)` 안에서
  **이미 본 국면당 1회**로 수렴(국면 전이는 통과, 국면 흔들림·빈 응답에도 안전).
- **검증**: `make test` exit 0 · 하네스 57/0 + 46/0 · main baseline 대비 mjs 회귀 0 ·
  뮤테이션 3종 KILL · codex 적대 리뷰 5R(P1 3·P2 3 전건 수정, 잔여 0).
- **잔여**: 배포 후 라이브 재확인 + PB-0008 실 Windows 브라우저 Run 기록
  (`docs/test-runs.d/REV-20260827T160500-bridge-progress-scroll.md`).
- **남은 리스크**: 없음(비파괴·읽기 경로). 브리지 원장 자체는 보존되며 말풍선 '단계 보기' 는
  `_load_steps_for_message`(메시지 `meta.run_id`) 경로라 영향 없음.

## 2026-08-27T17:55:00+09:00 — 위 cycle 라이브 배포 검증 완료 (TASK-20260827T160500-bridge-progress-scroll)

**상태: 완료** (BLOCKED 없음)

- 배포: `make deploy-web` exit 0 · 전 서비스 `GIT_COMMIT=eb6412ad` · 배포 창 caddy
  `no upstreams available` **0회**(무중단 실측).
- 라이브 실측(배포본 직접 호출): `_load_latest_run_id_from_steps('20260827061652-5ab532d1')`
  `('t_LBtWKW0f1sBBfGK-', False)` → **`('', False)`** (web-a/web-b 동일). 브리지 원장 19행은
  그대로 보존 — 'AI 추론' 표면 영향 0.
- PB-0008(실 Windows Chrome 151, relay): 라이브 도달성 PASS · 서빙 `app.js` 에 최종 설계 baked
  확인 PASS. **로그인 후 대화 화면 실측은 미수행** — 브라우저 프로파일에 세션이 없고 자격증명
  미보유(사유는 `docs/test-runs.d/REV-20260827T160500-bridge-progress-scroll.md` §5.3).

### 8. 개선 제안 (§8.1 — 기록만, 사용자 지시 없이 실행 안 함)

- **`bin/win-browser.py` 의 Windows host 오탐**: `win_host_ip()` 가 `/etc/resolv.conf` 의 **첫
  nameserver** 를 Windows host 로 쓴다. 이 머신은 첫 nameserver 가 `8.8.8.8`(공용 DNS)이라
  relay 를 엉뚱한 주소로 겨냥해 `launch` 가 `bridge_unreachable` 로 실패한다. 실제 WSL
  게이트웨이 `172.26.144.1` 로는 CDP 가 정상 응답하므로, 첫 nameserver 가 기본 게이트웨이와
  다른 서브넷이면 `ip route show default` 로 폴백하도록 보정하면 PB-0008 진입 마찰이 사라진다.
  (본 Run 은 그 우회 경로로 수행했다.)
- **PB-0008 로그인 세션 부재**: 검증용 브라우저 프로파일에 세션이 없어 로그인 후 화면 실측이
  구조적으로 막힌다. 전용 검증 계정 또는 세션 부트스트랩 절차가 있으면 웹/UI cycle 의 완료
  게이트가 실효를 갖는다.

## 2026-08-31T18:30:00+09:00 — 연결 성립 시 토스트 + 모달 자동 닫기 (TASK-20260831T1827-connect-modal-autoclose)

**상태: 완료** (BLOCKED 없음) — PR #1447 머지(`0fad9129`) → 라이브 배포 → POST-DEPLOY 실측 PASS

- 사용자 요청: 「'내 AI 연결하기' 과정을 통해 정상적으로 연결이 진행되었을 경우 정상적으로
  연결되었다는 토스트 메세지 출력과 함께 모달을 닫도록」
- 변경 범위: `static/app/connect-modal.js` 1파일 + 신규 테스트 1파일. 서버·스키마·권한 변경 0.
- 판정 시점을 **「대기 중이 됨」(`listening: true`)** 으로 두었다. 「연결 준비」로 토큰이
  발급된 시점에 닫으면, 모달이 스스로 "이 창을 닫으면 다시 볼 수 없습니다" 라고 알린 그 명령이
  사라지는데 정작 연결은 아직 아무 일도 일어나지 않는다.
- **라이브 결함 재현(PB-0008, 배포본 `1c0864dc`)**: 배지가 «내 AI 대기 중» 으로 바뀌어도 모달이
  그대로 남고 알림 0 — 그 모달이 바로 그 배지를 덮고 있다. 스크린샷 1장으로 확인.
- **POST-DEPLOY 실측 PASS**(배포본 `0fad9129`, 자산 `?v=16960c2c319d`): 전이 후
  `modal_hidden:true` + 토스트 「내 AI가 연결되었습니다…」 + 배지 «내 AI 대기 중» + 입력창 해제.
  무중단 blip 0 · 대화 스모크 PASS · web-a/b 둘 다 `0fad9129`.
- 검증: 신규 행위 테스트 **25/0 PASS** · **수정 전 코드에서 7건 FAIL 실증**(G11-b) ·
  뮤테이션 9종 역검증 · **codex 적대 리뷰 3라운드 최종 P1 0**(1R BLOCK → 2R 승인불가 → 3R PASS).
  1R 의 P1 2건은 뿌리가 같았다 — **닫기 판정이 두 곳에 있었다**. 판정을 한 곳으로 모으고,
  창보다 오래 사는 대기 루프에 창 세대 검사를 두어 해소했다.

### 남은 리스크 / 후속

- **실 러너 end-to-end 미수행**: 서버가 스스로 `listening:true` 를 내는 경로(개인 머신에 AI CLI
  설치·인증 후 러너 기동)는 AI 무인 완결이 불가해 검증하지 않았다. 이번 검증은 「서버가 그 값을
  줄 때 화면이 어떻게 반응하는가」라는 프론트엔드 계약에 한정되며, 그 사실을 완료로 오인 보고하지
  않는다. 서버가 그 필드를 내는 계약 자체는 이번 변경 이전부터 같은 코드가 소비하던 것이다.
- 폴링 축이 하나 늘었다(모달 열린 동안 5초). 닫으면 즉시 멎고(타이머 계측으로 잠금), 잠기지
  않은 사용자에게 요청 0인 기존 계약은 유지된다.
- **`_gateInFlight` 해제 전용 단언 없음**(codex 3R 잔여 P2) — 폴링 간격 5초를 테스트에서
  발화시킬 수단이 없다. 코드 방어(`_raceTimeout` 상한)는 넣었으나 그 방어를 겨누는 단언은 없다.
- **`ux`/`design` 도메인 심사 미수행** — 세션 도구 제약(§18.8.2 carve-out).
  `[SKIPPED:tool-restricted:ux-design]` 로 명시.

## 2026-09-01T03:30:00+09:00 — 실행 성공인데 창이 안 닫히던 회귀 정정 (TASK-20260901T0330-connect-modal-launch-close)

**상태: 완료** (BLOCKED 없음) — PR #1456 머지(`ead6e30f`) → 배포 → POST-DEPLOY 실측 PASS

- **사용자 제보**: 「내 AI가 대기 중입니다. 이제 질문을 보낼 수 있습니다.」 를 받았는데 모달이
  닫히지 않았다. 그 문구는 `[내 AI 실행]` 대기 루프에서만 나온다.
- **원인은 직전 cycle 의 내 수정이다.** codex P1-2 를 수용하며 적용 범위를 넓혀, 사용자가 직접
  누른 실행까지 자동 경로의 기준선에 묶었다. 창을 열 때 이미 «대기 중» 이면 전이가 아니므로
  아무도 닫지 않는다 — 성공을 말하면서 아무것도 하지 않은 것이다.
- **정정**: 실행 성공 분기가 다시 알리고 닫는다 + 그 분기에 창-세대 검사를 두어 «남의 창» 을
  닫지 않게 한다. 기준선은 자동 관측 경로에만 남는다.
- 검증: 25/0 PASS · 제보 재현 H3·H4 가 **라이브 배포본에서 FAIL** · 뮤테이션 8종 ·
  codex 독립 확인 **P1 0**(트레이드오프 타당 판정).

### 남은 리스크

- 남의 러너로 인한 오닫힘은 원리적으로 남는다(서버가 러너 소유를 구분해 주지 않는 한).
  의식적 트레이드오프이며 「연결 준비」 재클릭으로 복구된다.

### POST-DEPLOY (2026-09-01T04:05)

배포본 `ead6e30f`(자산 `?v=caa9885f1a64`)에서 **제보 경로를 그대로 클릭**해 확인했다 — 이미
«내 AI 대기 중» 인 상태에서 모달을 열고 「연결 준비」 후 `[내 AI 실행]` 클릭 → `modal_hidden:true`
+ 토스트 「내 AI가 연결되었습니다…」. 제보하신 「대기 중입니다」 문구는 통로가 합쳐지며 사라졌다.
무중단 blip 0. 증적: `docs/test-runs.d/…-launch-close-postdeploy.md` +
`docs/evidence/connect-modal-autoclose/pd2-*.png`.

## 2026-09-01T05:30:00+09:00 — 명령 경로·«업데이트 필요» 갱신도 닫히도록 판정 축 교체 (TASK-20260901T0530-connect-modal-transition)

**상태: 완료** (BLOCKED 없음) — PR #1481 머지(`17d36ad8`) → 배포 → POST-DEPLOY 실측 PASS

- 사용자 요청 2건(명령 경로 재연결 · «업데이트 필요» 갱신)이 **같은 뿌리**였다: 기준선을
  «창을 열 때 고정» 한 것과, 판정 축이 `listening` 한 축뿐이었던 것.
- 기준을 **직전 관측**으로, 축을 **«쓸 수 있는 상태»**(`listening && !runner_stale`)로 올려
  두 경로를 한 규칙으로 덮었다. 문구도 «연결» / «갱신» 으로 나눴다.
- codex 1R 이 **P1 1건**(늦은 응답이 다음 창의 직전 관측을 오염 → 일어나지 않은 전이)을 잡았고,
  창 세대가 다르면 기록조차 하지 않도록 고친 뒤 2R **P1 0**.
- 검증: 39/0 PASS · **라이브 배포본에서 6건 FAIL**(제보 재현) · 뮤테이션 4종 KILL.

### 남은 리스크

- 실행 경로의 문구 분기·`_lastObserved.ok` stale 검사는 미잠금(자동 경로가 먼저 판정을 끝내
  도달 희박 — 방어적 중복).
- 남의 러너로 인한 오닫힘은 그대로 남는다(서버 `listening` 이 계정 단위).

### POST-DEPLOY (2026-09-01T06:10)

배포본 `17d36ad8`(자산 `?v=6dcb74cd1d37`)에서 **요청 두 경로를 각각** 확인했다.
A(명령 재연결): 열림 유지 → 끊긴 동안 유지 → 재연결 후 닫힘 + 「연결되었습니다」.
B(«업데이트 필요» 갱신): 갱신 후 닫힘 + 「최신으로 갱신되었습니다」 — 문구가 상황을 따라간다.
무중단 blip 0. 증적: `docs/test-runs.d/…-transition-postdeploy.md` + `docs/evidence/…/pd3-*.png`.

## REPORT-20260907T181510-kb-external-search

기존 로컬 LLM 철거 작업(ADR-20260907T175000-local-llm-decommission-scope-boundary)에 이어,
검색 근거를 사용자가 선택한 기존 Claude/Codex 연결로 전달했다. 샘플 로더의 vector 필수
조기 반환과 편집 후 embedding 실패→stale 강등이 연결 단절 원인이었다. 문자 검색과 SQL
신선도를 분리하고, 기존 제품/대화 권한을 재확인하는 외부 claim/focus 경로에 연결했다.

R1에서 legacy DB prefix 충돌을 발견했다. 독립 DB provenance가 없는 저장소에 대해 MySQL
키의 모든 가능한 DB 접두를 인가하도록 고쳤으며, MSSQL 레거시·불명확 키는 제외하고 기존
구조 조회 도구를 안내한다. 기존 벡터/볼륨은 일괄 삭제하지 않는다. 질문 수정에 따른 해당
벡터 무효화는 유지한다. 문자 검색을 의미검색 복구로 보고하지 않는다.

최종 격리 PG/회귀 203 PASS. 운영 RO 실측은 test-runs.d 기록 참조. backend/security R2
P1 0, QA R3 P1/P2 0. Git 동기화·배포 결과는 이슈 #1598에 연결되는 PR 본문에 기록한다.
정책 hash: 8e7d65bd9d31b1013ef522b762abbc62fb023ef8c358a92e46ab567eac277770.
작업 worktree: .worktrees/feature-0002-kb-external-search; 공개 branch: issue/1598-kb-external-search.

### Git 동기화 결과
- 코드/검증/문서를 함께 commit/push하고 PR에서 병합·배포 결과를 기록한다.
- 기존 main의 .codex/config.toml 및 untracked source-command skills는 유지한다.

### 전체 CI 대체 및 통합
- origin/main067e4a58 통합(50e1c94a). 문서 충돌은 양쪽 기록 보존. 제품 KB 구현 충돌 없음.
- 로컬 전체7485 PASS/28 skip, 옛 구획 assertion1건은 테스트 정합 후 해당suite19 PASS.
- 전체ruff0, migrate-lint/head/code navigation PASS. GitHub runner는 billing 차단으로 미실행.
- 최종 Git·배포 상태: PR #1599 본문에 기록(AGENTS §16.3 결과 기록의 PR 정본 허용).

## TASK-20260908T120000-runner-update-recovery — 러너 경합·종료 복구

갱신 실패 시 사라진 1단계 명령을 가리키던 안내를 DQA 앱 업데이트 확인·최신본 설치·재연결로 교정한다. 동일 지문 관측만으로 낡은 실행 스크립트가 원인이라고 단정하던 문장도 제거한다.

Windows CPython 3.14.7에서 직접 재실행/클라이언트 감독 × 동시/교차 갱신 4개 조합 모두 **2/2 복귀**, 각 계정 생존 PID 1개 및 후속 요청 대기를 확인했다. 동시 감독 사례 다운로드 간격 3.43ms. Linux에서도 동일 4개 조합을 실제 프로세스로 검증한다.

빌드 지문을 매번 디스크에서 읽는 뮤턴트는 `run.ready` A=2/B=1로 실패했다. 따라서 한 대만 복귀하는 회귀를 완료로 인정하지 않는다. 상세 결과·명령·한계는 `unit/feature-0043-external-llm-bridge/docs/test-runs.d/TASK-20260908T120000-runner-update-recovery.md`.

2026-09-08 PR #1606 병합 후 서버 배포와 DQA 1.1.1 설치기 채널 반입을 완료했다. 사용자의 기존 앱에 감독 기능이 들어가려면 **1.1.1 설치 후 재연결**이 필요하다. 이미 종료된 옛 러너는 서버 파일 교체만으로 소급 복구되지 않는다. 이번 실측은 실제 OS/실제 프로세스 + 격리 HTTPS 서버이며, 실제 사용자 AI 작업을 실행하거나 계정 15시간 단절의 전체 원인을 재현했다고 주장하지 않는다.

## TASK-20260908T120000-runner-update-recovery — 배포 후 완료 기록

- 서버 코드 `0f58a1de2f53883bbff1158f87c7637a85323d88`를 web-a/b에 롤링 배포했다. ready/soak PASS, 배포 구간 Caddy `no upstreams available` 0건. 변경된 서버 제공 러너·정적 자산을 배포했고 worker 배포·실제 AI 대화는 이번 검증 대상이 아니다.
- 공식 클라이언트 채널 1.1.1 게시 완료. 실제 Windows 앱의 updater 코드가 1.1.0에서 1.1.1을 발견하고 설치기 25,731,162 bytes를 다운로드해 SHA-256 일치를 확인했다. 설치기를 실행해 사용자 설치본을 바꾸지는 않았다.
- 사용자는 **DQA 앱에서 1.1.1로 업데이트한 뒤 다시 연결**한다. 별도 러너 실행·터미널 명령은 필요 없다. 실제 두 러너 복귀 및 파싱 전 실패 복구 실측은 아래 정본에 기록했다.
- 검증 정본: `unit/feature-0043-external-llm-bridge/docs/test-runs.d/TASK-20260908T120000-runner-update-recovery.md`.


### TASK-20260908T020000-delegation-friction — 교차 검증 보완

테스트 수집 누락 복구로 드러난 연결 안내/테스트 경계 오류를 함께 수정한다. 변경·검증 정본은
[feature-0043 TASK](../../feature-0043-external-llm-bridge/docs/TASK.md) 및
[위탁 병목 개선 REPORT](../../../docs/improvements/delegation-friction-20260908/REPORT.md)다.
DQA 클라이언트가 주 사용 환경이며 브라우저 인계 경로 검증을 앱 전체 검증으로 합산하지 않는다.

## DQA 연결 개선 배포 결과 — 2026-09-08

PR #1619 / 서버 92cfa2c2 전체 배포 및 DQA 1.2.0 설치기 공개 완료. 실제 다운로드 크기·SHA-256이 Windows 원본과 일치한다. 최종 검증/미확인 경계와 증거 정본은 feature-0046 REPORT의 배포 완료 절과 공동 실행 원장이다.

## CHG-20260908-attachment-cycle-cleanup

- Timestamp: 2026-09-08T06:38:22.052443+00:00; Session: 01a07f94-148f-7253-a515-1a7a66a97cea

정리 중 cycle-finalize가 종료 코드 141로 실패했다. `set -o pipefail` 아래에서 첫 경로를 얻은 awk의 조기 종료가 큰 worktree 목록을 출력하는 git에 SIGPIPE를 전달했다. cycle-init/finalize 모두 첫 경로만 출력하면서 나머지 입력을 소비하도록 수정했다. Bats 전체 25 PASS, 격리된 기존 코드 뮤턴트는 신규 2건 모두 141로 실패. 제품 런타임 변경은 없으며 추가 배포 대상이 아니다.

## CHG-20260908T162000-tool-surface

- Related TASK: TASK-20260908T162000-tool-surface
- Timestamp: 2026-09-08T08:01:57.915443+00:00; Session: 01a07f94-148f-7253-a515-1a7a66a97cea

[TASK-20260908T162000-tool-surface 도구 감사](TOOL_SURFACE_AUDIT.md): 대화의 HTTP404/SQL 가드 제한을 분리해 확인했다. 조회5종 연결, 21종 계약 분류, 서버 catalog·MCP 전체인자 전달과 제품 경계 보강. 검증/배포 결과는 test-runs.d/TASK-20260908T162000-tool-surface.md.

## CHG-20260908T172000-tool-surface-deploy-proof

- Related TASK: TASK-20260908T162000-tool-surface
- Timestamp: 2026-09-08T08:20:41.263318+00:00; Session: 01a07f94-148f-7253-a515-1a7a66a97cea

PR #1635 / ca3fe660을 격리 배포 트리에서 전체 롤링했다. 7서비스 healthy·90초 soak·56배포본 계약검사 PASS, 실제 task 권한 catalog/미허용 datasource/첨부 대체경로 확인. 실제 SQL Server는 새 웹·기존 워커·호스트 모두 연결 timeout이어서 프로시저 결과 성공과 구분한다. 신규 AI 응답0으로 fixed:deployed:unverified-live 유지. 정본: [배포·미실측 기록](test-runs.d/TASK-20260908T162000-tool-surface.md). 제품 코드 추가 변경 없이 증거·제한을 문서화한다.
## TASK-20260908T125500-share-client-entry — 공유 링크: 열람은 브라우저, 참여·fork 는 DQA 앱

**무엇이 바뀌었나.** 대화를 링크로 공유하면 받는 사람은 지금까지처럼 **평범한 웹브라우저로
내용을 그대로 본다**(익명 포함 — 열람 경로는 한 줄도 바뀌지 않았다). 달라진 것은 그 아래
액션 바다: 그 대화에 **참여하거나 자기 계정으로 fork 하는 일은 DQA 앱에서** 한다. 브라우저
화면에는 `[링크 복사]` 와 `[DQA 앱에서 참여 · fork]` 만 보이고, 누르면
`dqa-connect://open?…&path=/share/<token>` 으로 앱이 떠서 **그 대화를** 연다(서비스 루트가
아니다). 직접 실행 버튼(`대화에 참여`·`내 계정에서 fork`)은 **앱 창 안에서만** 나타난다.

**사용자 결정 2건**(착수 전 확인). ① 앱 미설치자 → **앱 전용 + 받기 안내**(웹 폴백 없음).
② 서버 집행 → **프런트 유도까지**. ②의 근거는 join/fork 를 직접 POST 하려면 이미 «유효
로그인 세션 + 유효 공유 토큰» 이 있어야 한다는 것이다 — 우회로 얻는 것은 권한이 아니라
«어느 화면에서 눌렀는가» 뿐이므로, 이 분기는 **표시이지 집행이 아니다**(서버 join/fork
게이트는 무변경). 이 비대칭은 코드 주석·FUNCTION·REVIEW 에 명시했다.

**막다른 길을 만들지 않기 위한 네 가지.** 브라우저는 스킴 핸들러 부재를 **알려 주지 않으므로**
(a) 누른 직후 안내가 뜨고, (b) `[DQA 앱 받기]` 는 서버가 실물을 확인했을 때만 보이며 없으면
안내 문구도 그 버튼을 가리키지 않는다. (c) 참여도 fork 도 불가능한 링크에서는 진입 버튼
자체를 감춘다. (d) 서버가 링크 조립에 실패한 회차에는 **종전 웹 버튼으로 열화**한다 —
「앱 전용」의 예외가 아니라 우리 쪽 장애일 때의 열화다.

**검증.** 계약 15 PASS(`test_share_client_entry.py`) + 동작 30 PASS(jsdom
`verify_share_client_entry.mjs`) + 클라이언트 전건 PASS. 하네스 자체의 결함을 먼저 잡았다 —
첫 작성본은 `runScripts: "outside-only"` 라 `share.js` 가 한 줄도 실행되지 않았는데 「버튼이
안 보인다」류 단정이 전부 통과했다(초기 HTML 이 이미 `hidden`). ⓪번 양성 대조군이 그 형태를
봉인한다. `test_share_redaction_invariant.py` 7건은 **main 에서도 동일하게 실패**하는 로컬
환경 의존 항목이라 회귀에서 제외했다(판정 = main 대비 차집합).

**남은 것.** **클라이언트를 재배포해야 목적지 이동이 성립한다.** 서버만 배포하면 구버전 앱은
`path` 를 몰라 서비스 루트를 연다 — 파손이 아니라 의도된 degrade 이며, 앱은 뜨고 사용자는
무엇을 해야 하는지 볼 수 있다. 설치기 빌드는 Windows 전용이라 feature-0046 릴리스 채널
절차를 따른다. 이 cycle 의 범위는 서버·프런트·클라이언트 **소스**까지다.

### §8 개선 제안 (기록만)

- `static/ai-connect.js` 가 브리지 좌표 규약(`?client_port=&client_nonce=`)을 **자체 구현**하고
  있다. 이번 cycle 이 만든 어댑터(`share-client-context.js`)와 정본 모듈
  (`app/client-bridge.js`)과는 별개 사본이다. 이번 요청 범위 밖이라 손대지 않았으며,
  통합하면 좌표 해석이 저장소에 하나로 남는다.
- **`verify_side_panel_exclusive.mjs` 의 C3 두 단정이 실패한다 — 선재이며 이번 변경과 무관하다.**
  이 cycle 을 위해 로컬에 `jsdom` 을 설치했더니 그동안 **`exit 2`(미검증)로 넘어가던** 그
  하네스가 실제로 돌았고, 그 순간 `C3 프로필 open → 프로필 열림`·`→ backdrop 열림` 2건이
  드러났다(65 passed / 2 failed). **`main` 에서 같은 명령을 돌려 동일 결과를 확인**했으므로
  회귀가 아니다. 그러나 이것이 뜻하는 바는 따로 있다 — `test_s6_behaviour_harness_runs_or_
  ci_gap_is_documented` 는 jsdom 이 **없을 때** 「CI gap 문서화」 경로로 통과하도록 설계돼
  있어, 도구가 없는 환경에서는 이 결함이 영원히 보이지 않는다(§16.7 G15 — 도구 부재를 skip
  이 아니라 미검증으로 표면화해야 한다). 소유는 side-panel 계약 쪽이므로 이번 cycle 에서
  고치지 않고 남긴다.

### 적대 검증 2라운드 — 무엇이 바뀌었나 (2026-09-08 후속)

이 cycle 은 §18.8 패널을 **두 번** 돌렸고, 두 번 모두 결함을 잡았다. 그 결과 위 요약의 설계는
유지되지만 **구현이 상당히 달라졌다.**

**1R 이 잡은 것 중 둘은 이 변경이 새로 만든 위험이었다.** ① 경로 검증이 `?`·`#` 를 통과시켜
`panel_url` 의 쿼리가 두 벌이 되고, 브라우저가 **첫 값**을 취하므로 링크를 만든 쪽이 브리지
nonce 를 덮어쓸 수 있었다(실행 재현). ② 브리지 좌표 캡처가 **익명 공유 페이지**로 내려와,
링크 한 줄로 origin 전역 `sessionStorage` 를 심을 수 있었다. 두 축 모두 봉인했다.

**2R 은 그 조치들이 성립하는지 물었고, 셋이 갈렸다.** X1 조치(deny-list)는 같은 문서가
`/static/share.html` 로도 익명 200 이라 **뚫렸고**(allow-list 로 극성 반전), `os.fchmod` 는
**배포 플랫폼인 Windows 에서 no-op** 이었으며(실 Windows 실측), 목적지 쓰기 실패가 **요청
자체를 삼켰다**. UX 쪽에서는 여백 동기화가 **인쇄를 깨뜨렸고**, T9 회귀 고정이 **항진명제**라
바가 화면의 31% 를 먹어도 초록이었다.

**이 cycle 이 스스로 잡은 것도 셋이다** — 경계 테스트를 상수에서 계산했더니 상수와 표가 함께
움직여 항진명제가 됐고, 좁은 폭 조치가 `textContent` 대입으로 받기 링크를 **삭제**했으며,
하네스 두 곳의 테스트 nonce 가 실제 규격 밖이라 제품과 다른 것을 재고 있었다.

**검증 규모**: 계약 21 · jsdom 81 · 클라이언트 585 · 실 렌더 16. 각 조치는 뮤턴트로 봉인을
확인했다. 회귀 판정은 main 대비 **차집합 0**.

**이연 8건**은 TASK.md 「남은 것 · 후속」과 2R artifact §이연에 근거와 함께 남겼다 — 그중
둘(브라우저 명령줄의 토큰, 스킴 하이재킹 노출 빈도)은 이 변경이 **키운** 축이므로 다음 cycle 의
후보로 명시한다.
