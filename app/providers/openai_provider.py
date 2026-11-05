from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


def generate_text(prompt: str) -> str | None:
    """Return LLM text, or None so callers fall back to deterministic output.

    An unconfigured, slow or failing LLM must never break the briefing, so errors are
    logged and swallowed here rather than propagated.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    if not api_key or not model:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    try:
        client = OpenAI(api_key=api_key, timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20")), max_retries=1)
        response = client.responses.create(model=model, input=prompt)
        return response.output_text.strip() or None
    except Exception as exc:
        log.warning("LLM call failed, using fallback: %s", exc)
        return None
