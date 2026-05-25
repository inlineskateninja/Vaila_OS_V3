from pathlib import Path
from System_Services.envelope_service import EnvelopeService
from System_Services.orchestration_service import OrchestrationService
from System_Services.logging_service import LoggingService


def test_orchestrator_chat_history_isolation() -> None:
    project_root = Path(__file__).resolve().parents[1]
    logger = LoggingService(project_root=project_root)
    orchestrator = OrchestrationService(project_root=project_root, logger=logger)
    
    # Verify histories are isolated and start empty
    hist_cli = orchestrator.get_history("cli_session")
    hist_desktop = orchestrator.get_history("desktop_session")
    
    assert len(hist_cli) == 0
    assert len(hist_desktop) == 0
    
    # Append manually to mock successful interaction
    hist_cli.append({"role": "user", "content": "Hello"})
    hist_cli.append({"role": "assistant", "content": "Hi there"})
    
    # Assert isolation
    assert len(orchestrator.get_history("cli_session")) == 2
    assert len(orchestrator.get_history("desktop_session")) == 0
    
    # Assert clearing works
    orchestrator.clear_history("cli_session")
    assert len(orchestrator.get_history("cli_session")) == 0
    
    logger.close()
