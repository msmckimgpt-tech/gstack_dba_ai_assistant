---
run_at: 2026-08-28T10:00:00+09:00
session: ai/claude/feature-0043-bridge-onboarding-trust
scope: 온보딩 지시문의 자기 증명 (TASK-20260828T100000) — `/ai/connect` 지시문 본문
verdict: 배포 전 **미수행** — 대상이 라이브에 없어 관측 불가. 배포 직후 수행 후 본 fragment 갱신
---

# Run — 온보딩 지시문 자기 증명

Environment: **Windows-browser 미수행(배포 전)** — 사유는 아래. 배포 후 수행 예정.

## 왜 지금은 수행할 수 없나

이 cycle 이 바꾼 것은 **화면에 그려지는 텍스트**다(앞선 브리지 cycle 들과 다르다 — 그때는
`static/` 아래이지만 브라우저가 파싱하지 않는 파이썬 파일이라 "대상 화면 없음" 이 사유였다).
지시문은 `/ai/connect` 단독 페이지와 대화 화면의 연결 모달 **양쪽에 표시**되므로, 시각검증
대상이 분명히 존재한다.

다만 그 문안은 **서버가 조립해 내려보낸다**(`compose_connect_handoff`). 즉 라이브에 이 코드가
배포되기 전에는 브라우저로 무엇을 열어도 **옛 지시문**만 보인다 — 지금 PB-0008 을 수행하면
이번 변경과 무관한 화면을 찍고 "검증했다" 고 적는 셈이 된다. 그건 게이트를 만족시킬 뿐
아무것도 검증하지 않는다.

`deploy_scope` 가 활성이라 이 cycle 은 머지 후 곧바로 재배포된다. 검증은 **그 다음**이 맞다.

## 배포 전에 실제로 검증한 것

화면 없이 확정할 수 있는 것은 전부 확정했다.

| 축 | 방법 | 결과 |
|---|---|---|
| 지시문 실문안 | 배포본 함수(`compose_connect_handoff`)를 실제 로드해 렌더 | 전문 육안 확인 — 검증 값 블록·평문 CA 경로·5단계 러너·토큰 성질 모두 의도대로 |
| CA 지문 정확성 | `openssl x509 -noout -fingerprint -sha256` 과 3출처 대조 (`artifacts/certs/rootCA.pem` · `artifacts/trust-bundle/rootCA.crt` · trust 번들 페이지 표기) | 4값 전부 일치 |
| 러너 체크섬 | 정본 ↔ 서빙 사본 `sha256sum` | 동일 |
| 전송 가드 | `_transport_is_safe` 10 케이스 (userinfo·서브도메인 우회 포함) | 전건 기대대로 |
| 계약 회귀 | `test_handoff_trust.py` 37건 + feature-0043 스위트 + `make test` | green (exit 0) |
| 사각지대 | 뮤테이션 5종(C2·X1·X7·X8·X11) 재적용 | 전부 KILL |

## 배포 후 수행할 것 (이 fragment 를 갱신한다)

1. `bin/win-browser.py` relay 로 `/ai/connect` 접속 → [연결 정보 만들기].
2. **판독 항목**: ⓐ 검증 값 블록에 CA 지문·러너 체크섬이 **실제 값**으로 렌더되는가(플레이스홀더나
   빈 자리가 아닌가) ⓑ 평문 CA URL 이 https 보다 **앞에** 오는가 ⓒ 발급자 계정명이 실리는가.
3. **레이아웃**: 지시문이 길어졌으므로(약 1.6배) 모달 안에서 스크롤·복사 버튼이 정상인지 —
   잘림·overflow 로 일부가 복사되지 않으면 그 자체가 이번 변경의 회귀다.
4. 결과(스크린샷 경로 포함)를 위 verdict 와 함께 이 파일에 기록.
