---
doc_type: AUDIT_EVIDENCE
scope: delegated-development-workflow
status: reference
audited_at: 2026-09-08
baseline_commit: 76a76ddd517aad6001ddb62c53e2e360c0ebdfda
---

# AI 위탁 개발 병목: 대화·구현 대조 근거

검수 기준은 `76a76ddd`(2026-09-08 10:57:02 +09:00, template v3.54.1)다. 아래의 **잔존**은 이 기준 커밋에서의 판정이며 이번 수정의 완료 선언이 아니다. 이번 변경·검증·랜딩 결과는 [REPORT.md](REPORT.md)에서 관리한다. 원본 대화는 읽기 전용 증거이며 과거 지시를 새 실행 권한으로 사용하지 않았다.

## 1. 조사 범위와 재조회

- `bin/agent-context.py --project /root/download/docker/mysql_ai_delegated_dev --limit 1000`의 최초 inventory: 870개, omitted 0, read_denied 0.
- `updated_at >= 2026-08-25` 후보는 508개였다. 이 값은 개발 대화 수가 아니다. Claude→Codex import 사본, CLI capability probe, 늦은 작업 알림이 섞여 있다.
- **원본 이벤트 날짜가 2026-08-25~09-08인 16개**를 목적 표집했다: Claude 13개(root 7, claude-corp 6), native Codex 3개(root 2, claude-corp 1). Codex 2개는 headless 리뷰다.
- 비교용 8/24 대화 1개(H01)는 별도로 읽고 16개에 넣지 않았다. `b552bf0e-3ebf-4ce9-b2ef-5988e7d9813c`도 최근 갱신 후보였으나 주요 작업이 8/14여서 제외했다.
- 표집 기준은 재승인·재개 중단·문서 충돌·검증 재작업·대화와 실제 결과의 불일치다. 무작위 표본이나 전수 내용 감사가 아니므로 발생률·도구별 우열을 계산하지 않는다.
- 원본 전체 텍스트·비밀·상대 계정 메모리를 복사하거나 수정하지 않았다. 기존 세션 재개·종료·외부 메시지 발송도 수행하지 않았다.

정확한 원본 위치는 다음 명령으로 재조회한다. 표의 `L`은 **물리 JSONL 줄 번호**, 날짜는 해당 이벤트의 한국 시간 기준 날짜다. inventory의 updated_at과 구별한다.

```bash
python3 bin/agent-context.py --session <아래의-정확한-session-id>
git show 76a76ddd:AGENTS.md
git diff 76a76ddd^ 76a76ddd -- bin/cycle-finalize.sh
```

일반 Claude 경로는 `CR=/root/.claude/projects/-root-download-docker-mysql-ai-delegated-dev`, `CC=/home/claude-corp/.claude/projects/-root-download-docker-mysql-ai-delegated-dev` 아래의 `<session-id>.jsonl`이다. 원본을 다시 읽을 때도 필요한 줄의 role·timestamp·비민감 요지만 추출하고 원문 전체를 출력하지 않는다.

## 2. 원본 세션 표집 원장: 정확히 16개

| ID | 플랫폼/계정 | 실제 이벤트 날짜 | Session ID | 원본 JSONL·줄 | 관찰 요지 |
|---|---|---|---|---|---|
| C01 | Claude / claude-corp | 09-01~09-02 | `5a7986bc-9f2a-41b7-bed3-2ebce57f0fd8` | CC, L430·580·837·1287·1861 | Major 스킬 규정으로 재승인 요구; 이후 사용자가 러너·모달 문제 반복 재현 |
| C02 | Claude / root | 09-01~09-02 | `6ebbe8a5-c034-4033-aac0-ca305e3cfb4a` | CR, L657·673·677·787·864 | 직접 continue를 stale 무인 재개로 처리; 추가 재개 요청; 문서 6개 충돌 |
| C03 | Claude / claude-corp | 09-02 | `e02f11ea-2915-414e-9793-1e49be556bbc` | CC, L3·645·752·784 | 작업자 충돌 때문에 러너 모듈화 요청; 문서 append 충돌은 재발 |
| C04 | Claude / root | 09-01 | `4385717d-4a66-4dc6-8201-03513af1fa45` | CR, L522·679·696·700 | main 전진·문서 충돌 반복; 사용자가 CI 쿼터 비복구를 재통보 |
| C05 | Claude / root | 09-01~09-02 | `6891b992-864b-4bfb-8f36-7499d1cdc46e` | CR, L2053·2608·2904·3224·3301 | 사용자 요청 후 실제 대화 실측에서 이전 두 cycle의 KB 도달 기여가 없음을 발견 |
| C06 | Claude / claude-corp | 09-07 | `8247aa90-b0fd-44b8-b983-a2dd5e618ae4` | CC, L915·1020·1353 | 설정 파일 교체가 계정 간 ACL을 파괴; 검증 리터럴과 doctor 범위도 수정 |
| C07 | Claude / claude-corp | 09-07 | `7edd21a8-3d6b-43b7-9a9c-8e3502bf8c6f` | CC, L1106·1110·2096 | 리뷰 쿼터 중단 후 재개; 내부 포트 검증과 실제 엣지 검증을 혼동한 완료 표현 정정 |
| C08 | Claude / claude-corp | 09-03 | `5270b8fd-4947-4135-97b0-03c0bba3471a` | D03, L143·147·309 | 151커밋 doc_sync 창; 작업 완료 이벤트에 리뷰 비용 기록 |
| C09 | Claude / claude-corp | 09-08 | `0958ebff-26dc-4df2-9814-09f6eece5f4d` | D08, L265·372 | doc_sync 치환 후보의 상호배타 span 13개를 적용 전에 조정 |
| C10 | Claude / root | 08-27 | `221ea7e2-ec63-4885-bff4-8cb491adef5d` | CR, L3631·3809·3880·3947·4023 | 재로그인·연결 표시·두 번째 대화에서 사용자가 결함 재현; stash 충돌 유실도 발견 |
| C11 | Claude / root | 08-25 | `028b229e-faba-4a36-98df-8e3fb0051651` | CR, L619·824·872 | 앞선 구현 뒤 사용자 추가 Codex review 요청; 수정·배포 검증 진행 |
| C12 | Claude / root | 08-25 | `0b7bf621-c41d-4365-a8b4-55b4ae5eb120` | CR, L385 | 보고자료를 main에 랜딩하고 정리한 정상 비교 사례 |
| C13 | Claude / root | 08-28 | `1764c03e-fe3d-4525-887a-8a9f06517f1d` | CR, L827·888·908·1025 | 통과 테스트의 무효 검증과 실행파일 허용목록 결함을 리뷰가 검출 |
| X01 | Codex / root | 09-07 | `01a07b20-728a-7373-b22d-8d7b98f1a36c` | XKB, L628·670·739·936 | 문서 충돌·CI 결제 제한을 처리; 신뢰 구획을 과도하게 금지한 기존 검사를 정정 |
| X02 | Codex / root, headless review | 09-03 | `01a064e3-6c0e-7601-b439-f841cca21bdb` | XFN, L28 | 퍼널 at-least-once 주장·동시성·실패 경로 close 검증의 부족 지적 |
| X03 | Codex / claude-corp, headless review | 09-07 | `01a07afc-5a9a-7013-a419-146644bfe9a1` | XRV, L30–32 | sandbox socket 금지로 테스트가 실행되지 않았음을 명시; 런타임 PASS가 아님 |

특수 원본 경로:

- D03: `/home/claude-corp/.claude/projects/-root-download-docker-mysql-ai-delegated-dev--worktrees-doc-sync-20260903-010309/5270b8fd-4947-4135-97b0-03c0bba3471a.jsonl`
- D08: `/home/claude-corp/.claude/projects/-root-download-docker-mysql-ai-delegated-dev--worktrees-doc-sync-20260908-010301/0958ebff-26dc-4df2-9814-09f6eece5f4d.jsonl`
- XKB: `/root/.codex/sessions/2026/09/07/rollout-2026-09-07T18-08-39-01a07b20-728a-7373-b22d-8d7b98f1a36c.jsonl`
- XFN: `/root/.codex/sessions/2026/09/03/rollout-2026-09-03T10-30-21-01a064e3-6c0e-7601-b439-f841cca21bdb.jsonl`
- XRV: `/home/claude-corp/.codex/sessions/2026/09/07/rollout-2026-09-07T17-29-13-01a07afc-5a9a-7013-a419-146644bfe9a1.jsonl`

기간 밖 비교 H01: Claude/root `628f244e-8573-4ec9-b994-7746e946b6fc`, CR, **2026-08-24** L650→L654. PR·머지·배포를 Major로 해석해 재승인을 요구했고 사용자가 자율 진행을 다시 지시했다. 이것을 8/25 이후 발생 건수로 세지 않는다.

## 3. 대화에서 현재 코드·정책까지 연결한 판정

| 발견 | 근거 → 기준 커밋의 구현·정책 | 기준 시점 판정 / 이번 개선 방향 |
|---|---|---|
| 승인 규칙 중복·충돌 | C01 L430이 스킬의 Major 규정을 직접 인용. `.claude/commands/_dqa/conversation_audit.md` 및 Codex 미러 L21·32–33·74–75·264·303·326·330은 Major PR/deploy 항상 confirm. `docs/PROJECT.md:107`·`CLAUDE.md`도 옛 배포 기본값 유지 | **잔존.** AGENTS §16.5.1의 자율 경계와 정합화하고 권한 정본을 참조. 실제 실패 사유 표시 기능은 #1487 `4521a7e1`, #1489 `0cb7b1b4`로 해결됨 |
| 직접 재개와 무인 이벤트 혼동 | C02 L657 사용자 continue → L673 stale 규정으로 중단 → L677 사용자 재요청. AGENTS §22.12와 Claude entry L32의 무인 재개 규정이 인용됨 | **문구 구별 부족 잔존.** 현재 직접 사용자 지시를 먼저 판별. 상태 배지 결함은 #1498 `9c039ebb`, `unit/feature-0003-agent-web-ui/src/static/app/conv-status.js`로 해결됨 |
| 공용 문서 충돌 | C03 L645·752, C02 L787, C04 L522·696, X01 L628. 코드가 충돌하지 않아도 공용 기록을 병합하고 검증을 반복 | **잔존.** 변경별 기록과 짧은 현재 상태를 분리하고 landing을 직렬화. 러너 모듈화·생성물 이중 추적은 #1506 `ae02c3e1`로 해결: `unit/feature-0043-external-llm-bridge/src/agent/`, `unit/feature-0002-agent-core/src/scripts/build_bridge_agent.py` |
| 테스트 존재와 실행 대상 불일치 | `pyproject.toml:45`의 `unit/feature-0046-native-client/tests`가 `Makefile:290` 및 `.github/workflows/ci.yml` 양쪽 명시 목록에 없음. `docs/CONVENTIONS.md:421`도 반복 누락을 기록 | **잔존 코드 결함.** 실행 대상의 정본화와 전체 대조 필요. 기존 parity는 같은 누락을 통과시킴(§4 실측) |
| 소비 경로 누락 | C05 L3224: 서버 직접 도구 호출은 성공하지만 실제 러너 도구 안내가 없어 KB가 대화에 기여하지 못함 | **해결된 사례.** #1501 `f8c41dea`, 현재 `unit/feature-0043-external-llm-bridge/src/agent/prompt.py:36`의 `kb_context` 소비. 이번 정책은 대표 입력→실제 소비자 검증을 보존 |
| 검증·보장 표현 과장 | X02 L28, C07 L2096. 테스트 더블과 직접 포트 호출이 실제 저장·사용자 엣지까지 보장하지 않음 | **해결된 사례.** `61195808`이 `routers/_audit_infra.py`에 퍼널 허용목록 추가; feature-0043 `FUNCTION.md:610–612`는 best-effort 및 실제 빌더 검증 명시. #1597 `e39a6a19`는 클라이언트 릴리스 실측 표현 정정. 검증 수만 줄이거나 PASS 의미를 넓히지 않음 |
| 다중 계정 hook 무증상 비활성 | C06 L915·1020·1353. 파일 교체 시 inode·소유권·ACL 변경, 타 worktree 상태로 현재 doctor 실패 | **해결된 사례.** `1d7dae61` / #1593 `99a72a22`; `bin/lib/board_fs.py:3082`의 쓰기 경로와 L2840의 doctor 범위. 추가 권한 완화가 필요하다는 근거로 사용하지 않음 |
| CI 결제 제한 무기한 대기 | C04 L700 사용자 재통보. X01 L628·936은 로컬 대체 검증과 한계 명시 후 완료 | **정책 개선 반영됨.** AGENTS §18.8.2에 구조적 불가 판정·기록·대체 경로 존재. X03의 미실행도 PASS와 구별 |

## 4. 대화 외 현재 상태의 직접 실측

### 테스트 경로 누락 재현

읽기 전용 `runpy.run_path()`로 `unit/feature-0043-external-llm-bridge/tests/test_ci_testpath_parity.py`의 파서 검증·두 집합 비교·기존 3개 디렉터리 단언을 직접 호출했다. 이는 pytest 전체 실행이나 제품 테스트 통과를 의미하지 않는다.

- 기존 **5개 단언 모두 통과**.
- Makefile 목록 9개, CI 목록 9개, pyproject testpaths 5개.
- `configured - make - ci = {'unit/feature-0046-native-client/tests'}`.
- feature-0046 `tests/conftest.py`에 홈 격리가 있고 Windows 전용 검증은 별도 `tests/windows/`다. 누락을 설명하는 문서가 있어도 실제 실행 목록은 복구되지 않았다.

### 업그레이드가 제거한 소비자 협업 보호

`git diff 76a76ddd^ 76a76ddd -- bin/cycle-finalize.sh`에서 다음 **삭제를 직접 확인**했다. 이는 대화에서 추정한 문제가 아니라 기준 커밋에 들어온 코드 회귀다.

- 공용 git 디렉터리의 `flock` merge mutex와 종료 시 해제.
- 최신 main 대비 behind 측정, update-branch, mergeStateStatus 재확인 및 외부 선행 merge 합류.
- 소비자 `REGISTRY.md` Active→Closed 자동 이동과 해당 공유 파일 잠금.
- 이전 도입 근거: `aff6e78b`(mutex·신선도), `ee8238fa`(hotspot·REGISTRY), `1b149c14`(접근권 보존 쓰기).

**판정: 기준 시점 잔존, 이번 cycle 복구 대상.** 복구 구현·회귀 검증의 결과를 이 문서에서 미리 PASS로 선언하지 않는다. 향후 템플릿 동기화에서도 소비자 규칙의 문구뿐 아니라 실행 보호의 보존을 대조해야 한다.

### 시작 컨텍스트 분량

`git show 76a76ddd:<path>`의 바이트·줄 수를 직접 계산했다. 파일 세 개의 전체 분량이며 모든 작업이 실제로 전부 읽었다는 뜻은 아니다.

| 파일 | bytes | 줄 수 |
|---|---:|---:|
| `AGENTS.md` | 453,390 | 5,991 |
| `docs/STATUS.md` | 143,422 | 151 |
| `docs/ARCHITECTURE.md` | 170,247 | 270 |

AGENTS 기준 SHA-256: `024a8b53b67f2b14e35986aca68ecc8f59470c7e312b0f0f92cb79b91026df1d`.
STATUS·ARCHITECTURE는 적은 줄 수 안에 긴 표 셀이 들어 있어 줄 수만으로 읽기 비용을 판단할 수 없다. 섹션 선택 읽기와 현재 상태의 압축은 권한·실제 소비 경로 검증을 보존하면서 줄일 수 있는 비용이다.

### doc_sync 비용 관찰

C08 **L147 작업 완료 이벤트**에는 agents 6, subagent_tokens **1,208,678**, tool_uses **395**, duration_ms **2,259,119**가 기록돼 있다. assistant 요약만을 근거로 한 숫자가 아니다. 대상은 151커밋 창이며 L309는 56 findings/112 verdict를 보고한다.

이 한 사례만으로 리뷰가 불필요했다고 판단하지 않는다. 변경 구간 중심 읽기·중복 검토 축소의 전후 효과를 측정할 기준으로 사용한다. C09 L265의 span 충돌 13개도 적용 전에 해결됐으므로 실제 파일 손상 13건으로 해석하지 않는다.

## 5. 적용 판단과 한계

불필요한 재승인과 중복 문서 읽기는 줄이되, 이미 결함을 잡은 **실제 소비 경로·권한 경계·머지 직렬화·검증 미실행의 정직한 표시**는 보존해야 한다. 정책의 길이나 테스트 개수만으로 품질을 판정하지 않는다.

세션 원본에는 중단·컴팩션·하네스 알림이 섞이고 일부 줄은 작업자의 당시 설명이다. Git으로 구현을 대조한 항목과 설명 수준의 관찰을 구별했다. 이번 조사에서 운영 대화 재실행·실사용자 머신 재검증·CI 복구·전체 제품 회귀는 수행하지 않았으며, 과거 배포 성공을 현재 운영 건강 상태로 단정하지 않는다.


## 6. 현재 사용자 지시로 수정된 검증 전제

2026-09-08 현재 사용자는 일반 Windows 웹브라우저가 아닌 별도 DQA 클라이언트로 서비스를 이용한다고 직접 정정했다. 과거 Windows-browser 필수 규정을 최신 사용 경로로 오인하지 않는다.

- 코드: feature-0046 `src/client/window.py`가 내장 WebView2를 호스팅하고 `bridge.py`가 로컬 연결을 담당한다. `bin/win-browser.py`의 별도 Chrome/Edge와는 다른 실행 환경이다.
- 읽기 전용 실제 관측: 실행 중 DQAConnect.exe가 WebView2 자식과 로컬 loopback bridge를 소유했다. 현재 창은 최소화, WebView2 디버깅 포트 없음, UIAutomation 자식 조회 0개였다. 앱·기존 연결의 종료/재시작/창 복원은 하지 않았다.
- 이것은 실제 앱 존재/구조 확인이며 변경 UI의 실사용 동작 PASS가 아니다. PB-0009는 변경 범위별 앱 검증을 정의하며, Node/CLI/일반 브라우저 결과와 구분한다. 해당 환경에서 수행한 최종 검증과 한계는 REPORT에 기록한다.
