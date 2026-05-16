# AI 에이전트 작업자 가이드

당신은 Primal Codex 프로젝트의 작업자입니다.
먼저 [README](README.md)를 읽고 프로젝트에 대해 전반적인 이해를 하세요.
절대 임의로 **가정하지 마세요.**
모르는 것은 사용자에게 물어보세요.

## 작업 가이드라인
- Python은 3.11 버전입니다.
- `typer`, `fastapi` 기반 CLI, HTTP/SSE 서버입니다.
- `uv` 패키지 매니저를 사용하세요.
- 커밋은 [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)을 따르세요.
- 주석과 docstring은 [Google Python Style Guide — Comments and Docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)를 참고해 관용적인 영어 표현으로 간결하게 작성하세요.
- 프로덕션 의존성(`dependencies`)은 버전을 pin합니다 (`==`).
  - 좋음: "typer==0.25.1"
  - 나쁨: "typer>=0.25.1"
- 개발 의존성(`dependency-groups.dev`)은 compatible release를 사용합니다 (`~=`).
  - 좋음: "ruff~=0.15.13"
  - 나쁨: "ruff>=0.15.13"
- Python 파일 수정 후 아래 명령어들을 실행하세요.
  - `uv run ruff format <foo.py> <bar.py>`
  - `uv run ruff check --fix <foo.py> <bar.py>`
  - `uv run pyrefly check <foo.py> <bar.py>`
