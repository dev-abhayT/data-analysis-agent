from typing import Generator, Any
from config.settings import get_settings


def _make_gemini() -> "GeminiProvider":
    from llm.providers.gemini import GeminiProvider
    s = get_settings()
    return GeminiProvider(api_key=s.gemini_api_key, model=s.gemini_model)


def _make_anthropic() -> "AnthropicProvider":
    from llm.providers.anthropic import AnthropicProvider
    s = get_settings()
    return AnthropicProvider(api_key=s.anthropic_api_key, model=s.llm_model)


def _make_provider():
    s = get_settings()
    provider = s.llm_provider.lower() if s.llm_provider else ""
    if provider == "anthropic" or (not provider and s.anthropic_api_key):
        return _make_anthropic()
    if provider == "gemini" or (not provider and s.gemini_api_key):
        return _make_gemini()
    raise RuntimeError(
        "No LLM provider configured. Set AGENT_ANTHROPIC_API_KEY or "
        "AGENT_GEMINI_API_KEY in .env, or set AGENT_LLM_PROVIDER explicitly."
    )


class LLMClient:
    def __init__(self) -> None:
        self._provider = _make_provider()

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        return self._provider.call_model(prompt, system=system)

    def call_json(self, prompt: str, *, system: str | None = None) -> dict[str, Any]:
        if hasattr(self._provider, "call_json"):
            return self._provider.call_json(prompt, system=system)
        # Fallback for Anthropic: parse JSON from response text
        import json
        text = self._provider.call_model(prompt, system=system).strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        return json.loads(text)

    def stream_model(
        self, prompt: str, *, system: str | None = None
    ) -> Generator[tuple[str, dict | None], None, None]:
        if hasattr(self._provider, "stream_model"):
            yield from self._provider.stream_model(prompt, system=system)
        else:
            # Fallback: yield full text as single chunk
            text = self._provider.call_model(prompt, system=system)
            yield text, None
