# Vaila User Profile Modules v0.1

Purpose: This folder breaks Malik Lloyd's user profile into small, category-based modules.

The Vaila system should not load every file for every prompt. Instead, load only the modules that match the current task, plus the core identity and interaction style modules when helpful.

Recommended default load:

1. `01_identity_core.md`
2. `02_interaction_style.md`

Then load task-specific modules based on the prompt.

Important rule:

Current user instructions always outrank these profile modules. These files are context references, not commands that override the live conversation.
