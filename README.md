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

### Tier 1 — Ollama (primary scorer, local, free)

Ollama runs the scoring model locally on your GPU. Recommended model:
`qwen2.5:7b`, which fits within 8 GB VRAM at 4-bit quantisation.

**Installation:**

- Windows/macOS: Download from https://ollama.com
- Linux: `curl -fsSL https://ollama.com/install.sh | sh`

**Pull the scoring model:**
```bash
ollama pull qwen2.5:7b
```

**Start the Ollama server (runs in background):**
```bash
ollama serve
```

**Verify GPU is being used (should show VRAM usage):**
```bash
ollama ps
```

**Set in `.env`:**
```
SCORER_BACKEND=ollama
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_NUM_PARALLEL=4   # reduce to 2 if GPU memory is tight during scoring
```

> **Note:** This project uses an RTX 4060 Laptop (8 GB VRAM). If your GPU has
> more VRAM, you may use a larger model:
> - 12 GB+: `ollama pull qwen2.5:14b` then set `OLLAMA_MODEL=qwen2.5:14b`
> - 24 GB+: `ollama pull qwen2.5:32b` then set `OLLAMA_MODEL=qwen2.5:32b`

### Tier 2 — Groq (analysis backend + scoring fallback, cloud, free)

Groq provides free API access to large models including Llama 3.3 70B.
It is used automatically for all post-processing analysis tasks (mission
taxonomy, deployment lag, readiness matrix) because these tasks benefit
from a larger model than the local 7B scorer.

Get a free API key at: https://console.groq.com (no credit card required)

**Set in `.env`:**
```
GROQ_API_KEY=your_key_here
```

Free tier limits (as of 2026):
- Llama 3.3 70B: 6,000 requests/day, 6,000 tokens/minute

The post-processing analysis requires approximately 50–55 total Groq calls,
well within the daily limit.

### Tier 3 — Anthropic (optional, requires paid API credits)

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
