---
run_at: 2026-07-30T17:30:00+09:00
session: ai/root/feature-0032-llm-token-budget
scope: admin.js — AI 운영 현황 pane '백그라운드 LLM 토큰 예산' 섹션 렌더 (feature-0032)
verdict: DEFERRED (POST-DEPLOY)
---

# Run 2026-07-30 — Environment: Windows-browser (PB-0008) — **미수행 사유 + 배포 후 수행 예정**

## 미수행 사유

`admin.js` 의 AI 운영 현황 pane 에 '백그라운드 LLM 토큰 예산' 섹션(사용량 막대 · 비율 · 남은 여유 ·
면제 안내)을 추가했다. 이 섹션이 그리는 값은 **새 web 이미지가 응답에 싣는 `llm_token_budget`**
필드다. 배포 전 라이브 web 은 그 필드를 반환하지 않으므로 섹션이 원리적으로 렌더될 수 없다
(현행 코드에서는 `data.llm_token_budget` 부재 → `enabled:false` 경로로 "상한 없음"만 표시).

즉 배포 전 검증은 **거짓 음성**만 만든다. 배포 후로 미루는 것은 본 feature 의 기존 관례와
동일하다(T0b 워커 자원 pane 선례 — `REV-20260730T143000-worker-resources-pane.md`).

## 배포 후 검증 항목 (PB-0008, `bin/win-browser.py`)

- 감사 > AI 운영 현황 진입 → **'백그라운드 LLM 토큰 예산 (최근 24시간)' 섹션 노출**
- 실제 수치 표시: `<소비> / <상한> 토큰 (N% · 남은 여유 M)` — 배포 시점 실측은 약 685만/2,000만
- 막대 색: 80% 미만 녹색(현재 34% → 녹색)
- 면제 안내 문구 노출: "대화 답변·자가검증·제목 생성처럼 사용자가 기다리는 호출은 이 예산에서
  제외되며 상한과 무관하게 항상 나갑니다."
- 상한을 현재 소비보다 낮게 내린 뒤(콘솔 설정 live 반영) 재진입 → 막대 빨강 + "상한 도달" 문구 +
  attention 배너 확인 → **같은 창에서 대화 답변이 정상인지 확인** → 상한 원복
  (이것이 "예산이 사용자를 막지 않는다"의 유일한 라이브 증거다)

## 배포 전 확보한 대체 증거

- `test_llm_budget_pane.py` — `admin.js` 가 `data.llm_token_budget` 를 실제로 읽는지, 면제 안내
  문구가 있는지, "상한 없음"과 "조회 불가"를 다른 문구로 구분하는지, snapshot 키와 렌더 키가
  일치하는지를 소스 단정으로 검사(응답 필드 존재 ≠ 노출이라는 T0b 교훈의 회귀 방지).
- `node --check admin.js` 통과.
