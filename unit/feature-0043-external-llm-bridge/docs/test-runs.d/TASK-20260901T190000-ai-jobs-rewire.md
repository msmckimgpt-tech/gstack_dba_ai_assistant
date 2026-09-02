---
run_at: 2026-09-01T19:30:00+09:00
session: ai/claude/ai-jobs-rewire-external
scope: "남은 AI 기능 3종(그래프 능동 분석·테이블 인사이트·클러스터 라벨)을 연결한 개인 AI 로 배선 — PRE-DEPLOY"
verdict: PASS
---

# Run — TASK-20260901T190000-ai-jobs-rewire (PRE-DEPLOY)

## 자동 검증

| 항목 | 결과 |
|---|---|
| `make test` (컨테이너, 전용 compose 프로젝트) | 기록 시점 최종 실행 green |
| ruff | All checks passed |
| route 골든 (`route_snapshot_p5b.json`) | +1 / -0 — `POST /api/ai/connect/batch-consent` 만 |
| `docs/ROUTEMAP.md` | 재생성 (262 routes / 29 modules) |
| 러너 거울 2본 바이트 대조 | `cmp` OK (main 병합 후 재확인) |

## 신규 계약 21건

`test_ai_jobs_rewire.py`(15) · `test_batch_consent_toggle.py`(6)

- 배선 전 구간: `wired: True` 인 자동기입형은 **반영 함수가 실재**하는가(AST)
- 프롬프트 정본: 서버 호출과 위임이 **같은 조립 함수**를 부르는가(AST — 문자열 검사는 설명
  주석의 함수 이름까지 잡아 거짓 판정)
- 게이트: 닫혀도 위임 가능하면 통과 / 둘 다 없으면 거절 / 열려 있으면 러너를 묻지도 않음
- 반영: 늦은 답이 최신 값을 덮지 않음 · 대상 불명은 예외 · 빈 결과를 성공으로 접지 않음
- 중복: 배경 배치 적재가 `dedupe_key` 를 거는가 + 조회 대상과 저장 대상이 같은 값인가
- 자격 판정 단일화: 웹(`_console_llm`)과 워커(`node_analysis`)가 같은 함수를 부르는가
- **이음매**: 러너 안의 거울 구현(`apply_consent`·`normalize_consent`)이 서버 정본과 9행
  진리표에서 한 칸도 다르지 않은가 — 손으로 맞춰 둔 두 구현이라 이 대조가 없으면 한쪽만
  고쳐지는 날 웹 토글이 켜져 있는데 러너는 신고하지 않는다
- 하트비트 응답에 `batch_consent` 키가 **없으면** 러너가 직전 값을 유지하는가(진동 방지)

## 역검증 (mutants = 실제 출하 코드)

기준 커밋 `d1b2a688`(이 cycle 이전)에 신규 테스트를 그대로 얹어 실행:

- `test_ai_jobs_rewire.py` — **13/15 FAIL**
- `test_batch_consent_toggle.py` — 모듈 자체 부재로 **collection ERROR**
  (`ImportError: cannot import name 'bridge_consent'`)

통과한 2건은 「wired=True 인데 반영 함수 없음」 가드와 「delegable 목록에 배경 배치가 섞이지
않음」 — 기준 커밋에서는 **아무것도 wired 가 아니라 vacuous 하게 통과**한다. 그 사실을 여기
적어 둔다(통과했다고 그 검사가 무의미한 것은 아니지만, 그때 무엇을 봤는지는 다르다).

## 낡은 계약 테스트 재작성 (4파일)

| 파일 | 무엇이 낡았나 | 어떻게 고쳤나 |
|---|---|---|
| `test_ux_parity` | 「닫혔으면 거절」이 **곧 제보된 결함** | 「위임할 곳도 없으면 거절」 + 3경우 반환값 검사 |
| `test_routine_dbanalysis` | 위와 동형 | 거절 케이스 + **통과 케이스**를 함께 검사 |
| `test_runtime_model_selector` (2건) | 소스 문자열 핀 — 질의가 shared 로 옮겨가자 계약은 그대로인데 FAIL | **실제로 나가는 SQL** 과 **반환값**을 본다 |
| `test_node_analysis_retry` · `test_semantic_cluster_content` | 게이트 **뒤** 로직인데 게이트를 안 열었다 | autouse 픽스처가 `AGENT_SERVER_LLM_ENABLED=1` + 닫힌 게이트에서 위임하는지 보는 테스트 신설 |

## 이 실행에서 드러난 것 (기록)

- 새로 쓴 게이트-통과 테스트가 **게이트를 지나 실제 PG 에 연결을 시도**했다. 컨테이너는
  호스트 미해석으로 죽었고(그래서 잡혔다), 개발 머신에서는 라이브 원장에 run 을 만들 수
  있었다. `_rw_conn` 을 「PG 없음」으로 막아 고쳤다. 라이브 오염 여부는 실측 확인 —
  `node_analysis_runs` 에 `ds1` scope 행 **0건**(오염 없음).

## 미검증 — POST-DEPLOY 로 남는 것

**사용자 요구: 라이브 end-to-end 필수.** 아래는 배포·러너 갱신 후에만 확인된다.

- AC-1/-2: 그래프에서 노드 분석을 실제로 눌러 202 → 러너 로그 `kind=job` → 원장 `done` → 화면
- AC-3: 러너가 답하지 않을 때 lease 회수로 `pending` 복귀
- AC-4: 웹 토글 → ≤30초 안에 러너 신고 갱신
- AC-5: 동의 러너 0명일 때 콘솔이 그 사실을 말하는가
