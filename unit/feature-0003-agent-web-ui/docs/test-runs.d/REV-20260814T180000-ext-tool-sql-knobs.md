---
run_at: 2026-08-14T18:00:00+09:00
session: ai/claude/feature-0041-external-ai-tool-surface
scope: feature-0041 P1 — 외부 AI 도구 패널에 SQL knob 2종
verdict: PASS
---

# Run — 외부 AI 도구 패널 (PB-0008, 머지 전)

- **Environment**: Windows-browser · **Runner**: AI · **Bridge**: relay `http://172.26.144.1:9223`
- **대상**: 브랜치 코드 bind-mount 격리 컨테이너(`/app/web` + `/app/shared`)
- **Evidence**: `evidence/REV-20260814T-sql-knobs.png`

`시스템 > 설정 > 외부 AI 도구` 패널 실측 — **6행**:

1. 계정당 분당 도구 호출 상한
2. 계정당 시간당 반환 행수 상한
3. 계정당 시간당 반환 바이트 상한
4. 미제출 작업 허용 개수
5. **자유 SELECT(execute_sql) 허용** ← 신규
6. **쿼리 1건 반환 행수 상한** ← 신규

두 신규 knob 모두 라벨·설명·단위·기본값·'즉시 반영' 배지와 함께 렌더된다. 둘 다 읽는 코드가
실재하며(`routers/ai_tools.py` 의 P1 게이트·건당 상한), "소비처 없는 knob 금지" 규율을 지킨다 —
그 규율을 강제하는 테스트도 함께 있다(`test_every_console_knob_has_a_consumer`).
