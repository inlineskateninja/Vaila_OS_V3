from __future__ import annotations

from dataclasses import asdict, dataclass

DEFAULT_CONTEXT_PACKET_MAX_CHARS = 9000
DEFAULT_LLM_CONTEXT_PACKET_MAX_CHARS = 5200
DEFAULT_SECTION_MAX_CHARS = 2200
DEFAULT_USER_REQUEST_MAX_CHARS = 4500
DEFAULT_INTERPRETER_PROMPT_MAX_CHARS = 2500


@dataclass
class PromptBudgetReport:
    original_chars: int
    final_chars: int
    max_chars: int
    compacted: bool = False
    sections_compacted: list[str] | None = None

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["sections_compacted"] = self.sections_compacted or []
        return data


def estimate_token_count(text: str) -> int:
    """Rough local-model token estimate.

    This intentionally favors safety over precision. LM Studio models commonly use
    llama.cpp-style context limits, and a conservative character budget prevents
    n_keep >= n_ctx failures before the request reaches the model.
    """
    if not text:
        return 0
    return max(1, (len(text) + 2) // 3)


def compact_text(text: str, max_chars: int, label: str = "text") -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    marker = f"\n[... {label} compacted: {len(text) - max_chars} characters omitted for model context budget. Full source remains in logs/files. ...]\n"
    if max_chars <= len(marker) + 20:
        return text[:max_chars]
    head = max_chars // 2
    tail = max_chars - head - len(marker)
    return text[:head].rstrip() + marker + text[-tail:].lstrip()


def compact_section_block(block: str, max_chars: int, section_name: str) -> tuple[str, bool]:
    if len(block) <= max_chars:
        return block, False
    return compact_text(block, max_chars, section_name), True


def fit_context_packet(packet: str, max_chars: int = DEFAULT_CONTEXT_PACKET_MAX_CHARS) -> tuple[str, PromptBudgetReport]:
    if len(packet) <= max_chars:
        return packet, PromptBudgetReport(
            original_chars=len(packet),
            final_chars=len(packet),
            max_chars=max_chars,
            compacted=False,
            sections_compacted=[],
        )

    compacted = compact_text(packet, max_chars, "context packet")
    return compacted, PromptBudgetReport(
        original_chars=len(packet),
        final_chars=len(compacted),
        max_chars=max_chars,
        compacted=True,
        sections_compacted=["context_packet"],
    )
