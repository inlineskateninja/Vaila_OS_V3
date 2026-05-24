from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class MemoryRecord:
    id: str
    question: str
    answer: str
    tags: list[str] = field(default_factory=list)
    persona_scope: list[str] = field(default_factory=list)
    confidence: str = "medium"
    source_type: str = "unknown"
    last_updated: str = ""
    source_document_id: str = ""
    source_path: str = ""
    category: str = "general"
    created_at: str = ""
    relevance_score: float = 1.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryRecord":
        return cls(
            id=data.get("id", ""),
            question=data.get("question", ""),
            answer=data.get("answer", ""),
            tags=data.get("tags", []),
            persona_scope=data.get("persona_scope", []),
            confidence=data.get("confidence", "medium"),
            source_type=data.get("source_type", "unknown"),
            last_updated=data.get("last_updated", ""),
            source_document_id=data.get("source_document_id", ""),
            source_path=data.get("source_path", ""),
            category=data.get("category", "general"),
            created_at=data.get("created_at", data.get("last_updated", "")),
            relevance_score=float(data.get("relevance_score", 1.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_prompt_block(self) -> str:
        source_line = f"Source: {self.source_path}\n" if self.source_path else ""
        return (
            f"[Memory: {self.id}]\n"
            f"Question: {self.question}\n"
            f"Answer: {self.answer}\n"
            f"Tags: {', '.join(self.tags)}\n"
            f"Category: {self.category}\n"
            f"Last updated: {self.last_updated}\n"
            f"{source_line}"
        )


@dataclass
class MemoryCandidate:
    id: str
    question: str
    answer: str
    tags: list[str] = field(default_factory=list)
    persona_scope: list[str] = field(default_factory=lambda: ["all"])
    confidence: str = "medium"
    source_type: str = "document_import"
    source_document_id: str = ""
    source_path: str = ""
    source_title: str = ""
    chunk_ids: list[str] = field(default_factory=list)
    status: str = "pending"
    created_at: str = ""
    reviewed_at: str = ""
    review_note: str = ""
    category: str = "general"
    relevance_score: float = 1.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryCandidate":
        return cls(
            id=data.get("id", ""),
            question=data.get("question", ""),
            answer=data.get("answer", ""),
            tags=data.get("tags", []),
            persona_scope=data.get("persona_scope", ["all"]),
            confidence=data.get("confidence", "medium"),
            source_type=data.get("source_type", "document_import"),
            source_document_id=data.get("source_document_id", ""),
            source_path=data.get("source_path", ""),
            source_title=data.get("source_title", ""),
            chunk_ids=data.get("chunk_ids", []),
            status=data.get("status", "pending"),
            created_at=data.get("created_at", ""),
            reviewed_at=data.get("reviewed_at", ""),
            review_note=data.get("review_note", ""),
            category=data.get("category", "general"),
            relevance_score=float(data.get("relevance_score", 1.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_memory_record(self, approved_at: str) -> MemoryRecord:
        memory_id = self.id.replace("candidate_", "memory_", 1)
        return MemoryRecord(
            id=memory_id,
            question=self.question,
            answer=self.answer,
            tags=self.tags,
            persona_scope=self.persona_scope,
            confidence=self.confidence,
            source_type=self.source_type,
            last_updated=approved_at[:10],
            source_document_id=self.source_document_id,
            source_path=self.source_path,
            category=self.category,
            created_at=self.created_at,
            relevance_score=self.relevance_score,
        )

    def to_review_block(self) -> str:
        return (
            f"[{self.status.upper()}] {self.id}\n"
            f"Source: {self.source_title or self.source_path}\n"
            f"Question: {self.question}\n"
            f"Answer: {self.answer}\n"
            f"Tags: {', '.join(self.tags)}\n"
            f"Category: {self.category}\n"
        )


@dataclass
class SourceDocument:
    id: str
    path: str
    title: str
    file_type: str
    sha256: str
    imported_at: str
    char_count: int
    chunk_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DocumentChunk:
    id: str
    document_id: str
    index: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ImportReport:
    document: SourceDocument
    candidates_created: int
    candidate_ids: list[str]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document": self.document.to_dict(),
            "candidates_created": self.candidates_created,
            "candidate_ids": self.candidate_ids,
            "warnings": self.warnings,
        }

    def display(self) -> str:
        warnings = "\n".join(f"  - {warning}" for warning in self.warnings) or "  - None"
        candidate_ids = "\n".join(f"  - {candidate_id}" for candidate_id in self.candidate_ids) or "  - None"
        return (
            f"Imported: {self.document.title}\n"
            f"Document ID: {self.document.id}\n"
            f"File type: {self.document.file_type}\n"
            f"Characters: {self.document.char_count}\n"
            f"Chunks: {self.document.chunk_count}\n"
            f"Candidates created: {self.candidates_created}\n"
            f"Candidate IDs:\n{candidate_ids}\n"
            f"Warnings:\n{warnings}"
        )


@dataclass
class RequestEnvelope:
    id: str
    original_text: str
    normalized_text: str
    received_at: str
    source: str = "chat"
    response_type: str = "short_text"
    device_context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PromptInterpretation:
    schema_version: str = "prompt_interpretation.v1"
    ok: bool = False
    source: str = "not_run"
    interpreter_profile: str = "prompt_interpreter"
    interpreter_model: str = ""
    advised_task_type: str = ""
    advised_persona: str = ""
    advised_model_profile: str = ""
    advised_fallback_profile: str = ""
    confidence: float = 0.0
    intent_summary: str = ""
    refined_prompt: str = ""
    requested_operations: list[str] = field(default_factory=list)
    context_needs: list[str] = field(default_factory=list)
    tool_hints: list[str] = field(default_factory=list)
    response_goal: str = ""
    memory_queries: list[str] = field(default_factory=list)
    memory_tags: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str = ""
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RoutingComparison:
    status: str
    deterministic_task_type: str
    deterministic_persona: str
    deterministic_model_profile: str
    advised_task_type: str = ""
    advised_persona: str = ""
    advised_model_profile: str = ""
    task_type_match: bool = False
    persona_match: bool = False
    model_profile_match: bool = False
    has_disagreement: bool = False
    disagreements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RoutePlan:
    user_text: str
    task_type: str
    persona: str
    model_tier: str
    model_profile: str
    fallback_profile: str
    memory_queries: list[str]
    memory_tags: list[str]
    reasons: list[str]
    context_domain: str = "general"
    context_references: list[str] = field(default_factory=list)
    file_references: list[str] = field(default_factory=list)

    def display(self) -> str:
        return (
            f"Task type: {self.task_type}\n"
            f"Persona: {self.persona}\n"
            f"Context domain: {self.context_domain}\n"
            f"Model tier: {self.model_tier}\n"
            f"Model profile: {self.model_profile}\n"
            f"Fallback profile: {self.fallback_profile}\n"
            f"Context references:\n"
            + "\n".join(f"  - {reference}" for reference in self.context_references)
            + "\nFile references:\n"
            + "\n".join(f"  - {reference}" for reference in self.file_references)
            + "\n"
            f"Memory queries:\n"
            + "\n".join(f"  - {query}" for query in self.memory_queries)
            + "\nMemory tags:\n"
            + "\n".join(f"  - {tag}" for tag in self.memory_tags)
            + "\nReasons:\n"
            + "\n".join(f"  - {reason}" for reason in self.reasons)
        )
