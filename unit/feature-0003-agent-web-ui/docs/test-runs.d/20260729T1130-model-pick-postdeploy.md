---
run_at: 2026-07-29T11:30:00+09:00
session: ai/claude/feature-0003-model-pick-postdeploy
scope: POST-DEPLOY 라이브 실증 — model-pick-early-cid (PR #1032 → main bc920534 → 배포 11:08:44 KST)
verdict: PASS
---

### Run (2026-07-29 11:30) — model-pick-early-cid POST-DEPLOY — **Environment: Windows-browser**

#### 1. 대상

선행 cycle `20260728T1911-model-pick-early-cid` 가 배포 후 잔여로 남긴 PB-0008 실측을 이행한다.
검증 명제는 코드가 아니라 **실행 결과**다 — "[새 대화 → 모델 sonnet 선택 → 첨부파일 업로드 → 전송]
시나리오가 배포본에서 실제로 sonnet 으로 실행되는가". 정본은 화면이 아니라
`agent_runtime.llm_usage.model` + `kv model:<acct>` 행이다(선행 cycle 이 못박은 기준).

**이 Run 이 필요했던 직접 계기**: 사용자가 완료 보고 후 "이전과 동일하게 폴백된다"고 재보고했다.
그러나 라이브 대조 결과 그 재현은 **배포 이전 세션**이었다(§4). 따라서 본 Run 은 (a) 재보고의
시각 귀속을 확정하고 (b) 배포본에서의 실제 동작을 사용자 손을 빌리지 않고 직접 실증한다.

#### 2. Environment

- Bridge: `relay` @ `http://172.26.144.1:9223` (`doctor` → `ok: true`, Chrome/150.0.7871.115)
- Browser: Windows Chrome/150.0.7871.115 (실제 Windows 창 — WSL headless 아님)
- URL: `https://112.185.196.20/` (Windows hosts 에 `mysql-ai.company.local` 미등록 → 사용자 지정 IP 경로)
- 계정: `WEB_BOOTSTRAP_ADMIN_USERNAME`(.env) — 사용자 계정 가장 없이 검증 전용 세션(사용자 승인)
- 배포본: web-a/web-b `StartedAt=2026-07-29T02:08:44Z`(= 11:08:44 KST) · edge `/healthz`
  `git_commit=36618965` · 서빙 자산 `app.js?v=7529ce4ce347` 에 `_adoptComposerModelPickToConv`(2 호출 +
  정의) · `_modelSelectionSilentlyDropped`(정의 + 분기) **총 4 심볼 baked** 확인

#### 3. 계측 (관측 채널을 먼저 고정)

화면 표시는 이 결함에서 **신뢰할 수 없는 채널**이다(무음 강등의 정의 자체가 "화면은 맞고 실행이 다름").
그래서 판정 채널을 3중으로 깔고 시작했다:

1. `window.fetch` wrap — `/api/ask` 요청 **본문 원문** 캡처(`model` 필드 존부가 결함의 직접 지문)
2. `showToast` wrap — 무음 강등 감지 경보(C lever)의 발동/미발동 기록
3. 전역 `state` 스냅샷 — 각 단계 직후 `activeConversationId` / `_modelPickedForConvId` /
   `selectedModel` / `pendingSentinel`

#### 4. 사용자 재보고의 시각 귀속 (선결 사실)

| 사건 | 시각(KST) | 근거 |
|---|---|---|
| 재현 대화 `…2211841a`(`SQL 파일 리뷰 동의`) 첫 user 전송 | **10:33:48** | `core_messages` id 5883 |
| 수정 배포 완료(web 재기동) | **11:08:44** | 컨테이너 `StartedAt` |
| 배포 후 신규 대화·첨부 | **0건** (11:05~11:29) | `core_conversations` / `core_attachments` |

→ 재보고된 재현은 배포보다 **35분 앞선** 구자산 세션이다. 배포 후 사용자 조작 흔적이 전무하므로
"수정본에서 재현됐다"는 해석은 성립하지 않는다.

**대조군이 원 진단을 오히려 강화한다**: 같은 오전 같은 구버전에서 `…a8b43197`(10:30, 첨부 5건)은
**sonnet 정상 실행**, `…2211841a`(10:33, 첨부 1건)만 haiku 강등. 즉 "첨부가 있으면 무조건 깨진다"가
아니라 **선택 → 첨부 순서**일 때만 발현한다 — 선행 cycle 이 특정한 경로(`_modelPickedForConvId=""`
상태에서 early-cid 발급)와 정확히 일치한다.

#### 5. 시나리오 전 구간 관측 (배포본)

| # | 조작 | 관측 | 판정 |
|---|---|---|---|
| 1 | `#newConversationBtn` 클릭 | `pending=true` · `sentinel=__pending___1785292099416_c9my8a` · `selectedModel=null` · `pickedFor=null` · 라벨 `모델: claude-haiku` | 새 대화 haiku 계약 유지 |
| 2 | 모델 `claude-sonnet-4` 선택 | `selectedModel=claude-sonnet-4` · **`pickedFor=""`** · `activeConv=""` | **결함 전제 상태 재현** — 귀속이 pending(빈 문자열) |
| 3 | `pb0008_model_persist_check.sql` 업로드 | early-cid `20260729022859-2e511059` 발급 · **`pickedFor=20260729022859-2e511059`** · `selectedModel` 보존 · `sentinel=null` | **승계 성립** (구버전이면 `""` 잔류) |
| 4 | 전송 | 캡처된 `/api/ask` body `model="claude-sonnet-4"` · `conversation_id=20260729022859-2e511059` · `reasoning_level=normal` | **동봉 확인** (구버전이면 `model` 키 부재) |
| 5 | 경보 채널 | 토스트 = 첨부 완료 · 응답 갱신 2건뿐, **무음 강등 경보 미발동** | C lever 오탐 0 |

#### 6. 정본 판정 (라이브 원장)

- `llm_usage` id **69372** — `task=agent` · `model=claude-sonnet-4` · `resolved_model=claude-sonnet-4-chat`
  → **요청 alias·해소 모델 모두 sonnet. 강등 0.**
- `llm_usage` id **69373** — `task=redteam` · `claude-sonnet-4-chat` (답변 모델 정합 유지)
- `kv(20260729022859-2e511059, model:1)` = **`claude-sonnet-4`** → 명시 선택이 KV 에 **행 생성 + 값 일치**.
  구버전 결함의 지문이 정확히 이 행의 **부재**였다.
- `core_attachments` id 624 `upload_status=uploaded` (첨부 경로 자체도 정상)

#### 7. 지문 판독 정밀화 (원 진단 서술의 보정)

선행 cycle 은 "미동봉 = `kv model:<acct>` 행 부재"로 적었다. 서버 실제 계약은 3분기다 —
`conversations.py` 는 `model_explicit` 일 때만 저장하되 **값이 세션 기본값과 같으면 빈 값으로 지운다**
(기본값에서의 이탈만 저장하는 설계, 적대 리뷰 C2).

| kv 상태 | 의미 |
|---|---|
| 행 부재 | 미동봉 (`model_explicit=False`) — 이번 결함의 지문 |
| 빈 값 행 | **기본값과 같은 모델이 명시 동봉**됨 |
| 값 있는 행 | 비-기본 모델 명시 동봉 |

재현 대화 `…2211841a` 는 두 단계가 모두 남아 있다: 10:33 첫 전송 시점 행 부재(미동봉) → 10:59:02
빈 값 행(hydration 이 선택기를 haiku 로 되돌린 뒤 이어 보낸 전송). 원 진단과 정합하며, 향후
"빈 값 행"을 미동봉으로 오독하지 않도록 여기 고정한다.

#### 8. 한계 (정직 표기)

- 본 Run 은 **직접 재현 실험 1건**이다. 관측 표본 기반 corroboration(30일 non-default 선택 대화의
  첫 요청 오전송 3/5 → 재측정)은 배포 직후 표본이 없어 다음 `/_dqa:conversation_audit` 로 이월한다.
- 검증 계정은 bootstrap admin 이다. 계정별 모델 권한(RBAC) 조합은 본 Run 의 대상이 아니다
  (선행 `model-access-rbac` cycle 이 별도로 잠근 축).
- 검증 대화(`20260729022859-2e511059`)는 증적으로 보존한다(삭제 시 원장 재확인 경로가 사라짐).
