---
run_at: 2026-07-28T12:45:00+09:00
session: ai/claude/feature-0014-asset-stamp-cache-integrity
scope: feature-0014 (배포 캐시 무결성) — cross-cut: feature-0002 injector · feature-0003 web/static_cache · feature-0006 Caddyfile
verdict: PASS (PRE-COMMIT) / POST-DEPLOY 라이브 결정론 검증 예정
---

# Run — asset-stamp-cache-integrity

- Date: 2026-07-28
- Environment: `CLI` (pytest·ruff·caddy validate·컨테이너 실측)
- Runner: AI (claude)
- Bridge: n/a (PRE-COMMIT 단계)

## 1. 단위·통합

| 스위트 | 결과 |
|---|---|
| `feature-0003/tests/test_static_cache_integrity.py` + `feature-0002/tests/test_inject_asset_stamp_sidecar.py` | **32 passed / 0 failed / 0 skipped** |
| 전체 회귀 (`feature-0002` + `feature-0003` + `feature-0023` tests) | **2719 passed / 2 skipped / 0 failed** (rc=0) |
| `ruff check unit/ shared/` | All checks passed |
| `caddy validate --adapter caddyfile` | `adapted config to JSON` (잔여 에러 = 검증 샌드박스 cert 부재뿐) |

핵심 단정 — **문구가 아니라 불변식**을 본다:
- 요청 `?v=` == 빌드 스탬프 → `immutable`
- 불일치(구 스탬프·`dev`·임의값) → `no-store` + `X-Asset-Stamp: mismatch`
- `?v=` 없음 → 헤더 미설정(기존 ETag/304 유지)
- vendor pin → `immutable` (별개 버전 축)
- 사이드카 부재 → 미설정 (fail-safe)
- 엣지 `Caddyfile` 에 `Cache-Control` 강제 규칙이 **없다** (있으면 upstream 판정이 덮여 불변식 무력화 → FAIL)

## 2. 통합 테스트가 적발한 실결함 (격리 테스트는 통과했던 것)

`test_end_to_end_build_then_serve` 는 **실 injector → 실 static 트리 사본 → 실 StaticFiles + 래퍼**를
태운다. 여기서 초판의 접합부 결함이 드러났다:

> Starlette 최신 `Mount` 는 하위 앱에 `scope["path"]` 를 **자르지 않고** 넘긴다
> (`/static/vendor/g6.min.js`). prefix 기반 vendor 판정(`path.startswith("/vendor/")`)이 빗나가
> **라이브러리 pin 이 상시 `no-store`** 가 될 뻔했다(vendor 캐시 전면 상실).

세그먼트 검사로 교체하고 두 mount 규약(`/vendor/…`·`/static/vendor/…`)을 파라미터로 고정.
격리 단위테스트만 있었으면 통과했을 결함이라, 접합부 테스트를 남긴 판단이 실증됐다.

## 3. 이미지 경로 정합 (배포 전 사전 확인)

| 확인 | 결과 |
|---|---|
| Dockerfile injector root | `--root /app/web/static` |
| 앱 `STATIC_DIR` | `/app/web/static` (컨테이너 실측 — 동일) |
| `static_cache.py` 동봉 | `COPY unit/feature-0003-agent-web-ui/src /app/web` |
| `/app/web` 이 런타임 sys.path 에 존재 | **True** (`perf_metrics` 와 동일 기전, 컨테이너 직접 확인) |
| `asset_stamp_verify` 와의 간섭 | 없음 (`*.html`/`*.js` 만 grep — 사이드카 비대상) |

## 4. Windows-browser 시각검증 (§15.4.1)

본 cycle 의 변경은 **HTTP 응답 헤더와 빌드 산출물**이며 DOM·CSS·레이아웃 무변경이다
(`.html`/`.css`/프론트 `.js` 파일 변경 0건 — `git diff --stat` 으로 확인 가능).
따라서 PB-0008 로 확인할 픽셀이 없다. 대신 POST-DEPLOY 에서 **결정론적 헤더 프로브**로 검증한다:

```
curl -skI "https://<host>/static/admin.js?v=<현 스탬프>"   → cache-control: public, max-age=31536000, immutable
curl -skI "https://<host>/static/admin.js?v=<옛 스탬프>"   → cache-control: no-store  + x-asset-stamp: mismatch
curl -skI "https://<host>/static/vendor/g6.min.js?v=5.1.1" → cache-control: public, max-age=31536000, immutable
curl -skI "https://<host>/static/admin.js"                 → cache-control 없음 (ETag/304)
```

부수로, 직전 cycle(graph-noise-reduction)의 그래프 뷰 변경이 **캐시를 비우지 않은 브라우저에서도**
정상 렌더되는지 PB-0008 로 함께 확인한다(본 수정의 사용자 체감 효과).

## 5. 한계

- 롤링 창 자체는 남는다 — 창 안에서 버전이 섞인 페이지를 한 번 볼 수 있다(종전과 동일).
  달라진 것은 그 상태가 **캐시에 굳지 않는다**는 점. "창 제거" 는 content-addressed 경로가 후속 과제.
- 이미 오염된 브라우저는 자동 복구되지 않는다(해당 URL 재요청 시점까지). 스탬프가 바뀌면 새 URL 이라 실질 영향은 소멸.
