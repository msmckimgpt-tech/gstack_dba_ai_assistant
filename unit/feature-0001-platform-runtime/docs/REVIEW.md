---
doc_type: REVIEW
feature_id: feature-0001-platform-runtime
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260515-0003
- Date: 2026-05-15
- Decision: `browser-up` / `insight-up` 도 `web` 타깃과 동일하게 `dc-build` 가드 + `up --no-build` 패턴으로 전환한다.
- Reason: `make browser-up` 실행 중 compose/buildx provenance metadata file race 가 재현됐다. 이미지 빌드는 성공했지만 compose 후처리에서 임시 metadata 파일을 찾지 못해 exit 2로 종료했다. 이미 `Makefile`에는 이 환경 결함을 흡수하는 `dc-build` 가드가 있으므로 같은 원인을 같은 방식으로 처리하는 것이 맞다.
- Risk: `up -d --no-build` 는 직전 `dc-build` 성공을 전제로 한다. `dc-build`가 실제 빌드 오류와 metadata race를 구분하므로, 빌드 실패를 숨기지 않는다.

## REV-20260326-0001
- Date: 2026-03-26
- Decision: 운영 자산만 버전관리 대상으로 두고 데이터/로그는 외부 산출물로 분리
- Reason: 기능 단위 추적성과 런타임 안전성 확보
- Risk: 엄격한 운영 검증 시나리오가 아직 없다
