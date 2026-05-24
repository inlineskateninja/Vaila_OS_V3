# Vaila OS V3

Vaila OS V3 is the rebuilt local operating layer for the Vaila / Home Jane system.

## Phase 1 Goals

- CLI mode
- Local API service mode
- Desktop client mode
- Text-based interaction
- Persona selector
- Prompt envelope creation
- Regex-first routing
- Unified LLM gateway
- Async logging and memory candidate handling
- Tool dispatch
- System self-assessment with sandboxed patch exports

## Golden Rule

The system may analyze its own files, but it must not directly rewrite core files without user approval. Proposed changes go to:

`Sandbox/Proposed_Patches/`

Self-assessment exports go to:

`Sandbox/Self_Assessment_Exports/`

## Recommended PyCharm Setup

1. Open this folder as a PyCharm project.
2. Create a new virtual environment.
3. Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

4. Optional: create a `.env` file based on `.env.example`.
5. Run:

```powershell
python Core_System_Files\app.py
```

## LM Studio Defaults

The starter gateway expects an OpenAI-compatible local server.

Default base URL:

`http://localhost:1234/v1`

Default model:

Set in `.env` using `LMSTUDIO_MODEL`.

## Optional Connected Services

Vaila OS V3 can connect to optional external services, but none are required for Phase 1 boot.

- n8n is optional and disabled by default.
- OpenBrain is optional and disabled by default.
- Secrets go in `.env` or `Secrets/`, never in registry JSON files.
- Phase 1 uses n8n webhooks instead of custom n8n nodes.
- Phase 1 forwards memory candidates to OpenBrain only when OpenBrain is explicitly enabled.

Safe defaults are listed in `.env.example`. Keep blank secret fields blank until a local service is ready.

Future expansion notes:

- n8n REST workflow listing, activation, import/export, and admin functions can be added after webhook behavior is stable.
- OpenBrain HTTP or MCP memory retrieval can replace the local placeholder adapter when the final backend contract is chosen.
