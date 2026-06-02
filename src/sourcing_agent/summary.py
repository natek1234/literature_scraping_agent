from __future__ import annotations

import datetime
import os

_DB_ORDER = [
    "Semantic Scholar",
    "arXiv",
    "IEEE Xplore",
    "Web of Science",
    "Scopus",
    "ACM Digital Library",
    "NASA Technical Reports Server",
]

_WIDTH = 72


class SummaryWriter:
    """Writes a concise, human-readable sourcing progress summary to disk.

    Call update_* methods as the pipeline progresses; each call rewrites
    the summary file atomically so it always reflects current state.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self._run_id = ""
        self._project = ""
        self._status = "starting"
        self._started = ""
        self._db: dict[str, dict] = {}  # name -> {count, note, done}
        self._raw_total = 0
        self._dedup_unique = 0
        self._dedup_removed = 0
        self._dedup_done = False
        self._scoring: dict[str, int] = {
            "total": 0,
            "scored": 0,
            "include": 0,
            "maybe": 0,
            "exclude": 0,
            "errors": 0,
        }
        self._zotero = "not started"
        self._excel = "not started"

    def init(self, run_id: str, project: str) -> None:
        self._run_id = run_id
        self._project = project
        self._started = _now()
        self._status = "querying databases"
        self._write()

    def update_db(self, name: str, count: int, note: str = "") -> None:
        self._db[name] = {"count": count, "note": note}
        self._raw_total = sum(v["count"] for v in self._db.values())
        self._write()

    def update_dedup(self, unique: int, removed: int) -> None:
        self._dedup_unique = unique
        self._dedup_removed = removed
        self._dedup_done = True
        self._status = "scoring"
        self._write()

    def update_scoring(
        self,
        total: int,
        scored: int,
        include: int,
        maybe: int,
        exclude: int,
        errors: int,
    ) -> None:
        self._scoring = {
            "total": total,
            "scored": scored,
            "include": include,
            "maybe": maybe,
            "exclude": exclude,
            "errors": errors,
        }
        self._write()

    def update_zotero(self, status: str) -> None:
        self._zotero = status
        self._write()

    def update_excel(self, status: str) -> None:
        self._excel = status
        self._status = "complete"
        self._write()

    def mark_complete(self) -> None:
        self._status = "complete"
        self._write()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _write(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        content = self._render()
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(content)

    def _render(self) -> str:
        lines: list[str] = []
        sep = "=" * _WIDTH

        lines += [
            sep,
            f"  SOURCING SUMMARY  |  {self._run_id}",
            sep,
            f"  Project : {self._project}",
            f"  Status  : {self._status.upper()}",
            f"  Started : {self._started}",
            f"  Updated : {_now()}",
            "",
            "DATABASE QUERIES",
        ]

        # Column widths
        name_w = max(len(n) for n in _DB_ORDER)
        count_w = 7

        for name in _DB_ORDER:
            if name not in self._db:
                lines.append(f"  {name:<{name_w}}  {'—':>{count_w}}    pending")
                continue
            info = self._db[name]
            note: str = info.get("note", "") or ""
            count: int = info["count"]
            count_str = f"{count:,}" if count else "0"

            if "skipped — add credentials" in note:
                status = f"SKIPPED  ({note})"
            elif "resumed from cache" in note:
                status = f"cached   {count_str} papers"
            elif count > 0:
                status = f"OK       {count_str} papers"
            else:
                status = f"0 results  ({note})" if note else "0 results"

            lines.append(f"  {name:<{name_w}}  {status}")

        lines.append("  " + "-" * (name_w + count_w + 14))
        lines.append(f"  {'Raw total':<{name_w}}  {self._raw_total:>{count_w},}")

        if self._dedup_done:
            lines.append(
                f"  {'After deduplication':<{name_w}}  {self._dedup_unique:>{count_w},}"
                f"    (removed {self._dedup_removed:,} duplicates)"
            )

        lines += ["", "SCORING"]

        sc = self._scoring
        if sc["total"] > 0:
            pct = int(sc["scored"] / sc["total"] * 100) if sc["total"] else 0
            lines += [
                f"  Progress  :  {sc['scored']:>5,} / {sc['total']:,}  ({pct}%)",
                f"  Include   :  {sc['include']:>5,}",
                f"  Maybe     :  {sc['maybe']:>5,}",
                f"  Exclude   :  {sc['exclude']:>5,}",
            ]
            if sc["errors"]:
                lines.append(
                    f"  Errors    :  {sc['errors']:>5,}"
                    "  ← check ANTHROPIC_API_KEY in .env"
                )
        else:
            lines.append("  not started")

        lines += [
            "",
            "OUTPUTS",
            f"  Zotero    : {self._zotero}",
            f"  Excel     : {self._excel}",
            sep,
        ]

        return "\n".join(lines) + "\n"


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
