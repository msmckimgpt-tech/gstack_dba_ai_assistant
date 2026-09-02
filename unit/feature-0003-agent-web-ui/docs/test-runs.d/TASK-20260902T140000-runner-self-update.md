---
run_at: 2026-09-02T14:40:00+09:00
session: ai/claude-corp/feature-0043-runner-self-update
scope: 러너 자기 갱신 + 자기갱신 러너의 낡음을 화면에서 감추기
verdict: PASS (신규 30건 · 뮤테이션 12/12 KILL · 기준선 동일) — 화면 축은 POST-DEPLOY 실측
---

# Run — TASK-20260902T140000 러너 자기 갱신

## Environment: Windows-browser (PB-0008) — **POST-DEPLOY 에 이 절을 채운다**

화면 축(`connect-modal.js` 의 낡음 접기)은 배포 전 확인이 **불가능**하다: JS 는 `docker cp`
로 미리 볼 수 없고(자산 지문 미주입 + 브라우저 모듈 캐시로 구버전이 도는 함정), 서버가
`runner_self_updating` 을 아직 싣지 않아 접는 식이 물릴 값 자체가 없다.

배포 뒤 확인할 것:

1. `connect_status` 응답에 `runner_self_updating` 이 실린다.
2. 새 빌드 러너의 `RunnerFeatures` 에 `self_update` 가 들어간다.
3. 그 러너가 낡은 상태에서 칩이 **「업데이트 필요」를 보이지 않는다**.

## 배포 전 실측

### 배포본 자기 인식 (실물)

빌드된 단일 파일을 그 파일로 실행해 확인:

| 관측 | 값 |
|---|---|
| `_self_build()` | 파일 sha256[:12] 와 **일치** |
| `running_bundle_path(_self_build())` | 그 파일 경로 **반환** |
| `AGENT_FEATURES` | `('console_jobs', 'self_review', 'self_update')` |

### 개발 트리 보호 (반대 방향)

모듈 실행에서는 `_self_build()` 가 `agent/events.py` 지문(`579c425cb6fa`)이라 배포본과 다르고,
`running_bundle_path()` 가 **`None`** 을 돌려준다 — 자기 갱신도, `self_update` 신고도 없다.
이 검사가 없으면 러너가 개발자의 소스를 배포본으로 덮어쓴다.

### 자동 검증

| 대상 | 결과 |
|---|---|
| `tests/test_runner_self_update.py` **30건**(신규) | **PASS** |
| 뮤테이션 **12종**(M1~M12) | **12/12 KILLED** |
| `feature-0043` + `feature-0003` + `feature-0002` 전량 | **main 기준선과 동일** (잔여 2건은 main 에도 있는 순서 의존 기존 실패) |
| ruff | clean (F821 1건은 main 기준선) |
| 배포본 stdlib-only | 표준 라이브러리 밖 import **0** |

### 뮤테이션이 잡은 헛통과 2건

- **M2**: 「평문에서는 받지 않는다」가 **DNS 실패** 덕에 통과하고 있었다 — 가드를 지워도
  `None` 이었다. 대조군(https 는 통과) + 「호출 자체가 없었음」 단정으로 재작성.
- **M11**: except 블록을 «빈 줄까지» 로 잘라 그 뒤의 `return False` 가 딸려 들어왔다 —
  안을 `return True` 로 바꿔도 통과. 들여쓰기 경계로 자르도록 수정.

둘 다 **단언이 참이 되는 경로가 하나가 아니었다.** 뮤테이션이 없으면 영원히 모른다.

### 번들 평탄화 함정 (자체 검토)

`from . import selfupdate` 는 번들러가 벗겨 내 배포본에서 `NameError` 가 된다(기존 테스트
5건이 그 형태로 죽어 발견). 이름 직접 import 로 바꾸고, 평탄한 4,800줄 네임스페이스에서
충돌하지 않도록 `install`·`digest`·`reexec` 를 도메인 접두로 개명했다.

## 부트스트랩 한계

이 기능은 **이 기능이 들어간 빌드부터** 발효한다. 지금 도는 러너는 자기 갱신을 모르므로 한
번은 런처가 갈아 끼워야 한다(그 경로는 `TASK-20260902T100000` 에서 라이브 동작 확인 —
13:36:51 실측). 그 한 번 뒤로는 배포가 몇 번을 나든 화면에 조치 요구가 뜨지 않는다.
