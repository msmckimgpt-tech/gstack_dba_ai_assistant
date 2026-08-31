## Run — TASK-20260831T190000-job-result-unwrap (POST-DEPLOY)

- Date: 2026-08-31
- Environment: 배포본 컨테이너 직접 실행(`repo-web-a-1`) + Windows-browser(PB-0008) 보조
- Target: 배포본 **cac907c4**
- Result: **PASS** — 사용자가 제보한 **그 텍스트**가 본문만 남는다

### 사용자 제보 재현 → 해소 실측

제보된 문자열(각인 래퍼 + 경계 고지 + 본문)을 배포본의 `unwrap_external_answer` 에 그대로
통과시켰다:

```
마커 잔존: False
본문 첫 40자: 수집·적재된 각 레코드나 지표가 어느 유입 경로에서 왔는지를 표시하는 출
본문 끝 20자: 의 라벨을 유지하는 것이 일반적이다.
길이: 230
```

`⟦UNTRUSTED-DATA⟧` · `⟦/UNTRUSTED-DATA⟧` · `[UNTRUSTED] Authored by an external AI runtime…`
가 전부 제거되고 **정의 본문 230자만** 남았다. 컨테이너의 `GIT_COMMIT` 이 `cac907c4` 로
확인돼 이 결과가 배포본의 것임이 확정된다.

### 스코프 경계도 함께 실측됐다

브라우저 세션에서 제보된 task id(`j_fkh687IxkuailLF9`)를 조회하자 **404** 였다 — 그 작업은
다른 계정 소유이고, 폴링 엔드포인트가 `AccountId` 로 닫는 계약이 라이브에서 실제로
작동한다는 뜻이다(없는 것과 남의 것을 구분하지 않는 응답도 그대로).

### 배포 체크리스트

- web·워커 전 서비스 `cac907c4` · 대화 스모크 PASS
- **무중단 실측** `no upstreams available` = **0**
- `/readyz` git_commit = `cac907c4`

### 남은 확인 (사용자)

이 실측은 **서버가 내보내는 값**이 깨끗함을 증명한다. 그 값이 폼 입력란에 채워지는 것까지는
`console_jobs` 신고 러너로 자동완성을 한 번 더 실행해 봐야 눈으로 확인된다 — 다음 실행부터는
원문이 `JobResult` 로 보존되므로 폴백 파싱도 타지 않는다.
