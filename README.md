# WordCard · 말씀카드

> 설교 요약과 성경 구절을 붙여넣으면 인스타그램 카드뉴스를 만들고, 교회 계정에 바로 게시하는 데스크톱 앱

![WordCard로 만든 카드 예시](docs/미리보기.png)

교회 미디어 담당자는 매주 설교 말씀을 카드뉴스로 만들어 올립니다. 디자인 툴로 장마다 작업하면 시간이 오래 걸리고, 담당자가 바뀔 때마다 계정의 디자인 톤도 달라집니다.
**WordCard**에서는 글을 붙여넣고 버튼을 한 번 누르면, 교회 템플릿에 맞춘 카드가 여러 장 만들어지고 인스타그램에 캐러셀로 바로 게시됩니다.

- **네이티브 데스크톱 앱:** PySide6(Qt)로 만들었고, 웹서버나 브라우저 UI를 쓰지 않습니다.
- **오프라인 동작:** 카드 생성과 저장은 인터넷 없이 됩니다. 네트워크는 게시할 때만 씁니다.
- **공식 API만 사용:** Instagram API with Instagram Login만 쓰며, 계정 비밀번호를 받지 않습니다.

## 주요 기능

| 기능 | 설명 |
|------|------|
| 자동 카드 분할 | 빈 줄로 문단을 나누고 표지·본문·성경 구절·마무리 카드를 자동으로 판정합니다. 문장 중간에서 끊지 않고 다음 카드로 넘깁니다 |
| 성경 장절 인식 | 66권 이름과 약칭을 인식합니다. `요 3:16`, `요한복음 3:16-18`, `시편 23편 1절` 같은 표기를 구절 카드로 분류하고 출처를 따로 배치합니다 |
| 한글 조판 | 어절 단위로 줄을 바꾸고, 줄 앞에 문장부호가 오지 않게 합니다. 글자 크기를 자동으로 맞추고 80px 안전 여백을 둡니다 |
| 템플릿 | 밝은·어두운·따뜻한 톤 3종을 제공하고, 4:5(1080×1350)와 1:1(1080×1080) 비율을 지원합니다. 템플릿은 JSON과 이미지 폴더로 추가할 수 있습니다 |
| 미리보기·편집 | 썸네일에서 카드별로 글·유형·출처를 고칠 수 있습니다. 미리보기와 저장된 PNG는 픽셀 단위로 같습니다 |
| 인스타 게시 | 1장은 단일 이미지, 2~10장은 캐러셀로 게시하고 캡션·해시태그를 검증합니다. 게시 한도를 확인하고, 게시가 끝나면 게시물 링크를 보여 줍니다 |
| 안전한 작업 | 1분마다 자동으로 임시 저장하고 비정상 종료 후 복구합니다. 게시 전 PNG를 로컬에 백업하고, 같은 작업을 다시 게시하려 하면 확인합니다 |

## 사용 흐름

```
제목과 본문 붙여넣기 → [카드 만들기] → 카드 확인·수정 → [PNG로 모두 저장] 또는 [인스타에 올리기]
```

입력 예시 ([docs/사용_예시.txt](docs/사용_예시.txt)):

```
감사로 시작하는 한 주
2026년 10월 4일 | 교회 미디어팀

하루를 돌아보며 감사한 일을 적어 보세요.

여기에 사용자가 직접 준비한 성경 구절을 입력합니다.
(요한복음 3:16)

이번 한 주도 서로 격려하며 함께 걸어갑시다.
```

첫 문단은 표지, 장절 표기가 있는 문단은 성경 구절 카드, 마지막 문단은 마무리 카드가 됩니다.
단축키: `Ctrl+Enter` 만들기 · `Ctrl+S` 저장 · `Ctrl+O` 열기 · `Ctrl+N` 새 작업

## 빠른 시작

Python 3.12 이상이 필요합니다.

```sh
git clone https://github.com/sorrychoe/wordcard.git
cd wordcard
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m wordcard
```

GUI 없이 명령줄에서 PNG를 만들 수도 있습니다.

```sh
python -m wordcard --text docs/사용_예시.txt --output output --template light --ratio 4:5
```

자세한 설치 방법과 문제 해결은 [설치 및 실행 안내](docs/설치_및_실행_안내.md)를, 인스타 계정 연결은 [인스타 연결 안내](docs/인스타_연결_안내.md)를 참고하세요.

## 기술 스택

| 영역 | 선택 |
|------|------|
| 언어 | Python 3.12+ |
| GUI | PySide6 (Qt 6) |
| 이미지 생성 | Pillow |
| 비밀 저장 | keyring (Windows 자격 증명 관리자, macOS 키체인, Linux Secret Service) |
| HTTP | 표준 라이브러리 `urllib` (추가 의존성 없음) |
| 패키징 | PyInstaller, Inno Setup, GitHub Actions |
| 테스트 | pytest / unittest |

## 구조

```
텍스트 ─▶ parser ─▶ layout ─▶ renderer ─▶ UI 미리보기 / exporter (PNG)
          문단·유형·장절  줄바꿈·크기·분할  Pillow 합성        │
                                                             ▼
                                         uploader: JPEG 변환 → ImgBB 임시 호스팅
                                                  → 컨테이너 생성 → 상태 확인 → 게시
```

```
src/wordcard/
├── parser.py        # 텍스트 → 카드 목록, 카드 유형 판정
├── bible_books.py   # 성경 66권 이름·약칭, 장절 정규식
├── layout.py        # 한글 줄바꿈, 글자 크기 맞춤, 카드 분할
├── renderer.py      # 카드 이미지 합성 (미리보기와 저장에서 공용)
├── exporter.py      # PNG 일괄 저장
├── uploader.py      # Instagram Graph API 게시, 토큰 갱신
├── project.py       # .wordcard 작업 파일
├── settings.py      # 설정, OS 자격 증명 저장소
└── ui/              # 메인 창, 설정 창, 업로드 창
templates/           # light · dark · warm (template.json + 이미지)
fonts/               # 나눔고딕·나눔명조 (SIL OFL)
```

parser, layout, renderer는 GUI와 분리된 순수 로직입니다. 그래서 GUI 없이 테스트할 수 있고, 명령줄에서도 그대로 씁니다.

## 설계 포인트

- **게시 중 문제가 생겨도 결과가 꼬이지 않습니다.** 최종 게시 요청은 자동으로 다시 보내지 않아 중복 게시를 막습니다. 게시 직전에 `pending` 기록을 남기고, 성공하면 게시물 ID부터 저장합니다. 응답이 끊겨 결과가 불확실하면 사용자에게 인스타 계정을 직접 확인하도록 안내합니다.
- **비밀 정보는 OS 저장소에만 둡니다.** 액세스 토큰과 ImgBB 키는 OS 자격 증명 저장소에만 저장합니다. 평문으로만 저장되는 백엔드는 거부하고, 로그·설정 파일·작업 파일에는 남기지 않습니다.
- **토큰을 자동으로 갱신합니다.** 장기 토큰이 만료되기 7일 전부터, 프로그램을 실행할 때 갱신합니다.
- **이미지를 공개 URL로 임시 호스팅합니다.** 인스타 API가 공개 URL에서만 이미지를 가져가기 때문입니다. ImgBB에 1시간 뒤 만료되도록 올리며, 호스팅 함수 하나만 바꾸면 자체 저장소로 교체할 수 있습니다.
- **성경 본문은 넣지 않았습니다.** 번역본 저작권 때문에 본문 데이터는 포함하지 않았고, 책 이름과 장절 인식만 제공합니다.

## 테스트

```sh
make test PYTHON=.venv/bin/python
# 또는
python -m pytest -q
PYTHONPATH=src python -m unittest discover -s tests -v   # pytest 없이 실행
```

테스트는 텍스트 분석, 출력 크기와 여백, 미리보기와 저장 결과의 픽셀 일치, 작업 파일, 모의 API 게시 시나리오, GUI, docstring을 확인합니다. 실제 서비스에는 요청하지 않습니다. 자세한 내용은 [검증 현황](docs/검증.md)에 있습니다.

## 빌드와 배포

| 명령 | 내용 |
|------|------|
| `make build` | PyInstaller로 현재 OS용 실행 폴더를 `dist/WordCard/`에 만듭니다 |
| `make package` | 실행 폴더를 `dist/WordCard-<OS>-<아키텍처>.tar.gz`로 묶습니다 |
| `make clean` | 빌드 캐시를 지웁니다 (가상환경과 배포본은 유지) |

Windows 설치본은 Windows에서 만들어야 합니다. PyInstaller는 다른 OS용으로 교차 빌드하지 않습니다.

```powershell
python -m PyInstaller --noconfirm packaging/wordcard.spec
iscc packaging/windows.iss      # Inno Setup 6 → dist/installer/WordCard-Setup.exe
```

`.github/workflows/windows.yml`은 `main` 브랜치나 `v*` 태그에 push하거나 수동으로 실행하면 돌아갑니다. 테스트, 빌드, 설치본 200MB 제한 확인을 거쳐 아티팩트를 업로드합니다.

## 데이터 저장 위치

| 데이터 | 위치 |
|------|------|
| 설정·임시 저장 | Windows `%APPDATA%/WordCard/` · macOS `~/Library/Application Support/WordCard/` · Linux `~/.local/share/WordCard/` |
| 작업 파일 `.wordcard` | 사용자가 선택한 폴더 (원문, 템플릿, 비율, 수정한 카드, 캡션, 게시 기록) |
| 토큰·API 키 | OS 자격 증명 저장소 |

## 현재 상태

카드 생성·편집·저장 엔진과 GUI는 자동 테스트와 Linux 빌드로 검증했습니다. 아래 항목은 아직 확인하지 않았으니, 운영 계정에 쓰기 전에 테스트 계정으로 먼저 확인하세요.

- macOS 키체인 연동

## 기획 문서

요구사항, 화면 설계, 기술 결정은 [AGENT.md](AGENT.md)에 정리되어 있습니다.

## 라이선스

- 소스 코드: [MIT License](LICENSE)
- 나눔 글꼴: NAVER, SIL Open Font License 1.1 ([fonts/OFL-Nanum.txt](fonts/OFL-Nanum.txt))
- PySide6/Qt: LGPLv3 (동적 라이브러리로 패키징). 배포하는 사람은 Qt와 다른 의존성의 라이선스 고지 의무를 확인해야 합니다.
