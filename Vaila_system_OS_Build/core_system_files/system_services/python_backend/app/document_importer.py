import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from app.memory_taxonomy import categorize_memory
from app.schemas import DocumentChunk, ImportReport, MemoryCandidate, SourceDocument


SUPPORTED_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".log"}
KEY_SIGNAL_WORDS = (
    "must", "should", "need", "needs", "required", "requirement", "rule",
    "decision", "priority", "phase", "architecture", "memory", "persona",
    "router", "model", "tool", "agent", "approval", "sync", "home jane", "vaila",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def stable_hash(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:length]


class DocumentImporter:
    def __init__(self, project_root: str | Path, report_path: str | Path | None = None):
        self.project_root = Path(project_root)
        self.report_path = Path(report_path) if report_path else self.project_root / "data" / "imports" / "reports" / "import_reports.jsonl"

    def import_document(
        self,
        path: str | Path,
        tags: list[str] | None = None,
        persona_scope: list[str] | None = None,
    ) -> tuple[ImportReport, list[MemoryCandidate]]:
        source_path = Path(path).expanduser()
        if not source_path.is_absolute():
            source_path = (Path.cwd() / source_path).resolve()

        if not source_path.exists():
            raise FileNotFoundError(f"Document not found: {source_path}")
        if not source_path.is_file():
            raise ValueError(f"Path is not a file: {source_path}")

        file_type = source_path.suffix.lower()
        if file_type not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {file_type}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        text, warnings = self._read_text(source_path, file_type)
        if not text.strip():
            raise ValueError(f"Document had no readable text: {source_path}")

        sha256 = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
        document_id = f"doc_{stable_hash(str(source_path) + sha256, 16)}"
        chunks = self._chunk_text(text, document_id=document_id)
        imported_at = utc_now()
        title = source_path.name
        relative_or_absolute = self._display_path(source_path)

        document = SourceDocument(
            id=document_id,
            path=relative_or_absolute,
            title=title,
            file_type=file_type,
            sha256=sha256,
            imported_at=imported_at,
            char_count=len(text),
            chunk_count=len(chunks),
        )

        candidates = self._build_candidates(
            document=document,
            chunks=chunks,
            text=text,
            tags=tags or [],
            persona_scope=persona_scope or ["all"],
            created_at=imported_at,
        )

        report = ImportReport(
            document=document,
            candidates_created=len(candidates),
            candidate_ids=[candidate.id for candidate in candidates],
            warnings=warnings,
        )
        self._append_report(report)
        return report, candidates

    def _read_text(self, path: Path, file_type: str) -> tuple[str, list[str]]:
        warnings: list[str] = []
        raw = path.read_text(encoding="utf-8", errors="replace")

        if file_type == ".json":
            try:
                parsed = json.loads(raw)
                return json.dumps(parsed, ensure_ascii=False, indent=2), warnings
            except json.JSONDecodeError as error:
                warnings.append(f"JSON parse failed, imported as raw text: {error}")
                return raw, warnings

        return raw, warnings

    def _chunk_text(self, text: str, document_id: str, max_chars: int = 2500, overlap: int = 250) -> list[DocumentChunk]:
        cleaned = text.replace("\r\n", "\n")
        chunks: list[DocumentChunk] = []
        start = 0
        index = 1

        while start < len(cleaned):
            end = min(start + max_chars, len(cleaned))
            if end < len(cleaned):
                newline = cleaned.rfind("\n", start, end)
                if newline > start + max_chars // 2:
                    end = newline

            chunk_text = cleaned[start:end].strip()
            if chunk_text:
                chunks.append(
                    DocumentChunk(
                        id=f"{document_id}_chunk_{index:03d}",
                        document_id=document_id,
                        index=index,
                        text=chunk_text,
                    )
                )
                index += 1

            if end >= len(cleaned):
                break
            start = max(0, end - overlap)

        return chunks

    def _build_candidates(
        self,
        document: SourceDocument,
        chunks: list[DocumentChunk],
        text: str,
        tags: list[str],
        persona_scope: list[str],
        created_at: str,
    ) -> list[MemoryCandidate]:
        base_tags = self._clean_tags(["document_import", document.file_type.lstrip("."), *tags])
        candidates: list[MemoryCandidate] = []

        summary = self._summarize_text(text)
        candidates.append(
            self._candidate(
                document=document,
                question=f"What important context was imported from {document.title}?",
                answer=summary,
                tags=[*base_tags, "summary"],
                persona_scope=persona_scope,
                chunk_ids=[chunk.id for chunk in chunks[:2]],
                created_at=created_at,
                seed="summary",
            )
        )

        for heading, body in self._extract_markdown_sections(text)[:8]:
            answer = self._summarize_text(body, max_sentences=4, max_chars=900)
            if len(answer) < 80:
                continue
            candidates.append(
                self._candidate(
                    document=document,
                    question=f"What does '{heading}' say in {document.title}?",
                    answer=answer,
                    tags=[*base_tags, "section"],
                    persona_scope=persona_scope,
                    chunk_ids=self._matching_chunk_ids(chunks, body),
                    created_at=created_at,
                    seed=f"section:{heading}",
                )
            )

        signal_lines = self._extract_signal_lines(text)
        if signal_lines:
            candidates.append(
                self._candidate(
                    document=document,
                    question=f"What rules, decisions, or requirements appear in {document.title}?",
                    answer="\n".join(f"- {line}" for line in signal_lines[:12]),
                    tags=[*base_tags, "rules", "decisions", "requirements"],
                    persona_scope=persona_scope,
                    chunk_ids=[chunk.id for chunk in chunks[:4]],
                    created_at=created_at,
                    seed="signals",
                )
            )

        return self._dedupe_candidates(candidates)

    def _candidate(
        self,
        document: SourceDocument,
        question: str,
        answer: str,
        tags: list[str],
        persona_scope: list[str],
        chunk_ids: list[str],
        created_at: str,
        seed: str,
    ) -> MemoryCandidate:
        candidate_id = f"candidate_{stable_hash(document.id + seed + question + answer, 18)}"
        clean_tags = self._clean_tags(tags)
        category = categorize_memory(question, answer, clean_tags)
        if category not in clean_tags:
            clean_tags.append(category)
        return MemoryCandidate(
            id=candidate_id,
            question=normalize_space(question),
            answer=answer.strip(),
            tags=clean_tags,
            persona_scope=persona_scope,
            confidence="medium",
            source_type="document_import",
            source_document_id=document.id,
            source_path=document.path,
            source_title=document.title,
            chunk_ids=chunk_ids,
            status="pending",
            created_at=created_at,
            category=category,
        )

    def _summarize_text(self, text: str, max_sentences: int = 6, max_chars: int = 1200) -> str:
        cleaned = normalize_space(text)
        if len(cleaned) <= max_chars:
            return cleaned

        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        selected: list[str] = []
        char_count = 0
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if char_count + len(sentence) > max_chars:
                break
            selected.append(sentence)
            char_count += len(sentence)
            if len(selected) >= max_sentences:
                break

        if selected:
            return " ".join(selected)
        return cleaned[:max_chars].rsplit(" ", 1)[0].strip()

    def _extract_markdown_sections(self, text: str) -> list[tuple[str, str]]:
        lines = text.splitlines()
        sections: list[tuple[str, list[str]]] = []
        current_heading = "Overview"
        current_body: list[str] = []

        for line in lines:
            heading_match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
            if heading_match:
                if current_body:
                    sections.append((current_heading, current_body))
                current_heading = heading_match.group(1).strip()
                current_body = []
            else:
                current_body.append(line)

        if current_body:
            sections.append((current_heading, current_body))

        return [(heading, "\n".join(body).strip()) for heading, body in sections if "\n".join(body).strip()]

    def _extract_signal_lines(self, text: str) -> list[str]:
        results: list[str] = []
        seen: set[str] = set()

        for raw_line in text.splitlines():
            line = normalize_space(raw_line.strip(" -\t"))
            if len(line) < 25 or len(line) > 280:
                continue
            lower = line.lower()
            if any(word in lower for word in KEY_SIGNAL_WORDS):
                if line not in seen:
                    results.append(line)
                    seen.add(line)
            if len(results) >= 20:
                break

        return results

    def _matching_chunk_ids(self, chunks: list[DocumentChunk], text: str) -> list[str]:
        sample = normalize_space(text[:250]).lower()
        if not sample:
            return []
        matches = [chunk.id for chunk in chunks if sample[:80] in normalize_space(chunk.text).lower()]
        return matches[:3]

    def _dedupe_candidates(self, candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
        seen: set[str] = set()
        unique: list[MemoryCandidate] = []
        for candidate in candidates:
            fingerprint = stable_hash(candidate.question.lower() + candidate.answer.lower(), 24)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            unique.append(candidate)
        return unique

    def _append_report(self, report: ImportReport) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        with self.report_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(report.to_dict(), ensure_ascii=False) + "\n")

    def _display_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.project_root))
        except ValueError:
            return str(path)

    @staticmethod
    def _clean_tags(tags: list[str]) -> list[str]:
        cleaned: list[str] = []
        for tag in tags:
            safe = re.sub(r"[^a-zA-Z0-9_\-]+", "_", tag.strip().lower()).strip("_")
            if safe and safe not in cleaned:
                cleaned.append(safe)
        return cleaned
