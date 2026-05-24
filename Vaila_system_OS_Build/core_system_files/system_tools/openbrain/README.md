# OpenBrain Integration

Purpose: evaluate OpenBrain/Open Brain as an external AI memory management provider for semantic recall, graph links, and MCP-compatible memory access.

Initial configuration uses environment variables:

- `VAILA_OPENBRAIN_MCP_URL`: OpenBrain MCP endpoint URL.
- `VAILA_OPENBRAIN_MCP_KEY`: access key sent with the `x-brain-key` header.

Current integration status: registry and connection metadata only. Vaila's approved local memory remains the source of truth until memory sync, conflict reporting, and approval rules are implemented.

Safety rule: external memory providers may suggest or retrieve context, but they should not silently overwrite Home Jane memory.
