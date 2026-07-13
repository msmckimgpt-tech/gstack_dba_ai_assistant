# Scene-Spec 계약 — 엔진-중립 렌더 경계 (feature-0016 §78 Phase B)

`graph-renderer-pixi.js`(SceneAdapter)와 `graph-core.js`(모델·배치) 사이의 **엔진-중립
계약**. 이 경계 덕분에 렌더러 교체(G6→PixiJS)가 배치·모델·상호작용 로직을 건드리지 않는다.

## 원칙 — scene-spec = `_metaG6Build()` 출력 형태

`_metaG6Build()` 가 이미 반환하는 `{ combos, nodes, edges }` 구조가 곧 scene-spec 이다.
G6 v5 의 data-shape 이 충분히 엔진-중립이라(좌표·스타일·상태 평면), 어댑터가 이 형태를
**그대로 소비**한다. 따라서 B-late 배선은 다음 치환만으로 끝난다:

```
G6:    graph.setData(_metaG6Build()); await graph.draw();
Pixi:  adapter.setScene(_metaG6Build());   // draw 는 setScene 내부
```

`graph-core.js` 의 emission 절(`nodes.push/edges.push/combos.push`)은 **무변경**이 목표다.

## 노드 (`nodes[]`)

```
{ id: string,
  type: "rect" | "circle",
  combo?: string,               // 소속 스키마/그룹 combo id (containment)
  states?: string[],            // ["selected"|"analyzed"|"running"|"busy"|"dimmed"|"match"]
  data?: { label, kind, fqn, role, ... },   // 도메인 (렌더 무관, 이벤트 payload 용)
  style: {
    x, y,                       // 모델 좌표 (rect=중심, circle=중심)
    size: number | [w, h],      // circle=지름(number), rect=[폭,높이]
    radius?: number,            // rect 모서리 둥글기
    fill, stroke, lineWidth,
    fillOpacity?, opacity?,     // dim bake (ADR-028) — base 에 확정된 값
    zIndex,                     // _METZ 의미 계층 (소수 오프셋 허용)
    labelText?, labelPlacement?("center"|"right"|"top"),
    labelFill?, labelFontSize?, labelFontWeight?, labelMaxWidth?, labelOffsetX?,
    cursor?
  } }
```

## 엣지 (`edges[]`)

```
{ id, source, target,
  data?: { label, status, type },
  style: {
    stroke, lineWidth,
    lineDash?: [on, off],       // 생략=실선 (false 금지 — 계약상 키 자체를 안 넣음)
    startArrow?: bool, endArrow?: bool,
    strokeOpacity?, zIndex,
    labelText?, labelFontSize?, labelFill?, labelBackground?, ...
  } }
```

## Combo (`combos[]`)

```
{ id, type:"rect", data:{label,kind},
  style: { labelText, radius, padding:[t,r,b,l], labelPlacement:"top",
           fill, fillOpacity, stroke, lineWidth, lineDash, zIndex } }
```

- combo 는 **명시 위치가 없다** — 어댑터가 `combo===id` 인 자식 노드들의 union bounds +
  padding 으로 카드 bbox 를 계산한다(G6 combo auto-fit 대체). 이 계약 덕분에 G6 의
  auto-fit 제약(ADR-029/030 이 감수하던 combo-safe 컬링 제한)이 어댑터에서 **소멸**한다.

## 어댑터 인터페이스 (G6.Graph 호환 — 배선 최소화)

`_metaGraph.graph` 가 부르는 G6 메서드를 미러한다:

- 데이터: `setScene(built)`(=setData+draw), `draw()`
- 카메라: `getZoom`, `zoomTo(z,opts)`, `zoomBy`, `translateBy([dx,dy])`, `fitView`,
  `focusElement(id,opts)`, `getCanvasByViewport([mx,my])`(model→screen),
  `getViewportByCanvas([sx,sy])`(screen→model), `getElementRenderBounds(id)`,
  `getElementPosition(id)`, `getSize()`, `resize(w,h)`
- 상태: `setElementState`, `setElementZIndex`
- 이벤트: `on(name,fn)`/`off` — G6 이벤트명 합성(`node:click`·`node:dblclick`·`combo:click`·
  `canvas:click`·`node:contextmenu`·`combo:contextmenu`·`edge:contextmenu`·`canvas:contextmenu`·
  `node:dragstart|drag|dragend`·`combo:*`·`afterdraw`·`aftertransform`)
- 플러그인: `getPluginInstance("minimap")`
- 정리: `destroy()`

> **주의(G6 좌표계 vs Pixi)**: G6 `getCanvasByViewport` 는 model→viewport(screen),
> `getViewportByCanvas` 는 viewport→model 이다(이름과 방향이 헷갈림). 어댑터는 G6 의미와
> **동일**하게 구현해 graph-core 호출부를 안 바꾼다.

## v1 범위 / 후속

- v1(B-early): 노드 2종·엣지 6종·combo bbox·라벨·상태(selected/analyzed/running/match/dim)·
  카메라 전 API·이벤트 합성(spatial hit-test)·팬/줌 성능 경로.
- 후속(B-late 이후 §): 미니맵(RenderTexture)·드래그 자유배치 persistence·scene diff 오브젝트
  풀(현재 full rebuild)·BitmapText 한글 atlas(대형 라벨 최적화).
