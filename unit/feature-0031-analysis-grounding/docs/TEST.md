---
doc_type: TEST
feature_id: feature-0031-analysis-grounding
status: active
edit_policy: rewrite
source_of_truth: true
---

# Test

## 1. Test Contract

**성공 조건**
1. **프라이버시 불변식** — 원시 컬럼 값이 저장·주입 어느 경로에도 실리지 않는다. 문자열 컬럼의
   min/max 값은 존재하지 않고, 형태 분류(`value_pattern`)만 남는다.
2. **보수적 시작 → 점진 승격** — 첫 접촉은 Stage 0(사용자 테이블 read 0), refresh 간격 이내면
   수집하지 않으며, 승격은 한 번에 한 단계이고 상한(운영자 knob·주간 시간창)을 넘지 않는다.
3. **부하 게이트** — `ds` 자원 예산이 거절하면 운영 DB 에 연결조차 하지 않고 다음 주기로 이월하며,
   거절 경로에서도 슬롯을 반납한다.
4. **payload 동형성** — 증거가 없으면 `evidence` 키 자체가 생기지 않아 종전 payload 와 같다.
   LLM 호출 수는 변하지 않는다.
5. **thin 판정 정합** — 프롬프트 계약("한국어 1~2문장")대로 쓴 분석이 thin 으로 잡히지 않고,
   실제로 빈약한 분석(항목 1개만 채워짐, 상투 무응답)은 잡힌다.

**실패 조건(회귀로 간주)**
- 집계 산출물·upsert 바인딩·evidence 블록 중 어디서든 원시 문자열이 발견되면 실패.
- 예산 거절 상황에서 `db.connect` 가 호출되면 실패.
- 수집 경로의 예외가 호출측(노드 분석)으로 전파되면 실패.

## 2. 자동 테스트

`unit/feature-0002-agent-core/tests/test_metadata_stats.py` (신규)

| 축 | 케이스 |
|---|---|
| A 프라이버시 | 분류 결과가 DB CHECK 열거 안에만 있음 · 입력 값이 반환에 섞이지 않음 · 집계 산출물에 원시 문자열 부재 · upsert 바인딩 문자열이 식별자+분류값뿐 · evidence 에 문자열 극단값 부재 |
| B 승격 | 첫 접촉 Stage 0 · refresh 창 이내 skip · 하루 1단계 · 상한 초과 금지 · 주간 시간창 상한 · Stage 0 표본 0행 |
| C 게이트 | 예산 거절 시 connect 미호출 + 슬롯 반납 · kill-switch 연동 · 자체 knob off · ensure_stats fail-soft · 식별자 화이트리스트(인젝션 형태 거부) |
| D payload | node_key 파싱 · 증거 없으면 None · 조회 실패 시 fail-soft · 멀티 datasource 비활성 시 skip |
| E thin | 계약 길이 분석이 비-thin · summary 만 채워지면 thin · 상투구는 미충족 · Table 은 role 도 충족 항목 · 빈 분석/파싱 불가 보수 판정 |

**기존 테스트 갱신**
- `test_graph_category_recursive_refine.py` — `_mk_analysis` fixture 의 rel/usage 를 한 글자
  더미에서 실제 계약 문장으로 교체(항목 충족도 판정과 정합), back-refine 커서를
  `(id, analysis, node_label)` 3-tuple 계약으로 갱신.
- `test_worker_parallelism.py` — `PERF_KEYS` 에 증거 수집 knob 4종 추가.

## 3. 실행

```
COMPOSE_PROJECT_NAME=repo make test
```
(worktree 에서는 `repo/` 의 `.env*` 복사 + `COMPOSE_PROJECT_NAME=repo` 가 필요하다 — compose
프로젝트명이 디렉토리명이 되면 격리 네트워크라 DNS 의존 테스트가 가짜 실패한다.)

## 4. 라이브 검증 (배포 후)

1. **마이그레이션 적용 확인** — `alembic_version` 이 `0050_metadata_stats` 인지 직접 확인한다
   (배포 자동 마이그레이션이 stale agent 이미지로 신규 리비전을 놓친 전례가 있다).
2. **수집 동작** — insight-worker 로그에서 `증거 수집 완료 … stage=0` 확인. Stage 0 이므로 이
   시점에 운영 DB 사용자 테이블 read 는 0이어야 한다.
3. **승격** — 24시간 후 같은 테이블이 `stage=1` 로 올라가는지 `metadata_table_stats` 로 확인.
4. **접지 효과(전/후 대조)** — 동일 노드 N개의 분석문을 증거 주입 전/후로 비교해 summary 에
   실측 수치가 등장하는지, caveats 가 실질 위험을 담는지 대조한다.
5. **PB-0008** — 그래프 뷰에서 Table 노드 AI 분석을 실행해 분석문에 수치 근거가 나타나는지
   Windows 브라우저로 확인.

## 5. 알려진 환경성 실패 (회귀 아님)

- `test_share_redaction_invariant.py` 는 main baseline 에서도 동일하게 실패한다(정식 경로는
  `make test` 컨테이너). 본 cycle 의 변경과 무관하다.
