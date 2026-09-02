---
doc_type: WIKI_ARTICLE
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.51.0
domain: [flows, features, workers, operations]
ai_read_priority: 7
wiki_role: article
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
sources:
  - ../../docs/ROUTEMAP.md
  - ../../docs/ARCHITECTURE.md
  - ../../shared/attachment_write.py
  - ../../unit/feature-0019-message-editing/docs/FUNCTION.md
  - ../../unit/feature-0009-group-conversation/docs/FUNCTION.md
  - ../../unit/feature-0024-conversation-folders/docs/FUNCTION.md
  - ../../unit/feature-0039-ops-scheduler/docs/FUNCTION.md
  - ../../unit/feature-0016-metadata-graph/docs/FUNCTION.md
---

# Flows — 세부 기능 동작

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/article` |
| 정본 | 각 절의 소유 feature `docs/FUNCTION.md` · [[../../docs/ROUTEMAP\|docs/ROUTEMAP.md]] (route → handler → auth) |
| 범위 | 첨부 · 메시지 편집/브랜치 · 그룹 대화 · 폴더 · 공유 · 검색 · 메타데이터/그래프 · 워커·큐 · 정기 잡 · 배포 |

## 목차

1. [개요](#1-개요)
2. [상세](#2-상세)
     - [2.1 첨부 파일 수명주기](#21-첨부-파일-수명주기)
     - [2.2 assistant 가 파일을 고치는 경로](#22-assistant-가-파일을-고치는-경로)
     - [2.3 메시지 편집과 재답변 브랜치](#23-메시지-편집과-재답변-브랜치)
     - [2.4 그룹 대화](#24-그룹-대화)
     - [2.5 폴더 (프로젝트)](#25-폴더-프로젝트)
     - [2.6 공유와 fork](#26-공유와-fork)
     - [2.7 대화 검색](#27-대화-검색)
     - [2.8 메타데이터 거버넌스와 지식그래프](#28-메타데이터-거버넌스와-지식그래프)
     - [2.9 실행 큐와 워커](#29-실행-큐와-워커)
     - [2.10 정기 잡 (ops-scheduler)](#210-정기-잡-ops-scheduler)
     - [2.11 무중단 배포](#211-무중단-배포)
3. [특징](#3-특징)
4. [평가](#4-평가)
5. [관련 문서](#5-관련-문서)
6. [둘러보기](#6-둘러보기)
7. [외부 link](#7-외부-link)
- [분류](#분류)

## 1. 개요

[[User-Journeys|사용자 화면 흐름]] 이 "무엇이 보이는가" 라면, 여기는 그 아래에서 **각 기능이 실제로 무엇을 하는가** 다. 45 개 feature 전부가 아니라, 사용자가 자주 만나거나 흐름이 비자명한 것들을 골랐다. 각 절의 정본은 해당 feature 의 `FUNCTION.md` 이며 본 문서는 그 흐름 mirror 다.

## 2. 상세

### 2.1 첨부 파일 수명주기

```mermaid
flowchart TD
    U["업로드 — 드래그&드롭 · ＋ 메뉴<br/>POST /api/conversations/{cid}/attachments"] --> G1{"저장 가드"}
    G1 -->|"소유권 · kind · 용량 · 확장자 allowlist"| G2["MinIO 오브젝트 저장<br/>(agent-attachments 버킷)"]
    G2 --> M["메타 기록 — 버전 v1"]
    M --> S{"질의 가능한 형식?"}
    S -->|예| SB["sandbox schema 적재<br/>(attachment_writer)"]
    SB --> Q["LLM 이 SQL 로 질의<br/>(attachment_reader · SELECT only)"]
    M --> A["다음 질문에 attachment_ids 로 동반"]

    A --> V{"assistant 가 수정본을 만들면"}
    V --> V2["새 버전 v2 · 'AI 수정' 배지"]
    V2 --> D["버전 diff 패널 — 직전 버전과 비교"]

    M --> DL["다운로드 · 전체 다운로드"]
    M --> DEL["삭제 → 휴지통"]
    DEL --> RS["복원 (POST /restore)"]
    DEL --> CU["만료 정리 (attachment_cleanup)"]
```

관련 route: `GET /api/attachments/{id}` · `/download` · `/source` · `/versions` · `/diff` · `POST /restore` · `DELETE`. sandbox 의 4 user 분리는 [[Security-Controls#27-첨부-sandbox--4-user-분리|Security §2.7]] 참조.

diff 패널의 UI 계약 두 가지가 실측으로 굳었다 — 표 레이아웃은 `colgroup` 이 필수이고(Chrome 이 `col` 퍼센트 `calc()` 를 무시), **스크롤 보존은 픽셀이 아니라 줄번호 앵커**로 한다(버전을 바꿀 때만 초기화).

### 2.2 assistant 가 파일을 고치는 경로

답변에 ` ```attachment-edit ` / ` ```attachment-new ` 블록이 실리면 그 내용은 채팅 본문이 아니라 **다운로드 첨부**(원본의 새 버전 / 새 파일)가 되어야 한다.

```mermaid
flowchart LR
    A["답변 본문"] --> B["materialize edit"] --> C["materialize new"] --> D["도구 전달분 바인딩"] --> E["strip (본문에서 블록 제거)"] --> F["미전달 고지"] --> G["content 갱신"]
```

이 시퀀스는 `shared/attachment_write.py` **한 벌**이다. 원래 ask-worker 경로(`modules/ask.py`)에만 있었고 브리지 경로(`routers/ai_tools.py`)에는 **아예 없어서**, 개인 AI 가 관례대로 블록을 만들어 냈는데 서버가 처리하지 않아 **파일은 v1 그대로인 채 답변만 "수정했습니다" 라고 말하는** 거짓 성공이 났다(라이브 실측 2026-08-28).

두 번째 구현을 쓰는 대신 한 벌로 합친 이유: 저장 가드(소유권·kind·용량·확장자 allowlist)가 materialize 안에 있어서 **구현이 갈리면 가드도 갈리고, 갈리는 순간 느슨한 쪽이 사용자가 보는 진실**이 된다.

> 잔여: 동기 inproc 경로(`_ask_impl`)의 첨부 쓰기는 아직 세 번째 구현이다. 합치는 것은 별도 cycle.

### 2.3 메시지 편집과 재답변 브랜치

```mermaid
flowchart TD
    M["내가 보낸 메시지"] --> C{"어떤 수정인가"}
    C -->|"메시지 수정<br/>(단순)"| S["내용만 교체 — 재답변 없음"]
    C -->|"요청사항 수정<br/>(재답변)"| R["새 버전 브랜치 생성"]
    R --> ASK["/api/ask 재dispatch<br/>(브리지 대기가 될 수 있다)"]
    ASK --> V["버전 페이저 &lt; 2/3 &gt;<br/>POST /api/conversations/{cid}/branch/switch"]
    V --> CACHE["브랜치 뷰 LRU 캐시 —<br/>페이저 1클릭이 서버 요청 4건을 부르지 않게"]
    G["그룹·공유 대화"] -.->|"단순 수정만 (브랜치 없음)"| S
```

이 기능에는 실측된 함정이 하나 있다. 브랜치 체이닝이 대화 단위 `active_leaf` 를 **write 마다 다시 읽던 시절**, 동시 재답변이 겹치면 답변이 user 메시지의 형제로 붙어 **"내 메시지가 사라지고 답변만 쌓이는"** 것처럼 보였다. 수정은 **run 단위 thread-local 커서**로 갈랐고, 복구는 대화 스코프의 `LAG` UPDATE 로 했다.

### 2.4 그룹 대화

```mermaid
flowchart TD
    P["멤버가 메시지 전송"] --> C{"@assistant 멘션 있나<br/>(**서버가 재파싱** — 클라이언트 플래그 불신)"}
    C -->|없음| ST["store-only — 사람-사람 채팅<br/>(assistant 실행 안 함)"]
    C -->|"없는데 /api/ask 에 도달"| E422["422 group_requires_mention<br/>→ 클라이언트가 store-only 로 재라우팅"]
    C -->|있음| ASK["assistant 실행<br/>발신자 각인 (sender_account_id · sender_username · group_chat)"]

    O["소유자 전용 조작"] --> K["멤버 추방 (DELETE members/{id})"]
    O --> B["차단 (ban) — 재참여 양 경로 fail-closed 게이트"]
    O --> UB["차단 해제"]
```

멘션 판정을 **서버에서 다시 하는 것**이 요점이다. 클라이언트의 send-routing 이 이미 store-only 로 보내지만, stale 클라이언트나 직접 API 호출이 `/api/ask` 에 도달하면 여기서 거부해 단일 실패점을 없앤다. 파서 자체가 고장나면 보수적으로 통과시킨다(기존 동작 유지).

### 2.5 폴더 (프로젝트)

| 동작 | route | 권한 |
|---|---|---|
| 목록 | `GET /api/folders` | `folder.list.own` |
| 생성·이름변경·삭제·복원 | `POST /api/folders` · `PATCH`/`DELETE /api/folders/{id}` · `POST /{id}/restore` | `folder.manage.own` |
| 대화 이동 | `PATCH /api/conversations/{cid}/folder` | `folder.manage.own` |

최대 깊이는 서버가 알려주는 `max_depth`(기본 4)를 따르고, 권한이 없거나 미부트스트랩이면 폴더 층만 사라진 채 정상 동작한다. 삭제에는 undo 가 붙는다.

### 2.6 공유와 fork

```mermaid
sequenceDiagram
    autonumber
    actor O as 소유자
    participant W as web
    actor V as 공유받은 사람

    O->>W: POST /api/conversations/{cid}/share<br/>(conversation.share.create)
    Note right of W: window [from,to] 를 함께 굳힌다
    W-->>O: 링크 /share/{token}
    O->>V: 링크 전달

    alt 비로그인
        V->>W: GET /share/{token} → read-only 뷰
        Note over W: hard window — 라이브 tail 병합 없음
    else 로그인 + conversation.create
        V->>W: POST /api/public/share/{token}/fork
        W->>W: 복사 window = INTERSECTION(share window, 요청자 멤버 window)
        W-->>V: 내 계정의 새 대화 (display + core + 첨부 3 store 모두 clip)
    else 참여
        V->>W: POST /api/share/{token}/join
        W->>W: join stamp = monotonic-narrowing (절대 확대 안 함)
    end
    O->>W: DELETE /api/share/{share_id} — 링크 철회
```

빈 교집합이면 400, 멤버 window 조회가 PG 오류면 500(fail-closed). bounded 멤버가 자기 window 밖으로 재공유하려 하면 403.

### 2.7 대화 검색

`GET /api/conversations` 는 `q` / `owner_id` / `product_id` / `date_from` / `date_to` / `cursor` 중 하나 이상이 오면 **검색 모드**로 전환된다. cross-account 검색은 admin/operator 의 감사 필요와 PII 보호 사이의 균형을 위해 별도 정책이 걸려 있다: 검색 표면 한정 · SQL safety · 성능 안전망 · **PII audit**(PIPA §29 준거) · UI 표면 제약. 상세는 [[../../docs/SECURITY|docs/SECURITY.md]] §8.

### 2.8 메타데이터 거버넌스와 지식그래프

```mermaid
flowchart TD
    subgraph 수집["수집 (LLM 무관 — 게이트와 분리)"]
        S1["metadata_table_stats"]
        S2["metadata_column_stats"]
    end
    subgraph 큐레이션["관리 콘솔 큐레이션"]
        C1["용어사전 (전역 / 제품 통용범위 축)"]
        C2["ENUM 코드사전"]
        C3["테이블 설명"]
        C4["컬럼 설명"]
        C5["샘플쿼리"]
    end
    subgraph 자동화["AI 자동완성 (개인 AI 위임)"]
        A1["단건 자동완성 → 폼에 채움 (사람 검토)"]
        A2["일괄 자동완성 → 폼에 채움"]
        A3["그래프 AI 능동 분석 → 자동 기입"]
    end
    수집 --> 큐레이션
    큐레이션 --> A1 & A2
    큐레이션 --> G["AGE 지식그래프 (Postgres + Apache AGE)"]
    A3 --> G
    G --> VIS["관리 콘솔 그래프 탭 — PixiJS 캔버스<br/>노드 종류 · 관계·AI 상태 · 테이블 역할 범례"]
    큐레이션 --> CTX["get_task_context 5층<br/>→ 개인 AI 답변의 접지"]
```

큐레이션이 실제로 **답변에 도달하는 주 경로**가 `get_task_context` 라는 점이 중요하다 — 2026-09-02 부터는 점유 응답(`claim_request`)에 접지 근거를 함께 싣는 **자동 주입**이 더해져 「유일한 경로」가 아니다([[External-AI-Bridge#27-접지-지식--get_task_context-5층|Bridge §2.7]]). 그래프 동기화는 증분(30분)과 전량(04:17) 두 스케줄로 돌고, 호스트에 남아 있는 `bin/routine-backfill.sh` 와 **`flock` 으로 상호배제**된다.

### 2.9 실행 큐와 워커

```mermaid
flowchart LR
    W["web /api/ask"] -->|enqueue| Q[("ask_jobs<br/>agent_runtime schema")]
    Q -->|"SKIP LOCKED claim"| AW["ask-worker"]
    Q -->|"부하 시"| AS["ask-worker-surge"]
    AW --> AG["agent loop"]
    IW["insight-worker"] --> RO[("rag_objects<br/>datasource scope 격리 캐시")]
    OS["ops-scheduler"] --> JOBS["정기 잡 4종"]
```

| 워커 | 하는 일 |
|---|---|
| `ask-worker` / `-surge` | `ask_jobs` 를 `SKIP LOCKED` 로 집어 agent loop 실행. **web 재배포가 in-flight run 을 죽이지 않는다** |
| `insight-worker` | 데이터소스 scope(`engine+host+port` 해시)로 `rag_objects` 를 격리 캐시 → 완료율·DB별 파악내용 표면화 |
| `ops-scheduler` | 아래 §2.10 |

> `web` 의 in-process 실행(`AGENT_ASK_EXECUTION_MODE=inprocess`)도 롤백 옵션으로 남아 있으나, 운영은 큐(`=worker`)가 라이브다. 다만 [[External-AI-Bridge|브리지 전환]] 이후 대화 답변은 이 큐가 아니라 `WebAiTasks` 대기열을 탄다 — 큐는 게이트가 열린 경우와 브리지 비대상 경로에서 계속 쓰인다.

### 2.10 정기 잡 (ops-scheduler)

스케줄 정본은 crontab 이 아니라 **`docker-compose.yml` 의 `ops-scheduler` 환경변수**이고, 잡 로직은 이미지 안(`/app/scripts/ops_*.sh`)에 실린다.

| 시각 | 잡 |
|---|---|
| 03:00 | 플랫폼 논리 백업 |
| 03:30 | 백업 복원 리허설 |
| 매 30분 | AGE 메타데이터 그래프 증분 sync |
| 04:17 | 그래프 전량 sync |

호스트 root crontab 에서 옮겨온 이유가 설계 자체다. 기존 래퍼가 전부 `docker exec` 로 DB 컨테이너에 들어갔고 이 호스트는 docker 소켓 접근이 root 에만 있었다. **잡을 서비스 안으로 옮기면 docker 소켓 의존 자체가 사라져 root 권한 근거가 소멸**한다. 반대 방향(컨테이너에 docker 소켓 마운트)은 컨테이너 → 호스트 root 승격 경로라 채택하지 않았다.

### 2.11 무중단 배포

```mermaid
flowchart TD
    D["make deploy-web<br/>(origin/main HEAD 기준)"] --> B["빌드 게이트 (feature-0017)"]
    B --> R1["web-a 롤링 교체"]
    R1 --> H1{"/healthz soak"}
    H1 -->|실패| RB["make web-rollback"]
    H1 -->|통과| R2["web-b 롤링 교체"]
    R2 --> WK["워커 (insight · ask) graceful 재기동"]
    WK --> GW["gateway reconcile"]
    GW --> MCPR["ext-tool-mcp-a/b one-at-a-time<br/>+ 브리지 드레인·게이트 (feature-0045)"]
    MCPR --> DONE["healthz / smoke assert PASS = 완료"]
```

부분 범위 타깃도 있다 — `make deploy-web-only`(web+caddy) · `make deploy-workers`(insight/ask+gateway). 마이그레이션은 **expand/contract 필수**이고(`bin/migrate-lint.sh` 통과 의무), contract(DROP/RENAME/타입변경/NOT NULL)는 2-phase 또는 서명 annotation 을 요구한다 — 롤링 중 mixed-version 이 안전해야 하기 때문이다.

실측된 함정 둘:

- **`/healthz` soak 의 false-positive** — 동시에 무거운 PG 부하(그래프 sync)가 돌면 롤백으로 오판한다. web 재배포와 graph re-sync 를 순차화한다.
- **롤링 창의 캐시 오염** — 구 replica 가 신 `?v=` URL 에 구 콘텐츠를 200 으로 답하면 `immutable` 로 고착됐다. 엣지의 무조건 immutable 을 제거하고, upstream 이 `?v=` == `static/.asset-stamp` 일 때만 immutable, 불일치는 `no-store` 로 바꿔 근본 해소했다.

## 3. 특징

- **경로 공용 정본** — 답변을 만든 주체가 안이든 밖이든 첨부 쓰기 시퀀스는 한 벌(`shared/attachment_write.py`).
- **서버 재판정** — 그룹 멘션·권한·window 는 클라이언트 신호를 믿지 않고 서버가 다시 판정한다.
- **권한 근거 소멸시키기** — 정기 잡을 서비스로 옮겨 root 권한의 *근거 자체*를 없앴다(권한만 낮춘 것이 아니다).
- **롤링 안전을 스키마 규약으로** — expand/contract 가 mixed-version 창을 계약으로 만든다.

## 4. 평가

| 축 | 상태 |
|---|---|
| 강점 | 단일 정본 원칙이 반복 적용됨(첨부 쓰기·상태 술어·window 연산) · 배포가 in-flight 작업을 죽이지 않음 |
| 잔여 | 동기 inproc 경로의 첨부 쓰기 3번째 구현 미통합 |
| 운영 주의 | graph sync 와 web 배포의 순차화 · `flock` 상호배제 유지 |

## 5. 관련 문서

- [[User-Journeys|사용자 화면 흐름]] — 위 기능들이 화면에서 어떻게 보이는가
- [[Security-Controls|보안 처리 과정]] — 첨부 sandbox·공유 window 의 방어
- [[External-AI-Bridge|외부 AI 연계 동작]] — 콘솔 작업 위임과 접지 지식
- [[../Architecture/Data-Flow|Architecture/Data-Flow]] — 워커·큐의 시스템 배치

## 6. 둘러보기

- 상위: [[_Index|Flows MOC]]
- sibling: [[Auth-and-Session]] · [[External-AI-Bridge]] · [[Security-Controls]] · [[User-Journeys]]
- 관련 feature: [[../Features/feature-0019-message-editing]] · [[../Features/feature-0009-group-conversation]] · [[../Features/feature-0024-conversation-folders]] · [[../Features/feature-0016-metadata-graph]] · [[../Features/feature-0039-ops-scheduler]] · [[../Features/feature-0014-zero-downtime-deploy]]

## 7. 외부 link

- [Apache AGE — Cypher on PostgreSQL](https://age.apache.org/)
- [expand/contract 마이그레이션 패턴](https://martinfowler.com/bliki/ParallelChange.html)

## 분류

`#wiki/article` · `#status/active` · `#confidence/high` · `#maturity/substantial`
