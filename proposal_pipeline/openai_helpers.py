"""OpenAI SDK helpers with structured output, retry logic, and persistence."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional, Type, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

# Load .env from the project root (two levels up from this file:
#   proposal_pipeline/openai_helpers.py -> proposal_pipeline/ -> project root)
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

# Debug: confirm which key is loaded
_loaded_key = os.getenv("OPENAI_API_KEY", "")
print(f"[openai_helpers] Using OPENAI_API_KEY: {_loaded_key[:20]}..." if _loaded_key else "[openai_helpers] WARNING: OPENAI_API_KEY not set!")

# Reasoning models (o1, o3, gpt-5, etc.) only support temperature=1 (the default).
# Passing any other value causes a 400 error, so we detect and skip it.
_REASONING_MODEL_PREFIXES = ("o1", "o3", "gpt-5")

def _is_reasoning_model(model: str) -> bool:
    return any(model.startswith(p) for p in _REASONING_MODEL_PREFIXES)

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)


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
