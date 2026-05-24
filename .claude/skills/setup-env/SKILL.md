---
name: setup-env
description: >
  First-time environment setup for the literature sourcing agent. Installs
  all dependencies, configures MCP servers, validates credentials, and
  creates the project scaffold. Run this once before the first sourcing run
  on a new machine.
allowed-tools: Read, Write, Edit, Bash, Glob
---

# /setup-env — First-Time Environment Setup

Run this once when setting up the agent on a new machine or after cloning
the repository. It is safe to re-run — all steps are idempotent.

---

## Step 1 — Check Python version

```bash
python --version
```

Require Python 3.11+. If the version is lower, stop and tell the user:
"Python 3.11 or higher is required. Please install it from python.org or
via your package manager (e.g. `brew install python@3.11` on macOS,
`sudo apt install python3.11` on Ubuntu)."

---

## Step 2 — Install Python dependencies

```bash
pip install -e ".[dev]" --break-system-packages
```

If `pyproject.toml` does not exist, tell the user it is missing and stop.

Verify the install:
```bash
python -c "
import anthropic, requests, aiohttp, httpx, tenacity, \
       playwright.async_api, feedparser, \
       openpyxl, pyzotero, rapidfuzz, loguru, dotenv, yaml, pydantic
print('All dependencies installed successfully.')
"
```

---

## Step 3 — Install Playwright browser

```bash
python -m playwright install chromium --with-deps
```

This downloads the Chromium browser used for paywalled database automation.

---

## Step 4 — Install Zotero MCP server

```bash
pip install zotero-mcp-server --break-system-packages
zotero-mcp setup
```

If `zotero-mcp` is already installed, this is a no-op.

Then verify `.mcp.json` exists in the project root. If it does not exist,
create it:

```json
{
  "mcpServers": {
    "zotero": {
      "command": "zotero-mcp",
      "env": {
        "ZOTERO_LOCAL": "true",
        "ZOTERO_API_KEY": "${ZOTERO_API_KEY}",
        "ZOTERO_LIBRARY_ID": "${ZOTERO_LIBRARY_ID}"
      }
    }
  }
}
```

Tell the user: "`.mcp.json` has been created. Restart Claude Code to
activate the Zotero MCP connection."

---

## Step 5 — Check or create .env

Read `.env` if it exists. If it does not, create it from this template
and tell the user to fill in their credentials:

```bash
cat > .env << 'EOF'
# ─── Zotero ──────────────────────────────────────────────────────────
ZOTERO_API_KEY=your_api_key_here
ZOTERO_LIBRARY_ID=your_library_id_here
ZOTERO_LOCAL=true

# ─── Open-access API keys (optional but recommended) ─────────────────
# Semantic Scholar: raises rate limit from 10 to 100 req/sec
S2_API_KEY=your_semantic_scholar_key_here
# NASA NTRS: no API key required (public API)

# ─── Paywalled databases (institutional credentials) ─────────────────
# IEEE Xplore
IEEE_USERNAME=your_email@institution.edu
IEEE_PASSWORD=your_password_here
IEEE_PROXY_URL=https://ezproxy.your-institution.edu

# Web of Science
WOS_USERNAME=your_email@institution.edu
WOS_PASSWORD=your_password_here
WOS_PROXY_URL=https://ezproxy.your-institution.edu

# Scopus
SCOPUS_USERNAME=your_email@institution.edu
SCOPUS_PASSWORD=your_password_here
SCOPUS_PROXY_URL=https://ezproxy.your-institution.edu

# ACM Digital Library
ACM_USERNAME=your_email@institution.edu
ACM_PASSWORD=your_password_here
ACM_PROXY_URL=https://ezproxy.your-institution.edu
EOF
```

Then check `.gitignore` — ensure it contains these entries. If `.gitignore`
does not exist, create it:

```
.env
outputs/
.claude/settings.local.json
__pycache__/
*.pyc
.pytest_cache/
dist/
*.egg-info/
```

---

## Step 6 — Validate credentials that are present

Load `.env` and test whichever credentials are filled in (skip blank ones):

**Zotero (if ZOTERO_API_KEY is set):**
```bash
python -c "
import os; from dotenv import load_dotenv; load_dotenv()
from pyzotero import zotero
z = zotero.Zotero(os.environ['ZOTERO_LIBRARY_ID'], 'user', os.environ['ZOTERO_API_KEY'])
count = z.count_items()
print(f'Zotero OK — library has {count} items')
"
```

**NASA NTRS (always available, no key needed):**
```bash
python -c "
import requests
r = requests.get('https://ntrs.nasa.gov/api/citations/search',
  params={'q': 'Mars rover autonomy', 'rows': 1})
print(f'NASA NTRS API OK — status {r.status_code}')
"
```

**Semantic Scholar (always available, no key needed):**
```bash
python -c "
import requests
r = requests.get('https://api.semanticscholar.org/graph/v1/paper/search',
  params={'query': 'autonomous robotics AI', 'limit': 1, 'fields': 'title'})
print(f'Semantic Scholar API OK — status {r.status_code}')
"
```

---

## Step 7 — Create output directory and scaffold

```bash
mkdir -p outputs src/sourcing_agent/databases src/sourcing_agent/pipeline src/sourcing_agent/output
touch src/__init__.py src/sourcing_agent/__init__.py
touch src/sourcing_agent/databases/__init__.py
touch src/sourcing_agent/pipeline/__init__.py
touch src/sourcing_agent/output/__init__.py
```

---

## Step 8 — Print setup summary

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Environment setup complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Python:              OK (3.x.x)
  Dependencies:        OK
  Playwright:          OK (Chromium installed)
  Zotero MCP:          OK / needs credentials
  .env:                created / already existed
  .gitignore:          OK
  NASA NTRS API:       OK
  Semantic Scholar:    OK
  Zotero connection:   OK / FAIL (see above)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Next steps:
  1. Fill in credentials in .env (if not already done)
     Required: ZOTERO_API_KEY, ZOTERO_LIBRARY_ID
     Recommended: S2_API_KEY
     Paywalled DBs: IEEE, WOS, SCOPUS, ACM credentials
  2. Edit CONTEXT.md for your research project
  3. Run /source-papers to start the pipeline
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
