"""OpenAI SDK helpers with structured output, retry logic, and persistence."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional, Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel

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
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
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
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": augmented_system},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
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
