---
run_at: 2026-08-27T09:30:00+09:00
session: ai/claude/feature-0043-external-llm-bridge
scope: codex 2차 리뷰 P1 6건 · P2 3건 조치 + 상태/장애/권한 회귀 17건
verdict: PASS (단위) / 잔여 — PB-0008 시각검증 · 도달성 probe
---

# Run — codex 2차 조치 검증

Environment: container (`make test` 하네스) + 로컬 pytest

## 결과

| 스위트 | 결과 |
|---|---|
| `unit/feature-0043-external-llm-bridge/tests` | **71 passed** (게이트 24 · 러너 5 · 배선 25 · **상태/장애/권한 17**) |
| 편집 Python 4파일 AST | 통과 |
| `static/app/composer.js` ESM `node --check` | 통과 |
| 컨테이너 `make test` (전체) | 통과 |

## 2차 조치가 닫은 것

1차 조치 뒤 재리뷰가 **절반만 닫힌 것들**을 드러냈다.

- **P1-A (기능 사망)** — `selectConversation()` 은 이미 활성인 대화면 즉시 return 한다(읽음처리만).
  폴링은 성공하고 토스트까지 뜨는데 답변은 화면에 나타나지 않았다. `loadHistory()` 로 교체하고,
  테스트가 **주석이 아닌 실제 호출**만 검사하도록 작성해 재발을 막았다.
- **P1-E (권한)** — 질문 후 그룹에서 퇴출된 계정이 `claim_request` 로 최신 문맥을 읽고
  `submit_answer` 로 그 대화에 쓸 수 있었다. 양 시점 fail-closed 재검증.
- **P1-B/C (상태 신뢰성)** — `submitted` 와 "대화에 실렸다" 를 분리(`Delivered` 컬럼),
  전달을 원장보다 먼저, `save_memory_message` 의 삼킨 실패(0 반환) 확인.
- **P1-D (고착)** — lease 30분. 목록·점유가 같은 술어를 공유.
- **P1-F / P2** — 러너 문맥 전달 · 세션 소유권 · INSERT→저장 순서 · 폴러 4xx 중단.

## 테스트 축을 넓힌 이유

codex 가 1차 조치의 회귀 테스트를 두고 *"대부분 AST/문자열 배선 검사라 상태 전이·장애·권한
결함을 검출하지 못한다"* 고 지적했다. 정확한 지적이라 **검사 대상이 배선이 아니라 조건·순서·
실패 경로**인 17건을 추가했다(권한 판정의 fail-closed, 전달↔원장 순서, lease 술어 공유,
save 반환값 확인, 취소의 스코프, 폴러의 4xx 분기).

## 미수행 (정직 표기)

- **PB-0008 실 Windows 브라우저 시각검증** — 웹 자산(`composer.js`) 변경 cycle 이므로 필수.
- **도달성 1-probe** (`reachability_scope: included`).

---

## POST-DEPLOY 실측 (라이브 `0b2b4435`, 2026-08-27)

| 항목 | 결과 |
|---|---|
| 서비스별 GIT_COMMIT | `web-a`·`web-b`·`ask-worker`·`insight-worker`·`ext-tool-mcp` = **0b2b4435** |
| 게이트 차단 (ask-worker 런타임) | `server_llm_enabled()=False` · 전 alias `client=None` · 사유 로그 정상 |
| MCP 주 경로 도구 노출 | **12종** — `list_open_requests`·`claim_request` 포함 |
| 스키마 마이그레이션 | `Origin`·`ClaimedBy`·`ClaimedAt`·`ClaimedClient`·`Delivered` + `IX_WebAiTasks_Bridge` |
| 라우트 도달성 | 신규 3종 전부 도달(401/405 — catch-all 404 아님) · 엣지 `/` 200 · 무토큰 `/api/ai/mcp` 401 |

### 배포 중 발견한 결함 (조치 완료)

gateway reconcile 이 대화 스모크 FAIL 로 **안전 중단**됐다. FAIL 사유는 게이트가 정상 작동한
것(`_get_llm_client` 가 `None`)이었고, 스모크의 전제("우리 LLM 이 대화 답변을 만든다")가 이번
전환으로 낡은 것이었다. `deploy-web.sh` 가 스모크 실패 시 교체하지 않는 설계라 **라이브 장애 0**.

→ `bin/smoke-conversation.sh` 를 전환 모드 인지형으로 수정(PR #1352): 게이트 차단 시
"차단이 실제로 걸려 있는가" 를 단정하고, 게이트가 열리면 종전 LLM 왕복 검사로 자동 복귀.

**교훈**: 계획 단계의 blast-radius 목록에 **배포 게이트**가 빠져 있었다 — "LLM 을 쓰는 곳"을
셀 때 검증 스크립트를 세지 않았다.

### PB-0008

브리지 setup 불가로 **미수행**(사유·해소조건은
`unit/feature-0003-agent-web-ui/docs/test-runs.d/REV-20260827T000500-bridge-poll-ui.md`).
화면 렌더·폴링 자동갱신은 여전히 미검증이며, 위 실측은 "부품이 제자리에 있다" 까지만 보인다.

---

## 배포 완결 실측 (`11049643`, 2026-08-27)

PR #1352(스모크 전제) 병합 후 `make deploy-web` 재실행 → **gateway reconcile 포함 전 단계 완료**.

### 배포 체크리스트 (feature-0014 RUNBOOK §10)

| # | 항목 | 결과 |
|---|---|---|
| 1 | web-a·web-b 대상 SHA + soak | `mysql-ai-web:11049643` 양쪽 |
| 2 | 워커 롤아웃 | `ask-worker`·`insight-worker`·`ops-scheduler`·`ext-tool-mcp` = `mysql-ai-agent:11049643` |
| 1b | 대화 스모크 | **PASS** — "서버 계정 LLM 차단 확인(전환 모드)" |
| 2b | surge 잔존 | **0** (정리 완료) |
| 3 | 캐시 무효화 | asset 스탬프 갱신 OK |
| 5 | 무중단 실측 | `no upstreams available` **0건** (15분 창) |

### 두 자물쇠 모두 라이브 반영

```
# ① gateway config (두 번째 자물쇠)
$ docker compose exec bedrock-gateway grep "^  - model_name" /app/config.yaml
  - model_name: titan-embed        ← 계정 alias 14종 전부 비활성, 로컬 임베딩만

# ② 앱 게이트 (정본)
$ docker compose exec ask-worker python3 -c "..."
server_llm_enabled(): False
claude-opus-5-chat client: None
```

### 완결 판정

사용자 요청의 **"root·claude-corp 계정을 LLM 으로 사용하는 부분을 모두 주석처리"** 는
라이브에서 완결됐다 — 코드 게이트와 설정 주석 양쪽이 반영됐고, 어느 한쪽만 풀어서는 열리지 않는다.
