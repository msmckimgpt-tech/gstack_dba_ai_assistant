# TASK-20260903T200000 — 「모른다」를 정상으로 말하지 않는다

- verdict: PASS (PRE-DEPLOY)
- scope: feature-0043-external-llm-bridge (러너) + feature-0003-agent-web-ui (서버·화면)
- 근거: 사용자 지적 2026-09-03 *"연결되지 않은 상황이 정상 연결되었다고 거짓으로 출력되는
  부분을 수정하는 작업입니다. claude 인증 상태는 현상일 뿐입니다."*

## 1. 무엇을 관측했나 — 결함의 인과 사슬

| 지점 | 종전 값 | 결과 |
|---|---|---|
| `state._AI_READY` 초기값 | `True` (fail-open) | 확인된 바 없는데 「정상」 |
| `api.heartbeat` | `bool(_ai_ok)` → `true` | 서버로 「정상」 전달 |
| `WebOAuthTokens.RunnerAiReady` | `1` | 화면 판정 근거가 거짓 |
| 칩 | `state=on` 「대기 중」 | **사용자가 본 거짓** |
| 캐시된 caps 경로 | 협상 `ask` 가 빈다 | 관측 기회조차 없음 ← **라이브 경로** |

## 2. 단위 테스트

```
$ PYTHONPATH=… python3 -m pytest -q unit/feature-0043-external-llm-bridge/tests/test_unknown_is_not_ready.py
13 passed in 0.34s

$ PYTHONPATH=… python3 -m pytest -q unit/feature-0043-external-llm-bridge/tests/test_ai_unusable_surfaced.py
18 passed in 0.15s      (종전 15건 → 4건 재작성 + 3건 신설)

$ PYTHONPATH=… python3 -m pytest -q unit/feature-0003-agent-web-ui/tests/test_ai_ready_surfaced.py
19 passed in 0.13s      (종전 13건 → 1건 갱신 + 7건 신설)
```

핵심 단정 3건 (나머지는 파일 docstring 참조):

- `test_starts_unknown_not_healthy` — 초기값이 `(None, "")`. 종전은 `(True, "")` 였고
  **그 테스트가 결함을 잠그고 있었다**.
- `test_unknown_does_not_block_questions` — 그러나 `ai_blocked() == (False, "")`.
  게이트 축은 fail-open 유지 — 접으면 모든 첫 질문이 죽는다.
- ⭐ `test_cached_caps_path_still_settles_the_state` — **라이브의 그 경로**. `config.json` 에
  caps 를 심어 협상이 아무것도 묻지 않게 만든 뒤 러너를 실제로 띄웠다. 협상 요약 루프
  (`for n in ask`)가 한 번도 돌지 않으므로, 원장이 `False` 로 떨어졌다면 그것을 한 것은
  **생존 확인뿐**이다 — 즉 이 단정이 곧 배선의 실증이다. 관측: `ai_health() == (False,
  "이 컴퓨터의 claude 가 응답하지 않습니다 — OAuth access token has expired.")`.

## 3. 적대적 뮤테이션 스윕 13종 (리뷰 패널 대체)

본 세션은 `Agent` 서브에이전트 호출이 금지되어 있어, 결함을 되살리는 최소 편집마다 테스트가
실제로 죽는지 확인하는 방식으로 대체했다. 스크립트: `mut_sweep.py` (커밋 대상 아님).

**1R — SURVIVED 2/13**:

| id | 뮤테이션 | 판정 | 원인 |
|---|---|---|---|
| M3 | `note_ai_probing` 의 `False` 가드 제거 | **ANCHOR-MISS** | 뮤테이션 문자열 들여쓰기 불일치 → **적용조차 안 됐다.** 그 상태의 초록은 KILL 이 아니라 「아무것도 검증하지 않음」 |
| M6 | 협상 경로의 `note_ai_probing` 호출 제거 | **SURVIVED** | 제 테스트가 소스 문자열 존재만 봤고, 호출부가 두 곳이라 하나 남으면 통과 — 「죽은 가드」를 테스트 쪽에서 재현 |

조치: M3 앵커 정정 · M6 는 협상 본체가 불린 **그 순간의 원장 값**을 보는 행위 단정으로 교체.

**2R — 전건 KILLED (13/13)**: M1 fail-open 복원 · M2 게이트가 `None` 을 막음 · M3 세탁 ·
M4 하트비트 `bool()` 압착 · M5 생존 확인 배선 제거 · M6 협상 시작 표시 누락 · M7 실패를
로그만 남김 · M8 명시 `reported` 무시 · M9 NULL-불안전 비교 · M10 키 존재 판정 제거 ·
M11 「확인 중」 갈래 죽은 가드 · M12 모달 판정 느슨화 · M13 「확인 중」을 정상 초록으로.

⚠ 스윕은 매 뮤테이션마다 `make bridge-agent` 로 **번들을 다시 굽는다**. 러너 번들은 빌드
생성물이라 이 단계가 없으면 뮤테이션이 테스트에 도달하지 않아 전건 KILL 로 위장된다
(직전 cycle 실측 함정).

## 4. 회귀

`unit/feature-0043-external-llm-bridge/tests` · `unit/feature-0003-agent-web-ui/tests` ·
`unit/feature-0041-external-ai-tool-surface/tests` — 결과는 §6 에 기록.

`test_share_redaction_invariant.py` 7건은 **미변경 `main` 에서도 동일하게 실패**한다
(`ModuleNotFoundError: No module named 'web'` — 컨테이너 밖 PYTHONPATH 차이). 이 cycle 의
회귀가 아니며, CI 컨테이너에서는 해당 경로가 제공된다.

## 5. 남긴 미검증 (정직 표기)

- 질문을 **이미 보낸 뒤** 확인이 실패로 떨어지는 창(최대 30초)에서 그 질문은 즉시-정직-응답
  경로를 타지 못한다. 종단 보장은 P0-AK 소관이며 이 cycle 이 좁히지 않았다.
- 사용자 머신의 `claude` 재인증 자체는 사용자 조치다. 이 cycle 이 고친 것은 **그 상태가
  화면에 정직하게 나타나는가** 이며, 사용자가 말한 대로 인증 상태는 현상일 뿐이다.
