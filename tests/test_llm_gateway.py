from pathlib import Path

from System_Services.llm_gateway import LLMGateway


def test_llm_gateway_initializes():
    gateway = LLMGateway(project_root=Path("."))
    assert gateway.base_url
    assert gateway.model
