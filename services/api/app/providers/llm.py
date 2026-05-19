"""LLM provider adapter — abstracts AI model calls behind a thin interface.

Current implementation: stub that returns placeholder text.
Future: call Aliyun model provider or other backends.
"""

from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    model: str
    usage_tokens: int = 0


def generate(prompt: str, system: str = "", model: str = "default") -> LLMResponse:
    """Generate text from a prompt. Stub implementation."""
    return LLMResponse(
        text=f"[stub] Generated response for prompt: {prompt[:80]}...",
        model=model,
        usage_tokens=0,
    )
