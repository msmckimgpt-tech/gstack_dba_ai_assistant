---
doc_type: REVIEW
feature_id: feature-0037-domain-synthesis
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260731T134000-domain-synthesis [CODEX: 반영 완료]

- **Related Change:** feature-0037 도메인 합성(L3, lazy) (CHG-20260731T133000).
- **Panel:** `codex exec` 적대 리뷰(fresh-context, 스테이징 diff 직접 판독).
- **반증 요청 가설:** ① 답변 경로 지연·부하 ② 사전 전량 생성 퇴화 ③ 재생성 판정 결함
  ④ 비용(상한 우회·중복 합성) ⑤ 워커·답변 경로 파손 ⑥ alembic live 안전성.

### codex 지적과 처리

| # | 지적 | 판정 | 조치 |
|---|---|---|---|
| C1 | **재생성 판정이 멤버 수·분석 수 변화를 놓치고, 25개 초과 클러스터의 변화도 놓친다**(cap 으로 자른 뒤 해시하므로) | **유효(P1)** | 해시에 카운트 포함 + 해시는 cap 전 전체 집합(최대 300)으로 계산. payload 만 25개로 자르고 **커버리지 합계는 전체 기준**으로 센다 |
| C2 | partial index 가 조회를 못 받는다 — 인덱스는 `generated_at IS NULL AND requested_at IS NOT NULL` 인데 조회는 후자만 봐서, 생성된 행이 쌓일수록 요청 이력 전체 스캔에 가까워진다 | **유효(P2)** | 미생성분을 **별도 쿼리**로 먼저(인덱스 적중), 남는 여유만큼만 기존 생성분 재검사 |
| C3 | advisory lock 획득 **전에** 합성이 실행된다 — lock 못 얻은 워커도 돌아 같은 스키마를 중복 합성할 수 있다. 이 pass 에는 행 단위 claim 이 없다 | **유효(P2)** | `if lock_acquired:` 게이트로 이동. 행 단위 claim 은 상태 전이를 늘려야 하는데 pass 상한이 3이라 lock 만으로 충분하다 |
| — | 사전 전량 생성 퇴화 | **반증됨** | `requested_at IS NOT NULL` 조건으로 요청 없는 스키마는 합성되지 않음 |
| — | 정상 경로 쓰기 | **반증됨** | 요약이 있으면 쓰기 없음(요청은 miss 때만) |
| — | 예외·커넥션 | **반증됨** | 흡수·close 확인 |
| — | alembic chain·GRANT | **반증됨** | revision·MAX_MIGRATION 정합, GRANT 명시 |

### Verdict

SHIP — P1 1건·P2 2건 전부 수정.

### 스스로 짚는 점

C1 은 **최적화(cap)가 정확성(재생성 판정)을 조용히 깨뜨린 사례**다. 25개로 자른 것은 토큰
보호였는데, 그 잘린 목록으로 해시를 계산하면서 "입력이 바뀌었는가"라는 다른 질문의 답까지
잘라 버렸다. 같은 데이터를 두 목적으로 쓸 때는 각 목적이 요구하는 범위를 따로 봐야 한다.

### 남긴 리스크

- 행 단위 claim 이 없어 lock 밖 경로가 생기면(예: 수동 호출) 중복 합성이 가능하다.
  현재는 insight tick 만이 호출자이고 그것은 lock 아래에 있다.
- 요청은 남았는데 클러스터 요약이 아직 없는 스키마는 계속 대기한다(합성 재료 부재).
  L2 가 채워지면 자연히 해소된다.
