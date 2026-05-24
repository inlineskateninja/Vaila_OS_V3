import json
from datetime import date, datetime, timezone
from pathlib import Path

from app.memory_taxonomy import path_for_category
from app.schemas import MemoryRecord


STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "this", "that", "it", "as", "by",
    "from", "what", "how", "why", "when", "where", "do", "does", "should",
}


def normalize_words(text: str) -> set[str]:
    clean = "".join(char.lower() if char.isalnum() else " " for char in text)
    return {word for word in clean.split() if word and word not in STOPWORDS}


def utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def age_days(record: MemoryRecord) -> int | None:
    value = record.last_updated or record.created_at
    if not value:
        return None
    try:
        return (date.today() - date.fromisoformat(value[:10])).days
    except ValueError:
        return None


def recency_bucket(record: MemoryRecord) -> str:
    age = age_days(record)
    if age is None:
        return "undated"
    if age <= 7:
        return "recent"
    if age <= 90:
        return "active"
    return "long_term"


def depreciation_score(record: MemoryRecord) -> float:
    age = age_days(record)
    if age is None:
        return 0.0
    if age <= 7:
        return 3.0
    if age <= 30:
        return 1.5
    if age <= 90:
        return 0.5
    return -0.5


class MemoryStore:
    def __init__(self, memory_root: str | Path):
        self.memory_root = Path(memory_root)
        self.records: list[MemoryRecord] = []

    def load(self) -> None:
        self.records.clear()
        self.memory_root.mkdir(parents=True, exist_ok=True)

        for path in self.memory_root.rglob("*.jsonl"):
            self._load_jsonl(path)

    def _load_jsonl(self, path: Path) -> None:
        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    self.records.append(MemoryRecord.from_dict(data))
                except json.JSONDecodeError as error:
                    print(f"Skipping invalid JSON in {path}, line {line_number}: {error}")

    def append_record(
        self,
        record: MemoryRecord,
        relative_path: str | None = None,
    ) -> Path:
        if not record.last_updated:
            record.last_updated = utc_today()
        if not record.created_at:
            record.created_at = record.last_updated
        relative_path = relative_path or path_for_category(record.category)
        target_path = self.memory_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        existing_ids = {existing.id for existing in self.records}
        if record.id in existing_ids:
            raise ValueError(f"Memory record already exists: {record.id}")

        with target_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

        self.records.append(record)
        return target_path

    def search(
        self,
        query: str,
        persona: str = "proto_jane",
        tags: list[str] | None = None,
        limit: int = 5,
        category: str | None = None,
        prefer_recent: bool = True,
    ) -> list[MemoryRecord]:
        return [record for score, record in self.search_scored(query, persona, tags, limit, category, prefer_recent)]

    def search_scored(
        self,
        query: str,
        persona: str = "proto_jane",
        tags: list[str] | None = None,
        limit: int = 5,
        category: str | None = None,
        prefer_recent: bool = True,
    ) -> list[tuple[float, MemoryRecord]]:
        tags = tags or []
        query_words = normalize_words(query)
        tag_set = set(tags)

        scored: list[tuple[float, MemoryRecord]] = []

        for record in self.records:
            if category and record.category != category:
                continue
            score = 0.0

            memory_text = f"{record.question} {record.answer} {' '.join(record.tags)} {record.category}"
            memory_words = normalize_words(memory_text)

            overlap = query_words.intersection(memory_words)
            score += len(overlap) * 2

            record_tags = set(record.tags)
            tag_overlap = tag_set.intersection(record_tags)
            score += len(tag_overlap) * 4

            scope = set(record.persona_scope)
            if "all" in scope:
                score += 2
            if persona in scope:
                score += 4

            if record.confidence == "high":
                score += 1

            if prefer_recent:
                score += depreciation_score(record)

            score *= max(record.relevance_score, 0.1)

            if score > 0:
                scored.append((score, record))

        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[:limit]

    def category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.records:
            counts[record.category] = counts.get(record.category, 0) + 1
        return dict(sorted(counts.items()))

    def recency_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.records:
            bucket = recency_bucket(record)
            counts[bucket] = counts.get(bucket, 0) + 1
        return dict(sorted(counts.items()))
