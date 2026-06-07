"""
Manual session saver — use this when institutional SSO requires Duo MFA.

Steps:
  1. Run this script: python scripts/save_browser_session.py
  2. A visible browser window opens at your proxy/SSO login page.
  3. Log in normally (including Duo if prompted).
  4. Once you land on the database search page, press Enter here.
  5. The session is saved to outputs/.auth/<db>_session.json.
     The pipeline loads it automatically at the paywalled-DB step.

The pipeline always prompts for a fresh session at the start of each run
so you typically do not need to run this script manually.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from sourcing_agent.databases.browser_scraper import (  # noqa: E402
    prompt_and_save_session,
)

_PROXY_VARS = {
    "Web of Science": "WOS_PROXY_URL",
    "Scopus": "SCOPUS_PROXY_URL",
    "IEEE Xplore": "IEEE_PROXY_URL",
}


async def main() -> None:
    print("\nManual browser session saver")
    print("This opens a headed browser for each database you choose.\n")

    names = list(_PROXY_VARS.keys())
    for i, name in enumerate(names, 1):
        print(f"  {i}. {name}")
    print("  a. All databases")
    print("  q. Quit")

    choice = input("\nChoose database(s): ").strip().lower()

    if choice == "q":
        return
    elif choice == "a":
        selected = names
    else:
        try:
            idx = int(choice) - 1
            selected = [names[idx]]
        except (ValueError, IndexError):
            print("Invalid choice.")
            return

    for name in selected:
        proxy_url = os.environ.get(_PROXY_VARS[name], "")
        if not proxy_url or "your-institution" in proxy_url:
            print(f"  [{name}] Skipped — {_PROXY_VARS[name]} not set in .env")
            continue
        await prompt_and_save_session(name, proxy_url)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
