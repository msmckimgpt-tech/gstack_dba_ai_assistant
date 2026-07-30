---
doc_type: REVIEW
feature_id: feature-0033-analysis-synthesis
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260730T083000-cluster-summary [CODEX: 반영 완료]

- **Related Change:** feature-0033 클러스터 합성 요약(L2) (CHG-20260730T082000).
- **Panel:** `codex exec` 적대 리뷰(fresh-context, 스테이징 diff 직접 판독).
- **반증 요청 가설:** ① 요약 → 시그니처 → 재임베딩 순환 ② 캐시 키 오적중·영구 미스
  ③ 비용 폭주(상한 우회) ④ 요약 실패가 클러스터 pass 를 깨뜨림 ⑤ 저장 정확성(id churn·경합)
  ⑥ alembic live 안전성.

### codex 지적과 처리

| # | 지적 | 판정 | 조치 |
|---|---|---|---|
| C1 | **상한 40이 pass 전체가 아니라 effective-schema 루프 내부**에 적용된다 — 실제 최대치가 `Σ schema × 40` 이라 스키마 수(라이브 수백 개)만큼 곱해진다 | **유효(P1)** | 호출측이 `rep["summaries"]` 로 이미 쓴 몫을 빼고 `remaining` 을 넘기도록 변경. 회귀 테스트(remaining=2/0) |
| C2 | **토큰 예산이 pass 진입 시 1회만 확인**된다. 이후 배치의 `acquire("llm")` 은 동시성 슬롯일 뿐 누적 소비와 무관한 축이라, 긴 pass 도중 예산이 소진돼도 끝까지 호출한다 | **유효(P1)** | 배치 루프마다 `llm_budget.allowed()` 재확인(60초 캐시라 PG 부담 없음). 회귀 테스트 |
| C3 | 증거 매칭이 대소문자에 취약 — 어긋나면 `evidence_version` 이 영구히 `""` 가 되어 **L0 변경이 요약에 전파되는 유일한 경로가 조용히 죽는다** | **유효(P1)** | 증거 맵 키·조회를 casefold 정규화. 회귀 테스트 |
| C4 | `_summary_cache`·`_evidence_versions` 가 SAVEPOINT 없이 예외만 삼킨다 — non-autocommit 커넥션에서 신규 테이블 부재 시 트랜잭션이 aborted 되어 뒤따르는 라벨 역기록 UPDATE 가 전부 깨진다 | **유효(P2)** | `_summary_savepoint` 도입, 조회·적재 3곳에 적용. feature-0031 에서 배운 것과 같은 계열의 결함을 반복했다 |
| C5 | upsert 가 버전 비교 없이 무조건 갱신 — 동시 실행에서 오래된 입력이 최신 요약을 덮을 수 있다 | **유효(P2)** | `WHERE ... IS DISTINCT FROM` 조건 추가(stale-writer 방지) |
| C6 | `_summary_put` 이 실패를 삼키는데 호출측은 무조건 `made += 1` — 캐시는 계속 미스인데 보고는 성공이라 다음 pass 마다 같은 요약을 재호출한다 | **유효(P2)** | bool 반환으로 바꾸고 성공만 카운트. 회귀 테스트 |
| C7 | 해시 입력이 개행 결합이라 `["a\nb","c"]` 와 `["a","b\nc"]` 가 같은 지문이 된다 + 64비트 절단 | **유효(P2)** | 길이 프리픽스 인코딩(단사)으로 교체 + 128비트로 확대. ⚠ 기존 `_member_set_hash` 는 **건드리지 않았다** — 그것은 라벨 캐시 키라 바꾸면 전량 미스 나 재라벨 폭주 |
| — | 요약 → 시그니처 순환 | **반증됨** | `build_table_signature_text` 가 요약을 참조하지 않고, 생성은 클러스터 확정 후 별도 경로 |

### Verdict

SHIP — P1 3건·P2 4건 전부 in-cycle 수정. 순환 가설은 코드 근거로 반증.

### 스스로 짚는 점

C4(savepoint)는 바로 앞 cycle(feature-0031)에서 **같은 결함을 자체 점검으로 잡았던 것**인데
이번에 반복했다. 같은 커넥션을 공유하는 모듈을 새로 만들 때는 조회 한 줄이라도 savepoint 로
감싸는 것을 기본값으로 삼아야 한다. FUNCTION.md §5 에 그 계약을 명시했다.

### 남긴 리스크

- routine 클러스터는 아직 요약 대상이 아니다(1차는 테이블 클러스터).
- 요약 품질은 배포 후 표본을 직접 읽어야 판정 가능하다(TEST.md §4).
