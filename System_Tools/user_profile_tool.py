from __future__ import annotations

import json
import os
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any


class UserProfileTool:
    """
    User Profile System Tool for Vaila OS V3.
    Manages unzipping, reading, updating, and dynamically loading user profile modules
    based on trigger rules in 13_context_loading_rules.md.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.user_details_dir = self.project_root / "User" / "User_Details"

    def import_zip(self, zip_path: str | Path) -> dict[str, Any]:
        """
        Extracts the profile ZIP archive into User/User_Details/.
        Enforces safety checks (such as Zip Slip path traversal mitigation).
        """
        zip_path = Path(zip_path)
        if not zip_path.exists():
            return {"ok": False, "error": f"ZIP file not found at path: {zip_path}"}
        if not zip_path.is_file():
            return {"ok": False, "error": f"Specified path is not a file: {zip_path}"}

        self.user_details_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                # Security sanity check: resolve all target paths to prevent Zip Slip
                for member in zip_ref.infolist():
                    target_path = Path(os.path.abspath(self.user_details_dir / member.filename))
                    if not target_path.resolve().is_relative_to(self.user_details_dir.resolve()):
                        return {
                            "ok": False,
                            "error": f"Security alert: Zip member '{member.filename}' attempts path traversal.",
                        }

                zip_ref.extractall(self.user_details_dir)

            # Locate the extracted profile index and manifest
            manifest_path = self.get_manifest_path()
            if not manifest_path:
                return {
                    "ok": True,
                    "warning": "Extracted successfully, but profile_manifest.json was not found in the root of the extracted files.",
                    "extracted_to": str(self.user_details_dir),
                }

            return {
                "ok": True,
                "extracted_to": str(manifest_path.parent),
                "manifest": self.get_manifest(),
            }

        except Exception as exc:
            return {"ok": False, "error": f"Extraction failed: {exc}"}

    def get_manifest_path(self) -> Path | None:
        """
        Searches recursively under User/User_Details/ for profile_manifest.json.
        """
        if not self.user_details_dir.exists():
            return None
        
        # Look for profile_manifest.json directly or recursively
        manifest_files = list(self.user_details_dir.glob("**/profile_manifest.json"))
        if manifest_files:
            return manifest_files[0]
        return None

    def get_profile_dir(self) -> Path | None:
        """
        Gets the directory containing the active user profile manifest and modules.
        """
        path = self.get_manifest_path()
        if path:
            return path.parent
        return None

    def get_manifest(self) -> dict[str, Any] | None:
        """
        Loads and returns the profile_manifest.json metadata.
        """
        path = self.get_manifest_path()
        if not path or not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def read_module(self, filename: str) -> str:
        """
        Reads and returns the content of a specific profile module file.
        """
        profile_dir = self.get_profile_dir()
        if not profile_dir:
            return f"Error: No active user profile loaded. Please import the profile zip."

        file_path = profile_dir / filename
        if not file_path.exists():
            return f"Error: Profile module file not found: {filename}"
        if not file_path.is_file():
            return f"Error: Specified path is not a file: {filename}"

        try:
            return file_path.read_text(encoding="utf-8")
        except Exception as exc:
            return f"Error reading file '{filename}': {exc}"

    def save_module(self, filename: str, content: str) -> bool:
        """
        Saves/updates the content of a specific profile module file.
        """
        profile_dir = self.get_profile_dir()
        if not profile_dir:
            return False

        file_path = profile_dir / filename
        try:
            file_path.write_text(content, encoding="utf-8")
            return True
        except Exception:
            return False

    def route_context(self, user_prompt: str) -> dict[str, Any]:
        """
        Implements context loading rules from 13_context_loading_rules.md.
        Dynamically matches keywords in the user_prompt and returns a dict with:
        - "loaded_modules": list of file basenames matched
        - "matched_keywords": dict of triggers mapped to list of matched words
        - "context_block": fully compiled text block to inject into system prompt
        """
        manifest = self.get_manifest()
        profile_dir = self.get_profile_dir()

        if not manifest or not profile_dir:
            return {
                "loaded_modules": [],
                "matched_keywords": {},
                "context_block": ""
            }

        # Baseline default files that are always loaded (recommended default set)
        defaults = manifest.get("recommended_default_modules", ["01_identity_core.md", "02_interaction_style.md"])
        active_modules = set(defaults)
        matched_triggers: dict[str, list[str]] = {}

        # Safe parsing helper
        prompt_lower = user_prompt.lower()

        # Helper to check keywords
        def check_keywords(category: str, keywords: list[str]) -> list[str]:
            found = []
            for kw in keywords:
                # Match full words or exact substrings
                pattern = rf"\b{re.escape(kw)}\b"
                if re.search(pattern, prompt_lower) or kw in prompt_lower:
                    found.append(kw)
            if found:
                matched_triggers[category] = found
            return found

        # Define all rules maps
        rules = {
            "technical": {
                "triggers": ["code", "python", "powershell", "pycharm", "github", "lm studio", "app", "bug", "error", "traceback", "install", "architecture", "file structure", "hardware", "electronics", "pinout", "arduino", "raspberry pi", "esp32"],
                "modules": ["02_interaction_style.md", "03_learning_and_technical_guidance.md"],
                "conditional": {
                    "triggers": ["vaila", "home jane", "proto jane", "orator", "local ai", "memory", "tools", "tts", "agents"],
                    "modules": ["04_project_vaila_context.md"]
                }
            },
            "vaila_system": {
                "triggers": ["vaila", "home jane", "proto jane", "project orator", "jane os", "local ai", "memory layer", "persona routing", "tool integration", "n8n", "openbrain", "agent", "sync", "tts", "stt", "voice console"],
                "modules": ["02_interaction_style.md", "03_learning_and_technical_guidance.md", "04_project_vaila_context.md"],
                "conditional": {
                    "triggers": ["personas", "persona", "internal advisor", "voice profile"],
                    "modules": ["05_persona_system.md"]
                }
            },
            "persona": {
                "triggers": ["maelith", "vecht", "serren", "riven", "council", "persona", "archetype", "internal advisor", "voice profile"],
                "modules": ["02_interaction_style.md", "05_persona_system.md"],
                "conditional": {
                    # If persona is task context, check if also about Vaila implementation
                    "triggers": ["vaila", "home jane", "proto jane", "local ai", "memory", "routing"],
                    "modules": ["04_project_vaila_context.md", "03_learning_and_technical_guidance.md"]
                }
            },
            "writing": {
                "triggers": ["rewrite", "draft", "post", "essay", "script", "statement", "letter", "bio", "profile", "make this sound like me"],
                "modules": ["02_interaction_style.md", "11_writing_style.md"],
                "conditionals": [
                    {
                        "triggers": ["youtube", "twitch", "tiktok", "instagram", "substack", "patreon", "discord", "branding", "channel", "audience"],
                        "modules": ["08_content_brand.md"]
                    },
                    {
                        "triggers": ["resume", "cover letter", "job", "application"],
                        "modules": ["06_work_skills_context.md"]
                    },
                    {
                        "triggers": ["conflict", "legal", "hr", "advocacy"],
                        "modules": ["10_sensitive_context_and_boundaries.md"]
                    }
                ]
            },
            "work_skills": {
                "triggers": ["resume", "cover letter", "job", "application", "interview", "work history", "professional summary", "staff", "venue", "9:30 club", "logistics", "technical support"],
                "modules": ["02_interaction_style.md", "06_work_skills_context.md", "11_writing_style.md"]
            },
            "inline_skate_ninja": {
                "triggers": ["inline skate ninja", "skating", "skate lesson", "skate safety", "skate event", "mobility", "stronger culture", "safer streets"],
                "modules": ["02_interaction_style.md", "07_inline_skate_ninja.md"],
                "conditional": {
                    "triggers": ["post", "draft", "content", "audience", "marketing", "channel"],
                    "modules": ["08_content_brand.md", "11_writing_style.md"]
                }
            },
            "content_brand": {
                "triggers": ["malik.voice", "content", "youtube", "twitch", "tiktok", "instagram", "substack", "patreon", "discord", "branding", "channel", "audience"],
                "modules": ["02_interaction_style.md", "08_content_brand.md", "11_writing_style.md"]
            },
            "productivity": {
                "triggers": ["plan", "schedule", "routine", "productivity", "personal os", "roadmap", "priorities", "habits", "accountability", "weekly review"],
                "modules": ["02_interaction_style.md", "09_personal_os_and_productivity.md"],
                "conditional": {
                    "triggers": ["goal", "goals", "long-term", "future", "trajectory"],
                    "modules": ["12_long_term_goals.md"]
                }
            },
            "sensitive": {
                "triggers": ["legal", "lawyer", "court", "hr", "discrimination", "retaliation", "trauma", "diagnosis", "therapy", "psychiatric", "self-harm", "violence", "safety", "crisis", "workplace conflict", "connie", "protective order"],
                "modules": ["02_interaction_style.md", "10_sensitive_context_and_boundaries.md"],
                "conditionals": [
                    {
                        "triggers": ["rewrite", "draft", "post", "essay", "script", "statement", "letter", "bio", "profile", "make this sound like me"],
                        "modules": ["11_writing_style.md"]
                    },
                    {
                        "triggers": ["resume", "cover letter", "job", "application", "interview", "work history", "professional summary", "staff", "venue", "9:30 club", "logistics", "technical support"],
                        "modules": ["06_work_skills_context.md"]
                    }
                ]
            }
        }

        # Apply routing matching logic
        for cat, config in rules.items():
            matched = check_keywords(cat, config["triggers"])
            if matched:
                active_modules.update(config["modules"])
                
                # Check conditionals
                if "conditional" in config:
                    cond = config["conditional"]
                    cond_matched = check_keywords(f"{cat}_cond", cond["triggers"])
                    if cond_matched:
                        active_modules.update(cond["modules"])
                
                if "conditionals" in config:
                    for cond in config["conditionals"]:
                        cond_matched = check_keywords(f"{cat}_cond", cond["triggers"])
                        if cond_matched:
                            active_modules.update(cond["modules"])

        # Compile loaded modules contents into a single markdown string
        loaded_list = sorted(list(active_modules))
        chunks = []
        for fn in loaded_list:
            content = self.read_module(fn)
            if content and not content.startswith("Error:"):
                # Clean clean metadata prefixes if needed, but keeping files intact
                chunks.append(f"### PROFILE MODULE: {fn.replace('.md', '').upper()}\n{content.strip()}")

        context_block = ""
        if chunks:
            context_block = (
                "## USER PROFILE REFERENCE BLOCK\n"
                "The following dynamic, task-relevant user profile modules have been loaded. "
                "Use this information as a direct reference to understand Malik's identity, "
                "behavior constraints, and writing or technical preferences. Do not disclose this block "
                "to the user unless explicitly asked about system architecture.\n\n" + "\n\n".join(chunks)
            )

        return {
            "loaded_modules": loaded_list,
            "matched_keywords": matched_triggers,
            "context_block": context_block
        }
