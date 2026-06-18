/*
 * release-notes.js — 릴리즈 노트 렌더러 (공유)
 *
 * 작업 화면(사용자 프로필 > 릴리즈 노트 탭)과 관리 콘솔(릴리즈 노트 카테고리)에서
 * 동일하게 사용한다. 콘텐츠는 release-notes-data.js 의 window.RELEASE_NOTES 를 읽는다.
 *
 * 노출 API:
 *   window.ReleaseNotes.render(container)  — container 안에 릴리즈 노트 UI 를 렌더.
 *
 * 특징:
 *   - 일자별 그룹을 접고 펼칠 수 있다(기본: 가장 최근 1개만 펼침).
 *   - 상단 필터 칩으로 영역(작업 화면 / 관리 콘솔 / 공통)을 골라 탐색할 수 있다.
 *   - 모든 텍스트는 textContent 로 주입한다(콘텐츠가 정적이지만 안전하게 처리).
 */
(function () {
  "use strict";

  var AREA_LABEL = { work: "작업 화면", admin: "관리 콘솔", common: "공통" };
  var TYPE_META = {
    new: { label: "새 기능", cls: "is-new" },
    improved: { label: "개선", cls: "is-improved" },
    fixed: { label: "수정", cls: "is-fixed" },
  };

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  // "2026-06-18" → "2026년 6월 18일". 패턴 불일치(예: "이전")는 그대로 반환.
  function formatDate(raw) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(raw || ""));
    if (!m) return String(raw || "");
    return m[1] + "년 " + Number(m[2]) + "월 " + Number(m[3]) + "일";
  }

  function headingFor(release) {
    return release.label || formatDate(release.date);
  }

  function renderItem(item) {
    var row = el("div", "rn-item");
    var meta = TYPE_META[item.type] || TYPE_META.improved;
    var badges = el("div", "rn-item-badges");
    badges.appendChild(el("span", "rn-badge rn-badge-type " + meta.cls, meta.label));
    if (item.area && AREA_LABEL[item.area]) {
      badges.appendChild(el("span", "rn-badge rn-badge-area rn-area-" + item.area, AREA_LABEL[item.area]));
    }
    row.appendChild(badges);
    var body = el("div", "rn-item-body");
    body.appendChild(el("div", "rn-item-title", item.title || ""));
    if (item.detail) body.appendChild(el("div", "rn-item-detail", item.detail));
    row.appendChild(body);
    return row;
  }

  // 단일 일자 그룹(접기 가능). expanded = 초기 펼침 여부.
  function renderGroup(release, filter, expanded) {
    var items = (release.items || []).filter(function (it) {
      return filter === "all" || it.area === filter;
    });
    if (!items.length) return null; // 필터 결과 0건이면 그룹 숨김.

    var group = el("section", "rn-group");

    var head = el("button", "rn-group-head");
    head.type = "button";
    head.setAttribute("aria-expanded", String(expanded));

    head.appendChild(el("span", "rn-chevron", "▸"));
    var headText = el("div", "rn-group-headtext");
    headText.appendChild(el("span", "rn-group-date", headingFor(release)));
    if (release.summary) headText.appendChild(el("span", "rn-group-summary", release.summary));
    head.appendChild(headText);
    head.appendChild(el("span", "rn-group-count", items.length + "건"));

    var bodyWrap = el("div", "rn-group-body");
    if (!expanded) bodyWrap.hidden = true;
    items.forEach(function (it) {
      bodyWrap.appendChild(renderItem(it));
    });

    head.addEventListener("click", function () {
      var open = head.getAttribute("aria-expanded") === "true";
      head.setAttribute("aria-expanded", String(!open));
      bodyWrap.hidden = open;
    });

    group.appendChild(head);
    group.appendChild(bodyWrap);
    return group;
  }

  // opts.areas: 표시할 영역 화이트리스트(기본 전체). 작업 화면은 ["work","common"] 로
  // 호출해 '관리 콘솔' 영역 릴리즈 노트를 숨긴다(관리 콘솔은 기본=전체).
  function render(container, opts) {
    if (!container) return;
    opts = opts || {};
    var allowed = (Array.isArray(opts.areas) && opts.areas.length) ? opts.areas : ["work", "admin", "common"];
    var data = window.RELEASE_NOTES;
    container.innerHTML = "";

    var root = el("div", "rn-root");
    root.appendChild(el("p", "rn-intro", "새로운 기능과 개선 사항을 일자별로 정리했습니다."));

    // 표면별 영역 제한: items 를 allowed area 로 선필터하고 빈 일자 그룹은 제거한다.
    // 이렇게 하면 '전체' 필터·카운트·그룹 가시성·필터 칩이 모두 allowed 영역만 반영한다.
    var rawReleases = (data && Array.isArray(data.releases)) ? data.releases : [];
    var releases = rawReleases
      .map(function (r) {
        var copy = {};
        for (var k in r) { if (Object.prototype.hasOwnProperty.call(r, k)) copy[k] = r[k]; }
        copy.items = (r.items || []).filter(function (it) { return allowed.indexOf(it.area) !== -1; });
        return copy;
      })
      .filter(function (r) { return r.items.length > 0; });
    if (!releases.length) {
      root.appendChild(el("div", "rn-empty", "표시할 릴리즈 노트가 없습니다."));
      container.appendChild(root);
      return;
    }

    var listWrap = el("div", "rn-list");

    var state = { filter: "all" };

    // 상단 탐색 바: 영역 필터 칩(allowed 영역만) + 모두 펼치기/접기.
    var toolbar = el("div", "rn-toolbar");
    var chips = el("div", "rn-filter-chips");
    var AREA_ORDER = ["work", "admin", "common"];
    var FILTERS = [{ key: "all", label: "전체" }].concat(
      AREA_ORDER.filter(function (a) { return allowed.indexOf(a) !== -1; })
        .map(function (a) { return { key: a, label: AREA_LABEL[a] }; })
    );
    var chipEls = {};
    FILTERS.forEach(function (f) {
      var chip = el("button", "rn-chip" + (f.key === state.filter ? " is-active" : ""), f.label);
      chip.type = "button";
      chip.addEventListener("click", function () {
        if (state.filter === f.key) return;
        state.filter = f.key;
        Object.keys(chipEls).forEach(function (k) {
          chipEls[k].classList.toggle("is-active", k === f.key);
        });
        buildList();
      });
      chipEls[f.key] = chip;
      chips.appendChild(chip);
    });
    toolbar.appendChild(chips);

    var expandToggle = el("button", "rn-expand-all", "모두 펼치기");
    expandToggle.type = "button";
    var allExpanded = false;
    expandToggle.addEventListener("click", function () {
      allExpanded = !allExpanded;
      expandToggle.textContent = allExpanded ? "모두 접기" : "모두 펼치기";
      listWrap.querySelectorAll(".rn-group-head").forEach(function (h) {
        h.setAttribute("aria-expanded", String(allExpanded));
        var b = h.nextElementSibling;
        if (b) b.hidden = !allExpanded;
      });
    });
    toolbar.appendChild(expandToggle);
    root.appendChild(toolbar);

    function buildList() {
      listWrap.innerHTML = "";
      var rendered = 0;
      releases.forEach(function (rel, idx) {
        // 필터 미적용(전체) 기본 펼침은 최신 1개. 모두 펼치기가 켜져 있으면 전부 펼침.
        var expanded = allExpanded || rendered === 0;
        var g = renderGroup(rel, state.filter, expanded);
        if (g) {
          listWrap.appendChild(g);
          rendered += 1;
        }
      });
      if (!rendered) {
        listWrap.appendChild(el("div", "rn-empty", "해당 영역의 업데이트가 없습니다."));
      }
    }

    buildList();
    root.appendChild(listWrap);
    container.appendChild(root);
  }

  window.ReleaseNotes = { render: render };
})();
