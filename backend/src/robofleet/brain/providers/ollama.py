"""First-Class Local LLM Mode Provider via Ollama.

Runs local inference (recommended initial model: qwen3.5:4b) over Ollama's HTTP API
with strict concurrency control, compact prompts, structured JSON validation, Windows-friendly
health checks, explicit unavailable state tracking, and deterministic safety fallback.
Never silently escalates to a cloud API provider.
"""

from __future__ import annotations

import asyncio
import logging
import time
from http import HTTPStatus
from typing import Any, Literal

import httpx
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
from robofleet.config.models import LocalLLMConfig
from robofleet.contracts.brain import SituationBrief

logger = logging.getLogger(__name__)


class OllamaProvider(CircuitBreakerMixin):
    """Local Ollama LLM decision provider."""

    name: str = "local_llm"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3.5:4b",
        timeout_s: float = 15.0,
        context_length: int = 4096,
        temperature: float = 0.15,
        max_tokens: int = 512,
        retry_count: int = 1,
        max_concurrency: int = 1,
        fallback_policy: Literal["heuristic", "safe_wait"] = "heuristic",
        health_check_interval_s: float = 15.0,
        circuit_threshold: int = 3,
        circuit_cooldown_s: float = 20.0,
    ) -> None:
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
        self.model = model or "qwen3.5:4b"
        self.timeout_s = timeout_s
        self.context_length = context_length
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.retry_count = retry_count
        self.max_concurrency = max(1, max_concurrency)
        self.fallback_policy: Literal["heuristic", "safe_wait"] = fallback_policy
        self.health_check_interval_s = health_check_interval_s
        self.fallback = HeuristicProvider()
        self._init_circuit(circuit_threshold=circuit_threshold, circuit_cooldown_s=circuit_cooldown_s)

        # Event-loop-scoped semaphores prevent cross-loop RuntimeError in tests
        self._semaphores: dict[int, asyncio.Semaphore] = {}
        self.last_health_check_ts: float = 0.0
        self.last_health_status: ProviderHealthStatus | None = None

    def apply_config(self, cfg: LocalLLMConfig) -> None:
        self.base_url = (cfg.base_url or "http://localhost:11434").rstrip("/")
        self.model = cfg.model or "qwen3.5:4b"
        self.timeout_s = cfg.timeout_s
        self.context_length = cfg.context_length
        self.temperature = cfg.temperature
        self.max_tokens = cfg.max_tokens
        self.retry_count = cfg.retry_count
        if cfg.max_concurrency != self.max_concurrency:
            self.max_concurrency = max(1, cfg.max_concurrency)
            self._semaphores.clear()
        self.fallback_policy = cfg.fallback_policy
        self.health_check_interval_s = cfg.health_check_interval_s
        self.circuit_threshold = cfg.circuit_threshold
        self.circuit_cooldown_s = cfg.circuit_cooldown_s
        self.last_health_check_ts = 0.0

    def _get_semaphore(self) -> asyncio.Semaphore:
        loop_id = id(asyncio.get_running_loop())
        sem = self._semaphores.get(loop_id)
        if sem is None:
            sem = asyncio.Semaphore(self.max_concurrency)
            self._semaphores[loop_id] = sem
        return sem

    def _chat_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/chat"

    def _tags_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/tags"

    @staticmethod
    def _model_matches(target: str, installed_names: list[str]) -> bool:
        t = target.strip().lower()
        if not t:
            return False
        t_latest = f"{t}:latest" if ":" not in t else t
        for name in installed_names:
            n = name.strip().lower()
            if n in (t, t_latest) or (t.endswith(":latest") and n == t[:-7]):
                return True
        return False

    async def list_installed_models(self) -> tuple[bool, list[str], str]:
        """Query Ollama /api/tags. Returns (service_up, models, error_message)."""
        try:
            async with httpx.AsyncClient(timeout=min(self.timeout_s, 5.0)) as client:
                resp = await client.get(self._tags_url())
            if resp.status_code != HTTPStatus.OK:
                return False, [], f"Ollama API returned HTTP {resp.status_code}"
            data = resp.json()
            models = [
                str(m.get("name"))
                for m in data.get("models", [])
                if isinstance(m, dict) and m.get("name")
            ]
            return True, models, ""
        except httpx.ConnectError:
            return (
                False,
                [],
                f"Ollama service is not running or unreachable at {self.base_url}. Run `ollama serve`.",
            )
        except Exception as exc:
            return False, [], f"Failed querying Ollama at {self.base_url}: {exc}"

    async def check_health(self, force: bool = True) -> ProviderHealthStatus:
        """Check Ollama service reachability and whether the selected local model exists."""
        now = time.time()
        if (
            not force
            and self.last_health_status is not None
            and (now - self.last_health_check_ts) < self.health_check_interval_s
        ):
            return self.last_health_status

        t0 = time.perf_counter()
        if not self.base_url or not self.base_url.startswith(("http://", "https://")):
            status = ProviderHealthStatus(
                ok=False,
                operating_mode="local_llm",
                provider_name="Ollama",
                model_name=self.model,
                status="error",
                message="Invalid Ollama URL. Must start with http:// or https://.",
            )
            self.last_health_status = status
            self.last_health_check_ts = now
            return status

        service_up, models, err_msg = await self.list_installed_models()
        latency = round((time.perf_counter() - t0) * 1000.0, 2)

        if not service_up:
            status = ProviderHealthStatus(
                ok=False,
                operating_mode="local_llm",
                provider_name="Ollama",
                model_name=self.model,
                status="unavailable",
                message=err_msg,
                latency_ms=latency,
            )
        elif not self._model_matches(self.model, models):
            status = ProviderHealthStatus(
                ok=False,
                operating_mode="local_llm",
                provider_name="Ollama",
                model_name=self.model,
                status="unavailable",
                message=(
                    f"Ollama is running, but model '{self.model}' is not downloaded. "
                    f"Install it with: ollama pull {self.model}"
                ),
                available_models=models,
                latency_ms=latency,
            )
        else:
            status = ProviderHealthStatus(
                ok=True,
                operating_mode="local_llm",
                provider_name="Ollama",
                model_name=self.model,
                status="connected",
                message=f"Ollama ready with local model '{self.model}' ({latency}ms).",
                available_models=models,
                latency_ms=latency,
            )

        self.last_health_status = status
        self.last_health_check_ts = now
        return status

    def _build_chat_payload(self, messages: list[dict[str, str]], disable_thinking: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.context_length,
                "num_predict": self.max_tokens,
            },
        }
        if disable_thinking:
            payload["think"] = False
        return payload

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
                operating_mode="local_llm",
                fallback_policy=self.fallback_policy,
                reason=f"Ollama circuit breaker open ({self.last_error or 'repeated failures'})",
                model_name=self.model,
            )

        if not self.base_url.startswith(("http://", "https://")):
            return await build_explicit_fallback_result(
                heuristic_fallback=self.fallback,
                brief=brief,
                specialists=specialists,
                operating_mode="local_llm",
                fallback_policy=self.fallback_policy,
                reason="Invalid Ollama endpoint URL",
                model_name=self.model,
            )

        messages = build_decision_messages(brief, spec_proposals)
        disable_thinking = True
        last_err = ""
        p_tokens_total = 0
        c_tokens_total = 0

        sem = self._get_semaphore()
        async with sem:
            for attempt in range(self.retry_count + 1):
                payload = self._build_chat_payload(messages, disable_thinking=disable_thinking)
                try:
                    async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                        resp = await client.post(self._chat_url(), json=payload)

                    if resp.status_code == HTTPStatus.BAD_REQUEST and disable_thinking and "think" in resp.text.lower():
                        disable_thinking = False
                        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                            resp = await client.post(
                                self._chat_url(),
                                json=self._build_chat_payload(messages, disable_thinking=False),
                            )

                    if resp.status_code == HTTPStatus.NOT_FOUND:
                        last_err = f"Ollama model '{self.model}' not found (HTTP 404). Run: ollama pull {self.model}"
                        logger.warning("[Local LLM Mode / Ollama] %s", last_err)
                        break

                    if resp.status_code != HTTPStatus.OK:
                        err_text = resp.text[:200]
                        if "memory" in err_text.lower() or "oom" in err_text.lower():
                            last_err = f"Local model out-of-memory error for '{self.model}': {err_text}"
                            break
                        last_err = f"Ollama HTTP {resp.status_code}: {err_text}"
                        logger.warning("[Local LLM Mode / Ollama] %s", last_err)
                        continue

                    data = resp.json()
                    if isinstance(data, dict) and data.get("error"):
                        last_err = f"Ollama error: {data['error']}"
                        logger.warning("[Local LLM Mode / Ollama] %s", last_err)
                        if "memory" in last_err.lower() or "not found" in last_err.lower():
                            break
                        continue

                    latency = (time.perf_counter() - t0) * 1000.0
                    p_tokens = int(data.get("prompt_eval_count", 0))
                    c_tokens = int(data.get("eval_count", 0))
                    p_tokens_total += p_tokens
                    c_tokens_total += c_tokens

                    msg = data.get("message", {}) if isinstance(data, dict) else {}
                    text_content = str(msg.get("content", "") or data.get("response", "") or "")

                    validated = parse_and_validate_llm_response(text_content, brief)
                    if not validated.ok:
                        last_err = f"Invalid structured output from Ollama ({self.model}): {validated.error}"
                        logger.warning(
                            "[Local LLM Mode / Ollama] %s (attempt %d)",
                            last_err,
                            attempt + 1,
                        )
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
                        operating_mode="local_llm",
                        provider_name="Ollama",
                        model_name=self.model,
                        fallback_used=False,
                        provider_status="connected",
                        attribution=f"Local LLM Mode — Ollama — {self.model}",
                    )

                except httpx.ConnectError:
                    last_err = f"Ollama service unavailable at {self.base_url} (connection refused)"
                    logger.warning("[Local LLM Mode / Ollama] %s", last_err)
                    break
                except httpx.TimeoutException:
                    last_err = f"Local inference timed out after {self.timeout_s:.1f}s ({self.model})"
                    logger.warning("[Local LLM Mode / Ollama] %s (attempt %d)", last_err, attempt + 1)
                except Exception as exc:
                    last_err = f"Ollama inference error: {exc}"
                    logger.warning("[Local LLM Mode / Ollama] %s (attempt %d)", last_err, attempt + 1)

        self._record_failure(last_err or "Ollama local inference failed")
        return await build_explicit_fallback_result(
            heuristic_fallback=self.fallback,
            brief=brief,
            specialists=specialists,
            operating_mode="local_llm",
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
