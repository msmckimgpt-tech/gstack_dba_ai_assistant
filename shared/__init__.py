"""shared — 두 feature(agent-core·web-ui)와 컨테이너가 공유하는 저결합 공통 모듈.

feature-0011-shared-extraction P5a Step 1 플러밍: `modules/` 안에 흩어진 cross-feature
공통 코드를 단일 import 네임스페이스(`shared.*`)로 모은다. 컨테이너는 Dockerfile 의
`COPY shared /app/shared`, 테스트는 Makefile PYTHONPATH 의 `/work/shared` 로 본 패키지를
두 feature·격리 컨테이너 양쪽에서 import 가능하게 한다 (회귀 0 게이트: `make test`).
"""
