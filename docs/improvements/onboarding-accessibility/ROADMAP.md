---
doc_type: DQA_ROADMAP
initiative: onboarding-accessibility
created_at: 2026-09-02
source_research: ./RESEARCH.md
status: active
schema_version: 1
---

# 개발 로드맵 — onboarding-accessibility (「AI 연결」 축)

> **다른 세션이 0 맥락으로 읽고 착수 가능**하도록 쓴다. 각 항목 = worktree cycle 1개.

## 0. 맥락 (context-free 진입)

**대상 제품**: 사내 LAN 전용 DB 질의 어시스턴트(Database Query Assistant). 서버는 도구·컨텍스트·
데이터만 제공하고, **추론은 각 사용자의 개인 머신 AI 런타임이 자기 계정으로** 수행한다
(feature-0041 도구 표면 + feature-0043 pull 브리지). 서버측 LLM 은 `shared/llm_gate.py` 에서
fail-closed 차단이며 **본 로드맵은 그것을 건드리지 않는다.**

**왜 이 로드맵이 존재하는가**: 사용자 제보(2026-09-02) — *"각 사용자들이 처음 사용하는 입장에서
접근성이 너무 떨어진다"*, 후속 결정에서 *"현재 가장 큰 걸림돌은 'AI 연결'"*. `RESEARCH.md` §9.1 이
근본 원인을 확정했다: **연결을 우리가 만든 배포물(파이썬 상주 러너 + 셸 설치 스크립트 1,506줄)로
구현했고, AI 클라이언트 생태계가 이미 가진 1급 배포 포맷(MCPB `.mcpb` · 플러그인)을 쓰지 않았다.**
그 포맷은 런타임·설치 UX·설정 UI·업데이트 채널을 함께 가져오는데, 우리는 넷을 전부 자체 구현했고
넷 모두가 마찰이 됐다.

**사용자 결정으로 범위 밖 (RESEARCH §9)**: 서버 추론 복원·미터링(**보류**) · 공인 인증서 전환
(**논외**) · Intune/GPO(**MDM 존재 여부 미응답 — 보류**).

**정본 진입**: `repo/AGENTS.md` · `repo/docs/PROJECT.md` · `repo/docs/SECURITY.md` ·
`unit/feature-0043-external-llm-bridge/docs/FUNCTION.md`(P0-H · P0-K · P0-J · P0-Z3~Z6)

**측정 기반**: **없음 — ITEM-00 이 만든다.** 그래서 ITEM-00 이 전 항목의 선행이다.

---

## 1. 종속성 그래프

```
ITEM-00 (연결 퍼널 계측) ──enables──▶ (전 항목 — 효과 증명 수단)

ITEM-01 (하트비트 클라이언트 종류 분리)
      └──requires──▶ ITEM-02 (MCPB 번들)          ← 수명·축출 가드가 선행
                          └──enables──▶ ITEM-04 (연결 축 2분할)
ITEM-03 (연결 진행·진단 웹 표시) ──enables──▶ ITEM-04

ITEM-05 (AI CLI 허용목록 3자리 정합)  — 독립
ITEM-06 (「AI 없음」 안내 분기 정확화) — 독립
ITEM-07 (Claude Code 플러그인 배포)   ──requires──▶ ITEM-01

SPIKE-01 (Claude Desktop 딥링크 조사) ──enables──▶ ITEM-04 (사용감 상향, 선택)
```

**DAG 검증**: 순환 없음. 측정 수단(ITEM-00)은 모든 효과 항목의 선행으로 끌어올렸다
(`improve_listup` 정합 축 6 — 측정 없이 성능·UX 항목 채택 금지).

## 2. Phase 시퀀스

| Phase | 포함 ITEM | 병렬? | 진입 조건 | 왜 이 순서인가 |
|---|---|---|---|---|
| **P0** | ITEM-00 · ITEM-05 · ITEM-06 | ✅ 병렬 | (없음) | 계측이 없으면 P1 의 효과를 증명할 수 없다. ITEM-05·06 은 독립·저위험이라 같은 창에서 처리 |
| **P1** | ITEM-01 → ITEM-02 | ❌ 순차 | ITEM-00 done | ITEM-01 없이 ITEM-02 를 내면 「하루 두 번 끊기고 남의 러너를 축출하는 확장」이 된다 |
| **P2** | ITEM-03 · ITEM-07 | ✅ 병렬 | ITEM-02 done | 등록형 경로가 생긴 뒤라야 진단 화면이 덮을 상태 집합이 확정된다 |
| **P3** | ITEM-04 | ❌ | ITEM-02·03 done | 두 축을 나눠 제시하려면 양쪽 경로가 모두 실재해야 한다 |
| **선택** | SPIKE-01 | ✅ | (없음) | 결과가 ITEM-04 의 사용감을 바꾸지만 차단하지는 않는다 |

---

## 3. 항목

### ITEM-00 · 연결 퍼널 계측
- **status**: pending
- **feature_id**: `feature-0043-external-llm-bridge` (기존 확장 — 연결 축 코드가 여기 거주)
- **dimension**: operational
- **risk_grade**: Minor
- **depends_on**: []
- **enables**: [ITEM-01, ITEM-02, ITEM-03, ITEM-04, ITEM-07]
- **why**: RESEARCH F-015. 「어느 단계에서 사람들이 떨어지는가」를 아무도 모른다. 이 로드맵의 모든
  항목이 «연결이 쉬워졌다»를 주장하는데, 그 주장을 반증할 수단이 저장소에 없다.
- **fit_verdict**: adopt
- **what**: 연결 퍼널 5단계를 `WebAuditEvents` 에 `action='ai.connect.funnel'` 로 적재한다.
  단계 = `page_view`(`/ai/connect` 또는 모달 열림) · `handoff_issued`(토큰 발급) ·
  `first_heartbeat`(그 계정의 최초 하트비트) · `first_claim`(최초 `claim_request`) ·
  `first_answer`(최초 `submit_answer`). `ChangeJson` = `{step, path_kind, account_id, ts}`.
  `path_kind` ∈ `{runner_posix, runner_windows, connector, probe, handoff}` — **경로별 이탈률을
  가르는 것이 이 계측의 목적**이므로 단계만 세면 가치의 절반을 잃는다.
- **entry_points**:
  - `unit/feature-0003-agent-web-ui/src/routers/oauth_as.py:533` `connect_status()` — `connected`/
    `listening` 판정이 이미 여기 있다. **판정 로직을 복제하지 말고 재사용**한다.
  - `unit/feature-0003-agent-web-ui/src/routers/oauth_as.py:1296` `POST /api/ai/connect/token` — `handoff_issued`
  - `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py:4489` `bridge_heartbeat` — `first_heartbeat`
  - `claim_request` · `submit_answer` 핸들러 (`routers/ai_tools.py`) — `first_claim`/`first_answer`
- **acceptance**:
  1. 신규 계정으로 연결을 완주하면 5단계가 시간순으로 `WebAuditEvents` 에 정확히 1행씩 남는다.
  2. 중도 이탈(토큰만 발급하고 설치 안 함) 계정은 2단계까지만 남는다.
  3. **재실행 멱등** — 같은 계정이 재연결해도 `first_*` 는 중복 적재되지 않는다(계정당 1회).
  4. `path_kind` 가 러너(posix/windows)·등록형·probe 를 구분한다.
  5. 토큰 원문·명령문·프롬프트는 **적재하지 않는다** (`docs/SECURITY.md` D12 정합).
- **guards**: 계측 실패가 연결을 막지 않는다 — 적재 예외는 삼키고 로그만 남긴다(fail-open).
  하트비트는 30초마다 오므로 `first_heartbeat` 판정에 **계정당 1회 가드**가 없으면 원장이 폭주한다.
- **effort**: 中
- **notes**: 웹 자산 변경이 있으면 PB-0008 대상. 서버 전용이면 비대상.

---

### ITEM-01 · 하트비트에 클라이언트 종류를 선언하고 supersede 를 러너로 한정
- **status**: pending
- **feature_id**: `feature-0043-external-llm-bridge`
- **dimension**: structural
- **risk_grade**: **Major** — 잘못하면 사용자의 러너가 조용히 굶는다 (라이브 실측 이력 있는 축)
- **depends_on**: [ITEM-00]
- **enables**: [ITEM-02, ITEM-07]
- **why**: RESEARCH F-012. ITEM-02(MCPB)의 **하드 전제**다. 두 결함을 동시에 닫는다:
  1. **수명** — 확장에 붙여넣은 토큰은 **최대 12시간**이면 죽는다. 수명 연장은
     `bridge_heartbeat` 가 `ExpiresAt` 를 미는 것으로만 일어나고, 하트비트를 보내는 것은 러너뿐이다.
  2. **축출** — 그래서 프록시가 하트비트를 보내기 시작하면, supersede 판정
     (`_stale_runner_yield_to`)이 **하트비트 이력이 있는 행끼리 연결 순서로** 승자를 정하므로
     **같은 계정에서 돌던 사용자의 러너를 축출**한다. FUNCTION.md P0-K 가
     *"하트비트를 모르는 등록형 MCP 클라이언트는 이 판정에 걸리지 않는다"* 로 보장하던 안전이
     **F-012 를 넣는 순간 깨진다.**
- **fit_verdict**: **adopt-with-guard**
- **what**:
  - `POST /api/ai/bridge_heartbeat` payload 에 `client_kind` ∈ `{runner, connector}` 를 받는다.
    **부재 = `runner`** (구 러너 호환 — 사용자 머신의 옛 사본을 우리가 갱신할 수 없다, C3).
  - `WebOAuthTokens` 에 `ClientKind` 컬럼 추가(멱등 ALTER, 기본값 `runner`).
  - `stale_runner_must_yield()` 의 후보 집합을 **`ClientKind='runner'` 로 한정**한다.
    `connector` 행은 승자로도 패자로도 판정에 들어가지 않는다.
  - `connector` 하트비트도 **`ExpiresAt` 연장은 동일하게** 받는다 — 그것이 이 항목의 절반이다.
- **entry_points**:
  - `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py:4489` `bridge_heartbeat()`
  - `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py:327` `_stale_runner_yield_to()`
  - `unit/feature-0003-agent-web-ui/src/oauth_store.py:492` `heartbeat()` ·
    `:544` `account_is_heartbeating()` · `stale_runner_must_yield()`
- **acceptance**:
  1. `client_kind` 미지정 하트비트가 종전과 **바이트 동일하게** 동작한다(구 러너 무회귀).
  2. `connector` 하트비트가 `ExpiresAt` 를 `HEARTBEAT_EXTEND_SEC` 만큼 민다.
  3. **같은 계정에 러너(먼저) + connector(나중)** 가 공존할 때 러너가 **양보하지 않는다**
     — `claim_request` 가 409 를 내지 않고, 목록·대기가 억제되지 않는다.
  4. 러너 2개(먼저/나중)의 기존 supersede 동작은 **불변**이다(회귀 잠금).
  5. `connector` 만 있는 계정의 `/api/ai/connect/status` 가 `listening: true` 를 낸다.
  6. 뮤테이션: `ClientKind` 필터를 제거하면 acceptance 3 이 **FAIL** 해야 한다(가드가 load-bearing).
- **guards**: 판정 실패는 **fail-open(양보 없음)** 을 유지한다 — `_stale_runner_yield_to` 의 기존
  규약이며, 뒤집으면 멀쩡한 러너가 굶는다. 새 컬럼이 없는 배포에서도 읽기 축이 동작해야 한다
  (`one-axis-supports-a-deployment-all-must` — 쓰기 축도 같은 배포를 알아야 한다).
- **effort**: 中
- **notes**: alembic/멱등 ALTER 는 `docs/CONVENTIONS.md §12` expand/contract 준수 · `bin/migrate-lint.sh` 통과.

---

### ITEM-02 · MCPB 번들(`.mcpb`) 배포 — 터미널·Python 없는 등록 경로
- **status**: pending
- **feature_id**: `feature-0046-mcpb-connector-bundle` (**신규** — 언어(Node)·배포 포맷·수명주기가
  러너와 다르다. `feature-0043` 에 넣으면 이미 4,267행인 러너 축과 머지 지점이 겹친다)
- **dimension**: structural
- **risk_grade**: **Major** — 새 배포 아티팩트 + 토큰을 다루는 새 클라이언트 표면
- **depends_on**: [ITEM-00, ITEM-01]
- **enables**: [ITEM-04]
- **why**: RESEARCH F-011 · §9.1. **W3(터미널)·W4(Python)를 동시에 소멸**시키는 유일한 항목이다.
  Node.js 가 Claude Desktop 에 동봉되므로 사용자 머신에 런타임을 요구하지 않는다. Anthropic 공식
  문서가 *"Access to systems behind your firewall (private databases)"* · *"Zero-trust compliance
  inside corporate network boundaries"* 를 MCPB 권장 케이스로 명시한다 — 우리 배치 그대로다.
- **fit_verdict**: **adopt-with-guard**
- **what**:
  - `src/` 에 얇은 **stdio↔HTTP 프록시**(Node + `@modelcontextprotocol/sdk`). 하는 일은 셋뿐:
    ① stdio MCP 요청을 `{base}/api/ai/mcp` 로 `Authorization: Bearer` 와 함께 중계
    ② 30초 주기로 `POST /api/ai/bridge_heartbeat` `{client_kind:"connector"}` (ITEM-01)
    ③ 종료 시 정리. **답변 생성·CLI 실행·파일 쓰기를 하지 않는다** (러너와의 경계).
  - `manifest.json`: `user_config` 로 `base_url`(문자열) · `token`(**sensitive**) 를 받고,
    `env` 로 `NODE_EXTRA_CA_CERTS` 를 지정한다. `compatibility` 에 `darwin`·`win32`.
  - `mcpb pack` 산출물을 `/static/agent/mysql-ai.mcpb` 로 서빙하고 **sha256 을 서버가 계산해**
    `/ai/connect` 가 표시(기존 `_setup_checksum` 과 같은 규약).
  - `/ai/connect` 에 **[확장 파일 받기]** 를 추가한다 — 순서·문안은 ITEM-04 가 정한다.
- **entry_points**:
  - 신규: `unit/feature-0046-mcpb-connector-bundle/src/{proxy.js,manifest.json}`
  - 빌드: `unit/feature-0002-agent-core/src/scripts/build_bridge_agent.py` 와 **같은 계층**에 번들
    빌드를 둔다(소스는 커밋, 배포본은 빌드 생성물 — 2026-09-02 러너 모듈화와 동일 규약)
  - 서빙·체크섬: `unit/feature-0003-agent-web-ui/src/routers/oauth_as.py`
    `_setup_checksum()` · `compose_launch_commands()`
  - 배포 게이트: `bin/deploy-web.sh:1642` `bridge_runner_verify()` 와 같은 형태로 번들 검증 추가
- **acceptance**:
  1. 실 Windows 와 macOS 에서 `.mcpb` **더블클릭 → 설정 UI 에 주소·토큰 입력 → 설치 완료**까지
     터미널을 한 번도 열지 않고 성공한다. (**PB-0008 실 Windows 브라우저 + 실 설치 왕복**)
  2. 설치 직후 `/api/ai/connect/status` 가 `listening: true` 를 낸다(프록시 하트비트 도달).
  3. 웹에서 질문 → Claude Desktop 세션이 `claim_request` → `submit_answer` → **같은 말풍선이
     답변으로 덮어써진다**(P0-F 계약 유지).
  4. **12시간을 넘겨도 연결이 유지된다** — 하트비트가 `ExpiresAt` 를 밀고 있음을 DB 로 확인.
  5. 서빙 sha256 = 빌드 산출물 sha256 (갈리면 사용자가 받는 것과 테스트한 것이 다르다).
  6. 같은 계정에 러너가 함께 떠 있어도 **러너가 축출되지 않는다**(ITEM-01 acceptance 3 재확인).
- **guards**:
  - **토큰은 `user_config` 의 sensitive 필드로만 받는다** — 번들 파일에 굽지 않는다(배포물이
    자격증명을 담으면 파일 하나가 계정 탈취 경로가 된다).
  - 프록시는 **`{base}/api/ai/mcp` 와 `/api/ai/bridge_heartbeat` 외 어떤 URL 도 만들지 않는다**
    (러너의 「나가는 곳은 한 곳」 계약과 동형 — 테스트로 잠근다).
  - **모델 선택기는 뜨지 않는다** — 프록시는 CLI 를 호출하지 않아 caps 를 신고할 수 없고,
    P0-Z6 규칙대로 신고 없음 = `hidden` + 사유 표시가 **정상 동작**이다. 이것을 결함으로
    오인해 폴백 목록을 만들지 않는다(그 폴백이 `gpt-5.1-codex` 를 화면에 띄운 그 경로다).
- **effort**: 大
- **notes**: ⚠ **Claude Desktop 전용**(macOS·Windows). codex·gemini 사용자는 ITEM-07 또는 기존
  러너. 이 한계를 `/ai/connect` 가 **표시해야** 한다 — 안 하면 codex 사용자가 받아서 안 되는
  파일을 받는다. Node 의존성은 번들에 포함하되 크기를 보고한다.

---

### ITEM-03 · 연결 진행·진단을 웹 화면이 끝까지 표시
- **status**: pending
- **feature_id**: `feature-0043-external-llm-bridge`
- **dimension**: functional
- **risk_grade**: Minor
- **depends_on**: [ITEM-00, ITEM-02]
- **enables**: [ITEM-04]
- **why**: RESEARCH F-006. GUI 편향 사용자에게 가장 직접적인 처방 — *"터미널을 안 봐도 된다"* 를
  참으로 만든다. 실측 최악 사례: 능력 협상 실패로 **240초 침묵**, 그동안 하트비트·로그·질문 수신이
  0인데 설치 스크립트는 2초 뒤 「완료」를 선언했다(`REPORT.md` TASK-20260902T140000 ②).
  **등록형 경로에서는 러너 로그조차 없으므로 이 항목이 더 필요하다.**
- **fit_verdict**: adopt
- **what**: `/ai/connect` 와 연결 모달에 **단계 체크리스트**를 그린다 — 각 행에 ✅/⏳/❌ +
  **실패 시 다음 행동 1개**. 데이터는 `/api/ai/connect/status` 를 확장해 싣는다(새 엔드포인트
  금지 — 두 엔드포인트가 갈리면 0ms 재로드 순환이 난다).
  행: `설치됨` · `연결됨`(토큰 유효) · `듣는 중`(하트비트 최근성) · `답할 AI 있음`(러너 caps 신고
  또는 connector) · `첫 답변 완료`.
- **entry_points**:
  - `unit/feature-0003-agent-web-ui/src/routers/oauth_as.py:533` `connect_status()` — **여기를 확장**
  - `unit/feature-0003-agent-web-ui/src/static/ai-connect.js` · `src/static/app/connect-modal.js`
  - 판정 상수: `oauth_store.HEARTBEAT_WINDOW_SEC`(=90) 재사용
- **acceptance**:
  1. 러너가 `exit 4`(AI 없음)로 죽은 계정의 화면이 **`답할 AI 있음: ❌` + 다음 행동**을 보인다
     — 터미널을 열지 않고 원인을 안다.
  2. 재부팅으로 러너가 사라진 계정이 `연결됨 ✅ / 듣는 중 ❌` 로 **갈라져** 보인다(현재는
     「연결됨」만 보여 아무도 없는 곳에 질문하게 된다 — 제보 2026-08-27).
  3. 단독 페이지와 모달이 **같은 판정**을 쓴다(두 벌이면 갈린다 — P0-L 계약).
  4. 상태 갱신이 국면당 1회로 수렴한다(재로드 순환 금지).
  5. **PB-0008** 실 Windows 브라우저로 3상태(미연결/정상/AI없음) 시각 확인.
- **guards**: 판정 실패는 기존 fail-open(「연결됨」)을 유지 — 확신 없이 「연결 없음」을 단정하면
  이미 연결한 사용자에게 매번 설정하라고 떠든다(P0-G).
- **effort**: 中
- **notes**: 웹 자산 변경 → **PB-0008 필수**(`FIRST_REQUEST.md` `visual_verification_scope: always`).

---

### ITEM-04 · 연결을 두 축으로 나눠 묻는다 — 러너를 필수에서 선택으로
- **status**: pending
- **feature_id**: `feature-0043-external-llm-bridge`
- **dimension**: functional
- **risk_grade**: Minor
- **depends_on**: [ITEM-02, ITEM-03]
- **enables**: []
- **why**: RESEARCH F-014 · §9.2. **현재 결함의 정체** — 「지금 답 받기」만 원하는 사용자(대부분)도,
  무인 처리를 위해 만든 상주 러너의 설치 벽을 통과해야 한다. 필요하지 않은 사람에게 부과된 비용이다.
- **fit_verdict**: adopt
- **what**: `/ai/connect` 첫 화면이 **질문 하나**를 묻는다 — *"자리를 비운 사이에도 답이 와 있어야
  하나요?"*
  - **아니오(기본)** → 확장 설치(ITEM-02). 설치물 0, 터미널 0.
  - **예** → 러너 설치(현행 경로). 「이 경우 터미널을 한 번 씁니다」를 **미리** 말한다.
  - 부가: Desktop 스케줄 태스크 안내를 접힌 항목으로. **비용을 반드시 병기** — 질문이 없어도
    매 실행마다 새 세션이 뜨므로 사용자 구독 쿼터를 태운다. **권장 기본값은 러너**.
- **entry_points**:
  - `unit/feature-0003-agent-web-ui/src/static/ai-connect.html` — 현재 `<details>` 「터미널을 쓸 수
    없다면」(:66-76)에 접혀 있는 등록형 경로를 **1급으로 끌어올린다**
  - `unit/feature-0003-agent-web-ui/src/routers/oauth_as.py:1071` `compose_connect_handoff()` ·
    `:865` `compose_launch_commands()` — **조립은 서버 한 곳** 규약 유지(화면이 조립하면 갈린다)
- **acceptance**:
  1. 「아니오」 경로를 고른 신규 사용자가 **터미널을 열지 않고** 첫 답변을 받는다(라이브 왕복 1건).
  2. 「예」 경로가 현행 러너 설치와 **동작 동일**(회귀 0).
  3. 두 경로의 트레이드오프(자리 비움 처리 / 터미널 1회 / 모델 선택기 유무)가 화면에 **명시**된다.
  4. JS 가 잡는 **DOM id 13개 불변**(P0-G 테스트 계약 — 문안 수정이 버튼을 죽이지 않게).
  5. **PB-0008** 실 Windows 브라우저 시각검증.
- **guards**: 기존 러너 사용자의 [내 AI 실행] 자동 진행(`BridgeLastOs` 기반)을 **깨지 않는다**.
- **effort**: 中

---

### ITEM-05 · AI CLI 허용 목록 3자리 정합 (드리프트 수정)
- **status**: pending
- **feature_id**: `feature-0043-external-llm-bridge`
- **dimension**: structural
- **risk_grade**: Minor
- **depends_on**: []
- **enables**: []
- **why**: RESEARCH F-010 · §1.1. `ollama` 가 설치 스크립트·서버 안내에는 남아 있는데 러너
  `_RUNTIME_SPECS` 에는 P0-Z6.1 로 제거됐다(`_CLI_ADAPTERS` 는 그 파생). **설치는 통과하고
  런타임에서 실패**한다.
- **fit_verdict**: adopt
- **what**: 세 자리에서 `ollama` 제거 + **러너를 단일 출처로 삼는 동기화 테스트** 추가.
- **entry_points**:
  - `unit/feature-0043-external-llm-bridge/src/bridge_setup.sh:152` `_KNOWN_AI_CLIS`
  - `unit/feature-0043-external-llm-bridge/src/bridge_setup.ps1:206` `$KnownAiClis`
  - `unit/feature-0003-agent-web-ui/src/routers/oauth_as.py` `_PROBED_AI_ALLOWLIST`
  - 정본: `unit/feature-0043-external-llm-bridge/src/agent/runtimes.py` `_RUNTIME_SPECS`
- **acceptance**:
  1. 세 목록이 `_RUNTIME_SPECS` 키 집합과 **정확히 일치**한다.
  2. 테스트가 세 파일을 파싱해 정본과 대조하고, **어느 한 곳에 이름을 더하면 FAIL** 한다.
  3. `BRIDGE_PROBED_AI='ollama'` 가 설치 단계에서 거부된다(런타임까지 가지 않는다).
- **guards**: **제거만 하고 동기화 테스트를 안 걸면 다음 런타임 추가 때 같은 드리프트가 재발**한다
  (AGENTS.md §16.7 G10 — 재발 관측된 결함 클래스는 구조 테스트로 잠근다).
- **effort**: 小

---

### ITEM-06 · 「AI 없음」 안내를 데스크톱 앱 ↔ CLI 로 분기
- **status**: pending
- **feature_id**: `feature-0043-external-llm-bridge`
- **dimension**: functional
- **risk_grade**: Minor
- **depends_on**: []
- **enables**: []
- **why**: RESEARCH F-007. 현재 안내(`_AI_SETUP_URL`)는 **CLI 설치 문서 한 곳**만 가리킨다.
  비개발자에게는 GUI 설치 관리자가 정답이다.
- **fit_verdict**: **adopt-with-guard**
- **what**: 안내를 두 갈래로 나눈다.
  - **러너 경로 사용자** → `claude` **CLI** 설치(러너가 `Popen` 으로 띄울 바이너리가 필요)
  - **등록형 경로 사용자** → **데스크톱 앱** GUI 설치 관리자
  구독 요건(Pro/Max/Team/Enterprise)을 함께 표시한다.
- **entry_points**:
  - `unit/feature-0043-external-llm-bridge/src/agent/discovery.py:190` `_AI_SETUP_URL` ·
    `:193` `_no_ai_message()`
  - `unit/feature-0003-agent-web-ui/src/static/ai-connect.html`
- **acceptance**:
  1. 러너 안내가 **CLI** 를, 등록형 안내가 **데스크톱 앱**을 가리킨다.
  2. 「데스크톱 앱만 설치하면 러너가 뜬다」로 읽히는 문장이 **없다**.
  3. 구독 요건이 표시된다.
- **guards**: ⚠ **분기 정확도가 이 항목의 전부다.** 데스크톱 앱은 `claude` CLI 를 설치하지
  **않는다**(공식 문서 명시). 뭉뚱그리면 사용자는 설치를 마치고도 러너가 안 뜨는 상태를 만난다 —
  현재보다 나쁜 결말이다.
- **effort**: 小

---

### ITEM-07 · Claude Code 플러그인 배포 (CLI·비-Desktop 사용자)
- **status**: pending
- **feature_id**: `feature-0046-mcpb-connector-bundle` (같은 배포-포맷 축)
- **dimension**: functional
- **risk_grade**: Minor
- **depends_on**: [ITEM-01]
- **enables**: []
- **why**: RESEARCH F-013. ITEM-02 는 Claude Desktop 전용이라 CLI 사용자를 덮지 못한다. 플러그인은
  `/plugin marketplace add` + `/plugin install` **두 명령**으로 MCP 서버를 등록한다 — 터미널을
  쓰지만 **우리 스크립트가 아니라 Claude 의 명령**이고 설정 파일 손편집이 사라진다.
- **fit_verdict**: **adopt-with-guard**
- **what**: 사내 마켓플레이스 저장소에 플러그인 정의를 두고 MCP 서버 항목(`{base}/api/ai/mcp` +
  Bearer)을 번들. `/ai/connect` 가 두 명령을 복사 가능하게 표시.
- **entry_points**: 신규 `unit/feature-0046-mcpb-connector-bundle/src/plugin/` ·
  `unit/feature-0003-agent-web-ui/src/static/ai-connect.html`
- **acceptance**:
  1. 두 명령만으로 Claude Code CLI 에 MCP 서버가 등록되고 `list_open_requests` 가 200 을 낸다.
  2. 토큰이 마켓플레이스 저장소에 **커밋되지 않는다**(사용자가 설치 후 주입).
  3. 12시간 초과 연결 유지가 확인된다(ITEM-01 하트비트 축).
- **guards**: **codex·gemini 사용자는 여전히 미커버**임을 화면이 말한다 — 커버리지를 과장하면
  그 사용자는 안내를 따라갔다가 막힌다(P0-I 가 닫은 결함 클래스).
- **effort**: 中

---

### SPIKE-01 · Claude Desktop 딥링크 가능성 조사 (선택, 타임박스)
- **status**: pending
- **feature_id**: `feature-0046-mcpb-connector-bundle`
- **dimension**: functional
- **risk_grade**: Minor (조사 — 코드 변경 0)
- **depends_on**: []
- **enables**: [ITEM-04]
- **why**: 등록형 경로의 남은 약점은 **「사용자가 자기 AI 앱에 가서 말을 걸어야 한다」**는 것이다.
  Claude Desktop 이 프로토콜 핸들러(딥링크)를 노출한다면, 웹에서 [내 AI 로 보내기] 한 번으로 앱을
  깨우고 프롬프트를 채울 수 있다 — 우리는 이미 `mysql-ai-bridge://` 로 같은 패턴을 구현해 봤다.
- **fit_verdict**: adopt (조사 항목)
- **what**: ① Claude Desktop 이 등록하는 URL 스킴 실측(Windows 레지스트리 / macOS
  `LSCopyDefaultHandlerForURLScheme`) ② 프롬프트 프리필 파라미터 유무 ③ 공식 문서·릴리스노트 근거
  ④ 없으면 대안(OS 알림 → 기존 스킴) 판정. **타임박스 1 cycle, 산출물은 판정 문서 1건.**
- **acceptance**: 「가능/불가능 + 근거 + 가능 시 ITEM-04 에 붙일 spec」이 문서로 남는다.
  **불가 판정도 성공적 산출물**이다(되살아나지 않게 기록).
- **effort**: 小
- **notes**: 실측 없이 「될 것 같다」로 ITEM-04 에 넣지 않는다.

---

## 4. 정합성 6축 review 요약

각 항목을 `improve_listup` 정합 축으로 판정했다. **코드 근거는 각 항목 `entry_points` 에 인용**했다.

| 축 | 판정 요지 |
|---|---|
| **1. 아키텍처 정합** | 전 항목이 기존 구조에 **얹힌다** — MCP 도구 표면(feature-0041)·pull 브리지(0043)·하트비트 채널·`connect_status` 판정을 그대로 쓴다. **구조 피벗 0.** ITEM-02 만 새 배포 아티팩트를 더하나, 서버 계약(`/api/ai/mcp` + Bearer)은 **무변경**이다 |
| **2. 제약 정합** | `PROJECT.md §6` 과 충돌 없음. 온프레미스·폐쇄망 유지(MCPB 는 **로컬 실행**이라 클라우드 왕복이 없다 — 오히려 `claude.ai` 원격 커넥터보다 정합적이다). 비밀정보 비-VCS: ITEM-02·07 의 토큰 비-커밋을 guards 에 못박음 |
| **3. 보안·RBAC 정합** | 신규 권한 **0**. 인증은 기존 `require_ai_token` 단일 해석기를 그대로 통과한다(P0-I 의 「두 벌이면 갈린다」 회피). **신규 위험 1건 식별 — ITEM-01 의 러너 축출**, 이것이 ITEM-01 이 ITEM-02 의 선행인 이유다. ITEM-00 계측은 토큰·프롬프트 미기록(D12) |
| **4. 성능·비용 정합** | 서버 부하 증가 = 하트비트 1행/30초/클라이언트(기존 러너와 동일 규모, `HEARTBEAT_MIN_WRITE_SEC` 쓰기증폭 방어 존재). **LLM 비용 증가 0** — 서버는 추론하지 않는다. ⚠ ITEM-04 의 Desktop 스케줄 태스크 안내만 **사용자 쿼터**를 태우므로 비용 고지를 acceptance 에 넣었다 |
| **5. 재사용 지렛대** | 매우 높다. ITEM-01 은 **서버 엔드포인트를 새로 만들지 않는다**(기존 `bridge_heartbeat` 에 필드 1개). ITEM-03 은 **기존 `connect_status` 판정 재사용**. ITEM-00 은 `WebAuditEvents` 재사용. 신규 코드가 실제로 큰 것은 ITEM-02 프록시 하나뿐 |
| **6. 측정 가능성** | **여기가 가장 약했다** — 초안에는 측정 수단이 아예 없었다. 그래서 **ITEM-00 을 신설해 P0 선행으로 끌어올렸다.** 이것이 없으면 ITEM-02·04 의 「쉬워졌다」를 반증할 수단이 저장소에 없다 |

## 5. 보류·기각 (재논의 방지)

| finding | verdict | 사유 |
|---|---|---|
| F-005 서버측 폴백 티어(API 키·virtual key) | **보류(defer)** | 사용자 결정 2026-09-02 *"서버 추론 복원은 보류"*. 기각 아님 — BYO-AI 로 덮이지 않는 사용자가 실제로 관측되면 재개 |
| F-009 공인 인증서 전환 | **논외(out-of-scope)** | 사용자 결정 *"아직 배포가 이루어지지 않았고, 현재 가장 큰 걸림돌은 AI 연결"* |
| F-004 Intune/GPO 배포 | **보류(미판정)** | 사내 MDM 존재 여부 미응답. 존재하면 최대 레버라는 판단은 유효 — 확인되면 재평가 |
| F-002 러너 단일 실행파일(PyInstaller) | **보류** | ITEM-02 가 **터미널·Python 을 둘 다 없애므로** 러너 동결의 한계효용이 크게 준다. ITEM-02 배포 후 러너 잔존 사용자 비율(ITEM-00 계측)을 보고 재판정 |
| F-003 네이티브 설치 관리자(.msi/.pkg) | **보류** | 같은 이유 + 코드 서명 인증서 확보가 선행. MCPB 는 서명 없이도 Claude Desktop 이 설치 UI 를 제공한다 |
| F-008 로그온 자동시작 | **보류** | 기존 설계 결정(「하지 않는 일」)의 명시적 번복이라 `docs/DECISIONS.md` ADR 경유가 선행. ITEM-04 가 러너를 「선택」으로 만들면 대상 인원이 줄어 우선순위도 내려간다 |
| `claude.ai` 원격 커스텀 커넥터 | **기각(reject)** | LAN + `.company.local` 사설 CA 라 Anthropic 인프라가 우리 서버로 아웃바운드할 수 없다. F-009 가 논외로 확정된 이상 이 경로는 열리지 않는다 |
| 로컬 LLM(ollama) 어댑터 복원 | **기각** | P0-Z6.1 사용자 결정으로 제거됨. 그 축은 *"고칠수록 결함을 만드는 자리"* 로 실증됨. ITEM-05 는 그 결정의 **잔재 정리**이지 복원이 아니다 |

## 6. 진행 현황

- 총 **8** (ITEM 7 + SPIKE 1) · done 0 · in-progress 0 · pending 8 · blocked 0
- **다음 ready**: `ITEM-00` · `ITEM-05` · `ITEM-06` (P0 병렬 — 선행 의존 없음)
- 신규 feature 배정: `feature-0046-mcpb-connector-bundle` (2026-09-02 기준 최대 = `feature-0045`,
  타 worktree·ROADMAP 점유 없음 확인)
