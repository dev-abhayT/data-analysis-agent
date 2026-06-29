import json
import time
import re
from typing import Generator, Any
from google import genai
from google.genai import types


def _is_rate_limit(exc: Exception) -> bool:
    """Return True if this exception is a 429 / RESOURCE_EXHAUSTED."""
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg


def _retry_delay_from_exc(exc: Exception, default: float = 35.0) -> float:
    """Extract the 'retryDelay' seconds from a 429 error message, or use default."""
    msg = str(exc)
    m = re.search(r"retryDelay.*?(\d+)s", msg)
    if m:
        return float(m.group(1)) + 2.0  # add 2s buffer
    return default


class GeminiProvider:
    DEFAULT_MODEL = "gemini-2.5-flash"
    _MAX_RETRIES = 2

    def __init__(self, api_key: str, model: str = "") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def _retry_call(self, fn, *args, **kwargs):
        """Call fn(*args, **kwargs) with up to _MAX_RETRIES on 429."""
        for attempt in range(self._MAX_RETRIES + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                if _is_rate_limit(exc) and attempt < self._MAX_RETRIES:
                    wait = _retry_delay_from_exc(exc)
                    time.sleep(wait)
                    continue
                raise

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        """Synchronous non-streaming call."""
        config = types.GenerateContentConfig(system_instruction=system) if system else None

        def _call():
            return self._client.models.generate_content(
                model=self._model, contents=prompt, config=config
            )

        response = self._retry_call(_call)
        return response.text

    def call_json(self, prompt: str, *, system: str | None = None) -> dict[str, Any]:
        """Call Gemini with JSON output. Strips markdown fences if present."""
        if system:
            config = types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
            )
        else:
            config = types.GenerateContentConfig(
                response_mime_type="application/json"
            )

        def _call():
            return self._client.models.generate_content(
                model=self._model, contents=prompt, config=config
            )

        response = self._retry_call(_call)
        text = response.text.strip()
        # Strip ```json fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        return json.loads(text)

    def stream_model(
        self, prompt: str, *, system: str | None = None
    ) -> Generator[tuple[str, dict | None], None, None]:
        """
        Streaming call. Yields (token_chunk, usage_metadata) pairs.
        usage_metadata is None for all chunks except the last one.
        The last chunk carries usage: {"prompt_tokens": int, "completion_tokens": int}.
        """
        config = types.GenerateContentConfig(system_instruction=system) if system else None

        for attempt in range(self._MAX_RETRIES + 1):
            try:
                stream = self._client.models.generate_content_stream(
                    model=self._model, contents=prompt, config=config
                )
                usage = None
                for chunk in stream:
                    text = ""
                    if chunk.candidates:
                        for part in chunk.candidates[0].content.parts:
                            if hasattr(part, "text") and part.text:
                                text += part.text
                    if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                        meta = chunk.usage_metadata
                        prompt_tokens = getattr(meta, "prompt_token_count", 0) or 0
                        completion_tokens = getattr(meta, "candidates_token_count", 0) or 0
                        if prompt_tokens or completion_tokens:
                            usage = {
                                "prompt_tokens": prompt_tokens,
                                "completion_tokens": completion_tokens,
                            }
                    # Yield chunk — attach usage only if no text in this chunk
                    yield text, (usage if not text else None)
                # Yield a final empty-text chunk with usage if we collected it
                if usage is not None:
                    yield "", usage
                return  # success
            except Exception as exc:
                if _is_rate_limit(exc) and attempt < self._MAX_RETRIES:
                    wait = _retry_delay_from_exc(exc)
                    time.sleep(wait)
                    continue
                raise
