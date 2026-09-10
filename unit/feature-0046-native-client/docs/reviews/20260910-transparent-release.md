# 1.3.1 투명 아이콘 독립 검토

- Trigger: UI/아이콘·설치 UX, code/설치 수명.
- Reviewers: icon_release_review(UX/QA·설치 수명), icon_final_design(디자인/자산).
- Verdict: PASS — 현재 제품 코드 차단 P1/P2 0. 실제 설치 실패 시나리오 결과 반영.
- Human Approval Needed: no — 사용자가 SVG 변환과 최신 버전 배포를 명시 승인.
- P1 이전 슬롯 재실행 경로 → 안정 launcher 경로와 단독 실행 fallback으로 해결.
- P2 기존 launcher onlyifdoesntexist 아이콘 잔존 → 원자 교체/안정ICO, 신규 제거로그 누락 → UninstallDelete 및 실제 fresh/upgrade 제거 확인.
- 실패 교체를 Inno가 삼키는 실측 → 성공 플래그 기반 활성화 차단, invalid payload/locked launcher 재검증 PASS. 수동 실패 완료 안내 픽셀은 별도 미검증으로 기록.
- COM 값 소유권/해제, 숨김 유지·실제 종료 정리, 재실행 인자 비영속화 검토 완료.
- 디자인: 밝음/어두움 16–48px에서 Q/데이터2획 구분, PNG 및ICO9크기 실제alpha0..255/4모서리0, 웹byte일치와6favicon/4로고 PASS.
- P3 README의 EXE 표시아이콘 설명은 root dqa.ico 참조로 교정했다.
- 테스트 nonce fixture 정합은 제품 인증 변경이 아니며624전체검사로 확인. 세부 증적은 test-runs.d/20260910-transparent-icon-release.md.
