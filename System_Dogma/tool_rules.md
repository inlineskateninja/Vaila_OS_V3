# Tool Rules

- Tools should be callable from orchestration without becoming core dependencies.
- Tools must return clear text results to the orchestrator.
- Tools that propose file changes must export proposals to Sandbox.
- Connected services such as n8n, OpenBrain, and Google should be adapters, not required boot dependencies.
