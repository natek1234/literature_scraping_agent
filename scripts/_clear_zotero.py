"""Clear all items from SpaceAutonomy_Review_2026 and its subcollections.

Collects unique item keys across the whole collection hierarchy, deletes
items in batches of 50 using a fresh library version before each delete
(same pattern as zotero_writer.py) to avoid HTTP 412 errors, then deletes
all collections so the pipeline recreates the structure fresh on next run.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from pyzotero import zotero

TOP_COLLECTION = "SpaceAutonomy_Review_2026"
BATCH_SIZE = 50
MAX_RETRIES = 3


def main() -> None:
    z = zotero.Zotero(
        os.environ["ZOTERO_LIBRARY_ID"], "user", os.environ["ZOTERO_API_KEY"]
    )

    # ── Locate top-level collection ──────────────────────────────────────────
    all_cols = z.everything(z.collections())
    top = next((c for c in all_cols if c["data"]["name"] == TOP_COLLECTION), None)
    if not top:
        print(f"ERROR: {TOP_COLLECTION} not found in library")
        sys.exit(1)

    top_key = top["key"]
    print(f"Found {TOP_COLLECTION}: key={top_key}")

    subcols = [c for c in all_cols if c["data"].get("parentCollection") == top_key]
    all_col_keys = [top_key] + [sc["key"] for sc in subcols]

    # ── Collect unique items across the hierarchy ────────────────────────────
    seen_keys: set[str] = set()
    all_items: list[dict] = []
    for col_key in all_col_keys:
        for item in z.everything(z.collection_items(col_key)):
            if item["key"] not in seen_keys:
                seen_keys.add(item["key"])
                all_items.append(item)

    print(f"Unique items to delete: {len(all_items)}")
    print(f"Subcollections to delete: {len(subcols)}")

    if not all_items and not subcols:
        print("Nothing to delete — collection is already empty.")
        return

    # ── Delete items in batches using fresh library version each time ────────
    deleted = 0
    for start in range(0, len(all_items), BATCH_SIZE):
        batch = all_items[start : start + BATCH_SIZE]
        for attempt in range(MAX_RETRIES):
            try:
                # Fetch current library version immediately before DELETE
                # (same approach as zotero_writer.py to avoid HTTP 412).
                last_modified = z.last_modified_version()
                z.delete_item(batch, last_modified=last_modified)
                deleted += len(batch)
                print(f"  Deleted {deleted}/{len(all_items)} items")
                time.sleep(0.25)
                break
            except Exception as exc:
                err = str(exc)
                is_412 = "412" in err or "precondition" in err.lower()
                if is_412 and attempt < MAX_RETRIES - 1:
                    print(f"  412 on batch {start // BATCH_SIZE + 1}, retry {attempt + 1}")
                    time.sleep(1)
                else:
                    print(f"  WARNING: batch {start // BATCH_SIZE + 1} failed: {exc}")
                    break

    # ── Delete subcollections ────────────────────────────────────────────────
    for sc in subcols:
        try:
            z.delete_collection(sc)
            print(f"  Deleted subcollection: {sc['data']['name']}")
        except Exception as exc:
            print(f"  WARNING: could not delete {sc['data']['name']}: {exc}")

    # ── Delete top-level collection ──────────────────────────────────────────
    try:
        fresh_top = next(
            (c for c in z.everything(z.collections()) if c["key"] == top_key), top
        )
        z.delete_collection(fresh_top)
        print(f"  Deleted top-level collection: {TOP_COLLECTION}")
    except Exception as exc:
        print(f"  WARNING: could not delete top-level collection: {exc}")

    print(f"\nDone — {deleted} items deleted, {len(subcols) + 1} collections removed.")
    print("The pipeline will recreate the collection structure on next run.")


if __name__ == "__main__":
    main()
