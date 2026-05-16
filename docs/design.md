# Primal Codex 설계

## 목적

Codex 클라이언트(CLI, TUI, Desktop app)와 OpenAI compatible API를 제공하는 오픈소스 모델 클라우드 제공자를 연동하기 위한 리버스 프록시 서버입니다.
Codex에서 이제는 [OpenAI Chat Completions](https://developers.openai.com/api/reference/chat-completions/overview)를 지원하지 않습니다.
오직 [OpenAI Responses API](https://developers.openai.com/api/reference/responses/overview)만 지원합니다.
그래서 Codex와 오픈소스 모델 클라우드 제공자를 연동하기 위해서는 Responses API를 OpenAI compatible API로 변환하는 계층이 필요합니다.
이 프로젝트는 그 변환 계층을 담당합니다.

## 설계

### 구성 파일

구성 파일 ($PRIMAL_CODEX_HOME/config.toml)

```toml
[server]
host = "127.0.0.1"
port = 8010

[providers.crof]
base_url = "https://crof.ai/v1"
env_key = "CROF_API_KEY"

[providers.crof.models."glm-5.1-precision"]
supported_reasoning_levels = [{effort="medium"}, {effort="high"}]
```

### 모델 목록 조회

```
Codex 클라이언트 -> GET /models 요청 -> Primal Codex 서버
```



```
Codex <-> Responses API (SSE /responses) <-> Primal Codex 서버 <-> OpenAI compatible API (SSE /chat/completions)
```