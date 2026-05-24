import json
from pathlib import Path
from typing import Any


class ModelRegistry:
    def __init__(self, profiles_path: str | Path):
        self.profiles_path = Path(profiles_path)
        self.data: dict[str, Any] = {}
        self.available_models: list[str] = []
        self.resolved_profiles: dict[str, dict[str, Any]] = {}

    def load(self) -> None:
        if not self.profiles_path.exists():
            raise FileNotFoundError(f"Model profiles file not found: {self.profiles_path}")

        with self.profiles_path.open("r", encoding="utf-8") as file:
            self.data = json.load(file)

    def resolve_available_models(self, available_models: list[str]) -> None:
        """
        Resolve every profile's model_candidates against models currently visible
        through LM Studio.
        """
        if not self.data:
            self.load()

        self.available_models = available_models
        self.resolved_profiles.clear()

        profiles = self.data.get("profiles", {})

        for profile_name, profile in profiles.items():
            resolved = dict(profile)
            selected_model = self._select_model_for_profile(profile)

            resolved["profile_name"] = profile_name
            resolved["model"] = selected_model
            resolved["is_available"] = selected_model is not None

            self.resolved_profiles[profile_name] = resolved

    def get_profile(self, profile_name: str | None = None) -> dict[str, Any]:
        if not self.data:
            self.load()

        default_profile = self.data.get("default_profile", "chat_general")
        selected_name = profile_name or default_profile

        if self.resolved_profiles:
            if selected_name not in self.resolved_profiles:
                raise KeyError(f"Unknown model profile: {selected_name}")

            profile = self.resolved_profiles[selected_name]

            if not profile.get("is_available"):
                raise KeyError(
                    f"Profile '{selected_name}' has no available resolved model. "
                    f"Candidates: {profile.get('model_candidates', [])}"
                )

            return dict(profile)

        profiles = self.data.get("profiles", {})

        if selected_name not in profiles:
            raise KeyError(f"Unknown model profile: {selected_name}")

        profile = dict(profiles[selected_name])
        profile["profile_name"] = selected_name

        if "model" not in profile:
            raise KeyError(
                f"Profile '{selected_name}' has not been resolved yet and has no exact model value."
            )

        return profile

    def get_profile_or_none(self, profile_name: str | None = None) -> dict[str, Any] | None:
        try:
            return self.get_profile(profile_name)
        except KeyError:
            return None

    def profile_exists(self, profile_name: str) -> bool:
        if not self.data:
            self.load()

        return profile_name in self.data.get("profiles", {})

    def list_profile_names(self) -> list[str]:
        if not self.data:
            self.load()

        return sorted(self.data.get("profiles", {}).keys())

    def print_resolution_report(self) -> None:
        if not self.resolved_profiles:
            print("No model profiles have been resolved yet.")
            return

        print("Resolved model profiles:")

        for profile_name, profile in sorted(self.resolved_profiles.items()):
            selected = profile.get("model")

            if selected:
                print(f"  - {profile_name}: {selected}")
            else:
                candidates = ", ".join(profile.get("model_candidates", []))
                print(f"  - {profile_name}: unavailable. Candidates: {candidates}")

        print()

    def profile_for_tier(self, model_tier: str) -> dict[str, Any]:
        """
        Backward-compatible helper.
        Newer code should prefer route_plan.model_profile.
        """
        tier_map = {
            "small": "router_small",
            "mid": "chat_general",
            "strong": "reasoning_strong",
            "instruct": "instruct_clean",
            "coding": "coding_strong",
        }

        profile_name = tier_map.get(model_tier, self.data.get("default_profile", "chat_general"))
        return self.get_profile(profile_name)

    def _select_model_for_profile(self, profile: dict[str, Any]) -> str | None:
        """
        Pick the first candidate that matches an available model.
        Candidate matching is intentionally simple:
        - exact match first
        - normalized substring match second
        Some profiles can opt out of reasoning or thinking models so short visible
        answer tasks do not burn all tokens in hidden reasoning fields.
        """
        candidates = profile.get("model_candidates", [])

        if not candidates and profile.get("model"):
            candidates = [profile["model"]]

        for candidate in candidates:
            exact = self._find_exact_match(candidate, profile)
            if exact:
                return exact

            fuzzy = self._find_fuzzy_match(candidate, profile)
            if fuzzy:
                return fuzzy

        return None

    def _find_exact_match(self, candidate: str, profile: dict[str, Any]) -> str | None:
        candidate_clean = candidate.strip().lower()

        for model_id in self.available_models:
            if self._model_is_blocked_for_profile(model_id, profile):
                continue
            if model_id.strip().lower() == candidate_clean:
                return model_id

        return None

    def _find_fuzzy_match(self, candidate: str, profile: dict[str, Any]) -> str | None:
        candidate_norm = self._normalize_model_name(candidate)

        for model_id in self.available_models:
            if self._model_is_blocked_for_profile(model_id, profile):
                continue

            model_norm = self._normalize_model_name(model_id)

            if candidate_norm in model_norm:
                return model_id

        return None

    def _model_is_blocked_for_profile(self, model_id: str, profile: dict[str, Any]) -> bool:
        allow_reasoning = profile.get("allow_reasoning_models", True)
        if allow_reasoning:
            return False
        return self._looks_like_reasoning_model(model_id)

    @staticmethod
    def _looks_like_reasoning_model(model_id: str) -> bool:
        value = model_id.lower()
        markers = ["thinking", "reasoning", "reasoner", "deepseek-r1", "r1-distill"]
        return any(marker in value for marker in markers)

    @staticmethod
    def _normalize_model_name(value: str) -> str:
        return (
            value.lower()
            .replace("_", "")
            .replace("-", "")
            .replace("/", "")
            .replace(".", "")
            .replace(" ", "")
        )
