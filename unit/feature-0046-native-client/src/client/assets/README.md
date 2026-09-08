# DQA 아이콘

DQA(Database Query Assistant)의 질문(Q)과 데이터 2행을 한 심볼로 결합했다. 마상소프트·마상게임즈 공식 심볼의 각진 사선과 시안→보라→마젠타 흐름을 참고하고, 어두운 바탕과 단순한 면으로 업무 도구에 맞게 절제했다.

## 정본과 변환

- `dqa.png`: 내장 imagegen 도구가 반환한 최종 원본(1254×1254, RGB, 2026-09-08).
- `dqa.ico`: 원본에서 크기/형식만 변환한 Windows 자산. 16, 20, 24, 32, 40, 48, 64, 128, 256px 프레임.
- 원본은 불투명 정사각형이다. alpha나 투명 모서리를 전제하지 않는다.
- 이전 남색·청록 초안은 사용자 추가 요청(마상 브랜드 방향)에 따라 최종본으로 교체했다.
- 사용자 확정 범위: 아이콘·설치 파일 우선. 웹 화면 색상 테마는 이번 요청에 포함되지 않는다.

재변환(Pillow 12.2.0 사용, 앱 런타임 의존성은 아님):

```bash
python3 unit/feature-0046-native-client/src/scripts/export_icon.py
```

16~128px은 32-bit DIB, 256px은 PNG 프레임이다. 전체 프레임을 PNG로 쓰면 실측 Tk 8.6에서 첫 16px 프레임을 32px로 확대해 창 아이콘이 흐려졌다. 동일 원본·동일 크기의 DIB로 바꾸면 트레이·Tk·WebView2의 실제 픽셀이 해당 프레임과 일치한다. `export_icon.py`가 이 혼합 인코딩을 재현한다.

## 생성 근거

2026-09-08 공식 웹페이지와 실제 이미지 파일을 확인했다. 아래 특징은 이미지 관찰에 따른 디자인 해석이며 공식 CI 색상 규정으로 주장하지 않는다.

- [마상소프트 공식 사이트](https://www.masangsoft.com/), [심볼 이미지](https://www.masangsoft.com/_CompanyHomepage/ko/images/logo_main.png): 각진 사선 연결, 시안·보라·마젠타 색상 흐름.
- [마상게임즈 공식 사이트](https://www.masanggames.com/), [파비콘](https://www.masanggames.com/_Support/pages/favicon.ico): 작은 크기의 동일 계열 각진 심볼.
- 공식 참조 이미지는 생성 입력으로 사용했으며 회사 로고 자체를 앱의 로고라고 배포하지 않는다.

최종 내장 imagegen 편집 프롬프트(핵심):

> Create a final DQA desktop icon aligned with Masangsoft/Masanggames. The previous DQA icon is the redesign target; official parent-brand images are references. A bespoke angular Q-like enclosure with two data strokes, not the literal corporate M. Thick open six-sided ring with clipped corners and a short diagonal lower-right tail. Large unbroken surfaces and enough gap for 16px. One restrained cyan–violet–magenta transition. Opaque full-bleed near-black charcoal-plum square. No glow, bevels, reflection, extrusion, text or wordmark. Sophisticated enterprise tool.

## 적용 경로

`branding.ICON_PATH`를 Tk·WebView2·트레이가 사용하고 PyInstaller는 ICO만 런타임 데이터로 동봉한다. EXE 리소스에도 같은 ICO가 들어간다. 시작 메뉴·바탕화면·스킴·프로그램 제거 항목은 이 EXE를 참조한다. 설치기는 `SetupIconFile`로 같은 ICO를 Setup/Uninstall에 적용한다.

브라우저 폴백(`--app`으로 별도 브라우저 실행)은 브라우저가 창·작업표시줄 아이콘을 관리한다. 이 경로의 웹 favicon·사이트 색상 테마는 이번 범위에 포함되지 않는다.

근거: [PyInstaller 데이터 경로](https://pyinstaller.org/en/stable/runtime-information.html), [Inno Setup 아이콘](https://jrsoftware.org/ishelp/topic_setup_setupiconfile.htm). pywebview Windows `icon=`은 빌드 머신의 `webview/platforms/winforms.py`에서 `_state['icon']` → `System.Drawing.Icon` 배선을 확인했다.
