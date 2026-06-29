# feature-0012 src — (cross-cut)

P5b(app.py router 분할)의 코드는 **feature-0003-agent-web-ui** 에 거주한다(분할 대상이 feature-0003 의
`src/app.py` 이므로). 본 feature 는 추적 cycle 이며 자체 src 없음. router 추출물은
`unit/feature-0003-agent-web-ui/src/routers/` + `src/web_context.py`(후속)에 생성된다.
