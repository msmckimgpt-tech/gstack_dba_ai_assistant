---
run_at: 2026-07-13T17:50:00+09:00
session: ai/claude/feature-0016-content-cluster-p2 (postdeploy)
scope: POST-DEPLOY live (content-cluster-p2 TP.4)
verdict: PASS
---

# Run (2026-07-13) — content-cluster-p2 POST-DEPLOY 라이브 실증 + PB-0008 — Environment: Windows-browser

- 배포: PR #763 머지(main 469fa20d) — deploy-web 무중단 롤링(soak PASS) + insight/ask-worker 재빌드(GIT_COMMIT 469fa20d).
- 클러스터 pass 재가동: objects 23,465 · clusters 3,652 · **attached 4,843**(cap 가드 반영 — 프로브 5,249 대비 소폭 감소 = MAX_SIZE 우회 차단 실동작) · error 0. 단일 full sync 후 AGE 수렴(cc_data_main Table 225=관계형·Routine 298=관계형 — attach 로 루틴 편입 217→298).
- **사용자 리포트 3종 분리 실증**: DT_Castle→"게임 콘텐츠 마스터"(cid20) / DT_CashPoint→"캐시포인트 관리"(cid13) / dt_CombineMaterial→"아이템 합성 강화"(cid0) — 동거 해소(AC-p2-1). cc_data_main 미클러스터 테이블 114→**30**.
- **PB-0008 실 Windows Chrome**(win-browser, https://localhost/admin 로그인, QA 핸들 __mg 임시 주입→원복 완료):
  - cc_data_main 펼침: 그룹 138→**111**(attach 가 affix 잔여 흡수), be: 95, **beSortedAsc=true·beFirst=true**(id 순 선두 배치), **`nm:dt_*` 가짜 가족 0**(구 "dt_c…" 밴드 소멸), nm: 잔여 15(실스템).
  - **연관 밴드 인접(AC-p2-2)**: 라벨 시퀀스 — 길드 4연속(정보 조회→멤버 조회→정보 조회→가입 신청)·퀘스트 3연속(데이터 관리→보상 조회→보상 삭제)·**몬스터 계열 6+연속**(정보→가이드→도감→스킬·클래스→스폰→드롭 아이템→드롭 그룹→드롭 관리)·저항/속성/NPC 각 2연속.
  - window error: benign "ResizeObserver loop…" 1건뿐(예외 아님·기존 노이즈) — 기능 오류 0. 스크린샷 /tmp/win-browser-shots/shot_p2_cashpoint_band.png(길드·퀘스트 인접 밴드)·shot_p2_bands_overview.png.
- AC-p2-1·2·3 전부 충족. 후속(자연 수렴): 타 ds 는 worker cadence 가 동일 로직으로 재클러스터.
