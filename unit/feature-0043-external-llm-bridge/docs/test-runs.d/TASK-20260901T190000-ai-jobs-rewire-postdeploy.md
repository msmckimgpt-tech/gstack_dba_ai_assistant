---
run_at: 2026-09-02T18:50:00+09:00
session: ai/claude/ai-jobs-rewire-external → ai/claude/ai-jobs-auto-run-delegation
scope: "남은 AI 기능 3종의 개인 AI 배선 — 라이브 POST-DEPLOY 실측 (배포본 f04b0acc)"
verdict: PASS
---

# Run — TASK-20260901T190000-ai-jobs-rewire (POST-DEPLOY)

배포 4회: `d18da709`(본체) → `7d9f8723` → `3244ccce` → **`f04b0acc`**(최종).
전 서비스 SHA 일치 · `no upstreams available` **0건** · `WebAccounts.BridgeBatchConsent` ALTER 적용.

## AC 실측

| AC | 결과 | 근거 |
|---|---|---|
| **-1** 게이트 통과 | PASS | `enqueue_analysis(requested_by='admin')` → `{'ok': True, 'status': 'running'}` |
| **-2** 위임→반영 | PASS | 러너 `task.dispatch kind=job **model=haiku**` → job `done` + 분석문 297자 + `role=stats` + **run 마감** + `JobAppliedAt`, `JobApplyError` 없음 |
| **-3** lease 회수 | PASS | job 30441(콘솔 작업 취소 → 답이 영영 안 옴)이 **손대지 않았는데** 회수→재위임→`done` |
| **-4** 웹 토글 | PASS | 실제 체크박스 클릭 → DB 기입 · 켜기 **50초** / 끄기 **48초** 만에 러너 신고 반영 |
| **-5** 동의 0명 표면화 | PASS | 콘솔 `배경 작업 동의 0 (사용자가 '내 AI 연결' 에서 켤 수 있습니다)` · 1명일 땐 `동의 1` |
| **-6** 게이트 되돌림 | PASS | enqueue 는 러너를 묻지도 않고 통과 · 위임 분기는 `not server_llm_enabled()` 안에만 존재 |

## 배경 배치 2종

| 종류 | 결과 |
|---|---|
| `cluster_label` | 위임 → 러너 처리 → **kv 캐시에 `몬스터 스폰` 기입** |
| `insight_summary` | 반영 오류 없음 + KV 이음매에 `{"domain": "Game Data", "summary": "This table stores clan rankings…"}` |

## 정상 운영 경로 (손대지 않고 관찰)

마지막 배포 후 **아무 명령도 내리지 않은 90초** 동안:
`위임중 0 → 5 → 0` · `개인 AI 로 완료 13 → 18`. 워커가 스스로 집어 위임하고 반영한다.

## ⚠ 라이브가 잡은 결함 **6건** — 전부 단위 전건 green 상태에서 나왔다

| # | 결함 | 성격 | 수정 |
|---|---|---|---|
| 1 | `auto:insight-change` run 이 영원히 위임 불가 | `requested_by` 를 사용자명으로만 상정 | 배경 동의 풀 폴백 + 실패 상한 |
| 2 | 토글 문구 "30초" vs 실측 50초 | 내가 쓴 문장이 사실과 다름 | "1분 안에" |
| 3 | 배포 프리플라이트가 exec 오류 문구를 CA 로 해시 | **오진단으로 배포 차단** | PEM 확인 + 판정 불가는 skip |
| 4 | `apply_external_insight_summary` 성공 경로 `NameError` | 테스트가 **거절 경로만** 돌림 | 로거 + 성공 경로 테스트 |
| 5 | `save_memory_kv` 가 쓰기 실패를 삼킴 | "안 써도 성공" | **되읽어 확인** |
| 6 | **워커가 `process_pending` 을 아예 안 부름** | 호출부가 `if _llm_open` | 게이트 제거 |

### 6번이 이 cycle 의 핵심 교훈

나머지 5건을 다 고쳐도 **정상 운영에서는 아무것도 돌지 않는** 상태였다. 그리고 앞선 라이브
검증(AC-1·AC-2)이 통과한 것은 **내가 `process_pending` 을 손으로 불렀기 때문**이다 — 헬퍼가
옳은 것과 진입점이 그것을 부르는 것은 다른 사실이다.

**탐지 수단은 관찰 기반 AC 하나였다.** AC-3(회수)을 20분 실경과로 관찰하지 않았다면
(lease 900초를 **1424초**까지 넘겨도 회수 없음) 이 결함은 배포된 채 남았고, 사용자는
"202 는 뜨는데 결과가 안 온다" 를 겪었을 것이다.

그리고 그 게이트를 **테스트가 지키고 있었다** — `test_insight_skips_only_llm_work` 가
`"process_pending() if _llm_open else {}"` 를 단정했다. 전환 이전엔 옳은 계약이었고, 전제가
깨진 뒤에도 아무도 다시 읽지 않았다.

## 검증 수단

- `make test` green(컨테이너) · ruff clean · `verify-completion` PASS
- 계약 테스트 **누적 37건** 신설 · 낡은 계약 테스트 **5파일** 재작성
- 뮤테이션 **12종**: 10 KILL · 2 등가(M5/M5b 는 서로 되메움, 동시 제거 M5c 는 KILL)
  - ⚠ 자체 적발 2건: M3(dedupe)은 「키를 넘기는가」만 보고 「작동하는가」를 안 봐서 생존,
    M5 확인 중 배급 자격 판정에 **행위 테스트가 아예 없다**는 공백 발견

## 정리한 것 / 남긴 것

- 검증용 배치 동의(`bootstrap_admin`·`admin`) **원복 완료** — 동의는 계정 소유자의 것이다.
  배경 배치를 실제로 돌리려면 '내 AI 연결' 에서 켜야 하고, 콘솔이 그 사실을 말한다.
  ⚠ 그동안 **사용자 요청 분석(그래프 능동 분석)은 영향 없다** — 그건 요청자 계정의
  `console_jobs` 자격으로 가고 배경 동의를 요구하지 않는다.
- 검증용 브라우저 세션 로그아웃 완료.
- `bootstrap_admin` access 토큰 5개가 남아 있으나 **이 세션이 만든 것이 아니다**(3~7시간 전,
  4개는 하트비트 이력 없음). 병렬 세션의 검증을 끊을 수 있어 폐기하지 않았다.

## 알려진 한계

- `insight_summary` 는 **테이블 축만** 배선됐다(라벨을 "테이블 인사이트 배치" 로 좁혔다).
  스키마·계정 인사이트는 서버 경로뿐이라 게이트가 닫힌 지금 계속 스킵된다.
- AI 가 `{"labels":[]}`(라벨할 것 없음)를 주면 `cluster_label` 반영이 실패로 기록되고 그 배치는
  다음 pass 에 재적재된다. **비용 성질은 전환 이전과 같다**(그때도 캐시 미스로 재호출).
- 배경 배치의 위임 대상은 「동의한 러너 중 가장 최근 하트비트」 하나다. 여러 명이 동의해도
  분산하지 않는다 — 분산하려면 "누가 얼마나 태웠는가" 를 관리해야 하고 이 축의 범위 밖이다.
