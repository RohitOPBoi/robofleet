"""Unified Cloud AI Mode Provider Router.

Presents a provider-independent AI Mode facade backed by interchangeable protocol
adapters (OpenAI-compatible chat/responses or Anthropic-native messages).
"""

from __future__ import annotations

import os
from typing import Any

from robofleet.brain.credentials import PROVIDER_PRESETS, SecretCredentialStore, resolve_preset
from robofleet.brain.providers.anthropic import AnthropicProvider
from robofleet.brain.providers.base import LLMProviderResult, ProviderHealthStatus
from robofleet.brain.providers.openai_compatible import OpenAICompatibleProvider
from robofleet.config.models import AICloudConfig
from robofleet.contracts.brain import SituationBrief


class UnifiedAIProvider:
    """Routes Cloud AI Mode decisions to OpenAI-compatible or Anthropic adapters."""

    name: str = "ai"

    def __init__(
        self,
        cloud_config: AICloudConfig | None = None,
        credential_store: SecretCredentialStore | None = None,
    ) -> None:
        self.credential_store = credential_store or SecretCredentialStore()
        self.config = cloud_config or self._initial_cloud_config()

        self.openai_adapter = OpenAICompatibleProvider(credential_store=self.credential_store)
        self.anthropic_adapter = AnthropicProvider(credential_store=self.credential_store)
        self.last_health_status: ProviderHealthStatus | None = None
        self.apply_config(self.config)

    @staticmethod
    def _initial_cloud_config() -> AICloudConfig:
        """Backward compatibility: prefer Anthropic preset automatically if only ANTHROPIC_API_KEY is set."""
        has_openai = bool(
            os.environ.get("OPENAI_API_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("GROQ_API_KEY")
            or os.environ.get("ROBOFLEET_AI_API_KEY")
        )
        has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
        if has_anthropic and not has_openai:
            preset = PROVIDER_PRESETS["anthropic"]
            return AICloudConfig(
                provider_type="anthropic",
                provider_label=preset.label,
                api_compatibility="anthropic_messages",
                base_url=preset.default_base_url,
                model=preset.default_model,
            )
        return AICloudConfig()

    def apply_config(self, cfg: AICloudConfig) -> None:
        self.config = cfg
        self.openai_adapter.apply_config(cfg)
        self.anthropic_adapter.apply_config(cfg)

    def get_active_adapter(self) -> OpenAICompatibleProvider | AnthropicProvider:
        if (
            self.config.provider_type == "anthropic"
            or self.config.api_compatibility == "anthropic_messages"
        ):
            return self.anthropic_adapter
        return self.openai_adapter

    @property
    def current_profile_key(self) -> str:
        adapter = self.get_active_adapter()
        return getattr(adapter, "profile_key", self.config.provider_label.lower())

    def has_configured_key(self) -> bool:
        preset = resolve_preset(self.config.provider_label)
        return self.credential_store.has_key(
            self.current_profile_key,
            env_vars=preset.env_var_names,
        )

    def get_masked_key(self) -> str:
        preset = resolve_preset(self.config.provider_label)
        return self.credential_store.get_masked_key(
            self.current_profile_key,
            env_vars=preset.env_var_names,
        )

    def key_source(self) -> str:
        preset = resolve_preset(self.config.provider_label)
        return self.credential_store.key_source(
            self.current_profile_key,
            env_vars=preset.env_var_names,
        )

    @property
    def circuit_tripped(self) -> bool:
        return self.get_active_adapter().circuit_tripped

    @property
    def total_cost_usd(self) -> float:
        return self.openai_adapter.total_cost_usd + self.anthropic_adapter.total_cost_usd

    @property
    def last_error(self) -> str:
        return self.get_active_adapter().last_error

    async def test_connection(self) -> ProviderHealthStatus:
        res = await self.get_active_adapter().test_connection()
        self.last_health_status = res
        return res

    async def decide(
        self,
        brief: SituationBrief,
        specialists: list[Any] | None = None,
    ) -> LLMProviderResult:
        adapter = self.get_active_adapter()
        return await adapter.decide(brief, specialists)
