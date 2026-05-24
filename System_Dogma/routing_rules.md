# Routing Rules

Phase 1 routing uses deterministic regex first.

Routing pipeline:

```text
User Prompt -> Envelope -> Router -> Tool Dispatch / Memory -> Unified LLM Gateway -> Async Logging -> Return
```

The PromptInterpreter does not run for text chat surfaces such as the desktop client, CLI, or local API. It is reserved for the future STT voice layer, where spoken input may need advisory interpretation before or after routing.

Memory candidate capture is also queued after the LLM response so memory bookkeeping does not delay visible output.
