# Primal Codex

Enables Codex to work with the OpenAI Chat Completions API (`/chat/completions`).

## 목적

Codex 클라이언트(CLI, TUI, Desktop app)와 OpenAI compatible API를 제공하는 오픈소스 모델 클라우드 제공자를 연동하기 위한 리버스 프록시 서버입니다.
Codex에서 이제는 [OpenAI Chat Completions](https://developers.openai.com/api/reference/chat-completions/overview)를 지원하지 않습니다.
오직 [OpenAI Responses API](https://developers.openai.com/api/reference/responses/overview)만 지원합니다.
그래서 Codex와 오픈소스 모델 클라우드 제공자를 연동하기 위해서는 Responses API를 OpenAI compatible API로 변환하는 계층이 필요합니다.
이 프로젝트는 그 변환 계층을 담당합니다.

## 설계

### 구성 파일

구성 파일의 경로는 환경변수 `PRIMAL_CODEX_HOME`가 빈 값이 아니라면 `$PRIMAL_CODEX_HOME/config.toml`, 
빈 값이라면 `~/.primal-codex/config.toml`입니다.

구성 파일은 TOML 포맷입니다. 
멀티 제공자를 지원하기 위해서 제공자는 여러개 등록될 수 있습니다.
Codex 클라이언트로 전달되는 모델 `slug`값은 `<provider_id>/<model_id>`입니다.

아래 블록은 Crof 제공자의 GLM-5.1 Precision 모델을 사용하는 예제입니다.
이 경우 Codex 클라이언트는 `crof/glm-5.1-precision`이라는 모델 정보를 받습니다.

```toml
[server]
host = "127.0.0.1"
port = 8010

[providers.crof]
base_url = "https://crof.ai/v1"
env_key = "CROF_API_KEY"

[providers.crof.models."glm-5.1-precision"]
supported_reasoning_levels = [{effort="medium"}, {effort="high"}]
input_modalities = ["text"]
```

### 명령어

#### 구성 파일 초기화

`primal-codex init` 명령어를 사용해 빈 구성파일을 생성합니다.
빈 구성파일에는 주석을 uncomment하거나 보고 작성할 수 있도록 충분한 정보를 제공해야 합니다.

#### Codex 설정 업데이트

`primal-codex codex` 명령어를 사용해 Codex 설정을 업데이트합니다.

`CODEX_HOME` 환경변수가 빈 값이 아니라면 `$CODEX_HOME/config.toml`을 읽습니다.
빈 값이라면 `~/.codex/config.toml`을 읽습니다.

`model_catalog_json`값이 있다면 지웁니다. 이 설정이 없어야 Codex 클라이언트가 Primal Codex 서버의 /models 엔드포인트에서 모델 목록을 조회합니다.
`model_provider`값을 `primal-codex`로 설정합니다.
`model_providers.primal-codex.name`을 `primal-codex`로 설정합니다. 필수 프로퍼티입니다.
`model_providers.primal-codex.base_url`을 `http://<config.server.host>:<config.server.port>`로 설정합니다.

변경 사항이 있다면, 기존 파일을 `<path>.bak`으로 백업한 후 신규 파일을 씁니다.

#### 서버 실행

`primal-codex serve` 명령어를 사용해 Primal Codex 서버를 실행합니다.

### 서버 API

#### 모델 목록 조회

```
Codex 클라이언트 -> GET /models -> 로드된 구성 파일 내용을 기반으로 모델 목록 반환
```

구성 파일은 멀티 제공자 목록을 지원하기 때문에 Codex로 모델 목록을 내려줄 때,
모델의 slug를 `<provider_id>/<model_id>` 형태로 전달합니다.

구성 파일에 모델의 정의되지 않은 필드들은 서버가 적절히 기본값을 전달합니다.
Primal Codex의 구성 파일 -> 서버에서 일부 조건에 따라서 기본값을 설정 -> Codex 클라이언트에서 API 요청의 응답에 기본값을 채움.
이 순서로 모델 정보의 값이 채워집니다.
어떤 필드를 구성할 수 있는지는 Primal Codex 구성 파일의 주석을 확인해주세요.

어떤 모델 정보가 Codex로 전달되는지 확인을 원하는 경우,
`http://<config.server.host>:<config.server.port>/models`를 요청해보세요.

#### LLM 요청

```
Codex 클라이언트 <-> Responses API (SSE /responses) <-> Primal Codex 서버 <-> OpenAI compatible API (SSE /chat/completions)
```

Responses API 요청을 Chat Completions 요청으로 변환해 제공자로 전달합니다.
Codex가 준 모델 slug는 `<provider_id>/<model_id>`로 분해해 올바른 제공자의 API를 호출합니다.

#### (TODO) OpenAPI

`<base_url>/openapi.json`과 같은 기능이 있어야 합니다. FastAPI 기능 확인을 해야합니다.
