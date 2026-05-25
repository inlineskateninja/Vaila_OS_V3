from __future__ import annotations

from pathlib import Path

from System_Services.envelope_service import EnvelopeService
from System_Services.logging_service import LoggingService
from System_Services.orchestration_service import OrchestrationService
from System_Services.router_service import RouterService
from System_Services.status_service import StatusService


def run_cli(project_root: Path) -> None:
    status = StatusService()
    logger = LoggingService(project_root=project_root)
    envelope_service = EnvelopeService(project_root=project_root)
    router = RouterService(project_root=project_root)
    orchestrator = OrchestrationService(project_root=project_root, logger=logger)

    status.info("CLI mode ready.")
    status.info("Type 'exit' or 'quit' to close Vaila OS V3.")

    while True:
        try:
            user_text = input("\nUser > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nShutting down Vaila OS V3.")
            break

        if not user_text:
            continue

        if user_text.lower() in {"exit", "quit"}:
            status.info("Shutdown requested.")
            break

        if user_text.lower() == "clear":
            orchestrator.clear_history("cli_session")
            status.info("Conversation history cleared.")
            continue

        envelope = envelope_service.create(
            user_text=user_text,
            source="cli",
            metadata={"session_id": "cli_session"},
        )
        route = router.route(envelope)
        status.route(route)

        response = orchestrator.handle(envelope=envelope, route=route)
        print(f"\nVaila > {response.visible_text}")

        logger.log_session_event(
            {
                "event_type": "cli_interaction_complete",
                "envelope": envelope.to_dict(),
                "route": route,
                "response_meta": response.meta,
            }
        )

    logger.close()
