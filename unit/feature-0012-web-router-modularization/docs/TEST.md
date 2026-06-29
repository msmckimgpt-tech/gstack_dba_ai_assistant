---
doc_type: TEST
feature_id: feature-0012-web-router-modularization
status: active
edit_policy: rewrite
source_of_truth: true
---

# Test Contract

## 1. 성공 조건
- `make test` 회귀 0 (안전망 1건 추가, 전체 green).
- `test_route_parity_p5b.py`: 현재 app 의 route 테이블이 골든(179 route)과 **경로·메서드·count·등록순서** 모두 일치 → PASS.

## 2. 실패 모드 (안전망이 잡아야 할 것)
- router 추출/`include_router` 이 경로를 **누락/중복** → count·set drift → FAIL.
- 경로/메서드는 같으나 **등록 순서 변경** → order diff → FAIL(`{var}` vs 구체경로 충돌이 라우팅 매칭을 바꿀 수 있음).
- 의도적 route 변경(신규 endpoint 등) → 실패 → **골든 스냅샷 갱신**으로 해소(behavior-neutral 추출은 갱신 불요).

## 3. 검증 기법
- Environment: 격리 agent 이미지 `make test`(`--no-deps`, pytest). `app.routes` 정적 열람(startup·DB 불요).
- Environment: Windows-browser(PB-0008) — **본 cycle 적용 N/A**(테스트/doc 만, UI 표면 무변경). 실제 router 추출 단위마다 적용(후속, env 필요).
- 골든 생성: `app.routes` 열거(path·methods[HEAD/OPTIONS 제외]·type, 순서 보존) → `route_snapshot_p5b.json`.

## 4. 복구 동작
- 안전망 fail = router 추출 회귀 신호 → 추출 되돌리거나 누락/순서 수정. 의도적 변경이면 골든 갱신 + REVIEW 기록.
