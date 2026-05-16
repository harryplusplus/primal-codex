""""""

import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def codex() -> None:
    """Codex 구성 파일의 `model_provider` 관련 구성을 업데이트합니다.

    기본 경로는 `$CODEX_HOME/config.toml`입니다.
    환경변수 `CODEX_HOME` (fallback: `~/.codex`)을 존중합니다.
    `$CODEX_HOME/config.toml` (fallback: `~/.codex/config.toml`)
    """


@app.command()
def serve() -> None:
    """Primal Codex API 서버를 실행합니다."""


def main() -> None:
    """"""
    app()


if __name__ == "__main__":
    main()
