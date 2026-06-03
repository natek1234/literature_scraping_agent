# Literature Sourcing Agent

Autonomous academic literature sourcing agent — Phase 1 of a two-phase pipeline.
Retrieves, scores, deduplicates, and stores candidate papers from multiple academic databases into Zotero.

## Quick start

```bash
/setup-env   # first-time setup
/source-papers  # start a sourcing run
```

## LLM Backend Setup

The pipeline uses a three-tier LLM backend for paper scoring and analysis.
No paid API subscription is required.

### Tier 1 — Groq (primary scorer, cloud, free)

Groq provides free API access to Llama 3.3 70B — a large, high-quality
model that produces reliable JSON scoring outputs without the retry overhead
of smaller local models. It is used as the default scorer **and** for all
post-processing analysis tasks (mission taxonomy, deployment lag, readiness
matrix).

Get a free API key at: https://console.groq.com (no credit card required)

**Set in `.env`:**
```
SCORER_BACKEND=groq
GROQ_API_KEY=your_key_here
```

Free tier limits (as of 2026):
- Llama 3.3 70B: 6,000 requests/day, 6,000 tokens/minute

A typical sourcing run of ~500–800 deduplicated papers comfortably fits
within the daily limit. The post-processing analysis uses ~50–55 additional
calls.

### Tier 2 — Ollama (local fallback, GPU required, optional)

Ollama runs a smaller model locally on your GPU and activates automatically
if Groq fails or is rate-limited. It is optional but recommended for
resilience and offline / development use.

Recommended model: `qwen2.5:7b`, which fits within 8 GB VRAM at 4-bit
quantisation.

**Installation:**

- Windows/macOS: Download from https://ollama.com
- Linux: `curl -fsSL https://ollama.com/install.sh | sh`

**Pull the scoring model and start the server:**
```bash
ollama pull qwen2.5:7b
ollama serve   # runs in background; starts automatically on Windows after install
```

**Verify GPU is active:**
```bash
ollama ps   # should show qwen2.5:7b with VRAM usage
```

**Set in `.env`:**
```
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_NUM_PARALLEL=4   # reduce to 2 if GPU memory is tight during scoring
```

> **GPU sizing:** This project uses an RTX 4060 Laptop (8 GB VRAM).
> With more VRAM you can use a larger fallback model:
> - 12 GB+: `ollama pull qwen2.5:14b` → `OLLAMA_MODEL=qwen2.5:14b`
> - 24 GB+: `ollama pull qwen2.5:32b` → `OLLAMA_MODEL=qwen2.5:32b`

To use Ollama as the **primary** scorer instead of Groq, set:
```
SCORER_BACKEND=ollama
```
In this mode the pipeline tries Ollama first (with a temperature-0 retry on
invalid JSON), then falls back to Groq.

### Tier 3 — Anthropic (explicit override, requires paid API credits)

If you have Anthropic API credits and want to use Claude for scoring,
set in `.env`:
```
SCORER_BACKEND=anthropic
ANTHROPIC_API_KEY=your_key_here
```

### Verifying your setup

After filling in `.env`, open Claude Code and run:
```
/setup-env
```

The pre-flight Check 7 will report which backends are available and
confirm the scoring and analysis models before any pipeline run.
