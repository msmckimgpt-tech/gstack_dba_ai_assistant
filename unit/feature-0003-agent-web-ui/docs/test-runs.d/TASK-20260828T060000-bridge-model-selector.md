---
run_at: 2026-08-28T15:10:00+09:00
session: ai/root/feature-0043-bridge-model-selector
scope: 브리지 모드에서 모델·추론 강도 조작면 제거 (P0-T) — 카탈로그·화면·전송·적재 4지점
verdict: PASS (단위·통합) / 화면 확인은 사용자 육안검증으로 이관(사용자 결정)
---

# Run — 모델·추론 조작면 제거 (P0-T)

Environment: container (`make test` 하네스) · 로컬 pytest · **Windows-browser (PB-0008)**

## 결과

| 스위트·검사 | 결과 |
|---|---|
| 컨테이너 `make test` (pytest 전체 + ruff) | **exit 0 · FAILED 0건** — ruff `All checks passed!` |
| `unit/feature-0043-external-llm-bridge/tests` (로컬) | **204 passed** |
| `unit/feature-0003-agent-web-ui/tests/test_model_persist.py` (이중 계약 갱신) | **16 passed** (기존 14 + 브리지 반대편 2) |
| `unit/feature-0003-agent-web-ui/tests/test_model_catalog_bridge_mode.py` (신규) | **3 passed** |
| `test_anonymous_surface_hardening.py` (이중 계약 갱신) | **7 passed** |
| 편집 Python 4파일 AST | 통과 |
| `app.js` · `app/composer.js` ESM `node --check` | 통과 |
| 러너 정본 ↔ 배포본 sha256 | 일치 (`e3b29213…`) |

## 뮤테이션 검증 (테스트가 실제로 잡는가)

`system.py` 의 게이트 조건을 반전(`if not server_llm_enabled()` → `if server_llm_enabled()`) →
`test_blocked_gate_hides_selector` · `test_reopened_gate_restores_selector` **2건 KILL**.
소스 문자열 검사만으로는 이 반전을 못 잡으므로 반환값 테스트를 별도로 두었다.

## Environment: Windows-browser (PB-0008)

**브리지가 이번 cycle 에 복구됐다.** 종전 두 cycle 은 `win_host` 가 `8.8.8.8` 로 잡혀
relay 가 바인딩조차 못 했고, 진단 메시지는 portproxy·mirrored 설정을 가리켜 원인을 엉뚱한 곳에서
찾게 만들었다. 실제 원인은 `bin/win-browser.py` 의 `win_host_ip()` 가 `/etc/resolv.conf` 의
**첫** nameserver 를 무조건 채택한 것이었다(이 호스트는 공용 DNS 를 먼저 나열한다).

| 단계 | 결과 |
|---|---|
| `win-browser.py doctor` | `ok: true` · `bridge_mode: relay` · `endpoint: http://172.26.144.1:9223` |
| `launch` (Chrome 151.0.7922.170) | relay `172.26.144.1:9223 -> 127.0.0.1:9222` |
| `goto https://mysql-ai.company.local/` | **status 200** · title `DQA — Database Query Assistant` |
| 스크린샷 | `evidence/20260828T060000-winbrowser-bridge-restored.png` (로그인 화면) |

사설 호스트 이름은 `WIN_BROWSER_HOST_MAP="mysql-ai.company.local=<wsl-ip>"` 로 해결했다 —
Windows hosts 파일(관리자 권한·시스템 영구 변경) 없이 이 브라우저 인스턴스에만 적용된다.

**로그인 이후 화면(컴포저에서 두 항목이 사라졌는가)은 AI 가 확인하지 않았다.**
사용자 결정(2026-08-28): "배포만 하고 사용자가 직접 확인". AI 가 라이브 계정 자격증명을 갖지
않으며, PB-0008 §41 도 테스트 프로필에 민감 계정 로그인을 금지한다. 화면 판정은 배포 후
사용자 육안검증에 위임한다 — **부품이 제자리에 있다는 것과 화면이 의도대로 움직인다는 것은
다른 주장**이므로, 여기서 후자를 주장하지 않는다.

확인 포인트(사용자용): 대화 입력창의 `+` 메뉴에 **'모델: …' 과 '추론 강도: …' 두 줄이 없어야**
한다. 첨부 관련 두 줄만 남는다.
