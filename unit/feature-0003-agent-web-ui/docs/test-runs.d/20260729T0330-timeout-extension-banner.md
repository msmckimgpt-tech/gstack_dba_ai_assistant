---
run_at: 2026-07-29T03:30:00Z
session: ai/root/feature-0030-ask-timeout-extension
scope: [timeout-extension, composer-banner, browser-notification, rbac]
verdict: PENDING (코드 미배포 — 배포 직후 라이브 수행 예정)
---

### Run (2026-07-29) — feature-0030 실행시간 연장 배너 — **Environment: Windows-browser (PB-0008)**

cycle: `ai/root/feature-0030-ask-timeout-extension` · CHG-20260729T032307-timeout-extension.

**현재 상태: 미수행 — 사유는 대상 코드가 아직 라이브에 없기 때문.**
본 cycle 이 추가한 배너·승인 경로는 배포된 web 컨테이너에서만 관측 가능하다. 브리지 자체는
정상(`bin/win-browser.py doctor` → `{"ok": true, bridge_mode: "relay", cdp_version:
"Chrome/150.0.7871.115"}`)이므로, **cycle-final 후 배포 직후 아래 시나리오를 실행하고 본
fragment 를 PASS/FAIL 로 갱신한다**(프로젝트의 POST-DEPLOY PB-0008 관례).

#### 검증 시나리오

1. 관리 콘솔 `시스템 > 설정 > 실행 타임아웃` → `에이전트/쿼리 실행 타임아웃` = 10초 저장
   (run 예산 30초 · 확인 시점 24초). 같은 화면에 신규 설정 3종이 보이는지 확인.
2. 작업 화면에서 다단계 추론이 필요한 질문 전송.
3. ~24초 시점: 컴포저 위 **주황 배너** + [계속 추론] 노출, 남은 시간 표시.
4. **미승인 경로**: 방치 → 30초 + 유예(20초) 후 종전 문구로 타임아웃 종료.
5. **승인 경로**: [계속 추론] 클릭 → 배너가 회색 "시간 제한 없이 끝까지 추론하는 중" 으로 전환 →
   30초를 넘겨 답변 완주.
6. 승인 후 '중단' 버튼이 여전히 즉시(≤15분 per-call 상한 내) 동작하는지 — codex P1-3 수정의
   핵심 계약.
7. 다음 질문은 기본 타임아웃으로 복귀(승인 비전이).
8. 콘솔 설정 원복.
