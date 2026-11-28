"""Secure Backend Credential Store and Secret Redaction Utilities.

Credentials live strictly in backend process memory or environment variables:
- Never serialized into ScenarioConfig / /api/config/effective.
- Never persisted to browser storage or source files.
- Never emitted into logs, error messages, URLs, or LLM prompts.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderPreset:
    """Metadata and reliable endpoint defaults for a cloud API provider."""

    id: str
    label: str
    provider_type: str  # "openai_compatible" | "anthropic" | "custom"
    api_compatibility: str  # "openai_chat" | "openai_responses" | "anthropic_messages"
    default_base_url: str
    default_model: str
    suggested_models: tuple[str, ...]
    env_var_names: tuple[str, ...]


PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "openai": ProviderPreset(
        id="openai",
        label="OpenAI",
        provider_type="openai_compatible",
        api_compatibility="openai_chat",
        default_base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        suggested_models=("gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"),
        env_var_names=("OPENAI_API_KEY", "ROBOFLEET_AI_API_KEY"),
    ),
    "openrouter": ProviderPreset(
        id="openrouter",
        label="OpenRouter",
        provider_type="openai_compatible",
        api_compatibility="openai_chat",
        default_base_url="https://openrouter.ai/api/v1",
        default_model="openai/gpt-4o-mini",
        suggested_models=(
            "openai/gpt-4o-mini",
            "anthropic/claude-3.5-sonnet",
            "qwen/qwen-2.5-72b-instruct",
            "meta-llama/llama-3.3-70b-instruct",
        ),
        env_var_names=("OPENROUTER_API_KEY", "ROBOFLEET_AI_API_KEY"),
    ),
    "groq": ProviderPreset(
        id="groq",
        label="Groq",
        provider_type="openai_compatible",
        api_compatibility="openai_chat",
        default_base_url="https://api.groq.com/openai/v1",
        default_model="llama-3.3-70b-versatile",
        suggested_models=("llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3-32b"),
        env_var_names=("GROQ_API_KEY", "ROBOFLEET_AI_API_KEY"),
    ),
    "together": ProviderPreset(
        id="together",
        label="Together AI",
        provider_type="openai_compatible",
        api_compatibility="openai_chat",
        default_base_url="https://api.together.xyz/v1",
        default_model="Qwen/Qwen2.5-7B-Instruct-Turbo",
        suggested_models=(
            "Qwen/Qwen2.5-7B-Instruct-Turbo",
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        ),
        env_var_names=("TOGETHER_API_KEY", "ROBOFLEET_AI_API_KEY"),
    ),
    "fireworks": ProviderPreset(
        id="fireworks",
        label="Fireworks AI",
        provider_type="openai_compatible",
        api_compatibility="openai_chat",
        default_base_url="https://api.fireworks.ai/inference/v1",
        default_model="accounts/fireworks/models/llama-v3p3-70b-instruct",
        suggested_models=(
            "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "accounts/fireworks/models/qwen2p5-72b-instruct",
        ),
        env_var_names=("FIREWORKS_API_KEY", "ROBOFLEET_AI_API_KEY"),
    ),
    "deepseek": ProviderPreset(
        id="deepseek",
        label="DeepSeek",
        provider_type="openai_compatible",
        api_compatibility="openai_chat",
        default_base_url="https://api.deepseek.com",
        default_model="deepseek-chat",
        suggested_models=("deepseek-chat", "deepseek-reasoner"),
        env_var_names=("DEEPSEEK_API_KEY", "ROBOFLEET_AI_API_KEY"),
    ),
    "anthropic": ProviderPreset(
        id="anthropic",
        label="Anthropic",
        provider_type="anthropic",
        api_compatibility="anthropic_messages",
        default_base_url="https://api.anthropic.com",
        default_model="claude-3-5-sonnet-20241022",
        suggested_models=(
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-7-sonnet-20250219",
        ),
        env_var_names=("ANTHROPIC_API_KEY", "ROBOFLEET_AI_API_KEY"),
    ),
    "custom": ProviderPreset(
        id="custom",
        label="Custom Endpoint",
        provider_type="custom",
        api_compatibility="openai_chat",
        default_base_url="",
        default_model="",
        suggested_models=(),
        env_var_names=("ROBOFLEET_AI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"),
    ),
}

_MASK_MIN_LEN = 8
_MASK_EDGE_CHARS = 4

_KEY_REGEXES: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-ant-api\d*-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-or-v1-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"gsk_[A-Za-z0-9_\-]{12,}"),
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{8,}", re.IGNORECASE),
    re.compile(r"(x-api-key['\":=\s]+)[A-Za-z0-9._\-]{8,}", re.IGNORECASE),
)


class SecretCredentialStore:
    """In-memory credential vault keyed by provider profile with env-var fallback."""

    def __init__(self) -> None:
        self._keys: dict[str, str] = {}

    @staticmethod
    def _normalize_profile(profile_key: str) -> str:
        return profile_key.strip().lower()

    def set_key(self, profile_key: str, api_key: str) -> None:
        norm = self._normalize_profile(profile_key)
        cleaned = api_key.strip()
        if cleaned:
            self._keys[norm] = cleaned

    def clear_key(self, profile_key: str) -> None:
        norm = self._normalize_profile(profile_key)
        self._keys.pop(norm, None)

    def clear_all(self) -> None:
        self._keys.clear()

    def get_key(
        self,
        profile_key: str,
        env_vars: tuple[str, ...] = ("ROBOFLEET_AI_API_KEY",),
        explicit_fallback: str | None = None,
    ) -> str:
        norm = self._normalize_profile(profile_key)
        if norm in self._keys and self._keys[norm]:
            return self._keys[norm]
        if explicit_fallback and explicit_fallback.strip():
            return explicit_fallback.strip()
        for env_name in env_vars:
            val = os.environ.get(env_name, "").strip()
            if val:
                return val
        return ""

    def has_key(
        self,
        profile_key: str,
        env_vars: tuple[str, ...] = ("ROBOFLEET_AI_API_KEY",),
        explicit_fallback: str | None = None,
    ) -> bool:
        return bool(self.get_key(profile_key, env_vars=env_vars, explicit_fallback=explicit_fallback))

    def key_source(
        self,
        profile_key: str,
        env_vars: tuple[str, ...] = ("ROBOFLEET_AI_API_KEY",),
    ) -> str:
        norm = self._normalize_profile(profile_key)
        if norm in self._keys and self._keys[norm]:
            return "session"
        for env_name in env_vars:
            if os.environ.get(env_name, "").strip():
                return f"env:{env_name}"
        return "unset"

    @staticmethod
    def mask_secret(secret: str) -> str:
        if not secret:
            return ""
        if len(secret) <= _MASK_MIN_LEN:
            return "*" * len(secret)
        return f"{secret[:_MASK_EDGE_CHARS]}...{secret[-_MASK_EDGE_CHARS:]}"

    def get_masked_key(
        self,
        profile_key: str,
        env_vars: tuple[str, ...] = ("ROBOFLEET_AI_API_KEY",),
        explicit_fallback: str | None = None,
    ) -> str:
        key = self.get_key(profile_key, env_vars=env_vars, explicit_fallback=explicit_fallback)
        return self.mask_secret(key)

    def redact(self, text: str) -> str:
        """Remove any stored keys or common key tokens from text before logging or returning errors."""
        if not text:
            return text
        sanitized = text
        for stored_key in self._keys.values():
            if stored_key and len(stored_key) >= _MASK_EDGE_CHARS:
                sanitized = sanitized.replace(stored_key, "[REDACTED_KEY]")
        for env_val in (
            os.environ.get("ANTHROPIC_API_KEY", ""),
            os.environ.get("OPENAI_API_KEY", ""),
            os.environ.get("OPENROUTER_API_KEY", ""),
            os.environ.get("GROQ_API_KEY", ""),
            os.environ.get("TOGETHER_API_KEY", ""),
            os.environ.get("FIREWORKS_API_KEY", ""),
            os.environ.get("DEEPSEEK_API_KEY", ""),
            os.environ.get("ROBOFLEET_AI_API_KEY", ""),
        ):
            clean_val = env_val.strip()
            if clean_val and len(clean_val) >= _MASK_EDGE_CHARS:
                sanitized = sanitized.replace(clean_val, "[REDACTED_KEY]")
        for pattern in _KEY_REGEXES:
            sanitized = pattern.sub("[REDACTED_KEY]", sanitized)
        return sanitized


class SecretRedactingFilter(logging.Filter):
    """Logging filter that prevents stored credentials from reaching log handlers."""

    def __init__(self, store: SecretCredentialStore) -> None:
        super().__init__()
        self._store = store

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._store.redact(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    self._store.redact(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: self._store.redact(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
        return True


def resolve_preset(provider_label_or_id: str) -> ProviderPreset:
    """Resolve preset metadata by ID or label, defaulting to custom."""
    key = provider_label_or_id.strip().lower().replace(" ", "_")
    for preset in PROVIDER_PRESETS.values():
        if preset.id == key or preset.label.lower().replace(" ", "_") == key:
            return preset
    return PROVIDER_PRESETS["custom"]


def redact_text_with_known_secrets(text: str, extra_secrets: tuple[str, ...] = ()) -> str:
    """Standalone helper to scrub API secrets from diagnostic strings."""
    store = SecretCredentialStore()
    for idx, sec in enumerate(extra_secrets):
        if sec:
            store.set_key(f"tmp_{idx}", sec)
    return store.redact(text)
