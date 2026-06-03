from __future__ import annotations

import json
import os

import httpx
from loguru import logger

_SCORER_SYSTEM = (
    "You are a research librarian screening papers for a systematic literature review. "
    "Score and tag each paper based on the criteria below. "
    "Return ONLY valid JSON — no preamble, no markdown fences, no trailing text."
)

_GROQ_ANALYSIS_MODEL = "llama-3.3-70b-versatile"
_ANTHROPIC_MODEL = "claude-sonnet-4-6"

_ollama_available_cache: bool | None = None


class ScoringBackendError(Exception):
    pass


class AnalysisBackendError(Exception):
    pass


def _ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")


def _ollama_parallel() -> int:
    return int(os.environ.get("OLLAMA_NUM_PARALLEL", "4"))


def _scorer_backend() -> str:
    return os.environ.get("SCORER_BACKEND", "groq").lower()


def _check_ollama_sync() -> bool:
    try:
        r = httpx.get("http://localhost:11434/", timeout=2.0)
        return r.status_code < 500
    except Exception:
        return False


async def _check_ollama_available() -> bool:
    global _ollama_available_cache
    if _ollama_available_cache is not None:
        return _ollama_available_cache
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:11434/", timeout=2.0)
            _ollama_available_cache = r.status_code < 500
    except Exception:
        _ollama_available_cache = False
    if not _ollama_available_cache:
        logger.warning(
            "Ollama is not available at localhost:11434 — falling back to Groq for scoring"
        )
    return _ollama_available_cache


async def _call_ollama(
    prompt: str,
    temperature: float = 0.1,
    system: str | None = None,
) -> str:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    resp = await client.chat.completions.create(
        model=_ollama_model(),
        messages=[
            {"role": "system", "content": system or _SCORER_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or ""


async def _call_groq(
    prompt: str,
    system: str,
    model: str = _GROQ_ANALYSIS_MODEL,
) -> str:
    from groq import AsyncGroq

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set")
    client = AsyncGroq(api_key=api_key)
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or ""


async def _call_anthropic(prompt: str) -> str:
    try:
        from anthropic import AsyncAnthropic
        from anthropic.types import TextBlock
    except ImportError as exc:
        raise ScoringBackendError(
            "anthropic package not installed — install it with: pip install anthropic>=0.40.0"
        ) from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ScoringBackendError("ANTHROPIC_API_KEY not set")
    client = AsyncAnthropic(api_key=api_key)
    resp = await client.messages.create(
        model=_ANTHROPIC_MODEL,
        max_tokens=512,
        system=_SCORER_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    block = next((b for b in resp.content if isinstance(b, TextBlock)), None)
    if block is None:
        raise ScoringBackendError("No TextBlock in Anthropic response")
    text = block.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return text


async def call_scorer(prompt: str) -> str:
    """Call the scoring backend. Returns a raw JSON response string.

    Default (groq): Groq primary, Ollama fallback on failure.
    Explicit ollama: Ollama primary (2 attempts), Groq fallback.
    Explicit anthropic: Anthropic only, no fallback.
    Raises ScoringBackendError if all available tiers fail.
    """
    backend = _scorer_backend()

    if backend == "anthropic":
        return await _call_anthropic(prompt)

    if backend == "ollama":
        # Explicit Ollama mode: Ollama x2, then Groq fallback
        if not await _check_ollama_available():
            groq_key = os.environ.get("GROQ_API_KEY", "")
            if not groq_key:
                raise ScoringBackendError(
                    "Ollama unavailable and GROQ_API_KEY not set — no scoring backend available"
                )
            try:
                return await _call_groq(prompt, system=_SCORER_SYSTEM)
            except Exception as e:
                raise ScoringBackendError(f"Groq fallback failed: {e}") from e

        try:
            raw = await _call_ollama(prompt)
            json.loads(raw)
            return raw
        except json.JSONDecodeError:
            logger.debug(
                "Ollama returned invalid JSON on first attempt — retrying at temperature=0"
            )
        except Exception as e:
            logger.warning(f"Ollama attempt 1 failed: {e}")

        try:
            raw = await _call_ollama(prompt, temperature=0.0)
            json.loads(raw)
            return raw
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Ollama double failure — escalating to Groq: {e}")

        groq_key = os.environ.get("GROQ_API_KEY", "")
        if not groq_key:
            raise ScoringBackendError(
                "Ollama failed twice and GROQ_API_KEY not set — all backends exhausted"
            )
        try:
            return await _call_groq(prompt, system=_SCORER_SYSTEM)
        except Exception as e:
            raise ScoringBackendError(f"All backends failed: {e}") from e

    # Default "groq": Groq primary, Ollama fallback
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        try:
            return await _call_groq(prompt, system=_SCORER_SYSTEM)
        except Exception as e:
            logger.warning(f"Groq scorer failed — falling back to Ollama: {e}")

    # Ollama fallback (or sole option when GROQ_API_KEY not set)
    if not await _check_ollama_available():
        if not groq_key:
            raise ScoringBackendError(
                "No scoring backend available — set GROQ_API_KEY or start Ollama (ollama serve)"
            )
        raise ScoringBackendError("Groq failed and Ollama is not available")

    try:
        raw = await _call_ollama(prompt)
        json.loads(raw)
        return raw
    except json.JSONDecodeError:
        logger.debug(
            "Ollama returned invalid JSON on first attempt — retrying at temperature=0"
        )
    except Exception as e:
        logger.warning(f"Ollama attempt 1 failed: {e}")

    try:
        raw = await _call_ollama(prompt, temperature=0.0)
        json.loads(raw)
        return raw
    except (json.JSONDecodeError, Exception) as e:
        raise ScoringBackendError(f"All backends failed: {e}") from e


async def call_analysis(prompt: str, system: str) -> str:
    """Call the analysis backend (always Groq; falls back to Ollama if no key).

    Returns a raw response string. Raises AnalysisBackendError if all fail.
    """
    groq_key = os.environ.get("GROQ_API_KEY", "")

    if groq_key:
        try:
            return await _call_groq(prompt, system=system, model=_GROQ_ANALYSIS_MODEL)
        except Exception as e:
            logger.warning(f"Groq analysis call failed: {e}")

    if await _check_ollama_available():
        try:
            return await _call_ollama(prompt, system=system)
        except Exception as e:
            raise AnalysisBackendError(
                f"Ollama fallback for analysis failed: {e}"
            ) from e

    raise AnalysisBackendError(
        "No analysis backend available — set GROQ_API_KEY or start Ollama"
    )


def get_backend_info() -> dict:
    """Return a dict describing the current backend configuration.

    Performs a synchronous ping to check Ollama availability.
    """
    backend = _scorer_backend()
    model = _ollama_model()
    parallel = _ollama_parallel()
    groq_key = os.environ.get("GROQ_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    ollama_up = _check_ollama_sync()

    if backend == "anthropic":
        scorer_model = _ANTHROPIC_MODEL
    elif backend == "groq":
        scorer_model = _GROQ_ANALYSIS_MODEL
    else:
        scorer_model = model

    analysis_backend = "groq" if groq_key else "ollama"
    analysis_model = _GROQ_ANALYSIS_MODEL if groq_key else model

    return {
        "scorer_backend": backend,
        "scorer_model": scorer_model,
        "scorer_parallel": parallel,
        "analysis_backend": analysis_backend,
        "analysis_model": analysis_model,
        "groq_available": bool(groq_key),
        "ollama_available": ollama_up,
        "anthropic_available": bool(anthropic_key),
    }
