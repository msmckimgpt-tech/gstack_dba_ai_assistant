---
doc_type: ANCHOR
feature_id: feature-0007-bedrock-llm-provider
created_at: 2026-05-22T02:24:52Z
status: active
edit_policy: mixed
source_of_truth: true
---

<!--
ANCHOR.md — External Anchor Document (9번째 1급 문서)

이 문서는 기능의 "방향성 stable reference"다. AI-delegated 개발의 폐쇄 루프 문제를
방지하기 위해 외부 관점과 가정된 사용 맥락을 명시적으로 기록한다.

정책 요약 (AGENTS.md §18):
- §1~§3 (stable reference): rewrite 가능. 방향이 바뀌면 명시적으로 갱신한다.
- §4 (외부 검증 로그): append-only. source는 `human:<name>` 만 허용. AI는 §4 writer가 아님.
- Conflict Protocol: AI는 사용자 요청이 §1~§3와 충돌 시 작업을 시작하지 않고
  gstack skill 재앵커를 유도한다.
- 24h bootstrap grace: `created_at` 기준 24시간 이내면 §1~§3이 빈칸이어도 verify 통과.
-->

# ANCHOR: feature-0007 Bedrock LLM Provider

## §1. 외부 관점 요약

"왜 사용자가 자기 OpenAI 키를 입력하지 않게 만들었지? 보안이나 비용 분리 측면에서
사용자별 키가 더 안전한 패턴 아닌가?" — 본 시스템은 회사 사내 직원 전용 도구로
운영되며, 운영자가 LLM 비용을 부담하는 사내 자산 모델을 채택했다. 외부 사용자 노출이
없어서 PIPA / 외부 IP allowlist / per-user cost attribution 의 리스크가 사내
환경에서 흡수된다. 사용자가 자기 OpenAI 키를 따로 발급받아 입력해야 하는 진입
장벽이 운영 목표와 부합하지 않았고, 사내 운영자 측 단일 AWS Bedrock 자격증명을
모든 LLM 호출의 entry 로 일원화하는 것이 trust 모델과 사용자 경험 양쪽에서 자연
스러웠다. 데이터 잔류 관련: 본 cycle 의 Phase E (2026-05-21) 검증 결과 AWS
Bedrock 의 frontier ACTIVE Claude (Sonnet 4.5/4.6, Haiku 4.5) 는 모두 `global.*`
inference profile 만 제공 — region-pinned (Seoul-only) on-demand 부재. 초기 plan
의 "Seoul region 한정" 정책은 사용자 reanchor (2026-05-21) 로 **global routing
수용** 으로 완화되었다. 사내 한정 + 비-개인정보 SQL 작업 (운영 DB 의 schema 분석
중심) 가정으로 PIPA risk 낮음. 엄격 잔류가 필요한 시점에는 별 cycle 의 Provisioned
throughput 또는 별 provider (Anthropic API / Azure OpenAI Korea / on-prem) 재검토.

## §2. 대안 분기

- **Alt-A: OpenAI-compatible gateway (LiteLLM proxy) 경유 (채택).**
  페르소나: 빠른 도입을 우선하는 소규모 팀. 본 코드 베이스가 이미 `OpenAI(api_key,
  base_url)` SDK 패턴으로 동작 + Local LLM gateway 분기가 동일 모양으로 존재 →
  코드 변경 범위가 가장 작음. 안 고른 이유: N/A — 채택.

- **Alt-B: boto3 + bedrock-runtime native 직접 호출.**
  페르소나: 장기 운영하는 대규모 서비스 (latency / cost / streaming 최적화 여지
  더 큼, gateway SPOF 회피). 안 고른 이유: Anthropic Messages API / Llama
  instruction format / Nova Converse API 등 모델별 schema 가 OpenAI Chat
  Completions 와 비호환. `llm.py` 의 모든 호출 사이트에 provider abstraction
  wrapper 도입 필요 + tool use / JSON mode / streaming 분기 신설. 본 cycle 의
  코드 변경 범위가 폭주. 운영 정상화 후 hotspot 만 native 로 마이그레이션
  하는 것을 별 cycle 로 검토.

- **Alt-C: 사용자 API Vault 유지 + OpenAI 그대로.**
  페르소나: 사용자별 비용 분리 + 사용자가 자기 키 통제권 보유를 원하는 운영.
  안 고른 이유: 사용자 결정 — 사내 직원 전용 서비스라 운영자가 비용 부담이
  자연스럽고, 직원 개개인이 OpenAI 키를 발급받아 입력하는 진입 장벽이 없는 편이
  사내 도구 사용성에 적합. PIPA 가 사내 한정으로 risk 완화됨.

- **Alt-D: 하이브리드 (사용자 키 + 서비스 키 병존).**
  페르소나: 일부 power user 가 자기 키로 더 빠른 모델 사용하고 일반 사용자는
  서비스 키 사용. 안 고른 이유: 코드 분기 복잡도 ↑ + 두 trust 모델 동시 유지
  부담 + 본 사내 운영 모델에 효용 낮음. 사용자가 명시 폐기 선택.

- **Alt-E: AWS Bedrock global inference profile 수용 (실제 채택, 2026-05-21
  reanchor).** 페르소나: 모델 가용성 + frontier 품질 우선 (Sonnet 4.5/4.6,
  Haiku 4.5 의 ACTIVE inference profile 이 모두 `global.*` 만 제공). 초기 plan
  의 "Seoul region 한정" 은 Phase E 검증 시점에 ACTIVE Sonnet 의 region-pinned
  on-demand 부재로 실현 불가 판명. 사용자 reanchor 후 수용. PIPA 잔류 통제는
  사내 한정 + 비-개인정보 SQL 작업 가정으로 risk 낮음 — 엄격 잔류 필요 시
  Provisioned throughput 또는 별 provider 재검토는 별 cycle.

## §3. 가정된 사용 시나리오

사내 운영팀 신규 멤버가 본 시스템에 처음 로그인했을 때, 별도로 OpenAI 키를 발급
받거나 API Vault 탭에서 키 입력 wizard 를 수행할 필요 없이 바로 메시지 입력창에
질문을 적고 보낼 수 있다. 시스템은 운영자가 보유한 단일 AWS Bedrock 자격증명을
서비스 단에서 사용하므로, 사용자에게 "당신의 OpenAI 키를 입력하세요" 같은 진입
장벽이 없고 회사가 LLM 비용을 부담하는 사내 자산으로 인지된다. 6 개월 후 운영
비용 가시화 시 별 cycle 에서 per-user / per-role token quota 또는 model tier
gating (역할별 더 비싼 모델 허용 여부) 이 도입될 수 있지만, 본 cycle 의 사용자
경험은 "그냥 동작" 이다 — 사용자는 LLM provider 가 OpenAI 인지 Bedrock 인지
의식할 필요가 없다.

## §4. 외부 검증 로그 (append-only)

(엔트리 없음 — 일반 TASK cycle 완료 조건 아님. 본 cycle 은 plan-review 단계에서 사용자 PLAN-APPROVED 마커로 충분하며, release/milestone 검증 시점에 사용자가 직접 entry 를 append 한다. §4 는 append-only + source `human:<name>` only 이므로 AI 가 갱신하지 않는다.)
