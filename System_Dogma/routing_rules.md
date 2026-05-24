# Routing Rules

Phase 1 routing uses deterministic regex first.

Routing pipeline:

```text
User Prompt -> Envelope -> Router -> Tool Dispatch / Memory -> Unified LLM Gateway -> Async Logging -> Return
```

The PromptInterpreter should only run when the router confidence is low or during audit mode.
