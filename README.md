# 말씀카드

교회 설교 요약과 직접 입력한 성경 구절을 인스타그램 카드뉴스로 만드는 **네이티브 데스크톱 앱**입니다. 웹서버·브라우저 UI 없이 PySide6와 Pillow를 사용합니다.

## 일반 사용자

Windows 배포본의 `WordCard-Setup.exe`를 설치하거나 `WordCard-Windows.zip`을 풀어 `WordCard.exe`를 실행합니다. Python을 별도로 설치하지 않습니다. **현재 저장소에는 소스와 빌드 설정이 있으며, 검증된 Windows 설치본은 아직 생성하지 않았습니다.**

1. 첫 문단에 제목과 부제를 입력하고, 빈 줄로 본문을 구분합니다.
2. 템플릿과 비율을 선택한 뒤 **카드 만들기**를 누릅니다.
3. 썸네일에서 카드를 고르고 글·유형·출처를 수정합니다.
4. **PNG로 모두 저장**을 누르거나 **작업 저장**으로 나중에 이어서 작업합니다.
5. 게시하려면 [인스타 연결 안내](docs/인스타_연결_안내.md)에 따라 설정한 뒤 **인스타에 올리기**를 누릅니다.

`Ctrl+Enter`: 만들기 · `Ctrl+S`: 작업 저장 · `Ctrl+O`: 열기 · `Ctrl+N`: 새 작업

카드 만들기와 저장은 오프라인으로 동작합니다. 한 문장이 최소 글자 크기로도 한 장에 들어가지 않으면 문장에 줄바꿈을 넣도록 안내합니다. 10장을 넘는 작업도 PNG 저장은 가능하지만 게시하려면 나눠야 합니다. 수동으로 고친 카드는 작업 파일에 보관됩니다. 원문으로 **카드 만들기**를 다시 실행하면 수동 수정 대신 원문으로 카드를 다시 구성합니다.

## 개발 실행

Python 3.12 이상을 사용합니다. 개발언어를 Python으로 제한할 필요는 없지만, 이 구현은 기획서의 네이티브 UI·이미지 처리 요구에 맞는 기존 기술 선택을 유지합니다.

```sh
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m wordcard
```

글꼴 3개와 라이선스는 `fonts/`에 포함되어 있습니다. 다운로드가 제한된 환경에서도 동일한 한글 결과를 얻기 위해 기본 글꼴을 나눔고딕·나눔명조로 정하고 AGENT.md에 반영했습니다. 템플릿의 글꼴 파일명을 바꿔 다른 OFL 글꼴을 사용할 수도 있습니다.

GUI 없이 생성하기:

```sh
python -m wordcard --text 내설교.txt --output output --template light --ratio 4:5
```

글 파일은 UTF-8로 저장합니다. 실제 성경 본문은 배포하지 않습니다. `AGENT.md`의 4.1절 예시는 문단 규칙에 따라 **4장**이 되므로 개발 단계의 기존 6장 기준을 바로잡았습니다.

## 테스트

Linux/macOS에서 Make를 사용하면 다음 명령으로 설치·테스트·실행·빌드를 수행할 수 있습니다.
`requirements.txt`에는 실행 라이브러리와 테스트·빌드 도구가 모두 포함되어 있습니다.

```sh
make install PYTHON=.venv/bin/python
make test PYTHON=.venv/bin/python
make run PYTHON=.venv/bin/python
make build PYTHON=.venv/bin/python
make package PYTHON=.venv/bin/python
make clean
```

`make package`는 현재 OS용 실행 폴더를 `dist/WordCard-<OS>-<아키텍처>.tar.gz`로 묶습니다.
Linux에서 만든 파일은 Windows에서 직접 실행할 수 없습니다.

`make clean`은 `build/`, `.pytest_cache/`, 소스·테스트·패키징 폴더의 `__pycache__/`를 삭제합니다.
가상환경, `dist/` 배포본, 저장한 카드와 작업 파일은 유지합니다.

```sh
python -m pytest -q
# pytest 없는 환경에서도 엔진과 API 모의 검증 가능:
PYTHONPATH=src python -m unittest discover -s tests -v
```

실제 서비스 요청이나 게시 없이 계정 응답·업로드·게시 실패를 모의합니다. GUI 테스트는 PySide6가 있을 때만 실행합니다. Windows 빌드 환경에서는 PySide6를 설치하므로 GUI 테스트도 실행됩니다.

## Windows 배포

Windows에서 실행합니다. PyInstaller는 다른 OS의 실행 파일을 교차 빌드하지 않습니다.

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m PyInstaller --noconfirm packaging/wordcard.spec
iscc packaging/windows.iss
```

마지막 단계에는 Inno Setup 6이 필요합니다. `dist/WordCard/` 전체가 포터블 배포본이며 `dist/installer/WordCard-Setup.exe`가 설치본입니다. `.github/workflows/windows.yml`은 수동 실행 또는 버전 태그 push 시 테스트, 빌드, 설치본 200MB 제한 확인, 아티팩트 보관을 수행합니다. 이 저장소에서 워크플로를 원격 실행하지는 않았습니다.

배포 전에 깨끗한 Windows 10/11 PC에서 오프라인 실행·한글 출력·자격 증명 저장·복구를 확인해야 합니다. macOS는 해당 OS에서 PyInstaller 빌드 및 키체인 검증이 필요합니다. 서명·공증은 포함하지 않았습니다.

## 저장 위치와 게시 안정성

- Windows: `%APPDATA%/WordCard/`, macOS: `~/Library/Application Support/WordCard/`, Linux: `$XDG_DATA_HOME/WordCard/` 또는 `~/.local/share/WordCard/`
- `settings.json`: 교회 정보, 기본값, 계정 이름·번호·만료일. 토큰 및 API 키 제외.
- `recovery.wordcard`: 1분마다 임시 저장, 비정상 종료 후 복구 제안.
- `.wordcard`: 원문, 템플릿, 비율, 수정 카드, 캡션, 게시 기록.
- `publication.json`: 게시 요청 직전/이후의 결과 기록. 연결 정보는 제외.
- 액세스 토큰과 ImgBB 키: OS 자격 증명 저장소만 사용. 평문 저장소는 거부합니다.

게시 전에 PNG와 작업 사본을 새 폴더에 저장합니다. 게시 요청 전에 `pending` 기록을 저장하고, 성공하면 게시물 ID를 먼저 보관한 후 링크를 조회합니다. 최종 게시 요청은 중복 방지를 위해 자동 재시도하지 않습니다. 결과가 불확실하면 인스타 계정에서 직접 확인하도록 안내합니다. 기타 네트워크 요청은 최대 3회 시도합니다.

## 확인 현황과 제한

엔진·API 모의 테스트 결과는 [개발 검증 기록](docs/검증.md)에 기재합니다. 실제 Meta/ImgBB 게시, Windows 설치와 일반 사무용 PC 성능, 2~4주 시범 운영은 별도 검증이 필요합니다. API 버전은 `uploader.py`의 `GRAPH`에서 관리합니다. 실제 계정 검증 전에는 운영 배포로 간주하지 마세요.

## 라이선스

나눔 글꼴: NAVER, SIL OFL 1.1 (`fonts/OFL-Nanum.txt`). PySide6/Qt는 LGPLv3에 따른 동적 라이브러리 형태로 패키징합니다. 배포자는 Qt 및 다른 의존성의 라이선스 고지·소스 제공 의무를 확인해야 합니다.
