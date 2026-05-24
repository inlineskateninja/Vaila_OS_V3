from pathlib import Path
from tempfile import TemporaryDirectory

from System_Tools.self_assessment import SelfAssessmentTool


def test_self_assessment_exports_report():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        tool = SelfAssessmentTool(project_root=root)
        result = tool.run_self_assessment()
        assert "Self-assessment complete" in result
        reports = list((root / "Sandbox" / "Self_Assessment_Exports").glob("*.md"))
        assert reports
