"""OpenAI SDK helpers with structured output, retry logic, and cost tracking."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Type, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

# Load .env from the project root (two levels up from this file:
#   proposal_pipeline/openai_helpers.py -> proposal_pipeline/ -> project root)
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)

# Verify key is loaded (log only last 4 chars for safety)
_loaded_key = os.getenv("OPENAI_API_KEY", "")
if not _loaded_key:
    logger.warning("OPENAI_API_KEY not set — API calls will fail")

# Reasoning models (o1, o3, gpt-5, etc.) only support temperature=1 (the default).
# Passing any other value causes a 400 error, so we detect and skip it.
_REASONING_MODEL_PREFIXES = ("o1", "o3", "gpt-5")

def _is_reasoning_model(model: str) -> bool:
    return any(model.startswith(p) for p in _REASONING_MODEL_PREFIXES)


# ── Cost Tracking ──

# Pricing per 1M tokens (USD) — update as OpenAI changes pricing
# Source: https://openai.com/api/pricing/
MODEL_PRICING: dict[str, dict[str, float]] = {
    # GPT-5 family
    "gpt-5": {"input": 1.25, "output": 10.00},
    "gpt-5.3": {"input": 1.75, "output": 14.00},
    "gpt-5.4": {"input": 2.50, "output": 15.00},
    # GPT-4o family
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    # GPT-4 Turbo
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    # o1/o3 reasoning
    "o1": {"input": 15.00, "output": 60.00},
    "o1-mini": {"input": 1.10, "output": 4.40},
    "o3": {"input": 10.00, "output": 40.00},
    "o3-mini": {"input": 1.10, "output": 4.40},
}


def _get_pricing(model: str) -> dict[str, float]:
    """Look up pricing for a model, falling back to gpt-4o rates."""
    # Try exact match first, then prefix match
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]
    for prefix, pricing in MODEL_PRICING.items():
        if model.startswith(prefix):
            return pricing
    return {"input": 2.50, "output": 10.00}  # Default to gpt-4o rates


@dataclass
class UsageTracker:
    """Thread-safe tracker for cumulative token usage and estimated cost."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_calls: int = 0
    estimated_cost_usd: float = 0.0
    call_log: list = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, model: str, input_tokens: int, output_tokens: int, call_type: str = "") -> float:
        """Record token usage from an API call. Returns the cost for this call."""
        pricing = _get_pricing(model)
        call_cost = (
            (input_tokens / 1_000_000) * pricing["input"]
            + (output_tokens / 1_000_000) * pricing["output"]
        )

        with self._lock:
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_calls += 1
            self.estimated_cost_usd += call_cost
            self.call_log.append({
                "call_number": self.total_calls,
                "type": call_type,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": round(call_cost, 6),
                "cumulative_cost_usd": round(self.estimated_cost_usd, 4),
            })

        return call_cost

    def summary(self) -> dict:
        """Return a summary dict suitable for saving to manifest."""
        with self._lock:
            return {
                "total_api_calls": self.total_calls,
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "total_tokens": self.total_input_tokens + self.total_output_tokens,
                "estimated_cost_usd": round(self.estimated_cost_usd, 4),
                "cost_breakdown": self.call_log.copy(),
            }

    def __str__(self) -> str:
        return (
            f"{self.total_calls} API calls | "
            f"{self.total_input_tokens:,} in + {self.total_output_tokens:,} out tokens | "
            f"${self.estimated_cost_usd:.2f} estimated"
        )


# Global tracker — reset per pipeline run
_usage_tracker = UsageTracker()


def get_usage_tracker() -> UsageTracker:
    """Get the current usage tracker."""
    return _usage_tracker


def reset_usage_tracker() -> UsageTracker:
    """Reset the global usage tracker (call at start of pipeline run)."""
    global _usage_tracker
    _usage_tracker = UsageTracker()
    return _usage_tracker


def _record_usage(response, model: str, call_type: str = "") -> None:
    """Extract usage from an API response and record it."""
    usage = getattr(response, "usage", None)
    if usage:
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        cost = _usage_tracker.record(model, input_tokens, output_tokens, call_type)
        logger.debug(
            "API call [%s]: %d in + %d out tokens = $%.4f (cumulative: $%.2f)",
            call_type,
            input_tokens,
            output_tokens,
            cost,
            _usage_tracker.estimated_cost_usd,
        )


# ── Client & API Wrappers ──


def get_client(api_key: Optional[str] = None) -> OpenAI:
    """Get an OpenAI client. Uses provided key or falls back to OPENAI_API_KEY env var."""
    if api_key:
        return OpenAI(api_key=api_key)
    return OpenAI()


def chat_completion(
    client: OpenAI,
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-5",
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> str:
    """Simple chat completion returning text content."""
    kwargs: dict = dict(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    if _is_reasoning_model(model):
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["max_tokens"] = max_tokens
        kwargs["temperature"] = temperature
    response = client.chat.completions.create(**kwargs)
    _record_usage(response, model, "chat_completion")
    return response.choices[0].message.content


def structured_output(
    client: OpenAI,
    system_prompt: str,
    user_prompt: str,
    response_model: Type[T],
    model: str = "gpt-5",
    temperature: float = 0.2,
    max_retries: int = 2,
) -> T:
    """Get structured output parsed into a Pydantic model.

    Uses json_object response format with schema injection and automatic retry
    on parse/validation failures.
    """
    schema_json = json.dumps(response_model.model_json_schema(), indent=2)
    augmented_system = (
        f"{system_prompt}\n\n"
        f"You MUST respond with valid JSON matching this exact schema:\n"
        f"```json\n{schema_json}\n```\n"
        f"Return ONLY the JSON object, no other text."
    )

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            kwargs: dict = dict(
                model=model,
                messages=[
                    {"role": "system", "content": augmented_system},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            if not _is_reasoning_model(model):
                kwargs["temperature"] = temperature
            response = client.chat.completions.create(**kwargs)
            _record_usage(response, model, "structured_output")
            raw = response.choices[0].message.content
            return response_model.model_validate_json(raw)
        except Exception as e:
            last_error = e
            logger.warning(
                "structured_output attempt %d/%d failed: %s",
                attempt + 1,
                max_retries + 1,
                e,
            )
            if attempt < max_retries:
                time.sleep(1)

    raise last_error  # type: ignore[misc]


def save_structured_output(data: BaseModel, filename: str) -> str:
    """Save a Pydantic model as a JSON file in the output/ directory."""
    os.makedirs("output", exist_ok=True)
    path = os.path.join("output", filename)
    with open(path, "w") as f:
        f.write(data.model_dump_json(indent=2))
    logger.info("Saved structured output to %s", path)
    return path
