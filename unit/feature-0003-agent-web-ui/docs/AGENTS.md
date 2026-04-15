---
doc_type: FEATURE_AGENT_POLICY
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: human-guided
source_of_truth: false
---

# Feature AI Notes

- 이 기능의 우선 문서는 루트 `../../../AGENTS.md` 이다.
- 이 기능은 `app.py`, `static/*` 등 Web UI 자산을 소유한다.
- 코어 모듈 import는 유지하되, 코어 비즈니스 로직 자체는 수정 범위가 아니다.
- Web/TLS 운영 자산은 `feature-0006-lan-proxy-access`가 소유한다.

## 8. 도메인 특화 규칙

### §8.1 UI/UX 설계 원칙 (강제)

본 프론트엔드는 실제 서비스 중인 AI 채팅 앱(ChatGPT, Claude, Linear)의 검증된 패턴을 우선 따른다.

#### 레이아웃 구조 (변경 금지)
```
[Topbar 52px]
[Sidebar 252px] | [Chat Pane]
                    [Chat Header]
                    [Access Notice / Progress Strip — 조건부]
                    [Messages — flex:1, overflow-y:auto]
                    [Composer — 하단 고정]
```
- **전체 높이는 `100vh`이며 스크롤은 `Messages` 영역에만 발생**한다.
- 카드(`.surface-card`)를 세로로 쌓아 외부 스크롤을 만드는 구조는 금지한다.

#### 공간 효율 규칙
- **eyebrow(상위 레이블), hero 영역, 마케팅 카피**를 불필요하게 추가하지 않는다.
- 섹션 제목은 해당 섹션이 **기능적으로 필수**일 때만 노출한다.
- 권한 안내, 상태 설명 등 **부가 정보는 항상 표시하지 않고 조건부(`hidden` 클래스)로 처리**한다.
- Progress strip, access notice는 실제 상태가 있을 때만 렌더링한다.

#### 입력 컴포저 규칙
- textarea는 `rows="1"` + JS 자동 높이(최대 180px) 방식을 사용한다.
- 전송 버튼은 텍스트 없는 아이콘 버튼(`.send-btn`)으로 한다.
- `Ctrl+Enter` 또는 `Cmd+Enter`로 전송할 수 있어야 한다.

#### 색상 / 토큰 규칙
- 모든 색상은 `styles.css` 상단 `:root` 토큰만 사용한다.
- 인라인 `style` 속성에 하드코딩된 색상값을 추가하지 않는다.
  - 단, 레이아웃 보조(font-size, letter-spacing 등)는 허용한다.

#### 버튼 클래스 규칙
| 용도 | 클래스 |
|------|--------|
| 주요 액션 (로그인, 저장, 전송) | `btn-primary` |
| 보조 액션 (초기화, 취소) | `btn-secondary` |
| 헤더/스트립 내 소형 액션 | `tool-btn` |
| 컴포저 전송 | `send-btn` |
| 새 대화 버튼 | `btn-new-conv` |
| 상단바 버튼 | `topbar-btn` |

#### 대화 목록 아이템 규칙
- 클래스: `conv-item` / 활성: `conv-item.is-active`
- 내부 요소: `.conv-item-title` (제목), `.conv-item-meta` (날짜 + dot)
- 상태 dot: `.conv-dot` + `.is-processing` / `.is-completed`

#### 프로필 드로어 구조 규칙
- 사이드바 하단에 아바타+이름+역할+화살표로 구성된 `.profile-trigger` 버튼을 배치한다.
- 프로필 드로어는 **계정 / 보안 / API Vault** 3탭 구조를 유지한다.
  - **계정 탭**: 권한 현황(pills), 활동 정보(생성일·로그인일·승인일), 로그아웃
  - **보안 탭**: 비밀번호 변경 폼
  - **API Vault 탭**: 모델 선택, 암호화 API 키 관리, 저장/초기화
- 탭 전환은 `data-profile-tab` / `data-profile-pane` 속성으로 JS에서 처리한다.
- 드로어 헤더에는 아바타+이름+역할이 항상 표시되어 탭 전환 시에도 계정 컨텍스트가 유지된다.

#### 탑바 구성 규칙
- 탑바에는 **전역 네비게이션**만 배치한다: 브랜드, 관리 콘솔(admin 전용).
- 계정별 설정(API Vault 등)은 탑바가 아닌 프로필 드로어 안에 배치한다.
- 탑바 버튼 수는 최소로 유지한다. 기능이 드로어 안으로 이동했으면 탑바 버튼도 함께 제거한다.

#### 인증 상태 전환 규칙
- 로그아웃 시: 열려 있는 드로어를 먼저 닫은 뒤 인증 화면으로 전환한다.
- 로그아웃 시: 로그인·회원가입 폼의 값과 오류 메시지를 초기화하고 로그인 탭으로 복귀한다.
- 회원가입 완료/실패 여부와 무관하게 로그아웃 시점에 폼 상태를 깨끗하게 비워야 한다.

### §8.2 검증 정책 (강제)

> **Web UI 변경사항은 실제 브라우저 화면으로 검증**해야 최종 완료로 처리한다.
> `curl` API 테스트 또는 정적 HTML 확인만으로는 검증을 완료한 것으로 인정하지 않는다.

#### 필수 검증 항목
1. **로그인** — 인증 화면에서 폼 제출 후 워크스페이스 전환 확인
2. **레이아웃** — 전체 화면이 스크롤 없이 한 화면에 담기는지 확인 (1280×720 기준)
3. **대화 선택** — 사이드바 아이템 클릭 시 메시지 영역 갱신 확인
4. **컴포저** — 텍스트 입력 시 textarea 자동 높이 확인
5. **프로필 드로어** — 탭 전환(계정/보안/API Vault)이 정상 동작하는지 확인
6. **로그아웃** — 드로어가 닫히고 인증 화면으로 복귀, 폼이 초기화된 상태 확인

#### 브라우저 검증 절차
```
1. POST /session → session_id 획득
2. POST /goto { url: "https://web:8000", ignore_https_errors: true }
3. 시나리오별 조작 (type / click / eval)
4. POST /screenshot → 이미지 Read 도구로 시각 확인
```

## 9. 환경변수 정책

- `ENABLE_WEB_TLS=1` + 인증서 파일이 있으면 HTTPS, 없으면 HTTP로 기동한다.
- 브라우저 컨테이너에서 접근 시 `https://web:8000` + `ignore_https_errors: true` 사용.

## 10. 절대 금지사항

- 외부 스크롤을 유발하는 수직 카드 적층 구조 추가
- 항상 표시되는 마케팅 카피 / 장황한 설명 텍스트 추가
- 인라인 하드코딩 색상값 사용
- CSS 변수 이름 임의 추가/변경 (`:root` 토큰 확장은 ADR 필요)
- 기존 `.btn-primary` 등 버튼 클래스를 파괴적으로 재정의
- 구 클래스명(`conversation-item`, `auth-overlay`, `page-shell` 등) 재도입
- 계정별 설정(API Vault 등)을 탑바에 배치 — 프로필 드로어 탭으로만 구성
- 드로어/모달을 열어둔 채 인증 상태를 전환 — 전환 전 반드시 닫기
- 탭 구조 없이 정보를 드로어 단일 스크롤에 누적 — 카테고리별 탭 분리 필수
