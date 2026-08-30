---
doc_type: WIKI_HOT_CACHE
last_updated: 2026-08-31
---

# Hot Cache

## Last Updated
2026-08-31

## Key Recent Facts
- **feature-0043 브리지가 08-28 하루에 13 cycle 을 더 태워 배포 `35f03f62` 에 도달했다.** 서버 보유 Claude 계정(claude-corp/root)으로는 여전히 추론하지 않고, 차단은 두 겹이며 **코드(`shared/llm_gate.py`)가 정본**(기본값=차단)·`litellm_config.yaml` alias 주석이 두 번째 자물쇠다. 로컬 임베딩(bge-m3)만 살아 있다.
- **연결이 요청의 전제조건이 됐다.** `연결됨`(토큰) × `대기 중`(러너) 곱을 서버(`compose_blocked`)가 단독 판정하고, 미연결 요청은 `409 bridge_blocked` 로 **아무것도 저장하지 않는다**(입력은 지우지 않는다). 기본 진입점은 AI 지시문이 아니라 **원클릭 셸 명령**(`bridge_setup.sh`/`.ps1`) — 해석층이 사라져 같은 입력이면 같은 결과다. 셋째 길로 환경 **판단만** 그 머신의 AI 가 `BRIDGE_PROBED_*` 네 칸을 채우고 스크립트가 실존·타입·범위·allowlist 로 다시 본다.
- **동시 처리는 수요를 따라간다.** 워커는 **1개**로 시작해 대기 질문 수만큼 확장(상한 `--max-workers` 기본 8 · 예측 확장 없음), 300초 유휴 슬롯을 LRU 로 회수하되 **최소 1개 유지**. tick 은 별도 타이머가 아니라 long-poll 반환이다. 모델·추론등급 목록의 출처는 **러너 자신의 하트비트 신고**라 서버는 이름을 모른 채 운반만 하고, 새 런타임 지원에 서버 배포가 필요 없다. 하트비트가 도는 동안 연결은 시간으로 끊기지 않는다(웹 로그아웃만 즉시 무효 + 러너 자동 종료).
- **실 LLM 8축 + PB-0008 5축 전건 PASS.** 사전 코드분석이 예측한 괴리 중 **인라인 쿼리결과·rationale 2건은 오판**이었다 — 원장 한 곳(`tool_call_usage`)이 비었다고 그 정보가 어디에도 없는 것은 아니었다. 세 번째로 예측했던 **결과 CSV 는 지금도 미복원**(FUNCTION §「의도적으로 복원하지 않은 것」) — REPORT §7.0 의 '3건 전부 오판' 서술과 갈리는 **정본 내부모순**이라 미러는 보수적으로 적는다.

## Recent Changes
- `bridge_agent.py` — 동적 워커 풀 · 30초 하트비트 + 능력 신고 · `--ai` 상속 범위 정정 · `bridge_setup.{sh,ps1}`(원클릭 · `BRIDGE_PROBED_*` 검증)
- `routers/ai_tools.py`(`bridge_heartbeat`·`compose_blocked`·`compose_probe_setup_instruction`) · `static/ai-connect.js` · `static/app/{connect-modal,messages,composer,attach-diff}.js`
- `shared/attachment_write.py`(신규) — assistant 첨부 쓰기 시퀀스를 worker·브리지가 **같은 함수**로 부른다(저장 가드가 갈리면 느슨한 쪽이 진실이 된다)
- feature-0006 Caddyfile — 설치 스크립트 **2파일만** 평문 HTTP 개방(사내 CA 부트스트랩 데드락 · `/static/*` 통째 개방 아님)
- `bin/win-browser.py` — `session-login` 이 사용자 탭을 자기 것으로 오인해 닫고 브라우저를 통째로 죽이던 결함 수정

## Active Threads
- **취소 후 `submit_answer` 409 집행은 여전히 미검증.** 러너는 취소를 인지해 제출 **전에** 하차하므로(설계대로다) 그 경로에 닿지 않는다 — 신호를 읽지 않는 등록형 AI 로만 재현된다. 함께 묶여 있던 진행 **단계** 표시는 08-28 실 LLM 검증에서 PASS 로 해소됐다.
- **원클릭 실 머신 확인 · URL 스킴 핸들러 등록의 OS 별 실측**(macOS `lsregister` · Linux `xdg-mime` · Windows HKCU)은 각 OS 와 새 토큰이 필요해 미수행. 실패 시 거동(연결은 되고 버튼만 안 됨 + 그 사실 고지)은 소스에 고정.
- **긴 조사의 무제한 대기 미재현** — 검증 질문이 40초에 끝나 900초 벽에 닿지 못했다. 코드·배포본 반영만 확인.
- **동기 inproc 경로(`_ask_impl`)의 첨부 쓰기는 아직 세 번째 구현**이다(응답 body shape 상이) — 합치는 것은 별도 cycle.
- **`.env` 위생** — `AGENT_*_MODEL` 계열은 게이트가 차단선을 쥐어 기능상 무해하나 운영자 직접 주석 권장(세션 권한상 AI 가 읽기·수정 불가).
