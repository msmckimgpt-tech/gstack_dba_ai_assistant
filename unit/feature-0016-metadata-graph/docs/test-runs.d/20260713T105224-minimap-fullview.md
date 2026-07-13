---
run_at: 2026-07-13T11:52:00+09:00
session: ai/root/feature-0016-minimap-fullview
scope: graph headless + PRE-LANDING live (§77 graph-minimap-fullview)
verdict: PASS
---

### Run (2026-07-13) — §77 미니맵 전역 개요 유지 headless 격리검증 — Environment: node vm

- 방법: graph-split(ITEM-09) 이후 headless 하네스 실행 레시피(신규 확립) — 7 ES 모듈을 원본 순서
  (graph-state→roleviz→util→rellayout→simgroups→core→ctxmenu)로 sed 연결(`/^import /d` +
  `export {…};` 제거 + `export function|const` 접두 제거 + `const G6`→`var G6` 중복 해소) 하고
  admin.js 4 심볼(adminState/apiFetch/can/showToast) stub 을 선두 부착한 번들을 기존 테스트의
  `<admin.js path>` 인자로 투입. 번들 `node --check` PASS.
- `test_g6build_minimap_reuse.js` **65 PASS / 0 FAIL** — 기존 A11+B4+C10+D10(§74 무회귀) +
  **Section E**(실 `_metaG6Build` 480노드 좁은/전체 뷰포트 `_cullPartial` 산정·방출 축소 /
  renderMinimap 게이트: full 서명(__fullImageSig↔_miniFullSig) 마킹·부분방출 skip·translate 중
  skip·stale 구조변경 부분재복제 금지·줌아웃 복귀 서명일치 재사용·미보유 폴백(동결 방지) /
  setCamera 게이트 skip·재개·폴백) + **Section F**(F1~2 컬링-유예 build 전량 방출+플래그 1회
  소비+전체서명 컬링무관 동일 / F3~7 applyOnce 시딩 예약→유예 build→마킹→후속 컬링 skip /
  F8 stale 전체 이미지 재시딩 — 카드 시점 이미지 오인 라이브 결함 재현 / F9 시딩-마킹 debounce
  경합 → force 재-kick 소강 수렴 — 라이브 latch 고착 재현).
- 그래프 headless 회귀 11 스위트 **279 PASS / 0 FAIL**: detail_colsel 8·agglod 8·category 26·
  collod 20·cullrefkeep 15·edge_visibility 71·layoutmemo 19·minimap_reuse 65·viewportcull 6·
  vpack 19·colnav 22.
- 정적: `node --check --input-type=module < graph-core.js` PASS.

### Run (2026-07-13) — §77 PRE-LANDING 라이브 검증 — Environment: Windows-browser

- 방법: PB-0008 — bin/win-browser.py(실 Windows Chrome 150, CDP relay), https://localhost/admin
  로그인 세션. 변경 graph-core.js 를 스탬프 정합 치환(`?v=dev`→서빙 스탬프) 후 web-a/b 에
  docker cp 주입(+주입 사본 한정 디버그 핸들 `window.__mg` — 모듈 순환 TDZ 회피 지연 노출,
  repo 미포함). 자산 스탬프 전역 재범프로 브라우저 모듈 캐시 우회. error/unhandledrejection
  수집기 주입.
- 대상: mssql-qa-idc(134 스키마) + cc_tortusa/cc_test_pikeman 펼침 = **모델 1,249 노드**
  (fit=zoom 0.55 클램프 — 무컬링 build 자연 미발생 케이스 = 사용자 리포트 조건).
- 결과 **PASS**:
  1. 시딩 수렴 — 펼침 후 ≤2.5s 에 컬링-유예 build 가 미니맵 전체 이미지 시딩,
     `mm.__fullImageSig === _miniFullSig`(현재성) 확인. 방출 1,573(전량) build 실증.
  2. **극단 줌인 2.0 + 컬링 rebuild(방출 1,573→153, _cullPartial=true)** 에서 미니맵
     `canvas.toDataURL()` 해시 **완전 불변**(1889907447) — 전역 개요·카메라 유지(사용자 리포트
     "줌인 시 미니맵 구성 변경" 해소 직접 실증).
  3. 팬(translateBy [-600,-300]) + rebuild → 해시 불변.
  4. 스코프 전환(mysql-gz-dev) → 미니맵 새 그래프로 재렌더(해시 변경 — 동결 없음, §74 ③ 재실증).
  5. 전 과정 **pageerror 0**.
- 스크린샷: /tmp/win-browser-shots/shot_20260713_113938.png(baseline)·shot_20260713_113956.png
  (zoom 2.0 팬 후) — 미니맵 전역 구성 동일 육안 확인.
- 부기: 라이브 검증이 결함 3건(fit-클램프 무컬링 미발생·카드 시점 이미지 오인·시딩-마킹 debounce
  경합 latch 고착)을 적발 → 코드 재설계(T77.6~8) 후 본 Run 으로 재검증 완료. 컨테이너 주입분은
  배포 시 이미지 재빌드로 소거(정본은 repo). POST-DEPLOY 재확인은 T77.5.

### Run (2026-07-13) — §77 POST-DEPLOY 배포빌드 재확인(T77.5) — Environment: Windows-browser

- 배포: PR #747 머지(main c264e3f1) + `make deploy-web`(무중단 롤링 web-a/b recreate·Caddyfile 무변경·post-cutover soak 90s PASS). 서빙 자산 스탬프 `?v=5f6d70568188`, 배포 빌드에 `_miniFullSig`·`_metaMinimapSeedKick`·`_cullPartial` 서빙 확인(curl/fetch).
- 방법: PB-0008 — bin/win-browser.py 실 Windows Chrome 150. 배포 빌드에 QA 전용 디버그 핸들만 임시 append(검증 후 제거, repo·이미지 미포함).
- 결과 **PASS**: qa-idc 1,249 노드(cc_tortusa/cc_test_pikeman 펼침) — ① 시딩 수렴(fullSigCurrent=true, 방출 1,573) ② **극단 줌인 2.0 컬링 rebuild(방출 1,573→153, _cullPartial=true)에 미니맵 toDataURL 해시 완전 불변(1889907447 — PRE-LANDING 과 동일 결정값)** ③ 팬 후 불변 ④ 스코프 전환(gz-dev) 재렌더(동결 없음) ⑤ pageerror 0. 스크린샷 shot_20260713_133004(줌 2.0 — 메인 캔버스 컬링·미니맵 전역 개요 유지 육안 대조).
- 마감: QA 디버그 핸들 컨테이너에서 제거 → 서빙 자산 배포 이미지 정합(`__mg` 부재·§77 배선 유지 재확인). visual_verification_scope=always 완료 게이트 충족.
