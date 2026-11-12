"""OpenTelemetry-aligned AI telemetry, token/quota accounting, and PII-safe logging."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import Counter
from contextlib import contextmanager
from typing import Any, Iterator

from opentelemetry import trace

from .pii import scrub_pii

logger = logging.getLogger("civicops.telemetry")
_tracer = trace.get_tracer("civicops.ai")

_BLOCKED_KEYS = {
    "prompt",
    "message",
    "description",
    "complaint",
    "reply",
    "raw_text",
    "phone",
    "email",
    "reporter_name",
    "api_key",
}


def is_content_capture_enabled() -> bool:
    """Enforce OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=off by default."""
    val = os.getenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "off").strip().lower()
    return val in {"1", "true", "on", "yes"}


class _TelemetryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.ai_requests_total = 0
            self.ai_fallback_total = 0
            self.ai_tokens_input_total = 0
            self.ai_tokens_output_total = 0
            self.ai_tokens_thoughts_total = 0
            self.guardrail_triggers_total = 0
            self.outcomes: Counter[str] = Counter()
            self.fallback_reasons: Counter[str] = Counter()
            self.guardrail_reasons: Counter[str] = Counter()
            self.models: Counter[str] = Counter()
            self.latencies_ms: list[float] = []

    def record_ai_call(
        self,
        *,
        operation: str,
        model: str | None,
        outcome: str,
        latency_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        thoughts_tokens: int = 0,
    ) -> None:
        with self._lock:
            self.ai_requests_total += 1
            self.ai_tokens_input_total += max(0, input_tokens)
            self.ai_tokens_output_total += max(0, output_tokens)
            self.ai_tokens_thoughts_total += max(0, thoughts_tokens)
            self.outcomes[f"{operation}:{outcome}"] += 1
            self.models[model or "none"] += 1
            self.latencies_ms.append(round(latency_ms, 2))
            if len(self.latencies_ms) > 500:
                self.latencies_ms = self.latencies_ms[-500:]

    def record_fallback(self, *, operation: str, reason: str) -> None:
        with self._lock:
            self.ai_fallback_total += 1
            self.fallback_reasons[f"{operation}:{reason}"] += 1

    def record_guardrail(self, *, reason: str) -> None:
        with self._lock:
            self.guardrail_triggers_total += 1
            self.guardrail_reasons[reason] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            avg_lat = (
                round(sum(self.latencies_ms) / len(self.latencies_ms), 2)
                if self.latencies_ms
                else 0.0
            )
            return {
                "capture_message_content": is_content_capture_enabled(),
                "ai_requests_total": self.ai_requests_total,
                "ai_fallback_total": self.ai_fallback_total,
                "ai_tokens_input_total": self.ai_tokens_input_total,
                "ai_tokens_output_total": self.ai_tokens_output_total,
                "ai_tokens_thoughts_total": self.ai_tokens_thoughts_total,
                "guardrail_triggers_total": self.guardrail_triggers_total,
                "mean_ai_latency_ms": avg_lat,
                "outcomes": dict(self.outcomes),
                "fallback_reasons": dict(self.fallback_reasons),
                "guardrail_reasons": dict(self.guardrail_reasons),
                "models": dict(self.models),
                "estimated_cost_usd": 0.0,
            }


_store = _TelemetryStore()


def reset_telemetry() -> None:
    _store.reset()


def get_telemetry_snapshot() -> dict[str, Any]:
    return _store.snapshot()


def record_fallback(*, operation: str, reason: str) -> None:
    _store.record_fallback(operation=operation, reason=reason)


def record_guardrail_trigger(*, reason: str) -> None:
    _store.record_guardrail(reason=reason)


def _sanitize_extra(extra: dict[str, Any] | None) -> dict[str, Any]:
    if not extra:
        return {}
    safe: dict[str, Any] = {}
    for key, val in extra.items():
        if key.lower() in _BLOCKED_KEYS:
            safe[f"{key}_chars"] = len(str(val))
            continue
        if isinstance(val, str):
            safe[key] = scrub_pii(val)
        elif isinstance(val, (int, float, bool)) or val is None:
            safe[key] = val
    return safe


@contextmanager
def trace_ai_call(
    *,
    operation: str,
    model: str | None,
    extra: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    """Record an OTel span + structured PII-free telemetry event for an AI call."""
    meta: dict[str, Any] = {
        "operation": operation,
        "model": model,
        "outcome": "unknown",
        "input_tokens": 0,
        "output_tokens": 0,
        "thoughts_tokens": 0,
    }
    safe_extra = _sanitize_extra(extra)
    t0 = time.perf_counter()
    with _tracer.start_as_current_span(f"gen_ai.{operation}") as span:
        span.set_attribute("gen_ai.system", "google_gemini")
        if model:
            span.set_attribute("gen_ai.request.model", model)
        for k, v in safe_extra.items():
            if v is not None:
                span.set_attribute(f"civicops.{k}", v)
        try:
            yield meta
        finally:
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            span.set_attribute("gen_ai.usage.input_tokens", int(meta["input_tokens"]))
            span.set_attribute("gen_ai.usage.output_tokens", int(meta["output_tokens"]))
            span.set_attribute("civicops.outcome", str(meta["outcome"]))
            span.set_attribute("civicops.latency_ms", latency_ms)
            _store.record_ai_call(
                operation=operation,
                model=model,
                outcome=str(meta["outcome"]),
                latency_ms=latency_ms,
                input_tokens=int(meta["input_tokens"]),
                output_tokens=int(meta["output_tokens"]),
                thoughts_tokens=int(meta["thoughts_tokens"]),
            )
            event = {
                "event": "gen_ai_call",
                "gen_ai.system": "google_gemini",
                "gen_ai.request.model": model,
                "operation": operation,
                "outcome": meta["outcome"],
                "latency_ms": latency_ms,
                "input_tokens": int(meta["input_tokens"]),
                "output_tokens": int(meta["output_tokens"]),
                "thoughts_tokens": int(meta["thoughts_tokens"]),
                **safe_extra,
            }
            logger.info(json.dumps(event, default=str))

