---
doc_type: TEST
feature_id: feature-0038-frontend-modularization
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

<!-- §1, §2, §4는 rewrite (케이스 정의). §3은 append-only (실행 결과 이력). -->

## 1. Test Scope
- behavior-neutral 검증: 각 추출 cycle 이 렌더·인터랙션·서버 계약을 바꾸지 않았는지
- 제외: 기능 신규 동작 (본 initiative 는 동작 변경 0 이 계약)

> **검증 환경 분류 (AGENTS.md §15.4)** — §3 Run 의 `Environment` 는 아래 중 하나로 명시한다.
> 웹/UI(화면·상호작용) 검증은 **`Windows-browser` 만 인정**한다.
>
> | Environment | 의미 | UI 검증 인정 |
> |---|---|---|
> | `CLI` | curl / pytest / API 계약 | ✗ (서버 계약만) |
> | `WSL-headless` | WSL 내부 headless chromium | ✗ (화면 검증 불가) |
> | `Windows-browser` | 실제 Windows Chrome/Edge CDP 자동 구동 (`bin/win-browser.py`) | ✓ |

## 2. Test Cases

### TEST-20260803T170000-css-split-1 (byte-parity)
- Purpose: styles.css → css/ 7분할이 캐스케이드 관점에서 무손실임을 기계 증명
- Preconditions: 분할 완료 상태
- Steps: `cat css/{base,shell,chat,drawers,admin,profile,search-audit}.css | cmp static/styles.css(구) -`
- Expected Result: byte-identical (cmp exit 0)

### TEST-20260803T170000-css-split-2 (per-file 파싱 건전성)
- Purpose: 분할 경계가 주석/규칙 블록을 파일 간에 쪼개지 않았는지
- Steps: 파일별 `/* */` 균형 + 주석 제거 후 `{}` 균형 스캔
- Expected Result: 전 파일 균형 (원본 기존 결함 제외 — §3 Run 참조)

### TEST-20260803T170000-css-split-3 (실렌더)
- Purpose: 작업화면·관리콘솔이 분할 CSS 7장으로 동일 렌더
- Steps: PB-0008 — web-a/b 에 docker cp 주입(CSS-safe) → 실 Windows Chrome 로 / 및 /admin 진입, styleSheets 로드 수·landmark computed style·전체 스크린샷
- Expected Result: 7 sheets 로드·layout 정상·시각 회귀 0

## 3. Test Run History
<!-- append-only: 새 실행 결과를 아래에 추가한다. 기존 결과를 수정하거나 삭제하지 않는다. -->

### Run 2026-08-03-001 (Cycle 1 기준선)
- Date: 2026-08-03
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: 분할 전 실측 — styles.css 9,328줄 sha256=349ce797a2caf3…3190, admin.js 14,007줄, app.js 13,165줄. url()/@import 참조 0건 (분할 경로 안전 전제 확인).
- Pass/Fail: PASS (기준선 기록)

### Run 2026-08-03-002 (byte-parity + 파싱 건전성)
- Date: 2026-08-03
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: 7파일 순차 concat `cmp` → **byte-identical**. 파일별 주석·중괄호 균형 스캔 → 전 파일 OK. admin.css 의 `/* … --text*/ … */` 주석 조기종료 1건은 **원본 L5577 에 기존재하는 pre-existing 결함**으로, 조기종료·잔여 토큰이 같은 파일 안에 온전히 보존되어 분할로 인한 동작 변화 없음 (REVIEW REV-20260803T174500-css-split 기록).
- Pass/Fail: PASS

### Run 2026-08-03-003 (headless — CSS 소비 스위트)
- Date: 2026-08-03
- Environment: WSL-headless
- Runner: AI (claude-corp)
- Result Summary: 분할 CSS concat 을 실 chromium 에 태우는 `verify_product_dropup_keynav.py` **27 passed / 0 failed** · `verify_product_dropup_scroll.py` **11 passed / 0 failed** (양 스크립트는 이번 cycle 에서 concat 로더로 갱신).
- Pass/Fail: PASS

### Run 2026-08-03-004 (make test 전 스위트)
- Date: 2026-08-03
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: worktree 에서 `sudo make test` (격리 compose 프로젝트 `repo-unittest`) — **EXIT 0** (pytest feature-0002/0003/0023 전 스위트 PASS, ruff "All checks passed!"). 갱신된 CSS 참조 테스트 5파일(test_share_edit_usable·test_share_joinable_confirm_persist·test_permission_dependency_map + headless 2종) 포함.
- Pass/Fail: PASS

### Run 2026-08-03-005 (PB-0008 사전 시각검증 — 미머지 static QA)
- Date: 2026-08-03
- Environment: Windows-browser
- Runner: AI (claude-corp)
- Bridge: relay @ http://172.26.144.1:9223 — `win-browser.py doctor` ok:true, Chrome/150.0.7871.128, eval 프로브 `1+1`→2
- Evidence: `test-runs.d/evidence/20260803-css-split-workscreen.png` · `test-runs.d/evidence/20260803-css-split-admin.png`
- Result Summary: web-a/b 양 replica 에 css/ 7파일 + 신규 index/admin.html docker cp 주입(CSS-safe 사전 QA, 원본 백업 후) → LB 왕복 4회 신규 html 서빙 확인 → 실 Windows Chrome 진입. 작업화면: 7 sheets 전부 로드(cssRules>0)·`.app-shell` grid·`.sidebar` 252px·전체 스크린샷 정상. 관리콘솔: 7+graph.css 8 sheets·`.admin-pane` flex·`.admin-sidebar` 220px·대시보드 카드/차트/지표 전부 정상 렌더(스크린샷). 시각 회귀 0. QA 후 컨테이너 원상 복구(백업 html 재주입 + css/ 제거) 확인.
- Pass/Fail: PASS
- Notes: 주입 도중 병렬 세션의 PR #1120 배포로 컨테이너가 재생성되어 1회 재주입함 — QA 결과에는 영향 없음. POST-DEPLOY 재검증은 배포 후 Run 으로 별도 기록.

### Run 2026-08-03-006 (롤백 리허설)
- Date: 2026-08-03
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: Cycle 1 커밋(44308fae)에 `git revert --no-edit HEAD` 실적용 →
  base(c0c6800f) 대비 `git diff` **0줄**(완전 원상: styles.css sha256 원본 일치
  349ce797…·css/ 소멸·html 단일 link 복원) → revert 제거 후 재적용·최신 main rebase.
  단일-PR 단일-revert 롤백 가능성 실증 — 이후 cycle 은 동일 절차 준용(§2.1 게이트 6).
  라이브 롤백은 deploy-web.sh last-good 병용.
- Pass/Fail: PASS

## 4. Untested Areas
- 배포 파이프라인 통과(asset-stamp 주입·soak)는 머지 후 배포 시 검증 — POST-DEPLOY PB-0008 Run 예정
- 공유 뷰(share.html)는 share.css 사용으로 본 cycle 영향 없음 (링크 무변경 확인)
