import json
import shlex
from pathlib import Path
from typing import Any

from app.core import VailaCore


HELP_TEXT = """
Commands:
  /help                         Show this help menu.
  /tools                        Show available Phase 2 tools.
  /analyze <file>               Analyze a supported file without creating memory candidates.
  /import <file> [tags...]       Import a supported document and create memory candidates.
  /candidates [pending|all]      List memory candidates.
  /show <candidate_id>           Show one memory candidate in full.
  /approve <candidate_id>        Approve a candidate and write it to memory.
  /reject <candidate_id> [note]  Reject a pending candidate.
  /memory <query>                Search loaded memory records.
  /commands                      Show memory/action command list.
  /personas                      Show installed personas.
  /propose-chat [limit]          Propose memory candidates from recent chat.
  /delete-memory <topic>         Show safe delete proposal for matching memories.
  /activity [limit]              Show recent operational activity.
  /review                        Generate a Phase 2 project review.
  /models                        Show model profile resolution.
  /reload                        Reload memory and candidate files from disk.
  /exit                          Quit.

Supported imports: .md, .txt, .json, .yaml, .yml, .py, .log
Normal text still runs the router, memory retrieval, and LLM response path.
""".strip()


class VailaConsoleApp:
    def __init__(self) -> None:
        self.core = VailaCore()

    def start(self) -> None:
        print("Vaila Persona Core: Phase 2 Local Service Build")
        print("Type /help for commands. Type /exit to quit.\n")
        self.core.load_local_state()
        model_status = self.core.resolve_models()
        if model_status.get("ok"):
            print("Model profiles resolved from LM Studio.\n")
        else:
            print("Could not resolve LM Studio models. Chat may fail until LM Studio is running.")
            print(f"Reason: {model_status.get('message')}\n")
        self.print_state_summary()

        while True:
            try:
                user_text = input("Vaila > ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting.")
                break

            if not user_text:
                continue

            if user_text.lower() in {"/exit", "exit", "quit", "/quit"}:
                self.offer_conversation_retention()
                break

            try:
                if user_text.startswith("/"):
                    self.handle_command(user_text)
                else:
                    self.handle_chat(user_text)
            except Exception as error:
                print(f"Error: {error}")
            print()

    def print_state_summary(self) -> None:
        summary = self.core.state_summary()
        print(f"Loaded {summary['memory_records']} memory records.")
        print(f"Loaded {summary['pending_candidates']} pending memory candidates.\n")

    def handle_command(self, command_text: str) -> None:
        parts = shlex.split(command_text)
        command = parts[0].lower()
        args = parts[1:]

        if command == "/help":
            print(HELP_TEXT)
        elif command == "/tools":
            self.command_tools()
        elif command == "/analyze":
            self.command_analyze(args)
        elif command == "/import":
            self.command_import(args)
        elif command == "/candidates":
            status = args[0] if args else "pending"
            self.command_candidates(status)
        elif command == "/show":
            self.command_show(args)
        elif command == "/approve":
            self.command_approve(args)
        elif command == "/reject":
            self.command_reject(args)
        elif command == "/memory":
            self.command_memory(args)
        elif command == "/commands":
            self.command_commands()
        elif command == "/personas":
            self.command_personas()
        elif command == "/propose-chat":
            self.command_propose_chat(args)
        elif command == "/delete-memory":
            self.command_delete_memory(args)
        elif command == "/activity":
            self.command_activity(args)
        elif command == "/review":
            self.command_review()
        elif command == "/models":
            self.command_models()
        elif command == "/reload":
            self.core.reload()
            self.print_state_summary()
        else:
            print(f"Unknown command: {command}")
            print("Type /help for the command list.")

    def command_import(self, args: list[str]) -> None:
        if not args:
            print("Usage: /import <file_path> [tags...]")
            return

        result = self.core.import_document(path=args[0], tags=args[1:])
        report = result["report"]
        document = report["document"]

        print(f"Imported: {document['title']}")
        print(f"Document ID: {document['id']}")
        print(f"File type: {document['file_type']}")
        print(f"Characters: {document['char_count']}")
        print(f"Chunks: {document['chunk_count']}")
        print(f"Candidates created: {report['candidates_created']}")
        print(f"Saved new pending candidates: {result['added_count']}")
        if result["skipped_duplicate_count"]:
            print(f"Skipped duplicates: {result['skipped_duplicate_count']}")
        print("Candidate IDs:")
        for candidate_id in report["candidate_ids"]:
            print(f"  - {candidate_id}")
        print("Warnings:")
        warnings = report.get("warnings", [])
        if warnings:
            for warning in warnings:
                print(f"  - {warning}")
        else:
            print("  - None")
        print("Review with /candidates, then approve with /approve <candidate_id>.")

    def command_tools(self) -> None:
        for tool in self.core.tool_registry():
            approval = "approval required" if tool.get("approval_required") else "read-only"
            print(f"- {tool['name']}: {tool['description']} ({approval})")

    def command_analyze(self, args: list[str]) -> None:
        if not args:
            print("Usage: /analyze <file_path>")
            return
        result = self.core.analyze_file(args[0])
        print(format_file_analysis(result["analysis"]))

    def command_candidates(self, status: str) -> None:
        if status not in {"pending", "all", "approved", "rejected"}:
            print("Usage: /candidates [pending|all|approved|rejected]")
            return

        candidates = self.core.list_candidates(status)
        if not candidates:
            print(f"No candidates found for status: {status}")
            return

        for candidate in candidates:
            print(format_candidate(candidate))

    def command_show(self, args: list[str]) -> None:
        if not args:
            print("Usage: /show <candidate_id>")
            return

        candidate = self.core.get_candidate(args[0])
        if candidate is None:
            print(f"No candidate found: {args[0]}")
            return

        print(format_candidate(candidate.to_dict()))
        print(f"Persona scope: {', '.join(candidate.persona_scope)}")
        print(f"Source document ID: {candidate.source_document_id}")
        print(f"Chunk IDs: {', '.join(candidate.chunk_ids)}")
        if candidate.review_note:
            print(f"Review note: {candidate.review_note}")

    def command_approve(self, args: list[str]) -> None:
        if not args:
            print("Usage: /approve <candidate_id>")
            return

        result = self.core.approve_candidate(args[0])
        print(f"Approved candidate: {result['candidate']['id']}")
        print(f"Written to: {result['written_to']}")

    def command_reject(self, args: list[str]) -> None:
        if not args:
            print("Usage: /reject <candidate_id> [note]")
            return

        note = " ".join(args[1:]) if len(args) > 1 else ""
        result = self.core.reject_candidate(args[0], note=note)
        print(f"Rejected candidate: {result['candidate']['id']}")

    def command_memory(self, args: list[str]) -> None:
        if not args:
            print("Usage: /memory <query>")
            return

        query = " ".join(args)
        results = self.core.search_memory(query=query, persona="proto_jane", tags=[], limit=8)
        if not results:
            print("No memory records matched.")
            return

        for record in results:
            print(format_memory(record))


    def command_commands(self) -> None:
        for command in self.core.memory_commands():
            print(f"{command['name']}: {command['description']}")
            for example in command.get("examples", []):
                print(f"  example: {example}")

    def command_personas(self) -> None:
        for persona in self.core.list_personas():
            print(f"- {persona['display_name']} ({persona['persona_id']}): {persona.get('role', '')}")
            if persona.get("influences"):
                print(f"  influences: {', '.join(persona['influences'])}")

    def command_propose_chat(self, args: list[str]) -> None:
        limit = int(args[0]) if args else 20
        result = self.core.propose_memories_from_recent_chat(limit=limit)
        print(f"Created {result['created_count']} pending candidate(s) from {result['reviewed_events']} recent chat event(s).")
        for candidate in result["created"]:
            print(f"  - {candidate['id']}: {candidate['question']}")

    def command_delete_memory(self, args: list[str]) -> None:
        if not args:
            print("Usage: /delete-memory <topic>")
            return
        result = self.core.delete_memory_proposal(" ".join(args))
        print(result["message"])
        for record in result["matches"]:
            print(f"  - {record['id']} | {record['question']} | score {record.get('score')}")

    def offer_conversation_retention(self) -> None:
        try:
            answer = input("Retain this conversation for memory consideration before closing? [y/N] ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return
        if answer not in {"y", "yes"}:
            return
        result = self.core.propose_memories_from_recent_chat(limit=30)
        print(f"Created {result['created_count']} pending memory candidate(s). Review them next session with /candidates.")

    def command_activity(self, args: list[str]) -> None:
        limit = 25
        if args:
            try:
                limit = max(1, min(200, int(args[0])))
            except ValueError:
                print("Usage: /activity [limit]")
                return
        events = self.core.recent_activity(limit=limit)
        if not events:
            print("No activity logged yet.")
            return
        for event in events:
            print(format_activity(event))

    def command_review(self) -> None:
        review = self.core.project_review(limit=50)
        print(format_project_review(review))

    def command_models(self) -> None:
        status = self.core.resolve_models()
        print(json.dumps(status, indent=2, ensure_ascii=False))

    def handle_chat(self, user_text: str) -> None:
        result = self.core.chat(user_text, include_context=True)

        print("\n=== REQUEST ENVELOPE ===")
        print(format_request_envelope(result.get("request_envelope", {})))

        print("\n=== PROMPT INTERPRETATION ===")
        print(format_prompt_interpretation(result.get("prompt_interpretation", {}), result.get("routing_comparison", {})))

        print("\n=== ROUTE PLAN ===")
        print(format_route_plan(result["route_plan"]))

        print("\n=== RETRIEVED MEMORY ===")
        if result["memories"]:
            for record in result["memories"]:
                print(format_memory(record))
        else:
            print("No relevant memory found.")

        print("\n=== CONTEXT PACKET PREVIEW ===")
        print(result.get("context_packet", ""))

        print("\n=== LLM RESPONSE ===")
        if result.get("ok"):
            print(f"[Model used: {result['selected_profile']} | {result['model']}]")
            print(f"[Response time: {result['elapsed_seconds']} seconds]\n")
            print(result["response"])
        else:
            print(f"Model response failed: {result.get('error')}")

        created_candidates = result.get("memory_candidates_created", [])
        if created_candidates:
            print("\n=== MEMORY CANDIDATES CREATED ===")
            for candidate in created_candidates:
                print(f"  - {candidate['id']}: {candidate['question']} [{candidate.get('category', 'general')}]")
            print("Review with /candidates, then approve with /approve <candidate_id>.")
        elif result.get("memory_candidate_note"):
            print(f"\nMemory note: {result['memory_candidate_note']}")


def format_request_envelope(envelope: dict[str, Any]) -> str:
    if not envelope:
        return "No request envelope returned."
    return (
        f"Request ID: {envelope.get('id', '')}\n"
        f"Received UTC: {envelope.get('received_at', '')}\n"
        f"Original text: {envelope.get('original_text', '')}"
    )


def format_prompt_interpretation(interpretation: dict[str, Any], comparison: dict[str, Any]) -> str:
    if not interpretation:
        return "No prompt interpretation returned."
    if not interpretation.get("ok"):
        return (
            f"Status: unavailable\n"
            f"Source: {interpretation.get('source', '')}\n"
            f"Error: {interpretation.get('error', '')}\n"
            f"Comparison status: {comparison.get('status', '')}"
        )
    disagreements = comparison.get("disagreements", []) or ["None"]
    return (
        f"Status: {comparison.get('status', '')}\n"
        f"Advised task: {interpretation.get('advised_task_type', '')}\n"
        f"Advised persona: {interpretation.get('advised_persona', '')}\n"
        f"Advised model profile: {interpretation.get('advised_model_profile', '')}\n"
        f"Confidence: {interpretation.get('confidence', 0)}\n"
        f"Intent: {interpretation.get('intent_summary', '')}\n"
        "Disagreements:\n"
        + "\n".join(f"  - {item}" for item in disagreements)
    )


def format_route_plan(route: dict[str, Any]) -> str:
    return (
        f"Task type: {route['task_type']}\n"
        f"Persona: {route['persona']}\n"
        f"Model tier: {route['model_tier']}\n"
        f"Model profile: {route['model_profile']}\n"
        f"Fallback profile: {route['fallback_profile']}\n"
        "Memory queries:\n"
        + "\n".join(f"  - {query}" for query in route["memory_queries"])
        + "\nMemory tags:\n"
        + "\n".join(f"  - {tag}" for tag in route["memory_tags"])
        + "\nReasons:\n"
        + "\n".join(f"  - {reason}" for reason in route["reasons"])
    )


def format_memory(record: dict[str, Any]) -> str:
    source_line = f"Source: {record['source_path']}\n" if record.get("source_path") else ""
    return (
        f"[Memory: {record['id']}]\n"
        f"Question: {record['question']}\n"
        f"Answer: {record['answer']}\n"
        f"Tags: {', '.join(record.get('tags', []))}\n"
        f"{source_line}"
    )


def format_candidate(candidate: dict[str, Any]) -> str:
    return (
        f"[{candidate['status'].upper()}] {candidate['id']}\n"
        f"Source: {candidate.get('source_title') or candidate.get('source_path')}\n"
        f"Question: {candidate['question']}\n"
        f"Answer: {candidate['answer']}\n"
        f"Tags: {', '.join(candidate.get('tags', []))}\n"
    )


def format_file_analysis(analysis: dict[str, Any]) -> str:
    def block(title: str, items: list[str]) -> list[str]:
        lines = [f"{title}:"]
        if items:
            lines.extend(f"  - {item}" for item in items)
        else:
            lines.append("  - None")
        return lines

    lines = [
        "=== FILE ANALYSIS ===",
        f"File: {analysis['path']}",
        f"Type: {analysis['file_type']}",
        f"Size: {analysis['size_bytes']} bytes",
        f"Lines: {analysis['line_count']}",
        f"Words: {analysis['word_count']}",
        f"SHA-256: {analysis['sha256']}",
        "",
        "Summary:",
        analysis.get("summary", ""),
        "",
    ]
    lines.extend(block("Headings / structure", analysis.get("headings", [])))
    lines.append("")
    lines.extend(block("Key lines", analysis.get("key_lines", [])))
    lines.append("")
    lines.extend(block("Action items", analysis.get("action_items", [])))
    lines.append("")
    lines.extend(block("Structural notes", analysis.get("structural_notes", [])))
    lines.append("")
    lines.extend(block("Warnings", analysis.get("warnings", [])))
    return "\n".join(lines)



def format_activity(event: dict[str, Any]) -> str:
    details = event.get("details", {})
    compact_details = []
    for key, value in details.items():
        if value in (None, "", [], {}):
            continue
        compact_details.append(f"  {key}: {value}")
    detail_text = "\n".join(compact_details) if compact_details else "  No details."
    return (
        f"[{event.get('created_at')}] {event.get('event_type')}\n"
        f"{event.get('summary')}\n"
        f"Details:\n{detail_text}"
    )


def format_project_review(review: dict[str, Any]) -> str:
    state = review.get("state", {})
    lines = [
        "=== PROJECT REVIEW ===",
        f"Generated: {review.get('generated_at')}",
        f"Phase: {review.get('phase')}",
        "",
        "Summary:",
        review.get("summary", ""),
        "",
        "Phase fit:",
        review.get("phase_fit", ""),
        "",
        "State:",
        f"  Memory records: {state.get('memory_records')}",
        f"  Pending candidates: {state.get('pending_candidates')}",
        f"  Approved candidates: {state.get('approved_candidates')}",
        f"  Rejected candidates: {state.get('rejected_candidates')}",
        f"  Activity events: {state.get('activity_events')}",
        f"  Activity counts: {state.get('activity_counts')}",
        "",
        "Risks:",
    ]
    lines.extend(f"  - {item}" for item in review.get("risks", []))
    lines.append("")
    lines.append("Recommended next steps:")
    lines.extend(f"  - {item}" for item in review.get("recommended_next_steps", []))
    lines.append("")
    lines.append("Suggested tests:")
    lines.extend(f"  - {item}" for item in review.get("suggested_tests", []))
    return "\n".join(lines)

def build_context_packet(route_plan, memories) -> str:
    """Backward-compatible helper for older scripts that imported app.main directly."""
    return VailaCore().build_context_packet(route_plan, memories)


def main() -> None:
    VailaConsoleApp().start()


if __name__ == "__main__":
    main()
