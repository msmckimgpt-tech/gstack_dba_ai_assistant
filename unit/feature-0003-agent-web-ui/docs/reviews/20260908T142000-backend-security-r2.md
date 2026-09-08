---
doc_type: REVIEW_ARTIFACT
feature_id: feature-0003-agent-web-ui
agent: backend-security
timestamp: 2026-09-08T14:20:00+09:00
trigger: 라운드 2 확인 라운드 (§18.8 수렴 계약 (a)) — 라운드 1 P1 폐쇄 + 신규 결함 탐색
verdict: CONCERN
---

컨테이너에서 워크트리 소스를 임포트해 함수를 직접 실행하고, 라이브 원장 9,759행 전건 재생.

## Half A — 라운드 1 P1 폐쇄 확인

| # | 항목 | 판정 |
|---|---|---|
| 1 | 규칙 (c) 과차단 | **CLOSED** — 재생 버려진 제목 19건(초판 412), 유출 3종 catch / 정상 2종 pass, census 25 실측 |
| 2 | 사유 축 손실 | **CLOSED** — 사유 3,144건 재생 중 버려진 사유 0건 |
| 3 | 파생값의 공격 payload 재주입 | **CLOSED** — 적대 `keyword` → `요청한 작업을 수행한다` |
| 4 | 파생 길이 무제한 | **CLOSED** — 100KB × 7도구 전부 len=255 |
| 5 | 유니코드 우회 | **CLOSED** — 전각 밑줄·전각 라틴·제로폭 전부 True |
| 6 | 진행 vs 완료 분기 | **CLOSED** — census 25 × {정상,적대} × {완료,진행} parity failures 0 |
| 7 | `sql_text` → `tool_result` 슬롯 | **CLOSED** |
| 8 | census 누락 2종 | **CLOSED** |
| 9 | `_resolve_step_display(None)` | **CLOSED** |
| 10 | `intent` 유출 | **PARTIALLY** — share·live 는 닫힘, 인증 메인 경로 잔존 (F1) |

### 1. Blocking issues

- **F1 (medium) `intent` 가 인증 클라이언트 payload 에 그대로 남아 있다.**
  - Evidence: `_resolve_step_display` 반환 키에 `intent` 원문 보존. 라이브 원장 — census 도구
    식별자가 든 행 **3,254건**, 인자 리터럴까지 든 행 **14건**. `_record_bridge_step` 이 지금도
    `intent = f"{tool_name}: …"` 를 새로 적재한다.
  - Location: `src/routers/_conv_store.py:2594` · `src/routers/ai_tools.py:1865`
  - Reason: 판정축은 「렌더 여부」가 아니라 「나가는가」다(§16.8 B-2(a)). 같은 커밋이 공유·진행
    경로에는 같은 논거로 제거했다.
  - Action: 표시 dict 에서 `intent` 를 빼고, 신규 적재의 도구명 접두도 끊어라.
- **F2 (medium) census 25 중 8이 손 열거** — `scratch_tool_defs()` 가 런타임 스위치로 `[]` 를
  돌려주고 폴백이 무조건 합쳐진다. 게이트 없는 `_TOOL_HANDLERS` 는 21종을 담는다.
  - Location: `src/routers/_conv_store.py:6319`
  - Action: `_TOOL_HANDLERS` + 브리지 표면 조회를 1차 모수로 쓰고 폴백을 조건부로.
- **F3 (medium) 표시 경로가 AI 가 말한 적 없는 근거를 새로 만든다** — 저장 사유가 없던
  6,615행 중 **644행(6.6%)** 이 서버 작문 근거를 얻는데 프런트에 `reason_source` 를 읽는 코드가
  0건이라 AI 사유와 구분되지 않는다.
  - Location: `src/routers/_conv_store.py:6431` · `src/static/app.js:3564`
  - Action: 구분 표시를 넣거나 파생을 되돌려라 — 둘 중 하나는 골라야 한다.

### 2. Cross-domain concerns

- **F4 census 가 비면 규칙(b) 정규식이 모든 문자열에 매칭돼 제목이 전멸한다**(실행 확인).
  다음 리팩터가 반드시 밟는 지뢰이고 실패 모드가 조용하다.
- **F5 클라이언트 심층 방어가 두 렌더러 중 하나에만** — activity 행은 백틱만 벗기고 인자
  리터럴을 그대로 그린다. 대응 테스트가 그 줄을 고정 단언해 결손을 보존한다.
- **F6 `_BRIDGE_ONLY_NARRATION` 의 work 문구가 죽은 채 남아** `_DERIVED_WORK_TAIL` 과 다른
  문장을 들고 있다.

### 3. Challenge to current spec

규칙(b)의 「어디에나 등장하면 차단」은 파생값 자신을 자해한다(`table_name='execute_sql'` →
제목 붕괴, 실행 확인). 라이브 카탈로그에는 충돌 0건이나 축이 자기모순적이다. 진행(SSE)
경로에 이음매를 붙인 비용은 계측되지 않았다 — 파생이 필요한 `execute_sql` 행 120건은
94.8ms/프레임(`_extract_sql_tables` 지배). `_derive_step_work_tail` 의 3번째 인자는 이제 죽은
인자다. REPORT.md 의 「잔존 유출 0건」은 축(렌더 vs payload)을 명시해야 한다.

### 4. Verdict

CONCERN
