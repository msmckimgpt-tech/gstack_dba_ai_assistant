"""정적 자산 캐시 무결성 (feature-0014-zero-downtime-deploy, asset-stamp-cache-integrity 2026-07-28).

# 문제 — 롤링 배포 창의 캐시 오염 (라이브 실측 2026-07-28)

`web-a`/`web-b` 2-replica 롤링 배포에서 정적 자산은 **각 replica 의 로컬 파일시스템**에서
**경로만으로** 서빙된다(쿼리스트링은 파일 조회에 무관). 그런데 엣지(Caddy)는 `?v=` 의
**존재**만 보고 `Cache-Control: public, max-age=31536000, immutable` 을 부여했다.

그 결과 롤아웃 창에서:

    1. 클라이언트가 NEW replica 에서 HTML 을 받는다 → 참조가 전부 `?v=<NEW>`.
    2. sticky(`lb_policy cookie weblb`)로 고정된 replica 가 **바로 그 순간 recreate** 되면
       LB 가 클라이언트를 OLD replica 로 재배정한다.
    3. OLD replica 가 `?v=<NEW>` 요청에 **OLD 바이트**로 200 응답한다(경로가 같으므로).
    4. 그 응답이 `immutable` 로 **1년간 고착**된다 — 스탬프를 아무리 바꿔도 그 URL 은
       영원히 낡은 내용을 돌려준다.

ES module 진입점이 이렇게 굳으면 import 체인 전체가 구 스탬프로 끌려가, 서버는 신 코드를
서빙하는데 브라우저만 구버전을 렌더한다(실측: 그래프 뷰 변경이 배포 후에도 미반영).
`location.reload(true)` 는 최신 Chrome 에서 no-op 이라 사용자가 스스로 벗어나기 어렵다.

# 해소 — 불변식

    응답이 `immutable` 로 표시되려면, 응답한 replica 의 **빌드 스탬프 == 요청 URL 의 `?v=`**
    여야 한다. 불일치 응답은 `no-store` 로 표시한다.

이러면 오염이 **구조적으로 불가능**해진다 — 버전이 어긋난 응답은 애초에 캐시에 들어가지
못하므로, 롤아웃 창은 "잠깐 재검증이 늘어나는 구간"으로 격하되고 롤아웃 종료 후 자연 수렴한다.
sticky LB 는 이 창을 *좁히는* 최적화로 남고(여전히 유효), 본 모듈이 *영구 피해를 차단*한다.

빌드 스탬프의 출처는 `scripts/inject_asset_stamp.py` 가 남기는 `<static>/.asset-stamp`
사이드카다(주입한 content-hash 와 동일 값).

# 정책 표

| 요청                                   | Cache-Control                                  |
|----------------------------------------|------------------------------------------------|
| `?v=` 없음                             | (미설정 — 기존 ETag/304 조건부 GET 유지)        |
| `?v=` == 내 빌드 스탬프                | `public, max-age=31536000, immutable`          |
| `?v=` != 내 빌드 스탬프                | `no-store` + `X-Asset-Stamp: mismatch`         |
| `/static/vendor/**` 의 `?v=`           | `public, max-age=31536000, immutable`          |
| 스탬프 사이드카 부재(dev/미주입 빌드)  | (미설정 — fail-safe: 캐싱을 잃을 뿐 오염 없음)  |

vendor 예외: `vendor/g6.min.js?v=5.1.1` 류는 **라이브러리 버전 pin**(사람이 업그레이드 때
bump)이지 빌드 스탬프가 아니다 — 빌드 해시와 비교하면 항상 불일치가 되어 상시 `no-store` 로
캐시를 통째로 잃는다. 별개 버전 축이므로 종전 동작(immutable)을 유지한다. 잔여 위험은
"라이브러리 pin bump 와 롤아웃이 겹치는 순간" 뿐이며 빈도가 극히 낮다(§16.3 정직 표기).

# 설계 제약

- **순수 ASGI 래퍼** — `BaseHTTPMiddleware` 를 쓰지 않는다(스트리밍 응답 간섭 회피,
  `perf_metrics.PerfTimingMiddleware` 와 동일 관례).
- **fail-open** — 헤더 결정 중 예외는 삼키고 원본 응답을 그대로 통과시킨다. 캐시 헤더는
  최적화이지 correctness gate 가 아니다.
- 엣지(Caddy)는 더 이상 `Cache-Control` 을 강제하지 않는다 — upstream 헤더가 권위.
  (엣지가 덮어쓰면 본 불변식이 무력화되므로 `Caddyfile` 의 `header @static_versioned` 제거가
  본 변경의 짝이다.)
"""
from __future__ import annotations

import os
from typing import Any, Callable, Iterable
from urllib.parse import parse_qs

STAMP_SIDECAR = ".asset-stamp"

IMMUTABLE = b"public, max-age=31536000, immutable"
NO_STORE = b"no-store"

# 캐시 헤더를 붙일 상태코드. 리다이렉트·에러 응답에는 관여하지 않는다(304 는 조건부 GET 의
# 성공 경로라 포함 — 재검증 결과에도 동일 정책이 실려야 클라이언트 freshness 가 갱신된다).
_CACHEABLE_STATUS = frozenset((200, 304))


def read_build_stamp(static_dir: str | os.PathLike[str]) -> str | None:
    """`<static>/.asset-stamp` 를 읽어 빌드 스탬프를 반환. 부재·읽기 실패면 None (fail-safe)."""
    try:
        with open(os.path.join(os.fspath(static_dir), STAMP_SIDECAR), encoding="utf-8") as fh:
            stamp = fh.read().strip()
    except (OSError, UnicodeDecodeError):
        return None
    return stamp or None


def _requested_stamp(query_string: bytes) -> str | None:
    """쿼리스트링에서 `v` 파라미터를 뽑는다. 없으면 None, 중복이면 첫 값."""
    if not query_string:
        return None
    try:
        values = parse_qs(query_string.decode("latin-1"), keep_blank_values=True).get("v")
    except Exception:
        return None
    if not values:
        return None
    return values[0]


def _is_vendor(path: str) -> bool:
    """vendor 자산 여부 — 경로에 `vendor/` 세그먼트가 있으면 참.

    prefix 매칭이 아니라 **세그먼트 포함** 검사인 이유: Starlette 버전에 따라 `Mount` 가
    하위 앱에 넘기는 `scope["path"]` 가 마운트 접두를 **자르기도 하고**(`/vendor/g6.min.js`)
    **전체 경로 그대로**(`/static/vendor/g6.min.js`) 넘기기도 한다(최근 버전은 후자 — `path` 는
    보존하고 `root_path` 로 구분). prefix 로 판정하면 후자에서 vendor 가 빌드 자산으로 오인돼
    라이브러리 pin(`?v=5.1.1`)이 상시 `no-store` 가 된다 — 통합 테스트가 실측으로 적발한 접합부
    결함. 두 규약 모두에서 동일하게 동작하도록 세그먼트로 본다(`/static` 마운트 하위에서
    `vendor/` 는 vendor 디렉토리 하나뿐이라 오탐 여지가 없다).
    """
    return "/vendor/" in path or path.startswith("vendor/")


def decide_cache_control(
    *,
    path: str,
    query_string: bytes,
    build_stamp: str | None,
) -> bytes | None:
    """정책 표 그대로. 반환 None = 헤더 미설정(기존 ETag/304 동작 유지)."""
    requested = _requested_stamp(query_string)
    if requested is None:
        return None
    if _is_vendor(path):
        return IMMUTABLE          # 라이브러리 pin — 빌드 스탬프와 다른 버전 축
    if not build_stamp:
        return None               # 미주입 빌드(dev) — 캐싱을 잃을 뿐 오염은 없다
    return IMMUTABLE if requested == build_stamp else NO_STORE


def _apply_headers(
    raw_headers: Iterable[tuple[bytes, bytes]],
    cache_control: bytes,
    mismatch: bool,
) -> list[tuple[bytes, bytes]]:
    out = [(k, v) for (k, v) in raw_headers if k.lower() not in (b"cache-control", b"x-asset-stamp")]
    out.append((b"cache-control", cache_control))
    if mismatch:
        # 관측용 — 롤아웃 창에서 버전 스큐가 실제로 얼마나 발생하는지 엣지 로그로 셀 수 있다.
        out.append((b"x-asset-stamp", b"mismatch"))
    return out


class StaticCacheHeadersMiddleware:
    """`/static` mount 를 감싸 정책 표대로 Cache-Control 을 부여하는 순수 ASGI 래퍼."""

    def __init__(self, app: Any, static_dir: str | os.PathLike[str], build_stamp: str | None = None) -> None:
        self.app = app
        # 시작 시 1회 로드 — 이미지 내 정적 파일이라 런타임에 바뀌지 않는다(재빌드 = 새 컨테이너).
        self.build_stamp = build_stamp if build_stamp is not None else read_build_stamp(static_dir)

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        try:
            cache_control = decide_cache_control(
                path=scope.get("path", "") or "",
                query_string=scope.get("query_string", b"") or b"",
                build_stamp=self.build_stamp,
            )
        except Exception:
            cache_control = None  # fail-open

        if cache_control is None:
            await self.app(scope, receive, send)
            return

        mismatch = cache_control == NO_STORE

        async def send_wrapper(message: dict) -> None:
            if message.get("type") == "http.response.start":
                try:
                    if message.get("status") in _CACHEABLE_STATUS:
                        message = dict(message)
                        message["headers"] = _apply_headers(
                            message.get("headers") or (), cache_control, mismatch
                        )
                except Exception:
                    pass  # fail-open — 헤더 조작 실패가 응답을 죽이지 않는다
            await send(message)

        await self.app(scope, receive, send_wrapper)
