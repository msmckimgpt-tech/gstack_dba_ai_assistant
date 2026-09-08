# DQA 아이콘

DQA(Database Query Assistant)의 질문(Q)과 데이터 2행을 한 심볼로 결합했다. 마상소프트·마상게임즈 공식 심볼의 각진 사선과 시안→보라→마젠타 흐름을 참고하고, 배경 없는 단순한 면으로 업무 도구에 맞게 절제했다.

## 정본과 변환

- `dqa.svg`: 배경 도형이 없는 벡터 정본(1024×1024). 기존 생성 디자인의 각진 Q·두 데이터 행을 정리했다.
- `dqa.png`: SVG를 CairoSVG로 렌더링한 1024×1024 RGBA. 심볼 밖과 내부 빈 공간은 실제 alpha=0이다.
- `dqa.ico`: 16/20/24/32/40/48/64/128/256px. 모든 프레임의 투명 알파를 보존한다.
- 사용자 후속 요청으로 불투명 정사각형을 폐기했다. 내장 imagegen의 배경 추출 결과가 체크무늬 RGB여서 채택하지 않았고, 사용자가 **SVG로 정리해 투명 PNG/ICO 변환**을 명시 승인했다.
- 웹 화면 색상 테마는 변경하지 않는다.

재생성(CairoSVG·Pillow는 자산 제작용이며 앱 런타임 의존성에 추가하지 않는다):

```bash
python3 -m venv /tmp/dqa-icon-build
/tmp/dqa-icon-build/bin/pip install CairoSVG Pillow
/tmp/dqa-icon-build/bin/python unit/feature-0046-native-client/src/scripts/export_icon.py
```

16~128px은 32-bit DIB, 256px은 PNG 프레임이다. 전체 프레임을 PNG로 쓰면 실측 Tk 8.6에서 첫 16px 프레임을 32px로 확대해 창 아이콘이 흐려졌다. 동일 원본·동일 크기의 DIB로 바꾸면 트레이·Tk·WebView2의 실제 픽셀이 해당 프레임과 일치한다. `export_icon.py`가 이 혼합 인코딩을 재현한다.

## 생성 근거

2026-09-08 공식 웹페이지와 실제 이미지 파일을 확인했다. 아래 특징은 이미지 관찰에 따른 디자인 해석이며 공식 CI 색상 규정으로 주장하지 않는다.

- [마상소프트 공식 사이트](https://www.masangsoft.com/), [심볼 이미지](https://www.masangsoft.com/_CompanyHomepage/ko/images/logo_main.png): 각진 사선 연결, 시안·보라·마젠타 색상 흐름.
- [마상게임즈 공식 사이트](https://www.masanggames.com/), [파비콘](https://www.masanggames.com/_Support/pages/favicon.ico): 작은 크기의 동일 계열 각진 심볼.
- 공식 참조 이미지는 생성 입력으로 사용했으며 회사 로고 자체를 앱의 로고라고 배포하지 않는다.

이전 1.1.2의 내장 imagegen 디자인 프롬프트(형태·색상 근거이며 불투명 배경은 폐기):

> Create a final DQA desktop icon aligned with Masangsoft/Masanggames. The previous DQA icon is the redesign target; official parent-brand images are references. A bespoke angular Q-like enclosure with two data strokes, not the literal corporate M. Thick open six-sided ring with clipped corners and a short diagonal lower-right tail. Large unbroken surfaces and enough gap for 16px. One restrained cyan–violet–magenta transition. Opaque full-bleed near-black charcoal-plum square. No glow, bevels, reflection, extrusion, text or wordmark. Sophisticated enterprise tool.

투명 추출 시도 프롬프트(핵심):

> Change only the background. Remove the dark background around and inside the Q and data bars. Return a genuinely transparent PNG with alpha 0 outside the colored symbol. Preserve the geometry and cyan–violet–magenta colors. No checkerboard, square background, shadow or new outline.

이 시도는 실제 alpha가 없어 배포하지 않았다. 최종 자산은 사용자 승인에 따른 SVG 정리·렌더링 산출물이다.

## 적용 경로

`branding.ICON_PATH`를 Tk·WebView2·트레이가 사용하고 PyInstaller는 ICO만 런타임 데이터로 동봉한다. EXE 리소스에도 같은 ICO가 들어간다. 시작 메뉴·바탕화면·스킴·프로그램 제거 항목은 이 EXE를 참조한다. 설치기는 `SetupIconFile`로 같은 ICO를 Setup/Uninstall에 적용한다.

웹의 6개 HTML 진입점도 같은 SVG/ICO를 favicon으로 연결하고, 로그인·사이드바·빈 대화·관리 사이드바의 4개 로고 이미지는 같은 SVG를 사용한다. `export_icon.py`가 `feature-0003`의 `static/brand` 복사본까지 갱신한다. 브라우저 폴백(`--app`)은 이 사이트 아이콘을 사용할 수 있으며 창 그룹은 브라우저가 관리한다. 사이트 색상 테마는 유지한다.

근거: [PyInstaller 데이터 경로](https://pyinstaller.org/en/stable/runtime-information.html), [Inno Setup 아이콘](https://jrsoftware.org/ishelp/topic_setup_setupiconfile.htm). pywebview Windows `icon=`은 빌드 머신의 `webview/platforms/winforms.py`에서 `_state['icon']` → `System.Drawing.Icon` 배선을 확인했다.

작업 표시줄은 창의 Icon만으로 검증하지 않는다. `branding.APP_USER_MODEL_ID`를 UI 생성 전에 설정하고 창의 ID·재실행 명령·표시 이름·아이콘 경로를 지정한다. 설치기가 만드는 앱 바로가기도 같은 ID를 쓴다. 재실행 명령에는 이전 실행의 인자나 연결 토큰을 저장하지 않는다. [Microsoft 앱 식별자](https://learn.microsoft.com/en-us/windows/win32/shell/appids), [재실행 아이콘](https://learn.microsoft.com/en-us/windows/win32/properties/props-system-appusermodel-relaunchiconresource).
