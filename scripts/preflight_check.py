"""Pre-flight checks for sourcing run."""
from dotenv import load_dotenv

load_dotenv()
import os

placeholders = ("your_email", "your_password", "placeholder", "your-institution")

creds = {
    "IEEE": ("IEEE_USERNAME", "IEEE_PASSWORD", "IEEE_PROXY_URL"),
    "WoS": ("WOS_USERNAME", "WOS_PASSWORD", "WOS_PROXY_URL"),
    "Scopus": ("SCOPUS_USERNAME", "SCOPUS_PASSWORD", "SCOPUS_PROXY_URL"),
    "ACM": ("ACM_USERNAME", "ACM_PASSWORD", "ACM_PROXY_URL"),
}
for db, (u, p, px) in creds.items():
    uv = os.environ.get(u, "")
    pv = os.environ.get(p, "")
    pxv = os.environ.get(px, "")
    real = all([uv, pv, pxv]) and not any(ph in uv + pv + pxv for ph in placeholders)
    print(f"  {db}: {'OK' if real else 'MISSING/PLACEHOLDER'}")

print(f"  S2_API_KEY: {'OK' if os.environ.get('S2_API_KEY','') else 'not set (10 req/s limit)'}")
print(f"  GROQ_API_KEY: {'OK' if os.environ.get('GROQ_API_KEY','') else 'not set'}")
print(f"  SCORER_BACKEND: {os.environ.get('SCORER_BACKEND','not set')}")
print(f"  ZOTERO_API_KEY: {'OK' if os.environ.get('ZOTERO_API_KEY','') else 'not set'}")
print(f"  ZOTERO_LIBRARY_ID: {os.environ.get('ZOTERO_LIBRARY_ID','not set')}")
