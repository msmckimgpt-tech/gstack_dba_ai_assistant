---
run_at: 2026-07-29T15:40:00+09:00
session: ai/claude/feature-0003-attach-list-delete
scope: 첨부 목록 행 삭제(×) 추가 — 안내 문구와 화면의 불일치 해소 (pre-commit)
verdict: PASS (컨테이너 스위트 · 정적) / PB-0008 라이브 재검증은 배포 직후 append 예정
---

### Run (2026-07-29 15:40) — attach-list-delete pre-commit — **Environment: container(agent image) — Windows-browser 는 배포 직후 수행(아래 §3)**

#### 1. 발견 경위 (선행 cycle 의 POST-DEPLOY 검증 산물)

본 cycle 자체가 **PB-0008 라이브 검증의 결과물**이다. 선행 `20260729T1402-attach-full-scope` 배포
직후 실 Windows Chrome(relay, Chrome/150)으로 첨부 사이드패널을 열어 확인한 결과:

- 안내 1줄 노출 확인: "AI 는 이 대화에 올린 파일 전체를 참고합니다. 필요 없는 파일은 × 로 삭제하세요."
- `#composerAttachmentsScopeAll` / `#attachScopeAllRow` **부재** 확인 (체크박스 제거 정합)
- **그러나** 그 화면의 목록 행(`.attach-list-item`)에는 다운로드(⬇)만 있고 **× 가 없었다** —
  안내가 가리키는 컨트롤이 화면에 없는 구간(목록 뷰)이 실재했다. 본 cycle 이 그것을 메운다.

#### 2. 컨테이너 스위트

`COMPOSE_PROJECT_NAME=repo make test` → **실패 13건**, main baseline(PG 환경성 attachment 13건)과
동일 집합. 본 변경은 프론트 2파일(app.js/styles.css)뿐이라 파이썬 테스트에 영향 없음 —
**신규 실패 0**. `node --check app.js` PASS.

#### 3. PB-0008 Windows-browser 라이브 재검증 — 배포 직후 수행

선행 cycle 과 동일한 근거(병렬 세션 7개가 같은 핫스팟 편집 중, 머지 전 라이브 교체 회피)로
검증 시점을 배포 후로 둔다. 확인 항목:

1. 첨부 목록 행에 `×` 노출 + hover 시 danger 색
2. `×` → confirm → 실제 삭제 → 목록에서 사라짐 + 토스트
3. 삭제 후 다른 파일 업로드 시 **지운 파일이 pill 로 부활하지 않음** (ux BLOCK 회귀 가드)
4. 버전 배지(`v2 · AI 수정`) 행에서 이름 말줄임이 배지를 먹지 않고, 메타줄이 1줄 유지
5. 그룹 대화에서는 목록 `×` **미노출**(안전판)
