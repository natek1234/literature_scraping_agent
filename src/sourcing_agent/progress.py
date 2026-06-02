from __future__ import annotations

import datetime
import os

import yaml
from loguru import logger


class ProgressTracker:
    def __init__(self, progress_file: str = "./outputs/sourcing-progress.txt") -> None:
        self.progress_file = progress_file
        self._data: dict = {}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _load(self) -> dict:
        if os.path.exists(self.progress_file):
            with open(self.progress_file, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return data
        return {}

    def _save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self.progress_file) or ".", exist_ok=True)
        with open(self.progress_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def initialise(self, project_title: str) -> None:
        run_id = datetime.datetime.now().strftime("run_%Y%m%d_%H%M%S")
        self._data = {
            "RUN_ID": run_id,
            "PROJECT": project_title,
            "STATUS": "in_progress",
            "STEPS_COMPLETED": {},
            "PRISMA": {},
            "SCORING": {"total": 0, "scored": 0, "errors": 0, "last_batch_index": 0},
            "RESULTS": {"include": 0, "maybe": 0, "exclude": 0, "by_kunze": {}},
            "CLUSTER_CONFIDENCE": {"high": 0, "medium": 0, "low": 0},
            "RESUME_FROM": "config_loaded",
        }
        self._save(self._data)

    def load_or_init(self, project_title: str) -> None:
        existing = self._load()
        if existing and existing.get("STATUS") == "in_progress":
            self._data = existing
            logger.info(
                f"Resuming run {existing.get('RUN_ID')} from {existing.get('RESUME_FROM')}"
            )
        else:
            self.initialise(project_title)

    def write_checkpoint(self, step: str, data: dict | None = None) -> None:
        self._data = self._load()
        if "STEPS_COMPLETED" not in self._data:
            self._data["STEPS_COMPLETED"] = {}
        self._data["STEPS_COMPLETED"][step] = True
        if data:
            for k, v in data.items():
                # Flat keys go into STEPS_COMPLETED metadata; nested go into top-level
                if k in (
                    "retrieved",
                    "unique",
                    "doi_dupes",
                    "fuzzy_dupes",
                    "total",
                    "scored",
                    "errors",
                ):
                    if "SCORING" in self._data and k in ("total", "scored", "errors"):
                        self._data["SCORING"][k] = v
                    else:
                        self._data["STEPS_COMPLETED"][f"{step}_{k}"] = v
                elif k == "last_batch_index":
                    self._data["SCORING"]["last_batch_index"] = v
                elif k == "scored_so_far":
                    self._data["SCORING"]["scored"] = v
                elif k == "status":
                    self._data["STATUS"] = v
                else:
                    self._data["STEPS_COMPLETED"][f"{step}_{k}"] = v
        self._data["RESUME_FROM"] = step
        self._save(self._data)
        logger.debug(f"Checkpoint written: {step}")

    def is_step_complete(self, step: str) -> bool:
        data = self._load()
        return bool(data.get("STEPS_COMPLETED", {}).get(step, False))

    def invalidate_step(self, step: str) -> None:
        """Remove a step from STEPS_COMPLETED so it will be re-run."""
        self._data = self._load()
        steps = self._data.get("STEPS_COMPLETED", {})
        steps.pop(step, None)
        self._data["STEPS_COMPLETED"] = steps
        self._save(self._data)
        logger.debug(f"Step invalidated: {step}")

    def log_prisma_count(self, stage: str, db: str, count: int) -> None:
        self._data = self._load()
        if "PRISMA" not in self._data:
            self._data["PRISMA"] = {}
        key = f"{db.lower().replace(' ', '_')}_{stage}"
        self._data["PRISMA"][key] = count
        self._save(self._data)

    def get_prisma_table(self) -> list[dict]:
        data = self._load()
        prisma = data.get("PRISMA", {})
        rows = []
        for key, count in prisma.items():
            parts = key.rsplit("_", 1)
            if len(parts) == 2:
                rows.append({"stage": parts[1], "database": parts[0], "count": count})
            else:
                rows.append({"stage": key, "database": "all", "count": count})
        return rows

    def update_results(
        self,
        include: int,
        maybe: int,
        exclude: int,
        by_kunze: dict,
        cluster_confidence: dict,
    ) -> None:
        self._data = self._load()
        self._data["RESULTS"] = {
            "include": include,
            "maybe": maybe,
            "exclude": exclude,
            "by_kunze": by_kunze,
        }
        self._data["CLUSTER_CONFIDENCE"] = cluster_confidence
        self._save(self._data)

    def mark_complete(self) -> None:
        self._data = self._load()
        self._data["STATUS"] = "complete"
        self._save(self._data)
        logger.info("Pipeline complete — progress file updated.")

    @property
    def run_id(self) -> str:
        return self._data.get("RUN_ID", "unknown")

    @property
    def last_batch_index(self) -> int:
        data = self._load()
        return int(data.get("SCORING", {}).get("last_batch_index", 0))
