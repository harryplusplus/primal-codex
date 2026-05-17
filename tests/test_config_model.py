"""Tests for config loading and model enrichment.

Covers:
1. ``load_config()`` — file-based config loading with defaults.
2. ``ServerConfig.url()`` — URL string generation from host/port.
3. ``ProviderConfig.resolve_api_key()`` — environment variable lookup.
4. ``enrich_model()`` — single model enrichment (slug, fallbacks, field mapping).
5. ``compute_model_map()`` — multi-model merge and provider-indexed nested map.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from primal_codex.config import (
    PrimalCodexConfig,
    ProviderConfig,
    ServerConfig,
    compute_model_map,
    load_config,
)
from primal_codex.models import (
    ConfigShellToolType,
    InputModality,
    ModelConfig,
    ModelVisibility,
    ReasoningEffort,
    ReasoningEffortPreset,
    TruncationMode,
    TruncationPolicyConfig,
    Verbosity,
    enrich_model,
)
from primal_codex.paths import PRIMAL_CODEX_HOME_ENV_KEY

if TYPE_CHECKING:
    import pytest


def _write_primal_config(path: Path, content: str) -> Path:
    """Write a Primal Codex config file and return its path."""
    config_path = path / "config.toml"
    config_path.write_text(content, encoding="utf-8")
    return config_path


class TestLoadConfig:
    """Tests for ``load_config()``."""

    def test_no_file_returns_defaults(
        self, tmp_primal_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Return default config when no file exists."""
        monkeypatch.setenv(PRIMAL_CODEX_HOME_ENV_KEY, str(tmp_primal_home))
        cfg = load_config()
        assert cfg.server.host == "127.0.0.1"
        assert cfg.server.port == 8010
        assert cfg.providers == {}

    def test_empty_config_returns_defaults(
        self, tmp_primal_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Leave defaults unchanged for an empty config."""
        _write_primal_config(tmp_primal_home, "")
        monkeypatch.setenv(PRIMAL_CODEX_HOME_ENV_KEY, str(tmp_primal_home))
        cfg = load_config()
        assert cfg.server.host == "127.0.0.1"
        assert cfg.server.port == 8010

    def test_custom_server(
        self, tmp_primal_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Read custom host and port from config."""
        _write_primal_config(
            tmp_primal_home, "[server]\nhost = '0.0.0.0'\nport = 9999\n"
        )
        monkeypatch.setenv(PRIMAL_CODEX_HOME_ENV_KEY, str(tmp_primal_home))
        cfg = load_config()
        assert cfg.server.host == "0.0.0.0"
        assert cfg.server.port == 9999

    def test_providers_parsed(
        self, tmp_primal_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Parse providers and their models from config."""
        _write_primal_config(
            tmp_primal_home,
            (
                "[providers.crof]\n"
                'base_url = "https://crof.ai/v1"\n'
                'env_key = "CROF_API_KEY"\n'
                "\n"
                '[providers.crof.models."glm-5.1-precision"]\n'
                "priority = 10\n"
            ),
        )
        monkeypatch.setenv(PRIMAL_CODEX_HOME_ENV_KEY, str(tmp_primal_home))
        cfg = load_config()
        assert "crof" in cfg.providers
        assert cfg.providers["crof"].base_url == "https://crof.ai/v1"
        assert cfg.providers["crof"].env_key == "CROF_API_KEY"
        assert "glm-5.1-precision" in cfg.providers["crof"].models

    def test_unknown_keys_ignored(
        self, tmp_primal_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Silently ignore unknown top-level keys."""
        _write_primal_config(
            tmp_primal_home, 'unknown_key = "something"\n[server]\nport = 8080\n'
        )
        monkeypatch.setenv(PRIMAL_CODEX_HOME_ENV_KEY, str(tmp_primal_home))
        cfg = load_config()
        assert cfg.server.port == 8080


class TestServerConfig:
    """Tests for ``ServerConfig.url()``."""

    def test_default_url(self) -> None:
        """Return ``http://127.0.0.1:8010`` with default values."""
        cfg = ServerConfig()
        assert cfg.url() == "http://127.0.0.1:8010"

    def test_custom_host(self) -> None:
        """Use the custom host in the URL."""
        cfg = ServerConfig(host="0.0.0.0")
        assert cfg.url() == "http://0.0.0.0:8010"

    def test_custom_port(self) -> None:
        """Use the custom port in the URL."""
        cfg = ServerConfig(port=9999)
        assert cfg.url() == "http://127.0.0.1:9999"

    def test_custom_host_and_port(self) -> None:
        """Use both custom host and port in the URL."""
        cfg = ServerConfig(host="0.0.0.0", port=443)
        assert cfg.url() == "http://0.0.0.0:443"


class TestProviderConfig:
    """Tests for ``ProviderConfig.resolve_api_key()``."""

    def test_no_env_key_returns_none(self) -> None:
        """Return None when env_key is not set."""
        provider = ProviderConfig(base_url="https://example.com")
        assert provider.resolve_api_key() is None

    def test_missing_env_var_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Return None when the configured env var is unset."""
        monkeypatch.delenv("MY_TEST_KEY", raising=False)
        provider = ProviderConfig(base_url="https://example.com", env_key="MY_TEST_KEY")
        assert provider.resolve_api_key() is None

    def test_env_var_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Read the env var value when set."""
        monkeypatch.setenv("MY_TEST_KEY", "sk-secret")
        provider = ProviderConfig(base_url="https://example.com", env_key="MY_TEST_KEY")
        assert provider.resolve_api_key() == "sk-secret"


class TestEnrichModel:
    """Tests for ``enrich_model()``."""

    def test_slug_format(self) -> None:
        """Format slug as ``{provider_id}/{model_id}``."""
        info = enrich_model(
            model_id="my-model",
            provider_id="my-provider",
            cfg=ModelConfig(),
            default_base_instructions="You are a helpful assistant.",
        )
        assert info.slug == "my-provider/my-model"

    def test_display_name_fallback_to_slug(self) -> None:
        """Fall back to slug when display_name is not set."""
        info = enrich_model(
            model_id="my-model",
            provider_id="p",
            cfg=ModelConfig(),
            default_base_instructions="You are a helpful assistant.",
        )
        assert info.display_name == "p/my-model"

    def test_display_name_from_config(self) -> None:
        """Use display_name from config when set."""
        info = enrich_model(
            model_id="my-model",
            provider_id="p",
            cfg=ModelConfig(display_name="My Custom Name"),
            default_base_instructions="You are a helpful assistant.",
        )
        assert info.display_name == "My Custom Name"

    def test_base_instructions_fallback(self) -> None:
        """Use the default prompt when base_instructions is not set."""
        info = enrich_model(
            model_id="m",
            provider_id="p",
            cfg=ModelConfig(),
            default_base_instructions="Default prompt here.",
        )
        assert info.base_instructions == "Default prompt here."

    def test_base_instructions_from_config(self) -> None:
        """Prefer base_instructions from config over the default."""
        info = enrich_model(
            model_id="m",
            provider_id="p",
            cfg=ModelConfig(base_instructions="Custom prompt."),
            default_base_instructions="Default prompt here.",
        )
        assert info.base_instructions == "Custom prompt."

    def test_description_passthrough(self) -> None:
        """Pass description through as-is (allow None)."""
        info = enrich_model(
            model_id="m",
            provider_id="p",
            cfg=ModelConfig(description="A great model."),
            default_base_instructions="...",
        )
        assert info.description == "A great model."

    def test_description_none(self) -> None:
        """Keep description as None when not configured."""
        info = enrich_model(
            model_id="m",
            provider_id="p",
            cfg=ModelConfig(),
            default_base_instructions="...",
        )
        assert info.description is None

    def test_shell_type_default(self) -> None:
        """Default shell_type to ``shell_command``."""
        info = enrich_model(
            model_id="m",
            provider_id="p",
            cfg=ModelConfig(),
            default_base_instructions="...",
        )
        assert info.shell_type == ConfigShellToolType.shell_command

    def test_shell_type_custom(self) -> None:
        """Override shell_type from config."""
        cfg = ModelConfig(shell_type=ConfigShellToolType.disabled)
        info = enrich_model(
            model_id="m", provider_id="p", cfg=cfg, default_base_instructions="..."
        )
        assert info.shell_type == ConfigShellToolType.disabled

    def test_visibility_default(self) -> None:
        """Default visibility to ``list``."""
        info = enrich_model(
            model_id="m",
            provider_id="p",
            cfg=ModelConfig(),
            default_base_instructions="...",
        )
        assert info.visibility == ModelVisibility.list

    def test_priority_default(self) -> None:
        """Default priority to 0."""
        info = enrich_model(
            model_id="m",
            provider_id="p",
            cfg=ModelConfig(),
            default_base_instructions="...",
        )
        assert info.priority == 0

    def test_priority_custom(self) -> None:
        """Propagate priority from config."""
        cfg = ModelConfig(priority=50)
        info = enrich_model(
            model_id="m", provider_id="p", cfg=cfg, default_base_instructions="..."
        )
        assert info.priority == 50

    def test_default_supported_in_api(self) -> None:
        """Default supported_in_api to True."""
        info = enrich_model(
            model_id="m",
            provider_id="p",
            cfg=ModelConfig(),
            default_base_instructions="...",
        )
        assert info.supported_in_api is True

    def test_supports_reasoning_summaries_default(self) -> None:
        """Default supports_reasoning_summaries to False."""
        info = enrich_model(
            model_id="m",
            provider_id="p",
            cfg=ModelConfig(),
            default_base_instructions="...",
        )
        assert info.supports_reasoning_summaries is False

    def test_input_modalities_default(self) -> None:
        """Include both text and image in default input_modalities."""
        info = enrich_model(
            model_id="m",
            provider_id="p",
            cfg=ModelConfig(),
            default_base_instructions="...",
        )
        assert InputModality.text in info.input_modalities
        assert InputModality.image in info.input_modalities

    def test_input_modalities_custom(self) -> None:
        """Restrict input_modalities to text only from config."""
        cfg = ModelConfig(input_modalities=[InputModality.text])
        info = enrich_model(
            model_id="m", provider_id="p", cfg=cfg, default_base_instructions="..."
        )
        assert info.input_modalities == [InputModality.text]

    def test_truncation_policy_default(self) -> None:
        """Default truncation policy to tokens with 10_000 limit."""
        info = enrich_model(
            model_id="m",
            provider_id="p",
            cfg=ModelConfig(),
            default_base_instructions="...",
        )
        assert info.truncation_policy.mode == TruncationMode.tokens
        assert info.truncation_policy.limit == 10_000

    def test_truncation_policy_custom(self) -> None:
        """Propagate truncation policy from config."""
        cfg = ModelConfig(
            truncation_policy=TruncationPolicyConfig(
                mode=TruncationMode.bytes, limit=5_000
            )
        )
        info = enrich_model(
            model_id="m", provider_id="p", cfg=cfg, default_base_instructions="..."
        )
        assert info.truncation_policy.mode == TruncationMode.bytes
        assert info.truncation_policy.limit == 5_000

    def test_supports_search_tool_default(self) -> None:
        """Default supports_search_tool to False."""
        info = enrich_model(
            model_id="m",
            provider_id="p",
            cfg=ModelConfig(),
            default_base_instructions="...",
        )
        assert info.supports_search_tool is False

    def test_context_window_none(self) -> None:
        """Keep context_window as None when not configured."""
        info = enrich_model(
            model_id="m",
            provider_id="p",
            cfg=ModelConfig(),
            default_base_instructions="...",
        )
        assert info.context_window is None

    def test_context_window_custom(self) -> None:
        """Propagate context_window from config."""
        cfg = ModelConfig(context_window=128_000)
        info = enrich_model(
            model_id="m", provider_id="p", cfg=cfg, default_base_instructions="..."
        )
        assert info.context_window == 128_000

    def test_effective_context_window_percent_default(self) -> None:
        """Default effective_context_window_percent to 95."""
        info = enrich_model(
            model_id="m",
            provider_id="p",
            cfg=ModelConfig(),
            default_base_instructions="...",
        )
        assert info.effective_context_window_percent == 95

    def test_default_verbosity_none(self) -> None:
        """Keep default_verbosity as None when not configured."""
        info = enrich_model(
            model_id="m",
            provider_id="p",
            cfg=ModelConfig(),
            default_base_instructions="...",
        )
        assert info.default_verbosity is None

    def test_default_verbosity_custom(self) -> None:
        """Propagate default_verbosity from config."""
        cfg = ModelConfig(default_verbosity=Verbosity.high)
        info = enrich_model(
            model_id="m", provider_id="p", cfg=cfg, default_base_instructions="..."
        )
        assert info.default_verbosity == Verbosity.high

    def test_supported_reasoning_levels_default_empty(self) -> None:
        """Default supported_reasoning_levels to an empty list."""
        info = enrich_model(
            model_id="m",
            provider_id="p",
            cfg=ModelConfig(),
            default_base_instructions="...",
        )
        assert info.supported_reasoning_levels == []

    def test_supported_reasoning_levels_custom(self) -> None:
        """Propagate reasoning levels from config."""
        cfg = ModelConfig(
            supported_reasoning_levels=[
                ReasoningEffortPreset(effort=ReasoningEffort.medium),
                ReasoningEffortPreset(effort=ReasoningEffort.high),
            ]
        )
        info = enrich_model(
            model_id="m", provider_id="p", cfg=cfg, default_base_instructions="..."
        )
        assert len(info.supported_reasoning_levels) == 2
        assert info.supported_reasoning_levels[0].effort == ReasoningEffort.medium
        assert info.supported_reasoning_levels[1].effort == ReasoningEffort.high


class TestComputeModelMap:
    """Tests for ``compute_model_map()``."""

    def test_empty_providers_returns_empty(self) -> None:
        """Return an empty dict when no providers are configured."""
        config = PrimalCodexConfig()
        model_map = compute_model_map(config)
        assert model_map == {}

    def test_single_provider_single_model(self) -> None:
        """Yield one entry for a single provider with one model."""
        config = PrimalCodexConfig(
            providers={
                "crof": ProviderConfig(
                    base_url="https://crof.ai/v1",
                    models={
                        "glm-5": ModelConfig(display_name="GLM-5"),
                    },
                ),
            }
        )
        model_map = compute_model_map(config)
        assert set(model_map) == {"crof"}
        assert set(model_map["crof"]) == {"glm-5"}
        info = model_map["crof"]["glm-5"]
        assert info.slug == "crof/glm-5"
        assert info.display_name == "GLM-5"

    def test_multiple_providers(self) -> None:
        """Include models from all providers."""
        config = PrimalCodexConfig(
            providers={
                "a": ProviderConfig(
                    base_url="https://a.ai",
                    models={"m1": ModelConfig(), "m2": ModelConfig()},
                ),
                "b": ProviderConfig(
                    base_url="https://b.ai", models={"m3": ModelConfig()}
                ),
            }
        )
        model_map = compute_model_map(config)
        assert set(model_map) == {"a", "b"}
        assert set(model_map["a"]) == {"m1", "m2"}
        assert set(model_map["b"]) == {"m3"}
        assert model_map["a"]["m1"].slug == "a/m1"
        assert model_map["a"]["m2"].slug == "a/m2"
        assert model_map["b"]["m3"].slug == "b/m3"

    def test_priority_preserved(self) -> None:
        """Preserve priority from config in each ModelInfo."""
        config = PrimalCodexConfig(
            providers={
                "p": ProviderConfig(
                    base_url="https://p.ai",
                    models={
                        "low": ModelConfig(priority=100),
                        "high": ModelConfig(priority=10),
                        "mid": ModelConfig(priority=50),
                    },
                ),
            }
        )
        model_map = compute_model_map(config)
        assert model_map["p"]["low"].priority == 100
        assert model_map["p"]["high"].priority == 10
        assert model_map["p"]["mid"].priority == 50

    def test_base_instructions_comes_from_prompt_file(self) -> None:
        """Read base_instructions from the prompt.md file when not overridden."""
        config = PrimalCodexConfig(
            providers={
                "p": ProviderConfig(
                    base_url="https://p.ai",
                    models={"m": ModelConfig()},
                ),
            }
        )
        model_map = compute_model_map(config)
        prompt = (
            Path(__file__).resolve().parents[1] / "assets" / "prompt.md"
        ).read_text(encoding="utf-8")
        assert model_map["p"]["m"].base_instructions == prompt
