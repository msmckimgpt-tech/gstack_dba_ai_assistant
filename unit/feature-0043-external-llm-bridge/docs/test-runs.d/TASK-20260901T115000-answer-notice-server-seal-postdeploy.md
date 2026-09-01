# TASK-20260901T115000-answer-notice-server-seal — POST-DEPLOY 라이브 실측

- **일시**: 2026-09-01 13:13~13:16 KST
- **배포본**: `7fb2dca4` (web-a/b · ask/insight-worker · ops-scheduler · ext-tool-mcp-a/b 전 서비스 이미지 태그 일치)
- **대상 계약**: AC-20260901T115000-answer-notice-seal-1~6

## 0. 배포 도달 확인

| 축 | 값 |
|---|---|
| `docker exec repo-web-a-1 printenv GIT_COMMIT` | `7fb2dca4` |
| 배포본에 `_strip_model_notice` | 3건 (상수 + 정의 + 호출) |
| 엣지 무중단(`caddy` 의 `no upstreams available`, 최근 10분) | **0건** |

## 1. 배포본 함수 직접 구동 (컨테이너 안)

라이브 컨테이너의 `/app/web/routers/ai_tools.py` 에서 상수·함수를 그대로 떼어 실행:

| 입력 | 고지 잔존 | 미반영 보존 | 본문 보존 |
|---|---|---|---|
| `> 이 답변은 claude 의 모델 opus · 추론등급 xhigh 로 생성했습니다.` | **NO** | — | YES |
| `> 이 답변은 claude 의 추론등급 xhigh 로 생성했습니다.` | **NO** | — | YES |
| `> 참고: 요청하신 모델 opus 은(는) … 기본 설정으로 답했습니다.` | NO | **YES** | YES |
| 닫히지 않은 ` ```sql ` 펜스 뒤의 고지 | **NO** | — | YES |
| `이 답변은 논리 모델 기준으로 생성했습니다.` (유사 문장) | **YES**(보존이 정답) | — | YES |

배포본 상수 실측: `_NOTICE_TAIL_LINES=8` · `_NOTICE_MAX_LINE=300`.

## 2. 서버 봉인 실증 — 고지가 붙은 답변을 실제로 제출

러너를 거치지 않고 **REST 도구 표면으로 직접** 제출했다(러너 밖 등록형 AI 가 자기 판단으로
같은 문장을 쓰는 경우의 재현). `open_task` → `submit_answer`, `title` 에도 같은 문구.

- task `t_AOi-ME_X__-oYUxk` · 제출 응답 `{"recorded":true}`
- 라이브 MySQL `agent_memory.webaitasks` 대조:

```
고지잔존=NO    미반영보존=YES    본문보존=YES    AnswerBytes=145
```

제출한 본문에는 고지 1줄 + 미반영 고지 1줄이 함께 있었다. **둘이 갈렸다** — 봉인은 고지만
걷고 미반영 사실은 남겼다.

## 3. 실 브리지 왕복 — 웹 대화 → 러너 → 답변

로그인 세션(`bootstrap_admin`)으로 `/api/ask` 에 **모델 `sonnet` · 추론등급 `high` 를 명시
지정**해 질문했다. 지정이 반영되면 종전 러너는 정확히 고지를 붙이던 조건이다.

| task | RequestedModel | ReasoningLevel | 고지 잔존 |
|---|---|---|---|
| **#86** (이번 검증, 배포 후) | `sonnet` | `high` | **NO** |
| #83 (배포 전, 대조군) | `opus` | `xhigh` | YES |

같은 조건에서 배포 전 답변에는 고지가 있고 배포 후에는 없다.

## 4. 러너 설치본 정합

- 실행 중이던 러너는 12:47 시점에 `--resume` 만으로 기동을 시도하다 토큰 부재로 종료돼 있었다
  (`bridge.log`: `토큰이 필요합니다`). 12:40:45 로그에는 **지문 불일치 경고**가 남아 있었다.
- 설치본을 배포본으로 교체 — `md5 4c8851ca…` 로 **양쪽 일치**, `py_compile` OK.
- 새 토큰(`/api/ai/connect/token`, 세션 결합)으로 `--check` → `연결 정상 / 사용할 AI: claude`
  확인 후 상주 기동(PID 1147300). 검증용 임시 토큰 파일 2개는 폐기했다(러너는 메모리 보유).

## 정리

배포·러너 정합·서버 봉인·실 왕복 4축 모두 실측했다. 남은 트레이드오프는 「답변 말미 8줄 안에
이 문장을 예시로 두면 지워진다」이며 조정 지점은 `_NOTICE_TAIL_LINES` 상수 하나다.

이미 저장된 과거 답변 7건(08-31~09-01)은 **편집하지 않았다** — 확정 답변 불변(사용자 결정).
