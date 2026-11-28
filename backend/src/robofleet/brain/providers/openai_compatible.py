"""Universal OpenAI-Compatible Cloud API Provider (AI Mode).

Supports OpenAI, OpenRouter, Groq, Together AI, Fireworks AI, DeepSeek,
and custom OpenAI-compatible chat-completions or responses endpoints.
"""

from __future__ import annotations

import logging
import time
from http import HTTPStatus
from typing import Any, Literal

import httpx
from robofleet.brain.credentials import SecretCredentialStore, resolve_preset
from robofleet.brain.prompt_builder import build_decision_messages
from robofleet.brain.providers.base import (
    CircuitBreakerMixin,
    LLMProviderResult,
    ProviderHealthStatus,
    build_explicit_fallback_result,
    collect_and_arbitrate_specialists,
)
from robofleet.brain.providers.heuristic import HeuristicProvider
from robofleet.brain.providers.validation import parse_and_validate_llm_response
from robofleet.config.models import AICloudConfig
from robofleet.contracts.brain import SituationBrief

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(CircuitBreakerMixin):
    """Cloud API adapter for OpenAI-compatible chat-completions and responses APIs."""

    name: str = "ai"

    def __init__(
        self,
        api_key: str | None = None,
        provider_label: str = "OpenAI",
        api_compatibility: Literal["openai_chat", "openai_responses"] = "openai_chat",
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        organization_id: str | None = None,
        project_id: str | None = None,
        timeout_s: float = 10.0,
        max_tokens: int = 800,
        temperature: float = 0.15,
        retry_count: int = 1,
        circuit_threshold: int = 3,
        circuit_cooldown_s: float = 30.0,
        fallback_policy: Literal["heuristic", "safe_wait"] = "heuristic",
        credential_store: SecretCredentialStore | None = None,
    ) -> None:
        self.provider_label = provider_label
        self.api_compatibility: Literal["openai_chat", "openai_responses"] = api_compatibility
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.model = model
        self.organization_id = organization_id
        self.project_id = project_id
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.retry_count = retry_count
        self.fallback_policy: Literal["heuristic", "safe_wait"] = fallback_policy
        self.credential_store = credential_store or SecretCredentialStore()
        self._explicit_api_key = api_key or ""
        if self._explicit_api_key:
            self.credential_store.set_key(self.profile_key, self._explicit_api_key)

        self.fallback = HeuristicProvider()
        self._init_circuit(circuit_threshold=circuit_threshold, circuit_cooldown_s=circuit_cooldown_s)

    @property
    def profile_key(self) -> str:
        return f"openai_compatible:{self.provider_label.lower().replace(' ', '_')}"

    def apply_config(self, cfg: AICloudConfig) -> None:
        self.provider_label = cfg.provider_label or "OpenAI"
        if cfg.api_compatibility in ("openai_chat", "openai_responses"):
            self.api_compatibility = cfg.api_compatibility
        self.base_url = (cfg.base_url or "https://api.openai.com/v1").rstrip("/")
        self.model = cfg.model or ""
        self.organization_id = cfg.organization_id
        self.project_id = cfg.project_id
        self.timeout_s = cfg.timeout_s
        self.max_tokens = cfg.max_tokens
        self.temperature = cfg.temperature
        self.retry_count = cfg.retry_count
        self.fallback_policy = cfg.fallback_policy
        self.circuit_threshold = cfg.circuit_threshold
        self.circuit_cooldown_s = cfg.circuit_cooldown_s

    def _resolve_api_key(self) -> str:
        preset = resolve_preset(self.provider_label)
        return self.credential_store.get_key(
            self.profile_key,
            env_vars=preset.env_var_names,
            explicit_fallback=self._explicit_api_key,
        )

    def _headers(self, api_key: str) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if self.organization_id:
            headers["OpenAI-Organization"] = self.organization_id
        if self.project_id:
            headers["OpenAI-Project"] = self.project_id
        if "openrouter" in self.base_url.lower():
            headers["X-Title"] = "RoboFleet Operations Brain"
        return headers

    def _inference_url(self) -> str:
        base = self.base_url.rstrip("/")
        if self.api_compatibility == "openai_responses":
            if base.endswith("/responses"):
                return base
            return f"{base}/responses"
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    def _models_url(self) -> str:
        base = self.base_url.rstrip("/")
        for suffix in ("/chat/completions", "/responses"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
        return f"{base}/models"

    def _build_payload(self, messages: list[dict[str, str]], use_json_mode: bool = True) -> dict[str, Any]:
        if self.api_compatibility == "openai_responses":
            payload: dict[str, Any] = {
                "model": self.model,
                "instructions": messages[0]["content"],
                "input": messages[1]["content"],
                "temperature": self.temperature,
                "max_output_tokens": self.max_tokens,
            }
            if use_json_mode:
                payload["text"] = {"format": {"type": "json_object"}}
            return payload

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if use_json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    @staticmethod
    def _extract_response_text(data: dict[str, Any], compatibility: str) -> tuple[str, int, int]:
        usage = data.get("usage", {})
        if compatibility == "openai_responses":
            p_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)))
            c_tokens = int(usage.get("output_tokens", usage.get("completion_tokens", 0)))
            text = str(data.get("output_text", "") or "")
            if not text:
                for item in data.get("output", []):
                    if isinstance(item, dict):
                        for content in item.get("content", []):
                            if isinstance(content, dict) and content.get("type") in ("output_text", "text"):
                                text += str(content.get("text", ""))
            return text, p_tokens, c_tokens

        p_tokens = int(usage.get("prompt_tokens", 0))
        c_tokens = int(usage.get("completion_tokens", 0))
        choices = data.get("choices", [])
        if choices and isinstance(choices[0], dict):
            msg = choices[0].get("message", {})
            if isinstance(msg, dict):
                return str(msg.get("content", "") or ""), p_tokens, c_tokens
        return "", p_tokens, c_tokens

    async def list_models(self, api_key: str | None = None) -> list[str]:
        """Fetch available model IDs from OpenAI-compatible /models endpoint when supported."""
        resolved_key = api_key if api_key is not None else self._resolve_api_key()
        if not self.base_url or not resolved_key:
            return []
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.get(self._models_url(), headers=self._headers(resolved_key))
            if resp.status_code != HTTPStatus.OK:
                return []
            data = resp.json()
            items = data.get("data", []) if isinstance(data, dict) else []
            return [str(m.get("id")) for m in items if isinstance(m, dict) and m.get("id")]
        except Exception:
            return []

    async def test_connection(self) -> ProviderHealthStatus:
        """Verify credentials, base URL, protocol compatibility, and target model."""
        t0 = time.perf_counter()
        if not self.base_url or not self.base_url.startswith(("http://", "https://")):
            return ProviderHealthStatus(
                ok=False,
                operating_mode="ai",
                provider_name=self.provider_label,
                model_name=self.model,
                status="error",
                message="Invalid API base URL. Must start with http:// or https://.",
            )

        if not self.model.strip():
            return ProviderHealthStatus(
                ok=False,
                operating_mode="ai",
                provider_name=self.provider_label,
                model_name="",
                status="unconfigured",
                message="Model identifier is empty. Enter a valid model name.",
            )

        api_key = self._resolve_api_key()
        if not api_key:
            return ProviderHealthStatus(
                ok=False,
                operating_mode="ai",
                provider_name=self.provider_label,
                model_name=self.model,
                status="unconfigured",
                message=f"No API key configured for {self.provider_label}.",
            )

        available_models = await self.list_models(api_key)
        test_messages = [
            {"role": "system", "content": "Return valid JSON object with key status='ok'."},
            {"role": "user", "content": "Health ping"},
        ]
        headers = self._headers(api_key)

        try:
            payload = self._build_payload(test_messages, use_json_mode=True)
            if "max_tokens" in payload:
                payload["max_tokens"] = 32
            if "max_output_tokens" in payload:
                payload["max_output_tokens"] = 32

            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(self._inference_url(), headers=headers, json=payload)
                if resp.status_code == HTTPStatus.BAD_REQUEST and "response_format" in resp.text.lower():
                    payload = self._build_payload(test_messages, use_json_mode=False)
                    if "max_tokens" in payload:
                        payload["max_tokens"] = 32
                    resp = await client.post(self._inference_url(), headers=headers, json=payload)

            latency = round((time.perf_counter() - t0) * 1000.0, 2)
            if resp.status_code == HTTPStatus.OK:
                if available_models and self.model not in available_models:
                    # Endpoint responded OK, warn only if exact list returned without match? Actually chat endpoint succeeded so model works.
                    pass
                return ProviderHealthStatus(
                    ok=True,
                    operating_mode="ai",
                    provider_name=self.provider_label,
                    model_name=self.model,
                    status="connected",
                    message=f"Connected to {self.provider_label} ({self.model}) in {latency}ms.",
                    available_models=available_models[:50],
                    latency_ms=latency,
                )

            safe_err = self.credential_store.redact(resp.text[:200])
            if resp.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                return ProviderHealthStatus(
                    ok=False,
                    operating_mode="ai",
                    provider_name=self.provider_label,
                    model_name=self.model,
                    status="error",
                    message=f"Authentication failed (HTTP {resp.status_code}). Check your {self.provider_label} API key.",
                    available_models=available_models[:50],
                    latency_ms=latency,
                )
            if resp.status_code == HTTPStatus.NOT_FOUND:
                return ProviderHealthStatus(
                    ok=False,
                    operating_mode="ai",
                    provider_name=self.provider_label,
                    model_name=self.model,
                    status="error",
                    message=f"Endpoint or model '{self.model}' not found (HTTP 404). Verify Base URL and compatibility protocol.",
                    available_models=available_models[:50],
                    latency_ms=latency,
                )
            if resp.status_code == HTTPStatus.TOO_MANY_REQUESTS:
                return ProviderHealthStatus(
                    ok=False,
                    operating_mode="ai",
                    provider_name=self.provider_label,
                    model_name=self.model,
                    status="unavailable",
                    message=f"Rate limit or quota exceeded on {self.provider_label} (HTTP 429).",
                    available_models=available_models[:50],
                    latency_ms=latency,
                )
            return ProviderHealthStatus(
                ok=False,
                operating_mode="ai",
                provider_name=self.provider_label,
                model_name=self.model,
                status="unavailable",
                message=f"{self.provider_label} returned HTTP {resp.status_code}: {safe_err}",
                available_models=available_models[:50],
                latency_ms=latency,
            )
        except Exception as exc:
            safe_exc = self.credential_store.redact(str(exc))
            return ProviderHealthStatus(
                ok=False,
                operating_mode="ai",
                provider_name=self.provider_label,
                model_name=self.model,
                status="unavailable",
                message=f"Connection error to {self.provider_label}: {safe_exc}",
                available_models=available_models[:50],
            )

    async def decide(
        self,
        brief: SituationBrief,
        specialists: list[Any] | None = None,
    ) -> LLMProviderResult:
        t0 = time.perf_counter()
        spec_proposals = collect_and_arbitrate_specialists(brief, specialists)

        if self.is_circuit_open:
            return await build_explicit_fallback_result(
                heuristic_fallback=self.fallback,
                brief=brief,
                specialists=specialists,
                operating_mode="ai",
                fallback_policy=self.fallback_policy,
                reason=f"{self.provider_label} circuit breaker open after repeated failures",
                model_name=self.model,
            )

        if not self.base_url or not self.base_url.startswith(("http://", "https://")):
            return await build_explicit_fallback_result(
                heuristic_fallback=self.fallback,
                brief=brief,
                specialists=specialists,
                operating_mode="ai",
                fallback_policy=self.fallback_policy,
                reason="Invalid API base URL configured",
                model_name=self.model,
            )

        api_key = self._resolve_api_key()
        if not api_key:
            return await build_explicit_fallback_result(
                heuristic_fallback=self.fallback,
                brief=brief,
                specialists=specialists,
                operating_mode="ai",
                fallback_policy=self.fallback_policy,
                reason=f"{self.provider_label} API key not configured",
                model_name=self.model,
            )

        messages = build_decision_messages(brief, spec_proposals)
        headers = self._headers(api_key)
        use_json_mode = True
        last_err = ""
        p_tokens_total = 0
        c_tokens_total = 0

        for attempt in range(self.retry_count + 1):
            payload = self._build_payload(messages, use_json_mode=use_json_mode)
            try:
                async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                    resp = await client.post(self._inference_url(), headers=headers, json=payload)

                if resp.status_code == HTTPStatus.BAD_REQUEST and use_json_mode and (
                    "response_format" in resp.text.lower() or "json" in resp.text.lower()
                ):
                    use_json_mode = False
                    async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                        resp = await client.post(
                            self._inference_url(),
                            headers=headers,
                            json=self._build_payload(messages, use_json_mode=False),
                        )

                if resp.status_code != HTTPStatus.OK:
                    safe_text = self.credential_store.redact(resp.text[:180])
                    last_err = f"{self.provider_label} HTTP {resp.status_code}: {safe_text}"
                    logger.warning("[AI Mode / %s] %s", self.provider_label, last_err)
                    if resp.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN, HTTPStatus.NOT_FOUND):
                        break  # Fail fast on auth/endpoint mismatch
                    continue

                data = resp.json()
                latency = (time.perf_counter() - t0) * 1000.0
                text_content, p_tokens, c_tokens = self._extract_response_text(
                    data, self.api_compatibility
                )
                p_tokens_total += p_tokens
                c_tokens_total += c_tokens

                validated = parse_and_validate_llm_response(text_content, brief)
                if not validated.ok:
                    last_err = f"Invalid structured output from {self.model}: {validated.error}"
                    logger.warning("[AI Mode / %s] %s (attempt %d)", self.provider_label, last_err, attempt + 1)
                    continue

                self._record_success(latency, p_tokens_total, c_tokens_total, cost=0.0)
                return LLMProviderResult(
                    proposals=validated.proposals or spec_proposals,
                    commands=validated.commands,
                    rejected_commands=validated.rejected_commands,
                    rationale=validated.rationale,
                    situation_summary=validated.situation_summary,
                    traffic_plan=validated.traffic_plan,
                    unresolved_risks=validated.unresolved_risks,
                    confidence=validated.confidence,
                    requires_human_approval=validated.requires_human_approval,
                    token_usage={
                        "prompt_tokens": p_tokens_total,
                        "completion_tokens": c_tokens_total,
                        "total_tokens": p_tokens_total + c_tokens_total,
                    },
                    cost_usd=0.0,
                    latency_ms=round(latency, 2),
                    operating_mode="ai",
                    provider_name=self.provider_label,
                    model_name=self.model,
                    fallback_used=False,
                    provider_status="connected",
                    attribution=f"AI Mode — {self.provider_label} — {self.model}",
                )

            except Exception as exc:
                last_err = f"{self.provider_label} inference error: {self.credential_store.redact(str(exc))}"
                logger.warning("[AI Mode / %s] %s (attempt %d)", self.provider_label, last_err, attempt + 1)

        self._record_failure(last_err or f"{self.provider_label} inference failed")
        return await build_explicit_fallback_result(
            heuristic_fallback=self.fallback,
            brief=brief,
            specialists=specialists,
            operating_mode="ai",
            fallback_policy=self.fallback_policy,
            reason=self.last_error,
            model_name=self.model,
            token_usage={
                "prompt_tokens": p_tokens_total,
                "completion_tokens": c_tokens_total,
                "total_tokens": p_tokens_total + c_tokens_total,
            }
            if (p_tokens_total or c_tokens_total)
            else None,
        )
