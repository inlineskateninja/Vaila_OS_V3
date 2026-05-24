from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.time_context import TimeContext, build_time_context


HOME_JANE_DEVICE_TYPES = {"home_jane", "home jane", "home-jane"}
LAPTOP_DEVICE_TYPES = {"laptop", "desktop_client_laptop"}


@dataclass
class ContextToolSpec:
    name: str
    description: str
    required: bool
    inputs: dict[str, str] = field(default_factory=dict)
    privacy_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeviceContext:
    device_id: str = "home_jane"
    device_type: str = "home_jane"
    location_available: bool = False
    location_opt_in: bool = False

    @classmethod
    def from_values(
        cls,
        device_id: str | None = None,
        device_type: str | None = None,
        location_available: bool = False,
        location_opt_in: bool = False,
    ) -> "DeviceContext":
        return cls(
            device_id=(device_id or "home_jane").strip() or "home_jane",
            device_type=normalize_device_type(device_type or device_id or "home_jane"),
            location_available=bool(location_available),
            location_opt_in=bool(location_opt_in),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LocationPolicy:
    device_type: str
    location_available: bool
    location_opt_in: bool
    inclusion_policy: str
    include_location: bool
    log_location: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_prompt_block(self) -> str:
        return "\n".join(
            [
                "[Location Context Policy]",
                f"Device type: {self.device_type}",
                f"Location available: {str(self.location_available).lower()}",
                f"Location opt-in: {str(self.location_opt_in).lower()}",
                f"Inclusion policy: {self.inclusion_policy}",
                f"Include location in model context: {str(self.include_location).lower()}",
                f"Log location data: {str(self.log_location).lower()}",
                f"Reason: {self.reason}",
                "Raw location data collected: false",
            ]
        )


@dataclass
class ContextToolResult:
    name: str
    ok: bool
    required: bool
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SessionContext:
    time_context: TimeContext
    device_context: DeviceContext
    location_policy: LocationPolicy
    tool_results: list[ContextToolResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_context": self.time_context.to_dict(),
            "device_context": self.device_context.to_dict(),
            "location_policy": self.location_policy.to_dict(),
            "tools": [result.to_dict() for result in self.tool_results],
        }

    def to_prompt_block(self) -> str:
        return "\n\n".join(
            [
                "[Session Context Tools]",
                "- time_context: required and active for every chat call.",
                "- location_policy: required policy check; no raw location data is collected by this tool.",
                self.time_context.to_prompt_block(),
                self.location_policy.to_prompt_block(),
            ]
        )


def normalize_device_type(value: str) -> str:
    normalized = value.strip().lower().replace("_", " ").replace("-", " ")
    if normalized in HOME_JANE_DEVICE_TYPES:
        return "home_jane"
    if normalized in LAPTOP_DEVICE_TYPES:
        return "laptop"
    return normalized.replace(" ", "_") or "unknown_device"


def context_tool_specs() -> list[ContextToolSpec]:
    return [
        ContextToolSpec(
            name="time_context",
            description="Adds request timestamps and resolves relative time phrases for routing and memory lookup.",
            required=True,
            inputs={"user_text": "Current user request.", "timezone": "Preferred local timezone."},
            privacy_notes=["No location lookup is required for timezone-based time context."],
        ),
        ContextToolSpec(
            name="location_policy",
            description="Determines whether location context may be included or logged for the active device.",
            required=True,
            inputs={
                "device_type": "home_jane, laptop, phone, tablet, wearable, or another device class.",
                "location_available": "Whether the device layer has location identification available.",
                "location_opt_in": "Whether optional laptop location inclusion has been enabled.",
            },
            privacy_notes=[
                "Home Jane never logs location data.",
                "Laptop location is optional.",
                "Other location-capable devices must include location context when available.",
            ],
        ),
    ]


def resolve_location_policy(device_context: DeviceContext) -> LocationPolicy:
    device_type = normalize_device_type(device_context.device_type)
    location_available = bool(device_context.location_available)
    location_opt_in = bool(device_context.location_opt_in)

    if device_type == "home_jane":
        return LocationPolicy(
            device_type=device_type,
            location_available=location_available,
            location_opt_in=location_opt_in,
            inclusion_policy="never_log",
            include_location=False,
            log_location=False,
            reason="Home Jane is the source-of-truth system and must never log location data.",
        )

    if device_type == "laptop":
        include_location = location_available and location_opt_in
        return LocationPolicy(
            device_type=device_type,
            location_available=location_available,
            location_opt_in=location_opt_in,
            inclusion_policy="optional",
            include_location=include_location,
            log_location=include_location,
            reason="Laptop location is included only when location is available and the user has opted in.",
        )

    include_location = location_available
    return LocationPolicy(
        device_type=device_type,
        location_available=location_available,
        location_opt_in=location_opt_in,
        inclusion_policy="mandatory_if_available",
        include_location=include_location,
        log_location=include_location,
        reason="Non-laptop devices with location identification available must include location context.",
    )


def build_session_context(
    user_text: str,
    device_context: DeviceContext | None = None,
    timezone_name: str = "America/New_York",
) -> SessionContext:
    device_context = device_context or DeviceContext()
    time_context = build_time_context(user_text, timezone_name=timezone_name)
    location_policy = resolve_location_policy(device_context)
    tool_results = [
        ContextToolResult(
            name="time_context",
            ok=True,
            required=True,
            result=time_context.to_dict(),
        ),
        ContextToolResult(
            name="location_policy",
            ok=True,
            required=True,
            result=location_policy.to_dict(),
        ),
    ]
    return SessionContext(
        time_context=time_context,
        device_context=device_context,
        location_policy=location_policy,
        tool_results=tool_results,
    )
