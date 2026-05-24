from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.activity_log import utc_now


class ModelEvaluator:
    def __init__(self, log_path: str | Path):
        self.log_path = Path(log_path)
        self.records: list[dict[str, Any]] = []

    def load(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.records.clear()
        if not self.log_path.exists():
            return
        with self.log_path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                try:
                    self.records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    def log_attempt(
        self,
        profile: str,
        model: str | None,
        task_type: str,
        persona: str,
        ok: bool,
        elapsed_seconds: float | None = None,
        error: str = "",
    ) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "created_at": utc_now(),
            "profile": profile,
            "model": model,
            "task_type": task_type,
            "persona": persona,
            "ok": ok,
            "elapsed_seconds": elapsed_seconds,
            "error": error[:500] if error else "",
        }
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.records.append(record)

    def summary(self) -> dict[str, Any]:
        stats: dict[str, dict[str, Any]] = {}
        for record in self.records:
            profile = record.get("profile") or "unknown"
            item = stats.setdefault(profile, {"attempts": 0, "successes": 0, "failures": 0, "elapsed_total": 0.0})
            item["attempts"] += 1
            if record.get("ok"):
                item["successes"] += 1
            else:
                item["failures"] += 1
            if isinstance(record.get("elapsed_seconds"), (int, float)):
                item["elapsed_total"] += float(record["elapsed_seconds"])
        for item in stats.values():
            attempts = item["attempts"] or 1
            item["success_rate"] = round(item["successes"] / attempts, 3)
            item["average_elapsed_seconds"] = round(item["elapsed_total"] / attempts, 3)
            del item["elapsed_total"]
        return {"ok": True, "profiles": stats, "records": len(self.records)}

    def choose_profile_order(self, primary: str, fallback: str) -> list[str]:
        # Conservative auto-selection. Do not override until there is enough data.
        summary = self.summary().get("profiles", {})
        primary_stats = summary.get(primary)
        fallback_stats = summary.get(fallback)
        order = [primary]
        if fallback not in order:
            order.append(fallback)
        if not primary_stats or not fallback_stats:
            return order
        if fallback_stats.get("attempts", 0) < 3:
            return order
        primary_rate = primary_stats.get("success_rate", 0)
        fallback_rate = fallback_stats.get("success_rate", 0)
        if fallback_rate >= 0.8 and primary_rate < 0.5:
            return [fallback, primary]
        return order
