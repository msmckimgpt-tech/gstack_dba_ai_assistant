---
doc_type: DQA_ROADMAP
initiative: onboarding-accessibility
created_at: 2026-09-02
revised_at: 2026-09-02
source_research: ./RESEARCH.md
status: active
schema_version: 1
---

# 개발 로드맵 — onboarding-accessibility (「AI 연결」 축)

> **다른 세션이 0 맥락으로 읽고 착수 가능**하도록 쓴다. 각 항목 = worktree cycle 1개.
>
> **개정 이력**: 초판(2026-09-02 오전)은 MCPB 번들을 주 경로로 삼았다. 같은 날 사용자 지적
> *"현재 서비스는 claude 뿐만 아니라 다른 AI 모델을 모두 수용 가능해야 합니다"* + **네이티브
> 클라이언트 채택 결정**으로 주 경로가 교체됐다. 무엇이 왜 바뀌었는지는 §5 보류·기각에 남긴다.

## 0. 맥락 (context-free 진입)

**대상 제품**: 사내 LAN 전용 DB 질의 어시스턴트. 서버는 도구·컨텍스트·데이터만 제공하고,
**추론은 각 사용자의 개인 머신 AI 런타임이 자기 계정으로** 수행한다(feature-0041 도구 표면 +
feature-0043 pull 브리지). 서버측 LLM 은 `shared/llm_gate.py` 에서 fail-closed 차단이며
**본 로드맵은 그것을 건드리지 않는다.**

**왜 이 로드맵이 존재하는가**: 사용자 제보(2026-09-02) — *"각 사용자들이 처음 사용하는 입장에서
접근성이 너무 떨어진다"* → *"현재 가장 큰 걸림돌은 'AI 연결'"*. `RESEARCH.md` §9.1 이 근본 원인을
확정했다: **연결을 우리가 만든 배포물(파이썬 상주 러너 + 셸 설치 스크립트 1,531줄)로 구현했고,
런타임·설치 UX·설정 UI·업데이트 채널을 전부 자체 구현해 넷 모두가 마찰이 됐다.**

**주 처방 (사용자 결정 2026-09-02)**: **네이티브 설치형 클라이언트**. 사용자가 하는 일은
「설치 파일 더블클릭 → 쓸 AI 선택 → 로그인 클릭」이 전부가 되고, 터미널·Python·CLI 설치 명령·
토큰 복사가 모두 사라진다.

### 0.1 불변 제약 — ToS 경계 (**위반 시 사용자 계정이 정지된다**)

2026년에 3사가 모두 구독 OAuth 의 제3자 사용을 차단했다. **이 경계를 넘는 설계는 자동 기각이다.**

| | 허용 ✅ | 금지 ❌ |
|---|---|---|
| **무엇** | 벤더의 **공식 CLI 바이너리를 그대로 실행**한다. `claude -p` subprocess 호출은 2026-04 중순 명시적으로 허용 확인 | 구독 **OAuth 토큰을 추출·보관·중계**해 우리 클라이언트가 직접 API 를 부른다 |
| **누가 토큰을 만지나** | 벤더 CLI 만. 우리는 보지도 저장하지도 않는다 | 우리가 만진다 |
| **선례** | 현행 러너가 이미 이 방식이다 | Anthropic 2026-02-20 약관 → **2026-04-04 차단**(OpenClaw·OpenCode 등) · Google 2026-02 Gemini CLI 토큰 프록시 금지 + **유료 구독자 계정 정지** |

> **따라서 「로그인 OAuth 위임」은 「대행 실행」으로만 구현한다** — 클라이언트가 벤더의 공식
> 로그인 명령을 subprocess 로 띄우고 **진행 상황만 GUI 로 표시**한다. 사용자 체감은 동일하고
> (버튼 클릭 → 브라우저 승인 → 끝), 토큰은 벤더 자격증명 저장소에만 남는다.
> **이 문장을 어기는 구현은 리뷰에서 차단한다.**

### 0.2 재사용 지렛대 — 엔진은 이미 있다

클라이언트는 **새 제품이 아니라 기존 러너의 껍데기 교체**다.

| 이미 있는 것 | 위치 | 클라이언트에서의 역할 |
|---|---|---|
| 러너 엔진 5,849행 (18모듈) | `unit/feature-0043-external-llm-bridge/src/agent/` | 그대로 내장 |
| 런타임 3종 지원 (claude·codex·gemini) + 표 밖 CLI 지목 | `src/agent/runtimes.py` `_RUNTIME_SPECS` · P0-Z4 | 그대로 |
| CLI 감지 (Windows `.exe`·PATH 밖 표준 위치) | `src/agent/discovery.py` | 그대로 |
| 능력 질의(모델·추론등급 신고) | `src/agent/caps.py` | 그대로 |
| 무결성 대조(CA 지문·체크섬) | `bridge_setup.sh`/`.ps1` | **설치 관리자로 이관** |
| 자기 갱신 | `src/agent/selfupdate.py` | **자동 업데이트로 승격** |
| 셸 설치 스크립트 1,531행 | `bridge_setup.sh` 862 + `.ps1` 669 | **소멸** |

**정본 진입**: `repo/AGENTS.md` · `repo/docs/PROJECT.md` · `repo/docs/SECURITY.md` ·
`unit/feature-0043-external-llm-bridge/docs/FUNCTION.md`(P0-H · P0-K · P0-J · P0-Z3~Z6)

**범위 밖 (사용자 결정, RESEARCH §9)**: 서버 추론 복원·미터링(**보류**) · 공인 인증서 전환
(**논외**) · Intune/GPO(**MDM 존재 여부 미응답 — 보류**).

**측정 기반**: **없음 — ITEM-00 이 만든다.**

> ⚠ **`file:line` 앵커는 `main` `2eda1169`(2026-09-02) 기준이다.** 초판 작성 후 하루도 안 돼 4건이
> 밀렸다(PR #1533 병합). **행번호가 아니라 함께 적은 심볼명이 durable anchor** 이므로, 어긋나면
> `grep -n '<심볼>'` 으로 다시 잡는다.

---

## 1. 종속성 그래프

```
ITEM-00 (연결 퍼널 계측) ──enables──▶ (전 항목 — 효과 증명 수단)

SPIKE-02 (클라이언트 실현가능성) ──requires──▶ ITEM-08 (네이티브 클라이언트)
                                                    ▲
[조직 작업] 코드 서명 확보 ──── hard precondition ───┘

ITEM-08 ──enables──▶ ITEM-03 (웹 연결 진단 — 클라이언트 상태 반영)
        ──enables──▶ ITEM-06 (「AI 없음」 → 클라이언트 유도로 전환)

ITEM-05 (AI CLI 허용목록 3자리 정합) — 독립
```

**DAG 검증**: 순환 없음. 측정 수단(ITEM-00)을 전 항목 선행으로 두었고, **실현가능성(SPIKE-02)과
코드 서명(조직 작업)을 ITEM-08 의 하드 선행**으로 세웠다 — 「될 것 같다」로 Major 항목을 열지 않는다.

## 2. Phase 시퀀스

| Phase | 포함 | 병렬? | 진입 조건 | 왜 이 순서인가 |
|---|---|---|---|---|
| **P0** | ITEM-00 · ITEM-05 · **SPIKE-02** | ✅ 병렬 | (없음) | SPIKE 가 ITEM-08 의 spec 을 확정한다. 계측이 없으면 「쉬워졌다」를 반증할 수 없다. ITEM-05 는 독립·저위험 |
| **게이트** | — | — | SPIKE-02 done **AND** 코드 서명 확보 | **둘 중 하나라도 미충족이면 P1 진입 금지.** 서명 없이 배포하면 SmartScreen/Gatekeeper 경고가 터미널 벽을 그대로 대체한다 |
| **P1** | ITEM-08 [Major] | ❌ | 위 게이트 통과 | 클라이언트가 나머지 항목의 전제를 바꾼다 |
| **P2** | ITEM-03 · ITEM-06 | ✅ 병렬 | ITEM-08 done | 클라이언트가 실재해야 웹이 표시할 상태 집합과 안내 문안이 확정된다 |

> **SPIKE-02 완료(2026-09-03) 로 게이트가 한쪽만 남았다** — 실현가능성은 **GO**(3사 중 claude·codex
> 로그인 대행 실측 확인 · 러너 stdlib 전용이라 동봉 단순 · 크레딧 풀 우려는 **취소된 변경**이라 무근).
> 남은 것은 **코드 서명 조직 결정** 하나다. 단 SPIKE §2.3 이 그 게이트를 **완화**할 것을 제안한다:
> Windows 는 미서명 + 안내 동반으로 착수 가능(경고 2클릭, 이탈 위험 감수), **macOS 는 서명·공증
> 없이는 Gatekeeper 가 차단**하므로 지원 대상에 넣는 순간 Apple Developer Program($99/년) 필수.
> 즉 「확보 불가」는 **차단**이 아니라 **범위 축소**(Windows 우선)로 처리 가능하다 — 채택 여부는 사용자 결정.

---

## 3. 항목

### SPIKE-02 · 네이티브 클라이언트 실현가능성 (타임박스 1 cycle)
- **status**: **done** (2026-09-03) — 판정 **conditional-go**. 산출물 `./SPIKE-02-native-client.md`
- **feature_id**: `feature-0046-native-client`
- **dimension**: structural
- **risk_grade**: Minor (조사 — 제품 코드 변경 0)
- **depends_on**: []
- **enables**: [ITEM-08]
- **why**: ITEM-08 은 Major 이고 «제품이 하나 더 생기는» 규모다. 그 결정을 **추정 위에 세우지
  않는다.** 아래 4가지는 전부 실측 가능하고, 어느 하나가 부정이면 spec 이나 방향이 바뀐다.
- **fit_verdict**: adopt
- **what** — 네 가지를 실측하고 판정 문서 1건을 남긴다:
  1. **3사 CLI 의 스크립트 가능 로그인**: `claude` · `codex` · `gemini` 각각에 대해
     ① 비대화형/GUI 에서 띄울 수 있는 로그인 명령이 있는가 ② 브라우저 플로우를 subprocess 로
     감쌌을 때 성공/실패를 **종료코드나 출력으로 판정**할 수 있는가 ③ 이미 로그인돼 있는지
     확인하는 명령이 있는가. **없으면 그 런타임은 「대행 실행」 대신 「안내」로 강등**된다.
  2. **서명 없는 설치의 실제 경고**: 서명하지 않은 더미 설치 파일로 Windows SmartScreen ·
     macOS Gatekeeper 화면을 **캡처**한다. 「경고가 뜬다」가 아니라 **비개발자가 통과할 수 있는
     경고인가**를 화면으로 판정한다(벽이 이동만 하는지 실제로 낮아지는지).
  3. **기술 스택 선정**: Tauri / Electron / Go+트레이 중 택1. 판정 기준 = 번들 크기 ·
     3플랫폼 빌드 난이도 · **파이썬 러너 엔진 5,849행을 어떻게 동봉하는가**(임베드 인터프리터 vs
     PyInstaller 동결 vs 포팅). **포팅은 기각 후보** — 엔진 재작성은 재사용 지렛대를 버린다.
  4. **Agent SDK 크레딧 풀 영향**: `claude -p` subprocess 호출이 2026-06-15부터 일반 구독 한도가
     아니라 Agent SDK 크레딧 풀에서 차감된다는 보고를 **실측 확인**한다(우리 사용자 실질 한도에
     직결). 사실이면 `/ai/connect` 안내에 반영해야 하고, 다른 두 벤더도 같은 축을 확인한다.
- **entry_points**: 조사 — 제품 코드 변경 없음. 산출물
  `docs/improvements/onboarding-accessibility/SPIKE-02-native-client.md`
- **acceptance**:
  1. 네 항목 각각에 **판정 + 근거(명령 출력·스크린샷·문서 링크)** 가 문서에 있다.
  2. 「가능」뿐 아니라 **「불가능」도 근거와 함께** 기록된다(되살아나지 않게).
  3. ITEM-08 의 `what` 에 붙일 spec 초안(스택·로그인 대행 범위·런타임별 커버리지)이 나온다.
  4. **추정과 실측이 구분 표기**된다 — 실측하지 못한 항목은 「미실측」으로 명시.
- **guards**: 타임박스 1 cycle. 초과하면 **부분 판정으로 종결**하고 미실측 범위를 명시한다
  (조사가 무한 확장해 착수를 막는 것을 방지).
- **effort**: 中

---

### ITEM-08 · 네이티브 클라이언트 — 설치·로그인 대행·러너 내장
- **status**: **초판 done** (2026-09-03) — Windows 우선·미서명 (사용자 결정). 자동시작·자동업데이트·벤더 설치기 실행은 후속
- **feature_id**: `feature-0046-native-client` (**신규**)
- **dimension**: structural
- **risk_grade**: **Major** — 새 배포 아티팩트 + 사용자 머신에 상주물 + 타사 설치기 실행
- **depends_on**: [ITEM-00, SPIKE-02, **코드 서명 확보(조직 작업)**]
- **enables**: [ITEM-03, ITEM-06]
- **why**: RESEARCH §9.1 · 사용자 결정 2026-09-02. **터미널·Python·CLI 설치 명령·토큰 복사를
  한 번에 없애는 유일한 항목**이며, MCPB 와 달리 **claude·codex·gemini 를 모두 덮는다**
  (러너 `_RUNTIME_SPECS` 를 그대로 쓰기 때문). 덤으로 **C3**(러너가 사용자 머신 파일이라 우리가
  갱신할 수 없다 — P0-Z6 4차 재발의 뿌리)가 자동 업데이트로 닫힌다.
- **fit_verdict**: **adopt-with-guard**
- **what** — 서명된 설치 파일(Windows `.exe`/`.msi` · macOS `.pkg`/`.dmg`)이 하는 일:
  1. **러너 엔진 동봉** — `src/agent/` 를 그대로 싣는다(SPIKE-02 가 정한 방식). 파이썬 설치 불요.
  2. **CA 신뢰** — 현행 스크립트와 **같은 계약**: 지문 대조 후 **이 프로세스에만** 적용, OS 신뢰
     저장소 미변경. (설치 관리자라고 해서 전역 설치로 바꾸지 않는다 — 그 절제가 외부 AI 거절
     사유를 해소한 근거였다.)
  3. **AI CLI 감지 → 없으면 벤더 공식 설치기를 «동의를 받고» 실행** (`bridge_setup.ps1` 의
     winget 동의 패턴과 동형 — 말없이 설치하지 않는다).
  4. **로그인 대행 실행** — 벤더 공식 로그인 명령을 subprocess 로 띄우고 GUI 로 진행 표시.
     **§0.1 경계 준수: 토큰을 읽지도 저장하지도 중계하지도 않는다.**
  5. **상주 + 로그온 자동시작** — 트레이 아이콘 + 상태창. 재부팅 후 자동 기동.
  6. **자동 업데이트** — 서명 검증 후 교체. 실패 시 **있던 버전 그대로** 기동(갱신하려다 못
     띄우는 것이 가장 나쁜 결말 — 현행 `try_self_update` 와 같은 규약).
  7. **토큰 수령** — 기존 `dqa-connect://` 스킴 재사용(웹 [내 AI 실행] 경로 보존).
     ⚠ 2026-09-03 개명: `mysql-ai-bridge` → `dqa-connect`(제품명 `DQA Connect`,
     역-DNS `com.masangsoft.dqa-connect`). **정본은 `shared/dqa_identity.py`** 이고
     `tests/test_name_ssot.py` 가 다섯 자리를 대조한다 — 클라이언트도 그 정본을 쓰고
     이름을 자체 선언하지 않는다. Tauri `productName`/`identifier` 는 각각 `APP_NAME`/
     `APP_ID` 에서 온다. 이름에 구현 형태(`bridge`·`runner`·`client`)를 넣지 않은 것이
     이 항목을 위한 선택이다 — 러너→클라이언트 전환에 개명이 따라붙지 않게 한다.
- **entry_points**:
  - 신규: `unit/feature-0046-native-client/src/`
  - 엔진 재사용: `unit/feature-0043-external-llm-bridge/src/agent/` (18모듈, 5,849행)
  - 빌드: `unit/feature-0002-agent-core/src/scripts/build_bridge_agent.py` 와 **같은 계층**
    (소스는 커밋, 배포본은 빌드 생성물)
  - 서빙·체크섬: `unit/feature-0003-agent-web-ui/src/routers/oauth_as.py` `_setup_checksum()` ·
    `compose_launch_commands()`
  - 배포 게이트: `bin/deploy-web.sh:1661` `bridge_runner_verify()` 와 같은 형태로 설치 파일 검증
- **acceptance**:
  1. **실 Windows + 실 macOS 에서, 터미널을 한 번도 열지 않고**: 설치 → AI 선택 → 로그인 →
     웹에서 질문 → 답변 수신까지 완주한다. (**PB-0008** 실 Windows 브라우저 + 실 설치 왕복)
  2. **claude · codex · gemini 각각**에 대해 1 을 통과한다(하나라도 실패면 그 런타임은
     「감지·안내」로 강등하고 화면이 그 사실을 말한다 — 커버리지 과장 금지, P0-I 계약).
  3. **서명 검증** — 설치 파일이 서명돼 있고 SmartScreen/Gatekeeper 경고 없이 설치된다.
  4. 재부팅 후 자동 기동하고 `/api/ai/connect/status` 가 `listening: true` 를 낸다.
  5. 자동 업데이트가 **서명 검증 실패 시 교체하지 않고 기존 버전으로 기동**한다.
  6. 서빙 sha256 = 빌드 산출물 sha256.
  7. **토큰 비접촉 증명** — 클라이언트가 벤더 자격증명 파일·키체인을 읽지 않음을 소스·테스트로
     보인다(§0.1 경계가 load-bearing 이므로 «안 한다»를 검사한다).
- **guards**:
  - **§0.1 ToS 경계** — OAuth 토큰 접촉 금지. 위반 구현은 리뷰 차단.
  - **CA 는 프로세스 한정** — 전역 신뢰 저장소 변경 금지(현행 계약 유지).
  - **타사 설치기 실행은 명시 동의 후에만.** 비대화형이면 명령만 알려 주고 멈춘다.
  - **모델 선택기**: 클라이언트는 러너이므로 caps 신고가 그대로 동작한다 → P0-Z3~Z6 축 보존.
    신고 출처는 `probe`/`cache` 만 허용하는 기존 게이트를 우회하지 않는다.
  - **기존 러너와 공존** — 클라이언트도 `client_kind=runner` 이므로 「나중에 연결된 쪽이 이긴다」
    가 그대로 적용된다(사용자가 갈아타면 새 것이 이긴다 = 의도된 동작). 별도 가드 불요.
- **effort**: **大**
- **notes**: ⚠ **제품이 하나 더 생긴다** — 3플랫폼 × 아키텍처 빌드, 자동 업데이트 인프라,
  타사 설치기가 깨질 때의 지원 부담이 영구적이다. SPIKE-02 판정 없이 착수하지 않는다.

---

### ITEM-00 · 연결 퍼널 계측
- **status**: **done** (2026-09-03)
- **feature_id**: `feature-0043-external-llm-bridge`
- **dimension**: operational
- **risk_grade**: Minor
- **depends_on**: []
- **enables**: [ITEM-03, ITEM-06, ITEM-08]
- **why**: RESEARCH F-015. 「어느 단계에서 사람들이 떨어지는가」를 아무도 모른다. **클라이언트
  전환의 효과를 증명할 수단이 저장소에 없으면, 大 규모 항목을 하고도 나아졌는지 말할 수 없다.**
  전환 **전** 기준선을 잡아야 하므로 ITEM-08 보다 반드시 먼저다.
- **fit_verdict**: adopt
- **what**: 연결 퍼널 5단계를 `WebAuditEvents` 에 `action='ai.connect.funnel'` 로 적재.
  단계 = `page_view` · `handoff_issued` · `first_heartbeat` · `first_claim` · `first_answer`.
  `ChangeJson` = `{step, path_kind, account_id, ts}`.
  `path_kind` ∈ `{runner_posix, runner_windows, native_client, connector, probe, handoff}`
  — **경로별 이탈률을 가르는 것이 목적**이므로 단계만 세면 가치의 절반을 잃는다.
- **entry_points**:
  - `unit/feature-0003-agent-web-ui/src/routers/oauth_as.py:534` `connect_status()` —
    `connected`/`listening` 판정이 이미 여기 있다. **복제하지 말고 재사용**한다.
  - `unit/feature-0003-agent-web-ui/src/routers/oauth_as.py:1387` `POST /api/ai/connect/token`
  - `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py:4661` `bridge_heartbeat`
  - `claim_request` · `submit_answer` 핸들러 (`routers/ai_tools.py`)
- **acceptance**:
  1. 신규 계정이 연결을 완주하면 5단계가 시간순으로 정확히 1행씩 남는다.
  2. 중도 이탈 계정은 그 지점까지만 남는다.
  3. **재실행 멱등** — `first_*` 는 계정당 1회.
  4. `path_kind` 가 경로를 구분한다(`native_client` 값을 미리 정의해 ITEM-08 이 그대로 쓴다).
  5. 토큰 원문·명령문·프롬프트는 **적재하지 않는다**(`docs/SECURITY.md` D12).
- **guards**: 계측 실패가 연결을 막지 않는다(fail-open). 하트비트는 30초마다 오므로
  `first_heartbeat` 에 **계정당 1회 가드**가 없으면 원장이 폭주한다.
- **effort**: 中

---

### ITEM-03 · 연결 상태·진단을 웹 화면이 표시
- **status**: **done** (2026-09-03) — PB-0008 실 Windows 시각검증 완료
- **feature_id**: `feature-0043-external-llm-bridge`
- **dimension**: functional
- **risk_grade**: Minor
- **depends_on**: [ITEM-00, ITEM-08]
- **enables**: []
- **why**: RESEARCH F-006. 클라이언트가 자기 트레이에 상태를 그려도 **웹 화면은 여전히 알아야
  한다** — 사용자가 질문하는 곳이 웹이고, 「연결됨」만 보이면 아무도 없는 곳에 질문하게 된다
  (제보 2026-08-27). 실측 최악 사례: 능력 협상 실패로 **240초 침묵**(`REPORT.md`
  TASK-20260902T140000 ②).
- **fit_verdict**: adopt
- **what**: `/ai/connect` 와 연결 모달에 **단계 체크리스트** — 각 행에 ✅/⏳/❌ + **실패 시 다음
  행동 1개**. 데이터는 `/api/ai/connect/status` 를 확장해 싣는다(**새 엔드포인트 금지** — 두
  엔드포인트가 갈리면 0ms 재로드 순환이 난다).
  행: `클라이언트 설치됨` · `연결됨`(토큰 유효) · `듣는 중`(하트비트 최근성) ·
  `답할 AI 있음`(caps 신고) · `첫 답변 완료`.
- **entry_points**:
  - `unit/feature-0003-agent-web-ui/src/routers/oauth_as.py:534` `connect_status()` — **확장**
  - `unit/feature-0003-agent-web-ui/src/static/ai-connect.js` · `src/static/app/connect-modal.js`
  - 판정 상수: `oauth_store.HEARTBEAT_WINDOW_SEC`(=90) 재사용
- **acceptance**:
  1. AI 로그인 만료로 답변이 실패하는 계정의 화면이 **`답할 AI 있음: ❌` + 다음 행동**을 보인다.
  2. 재부팅으로 클라이언트가 안 뜬 계정이 `연결됨 ✅ / 듣는 중 ❌` 로 **갈라져** 보인다.
  3. 단독 페이지와 모달이 **같은 판정**을 쓴다(P0-L 계약).
  4. 상태 갱신이 국면당 1회로 수렴한다(재로드 순환 금지).
  5. **PB-0008** 실 Windows 브라우저로 3상태 시각 확인.
- **guards**: 판정 실패는 기존 fail-open(「연결됨」)을 유지(P0-G).
- **effort**: 中
- **notes**: 웹 자산 변경 → **PB-0008 필수**(`<project_root>/FIRST_REQUEST.md`
  `visual_verification_scope: always`).

---

### ITEM-05 · AI CLI 허용 목록 3자리 정합 (드리프트 수정)
- **status**: **done** (2026-09-02) — census 결과 3자리가 아니라 **6자리**였다(FUNCTION.md P0-Z6.1-a)
- **feature_id**: `feature-0043-external-llm-bridge`
- **dimension**: structural
- **risk_grade**: Minor
- **depends_on**: []
- **enables**: []
- **why**: RESEARCH F-010 · §1.1. `ollama` 가 설치 스크립트·서버 안내에는 남아 있는데 러너
  `_RUNTIME_SPECS` 에는 P0-Z6.1 로 제거됐다(`_CLI_ADAPTERS` 는 그 파생). **설치는 통과하고
  런타임에서 실패**한다. **클라이언트도 같은 목록을 쓰므로 먼저 정리해야 그 결함을 물려받지 않는다**
  (`reuse-inherits-defects`).
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
  3. `BRIDGE_PROBED_AI='ollama'` 가 설치 단계에서 거부된다.
- **guards**: **제거만 하고 동기화 테스트를 안 걸면 다음 런타임 추가 때 재발**한다
  (AGENTS.md §16.7 G10).
- **effort**: 小

---

### ITEM-06 · 「AI 없음」 안내를 클라이언트 유도로 전환
- **status**: **done** (2026-09-03) — 단 클라이언트 **배포 채널 없음**(리눅스 파이프라인이 Windows exe 를 못 만든다) → 「있을 때만 권한다」로 구현
- **feature_id**: `feature-0043-external-llm-bridge`
- **dimension**: functional
- **risk_grade**: Minor
- **depends_on**: [ITEM-08]
- **enables**: []
- **why**: RESEARCH F-007. 현재 안내(`_AI_SETUP_URL`)는 **CLI 설치 문서 한 곳**만 가리키고, 그 끝은
  터미널이다. 클라이언트가 설치를 대행하면 안내의 정답이 바뀐다 — *"클라이언트를 받으세요"*.
- **fit_verdict**: **adopt-with-guard**
- **what**: 「쓸 수 있는 AI 를 찾지 못했습니다」 경로를 **클라이언트 다운로드로** 유도한다.
  클라이언트가 커버하지 못하는 런타임(SPIKE-02 판정 결과)만 종전 CLI 안내를 남긴다.
  구독 요건(Pro/Max/Team/Enterprise 등)을 함께 표시한다.
- **entry_points**:
  - `unit/feature-0043-external-llm-bridge/src/agent/discovery.py:190` `_AI_SETUP_URL` ·
    `:193` `_no_ai_message()`
  - `unit/feature-0003-agent-web-ui/src/static/ai-connect.html`
- **acceptance**:
  1. AI 미보유 사용자가 보는 안내의 **첫 행동이 클라이언트 다운로드**다.
  2. 클라이언트가 덮지 못하는 런타임은 **그 사실과 함께** 종전 안내를 준다(커버리지 과장 금지).
  3. 구독 요건이 표시된다.
- **guards**: ⚠ **커버리지 정확도가 이 항목의 전부다.** SPIKE-02 가 「대행 실행 불가」로 판정한
  런타임을 클라이언트가 덮는 것처럼 안내하면, 그 사용자는 설치를 마치고도 막힌다 — 현재보다
  나쁜 결말이며 P0-I 가 닫은 결함 클래스의 재발이다.
- **effort**: 小

---

## 4. 정합성 6축 review 요약 (클라이언트 기준 재판정)

| 축 | 판정 요지 |
|---|---|
| **1. 아키텍처 정합** | **구조 피벗 0.** 클라이언트는 러너 엔진(5,849행)을 그대로 내장하고 서버 계약(`/api/ai/mcp` · `bridge_heartbeat` · 스킴)은 **무변경**이다. 바뀌는 것은 «배포·설치·업데이트 껍데기» 뿐이며 셸 스크립트 1,531행이 그 자리에서 사라진다 |
| **2. 제약 정합** | `PROJECT.md §6` 충돌 없음. 온프레미스·폐쇄망 유지(클라이언트는 로컬 실행). **신규 제약 1건 명문화 — §0.1 ToS 경계**: 3사가 2026년에 구독 OAuth 의 제3자 사용을 차단했으므로 「로그인 위임」은 「대행 실행」으로만 구현한다. 위반 시 **사용자 계정 정지** 사례가 실재한다(Google, 유료 구독자 대량 정지) |
| **3. 보안·RBAC 정합** | 신규 서버 권한 **0**. 인증은 기존 `require_ai_token` 단일 해석기 그대로. **신규 위험 2건**: ⓐ 타사 설치기 실행 → 명시 동의 가드 ⓑ 벤더 자격증명 접촉 → ITEM-08 acceptance 7 이 «안 한다»를 검사한다. CA 는 **프로세스 한정** 계약 유지(전역 설치로 바꾸지 않는다) |
| **4. 성능·비용 정합** | 서버 부하 변화 **없음**(하트비트 규모 동일). **LLM 비용 증가 0**(서버는 추론하지 않는다). ⚠ **사용자 쿼터 축 변화 미확인** — `claude -p` 가 2026-06-15부터 Agent SDK 크레딧 풀에서 차감된다는 보고 → SPIKE-02 항목 4 |
| **5. 재사용 지렛대** | **매우 높다.** 엔진·런타임 감지·caps 신고·무결성 대조·스킴 핸들러가 전부 존재한다. 신규는 GUI·설치 관리자·자동 업데이트뿐이고, 그 대가로 셸 스크립트 1,531행이 소멸한다. **순 코드량이 줄 가능성이 있다** |
| **6. 측정 가능성** | ITEM-00 이 전환 **전** 기준선을 잡는다. `path_kind` 에 `native_client` 를 미리 정의해 ITEM-08 이 그대로 쓰게 했다 — 전후 비교가 같은 축에서 성립한다 |

## 5. 보류·기각 (재논의 방지)

### 5.1 이번 개정에서 내려간 항목

| 항목 | verdict | 사유 |
|---|---|---|
| **ITEM-02 MCPB 번들(`.mcpb`)** | **기각(reject)** | 사용자 지적 2026-09-02: *"현재 서비스는 claude 뿐만 아니라 다른 AI 모델을 모두 수용 가능해야 합니다."* MCPB 는 **Claude Desktop 전용**이라 그 요구를 원리적으로 만족하지 못한다. 클라이언트와 병행하면 화면이 다시 «내가 어느 쪽인가»를 묻게 되는데, 그것은 P0-H 가 이미 기각한 모양이다(*"사용자는 자기 AI 가 어느 쪽에 해당하는지 판정할 수 없다"*). **되살아날 조건**: 클라이언트 방향이 코드 서명 부재로 좌초하고 Claude Desktop 사용자 비중이 지배적일 때 |
| **ITEM-01 client_kind 분리 + supersede 한정** | **보류(defer)** | 존재 이유가 «MCPB 프록시가 하트비트를 보내면 사용자 러너를 축출한다» 였다. 클라이언트는 **러너 자체**라 `client_kind=runner` 이고 「나중에 연결된 쪽이 이긴다」가 의도된 동작이 된다 → 동기 소멸. **되살아날 조건**: 등록형(비-러너) 경로를 다시 도입할 때 **하드 선행**으로 복귀 |
| **ITEM-04 연결 축 2분할** | **ITEM-08 에 흡수** | 「지금 답 받기 / 자리 비워도 처리」를 나눠 물으려던 이유는 러너 설치가 비쌌기 때문이다. 클라이언트가 상주까지 기본 제공하면 **나눌 이유가 사라지고** `/ai/connect` 는 「클라이언트를 받으세요」 한 줄이 된다 — 그것이 접근성의 최선이다 |
| **ITEM-07 Claude Code 플러그인** | **보류(defer)** | 클라이언트가 CLI 사용자까지 덮으므로 중복이다. 플러그인은 **이미 Claude Code CLI 를 능숙하게 쓰는 사용자**에게만 더 가벼운데, 그 층은 지금도 막히지 않는다(원 마찰은 비개발자다) |

### 5.2 이전 개정에서 내려간 항목 (유지)

| finding | verdict | 사유 |
|---|---|---|
| F-005 서버측 폴백 티어 | **보류** | 사용자 결정 *"서버 추론 복원은 보류"*. BYO-AI 로 덮이지 않는 사용자가 관측되면 재개 |
| F-009 공인 인증서 전환 | **논외** | 사용자 결정 *"아직 배포 전이며 현재 병목이 아니다"* |
| F-004 Intune/GPO 배포 | **보류(미판정)** | MDM 존재 여부 미응답. ⚠ **코드 서명 확보 불가 시 이 항목이 유일한 대안**이 되므로 그때 우선 재질의 |
| F-002 러너 단일 실행파일 · F-003 네이티브 설치 관리자 · F-008 자동시작 | **ITEM-08 에 흡수** | 셋 다 클라이언트가 하는 일의 부분집합이다 |
| `claude.ai` 원격 커스텀 커넥터 | **기각** | LAN + 사설 CA 라 Anthropic 인프라가 우리 서버로 아웃바운드할 수 없다. F-009 논외 확정으로 열리지 않는다 |
| 로컬 LLM(ollama) 어댑터 복원 | **기각** | P0-Z6.1 사용자 결정으로 제거. ITEM-05 는 그 결정의 **잔재 정리**이지 복원이 아니다 |
| **클라이언트가 OAuth 를 자체 구현/토큰 보관** | **기각(하드)** | §0.1. 3사가 2026년에 차단했고 Google 은 유료 구독자 계정을 정지했다. 어떤 편의도 이 선을 넘는 근거가 되지 않는다 |

## 6. 진행 현황

- 총 **5** (ITEM 4 + SPIKE 1) · **done 5** · in-progress 0 · pending 0 · blocked 0 — **로드맵 전 항목 완료**
- **완료**: `ITEM-05`(2026-09-02) · `ITEM-00`(2026-09-03) · `SPIKE-02`(2026-09-03, conditional-go)
- **P0 전량 완료 + ITEM-08 초판 완료.** 사용자 결정(2026-09-03)으로 **Windows 우선·미서명** 확정 — 서명 게이트 해소.
- **다음 (로드맵 밖 후속)**:
  1. **클라이언트 배포 채널** — Windows 빌드 산출물을 서버 `static/agent/` 에 놓는 경로. 이것이 없으면 ITEM-06 의 클라이언트 유도가 화면에 나타나지 않는다(현재는 정직하게 숨김).
  2. ~~**ITEM-00 라이브 적재 실측**~~ — **2026-09-03 완료**(아래 §10.1).
  3. 클라이언트 후속: 자동시작 · 자동 업데이트 · 벤더 설치기 동의 실행 · gemini 로그인 대행.
- **차단 해소에 필요한 조직 작업**: 코드 서명 인증서 확보 여부 확정(Windows + Apple).
  「확보 불가」면 F-004(사내 MDM 배포)로 대체 가능한지 재질의 → 둘 다 불가면 ITEM-08 재검토.
- 신규 feature 배정: `feature-0046-native-client` (초판의 `feature-0046-mcpb-connector-bundle`
  을 **재명명** — 해당 `unit/` 디렉토리가 아직 생성되지 않아 참조 파손 없음을 확인)

## 10.1 ITEM-00 라이브 적재 실측 (2026-09-03)

계측을 「짰다」와 「쌓인다」는 다른 축이다. 배포 후 실제 원장을 세어 후자를 확인했다.

**결함 두 겹이 순서대로 드러났다.** 계측 코드가 옳아도 적재는 0 이었다.

1. `first_heartbeat` 호출부가 존재하지 않는 이름(`account`)을 넘겨 `NameError` — 퍼널 기록이
   fail-open 이라 예외가 삼켜졌다. 화면·로그 어디에도 증상이 없었다.
2. 1번을 고쳐도 여전히 0. 원인은 **받는 쪽**이었다 — `build_audit_change_json` 의 명시
   허용목록에 `ai.connect.funnel` 이 없어 `unknown audit action` 으로 거부됐다(PR #1552).

두 번째가 이 사이클의 교훈이다. 처음 진단할 때 `[connect-funnel]` 만 grep 해서 **보내는 쪽**만
봤고, 실제 실패 로그는 `[TASK-0073 Phase A6] … unknown audit action` 이었다. fail-open 계측은
**양쪽 다** 조용히 실패한다 — 보내는 쪽과 받는 쪽 로그를 함께 봐야 한다.

**실측 결과** (배포 이미지 `85b6f9bb`, `WebAuditEvents`):

| step | 건수 | path_kind | 출처 |
|---|---|---|---|
| `first_heartbeat` | 2 | `runner_windows` | 실사용 계정 2개(10·27)의 상주 러너 |
| `page_view` | 1 | `unknown` | PB-0008 실제 Windows 브라우저 `/ai/connect` |
| `handoff_issued` | 1 | `runner_posix` | 연결 정보 발급 |

`COUNT(DISTINCT ResourceId)` = 4 = 총 행수 → dedupe 키가 계정×단계로 분리되고 있다.
`first_claim`·`first_answer` 는 아직 0 — 해당 사건이 발생하지 않았을 뿐이고, 같은
choke-point(`ai_tools.py`)를 쓰므로 앞 세 단계의 적재가 배선을 증명한다.

**아직 확인되지 않은 것**: `first_claim`·`first_answer` 의 실적재. 다음 실사용 답변 이후 확인.

## 10.2 클라이언트 배포 채널 — 서버가 실물을 못 만든다 (미해결)

`/api/ai/connect/status` 의 `client_download` 는 라이브에서 `null` 이고, 화면의 「연결 프로그램
받기」는 **숨겨져 있다**. 없는 다운로드를 안내하지 않는다는 ITEM-06 의 설계대로다.

원인은 파이프라인 축이다 — 배포는 Linux 컨테이너에서 이뤄지는데 PyInstaller 는 **실행 대상
OS 에서만** 그 OS 용 실행파일을 만든다. 즉 서버 빌드로는 `.exe` 가 나오지 않는다.

초판 실행파일은 Windows 머신에서 직접 빌드해 검증했다(`mysql-ai-client.exe`, 9,174,460 B,
sha256 `481f1ef291f42d89514301ada9e5d4f0fdf518a2d9b6fb910ccfc5a4631cf4e5`). 이것은 **1회성
수동 산출물**이며 배포 파이프라인에 들어 있지 않다 — 지금 화면이 숨어 있는 이유가 그것이다.

**필요한 후속**(택1, 조직 결정 필요):
- Windows 러너가 있는 CI 에서 빌드 → 산출물을 서버 정적 경로에 배치
- 사내 파일 서버/MDM 배포 → `client_download` 가 그 URL 을 가리키도록 설정

