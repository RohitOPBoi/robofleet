"""Anthropic-Native Cloud Adapter (Internal Adapter within AI Mode).

Preserves native Anthropic Messages API compatibility under the unified AI Mode
abstraction, while strictly reporting honest provider attribution and never masking
heuristic fallbacks as LLM-generated decisions.
"""

from __future__ import annotations

import logging
import time
from http import HTTPStatus
from typing import Any, Literal

import httpx

from robofleet.brain.credentials import SecretCredentialStore
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

# Standard reference pricing per million tokens
SONNET_INPUT_PRICE_PER_M = 3.0
SONNET_OUTPUT_PRICE_PER_M = 15.0


class AnthropicProvider(CircuitBreakerMixin):
    name: str = "ai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-3-5-sonnet-20241022",
        base_url: str = "https://api.anthropic.com",
        timeout_s: float = 10.0,
        max_tokens: int = 800,
        temperature: float = 0.15,
        retry_count: int = 1,
        circuit_threshold: int = 3,
        circuit_cooldown_s: float = 30.0,
        failure_threshold: int | None = None,
        cooldown_sec: float | None = None,
        fallback_policy: Literal["heuristic", "safe_wait"] = "heuristic",
        credential_store: SecretCredentialStore | None = None,
        profile_key: str = "anthropic",
    ) -> None:
        self._explicit_api_key = api_key or ""
        self.model = model
        self.base_url = base_url.rstrip("/") or "https://api.anthropic.com"
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.retry_count = retry_count
        self.fallback_policy: Literal["heuristic", "safe_wait"] = fallback_policy
        self.credential_store = credential_store or SecretCredentialStore()
        self.profile_key = profile_key
        if self._explicit_api_key:
            self.credential_store.set_key(self.profile_key, self._explicit_api_key)

        self.fallback = HeuristicProvider()
        self._init_circuit(
            circuit_threshold=failure_threshold if failure_threshold is not None else circuit_threshold,
            circuit_cooldown_s=cooldown_sec if cooldown_sec is not None else circuit_cooldown_s,
        )

    def apply_config(self, cfg: AICloudConfig) -> None:
        self.model = cfg.model or "claude-3-5-sonnet-20241022"
        self.base_url = (cfg.base_url or "https://api.anthropic.com").rstrip("/")
        self.timeout_s = cfg.timeout_s
        self.max_tokens = cfg.max_tokens
        self.temperature = cfg.temperature
        self.retry_count = cfg.retry_count
        self.fallback_policy = cfg.fallback_policy
        self.circuit_threshold = cfg.circuit_threshold
        self.circuit_cooldown_s = cfg.circuit_cooldown_s

    def _resolve_api_key(self) -> str:
        return self.credential_store.get_key(
            self.profile_key,
            env_vars=("ANTHROPIC_API_KEY", "ROBOFLEET_AI_API_KEY"),
            explicit_fallback=self._explicit_api_key,
        )

    def _messages_url(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/v1/messages"):
            return base
        if base.endswith("/v1"):
            return f"{base}/messages"
        return f"{base}/v1/messages"

    async def test_connection(self) -> ProviderHealthStatus:
        """Verify Anthropic API key, endpoint, and model availability."""
        t0 = time.perf_counter()
        api_key = self._resolve_api_key()
        if not api_key:
            return ProviderHealthStatus(
                ok=False,
                operating_mode="ai",
                provider_name="Anthropic",
                model_name=self.model,
                status="unconfigured",
                message="API key is missing. Enter an Anthropic API key or set ANTHROPIC_API_KEY.",
            )

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 16,
            "temperature": 0.0,
            "messages": [{"role": "user", "content": "Respond with OK."}],
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(self._messages_url(), headers=headers, json=payload)
            latency = round((time.perf_counter() - t0) * 1000.0, 2)
            if resp.status_code == HTTPStatus.OK:
                return ProviderHealthStatus(
                    ok=True,
                    operating_mode="ai",
                    provider_name="Anthropic",
                    model_name=self.model,
                    status="connected",
                    message=f"Connected to Anthropic ({self.model}) in {latency}ms.",
                    latency_ms=latency,
                )
            safe_err = self.credential_store.redact(resp.text[:200])
            if resp.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                return ProviderHealthStatus(
                    ok=False,
                    operating_mode="ai",
                    provider_name="Anthropic",
                    model_name=self.model,
                    status="error",
                    message=f"Authentication rejected (HTTP {resp.status_code}). Check your Anthropic API key.",
                    latency_ms=latency,
                )
            return ProviderHealthStatus(
                ok=False,
                operating_mode="ai",
                provider_name="Anthropic",
                model_name=self.model,
                status="unavailable",
                message=f"Anthropic endpoint returned HTTP {resp.status_code}: {safe_err}",
                latency_ms=latency,
            )
        except Exception as exc:
            safe_msg = self.credential_store.redact(str(exc))
            return ProviderHealthStatus(
                ok=False,
                operating_mode="ai",
                provider_name="Anthropic",
                model_name=self.model,
                status="unavailable",
                message=f"Failed to reach Anthropic endpoint: {safe_msg}",
            )

    async def decide(
        self,
        brief: SituationBrief,
        specialists: list[Any] | None = None,
    ) -> LLMProviderResult:
        t0 = time.perf_counter()

        # Always compute specialist proposals first so fallback and LLM prompt share grounded insights
        spec_proposals = collect_and_arbitrate_specialists(brief, specialists)

        if self.is_circuit_open:
            return await build_explicit_fallback_result(
                heuristic_fallback=self.fallback,
                brief=brief,
                specialists=specialists,
                operating_mode="ai",
                fallback_policy=self.fallback_policy,
                reason="Anthropic circuit breaker open after repeated failures",
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
                reason="Anthropic API key not configured",
                model_name=self.model,
            )

        messages = build_decision_messages(brief, spec_proposals)
        system_prompt = messages[0]["content"]
        user_msg = messages[1]["content"]

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_msg}],
        }

        last_err = ""
        p_tokens_total = 0
        c_tokens_total = 0
        total_cost = 0.0

        for attempt in range(self.retry_count + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                    resp = await client.post(self._messages_url(), headers=headers, json=payload)

                if resp.status_code != HTTPStatus.OK:
                    err_snippet = self.credential_store.redact(resp.text[:160])
                    last_err = f"Anthropic HTTP {resp.status_code}: {err_snippet}"
                    logger.warning("[AI Mode / Anthropic] %s", last_err)
                    if resp.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN, HTTPStatus.NOT_FOUND):
                        break  # Do not retry auth or missing-endpoint errors
                    continue

                data = resp.json()
                latency = (time.perf_counter() - t0) * 1000.0
                usage = data.get("usage", {})
                p_tokens = int(usage.get("input_tokens", 0))
                c_tokens = int(usage.get("output_tokens", 0))
                p_tokens_total += p_tokens
                c_tokens_total += c_tokens
                call_cost = (
                    (p_tokens / 1_000_000) * SONNET_INPUT_PRICE_PER_M
                    + (c_tokens / 1_000_000) * SONNET_OUTPUT_PRICE_PER_M
                )
                total_cost += call_cost

                text_content = "".join(
                    b.get("text", "")
                    for b in data.get("content", [])
                    if isinstance(b, dict) and b.get("type") == "text"
                )
                validated = parse_and_validate_llm_response(text_content, brief)
                if not validated.ok:
                    last_err = f"Invalid structured output from Anthropic ({self.model}): {validated.error}"
                    logger.warning("[AI Mode / Anthropic] %s (attempt %d)", last_err, attempt + 1)
                    continue

                self._record_success(latency, p_tokens_total, c_tokens_total, total_cost)
                merged_proposals = validated.proposals or spec_proposals
                return LLMProviderResult(
                    proposals=merged_proposals,
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
                    cost_usd=round(total_cost, 6),
                    latency_ms=round(latency, 2),
                    operating_mode="ai",
                    provider_name="Anthropic",
                    model_name=self.model,
                    fallback_used=False,
                    provider_status="connected",
                    attribution=f"AI Mode — Anthropic — {self.model}",
                )

            except Exception as exc:
                last_err = f"Anthropic request error: {self.credential_store.redact(str(exc))}"
                logger.warning("[AI Mode / Anthropic] %s (attempt %d)", last_err, attempt + 1)

        self._record_failure(last_err or "Anthropic inference failed")
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
            cost_usd=round(total_cost, 6),
        )
