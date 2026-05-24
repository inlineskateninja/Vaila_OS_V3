# n8n Integration

Purpose: workflow automation after Vaila has made a routing/tool decision and passed approval checks.

Initial configuration uses environment variables:

- `VAILA_N8N_BASE_URL`: base URL for the n8n instance or webhook host.
- `VAILA_N8N_API_KEY`: optional API key for n8n REST API calls.
- `VAILA_N8N_WEBHOOK_PATH`: webhook path used by Vaila-triggered workflows.

Current integration status: registry and HTTP client scaffolding only. No workflow is executed unless the environment variables are configured and a caller explicitly invokes the integration.

Safety rule: n8n should execute external actions only after Vaila's permission/approval layer says the action is allowed.
