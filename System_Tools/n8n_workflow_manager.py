from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

class N8NWorkflowManager:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def create_webhook_node(self, name: str, path: str, method: str = "POST") -> dict[str, Any]:
        """Creates a fully configured n8n Webhook Node."""
        return {
            "parameters": {
                "path": path,
                "options": {},
                "httpMethod": method,
                "responseMode": "onReceived"
            },
            "id": str(uuid4()),
            "name": name,
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 1,
            "position": [250, 300]
        }

    def create_http_request_node(self, name: str, url: str, method: str = "POST", body_parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        """Creates a fully configured n8n HTTP Request Node."""
        params: dict[str, Any] = {
            "url": url,
            "method": method,
            "authentication": "none",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Content-Type", "value": "application/json"}
                ]
            },
            "options": {}
        }
        
        if body_parameters:
            params["sendBody"] = True
            params["contentType"] = "json"
            params["bodyParameters"] = {
                "parameters": [
                    {"name": k, "value": v} for k, v in body_parameters.items()
                ]
            }

        return {
            "parameters": params,
            "id": str(uuid4()),
            "name": name,
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4,
            "position": [500, 300]
        }

    def create_if_secret_check_node(self, name: str, secret_token: str) -> dict[str, Any]:
        """Creates an n8n If Node designed to verify Vaila's header authentication secret."""
        return {
            "parameters": {
                "conditions": {
                    "string": [
                        {
                            "value1": "={{ $headers[\"x-vaila-webhook-secret\"] }}",
                            "value2": secret_token
                        }
                    ]
                }
            },
            "id": str(uuid4()),
            "name": name,
            "type": "n8n-nodes-base.if",
            "typeVersion": 1,
            "position": [380, 200]
        }

    def compile_webhook_trigger_workflow(self, name: str, webhook_path: str, action_url: str, secret_token: str | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Compiles a complete 2-node or 3-node workflow:
        If secret_token: Webhook -> If Check -> HTTP Request
        Else: Webhook -> HTTP Request
        """
        webhook = self.create_webhook_node("Webhook Trigger", webhook_path)
        http_req = self.create_http_request_node("API Notification", action_url)
        
        if secret_token:
            if_node = self.create_if_secret_check_node("Verify Secret", secret_token)
            
            # Position layout spacing
            webhook["position"] = [100, 300]
            if_node["position"] = [300, 300]
            http_req["position"] = [500, 200]  # connect to "true" branch
            
            nodes = [webhook, if_node, http_req]
            
            connections = {
                webhook["name"]: {
                    "main": [
                        [
                            {
                                "node": if_node["name"],
                                "type": "main",
                                "index": 0
                            }
                        ]
                    ]
                },
                if_node["name"]: {
                    "main": [
                        [
                            {
                                "node": http_req["name"],
                                "type": "main",
                                "index": 0
                            }
                        ]
                    ]
                }
            }
        else:
            webhook["position"] = [100, 300]
            http_req["position"] = [350, 300]
            
            nodes = [webhook, http_req]
            
            connections = {
                webhook["name"]: {
                    "main": [
                        [
                            {
                                "node": http_req["name"],
                                "type": "main",
                                "index": 0
                            }
                        ]
                    ]
                }
            }
            
        return nodes, connections
