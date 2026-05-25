# 13 Context Loading Rules

module_id: context_loading_rules  
load_priority: router_system  
load_when: prompt routing, context selection, memory loading, Vaila system design  
avoid_loading_when: direct user-facing answer generation unless discussing architecture

## Core Rule

Do not load the entire user profile by default.

Load:

1. The smallest useful set of modules.
2. The live conversation context.
3. Any relevant project files.
4. Only then optional background modules.

Current user instructions always outrank profile modules.

## Default Load Set

For most normal sessions, load:

- `01_identity_core.md`
- `02_interaction_style.md`

For very small utility tasks, no profile module may be needed.

## Prompt-to-Module Routing

### Technical Prompt

Triggers:

- code
- Python
- PowerShell
- PyCharm
- GitHub
- LM Studio
- app
- bug
- error
- traceback
- install
- architecture
- file structure
- hardware
- electronics
- pinout
- Arduino
- Raspberry Pi
- ESP32

Load:

- `02_interaction_style.md`
- `03_learning_and_technical_guidance.md`

If the prompt mentions Vaila, Home Jane, Proto Jane, Orator, local AI, memory, tools, TTS, or agents, also load:

- `04_project_vaila_context.md`

### Vaila System Prompt

Triggers:

- Vaila
- Home Jane
- Proto Jane
- Project Orator
- Jane OS
- local AI
- memory layer
- persona routing
- tool integration
- n8n
- OpenBrain
- agent
- sync
- TTS
- STT
- voice console

Load:

- `02_interaction_style.md`
- `03_learning_and_technical_guidance.md`
- `04_project_vaila_context.md`

If personas are mentioned, also load:

- `05_persona_system.md`

### Persona Prompt

Triggers:

- Maelith
- Vecht
- Serren
- Riven
- Council
- persona
- archetype
- internal advisor
- voice profile

Load:

- `02_interaction_style.md`
- `05_persona_system.md`

If the task is about Vaila's implementation of personas, also load:

- `04_project_vaila_context.md`
- `03_learning_and_technical_guidance.md`

### Writing Prompt

Triggers:

- rewrite
- draft
- post
- essay
- script
- statement
- letter
- bio
- profile
- make this sound like me

Load:

- `02_interaction_style.md`
- `11_writing_style.md`

If the writing is public-facing or content-related, also load:

- `08_content_brand.md`

If the writing is workplace-related, also load:

- `06_work_skills_context.md`
- `10_sensitive_context_and_boundaries.md` only if conflict, legal, HR, or advocacy is involved.

### Work or Resume Prompt

Triggers:

- resume
- cover letter
- job
- application
- interview
- work history
- professional summary
- staff
- venue
- 9:30 Club
- logistics
- technical support

Load:

- `02_interaction_style.md`
- `06_work_skills_context.md`
- `11_writing_style.md`

### Inline Skate Ninja Prompt

Triggers:

- Inline Skate Ninja
- skating
- skate lesson
- skate safety
- skate event
- mobility
- stronger culture
- safer streets

Load:

- `02_interaction_style.md`
- `07_inline_skate_ninja.md`

If marketing or content is involved, also load:

- `08_content_brand.md`
- `11_writing_style.md`

### Content or Brand Prompt

Triggers:

- Malik.Voice
- content
- YouTube
- Twitch
- TikTok
- Instagram
- Substack
- Patreon
- Discord
- branding
- channel
- script
- audience

Load:

- `02_interaction_style.md`
- `08_content_brand.md`
- `11_writing_style.md`

### Productivity or Life Planning Prompt

Triggers:

- plan
- schedule
- routine
- productivity
- personal OS
- roadmap
- priorities
- habits
- accountability
- weekly review

Load:

- `02_interaction_style.md`
- `09_personal_os_and_productivity.md`

If long-term direction is involved, also load:

- `12_long_term_goals.md`

### Sensitive Prompt

Triggers:

- legal
- lawyer
- court
- HR
- discrimination
- retaliation
- trauma
- diagnosis
- therapy
- psychiatric
- self-harm
- violence
- safety
- crisis
- workplace conflict
- Connie
- protective order

Load:

- `02_interaction_style.md`
- `10_sensitive_context_and_boundaries.md`

If writing is involved, also load:

- `11_writing_style.md`

If workplace context is involved, also load:

- `06_work_skills_context.md`

## Token Budget Recommendation

Use a tiered approach:

### Minimal Context

Use for simple utility tasks.

Load:

- No profile, or only `02_interaction_style.md`.

### Normal Context

Use for most responses.

Load:

- `01_identity_core.md`
- `02_interaction_style.md`
- One task-specific module.

### Deep Context

Use for major planning, architecture, or personal writing tasks.

Load:

- `01_identity_core.md`
- `02_interaction_style.md`
- Two to four task-specific modules.

### Full Review

Use rarely.

Load all modules only when Malik asks for a full profile review, migration, rewrite, or system-level audit.

## Conflict Resolution

When modules conflict:

1. Safety rules win.
2. Current user instruction wins next.
3. Live project files beat profile memory.
4. More specific modules beat general modules.
5. Recent confirmed context beats old context.
6. If uncertain, state the uncertainty and proceed carefully.
