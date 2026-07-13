---
run_at: 2026-07-13T15:40:00+09:00
session: ai/claude/feature-0016-content-cluster (postdeploy)
scope: POST-DEPLOY live (content-cluster TC.8)
verdict: PASS
---

# Run (2026-07-13) — content-cluster POST-DEPLOY 라이브 실증 + PB-0008 — Environment: Windows-browser

- 배포: PR #746(87767ebe 이전 8eceefe2)+h1 PR #748(87767ebe) — deploy-web 무중단 롤링(soak PASS)×2 + alembic **0040 head 적용** + insight/ask-worker 재빌드(**numpy 2.4.6 탑재**·GIT_COMMIT 87767ebe).
- 데이터 파이프라인 실증(관계형 스토어):
  - 시그니처 백필 full pass: 테이블 processed 15,854/changed 429(분석 보유분), 루틴 processed 22,041/changed 21,541(전량 신규), failed 0, remaining 0. **cc_data_main 테이블 255/255·루틴 300/300 시그니처에 능동 분석문 주입** 확인(text_content LIKE 'analysis:').
  - 임베딩 드레인: backlog 19,770 → 0 (bge-m3/embed-ollama, ~57분). cc_data_main 임베딩 100%.
  - 클러스터 pass(h1 후): **objects 23,465(테이블 7,055+루틴 16,410) · clusters 3,652 · schemas 134 · skipped 0 · error 0**. h1 이전엔 루틴 전량 미합류(objects 7,055 — routine_objects.scope_key=datasource 비대칭, PR #748 로 수정).
  - cc_data_main: 클러스터 37+@ — **한국어 컨텐츠 라벨 + 테이블·루틴 혼성** 실증: "아이템 합성 강화"(t5+r14)·"물물교환 거래"(t5+r12)·"퀘스트 데이터 관리"(r10)·"게임 콘텐츠 마스터"(t16)·"업적 시스템"(t8)·"길드 용병 관리"(t3+r3)·"메일 시스템"(r6)·"몬스터 도감 관리"(r6)….
- AGE 투영: full sync 수렴 — cc_data_main **Table 141/141·Routine 217/217**(관계형=그래프 동수). 도중 관측된 sync errors/deadlock 은 **병렬 full sync 중복 실행(운영 실수)+worker 증분 sync 경합**이 원인(코드 결함 아님) — 단일 실행·멱등 재시도로 수렴, step_failures 시 워터마크 미전진이라 증분이 자연 재커버.
- API: `schema_tables('mssql-06656002eda6','…:cc_data_main')` → Routine 300 중 217 cluster_id/label 반환(예: `sp_AddGemStoneEngraving()`→"보석 각인"), Table 255 중 141(예: `TT_AchieveCategory`→"업적 시스템").
- **PB-0008 실 Windows Chrome(bin/win-browser.py, https://localhost/admin 로그인)**:
  - 그래프 뷰 탭 → 데이터소스 `mssql-qa-idc` 전환(134 스키마 카드) → cc_data_main 펼침.
  - `_metaGraph.groupOrder`: 그룹 138 중 **be: 컨텐츠 밴드 95** — "퀘스트 데이터 관리 · 10"·"이상 상태 관리 · 9"·"메일 시스템 · 6"·"몬스터 도감 관리 · 6"·"변신 형태 시스템"(t3+r3 혼성)·"텔레포트 지점 · 3" 등 육안 렌더(스크린샷 /tmp/win-browser-shots/shot_content_cluster_bands.png·shot_content_cluster_mixed.png).
  - **AC-1 PASS**(be: 밴드 ≥5=95, 이름 스템이 아닌 한국어 컨텐츠 라벨) · **AC-2 PASS**(ƒ/⚙ 루틴이 관련 테이블과 동일 밴드 — 변신 형태 시스템 t3+r3 등) · **AC-3**(미클러스터 잔여는 기존 nm:/role:/misc 폴백 그대로 — 무회귀) · window error 수집기 **0건**, 전 구동 스텝 eval 정상.
  - 검증용 QA 핸들(window.__mg — 서빙 사본 한정 임시 append)은 검증 후 **원복 완료**(__mg 잔재 0, repo·이미지 미포함).
- 후속(자연 수렴, 비차단): 타 ds 루틴 임베딩 잔량·클러스터·AGE 투영은 worker 데몬 cadence(클러스터 6h·sync 증분)가 소진. LLM 라벨 kv 캐시 적재로 재호출 0.
