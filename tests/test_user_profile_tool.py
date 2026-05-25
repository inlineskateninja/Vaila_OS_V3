from __future__ import annotations

from pathlib import Path
from System_Tools.user_profile_tool import UserProfileTool


def test_user_profile_tool_instantiation() -> None:
    project_root = Path(__file__).resolve().parents[1]
    tool = UserProfileTool(project_root=project_root)
    assert tool.project_root == project_root
    assert tool.user_details_dir == project_root / "User" / "User_Details"


def test_user_profile_routing_fallback() -> None:
    # Test routing logic when no manifest is active (should return empty list/block gracefully)
    project_root = Path(__file__).resolve().parents[1]
    tool = UserProfileTool(project_root=project_root)
    res = tool.route_context("hello, who are you?")
    assert isinstance(res, dict)
    assert res["loaded_modules"] == []
    assert res["matched_keywords"] == {}
    assert res["context_block"] == ""
