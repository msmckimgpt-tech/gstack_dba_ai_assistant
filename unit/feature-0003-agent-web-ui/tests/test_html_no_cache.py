"""TASK-0256d: HTML 엔트리포인트(index/admin/share)는 Cache-Control: no-cache 로 서빙해야

정적 자산은 `?v=` 캐시버스터로 영구 캐시해도 되지만, 그 버전을 참조하는 HTML 자체가
브라우저에 휴리스틱 캐시되면 옛 `?v=` 를 계속 참조해 캐시버스터가 무력화된다. 본 테스트는
세 HTML route 가 no-cache 헤더를 전달하는지 FileResponse 를 가로채 검증한다(DB·파일 불요).

`make test`(agent 이미지, --no-deps)에서 DB 없이 monkeypatch 로 실행된다.

feature-0012 P5b Final: index/admin_index/share_page 는 routers/static_pages.py 로 추출됨.
핸들러는 `app.FileResponse` 를 호출하므로 `monkeypatch.setattr(app, "FileResponse", ...)`
가로채기 계약은 그대로 유효(호출 위치만 routers.static_pages 로 전환).
"""
from __future__ import annotations

import app  # noqa: E402
from routers import static_pages  # noqa: E402


def test_html_routes_set_no_cache(monkeypatch):
    captured = []

    class _FakeFileResponse:
        def __init__(self, path, headers=None, **_kw):
            captured.append((str(path), headers))
            self.headers = headers or {}

    monkeypatch.setattr(app, "FileResponse", _FakeFileResponse)

    static_pages.index()
    static_pages.admin_index()
    static_pages.share_page("any-token")

    assert len(captured) == 3
    # 세 route 모두 no-cache 를 명시적으로 전달한다.
    for _path, headers in captured:
        assert headers == {"Cache-Control": "no-cache"}, headers
    # 각 route 가 올바른 HTML 파일을 서빙한다.
    served = [p.replace("\\", "/").rsplit("/", 1)[-1] for p, _ in captured]
    assert served == ["index.html", "admin.html", "share.html"], served
