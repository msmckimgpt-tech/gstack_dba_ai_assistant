---
run_at: 2026-08-28T15:10:00+09:00
session: ai/root/feature-0043-bridge-model-selector
scope: P0-T — 모델·추론 조작면 제거 (P0-M supersede). 카탈로그·화면·전송·적재/전달 4지점
verdict: PASS (단위·통합) / 화면 확인은 사용자 육안검증(사용자 결정)
---

# Run — P0-T 조작면 제거

Environment: container (`make test`) · 로컬 pytest · Windows-browser(브리지 복구, 상세는
`unit/feature-0003-agent-web-ui/docs/test-runs.d/TASK-20260828T060000-bridge-model-selector.md`)

## 결과

| 대상 | 결과 |
|---|---|
| `unit/feature-0043-external-llm-bridge/tests` | **203 passed** |
| 컨테이너 `make test` 전체 | exit 0 (ruff 포함) |
| 러너 정본 ↔ `static/agent` 배포본 sha256 | 일치 |

## 이 cycle 이 잠근 계약

- 카탈로그: 차단 시 빈 목록 + `model_selector: "hidden"`, 해제 시 `"visible"` 복원 (**반환값** 검사).
- 화면: 두 항목 숨김 + 메뉴 열기 가드 (키보드·직접 호출 우회 차단).
- 전송: `sendPrompt` · `_submitMessageEdit` 양쪽에서 숨김 시 미동봉.
- 적재/전달: INSERT·`claim_request` 에서 두 컬럼 미사용, 죽은 헬퍼 제거, 러너 모델 인자 경로 제거.
- 이력 보존: 스키마 컬럼은 유지(과거 행의 값은 그때의 사실).

## 뮤테이션

게이트 조건 반전 → 카탈로그 반환값 테스트 2건 KILL. 소스 문자열 검사만으로는 잡히지 않는
축이라 반환값 테스트를 feature-0003 스위트에 별도로 두었다(웹 라우터 import 경계 때문).

## codex 독립 리뷰 (REV-20260828T063000)

P1 1건 · P2 2건 전건 조치. **P1 은 내가 만든 회귀였다** — 화면이 `model` 을 안 보내면 서버가
`API_DEFAULT_MODEL`(haiku)로 메꾸고 **그 값으로 모델 RBAC 를 검사**하므로, haiku 권한만 없는
계정은 개인 AI 처리와 무관하게 질문 자체가 403 이 된다. 같은 파일 바로 위의 토큰 쿼터 게이트가
이미 같은 이유로 조건부화돼 있었는데도 놓쳤다. 조작면을 없앨 때는 **그 값의 소비처 전부**를
따라가야 한다는 것이 이 cycle 의 교훈이다.

조치 후 재검증: feature-0043 + 카탈로그 + hardening = **214 passed**, 컨테이너 `make test` exit 0.

## rebase

`origin/main` 이 1커밋 전진(#1367 연결 상태 상시 표시)해 rebase 했다. 충돌 2건(`app.js` import
라인 · `TASK.md` 말미 append)은 union 으로 해소 — 양쪽 기능이 서로를 지우지 않는다.

## 미검증

로그인 이후 컴포저 화면. 사용자 결정으로 배포 후 육안확인에 위임했다.
