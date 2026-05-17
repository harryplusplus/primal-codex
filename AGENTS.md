# AI 에이전트 작업자 가이드

당신은 Primal Codex 프로젝트의 작업자입니다.
먼저 [README](README.md)를 읽고 프로젝트에 대해 전반적인 이해를 하세요.
절대 임의로 **가정하지 마세요.**
모르는 것은 사용자에게 물어보세요.

## 작업 가이드라인
- Python 버전은 3.11입니다.
- `typer`, `fastapi` 기반의 CLI, HTTP/SSE 서버입니다.
- 주석과 docstring은 [Google Python Style Guide — Comments and Docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)를 참고해 관용적인 영어 표현으로 간결하게 작성하세요.
- 타입 명세는 1급입니다.
  - `typing.Any`대신에 아래와 같은 타입을 사용하세요.
    - 외부로 직렬화하는 경우에는 `TypedDict`를 사용하세요.
    - 외부로부터 역직렬화하는 경우에는 `pydantic`을 사용하세요.
    - 코드 내부에서만 사용하는 경우에는 `@dataclass`를 사용하세요.
- Python 파일 수정 후 아래 명령어들을 실행하세요.
  - `uv run ruff format <foo.py> <bar.py>`
  - `uv run ruff check --fix <foo.py> <bar.py>`
  - `uv run pyrefly check <foo.py> <bar.py>`
- 커밋은 [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)을 따르세요.
- Codex 클라이언트의 동작을 확인하려면 `external/codex` 경로에서 소스 코드를 확인하세요.
- `codex` CLI를 실행할 때는 `CODEX_HOME=<tmp/codex> RUST_LOG=debug codex` 명령어를 사용하세요.
- `primal-codex` CLI를 실행할 때는 `PRIMAL_CODEX_HOME=<tmp/primal-codex> CODEX_HOME=<tmp/codex> uv run primal-codex` 명령어를 사용하세요.

## 의존성 관리
- `uv` 패키지 매니저를 사용하세요.
- 프로덕션 의존성(`dependencies`)은 버전을 pin합니다 (`==`).
  - 좋음: "typer==0.25.1"
  - 나쁨: "typer>=0.25.1"
- 개발 의존성(`dependency-groups.dev`)은 compatible release를 사용합니다 (`~=`).
  - 좋음: "ruff~=0.15.13"
  - 나쁨: "ruff>=0.15.13"

## 테스트
- `uv run pytest`로 실행합니다.

### 유닛 테스트
- `typer.testing.CliRunner`, `fastapi.testclient.TestClient`를 사용합니다.
- 공유 fixture는 `tests/conftest.py`에 정의되어 있습니다.

### 통합 테스트
- `tests/test_integration.py` — `CROF_API_KEY` 없으면 `pytest.fail()`로 실패합니다.
- 텍스트, 이미지, 도구 호출, 멀티턴 등 기능이 추가될 때마다 시나리오 클래스를 추가하세요.
