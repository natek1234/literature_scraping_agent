"""Audit Zotero SpaceAutonomy_Review_2026 before clearing."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from pyzotero import zotero

z = zotero.Zotero(os.environ["ZOTERO_LIBRARY_ID"], "user", os.environ["ZOTERO_API_KEY"])
total = z.count_items()
print(f"Library total: {total} items")

all_cols = z.everything(z.collections())
target = next((c for c in all_cols if c["data"]["name"] == "SpaceAutonomy_Review_2026"), None)
if not target:
    print("ERROR: SpaceAutonomy_Review_2026 not found")
    sys.exit(1)

key = target["key"]
print(f"Found SpaceAutonomy_Review_2026: key={key}")

top_items = z.everything(z.collection_items(key))
print(f"Items in top-level collection: {len(top_items)}")

subcols = [c for c in all_cols if c["data"].get("parentCollection") == key]
print(f"Subcollections: {len(subcols)}")
grand_total = len(top_items)
for sc in subcols:
    sc_items = z.everything(z.collection_items(sc["key"]))
    print(f"  {sc['data']['name']}: {len(sc_items)} items")
    grand_total += len(sc_items)

print(f"Total items across all subcollections: {grand_total}")
