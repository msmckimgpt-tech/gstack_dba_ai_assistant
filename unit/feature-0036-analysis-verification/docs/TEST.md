---
doc_type: TEST
feature_id: feature-0036-analysis-verification
status: active
edit_policy: rewrite
source_of_truth: true
---

# Test

## 1. Test Contract

**이 파일의 절반은 하나의 명제를 지킨다: 판정 실패는 "검증됨"이 아니다.**

1. **정직성** — LLM 실패·계약 위반·근거 없음·증거 부재·저장 실패 → 전부 행 없음.
2. **대상 정확성** — 분석문+증거 둘 다, `error IS NULL`, 같은 분석문 버전은 건너뜀.
3. **비용** — pass 상한, 인자 우회 불가, 항목별 예산 재확인, 예산 모듈 부재 시 중단.
4. **격리** — savepoint, 예외 미전파, 자체 연결.

## 2. 자동 테스트 — `tests/test_analysis_verify.py` (38건)

| 축 | 케이스 |
|---|---|
| A 정직성 | LLM None · 계약 위반 verdict 6종 · **reason 없음 3종** · 증거 부재 · 파싱 불가 분석문 · 저장 실패 → 전부 미기록. 대소문자·공백은 정규화 수용. DB CHECK 제약 ↔ 모듈 상수 일치 |
| B 대상 | 분석문+증거 JOIN · **이전 판정 해시 조회**(NOT EXISTS 아님) · 같은 해시 건너뜀 · **다른 해시 재판정** · `error IS NULL` 이중 · 깊은 증거 우선 · limit 0 단락 |
| C 비용 | pass 상한 · **인자로 상한 우회 불가** · 예산 차단 · **항목별 재확인** · 예산 모듈 부재 시 중단 · 스위치 off · cap 0 |
| D 격리 | savepoint 사용 · 예외 흡수 · evidence 조회 실패 · **자체 연결 개설** · insight 가 인자 없이 호출 |
| E 저장 | 3 verdict 기록 · 근거 문장 보존 · **노드당 1행 유지(DELETE 선행)** · 해시 변화 감지 |
| F 프롬프트 | rubber-stamp 금지 · 날조 금지 · 표본임을 명시 |

## 3. 실행

```
COMPOSE_PROJECT_NAME=repo make test
```

## 4. 라이브 검증 (배포 후)

1. `alembic_version` = `0052_analysis_verdicts` + GRANT 확인.
2. insight 로그에서 `분석 검증 pass — 판정 N (뒷받침 x · 모순 y · 판정불가 z)` 확인.
3. `node_analysis_verdicts` 표본 판독 — 특히 `contradicted` 의 `reason` 이 **구체적 숫자를
   지목**하는지(그러지 않으면 판정자가 형식만 채운 것이다).
4. 판정 대상이 현재 7건 수준이므로(증거 커버리지), 플래너(feature-0035)가 커버리지를 채운 뒤
   재측정한다.
