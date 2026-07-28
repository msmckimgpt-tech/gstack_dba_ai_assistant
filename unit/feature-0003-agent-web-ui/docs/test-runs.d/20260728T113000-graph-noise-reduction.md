---
run_at: 2026-07-28T11:42:00+09:00
session: ai/claude/feature-0003-graph-noise-reduction
scope: feature-0003-agent-web-ui (그래프 뷰 상세 패널 설명문 → hover 툴팁 · 관리 콘솔 커밋 바 조건부 노출)
verdict: PASS
---

# Run — graph-noise-reduction (AC-GNR-1~6)

- Date: 2026-07-28
- Environment: `Windows-browser` (`bin/win-browser.py`, 실 Windows Chrome CDP 구동) + `CLI` (헤드리스 단위)
- Runner: AI (claude)
- Bridge: `relay` @ `http://172.26.144.1:9223` — `doctor {"ok": true, "cdp_version": "Chrome/150.0.7871.115"}`
- 대상 URL: `https://localhost/admin` → 지식베이스 > 그래프 뷰 (데이터소스 `mysql-web-global-qa`)
- 자산 스테이징: 미머지 브랜치라 `docker cp` 로 `repo-web-a-1`/`repo-web-b-1` 의 `/app/web/static` 에 변경 4파일 주입 후
  전 자산의 cache-buster 를 `?v=qa113855` 로 일괄 재기입(ES module import specifier 불일치로 인한 **이중 인스턴스화 회피**).

## 1. 헤드리스 단위 (CLI)

| 항목 | 결과 |
|---|---|
| `node --check` (ESM) `graph-ctxmenu.js` | OK |
| `tests/headless/test_detail_dbgroups.js` (⑰ 블록 +14 assert 포함) | **78 PASS / 0 FAIL** |
| `tests/headless/test_graph_reveal.js` | 17 PASS / 0 FAIL |

⑰ 블록이 단정하는 것: `_metaSecHelp` 마커 생성·`&<>"` 이스케이프·키보드 접근(`tabindex`+`aria-label`)·빈 tip 안전,
본문에서 제거된 문단 **7종**, 툴팁으로 보존된 정보 **4종**, 렌더에 남는 `admin-meta-detail-note` **1건(절단 경고)**.

> **pre-existing 실패(본 cycle 무관)**: `test_detail_colsel.js` · `test_graph_colnav.js` 는 ITEM-09 ES-module
> 리팩터 이후 `vm` 전체 eval 이 불가해 **main(baseline) 에서도 동일하게 실패**한다(`_metaGraphRenderDetail 미로딩`).
> baseline 대조로 확인함. 본 cycle 은 `test_detail_colsel.js` ⑤ 의 단정만 새 계약에 맞게 갱신했다.

## 2. 라이브 실측 (Windows-browser, DOM eval)

노드 상세 — `mysql-web-global-qa` > `masangsoft.masangsoft_documents` (사용자 스크린샷과 동일 대상):

```
h4:    ["컬럼 (2) ⓘ", "사용하는 함수·프로시저 (10) · 읽기 3 · 쓰기 7 ⓘ", "AI 능동 분석"]
notes: 0                       # p.admin-meta-detail-note — 사용자 지목 2개 문단 소멸
tips:  ["컬럼 클릭 = 상세로 전환 + 그래프에서 강조. 관계가 있는 컬럼(🔗)은 캐럿(▸)으로 …",
        "이 테이블을 사용하는 함수·프로시저를 읽기/쓰기로 나눠 표시하며 목록을 잘라내지 않습니다. …"]
aiBox: "분석 결과 없음"
aiBtnTitle: "이 노드에서 시작해 관련 노드를 AI가 재귀적으로 분석합니다(백그라운드). hover 로 분석 지침 입력."
panelTextLen: 512              # 변경 전 852 → 40% 감소
helpCss: {fs:"11px", cursor:"help", opacity:"0.55", color:"rgb(128,125,114)"}
```

| AC | 확인 지점 | 결과 |
|---|---|---|
| GNR-1 | 컬럼·관계·함수/프로시저 h4 의 ⓘ + `title` 전문 | PASS |
| GNR-2 | 관계 상세 `참조함 0 · 참조받음 0 · 연관 용어 0 ⓘ` / 클러스터 상세 `테이블 109개 ⓘ` | PASS |
| GNR-3 | empty-state `노드를 클릭하면 상세가 여기에 표시됩니다.` (1줄) | PASS |
| GNR-4 | AI box 상태 1줄 + 버튼 `title` 이관 | PASS |
| GNR-5 | 절단 경고 — `truncated=false` 미노출 / `true` 1줄(헤드리스 단정) | PASS |
| GNR-6 | 커밋 바 `display:none`(0건) ↔ `flex`+`has-pending`(1건 pending) 왕복 | PASS |

컬럼 노드 상세(`…documents.user_id`) → `h4: ["관계 ⓘ", "AI 능동 분석"]`, `notes: 0`,
tip `행 hover = 관계 의미, 클릭 = 대상 추적(상세 + 카메라 이동).`

**커밋 바 인터랙션 왕복** (§16.6 인터랙션 결과 검증):

```
초기(0건):   display=none   class="admin-commit-bar"        summary="변경 없음"
권한 select 변경 → change 이벤트
변경 후(1건): display=flex   class="admin-commit-bar has-pending"
             commitBarCount="1건 pending"  detail="(계정 1)"  applyBtn.disabled=false
             summary="1건 pending"
```

변경은 클라이언트 pending 상태만 만들고 **적용하지 않았다** — 이후 페이지 리로드로 폐기(서버 무영향).
(`취소` 버튼은 `window.confirm` 을 띄우며 자동화 드라이버가 dialog 를 auto-dismiss 해 pending 이 유지된다 — **pre-existing 동작**, 본 변경과 무관.)

## 3. Evidence (스크린샷)

- `artifacts/pb0008/feature-0003-graph-noise-reduction/pb0008-graph-noise-after2-20260728.png`
  — 그래프 뷰 + `masangsoft_documents` 상세. 사용자 스크린샷에서 초록 표시된 두 설명 문단 자리에 목록이 바로 이어지고,
    하단 커밋 바가 사라져 캔버스가 화면 바닥까지 확장됨. 좌하단 `변경 없음` 요약은 유지.
- `artifacts/pb0008/feature-0003-graph-noise-reduction/pb0008-commitbar-pending-20260728.png`
  — 같은 그래프 뷰에서 pending 1건일 때 커밋 바가 **다시 나타난** 상태(`1건 pending (계정 1)` + 활성 `취소`/`모두 적용`).
    "바가 사라진 것" 이 아니라 "조건부" 임을 보이는 대조 증적.

## 4. 한계 · 후속

- **native `title` 툴팁은 스크린샷에 캡처되지 않는다**(브라우저 OS 레이어 렌더). 툴팁 *내용*은 라이브 DOM eval 로 전문
  실측했고, 레이아웃·간격 등 **픽셀 클래스** 변경은 위 스크린샷으로 확인했다(§16.6 evidence 변경-클래스 분기 준수).
- 검증 중 **다른 세션의 롤링 배포 3회**(`ebedc256` → `0062acb3` → `fe6d3700`)로 스테이징이 두 번 덮였다. 그때마다
  worktree 를 최신 main 으로 rebase 하고 재주입·재측정했으며, 위 판독은 전부 패치가 서빙되던 시점의 것이다.
  검증 종료 시점에 마지막 배포가 스테이징을 자동 회수해 **라이브에는 잔재가 없다**(`curl` 로 baked 자산 복귀 확인).
- 배포(`deploy_scope: included`) 후 main 기반 재확인은 cycle-final 이후 사후 확인 항목으로 남긴다.
